"""Mission 7 beat 3: Alex arrives with the mansion plan and a sketch of the farm.

Scene renderers take ``(surface, t_ms)`` on the full-size surface.
The host supplies the letterbox; important action stays inside y=80..620.
Registered lazily from ``missions/m7/meta.py``.

All animation is derived from t_ms, so seeking and replaying are deterministic.
"""

import math

import pygame

from core.config import HEIGHT, WIDTH, font_terminal, font_terminal_small
from engine.anim import REF_H, SPECS, draw_character
from engine.anim import dark as _dark, lite as _lite


INK = (30, 26, 24)
ORANGE = (232, 112, 30)
ORANGE_D = (164, 68, 24)
PPM_FULL = 139.0

RIDE_GROUND = 548
MEET_GROUND = 510

SKY_TOP = (100, 143, 169)
SKY_BOTTOM = (242, 208, 158)
PAPER = (231, 218, 181)
PAPER_LIGHT = (247, 236, 204)
PLAN_INK = (63, 72, 66)
PLAN_RED = (153, 67, 48)

# Backgrounds are static plates. Moving dust, foliage, and light are drawn
# separately, keeping the more detailed landscape inexpensive to render.
_BACKGROUND_CACHE = {}


# ---------------------------------------------------------------------------
# Animation and drawing helpers
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


def _line(surface, col, a, b, w=1):
    pygame.draw.line(surface, col, _pt(a), _pt(b), max(1, int(round(w))))


def _poly(surface, col, pts, width=0):
    pygame.draw.polygon(surface, col, [_pt(p) for p in pts], width)


def _ellipse(surface, col, rect, width=0):
    r = pygame.Rect(*(int(round(v)) for v in rect))
    if r.w > 0 and r.h > 0:
        pygame.draw.ellipse(surface, col, r, width)


def _text(surface, text, pos, color, small=True):
    font = font_terminal_small if small else font_terminal
    image = font.render(text, True, color)
    surface.blit(image, _pt(pos))
    return image.get_rect(topleft=_pt(pos))


def _fit_text(surface, text, rect, color, small=True):
    """Preserve the project's fonts, shrinking only when a label needs it."""
    font = font_terminal_small if small else font_terminal
    image = font.render(text, True, color)
    rect = pygame.Rect(rect)
    factor = min(
        1.0,
        rect.w / float(max(1, image.get_width())),
        rect.h / float(max(1, image.get_height())),
    )
    if factor < 1.0:
        image = pygame.transform.smoothscale(
            image,
            (
                max(1, int(image.get_width() * factor)),
                max(1, int(image.get_height() * factor)),
            ),
        )
    surface.blit(image, image.get_rect(midleft=rect.midleft))


def _shadow(surface, x, y, width, height=13, alpha=65):
    width, height = max(2, int(width)), max(2, int(height))
    shade = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.ellipse(shade, (20, 23, 19, alpha), shade.get_rect())
    surface.blit(shade, (int(x - width / 2), int(y - height / 2)))


def _vignette(surface, strength=32):
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(12):
        inset = i * 12
        rect = pygame.Rect(inset, 80 + i * 4, WIDTH - inset * 2, 540 - i * 8)
        if rect.w > 0 and rect.h > 0:
            pygame.draw.rect(
                layer,
                (12, 19, 19, int(strength * (1.0 - i / 12.0))),
                rect,
                max(1, 12 - i),
            )
    surface.blit(layer, (0, 0))


def _character(surface, name, x, y, scale, facing_right, **kwargs):
    _shadow(surface, x + 9, y + 2, 93 * scale, 15 * scale, 66)
    draw_character(surface, name, x, y, scale, facing_right, **kwargs)


class _ArtPen:
    """Small explicit transform for close-ups and moving hand-held objects.

    Coordinates are local pixels. Unlike a character pen, this transform has
    no implicit facing convention, making grip positions easy to share.
    """

    def __init__(self, surface, x, y, scale=1.0, angle=0.0):
        self.surface = surface
        self.x = x
        self.y = y
        self.scale = scale
        a = math.radians(angle)
        self.ca = math.cos(a)
        self.sa = math.sin(a)

    def point(self, x, y):
        return (
            self.x + (x * self.ca - y * self.sa) * self.scale,
            self.y + (x * self.sa + y * self.ca) * self.scale,
        )

    def poly(self, color, points):
        _poly(self.surface, color, [self.point(x, y) for x, y in points])

    def line(self, color, points, width=1):
        pts = [_pt(self.point(x, y)) for x, y in points]
        if len(pts) >= 2:
            pygame.draw.lines(
                self.surface,
                color,
                False,
                pts,
                max(1, int(round(width * self.scale))),
            )

    def circ(self, color, x, y, radius):
        pygame.draw.circle(
            self.surface,
            color,
            _pt(self.point(x, y)),
            max(1, int(round(radius * self.scale))),
        )


# ---------------------------------------------------------------------------
# Landscape
# ---------------------------------------------------------------------------

def _ridge(surface, base, amp, col, phase):
    points = [(0, HEIGHT)]
    for x in range(0, WIDTH + 25, 25):
        y = base - amp * (
            0.5
            + 0.32 * math.sin(x * 0.0042 + phase)
            + 0.18 * math.sin(x * 0.011 + phase * 2.3)
        )
        points.append((x, int(y)))
    points.append((WIDTH, HEIGHT))
    _poly(surface, col, points)


def _farm_far(surface, y):
    x = WIDTH * 0.79

    pygame.draw.rect(surface, (133, 112, 85), (int(x), int(y - 24), 48, 27))
    _poly(
        surface, (114, 72, 57),
        [(x - 5, y - 24), (x + 53, y - 24), (x + 25, y - 45)],
    )
    pygame.draw.rect(surface, (69, 75, 63), (int(x + 19), int(y - 11), 10, 14))
    pygame.draw.rect(surface, (190, 175, 132), (int(x + 6), int(y - 17), 8, 8))

    x += 66
    pygame.draw.rect(surface, (127, 74, 58), (int(x), int(y - 38), 67, 41))
    _poly(
        surface, (88, 65, 59),
        [(x - 6, y - 38), (x + 73, y - 38), (x + 34, y - 62)],
    )
    pygame.draw.rect(surface, (62, 57, 46), (int(x + 25), int(y - 18), 18, 21))
    _line(surface, (160, 112, 82), (x + 25, y - 18), (x + 43, y + 3), 1)
    _line(surface, (160, 112, 82), (x + 43, y - 18), (x + 25, y + 3), 1)


def _tree(surface, x, y, scale, seed=1, distant=False):
    rnd = _rng(seed)
    trunk = (66, 66, 49) if distant else (63, 53, 39)
    leaf = (75, 95, 65) if distant else (53, 77, 48)
    _line(surface, trunk, (x, y), (x - 4 * scale, y - 100 * scale), 9 * scale)
    for i in range(11):
        dx = (next(rnd) % 65 - 32) * scale
        dy = (next(rnd) % 67) * scale
        radius = (18 + next(rnd) % 17) * scale
        color = _mix(leaf, (118, 128, 73), (i % 4) * 0.09)
        pygame.draw.circle(
            surface, color,
            _pt((x + dx, y - 79 * scale - dy)),
            max(1, int(radius)),
        )


