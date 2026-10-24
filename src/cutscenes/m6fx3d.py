"""m6fx3d.py - the Mission 6 FX kit: soft night light, smoke and haze.

M6 shares m5fx3d's rain, sky, smoke, motes, sparks and camera.  Its practical
halos use continuous falloff and depth-aware sprite compositing: the GL path
hides light behind world geometry and drops it when the fixture is occluded,
while the software backend paints the same sprites in layer order.

Colours are the 2D game's sodium amber (``missions.m6.palette3d``, copied
here so this module stays as dependency-light as m5fx3d).  Time is in
MILLISECONDS, as in m5fx3d.
"""
import math

import pygame

from cutscenes import m5fx3d as _m5

__all__ = list(_m5.__all__) + ["AMBER", "SODIUM_PALE", "LAMP_WHITE", "beacon"]

SODIUM = (255, 181, 79)          # palette3d.SODIUM: the 2D lamp amber at full
SODIUM_PALE = (255, 236, 154)    # palette3d.SODIUM_PALE: a lamp's hot side
LAMP_WHITE = (255, 251, 206)     # palette3d.LAMP_WHITE: a bare bulb's core
AMBER = (187, 133, 58)           # palette3d.AMBER: the lamp as the 2D draws it
FX_LAYER = _m5.FX_LAYER
_CACHE = {}
DITHER_STEP = 8                  # the grade's ordered dither: 15-bit, 32 levels

# Falloff peaks.  The hot core is separate geometry (the emissive head), so
# these stay well below 1: a halo is the light in the air, not the bulb.
_LAMP_PEAK = 0.66
_SOFT_PEAK = 1.0

# Sodium colour ramp from the centre out.  Cooling the rim is what keeps a
# halo from reading as a flat orange disc.
_LAMP_RAMP = ((0.0, LAMP_WHITE), (0.24, SODIUM_PALE), (0.58, SODIUM),
              (1.0, AMBER))

def __getattr__(name):
    return getattr(_m5, name)


def _tag(draw):
    draw.light = True
    return draw


def _ramp_colour(stops, rr):
    """Per-pixel colour through ``stops`` ((position, rgb), ...)."""
    import numpy as np
    xs = [s[0] for s in stops]
    out = np.empty(rr.shape + (3,), dtype=np.float32)
    for ch in range(3):
        out[:, :, ch] = np.interp(np.clip(rr, 0.0, 1.0), xs,
                                  [s[1][ch] for s in stops])
    return out


def _stops_for(col, core, k):
    """Scaled colour stops for a halo.  Sodium lamps get the full ramp;
    other practicals fade from a bright centre to a darker version of their
    own colour."""
    def sc(c, f=1.0):
        return tuple(max(0, min(255, int(round(v * k * f)))) for v in c)

    if tuple(col) in (SODIUM, SODIUM_PALE, AMBER) or tuple(col) == (255, 181, 79):
        return tuple((p, sc(c)) for p, c in _LAMP_RAMP)
    hot = core or tuple(min(255, int(v * 0.55 + 170 * 0.45)) for v in col)
    return ((0.0, sc(hot)), (0.30, sc(col)), (1.0, sc(col, 0.52)))


def _halo_img(stops, rx, ry=None, power=2.0, peak=_LAMP_PEAK,
              core=0.0, core_r=0.20, rim=False):
    """Continuous additive halo with a soft core and coloured falloff."""
    ry = rx if ry is None else ry
    rx = max(1, min(260, _m5._bucket(rx)))
    ry = max(1, min(260, _m5._bucket(ry)))
    stops = tuple(stops)
    key = ("halo", stops, rx, ry, power, round(peak, 3),
           round(core, 3), round(core_r, 3), bool(rim))
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
        if rim:
            edge = np.clip((1.06 - rr) / 0.22, 0.0, 1.0)
            fill = np.clip(rr / 0.88, 0.0, 1.0) ** 2
            inten = peak * edge * (0.45 + 0.55 * fill)
        else:
            inten = peak * np.clip(1.0 - rr, 0.0, 1.0) ** power
        if core > 0.0:
            inten = inten + core * np.clip(1.0 - rr / max(0.02, core_r), 0.0, 1.0) ** 1.5
        col = _ramp_colour(stops, rr)
        arr = np.clip(np.round(np.clip(inten, 0.0, 1.0)[:, :, None] * col),
                      0, 255).astype(np.uint8)
        s = pygame.Surface((w, h))
        sa.blit_array(s, arr)
    except ImportError:
        s = pygame.Surface((w, h))
        s.fill((0, 0, 0))
        rimcol = tuple(stops[-1][1])
        for i in range(48, 0, -1):
            f = i / 48.0
            k = peak * (1.0 - f) ** power
            if k <= 0.005:
                continue
            c = tuple(min(255, int(v * k)) for v in rimcol)
            pygame.draw.ellipse(s, c, ((w - int(w * f)) // 2,
                                       (h - int(h * f)) // 2,
                                       max(1, int(w * f)), max(1, int(h * f))))
    _CACHE[key] = s
    return s


