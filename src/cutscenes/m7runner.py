"""Mission 7 beat 3: Alex rides in with the mansion plan (2D cutscene scenes).

Scene renderers take ``(surface, t_ms)`` on the full-size surface; the host adds
the letterbox, so figures stay inside y 80..620.  Registered lazily from
``missions/m7/meta.py``.
"""
import math

import pygame

from core.config import HEIGHT, WIDTH
from engine.anim import draw_character

INK = (30, 24, 22)
ORANGE = (232, 112, 30)
ORANGE_D = (176, 78, 22)
PPM_FULL = 139.0                       # px per metre at figure scale 1.0

RIDE_GROUND = 548
MEET_GROUND = 498


def _ease_out(u):
    u = max(0.0, min(1.0, u))
    return 1.0 - (1.0 - u) ** 2.2


def _k(t, start, length):
    u = max(0.0, min(1.0, (t - start) / float(length)))
    return u * u * (3.0 - 2.0 * u)


def _rng(seed):
    s = seed & 0x7FFFFFFF
    while True:
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        yield s >> 8


def _ridge(surface, base, amp, col, phase):
    pts = [(0, HEIGHT), ]
    for x in range(0, WIDTH + 25, 25):
        y = base - amp * (0.5 + 0.32 * math.sin(x * 0.0042 + phase) + 0.18 * math.sin(x * 0.011 + phase * 2.3))
        pts.append((x, int(y)))
    pts.append((WIDTH, HEIGHT))
    pygame.draw.polygon(surface, col, pts)


def _backdrop(surface, ground, farm=False):
    """Late-afternoon hills; ``ground`` is the line the figures stand on."""
    top, bot = (146, 176, 200), (238, 208, 162)
    horizon = ground - 150
    for y in range(0, horizon + 8, 8):
        u = y / float(max(1, horizon))
        surface.fill(tuple(int(a + (b - a) * u) for a, b in zip(top, bot)), (0, y, WIDTH, 8))
    for r, col in ((74, (244, 224, 176)), (48, (250, 238, 198)), (30, (255, 250, 224))):
        pygame.draw.circle(surface, col, (770, horizon - 70), r)
    _ridge(surface, ground - 150, 70, (160, 172, 172), 0.6)
    _ridge(surface, ground - 105, 52, (120, 142, 114), 2.1)
    if farm:
        _farm_far(surface, ground - 112)
    _ridge(surface, ground - 62, 38, (86, 112, 74), 4.0)
    surface.fill((78, 100, 60), (0, ground - 40, WIDTH, HEIGHT))
    surface.fill((150, 122, 86), (0, ground - 14, WIDTH, HEIGHT))
    surface.fill((120, 94, 66), (0, ground + 8, WIDTH, 3))
    surface.fill((120, 94, 66), (0, ground + 44, WIDTH, 3))
    rnd = _rng(77)
    for _ in range(46):
        x, y = next(rnd) % WIDTH, ground - 36 + next(rnd) % 24
        surface.fill((60, 82, 46), (x, y, 2, 5))
    for _ in range(40):
        x, y = next(rnd) % WIDTH, ground - 8 + next(rnd) % 120
        surface.fill((172, 144, 104), (x, y, 5, 2))


def _farm_far(surface, y):
    pygame.draw.rect(surface, (110, 82, 70), (820, y - 22, 46, 24))
    pygame.draw.polygon(surface, (132, 70, 56), [(814, y - 22), (872, y - 22), (843, y - 40)])
    pygame.draw.rect(surface, (118, 70, 60), (880, y - 34, 62, 36))
    pygame.draw.polygon(surface, (96, 52, 46), [(874, y - 34), (948, y - 34), (911, y - 54)])


def _fence(surface, y, x0=0, x1=WIDTH):
    surface.fill((92, 64, 46), (x0, y - 26, x1 - x0, 4))
    surface.fill((92, 64, 46), (x0, y - 12, x1 - x0, 4))
    for x in range(x0, x1, 78):
        surface.fill((70, 48, 36), (x, y - 38, 7, 42))


def _dust(surface, t, puffs):
    for ts, x, y, size in puffs:
        age = t - ts
        if not 0 <= age < 1100:
            continue
        u = age / 1100.0
        r = int(size * (0.55 + u))
        s = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
        pygame.draw.circle(s, (218, 190, 146, int(150 * (1 - u))), (r, r), r)
        surface.blit(s, (int(x - r), int(y - r - u * 26)))