def _fence(surface, y, x0=0, x1=WIDTH):
    if x1 <= x0:
        return
    for rail_y in (y - 27, y - 13):
        _line(surface, (65, 56, 42), (x0, rail_y + 3), (x1, rail_y + 3), 6)
        _line(surface, (126, 104, 70), (x0, rail_y), (x1, rail_y), 4)

    for x in range(int(x0), int(x1), 78):
        _poly(
            surface, (77, 62, 43),
            [(x, y + 5), (x - 2, y - 38), (x + 4, y - 43),
             (x + 9, y - 37), (x + 8, y + 5)],
        )
        _line(surface, (156, 129, 85), (x + 1, y - 35), (x + 2, y), 2)
        for yy in (y - 25, y - 11):
            pygame.draw.circle(surface, (49, 46, 38), (x + 4, int(yy)), 1)


def _background_plate(ground, farm):
    key = (WIDTH, HEIGHT, ground, bool(farm))
    if key in _BACKGROUND_CACHE:
        return _BACKGROUND_CACHE[key]

    plate = pygame.Surface((WIDTH, HEIGHT))
    horizon = ground - 150

    for y in range(0, HEIGHT, 4):
        u = _clamp(y / float(max(1, horizon + 30)))
        plate.fill(_mix(SKY_TOP, SKY_BOTTOM, u), (0, y, WIDTH, 4))

    sun_x = int(WIDTH * 0.74)
    sun_y = int(horizon - 100)
    glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for radius, alpha in ((126, 8), (98, 10), (74, 14), (51, 22)):
        pygame.draw.circle(glow, (255, 223, 165, alpha), (sun_x, sun_y), radius)
    plate.blit(glow, (0, 0))
    pygame.draw.circle(plate, (255, 237, 191), (sun_x, sun_y), 27)

    # Quiet broken cloud banks rather than a flat sky.
    clouds = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for x, y, w in (
        (WIDTH * 0.12, 158, 180),
        (WIDTH * 0.43, 121, 140),
        (WIDTH * 0.80, 192, 205),
    ):
        for i in range(5):
            pygame.draw.ellipse(
                clouds, (250, 230, 194, 24),
                (int(x + i * 22), int(y + math.sin(i) * 4), int(w * 0.48), 13),
            )
    plate.blit(clouds, (0, 0))

    _ridge(plate, ground - 151, 79, (151, 167, 163), 0.6)
    _ridge(plate, ground - 110, 60, (113, 139, 119), 2.1)

    if farm:
        _farm_far(plate, ground - 112)

    # Orchard silhouettes establish a real middle distance.
    for i, x in enumerate(range(18, WIDTH, 91)):
        yy = ground - 83 + math.sin(i * 0.8) * 9
        _tree(plate, x, yy, 0.32 + (i % 3) * 0.035, 21 + i, True)

    _ridge(plate, ground - 63, 36, (82, 110, 75), 4.0)
    _poly(
        plate, (99, 120, 73),
        [(0, ground - 48), (WIDTH * 0.28, ground - 80),
         (WIDTH * 0.61, ground - 51), (WIDTH, ground - 71),
         (WIDTH, HEIGHT), (0, HEIGHT)],
    )

    # Field furrows lead the eye toward the farm.
    for i in range(8):
        start = WIDTH * 0.62 + i * 37
        _line(
            plate, (116, 130, 79),
            (start, ground - 70), (start + 180, ground - 22), 2,
        )

    _poly(
        plate, (107, 114, 68),
        [(0, ground - 28), (WIDTH * 0.30, ground - 38),
         (WIDTH * 0.65, ground - 24), (WIDTH, ground - 34),
         (WIDTH, HEIGHT), (0, HEIGHT)],
    )

    # The track is broad enough for the motorcycle, with irregular shoulders.
    _poly(
        plate, (157, 130, 94),
        [(0, ground - 12), (WIDTH * 0.28, ground - 17),
         (WIDTH * 0.60, ground - 10), (WIDTH, ground - 18),
         (WIDTH, HEIGHT), (0, HEIGHT)],
    )
    _poly(
        plate, (170, 143, 104),
        [(0, ground + 5), (WIDTH, ground - 1),
         (WIDTH, ground + 31), (0, ground + 38)],
    )

    for offset in (13, 50):
        points = [
            (x, ground + offset + math.sin(x * 0.008) * 3)
            for x in range(0, WIDTH + 24, 24)
        ]
        pygame.draw.lines(
            plate, (132, 108, 79), False, [_pt(p) for p in points], 2,
        )

    rnd = _rng(77)
    for _ in range(220):
        x = next(rnd) % WIDTH
        y = ground - 7 + next(rnd) % max(1, HEIGHT - ground + 7)
        color = (186, 158, 114) if next(rnd) % 2 else (137, 113, 82)
        plate.fill(color, (x, y, 2 + next(rnd) % 5, 1 + next(rnd) % 2))

    for _ in range(110):
        x = next(rnd) % WIDTH
        y = ground - 34 + next(rnd) % 19
        h = 3 + next(rnd) % 9
        _line(plate, (72, 94, 53), (x, y), (x + 2, y - h), 1)

    # A framing tree never competes with the actors' faces.
    _tree(plate, WIDTH - 18, ground - 40, 1.10, 146)

    # Limit cache growth if scenes are previewed at several resolutions.
    if len(_BACKGROUND_CACHE) >= 8:
        _BACKGROUND_CACHE.clear()
    _BACKGROUND_CACHE[key] = plate
    return plate


def _backdrop(surface, ground, farm=False, t=0):
    surface.blit(_background_plate(ground, farm), (0, 0))

    # Tiny airborne seeds make held shots feel alive without visual noise.
    motes = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(11):
        x = (i * 137 + t * (0.006 + i * 0.0003)) % (WIDTH + 40) - 20
        y = ground - 48 - (i * 31 % 145) + math.sin(t * 0.0007 + i) * 8
        pygame.draw.circle(motes, (255, 230, 173, 60), _pt((x, y)), 1)
    surface.blit(motes, (0, 0))


def _foreground(surface, ground, t):
    # Sparse close grass frames the track without hiding shoes or wheels.
    for side, base in ((0, 13), (1, WIDTH - 35)):
        for i in range(14):
            x = base + (i * 13 % 58) * (1 if side == 0 else -1)
            y = min(617, ground + 61 + i % 4 * 4)
            sway = math.sin(t * 0.0015 + i * 1.7) * 2
            _line(
                surface, (68, 83, 45),
                (x, y), (x + sway - 5, y - 12 - i % 6), 2,
            )


def _dust(surface, t, puffs):
    for ts, x, y, size in puffs:
        age = t - ts
        if not 0 <= age < 1450:
            continue
        u = age / 1450.0
        radius = max(1, int(size * (0.50 + u * 1.25)))
        puff = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
        for factor, alpha in ((1.0, 22), (0.76, 29), (0.48, 23)):
            pygame.draw.circle(
                puff,
                (220, 190, 144, int(alpha * (1.0 - u) ** 1.3)),
                (radius + 2, radius + 2),
                max(1, int(radius * factor)),
            )
        surface.blit(
            puff,
            (
                int(x - radius + u * 25),
                int(y - radius - u * 30),
            ),
        )


