"""Mission 6 night atmosphere: light pools, wet puddle patches, snow layers & fast filmic tuning."""
from __future__ import annotations

import math
import os

import numpy as np
import pygame

from core.config import HEIGHT, TILE_SIZE, WIDTH
from engine.core import now_s as _now_s

T = TILE_SIZE

_POOLS: dict = {}
_BULBS: dict = {}
_SPILLS: dict = {}
_FLASHLIGHT: dict = {}
_PUDDLE_PATCHES: dict = {}
_AO_BANDS: dict = {}
_SNOW_SPRITES: dict = {}


def _reduced_motion() -> bool:
    if os.environ.get("ACA_FREEZE", "") == "1":
        return True
    try:
        from core.user_settings import SETTINGS
        return bool(getattr(SETTINGS, "reduced_motion", False))
    except Exception:
        return False


def _quality() -> int:
    try:
        from game.render3d_bridge import quality_3d
        return int(quality_3d())
    except Exception:
        return 2


def _safe_convert(surf: pygame.Surface) -> pygame.Surface:
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        return surf.convert()
    return surf


def _safe_convert_alpha(surf: pygame.Surface) -> pygame.Surface:
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        return surf.convert_alpha()
    return surf


def _filmic(k: np.ndarray) -> np.ndarray:
    """Gentle ACES-style midtone lift & highlight roll-off baked at sprite build time."""
    k = np.clip(k, 0.0, 1.0)
    return np.clip(k * (1.24 - 0.24 * k), 0.0, 1.0)


# ── Light pools, bloomed fixture bulbs & booth window spill ──────────────────

def ground_pool_sprite(rx: int, ry: int, col: tuple[int, int, int],
                       cone_bias: float = 0.0) -> pygame.Surface:
    """Smooth elliptical light pool with baked filmic curve (native pixel format)."""
    rx = max(12, int(rx))
    ry = max(12, int(ry))
    col = (int(col[0]), int(col[1]), int(col[2]))
    key = (rx, ry, col, round(cone_bias, 2))
    s = _POOLS.get(key)
    if s is not None:
        return s
    # byte budget, not a count: flickering lamps sweep ~260 radii (~50 MB) per stage,
    # and the old 192-entry cap cleared and rebuilt them every few frames
    if len(_POOLS) > 192 and sum(p.get_width() * p.get_height() for p in _POOLS.values()) * 4 > 128 << 20:
        _POOLS.clear()
    w, h = rx * 2, ry * 2
    xx, yy = np.mgrid[0:w, 0:h].astype(np.float32)  # [x, y] surfarray order
    dx = (xx - rx) / float(rx)
    dy = (yy - ry) / float(ry)
    if cone_bias != 0.0:
        scale_x = 1.0 + cone_bias * np.clip(dy, -0.5, 1.0) * 0.28
        dx = dx / np.maximum(0.65, scale_x)
    d2 = dx * dx + dy * dy
    k = np.where(
        d2 < 1.0,
        0.72 * np.exp(-d2 * 2.05) * np.power(np.maximum(0.0, 1.0 - d2), 1.35),
        0.0,
    )
    k = _filmic(k)
    rgb = np.empty((w, h, 3), dtype=np.uint8)
    for c in range(3):
        rgb[..., c] = np.clip(k * col[c], 0, 255).astype(np.uint8)
    s = _safe_convert(pygame.surfarray.make_surface(rgb))
    _POOLS[key] = s
    return s


def bulb_glow_sprite(radius: int, col: tuple[int, int, int]) -> pygame.Surface:
    """Bloomed fixture bulb sprite (soft outer optical halo + hot core, zero screen readback)."""
    r = max(12, int(radius))
    col = (int(col[0]), int(col[1]), int(col[2]))
    key = (r, col)
    s = _BULBS.get(key)
    if s is not None:
        return s
    if len(_BULBS) > 128:
        _BULBS.clear()
    w = h = r * 2
    xx, yy = np.mgrid[0:w, 0:h].astype(np.float32)
    dx = (xx - r) / float(r)
    dy = (yy - r) / float(r)
    d2 = dx * dx + dy * dy
    halo = 0.26 * np.exp(-d2 * 3.1) * np.maximum(0.0, 1.0 - d2)
    core = 0.74 * np.exp(-d2 * 28.0)
    rgb = np.empty((w, h, 3), dtype=np.uint8)
    for c in range(3):
        hot = 255.0 * 0.65 + col[c] * 0.35
        rgb[..., c] = np.clip(halo * col[c] + core * hot, 0, 255).astype(np.uint8)
    s = _safe_convert(pygame.surfarray.make_surface(rgb))
    _BULBS[key] = s
    return s