def _line(surface, col, a, b, w):
    pygame.draw.line(surface, col, a, b, max(2, int(w)))


def _bike(surface, x, y, ppm, wheel_a, facing_right=True):
    """Side-on dirt bike, ground contact centred on x."""
    sg = 1 if facing_right else -1

    def P(mx, my):
        return (int(x + sg * mx * ppm), int(y - my * ppm))

    shade = pygame.Surface((int(2.0 * ppm), int(0.16 * ppm) + 2), pygame.SRCALPHA)
    pygame.draw.ellipse(shade, (0, 0, 0, 70), shade.get_rect())
    surface.blit(shade, (int(x - ppm), int(y - 0.06 * ppm)))
    rr = 0.33 * ppm
    for wx in (-0.62, 0.62):
        c = P(wx, 0.33)
        pygame.draw.circle(surface, INK, c, int(rr))
        pygame.draw.circle(surface, (70, 70, 74), c, int(rr * 0.84))
        pygame.draw.circle(surface, (176, 176, 182), c, int(rr * 0.6))
        pygame.draw.circle(surface, (58, 58, 62), c, int(rr * 0.5))
        for k in range(14):
            a = wheel_a + k * math.pi / 7.0
            pygame.draw.rect(surface, INK, (c[0] + math.cos(a) * rr - 1, c[1] + math.sin(a) * rr - 1, 3, 3))
        for k in range(3):
            a = wheel_a + k * math.pi / 3.0
            d = (math.cos(a) * rr * 0.5, math.sin(a) * rr * 0.5)
            _line(surface, (150, 150, 156), (c[0] - d[0], c[1] - d[1]), (c[0] + d[0], c[1] + d[1]), 1)
        pygame.draw.circle(surface, (210, 210, 214), c, max(2, int(rr * 0.12)))
    w = 0.07 * ppm
    _line(surface, (60, 62, 66), P(-0.1, 0.5), P(-0.62, 0.33), w * 1.2)
    pygame.draw.polygon(surface, (60, 62, 66), [P(-0.1, 0.5), P(-0.45, 0.85), P(0.2, 0.95), P(0.45, 1.02), P(0.25, 0.55)])
    pygame.draw.polygon(surface, (126, 128, 134), [P(-0.1, 0.42), P(0.3, 0.42), P(0.3, 0.78), P(-0.1, 0.78)])
    pygame.draw.polygon(surface, INK, [P(-0.1, 0.42), P(0.3, 0.42), P(0.3, 0.78), P(-0.1, 0.78)], 1)
    pygame.draw.polygon(surface, (90, 92, 98), [P(0.0, 0.78), P(0.24, 0.78), P(0.2, 0.9), P(0.04, 0.9)])
    _line(surface, (192, 192, 198), P(0.15, 0.45), P(-0.3, 0.4), w)
    _line(surface, (192, 192, 198), P(-0.3, 0.4), P(-0.85, 0.74), w)
    _line(surface, (150, 150, 156), P(0.5, 1.1), P(0.62, 0.33), w * 0.9)
    pygame.draw.polygon(surface, ORANGE, [P(-0.05, 0.95), P(0.5, 1.02), P(0.46, 0.82), P(-0.05, 0.82)])
    pygame.draw.polygon(surface, ORANGE_D, [P(-0.05, 0.84), P(0.46, 0.84), P(0.46, 0.82), P(-0.05, 0.82)])
    pygame.draw.polygon(surface, (34, 32, 32), [P(-0.78, 0.92), P(-0.05, 0.95), P(-0.05, 0.86), P(-0.72, 0.84)])
    pygame.draw.polygon(surface, ORANGE, [P(-0.92, 0.88), P(-0.72, 0.92), P(-0.8, 0.7)])
    pygame.draw.polygon(surface, ORANGE, [P(0.4, 0.72), P(0.85, 0.7), P(0.92, 0.6), P(0.5, 0.64)])
    pygame.draw.polygon(surface, (240, 238, 230), [P(0.55, 1.0), P(0.74, 1.0), P(0.76, 0.85), P(0.57, 0.85)])
    pygame.draw.polygon(surface, INK, [P(0.55, 1.0), P(0.74, 1.0), P(0.76, 0.85), P(0.57, 0.85)], 1)
    _line(surface, (190, 190, 196), P(0.5, 1.1), P(0.4, 1.3), w * 0.8)
    _line(surface, INK, P(0.4, 1.3), P(0.3, 1.3), w * 1.1)


