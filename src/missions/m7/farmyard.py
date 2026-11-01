"""Mission 7 top-down farmyard.

Beat 2: the chores (generator, water, feed), then Bodi's goat rescue
(goat_rescue.py), which starts when the player talks to him.
Beat 4: defensive preparation using the same map.

Static scenery is baked once per begin(). Characters, animals, machinery,
and interactive changes are drawn each frame.

Controls:
    WASD / arrows: walk
    E: interact
    Space / Enter / E: advance dialogue

Minigame controls are shown on their cards.
"""

import math
import sys

import pygame

from core.config import (
    HEIGHT,
    WIDTH,
    audio as _audio_manager,
    font_prompt,
    font_terminal_small,
)
from core.state import STATE
from engine.core import now_ms as _now_ms
from entities.player import Player

from . import m7_audio as _m7_audio
from . import maps as M
from . import minigames as G
from .colonel import ColonelPaie
from .goat_rescue import GoatRescue
from .meta import MID_GOAT_ESCAPE


T = M.TILE
OX, OY = M.ORIGIN

CHORES = "chores"
PREP = "prep"
FARM_STAGES = (CHORES, PREP)
CHORES_NEEDED = ("generator", "water", "feed")
PREP_ITEMS = ("tractor", "shed", "loft")
PREP_PICKS = 2

CHAR_MS = 26
SPEED = 180.0

_S = {}
_RESCUE = None
_COLONEL = None          # easter egg: Colonel Paie the scarecrow

_TILES = {}
_TRACTOR_ROT = {}
_FIG_CACHE = {}
_GOAT_CACHE = {}
_PIG_CACHE = {}
_SHADOWS = {}

PX = 2
FW, FH, FCX, FBASE = 34, 28, 17, 24
GW, GH, GCX, GBASE = 28, 21, 12, 18
_CLEAR = (0, 0, 0, 0)

_LOOKS = {
    "biribel": dict(
        torso=(40, 42, 52),
        arm=(34, 36, 46),
        legs=(30, 32, 40),
        boots=(20, 20, 24),
        hair=(34, 26, 22),
        skin=(200, 156, 116),
        patch=(70, 120, 190),
    ),
    "bodi": dict(
        torso=(126, 72, 48),
        arm=(116, 66, 44),
        legs=(60, 74, 112),
        boots=(70, 56, 40),
        hair=(36, 30, 26),
        skin=(206, 164, 124),
        patch=None,
    ),
    "alex": dict(
        torso=(56, 96, 180),
        arm=(50, 88, 170),
        legs=(74, 88, 124),
        boots=(226, 226, 230),
        hair=(128, 90, 62),
        skin=(212, 172, 132),
        patch=None,
    ),
}

_GOATS = (
    ((10.9, 8.0), (226, 220, 206), 0.0),
    ((12.3, 8.2), (150, 146, 140), 2.1),
    ((13.0, 7.7), (142, 98, 66), 4.0),
)

_GUN = dict(
    metal=(46, 44, 46),
    steel=(118, 120, 128),
    wood=(128, 84, 48),
    wood_d=(86, 54, 32),
    wood_l=(160, 112, 70),
)

_BELT = (44, 34, 28)
_BUCKLE = (176, 156, 104)
_HORN = (176, 164, 140)
_LOOK_PHASE = {"biribel": 0, "bodi": 1300, "alex": 2600}


def _snd():
    return _m7_audio.instance(_audio_manager)


def _tone(col, factor, add=0):
    return tuple(
        max(0, min(255, int(v * factor + add))) for v in col
    )


def _rng(seed):
    value = seed & 0x7FFFFFFF
    while True:
        value = (value * 1103515245 + 12345) & 0x7FFFFFFF
        yield value >> 8


def _inside(c, r, box):
    return (
        box[0] <= c < box[0] + box[2]
        and box[1] <= r < box[1] + box[3]
    )


def _shadow(surface, rect, off=8, alpha=70):
    image = pygame.Surface(rect.size, pygame.SRCALPHA)
    image.fill((12, 10, 8, alpha))
    surface.blit(image, (rect.x + off, rect.y + off))


def _ellipse_shadow(surface, center, size, alpha=80):
    key = ("ellipse", size, alpha)
    image = _SHADOWS.get(key)
    if image is None:
        image = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.ellipse(
            image, (12, 10, 8, alpha), image.get_rect()
        )
        _SHADOWS[key] = image
    surface.blit(image, image.get_rect(center=center))


# -- static scenery --------------------------------------------------------

_PALETTES = {
    "grass": M.GRASS,
    "dirt": M.DIRT,
    "pen": M.PENDIRT,
    "track": M.TRACK,
    "hay": M.HAYFLOOR,
}


def _ground_kind(c, r, ch):
    if _inside(c, r, M.BARN_INSIDE) or (c, r) == (11, 3):
        return "hay"
    if _inside(c, r, M.PEN):
        return "pen"
    if ch == ":" or (r >= 8 and 6 <= c <= 8):
        return "track"
    if ch == "#" or (r <= 3 and not 6 <= c <= 8):
        return "grass"
    return "dirt"


def _ground_tile(kind, variant):
    key = (kind, variant)
    cached = _TILES.get(key)
    if cached is not None:
        return cached

    base, dark, light = _PALETTES[kind]
    tile = pygame.Surface((T, T))
    tile.fill(base)
    rnd = _rng(variant * 7919 + len(kind) * 131)

    for _ in range(5):
        x, y = next(rnd) % T, next(rnd) % T
        w = 8 + next(rnd) % 19
        h = 3 + next(rnd) % 8
        col = _tone(
            base, 0.96 if next(rnd) % 2 else 1.035
        )
        tile.fill(col, (x, y, w, h))

    for _ in range(19):
        x = next(rnd) % max(1, T - 10)
        y = next(rnd) % max(1, T - 10)
        col = dark if next(rnd) % 3 else light

        if kind == "grass":
            tile.fill(dark, (x + 2, y + 3, 5, 2))
            tile.fill(col, (x + 3, y, 2, 5))
            tile.fill(light, (x, y + 2, 2, 3))
            if next(rnd) % 15 == 0:
                tile.fill(
                    (211, 190, 112), (x + 3, y - 1, 2, 2)
                )
        elif kind == "hay":
            pygame.draw.line(
                tile, col, (x, y + 3), (x + 9, y), 2
            )
            if next(rnd) % 3 == 0:
                tile.fill(light, (x + 2, y + 5, 7, 1))
        else:
            tile.fill(
                col, (x, y, 3 + next(rnd) % 4, 2)
            )
            if next(rnd) % 4 == 0:
                tile.fill(
                    _tone(light, 0.95),
                    (x + 1, y - 1, 2, 1),
                )

    if kind == "track":
        for xx in (int(T * 0.23), int(T * 0.74)):
            tile.fill(dark, (xx, 0, 7, T))
            tile.fill(
                _tone(dark, 1.12), (xx + 1, 0, 2, T)
            )
            for yy in range(variant % 6, T, 10):
                pygame.draw.line(
                    tile, _tone(dark, 0.86),
                    (xx - 2, yy), (xx + 7, yy + 4), 2,
                )
    elif kind == "pen":
        for _ in range(3):
            x = next(rnd) % max(1, T - 8)
            y = next(rnd) % max(1, T - 6)
            tile.fill(dark, (x, y, 2, 3))
            tile.fill(dark, (x + 4, y, 2, 3))

    _TILES[key] = tile
    return tile


