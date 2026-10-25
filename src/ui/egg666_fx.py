"""egg666_fx.py - light halos, the PS2 grade and the crisp present for the 3D "666" scare.

The recipe is the M6 FX kit's (``cutscenes.m6fx3d``): a halo is a small hot
core with a short, ordered-dithered falloff, the grade is a contrast and
split-tone table with an ink floor and a 15-bit Bayer dither, and the present
is nearest x2 then a box filter down.  It is written out here rather than
imported because ``ui`` must not reach into the mission-named FX modules
(``tools/check_boundaries.py`` W1).  Time is in milliseconds.
"""
import math

import numpy as np
import pygame

WARM = (255, 181, 79)            # a lamp's amber
WARM_CORE = (255, 251, 206)      # a bare bulb's core
FX_LAYER = 6                     # the layer practical-light sprites use
INK = (7, 8, 11)                 # the 2D game's black: the grade never goes below it
DITHER = 8                       # the grade's ordered dither: 15-bit, 32 levels
_BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
_RADII = (2, 3, 4, 6, 8, 11, 14, 18, 23, 29, 36, 44, 54, 64, 80)
_cache = {}


# -- accessibility -------------------------------------------------------------
def reduced_motion():
    try:
        from core.state import STATE  # lazy: keep this module free of game state at load
        return bool(getattr(STATE, "reduced_motion", False))
    except Exception:
        return False


def flash_scale():
    """0.35 when the player turned flash reduction on, else 1.0."""
    try:
        from core.user_settings import SETTINGS  # lazy: settings owner
        return 0.35 if SETTINGS.flash_reduction else 1.0
    except Exception:
        return 1.0


# -- light halos ---------------------------------------------------------------
def _flick(t, seed, amount):
    """0..1 brightness multiplier: two incommensurate sines and a rare dip."""
    if amount <= 0:
        return 1.0
    w = 0.5 + 0.25 * math.sin(t * 0.011 + seed * 3.1) + 0.25 * math.sin(t * 0.0047 + seed)
    dip = 0.55 if (int(t // 90 + seed * 7) % 37) == 0 else 1.0
    return (1.0 - amount * w) * dip


def _halo(col, core, rad, k):
    """A quantised, Bayer-dithered additive halo (cached per colour, radius and level)."""
    key = ("halo", col, core, rad, k)
    s = _cache.get(key)
    if s is None:
        w = rad * 2 + 2
        a = (np.arange(w, dtype=np.float32) - (rad + 0.5)) / rad
        rr = np.sqrt(a[:, None] ** 2 + a[None, :] ** 2)
        bay = (np.array(_BAYER, dtype=np.float32) + 0.5) / 16.0 - 0.5
        bay = np.tile(bay, (w // 4 + 1, w // 4 + 1))[:w, :w]
        inten = 0.66 * np.clip(1.0 - rr, 0.0, 1.0) ** 2.2 + 0.38 * np.clip(1.0 - rr / 0.14, 0.0, 1.0) ** 1.5
        q = np.floor(inten * 11 + 0.5 + bay * 0.55) / 11
        q = np.where(inten > 0.0, np.clip(q, 0.0, 1.0), 0.0)
        t = np.clip(rr / 0.6, 0.0, 1.0)[:, :, None]
        colour = np.array(core, dtype=np.float32) * (1.0 - t) + np.array(col, dtype=np.float32) * t
        arr = np.clip(np.round(q[:, :, None] * colour * k + bay[:, :, None] * 0.7), 0, 255).astype(np.uint8)
        s = _cache[key] = pygame.Surface((w, w))
        pygame.surfarray.blit_array(s, arr)
    return s


def glow(col, radius_m, t_ms=0.0, pulse=0.0, flicker=0.0, seed=0, core=WARM_CORE, intensity=1.0,
         max_px=36):
    """A practical light's halo for ``Renderer.add_sprite``: a small hot core
    and a short dithered falloff, sized by real distance.  Tagged so the GL
    compositor hides it behind geometry per pixel."""
    def draw(s, sx, sy, scale, z):
        k = intensity * _flick(t_ms, seed, flicker) * (1.0 + pulse * math.sin(t_ms * 0.004 + seed))
        k = min(1.0, k)
        if k <= 0.025 or scale < 0.4:
            return
        want = min(max_px, max(2.0, radius_m * scale))
        rad = min(_RADII, key=lambda r: abs(r - want))
        img = _halo(col, core, rad, round(k * 16.0) / 16.0)
        s.blit(img, (int(sx - img.get_width() / 2), int(sy - img.get_height() / 2)),
               special_flags=pygame.BLEND_ADD)
    draw.light = True
    draw.bounds_m = (radius_m, radius_m)
    draw.bounds_cap_px = (max_px, max_px)
    return draw


# -- the PS2 frame ---------------------------------------------------------------
def _make_lut():
    x = np.arange(256, dtype=np.float32) / 255.0
    x = x ** 0.80                                   # open the mids
    x = np.clip((x - 0.05) / 0.95, 0.0, 1.0)        # crush the toe: true blacks
    x = np.clip(0.42 + (x - 0.42) * 1.12, 0.0, 1.0)  # an S of contrast
    sh, mid, hi = (1.0 - x) ** 2, 4.0 * x * (1.0 - x), x ** 2
    chan = (x - 0.006 * sh + 0.010 * mid + 0.030 * hi,   # slate shadows, rust mids, warm highs
            x + 0.003 * sh + 0.004 * hi,
            x + 0.014 * sh - 0.012 * mid - 0.026 * hi)
    chan = [v - 0.10 * np.maximum(0.0, v - 0.86) ** 2 for v in chan]
    chan = [f + v * (1.0 - f) for f, v in zip(np.array(INK, dtype=np.float32) / 255.0, chan)]
    off = (np.arange(16, dtype=np.float32) + 0.5) / 16.0 - 0.5
    lut = np.empty((3, 16 * 256), dtype=np.uint8)
    for i, v in enumerate(chan):
        q = np.floor((v[None, :] * 255.0 + off[:, None] * DITHER) / DITHER + 0.5) * DITHER
        lut[i] = np.clip(q, 0.0, 255.0).astype(np.uint8).ravel()
    return lut


def grade(surface):
    """Contrast, split tone, the ink floor and a Bayer dither, on the small frame."""
    lut = _cache.get("lut")
    if lut is None:
        lut = _cache["lut"] = _make_lut()
    w, h = surface.get_size()
    cell = _cache.get(("bayer", w, h))
    if cell is None:
        b = np.array([v for row in _BAYER for v in row], dtype=np.uint16).reshape(4, 4) * 256
        cell = _cache[("bayer", w, h)] = np.tile(b, (-(-h // 4), -(-w // 4)))[:h, :w].T.copy()
    arr = pygame.surfarray.pixels3d(surface)
    for i in range(3):
        arr[..., i] = lut[i].take(cell + arr[..., i])
    del arr


def present(src, dst):
    """Hard-pixel upscale to the screen: nearest x2, then a box filter down."""
    w, h = src.get_size()
    mid = _cache.get("mid")
    if mid is None or mid.get_size() != (w * 2, h * 2):
        mid = _cache["mid"] = pygame.Surface((w * 2, h * 2))
    pygame.transform.scale(src, (w * 2, h * 2), mid)
    pygame.transform.smoothscale(mid, dst.get_size(), dst)
