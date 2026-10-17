"""Raw file loaders: the only place in the codebase that may call
``pygame.image.load`` / ``pygame.mixer.Sound`` on game assets (D5 tracker).

They are deliberately thin so behaviour is identical to the direct calls they
replace; the point is a single chokepoint for path resolution, error logging
and later caching/packing. ``load_image(convert=None)`` keeps the exact legacy
semantics: ``convert_alpha()`` only when the caller asks for it.
"""
from __future__ import annotations

from typing import Any

__all__ = ["load_image", "load_sound", "load_music"]

_resolve = None


def configure(resolve) -> None:
    """Install a path resolver (e.g. ``core.config.resource_path``) used for str paths."""
    global _resolve
    _resolve = resolve


def _path(src):
    if isinstance(src, str) and _resolve is not None:
        return _resolve(src)
    return src


def load_image(src: Any, *, convert: str | None = None, resolve: bool = False):
    """``pygame.image.load`` + optional ``"alpha"``/``"opaque"`` conversion.

    ``src`` may be a path or a file-like object; ``resolve=True`` routes a str
    path through the configured resolver (PyInstaller-safe).
    """
    import pygame
    surf = pygame.image.load(_path(src) if resolve else src)
    if convert == "alpha":
        surf = surf.convert_alpha()
    elif convert == "opaque":
        surf = surf.convert()
    return surf


def load_sound(src: Any, *, resolve: bool = False):
    """``pygame.mixer.Sound`` for a path, file-like or buffer (mixer must be initialised)."""
    import pygame
    return pygame.mixer.Sound(_path(src) if resolve else src)


def load_music(src: Any, *, resolve: bool = False) -> None:
    """``pygame.mixer.music.load`` for a path or file-like."""
    import pygame
    pygame.mixer.music.load(_path(src) if resolve else src)
