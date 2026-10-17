
"""m4aftermath.py - Mission 4 finale + intro cutscene art (The Aftermath).

Bespoke shots replace the Slice-0 title-card stubs:

  1. m4_city_curfew      - the capital hours after the broadcast: skyline on
                           fire, searchlights, a curfew the regime can no
                           longer hold. Doubles as the M3 -> M4 intro callback
                           frame (the Vostral still glowing on the street).
  2. m4_arrest_screen    - the state airwaves turning on their own general:
                           Balaceanu escorted out on a wall monitor while the
                           square cheers Retardovici's crest. Biribel is not in
                           this frame - the arrest happens without him.
  3. m4_maru_silhouette  - the liaison in the transmitter hall, the only new
                           face the team actually meets on the ground.
  4. m4_roof_dawn        - studio roof at first light, curfew lifting; Biribel
                           and Vasile watch a city that cheered the wrong man.

Purely procedural, in the same visual language as m3ending (SAFE_TOP..SAFE_BOT
composition so the dialogue box never covers the performers; every wide shot
lives inside that band). Helpers are ported by import from the shared cutscene
layers, not re-implemented.
"""
import math
import random

import pygame

from core.config import (HEIGHT, SCENE_TOP, WIDTH, font_terminal_small)
from core.state import STATE
from functools import lru_cache

from cutscenes.cast import draw_biribel, draw_vasile
from cutscenes.m3ko import _ko_clamp01, _ko_glow, _ko_tint
from cutscenes.m3cell import _m3_clamp01, _m3_noise, _m3_smooth
from cutscenes.chair import _draw_dust_motes
from cutscenes.route12 import _draw_vertical_gradient

_CREST = (230, 200, 120)      # Retardovici's presidential gold
_ARREST = (220, 90, 70)       # Balaceanu red (the general being led out)
_LIAISON = (110, 200, 140)    # Maru green (matches m4.meta C_MARU)
_DAWN = (228, 150, 96)        # first-light warm

SAFE_TOP = SCENE_TOP + 6
SAFE_BOT = HEIGHT - 158   # dialogue box ceiling


