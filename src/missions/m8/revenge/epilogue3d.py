"""Mission 8 Revenge - phase 7: the epilogue, one 3D shot per line.

Staged on the chase set (``chase_set``): the train running east from the Kim
Kim crossing with Biribel on the last car's step, Bodi's tractor dead on the
tracks, Ucilev at the border hut with the photo.  The state TV studio and the
funeral in the mansion grounds are small stages built off the road, far out
in the fields, until the Duty mansion set exists.

``draw(surface, line, t)`` renders line ``line`` of ``meta.BEATS[epilogue]``
``t`` seconds after it came up; ``beats`` owns the plate and the input.
"""
import json
import math
import os

import pygame

from core.config import HEIGHT, WIDTH, font_terminal_small, font_title
from core.outfits import OUTFIT_GUARD
from cutscenes import m6world3d as _w
from cutscenes import m7world3d as W7
from engine3d import POSES, Mesh, box
from engine3d.core import quad_xz, rot_y, rot_z
from engine3d.textures import tex

from . import chase_set as S

RX = S.road_x(S.CROSSING_Z)
CZ = S.CROSSING_Z
STUDIO = (-150.0, 420.0)        # x, z: state TV, out in the west fields
FUNERAL = (150.0, 600.0)        # the mansion grounds, east fields
NIGHT = (58, 68, 108)
DUSK = (104, 112, 152)
TV_TINT = (210, 222, 236)

# laid out: flat on his back, legs straight, arms at his sides
LYING = dict(POSES["dead_back"], body_r=0, head_y=0, head_p=0, lhip_p=0, lhip_r=0, lkn=0,
             rhip_p=0, rhip_r=0, rkn=0, lsh_p=0, lsh_r=6, lel=6, rsh_p=0, rsh_r=6, rel=6)
LYING.update(head_p=-6, lhip_p=4, lhip_r=4, lkn=6, rhip_p=4, rhip_r=4, rkn=6)
_MARU_POSE = {}


def maru_pose(pos=(FUNERAL[0] - 0.02, 1.24, FUNERAL[1]), yaw=90.0):
    """Maru lying flat with hands folded peacefully across his lower chest."""
    key = (pos, yaw)
    got = _MARU_POSE.get(key)
    if got is None:
        h = _w.hum("maru", flags=("suit",))
        base = dict(LYING)
        _, j, _ = h.pose_world(base, pos, yaw, rifle_on=False)
        cx, cy, cz = j["chest"]
        pole = (0.72, -0.45, -0.78)
        p = _w.reach(h, base, "l", (cx + 0.15, cy + 0.08, cz + 0.01), pos, yaw, pole=pole)
        p = _w.reach(h, p, "r", (cx + 0.13, cy + 0.11, cz - 0.01), pos, yaw, pole=pole)
        got = _MARU_POSE[key] = p
    return got
_SEATED = dict(POSES["stand"], lhip_p=88, lkn=86, rhip_p=88, rkn=86, lsh_p=46, lel=40,
               rsh_p=46, rel=40, spine=6)


# --- the off-road stages -----------------------------------------------------

NAVY, RED, GOLD = (26, 36, 62), (150, 30, 32), (230, 200, 120)


def _flag(m, x, z, h=2.75, w=0.7):
    """A hanging state flag on a pole: navy over red, four fold strips."""
    m.add(box(0.05, h, 0.05, (150, 140, 108), center=(x, h / 2, z)))
    m.add(box(0.09, 0.07, 0.09, GOLD, center=(x, h + 0.03, z)))
    m.add(box(w, 0.03, 0.03, (150, 140, 108), center=(x + w / 2, h - 0.13, z)))
    n = 4
    for i in range(n):
        sh = 1.0 - 0.15 * (i % 2)
        cx, cz = x + (i + 0.5) * w / n, z + (0.035 if i % 2 else -0.01)
        m.add(box(w / n, h * 0.2, 0.02, tuple(int(c * sh) for c in NAVY), center=(cx, h - 0.42, cz)))
        m.add(box(w / n, h * 0.2, 0.02, tuple(int(c * sh) for c in RED), center=(cx, h - 0.97, cz)))


