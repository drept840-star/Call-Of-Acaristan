"""Mission 8 Duty - Architectural doors and detailed furniture for Retardovici's estate."""
import math

import pygame

from engine.anim import draw_character
from cutscenes import m7world3d as W7
from engine3d import Mesh, box
from engine3d.core import rot_x, rot_y
from engine3d.textures import tex

_CACHE = {}

GOLD = (212, 176, 86)
BRASS = (196, 158, 72)
DARK_IRON = (28, 30, 34)


def _wood(rgb=(78, 44, 28)):
    return W7._t("plank", rgb)


def study_door_angles(open_u):
    """Asymmetric hinge angles (left_deg, right_deg) for the kicked-in study doors."""
    if open_u <= 0.0:
        return (0.0, 0.0)
    if open_u >= 1.0:
        return (-94.0, 106.0)
    if open_u < 0.46:
        q = open_u / 0.46
        e = 1.0 - (1.0 - q) ** 2.6
        return (-104.0 * e, 118.0 * e)
    q = (open_u - 0.46) / 0.54
    wob = math.cos(q * math.pi * 1.5) * (1.0 - q)
    return (-94.0 - 10.0 * wob, 106.0 + 12.0 * wob)


def study_door_surround(ff, rooms_z, wall):
    """Moulded mahogany & gilt casing around the first-floor study doorway."""
    key = ("study_surround", round(ff, 3), round(rooms_z, 3), round(wall, 3))
    got = _CACHE.get(key)
    if got is not None:
        return got
    m = Mesh()
    mahog = _wood((66, 36, 24))
    dark = _wood((48, 26, 18))
    for s in (-1, 1):
        m.add(box(0.05, 2.78, wall + 0.04, mahog, center=(s * 1.175, ff + 1.39, rooms_z)))
    m.add(box(2.40, 0.06, wall + 0.04, mahog, center=(0.0, ff + 2.77, rooms_z)))
    m.add(box(2.36, 0.016, wall + 0.04, BRASS, center=(0.0, ff + 0.016, rooms_z)))
    for face in (-1, 1):
        fz = rooms_z + face * (wall * 0.5 + 0.035)
        for s in (-1, 1):
            m.add(box(0.20, 2.86, 0.07, mahog, center=(s * 1.26, ff + 1.43, fz)))
            m.add(box(0.24, 0.14, 0.09, dark, center=(s * 1.26, ff + 0.07, fz)))
            m.add(box(0.04, 2.52, 0.02, GOLD, center=(s * 1.26, ff + 1.43, fz + face * 0.038)))
        m.add(box(2.74, 0.20, 0.09, mahog, center=(0.0, ff + 2.89, fz)))
        m.add(box(2.86, 0.10, 0.12, dark, center=(0.0, ff + 3.03, fz + face * 0.01)))
        m.add(box(2.60, 0.045, 0.02, GOLD, center=(0.0, ff + 2.89, fz + face * 0.048)))
    got = _CACHE[key] = m
    return got


def study_door_leaf(side):
    """Single presidential mahogany leaf built in hinge space (side: -1 left, +1 right)."""
    key = ("study_leaf", int(side))
    got = _CACHE.get(key)
    if got is not None:
        return got
    m = Mesh()
    w = 1.150
    h = 2.735
    d = 0.088
    cx = -side * (w * 0.5)
    inner_dir = -side
    mahog = _wood((78, 42, 26))
    panel_col = _wood((62, 32, 20))
    trim_col = _wood((96, 54, 34))

    m.add(box(w, h, d - 0.024, panel_col, center=(cx, h * 0.5, 0.0)))
    m.add(box(0.14, h, d, mahog, center=(inner_dir * 0.07, h * 0.5, 0.0)))
    m.add(box(0.14, h, d, mahog, center=(inner_dir * (w - 0.07), h * 0.5, 0.0)))
    m.add(box(w - 0.24, 0.28, d, mahog, center=(cx, 0.14, 0.0)))
    m.add(box(w - 0.24, 0.20, d, mahog, center=(cx, 1.05, 0.0)))
    m.add(box(w - 0.24, 0.20, d, mahog, center=(cx, h - 0.10, 0.0)))

    pw = w - 0.36
    for y0, y1 in ((0.32, 0.92), (1.19, 2.50)):
        py = (y0 + y1) * 0.5
        ph = y1 - y0
        for fz in (-1, 1):
            m.add(box(pw, ph, 0.016, trim_col, center=(cx, py, fz * (d * 0.5 - 0.008))))
            m.add(box(pw - 0.08, ph - 0.08, 0.014, mahog, center=(cx, py, fz * (d * 0.5 + 0.002))))
            m.add(box(pw - 0.04, 0.018, 0.008, GOLD, center=(cx, y1 - 0.02, fz * (d * 0.5 + 0.004))))
            m.add(box(pw - 0.04, 0.018, 0.008, GOLD, center=(cx, y0 + 0.02, fz * (d * 0.5 + 0.004))))

    m.add(box(w - 0.08, 0.18, d + 0.010, BRASS, center=(cx, 0.10, 0.0)))
    for hy in (0.36, 1.37, 2.38):
        m.add(box(0.036, 0.14, 0.036, BRASS, center=(0.0, hy, 0.0)))

    hx = inner_dir * (w - 0.11)
    for fz in (-1, 1):
        m.add(box(0.068, 0.24, 0.014, BRASS, center=(hx, 1.05, fz * (d * 0.5 + 0.007))))
        m.add(box(0.024, 0.028, 0.038, BRASS, center=(hx, 1.08, fz * (d * 0.5 + 0.026))))
        m.add(box(0.13, 0.024, 0.022, GOLD, center=(hx - inner_dir * 0.048, 1.08, fz * (d * 0.5 + 0.044))))
        m.add(box(0.018, 0.032, 0.008, (18, 16, 16), center=(hx, 0.99, fz * (d * 0.5 + 0.015))))

    if side > 0:
        m.add(box(0.042, h - 0.02, d + 0.018, trim_col, center=(-w + 0.005, h * 0.5, 0.0)))
        m.add(box(0.018, h - 0.04, 0.010, GOLD, center=(-w + 0.005, h * 0.5, -(d * 0.5 + 0.010))))

    got = _CACHE[key] = m
    return got


