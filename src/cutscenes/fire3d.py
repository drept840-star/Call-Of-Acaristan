"""Procedural turbulent fire, warm-underlit smoke, ember beds and rising sparks.

Shared by 3D scenes/cutscenes (``cutscenes.m7world3d``, ``oil_rig_3d``,
``missions.walking_attack3d``, ``missions.m8.revenge.trap3d``) and 2.5D
top-down renderers (``missions.m1..m6.draw3d``).

Design:
  * Cyclic seamless 2D advected turbulence baked lazily per (variant, frame)
    into paired surfaces: a saturated feathered ``SRCALPHA`` flame body (so
    outer tongues hold rich crimson/orange contrast even against bright sky or
    plaster walls) and a ``BLEND_RGB_ADD`` incandescent core + air halo.
  * Billowing multi-lobe smoke puffs lit from below by the fire while young,
    cooling into charcoal soot as they rise from the upper flame tips.
  * Feathered ground ember beds + continuous rising cooling sparks.
  * Pitch-aware row-by-row depth testing via ``draw_depth`` + ``phys_occ=True``
    on ``GLRenderer``, while staying 100% compatible with ``SoftwareRenderer``.

Dependency-light and deterministic (no global ``random`` state touched).
"""
from collections import OrderedDict
import math

import pygame

_N_FRAMES = 24
_N_VARIANTS = 3
_FRAME_MS = 34.0            # ~29.4 fps cyclic playback -> 816 ms seamless loop
_BASE_W, _BASE_H = 64, 96
_SMOKE_SZ = 64
_BED_SZ = 72

_NOISE_TILES = OrderedDict()
_BASE_FLAMES = OrderedDict()
_SCALED_FLAMES = OrderedDict()
_SMOKE_BASE = OrderedDict()
_SMOKE_SCALED = OrderedDict()
_BED_BASE = OrderedDict()
_BED_SCALED = OrderedDict()
_HALO_CACHE = OrderedDict()
_SCRATCH = {"rgba": None, "rgb": None}


def _lru_get(cache, key):
    val = cache.get(key)
    if val is not None:
        cache.move_to_end(key)
    return val


def _lru_put(cache, key, val, cap):
    if len(cache) >= cap:
        cache.popitem(last=False)
    cache[key] = val
    return val


def _clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else (hi if v > hi else v)