def studio(chair=True):
    """State TV, studio A: dark acoustic navy set framed for the broadcast
    camera - crest, lit side monitors, flags, recessed light columns, desk and truss."""
    m = Mesh()
    sx, sz = STUDIO
    m.add(box(18.0, 0.06, 16.0, W7._t("plank", (24, 26, 36)), center=(sx, 0.03, sz - 1.0)))
    m.add(box(10.0, 0.02, 5.0, (16, 22, 46), center=(sx, 0.07, sz + 1.0)))          # carpet
    m.add(box(16.0, 5.6, 0.3, (16, 21, 40), center=(sx, 2.8, sz + 3.4)))            # back wall
    m.add(box(4.2, 4.0, 0.08, (12, 16, 34), center=(sx, 2.0, sz + 3.24)))           # center recess
    m.add(box(16.0, 0.2, 12.0, (12, 14, 24), center=(sx, 5.6, sz - 2.0)))           # ceiling
    for dx in (-7.8, 7.8):                                                          # side walls past cam
        m.add(box(0.3, 5.6, 12.0, (14, 18, 36), center=(sx + dx, 2.8, sz - 2.0)))
    for y in (0.4, 2.85):                                                           # horizontal strips
        m.add(box(12.0, 0.04, 0.04, (95, 138, 225), center=(sx, y, sz + 3.20), emissive=True))
    for dx in (-3.6, -2.18, 2.18, 3.6):                                             # vertical light columns
        m.add(box(0.045, 3.4, 0.04, (80, 120, 210), center=(sx + dx, 2.0, sz + 3.20), emissive=True))
    # the crest: lowered to y=2.14 so it sits in frame above the anchor
    cy = 2.14
    m.add(box(0.86, 0.86, 0.06, (14, 19, 36), center=(sx, cy, sz + 3.19)))
    for i in range(16):
        a = 2 * math.pi * i / 16
        m.add(box(0.14, 0.04, 0.04, GOLD), rot_z(math.degrees(a) + 90),
              (sx + 0.31 * math.cos(a), cy + 0.31 * math.sin(a), sz + 3.15))
    for i in range(5):
        a = 90 + i * 72
        m.add(box(0.06, 0.22, 0.03, GOLD, center=(0.0, 0.11, 0.0)), rot_z(a - 90), (sx, cy, sz + 3.14))
    # side monitors: brought in to dx=+-1.55, y=1.74 so both appear on camera
    for dx in (-1.55, 1.55):
        m.add(box(1.15, 0.68, 0.06, (10, 12, 16), center=(sx + dx, 1.74, sz + 3.18)))
        m.add(box(1.03, 0.56, 0.02, (34, 62, 128), center=(sx + dx, 1.74, sz + 3.14), emissive=True))
        for j in range(4):
            h = 0.10 + 0.08 * j
            m.add(box(0.13, h, 0.01, (190, 204, 236),
                      center=(sx + dx - 0.30 + j * 0.20, 1.50 + h / 2, sz + 3.12), emissive=True))
    _flag(m, sx - 3.10, sz + 2.85, h=2.55, w=0.62)
    _flag(m, sx + 2.48, sz + 2.85, h=2.55, w=0.62)
    # anchor desk (0.88 m tall so seated/standing torso reads cleanly) + wings + chair
    body, top, strip = (18, 22, 34), (58, 56, 62), (110, 160, 245)
    m.add(box(2.6, 0.85, 0.70, body, center=(sx, 0.425, sz + 0.80)))
    m.add(box(2.7, 0.05, 0.82, top, center=(sx, 0.875, sz + 0.80)))
    for s in (-1, 1):
        wing = Mesh()
        wing.add(box(1.4, 0.85, 0.66, body, center=(0.0, 0.425, 0.0)))
        wing.add(box(1.5, 0.05, 0.78, top, center=(0.0, 0.875, 0.0)))
        wing.add(box(1.36, 0.04, 0.02, strip, center=(0.0, 0.69, -0.34), emissive=True))
        m.add(wing, rot_y(-s * 28), (sx + s * 1.85, 0.0, sz + 1.12))
    m.add(box(2.5, 0.04, 0.02, strip, center=(sx, 0.69, sz + 0.44), emissive=True))
    m.add(box(0.64, 0.32, 0.03, GOLD, center=(sx, 0.40, sz + 0.44)))
    m.add(box(0.46, 0.18, 0.02, NAVY, center=(sx, 0.40, sz + 0.425)))
    m.add(box(0.36, 0.02, 0.26, (226, 222, 206), center=(sx - 0.36, 0.91, sz + 0.72)))  # papers
    m.add(box(0.04, 0.24, 0.04, (28, 28, 30), center=(sx + 0.46, 1.02, sz + 0.64)))     # desk mic
    if chair:
        m.add(box(0.54, 0.08, 0.50, (24, 24, 28), center=(sx, 0.44, sz + 1.40)))             # chair seat
        m.add(box(0.54, 0.66, 0.08, (24, 24, 28), center=(sx, 0.78, sz + 1.66)))             # chair back
    return m


CMD_ROOM = (-250.0, 420.0)      # x, z: Guard command room, west fields
PHONE_POS = (CMD_ROOM[0] - 0.44, 0.90, CMD_ROOM[1] + 0.82)
PHONE_YAW = 26.0
PHONE_SCALE = 1.15

_PHONE_CACHE = {}
_DEFAULT_PHONE_META = {
    "base": {
        "cradle_saddle_y": 0.095,
        "cradle_z": -0.034,
        "horn_top_y": 0.114,
        "cord_jack": [0.060, 0.022, -0.025],
    },
    "handset": {
        "ear_grill": [0.093, -0.026, 0.0],
        "mouth_grill": [-0.093, -0.022, 0.0],
        "cord_collar": [-0.111, 0.002, 0.0],
        "handle_bounds_yz": [-0.015, 0.015, -0.014, 0.014],
        "cradle_rest_y": -0.015,
    },
}


def _load_phone_asset(ref):
    try:
        from game.render3d_bridge import MESHES_DIR, load_mesh_asset

        verts, faces = load_mesh_asset(ref)
        m = Mesh()
        m.verts = [tuple(float(c) for c in v) for v in verts]
        m.faces = [(tuple(f[0]), tuple(f[1]), 2, True, False) for f in faces]
        meta = {}
        path = os.path.join(MESHES_DIR, f"{ref}.mesh.json")
        with open(path, encoding="utf-8") as fh:
            meta = json.load(fh).get("meta", {})
        return m, meta
    except Exception:
        return None, None


