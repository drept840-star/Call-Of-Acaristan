
"""m3ending.py - Mission 3 finale cutscene (the Vostral read live on air).

Four bespoke shots replace the old single title card:

  1. m3_end_studio       - over Biribel's shoulder at the booth, the address
                           playing on the studio wall while she works.
  2. m3_end_cut          - the feed dies mid-sentence and the record takes it.
  3. m3_end_nation       - the Vostral on every screen in Acaristan, 22:07.
  4. m3_end_booth_dark   - booth aftermath: red emergency light, OFF AIR.
  5. title_card          - closing line (engine's existing title renderer).

Purely procedural, in the same visual language as m3ko / m3broadcast.

LAYOUT RULE: the dialogue box owns the bottom ~150px, so every wide shot
composes inside SAFE_TOP..SAFE_BOT. Shooting into that band hides the
performers behind the caption.
"""
import math
import random

import pygame

from core.config import (HEIGHT, SCENE_BOT, SCENE_TOP, WIDTH, font_terminal, font_terminal_small)

from cutscenes.m3ko import _ko_actor, _ko_clamp01, _ko_glow, _ko_tag, _ko_tint
from cutscenes.m3cell import _m3_clamp01, _m3_noise, _m3_smooth
from cutscenes.chair import _draw_dust_motes
from cutscenes.route12 import _draw_vertical_gradient, _lerp_cutscene

_ONAIR = (255, 70, 62)
_RECORD = (120, 235, 165)

SAFE_TOP = SCENE_TOP + 6
SAFE_BOT = HEIGHT - 158   # dialogue box ceiling