def booth_spill_sprite(w: int, h: int, col: tuple[int, int, int],
                       side: str = "east") -> pygame.Surface:
    """Soft feathered rectangular/trapezoidal window spill onto asphalt."""
    w, h = max(16, int(w)), max(16, int(h))
    col = (int(col[0]), int(col[1]), int(col[2]))
    key = (w, h, col, side)
    s = _SPILLS.get(key)
    if s is not None:
        return s
    xx, yy = np.mgrid[0:w, 0:h].astype(np.float32)
    u = xx / float(max(1, w - 1))
    v = yy / float(max(1, h - 1))
    if side == "west":
        u = 1.0 - u
    elif side == "south":
        u, v = v, u
    half_span = 0.26 + 0.24 * u
    edge = np.abs(v - 0.5) / half_span
    across = np.clip(1.0 - edge * edge, 0.0, 1.0) ** 1.7
    along = np.clip(1.0 - u, 0.0, 1.0) ** 1.35 * np.clip(u * 6.0, 0.25, 1.0)
    k = _filmic(0.68 * across * along)
    rgb = np.empty((w, h, 3), dtype=np.uint8)
    for c in range(3):
        rgb[..., c] = np.clip(k * col[c], 0, 255).astype(np.uint8)
    s = _safe_convert(pygame.surfarray.make_surface(rgb))
    _SPILLS[key] = s
    return s