def _fallback_phone_base():
    m = Mesh()
    body, dark, chrome, dial = (38, 42, 50), (22, 24, 30), (200, 206, 216), (210, 212, 214)
    m.add(box(0.136, 0.014, 0.156, dark, center=(0.0, 0.007, 0.001)))
    m.add(box(0.134, 0.076, 0.168, body, center=(0.0, 0.052, -0.002)))
    for sx in (-0.037, 0.037):
        m.add(box(0.012, 0.024, 0.010, body, center=(sx, 0.102, -0.050)))
        m.add(box(0.012, 0.021, 0.009, body, center=(sx, 0.100, -0.019)))
        m.add(box(0.008, 0.018, 0.008, chrome, center=(sx, 0.100, -0.034)))
    m.add(box(0.082, 0.020, 0.082, chrome, center=(0.0, 0.056, 0.048)))
    m.add(box(0.072, 0.022, 0.072, dial, center=(0.0, 0.058, 0.048)))
    m.add(box(0.016, 0.014, 0.084, dark, center=(0.018, 0.007, -0.134)))
    return m


def _fallback_phone_handset():
    m = Mesh()
    body, grill, dark = (38, 42, 50), (140, 144, 150), (22, 24, 30)
    m.add(box(0.164, 0.028, 0.026, body, center=(0.0, 0.0, 0.0)))
    for x in (-0.093, 0.093):
        m.add(box(0.052, 0.034, 0.052, body, center=(x, -0.009, 0.0)))
        m.add(box(0.042, 0.006, 0.042, grill, center=(x, -0.025, 0.0)))
    m.add(box(0.018, 0.014, 0.014, dark, center=(-0.114, 0.002, 0.0)))
    return m


def _phone_bundle():
    got = _PHONE_CACHE.get("bundle")
    if got is None:
        base_m, base_meta = _load_phone_asset("telephone_base")
        hs_m, hs_meta = _load_phone_asset("telephone_handset")
        if base_m is None:
            base_m, base_meta = _fallback_phone_base(), dict(_DEFAULT_PHONE_META["base"])
        if hs_m is None:
            hs_m, hs_meta = _fallback_phone_handset(), dict(_DEFAULT_PHONE_META["handset"])
        meta = {
            "base": {**_DEFAULT_PHONE_META["base"], **(base_meta or {})},
            "handset": {**_DEFAULT_PHONE_META["handset"], **(hs_meta or {})},
        }
        got = _PHONE_CACHE["bundle"] = (base_m, hs_m, meta)
    return got


def telephone_base_mesh():
    return _phone_bundle()[0]


def telephone_handset_mesh():
    return _phone_bundle()[1]


def telephone_meta():
    return _phone_bundle()[2]


def command_room():
    """Guard command / situation room: dark slate walls, tactical Route 12
    wall map, radio racks, steel desk with field radio & gooseneck mic."""
    m = Mesh()
    cx, cz = CMD_ROOM
    floor = W7._t("plank", (24, 26, 28))
    wall = (28, 32, 34)
    trim = (18, 20, 22)
    steel = (52, 56, 58)
    olive = (54, 62, 46)

    m.add(box(16.0, 0.08, 14.0, floor, center=(cx, 0.04, cz - 1.0)))
    m.add(box(16.0, 5.0, 0.3, wall, center=(cx, 2.5, cz + 3.2)))
    m.add(box(16.0, 0.2, 14.0, (14, 16, 18), center=(cx, 5.0, cz - 1.0)))
    for dx in (-7.8, 7.8):
        m.add(box(0.3, 5.0, 14.0, wall, center=(cx + dx, 2.5, cz - 1.0)))
    m.add(box(15.4, 0.9, 0.06, trim, center=(cx, 0.45, cz + 3.02)))

    # Tactical wall map behind Retardovici: Route 12 & Kim Kim rail crossing.
    m.add(box(3.4, 1.7, 0.06, (20, 22, 24), center=(cx, 1.92, cz + 3.00)))
    m.add(box(3.16, 1.46, 0.02, (74, 82, 68), center=(cx, 1.92, cz + 2.96)))
    m.add(box(3.16, 0.05, 0.015, (165, 48, 42), center=(cx, 2.24, cz + 2.94)))
    for i in range(6):
        px = cx - 0.85 + 0.14 * math.sin(i * 0.9)
        py = 1.36 + i * 0.17
        m.add(box(0.06, 0.21, 0.015, (38, 42, 44), center=(px, py, cz + 2.94)))
    for px, py in ((cx - 0.80, 1.82), (cx - 0.78, 2.24)):
        m.add(box(0.09, 0.09, 0.03, (235, 65, 50), center=(px, py, cz + 2.93), emissive=True))

    # Left comms rack with green/amber status LEDs.
    rx, rz = cx - 2.45, cz + 2.45
    m.add(box(1.1, 2.1, 0.7, trim, center=(rx, 1.05, rz)))
    for y in (0.65, 1.15, 1.65):
        m.add(box(0.92, 0.36, 0.04, olive, center=(rx, y, rz - 0.36)))
        m.add(box(0.08, 0.05, 0.02, (80, 210, 110), center=(rx - 0.28, y + 0.08, rz - 0.39), emissive=True))
        m.add(box(0.08, 0.05, 0.02, (230, 160, 55), center=(rx - 0.14, y + 0.08, rz - 0.39), emissive=True))

    # Steel command desk (matching epi_president desk height & depth).
    m.add(box(2.7, 0.85, 0.72, trim, center=(cx, 0.425, cz + 0.80)))
    m.add(box(2.8, 0.05, 0.84, steel, center=(cx, 0.875, cz + 0.80)))
    m.add(box(0.68, 0.015, 0.48, (186, 182, 166), center=(cx + 0.32, 0.91, cz + 0.74)))
    m.add(box(0.28, 0.02, 0.20, (140, 120, 90), center=(cx + 0.16, 0.92, cz + 0.90)))

    # Rotary desk telephone on Retardovici's right (-X), replacing the radio & desk mic.
    phone = telephone_base_mesh()
    if PHONE_SCALE != 1.0:
        scaled = Mesh()
        scaled.verts = [(v[0] * PHONE_SCALE, v[1] * PHONE_SCALE, v[2] * PHONE_SCALE) for v in phone.verts]
        scaled.faces = list(phone.faces)
        phone = scaled
    m.add(phone, rot_y(PHONE_YAW), PHONE_POS)
    # Chair behind desk.
    m.add(box(0.54, 0.08, 0.50, (24, 24, 28), center=(cx, 0.44, cz + 1.40)))
    m.add(box(0.54, 0.66, 0.08, (24, 24, 28), center=(cx, 0.78, cz + 1.66)))
    return m