# ---------------------------------------------------------------------------
# Motorcycle and rider
# ---------------------------------------------------------------------------

def _bike(surface, x, y, ppm, wheel_a, facing_right=True, lean=0.0):
    """Side-on trail bike, with coherent axles, suspension, and contact points."""
    sg = 1 if facing_right else -1

    def P(mx, my):
        return (
            x + sg * (mx + lean * my) * ppm,
            y - my * ppm,
        )

    def line(col, a, b, width):
        _line(surface, col, P(*a), P(*b), width * ppm)

    def shape(col, pts):
        _poly(surface, col, [P(*p) for p in pts])

    _shadow(surface, x + 12, y + 3, ppm * 2.08, ppm * 0.16, 76)
    radius = 0.33 * ppm

    for wx in (-0.64, 0.66):
        center = P(wx, 0.33)
        pygame.draw.circle(surface, (26, 27, 27), _pt(center), int(radius))
        pygame.draw.circle(surface, (56, 57, 57), _pt(center), int(radius * 0.84))
        pygame.draw.circle(surface, (181, 180, 168), _pt(center), int(radius * 0.65))
        pygame.draw.circle(surface, (61, 65, 63), _pt(center), int(radius * 0.56))

        for i in range(20):
            a = wheel_a + i * math.tau / 20
            a0 = (
                center[0] + math.cos(a) * radius * 0.91,
                center[1] + math.sin(a) * radius * 0.91,
            )
            a1 = (
                center[0] + math.cos(a + 0.04) * radius,
                center[1] + math.sin(a + 0.04) * radius,
            )
            _line(surface, (18, 21, 20), a0, a1, max(2, ppm * 0.035))

        for i in range(8):
            a = wheel_a + i * math.tau / 8
            end = (
                center[0] + math.cos(a) * radius * 0.53,
                center[1] + math.sin(a) * radius * 0.53,
            )
            _line(surface, (161, 163, 155), center, end, max(1, ppm * 0.012))

        pygame.draw.circle(
            surface, (199, 195, 174), _pt(center), max(2, int(ppm * 0.047)),
        )

    # Swingarm, frame triangle, and rear shock.
    line((78, 80, 75), (-0.12, 0.48), (-0.64, 0.33), 0.085)
    line((174, 175, 160), (-0.12, 0.46), (-0.64, 0.35), 0.032)
    line(INK, (-0.42, 0.88), (-0.05, 0.45), 0.065)
    line(INK, (-0.05, 0.45), (0.41, 0.91), 0.065)
    line(INK, (-0.42, 0.88), (0.41, 0.91), 0.055)
    line((196, 172, 96), (-0.36, 0.77), (-0.17, 0.46), 0.040)

    # Engine block and cooling ribs.
    shape(
        (73, 77, 74),
        [(-0.19, 0.46), (0.27, 0.45), (0.31, 0.70),
         (0.18, 0.84), (-0.12, 0.80)],
    )
    shape(
        (137, 141, 131),
        [(-0.13, 0.48), (0.23, 0.48), (0.24, 0.67), (-0.10, 0.69)],
    )
    for i in range(4):
        line(
            (60, 65, 62),
            (-0.09, 0.70 + i * 0.032),
            (0.19, 0.70 + i * 0.032),
            0.014,
        )
    pygame.draw.circle(
        surface, (95, 99, 91), _pt(P(0.05, 0.57)), max(2, int(ppm * 0.11)),
    )
    line((184, 177, 151), (0.18, 0.49), (-0.26, 0.39), 0.044)
    line((112, 113, 101), (-0.26, 0.39), (-0.80, 0.70), 0.063)

    # Forks and fork boots.
    for dx in (-0.024, 0.024):
        line((181, 184, 174), (0.47 + dx, 1.07), (0.66 + dx, 0.33), 0.034)
        line((49, 53, 49), (0.49 + dx, 0.96), (0.57 + dx, 0.65), 0.044)

    shape(
        ORANGE_D,
        [(-0.14, 0.99), (0.40, 1.05), (0.47, 0.88),
         (0.26, 0.78), (-0.11, 0.83)],
    )
    shape(
        ORANGE,
        [(-0.13, 1.00), (0.36, 1.04), (0.42, 0.91),
         (0.22, 0.87), (-0.11, 0.90)],
    )
    line((255, 167, 72), (-0.08, 0.99), (0.31, 1.02), 0.015)

    shape(
        (30, 32, 30),
        [(-0.83, 0.99), (-0.13, 1.02), (-0.09, 0.91), (-0.77, 0.88)],
    )
    line((95, 91, 75), (-0.76, 0.98), (-0.19, 1.00), 0.014)

    shape(ORANGE, [(-1.00, 0.91), (-0.79, 0.98), (-0.65, 0.89), (-0.92, 0.82)])
    shape(ORANGE, [(0.40, 0.76), (0.84, 0.75), (0.99, 0.65), (0.48, 0.67)])
    line((255, 166, 72), (0.47, 0.75), (0.83, 0.74), 0.018)

    shape(
        (230, 222, 194),
        [(0.51, 1.03), (0.72, 1.02), (0.76, 0.85), (0.55, 0.85)],
    )
    line((69, 67, 54), (0.62, 0.99), (0.64, 0.89), 0.017)
    line((166, 170, 156), (0.47, 1.07), (0.35, 1.27), 0.035)
    line(INK, (0.35, 1.27), (0.20, 1.28), 0.043)
    line((107, 110, 98), (-0.15, 0.36), (0.05, 0.36), 0.032)

    # Compact canvas tool roll strapped behind the saddle.
    shape(
        (85, 92, 65),
        [(-0.94, 1.02), (-0.58, 1.04), (-0.56, 1.15), (-0.91, 1.15)],
    )
    for xx in (-0.84, -0.66):
        line((52, 58, 44), (xx, 1.03), (xx, 1.15), 0.025)


