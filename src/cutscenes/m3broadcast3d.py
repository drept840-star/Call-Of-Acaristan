"""Seekable 3D bridge from the loading dock to the state television studio."""
import math
import os

import pygame

from core.config import HEIGHT, SCENE_TOP, WIDTH

SCENES = ("m3_bcast_shutter", "m3_bcast_road", "m3_bcast_mast",
          "m3_bcast_onair", "m3_bcast_channel")
TOP, BOTTOM = SCENE_TOP + 6, HEIGHT - 158
SIZE = (int(WIDTH * 0.64), int((BOTTOM - TOP) * 0.64))
SLAM_MS = 900
WALK_MS = 3200
DOOR_Z = 8.0
MAST = (12.5, 24.0, 24.0)
_cache = {"sets": {}, "rig": None, "route": None, "failed": False, "err": None}


def smooth(t, start, duration):
    u = max(0.0, min(1.0, (t - start) / duration))
    return u * u * (3 - 2 * u)


def mix(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def _dynamic(r, mesh):
    r.add_dynamic(mesh.verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces])


def _beam(a, b, width, color):
    from engine3d import Mesh, box, m_mul, rot_x, rot_y
    dx, dy, dz = (b[i] - a[i] for i in range(3))
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    matrix = m_mul(rot_y(math.degrees(math.atan2(dx, dz))),
                   rot_x(-math.degrees(math.atan2(dy, math.hypot(dx, dz)))))
    return Mesh().add(box(width, width, length, color), m=matrix, t=mix(a, b, 0.5))


def _lettering(text, center, width, color, emissive=False):
    from engine3d import Mesh
    from cutscenes.m5decal import _rects
    from ui.pixfont import PixelFont
    font = PixelFont("R7", 1)
    image = font.render(text, False, color)
    w, h = image.get_size()
    unit = width / max(1, w)
    cx, cy, cz = center
    mesh = Mesh()
    for x0, y0, x1, y1, col in _rects(image, q=1):
        xa, xb = cx + (x0 - w / 2) * unit, cx + (x1 - w / 2) * unit
        ya, yb = cy + (h / 2 - y1) * unit, cy + (h / 2 - y0) * unit
        mesh.face(((xa, ya, cz), (xa, yb, cz), (xb, yb, cz), (xb, ya, cz)),
                  col, 2, False, emissive)
    return mesh


def _mast(r, x, z, height):
    from engine3d import box
    steel = (103, 116, 118)
    for i in range(8):
        y0, y1 = i * height / 8, (i + 1) * height / 8
        a, b = 1.3 * (1 - i / 9), 1.3 * (1 - (i + 1) / 9)
        for side in (-1, 1):
            r.bake(_beam((x + side * a, y0, z), (x + side * b, y1, z), 0.10, steel))
            r.bake(_beam((x + side * a, y0, z + a), (x + side * b, y1, z + b), 0.10, steel))
        r.bake(_beam((x - a, y0, z), (x + b, y1, z), 0.055, steel))
        r.bake(_beam((x + a, y0, z), (x - b, y1, z), 0.055, steel))
        r.bake(box(a * 2, 0.08, a, steel, center=(x, y0, z + a / 2)))
    for y in (height * 0.65, height * 0.79):
        r.bake(box(2.6, 0.1, 0.12, steel, center=(x, y, z)))
        for side in (-1, 1):
            r.bake(box(0.12, 1.4, 0.16, (156, 160, 146), center=(x + side * 1.2, y, z)))
    r.bake(box(0.15, 1.1, 0.15, steel, center=(x, height + 0.45, z)))
    r.bake(box(0.20, 0.22, 0.20, (231, 53, 34), center=(x, height, z), emissive=True))


