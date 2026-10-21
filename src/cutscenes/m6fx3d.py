"""m6fx3d.py - the Mission 6 FX kit: m5fx3d with hard PS2 halos.

M6 shares m5fx3d's rain, sky, smoke, motes, sparks and camera, but not its
glows. M5's halos are smooth radial falloffs; the M6 yard and train are drawn
as a late PS2 game, where a lamp's halo is a flat sprite: a hot core, two or
three flat bands and a dithered one-pixel edge, never a soft bloom. Every
light sprite here (glow / sodium_lamp / window_glow / crt_bloom / flash /
haze / light_shaft) is built from that stepped shape. Anything else is
m5fx3d's own, forwarded by the module ``__getattr__``, so
``from cutscenes import m6fx3d as _fx`` is a drop-in for m5fx3d.

The lamp colours are the 2D game's sodium amber (``missions.m6.palette3d``,
copied here so this module stays as dependency-light as m5fx3d).
Time is in MILLISECONDS, as in m5fx3d.
"""
import math

import pygame

from cutscenes import m5fx3d as _m5

__all__ = list(_m5.__all__) + ["AMBER", "SODIUM_PALE", "LAMP_WHITE"]

SODIUM = (255, 181, 79)          # palette3d.SODIUM: the 2D lamp amber at full
SODIUM_PALE = (255, 236, 154)    # palette3d.SODIUM_PALE: a lamp's hot side
LAMP_WHITE = (255, 251, 206)     # palette3d.LAMP_WHITE: a bare bulb's core
AMBER = (187, 133, 58)           # palette3d.AMBER: the lamp as the 2D draws it
FX_LAYER = _m5.FX_LAYER
_CACHE = {}

# A lamp halo from the centre out: (edge as a fraction of the radius, level).
_LAMP = ((0.34, 0.42), (0.64, 0.20), (1.0, 0.08))
_CORE = ((1.0, 1.0),)
_WINDOW = ((0.62, 1.0), (0.84, 0.48), (1.0, 0.18))
_HAZE = ((0.40, 1.0), (0.72, 0.56), (1.0, 0.24))
_FLASH = ((0.22, 1.0), (0.52, 0.55), (1.0, 0.22))

# 4x4 Bayer matrix: where two bands meet, the edge is ordered-dithered over
# one pixel instead of anti-aliased.
_BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def __getattr__(name):
    return getattr(_m5, name)


