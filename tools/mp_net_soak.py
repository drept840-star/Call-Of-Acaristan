"""Headless arena network test with optional TCP and UDP impairment.

Examples (run from the repository root):
    python tools/mp_net_soak.py
    python tools/mp_net_soak.py --players 4 --seconds 12 --latency-ms 45 --jitter-ms 12
    python tools/mp_net_soak.py --players 4 --loss-percent 1.0
    python tools/mp_net_soak.py --lag-shot-check --latency-ms 35
    python tools/mp_net_soak.py --players 2 --block-udp --require-tcp-fallback
    python tools/mp_net_soak.py --players 2 --block-udp --punch

TCP bytes stay ordered; ``--loss-percent`` models retransmission stalls there,
and actually drops disposable UDP motion packets (which may also reorder).
"""

import argparse
import collections
import os
import random
import select
import socket
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from net import portmap  # noqa: E402
from net import roomcode  # noqa: E402
from ui.match_screen import MatchScreen  # noqa: E402
from missions import arena as AR  # noqa: E402

UDP_MAX_PACKET = 1201


class TcpImpairmentProxy(object):
    """Local TCP forwarder adding latency/jitter and loss-like stalls."""

    def __init__(self, target, latency_ms=0.0, jitter_ms=0.0,
                 loss_percent=0.0, stall_ms=120.0, seed=None,
                 udp_enabled=True, rate_kbps=0.0, queue_kb=1024.0):
        self.target = target
        self.latency = max(0.0, latency_ms) / 1000.0
        self.jitter = max(0.0, jitter_ms) / 1000.0
        self.loss = min(100.0, max(0.0, loss_percent)) / 100.0
        self.stall = max(0.0, stall_ms) / 1000.0
        # A rate cap models a slow relay hop: bytes beyond the bottleneck
        # queue stay in the sender's own buffers, where real backlogs form.
        self.rate = max(0.0, rate_kbps) * 1024.0
        self.queue_limit = int(max(1.0, queue_kb) * 1024)
        self.rng = random.Random(seed)
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(8)
        self.listener.settimeout(0.2)
        self.port = self.listener.getsockname()[1]
        self.udp_listener = None
        self.udp_relay = None
        self.udp_client_to_host = 0
        self.udp_host_to_client = 0
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._accept_loop,
                                       name="mp-impairment-proxy", daemon=True)
        self.udp_thread = None
        if udp_enabled:
            # Bind UDP on the same numeric port (TCP and UDP have separate
            # port spaces), so the datagram channel experiences the same
            # impairment as its reliable control connection.
            self.udp_listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_listener.bind(("127.0.0.1", self.port))
            self.udp_listener.setblocking(False)
            self.udp_relay = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_relay.bind(("127.0.0.1", 0))
            self.udp_relay.setblocking(False)
            self.udp_thread = threading.Thread(
                target=self._udp_loop, name="mp-udp-impairment", daemon=True)
        self.thread.start()
        if self.udp_thread is not None:
            self.udp_thread.start()

    def _accept_loop(self):
        while not self.stopped.is_set():
            try:
                client, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._relay, args=(client,), daemon=True).start()

    def _relay(self, client):
        upstream = None
        try:
            upstream = socket.create_connection(self.target, timeout=3.0)
            if self.rate:
                # Loopback buffers would otherwise add far more queue than
                # the modelled bottleneck itself.
                for sock in (client, upstream):
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8192)
            client.setblocking(False)
            upstream.setblocking(False)
            # Each entry is [delivery_time, bytes]. The monotonically ordered
            # deadlines preserve TCP's byte order within each direction.
            to_client = collections.deque()
            to_host = collections.deque()
            last_due = {client: 0.0, upstream: 0.0}
            while not self.stopped.is_set():
                now = time.monotonic()
                read_socks = []
                if sum(len(x[1]) for x in to_host) < self.queue_limit:
                    read_socks.append(client)
                if sum(len(x[1]) for x in to_client) < self.queue_limit:
                    read_socks.append(upstream)
                write_socks = []
                if to_host and to_host[0][0] <= now:
                    write_socks.append(upstream)
                if to_client and to_client[0][0] <= now:
                    write_socks.append(client)
                deadlines = [q[0][0] for q in (to_client, to_host) if q]
                timeout = 0.01
                if deadlines:
                    timeout = min(timeout, max(0.0, min(deadlines) - now))
                ready_r, ready_w, _ = select.select(read_socks, write_socks,
                                                    [], timeout)
                for src in ready_r:
                    queue = to_host if src is client else to_client
                    room = self.queue_limit - sum(len(x[1]) for x in queue)
                    try:
                        chunk = src.recv(max(1, min(65536, room)))
                    except (BlockingIOError, OSError):
                        continue
                    if not chunk:
                        return
                    dest = upstream if src is client else client
                    queue = to_host if src is client else to_client
                    now = time.monotonic()
                    delay = self.latency + self.rng.uniform(-self.jitter,
                                                            self.jitter)
                    delay = max(0.0, delay)
                    if self.rng.random() < self.loss:
                        delay += self.stall
                    due = max(now + delay, last_due[dest])
                    if self.rate:
                        due = max(now + delay,
                                  last_due[dest] + len(chunk) / self.rate)
                    last_due[dest] = due
                    queue.append([due, chunk])
                for dest in ready_w:
                    queue = to_host if dest is upstream else to_client
                    if not queue:
                        continue
                    try:
                        sent = dest.send(queue[0][1])
                    except (BlockingIOError, OSError):
                        continue
                    if sent <= 0:
                        return
                    if sent == len(queue[0][1]):
                        queue.popleft()
                    else:
                        queue[0][1] = queue[0][1][sent:]
        except OSError:
            pass
        finally:
            for sock in (client, upstream):
                if sock is not None:
                    try:
                        sock.close()
                    except OSError:
                        pass

    def _udp_loop(self):
        """Impair both UDP directions while preserving datagram boundaries."""
        if self.udp_listener is None or self.udp_relay is None:
            return
        to_host, to_client = [], []
        client_addr = None
        while not self.stopped.is_set():
            now = time.monotonic()
            read_socks = [self.udp_listener, self.udp_relay]
            write_socks = []
            if any(item[0] <= now for item in to_host):
                write_socks.append(self.udp_relay)
            if any(item[0] <= now for item in to_client):
                write_socks.append(self.udp_listener)
            deadlines = [q[0][0] for q in (to_host, to_client) if q]
            timeout = 0.01
            if deadlines:
                timeout = min(timeout, max(0.0, min(deadlines) - now))
            try:
                ready_r, ready_w, _ = select.select(
                    read_socks, write_socks, [], timeout)
            except (OSError, ValueError):
                break
            for src in ready_r:
                try:
                    data, addr = src.recvfrom(UDP_MAX_PACKET)
                except (BlockingIOError, OSError):
                    continue
                if src is self.udp_listener:
                    client_addr = addr
                    queue = to_host
                    destination = self.target
                else:
                    if addr[0] != self.target[0] or addr[1] != self.target[1]:
                        continue
                    if client_addr is None:
                        continue
                    queue = to_client
                    destination = client_addr
                if self.rng.random() < self.loss:
                    continue  # UDP loss is an actual dropped datagram.
                delay = max(0.0, self.latency +
                            self.rng.uniform(-self.jitter, self.jitter))
                if len(queue) >= 1024:
                    queue.pop(0)
                queue.append([time.monotonic() + delay, data, destination])
            for dest_sock in ready_w:
                queue = to_host if dest_sock is self.udp_relay else to_client
                now = time.monotonic()
                # Independent datagrams may overtake each other when jitter
                # differs, matching real UDP rather than preserving a stream.
                for index in range(len(queue) - 1, -1, -1):
                    if queue[index][0] > now:
                        continue
                    _due, data, destination = queue[index]
                    try:
                        dest_sock.sendto(data, destination)
                    except (BlockingIOError, OSError):
                        continue
                    queue.pop(index)

    def close(self):
        self.stopped.set()
        for sock in (self.listener, self.udp_listener, self.udp_relay):
            if sock is None:
                continue
            try:
                sock.close()
            except OSError:
                pass
        self.thread.join(timeout=0.5)
        if self.udp_thread is not None:
            self.udp_thread.join(timeout=0.5)


