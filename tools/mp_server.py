"""Standalone KRAPNET master server for Call of Acaristan.

Run it next to the game (or on a VPS / LAN box):

    python tools/mp_server.py                       # 127.0.0.1:27015
    python tools/mp_server.py --host 0.0.0.0        # reachable on the LAN
    python tools/mp_server.py --port 27020

What it does
------------
  * Accepts client connections on TCP and answers ``query`` packets with the
    current server list, the way a Steam/Source master server does.
  * Relays ``chat`` lines to every connected client.
  * Optionally advertises itself on UDP 27016 so LAN clients can find it
    with no configuration (see ``--no-discovery`` to disable).

A note on scope: this is a *lobby relay*, not a game server. It carries the
server list and the global chat channel and nothing else -- no simulation, no
player state, no gameplay traffic. Gameplay lives in ARENA MATCH, on its own
socket, and does not pass through here at all (see the ports table in
docs/KRAPNET_MULTIPLAYER.md for why).

There are no accounts, but there are limits: a chat rate floor, a per-name
registration interval, a cap on live rows and a cap on concurrent clients.
Those contain a flood; they do not authenticate anybody. Anyone can still
claim any name.

Everything here is stdlib-only and deliberately boring: a thread per client,
a dict of rows, newline-delimited JSON.
"""

import argparse
import os
import signal
import socket
import socketserver
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from net import protocol as P  # noqa: E402

# The seeded row set: the servers the master reports when no real game
# server has registered, so a fresh install still has something to browse.
SEED_SERVERS = [
    ("Vasile's Cigarette Break", 1, 4, 12),
    ("Biribel's Safe House (PASS: 742)", 0, 2, 67),
    ("MAG Recruitment Center", 24, 32, 88),
    ("Krapistan #1 Official", 0, 64, 350),
    ("noobs only pls", 3, 10, 156),
    ("[24/7] OIL RIG EXPLOSION SIM", 12, 16, 78),
    ("MR.BEAST GIVING AWAY CIGARETTES", 99, 100, 45),
    ("yo mama's basement", 1, 2, 4),
]

SEED_RULES = {
    "Vasile's Cigarette Break": [
        "GAMEMODE:  Cigarette Break",
        "MAP:       Alleyway",
        "RULES:     Nobody is actually on a break.",
    ],
    "MAG Recruitment Center": [
        "GAMEMODE:  Recruitment",
        "MAP:       Recruitment Hall",
        "RULES:     Sign the sheet. Then sign up.",
    ],
    "Krapistan #1 Official": [
        "GAMEMODE:  Official Business",
        "MAP:       Krapistan City",
        "RULES:     Read the rules. They are the rules.",
    ],
}

SERVER_TTL = 15.0
MAX_MSG = 1 << 20

# ── Abuse limits ────────────────────────────────────────────────────────
# This master has no accounts and no passwords, which is a deliberate choice
# (paste an address, play) but it does NOT mean "unlimited". Without these a
# single client can flood every connected player's chat panel, publish
# thousands of fake rows to replace the real list, or open connections until
# the master runs out of threads. Each limit below is a floor a human cannot
# hit by accident and a script trips in seconds.
#
# What this is NOT: authentication. Anyone can still claim any name and any
# row. These bounds contain annoyance; they do not establish identity. See
# "Known limitations" in docs/KRAPNET_MULTIPLAYER.md.
CHAT_MIN_GAP = 0.4          # seconds between one client's chat lines
CHAT_BURST = 5             # ...but a burst of N is allowed back to back
CHAT_WINDOW = 10.0         # the burst is refilled over this many seconds
# Registration is how a row gets into everyone's browser, so it is the most
# abusable verb here. One row per name per interval is generous for a host
# re-registering its 15s TTL and impossible to spam with.
REGISTER_MIN_GAP = 2.0
REGISTER_MAX_NAMES = 64    # distinct live rows before further ones are refused
MAX_CLIENTS = 128          # concurrent sockets before new ones are refused