def _stepped(col, rx, ry=None, bands=_LAMP, power=2.0):
    """Additive sprite: flat bands of ``col`` out to (rx, ry) pixels.
    ``power`` 2 is a disc or ellipse; higher squares it off toward a
    rectangle (a lit window). Cached by quantised colour and size."""
    ry = rx if ry is None else ry
    rx = max(1, min(260, _m5._bucket(rx)))
    ry = max(1, min(260, _m5._bucket(ry)))
    col = _m5._q(col)
    key = (col, rx, ry, bands, power)
    s = _CACHE.get(key)
    if s is not None:
        return s
    w, h = rx * 2 + 2, ry * 2 + 2
    try:
        import numpy as np
        import pygame.surfarray as sa
        ax = (np.arange(w, dtype=np.float32) - (rx + 0.5)) / rx
        ay = (np.arange(h, dtype=np.float32) - (ry + 0.5)) / ry
        rr = (np.abs(ax)[:, None] ** power + np.abs(ay)[None, :] ** power) ** (1.0 / power)
        bay = (np.array(_BAYER, dtype=np.float32) + 0.5) / 16.0 - 0.5
        rr += np.tile(bay, (w // 4 + 1, h // 4 + 1))[:w, :h] * (1.7 / min(rx, ry))
        lv = np.zeros((w, h), dtype=np.float32)
        for edge, level in reversed(bands):
            lv[rr < edge] = level
        arr = np.clip(np.round(lv[:, :, None] * np.array(col, dtype=np.float32)),
                      0, 255).astype(np.uint8)
        s = pygame.Surface((w, h))
        sa.blit_array(s, arr)
    except ImportError:                       # numpy-less fallback: flat ellipses
        s = pygame.Surface((w, h))
        s.fill((0, 0, 0))
        for edge, level in reversed(bands):
            ew, eh = max(1, int(w * edge)), max(1, int(h * edge))
            pygame.draw.ellipse(s, _m5._scale(col, level),
                                ((w - ew) // 2, (h - eh) // 2, ew, eh))
    _CACHE[key] = s
    return s


# ── light sprites (draw(s, sx, sy, scale_px_per_m, z)) ──
def glow(col, radius_m, t=0, pulse=0.0, flicker=0.0, seed=0, core=None, intensity=1.0,
         max_px=200):
    """A practical light's halo: flat bands and, with ``core``, a hot disc."""
    def draw(s, sx, sy, scale, z):
        k = intensity * _m5._flick(t, seed, flicker) * (1.0 + pulse * math.sin(t * 0.004 + seed))
        k = min(1.0, k)
        rad = min(max_px, 28, radius_m * scale)
        if rad < 1.5 or k <= 0.02:
            return
        _m5._add_at(s, _stepped(_m5._scale(col, k), rad), sx, sy)
        if core is not None and rad > 3:
            _m5._add_at(s, _stepped(_m5._scale(core, k), max(1.5, rad * 0.2), bands=_CORE),
                        sx, sy)
    draw.bounds_m = (radius_m, radius_m)
    draw.bounds_cap_px = (min(max_px, 28), min(max_px, 28))
    return draw


def sodium_lamp(t, seed=0, radius_m=2.2, intensity=0.85):
    """Yard or street lamp: amber bands round a near-white core."""
    return glow(SODIUM, radius_m, t, flicker=0.06, seed=seed, core=LAMP_WHITE,
                intensity=intensity)


def window_glow(col, w_m, h_m, intensity=0.55, t=0, flicker=0.0, seed=0):
    """A lit window, screen or door: a squared-off stepped glow."""
    def draw(s, sx, sy, scale, z):
        k = intensity * _m5._flick(t, seed, flicker)
        rx, ry = w_m * scale * 1.1, h_m * scale * 1.1
        if rx < 1.5 or ry < 1.5 or k <= 0.01:
            return
        _m5._add_at(s, _stepped(_m5._scale(col, k), min(260, rx), min(260, ry),
                                bands=_WINDOW, power=3.0), sx, sy)
    draw.bounds_m = (w_m * 1.1, h_m * 1.1)
    draw.bounds_cap_px = (260, 260)
    return draw


def crt_bloom(t, col=(120, 160, 220), w_m=0.6, h_m=0.45, intensity=0.6, seed=0):
    """A cathode-ray screen's glow, breathing with the picture."""
    k = intensity * (0.82 + 0.12 * math.sin(t * 0.0063 + seed) + 0.06 * math.sin(t * 0.031))
    return window_glow(col, w_m * 1.6, h_m * 1.8, k)


def flash(age_ms, col=(255, 236, 200), radius_m=3.0, dur_ms=420):
    """Muzzle or blast flash: a stepped burst that collapses fast."""
    def draw(s, sx, sy, scale, z):
        if age_ms < 0 or age_ms > dur_ms:
            return
        k = (1.0 - age_ms / dur_ms) ** 2 * _m5.flash_scale()
        rad = min(220, radius_m * scale * (0.6 + 0.6 * k))
        if rad < 1.5:
            return
        _m5._add_at(s, _stepped(_m5._scale(col, k), rad, bands=_FLASH), sx, sy)
    draw.bounds_m = (radius_m * 1.2, radius_m * 1.2)
    draw.bounds_cap_px = (220, 220)
    return draw


# ── volumetrics ──
def haze(col, radius_m=3.0, t=0, seed=0, intensity=0.16):
    """Low lit fog round a light: a few faint flat bands that breathe."""
    def draw(s, sx, sy, scale, z):
        rad = radius_m * scale
        if rad < 3:
            return
        k = intensity * (0.75 + 0.25 * math.sin(t * 0.0007 + seed * 1.9))
        rad = int(rad * (1.0 + 0.05 * math.sin(t * 0.0009 + seed)))
        _m5._add_at(s, _stepped(_m5._scale(col, k * 0.5), rad, bands=_HAZE), sx, sy)
    draw.bounds_m = (radius_m * 1.06, radius_m * 1.06)
    draw.bounds_cap_px = (220, 220)
    return draw


def light_shaft(col, height_m=5.0, top_m=0.9, bot_m=2.1, t=0, seed=0,
                intensity=0.34, tilt=0.10):
    """A practical's cone through the haze, hung screen-down from the lamp:
    a short stack of flat stepped discs widening to the ground."""
    def draw(s, sx, sy, scale, z):
        h = height_m * scale
        wtop, wbot = top_m * scale, bot_m * scale
        if h < 6 or wbot < 2:
            return
        k = intensity * _m5._flick(t, seed, 0.10)
        sway = math.sin(t * 0.0011 + seed * 2.3) * tilt * wbot
        n = max(3, int(h // 22))
        for i in range(n):
            f = i / (n - 1.0)
            kk = k * (1.0 - 0.45 * f)
            if kk <= 0.015:
                continue
            w = wtop + (wbot - wtop) * f
            _m5._add_at(s, _stepped(_m5._scale(col, kk * 0.6), w, bands=_HAZE),
                        sx + sway * f, sy + f * h)
    return draw
