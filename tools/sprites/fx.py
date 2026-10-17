"""fx.py - Mission 2 tanker-blast aftermath as sprites (Polish T7).

Replaces the per-frame rebuilds in ``missions/m2/draw.py::_draw_tanker_blast_fx``
that never change once the blast has settled:

  scorch            the 520 px oily scorch decal. Procedurally this was a
                    ~1080x1080 SRCALPHA surface drawn, stretched 1.35x and
                    blitted EVERY frame forever after the blast. Authored at
                    half resolution (``scale: 2`` in the JSON) and expanded
                    2x nearest-neighbour once at load - an integer scale.
  wreck_hull        blackened tanker hull + twisted ribs
  wreck_fissure_<a> glowing fissure overlay at 4 alpha levels (pulse)
  wreck_core_<a>    engine-bay core glow at 4 alpha levels (fade / blink)
  spot_<size>_<i>   ground spot fire (scorch patch + layered glow), 4 size
                    buckets x 4 flicker levels

The fireball, mushroom cloud, streaks, cracks and debris stay procedural:
they are driven by per-blast random state on STATE and animate every frame.

Anchors: scorch -> decal centre; wreck_* -> wreck centre (the procedural
blit point + half size); spot_* -> fire centre.

    python tools/sprites/fx.py [--preview] [--out DIR]
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
import palette as P  # noqa: E402
import pygame  # noqa: E402

FAMILY = "fx"
SCORCH_R = 520
WRECK = (64 * 5 - 12 + 80, 64 * 3 - 16 + 80)
FISSURE_ALPHAS = (50, 90, 130, 170)
CORE_ALPHAS = (40, 80, 115, 150)
SPOT_SIZES = (14, 18, 22, 26)
SPOT_FLICKER = (0.65, 0.78, 0.9, 1.0)


def scorch():
    """Half-res scorch: stepped oily rings, radial cracks, fuel splashes."""
    r = SCORCH_R // 2
    w0 = r * 2 + 20
    base = kit.new(w0, w0)
    c = w0 // 2
    for off, a, col in ((0, 220, (8, 6, 5)), (8, 180, (18, 14, 11)), (17, 140, (32, 24, 18)),
                        (28, 100, (55, 40, 32)), (41, 65, (82, 62, 48)), (55, 40, (110, 88, 68))):
        pygame.draw.circle(base, (*col, a), (c, c), max(2, r - off))
    rng = random.Random(52051)
    # irregular rim: bite flat notches out of the outer ring so it is not a disc
    for _ in range(18):
        ang = rng.uniform(0, math.tau)
        rr = r - rng.randint(0, 6)
        pygame.draw.circle(base, (0, 0, 0, 0), (int(c + math.cos(ang) * (rr + 8)), int(c + math.sin(ang) * (rr + 8))),
                           rng.randint(6, 12))
    for _ in range(12):                                  # radial cracks
        ang = rng.uniform(0, math.tau)
        end = rng.randint(10, 40)
        pts = []
        for k in range(6):
            rr = (r - 15) + (end + 15) * k / 5
            j = rng.uniform(-0.03, 0.03)
            pts.append((c + math.cos(ang + j) * rr, c + math.sin(ang + j) * rr))
        pygame.draw.lines(base, (15, 10, 8, 200), False, pts, 2)
        pygame.draw.lines(base, (40, 30, 22, 120), False, pts, 1)
    for _ in range(26):                                  # fuel splash flecks
        ang, rr = rng.uniform(0, math.tau), rng.uniform(0.3, 1.0) * r
        x, y = int(c + math.cos(ang) * rr), int(c + math.sin(ang) * rr)
        pygame.draw.ellipse(base, (6, 5, 4, 150), (x, y, rng.randint(3, 8), rng.randint(2, 4)))
    # fuel splashes wider than tall: same 1.35 stretch the procedural used,
    # applied here at author time (nearest) so runtime only does 2x.
    sw = int(round(w0 * 1.35))
    return pygame.transform.scale(base, (sw, w0))


def wreck_hull():
    w, h = WRECK
    s = kit.new(w, h)
    kit.ellipse_shadow(s, (8, 22, w - 12, h - 24), alpha=(110, 55))   # stays inside the frame
    b = kit.new(w, h)
    C = [(10, 8, 7), (21, 17, 14), (36, 30, 25), (54, 45, 37), (74, 62, 50)]
    pygame.draw.ellipse(b, (12, 9, 8), (0, 12, w, h - 12))
    pygame.draw.ellipse(b, (28, 22, 18), (12, 18, w - 24, h - 30))
    pygame.draw.ellipse(b, (45, 36, 28), (24, 24, w - 48, h - 48))
    pygame.draw.ellipse(b, C[3], (40, 26, w - 120, 10))               # lit crown (upper-left)
    rng = random.Random(77123)
    for i in range(8):                                                 # twisted ribs
        rx = 24 + i * (w - 48) // 7 + rng.randint(-8, 8)
        top = rng.randint(28, 90)
        pts = [(rx, h - 14), (rx + rng.randint(-4, 4), (h - 14 + top) // 2), (rx + rng.randint(-8, 8), top)]
        pygame.draw.lines(b, (55, 46, 38), False, pts, 3)
        pygame.draw.lines(b, (86, 74, 62), False, pts, 1)
    for _ in range(10):                                                # torn plates
        x, y = rng.randint(40, w - 60), rng.randint(40, h - 50)
        pts = [(x, y), (x + rng.randint(10, 24), y + rng.randint(-6, 6)), (x + rng.randint(4, 18), y + rng.randint(6, 14))]
        pygame.draw.polygon(b, C[2], pts)
        pygame.draw.line(b, C[4], pts[0], pts[1])
    s.blit(kit.outline(b, (6, 5, 4)), (0, 0))
    return s


def _fissure_paths():
    w, h = WRECK
    rng = random.Random(77124)
    paths = []
    for _ in range(6):
        pts = [(rng.randint(30, w - 30), rng.randint(40, h - 40))]
        for _s in range(rng.randint(3, 4)):
            pts.append((max(20, min(w - 20, pts[-1][0] + rng.randint(-25, 25))),
                        max(30, min(h - 30, pts[-1][1] + rng.randint(-15, 15)))))
        paths.append(pts)
    return paths


def wreck_fissure(alpha):
    s = kit.new(*WRECK)
    for pts in _fissure_paths():
        pygame.draw.lines(s, (255, 100, 30, alpha), False, pts, 5)
        pygame.draw.lines(s, (255, 200, 100, min(255, alpha + 40)), False, pts, 2)
    return s


def wreck_core(alpha):
    w, h = WRECK
    s = kit.new(w, h)
    for r, col in ((70, (255, 90, 25)), (45, (255, 140, 45)), (25, (255, 200, 90)), (12, (255, 240, 180))):
        pygame.draw.circle(s, (*col, alpha), (w // 2, h - 12), r)
    return s


def spot(size, flicker):
    W, H = size * 3 + 4, size * 2 + 4
    s = kit.new(W, H)
    cx, cy = W // 2, H // 2
    pygame.draw.ellipse(s, (10, 7, 5, 160), (cx - size * 3 // 2, cy - size, size * 3, size * 2))
    for r, col, mul in ((size, P.FIRE[1], 0.45), (int(size * 0.65), P.FIRE[2], 0.65),
                        (int(size * 0.4), P.FIRE[3], 0.85), (int(size * 0.2), P.FIRE[4], 1.0)):
        if r > 0:
            lay = kit.new(W, H)
            pygame.draw.circle(lay, (*col, int(220 * flicker * mul)), (cx, cy), r)
            s.blit(lay, (0, 0))
    return s


def build():
    sc = kit.Sheet("spr_fx_scorch", FAMILY, max_w=2048)
    sc.meta = {"scale": 2, "note": "authored at half resolution; core.artpack expands 2x nearest"}
    surf = scorch()
    sc.add("scorch", surf, (surf.get_width() // 2, surf.get_height() // 2), scale=2,
           radius=SCORCH_R, grow_frames=40)
    sh = kit.Sheet("spr_fx_m2", FAMILY, max_w=1600)
    sh.meta = {"fissure_alphas": list(FISSURE_ALPHAS), "core_alphas": list(CORE_ALPHAS),
               "spot_sizes": list(SPOT_SIZES), "spot_flicker": list(SPOT_FLICKER),
               "timing": "pick the frame nearest the procedural alpha/flicker each frame"}
    w, h = WRECK
    sh.add("wreck_hull", wreck_hull(), (w // 2, h // 2))
    for a in FISSURE_ALPHAS:
        sh.add("wreck_fissure_%d" % a, wreck_fissure(a), (w // 2, h // 2), alpha=a, overlay=True)
    for a in CORE_ALPHAS:
        sh.add("wreck_core_%d" % a, wreck_core(a), (w // 2, h // 2), alpha=a, overlay=True)
    for sz in SPOT_SIZES:
        for i, f in enumerate(SPOT_FLICKER):
            sf = spot(sz, f)
            sh.add("spot_%d_%d" % (sz, i), sf, (sf.get_width() // 2, sf.get_height() // 2),
                   size=sz, flicker=f)
    return [sc, sh]


if __name__ == "__main__":
    sys.exit(kit.run(FAMILY, build))
