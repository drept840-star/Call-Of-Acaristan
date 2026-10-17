"""Bake camera-space procedural painters into world layers (Phase 3 conversion kit).

The legacy missions paint their dressing with ``pygame.draw.*(screen, col,
(world_x - cam_x, world_y - cam_y, ...))`` where ``screen`` is a module global.
``bake_camera_layer`` runs such a painter once per window-sized tile with the
module's ``screen`` redirected to a canvas and returns one RGBA surface whose
(0, 0) is world ``origin``. The result blits with ``(origin - cam)`` and is
pixel-identical to the live painter for everything drawn opaque and for every
translucent element that lands on an untouched canvas pixel; translucency
stacked on translucency is composited with the exact *over* operator (see
``BakeSurface.blit``) and can differ from the live screen by rounding only.
Additive / multiplicative blits over the live world cannot be represented and
must stay live; ``probe_layer`` measures all of that.

``BakeSurface`` emulates an opaque screen on an SRCALPHA canvas: ``fill`` /
``set_at`` and (inside ``screen_emulation``) every ``pygame.draw`` /
``pygame.gfxdraw`` primitive drop the alpha component of 4-tuple colours when
the target is the canvas, because on the real screen (no per-pixel alpha) those
alphas are ignored. Blits onto the canvas keep their alpha, as on screen.
"""
from __future__ import annotations

import contextlib
from typing import Callable, Iterable

import pygame

__all__ = ["BakeSurface", "screen_emulation", "bake_camera_layer", "bake_chunk_layer", "probe_layer", "layer_bounds"]

_DRAW_FUNCS = ("rect", "polygon", "circle", "ellipse", "arc", "line", "lines", "aaline", "aalines")
_GFX_FUNCS = ("pixel", "hline", "vline", "line", "rectangle", "box", "circle", "aacircle", "filled_circle",
              "ellipse", "aaellipse", "filled_ellipse", "arc", "pie", "trigon", "aatrigon", "filled_trigon",
              "polygon", "aapolygon", "filled_polygon", "bezier")


def _opaque(color):
    if isinstance(color, pygame.Color):
        return (color.r, color.g, color.b)
    if isinstance(color, (tuple, list)) and len(color) == 4:
        return tuple(color[:3])
    return color


