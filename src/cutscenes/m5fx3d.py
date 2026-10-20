"""m5fx3d.py - FX kit for the Mission 5 3D cutscenes (m5martial3d / m5mid3d).

The production layers the M2 oil-rig cinematic has and M5 lacked:

    light sprites   glow / sodium_lamp / window_glow / crt_bloom / scope_glint /
                    wet_reflection / dust_motes / flash / sparks - all
                    ``draw(s, sx, sy, scale, z)`` callbacks for ``r.add_sprite``
                    (depth-scaled, depth-masked on GL, painter-sorted on software)
    volumetrics     light_shaft (a practical's cone through the haze) /
                    haze (low ground fog around a light) / glint (wet sheen)
    rain3d          world-space rain in two depth bands around the camera, tinted
                    near practical lights, plus ground splash crowns
    night_sky       horizon-locked gradient, stars + moon with camera parallax,
                    drifting cloud bands, sodium sky-glow, horizon mist
    cig_smoke       a lit cigarette's wisp: puffs that expand, drift and fade
    set_cam         smoothstep framing + handheld drift + roll + decaying shake;
                    every non-scripted motion is zeroed under reduced motion

Dependency-light on purpose: pygame + math only at import time (core.state is
read lazily), so any cutscenes part can import it without load-order cycles.
Additive glows are pre-baked RGB surfaces blitted with BLEND_ADD and cached by
(colour, radius bucket) - no per-frame Surface allocation in steady state.
Time is in MILLISECONDS (the M5 time base).
"""
import math
import random

import pygame

__all__ = ["reduced_motion", "glow", "sodium_lamp", "window_glow", "crt_bloom",
           "scope_glint", "wet_reflection", "dust_motes", "flash", "sparks",
           "rain3d", "night_sky", "handheld", "shake", "set_cam", "SODIUM", "FX_LAYER",
           "light_shaft", "haze", "glint", "cig_smoke"]

SODIUM = (255, 168, 84)      # low-pressure sodium: the colour of the city at night
FX_LAYER = 6                 # same layer M2 uses for its practicals
_TAU = math.pi * 2.0
_CACHE = {}


# ── settings ──
def reduced_motion():
    """True when the player turned on reduced motion (same flag M2 reads)."""
    try:
        from core.state import STATE  # lazy: keep this module free of game imports at load
        return bool(getattr(STATE, "reduced_motion", False))
    except Exception:
        return False


def shake_scale():
    """RPE6 P9: accessibility shake multiplier (live SETTINGS; 1.0 = legacy)."""
    try:
        from core.user_settings import SETTINGS
        return max(0.0, min(1.0, float(SETTINGS.shake_scale)))
    except Exception:
        return 1.0


def flash_scale():
    """RPE6 P9: 0.35 when flash reduction is on (peak flash intensity), else 1.0."""
    try:
        from core.user_settings import SETTINGS
        return 0.35 if SETTINGS.flash_reduction else 1.0
    except Exception:
        return 1.0


# ── baked additive shapes ──
def _q(c, steps=12):
    """Quantise a colour so per-frame flicker reuses cached surfaces."""
    return tuple(min(255, max(0, int(round(v / steps) * steps))) for v in c)


def _bucket(rad):
    rad = int(rad)
    if rad > 96:
        return rad - rad % 8
    if rad > 24:
        return rad - rad % 3
    return rad


def _halo(col, rad, power=2.2):
    """Round additive glow: black RGB surface, colour falling off to 0 at ``rad``."""
    rad = max(2, min(220, _bucket(rad)))
    col = _q(col)
    key = ("h", col, rad, power)
    s = _CACHE.get(key)
    if s is None:
        s = _halo_smooth(col, rad, power)
        _CACHE[key] = s
    return s