def _fence(surface, grid, c, r):
    x, y = c * T, r * T
    cx, cy = x + T // 2, y + T // 2

    def linked(cc, rr):
        return (
            0 <= rr < len(grid)
            and 0 <= cc < len(grid[rr])
            and grid[rr][cc] in "#f"
        )

    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if not linked(c + dx, r + dy):
            continue

        if dx:
            start = cx if dx > 0 else x
            surface.fill(
                (55, 44, 28),
                (start + 3, cy + 6, T // 2, 6),
            )
            surface.fill(
                M.WOOD_D, (start, cy - 5, T // 2, 10)
            )
            surface.fill(
                M.WOOD, (start, cy - 5, T // 2, 7)
            )
            surface.fill(
                M.WOOD_L, (start, cy - 5, T // 2, 2)
            )
        else:
            start = cy if dy > 0 else y
            surface.fill(
                (55, 44, 28),
                (cx + 5, start + 3, 6, T // 2),
            )
            surface.fill(
                M.WOOD_D, (cx - 5, start, 10, T // 2)
            )
            surface.fill(
                M.WOOD, (cx - 5, start, 7, T // 2)
            )
            surface.fill(
                M.WOOD_L, (cx - 5, start, 2, T // 2)
            )

    surface.fill(M.INK, (cx - 7, cy - 8, 14, 16))
    surface.fill(M.WOOD, (cx - 5, cy - 6, 10, 12))
    surface.fill(M.WOOD_L, (cx - 5, cy - 6, 10, 3))
    surface.fill(M.WOOD_D, (cx + 2, cy - 2, 3, 8))
    surface.fill(M.METAL_D, (cx - 1, cy - 1, 2, 2))


def _house(surface):
    c, r, w, h = M.HOUSE
    box = pygame.Rect(c * T, r * T, w * T, h * T)
    _shadow(surface, box, 10)
    pygame.draw.rect(surface, M.INK, box)

    wall = pygame.Rect(
        box.x + 4, box.bottom - 22, box.w - 8, 18
    )
    surface.fill((198, 181, 146), wall)
    surface.fill(
        (224, 207, 171), (wall.x, wall.y, wall.w, 4)
    )
    surface.fill(
        (137, 120, 96),
        (wall.x, wall.bottom - 4, wall.w, 4),
    )

    roof = pygame.Rect(
        box.x + 4, box.y + 4, box.w - 8, box.h - 26
    )
    surface.fill(M.ROOF, roof)
    ridge = roof.centery
    surface.fill(
        _tone(M.ROOF, 0.86),
        (roof.x, ridge, roof.w, roof.bottom - ridge),
    )
    for row, yy in enumerate(range(roof.y + 8, roof.bottom, 13)):
        surface.fill(M.ROOF_D, (roof.x, yy, roof.w, 2))
        offset = 0 if row % 2 else 14
        for xx in range(roof.x + offset, roof.right - 2, 28):
            surface.fill(
                _tone(M.ROOF_D, 1.1), (xx, yy - 9, 2, 9)
            )
    surface.fill(
        M.ROOF_D, (roof.x, ridge + 3, roof.w, 4)
    )
    surface.fill(
        M.ROOF_L, (roof.x, ridge - 3, roof.w, 5)
    )
    surface.fill(
        _tone(M.ROOF_L, 1.1),
        (roof.x, ridge - 3, roof.w, 1),
    )

    chimney = pygame.Rect(
        roof.right - 48, roof.y + 12, 26, 30
    )
    _shadow(surface, chimney, 5)
    surface.fill(M.STONE_D, chimney)
    surface.fill(M.STONE, chimney.inflate(-4, -4))
    for yy in range(chimney.y + 7, chimney.bottom - 3, 7):
        surface.fill(
            M.STONE_D, (chimney.x + 2, yy, 22, 2)
        )
    surface.fill(
        M.INK, (chimney.x + 6, chimney.y + 4, 14, 9)
    )
    surface.fill(
        (50, 43, 39),
        (chimney.x + 8, chimney.y + 6, 10, 5),
    )

    for col in (2, 3, 5):
        window = pygame.Rect(
            col * T + 23, wall.y + 4, 20, 10
        )
        surface.fill(M.WOOD_D, window.inflate(4, 4))
        surface.fill((68, 100, 119), window)
        surface.fill(
            (144, 177, 178),
            (window.x + 2, window.y + 1, 6, 3),
        )
        surface.fill(
            (214, 200, 160),
            (window.centerx - 1, window.y, 2, 10),
        )

    surface.fill(M.INK, (4 * T + 13, wall.y - 2, 38, 20))
    surface.fill(M.WOOD, (4 * T + 16, wall.y, 32, 18))
    surface.fill(
        M.WOOD_L, (4 * T + 18, wall.y + 2, 2, 14)
    )
    surface.fill(
        M.WOOD_D, (4 * T + 31, wall.y + 2, 2, 16)
    )
    surface.fill(
        (222, 191, 92),
        (4 * T + 42, wall.y + 10, 3, 3),
    )

    porch = pygame.Rect(3 * T, 4 * T, 3 * T, 28)
    surface.fill(M.WOOD_D, porch)
    for i, xx in enumerate(range(porch.x, porch.right, 16)):
        surface.fill(
            M.WOOD if i % 2 else M.WOOD_L,
            (xx + 1, porch.y, 14, 25),
        )
        for yy in (porch.y + 4, porch.y + 20):
            surface.fill(M.WOOD_D, (xx + 6, yy, 2, 2))
    surface.fill(
        M.INK, (porch.x, porch.bottom - 2, porch.w, 2)
    )
    surface.fill(
        (76, 63, 43), (4 * T + 14, 4 * T + 5, 38, 15)
    )
    for xx in (3 * T + 18, 3 * T + 29):
        surface.fill(M.INK, (xx, 4 * T + 8, 8, 12))
        surface.fill(
            (72, 53, 36), (xx + 1, 4 * T + 8, 6, 9)
        )


def _barn(surface, grid):
    c, r, w, h = M.BARN
    box = pygame.Rect(c * T, r * T, w * T, h * T)
    _shadow(surface, box, 10)

    for rr, row in enumerate(grid):
        for cc, ch in enumerate(row):
            if ch != "B":
                continue
            x, y = cc * T, rr * T
            surface.fill(M.BARN_WALL, (x, y, T, T))
            for i in range(0, T, 12):
                surface.fill(
                    (83, 42, 35), (x + i, y, 2, T)
                )
                surface.fill(
                    (145, 79, 61), (x + i + 2, y, 2, T)
                )
            surface.fill((166, 99, 72), (x, y, T, 4))
            surface.fill(
                (66, 35, 30), (x, y + T - 8, T, 8)
            )
            surface.fill(
                (108, 62, 49),
                (x + 3, y + T - 7, T - 6, 2),
            )

    pygame.draw.rect(surface, M.INK, box, 3)
    ic, ir, iw, ih = M.BARN_INSIDE
    inner = pygame.Rect(ic * T, ir * T, iw * T, ih * T)
    pygame.draw.rect(
        surface, (61, 35, 27), inner.inflate(6, 6), 4
    )

    for xx in (inner.left - 6, inner.right - 2):
        surface.fill(
            M.WOOD_D, (xx, inner.top - 4, 8, inner.h + 8)
        )
        surface.fill(
            M.WOOD_L, (xx, inner.top - 4, 2, inner.h + 8)
        )
    surface.fill(
        M.WOOD_D, (inner.x, inner.y - 5, inner.w, 9)
    )
    surface.fill(
        M.WOOD, (inner.x, inner.y - 5, inner.w, 4)
    )

    for xx in (11 * T - 6, 12 * T - 2):
        surface.fill(M.INK, (xx - 1, 3 * T, 10, T))
        surface.fill(M.WOOD, (xx + 1, 3 * T, 6, T))
        surface.fill(M.WOOD_L, (xx + 1, 3 * T, 2, T))
    surface.fill(M.WOOD_D, (11 * T, 4 * T - 5, T, 5))

    for i in range(3):
        bale = pygame.Rect(
            10 * T + 8 + i * 15, T + 9, 14, 25
        )
        surface.fill(M.HAYFLOOR[1], bale)
        surface.fill(M.HAYFLOOR[0], bale.inflate(-2, -2))
        surface.fill(
            M.HAYFLOOR[2],
            (bale.x + 2, bale.y + 2, 9, 3),
        )
        surface.fill(
            (133, 101, 47),
            (bale.centerx, bale.y + 1, 2, bale.h - 2),
        )
    surface.fill(
        M.WOOD_D, (10 * T + 4, T + 38, 54, 5)
    )

    sign = pygame.Rect(
        box.x + 12, box.y + 16, min(44, T - 20), 20
    )
    surface.fill(M.WOOD_D, sign.inflate(4, 4))
    surface.fill((211, 190, 143), sign)
    surface.fill(
        (113, 84, 53),
        (sign.x + 5, sign.y + 6, sign.w - 10, 2),
    )
    surface.fill(
        (113, 84, 53),
        (sign.x + 9, sign.y + 11, sign.w - 18, 2),
    )


def _well(surface):
    cx, cy = M.tile_px(M.POINTS["well"]["at"])
    _ellipse_shadow(surface, (cx + 5, cy + 9), (72, 50))
    pygame.draw.circle(surface, M.INK, (cx, cy), 31)
    pygame.draw.circle(surface, M.STONE_D, (cx, cy), 28)
    pygame.draw.circle(surface, M.STONE, (cx, cy - 2), 27)
    pygame.draw.circle(surface, M.INK, (cx, cy - 2), 20)
    pygame.draw.circle(surface, M.WATER, (cx, cy - 2), 16)

    for i in range(10):
        a = i * math.tau / 10
        p0 = (
            cx + int(math.cos(a) * 21),
            cy - 2 + int(math.sin(a) * 21),
        )
        p1 = (
            cx + int(math.cos(a) * 28),
            cy - 2 + int(math.sin(a) * 28),
        )
        pygame.draw.line(surface, M.STONE_D, p0, p1, 2)

    surface.fill((136, 174, 193), (cx - 9, cy - 10, 11, 2))
    surface.fill((103, 144, 173), (cx + 3, cy + 2, 7, 2))
    for xx in (cx - 34, cx + 26):
        surface.fill(M.INK, (xx - 1, cy - 9, 10, 18))
        surface.fill(M.WOOD, (xx + 1, cy - 8, 6, 16))
        surface.fill(M.WOOD_L, (xx + 1, cy - 8, 2, 13))
    surface.fill(M.WOOD_D, (cx - 29, cy - 4, 59, 7))
    surface.fill(M.WOOD_L, (cx - 29, cy - 4, 59, 2))
    for xx in range(cx - 4, cx + 5, 3):
        surface.fill((187, 165, 118), (xx, cy - 6, 2, 11))
    surface.fill((174, 151, 103), (cx + 1, cy + 4, 2, 11))


def _shed(surface):
    box = pygame.Rect(T, 7 * T, 3 * T, T)
    _shadow(surface, box, 8)
    surface.fill(M.INK, box)
    surface.fill(
        M.WOOD_D, (box.x + 3, box.bottom - 12, box.w - 6, 9)
    )
    roof = pygame.Rect(
        box.x + 3, box.y + 3, box.w - 6, box.h - 14
    )
    surface.fill(M.METAL, roof)
    for i, xx in enumerate(range(roof.x + 3, roof.right, 13)):
        surface.fill(M.METAL_D, (xx, roof.y, 3, roof.h))
        surface.fill(
            _tone(M.METAL, 1.25),
            (xx + 3, roof.y, 1, roof.h),
        )
        if i % 4 == 0:
            surface.fill(
                (130, 82, 51),
                (xx + 5, roof.bottom - 17, 5, 12),
            )
    surface.fill(
        _tone(M.METAL, 1.2), (roof.x, roof.y, roof.w, 3)
    )
    surface.fill(
        M.METAL_D, (roof.x, roof.bottom - 3, roof.w, 3)
    )

    for bx in (T + 18, T + 46):
        by = 8 * T + 16
        _ellipse_shadow(surface, (bx + 3, by + 5), (31, 24))
        pygame.draw.circle(surface, M.INK, (bx, by), 14)
        pygame.draw.circle(surface, (151, 48, 35), (bx, by), 12)
        pygame.draw.circle(
            surface, (195, 73, 45), (bx - 1, by - 2), 10, 2
        )
        pygame.draw.circle(surface, (101, 38, 29), (bx, by), 6)
        pygame.draw.circle(
            surface, M.METAL_D, (bx + 5, by - 5), 3
        )
        surface.fill((218, 178, 94), (bx - 4, by + 2, 8, 4))


def _bin(surface):
    cx, cy = M.tile_px(M.POINTS["bin"]["at"])
    x, y = cx - T // 2, cy - T // 2
    _shadow(surface, pygame.Rect(x + 6, y + 10, 52, 44), 5)
    surface.fill(M.INK, (x + 5, y + 9, 54, 46))
    surface.fill(M.WOOD, (x + 7, y + 11, 50, 42))
    surface.fill(M.WOOD_D, (x + 11, y + 15, 42, 34))
    surface.fill(M.GRAIN, (x + 13, y + 17, 38, 30))

    rnd = _rng(441)
    for _ in range(35):
        xx = x + 15 + next(rnd) % 34
        yy = y + 19 + next(rnd) % 25
        surface.fill(
            M.HAYFLOOR[2] if next(rnd) % 2 else (160, 127, 64),
            (xx, yy, 3, 1),
        )

    surface.fill(M.WOOD_L, (x + 7, y + 11, 50, 4))
    surface.fill(M.WOOD_D, (x + 7, y + 46, 50, 4))
    for xx in (x + 8, x + 51):
        surface.fill(M.METAL_D, (xx, y + 12, 4, 39))
        surface.fill(M.METAL, (xx + 1, y + 16, 2, 2))
        surface.fill(M.METAL, (xx + 1, y + 43, 2, 2))


def _bike(surface):
    cx, cy = M.tile_px(M.BIKE_AT)
    _shadow(surface, pygame.Rect(cx - 7, cy - 26, 14, 52), 4)
    for wy in (-27, 15):
        surface.fill(M.INK, (cx - 5, cy + wy, 10, 13))
        surface.fill(
            (74, 74, 80), (cx - 3, cy + wy + 1, 6, 11)
        )
        for yy in range(cy + wy + 2, cy + wy + 12, 4):
            surface.fill((32, 32, 36), (cx - 4, yy, 8, 2))

    surface.fill(M.INK, (cx - 7, cy - 14, 14, 30))
    surface.fill((232, 112, 30), (cx - 5, cy - 11, 10, 14))
    surface.fill((255, 167, 62), (cx - 4, cy - 10, 3, 10))
    surface.fill((38, 34, 34), (cx - 4, cy + 4, 8, 11))
    surface.fill(M.METAL, (cx - 13, cy - 19, 26, 3))
    surface.fill(M.INK, (cx - 13, cy - 19, 3, 3))
    surface.fill(M.INK, (cx + 10, cy - 19, 3, 3))
    surface.fill((228, 214, 165), (cx - 4, cy - 23, 8, 4))


def _pig_home():
    c, r, w, h = M.PEN
    return (c + w * 0.43) * T, (r + h * 0.68) * T


def _mud_patch(surface):
    cx, cy = _pig_home()
    rnd = _rng(9203)
    for i in range(9):
        x = int(cx - 37 + next(rnd) % 50)
        y = int(cy - 15 + next(rnd) % 25)
        col = (105, 79, 54) if i % 2 else (116, 88, 60)
        pygame.draw.ellipse(surface, col, (x, y, 25, 11))
    pygame.draw.ellipse(
        surface, (133, 107, 75),
        (int(cx - 15), int(cy - 2), 22, 6),
    )
    surface.fill(
        (155, 127, 87), (int(cx - 10), int(cy), 10, 2)
    )


def _build_static(grid, stage, fence_grid=None, skip_fence=()):
    """Bake scenery, optionally using separate fence connectivity.

    grid:
        Gameplay and ground grid.
    fence_grid:
        Optional visual connectivity grid. This lets neighboring fence
        tiles connect to a section that is drawn dynamically.
    skip_fence:
        Fence tile coordinates whose own art must not be baked.
    """
    surface = pygame.Surface((M.COLS * T, M.ROWS * T))

    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            kind = _ground_kind(c, r, ch)
            surface.blit(
                _ground_tile(kind, (c * 3 + r * 5) % 6),
                (c * T, r * T),
            )

    _mud_patch(surface)

    links = grid if fence_grid is None else fence_grid
    skipped = set(skip_fence)
    for r, row in enumerate(links):
        for c, ch in enumerate(row):
            if ch in "#f" and (c, r) not in skipped:
                _fence(surface, links, c, r)

    _house(surface)
    _barn(surface, grid)
    _well(surface)
    _shed(surface)
    _bin(surface)
    if stage == PREP:
        _bike(surface)

    return surface


# -- state -----------------------------------------------------------------

def _bodi_tile():
    if "loft" in _S["preps"]:
        return M.LOFT_TILE
    return (
        (4.5, 5.5)
        if _S["stage"] == PREP else M.BODI_TILE
    )


def _make_walls():
    moved = "tractor" in _S["preps"]
    walls = [
        pygame.Rect(c * T, r * T, T, T)
        for r, row in enumerate(_S["grid"])
        for c, ch in enumerate(row)
        if ch in M.SOLID and not (moved and ch == "T")
    ]

    bx, by = M.tile_px(_bodi_tile())
    walls.append(pygame.Rect(bx - 14, by - 6, 28, 22))

    if _S["stage"] == PREP:
        ax, ay = M.tile_px(M.ALEX_TILE)
        walls.append(pygame.Rect(ax - 14, ay - 6, 28, 22))
        kx, ky = M.tile_px(M.BIKE_AT)
        walls.append(pygame.Rect(kx - 10, ky - 28, 20, 56))

    if moved:
        walls.append(
            pygame.Rect(
                6 * T, M.TRACTOR_PARK[1] + 10, 3 * T, 44
            )
        )

    # Easter egg: the scarecrow's post is solid (map pixels, like the rest).
    if _COLONEL is not None:
        walls.append(_COLONEL.map_rect())

    STATE.walls = walls


def begin(stage, on_done):
    global _RESCUE, _COLONEL
    _RESCUE = None

    if stage not in FARM_STAGES:
        raise ValueError("Unknown farm stage: %r" % (stage,))

    now = _now_ms()
    grid = M.farm_grid()

    STATE.enemies = []
    STATE.bullets = []
    STATE.particles = []
    STATE.doors = []

    # Mission 7 farmyard hands the player a sidearm, not the mission weapons.
    # Until Alex dispatches the raid, the player is not allowed to shoot,
    # melee, throw bottles, reload, or switch away from the sidearm.
    STATE.weapons_locked = True
    STATE.thrown_bottles.clear()
    STATE.is_reloading = False
    STATE.reload_timer = 0

    # Colonel Paie: fresh on a new CHORES start, kept across CHORES -> PREP
    # so his dialogue progress survives.
    if stage == CHORES or _COLONEL is None:
        _COLONEL = ColonelPaie(M, _say_colonel, _toast)

    px, py = M.tile_px(M.PLAYER_TILE)
    STATE.player = Player(px - 16, py - 16)
    STATE.camera_x = 0
    STATE.camera_y = 0
    STATE.m7_preps = []
    prepared = stage == PREP
    _S.clear()
    _S.update(
        stage=stage,
        on_done=on_done,
        grid=grid,
        static=_build_static(grid, stage),
        now=now,
        last_update=now,
        pos=pygame.Vector2(STATE.player.rect.topleft),
        done=set(CHORES_NEEDED) if prepared else set(),
        carry=None,
        gen_on=prepared,
        genplay=None,
        drive=None,
        trough={"water": prepared, "feed": prepared},
        crate=prepared and bool(getattr(STATE, "m7_crate", False)),
        lines=[],
        line_t0=0,
        after=None,
        toast=("", 0),
        prev_adv=False,
        face="d",
        step=0.0,
        moving=False,
        near=None,
        finished=False,
        escape_shown=False,
        preps=[],
        tick_n=0,
        life_t=now,
        life_i=0,
        life_gap=5000,
        step_ph=0,
    )

    _make_walls()

    if prepared:
        _snd().start_loop("m7_gen_idle", 0.20)
        _say([
            (
                "",
                "Two Guard trucks on the valley road, "
                "trailing dust up the hill.",
            ),
            (
                "ALEX",
                "Twenty minutes, maybe less. "
                "Whatever you're doing, do it fast.",
            ),
            (
                "BODI",
                "The farm can spare two things. Choose well.",
            ),
        ])


def _start_rescue():
    """Beat 2b: once the chores are done, Bodi's talk turns into the goat hunt."""
    global _RESCUE
    if _RESCUE is None and _S and not _S["finished"]:
        _S["moving"] = False
        _RESCUE = GoatRescue(sys.modules[__name__])


def active():
    return bool(_S)


def _toast(text, ms=2800):
    _S["toast"] = (text, _now_ms() + ms)


def _say(lines, after=None):
    _S["lines"] = list(lines)
    _S["line_t0"] = _now_ms()
    _S["tick_n"] = 0
    _S["after"] = after
    _S["moving"] = False


def _say_colonel(lines):
    """Adapter: colonel.py uses (speaker|None, text); this file uses
    ("", text) for narration and UPPERCASE speaker names."""
    _say([((who or "").upper(), text) for who, text in lines])


def _advance_line():
    if not _S or not _S["lines"]:
        return
    now = _now_ms()
    text = _S["lines"][0][1]
    if (now - _S["line_t0"]) // CHAR_MS < len(text):
        _S["line_t0"] = now - len(text) * CHAR_MS - 1
        return

    _S["lines"].pop(0)
    _S["line_t0"] = now
    _S["tick_n"] = 0

    if not _S["lines"]:
        after = _S["after"]
        _S["after"] = None
        if after:
            after()


def _finish():
    if not _S or _S["finished"]:
        return
    _S["finished"] = True
    _S["moving"] = False
    # The farmyard is handing control back to the combat / raid context.
    # Re-enable mission weapons exactly once, at the end of the whole farm
    # section (chores, goat rescue, prep), not between stages.
    STATE.weapons_locked = False
    _S["on_done"]()


def _chores_done():
    return all(k in _S["done"] for k in CHORES_NEEDED)


def _chores_complete():
    """The last chore landed: play the escape before handing control back.

    The film is requested once; the app consumes the request on the next
    frame and returns through ``after_goat_escape`` without advancing the
    stage ladder.
    """
    if (
        not _S
        or _RESCUE is not None
        or _S["escape_shown"]
        or not _chores_done()
    ):
        return False
    _S["escape_shown"] = True
    _S["lines"] = []
    _S["after"] = None
    _S["moving"] = False
    STATE.request_m7_cutscene = MID_GOAT_ESCAPE
    return True


def after_goat_escape():
    """The escape film ended: the farm resumes with Bodi waiting."""
    if not _S or _S["finished"]:
        return
    _S["last_update"] = _now_ms()
    _S["moving"] = False
    _toast("Chores done. Bodi is waiting.", 3600)


def _teleport(tile):
    STATE.player.rect.center = M.tile_px(tile)
    _S["pos"] = pygame.Vector2(STATE.player.rect.topleft)
    _S["moving"] = False
    _S["near"] = None


# -- interaction -----------------------------------------------------------

def _point_px(pid):
    if pid == "bodi":
        return M.tile_px(_bodi_tile())
    if pid == "alex":
        return M.tile_px(M.ALEX_TILE)
    return M.tile_px(M.POINTS[pid]["at"])


def _reach(pid):
    return (
        70 if pid in ("bodi", "alex")
        else M.POINTS[pid]["reach"]
    )


def _preps_open():
    if len(_S["preps"]) >= PREP_PICKS:
        return []
    return [k for k in PREP_ITEMS if k not in _S["preps"]]


def _available():
    if _S["stage"] == PREP:
        picks = _preps_open()
        out = [
            ("alex", "TALK TO ALEX"),
            (
                "bodi",
                "SEND BODI TO THE HAYLOFT"
                if "loft" in picks else "TALK",
            ),
        ]
        if "tractor" in picks:
            out.append(("tractor", "BLOCK THE TRACK"))
        if "shed" in picks:
            out.append(("shed", "RIG THE FUEL SHED"))
        out.append(("colonel", "LOOK AT THE SCARECROW"))
        return out

    out = [("bodi", "TALK")]
    if not _S["gen_on"]:
        out.append(("generator", "START THE GENERATOR"))
    if "water" not in _S["done"] and _S["carry"] is None:
        out.append(("well", "DRAW WATER"))
    if "feed" not in _S["done"] and _S["carry"] is None:
        out.append(("bin", "TAKE FEED"))
    if _S["carry"]:
        out.append(("trough", "FILL THE TROUGH"))
    if not _S["crate"]:
        out.append(("hay", "SEARCH THE HAY"))
    out.append(("porch", "LOOK"))
    out.append(("colonel", "LOOK AT THE SCARECROW"))
    return out


def _nearest():
    px, py = STATE.player.rect.center
    best = None
    best_distance = float("inf")
    for pid, label in _available():
        x, y = _point_px(pid)
        reach = _reach(pid)
        distance = math.hypot(px - x, py - y)
        if distance <= reach and distance < best_distance:
            best = (pid, label)
            best_distance = distance
    return best


def _h_generator():
    _S["genplay"] = G.GenPuzzle(_now_ms())
    _S["moving"] = False
    _toast(
        "Bodi: Three pumps. Then give the cord a proper pull.",
        3600,
    )


def _gen_sound(event):
    snd = _snd()
    if event in ("prime", "cord"):
        snd.gen_pull()
    elif event in ("primed", "pull_weak"):
        snd.gen_cough()
    elif event == "pull_ok":
        snd.gen_pull()
    elif event == "pull_miss":
        snd.gen_backfire()
    elif event == "run":
        snd.gen_catch()


def _h_well():
    _S["carry"] = "water"
    _snd().well()
    _toast("You haul a bucket up from the well.")


def _h_bin():
    _S["carry"] = "feed"
    _snd().grain()
    _toast("A scoop of grain from the bin.")


def _h_trough():
    kind = _S["carry"]
    if kind is None:
        return
    _S["trough"][kind] = True
    _S["carry"] = None
    _S["done"].add(kind)
    _snd().pour()
    _snd().bucket()
    _toast(
        "Water in the trough."
        if kind == "water" else "Grain in the trough."
    )
    _chores_complete()


def _h_hay():
    _S["crate"] = True
    STATE.m7_crate = True
    _snd().hay()
    _snd().crate()
    _say([
        ("", "Under the hay: a crate of rifle magazines."),
        (
            "",
            "Behind it, a photograph. Bodi and Maru "
            "in uniform, years younger.",
        ),
    ])


def _h_porch():
    _snd().door()
    _toast("The porch. Boots by the door, a kettle gone cold.")


def _picked(kind):
    if kind not in _preps_open():
        return False
    _S["preps"].append(kind)
    STATE.m7_preps = list(_S["preps"])
    _make_walls()

    _S["near"] = None
    if len(_S["preps"]) >= PREP_PICKS:
        _toast(
            "Two jobs done. Talk to Alex when you are ready.",
            3400,
        )
    return True


def _h_tractor():
    _S["drive"] = G.TractorPuzzle(
        M.tractor_route_px(), _now_ms()
    )
    _S["moving"] = False
    _snd().trac_idle()
    _toast(
        "Hold the shown control. Ease off before each stop.",
        3400,
    )


def _finish_tractor():
    puzzle = _S["drive"]
    smooth = puzzle.smooth
    total = len(puzzle.route)
    _picked("tractor")
    _teleport((6.0, 7.0))
    _S["drive"] = None

    if smooth == total:
        line = (
            "You set the brake. A perfect bit of parking. "
            "The track is blocked."
        )
    else:
        line = (
            "You set the brake and climb down. "
            "The track is blocked."
        )
    _say([("", line)])


def _h_shed():
    if not _picked("shed"):
        return
    _snd().crate()
    _snd().fence_creak()
    _say([
        (
            "",
            "You loosen the drum caps and string a wire to the door. "
            "One spark and the shed goes up.",
        ),
    ])


def _h_loft():
    if not _picked("loft"):
        return
    _say([
        ("BODI", "The hayloft. Long sight over the whole yard."),
        ("BODI", "Don't make me waste the shots."),
    ])


def _h_alex():
    if len(_S["preps"]) >= PREP_PICKS:
        _say(
            [
                ("ALEX", "Dust on the road. Here they come."),
                (
                    "ALEX",
                    "Try not to get shot, Biribel. "
                    "It would be embarrassing for both of us.",
                ),
            ],
            after=_finish,
        )
    else:
        _say([("ALEX", "Pick two! The road is running out.")])


def _h_colonel():
    if _COLONEL is not None:
        _COLONEL.interact()


def _h_bodi():
    if _S["stage"] == PREP:
        if "loft" in _S["preps"]:
            _say([("BODI", "Up here. Go on, I have the yard.")])
        elif "loft" in _preps_open():
            _h_loft()
        else:
            _say([
                (
                    "BODI",
                    "I'll stay on the ground. "
                    "Somebody has to watch the pigs.",
                ),
            ])
    elif _chores_done():
        _say(
            [("BODI", "I grow potatoes. I don't do politics.")],
            after=_start_rescue,
        )
    else:
        _say([
            ("BODI", "Generator, well, feed bin. Then we talk."),
        ])


_HANDLERS = {
    "generator": _h_generator,
    "well": _h_well,
    "bin": _h_bin,
    "trough": _h_trough,
    "hay": _h_hay,
    "porch": _h_porch,
    "bodi": _h_bodi,
    "tractor": _h_tractor,
    "shed": _h_shed,
    "alex": _h_alex,
    "colonel": _h_colonel,
}


def interact():
    if not _S or _S["finished"]:
        return False
    if _RESCUE is not None:
        return _RESCUE.interact()
    if _S["genplay"] is not None or _S["drive"] is not None:
        return True
    if _S["lines"]:
        _advance_line()
        return True

    near = _nearest()
    _S["near"] = near
    if near is None:
        return False
    _HANDLERS[near[0]]()
    return True


# -- update ----------------------------------------------------------------

_DRIVE_KEYS = (
    ("w", pygame.K_w, pygame.K_UP),
    ("a", pygame.K_a, pygame.K_LEFT),
    ("s", pygame.K_s, pygame.K_DOWN),
    ("d", pygame.K_d, pygame.K_RIGHT),
)


def _down(keys, code):
    try:
        return bool(keys[code])
    except (IndexError, KeyError, TypeError):
        return False


def _drive_frame(keys, puzzle, now):
    held = {
        name for name, code, alternate in _DRIVE_KEYS
        if _down(keys, code) or _down(keys, alternate)
    }
    brake = (
        _down(keys, pygame.K_SPACE)
        or _down(keys, pygame.K_e)
    )
    puzzle.set_input(held, brake, now)
    snd = _snd()

    for event in puzzle.take_events():
        if event == "drive":
            snd.trac_rev()
            snd.trac_move()
        elif event == "arrive":
            snd.trac_still()
        elif event == "smooth":
            snd.chock()
        elif event == "bump":
            snd.gen_cough()
        elif event == "stall":
            snd.trac_still()
            snd.trac_stall()
        elif event == "park":
            snd.trac_off()
            snd.chock()
            _finish_tractor()


def _move_player(keys, dt):
    dx = int(
        _down(keys, pygame.K_d)
        or _down(keys, pygame.K_RIGHT)
    )
    dx -= int(
        _down(keys, pygame.K_a)
        or _down(keys, pygame.K_LEFT)
    )
    dy = int(
        _down(keys, pygame.K_s)
        or _down(keys, pygame.K_DOWN)
    )
    dy -= int(
        _down(keys, pygame.K_w)
        or _down(keys, pygame.K_UP)
    )

    direction = pygame.Vector2(dx, dy)
    if direction.length_squared() > 1:
        direction.normalize_ip()

    player = STATE.player
    rect = player.rect
    old = pygame.Vector2(rect.topleft)
    pos = _S["pos"]

    if (
        abs(rect.x - round(pos.x)) > 1
        or abs(rect.y - round(pos.y)) > 1
    ):
        pos.update(rect.topleft)

    if dx:
        pos.x += direction.x * SPEED * dt
        rect.x = round(pos.x)
        for wall in STATE.walls:
            if rect.colliderect(wall):
                rect.x = (
                    wall.left - rect.w if dx > 0 else wall.right
                )
                pos.x = rect.x

    if dy:
        pos.y += direction.y * SPEED * dt
        rect.y = round(pos.y)
        for wall in STATE.walls:
            if rect.colliderect(wall):
                rect.y = (
                    wall.top - rect.h if dy > 0 else wall.bottom
                )
                pos.y = rect.y

    bounds = pygame.Rect(0, 0, M.COLS * T, M.ROWS * T)
    clamped = rect.clamp(bounds)
    if clamped.x != rect.x:
        rect.x = clamped.x
        pos.x = rect.x
    if clamped.y != rect.y:
        rect.y = clamped.y
        pos.y = rect.y

    travelled = (pygame.Vector2(rect.topleft) - old).length()
    _S["moving"] = travelled > 0

    if dx or dy:
        _S["face"] = (
            ("r" if dx > 0 else "l")
            if abs(dx) > abs(dy)
            else ("d" if dy > 0 else "u")
        )
        player.angle = math.atan2(dy, dx)

    if travelled:
        _S["step"] += travelled * 0.0733
        phase = int(_S["step"] / math.pi)
        if phase != _S["step_ph"]:
            _S["step_ph"] = phase
            _snd().step(phase)


def update(keys):
    if not _S or keys is None:
        return (0, 0)
    if _RESCUE is not None:
        return _RESCUE.update(keys)

    now = _now_ms()
    dt = max(
        0.0, min(0.05, (now - _S["last_update"]) / 1000.0)
    )
    _S["last_update"] = now
    _S["now"] = now

    advance = (
        _down(keys, pygame.K_SPACE)
        or _down(keys, pygame.K_RETURN)
    )
    fresh_advance = advance and not _S["prev_adv"]
    _S["prev_adv"] = advance

    if fresh_advance and _S["lines"]:
        _advance_line()
        return (0, 0)

    if _S["lines"] or _S["finished"]:
        _S["moving"] = False
        return (0, 0)

    puzzle = _S["genplay"]
    if puzzle is not None:
        _S["moving"] = False
        puzzle.set_input(_down(keys, pygame.K_e), now)
        for event in puzzle.take_events():
            _gen_sound(event)
        if puzzle.done:
            _S["gen_on"] = True
            _S["done"].add("generator")
            _S["genplay"] = None
            _snd().start_loop("m7_gen_idle", 0.20)
            _toast(
                "There she goes! "
                "The generator settles into a steady thud.",
                3400,
            )
            _chores_complete()
        _wildlife(now)
        return (0, 0)

    if _S["drive"] is not None:
        _S["moving"] = False
        _drive_frame(keys, _S["drive"], now)
        return (0, 0)

    _move_player(keys, dt)
    _S["near"] = _nearest()
    _wildlife(now)
    return (0, 0)


def _wildlife(now):
    if now - _S["life_t"] < _S["life_gap"]:
        return
    index = _S["life_i"]
    if index % 3 == 0:
        _snd().bird()
    elif index % 3 == 1:
        _snd().goat()
    else:
        _snd().hen()
    _S["life_i"] = index + 1
    _S["life_t"] = now
    _S["life_gap"] = 6000 + now % 5000


# -- pixel characters ------------------------------------------------------

def _pal(look):
    palette = {}
    for name, col in _LOOKS[look].items():
        if col is not None:
            palette[name] = col
            palette[name + "_l"] = _tone(col, 1.2, 24)
            palette[name + "_d"] = _tone(col, 0.66)
    return palette


def _ink_scaled(canvas):
    mask = pygame.mask.from_surface(canvas, 1)
    ink = mask.to_surface(
        setcolor=M.INK + (255,), unsetcolor=_CLEAR
    )
    output = pygame.Surface(
        canvas.get_size(), pygame.SRCALPHA
    )
    for offset in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        output.blit(ink, offset)
    output.blit(canvas, (0, 0))
    w, h = canvas.get_size()
    return pygame.transform.scale(output, (w * PX, h * PX))


def _drop_shadow(w, h):
    key = ("pixel", w, h)
    image = _SHADOWS.get(key)
    if image is None:
        small = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(
            small, (14, 12, 10, 92), small.get_rect()
        )
        image = pygame.transform.scale(small, (w * PX, h * PX))
        _SHADOWS[key] = image
    return image


def _paint_gun(canvas, face, ty):
    g, cx = _GUN, FCX
    sign = -1 if face == "l" else 1

    def s(dx, yy, w, h, col):
        x = cx + dx if sign > 0 else cx - dx - w
        canvas.fill(col, (x, yy, w, h))

    if face in "lr":
        s(-4, ty + 2, 4, 2, g["wood"])
        s(-4, ty + 3, 4, 1, g["wood_d"])
        s(0, ty + 2, 4, 2, g["metal"])
        s(0, ty + 2, 4, 1, g["steel"])
        s(4, ty + 2, 8, 1, g["metal"])
        s(11, ty + 2, 1, 1, g["steel"])
        s(4, ty + 3, 3, 1, g["wood"])
    elif face == "u":
        canvas.fill(g["metal"], (cx + 4, ty - 9, 2, 12))
        canvas.fill(g["steel"], (cx + 4, ty - 9, 1, 12))
        canvas.fill(g["wood"], (cx + 4, ty + 3, 2, 4))
    else:
        canvas.fill(g["wood"], (cx + 1, ty + 1, 3, 3))
        canvas.fill(g["wood_l"], (cx + 1, ty + 1, 1, 2))
        canvas.fill(g["wood_d"], (cx + 3, ty + 1, 1, 3))
        canvas.fill(g["metal"], (cx + 1, ty + 4, 3, 2))
        canvas.fill(g["steel"], (cx + 1, ty + 4, 1, 2))
        canvas.fill(g["metal"], (cx + 2, ty + 6, 1, 6))


def _held_gun(surface, x, y, face):
    canvas = pygame.Surface((FW, FH), pygame.SRCALPHA)
    _paint_gun(canvas, face, 11)
    surface.blit(
        _ink_scaled(canvas), (x - FCX * PX, y - FBASE * PX)
    )


def _fig_frame(look, face, frame, bob, blink, gun, carry):
    key = (look, face, frame, bob, blink, gun, carry)
    cached = _FIG_CACHE.get(key)
    if cached is not None:
        return cached

    p = _pal(look)
    canvas = pygame.Surface((FW, FH), pygame.SRCALPHA)
    cx = FCX
    sign = -1 if face == "l" else 1
    side = face in "lr"
    hy, ty = 4 + bob, 11 + bob
    lift = (1, 0, -1, 0)[frame] if frame >= 0 else 0
    bodi = look == "bodi"
    apron = _tone(p["torso"], 0.6)

    def r(x, yy, w, h, col):
        canvas.fill(col, (x, yy, w, h))

    def s(dx, yy, w, h, col):
        r(
            cx + dx if sign > 0 else cx - dx - w,
            yy, w, h, col,
        )

    if gun and face == "u":
        _paint_gun(canvas, face, ty)

    if side:
        for offset, raised, near in (
            (-2 * lift, 1 if lift == 0 else 0, False),
            (2 * lift, 0, True),
        ):
            leg = p["legs"] if near else p["legs_d"]
            boot = p["boots"] if near else p["boots_d"]
            s(-2 + offset, 17, 3, 5 - raised, leg)
            s(-2 + offset, 22 - raised, 4, 2, boot)
            if near:
                s(-2 + offset, 17, 1, 5, p["legs_d"])
                s(1 + offset, 22, 1, 1, p["boots_l"])
    else:
        for lx, amount in ((-4, lift), (1, -lift)):
            bottom = 21 + amount
            r(cx + lx, 17, 3, bottom - 16, p["legs"])
            r(
                cx + lx + (2 if lx < 0 else 0),
                17, 1, bottom - 16, p["legs_d"],
            )
            r(cx + lx, bottom + 1, 3, 2, p["boots"])
            r(cx + lx, bottom + 2, 3, 1, p["boots_d"])
            if face == "d":
                r(
                    cx + lx + (0 if lx < 0 else 2),
                    bottom + 1, 1, 1, p["boots_l"],
                )

    if side:
        s(-4, ty, 8, 7, p["torso"])
        s(-4, ty, 1, 1, _CLEAR)
        r(cx - 4, ty + 1, 1, 4, p["torso_l"])
        s(-3, ty, 6, 1, p["torso_l"])
        r(cx + 3, ty + 1, 1, 5, p["torso_d"])
        if bodi:
            s(1, ty + 1, 3, 4, apron)
        s(-4, ty + 5, 8, 1, _BELT)
        s(2, ty + 5, 1, 1, _BUCKLE)
        s(-4, ty + 6, 8, 1, p["torso_d"])
        s(1, ty, 2, 1, p["skin_d"])
    else:
        r(cx - 5, ty, 10, 7, p["torso"])
        r(cx - 5, ty, 1, 1, _CLEAR)
        r(cx + 4, ty, 1, 1, _CLEAR)
        r(cx - 4, ty, 8, 1, p["torso_l"])
        r(cx - 5, ty + 1, 1, 4, p["torso_l"])
        r(cx + 4, ty + 1, 1, 5, p["torso_d"])
        if bodi and face == "d":
            r(cx - 3, ty + 1, 6, 4, apron)
            r(cx - 2, ty + 3, 4, 1, p["torso_d"])
        elif bodi:
            r(cx - 3, ty, 1, 5, apron)
            r(cx + 2, ty, 1, 5, apron)
        elif face == "u":
            r(cx - 1, ty + 1, 1, 4, p["torso_d"])
        r(cx - 5, ty + 5, 10, 1, _BELT)
        r(cx - 5, ty + 6, 10, 1, p["torso_d"])
        if face == "d":
            r(cx - 1, ty + 5, 2, 1, _BUCKLE)
            r(cx - 2, ty, 4, 1, p["torso_d"])
            r(cx - 1, ty, 2, 1, p["skin_d"])

        for ax, amount in ((cx - 7, -lift), (cx + 5, lift)):
            inner = ax + 1 if ax < cx else ax
            if carry:
                r(ax, hy - 1, 2, ty + 3 - hy, p["arm"])
                r(inner, hy - 1, 1, ty + 3 - hy, p["arm_d"])
                r(ax, hy - 2, 2, 1, p["skin"])
            else:
                r(ax, ty + 1, 2, 4 + amount, p["arm"])
                r(inner, ty + 1, 1, 4 + amount, p["arm_d"])
                r(ax, ty + 5 + amount, 2, 1, p["skin"])
                if ax < cx:
                    r(ax, ty + 1, 1, 2, p["arm_l"])
            if p.get("patch") and (ax < cx) == (face == "d"):
                r(
                    ax, hy + 1 if carry else ty + 1,
                    2, 2, p["patch"],
                )

        if gun and face == "d":
            _paint_gun(canvas, face, ty)
            r(cx + 4, ty + 4, 1, 1, p["skin"])

    if side and not carry:
        if gun:
            _paint_gun(canvas, face, ty)
            s(-1, ty + 1, 2, 3, p["arm"])
            s(-1, ty + 3, 4, 1, p["arm"])
            s(3, ty + 3, 1, 1, p["skin"])
        else:
            s(-2 - lift, ty + 1, 1, 4, p["torso_d"])
            s(-1 - lift, ty + 1, 2, 4, p["arm"])
            s(-1 - lift, ty + 5, 2, 1, p["skin"])
        if p.get("patch"):
            s(
                -1 + (0 if gun else -lift),
                ty + 1, 2, 2, p["patch"],
            )

    if side and carry:
        s(-1, hy - 1, 2, ty + 3 - hy, p["arm"])
        s(-1, hy - 1, 1, ty + 3 - hy, p["arm_d"])
        s(-1, hy - 2, 2, 1, p["skin"])

    eye = p["skin_d"] if blink else M.INK
    r(cx - 4, hy, 8, 7, p["skin"])
    r(cx - 4, hy + 6, 1, 1, _CLEAR)
    r(cx + 3, hy + 6, 1, 1, _CLEAR)
    r(cx - 3, hy + 6, 6, 1, p["skin_d"])
    r(cx + 3, hy + 1, 1, 5, p["skin_d"])

    hair, hair_l, hair_d = (
        p["hair"], p["hair_l"], p["hair_d"]
    )
    r(cx - 3, hy - 1, 6, 1, hair)
    r(cx - 4, hy, 8, 2, hair)
    r(cx - 2, hy - 1, 2, 1, hair_l)
    r(cx - 3, hy, 1, 1, hair_l)

    if face == "d":
        r(cx - 4, hy + 2, 1, 2, hair)
        r(cx + 3, hy + 2, 1, 2, hair)
        r(cx - 2, hy + 2, 2, 1, hair)
        r(cx - 5, hy + 3, 1, 2, p["skin_d"])
        r(cx + 4, hy + 3, 1, 2, p["skin_d"])
        r(cx - 2, hy + 3, 1, 1, eye)
        r(cx + 1, hy + 3, 1, 1, eye)
        r(cx - 1, hy + 4, 1, 1, p["skin_d"])
    elif face == "u":
        r(cx - 4, hy + 2, 8, 4, hair)
        r(cx - 4, hy + 5, 8, 1, hair_d)
        r(cx, hy + 2, 1, 1, hair_d)
        r(cx - 5, hy + 3, 1, 2, p["skin_d"])
        r(cx + 4, hy + 3, 1, 2, p["skin_d"])
    else:
        s(-4, hy + 2, 4, 3, hair)
        s(-4, hy + 5, 3, 1, hair_d)
        s(2, hy + 2, 1, 1, hair)
        s(-1, hy + 3, 1, 2, p["skin_d"])
        s(2, hy + 3, 1, 1, eye)
        s(4, hy + 4, 1, 1, p["skin"])

    image = _ink_scaled(canvas)
    _FIG_CACHE[key] = image
    return image


def _figure(
    surface, x, y, face, step, look,
    moving=True, gun=False, carry=False,
):
    if moving:
        frame = int(step / (math.pi / 2)) % 4
        bob = -1 if frame % 2 else 0
        blink = False
    else:
        now = _S.get("now", _now_ms()) + _LOOK_PHASE.get(look, 0)
        frame = -1
        bob = (now // 800) % 2
        blink = now % 3700 < 120

    surface.blit(_drop_shadow(12, 4), (x - 12, y - 5))
    image = _fig_frame(
        look, face, frame, bob, blink, gun, carry
    )
    surface.blit(image, (x - FCX * PX, y - FBASE * PX))


# -- animals ---------------------------------------------------------------

def _goat_frame(col, right, frame, moving, dip):
    key = (col, right, frame if moving else -1, dip)
    cached = _GOAT_CACHE.get(key)
    if cached is not None:
        return cached

    canvas = pygame.Surface((GW, GH), pygame.SRCALPHA)
    dark = _tone(col, 0.72)
    light = _tone(col, 1.08, 14)
    deep = _tone(col, 0.48)
    hoof = (57, 49, 43)
    nose = (72, 59, 51)
    horn_dark = (121, 110, 91)
    ear_inner = _tone(col, 0.68, 12)

    def r(x, y, w, h, color):
        canvas.fill(color, (x, y, w, h))

    legs = (
        (8, True, 0),
        (17, True, 1),
        (6, False, 1),
        (15, False, 0),
    )
    for lx, far, phase in legs:
        lifted = moving and frame == phase
        shift = (1 if phase else -1) if moving else 0
        x = lx + shift
        bottom = 17 if lifted else 19
        r(x, 12, 2, bottom - 12, dark if far else col)
        r(x, 14, 1, max(1, bottom - 14), deep if far else dark)
        r(x - 1, bottom - 1, 3, 2, hoof)
        r(x, bottom - 1, 1, 1, _tone(hoof, 1.35))

    r(3, 7, 2, 4, dark)
    r(2, 5, 2, 3, col)
    r(2, 4, 1, 2, light)
    r(5, 8, 13, 6, col)
    r(7, 7, 10, 2, col)
    r(4, 9, 2, 3, col)
    r(7, 13, 9, 2, dark)
    r(7, 7, 8, 1, light)
    r(5, 9, 2, 2, light)
    r(9, 9, 5, 1, light)
    r(10, 12, 6, 1, dark)
    r(7, 13, 2, 1, col)
    r(13, 13, 2, 1, col)

    if dip:
        r(17, 9, 3, 5, col)
        r(19, 11, 3, 5, col)
        r(17, 10, 1, 3, light)
        r(19, 14, 2, 2, dark)
        r(19, 9, 1, 3, horn_dark)
        r(18, 8, 2, 1, _HORN)
        r(17, 7, 1, 2, _HORN)
        r(22, 10, 1, 2, _HORN)
        r(18, 12, 3, 1, dark)
        r(17, 11, 2, 1, col)
        r(23, 12, 3, 1, col)
        r(24, 13, 1, 1, ear_inner)
        r(21, 12, 3, 5, col)
        r(22, 13, 3, 4, col)
        r(21, 12, 2, 1, light)
        r(23, 16, 3, 2, nose)
        r(23, 14, 1, 1, M.INK)
        r(21, 17, 2, 2, dark)
        r(21, 19, 1, 1, deep)
    else:
        r(17, 6, 3, 7, col)
        r(18, 5, 3, 5, col)
        r(17, 7, 1, 4, light)
        r(19, 10, 1, 4, dark)
        r(19, 3, 1, 3, horn_dark)
        r(18, 2, 2, 1, _HORN)
        r(17, 1, 2, 1, _HORN)
        r(16, 0, 1, 2, _HORN)
        r(22, 3, 1, 2, horn_dark)
        r(21, 1, 1, 3, _HORN)
        r(20, 0, 1, 2, _HORN)
        r(22, 4, 3, 1, dark)
        r(24, 3, 1, 1, col)
        r(19, 4, 4, 5, col)
        r(22, 6, 3, 3, col)
        r(24, 7, 2, 2, col)
        r(19, 4, 3, 1, light)
        r(22, 6, 2, 1, light)
        r(25, 7, 1, 2, nose)
        r(23, 9, 2, 1, dark)
        r(17, 5, 3, 2, col)
        r(16, 5, 2, 1, light)
        r(18, 6, 2, 1, ear_inner)
        r(21, 5, 2, 2, (194, 165, 94))
        r(21, 6, 2, 1, M.INK)
        r(21, 9, 2, 2, dark)
        r(21, 11, 2, 1, dark)
        r(21, 12, 1, 1, deep)

    image = _ink_scaled(canvas)
    if not right:
        image = pygame.transform.flip(image, True, False)
    _GOAT_CACHE[key] = image
    return image


def _goat(surface, x, y, col, right, frame, moving, dip):
    surface.blit(_drop_shadow(12, 4), (x - 12, y + 1))
    image = _goat_frame(col, right, frame, moving, dip)
    anchor = GCX if right else GW - GCX
    surface.blit(
        image, (x - anchor * PX, y + 6 - GBASE * PX)
    )


def _pig_frame(right, frame, sniff, blink):
    key = (right, frame, sniff, blink)
    cached = _PIG_CACHE.get(key)
    if cached is not None:
        return cached

    canvas = pygame.Surface((29, 19), pygame.SRCALPHA)
    pink = (207, 142, 133)
    light = (236, 173, 155)
    dark = (164, 102, 100)
    mud = (121, 89, 67)
    hoof = (75, 57, 54)

    def r(x, y, w, h, color):
        canvas.fill(color, (x, y, w, h))

    for index, lx in enumerate((7, 10, 18, 21)):
        lift = (
            1 if frame >= 0 and index % 2 == frame % 2 else 0
        )
        r(lx, 12, 2, 4 - lift, dark if index % 2 else pink)
        r(lx, 15 - lift, 2, 2, hoof)

    r(5, 6, 17, 8, pink)
    r(7, 4, 13, 11, pink)
    r(8, 4, 10, 2, light)
    r(5, 8, 2, 4, light)
    r(7, 13, 14, 2, dark)
    r(9, 9, 5, 3, mud)
    r(11, 8, 3, 2, mud)
    r(17, 12, 4, 2, mud)
    r(3, 7, 3, 1, pink)
    r(2, 5, 1, 3, light)
    r(3, 4, 2, 1, light)
    r(4, 5, 1, 2, pink)

    hy = 8 if sniff else 6
    r(20, hy, 5, 7, pink)
    r(21, hy - 1, 3, 2, light)
    r(24, hy + 3, 3, 4, dark)
    r(25, hy + 3, 2, 3, (224, 143, 143))
    r(26, hy + 4, 1, 1, (105, 63, 68))
    r(23, hy + 2, 1, 1, dark if blink else M.INK)
    r(20, hy - 3, 3, 4, dark)
    r(20, hy - 3, 2, 3, light)
    r(21, hy - 1, 2, 2, (191, 119, 119))

    image = _ink_scaled(canvas)
    if not right:
        image = pygame.transform.flip(image, True, False)
    _PIG_CACHE[key] = image
    return image


def _pig(surface, x, y, right, frame, sniff, blink):
    surface.blit(_drop_shadow(21, 6), (x - 21, y - 5))
    image = _pig_frame(right, frame, sniff, blink)
    surface.blit(image, (x - 29, y - 30))


def _animal_jobs(now):
    jobs = []
    t = now / 1000.0
    for (hx, hy), col, phase in _GOATS:
        a = t * 0.35 + phase
        b = t * 0.5 + phase * 1.7
        x = (hx + 0.35 * math.sin(a)) * T + OX
        y = (hy + 0.25 * math.sin(b)) * T + OY
        speed = (
            abs(0.1225 * math.cos(a))
            + abs(0.125 * math.cos(b))
        )
        moving = speed > 0.07
        dip = (
            not moving
            and ((now + int(phase * 1000)) // 900) % 3 == 0
        )
        args = (
            int(x), int(y), col, math.cos(a) > 0,
            (now // 170 + int(phase * 10)) % 2,
            moving, dip,
        )
        jobs.append((y + 6, _goat, args))

    cx, cy = _pig_home()
    c, r, w, h = M.PEN
    ax = min(T * 0.48, max(0, (w * T - 70) * 0.22))
    ay = min(T * 0.18, max(0, (h * T - 50) * 0.18))
    a = t * 0.27
    x = cx + math.sin(a) * ax
    y = cy + math.sin(a * 1.7) * ay

    left, right = c * T + 31, (c + w) * T - 31
    top, bottom = r * T + 32, (r + h) * T - 12
    if left <= right:
        x = max(left, min(right, x))
    if top <= bottom:
        y = max(top, min(bottom, y))

    sniff = abs(math.cos(a)) < 0.32
    frame = -1 if sniff else (now // 210) % 2
    args = (
        int(x + OX), int(y + OY),
        math.cos(a) >= 0, frame, sniff, now % 4300 < 130,
    )
    jobs.append((y + OY, _pig, args))
    return jobs


# -- machinery and changing scenery ---------------------------------------

def _tractor_surface():
    """Detailed 128x64 top-down tractor, facing east."""
    surface = pygame.Surface((128, 64), pygame.SRCALPHA)
    surface.fill(M.METAL_D, (18, 5, 11, 54))
    surface.fill(M.METAL_D, (99, 9, 7, 46))

    for x, y, w, h in (
        (7, 0, 33, 16),
        (7, 48, 33, 16),
        (92, 4, 22, 12),
        (92, 48, 22, 12),
    ):
        surface.fill(M.INK, (x, y, w, h))
        surface.fill(
            (35, 36, 36), (x + 2, y + 2, w - 4, h - 4)
        )
        for tx in range(x + 3, x + w - 2, 6):
            pygame.draw.line(
                surface, (70, 69, 65),
                (tx, y + 2), (tx + 3, y + h - 3), 2,
            )
        surface.fill(
            (23, 24, 24), (x + 2, y + h // 2, w - 4, 2)
        )

    surface.fill(M.INK, (6, 14, 116, 36))
    surface.fill(M.TRACTOR_D, (8, 16, 112, 32))
    surface.fill(M.TRACTOR, (10, 17, 109, 28))

    for y in (12, 43):
        surface.fill(M.TRACTOR_D, (5, y, 38, 9))
        surface.fill(M.TRACTOR, (7, y, 35, 6))
        surface.fill(
            _tone(M.TRACTOR, 1.25), (9, y, 31, 2)
        )

    surface.fill(M.INK, (22, 21, 43, 22))
    surface.fill((81, 73, 56), (24, 23, 38, 18))
    surface.fill((43, 39, 34), (26, 25, 14, 14))
    surface.fill((96, 77, 53), (27, 25, 11, 10))
    surface.fill((121, 96, 66), (28, 25, 9, 2))
    pygame.draw.circle(surface, M.INK, (53, 32), 7, 2)
    surface.fill(M.METAL, (52, 29, 2, 6))
    surface.fill(M.METAL, (49, 31, 8, 2))

    surface.fill(M.TRACTOR_D, (65, 20, 52, 25))
    surface.fill(M.TRACTOR, (66, 20, 49, 21))
    surface.fill(_tone(M.TRACTOR, 1.3), (68, 21, 43, 4))
    surface.fill(_tone(M.TRACTOR, 0.88), (67, 36, 48, 5))
    surface.fill(M.INK, (114, 22, 7, 21))
    for yy in range(24, 42, 4):
        surface.fill(M.METAL, (115, yy, 5, 1))

    surface.fill(M.TRACTOR_D, (82, 25, 2, 12))
    surface.fill((222, 206, 143), (91, 28, 12, 5))
    surface.fill(M.INK, (72, 15, 7, 18))
    surface.fill(M.METAL_D, (73, 16, 5, 15))
    surface.fill(M.METAL, (73, 16, 2, 13))
    surface.fill(M.INK, (71, 15, 9, 4))

    for yy in (18, 42):
        surface.fill(M.INK, (110, yy, 8, 5))
        surface.fill((237, 218, 145), (112, yy + 1, 5, 3))

    surface.fill(M.METAL_D, (121, 22, 5, 21))
    surface.fill(M.METAL, (122, 23, 2, 18))
    surface.fill(M.METAL_D, (1, 27, 7, 10))
    surface.fill(M.METAL, (2, 29, 5, 6))
    return surface


def _tractor_draw(surface, cx, cy, angle):
    step = int(round(angle / 11.25)) % 32
    base = _TRACTOR_ROT.get(-1)
    if base is None:
        base = _tractor_surface()
        _TRACTOR_ROT[-1] = base
    image = _TRACTOR_ROT.get(step)
    if image is None:
        image = pygame.transform.rotate(base, -step * 11.25)
        _TRACTOR_ROT[step] = image

    _ellipse_shadow(
        surface, (int(cx) + 4, int(cy) + 7), (116, 46), 85
    )
    surface.blit(
        image, image.get_rect(center=(int(cx), int(cy)))
    )


def _tractor_pose(now):
    if _S["drive"] is not None:
        return _S["drive"].pose(now)
    if "tractor" in _S["preps"]:
        return (
            M.TRACTOR_PARK[0] + T,
            M.TRACTOR_PARK[1] + T // 2,
            0.0,
        )
    return (
        M.TRACTOR_AT[0] * T + T,
        M.TRACTOR_AT[1] * T + T // 2,
        0.0,
    )


def _draw_tractor(surface, now):
    x, y, angle = _tractor_pose(now)
    puzzle = _S["drive"]
    if puzzle is not None and puzzle.speed > 0.25:
        for i in range(5):
            age = (now / 900.0 + i * 0.19) % 1.0
            size = 3 + int(age * 5)
            dx = -20 - age * 30
            dy = math.sin(i * 2.8) * 15
            a = math.radians(angle)
            xx = x + math.cos(a) * dx - math.sin(a) * dy
            yy = y + math.sin(a) * dx + math.cos(a) * dy
            surface.fill(
                (157, 132, 92),
                (int(xx + OX), int(yy + OY), size, size),
            )

    _tractor_draw(surface, x + OX, y + OY, angle)

    if "tractor" in _S["preps"]:
        _, py = M.TRACTOR_PARK
        for bx in (6 * T, int(8.5 * T)):
            surface.fill(
                M.INK, (bx + OX, py + 16 + OY, T // 2, 40)
            )
            surface.fill(
                M.WOOD,
                (bx + 2 + OX, py + 18 + OY, T // 2 - 4, 36),
            )
            surface.fill(
                M.WOOD_L,
                (bx + 2 + OX, py + 18 + OY, T // 2 - 4, 3),
            )
            surface.fill(
                M.WOOD_D,
                (bx + 2 + OX, py + 30 + OY, T // 2 - 4, 3),
            )


def _draw_generator(surface, now):
    gx, gy = _point_px("generator")
    x, y = gx - 32 + OX, gy - 32 + OY
    puzzle = _S["genplay"]
    running = _S["gen_on"]
    momentum = puzzle.comp if puzzle is not None else 0.0

    shake = 0
    if running:
        shake = int(math.sin(now * 0.055) * 1.6)
    elif puzzle is not None and abs(puzzle.flash) > 0.2:
        shake = int(
            math.sin(now * 0.085) * abs(puzzle.flash) * 3
        )
    xx = x + shake

    _ellipse_shadow(surface, (x + 35, y + 49), (67, 31), 85)
    for fx in (x + 7, x + 49):
        surface.fill(M.INK, (fx, y + 46, 10, 10))
        surface.fill((48, 47, 44), (fx + 2, y + 48, 6, 5))

    frame = pygame.Rect(xx + 3, y + 9, 59, 43)
    pygame.draw.rect(surface, M.INK, frame, 4)
    surface.fill(M.METAL, (xx + 5, y + 10, 54, 2))
    surface.fill(M.METAL_D, (xx + 4, y + 14, 3, 32))
    surface.fill(M.INK, (xx + 10, y + 14, 44, 15))
    surface.fill(M.GENERATOR, (xx + 12, y + 15, 40, 12))
    surface.fill(
        _tone(M.GENERATOR, 1.3, 8),
        (xx + 14, y + 16, 35, 3),
    )
    surface.fill(
        _tone(M.GENERATOR, 0.7),
        (xx + 12, y + 25, 40, 3),
    )
    surface.fill(M.INK, (xx + 29, y + 12, 11, 6))
    surface.fill(M.METAL_D, (xx + 31, y + 12, 7, 3))
    surface.fill(M.INK, (xx + 10, y + 30, 29, 18))
    surface.fill(M.METAL_D, (xx + 12, y + 31, 25, 15))
    for yy in range(y + 32, y + 46, 4):
        surface.fill(M.METAL, (xx + 13, yy, 21, 1))

    center = (xx + 46, y + 38)
    pygame.draw.circle(surface, M.INK, center, 12)
    pygame.draw.circle(surface, (80, 79, 72), center, 9)
    pygame.draw.circle(surface, M.METAL_D, center, 6)
    spin = now * (0.018 if running else 0.009 * momentum)
    for i in range(3):
        a = spin + i * math.tau / 3
        endpoint = (
            center[0] + int(math.cos(a) * 7),
            center[1] + int(math.sin(a) * 7),
        )
        pygame.draw.line(
            surface, M.METAL, center, endpoint, 2
        )
    pygame.draw.circle(surface, (177, 171, 147), center, 2)

    surface.fill(M.INK, (xx + 51, y, 8, 17))
    surface.fill(M.METAL_D, (xx + 53, y + 1, 4, 15))
    surface.fill(M.METAL, (xx + 53, y + 2, 1, 12))
    surface.fill(M.INK, (xx + 49, y - 2, 12, 4))
    lamp = (154, 217, 112) if running else (95, 68, 47)
    surface.fill(M.INK, (xx + 9, y + 20, 7, 7))
    surface.fill(lamp, (xx + 11, y + 22, 3, 3))
    surface.fill((224, 192, 96), (xx + 18, y + 20, 9, 5))
    surface.fill(M.INK, (xx + 22, y + 21, 1, 3))

    if running or momentum > 0.15:
        for i in range(4):
            age = (
                now * (0.00065 if running else 0.0004) + i / 4.0
            ) % 1.0
            size = 4 + int(age * 7)
            tone = int(155 - age * 50)
            surface.fill(
                (tone, tone, max(0, tone - 8)),
                (
                    int(xx + 51 - age * 18),
                    int(y - 7 - age * 36),
                    size, size,
                ),
            )

    if puzzle is not None:
        pull = puzzle.extension(now)
        end = (
            int(xx + 47 + pull * 31),
            int(y + 47 + pull * 13),
        )
        pygame.draw.line(
            surface, (197, 181, 137),
            (xx + 47, y + 43), end, 2,
        )
        pygame.draw.line(
            surface, M.INK,
            (end[0] - 4, end[1] + 3),
            (end[0] + 4, end[1] - 3), 5,
        )


def _draw_trough(surface):
    x = M.TROUGH[0] * T + OX
    y = M.TROUGH[1] * T + OY
    _ellipse_shadow(
        surface, (x + T + 3, y + 40), (2 * T - 8, 25), 60
    )
    surface.fill(M.INK, (x + 2, y + 14, 2 * T - 4, 30))
    surface.fill(M.WOOD, (x + 4, y + 16, 2 * T - 8, 26))
    surface.fill(M.WOOD_L, (x + 4, y + 16, 2 * T - 8, 4))
    surface.fill(M.WOOD_D, (x + 4, y + 38, 2 * T - 8, 4))

    inner = pygame.Rect(x + 10, y + 22, 2 * T - 20, 14)
    surface.fill(M.WOOD_D, inner)
    middle = inner.centerx

    if _S["trough"]["water"]:
        surface.fill(
            M.WATER,
            (inner.x + 2, inner.y + 2,
             inner.w // 2 - 3, inner.h - 4),
        )
        shimmer = int(math.sin(_S["now"] * 0.003) * 3)
        surface.fill(
            (133, 174, 187),
            (inner.x + 10 + shimmer, inner.y + 4, 17, 2),
        )

    if _S["trough"]["feed"]:
        surface.fill(
            M.GRAIN,
            (middle + 2, inner.y + 2,
             inner.w // 2 - 4, inner.h - 4),
        )
        for i in range(8):
            surface.fill(
                (175, 140, 72),
                (middle + 5 + i * 6,
                 inner.y + 4 + i % 3, 3, 2),
            )

    surface.fill(
        M.WOOD, (middle - 1, inner.y, 3, inner.h)
    )
    for xx in (x + 18, x + 2 * T - 24):
        surface.fill(M.METAL_D, (xx, y + 16, 4, 26))
        surface.fill(M.METAL, (xx + 1, y + 18, 2, 2))


def _draw_hay(surface):
    x, y = 12 * T + OX, T + OY
    surface.fill(M.HAYFLOOR[1], (x + 4, y + 12, 56, 44))
    surface.fill(M.HAYFLOOR[0], (x + 8, y + 10, 48, 40))
    for i in range(10):
        xx = x + 11 + (i * 13) % 41
        yy = y + 14 + (i * 7) % 29
        pygame.draw.line(
            surface, M.HAYFLOOR[2],
            (xx, yy + 3), (xx + 8, yy), 2,
        )
    surface.fill((139, 106, 52), (x + 21, y + 11, 3, 39))
    surface.fill((139, 106, 52), (x + 42, y + 11, 3, 39))

    if _S["crate"]:
        surface.fill(M.INK, (x + 10, y + 22, 40, 26))
        surface.fill(M.WOOD, (x + 12, y + 24, 36, 22))
        surface.fill(M.WOOD_L, (x + 13, y + 24, 34, 3))
        surface.fill(M.WOOD_D, (x + 12, y + 33, 36, 3))
        for xx in (x + 17, x + 40):
            surface.fill(M.METAL_D, (xx, y + 24, 3, 22))
        surface.fill(
            (216, 200, 148), (x + 25, y + 36, 11, 6)
        )


def _draw_rig(surface, now):
    if "shed" not in _S["preps"]:
        return
    bx, by = T + 46 + OX, 8 * T + 16 + OY
    points = (
        (bx, by),
        (3 * T + 14 + OX, 8 * T + 34 + OY),
        (3 * T + 14 + OX, 7 * T + 52 + OY),
    )
    pygame.draw.lines(surface, M.INK, False, points, 3)
    pygame.draw.lines(surface, (190, 60, 44), False, points, 1)
    surface.fill(M.INK, (bx - 4, by - 6, 9, 7))
    surface.fill((197, 74, 49), (bx - 2, by - 4, 5, 3))


def _draw_carry(surface, x, y):
    kind = _S["carry"]
    if not kind:
        return
    col = M.WATER if kind == "water" else M.GRAIN
    bob = (
        -2
        if _S["moving"]
        and int(_S["step"] / (math.pi / 2)) % 2
        else 0
    )
    y += bob

    def p(lx, ly, w, h, color):
        surface.fill(
            color,
            (x + lx * PX, y + ly * PX, w * PX, h * PX),
        )

    p(-3, -33, 6, 1, M.INK)
    p(-4, -32, 1, 3, M.INK)
    p(3, -32, 1, 3, M.INK)
    p(-5, -30, 10, 8, M.INK)
    p(-4, -29, 8, 6, M.METAL)
    p(-4, -29, 8, 1, _tone(M.METAL, 1.25, 20))
    p(-3, -28, 6, 1, col)
    p(-3, -28, 2, 1, _tone(col, 1.2, 18))
    p(3, -27, 1, 4, M.METAL_D)
    p(-4, -25, 8, 1, M.METAL_D)


def _draw_person(surface, look, x, y, face, step):
    me = look == "biribel"
    _figure(
        surface, x, y, face, step, look,
        moving=me and _S["moving"],
        gun=me and _S["stage"] == PREP,
        carry=me and bool(_S["carry"]),
    )
    if me:
        _draw_carry(surface, x, y)


def _draw_route_marker(surface, now):
    puzzle = _S["drive"]
    if puzzle is None or puzzle.state in ("park", "done"):
        return

    _, _, x, y, _, _, _, _ = puzzle.step()
    center = (int(x + OX), int(y + OY))
    color = (227, 198, 119)
    radius = 15 + int(math.sin(now * 0.006) * 2)
    pygame.draw.circle(
        surface, M.INK, center, radius + 2, 2
    )
    pygame.draw.circle(surface, color, center, radius, 2)

    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        start = (
            center[0] + dx * 20, center[1] + dy * 20
        )
        end = (
            center[0] + dx * 26, center[1] + dy * 26
        )
        pygame.draw.line(surface, color, start, end, 2)


# -- UI and scene drawing --------------------------------------------------

def _objective():
    if _S["finished"]:
        return ""
    if _S["genplay"] is not None:
        return "START THE GENERATOR"
    if _S["drive"] is not None:
        return "BLOCK THE TRACK"

    if _S["stage"] == PREP:
        if len(_S["preps"]) >= PREP_PICKS:
            return "TALK TO ALEX"
        marks = [
            "x" if item in _S["preps"] else " "
            for item in PREP_ITEMS
        ]
        return (
            "PREPARE %d/%d  TRACTOR [%s]  SHED [%s]  LOFT [%s]"
            % (len(_S["preps"]), PREP_PICKS, *marks)
        )

    if _chores_done():
        return "TALK TO BODI"
    marks = [
        "x" if item in _S["done"] else " "
        for item in CHORES_NEEDED
    ]
    return (
        "CHORES  GENERATOR [%s]  WATER [%s]  FEED [%s]"
        % tuple(marks)
    )


def _draw_toast(surface, text):
    max_width = WIDTH - 70
    lines = []
    current = ""
    for word in text.split():
        candidate = word if not current else current + " " + word
        if (
            current
            and font_terminal_small.size(candidate)[0] > max_width
        ):
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)

    images = [
        font_terminal_small.render(
            line, True, (240, 232, 204)
        )
        for line in lines
    ]
    if not images:
        return

    line_h = font_terminal_small.get_linesize()
    width = max(image.get_width() for image in images) + 24
    height = line_h * len(images) + 14
    box = pygame.Rect(0, 0, width, height)
    box.midbottom = (WIDTH // 2, HEIGHT - 48)

    pygame.draw.rect(surface, (20, 20, 22), box)
    pygame.draw.rect(surface, M.WOOD_L, box, 2)
    for i, image in enumerate(images):
        surface.blit(
            image,
            image.get_rect(
                midtop=(box.centerx, box.y + 7 + i * line_h)
            ),
        )


def draw(surface):
    if not _S:
        surface.fill(M.SKY_EDGE)
        return
    if _RESCUE is not None:
        _RESCUE.draw(surface)
        return

    from cutscenes.engine import draw_dialogue_box
    from engine.ui import prompt as _prompt
    from ui import hud

    now = _now_ms()
    _S["now"] = now
    surface.fill(M.SKY_EDGE)
    surface.blit(_S["static"], (OX, OY))
    _draw_route_marker(surface, now)
    _draw_hay(surface)
    _draw_rig(surface, now)

    player = STATE.player
    px, py = player.rect.centerx, player.rect.bottom - 2

    def face_to(x, y):
        if abs(px - x) > abs(py - y) + 16:
            return "r" if px > x else "l"
        return "u" if py < y else "d"

    jobs = _animal_jobs(now)
    if _S["escape_shown"]:
        jobs = jobs[1:]          # the cream goat is out through the gap
    bx, by = M.tile_px(_bodi_tile())
    jobs.append(
        (
            by + 14 + OY,
            _draw_person,
            (
                "bodi", bx + OX, by + 14 + OY,
                face_to(bx, by), 0.0,
            ),
        )
    )

    if _S["drive"] is None:
        jobs.append(
            (
                py + OY,
                _draw_person,
                (
                    "biribel", px + OX, py + OY,
                    _S["face"], _S["step"],
                ),
            )
        )

    if _S["stage"] == PREP:
        ax, ay = M.tile_px(M.ALEX_TILE)
        jobs.append(
            (
                ay + 14 + OY,
                _draw_person,
                (
                    "alex", ax + OX, ay + 14 + OY,
                    face_to(ax, ay), 0.0,
                ),
            )
        )

    gx, gy = _point_px("generator")
    jobs.append(
        (gy + 18 + OY, _draw_generator, (now,))
    )
    tx, ty, _ = _tractor_pose(now)
    jobs.append(
        (ty + 22 + OY, _draw_tractor, (now,))
    )
    jobs.append(
        (M.TROUGH[1] * T + 42 + OY, _draw_trough, ())
    )

    # Easter egg: Colonel Paie, y-sorted by his feet.
    if _COLONEL is not None:
        jobs.append((_COLONEL.sort_y, _COLONEL.draw, ()))

    for _, function, args in sorted(jobs, key=lambda job: job[0]):
        function(surface, *args)

    busy = (
        _S["genplay"] is not None
        or _S["drive"] is not None
    )
    near = _S["near"]

    if (
        near and not _S["lines"]
        and not busy and not _S["finished"]
    ):
        x, y = _point_px(near[0])
        _prompt.draw(
            surface, x + OX, y + OY,
            "[E] " + near[1],
            (236, 228, 196), font=font_prompt,
        )

    objective = _objective()
    if objective:
        hud.draw_objective_panel(
            surface, objective, x=20, y=16
        )

    if not _S["lines"]:
        if _S["genplay"] is not None:
            G.draw_generator(surface, _S["genplay"], now)
        elif _S["drive"] is not None:
            G.draw_tractor(surface, _S["drive"], now)

    text, until = _S["toast"]
    if text and now < until and not _S["lines"]:
        _draw_toast(surface, text)

    if _S["lines"]:
        who, line = _S["lines"][0]
        count = max(
            0,
            min(len(line), (now - _S["line_t0"]) // CHAR_MS),
        )
        if count // 3 > _S["tick_n"] // 3:
            _snd().dialogue_tick()
            _S["tick_n"] = count
        draw_dialogue_box(
            surface, who, line, count, len(line),
            can_continue=count >= len(line),
            show_speaker=bool(who),
        )