def _core_img(col, rad):
    """One small, hard hot centre - the fixture itself, not a ring."""
    rad = max(1, min(10, int(rad)))
    key = ("core", tuple(col), rad)
    s = _CACHE.get(key)
    if s is None:
        s = pygame.Surface((rad * 2 + 2, rad * 2 + 2))
        s.fill((0, 0, 0))
        pygame.draw.circle(s, tuple(col), (rad + 1, rad + 1), rad)
        _CACHE[key] = s
    return s


# ── light sprites (draw(s, sx, sy, scale_px_per_m, z)) ──
def glow(col, radius_m, t=0, pulse=0.0, flicker=0.0, seed=0, core=None, intensity=1.0,
         max_px=36):
    """A practical light's soft halo, sized by real distance.  Beyond ~60 m
    only the core survives, so a far lamp is a pixel of light, not a disc."""
    def draw(s, sx, sy, scale, z):
        k = intensity * _m5._flick(t, seed, flicker) * (1.0 + pulse * math.sin(t * 0.004 + seed))
        k = min(1.0, k)
        if k <= 0.025 or scale < 0.4:
            return
        # fade the air glow before the lamp reads as a disc in fog
        air = max(0.0, min(1.0, (65.0 - z) / 20.0))
        rad = min(max_px, max(1.5, radius_m * scale))
        core_col = core or LAMP_WHITE
        if z <= 62.0 and air > 0.02:
            kk = k * air
            if kk > 0.02:
                stops = _stops_for(col, core_col, kk)
                rx = rad * (0.55 + 0.45 * air)
                _m5._add_at(s, _halo_img(stops, rx, rx, power=2.2,
                                         peak=_LAMP_PEAK,
                                         core=0.38 if core else 0.0,
                                         core_r=0.14), sx, sy)
        ck = k
        cr = max(1.0, min(5.0, rad * 0.14))
        _m5._add_at(s, _core_img(_m5._scale(core_col, ck), cr), sx, sy)
    _tag(draw)
    draw.bounds_m = (radius_m, radius_m)
    draw.bounds_cap_px = (max_px, max_px)
    return draw


def beacon(col, radius_m=0.35, t=0, period_ms=1500.0, phase=0.0,
           intensity=1.0, seed=0):
    """Aviation / IFF lamp: hard on-off at a slow period, no flicker and a
    deliberately smaller halo than a work light."""
    def draw(s, sx, sy, scale, z):
        on = ((t + phase * period_ms) % period_ms) < period_ms * 0.42
        if not on:
            return
        rad = min(12.0, max(1.5, radius_m * scale))
        k = intensity
        stops = _stops_for(col, None, k)
        _m5._add_at(s, _halo_img(stops, rad, rad, power=2.0,
                                 peak=0.62), sx, sy)
        _m5._add_at(s, _core_img(_m5._scale(col, k), max(1.0, rad * 0.42)),
                    sx, sy)
    _tag(draw)
    draw.bounds_m = (radius_m, radius_m)
    draw.bounds_cap_px = (12, 12)
    return draw


def sodium_lamp(t, seed=0, radius_m=2.2, intensity=0.85):
    """Yard or street lamp: amber falloff round a near-white core."""
    return glow(SODIUM, radius_m, t, flicker=0.06, seed=seed, core=LAMP_WHITE,
                intensity=intensity)


