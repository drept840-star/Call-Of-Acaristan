
"""Split from mission4.py - see __init__.py for the package facade.

Render pipeline for Mission 4 (game_draw). Z-order mirrors
missions.m3.systems' inner draw: floor → blood decals → corpses →
pickups → enemies → player → muzzle → bullets → particles/casings →
floating texts → vignette/scanlines → death overlay → HUD → reticle.
Slice 0 draws tiles as flat rects (no staticlayer bake yet); W2 adds the
city art pass. World tile colors MATCH the hud MiniMap "m4" palette so
the minimap reads like the world.
"""

import math
import random
import zlib
import time

import pygame

from core.config import (C_BG_GAME, C_KRAP_BLUE, C_TERMINAL, C_WHITE, HEIGHT, MUZZLE_FLASH, TILE_SIZE, WIDTH, draw_scanlines, draw_vignette, font_dialogue, font_speaker, font_terminal_small, screen)
from core.state import STATE
from game.art import m4 as _m4art
from entities import corpse
from entities.art_cache import get_blood_decal, get_fullscreen_overlay, get_panel_bg, get_plate_bg
from core import artpack
from ui.hud import (
    THEME, MiniMap, draw_combat_reticle, draw_objective_panel, draw_pinned_radio,
)
from engine.text import T as _T  # T is TILE_SIZE in this module - do not shadow
from engine.ui import health_bar as _hud_health_bar, hostiles as _hud_hostiles, weapon_panel as _hud_weapon_panel
from fx import effects
from core import config as _config
from core import artpack, render_util, lighting, staticlayer
# RPE6 A-003: M4 owns this take module; importing it registers the M4 scene ids
# (core.cutscene_registry) before any M4 shot can be dispatched.
from cutscenes import m4aftermath  # noqa: F401
from core.camera import draw_bullets
from engine.core import now_s as _now_s  # RPE6 B-001 timebase

audio = _config.audio

from missions.m4 import maps as _m4_maps  # _objective / _last_keys live view
from missions.m4.maps import (
    M4_BLOCKS, STATION_BLOCK, SIDEWALK_N, SIDEWALK_S)
from missions.m4.meta import (
    M4_HOLD_SECONDS, STAGE_DONE,
    STAGE_AFTERMATH, STAGE_KRAP_STATUS, STAGE_MARU, STAGE_COMMIT,
    TILE, TRANSMITTER_TILE, JAMMER_TILE,
    VASILE_CACHE_TILE, STATION_DOOR_TILE,
    C_VASILE, C_MARU,
)
from missions.m4.world import (
    _movement_locked, _solid_walls, friendly_npcs,
    _street_door_pos, _vasile_cache_pos)
from missions.m4 import flow as _m4_flow  # live view of _m4_dlg (typewriter state)


# Night-city palette (must stay in sync with ui.hud MiniMap._M4_BASE).
M4_TILE_BASE = {
    "C": (44, 46, 52),    # building block / concrete perimeter (solid)
    "B": (64, 58, 48),    # barricade concrete (solid)
    ".": (30, 31, 34),    # asphalt
    "d": (40, 41, 45),    # sidewalk (art-backed t_d_*)
    "a": (26, 27, 30),    # legacy sidewalk
    "g": (34, 33, 30),    # rubble
    "R": (40, 42, 48),    # lane paint
    "D": (52, 54, 62),    # doorway gap (walkable)
    "F": (38, 34, 30),    # interior floor (station foyer)
    "O": (29, 34, 40),    # interior floor
    "L": (34, 40, 46),    # corridor floor
    "E": (30, 31, 34),    # guard spawn marker (floor)
    "M": (30, 31, 34),    # marksman spawn marker (floor)
    "P": (30, 31, 34),    # player spawn marker (floor)
    "X": (28, 36, 34),    # objective marker floor
    "S": (56, 84, 96),    # station fixture
    "V": (44, 58, 74),    # Vasile comms cache
    "N": (40, 54, 46),    # liaison detail (Maru's people)
    "T": (70, 78, 92),    # transmitter
    "J": (60, 66, 80),    # jammer spot
}


# ── sprite tile renderer (ported from m3/draw._render_cell_bg; the m3 module
#    is NOT imported - its globals are mission-scoped). Floors/walls resolve
#    through core.artpack; M4_TILE_BASE is the procedural fallback used when
#    the art tier is off (ACA_ART=legacy) or a PNG is missing.
_ART_FLOOR_CODES = (".", "g", "O", "L", "d", "F")   # chars with a real floor sprite
# Objective fixture props: the transmitter rack, the jammer CRT. (Vasile's
# comms cache has its own bespoke sprite - see _m4_cache_sprite - so the drop
# never reads as a generic crate.)
_M4_FIXTURE_PROP = {"T": "rack_1", "J": "crt_2"}


def _stable_seed(key):
    """Process-independent seed for authored per-building variation. ``hash(str)`` is salted per
    interpreter launch (PYTHONHASHSEED), which re-rolled the facades on every run (B-017) and made
    the static world unbakeable; crc32 keeps the variation deterministic."""
    return zlib.crc32(str(key).encode("utf-8")) & 0xFFFFFFFF


def _m4_is_station(g):
    return g is _m4_maps.MISSION4_STATION_MAP


def _m4_floor_code(ch, station):
    """Map a marker char with no dedicated sprite to the art-backed floor code
    it actually sits on (E/M/R/P on asphalt, V on the sidewalk, station
    fixtures/doorways on interior floor).
    """
    if ch in _ART_FLOOR_CODES:
        return ch
    if ch in ("N", "T", "J"):
        return "O"
    if ch == "P":
        return "F"
    if ch == "D":
        return "O" if station else "."
    return {"a": "d", "X": "g", "E": ".", "M": ".", "R": ".", "V": "d"}.get(ch, ".")


def _m4_floor_art(ch, col, row, station):
    code = ch if ch in _ART_FLOOR_CODES else _m4_floor_code(ch, station)
    return artpack.tile(code, col, row)


def _m4_tile_rect(target, base, sx, sy, ch, col=0, row=0):
    """Procedural fallback blit (art tier off or PNG missing)."""
    pygame.draw.rect(target, base, (sx, sy, TILE_SIZE, TILE_SIZE))
    if ch in ("C", "B", "D"):
        edge = tuple(min(255, c + 14) for c in base)
        pygame.draw.line(target, edge, (sx, sy), (sx + TILE_SIZE - 1, sy))
    if ch == "C":
        # Weathered concrete for the leftover solid field (map perimeter,
        # safehouse shell): panel seams, a damp head and seeded grime so no
        # C tile ever reads as a flat untextured slab again.
        seed = col * 73856093 ^ row * 19349663
        rnd = random.Random(seed & 0xFFFFFFFF)
        dark = tuple(max(0, c - 10) for c in base)
        lite = tuple(min(255, c + 8) for c in base)
        pygame.draw.line(target, dark, (sx + 31, sy + 2), (sx + 31, sy + 63), 1)
        pygame.draw.line(target, lite, (sx + 32, sy + 2), (sx + 32, sy + 63), 1)
        pygame.draw.line(target, dark, (sx + 2, sy + 40), (sx + 62, sy + 40), 1)
        for _ in range(26):
            gx = sx + rnd.randrange(TILE_SIZE)
            gy = sy + rnd.randrange(TILE_SIZE)
            target.set_at((gx, gy), dark if rnd.random() < 0.6 else lite)
        # one seeded stain patch per tile so big C fields (perimeter ring,
        # safehouse shell) never read as a flat slab
        px = sx + rnd.choice((4, 20, 36))
        py = sy + rnd.choice((6, 24, 44))
        pygame.draw.rect(target, tuple(max(0, c - 5) for c in base),
                         (px, py, rnd.randint(10, 22), rnd.randint(8, 16)))
        # damp head rising from the bottom edge
        for i in range(6):
            a_col = tuple(max(0, c - 6 - i) for c in base)
            pygame.draw.line(target, a_col, (sx, sy + 63 - i),
                             (sx + TILE_SIZE - 1, sy + 63 - i), 1)


