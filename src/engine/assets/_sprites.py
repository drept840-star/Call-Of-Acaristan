
"""sprite_lib.py - tiny cached PNG loader with graceful fallback.

The game is fully procedural by default; a handful of hero interactables
(Battery Backup cabinet, Security booth) ship as real sprites for instant
legibility. If the PNGs are missing (bare zip, stripped install), get_sprite()
returns None and every call site falls back to its procedural renderer, so the
game never crashes and never requires assets.
"""
import os
import pygame
# RPE6 Phase 2 (A-006): moved verbatim from entities/sprite_lib.py (owner module of engine.assets.sprites) except for the injection points marked RPE6.
__all__ = ["configure", "sprite_path", "get_sprite"]

_RESOLVE = None   # RPE6: path resolver injected by the host (core.config.resource_path in the game)


def configure(resolve):
    global _RESOLVE
    _RESOLVE = resolve


def resource_path(rel):
    return _RESOLVE(rel) if _RESOLVE is not None else rel

_CACHE = {}


def sprite_path(name):
    return os.path.join(resource_path("assets"), "sprites", name)


def get_sprite(name):
    """Return a cached Surface for assets/sprites/<name>, or None if absent."""
    if name in _CACHE:
        return _CACHE[name]
    surf = None
    try:
        path = sprite_path(name)
        if os.path.exists(path):
            surf = pygame.image.load(path).convert_alpha()
    except Exception:
        surf = None
    _CACHE[name] = surf
    return surf
