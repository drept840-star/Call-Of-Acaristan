"""Split from cutscenes.py - see cutscenes.py (shim) for the map."""
# cutscenes package
# ------------------------------------------------------------

"""Cutscene visuals and dialogue: character drawings, scene backgrounds, shot lists."""
import math
import random
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import pygame

from core import render_util
from core.config import (C_KRAP_BLUE, C_KRAP_UNIFORM, C_ORANGE, HEIGHT, SCENE_BOT, SCENE_H, SCENE_TOP, WIDTH, draw_sky_gradient, font_dialogue, font_location_sub, font_prompt, font_speaker, font_terminal, font_terminal_small)

from cutscenes.cast import draw_biribel, draw_vasile
from cutscenes.figure_kit import draw_character as _fk_draw
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
from engine.text import T as _T  # RPE6 Phase 4 text table

def draw_factory(surface, t):
    ground_y = SCENE_BOT - 60
    draw_sky_gradient(surface, (18, 20, 26), (28, 24, 22))
    fac_left = 150
    fac_right = 850
    fac_top = SCENE_TOP + 80
    fac_h = ground_y - fac_top
    pygame.draw.rect(
        surface, (22, 26, 32), (fac_left, fac_top, fac_right - fac_left, fac_h)
    )
    for i in range(fac_left, fac_right, 12):
        shade = 28 + (i % 24 > 12) * 4
        pygame.draw.line(
            surface, (shade, shade + 2, shade + 6), (i, fac_top), (i, ground_y), 1
        )
    for wx in range(fac_left + 40, fac_right - 40, 90):
        for wy_off in range(0, 3):
            wy = fac_top + 30 + wy_off * 70
            is_lit = (wx // 90 + wy_off) % 3 != 0
            win_c = (55, 50, 32) if is_lit else (18, 20, 24)
            pygame.draw.rect(surface, win_c, (wx, wy, 50, 45))
            pygame.draw.rect(surface, (18, 20, 26), (wx, wy, 50, 45), 2)
            if is_lit:
                glow = pygame.Surface((54, 49), pygame.SRCALPHA)
                glow.fill((60, 55, 30, 25))
                surface.blit(glow, (wx - 2, wy - 2))
    for chx, chh in [(620, 130), (680, 160), (750, 110)]:
        pygame.draw.rect(surface, (26, 28, 34), (chx, fac_top - chh, 28, chh))
        for pi in range(4):
            poff = (t // 20 + pi * 15) % 80
            palpha = max(0, 70 - poff)
            pr = 15 + pi * 4
            psurf = pygame.Surface((pr * 2, pr * 2), pygame.SRCALPHA)
            pygame.draw.circle(psurf, (35, 38, 44, palpha), (pr, pr), pr)
            surface.blit(psurf, (chx + 14 - pr, fac_top - chh - 20 - poff))
    pygame.draw.rect(surface, (15, 16, 18), (0, ground_y, WIDTH, SCENE_BOT - ground_y))
def draw_oil_rig(surface, x, ground_y, t, scale=1.0, burning=False, lights_only=False):
    s = scale
    base_w = int(120 * s)
    base_h = int(20 * s)
    deck_y = ground_y - int(60 * s)
    tower_h = int(100 * s)
    tx = x
    ty = deck_y - tower_h
    if not lights_only:
        leg_col = (45, 48, 55)
        deck_col = (60, 65, 75)
        tower_col = (55, 60, 70)
        for lx in (-base_w // 2 + 10, base_w // 2 - 10):
            pygame.draw.line(
                surface,
                leg_col,
                (x + lx, deck_y + base_h),
                (x + lx, ground_y + 20),
                int(4 * s),
            )
        pygame.draw.rect(surface, deck_col, (x - base_w // 2, deck_y, base_w, base_h))
        pygame.draw.line(
            surface, tower_col, (tx - int(20 * s), deck_y), (tx, ty), int(3 * s)
        )
        pygame.draw.line(
            surface, tower_col, (tx + int(20 * s), deck_y), (tx, ty), int(3 * s)
        )
        for i in range(4):
            ratio = i / 4.0
            ly = deck_y - int(tower_h * ratio)
            lw = int(20 * s * (1 - ratio))
            pygame.draw.line(
                surface, tower_col, (tx - lw, ly), (tx + lw, ly), int(2 * s)
            )
        pygame.draw.circle(surface, (120, 100, 80), (tx, ty), int(4 * s))
    else:
        if (t // 18) % 2 == 0:
            pygame.draw.circle(surface, (255, 50, 50), (tx, ty), int(6 * s))
            beacon_glow = pygame.Surface((int(36 * s), int(36 * s)), pygame.SRCALPHA)
            pygame.draw.circle(
                beacon_glow, (255, 50, 50, 75), (int(18 * s), int(18 * s)), int(18 * s)
            )
            surface.blit(beacon_glow, (tx - int(18 * s), ty - int(18 * s)))
        for lx_off in range(-base_w // 2 + 15, base_w // 2 - 10, int(25 * s)):
            pygame.draw.circle(
                surface,
                (255, 200, 100),
                (x + lx_off, deck_y + base_h // 2),
                int(2.5 * s),
            )
            deck_glow = pygame.Surface((int(12 * s), int(12 * s)), pygame.SRCALPHA)
            pygame.draw.circle(
                deck_glow, (255, 200, 100, 50), (int(6 * s), int(6 * s)), int(6 * s)
            )
            surface.blit(
                deck_glow, (x + lx_off - int(6 * s), deck_y + base_h // 2 - int(6 * s))
            )
        spot_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        beam_len = 220 * s
        phase_offset = x * 0.13
        beam_angle = math.sin(t * 0.02 + phase_offset) * 0.5 - math.pi / 2
        end_cx = x + math.cos(beam_angle) * beam_len
        end_cy = deck_y + math.sin(beam_angle) * beam_len
        perp_angle = beam_angle + math.pi / 2
        cone_half_w = 30 * s
        bx1 = end_cx - math.cos(perp_angle) * cone_half_w
        by1 = end_cy - math.sin(perp_angle) * cone_half_w
        bx2 = end_cx + math.cos(perp_angle) * cone_half_w
        by2 = end_cy + math.sin(perp_angle) * cone_half_w
        pygame.draw.polygon(
            spot_surf, (255, 255, 220, 20), [(x, deck_y), (bx1, by1), (bx2, by2)]
        )
        surface.blit(spot_surf, (0, 0))
        if burning:
            fire_x = x + int(math.sin(t * 0.01) * 5)
            fire_y = deck_y - int(5 * s)
            for ri, (rc, ra) in enumerate([(255, 180), (220, 130), (160, 80)]):
                rr = max(2, int((15 - ri * 4) * s))
                pygame.draw.circle(
                    surface,
                    (rc, max(0, 80 - ri * 20), 10, ra),
                    (fire_x, fire_y - ri * int(5 * s)),
                    rr,
                )
            for pi in range(5):
                poff = (t // 15 + pi * 12) % 80
                palpha = max(0, 100 - poff)
                pr = int((10 + pi * 3) * s)
                psurf = pygame.Surface((pr * 2, pr * 2), pygame.SRCALPHA)
                pygame.draw.circle(psurf, (40, 40, 45, palpha), (pr, pr), pr)
                surface.blit(
                    psurf,
                    (fire_x - pr + _rng_legacy.randint(-3, 3), deck_y - int(40 * s) - poff),
                )
def draw_propaganda_poster(surface, x, y, w, h, defaced=False):
    pygame.draw.rect(surface, (200, 180, 140), (x, y, w, h))
    pygame.draw.rect(surface, (60, 50, 40), (x, y, w, h), 2)
    face_x = x + w // 2
    face_y = y + h // 3
    face_r = min(w, h) // 6
    pygame.draw.circle(surface, (40, 30, 25), (face_x, face_y), face_r)
    pygame.draw.rect(
        surface, (40, 30, 25), (face_x - face_r, face_y, face_r * 2, face_r * 2)
    )
    for i in range(3):
        ty = y + h * 2 // 3 + i * 8
        pygame.draw.rect(surface, (60, 50, 40), (x + 10, ty, w - 20, 4))
    pygame.draw.rect(surface, (160, 30, 30), (x, y, w, 12))
    if defaced:
        pygame.draw.circle(
            surface, (15, 15, 15), (face_x - 4, face_y - 2), face_r + 2, 3
        )
        pygame.draw.line(
            surface, (15, 15, 15), (x + 4, y + 4), (x + w - 4, y + h - 4), 3
        )
        tag = font_terminal_small.render(_T("route12.maru"), True, (15, 15, 15))
        surface.blit(tag, (x + w // 2 - tag.get_width() // 2, y + h - 18))
def draw_mag_graffiti(surface, x, y, scale=1.0):
    s = scale
    pts = [
        (x, y - int(8 * s)),
        (x - int(6 * s), y - int(12 * s)),
        (x - int(10 * s), y - int(2 * s)),
        (x - int(8 * s), y + int(8 * s)),
        (x, y + int(12 * s)),
        (x + int(8 * s), y + int(8 * s)),
        (x + int(10 * s), y - int(2 * s)),
        (x + int(6 * s), y - int(12 * s)),
    ]
    pygame.draw.polygon(surface, (15, 15, 15), pts)
    pygame.draw.circle(
        surface, (180, 30, 30), (x - int(3 * s), y - int(2 * s)), int(1 * s)
    )
    pygame.draw.circle(
        surface, (180, 30, 30), (x + int(3 * s), y - int(2 * s)), int(1 * s)
    )
_VAN_GLOWS = {}
_VAN_BAKE = {}
_VAN_RAIN = None


def _van_glow(radius, col, alpha, squash=1.0):
    """Cached radial glow (SRCALPHA), optionally squashed vertically."""
    key = (radius, col, alpha, squash)
    g = _VAN_GLOWS.get(key)
    if g is None:
        h = max(2, int(radius * 2 * squash))
        g = pygame.Surface((radius * 2, h), pygame.SRCALPHA)
        for i in range(radius, 0, -2):
            a = int(alpha * (1.0 - i / radius) ** 1.5)
            pygame.draw.ellipse(
                g, (col[0], col[1], col[2], a),
                (radius - i, h // 2 - int(i * squash), i * 2, max(2, int(i * 2 * squash))),
            )
        _VAN_GLOWS[key] = g
    return g


def _van_exterior_bake():
    """Sky, wet road and the two scrolling skyline strips, painted once."""
    b = _VAN_BAKE.get("ext")
    if b is not None:
        return b
    road_y = SCENE_BOT - 150
    base = pygame.Surface((WIDTH, HEIGHT))
    base.fill((6, 7, 9))
    draw_sky_gradient(base, (9, 11, 17), (30, 21, 24))
    haze = pygame.Surface((WIDTH, 90), pygame.SRCALPHA)
    for i in range(90):
        haze.fill((120, 78, 52, int(34 * (i / 90.0) ** 2)), (0, i, WIDTH, 1))
    base.blit(haze, (0, road_y - 120))
    pygame.draw.rect(base, (10, 12, 15), (0, road_y, WIDTH, SCENE_BOT - road_y))
    pygame.draw.rect(base, (30, 32, 36), (0, road_y, WIDTH, 5))
    pygame.draw.rect(base, (14, 15, 18), (0, road_y + 5, WIDTH, 9))
    for y in range(road_y + 22, SCENE_BOT, 22):
        pygame.draw.line(base, (19, 25, 33), (0, y), (WIDTH, y), 1)
    sheen = pygame.Surface((WIDTH, SCENE_BOT - road_y), pygame.SRCALPHA)
    for i in range(sheen.get_height()):
        sheen.fill((70, 90, 120, int(26 * i / sheen.get_height())), (0, i, WIDTH, 1))
    base.blit(sheen, (0, road_y))
    period = 20 * 56
    far = pygame.Surface((period, 130), pygame.SRCALPHA)
    rng = random.Random(91)
    for i in range(20):
        bx, bh = i * 56, rng.randint(34, 108)
        col = rng.choice([(13, 15, 20), (16, 17, 22), (18, 16, 18)])
        pygame.draw.rect(far, col, (bx, 130 - bh, 50, bh))
        pygame.draw.rect(far, (22, 24, 30), (bx, 130 - bh, 50, 2))
        if rng.random() > 0.6:
            pygame.draw.line(far, (26, 28, 34), (bx + 25, 130 - bh), (bx + 25, 130 - bh - 14), 1)
        for wy in range(130 - bh + 12, 126, 17):
            for wx in (bx + 9, bx + 26):
                if rng.random() > 0.62:
                    c = rng.choice([(150, 115, 60), (104, 90, 62), (86, 110, 128)])
                    pygame.draw.rect(far, c, (wx, wy, 5, 6))
    near_p = 760
    near = pygame.Surface((near_p, 190), pygame.SRCALPHA)
    pygame.draw.rect(near, (7, 8, 10), (0, 150, near_p, 40))
    for fx in range(0, near_p, 12):
        pygame.draw.line(near, (11, 12, 15), (fx, 128), (fx, 160), 1)
    pygame.draw.line(near, (13, 14, 17), (0, 130), (near_p, 130), 2)
    pygame.draw.line(near, (13, 14, 17), (0, 150), (near_p, 150), 1)
    for cx2, cw, ch, cc in ((70, 120, 62, (36, 22, 20)), (200, 120, 62, (18, 26, 38)),
                            (200, 120, 124, (30, 30, 34)), (470, 120, 62, (20, 30, 24))):
        pygame.draw.rect(near, cc, (cx2, 150 - ch, cw, ch))
        pygame.draw.rect(near, (6, 7, 9), (cx2, 150 - ch, cw, ch), 2)
        for rib in range(cx2 + 8, cx2 + cw - 4, 10):
            pygame.draw.line(near, (6, 7, 9), (rib, 150 - ch + 3), (rib, 148), 1)
    pygame.draw.rect(near, (9, 10, 12), (356, 52, 5, 98))
    pygame.draw.rect(near, (9, 10, 12), (336, 50, 30, 5))
    pygame.draw.rect(near, (176, 140, 84), (334, 53, 12, 4))
    _VAN_BAKE["ext"] = b = (base, far, near)
    return b


def _van_rain_cache():
    global _VAN_RAIN
    if _VAN_RAIN is None:
        rng = random.Random(44)
        _VAN_RAIN = [(rng.randint(0, WIDTH), rng.randint(0, SCENE_H), rng.randint(25, 70), rng.randint(14, 26))
                     for _ in range(130)]
    return _VAN_RAIN


def _van_wheel(surface, wx, wy, t, r=22):
    pygame.draw.circle(surface, (4, 5, 7), (wx, wy), r)
    pygame.draw.circle(surface, (22, 24, 28), (wx, wy), r, 2)
    pygame.draw.circle(surface, (42, 46, 52), (wx, wy), r - 9)
    ang = t * 0.021
    for k in range(5):
        a = ang + k * (math.tau / 5)
        pygame.draw.line(surface, (20, 22, 26), (wx, wy),
                         (wx + int(math.cos(a) * (r - 10)), wy + int(math.sin(a) * (r - 10))), 2)
    pygame.draw.circle(surface, (15, 16, 18), (wx, wy), 4)
    pygame.draw.circle(surface, (84, 90, 98), (wx, wy), 2)




def draw_van_exterior(surface, t):
    """Moving-van establishing shot: parallax skyline, rain in the headlights, spinning wheels."""
    base, far, near = _van_exterior_bake()
    road_y = SCENE_BOT - 150
    surface.blit(base, (0, SCENE_TOP), (0, SCENE_TOP, WIDTH, SCENE_H))
    off_far = int(t * 0.03) % far.get_width()
    for x0 in (-off_far, far.get_width() - off_far):
        surface.blit(far, (x0, road_y - 130 + 4))
    off_near = int(t * 0.2) % near.get_width()
    lamp_x = []
    for x0 in (-off_near, near.get_width() - off_near):
        surface.blit(near, (x0, road_y - 150 + 2))
        lamp_x.append(x0 + 340)
    for lx in lamp_x:
        if -120 < lx < WIDTH + 120:
            surface.blit(_van_glow(70, (255, 190, 110), 70), (lx - 70, road_y - 150 + 56 - 70))
            surface.blit(_van_glow(90, (255, 190, 110), 46, 0.22), (lx - 90, road_y + 36))
    for i in range(12):
        rx = (i * 97 - int(t * 0.12)) % WIDTH
        rw = 30 + (i % 3) * 20
        col = [(40, 75, 110), (90, 65, 45), (120, 45, 35)][i % 3]
        refl = pygame.Surface((rw, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(refl, (*col, 35), (0, 0, rw, 8))
        surface.blit(refl, (rx, road_y + 25 + (i % 5) * 16))
    dash_off = int(t * 0.5) % 150
    for dx in range(-150, WIDTH + 150, 150):
        pygame.draw.rect(surface, (52, 54, 58), (dx - dash_off, road_y + 118, 74, 4))
    # Wheels are pinned to the road; only the body rides the suspension.
    bob = int(round(math.sin(t * 0.011) * 1.2 + math.sin(t * 0.027) * 0.6))
    van_x = WIDTH // 2 - 170
    wheel_cy = road_y + 50                 # wheel centre (fixed)
    ground_y = wheel_cy + 22               # tyre contact line (fixed)
    van_y = wheel_cy - 72 + bob
    # Wide soft ground shadow, then a hard dark contact patch under every tyre.
    shadow = pygame.Surface((380, 44), pygame.SRCALPHA)
    render_util.soft_shadow(shadow, (0, 6, 380, 32), 170)
    render_util.soft_shadow(shadow, (30, 14, 320, 18), 120)
    surface.blit(shadow, (van_x - 34, ground_y - 22))
    for wcx in (van_x + 62, van_x + 235):
        contact = pygame.Surface((76, 14), pygame.SRCALPHA)
        pygame.draw.ellipse(contact, (0, 0, 0, 215), (0, 0, 76, 14))
        pygame.draw.ellipse(contact, (0, 0, 0, 255), (14, 3, 48, 8))
        surface.blit(contact, (wcx - 38, ground_y - 8))
    puffs = pygame.Surface((220, 90), pygame.SRCALPHA)
    for i in range(6):
        age = ((t / 520.0) + i / 6.0) % 1.0
        pygame.draw.circle(puffs, (96, 102, 112, int(80 * (1 - age) ** 1.6)),
                           (int(212 - age * 200), int(70 - age * 30)), int(4 + age * 15))
    surface.blit(puffs, (van_x - 222, van_y + 16))
    spray = pygame.Surface((120, 50), pygame.SRCALPHA)
    for i in range(9):
        age = ((t / 380.0) + i / 9.0) % 1.0
        pygame.draw.circle(spray, (120, 140, 170, int(70 * (1 - age))),
                           (int(112 - age * 100), int(44 - math.sin(age * 3.1) * 26)), 2 + int(age * 3))
    surface.blit(spray, (van_x - 70, van_y + 50))
    pygame.draw.rect(surface, (15, 17, 20), (van_x, van_y, 310, 72), border_radius=5)
    pygame.draw.rect(surface, (22, 25, 30), (van_x + 2, van_y + 46, 306, 24), border_radius=4)
    pygame.draw.rect(surface, (40, 46, 54), (van_x, van_y, 310, 72), 2, border_radius=5)
    pygame.draw.line(surface, (72, 84, 98), (van_x + 8, van_y + 2), (van_x + 224, van_y + 2), 1)
    cab = [(van_x + 230, van_y), (van_x + 290, van_y + 12), (van_x + 310, van_y + 45), (van_x + 230, van_y + 45)]
    pygame.draw.polygon(surface, (18, 22, 27), cab)
    pygame.draw.polygon(surface, (42, 48, 56), cab, 1)
    pygame.draw.rect(surface, (22, 26, 31), (van_x + 24, van_y - 5, 170, 5))
    for rx in (40, 100, 160):
        pygame.draw.line(surface, (46, 52, 60), (van_x + rx, van_y - 5), (van_x + rx, van_y), 2)
    pygame.draw.rect(surface, (26, 30, 36), (van_x + 120, van_y - 11, 34, 7), border_radius=2)
    sway = math.sin(t * 0.008) * 5
    pygame.draw.line(surface, (60, 66, 74), (van_x + 214, van_y), (van_x + 206 + int(sway), van_y - 52), 1)
    pygame.draw.circle(surface, (170, 40, 36) if (t // 500) % 2 == 0 else (60, 20, 20),
                       (van_x + 206 + int(sway), van_y - 52), 2)
    pygame.draw.rect(surface, (22, 34, 46), (van_x + 236, van_y + 10, 42, 26), border_radius=2)
    pygame.draw.circle(surface, (9, 11, 14), (van_x + 256, van_y + 22), 7)
    pygame.draw.rect(surface, (9, 11, 14), (van_x + 247, van_y + 27, 20, 9))
    pygame.draw.rect(surface, (18, 28, 38), (van_x + 90, van_y + 12, 48, 24), border_radius=2)
    pygame.draw.rect(surface, (9, 11, 14), (van_x + 105, van_y + 24, 15, 12))
    pygame.draw.circle(surface, (9, 11, 14), (van_x + 112, van_y + 21), 6)
    glow = int(26 + 8 * math.sin(t * 0.004))
    surface.blit(_van_glow(40, (160, 60, 50), glow), (van_x + 114 - 40, van_y + 24 - 40))
    pygame.draw.line(surface, (80, 100, 120), (van_x + 240, van_y + 13), (van_x + 272, van_y + 13), 1)
    pygame.draw.line(surface, (60, 74, 90), (van_x + 94, van_y + 14), (van_x + 120, van_y + 14), 1)
    pygame.draw.rect(surface, (11, 13, 16), (van_x + 150, van_y + 8, 74, 56), 1)
    pygame.draw.line(surface, (11, 13, 16), (van_x + 186, van_y + 8), (van_x + 186, van_y + 64), 1)
    pygame.draw.rect(surface, (70, 78, 88), (van_x + 160, van_y + 33, 12, 3))
    pygame.draw.rect(surface, (20, 23, 28), (van_x + 280, van_y + 20, 9, 14), border_radius=2)
    pygame.draw.rect(surface, C_KRAP_BLUE, (van_x + 24, van_y + 22, 185, 7))
    pygame.draw.rect(surface, (220, 220, 225), (van_x + 24, van_y + 30, 185, 2))
    krap = font_terminal_small.render(_T("route12.krap"), True, (190, 210, 230))
    surface.blit(krap, (van_x + 38, van_y + 40))
    for sx2, sy2 in ((60, 52), (92, 57), (176, 54), (246, 50)):
        pygame.draw.rect(surface, (58, 40, 30), (van_x + sx2, van_y + sy2, 6, 2))
    for wx in (van_x + 62, van_x + 235):
        # Arch cut into the body (moves with it), wheel stays planted.
        pygame.draw.circle(surface, (6, 7, 9), (wx, van_y + 72), 27)
        _van_wheel(surface, wx, wheel_cy, t)
        pygame.draw.rect(surface, (8, 9, 11), (wx - 34, van_y + 66, 4, 16))
        # Tyre squash where rubber meets wet asphalt, and a thin specular edge.
        pygame.draw.ellipse(surface, (3, 4, 5), (wx - 20, ground_y - 4, 40, 7))
        pygame.draw.line(surface, (46, 56, 70), (wx - 12, ground_y + 3), (wx + 12, ground_y + 3), 1)
    # Wet-road reflection: the lower body mirrored under the contact line, fading out.
    rh = 46
    ref = surface.subsurface((van_x, van_y + 72 - rh + 22, 310, rh)).copy()
    ref = pygame.transform.flip(ref, False, True)
    fade = _VAN_BAKE.get("refl_fade")
    if fade is None:
        fade = pygame.Surface((310, rh), pygame.SRCALPHA)
        for yy in range(rh):
            fade.fill((255, 255, 255, int(70 * (1.0 - yy / rh) ** 1.4)), (0, yy, 310, 1))
        _VAN_BAKE["refl_fade"] = fade
    ref = ref.convert_alpha()
    ref.blit(fade, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(ref, (van_x, ground_y + 2))
    brake = 150 if (t // 1800) % 5 != 4 else 230
    pygame.draw.rect(surface, (200, 44, 38), (van_x - 4, van_y + 28, 6, 14))
    surface.blit(_van_glow(36, (255, 40, 30), brake), (van_x - 36, van_y + 35 - 36))
    surface.blit(_van_glow(70, (255, 40, 30), 70, 0.3), (van_x - 74, ground_y - 6))
    pygame.draw.ellipse(surface, (232, 224, 160), (van_x + 304, van_y + 24, 12, 10))
    beam = pygame.Surface((330, 120), pygame.SRCALPHA)
    pygame.draw.polygon(beam, (225, 215, 160, 34), [(0, 55), (326, 8), (326, 112), (0, 64)])
    pygame.draw.polygon(beam, (240, 232, 190, 22), [(0, 58), (326, 40), (326, 90), (0, 62)])
    surface.blit(beam, (van_x + 310, van_y - 6))
    surface.blit(_van_glow(40, (255, 240, 190), 120), (van_x + 310 - 40, van_y + 29 - 40))
    surface.blit(_van_glow(150, (210, 200, 150), 70, 0.2), (van_x + 380, ground_y - 14))
    rain = pygame.Surface((WIDTH, SCENE_H), pygame.SRCALPHA)
    for rx0, ry0, ra, rl in _van_rain_cache():
        rx = (rx0 - int(t * 1.9)) % WIDTH
        ry = (ry0 + int(t * 5.0)) % SCENE_H
        pygame.draw.line(rain, (135, 155, 190, ra), (rx, ry), (rx - 5, ry + rl), 1)
        if van_x + 310 < rx < van_x + 640 and van_y - SCENE_TOP < ry < van_y - SCENE_TOP + 110:
            pygame.draw.line(rain, (230, 232, 215, min(255, ra * 2)), (rx, ry), (rx - 6, ry + rl + 4), 1)
    surface.blit(rain, (0, SCENE_TOP))
    tag = font_location_sub.render(_T("route12.acaristan_city_slum_district"), True, (130, 150, 170))
    bg = pygame.Surface((tag.get_width() + 24, tag.get_height() + 10), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 150))
    surface.blit(bg, (42, SCENE_TOP + 24))
    surface.blit(tag, (54, SCENE_TOP + 29))


def _van_interior_bake():
    """Static cabin (walls, board, benches, crates, floor), painted once. No windows or people."""
    b = _VAN_BAKE.get("int")
    if b is not None:
        return b
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((8, 8, 10))
    floor_y = SCENE_BOT - 95
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_H)
        pygame.draw.line(surf, (int(17 + p * 10), int(13 + p * 7), int(14 + p * 8)), (0, y), (WIDTH, y))
    pygame.draw.rect(surf, (11, 10, 12), (0, SCENE_TOP, WIDTH, 36))
    pygame.draw.line(surf, (34, 28, 30), (0, SCENE_TOP + 36), (WIDTH, SCENE_TOP + 36), 2)
    for x in range(80, WIDTH - 80, 96):
        pygame.draw.line(surf, (26, 22, 24), (x, SCENE_TOP + 38), (x, floor_y), 1)
        pygame.draw.line(surf, (11, 10, 12), (x + 1, SCENE_TOP + 38), (x + 1, floor_y), 1)
        for ry in range(SCENE_TOP + 56, floor_y - 6, 52):
            pygame.draw.circle(surf, (44, 38, 38), (x - 4, ry), 1)
            pygame.draw.circle(surf, (44, 38, 38), (x + 5, ry), 1)
    for y in range(SCENE_TOP + 62, floor_y, 48):
        pygame.draw.line(surf, (22, 18, 20), (40, y), (WIDTH - 40, y), 1)
    pygame.draw.rect(surf, (28, 24, 26), (60, SCENE_TOP + 44, WIDTH - 120, floor_y - SCENE_TOP - 54), 2)
    pygame.draw.line(surf, (36, 30, 32), (WIDTH // 2, SCENE_TOP + 44), (WIDTH // 2, floor_y), 2)
    pygame.draw.rect(surf, (52, 46, 42), (WIDTH // 2 - 30, SCENE_TOP + 170, 60, 7), border_radius=2)
    pygame.draw.rect(surf, (20, 18, 18), (WIDTH // 2 - 30, SCENE_TOP + 177, 60, 3))
    win_x, win_y, win_w, win_h = WIDTH - 310, SCENE_TOP + 70, 220, 180
    pygame.draw.rect(surf, (42, 34, 32), (win_x - 8, win_y - 8, win_w + 16, win_h + 16), 6)
    pygame.draw.rect(surf, (22, 18, 18), (win_x - 8, win_y - 8, win_w + 16, win_h + 16), 1)
    pygame.draw.line(surf, (30, 26, 26), (win_x + win_w // 2, win_y), (win_x + win_w // 2, win_y + win_h), 4)
    bx, by, bw, bh = WIDTH - 560, SCENE_TOP + 82, 170, 140
    pygame.draw.rect(surf, (45, 38, 32), (bx - 5, by - 5, bw + 10, bh + 10))
    pygame.draw.rect(surf, (10, 14, 16), (bx, by, bw, bh))
    for gx in range(bx + 17, bx + bw, 17):
        pygame.draw.line(surf, (18, 26, 28), (gx, by), (gx, by + bh), 1)
    for gy in range(by + 17, by + bh, 17):
        pygame.draw.line(surf, (18, 26, 28), (bx, gy), (bx + bw, gy), 1)
    pygame.draw.line(surf, (30, 52, 66), (bx + 8, by + 126), (bx + bw - 8, by + 12), 1)
    pts = [(bx + 22, by + 100), (bx + 48, by + 82), (bx + 68, by + 92), (bx + 96, by + 58),
           (bx + 120, by + 66), (bx + 140, by + 32)]
    cols = [(120, 70, 60), (95, 105, 135), (130, 95, 45)]
    for i in range(len(pts) - 1):
        pygame.draw.line(surf, cols[i % 3], pts[i], pts[i + 1], 3)
    for p in pts[:-1]:
        pygame.draw.circle(surf, (170, 160, 130), p, 2)
    pygame.draw.circle(surf, C_ORANGE, pts[-1], 5, 1)
    hdr = font_terminal_small.render("SLUM DIST. // ROUTE 4", True, (86, 118, 130))
    surf.blit(hdr, (bx + 6, by - 20))
    pygame.draw.rect(surf, (24, 22, 22), (46, SCENE_TOP + 140, 250, 8))
    pygame.draw.rect(surf, (14, 16, 18), (60, SCENE_TOP + 98, 94, 42), border_radius=2)
    pygame.draw.rect(surf, (52, 58, 62), (60, SCENE_TOP + 98, 94, 42), 1, border_radius=2)
    pygame.draw.circle(surf, (28, 32, 36), (82, SCENE_TOP + 120), 11)
    pygame.draw.circle(surf, (70, 76, 82), (82, SCENE_TOP + 120), 11, 1)
    pygame.draw.line(surf, (84, 90, 96), (82, SCENE_TOP + 120), (88, SCENE_TOP + 112), 1)
    pygame.draw.rect(surf, (8, 18, 12), (108, SCENE_TOP + 106, 38, 14))
    pygame.draw.rect(surf, (32, 30, 28), (170, SCENE_TOP + 112, 30, 28), border_radius=3)
    pygame.draw.rect(surf, (52, 48, 42), (170, SCENE_TOP + 112, 30, 28), 1, border_radius=3)
    pygame.draw.rect(surf, (10, 10, 12), (0, floor_y, WIDTH, SCENE_BOT - floor_y))
    pygame.draw.line(surf, (30, 26, 26), (0, floor_y), (WIDTH, floor_y), 2)
    for sx in range(0, WIDTH, 32):
        pygame.draw.line(surf, (18, 18, 20), (sx, floor_y), (sx + 12, SCENE_BOT), 1)
    for sy in range(floor_y + 22, SCENE_BOT, 22):
        pygame.draw.line(surf, (14, 14, 16), (0, sy), (WIDTH, sy), 1)
    rng = random.Random(61)
    for _ in range(26):
        x, y = rng.randint(10, WIDTH - 30), rng.randint(floor_y + 6, SCENE_BOT - 6)
        pygame.draw.line(surf, (22, 22, 24), (x, y), (x + rng.randint(6, 18), y), 1)
    for bxx, bww in ((40, 260), (WIDTH - 360, 300)):
        pygame.draw.rect(surf, (18, 16, 16), (bxx, floor_y - 35, bww, 48), border_radius=4)
        pygame.draw.rect(surf, (32, 27, 25), (bxx, floor_y - 35, bww, 8), border_radius=3)
        pygame.draw.line(surf, (48, 42, 38), (bxx + 4, floor_y - 34), (bxx + bww - 4, floor_y - 34), 1)
        for sx in range(bxx + 40, bxx + bww - 20, 70):
            pygame.draw.rect(surf, (36, 32, 28), (sx, floor_y - 35, 6, 48))
    pygame.draw.rect(surf, (55, 58, 48), (325, floor_y - 52, 86, 46), border_radius=3)
    pygame.draw.rect(surf, (85, 88, 72), (325, floor_y - 52, 86, 46), 2, border_radius=3)
    pygame.draw.line(surf, (40, 42, 34), (325, floor_y - 30), (411, floor_y - 30), 1)
    surf.blit(font_terminal_small.render(_T("route12.krap"), True, C_KRAP_BLUE), (350, floor_y - 46))
    pygame.draw.rect(surf, (70, 54, 38), (430, floor_y - 44, 72, 38), border_radius=2)
    pygame.draw.rect(surf, (45, 32, 22), (430, floor_y - 44, 72, 38), 2, border_radius=2)
    pygame.draw.rect(surf, (62, 48, 34), (344, floor_y - 74, 52, 22), border_radius=2)
    pygame.draw.rect(surf, (36, 28, 20), (344, floor_y - 74, 52, 22), 2, border_radius=2)
    pygame.draw.ellipse(surf, (28, 30, 26), (512, floor_y - 18, 34, 14), 3)
    pygame.draw.rect(surf, (5, 6, 8), (WIDTH // 2 - 70, SCENE_BOT - 112, 140, 28), border_radius=3)
    pygame.draw.line(surf, (12, 14, 16), (WIDTH // 2 - 52, SCENE_BOT - 98), (WIDTH // 2 + 50, SCENE_BOT - 98), 3)
    pygame.draw.circle(surf, (18, 20, 24), (WIDTH // 2 + 58, SCENE_BOT - 98), 6)
    _VAN_BAKE["int"] = b = surf
    return b


def draw_van_interior(surface, t):
    """KRAP van cabin: swinging lamp, moving city in the window, live radio, breathing cast."""
    base = _van_interior_bake()
    surface.blit(base, (0, SCENE_TOP), (0, SCENE_TOP, WIDTH, SCENE_H))
    floor_y = SCENE_BOT - 95
    win_x, win_y, win_w, win_h = WIDTH - 310, SCENE_TOP + 70, 220, 180
    pygame.draw.rect(surface, (7, 9, 13), (win_x, win_y, win_w, win_h))
    sky = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
    for i in range(0, win_h, 6):
        sky.fill((60, 40, 36, int(40 * i / win_h)), (0, i, win_w, 6))
    surface.blit(sky, (win_x, win_y))
    city = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
    for i in range(9):
        bx = (i * 41 - int(t * 0.045)) % (win_w + 40) - 20
        bh = 36 + (i * 37) % 52
        pygame.draw.rect(city, (11, 12, 16), (bx, win_h - 40 - bh, 26, bh))
    surface.blit(city, (win_x, win_y))
    for i in range(16):
        lx = win_x + ((i * 41 - int(t * 0.7)) % win_w)
        ly = win_y + 20 + (i * 23) % (win_h - 40)
        col = [(150, 80, 55), (80, 95, 130), (170, 130, 55)][i % 3]
        pygame.draw.rect(surface, col, (lx, ly, 22, 4))
    flare_x = win_x + win_w - ((t * 0.35) % (win_w + 160)) + 40
    if win_x - 60 < flare_x < win_x + win_w + 60:
        surface.blit(_van_glow(60, (255, 190, 110), 90), (int(flare_x) - 60, win_y + 60))
    for i in range(18):
        rx = win_x + ((i * 29 + int(t * 1.1)) % win_w)
        ry = win_y + ((i * 47 + int(t * 2.8)) % win_h)
        pygame.draw.line(surface, (140, 150, 175), (rx, ry), (rx - 2, ry + 18), 1)
    refl = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
    pygame.draw.polygon(refl, (200, 210, 230, 16), [(0, 0), (70, 0), (20, win_h), (0, win_h)])
    surface.blit(refl, (win_x, win_y))
    sw = math.sin(t * 0.0023) * 22 + math.sin(t * 0.0071) * 4
    pivot = (WIDTH // 2, SCENE_TOP + 36)
    lamp_x = int(pivot[0] + sw)
    lamp_y = SCENE_TOP + 66
    pygame.draw.line(surface, (36, 32, 32), pivot, (lamp_x, lamp_y), 2)
    flick = 0.82 if (t // 90) % 37 == 5 else 1.0
    surface.blit(_van_glow(230, (255, 150, 90), int(58 * flick), 0.62),
                 (lamp_x - 230, lamp_y + 8 - int(230 * 0.62)))
    surface.blit(_van_glow(120, (255, 120, 80), int(48 * flick)), (lamp_x - 120, lamp_y - 120))
    pygame.draw.rect(surface, (30, 26, 26), (lamp_x - 22, lamp_y - 6, 44, 12), border_radius=4)
    pygame.draw.rect(surface, (205, 60, 52) if flick == 1.0 else (120, 36, 34),
                     (lamp_x - 17, lamp_y, 34, 8), border_radius=3)
    for k in range(4):
        on = ((t // (160 + k * 40)) + k) % 3 == 0
        pygame.draw.circle(surface, (80, 220, 110) if on else (22, 40, 26), (66 + k * 8, SCENE_TOP + 132), 2)
    for k in range(6):
        h = 2 + int(abs(math.sin(t * 0.011 + k * 1.3)) * 9)
        pygame.draw.rect(surface, (40, 170, 80), (112 + k * 6, SCENE_TOP + 120 - h, 4, h))
    bx, by = WIDTH - 560, SCENE_TOP + 82
    seg = [(bx + 22, by + 100), (bx + 48, by + 82), (bx + 68, by + 92), (bx + 96, by + 58),
           (bx + 120, by + 66), (bx + 140, by + 32)]
    f = ((t / 3200.0) % 1.0) * (len(seg) - 1)
    i0 = min(len(seg) - 2, int(f))
    fx = seg[i0][0] + (seg[i0 + 1][0] - seg[i0][0]) * (f - i0)
    fy = seg[i0][1] + (seg[i0 + 1][1] - seg[i0][1]) * (f - i0)
    surface.blit(_van_glow(14, (255, 170, 80), 140), (int(fx) - 14, int(fy) - 14))
    pygame.draw.circle(surface, (255, 214, 140), (int(fx), int(fy)), 3)
    pulse = int(3 + 2 * math.sin(t * 0.006))
    pygame.draw.circle(surface, C_ORANGE, seg[-1], 5 + pulse // 2, 1)
    jost = math.sin(t * 0.009) * 1.2
    blink_v = 1.0 if (t // 90) % 41 == 3 else 0.0
    blink_b = 1.0 if (t // 90) % 53 == 7 else 0.0
    glow_v = pygame.Surface((160, 220), pygame.SRCALPHA)
    pygame.draw.ellipse(glow_v, (100, 160, 220, 28), (0, 20, 160, 180))
    surface.blit(glow_v, (75, floor_y - 215))
    glow_b = pygame.Surface((180, 240), pygame.SRCALPHA)
    pygame.draw.ellipse(glow_b, (180, 190, 200, 18), (0, 20, 180, 200))
    surface.blit(glow_b, (WIDTH // 2 + 50, floor_y - 230))
    _fk_draw(surface, "vasile", 160 + jost, floor_y + 2, 0.72, True, t=t, blink=blink_v)
    _fk_draw(surface, "biribel", WIDTH // 2 + 150 - jost * 0.7, floor_y + 2, 0.76, False, True,
             t=t, blink=blink_b)
    for i in range(14):
        dx = lamp_x - 170 + (i * 53 + int(t * 0.012 * (1 + i % 3))) % 340
        dy = SCENE_TOP + 90 + (i * 37 + int(t * 0.01)) % 250
        pygame.draw.circle(surface, (150, 120, 100), (int(dx), int(dy)), 1)
    red = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    red.fill((60, 10, 12, 22))
    surface.blit(red, (0, 0))
# ── Handoff insert-shot helpers (van cutscene) ──
def _ease_cutscene(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3
def _lerp_cutscene(a, b, t):
    return a + (b - a) * t
def _ca(v):
    """Clamp an alpha value to the valid pygame range 0..255."""
    return max(0, min(255, int(v)))
def _draw_handoff_pistol(surface, cx, cy, scale=1.0, angle=-8):
    s = scale
    w, h = int(150 * s), int(80 * s)
    gun = pygame.Surface((w, h), pygame.SRCALPHA)
    def R(x, y, ww, hh):
        return pygame.Rect(int(x * s), int(y * s), int(ww * s), int(hh * s))
    pygame.draw.rect(gun, (52, 56, 62), R(32, 24, 72, 15), border_radius=int(3 * s))
    pygame.draw.rect(gun, (18, 20, 24), R(32, 24, 72, 15), int(2 * s), border_radius=int(3 * s))
    pygame.draw.rect(gun, (70, 74, 80), R(98, 28, 24, 7), border_radius=int(2 * s))
    pygame.draw.circle(gun, (8, 8, 10), (int(123 * s), int(31 * s)), int(4 * s))
    pygame.draw.rect(gun, (28, 30, 34), R(36, 38, 58, 13), border_radius=int(3 * s))
    grip_pts = [(int(48 * s), int(48 * s)), (int(74 * s), int(48 * s)),
                (int(82 * s), int(73 * s)), (int(56 * s), int(75 * s))]
    pygame.draw.polygon(gun, (22, 23, 25), grip_pts)
    pygame.draw.polygon(gun, (10, 11, 13), grip_pts, int(1 * s))
    pygame.draw.circle(gun, (16, 17, 19), (int(83 * s), int(49 * s)), int(8 * s), int(2 * s))
    pygame.draw.line(gun, (105, 112, 120), (int(38 * s), int(27 * s)), (int(93 * s), int(27 * s)), int(1 * s))
    pygame.draw.circle(gun, (180, 35, 35), (int(82 * s), int(22 * s)), int(2 * s))
    rot = pygame.transform.rotate(gun, angle)
    rect = rot.get_rect(center=(int(cx), int(cy)))
    surface.blit(rot, rect)
def _draw_handoff_molotov(surface, cx, cy, scale=1.0, angle=0):
    """Unlit molotov: glass bottle, amber fuel, rag stuffed in the neck."""
    s = scale
    w, h = int(64 * s), int(150 * s)
    bottle = pygame.Surface((w, h), pygame.SRCALPHA)
    bx = w // 2
    rag_col = (196, 178, 130)
    rag_dark = (150, 132, 92)
    pygame.draw.polygon(bottle, rag_col, [
        (bx - int(4 * s), int(18 * s)),
        (bx - int(16 * s), int(34 * s)),
        (bx - int(11 * s), int(40 * s)),
        (bx - int(1 * s), int(26 * s)),
    ])
    pygame.draw.line(bottle, rag_dark,
                     (bx - int(6 * s), int(22 * s)),
                     (bx - int(14 * s), int(36 * s)), max(1, int(1 * s)))
    pygame.draw.ellipse(bottle, rag_col,
                        (bx - int(8 * s), int(10 * s), int(16 * s), int(12 * s)))
    pygame.draw.ellipse(bottle, rag_dark,
                        (bx - int(8 * s), int(10 * s), int(16 * s), int(12 * s)), max(1, int(1 * s)))
    glass = (96, 66, 30)
    glass_dark = (52, 36, 18)
    pygame.draw.rect(bottle, glass_dark,
                     (bx - int(7 * s), int(18 * s), int(14 * s), int(26 * s)),
                     border_radius=int(3 * s))
    pygame.draw.rect(bottle, glass,
                     (bx - int(5 * s), int(20 * s), int(10 * s), int(23 * s)),
                     border_radius=int(3 * s))
    pygame.draw.polygon(bottle, glass_dark, [
        (bx - int(7 * s), int(42 * s)),
        (bx + int(7 * s), int(42 * s)),
        (bx + int(20 * s), int(62 * s)),
        (bx - int(20 * s), int(62 * s)),
    ])
    pygame.draw.polygon(bottle, glass, [
        (bx - int(5 * s), int(44 * s)),
        (bx + int(5 * s), int(44 * s)),
        (bx + int(17 * s), int(62 * s)),
        (bx - int(17 * s), int(62 * s)),
    ])
    body_rect = pygame.Rect(bx - int(20 * s), int(60 * s), int(40 * s), int(78 * s))
    pygame.draw.rect(bottle, glass_dark, body_rect, border_radius=int(8 * s))
    inner = body_rect.inflate(int(-6 * s), int(-6 * s))
    pygame.draw.rect(bottle, glass, inner, border_radius=int(7 * s))
    fuel_h = int(inner.height * 0.65)
    fuel_rect = pygame.Rect(inner.x, inner.bottom - fuel_h, inner.width, fuel_h)
    pygame.draw.rect(bottle, (212, 116, 30), fuel_rect, border_radius=int(6 * s))
    pygame.draw.rect(bottle, (245, 160, 55),
                     (fuel_rect.x, fuel_rect.y, fuel_rect.width, int(4 * s)))
    pygame.draw.line(bottle, (255, 220, 160),
                     (inner.x + int(4 * s), inner.y + int(6 * s)),
                     (inner.x + int(4 * s), inner.bottom - int(8 * s)), max(1, int(2 * s)))
    pygame.draw.rect(bottle, (60, 60, 64),
                     (bx - int(7 * s), int(30 * s), int(14 * s), int(5 * s)))
    rot = pygame.transform.rotate(bottle, angle)
    rect = rot.get_rect(center=(int(cx), int(cy)))
    surface.blit(rot, rect)
def draw_van_handoff(surface, t, item="weapon"):
    draw_van_interior(surface, t)
    dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 105))
    surface.blit(dim, (0, 0))
    panel_w = 650
    panel_h = 355
    panel_x = WIDTH // 2 - panel_w // 2
    panel_y = SCENE_TOP + 42
    panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
    shadow = pygame.Surface((panel_w + 28, panel_h + 28), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 145), shadow.get_rect(), border_radius=8)
    surface.blit(shadow, (panel_x + 14, panel_y + 14))
    pygame.draw.rect(surface, (9, 10, 13), panel, border_radius=6)
    pygame.draw.rect(surface, (52, 62, 74), panel, 2, border_radius=6)
    pygame.draw.rect(surface, C_KRAP_BLUE, (panel_x, panel_y, 5, panel_h), border_radius=4)
    for x in range(panel_x + 35, panel.right - 35, 80):
        pygame.draw.line(surface, (22, 24, 29), (x, panel_y + 10), (x, panel.bottom - 10), 1)
    for y in range(panel_y + 45, panel.bottom - 20, 42):
        pygame.draw.line(surface, (18, 20, 25), (panel_x + 15, y), (panel.right - 15, y), 1)
    label = "LOADOUT TRANSFER // SERVICE SIDEARM" if item == "weapon" else "LOADOUT TRANSFER // INCENDIARY PACKAGE"
    tag = font_terminal_small.render(label, True, (110, 150, 180))
    surface.blit(tag, (panel_x + 18, panel_y + 12))
    rec = font_terminal_small.render(_T("route12.rec"), True, (220, 55, 45))
    surface.blit(rec, (panel.right - rec.get_width() - 22, panel_y + 12))
    if (_now_ms() // 400) % 2 == 0:
        pygame.draw.circle(surface, (220, 55, 45), (panel.right - rec.get_width() - 34, panel_y + 19), 4)
    table_y = panel_y + 250
    table_pts = [(panel_x + 110, table_y), (panel.right - 110, table_y),
                 (panel.right - 55, panel.bottom - 28), (panel_x + 55, panel.bottom - 28)]
    pygame.draw.polygon(surface, (48, 36, 24), table_pts)
    pygame.draw.polygon(surface, (80, 60, 38), table_pts, 2)
    for yy in range(table_y + 18, panel.bottom - 35, 22):
        pygame.draw.line(surface, (35, 25, 17), (panel_x + 75, yy), (panel.right - 75, yy), 1)
    crate_lbl = font_terminal_small.render(_T("route12.krap_field_kit"), True, (130, 110, 80))
    if item == "weapon":
        surface.blit(crate_lbl, (WIDTH // 2 - crate_lbl.get_width() // 2, panel.bottom - 58))
    p = _ease_cutscene((t - 250) / 1100.0)
    idle = math.sin(t * 0.006) * 2
    if item == "weapon":
        hand_y = panel_y + 202 + idle
        left_start = (panel_x + 90, panel_y + 190)
        right_start = (panel.right - 90, panel_y + 206)
        left_hand_x = _lerp_cutscene(panel_x + 230, WIDTH // 2 - 35, p)
        left_hand_y = _lerp_cutscene(panel_y + 190, hand_y, p)
        right_hand_x = _lerp_cutscene(panel.right - 205, WIDTH // 2 + 38, p)
        right_hand_y = _lerp_cutscene(panel_y + 215, hand_y + 5, p)
        glow = pygame.Surface((300, 210), pygame.SRCALPHA)
        for r in range(130, 0, -8):
            a = int(22 * (1 - r / 130))
            pygame.draw.ellipse(glow, (120, 160, 220, a), (150 - r, 105 - r // 2, r * 2, r))
        surface.blit(glow, (WIDTH // 2 - 150, panel_y + 95))
        pygame.draw.line(surface, C_KRAP_UNIFORM, left_start, (left_hand_x, left_hand_y), 22)
        pygame.draw.line(surface, (25, 30, 38), left_start, (left_hand_x, left_hand_y), 3)
        pygame.draw.circle(surface, (178, 150, 125), (int(left_hand_x), int(left_hand_y)), 15)
        pygame.draw.circle(surface, (70, 82, 100), (int(left_hand_x - 6), int(left_hand_y + 3)), 7)
        biribel_sleeve = (45, 55, 48)
        pygame.draw.line(surface, biribel_sleeve, right_start, (right_hand_x, right_hand_y), 22)
        pygame.draw.line(surface, (24, 30, 26), right_start, (right_hand_x, right_hand_y), 3)
        pygame.draw.circle(surface, (54, 44, 36), (int(right_hand_x), int(right_hand_y)), 16)
        pygame.draw.circle(surface, (170, 140, 112), (int(right_hand_x - 4), int(right_hand_y + 1)), 7)
        item_x = _lerp_cutscene(left_hand_x, WIDTH // 2, 0.55)
        item_y = hand_y - 20
        _draw_handoff_pistol(surface, item_x, item_y, scale=1.3, angle=-8)
        small = font_terminal_small.render(_T("route12.9mm_sidearm_12_rd_mag"), True, (150, 165, 175))
        surface.blit(small, (WIDTH // 2 - small.get_width() // 2, panel_y + 292))
    else:
        # ── MOLOTOVS: crate slides across the table toward Biribel ──
        crate_w, crate_h = 190, 86
        crate_start_x = panel_x + 175
        crate_end_x = WIDTH // 2 + 30
        crate_x = _lerp_cutscene(crate_start_x, crate_end_x, p)
        crate_y = table_y - 14 + idle * 0.5
        shad = pygame.Surface((crate_w + 30, 26), pygame.SRCALPHA)
        render_util.soft_shadow(shad, shad.get_rect(), 110)
        surface.blit(shad, (int(crate_x - crate_w // 2 - 15), int(crate_y + crate_h - 28)))
        crate_rect = pygame.Rect(int(crate_x - crate_w // 2), int(crate_y), crate_w, crate_h)
        pygame.draw.rect(surface, (84, 58, 32), crate_rect, border_radius=4)
        pygame.draw.rect(surface, (46, 30, 16), crate_rect, 3, border_radius=4)
        interior = crate_rect.inflate(-18, -18)
        interior.y -= 6
        pygame.draw.rect(surface, (26, 18, 12), interior, border_radius=3)
        for px2 in range(crate_rect.x + 28, crate_rect.right - 16, 38):
            pygame.draw.line(surface, (58, 38, 20),
                             (px2, crate_rect.y + 4), (px2, crate_rect.bottom - 4), 2)
        stencil = font_terminal_small.render(_T("route12.flammable"), True, (160, 60, 40))
        surface.blit(stencil, (crate_rect.centerx - stencil.get_width() // 2,
                               crate_rect.bottom - 22))
        _draw_handoff_molotov(surface, crate_rect.centerx - 34, crate_rect.y - 26,
                              scale=0.62, angle=-12)
        _draw_handoff_molotov(surface, crate_rect.centerx + 34, crate_rect.y - 24,
                              scale=0.62, angle=10)
        glow = pygame.Surface((280, 180), pygame.SRCALPHA)
        for r in range(115, 0, -8):
            a = int(16 * (1 - r / 115))
            pygame.draw.ellipse(glow, (235, 170, 90, a), (140 - r, 90 - r // 2, r * 2, r))
        surface.blit(glow, (int(crate_rect.centerx - 140), int(crate_rect.y - 95)))
        push_x = crate_rect.x - 6
        push_y = crate_rect.centery - 6
        left_start = (panel_x + 80, panel_y + 195)
        pygame.draw.line(surface, C_KRAP_UNIFORM, left_start, (push_x, push_y), 22)
        pygame.draw.line(surface, (25, 30, 38), left_start, (push_x, push_y), 3)
        pygame.draw.circle(surface, (178, 150, 125), (int(push_x), int(push_y)), 14)
        reach_p = _ease_cutscene((p - 0.55) / 0.45)
        if reach_p > 0:
            right_start = (panel.right - 80, panel_y + 210)
            reach_x = _lerp_cutscene(panel.right - 190, crate_rect.right + 4, reach_p)
            reach_y = _lerp_cutscene(panel_y + 215, crate_rect.centery - 2, reach_p)
            biribel_sleeve = (45, 55, 48)
            pygame.draw.line(surface, biribel_sleeve, right_start, (reach_x, reach_y), 22)
            pygame.draw.line(surface, (24, 30, 26), right_start, (reach_x, reach_y), 3)
            pygame.draw.circle(surface, (54, 44, 36), (int(reach_x), int(reach_y)), 15)
            pygame.draw.circle(surface, (170, 140, 112),
                               (int(reach_x - 4), int(reach_y + 1)), 7)
        small = font_terminal_small.render(
            _T("route12.2x_molotov_unlit_field_expedient"), True, (190, 135, 80))
        surface.blit(small, (WIDTH // 2 - small.get_width() // 2, panel_y + 18 + 24))
    scan = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    for sy in range(0, panel_h, 4):
        pygame.draw.line(scan, (0, 0, 0, 22), (0, sy), (panel_w, sy))
    surface.blit(scan, (panel_x, panel_y))
    pygame.draw.line(surface, (80, 95, 110), (panel_x + 12, panel_y + 34), (panel.right - 12, panel_y + 34), 1)
# ─────────────────────────────────────────────
# CUTSCENE 1 - THE WORLD
# ─────────────────────────────────────────────
GROUND_Y = SCENE_BOT - 55
PAL_RAINY = [(26, 30, 38), (22, 28, 36)]

def draw_route12_black(surface, t):
    surface.fill((2, 3, 6))
    rng = random.Random(int(t // 80))
    for _ in range(45):
        x = rng.randint(0, WIDTH - 1)
        y = rng.randint(SCENE_TOP, SCENE_BOT - 1)
        shade = rng.randint(8, 28)
        surface.set_at((x, y), (shade, shade, shade + 4))
    pulse = int(35 + math.sin(t * 0.006) * 20)
    glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.circle(glow, (40, 80, 120, pulse), (WIDTH // 2, HEIGHT // 2), 220)
    surface.blit(glow, (0, 0))
    tag = font_terminal.render(_T("route12.krap_field_audio_route_12"), True, (75, 125, 165))
    surface.blit(tag, (WIDTH // 2 - tag.get_width() // 2, SCENE_TOP + 210))
    sub = font_terminal_small.render(_T("route12.rain_audio_file_room_static_no_l"), True, (90, 90, 95))
    surface.blit(sub, (WIDTH // 2 - sub.get_width() // 2, SCENE_TOP + 244))


def draw_route12_files(surface, t):
    """Vasile studies the recovered Route 12 file.

    Cleaner spacing pass: the close-up now uses three separated document zones
    instead of stacking every clue on top of the main security order.
    """
    def ease01(v):
        v = max(0.0, min(1.0, v))
        return v * v * (3 - 2 * v)

    push = ease01((t - 1350) / 1100.0)
    finger_t = ease01((t - 2450) / 850.0)
    flicker = 0.78 + 0.22 * math.sin(t * 0.009)

    # ── Base van interior, without default characters.
    surface.fill((7, 8, 10))
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_H)
        pygame.draw.line(
            surface,
            (int(13 + p * 9), int(11 + p * 6), int(13 + p * 7)),
            (0, y),
            (WIDTH, y),
        )
    for x in range(80, WIDTH - 80, 96):
        pygame.draw.line(surface, (25, 22, 24), (x, SCENE_TOP + 10), (x, SCENE_BOT - 92), 1)
    for y in range(SCENE_TOP + 50, SCENE_BOT - 90, 48):
        pygame.draw.line(surface, (21, 18, 20), (40, y), (WIDTH - 40, y), 1)

    floor_y = SCENE_BOT - 95
    pygame.draw.rect(surface, (10, 10, 12), (0, floor_y, WIDTH, SCENE_BOT - floor_y))
    pygame.draw.rect(surface, (145, 28, 30), (WIDTH // 2 - 95, SCENE_TOP + 28, 190, 7))
    red_glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.circle(red_glow, (130, 20, 24, 28), (WIDTH // 2, SCENE_TOP + 76), 210)
    surface.blit(red_glow, (0, 0))

    # Subdued right-side route monitor.
    win = pygame.Rect(WIDTH - 300, SCENE_TOP + 78, 210, 165)
    pygame.draw.rect(surface, (7, 9, 13), win)
    pygame.draw.rect(surface, (48, 39, 34), win.inflate(12, 12), 4)
    for i in range(12):
        lx = win.x + 12 + ((i * 31 + int(t * 0.35)) % (win.w - 24))
        ly = win.y + 24 + (i * 21) % (win.h - 48)
        pygame.draw.rect(surface, [(150, 80, 55), (80, 95, 130), (170, 130, 55)][i % 3], (lx, ly, 26, 4))

    # ── Wide shot: Vasile and folder.
    lamp = pygame.Surface((360, 360), pygame.SRCALPHA)
    pygame.draw.circle(lamp, (85, 145, 210, int(48 * (1 - push * 0.35))), (180, 180), 170)
    surface.blit(lamp, (42, SCENE_TOP + 112))
    draw_vasile(surface, 185, floor_y + 2, scale=0.72, facing_right=True)

    table = pygame.Rect(315, floor_y - 74, 278, 70)
    pygame.draw.rect(surface, (0, 0, 0), table.move(8, 8), border_radius=4)
    pygame.draw.rect(surface, (34, 25, 18), table, border_radius=4)
    pygame.draw.rect(surface, (74, 55, 35), table, 2, border_radius=4)
    folder_x, folder_y = table.x + 28, table.y + 10
    folder_pts = [
        (folder_x, folder_y + 12),
        (folder_x + 88, folder_y),
        (folder_x + 214, folder_y + 14),
        (folder_x + 204, folder_y + 52),
        (folder_x + 8, folder_y + 54),
    ]
    pygame.draw.polygon(surface, (150, 118, 62), folder_pts)
    pygame.draw.polygon(surface, (95, 72, 38), folder_pts, 2)
    for i, off in enumerate((0, 9, 18)):
        pygame.draw.rect(surface, (204, 196, 160), (folder_x + 30 + off, folder_y + 8 + off // 3, 112, 44), border_radius=2)
        pygame.draw.rect(surface, (95, 83, 60), (folder_x + 30 + off, folder_y + 8 + off // 3, 112, 44), 1, border_radius=2)
        pygame.draw.line(surface, (120, 104, 76), (folder_x + 40 + off, folder_y + 24 + off // 3), (folder_x + 124 + off, folder_y + 24 + off // 3), 1)
        pygame.draw.line(surface, (120, 104, 76), (folder_x + 40 + off, folder_y + 34 + off // 3), (folder_x + 114 + off, folder_y + 34 + off // 3), 1)
    tag = font_terminal_small.render(_T("route12.recovered_from_volkov_warehouse"), True, (125, 145, 155))
    tag.set_alpha(int(230 * (1 - push * 0.55)))
    surface.blit(tag, (table.x + 18, table.y - 24))

    # ── Close-up layer: spaced physical documents on a desk.
    close = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, int(135 * push)))
    close.blit(dim, (0, 0))

    desk = pygame.Rect(86, SCENE_TOP + 34, WIDTH - 172, 402)
    pygame.draw.rect(close, (22, 15, 10, int(245 * push)), desk, border_radius=8)
    pygame.draw.rect(close, (70, 48, 28, int(210 * push)), desk, 2, border_radius=8)
    for yy in range(desk.y + 34, desk.bottom - 20, 42):
        pygame.draw.line(close, (34, 24, 16, int(120 * push)), (desk.x + 18, yy), (desk.right - 18, yy), 1)

    # Folder backing, slightly larger but visually quiet.
    folder = pygame.Rect(desk.x + 40, desk.y + 42, desk.w - 80, desk.h - 78)
    folder_shape = [
        (folder.x, folder.y + 36),
        (folder.x + 132, folder.y),
        (folder.right - 22, folder.y + 25),
        (folder.right, folder.bottom - 20),
        (folder.x + 24, folder.bottom),
    ]
    pygame.draw.polygon(close, (145, 111, 58, int(236 * push)), folder_shape)
    pygame.draw.polygon(close, (88, 66, 36, int(210 * push)), folder_shape, 2)
    tab = font_terminal_small.render(_T("route12.route_12_checkpoint_12"), True, (56, 42, 24))
    tab.set_alpha(int(230 * push))
    close.blit(tab, (folder.x + 34, folder.y + 14))

    def draw_paper(rect, title, rows, stamp=None, stamp_col=(170, 38, 32), paper_col=(213, 205, 176), angle=0, title_size="terminal"):
        paper = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(paper, paper_col, paper.get_rect(), border_radius=3)
        pygame.draw.rect(paper, (95, 80, 58), paper.get_rect(), 2, border_radius=3)
        pygame.draw.rect(paper, (188, 181, 152), (0, 0, rect.w, 34), border_radius=3)
        title_font = font_terminal if title_size == "terminal" else font_terminal_small
        title_s = title_font.render(title, True, (45, 37, 28))
        paper.blit(title_s, (14, 8 if title_size == "terminal" else 10))
        y = 50
        for label, value, col in rows:
            lab = font_terminal_small.render(label, True, (78, 68, 52))
            val_font = font_prompt if rect.w > 300 else font_terminal_small
            val = val_font.render(value, True, col)
            paper.blit(lab, (18, y + 3))
            paper.blit(val, (130 if rect.w < 330 else 146, y))
            pygame.draw.line(paper, (160, 148, 112), (16, y + 24), (rect.w - 18, y + 24), 1)
            y += 32
        for yy in range(y + 4, rect.h - 18, 15):
            pygame.draw.line(paper, (170, 158, 120), (18, yy), (rect.w - 20, yy), 1)
        if stamp:
            st = font_terminal.render(stamp, True, stamp_col)
            st = pygame.transform.rotate(st, -7)
            st.set_alpha(205)
            paper.blit(st, (rect.w - st.get_width() - 14, rect.h - st.get_height() - 12))
        paper.set_alpha(int(255 * push))
        if angle:
            rot = pygame.transform.rotate(paper, angle)
            close.blit(rot, rot.get_rect(center=rect.center))
        else:
            close.blit(paper, rect)

    # Layout zones:
    #   left top  = checkpoint photo
    #   left bottom = IPA manifest
    #   right = security order
    #   bottom center = field note, not covering key rows.
    photo = pygame.Rect(desk.x + 74, desk.y + 74, 250, 140)
    draw_paper(photo, "PHOTO // CHECKPOINT", [], paper_col=(198, 192, 166), title_size="small")
    pygame.draw.rect(close, (20, 23, 25, int(255 * push)), (photo.x + 20, photo.y + 42, photo.w - 40, 70))
    pygame.draw.rect(close, (55, 65, 66, int(255 * push)), (photo.x + 42, photo.y + 65, 50, 36))
    pygame.draw.rect(close, (55, 65, 66, int(255 * push)), (photo.x + 128, photo.y + 58, 54, 43))
    pygame.draw.line(close, (155, 60, 45, int(255 * push)), (photo.x + 44, photo.y + 101), (photo.x + 90, photo.y + 66), 2)
    pygame.draw.circle(close, (185, 45, 35, int(255 * push)), (photo.right - 22, photo.y + 22), 5)

    manifest = pygame.Rect(desk.x + 74, desk.y + 252, 275, 105)
    draw_paper(
        manifest,
        "IPA TRUCK MANIFEST",
        [("DEST", "CHECKPOINT 12", (40, 46, 48)), ("CLEAR", "BALACEANU OFFICE", (190, 55, 42))],
        paper_col=(207, 196, 158),
        angle=-1,
        title_size="small",
    )

    main_doc = pygame.Rect(desk.x + 490, desk.y + 70, 395, 285)
    draw_paper(
        main_doc,
        "SECURITY ORDER",
        [
            ("ROUTE", "12 / CHECKPOINT 12", (40, 46, 48)),
            ("STATUS", "PRE-MARKED UNSTABLE", (42, 85, 105)),
            ("PUBLIC", "MAG BOMBING", (40, 46, 48)),
            ("AUTH", "IPA / BALACEANU", (190, 55, 42)),
            ("DECREE", "DRAFTED 02:14", (190, 55, 42)),
            ("REPORT", "FILED 03:27", (40, 46, 48)),
        ],
        stamp="BEFORE ATTACK",
    )
    highlight = pygame.Surface((main_doc.w - 34, 56), pygame.SRCALPHA)
    highlight.fill((170, 42, 32, int(34 * push * flicker)))
    close.blit(highlight, (main_doc.x + 17, main_doc.y + 208))

    note = pygame.Rect(desk.x + 360, desk.y + 292, 220, 92)
    draw_paper(
        note,
        "FIELD NOTE",
        [("PAINT", "AFTER BLAST", (40, 46, 48)), ("CLAIM", "NONE", (190, 55, 42))],
        stamp="NOT MAG?",
        paper_col=(224, 211, 166),
        angle=2,
        title_size="small",
    )

    # Thin evidence strings - routed around text-heavy areas.
    line_col = (185, 68, 45, int(220 * push))
    connections = [
        ((photo.right - 8, photo.centery + 12), (main_doc.x + 18, main_doc.y + 70)),
        ((manifest.right - 6, manifest.y + 34), (main_doc.x + 18, main_doc.y + 214)),
        ((note.right - 8, note.y + 34), (main_doc.x + 18, main_doc.y + 172)),
    ]
    for a, b in connections:
        pygame.draw.line(close, line_col, a, b, 2)
        pygame.draw.circle(close, line_col, a, 4)
        pygame.draw.circle(close, line_col, b, 4)

    # Vasile's finger points at the timestamp conflict without covering it.
    start_x, start_y = desk.x + 210, desk.bottom + 48
    target_x, target_y = main_doc.x + 250, main_doc.y + 250
    fx = start_x + (target_x - start_x) * finger_t
    fy = start_y + (target_y - start_y) * finger_t
    if push > 0.35:
        hand = pygame.Surface((220, 130), pygame.SRCALPHA)
        from core.hands import point_hand
        pygame.draw.line(hand, (82, 95, 122), (124, 96), (92, 74), 19)
        point_hand(hand, (86, 68), angle=-35, mirror=-1, sc=0.85,
                   pal={"skin": (225, 186, 142), "hi": (244, 210, 172),
                        "mid": (180, 138, 104), "sh": (160, 118, 88),
                        "nail": (205, 165, 130), "nail_edge": (150, 110, 80),
                        "nail_tip": (246, 222, 192)})
        hand.set_alpha(int(255 * push))
        hand = pygame.transform.rotate(hand, -6)
        close.blit(hand, (fx - 52, fy - 18))
        pygame.draw.circle(close, (255, 210, 110, int(105 * push * flicker)), (int(target_x), int(target_y)), 18, 2)

    scan_y = desk.y + 28 + int((t * 0.075) % max(1, desk.h - 56))
    scan = pygame.Surface((desk.w, 3), pygame.SRCALPHA)
    scan.fill((95, 180, 225, int(36 * push)))
    close.blit(scan, (desk.x, scan_y))
    cap = font_terminal_small.render(_T("route12.vasile_s_finger_stops_on_the_tim"), True, (135, 155, 165))
    cap.set_alpha(int(255 * push))
    close.blit(cap, (desk.x + 26, desk.bottom + 12))

    surface.blit(close, (0, 0))


def draw_route12_mag_alert(surface, t):
    """Official Route 12 public-release bulletin.

    Spacing-focused version: one readable main form, side notes outside the form,
    no stamps/text overlapping critical fields.
    """
    # Dark briefing wall.
    surface.fill((18, 17, 16))
    for y in range(SCENE_TOP, SCENE_BOT, 36):
        pygame.draw.rect(surface, (27, 24, 21), (0, y, WIDTH, 28))
        pygame.draw.line(surface, (9, 8, 7), (0, y + 28), (WIDTH, y + 28), 1)

    # Soft red emergency light behind the board.
    glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pulse = int(28 + math.sin(t * 0.005) * 10)
    pygame.draw.circle(glow, (175, 30, 24, pulse), (WIDTH // 2, SCENE_TOP + 215), 340)
    surface.blit(glow, (0, 0))

    # Wide backing board so sticky notes can live OUTSIDE the main sheet.
    board = pygame.Rect(WIDTH // 2 - 425, SCENE_TOP + 34, 850, 390)
    pygame.draw.rect(surface, (54, 39, 27), board, border_radius=7)
    pygame.draw.rect(surface, (115, 82, 45), board, 3, border_radius=7)
    pygame.draw.rect(surface, (30, 22, 15), board.inflate(-28, -28), 1, border_radius=4)

    # Main paper: centered and tall enough to separate fields from lower evidence.
    paper = pygame.Rect(WIDTH // 2 - 265, SCENE_TOP + 58, 530, 330)
    shadow = pygame.Surface((paper.w + 22, paper.h + 22), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 95))
    surface.blit(shadow, (paper.x + 11, paper.y + 13))
    pygame.draw.rect(surface, (196, 186, 142), paper, border_radius=2)
    pygame.draw.rect(surface, (78, 60, 38), paper, 3, border_radius=2)

    # Header strip.
    header = pygame.Rect(paper.x, paper.y, paper.w, 48)
    pygame.draw.rect(surface, (154, 28, 24), header)
    pygame.draw.rect(surface, (86, 18, 16), (header.x, header.bottom - 5, header.w, 5))
    hdr = font_speaker.render(_T("route12.emergency_security_alert"), True, (246, 226, 196))
    surface.blit(hdr, (header.centerx - hdr.get_width() // 2, header.y + 10))
    for px in (paper.x + 20, paper.right - 20):
        pygame.draw.circle(surface, (88, 48, 24), (px + 2, paper.y + 22), 7)
        pygame.draw.circle(surface, (202, 126, 62), (px, paper.y + 20), 7)

    # Official form fields, with large vertical spacing and no stamp overlap.
    form_x = paper.x + 42
    form_y = paper.y + 76
    label_col = (75, 59, 42)
    value_col = (43, 36, 28)
    warning_col = (132, 28, 24)
    rows = [
        ("INCIDENT", "ROUTE 12 / CHECKPOINT 12", value_col),
        ("PUBLIC LABEL", "SUSPECTED MAG BOMBING", warning_col),
        ("SOURCE", "IPA CIVIL SECURITY DESK", value_col),
        ("STATUS", "UNVERIFIED - FIELD REVIEW PENDING", warning_col),
    ]
    for i, (label, value, col) in enumerate(rows):
        y = form_y + i * 44
        lab = font_terminal_small.render(label, True, label_col)
        val_font = font_terminal if len(value) < 29 else font_prompt
        val = val_font.render(value, True, col)
        surface.blit(lab, (form_x, y + 6))
        surface.blit(val, (form_x + 145, y))
        pygame.draw.line(surface, (126, 108, 78), (form_x, y + 30), (paper.right - 42, y + 30), 1)

    # Highlight only the suspicious status row, not the whole document.
    hi = pygame.Surface((paper.w - 84, 32), pygame.SRCALPHA)
    hi.fill((190, 38, 26, 26))
    surface.blit(hi, (form_x, form_y + 3 * 44 - 3))

    # Lower evidence row. Everything here is below the fields.
    evidence_y = paper.y + 250
    photo = pygame.Rect(paper.x + 44, evidence_y, 132, 48)
    pygame.draw.rect(surface, (22, 23, 22), photo)
    pygame.draw.rect(surface, (96, 80, 58), photo, 2)
    tag = font_terminal.render(_T("route12.mag"), True, (15, 15, 14))
    tag = pygame.transform.rotate(tag, -7)
    tag.set_alpha(170)
    surface.blit(tag, (photo.x + 36, photo.y + 9))
    photo_lbl = font_terminal_small.render(_T("route12.attached_photo_unverified"), True, (70, 58, 42))
    surface.blit(photo_lbl, (photo.x, photo.bottom + 5))

    # Small stamp in its own lower-right area, not on top of form fields.
    stamp_box = pygame.Rect(paper.right - 200, evidence_y - 4, 160, 60)
    pygame.draw.rect(surface, (0, 0, 0, 28), stamp_box)
    pygame.draw.rect(surface, (130, 28, 24), stamp_box, 1)
    stamp = font_terminal.render(_T("route12.suspected_mag"), True, (140, 26, 22))
    stamp = pygame.transform.rotate(stamp, -5)
    stamp.set_alpha(178)
    surface.blit(stamp, (stamp_box.centerx - stamp.get_width() // 2, stamp_box.y + 7))
    bomb = font_terminal_small.render(_T("route12.bombing"), True, (140, 26, 22))
    bomb = pygame.transform.rotate(bomb, -5)
    bomb.set_alpha(172)
    surface.blit(bomb, (stamp_box.centerx - bomb.get_width() // 2, stamp_box.y + 36))

    # Footer at the very bottom, separate from photo and stamp.
    footer = pygame.Rect(paper.x + 34, paper.bottom - 28, paper.w - 68, 20)
    pygame.draw.rect(surface, (0, 0, 0, 34), footer)
    footer_txt = font_terminal_small.render(_T("route12.public_release_prepared_field_ve"), True, (72, 48, 32))
    surface.blit(footer_txt, (footer.centerx - footer_txt.get_width() // 2, footer.y + 4))

    # Side notes: outside the paper, so they cannot cover form fields.
    note1 = pygame.Rect(board.x + 36, board.y + 70, 112, 66)
    pygame.draw.rect(surface, (178, 162, 114), note1, border_radius=2)
    pygame.draw.rect(surface, (84, 64, 38), note1, 1, border_radius=2)
    n1 = font_terminal_small.render(_T("route12.no_claim"), True, (100, 36, 28))
    n2 = font_terminal_small.render(_T("route12.signal"), True, (100, 36, 28))
    surface.blit(n1, (note1.x + 16, note1.y + 16))
    surface.blit(n2, (note1.x + 25, note1.y + 38))

    note2 = pygame.Rect(board.right - 152, board.bottom - 106, 116, 60)
    pygame.draw.rect(surface, (154, 132, 92), note2, border_radius=2)
    pygame.draw.rect(surface, (84, 64, 38), note2, 1, border_radius=2)
    n3 = font_terminal_small.render(_T("route12.release"), True, (72, 48, 32))
    n4 = font_terminal_small.render(_T("route12.queued"), True, (125, 36, 28))
    surface.blit(n3, (note2.x + 28, note2.y + 14))
    surface.blit(n4, (note2.x + 30, note2.y + 34))

    # Very subtle broadcast glitch. Global scanlines still draw later.
    if int(t // 260) % 2 == 0:
        pygame.draw.rect(surface, (255, 255, 255, 12), (paper.x, paper.y + 54, paper.w, 2))


def _draw_route12_checkpoint_base(surface, t, tanker=False):
    """Cinematic Route 12 checkpoint plate; all major visuals stay above dialogue."""
    draw_sky_gradient(surface, (8, 12, 18), (28, 28, 30))
    horizon_y = SCENE_TOP + 96
    road_y = SCENE_TOP + 300
    pygame.draw.rect(surface, (16, 18, 20), (0, horizon_y, WIDTH, SCENE_BOT - horizon_y))
    # Distant tree/building silhouettes.
    rng = random.Random(212)
    for x in range(-20, WIDTH + 60, 56):
        h = rng.randint(30, 90)
        pygame.draw.rect(surface, (10, 12, 14), (x, road_y - h - 58, 44, h))
    # Highway surface.
    pygame.draw.rect(surface, (30, 31, 32), (0, road_y, WIDTH, 210))
    pygame.draw.rect(surface, (23, 24, 25), (0, road_y + 86, WIDTH, 38))
    for x in range(-80 + int((t * 0.012) % 150), WIDTH + 150, 150):
        pygame.draw.rect(surface, (154, 136, 60), (x, road_y + 102, 72, 5))
    # Toll booths / checkpoint lanes with perspective spacing.
    booth_specs = [(120, road_y - 106, 104, 128), (330, road_y - 78, 92, 112), (590, road_y - 72, 92, 108), (790, road_y - 96, 104, 126)]
    for i, (bx, by, bw, bh) in enumerate(booth_specs):
        pygame.draw.rect(surface, (37, 44, 48), (bx + 5, by + 8, bw, bh))
        pygame.draw.rect(surface, (59, 68, 72), (bx, by, bw, bh))
        pygame.draw.rect(surface, (102, 112, 118), (bx, by, bw, bh), 2)
        pygame.draw.rect(surface, (8, 12, 15), (bx + 16, by + 24, bw - 32, 36))
        pygame.draw.line(surface, (138, 43, 34), (bx + 4, by + bh - 6), (bx + bw - 4, by + 16), 4)
        if i == 1:
            pygame.draw.circle(surface, (255, 110, 35), (bx + bw - 10, by + 12), 5)
    # Burned KRAP flag in a clear upper-left composition.
    pole_x = 88
    pygame.draw.line(surface, (55, 55, 58), (pole_x, road_y - 150), (pole_x, road_y + 20), 5)
    flag = [(pole_x, road_y - 148), (pole_x + 94, road_y - 138), (pole_x + 76, road_y - 96), (pole_x, road_y - 104)]
    pygame.draw.polygon(surface, C_KRAP_BLUE, flag)
    pygame.draw.polygon(surface, (8, 8, 8), [(pole_x + 66, road_y - 135), (pole_x + 94, road_y - 138), (pole_x + 76, road_y - 96), (pole_x + 58, road_y - 101)])
    # Foreground wrecks and evidence silhouette.
    wrecks = [(230, road_y + 74, 112, 40, (35, 32, 30)), (660, road_y + 78, 132, 42, (45, 38, 34))]
    for wx, wy, ww, wh, col in wrecks:
        pygame.draw.rect(surface, col, (wx, wy, ww, wh), border_radius=5)
        pygame.draw.rect(surface, (82, 65, 50), (wx, wy, ww, wh), 2, border_radius=5)
        pygame.draw.circle(surface, (10, 10, 10), (wx + 18, wy + wh), 9)
        pygame.draw.circle(surface, (10, 10, 10), (wx + ww - 18, wy + wh), 9)
    # Smoke columns kept semi-transparent.
    for i in range(10):
        sx = rng.randint(80, 900)
        sy = road_y - rng.randint(20, 150)
        drift = math.sin(t * 0.0014 + i) * 16
        for r in range(46, 10, -9):
            sm = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(sm, (45, 45, 45, max(10, 42 - r // 2)), (r, r), r)
            surface.blit(sm, (sx + drift - r, sy - i * 8 - r))
    if tanker:
        tank = pygame.Rect(WIDTH // 2 - 132, road_y + 20, 264, 72)
        render_util.soft_shadow(surface, (tank.x - 20, tank.y + 30, tank.w + 40, 72), 90)
        pygame.draw.rect(surface, (80, 74, 62), tank, border_radius=24)
        pygame.draw.rect(surface, (155, 42, 32), (tank.x + 18, tank.centery - 10, tank.w - 36, 20))
        pygame.draw.rect(surface, (132, 124, 98), tank, 2, border_radius=24)
        for sx in range(tank.x + 34, tank.right - 20, 46):
            pygame.draw.line(surface, (42, 45, 48), (sx, tank.y + 10), (sx, tank.bottom - 10), 3)
        leak = pygame.Surface((160, 42), pygame.SRCALPHA)
        pygame.draw.ellipse(leak, (45, 38, 25, 125), (0, 0, 160, 42))
        surface.blit(leak, (tank.right - 28, tank.bottom - 6))
        warn = font_terminal.render(_T("route12.leaking_fuel"), True, (255, 120, 50))
        surface.blit(warn, (tank.centerx - warn.get_width() // 2, tank.y - 34))
    else:
        label = font_terminal.render(_T("route12.checkpoint_12_suspected_mag_bomb"), True, (170, 145, 90))
        surface.blit(label, (WIDTH // 2 - label.get_width() // 2, road_y - 34))


def draw_route12_checkpoint(surface, t):
    """Mission 2 intro checkpoint hero shot.

    Goal: one readable cinematic image, not a flat row of booths. The important
    stuff stays above the dialogue box: burned KRAP flag, ruined checkpoint,
    headlights/squad entering, and the suspicious MAG label.
    """
    draw_sky_gradient(surface, (7, 11, 17), (25, 28, 31))
    top = SCENE_TOP
    bot = SCENE_BOT
    horizon_y = top + 118
    road_near_y = bot - 88
    road_far_y = top + 300

    # Distant skyline / tree line, low contrast so it doesn't fight the action.
    pygame.draw.rect(surface, (11, 14, 17), (0, horizon_y, WIDTH, bot - horizon_y))
    rng = random.Random(1212)
    for x in range(-30, WIDTH + 40, 42):
        h = rng.randint(38, 118)
        col = rng.choice([(9, 11, 14), (12, 13, 16), (14, 13, 15)])
        pygame.draw.rect(surface, col, (x, road_far_y - h, 34, h))
        if rng.random() > 0.78:
            pygame.draw.rect(surface, (95, 65, 38), (x + 12, road_far_y - h + 16, 5, 7))

    # Highway in perspective.
    pygame.draw.polygon(
        surface,
        (28, 30, 31),
        [(-110, bot), (WIDTH + 110, bot), (760, road_far_y), (240, road_far_y)],
    )
    pygame.draw.polygon(
        surface,
        (20, 22, 23),
        [(0, bot), (210, bot), (375, road_far_y), (255, road_far_y)],
    )
    pygame.draw.polygon(
        surface,
        (20, 22, 23),
        [(WIDTH, bot), (WIDTH - 210, bot), (625, road_far_y), (745, road_far_y)],
    )
    # Perspective lane marks.
    for i in range(7):
        p = i / 6
        y = road_far_y + p * (road_near_y - road_far_y)
        w = 52 + p * 62
        gap = 60 + p * 100
        x_center = WIDTH // 2
        col = (145, 132, 66)
        pygame.draw.rect(surface, col, (x_center - gap - w, y, w, 5))
        pygame.draw.rect(surface, col, (x_center + gap, y, w, 5))

    # Checkpoint gantry/sign: makes the place identifiable immediately.
    gantry_y = top + 165
    pygame.draw.line(surface, (46, 54, 58), (122, gantry_y), (878, gantry_y), 6)
    pygame.draw.line(surface, (18, 22, 25), (122, gantry_y + 5), (878, gantry_y + 5), 3)
    for gx in (145, 855):
        pygame.draw.rect(surface, (35, 42, 45), (gx - 5, gantry_y, 10, 244))
        pygame.draw.rect(surface, (16, 18, 20), (gx - 2, gantry_y + 8, 4, 232))
    sign = pygame.Rect(WIDTH // 2 - 240, gantry_y - 50, 480, 42)
    pygame.draw.rect(surface, (12, 15, 18), sign, border_radius=3)
    pygame.draw.rect(surface, (70, 83, 88), sign, 2, border_radius=3)
    sign_txt = font_terminal.render(_T("route12.checkpoint_12_route_12"), True, (195, 190, 150))
    surface.blit(sign_txt, (sign.centerx - sign_txt.get_width() // 2, sign.y + 10))
    alert = font_terminal_small.render(_T("route12.public_label_suspected_mag_bombi"), True, (176, 132, 58))
    surface.blit(alert, (sign.centerx - alert.get_width() // 2, sign.bottom + 10))

    # Toll booths, varied and damaged instead of repeated boxes.
    booths = [
        (185, road_far_y - 42, 110, 132, True),
        (382, road_far_y - 16, 92, 112, False),
        (565, road_far_y - 18, 96, 116, True),
        (748, road_far_y - 40, 108, 130, False),
    ]
    for i, (bx, by, bw, bh, broken) in enumerate(booths):
        pygame.draw.rect(surface, (21, 24, 27), (bx + 8, by + 10, bw, bh))
        pygame.draw.rect(surface, (53, 63, 66), (bx, by, bw, bh))
        pygame.draw.rect(surface, (98, 108, 112), (bx, by, bw, bh), 2)
        pygame.draw.rect(surface, (5, 9, 12), (bx + 16, by + 28, bw - 32, 34))
        if broken:
            pygame.draw.line(surface, (140, 42, 34), (bx + 4, by + bh - 8), (bx + bw - 5, by + 20), 4)
            pygame.draw.polygon(surface, (16, 18, 20), [(bx + bw - 28, by), (bx + bw, by + 8), (bx + bw - 8, by + 35)])
        if i == 1:
            pygame.draw.circle(surface, (235, 92, 34), (bx + bw - 10, by + 12), 5)
            glow = pygame.Surface((46, 46), pygame.SRCALPHA)
            pygame.draw.circle(glow, (235, 92, 34, 65), (23, 23), 20)
            surface.blit(glow, (bx + bw - 33, by - 11))

    # Burned KRAP flag: left focal anchor.
    pole_x = 85
    pygame.draw.line(surface, (55, 58, 60), (pole_x, road_far_y - 160), (pole_x, road_far_y + 112), 5)
    flag = [(pole_x, road_far_y - 158), (pole_x + 108, road_far_y - 144), (pole_x + 82, road_far_y - 92), (pole_x, road_far_y - 104)]
    pygame.draw.polygon(surface, C_KRAP_BLUE, flag)
    pygame.draw.polygon(surface, (5, 5, 6), [(pole_x + 76, road_far_y - 139), (pole_x + 108, road_far_y - 144), (pole_x + 82, road_far_y - 92), (pole_x + 60, road_far_y - 98)])

    # Wrecks/abandoned cars in foreground.
    for wx, wy, ww, wh, col in [
        (245, road_near_y - 68, 120, 44, (52, 42, 34)),
        (655, road_near_y - 58, 138, 48, (62, 48, 38)),
    ]:
        pygame.draw.rect(surface, (0, 0, 0), (wx + 5, wy + 8, ww, wh), border_radius=5)
        pygame.draw.rect(surface, col, (wx, wy, ww, wh), border_radius=5)
        pygame.draw.rect(surface, (105, 82, 58), (wx, wy, ww, wh), 2, border_radius=5)
        pygame.draw.circle(surface, (8, 8, 9), (wx + 18, wy + wh), 10)
        pygame.draw.circle(surface, (8, 8, 9), (wx + ww - 18, wy + wh), 10)

    # KRAP van/headlights entering from screen-left, implying the squad arrival.
    van_x, van_y = 35, road_near_y - 78
    pygame.draw.rect(surface, (22, 29, 38), (van_x, van_y, 132, 54), border_radius=5)
    pygame.draw.rect(surface, C_KRAP_BLUE, (van_x + 14, van_y + 14, 72, 8))
    pygame.draw.rect(surface, (195, 205, 205), (van_x + 14, van_y + 24, 72, 2))
    pygame.draw.rect(surface, (7, 10, 13), (van_x + 92, van_y + 10, 30, 24), border_radius=2)
    for ly in (van_y + 18, van_y + 34):
        beam = pygame.Surface((360, 80), pygame.SRCALPHA)
        pygame.draw.polygon(beam, (210, 210, 145, 28), [(0, 20), (340, -10), (340, 58), (0, 36)])
        surface.blit(beam, (van_x + 124, ly - 20))
        pygame.draw.circle(surface, (230, 220, 140), (van_x + 126, ly), 5)

    # Small squad staged above the dialogue box: Biribel on point, three
    # KRAP squad members behind him - all cast-sheet figures (figure_kit).
    squad_y = road_near_y - 78
    foot = squad_y + 16
    for i, sx in reversed(list(enumerate((430, 458, 486, 520)))):
        who = "biribel" if i == 0 else "krap"
        _fk_draw(surface, who, sx, foot, 0.16, facing_right=True, t=t + i * 400)
        # Slung rifle across the chest, aimed low toward the wrecks.
        pygame.draw.line(surface, (18, 18, 20), (sx - 2, foot - 26), (sx + 18, foot - 31), 3)

    # Smoke, sparks, and subtle warning lights.
    rng = random.Random(902)
    for i in range(12):
        sx = rng.randint(130, 880)
        sy = road_far_y - rng.randint(12, 118)
        drift = math.sin(t * 0.0016 + i) * 18
        for r in range(48, 10, -9):
            sm = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(sm, (45, 45, 45, max(10, 44 - r // 2)), (r, r), r)
            surface.blit(sm, (sx + drift - r, sy - i * 7 - r))
    if int(t / 250) % 2 == 0:
        pygame.draw.circle(surface, (255, 90, 35), (402, road_far_y - 4), 4)
        pygame.draw.circle(surface, (255, 90, 35), (665, road_far_y + 12), 3)

    # A low fog band gives depth and separates the scene from dialogue UI.
    fog = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(80):
        a = int(36 * (i / 80))
        pygame.draw.line(fog, (18, 22, 26, a), (0, road_near_y - 30 + i), (WIDTH, road_near_y - 30 + i))
    surface.blit(fog, (0, 0))


def draw_route12_tanker(surface, t):
    _draw_route12_checkpoint_base(surface, t, tanker=True)


def draw_route12_broadcast(surface, t):
    """Readable TV-broadcast cutscene for the Route 12 frame-up."""
    # TV studio / emergency broadcast background. Make this bright enough that it
    # never reads as an empty black screen behind the dialogue box.
    draw_sky_gradient(surface, (24, 18, 18), (62, 42, 34))
    stage_y = SCENE_TOP + 82
    pygame.draw.rect(surface, (42, 25, 22), (0, stage_y, WIDTH, SCENE_BOT - stage_y))
    # Broadcast monitor glow.
    glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.circle(glow, (160, 45, 35, 55), (WIDTH // 2, SCENE_TOP + 265), 360)
    pygame.draw.circle(glow, (255, 190, 90, 34), (WIDTH // 2, SCENE_TOP + 210), 250)
    surface.blit(glow, (0, 0))
    # Flags / pillars.
    for x in (80, 185, WIDTH - 255, WIDTH - 150):
        pygame.draw.rect(surface, (35, 42, 62), (x, stage_y + 18, 46, 395))
        pygame.draw.rect(surface, C_KRAP_BLUE, (x + 6, stage_y + 24, 14, 360))
        pygame.draw.rect(surface, (140, 35, 30), (x + 24, stage_y + 24, 14, 360))
    # Large red broadcast header.
    header = pygame.Rect(120, SCENE_TOP + 42, WIDTH - 240, 54)
    pygame.draw.rect(surface, (92, 17, 15), header, border_radius=4)
    pygame.draw.rect(surface, (210, 70, 45), header, 2, border_radius=4)
    htxt = font_speaker.render(_T("route12.acaristan_state_address_route_12"), True, (255, 230, 205))
    surface.blit(htxt, (header.centerx - htxt.get_width() // 2, header.y + 12))
    # Podium higher in the frame so it is visible above the dialogue UI.
    podium_y = SCENE_TOP + 430
    # President and Balaceanu from the cast sheet (figure_kit), standing
    # behind the podium so it hides their legs. Drawn before the podium.
    figures = [
        (WIDTH // 2 - 115, "president", "PRESIDENT\nRETARDOVICI", True),
        (WIDTH // 2 + 130, "balaceanu", "BALACEANU", False),
    ]
    for cx, who, _name, face_right in figures:
        render_util.soft_shadow(surface, (cx - 54, podium_y - 22, 108, 24), 90)
        _fk_draw(surface, who, cx, podium_y, 1.0, facing_right=face_right, t=t, look=0,
                 smile=0.35 if who == "president" else 0)
    pygame.draw.rect(surface, (82, 60, 46), (WIDTH // 2 - 230, podium_y - 120, 460, 130), border_radius=7)
    pygame.draw.rect(surface, (155, 122, 82), (WIDTH // 2 - 230, podium_y - 120, 460, 130), 3, border_radius=7)
    seal = pygame.Rect(WIDTH // 2 - 78, podium_y - 96, 156, 58)
    pygame.draw.rect(surface, (35, 28, 24), seal, border_radius=4)
    seal_txt = font_terminal.render(_T("route12.ipa_state"), True, (230, 205, 150))
    surface.blit(seal_txt, (seal.centerx - seal_txt.get_width() // 2, seal.y + 18))
    for cx, _who, name, _fr in figures:
        # Microphones
        for mx in (-18, 18):
            pygame.draw.line(surface, (10, 10, 12), (cx + mx, podium_y - 80), (cx + mx // 2, podium_y - 128), 3)
            pygame.draw.circle(surface, (8, 8, 10), (cx + mx // 2, podium_y - 130), 7)
        for j, line in enumerate(name.split("\n")):
            nt = font_terminal_small.render(line, True, (240, 220, 190))
            surface.blit(nt, (cx - nt.get_width() // 2, podium_y - 58 + j * 15))
    # Lower-third is high enough not to be hidden by the game's dialogue box.
    chy = pygame.Rect(0, SCENE_BOT - 95, WIDTH, 42)
    pygame.draw.rect(surface, (115, 18, 16), chy)
    pygame.draw.line(surface, (245, 120, 70), (0, chy.y), (WIDTH, chy.y), 2)
    txt = font_terminal.render(_T("route12.breaking_krap_blamed_for_route_1"), True, (255, 235, 210))
    surface.blit(txt, (WIDTH // 2 - txt.get_width() // 2, chy.y + 10))
    # TV scan bands/noise.
    for y in range(0, HEIGHT, 5):
        pygame.draw.line(surface, (0, 0, 0, 28), (0, y), (WIDTH, y))
    if int(t // 90) % 2 == 0:
        pygame.draw.rect(surface, (255, 255, 255, 18), (0, SCENE_TOP + 120, WIDTH, 3))


def draw_ipa_radio_chatter(surface, t):
    """M2 ending shot: IPA dispatch radio ordering Biribel's capture.

    A cold blue IPA dispatch console. The text reads out as a single
    urgent transmission, with status indicators (REC, AUTHORIZATION
    CODE, etc.) framing the message. No camera motion -- this is a
    static "we are hearing them on the radio" shot.
    """
    # Cold IPA-blue ambient.
    _draw_vertical_gradient(surface, 0, 0, WIDTH, HEIGHT, (4, 8, 14), (2, 4, 8))
    # Subtle scanline noise.
    rng = random.Random(t // 3)
    for _ in range(40):
        sx = rng.randint(0, WIDTH - 1)
        sy = rng.randint(0, HEIGHT - 1)
        v = rng.randint(8, 28)
        surface.set_at((sx, sy), (v, v + 4, v + 8))

    # Dispatch console (large, centered).
    panel_w, panel_h = 720, 320
    panel_x = WIDTH // 2 - panel_w // 2
    panel_y = HEIGHT // 2 - panel_h // 2 + 10
    # Outer bezel.
    pygame.draw.rect(surface, (12, 18, 24),
                     (panel_x - 10, panel_y - 10, panel_w + 20, panel_h + 20),
                     border_radius=4)
    pygame.draw.rect(surface, (30, 50, 65),
                     (panel_x - 10, panel_y - 10, panel_w + 20, panel_h + 20),
                     2, border_radius=4)
    # Screen inset (the dispatch display).
    pygame.draw.rect(surface, (6, 12, 20),
                     (panel_x, panel_y, panel_w, panel_h))
    pygame.draw.rect(surface, (22, 40, 55),
                     (panel_x, panel_y, panel_w, panel_h), 1)
    # Scanlines (every 2px on the display).
    for sy in range(panel_y + 2, panel_y + panel_h - 2, 2):
        pygame.draw.line(surface, (8, 14, 22),
                         (panel_x + 2, sy), (panel_x + panel_w - 2, sy), 1)

    # Top status bar: IPA DISPATCH | REC.
    bar_y = panel_y + 4
    pygame.draw.rect(surface, (28, 50, 70),
                     (panel_x + 4, bar_y, panel_w - 8, 18))
    head = font_speaker.render(_T("route12.ipa_dispatch_channel_7"), True, (180, 220, 240))
    surface.blit(head, (panel_x + 14, bar_y + 2))
    rec_pulse = 0.5 + 0.5 * math.sin(t * 0.4)
    if rec_pulse > 0.4:
        rec_dot = font_terminal_small.render(_T("route12.rec_2"), True, (220, 50, 50))
        surface.blit(rec_dot, (panel_x + panel_w - rec_dot.get_width() - 14, bar_y + 4))

    # Main message (centered on the dispatch display).
    msg_y = panel_y + 60
    # Hand-set as two lines so the dispatch reads as a real radio order.
    line1 = font_dialogue.render(_T("route12.all_units_the_krap_operator_is_t"),
                                 True, (200, 230, 245))
    line2 = font_dialogue.render(_T("route12.bring_him_in_authorization_ipa_c"),
                                 True, (220, 240, 255))
    surface.blit(line1, (panel_x + panel_w // 2 - line1.get_width() // 2, msg_y))
    surface.blit(line2, (panel_x + panel_w // 2 - line2.get_width() // 2, msg_y + 40))

    # Bottom status: a classification bar (red -- "FLAGGED TARGET").
    foot_y = panel_y + panel_h - 30
    pygame.draw.rect(surface, (110, 30, 30),
                     (panel_x + 4, foot_y, panel_w - 8, 22))
    foot = font_terminal_small.render(
        _T("route12.flagged_target_krap_operator_acu"),
        True, (240, 220, 200),
    )
    surface.blit(foot, (panel_x + panel_w // 2 - foot.get_width() // 2,
                         foot_y + 5))

    # A second red ALERT banner below the panel (urgent framing).
    alert_y = panel_y + panel_h + 30
    alert = font_terminal_small.render(
        _T("route12.priority_alpha_all_field_units"),
        True, (220, 80, 80),
    )
    alert.set_alpha(int(180 + 60 * math.sin(t * 0.3)))
    surface.blit(alert, (WIDTH // 2 - alert.get_width() // 2, alert_y))


def draw_krap_door_kickin(surface, t):
    """M2 ending shot: KRAP safehouse door being kicked in. Visual only.

    Sequence (driven by t):
      0-1.5s   Closed door, faint blue lights flashing outside the frame
      1.5-3s   Door splinters inward, blue lights wash in
      3-4.5s   Silhouettes pour in (IPA boots the door), hands grab Biribel
      4.5-6s   Fades to black (the screen goes dark as he's taken)

    No dialogue. The visuals tell the story. Vasile's voice (from the
    next shot) does the emotional work.
    """
    # Phase 0-1.5s: closed door. Phases 1.5-3s: door breaks. 3-4.5s:
    # silhouettes rush in. 4.5-6s: black.
    # The dispatcher clock is milliseconds (app.render passes t_ms); the old
    # t / 360 was a 60fps frame count, which blacked the shot out in 0.3s
    # before anyone could see the raid.
    phase = min(1.0, t / 6000.0)  # 6s shot, normalize to 0..1

    # Dim warm apartment behind the door.
    _draw_vertical_gradient(surface, 0, 0, WIDTH, HEIGHT, (12, 10, 8), (4, 3, 3))

    # A wood door in the center (large, takes up ~half the screen).
    door_w, door_h = 280, 480
    door_x = WIDTH // 2 - door_w // 2
    door_y = HEIGHT // 2 - door_h // 2 + 20
    if phase < 0.25:
        # Door intact.
        pygame.draw.rect(surface, (44, 28, 16), (door_x, door_y, door_w, door_h))
        # Wood grain.
        for gy in range(door_y, door_y + door_h, 12):
            rng = random.Random(gy * 7)
            c = 50 + rng.randint(-6, 6)
            pygame.draw.line(surface, (c, int(c * 0.6), int(c * 0.3)),
                             (door_x, gy), (door_x + door_w, gy), 1)
        # Door panels (two rectangles).
        pygame.draw.rect(surface, (28, 18, 10),
                         (door_x + 24, door_y + 30, door_w - 48, door_h // 2 - 50),
                         border_radius=2)
        pygame.draw.rect(surface, (28, 18, 10),
                         (door_x + 24, door_y + door_h // 2 + 20,
                          door_w - 48, door_h // 2 - 50),
                         border_radius=2)
        # Door handle.
        pygame.draw.circle(surface, (180, 150, 90),
                           (door_x + door_w - 30, door_y + door_h // 2), 6)
    elif phase < 0.5:
        # Door splinters inward.
        splinter_t = (phase - 0.25) / 0.25  # 0..1
        # Splinter lines (cracks spreading).
        for i in range(8):
            rng = random.Random(i * 13)
            sx = door_x + rng.randint(20, door_w - 20)
            sy = door_y + rng.randint(20, door_h - 20)
            ex = door_x + rng.randint(0, door_w)
            ey = door_y + rng.randint(0, door_h)
            pygame.draw.line(surface, (10, 6, 4),
                             (sx, sy), (ex, ey), 2)
        # Door swung inward (now at an angle).
        swing = int(splinter_t * 35)
        door_pts = [
            (door_x, door_y),
            (door_x + door_w, door_y),
            (door_x + door_w - swing, door_y + door_h),
            (door_x + swing, door_y + door_h),
        ]
        pygame.draw.polygon(surface, (44, 28, 16), door_pts)
        # Bright blue light floods through the gap.
        gap_pts = [
            (door_x + door_w - swing, door_y),
            (door_x + door_w, door_y),
            (door_x + door_w, door_y + door_h),
            (door_x + door_w - swing, door_y + door_h),
        ]
        light = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.polygon(light, (40, 90, 180, int(200 * splinter_t)), gap_pts)
        surface.blit(light, (0, 0))
    else:
        # Door is open / gone. Blue light fills the frame.
        blue_t = min(1.0, (phase - 0.5) / 0.4)
        _draw_light_cone(surface, WIDTH // 2, HEIGHT // 2 + 40, 500,
                         (60, 110, 200), alpha=int(160 * blue_t))
        # IPA agents rushing in (4 of them, through the door) - cast-sheet
        # "ipa" figures as backlit silhouettes; the lead agent hauls Biribel.
        # (The old primitive bodies were staged below the bottom edge.)
        rush = min(1.0, max(0.0, (phase - 0.5) / 0.3))
        ipa_scale = 1.25
        floor = door_y + door_h + 6
        bir_x = door_x - 40 + int(rush * 20)
        bir_foot = HEIGHT - 4
        bir_scale = 1.12
        bir_k = bir_scale * 254 / 296.0
        collar = (bir_x + 18, bir_foot - 214 * bir_k)
        for i in reversed(range(4)):
            sx = door_x + 40 + i * 66 + int((1 - rush) * 50)
            foot = floor + i * 6
            reach = None
            if i == 0:  # arms out to Biribel's collar and shoulder
                reach = ((collar[0] - sx, collar[1] - foot),
                         (collar[0] + 40 - sx, collar[1] + 30 - foot))
            _fk_draw(surface, "ipa", sx, foot, ipa_scale, facing_right=False, silhouette=True,
                     reach=reach, moving=1, t=t + i * 230)
            # IPA collar / insignia (a thin bright strip).
            ik = ipa_scale * 262 / 296.0
            pygame.draw.rect(surface, (160, 200, 230), (sx - 6, int(foot - 196 * ik), 12, 4))
        # Biribel in front of them, dragged off balance toward the door.
        _fk_draw(surface, "biribel", bir_x, bir_foot, bir_scale, facing_right=True,
                 silhouette=True, fear=1.0, bow=0.4, moving=1, t=t,
                 reach=((-70, -150 * bir_k), (60, -200 * bir_k)))
        # Last phase: fade to black.
        if phase > 0.85:
            fade = (phase - 0.85) / 0.15
            black = pygame.Surface((WIDTH, HEIGHT))
            black.fill((0, 0, 0))
            black.set_alpha(int(255 * fade))
            surface.blit(black, (0, 0))

    # IPA blue lights flashing on the walls (always present, pulses).
    light_pulse = 0.6 + 0.4 * math.sin(t * 0.005)  # ms clock (was 0.3/frame)
    _draw_light_cone(surface, WIDTH // 2 + 100, HEIGHT // 2, 200,
                     (40, 80, 160), alpha=int(60 * light_pulse))


def draw_biribel_blackout(surface, t):
    """M2 ending shot: Vasile's voice fades as Biribel is dragged away.

    Black screen with a small radio showing the dying signal. The
    dialogue text fades in and out as Vasile's voice breaks up.
    Mirrors the M2 cutscene aesthetic (no camera transform -- this
    is a clean cinematic beat, not an interactive intro shot).
    """
    # Pure black.
    surface.fill((2, 2, 3))

    # Small radio device at the bottom-left.
    radio_x, radio_y = 100, HEIGHT - 200
    pygame.draw.rect(surface, (22, 22, 26),
                     (radio_x, radio_y, 130, 70), border_radius=4)
    pygame.draw.rect(surface, (45, 45, 50),
                     (radio_x, radio_y, 130, 70), 2, border_radius=4)
    # Speaker grille.
    for gy in range(radio_y + 10, radio_y + 42, 5):
        for gx in range(radio_x + 10, radio_x + 70, 5):
            pygame.draw.circle(surface, (8, 8, 10), (gx, gy), 1)
    # Frequency window (LCD strip).
    pygame.draw.rect(surface, (40, 60, 30), (radio_x + 78, radio_y + 10, 44, 16))
    freq = font_terminal_small.render(_T("route12.87_5"), True, (110, 200, 130))
    surface.blit(freq, (radio_x + 84, radio_y + 12))
    # Tuning knob.
    pygame.draw.circle(surface, (35, 35, 40), (radio_x + 100, radio_y + 50), 10)
    pygame.draw.line(surface, (90, 90, 95),
                     (radio_x + 100, radio_y + 50),
                     (radio_x + 100 + int(math.cos(t * 0.06) * 6),
                      radio_y + 50 + int(math.sin(t * 0.06) * 6)), 1)
    # LED.
    led_pulse = 0.4 + 0.6 * math.sin(t * 0.15)  # pulse slows as signal dies
    led_color = (int(80 + 100 * led_pulse), int(15 + 20 * led_pulse),
                 int(15 + 20 * led_pulse))
    pygame.draw.circle(surface, led_color, (radio_x + 118, radio_y + 14), 3)
    _draw_light_cone(surface, radio_x + 118, radio_y + 14, 50,
                     (200, 40, 40), alpha=int(40 * led_pulse))

    # Waveform (the dying signal).
    wave_x = radio_x + 10
    wave_y = radio_y - 28
    wave_w, wave_h = 120, 22
    pygame.draw.rect(surface, (12, 18, 14),
                     (wave_x - 2, wave_y - 2, wave_w + 4, wave_h + 4))
    pygame.draw.rect(surface, (35, 50, 38),
                     (wave_x - 2, wave_y - 2, wave_w + 4, wave_h + 4), 1)
    # Amplitude decays over time (the signal is dying).
    amp = max(0.1, 0.9 - (t / 240.0))
    pts = []
    for i in range(wave_w):
        n = (math.sin(t * 0.4 + i * 0.5) * 0.4
             + math.sin(t * 0.7 + i * 0.9) * 0.3
             + (random.Random(t // 3 + i).random() - 0.5) * 0.5)
        py = wave_y + wave_h // 2 + int(n * amp * (wave_h // 2 - 2))
        pts.append((wave_x + i, py))
    if len(pts) > 1:
        pygame.draw.lines(surface, (110, 200, 130), False, pts, 1)
    pygame.draw.line(surface, (40, 60, 45),
                     (wave_x, wave_y + wave_h // 2),
                     (wave_x + wave_w, wave_y + wave_h // 2), 1)
    # Signal label.
    wave_lbl = font_terminal_small.render(
        _T("route12.rx_ch_7_no_signal"), True, (80, 120, 90))
    surface.blit(wave_lbl, (wave_x, wave_y - 18))
    # Callsign.
    callsign = font_terminal_small.render(
        _T("route12.vasile_krap_field_unit"), True, (70, 100, 80))
    surface.blit(callsign, (wave_x, wave_y + wave_h + 2))


def draw_route12_aftermath(surface, t):
    _draw_route12_checkpoint_base(surface, t, tanker=True)
    fire = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(16):
        x = 90 + i * 58 + math.sin(t * 0.003 + i) * 16
        y = GROUND_Y - 80 + (i % 3) * 18
        pygame.draw.circle(fire, (255, 95, 25, 58), (int(x), int(y)), 44)
        pygame.draw.circle(fire, (255, 190, 70, 70), (int(x), int(y + 10)), 20)
    surface.blit(fire, (0, 0))
    draw_biribel(surface, WIDTH // 2 + 25, GROUND_Y + 8, scale=0.82, facing_right=False, in_silhouette=True)


# ─────────────────────────────────────
# Mission 3 - Stabilization Center scene renderers
# ─────────────────────────────────────
# Four procedural scenes for the M3 intro cutscene. Purely visual - no
# new art assets needed. All reuse the existing character renderers
# (draw_biribel, draw_volkov), the light-cone helper, and gradient tools.


def _draw_vertical_gradient(surface, x, y, w, h, top_color, bottom_color):
    """Draw a vertical gradient rectangle."""
    for i in range(h):
        t = i / max(1, h - 1)
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        pygame.draw.line(surface, (r, g, b), (x, y + i), (x + w, y + i))




def _draw_light_cone(surface, lx, ly, radius, color, alpha=80):
    """Draw a radial light cone - a soft glow centered at (lx, ly).

    Used for the fluorescent overhead, the bare bulb in the cell, etc.
    Clamps the color channels + alpha to valid ranges to avoid
    "invalid color argument" crashes from flicker math producing
    out-of-range values.
    """
    # Clamp color channels to 0-255.
    r = max(0, min(255, int(color[0])))
    g = max(0, min(255, int(color[1])))
    b = max(0, min(255, int(color[2])))
    a = max(0, min(255, int(alpha)))
    if a <= 0 or radius <= 0:
        return
    glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    steps = 20
    for i in range(steps):
        t = i / steps
        rad = int(radius * (1 - t * 0.6))
        aa = int(a * (1 - t) ** 2)
        if aa > 0 and rad > 0:
            pygame.draw.circle(glow, (r, g, b, aa), (radius, radius), rad)
    surface.blit(glow, (lx - radius, ly - radius))