class BakeSurface(pygame.Surface):
    """SRCALPHA canvas that behaves like the opaque screen for direct pixel writes.

    ``blit`` composites with the exact *over* operator so that translucent
    elements stacked on each other bake to the same result the live screen
    shows (pygame's RGBA->RGBA blit is not an over operator; it would drift by
    tens of levels).  Three regimes per pixel:

    * destination alpha 0   -> source stored verbatim (what pygame does, exact);
    * destination alpha 255 -> pygame's own integer formula (bit-exact with the
      live screen draw);
    * in between            -> float over, rounded (rounding-level vs live).

    Blits with ``special_flags`` (additive, multiply, ...) cannot be stored in
    an alpha layer where the canvas is not yet opaque; they are performed with
    pygame and counted in ``unrepresentable_px`` so probes/lints can flag the
    painter for a static/live split.
    """

    def __init__(self, size):
        super().__init__(size, pygame.SRCALPHA)
        self.unrepresentable_px = 0

    def fill(self, color=(0, 0, 0), rect=None, special_flags=0):
        if special_flags:
            return super().fill(color, rect, special_flags)
        return super().fill(_opaque(color), rect)

    def set_at(self, pos, color):
        return super().set_at(pos, _opaque(color))

    def blits(self, blit_sequence, doreturn=True):
        out = []
        for item in blit_sequence:
            out.append(self.blit(*item))
        return out if doreturn else None

    def blit(self, source, dest, area=None, special_flags=0):
        import numpy as np  # lazy: bake-time only

        if isinstance(dest, pygame.Rect):
            dx, dy = dest.x, dest.y
        else:
            dx, dy = int(dest[0]), int(dest[1])
        src_rect = source.get_rect() if area is None else pygame.Rect(area).clip(source.get_rect())
        if src_rect.w <= 0 or src_rect.h <= 0:
            return pygame.Rect(dx, dy, 0, 0)
        target = pygame.Rect(dx, dy, src_rect.w, src_rect.h)
        clip = target.clip(self.get_clip())
        if clip.w <= 0 or clip.h <= 0:
            return pygame.Rect(dx, dy, 0, 0)
        if special_flags:
            da = pygame.surfarray.pixels_alpha(self)
            self.unrepresentable_px += int(np.count_nonzero(da[clip.x:clip.right, clip.y:clip.bottom] != 255))
            del da
            return super().blit(source, dest, area, special_flags)
        # source pixels (RGBA, colourkey -> alpha 0), restricted to the clipped region
        sub = pygame.Rect(src_rect.x + (clip.x - target.x), src_rect.y + (clip.y - target.y), clip.w, clip.h)
        raw = pygame.image.tobytes(source.subsurface(sub), "RGBA")
        s = np.frombuffer(raw, dtype=np.uint8).reshape(clip.h, clip.w, 4).astype(np.int32)
        sa = source.get_alpha()
        A = s[:, :, 3]
        if sa is not None and sa < 255:
            A = (A * int(sa)) // 255
        sc = s[:, :, :3]
        d3 = pygame.surfarray.pixels3d(self)[clip.x:clip.right, clip.y:clip.bottom].transpose(1, 0, 2)
        dA = pygame.surfarray.pixels_alpha(self)[clip.x:clip.right, clip.y:clip.bottom].T
        dc = d3.astype(np.int32)
        da = dA.astype(np.int32)
        has_src = A > 0
        m0 = has_src & (da == 0)
        m255 = has_src & (da == 255)
        mid = has_src & (da > 0) & (da < 255)
        out_c = dc.copy()
        out_a = da.copy()
        if m0.any():
            out_c[m0] = sc[m0]
            out_a[m0] = A[m0]
        if m255.any():
            A3 = A[:, :, None]
            v = dc + (((sc - dc) * A3 + sc) >> 8)
            out_c[m255] = v[m255]
        if mid.any():
            aS = A.astype(np.float64) / 255.0
            aD = da.astype(np.float64) / 255.0
            aO = aS + aD * (1.0 - aS)
            num = sc.astype(np.float64) * aS[:, :, None] + dc.astype(np.float64) * (aD * (1.0 - aS))[:, :, None]
            v = np.rint(num / np.maximum(aO, 1e-9)[:, :, None]).astype(np.int32)
            out_c[mid] = v[mid]
            out_a[mid] = np.rint(aO * 255.0).astype(np.int32)[mid]
        d3[...] = np.clip(out_c, 0, 255).astype(np.uint8)
        dA[...] = np.clip(out_a, 0, 255).astype(np.uint8)
        del d3, dA
        return pygame.Rect(clip)


@contextlib.contextmanager
def screen_emulation(targets: Iterable[pygame.Surface]):
    """Patch pygame.draw / pygame.gfxdraw so 4-tuple colours drawn on ``targets`` lose their alpha."""
    ids = {id(t) for t in targets}
    saved = []

    def wrap(mod, name):
        orig = getattr(mod, name)

        def f(surface, color, *a, **k):
            if id(surface) in ids:
                color = _opaque(color)
            return orig(surface, color, *a, **k)
        f.__name__ = name
        f.__wrapped__ = orig
        saved.append((mod, name, orig))
        setattr(mod, name, f)

    for n in _DRAW_FUNCS:
        if hasattr(pygame.draw, n):
            wrap(pygame.draw, n)
    try:
        import pygame.gfxdraw as gfx
        for n in _GFX_FUNCS:
            if hasattr(gfx, n):
                wrap(gfx, n)
    except ImportError:
        pass
    try:
        yield
    finally:
        for mod, name, orig in reversed(saved):
            setattr(mod, name, orig)


@contextlib.contextmanager
def _redirect(redirects, surface):
    saved = [(mod, attr, getattr(mod, attr)) for mod, attr in redirects]
    for mod, attr in redirects:
        setattr(mod, attr, surface)
    try:
        yield
    finally:
        for mod, attr, old in saved:
            setattr(mod, attr, old)