def _advance(screens, dt, keys, mouse):
    """Advance the host first, then every client through real game code."""
    host = screens[0]
    host.update(keys, mouse, dt)
    for screen in screens[1:]:
        # Clients begin in panel mode with a queued join action; their first
        # update transitions them into the live socket-backed match screen.
        screen.update(keys, mouse, dt)


class FakeStunServer(object):
    """Loopback STUN server: answers each binding request with its source.

    Stands in for the public servers so --punch never leaves this machine.
    """

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        import struct
        magic = portmap.STUN_MAGIC
        while self.running:
            try:
                data, (ip, port) = self.sock.recvfrom(2048)
            except (socket.timeout, OSError):
                continue
            if len(data) < 20:
                continue
            xaddr = struct.unpack("!I", socket.inet_aton(ip))[0] ^ magic
            attr = struct.pack("!HHBBHI", 0x0020, 8, 0, 1,
                               port ^ (magic >> 16), xaddr)
            reply = (struct.pack("!HHI", portmap.STUN_BINDING_RESPONSE,
                                 len(attr), magic) + data[8:20] + attr)
            try:
                self.sock.sendto(reply, (ip, port))
            except OSError:
                pass

    def close(self):
        self.running = False
        self.sock.close()


class _Keys(object):
    """Tiny key-state object usable by MatchScreen without a real keyboard."""
    def __init__(self, *held):
        self.held = set(held)

    def __getitem__(self, key):
        return key in self.held