def _set(r, key):
    from engine3d import box, quad_xz
    from engine3d.textures import tex
    from cutscenes.ps2mat import mesh as textured
    from engine.text import T

    def bake(m):
        r.bake(textured(m))

    if key == "dock":
        bake(quad_xz(-10, -8, 10, 12, 0, (73, 77, 74), seg=1.5))
        for x in (-4.5, 4.5):
            bake(box(3.8, 5.5, 0.6, (91, 98, 92), center=(x, 2.75, 4.3), seg=0.8))
            bake(box(0.18, 4, 0.4, (140, 144, 126), center=(x * 0.60, 2, 3.9)))
        # Full enclosure: outboard wall segments, side returns and a ceiling,
        # so the wide lens never sees past the set into clear colour.
        for x in (-8.2, 8.2):
            bake(box(3.6, 5.5, 0.6, (91, 98, 92), center=(x, 2.75, 4.3), seg=0.8))
        for x in (-10, 10):
            bake(box(0.4, 5.5, 20, (84, 91, 86), center=(x, 2.75, 2), seg=1.2))
            for z in (-6, -3, 0, 3):
                bake(box(0.16, 5.5, 0.5, (100, 107, 99), center=(x * 0.98, 2.75, z)))
            bake(box(0.10, 0.10, 12, (52, 62, 58), center=(x * 0.975, 3.7, -1), seg=1))
        bake(box(20.4, 0.18, 20.6, (60, 66, 62), center=(0, 5.62, 2), seg=2))
        for z in (-5, -2, 1, 4):
            bake(box(20, 0.26, 0.3, (47, 54, 50), center=(0, 5.42, z), seg=2))
        for z in (-3, 0):
            bake(box(0.10, 0.30, 0.44, (42, 50, 46), center=(9.73, 3.1, z)))
            bake(box(0.06, 0.20, 0.32, (236, 207, 146), center=(9.70, 3.1, z), emissive=True))
        bake(box(5.6, 1.6, 0.7, (95, 103, 96), center=(0, 4.7, 4.3), seg=0.8))
        bake(box(5.7, 0.44, 0.65, (39, 49, 48), center=(0, 4.03, 3.8)))
        bake(box(20, 5.5, 0.3, (46, 58, 60), center=(0, 2.75, 9.2), seg=1.5))
        # Bulkhead lamp + conduit on the far wall so the open shutter frames a
        # lit surface, not a flat dark void, during the slam.
        bake(box(8, 0.07, 0.06, (30, 40, 42), center=(0, 3.3, 9.03), seg=1))
        for x in (4.5, 5.0):
            bake(box(0.08, 5.5, 0.08, (36, 46, 48), center=(x, 2.75, 9.0)))
        bake(box(0.5, 0.18, 0.12, (40, 50, 48), center=(2.0, 2.7, 9.02)))
        bake(box(0.38, 0.09, 0.07, (224, 192, 132), center=(2.0, 2.66, 8.97), emissive=True))
        for x in (-3.0, 3.0):
            bake(box(0.18, 0.9, 0.18, (180, 145, 65), center=(x, 0.45, 2.7)))
            for y in (0.25, 0.6):
                bake(box(0.19, 0.13, 0.19, (30, 36, 33), center=(x, y, 2.7)))
        for x, z in ((-4.5, 1), (4.1, 5.6)):
            bake(box(1.1, 0.85, 1.1, (118, 100, 68), center=(x, 0.425, z)))
        for x in (-1.9, 1.9):
            bake(quad_xz(x - 0.06, -6, x + 0.06, 3.7, 0.012, (155, 137, 78)))
        for y in (1.0, 1.17):
            bake(box(2.5, 0.065, 0.08, (77, 91, 90), center=(-4.5, y, 3.92)))
        bake(box(2.6, 0.5, 0.08, (27, 38, 38), center=(0, 4.7, 3.9)))
        r.bake(_lettering(T("m3broadcast.dock_03_sealed"), (0, 4.7, 3.845), 2.3, (194, 187, 151)))
        return

    if key == "road":
        # Wet verge under and beyond the carriageway: the road is grounded,
        # not a ribbon floating in clear colour.
        r.bake(quad_xz(-70, -10, 70, 130, -0.14, tex("pavement", like=(30, 36, 38)), seg=8))
        r.bake(quad_xz(-5.8, -6, 5.8, 115, 0, tex("pavement", like=(49, 54, 58)), seg=4))
        for x in (-6, 6):
            bake(box(0.3, 0.28, 116, (89, 97, 94), center=(x, 0.14, 52), seg=4))
            bake(box(0.12, 0.12, 116, (120, 132, 128), center=(x, 0.8, 52), seg=4))
            r.bake(quad_xz(x - 0.7, -6, x + 0.7, 115, -0.08, (24, 32, 35), seg=4))
            r.bake(quad_xz(x * 0.89 - 0.035, -6, x * 0.89 + 0.035, 115, 0.012,
                          (169, 165, 132), layer=1, seg=4))
        for i in range(15):
            x = -39 + i * 5.5
            h = 4 + (i * 7 % 9)
            bake(box(4, h, 5, (46, 57, 65), center=(x, h / 2, 103 + i % 3 * 3), seg=3))
            for y in range(2, h, 3):
                bake(box(0.6, 0.65, 0.04, (166, 144, 98), center=(x, y, 100.4 + i % 3 * 3), emissive=True))
        # A second, taller skyline row deep in the fog gives the horizon depth.
        for i in range(11):
            x = -50 + i * 10
            h = 9 + (i * 5 % 10)
            bake(box(7, h, 6, (34, 44, 52), center=(x, h / 2 - 0.14, 121 + i % 2 * 4), seg=4))
        _mast(r, 15, 99, 17)
        # A vehicle-neutral passenger view, with the proof lit on the dash.
        bake(box(3.1, 0.42, 0.7, (38, 46, 50), center=(0, 0.75, -0.9), seg=0.6))
        bake(box(0.62, 0.035, 0.42, (170, 151, 111), center=(0.75, 0.98, -0.82)))
        for i in range(3):
            bake(box(0.37, 0.008, 0.012, (100, 75, 56), center=(0.75, 1.003, -0.95 + i * 0.06)))
        bake(box(0.13, 0.009, 0.10, (131, 44, 31), center=(0.94, 1.003, -0.72)))
        return

    if key == "exterior":
        r.bake(quad_xz(-36, -30, 36, 48, 0, tex("pavement", like=(50, 59, 63)), seg=4))
        # Lit apron + walkway: the facade base meets visible ground, not void.
        r.bake(quad_xz(-16, -8, 2, 14, 0.012, tex("pavement", like=(58, 64, 66)), seg=3))
        r.bake(quad_xz(-8.5, 14, 1.5, 18.6, 0.02, tex("concrete", like=(82, 88, 86)), seg=1.5))
        r.bake(quad_xz(-7, -2, -2, 14, 0.018, tex("concrete", like=(74, 80, 78)), seg=2))
        for x in (-7.6, -1.4):
            for z in (2, 6, 10):
                bake(box(0.09, 0.55, 0.09, (60, 70, 66), center=(x, 0.275, z)))
                bake(box(0.11, 0.09, 0.11, (230, 200, 140), center=(x, 0.56, z), emissive=True))
        # Perimeter wall with a gate gap on the walkway; the fence continues it.
        bake(box(15, 1.05, 0.25, (88, 96, 90), center=(-14.5, 0.525, 14), seg=1))
        bake(box(8, 1.05, 0.25, (88, 96, 90), center=(3, 0.525, 14), seg=1))
        for x in (-7, -1):
            bake(box(0.3, 1.5, 0.3, (100, 108, 100), center=(x, 0.75, 14)))
            bake(box(0.16, 0.12, 0.16, (232, 202, 142), center=(x, 1.56, 14), emissive=True))
        bake(box(23, 9.4, 7, (104, 112, 107), center=(-3.5, 4.7, 22), seg=2))
        for y in (0.35, 3.35, 6.35, 9.5):
            bake(box(23.7, 0.22, 7.6, (135, 139, 122), center=(-3.5, y, 22), seg=2))
        for row in range(3):
            for col in range(9):
                x, y = -13.7 + col * 2.55, 1.8 + row * 3
                bake(box(1.5, 1.65, 0.09, (25, 42, 48), center=(x, y, 18.43)))
                if (col + row * 3) % 4 != 2:
                    bake(box(1.28, 1.4, 0.04, (152, 146, 105), center=(x, y, 18.36), emissive=True))
                bake(box(0.07, 1.65, 0.12, (65, 83, 82), center=(x, y, 18.31)))
        bake(box(5.3, 0.3, 3.8, (47, 62, 65), center=(-3.5, 3.25, 17), seg=1))
        bake(box(3.8, 2.7, 0.15, (25, 40, 42), center=(-3.5, 1.35, 18.15)))
        for x in (-4.8, -2.2):
            bake(box(1.0, 2.4, 0.1, (119, 141, 134), center=(x, 1.2, 18.02)))
            bake(box(0.12, 0.6, 0.08, (206, 187, 131), center=(x, 1.2, 17.94)))
        for x in (-5.7, -1.3):
            bake(box(0.12, 3.1, 0.12, (112, 124, 116), center=(x, 1.55, 15.5)))
        bake(box(4.0, 0.17, 0.18, (227, 203, 147), center=(-3.5, 3.04, 15.4), emissive=True))
        _mast(r, MAST[0], MAST[2], MAST[1])
        # Roof plant, cable trays and fence give the tower a real compound.
        for x in (-11, -6, 0):
            bake(box(2.1, 1.1, 2, (78, 93, 90), center=(x, 10.15, 22)))
            for y in (9.9, 10.15, 10.4):
                bake(box(1.7, 0.04, 0.08, (133, 142, 130), center=(x, y, 20.94)))
        for x in range(7, 22, 2):
            bake(box(0.055, 2.1, 0.055, (97, 112, 110), center=(x, 1.05, 14)))
        for y in (0.65, 1.7, 2.1):
            bake(box(14, 0.035, 0.04, (91, 108, 107), center=(14, y, 14)))
        for z in range(0, 16, 2):
            bake(box(0.32, 0.08, 1.85, (43, 57, 58), center=(3.2, 0.04, z)))
        # Stepped wings and a fogged skyline: the wing sits in a city, not a void.
        bake(box(8, 5.5, 6, (96, 104, 100), center=(-19, 2.75, 22.5), seg=1.5))
        bake(box(8.4, 0.25, 6.4, (130, 136, 120), center=(-19, 5.6, 22.5), seg=1.5))
        for x in (-21.5, -17.5):
            for y in (1.9, 4.0):
                bake(box(1.1, 1.3, 0.08, (25, 42, 48), center=(x, y, 19.46)))
                if not (x == -17.5 and y == 4.0):
                    bake(box(0.9, 1.05, 0.04, (148, 142, 102), center=(x, y, 19.42), emissive=True))
        bake(box(7, 4, 5, (90, 98, 94), center=(17.5, 2, 23), seg=1.5))
        bake(box(7.4, 0.22, 5.4, (124, 130, 116), center=(17.5, 4.1, 23), seg=1.5))
        for x in (15.8, 19.2):
            bake(box(1.0, 1.2, 0.08, (25, 42, 48), center=(x, 2.0, 20.46)))
            bake(box(0.8, 0.95, 0.04, (148, 142, 102), center=(x, 2.0, 20.42), emissive=True))
        for i in range(9):
            x = -32 + i * 8
            h = 5 + (i * 7 % 9)
            bake(box(6, h, 5, (34, 44, 52), center=(x, h / 2, 40 + i % 3 * 2), seg=3))
        bake(box(0.08, 2.6, 0.08, (90, 102, 100), center=(5, 10.9, 22)))
        for y in (11.6, 12.0):
            bake(box(1.2, 0.05, 0.05, (90, 102, 100), center=(5, y, 22)))
        return

    # Studio corridor: acoustic panels, recessed doors and practical red tally.
    bake(quad_xz(-3.2, -6, 3.2, 9.3, 0, (66, 70, 66), seg=0.8))
    # Ceiling slab sits on the beam tops; the corridor is capped, not open sky.
    bake(box(6.7, 0.14, 16.6, (62, 68, 62), center=(0, 3.80, 1.5), seg=0.8))
    for z in (-4.5, -1.5, 1.5, 4.5):
        bake(box(6.4, 0.03, 0.06, (48, 54, 49), center=(0, 3.72, z)))
    for x in (-3.2, 3.2):
        bake(box(0.22, 3.8, 16, (102, 108, 94), center=(x, 1.9, 1.5), seg=0.8))
        bake(box(0.08, 0.18, 15, (45, 61, 57), center=(x * 0.96, 0.18, 1), seg=1))
        bake(box(0.10, 0.12, 15, (134, 139, 119), center=(x * 0.96, 1.0, 1), seg=1))
        for z in (-2, 0, 2, 4, 6):
            bake(box(0.09, 1.4, 1.45, (38, 57, 57), center=(x * 0.96, 2.05, z)))
            for y in (1.6, 1.9, 2.2, 2.5):
                bake(box(0.12, 0.025, 1.24, (90, 108, 97), center=(x * 0.94, y, z)))
    for z in (-3, 0, 3, 6):
        bake(box(6.3, 0.16, 0.18, (70, 87, 79), center=(0, 3.65, z), seg=0.8))
        bake(box(1.6, 0.07, 0.22, (32, 46, 43), center=(0, 3.52, z)))
        bake(box(1.4, 0.025, 0.15, (189, 213, 190), center=(0, 3.47, z), emissive=True))
    for x in (-2.4, 2.4):
        bake(box(1.6, 3.8, 0.3, (110, 116, 98), center=(x, 1.9, DOOR_Z), seg=0.7))
    bake(box(3.2, 0.8, 0.3, (107, 115, 96), center=(0, 3.4, DOOR_Z), seg=0.7))
    for x in (-0.75, 0.75):
        bake(box(1.46, 2.85, 0.16, (61, 76, 69), center=(x, 1.44, 8.04), seg=0.7))
        bake(box(0.92, 0.36, 0.1, (152, 155, 123), center=(x, 1.08, 7.92)))
        bake(box(0.72, 0.47, 0.06, (30, 51, 54), center=(x, 2.08, 7.92)))
    for x in (-1.58, 1.58):
        bake(box(0.14, 3.05, 0.35, (147, 150, 125), center=(x, 1.52, 7.9)))
    bake(box(3.3, 0.15, 0.36, (147, 150, 125), center=(0, 3.0, 7.9)))
    bake(box(1.95, 0.42, 0.20, (39, 23, 23), center=(0, 3.37, 7.78)))
    r.bake(_lettering(T("m3broadcast.on_air"), (0, 3.37, 7.665), 1.6, (247, 82, 52), True))
    bake(box(0.025, 2.84, 0.03, (211, 170, 100), center=(0, 1.43, 7.94), emissive=True))
    bake(box(2.9, 0.025, 0.05, (216, 176, 101), center=(0, 0.02, 7.90), emissive=True))
    # The radio's lost-link lamp is beside the real door, in the final lens.
    bake(box(0.38, 0.64, 0.15, (31, 47, 45), center=(-1.95, 1.42, 7.76)))
    for y in (1.25, 1.34, 1.43, 1.52):
        bake(box(0.26, 0.025, 0.035, (135, 149, 129), center=(-1.95, y, 7.67)))
    bake(box(0.06, 0.06, 0.03, (204, 51, 33), center=(-1.95, 1.65, 7.66), emissive=True))
    for x in (-2.85, -2.73, -2.61):
        bake(box(0.04, 0.04, 13, (37, 47, 44), center=(x, 0.03, 1), seg=1))


