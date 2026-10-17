"""Pieces of the abandoned Route 12 sniper nest (0 scuff ellipse 48x24, 1 brass casing 8x6,
2 left-behind rifle 40x12), baked from ``missions.m2.draw._paint_nest_bit`` (live fallback).
Anchors: scuff (24, 8), casing (4, 3), rifle (20, 6) - see ``missions.m2.draw._NEST_BITS``.
"""
import pygame

VARIANTS = 3
VARIANT_NAMES = ("scuff", "casing", "rifle")
_SIZES = ((48, 24), (8, 6), (40, 12))
_ANCHORS = ((24, 8), (4, 3), (20, 6))
SIZE = _SIZES[0]
BAKE_DEPS = ("missions.m2.draw",)


def render(variant=0, scale=1):
    from missions.m2 import draw as D   # lazy: game modules only at bake / fallback time
    size = _SIZES[variant]
    surf = pygame.Surface(size, pygame.SRCALPHA)
    D._paint_nest_bit(surf, VARIANT_NAMES[variant], *_ANCHORS[variant])
    if scale != 1:
        surf = pygame.transform.scale(surf, (int(size[0] * scale), int(size[1] * scale)))
    return surf
