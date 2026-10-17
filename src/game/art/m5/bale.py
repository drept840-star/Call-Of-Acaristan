"""Strapped newspaper bundles seen from above (Print Works stacks/pallets).
One baked variant per footprint the map uses, with and without the black
"MAG" label: variant = size_index * 2 + (1 if labelled). Bundles are offset
by a fixed per-variant seed; top edges catch the upper-left key light.
Replaces decor_interior._bale (the drop shadow stays live)."""
import random

import pygame

from game.art.m5 import _kit as K

SIZES = ((56, 56), (71, 58), (45, 45), (58, 122))
VARIANTS = len(SIZES) * 2
PAPER = (214, 208, 190)
PAPER_D = (176, 170, 152)
INK = (24, 26, 34)
STRAP = (150, 40, 34)
MAG = (230, 190, 120)


def variant_for(w, h, label):
    """Variant for a (w, h) footprint, or None when it is not baked."""
    try:
        return SIZES.index((w, h)) * 2 + (1 if label and w > 40 else 0)
    except ValueError:
        return None


def render(variant=0, scale=1):
    si, lab = divmod(int(variant) % VARIANTS, 2)
    w, h = SIZES[si]
    rnd = random.Random(500 + si)
    s = K.new(w, h)
    pygame.draw.rect(s, PAPER_D, (0, 0, w, h))
    rows = max(1, h // 22)
    for i in range(rows):
        y = i * (h // rows)
        hh = h // rows - 2
        off = rnd.randint(-2, 2)
        b = pygame.Rect(2 + off, y + 1, w - 4, hh)
        pygame.draw.rect(s, PAPER, b)
        pygame.draw.line(s, (236, 232, 218), b.topleft, (b.right - 1, b.y))      # lit top edge
        pygame.draw.line(s, (236, 232, 218), b.topleft, (b.x, b.bottom - 1))     # lit left edge
        for k in range(3, b.h - 1, 4):                                         # page edges
            pygame.draw.line(s, PAPER_D, (b.x + 2, b.y + k), (b.right - 3, b.y + k))
        pygame.draw.rect(s, STRAP, (b.x + b.w // 3, b.y, 3, b.h))
        pygame.draw.rect(s, STRAP, (b.x + 2 * b.w // 3, b.y, 3, b.h))
        pygame.draw.rect(s, (120, 116, 104), b, 1)
    if lab and w > 40:
        pygame.draw.rect(s, INK, (6, 6, 26, 11))
        K.text(s, "MAG", 9, 8, MAG)
    return K.scaled(s, scale)