def flashlight_cone_sprite(angle_rad: float, reach: int = 260,
                           col: tuple[int, int, int] = (218, 236, 248)
                           ) -> tuple[pygame.Surface, int, int]:
    """Tightly cropped, 64-angle cached directional flashlight cone (1/4-res build, instant)."""
    bucket = int(round(angle_rad / (2.0 * math.pi) * 64.0)) % 64
    key = (bucket, reach, col)
    hit = _FLASHLIGHT.get(key)
    if hit is not None:
        return hit
    qr = max(32, reach // 4)
    a = bucket * (2.0 * math.pi / 64.0)
    ca, sa = math.cos(a), math.sin(a)
    sz = qr * 2
    xx, yy = np.mgrid[0:sz, 0:sz].astype(np.float32)
    rx = xx - qr
    ry = yy - qr
    fwd = rx * ca + ry * sa
    lat = -rx * sa + ry * ca
    dist = np.hypot(rx, ry)
    cone_r = dist / float(qr)
    ang_ratio = np.abs(lat) / np.maximum(2.5, fwd * 0.46 + 2.5)
    in_cone = (fwd > -1.5) & (cone_r < 1.0) & (ang_ratio < 1.0)
    cone_i = np.where(
        in_cone,
        0.72 * np.power(np.maximum(0.0, 1.0 - cone_r), 1.3)
        * np.power(np.maximum(0.0, 1.0 - ang_ratio * ang_ratio), 1.65),
        0.0,
    )
    body_r = dist / 14.0
    body_i = np.where(body_r < 1.0, 0.36 * np.power(np.maximum(0.0, 1.0 - body_r * body_r), 1.6), 0.0)
    tot = _filmic(np.maximum(cone_i, body_i))
    nz = np.nonzero(tot > 0.01)
    x0, x1 = int(nz[0].min()), int(nz[0].max()) + 1
    y0, y1 = int(nz[1].min()), int(nz[1].max()) + 1
    crop_tot = tot[x0:x1, y0:y1]
    cw, ch = x1 - x0, y1 - y0
    rgb = np.empty((cw, ch, 3), dtype=np.uint8)
    for c in range(3):
        rgb[..., c] = np.clip(crop_tot * col[c], 0, 255).astype(np.uint8)
    small = pygame.surfarray.make_surface(rgb)
    spr = _safe_convert(pygame.transform.smoothscale(small, (cw * 4, ch * 4)))
    res = (spr, (x0 - qr) * 4, (y0 - qr) * 4)
    _FLASHLIGHT[key] = res
    return res


# ── Pre-baked wet asphalt puddle patches (zero per-frame multiply) ───────────

def _spec_streak(rx: int, ry: int, col: tuple[int, int, int]) -> pygame.Surface:
    rx, ry = max(6, int(rx)), max(10, int(ry))
    w, h = rx * 2, ry * 2
    xx, yy = np.mgrid[0:w, 0:h].astype(np.float32)
    dx = (xx - rx) / float(rx)
    dy = (yy - ry) / float(ry)
    d2 = dx * dx + dy * dy
    ripple = 0.58 + 0.42 * np.sin(yy * 0.9 + xx * 0.14)
    k = np.where(
        d2 < 1.0,
        0.52 * ripple * np.exp(-dx * dx * 3.6) * np.power(np.maximum(0.0, 1.0 - d2), 1.35),
        0.0,
    )
    rgb = np.empty((w, h, 3), dtype=np.uint8)
    for c in range(3):
        rgb[..., c] = np.clip(k * col[c], 0, 255).astype(np.uint8)
    return pygame.surfarray.make_surface(rgb)


def wet_puddle_patches(stage_id: str, grid: list[str]
                       ) -> list[tuple[pygame.Surface, int, int]]:
    """Pre-baked tight wet-asphalt reflection patches for ``stage_id``."""
    if stage_id not in ("customs", "noman", "rail"):
        return []
    hit = _PUDDLE_PATCHES.get(stage_id)
    if hit is not None:
        return hit
    if stage_id == "customs":
        puddles = [
            (15.2, 2.8, 76, 36, 225, [(15.5 * T, 2.8 * T, 38, 44, (255, 168, 68)),
                                      (13.0 * T, 2.9 * T, 14, 24, (242, 66, 54)),
                                      (18.6 * T, 2.9 * T, 14, 24, (242, 66, 54))]),
            (13.4, 6.8, 62, 36, 210, [(13.3 * T, 7.2 * T, 28, 42, (112, 238, 208))]),
            (17.2, 10.4, 62, 36, 210, [(17.4 * T, 10.5 * T, 28, 42, (112, 238, 208))]),
            (14.5, 4.5, 58, 44, 180, [(15.2 * T, 4.4 * T, 28, 40, (255, 174, 78))]),
            (10.5, 13.8, 56, 32, 215, [(10.2 * T, 14.3 * T, 26, 36, (255, 178, 76))]),
            (16.2, 16.9, 66, 34, 220, [(15.4 * T, 16.7 * T, 32, 38, (144, 196, 242))]),
            (20.6, 13.8, 54, 30, 185, [(20.2 * T, 14.3 * T, 26, 36, (255, 178, 76))]),
        ]
    elif stage_id == "noman":
        puddles = [
            (20.0, 2.2, 72, 32, 185, [(20.0 * T, 2.2 * T, 36, 40, (255, 186, 116))]),
            (13.0, 2.2, 54, 28, 165, [(13.0 * T, 2.3 * T, 28, 34, (255, 204, 140))]),
            (27.0, 2.2, 54, 28, 165, [(27.0 * T, 2.3 * T, 28, 34, (255, 204, 140))]),
            (20.0, 15.6, 72, 32, 185, [(20.0 * T, 15.6 * T, 36, 40, (255, 186, 116))]),
        ]
    else:
        puddles = [
            (12.0, 6.2, 68, 30, 180, [(12.0 * T, 6.2 * T, 34, 38, (255, 198, 132))]),
            (20.0, 6.2, 68, 30, 180, [(20.0 * T, 6.2 * T, 34, 38, (255, 198, 132))]),
            (28.0, 6.2, 68, 30, 180, [(28.0 * T, 6.2 * T, 34, 38, (255, 198, 132))]),
            (36.0, 6.2, 68, 30, 180, [(36.0 * T, 6.2 * T, 34, 38, (255, 198, 132))]),
            (25.0, 11.4, 56, 26, 165, [(25.0 * T, 11.3 * T, 28, 32, (220, 170, 110))]),
        ]
    out: list[tuple[pygame.Surface, int, int]] = []
    for cx_t, cy_t, rx, ry, val, specs in puddles:
        wx0 = int(cx_t * T - rx)
        wy0 = int(cy_t * T - ry)
        pw, ph = rx * 2, ry * 2
        patch = pygame.Surface((pw, ph))
        patch.fill((0, 0, 0))
        for sx, sy, srx, sry, col in specs:
            spr = _spec_streak(srx, sry, col)
            patch.blit(spr, (int(sx - wx0 - srx), int(sy - wy0 - sry)),
                       special_flags=pygame.BLEND_RGB_ADD)
        mask = pygame.Surface((pw, ph))
        mask.fill((0, 0, 0))
        pygame.draw.ellipse(mask, (val // 2, val // 2, val // 2), (0, 0, pw, ph))
        pygame.draw.ellipse(mask, (val, val, val),
                            (pw // 6, ph // 6, (pw * 2) // 3, (ph * 2) // 3))
        patch.blit(mask, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        out.append((_safe_convert(patch), wx0, wy0))
    _PUDDLE_PATCHES[stage_id] = out
    return out


# ── Ground Contact AO helpers ────────────────────────────────────────────────

def paint_prop_contact_ao(surf: pygame.Surface, props: list[dict]) -> None:
    """Paint soft ambient-occlusion contact gradients hugging prop bases."""
    for p in props:
        kind = p.get("kind", "")
        if kind in ("boom", "mast"):
            continue
        x0 = int(p["x"])
        bottom = int(p["bottom"])
        w = int(p["w"])
        fh = int(p["fh"])
        top = bottom - fh
        ao_w = max(8, w + 12)
        ao_h = max(8, fh + 10)
        key = ("pao", ao_w, ao_h)
        band = _AO_BANDS.get(key)
        if band is None:
            if len(_AO_BANDS) > 96:
                _AO_BANDS.clear()
            band = pygame.Surface((ao_w, ao_h), pygame.SRCALPHA)
            for pad, a in ((5, 22), (3, 36), (1, 56)):
                r = pygame.Rect(5 - pad, 5 - pad, w + pad * 2, fh + pad * 2)
                pygame.draw.rect(band, (4, 6, 12, a), r, border_radius=4)
            _AO_BANDS[key] = _safe_convert_alpha(band)
        surf.blit(band, (x0 - 5, top - 5))


# ── 3-layer soft wind-streaked snow ──────────────────────────────────────────

def _snow_sprite(layer: int, alpha: int) -> pygame.Surface:
    key = (layer, alpha // 16)
    s = _SNOW_SPRITES.get(key)
    if s is not None:
        return s
    a = max(32, min(224, (alpha // 16) * 16))
    if layer == 0:
        s = pygame.Surface((4, 4), pygame.SRCALPHA)
        pygame.draw.circle(s, (176, 194, 218, a // 2), (2, 2), 2)
        pygame.draw.circle(s, (198, 214, 232, a), (2, 2), 1)
    elif layer == 1:
        s = pygame.Surface((8, 10), pygame.SRCALPHA)
        pygame.draw.line(s, (186, 206, 228, a // 2), (1, 1), (6, 8), 3)
        pygame.draw.line(s, (220, 234, 248, a), (2, 2), (5, 7), 1)
    else:
        s = pygame.Surface((12, 14), pygame.SRCALPHA)
        pygame.draw.line(s, (192, 212, 236, a // 3), (2, 2), (9, 11), 5)
        pygame.draw.line(s, (218, 232, 246, (a * 2) // 3), (3, 3), (8, 10), 2)
    s = _safe_convert_alpha(s)
    _SNOW_SPRITES[key] = s
    return s


def draw_snow(surface: pygame.Surface, count: int) -> None:
    """3-depth-layer soft wind-streaked falling snow (native alpha blits, zero allocations)."""
    t = _now_s()
    rm = _reduced_motion()
    total = max(12, int(count * 1.35))
    for i in range(total):
        h = ((i * 73856093) ^ (29 * 19349663)) & 0xFFFFFFFF
        bucket = h % 10
        if bucket < 5:
            layer, speed, drift_x, alpha = 0, 28 + (h % 18), 16.0, 88 + (h % 36)
        elif bucket < 9:
            layer, speed, drift_x, alpha = 1, 56 + (h % 32), 34.0, 128 + (h % 56)
        else:
            layer, speed, drift_x, alpha = 2, 92 + (h % 38), 54.0, 76 + (h % 44)
        depth = 0.45 + layer * 0.35
        sway = 0.0 if rm else math.sin(t * 0.75 + i * 0.9) * 18.0 * depth
        x = ((h % (WIDTH + 120)) + t * drift_x + sway) % (WIDTH + 60) - 30
        y = (((h >> 9) % (HEIGHT + 160)) + t * speed) % (HEIGHT + 60) - 30
        if -16 < x < WIDTH + 16 and -16 < y < HEIGHT + 16:
            surface.blit(_snow_sprite(layer, alpha), (int(x), int(y)))
