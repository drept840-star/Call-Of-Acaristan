"""First-person reward cinematics for the walking sim.

Three staged pickups: the hungry kid's plate carrier and the two KRAP supply
crates. Each is drawn as a small cinematic - motivated light, a set that reads
at a glance, figure_kit character art and the shared core.hands hands.

Timeline, rewards and cutscene state live in ``missions/walking_sim.py``;
this module is presentation only.
"""
import math
import random

import pygame

from core import hands as _hands
from core.config import (HEIGHT, LETTER_H, WIDTH, draw_letterbox,
                         draw_vignette, font_dialogue, font_speaker,
                         font_terminal_small)
from core.state import STATE
from engine.anim import HEIGHT as _FIG_H, SPECS as _FIG_SPECS, draw_character
from engine.text import T as _T

GROUND_Y = 548
KID_X = 392
KID_FEET_Y = 552
KID_SCALE = 1.35
RUBBLE_X = 726
RUBBLE_Y = 528
CRATE_CX = 500
CRATE_BASE = 592

_CACHE = {}

# Frame -> one-shot sound cues, fired by missions.walking_sim's update loop.
SOUND_CUES = {
    "kid_kevlar": ((30, "footstep_wet", 0.16), (58, "footstep_wet", 0.13),
                   (86, "footstep_wet", 0.15), (98, "footstep_wet", 0.11),
                   (344, "footstep_debris", 0.22)),
    "crate_ammo": ((112, "footstep_debris", 0.16),),
    "crate_kevlar": ((114, "footstep_debris", 0.16),),
}


# ── small shared helpers ────────────────────────────────────────────────
def _clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def _mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _dark(c, t=.25):
    return _mix(c, (6, 8, 10), t)


def _lite(c, t=.25):
    return _mix(c, (255, 244, 225), t)


def _lerp(a, b, t):
    return a + (b - a) * t


def _ease_out(t):
    t = _clamp(t)
    return 1 - (1 - t) ** 3


def _ease_in_out(t):
    t = _clamp(t)
    return t * t * (3 - 2 * t)


def _i(pt):
    return int(round(pt[0])), int(round(pt[1]))


def _quad(surface, col, pts):
    pygame.draw.polygon(surface, col, [_i(p) for p in pts])


def _vgrad(surface, rect, top, bottom):
    x, y, w, h = rect
    for i in range(max(1, h)):
        pygame.draw.line(surface, _mix(top, bottom, i / max(1, h - 1)),
                         (x, y + i), (x + w - 1, y + i))


def _glow(surface, cx, cy, radius, color, alpha):
    if radius <= 0 or alpha <= 0:
        return
    glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    steps = 18
    for i in range(steps):
        t = i / steps
        r = int(radius * (1 - 0.55 * t))
        a = int(alpha * (1 - t) ** 2)
        if r > 0 and a > 0:
            pygame.draw.circle(glow, (color[0], color[1], color[2], a),
                               (radius, radius), r)
    surface.blit(glow, (cx - radius, cy - radius))


def _soft_shadow(surface, rect, alpha=90):
    x, y, w, h = rect
    shadow = pygame.Surface((max(2, w), max(2, h)), pygame.SRCALPHA)
    for i in range(5):
        t = i / 4
        pygame.draw.ellipse(
            shadow, (0, 0, 0, int(alpha * (1 - t) * 0.35)),
            (int(w * t * .12), int(h * t * .12),
             int(w * (1 - t * .24)), int(h * (1 - t * .24))))
    surface.blit(shadow, (x, y))


def _cached(key, build):
    surf = _CACHE.get(key)
    if surf is None:
        surf = build()
        _CACHE[key] = surf
    return surf


def _grain():
    def build():
        surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        rng = random.Random(8123)
        for _ in range(900):
            gx = rng.randint(0, WIDTH - 1)
            gy = rng.randint(0, HEIGHT - 1)
            a = rng.randint(9, 26)
            surf.set_at((gx, gy), (a, a, a, a) if rng.random() < .5 else (0, 0, 0, a))
        return surf
    return _cached("grain", build)