def window_glow(col, w_m, h_m, intensity=0.55, t=0, flicker=0.0, seed=0,
                rim=False):
    """A lit window, screen or doorway: a low, smooth squircle bleed.  The
    lit pane is already emissive geometry; this only softens its edge."""
    def draw(s, sx, sy, scale, z):
        k = intensity * _m5._flick(t, seed, flicker)
        if z > 40.0:
            k *= max(0.0, (40.0 - z) / 15.0)
        if k <= 0.01:
            return
        rx, ry = w_m * scale * 1.05, h_m * scale * 1.05
        if rx < 1.5 or ry < 1.5:
            return
        stops = ((0.0, _m5._scale(col, k * 0.55)),
                 (1.0, _m5._scale(col, k)))
        _m5._add_at(s, _halo_img(stops, min(260, rx), min(260, ry),
                                 power=3.0,
                                 peak=_SOFT_PEAK, rim=rim), sx, sy)
    _tag(draw)
    draw.light_soft = True      # a window's bleed, anchor-gated not per-pixel
    draw.bounds_m = (w_m * 1.05, h_m * 1.05)
    draw.bounds_cap_px = (260, 260)
    return draw


def crt_bloom(t, col=(120, 160, 220), w_m=0.6, h_m=0.45, intensity=0.6, seed=0):
    """A cathode-ray screen's glow, breathing with the picture."""
    k = intensity * (0.82 + 0.12 * math.sin(t * 0.0063 + seed) + 0.06 * math.sin(t * 0.031))
    return window_glow(col, w_m * 1.6, h_m * 1.8, k)


def flash(age_ms, col=(255, 236, 200), radius_m=3.0, dur_ms=420):
    """Muzzle or blast flash: a hot soft burst that collapses fast."""
    def draw(s, sx, sy, scale, z):
        if age_ms < 0 or age_ms > dur_ms:
            return
        k = (1.0 - age_ms / dur_ms) ** 2 * _m5.flash_scale()
        rad = min(90, max(1.5, radius_m * scale * (0.6 + 0.6 * k)))
        if rad < 1.5 or k <= 0.02:
            return
        kk = k
        stops = ((0.0, LAMP_WHITE), (0.34, _m5._scale(col, kk)),
                 (1.0, _m5._scale(col, kk * 0.35)))
        _m5._add_at(s, _halo_img(stops, rad, rad, power=2.0,
                                 peak=_SOFT_PEAK, core=0.5, core_r=0.16), sx, sy)
    _tag(draw)
    draw.bounds_m = (radius_m * 1.2, radius_m * 1.2)
    draw.bounds_cap_px = (90, 90)
    return draw


# ── volumetrics ──
def haze(col, radius_m=3.0, t=0, seed=0, intensity=0.16):
    """Low lit fog round a light: a big, very soft blob that breathes.
    No hot core - haze does not glow, it scatters."""
    def draw(s, sx, sy, scale, z):
        rad = min(140, radius_m * scale)
        if rad < 3:
            return
        k = intensity * (0.75 + 0.25 * math.sin(t * 0.0007 + seed * 1.9))
        rad = int(rad * (1.0 + 0.05 * math.sin(t * 0.0009 + seed)))
        kk = k * 0.5
        if kk <= 0.005:
            return
        stops = ((0.0, _m5._scale(col, kk)), (1.0, _m5._scale(col, kk * 0.30)))
        _m5._add_at(s, _halo_img(stops, rad, rad, power=2.6,
                                 peak=_SOFT_PEAK), sx, sy)
    _tag(draw)
    draw.light_soft = True          # fog scatters in front of geometry
    draw.bounds_m = (radius_m * 1.06, radius_m * 1.06)
    draw.bounds_cap_px = (140, 140)
    return draw


