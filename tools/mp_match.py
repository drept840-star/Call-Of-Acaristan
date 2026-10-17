"""Play a real multiplayer arena match. This is the whole stack in one file.

    python tools/mp_match.py --host                    # you host
    python tools/mp_match.py --join 192.168.1.42:27015  # friend joins
    python tools/mp_match.py --host --tunnel           # public, no router setup

Controls: WASD to move, mouse to aim, left click (hold) to fire, Esc to quit.

This exists because steps 1-3 were proven by headless tests, and a headless
test cannot tell you whether the game is any fun. Running the real renderer
against the real simulation over a real socket is the only way to find the
problems that only appear when all three are wired together at once: input
latency you can feel, camera lag, a fire rate that feels wrong.

It is also the fastest way to play with a friend before the in-game menu
exists, and it uses the same modules the game will, so nothing here is
throwaway.
"""
import argparse
import math
import os
import select
import socket
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

from net import protocol as P  # noqa: E402
from net.match import Fanout, MatchSession, TICK_RATE  # noqa: E402
from missions import arena as AR  # noqa: E402
from ui.arena_view import ArenaView  # noqa: E402

VIEW_W, VIEW_H = 1000, 700
STEP = 1.0 / TICK_RATE
SCORE_LIMIT = 15


class Wire(object):
    """Newline-JSON framing over a socket, shared by host and client.

    Reuses the relay lobby's framing exactly rather than inventing a second
    transport; anything that speaks the lobby can speak this.
    """

    def __init__(self, sock):
        self.sock = sock
        self.out = b""
        self.lock = threading.Lock()

    # Named _send, not send, to match MPRelayClient: that is the contract
    # MatchSession._send() looks for. Naming it `send` meant the attribute
    # lookup failed, every snapshot was silently dropped, and the client
    # rendered an empty world -- which reads like a rendering bug rather
    # than a missing underscore.
    def _send(self, obj):
        with self.lock:
            self.out += P.encode(obj)
            if len(self.out) > 16384:
                self.flush()

    def flush(self):
        with self.lock:
            if not self.out:
                return
            data, self.out = self.out, b""
        try:
            self.sock.sendall(data)
        except OSError:
            pass


def aim_degrees(mouse, player_xy, cam_x, cam_y):
    """Angle from the player toward the mouse, in degrees.

    The mouse is screen-space, so it is converted back into world space
    first. Getting this wrong makes everyone shoot in a direction that
    looks right on their own screen and is nonsense to everybody else.
    """
    wx, wy = mouse[0] + cam_x, mouse[1] + cam_y
    return math.degrees(math.atan2(wy - player_xy[1],
                                   wx - player_xy[0])) % 360.0


def parse_addr(text):
    """'host', 'host:port', or a pasted cloudflared/ngrok address."""
    t = (text or "").strip().strip('"').strip("'")
    for pre in ("tcp://", "http://", "https://"):
        if t.lower().startswith(pre):
            t = t[len(pre):]
    t = t.rstrip("/")
    for sep in ("?", "#", "/"):
        if sep in t:
            t = t.split(sep, 1)[0]
    port = 27015
    if t.count(":") == 1:
        h, _, p = t.partition(":")
        if p.isdigit() and 1 <= int(p) <= 65535:
            t, port = h, int(p)
    return t or "127.0.0.1", port


def _open_display():
    screen = pygame.display.set_mode((VIEW_W, VIEW_H))
    pygame.display.set_caption("ACARISTAN -- ARENA")
    return screen


