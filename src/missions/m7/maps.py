"""Mission 7 top-down farm: tile grid, palette and interaction points (beats 2 and 4).

The grid is the legacy copy of ``content/levels/m7.farm.level.json`` (the data
file wins unless ``ACA_LEVEL_SRC=legacy``).  Props are drawn in code from the
tile characters; the art pack has no farm tiles.
"""
from game import levels as _levels

LEVEL_ID = "m7.farm"
TILE = 64
COLS, ROWS = 15, 10
# Screen offset of the 15x10 map inside the 1000x700 canvas.
ORIGIN = (20, 30)

# '#' fence, 'H' house, 'B' barn wall, 'W' well, 'G' generator, 'T' tractor,
# 'N' feed bin, 's' fuel shed, 'f' pen fence, '.' open ground, ':' track.
FARM_GRID = [
    "#########BBBBB#",
    "#.HHHH...B...B#",
    "#.HHHH...B...B#",
    "#.HHHH...BB.BB#",
    "#...........TT#",
    "#.......W.N...#",
    "#........fffff#",
    "#sss.....f....#",
    "#....G........#",
    "######:::######",
]
SOLID = frozenset("#HBWGTNsf")

PLAYER_TILE = (4.5, 4.5)
BODI_TILE = (6.5, 4.5)
LOFT_TILE = (10.5, 1.4)     # beat 4: Bodi in the hayloft
ALEX_TILE = (9.5, 8.5)      # beat 4: Alex waits by his bike
BIKE_AT = (10.5, 8.5)
# Beat 4: the tractor parks across the track mouth (pixel top-left of its sprite).
TRACTOR_PARK = (int(6.5 * TILE), 8 * TILE)

HOUSE = (2, 1, 4, 3)        # col, row, cols, rows
BARN = (9, 0, 5, 4)
BARN_INSIDE = (10, 1, 3, 2)
PEN = (10, 7, 4, 2)
TROUGH = (11, 7)            # col, row of the first of its two tiles
TRACTOR_AT = (12, 4)        # col, row of its two tiles

# A clear reversing lane, followed by low-speed stationary steering manoeuvres.
# The feed bin and well stand south of this lane, not across it.
TRACTOR_ROUTE = (
    ((13.0, 4.5), (7.0, 4.5), 0.0, 0.0, "s", "REVERSE ALONG THE YARD"),
    ((7.0, 4.5), (7.0, 4.5), 0.0, -90.0, "a", "TURN THE WHEELS LEFT"),
    ((7.0, 4.5), (7.0, 7.0), -90.0, -90.0, "s", "BACK DOWN THE LANE"),
    ((7.0, 7.0), (7.0, 7.0), -90.0, -180.0, "a", "TURN TOWARD THE TRACK"),
    ((7.0, 7.0), (7.5, 7.0), -180.0, -180.0, "s", "BACK INTO POSITION"),
    ((7.5, 7.0), (7.5, 7.0), -180.0, -90.0, "d", "STRAIGHTEN FOR THE TRACK"),
    ((7.5, 7.0), (7.5, 8.5), -90.0, -90.0, "s", "BACK TO THE GATE"),
    ((7.5, 8.5), (7.5, 8.5), -90.0, 0.0, "d", "BLOCK THE TRACK"),
)


def tractor_route_px():
    return tuple((a[0] * TILE, a[1] * TILE, b[0] * TILE, b[1] * TILE, h0, h1, key, label)
                 for a, b, h0, h1, key, label in TRACTOR_ROUTE)

# Interaction points: tile-centre coordinates and reach in pixels.
POINTS = {
    "generator": {"at": (5.5, 8.5), "reach": 84},
    "well": {"at": (8.5, 5.5), "reach": 92},
    "bin": {"at": (10.5, 5.5), "reach": 86},
    "trough": {"at": (12.0, 7.5), "reach": 92},
    "hay": {"at": (12.5, 1.5), "reach": 80},
    "porch": {"at": (3.0, 4.5), "reach": 52},
    "tractor": {"at": (13.0, 4.5), "reach": 96},
    "shed": {"at": (2.0, 8.0), "reach": 90},
}

# Flat daylight palette, shared by the tiles and the props.
GRASS = ((78, 98, 60), (62, 82, 48), (98, 118, 72))
DIRT = ((126, 100, 70), (104, 80, 56), (148, 122, 88))
PENDIRT = ((118, 92, 64), (96, 74, 50), (150, 124, 70))
TRACK = ((112, 88, 62), (88, 66, 46), (130, 104, 76))
HAYFLOOR = ((176, 148, 82), (148, 120, 60), (200, 172, 104))
INK = (30, 24, 22)
WOOD = (104, 72, 50)
WOOD_D = (76, 52, 38)
WOOD_L = (136, 98, 68)
ROOF = (150, 66, 48)
ROOF_D = (116, 48, 36)
ROOF_L = (178, 90, 62)
BARN_WALL = (112, 60, 52)
STONE = (124, 124, 118)
STONE_D = (88, 88, 84)
WATER = (52, 88, 116)
METAL = (122, 126, 130)
METAL_D = (84, 88, 94)
TRACTOR = (52, 112, 70)
TRACTOR_D = (36, 78, 50)
GENERATOR = (186, 98, 42)
GRAIN = (200, 170, 96)
SKY_EDGE = (22, 26, 22)


def farm_grid():
    return _levels.grid(LEVEL_ID, FARM_GRID)


def tile_px(tile):
    """Map-pixel centre of a (col, row) float pair."""
    return int(tile[0] * TILE), int(tile[1] * TILE)
