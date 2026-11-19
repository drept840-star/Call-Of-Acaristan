"""Mission 1–5 / Walk / Arena night grade for 2.5D frames."""
from collections import OrderedDict
import math

import numpy as np
import pygame

AMBIENT = (118, 130, 160)          # the light map's floor: midnight blue
VIGNETTE_MAX = 175
_BASE_PX = 128

_grads = OrderedDict()
_cones = OrderedDict()
_cache = {"lm": None, "vig": None}


def _safe_convert(surf):
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        return surf.convert()
    return surf


def _base():
    if "base" not in _cache:
        n = _BASE_PX
        x, y = np.mgrid[0:n, 0:n].astype(np.float32)
        d = np.hypot(x - (n - 1) / 2.0, y - (n - 1) / 2.0) / (n / 2.0)
        d2 = d * d
        f = np.where(d < 1.0, np.exp(-d2 * 2.1) * np.maximum(0.0, 1.0 - d2) ** 1.35, 0.0)
        _cache["base"] = f
    return _cache["base"]


def _glow_base():
    if "glow" not in _cache:
        n = _BASE_PX
        x, y = np.mgrid[0:n, 0:n].astype(np.float32)
        d = np.hypot(x - (n - 1) / 2.0, y - (n - 1) / 2.0) / (n / 2.0)
        d2 = d * d
        f = np.clip(0.38 * np.exp(-d2 * 3.0) * np.maximum(0.0, 1.0 - d2)
                    + 0.72 * np.exp(-d2 * 16.0), 0.0, 1.0)
        _cache["glow"] = f
    return _cache["glow"]


def _reflect_base():
    if "reflect" not in _cache:
        n = _BASE_PX
        x, y = np.mgrid[0:n, 0:n].astype(np.float32)
        dx = (x - (n - 1) / 2.0) / (n / 2.0)
        dy = (y - (n - 1) / 2.0) / (n / 2.0)
        d2 = dx * dx + dy * dy
        ripple = 0.56 + 0.44 * np.sin(y * 0.72 + x * 0.14)
        f = np.where(d2 < 1.0,
                     ripple * np.exp(-dx * dx * 3.8) * np.power(np.maximum(0.0, 1.0 - d2), 1.35),
                     0.0)
        _cache["reflect"] = f
    return _cache["reflect"]