def front_doors_mesh(front_open, gf):
    """Grand walnut double doors with frosted amber transoms and forged hardware."""
    key = ("front_doors", bool(front_open), round(gf, 3))
    got = _CACHE.get(key)
    if got is not None:
        return got
    m = Mesh()
    walnut = _wood((58, 36, 24))
    inset = _wood((44, 26, 18))
    glass = (224, 186, 122)
    w, h, d = 1.175, 3.38, 0.11
    for side in (-1, 1):
        leaf = Mesh()
        cx = -side * (w * 0.5)
        inner_dir = -side
        leaf.add(box(w, h, d - 0.02, inset, center=(cx, h * 0.5, 0.0)))
        leaf.add(box(0.16, h, d, walnut, center=(inner_dir * 0.08, h * 0.5, 0.0)))
        leaf.add(box(0.16, h, d, walnut, center=(inner_dir * (w - 0.08), h * 0.5, 0.0)))
        for ry, rh in ((0.16, 0.32), (1.10, 0.20), (1.92, 0.18), (h - 0.14, 0.28)):
            leaf.add(box(w - 0.26, rh, d, walnut, center=(cx, ry, 0.0)))
        pw = w - 0.40
        for py, ph in ((0.64, 0.58), (1.51, 0.50)):
            for fz in (-1, 1):
                leaf.add(box(pw, ph, 0.02, walnut, center=(cx, py, fz * (d * 0.5 + 0.002))))
                leaf.add(box(pw + 0.04, 0.02, 0.01, BRASS, center=(cx, py + ph * 0.5, fz * (d * 0.5 + 0.004))))
        leaf.add(box(pw, 0.98, 0.03, glass, center=(cx, 2.54, 0.0), emissive=True))
        leaf.add(box(0.03, 0.98, d + 0.01, DARK_IRON, center=(cx, 2.54, 0.0)))
        leaf.add(box(pw, 0.03, d + 0.01, DARK_IRON, center=(cx, 2.54, 0.0)))
        for hy in (0.48, 1.56, 2.86):
            leaf.add(box(0.42, 0.055, d + 0.016, DARK_IRON, center=(inner_dir * 0.21, hy, 0.0)))
        px = inner_dir * (w - 0.14)
        for fz in (-1, 1):
            leaf.add(box(0.07, 0.26, 0.016, BRASS, center=(px, 1.24, fz * (d * 0.5 + 0.008))))
            leaf.add(box(0.09, 0.09, 0.024, GOLD, center=(px, 1.22, fz * (d * 0.5 + 0.026))))
        ang = -88.0 * side if front_open else 0.0
        m.add(leaf, rot_y(ang), (side * 1.18, gf, 0.25))
    got = _CACHE[key] = m
    return got


def terrace_doors_mesh(terrace_open, ff, hz, wall):
    """Tall paned French double doors leading from the study onto the helipad terrace."""
    key = ("terrace_doors", bool(terrace_open), round(ff, 3), round(hz, 3))
    got = _CACHE.get(key)
    if got is not None:
        return got
    m = Mesh()
    frame = (214, 208, 196)
    glass = (52, 74, 114)
    w, h, d = 1.45, 2.58, 0.08
    for side in (-1, 1):
        leaf = Mesh()
        cx = -side * (w * 0.5)
        inner_dir = -side
        leaf.add(box(w - 0.12, h - 0.20, 0.024, glass, center=(cx, h * 0.5 + 0.05, 0.0), emissive=True))
        leaf.add(box(0.11, h, d, frame, center=(inner_dir * 0.055, h * 0.5, 0.0)))
        leaf.add(box(0.11, h, d, frame, center=(inner_dir * (w - 0.055), h * 0.5, 0.0)))
        leaf.add(box(w, 0.24, d, frame, center=(cx, 0.12, 0.0)))
        leaf.add(box(w, 0.12, d, frame, center=(cx, h - 0.06, 0.0)))
        leaf.add(box(0.04, h - 0.24, d * 0.72, frame, center=(cx, h * 0.5 + 0.05, 0.0)))
        for my in (0.72, 1.26, 1.80, 2.28):
            leaf.add(box(w - 0.12, 0.04, d * 0.72, frame, center=(cx, my, 0.0)))
        hx = inner_dir * (w - 0.08)
        for fz in (-1, 1):
            leaf.add(box(0.045, 0.18, 0.012, BRASS, center=(hx, 1.04, fz * (d * 0.5 + 0.006))))
            leaf.add(box(0.11, 0.022, 0.02, GOLD, center=(hx - inner_dir * 0.04, 1.06, fz * (d * 0.5 + 0.024))))
        ang = 86.0 * side if terrace_open else 0.0
        m.add(leaf, rot_y(ang), (side * 1.46, ff, hz - wall * 0.35))
    got = _CACHE[key] = m
    return got


def interior_doorway_trim(y0, z_mid, wall, x_center, width, height=2.8, ajar_dir=0):
    """Doorway jamb casing, lintel trim, brass threshold, and optional wide-open door."""
    m = Mesh()
    mahog = _wood((66, 38, 26))
    hw = width * 0.5
    for s in (-1, 1):
        m.add(box(0.045, height, wall + 0.04, mahog, center=(x_center + s * (hw - 0.02), y0 + height * 0.5, z_mid)))
        for face in (-1, 1):
            m.add(box(0.12, height + 0.06, 0.05, mahog,
                      center=(x_center + s * (hw + 0.04), y0 + height * 0.5, z_mid + face * (wall * 0.5 + 0.025))))
    m.add(box(width + 0.24, 0.14, wall + 0.08, mahog, center=(x_center, y0 + height - 0.04, z_mid)))
    m.add(box(width - 0.04, 0.012, wall + 0.04, BRASS, center=(x_center, y0 + 0.012, z_mid)))
    if ajar_dir:
        dw = min(1.28, width * 0.72)
        hinge_x = x_center + ajar_dir * (hw - 0.03)
        leaf = Mesh()
        leaf.add(box(dw, height - 0.06, 0.07, _wood((72, 42, 28)),
                     center=(ajar_dir * dw * 0.5, (height - 0.06) * 0.5, 0.0)))
        for py, ph in ((0.55, 0.65), (1.75, 0.85)):
            leaf.add(box(dw - 0.28, ph, 0.084, _wood((88, 52, 34)), center=(ajar_dir * dw * 0.5, py, 0.0)))
        leaf.add(box(0.05, 0.20, 0.11, BRASS, center=(ajar_dir * (dw - 0.10), 1.04, 0.0)))
        m.add(leaf, rot_y(-12.0 * ajar_dir), (hinge_x, y0 + 0.02, z_mid + wall * 0.5 + 0.08))
    return m


# --- furniture -------------------------------------------------------------------

