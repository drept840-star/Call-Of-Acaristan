
"""surfaces.py - floor-material zones for footstep timbre selection.

Deliberately tiny and data-only: a list of world-space rects per mission and a
default. Rects reuse room layouts already authored in the mission draw code;
they are tuning data, not simulation. Unknown mission/position -> concrete.
"""

TILE = 64


def _r(c0, r0, c1, r1):
    return (c0 * TILE, r0 * TILE, c1 * TILE, r1 * TILE)


# (rect, material). First match wins; keep lists short and specific.
MATERIAL_ZONES = {
    "MISSION1": [
        (_r(12, 20, 20, 26), "metal"),     # warehouse bay / workspace plates
        (_r(2, 4, 12, 12), "debris"),      # yard rubble
        (_r(14, 23, 18, 26), "wet"),       # puddle by the gate
    ],
    "MISSION2": [
        (_r(20, 16, 30, 24), "metal"),     # tanker pad / truck deck
        (_r(30, 8, 40, 16), "debris"),     # garden rubble
        (_r(10, 20, 14, 24), "water"),     # flooded ditch
    ],
    "MISSION3": [
        (_r(20, 20, 32, 28), "grate"),     # service corridors
        (_r(36, 32, 46, 42), "metal"),     # comms server room
        (_r(16, 30, 20, 34), "wet"),       # shower row
    ],
    "WALK": [
        (_r(20, 8, 30, 14), "debris"),     # warehouse approach rubble
    ],
}

DEFAULT_MATERIAL = "concrete"

# prefix + variant count per material (concrete reuses the original family)
_FOOT_PREFIX = {
    "concrete": ("footstep", 3),
    "metal": ("footstep_metal", 3),
    "grate": ("footstep_grate", 2),
    "wet": ("footstep_wet", 2),
    "water": ("footstep_water", 2),
    "debris": ("footstep_debris", 2),
}


def material_at(x, y, mission):
    for rect, mat in MATERIAL_ZONES.get(mission, ()):
        x0, y0, x1, y1 = rect
        if x0 <= x <= x1 and y0 <= y <= y1:
            return mat
    return DEFAULT_MATERIAL


def footstep_prefix(material):
    return _FOOT_PREFIX.get(material, _FOOT_PREFIX["concrete"])
