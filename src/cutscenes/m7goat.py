"""Mission 7 bridge: the wire was never mended, and Bodi's goat gets out.

Plays automatically when the last chore lands, before the player talks to
Bodi, so the rescue starts from something the player has seen rather than
from a line of dialogue.  Scene renderers take ``(surface, t_ms)`` on the
full-size surface; the host supplies the letterbox and keeps important
action inside y=80..620.  Registered lazily from ``missions/m7/meta.py``.

Shot list (timeline ``m7.goat_escape``):

    pen       the last bucket; the cream goat works the loose wire
    slip      close: the post gives, the wire snaps, she is through
    orchard   she is already at the trees; Bodi sees the empty gap
    potatoes  Biribel asks the obvious question
    bodi      Bodi answers it, wire coil already in hand

All animation is derived from t_ms, so seeking and replaying are
deterministic.  The wide plate is painted once and cached.
"""

import math

import pygame

from core.config import HEIGHT, WIDTH
from engine.anim import draw_character

INK = (30, 26, 24)
GROUND = 566

SKY_TOP = (104, 146, 170)
SKY_BOTTOM = (243, 209, 158)

GRASS = (110, 124, 77)
GRASS_D = (86, 102, 62)
YARD = (156, 129, 94)
YARD_L = (176, 149, 110)

FENCE_D = (70, 57, 41)
FENCE = (134, 110, 74)
FENCE_L = (175, 148, 101)
WIRE = (154, 150, 132)

WOOD_D = (86, 58, 38)
WOOD = (128, 86, 52)
WOOD_L = (166, 118, 72)
METAL = (112, 114, 116)
METAL_D = (74, 76, 78)

GOAT_CREAM = (226, 220, 206)
GOAT_GREY = (150, 146, 140)
GOAT_BROWN = (142, 98, 66)
HOOF = (58, 52, 46)
HORN = (170, 152, 116)
HORN_D = (126, 110, 82)
BUCKLE = (188, 170, 120)

_PLATES = {}
_SOFT = {}


# ---------------------------------------------------------------------------
# Small drawing and timing helpers
# ---------------------------------------------------------------------------

def _clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, value))


def _lerp(a, b, u):
    return a + (b - a) * u


def _mix(a, b, u):
    return tuple(int(_lerp(x, y, u)) for x, y in zip(a, b))


def _ease_out(u):
    u = _clamp(u)
    return 1.0 - (1.0 - u) ** 2.2


def _k(t, start, length):
    u = _clamp((t - start) / float(max(1, length)))
    return u * u * (3.0 - 2.0 * u)


def _rng(seed):
    s = seed & 0x7FFFFFFF
    while True:
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        yield s >> 8


def _pt(p):
    return int(round(p[0])), int(round(p[1]))


def _line(surface, col, a, b, width=1):
    pygame.draw.line(
        surface, col, _pt(a), _pt(b), max(1, int(round(width)))
    )


def _poly(surface, col, pts, width=0):
    pygame.draw.polygon(
        surface, col, [_pt(p) for p in pts], max(0, int(round(width)))
    )


def _ellipse(surface, col, rect, width=0):
    r = pygame.Rect(*(int(round(v)) for v in rect))
    if r.w > 0 and r.h > 0:
        pygame.draw.ellipse(surface, col, r, max(0, int(round(width))))


def _dark(c, t=0.3):
    return _mix(c, (6, 8, 10), t)


def _lite(c, t=0.24):
    return _mix(c, (255, 245, 224), t)


def _shadow(surface, x, y, width, height=13, alpha=65):
    width, height = max(2, int(width)), max(2, int(height))
    shade = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.ellipse(shade, (20, 23, 19, alpha), shade.get_rect())
    surface.blit(shade, (int(x - width / 2), int(y - height / 2)))


def _vignette(surface, strength=34):
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(12):
        inset = i * 12
        rect = pygame.Rect(
            inset, 80 + i * 4, WIDTH - inset * 2, 540 - i * 8
        )
        if rect.w > 0 and rect.h > 0:
            pygame.draw.rect(
                layer,
                (12, 19, 19, int(strength * (1.0 - i / 12.0))),
                rect,
                max(1, 12 - i),
            )
    surface.blit(layer, (0, 0))


# ---------------------------------------------------------------------------
# Landscape
# ---------------------------------------------------------------------------

def _ridge(surface, base, amp, col, phase):
    points = [(0, HEIGHT)]
    for x in range(0, WIDTH + 26, 26):
        y = base - amp * (
            0.5
            + 0.32 * math.sin(x * 0.0042 + phase)
            + 0.18 * math.sin(x * 0.011 + phase * 2.3)
        )
        points.append((x, int(y)))
    points.append((WIDTH, HEIGHT))
    _poly(surface, col, points)


