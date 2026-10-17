
"""m5martial.py - Mission 5 intro + ending cutscene art (Martial Law).

Eight bespoke shots replace the W4 lit-black stubs:

  Intro
  1. m5_tv_bulletin      - the state airwaves reading Balaceanu's death as
                           suicide; a studio desk, crest, and a lower-third
                           that says MORE. The arrest screen from M4 has aged
                           into an obituary.
  2. m5_safehouse_tv     - Biribel's safehouse, the same bulletin playing on
                           a small CRT he is not watching. He is at the window.
  3. m5_retardovici_tv   - the president's address dissolving parliament:
                           podium, seal, two flags, a calm man taking a
                           country slowly.

  Ending
  4. m5_river_gate       - rain off the basement tunnel onto the river; Maru
                           through the gate, and the red dot of a scope
                           finding Biribel's chest before he knows it.
  5. m5_ucilev_scope     - inside Ucilev's optic: reticle, range, a held
                           breath. The operator nobody remembers.
  6. m5_ucilev_reveal    - the scope lifts; Ucilev Nadgob Ierdna's face in the
                           lamp light, Guard black and red armband. He lowers
                           the rifle an inch. "Not tonight."
  7. m5_ucilev_leaves    - he walks away into the rain, back to camera, the
                           river gate bright behind him.
  8. m5_radio            - Vasile on the radio in the empty street after:
                           two men on a wire deciding what neither saw.

Purely procedural, in the same visual language as m4aftermath: composition
lives inside SAFE_TOP..SAFE_BOT so the dialogue box never covers the
performers; helpers are imported from the shared cutscene layers, not
re-implemented; every named figure goes through cutscenes.cast.
"""
import math
import random

import pygame

from core.config import (HEIGHT, SCENE_BOT, SCENE_TOP, WIDTH, font_terminal_small)
from core.state import STATE

from cutscenes.cast import (draw_balaceanu, draw_biribel, draw_maru,
                            draw_president, draw_ucilev, draw_vasile)
from cutscenes.m3ko import _ko_clamp01, _ko_glow, _ko_tint
from cutscenes.m3cell import _m3_clamp01, _m3_noise, _m3_smooth
from cutscenes.chair import _draw_dust_motes
from cutscenes.route12 import _draw_vertical_gradient
from engine.text import T as _T  # RPE6 Phase 4 text table

_CREST = (230, 200, 120)      # Retardovici's presidential gold
_GUARD_RED = (180, 40, 40)    # the Presidential Guard armband
_LIAISON = (110, 200, 140)    # Maru green (matches m5.meta C_MARU)
_RIVER = (70, 96, 120)        # night water under the gate lamp
_SODIUM = (228, 168, 96)      # single sodium street lamp by the gate

SAFE_TOP = SCENE_TOP + 6
SAFE_BOT = HEIGHT - 158   # dialogue box ceiling
_FILM_H = SAFE_BOT - SAFE_TOP


def _tag(surface, text, color=(120, 200, 220)):
    """Location tag pinned inside the safe band (m4aftermath._tag idiom).
    Empty text draws nothing (shots without a slate, e.g. character closes)."""
    if not text:
        return
    surf = font_terminal_small.render(text, True, color)
    pad_x, pad_y = 10, 3
    plate = pygame.Surface((surf.get_width() + pad_x * 2, surf.get_height() + pad_y * 2),
                           pygame.SRCALPHA)
    plate.fill((4, 6, 10, 190))
    pygame.draw.rect(plate, (*color, 90), plate.get_rect(), 1)
    px = WIDTH // 2 - plate.get_width() // 2
    surface.blit(plate, (px, SAFE_TOP + 6))
    surface.blit(surf, (px + pad_x, SAFE_TOP + 6 + pad_y))


def _beat(t, start, length):
    return _m3_smooth(_m3_clamp01((t - start) / float(length)))


def _scanlines(surface, rect, step=4, alpha=17):
    for y in range(rect[1], rect[1] + rect[3], step):
        pygame.draw.line(surface, (0, 0, 0, alpha), (rect[0], y),
                         (rect[0] + rect[2], y))