class TokenGate(object):
    """A token bucket with a floor, for one client.

    The floor is the part that matters for chat: a plain "N per second" limit
    punishes a fast typist exactly when they are most worth listening to, so a
    single line is always allowed through after ``gap`` seconds, while a burst
    of ``burst`` is allowed back to back and then refills at one per ``gap``.
    A human sending three quick lines is untouched; a script sending three
    hundred is cut off immediately.
    """

    def __init__(self, gap, burst):
        self.gap = max(0.0, float(gap))
        self.burst = max(1, int(burst))
        self.tokens = float(self.burst)
        self.last = time.monotonic()

    def allow(self):
        now = time.monotonic()
        self.tokens = min(float(self.burst),
                          self.tokens + (now - self.last) / max(self.gap, 1e-6))
        self.last = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class MasterState(object):
    """Shared, lock-guarded state for one master process."""

    def __init__(self, seed=True):
        self.lock = threading.Lock()
        # name -> {"name","current","max","ping","rules","seen"}
        self.servers = {}
        # conn -> {"id","name","sock"}
        self.clients = {}
        self.chat_log = []
        self.next_id = 1
        self.started = time.time()
        self.msg_counts = {}
        # Name -> monotonic time of its last accepted register. A gate per
        # NAME rather than per connection, because the abuse is "publish many
        # rows", and one socket could otherwise rename itself per line.
        self.register_seen = {}
        if seed:
            now = time.monotonic()
            for name, cur, mx, ping in SEED_SERVERS:
                self.servers[name] = {
                    "name": name,
                    "current": cur,
                    "max": mx,
                    "ping": ping,
                    "rules": SEED_RULES.get(name, []),
                    "seen": now,
                }

    def client_count(self):
        with self.lock:
            return len(self.clients)

    def may_register(self, name):
        """True if *name* may publish a row now. Records the attempt either way.

        The timestamp is recorded on every attempt, accepted or not, so a
        client that keeps hammering is slowed to one attempt per interval
        instead of one per round trip.
        """
        now = time.monotonic()
        with self.lock:
            live = len(self.servers)
            if live >= REGISTER_MAX_NAMES and name not in self.servers:
                return False, "server list is full (%d rows)" % live
            last = self.register_seen.get(name)
            if last is not None and now - last < REGISTER_MIN_GAP:
                return False, "registering too often; retry in %.1fs" % (
                    REGISTER_MIN_GAP - (now - last))
            self.register_seen[name] = now
            if len(self.register_seen) > 512:
                # Bound the bookkeeping, not the rows: an attacker must not be
                # able to grow this dict forever with names they never use.
                cutoff = now - REGISTER_MIN_GAP
                self.register_seen = dict(
                    (n, t) for n, t in self.register_seen.items() if t >= cutoff)
            return True, ""

    def register(self, row, rules=None):
        name, cur, mx, ping = row
        with self.lock:
            self.servers[name] = {
                "name": name,
                "current": cur,
                "max": mx,
                "ping": ping,
                "rules": list(rules or []),
                "seen": time.monotonic(),
            }
            return name

    def sweep(self):
        """Drop rows that stopped re-registering. Returns the dropped names."""
        now = time.monotonic()
        with self.lock:
            dead = [n for n, r in self.servers.items()
                    if now - r["seen"] > SERVER_TTL]
            for n in dead:
                del self.servers[n]
            return dead

    def list_payload(self):
        """Build the ``servers`` body: rows plus a rules side-table."""
        with self.lock:
            rows = [[r["name"], r["current"], r["max"], r["ping"]]
                    for r in sorted(self.servers.values(), key=lambda r: r["name"])]
            rules = dict((r["name"], r["rules"]) for r in self.servers.values())
        return rows, rules

    def add_chat(self, user, text, color):
        entry = {"user": user, "text": text, "color": color, "ts": time.time()}
        with self.lock:
            self.chat_log.append(entry)
            if len(self.chat_log) > 200:
                del self.chat_log[:-200]
        return entry

    def recent_chat(self, n=25):
        with self.lock:
            return list(self.chat_log[-n:])

    def add_client(self, conn, name):
        with self.lock:
            cid = self.next_id
            self.next_id += 1
            self.clients[conn] = {"id": cid, "name": name, "sock": conn}
            return cid

    def remove_client(self, conn):
        with self.lock:
            self.clients.pop(conn, None)

    def broadcast(self, obj, exclude=None):
        """Send one message to every client. Individual failures are dropped."""
        payload = P.encode(obj)
        with self.lock:
            targets = [(c, d["sock"]) for c, d in self.clients.items()
                       if c is not exclude]
        dead = []
        for conn, sock in targets:
            try:
                sock.sendall(payload)
            except OSError:
                dead.append(conn)
        for conn in dead:
            self.remove_client(conn)