def command_lights():
    """Crisp dark war-room lighting (warm key, cool fill, cool steel-blue rim)."""
    cx, cz = CMD_ROOM
    return [
        {"pos": (cx - 1.6, 2.7, cz - 2.0), "color": (255, 224, 180), "intensity": 0.90, "range": 8.0},
        {"pos": (cx + 2.4, 2.2, cz - 2.4), "color": (120, 155, 215), "intensity": 0.28, "range": 8.0},
        {"pos": (cx + 0.4, 2.6, cz + 2.5), "color": (100, 150, 225), "intensity": 0.60, "range": 6.5},
    ]


LAMP_H = 3.2
ESTATE_LAMPS = tuple((FUNERAL[0] + s * 3.4, FUNERAL[1] + z) for z in (-22.0, -16.0, -10.0)
                     for s in (-1, 1))
CANDLES = tuple((FUNERAL[0] + dx, FUNERAL[1] + dz) for dx in (-1.75, 1.75) for dz in (-0.90, 0.90))
HONOUR = ((-2.85, 0.0, 90.0), (2.85, 0.0, 270.0), (-1.15, 2.15, 180.0), (1.15, 2.15, 180.0))


def _lamp_post(m, x, z, h=LAMP_H):
    m.add(box(0.36, 0.3, 0.36, (40, 40, 42), center=(x, 0.15, z)))
    m.add(box(0.11, h, 0.11, (30, 30, 32), center=(x, h / 2, z)))
    m.add(box(0.34, 0.08, 0.34, (30, 30, 32), center=(x, h + 0.04, z)))
    m.add(box(0.26, 0.4, 0.26, (255, 226, 160), center=(x, h + 0.28, z), emissive=True))
    m.add(box(0.38, 0.1, 0.38, (30, 30, 32), center=(x, h + 0.52, z)))


def _window(m, x, y, z):
    m.add(box(1.5, 2.1, 0.08, (226, 222, 210), center=(x, y, z)))
    m.add(box(1.2, 1.8, 0.04, (238, 206, 140), center=(x, y, z - 0.05), emissive=True))
    m.add(box(1.2, 0.05, 0.02, (60, 50, 40), center=(x, y, z - 0.08)))
    m.add(box(0.05, 1.8, 0.02, (60, 50, 40), center=(x, y, z - 0.08)))
    for s in (-1, 1):
        m.add(box(0.5, 1.9, 0.05, (52, 66, 54), center=(x + s * 1.0, y, z - 0.04)))
    m.add(box(1.7, 0.12, 0.2, (226, 222, 210), center=(x, y - 1.1, z - 0.08)))