def renderer(key):
    if key not in _cache["sets"]:
        from engine3d import Light, Renderer
        outside = key in ("road", "exterior")
        r = Renderer(*SIZE, fog=(28, 38, 46) if outside else (16, 27, 34),
                     fog_start=28 if outside else 12,
                     fog_end=135 if outside else 42)
        r.light = Light(direction=(-0.5, 0.8, -0.6), ambient=0.34, diffuse=0.57,
                        sky=0.08, tint=(0.91, 0.99, 1.0))
        r.light_albedo = True
        _set(r, key)
        _cache["sets"][key] = r, pygame.Surface(SIZE)
    return _cache["sets"][key]


def rig():
    if _cache["rig"] is None:
        from cutscenes.cast3d import humanoid3d
        _cache["rig"] = humanoid3d("biribel", rifle="os12", jacket=(88, 64, 46),
            pants=(88, 64, 46), vest=None, pouches=False, accent=None,
            armband=(88, 64, 46), belt=None, buckle=None, cuff=(56, 42, 32),
            lapel=None, shirt=None)
        _cache["rig"].set_expression("stern", 0)
    return _cache["rig"]


def corridor_actor(t):
    from cutscenes import m6world3d as motion  # lazy: planted-foot animation
    from engine3d.hold import hold_weapon
    if _cache["route"] is None:
        route = motion.path(((-0.85, 0.2), (-0.85, 6.25)))
        _cache["route"] = route, motion.walk_stride(route.length, nominal=0.78)
    route, stride = _cache["route"]
    a, b = motion.walk_span(route.length, stride)
    p, pos, yaw = motion.walk(rig(), route, a + (b - a) * motion.travel(t, 0, WALK_MS), stride)
    p = motion.life_pose(p, t, amp=0.30, seed=4)
    p["head_y"] = -9 * smooth(t, WALK_MS - 300, 500)
    p = hold_weapon(rig(), p, pos, yaw, "os12", "carry")
    return p, pos, yaw