def dining_chair(armrests=False):
    """Carved mahogany dining chair with 4 legs, stretcher rails & crimson cushion (+Z forward)."""
    key = ("dining_chair", bool(armrests))
    got = _CACHE.get(key)
    if got is not None:
        return got
    m = Mesh()
    wood = _wood((72, 38, 24))
    velvet = (126, 26, 32)
    trim = (168, 134, 62)
    for sx in (-0.21, 0.21):
        m.add(box(0.046, 0.45, 0.046, wood, center=(sx, 0.225, 0.20)))
        m.add(box(0.048, 0.05, 0.048, BRASS, center=(sx, 0.025, 0.20)))
        m.add(box(0.048, 0.46, 0.048, wood, center=(sx, 0.23, -0.20)))
        m.add(box(0.044, 0.58, 0.046, wood), rot_x(-6.0), (sx, 0.74, -0.23))
    m.add(box(0.38, 0.026, 0.026, wood, center=(0.0, 0.14, 0.0)))
    for sx in (-0.21, 0.21):
        m.add(box(0.028, 0.028, 0.36, wood, center=(sx, 0.14, 0.0)))
        m.add(box(0.032, 0.06, 0.40, wood, center=(sx, 0.42, 0.0)))
    m.add(box(0.42, 0.06, 0.032, wood, center=(0.0, 0.42, 0.20)))
    m.add(box(0.42, 0.06, 0.032, wood, center=(0.0, 0.42, -0.20)))
    m.add(box(0.46, 0.055, 0.45, velvet, center=(0.0, 0.478, 0.01)))
    m.add(box(0.47, 0.016, 0.46, (94, 18, 22), center=(0.0, 0.454, 0.01)))
    back = Mesh()
    back.add(box(0.46, 0.075, 0.042, wood, center=(0.0, 0.54, 0.0)))
    back.add(box(0.24, 0.04, 0.046, trim, center=(0.0, 0.58, 0.0)))
    back.add(box(0.38, 0.036, 0.034, wood, center=(0.0, 0.13, 0.0)))
    for bx in (-0.12, 0.12):
        back.add(box(0.028, 0.36, 0.026, wood, center=(bx, 0.33, 0.0)))
    back.add(box(0.18, 0.28, 0.044, velvet, center=(0.0, 0.34, 0.01)))
    m.add(back, rot_x(-6.0), (0.0, 0.46, -0.20))
    if armrests:
        for sx in (-0.23, 0.23):
            m.add(box(0.038, 0.20, 0.038, wood, center=(sx, 0.58, 0.15)))
            m.add(box(0.052, 0.036, 0.40, wood, center=(sx, 0.68, -0.02)))
            m.add(box(0.056, 0.022, 0.22, velvet, center=(sx, 0.70, 0.0)))
    got = _CACHE[key] = m
    return got


def _candelabra():
    m = Mesh()
    m.add(box(0.18, 0.035, 0.18, BRASS, center=(0.0, 0.018, 0.0)))
    m.add(box(0.05, 0.42, 0.05, GOLD, center=(0.0, 0.24, 0.0)))
    m.add(box(0.42, 0.03, 0.03, GOLD, center=(0.0, 0.38, 0.0)))
    m.add(box(0.03, 0.03, 0.42, GOLD, center=(0.0, 0.38, 0.0)))
    for cx, cz, ch in ((0.0, 0.0, 0.18), (-0.19, 0.0, 0.14), (0.19, 0.0, 0.14),
                       (0.0, -0.19, 0.14), (0.0, 0.19, 0.14)):
        base_y = 0.45 if (cx == 0.0 and cz == 0.0) else 0.40
        m.add(box(0.06, 0.02, 0.06, BRASS, center=(cx, base_y, cz)))
        m.add(box(0.032, ch, 0.032, (238, 232, 212), center=(cx, base_y + ch * 0.5, cz)))
        m.add(box(0.02, 0.04, 0.02, (255, 224, 146), center=(cx, base_y + ch + 0.025, cz), emissive=True))
    return m


def banquet_table(pig_mesh=None):
    """6-metre mahogany banquet table with turned legs, runner, place settings & candelabras."""
    key = ("banquet_table", id(pig_mesh))
    got = _CACHE.get(key)
    if got is not None:
        return got
    m = Mesh()
    mahog = _wood((76, 42, 26))
    dark = _wood((52, 28, 18))
    cloth = (232, 228, 218)
    plate = (238, 236, 230)
    silver = (196, 202, 208)
    wine = (96, 18, 26)

    m.add(box(1.84, 0.07, 6.04, mahog, center=(0.0, 0.825, 0.0)))
    m.add(box(1.68, 0.11, 5.84, dark, center=(0.0, 0.735, 0.0)))
    for pz in (-2.2, 0.0, 2.2):
        for px in (-0.64, 0.64):
            m.add(box(0.14, 0.68, 0.14, mahog, center=(px, 0.36, pz)))
            m.add(box(0.20, 0.08, 0.20, dark, center=(px, 0.04, pz)))
        m.add(box(1.28, 0.06, 0.08, dark, center=(0.0, 0.18, pz)))
    m.add(box(0.10, 0.07, 4.5, dark, center=(0.0, 0.18, 0.0)))

    m.add(box(0.76, 0.014, 6.08, cloth, center=(0.0, 0.865, 0.0)))
    m.add(box(0.80, 0.008, 6.06, GOLD, center=(0.0, 0.860, 0.0)))
    for sz in (-3.03, 3.03):
        m.add(box(0.76, 0.24, 0.016, cloth, center=(0.0, 0.74, sz)))
        m.add(box(0.76, 0.03, 0.018, GOLD, center=(0.0, 0.62, sz)))

    m.add(box(0.72, 0.025, 1.04, silver, center=(0.0, 0.878, 0.0)))
    if pig_mesh is not None:
        m.add(pig_mesh, rot_y(90.0), (0.0, 0.89, 0.0))

    cand = _candelabra()
    for cz in (-1.55, 1.55):
        m.add(cand, t=(0.0, 0.87, cz))

    def _setting(sx, sz, s_in):
        m.add(box(0.28, 0.014, 0.28, GOLD, center=(sx, 0.867, sz)))
        m.add(box(0.23, 0.016, 0.23, plate, center=(sx, 0.876, sz)))
        m.add(box(0.02, 0.01, 0.16, silver, center=(sx - 0.17, 0.866, sz)))
        m.add(box(0.02, 0.01, 0.16, silver, center=(sx + 0.17, 0.866, sz)))
        m.add(box(0.08, 0.018, 0.13, (124, 24, 30), center=(sx, 0.888, sz)))
        gx = sx + s_in * 0.18
        gz = sz + 0.15
        m.add(box(0.05, 0.01, 0.05, silver, center=(gx, 0.866, gz)))
        m.add(box(0.016, 0.08, 0.016, silver, center=(gx, 0.905, gz)))
        m.add(box(0.055, 0.06, 0.055, wine, center=(gx, 0.96, gz)))

    for dz in (-2.2, -1.1, 1.1, 2.2):
        _setting(-0.62, dz, 1.0)
        _setting(0.62, dz, -1.0)
    _setting(0.0, -2.65, 0.0)
    _setting(0.0, 2.65, 0.0)

    got = _CACHE[key] = m
    return got