# ── set dressing ────────────────────────────────────────────────────────
def _corrugated(surface, x0, x1, y0, y1, base, seed, ribs=18):
    rng = random.Random(seed)
    pygame.draw.rect(surface, base, (x0, y0, x1 - x0, y1 - y0))
    for x in range(x0, x1, ribs):
        pygame.draw.line(surface, _dark(base, .30), (x, y0), (x, y1), 3)
        pygame.draw.line(surface, _lite(base, .10), (x + 4, y0), (x + 4, y1), 1)
    for y in (y0 + 40, y1 - 30):
        pygame.draw.line(surface, _dark(base, .34), (x0, y), (x1, y), 3)
        pygame.draw.line(surface, _lite(base, .12), (x0, y + 3), (x1, y + 3), 1)
    count = max(4, (x1 - x0) // 90)
    for i in range(count):
        rx = rng.randrange(x0 + 16, max(x0 + 17, x1 - 16))
        ry = y0 + 44 + (i % 2) * (y1 - y0 - 96)
        pygame.draw.circle(surface, _lite(base, .28), (rx, ry), 2)
        pygame.draw.circle(surface, _dark(base, .35), (rx + 1, ry + 1), 1)
    for _ in range(max(6, (x1 - x0) // 26)):
        rx = rng.randrange(x0 + 12, max(x0 + 13, x1 - 12))
        ry = rng.randrange(y0 + 10, y0 + max(11, (y1 - y0) // 2))
        ln = rng.randrange(26, 120)
        col = (base[0] + rng.randrange(-10, 26), max(0, base[1] - 16),
               max(0, base[2] - 24))
        pygame.draw.line(surface, col, (rx, ry), (rx, ry + ln), 1)
    grime = pygame.Surface(((x1 - x0), max(2, y1 - y0)), pygame.SRCALPHA)
    for i in range(0, grime.get_height(), 3):
        t = i / max(1, grime.get_height())
        pygame.draw.line(grime, (8, 10, 10, int(70 * t ** 2)),
                         (0, i), (grime.get_width(), i))
    surface.blit(grime, (x0, y0))


def _stencil(surface, text, x, y, font, color, alpha=110):
    img = font.render(text, True, color)
    img.set_alpha(alpha)
    surface.blit(img, (x, y))


def _alley_backdrop():
    def build():
        s = pygame.Surface((WIDTH, HEIGHT))
        _vgrad(s, (0, 0, WIDTH, HEIGHT), (10, 13, 17), (19, 22, 23))

        bays = ((-30, 306, (43, 48, 46), 11),
                (306, 690, (58, 47, 37), 12),
                (690, 1030, (38, 47, 53), 13))
        for x0, x1, col, seed in bays:
            _corrugated(s, x0, x1, 88, GROUND_Y, col, seed)

        # Support posts between the container panels.
        for x in (306, 690):
            pygame.draw.rect(s, (26, 28, 28), (x - 9, 88, 18, GROUND_Y - 88))
            pygame.draw.line(s, (62, 64, 60), (x - 8, 88), (x - 8, GROUND_Y), 1)
            pygame.draw.line(s, (12, 14, 14), (x + 8, 88), (x + 8, GROUND_Y), 1)

        # A closed container door on the middle bay.
        pygame.draw.rect(s, (44, 37, 31), (396, 214, 214, GROUND_Y - 214))
        pygame.draw.rect(s, (23, 21, 19), (396, 214, 214, GROUND_Y - 214), 4)
        for y in range(238, GROUND_Y, 42):
            pygame.draw.line(s, (30, 26, 23), (402, y), (604, y), 2)
            pygame.draw.line(s, (70, 58, 46), (402, y + 2), (604, y + 2), 1)
        pygame.draw.rect(s, (52, 54, 50), (594, 330, 10, 130))
        pygame.draw.circle(s, (86, 88, 80), (599, 396), 5)
        pygame.draw.line(s, (25, 23, 21), (599, 396), (577, 380), 4)

        # Roll-up hatch on the right bay.
        pygame.draw.rect(s, (24, 28, 30), (744, 150, 196, GROUND_Y - 150))
        for y in range(156, GROUND_Y, 16):
            pygame.draw.line(s, (36, 43, 46), (746, y), (938, y), 8)
            pygame.draw.line(s, (50, 58, 61), (746, y + 2), (938, y + 2), 1)
        pygame.draw.rect(s, (17, 20, 22), (744, 150, 196, GROUND_Y - 150), 4)

        # Tarp and chain dressing.
        _quad(s, (52, 55, 46), [(96, 96), (176, 96), (188, 236), (150, 262), (104, 240)])
        for i in range(4):
            x = 108 + i * 18
            pygame.draw.line(s, (37, 40, 34), (x, 100), (x + 6, 250), 2)
        pygame.draw.line(s, (78, 80, 70), (100, 120), (150, 220), 1)
        for i in range(9):
            x = 860 + int(math.sin(i * .7) * 6)
            y = 150 + i * 26
            pygame.draw.ellipse(s, (74, 76, 72), (x, y, 9, 15), 1)

        _stencil(s, "KRAP", 430, 300, font_terminal_small, (150, 142, 118), 90)
        _stencil(s, "0 7", 530, 288, font_speaker, (142, 132, 108), 80)

        # Warm sodium lamp on the left, with the cone falling across the kid.
        _glow(s, 150, 140, 190, (231, 176, 104), 26)
        pygame.draw.rect(s, (28, 28, 26), (128, 120, 46, 10), border_radius=3)
        pygame.draw.polygon(s, (146, 134, 106), [(136, 130), (166, 130), (176, 152), (126, 152)])
        pygame.draw.polygon(s, (206, 176, 120), [(140, 151), (162, 151), (168, 162), (134, 162)])
        pygame.draw.ellipse(s, (255, 232, 178), (144, 152, 15, 9))
        pygame.draw.line(s, (20, 21, 20), (150, 88), (150, 122), 2)

        cone = pygame.Surface((WIDTH, GROUND_Y), pygame.SRCALPHA)
        pygame.draw.polygon(cone, (228, 174, 106, 7),
                            [(140, 150), (176, 150), (520, GROUND_Y), (150, GROUND_Y)])
        pygame.draw.polygon(cone, (228, 174, 106, 5),
                            [(148, 150), (168, 150), (420, GROUND_Y), (230, GROUND_Y)])
        pygame.draw.polygon(cone, (228, 174, 106, 4),
                            [(158, 150), (162, 150), (330, GROUND_Y), (300, GROUND_Y)])
        s.blit(cone, (0, 0))
        pygame.draw.ellipse(s, (72, 66, 49), (236, GROUND_Y - 6, 340, 20))
        _glow(s, 406, GROUND_Y + 6, 150, (231, 176, 104), 20)

        # Asphalt.
        _vgrad(s, (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y), (33, 35, 35), (14, 15, 16))
        pygame.draw.rect(s, (45, 47, 45), (0, GROUND_Y - 8, WIDTH, 9))
        pygame.draw.line(s, (70, 71, 66), (0, GROUND_Y - 8), (WIDTH, GROUND_Y - 8), 1)
        rng = random.Random(4142)
        for _ in range(130):
            x = rng.randrange(0, WIDTH)
            y = rng.randrange(GROUND_Y + 4, HEIGHT)
            pygame.draw.line(s, rng.choice(((52, 55, 52), (40, 46, 47), (58, 56, 49))),
                             (x, y), (x + rng.randrange(3, 26), y), 1)
        for _ in range(7):
            x = rng.randrange(30, WIDTH - 60)
            y = rng.randrange(GROUND_Y + 30, HEIGHT - 20)
            pts = [(x, y)]
            for _j in range(4):
                x += rng.randrange(-24, 26)
                y += rng.randrange(-12, 16)
                pts.append((x, y))
            pygame.draw.lines(s, (18, 20, 20), False, pts, 1)

        # Puddles reflecting the lamp - the street reads wet, not dusty.
        for cx, cy, w, h, a in ((330, 596, 210, 34, 26), (760, 574, 150, 24, 20)):
            pud = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(pud, (24, 32, 36, 190), (0, 0, w, h))
            pygame.draw.ellipse(pud, (86, 88, 68, 70), (w // 4, h // 3, w // 2, h // 4), 1)
            for i in range(4):
                pygame.draw.line(pud, (128 + i * 12, 118 + i * 10, 78, a),
                                 (int(w * .28), int(h * (.34 + i * .12))),
                                 (int(w * .72), int(h * (.34 + i * .12))), 1)
            s.blit(pud, (cx - w // 2, cy - h // 2))

        # Foreground frame: a crate corner left, a barrel right, both almost black.
        for x, y, w, h, top in ((-40, 452, 190, 268, 22), (886, 470, 160, 250, 18)):
            pygame.draw.rect(s, (14, 16, 16), (x, y, w, h))
            pygame.draw.rect(s, (26, 28, 26), (x, y, w, top))
            pygame.draw.line(s, (54, 56, 50), (x + 3, y + 2), (x + w - 3, y + 2), 1)
            for k in range(1, 4):
                pygame.draw.line(s, (9, 10, 10), (x, y + top + k * 40), (x + w, y + top + k * 40), 2)
        pygame.draw.ellipse(s, (10, 11, 11), (912, 452, 108, 26))
        return s
    return _cached("alley", build)


def _warehouse_backdrop():
    def build():
        s = pygame.Surface((WIDTH, HEIGHT))
        _vgrad(s, (0, 0, WIDTH, HEIGHT), (12, 16, 18), (10, 12, 13))
        wall_bottom = 392
        _vgrad(s, (0, 60, WIDTH, wall_bottom - 60), (48, 55, 57), (33, 38, 40))
        for x in range(0, WIDTH, 164):
            pygame.draw.line(s, (27, 33, 35), (x, 60), (x, wall_bottom), 3)
            pygame.draw.line(s, (58, 65, 66), (x + 3, 60), (x + 3, wall_bottom), 1)
            for y in (120, 250):
                pygame.draw.circle(s, (66, 72, 72), (x + 10, y), 3)
                pygame.draw.circle(s, (24, 29, 30), (x + 11, y + 1), 2)

        # Roll-up door and its rail on the right.
        pygame.draw.rect(s, (26, 32, 34), (636, 96, 340, wall_bottom - 96))
        for y in range(102, wall_bottom, 18):
            pygame.draw.rect(s, (38, 45, 47), (638, y, 336, 13))
            pygame.draw.line(s, (52, 60, 62), (638, y + 1), (974, y + 1), 1)
            pygame.draw.line(s, (19, 24, 25), (638, y + 13), (974, y + 13), 1)
        pygame.draw.rect(s, (20, 25, 27), (636, 96, 340, wall_bottom - 96), 5)
        pygame.draw.rect(s, (62, 66, 62), (960, 190, 9, 140))
        pygame.draw.circle(s, (104, 106, 96), (964, 270), 5)

        # Shelving silhouette on the left keeps the eye off the edges.
        pygame.draw.rect(s, (24, 28, 29), (0, 150, 210, wall_bottom - 150))
        for y in (196, 268, 340):
            pygame.draw.rect(s, (38, 43, 43), (0, y, 210, 9))
        for i, (x, w, h) in enumerate(((16, 74, 46), (108, 66, 38), (24, 58, 40), (120, 52, 44))):
            y = (196 - h) if i < 2 else (268 - h)
            pygame.draw.rect(s, (56, 52, 42), (x, y, w, h))
            pygame.draw.rect(s, (28, 26, 22), (x, y, w, h), 2)
        pygame.draw.rect(s, (30, 36, 37), (0, 150, 210, wall_bottom - 150), 4)

        # Pipes and conduit across the upper wall.
        for y, w, col in ((96, 11, (58, 64, 64)), (122, 6, (44, 51, 52))):
            pygame.draw.line(s, col, (0, y), (WIDTH, y), w)
            pygame.draw.line(s, _lite(col, .18), (0, y - w // 3), (WIDTH, y - w // 3), 1)
        for x in (250, 520, 780):
            pygame.draw.rect(s, (36, 42, 43), (x, 88, 8, 42))

        # Bare cage lamp above the crate.
        pygame.draw.line(s, (20, 21, 20), (386, 60), (386, 142), 2)
        _glow(s, 386, 160, 150, (232, 182, 112), 24)
        pygame.draw.polygon(s, (44, 44, 40), [(366, 142), (406, 142), (412, 158), (360, 158)])
        pygame.draw.rect(s, (255, 233, 178), (374, 152, 24, 7), border_radius=2)
        pygame.draw.rect(s, (60, 58, 48), (360, 158, 52, 3))

        # Floor: concrete slabs converging on the crate.
        _vgrad(s, (0, wall_bottom, WIDTH, HEIGHT - wall_bottom), (44, 47, 47), (22, 24, 24))
        vp = (500, 300)
        for x in range(-140, WIDTH + 200, 150):
            pygame.draw.line(s, (31, 34, 34), vp, (x, HEIGHT), 2)
        for i in range(1, 6):
            y = wall_bottom + int((HEIGHT - wall_bottom) * (i / 5) ** 1.6)
            pygame.draw.line(s, (30, 33, 33), (0, y), (WIDTH, y), 2)
            pygame.draw.line(s, (55, 58, 56), (0, y + 2), (WIDTH, y + 2), 1)
        rng = random.Random(771)
        for _ in range(90):
            x = rng.randrange(0, WIDTH)
            y = rng.randrange(wall_bottom + 6, HEIGHT)
            pygame.draw.line(s, rng.choice(((52, 55, 50), (36, 41, 40), (58, 57, 50))),
                             (x, y), (x + rng.randrange(4, 30), y), 1)
        for _ in range(5):
            x = rng.randrange(120, 880)
            y = rng.randrange(wall_bottom + 20, HEIGHT - 40)
            pygame.draw.ellipse(s, (28, 30, 29), (x, y, rng.randrange(50, 120), rng.randrange(14, 30)))

        # Light shaft from the lamp onto the crate.
        shaft = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.polygon(shaft, (236, 190, 122, 14),
                            [(380, 158), (412, 158), (640, HEIGHT), (250, HEIGHT)])
        s.blit(shaft, (0, 0))
        _glow(s, 470, 548, 230, (236, 190, 122), 14)
        pygame.draw.rect(s, (16, 18, 18), (0, 0, WIDTH, 60))
        return s
    return _cached("warehouse", build)


# ── first-person hands ──────────────────────────────────────────────────
_SLEEVE = (42, 51, 43)
_SLEEVE_LITE = (70, 80, 64)


def _forearm(surface, wrist, elbow, w_wrist, w_elbow):
    dx, dy = elbow[0] - wrist[0], elbow[1] - wrist[1]
    d = math.hypot(dx, dy) or 1.0
    px, py = -dy / d, dx / d
    ux, uy = dx / d, dy / d
    quad = [(wrist[0] + px * w_wrist, wrist[1] + py * w_wrist),
            (elbow[0] + px * w_elbow, elbow[1] + py * w_elbow),
            (elbow[0] - px * w_elbow, elbow[1] - py * w_elbow),
            (wrist[0] - px * w_wrist, wrist[1] - py * w_wrist)]
    _quad(surface, _SLEEVE, quad)
    # A narrow lit edge and a darker inner edge give the sleeve a rounded read.
    _quad(surface, _SLEEVE_LITE, [
        (wrist[0] + px * w_wrist * .78, wrist[1] + py * w_wrist * .78),
        (elbow[0] + px * w_elbow * .80, elbow[1] + py * w_elbow * .80),
        (elbow[0] + px * w_elbow * .46, elbow[1] + py * w_elbow * .46),
        (wrist[0] + px * w_wrist * .50, wrist[1] + py * w_wrist * .50)])
    _quad(surface, _dark(_SLEEVE, .38), [
        (wrist[0] - px * w_wrist, wrist[1] - py * w_wrist),
        (elbow[0] - px * w_elbow, elbow[1] - py * w_elbow),
        (elbow[0] - px * w_elbow * .55, elbow[1] - py * w_elbow * .55),
        (wrist[0] - px * w_wrist * .62, wrist[1] - py * w_wrist * .62)])
    # Two cloth folds, following the forearm.
    for t0 in (.30, .58):
        w = _lerp(w_wrist, w_elbow, t0) * .8
        ca = (wrist[0] + ux * d * t0, wrist[1] + uy * d * t0)
        pygame.draw.line(surface, _dark(_SLEEVE, .30),
                         _i((ca[0] + px * w, ca[1] + py * w)),
                         _i((ca[0] - px * w, ca[1] - py * w)), 1)
    # Cuff band at the wrist.
    cu0 = (wrist[0] + ux * 6, wrist[1] + uy * 6)
    cu1 = (wrist[0] + ux * 24, wrist[1] + uy * 24)
    _quad(surface, (26, 31, 26), [
        (cu0[0] + px * w_wrist, cu0[1] + py * w_wrist),
        (cu1[0] + px * w_wrist * 1.12, cu1[1] + py * w_wrist * 1.12),
        (cu1[0] - px * w_wrist * 1.12, cu1[1] - py * w_wrist * 1.12),
        (cu0[0] - px * w_wrist, cu0[1] - py * w_wrist)])
    pygame.draw.line(surface, _SLEEVE_LITE,
                     (int(cu1[0] + px * w_wrist * 1.12), int(cu1[1] + py * w_wrist * 1.12)),
                     (int(cu1[0] - px * w_wrist * 1.12), int(cu1[1] - py * w_wrist * 1.12)), 1)


def _fist(surface, wrist, elbow, mirror, sc):
    """First-person fist seen from behind, fingers folded over a held edge.

    Local units: +y runs from the wrist toward the knuckles, index side at -x.
    """
    fx, fy = wrist[0] - elbow[0], wrist[1] - elbow[1]
    d = math.hypot(fx, fy) or 1.0
    fx, fy = fx / d, fy / d
    sx, sy = -fy * mirror, fx * mirror

    def P(x, y):
        return (wrist[0] + sc * (sx * x + fx * y), wrist[1] + sc * (sy * x + fy * y))

    skin, hi = _hands.HAND_SKIN, _hands.HAND_SKIN_HI
    mid, sh = _hands.HAND_SKIN_MID, _hands.HAND_SKIN_SH
    edge = _dark(sh, .35)
    ol = max(2, round(sc))

    def poly(col, pts, outline=False):
        pts = [_i(P(x, y)) for x, y in pts]
        pygame.draw.polygon(surface, col, pts)
        if outline:
            pygame.draw.lines(surface, edge, True, pts, ol)

    def cap(col, x, y, r):
        pygame.draw.circle(surface, col, _i(P(x, y)), max(1, round(r * sc)))

    def knuckle_y(x):
        return 24 - (x + 16) / 32 * 5

    # Folded fingers: near half lit, far half turning away from the light.
    for pass_ in ("edge", "fill"):
        for i, length in enumerate((11, 12, 11, 9)):
            x0 = -16 + i * 8
            xc = x0 + 4
            ky = knuckle_y(xc)
            end = ky + length - 4
            grow = .9 if pass_ == "edge" else 0
            col = edge if pass_ == "edge" else mid
            poly(col, ((x0 - grow + .3, ky - 2), (x0 + 8 + grow - .3, ky - 2),
                       (x0 + 8 + grow - .3, end), (x0 - grow + .3, end)))
            cap(col, xc, end, 3.7 + grow)
            if pass_ == "fill":
                poly(skin, ((x0 + .3, ky - 2), (x0 + 7.7, ky - 2),
                            (x0 + 7.7, ky + length * .5), (x0 + .3, ky + length * .5)))

    # Back of the hand, tucked under the cuff at the wrist.
    back = ((-12, -4), (12, -4), (15.5, 9), (16.5, knuckle_y(16.5)),
            (-16.5, knuckle_y(-16.5)), (-15, 9))
    poly(skin, back, outline=True)
    poly(mid, ((6, -4), (12, -4), (15.5, 9), (16.5, knuckle_y(16.5)),
               (9, knuckle_y(9)), (10, 8)))
    poly(hi, ((-14.5, 9), (-8, 10), (-6, knuckle_y(-6) - 1),
              (-16, knuckle_y(-16) - 1)))
    for i in range(4):
        xc = -12 + i * 8
        cap(hi if i < 2 else skin, xc, knuckle_y(xc) - 1.5, 2.2)

    # Thumb along the index side, its tip wrapping toward the index finger.
    a, b, c = (-11, 1), (-19, 12), (-15.5, 23)
    for col, grow in ((edge, 1.8), (skin, 0.0)):
        for (p, q, w) in ((a, b, 10), (b, c, 8)):
            pygame.draw.line(surface, col, _i(P(*p)), _i(P(*q)),
                             max(1, round((w + grow) * sc)))
        for p, w in ((a, 10), (b, 8), (c, 7)):
            cap(col, p[0], p[1], (w + grow) * .5)
    pygame.draw.line(surface, hi, _i(P(-15.5, 4)), _i(P(-20, 12)), max(1, round(sc * 1.4)))
    cap(mid, -14.5, 24.5, 2.4)


def _hand(surface, wrist, elbow, kind="grip", axis=0.0, mirror=1, sc=2.2, angle=0.0):
    if kind == "grip":
        # Fist first so the sleeve cuff covers the wrist joint.
        _fist(surface, wrist, elbow, mirror, sc)
        _forearm(surface, wrist, elbow, 13 * sc, 17 * sc)
        return
    _forearm(surface, wrist, elbow, 16 * sc * .42, 25 * sc * .42)
    if kind == "open":
        _hands.open_hand_dorsal(surface, _i(wrist), angle=angle, mirror=mirror,
                                sc=sc, spread=1.05)
    elif kind == "point":
        _hands.point_hand(surface, _i(wrist), angle=angle, mirror=mirror, sc=sc)


def _elbow_for(wrist, side, reach=1.0):
    return (wrist[0] + side * 118 * reach, wrist[1] + 330 * reach)


# ── item art ────────────────────────────────────────────────────────────
def _kevlar_art():
    def build():
        k = 3
        s = pygame.Surface((180 * k, 210 * k), pygame.SRCALPHA)
        cloth = (86, 95, 72)
        dark = (49, 56, 42)
        lite = (117, 126, 96)
        strap = (68, 75, 57)

        def P(pts):
            return [(int(x * k), int(y * k)) for x, y in pts]

        # Shoulder straps first, behind the front panel.
        for x0 in (48, 112):
            _quad(s, strap, P([(x0, 46), (x0 + 8, 4), (x0 + 30, 4), (x0 + 26, 48)]))
            _quad(s, _lite(strap, .2), P([(x0 + 6, 8), (x0 + 10, 6), (x0 + 8, 44), (x0 + 4, 42)]))
            pygame.draw.line(s, _dark(strap, .5),
                             (int((x0 + 2) * k), int(10 * k)),
                             (int((x0 + 1) * k), int(46 * k)), 2 * k)
        # Shoulder buckles.
        for x0 in (46, 110):
            pygame.draw.rect(s, (52, 53, 44), (x0 * k, 26 * k, 34 * k, 12 * k), border_radius=3 * k)
            pygame.draw.rect(s, (106, 104, 84), (x0 * k, 26 * k, 34 * k, 3 * k))
        # Cummerbund wings.
        _quad(s, dark, P([(32, 116), (6, 128), (9, 180), (36, 174)]))
        _quad(s, dark, P([(148, 116), (174, 128), (171, 180), (144, 174)]))
        for x0, sgn in ((10, 1), (168, -1)):
            pygame.draw.rect(s, (54, 54, 44), (x0 * k, 138 * k, 12 * k, 22 * k), border_radius=2 * k)
            pygame.draw.rect(s, (120, 118, 96), (x0 * k, 138 * k, 12 * k, 3 * k))

        # Front panel.
        body = P([(48, 36), (132, 36), (150, 62), (146, 188), (124, 204),
                  (56, 204), (34, 188), (30, 62)])
        _quad(s, cloth, body)
        # Panel shading: right side cool, left edge warm rim.
        _quad(s, _dark(cloth, .26), P([(104, 38), (132, 36), (150, 62), (146, 188),
                                       (124, 204), (110, 202), (126, 120)]))
        _quad(s, _lite(cloth, .14), P([(46, 38), (56, 38), (56, 200), (50, 198)]))
        pygame.draw.lines(s, _dark(cloth, .45), True, body, 3 * k)

        # Plate pocket and stitching.
        pocket = pygame.Rect(48 * k, 62 * k, 84 * k, 118 * k)
        pygame.draw.rect(s, _dark(cloth, .12), pocket, border_radius=4 * k)
        pygame.draw.rect(s, _dark(cloth, .4), pocket, 2 * k, border_radius=4 * k)
        for i in range(6):
            y = 68 + i * 19
            pygame.draw.line(s, (58, 64, 49), (52 * k, y * k), (128 * k, y * k), 1 * k)

        # MOLLE webbing.
        for row in range(4):
            y = 74 + row * 22
            for col in range(3):
                x = 56 + col * 25
                pygame.draw.rect(s, _dark(cloth, .22), (x * k, y * k, 20 * k, 8 * k), border_radius=2 * k)
                pygame.draw.line(s, _lite(cloth, .22), (x * k, (y + 1) * k),
                                 ((x + 20) * k, (y + 1) * k), 1 * k)
                pygame.draw.line(s, _dark(cloth, .5), ((x + 10) * k, y * k),
                                 ((x + 10) * k, (y + 8) * k), 1 * k)

        # Velcro ID patch and drag handle.
        pygame.draw.rect(s, (58, 64, 47), (70 * k, 48 * k, 40 * k, 12 * k), border_radius=2 * k)
        pygame.draw.rect(s, (70, 118, 196), (74 * k, 50 * k, 32 * k, 8 * k), border_radius=1 * k)
        pygame.draw.line(s, (96, 98, 80), (84 * k, 32 * k), (96 * k, 32 * k), 5 * k)

        # Damage: torn corner, frayed threads, ceramic crack.
        tear = P([(126, 176), (146, 166), (146, 188), (124, 204), (112, 202)])
        _quad(s, (18, 20, 18), tear)
        for i, (x0, y0, x1, y1) in enumerate(((126, 176, 120, 186), (134, 172, 132, 184),
                                              (140, 170, 141, 182))):
            pygame.draw.line(s, (96, 92, 70), (x0 * k, y0 * k), (x1 * k, y1 * k), 1 * k)
        pygame.draw.lines(s, (122, 126, 104), False,
                          P([(62, 84), (78, 118), (74, 140), (96, 166)]), 1 * k)
        pygame.draw.lines(s, (44, 48, 38), False,
                          P([(63, 85), (79, 119), (75, 141), (97, 167)]), 1 * k)
        for x0, y0, x1, y1 in ((58, 150, 72, 154), (92, 96, 108, 100), (64, 176, 84, 180),
                               (110, 130, 124, 134)):
            pygame.draw.line(s, (58, 62, 48), (x0 * k, y0 * k), (x1 * k, y1 * k), 2 * k)

        # Rim light: warm from the lamp on the left, cool bounce on the right.
        pygame.draw.lines(s, (214, 178, 122), False,
                          P([(48, 40), (32, 64), (34, 186)]), 3 * k)
        pygame.draw.lines(s, (120, 140, 148), False,
                          P([(148, 66), (144, 186), (122, 202)]), 2 * k)

        # Ground-in dirt at the hem.
        dirt = pygame.Surface((180 * k, 210 * k), pygame.SRCALPHA)
        for i in range(48):
            t = i / 48
            pygame.draw.line(dirt, (20, 22, 18, int(90 * t ** 2)),
                             (0, int((170 + i * .7) * k)), (180 * k, int((170 + i * .7) * k)),
                             k)
        s.blit(dirt, (0, 0))
        return pygame.transform.smoothscale(s, (180, 210))
    return _cached("kevlar", build)


def _mag_art():
    def build():
        k = 4
        s = pygame.Surface((90 * k, 170 * k), pygame.SRCALPHA)
        left, right = [], []
        for i in range(9):
            t = i / 8
            cx = 45 + 5 * math.sin(t * 2.1)
            cy = 16 + t * 124
            w = 15 - 4 * t
            left.append((cx - w, cy))
            right.append((cx + w, cy))
        body = [(int(x * k), int(y * k)) for x, y in left + right[::-1]]
        pygame.draw.polygon(s, (88, 92, 86), body)
        pygame.draw.polygon(s, (34, 36, 34), body, 2 * k)
        # Side highlight and ribbing.
        pygame.draw.lines(s, (126, 130, 118), False,
                          [(int((x - 9) * k), int(y * k)) for x, y in left[1:]], 2 * k)
        for i in range(1, 8):
            t = i / 8
            cx = 45 + 5 * math.sin(t * 2.1)
            cy = 16 + t * 124
            pygame.draw.line(s, (58, 61, 56), (int((cx - 13 + 3 * t) * k), int(cy * k)),
                             (int((cx + 13 - 3 * t) * k), int(cy * k)), 2 * k)
        for i in range(4):
            pygame.draw.circle(s, (30, 32, 30),
                               (int((45 - 8 + 3 * 0.4 + 4 * math.sin(i * .4)) * k),
                                int((58 + i * 20) * k)), 3 * k // 2)
        # Baseplate.
        pygame.draw.rect(s, (56, 58, 54), (24 * k, 134 * k, 44 * k, 14 * k), border_radius=2 * k)
        pygame.draw.rect(s, (96, 98, 90), (24 * k, 134 * k, 44 * k, 3 * k))
        # Feed lips and two brass rounds at the top.
        pygame.draw.polygon(s, (52, 54, 50),
                            [(int(33 * k), int(16 * k)), (int(57 * k), int(16 * k)),
                             (int(53 * k), int(28 * k)), (int(37 * k), int(28 * k))])
        for x in (35, 45):
            pygame.draw.rect(s, (178, 138, 56), (x * k, 6 * k, 7 * k, 12 * k), border_radius=1 * k)
            pygame.draw.rect(s, (214, 178, 94), (x * k, 6 * k, 7 * k, 3 * k), border_radius=1 * k)
            pygame.draw.circle(s, (206, 168, 84), (int((x + 3.5) * k), int(5 * k)), 4 * k)
            pygame.draw.circle(s, (150, 112, 44), (int((x + 3.5) * k), int(5 * k)), 4 * k, 1 * k)
            pygame.draw.line(s, (118, 86, 34), (int((x + 6) * k), 7 * k),
                             (int((x + 6) * k), 17 * k), 1 * k)
        # Wear.
        for x0, y0, x1, y1 in ((38, 46, 50, 50), (42, 92, 54, 96), (36, 110, 48, 114)):
            pygame.draw.line(s, (150, 152, 140), (x0 * k, y0 * k), (x1 * k, y1 * k), 2 * k)
        return pygame.transform.smoothscale(s, (90, 170))
    return _cached("mag", build)


def _item_surface(kind, width):
    art = _kevlar_art() if kind == "kevlar" else _mag_art()
    h = int(art.get_height() * width / art.get_width())
    return pygame.transform.smoothscale(art, (int(width), max(1, h)))


# ── speech + acquisition plate ──────────────────────────────────────────
def _bubble(surface, text, cx, bottom, alpha, mouth):
    if alpha <= 0:
        return
    lines = text if isinstance(text, (list, tuple)) else [text]
    imgs = [font_dialogue.render(line, True, (234, 224, 198)) for line in lines]
    tw = max(img.get_width() for img in imgs)
    th = sum(img.get_height() for img in imgs) + 4 * (len(imgs) - 1)
    pad = 14
    w, h = tw + pad * 2, th + pad
    x = int(max(12, min(WIDTH - w - 12, cx - w // 2)))
    y = int(bottom - h)
    base_x = max(x + 26, min(x + w - 26, mouth[0]))
    x0 = min(x, mouth[0] - 14) - 8
    y0 = y - 8
    x1 = max(x + w, mouth[0] + 14) + 8
    y1 = max(y + h, mouth[1]) + 8
    canvas = pygame.Surface((x1 - x0, y1 - y0), pygame.SRCALPHA)
    px, py = x - x0, y - y0
    mx, my = mouth[0] - x0, mouth[1] - y0
    bx = base_x - x0
    pygame.draw.polygon(canvas, (11, 17, 20, 230),
                        [(bx - 13, py + h - 2), (bx + 13, py + h - 2), (mx, my)])
    pygame.draw.polygon(canvas, (150, 140, 110, 200),
                        [(bx - 14, py + h - 1), (mx, my), (bx + 14, py + h - 1)], 1)
    pygame.draw.rect(canvas, (10, 15, 18, 236), (px, py, w, h), border_radius=5)
    pygame.draw.rect(canvas, (146, 136, 108, 205), (px, py, w, h), 1, border_radius=5)
    pygame.draw.rect(canvas, (220, 164, 94, 235), (px, py, 4, h))
    ty = py + (h - th) // 2
    for img in imgs:
        canvas.blit(img, (px + pad + (tw - img.get_width()) // 2, ty))
        ty += img.get_height() + 4
    canvas.set_alpha(alpha)
    surface.blit(canvas, (x0, y0))


def _plate(surface, t, start, end, title, stat, icon_kind, icon_w=44):
    if t < start:
        return
    a_in = _ease_out((t - start) / 14)
    a_out = _clamp((end - t) / 16)
    alpha = int(255 * min(a_in, a_out))
    if alpha <= 0:
        return
    title_img = font_speaker.render(title, True, (246, 210, 128))
    stat_img = font_terminal_small.render(stat, True, (122, 220, 128))
    icon = _item_surface(icon_kind, icon_w)
    pad = 16
    w = pad * 2 + icon.get_width() + 14 + max(title_img.get_width(), stat_img.get_width())
    h = max(icon.get_height(), title_img.get_height() + stat_img.get_height() + 4) + pad - 6
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(panel, (9, 14, 17, 238), (0, 0, w, h), border_radius=4)
    pygame.draw.rect(panel, (150, 140, 110, 210), (0, 0, w, h), 1, border_radius=4)
    pygame.draw.rect(panel, (224, 168, 96, 240), (0, 0, 4, h))
    pygame.draw.rect(panel, (24, 32, 34, 255), (pad, (h - icon.get_height()) // 2,
                                                 icon.get_width() + 10, icon.get_height() + 4),
                     border_radius=3)
    panel.blit(icon, (pad + 5, (h - icon.get_height()) // 2 + 2))
    tx = pad + icon.get_width() + 20
    panel.blit(title_img, (tx, (h - title_img.get_height() - stat_img.get_height() - 2) // 2))
    panel.blit(stat_img, (tx, (h - title_img.get_height() - stat_img.get_height() - 2) // 2
                          + title_img.get_height() + 2))
    panel.set_alpha(alpha)
    slide = int((1 - a_in) * 46)
    surface.blit(panel, (WIDTH // 2 - w // 2 + slide, LETTER_H + 14))


# ── the kid and the plate carrier ───────────────────────────────────────
def _draw_motes(surface, t, seed=51, count=26):
    rng = random.Random(seed)
    for i in range(count):
        x = rng.uniform(260, 760)
        y = rng.uniform(180, 520)
        sp = rng.uniform(.12, .45)
        ph = rng.uniform(0, math.tau)
        px = (x + t * sp * 1.4) % WIDTH
        py = (y + math.sin(t * .012 + ph) * 18) % 560
        a = int(34 * max(0.0, 1 - abs(px - 470) / 380))
        if a > 0:
            pygame.draw.circle(surface, (208, 196, 160, a), (int(px), int(py)), 1)


def _rubble(surface, t):
    _soft_shadow(surface, (RUBBLE_X - 110, RUBBLE_Y + 6, 220, 26), 120)
    rng = random.Random(99)
    items = []
    for _ in range(14):
        x = RUBBLE_X + rng.randint(-92, 92)
        y = RUBBLE_Y + rng.randint(-34, 16)
        w = rng.randint(16, 52)
        h = rng.randint(11, 26)
        shade = rng.randint(-12, 14)
        base = 62 + shade
        col = (base, int(base * .94), int(base * .86))
        items.append((y, x, y, w, h, col))
    items.sort()
    for _, x, y, w, h, col in items:
        pygame.draw.rect(surface, col, (x, y, w, h))
        pygame.draw.line(surface, _lite(col, .18), (x, y), (x + w, y), 1)
        pygame.draw.line(surface, _dark(col, .4), (x, y + h - 1), (x + w, y + h - 1), 1)
    # Rebar poking out of the pile.
    pygame.draw.line(surface, (24, 22, 18), (RUBBLE_X - 66, RUBBLE_Y - 52), (RUBBLE_X - 52, RUBBLE_Y - 4), 4)
    pygame.draw.line(surface, (96, 82, 62), (RUBBLE_X - 65, RUBBLE_Y - 52), (RUBBLE_X - 51, RUBBLE_Y - 4), 2)
    pygame.draw.line(surface, (24, 22, 18), (RUBBLE_X + 58, RUBBLE_Y - 40), (RUBBLE_X + 48, RUBBLE_Y - 2), 3)

    # The plate carrier is half-buried until the player takes it.
    if t < 345:
        peek = _ease_out((t - 150) / 50)
        if peek > 0:
            art = _item_surface("kevlar", 108)
            art = art.copy()
            art.set_alpha(int(255 * (0.25 + 0.75 * peek)))
            bob = 0 if getattr(STATE, "reduced_motion", False) else int(math.sin(t * .05) * 1.5)
            surface.blit(art, (RUBBLE_X - 58, RUBBLE_Y - 44 + bob))
    if 170 < t < 340:
        g = _clamp((t - 170) / 30) * _clamp((340 - t) / 40)
        if not getattr(STATE, "reduced_motion", False):
            _glow(surface, RUBBLE_X + 2, RUBBLE_Y - 18, 52, (255, 208, 108),
                  int(36 * g * (0.6 + 0.4 * math.sin(t * .16))))


def _kid_pose(t):
    enter = _ease_out((t - 24) / 74)
    x = _lerp(-46, KID_X, enter)
    moving = 1.0 if t < 100 else 0.0
    bow = 0.0
    if 44 < t < 116:
        bow = 0.42 * math.sin(_clamp((t - 44) / 72) * math.pi)
    blink = 1.0 if int(t) % 97 < 3 else 0.0
    look = 0.55 if 205 < t < 346 else 0.22
    smile = 0.18 if t > 436 else 0.0
    return x, moving, bow, blink, look, smile


def _capsule(surface, a, b, w, col):
    pygame.draw.line(surface, col, _i(a), _i(b), max(1, int(w)))
    r = max(1, int(w / 2))
    pygame.draw.circle(surface, col, _i(a), r)
    pygame.draw.circle(surface, col, _i(b), r)


def _kid_arms(surface, x, t, moving):
    """Bare, bent arms so the point at the rubble reads as a gesture.

    figure_kit's ``reach`` draws a straight tube; at this close framing that
    reads as a spear, so the kid's arms are staged by hand on the same
    shoulder anchors the rig uses.
    """
    k = KID_SCALE * _FIG_H["hungry_kid"] / 296.0
    u = k / .976  # offsets below were tuned at k = .976
    sh_y = KID_FEET_Y - 207.0 * k
    sh_x = 40 * _FIG_SPECS["hungry_kid"]["bulk"] * k
    p = _ease_out((t - 205) / 44)
    if t > 330:
        p *= 1 - _ease_in_out((t - 330) / 52)
    phase = (t * 16.0) / 900.0 * math.tau
    swing = math.sin(phase) * 6.0 * u * (moving or 0.0)
    skin = (190, 160, 130)
    shade = (150, 124, 100)
    sleeve = (135, 128, 102)

    for side in (-1, 1):
        sh = (x + side * sh_x, sh_y)
        if side > 0 and p > 0:
            el = (_lerp(x + 38 * u, x + 68 * u, p), _lerp(sh_y + 34 * u, sh_y + 28 * u, p))
            wr = (_lerp(x + 36 * u + swing, x + 110 * u, p),
                  _lerp(sh_y + 61 * u + swing * .4, sh_y + 46 * u, p))
        else:
            el = (x + side * 39 * u + swing * side, sh_y + 34 * u)
            wr = (x + side * 37 * u + swing * side, sh_y + 61 * u)
        sl = (_lerp(sh[0], el[0], .55), _lerp(sh[1], el[1], .55))
        _capsule(surface, sh, el, 10 * u, shade)
        _capsule(surface, el, wr, 8.5 * u, skin)
        _capsule(surface, sl, wr, 7.5 * u, skin)
        pygame.draw.line(surface, _lite(skin, .18), _i((el[0] + 1, el[1])),
                         _i((wr[0] + 1, wr[1])), 1)
        _capsule(surface, sh, sl, 17 * u, sleeve)
        pygame.draw.line(surface, _dark(sleeve, .3), _i((sl[0] - 6, sl[1])),
                         _i((sl[0] + 6, sl[1])), 2)
        pygame.draw.line(surface, _lite(sleeve, .18), _i((sh[0] - 4, sh[1] + 2)),
                         _i((sl[0] - 4, sl[1])), 1)
        if side > 0 and p > .45:
            ang = math.degrees(math.atan2(wr[1] - el[1], wr[0] - el[0])) + 90
            _hands.point_hand(surface, _i(wr), angle=ang, mirror=1, sc=.42 * u)
        else:
            pygame.draw.ellipse(surface, skin, (int(wr[0] - 6), int(wr[1] - 4), 12, 17))
            for fx in (-2, 1, 4):
                pygame.draw.line(surface, shade, (int(wr[0] + fx), int(wr[1] + 5)),
                                 (int(wr[0] + fx), int(wr[1] + 12)), 1)
            pygame.draw.ellipse(surface, shade, (int(wr[0] + (4 if side > 0 else -9)),
                                                int(wr[1] + 3), 5, 8))
            pygame.draw.ellipse(surface, _dark(skin, .18),
                                (int(wr[0] - 6), int(wr[1] - 4), 12, 17), 1)


def _draw_kid(surface, t):
    x, moving, bow, blink, look, smile = _kid_pose(t)
    if t < 24:
        return
    draw_character(surface, "hungry_kid", x, KID_FEET_Y, KID_SCALE,
                   facing_right=True, t=t * 16.0, fear=0.22, smile=smile,
                   blink=blink, look=look, moving=moving, bow=bow, arms=False)
    _kid_arms(surface, x, t, moving)


def _kid_mouth(x):
    return (x + 34, 320)


def _draw_kid_scene(surface, t, duration):
    surface.blit(_alley_backdrop(), (0, 0))
    kid_x = _kid_pose(t)[0]

    # Drips off the container roof and rain beyond the right edge.
    if not getattr(STATE, "reduced_motion", False):
        for i, (dx, speed) in enumerate(((238, .55), (622, .42), (872, .62))):
            dy = 92 + ((t * speed * 6 + i * 120) % 430)
            pygame.draw.line(surface, (108, 128, 134), (dx, dy), (dx - 1, dy + 6), 1)
            if dy > GROUND_Y - 12:
                r = int((dy - GROUND_Y) % 8)
                pygame.draw.ellipse(surface, (96, 112, 114),
                                    (dx - 6 + r, GROUND_Y + 4, 12 - r * 2, 3), 1)
        for i in range(14):
            rx = 900 + (i * 37) % 90
            ry = 120 + ((t * 9 + i * 43) % 400)
            pygame.draw.line(surface, (70, 88, 96, 60), (rx, ry), (rx - 3, ry + 13), 1)

    _rubble(surface, t)
    _draw_kid(surface, t)
    # Foreground crate corner frames the entrance.
    pygame.draw.rect(surface, (13, 15, 15), (-40, 600, 210, 120))
    pygame.draw.rect(surface, (24, 26, 24), (-40, 586, 210, 18))

    if 50 < t < 132:
        a = min(255, int((t - 50) * 7))
        if t > 112:
            a = max(0, int(255 - (t - 112) * 13))
        _bubble(surface, "*cough* ...hey. Hey, mister.", kid_x + 48, 248, a, _kid_mouth(kid_x))
    elif 140 < t < 222:
        a = min(255, int((t - 140) * 5))
        if t > 196:
            a = max(0, int(255 - (t - 196) * 10))
        _bubble(surface, "I haven't eaten in two days.", kid_x + 44, 248, a, _kid_mouth(kid_x))
    elif 225 < t < 312:
        a = min(255, int((t - 225) * 5))
        if t > 286:
            a = max(0, int(255 - (t - 286) * 10))
        _bubble(surface, "Over there. Behind those crates.", kid_x + 96, 252, a, _kid_mouth(kid_x))
    elif 390 < t < 484:
        a = min(255, int((t - 390) * 4))
        if t > 452:
            a = max(0, int(255 - (t - 452) * 8))
        _bubble(surface, ("Be careful, mister.", "The guards are angry tonight."),
                470, 252, a, _kid_mouth(kid_x))

    _draw_kid_pickup(surface, t)

    if t > 372:
        _plate(surface, t, 372, 512, _T("ws.kevlar_plate_acquired"), _T("ws.10_max_hp"), "kevlar")
    if 375 < t < 404:
        a = int(255 * _clamp((t - 375) / 12) * _clamp((404 - t) / 8))
        img = font_terminal_small.render(_T("ws.cracked_but_functional_better_th"),
                                         True, (196, 188, 164))
        strip = pygame.Surface((img.get_width() + 24, img.get_height() + 10), pygame.SRCALPHA)
        pygame.draw.rect(strip, (10, 15, 18, 220), strip.get_rect(), border_radius=3)
        pygame.draw.rect(strip, (120, 114, 92, 160), strip.get_rect(), 1, border_radius=3)
        strip.blit(img, (12, 5))
        strip.set_alpha(a)
        surface.blit(strip, (WIDTH // 2 - strip.get_width() // 2, 480))


def _draw_kid_pickup(surface, t):
    if t < 300:
        return
    grip = _ease_out((t - 300) / 42)
    lift = _ease_out((t - 345) / 52)
    vx = _lerp(RUBBLE_X, 598, lift)
    vy = _lerp(RUBBLE_Y - 12, 342, lift)
    width = _lerp(108, 176, lift)
    if not getattr(STATE, "reduced_motion", False) and t > 368:
        vx += math.sin((t - 368) * .075) * 3
    art = _item_surface("kevlar", int(width))
    if lift > .02:
        art = pygame.transform.rotate(art, -3.0 * lift)
    surface.blit(art, (int(vx - art.get_width() // 2), int(vy - art.get_height() // 2)))

    lw = (_lerp(268, vx - art.get_width() * .40, grip),
          _lerp(742, vy - art.get_height() * .10, grip))
    rw = (_lerp(742, vx + art.get_width() * .40, grip),
          _lerp(742, vy - art.get_height() * .06, grip))
    _hand(surface, lw, _elbow_for(lw, -1), kind="grip", axis=8, mirror=-1, sc=2.0)
    _hand(surface, rw, _elbow_for(rw, 1), kind="grip", axis=-8, mirror=1, sc=2.0)


# ── supply crates ───────────────────────────────────────────────────────
def _crate_geom(cx, base):
    w, h, d = 372, 150, 78
    top = base - h
    back = top - d
    return {
        "left": cx - w // 2, "right": cx + w // 2,
        "top": top, "back": back, "base": base,
        "bl": cx - w // 2 + 28, "br": cx + w // 2 - 28,
    }


def _lid_edge_point(g, open_t):
    return (g["left"] + (g["right"] - g["left"]) / 2,
            _lerp(g["top"], g["back"] - 176, open_t))


def _draw_crate(surface, g, open_t, contents, taking):
    left, right, top, back, base = g["left"], g["right"], g["top"], g["back"], g["base"]
    bl, br = g["bl"], g["br"]

    _soft_shadow(surface, (left - 22, base - 4, right - left + 44, 30), 130)

    opening = [(bl, back), (br, back), (right, top), (left, top)]
    # Interior: back wall band, then floor, then the two side walls.
    _quad(surface, (30, 26, 21), [(bl, back), (br, back), (br - 6, back + 26), (bl + 6, back + 26)])
    _quad(surface, (37, 32, 25), opening)
    _quad(surface, (46, 40, 30), [(bl + 6, back + 26), (br - 6, back + 26), (right - 12, top), (left + 12, top)])
    _quad(surface, (28, 24, 20), [(bl, back), (bl + 8, back + 4), (left + 14, top), (left, top)])
    _quad(surface, (24, 21, 18), [(br, back), (br - 8, back + 4), (right - 14, top), (right, top)])

    # Packing paper and straw on the floor.
    rng = random.Random(313)
    paper = [(left + 26, top - 8), (left + 150, top - 30), (right - 60, top - 6),
             (right - 26, top - 20), (right - 40, top + 16), (left + 60, top + 10)]
    pygame.draw.polygon(surface, (62, 58, 47), paper)
    pygame.draw.polygon(surface, (78, 72, 56), paper, 1)
    for _ in range(26):
        x = rng.randrange(left + 34, right - 34)
        y = rng.randrange(top - 34, top + 8)
        pygame.draw.line(surface, rng.choice(((112, 102, 70), (86, 78, 56), (132, 120, 82))),
                         (x, y), (x + rng.randrange(-9, 10), y + rng.randrange(-4, 5)), 1)

    # Contents stand in the crate: their tops sit below the back rim so the
    # lid always hides them until it swings clear.
    if not taking:
        if contents == "ammo":
            mag = _item_surface("mag", 52)
            for mx, ang in ((left + 132, -10), (left + 190, 3), (left + 244, -4)):
                img = pygame.transform.rotate(mag, ang)
                surface.blit(img, (mx - img.get_width() // 2, back + 8))
            for i in range(7):
                x = left + 116 + i * 10
                y = top - 12 + (i % 3) * 2
                pygame.draw.rect(surface, (176, 138, 60), (x, y, 7, 3))
                pygame.draw.circle(surface, (214, 182, 96), (x + 7, y + 1), 1)
        else:
            vest = _item_surface("kevlar", 104)
            surface.blit(vest, (left + 134, back + 6))

    # Front face.
    front = [(left, top), (right, top), (right, base), (left, base)]
    _quad(surface, (82, 62, 41), front)
    for x in range(left + 8, right, 46):
        pygame.draw.line(surface, (66, 49, 33), (x, top + 4), (x, base - 4), 3)
        pygame.draw.line(surface, (104, 80, 52), (x + 4, top + 4), (x + 4, base - 4), 1)
    _quad(surface, (58, 44, 30), [(left, top), (left + 34, top + 8), (left + 34, base - 8), (left, base)])
    _quad(surface, (66, 50, 33), [(right, top), (right - 34, top + 8), (right - 34, base - 8), (right, base)])
    pygame.draw.rect(surface, (54, 58, 54), (left + 44, top + 6, 12, base - top - 12))
    pygame.draw.rect(surface, (96, 100, 90), (left + 46, top + 6, 3, base - top - 12))
    pygame.draw.rect(surface, (54, 58, 54), (right - 56, top + 6, 12, base - top - 12))
    pygame.draw.rect(surface, (96, 100, 90), (right - 54, top + 6, 3, base - top - 12))
    pygame.draw.rect(surface, (33, 28, 22), (left, top, right - left, 7))
    pygame.draw.line(surface, (118, 92, 58), (left + 2, base - 6), (right - 2, base - 6), 3)
    # Corner plates and rivets.
    for x, y in ((left + 2, top + 2), (right - 26, top + 2), (left + 2, base - 26), (right - 26, base - 26)):
        pygame.draw.rect(surface, (47, 51, 47), (x, y, 24, 24))
        pygame.draw.rect(surface, (90, 94, 84), (x, y, 24, 24), 1)
        pygame.draw.circle(surface, (120, 122, 106), (x + 12, y + 12), 2)
    # Latch and stencil.
    pygame.draw.rect(surface, (52, 56, 52), (left + 176, top - 2, 22, 18), border_radius=2)
    pygame.draw.rect(surface, (110, 112, 100), (left + 178, top, 18, 4))
    _stencil(surface, "KRAP / SUPPLY", left + 116, base - 38, font_terminal_small,
             (176, 156, 108), 150)
    pygame.draw.line(surface, (150, 132, 94), (left + 116, base - 20), (left + 246, base - 20), 1)
    # Rim light on the near edge makes the box sit in the lamp pool.
    pygame.draw.line(surface, (158, 126, 84), (left + 2, top + 1), (right - 2, top + 1), 2)
    pygame.draw.line(surface, (40, 31, 22), (left + 2, top + 3), (right - 2, top + 3), 2)
    pygame.draw.line(surface, (146, 116, 78), (left + 1, top + 6), (left + 1, base - 2), 2)
    pygame.draw.line(surface, (92, 104, 104), (right - 1, top + 6), (right - 1, base - 2), 1)

    # Lid, hinged on the back rim.
    lid_far_y = _lerp(top, back - 176, open_t)
    far_l = _lerp(left, bl + 4, open_t)
    far_r = _lerp(right, br - 4, open_t)
    lid = [(bl, back), (br, back), (far_r, lid_far_y), (far_l, lid_far_y)]
    _quad(surface, (63, 47, 33), lid)
    for i in range(1, 5):
        t = i / 5
        pygame.draw.line(surface, (58, 43, 29),
                         (int(_lerp(bl, far_l, t)), int(_lerp(back, lid_far_y, t))),
                         (int(_lerp(br, far_r, t)), int(_lerp(back, lid_far_y, t))), 2)
    if open_t > .25:
        for fx in (.2, .5, .8):
            xh = _lerp(bl, br, fx)
            xf = _lerp(far_l, far_r, fx)
            pygame.draw.line(surface, (52, 40, 28), (int(xh), back),
                             (int(xf), int(lid_far_y)), 7)
            pygame.draw.line(surface, (92, 72, 48), (int(xh) + 2, back),
                             (int(xf) + 2, int(lid_far_y)), 2)
        pygame.draw.line(surface, (60, 46, 31), _i((bl + 26, back - 8)),
                         _i((br - 26, lid_far_y + 14)), 5)
        _stencil(surface, "KRAP / 04", int(_lerp(bl, far_l, .18)) + 16,
                 int(_lerp(back, lid_far_y, .30)), font_terminal_small, (150, 128, 92), 90)
    _quad(surface, (49, 43, 34), [(bl, back), (br, back), (br, back + 10), (bl, back + 10)])
    pygame.draw.polygon(surface, (30, 25, 20), [_i(p) for p in lid], 3)
    for x in (bl + 26, br - 26):
        pygame.draw.line(surface, (48, 52, 48), (x, back), (x, int(lid_far_y) + 10), 6)
        pygame.draw.circle(surface, (104, 106, 94), (x, int(lid_far_y) + 12), 2)


def _draw_crate_scene(surface, t, duration, contents):
    surface.blit(_warehouse_backdrop(), (0, 0))
    _draw_motes(surface, t, seed=57, count=30)
    if not getattr(STATE, "reduced_motion", False):
        _glow(surface, 470, 520, 240, (236, 190, 122), int(10 + 6 * math.sin(t * .04)))

    g = _crate_geom(CRATE_CX, CRATE_BASE)
    open_t = _ease_out((t - 34) / 76)
    taking = t > 110
    _draw_crate(surface, g, open_t, contents, taking)

    # Item and hands.
    grab = _ease_out((t - 110) / 48)
    item_x = _lerp(CRATE_CX, 522, grab)
    item_y0 = g["back"] + 64
    item_y = _lerp(item_y0, 336, grab)
    item_w = _lerp(106 if contents == "kevlar" else 64,
                   160 if contents == "kevlar" else 96, grab)
    item_h = item_w * (210 / 180 if contents == "kevlar" else 170 / 90)
    if t >= 110:
        art = _item_surface(contents, int(item_w))
        if contents == "ammo":
            art = pygame.transform.rotate(art, int(_lerp(-6, 8, grab)))
        surface.blit(art, (int(item_x - art.get_width() // 2),
                           int(item_y - art.get_height() // 2)))

    # Left hand: rests on the near rim, then steadies the item when both are needed.
    entry_l = _ease_out((t - 16) / 36)
    lx = _lerp(304, g["left"] + 92, entry_l)
    ly = _lerp(742, g["top"] + 8, entry_l)
    if t > 108 and contents == "kevlar":
        mx = _ease_out((t - 108) / 40)
        lx = _lerp(lx, item_x - item_w * .40, mx)
        ly = _lerp(ly, item_y - item_h * .08, mx)
    _hand(surface, (lx, ly), _elbow_for((lx, ly), -1), kind="grip", axis=0,
          mirror=-1, sc=2.1)

    # Right hand: opens the lid, then takes the item.
    entry_r = _ease_out((t - 22) / 36)
    lid_pt = _lid_edge_point(g, open_t)
    rx = _lerp(742, lid_pt[0] + 20, entry_r)
    ry = _lerp(742, lid_pt[1] + 46, entry_r)  # folded fingers land on the lid edge
    if t > 106:
        rel = _ease_out((t - 106) / 28)
        if contents == "kevlar":
            rx = _lerp(rx, item_x + item_w * .40, rel)
            ry = _lerp(ry, item_y - item_h * .05, rel)
        else:
            rx = _lerp(rx, item_x, rel)
            ry = _lerp(ry, item_y + item_h * .22, rel)
    _hand(surface, (rx, ry), _elbow_for((rx, ry), 1), kind="grip",
          axis=90 if t < 106 else (12 if contents == "kevlar" else 90),
          mirror=1, sc=2.2)

    if contents == "ammo":
        if t > 136:
            _plate(surface, t, 136, duration - 10, _T("ws.magazine_acquired"),
                   _T("ws.1_starting_mag"), "mag")
    else:
        if t > 136:
            _plate(surface, t, 136, duration - 10, _T("ws.kevlar_salvaged"),
                   _T("ws.10_max_hp"), "kevlar")


# ── entry point ─────────────────────────────────────────────────────────
def _finish(surface, t, duration):
    # Cool grade, grain and vignette sell the cutscene as film, not HUD.
    def build_tint():
        tint = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        tint.fill((14, 22, 34, 12))
        return tint
    surface.blit(_cached("tint", build_tint), (0, 0))
    grain = _grain()
    ox, oy = int(t * .9) % 7, int(t * 1.3) % 7
    surface.blit(grain, (ox, oy))
    draw_vignette(surface, strength=180)
    draw_letterbox(surface)
    footer = font_terminal_small.render(_T("ws.first_person_interaction"), True, (96, 106, 116))
    surface.blit(footer, (WIDTH // 2 - footer.get_width() // 2, HEIGHT - LETTER_H + 20))

    fade = 0
    if t < 24:
        fade = int(255 * (1 - t / 24))
    elif t > duration - 26:
        fade = int(255 * _clamp((t - (duration - 26)) / 26))
    if fade > 0:
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, max(0, min(255, fade))))
        surface.blit(veil, (0, 0))


def draw(surface, cut):
    scene = cut.get("scene", "")
    t = cut.get("timer", 0.0)
    duration = cut.get("duration", 180)
    if scene == "kid_kevlar":
        _draw_kid_scene(surface, t, duration)
    else:
        _draw_crate_scene(surface, t, duration,
                          "ammo" if scene == "crate_ammo" else "kevlar")
    _finish(surface, t, duration)