def shutter_bottom(t):
    return 0.08 + 2.9 * (1 - smooth(t, 0, SLAM_MS))


def _shutter(r, t):
    from engine3d import box
    from cutscenes import m6fx3d as fx
    bottom = shutter_bottom(t)
    for i in range(23):
        y = bottom + 0.09 + i * 0.17
        if y < 3.85:
            _dynamic(r, box(5.15, min(0.15, 3.92 - y), 0.16, (99, 109, 101),
                            center=(0, y, 3.84)))
    _dynamic(r, box(5.25, 0.14, 0.23, (147, 127, 64), center=(0, bottom, 3.78)))
    for x in (-2, -1, 0, 1, 2):
        _dynamic(r, box(0.36, 0.145, 0.025, (35, 43, 39), center=(x, bottom, 3.65)))
    swing = 0.24 * math.exp(-t / 3200) * math.sin(t * 0.005)
    _dynamic(r, _beam((0, 5.6, 2.2), (swing, 3.5, 2.2), 0.025, (30, 41, 39)))
    _dynamic(r, box(0.40, 0.16, 0.25, (236, 207, 146), center=(swing, 3.42, 2.2), emissive=True))
    r.add_sprite((swing, 3.35, 2.15), fx.glow((241, 189, 102), 0.30, t=t, intensity=0.55), layer=2)
    if SLAM_MS <= t < SLAM_MS + 1700:
        for i in range(5):
            r.add_sprite((-2 + i, 0.12, 3.57),
                fx.haze((132, 128, 109), 0.45, t=t - SLAM_MS, seed=i,
                        intensity=0.16 * (1 - (t - SLAM_MS) / 1700)), layer=2)