class MasterHandler(socketserver.BaseRequestHandler):
    """One thread per connected client (via ThreadingTCPServer)."""

    def setup(self):
        self.state = self.server.state
        self.request.settimeout(0.5)
        self.buf = b""
        self.alive = True
        self.cid = None
        self.name = "anon"
        # Per-connection limits. Held here rather than in MasterState because
        # they are about THIS socket, and sharing them across clients would
        # mean one flood throttles everybody.
        self.chat_gate = TokenGate(CHAT_MIN_GAP, CHAT_BURST)
        self.spam_warned = False

    def handle(self):
        sock = self.request
        # Connection cap, checked before the client is registered so a refused
        # socket never appears in the broadcast set or the thread pool.
        if self.state.client_count() >= MAX_CLIENTS:
            self.send({"t": P.T_ERROR,
                       "text": "master is full (%d clients); try again later"
                               % MAX_CLIENTS})
            return
        self.cid = self.state.add_client(sock, self.name)
        self.log("client #%d connected from %s" % (
            self.cid, self.client_address[0]))
        self.send({"t": P.T_WELCOME, "name": self.name, "id": self.cid,
                   "proto": P.PROTO_VERSION,
                   "uptime": int(time.time() - self.state.started)})
        # Backfill recent chat so a joiner is not staring at an empty panel.
        for entry in self.state.recent_chat():
            self.send({"t": P.T_CHAT, "user": entry["user"],
                       "text": entry["text"], "color": entry["color"]})
        self.send_servers()
        try:
            while self.alive and not self.server.stopping:
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                self.buf += chunk
                if len(self.buf) > MAX_MSG:
                    self.log("client #%d exceeded max buffer; dropping" % self.cid)
                    break
                while b"\n" in self.buf:
                    line, self.buf = self.buf.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    msg = P.decode(line)
                    if msg:
                        self.on_message(msg)
                    else:
                        self.log("client #%d sent malformed JSON" % self.cid)
        finally:
            self.state.remove_client(sock)
            self.log("client #%d disconnected" % self.cid)

    def log(self, fmt, *a):
        if self.server.verbose:
            sys.stderr.write("[master] " + (fmt % a if a else fmt) + "\n")
            sys.stderr.flush()

    def send(self, obj):
        try:
            self.request.sendall(P.encode(obj))
            return True
        except OSError:
            self.alive = False
            return False

    def send_servers(self):
        rows, rules = self.state.list_payload()
        self.send({"t": P.T_SERVERS, "servers": rows, "rules": rules})

    def on_message(self, msg):
        kind = msg.get("t")
        self.state.msg_counts[kind] = self.state.msg_counts.get(kind, 0) + 1
        if kind == P.T_HELLO:
            name = msg.get("user")
            if isinstance(name, str) and name.strip():
                self.name = name.strip()[:32]
            if msg.get("proto") != P.PROTO_VERSION:
                self.send({"t": P.T_ERROR,
                           "text": "protocol mismatch; update the game"})
            # Re-send welcome now that we know who this is, so the client
            # can adopt the sanitised name (the first welcome still said
            # "anon" because it was sent before HELLO was read).
            self.send({"t": P.T_WELCOME, "name": self.name, "id": self.cid,
                       "proto": P.PROTO_VERSION})
            return
        if kind == P.T_QUERY:
            self.send_servers()
            return
        if kind == P.T_CHAT:
            text = msg.get("text")
            if not isinstance(text, str) or not text.strip():
                return
            # Throttle before relaying, not after: the cost of a flood is
            # paid by every OTHER client receiving it, so the gate has to sit
            # on the broadcast path. Warned once, because a client that is
            # merely typing fast should be corrected, not disconnected.
            if not self.chat_gate.allow():
                if not self.spam_warned:
                    self.spam_warned = True
                    # SOFT: this client is being throttled, not disconnected.
                    # A hard error here would make the client's relay session
                    # drop -- losing its server list and chat -- for having a
                    # fast typist.
                    self.send(P.make_error("sending too fast; slow down",
                                           soft=True))
                return
            text = P.sanitize_chat(text) or ""
            if not text:
                return
            entry = self.state.add_chat(self.name, text, P.color_for(self.name))
            self.state.broadcast({"t": P.T_CHAT, "user": entry["user"],
                                   "text": entry["text"],
                                   "color": entry["color"]})
            self.log("chat <%s> %s" % (self.name, text))
            return
        if kind == P.T_REGISTER:
            row = P.normalize_row(msg.get("row"))
            if row is None:
                self.send({"t": P.T_ERROR, "text": "bad register row"})
                return
            # Rules are the one register field with no bound in normalize_row,
            # so bound it here. Without this a single register can push
            # megabytes into the payload every client parses and draws in a
            # hover tooltip.
            rules = msg.get("rules")
            rules = [str(r)[:64] for r in rules[:16]] \
                if isinstance(rules, list) else []
            allowed, why = self.state.may_register(row[0])
            if not allowed:
                # Soft, for the same reason as the chat throttle: a host that
                # re-registers faster than the interval is misconfigured, not
                # malicious, and dropping its whole session over it would look
                # like the master had gone down.
                self.send(P.make_error(why, soft=True))
                self.log("refused register %r: %s" % (row[0], why))
                return
            self.state.register(row, rules)
            # A refused client may be mid-refresh and want a corrected list.
            self.send_servers()
            self.log("registered %r" % (row[0],))
            return
        if kind == P.T_BYE:
            self.alive = False
            return