class Peer(object):
    """One connected client and the player slot it owns.

    Keeping the read buffer and the assigned id together on the connection
    is what stops the classic roster bug: assigning a player id at accept
    time but freeing it somewhere else, so a late joiner inherits a slot
    whose previous owner is still sending input.
    """

    def __init__(self, sock, addr, player_id):
        self.sock = sock
        self.addr = addr
        self.player_id = player_id
        self.wire = Wire(sock)
        self.buf = b""

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def run_host(args, screen):
    """Bind, accept a roster of players, then simulate and render at 60 Hz.

    Accepting continues for the whole match, not just at the start, so a
    friend who is late still gets a slot instead of being told the match
    already began. That is what makes "invite three people" work.
    """
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", args.port))
    srv.listen(args.players)
    srv.setblocking(False)
    local_ip = socket.gethostbyname(socket.gethostname())
    print("Hosting %s on port %d.  Local: %s:%d"
          % (args.map, args.port, local_ip, args.port))
    print("Up to %d players.  Waiting for someone to join..." % args.players)

    # Slot 0 is always the host's own player, so remote players start at 1
    # and the local id stays a constant.
    sess = MatchSession(Fanout(lambda: peers), is_host=True, local_id=0)
    sim = AR.ArenaSim(sess, AR.ARENAS[args.map], score_limit=args.score,
                      map_name=args.map)
    sim.add_player(0, "HOST")
    view = ArenaView(args.map)

    peers = []
    started = False
    clock = pygame.time.Clock()
    acc = 0.0
    running = True
    tracer = None
    tracer_t = 0.0
    while running:
        dt = clock.tick(60) / 1000.0
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                running = False
        keys = pygame.key.get_pressed()
        mx, my = pygame.mouse.get_pos()
        firing = pygame.mouse.get_pressed()[0]

        # ── accept new players ──
        # A full lobby must not spin on accept(); check the count first.
        if len(peers) < args.players - 1:
            try:
                conn, addr = srv.accept()
            except (BlockingIOError, OSError):
                conn = None
            if conn is not None:
                conn.setblocking(False)
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                # Lowest free slot, so ids stay small and stable.
                used = set(p.player_id for p in peers)
                pid = next(i for i in range(1, args.players) if i not in used)
                peers.append(Peer(conn, addr, pid))
                sim.add_player(pid, "P%d" % pid)
                print("P%d joined from %s  (%d/%d)"
                      % (pid, addr[0], len(peers) + 1, args.players))
                if not started:
                    started = True
                    print("Match started.")

        # ── read every client ──
        # select() rather than a thread per peer: a thread each would put
        # shared simulation state behind locks for no benefit, since all the
        # real work has to happen on this one loop anyway.
        if peers:
            try:
                ready, _, _ = select.select([p.sock for p in peers], [], [], 0)
            except (OSError, ValueError):
                ready = []
            for sock in ready:
                peer = next((p for p in peers if p.sock is sock), None)
                if peer is None:
                    continue
                try:
                    chunk = sock.recv(65536)
                except (BlockingIOError, OSError):
                    continue
                if chunk == b"":
                    print("P%d left." % peer.player_id)
                    sim.remove_player(peer.player_id)
                    peer.close()
                    peers.remove(peer)
                    continue
                peer.buf += chunk
                if len(peer.buf) > 1 << 20:
                    # A peer streaming without newlines must not eat RAM.
                    sim.remove_player(peer.player_id)
                    peer.close()
                    peers.remove(peer)
                    continue
                while b"\n" in peer.buf:
                    line, peer.buf = peer.buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    # Hand the RAW dict to _accept_input and let it do the
                    # validating. Parsing here first strips the "t" field, and the
                    # validation in _accept_input then rejects the packet as "not an
                    # input" -- so every remote player's input was silently dropped
                    # while local play worked fine.
                    raw = P.decode(line)
                    if isinstance(raw, dict):
                            sess._accept_input(raw, peer_id=peer.player_id)

        # The host's own player is driven from its keyboard, exactly like a
        # remote one is driven from the network -- one code path, so local
        # and remote play can never diverge.
        me = sim.players[0]
        ax, ay = local_axes(keys)
        buttons = P.F_FIRING if firing else 0
        sess._accept_input(
            {"t": P.T_INPUT, "q": sim.tick, "mx": ax, "my": ay,
             "a": aim_degrees((mx, my), (me["x"], me["y"]),
                              view.cam_x, view.cam_y), "b": buttons},
            peer_id=0)

        acc += min(dt, 0.1)
        steps = 0
        while acc >= STEP and steps < 5:
            sim.step()
            if sim.last_shot:
                tracer = sim.last_shot
                tracer_t = time.time()
            acc -= STEP
            steps += 1

        world = dict((e[0], e) for e in sess.world)
        view.draw(screen, world, 0, sim.scoreboard())
        _draw_lobby(screen, len(peers) + 1, args.players)
        if tracer and time.time() - tracer_t < 0.07:
            _draw_tracer(screen, view, tracer)
        if sim.finished:
            _draw_banner(screen, sim.winner)
        pygame.display.flip()

    srv.close()
    for peer in peers:
        peer.close()