def _tree(surface, x, y, scale, seed=1, distant=False):
    rnd = _rng(seed)
    trunk = (66, 66, 49) if distant else (63, 53, 39)
    leaf = (75, 95, 65) if distant else (53, 77, 48)
    _line(surface, trunk, (x, y), (x - 3 * scale, y - 86 * scale),
          max(2, 9 * scale))
    for i in range(9):
        dx = (next(rnd) % 61 - 30) * scale
        dy = (next(rnd) % 58) * scale
        radius = (17 + next(rnd) % 15) * scale
        col = _mix(leaf, (118, 128, 73), (i % 4) * 0.09)
        pygame.draw.circle(
            surface,
            col,
            _pt((x + dx, y - 70 * scale - dy)),
            max(1, int(radius)),
        )


def _house(surface, x, base):
    """A stone farmhouse with its roof against the low sun."""
    w, h = 190, 104
    pygame.draw.rect(surface, (198, 180, 148), (x, base - h, w, h))
    pygame.draw.rect(surface, (178, 160, 128), (x, base - h, w, 10))
    _poly(
        surface,
        (146, 76, 58),
        [(x - 12, base - h), (x + w + 12, base - h),
         (x + w - 14, base - h - 56), (x + 10, base - h - 56)],
    )
    _poly(
        surface,
        (110, 60, 48),
        [(x + 10, base - h - 56), (x + w - 14, base - h - 56),
         (x + w - 26, base - h - 48), (x + 20, base - h - 48)],
    )
    pygame.draw.rect(surface, (96, 70, 54), (x + 132, base - h - 78, 22, 44))
    pygame.draw.rect(surface, (70, 52, 42), (x + 134, base - h - 82, 26, 8))

    for wx in (x + 22, x + 96):
        pygame.draw.rect(surface, (66, 56, 44), (wx - 3, base - h + 22 - 3, 38, 40))
        pygame.draw.rect(surface, (246, 196, 112), (wx, base - h + 22, 32, 34))
        pygame.draw.line(
            surface, (120, 92, 62), (wx + 16, base - h + 22),
            (wx + 16, base - h + 56), 2,
        )
        pygame.draw.line(
            surface, (120, 92, 62), (wx, base - h + 39),
            (wx + 32, base - h + 39), 2,
        )
    pygame.draw.rect(surface, (78, 60, 44), (x + 70, base - 46, 32, 46))
    pygame.draw.rect(surface, (102, 78, 56), (x + 72, base - 44, 28, 42))
    pygame.draw.circle(surface, BUCKLE, (x + 92, base - 24), 2)
    _line(surface, (120, 102, 80), (x + 6, base - 8), (x + w - 6, base - 8), 3)


def _barn(surface, x, base, w=280, h=150):
    pygame.draw.rect(surface, (140, 84, 61), (x, base - h, w, h))
    for i in range(0, w, 22):
        _line(surface, (120, 70, 52), (x + i, base - h), (x + i, base), 1)
    _poly(
        surface,
        (94, 58, 44),
        [(x - 16, base - h), (x + w + 16, base - h),
         (x + w - 30, base - h - 52), (x + 30, base - h - 52)],
    )
    pygame.draw.rect(surface, (74, 54, 40), (x + 46, base - 104, 84, 104))
    pygame.draw.rect(surface, (58, 42, 32), (x + 52, base - 98, 72, 98))
    for a, b in (
        ((x + 52, base - 98), (x + 124, base)),
        ((x + 124, base - 98), (x + 52, base)),
    ):
        _line(surface, (150, 130, 96), a, b, 5)
    pygame.draw.rect(surface, (54, 40, 30), (x + 174, base - 118, 62, 46))
    pygame.draw.rect(surface, (92, 70, 48), (x + 180, base - 112, 50, 34))
    _line(surface, (170, 148, 104), (x + 180, base - 86), (x + 230, base - 86), 2)


def _well(surface, x, base):
    pygame.draw.ellipse(surface, (94, 88, 74), (x - 34, base - 13, 68, 26))
    pygame.draw.ellipse(surface, (134, 126, 106), (x - 31, base - 16, 62, 24))
    pygame.draw.ellipse(surface, (52, 62, 61), (x - 23, base - 12, 46, 15))
    pygame.draw.ellipse(surface, (112, 130, 128), (x - 19, base - 10, 38, 10))
    for px in (x - 27, x + 22):
        _line(surface, (76, 62, 44), (px, base - 12), (px, base - 74), 5)
    _poly(
        surface,
        (112, 68, 50),
        [(x - 42, base - 70), (x + 42, base - 70),
         (x + 19, base - 92), (x - 19, base - 92)],
    )
    _line(surface, (66, 54, 40), (x - 32, base - 68), (x + 32, base - 68), 4)
    _line(surface, (144, 128, 92), (x, base - 68), (x, base - 34), 2)
    _line(surface, (144, 128, 92), (x - 5, base - 40), (x + 5, base - 40), 6)
    pygame.draw.rect(surface, (86, 66, 44), (x - 8, base - 40, 16, 14))


def _trough(surface, x, base):
    w, h = 148, 34
    pygame.draw.rect(surface, WOOD_D, (x, base - h, w, h))
    pygame.draw.rect(surface, WOOD, (x + 3, base - h + 3, w - 6, h - 8))
    pygame.draw.rect(surface, (78, 84, 72), (x + 8, base - h + 5, w - 16, 9))
    pygame.draw.rect(surface, (98, 108, 88), (x + 10, base - h + 6, w - 20, 6))
    for i in range(3):
        _line(surface, (70, 58, 42), (x + 2, base - h + 8 + i * 9),
              (x + w - 2, base - h + 8 + i * 9), 1)
    for px in (x + 10, x + w - 10):
        pygame.draw.rect(surface, (60, 48, 36), (px - 4, base - 6, 8, 8))