def _pool(surface, cx, cy, rx, ry, color, alpha, steps=16):
    """Soft elliptical floor pool.

    Must composite through an SRCALPHA layer: drawing a 4-tuple straight onto
    the display surface drops the alpha channel and yields a hard opaque disc.
    Falls off in rings so the edge never reads as a pasted circle.
    """
    if alpha <= 0:
        return
    layer = pygame.Surface((int(rx * 2) + 2, int(ry * 2) + 2), pygame.SRCALPHA)
    for i in range(steps, 0, -1):
        f = i / steps
        a = int(alpha * (1.0 - f) ** 2.2)
        if a <= 0:
            continue
        w, h = int(rx * 2 * f), int(ry * 2 * f)
        pygame.draw.ellipse(layer, (color[0], color[1], color[2], a),
                            pygame.Rect(layer.get_width() // 2 - w // 2,
                                        layer.get_height() // 2 - h // 2, w, h))
    surface.blit(layer, (int(cx - layer.get_width() / 2),
                         int(cy - layer.get_height() / 2)))


def _tag(surface, text):
    """Location tag pinned to the top of the safe area (the shared _ko_tag
    sits at HEIGHT-250, which lands on the performers in these shots)."""
    surf = font_terminal_small.render(text, True, (120, 200, 220))
    surface.blit(surf, (WIDTH // 2 - surf.get_width() // 2, SAFE_TOP + 2))


def _figure(surface, who, cx, foot_y, scale, facing_right, t):
    """True black silhouette. ``_ko_actor(silhouette=True)`` only darkens
    Biribel - draw_volkov takes no such flag, so mixed crowds came out half
    coloured. Flattens whatever the cast draws against its own alpha."""
    import cutscenes.cast as _cast
    w = int(150 * scale) + 8
    h = int(320 * scale) + 8
    ts = pygame.Surface((w, h), pygame.SRCALPHA)
    if who == "volkov":
        _cast.draw_volkov(ts, w // 2, h - 6, scale=scale,
                          facing_right=facing_right)
    else:
        _cast.draw_biribel(ts, w // 2, h - 6, scale=scale,
                           facing_right=facing_right, in_silhouette=True)
    # Flatten the sprite against its own coverage.
    flat = ts.copy()
    flat.fill((6, 7, 11, 255), special_flags=pygame.BLEND_RGBA_MIN)
    bob = (math.sin(t * 0.006) + 1) * 0.8
    surface.blit(flat, (int(cx - ts.get_width() / 2),
                        int(foot_y - ts.get_height() + 6 - bob)))

def _end_screens(surface, t, count=3, y=None, flip_at=None, dark=False):
    """Wall of studio monitors. With ``flip_at`` they turn from the address to
    the record at that millisecond; ``dark`` kills them for the aftermath."""
    y = SAFE_TOP + 74 if y is None else y
    flip = 0.0 if flip_at is None else _m3_smooth(_m3_clamp01((t - flip_at) / 900.0))
    gap = 30
    sw = 236
    sh = 148
    total = count * sw + (count - 1) * gap
    x0 = (WIDTH - total) // 2
    for i in range(count):
        x = x0 + i * (sw + gap)
        pygame.draw.rect(surface, (16, 14, 19), (x, y, sw, sh))
        pygame.draw.rect(surface, (92, 86, 99), (x, y, sw, sh), 2)
        pygame.draw.rect(surface, (58, 52, 64), (x, y, sw, 10))
        inner = pygame.Rect(x + 8, y + 16, sw - 16, sh - 24)
        if dark:
            pygame.draw.rect(surface, (13, 13, 17), inner)
            pygame.draw.line(surface, (24, 24, 30), inner.topleft, inner.bottomright, 1)
            continue
        showing_record = flip >= 0.5
        base = (12, 44, 28) if showing_record else (44, 13, 13)
        pygame.draw.rect(surface, base, inner)
        if not showing_record:
            # The address: podium silhouette + a caption crawl bar.
            pygame.draw.rect(surface, (104, 56, 50), (inner.centerx - 26, inner.y + 20, 52, 62))
            pygame.draw.circle(surface, (140, 80, 70), (inner.centerx, inner.y + 15), 13)
            for r in range(3):
                pygame.draw.line(surface, (168, 90, 78),
                                 (inner.x + 12, inner.bottom - 16 - r * 9),
                                 (inner.right - 12, inner.bottom - 16 - r * 9), 2)
        else:
            # The record: a service-record page, stamped and dated.
            pg = pygame.Rect(inner.x + 30, inner.y + 12, inner.w - 60, inner.h - 24)
            pygame.draw.rect(surface, (226, 218, 192), pg)
            for r in range(6):
                pygame.draw.line(surface, (74, 74, 84),
                                 (pg.x + 8, pg.y + 12 + r * 13),
                                 (pg.right - 8, pg.y + 12 + r * 13), 1)
            pygame.draw.circle(surface, (184, 52, 46), (pg.right - 16, pg.bottom - 16), 12, 2)
        _ko_glow(surface, _RECORD if showing_record else _ONAIR,
                 (x + sw // 2, y + sh // 2), 120,
                 14 if not showing_record else 24)


def _end_console(surface, cx, foot_y, t, lit=True):
    """The booth desk with the retro PC (seen from the operator's side)."""
    w, h = 210, 82
    top = foot_y - h
    pygame.draw.rect(surface, (46, 42, 55), (cx - w // 2, top, w, h))
    pygame.draw.rect(surface, (78, 72, 92), (cx - w // 2, top, w, h), 2)
    pygame.draw.rect(surface, (28, 26, 34), (cx - w // 2, foot_y - 10, w, 10))
    case_w, case_h = 84, 62
    case_x, case_y = cx - case_w // 2, top - case_h + 10
    pygame.draw.rect(surface, (152, 143, 115), (case_x, case_y, case_w, case_h))
    pygame.draw.rect(surface, (112, 104, 80), (case_x, case_y, case_w, case_h), 2)
    pygame.draw.rect(surface, (32, 30, 24), (case_x + 9, case_y + 9,
                                            case_w - 18, case_h - 18))
    if lit:
        pulse = 0.5 + 0.5 * math.sin(t * 0.006)
        col = (int(64 + 74 * pulse), 205, int(124 + 62 * pulse))
        pygame.draw.rect(surface, col, (case_x + 14, case_y + 14,
                                        case_w - 28, case_h - 28))
        for r in range(4):
            pygame.draw.line(surface, (12, 40, 24),
                             (case_x + 20, case_y + 24 + r * 9),
                             (case_x + case_w - 20, case_y + 24 + r * 9), 1)
        _ko_glow(surface, (90, 235, 150), (cx, case_y + case_h // 2), 190,
                 int(26 + 24 * pulse))
    for i in range(6):
        pygame.draw.rect(surface, (88, 82, 62),
                         (cx - 70 + i * 23, top + 50, 18, 11))
    for i in range(3):
        pygame.draw.rect(surface, (124, 62, 52),
                         (cx + 58, top + 22 + i * 13, 28, 8))
    _pool(surface, cx, foot_y + 6, 150, 26, _RECORD, 34 if lit else 12)


def _draw_m3_end_studio(surface, t):
    """Over Biribel's shoulder: the booth, the PC, the address on the wall."""
    surface.fill((14, 12, 17))
    _draw_vertical_gradient(surface, 0, SCENE_TOP, WIDTH, SCENE_BOT - SCENE_TOP,
                            (30, 25, 34), (11, 10, 14))
    floor_y = SAFE_BOT

    pygame.draw.rect(surface, (32, 29, 38), (0, SCENE_TOP, WIDTH, floor_y - SCENE_TOP))
    for x in range(0, WIDTH, 52):
        pygame.draw.line(surface, (21, 19, 26), (x, SCENE_TOP), (x + 52, floor_y), 1)
    pygame.draw.rect(surface, (40, 36, 47), (0, SCENE_TOP, WIDTH, 28))
    for i in range(5):
        lx = 110 + i * 320
        pygame.draw.rect(surface, (62, 54, 46), (lx - 30, SCENE_TOP + 14, 60, 11))
        _ko_glow(surface, (255, 200, 140), (lx, SCENE_TOP + 28), 150, 22)

    # The address is still running: no flip in this shot.
    _end_screens(surface, t, count=3, y=SAFE_TOP + 62)

    pygame.draw.rect(surface, (19, 17, 23), (0, floor_y, WIDTH, HEIGHT - floor_y))
    for y in range(floor_y, HEIGHT, 24):
        pygame.draw.line(surface, (25, 23, 30), (0, y), (WIDTH, y), 1)
    _pool(surface, WIDTH // 2 + 40, floor_y + 6, 330, 40, (210, 120, 100), 40)
    _pool(surface, WIDTH // 2 + 150, floor_y - 6, 130, 30, _RECORD, 46)

    # Volkov holds the aisle behind her; Biribel is at the booth console.
    _ko_actor(surface, "volkov", WIDTH // 2 - 250, floor_y, scale=0.66,
              facing_right=True, t=t, moving=False, walk_phase=0.0)
    _end_console(surface, WIDTH // 2 + 150, floor_y, t, lit=True)
    _ko_actor(surface, "biribel", WIDTH // 2 + 34, floor_y, scale=0.66,
              facing_right=True, t=t, moving=False, walk_phase=0.0)
    _draw_dust_motes(surface, t)
    _m3_noise(surface, 5501, count=70, alpha=20)
    _ko_tint(surface)
    _tag(surface, "BROADCAST WING // FEED LIVE")


def _draw_m3_end_cut(surface, t):
    """The address dies mid-word and the record replaces it."""
    surface.fill((8, 7, 10))
    _draw_vertical_gradient(surface, 0, SCENE_TOP, WIDTH, SCENE_BOT - SCENE_TOP,
                            (18, 15, 19), (6, 6, 9))

    cut = _m3_smooth(_m3_clamp01(t / 700.0))
    cx, cy = WIDTH // 2, (SAFE_TOP + SAFE_BOT) // 2

    # Feed tearing: short random runs, not an even ruled grid.
    rng = random.Random(4242)
    for _ in range(30):
        yy = rng.randint(SCENE_TOP, SAFE_BOT)
        wdt = rng.randint(40, 420)
        xx = rng.randint(-60, WIDTH - 40)
        hgt = rng.randint(1, 6)
        tone = rng.random()
        col = ((int(40 + 70 * tone), 22, 26) if rng.random() < 0.7
               else (int(20 + 30 * tone), int(60 + 50 * tone), 44))
        off = int(math.sin(t * 0.03 + yy) * 10 * (1.0 - cut))
        pygame.draw.rect(surface, col, (xx + off, yy, wdt, hgt))
    if cut < 0.9:
        sweep = int(SAFE_BOT - cut * (SAFE_BOT - SCENE_TOP))
        pygame.draw.rect(surface, (215, 220, 225), (0, sweep, WIDTH, 3))

    card_w, card_h = 460, 168
    card = pygame.Rect(cx - card_w // 2, cy - card_h // 2, card_w, card_h)
    seg = 6
    sh = card_h // seg
    for i in range(seg):
        row_off = int(math.sin(t * 0.02 + i * 1.7) * (1.0 - cut) * 18)
        col = (20, 48, 34) if i in (2, 3) else (36, 11, 13)
        pygame.draw.rect(surface, col, (card.x + row_off, card.y + i * sh,
                                        card_w, sh - 2))
    pygame.draw.rect(surface, (150, 60, 52), card, 2)
    tag = font_terminal_small.render(_T("m3ending.state_address_22_00"), True, (206, 96, 86))
    surface.blit(tag, (card.x + 16, card.y + 12))
    if cut > 0.45:
        seal = font_terminal.render(_T("m3ending.signal_lost"), True, _RECORD)
        surface.blit(seal, (cx - seal.get_width() // 2, cy - 18))
        _pool(surface, cx, cy, 300, 90, _RECORD, 30)
    _m3_noise(surface, 991, count=90, alpha=24)
    _ko_tint(surface)
    _tag(surface, "CARRIER LOST // VOSTRAL ON AIR")


def _draw_m3_end_nation(surface, t):
    """Acaristan at night: every screen in the street is showing the record."""
    surface.fill((9, 11, 18))
    _draw_vertical_gradient(surface, 0, SCENE_TOP, WIDTH, SCENE_BOT - SCENE_TOP,
                            (18, 22, 38), (8, 9, 14))

    rng = random.Random(77)
    skyline = []
    x = -20
    while x < WIDTH + 20:
        bw = rng.randint(58, 104)
        bh = rng.randint(120, 330)
        skyline.append((x, bw, bh))
        x += bw + rng.randint(4, 16)

    base_y = SAFE_BOT - 178
    for bx, bw, bh in skyline:
        by = base_y - bh
        pygame.draw.rect(surface, (15, 18, 27), (bx, by, bw, bh + 120))
        pygame.draw.rect(surface, (21, 25, 36), (bx, by, bw, 3))
        # Window grid - lit cells in runs, not scattered dots.
        for wy in range(by + 14, base_y - 8, 20):
            lit = 0
            for wx in range(bx + 9, bx + bw - 11, 16):
                run_on = rng.random() < 0.42
                col = None
                if run_on and lit < 3:
                    col = (56, 60, 84)
                    lit += 1
                elif run_on:
                    lit = 0
                if col:
                    pygame.draw.rect(surface, col, (wx, wy, 8, 11))
        if rng.random() < 0.4:
            lamp = font_terminal_small.render(_T("m3ending.vostral"), True, (86, 150, 118))
            lx = bx + bw // 2 - lamp.get_width() // 2
            surface.blit(lamp, (lx, by - 20))
            _ko_glow(surface, _RECORD, (bx + bw // 2, by - 12), 70, 14)

    # Street level: shopfront CRTs, all carrying the record. Sits above the
    # caption band; the crowd in front of them is drawn after.
    street_y = base_y + 8
    for i in range(6):
        x = 24 + i * 166
        sw, sh = 146, 78
        pygame.draw.rect(surface, (11, 13, 19), (x, street_y, sw, sh))
        pygame.draw.rect(surface, (68, 74, 88), (x, street_y, sw, sh), 2)
        pulse = 0.5 + 0.5 * math.sin(t * 0.004 + i)
        inner = pygame.Rect(x + 7, street_y + 7, sw - 14, sh - 14)
        pygame.draw.rect(surface, (int(18 + 32 * pulse), 64, int(38 + 26 * pulse)), inner)
        pg = pygame.Rect(inner.x + 18, inner.y + 7, inner.w - 36, inner.h - 14)
        pygame.draw.rect(surface, (222, 214, 190), pg)
        for r in range(3):
            pygame.draw.line(surface, (76, 76, 86), (pg.x + 6, pg.y + 9 + r * 11),
                             (pg.right - 6, pg.y + 9 + r * 11), 1)
        pygame.draw.circle(surface, (188, 54, 48), (pg.right - 9, pg.bottom - 8), 7, 2)
        _ko_glow(surface, _RECORD, (x + sw // 2, street_y + sh // 2), 96,
                 int(14 + 12 * pulse))
    _pool(surface, WIDTH // 2, street_y + 86, 620, 34, _RECORD, 40)

    # Foreground: onlookers, silhouetted, standing in front of the wall.
    for i, sx in enumerate((128, 356, 700, 902)):
        _figure(surface, "biribel" if i % 2 else "volkov", sx, SAFE_BOT + 4,
                0.5, i % 2 == 0, t)
    _draw_dust_motes(surface, t)
    _m3_noise(surface, 313, count=60, alpha=16)
    _ko_tint(surface)
    _tag(surface, "ACARISTAN // 22:07")


def _draw_m3_end_booth_dark(surface, t):
    """Aftermath in the booth: emergency lighting, two people, job done."""
    surface.fill((7, 6, 8))
    _draw_vertical_gradient(surface, 0, SCENE_TOP, WIDTH, SCENE_BOT - SCENE_TOP,
                            (24, 15, 15), (7, 6, 8))
    floor_y = SAFE_BOT

    pygame.draw.rect(surface, (17, 14, 15), (0, floor_y, WIDTH, HEIGHT - floor_y))
    for y in range(floor_y, HEIGHT, 26):
        pygame.draw.line(surface, (23, 19, 20), (0, y), (WIDTH, y), 1)

    # Emergency beacons on the side walls - the studio monitors occupy the
    # upper wall, so the red has to come from the flanks to read at all.
    for i, lx in enumerate((34, WIDTH - 34)):
        pulse = 0.35 + 0.65 * max(0.0, math.sin(t * 0.004 + i * 1.6))
        pygame.draw.rect(surface, (74, 30, 26), (lx - 16, SAFE_TOP + 210, 32, 16))
        _ko_glow(surface, (228, 66, 52), (lx, SAFE_TOP + 218), 210,
                 int(16 + 34 * pulse))
    for i, lx in enumerate((150, WIDTH - 150)):
        pulse = 0.35 + 0.65 * max(0.0, math.sin(t * 0.004 + i * 2.2 + 0.7))
        _ko_glow(surface, (222, 62, 50), (lx, floor_y - 90), 150,
                 int(10 + 22 * pulse))

    # Dead monitors + a dark ON AIR sign.
    _end_screens(surface, t, count=3, y=SAFE_TOP + 62, dark=True)
    sign = pygame.Rect(WIDTH // 2 - 50, SAFE_TOP + 34, 100, 28)
    pygame.draw.rect(surface, (26, 10, 10), sign, border_radius=4)
    pygame.draw.rect(surface, (72, 30, 28), sign, 2, border_radius=4)
    dark = font_terminal_small.render(_T("m3ending.off_air"), True, (100, 46, 42))
    surface.blit(dark, (sign.centerx - dark.get_width() // 2, sign.y + 6))

    _pool(surface, WIDTH // 2 - 20, floor_y + 6, 300, 36, (206, 70, 58), 34)
    _end_console(surface, WIDTH // 2 + 150, floor_y, t, lit=False)
    _ko_actor(surface, "biribel", WIDTH // 2 - 20, floor_y, scale=0.66,
              facing_right=True, t=t, moving=False, walk_phase=0.0)
    _ko_actor(surface, "volkov", WIDTH // 2 + 250, floor_y, scale=0.66,
              facing_right=False, t=t, moving=False, walk_phase=0.0)
    _draw_dust_motes(surface, t)
    _m3_noise(surface, 8080, count=70, alpha=22)
    _ko_tint(surface)
    _tag(surface, "BROADCAST WING // 22:07")


# RPE6 Phase 2 (A-003 take registry): the cutscene scene ids this module owns.
# cutscenes.engine.draw_cutscene_scene finds them through core.cutscene_registry
# instead of importing this module by name (boundary rule 4 / W1).
from core.cutscene_registry import register_scene_renderers as _register_takes  # noqa: E402
from engine.text import T as _T  # RPE6 Phase 4 text table

_register_takes({
    "m3_end_studio": _draw_m3_end_studio,
    "m3_end_cut": _draw_m3_end_cut,
    "m3_end_nation": _draw_m3_end_nation,
    "m3_end_booth_dark": _draw_m3_end_booth_dark,
})