# 4x4 Bayer matrix, centred on 0 (-0.5..0.5 LSB): breaks the 8-bit steps of a
# dim, wide falloff into a fine grain instead of visible contour rings.
_BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def _halo_smooth(col, rad, power):
    """Per-pixel radial falloff (the old version stacked <= 18 flat circles,
    which read as hard concentric bands on every lamp in M5)."""
    d = rad * 2 + 2
    try:
        import numpy as np
        import pygame.surfarray as sa
        ax = np.arange(d, dtype=np.float32) - (rad + 1)
        rr = np.sqrt(ax[:, None] ** 2 + ax[None, :] ** 2) / float(rad)
        f = np.clip(1.0 - rr, 0.0, 1.0)
        k = f ** power + 0.04 * f
        bay = (np.array(_BAYER, dtype=np.float32) + 0.5) / 16.0 - 0.5
        dith = np.tile(bay, (d // 4 + 1, d // 4 + 1))[:d, :d]
        arr = np.empty((d, d, 3), dtype=np.uint8)
        for ch in range(3):
            v = k * col[ch] + dith * (k > 0)
            arr[:, :, ch] = np.clip(np.round(v), 0, 255).astype(np.uint8)
        s = pygame.Surface((d, d))
        sa.blit_array(s, arr)
        return s
    except ImportError:                       # numpy-less fallback: many fine rings
        s = pygame.Surface((d, d))
        s.fill((0, 0, 0))
        steps = max(8, rad)
        for i in range(steps, 0, -1):
            f = i / steps
            k = (1.0 - f) ** power + 0.04 * (1.0 - f)
            pygame.draw.circle(s, (int(col[0] * k), int(col[1] * k), int(col[2] * k)),
                               (rad + 1, rad + 1), max(1, int(rad * f)))
        return s


def _ellipse(col, rx, ry, power=2.0):
    rx, ry = max(2, min(260, _bucket(rx))), max(2, min(260, _bucket(ry)))
    col = _q(col)
    key = ("e", col, rx, ry, power)
    s = _CACHE.get(key)
    if s is None:
        base = _halo(col, 48, power)
        s = pygame.transform.smoothscale(base, (rx * 2 + 2, ry * 2 + 2))
        _CACHE[key] = s
    return s


def _add_at(s, img, cx, cy):
    s.blit(img, (int(cx - img.get_width() / 2), int(cy - img.get_height() / 2)),
           special_flags=pygame.BLEND_ADD)


def _scale(c, k):
    return (min(255, int(c[0] * k)), min(255, int(c[1] * k)), min(255, int(c[2] * k)))


def _flick(t, seed, amount):
    """0..1 brightness multiplier: two incommensurate sines + a rare dip."""
    if amount <= 0:
        return 1.0
    w = 0.5 + 0.25 * math.sin(t * 0.011 + seed * 3.1) + 0.25 * math.sin(t * 0.0047 + seed)
    dip = 0.55 if (int(t // 90 + seed * 7) % 37) == 0 else 1.0
    return (1.0 - amount * w) * dip


# ── light sprites (draw(s, sx, sy, scale_px_per_m, z)) ──
def glow(col, radius_m, t=0, pulse=0.0, flicker=0.0, seed=0, core=None, intensity=1.0,
         max_px=200):
    """Soft additive halo on a practical light. ``core`` = small hot centre."""
    def draw(s, sx, sy, scale, z):
        k = intensity * _flick(t, seed, flicker) * (1.0 + pulse * math.sin(t * 0.004 + seed))
        # A fixture halo is not a light source on foreground faces.
        k = min(.18, k * .35)
        rad = min(max_px, 28, radius_m * scale)
        if rad < 1.5 or k <= 0.02:
            return
        _add_at(s, _halo(_scale(col, k), rad), sx, sy)
        if core is not None and rad > 3:
            _add_at(s, _halo(_scale(core, k), max(2, rad * 0.22), 1.2), sx, sy)
    draw.bounds_m = (radius_m, radius_m)
    draw.bounds_cap_px = (min(max_px, 28), min(max_px, 28))
    return draw


def sodium_lamp(t, seed=0, radius_m=2.2, intensity=0.85):
    """Street lamp: wide warm pool + hot near-white core, barely-there flicker."""
    return glow(SODIUM, radius_m, t, flicker=0.06, seed=seed, core=(255, 226, 170),
                intensity=intensity)


def window_glow(col, w_m, h_m, intensity=0.55, t=0, flicker=0.0, seed=0):
    """Soft rectangular-ish glow for a lit window / screen / door."""
    def draw(s, sx, sy, scale, z):
        k = intensity * _flick(t, seed, flicker)
        rx, ry = w_m * scale * 1.1, h_m * scale * 1.1
        if rx < 1.5 or ry < 1.5:
            return
        _add_at(s, _ellipse(_scale(col, k), min(260, rx), min(260, ry)), sx, sy)
    draw.bounds_m = (w_m * 1.1, h_m * 1.1)
    draw.bounds_cap_px = (260, 260)
    return draw


def crt_bloom(t, col=(120, 160, 220), w_m=0.6, h_m=0.45, intensity=0.6, seed=0):
    """Cathode-ray bloom: cool, breathing with the picture, slight 50 Hz roll."""
    k = intensity * (0.82 + 0.12 * math.sin(t * 0.0063 + seed) + 0.06 * math.sin(t * 0.031))
    return window_glow(col, w_m * 1.6, h_m * 1.8, k)


def scope_glint(strength, col=(255, 236, 210)):
    """Lens glint off an optic: halo + thin cross flare. strength 0..1."""
    def draw(s, sx, sy, scale, z):
        if strength <= 0.02:
            return
        rad = max(4, min(60, 0.25 * scale)) * (0.6 + 0.6 * strength)
        _add_at(s, _halo(_scale(col, strength), rad * 2.2), sx, sy)
        ln = rad * (3.0 + 3.0 * strength)
        c = _scale(col, 0.75 * strength)
        pygame.draw.line(s, c, (sx - ln, sy), (sx + ln, sy), 1)
        pygame.draw.line(s, c, (sx, sy - ln * 0.45), (sx, sy + ln * 0.45), 1)
        pygame.draw.circle(s, _scale(col, strength), (int(sx), int(sy)), max(1, int(rad * 0.25)))
    return draw


def wet_reflection(col, t, seed=0, length_m=2.4, width_m=0.35, intensity=0.5):
    """Light smeared on wet ground/water: a vertical, wavering stack of dashes
    running DOWN-screen from the anchor (anchor = where the light meets the ground)."""
    def draw(s, sx, sy, scale, z):
        w = width_m * scale
        ln = length_m * scale
        if w < 1.0:
            return
        n = 9
        for i in range(n):
            f = i / (n - 1)
            k = intensity * (1.0 - f) ** 1.4 * (0.75 + 0.25 * math.sin(t * 0.009 + i * 1.9 + seed))
            if k <= 0.03:
                continue
            x = sx + math.sin(t * 0.0045 + i * 1.3 + seed) * w * 0.45
            y = sy + f * ln
            _add_at(s, _ellipse(_scale(col, k), max(2, w * (1.0 - 0.4 * f)), max(2, ln / n * 0.9)),
                    x, y)
    return draw


def dust_motes(t, seed=0, count=26, spread_m=(1.6, 1.4), col=(150, 140, 120)):
    """Slow particles hanging in a light beam (anchor = beam centre)."""
    rng = random.Random(seed)
    motes = [(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(0.3, 1.0),
              rng.uniform(0, _TAU)) for _ in range(count)]

    def draw(s, sx, sy, scale, z):
        ax, ay = spread_m[0] * scale, spread_m[1] * scale
        if ax < 4:
            return
        for ux, uy, b, ph in motes:
            x = sx + (ux + 0.08 * math.sin(t * 0.0005 + ph)) * ax
            y = sy + (((uy + 1.0 + t * 0.00004 * b) % 2.0) - 1.0) * ay
            tw = 0.55 + 0.45 * math.sin(t * 0.002 + ph * 3.0)
            _add_at(s, _halo(_scale(col, b * tw), max(2, scale * 0.012)), x, y)
    draw.bounds_m = (spread_m[0] * 1.1 + 0.05, spread_m[1] * 1.1 + 0.05)
    return draw


def cap_flash(surface, knee=170, slope=0.25):
    """RPE6 P9: soft luminance ceiling for flash reduction.

    Channels above ``knee`` are compressed by ``slope``, so a white-out
    peak lands near knee + (255-knee)*slope (~191) instead of 255, while
    everything below the knee is untouched.  Applied by takes whose
    brightest beat is the point of the shot (the breach backlight).
    """
    import numpy as np
    import pygame
    arr = pygame.surfarray.pixels3d(surface)
    over = arr > knee
    arr[over] = knee + (arr[over].astype(np.int32) - knee) * slope
    del arr


def flash(age_ms, col=(255, 236, 200), radius_m=3.0, dur_ms=420):
    """Blast / muzzle flash: big additive bloom that collapses fast."""
    def draw(s, sx, sy, scale, z):
        if age_ms < 0 or age_ms > dur_ms:
            return
        k = (1.0 - age_ms / dur_ms) ** 2 * flash_scale()   # RPE6 P9: flash reduction caps the peak
        _add_at(s, _halo(_scale(col, k), min(220, radius_m * scale * (0.6 + 0.6 * k))), sx, sy)
    draw.bounds_m = (radius_m * 1.2, radius_m * 1.2)
    draw.bounds_cap_px = (220, 220)
    return draw


def sparks(seed, age_ms, col=(255, 200, 120), n=18, speed_m=4.0, dur_ms=700):
    """Ballistic sparks thrown from the anchor (screen space, depth-scaled)."""
    rng = random.Random(seed)
    parts = [(rng.uniform(-math.pi, 0.15), rng.uniform(0.35, 1.0)) for _ in range(n)]

    def draw(s, sx, sy, scale, z):
        if age_ms < 0 or age_ms > dur_ms:
            return
        a = age_ms / 1000.0
        fade = 1.0 - age_ms / dur_ms
        for ang, v in parts:
            vx, vy = math.cos(ang) * v * speed_m, math.sin(ang) * v * speed_m
            x = sx + vx * a * scale
            y = sy + (vy * a + 4.9 * a * a) * scale
            tx, ty = x - vx * 0.03 * scale, y - (vy + 9.8 * a) * 0.03 * scale
            pygame.draw.line(s, _scale(col, fade), (tx, ty), (x, y), 1)
    return draw


# ── volumetrics / sheen ──────────────────────────────────────────────────
def light_shaft(col, height_m=5.0, top_m=0.9, bot_m=2.1, t=0, seed=0,
                intensity=0.34, tilt=0.10):
    """A practical's cone through the haze: anchored at the lamp head, a soft
    stack of light falling and widening to the ground. Screen-space cheat
    anchored in 3D (same idiom as wet_reflection): the shaft hangs along
    screen-down from the light, sways with the wind and breathes with the
    flicker, so the halo reads as a VOLUME of lit haze, not a flat sticker."""
    def draw(s, sx, sy, scale, z):
        h = height_m * scale
        wtop, wbot = top_m * scale, bot_m * scale
        if h < 6 or wbot < 2:
            return
        k = intensity * _flick(t, seed, 0.10)
        sway = math.sin(t * 0.0011 + seed * 2.3) * tilt * wbot
        n = max(3, int(h // 22))
        for i in range(n):
            f = i / (n - 1.0)
            w = wtop + (wbot - wtop) * f
            kk = k * (1.0 - 0.45 * f) * (0.75 + 0.25 * math.sin(t * 0.003 + seed + i))
            if kk <= 0.015:
                continue
            _add_at(s, _halo(_scale(col, kk), w, 2.4), sx + sway * f, sy + f * h)
    return draw


def haze(col, radius_m=3.0, t=0, seed=0, intensity=0.16):
    """Low ground fog: a big, slow, very soft additive blob that breathes -
    the medium a light shaft needs to be visible in."""
    def draw(s, sx, sy, scale, z):
        rad = radius_m * scale
        if rad < 3:
            return
        k = intensity * (0.75 + 0.25 * math.sin(t * 0.0007 + seed * 1.9))
        rad = int(rad * (1.0 + 0.05 * math.sin(t * 0.0009 + seed)))
        _add_at(s, _halo(_scale(col, k), rad, 2.8), sx, sy)
    draw.bounds_m = (radius_m * 1.06, radius_m * 1.06)
    draw.bounds_cap_px = (220, 220)
    return draw


def glint(col, radius_m=0.35, t=0, seed=0, intensity=0.8, rate=1.0):
    """Small shimmering highlight: a wet shoulder catching the key, an ember's
    breath, glass. Faster and tighter than glow()."""
    def draw(s, sx, sy, scale, z):
        rad = radius_m * scale
        if rad < 1.2:
            return
        k = intensity * (0.55 + 0.45 * math.sin(t * 0.004 * rate + seed * 2.2))
        _add_at(s, _halo(_scale(col, k * 0.6), rad * 2.0), sx, sy)
        _add_at(s, _halo(_scale(col, k), max(1.5, rad * 0.5), 1.3), sx, sy)
    draw.bounds_m = (radius_m * 2.05, radius_m * 2.05)
    draw.bounds_cap_px = (220, 220)
    return draw


def cig_smoke(t, seed=0, drift=(0.12, -0.5), intensity=0.30, life_ms=2600):
    """A lit cigarette's wisp: puffs that expand, rise and fade. Alpha-blended
    (smoke DIMS, so it must not be additive). Anchor at the ember."""
    puffs = []
    rng = random.Random(seed)
    for i in range(5):
        puffs.append((rng.uniform(0.0, 1.0), rng.uniform(0.7, 1.3), rng.uniform(0, _TAU)))
    strip = None

    def draw(s, sx, sy, scale, z):
        nonlocal strip
        if scale < 2:
            return
        if strip is None:
            r = 26
            strip = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            for i in range(r, 0, -1):
                f = (1 - i / r) ** 1.6
                pygame.draw.circle(strip, (176, 172, 168, int(120 * f)), (r, r), i)
        for ph, sp, off in puffs:
            age = ((t / float(life_ms) + ph) % 1.0)
            if age <= 0.02:
                continue
            rise = age * .45 * scale * sp
            px = sx + (drift[0] + math.sin(off + age * 5.0) * 0.35) * age * scale * sp
            py = sy - rise + drift[1] * age * scale * 0.3
            r = (0.8 + age * 2.0) * scale / 6.0
            a = int(150 * intensity / 0.30 * (1 - age) ** 1.4)
            if a > 4 and r > 0.6:
                img = pygame.transform.scale(strip, (int(r * 2), int(r * 2)))
                img.set_alpha(min(255, a))
                s.blit(img, (int(px - r), int(py - r)))
    return draw


# ── rain ──
def rain3d(r, t, seed=0, n_near=70, n_far=150, lights=(), col=(96,104,120),
           wind=(.35,.1), ground=0.0, splashes=10, layer=FX_LAYER,
           near_d0=1.2, near_ln=.5, surface=None):
    """World-lattice drops; contact ripples only on declared horizontal surfaces.

    No lens-space splash sprites. The falling drop and its impact share one
    stable world position and clock; walls/void/interiors cannot emit crowns.
    """
    from engine3d.core import quad_xz
    cx, cy, cz = r.cam
    total = n_near + n_far
    for i in range(total):
        u = ((math.sin((i+1)*12.9898+seed*78.233)*43758.5453) % 1.0)
        v = ((math.sin((i+1)*4.1414+seed*9.17)*24634.6345) % 1.0)
        x = math.floor(cx/8)*8 + (u*2-1)*22
        z = math.floor(cz/8)*8 + (v*2-1)*22
        hit = surface(x,z) if surface is not None else None
        floor = ground if hit is None else hit
        phase = (t*.009 + u*97 + v*31) % 12.0
        y = floor + 12.0 - phase
        distance = math.sqrt((x-cx)**2+(y-cy)**2+(z-cz)**2)
        if distance < max(2.5, near_d0):
            continue
        if phase < 11.72:
            ln = min(near_ln if distance < 7 else .42, y-floor)
            r.add_line3d((x,y,z),(x-wind[0]*ln*.2,y-ln,z-wind[1]*ln*.2),
                         _scale(col,.45),1,layer=layer)
        elif hit is not None and splashes:
            age = (phase-11.72)/.28
            w = .018+.065*age
            # Flat, dim contact ring at the collision plane; no airborne rays.
            for a,b in ((-w,w),(w,-w)):
                r.add_line3d((x+a,hit+.016,z-w*.4),(x+b,hit+.016,z+w*.4),
                             _scale(col,.35*(1-age)),1,layer=2)


# ── sky ──
def night_sky(r, buf, t, top, bot, *, stars=60, moon=False, clouds=4, sodium=None,
              mist=(26, 30, 40), seed=0, star_cut=0.0):
    """Fill ``buf`` with a night sky locked to the camera's horizon: gradient,
    stars + moon parked at fixed azimuths (so they parallax with yaw), drifting
    cloud bands, a warm city sky-glow (``sodium`` colour) and a mist band.
    ``star_cut``: 0 clear .. 1 fully overcast."""
    w, h = buf.get_size()
    hy = int(max(-h, min(h * 2, r.horizon_y())))
    key = ("sky", w, h, top, bot)
    grad = _CACHE.get(key)
    if grad is None:
        gh = h * 3
        grad = pygame.Surface((w, gh))
        for y in range(gh):
            f = min(1.0, max(0.0, (y - h * 0.2) / (h * 1.6)))
            f = f ** 0.8
            pygame.draw.line(grad, tuple(int(a + (b - a) * f) for a, b in zip(top, bot)),
                             (0, y), (w, y))
        _CACHE[key] = grad
    buf.blit(grad, (0, 0), area=pygame.Rect(0, max(0, min(2 * h, int(h * 1.8) - hy)), w, h))
    yaw = math.degrees(math.atan2(r.fwd[0], r.fwd[2]))
    px_deg = w / max(1.0, r.fov)
    if stars and star_cut < 1.0 and hy > 4:
        rng = random.Random(seed + 404)
        for i in range(stars):
            az, el, tw = rng.uniform(-180, 180), rng.uniform(0.04, 1.0), rng.random()
            if rng.random() < star_cut:
                continue
            x = int(w / 2 + ((az - yaw + 180) % 360 - 180) * px_deg)
            y = int(hy - el * min(hy, h) * 0.98)
            if 0 <= x < w and 0 <= y < hy - 3:
                b = int((60 + 120 * tw) * (0.55 + 0.45 * math.sin(t * 0.0017 + i)))
                buf.set_at((x, y), (b, b, min(255, int(b * 1.12))))
    if moon and hy > 10:
        mx = w / 2 + ((moon[0] - yaw + 180) % 360 - 180) * px_deg
        my = hy - moon[1] * px_deg
        if -60 < mx < w + 60:
            _add_at(buf, _halo((60, 66, 80), max(12, px_deg * 4.0)), mx, my)
            pygame.draw.circle(buf, (214, 220, 226), (int(mx), int(my)), max(2, int(px_deg * 0.55)))
    for i in range(clouds):
        cw = int(w * (0.45 + 0.12 * i))
        ch = max(6, int(h * (0.05 + 0.02 * i)))
        drift = t * 0.004 * (1 + 0.4 * i)
        x = int((i * w * 0.37 + drift - yaw * px_deg * (0.9 + 0.05 * i)) % (w + cw)) - cw
        y = int(hy - h * (0.12 + 0.11 * i))
        if y + ch < 0 or y > h:
            continue
        band = _CACHE.get(("cloud", cw, ch))
        if band is None:
            band = pygame.Surface((cw, ch), pygame.SRCALPHA)
            for inset, a in ((0, 30), (1, 26), (2, 20), (3, 14)):
                pygame.draw.ellipse(band, (6, 8, 12, a),
                                    (inset * cw // 10, inset * ch // 9,
                                     cw - inset * cw // 5, ch - inset * 2 * ch // 9))
            _CACHE[("cloud", cw, ch)] = band
        buf.blit(band, (x, y))
    if sodium is not None and -h < hy < h * 2:
        _add_at(buf, _ellipse(sodium, w * 0.7, max(8, h * 0.2)), w * 0.5, hy)
    if mist is not None and -20 < hy < h + 20:
        _add_at(buf, _ellipse(mist, w * 0.9, max(4, h * 0.05)), w * 0.5, hy)


# ── camera ──
def handheld(t, amp, seed=0):
    """Breathing-camera offset (m): low-frequency sines, never a shake."""
    if amp <= 0 or reduced_motion():
        return (0.0, 0.0, 0.0)
    a = t * 0.001 * _TAU
    x = amp * (0.6 * math.sin(a * 0.37 + seed) + 0.4 * math.sin(a * 0.13 + seed * 2.1))
    y = amp * 0.7 * (0.6 * math.sin(a * 0.61 + seed * 1.3) + 0.4 * math.sin(a * 0.21 + seed * .7))
    z = amp * 0.4 * math.sin(a * 0.17 + seed * 3.3)
    return (x, y, z)


def shake(t, t_hit, dur_ms, amp):
    """Decaying impact shake -> (dx, dy, roll_deg, px). Zero under reduced motion."""
    if amp <= 0 or t < t_hit or t > t_hit + dur_ms or reduced_motion():
        return (0.0, 0.0, 0.0, 0)
    k = (1.0 - (t - t_hit) / float(dur_ms)) ** 2
    a = t * 0.06
    return (amp * k * math.sin(a * 1.7), amp * k * 0.7 * math.cos(a * 2.3),
            min(1.4, amp * k * 30.0) * math.sin(a * 1.1), int(round(2 * k * math.sin(a * 3.1))))


def set_cam(r, t, eye, tgt, fov, hh=0.0, seed=0, roll=0.0, shk=None):
    """set_camera + handheld drift + roll (+ an optional ``shake`` tuple).
    Returns the 2D pixel offset to apply after presenting (0 if none)."""
    h = handheld(t, hh * shake_scale(), seed)   # RPE6 P9: shake scale applies to handheld too
    dx = dy = sroll = 0.0
    px = 0
    if shk is not None:
        dx, dy, sroll, px = shk
    rm = reduced_motion()
    eye = (eye[0] + h[0] + dx, eye[1] + h[1] + dy, eye[2] + h[2])
    tgt = (tgt[0] + h[0] * 0.35 + dx * 0.5, tgt[1] + h[1] * 0.35 + dy * 0.5, tgt[2])
    rl = 0.0 if rm else max(-1.4, min(1.4, roll + sroll))
    r.set_camera(eye, tgt, fov, roll=rl)
    return 0 if rm else px