def _hay(surface, x, base, seed=7):
    rnd = _rng(seed)
    for i in range(3):
        w, h = 44 - i * 4, 26 - i * 3
        pygame.draw.ellipse(
            surface, (176, 148, 88), (x + i * 8, base - h - i * 5, w, h)
        )
        pygame.draw.ellipse(
            surface, (142, 116, 68), (x + i * 8, base - h - i * 5, w, h), 2
        )
        for _ in range(9):
            sx = x + i * 8 + next(rnd) % max(1, w)
            sy = base - h - i * 5 + next(rnd) % max(1, h)
            _line(surface, (204, 176, 108), (sx, sy), (sx + 5, sy - 3), 1)


def _yard_plate():
    key = (WIDTH, HEIGHT, GROUND)
    if key in _PLATES:
        return _PLATES[key]

    plate = pygame.Surface((WIDTH, HEIGHT))
    horizon = GROUND - 150

    for y in range(0, horizon + 40, 4):
        u = _clamp(y / float(horizon + 40))
        plate.fill(_mix(SKY_TOP, SKY_BOTTOM, u), (0, y, WIDTH, 4))

    sun_x, sun_y = int(WIDTH * 0.76), int(horizon - 96)
    glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for radius, alpha in ((128, 8), (98, 10), (74, 14), (51, 22)):
        pygame.draw.circle(glow, (255, 223, 165, alpha), (sun_x, sun_y), radius)
    plate.blit(glow, (0, 0))
    pygame.draw.circle(plate, (255, 237, 191), (sun_x, sun_y), 28)

    clouds = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for x, y, w in (
        (WIDTH * 0.10, 148, 190),
        (WIDTH * 0.42, 118, 150),
        (WIDTH * 0.78, 186, 210),
    ):
        for i in range(5):
            pygame.draw.ellipse(
                clouds,
                (250, 230, 194, 24),
                (int(x + i * 22), int(y + math.sin(i) * 4), int(w * 0.48), 13),
            )
    plate.blit(clouds, (0, 0))

    _ridge(plate, horizon - 20, 62, (151, 167, 163), 0.6)
    _ridge(plate, horizon + 12, 46, (113, 139, 119), 2.1)
    for i, x in enumerate(range(14, WIDTH, 84)):
        yy = horizon - 6 + math.sin(i * 0.8) * 7
        _tree(plate, x, yy, 0.28 + (i % 3) * 0.03, 31 + i, True)

    _house(plate, 34, 438)
    _barn(plate, 706, 438, 300, 152)

    _poly(
        plate,
        GRASS,
        [(0, horizon + 6), (WIDTH, horizon - 4),
         (WIDTH, HEIGHT), (0, HEIGHT)],
    )
    _poly(
        plate,
        GRASS_D,
        [(0, horizon + 52), (WIDTH * 0.34, horizon + 34),
         (WIDTH * 0.68, horizon + 58), (WIDTH, horizon + 28),
         (WIDTH, horizon + 40), (0, horizon + 70)],
    )
    _poly(
        plate,
        YARD,
        [(150, horizon + 22), (WIDTH * 0.44, horizon + 8),
         (WIDTH * 0.62, horizon + 30), (WIDTH, horizon + 16),
         (WIDTH, HEIGHT - 30), (0, HEIGHT - 18), (40, horizon + 68)],
    )
    _poly(
        plate,
        YARD_L,
        [(300, horizon + 34), (WIDTH * 0.55, horizon + 24),
         (WIDTH * 0.66, horizon + 44), (WIDTH, horizon + 34),
         (WIDTH, horizon + 52), (180, horizon + 66)],
    )

    _well(plate, 244, 508)
    _trough(plate, 340, 558)
    _hay(plate, 866, 474, 9)

    # A lane runs from the barn toward the track; wheel ruts keep it read.
    _poly(
        plate,
        (146, 120, 88),
        [(600, 700), (740, 700), (860, 470), (790, 470)],
    )
    for offset in (0, 26):
        _line(
            plate,
            (116, 94, 70),
            (636 + offset, 700),
            (824 + offset, 480),
            2,
        )

    # The pen: two runs with a gap (the escape post is drawn per shot so it
    # can lean and give).  Goats are painted over these rails.
    for x0, x1 in ((590, 690), (790, 1000)):
        for rail_y in (470, 506):
            _line(plate, (65, 56, 42), (x0, rail_y + 4), (x1, rail_y + 4), 7)
            _line(plate, FENCE, (x0, rail_y), (x1, rail_y), 5)
        _line(plate, FENCE_L, (x0, rail_y - 2), (x1, rail_y - 2), 1)
    for x in (590, 690, 790, 880, 970):
        _poly(
            plate,
            (77, 62, 43),
            [(x - 4, 552), (x - 2, 432), (x + 4, 426),
             (x + 9, 433), (x + 7, 552)],
        )
        _line(plate, FENCE_L, (x + 1, 438), (x + 2, 546), 2)
        for yy in (473, 509):
            pygame.draw.circle(plate, (49, 46, 38), (x + 3, yy), 1)

    rnd = _rng(77)
    for _ in range(260):
        x = next(rnd) % WIDTH
        y = horizon + 12 + next(rnd) % max(1, HEIGHT - horizon - 12)
        color = (190, 162, 118) if next(rnd) % 2 else (134, 110, 80)
        plate.fill(color, (x, y, 2 + next(rnd) % 5, 1 + next(rnd) % 2))
    for _ in range(120):
        x = next(rnd) % WIDTH
        y = horizon + 4 + next(rnd) % 48
        h = 3 + next(rnd) % 9
        _line(plate, (72, 94, 53), (x, y), (x + 2, y - h), 1)

    if len(_PLATES) >= 4:
        _PLATES.clear()
    _PLATES[key] = plate
    return plate


