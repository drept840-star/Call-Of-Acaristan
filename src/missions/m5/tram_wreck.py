"""M5 Lower Quarter: the burning tram wreck (top-down).

Two halves, both owned here so the look stays in one place:
  * bake(s)        - the static wreck, painted once into the decor layer.
                     Drawn at 2x then smoothscaled down (clean edges, soft
                     gradients, no per-pixel loops).
  * draw_smoke()   - soft smoke puffs, drawn *before* the light multiply so
                     the fire lights them from below.
  * draw_fire()    - additive flame tongues / hot bed / sparks, drawn *after*
                     the light multiply so they stay emissive.

Only imports core.config, so missions.m5.decor / decor_paint can both use it
without an import cycle.
"""

import math
import random
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream

import pygame

from core.config import TILE_SIZE as T
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
from engine.render2d import RectDraw as _RectDraw, SCREEN as _SCREEN, SurfaceDraw as _SurfaceDraw  # RPE6 Phase 6

from engine.text import T as _T  # RPE6 Phase 4 text table

# ── palette ──
C_LIVERY = (102, 34, 30)        # tram red, faded
C_LIVERY_DK = (52, 16, 14)
C_CREAM = (170, 152, 114)
C_ROOF_LO = (58, 60, 64)        # roof eaves
C_ROOF_HI = (118, 120, 124)     # roof ridge
C_CHAR = (12, 9, 8)
C_SOOT = (22, 16, 14)
C_HEAT = (70, 72, 96)           # blued, heat-tempered steel
C_METAL = (104, 106, 112)
C_GLASS = (24, 30, 38)
C_SPRAY = (226, 220, 204)

# world rect of the wreck (matches QUARTER_TRAM_TILES = cols 24-26, row 14)
RECT = pygame.Rect(int(23.55 * T), int(13.95 * T), int(3.9 * T), int(1.05 * T))
# burned-out roof hole, as fractions of the tram rect
_HOLE = (0.40, 0.76, 0.14, 0.86)        # x0, x1, y0, y1
# where the fire is fiercest (fx, fy, weight) - flames cluster, never uniform
_SPOTS = ((0.52, 0.50, 1.0), (0.64, 0.36, 0.75), (0.70, 0.64, 0.6), (0.46, 0.68, 0.45))
_WIND = (30.0, -9.0)                    # px/s: blows east, a little 'up'
_WIND_DEG = math.degrees(math.atan2(-_WIND[1], _WIND[0]))


def _oct(x0, y0, w, h, cl, cr):
    """Car outline: chamfered left/right ends (cl/cr = chamfer size)."""
    return [(x0 + cl, y0), (x0 + w - cr, y0), (x0 + w, y0 + cr * 0.6), (x0 + w, y0 + h - cr * 0.6),
            (x0 + w - cr, y0 + h), (x0 + cl, y0 + h), (x0, y0 + h - cl * 0.6), (x0, y0 + cl * 0.6)]


def _inset(poly, d):
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    out = []
    for x, y in poly:
        dx, dy = x - cx, y - cy
        out.append((x - math.copysign(min(d, abs(dx)), dx), y - math.copysign(min(d, abs(dy)), dy)))
    return out


def _jagged(cx, cy, rx, ry, n, rnd, amp):
    pts = []
    for i in range(n):
        a = i / n * math.tau
        k = 1.0 + rnd.uniform(-amp, amp) * (1.6 if i % 5 == 0 else 1.0)
        pts.append((cx + math.cos(a) * rx * k, cy + math.sin(a) * ry * k))
    return pts