def _run_lag_shot_check(host, client, proxy=None):
    """Fire through the real delayed TCP path at a target moving on the host.

    The client aims at its interpolated world while the host moves the target.
    We only pull the trigger once the present-day target has moved outside the
    shot line, then require host-confirmed damage from the client's real input
    packet. This would fail if the host went back to current-position-only
    hit detection.
    """
    dt = 1.0 / 60.0
    idle = _Keys()
    down = _Keys(pygame.K_s)
    no_mouse = (500, 350, False)
    player_id = client.sess.local_id
    if player_id is None or player_id not in host.sim.players:
        raise RuntimeError("lag-shot check has no assigned client player")

    sim = host.sim
    sim.walls = []
    sim.rules.walls = []
    runner = sim.players[0]       # host moves the target down the screen
    shooter = sim.players[player_id]
    shooter.update(x=180.0, y=300.0, angle=0.0, hp=100, armour=0,
                   dead=False, reload=0, cooldown=0, spread=0.0,
                   sprinting=False, dry_latch=False)
    runner.update(x=300.0, y=300.0, angle=180.0, hp=100, armour=0,
                  dead=False, reload=0, cooldown=0, spread=0.0,
                  sprinting=False, dry_latch=False)
    sim.rules.spawned_at[0] = sim.tick - 1000
    sim.rules.spawned_at[player_id] = sim.tick - 1000
    sim.rules.note_position(0, (runner["x"], runner["y"]))
    sim.rules.note_position(player_id, (shooter["x"], shooter["y"]))
    host.sess.world = sim.snapshot_entities()
    host.sess.broadcast()
    if client._pred is not None:
        client._pred.walls = []
        client._pred.reconcile(shooter["x"], shooter["y"], 0.0)

    # Let that setup snapshot traverse the same proxy before moving anyone.
    ready = False
    for _ in range(120):
        host.update(idle, no_mouse, dt)
        client.update(idle, no_mouse, dt)
        world = client.sess.sample_world() or {}
        local = world.get(player_id)
        other = world.get(0)
        if (local is not None and other is not None
                and abs(local[2] - shooter["x"]) < 3.0
                and abs(other[2] - runner["x"]) < 3.0):
            ready = True
            break
        time.sleep(dt)
    if not ready:
        raise RuntimeError("client did not receive the prepared positions")

    off_line_at_fire = False
    hit = False
    initial_hp = runner["hp"]
    last_offset = 0.0
    # The client aims at what its interpolator currently displays. The host
    # walks the target steadily so that its present location is clearly off
    # that displayed shot line before the client fires.
    for _ in range(240):
        host.update(down, no_mouse, dt)
        world = client.sess.sample_world() or {}
        target = world.get(0)
        pred = client._pred
        fire = False
        mouse = no_mouse
        if target is not None and pred is not None and pred.seeded:
            tx, ty = float(target[2]), float(target[3])
            dx, dy = tx - pred.x, ty - pred.y
            length = max(1.0, (dx * dx + dy * dy) ** 0.5)
            current = sim.players[0]
            # Perpendicular distance from the current target to the line the
            # shooter is aiming along; beyond PLAYER_RADIUS means a present-
            # position-only trace cannot hit.
            offset = abs(dx * (current["y"] - pred.y)
                         - dy * (current["x"] - pred.x)) / length
            last_offset = offset
            fire = offset > AR.PLAYER_RADIUS + 5.0
            off_line_at_fire = off_line_at_fire or fire
            mouse = (int(round(tx - client.view.cam_x)),
                     int(round(ty - client.view.cam_y)), fire)
        client.update(idle, mouse, dt)
        if runner["hp"] < initial_hp:
            hit = True
            break
        time.sleep(dt)

    rewound = getattr(sim, "lag_compensated_shots", 0)
    ticks_rewound = getattr(sim, "rewind_ticks_total", 0)
    if not off_line_at_fire:
        raise RuntimeError("test never aimed while the current target was off-line "
                           "(last offset %.1f px)" % last_offset)
    if not hit:
        raise RuntimeError("the delayed shot caused no host-confirmed damage "
                           "(current-to-aim offset %.1f px, rewound shots %d)"
                           % (last_offset, rewound))
    if rewound <= 0 or ticks_rewound <= 0:
        raise RuntimeError("host damage arrived without using recent position history")
    if not client._udp_active:
        peer = next((p for p in host.peers
                     if p.player_id == client.sess.local_id), None)
        details = (
            bool(client._udp_token), client._udp_peer_addr,
            client._udp_last_snapshot, getattr(peer, "udp_ready", None),
            getattr(peer, "udp_addr", None), client._udp_fallback_until,
            client._udp_last_rx, client._udp_acked_nonce,
            (getattr(proxy, "udp_client_to_host", None),
             getattr(proxy, "udp_host_to_client", None)))
        raise RuntimeError(
            "shot check passed only after falling back to TCP; UDP path "
            "did not stay healthy (token=%s, endpoint=%r, last_snapshot=%.3f, "
            "host_ready=%r, host_addr=%r, fallback_until=%.3f, "
            "last_rx=%.3f, acked=%r, relay=%r)" % details)
    print("LAG SHOT CHECK: PASS | delayed UDP shot hit the moving target after "
          "its current position left the aim line | rewound inputs=%d, "
          "ticks=%d" % (rewound, ticks_rewound))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--players", type=int, default=4,
                    help="total players including host (2..8, default 4)")
    ap.add_argument("--seconds", type=float, default=8.0,
                    help="live test duration in seconds (default 8)")
    ap.add_argument("--latency-ms", type=float, default=35.0,
                    help="one-way latency added by each client proxy")
    ap.add_argument("--jitter-ms", type=float, default=8.0,
                    help="uniform per-chunk jitter")
    ap.add_argument("--loss-percent", type=float, default=0.5,
                    help="chance of a TCP-like retransmission stall or a dropped UDP packet")
    ap.add_argument("--stall-ms", type=float, default=120.0,
                    help="extra delay for a simulated loss event")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--rate-kbps", type=float, default=0.0,
                    help="cap each TCP direction to this many KiB/s (0 = no cap)")
    ap.add_argument("--queue-kb", type=float, default=1024.0,
                    help="bottleneck queue in the TCP proxy (KiB, default 1024)")
    ap.add_argument("--max-view-delay-ms", type=float, default=0.0,
                    help="fail if a client's newest snapshot trails the host by more")
    ap.add_argument("--lag-shot-check", action="store_true",
                    help="run a real delayed UDP shot against a moving target; uses 2 players")
    ap.add_argument("--block-udp", action="store_true",
                    help="block the datagram path to test automatic TCP compatibility fallback")
    ap.add_argument("--punch", action="store_true",
                    help="with --block-udp: host behind a TCP-only route; "
                         "require a hole-punched direct UDP path")
    ap.add_argument("--require-tcp-fallback", action="store_true",
                    help="fail unless blocked-UDP clients keep receiving snapshots over TCP")
    args = ap.parse_args(argv)
    if args.lag_shot_check:
        args.players = 2
    if args.lag_shot_check and args.block_udp:
        ap.error("--lag-shot-check requires UDP; do not combine it with --block-udp")
    if args.punch and (not args.block_udp or args.require_tcp_fallback):
        ap.error("--punch needs --block-udp and excludes --require-tcp-fallback")
    if args.require_tcp_fallback and not args.block_udp:
        ap.error("--require-tcp-fallback must be used with --block-udp")
    if not 2 <= args.players <= 8:
        ap.error("--players must be between 2 and 8")
    if args.seconds <= 0:
        ap.error("--seconds must be positive")

    pygame.init()
    pygame.display.set_mode((1000, 700))
    keys = pygame.key.get_pressed()
    idle_mouse = (500, 350, False)
    host = MatchScreen()
    clients = []
    proxies = []
    stun = None
    old_stun = portmap.STUN_SERVERS
    try:
        host.open_panel()
        host.players = args.players
        host.mode_name = AR.MODE_FFA
        host.player_name = "SOAK-HOST"
        host.request_host(0)
        host.update(keys, idle_mouse, 1.0 / 60.0)
        if host.mode != "hosting" or host.srv is None:
            raise RuntimeError("host failed to start: %s" % host.status)
        if args.punch:
            # The proxy drops UDP like a bore tunnel; only a punched path
            # straight to the host's game socket can carry datagrams.
            stun = FakeStunServer()
            portmap.STUN_SERVERS = (("127.0.0.1", stun.port),)
            host._start_udp_punching()
        target = ("127.0.0.1", host.srv.getsockname()[1])
        for i in range(1, args.players):
            proxy = TcpImpairmentProxy(
                target, args.latency_ms, args.jitter_ms, args.loss_percent,
                args.stall_ms, seed=args.seed + i,
                udp_enabled=not args.block_udp, rate_kbps=args.rate_kbps,
                queue_kb=args.queue_kb)
            proxies.append(proxy)
            client = MatchScreen()
            client.open_panel()
            client.player_name = "SOAK-%02d" % i
            client.request_join("127.0.0.1:%d@%s" %
                                (proxy.port, host.join_token))
            clients.append(client)

        screens = [host] + clients
        deadline = time.monotonic() + 12.0
        while len(host.peers) < args.players - 1 and time.monotonic() < deadline:
            _advance(screens, 1.0 / 60.0, keys, idle_mouse)
            time.sleep(1.0 / 120.0)
        if len(host.peers) != args.players - 1:
            raise RuntimeError("only %d/%d clients joined (%s)" % (
                len(host.peers) + 1, args.players,
                "; ".join(c.status for c in clients)))
        if not host._begin_countdown():
            raise RuntimeError("could not start test match: %s" % host.status)

        # The requested duration is live-match time, not lobby/countdown time.
        # Wait until every client has received the host's playing phase so even
        # short runs contain real 20 Hz snapshots rather than only the seed.
        ready_deadline = time.monotonic() + 10.0
        while (host.session_phase() != "playing"
               or any(c.session_phase() != "playing" for c in clients)):
            if time.monotonic() >= ready_deadline:
                raise RuntimeError("clients did not enter live play")
            frame_start = time.monotonic()
            _advance(screens, 1.0 / 60.0, keys, idle_mouse)
            time.sleep(max(0.0, 1.0 / 60.0 -
                           (time.monotonic() - frame_start)))

        if args.lag_shot_check:
            _run_lag_shot_check(host, clients[0], proxies[0])

        end = time.monotonic() + args.seconds
        settle = time.monotonic() + args.seconds * 0.5
        # How far each client's newest snapshot trails the host sim, sampled
        # over the second half so a standing backlog shows up, not warm-up.
        view_delay = [[] for _ in clients]
        frame = 0
        last = time.monotonic()
        while time.monotonic() < end:
            now = time.monotonic()
            dt = min(0.1, max(1.0 / 240.0, now - last))
            last = now
            _advance(screens, dt, keys, idle_mouse)
            frame += 1
            if now >= settle:
                for index, client in enumerate(clients):
                    snap = client._latest_snap_tick
                    if snap is not None:
                        view_delay[index].append(
                            (host.sess.tick - snap) * 1000.0 / 60.0)
            # A ~60 Hz pump makes this a modest soak rather than a CPU burner.
            time.sleep(max(0.0, 1.0 / 60.0 - (time.monotonic() - now)))

        failures = []
        print("Arena network soak: %d total | latency %gms one-way | "
              "jitter %gms | TCP stalls / UDP drops %g%% (TCP +%gms) | "
              "%d frames" % (
                  args.players, args.latency_ms, args.jitter_ms,
                  args.loss_percent, args.stall_ms, frame))
        for index, client in enumerate(clients, 1):
            stats = client.net_telemetry.stats()
            print("  player %d: ping=%sms jitter=%sms snapshots=%d@%sHz "
                  "gaps=%d inputs=%d quality=%s" % (
                      index, stats["rtt_ms"], stats["jitter_ms"],
                      stats["snapshots_received"], stats["snapshot_hz"],
                      stats["snapshot_gaps"], stats["inputs_sent"],
                      stats["quality"]))
            delays = view_delay[index - 1]
            if delays:
                print("  player %d: view delay avg=%.0fms max=%.0fms" % (
                    index, sum(delays) / len(delays), max(delays)))
                if args.max_view_delay_ms and max(delays) > args.max_view_delay_ms:
                    failures.append("player %d view delay %.0fms over %gms" % (
                        index, max(delays), args.max_view_delay_ms))
            if stats["pongs_received"] == 0:
                failures.append("player %d received no heartbeat response" % index)
            if stats["snapshots_received"] < 2:
                failures.append("player %d received too few snapshots" % index)
            if client.mode != "playing":
                failures.append("player %d left unexpectedly: %s" %
                                (index, client.status))
        if args.require_tcp_fallback:
            for index, client in enumerate(clients, 1):
                if client._udp_active:
                    failures.append("player %d unexpectedly marked UDP active" % index)
                if client.net_telemetry.stats()["snapshots_received"] < 2:
                    failures.append("player %d got no TCP fallback snapshots" % index)
            if not failures:
                print("TCP FALLBACK CHECK: PASS | UDP blocked, live snapshots "
                      "continued over the reliable connection")
        if args.punch:
            for index, client in enumerate(clients, 1):
                if not client._udp_active:
                    failures.append("player %d never got a punched UDP path"
                                    % index)
            if not failures:
                print("PUNCH CHECK: PASS | UDP blocked on the tunnel, every "
                      "player reached the host over a punched UDP path")
        if failures:
            print("FAIL: " + "; ".join(failures))
            return 1
        print("SOAK TEST: OK")
        return 0
    except Exception as exc:
        print("SOAK TEST: FAIL: %s" % exc)
        return 1
    finally:
        for client in clients:
            try:
                client.close()
            except Exception:
                pass
        try:
            host.close()
        except Exception:
            pass
        for proxy in proxies:
            proxy.close()
        portmap.STUN_SERVERS = old_stun
        if stun is not None:
            stun.close()
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
