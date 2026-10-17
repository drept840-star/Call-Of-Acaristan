
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

from core.config import *
from core.state import STATE

from cutscenes.cast import (draw_balaceanu, draw_biribel, draw_maru,
                            draw_president, draw_ucilev, draw_vasile)
from cutscenes.m3ko import _ko_clamp01, _ko_glow, _ko_tint
from cutscenes.m3cell import _m3_clamp01, _m3_noise, _m3_smooth
from cutscenes.chair import _draw_dust_motes
from cutscenes.route12 import _draw_vertical_gradient

_CREST = (230, 200, 120)      # Retardovici's presidential gold
_GUARD_RED = (180, 40, 40)    # the Presidential Guard armband
_LIAISON = (110, 200, 140)    # Maru green (matches m5.meta C_MARU)
_RIVER = (70, 96, 120)        # night water under the gate lamp
_SODIUM = (228, 168, 96)      # single sodium street lamp by the gate

SAFE_TOP = SCENE_TOP + 6
SAFE_BOT = HEIGHT - 158   # dialogue box ceiling
_FILM_H = SAFE_BOT - SAFE_TOP


def _tag(surface, text, color=(120, 200, 220)):
    """Location tag pinned inside the safe band (m4aftermath._tag idiom)."""
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
    ui.blit(font_terminal_small.render("STATE / LIVE", True, (214, 213, 198)),
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
    surface.fill((7, 9, 15))
    _ko_glow(surface, (70, 96, 130), (WIDTH // 2, SAFE_TOP + 210), 460, 20)
    panel, (mx, my, open_p) = _broadcast_panel(
        t, who="anchor", caption="BALACEANU DEATH 'SUICIDE'  ·  MORE AT 22:00",
        cap_col=(220, 90, 70), reveal_ms=1400)
    surface.blit(panel, (mx, my))
    # Anchor silhouette at the desk, papers lit from below.
    aw, ah = panel.get_size()
    desk = pygame.Surface((aw, ah), pygame.SRCALPHA)
    pygame.draw.rect(desk, (14, 18, 28, 255), (0, ah - 60, aw, 60))
    pygame.draw.line(desk, (58, 52, 48), (0, ah - 60), (aw, ah - 60), 2)
    panel.blit(desk, (0, 0))
    pygame.draw.rect(surface, (98, 106, 112),
                     (mx - 10, my - 8, aw + 20, ah + 16), 2, border_radius=5)
    # A second monitor at the edge repeats the frame half a beat late.
    echo = pygame.transform.scale(panel, (round(aw * 0.26), round(ah * 0.26)))
    surface.blit(echo, (WIDTH - echo.get_width() - 24, SAFE_TOP + 14))
    pygame.draw.rect(surface, (60, 66, 74),
                     (*echo.get_rect().topleft, echo.get_width(),
                      echo.get_height()), 1)
    _m3_noise(surface, 5151, count=64, alpha=18)
    _ko_tint(surface)
    _tag(surface, "STATE TELEVISION // 21:58")


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
    seal = font_terminal_small.render("IPA / STATE", True, _CREST)
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
    # Iron gate (right), bars catching the lamp.
    gx = WIDTH - 300 + lx
    pygame.draw.rect(surface, (26, 28, 34), (gx, SAFE_TOP + 120, 220, 300))
    for b in range(6):
        bx = gx + 18 + b * 36
        pygame.draw.line(surface, (54, 58, 66), (bx, SAFE_TOP + 130),
                         (bx, SAFE_BOT - 4), 5)
    pygame.draw.line(surface, (54, 58, 66), (gx + 8, SAFE_TOP + 170),
                     (gx + 212, SAFE_TOP + 170), 5)
    # Sodium lamp above the gate.
    lamp_xy = (gx + 110 + lx // 2, SAFE_TOP + 60 + ly)
    pygame.draw.line(surface, (36, 36, 42), (gx + 110, SAFE_TOP + 20),
                     lamp_xy, 3)
    _ko_glow(surface, _SODIUM, lamp_xy, 220, 34)
    pygame.draw.circle(surface, (255, 214, 150), lamp_xy, 6)
    return gx, water_y, lamp_xy


def _rain_streaks(surface, t, seed, n=90):
    rng = random.Random(seed)
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(n):
        x = rng.randint(0, WIDTH)
        y = (rng.randint(0, HEIGHT) + int(t * 0.9)) % HEIGHT
        ln = rng.randint(10, 22)
        pygame.draw.line(layer, (150, 170, 200, rng.randint(28, 60)),
                         (x, y), (x - 3, y + ln), 1)
    surface.blit(layer, (0, 0))


def _draw_m5_river_gate(surface, t):
    """Maru through the gate; Biribel turns as a red dot finds his chest.

    The escort ends here and the standoff begins on the next shot, so this
    frame holds both: Maru half-gone through the bars, Biribel alone on the
    quay, and the scope's dot arriving on him mid-beat."""
    surface.fill((6, 8, 12))
    t = max(0, min(t, 7200))
    gx, water_y, lamp = _river_set(surface, t)
    _rain_streaks(surface, t, 77)
    # Maru slipping through the gate, hood up, favouring the wounded arm.
    walk = _beat(t, 600, 2600)
    mx = int(gx + 150 + walk * 90)
    draw_maru(surface, mx, SAFE_BOT + 4, scale=0.74, facing_right=True,
              in_silhouette=True)
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
    range and windage etched on the glass. A held breath moves the reticle."""
    surface.fill((2, 3, 5))
    t = max(0, min(t, 9200))
    # The scene through the lens: the quay, Biribel small and unaware.
    inner = pygame.Surface((WIDTH, HEIGHT))
    _river_set(inner, t, lamp=(-40, 6))
    _rain_streaks(inner, t, 12)
    _figure_sil(inner, draw_biribel, 360, SAFE_BOT + 4, 0.82,
                facing_right=True, t=t)
    cx, cy = WIDTH // 2, SAFE_TOP + (_FILM_H // 2) - 10
    radius = _FILM_H // 2 - 6
    mask = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (cx, cy), radius)
    masked = inner.copy()
    masked.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(masked, (0, 0))
    # Breath sway: the whole optic drifts until the exhale settles it.
    sway_x = math.sin(t * 0.004) * (10 * (1 - _beat(t, 1200, 2400)))
    sway_y = math.cos(t * 0.003) * (7 * (1 - _beat(t, 1200, 2400)))
    # Reticle.
    rcx, rcy = cx + sway_x, cy + sway_y
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
    hud = font_terminal_small.render("Y-3  INTAKE MATCH", True, (150, 165, 175))
    surface.blit(hud, (cx - hud.get_width() // 2, cy + radius - 30))
    rng_txt = font_terminal_small.render("RANGE 240m  ·  WIND L2", True,
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
    nowhere as he walks off. Returns (foot, arm_low, walking)."""
    lift = _beat(t, 900, 2200)         # scope-eye to standing eye contact
    lower = _beat(t, 3400, 2600)       # "not tonight": the barrel drops
    return lift, lower


def _draw_m5_ucilev_reveal(surface, t):
    """The operator listed dead two years ago, out of the optic and into the
    lamp light. Ucilev Nadgob Ierdna lowers the rifle an inch."""
    surface.fill((6, 8, 12))
    t = max(0, min(t, 8400))
    _draw_vertical_gradient(surface, 0, SCENE_TOP, WIDTH, SAFE_BOT - SCENE_TOP,
                            (18, 22, 32), (6, 8, 12))
    # Far-bank ground and the rain curtain behind him.
    ground_y = SAFE_BOT - 40
    pygame.draw.rect(surface, (12, 14, 18), (0, ground_y, WIDTH, HEIGHT - ground_y))
    _rain_streaks(surface, t, 33, n=70)
    # Key light: the sodium lamp behind-left rimming the Guard black.
    _ko_glow(surface, _SODIUM, (WIDTH - 260, SAFE_TOP + 90), 240, 30)
    cx = WIDTH // 2 - 40
    lift, lower = _ucilev_pose(t)
    foot = SAFE_BOT - 6
    draw_ucilev(surface, cx, foot, scale=0.96, facing_right=lift < 0.5)
    # Rifle held across the body, muzzle dropping with `lower`.
    ang = -0.9 + lower * 0.7
    ex, ey = cx - 46, foot - 150
    pygame.draw.line(surface, (10, 11, 13), (ex, ey),
                     (ex + math.cos(ang) * 120, ey + math.sin(ang) * 120), 6)
    pygame.draw.line(surface, (60, 62, 68), (ex + 8, ey - 2),
                     (ex + 8 + math.cos(ang) * 110, ey - 2 + math.sin(ang) * 110), 2)
    # Red armband catchlight on the gun-side shoulder.
    pygame.draw.line(surface, _GUARD_RED, (cx + 22, foot - 206),
                     (cx + 34, foot - 196), 6)
    # His eyes track off-frame to Biribel, not the camera.
    gaze = _beat(t, 0, 1200)
    hx, hy = cx + 2, foot - 252
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
    _rain_streaks(surface, t, 55, n=100)
    # Walking away: smaller each beat, drifting up toward the gate.
    walk = _beat(t, 400, 5600)
    scale = 0.92 - walk * 0.22
    cx = int(WIDTH // 2 + walk * 150)
    foot = int(SAFE_BOT - walk * 60)
    bob = int(math.sin(t * 0.012) * 2 * (1 - walk))
    draw_ucilev(surface, cx, foot + bob, scale=scale, facing_right=False)
    # Rifle flat at the side, muzzle down, swinging with the stride.
    swing = math.sin(t * 0.012) * 6 * (1 - walk)
    ex, ey = cx - int(34 * scale), foot - int(120 * scale) + bob
    pygame.draw.line(surface, (10, 11, 13), (ex, ey),
                     (ex - swing, ey + int(96 * scale)), 5)
    # Gate lamp halo where Maru disappeared.
    _ko_glow(surface, _SODIUM, (gx + 110, SAFE_TOP + 70), 200, 26)
    _m3_noise(surface, 4412, count=52, alpha=16)
    _ko_tint(surface)
    _tag(surface, "EAST CHANNEL // HE DOESN'T TURN", _RIVER)


# ────────────────────────────────────────────
# ENDING 8 - the radio
# ────────────────────────────────────────────
def _draw_m5_radio(surface, t):
    """Two men on a wire deciding what neither saw. Split frame: Biribel on
    the wet quay with the handset, Vasile in his new office with the flag on
    the desk. Neither admits anything."""
    surface.fill((6, 7, 11))
    t = max(0, min(t, 8800))
    split = _beat(t, 0, 1600)          # the seam opens between the two lines
    sx = int(WIDTH // 2)
    # LEFT - Biribel, quay, rain, the gate glow behind.
    left = pygame.Surface((sx, HEIGHT))
    _river_set(left, t, lamp=(-160, 0))
    _rain_streaks(left, t, 91, n=50)
    draw_biribel(left, sx - 130, SAFE_BOT + 4, scale=0.82, facing_right=False)
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
    draw_vasile(right, 150, SAFE_BOT - 4, scale=0.86, facing_right=True)
    # Handset cord running off the desk edge.
    pygame.draw.lines(right, (40, 40, 46), False,
                      [(150, SAFE_BOT - 120), (200, SAFE_BOT - 90),
                       (260, SAFE_BOT - 110)], 2)
    surface.blit(right, (sx, 0))
    # The seam: a hard vertical join with a thin broadcast line between them.
    seam = int(sx - (WIDTH - sx) * (1 - split) * 0.0)
    pygame.draw.line(surface, (70, 76, 86), (seam, SCENE_TOP), (seam, SCENE_BOT), 2)
    _ko_glow(surface, (120, 140, 170), (seam, SAFE_TOP + _FILM_H // 2), 120, 14)
    _m3_noise(surface, 6006, count=50, alpha=15)
    _ko_tint(surface)
    _tag(surface, "WIRE // QUAY <-> GUARD HQ", _LIAISON)
