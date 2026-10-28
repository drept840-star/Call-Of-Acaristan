"""The 2D top-down M7 farm palette, for the 3D farm (raid and films).

Sampled from gameplay frames of the 2D farmyard (chores and prep stages:
house, barn, hayloft, pen, shed, track, grass, fences).  ``assets/tex3d/m7.gpl``
is the same set as a GIMP palette, for painting the M7 3D textures
(``tools/tex3d_draw_m7.py``).

The 2D farm is a flat daylight set; the 3D night comes from the light, the
fog and the raid grade, so these stay daylight albedos.  The few colours
marked "derived" are not on screen in 2D: autumn shades mixed from sampled
neighbours (stubble loam, dry grass, plaster shade) and the far-hill darks.
"""

INK = (30, 24, 22)              # the 2D outline: never true black
INK_DEEP = (9, 10, 9)
SKY_EDGE = (22, 26, 22)         # the 2D map border

GRASS = (78, 98, 60)
GRASS_D = (62, 82, 48)
GRASS_HI = (98, 118, 72)
GRASS_DD = (40, 48, 29)         # tuft shadows
GRASS_INK = (25, 33, 19)
MOSS = (56, 71, 43)

DIRT = (126, 100, 70)           # yard
DIRT_D = (104, 80, 56)
DIRT_HI = (148, 122, 88)
PENDIRT = (118, 92, 64)
TRACK = (112, 88, 62)
TRACK_D = (88, 66, 46)
TRACK_HI = (130, 104, 76)

HAY = (200, 170, 96)
HAY_HI = (200, 172, 104)
HAY_MID = (176, 148, 82)
HAY_SIDE = (166, 136, 70)
HAY_SHADE = (148, 120, 60)
HAY_D = (127, 107, 59)          # hayloft floor: the ochre of the stubble
HAY_DD = (107, 87, 43)

WOOD = (104, 72, 50)
WOOD_D = (76, 52, 38)
WOOD_L = (136, 98, 68)
WOOD_GREY = (76, 66, 58)        # weathered, silvered boards
WOOD_DUN = (86, 68, 48)
WOOD_MID = (96, 74, 50)
WOOD_DARK = (44, 38, 36)
WOOD_BLACK = (36, 30, 26)

ROOF = (150, 66, 48)            # clay tile
ROOF_D = (116, 48, 36)
ROOF_L = (178, 90, 62)
BARN = (112, 60, 52)            # oxblood boards
BARN_D = (84, 44, 38)
BARN_L = (140, 80, 66)
BARN_DD = (46, 24, 21)
BARN_INK = (34, 18, 15)
BRICK_D = (60, 34, 30)

PLASTER = (206, 190, 156)       # whitewash
PLASTER_L = (226, 220, 206)
STONE = (124, 124, 118)
STONE_D = (88, 88, 84)
GALV = (122, 126, 130)          # galvanised sheet
GALV_D = (84, 88, 94)
STEEL_D = (52, 52, 56)
RUST = (120, 60, 28)
RUST_D = (70, 40, 24)
WATER = (52, 88, 116)
GLASS = (60, 86, 112)
TRACTOR = (52, 112, 70)
TRACTOR_D = (36, 78, 50)
GENERATOR = (186, 98, 42)       # the orange of the generator and the twine
LAMP = (200, 156, 116)          # the porch light's pool in 2D

# derived (autumn and night shades that 2D never draws)
LOAM = (66, 50, 36)             # ploughed earth between the stubble rows
GRASS_DRY = (96, 98, 58)        # late-season grass going to straw
PLASTER_SHADE = (176, 164, 138)
HILL_NEAR = (26, 32, 30)        # far masses: aerial perspective in the albedo
HILL_FAR = (40, 48, 54)


def full(col):
    """``col`` scaled so its brightest channel is 255: a swatch as a light."""
    k = 255.0 / max(col)
    return tuple(min(255, int(round(c * k))) for c in col)


LAMP_WARM = full(LAMP)          # (255, 199, 148): porch and barn bulbs
WINDOW = full(HAY_HI)           # (255, 219, 133): lamplit panes