def _soft_plate():
    key = (WIDTH, HEIGHT)
    if key in _SOFT:
        return _SOFT[key]
    small = pygame.transform.smoothscale(
        _yard_plate(), (WIDTH // 2, HEIGHT // 2)
    )
    soft = pygame.transform.smoothscale(small, (WIDTH, HEIGHT))
    haze = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    haze.fill((38, 34, 26, 30))
    soft.blit(haze, (0, 0))
    _SOFT[key] = soft
    return soft


def _zoom_plate(cx, cy, zoom):
    """A locked-off piece of the yard plate, enlarged for a close shot."""
    key = ("zoom", int(cx), int(cy), round(zoom, 2))
    if key in _SOFT:
        return _SOFT[key]
    plate = _yard_plate()
    w = int(WIDTH / zoom)
    h = int(HEIGHT / zoom)
    x0 = max(0, min(WIDTH - w, int(cx - w / 2.0)))
    y0 = max(0, min(HEIGHT - h, int(cy - h / 2.0)))
    crop = plate.subsurface((x0, y0, w, h)).copy()
    out = pygame.transform.smoothscale(crop, (WIDTH, HEIGHT))
    haze = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    haze.fill((30, 27, 22, 34))
    out.blit(haze, (0, 0))
    if len(_SOFT) >= 6:
        _SOFT.clear()
    _SOFT[key] = out
    return out


def _motes(surface, t, n=12):
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(n):
        x = (i * 149 + t * (0.006 + i * 0.0003)) % (WIDTH + 40) - 20
        y = 300 - (i * 47 % 210) + math.sin(t * 0.0007 + i) * 9
        pygame.draw.circle(layer, (255, 230, 173, 54), _pt((x, y)), 1)
    surface.blit(layer, (0, 0))


def _hen(surface, x, y, t, seed=0):
    peck = (int(t / 260.0) + seed) % 4 == 0
    _shadow(surface, x, y + 1, 20, 6, 55)
    pygame.draw.ellipse(surface, (126, 88, 58), (x - 10, y - 13, 20, 13))
    pygame.draw.polygon(
        surface,
        (96, 66, 44),
        [(x - 8, y - 11), (x - 18, y - 17), (x - 10, y - 5)],
    )
    if peck:
        pygame.draw.circle(surface, (168, 122, 76), (x + 10, y - 3), 4)
        pygame.draw.polygon(
            surface, (196, 146, 58),
            [(x + 13, y - 4), (x + 18, y - 3), (x + 13, y - 1)],
        )
    else:
        pygame.draw.circle(surface, (168, 122, 76), (x + 8, y - 14), 4)
        pygame.draw.polygon(
            surface, (196, 146, 58),
            [(x + 11, y - 15), (x + 16, y - 14), (x + 11, y - 12)],
        )
        pygame.draw.circle(surface, INK, (x + 9, y - 15), 1)


# ---------------------------------------------------------------------------
# Props
# ---------------------------------------------------------------------------

def _post(surface, x, base, height, lean=0.0, width=13):
    ang = math.radians(lean)
    ca, sa = math.cos(ang), math.sin(ang)

    def P(dx, dy):
        return x + dx * ca - dy * sa, base + dx * sa + dy * ca

    pts = [
        P(-width / 2, 0), P(-width / 2 + 1, -height + 10),
        P(-width / 2 + 4, -height), P(width / 2 - 2, -height + 4),
        P(width / 2, 0),
    ]
    _poly(surface, (77, 62, 43), pts)
    _line(surface, FENCE_L, P(-width / 2 + 4, -8), P(-width / 2 + 4, -height + 12), 2)
    for yy in (-42, -76):
        pygame.draw.circle(surface, (49, 46, 38), _pt(P(0, yy)), 2)
    return P


def _wire(surface, x0, y0, x1, y1, sag=0.0, width=2, col=WIRE):
    midx = (x0 + x1) / 2.0
    midy = (y0 + y1) / 2.0 + sag
    pts = []
    for i in range(9):
        u = i / 8.0
        bx = (1 - u) ** 2 * x0 + 2 * (1 - u) * u * midx + u * u * x1
        by = (1 - u) ** 2 * y0 + 2 * (1 - u) * u * midy + u * u * y1
        pts.append((bx, by))
    pygame.draw.lines(surface, col, False, [_pt(p) for p in pts], max(1, width))


def _bucket(surface, x, y, scale=1.0, water=False, grain=False):
    """A bucket whose rim centre is (x, y)."""
    w = 30 * scale
    h = 32 * scale
    top = [(x - w / 2, y), (x + w / 2, y)]
    body = [
        (x - w / 2, y),
        (x + w / 2, y),
        (x + w * 0.36, y + h),
        (x - w * 0.36, y + h),
    ]
    _poly(surface, (126, 132, 134), body)
    _poly(surface, (96, 100, 102), [(x + w * 0.16, y), (x + w / 2, y),
                                    (x + w * 0.36, y + h), (x + w * 0.06, y + h)])
    pygame.draw.ellipse(
        surface, (168, 172, 170), (x - w / 2, y - 4 * scale, w, 8 * scale)
    )
    pygame.draw.ellipse(
        surface, (62, 66, 66), (x - w * 0.40, y - 1 * scale, w * 0.80, 5 * scale)
    )
    if water:
        pygame.draw.ellipse(
            surface, (112, 142, 146),
            (x - w * 0.34, y, w * 0.68, 4 * scale),
        )
    if grain:
        pygame.draw.ellipse(
            surface, (192, 164, 96),
            (x - w * 0.34, y - 1 * scale, w * 0.68, 5 * scale),
        )
    for yy in (0.30, 0.72):
        _line(
            surface, (72, 78, 78),
            (x - w * 0.45, y + h * yy), (x + w * 0.45, y + h * yy),
            max(1, int(2 * scale)),
        )
    pygame.draw.arc(
        surface, (54, 58, 60),
        pygame.Rect(int(x - w * 0.56), int(y - h * 0.42), int(w * 0.72), int(h * 0.54)),
        math.radians(18), math.radians(162), max(1, int(2 * scale)),
    )


def _coil(surface, x, y, scale=1.0):
    for i in range(3):
        r = (16 - i * 4) * scale
        pygame.draw.ellipse(
            surface, (148, 146, 130),
            (x - r, y - r * 0.66, r * 2, r * 1.32),
            max(1, int(2 * scale)),
        )
    _line(surface, (116, 114, 100), (x - 15 * scale, y + 6 * scale),
          (x - 8 * scale, y + 13 * scale), max(1, int(2 * scale)))


def _grain_stream(surface, x, y, height, t):
    for i in range(10):
        u = ((t * 0.0016 + i / 10.0) % 1.0)
        px = x + math.sin(i * 2.1) * 4
        _line(
            surface, (208, 178, 104),
            (px, y + height * u), (px + 1, y + height * u + 5),
            2,
        )


# ---------------------------------------------------------------------------
# Goat
# ---------------------------------------------------------------------------

def _goat(
    surface, x, feet, scale, right, t,
    coat=GOAT_CREAM, pose="idle", phase=0.0, squeeze=0.0,
):
    """A side-view goat, roughly 1.7 m at the horn tips.

    ``pose`` is one of idle / graze / walk / push.  ``phase`` offsets the walk
    cycle so a group of goats never moves in lockstep.
    """
    s = 1.0 if right else -1.0
    k = 100.0 * scale

    def P(gx, gy):
        return x + s * gx * k, feet - gy * k

    def poly(col, pts, width=0):
        pygame.draw.polygon(
            surface, col, [_pt(P(*p)) for p in pts], max(0, int(round(width)))
        )

    def ink(pts, width=2.0):
        pygame.draw.polygon(
            surface, INK, [_pt(P(*p)) for p in pts],
            max(1, int(round(width * scale))),
        )

    def limb(col, a, b, w):
        pygame.draw.line(surface, INK, _pt(P(*a)), _pt(P(*b)),
                         max(2, int(round((w + 0.028) * k))))
        pygame.draw.line(surface, col, _pt(P(*a)), _pt(P(*b)),
                         max(1, int(round(w * k))))

    ph = t * 0.001 * (7.0 if pose == "walk" else 3.0) + phase
    body_y = 0.012 * math.sin(ph * 2.0) - 0.035 * squeeze
    body_x = -0.05 * squeeze

    def B(px, py):
        return body_x + px * (1.0 - 0.13 * squeeze), body_y + py

    _shadow(surface, x, feet + 1, 1.30 * k, 15 * scale, 62)

    def leg(hip_x, hip_y, sw, lift, col, w):
        knee = (hip_x + sw * 0.11, hip_y - 0.35)
        hoof = (hip_x + sw * 0.24, 0.045 + lift)
        limb(col, (hip_x, hip_y), knee, w)
        limb(col, knee, hoof, w * 0.78)
        poly(HOOF, [(hoof[0] - 0.042, 0.055 + lift),
                    (hoof[0] + 0.058, 0.055 + lift),
                    (hoof[0] + 0.052, 0.005 + lift),
                    (hoof[0] - 0.042, 0.005 + lift)])

    if pose == "push":
        far = ((-0.36, 0.14, 0.0), (0.36, -0.10, 0.0))
        near = ((-0.46, -0.22, 0.0), (0.46, 0.24, 0.0))
    elif pose == "walk":
        far = ((-0.36, 1.7, 0.0), (0.36, 0.2, 0.0))
        near = ((-0.46, 0.0, 0.0), (0.46, 2.2, 0.0))
    else:
        far = ((-0.36, 0.0, 0.0), (0.36, 0.0, 0.0))
        near = ((-0.46, 0.0, 0.0), (0.46, 0.0, 0.0))

    def resolved(legs):
        out = []
        for hip_x, off, base in legs:
            if pose == "push" or pose == "idle" or pose == "graze":
                out.append((hip_x, off, 0.0))
            else:
                a = math.sin(ph + off)
                out.append((hip_x, a * 0.21, max(0.0, a) * 0.08))
        return out

    for hip_x, sw, lift in resolved(far):
        leg(hip_x, 0.74, sw, lift, _dark(coat, 0.22), 0.050)

    body = [
        B(-0.60, 0.86), B(-0.58, 1.00), B(-0.44, 1.09),
        B(-0.08, 1.12), B(0.28, 1.10), B(0.46, 1.03),
        B(0.56, 0.90), B(0.53, 0.77), B(0.42, 0.70),
        B(0.06, 0.67), B(-0.28, 0.68), B(-0.50, 0.72),
        B(-0.62, 0.79),
    ]
    poly(coat, body)
    ink(body, 2.2)
    poly(_dark(coat, 0.16), [B(-0.48, 0.73), B(-0.22, 0.68), B(0.06, 0.68),
                             B(0.38, 0.71), B(0.42, 0.76), B(0.04, 0.74),
                             B(-0.28, 0.75)])
    poly(_lite(coat, 0.12), [B(-0.46, 1.00), B(-0.20, 1.08), B(0.10, 1.09),
                             B(0.36, 1.04), B(0.20, 1.00), B(-0.18, 0.99)])
    poly(_dark(coat, 0.08), [B(0.44, 0.92), B(0.54, 0.88), B(0.49, 0.78),
                             B(0.40, 0.74)])

    for hip_x, sw, lift in resolved(near):
        leg(hip_x, 0.76, sw, lift, coat, 0.056)

    # Neck and head.  The head rotates around the neck hinge, so the same
    # drawing reads as alert, grazing and pushing at the wire.
    if pose == "graze":
        hinge = (0.80, 0.70)
        angle = -70.0
    elif pose == "push":
        hinge = (0.82, 1.16 + body_y)
        angle = 12.0
    else:
        hinge = (0.72, 1.34 + body_y)
        angle = 52.0

    limb(coat, (0.42, 1.00 + body_y), hinge, 0.145)
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)

    def H(px, py):
        return hinge[0] + px * ca - py * sa, hinge[1] + px * sa + py * ca

    head = [
        H(-0.14, 0.02), H(-0.12, 0.14), H(-0.01, 0.21),
        H(0.16, 0.18), H(0.30, 0.10), H(0.35, 0.01),
        H(0.29, -0.08), H(0.15, -0.13), H(0.01, -0.11),
        H(-0.11, -0.04),
    ]
    poly(coat, head)
    ink(head, 2.0)
    cheek = [H(0.04, 0.02), H(0.13, 0.09), H(0.24, 0.05), H(0.20, -0.03),
             H(0.08, -0.06)]
    poly(_lite(coat, 0.18), cheek)
    muzzle = [H(0.22, 0.02), H(0.35, 0.01), H(0.29, -0.08), H(0.20, -0.06)]
    poly(_dark(coat, 0.14), muzzle)
    _line(surface, _dark(coat, 0.38), _pt(P(*H(0.23, -0.07))),
          _pt(P(*H(0.31, -0.045))), max(1, int(1.4 * scale)))

    ear = [H(-0.04, 0.13), H(-0.20, 0.16), H(-0.24, 0.06), H(-0.09, 0.03)]
    poly(_dark(coat, 0.10), ear)
    ink(ear, 1.2)
    ear_in = [H(-0.07, 0.12), H(-0.18, 0.13), H(-0.20, 0.07), H(-0.10, 0.05)]
    poly((198, 160, 146), ear_in)

    for dx, col in ((-0.022, HORN_D), (0.0, HORN)):
        horn = [
            H(-0.03 + dx, 0.17), H(-0.10 + dx, 0.29),
            H(-0.20 + dx, 0.36), H(-0.29 + dx, 0.35),
            H(-0.24 + dx, 0.29), H(-0.14 + dx, 0.27),
            H(-0.06 + dx, 0.16),
        ]
        poly(col, horn)
        ink(horn, 1.1)

    pygame.draw.circle(surface, INK, _pt(P(*H(0.10, 0.065))),
                       max(1, int(0.034 * k)))
    pygame.draw.circle(surface, (248, 244, 228), _pt(P(*H(0.11, 0.075))),
                       max(1, int(0.011 * k)))
    pygame.draw.circle(surface, (62, 50, 44), _pt(P(*H(0.325, 0.02))),
                       max(1, int(0.021 * k)))

    beard = [H(0.16, -0.10), H(0.13, -0.19), H(0.06, -0.09)]
    poly(_dark(coat, 0.58), beard)

    # Short upturned tail.
    wag = math.sin(t * 0.004 + phase) * 0.03
    tail = [B(-0.60, 0.96), B(-0.65, 1.12 + wag), B(-0.71, 0.95)]
    poly(coat, tail)
    ink(tail, 1.4)
    poly(_dark(coat, 0.18), [B(-0.65, 0.97), B(-0.68, 1.07 + wag),
                             B(-0.71, 0.96)])

    # Collar and bell: a small glint keeps the neck line readable in shade.
    _line(surface, (74, 58, 42), _pt(P(0.47, 1.08 + body_y)),
          _pt(P(0.54, 0.98 + body_y)), max(1, int(2 * scale)))
    pygame.draw.circle(surface, (150, 122, 58), _pt(P(0.52, 0.95 + body_y)),
                       max(1, int(0.045 * k)))
    pygame.draw.circle(surface, (228, 196, 108), _pt(P(0.53, 0.965 + body_y)),
                       max(1, int(0.018 * k)))


