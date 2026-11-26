"""Procedural cached fireball, blast flash, and ground-flash 3D sprites.

Pure ``engine.render3d``: imports only stdlib, ``pygame``, and ``numpy``.
All surfaces are generated deterministically from fixed seeds and cached in
bounded LRU tables; runtime draws perform only fast blits.
"""
from __future__ import annotations

from collections import OrderedDict
import math
from typing import Tuple

import numpy as np
import pygame

__all__ = [
    "fireball_sprite",
    "flash_sprite",
    "ground_flash_sprite",
    "prewarm",
]

_N_PHASE = 12
_N_VAR = 3
_BASE = 96
_FLASH_BASE_PX = 128

_BASE_FIREBALL: dict[tuple[int, int], tuple[pygame.Surface, pygame.Surface]] = {}
_SCALED_FIREBALL: OrderedDict[tuple[int, int, int, int], tuple[pygame.Surface, pygame.Surface]] = OrderedDict()
_FLASH_BASE: pygame.Surface | None = None
_GROUND_FLASH_BASE: pygame.Surface | None = None
_SCALED_FLASH: OrderedDict[tuple[str, int, int], pygame.Surface] = OrderedDict()
_PREWARMED = False

# Temperature ramp stops: soot -> char -> crimson -> orange -> amber -> yellow -> cream
_T_STOPS = (0.00, 0.18, 0.35, 0.55, 0.75, 0.90, 1.00)
_R_STOPS = (34.0, 74.0, 150.0, 236.0, 255.0, 255.0, 255.0)
_G_STOPS = (30.0, 46.0, 52.0, 110.0, 184.0, 236.0, 252.0)
_B_STOPS = (30.0, 34.0, 18.0, 26.0, 64.0, 150.0, 228.0)


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else (hi if v > hi else v)


def _lru_get(cache: OrderedDict, key):
    hit = cache.get(key)
    if hit is not None:
        cache.move_to_end(key)
    return hit


def _lru_put(cache: OrderedDict, key, val, cap: int):
    if key in cache:
        cache.move_to_end(key)
    elif len(cache) >= cap:
        cache.popitem(last=False)
    cache[key] = val
    return val


def _upsample_bilinear(grid: np.ndarray, n: int) -> np.ndarray:
    g = grid.shape[0]
    coords = np.linspace(0.0, float(g - 1) - 1e-6, n, dtype=np.float32)
    i0 = np.floor(coords).astype(np.int32)
    i1 = np.minimum(i0 + 1, g - 1)
    f = coords - i0
    top = grid[i0[:, None], i0[None, :]] * (1.0 - f[None, :]) + grid[i0[:, None], i1[None, :]] * f[None, :]
    bot = grid[i1[:, None], i0[None, :]] * (1.0 - f[None, :]) + grid[i1[:, None], i1[None, :]] * f[None, :]
    return top * (1.0 - f[:, None]) + bot * f[:, None]


def _fbm(n: int, seed: int) -> np.ndarray:
    """Deterministic 3-octave value noise normalised to [0, 1] on an n x n grid."""
    rng = np.random.default_rng(int(seed))
    acc = np.zeros((n, n), dtype=np.float32)
    for g, w in ((4, 0.55), (8, 0.30), (16, 0.15)):
        grid = rng.random((g, g), dtype=np.float32)
        acc += _upsample_bilinear(grid, n) * w
    lo = float(acc.min())
    hi = float(acc.max())
    span = hi - lo
    if span < 1e-6:
        return np.zeros((n, n), dtype=np.float32)
    return (acc - lo) / span


