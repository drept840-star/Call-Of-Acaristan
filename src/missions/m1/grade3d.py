"""Mission 1 night grade for the 2.5D frame: a screen-space light map.

The 3D pass lights the set; this pass makes it read as night. The frame is
multiplied by a light map that starts at a midnight-blue ambient and gets
soft radial lights added where lamps, lit windows, tail lights, fires and
muzzle flashes are; then the hot cores and the wet-pavement reflections
under them are added on top (bloom), and a faint blue lift goes into the
blacks. Lights are given in world space and projected through the frame's
``td.View``, so they track the camera like the set does.

Light tuples: ``(kind, pos, color, radius_m, intensity)``.
  "pool"    - an ellipse on the ground under ``pos`` (lamp throw, window spill)
  "glow"    - a point light at ``pos`` (bulb, window glass, flame, muzzle)
  "reflect" - a vertical streak on the wet floor below ``pos``

Gradients are pre-rendered per (colour, size) and cached; the pass is pure
drawing and touches no game state.
"""
import math

import numpy as np
import pygame

AMBIENT = (118, 130, 160)          # the light map's floor: midnight blue
NIGHT_LIFT = (5, 8, 14)            # added after the multiply: blue in the blacks
VIGNETTE_MAX = 175
_BASE_PX = 128

_grads = {}
_cache = {"lm": None, "vig": None}


def _base():
    if "base" not in _cache:
        n = _BASE_PX
        y, x = np.mgrid[0:n, 0:n].astype(np.float32)
        d = np.hypot(x - (n - 1) / 2.0, y - (n - 1) / 2.0) / (n / 2.0)
        f = np.clip(1.0 - d * d, 0.0, 1.0) ** 2
        _cache["base"] = f
    return _cache["base"]


def _grad(col, w, h):
    """Additive radial gradient, ``col`` at the centre to black at the rim."""
    w = max(4, int(w) // 4 * 4)
    h = max(4, int(h) // 4 * 4)
    c = tuple(max(0, min(255, int(v) // 6 * 6)) for v in col)
    key = (c, w, h)
    s = _grads.get(key)
    if s is None:
        if len(_grads) > 400:
            _grads.clear()
        arr = (_base()[..., None] * np.array(c, np.float32)).astype(np.uint8)
        src = pygame.surfarray.make_surface(np.ascontiguousarray(arr))
        s = _grads[key] = pygame.transform.smoothscale(src, (w, h))
    return s


def _scale(col, k):
    return (col[0] * k, col[1] * k, col[2] * k)


def _add(dst, col, cx, cy, w, h):
    if w < 4 or h < 4:
        return
    dw, dh = dst.get_size()
    if cx + w / 2.0 < 0 or cx - w / 2.0 > dw or cy + h / 2.0 < 0 or cy - h / 2.0 > dh:
        return
    g = _grad(col, w, h)
    dst.blit(g, (int(cx - g.get_width() / 2.0), int(cy - g.get_height() / 2.0)),
             special_flags=pygame.BLEND_RGB_ADD)


def _light_map(size, ambient=AMBIENT):
    lm = _cache["lm"]
    if lm is None or lm.get_size() != size:
        lm = _cache["lm"] = pygame.Surface(size)
    lm.fill(ambient)
    return lm


def apply(surface, v, lights, ambient=AMBIENT):
    """Grade ``surface`` (the presented 3D frame) through view ``v``."""
    lm = _light_map(surface.get_size(), ambient)
    bloom = []
    for kind, pos, col, rad, k in lights:
        x, y, z = pos
        if kind == "pool":
            c = v.screen((x, 0.0, z))
            ex = v.screen((x + rad, 0.0, z))
            n, s = v.screen((x, 0.0, z + rad)), v.screen((x, 0.0, z - rad))
            if c is None or ex is None or n is None or s is None:
                continue
            w = abs(ex[0] - c[0]) * 2.0
            h = abs(s[1] - n[1])
            _add(lm, _scale(col, k), c[0], (n[1] + s[1]) / 2.0, w, h)
            continue
        c = v.screen(pos)
        ex = v.screen((x + rad, y, z))
        if c is None or ex is None:
            continue
        r = abs(ex[0] - c[0])
        if kind == "glow":
            _add(lm, _scale(col, k), c[0], c[1], r * 2.0, r * 2.0)
            bloom.append((_scale(col, k * 0.38), c[0], c[1], r * 0.9, r * 0.9))
        elif kind == "reflect":
            g = v.screen((x, 0.0, z))
            if g is not None:
                bloom.append((_scale(col, k), g[0], g[1] + r * 1.4, r * 0.7, r * 3.2))
    surface.blit(lm, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    for col, cx, cy, w, h in bloom:
        _add(surface, col, cx, cy, w, h)
    surface.fill(NIGHT_LIFT, special_flags=pygame.BLEND_RGB_ADD)


def vignette(surface):
    """Soft dark corners: smoothstep from the middle of the frame out."""
    size = surface.get_size()
    vig = _cache["vig"]
    if vig is None or vig.get_size() != size:
        w, h = size
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.hypot((x - w / 2.0) / (w / 2.0), (y - h / 2.0) / (h / 2.0)) / math.sqrt(2.0)
        t = np.clip((d - 0.42) / 0.58, 0.0, 1.0)
        a = (t * t * (3.0 - 2.0 * t) * VIGNETTE_MAX).astype(np.uint8)
        vig = pygame.Surface(size, pygame.SRCALPHA)
        vig.fill((3, 5, 9, 0))
        pygame.surfarray.pixels_alpha(vig)[:] = a.T
        _cache["vig"] = vig
    surface.blit(vig, (0, 0))