class ThreadedTCPServer(socketserver.ThreadingTCPServer):
    """Threaded, reusable-address TCP server.

    allow_reuse_address matters on Windows: without it a restart trips over
    TIME_WAIT on the listening port and the server refuses to start.
    """

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, addr, handler, state, verbose=False):
        self.state = state
        self.verbose = verbose
        self.stopping = False
        socketserver.ThreadingTCPServer.__init__(self, addr, handler)

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        socketserver.ThreadingTCPServer.server_bind(self)



def run_discovery(port, tcp_port, stop_evt, verbose=False):
    """Answer LAN discovery probes so clients need no configuration.

    A client broadcasts DISCOVERY_MAGIC to UDP ``port``; we reply with
    DISCOVERY_REPLY plus the TCP port to use. Windows usually prompts once
    for firewall permission on this socket, which is the intended UX.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("", port))
    except OSError as exc:
        sys.stderr.write("[master] discovery disabled (%s)\n" % exc)
        return
    sys.stderr.write("[master] discovery beacon on udp/%d\n" % port)
    sys.stderr.flush()
    sock.settimeout(0.5)
    while not stop_evt.is_set():
        try:
            data, addr = sock.recvfrom(512)
        except socket.timeout:
            continue
        except OSError:
            break
        if data.strip() == P.DISCOVERY_MAGIC:
            reply = P.DISCOVERY_REPLY + (":%d" % tcp_port).encode("ascii")
            try:
                sock.sendto(reply, addr)
                if verbose:
                    sys.stderr.write("[master] probe from %s\n" % (addr[0],))
            except OSError:
                pass
    sock.close()



def main(argv=None):
    ap = argparse.ArgumentParser(description="Call of Acaristan KRAPNET master")
    ap.add_argument("--host", default="127.0.0.1",
                    help="bind address (use 0.0.0.0 to serve a LAN)")
    ap.add_argument("--port", type=int, default=P.DEFAULT_MASTER_PORT)
    ap.add_argument("--discovery-port", type=int, default=P.DISCOVERY_PORT)
    ap.add_argument("--no-discovery", action="store_true")
    ap.add_argument("--no-seed", action="store_true",
                    help="start with zero servers instead of the fictional set")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)

    verbose = not args.quiet
    state = MasterState(seed=not args.no_seed)
    try:
        server = ThreadedTCPServer((args.host, args.port), MasterHandler,
                                   state, verbose)
    except OSError as exc:
        sys.stderr.write("[master] cannot bind %s:%d -- %s\n" % (
            args.host, args.port, exc))
        return 1

    stop_evt = threading.Event()
    if not args.no_discovery:
        threading.Thread(target=run_discovery,
                         args=(args.discovery_port, args.port, stop_evt, verbose),
                         daemon=True).start()

    def _sig(_signum, _frame):
        stop_evt.set()
        server.stopping = True
        # shutdown() blocks until serve_forever returns, so it must not be
        # called from the signal handler's own thread.
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, _sig)
    try:
        signal.signal(signal.SIGTERM, _sig)
    except (ValueError, AttributeError, OSError):
        pass  # SIGTERM does not exist on Windows

    sys.stderr.write("[master] listening on %s:%d  (proto %d)\n" % (
        args.host, args.port, P.PROTO_VERSION))
    sys.stderr.write("[master] seeded %d servers%s\n" % (
        len(state.servers),
        "" if args.no_seed else "  (--no-seed to start empty)"))
    sys.stderr.flush()
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        stop_evt.set()
        server.server_close()
        sys.stderr.write("[master] stopped\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