def sideboard():
    """Dining room mahogany credenza with bottles and serving silver."""
    got = _CACHE.get("sideboard")
    if got is not None:
        return got
    m = Mesh()
    wood = _wood((68, 36, 22))
    dark = _wood((46, 24, 16))
    m.add(box(2.36, 0.74, 0.52, wood, center=(0.0, 0.50, 0.0)))
    for sx in (-1.08, 1.08):
        for sz in (-0.20, 0.20):
            m.add(box(0.08, 0.14, 0.08, dark, center=(sx, 0.07, sz)))
    m.add(box(2.44, 0.05, 0.58, (214, 208, 198), center=(0.0, 0.895, 0.0)))
    for cx in (-0.74, 0.0, 0.74):
        m.add(box(0.64, 0.54, 0.02, dark, center=(cx, 0.48, -0.265)))
        m.add(box(0.03, 0.05, 0.02, BRASS, center=(cx + 0.22, 0.50, -0.28)))
    m.add(box(0.46, 0.02, 0.30, (196, 202, 208), center=(-0.45, 0.93, 0.0)))
    for bx, col in ((-0.54, (32, 74, 38)), (-0.42, (118, 28, 30)), (-0.30, (32, 74, 38))):
        m.add(box(0.07, 0.24, 0.07, col, center=(bx, 1.05, 0.0)))
        m.add(box(0.03, 0.08, 0.03, col, center=(bx, 1.20, 0.0)))
    m.add(box(0.14, 0.04, 0.14, BRASS, center=(0.68, 0.94, 0.0)))
    m.add(box(0.04, 0.24, 0.04, GOLD, center=(0.68, 1.08, 0.0)))
    m.add(box(0.28, 0.18, 0.28, (242, 224, 178), center=(0.68, 1.26, 0.0), emissive=True))
    _CACHE["sideboard"] = m
    return m


def office_swivel_chair():
    """Rolling 5-star pedestal office chair (+Z faces desk)."""
    got = _CACHE.get("office_swivel")
    if got is not None:
        return got
    m = Mesh()
    steel = (38, 42, 46)
    leather = (30, 32, 36)
    for i in range(5):
        a = i * math.tau / 5.0
        ca, sa = math.cos(a), math.sin(a)
        m.add(box(0.04, 0.04, 0.28, steel), rot_y(math.degrees(a)), (sa * 0.14, 0.06, ca * 0.14))
        m.add(box(0.04, 0.04, 0.04, (18, 18, 20), center=(sa * 0.26, 0.02, ca * 0.26)))
    m.add(box(0.06, 0.36, 0.06, (62, 66, 72), center=(0.0, 0.24, 0.0)))
    m.add(box(0.48, 0.08, 0.46, leather, center=(0.0, 0.45, 0.02)))
    m.add(box(0.08, 0.34, 0.03, steel, center=(0.0, 0.62, -0.22)))
    m.add(box(0.44, 0.42, 0.08, leather), rot_x(-8.0), (0.0, 0.76, -0.20))
    for sx in (-0.25, 0.25):
        m.add(box(0.035, 0.18, 0.035, steel, center=(sx, 0.56, 0.02)))
        m.add(box(0.045, 0.032, 0.30, leather, center=(sx, 0.65, 0.02)))
    _CACHE["office_swivel"] = m
    return m


def executive_chair():
    """High-back tufted oxblood-leather presidential armchair (+Z forward)."""
    got = _CACHE.get("executive_chair")
    if got is not None:
        return got
    m = Mesh()
    wood = _wood((58, 30, 20))
    oxblood = (88, 24, 28)
    for i in range(5):
        a = i * math.tau / 5.0
        ca, sa = math.cos(a), math.sin(a)
        m.add(box(0.05, 0.05, 0.32, wood), rot_y(math.degrees(a)), (sa * 0.16, 0.07, ca * 0.16))
        m.add(box(0.045, 0.045, 0.045, BRASS, center=(sa * 0.30, 0.022, ca * 0.30)))
    m.add(box(0.09, 0.36, 0.09, BRASS, center=(0.0, 0.25, 0.0)))
    m.add(box(0.68, 0.07, 0.64, wood, center=(0.0, 0.44, 0.02)))
    m.add(box(0.64, 0.10, 0.60, oxblood, center=(0.0, 0.52, 0.02)))
    for sx in (-0.33, 0.33):
        m.add(box(0.07, 0.22, 0.07, wood, center=(sx, 0.58, 0.20)))
        m.add(box(0.09, 0.07, 0.48, oxblood, center=(sx, 0.69, 0.02)))
    back = Mesh()
    back.add(box(0.66, 0.72, 0.12, oxblood, center=(0.0, 0.36, 0.0)))
    back.add(box(0.70, 0.08, 0.14, wood, center=(0.0, 0.74, 0.0)))
    back.add(box(0.26, 0.06, 0.15, GOLD, center=(0.0, 0.79, 0.0)))
    for sx in (-0.32, 0.32):
        back.add(box(0.08, 0.68, 0.18, oxblood, center=(sx, 0.36, 0.06)))
    for tx in (-0.16, 0.0, 0.16):
        for ty in (0.24, 0.44, 0.60):
            back.add(box(0.025, 0.025, 0.02, GOLD, center=(tx, ty, 0.065)))
    m.add(back, rot_x(-8.0), (0.0, 0.52, -0.25))
    _CACHE["executive_chair"] = m
    return m


