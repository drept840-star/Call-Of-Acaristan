"""engine3d.textures - pixel textures on world faces.

A face is textured by giving it a ``Tex`` colour in place of a plain RGB
tuple: ``box(2, 1, 2, tex("crate"))``. A Tex is still an (r, g, b) tuple, so
every path that only reads colours keeps working. The GL backend also reads
``.tex`` and multiplies the face by the texture; the software backend draws
the plain colour, which is the texture's average.

Textures are ``SIZE`` x ``SIZE`` PNGs in ``assets/tex3d/<name>.png``. They
are tiled in world space at a fixed texel density (``density`` texels per
metre), so a texture keeps its pixel size on every face whatever the face's
size. The GL backend works out the UVs itself (see ``gl._tex_frame``).

Each texture is stored divided by its own mean, and a face's colour is that
mean: the face is lit as usual and the shader multiplies the result by
texel / mean, which gives back the texel. ``like=`` scales the mean to
another colour's brightness, so swapping a flat colour for a texture keeps
the scene's exposure; ``tint=True`` keeps that colour outright, for painted
surfaces where the texture only adds its pattern. A tinted face reads the
texture's light and dark only (a greyscale copy of the layer): its hue
multiplied over paint turned a yellow barrel's rust patches green.
"""
import os
import sys

import numpy as np
import pygame

__all__ = ["Tex", "tex", "version", "stack", "SIZE"]

SIZE = 64
DENSITY = 32.0                      # default texels per metre: a tile is 2 m
# Textures drawn at another scale: snow at half the detail, so its drifts
# still read across a yard instead of melting into mip grey.
_DENSITY = {"snow": 16.0, "snow_trod": 16.0}

_names = {}                         # name -> layer
_layers = []                        # [(name, ratio float16 (SIZE, SIZE, 3), mean)]
_uvk = []                           # layer -> density / SIZE (tiles per metre)
_version = 0


class Tex(tuple):
    """An (r, g, b) colour that also names a texture layer (``.tex``) and its
    tiling (``.uvk``, tiles per metre)."""

    def __new__(cls, rgb, layer, uvk):
        t = tuple.__new__(cls, (int(rgb[0]), int(rgb[1]), int(rgb[2])))
        t.tex = layer
        t.uvk = uvk
        return t

    def with_rgb(self, rgb):
        """The same texture on another colour (a lit or dimmed copy)."""
        return Tex(rgb, self.tex, self.uvk)


def _root():
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, "assets", "tex3d")


def _load(name, density, mono=False):
    path = os.path.join(_root(), name + ".png")
    if not os.path.exists(path):
        return None
    img = pygame.image.load(path)
    if img.get_size() != (SIZE, SIZE):
        img = pygame.transform.scale(img, (SIZE, SIZE))
    rgb = np.asarray(pygame.surfarray.array3d(img), dtype=np.float64).transpose(1, 0, 2)
    if mono:
        rgb = np.repeat((rgb @ np.array([0.299, 0.587, 0.114]))[..., None], 3, axis=2)
    mean = np.maximum(rgb.reshape(-1, 3).mean(axis=0), 1.0)
    global _version
    key = name + "/tint" if mono else name
    layer = len(_layers)
    _layers.append((key, (rgb / mean).astype(np.float16), tuple(mean)))
    _uvk.append(float(density) / SIZE)
    _names[key] = layer
    _version += 1
    return layer


def tex(name, like=None, density=None, tint=False):
    """The colour a face takes to show texture ``name``.

    ``like``: an RGB colour whose brightness the face keeps (its hue still
    comes from the texture); with ``tint`` the face keeps ``like`` itself.
    ``density`` (texels per metre) only counts on a texture's first use.
    A missing texture gives back ``like`` (or grey)."""
    tint = tint and like is not None
    layer = _names.get(name + "/tint" if tint else name)
    if layer is None:
        if density is None:
            density = _DENSITY.get(name, DENSITY)
        layer = _load(name, density, mono=tint)
        if layer is None:
            return tuple(like) if like is not None else (128, 128, 128)
    if tint:
        return Tex(like, layer, _uvk[layer])
    mean = _layers[layer][2]
    rgb = mean
    if like is not None:
        y_like = 0.299 * like[0] + 0.587 * like[1] + 0.114 * like[2]
        y_mean = 0.299 * mean[0] + 0.587 * mean[1] + 0.114 * mean[2]
        k = y_like / max(y_mean, 1e-6)
        rgb = tuple(min(255.0, c * k) for c in mean)
    return Tex(tuple(round(c) for c in rgb), layer, _uvk[layer])


def version():
    """Bumps whenever a texture is added: the GL backend re-uploads then."""
    return _version


def stack():
    """All layers as one float16 array (L, SIZE, SIZE, 3), or None."""
    if not _layers:
        return None
    return np.stack([ratio for _, ratio, _ in _layers])