def _person(surface, name, x, feet, scale, right, **kwargs):
    _shadow(surface, x + 9 * scale, feet + 2, 93 * scale, 15 * scale, 66)
    draw_character(surface, name, x, feet, scale, right, **kwargs)


# ---------------------------------------------------------------------------
# Shots
# ---------------------------------------------------------------------------

def _gap_wires(surface, lean, droop=0.0, cut=0.0):
    """The escape gap: one leaning post, three strands, a snap in the middle."""
    post = _post(surface, 738, 548, 128, lean)
    left = [(690, 474), (690, 508)]
    right = [(790, 474), (790, 508)]
    for (lx, ly), (rx, ry) in zip(left, right):
        pin = post(0, ly - 548)
        if cut < 0.5:
            _wire(surface, lx, ly, pin[0] - 2, pin[1], sag=5.0 + droop)
            _wire(surface, pin[0] + 2, pin[1], rx, ry, sag=7.0 + droop)
        else:
            # Two loose ends, curling down into the grass.
            _wire(surface, lx, ly, lx + 34, ly + 16 + droop, sag=3.0,
                  col=(132, 128, 112))
            _wire(surface, rx, ry, rx - 30, ry + 28 + droop, sag=2.0,
                  col=(132, 128, 112))
    return post


def pen(surface, t):
    """Wide: the last bucket, and one goat already working the loose wire."""
    surface.blit(_yard_plate(), (0, 0))
    _motes(surface, t)
    _hen(surface, 168, 486, t, 1)
    _hen(surface, 214, 496, t + 900, 0)

    # Bodi with the feed bucket.
    _person(
        surface, "bodi", 300, 560, 0.72, True,
        t=t, smile=0.12, moving=0.0,
    )
    _bucket(surface, 332, 468, 0.80, grain=True)

    # Biribel with the water bucket, turned toward the pen.
    _person(
        surface, "biribel", 508, 566, 0.70, True,
        t=t, smile=0.05, moving=0.0,
    )
    _bucket(surface, 539, 472, 0.78, water=True)

    lean = 2.0 + 12.0 * _k(t, 2300, 1300)
    push = _k(t, 2450, 1150)
    x = _lerp(670, 678, push)
    _goat(
        surface, x, 552, 0.58, True, t,
        coat=GOAT_CREAM, pose="push" if push > 0.2 else "idle",
        phase=0.4, squeeze=0.35 * push,
    )
    _goat(surface, 822, 548, 0.55, False, t, coat=GOAT_GREY, phase=1.7)
    _goat(surface, 902, 550, 0.56, True, t, coat=GOAT_BROWN, pose="graze",
          phase=3.1)
    _gap_wires(surface, lean)

    # Foreground framing rail, below the actors' feet.
    _line(surface, (62, 52, 38), (536, 618), (1000, 618), 9)
    _line(surface, FENCE, (536, 613), (1000, 613), 6)
    _post(surface, 566, 700, 132, 0.0, 15)
    _line(surface, FENCE_L, (536, 610), (1000, 610), 1)