def study_desk():
    """Executive presidential twin-pedestal desk (top at y = 0.888 so placed at FF+0.012 -> FF+0.90)."""
    got = _CACHE.get("study_desk")
    if got is not None:
        return got
    m = Mesh()
    mahog = _wood((76, 42, 26))
    dark = _wood((50, 26, 18))
    top_col = _wood((98, 56, 34))
    for sx in (-0.94, 0.94):
        m.add(box(0.78, 0.74, 0.98, mahog, center=(sx, 0.44, 0.0)))
        m.add(box(0.84, 0.08, 1.04, dark, center=(sx, 0.04, 0.0)))
        for dy in (0.19, 0.42, 0.65):
            m.add(box(0.64, 0.18, 0.025, dark, center=(sx, dy, -0.495)))
            m.add(box(0.10, 0.025, 0.025, BRASS, center=(sx, dy, -0.515)))
            m.add(box(0.64, 0.18, 0.025, dark, center=(sx, dy, 0.495)))
            m.add(box(0.10, 0.025, 0.025, BRASS, center=(sx, dy, 0.515)))
    m.add(box(1.16, 0.64, 0.08, dark, center=(0.0, 0.46, -0.38)))
    m.add(box(2.78, 0.075, 1.12, top_col, center=(0.0, 0.850, 0.0)))
    m.add(box(2.68, 0.04, 1.02, dark, center=(0.0, 0.80, 0.0)))
    m.add(box(1.06, 0.010, 0.62, (28, 72, 46), center=(0.0, 0.892, 0.08)))
    m.add(box(1.08, 0.008, 0.64, GOLD, center=(0.0, 0.890, 0.08)))
    lx, lz = -0.34, -0.24
    m.add(box(0.16, 0.03, 0.16, BRASS, center=(lx, 0.903, lz)))
    m.add(box(0.03, 0.28, 0.03, BRASS, center=(lx, 1.05, lz)))
    m.add(box(0.24, 0.08, 0.12, (34, 136, 74), center=(lx, 1.20, lz + 0.03), emissive=True))
    m.add(box(0.28, 0.05, 0.34, (220, 212, 190), center=(0.12, 0.92, 0.10)))
    m.add(box(0.29, 0.016, 0.04, (162, 34, 34), center=(0.12, 0.942, 0.10)))
    _CACHE["study_desk"] = m
    return m


def bookshelf_bay(length=6.4, height=3.0, depth=0.50):
    """Three-bay mahogany library bookcase with pilaster stiles, crown cornice & varied books."""
    key = ("bookshelf_bay", round(length, 2), round(height, 2))
    got = _CACHE.get(key)
    if got is not None:
        return got
    m = Mesh()
    carcass = _wood((46, 26, 18))
    shelf = _wood((68, 38, 24))
    m.add(box(0.06, height, length, carcass, center=(depth * 0.5 - 0.03, height * 0.5, 0.0)))
    m.add(box(depth + 0.04, 0.16, length + 0.06, carcass, center=(0.0, 0.08, 0.0)))
    m.add(box(depth + 0.08, 0.16, length + 0.10, carcass, center=(-0.02, height - 0.08, 0.0)))
    m.add(box(depth + 0.02, 0.04, length + 0.04, GOLD, center=(-0.02, height - 0.17, 0.0)))
    for k in range(4):
        pz = -length * 0.5 + 0.08 + k * ((length - 0.16) / 3.0)
        m.add(box(depth, height - 0.24, 0.12, shelf, center=(0.0, height * 0.5, pz)))
    palette = ((124, 38, 34), (40, 56, 88), (88, 72, 36), (32, 66, 46), (72, 40, 28), (112, 86, 42))
    for s_idx in range(5):
        sy = 0.22 + s_idx * 0.53
        m.add(box(depth - 0.02, 0.045, length - 0.04, shelf, center=(0.0, sy, 0.0)))
        for bay in range(3):
            bz0 = -length * 0.5 + 0.18 + bay * ((length - 0.16) / 3.0)
            for b in range(11):
                bh = 0.28 + ((b * 7 + s_idx * 3 + bay) % 5) * 0.035
                bd = 0.12 + ((b + bay) % 3) * 0.025
                bcol = palette[(b + s_idx * 2 + bay) % len(palette)]
                bz = bz0 + b * 0.16
                m.add(box(0.28, bh, bd, bcol, center=(-0.04, sy + 0.022 + bh * 0.5, bz)))
                if (b + s_idx) % 4 == 0:
                    m.add(box(0.02, 0.04, bd + 0.004, GOLD, center=(-0.175, sy + 0.04 + bh * 0.65, bz)))
    _CACHE[key] = m
    return m


def four_poster_bed():
    """Carved mahogany four-poster bed with turned posts, canopy finials, pillows & draped duvet."""
    got = _CACHE.get("four_poster_bed")
    if got is not None:
        return got
    m = Mesh()
    mahog = _wood((66, 36, 22))
    dark = _wood((46, 24, 16))
    mattress = (228, 224, 214)
    sheet = (240, 236, 228)
    duvet = (126, 26, 34)
    duvet_fold = (146, 34, 42)
    for sx in (-1.12, 1.12):
        for sz, ph in ((1.34, 2.08), (-1.34, 1.32)):
            m.add(box(0.11, ph, 0.11, mahog, center=(sx, ph * 0.5, sz)))
            m.add(box(0.14, 0.08, 0.14, dark, center=(sx, 0.04, sz)))
            m.add(box(0.09, 0.12, 0.09, BRASS, center=(sx, ph + 0.06, sz)))
    m.add(box(2.14, 1.24, 0.10, mahog, center=(0.0, 0.94, 1.34)))
    m.add(box(1.86, 0.86, 0.04, duvet, center=(0.0, 1.00, 1.28)))
    m.add(box(1.90, 0.04, 0.05, GOLD, center=(0.0, 1.44, 1.28)))
    m.add(box(2.14, 0.62, 0.09, mahog, center=(0.0, 0.58, -1.34)))
    for sx in (-1.10, 1.10):
        m.add(box(0.08, 0.24, 2.58, mahog, center=(sx, 0.34, 0.0)))
    m.add(box(2.12, 0.18, 2.54, dark, center=(0.0, 0.35, 0.0)))
    m.add(box(2.10, 0.22, 2.50, mattress, center=(0.0, 0.54, 0.0)))
    m.add(box(2.14, 0.06, 0.42, sheet, center=(0.0, 0.66, 0.58)))
    m.add(box(2.18, 0.10, 1.72, duvet, center=(0.0, 0.67, -0.44)))
    m.add(box(2.22, 0.06, 0.24, duvet_fold, center=(0.0, 0.70, 0.34)))
    for sx in (-1.11, 1.11):
        m.add(box(0.05, 0.24, 1.72, duvet, center=(sx, 0.54, -0.44)))
    m.add(box(2.18, 0.22, 0.05, duvet, center=(0.0, 0.54, -1.29)))
    for sx in (-0.54, 0.54):
        m.add(box(0.86, 0.14, 0.46, sheet), rot_x(18.0), (sx, 0.74, 1.02))
        m.add(box(0.62, 0.12, 0.30, duvet_fold), rot_x(28.0), (sx, 0.72, 0.80))
    _CACHE["four_poster_bed"] = m
    return m