# ────────────────────────────────────────────
# Shared set pieces
# ────────────────────────────────────────────
def _studio_backdrop(panel, cx, cy, w, h):
    """IPA broadcast wall: dark navy gradient, crest centred above the desk."""
    _draw_vertical_gradient(panel, 0, 0, w, h, (30, 36, 52), (12, 15, 24))
    for x in (cx - w // 2 + 40, cx + w // 2 - 40):
        pygame.draw.rect(panel, (24, 29, 42), (x - 14, 0, 28, h))
        pygame.draw.line(panel, (52, 47, 44), (x - 14, 0), (x - 14, h), 2)
    pygame.draw.circle(panel, (104, 83, 52), (cx, cy - int(h * 0.22)), 34, 3)
    pygame.draw.circle(panel, (46, 44, 48), (cx, cy - int(h * 0.22)), 28)
    for dx in (-14, 0, 14):
        pygame.draw.polygon(panel, (168, 136, 84),
                            [(cx + dx, cy - int(h * 0.22) - 20),
                             (cx + dx + 6, cy - int(h * 0.22) + 6),
                             (cx + dx, cy - int(h * 0.22) + 20),
                             (cx + dx - 6, cy - int(h * 0.22) + 6)])
    _ko_glow(panel, (104, 146, 191), (cx, cy - 20), int(w * 0.55), 26)


def _broadcast_panel(t, *, who, caption, cap_col, reveal_ms, wide=None):
    """A public monitor filling the safe band as it switches on. Returns the
    panel plus the surround fade (1 = frame closed, 0 = full screen)."""
    open_p = _beat(t, 0, reveal_ms) if t < reveal_ms * 4 else 1.0
    mw = round(WIDTH * (0.62 + 0.38 * open_p))
    mh = round(_FILM_H * (0.58 + 0.42 * open_p))
    mx, my = (WIDTH - mw) // 2, SAFE_TOP + round((_FILM_H - mh) * 0.5 * open_p)
    panel = pygame.Surface((mw, mh))
    _studio_backdrop(panel, mw // 2, mh // 2, mw, mh)
    foot = mh - 26
    scale = mh / 460.0
    draw_president(panel, mw // 2, foot, scale=scale, facing_right=True) \
        if who == "president" else \
        draw_balaceanu(panel, mw // 2, foot, scale=scale, facing_right=False)
    # Lower third rises with the anchor's first sentence.
    bar_h = max(20, round(mh * 0.10))
    bar_y = mh - bar_h - 6
    pygame.draw.rect(panel, (16, 21, 33, 236), (0, bar_y, mw, bar_h))
    txt = font_terminal_small.render(caption, True, cap_col)
    panel.blit(txt, (max(10, (mw - txt.get_width()) // 2),
                     bar_y + (bar_h - txt.get_height()) // 2))
    ui = pygame.Surface((mw, mh), pygame.SRCALPHA)
    pygame.draw.circle(ui, (220, 67, 57), (20, 18), 3)
    ui.blit(font_terminal_small.render(_T("m5martial.state_live"), True, (214, 213, 198)),
            (30, 11))
    for y in range(0, mh, 4):
        pygame.draw.line(ui, (0, 0, 0, 16), (0, y), (mw, y))
    panel.blit(ui, (0, 0))
    return panel, (mx, my, open_p)


# ────────────────────────────────────────────
# INTRO 1 - the bulletin
# ────────────────────────────────────────────
def _draw_m5_tv_bulletin(surface, t):
    """The state airwaves turning a murdered prime minister into a suicide.

    A studio read: anchor desk, presidential crest, a chyron that keeps
    updating while the corpse is being described. Biribel is absent - this
    is the machine talking at him."""
    # The old take drew Balaceanu himself as the anchor (reading his own
    # death) inside a monitor frame; the studio now lives in m5studio.
    from cutscenes.m5studio import draw_bulletin_2d  # lazy: m5studio imports this module
    draw_bulletin_2d(surface, t)


# ────────────────────────────────────────────
# INTRO 2 - the safehouse
# ────────────────────────────────────────────
def _draw_m5_safehouse_tv(surface, t):
    """Biribel's safehouse. The bulletin plays on a small CRT he has stopped
    watching; he stands at the rain-blacked window instead."""
    surface.fill((10, 10, 13))
    _draw_vertical_gradient(surface, 0, SCENE_TOP, WIDTH, SAFE_BOT - SCENE_TOP,
                            (22, 20, 24), (7, 8, 10))
    rng = random.Random(1501)
    # Back wall + bare bulb casting the room's only warm pool.
    pygame.draw.rect(surface, (18, 18, 22), (0, SAFE_TOP, WIDTH, _FILM_H))
    _ko_glow(surface, (210, 170, 120), (WIDTH - 220, SAFE_TOP + 60), 200, 26)
    pygame.draw.line(surface, (40, 40, 46), (WIDTH - 220, SAFE_TOP),
                     (WIDTH - 220, SAFE_TOP + 54), 2)
    pygame.draw.circle(surface, (236, 200, 150), (WIDTH - 220, SAFE_TOP + 60), 6)
    # Window on the left: rain outside, sodium glow on the glass.
    wx, wy, ww, wh = 90, SAFE_TOP + 70, 300, 220
    pygame.draw.rect(surface, (8, 10, 16), (wx, wy, ww, wh))
    for i in range(26):
        rx = wx + rng.randint(6, ww - 6)
        ry = wy + ((i * 37 + int(t * 0.35)) % wh)
        pygame.draw.line(surface, (40, 52, 66), (rx, ry), (rx - 1, ry + 8), 1)
    _ko_glow(surface, (90, 110, 140), (wx + ww // 2, wy + wh - 20), ww, 22)
    pygame.draw.rect(surface, (34, 34, 40), (wx - 6, wy - 6, ww + 12, wh + 12), 6)
    pygame.draw.line(surface, (34, 34, 40), (wx + ww // 2, wy),
                     (wx + ww // 2, wy + wh), 4)
    # The CRT on a crate, right of centre, playing the bulletin.
    cw, ch = 168, 126
    cx, cy = WIDTH - 360, SAFE_TOP + 150
    feed = pygame.Surface((cw - 18, ch - 18))
    _studio_backdrop(feed, (cw - 18) // 2, (ch - 18) // 2, cw - 18, ch - 18)
    draw_balaceanu(feed, (cw - 18) // 2, ch - 30, scale=(ch - 18) / 460.0,
                   facing_right=False)
    pygame.draw.rect(feed, (16, 21, 33), (0, ch - 40, cw - 18, 22))
    _scanlines(feed, (0, 0, cw - 18, ch - 18))
    surface.blit(feed, (cx + 9, cy + 9))
    # Bezel is a border ring only - filling it would paint over the feed.
    pygame.draw.rect(surface, (46, 50, 58), (cx, cy, cw, ch), 6, border_radius=8)
    pygame.draw.rect(surface, (86, 90, 98), (cx, cy, cw, ch), 2, border_radius=8)
    _ko_glow(surface, (120, 150, 190), (cx + cw // 2, cy + ch // 2), 150, 18)
    # Crate the set sits on.
    pygame.draw.rect(surface, (30, 26, 22), (cx - 14, cy + ch, cw + 28, 46))
    pygame.draw.line(surface, (48, 42, 36), (cx - 14, cy + ch + 14),
                     (cx + cw + 14, cy + ch + 14), 2)
    # Biribel at the window, back to us, hands in pockets.
    _figure_sil(surface, draw_biribel, 360, SAFE_BOT - 4, 0.86,
                facing_right=False, t=t)
    _draw_dust_motes(surface, t)
    _m3_noise(surface, 4004, count=58, alpha=16)
    _ko_tint(surface)
    _tag(surface, "SAFEHOUSE // KRAP FLAT 4C", _LIAISON)


def _figure_sil(surface, fn, cx, foot_y, scale, *, facing_right, t):
    """Cached cast figure flattened to a near-black interior-lit silhouette
    (m4aftermath._figure idiom, generalised to any cast painter)."""
    bob = (math.sin(t * 0.006) + 1) * 0.8
    fn(surface, cx, foot_y - int(bob), scale=scale, facing_right=facing_right,
       in_silhouette=True)


# ────────────────────────────────────────────
# INTRO 3 - the president's address
# ────────────────────────────────────────────
def _draw_m5_retardovici_tv(surface, t):
    """The address that ends parliament. Podium, seal, two flags, and a man
    who has already won saying he is only restoring order."""
    surface.fill((7, 9, 15))
    _ko_glow(surface, (83, 118, 151), (WIDTH // 2, SAFE_TOP + 220), 470, 22)
    panel, (mx, my, open_p) = _broadcast_panel(
        t, who="president", caption="PRESIDENT RETARDOVICI  ·  ADDRESS TO THE NATION",
        cap_col=_CREST, reveal_ms=1600)
    aw, ah = panel.get_size()
    # Flags flank the seal; the podium front carries the crest.
    for side in (-1, 1):
        fx = aw // 2 + side * int(aw * 0.30)
        pygame.draw.line(panel, (70, 62, 54), (fx, 20), (fx, ah - 70), 4)
        flag = pygame.Surface((58, 96), pygame.SRCALPHA)
        wave = math.sin(t * 0.002 + side) * 4
        pygame.draw.polygon(flag, (25, 35, 59),
                            [(0, 0), (58, 6 + wave), (58, 90 + wave), (0, 96)])
        pygame.draw.polygon(flag, (94, 32, 35),
                            [(18, 0), (40, 3 + wave * .5), (40, 93 + wave * .5), (18, 96)])
        panel.blit(flag, (fx - 29, 24))
    pygame.draw.rect(panel, (20, 26, 38),
                     (aw // 2 - 92, ah - 150, 184, 150))
    pygame.draw.polygon(panel, (61, 45, 40),
                        [(aw // 2 - 92, ah - 150), (aw // 2 + 92, ah - 150),
                         (aw // 2 + 80, ah - 138), (aw // 2 - 80, ah - 138)])
    pygame.draw.circle(panel, (160, 129, 78), (aw // 2, ah - 78), 26, 2)
    seal = font_terminal_small.render(_T("m5martial.ipa_state"), True, _CREST)
    panel.blit(seal, (aw // 2 - seal.get_width() // 2, ah - 86))
    surface.blit(panel, (mx, my))
    pygame.draw.rect(surface, (98, 106, 112),
                     (mx - 10, my - 8, aw + 20, ah + 16), 2, border_radius=5)
    # Broadcast-hall emptiness: rows of seats no one is allowed to leave.
    crowd = pygame.Surface((WIDTH, 70), pygame.SRCALPHA)
    for i in range(26):
        px = 10 + i * 39
        py = 30 + (i * 11 % 18)
        pygame.draw.circle(crowd, (5, 8, 14), (px, py), 11)
        pygame.draw.polygon(crowd, (5, 8, 14),
                            [(px - 15, py + 13), (px + 15, py + 13),
                             (px + 21, 70), (px - 21, 70)])
    surface.blit(crowd, (0, SAFE_BOT - 70))
    _m3_noise(surface, 5151, count=64, alpha=18)
    _ko_tint(surface)
    _tag(surface, "ADDRESS TO THE NATION // PARLIAMENT SUSPENDED")


# ────────────────────────────────────────────
# ENDING 4 - the river gate
# ────────────────────────────────────────────
def _river_set(surface, t, *, lamp=(0, 0)):
    """Shared river-gate geometry: tunnel mouth left, iron gate + water right,
    one sodium lamp, rain. ``lamp`` offsets the light pool."""
    lx, ly = lamp
    # Night sky over the far bank.
    _draw_vertical_gradient(surface, 0, SCENE_TOP, WIDTH, SAFE_BOT - SCENE_TOP,
                            (16, 20, 30), (6, 8, 12))
    rng = random.Random(903)
    for bx in range(-20, WIDTH, 60):
        bh = rng.randint(30, 120)
        pygame.draw.rect(surface, (10, 12, 18), (bx, SAFE_BOT - 210 - bh, 52, bh + 40))
    # Water.
    water_y = SAFE_BOT - 170
    pygame.draw.rect(surface, (14, 22, 32), (0, water_y, WIDTH, 170))
    for i in range(16):
        wy = water_y + 8 + i * 10
        off = math.sin(t * 0.002 + i) * 14
        seg = 40 + (i % 4) * 22
        pygame.draw.line(surface, (24, 38, 54), (off + i * 17, wy),
                         (off + i * 17 + seg, wy), 2)
    # Quay the gate sits on.
    pygame.draw.rect(surface, (18, 18, 22), (0, SAFE_BOT, WIDTH, HEIGHT - SAFE_BOT))
    pygame.draw.rect(surface, (30, 30, 36), (0, SAFE_BOT - 6, WIDTH, 8))
    # Tunnel mouth (left) spilling cold light.
    tx, ty = 150, SAFE_BOT - 150
    pygame.draw.rect(surface, (9, 10, 14), (tx - 60, ty, 150, 150))
    pygame.draw.arc(surface, (40, 42, 50), (tx - 60, ty - 30, 150, 90),
                    math.pi, math.tau, 4)
    _ko_glow(surface, (90, 120, 150), (tx + 15, ty + 90), 130, 26)
    # Anchored, OPEN access gate: the leaf stays left of Maru's exit path.
    gx = WIDTH - 300 + lx
    for px in (gx, gx + 220):
        pygame.draw.rect(surface, (50, 48, 44), (px, SAFE_TOP + 100, 18, SAFE_BOT - SAFE_TOP - 100))
        pygame.draw.rect(surface, (82, 76, 64), (px - 4, SAFE_TOP + 94, 26, 8))
    pygame.draw.rect(surface, (42, 40, 38), (gx - 90, SAFE_TOP + 130, 90, SAFE_BOT - SAFE_TOP - 130))
    for b in range(6):
        bx = gx + 8 + b * 9
        pygame.draw.line(surface, (68, 72, 74), (bx, SAFE_TOP + 120 + b * 4),
                         (bx, SAFE_BOT - 5), 3)
    pygame.draw.line(surface, (68, 72, 74), (gx + 4, SAFE_TOP + 164),
                     (gx + 60, SAFE_TOP + 190), 3)
    # Sodium lamp above the gate.
    lamp_xy = (gx + 110 + lx // 2, SAFE_TOP + 60 + ly)
    pygame.draw.line(surface, (36, 36, 42), (gx + 110, SAFE_TOP + 20),
                     lamp_xy, 3)
    _ko_glow(surface, _SODIUM, lamp_xy, 220, 34)
    pygame.draw.circle(surface, (255, 214, 150), lamp_xy, 6)
    # Wet ground: the lamp and the water's own sheen, wavering (a matte deck
    # under a lit lamp reads as painted cardboard).
    _wet_smear(surface, gx + 110, SAFE_BOT - 6, 64, _SODIUM, t, seed=3, width=26)
    _wet_smear(surface, gx + 118, water_y + 6, 52, (66, 92, 118), t, seed=7, width=34)
    return gx, water_y, lamp_xy


def _rain_streaks(surface, t, seed, n=90, splash_y=None, n_splash=5):
    """Rain in two depth bands (far: short, dim, slow; near: long, bright,
    fast) on the scene's wind, plus crowns where it hits the deck: without
    the impact marks a screen-space overlay reads as a filter pasted ON the
    film instead of weather in the world. ``splash_y`` = screen y of the
    ground/water line the drops land on."""
    rng = random.Random(seed)
    n_far = max(4, int(n * 0.6))
    n_near = max(4, n - n_far)
    # far band: short dim streaks, slow fall
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(n_far):
        x = rng.randint(0, WIDTH)
        y = (rng.randint(0, HEIGHT) + int(t * 0.45)) % HEIGHT
        ln = rng.randint(5, 11)
        pygame.draw.line(layer, (120, 136, 160, rng.randint(16, 34)),
                         (x, y), (x - 2, y + ln), 1)
    surface.blit(layer, (0, 0))
    # near band: long, brighter, faster - the drops close to the lens
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(n_near):
        x = rng.randint(0, WIDTH)
        y = (rng.randint(0, HEIGHT) + int(t * 1.25)) % HEIGHT
        ln = rng.randint(12, 26)
        pygame.draw.line(layer, (168, 186, 212, rng.randint(30, 62)),
                         (x, y), (x - 4, y + ln), 1)
    surface.blit(layer, (0, 0))
    if splash_y is not None:                       # crowns + ripples on the deck
        layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for i in range(n_splash):
            ph = (t * 0.001 + i * 0.37 + seed * 0.11) % 1.0
            x = rng.randint(20, WIDTH - 20)
            r = 1 + int(5 * ph)
            a = int(110 * (1 - ph))
            pygame.draw.ellipse(layer, (150, 168, 196, a),
                                (x - r, splash_y - r // 2 - int(2 * ph), r * 2, r), 1)
            if ph > 0.55:                          # rebound droplets
                d = int((ph - 0.55) * 10)
                pygame.draw.line(layer, (168, 186, 212, a),
                                 (x - 2, splash_y), (x - 3, splash_y - d), 1)
                pygame.draw.line(layer, (168, 186, 212, a),
                                 (x + 2, splash_y), (x + 3, splash_y - int(d * 0.7)), 1)
        surface.blit(layer, (0, 0))


def _wet_smear(surface, x, y, length, col, t, seed=0, width=16):
    """Light smeared on wet ground: a wavering stack of dashes running down
    from where the light meets the deck (the matte-cardboard fix)."""
    n = 9
    layer = pygame.Surface((WIDTH, int(length) + 8), pygame.SRCALPHA)
    for i in range(n):
        f = i / (n - 1.0)
        k = 0.55 * (1.0 - f) ** 1.3 * (0.75 + 0.25 * math.sin(t * 0.009 + i * 1.9 + seed))
        if k <= 0.03:
            continue
        xx = x + math.sin(t * 0.0045 + i * 1.3 + seed) * width * 0.45
        yy = f * length
        w = max(2, int(width * (1.0 - 0.4 * f)))
        pygame.draw.ellipse(layer, (*[int(c * k) for c in col], 255),
                            (int(xx - w / 2), int(yy), w, max(2, int(length / n * 0.8))))
    surface.blit(layer, (int(x - width), int(y)))


def _draw_m5_river_gate(surface, t):
    """Maru through the gate; Biribel turns as a red dot finds his chest.

    The escort ends here and the standoff begins on the next shot, so this
    frame holds both: Maru half-gone through the bars, Biribel alone on the
    quay, and the scope's dot arriving on him mid-beat."""
    surface.fill((6, 8, 12))
    t = max(0, min(t, 7200))
    gx, water_y, lamp = _river_set(surface, t)
    _rain_streaks(surface, t, 77, splash_y=SAFE_BOT - 6, n_splash=6)
    # Maru slipping through the gate, hood up, favouring the wounded arm.
    walk = _beat(t, 600, 2600)
    mx = int(gx + 82 + walk * (WIDTH + 80 - gx - 82))
    from cutscenes.figure_kit import draw_character  # lazy: same module cast.py wraps
    draw_character(surface, "maru", mx, SAFE_BOT + 4, 0.74, True, silhouette=True,
                   t=t, moving=0.9)     # a real stride, not a sliding cutout
    # Biribel on the quay, turning toward the far bank.
    turn = _beat(t, 2600, 1400)
    _figure_sil(surface, draw_biribel, 360, SAFE_BOT + 4, 0.82,
                facing_right=turn > 0.5, t=t)
    # The red dot: appears on his chest after the turn lands.
    dot_on = _beat(t, 3600, 500)
    if dot_on > 0.02:
        dx, dy = 360 + 14, SAFE_BOT - 150
        pulse = 0.6 + 0.4 * math.sin(t * 0.01)
        r = max(2, round(4 * dot_on * pulse))
        _ko_glow(surface, (255, 40, 30), (dx, dy), 26, int(40 * dot_on))
        pygame.draw.circle(surface, (255, 50, 36), (dx, dy), r)
    _draw_dust_motes(surface, t)
    _m3_noise(surface, 2202, count=60, alpha=16)
    _ko_tint(surface)
    _tag(surface, "RIVER GATE // EAST CHANNEL", _RIVER)


# ────────────────────────────────────────────
# ENDING 5 - inside the scope
# ────────────────────────────────────────────
def _draw_m5_ucilev_scope(surface, t):
    """Ucilev's optic: the world cropped to a circle, crosshair on Biribel,
    range and windage etched on the glass. A held breath moves the reticle.

    240 m of lane: the hold wanders and breathes, and because the image is
    MAGNIFIED through the glass the world drifts several times further than
    the reticle (which rides the tube) - that differential is what makes it
    read as a man looking through a scope instead of a screenshot under a
    circular mask."""
    surface.fill((2, 3, 5))
    t = max(0, min(t, 9200))
    # The scene through the lens: the quay, Biribel small and unaware. Built
    # oversized so the drifting image can shift without exposing an edge.
    M = 26
    inner = pygame.Surface((WIDTH + 2 * M, HEIGHT + 2 * M))
    _river_set(inner, t, lamp=(-40, 6))
    _rain_streaks(inner, t, 12, n=40, splash_y=SAFE_BOT + 22 + M, n_splash=4)
    _figure_sil(inner, draw_biribel, 360 + M, SAFE_BOT + 4 + M, 0.82,
                facing_right=True, t=t)
    cx, cy = WIDTH // 2, SAFE_TOP + (_FILM_H // 2) - 10
    radius = _FILM_H // 2 - 6
    # Soft-edged mask (the old hard cut-out read as a stencil): a clear glass
    # circle inside a graded falloff into black.
    mask = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    mask.fill((0, 0, 0))
    pygame.draw.circle(mask, (255, 255, 255), (cx, cy), radius - 12)
    for i in range(1, 13):
        v = int(255 * (1 - i / 13.0) ** 1.1)
        pygame.draw.circle(mask, (v, v, v), (cx, cy), radius - 12 + i, 1)
    masked = inner.subsurface((M, M, WIDTH, HEIGHT)).copy()
    masked.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    # Hold: slow wander + breath + tremor. The WANDER is what the marksman
    # corrects; it decays as he commits to the shot.
    settle = _beat(t, 1200, 2400)
    wander = 1.0 - 0.6 * settle
    sway_x = (math.sin(t * 0.00042) * 11 * wander + math.sin(t * 0.00017 + 1.3) * 7 * wander
              + (1.0 - settle) * math.sin(t * 0.0021) * 4)
    sway_y = (math.cos(t * 0.00031 + 0.7) * 8 * wander + math.cos(t * 0.00053) * 4 * wander
              + (1.0 - settle) * math.cos(t * 0.0017) * 3)
    tremor = 0.6 * (math.sin(t * 0.0131) + math.sin(t * 0.0071 + 2.0) * 0.8)
    surface.blit(masked, (int(sway_x), int(sway_y)))
    # Reticle: rides the tube (tremor only) while the image drifts past it.
    rcx, rcy = cx + tremor, cy + tremor * 0.7
    ring = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.circle(ring, (10, 12, 14, 200), (rcx, rcy), radius, 6)
    pygame.draw.circle(ring, (120, 140, 150, 150), (rcx, rcy), radius, 1)
    for ang in range(0, 360, 30):
        a = math.radians(ang)
        pygame.draw.line(ring, (90, 110, 120, 130),
                         (rcx + int(math.cos(a) * radius * .92),
                          rcy + int(math.sin(a) * radius * .92)),
                         (rcx + int(math.cos(a) * radius * .80),
                          rcy + int(math.sin(a) * radius * .80)), 2)
    gap = 16
    pygame.draw.line(ring, (200, 60, 50, 200), (rcx - radius, rcy),
                     (rcx - gap, rcy), 1)
    pygame.draw.line(ring, (200, 60, 50, 200), (rcx + gap, rcy),
                     (rcx + radius, rcy), 1)
    pygame.draw.line(ring, (200, 60, 50, 200), (rcx, rcy - radius),
                     (rcx, rcy - gap), 1)
    pygame.draw.line(ring, (200, 60, 50, 200), (rcx, rcy + gap),
                     (rcx, rcy + radius), 1)
    for k in range(-4, 5):
        if k:
            pygame.draw.line(ring, (150, 60, 55, 150), (rcx - 5, rcy + k * 18),
                             (rcx + 5, rcy + k * 18), 1)
    pygame.draw.circle(ring, (255, 70, 50, 220), (rcx, rcy), 3)
    surface.blit(ring, (0, 0))
    # Etched data. The top tag lives below the optic's upper rim so it never
    # collides with the "OPTIC // FAR BANK" location tag at SAFE_TOP.
    hud = font_terminal_small.render(_T("m5martial.y_3_intake_match"), True, (150, 165, 175))
    surface.blit(hud, (cx - hud.get_width() // 2, cy + radius - 30))
    rng_txt = font_terminal_small.render(_T("m5martial.range_240m_wind_l2"), True,
                                         (120, 135, 145))
    surface.blit(rng_txt, (cx - rng_txt.get_width() // 2, cy + radius - 52))
    _m3_noise(surface, 8808, count=50, alpha=14)
    _ko_tint(surface)
    _tag(surface, "OPTIC // FAR BANK", _GUARD_RED)


# ────────────────────────────────────────────
# ENDING 6/7 - the reveal, then he leaves
# ────────────────────────────────────────────
def _ucilev_pose(t):
    """Rifle carried low at the reveal, muzzle down as he decides, shouldered
    nowhere as he walks off. Returns (lift, lower)."""
    lift = _beat(t, 900, 2200)         # scope-eye to standing eye contact
    lower = _beat(t, 3400, 2600)       # "not tonight": the barrel drops
    return lift, lower


def _draw_m5_ucilev_reveal(surface, t):
    """The operator listed dead two years ago, out of the optic and into the
    lamp light. Ucilev Nadgob Ierdna lowers the rifle an inch.

    The rifle's drop settles with a touch of overshoot (a weight, not a
    servo) and his chest breathes under the Guard blacks - an idle actor
    holds the frame, a mannequin kills it."""
    surface.fill((6, 8, 12))
    t = max(0, min(t, 8400))
    _draw_vertical_gradient(surface, 0, SCENE_TOP, WIDTH, SAFE_BOT - SCENE_TOP,
                            (18, 22, 32), (6, 8, 12))
    # Far-bank ground and the rain curtain behind him.
    ground_y = SAFE_BOT - 40
    pygame.draw.rect(surface, (12, 14, 18), (0, ground_y, WIDTH, HEIGHT - ground_y))
    _rain_streaks(surface, t, 33, n=70, splash_y=SAFE_BOT - 14, n_splash=4)
    # Key light: the sodium lamp behind-left rimming the Guard black.
    _ko_glow(surface, _SODIUM, (WIDTH - 260, SAFE_TOP + 90), 240, 30)
    cx = WIDTH // 2 - 40
    lift, lower = _ucilev_pose(t)
    foot = SAFE_BOT - 6
    breath = math.sin(t * 0.0021) * 1.4          # chest rise under the coat
    bob = int(breath * 0.5)
    draw_ucilev(surface, cx, foot + bob, scale=0.96, facing_right=lift < 0.5)
    # Rifle held across the body, muzzle dropping with `lower` (ease-out-back:
    # the weight carries past, then settles).
    lk = _beat(t, 3400, 2200)
    over = math.sin(math.pi * min(1.0, lk * 1.35)) * 0.06 * (1.0 - lk)
    ang = -0.9 + lower * 0.7 - over
    ex, ey = cx - 46, foot - 150 + bob
    pygame.draw.line(surface, (10, 11, 13), (ex, ey),
                     (ex + math.cos(ang) * 120, ey + math.sin(ang) * 120), 6)
    pygame.draw.line(surface, (60, 62, 68), (ex + 8, ey - 2),
                     (ex + 8 + math.cos(ang) * 110, ey - 2 + math.sin(ang) * 110), 2)
    # Red armband catchlight on the gun-side shoulder.
    pygame.draw.line(surface, _GUARD_RED, (cx + 22, foot - 206),
                     (cx + 34, foot - 196), 6)
    # His eyes track off-frame to Biribel, not the camera.
    gaze = _beat(t, 0, 1200)
    hx, hy = cx + 2, foot - 252 + bob
    pygame.draw.line(surface, (150, 150, 158), (hx - 6, hy), (hx - 2, hy), 2)
    _draw_dust_motes(surface, t)
    _m3_noise(surface, 4411, count=54, alpha=16)
    _ko_tint(surface)
    _tag(surface, "UCILEV NADGOB IERDNA // LISTED DEAD", _GUARD_RED)


def _draw_m5_ucilev_leaves(surface, t):
    """He lowers the rifle and walks away into the rain. Back to camera, the
    river gate still glowing where Maru went through."""
    surface.fill((6, 8, 12))
    t = max(0, min(t, 6800))
    gx, water_y, lamp = _river_set(surface, t)
    _rain_streaks(surface, t, 55, n=100, splash_y=SAFE_BOT - 6, n_splash=5)
    # Walking away: smaller each beat, drifting up toward the gate.
    walk = _beat(t, 400, 5600)
    scale = 0.92 - walk * 0.22
    cx = int(WIDTH // 2 + walk * 150)
    foot = int(SAFE_BOT - walk * 60)
    from cutscenes.figure_kit import draw_character  # lazy: same module cast.py wraps
    draw_character(surface, "ucilev", cx, foot, scale, False, t=t, moving=0.85 * (1 - walk))
    # Rifle flat at the side, muzzle down, swinging with the stride.
    swing = math.sin(t * 0.012) * 6 * (1 - walk)
    ex, ey = cx - int(34 * scale), foot - int(120 * scale)
    pygame.draw.line(surface, (10, 11, 13), (ex, ey),
                     (ex - swing, ey + int(96 * scale)), 5)
    # Gate lamp halo where Maru disappeared.
    _ko_glow(surface, _SODIUM, (gx + 110, SAFE_TOP + 70), 200, 26)
    _wet_smear(surface, gx + 110, SAFE_BOT - 6, 60, _SODIUM, t, seed=11, width=24)
    _m3_noise(surface, 4412, count=52, alpha=16)
    _ko_tint(surface)
    _tag(surface, "EAST CHANNEL // HE DOESN'T TURN", _RIVER)


# ────────────────────────────────────────────
# ENDING 8 - the radio
# ────────────────────────────────────────────
def _cig_puff(surface, x, y, t, scale=1.0, drift=-1.0):
    """Ember pulse + rising wisp for the 2D cast: the cached cast figures can
    never animate their cigarette, so the life is drawn on top at the mouth."""
    layer = pygame.Surface((90, 110), pygame.SRCALPHA)
    # ember: breathes with the smoke's pull
    k = 0.65 + 0.35 * math.sin(t * 0.004)
    pygame.draw.circle(layer, (255, 120, 40, int(220 * k)), (26, 78), 3)
    pygame.draw.circle(layer, (255, 190, 130, int(90 * k)), (26, 78), 6)
    # wisps: three puffs at staggered ages, expanding and fading as they rise
    for i in range(3):
        age = ((t * 0.00035 + i * 0.37) % 1.0)
        if age <= 0.02:
            continue
        r = (2.0 + age * 13.0) * scale
        a = int(70 * (1 - age) ** 1.4)
        px = 26 + (math.sin(i * 2.1 + age * 5.0) * 8 + drift * age * 6) * scale
        py = 76 - age * 62 * scale
        pygame.draw.circle(layer, (176, 172, 168, a), (int(px), int(py)), int(r))
    surface.blit(layer, (int(x - 26 * scale), int(y - 78 * scale)))


def _handset_2d(surface, cx, foot_y, k, f, hy, side=1, t=0):
    """The receiver held to the ear: earpiece at the ear, body down the cheek,
    mouthpiece at the lips, and a hand at the grip (the solve is handed back
    to draw_character's reach so the arm follows)."""
    ex = cx + side * 13 * k * f                     # ear
    ey = foot_y + (hy - 3) * k
    bob = math.sin(t * 0.0013 + side) * 1.2         # talk tilt
    pygame.draw.ellipse(surface, (58, 56, 54), (ex - 7, ey - 9 + bob, 14, 20))   # earpiece
    pygame.draw.rect(surface, (20, 20, 23), (ex - 4, ey + 6 + bob, 8, 16))       # body
    pygame.draw.ellipse(surface, (48, 46, 44), (ex - 6, ey + 20 + bob, 12, 12))  # mouthpiece
    pygame.draw.line(surface, (120, 116, 110), (ex - 6, ey - 5 + bob), (ex + 6, ey - 5 + bob), 1)
    return ex, ey + 26 + bob                         # the grip point (for the cord)


def _draw_m5_radio(surface, t):
    """Two men on a wire deciding what neither saw. Split frame: Biribel on
    the wet quay with the handset, Vasile in his new office with the flag on
    the desk. Neither admits anything.

    The figures are drawn LIVE (not from the pose cache) so they breathe and
    blink, the handsets are solved onto their ears with cords that droop to
    their sets, and the cigarette actually smokes - a magnet-glued prop and a
    frozen actor are what the old cached frame shipped."""
    surface.fill((6, 7, 11))
    t = max(0, min(t, 8800))
    split = _beat(t, 0, 1600)          # the seam opens between the two lines
    sx = int(WIDTH // 2)
    # LEFT - Biribel, quay, rain, the gate glow behind.
    left = pygame.Surface((sx, HEIGHT))
    _river_set(left, t, lamp=(-160, 0))
    _rain_streaks(left, t, 91, n=50, splash_y=SAFE_BOT - 6, n_splash=4)
    from cutscenes.figure_kit import draw_character  # lazy: same module cast.py wraps
    from core.outfits import OUTFIT_GUARD, biribel_2d
    bcx, bfoot, bs = sx - 130, SAFE_BOT + 4, 0.82
    bk = bs * 262 / 296.0
    breath = math.sin(t * 0.0023) * 1.4
    bhy = -258 + breath
    draw_character(left, "biribel", bcx, bfoot, bs, False, t=t,
                   blink=0.9 if (t % 4200) < 120 else 0,
                   reach=[(-13 * bk, (bhy - 3) * bk)],
                   wardrobe=biribel_2d(OUTFIT_GUARD))
    bx, by = _handset_2d(left, bcx, bfoot, bk, -1, bhy, side=1, t=t)
    pygame.draw.lines(left, (30, 30, 34), False,
                      [(bx, by), (bx - 10, by + 44), (bx + 6, by + 88),
                       (bx - 4, by + 150)], 2)      # cord off-frame
    surface.blit(left, (0, 0))
    # RIGHT - Vasile's office: a desk, a flag, one lamp, no rain.
    right = pygame.Surface((WIDTH - sx, HEIGHT))
    _draw_vertical_gradient(right, 0, SCENE_TOP, WIDTH - sx,
                            SAFE_BOT - SCENE_TOP, (26, 24, 22), (8, 8, 10))
    _ko_glow(right, (220, 170, 110), (WIDTH - sx - 150, SAFE_TOP + 70), 200, 26)
    # Desk with the presidential flag tucked behind it.
    pygame.draw.rect(right, (34, 28, 24), (40, SAFE_BOT - 110, WIDTH - sx - 80, 110))
    pygame.draw.line(right, (58, 48, 40), (40, SAFE_BOT - 110),
                     (WIDTH - sx - 40, SAFE_BOT - 110), 3)
    pole_x = WIDTH - sx - 120
    pygame.draw.line(right, (70, 62, 54), (pole_x, SAFE_TOP + 30),
                     (pole_x, SAFE_BOT - 110), 4)
    flag = pygame.Surface((70, 110), pygame.SRCALPHA)
    wave = math.sin(t * 0.002) * 4
    pygame.draw.polygon(flag, (25, 35, 59), [(0, 0), (70, 6 + wave),
                         (70, 104 + wave), (0, 110)])
    pygame.draw.polygon(flag, (94, 32, 35), [(22, 0), (48, 3 + wave * .5),
                         (48, 107 + wave * .5), (22, 110)])
    right.blit(flag, (pole_x - 35, SAFE_TOP + 34))
    vcx, vfoot, vs = 150, SAFE_BOT - 4, 0.86
    vk = vs * 262 / 296.0
    vhy = -258 + math.sin(t * 0.0021) * 1.4
    draw_character(right, "vasile", vcx, vfoot, vs, True, t=t,
                   blink=0.9 if (t % 3700) < 120 else 0,
                   reach=[(13 * vk, (vhy - 3) * vk)])
    vx, vy = _handset_2d(right, vcx, vfoot, vk, 1, vhy, side=1, t=t)
    pygame.draw.lines(right, (30, 30, 34), False,
                      [(vx, vy), (vx - 6, vy + 30), (vx + 26, vy + 52),
                       (vx + 44, vy + 78)], 2)       # cord to the desk set
    _cig_puff(right, vcx + 24.6 * vk, vfoot + (vhy + 27.1) * vk, t, scale=vk)
    surface.blit(right, (sx, 0))
    # The seam: a hard vertical join with a thin broadcast line between them.
    seam = int(sx - (WIDTH - sx) * (1 - split) * 0.0)
    pygame.draw.line(surface, (70, 76, 86), (seam, SCENE_TOP), (seam, SCENE_BOT), 2)
    _ko_glow(surface, (120, 140, 170), (seam, SAFE_TOP + _FILM_H // 2), 120, 14)
    _m3_noise(surface, 6006, count=50, alpha=15)
    _ko_tint(surface)
    _tag(surface, "WIRE // QUAY <-> GUARD HQ", _LIAISON)