def _road(r, t):
    from engine3d import box, quad_xz
    from cutscenes import m6fx3d as fx
    # Ring-road blocks stream past at the same 16 m/s as the lamps, so the
    # verges read as a city rather than empty ground. Wrap happens behind
    # the camera / deep in the fog, never on screen.
    for i in range(7):
        z = -8 + (i * 18 - t * 0.016) % 126
        for side in (-1, 1):
            x = side * (10.5 + (i * 3 % 4) * 2.5)
            h = 3 + (i * 7 + side * 2) % 8
            w = 4.5 + i % 3
            _dynamic(r, box(w, h, 5.5, (40 + i * 2, 50 + i * 2, 57 + i * 2),
                            center=(x, h / 2 - 0.14, z), skip=("bottom",)))
            for k in range(2):
                if (i + k) % 3:
                    _dynamic(r, box(0.06, 0.6, 0.8, (150, 132, 92),
                                    center=(x - side * (w / 2 + 0.02), 1.6 + k * 1.8,
                                            z - 1 + k * 2), emissive=True,
                                    skip=("front", "back", "top", "bottom",
                                          "right" if side > 0 else "left")))
    for i in range(15):
        z = -6 + (i * 8 - t * 0.016) % 120
        _dynamic(r, quad_xz(-0.055, z, 0.055, z + 3, 0.015, (166, 159, 117), layer=1))
    for i in range(7):
        z = -5 + (i * 18 - t * 0.016) % 126
        for side in (-1, 1):
            x = side * 6.6
            _dynamic(r, box(0.10, 6.4, 0.10, (68, 85, 86), center=(x, 3.2, z)))
            _dynamic(r, box(1.8, 0.10, 0.13, (89, 104, 100), center=(x - side * 0.85, 6.4, z)))
            _dynamic(r, box(0.54, 0.07, 0.23, (234, 200, 128), center=(x - side * 1.5, 6.34, z), emissive=True))
            if 0 < z < 55:
                r.add_sprite((x - side * 1.5, 6.28, z), fx.glow((237, 188, 102), 0.25,
                             t=t, intensity=0.5), layer=2)
                for j in range(4):
                    _dynamic(r, quad_xz(x - side * 1.8 - 0.24, z - j * 0.9,
                        x - side * 1.8 + 0.24, z - j * 0.9 + 0.25, 0.018,
                        (70 - j * 9, 65 - j * 8, 45 - j * 5), layer=1, emissive=True))
    r.add_sprite((15, 17, 99), fx.beacon((240, 54, 34), t=t, radius_m=0.3), layer=2)
    fx.rain3d(r, t, seed=26, n_near=28, n_far=55, splashes=0, layer=2)