def nightstand(with_lamp=True):
    """Mahogany bedside cabinet with drawer, cupboard door & optional warm bedside lamp."""
    key = ("nightstand", bool(with_lamp))
    got = _CACHE.get(key)
    if got is not None:
        return got
    m = Mesh()
    wood = _wood((68, 36, 22))
    dark = _wood((46, 24, 16))
    for sx in (-0.22, 0.22):
        for sz in (-0.18, 0.18):
            m.add(box(0.05, 0.14, 0.05, dark, center=(sx, 0.07, sz)))
    m.add(box(0.52, 0.44, 0.44, wood, center=(0.0, 0.36, 0.0)))
    m.add(box(0.58, 0.04, 0.50, wood, center=(0.0, 0.60, 0.0)))
    m.add(box(0.42, 0.12, 0.02, dark, center=(0.0, 0.50, -0.225)))
    m.add(box(0.06, 0.025, 0.02, BRASS, center=(0.0, 0.50, -0.24)))
    m.add(box(0.42, 0.22, 0.02, dark, center=(0.0, 0.30, -0.225)))
    m.add(box(0.025, 0.05, 0.02, BRASS, center=(-0.14, 0.30, -0.24)))
    if with_lamp:
        m.add(box(0.14, 0.03, 0.14, BRASS, center=(0.0, 0.635, 0.0)))
        m.add(box(0.04, 0.20, 0.04, GOLD, center=(0.0, 0.74, 0.0)))
        m.add(box(0.28, 0.20, 0.28, (242, 218, 168), center=(0.0, 0.90, 0.0), emissive=True))
    _CACHE[key] = m
    return m


def wardrobe():
    """Tall twin-door mahogany armoire with brass handles and crown cornice."""
    got = _CACHE.get("wardrobe")
    if got is not None:
        return got
    m = Mesh()
    wood = _wood((66, 36, 22))
    dark = _wood((46, 24, 16))
    m.add(box(0.68, 2.04, 1.72, wood, center=(0.0, 1.14, 0.0)))
    m.add(box(0.74, 0.12, 1.78, dark, center=(0.0, 0.06, 0.0)))
    m.add(box(0.78, 0.14, 1.84, dark, center=(0.0, 2.20, 0.0)))
    for dz in (-0.42, 0.42):
        m.add(box(0.025, 1.78, 0.74, dark, center=(-0.345, 1.14, dz)))
        m.add(box(0.02, 0.14, 0.04, BRASS, center=(-0.365, 1.12, dz * 0.25)))
    _CACHE["wardrobe"] = m
    return m


def bed_bench():
    """Tufted velvet luggage bench at the foot of the master bed."""
    got = _CACHE.get("bed_bench")
    if got is not None:
        return got
    m = Mesh()
    wood = _wood((66, 36, 22))
    velvet = (126, 26, 32)
    for sx in (-0.78, 0.78):
        for sz in (-0.16, 0.16):
            m.add(box(0.06, 0.34, 0.06, wood, center=(sx, 0.17, sz)))
    m.add(box(1.74, 0.08, 0.44, wood, center=(0.0, 0.34, 0.0)))
    m.add(box(1.70, 0.10, 0.42, velvet, center=(0.0, 0.41, 0.0)))
    _CACHE["bed_bench"] = m
    return m


def wingback_armchair(col=(118, 28, 32)):
    """Deep tufted wingback lounge armchair (+Z forward)."""
    key = ("wingback", tuple(col))
    got = _CACHE.get(key)
    if got is not None:
        return got
    m = Mesh()
    wood = _wood((58, 30, 20))
    trim = tuple(max(12, c - 26) for c in col)
    for sx in (-0.32, 0.32):
        for sz in (-0.30, 0.30):
            m.add(box(0.06, 0.18, 0.06, wood, center=(sx, 0.09, sz)))
    m.add(box(0.76, 0.12, 0.74, trim, center=(0.0, 0.24, 0.0)))
    m.add(box(0.64, 0.14, 0.66, col, center=(0.0, 0.36, 0.04)))
    for sx in (-0.34, 0.34):
        m.add(box(0.14, 0.42, 0.68, col, center=(sx, 0.48, -0.02)))
        m.add(box(0.16, 0.08, 0.70, trim, center=(sx, 0.68, -0.02)))
    back = Mesh()
    back.add(box(0.74, 0.78, 0.14, col, center=(0.0, 0.39, 0.0)))
    for sx in (-0.33, 0.33):
        back.add(box(0.10, 0.68, 0.22, trim, center=(sx, 0.44, 0.08)))
    m.add(back, rot_x(-10.0), (0.0, 0.30, -0.28))
    got = _CACHE[key] = m
    return got


def round_side_table(with_lamp=False):
    """Pedestal mahogany occasional table with splayed tripod base."""
    key = ("round_side_table", bool(with_lamp))
    got = _CACHE.get(key)
    if got is not None:
        return got
    m = Mesh()
    wood = _wood((72, 38, 24))
    for i in range(3):
        a = i * 120.0
        m.add(box(0.06, 0.06, 0.30, wood), rot_y(a),
              (math.sin(math.radians(a)) * 0.14, 0.05, math.cos(math.radians(a)) * 0.14))
    m.add(box(0.08, 0.52, 0.08, wood, center=(0.0, 0.32, 0.0)))
    m.add(box(0.56, 0.05, 0.56, wood, center=(0.0, 0.60, 0.0)))
    m.add(box(0.46, 0.03, 0.46, wood, center=(0.0, 0.58, 0.0)), m=rot_y(45.0))
    if with_lamp:
        m.add(box(0.12, 0.03, 0.12, BRASS, center=(0.0, 0.64, 0.0)))
        m.add(box(0.04, 0.20, 0.04, GOLD, center=(0.0, 0.75, 0.0)))
        m.add(box(0.26, 0.18, 0.26, (242, 218, 168), center=(0.0, 0.90, 0.0), emissive=True))
    _CACHE[key] = m
    return m