def _build_fireball(variant: int, phase: int) -> tuple[pygame.Surface, pygame.Surface]:
    """Generate the opaque-smoke/fire body and additive emissive glow for one phase."""
    u = phase / float(_N_PHASE - 1)
    lin = np.linspace(-1.0, 1.0, _BASE, dtype=np.float32)
    # ij indexing aligns axis 0 = x (width) and axis 1 = y (height) for pygame.surfarray
    xx, yy = np.meshgrid(lin, lin, indexing="ij")
    r = np.hypot(xx, yy)

    fbm1 = _fbm(_BASE, 1009 + variant * 131)
    fbm2 = _fbm(_BASE, 2017 + variant * 197 + phase * 7)

    edge = 0.74 + 0.46 * (fbm1 - 0.5)
    d = np.clip((edge - r) / 0.25, 0.0, 1.0)
    T = np.clip(
        (1.0 - (r / np.maximum(edge, 1e-4)) ** 1.25) * 1.30 + (fbm2 - 0.5) * 0.65 - u * 1.32 + 0.18,
        0.0,
        1.0,
    )

    rr = np.interp(T, _T_STOPS, _R_STOPS)
    gg = np.interp(T, _T_STOPS, _G_STOPS)
    bb = np.interp(T, _T_STOPS, _B_STOPS)
    rgb = np.stack((rr, gg, bb), axis=-1)

    top_shade = np.clip(0.80 + 0.28 * (-yy) * (1.0 - T), 0.55, 1.15)
    body_rgb = np.clip(rgb * top_shade[..., None], 0.0, 255.0).astype(np.uint8)
    alpha = np.clip(d * (0.95 - 0.12 * u) * 255.0, 0.0, 255.0).astype(np.uint8)

    body = pygame.Surface((_BASE, _BASE), pygame.SRCALPHA)
    pygame.surfarray.pixels3d(body)[:] = body_rgb
    pygame.surfarray.pixels_alpha(body)[:] = alpha

    em_k = (np.clip((T - 0.45) / 0.55, 0.0, 1.0) ** 1.5) * 0.55 * d
    add_rgb = np.clip(rgb * em_k[..., None], 0.0, 255.0).astype(np.uint8)
    add = pygame.Surface((_BASE, _BASE))
    pygame.surfarray.blit_array(add, add_rgb)

    return body, add


def _get_base_fireball(variant: int, phase: int) -> tuple[pygame.Surface, pygame.Surface]:
    key = (variant, phase)
    hit = _BASE_FIREBALL.get(key)
    if hit is None:
        hit = _build_fireball(variant, phase)
        _BASE_FIREBALL[key] = hit
    return hit


