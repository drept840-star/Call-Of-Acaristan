"""2.5D top-down frame bench (diagnostic, not a CI gate).

    python tools/td25_bench.py GROUP [--frames=N] [--backend=gl|software]
                               [--profile=TOP] [--shots=DIR] [--root=TREE]
    python tools/td25_bench.py --ab=BASE_TREE [--b=TREE] [--pairs=3] [GROUP ...]
                               [--backend=gl|software|both] [--frames=N]

GROUP is one of m1 m1esc m2 m3 m4 m5 m6 walk mp (or "all"). Each group sets
its missions up the way tools/m*_td3d_shots.py do, then walks the player
(and so the follow camera) through fixed waypoints for N frames and times
one full gameplay draw per frame (HUD included). The wall clock is pinned
to the frame counter and ``random`` is reseeded each frame, so a run draws
the same pixels every time. Prints one ``TD25`` line per sequence: mean and
p95 frame ms.

``--shots=DIR`` saves frame 0 and the last frame of each sequence. ``--profile=TOP`` adds a
cProfile table (tottime) per sequence. ``--root`` runs another checkout's
src/ and assets (the A/B baseline). ``--ab`` alternates BASE_TREE and this
tree (or ``--b``) in fresh processes (A, B, A, B ...) and prints the per-sequence median
of each side; this PC's frame times swing up to 2x between runs, so only
interleaved medians mean anything.
"""
import os
import random
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROUPS = ("m1", "m1esc", "m2", "m3", "m4", "m5", "m6", "walk", "mp")

opts = {"frames": 60, "backend": "gl", "profile": 0, "shots": None, "root": HERE,
        "ab": None, "b": HERE, "pairs": 3}
groups = []
for a in sys.argv[1:]:
    if a.startswith("--"):
        k, _, val = a[2:].partition("=")
        opts[k] = int(val) if k in ("frames", "profile", "pairs") else val
    else:
        groups.extend(GROUPS if a == "all" else [a])


# ── A/B driver ─────────────────────────────────────────────────────────

def _run(tree, group, backend):
    cmd = [sys.executable, os.path.abspath(__file__), group, "--root=" + tree,
           "--backend=" + backend, "--frames=%d" % opts["frames"]]
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=tree).stdout
    res = {}
    for line in out.splitlines():
        if line.startswith("TD25 "):
            _, seq, be, mean, p95 = line.split()[:5]
            res[(seq, be)] = (float(mean.split("=")[1]), float(p95.split("=")[1]))
    if not res:
        sys.stderr.write("no TD25 lines from %s %s %s\n%s\n" % (tree, group, backend, out[-2000:]))
    return res


def ab():
    base, here = os.path.abspath(opts["ab"]), os.path.abspath(opts["b"])
    backends = ("gl", "software") if opts["backend"] == "both" else (opts["backend"],)
    rows = {}
    for group in groups or GROUPS:
        for be in backends:
            for _ in range(opts["pairs"]):
                for side, tree in (("A", base), ("B", here)):
                    for key, val in _run(tree, group, be).items():
                        rows.setdefault(key, {"A": [], "B": []})[side].append(val)
    print("%-16s %-8s %9s %9s %7s   %9s %9s" % ("sequence", "backend", "A mean", "B mean",
                                               "win", "A p95", "B p95"))
    for (seq, be), d in rows.items():
        if not d["A"] or not d["B"]:
            continue
        am = statistics.median(m for m, _ in d["A"])
        bm = statistics.median(m for m, _ in d["B"])
        ap = statistics.median(p for _, p in d["A"])
        bp = statistics.median(p for _, p in d["B"])
        # pairwise wins: B faster than its own A in how many pairs
        wins = sum(1 for a, b in zip(d["A"], d["B"]) if b[0] < a[0])
        print("%-16s %-8s %9.2f %9.2f %6.1f%%   %9.2f %9.2f   B<A %d/%d  A=%s B=%s"
              % (seq, be, am, bm, 100.0 * (am - bm) / am, ap, bp, wins, len(d["B"]),
                 ",".join("%.1f" % m for m, _ in d["A"]), ",".join("%.1f" % m for m, _ in d["B"])))


if opts["ab"]:
    ab()
    sys.exit(0)


# ── one tree, one process ──────────────────────────────────────────────