def _rider(surface, x, ground, ppm, t, brake=0.0, dismount=0.0):
    """Side-on riding pose in Alex's figure_kit look: spiky hair, hood, blue
    hoodie with the red chest band, black belt, ripped jeans, white sneakers."""
    spec = SPECS["alex"]
    skin, hair, coat = spec["skin"], spec["hair"], spec["coat"]
    jeans, shoe, sole = spec["trousers"], spec["shoes"], spec["sole"]
    hood, cuff, band = spec["lapel"], spec["cuff_col"], spec["print"][1]

    bounce = math.sin(t * 0.022) * 0.010 * (1.0 - brake)
    rise = math.sin(dismount * math.pi) * 0.28
    shift = dismount * 0.37

    def P(mx, my):
        return (
            x + (mx + shift) * ppm,
            ground - (my + bounce + rise) * ppm,
        )

    def shape(col, pts, outline=True):
        pts = [P(*q) for q in pts]
        _poly(surface, col, pts)
        if outline:
            _poly(surface, INK, pts, 2)

    def limb(a, b, col, width):
        _line(surface, INK, P(*a), P(*b), (width + 0.030) * ppm)
        _line(surface, col, P(*a), P(*b), width * ppm)

    lean = 0.10 * (1.0 - brake)
    hip = (-0.33, 1.08)
    shoulder = (-0.27 + lean, 1.56)
    hx, hy = -0.17 + lean, 1.80            # head centre

    # Far leg and arm, a shade darker.
    far_j, far_c = _dark(jeans, 0.25), _dark(coat, 0.25)
    limb((-0.36, 1.07), (0.10, 0.80), far_j, 0.15)
    limb((0.10, 0.80), (-0.04, 0.42), far_j, 0.12)
    shape(_dark(shoe, 0.25), [(-0.09, 0.45), (0.15, 0.43), (0.17, 0.36), (-0.09, 0.36)])
    elbow = (0.04 + lean * 0.3, 1.36)
    limb(shoulder, elbow, far_c, 0.13)
    limb(elbow, (0.23, 1.28), far_c, 0.11)

    # Hood bunched behind the neck.
    shape(hood, [(hx - 0.27, 1.50), (hx - 0.30, 1.64), (hx - 0.18, 1.70), (hx - 0.06, 1.62)])

    # Hoodie body, hem resting on the belt.
    def edge(y):
        u = (y - 1.10) / 0.48
        return _lerp(-0.44, -0.42 + lean, u), _lerp(-0.13, -0.09 + lean, u)

    (b0, f0), (b1, f1) = edge(1.10), edge(1.58)
    shape(coat, [(b0, 1.10), (b1, 1.58), (-0.24 + lean, 1.64), (f1, 1.58), (f0, 1.10)])
    shape(_dark(coat, 0.28), [(b0, 1.10), (b1, 1.58), (b1 + 0.08, 1.56), (b0 + 0.07, 1.12)], outline=False)
    lo, hi = edge(1.40), edge(1.46)
    shape(band, [(lo[0], 1.40), (hi[0], 1.46), (hi[1], 1.46), (lo[1], 1.40)], outline=False)
    _line(surface, spec["strings"], P(f1 - 0.03, 1.56), P(f1 - 0.01, 1.47), 1)
    shape(spec["belt"], [(b0, 1.07), (b0, 1.12), (f0, 1.12), (f0, 1.07)], outline=False)

    # Near leg: bent knee, worn-through knee, white sneaker with a red sole.
    knee = (0.15 - dismount * 0.12, 0.80)
    foot = (-0.05 + dismount * 0.13, 0.41 - dismount * 0.13)
    limb(hip, knee, jeans, 0.17)
    limb(knee, foot, jeans, 0.13)
    for d in (-0.03, 0.0, 0.03):
        _line(surface, spec["rips"], P(knee[0] - 0.05, knee[1] + d), P(knee[0] + 0.04, knee[1] + d + 0.01), 1)
    fx, fy = foot
    shape(shoe, [(fx - 0.05, fy + 0.05), (fx + 0.20, fy + 0.03), (fx + 0.23, fy - 0.04), (fx - 0.05, fy - 0.04)])
    _line(surface, sole, P(fx - 0.05, fy - 0.045), P(fx + 0.23, fy - 0.045), max(2, int(ppm * 0.022)))

    # Neck and an angular side-on head, face toward the bars.
    limb((hx - 0.05, 1.60), (hx - 0.03, 1.72), skin, 0.10)
    head = [
        (hx - 0.17, hy + 0.04), (hx - 0.13, hy + 0.17), (hx + 0.09, hy + 0.18),
        (hx + 0.16, hy + 0.07), (hx + 0.20, hy - 0.01), (hx + 0.16, hy - 0.05),
        (hx + 0.15, hy - 0.14), (hx + 0.05, hy - 0.20), (hx - 0.07, hy - 0.14),
        (hx - 0.13, hy - 0.06),
    ]
    shape(skin, head)
    shape(_dark(skin, 0.18), [(hx - 0.16, hy + 0.03), (hx - 0.12, hy - 0.06), (hx - 0.06, hy - 0.13),
                              (hx - 0.02, hy - 0.04)], outline=False)
    shape(_dark(skin, 0.22), [(hx - 0.07, hy + 0.03), (hx - 0.02, hy + 0.04),
                              (hx - 0.01, hy - 0.05), (hx - 0.07, hy - 0.06)])
    shape(hair, [
        (hx - 0.19, hy + 0.00), (hx - 0.24, hy + 0.11), (hx - 0.15, hy + 0.15),
        (hx - 0.17, hy + 0.27), (hx - 0.06, hy + 0.20), (hx - 0.02, hy + 0.31),
        (hx + 0.04, hy + 0.21), (hx + 0.12, hy + 0.28), (hx + 0.12, hy + 0.18),
        (hx + 0.21, hy + 0.17), (hx + 0.13, hy + 0.10), (hx + 0.03, hy + 0.12),
        (hx - 0.09, hy + 0.09), (hx - 0.11, hy - 0.02),
    ])
    _line(surface, INK, P(hx + 0.07, hy + 0.07), P(hx + 0.15, hy + 0.06), max(2, int(ppm * 0.022)))
    pygame.draw.rect(surface, INK, (*_pt(P(hx + 0.10, hy + 0.04)), max(2, int(ppm * 0.03)), max(2, int(ppm * 0.03))))
    _line(surface, _dark(skin, 0.4), P(hx + 0.09, hy - 0.10), P(hx + 0.14, hy - 0.09), 1)

    # Near arm on the bar until he starts climbing off.
    near_elbow = (-0.03 + lean * 0.4, 1.38)
    hand = (0.23 - dismount * 0.15, 1.28 + dismount * 0.08)
    limb((-0.21 + lean, 1.56), near_elbow, coat, 0.14)
    limb(near_elbow, hand, coat, 0.115)
    limb((hand[0] - 0.05, hand[1] + 0.005), (hand[0] - 0.01, hand[1]), cuff, 0.12)
    pygame.draw.circle(surface, INK, _pt(P(*hand)), max(2, int(ppm * 0.062)))
    pygame.draw.circle(surface, skin, _pt(P(*hand)), max(2, int(ppm * 0.048)))


def _bike_x(t):
    return -170.0 + 650.0 * _ease_out(t / 2500.0)


def _puffs():
    out = []
    for i in range(42):
        ts = i * 60
        speed = 1.0 - _clamp(ts / 2500.0)
        out.append(
            (ts, _bike_x(ts) - 66, RIDE_GROUND - 5, 11 + 12 * speed)
        )
    for i in range(8):
        out.append(
            (1940 + i * 85, 382 + i * 10, RIDE_GROUND - 4, 18 + i * 2)
        )
    return out


def _bike_front_overlay(surface, bx, ppm, wheel=0.0, off=0.0):
    """Near-side tank partially occludes the seated rider's far thigh."""
    if off > 0.05:
        return

    def P(mx, my):
        return bx + mx * ppm, RIDE_GROUND - my * ppm

    _poly(
        surface, ORANGE,
        [P(-0.09, 0.98), P(0.36, 1.03), P(0.42, 0.91),
         P(0.22, 0.87), P(-0.09, 0.90)],
    )
    _line(surface, (255, 165, 76), P(-0.06, 0.98), P(0.30, 1.01), 1)