def slip(surface, t):
    """Close: the post gives, the wire snaps, and she is through."""
    surface.blit(_zoom_plate(700, 520, 1.9), (0, 0))

    # In-focus foreground ground, then scrub along the fence line.
    _poly(
        surface, (122, 99, 70),
        [(0, 582), (WIDTH, 578), (WIDTH, 700), (0, 700)],
    )
    for i in range(18):
        x = 12 + i * 57 + (i * 29 % 27)
        y = 606 + (i * 17 % 70)
        _line(surface, (66, 84, 48), (x, y), (x - 6, y - 16 - i % 8), 3)

    cut = _k(t, 1360, 280)
    lean = 7.0 + 17.0 * _k(t, 300, 1200)
    left = _post(surface, 268, 606, 308, -2.0, 26)
    right = _post(surface, 796, 606, 296, lean, 26)

    # While the strands hold they are in front of her: the camera is outside
    # the pen.  Once they give, the loose ends fall behind the passing goat.
    for ly, ry in ((424, 428), (466, 470), (508, 512)):
        pin_l = left(0, ly - 606)
        pin_r = right(0, ry - 606)
        if cut < 0.5:
            _wire(surface, pin_l[0], pin_l[1], pin_r[0], pin_r[1],
                  sag=13.0, width=4)

    go = _k(t, 1760, 980)
    x = _lerp(510, 1044, go)
    if cut < 0.5:
        pose, squeeze = "push", 0.45
    elif go < 0.35:
        pose, squeeze = "push", 0.30
    else:
        pose, squeeze = "walk", 0.0
    _goat(
        surface, x, 606, 1.45, True, t,
        coat=GOAT_CREAM, pose=pose, phase=0.8, squeeze=squeeze,
    )

    if cut >= 0.5:
        for ly, ry in ((424, 428), (466, 470), (508, 512)):
            pin_l = left(0, ly - 606)
            pin_r = right(0, ry - 606)
            _wire(surface, pin_l[0], pin_l[1], 610, ly + 26, sag=5.0,
                  width=4, col=(138, 134, 118))
            _wire(surface, pin_r[0], pin_r[1], 676, ry + 54, sag=3.0,
                  width=4, col=(138, 134, 118))

    # The snapped end whips up, then falls.
    if 0.0 < cut < 1.0:
        u = cut
        tip = (618 + 30 * u, 466 - 62 * math.sin(u * math.pi))
        _wire(surface, 604, 490, tip[0], tip[1], sag=-8.0, width=4,
              col=(212, 208, 184))
    elif cut >= 1.0:
        _wire(surface, 604, 490, 668, 576, sag=10.0, width=4,
              col=(138, 134, 118))

    # Dust at the push and the trot.
    if 0.05 < cut < 0.95 or 0.0 < go < 0.6:
        for i in range(6):
            age = (t * 0.002 + i * 0.13) % 1.0
            px = 468 + i * 30 + age * 48
            py = 590 - age * 26
            radius = max(2, int(13 * (1.0 - age)))
            puff = pygame.Surface(
                (radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA
            )
            pygame.draw.circle(
                puff, (204, 184, 150, int(42 * (1.0 - age))),
                (radius + 2, radius + 2), radius,
            )
            surface.blit(puff, (int(px - radius - 2), int(py - radius - 2)))
    _vignette(surface, 28)


def orchard(surface, t):
    """Wide: she is already at the trees.  Bodi sees the empty gap."""
    surface.blit(_yard_plate(), (0, 0))
    _motes(surface, t)
    _hen(surface, 700, 506, t + 500, 2)

    step = 9 * _k(t, 1300, 1200)
    _person(
        surface, "bodi", 322 + step, 566, 0.72, True,
        t=t, smile=0.0, moving=0.12 if step else 0.0,
    )
    _bucket(surface, 354 + step, 476, 0.78, grain=True)
    _person(
        surface, "biribel", 492 + step, 570, 0.70, True,
        t=t, smile=0.0, moving=0.12 if step else 0.0,
    )
    _bucket(surface, 523 + step, 478, 0.76, water=True)

    run = _ease_out(t / 3100.0)
    gx = _lerp(776, 1024, run)
    gs = _lerp(0.56, 0.40, run)
    if gx < 1005:
        _goat(surface, gx, 542, gs, True, t, coat=GOAT_CREAM, pose="walk",
              phase=2.0)

    _gap_wires(surface, 16.0, droop=7.0, cut=1.0)

    _line(surface, (62, 52, 38), (536, 618), (1000, 618), 9)
    _line(surface, FENCE, (536, 613), (1000, 613), 6)
    _line(surface, FENCE_L, (536, 610), (1000, 610), 1)
    _vignette(surface, 22)


def potatoes(surface, t):
    """Two-shot: Biribel asks the obvious question."""
    surface.blit(_yard_plate(), (0, 0))
    _motes(surface, t, 8)

    _person(
        surface, "bodi", 372, 610, 1.10, True,
        t=t, smile=0.05, moving=0.0,
    )
    _person(
        surface, "biribel", 656, 610, 1.06, False,
        t=t, smile=0.0, moving=0.0,
    )
    _vignette(surface, 44)


def bodi(surface, t):
    """A dirty single on Bodi: the goat can go, the potatoes cannot."""
    surface.blit(_zoom_plate(440, 516, 1.5), (0, 0))
    _vignette(surface, 40)

    lift = 0.5 + 0.5 * _k(t, 600, 900)
    _person(
        surface, "bodi", 404, 610, 1.16, True,
        t=t, smile=0.08, moving=0.0,
        reach=((46, -124 - 10 * lift),),
    )
    _coil(surface, 454, 484 - 10 * lift, 1.15)
    _person(
        surface, "biribel", 900, 604, 0.82, False,
        t=t, smile=0.0, moving=0.0,
    )

    # Foreground grass keeps the close shot from floating.
    for i in range(12):
        x = i * 89 + (i * 31 % 27)
        y = 700 - (i * 13 % 22)
        _line(surface, (58, 74, 43), (x, y), (x - 8, y - 30 - i % 9), 4)