def _bike_x(t):
    return -170.0 + 650.0 * _ease_out(t / 2500.0)


def _puffs():
    out = []
    for i in range(0, 41):
        ts = i * 60
        u = ts / 2500.0
        out.append((ts, _bike_x(ts) - 80, RIDE_GROUND - 6, 12 + 12 * (1 - u)))
    for i in range(7):
        out.append((2000 + i * 90, 400 + i * 12, RIDE_GROUND - 6, 20 + i * 3))
    return out


def ride(surface, t):
    """Alex comes down the track much too fast, skids in, steps off the bike."""
    _backdrop(surface, RIDE_GROUND, farm=True)
    _fence(surface, RIDE_GROUND - 40, 0, 330)
    k = 0.6
    bx = _bike_x(t)
    wheel = bx / (0.33 * PPM_FULL * k)
    for look, cx, facing in (("bodi", 836, False), ("biribel", 768, False)):
        draw_character(surface, look, cx, RIDE_GROUND - 8, k, facing, t=t)
    _dust(surface, t, _puffs())
    off = _k(t, 3000, 500)
    _bike(surface, bx, RIDE_GROUND, PPM_FULL * k, wheel)
    hop = -26.0 * math.sin(off * math.pi)
    ppm = PPM_FULL * k
    peg = 0.35 * ppm
    foot = RIDE_GROUND - peg * (1.0 - off) + hop
    rider_x = bx + 0.02 * ppm + off * 82
    draw_character(surface, "alex", rider_x, foot, k, True, t=t, moving=0.0,
                   reach=((0.38 * ppm, -0.95 * ppm),) if off < 0.05 else None)
    _bike_front_overlay(surface, bx, ppm, wheel, off)


def _bike_front_overlay(surface, bx, ppm, wheel, off):
    """Re-draw the near-side tank and fender over the rider's legs."""
    if off > 0.05:
        return

    def P(mx, my):
        return (int(bx + mx * ppm), int(RIDE_GROUND - my * ppm))

    pygame.draw.polygon(surface, ORANGE, [P(-0.05, 0.95), P(0.5, 1.02), P(0.46, 0.82), P(-0.05, 0.82)])
    pygame.draw.polygon(surface, (126, 128, 134), [P(-0.1, 0.42), P(0.3, 0.42), P(0.3, 0.78), P(-0.1, 0.78)])
    pygame.draw.polygon(surface, INK, [P(-0.1, 0.42), P(0.3, 0.42), P(0.3, 0.78), P(-0.1, 0.78)], 1)


def _meet_set(surface, t, alex_x, ext=0.0, take=0.0, holding=False):
    """``ext``: Alex's arm out with the folder; ``take``: Biribel takes it."""
    _backdrop(surface, MEET_GROUND)
    _fence(surface, MEET_GROUND - 46, 560, WIDTH)
    ppm = PPM_FULL * 0.8
    _dust(surface, t + 3000, [(2400 + i * 90, 150 + i * 14, MEET_GROUND - 6, 20 + i * 3) for i in range(7)])
    _bike(surface, 140, MEET_GROUND, ppm, 0.7)
    draw_character(surface, "bodi", 868, MEET_GROUND - 4, 0.66, False, t=t)
    given = take > 0.5
    biri = dict(prop="folder") if given else {}
    if 0.02 < take <= 0.5:
        biri = dict(reach=((-64 * take * 2, -104),))
    draw_character(surface, "biribel", 668, MEET_GROUND, 0.8, False, t=t, **biri)
    alex = dict(smile=1 if holding else 0.6)
    if holding and not given:
        alex["prop"] = "folder"
        if ext > 0.02:
            alex["reach"] = ((78 * ext, -104),)
    draw_character(surface, "alex", alex_x, MEET_GROUND, 0.8, True, t=t, **alex)


def meet(surface, t):
    """'Biribel! THE Biribel!' Alex, bike parked behind him, grins at the legend."""
    _meet_set(surface, t, 470 + 16 * _k(t, 0, 3600))


def folder(surface, t):
    """He hands over the mansion plan."""
    _meet_set(surface, t, 486 + 84 * _k(t, 0, 1000), ext=_k(t, 1000, 700) * (1.0 - _k(t, 2300, 500)),
              take=_k(t, 1900, 800), holding=True)