def funeral():
    """The estate at night: a plastered mansion with a tile roof, a portico on
    four columns and every window lit; a gravel drive between hedges, lamp
    posts and poplars; the gate piers; the flag-draped bier on its dais."""
    m = Mesh()
    fx, fz = FUNERAL
    stone = W7._t("stone", (150, 146, 136))
    plaster = W7._t("plaster", (198, 190, 170))
    tile = W7._t("tile", (122, 60, 48))
    gravel = W7._t("gravel", (92, 90, 86), tint=True)
    m.add(quad_xz(fx - 60, fz - 45, fx + 60, fz + 45, 0.06, W7._t("grass", (52, 68, 44)), layer=1, seg=10.0))
    m.add(quad_xz(fx - 2.4, fz - 31, fx + 2.4, fz - 4.5, 0.09, gravel, layer=1, seg=4.0))
    m.add(quad_xz(fx - 8.0, fz - 4.5, fx + 8.0, fz + 11.5, 0.09, gravel, layer=1, seg=4.0))
    # the mansion: plinth, two floors, string course, cornice, gable roof, chimneys
    mz, mw, md = fz + 16.0, 26.0, 8.0
    front = mz - md / 2
    m.add(box(mw + 0.4, 0.8, md + 0.4, stone, center=(fx, 0.4, mz)))
    m.add(box(mw, 8.4, md, plaster, center=(fx, 4.6, mz)))
    m.add(box(mw + 0.3, 0.22, md + 0.3, stone, center=(fx, 4.6, mz)))
    m.add(box(mw + 0.6, 0.4, md + 0.6, stone, center=(fx, 8.9, mz)))
    m.add(W7._gable_z(md + 0.6, mw + 0.2, 0.0, 3.0, tile, plaster, oh=0.4), rot_y(90), (fx, 9.1, mz))
    for dx in (-8.0, 8.0):
        m.add(box(0.9, 2.6, 0.9, plaster, center=(fx + dx, 11.4, mz + 1.2)))
        m.add(box(1.1, 0.2, 1.1, stone, center=(fx + dx, 12.75, mz + 1.2)))
    for s in (-1, 1):                                                               # the wings
        wx = fx + s * 17.0
        m.add(box(8.4, 0.8, 7.4, stone, center=(wx, 0.4, mz + 2.0)))
        m.add(box(8.0, 5.6, 7.0, plaster, center=(wx, 3.2, mz + 2.0)))
        m.add(box(8.4, 0.3, 7.4, stone, center=(wx, 6.1, mz + 2.0)))
        m.add(W7._gable_z(7.4, 8.4, 0.0, 2.2, tile, plaster, oh=0.3), rot_y(90), (wx, 6.25, mz + 2.0))
        for i in range(3):
            _window(m, wx - 2.6 + i * 2.6, 2.6, mz + 2.0 - 3.52)
    for i in range(9):                                                              # windows
        x = fx - 11.2 + i * 2.8
        for y in (2.6, 6.6):
            if abs(x - fx) > 1.0 or y > 5.0:
                _window(m, x, y, front - 0.02)
    m.add(box(1.6, 2.8, 0.1, (60, 40, 30), center=(fx, 2.2, front - 0.03)))
    m.add(box(1.3, 2.5, 0.04, (236, 210, 150), center=(fx, 2.15, front - 0.09), emissive=True))
    # portico: steps, four columns, entablature, pediment
    for k in range(3):
        m.add(box(7.4 - k * 0.5, 0.2, 2.6 - k * 0.5, stone,
                  center=(fx, 0.1 + k * 0.2, front - 1.3 + k * 0.25)))
    for dx in (-2.7, -0.9, 0.9, 2.7):
        m.add(box(0.5, 0.25, 0.5, stone, center=(fx + dx, 0.72, front - 2.0)))
        m.add(box(0.36, 4.6, 0.36, (226, 222, 210), center=(fx + dx, 3.15, front - 2.0)))
        m.add(box(0.5, 0.22, 0.5, stone, center=(fx + dx, 5.55, front - 2.0)))
    m.add(box(6.6, 0.6, 2.6, (226, 222, 210), center=(fx, 5.95, front - 1.1)))
    m.add(W7._gable_z(6.8, 2.8, 0.0, 1.4, tile, (226, 222, 210), oh=0.2), t=(fx, 6.25, front - 1.1))
    # hedges, poplars, trees in the grounds, lamp posts along the drive
    for s in (-1, 1):
        m.add(W7._hedgerow(fx + s * 3.4, fz - 30.0, fx + s * 3.4, fz - 24.0, seed=3 + s))
        m.add(W7._hedgerow(fx + s * 3.4, fz - 21.0, fx + s * 3.4, fz - 5.0, seed=5 + s))
        m.add(W7._hedgerow(fx + s * 9.5, fz - 4.0, fx + s * 9.5, fz + 9.0, seed=7 + s))
        for k in range(5):
            m.add(W7._poplar(k * 3 + (s > 0), 10.0 + (k * 7) % 3), t=(fx + s * 8.0, 0.0, fz - 28.0 + k * 5.5))
        for k in range(3):
            m.add(W7.tree(k + (s > 0) * 5), t=(fx + s * (24.0 + 4.0 * k), 0.0, fz + 2.0 - 6.0 * k))
    for x, z in ESTATE_LAMPS:
        _lamp_post(m, x, z)
    # gate piers, the iron gate standing open, the low wall
    gz = fz - 31.0
    for s in (-1, 1):
        m.add(box(1.0, 3.0, 1.0, stone, center=(fx + s * 3.2, 1.5, gz)))
        m.add(box(1.2, 0.3, 1.2, stone, center=(fx + s * 3.2, 3.15, gz)))
        m.add(box(0.6, 0.5, 0.6, GOLD, center=(fx + s * 3.2, 3.55, gz)))
        m.add(box(30.0, 1.1, 0.5, stone, center=(fx + s * 18.7, 0.55, gz)))
        leaf = Mesh()
        for k in range(8):
            leaf.add(box(0.05, 2.3, 0.05, (24, 24, 26), center=(0.15 + k * 0.33, 1.15, 0.0)))
        for y in (0.3, 2.2):
            leaf.add(box(2.7, 0.08, 0.06, (24, 24, 26), center=(1.35, y, 0.0)))
        m.add(leaf, rot_y(-70 if s < 0 else -110), (fx + s * 2.7, 0.0, gz))
    # the bier: dais, black cloth, roomy hollow open casket, pillow, open lid, flag
    wood = W7._t("plank", (64, 36, 24))
    satin = (232, 226, 214)
    satin_sh = (212, 206, 194)
    m.add(box(5.0, 0.3, 3.8, stone, center=(fx, 0.15, fz)))
    m.add(box(2.84, 0.70, 1.24, (20, 20, 24), center=(fx, 0.65, fz)))
    m.add(box(2.88, 0.05, 1.28, GOLD, center=(fx, 0.99, fz)))
    # outer mahogany shell (2.52 x 1.08 outer; inner satin well 2.36 x 0.90, mattress top 1.24)
    m.add(box(2.52, 0.14, 1.08, wood, center=(fx, 1.07, fz)))
    m.add(box(2.36, 0.10, 0.92, satin, center=(fx, 1.19, fz)))
    m.add(box(0.50, 0.08, 0.72, (238, 232, 220), center=(fx - 0.84, 1.28, fz)))  # pillow
    for dz in (-0.505, 0.505):
        m.add(box(2.52, 0.36, 0.07, wood, center=(fx, 1.30, fz + dz)))
        m.add(box(2.36, 0.24, 0.02, satin_sh, center=(fx, 1.34, fz + dz * 0.90)))
        m.add(box(2.20, 0.04, 0.04, GOLD, center=(fx, 1.24, fz + dz * 1.12)))
    for dx in (-1.22, 1.22):
        m.add(box(0.08, 0.36, 1.08, wood, center=(fx + dx, 1.30, fz)))
    m.add(box(0.02, 0.24, 0.90, satin_sh, center=(fx - 1.17, 1.34, fz)))
    # closed lower foot-lid with the state flag draped cleanly over it
    m.add(box(1.18, 0.05, 1.08, wood, center=(fx + 0.67, 1.495, fz)))
    m.add(box(1.20, 0.03, 1.10, NAVY, center=(fx + 0.67, 1.525, fz)))
    for sz in (-0.545, 0.545):
        m.add(box(1.20, 0.26, 0.02, NAVY, center=(fx + 0.67, 1.39, fz + sz)))
        m.add(box(1.20, 0.12, 0.02, RED, center=(fx + 0.67, 1.21, fz + sz)))
    m.add(box(0.22, 0.22, 0.02, GOLD, center=(fx + 0.67, 1.39, fz - 0.556)))
    # open upper half-lid hinged at the north edge, leaning up and slightly back
    lx0, lx1 = fx - 1.26, fx + 0.08
    bz0, bz1, tz0, tz1 = fz + 0.505, fz + 0.555, fz + 0.785, fz + 0.835
    m.face([(lx0, 1.48, bz0), (lx1, 1.48, bz0), (lx1, 2.34, tz0), (lx0, 2.34, tz0)], wood, 2, True)
    m.face([(lx0, 1.48, bz1), (lx1, 1.48, bz1), (lx1, 2.34, tz1), (lx0, 2.34, tz1)], wood, 2, True)
    m.face([(lx0, 2.34, tz0), (lx1, 2.34, tz0), (lx1, 2.34, tz1), (lx0, 2.34, tz1)], wood, 2, True)
    m.face([(lx0, 1.48, bz0), (lx0, 1.48, bz1), (lx0, 2.34, tz1), (lx0, 2.34, tz0)], wood, 2, True)
    m.face([(lx1, 1.48, bz0), (lx1, 1.48, bz1), (lx1, 2.34, tz1), (lx1, 2.34, tz0)], wood, 2, True)
    m.face([(fx - 1.16, 1.54, fz + 0.510), (fx - 0.02, 1.54, fz + 0.510),
            (fx - 0.02, 2.26, fz + 0.745), (fx - 1.16, 2.26, fz + 0.745)], satin, 2, True)
    for x, z in CANDLES:
        m.add(box(0.06, 1.3, 0.06, (150, 130, 80), center=(x, 0.95, z)))
        m.add(box(0.24, 0.05, 0.24, (150, 130, 80), center=(x, 1.62, z)))
        m.add(box(0.05, 0.22, 0.05, (240, 232, 212), center=(x, 1.75, z)))
    for dx in (-0.6, 0.6):
        for i in range(10):
            a = 2 * math.pi * i / 10
            col = (52, 82, 46) if i % 3 else (200, 40, 40)
            m.add(box(0.16, 0.16, 0.08, col,
                      center=(fx + dx + 0.32 * math.cos(a), 0.75 + 0.32 * math.sin(a), fz - 1.75)))
        m.add(box(0.04, 0.6, 0.04, (60, 50, 40), center=(fx + dx, 0.3, fz - 1.72)))
    for row in range(3):                                                            # empty chairs
        for i in range(-3, 4):
            if i == 0:
                continue
            x, z = fx + i * 0.9, fz - 4.6 - row * 1.1
            m.add(box(0.46, 0.06, 0.46, (36, 34, 36), center=(x, 0.46, z)))
            m.add(box(0.46, 0.5, 0.05, (36, 34, 36), center=(x, 0.74, z - 0.21)))
            for lx in (-0.2, 0.2):
                m.add(box(0.04, 0.44, 0.04, (30, 30, 32), center=(x + lx, 0.22, z)))
    return m