def _scratch(kind, w, h):
    """Reusable scratch subsurface for masked partial occlusion (no allocs)."""
    cur = _SCRATCH.get(kind)
    if cur is None or cur.get_width() < w or cur.get_height() < h:
        sw = max(256, (w + 63) // 64 * 64)
        sh = max(256, (h + 63) // 64 * 64)
        flags = pygame.SRCALPHA if kind == "rgba" else 0
        cur = _SCRATCH[kind] = pygame.Surface((sw, sh), flags)
    return cur.subsurface((0, 0, w, h))


# ── deterministic periodic noise (NumPy) ───────────────────────────────────

def _noise_tile(grid_n, out_n, seed):
    key = (grid_n, out_n, seed)
    hit = _lru_get(_NOISE_TILES, key)
    if hit is not None:
        return hit
    import numpy as np
    rng = np.random.default_rng(seed)
    g = rng.random((grid_n, grid_n), dtype=np.float32)
    c = np.arange(out_n, dtype=np.float32) * (grid_n / float(out_n))
    i0 = np.floor(c).astype(np.int32) % grid_n
    i1 = (i0 + 1) % grid_n
    t = c - np.floor(c)
    s = t * t * (3.0 - 2.0 * t)
    wx = s[:, None]
    wy = s[None, :]
    gx = g[i0, :] * (1.0 - wx) + g[i1, :] * wx
    out = gx[:, i0] * (1.0 - wy) + gx[:, i1] * wy
    return _lru_put(_NOISE_TILES, key, np.ascontiguousarray(out), 24)


def _sample_tile(tile, u, v, np):
    n = tile.shape[0]
    fx = (u % 1.0) * n
    fy = (v % 1.0) * n
    x0 = np.floor(fx).astype(np.int32) % n
    y0 = np.floor(fy).astype(np.int32) % n
    x1 = (x0 + 1) % n
    y1 = (y0 + 1) % n
    tx = fx - np.floor(fx)
    ty = fy - np.floor(fy)
    c00 = tile[x0, y0]
    c10 = tile[x1, y0]
    c01 = tile[x0, y1]
    c11 = tile[x1, y1]
    a = c00 * (1.0 - tx) + c10 * tx
    b = c01 * (1.0 - tx) + c11 * tx
    return a * (1.0 - ty) + b * ty


def _smooth_2d(arr, passes=2):
    """Separable 5-tap blur on (W, H) float32 array for soft radiant bloom."""
    out = arr
    for _ in range(passes):
        tmp = (
            0.12 * out
            + 0.22 * (arr_roll_x := out * 0.0)  # placeholder replaced below
        )
        del tmp, arr_roll_x
        break
    import numpy as np
    for _ in range(passes):
        p = np.pad(out, ((2, 2), (0, 0)), mode="constant")
        h = (p[:-4, :] + p[4:, :]) * 0.12 + (p[1:-3, :] + p[3:-1, :]) * 0.22 + p[2:-2, :] * 0.32
        p2 = np.pad(h, ((0, 0), (2, 2)), mode="constant")
        out = (p2[:, :-4] + p2[:, 4:]) * 0.12 + (p2[:, 1:-3] + p2[:, 3:-1]) * 0.22 + p2[:, 2:-2] * 0.32
    return out


# ── procedural flame atlas ─────────────────────────────────────────────────

_FIRE_STOPS = (0.0, 0.16, 0.38, 0.64, 0.88, 1.0)
_FIRE_R = (84.0, 178.0, 244.0, 255.0, 255.0, 255.0)
_FIRE_G = (10.0, 24.0, 82.0, 166.0, 224.0, 248.0)
_FIRE_B = (2.0, 4.0, 12.0, 32.0, 112.0, 200.0)


def _build_flame_base(variant, frame_idx):
    """Build (body_srcalpha, add_rgb) surfaces at ``_BASE_W x _BASE_H``."""
    W, H = _BASE_W, _BASE_H
    phase = (frame_idx % _N_FRAMES) / float(_N_FRAMES)
    theta = phase * math.tau
    try:
        import numpy as np
        import pygame.surfarray as sa
        tile_lo = _noise_tile(7, 128, 1307 + variant * 97)
        tile_hi = _noise_tile(13, 128, 5113 + variant * 131)

        u = np.linspace(-1.0, 1.0, W, dtype=np.float32)[:, None]
        # v = 0.0 at bottom row (y = H - 1), v = 1.0 at top row (y = 0)
        v = np.linspace(1.0, 0.0, H, dtype=np.float32)[None, :]

        n1 = _sample_tile(tile_lo, u * 0.55 + 0.13 * variant, v * 0.82 - phase, np)
        n2 = _sample_tile(tile_hi, u * 1.05 - 0.16 * np.sin(theta + v * 2.2), v * 1.60 - phase * 2.0, np)
        n3 = _sample_tile(tile_lo, u * 2.05 + 0.37, v * 2.95 - phase * 3.0, np)

        sway = (
            0.13 * np.sin(theta + v * 3.8 + variant * 2.1)
            + 0.055 * np.sin(2.0 * theta - v * 6.4 + variant * 0.9)
        ) * (v ** 1.15)
        wx = (n1 - 0.5) * 0.60 + (n2 - 0.5) * 0.28
        wy = (n2 - 0.5) * 0.34 + (n3 - 0.5) * 0.14
        warp = 0.20 + 0.90 * (v ** 0.85)
        uw = u - sway + wx * warp
        vw = np.clip(v + wy * (0.12 + 0.42 * v), 0.0, 1.15)

        base_round = np.clip(v / 0.16, 0.0, 1.0) ** 0.55
        tip_fade = np.clip(1.0 - vw, 0.0, 1.0)
        half_w = (0.62 * (1.0 - 0.68 * (vw ** 0.78)) + 0.09) * (0.74 + 0.26 * base_round)
        r = np.abs(uw) / np.maximum(0.06, half_w)
        radial = np.clip(1.0 - r ** 1.80, 0.0, 1.0)
        turb = 0.52 * n1 + 0.32 * n2 + 0.16 * n3

        field = (
            radial * (tip_fade ** 1.02) * base_round * (0.64 + 0.66 * turb)
            + (turb - 0.50) * (0.56 * v * np.clip(1.0 - r * 0.70, 0.0, 1.0))
        )
        d_belly = np.hypot(uw / 0.46, (v - 0.15) / 0.18)
        belly = np.clip(1.0 - d_belly, 0.0, 1.0) ** 1.6 * 0.42
        field = np.maximum(field, field * 0.76 + belly)

        edge_x = np.clip((0.95 - np.abs(u)) / 0.17, 0.0, 1.0)
        edge_y = np.clip(v / 0.05, 0.0, 1.0) * np.clip((0.97 - v) / 0.11, 0.0, 1.0)
        edge = edge_x * edge_y
        heat = np.clip(field * edge * 1.48, 0.0, 1.12)

        h = np.clip(heat, 0.0, 1.0)
        body = pygame.Surface((W, H), pygame.SRCALPHA)
        p3 = sa.pixels3d(body)
        p3[..., 0] = np.clip(np.interp(h, _FIRE_STOPS, _FIRE_R), 0, 255).astype(np.uint8)
        p3[..., 1] = np.clip(np.interp(h, _FIRE_STOPS, _FIRE_G), 0, 255).astype(np.uint8)
        p3[..., 2] = np.clip(np.interp(h, _FIRE_STOPS, _FIRE_B), 0, 255).astype(np.uint8)
        del p3
        pa = sa.pixels_alpha(body)
        pa[...] = np.clip((np.clip((heat - 0.06) / 0.22, 0.0, 1.0) ** 0.85) * 234.0 * edge, 0, 238).astype(np.uint8)
        del pa

        bloom_h = _smooth_2d(h, passes=3)
        core = np.clip((heat - 0.30) / 0.70, 0.0, 1.0) ** 1.35
        add = pygame.Surface((W, H))
        pa3 = sa.pixels3d(add)
        pa3[..., 0] = np.clip((bloom_h * 155.0 + core * 235.0) * edge, 0, 255).astype(np.uint8)
        pa3[..., 1] = np.clip((bloom_h * 46.0 + core * 195.0) * edge, 0, 255).astype(np.uint8)
        pa3[..., 2] = np.clip((bloom_h * 8.0 + core * 125.0) * edge, 0, 255).astype(np.uint8)
        del pa3
        return body, add
    except ImportError:
        body = pygame.Surface((W, H), pygame.SRCALPHA)
        add = pygame.Surface((W, H))
        add.fill((0, 0, 0))
        cx = W // 2
        for i in range(6):
            frac = i / 6.0
            ox = int(math.sin(theta + i * 1.4 + variant) * 6 * frac)
            rw = max(4, int(W * 0.36 * (1.0 - frac * 0.65)))
            rh = max(6, int(H * 0.34 * (1.0 - frac * 0.35)))
            cy = int(H * (0.78 - frac * 0.56))
            col = (240, int(64 + 160 * (1.0 - frac)), int(14 + 90 * (1.0 - frac)))
            pygame.draw.ellipse(body, (*col, int(190 * (1.0 - frac * 0.7))), (cx + ox - rw, cy - rh, rw * 2, rh * 2))
            pygame.draw.ellipse(add, (int(col[0] * 0.6), int(col[1] * 0.5), int(col[2] * 0.3)),
                                (cx + ox - rw // 2, cy - rh // 2, rw, rh))
        return body, add


def _base_flame(variant, frame_idx):
    key = (variant % _N_VARIANTS, frame_idx % _N_FRAMES)
    hit = _lru_get(_BASE_FLAMES, key)
    if hit is None:
        hit = _lru_put(_BASE_FLAMES, key, _build_flame_base(*key), _N_VARIANTS * _N_FRAMES + 4)
    return hit


def _qsize(px, hi=320):
    px = max(4, min(hi, int(round(px))))
    if px > 64:
        return (px + 4) // 8 * 8
    if px > 24:
        return (px + 2) // 4 * 4
    return max(4, px // 2 * 2)


def _scaled_flame(variant, frame_idx, w, h, heat, flip_x):
    w = _qsize(w, 300)
    h = _qsize(h, 380)
    hq = max(2, min(14, int(round(_clamp(heat, 0.15, 1.35) * 10.0))))
    key = (variant % _N_VARIANTS, frame_idx % _N_FRAMES, w, h, hq, bool(flip_x))
    hit = _lru_get(_SCALED_FLAMES, key)
    if hit is not None:
        return hit
    body0, add0 = _base_flame(variant, frame_idx)
    if flip_x:
        body0 = pygame.transform.flip(body0, True, False)
        add0 = pygame.transform.flip(add0, True, False)
    body = pygame.transform.smoothscale(body0, (w, h))
    add = pygame.transform.smoothscale(add0, (w, h))
    hk = hq / 10.0
    if hk < 0.99:
        try:
            import numpy as np
            pa = pygame.surfarray.pixels_alpha(body)
            pa[...] = np.clip(pa.astype(np.float32) * hk, 0, 255).astype(np.uint8)
            del pa
            p3 = pygame.surfarray.pixels3d(add)
            p3[...] = np.clip(p3.astype(np.float32) * hk, 0, 255).astype(np.uint8)
            del p3
        except ImportError:
            body.set_alpha(int(255 * hk))
    elif hk > 1.05:
        try:
            import numpy as np
            p3 = pygame.surfarray.pixels3d(add)
            p3[...] = np.clip(p3.astype(np.float32) * min(1.4, hk), 0, 255).astype(np.uint8)
            del p3
        except ImportError:
            pass
    return _lru_put(_SCALED_FLAMES, key, (body, add), 512)


# ── smoke puff surfaces (soft turbulent clouds with warm underglow) ────────

def _build_smoke_base(warmth, variant, shade_col=(36, 36, 40)):
    """Soft billowing cloud puff; ``warmth`` 0..4 adds warm fire underglow."""
    S = _SMOKE_SZ
    try:
        import numpy as np
        import pygame.surfarray as sa
        tile = _noise_tile(7, 128, 701 + variant * 53)
        tile2 = _noise_tile(14, 128, 1901 + variant * 71)
        x = np.linspace(-1.0, 1.0, S, dtype=np.float32)[:, None]
        y = np.linspace(-1.0, 1.0, S, dtype=np.float32)[None, :]
        # Shift/shape into clustered cloud lobes
        n1 = _sample_tile(tile, x * 0.45 + 0.17 * variant, y * 0.45 + 0.23 * variant, np)
        n2 = _sample_tile(tile2, x * 0.95 + 0.31, y * 0.95 + 0.11 * variant, np)
        r = np.hypot(x * 1.05, y * 1.05) + (n1 - 0.5) * 0.42 + (n2 - 0.5) * 0.18
        density = np.clip(1.0 - r, 0.0, 1.0) ** 1.45
        edge = np.clip((0.96 - np.maximum(np.abs(x), np.abs(y))) / 0.18, 0.0, 1.0)
        density *= edge
        # Directional soot shading (cooler top, darker dense core)
        top_light = np.clip(0.5 - y * 0.35 + (n2 - 0.5) * 0.25, 0.0, 1.0)
        cr = shade_col[0] * (0.72 + 0.52 * top_light)
        cg = shade_col[1] * (0.72 + 0.52 * top_light)
        cb = shade_col[2] * (0.75 + 0.55 * top_light)
        # Warm fire bounce lighting the underside of young smoke puffs
        w_k = _clamp(warmth / 4.0)
        if w_k > 0.01:
            # y > 0 is the bottom of the puff (facing the fire below)
            under = (np.clip((y + 0.42) / 1.35, 0.0, 1.0) ** 1.15) * w_k * (0.65 + 0.35 * n2)
            under = np.clip(under * 0.72, 0.0, 0.85)
            cr = cr * (1.0 - under) + 236.0 * under
            cg = cg * (1.0 - under) + 96.0 * under
            cb = cb * (1.0 - under) + 28.0 * under
        surf = pygame.Surface((S, S), pygame.SRCALPHA)
        p3 = sa.pixels3d(surf)
        p3[..., 0] = np.clip(cr, 0, 255).astype(np.uint8)
        p3[..., 1] = np.clip(cg, 0, 255).astype(np.uint8)
        p3[..., 2] = np.clip(cb, 0, 255).astype(np.uint8)
        del p3
        pa = sa.pixels_alpha(surf)
        pa[...] = np.clip(density * 225.0, 0, 225).astype(np.uint8)
        del pa
        return surf
    except ImportError:
        surf = pygame.Surface((S, S), pygame.SRCALPHA)
        for i in range(6, 0, -1):
            f = i / 6.0
            a = int(38 * (1.0 - f * 0.5))
            c = shade_col
            if warmth > 0 and i <= 4:
                wk = (warmth / 4.0) * 0.45
                c = (int(c[0] * (1 - wk) + 220 * wk), int(c[1] * (1 - wk) + 92 * wk), int(c[2] * (1 - wk) + 24 * wk))
            pygame.draw.circle(surf, (*c, a), (S // 2, S // 2), int(S * 0.44 * f))
        return surf


def smoke_puff_surface(warmth, variant, rad, alpha, shade_col=(36, 36, 40)):
    """Cached soft turbulent smoke puff scaled to ``(rad*2, rad*2)`` at ``alpha``."""
    warmth = max(0, min(4, int(warmth)))
    variant = int(variant) % 6
    rad = max(3, min(140, int(rad)))
    alpha = max(8, min(255, int(alpha) // 8 * 8))
    bkey = (warmth, variant, tuple(shade_col))
    base = _lru_get(_SMOKE_BASE, bkey)
    if base is None:
        base = _lru_put(_SMOKE_BASE, bkey, _build_smoke_base(warmth, variant, shade_col), 64)
    skey = (bkey, rad, alpha)
    hit = _lru_get(_SMOKE_SCALED, skey)
    if hit is not None:
        return hit
    img = pygame.transform.smoothscale(base, (rad * 2, rad * 2))
    if alpha < 250:
        try:
            import numpy as np
            pa = pygame.surfarray.pixels_alpha(img)
            pa[...] = np.clip(pa.astype(np.float32) * (alpha / 255.0), 0, 255).astype(np.uint8)
            del pa
        except ImportError:
            img.set_alpha(alpha)
    return _lru_put(_SMOKE_SCALED, skey, img, 768)


# ── feathered ember bed / fuel pool ───────────────────────────────────────

def _build_bed_base(variant, pulse_q):
    """(scorch_srcalpha, coals_rgb) at ``_BED_SZ x _BED_SZ``."""
    S = _BED_SZ
    pulse = 0.65 + 0.35 * (pulse_q / 6.0)
    try:
        import numpy as np
        import pygame.surfarray as sa
        tile = _noise_tile(8, 96, 3001 + variant * 67)
        tile2 = _noise_tile(15, 96, 4201 + variant * 89)
        x = np.linspace(-1.0, 1.0, S, dtype=np.float32)[:, None]
        y = np.linspace(-1.0, 1.0, S, dtype=np.float32)[None, :]
        n1 = _sample_tile(tile, x * 0.6 + 0.17 * variant, y * 0.6 + 0.29 * variant, np)
        n2 = _sample_tile(tile2, x * 1.2 + 0.41, y * 1.2 + 0.13, np)
        r = np.hypot(x, y) + (n1 - 0.5) * 0.28 + (n2 - 0.5) * 0.12
        edge = np.clip((0.96 - np.maximum(np.abs(x), np.abs(y))) / 0.14, 0.0, 1.0)

        scorch_d = np.clip(1.0 - r / 0.94, 0.0, 1.0) ** 1.35 * edge
        scorch = pygame.Surface((S, S), pygame.SRCALPHA)
        p3 = sa.pixels3d(scorch)
        p3[..., 0] = 18
        p3[..., 1] = 14
        p3[..., 2] = 13
        del p3
        pa = sa.pixels_alpha(scorch)
        pa[...] = np.clip(scorch_d * 188.0, 0, 188).astype(np.uint8)
        del pa

        # Glowing cracks + central ember core
        cracks = np.clip(1.0 - np.abs(n2 - 0.5) / 0.12, 0.0, 1.0) ** 1.7
        glow_d = np.clip(1.0 - r / 0.76, 0.0, 1.0) ** 1.5 * edge
        heat = np.clip((0.36 * glow_d + 0.85 * glow_d * cracks) * pulse, 0.0, 1.15)
        coals = pygame.Surface((S, S))
        c3 = sa.pixels3d(coals)
        c3[..., 0] = np.clip(heat * 255.0, 0, 255).astype(np.uint8)
        c3[..., 1] = np.clip((heat ** 1.55) * 165.0, 0, 255).astype(np.uint8)
        c3[..., 2] = np.clip((heat ** 2.4) * 58.0, 0, 255).astype(np.uint8)
        del c3
        return scorch, coals
    except ImportError:
        scorch = pygame.Surface((S, S), pygame.SRCALPHA)
        coals = pygame.Surface((S, S))
        coals.fill((0, 0, 0))
        c = S // 2
        pygame.draw.circle(scorch, (18, 14, 13, 140), (c, c), int(S * 0.44))
        pygame.draw.circle(coals, (int(200 * pulse), int(68 * pulse), 12), (c, c), int(S * 0.28))
        return scorch, coals


def _scaled_bed(variant, pulse_q, w, h, heat):
    w = _qsize(w, 280)
    h = _qsize(h, 240)
    hq = max(2, min(12, int(round(_clamp(heat, 0.15, 1.2) * 10.0))))
    key = (variant % 6, pulse_q % 7, w, h, hq)
    hit = _lru_get(_BED_SCALED, key)
    if hit is not None:
        return hit
    bkey = (variant % 6, pulse_q % 7)
    base = _lru_get(_BED_BASE, bkey)
    if base is None:
        base = _lru_put(_BED_BASE, bkey, _build_bed_base(*bkey), 48)
    scorch = pygame.transform.smoothscale(base[0], (w, h))
    coals = pygame.transform.smoothscale(base[1], (w, h))
    hk = hq / 10.0
    if hk < 0.99:
        try:
            import numpy as np
            pa = pygame.surfarray.pixels_alpha(scorch)
            pa[...] = np.clip(pa.astype(np.float32) * min(1.0, hk * 1.15), 0, 255).astype(np.uint8)
            del pa
            p3 = pygame.surfarray.pixels3d(coals)
            p3[...] = np.clip(p3.astype(np.float32) * hk, 0, 255).astype(np.uint8)
            del p3
        except ImportError:
            scorch.set_alpha(int(255 * hk))
    return _lru_put(_BED_SCALED, key, (scorch, coals), 384)


# ── smooth radiant halo (no Bayer contour rings) ──────────────────────────

def _soft_halo(col, rad):
    rad = _qsize(rad, 220)
    cq = tuple(max(0, min(255, int(round(c / 10.0) * 10))) for c in col)
    key = (cq, rad)
    hit = _lru_get(_HALO_CACHE, key)
    if hit is not None:
        return hit
    d = rad * 2 + 2
    try:
        import numpy as np
        import pygame.surfarray as sa
        ax = np.linspace(-1.0, 1.0, d, dtype=np.float32)
        rr = np.hypot(ax[:, None], ax[None, :])
        f = np.clip(1.0 - rr, 0.0, 1.0)
        k = (f ** 2.3) * 0.85 + (f ** 4.5) * 0.35
        s = pygame.Surface((d, d))
        p3 = sa.pixels3d(s)
        for ch in range(3):
            p3[..., ch] = np.clip(k * cq[ch], 0, 255).astype(np.uint8)
        del p3
    except ImportError:
        s = pygame.Surface((d, d))
        s.fill((0, 0, 0))
        steps = max(10, rad // 2)
        for i in range(steps, 0, -1):
            f = i / float(steps)
            k = (1.0 - f) ** 2.2
            pygame.draw.circle(s, (int(cq[0] * k), int(cq[1] * k), int(cq[2] * k)),
                               (rad + 1, rad + 1), max(1, int(rad * f)))
    return _lru_put(_HALO_CACHE, key, s, 256)


# ── depth-aware composite helpers ─────────────────────────────────────────

def _blit_masked_pair(s, body, add, dx, dy, sx, sy, scale, z, occ_depth, limit,
                      cam_fwd_y, cam_up_y, base_off_m, occ_bias, vertical=True):
    """Blit ``body`` (SRCALPHA or None) + ``add`` (RGB_ADD or None) with row-wise depth masking."""
    W, H = s.get_size()
    ref = body if body is not None else add
    bw, bh = ref.get_size()
    x0, y0 = max(0, dx), max(0, dy)
    x1, y1 = min(W, dx + bw), min(H, dy + bh)
    if x1 <= x0 or y1 <= y0:
        return
    if occ_depth is None:
        if body is not None:
            s.blit(body, (dx, dy))
        if add is not None:
            s.blit(add, (dx, dy), special_flags=pygame.BLEND_RGB_ADD)
        return
    import numpy as np
    if occ_depth.dtype == np.uint8:
        if vertical:
            proj_up = max(0.30, abs(cam_up_y))
            sy_base = sy + base_off_m * scale * proj_up
            rows = np.arange(y0, y1, dtype=np.float32)
            dh = np.maximum(0.0, (sy_base - rows) / max(1.0, scale * proj_up))
            z_row = np.maximum(0.25, z + (dh - base_off_m) * cam_fwd_y)
            lim_row = np.clip(np.round((z_row - occ_bias) * (255.0 / 64.0)), 0, 254).astype(np.uint8)
            occ = occ_depth[y0:y1, x0:x1] < lim_row[:, None]
        else:
            occ = occ_depth[y0:y1, x0:x1] < limit
    else:
        occ = occ_depth[y0:y1, x0:x1] < limit

    if not occ.any():
        if body is not None:
            s.blit(body, (dx, dy))
        if add is not None:
            s.blit(add, (dx, dy), special_flags=pygame.BLEND_RGB_ADD)
        return
    if occ.all():
        return

    cw, ch = x1 - x0, y1 - y0
    src_rect = pygame.Rect(x0 - dx, y0 - dy, cw, ch)
    occ_t = occ.T
    if body is not None:
        tmp_a = _scratch("rgba", cw, ch)
        tmp_a.fill((0, 0, 0, 0))
        tmp_a.blit(body, (0, 0), src_rect)
        pa = pygame.surfarray.pixels_alpha(tmp_a)
        pa[occ_t] = 0
        del pa
        s.blit(tmp_a, (x0, y0))
    if add is not None:
        tmp_rgb = _scratch("rgb", cw, ch)
        tmp_rgb.blit(add, (0, 0), src_rect)
        p3 = pygame.surfarray.pixels3d(tmp_rgb)
        p3[occ_t] = 0
        del p3
        s.blit(tmp_rgb, (x0, y0), special_flags=pygame.BLEND_RGB_ADD)


# ── public sprite factories & emitters ─────────────────────────────────────

def emit_flame_sprite(t_ms, seed=0, width_m=1.0, height_m=2.0, heat=1.0, drift=0.0,
                      cam_fwd_y=0.0, cam_up_y=1.0, base_off_m=0.0, flip_x=False,
                      is_25d=False):
    """Build a depth-aware turbulent flame sprite callback."""
    variant = abs(int(seed)) % _N_VARIANTS
    rate = 0.88 + 0.08 * (abs(int(seed * 7)) % 4)
    phase_f = ((t_ms * rate) / _FRAME_MS + (seed * 7.13) % _N_FRAMES) % _N_FRAMES
    frame_idx = int(phase_f) % _N_FRAMES
    # Smooth multi-sine flicker
    flick = 0.88 + 0.08 * math.sin(t_ms * 0.011 + seed * 1.9) + 0.04 * math.sin(t_ms * 0.027 + seed * 3.1)
    eff_heat = max(0.15, min(1.35, heat * flick))
    proj_up = max(0.58 if is_25d else 0.36, abs(cam_up_y))

    def _render(s, sx, sy, scale, z, occ_depth=None, limit=0.0):
        w = int(round(width_m * scale))
        h = int(round(height_m * scale * proj_up))
        if w < 4 or h < 5:
            return
        body, add = _scaled_flame(variant, frame_idx, w, h, eff_heat, flip_x)
        bw, bh = body.get_size()
        dx = int(round(sx - bw * 0.5 + drift * scale * 0.15))
        # Align bottom of flame slightly below base anchor to seat on ground/fuel
        base_px = sy + base_off_m * scale * max(0.30, abs(cam_up_y))
        dy = int(round(base_px - bh * 0.92))
        _blit_masked_pair(s, body, add, dx, dy, sx, sy, scale, z, occ_depth, limit,
                          cam_fwd_y, cam_up_y, base_off_m, 0.28, vertical=True)

    def draw(s, sx, sy, scale, z):
        _render(s, sx, sy, scale, z)

    def draw_depth(s, sx, sy, scale, z, occ_depth, limit):
        _render(s, sx, sy, scale, z, occ_depth, limit)

    draw.phys_occ = True
    draw.strict_occ = True
    draw.occ_bias = 0.28
    draw.bounds_m = (width_m * 0.72, height_m * 0.85)
    draw.bounds_cap_px = (300, 380)
    draw.draw_depth = draw_depth
    return draw


def ember_bed_sprite(rad_m, seed=0, t_ms=0.0, heat=1.0, squash=0.62):
    """Soft feathered ground scorch + pulsing molten ember cracks."""
    variant = abs(int(seed)) % 6
    pulse = 0.5 + 0.5 * math.sin(t_ms * 0.0055 + seed * 1.7)
    pulse_q = int(round(pulse * 6.0))
    eff_heat = max(0.15, min(1.2, heat))

    def draw(s, sx, sy, scale, z):
        w = int(round(rad_m * 2.0 * scale))
        h = max(4, int(round(w * squash)))
        if w < 5 or h < 4:
            return
        scorch, coals = _scaled_bed(variant, pulse_q, w, h, eff_heat)
        bw, bh = scorch.get_size()
        dx, dy = int(round(sx - bw * 0.5)), int(round(sy - bh * 0.5))
        s.blit(scorch, (dx, dy))
        s.blit(coals, (dx, dy), special_flags=pygame.BLEND_RGB_ADD)

    def _gl_surf(sx, sy, scale, z):
        w = int(round(rad_m * 2.0 * scale))
        h = max(4, int(round(w * squash)))
        if w < 5 or h < 4:
            return ()
        scorch, coals = _scaled_bed(variant, pulse_q, w, h, eff_heat)
        bw, bh = scorch.get_size()
        dx, dy = int(round(sx - bw * 0.5)), int(round(sy - bh * 0.5))
        return (("bed_s", variant, pulse_q, w, h, eff_heat), scorch, dx, dy, bw, bh, False), \
               (("bed_c", variant, pulse_q, w, h, eff_heat), coals, dx, dy, bw, bh, True)

    draw._gl_surf = _gl_surf
    draw.strict_occ = True
    draw.bounds_m = (rad_m * 1.05, rad_m * squash * 1.05)
    draw.bounds_cap_px = (280, 240)
    return draw


def emit_smoke(t_ms, seed=0, size_m=2.0, heat=1.0, compact=False,
               cam_fwd_y=0.0, cam_up_y=1.0, shade_col=(36, 36, 40)):
    """Buoyant soft turbulent smoke column with warm fire underglow on lower puffs."""
    size_m = max(0.0, float(size_m))
    seed_ph = seed * 1.731
    rise_k = 2.6 if compact else 4.4
    n_puffs = 5 if compact else 7
    proj_up = max(0.55 if compact else 0.38, abs(cam_up_y))

    def _render(s, sx, sy, scale, z, occ_depth=None, limit=0.0):
        if size_m <= 0.0 or scale < 0.4:
            return
        unit = min(40.0, size_m * scale)
        if unit < 0.8:
            return
        sw, sh = s.get_size()
        if sx + unit * 2.2 < 0 or sx - unit * 1.4 > sw or sy + unit * 1.2 < 0 or sy - unit * (rise_k + 1.8) > sh:
            return
        puffs = []
        for i in range(n_puffs):
            age = (t_ms * (0.00022 if compact else 0.00016) + i / float(n_puffs) + seed * 0.137) % 1.0
            puffs.append((age, i))
        for age, i in sorted(puffs, reverse=True):
            fade_in = min(1.0, age / 0.14)
            fade_out = (1.0 - age) ** 1.35
            peak_a = 128.0 if compact else 156.0
            opacity = int(peak_a * min(1.2, max(0.25, heat)) * fade_in * fade_out)
            if opacity < 8:
                continue
            radius = max(4, min(72, ((int(unit * (0.34 + age * (0.85 if compact else 1.18))) + 2) // 4) * 4))
            opacity = max(8, (opacity // 8) * 8)
            warmth = max(0, min(4, int((1.0 - age * 2.3) * 4.5 * min(1.0, heat))))
            drift = (
                age * age * (0.65 if compact else 1.05)
                + math.sin(age * 6.0 + seed_ph) * age * 0.36
                + math.sin(age * 11.0 + i * 2.1) * age * 0.14
            )
            ox = sx + unit * drift
            oy = sy - unit * (age * rise_k + age * age * 0.35) * proj_up
            if ox + radius < 0 or ox - radius > sw or oy + radius < 0 or oy - radius > sh:
                continue
            img = smoke_puff_surface(warmth, (int(seed) + i) % 6, radius, opacity, shade_col)
            dx, dy = int(ox - radius), int(oy - radius)
            if occ_depth is not None:
                _blit_masked_pair(s, img, None, dx, dy, ox, oy, scale, z, occ_depth, limit,
                                  cam_fwd_y, cam_up_y, 0.0, 0.25, vertical=False)
            else:
                s.blit(img, (dx, dy))

    def draw(s, sx, sy, scale, z):
        _render(s, sx, sy, scale, z)

    def draw_depth(s, sx, sy, scale, z, occ_depth, limit):
        _render(s, sx, sy, scale, z, occ_depth, limit)

    draw.phys_occ = True
    draw.strict_occ = True
    draw.occ_bias = 0.25
    draw.bounds_m = (size_m * 1.9, size_m * (rise_k + 1.4))
    draw.bounds_cap_px = (120, 220)
    draw.draw_depth = draw_depth
    return draw


def embers_sprite(t_ms, seed=0, spread_m=0.7, height_m=2.4, n=10, heat=1.0,
                  cam_fwd_y=0.0, cam_up_y=1.0):
    """Continuous buoyant glowing embers spiralling up out of a fire."""
    n = max(2, int(n))
    proj_up = max(0.45, abs(cam_up_y))

    def _render(s, sx, sy, scale, z, occ_depth=None, limit=0.0):
        if scale < 0.8 or heat <= 0.05:
            return
        sh, sw = s.get_height(), s.get_width()
        has_occ = occ_depth is not None
        if has_occ:
            oh, ow = occ_depth.shape
            import numpy as np
            is_u8 = (occ_depth.dtype == np.uint8)
        for i in range(n):
            h1 = ((i * 7919 + seed * 104729) % 1000) / 1000.0
            h2 = ((i * 6007 + seed * 13 + 311) % 997) / 997.0
            cycle_ms = 1150.0 + 750.0 * h2
            age = ((t_ms + h1 * cycle_ms) % cycle_ms) / cycle_ms
            fade = (1.0 - age) ** 1.1 * min(1.0, age / 0.10) * min(1.0, heat)
            if fade <= 0.08:
                continue
            swirl = math.sin(age * 7.5 + h1 * math.tau + seed) * (0.25 + 0.75 * age)
            ox = ((h1 - 0.5) * 0.9 + swirl * 0.55) * spread_m * scale
            rise_m = (0.15 + age * height_m)
            oy = -rise_m * scale * proj_up
            px, py = int(sx + ox), int(sy + oy)
            if px < 1 or px >= sw - 1 or py < 1 or py >= sh - 1:
                continue
            if has_occ:
                if px < 0 or px >= ow or py < 0 or py >= oh:
                    continue
                if is_u8:
                    z_p = max(0.25, z + rise_m * cam_fwd_y)
                    lim = int(max(0, min(254, round((z_p - 0.22) * (255.0 / 64.0)))))
                    if occ_depth[py, px] < lim:
                        continue
                elif occ_depth[py, px] < limit:
                    continue
            col = (
                int(min(255, (185 + 70 * fade) * min(1.0, heat))),
                int(min(255, (38 + 188 * fade * fade))),
                int(min(255, 16 + 115 * (fade ** 3))),
            )
            sz = 2 if (fade > 0.55 and scale > 8.0) else 1
            s.fill(col, (px, py, sz, sz))
            if fade > 0.45 and scale > 6.0:
                ty = min(sh - 1, py + max(1, int(0.05 * scale)))
                s.fill((col[0] // 2, col[1] // 2, col[2] // 2), (px, ty, 1, 1))

    def draw(s, sx, sy, scale, z):
        _render(s, sx, sy, scale, z)

    def draw_depth(s, sx, sy, scale, z, occ_depth, limit):
        _render(s, sx, sy, scale, z, occ_depth, limit)

    draw.phys_occ = True
    draw.strict_occ = True
    draw.occ_bias = 0.22
    draw.bounds_m = (spread_m * 1.4 + 0.2, height_m * 1.15 + 0.2)
    draw.bounds_cap_px = (220, 300)
    draw.draw_depth = draw_depth
    return draw


def _halo_sprite(col, radius_m, t_ms, seed, intensity=0.45, max_px=96):
    """Smooth un-banded additive flame radiance halo."""
    flick = 0.88 + 0.08 * math.sin(t_ms * 0.013 + seed * 2.3) + 0.04 * math.sin(t_ms * 0.031 + seed)
    k = _clamp(intensity * flick, 0.0, 1.0)

    def draw(s, sx, sy, scale, z):
        if k <= 0.02 or scale < 0.4:
            return
        rad = min(max_px, max(4, int(radius_m * scale)))
        img = _soft_halo((int(col[0] * k), int(col[1] * k), int(col[2] * k)), rad)
        s.blit(img, (int(sx - img.get_width() // 2), int(sy - img.get_height() // 2)),
               special_flags=pygame.BLEND_RGB_ADD)

    draw.light = True
    draw.light_soft = True
    draw.bounds_m = (radius_m, radius_m)
    draw.bounds_cap_px = (max_px, max_px)
    return draw


# ── high-level emitters ────────────────────────────────────────────────────

def emit_fire(r, pos, t_ms, seed=0, size=1.0, heat=1.0, smoky=True, embers=True,
              bed=True, glow=True, layer=2, tilt_25d=False):
    """Emit a rich multi-layered volumetric fire at ``pos``.

    Combines:
      1. Feathered ground scorch + pulsing coal bed (when near ground and ``bed``).
      2. Under-lit turbulent smoke plume emerging from the upper flames (if ``smoky``).
      3. Multi-lobe advected fluid flames (alpha body + additive core/halo).
      4. Smooth ambient fire glow halo (if ``glow``).
      5. Rising cooling ember sparks (if ``embers``).
    """
    size = max(0.0, float(size))
    heat = max(0.0, min(1.6, float(heat)))
    if size <= 0.02 or heat <= 0.02:
        return
    x, y, z = pos
    fwd = getattr(r, "fwd", (0.0, 0.0, 1.0))
    up = getattr(r, "up", (0.0, 1.0, 0.0))
    cam_fwd_y, cam_up_y = float(fwd[1]), float(up[1])
    is_25d = bool(tilt_25d or abs(cam_fwd_y) > 0.55)

    w_m = size * (1.28 if is_25d else 1.12)
    h_m = size * (1.85 if is_25d else 2.25) * (0.78 + 0.22 * min(heat, 1.3))

    if bed and y < 0.45:
        r.add_sprite(
            (x, max(0.012, y + 0.015), z),
            ember_bed_sprite(size * (0.88 if is_25d else 0.78), seed=seed, t_ms=t_ms,
                             heat=heat, squash=0.76 if is_25d else 0.54),
            layer=1, bias=-0.15,
        )

    if smoky:
        # Start inside the upper flame body so smoke grows seamlessly from tips
        r.add_sprite(
            (x, y + h_m * (0.48 if is_25d else 0.52), z),
            emit_smoke(t_ms, seed=seed, size_m=size * (0.78 if is_25d else 1.08),
                       heat=heat, compact=is_25d, cam_fwd_y=cam_fwd_y, cam_up_y=cam_up_y),
            layer=layer, bias=-0.12,
        )

    # Secondary wider orange flank tongue (adds parallax depth & asymmetry)
    if size >= 0.35:
        r.add_sprite(
            (x, y + h_m * 0.34, z),
            emit_flame_sprite(t_ms, seed=seed + 19, width_m=w_m * 1.10, height_m=h_m * 0.78,
                              heat=heat * 0.85, drift=-0.18 if (seed % 2) else 0.18,
                              cam_fwd_y=cam_fwd_y, cam_up_y=cam_up_y, base_off_m=h_m * 0.34,
                              flip_x=(seed % 2 == 0), is_25d=is_25d),
            layer=layer, bias=0.05,
        )

    # Primary roaring flame plume
    r.add_sprite(
        (x, y + h_m * 0.40, z),
        emit_flame_sprite(t_ms, seed=seed, width_m=w_m, height_m=h_m,
                          heat=heat, drift=0.0,
                          cam_fwd_y=cam_fwd_y, cam_up_y=cam_up_y, base_off_m=h_m * 0.40,
                          flip_x=(seed % 2 == 1), is_25d=is_25d),
        layer=layer, bias=0.14,
    )

    if glow:
        r.add_sprite(
            (x, y + h_m * 0.42, z),
            _halo_sprite((255, 118, 32), size * 2.1, t_ms, seed=seed,
                         intensity=0.46 * min(1.15, heat), max_px=96),
            layer=6,
        )

    if embers:
        cnt = 6 if is_25d else 10
        r.add_sprite(
            (x, y + size * 0.25, z),
            embers_sprite(t_ms, seed=seed + 5, spread_m=size * 0.65, height_m=h_m * 1.25,
                          n=cnt, heat=heat, cam_fwd_y=cam_fwd_y, cam_up_y=cam_up_y),
            layer=layer, bias=0.22,
        )


def emit_wall_fire(r, x, y, wall_z, t_ms, seed=0, size=1.0, heat=1.0,
                   smoky=False, embers=True, glow=True, layer=2):
    """Fire clinging to a wall facing -z with feathered scorch and rising tongues."""
    size = max(0.0, float(size))
    if size <= 0.02:
        return
    fz = wall_z - 0.04
    fwd = getattr(r, "fwd", (0.0, 0.0, 1.0))
    up = getattr(r, "up", (0.0, 1.0, 0.0))
    cam_fwd_y, cam_up_y = float(fwd[1]), float(up[1])
    w_m = size * 1.15
    h_m = size * 1.85

    if smoky:
        r.add_sprite(
            (x, y + h_m * 0.55, fz - 0.06),
            emit_smoke(t_ms, seed=seed, size_m=size * 1.0, heat=heat, compact=False,
                       cam_fwd_y=cam_fwd_y, cam_up_y=cam_up_y),
            layer=layer, bias=-0.08,
        )

    r.add_sprite(
        (x, y + h_m * 0.36, fz - 0.08),
        emit_flame_sprite(t_ms, seed=seed + 7, width_m=w_m * 1.12, height_m=h_m * 0.82,
                          heat=heat * 0.88, cam_fwd_y=cam_fwd_y, cam_up_y=cam_up_y,
                          base_off_m=h_m * 0.36, flip_x=(seed % 2 == 0)),
        layer=layer, bias=0.06,
    )
    r.add_sprite(
        (x, y + h_m * 0.40, fz - 0.12),
        emit_flame_sprite(t_ms, seed=seed, width_m=w_m, height_m=h_m,
                          heat=heat, cam_fwd_y=cam_fwd_y, cam_up_y=cam_up_y,
                          base_off_m=h_m * 0.40, flip_x=(seed % 2 == 1)),
        layer=layer, bias=0.14,
    )
    if glow:
        r.add_sprite(
            (x, y + h_m * 0.40, fz - 0.15),
            _halo_sprite((255, 112, 30), size * 1.8, t_ms, seed=seed,
                         intensity=0.38 * min(1.15, heat), max_px=80),
            layer=6,
        )
    if embers:
        r.add_sprite(
            (x, y + size * 0.3, fz - 0.10),
            embers_sprite(t_ms, seed=seed + 11, spread_m=size * 0.55, height_m=h_m * 1.2,
                          n=7, heat=heat, cam_fwd_y=cam_fwd_y, cam_up_y=cam_up_y),
            layer=layer, bias=0.20,
        )
