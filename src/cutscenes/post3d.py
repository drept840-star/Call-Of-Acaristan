"""Cinematic post stack for cutscene shots (RPE6 Phase 11 step 5).

Applied centrally by ``cutscenes.engine.draw_cutscene_scene`` from a
shot's ``"post"`` block, so every effect is timeline-keyable data::

    "post": {"grade": "night_warm", "grain": 0.3, "vignette": 0.55,
             "bloom": 0.5, "distortion": 0.015,
             "dof_focus": 6.0, "dof_strength": 0.7}

Values may be numbers or timeline expressions (env: ``t`` seconds,
``k`` shot progress, ``dur`` seconds).  Grade curves are data
(``src/game/content/grades/<id>.grade.json``: 17-point channel
curves).  Grain uses a named seeded stream (crc32 of scene+t bucket)
so goldens stay deterministic.  ``dof_*`` is consumed by renderers
themselves (they own depth; see ``core.cutscene_registry
current_shot``) - the rest is applied here, in grade -> distortion ->
bloom -> vignette -> grain order.

Quality gates (settings `quality_3d`): 0 = off, 1 = grade+vignette+
grain only, 2 = everything.  Accessibility: `film_grain` off kills
grain; `flash_reduction` caps bloom.
"""
from __future__ import annotations

import json
import os
import zlib

import numpy as np
import pygame

__all__ = ["apply_post", "grade_names"]

GRADES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "game", "content", "grades")
_cache: dict = {}


def _quality() -> int:
    try:
        from game.render3d_bridge import quality_3d  # lazy: bridge owner
        return quality_3d()
    except Exception:
        return 2


def grade_names() -> list:
    if os.path.isdir(GRADES_DIR):
        return sorted(f[: -len(".grade.json")] for f in os.listdir(GRADES_DIR)
                      if f.endswith(".grade.json"))
    return []


def _lut(gid: str):
    if gid not in _cache:
        with open(os.path.join(GRADES_DIR, f"{gid}.grade.json"),
                  encoding="utf-8") as fh:
            data = json.load(fh)
        xs = np.linspace(0, 255, 17)
        lut = []
        for ch in ("r", "g", "b"):
            pts = data["channels"][ch]
            lut.append(np.interp(np.arange(256), xs, pts).astype(np.uint8))
        _cache[gid] = np.stack(lut, axis=0)  # [3, 256] per-channel curves
    return _cache[gid]


def _arr(surf):
    return pygame.surfarray.array3d(surf).astype(np.int16)


def _put(surf, arr):
    pygame.surfarray.blit_array(
        surf, np.clip(arr, 0, 255).astype(np.uint8))


def apply_grade(surf, gid: str) -> None:
    curves = _lut(gid)
    a = pygame.surfarray.array3d(surf)
    out = np.empty_like(a)
    for c in range(3):
        out[..., c] = curves[c][a[..., c]]
    pygame.surfarray.blit_array(surf, out)


def _vignette_surf(w: int, h: int, strength: float):
    key = (w, h, int(strength * 20))
    s = _cache.get(("vig",) + key)
    if s is None:
        xx, yy = np.mgrid[0:w, 0:h]  # surfarray axis order is [x, y]
        r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        a = (np.clip((r - 0.62) / 0.55, 0, 1) ** 2 * 255 * strength).astype(np.uint8)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.surfarray.pixels_alpha(s)[:] = a
        _cache[("vig",) + key] = s
    return s


def apply_post(surf, spec, t: int, scene_id: str = "", dur_ms: int = 0) -> None:
    if not spec:
        return
    q = _quality()
    if q <= 0:
        return
    from engine.timeline import evaluate  # lazy: expr kernel

    env = {"t": t / 1000.0, "k": (t / dur_ms) if dur_ms else 0.0,
           "dur": (dur_ms or 0) / 1000.0}

    def val(name, default=0.0):
        v = spec.get(name, default)
        if isinstance(v, str):
            return float(evaluate(v, env))
        return float(v)

    w, h = surf.get_size()
    grade = spec.get("grade")
    if grade:
        apply_grade(surf, str(grade))
    if q >= 2:
        dist = val("distortion")
        if abs(dist) > 0.002:
            key = (w, h, int(dist * 500))
            maps = _cache.get(("dist",) + key)
            if maps is None:
                xx, yy = np.mgrid[0:w, 0:h].astype(np.float32)  # [x, y] order
                cx, cy = w / 2, h / 2
                rx, ry = (xx - cx) / cx, (yy - cy) / cy
                r2 = rx * rx + ry * ry
                scale = 1.0 + dist * r2
                maps = (np.clip((cx + rx * scale * cx), 0, w - 1).astype(np.int32),
                        np.clip((cy + ry * scale * cy), 0, h - 1).astype(np.int32))
                _cache[("dist",) + key] = maps
            a = pygame.surfarray.array3d(surf)
            pygame.surfarray.blit_array(surf, a[maps[0], maps[1]])
        bloom = val("bloom")
        if bloom > 0.01:
            try:
                from core.user_settings import SETTINGS
                if SETTINGS.flash_reduction:
                    bloom = min(bloom, 0.35)
            except Exception:
                pass
            small = pygame.transform.smoothscale(surf, (w // 4, h // 4))
            a = _arr(small)
            bright = np.clip(a - 165, 0, 255).astype(np.uint8)
            bs = pygame.surfarray.make_surface(bright)
            glow = pygame.transform.smoothscale(bs, (w // 16, h // 16))
            glow = pygame.transform.smoothscale(glow, (w, h))
            glow.set_alpha(int(200 * min(1.0, bloom)))
            surf.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    vig = val("vignette")
    if vig > 0.01:
        surf.blit(_vignette_surf(w, h, min(1.0, vig)), (0, 0))
    grain = val("grain")
    if grain > 0.01:
        try:
            from core.user_settings import SETTINGS
            if not SETTINGS.film_grain:
                grain = 0.0
        except Exception:
            pass
    if grain > 0.01:
        seed = zlib.crc32(f"{scene_id}:{t // 40}".encode("utf-8"))
        rng = np.random.default_rng(seed)
        noise = rng.integers(-1, 2, size=(w // 2, h // 2), dtype=np.int16)
        noise = np.repeat(np.repeat(noise, 2, axis=0), 2, axis=1)
        a = _arr(surf)
        a += (noise[:w, :h] * int(28 * grain)).astype(np.int16)[..., None]
        _put(surf, a)