def _draw_lobby(screen, count, maximum):
    """Show the roster size. Without this, a friend whose connection failed
    silently has no way to tell joining apart from being ignored."""
    try:
        font = pygame.font.Font(None, 20)
        surf = font.render("PLAYERS %d/%d" % (count, maximum), True,
                           (170, 180, 200))
    except Exception:
        return
    screen.blit(surf, (screen.get_width() - surf.get_width() - 10, 26))


def _draw_tracer(screen, view, shot):
    x, y, ang, dist = shot
    rad = math.radians(ang)
    sx = int(x - view.cam_x)
    sy = int(y - view.cam_y)
    pygame.draw.line(screen, (255, 226, 150), (sx, sy),
                     (sx + math.cos(rad) * dist,
                      sy + math.sin(rad) * dist), 2)


def _draw_banner(screen, winner):
    try:
        font = pygame.font.Font(None, 64)
        surf = font.render("MATCH OVER", True, (255, 210, 90))
    except Exception:
        return
    screen.blit(surf, (screen.get_width() // 2 - surf.get_width() // 2, 60))


def local_axes(keys):
    """WASD/arrows -> (-1..1, -1..1). """
    dx = dy = 0
    if keys[pygame.K_w] or keys[pygame.K_UP]:
        dy -= 1
    if keys[pygame.K_s] or keys[pygame.K_DOWN]:
        dy += 1
    if keys[pygame.K_a] or keys[pygame.K_LEFT]:
        dx -= 1
    if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
        dx += 1
    return dx, dy
def run_client(args, screen):
    """Connect, send input at 60 Hz, draw interpolated snapshots."""
    host, port = parse_addr(args.join)
    sock = socket.socket()
    sock.connect((host, port))
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.setblocking(False)
    print("Connected to %s:%d.  WASD to move, mouse to aim, hold LMB to fire."
          % (host, port))

    wire = Wire(sock)
    sess = MatchSession(wire, is_host=False, local_id=0)
    view = ArenaView(args.map)
    # Announce as a match client before anything else. The in-game host
    # (ui/match_screen.py) holds every accepted connection unverified until
    # this arrives, so without it an in-game host would drop this tool.
    wire._send(P.make_join_match(args.map))
    wire.flush()

    buf = b""
    seq = 0
    clock = pygame.time.Clock()
    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                running = False
        clock.tick(60)
        keys = pygame.key.get_pressed()
        mx, my = pygame.mouse.get_pos()
        firing = pygame.mouse.get_pressed()[0]

        try:
            chunk = sock.recv(65536)
            if chunk == b"":
                print("Host closed the connection.")
                running = False
            elif chunk:
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    msg = P.parse_snapshot(P.decode(line))
                    if msg is not None:
                        sess._accept_snapshot(P.make_snapshot(*msg))
                        # The only clock both sides share is the host's tick
                        # counter, so the client tracks the newest snapshot
                        # it has rather than counting its own frames. Leaving
                        # sess.tick at 0 would leave the interpolation buffer
                        # permanently behind and the world frozen.
                        sess.tick = msg[0]
        except (BlockingIOError, OSError):
            pass

        world = sess.sample_world() or {}
        me = world.get(0)
        if me is not None:
            # Send input only once we actually know where we are. Sending
            # before the first snapshot would move the host's idea of us
            # from a guessed origin, which is how players end up stuck
            # inside geometry on join.
            ax, ay = local_axes(keys)
            wire._send({"t": P.T_INPUT, "q": seq,
                       "mx": ax, "my": ay,
                       "a": aim_degrees((mx, my), (me[2], me[3]),
                                        view.cam_x, view.cam_y),
                       "b": P.F_FIRING if firing else 0})
            seq = (seq + 1) & 0xFFFFFFFF
        wire.flush()

        view.draw(screen, world, 0, ())
        pygame.display.flip()

    sock.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Play an arena match")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--host", action="store_true", help="host the match")
    g.add_argument("--join", help="host or host:port to join")
    ap.add_argument("--port", type=int, default=27015)
    ap.add_argument("--map", default="yard", choices=sorted(AR.ARENAS))
    ap.add_argument("--players", type=int, default=4,
                    help="max players in the match, host included (2-8)")
    ap.add_argument("--score", type=int, default=SCORE_LIMIT,
                    help="kills to win")
    args = ap.parse_args(argv)
    args.players = max(2, min(8, args.players))
    args.score = max(1, min(99, args.score))

    pygame.init()
    screen = _open_display()
    try:
        if args.host:
            run_host(args, screen)
        else:
            run_client(args, screen)
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())

