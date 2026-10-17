"""palette.py - the locked house palette shared by every tools/sprites generator.

One source of truth for sprite colours (Polish Task 7). Values are lifted
from the two existing authorities so new sheets sit next to old art without
a seam:

  * tools/make_art_pack.py  - floor/wall/prop tier (FLOOR, WALL, SHELF_*, ...)
  * src/game/art/m5/_kit.py - M5 house-style reference (INK, CREAM, BRASS, ...)
  * the live procedural renderers each sheet replaces (car paints, IPA
    cargo browns, tanker greys) so ACA_ART=legacy and the sprite tier agree
    on colour identity.

Lighting contract (same as game/art/m5/_kit.py): key light from the UPPER-LEFT.
``ramp(base)`` returns a 5-step material ramp [deep, shade, base, lit, hi]
whose shadows drift cool (toward blue) and highlights drift warm (toward
yellow); outlines are the ramp's ``deep`` step pushed darker ("1 px darker
hue"), never pure black.

pygame-free on purpose: generators import it before pygame.init().
"""

T = 64  # TILE_SIZE - every sheet is authored 1:1 at this pixel scale

# ── neutrals / ink (game/art/m5/_kit.py) ──
INK = (28, 24, 22)
CREAM = (214, 200, 164)
PAPER = (222, 214, 190)
BRASS = (176, 140, 62)
GOLD_HI = (232, 200, 120)
GOLD_LO = (112, 84, 36)
KRAP_BLUE = (52, 86, 150)
SOOT = (10, 8, 7)
ASH = (58, 50, 44)

# ── world tier (tools/make_art_pack.py) ──
ROAD = (32, 33, 33)
WALL = (45, 46, 44)
BARRIER = (60, 50, 40)
SHELF_WOOD = (34, 28, 24)
SHELF_EDGE = (74, 62, 50)
SKIN = (210, 180, 140)
UNIFORM = (60, 70, 50)
RED = (178, 42, 42)

# ── vehicles (missions/m2/draw.py palettes, locked) ──
CAR_PAINTS = (
    ("faded_red", (148, 52, 44)),
    ("sand", (158, 140, 96)),
    ("teal", (58, 110, 108)),
    ("dusty_white", (188, 184, 172)),
    ("faded_blue", (74, 96, 128)),
    ("rust_brown", (112, 78, 52)),
)
GLASS = (28, 38, 48)
GLASS_HI = (70, 90, 105)
TYRE = (16, 16, 18)
TYRE_HI = (52, 50, 48)
HUB = (95, 90, 84)
HEADLIGHT = (232, 212, 142)
TAILLIGHT = (200, 50, 40)
PLATE = (180, 175, 160)
IPA_CARGO = (78, 60, 44)
IPA_CAB = (68, 55, 42)
IPA_STENCIL = (200, 175, 130)
TANK_STEEL = (88, 82, 70)
TANK_CAB = (70, 66, 56)
MANIFOLD = (70, 74, 80)
VALVE_RED = (140, 35, 30)
HAZARD = (220, 160, 30)
CHAR = (26, 21, 18)          # charred hull base

# ── fire / glow ramp (blast FX, smoulder) ──
FIRE = ((180, 60, 25), (255, 90, 25), (255, 150, 45), (255, 210, 110), (255, 245, 200))

# ── props ──
CONE_ORANGE = (228, 100, 32)
BARREL_RUST = (104, 72, 48)
SIGN_STEEL = (72, 80, 84)
CASE_BEIGE = (192, 182, 152)
PHOSPHOR = (90, 220, 120)
PHOSPHOR_HI = (180, 255, 200)
CRT_GLASS = (4, 12, 8)
PUDDLE = (22, 32, 42)

_COOL = (40, 60, 110)   # shadow drift target
_WARM = (255, 236, 170)  # highlight drift target


def clamp(c):
    return tuple(max(0, min(255, int(round(v)))) for v in c[:3])


def mix(a, b, t):
    return clamp([a[i] + (b[i] - a[i]) * t for i in range(3)])


def shade(c, f):
    return clamp([v * f for v in c[:3]])


def ramp(base, steps=5, contrast=1.0):
    """[deep, shade, base, lit, hi] - cool shadows, warm highlights.

    ``steps`` 3 drops deep/hi, 4 drops hi. ``contrast`` scales the spread.
    """
    k = contrast
    deep = mix(shade(base, 1 - 0.52 * k), _COOL, 0.16 * k)
    shd = mix(shade(base, 1 - 0.28 * k), _COOL, 0.10 * k)
    lit = mix(base, _WARM, 0.16 * k)
    hi = mix(base, _WARM, 0.34 * k)
    full = [deep, shd, clamp(base), lit, hi]
    if steps == 3:
        return [shd, clamp(base), lit]
    if steps == 4:
        return full[:4]
    return full


def outline_of(c):
    """1 px darker-hue outline colour for a fill colour."""
    return mix(shade(c, 0.38), _COOL, 0.12)