def _grad(col, w, h, kind="pool"):
    """Additive radial / optical-glow / wet-ripple gradient (native format)."""
    w = max(4, int(w) // 4 * 4)
    h = max(4, int(h) // 4 * 4)
    c = tuple(max(0, min(255, int(v) // 6 * 6)) for v in col)
    key = (kind, c, w, h)
    s = _grads.get(key)
    if s is None:
        if len(_grads) >= 768:
            _grads.popitem(last=False)
        base = _glow_base() if kind == "glow" else (_reflect_base() if kind == "reflect" else _base())
        arr = (base[..., None] * np.array(c, np.float32)).astype(np.uint8)
        src = pygame.surfarray.make_surface(np.ascontiguousarray(arr))
        s = _grads[key] = _safe_convert(pygame.transform.smoothscale(src, (w, h)))
    else:
        _grads.move_to_end(key)
    return s


def _cone_grad(col, reach_px, screen_ang):
    """64-angle quantized directional flashlight cone (1/4-res build, native format)."""
    bucket = int(round(screen_ang / (2.0 * math.pi) * 64.0)) % 64
    rq = max(40, int(reach_px) // 8 * 8)
    c = tuple(max(0, min(255, int(v) // 8 * 8)) for v in col)
    key = (bucket, rq, c)
    hit = _cones.get(key)
    if hit is not None:
        _cones.move_to_end(key)
        return hit
    if len(_cones) >= 256:
        _cones.popitem(last=False)
    qr = max(24, rq // 4)
    a = bucket * (2.0 * math.pi / 64.0)
    ca, sa = math.cos(a), math.sin(a)
    sz = qr * 2
    xx, yy = np.mgrid[0:sz, 0:sz].astype(np.float32)
    rx, ry = xx - qr, yy - qr
    fwd = rx * ca + ry * sa
    lat = -rx * sa + ry * ca
    dist = np.hypot(rx, ry)
    cone_r = dist / float(qr)
    ang_ratio = np.abs(lat) / np.maximum(2.5, fwd * 0.48 + 2.5)
    in_cone = (fwd > -1.5) & (cone_r < 1.0) & (ang_ratio < 1.0)
    cone_i = np.where(
        in_cone,
        0.86 * np.power(np.maximum(0.0, 1.0 - cone_r), 1.3)
        * np.power(np.maximum(0.0, 1.0 - ang_ratio * ang_ratio), 1.6),
        0.0,
    )
    body_r = dist / 12.0
    body_i = np.where(body_r < 1.0, 0.34 * np.power(np.maximum(0.0, 1.0 - body_r * body_r), 1.6), 0.0)
    tot = np.maximum(cone_i, body_i)
    nz = np.nonzero(tot > 0.01)
    x0, x1 = int(nz[0].min()), int(nz[0].max()) + 1
    y0, y1 = int(nz[1].min()), int(nz[1].max()) + 1
    crop = tot[x0:x1, y0:y1]
    cw, ch = x1 - x0, y1 - y0
    rgb = np.empty((cw, ch, 3), dtype=np.uint8)
    for ch_i in range(3):
        rgb[..., ch_i] = np.clip(crop * c[ch_i], 0, 255).astype(np.uint8)
    small = pygame.surfarray.make_surface(rgb)
    spr = _safe_convert(pygame.transform.smoothscale(small, (cw * 4, ch * 4)))
    res = (spr, (x0 - qr) * 4, (y0 - qr) * 4)
    _cones[key] = res
    return res


def _scale(col, k):
    return (col[0] * k, col[1] * k, col[2] * k)


def _add(dst, col, cx, cy, w, h, kind="pool"):
    if w < 4 or h < 4:
        return
    dw, dh = dst.get_size()
    w, h = min(w, dw * 2.0), min(h, dh * 2.0)    # free cut cameras get close to lights
    if cx + w / 2.0 < 0 or cx - w / 2.0 > dw or cy + h / 2.0 < 0 or cy - h / 2.0 > dh:
        return
    g = _grad(col, w, h, kind=kind)
    dst.blit(g, (int(cx - g.get_width() / 2.0), int(cy - g.get_height() / 2.0)),
             special_flags=pygame.BLEND_RGB_ADD)


def _light_map(size, ambient=AMBIENT):
    lm = _cache["lm"]
    if lm is None or lm.get_size() != size:
        lm = _cache["lm"] = _safe_convert(pygame.Surface(size))
    lm.fill(ambient)
    return lm


def lift_of(ambient):
    """The lift added after the multiply: a little of the ambient's own hue
    in the blacks. A fixed blue lift turned every warm or neutral room
    blue-grey (it is most of a dark frame's colour)."""
    lo = min(ambient)
    return tuple(int(2 + (c - lo) * 0.25) for c in ambient)


def apply(surface, v, lights, ambient=AMBIENT):
    """Grade ``surface`` (the presented 3D frame) through view ``v``."""
    lm = _light_map(surface.get_size(), ambient)
    bloom = []
    for item in lights:
        kind = item[0]
        if kind == "cone":
            _, pos, ang, col, reach_m, k = item
            x, _y, z = pos
            c = v.screen((x, 0.0, z))
            tip = v.screen((x + math.cos(ang) * reach_m, 0.0, z - math.sin(ang) * reach_m))
            if c is None or tip is None:
                continue
            sr = math.hypot(tip[0] - c[0], tip[1] - c[1])
            if sr > 10.0:
                spr, ox, oy = _cone_grad(_scale(col, k), sr, math.atan2(tip[1] - c[1], tip[0] - c[0]))
                lm.blit(spr, (int(c[0] + ox), int(c[1] + oy)), special_flags=pygame.BLEND_RGB_ADD)
            continue
        _, pos, col, rad, k = item
        x, y, z = pos
        if kind == "pool":
            c = v.screen((x, 0.0, z))
            ex = v.screen((x + rad, 0.0, z))
            n, s = v.screen((x, 0.0, z + rad)), v.screen((x, 0.0, z - rad))
            if c is None or ex is None or n is None or s is None:
                continue
            w = abs(ex[0] - c[0]) * 2.0
            h = abs(s[1] - n[1])
            _add(lm, _scale(col, k), c[0], (n[1] + s[1]) / 2.0, w, h, kind="pool")
            continue
        if kind == "fire":
            c = v.screen(pos)
            ex = v.screen((x + rad, y, z))
            if c is None or ex is None:
                continue
            r = abs(ex[0] - c[0])
            _add(lm, _scale(col, k * 0.72), c[0], c[1], r * 3.0, r * 2.6, kind="pool")
            _add(lm, _scale((255, 250, 232), min(1.35, max(0.90, k * 1.15))),
                 c[0], c[1], r * 1.15, r * 1.15, kind="pool")
            bloom.append(("glow", _scale(col, k * 0.36), c[0], c[1], r * 1.55, r * 1.45))
            bloom.append(("glow", _scale((255, 210, 118), k * 0.20), c[0], c[1], r * 0.65, r * 0.65))
            continue
        c = v.screen(pos)
        ex = v.screen((x + rad, y, z))
        if c is None or ex is None:
            continue
        r = abs(ex[0] - c[0])
        if kind == "glow":
            _add(lm, _scale(col, k), c[0], c[1], r * 2.0, r * 2.0, kind="pool")
            bloom.append(("glow", _scale(col, k * 0.46), c[0], c[1], r * 1.15, r * 1.15))
        elif kind == "reflect":
            g = v.screen((x, 0.0, z))
            if g is not None:
                bloom.append(("reflect", _scale(col, k), g[0], g[1] + r * 1.4, r * 0.78, r * 3.4))
    surface.blit(lm, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    for bkind, col, cx, cy, w, h in bloom:
        _add(surface, col, cx, cy, w, h, kind=bkind)
    surface.fill(lift_of(ambient), special_flags=pygame.BLEND_RGB_ADD)


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