def hall_console_table():
    """Narrow gilded mahogany console table with marble top & urn (+X faces into hall)."""
    got = _CACHE.get("hall_console")
    if got is not None:
        return got
    m = Mesh()
    wood = _wood((66, 36, 22))
    for sx in (-0.18, 0.18):
        for sz in (-0.64, 0.64):
            m.add(box(0.06, 0.78, 0.06, wood, center=(sx, 0.39, sz)))
            m.add(box(0.07, 0.06, 0.07, GOLD, center=(sx, 0.03, sz)))
    m.add(box(0.40, 0.08, 1.36, wood, center=(0.0, 0.75, 0.0)))
    m.add(box(0.46, 0.05, 1.44, (214, 208, 198), center=(0.0, 0.81, 0.0)))
    m.add(box(0.16, 0.22, 0.16, GOLD, center=(0.0, 0.94, 0.0)))
    m.add(box(0.22, 0.06, 0.22, (196, 158, 72), center=(0.0, 1.04, 0.0)))
    _CACHE["hall_console"] = m
    return m


def armoury_rack():
    """Open-frame steel gun rack with notched rifle silhouettes and olive ammo tins."""
    got = _CACHE.get("armoury_rack")
    if got is not None:
        return got
    m = Mesh()
    steel = tex("steel", like=(54, 58, 62), tint=True)
    dark = (26, 28, 32)
    stock = _wood((86, 52, 32))
    gunmetal = (36, 40, 44)
    olive = (74, 92, 56)
    for sx in (-0.28, 0.28):
        for sz in (-0.76, 0.76):
            m.add(box(0.06, 2.20, 0.06, steel, center=(sx, 1.10, sz)))
    for sy in (0.12, 0.72, 1.48, 2.16):
        m.add(box(0.58, 0.05, 1.56, steel, center=(0.0, sy, 0.0)))
    m.add(box(0.04, 2.10, 1.54, dark, center=(-0.28, 1.12, 0.0)))
    for az in (-0.45, 0.0, 0.45):
        m.add(box(0.36, 0.22, 0.34, olive, center=(0.0, 0.25, az)))
        m.add(box(0.38, 0.03, 0.36, (184, 152, 64), center=(0.0, 0.36, az)))
    for k in range(4):
        rz = -0.54 + k * 0.36
        m.add(box(0.10, 0.34, 0.045, stock, center=(0.04, 0.92, rz)))
        m.add(box(0.08, 0.42, 0.045, gunmetal, center=(0.04, 1.24, rz)))
        m.add(box(0.035, 0.36, 0.035, gunmetal, center=(0.04, 1.56, rz)))
    for az in (-0.36, 0.32):
        m.add(box(0.36, 0.26, 0.48, olive, center=(0.0, 1.64, az)))
    _CACHE["armoury_rack"] = m
    return m


def armoury_bench():
    """Steel gunsmith workbench with cleaning mat, spare mags, and workshop stool."""
    got = _CACHE.get("armoury_bench")
    if got is not None:
        return got
    m = Mesh()
    steel = tex("steel", like=(52, 56, 60), tint=True)
    top = _wood((84, 58, 38))
    for sx in (-0.32, 0.32):
        for sz in (-1.08, 1.08):
            m.add(box(0.07, 0.80, 0.07, steel, center=(sx, 0.40, sz)))
    m.add(box(0.74, 0.06, 2.34, top, center=(0.0, 0.83, 0.0)))
    m.add(box(0.68, 0.04, 2.22, steel, center=(0.0, 0.24, 0.0)))
    m.add(box(0.46, 0.01, 0.88, (44, 58, 44), center=(-0.04, 0.865, -0.25)))
    m.add(box(0.08, 0.04, 0.56, (32, 34, 38), center=(-0.04, 0.89, -0.25)))
    for mz in (0.48, 0.60, 0.72):
        m.add(box(0.04, 0.03, 0.16, (38, 42, 46), center=(0.06, 0.875, mz)))
    st_x, st_z = -0.46, 0.20
    for sx in (-0.14, 0.14):
        for sz in (-0.14, 0.14):
            m.add(box(0.035, 0.52, 0.035, steel, center=(st_x + sx, 0.26, st_z + sz)))
    m.add(box(0.36, 0.05, 0.36, (44, 46, 50), center=(st_x, 0.54, st_z)))
    _CACHE["armoury_bench"] = m
    return m


_FONT_3X5 = {
    "S": ("111", "100", "111", "001", "111"),
    "R": ("110", "101", "110", "101", "101"),
    "E": ("111", "100", "110", "100", "111"),
    "T": ("111", "010", "010", "010", "010"),
    "A": ("010", "101", "111", "101", "101"),
    "D": ("110", "101", "101", "101", "110"),
    "O": ("111", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "010"),
    "I": ("111", "010", "010", "010", "111"),
    "C": ("111", "100", "100", "100", "111"),
    ".": ("0", "0", "0", "0", "1"),
    " ": ("0", "0", "0", "0", "0"),
}