def ride(surface, t):
    """Fast arrival, controlled braking, then a readable planted dismount."""
    t = max(0, t)
    _backdrop(surface, RIDE_GROUND, farm=True, t=t)
    _fence(surface, RIDE_GROUND - 40, 0, 330)

    for name, x, scale in (("bodi", 850, 0.60), ("biribel", 771, 0.63)):
        _character(
            surface, name, x, RIDE_GROUND - 7, scale, False,
            t=t, smile=0.12,
        )

    bx = _bike_x(t)
    ppm = PPM_FULL * 0.64
    brake = _k(t, 1650, 850)
    wheel = bx / (0.33 * ppm)
    settle = math.sin(_clamp((t - 2150) / 500.0) * math.pi) * 1.8
    ground = RIDE_GROUND + settle

    _dust(surface, t, _puffs())
    _bike(surface, bx, ground, ppm, wheel, lean=-0.022 * brake)

    dismount = _k(t, 2850, 650)
    if dismount < 0.52:
        _rider(surface, bx, ground, ppm, t, brake, dismount)
        _bike_front_overlay(surface, bx, ppm, wheel, dismount)
    else:
        # Swap only once the body has risen off the saddle. The remainder is
        # a short hop down, followed by a stable standing pose beside the bike.
        step = _clamp((dismount - 0.52) / 0.48)
        x = bx + _lerp(28, 87, _ease_out(step))
        foot_y = RIDE_GROUND - math.sin(step * math.pi) * 23 - (1 - step) * 15
        _character(
            surface, "alex", x, foot_y, 0.64, True,
            t=t, moving=0.0, smile=0.65,
        )

    _foreground(surface, RIDE_GROUND, t)


# ---------------------------------------------------------------------------
# Meeting and folder handover
# ---------------------------------------------------------------------------

def _lerp_point(a, b, u):
    return _lerp(a[0], b[0], u), _lerp(a[1], b[1], u)


def _folder_art(pen, opened=False):
    """A consistent buff dossier used in both the wide shot and the insert."""
    pen.poly(
        (92, 65, 38),
        [(-24, -30), (-8, -30), (-4, -34), (23, -34),
         (25, 31), (-24, 31)],
    )
    pen.poly(
        (178, 139, 82),
        [(-23, -29), (-8, -29), (-4, -33), (22, -33),
         (23, 30), (-23, 30)],
    )
    pen.poly(
        (205, 171, 111),
        [(-25, -25), (22, -25), (24, 31), (-23, 31)],
    )
    pen.line((231, 201, 146), [(-23, -24), (21, -24)], 0.8)
    pen.line((151, 116, 69), [(-21, 27), (20, 27)], 0.7)
    pen.poly((231, 219, 184), [(-17, -15), (15, -15), (15, -3), (-17, -3)])
    pen.line((94, 85, 61), [(-13, -11), (11, -11)], 1)
    pen.line((118, 103, 73), [(-13, -7), (5, -7)], 0.7)
    pen.line((153, 70, 47), [(-12, 12), (12, 12)], 1.5)
    pen.line((153, 70, 47), [(-12, 16), (7, 16)], 0.8)
    if opened:
        pen.line((127, 94, 56), [(-21, -23), (-20, 27)], 0.8)


def _draw_folder(surface, x, y, scale=0.72, angle=-7):
    _folder_art(_ArtPen(surface, x, y, scale, angle))


def _meeting_background(surface, t):
    _backdrop(surface, MEET_GROUND, farm=True, t=t)
    _fence(surface, MEET_GROUND - 46, 575, WIDTH)
    _bike(surface, 145, MEET_GROUND + 4, PPM_FULL * 0.76, 0.7, lean=-0.05)

    # A visible side stand makes the parked motorcycle feel grounded.
    _line(
        surface, (66, 68, 57),
        (146, MEET_GROUND - 29), (126, MEET_GROUND + 7), 3,
    )
    _line(
        surface, (49, 51, 44),
        (120, MEET_GROUND + 8), (133, MEET_GROUND + 8), 3,
    )

    _character(
        surface, "bodi", 872, MEET_GROUND - 5, 0.66, False,
        t=t, smile=0.15,
    )


def _meet_set(surface, t, alex_x, take=0.0, holding=False):
    """The dossier follows the same hand-to-hand path throughout the exchange."""
    _meeting_background(surface, t)
    by = MEET_GROUND
    bx = 682
    scale = 0.80
    ka = scale * SPECS["alex"]["height"] / REF_H
    kb = scale * SPECS["biribel"]["height"] / REF_H

    a_hand = (alex_x + 72 * ka, by - 151 * ka)
    b_hand = (bx - 71 * kb, by - 151 * kb)
    take = _clamp(take)

    if holding:
        # Alex first raises the dossier, then Biribel takes its weight.
        raised = _k(t, 650, 700)
        a_hand = (a_hand[0], a_hand[1] + (1 - raised) * 24)
        fx, fy = _lerp_point(a_hand, b_hand, take)
        fy -= math.sin(take * math.pi) * 7

        a_reach = ((fx - alex_x, fy - by),) if take < 0.94 else None
        b_reach = ((fx - bx, fy - by),) if take > 0.04 else None

        _character(
            surface, "alex", alex_x, by, scale, True,
            t=t, smile=0.9, reach=a_reach,
        )
        _character(
            surface, "biribel", bx, by, scale, False,
            t=t, reach=b_reach,
        )
        _draw_folder(surface, fx, fy + 8, 0.76, _lerp(-12, 7, take))

        # Small contact fingers sit in front of the dossier's edge.
        for active, point, spec_name in (
            (take < 0.94, (fx - 13, fy + 3), "alex"),
            (take > 0.04, (fx + 13, fy + 3), "biribel"),
        ):
            if active:
                pygame.draw.circle(
                    surface, SPECS[spec_name]["skin"], _pt(point), 4,
                )
    else:
        _character(
            surface, "biribel", bx, by, scale, False, t=t,
        )
        _character(
            surface, "alex", alex_x, by, scale, True,
            t=t, smile=0.85,
        )

    _foreground(surface, MEET_GROUND, t)


def meet(surface, t):
    """Alex recognizes Biribel; his rush gives way to a delighted, eager grin."""
    _meet_set(surface, t, 465 + 24 * _k(t, 0, 2100))


def folder(surface, t):
    """Alex steps closer, presents the dossier, and transfers it to Biribel."""
    _meet_set(
        surface, t,
        489 + 30 * _k(t, 0, 1000),
        take=_k(t, 1900, 800),
        holding=True,
    )


# ---------------------------------------------------------------------------
# Dossier insert
# ---------------------------------------------------------------------------

def _insert_background(surface, t, darkness=155):
    _backdrop(surface, MEET_GROUND + 40, farm=True, t=t)
    veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    veil.fill((12, 20, 19, darkness))
    surface.blit(veil, (0, 0))
    _vignette(surface, 40)