def _shaft_img(col, wtop, wbot, h, k):
    """One tapered quad of lit air with continuous lateral falloff."""
    wtop, wbot, h = max(1, min(260, wtop)), max(1, min(260, wbot)), max(2, min(400, h))
    key = ("shaft", tuple(col), wtop, wbot, h, round(k, 4))
    img = _CACHE.get(key)
    if img is not None:
        return img
    w = wbot * 2 + 2
    try:
        import numpy as np
        import pygame.surfarray as sa
        ax = np.abs(np.arange(w, dtype=np.float32) - wbot) / np.maximum(
            1.0, wbot)
        ay = np.arange(h, dtype=np.float32) / max(1.0, h - 1)
        halfw = (wtop + (wbot - wtop) * ay) / np.maximum(1.0, wbot)
        across = np.clip(1.0 - ax[:, None] / np.maximum(0.02, halfw)[None, :],
                         0.0, 1.0) ** 1.5
        down = (1.0 - 0.45 * ay)[None, :]
        inten = np.clip(k * across * down, 0.0, 1.0)
        arr = np.clip(np.round(inten[:, :, None] * np.array(col)[None, None, :]), 0, 255)
        img = pygame.Surface((w, h))
        sa.blit_array(img, arr.astype(np.uint8))
    except ImportError:
        img = pygame.Surface((w, h))
        img.fill((0, 0, 0))
        for y in range(h):
            f = y / max(1, h - 1)
            hw = int((wtop + (wbot - wtop) * f) * 0.5)
            c = tuple(min(255, int(v * k * (1.0 - 0.45 * f) * 0.55)) for v in col)
            pygame.draw.line(img, c, (wbot - hw, y), (wbot + hw, y))
    _CACHE[key] = img
    return img


def light_shaft(col, height_m=5.0, top_m=0.9, bot_m=2.1, t=0, seed=0,
                intensity=0.34, tilt=0.10):
    """A practical's cone through the haze: one tapered quad hung screen-down
    from the lamp, swaying with the wind.  For the two hero platform lamps
    only - a shaft on every lamp was a wall of orange."""
    def draw(s, sx, sy, scale, z):
        h = int(height_m * scale)
        wtop, wbot = int(top_m * scale), int(bot_m * scale)
        if h < 6 or wbot < 2:
            return
        k = intensity * _m5._flick(t, seed, 0.10)
        sway = math.sin(t * 0.0011 + seed * 2.3) * tilt * wbot
        _m5._add_at(s, _shaft_img(col, wtop, wbot, h, k),
                    sx + sway * 0.5, sy + h * 0.5)
    _tag(draw)
    draw.light_soft = True          # a cone of lit air, not a surface
    draw.bounds_m = (bot_m * 1.1, height_m)
    draw.bounds_cap_px = (260, 400)
    return draw


def powder(t, seed=0, spread_m=3.0, intensity=0.5, col=(188, 200, 220), puffs=14):
    """Rotor wash on powder snow: soft puffs that roll outward along the
    ground and lift, no streaks.  ``t`` is the wash clock in ms."""
    def draw(s, sx, sy, scale, z):
        for i in range(puffs):
            u = (math.sin(i * 12.9898 + seed * 78.233) * 43758.5453) % 1.0
            v = (math.sin(i * 39.346 + seed * 11.135) * 24634.6345) % 1.0
            a = u * 6.2832
            life = ((t * 0.00045) + v) % 1.0
            rr = spread_m * (0.25 + 0.75 * life) * scale
            rad = int(min(90, (0.35 + 0.55 * life) * spread_m * 0.32 * scale))
            if rad < 3:
                continue
            k = intensity * (1.0 - life) ** 1.4
            kk = k * 0.5
            if kk <= 0.01:
                continue
            x = sx + math.cos(a) * rr
            y = sy + math.sin(a) * rr * 0.22 - life * 0.25 * spread_m * scale
            stops = ((0.0, _m5._scale(col, kk)), (1.0, _m5._scale(col, kk * 0.25)))
            _m5._add_at(s, _halo_img(stops, rad, int(rad * 0.7), power=2.4,
                                     peak=_SOFT_PEAK), int(x), int(y))
    _tag(draw)
    draw.light_soft = True
    draw.bounds_m = (spread_m * 1.3, spread_m * 0.6)
    draw.bounds_cap_px = (200, 120)
    return draw


# -- M5's legacy PS2 frame helpers; M6 uses the smooth paths in its own scenes --
def _palette():
    from missions.m6 import palette3d   # lazy: the films never import missions.m6 at load
    return palette3d