def camera(scene, t):
    if scene == SCENES[0]:
        u = smooth(t, 0, 1600)
        return mix((-4.5, 2.3, -6.0), (-3.8, 2.15, -5.0), u), (0, 2.15, 4), 54
    if scene == SCENES[1]:
        return (1.35, 1.58, -2.9), (0.3, 1.45, 43), 62
    if scene == SCENES[2]:
        u = smooth(t, 0, 4800)
        return mix((-20, 5.2, -24), (-17, 5.8, -20), u), (-1, 7.4, 21), 55
    if scene == SCENES[3]:
        u = smooth(t, 0, WALK_MS)
        return mix((1.6, 2.05, -6), (1.6, 1.95, -1.5), u), mix((-0.4, 1.3, 4.5), (-0.2, 1.4, 7.1), u), 61
    u = smooth(t, 0, 2400)
    return mix((1.5, 1.85, 6.75), (1.15, 1.82, 6.95), u), (-0.8, 1.5, 6.25), 47


def _draw(scene, surface, t):
    from cutscenes import m6fx3d as fx
    key = ("dock", "road", "exterior", "corridor", "corridor")[SCENES.index(scene)]
    r, buf = renderer(key)
    eye, target, fov = camera(scene, t)
    shake = fx.shake(t, SLAM_MS, 400, 0.018) if key == "dock" else None
    fx.set_cam(r, t, eye, target, fov, hh=0.008 if key == "road" else 0, shk=shake)
    if key == "dock":
        lights = [{"pos": (0, 3.3, 2.2), "color": (239, 181, 100), "intensity": 1.5, "range": 9},
                  {"pos": (0, 2.4, 7), "color": (131, 179, 202), "intensity": 1.0, "range": 7}]
    elif key == "road":
        lights = [{"pos": (1.0, 1.3, -1), "color": (179, 195, 178), "intensity": 1.1, "range": 9}]
    elif key == "exterior":
        lights = [{"pos": (-3.5, 3.0, 15.4), "color": (236, 197, 130), "intensity": 1.6, "range": 12},
                  {"pos": (10, 7, 17), "color": (138, 183, 202), "intensity": 1.1, "range": 18}]
    else:
        lights = [{"pos": (0, 3.2, z), "color": (164, 200, 182), "intensity": 1.1, "range": 5} for z in (0, 3)]
        lights += [{"pos": (0, 3.15, 7.5), "color": (240, 92, 51), "intensity": 1.25, "range": 5},
                   {"pos": (1.5, 2.5, 6), "color": (197, 212, 168), "intensity": 1.25, "range": 5}]
    r.set_lights(lights)
    if key in ("road", "exterior"):
        fx.night_sky(r, buf, t, (5, 12, 22), (32, 43, 49), stars=0, clouds=5,
                     sodium=(92, 72, 50), seed=3)
    else:
        buf.fill((12, 22, 26))
    r.begin()
    r.add_static()
    if key == "dock":
        _shutter(r, t)
    elif key == "road":
        _road(r, t)
    elif key == "exterior":
        r.add_sprite(MAST, fx.beacon((244, 57, 34), t=t, radius_m=0.35), layer=2)
        fx.rain3d(r, t, seed=41, n_near=25, n_far=55, splashes=0, layer=2)
    else:
        # The second line is a new lens on the settled pose, never a second walk.
        actor_t = t if scene == SCENES[3] else WALK_MS + 600 + t
        p, pos, yaw = corridor_actor(actor_t)
        r.add_humanoid(rig(), p, pos, yaw, rifle_on=True)
        r.add_sprite((0, 3.37, 7.63), fx.glow((238, 66, 42), 0.28, t=t,
                     pulse=0.06, intensity=0.35), layer=2)
    r.flush(buf)
    fx.grade_cine(buf)
    surface.fill((5, 9, 12))
    fx.present_crisp(buf, surface.subsurface((0, TOP, WIDTH, BOTTOM - TOP)))


def draw(scene, surface, t):
    if scene not in SCENES or os.environ.get("ACARISTAN_CUTSCENE3D", "1").strip() == "0":
        return False
    if _cache["failed"]:
        return False
    try:
        _draw(scene, surface, max(0.0, float(t)))
        return True
    except Exception as exc:
        _cache["failed"], _cache["err"] = True, exc
        return False