def _paper_hand(surface, x, y, scale=1.0, right=False):
    """A thumb on top of the page, with a sleeve continuing off its lower edge."""
    skin = SPECS["biribel"]["skin"]
    sleeve = SPECS["biribel"]["coat"]
    sg = -1 if right else 1
    pen = _ArtPen(surface, x, y, scale)

    def shape(col, points):
        pen.poly(col, [(a * sg, b) for a, b in points])

    shape(_dark(sleeve, 0.35), [(-21, 30), (16, 29), (27, 105), (-30, 105)])
    shape(sleeve, [(-17, 30), (12, 30), (19, 105), (-24, 105)])
    shape(_dark(sleeve, 0.45), [(-19, 27), (15, 25), (18, 40), (-20, 43)])
    shape(
        _dark(skin, 0.24),
        [(-16, 2), (-5, -10), (5, -7), (12, 5),
         (13, 24), (5, 34), (-11, 32), (-20, 20)],
    )
    shape(
        skin,
        [(-13, 3), (-4, -7), (3, -5), (9, 7),
         (9, 23), (3, 29), (-9, 28), (-16, 18)],
    )
    shape(
        _lite(skin, 0.13),
        [(-13, 3), (-6, -16), (1, -20), (7, -16),
         (7, -7), (1, 7), (-5, 15), (-12, 12)],
    )
    for i in range(3):
        pen.line(
            _dark(skin, 0.26),
            [(sg * (-8 + i * 5), 17), (sg * (-6 + i * 5), 24)],
            0.8,
        )


def _dashed_line(surface, color, points, dash=8, gap=5, width=2):
    phase = 0.0
    period = float(dash + gap)
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length <= 0:
            continue
        distance = 0.0
        while distance < length:
            cycle = phase % period
            span = min(length - distance, period - cycle)
            if cycle < dash:
                span = min(span, dash - cycle)
                p0 = (a[0] + dx * distance / length, a[1] + dy * distance / length)
                p1 = (
                    a[0] + dx * (distance + span) / length,
                    a[1] + dy * (distance + span) / length,
                )
                _line(surface, color, p0, p1, width)
            distance += max(0.001, span)
            phase += max(0.001, span)