def bake_camera_layer(paint: Callable[[int, int], None], *, size, origin, tile, redirect, stats=None) -> pygame.Surface:
    """Render ``paint(cam_x, cam_y)`` into a ``size`` canvas whose (0, 0) is world ``origin``.

    ``tile`` is the live window size: the painter is called once per tile with
    the camera at the tile's world corner, so any culling it does against the
    window behaves exactly as at runtime. ``redirect`` lists ``(module, attr)``
    pairs whose value is the painter's screen global. ``stats`` (optional dict)
    receives ``unrepresentable_px``: pixels touched by special-flag blits while
    the canvas was not yet opaque there (such painters need a static/live split).
    """
    w, h = size
    tw, th = tile
    canvas = pygame.Surface((w, h), pygame.SRCALPHA)
    bad = 0
    for ty in range(0, h, th):
        for tx in range(0, w, tw):
            tile_surf = BakeSurface((min(tw, w - tx), min(th, h - ty)))
            with screen_emulation([tile_surf]), _redirect(redirect, tile_surf):
                paint(origin[0] + tx, origin[1] + ty)
            bad += tile_surf.unrepresentable_px
            canvas.blit(tile_surf, (tx, ty))
    if stats is not None:
        stats["unrepresentable_px"] = bad
    return canvas


def bake_chunk_layer(bake_cb: Callable[[pygame.Surface, int, int], None], *, world_size, chunk=512,
                     fill=(0, 0, 0)) -> pygame.Surface:
    """Run a chunked static-world callback ``bake_cb(surface, origin_x, origin_y)`` over the whole
    world and return ONE opaque surface covering the chunk grid (``ceil(w/chunk)*chunk`` wide).

    This reproduces a runtime chunk cache exactly: every chunk is a fresh opaque surface filled
    with ``fill``, the callback paints it with the camera at the chunk corner, and the chunks are
    stitched at their grid position. Blitting the result at ``(-cam_x, -cam_y)`` is pixel-identical
    to blitting the live chunks. The caller owns any "baking" flag the painters consult.
    """
    w, h = world_size
    cols = max(1, -(-int(w) // chunk))
    rows = max(1, -(-int(h) // chunk))
    canvas = pygame.Surface((cols * chunk, rows * chunk))
    canvas.fill(fill)
    for cj in range(rows):
        for ci in range(cols):
            surf = pygame.Surface((chunk, chunk))
            surf.fill(fill)
            bake_cb(surf, ci * chunk, cj * chunk)
            canvas.blit(surf, (ci * chunk, cj * chunk))
    return canvas


def layer_bounds(paint, *, world_rect, tile, redirect, pad=0):
    """World-space bounding rect of everything ``paint`` draws inside ``world_rect`` (probe pass)."""
    x0, y0, w, h = world_rect
    best = None
    tw, th = tile
    for ty in range(0, h, th):
        for tx in range(0, w, tw):
            t = BakeSurface((min(tw, w - tx), min(th, h - ty)))
            with screen_emulation([t]), _redirect(redirect, t):
                paint(x0 + tx, y0 + ty)
            r = t.get_bounding_rect()
            if r.w and r.h:
                r.move_ip(x0 + tx, y0 + ty)
                best = r if best is None else best.union(r)
    if best is None:
        return None
    return best.inflate(2 * pad, 2 * pad)


def probe_layer(paint, layer, origin, *, cams, tile, redirect, backgrounds=((0, 0, 0), (255, 255, 255), (97, 101, 109))):
    """Compare the live painter with the baked layer at several camera positions.

    Returns a dict: ``pixels`` compared, ``diff`` differing pixels, ``max_delta``
    (largest channel difference), ``worst`` (cam, background) of the worst tile.
    """
    import numpy as np
    tw, th = tile
    total = diff = 0
    max_delta = 0
    worst = None
    for cam in cams:
        for bg in backgrounds:
            live = pygame.Surface((tw, th))
            live.fill(bg)
            with _redirect(redirect, live):
                paint(cam[0], cam[1])
            baked = pygame.Surface((tw, th))
            baked.fill(bg)
            baked.blit(layer, (origin[0] - cam[0], origin[1] - cam[1]))
            a = np.frombuffer(pygame.image.tobytes(live, "RGB"), dtype=np.uint8).astype(np.int16)
            b = np.frombuffer(pygame.image.tobytes(baked, "RGB"), dtype=np.uint8).astype(np.int16)
            d = np.abs(a - b).reshape(-1, 3).max(1)
            n = int((d > 0).sum())
            total += len(d)
            diff += n
            md = int(d.max()) if len(d) else 0
            if md > max_delta or (md == max_delta and worst is None):
                max_delta = md
                worst = (tuple(cam), bg, n)
    return {"pixels": total, "diff": diff, "max_delta": max_delta, "worst": worst}