def _m4_blit_station_tile(target, ch, col, row, sx, sy):
    """Continuous station floor and connected cutaway walls.

    Tile markers describe gameplay, not different floor materials.
    Wall edges are drawn only where solid tiles meet walkable space.
    """
    from missions.m4.meta import M4_SOLID_CHARS

    g = _m4_maps.MISSION4_STATION_MAP
    size = TILE_SIZE
    x, y = int(sx), int(sy)
    rect = pygame.Rect(x, y, size, size)

    def solid_at(c, r):
        # Beyond the map is solid, so the outer border has no bright rim.
        if r < 0 or r >= len(g):
            return True
        if c < 0 or c >= len(g[r]):
            return True
        return g[r][c] in M4_SOLID_CHARS

    if ch in M4_SOLID_CHARS:
        # A single dark cutaway mass, not individually outlined cubes.
        pygame.draw.rect(target, (32, 35, 37), rect)

        edge = max(2, size // 16)
        face = max(4, size // 8)

        if not solid_at(col, row - 1):
            pygame.draw.rect(
                target, (94, 91, 80),
                (x, y, size, edge),
            )

        if not solid_at(col - 1, row):
            pygame.draw.rect(
                target, (76, 75, 68),
                (x, y, edge, size),
            )

        if not solid_at(col + 1, row):
            pygame.draw.rect(
                target, (56, 58, 55),
                (x + size - edge, y, edge, size),
            )

        if not solid_at(col, row + 1):
            # South-facing wall thickness, kept inside its solid tile.
            pygame.draw.rect(
                target, (69, 70, 63),
                (x, y + size - face, size, face),
            )
            pygame.draw.line(
                target, (103, 100, 87),
                (x, y + size - face),
                (x + size - 1, y + size - face),
            )
            pygame.draw.line(
                target, (24, 27, 28),
                (x, y + size - 1),
                (x + size - 1, y + size - 1),
            )
        return

    # Muted institutional linoleum. Identical underneath all walkable
    # codes, including doors, spawn points, and objective markers.
    pygame.draw.rect(target, (65, 66, 61), rect)

    # Sparse, low-contrast grain. No tile borders, checkerboard tint,
    # route stripes, or randomly selected floor sprites.
    seed = ((col * 73856093) ^ (row * 19349663)) & 0xFFFFFFFF
    rng = random.Random(seed)
    for _ in range(max(4, size // 4)):
        px = x + rng.randrange(size)
        py = y + rng.randrange(size)
        shade = rng.choice(((62, 63, 58), (68, 69, 64)))
        pygame.draw.line(target, shade, (px, py), (px, py))

    # Subtle contact shade on the FLOOR side of an actual wall.
    # It never follows a floor-material boundary or a doorway marker.
    contact = max(2, size // 24)
    shade = (49, 51, 47)

    if solid_at(col, row - 1):
        pygame.draw.rect(target, shade, (x, y, size, contact))
    if solid_at(col - 1, row):
        pygame.draw.rect(target, shade, (x, y, contact, size))
    if solid_at(col + 1, row):
        pygame.draw.rect(
            target, shade,
            (x + size - contact, y, contact, size),
        )
    if solid_at(col, row + 1):
        pygame.draw.rect(
            target, shade,
            (x, y + size - contact, size, contact),
        )

    # Preserve the existing objective equipment.
    prop = _M4_FIXTURE_PROP.get(ch)
    if prop is not None:
        sprite = artpack.get(prop)
        if sprite is not None:
            pw, ph = sprite.get_size()
            target.blit(
                sprite,
                (
                    x + (size - pw) // 2,
                    y + size - min(ph, size),
                ),
            )


def _m4_blit_tile(target, ch, col, row, sx, sy, station):
    """Blit one tile: wall sprite, floor sprite (with a marker fallback), a
    framed doorway, a painted lane dash, or an objective fixture prop."""
    if station:
        _m4_blit_station_tile(target, ch, col, row, sx, sy)
        return
    base = M4_TILE_BASE.get(ch, (24, 24, 26))

    # Solid walls / barriers / security glass.
    if ch in ("C", "B", "S"):
        spr = artpack.wall(ch, col, row)
        if spr is not None:
            target.blit(spr, (sx, sy))
        else:
            _m4_tile_rect(target, base, sx, sy, ch, col, row)
        return

    # Doorway: floor blit + a recessed frame (ported M3 "D" idiom).
    if ch == "D":
        floor = _m4_floor_art(ch, col, row, station)
        if floor is not None:
            target.blit(floor, (sx, sy))
        else:
            pygame.draw.rect(target, M4_TILE_BASE["."],
                             (sx, sy, TILE_SIZE, TILE_SIZE))
        pygame.draw.rect(target, (16, 16, 20),
                         (sx + 3, sy, TILE_SIZE - 6, TILE_SIZE), 3, border_radius=2)
        lintel = tuple(min(255, c + 20) for c in M4_TILE_BASE["D"])
        pygame.draw.line(target, lintel, (sx + 4, sy + 3),
                         (sx + TILE_SIZE - 4, sy + 3), 2)
        return

    # Floors / markers: dedicated sprite, else remap to the ground underneath.
    art = _m4_floor_art(ch, col, row, station)
    if art is not None:
        target.blit(art, (sx, sy))
    else:
        _m4_tile_rect(target, base, sx, sy, ch, col, row)

    if ch == "R":
        # Painted lane centre-dash over the asphalt (thin procedural overlay).
        pygame.draw.rect(target, (150, 150, 120),
                         (sx + TILE_SIZE // 2 - 3, sy + 8, 6, TILE_SIZE - 16))

    prop = _M4_FIXTURE_PROP.get(ch)
    if prop is not None:
        spr = artpack.get(prop)
        if spr is not None:
            pw, ph = spr.get_size()
            ox = sx + (TILE_SIZE - pw) // 2
            oy = sy + TILE_SIZE - min(ph, TILE_SIZE)
            target.blit(spr, (ox, oy))


def _draw_m4_floor_and_walls(surface, cam_x, cam_y):
    """Sprite-tile pass: floors + walls + doorways + static fixture props."""
    g = _m4_maps.MISSION4_MAP
    station = _m4_is_station(g)
    h = len(g)
    w = len(g[0]) if h else 0
    x0 = max(0, cam_x // TILE_SIZE)
    y0 = max(0, cam_y // TILE_SIZE)
    x1 = min(w, (cam_x + WIDTH) // TILE_SIZE + 1)
    y1 = min(h, (cam_y + HEIGHT) // TILE_SIZE + 1)
    for row in range(y0, y1):
        grow = g[row]
        for col in range(x0, x1):
            sx = col * TILE_SIZE - cam_x
            sy = row * TILE_SIZE - cam_y
            _m4_blit_tile(surface, grow[col], col, row, sx, sy, station)
    # Street only: stamp the authored building art over the raw C field so the
    # blocks read as actual buildings (roofs, cornices, windows, storefronts).
    if not station:
        _draw_m4_buildings(surface, cam_x, cam_y)


# ─────────────────────────────────────────────
# ACTUAL BUILDINGS (street art pass)
#
# The street map is a solid-C field carved by streets; every block in
# maps.M4_BLOCKS is one building footprint. This pass stamps authored art on
# top of the C tiles: a per-style wall facade (cladding/coursing), a banded
# cornice + roof plate with eaves shadow, multi-storey window grids with
# sills + ledges, varied roof props (water tank, antenna mast, satellite
# dish, AC unit, vent stack, stair bulkhead, billboard), and ground
# entrances (doorway + awning + warm practical + light spill) at the
# registered facade cols. Seeded by block id so the bake is deterministic.
# ─────────────────────────────────────────────
# Per-style facade palette: (base wall, deep shade, hi-light, mortar/shadow)
# Curfew-night pass: the capital is three nights into a curfew it can no
# longer police, in cold rain, sodiums off. Facades therefore sit at roughly
# half the old luminance, desaturated and cooled - wet masonry reads dark -
# and the only bright notes left on a block are a sparse dim window, a
# shuttered storefront bulb, or the station marquee. The m4street lighting
# grade still cools everything a further step, so these values are the
# *pre*-grade albedo of rain-dark brick, slate and soot-stained stone.
_M4_WALL_STYLES = {
    # Rain-dark brick tenement: soot-warmed brown-grey, near-black mortar.
    "row":       {"base": (62, 52, 44), "shade": (36, 30, 25), "hi": (94, 82, 68),
                  "mortar": (28, 23, 19), "roof": (48, 44, 38), "roof_hi": (76, 70, 60),
                  "roof_lo": (28, 26, 22), "sill": (32, 27, 23), "ledge": (56, 48, 40),
                  "cladding": "brick", "stripe_color": None, "stripe_w": 0},
    # Slate-grey mid-rise apartment: cold plaster, damp courses.
    "apartment": {"base": (54, 58, 66), "shade": (32, 36, 43), "hi": (84, 90, 100),
                  "mortar": (27, 24, 22), "roof": (42, 46, 53), "roof_hi": (66, 70, 78),
                  "roof_lo": (26, 28, 33), "sill": (28, 32, 38), "ledge": (50, 54, 62),
                  "cladding": "brick", "stripe_color": None, "stripe_w": 0},
    # Civic palace block: soot-stained limestone, engraved band, lead roof.
    # Deliberately no longer daylight beige - the bright monolith read as an
    # office slab at noon, not a ministry at night under martial law.
    "palace":    {"base": (60, 58, 51), "shade": (35, 34, 29), "hi": (86, 82, 72),
                  "mortar": (40, 37, 31), "roof": (40, 38, 33), "roof_hi": (60, 56, 48),
                  "roof_lo": (24, 22, 19), "sill": (34, 32, 27), "ledge": (52, 49, 42),
                  "cladding": "stone", "stripe_color": (34, 28, 20), "stripe_w": 4},
}
# Window glass palette: curfew dim. Candle / oil-lamp warm and cold TV
# phosphor, all low intensity - nobody runs bright ceiling lights with KRAP
# sweep teams on the boulevard.
_M4_LIT_WINDOWS = (
    (186, 138, 82), (166, 122, 76), (204, 152, 92), (118, 144, 164),
    (92, 122, 142))
_M4_DARK_WINDOW = (14, 16, 21)
# Curfew window-state odds (residential / storefront).
_M4_LIT_CHANCE = 0.12          # a dim light behind a drawn curtain
_M4_SHOP_LIT_CHANCE = 0.08     # shutter cracked open with a bulb behind it
_M4_BOARD_CHANCE = 0.14        # boarded up: plank strips over the recess
_M4_BROKEN_CHANCE = 0.10       # blown out: dark hole + shard glints + scorch
# Roof prop colours: water tanks, AC units, etc.
_M4_TANK_COLORS = ((58, 50, 42), (46, 50, 55), (64, 55, 45), (40, 43, 47))
_M4_BILLBOARD_COLORS = ((84, 42, 42), (42, 58, 80), (56, 70, 50),
                        (86, 66, 38), (62, 42, 62))

# Ground entrances onto walkable frontage: block_id -> list of (col, edge).
# edge 's' = south wall faces a sidewalk/street below, 'n' = north wall above.
_M4_BLOCK_DOORS = {
    "row_n_b": [(8, "s")],
    "row_n_c": [(13, "s")],
    "row_n_e": [(26, "s")],
    "row_n_g": [(36, "s")],
    "blk_05":    [(2, "s")],
    "blk_07":    [(6, "s"), (8, "s")],
    "blk_11":    [(12, "s")],
    "blk_17":    [(18, "s"), (20, "s")],
    "blk_23":    [(24, "s")],
    "blk_29":    [(30, "s")],
    "blk_35":    [(36, "s")],
    "blk_05b":   [(2, "n")],
    "blk_07b":   [(6, "n")],
    "blk_11b":   [(13, "s")],
    "blk_17b":   [(18, "s")],
    "blk_23b":   [(25, "s")],
    "blk_29b":   [(31, "s")],
    "blk_35b":   [(37, "s")],
    "blvd_s_1":  [(2, "n")],
    "blvd_s_2":  [(6, "n"), (7, "n")],
    "blvd_s_3":  [(13, "n")],
    "blvd_s_4":  [(18, "n"), (19, "n")],
    "blvd_s_5":  [(25, "n")],
    "blvd_s_6":  [(31, "n")],
    "blvd_s_7":  [(36, "n")],
    "blk_r1":    [(2, "s")],
    "blk_r2":    [(7, "s")],
    "blk_r3":    [(13, "s")],
    "blk_r4":    [(19, "s")],
    "blk_r5":    [(25, "s")],
    "blk_r6":    [(31, "s")],
    "blk_r7":    [(37, "s")],
    "blk_s1":    [(2, "n")],
    "blk_s2":    [(7, "n")],
    "blk_s3":    [(13, "n")],
    "blk_s4":    [(19, "n")],
    "blk_s5":    [(25, "n")],
    "blk_s6":    [(31, "n")],
    "blk_s7":    [(37, "n")],
}


def _m4_block_palette(style):
    """(base, shade, hi, mortar, roof, roof_hi, roof_lo, sill, ledge, cladding)."""
    return _M4_WALL_STYLES.get(style, _M4_WALL_STYLES["row"])


def _m4_facade_cladding(surf, bx, by, bw, bh, rnd, pal):
    """Per-style wall texture (drawn before windows so windows sit on top of it).
    Brick: staggered horizontal courses with mortar lines.
    Stone: ashlar block pattern (offset joints, large blocks)."""
    cladding = pal["cladding"]
    base, shade, hi, mortar = pal["base"], pal["shade"], pal["hi"], pal["mortar"]
    if cladding == "brick":
        course_h = 7                          # brick course height
        brick_w = 14                          # brick width
        course = 0
        y = int(by) + 6                        # start a bit down from the cornice
        end_y = int(by + bh) - 4
        while y < end_y:
            offset = (course % 2) * (brick_w // 2)
            # course shadow line (under each course)
            pygame.draw.line(surf, shade, (int(bx) + 2, y + course_h - 1),
                             (int(bx + bw) - 3, y + course_h - 1), 1)
            # mortar between courses
            pygame.draw.line(surf, mortar, (int(bx) + 2, y),
                             (int(bx + bw) - 3, y), 1)
            # vertical mortar (staggered) + per-brick highlight
            x = int(bx) + 2 - offset
            while x < int(bx + bw) - 2:
                if x > int(bx) + 2:
                    pygame.draw.line(surf, mortar, (x, y + 1),
                                     (x, y + course_h - 2), 1)
                if rnd.random() < 0.18:
                    # tiny brick tint variation
                    tint = tuple(min(255, c + rnd.randint(-3, 6))
                                 for c in base)
                    pygame.draw.rect(surf, tint,
                                     (x + 1, y + 1, brick_w - 2, course_h - 3))
                x += brick_w
            # top-of-course hi
            pygame.draw.line(surf, hi, (int(bx) + 2, y + 1),
                             (int(bx + bw) - 3, y + 1), 1)
            y += course_h
            course += 1
    elif cladding == "stone":
        block_h = 18
        block_w = 36
        y = int(by) + 8
        end_y = int(by + bh) - 4
        while y < end_y:
            # ashlar seam
            pygame.draw.line(surf, shade, (int(bx) + 2, y + block_h - 1),
                             (int(bx + bw) - 3, y + block_h - 1), 1)
            offset = ((y // block_h) % 2) * 22
            x = int(bx) + 2 - offset
            while x < int(bx + bw) - 2:
                if x > int(bx) + 2:
                    pygame.draw.line(surf, mortar, (x, y),
                                     (x, y + block_h), 1)
                x += block_w
            y += block_h


def _m4_storey_rows(bh, pal):
    """Visual storey count: one window row per real floor height (~30 px on
    brick tenements, ~40 px on stone civic floors) rather than the block's
    metadata storeys. The metadata cap gave the 576 px station monolith four
    window rows and ~450 px of blank concrete - a prison wall, not a building.
    """
    span = int(bh) - 26
    if span <= 0:
        return 1
    fh = 40 if pal["cladding"] == "stone" else 30
    return max(1, span // fh)


def _m4_floor_band(surf, bx, by, bw, bh, pal, storeys, y_top):
    """Subtle horizontal banding between storeys: a thin shadow + a thin hi.
    Reads as a ledge/sill line on the wall, breaking up the facade into floors.
    Follows the same visual row count as the window grid so ledges and window
    rows stay aligned."""
    rows = _m4_storey_rows(bh, pal)
    if rows < 2:
        return
    span = (bh - 18)
    if span <= 0:
        return
    rh = span / float(rows)
    for ri in range(1, rows):
        y = int(y_top) + int(ri * rh)
        pygame.draw.line(surf, pal["shade"],
                         (int(bx) + 2, y), (int(bx + bw) - 3, y), 1)


def _m4_boarded_panels(surf, x, y, ww, wh, rnd):
    """Plank strips nailed across a dark recess - curfew boarding."""
    pygame.draw.rect(surf, (10, 10, 12), (x, y, ww, wh))
    plank = (52, 44, 36) if rnd.random() < 0.5 else (44, 38, 32)
    n = 2 if wh < 16 else 3
    for i in range(n):
        py = y + 2 + i * (wh - 3) // n
        pygame.draw.line(surf, plank, (x - 1, py), (x + ww, py), 2)
        pygame.draw.line(surf, (30, 26, 22), (x - 1, py + 1), (x + ww, py + 1), 1)
    # diagonal brace
    pygame.draw.line(surf, (48, 40, 34), (x, y + wh - 1), (x + ww - 1, y), 1)


def _m4_broken_glass(surf, x, y, ww, wh, rnd, pal):
    """Blown window: black recess, shard glints in the sill, scorch halo."""
    pygame.draw.rect(surf, (8, 9, 12), (x, y, ww, wh))
    for _ in range(3):
        gx = x + rnd.randint(1, max(1, ww - 2))
        gy = y + rnd.randint(1, max(1, wh - 2))
        surf.set_at((gx, gy), (96, 110, 124))
    pygame.draw.line(surf, (70, 82, 94),
                     (x + 1, y + wh - 2), (x + ww // 2, y + wh - 3), 1)
    sc = pygame.Surface((ww + 8, wh + 6), pygame.SRCALPHA)
    pygame.draw.ellipse(sc, (6, 6, 8, 70), (0, 0, ww + 8, wh + 6))
    sc = pygame.transform.smoothscale(sc, (ww + 8, wh + 6))
    surf.blit(sc, (x - 4, y - 3))


def _m4_window_grid(surf, bx, by, bw, bh, rnd, pal, storeys, storefront_rows):
    """Per-floor window row under curfew: mostly dark glass, a sparse dim
    light behind drawn curtains, boarded and blown-out units. Boulevard-
    facing ground floors get shuttered shop fronts (corrugated slats, torn
    awning scraps, unlit sign plates) instead of the old open market row -
    the stalls are closed on night three of a curfew."""
    rows = _m4_storey_rows(bh, pal)
    if bw < 40 or bh < 30:
        return
    # The window band sits between the cornice (top ~14px) and the ground
    # entrance strip (bottom ~12px). Each floor is one window row.
    top_y = int(by) + 14
    bot_y = int(by + bh) - 12
    span = bot_y - top_y
    if span <= 0:
        return
    rh = span / float(rows)
    for ri in range(rows):
        ry = int(top_y + ri * rh + 3)
        # ground floor that fronts the boulevard: shuttered storefront row
        is_storefront = bool(storefront_rows) and ri == rows - 1
        # windows on this row
        # X spacing per style: apartments are tighter; row houses wider.
        if pal["cladding"] == "brick" and pal["base"][0] > pal["base"][2]:
            # row houses: wider bays
            step = 32
        else:
            step = 28
        # margin: don't paint over the cornice or the side cornice lip
        c0 = int(bx) + 10
        c1 = int(bx + bw) - 10
        x = c0
        while x < c1 - 18:
            if is_storefront:
                ww, wh = 26, 14
                # frame
                pygame.draw.rect(surf, (8, 9, 12), (x, ry, ww, wh))
                if rnd.random() < _M4_SHOP_LIT_CHANCE:
                    # shutter cracked: one dim bulb-slit at the bottom
                    col = _M4_LIT_WINDOWS[rnd.randrange(3)]
                    pygame.draw.rect(surf, (30, 30, 34),
                                     (x + 1, ry + 1, ww - 2, wh - 6))
                    for sly in range(ry + 3, ry + wh - 5, 3):
                        pygame.draw.line(surf, (24, 24, 27),
                                         (x + 1, sly), (x + ww - 2, sly), 1)
                    pygame.draw.rect(surf, col, (x + 1, ry + wh - 5, ww - 2, 4))
                    pygame.draw.line(surf, (8, 9, 12),
                                     (x + ww // 2, ry + wh - 5),
                                     (x + ww // 2, ry + wh - 2), 1)
                    # faint spill on the wet pavement
                    spill = pygame.Surface((ww + 6, 8), pygame.SRCALPHA)
                    for i in range(8):
                        a = int(14 * (1.0 - i / 8.0))
                        pygame.draw.line(spill, (col[0], col[1], col[2], a),
                                         (0, i), (ww + 6, i))
                    surf.blit(spill, (x - 3, ry + wh),
                              special_flags=pygame.BLEND_ADD)
                else:
                    # corrugated shutter down, slats + padlock hasp
                    pygame.draw.rect(surf, (44, 47, 46),
                                     (x + 1, ry + 1, ww - 2, wh - 2))
                    for sly in range(ry + 3, ry + wh - 1, 3):
                        pygame.draw.line(surf, (34, 37, 36),
                                         (x + 1, sly), (x + ww - 2, sly), 1)
                        pygame.draw.line(surf, (56, 60, 58),
                                         (x + 1, sly + 1), (x + ww - 2, sly + 1), 1)
                    pygame.draw.rect(surf, (24, 24, 26),
                                     (x + ww // 2 - 1, ry + wh - 4, 3, 3))
                    # rust streaks from the shutter box
                    pygame.draw.line(surf, (52, 40, 32),
                                     (x + 4, ry + 1), (x + 4, ry + 5), 1)
                # torn awning scraps on some fronts (the old bright market
                # ribs, now ragged and dark)
                if rnd.random() < 0.45:
                    awc = (58, 34, 30) if rnd.random() < 0.5 else (30, 42, 52)
                    axx = x - 1
                    while axx < x + ww + 1:
                        wseg = rnd.randint(3, 7)
                        if rnd.random() < 0.35:      # torn gap
                            axx += wseg
                            continue
                        pygame.draw.rect(surf, awc,
                                         (axx, ry + wh, wseg, rnd.randint(2, 5)))
                        axx += wseg
                # faded unlit sign plate above
                plate_y = ry - 6
                if plate_y > top_y:
                    pygame.draw.rect(surf, (26, 24, 22),
                                     (x - 2, plate_y, ww + 4, 4))
            else:
                # upper or mid-floor residential window
                ww, wh = 12, 14
                # palace gets slightly larger ornamental windows
                if pal["cladding"] == "stone":
                    ww, wh = 16, 18
                roll = rnd.random()
                lit = roll < _M4_LIT_CHANCE
                boarded = not lit and roll < _M4_LIT_CHANCE + _M4_BOARD_CHANCE
                broken = (not lit and not boarded
                          and roll < (_M4_LIT_CHANCE + _M4_BOARD_CHANCE
                                      + _M4_BROKEN_CHANCE))
                if boarded:
                    _m4_boarded_panels(surf, x, ry, ww, wh, rnd)
                elif broken:
                    _m4_broken_glass(surf, x, ry, ww, wh, rnd, pal)
                else:
                    col = (_M4_LIT_WINDOWS[rnd.randrange(len(_M4_LIT_WINDOWS))]
                           if lit else _M4_DARK_WINDOW)
                    # frame
                    pygame.draw.rect(surf, pal["shade"], (x, ry, ww, wh))
                    # glass (slightly inset)
                    pygame.draw.rect(surf, col, (x + 1, ry + 1, ww - 2, wh - 2))
                    # sash line for tall windows (apartments)
                    if wh >= 14 and pal["cladding"] != "stone":
                        pygame.draw.line(surf, pal["shade"],
                                         (x + 1, ry + wh // 2),
                                         (x + ww - 2, ry + wh // 2), 1)
                    # mullion
                    if ww >= 14:
                        pygame.draw.line(surf, pal["shade"],
                                         (x + ww // 2, ry + 1),
                                         (x + ww // 2, ry + wh - 2), 1)
                    if lit:
                        # drawn curtains narrow the glow to a slit
                        pygame.draw.rect(surf, (22, 19, 16),
                                         (x + 1, ry + 1, 3, wh - 2))
                        pygame.draw.rect(surf, (22, 19, 16),
                                         (x + ww - 4, ry + 1, 3, wh - 2))
                    else:
                        # faint cold sky reflection in the dark glass
                        pygame.draw.line(surf, (26, 30, 38),
                                         (x + 2, ry + 2), (x + 3, ry + 3), 1)
                # sill (1px ledge below the window)
                pygame.draw.line(surf, pal["hi"],
                                 (x - 1, ry + wh), (x + ww + 1, ry + wh), 1)
                pygame.draw.line(surf, pal["shade"],
                                 (x - 1, ry + wh + 1), (x + ww + 1, ry + wh + 1), 1)
            x += step + rnd.randint(-3, 4)


def _m4_ground_strip(surf, bx, by, bw, bh, pal, rnd):
    """A bottom strip in a darker tone (shop front band / damp course).
    Sits between the lowest window row and the sidewalk."""
    strip_h = 8
    y = int(by + bh) - strip_h - 1
    pygame.draw.rect(surf, pal["shade"],
                     (int(bx) + 1, y, int(bw) - 2, strip_h))
    pygame.draw.line(surf, pal["mortar"],
                     (int(bx) + 1, y), (int(bx + bw) - 2, y), 1)


def _m4_roof_plate(surf, bx, by, bw, bh, pal, rnd):
    """Roof plate at the TOP of the block: a cornice band + a small parapet
    strip. Does NOT extend down the wall - that would hide the windows."""
    rx, ry = int(bx), int(by)
    rw, rh = int(bw), int(bh)
    roof, roof_hi, roof_lo = pal["roof"], pal["roof_hi"], pal["roof_lo"]
    # Eave overhang: 3 px wider on the left/top edge to suggest a slab thickness.
    cornice_h = 7                          # cornice band height (px)
    # Cornice band (the visible stone lip below the roof).
    pygame.draw.rect(surf, roof_hi, (rx, ry, rw, cornice_h))
    pygame.draw.line(surf, tuple(min(255, c + 24) for c in roof_hi),
                     (rx, ry), (rx + rw - 1, ry), 1)
    pygame.draw.line(surf, roof_lo,
                     (rx, ry + cornice_h - 1),
                     (rx + rw - 1, ry + cornice_h - 1), 1)
    # A slim parapet cap above the cornice, slightly darker (recessed shadow).
    cap_h = 3
    pygame.draw.rect(surf, roof, (rx + 1, ry - cap_h, rw - 2, cap_h))
    pygame.draw.line(surf, roof_hi,
                     (rx + 1, ry - 1), (rx + rw - 2, ry - 1), 1)


def _m4_cornice_shadow(surf, bx, by, bw, bh, pal):
    """Eave drop shadow onto the wall just below the roof band (2 px)."""
    sh = pygame.Surface((int(bw), 3), pygame.SRCALPHA)
    for i in range(3):
        a = int(56 * (1.0 - i / 3.0))
        pygame.draw.line(sh, (0, 0, 0, a), (0, i), (int(bw), i))
    surf.blit(sh, (int(bx), int(by) + 8))


def _m4_facade_weathering(surf, bx, by, bw, bh, rnd, pal):
    """Curfew-night wear on the facade: rain streaks down from the cornice
    and sills, soot blotches, a scorch plume or two, hairline cracks, chipped
    edges and a damp course at the base. One alpha overlay per block, baked
    into the static layer with everything else. The city is coming apart -
    the walls should agree."""
    bw, bh = int(bw), int(bh)
    bx, by = int(bx), int(by)
    if bw < 24 or bh < 24:
        return
    ov = pygame.Surface((bw, bh), pygame.SRCALPHA)
    # 1. Rain streaks: thin cool-dark verticals, denser under the cornice.
    for _ in range(max(3, bw // 22)):
        sx = rnd.randint(2, bw - 3)
        ln = rnd.randint(int(bh * 0.25), int(bh * 0.85))
        a = rnd.randint(12, 24)
        pygame.draw.line(ov, (10, 12, 16, a), (sx, 8), (sx, 8 + ln), 1)
        if rnd.random() < 0.4:   # wet sheen beside the streak
            pygame.draw.line(ov, (120, 140, 160, 9),
                             (sx + 1, 8), (sx + 1, 8 + ln // 2), 1)
    # 2. Soot blotches (soft dark ellipses; bigger on monumental blocks).
    for _ in range(max(2, bw // 90)):
        rx = rnd.randint(6, max(7, bw - 6))
        ry = rnd.randint(10, max(11, bh - 10))
        rr = rnd.randint(10, 26 + min(44, bw // 12))
        bl = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(bl, (8, 8, 10, 46), (0, 0, rr * 2, rr * 2))
        bl = pygame.transform.smoothscale(bl, (rr * 2, rr * 2))
        ov.blit(bl, (rx - rr, ry - rr))
    # 2b. Large-scale damp/grime panels: soft broad dark patches so a big
    # facade never reads as one flat daylight-grey slab.
    for _ in range(max(2, (bw * bh) // 40000)):
        rw = rnd.randint(40, max(41, min(bw, 150)))
        rh2 = rnd.randint(40, max(41, min(bh, 170)))
        rx = rnd.randint(0, max(0, bw - rw))
        ry = rnd.randint(0, max(0, bh - rh2))
        half = pygame.Surface((max(2, rw // 2), max(2, rh2 // 2)),
                              pygame.SRCALPHA)
        pygame.draw.ellipse(half, (7, 8, 10, 34), half.get_rect())
        pn = pygame.transform.smoothscale(half, (rw, rh2))
        ov.blit(pn, (rx, ry))
    # 3. Scorch plume above one blown-out unit (fire damage, washed out).
    if rnd.random() < 0.55:
        sx = rnd.randint(8, max(9, bw - 8))
        sy = rnd.randint(int(bh * 0.3), max(int(bh * 0.3) + 1, int(bh * 0.8)))
        pl = pygame.Surface((26, 40), pygame.SRCALPHA)
        for i in range(40):
            w = 3 + i // 3
            a = int(34 * (1.0 - i / 40.0))
            pygame.draw.line(pl, (6, 6, 7, a),
                             (13 - w // 2 + (i % 3) - 1, 39 - i),
                             (13 + w // 2 + (i % 3) - 1, 39 - i))
        pl = pygame.transform.smoothscale(pl, (26, 40))
        ov.blit(pl, (sx - 13, sy - 40))
    # 4. Hairline cracks.
    for _ in range(1 if bw < 160 else 2):
        cx = rnd.randint(6, max(7, bw - 6))
        cy = rnd.randint(8, max(9, bh - 12))
        pts = [(cx, cy)]
        for _ in range(4):
            cx += rnd.randint(-4, 4)
            cy += rnd.randint(4, 9)
            pts.append((max(1, min(bw - 2, cx)), min(bh - 2, cy)))
        pygame.draw.lines(ov, (12, 12, 14, 120), False, pts, 1)
    # 5. Chipped corners / edges (plaster gone to rubble).
    for _ in range(3):
        edge = rnd.randrange(4)
        if edge == 0:
            cx, cy = rnd.randint(0, bw - 6), 0
        elif edge == 1:
            cx, cy = rnd.randint(0, bw - 6), bh - 4
        elif edge == 2:
            cx, cy = 0, rnd.randint(0, bh - 6)
        else:
            cx, cy = bw - 4, rnd.randint(0, bh - 6)
        pygame.draw.rect(ov, pal["mortar"] + (200,),
                         (cx, cy, rnd.randint(2, 4), rnd.randint(2, 4)))
    # 6. Damp course at the base (rising wet).
    for i in range(10):
        a = int(40 * (1.0 - i / 10.0))
        pygame.draw.line(ov, (6, 8, 10, a),
                         (0, bh - 1 - i), (bw, bh - 1 - i), 1)
    surf.blit(ov, (bx, by))


def _m4_facade_relief(surf, bx, by, bw, bh, pal):
    """1-pixel hi/lo relief around the block silhouette - reads as a 3D edge."""
    rx, ry = int(bx), int(by)
    rw, rh = int(bw), int(bh)
    hi = pal["hi"]
    lo = pal["shade"]
    # north + west: hi (sunward). south + east: lo (shadow).
    pygame.draw.line(surf, hi, (rx, ry), (rx + rw - 1, ry), 1)
    pygame.draw.line(surf, hi, (rx, ry), (rx, ry + rh - 1), 1)
    pygame.draw.line(surf, lo, (rx, ry + rh - 1), (rx + rw - 1, ry + rh - 1), 1)
    pygame.draw.line(surf, lo, (rx + rw - 1, ry), (rx + rw - 1, ry + rh - 1), 1)


def _m4_drop_shadow(surf, bx, by, bw, bh):
    """South-facing soft drop shadow on the walkable row beneath the block."""
    sh = pygame.Surface((int(bw), 12), pygame.SRCALPHA)
    for i in range(12):
        a = int(96 * (1.0 - i / 12.0))
        pygame.draw.line(sh, (0, 0, 0, a), (0, i), (int(bw), i))
    surf.blit(sh, (int(bx), int(by + bh)))


def _m4_roof_props(surf, bx, by, bw, bh, rnd, pal):
    """Roof props: water tank, antenna mast, satellite dish, AC unit, vent
    stacks, stair bulkhead, billboard. Variety scales with block size."""
    pad = 14
    ix0, iy0 = int(bx) + pad, int(by) + pad
    ix1, iy1 = int(bx + bw) - pad, int(by + bh) - pad
    if ix1 - ix0 < 50 or iy1 - iy0 < 30:
        return

    # Water tank on legs.
    if rnd.random() < 0.85:
        tx = rnd.randint(ix0, ix1 - 30)
        ty = rnd.randint(iy0, iy1 - 26)
        col = _M4_TANK_COLORS[rnd.randrange(len(_M4_TANK_COLORS))]
        # legs
        pygame.draw.rect(surf, (24, 22, 20), (tx + 3, ty + 22, 2, 6))
        pygame.draw.rect(surf, (24, 22, 20), (tx + 21, ty + 22, 2, 6))
        # body
        pygame.draw.rect(surf, col, (tx, ty, 26, 22), border_radius=4)
        pygame.draw.rect(surf, tuple(max(0, c - 22) for c in col),
                         (tx, ty, 26, 22), 1, border_radius=4)
        # band seam
        pygame.draw.line(surf, tuple(max(0, c - 14) for c in col),
                         (tx + 1, ty + 9), (tx + 24, ty + 9), 1)
        pygame.draw.line(surf, tuple(min(255, c + 14) for c in col),
                         (tx + 1, ty + 8), (tx + 24, ty + 8), 1)
        # cap
        pygame.draw.rect(surf, tuple(max(0, c - 28) for c in col),
                         (tx - 1, ty - 2, 28, 3), border_radius=1)

    # Antenna mast (TV/radio).
    if rnd.random() < 0.55:
        ax = rnd.randint(ix0, ix1 - 1)
        ay = rnd.randint(iy0 + 4, iy1 - 4)
        height = rnd.randint(22, 36)
        pygame.draw.line(surf, (38, 38, 42), (ax, ay), (ax, ay - height), 1)
        # crossbars
        for cy in range(ay - height + 4, ay, 5):
            pygame.draw.line(surf, (38, 38, 42), (ax - 3, cy), (ax + 3, cy), 1)
        # tip blinker
        pygame.draw.circle(surf, (220, 60, 50), (ax, ay - height), 1)

    # Satellite dish (small parabola silhouette).
    if rnd.random() < 0.35:
        dx_ = rnd.randint(ix0, ix1 - 14)
        dy_ = rnd.randint(iy0, iy1 - 12)
        pygame.draw.ellipse(surf, (88, 88, 96), (dx_, dy_, 14, 10))
        pygame.draw.ellipse(surf, (44, 44, 50), (dx_, dy_, 14, 10), 1)
        pygame.draw.line(surf, (44, 44, 50), (dx_ + 7, dy_ + 5),
                         (dx_ + 7, dy_ + 14), 1)
        pygame.draw.line(surf, (44, 44, 50), (dx_ + 6, dy_ + 14),
                         (dx_ + 8, dy_ + 14), 1)

    # AC condenser box.
    if rnd.random() < 0.55:
        cx = rnd.randint(ix0, ix1 - 22)
        cy = rnd.randint(iy0, iy1 - 14)
        pygame.draw.rect(surf, (96, 100, 106), (cx, cy, 22, 14), border_radius=1)
        pygame.draw.rect(surf, (52, 56, 62), (cx, cy, 22, 14), 1, border_radius=1)
        # grille
        for gx in range(cx + 2, cx + 20, 3):
            pygame.draw.line(surf, (40, 44, 50),
                             (gx, cy + 3), (gx, cy + 11), 1)
        # fan circle
        pygame.draw.circle(surf, (32, 36, 42), (cx + 11, cy + 7), 4, 1)

    # Vent stacks (1-3).
    for _ in range(rnd.randint(1, 3)):
        vx = rnd.randint(ix0, ix1 - 8)
        vy = rnd.randint(iy0, iy1 - 8)
        pygame.draw.rect(surf, (44, 44, 48), (vx, vy, 6, 8))
        pygame.draw.rect(surf, (28, 28, 32), (vx, vy, 6, 8), 1)
        pygame.draw.line(surf, (60, 60, 66), (vx, vy), (vx + 6, vy), 1)
        pygame.draw.line(surf, (60, 60, 66), (vx + 1, vy + 4),
                         (vx + 5, vy + 4), 1)

    # Stair bulkhead (roof access).
    if rnd.random() < 0.55:
        sx = rnd.randint(ix0, ix1 - 22)
        sy = rnd.randint(iy0, iy1 - 18)
        pygame.draw.rect(surf, pal["shade"], (sx, sy, 20, 16))
        pygame.draw.rect(surf, pal["mortar"], (sx, sy, 20, 16), 1)
        pygame.draw.line(surf, pal["mortar"], (sx, sy + 8),
                         (sx + 20, sy + 8), 1)
        pygame.draw.line(surf, pal["hi"], (sx, sy + 1),
                         (sx + 19, sy + 1), 1)
        # door
        pygame.draw.rect(surf, (16, 14, 18), (sx + 7, sy + 9, 6, 7))

    # Billboard / sign frame on the roof (clothesline variant instead - a
    # thin taut line between two posts with small hanging squares of fabric).
    if rnd.random() < 0.30 and (ix1 - ix0) > 80 and (iy1 - iy0) > 30:
        bx_ = rnd.randint(ix0, ix1 - 30)
        by_ = rnd.randint(iy0, iy1 - 14)
        pygame.draw.line(surf, (28, 24, 22),
                         (bx_, by_ + 12), (bx_ + 30, by_ + 12), 1)
        # posts
        pygame.draw.line(surf, (60, 50, 40),
                         (bx_, by_ + 6), (bx_, by_ + 16), 1)
        pygame.draw.line(surf, (60, 50, 40),
                         (bx_ + 30, by_ + 6), (bx_ + 30, by_ + 16), 1)
        # hanging laundry - curfew version: a couple of ragged dark scraps
        # nobody collected, not a full line of bright washing
        for j, lcol in enumerate(((92, 58, 50), (52, 66, 80),
                                  (88, 86, 78), (64, 54, 46))):
            if rnd.random() < 0.45:
                continue
            lx = bx_ + 2 + j * 7
            pygame.draw.rect(surf, lcol, (lx, by_ + 12, 5, rnd.randint(3, 5)))

    # Roof garden chair / table - rare now: a tipped chair nobody stacked.
    if rnd.random() < 0.07 and (ix1 - ix0) > 60 and (iy1 - iy0) > 40:
        cx = rnd.randint(ix0, ix1 - 18)
        cy = rnd.randint(iy0, iy1 - 14)
        pygame.draw.rect(surf, (56, 48, 40), (cx, cy + 4, 18, 10),
                         border_radius=1)
        pygame.draw.rect(surf, (36, 30, 26), (cx, cy + 4, 18, 10), 1,
                         border_radius=1)
        pygame.draw.line(surf, (36, 30, 26), (cx + 2, cy + 4),
                         (cx + 2, cy + 8), 1)
        pygame.draw.line(surf, (36, 30, 26), (cx + 16, cy + 4),
                         (cx + 16, cy + 8), 1)
        # chair back
        pygame.draw.line(surf, (56, 48, 40), (cx - 2, cy + 4),
                         (cx - 2, cy - 4), 1)

    # Solar panel (two thin angled rectangles).
    if rnd.random() < 0.20 and (ix1 - ix0) > 50:
        sx_ = rnd.randint(ix0, ix1 - 22)
        sy_ = rnd.randint(iy0, iy1 - 12)
        pygame.draw.polygon(surf, (40, 54, 80),
                            [(sx_, sy_ + 8), (sx_ + 20, sy_),
                             (sx_ + 22, sy_ + 4), (sx_ + 2, sy_ + 12)])
        pygame.draw.polygon(surf, (24, 34, 54),
                            [(sx_, sy_ + 8), (sx_ + 20, sy_),
                             (sx_ + 22, sy_ + 4), (sx_ + 2, sy_ + 12)], 1)
        # grid lines
        pygame.draw.line(surf, (60, 74, 100),
                         (sx_ + 4, sy_ + 10), (sx_ + 12, sy_ + 5), 1)
        pygame.draw.line(surf, (60, 74, 100),
                         (sx_ + 10, sy_ + 12), (sx_ + 18, sy_ + 7), 1)

    # Chimney (brick, vertical).
    if rnd.random() < 0.40 and (ix1 - ix0) > 40:
        chx = rnd.randint(ix0, ix1 - 8)
        chy = rnd.randint(iy0, iy1 - 12)
        pygame.draw.rect(surf, (58, 48, 42), (chx, chy, 8, 12))
        pygame.draw.rect(surf, (36, 30, 26), (chx, chy, 8, 12), 1)
        pygame.draw.line(surf, (76, 64, 52),
                         (chx, chy + 4), (chx + 8, chy + 4), 1)
        pygame.draw.line(surf, (76, 64, 52),
                         (chx, chy + 8), (chx + 8, chy + 8), 1)
        # chimney cap
        pygame.draw.rect(surf, (30, 26, 22), (chx - 1, chy - 1, 10, 2))


def _m4_horizontal_stripe(surf, bx, by, bw, bh, pal):
    """Civic palace: ornamental banded stripe between two storeys."""
    if pal.get("stripe_w", 0) <= 0:
        return
    rx, ry = int(bx), int(by)
    rw, rh = int(bw), int(bh)
    if rh < 80:
        return
    band_y = ry + rh // 2 - 2
    pygame.draw.rect(surf, pal["stripe_color"],
                     (rx, band_y, rw, pal["stripe_w"]))
    pygame.draw.line(surf, pal["hi"],
                     (rx, band_y - 1), (rx + rw - 1, band_y - 1), 1)
    pygame.draw.line(surf, pal["shade"],
                     (rx, band_y + pal["stripe_w"]),
                     (rx + rw - 1, band_y + pal["stripe_w"]), 1)


def _m4_draw_roof_props(*args, **kwargs):
    """Deprecated: roof props now drawn inline by _m4_roof_props()."""
    return None


def _m4_draw_storefront(surf, ex, ey, vertical, rnd):
    """One ground entrance: recessed dark doorway + frame + a practical lamp.
    Curfew: only a minority of doors still have a working lamp, and those run
    dim - the rest are dead fixtures over a black recess."""
    lit = rnd.random() < 0.30
    bulb = (214, 178, 120) if lit else (44, 40, 34)
    if vertical:
        # Wall horizontal along x; door centered at ex (tile col center).
        dw, dh = 26, 16
        dx = ex - dw // 2
        dy = ey - 2
        pygame.draw.rect(surf, (10, 9, 12), (dx, dy, dw, dh))
        pygame.draw.rect(surf, (74, 62, 48), (dx, dy, dw, dh), 1)
        # transom
        pygame.draw.line(surf, (74, 62, 48), (dx, dy + 4), (dx + dw, dy + 4), 1)
        # practical above the lintel
        lx, ly = ex, dy - 4
        pygame.draw.circle(surf, bulb, (lx, ly), 2)
        if lit:
            pool = pygame.Surface((dw + 18, 22), pygame.SRCALPHA)
            for i in range(22):
                a = int(26 * (1.0 - i / 22.0))
                pygame.draw.line(pool, (214, 170, 110, a),
                                 (0, dy + dh + i - (dy - 4)),
                                 (dw + 18, dy + dh + i - (dy - 4)))
            surf.blit(pool, (dx - 9, dy + dh), special_flags=pygame.BLEND_ADD)
    else:
        # Wall vertical along y; door on east or west face at ey (row center).
        dw, dh = 16, 26
        dx = ex - 2
        dy = ey - dh // 2
        pygame.draw.rect(surf, (10, 9, 12), (dx, dy, dw, dh))
        pygame.draw.rect(surf, (74, 62, 48), (dx, dy, dw, dh), 1)
        pygame.draw.line(surf, (74, 62, 48), (dx + 4, dy), (dx + 4, dy + dh), 1)
        lx, ly = dx + dw + 4, ey
        pygame.draw.circle(surf, bulb, (lx, ly), 2)
        if lit:
            pool = pygame.Surface((22, dh + 18), pygame.SRCALPHA)
            for i in range(22):
                a = int(26 * (1.0 - i / 22.0))
                pygame.draw.line(pool, (214, 170, 110, a),
                                 (i, 0), (i, dh + 18))
            surf.blit(pool, (dx + dw, dy - 9), special_flags=pygame.BLEND_ADD)


def _draw_m4_buildings(surface, cam_x, cam_y):
    """Stamp authored building art over the C field for every block whose
    footprint intersects the view. Seeded by block id -> deterministic."""
    T = TILE_SIZE
    vw, vh = WIDTH, HEIGHT
    for blk in M4_BLOCKS:
        bid, bx, by, bw, bh, style, storeys = blk
        px, py = bx * T - cam_x, by * T - cam_y
        pw, ph = bw * T, bh * T
        if px > vw or py > vh or px + pw < 0 or py + ph < 0:
            continue
        pal = _m4_block_palette(style)
        rnd = random.Random(_stable_seed(bid))
        # 1. Wall plate (the facade itself, base colour).
        pygame.draw.rect(surface, pal["base"], (px, py, pw, ph))
        # 2. Per-style wall cladding (brick courses or ashlar seams).
        _m4_facade_cladding(surface, px, py, pw, ph, rnd, pal)
        # 3. Subtle storey banding (ledge lines between windows).
        _m4_floor_band(surface, px, py, pw, ph, pal, storeys, py + 12)
        # 4. Window grid (per-storey windows or storefront row).
        storefront = (by + bh == SIDEWALK_N) or (by == SIDEWALK_S + 1)
        _m4_window_grid(surface, px, py, pw, ph, rnd, pal, storeys, storefront)
        # 5. Ground strip (shop base / damp course).
        _m4_ground_strip(surface, px, py, pw, ph, pal, rnd)
        # 6. Civic palace ornament: horizontal band stripe.
        _m4_horizontal_stripe(surface, px, py, pw, ph, pal)
        # 7. Roof plate (sits ABOVE the wall but in tile space the wall is
        #    already drawn over the full block; we draw the cornice band at the
        #    top and an eaves shadow below it).
        _m4_roof_plate(surface, px, py, pw, ph, pal, rnd)
        _m4_cornice_shadow(surface, px, py, pw, ph, pal)
        # 7b. Curfew wear: rain streaks, soot, scorch, cracks, damp base.
        _m4_facade_weathering(surface, px, py, pw, ph, rnd, pal)
        # 8. Roof props (water tank, antenna, dish, AC, vents, bulkhead, billboard).
        _m4_roof_props(surface, px, py, pw, ph, rnd, pal)
        # 9. Edge relief (1px hi/lo) for 3D silhouette.
        _m4_facade_relief(surface, px, py, pw, ph, pal)
        # 10. Drop shadow onto the walkable row south of the block.
        _m4_drop_shadow(surface, px, py, pw, ph)
        # 11. Ground entrances.
        for dcol, edge in _M4_BLOCK_DOORS.get(bid, ()):
            ex = dcol * T + T // 2 - cam_x
            ey = py + ph if edge == "s" else py
            _m4_draw_storefront(surface, ex, ey, True, rnd)

    # Radio station: monumental civic block - limestone with colonnade windows,
    # big satellite dish + radio mast on the roof, an inscribed frieze band,
    # and a lit "KRAPNET" marquee over the west door.
    sc, sr, sw, sh = STATION_BLOCK
    bx, by = sc * T - cam_x, sr * T - cam_y
    bw, bh = sw * T, sh * T
    if not (bx > vw or by > vh or bx + bw < 0 or by + bh < 0):
        pal = _M4_WALL_STYLES["palace"]
        rnd = random.Random(_stable_seed("station"))
        # Wall plate
        pygame.draw.rect(surface, pal["base"], (bx, by, bw, bh))
        # Stone cladding (ashlar)
        _m4_facade_cladding(surface, bx, by, bw, bh, rnd, pal)
        # Floor banding + 4-storey window grid (colonnade-like, tight windows)
        _m4_floor_band(surface, bx, by, bw, bh, pal, 4, by + 14)
        _m4_window_grid(surface, bx, by, bw, bh, rnd, pal, 4, False)
        # Civic ornament: heavy horizontal frieze band (entablature).
        band_y = by + bh // 2 - 4
        pygame.draw.rect(surface, (96, 76, 50),
                         (bx + 2, band_y, bw - 4, 6))
        pygame.draw.line(surface, pal["hi"],
                         (bx + 2, band_y - 1), (bx + bw - 3, band_y - 1), 1)
        pygame.draw.line(surface, pal["shade"],
                         (bx + 2, band_y + 6), (bx + bw - 3, band_y + 6), 1)
        # Pilasters (vertical strips every 1.5 tiles along the long faces).
        for pc in range(sc + 1, sc + sw, 2):
            px = pc * T - cam_x
            pygame.draw.rect(surface, pal["shade"], (px - 2, by + 4, 4, bh - 12))
            pygame.draw.line(surface, pal["hi"], (px - 2, by + 4),
                             (px - 2, by + bh - 8), 1)
            pygame.draw.line(surface, pal["shade"], (px + 1, by + 4),
                             (px + 1, by + bh - 8), 1)
        # Plinth + cornice
        _m4_ground_strip(surface, bx, by, bw, bh, pal, rnd)
        _m4_roof_plate(surface, bx, by, bw, bh, pal, rnd)
        _m4_cornice_shadow(surface, bx, by, bw, bh, pal)
        # Curfew wear on the civic monolith too.
        _m4_facade_weathering(surface, bx, by, bw, bh, rnd, pal)
        # Roof props: regular ones plus bigger station-specific extras.
        _m4_roof_props(surface, bx, by, bw, bh, rnd, pal)
        # Big parabolic satellite dish (the actual antenna).
        dx = (sc + 3) * T - cam_x
        dy = (sr + 2) * T - cam_y
        pygame.draw.ellipse(surface, (110, 112, 120), (dx, dy, 32, 22))
        pygame.draw.ellipse(surface, (66, 66, 74), (dx, dy, 32, 22), 1)
        pygame.draw.line(surface, (44, 44, 50), (dx + 16, dy + 11),
                         (dx + 16, dy + 28), 2)
        pygame.draw.ellipse(surface, (150, 152, 160), (dx + 13, dy + 8, 6, 4))
        # Big radio mast with cross-struts.
        ax = (sc + 2) * T + T // 2 - cam_x
        ay = (sr + 2) * T - cam_y
        pygame.draw.line(surface, (60, 60, 66), (ax, ay), (ax, ay - 60), 1)
        # Truss lines (zigzag pattern).
        for k in range(0, 60, 4):
            ofs = 3 if (k // 4) % 2 == 0 else -3
            pygame.draw.line(surface, (54, 54, 60),
                             (ax - ofs, ay - k), (ax + ofs, ay - k - 4), 1)
        # Aviation warning blinker.
        pygame.draw.circle(surface, (220, 60, 50), (ax, ay - 60), 2)
        # Two flagpoles at the south edge of the roof.
        for fx in (sc + 1, sc + 3):
            x = fx * T + T // 2 - cam_x
            y = (sr + 1) * T - cam_y
            pygame.draw.line(surface, (110, 110, 116), (x, y), (x, y - 38), 2)
            pygame.draw.line(surface, (140, 140, 148), (x, y - 38),
                             (x, y - 32), 1)
            pygame.draw.polygon(surface, (160, 50, 50),
                                [(x, y - 38), (x + 18, y - 32), (x, y - 26)])
            pygame.draw.line(surface, (200, 130, 130), (x, y - 34),
                             (x + 14, y - 30), 1)
        # Grand entrance: canopy + big lit RADIO marquee over the west door,
        # warm light spilling out onto the boulevard, and two banner pylons
        # framing the opening so it reads as "go in here" from down the street.
        mx = sc * T - cam_x
        my = 19 * T - cam_y + T // 2
        # Warm spill on the boulevard in front of the door (two soft pools,
        # drawn before the canopy so the architecture sits on top of the glow).
        spill = pygame.Surface((150, 76), pygame.SRCALPHA)
        pygame.draw.ellipse(spill, (255, 186, 115, 40),
                            (8, 10, 134, 56))
        pygame.draw.ellipse(spill, (255, 200, 140, 26),
                            (34, 20, 82, 36))
        surface.blit(spill, (mx - 148, my - 34))
        # Flanking banner pylons on the west face (rows 18 and 20): dark
        # posts with orange pennants + a warm uplight dot at each base.
        for prou in (18, 20):
            px = sc * T - cam_x + 6
            py = prou * T - cam_y + 8
            pygame.draw.rect(surface, (26, 24, 22), (px - 2, py, 5, 50))
            pygame.draw.rect(surface, (74, 62, 48), (px - 2, py, 5, 50), 1)
            pygame.draw.polygon(surface, (196, 110, 40),
                                [(px - 2, py + 4), (px + 22, py + 10),
                                 (px - 2, py + 16)])
            pygame.draw.circle(surface, (255, 200, 130), (px, py + 52), 3)
            halo = pygame.Surface((30, 18), pygame.SRCALPHA)
            pygame.draw.ellipse(halo, (255, 190, 120, 30), halo.get_rect())
            surface.blit(halo, (px - 15, py + 44))
        # Stone canopy above the door (deeper overhang).
        pygame.draw.rect(surface, pal["shade"], (mx - 8, my - 40, 48, 8))
        pygame.draw.line(surface, pal["hi"],
                         (mx - 8, my - 40), (mx + 39, my - 40), 1)
        pygame.draw.line(surface, pal["mortar"],
                         (mx - 8, my - 32), (mx + 39, my - 32), 1)
        # Big lit marquee plate with a real sign on it.
        sign = font_terminal_small.render(_T("m4.radio"), True, (255, 214, 150))
        plate_w = max(120, sign.get_width() + 44)
        plate_x = mx + 14 - plate_w // 2
        pygame.draw.rect(surface, (22, 20, 24),
                         (plate_x, my - 32, plate_w, 20))
        pygame.draw.rect(surface, (180, 160, 90),
                         (plate_x, my - 32, plate_w, 20), 1)
        pygame.draw.line(surface, (210, 190, 110),
                         (plate_x, my - 31), (plate_x + plate_w - 1, my - 31), 1)
        surface.blit(sign, (mx + 14 - sign.get_width() // 2, my - 29))
        # Lit bulb dots along the bottom edge of the marquee.
        for i in range(plate_w // 9):
            pygame.draw.circle(surface, (255, 224, 150),
                               (plate_x + 5 + i * 9, my - 14), 2)
        _m4_draw_storefront(surface, mx + 14, my + 32, True, rnd)
        # Edge relief + drop shadow.
        _m4_facade_relief(surface, bx, by, bw, bh, pal)
        _m4_drop_shadow(surface, bx, by, bw, bh)


def _draw_m4_objective_beacons(surface, cam_x, cam_y):
    """Per-frame pulsing outline on the objective fixtures (V/T/J/N + the
    street station door once the cache is in hand). Kept out of the tile blit
    so it animates with time and the later static bake stays deterministic
    (mirrors m3's dynamic-tile split)."""
    g = _m4_maps.MISSION4_MAP
    h = len(g)
    w = len(g[0]) if h else 0
    x0 = max(0, cam_x // TILE_SIZE)
    y0 = max(0, cam_y // TILE_SIZE)
    x1 = min(w, (cam_x + WIDTH) // TILE_SIZE + 1)
    y1 = min(h, (cam_y + HEIGHT) // TILE_SIZE + 1)
    a = 150 + int(math.sin(_now_s() * 3.0) * 70)
    street = not _m4_is_station(g)
    stage = getattr(STATE, "mission4_stage", "")
    door_armed = (street and stage == STAGE_AFTERMATH
                  and getattr(STATE, "m4_cache_taken", False))
    for row in range(y0, y1):
        grow = g[row]
        for col in range(x0, x1):
            ch = grow[col]
            if ch == "D" and door_armed and (col, row) == STATION_DOOR_TILE:
                ct = (255, 200, 90, a)  # gold: this is the way in
            elif ch in ("V", "T", "J", "N"):
                if ch == "V" and getattr(STATE, "m4_cache_taken", False):
                    continue  # drop already collected - no beacon on empty sidewalk
                ct = (170, 210, 250, a)
            else:
                continue
            sx = col * TILE_SIZE - cam_x
            sy = row * TILE_SIZE - cam_y
            hl = pygame.Surface((TILE_SIZE - 16, TILE_SIZE - 16), pygame.SRCALPHA)
            r = hl.get_rect()
            tick = 12
            # Corner brackets, not a closed rect - reads as a fixture marker
            # without the floating white box the full outline looked like.
            for px, py, dx, dy in ((0, 0, 1, 1), (r.right - 1, 0, -1, 1),
                                   (0, r.bottom - 1, 1, -1),
                                   (r.right - 1, r.bottom - 1, -1, -1)):
                pygame.draw.line(hl, ct, (px, py), (px + dx * tick, py), 2)
                pygame.draw.line(hl, ct, (px, py), (px, py + dy * tick), 2)
            surface.blit(hl, (sx + 8, sy + 8))


def _draw_m4_street_arrow(surface, cam_x, cam_y):
    """One off-screen edge arrow, pointing at the CURRENT street step only.

    Ported from m3.systems._draw_comms_step_arrow (values local, module not
    imported): silent while the target is on screen, so the player is pulled
    to one object at a time instead of everything at once. Cache first, then
    the station door - matching the objective text ladder in flow.py.
    """
    if _m4_is_station(_m4_maps.MISSION4_MAP):
        return
    if getattr(STATE, "mission4_stage", "") != STAGE_AFTERMATH:
        return
    if STATE.player is None:
        return
    if not getattr(STATE, "m4_cache_taken", False):
        wx, wy = _vasile_cache_pos()
        label = "CACHE"
    else:
        wx, wy = _street_door_pos()
        label = "STATION"
    sx, sy = wx - cam_x, wy - cam_y
    m = 64
    if m <= sx <= WIDTH - m and m <= sy <= HEIGHT - m:
        return
    cx = min(max(sx, m), WIDTH - m)
    cy = min(max(sy, m), HEIGHT - m)
    ang = math.atan2(sy - cy, sx - cx)
    pts = [(cx + math.cos(ang) * 15, cy + math.sin(ang) * 15),
           (cx + math.cos(ang + 2.5) * 9, cy + math.sin(ang + 2.5) * 9),
           (cx + math.cos(ang - 2.5) * 9, cy + math.sin(ang - 2.5) * 9)]
    pulse = 170 + int(60 * math.sin(_now_s() * 5.0))
    pygame.draw.polygon(surface, (255, 200, 90), pts)
    pygame.draw.polygon(surface, (pulse, pulse // 2, 40), pts, 1)
    tag = font_terminal_small.render(label, True, (255, 214, 150))
    shadow = font_terminal_small.render(label, True, (0, 0, 0))
    tx = min(max(cx - tag.get_width() // 2, 8), WIDTH - tag.get_width() - 8)
    surface.blit(shadow, (tx + 1, cy + 17))
    surface.blit(tag, (tx, cy + 16))


# ── Vasile's comms cache: bespoke drop sprite ────────────────────────────
# The W1 drop used to blit the generic ``prop_crate`` art, which read as
# "a crate" instead of "the KRAP comms cache". This is a purpose-built prop:
# olive hard case with brass latches + corner irons, a lid stencil, a field
# transceiver strapped on top with a coiled whip antenna, and a blink LED
# (drawn live over the cached sprite so it pulses).
def _m4_draw_cache_prop(s):
    # ground shadow
    pygame.draw.ellipse(s, (14, 16, 14, 170), (8, 46, 48, 14))
    # case body + lid
    pygame.draw.rect(s, (56, 64, 46), (12, 28, 40, 26), border_radius=3)
    pygame.draw.rect(s, (40, 47, 34), (12, 40, 40, 14), border_radius=2)
    pygame.draw.line(s, (74, 84, 62), (13, 29), (51, 29), 1)
    pygame.draw.line(s, (28, 33, 26), (12, 40), (52, 40), 1)
    # corner irons
    for cx in (12, 48):
        pygame.draw.rect(s, (86, 84, 74), (cx, 28, 4, 6))
        pygame.draw.rect(s, (86, 84, 74), (cx, 48, 4, 6))
    # brass latches
    for lx in (22, 38):
        pygame.draw.rect(s, (146, 128, 74), (lx, 37, 4, 7))
        pygame.draw.line(s, (96, 82, 44), (lx, 40), (lx + 3, 40), 1)
    # lid stencil band (KRAP chevron)
    pygame.draw.rect(s, (196, 192, 176), (17, 31, 14, 6))
    pygame.draw.polygon(s, (56, 64, 46), [(19, 32), (24, 34), (19, 36)])
    pygame.draw.line(s, (196, 192, 176), (34, 32), (46, 32), 1)
    pygame.draw.line(s, (196, 192, 176), (34, 35), (43, 35), 1)
    # carry handle
    pygame.draw.line(s, (30, 34, 26), (26, 27), (38, 27), 2)
    pygame.draw.line(s, (30, 34, 26), (26, 27), (26, 29), 2)
    pygame.draw.line(s, (30, 34, 26), (38, 27), (38, 29), 2)
    # field transceiver strapped on the lid
    pygame.draw.rect(s, (34, 36, 40), (30, 16, 18, 12), border_radius=2)
    pygame.draw.rect(s, (24, 26, 30), (30, 22, 18, 6), border_radius=2)
    pygame.draw.circle(s, (120, 130, 140), (35, 20), 2)
    pygame.draw.line(s, (90, 100, 110), (40, 19), (45, 19), 1)
    pygame.draw.line(s, (90, 100, 110), (40, 21), (45, 21), 1)
    # strap over the case
    pygame.draw.line(s, (46, 40, 32), (30, 28), (30, 54), 2)
    pygame.draw.line(s, (46, 40, 32), (44, 28), (44, 54), 2)
    # coiled whip antenna
    pts = [(48, 16)]
    for k in range(6):
        pts.append((48 + (3 if k % 2 == 0 else -3), 16 - k * 3))
    pygame.draw.lines(s, (70, 74, 80), False, pts, 1)
    pygame.draw.line(s, (70, 74, 80), (48, 16), (46, 18), 1)


def _m4_cache_sprite():
    return artpack.pose(("m4_cache_v2",), (64, 64), _m4_draw_cache_prop)


def _draw_m4_cache_prop_world(surface, cam_x, cam_y):
    """Dynamic pass: the cache prop + live blink LED (street map only, until
    picked up). Kept out of the static bake so pickup removes it for good."""
    if _m4_is_station(_m4_maps.MISSION4_MAP):
        return
    if getattr(STATE, "m4_cache_taken", False):
        return
    tx, ty = VASILE_CACHE_TILE
    sx = tx * TILE_SIZE - cam_x
    sy = ty * TILE_SIZE - cam_y
    if not (-70 < sx < WIDTH + 70 and -70 < sy < HEIGHT + 70):
        return
    surface.blit(_m4_cache_sprite(), (sx, sy))
    lit = (int(_now_s() * 2.4) % 2) == 0
    pygame.draw.circle(surface, (130, 255, 150) if lit else (44, 92, 54),
                       (sx + 35, sy + 20), 2)


# ── static-layer bake + night lighting + rain + world dressing ──
#    (ported from the m3/draw bake + lighting + exterior-ground idioms; the m3
#    module is NOT imported - those globals are mission-scoped). Everything
#    degrades to the direct sprite blit when the art/static tiers are off.
_M4_CAM = [0, 0]
# Open exterior ground the world-space dressing pass treats as wearable.
_GROUND_OPEN = (".", "d", "g")
_GROUND_SOLID = ("C", "B", "D")
_GROUND_BLOB_SIZES = (96, 112, 128)
_GROUND_BLOB_CELL = 5
_GROUND_BLOB_CHANCE = 0.6
_GROUND_BLOB_TRIES = 3
_GROUND_AO_DEPTH = 14
_M4_GROUND_BLOBS = {}
_M4_GROUND_AO = {}


def _m4_wing_name():
    return "m4station" if _m4_is_station(_m4_maps.MISSION4_MAP) else "m4street"


def _m4_doors_sig():
    return render_util.doors_anim_sig(getattr(STATE, "doors", ()))


def _m4_solid_world(wx, wy):
    """Light-blocking predicate over the M4 grid (walls, barricades, doors).
    Out-of-bounds reads as solid so light stops at the map edge."""
    g = _m4_maps.MISSION4_MAP
    tx = int(wx) // TILE_SIZE
    ty = int(wy) // TILE_SIZE
    h = len(g)
    w = len(g[0]) if h else 0
    if not (0 <= tx < w and 0 <= ty < h):
        return True
    return g[ty][tx] in _GROUND_SOLID


def _m4_static_layer():
    g = _m4_maps.MISSION4_MAP
    mh = len(g)
    mw = len(g[0]) if mh else 0
    # Keyed on map identity + wing so a street<->station swap drops the old
    # chunks and a restart never reuses a stale bake.
    sig = (id(g), _m4_wing_name())
    return staticlayer.get_layer("m4", sig, mw * TILE_SIZE, mh * TILE_SIZE)


def _bake_m4_static(surf, ox, oy):
    # Station skirting + furniture are deterministic and opaque -> part of the static layer
    # (RPE6 Phase 3); on the street map _draw_m4_station_dressing is a no-op.
    render_util.swap_screen(globals(), surf, lambda: (
        _draw_m4_floor_and_walls(surf, ox, oy),
        _draw_m4_ground_dressing(ox, oy),
        _draw_m4_station_dressing(surf, ox, oy)))


def _m4_ground_blob(dark, size):
    """Cached soft radial blotch for world-space ground tone."""
    key = (dark, size)
    spr = _M4_GROUND_BLOBS.get(key)
    if spr is None:
        spr = pygame.Surface((size, size), pygame.SRCALPHA)
        cx = cy = size // 2
        ink = (8, 8, 10) if dark else (232, 236, 242)
        peak = 24 if dark else 30
        for r in range(cx, 0, -1):
            a = int(peak * (1.0 - r / float(cx)) ** 1.7)
            if a <= 0:
                continue
            pygame.draw.circle(spr, (ink[0], ink[1], ink[2], a), (cx, cy), r)
        _M4_GROUND_BLOBS[key] = spr
    return spr


def _m4_ground_ao(edge):
    """Cached contact-shadow band along one ground edge ('n','s','w','e')."""
    spr = _M4_GROUND_AO.get(edge)
    if spr is None:
        depth = _GROUND_AO_DEPTH
        size = (depth, TILE_SIZE) if edge in ("w", "e") else (TILE_SIZE, depth)
        spr = pygame.Surface(size, pygame.SRCALPHA)
        for i in range(depth):
            a = int(72 * (1.0 - i / float(depth)) ** 1.5)
            if a <= 0:
                continue
            if edge == "n":
                pygame.draw.line(spr, (0, 0, 0, a), (0, i), (TILE_SIZE - 1, i))
            elif edge == "s":
                pygame.draw.line(spr, (0, 0, 0, a),
                                 (0, depth - 1 - i), (TILE_SIZE - 1, depth - 1 - i))
            elif edge == "w":
                pygame.draw.line(spr, (0, 0, 0, a), (i, 0), (i, TILE_SIZE - 1))
            else:
                pygame.draw.line(spr, (0, 0, 0, a),
                                 (depth - 1 - i, 0), (depth - 1 - i, TILE_SIZE - 1))
        _M4_GROUND_AO[edge] = spr
    return spr


def _m4_open_block(g, tc, tr, reach):
    """True when the whole (2*reach+1) tile square is open exterior ground."""
    h = len(g)
    w = len(g[0]) if h else 0
    if tc - reach < 0 or tr - reach < 0 or tc + reach >= w or tr + reach >= h:
        return False
    for row in range(tr - reach, tr + reach + 1):
        map_row = g[row]
        for col in range(tc - reach, tc + reach + 1):
            if map_row[col] not in _GROUND_OPEN:
                return False
    return True


def _draw_m4_ground_dressing(cam_x, cam_y):
    """Deterministic world-space wear on the curfew street: tone blotches,
    wall-base contact shadow and sparse scuffs/chips. Seeded by position
    (never time) so the bake stays reproducible; gated to open ground so the
    station interior stays clean."""
    g = _m4_maps.MISSION4_MAP
    mh = len(g)
    mw = len(g[0]) if mh else 0
    x0 = max(0, int(cam_x // TILE_SIZE) - 1)
    x1 = min(mw, int((cam_x + WIDTH) // TILE_SIZE) + 2)
    y0 = max(0, int(cam_y // TILE_SIZE) - 1)
    y1 = min(mh, int((cam_y + HEIGHT) // TILE_SIZE) + 2)

    # 1. Tone blotches - one seeded slot per cell square, jittered inside so
    #    the slots never read as a lattice.
    cell = _GROUND_BLOB_CELL
    for crow in range(y0 // cell - 1, y1 // cell + 2):
        for ccol in range(x0 // cell - 1, x1 // cell + 2):
            rnd = random.Random(ccol * 2750159 + crow * 76841)
            if rnd.random() > _GROUND_BLOB_CHANCE:
                continue
            spot = None
            for _ in range(_GROUND_BLOB_TRIES):
                tc = ccol * cell + rnd.randrange(0, cell)
                tr = crow * cell + rnd.randrange(0, cell)
                if _m4_open_block(g, tc, tr, 1):
                    spot = (tc, tr, rnd.choice(_GROUND_BLOB_SIZES),
                            rnd.random() < 0.30)
                    break
            if spot is None:
                continue
            tc, tr, size, dark = spot
            spr = _m4_ground_blob(dark, size)
            bx = tc * TILE_SIZE + rnd.randrange(0, TILE_SIZE) - cam_x
            by = tr * TILE_SIZE + rnd.randrange(0, TILE_SIZE) - cam_y
            if not render_util.screen_visible(bx - size, by - size, size * 2, size * 2):
                continue
            screen.blit(spr, (bx - size // 2, by - size // 2))

    # 2. Contact shadow where open ground meets a wall.
    ao_n, ao_s = _m4_ground_ao("n"), _m4_ground_ao("s")
    ao_w, ao_e = _m4_ground_ao("w"), _m4_ground_ao("e")
    depth = _GROUND_AO_DEPTH
    for row in range(y0, y1):
        map_row = g[row]
        for col in range(x0, x1):
            if map_row[col] not in _GROUND_OPEN:
                continue
            x = col * TILE_SIZE - cam_x
            y = row * TILE_SIZE - cam_y
            if row == 0 or g[row - 1][col] in _GROUND_SOLID:
                screen.blit(ao_n, (x, y))
            if row == mh - 1 or g[row + 1][col] in _GROUND_SOLID:
                screen.blit(ao_s, (x, y + TILE_SIZE - depth))
            if col == 0 or map_row[col - 1] in _GROUND_SOLID:
                screen.blit(ao_w, (x, y))
            if col == mw - 1 or map_row[col + 1] in _GROUND_SOLID:
                screen.blit(ao_e, (x + TILE_SIZE - depth, y))

    # 3. Sparse scuffs and aggregate chips - seeded per 2x2 tile slot.
    for crow in range(y0 // 2, y1 // 2 + 1):
        for ccol in range(x0 // 2, x1 // 2 + 1):
            rnd = random.Random(ccol * 40503 + crow * 12289)
            tc = ccol * 2 + rnd.randrange(0, 2)
            tr = crow * 2 + rnd.randrange(0, 2)
            if not (0 <= tr < mh and 0 <= tc < mw) or g[tr][tc] not in _GROUND_OPEN:
                continue
            r = rnd.random()
            if r > 0.20:
                continue
            x = tc * TILE_SIZE + rnd.randrange(6, TILE_SIZE - 6) - cam_x
            y = tr * TILE_SIZE + rnd.randrange(6, TILE_SIZE - 6) - cam_y
            if not render_util.screen_visible(x - 40, y - 40, 80, 80):
                continue
            if r < 0.12:
                ink = (26, 26, 28)
                pygame.draw.line(screen, ink, (x - 14, y),
                                 (x + 14, y + rnd.randint(-4, 4)), 1)
                if rnd.random() < 0.5:
                    pygame.draw.line(screen, ink, (x - 5, y + 3),
                                     (x + 9, y + 5), 1)
            else:
                for _ in range(rnd.randint(3, 4)):
                    cx = x + rnd.randint(-12, 12)
                    cy = y + rnd.randint(-9, 9)
                    cink = (30, 30, 32) if rnd.random() < 0.35 else (70, 72, 76)
                    pygame.draw.rect(screen, cink, (cx, cy, 2, 1))


# Practical fixtures. Street lamps are cold sodium (the m4street grade is
# blue-cyan); the station reads phosphor-green. Keys are prefixed st_/sn_ so
# the light cache stays per-map.
_M4_STREET_LAMPS = (
    (6, 19, 150, (198, 214, 244)),
    (11, 19, 150, (198, 214, 244)),
    (17, 19, 150, (198, 214, 244)),
    (22, 19, 150, (198, 214, 244)),
    (27, 19, 150, (198, 214, 244)),
    (30, 18, 130, (198, 214, 244)),
    (31, 19, 120, (222, 228, 248)),   # station approach (cold)
    (33, 19, 170, (255, 196, 130)),   # station door mouth (warm invite)
)
_M4_STATION_LAMPS = (
    (8, 15, 130, (200, 236, 210)),    # entry hall
    (12, 4, 150, (196, 255, 214)),    # transmitter hall (phosphor)
    (20, 7, 150, (196, 255, 214)),    # over the TX rack
    (19, 13, 130, (206, 234, 214)),   # east studio
)


def _push_m4_lights(cam_x, cam_y, t):
    lb = lighting.buffer()
    cast = _m4_solid_world
    cam = (cam_x, cam_y)
    station = _m4_is_station(_m4_maps.MISSION4_MAP)
    table = _M4_STATION_LAMPS if station else _M4_STREET_LAMPS
    prefix = "sn" if station else "st"
    render_util.push_lamps(
        lb,
        ((tx * TILE_SIZE + TILE_SIZE // 2, ty * TILE_SIZE + TILE_SIZE // 2,
          r, col, "%s_%d_%d" % (prefix, tx, ty))
         for tx, ty, r, col in table),
        cam_x, cam_y, t, cast,
        key_fn=lambda wx, wy: ("lamp", int(wx // TILE_SIZE), int(wy // TILE_SIZE)))
    if station:
        # Motivated glow on the objective fixtures.
        for (fx, fy), col, radius in (
                (TRANSMITTER_TILE, (170, 255, 200), 150),
                (JAMMER_TILE, (180, 220, 255), 120)):
            sx = fx * TILE_SIZE + TILE_SIZE // 2 - cam_x
            sy = fy * TILE_SIZE + TILE_SIZE // 2 - cam_y
            if render_util.screen_visible(sx, sy, 1, 1):
                lb.light(sx, sy, radius, col, 0.34, caster=cast, cam=cam,
                         key=("obj", fx, fy))


def _m4_draw_rain():
    """Shared sprite rain over the curfew street only (station interior dry)."""
    if _m4_is_station(_m4_maps.MISSION4_MAP):
        return
    drops = getattr(STATE, "rain_drops", None)
    if drops:
        _config.draw_rain(screen, drops)


def _draw_m4_pickup(surface, pu, cam_x, cam_y):
    """Pickup art: the shared bandage icon for heals, a drawn magazine for
    ammo (no ammo PNG exists in the pack - procedural covers the gap)."""
    x = int(pu[0] - cam_x)
    y = int(pu[1] - cam_y)
    if not (-40 < x < WIDTH + 40 and -40 < y < HEIGHT + 40):
        return
    kind = pu[2] if len(pu) > 2 else "bandage"
    render_util.soft_shadow(surface, (x - 10, y + 4, 20, 8), alpha=60)
    if kind == "bandage":
        spr = artpack.icon("bandage")
        if spr is not None:
            w, h = spr.get_size()
            surface.blit(spr, (x - w // 2, y - h // 2))
            return
        # Fallback: a pale cross patch on the ground.
        pygame.draw.rect(surface, (222, 226, 224), (x - 9, y - 7, 18, 14),
                         border_radius=3)
        pygame.draw.rect(surface, (200, 70, 70), (x - 2, y - 6, 4, 12))
        pygame.draw.rect(surface, (200, 70, 70), (x - 6, y - 2, 12, 4))
        return
    # K-9 / pistol magazine: a slim metallic stick mag with round bullet tips.
    body = pygame.Rect(x - 6, y - 12, 12, 24)
    pygame.draw.rect(surface, (34, 40, 42), body, border_radius=2)
    pygame.draw.rect(surface, (96, 120, 116), body, 1, border_radius=2)
    for ri in range(4):
        pygame.draw.circle(surface, (210, 178, 70), (x, body.y + 4 + ri * 5), 2)
    pygame.draw.rect(surface, (70, 84, 82), (body.x, body.bottom - 3, body.w, 4),
                     border_radius=1)


def _m4_wrap(text, font, max_w):
    """Greedy word wrap to pixel width (hud.draw_objective_panel idiom)."""
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        test = w if not cur else cur + " " + w
        if font.size(test)[0] <= max_w:
            cur = test
        elif cur:
            lines.append(cur)
            cur = w
        else:
            trimmed = w
            while trimmed and font.size(trimmed + "\u2026")[0] > max_w:
                trimmed = trimmed[:-1]
            lines.append(trimmed + "\u2026")
            cur = ""
    if cur:
        lines.append(cur)
    return lines


# --------------------------------------------------------------------
# Mission 4 NPC appearance, v7.
#
# v6's pure top-down blobs never read as people. v7 uses the house style
# for top-down humanoids -- the Volkov / M2 squadmate structure
# (m3._draw_volkov_in_game, mission2._draw_actor): foot shadow, boot +
# trouser legs, outlined trapezoid coat, thick-line arms with skin hands,
# layered head above the torso, rim-light halo. The body stays screen-
# upright like Volkov's; only the prop rig rotates with facing, exactly
# like his gun rig. Changed-up per character:
#   VASILE: steel-blue coat, red trim stripe + rim halo, field cap w/
#           band, cold grey eyes, wooden-stock rifle rig.
#   MARU:   (legacy look; v9 draws Maru + Vasile with cutscenes.figure_kit,
#           see _M4_KIT_CAST below - black hoodie, backpack straps, no glasses.)
# --------------------------------------------------------------------

_M4_NPC_ROLE = {
    "VASILE": "KRAP FIELD COMMANDER",
    "MARU": "MAG LIAISON / FORMER IPA ARCHIVIST",
}

_M4_NPC_POSE = (84, 84)          # pose surface (rig swings 360 degrees)
_M4_NPC_ANCHOR = (42, 48)        # body-centre origin inside that surface

_M4_NPC_LOOK = {
    "VASILE": {
        "build": 1.15, "headgear": "cap", "rifle": True, "satchel": False,
        "palette": {
            "coat": (44, 56, 74), "coat_dark": (30, 39, 52),
            "coat_hi": (62, 76, 96), "trim": (146, 52, 44),
            "seam": (146, 52, 44), "head": (36, 46, 60),
            "skin": (186, 152, 124), "barrel": (74, 76, 82),
            "stock": (92, 66, 44), "metal": (150, 145, 132),
        },
    },
    "MARU": {
        "build": 0.88, "headgear": "bandana", "rifle": False, "satchel": True,
        "palette": {
            "coat": (58, 84, 62), "coat_dark": (40, 60, 44),
            "coat_hi": (78, 106, 82), "trim": (214, 226, 190),
            "seam": (120, 150, 120), "head": (96, 132, 96),
            "skin": (156, 122, 96), "paper": (172, 158, 122),
            "paper_line": (112, 98, 72), "bag": (70, 54, 40),
            "bag_dark": (46, 36, 28), "strap": (58, 46, 36),
            "glass": (205, 214, 208),
        },
    },
}


def _m4_dim(col, k):
    return (int(col[0] * k), int(col[1] * k), int(col[2] * k))


def _m4_draw_npc(s, x, y, a, look):
    """Upright 3/4-view figure in the Volkov / M2 squadmate structure.

    (x, y) is the body centre on ``s``; ``a`` rotates ONLY the prop rig
    (Volkov's gun-rig idiom) while the body stays screen-upright.
    """
    x = int(x)
    y = int(y)
    pal = look["palette"]
    dx, dy = math.cos(a), math.sin(a)
    px, py = -dy, dx
    ax, ay = x, y - 7                    # chest rig anchor (Volkov idiom)

    def R(f, r):
        return (int(round(ax + dx * f + px * r)),
                int(round(ay + dy * f + py * r)))

    # 1 -- foot shadow + rim-light halo in the character's own trim hue ----
    shad = pygame.Surface((36, 14), pygame.SRCALPHA)
    render_util.soft_shadow(shad, shad.get_rect(), 70)
    s.blit(shad, (x - 18, y + 12))
    pygame.draw.polygon(s, _m4_dim(pal["trim"], 0.25),
                        [(x - 16, y - 16), (x + 16, y - 16),
                         (x + 14, y + 12), (x - 14, y + 12)])

    # 2 -- legs: boot ellipses + trouser rects (M2 upright) ------------------
    pygame.draw.ellipse(s, (10, 10, 12), (x - 13, y + 17, 12, 7))
    pygame.draw.ellipse(s, (10, 10, 12), (x + 1, y + 17, 12, 7))
    pygame.draw.rect(s, pal["coat_dark"], (x - 10, y + 3, 8, 15), border_radius=2)
    pygame.draw.rect(s, pal["coat_dark"], (x + 2, y + 3, 8, 15), border_radius=2)

    # 3 -- trapezoid coat + outline + centre opening + identity bits ---------
    torso = [(x - 13, y - 14), (x + 13, y - 14),
             (x + 11, y + 10), (x - 11, y + 10)]
    pygame.draw.polygon(s, pal["coat"], torso)
    pygame.draw.polygon(s, pal["coat_dark"], torso, 2)
    pygame.draw.line(s, pal["seam"], (x, y - 14), (x, y + 8), 2)
    if look["rifle"]:
        pygame.draw.rect(s, pal["trim"], (x - 11, y - 12, 22, 4), border_radius=2)
        pygame.draw.circle(s, pal["coat_hi"], (x + 9, y + 3), 3)
    if look["satchel"]:
        pygame.draw.line(s, pal["strap"], (x - 10, y - 12), (x + 12, y + 4), 2)
        pygame.draw.rect(s, pal["bag"], (x + 10, y + 2, 9, 11), border_radius=2)
        pygame.draw.line(s, pal["bag_dark"], (x + 11, y + 5), (x + 18, y + 5), 1)

    # 4 -- arms + prop rig (the only part that rotates with facing) ----------
    sh_l, sh_r = R(-1, 9), R(-1, -9)
    if look["rifle"]:
        hand_l, hand_r = R(13, 4), R(17, -4)
        pygame.draw.line(s, pal["coat"], sh_l, hand_l, 5)
        pygame.draw.line(s, pal["coat"], sh_r, hand_r, 5)
        pygame.draw.circle(s, pal["skin"], hand_l, 3)
        pygame.draw.circle(s, pal["skin"], hand_r, 3)
        start, end = R(9, 0), R(31, 0)
        pygame.draw.line(s, (8, 9, 10), start, end, 6)
        pygame.draw.line(s, pal["barrel"], start, end, 4)
        pygame.draw.line(s, pal["metal"], R(9, -1.8), R(31, -1.8), 1)
        pygame.draw.line(s, (18, 20, 20), end, R(37, 0), 3)
        pygame.draw.circle(s, (5, 5, 6), R(38, 0), 2)
        pygame.draw.line(s, (16, 18, 18), R(13, 0), R(12, 8), 4)   # stick mag
        pygame.draw.line(s, pal["stock"], R(9, 1), R(1, 2), 4)     # wood stock
    elif look.get("pistol"):
        hand_l, hand_r = R(14, 3), R(16, -3)
        pygame.draw.line(s, pal["coat"], sh_l, hand_l, 5)
        pygame.draw.line(s, pal["coat"], sh_r, hand_r, 5)
        pygame.draw.circle(s, pal["skin"], hand_l, 3)
        pygame.draw.circle(s, pal["skin"], hand_r, 3)
        start, end = R(14, 0), R(26, 0)
        pygame.draw.line(s, (8, 9, 10), start, end, 5)
        pygame.draw.line(s, pal.get("metal", (150, 145, 132)), start, end, 3)
        pygame.draw.line(s, pal.get("barrel", (74, 76, 82)), R(16, 1), R(15, 6), 3)
    else:
        hand_l, hand_r = R(12, 5), R(12, -5)
        pygame.draw.line(s, pal["coat"], sh_l, hand_l, 5)
        pygame.draw.line(s, pal["coat"], sh_r, hand_r, 5)
        pygame.draw.polygon(s, pal["paper"],
                            [R(9.5, 4), R(14.5, 4), R(14.5, -4), R(9.5, -4)])
        pygame.draw.line(s, pal["paper_line"], R(12, -3), R(12, 3), 1)
        pygame.draw.circle(s, pal["skin"], hand_l, 3)
        pygame.draw.circle(s, pal["skin"], hand_r, 3)

    # 5 -- head: halo, skull, headgear, eyes -----------------------------------
    hy = y - 24
    pygame.draw.circle(s, _m4_dim(pal["trim"], 0.4), (x, hy), 12)
    pygame.draw.circle(s, pal["skin"], (x, hy), 10)
    if look["headgear"] == "cap":
        pygame.draw.arc(s, pal["coat_dark"], (x - 10, hy - 10, 20, 20),
                        0, math.pi, 6)
        pygame.draw.line(s, pal["trim"], (x - 8, hy - 1), (x + 8, hy - 1), 2)
        for ex in (-3, 3):
            pygame.draw.circle(s, (26, 30, 36), (x + ex, hy + 2), 2)
            pygame.draw.circle(s, (140, 160, 170), (x + ex, hy + 2), 1)
    else:
        pygame.draw.arc(s, pal["head"], (x - 10, hy - 10, 20, 20),
                        0, math.pi, 6)
        pygame.draw.circle(s, pal["head"], (x - 9, hy - 5), 2)
        pygame.draw.line(s, pal["head"], (x - 9, hy - 5), (x - 13, hy - 1), 2)
        pygame.draw.line(s, pal["coat_dark"], (x - 9, hy - 5), (x - 12, hy - 9), 2)
        pygame.draw.line(s, pal["glass"], (x - 1, hy + 1), (x + 1, hy + 1), 1)
        for ex in (-4, 4):
            pygame.draw.circle(s, pal["glass"], (x + ex, hy + 2), 3)
            pygame.draw.circle(s, (24, 20, 18), (x + ex, hy + 2), 1)


def _m4_humanoid(s, cx, cy, a, uniform=None, skin=None, rifle=False,
                 wear="cap", accent=(220, 220, 220), look=None):
    """Compat wrapper for old call sites."""
    if look is None:
        look = {"build": 1.0, "headgear": "cap" if wear == "cap" else "bandana",
                "rifle": rifle, "satchel": False,
                "palette": {"coat": uniform or (62, 74, 88),
                            "coat_dark": (40, 48, 58),
                            "coat_hi": (78, 90, 104), "trim": accent,
                            "seam": accent,
                            "head": (uniform or (62, 74, 88)),
                            "skin": skin or (182, 150, 122),
                            "barrel": (74, 76, 82), "stock": (92, 66, 44),
                            "metal": (150, 145, 132),
                            "paper": (172, 158, 122),
                            "paper_line": (112, 98, 72),
                            "bag": (70, 54, 40), "bag_dark": (46, 36, 28),
                            "strap": (58, 46, 36), "glass": (205, 214, 208)}}
    _m4_draw_npc(s, cx, cy, a, look)


# v9: the named liaison NPCs use the cutscene cast kit (figure_kit) so the
# station matches the cutscenes and the 3D rig. Drawn 3x and smooth-scaled
# down once into the pose cache; only the weapon rig rotates with facing.
_M4_KIT_CAST = {"MARU": "maru", "VASILE": "vasile"}
_M4_KIT_SS = 3
_M4_KIT_SCALE = 0.232            # ~58 px tall at 1x (foot y+22 -> crown y-36)


# Weapon silhouettes in gun-local units (1x px): x along the barrel (0 = rear
# grip), y down the gun (magazine side). Drawn 3x with the body, then scaled.
_M4_GUNS = {
    "rifle": {
        "len": 30, "hands": ((0.0, 1.5), (12.5, 0.6)),
        "parts": [
            ("stock", [(-8, -1.0), (-2, -1.6), (-2, 1.4), (-4, 1.6), (-8, 3.0)]),
            ("dark", [(-2, -2.0), (10, -2.0), (10, 1.2), (-2, 1.6)]),
            ("dark", [(0.2, 1.2), (2.2, 1.2), (1.6, 4.6), (-0.4, 4.4)]),          # pistol grip
            ("mag", [(4.2, 1.0), (7.4, 1.0), (8.6, 4.6), (7.6, 7.6), (5.0, 7.0), (5.6, 4.0)]),
            ("stock", [(10, -1.6), (17, -1.2), (17, 1.0), (10, 1.2)]),           # handguard
            ("metal", [(17, -0.8), (28, -0.6), (28, 0.4), (17, 0.6)]),          # barrel
            ("metal", [(10, -2.6), (17, -2.4), (17, -1.6), (10, -2.0)]),        # gas tube
            ("dark", [(25.6, -2.4), (26.6, -2.4), (26.6, -0.6), (25.6, -0.6)]),  # front sight
            ("dark", [(28, -1.0), (30, -1.0), (30, 0.8), (28, 0.8)]),           # muzzle
        ],
        "shine": [((-1, -1.4), (9.5, -1.4)), ((17.5, -0.5), (27.5, -0.4))],
    },
    "pistol": {
        "len": 10, "hands": ((0.6, 1.2), (1.8, 1.8)),
        "parts": [
            ("dark", [(-0.6, 0.6), (2.2, 0.6), (1.4, 5.0), (-1.4, 4.6)]),        # grip
            ("metal", [(-1.2, -1.6), (9.6, -1.6), (9.6, 0.8), (-1.2, 0.8)]),     # slide
            ("dark", [(2.4, 0.8), (4.6, 0.8), (4.0, 2.2), (2.4, 2.2)]),          # trigger guard
        ],
        "shine": [((-0.6, -1.2), (9.0, -1.2))],
    },
}


def _dark_rgb(c, k):
    return (int(c[0] * k), int(c[1] * k), int(c[2] * k))


def _m4_draw_npc_kit(s, x, y, a, who, weapon, pal):
    from cutscenes.figure_kit import SPECS, draw_character
    ss = _M4_KIT_SS
    dx, dy = math.cos(a), math.sin(a)
    right = dx >= 0
    foot = y + 22
    big = pygame.Surface((s.get_width() * ss, s.get_height() * ss), pygame.SRCALPHA)
    gun = _M4_GUNS.get(weapon)
    if gun is None:
        draw_character(big, who, x * ss, foot * ss, _M4_KIT_SCALE * ss, right,
                       prop="folder" if weapon == "folder" else None)
        s.blit(pygame.transform.smoothscale(big, s.get_size()), (0, 0))
        return
    # 3/4 view: vertical aim is foreshortened (screen y squashed, gun shorter)
    ang = math.atan2(dy * 0.55, dx)
    shrink = 0.62 + 0.38 * abs(dx)
    ux, uy = math.cos(ang) * shrink, math.sin(ang) * shrink
    nx, ny = -math.sin(ang), math.cos(ang)
    if not right:                      # keep the magazine hanging down
        nx, ny = -nx, -ny
    behind = dy < -0.35                # aiming up-screen: gun goes behind the body
    # butt at the gun-side shoulder so nothing crosses the chest; aiming
    # up-screen it is carried at the shoulder edge, behind the body
    side = (9.0 if weapon == "rifle" else 7.0) * (0.55 + 0.45 * abs(dx)) + (3.0 if behind else 0.0)
    grip = (x + (side if right else -side) + ux * 4, y - 13 + uy * 3)

    def G(px_, py_):
        return ((grip[0] + ux * px_ + nx * py_) * ss, (grip[1] + uy * px_ + ny * py_) * ss)

    cols = {"stock": pal.get("stock", (92, 66, 44)), "dark": (22, 23, 25),
            "metal": pal.get("barrel", (74, 76, 82)), "mag": (34, 34, 36)}
    if weapon == "pistol":
        cols["metal"] = (58, 60, 64)

    def draw_gun():
        for kind, pts in gun["parts"]:
            poly = [G(*p_) for p_ in pts]
            pygame.draw.polygon(big, cols[kind], poly)
            pygame.draw.polygon(big, (8, 8, 9), poly, max(1, ss // 2))
        for p0, p1 in gun["shine"]:
            pygame.draw.line(big, pal.get("metal", (150, 145, 132)), G(*p0), G(*p1), max(1, ss // 2))

    # Custom armed pose: body without its default arms, then two arms that
    # actually hold the gun (far arm -> front hand under the gun, near arm ->
    # grip hand over it), so there are exactly two hands.
    spec = SPECS[who]
    k = _M4_KIT_SCALE * ss * spec["height"] / 296.0
    f = 1 if right else -1
    bulk = spec["bulk"]
    sh_y = foot * ss + (-258 + 51) * k
    near_sh = (x * ss + f * 36 * bulk * k, sh_y)      # shoulder on the facing side
    far_sh = (x * ss - f * 30 * bulk * k, sh_y)
    grip_h, front_h = G(*gun["hands"][0]), G(*gun["hands"][1])
    sleeve = spec["coat"] if spec.get("sleeves") != "short" else spec["skin"]
    hand_col = spec.get("glove") or spec["skin"]
    w_arm = max(2, round(15 * bulk * k))

    def hand_dot(hand):
        r = max(2, round(6.5 * k))
        pygame.draw.circle(big, (10, 10, 12), (round(hand[0]), round(hand[1])), r + 1)
        pygame.draw.circle(big, hand_col, (round(hand[0]), round(hand[1])), r)

    def arm(sh, hand, col):
        mx, my = (sh[0] + hand[0]) / 2, (sh[1] + hand[1]) / 2
        el = (mx - f * 3 * k * 4, my + 9 * k * 2.2)   # elbow drops down/back
        pygame.draw.line(big, (10, 10, 12), sh, el, w_arm + 2)
        pygame.draw.line(big, (10, 10, 12), el, hand, w_arm + 2)
        pygame.draw.line(big, col, sh, el, w_arm)
        pygame.draw.line(big, col, el, hand, w_arm)
        pygame.draw.circle(big, col, (round(el[0]), round(el[1])), w_arm // 2)
        r = max(2, round(6.5 * k))
        pygame.draw.circle(big, (10, 10, 12), (round(hand[0]), round(hand[1])), r + 1)
        pygame.draw.circle(big, hand_col, (round(hand[0]), round(hand[1])), r)

    behind = dy < -0.35
    far = _dark_rgb(sleeve, 0.78)
    if behind:                         # aiming up-screen: gun + both hands behind the body
        draw_gun()
        arm(far_sh, front_h, far)
        arm(near_sh, grip_h, far)
        draw_character(big, who, x * ss, foot * ss, _M4_KIT_SCALE * ss, right, arms=False)
    else:
        arm(far_sh, front_h, far)      # back arm stays behind the body...
        draw_character(big, who, x * ss, foot * ss, _M4_KIT_SCALE * ss, right, arms=False)
        draw_gun()
        hand_dot(front_h)              # fingers over the handguard
        arm(near_sh, grip_h, tuple(min(255, int(c * 1.25 + 8)) for c in sleeve))
    s.blit(pygame.transform.smoothscale(big, s.get_size()), (0, 0))


def _m4_figure_pose(name, color, facing, weapon="rifle"):
    who = _M4_KIT_CAST.get(name)
    if who:
        pal = (_M4_NPC_LOOK.get(name) or {}).get("palette", {})
        key = ("m4npc_kit_v14", name, weapon, int(round(math.degrees(facing))))
        return artpack.pose(key, _M4_NPC_POSE,
                            lambda s: _m4_draw_npc_kit(s, _M4_NPC_ANCHOR[0], _M4_NPC_ANCHOR[1],
                                                       facing, who, weapon, pal))
    look = dict(_M4_NPC_LOOK.get(name) or {})
    if not look:
        look = {"build": 1.0, "headgear": "cap", "rifle": True,
                "satchel": False,
                "palette": {"coat": (62, 74, 88), "coat_dark": (40, 48, 58),
                            "coat_hi": (78, 90, 104), "trim": color,
                            "seam": color, "head": (62, 74, 88),
                            "skin": (182, 150, 122), "barrel": (74, 76, 82),
                            "stock": (92, 66, 44), "metal": (150, 145, 132),
                            "paper": (172, 158, 122), "paper_line": (112, 98, 72),
                            "bag": (70, 54, 40), "bag_dark": (46, 36, 28),
                            "strap": (58, 46, 36), "glass": (205, 214, 208)}}
    else:
        look = dict(look)
        look["palette"] = dict(look.get("palette") or {})
    look["rifle"] = weapon == "rifle"
    look["pistol"] = weapon == "pistol"
    key = ("m4npc_v8", name, weapon, int(round(math.degrees(facing))))
    return artpack.pose(key, _M4_NPC_POSE,
                        lambda s: _m4_draw_npc(s, _M4_NPC_ANCHOR[0],
                                               _M4_NPC_ANCHOR[1], facing, look))


def _draw_m4_npcs(surface, cam_x, cam_y):
    """Friendly liaison-meet NPCs (Maru + Vasile) in the Volkov/M2 upright
    humanoid structure, plus name tag + role line. The foot shadow is baked
    into the pose. No-op on the street (friendly_npcs() is empty)."""
    live = {a["name"]: a for a in getattr(STATE, "m4_allies", []) or []}
    hold = getattr(STATE, "mission4_stage", None) == STAGE_COMMIT
    for row in friendly_npcs():
        name, (wx, wy), color, facing = row[0], row[1], row[2], row[3]
        weapon = row[4] if len(row) > 4 else "rifle"
        x = int(wx - cam_x)
        y = int(wy - cam_y)
        if not (-60 < x < WIDTH + 60 and -60 < y < HEIGHT + 60):
            continue
        rec = live.get(name)
        if rec and rec.get("downed", 0) > 0:
            facing = math.pi / 2
        surface.blit(_m4_figure_pose(name, color, facing, weapon),
                     (x - _M4_NPC_ANCHOR[0], y - _M4_NPC_ANCHOR[1]))
        tag = font_terminal_small.render(name, True, color)
        tag_y = y - 38 - tag.get_height()
        role = _M4_NPC_ROLE.get(name, "")
        if role and not hold:
            ry = tag_y - 3
            for ln in reversed(_m4_wrap(role, font_terminal_small, 118)):
                ls = font_terminal_small.render(ln, True, (150, 150, 145))
                ry -= ls.get_height() + 1
                surface.blit(ls, (x - ls.get_width() // 2, ry))
        surface.blit(tag, (x - tag.get_width() // 2, tag_y))
        if hold and rec:
            bar_w = 28
            frac = 0.0 if rec["max_hp"] <= 0 else max(
                0.0, min(1.0, rec["hp"] / rec["max_hp"]))
            bx, by = x - bar_w // 2, tag_y + tag.get_height() + 2
            pygame.draw.rect(surface, (28, 28, 28), (bx, by, bar_w, 3))
            fill = (220, 80, 70) if rec.get("downed", 0) > 0 else (120, 220, 150)
            pygame.draw.rect(surface, fill, (bx, by, int(bar_w * frac), 3))


def _draw_m4_lasers(surface, cam_x, cam_y):
    """Marksman telegraph beams (m2._draw_sniper_lasers_world idiom, ported).
    World-space red pin lines that fade with life; purely visual threat read."""
    for laser in getattr(STATE, "m4_lasers", []):
        fx, fy = laser["from"]
        tx, ty = laser["to"]
        sx1, sy1 = fx - cam_x, fy - cam_y
        sx2, sy2 = tx - cam_x, ty - cam_y
        alpha = max(0, min(190, int(laser.get("life", 0) * 4)))
        beam = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.line(beam, (255, 35, 22, alpha), (sx1, sy1), (sx2, sy2), 3)
        pygame.draw.line(beam, (255, 175, 110, alpha // 2), (sx1, sy1), (sx2, sy2), 1)
        pygame.draw.circle(beam, (255, 45, 30, alpha), (int(sx2), int(sy2)), 8, 1)
        surface.blit(beam, (0, 0))


def _draw_m4_dialogue(surface):
    """Typewriter dialogue panel for the station liaison meet (W3). Reads the
    single-owner flow._m4_dlg live; only draws while a beat is active."""
    dlg = _m4_flow._m4_dlg
    if not dlg["active"]:
        return
    beat = _m4_flow._current_beat()
    if beat is None:
        return

    panel_w = min(WIDTH - 120, 760)
    pad = 22
    max_text_w = panel_w - pad * 2
    body = font_dialogue
    line_h = body.get_height()

    full = _m4_flow._beat_text(beat)
    shown = full[:dlg["char_idx"]]
    lines = _m4_wrap(shown, body, max_text_w) if shown else [""]

    is_choice = beat.get("type") == "choice"
    typed = _m4_flow._line_fully_typed()
    options = beat.get("options", []) if is_choice else []
    opt_line_h = font_terminal_small.get_height() + 6
    opt_h = (len(options) * opt_line_h + 12) if (is_choice and typed) else 0

    head_h = font_speaker.get_height() + 8
    panel_h = head_h + max(1, len(lines)) * (line_h + 2) + opt_h + pad + 12
    px = (WIDTH - panel_w) // 2
    py = HEIGHT - panel_h - 40

    bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    pygame.draw.rect(bg, (8, 10, 14, 234), bg.get_rect(), border_radius=6)
    color = beat.get("color", C_WHITE)
    pygame.draw.rect(bg, (*color, 210), bg.get_rect(), 1, border_radius=6)
    surface.blit(bg, (px, py))

    surface.blit(font_speaker.render(beat.get("speaker", ""), True, color),
                 (px + pad, py + 8))

    y = py + head_h
    for ln in lines:
        surface.blit(body.render(ln, True, (226, 230, 236)), (px + pad, y))
        y += line_h + 2

    if is_choice and typed:
        y += 6
        sel = dlg["choice"]
        for i, (label, _follow) in enumerate(options):
            mark = "> " if i == sel else "  "
            col = (240, 214, 120) if i == sel else (150, 165, 180)
            surface.blit(font_terminal_small.render(mark + label, True, col),
                         (px + pad, y))
            y += opt_line_h

    hint = ("\u2190\u2192 pick    ENTER confirm" if (is_choice and typed)
            else "ENTER / E  continue")
    hint_surf = font_terminal_small.render(hint, True, (110, 120, 135))
    surface.blit(hint_surf,
                 (px + panel_w - hint_surf.get_width() - pad,
                  py + panel_h - hint_surf.get_height() - 6))


def _m4_objective_world_pos():
    """World centre of the current objective marker, for the minimap pin.
    Street: regroup on Vasile's cache, then the station door. Station:
    the transmitter rack."""
    stage = getattr(STATE, "mission4_stage", None)
    if (_m4_is_station(_m4_maps.MISSION4_MAP)
            or stage in (STAGE_MARU, STAGE_COMMIT, STAGE_DONE)):
        tx, ty = TRANSMITTER_TILE
    elif stage == STAGE_KRAP_STATUS:
        tx, ty = STATION_DOOR_TILE
    else:
        tx, ty = VASILE_CACHE_TILE
    return (tx * TILE + TILE // 2, ty * TILE + TILE // 2)


def _m4_mag_icon_variant(kind, rounds, cap, is_active):
    """Sprite variant of a magazine icon: kind (stick / box) x active x state, where state 0 is
    the empty magazine and 1..13 the non-empty fill levels 0..12 (round(rounds / cap * 12))."""
    rounds = max(0, int(rounds))
    cap = max(1, int(cap))
    state = 0 if rounds <= 0 else 1 + min(12, int(round(rounds / cap * 12)))
    return ((0 if kind == "stick" else 1) * 2 + (1 if is_active else 0)) * 14 + state


def _draw_m4_mag_icon(surface, mx, my, kind, rounds, cap, is_active):
    """One magazine icon (baked sprite game.art.m4.mag_icon; _paint_m4_mag_icon is the fallback /
    bake source)."""
    spr = _m4art.get("mag_icon", _m4_mag_icon_variant(kind, rounds, cap, is_active))
    if spr is not None:
        surface.blit(spr, (mx, my - 3))
        return
    _paint_m4_mag_icon(surface, mx, my, kind, rounds, cap, is_active)


def _paint_m4_mag_icon(surface, mx, my, kind, rounds, cap, is_active):
    """One magazine icon - a K-9/OS-12 stick mag (tall, ribbed witness holes)
    or a sidearm box mag (tapered). Draw language ported from the M3 HUD.
    Opaque primitives inside (mx, my - 3) .. (mx + 24, my + 53)."""
    rounds = max(0, int(rounds))
    cap = max(1, int(cap))
    if kind == "stick":
        mag_w, mag_h = 14, 52
        body = pygame.Rect(mx + 5, my, mag_w, mag_h)
        if rounds <= 0:
            base, rim, hi = (24, 28, 28), (52, 62, 58), (36, 42, 40)
        elif is_active:
            base, rim, hi = (36, 48, 44), (120, 230, 180), (70, 92, 84)
        else:
            base, rim, hi = (32, 38, 36), (86, 112, 102), (54, 66, 62)
        poly = [(body.x + 1, body.y), (body.right - 1, body.y + 1),
                (body.right - 3, body.bottom), (body.x + 3, body.bottom)]
        pygame.draw.polygon(surface, base, poly)
        pygame.draw.polygon(surface, rim if is_active else (64, 70, 66), poly, 1)
        pygame.draw.line(surface, hi, (body.x + 4, body.y + 4),
                         (body.x + 5, body.bottom - 5), 1)
        pygame.draw.rect(surface, (80, 86, 78),
                         (body.x + 2, body.y - 3, mag_w - 2, 4), border_radius=1)
        pygame.draw.rect(surface, (18, 20, 20),
                         (body.x + 1, body.bottom - 4, mag_w - 1, 5), border_radius=1)
        filled = int(round(rounds / cap * 12))
        for row_i in range(12):
            wy = body.bottom - 8 - row_i * 3
            on = row_i < filled
            for wx_off in (5, 9):
                col = ((220, 190, 70) if is_active else (150, 128, 58)) if on else (18, 20, 20)
                pygame.draw.circle(surface, col, (body.x + wx_off, wy), 1)
        if is_active:
            pygame.draw.line(surface, (120, 230, 180), (body.right + 3, body.y + 4),
                             (body.right + 3, body.bottom - 4), 2)
    else:
        top_w, bot_w, h = 24, 20, 46
        taper = (top_w - bot_w) // 2
        pts = [(mx, my), (mx + top_w, my),
               (mx + taper + bot_w, my + h), (mx + taper, my + h)]
        empty = rounds <= 0
        if empty:
            base, hl, rim = (45, 42, 38), (55, 52, 48), (55, 50, 45)
        elif is_active:
            base, hl, rim = (90, 86, 78), (115, 110, 100), (70, 66, 58)
        else:
            base, hl, rim = (72, 68, 62), (92, 88, 80), (60, 56, 50)
        pygame.draw.polygon(surface, base, pts)
        pygame.draw.polygon(surface, hl, [
            (mx + 1, my + 2), (mx + 5, my + 2),
            (mx + taper + 3, my + h - 3), (mx + taper + 1, my + h - 3)])
        pygame.draw.polygon(surface, C_TERMINAL if is_active else rim, pts, 1)
        gold = (220, 185, 45)
        dark = (55, 52, 48) if not empty else (40, 38, 35)
        fill = min(12, int(round(rounds / cap * 12)))
        for bi in range(12):
            pygame.draw.circle(surface, gold if bi < fill else dark,
                               (mx + top_w // 2, my + 8 + bi * 3), 2)


def _draw_m4_hold_bar(surface):
    """Hold-the-transmitter clock for STAGE_COMMIT, styled like the M3 clock
    plate (ported look, own values): a centred diegetic bar + countdown."""
    if getattr(STATE, "mission4_stage", None) != STAGE_COMMIT:
        return
    total = max(1, int(M4_HOLD_SECONDS * 60))
    t = getattr(STATE, "m4_hold_timer", 0)
    frac = max(0.0, min(1.0, t / total))
    secs_left = max(0, int(round((total - t) / 60)))
    w = 320
    x = (WIDTH - w) // 2
    y = 64
    surface.blit(get_plate_bg(w, 46), (x, y))
    surface.blit(font_terminal_small.render(_T("hud.hold_transmitter"), True,
                                            (200, 210, 224)), (x + 12, y + 6))
    bar = pygame.Rect(x + 12, y + 26, w - 70, 12)
    pygame.draw.rect(surface, (30, 30, 30), bar)
    pygame.draw.rect(surface, (120, 220, 170), (bar.x, bar.y, int(bar.w * frac), bar.h))
    pygame.draw.rect(surface, (150, 170, 190), bar, 1)
    surface.blit(font_terminal_small.render(_T("hud.hold_timer", s=secs_left), True,
                                            (220, 226, 236)), (bar.right + 8, y + 24))


def _draw_m4_hud(surface, cam_x, cam_y):
    """M4 gameplay HUD (visual-parity rework): objective panel + pinned radio,
    an HP panel, a K-9/OS-12/sidearm magazine-icon weapon panel, a hostiles
    counter, the minimap (now actually drawn) and the STAGE_COMMIT hold clock.
    The magazine-icon + clock-plate looks are ported from the M3 HUD language
    (values local; the m3 module is not imported)."""
    draw_objective_panel(surface, _m4_maps._objective)

    draw_pinned_radio(surface)

    _draw_m4_street_arrow(surface, cam_x, cam_y)

    if not STATE.player:
        return

    # Phase 4: the duplicated M4/M5 panel bodies are engine.ui.std widgets now.
    _hud_health_bar.draw(surface, THEME, STATE.player.hp, STATE.player.max_hp,
                         panel_bg=get_panel_bg)

    _hud_weapon_panel.draw(surface, THEME, _hud_weapon_panel.WeaponInfo.from_state(STATE),
                           panel_bg=get_panel_bg, mag_icon=_draw_m4_mag_icon)

    # ── Hostiles counter ──
    _hud_hostiles.draw(surface, THEME, len(STATE.enemies))

    # ── Minimap (the fix: start_m4 built STATE.minimap but it was never drawn) ──
    if STATE.show_minimap and STATE.minimap:
        STATE.minimap.draw(surface, STATE.player, STATE.enemies, cam_x, cam_y,
                           notebook_pos=_m4_objective_world_pos())

    # ── Hold-the-transmitter clock (STAGE_COMMIT only) ──
    _draw_m4_hold_bar(surface)


# ─────────────────────────────────────────────────────────────────────────
# Station interior dressing (W3 polish pass)
#
# The carved station grid used to render as bare "O"/"L" floor rects: no
# wall base, no signage, no furniture - rooms read as empty black boxes and
# the assault doors looked like holes in the wall. This pass adds, per frame
# (never baked, so it survives the street<->station swap cleanly):
#   * a skirting trim wherever floor meets wall (rooms get a visible base),
#   * engraved room plates on the wall face above each doorway,
#   * fixed furniture that also owns collision (world._build_station_world):
#     the TX rack row, the console desk, the entry bench, the studio table
#     and the utility shelves,
#   * flat decals that need no collision: cable coils, entry rug, posters,
#     the stair flight in the anteroom, the ON AIR box over the studio door.
# ─────────────────────────────────────────────────────────────────────────
_M4_ROOM_PLATES = (
    (10, 1, "TRANSMITTER HALL"),
    (9, 12, "ENTRY HALL"),
    (20, 10, "STUDIO A"),
    (15, 12, "STAIRS"),
    (10, 9, "UTILITIES"),
)
_M4_STATION_FLOOR = "OLD"


def _m4_station_grid():
    g = _m4_maps.MISSION4_MAP
    if not _m4_is_station(g):
        return None
    return g


def _draw_m4_skirting(surface, g, cam_x, cam_y):
    """3px dark base + 1px hi-light on every floor edge that meets a wall."""
    h = len(g)
    w = len(g[0])
    for row in range(h):
        for col in range(w):
            if g[row][col] not in _M4_STATION_FLOOR:
                continue
            sx = col * TILE_SIZE - cam_x
            sy = row * TILE_SIZE - cam_y
            if sx > WIDTH or sy > HEIGHT or sx + TILE_SIZE < 0 or sy + TILE_SIZE < 0:
                continue
            for dc, dr, line in (
                    (0, -1, ((sx, sy + 1), (sx + TILE_SIZE - 1, sy + 1))),
                    (0, 1, ((sx, sy + TILE_SIZE - 2), (sx + TILE_SIZE - 1, sy + TILE_SIZE - 2))),
                    (-1, 0, ((sx + 1, sy), (sx + 1, sy + TILE_SIZE - 1))),
                    (1, 0, ((sx + TILE_SIZE - 2, sy), (sx + TILE_SIZE - 2, sy + TILE_SIZE - 1)))):
                nc, nr = col + dc, row + dr
                nb = g[nr][nc] if (0 <= nc < w and 0 <= nr < h) else "C"
                if nb != "C":
                    continue
                pygame.draw.line(surface, (12, 14, 17), line[0], line[1], 3)
                pygame.draw.line(surface, (52, 60, 70), line[0], line[1], 1)


def _m4_room_plate(surface, sx, sy, text):
    f = font_terminal_small
    tw, th = f.size(text)
    pad = 6
    plate = pygame.Surface((tw + pad * 2, th + pad + 4), pygame.SRCALPHA)
    pygame.draw.rect(plate, (14, 16, 20, 225), plate.get_rect(), border_radius=3)
    pygame.draw.rect(plate, (78, 88, 100, 255), plate.get_rect(), 1, border_radius=3)
    pygame.draw.line(plate, (120, 132, 146, 255),
                     (2, 2), (plate.get_width() - 3, 2), 1)
    plate.blit(f.render(text, True, (148, 158, 170)), (pad, pad // 2 + 1))
    surface.blit(plate, (sx - plate.get_width() // 2, sy - plate.get_height() // 2))


def _draw_m4_station_props(surface, g, cam_x, cam_y):
    """Furniture + decals for the carved rooms (deterministic, no RNG)."""
    def S(col, row):
        return col * TILE_SIZE - cam_x, row * TILE_SIZE - cam_y

    def vis(sx, sy, mw=TILE_SIZE, mh=TILE_SIZE):
        return not (sx > WIDTH or sy > HEIGHT or sx + mw < 0 or sy + mh < 0)

    # TX rack row (north wall of the transmitter hall, cols 5-13 row 2).
    for c in range(5, 14):
        sx, sy = S(c, 2)
        if not vis(sx, sy):
            continue
        pygame.draw.rect(surface, (34, 38, 44), (sx + 1, sy + 1, 62, 62))
        pygame.draw.rect(surface, (20, 22, 26), (sx + 1, sy + 1, 62, 62), 1)
        pygame.draw.line(surface, (48, 52, 60), (sx + 4, sy + 4), (sx + 59, sy + 4), 1)
        if c % 3 == 0:
            pygame.draw.rect(surface, (58, 92, 78), (sx + 8, sy + 10, 30, 20))
            pygame.draw.rect(surface, (26, 34, 32), (sx + 8, sy + 10, 30, 20), 1)
            pygame.draw.line(surface, (120, 190, 150), (sx + 11, sy + 20),
                             (sx + 34, sy + 18), 1)
        else:
            for k in range(3):
                pygame.draw.line(surface, (24, 26, 32), (sx + 8, sy + 12 + k * 6),
                                 (sx + 40, sy + 12 + k * 6), 2)
            pygame.draw.rect(surface, (70, 76, 86), (sx + 44, sy + 10, 12, 16))
        for k, lc in enumerate(((110, 220, 140), (220, 180, 90), (110, 220, 140))):
            if (c + k) % 4 == 0:
                lc = (60, 66, 74)
            pygame.draw.circle(surface, lc, (sx + 12 + k * 10, sy + 52), 2)

    # Console desk + chair (transmitter hall middle).
    sx, sy = S(12, 6)
    if vis(sx, sy, 128, 64):
        pygame.draw.rect(surface, (72, 60, 46), (sx + 4, sy + 8, 120, 44),
                         border_radius=3)
        pygame.draw.rect(surface, (48, 40, 30), (sx + 4, sy + 8, 120, 44), 1,
                         border_radius=3)
        pygame.draw.line(surface, (96, 82, 62), (sx + 6, sy + 10),
                         (sx + 122, sy + 10), 1)
        pygame.draw.rect(surface, (206, 202, 188), (sx + 14, sy + 18, 26, 18))
        pygame.draw.line(surface, (120, 116, 104), (sx + 17, sy + 23),
                         (sx + 36, sy + 23), 1)
        pygame.draw.line(surface, (120, 116, 104), (sx + 17, sy + 28),
                         (sx + 33, sy + 28), 1)
        pygame.draw.rect(surface, (30, 32, 38), (sx + 52, sy + 16, 34, 22),
                         border_radius=2)
        pygame.draw.rect(surface, (70, 110, 92), (sx + 55, sy + 19, 28, 16))
        pygame.draw.line(surface, (140, 220, 170), (sx + 58, sy + 27),
                         (sx + 80, sy + 25), 1)
        pygame.draw.rect(surface, (58, 48, 38), (sx + 96, sy + 18, 18, 18))
        cx, cy = S(12, 7)
        pygame.draw.rect(surface, (44, 48, 54), (cx + 20, cy + 18, 24, 24),
                         border_radius=4)
        pygame.draw.line(surface, (66, 72, 82), (cx + 22, cy + 20),
                         (cx + 42, cy + 20), 2)

    # Entry hall: bench (west wall) + rug + torn posters (north wall).
    sx, sy = S(5, 15)
    if vis(sx, sy, 64, 128):
        pygame.draw.rect(surface, (70, 58, 44), (sx + 16, sy + 4, 32, 120),
                         border_radius=3)
        for k in range(5):
            pygame.draw.line(surface, (52, 42, 32), (sx + 18, sy + 12 + k * 24),
                             (sx + 46, sy + 12 + k * 24), 2)
        pygame.draw.rect(surface, (36, 30, 24), (sx + 18, sy + 6, 28, 8))
        pygame.draw.rect(surface, (36, 30, 24), (sx + 18, sy + 114, 28, 8))
    sx, sy = S(7, 14)
    if vis(sx, sy, 320, 192):
        pygame.draw.rect(surface, (40, 44, 52), (sx + 8, sy + 8, 304, 168), 2)
        pygame.draw.rect(surface, (34, 38, 46), (sx + 16, sy + 16, 288, 152), 1)
    for pc in (7, 9):
        sx, sy = S(pc, 12)
        if vis(sx, sy):
            pygame.draw.rect(surface, (88, 82, 70), (sx + 14, sy + 6, 36, 50))
            pygame.draw.polygon(surface, M4_TILE_BASE["C"],
                                [(sx + 14, sy + 56), (sx + 50, sy + 56),
                                 (sx + 50, sy + 44), (sx + 30, sy + 50)])
            pygame.draw.line(surface, (60, 56, 48), (sx + 18, sy + 14),
                             (sx + 46, sy + 14), 2)
            pygame.draw.line(surface, (60, 56, 48), (sx + 18, sy + 22),
                             (sx + 42, sy + 22), 2)

    # Studio A: broadcast table + mics, ON AIR box over the door.
    sx, sy = S(18, 13)
    if vis(sx, sy, 128, 64):
        pygame.draw.rect(surface, (66, 60, 52), (sx + 6, sy + 8, 116, 48),
                         border_radius=4)
        pygame.draw.rect(surface, (44, 40, 34), (sx + 6, sy + 8, 116, 48), 1,
                         border_radius=4)
        for mx in (sx + 34, sx + 84):
            pygame.draw.line(surface, (28, 28, 32), (mx, sy + 30), (mx, sy + 18), 2)
            pygame.draw.circle(surface, (50, 50, 56), (mx, sy + 16), 4)
            pygame.draw.circle(surface, (90, 90, 96), (mx - 1, sy + 15), 1)
        pygame.draw.rect(surface, (206, 202, 188), (sx + 52, sy + 34, 24, 16))
    # Utility spine: shelving bays either side of the walkable centre col.
    for sc in (10, 12):
        sx, sy = S(sc, 10)
        if not vis(sx, sy):
            continue
        pygame.draw.rect(surface, (62, 52, 40), (sx + 4, sy + 6, 56, 52))
        pygame.draw.rect(surface, (40, 34, 26), (sx + 4, sy + 6, 56, 52), 1)
        pygame.draw.line(surface, (84, 72, 54), (sx + 6, sy + 24),
                         (sx + 58, sy + 24), 2)
        pygame.draw.line(surface, (84, 72, 54), (sx + 6, sy + 42),
                         (sx + 58, sy + 42), 2)
        for bx, bw, bc in ((8, 18, (86, 74, 58)), (30, 14, (70, 78, 66)),
                           (12, 22, (92, 84, 66)), (38, 16, (78, 66, 52))):
            by = sy + 10 if bx < 28 else sy + 28
            pygame.draw.rect(surface, bc, (sx + bx, by, bw, 12))


def _draw_m4_station_dressing(surface, cam_x, cam_y):
    g = _m4_station_grid()
    if g is None:
        return

    _draw_m4_skirting(surface, g, cam_x, cam_y)
    _draw_m4_station_props(surface, g, cam_x, cam_y)


def _game_draw_inner(cam_x, cam_y):
    screen.fill(C_BG_GAME)
    if staticlayer.enabled():
        if not _m4art.blit_layer(screen, "world_static", cam_x, cam_y):
            _m4_static_layer().blit(screen, cam_x, cam_y, _bake_m4_static)
    else:
        _draw_m4_floor_and_walls(screen, cam_x, cam_y)
        _draw_m4_ground_dressing(cam_x, cam_y)
        _draw_m4_station_dressing(screen, cam_x, cam_y)   # baked into the static layer otherwise
    _draw_m4_cache_prop_world(screen, cam_x, cam_y)
    _draw_m4_objective_beacons(screen, cam_x, cam_y)

    # Blood decals (floor layer, under everything with a sprite).
    for decal in STATE.blood_decals[:]:
        surf = get_blood_decal(decal[3])
        surf.set_alpha(int(decal[2]))
        screen.blit(surf, (decal[0] - decal[3] - cam_x, decal[1] - decal[3] - cam_y))
        decal[2] -= 0.25
        if decal[2] <= 0:
            STATE.blood_decals.remove(decal)

    # Fallen bodies under the living.
    corpse.draw_corpses(screen, cam_x, cam_y)

    for pu in STATE.pickups:
        _draw_m4_pickup(screen, pu, cam_x, cam_y)

    for e in STATE.enemies:
        e.draw(screen, cam_x, cam_y)

    # Friendly liaison-meet NPCs (station stages only; empty on the street).
    _draw_m4_npcs(screen, cam_x, cam_y)

    # Player - skipped while the death animation draws the fallen body.
    if STATE.player:
        from entities import death_anim as _da
        if not _da.should_skip_player_draw():
            is_moving = bool(_m4_maps._last_keys) and (
                _m4_maps._last_keys[pygame.K_w] or _m4_maps._last_keys[pygame.K_s]
                or _m4_maps._last_keys[pygame.K_a] or _m4_maps._last_keys[pygame.K_d]
            ) and not _movement_locked()
            reload_duration = 90 if getattr(STATE, "current_weapon", "") == "os12" else (
                72 if getattr(STATE, "current_weapon", "") == "k9_smg" else 60)
            reload_progress = (
                1.0 - STATE.reload_timer / reload_duration
                if STATE.is_reloading and STATE.reload_timer > 0 else 0.0
            )
            reload_progress = max(0.0, min(1.0, reload_progress))
            STATE.player.draw(
                screen, cam_x, cam_y,
                walls=_solid_walls(),
                reload_active=STATE.is_reloading,
                reload_progress=reload_progress,
                melee_active=getattr(STATE, "melee_active", False),
                melee_progress=0.0,
                is_moving=is_moving,
            )

    # Muzzle flash (m1/m2/m3 barrel-tip idiom).
    if STATE.muzzle_flash_timer > 0 and STATE.player:
        if hasattr(STATE.player, "barrel_tip"):
            tip_x, tip_y = STATE.player.barrel_tip()
        else:
            tip_x = STATE.player.rect.centerx + math.cos(STATE.player.angle) * 39
            tip_y = STATE.player.rect.centery + math.sin(STATE.player.angle) * 39
        screen.blit(MUZZLE_FLASH, (int(tip_x - cam_x - 40), int(tip_y - cam_y - 40)))
        STATE.muzzle_flash_timer -= 1

    draw_bullets(screen, STATE.bullets, cam_x, cam_y, with_glow=True)

    # Marksman telegraph beams over the world, under the FX pass (W4 siege).
    _draw_m4_lasers(screen, cam_x, cam_y)

    for p in STATE.particles:
        p.draw(screen, cam_x, cam_y)
    for c in STATE.casings:
        c.draw(screen, cam_x, cam_y)
    for fz in getattr(STATE, "fire_zones", []):
        fz.draw(screen, cam_x, cam_y)

    # Unpinned floating texts (damage numbers, pickup notifications).
    unpinned = [ft for ft in STATE.floating_texts if not (len(ft) >= 6 and ft[5] == "pin")]
    for ft in unpinned:
        txt = font_terminal_small.render(ft[2], True, ft[3])
        screen.blit(txt, (ft[0] - cam_x - txt.get_width() // 2, ft[1] - cam_y))

    # Vignette is part of the world grade; the lighting composite follows it in
    # the wrapper, and the HUD is drawn after the composite so it stays legible.
    draw_vignette(screen)


def game_draw(fcx, fcy):
    cam_x, cam_y = int(round(fcx)), int(round(fcy))
    _M4_CAM[0], _M4_CAM[1] = cam_x, cam_y
    lit = artpack.enabled()
    if lit:
        lighting.buffer().begin_frame(_m4_wing_name(), _m4_doors_sig())
    _game_draw_inner(cam_x, cam_y)
    if lit:
        _push_m4_lights(cam_x, cam_y, _now_s())
        lighting.buffer().composite(screen, _now_s())

    _m4_draw_rain()
    draw_scanlines(screen)

    if STATE.player_dead:
        from entities import death_anim
        death_anim.draw_death_overlay(screen, cam_x, cam_y)

    # GC flash overlay (grenade/blast white flash) - matches M1/M2/M3.
    if STATE.gc_flash_timer > 0 and not getattr(STATE, "reduced_motion", False):
        flash_surf = get_fullscreen_overlay((255, 255, 255, 255))
        flash_surf.set_alpha(min(255, STATE.gc_flash_timer * 22))
        screen.blit(flash_surf, (0, 0))

    # HUD last, on top of the graded world.
    _draw_m4_hud(screen, cam_x, cam_y)
    _draw_m4_dialogue(screen)
    if (getattr(STATE, "mission4_stage", None) != STAGE_DONE
            and not getattr(STATE, "m4_dialogue_active", False)):
        draw_combat_reticle(screen)