def casket_lights():
    """estate_lights plus a warm key over Maru's face in the open casket."""
    fx, fz = FUNERAL
    return estate_lights() + [{"pos": (fx - 0.5, 2.6, fz - 1.6), "color": (255, 214, 170),
                               "intensity": 0.45, "range": 3.0}]


def estate_lights():
    """The local lights the estate shots share: candles, the porch, two drive lamps."""
    fx, fz = FUNERAL
    out = [{"pos": (x, 1.9, z), "color": (255, 196, 120), "intensity": 0.55, "range": 5.0}
           for x, z in CANDLES]
    out.append({"pos": (fx, 4.6, fz + 10.0), "color": (255, 214, 150), "intensity": 0.9, "range": 14.0})
    out += [{"pos": (x, LAMP_H + 0.3, z), "color": (255, 214, 150), "intensity": 0.7, "range": 9.0}
            for x, z in ESTATE_LAMPS[-2:]]
    return out


def lamp_glows(r, t):
    from cutscenes import m6fx3d as _fx  # lazy: numpy stack
    for x, z in ESTATE_LAMPS:
        r.add_sprite((x, LAMP_H + 0.28, z), _fx.glow((255, 214, 150), 0.9, int(t), flicker=0.05,
                                                     seed=int(x * 7 + z)), layer=_fx.FX_LAYER)
    for i, (x, z) in enumerate(CANDLES):
        r.add_sprite((x, 1.9, z), _fx.glow((255, 190, 110), 0.35, int(t), flicker=0.35, seed=i),
                     layer=_fx.FX_LAYER)


