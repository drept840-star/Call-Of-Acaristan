"""M5 shallow floodwater: one connected, world-space surface, never tile stamps.

Visual only: no map/collision/pathfinding changes. Cache the single active
map's mask and shore treatment, reuse viewport buffers, animate sparse ripples.
"""
import math
import random
import pygame
from core.config import TILE_SIZE

_CACHE = {}


def _build(grid):
    key = tuple(grid)
    if _CACHE.get("key") == key:
        return
    t = TILE_SIZE
    size = (len(grid[0]) * t, len(grid) * t)
    mask = pygame.Surface(size, pygame.SRCALPHA)
    base = pygame.Surface(size, pygame.SRCALPHA)

    def wet(c, r):
        return 0 <= r < len(grid) and 0 <= c < len(grid[r]) and grid[r][c] == "W"

    rng = random.Random(5705)
    for row, line in enumerate(grid):
        for col, ch in enumerate(line):
            if ch != "W":
                continue
            x, y = col * t, row * t
            mask.fill((255, 255, 255, 255), (x, y, t, t))
            base.fill((18, 36, 40, 132), (x, y, t, t))
            edges = []
            if not wet(col, row - 1):
                edges.append(((x, y + 1), (x + t - 1, y + 1)))
            if not wet(col, row + 1):
                edges.append(((x, y + t - 2), (x + t - 1, y + t - 2)))
            if not wet(col - 1, row):
                edges.append(((x + 1, y), (x + 1, y + t - 1)))
            if not wet(col + 1, row):
                edges.append(((x + t - 2, y), (x + t - 2, y + t - 1)))
            for a, b in edges:
                pygame.draw.line(base, (12, 20, 22, 205), a, b, 5)
                pygame.draw.line(base, (104, 102, 77, 100), a, b, 1)
            # Silt on the submerged floor, deliberately not bright cyan dashes.
            for _ in range(2):
                px, py = x + rng.randrange(5, t - 5), y + rng.randrange(5, t - 5)
                pygame.draw.circle(base, (28, 31, 25, 90), (px, py), rng.randrange(1, 4))
    # Wide shore strokes must never bleed onto collision/walkway tiles.
    base.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    _CACHE.clear()  # bounded: keep only the current map and viewport buffers
    _CACHE.update(key=key, mask=mask, base=base)


def draw(surface, grid, cam_x, cam_y, ticks, actors=(), reduced_motion=False):
    for img, pos in render(surface.get_size(), grid, cam_x, cam_y, ticks, actors, reduced_motion):
        surface.blit(img, pos)


def render(size, grid, cam_x, cam_y, ticks, actors=(), reduced_motion=False):
    """RPE6 Phase 6: the water as ``[(surface, topleft), ...]`` (base cut, then the wave sheet);
    ``size`` is the viewport. The wave sheet is a per-viewport scratch surface rebuilt each call."""
    if not grid:
        return []
    _build(grid)
    if _CACHE.get("viewport") != size:
        _CACHE["viewport"] = size
        _CACHE["waves"] = pygame.Surface(size, pygame.SRCALPHA)
        _CACHE["visible_mask"] = pygame.Surface(size, pygame.SRCALPHA)
    waves, clip = _CACHE["waves"], _CACHE["visible_mask"]
    waves.fill((0, 0, 0, 0))
    clip.fill((0, 0, 0, 0))
    clip.blit(_CACHE["mask"], (-cam_x, -cam_y))
    out = [(_CACHE["base"], (-cam_x, -cam_y))]
    # Slow, continuous bands use WORLD coordinates on both axes: neighbouring
    # water tiles and camera pans cannot expose a repeated tile boundary.
    phase = 0.0 if reduced_motion else (ticks // 120) * 0.13
    w, h = size
    for wy in range((cam_y // 28) * 28, cam_y + h + 28, 28):
        pts = []
        for wx in range((cam_x // 24) * 24 - 24, cam_x + w + 48, 24):
            dy = math.sin(wx * 0.022 + wy * 0.017 + phase) * 3
            dy += math.sin(wx * 0.047 - phase * 0.55) * 1.5
            pts.append((int(wx - cam_x), int(wy + dy - cam_y)))
        pygame.draw.lines(waves, (105, 123, 119, 38), False, pts, 1)
        if wy % 84 == 0:
            # A muted warm practical reflection, broken rather than a neon stripe.
            for i in range(1, len(pts) - 1, 7):
                a = pts[i]
                pygame.draw.line(waves, (190, 158, 106, 44), a, (a[0] + 13, a[1]), 1)
    if not reduced_motion:
        for x, y in actors:
            c, r = int(x) // TILE_SIZE, int(y) // TILE_SIZE
            if not (0 <= r < len(grid) and 0 <= c < len(grid[r]) and grid[r][c] == "W"):
                continue
            radius = 8 + (ticks // 90) % 18
            pygame.draw.ellipse(waves, (146, 152, 134, 85),
                                (int(x - cam_x - radius), int(y - cam_y - radius / 2),
                                 radius * 2, radius), 1)
    waves.blit(clip, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    out.append((waves, (0, 0)))
    return out