ROOT = os.path.abspath(opts["root"])
os.chdir(ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ["ACARISTAN_RENDERER"] = opts["backend"]
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()

from core import config as _cfg  # noqa: E402
from core.state import STATE  # noqa: E402
from engine.core.timebase import pin_wall  # noqa: E402

T = _cfg.TILE_SIZE
CLOCK = [0]
pin_wall(ms=lambda: CLOCK[0] * 1000 // 60, s=lambda: CLOCK[0] / 60.0)


def _path(spots, n):
    """n points walking the player through the tile waypoints."""
    pts = [(x * T + T // 2, y * T + T // 2) for x, y in spots]
    if len(pts) == 1:
        return [pts[0]] * n
    out = []
    for i in range(n):
        k = i * (len(pts) - 1) / float(max(1, n - 1))
        j = min(int(k), len(pts) - 2)
        f = k - j
        out.append((int(pts[j][0] + (pts[j + 1][0] - pts[j][0]) * f),
                    int(pts[j][1] + (pts[j + 1][1] - pts[j][1]) * f)))
    return out


def _mission_frame(mod):
    def draw(pos):
        STATE.player.rect.center = pos
        STATE.camera_x = pos[0] - _cfg.WIDTH // 2
        STATE.camera_y = pos[1] - _cfg.HEIGHT // 2
        mod.game_draw(STATE.camera_x, STATE.camera_y)
    return draw


def _is3d():
    """Did the last frame go through the 3D path (no 2D fallback)?"""
    from game import topdown3d as td
    return td.active_cam() is not None


def bench(seq, draw, path, check=_is3d):
    n = len(path)
    if opts["shots"]:
        os.makedirs(opts["shots"], exist_ok=True)
    CLOCK[0] = 0
    random.seed(1)
    draw(path[0])                        # warm: static bake, mesh caches
    if opts["shots"]:
        CLOCK[0] = 0
        random.seed(1)
        draw(path[0])
        pygame.image.save(_cfg.screen, os.path.join(
            opts["shots"], "%s_%s.png" % (seq, opts["backend"])))
    prof = None
    if opts["profile"]:
        import cProfile
        prof = cProfile.Profile()
    samples = []
    for i, pos in enumerate(path):
        CLOCK[0] = i + 1
        random.seed(i)
        t0 = time.perf_counter()
        if prof:
            prof.enable()
        draw(pos)
        if prof:
            prof.disable()
        samples.append((time.perf_counter() - t0) * 1000.0)
    if opts["shots"] and n > 1:
        pygame.image.save(_cfg.screen, os.path.join(
            opts["shots"], "%s_%s_end.png" % (seq, opts["backend"])))
    if not check():
        print("TD25-FAIL %s %s: frame did not draw in 3D" % (seq, opts["backend"]))
        return
    s = sorted(samples)
    print("TD25 %-14s %-8s mean=%.2f p95=%.2f n=%d" % (
        seq, opts["backend"], statistics.mean(s), s[min(n - 1, int(0.95 * n))], n))
    sys.stdout.flush()
    if prof:
        import io
        import pstats
        buf = io.StringIO()
        st = pstats.Stats(prof, stream=buf)
        st.sort_stats("tottime").print_stats(opts["profile"])
        st.sort_stats("cumulative").print_stats(opts["profile"])
        print("\n".join(l for l in buf.getvalue().splitlines()
                        if l.strip() and not l.startswith(("   Ordered", "   List"))))


N = opts["frames"]


def g_m1():
    from core import game_core as gc
    gc.start_mission(preserve_timer=True)
    from missions import m1
    bench("m1_street", _mission_frame(m1), _path([(9, 6), (23, 5), (8, 16)], N))
    bench("m1_yard", _mission_frame(m1), _path([(12, 23), (15, 28), (24, 31)], N))


def g_m1esc():
    from core import game_core as gc
    gc.start_mission(preserve_timer=True)
    from missions.m1 import escape3d
    ts = [int(i * 1080 / max(1, N - 1)) for i in range(N)]
    bench("m1_escape", lambda t: escape3d.frame(_cfg.screen, t), ts,
          check=lambda: __import__("game.topdown3d", fromlist=["x"]).enabled())


def g_m2():
    from missions import m2
    m2.start_mission2_truck(preserve_timer=True)
    STATE.mission2_card = None
    bench("m2_route", _mission_frame(m2), _path([(8, 72), (20, 62), (30, 38), (46, 33)], N))
    bench("m2_control", _mission_frame(m2), _path([(58, 20), (60, 17), (59, 7)], N))


def g_m3():
    from missions import m3
    for seq, start, spots in (
            ("m3_cell", "start_mission3_breakout_checkpoint", [(33, 9), (20, 14), (20, 21), (22, 27)]),
            ("m3_comms", "start_mission3_comms_checkpoint", [(6, 24), (20, 24), (39, 22)]),
            ("m3_arch", "start_mission3_archives_checkpoint", [(24, 41), (24, 28), (12, 25)]),
            ("m3_ko", "start_mission3_kill_order_checkpoint", [(19, 17), (32, 18), (25, 35)]),
            ("m3_bcast", "start_mission3_broadcast_checkpoint", [(15, 8), (14, 20), (25, 24)])):
        getattr(m3, start)(preserve_timer=True)
        bench(seq, _mission_frame(m3), _path(spots, N))


def g_m4():
    from missions import m4
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import m4_td3d_shots as shots
    for seq, start, spots in (
            ("m4_street", "start_m4", [(4, 4), (12, 19), (20, 18), (31, 19)]),
            ("m4_station", "start_mission4_station_checkpoint", [(17, 23), (18, 7), (27, 17)]),
            ("m4_siege", "start_mission4_tower_checkpoint", [(18, 22), (18, 9), (25, 11)])):
        getattr(m4, start)(preserve_timer=True)
        STATE.active_mission = "MISSION4"
        if seq == "m4_siege":
            shots._stage_siege(m4)
        bench(seq, _mission_frame(m4), _path(spots, N))


def g_m5():
    from missions import m5
    for seq, start, spots in (
            ("m5_hq", "start_mission5_hq_checkpoint", [(6, 9), (16, 11), (24, 5)]),
            ("m5_quarter", "start_mission5_quarter_checkpoint", [(6, 6), (18, 14), (30, 22)]),
            ("m5_print", "start_mission5_printworks_checkpoint", [(5, 15), (13, 10), (20, 5)]),
            ("m5_tunnel", "start_mission5_tunnel_checkpoint", [(4, 6), (25, 6), (42, 6)])):
        getattr(m5, start)(preserve_timer=True)
        STATE.active_mission = "MISSION5"
        bench(seq, _mission_frame(m5), _path(spots, N))


def g_m6():
    from missions import m6
    for seq, start, spots in (
            ("m6_customs", "start_mission6_customs_checkpoint", [(15, 10), (6, 6), (24, 14)]),
            ("m6_noman", "start_mission6_noman_checkpoint", [(20, 8), (8, 7), (30, 12)]),
            ("m6_rail", "start_mission6_rail_checkpoint", [(22, 11), (38, 9), (8, 12)])):
        getattr(m6, start)(preserve_timer=True)
        STATE.active_mission = "MISSION6"
        bench(seq, _mission_frame(m6), _path(spots, N))


def g_walk():
    from missions import walking_sim as ws
    from game import topdown3d as td
    ws.start_walking_sim()
    # rain_drops are rolled at import from an unseeded rng; pin them for repeatable shots
    rr = random.Random(0)
    ws.rain_drops[:] = [(rr.randint(0, _cfg.WIDTH), rr.randint(ws.SCENE_TOP, ws.SCENE_BOT),
                         rr.randint(10, 20)) for _ in range(len(ws.rain_drops))]

    def draw(pos):
        ws.walk_player.rect.center = pos
        ws.walk_camera_x = pos[0] - _cfg.WIDTH // 2
        ws.walk_camera_y = pos[1] - _cfg.HEIGHT // 2
        ws._clamp_walk_camera()
        ws.walk_render_x, ws.walk_render_y = ws.walk_camera_x, ws.walk_camera_y
        ws.walk_active_hover = ws._walk_hover_target()
        ws.draw_walking_sim()
    bench("walk", draw, _path([(3, 2), (17, 3), (27, 5), (38, 6)], N), check=td.enabled)


def g_mp():
    from missions import arena as AR
    from net import protocol as P
    from net.match import MatchSession
    from ui import arena_view3d, mp3d

    class _Sink(object):
        def _send(self, obj):
            return True

    for name in ("yard", "crossfire", "foundry"):
        sess = MatchSession(_Sink(), is_host=True)
        rows = getattr(AR, "ARENA_" + name.upper())
        sim = AR.ArenaSim(sess, rows, score_limit=999, map_name=name)
        for pid in range(4):
            sim.add_player(pid, "P%d" % pid)
        view = arena_view3d.make_view(name)
        seq = [0]

        def draw(i, sim=sim, sess=sess, view=view):
            for pid in range(4):
                a = (i * 0.05 + pid * 1.6)
                sess._accept_input(P.make_input(seq[0], round(_cos(a)), round(_sin(a)), a, 0),
                                   peer_id=pid)
            seq[0] += 1
            sim.step()
            world = {e[0]: e for e in sim.snapshot_entities()}
            view.draw(_cfg.screen, world, 0)
        bench("mp_" + name, draw, list(range(N)), check=mp3d.enabled)


def _cos(a):
    import math
    return math.cos(a)


def _sin(a):
    import math
    return math.sin(a)


_cfg.screen
for g in groups:
    globals()["g_" + g]()