# --- shots -------------------------------------------------------------------


def train_x(t, start=30.0, speed=7.0):
    """The last car's rear, well under way: ``start`` m past the crossing."""
    return RX + S.TRAIN_LAST_X + start + speed * min(t, 20.0)


def shot(line, t):
    """(eye, target, fov, grade) for line ``line`` at ``t`` s; grade is
    "night", "dusk" (close on the train), "tv", "funeral" or "title"."""
    if line == 0:                                    # Alex on the radio, the rear step
        x = train_x(t)
        return (x - 5.4, 2.6, CZ - 2.4), (x - 0.3, 2.5, CZ), 44.0, "dusk"
    if line == 1:                                    # the President on state TV
        sx, sz = STUDIO
        return (sx + 0.1 * t, 1.65, sz - 3.4), (sx, 1.55, sz + 1.4), 32.0, "tv"
    if line == 2:                                    # the estate, the closed funeral
        fx, fz = FUNERAL
        return (fx + 1.0, 3.2, fz - 9.0 - 0.35 * t), (fx, 1.8, fz + 6.0), 50.0, "funeral"
    if line == 3:                                    # Maru in the casket
        fx, fz = FUNERAL
        return (fx - 0.3, 2.7, fz - 2.7 - 0.03 * t), (fx, 1.3, fz), 44.0, "funeral"
    if line == 4:                                    # Ucilev made Commander
        sx, sz = STUDIO
        return (sx + 0.6, 1.6, sz - 3.6 + 0.05 * t), (sx + 0.6, 1.5, sz + 1.4), 36.0, "tv"
    if line == 5:                                    # the crossing: the tractor, the train going
        return (RX - 14.0, 3.0, CZ - 9.0), (RX + 20.0, 1.5, CZ + 1.0), 50.0, "night"
    if line == 6:                                    # Ucilev at the border hut
        return ((RX - 7.6 - 0.04 * t, 2.0, CZ - 12.8), (RX + 22.0, 1.4, CZ + 2.0), 46.0, "night")
    if line == 7:                                    # close, on the step
        x = train_x(t, 120.0, 6.0)
        return (x - 3.6, 2.95, CZ - 1.9), (x - 0.3, 2.75, CZ), 34.0, "dusk"
    if line == 8:                                    # the train pulls away from us
        x = train_x(t, 150.0, 6.0)
        return (x - 12.0 - 2.0 * t, 3.4, CZ - 5.0), (x + 12.0, 2.0, CZ), 46.0, "night"
    return (RX + 60.0, 6.0, CZ - 34.0), (RX + 170.0, 2.0, CZ), 40.0, "title"


def _train_at(line, t):
    if line == 0:
        return train_x(t)
    if line == 5:
        return train_x(t, 6.0, 3.0)
    if line == 6:
        return train_x(t, 12.0, 4.0)
    if line == 7:
        return train_x(t, 120.0, 6.0)
    if line == 8:
        return train_x(t, 150.0, 6.0)
    return train_x(t, 180.0, 6.0)