def _tag(surface, text, color=(120, 200, 220)):
    """Location tag pinned inside the safe band (m3ending._tag idiom)."""
    surf = font_terminal_small.render(text, True, color)
    surface.blit(surf, (WIDTH // 2 - surf.get_width() // 2, SAFE_TOP + 2))


def _skyline(surface, base_y, rng, *, lit_runs=True, fire=False, t=0, height_scale=1.0):
    """Row of rooftops along ``base_y``. ``fire`` turns some into burnings
    (ember glow + a rising plume), used by the curfew and roof shots."""
    buildings = []
    x = -20
    while x < WIDTH + 20:
        bw = rng.randint(56, 104)
        bh = round(rng.randint(110, 320) * height_scale)
        buildings.append((x, bw, bh))
        x += bw + rng.randint(4, 16)
    for bx, bw, bh in buildings:
        by = base_y - bh
        pygame.draw.rect(surface, (14, 16, 24), (bx, by, bw, bh + 60))
        pygame.draw.rect(surface, (22, 25, 36), (bx, by, bw, 3))
        if lit_runs:
            for wy in range(by + 12, base_y - 8, 19):
                lit = 0
                for wx in range(bx + 8, bx + bw - 10, 15):
                    on = rng.random() < 0.4
                    if on and lit < 3:
                        pygame.draw.rect(surface, (54, 58, 82), (wx, wy, 7, 10))
                        lit += 1
                    elif on:
                        lit = 0
        if fire and rng.random() < 0.28:
            fx = bx + bw // 2
            pulse = 0.5 + 0.5 * math.sin(t * 0.006 + fx)
            _ko_glow(surface, (220, 120, 60), (fx, by + 6), 90, int(20 + 30 * pulse))
            for k in range(5):
                ph = ((t / 900.0) + k * 0.5) % 2.5
                a = max(0, int(70 * (1 - ph / 2.5)))
                if a:
                    r = int(8 + ph * 16)
                    pygame.draw.circle(surface, (70, 62, 58, a),
                                       (int(fx + math.sin(ph * 2 + k) * 10),
                                        int(by - ph * 46)), r)
    return buildings


def _figure(surface, who, cx, foot_y, scale, facing_right, t, color=None):
    """Silhouette of a cast member (m3ending._figure idiom). ``color`` tints
    the flat for the liaison/crest shots; black by default."""
    w = int(150 * scale) + 8
    h = int(320 * scale) + 8
    ts = pygame.Surface((w, h), pygame.SRCALPHA)
    if who == "vasile":
        draw_vasile(ts, w // 2, h - 6, scale=scale, facing_right=facing_right)
    else:
        draw_biribel(ts, w // 2, h - 6, scale=scale, facing_right=facing_right,
                     in_silhouette=True)
    flat = ts.copy()
    fill = color if color is not None else (6, 7, 11)
    flat.fill((*fill, 255), special_flags=pygame.BLEND_RGBA_MIN)
    bob = (math.sin(t * 0.006) + 1) * 0.8
    surface.blit(flat, (int(cx - ts.get_width() / 2),
                        int(foot_y - ts.get_height() + 6 - bob)))


def _draw_m4_city_curfew(surface, t):
    """The capital at its third curfew night: a skyline on fire it can't police."""
    surface.fill((9, 11, 18))
    _draw_vertical_gradient(surface, 0, SCENE_TOP, WIDTH, SAFE_BOT - SCENE_TOP,
                            (26, 22, 34), (7, 8, 13))
    rng = random.Random(2048)

    base_y = SAFE_BOT - 120
    _skyline(surface, base_y, rng, lit_runs=True, fire=True, t=t)

    # Searchlights sweeping the smoke - the regime's last visible authority.
    for i, sx in enumerate((WIDTH // 4, WIDTH // 2, 3 * WIDTH // 4)):
        ang = math.sin(t * 0.0016 + i * 1.9) * 0.5
        cone = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        top_w, bottom_w = 10, 150
        reach = base_y - SAFE_TOP
        cxp, cyp = sx, SAFE_TOP + 10
        pts = [(cxp - top_w // 2, cyp), (cxp + top_w // 2, cyp),
               (int(cxp + math.sin(ang) * reach + bottom_w // 2), cyp + reach),
               (int(cxp + math.sin(ang) * reach - bottom_w // 2), cyp + reach)]
        pygame.draw.polygon(cone, (200, 210, 235, 20), pts)
        surface.blit(cone, (0, 0))

    # Street: wet asphalt catching the burning, a lone checkpoint barrier.
    pygame.draw.rect(surface, (12, 12, 16), (0, base_y, WIDTH, HEIGHT - base_y))
    for y in range(base_y, HEIGHT, 22):
        pygame.draw.line(surface, (18, 18, 24), (0, y), (WIDTH, y), 1)
    _ko_glow(surface, (200, 90, 60), (WIDTH // 2, base_y + 10), 360, 40)
    for bx in (WIDTH // 2 - 160, WIDTH // 2 + 120):
        pygame.draw.rect(surface, (40, 36, 30), (bx, base_y - 26, 90, 34))
        pygame.draw.rect(surface, (66, 58, 46), (bx, base_y - 26, 90, 6))

    _draw_dust_motes(surface, t)
    _m3_noise(surface, 5151, count=70, alpha=20)
    _ko_tint(surface)
    _tag(surface, "THE CAPITAL // 48H CURFEW")


# One millisecond timeline owns blocking and editorial cuts. No render-time
# events: seeking, replaying, or holding SPACE can never repeat the arrest.
ARREST_CUFF_MS = 7900
ARREST_ESCORT_MS = 9400
ARREST_END_MS = 14800
_FILM_H = SAFE_BOT - SAFE_TOP


def _beat(t, start, length):
    return _m3_smooth(_m3_clamp01((t - start) / float(length)))


def arrest_camera(t, reduced_motion=False):
    """Broadcast camera sheet; cropping never changes physical blocking.

    Crops keep the same screen direction (president left, general right).
    The cuff insert compresses 400ms of action into a 2.2s editorial hold.
    Reduced motion keeps the cuts but removes dolly movement/contact shake.
    """
    t = max(0, min(float(t), ARREST_END_MS))
    if t < 2400:
        name, a, b, p = "establish", (500, 228, 1000), (510, 225, 910), _beat(t, 0, 2400)
    elif t < 4800:
        name, a, b, p = "president", (311, 147, 350), (310, 145, 320), _beat(t, 2400, 2400)
    elif t < 7200:
        name, a, b, p = "realization", (679, 152, 370), (677, 147, 336), _beat(t, 4800, 2400)
    elif t < 9400:
        name, a, b, p = "cuffs", (500, 228, 1000), (500, 228, 1000), 0
    elif t < 12400:
        name, a, b, p = "escort", (610, 235, 820), (670, 228, 910), _beat(t, 9400, 3000)
    else:
        name, a, b, p = "aftermath", (340, 180, 560), (320, 178, 510), _beat(t, 12400, 1000)
    if reduced_motion:
        p = 0
    cx, cy, w = (a[i] + (b[i] - a[i]) * p for i in range(3))
    h = w * _FILM_H / WIDTH
    return name, pygame.Rect(round(cx - w / 2), round(cy - h / 2), round(w), round(h))


@lru_cache(maxsize=1)
def _arrest_room():
    """Static palace set: cached so close-ups do not redraw architecture."""
    s = pygame.Surface((WIDTH, _FILM_H))
    _draw_vertical_gradient(s, 0, 0, WIDTH, _FILM_H, (37, 42, 53), (16, 19, 26))
    for x in (66, 184, 814, 932):
        pygame.draw.rect(s, (46, 47, 54), (x - 26, 0, 52, 342))
        pygame.draw.rect(s, (74, 66, 59), (x - 25, 0, 5, 342))
        pygame.draw.rect(s, (28, 33, 44), (x + 17, 0, 9, 342))
        for y in (34, 307):
            pygame.draw.rect(s, (101, 83, 60), (x - 33, y, 66, 8))
    # Regime-blue and red banners recall the earlier Route 12 address.
    for x in (242, 752):
        pygame.draw.polygon(s, (25, 35, 59), [(x - 29, 24), (x + 29, 24),
                            (x + 29, 258), (x, 277), (x - 29, 258)])
        pygame.draw.rect(s, (94, 32, 35), (x - 6, 24, 12, 226))
        pygame.draw.line(s, (150, 114, 67), (x - 32, 24), (x + 32, 24), 4)
    pygame.draw.rect(s, (14, 20, 30), (852, 109, 126, 265))
    pygame.draw.rect(s, (104, 83, 64), (851, 108, 128, 266), 3)
    pygame.draw.rect(s, (6, 10, 17), (863, 117, 102, 255))
    pygame.draw.circle(s, (161, 138, 95), (945, 245), 3)
    # Seal stays behind the president, never above the prisoner.
    pygame.draw.circle(s, (100, 79, 48), (322, 69), 39, 3)
    pygame.draw.circle(s, (50, 48, 46), (322, 69), 33)
    for dx in (-18, 0, 18):
        pygame.draw.polygon(s, (173, 141, 86), [(322 + dx, 45), (329 + dx, 75),
                            (322 + dx, 91), (315 + dx, 75)])
    pygame.draw.rect(s, (28, 28, 34), (0, 342, WIDTH, _FILM_H - 342))
    for y in (348, 362, 385, 420):
        pygame.draw.line(s, (58, 52, 48), (0, y), (WIDTH, y), 1)
    for x in range(-400, 1600, 155):
        pygame.draw.line(s, (45, 42, 44), (500 + (x - 500) * .35, 342), (x, _FILM_H), 1)
    # Broad feathered practical light, composited rather than opaque discs.
    _ko_glow(s, (245, 187, 119), (318, 155), 235, 32)
    _ko_glow(s, (104, 146, 191), (680, 182), 245, 27)
    return s


def _face(s, cx, cy, scale, *, fear=0, smile=0, look=0, blink=0, president=False):
    """Angular, receding-haired campaign faces with motivated key/rim light.

    Expressions deform brows, eyelids, jaw and mouth, not floating emoji.
    Balaceanu keeps his tan skin/dark hair; the president the navy suit.
    """
    def p(x, y):
        return round(cx + x * scale), round(cy + y * scale)
    def line(col, points, width=1):
        pygame.draw.lines(s, col, False, [p(x, y) for x, y in points], max(1, round(width * scale)))
    def poly(col, points):
        pygame.draw.polygon(s, col, [p(x, y) for x, y in points])
    skin = (198, 154, 115) if not president else (207, 168, 127)
    poly((111, 76, 60), [(-12, 26), (12, 26), (14, 43), (-14, 43)])
    poly(skin, [(-26, -18), (-20, -31), (-5, -36), (17, -31), (26, -20),
               (25, 12), (18, 27 + fear * 2), (4, 34 + fear * 2), (-15, 28), (-25, 9)])
    poly((133, 91, 76), [(8, -31), (26, -20), (25, 12), (18, 27),
                       (4, 34), (8, 15), (14, 2)])
    poly((235, 190, 139), [(-24, -17), (-15, -27), (-12, -5), (-20, 10), (-24, 8)])
    # Receding temples, swept hair, ears, under-eye fatigue and nasolabial crease.
    poly((40, 29, 29), [(-26, -5), (-29, -23), (-19, -34), (-5, -38),
                       (17, -33), (26, -23), (26, -8), (20, -21),
                       (10, -26), (-2, -29), (-18, -22), (-20, -5)])
    line((88, 69, 61), [(-23, -27), (-13, -33), (3, -33)], 2)
    pygame.draw.ellipse(s, (178, 123, 98), (*p(-31, -3), max(1, round(8 * scale)), max(1, round(16 * scale))))
    line((99, 61, 53), [(-26, 1), (-25, 9)], 1)
    line((156, 110, 91), [(-17, 6), (-7, 7)], 1)
    line((101, 67, 62), [(9, 6), (18, 5)], 1)
    # Fear brings the inner brows up; disdain weighs the president's outer lid.
    line((56, 37, 35), [(-19, -10), (-8, -10 - fear * 5)], 2)
    line((48, 32, 32), [(7, -10 - fear * 4), (18, -9 + smile * 2)], 2)
    eye_h = max(0.4, (3 + fear * 2) * (1 - blink))
    for x in (-13, 13):
        poly((219, 203, 173), [(x - 5, -3), (x, -3 - eye_h), (x + 5, -3), (x, -2 + eye_h)])
        pygame.draw.circle(s, (22, 25, 28), p(x + look * 2, -3), max(1, round(1.8 * scale)))
        line((77, 50, 47), [(x - 5, -4), (x + 5, -4)], 1)
    line((117, 73, 59), [(1, -6), (-2, 9), (5, 11)], 1.4)
    line((223, 172, 122), [(-2, -5), (-4, 6)], 1)
    line((119, 74, 66), [(-7, 14), (-11, 22)], 1)
    line((66, 39, 40), [(-10, 22), (0, 21 + fear * 3), (11, 22 - smile * 4)], 1.6)
    if fear > .5:
        line((69, 43, 41), [(-3, 24), (5, 24)], 1)
    line((157, 103, 80), [(-5, 28), (5, 28)], 1)
    line((137, 168, 191) if not president else (248, 202, 128), [(23, -15), (24, 9), (17, 24)], 1)
    if fear > .65:
        line((184, 193, 189), [(-22, -13), (-23, -6)], 1)  # a single sweat catchlight


def _official(s, who, cx, foot, t, arrest=0, moving=0):
    president = who == "president"
    step = math.sin(max(0, t - ARREST_ESCORT_MS) * .009) * moving
    breath = math.sin(t * .0023) * (1.1 if president else 1.8) * (1 - moving)
    slouch = arrest * 9
    head_y = foot - 258 + breath + slouch
    lean = -arrest * 5
    # Weight transfer is tied to physical movement, not the camera's zoom.
    pygame.draw.ellipse(s, (10, 13, 20), (cx - 51, foot - 5, 102, 13))
    for side in (-1, 1):
        hip = (cx + side * 15, foot - 104)
        knee = (cx + side * 17 + step * side * 7, foot - 49)
        shoe = (cx + side * 18 - step * side * 13, foot)
        pygame.draw.lines(s, (19, 23, 33), False, [hip, knee, shoe], 19)
        pygame.draw.line(s, (62, 63, 71), (hip[0] - 7, hip[1]), (knee[0] - 7, knee[1]), 2)
        pygame.draw.ellipse(s, (8, 10, 17), (shoe[0] - 15, shoe[1] - 4, 34, 9))
    body = (31, 40, 61) if president else (49, 38, 37)
    pygame.draw.polygon(s, body, [(cx - 47, head_y + 43), (cx - 25, head_y + 33),
                        (cx + 24, head_y + 33), (cx + 47, head_y + 46),
                        (cx + 37 + lean, foot - 95), (cx - 37 + lean, foot - 95)])
    pygame.draw.polygon(s, (112, 109, 107), [(cx - 21, head_y + 37), (cx, head_y + 73), (cx + 21, head_y + 37)])
    pygame.draw.polygon(s, (217, 203, 178), [(cx - 14, head_y + 35), (cx, head_y + 51), (cx + 14, head_y + 35)])
    pygame.draw.polygon(s, (174, 40, 42) if president else (135, 31, 28),
                        [(cx - 5, head_y + 48), (cx + 5, head_y + 48), (cx + 7, head_y + 100), (cx, head_y + 112), (cx - 6, head_y + 101)])
    for side in (-1, 1):
        pygame.draw.lines(s, (80, 81, 90) if president else (98, 73, 65), False,
                         [(cx + side * 23, head_y + 37), (cx + side * 31, head_y + 70), (cx + side * 9, head_y + 92)], 2)
        shoulder = (cx + side * 40, head_y + 51)
        wrist = (cx + side * (44 - arrest * 26), foot - 145 + arrest * 5)
        pygame.draw.lines(s, body, False, [shoulder, (cx + side * 50, foot - 171), wrist], 16)
        pygame.draw.circle(s, (172, 126, 94), wrist, 7)
    pygame.draw.line(s, (122, 107, 86), (cx - 46, head_y + 49), (cx - 36, foot - 103), 2)
    pygame.draw.circle(s, _CREST if president else (156, 113, 74), (cx - 24, head_y + 70), 3)
    blink = .92 if (president and 3450 < t < 3570) or (not president and 5100 < t < 5240) else 0
    _face(s, cx + lean, head_y, 1, fear=arrest, smile=_beat(t, 12400, 1200) if president else 0,
          look=0 if president else -_beat(t, 4700, 1100), blink=blink, president=president)


def _guard(s, cx, foot, t, side, reach=0, moving=0):
    step = math.sin(t * .009 + side) * moving
    for k in (-1, 1):
        pygame.draw.lines(s, (16, 25, 39), False,
                         [(cx + k * 12, foot - 106), (cx + k * 14 + k * step * 8, foot - 51),
                          (cx + k * 15 - k * step * 11, foot)], 18)
        pygame.draw.ellipse(s, (7, 11, 18), (cx + k * 15 - k * step * 11 - 14, foot - 4, 32, 10))
    pygame.draw.polygon(s, (27, 40, 58), [(cx - 40, foot - 228), (cx + 40, foot - 228),
                        (cx + 33, foot - 99), (cx - 33, foot - 99)])
    pygame.draw.line(s, (91, 102, 110), (cx - 33, foot - 221), (cx - 28, foot - 115), 2)
    pygame.draw.rect(s, (12, 18, 28), (cx - 36, foot - 118, 72, 9))
    pygame.draw.rect(s, (174, 155, 106), (cx - 5, foot - 116, 10, 6))
    _face(s, cx, foot - 261, .82, look=-side)
    pygame.draw.polygon(s, (19, 29, 46), [(cx - 29, foot - 280), (cx - 22, foot - 302),
                        (cx + 23, foot - 302), (cx + 29, foot - 280)])
    pygame.draw.line(s, (129, 133, 126), (cx - 27, foot - 281), (cx + 28, foot - 281), 2)
    pygame.draw.circle(s, (174, 144, 89), (cx, foot - 292), 3)
    for k in (-1, 1):
        shoulder = (cx + k * 34, foot - 217)
        wrist = (cx + k * 39, foot - 150)
        if k == -side:
            wrist = (cx + k * (39 + reach * 25), foot - 158 + reach * 9)
        pygame.draw.lines(s, (31, 46, 65), False, [shoulder, (cx + k * 44, foot - 179), wrist], 14)
        pygame.draw.circle(s, (25, 30, 34), wrist, 7)


def _arrest_world(t):
    s = _arrest_room().copy()
    approach = _beat(t, 4300, 2900)
    cuffs = _beat(t, 7480, 420)
    walk = _beat(t, ARREST_ESCORT_MS, 3200)
    move = 1 if ARREST_ESCORT_MS < t < 12600 else 0
    bx = 681 + walk * 410
    _guard(s, bx - 73 - (1 - approach) * 142, 404, t, -1, cuffs, move or (0 < approach < 1))
    _official(s, "general", bx, 400, t, _beat(t, 4750, 2000), move)
    _guard(s, bx + 73 + (1 - approach) * 123, 411, t, 1, cuffs, move or (0 < approach < 1))
    _official(s, "president", 318, 400, t)
    # The lectern divides power from custody and hides only the president's legs.
    pygame.draw.polygon(s, (61, 45, 40), [(232, 286), (401, 286), (391, 415), (244, 415)])
    pygame.draw.polygon(s, (120, 90, 59), [(225, 282), (407, 282), (398, 293), (235, 293)])
    pygame.draw.line(s, (178, 140, 89), (233, 287), (401, 287), 2)
    pygame.draw.circle(s, (160, 129, 78), (318, 344), 29, 2)
    seal = font_terminal_small.render(_T("m4aftermath.ipa_state"), True, _CREST)
    s.blit(seal, (318 - seal.get_width() // 2, 337))
    for x in (296, 336):
        pygame.draw.lines(s, (10, 14, 21), False, [(x, 284), (x - 5, 255), (x - 2, 246)], 3)
        pygame.draw.ellipse(s, (17, 20, 24), (x - 8, 238, 12, 17))
    if cuffs:
        pygame.draw.line(s, (172, 176, 177), (bx - 17, 262), (bx + 17, 262), 2)
        for x in (bx - 17, bx + 17):
            pygame.draw.ellipse(s, (196, 203, 203), (x - 7, 253, 14, 17), 2)
    return s


def _cuff_insert(t):
    """Slow, legible contact: gloved hands close real hinged steel cuffs."""
    s = pygame.Surface((WIDTH, _FILM_H))
    _draw_vertical_gradient(s, 0, 0, WIDTH, _FILM_H, (38, 42, 52), (10, 15, 24))
    _ko_glow(s, (133, 164, 184), (515, 198), 370, 35)
    settle = _beat(t, 7200, 700)
    # Suited forearms tense at the wrists; gloves enter from opposite sides.
    for side in (-1, 1):
        x = 500 + side * 109
        pygame.draw.polygon(s, (52, 39, 39), [(x - 63, 425), (x + 62, 425),
                            (x + 46, 212), (x - 43, 212)])
        pygame.draw.polygon(s, (102, 78, 68), [(x - 56, 420), (x - 48, 243), (x - 38, 218), (x - 34, 420)])
        pygame.draw.rect(s, (210, 199, 174), (x - 38, 207, 76, 19))
        pygame.draw.polygon(s, (183, 134, 99), [(x - 33, 211), (x - 31, 159),
                            (x - 22, 139), (x + 28, 145), (x + 35, 205)])
        pygame.draw.line(s, (223, 172, 127), (x - 25, 200), (x - 23, 157), 4)
        gx = x + side * (168 - settle * 96)
        pygame.draw.polygon(s, (23, 32, 45), [(gx + side * 230, 147), (gx, 154),
                            (gx - side * 52, 175), (gx - side * 51, 207), (gx + side * 225, 238)])
        for k in range(3):
            pygame.draw.line(s, (63, 71, 77), (gx - side * 35, 169 + k * 11),
                             (gx + side * 10, 164 + k * 13), 5)
        cuff = pygame.Rect(x - 48, 185, 96, 57)
        pygame.draw.ellipse(s, (41, 52, 64), cuff, 12)
        pygame.draw.arc(s, (185, 198, 204), cuff, .08, math.pi + .22, 7)
        pygame.draw.arc(s, (108, 126, 142), cuff, math.pi + .22, math.tau, 6)
        close = _beat(t, ARREST_CUFF_MS - 20 + (side + 1) * 100, 200)
        pygame.draw.line(s, (203, 211, 214), (x - 43, 206), (x + 42, 156 + close * 55), 6)
        for k in range(4):
            pygame.draw.line(s, (68, 81, 94), (x + 25 + k * 4, 206), (x + 25 + k * 4, 216), 1)
    # Short chain hangs under gravity; no spark shower or gunshot language.
    for i in range(7):
        x = 443 + i * 16
        y = 225 + math.sin(i / 6 * math.pi) * (18 + (1 - settle) * 12)
        pygame.draw.ellipse(s, (143, 160, 172), (x - 11, y - 5, 22, 10), 3)
        pygame.draw.arc(s, (225, 225, 209), (x - 11, y - 5, 22, 10), 0, math.pi, 1)
    return s


def _camera_frame(world, rect):
    frame = pygame.Surface((rect.w, rect.h))
    frame.fill((8, 12, 19))
    frame.blit(world, (-rect.x, -rect.y))
    # Nearest-neighbour maintains the game's intentional hard-edged line art.
    return pygame.transform.scale(frame, (WIDTH, _FILM_H))


@lru_cache(maxsize=4)
def _film_shade(size, strength=64):
    w, h = size
    shade = pygame.Surface(size, pygame.SRCALPHA)
    for i in range(20):
        a = int(strength * ((20 - i) / 20) ** 2 / 5)
        pygame.draw.rect(shade, (3, 9, 19, a), (i * w // 70, i * h // 65,
                         w - i * w // 35, h - i * h // 32), max(1, w // 70))
    return shade


def _film_finish(frame, t, warm=False):
    # Split-tone grade: steel shadows, restrained amber practical highlights.
    frame.fill((250, 244, 230) if warm else (234, 241, 253), special_flags=pygame.BLEND_RGB_MULT)
    frame.blit(_film_shade(frame.get_size(), 46 if warm else 68), (0, 0))
    dust = pygame.Surface(frame.get_size(), pygame.SRCALPHA)
    for i in range(18):
        x = (71 + i * 137 + math.sin(t * .0004 + i) * 7) % WIDTH
        y = (31 + i * 79 - t * .006) % _FILM_H
        pygame.draw.circle(dust, (211, 191, 150, 28), (int(x), int(y)), 1)
    frame.blit(dust, (0, 0))


def _draw_m4_arrest_screen(surface, t):
    """A six-angle arrest on the public CRT; power survives its scapegoat.

    President/general/guards only. Biribel remains absent from the broadcast.
    All action settles by 14.8s, leaving a stable frame for input-paced reading.
    """
    t = max(0, min(t, ARREST_END_MS))
    reduced = bool(getattr(STATE, "reduced_motion", False))
    angle, rect = arrest_camera(t, reduced)
    frame = (_camera_frame(_cuff_insert(t), pygame.Rect(220, 75, 560, round(560 * _FILM_H / WIDTH)))
             if angle == "cuffs" else _camera_frame(_arrest_world(t), rect))
    _film_finish(frame, t)
    # Minimal contact jolt, not an explosion. Never present in reduced motion.
    if not reduced and ARREST_CUFF_MS <= t < ARREST_CUFF_MS + 130:
        shift = round(math.sin((t - ARREST_CUFF_MS) * .08) * 2 * (1 - (t - ARREST_CUFF_MS) / 130))
        frame.scroll(shift, 0)
    # Reveal/withdraw the actual public monitor, retaining the original square.
    surround = 1 - _beat(t, 0, 2200) if t < 2400 else _beat(t, 13400, 1400)
    if reduced:
        surround = 1 if t < 2400 or t >= 13400 else 0
    mw = round(WIDTH - 300 * surround)
    mh = round(_FILM_H - 142 * surround)
    mx, my = (WIDTH - mw) // 2, SAFE_TOP + round(18 * surround)
    surface.fill((7, 10, 17))
    _ko_glow(surface, (83, 118, 151), (WIDTH // 2, SAFE_TOP + 220), 450, 22)
    pygame.draw.rect(surface, (21, 29, 39), (mx - 12, my - 10, mw + 24, mh + 20), border_radius=6)
    pygame.draw.rect(surface, (98, 106, 112), (mx - 12, my - 10, mw + 24, mh + 20), 2, border_radius=6)
    feed = pygame.transform.scale(frame, (mw, mh))
    # Feed UI is clipped to the tube, not an unbounded crawl across actors.
    ui = pygame.Surface((mw, mh), pygame.SRCALPHA)
    pygame.draw.circle(ui, (220, 67, 57), (22, 20), 3)
    cap = font_terminal_small.render(_T("m4aftermath.state_live"), True, (218, 217, 200))
    ui.blit(cap, (34, 12))
    if t >= 4300:
        pygame.draw.rect(ui, (18, 23, 33, 231), (0, mh - 33, mw, 33))
        label = "GENERAL BALACEANU / RELIEVED OF COMMAND" if t < 9400 else "ARRESTED ON THE PRESIDENT'S ORDER"
        text = font_terminal_small.render(label, True, _ARREST if t < 12400 else _CREST)
        ui.blit(text, (max(12, (mw - text.get_width()) // 2), mh - 25))
    for y in range(0, mh, 4):
        pygame.draw.line(ui, (0, 0, 0, 17), (0, y), (mw, y))
    feed.blit(ui, (0, 0))
    surface.blit(feed, (mx, my))
    if surround > .1:
        crowd = pygame.Surface((WIDTH, _FILM_H), pygame.SRCALPHA)
        for i in range(23):
            px = 8 + i * 45
            py = _FILM_H - 34 - (i * 13 % 20)
            pygame.draw.circle(crowd, (5, 8, 14), (px, py), 12)
            pygame.draw.polygon(crowd, (5, 8, 14), [(px - 17, py + 15), (px + 17, py + 15),
                                (px + 24, _FILM_H), (px - 24, _FILM_H)])
            if i % 4 == 0 and t > 12400:
                pygame.draw.lines(crowd, (5, 8, 14), False, [(px - 12, py + 17), (px - 26, py - 5), (px - 19, py - 22)], 7)
        crowd.set_alpha(round(255 * surround))
        surface.blit(crowd, (0, SAFE_TOP))
        crest = font_terminal_small.render(_T("m4aftermath.long_live_the_president"), True, _CREST)
        crest.set_alpha(round(255 * surround))
        surface.blit(crest, ((WIDTH - crest.get_width()) // 2, SAFE_BOT - 96))


def _draw_m4_maru_silhouette(surface, t):
    """The liaison in the transmitter hall. Maru was a voice for three
    missions; this is the first time the team sees the shape of him."""
    surface.fill((7, 9, 12))
    _draw_vertical_gradient(surface, 0, SCENE_TOP, WIDTH, SAFE_BOT - SCENE_TOP,
                            (14, 22, 22), (5, 7, 8))
    floor_y = SAFE_BOT
    pygame.draw.rect(surface, (15, 18, 20), (0, floor_y, WIDTH, HEIGHT - floor_y))
    for y in range(floor_y, HEIGHT, 26):
        pygame.draw.line(surface, (22, 26, 28), (0, y), (WIDTH, y), 1)

    # Transmitter racks behind, status LEDs pulsing in liaison green.
    for i in range(5):
        rx = 120 + i * 210
        pygame.draw.rect(surface, (24, 28, 34), (rx, SAFE_TOP + 70, 150, floor_y - SAFE_TOP - 80))
        pygame.draw.rect(surface, (40, 46, 54), (rx, SAFE_TOP + 70, 150, 12))
        for r in range(7):
            on = 0.5 + 0.5 * math.sin(t * 0.004 + i + r * 0.7)
            pygame.draw.circle(surface, (int(60 + 140 * on), 220, int(120 + 60 * on)),
                               (rx + 24, SAFE_TOP + 108 + r * 26), 4)
        _ko_glow(surface, _LIAISON, (rx + 75, SAFE_TOP + 130), 120, int(8 + 12 * on))

    # Maru, a still hooded figure lit only by the racks.
    cx = WIDTH // 2 + 40
    _ko_glow(surface, (80, 148, 129), (cx, floor_y - 174), 185, 22)
    _figure(surface, "biribel", cx, floor_y, 0.90, facing_right=False, t=t,
            color=(16, 23, 29))

    # One cold CRT reflects the president's satisfied face over Maru's shoulder.
    monitor = pygame.Surface((168, 120))
    monitor.fill((23, 31, 41))
    _face(monitor, 84, 51, 1.2, smile=.8, president=True)
    pygame.draw.rect(monitor, (32, 42, 59), (38, 96, 92, 24))
    surface.blit(monitor, (WIDTH // 2 - 254, SAFE_TOP + 82))
    pygame.draw.rect(surface, (87, 91, 93), (WIDTH // 2 - 257, SAFE_TOP + 79, 174, 126), 2)
    # Maru stays an anonymous hooded liaison, not a newly invented cast face.
    # Hood/jaw incline and a held exhale make the silence a performance.
    incline = _beat(t, 900, 3100)
    hx, hy = cx - 3 * incline, floor_y - 212 + 6 * incline
    pygame.draw.polygon(surface, (12, 23, 29), [(hx - 26, hy - 15), (hx - 19, hy - 33),
                        (hx + 6, hy - 40), (hx + 27, hy - 21), (hx + 28, hy + 23), (hx - 26, hy + 24)])
    pygame.draw.polygon(surface, (48, 58, 57), [(hx - 20, hy - 13), (hx - 9, hy - 24),
                        (hx + 6, hy - 22), (hx + 14, hy - 7), (hx + 9, hy + 18), (hx - 5, hy + 22), (hx - 19, hy + 8)])
    pygame.draw.polygon(surface, (10, 19, 25), [(hx + 3, hy - 25), (hx + 16, hy - 6),
                        (hx + 9, hy + 18), (hx - 5, hy + 22), (hx + 1, hy + 2)])
    pygame.draw.line(surface, (94, 134, 127), (hx - 23, hy - 14), (hx - 19, hy + 9), 2)
    pygame.draw.line(surface, (19, 24, 27), (hx - 15, hy - 4), (hx - 6, hy - 6), 2)
    pygame.draw.line(surface, (29, 33, 33), (hx - 13, hy + 12), (hx - 4, hy + 13), 1)
    _draw_dust_motes(surface, t)
    _m3_noise(surface, 4004, count=64, alpha=18)
    _push_safe(surface, 1 + .13 * _beat(t, 0, 5200), (WIDTH // 2 + 15, SAFE_TOP + 240), t=t)
    _tag(surface, "TRANSMITTER HALL // THE MEET", _LIAISON)


def _push_safe(surface, zoom, focus, warm=False, t=0):
    """Crop only picture, never letterbox/subtitles; accessibility locks dolly."""
    frame = surface.subsurface((0, SAFE_TOP, WIDTH, _FILM_H)).copy()
    if not getattr(STATE, "reduced_motion", False):
        w, h = round(WIDTH / zoom), round(_FILM_H / zoom)
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (round(focus[0]), round(focus[1] - SAFE_TOP))
        rect.clamp_ip(frame.get_rect())
        frame = pygame.transform.scale(frame.subsurface(rect), (WIDTH, _FILM_H))
    _film_finish(frame, t, warm=warm)
    surface.blit(frame, (0, SAFE_TOP))


def _draw_m4_roof_dawn(surface, t):
    """Studio roof, first light. The curfew lifts on a city that cheered the
    wrong man; Biribel decides to stay. This is the closing frame."""
    surface.fill((20, 18, 26))
    t = max(0, min(t, 14200))
    warm = .35 + .65 * _beat(t, 0, 12000)
    _draw_vertical_gradient(surface, 0, SCENE_TOP, WIDTH, SAFE_BOT - SCENE_TOP,
                            (int(26 + 90 * warm), int(22 + 60 * warm), 40),
                            (10, 10, 16))

    # Sun clearing the skyline on the horizon line.
    sun_x = round(WIDTH * .74)
    sun_y = SAFE_BOT - 214 - round(10 * _beat(t, 0, 14200))
    for r in range(70, 0, -4):
        a = max(0, 90 - r)
        glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 190, 120, a), (r, r), r)
        surface.blit(glow, (sun_x - r, sun_y - r))
    pygame.draw.circle(surface, _DAWN, (sun_x, sun_y), 34)

    # Distant haze silhouettes add depth without regenerating gameplay art.
    far = pygame.Surface((WIDTH, _FILM_H), pygame.SRCALPHA)
    rng_far = random.Random(709)
    for x in range(-20, WIDTH, 43):
        h = rng_far.randint(40, 130)
        pygame.draw.rect(far, (117, 92, 90, 54), (x, _FILM_H - 168 - h, 38, h + 110))
    surface.blit(far, (0, SAFE_TOP))
    rng = random.Random(707)
    base_y = SAFE_BOT - 96
    _skyline(surface, base_y, rng, lit_runs=False, fire=False, t=t, height_scale=.58)
    # Smoke settles as the burning dies out overnight.
    _ko_glow(surface, (120, 90, 70), (WIDTH // 3, base_y - 40), 260, 22)

    # Roof edge the two of them stand on, foreground.
    pygame.draw.rect(surface, (12, 11, 15), (0, SAFE_BOT, WIDTH, HEIGHT - SAFE_BOT))
    pygame.draw.rect(surface, (30, 28, 34), (0, SAFE_BOT - 8, WIDTH, 10))
    for x in range(0, WIDTH, 60):
        pygame.draw.line(surface, (20, 19, 24), (x, SAFE_BOT), (x, HEIGHT), 2)

    _figure(surface, "biribel", WIDTH // 2 - 90, SAFE_BOT + 6, 0.90,
            facing_right=True, t=t, color=(17, 20, 27))
    _figure(surface, "vasile", WIDTH // 2 + 106, SAFE_BOT + 6, 0.86,
            facing_right=True, t=t, color=(17, 20, 27))
    _draw_dust_motes(surface, t)
    _m3_noise(surface, 331, count=52, alpha=14)
    # Both cast silhouettes keep their original design. A held shoulder line
    # settles after the exhale; subtle warm rims separate them from the roof.
    for x, y, side in ((WIDTH // 2 - 90, SAFE_BOT - 207, -1),
                       (WIDTH // 2 + 106, SAFE_BOT - 198, 1)):
        pygame.draw.lines(surface, (118, 90, 70), False,
                          [(x + 11, y - 5), (x + 21, y + 17), (x + 26, y + 51)], 1)
    _push_safe(surface, 1.13 - .13 * _beat(t, 0, 14200),
               (WIDTH // 2, SAFE_TOP + _FILM_H // 2), warm=True, t=t)
    _tag(surface, "SUNRISE // THE CURFEW LIFTS", _DAWN)


# RPE6 Phase 2 (A-003 take registry): the cutscene scene ids this module owns.
# cutscenes.engine.draw_cutscene_scene finds them through core.cutscene_registry
# instead of importing this module by name (boundary rule 4 / W1).
from core.cutscene_registry import register_scene_renderers as _register_takes  # noqa: E402
from engine.text import T as _T  # RPE6 Phase 4 text table

_register_takes({
    "m4_city_curfew": _draw_m4_city_curfew,
    "m4_arrest_screen": _draw_m4_arrest_screen,
    "m4_maru_silhouette": _draw_m4_maru_silhouette,
    "m4_roof_dawn": _draw_m4_roof_dawn,
})