def _plan_page(surface, rect, t):
    """Alex's sketch of the farm as the raid builds it, with the Guard's three approaches."""
    rect = pygame.Rect(rect)
    x, y, w, h = rect

    pygame.draw.rect(surface, PAPER, rect)
    pygame.draw.rect(surface, PAPER_LIGHT, rect.inflate(-8, -8))
    pygame.draw.rect(surface, (174, 158, 119), rect, 1)

    # Deterministic paper fibres and old fold lines.
    rnd = _rng(409)
    for _ in range(110):
        px = x + 8 + next(rnd) % max(1, w - 16)
        py = y + 8 + next(rnd) % max(1, h - 16)
        surface.fill((226, 213, 180), (px, py, 1 + next(rnd) % 3, 1))

    _line(surface, (217, 201, 165), (x + w * 0.52, y + 8), (x + w * 0.52, y + h - 8), 1)
    _line(surface, (221, 207, 173), (x + 8, y + h * 0.60), (x + w - 8, y + h * 0.60), 1)

    margin = 22
    _fit_text(
        surface, "BODI'S FARM",
        (x + margin, y + 15, w - 160, 30), PLAN_INK, small=False,
    )
    _fit_text(
        surface, "GUARD SWEEP / ALEX'S SKETCH",
        (x + margin, y + 47, w - 2 * margin, 19), (104, 100, 78),
    )
    _line(surface, (128, 126, 96), (x + margin, y + 74), (x + w - margin, y + 74), 1)

    stamp = pygame.Rect(x + w - 138, y + 18, 114, 29)
    pygame.draw.rect(surface, PLAN_RED, stamp, 2)
    _fit_text(surface, "TONIGHT", stamp.inflate(-10, -8), PLAN_RED)

    map_rect = pygame.Rect(x + 22, y + 88, int(w * 0.61), h - 123)
    notes_rect = pygame.Rect(map_rect.right + 17, y + 88, x + w - 22 - map_rect.right - 17, h - 123)

    # Fine survey grid.
    for gx in range(map_rect.left, map_rect.right, 20):
        _line(surface, (222, 213, 181), (gx, map_rect.top), (gx, map_rect.bottom), 1)
    for gy in range(map_rect.top, map_rect.bottom, 20):
        _line(surface, (222, 213, 181), (map_rect.left, gy), (map_rect.right, gy), 1)

    area = map_rect.inflate(-12, -12)

    # World metres from raid_world / m7world3d (x east, z north), north up.
    X0, X1, Z0, Z1 = -22.0, 48.0, -24.0, 26.0

    def W(wx, wz):
        return (
            area.left + (wx - X0) / (X1 - X0) * area.w,
            area.top + (Z1 - wz) / (Z1 - Z0) * area.h,
        )

    def block(x0, z0, x1, z1, label, fill=(206, 201, 168)):
        ax, ay = W(x0, z1)
        bx, by = W(x1, z0)
        r = pygame.Rect(int(ax), int(ay), max(2, int(bx - ax)), max(2, int(by - ay)))
        pygame.draw.rect(surface, fill, r)
        pygame.draw.rect(surface, PLAN_INK, r, 2)
        if label:
            _fit_text(surface, label, r.inflate(-6, -6), PLAN_INK)
        return r

    track_col = (196, 184, 146)
    # The track up from the valley road, its yard apron, and the orchard lane.
    _line(surface, track_col, W(0, -24), W(0, -12), max(4, int(6.4 * area.w / (X1 - X0))))
    _line(surface, track_col, W(20, 0), W(48, 0), max(3, int(2.3 * area.w / (X1 - X0))))

    # Yard fence, open at the track mouth (south) and the orchard gate (east).
    fence = (137, 143, 111)
    for a_, b_ in (
        ((-20, -16), (-3.4, -16)), ((3.4, -16), (20, -16)),
        ((-20, -16), (-20, 22)), ((-20, 22), (20, 22)),
        ((20, -16), (20, -3)), ((20, 3), (20, 22)),
    ):
        _line(surface, fence, W(*a_), W(*b_), 2)

    block(-16.5, 7.0, -7.5, 13.0, "HOUSE")
    block(7.0, 7.0, 19.0, 17.0, "BARN")
    block(-12.7, -10.5, -9.3, -7.5, "", fill=(214, 190, 150))
    _fit_text(surface, "FUEL", (int(W(-19, -11)[0]), int(W(-19, -11)[1]), 46, 14), PLAN_INK)
    pygame.draw.circle(surface, PLAN_INK, _pt(W(1.0, 4.0)), 5, 2)
    _fit_text(surface, "WELL", (int(W(-3, 1.5)[0]), int(W(-3, 1.5)[1]), 40, 14), PLAN_INK)

    # Orchard rows east of the gate.
    for ox in (26, 31, 36, 41):
        for oz in (-8, -2, 4, 10, 16):
            pygame.draw.circle(surface, (122, 138, 98), _pt(W(ox, oz)), 4)
            pygame.draw.circle(surface, PLAN_INK, _pt(W(ox, oz)), 4, 1)
    _fit_text(surface, "ORCHARD", (int(W(27, 21)[0]), int(W(27, 21)[1]), 90, 14), PLAN_INK)

    # Guard approaches, the visual focal point: east, south, then north.
    def arrow(points, number):
        pts = [W(*p) for p in points]
        _dashed_line(surface, PLAN_RED, pts, dash=8, gap=5, width=2)
        (ax, ay), (bx, by) = pts[-2], pts[-1]
        ang = math.atan2(by - ay, bx - ax)
        for side in (-1, 1):
            _line(
                surface, PLAN_RED, (bx, by),
                (bx - 9 * math.cos(ang + side * 0.5), by - 9 * math.sin(ang + side * 0.5)), 2,
            )
        sx, sy = pts[0]
        pygame.draw.circle(surface, PAPER_LIGHT, _pt((sx, sy)), 9)
        pygame.draw.circle(surface, PLAN_RED, _pt((sx, sy)), 9, 2)
        _fit_text(surface, str(number), (int(sx - 4), int(sy - 6), 10, 12), PLAN_RED)

    arrow(((46.5, -4.5), (34, -1), (23, 0)), 1)
    arrow(((4.5, -23), (4.5, -13)), 2)
    arrow(((-4, 25), (-3.5, 18.5)), 3)

    # North marker.
    nx, ny = map_rect.right - 13, map_rect.top + 15
    _line(surface, PLAN_INK, (nx, ny + 20), (nx, ny), 1)
    _poly(surface, PLAN_INK, [(nx, ny), (nx - 4, ny + 7), (nx + 4, ny + 7)])
    _fit_text(surface, "N", (nx - 4, ny - 14, 12, 12), PLAN_INK)

    # Written intelligence: enough breathing room to read on a held insert.
    note_x = notes_rect.x
    note_w = notes_rect.w
    sections = (
        ("01  ORCHARD", ("Rifles and a dog.", "Hold the gate.")),
        ("02  TRACK", ("Trucks come up it.", "Tractor blocks it.")),
        ("03  NORTH", ("Last push, past", "the barn. Use loft.")),
    )
    row = max(65, notes_rect.h // 3)
    for i, (heading, lines) in enumerate(sections):
        yy = notes_rect.y + i * row
        _fit_text(surface, heading, (note_x, yy, note_w, 19), PLAN_RED)
        for j, text in enumerate(lines):
            _fit_text(
                surface, text,
                (note_x, yy + 24 + j * 18, note_w, 17),
                PLAN_INK,
            )
        if i < 2:
            _line(
                surface, (197, 184, 148),
                (note_x, yy + row - 9), (note_x + note_w, yy + row - 9), 1,
            )

    # Alex's final underline appears during the push-in, not as flashing UI.
    reveal = _k(t, 450, 1100)
    underline_y = notes_rect.y + row * 2 + 61
    _line(
        surface, PLAN_RED,
        (note_x, underline_y),
        (note_x + max(1, note_w * 0.88 * reveal), underline_y - 2),
        2,
    )

    _fit_text(
        surface, "GUARD ROUTES IN RED. MANSION PLAN UNDERNEATH",
        (x + margin, y + h - 27, w - margin * 2, 16),
        (119, 100, 74),
    )


def plan_insert(surface, t):
    """Biribel opens the folder: Alex's sketch of the farm and where the Guard comes in."""
    _insert_background(surface, t, 162)
    u = _k(t, 0, 2400)

    width = min(WIDTH - 100, int(_lerp(700, 738, u)))
    height = int(_lerp(386, 407, u))
    cx = WIDTH // 2
    cy = 342
    rect = pygame.Rect(cx - width // 2, cy - height // 2, width, height)

    # Folder beneath the unfolded sheet.
    backing = rect.inflate(24, 22)
    shadow = pygame.Surface((backing.w + 32, backing.h + 32), pygame.SRCALPHA)
    pygame.draw.rect(
        shadow, (0, 0, 0, 80),
        (16, 16, backing.w, backing.h), border_radius=5,
    )
    surface.blit(shadow, (backing.x - 6, backing.y - 3))
    pygame.draw.rect(surface, (153, 112, 64), backing)
    pygame.draw.rect(surface, (193, 153, 95), backing.inflate(-5, -5))
    _plan_page(surface, rect, t)

    # Sleeves remain below the page and within the letterboxed action area.
    old_clip = surface.get_clip()
    surface.set_clip(old_clip.clip(pygame.Rect(0, 80, WIDTH, 540)))
    _paper_hand(surface, rect.left + 44, rect.bottom - 11, 0.92)
    _paper_hand(surface, rect.right - 42, rect.bottom - 10, 0.92, right=True)
    surface.set_clip(old_clip)


# ---------------------------------------------------------------------------
# Shotgun art and handover
# ---------------------------------------------------------------------------

def _shotgun_art(pen, grip, fore):
    """Pump-action sporting shotgun; grip and fore-end share one exact frame."""
    gx, gy = grip
    dx, dy = fore[0] - gx, fore[1] - gy
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    px, py = -uy, ux

    def P(a, b):
        return gx + ux * a + px * b, gy + uy * a + py * b

    steel, dark, edge = (65, 72, 78), (25, 29, 33), (138, 148, 152)
    wood, wood_d = (139, 87, 47), (83, 49, 29)
    L = length

    def shape(col, points):
        pen.poly(col, [P(a, b) for a, b in points])

    def line(col, points, width=1):
        pen.line(col, [P(a, b) for a, b in points], width)

    # Swept comb, narrow wrist, broad heel, and rubber butt plate.
    shape(dark, [(-3, -6), (-15, -8), (-47, -5), (-49, 12),
                 (-41, 14), (-18, 6), (-5, 7)])
    shape(wood, [(-5, -4), (-16, -6), (-45, -3), (-46, 10),
                 (-41, 11), (-18, 4), (-6, 5)])
    shape(wood_d, [(-44, 5), (-20, 1), (-7, 3), (-18, 6), (-43, 11)])
    line((182, 121, 67), [(-42, -1), (-22, -3), (-12, -2)])
    line((108, 65, 36), [(-39, 4), (-29, 2), (-20, 2)], 0.6)
    shape(dark, [(-49, -5), (-46, -5), (-47, 11), (-50, 12)])

    # Receiver, ejection port, and a small fastener.
    shape(dark, [(-7, -8), (L * 0.44, -8), (L * 0.48, 2), (2, 5), (-7, 4)])
    shape(steel, [(-5, -6), (L * 0.43, -6), (L * 0.43, 1), (1, 3), (-5, 2)])
    line(edge, [(-4, -6), (L * 0.40, -6)], 0.8)
    shape((18, 21, 24), [(3, -4), (L * 0.32, -4), (L * 0.32, -1), (3, -1)])
    pen.circ(edge, *P(L * 0.31, 1), 1)

    # Open trigger bow; hands are drawn outside it.
    line(dark, [(0, 4), (12, 4), (11, 11), (3, 11), (0, 4)], 1.5)
    line(steel, [(6, 4), (5, 8)], 1)
    shape(wood, [(-6, 2), (-1, 4), (-3, 13), (-9, 12)])

    # Separate barrel and magazine tube.
    shape(dark, [(L * 0.40, -7), (L + 43, -7), (L + 44, -3), (L * 0.40, -3)])
    line(edge, [(L * 0.42, -6), (L + 41, -6)], 0.8)
    shape(steel, [(L * 0.44, 0), (L + 28, 0), (L + 28, 3), (L * 0.44, 3)])
    line(dark, [(L + 28, 0), (L + 28, 3)], 2)
    line(dark, [(L + 43, -7), (L + 43, -3)], 2)
    pen.circ((210, 176, 101), *P(L + 39, -9), 0.8)

    # Ribbed walnut pump.
    shape(dark, [(L - 13, -3), (L + 11, -3), (L + 12, 6), (L - 12, 7)])
    shape(wood, [(L - 12, -2), (L + 10, -2), (L + 10, 5), (L - 11, 6)])
    line((181, 118, 65), [(L - 11, -1), (L + 9, -1)], 0.7)
    for i in range(-8, 10, 3):
        line(wood_d, [(L + i, 0), (L + i, 5)], 0.8)


def _shotgun_hand(pen, skin, grip, fore, support=False, sleeve=None):
    """Wrapped fingers, short thumb, and a forearm that actually meets the wrist."""
    gx, gy = grip
    dx, dy = fore[0] - gx, fore[1] - gy
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    at = fore if support else grip

    def P(a, b):
        return at[0] + ux * a + px * b, at[1] + uy * a + py * b

    def shape(col, points):
        pen.poly(col, [P(a, b) for a, b in points])

    shadow, light = _dark(skin, 0.27), _lite(skin, 0.12)
    if sleeve:
        shape(_dark(sleeve, 0.25), [(-6, 11), (6, 12), (15, 110), (-13, 110)])
        shape(sleeve, [(-4, 12), (5, 12), (12, 110), (-11, 110)])
        shape(_dark(sleeve, 0.45), [(-5, 10), (6, 10), (7, 16), (-6, 16)])

    shape(shadow, [(-5, 1), (-2, -2), (4, -2), (7, 2),
                   (6, 12), (2, 16), (-4, 12), (-6, 6)])
    shape(skin, [(-4, 2), (-1, 0), (4, 0), (5, 3),
                 (4, 11), (1, 13), (-3, 10), (-4, 6)])
    for i in range(3):
        b = 5 + i * 2.3
        pen.line(shadow, [P(-2, b), P(3, b + 1)], 0.65)
    shape(light, [(-5, 2), (-3, -1), (1, -1), (3, 1), (1, 3), (-2, 4)])


def _handover_frame(t):
    """World-space positions for the moving weapon and both receiving hands."""
    present = _k(t, 250, 1200)
    transfer = _k(t, 1550, 1300)
    settle = _k(t, 2900, 850)

    x = _lerp(569, 635, transfer)
    y = _lerp(390, 373, present) + settle * 13
    angle = _lerp(-12, -3, present) + settle * 6
    scale = 0.88

    pen = _ArtPen(None, x, y, scale, angle)
    grip, fore = (-24, 0), (24, -2)
    return x, y, scale, angle, pen.point(*grip), pen.point(*fore)


def shotgun_handover(surface, t):
    """Alex presents the Fallow 12; Biribel takes it before Alex releases."""
    _meeting_background(surface, t)
    ax = 514 - 20 * _k(t, 3200, 1100)
    bx = 698
    ground = MEET_GROUND

    x, y, scale, angle, grip_world, fore_world = _handover_frame(t)
    received = _k(t, 1200, 1050)
    release = _k(t, 2850, 650)

    # Alex supports the middle while Biribel reaches for the two real grips.
    midpoint = _lerp_point(grip_world, fore_world, 0.42)
    a_reach = (
        ((midpoint[0] - ax, midpoint[1] - ground + 7),)
        if release < 0.9 else None
    )
    b_reach = (
        (
            (grip_world[0] - bx, grip_world[1] - ground),
            (fore_world[0] - bx, fore_world[1] - ground),
        )
        if received > 0.02 else None
    )

    _character(
        surface, "alex", ax, ground, 0.86, True,
        t=t, smile=0.85 - release * 0.25, reach=a_reach,
    )
    _character(
        surface, "biribel", bx, ground, 0.86, False,
        t=t, reach=b_reach,
    )

    pen = _ArtPen(surface, x, y, scale, angle)
    grip, fore = (-24, 0), (24, -2)
    _shotgun_art(pen, grip, fore)

    # Fingers are layered over the furniture, not hidden behind the whole gun.
    if received > 0.12:
        _shotgun_hand(pen, SPECS["biribel"]["skin"], grip, fore)
        _shotgun_hand(pen, SPECS["biribel"]["skin"], grip, fore, support=True)
    if release < 0.90:
        pygame.draw.circle(
            surface, _dark(SPECS["alex"]["skin"], 0.20),
            _pt((midpoint[0], midpoint[1] + 7)), 5,
        )
        pygame.draw.circle(
            surface, SPECS["alex"]["skin"],
            _pt((midpoint[0], midpoint[1] + 6)), 4,
        )

    _foreground(surface, MEET_GROUND, t)


# ---------------------------------------------------------------------------
# Shotgun insert
# ---------------------------------------------------------------------------

def gun_insert(surface, t):
    """A controlled push-in on the walnut stock, receiver, and supporting hands."""
    _insert_background(surface, t, 168)

    u = _k(t, 0, 2400)
    scale = _lerp(3.35, 3.60, u)
    # Keep the complete gun inside narrower host surfaces as well.
    scale = min(scale, (WIDTH - 100) / 143.0)
    cx = WIDTH // 2 - 15
    cy = 326 + math.sin(t * 0.0008) * 1.2
    angle = -5 + u * 1.5

    grip, fore = (-24, 0), (24, -2)
    skin = SPECS["biribel"]["skin"]
    sleeve = SPECS["biribel"]["coat"]

    old_clip = surface.get_clip()
    surface.set_clip(old_clip.clip(pygame.Rect(0, 80, WIDTH, 540)))

    # Offset silhouette gives the weapon separation from the dark landscape.
    shadow_pen = _ArtPen(surface, cx + 11, cy + 15, scale, angle)
    shadow_pen.poly(
        (19, 25, 23),
        [(-74, -10), (69, -10), (69, 7), (3, 11),
         (-20, 17), (-74, 17)],
    )

    pen = _ArtPen(surface, cx, cy, scale, angle)
    _shotgun_hand(pen, skin, grip, fore, sleeve=sleeve)
    _shotgun_hand(pen, skin, grip, fore, support=True, sleeve=sleeve)
    _shotgun_art(pen, grip, fore)
    _shotgun_hand(pen, skin, grip, fore)
    _shotgun_hand(pen, skin, grip, fore, support=True)

    surface.set_clip(old_clip)

    # Restrained identification card instead of a floating HUD over the gun.
    alpha = int(255 * _k(t, 300, 650))
    card_w = min(440, WIDTH - 112)
    card = pygame.Surface((card_w, 63), pygame.SRCALPHA)
    card.fill((19, 27, 25, int(alpha * 0.74)))
    pygame.draw.rect(card, (190, 151, 91, alpha), (0, 0, 3, 63))

    title = font_terminal.render("FALLOW 12", True, (239, 225, 190))
    title.set_alpha(alpha)
    card.blit(title, (16, 8))

    detail = font_terminal_small.render(
        "12 GAUGE  /  PUMP ACTION  /  WALNUT",
        True, (185, 190, 168),
    )
    detail.set_alpha(alpha)
    if detail.get_width() > card_w - 32:
        detail = pygame.transform.smoothscale(
            detail,
            (
                card_w - 32,
                max(1, int(detail.get_height() * (card_w - 32) / detail.get_width())),
            ),
        )
    card.blit(detail, (17, 37))
    surface.blit(card, (56, 535))