def _draw_pixel_text(surf, text, cx, cy, col):
    """Draw crisp 3x5 bitmap lettering centered at (cx, cy) on ``surf``."""
    glyphs = []
    cols = 0
    for ch in text:
        g = _FONT_3X5.get(ch, _FONT_3X5[" "])
        gw = len(g[0])
        glyphs.append((g, gw))
        cols += gw + 1
    cols = max(1, cols - 1)
    x0 = int(cx - cols // 2)
    y0 = int(cy - 2)
    cur_x = 0
    for g, gw in glyphs:
        for ry, row in enumerate(g):
            for rx, bit in enumerate(row):
                if bit == "1":
                    px, py = x0 + cur_x + rx, y0 + ry
                    if 0 <= px < surf.get_width() and 0 <= py < surf.get_height():
                        surf.set_at((px, py), col)
        cur_x += gw + 1


def _draw_seal_2d(surf, cx, cy, size):
    """Blit the M5 presidential seal or draw a crisp fallback emblem onto ``surf``."""
    seal = None
    try:
        from art import m5 as _m5art
        seal = _m5art.get("presidential_crest", 0)
    except Exception:
        seal = None
    if seal is not None:
        img = pygame.transform.scale(seal, (size, size))
        surf.blit(img, (cx - size // 2, cy - size // 2))
        return
    r = max(4, size // 2)
    pygame.draw.circle(surf, (196, 158, 72), (cx, cy), r)
    pygame.draw.circle(surf, (96, 120, 54), (cx, cy), max(2, r - 2))
    sh = pygame.Rect(cx - r // 2, cy - r // 2, r, int(r * 1.1))
    pygame.draw.rect(surf, (160, 30, 30), sh)
    pygame.draw.line(surf, (22, 22, 26), (cx - r // 3, cy), (cx + r // 3, cy), 2)
    pygame.draw.line(surf, (22, 22, 26), (cx, cy - r // 3), (cx, cy + r // 3), 2)


def _merge_rects(surf, q=8):
    """Greedy horizontal+vertical pixel run merge -> [(x0, y0, x1, y1, rgb)]."""
    w, h = surf.get_size()
    open_ = {}
    out = []
    for y in range(h + 1):
        runs = {}
        if y < h:
            x = 0
            while x < w:
                r, g, b, _a = surf.get_at((x, y))
                c = (r // q * q, g // q * q, b // q * q)
                x1 = x + 1
                while x1 < w:
                    r2, g2, b2, _a2 = surf.get_at((x1, y))
                    if (r2 // q * q, g2 // q * q, b2 // q * q) != c:
                        break
                    x1 += 1
                runs[(x, x1, c)] = True
                x = x1
        nxt = {}
        for key, y0 in open_.items():
            if key in runs:
                nxt[key] = y0
            else:
                out.append((key[0], y0, key[1], y, key[2]))
        for key in runs:
            if key not in nxt:
                nxt[key] = y
        open_ = nxt
    return out


def _render_president_photo(pw, ph, w, h, paint):
    """Compose a Balaceanu-style painted state portrait of S. Retardovici."""
    plaque_h = 11
    avail_h = ph - plaque_h
    # Lift dark wall paints so Obj's indoor light.shade() keeps suit & backdrop distinct.
    base_bg = tuple(min(205, max(56, int(c * 1.45 + 24))) for c in paint)
    lit_bg = tuple(min(232, int(c * 1.22 + 12)) for c in base_bg)
    canvas = pygame.Surface((pw, ph))
    canvas.fill(base_bg)
    canvas.fill(lit_bg, (0, 0, int(pw * 0.42), avail_h))
    # Subtle warm studio halo behind the head & shoulders
    halo_cx, halo_cy = pw // 2, int(avail_h * 0.42)
    for r_k, boost in ((0.44, 14), (0.31, 26), (0.19, 38)):
        rad = max(8, int(min(pw, avail_h) * r_k))
        hcol = tuple(min(240, c + boost) for c in base_bg)
        pygame.draw.circle(canvas, hcol, (halo_cx, halo_cy), rad)

    if w > h * 1.12:
        cw = max(8, int(pw * 0.14))
        for rx in (0, pw - cw):
            canvas.fill((96, 26, 30), (rx, 0, cw, avail_h))
            canvas.fill((126, 34, 38), (rx + (cw // 3 if rx == 0 else 0), 0, max(2, cw // 3), avail_h))
        canvas.fill((208, 168, 78), (cw - 1, 0, 1, avail_h))
        canvas.fill((208, 168, 78), (pw - cw, 0, 1, avail_h))

    # Frame Retardovici from hair crest (-296) to below the 3rd gold button (-120)
    scale = avail_h / 188.0
    foot_y = int(round(avail_h + 120.0 * scale))
    cx = pw // 2 + (1 if w > h * 1.12 else 0)
    draw_character(
        canvas, "president", cx, foot_y,
        scale=scale, facing_right=True, t=0, look=0,
    )

    # Presidential seal in upper-left corner of canvas
    seal_sz = 18 if pw >= 84 else 14
    sx = (max(8, int(pw * 0.14)) + seal_sz // 2 + 4) if w > h * 1.12 else (seal_sz // 2 + 4)
    _draw_seal_2d(canvas, sx, seal_sz // 2 + 4, seal_sz)

    # Crisp brass nameplate strip + "S. RETARDOVICI" along the bottom edge
    pl_w = min(pw - 6, max(60, int(pw * 0.84)))
    pl_x = (pw - pl_w) // 2
    pl_y = ph - plaque_h
    canvas.fill((36, 28, 22), (0, avail_h, pw, plaque_h))
    canvas.fill((96, 74, 34), (pl_x, pl_y, pl_w, plaque_h))
    canvas.fill((208, 172, 82), (pl_x + 1, pl_y + 1, pl_w - 2, plaque_h - 2))
    canvas.fill((232, 200, 112), (pl_x + 1, pl_y + 1, pl_w - 2, 1))
    for rx in (pl_x + 2, pl_x + pl_w - 3):
        canvas.set_at((rx, pl_y + 2), (120, 90, 38))
        canvas.set_at((rx, pl_y + plaque_h - 3), (120, 90, 38))
    _draw_pixel_text(canvas, "S. RETARDOVICI", pw // 2, pl_y + plaque_h // 2, (26, 18, 14))
    return canvas


def president_portrait(w=1.3, h=1.7, paint=(54, 64, 58)):
    """Flat 2D studio photo/painting of the angled 3D Retardovici model in a gilt frame (faces -Z)."""
    key = ("president_portrait", round(w, 3), round(h, 3), tuple(paint))
    got = _CACHE.get(key)
    if got is not None:
        return got
    m = Mesh()
    frame_d = 0.042
    m.add(box(w + 0.16, h + 0.16, 0.016, (92, 72, 34), center=(0.0, 0.0, -0.008)))
    for sx in (-1, 1):
        m.add(box(0.08, h + 0.16, frame_d, GOLD, center=(sx * (w * 0.5 + 0.04), 0.0, -frame_d * 0.5)))
    for sy in (-1, 1):
        m.add(box(w + 0.16, 0.08, frame_d, GOLD, center=(0.0, sy * (h * 0.5 + 0.04), -frame_d * 0.5)))
    m.add(box(w + 0.02, h + 0.02, 0.016, (148, 120, 56), center=(0.0, 0.0, -0.016)))

    ph = 96
    pw = max(56, int(round(ph * w / h)))
    surf = _render_president_photo(pw, ph, w, h, paint)
    zc = -0.028
    for x0, y0, x1, y1, col in _merge_rects(surf, q=8):
        px0, px1 = (x0 / pw - 0.5) * w, (x1 / pw - 0.5) * w
        py0, py1 = (0.5 - y0 / ph) * h, (0.5 - y1 / ph) * h
        # Wind for a -Z normal (the frame's front face), so the baked face
        # shading matches the frame instead of darkening the whole photograph.
        m.face([(px0, py1, zc), (px0, py0, zc), (px1, py0, zc), (px1, py1, zc)], col, 2, False)

    got = _CACHE[key] = m
    return got