_BAYER4 = (0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5)


def dither_lut(chan, np):
    """Grade curves -> per-channel tables, one row per 4x4 Bayer threshold:
    the graded value, ordered-dithered down to DITHER_STEP levels.  This is
    the PS2 16-bit framebuffer look, and it lands on the sky and the glow
    sprites as well as the polygons, which the shader's dither never sees."""
    off = (np.arange(16, dtype=np.float32) + 0.5) / 16.0 - 0.5
    lut = np.empty((3, 16 * 256), dtype=np.uint8)
    for i, v in enumerate(chan):
        q = np.floor((v[None, :] * 255.0 + off[:, None] * DITHER_STEP)
                     / DITHER_STEP + 0.5) * DITHER_STEP
        lut[i] = np.clip(q, 0.0, 255.0).astype(np.uint8).ravel()
    return lut


def ink(chan, np):
    """Lift each graded channel onto the 2D game's black (``palette3d.INK``): the 2D
    never goes below (7,8,11), and the old crushed navy-black read as 3D."""
    return [f + v * (1.0 - f) for f, v in
            zip(np.array(_palette().INK, dtype=np.float32) / 255.0, chan)]


def apply_lut(surface, lut, np):
    """Run a ``dither_lut`` table over the buffer: one take per channel,
    indexed by the pixel's Bayer row plus its value."""
    w, h = surface.get_size()
    cell = _CACHE.get(("bayer", w, h))
    if cell is None:
        b = np.array(_BAYER4, dtype=np.uint16).reshape(4, 4) * 256
        cell = np.tile(b, (-(-h // 4), -(-w // 4)))[:h, :w].T.copy()
        _CACHE[("bayer", w, h)] = cell
    arr = pygame.surfarray.pixels3d(surface)
    for i in range(3):
        arr[..., i] = lut[i].take(cell + arr[..., i])
    del arr


def present_crisp(src, dst):
    """Hard-pixel upscale of the internal frame to the screen: nearest x2,
    then a box filter down (sharp bilinear), so the 1.5625 ratio keeps every
    pixel crisp and even instead of the old soft smoothscale."""
    w, h = src.get_size()
    mid = _CACHE.get("present_mid")
    if mid is None or mid.get_size() != (w * 2, h * 2):
        mid = _CACHE["present_mid"] = pygame.Surface((w * 2, h * 2))
    pygame.transform.scale(src, (w * 2, h * 2), mid)
    pygame.transform.smoothscale(mid, dst.get_size(), dst)


def grade_cine(surface):
    """Cinematic contrast/saturation grade on the internal render buffer.

    The old held rig + scanlines read grey because four warm-white sources
    met a 0.5 ambient; this puts the colour back without lifting shadows the
    way m6world3d.grade's gamma does.  Numpy is optional: skip cleanly.
    """
    try:
        import numpy as np
    except Exception:
        return
    lut = _CACHE.get("grade_lut")
    if lut is None:
        x = np.arange(256, dtype=np.float32) / 255.0
        # open the mids a little (the albedo-modulated rigs are dark by design),
        # crush the toe (true blacks), then an S of contrast around the mids
        x = x ** 0.80
        x = np.clip((x - 0.05) / 0.95, 0.0, 1.0)
        x = np.clip(0.42 + (x - 0.42) * 1.12, 0.0, 1.0)
        sh, mid, hi = (1.0 - x) ** 2, 4.0 * x * (1.0 - x), x ** 2
        # split tone: slate shadows, a touch of rust in the mids, warm highs
        chan = (x - 0.006 * sh + 0.010 * mid + 0.030 * hi,
                x + 0.003 * sh + 0.004 * hi,
                x + 0.014 * sh - 0.012 * mid - 0.026 * hi)
        lut = dither_lut(ink([v - 0.10 * np.maximum(0.0, v - 0.86) ** 2
                                for v in chan], np), np)
        _CACHE["grade_lut"] = lut
    # Three vectorised channel lookups: contrast + warm/cool split tone.  The
    # float luma/saturation pass cost ~40 ms on the 800x560 buffer; this keeps
    # the grade cheap enough for the live scene on both backends.
    apply_lut(surface, lut, np)