def _get_scaled_fireball(variant: int, phase: int, px: int, alpha_q: int) -> tuple[pygame.Surface, pygame.Surface]:
    px_q = max(4, min(384, ((px + 2) // 4) * 4))
    key = (variant, phase, px_q, alpha_q)
    hit = _lru_get(_SCALED_FIREBALL, key)
    if hit is not None:
        return hit
    base_body, base_add = _get_base_fireball(variant, phase)
    body_s = pygame.transform.smoothscale(base_body, (px_q, px_q))
    add_s = pygame.transform.smoothscale(base_add, (px_q, px_q))
    if alpha_q < 8:
        a = int(round(alpha_q * 255.0 / 8.0))
        body_s.fill((255, 255, 255, a), special_flags=pygame.BLEND_RGBA_MULT)
        add_s.fill((a, a, a), special_flags=pygame.BLEND_RGB_MULT)
    return _lru_put(_SCALED_FIREBALL, key, (body_s, add_s), 160)


def _build_radial_glow(inner: Tuple[int, int, int], outer: Tuple[int, int, int]) -> pygame.Surface:
    lin = np.linspace(-1.0, 1.0, _FLASH_BASE_PX, dtype=np.float32)
    xx, yy = np.meshgrid(lin, lin, indexing="ij")
    r2 = xx * xx + yy * yy
    r = np.sqrt(r2)
    edge = np.clip((1.0 - r) / 0.18, 0.0, 1.0)
    g = np.exp(-r2 * 4.2) * edge
    mix_t = g[..., None] ** 0.75
    col = (
        np.array(outer, dtype=np.float32)[None, None, :] * (1.0 - mix_t)
        + np.array(inner, dtype=np.float32)[None, None, :] * mix_t
    )
    rgb = np.clip(col * g[..., None], 0.0, 255.0).astype(np.uint8)
    surf = pygame.Surface((_FLASH_BASE_PX, _FLASH_BASE_PX))
    pygame.surfarray.blit_array(surf, rgb)
    return surf


def _ensure_flash_bases() -> tuple[pygame.Surface, pygame.Surface]:
    global _FLASH_BASE, _GROUND_FLASH_BASE
    if _FLASH_BASE is None:
        _FLASH_BASE = _build_radial_glow((255, 250, 226), (255, 170, 70))
    if _GROUND_FLASH_BASE is None:
        _GROUND_FLASH_BASE = _build_radial_glow((255, 200, 110), (255, 146, 54))
    return _FLASH_BASE, _GROUND_FLASH_BASE


def _get_scaled_flash(kind: str, w_px: int, h_px: int, kq: int) -> pygame.Surface:
    wq = max(4, min(384, ((w_px + 2) // 4) * 4))
    hq = max(4, min(384, ((h_px + 2) // 4) * 4))
    key = (kind, wq, hq, kq)
    hit = _lru_get(_SCALED_FLASH, key)
    if hit is not None:
        return hit
    flash_b, ground_b = _ensure_flash_bases()
    base = flash_b if kind == "flash" else ground_b
    s = pygame.transform.smoothscale(base, (wq, hq))
    if kq < 8:
        a = int(round(kq * 255.0 / 8.0))
        s.fill((a, a, a), special_flags=pygame.BLEND_RGB_MULT)
    return _lru_put(_SCALED_FLASH, key, s, 96)


def prewarm() -> None:
    """Prebuild all fireball phase bases and radial flash bases once."""
    global _PREWARMED
    if _PREWARMED:
        return
    for v in range(_N_VAR):
        for p in range(_N_PHASE):
            _get_base_fireball(v, p)
    _ensure_flash_bases()
    _PREWARMED = True


def fireball_sprite(
    rad_m: float,
    phase_u: float,
    variant: int,
    alpha_k: float = 1.0,
    max_px: int = 360,
):
    """Return a 3D renderer sprite callback for one billowing fireball/smoke lobe."""
    u = _clamp(float(phase_u), 0.0, 1.0)
    phase = max(0, min(_N_PHASE - 1, int(round(u * (_N_PHASE - 1)))))
    v = int(variant) % _N_VAR
    alpha_q = max(0, min(8, int(round(_clamp(float(alpha_k), 0.0, 1.0) * 8.0))))

    def draw(surf, sx, sy, scale, z):
        if alpha_q <= 0:
            return
        diam = max(4, min(max_px, int(rad_m * 2.0 * scale)))
        body_s, add_s = _get_scaled_fireball(v, phase, diam, alpha_q)
        ox = int(sx - body_s.get_width() * 0.5)
        oy = int(sy - body_s.get_height() * 0.5)
        surf.blit(body_s, (ox, oy))
        surf.blit(add_s, (ox, oy), special_flags=pygame.BLEND_RGB_ADD)

    draw.bounds_m = (rad_m * 1.05, rad_m * 1.05)
    draw.bounds_cap_px = (max_px + 4, max_px + 4)
    draw.phys_occ = True
    draw.occ_bias = rad_m * 0.8
    return draw


def flash_sprite(rad_m: float, k: float, max_px: int = 260):
    """Return an additive radial blast-flash sprite callback with physical occlusion."""
    kq = max(0, min(8, int(round(_clamp(float(k), 0.0, 1.0) * 8.0))))

    def draw(surf, sx, sy, scale, z):
        if kq <= 0:
            return
        diam = max(4, min(max_px, int(rad_m * 2.0 * scale)))
        img = _get_scaled_flash("flash", diam, diam, kq)
        surf.blit(
            img,
            (int(sx - img.get_width() * 0.5), int(sy - img.get_height() * 0.5)),
            special_flags=pygame.BLEND_RGB_ADD,
        )

    draw.bounds_m = (rad_m * 1.05, rad_m * 1.05)
    draw.bounds_cap_px = (max_px + 4, max_px + 4)
    draw.phys_occ = True
    draw.occ_bias = rad_m
    return draw


def ground_flash_sprite(rad_m: float, k: float, max_px: int = 280):
    """Return a squashed additive ground-spill flash sprite callback."""
    kq = max(0, min(8, int(round(_clamp(float(k), 0.0, 1.0) * 8.0))))

    def draw(surf, sx, sy, scale, z):
        if kq <= 0:
            return
        w_px = max(6, min(max_px, int(rad_m * 2.0 * scale)))
        h_px = max(4, int(round(w_px * 0.38)))
        img = _get_scaled_flash("ground", w_px, h_px, kq)
        surf.blit(
            img,
            (int(sx - img.get_width() * 0.5), int(sy - img.get_height() * 0.5)),
            special_flags=pygame.BLEND_RGB_ADD,
        )

    draw.bounds_m = (rad_m * 1.05, rad_m * 0.42)
    draw.bounds_cap_px = (max_px + 4, int(max_px * 0.42) + 4)
    draw.phys_occ = True
    draw.occ_bias = max(0.8, rad_m * 0.9)
    return draw
