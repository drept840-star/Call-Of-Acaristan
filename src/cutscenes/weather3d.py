"""Data-driven weather & atmosphere for 3D sets (RPE6 Phase 11 step 6).

Set files declare `weather` (rain), `emitter` (smoke / steam / dust)
and `fog_layer` nodes; hosts call :func:`attach` once per frame with
the shot time.  Everything is a closed-form function of (seed, t) -
no persistent state - so goldens and replays stay deterministic.
Counts scale with the `quality_3d` setting (0 = off, 1 = half,
2 = full); puddles are faked (dark sheen quad + light glints) in
`game.render3d_bridge.apply_set`, no reflection pass.
"""
from __future__ import annotations

import math

import pygame

__all__ = ["attach", "rain", "emitter", "fog_layer"]

_disc_cache: dict = {}


def _disc(col, size=64):
    key = (col, size)
    s = _disc_cache.get(key)
    if s is None:
        import numpy as np
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        yy, xx = np.mgrid[0:size, 0:size]
        d = ((xx - size / 2) / (size / 2)) ** 2 + ((yy - size / 2) / (size / 2)) ** 2
        a = (np.clip(1.0 - d, 0, 1) ** 1.5 * 255).astype(np.uint8)
        arr = pygame.surfarray.pixels_alpha(s)
        arr[:] = a
        rgb = pygame.surfarray.pixels3d(s)
        rgb[..., 0], rgb[..., 1], rgb[..., 2] = col[0], col[1], col[2]
        _disc_cache[key] = s
    return s


def _quality() -> int:
    try:
        from game.render3d_bridge import quality_3d  # lazy: settings owner
        return quality_3d()
    except Exception:
        return 2


def _hash01(i: int, seed: int, salt: int) -> float:
    return (math.sin((i + 1) * 12.9898 + seed * 78.233 + salt * 3.7) * 43758.5453) % 1.0


def _rain_simple(r, t: int, seed: int, n: int) -> None:
    """Fallback rain lattice (no FX module injected): seeded falling
    streaks around the camera, closed-form in (seed, t)."""
    cx, cy, cz = r.cam
    for i in range(n):
        u = _hash01(i, seed, 11)
        v = _hash01(i, seed, 12)
        x = math.floor(cx / 8) * 8 + (u * 2 - 1) * 20
        z = math.floor(cz / 8) * 8 + (v * 2 - 1) * 20
        phase = (t * 0.009 + u * 97 + v * 31) % 12.0
        y = 12.0 - phase
        if phase < 11.7:
            ln = 0.45
            r.add_line3d((x, y, z), (x - 0.03, y - ln, z - 0.01),
                         (70, 78, 94), 1, layer=3)


def rain(r, t: int, seed: int = 0, intensity: float = 1.0, fx=None) -> None:
    """Layered rain with splashes. Delegates to the host-injected FX
    module's rain lattice when given (hosts own that import - a shared
    module must not import mission-named modules, W1); otherwise the
    built-in fallback lattice above draws."""
    q = _quality()
    if q <= 0:
        return
    n_near = int(70 * intensity) if q >= 2 else int(35 * intensity)
    n_far = int(150 * intensity) if q >= 2 else int(70 * intensity)
    if fx is not None and hasattr(fx, "rain3d"):
        fx.rain3d(r, t, seed=seed, n_near=max(4, n_near), n_far=max(4, n_far),
                  splashes=10 if q >= 2 else 5)
    else:
        _rain_simple(r, t, seed, n_near + n_far)


def emitter(r, t: int, prim: dict) -> None:
    """One smoke/steam/dust emitter: rising soft particles, seeded."""
    q = _quality()
    if q <= 0:
        return
    kind = prim.get("sub", "smoke")
    base = tuple(prim["pos"])
    col = tuple(prim.get("color", (150, 150, 155)))
    rate = float(prim.get("rate", 1.0))
    rise = float(prim.get("rise", 1.2))
    spread = float(prim.get("spread", 0.35))
    size0 = float(prim.get("size", 0.5))
    seed = int(prim.get("seed", 0))
    n = int((26 if kind != "dust" else 34) * rate)
    if q == 1:
        n //= 2
    period = 4200.0 / max(0.2, rate)
    for i in range(n):
        ph = ((t + _hash01(i, seed, 1) * period) % period) / period
        ox = (_hash01(i, seed, 2) - 0.5) * spread * (0.4 + ph)
        oz = (_hash01(i, seed, 3) - 0.5) * spread * (0.4 + ph)
        drift = math.sin(t * 0.0006 + i) * 0.12 * ph
        pos = (base[0] + ox + drift, base[1] + rise * ph, base[2] + oz)
        alpha = (1.0 - ph) * (0.38 if kind == "smoke" else 0.42)
        size_m = size0 * (0.5 + ph * 1.6)

        def _draw(s, sx, sy, scale, z, _a=alpha, _sz=size_m, _c=col):
            px = max(4, int(_sz * scale))
            d = pygame.transform.smoothscale(_disc(_c), (px, px))
            d.set_alpha(int(255 * _a))
            s.blit(d, (int(sx - px / 2), int(sy - px / 2)))

        r.add_sprite(pos, _draw, layer=3)


def fog_layer(r, prim: dict) -> None:
    """A horizontal mist sheet: one wide soft sprite per layer quad."""
    if _quality() <= 0:
        return
    x0, z0, x1, z1 = prim["rect"]
    y = float(prim.get("y", 0.4))
    col = tuple(prim.get("color", (170, 180, 195)))
    density = float(prim.get("density", 0.5))
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    w_m = max(1.0, x1 - x0)

    def _draw(s, sx, sy, scale, z, _d=density, _c=col, _w=w_m):
        px = max(8, int(_w * scale))
        py = max(4, px // 5)
        d = pygame.transform.smoothscale(_disc(_c), (px, py))
        d.set_alpha(int(150 * _d))
        s.blit(d, (int(sx - px / 2), int(sy - py / 2)))

    r.add_sprite((cx, y, cz), _draw, layer=1)


def attach(r, prims, t: int, fx=None) -> None:
    """Apply a set's weather/emitter/fog_layer prims for this frame.
    ``fx`` is the host's FX module (rain lattice owner), if any."""
    for prim in prims:
        kind = prim["kind"]
        if kind == "weather" and prim.get("sub") == "rain":
            rain(r, t, seed=int(prim.get("seed", 0)),
                 intensity=float(prim.get("intensity", 1.0)), fx=fx)
        elif kind == "emitter":
            emitter(r, t, prim)
        elif kind == "fog_layer":
            fog_layer(r, prim)