def _cast(r, line, t, tm):
    if line in (1, 4):
        sx, sz = STUDIO
        S.put(r, "studio", studio, (0.0, 0.0, 0.0))
        talk = abs(math.sin(t * 11.0)) * 0.8 if line == 1 and t < 3.6 else 0.0
        _w.actor(r, "president", dict(POSES["stand"], lsh_p=24, lel=30, rsh_p=24, rel=30),
                 (sx, 0.0, sz + 1.4), 180.0 if line == 1 else 196.0, tm, seed=12, amp=0.3,
                 mouth=talk, expression="stern")
        if line == 4:
            _w.actor(r, "ucilev", dict(POSES["stand"]), (sx + 1.3, 0.0, sz + 1.5), 180.0, tm,
                     seed=34, amp=0.15, mouth=0.0)
        return
    if line in (2, 3):
        fx, fz = FUNERAL
        S.put(r, "funeral", funeral, (0.0, 0.0, 0.0))
        pos = (fx - 0.02, 1.24, fz)
        _w.actor(r, "maru", maru_pose(pos, 90.0), pos, 90.0, tm, seed=5, amp=0.0,
                 mouth=0.0, expression="closed", flags=("suit",))
        for i, (dx, dz, yaw) in enumerate(((-1.9, -0.9, 60.0), (1.9, -0.9, 300.0),
                                           (-1.9, 0.9, 120.0), (1.9, 0.9, 240.0))):
            _w.actor(r, ("guard", "officer"), dict(POSES["stand"]), (fx + dx, 0.0, fz + dz), yaw, tm,
                     seed=40 + i, amp=0.08, mouth=0.0)
        return
    tx = _train_at(line, t)
    S.put(r, "train", S.train, (tx, 0.0, CZ), 0.0)
    S.put(r, "tractor", S.tractor, (RX, 0.0, CZ - 0.3), S.road_yaw(CZ))
    S.put(r, "barrier_arm", S.barrier_arm, (RX - 3.0, 0.05, S.BARRIER_Z + 3.0), 210.0)
    _w.actor(r, ("ally", "bodi"), dict(_SEATED, spine=22, head_p=30),
             (RX, 0.62, CZ - 1.05), S.road_yaw(CZ), tm, seed=61, amp=0.0, mouth=0.0)
    from cutscenes import m6fx3d as _fx
    for k in range(4):                                   # the dead engine smokes
        a = ((t * 0.35 + k * 0.25) % 1.0)
        r.add_sprite((RX + 0.3 * a, 2.2 + 2.6 * a, CZ + 0.6 + 0.8 * a),
                     _fx.glow((56, 54, 56), 0.5 + a * 1.2, tm, intensity=0.5 * (1.0 - a)),
                     layer=_fx.FX_LAYER)
    if line in (0, 7, 8):
        key = ("biribel", OUTFIT_GUARD)
        pose = POSES["radio"] if line == 0 else dict(POSES["stand"], head_p=8)
        _w.actor(r, key, dict(pose), (tx - 0.3, 1.26, CZ), 270.0, tm, seed=93, amp=0.25, mouth=0.0)
    if line in (5, 6):
        photo = dict(POSES["stand"], rsh_p=40, rel=70, head_p=4)
        _w.actor(r, "ucilev", photo, (RX - 5.6, 0.0, CZ - 11.0), 64.0, tm, seed=34, amp=0.12,
                 mouth=0.0)


def draw(surface, line, t):
    eye, tgt, fov, grade = shot(line, t)
    r = S.frame(eye, tgt, fov)
    del _w.LAST[:]
    _cast(r, line, t, int(t * 1000.0) + line * 7919)
    _present(r, surface, grade)
    if grade == "tv":
        _tv(surface, t)
    elif line == 0:
        _static(surface, t)
    if grade == "title":
        _title(surface, t)


def _present(r, surface, grade):
    from cutscenes import m6fx3d as _fx  # lazy: numpy stack
    surf = r.surface
    r.flush(surf)
    if grade in ("night", "title"):
        surf.fill(NIGHT, special_flags=pygame.BLEND_MULT)
    elif grade == "dusk":
        surf.fill(DUSK, special_flags=pygame.BLEND_MULT)
    elif grade == "funeral":
        surf.fill((84, 90, 124), special_flags=pygame.BLEND_MULT)
    elif grade == "tv":
        surf.fill(TV_TINT, special_flags=pygame.BLEND_MULT)
    try:
        _fx.grade_cine(surf)
    except Exception:
        pass
    _fx.present_crisp(surf, surface)


def _tv(surface, t):
    lines = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for y in range(0, HEIGHT, 3):
        pygame.draw.line(lines, (0, 0, 0, 70), (0, y), (WIDTH, y))
    surface.blit(lines, (0, 0))
    bug = font_terminal_small.render("TVR 1  -  LIVE", True, (236, 230, 210))
    pygame.draw.rect(surface, (150, 30, 30), (36, 30, bug.get_width() + 16, 24))
    surface.blit(bug, (44, 34))


def _static(surface, t):
    k = int(t * 30.0)
    for i in range(14):
        y = (k * 53 + i * 131) % HEIGHT
        a = 40 + (k * 17 + i * 29) % 60
        band = pygame.Surface((WIDTH, 1 + (i % 3)), pygame.SRCALPHA)
        band.fill((200, 200, 200, a))
        surface.blit(band, (0, y))


def _title(surface, t):
    a = max(0.0, min(1.0, (t - 0.4) / 1.6))
    img = font_title.render("CALL OF ACARISTAN", True, (232, 226, 210))
    img.set_alpha(int(255 * a))
    surface.blit(img, ((WIDTH - img.get_width()) // 2, int(HEIGHT * 0.36)))