def _blur(surf, f=6):
    w, h = surf.get_size()
    small = pygame.transform.smoothscale(surf, (max(1, w // f), max(1, h // f)))
    return pygame.transform.smoothscale(small, (w, h))


def _clip(layer, mask):
    layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return layer


# ───────────────────────── static bake ─────────────────────────
def _wreck_sprite(w, h):
    """Returns the 1x wreck sprite (w+2m, h+2m) and the margin m."""
    S, m = 2, 24
    W, H, M = w * S, h * S, m * S
    rnd = random.Random(214)
    size = (W + 2 * M, H + 2 * M)
    spr = pygame.Surface(size, pygame.SRCALPHA)
    ox, oy = M, M
    split = int(W * 0.5)
    car_a = _oct(ox, oy, split - 5, H, 46, 8)
    car_b = _oct(ox + split + 5, oy, W - split - 5, H, 8, 38)
    hx0, hx1, hy0, hy1 = (ox + W * _HOLE[0], ox + W * _HOLE[1], oy + H * _HOLE[2], oy + H * _HOLE[3])
    hcx, hcy = (hx0 + hx1) / 2, (hy0 + hy1) / 2
    hrx, hry = (hx1 - hx0) / 2, (hy1 - hy0) / 2

    # soft contact + drop shadow
    sh = pygame.Surface(size, pygame.SRCALPHA)
    for poly in (car_a, car_b):
        pygame.draw.polygon(sh, (0, 0, 0, 190), [(x + 10, y + 14) for x, y in poly])
        pygame.draw.polygon(sh, (0, 0, 0, 120), [(x + 22, y + 26) for x, y in poly])
    spr.blit(_blur(sh, 10), (0, 0))

    mask = pygame.Surface(size, pygame.SRCALPHA)
    for poly in (car_a, car_b):
        pygame.draw.polygon(mask, (255, 255, 255, 255), poly)
    pygame.draw.rect(mask, (255, 255, 255, 255), (ox + split - 8, oy + 12, 16, H - 24))

    # 1) body: dark rim, red livery band, cream pinstripe, curved roof
    for poly in (car_a, car_b):
        pygame.draw.polygon(spr, C_LIVERY, poly)
    pygame.draw.rect(spr, (30, 28, 28), (ox + split - 8, oy + 12, 16, H - 24))   # bellows
    roof_m = pygame.Surface(size, pygame.SRCALPHA)
    for poly in (car_a, car_b):
        pygame.draw.polygon(roof_m, (255, 255, 255, 255), _inset(poly, 10))
    grad = pygame.Surface(size, pygame.SRCALPHA)
    for y in range(oy, oy + H):
        u = (y - oy) / H * 2 - 1
        k = math.cos(u * math.pi / 2) ** 0.8
        k = min(1.0, k * (1.06 if u < 0 else 0.94))                 # light from the north
        col = tuple(int(a + (b - a) * k) for a, b in zip(C_ROOF_LO, C_ROOF_HI))
        pygame.draw.line(grad, col + (255,), (0, y), (size[0], y))
    for poly in (car_a, car_b):
        pygame.draw.polygon(spr, C_CREAM, _inset(poly, 8), 2)
    spr.blit(_clip(grad, roof_m), (0, 0))
    for poly in (car_a, car_b):
        pygame.draw.polygon(spr, C_LIVERY_DK, poly, 3)

    # 2) roof furniture: seams, hatch, folded pantograph on the rear car
    for x in range(ox + 70, ox + W - 60, 38):
        if not (hx0 - 12 < x < hx1 + 12) and abs(x - (ox + split)) > 14:
            pygame.draw.line(spr, (76, 78, 82), (x, oy + 12), (x, oy + H - 12), 2)
            pygame.draw.line(spr, (132, 134, 138), (x + 2, oy + 12), (x + 2, oy + H // 2 - 6), 1)
    px, py = ox + W - 74, oy + H // 2
    pygame.draw.rect(spr, (46, 48, 52), (px - 22, py - 30, 50, 66), border_radius=6)
    pygame.draw.rect(spr, (82, 84, 90), (px - 26, py - 34, 50, 66), border_radius=6)
    pts = [(px - 40, py), (px - 2, py - 22), (px + 36, py), (px - 2, py + 22)]
    pygame.draw.polygon(spr, (26, 26, 30), [(x + 4, y + 5) for x, y in pts], 5)
    pygame.draw.polygon(spr, C_METAL, pts, 4)
    pygame.draw.line(spr, (170, 172, 178), (px - 46, py - 2), (px + 42, py - 2), 4)
    for ix in (px - 18, px + 14):
        pygame.draw.circle(spr, (186, 152, 104), (ix, py + 26), 4)

    # 3) burn: charred core, heat-blued halo, soot blown downwind (clipped)
    burn = pygame.Surface(size, pygame.SRCALPHA)
    for sx, sy, col, a in ((1.95, 1.45, C_HEAT, 70), (1.65, 1.3, (44, 34, 30), 170),
                           (1.35, 1.15, (28, 20, 17), 225), (1.15, 1.05, C_SOOT, 250)):
        pygame.draw.ellipse(burn, col + (a,), (hcx + 8 - hrx * sx, hcy - hry * sy * 1.25,
                                               2 * hrx * sx, 2 * hry * sy * 1.25))
    for _ in range(16):                                            # soot tongues
        x = rnd.uniform(hcx, hx1 + 30)
        y = rnd.uniform(oy + 6, oy + H - 20)
        pygame.draw.ellipse(burn, C_SOOT + (rnd.randint(90, 170),),
                            (x, y, rnd.uniform(50, 120), rnd.uniform(10, 22)))
    burn = _blur(burn, 7)
    for _ in range(140):                                           # blistered paint / ash flakes
        a = rnd.uniform(0, math.tau)
        d = rnd.uniform(1.02, 1.6)
        x, y = hcx + math.cos(a) * hrx * d, hcy + math.sin(a) * hry * d * 1.1
        col = rnd.choice(((14, 10, 9), (34, 26, 22), (86, 80, 74), (96, 58, 34)))
        pygame.draw.circle(burn, col + (rnd.randint(150, 230),), (x, y), rnd.choice((1, 2, 2, 3)))
    spr.blit(_clip(burn, mask), (0, 0))

    # 4) the hole: dark gutted interior (the live flames light it up)
    hole = _jagged(hcx, hcy, hrx, hry, 30, rnd, 0.14)
    hole = [(x, min(oy + H - 9, max(oy + 9, y))) for x, y in hole]
    inner = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.polygon(inner, (255, 255, 255, 255), hole)
    gut = pygame.Surface(size, pygame.SRCALPHA)
    gut.fill(C_CHAR + (255,))
    for y in range(int(hy0), int(hy1), 9):                         # floor planks
        pygame.draw.line(gut, (24, 18, 15, 255), (hx0, y), (hx1, y), 2)
    for x in range(int(hx0) + 14, int(hx1) - 16, 30):              # seat frames both sides
        for y in (oy + 20, oy + H - 42):
            r = pygame.Rect(x + rnd.randint(-3, 3), y + rnd.randint(-2, 2), 20, 22)
            pygame.draw.rect(gut, (50, 38, 32, 255), r, 3, border_radius=3)
    for _ in range(60):                                            # ash + ember grit
        x, y = rnd.uniform(hx0 + 8, hx1 - 8), rnd.uniform(hy0 + 6, hy1 - 6)
        pygame.draw.circle(gut, rnd.choice(((54, 18, 8, 255), (70, 26, 10, 255), (34, 28, 26, 255))),
                           (x, y), rnd.randint(1, 2))
    spr.blit(_clip(gut, inner), (0, 0))
    # peeled, curled roof sheet around the lip
    for i in range(0, len(hole), 3):
        x, y = hole[i]
        dx, dy = x - hcx, y - hcy
        d = math.hypot(dx, dy) or 1
        nx, ny = dx / d, dy / d
        L = rnd.uniform(6, 13)
        tip = (x + nx * L, y + ny * L * 0.6)
        side = (-ny * 6, nx * 6)
        tri = [(x + side[0], y + side[1]), tip, (x - side[0], y - side[1])]
        pygame.draw.polygon(spr, (40, 34, 30), tri)
        pygame.draw.line(spr, (82, 74, 68), (x + side[0], y + side[1]), tip, 1)
    pygame.draw.polygon(spr, (20, 15, 13), hole, 7)
    pygame.draw.lines(spr, (74, 44, 26), True, [(x + 1, y + 2) for x, y in hole], 2)
    for x in (hx0 + hrx * 0.45, hx0 + hrx * 1.05, hx0 + hrx * 1.6):   # surviving roof hoops
        mid = (x + 5, hcy + rnd.uniform(-4, 4))
        pygame.draw.lines(spr, (14, 11, 10), False, [(x + 3, hy0 - 4), (mid[0] + 3, mid[1] + 6),
                                                     (x + 3, hy1 + 6)], 7)
        pygame.draw.lines(spr, (70, 58, 50), False, [(x, hy0 - 6), mid, (x, hy1 + 4)], 2)

    # 5) side windows: glazed at the ends, blown out near the fire
    for side_y in (oy + 3, oy + H - 9):
        for x in range(ox + 54, ox + W - 46, 22):
            if abs(x - (ox + split)) < 14:
                continue
            near = hx0 - 24 < x < hx1 + 24
            pygame.draw.rect(spr, (14, 10, 9) if near else C_GLASS, (x, side_y, 15, 6))
            if not near:
                pygame.draw.line(spr, (96, 116, 134), (x + 2, side_y + 1), (x + 8, side_y + 1))

    # 6) cabs: windscreens + lamps (head white at the front, tail red at the back)
    for (x0, sgn, lamp) in ((ox + 3, 1, (236, 226, 186)), (ox + W - 3, -1, (210, 44, 36))):
        ws = [(x0 + sgn * 12, oy + 22), (x0 + sgn * 32, oy + 12), (x0 + sgn * 32, oy + H - 12),
              (x0 + sgn * 12, oy + H - 22)]
        pygame.draw.polygon(spr, C_GLASS, ws)
        pygame.draw.line(spr, (124, 144, 164), (x0 + sgn * 20, oy + 22), (x0 + sgn * 28, oy + 16), 3)
        for ly in (oy + 20, oy + H - 20):
            pygame.draw.circle(spr, lamp, (x0 + sgn * 7, ly), 4)

    # 7) fleet number + Guard spray tag across the front car roof
    num = pygame.transform.rotate(pygame.font.Font(None, 30).render(_T("tram_wreck.214"), True, (206, 202, 190)), 90)
    spr.blit(num, (ox + 40, oy + H // 2 - num.get_height() // 2))
    tag = pygame.font.Font(None, 40).render(_T("tram_wreck.provocateurs"), True, C_SPRAY)
    room = int(hx0 - 30 - (ox + 76))
    if tag.get_width() > room:
        tag = pygame.transform.smoothscale(tag, (room, int(tag.get_height() * room / tag.get_width())))
    tag = pygame.transform.rotate(tag, 4)
    halo = _blur(tag, 3)
    halo.set_alpha(110)
    tx, ty = ox + 76, oy + H // 2 - tag.get_height() // 2 + 4
    spr.blit(halo, (tx + 1, ty + 1))
    spr.blit(tag, (tx, ty))
    for _ in range(4):                                             # thin drips
        x = tx + rnd.randint(10, tag.get_width() - 10)
        pygame.draw.line(spr, (190, 184, 170), (x, ty + tag.get_height() - 8),
                         (x, ty + tag.get_height() + rnd.randint(1, 6)), 1)

    return pygame.transform.smoothscale(spr, (w + 2 * m, h + 2 * m)), m


def bake(s):
    """Paint the wreck + its ground marks into the static decor layer."""
    tr = RECT
    rnd = random.Random(24)
    # scorched asphalt, smeared downwind (blurred, so no hard rings)
    sc = pygame.Surface((tr.w + 360, tr.h + 220), pygame.SRCALPHA)
    cx, cy = sc.get_width() // 2, sc.get_height() // 2
    pygame.draw.ellipse(sc, (6, 5, 5, 110), (cx - tr.w // 2 - 40, cy - tr.h // 2 - 46, tr.w + 200, tr.h + 92))
    pygame.draw.ellipse(sc, (6, 5, 5, 150), (cx - 40, cy - tr.h // 2 - 22, tr.w // 2 + 110, tr.h + 44))
    for _ in range(18):                                            # soot fingers blown east
        x = rnd.randint(cx, cx + tr.w // 2 + 120)
        y = cy + rnd.randint(-tr.h // 2 - 30, tr.h // 2 + 30)
        pygame.draw.ellipse(sc, (6, 5, 5, rnd.randint(40, 90)), (x, y, rnd.randint(40, 110), rnd.randint(8, 18)))
    s.blit(_blur(sc, 10), (tr.centerx - cx, tr.centery - cy))
    # blown-out glass + debris on the road, thickest beside the burn
    for _ in range(90):
        side = rnd.choice((-1, 1))
        x = int(rnd.triangular(tr.x - 40, tr.right + 50, tr.x + tr.w * 0.6))
        y = (tr.y - rnd.randint(3, 30)) if side < 0 else (tr.bottom + rnd.randint(3, 36))
        col = rnd.choice(((150, 176, 190), (110, 128, 140), (58, 50, 46), (36, 32, 30), (90, 60, 40)))
        pygame.draw.rect(s, col, (x, y, rnd.randint(1, 3), rnd.randint(1, 2)))
    for _ in range(3):                                             # fallen roof sheets
        x = rnd.randint(tr.x + tr.w // 3, tr.right)
        y = tr.bottom + rnd.randint(6, 26)
        pts = [(x, y), (x + rnd.randint(10, 16), y + rnd.randint(-3, 3)), (x + rnd.randint(6, 14), y + rnd.randint(5, 9))]
        pygame.draw.polygon(s, (34, 30, 28), pts)
        pygame.draw.aaline(s, (78, 72, 68), pts[0], pts[1])
    spr, m = None, 24
    try:                                      # baked sprite (src/game/art/m5/tram_wreck.py)
        from art import m5 as _art
        spr = _art.get("tram_wreck", 0)
        if spr is not None and spr.get_size() != (tr.w + 2 * m, tr.h + 2 * m):
            spr = None
    except Exception:
        spr = None
    if spr is None:
        spr, m = _wreck_sprite(tr.w, tr.h)
    s.blit(spr, (tr.x - m, tr.y - m))
    # dropped catenary wire across the junction (thin, slight sag)
    pts = []
    for i in range(21):
        u = i / 20
        x = tr.x - 220 + u * (tr.w + 460)
        y = tr.y - 30 + u * (tr.h + 70) + math.sin(u * math.pi) * 18
        pts.append((x, y))
    pygame.draw.aalines(s, (84, 86, 92), False, pts)


# ───────────────────────── live FX ─────────────────────────
_fire, _smoke, _sparks = [], [], []
_state = {"t": None, "acc": [0.0, 0.0, 0.0]}
_glows, _puffs, _beds = {}, {}, {}
_tongues = []                       # [size_idx][col_idx] -> pre-rotated additive sprite

# flame colour ramp by age. Kept dim on purpose: overlapping ADD blits sum to
# a white-yellow core and fall off to orange/red at the edges.
_RAMP = ((0.0, (150, 128, 84)), (0.22, (170, 100, 36)), (0.5, (140, 50, 12)),
         (0.8, (70, 18, 4)), (1.0, (16, 4, 0)))
_NCOL = 10
_TSIZES = (9, 12, 15, 19, 24)       # tongue lengths (px)


def _ramp(t):
    for (t0, c0), (t1, c1) in zip(_RAMP, _RAMP[1:]):
        if t <= t1:
            k = (t - t0) / (t1 - t0)
            return tuple(int(a + (b - a) * k) for a, b in zip(c0, c1))
    return _RAMP[-1][1]


def _radial(r, col, p=1.8):
    g = pygame.Surface((r * 2, r * 2))
    g.fill((0, 0, 0))
    for i in range(r, 0, -1):
        k = (1 - i / r) ** p
        pygame.draw.circle(g, [int(c * k) for c in col], (r, r), i)
    return g


def _glow(r, col):
    key = (r, col)
    g = _glows.get(key)
    if g is None:
        g = _glows[key] = _radial(r, col)
    return g


def _tongue(L, col, deg):
    """Teardrop flame lick: hot round head, short tail leaning downwind (+x before rotation)."""
    S = 2
    n = int(L * 3.2 * S)
    c = n // 2
    g = pygame.Surface((n, n))
    g.fill((0, 0, 0))
    steps = 12
    for i in range(steps):
        u = i / (steps - 1)
        r = max(2, int(L * 0.6 * S * (1 - u) ** 0.7))
        k = (1 - u) ** 1.3 * 0.42
        x = c + u * L * 1.0 * S
        y = c - math.sin(u * math.pi) * L * 0.12 * S
        g.blit(_radial(r, [int(v * k) for v in col], 1.4), (int(x - r), int(y - r)),
               special_flags=pygame.BLEND_RGB_ADD)
    g = pygame.transform.smoothscale(g, (n // S, n // S))
    return pygame.transform.rotate(g, deg)


_ANGLES = (-26, -8, 10, 30, 52)     # offsets from the wind heading -> organic, not striped


def _build_tongues():
    for L in _TSIZES:
        _tongues.append([[_tongue(L, _ramp(i / (_NCOL - 1)), _WIND_DEG + a) for a in _ANGLES]
                         for i in range(_NCOL)])


def _puff(r):
    p = _puffs.get(r)
    if p is None:
        p = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        for i in range(r, 0, -1):
            k = (1 - i / r) ** 1.2
            v = int(52 + 30 * k)
            pygame.draw.circle(p, (v, v - 3, v - 6, int(170 * k)), (r, r), i)
        _puffs[r] = p
    return p


def _spot_point(spread=1.0):
    x0, x1, y0, y1 = _HOLE
    tot = sum(sp[2] for sp in _SPOTS)
    pick = _rng_legacy.random() * tot
    for fx, fy, wgt in _SPOTS:
        pick -= wgt
        if pick <= 0:
            break
    fx = min(x1 - 0.03, max(x0 + 0.03, _rng_legacy.gauss(fx, 0.045 * spread)))
    fy = min(y1 - 0.06, max(y0 + 0.06, _rng_legacy.gauss(fy, 0.13 * spread)))
    return RECT.x + RECT.w * fx, RECT.y + RECT.h * fy


def _step(dt):
    acc = _state["acc"]
    acc[0] += dt * 95                                           # flame licks / s
    while acc[0] >= 1 and len(_fire) < 120:
        acc[0] -= 1
        x, y = _spot_point()
        life = _rng_legacy.uniform(0.45, 0.95)
        _fire.append([x, y, _WIND[0] * _rng_legacy.uniform(0.15, 0.5), _rng_legacy.uniform(-8, 4),
                      0.0, life, _rng_legacy.uniform(0.0, 1.0), _rng_legacy.randrange(len(_ANGLES))])
    acc[1] += dt * 11                                           # smoke / s
    while acc[1] >= 1 and len(_smoke) < 80:
        acc[1] -= 1
        x, y = _spot_point(1.4)
        _smoke.append([x + 6, y - 4, _WIND[0] * 1.2 + _rng_legacy.uniform(-6, 10),
                       _WIND[1] * 1.4 + _rng_legacy.uniform(-12, 2), 0.0, _rng_legacy.uniform(3.5, 5.5),
                       _rng_legacy.uniform(9, 14)])
    acc[2] += dt * 12                                           # sparks / s
    while acc[2] >= 1 and len(_sparks) < 50:
        acc[2] -= 1
        x, y = _spot_point(0.7)
        _sparks.append([x, y, _WIND[0] + _rng_legacy.uniform(0, 40), _WIND[1] + _rng_legacy.uniform(-40, 20),
                        0.0, _rng_legacy.uniform(0.6, 1.6), _rng_legacy.uniform(0, 6.28)])
    for p in _fire:
        p[4] += dt
        p[0] += p[2] * dt
        p[1] += p[3] * dt
    for p in _smoke:
        p[4] += dt
        p[0] += p[2] * dt
        p[1] += p[3] * dt
        p[6] += dt * 10                                         # spreads as it drifts
    for p in _sparks:
        p[4] += dt
        p[0] += (p[2] + math.sin(p[4] * 9 + p[6]) * 26) * dt
        p[1] += (p[3] + math.cos(p[4] * 7 + p[6]) * 18) * dt
    _fire[:] = [p for p in _fire if p[4] < p[5]]
    _smoke[:] = [p for p in _smoke if p[4] < p[5]]
    _sparks[:] = [p for p in _sparks if p[4] < p[5]]


def update():
    now = _now_ms()
    last = _state["t"]
    if last is None:                                            # pre-warm: already burning on arrival
        for _ in range(240):
            _step(1 / 60)
        _state["t"] = now
        return
    _state["t"] = now
    _step(min(0.05, max(0.0, (now - last) / 1000.0)))


def reset():
    _fire.clear()
    _smoke.clear()
    _sparks.clear()
    _state["t"] = None


def _visible(size, cam_x, cam_y, pad=300):
    x, y = RECT.centerx - cam_x, RECT.centery - cam_y
    return -pad < x < size[0] + pad and -pad < y < size[1] + pad


def draw_smoke(s, cam_x, cam_y):
    for d in smoke_drawables(cam_x, cam_y, s.get_size()):
        d.draw(s, 0, 0)


def smoke_drawables(cam_x, cam_y, size):
    """RPE6 Phase 6: the smoke puffs as screen-space ``SurfaceDraw``s (alpha per puff)."""
    if not _visible(size, cam_x, cam_y, 500):
        return
    for x, y, _vx, _vy, age, life, r in _smoke:
        t = age / life
        a = int(255 * min(1.0, age / 0.5) * (1 - t) ** 1.3 * 0.8)
        if a <= 4:
            continue
        rr = max(4, int(r) // 3 * 3)
        yield _SurfaceDraw(_puff(rr), (int(x - rr - cam_x), int(y - rr - cam_y)), alpha=a, space=_SCREEN)


def _bed(r, lvl):
    """Hot bed under a fire spot, cached by flicker level."""
    key = (r, lvl)
    g = _beds.get(key)
    if g is None:
        k = 0.55 + lvl * 0.09
        g = _beds[key] = _radial(r, (int(170 * k), int(78 * k), int(22 * k)), 1.5)
    return g


def draw_fire(s, cam_x, cam_y):
    for d in fire_drawables(cam_x, cam_y, s.get_size()):
        d.draw(s, 0, 0)


def fire_drawables(cam_x, cam_y, size):
    """RPE6 Phase 6: heat bloom, hot beds, flame licks and sparks as additive screen-space draws."""
    if not _visible(size, cam_x, cam_y):
        return
    if not _tongues:
        _build_tongues()
    tms = _now_ms() / 1000.0
    add = pygame.BLEND_RGB_ADD
    # heat bloom over the hole (warm rim on the shell, not a wash over the whole tram)
    hx = RECT.x + RECT.w * (_HOLE[0] + _HOLE[1]) / 2 - cam_x
    hy = RECT.y + RECT.h * (_HOLE[2] + _HOLE[3]) / 2 - cam_y
    bloom = _glows.get("bloom")
    if bloom is None:
        bw = int(RECT.w * (_HOLE[1] - _HOLE[0]) * 1.9)
        bloom = _glows["bloom"] = pygame.transform.smoothscale(_radial(64, (70, 30, 10), 1.6),
                                                              (bw, int(RECT.h * 2.0)))
    yield _SurfaceDraw(bloom, (int(hx - bloom.get_width() / 2 + 6), int(hy - bloom.get_height() / 2)),
                       flags=add, space=_SCREEN)
    # glowing beds under each hot spot
    for i, (fx, fy, wgt) in enumerate(_SPOTS):
        f = 0.75 + 0.15 * math.sin(tms * (9 + i * 2.3) + i) + 0.1 * math.sin(tms * 21 + i * 4)
        lvl = max(0, min(5, int(f * 5)))
        r = int(10 + 12 * wgt)
        g = _bed(r, lvl)
        yield _SurfaceDraw(g, (int(RECT.x + RECT.w * fx - cam_x - r), int(RECT.y + RECT.h * fy - cam_y - r)),
                           flags=add, space=_SCREEN)
    # flame licks: teardrops leaning downwind, grow then shrink
    nsz = len(_TSIZES)
    for x, y, _vx, _vy, age, life, rs, ai in _fire:
        t = age / life
        env = math.sin(min(1.0, t * 1.15) * math.pi) ** 0.6
        si = min(nsz - 1, int((0.35 + 0.65 * rs) * env * nsz))
        ci = min(_NCOL - 1, int(t * _NCOL))
        g = _tongues[si][ci][ai]
        yield _SurfaceDraw(g, (int(x - cam_x - g.get_width() / 2), int(y - cam_y - g.get_height() / 2)),
                           flags=add, space=_SCREEN)
    # sparks: tiny hot points with a faint halo
    for x, y, _vx, _vy, age, life, _ph in _sparks:
        t = age / life
        if t > 0.9:
            continue
        q = int(t * 8) / 8                                     # quantised -> cached halos
        c = tuple(min(255, int(v * 1.6)) for v in _ramp(0.1 + q * 0.6))
        sx, sy = int(x - cam_x), int(y - cam_y)
        yield _SurfaceDraw(_glow(4, (c[0] // 3, c[1] // 3, c[2] // 3)), (sx - 4, sy - 4), flags=add, space=_SCREEN)
        yield _RectDraw((sx, sy, 1, 1), c, space=_SCREEN)
