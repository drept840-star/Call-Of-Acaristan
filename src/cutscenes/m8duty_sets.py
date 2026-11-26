"""Mission 8 Duty 3D sets: Capital Square Courthouse and Forest Crash Clearings.

Built once and cached as static ``Mesh`` objects so ``m8dutyfilms`` and
``ridge3d`` submit them via ``chase_set.put`` with zero per-frame allocation.
"""
import math
import random

from cutscenes import m7world3d as W7
from engine3d import Mesh, box, disc_xz, prism, quad_xz
from engine3d.core import Light, rot_x, rot_y, rot_z
from engine3d.textures import tex
from missions.m8.revenge import chase_set as CS
from missions.m8.revenge import epilogue3d as E

# E.FUNERAL is a (x, z) pair; the rest of this module and m8dutyfilms use (x, y, z).
CH = (E.FUNERAL[0], 0.0, E.FUNERAL[1])
TOP = 1.50
VAS_AT = (CH[0], TOP, CH[2] - 0.55)
CROWD_Z = CH[2] - 8.6

_CACHE = {}


def _pine_tree(seed, h=11.0):
    """Slimmer, darker spruce silhouette with seven dense evergreen bough tiers."""
    rng = random.Random(seed)
    m = Mesh()
    bark = tex("m7_bark", like=(28, 22, 18), tint=True)
    m.add(box(0.34, h * 0.30, 0.34, bark, center=(0.0, h * 0.15, 0.0)))
    cols = ((8, 18, 14), (10, 22, 16), (7, 16, 12), (11, 24, 17))
    for i in range(7):
        y = h * (0.09 + i * 0.122)
        rad = h * (0.128 - i * 0.0145) * rng.uniform(0.90, 1.10)
        up = h * (0.175 - i * 0.013)
        dn = h * 0.042
        col = tex("m7_leaf", like=cols[i % len(cols)], tint=True)
        jx, jz = rng.uniform(-0.08, 0.08), rng.uniform(-0.08, 0.08)
        m.add(W7._bipyr(jx, y, jz, rad, up, dn, col, n=8 + (i % 2)))
    return m


def _crash_pine(seed, h=13.0):
    """Lean, dark night spruce for the crash clearing (5 tiers, ~66 faces)."""
    rng = random.Random(seed)
    m = Mesh()
    bark = tex("m7_bark", like=(22, 17, 14), tint=True)
    m.add(box(0.36, h * 0.30, 0.36, bark, center=(0.0, h * 0.15, 0.0)))
    cols = ((8, 16, 13), (10, 20, 15), (7, 15, 12), (11, 22, 16))
    for i in range(5):
        y = h * (0.12 + i * 0.165)
        rad = h * (0.145 - i * 0.021) * rng.uniform(0.90, 1.10)
        up = h * (0.22 - i * 0.020)
        dn = h * 0.045
        col = tex("m7_leaf", like=cols[i % len(cols)], tint=True)
        jx, jz = rng.uniform(-0.08, 0.08), rng.uniform(-0.08, 0.08)
        m.add(W7._bipyr(jx, y, jz, rad, up, dn, col, n=6))
    return m


def _courthouse_building(m, fx, fz):
    """Neoclassical / Eastern-bloc Palace of Justice facing -z at (fx, 0, fz)."""
    stone = tex("ashlar", like=(164, 158, 146), tint=True, density=32.0)
    plaster = tex("stucco", like=(206, 198, 180), tint=True, density=48.0)
    trim = tex("stucco", like=(228, 222, 208), tint=True, density=48.0)
    slate = tex("steel", like=(68, 74, 82), tint=True)
    dark_wood = W7._t("plank", (62, 42, 30))
    glass = (34, 48, 66)
    warm_win = (214, 184, 128)
    gold = E.GOLD

    # Wide raised granite terrace + 6 monumental steps (front z = -4.8 .. 0.0)
    m.add(box(24.0, TOP, 21.0, stone, center=(fx, TOP * 0.5, fz + 9.0)))
    for i in range(6):
        w = 21.6 - i * 0.45
        d = 4.6 - i * 0.72
        h = 0.24
        y = 0.12 + i * h
        cz = fz - 3.6 + i * 0.36
        m.add(box(w, h, d, stone, center=(fx, y, cz)))
    # Stepped stone cheek walls & bronze lamp pedestals flanking the stair
    for s in (-1, 1):
        m.add(box(1.1, 1.55, 5.2, stone, center=(fx + s * 10.8, 0.85, fz - 3.3)))
        m.add(box(1.3, 0.18, 5.4, trim, center=(fx + s * 10.8, 1.70, fz - 3.3)))
        m.add(box(0.22, 1.1, 0.22, (34, 34, 38), center=(fx + s * 10.8, 2.34, fz - 5.2)))
        m.add(box(0.38, 0.42, 0.38, (255, 224, 160), center=(fx + s * 10.8, 3.05, fz - 5.2), emissive=True))

    # Central Pavilion (x -11..+11, z +2.4..+19.5, height TOP..12.6)
    m.add(box(22.0, 11.1, 17.2, plaster, center=(fx, TOP + 5.55, fz + 11.0)))
    m.add(box(22.4, 1.6, 17.6, stone, center=(fx, TOP + 0.8, fz + 11.0)))
    m.add(box(22.8, 0.55, 18.0, trim, center=(fx, 12.65, fz + 11.0)))
    # Central slate hip/mansard roof + clock/flagpole cupola
    m.add(box(20.6, 2.2, 15.6, slate, center=(fx, 14.0, fz + 11.0)))
    m.add(box(17.4, 1.1, 12.4, slate, center=(fx, 15.6, fz + 11.0)))
    m.add(box(0.12, 5.0, 0.12, (160, 160, 166), center=(fx, 18.4, fz + 8.0)))
    for i, col in enumerate((E.NAVY, E.RED)):
        m.add(box(0.04, 0.75, 1.6, col, center=(fx + 0.04, 20.1 - i * 0.75, fz + 8.8)))

    # Symmetrical East & West Courthouse Wings (x +-11..+-23, z +3.6..+18.4)
    for s in (-1, 1):
        wx = fx + s * 17.0
        m.add(box(12.0, 9.6, 14.8, plaster, center=(wx, 4.8, fz + 11.0)))
        m.add(box(12.3, 1.7, 15.1, stone, center=(wx, 0.85, fz + 11.0)))
        m.add(box(12.6, 0.45, 15.4, trim, center=(wx, 9.75, fz + 11.0)))
        m.add(box(11.4, 1.8, 14.0, slate, center=(wx, 10.85, fz + 11.0)))
        # Vertical stone pilasters & two tiers of tall recessed courtroom windows
        for px_off in (-4.4, -1.5, 1.5, 4.4):
            m.add(box(0.65, 7.6, 0.22, trim, center=(wx + px_off, 5.7, fz + 3.56)))
        for wx_off in (-2.95, 0.0, 2.95):
            for wy, lit in ((3.4, True), (7.0, False)):
                m.add(box(1.55, 2.5, 0.14, trim, center=(wx + wx_off, wy, fz + 3.55)))
                m.add(box(1.22, 2.1, 0.08, warm_win if lit else glass,
                          center=(wx + wx_off, wy, fz + 3.50), emissive=lit))
                m.add(box(1.22, 0.06, 0.12, (46, 46, 50), center=(wx + wx_off, wy, fz + 3.47)))
                m.add(box(0.06, 2.1, 0.12, (46, 46, 50), center=(wx + wx_off, wy, fz + 3.47)))

    # Main portico: 6 tall columns supporting entablature + triangular pediment
    for cx_off in (-7.8, -4.7, -1.6, 1.6, 4.7, 7.8):
        cx = fx + cx_off
        cz = fz - 1.4
        m.add(box(0.98, 0.36, 0.98, stone, center=(cx, TOP + 0.18, cz)))
        m.add(box(0.68, 7.0, 0.68, trim, center=(cx, TOP + 3.86, cz)))
        m.add(box(1.04, 0.38, 1.04, stone, center=(cx, TOP + 7.54, cz)))
    # Portico roof & entablature spanning back to central pavilion
    m.add(box(19.6, 0.95, 4.8, trim, center=(fx, TOP + 8.20, fz + 0.4)))
    m.add(box(20.2, 0.25, 5.2, stone, center=(fx, TOP + 8.78, fz + 0.4)))
    m.add(prism([(-10.1, TOP + 8.85), (10.1, TOP + 8.85), (0.0, TOP + 12.25)],
                4.8, plaster, z0=fz - 2.0))
    # Pediment cornice trim + gold national seal in the tympanum
    m.add(box(0.95, 0.95, 0.12, E.NAVY, center=(fx, TOP + 10.35, fz - 2.02)))
    m.add(box(0.62, 0.62, 0.14, gold, center=(fx, TOP + 10.35, fz - 2.06)))

    # Tall carved double doors & flanked courtroom windows behind the columns
    m.add(box(3.8, 5.4, 0.22, stone, center=(fx, TOP + 2.7, fz + 2.36)))
    m.add(box(3.0, 4.7, 0.14, dark_wood, center=(fx, TOP + 2.35, fz + 2.30)))
    m.add(box(0.08, 4.7, 0.18, gold, center=(fx, TOP + 2.35, fz + 2.26)))
    for s in (-1, 1):
        for wx_off in (5.2, 8.6):
            for wy, lit in ((TOP + 2.5, True), (TOP + 6.1, False)):
                m.add(box(1.55, 2.4, 0.14, trim, center=(fx + s * wx_off, wy, fz + 2.36)))
                m.add(box(1.22, 2.05, 0.08, warm_win if lit else glass,
                          center=(fx + s * wx_off, wy, fz + 2.31), emissive=lit))
        # Hanging vertical banners flanking the portal
        m.add(box(0.95, 3.8, 0.05, E.NAVY, center=(fx + s * 3.1, TOP + 4.4, fz + 2.24)))
        m.add(box(0.95, 1.3, 0.055, E.RED, center=(fx + s * 3.1, TOP + 3.15, fz + 2.23)))
        m.add(box(0.28, 0.28, 0.06, gold, center=(fx + s * 3.1, TOP + 5.2, fz + 2.22)))

    # Carpet runner, podium, microphones, and four ceremonial flags on top terrace
    m.add(box(3.4, 0.03, 5.4, E.RED, center=(fx, TOP + 0.015, fz - 0.1)))
    m.add(box(1.1, 1.18, 0.56, dark_wood, center=(fx, TOP + 0.59, fz - 1.15)))
    m.add(box(0.42, 0.42, 0.04, gold, center=(fx, TOP + 0.66, fz - 1.44)))
    for mx in (-0.18, 0.18):
        m.add(box(0.03, 0.34, 0.03, (34, 34, 38), center=(fx + mx, TOP + 1.34, fz - 1.28)))
    for fx_off, fz_off in ((-2.4, -0.7), (2.4, -0.7), (-4.0, 0.4), (4.0, 0.4)):
        fm = Mesh()
        E._flag(fm, 0.0, 0.0, h=2.85, w=0.72)
        m.add(fm, t=(fx + fx_off, TOP, fz + fz_off))


def _city_block(w, h, d, wall_col, win_lit_mod=7):
    """Background Eastern-bloc ministry / civic building closing the square."""
    m = Mesh()
    wall = tex("stucco", like=wall_col, tint=True, density=48.0)
    stone = tex("ashlar", like=(126, 122, 114), tint=True, density=32.0)
    roof = tex("steel", like=(62, 66, 72), tint=True)
    m.add(box(w, h, d, wall, center=(0.0, h * 0.5, 0.0)))
    m.add(box(w + 0.3, 1.8, d + 0.3, stone, center=(0.0, 0.9, 0.0)))
    m.add(box(w + 0.5, 0.45, d + 0.5, stone, center=(0.0, h + 0.2, 0.0)))
    m.add(box(w - 0.4, 0.8, d - 0.4, roof, center=(0.0, h + 0.8, 0.0)))
    floors = max(2, int((h - 2.5) // 3.0))
    cols = max(3, int(w // 3.8))
    for fl in range(floors):
        wy = 3.2 + fl * 3.0
        for ci in range(cols):
            wx = -w * 0.5 + 2.2 + ci * ((w - 4.4) / max(1, cols - 1))
            lit = (fl * 5 + ci * 3) % win_lit_mod == 0
            col = (218, 188, 128) if lit else (34, 44, 58)
            m.add(box(1.5, 1.7, 0.08, col, center=(wx, wy, -d * 0.5 - 0.03), emissive=lit))
            m.add(box(1.5, 1.7, 0.08, col, center=(wx, wy, d * 0.5 + 0.03), emissive=lit))
    return m


def courthouse_square():
    """Complete paved Capital Square + Palace of Justice + surrounding ministries."""
    m = _CACHE.get("courthouse_square")
    if m is not None:
        return m
    m = _CACHE["courthouse_square"] = Mesh()
    fx, fz = CH[0], CH[2]
    pave = tex("pavement", like=(118, 114, 108), tint=True)
    granite = tex("ashlar", like=(142, 138, 130), tint=True, density=32.0)
    asphalt = tex("pavement", like=(62, 64, 68), tint=True)
    kerb = W7._t("stone", (156, 152, 144))
    steel = (88, 94, 102)

    # Full paved square replacing rural grass out to +-82 m
    m.add(quad_xz(fx - 82.0, fz - 76.0, fx + 82.0, fz + 76.0, 0.08, pave, layer=1, seg=16.0))
    # Subtle granite plaza grid ribs & central ceremonial promenade
    m.add(quad_xz(fx - 26.0, fz - 22.0, fx + 26.0, fz + 24.0, 0.10, granite, layer=1, seg=12.0))
    for gz in range(-20, 4, 4):
        m.add(box(48.0, 0.015, 0.14, (96, 92, 86), center=(fx, 0.108, fz + gz)))
    for gx in range(-24, 28, 4):
        m.add(box(0.14, 0.015, 24.0, (96, 92, 86), center=(fx + gx, 0.108, fz - 10.0)))

    # East-west boulevard road across the south end of the square
    m.add(quad_xz(fx - 82.0, fz - 36.0, fx + 82.0, fz - 23.5, 0.09, asphalt, layer=1, seg=16.0))
    m.add(box(164.0, 0.10, 0.35, kerb, center=(fx, 0.11, fz - 23.4)))
    m.add(box(164.0, 0.10, 0.35, kerb, center=(fx, 0.11, fz - 36.1)))
    for dx in range(-72, 76, 8):
        m.add(box(3.4, 0.01, 0.16, (210, 206, 192), center=(fx + dx, 0.10, fz - 29.75)))

    # Monumental Courthouse
    _courthouse_building(m, fx, fz)

    # Steel crowd barriers framing the plaza audience
    for sx in (-1, 1):
        for bx in (4.2, 6.8, 9.4, 12.0):
            cx = fx + sx * bx
            bz = CROWD_Z + 1.4
            m.add(box(2.3, 0.06, 0.06, steel, center=(cx, 0.92, bz)))
            m.add(box(2.3, 0.05, 0.05, steel, center=(cx, 0.48, bz)))
            for px in (-1.0, 1.0):
                m.add(box(0.06, 0.96, 0.06, steel, center=(cx + px, 0.48, bz)))

    # Streetlamps & boulevard trees around the square
    for x_off in (-22.0, -13.5, 13.5, 22.0):
        for z_off in (-22.0, -10.0):
            E._lamp_post(m, fx + x_off, fz + z_off, h=4.2)
    for k, x_off in enumerate((-30.0, -18.0, 18.0, 30.0)):
        m.add(W7.tree(10 + k), t=(fx + x_off, 0.08, fz - 22.2))
        m.add(W7._poplar(20 + k, 11.5), t=(fx + x_off * 1.15, 0.08, fz - 38.0))

    # Flanking & opposite ministry buildings enclosing the Capital Square
    m.add(_city_block(30.0, 14.5, 14.0, (176, 170, 158)), rot_y(90), (fx - 44.0, 0.08, fz - 4.0))
    m.add(_city_block(28.0, 13.5, 14.0, (166, 162, 152)), rot_y(-90), (fx + 44.0, 0.08, fz - 4.0))
    m.add(_city_block(34.0, 15.0, 14.0, (182, 176, 164)), rot_y(0), (fx - 22.0, 0.08, fz - 52.0))
    m.add(_city_block(34.0, 14.0, 14.0, (168, 164, 154)), rot_y(0), (fx + 22.0, 0.08, fz - 52.0))
    m.add(_city_block(26.0, 16.0, 14.0, (172, 166, 156)), rot_y(0), (fx - 34.0, 0.08, fz + 24.0))
    m.add(_city_block(26.0, 16.0, 14.0, (172, 166, 156)), rot_y(0), (fx + 34.0, 0.08, fz + 24.0))
    return m


def courthouse_lights():
    fx, fz = CH[0], CH[2]
    return [
        {"pos": (fx, 5.2, fz - 3.0), "color": (255, 224, 182), "intensity": 0.95, "range": 18.0},
        {"pos": (fx - 13.5, 4.6, fz - 10.0), "color": (255, 214, 164), "intensity": 0.65, "range": 14.0},
        {"pos": (fx + 13.5, 4.6, fz - 10.0), "color": (255, 214, 164), "intensity": 0.65, "range": 14.0},
        {"pos": (fx, 4.2, fz + 1.5), "color": (255, 216, 168), "intensity": 0.70, "range": 12.0},
    ]


def crash_forest(center=(0.0, 0.0, 0.0)):
    """Dense Carpathian spruce clearing around ``center`` with torn earth, mossy log bank, and pinned girder."""
    key = ("crash_forest", int(center[0]), int(center[2]))
    m = _CACHE.get(key)
    if m is not None:
        return m
    m = _CACHE[key] = Mesh()
    cx, _, cz = center
    rng = random.Random(8402)
    dirt = W7._t("dirt", (32, 26, 21))
    scorch = tex("scorch", like=(18, 16, 16))
    moss = tex("m7_grass", like=(13, 21, 15), tint=True)
    outer_ground = tex("m7_grass", like=(9, 14, 12), tint=True)
    bark = tex("m7_bark", like=(30, 23, 18), tint=True)
    bark_hi = tex("m7_bark", like=(38, 30, 22), tint=True)
    steel = (48, 52, 58)
    steel_dark = (30, 32, 36)
    char = (24, 25, 28)

    # Wide forest floor + clearing dirt + scorch trenches under wreck (-2.2, 4.8) & tail debris (-4.8, -2.6)
    m.add(quad_xz(cx - 88.0, cz - 88.0, cx + 88.0, cz + 88.0, 0.0, outer_ground, layer=0, seg=22.0))
    m.add(quad_xz(cx - 26.0, cz - 26.0, cx + 26.0, cz + 26.0, 0.025, moss, layer=1, seg=13.0))
    m.add(quad_xz(cx - 7.5, cz - 6.0, cx + 6.0, cz + 9.0, 0.04, dirt, layer=1, seg=5.0))
    m.add(quad_xz(cx - 6.2, cz + 1.2, cx + 2.2, cz + 9.2, 0.052, scorch, layer=1, seg=4.0))
    m.add(quad_xz(cx - 6.8, cz - 4.4, cx - 2.6, cz - 0.8, 0.052, scorch, layer=1, seg=3.0))

    # Substantial fallen mossy spruce log + earth bank directly supporting Maru's reclined back
    # Maru sits at (cx + 0.55, 0, cz + 0.15) facing SW (225 deg); back leans NE (+0.707, +0.707)
    log_m = Mesh()
    log_m.add(box(0.68, 0.54, 2.8, bark, center=(0.0, 0.27, 0.0)))
    log_m.add(box(0.52, 0.22, 2.6, bark_hi, center=(0.04, 0.62, 0.0)))
    log_m.add(box(0.38, 0.10, 2.2, moss, center=(0.06, 0.74, -0.1)))
    log_m.add(box(0.92, 0.34, 2.9, dirt, center=(0.30, 0.16, 0.0)))
    m.add(log_m, rot_y(135.0), (cx + 1.06, 0.0, cz + 0.66))

    # Heavy sheared aircraft fuselage girder pinning Maru's right leg cleanly to the earth
    girder = Mesh()
    girder.add(box(0.32, 0.24, 2.35, steel, center=(0.0, 0.13, 0.0)))
    girder.add(box(0.38, 0.05, 2.35, steel_dark, center=(0.0, 0.25, 0.0)))
    girder.add(box(0.38, 0.05, 2.35, steel_dark, center=(0.0, 0.03, 0.0)))
    for gz in (-0.85, -0.35, 0.25, 0.80):
        girder.add(box(0.36, 0.22, 0.06, char, center=(0.0, 0.14, gz)))
    # Torn skin plate & hydraulic strut hanging off the outer end of the girder
    girder.add(box(0.55, 0.06, 0.68, (56, 62, 54), center=(0.18, 0.22, -0.82)))
    m.add(girder, rot_y(132.0), (cx + 0.14, 0.0, cz - 0.18))

    # Wreckage scatter: snapped rotor blades, cowling panels & charred tail-boom chunk at (-4.8, -2.6)
    m.add(box(0.24, 0.05, 3.6, (26, 28, 32)), rot_y(28.0), (cx - 0.2, 0.06, cz + 2.9))
    m.add(box(0.24, 0.05, 2.9, (26, 28, 32)), rot_y(-46.0), (cx - 4.4, 0.06, cz + 3.4))
    m.add(box(0.75, 0.26, 1.45, char), rot_y(18.0), (cx + 1.8, 0.12, cz + 3.6))
    # Secondary burning tail-boom/rotor debris pile in W-SW clearing (visible behind Biribel in crash_promise)
    m.add(box(0.95, 0.52, 2.1, char), rot_y(58.0), (cx - 4.8, 0.26, cz - 2.6))
    m.add(box(0.22, 0.06, 2.5, steel_dark), rot_y(-22.0), (cx - 4.3, 0.10, cz - 2.1))
    m.add(box(0.45, 0.36, 0.65, steel), rot_y(14.0), (cx - 5.2, 0.18, cz - 3.1))

    # Sheared pine stumps along the crash entry path
    for sx, sz in ((cx + 4.4, cz - 1.8), (cx - 3.6, cz + 1.4), (cx + 1.6, cz + 6.2)):
        m.add(box(0.42, 0.85, 0.42, bark, center=(sx, 0.42, sz)))
        m.add(box(0.38, 0.05, 0.38, (132, 112, 82), center=(sx, 0.86, sz)))

    # Two dense spruce rings closing all sightlines while keeping camera wedges & wreck open
    idx = 0
    for n_ring, r0, r1 in ((24, 9.2, 14.8), (40, 15.2, 28.0)):
        for i in range(n_ring):
            ang = math.tau * i / float(n_ring) + rng.uniform(-0.07, 0.07)
            rad = rng.uniform(r0, r1)
            px = cx + math.cos(ang) * rad
            pz = cz + math.sin(ang) * rad
            if math.hypot(px - cx, pz - cz) < 8.4:
                continue
            # Keep burning gunship wreck & secondary debris fire footprints clear
            if math.hypot(px - (cx - 2.2), pz - (cz + 4.8)) < 5.6:
                continue
            if math.hypot(px - (cx - 4.8), pz - (cz - 2.6)) < 3.6:
                continue
            # Keep crash_spin & crash_fire southern camera corridor unobstructed
            if -9.5 < (px - cx) < 6.0 and -21.0 < (pz - cz) < -2.0:
                continue
            h = rng.uniform(11.5, 19.5)
            m.add(_crash_pine(900 + idx, h), rot_y(rng.uniform(0.0, 360.0)), (px, 0.0, pz))
            idx += 1

    # Dark Carpathian mountain ridge wall + low brush skirt sealing 360-deg horizon
    ridge_col = (10, 15, 22)
    n_seg = 24
    r_ridge = 52.0
    for i in range(n_seg):
        a0 = math.tau * i / float(n_seg)
        a1 = math.tau * (i + 1) / float(n_seg)
        x0, z0 = cx + math.sin(a0) * r_ridge, cz + math.cos(a0) * r_ridge
        x1, z1 = cx + math.sin(a1) * r_ridge, cz + math.cos(a1) * r_ridge
        h0 = 14.0 + 7.5 * math.sin(i * 1.9) + 4.5 * math.cos(i * 3.1)
        h1 = 14.0 + 7.5 * math.sin((i + 1) * 1.9) + 4.5 * math.cos((i + 1) * 3.1)
        m.face([(x0, -1.0, z0), (x1, -1.0, z1), (x1, h1, z1), (x0, h0, z0)],
               ridge_col, layer=0, double=True)
    shrub_col = tex("m7_leaf", like=(9, 17, 13), tint=True)
    for i in range(22):
        ang = math.tau * i / 22.0 + 0.14
        rad = rng.uniform(9.5, 16.5)
        sx, sz = cx + math.cos(ang) * rad, cz + math.sin(ang) * rad
        if math.hypot(sx - (cx - 2.2), sz - (cz + 4.8)) < 5.0:
            continue
        if -9.5 < (sx - cx) < 6.0 and -21.0 < (sz - cz) < -2.0:
            continue
        m.add(W7._bipyr(sx, 0.0, sz, rng.uniform(1.4, 2.2), rng.uniform(1.5, 2.5), 0.12, shrub_col, n=5))
    return m


def crash_renderer(size=(640, 286)):
    """Dedicated cached Renderer with the crash forest statically baked once."""
    r = _CACHE.get("crash_r")
    if r is not None:
        return r
    from engine3d import Renderer
    r = Renderer(size[0], size[1], fog=(9, 13, 22), fog_start=18.0, fog_end=78.0)
    r.light = Light(direction=(0.45, 0.68, -0.52), ambient=0.16, diffuse=0.34,
                    sky=0.12, tint=(0.62, 0.74, 1.0))
    r.bake(crash_forest((0.0, 0.0, 0.0)))
    _CACHE["crash_r"] = r
    return r


def crash_frame(eye, tgt, fov, t=0, size=(640, 286), lights=(), pools=(), roll=0.0):
    """Set camera, Carpathian night sky, fog, and lights on the cached crash renderer."""
    r = crash_renderer(size)
    r.resize(size[0], size[1])
    r.hdr = False
    r.set_camera(eye, tgt, fov, roll)
    r.fog, r.fog_start, r.fog_end = (9, 13, 22), 18.0, 78.0
    r.light = Light(direction=(0.45, 0.68, -0.52), ambient=0.16, diffuse=0.34,
                    sky=0.12, tint=(0.62, 0.74, 1.0))
    try:
        r.set_lights(list(lights))
        r.set_pools(list(pools))
    except Exception:
        pass
    W7.sky(r, r.surface, t, "raid")
    r.begin()
    r.add_static()
    return r


def _snow_pine(seed, h=13.0):
    """Dark Carpathian night spruce with subtle snow-dusted bough tips."""
    m = _crash_pine(seed, h)
    rng = random.Random(seed + 41)
    snow_cap = tex("snow", like=(164, 176, 198), tint=True)
    for i in range(3):
        y = h * (0.28 + i * 0.21)
        rad = h * (0.11 - i * 0.020) * rng.uniform(0.92, 1.08)
        m.add(W7._bipyr(0.0, y + 0.14, 0.0, rad, h * 0.06, 0.02, snow_cap, n=6))
    return m


def _tripod_light(x, z, yaw=0.0):
    """Steel tripod floodlight stand with warm amber halogen diffuser at y=1.86 m."""
    from engine3d.core import m_mul
    m = Mesh()
    steel = (38, 42, 48)
    lamp = (242, 186, 108)
    leg = box(0.045, 1.48, 0.045, steel, center=(0.0, 0.72, 0.0))
    for a_deg in (0.0, 120.0, 240.0):
        a = math.radians(a_deg + yaw)
        rot = m_mul(rot_y(a_deg + yaw), rot_x(-16.0))
        m.add(leg, rot, (math.sin(a) * 0.42, 0.0, math.cos(a) * 0.42))
    m.add(box(0.06, 0.65, 0.06, steel, center=(0.0, 1.50, 0.0)))
    head = Mesh()
    head.add(box(0.38, 0.24, 0.18, (26, 28, 32), center=(0.0, 0.0, 0.0)))
    head.add(box(0.30, 0.18, 0.04, lamp, center=(0.0, 0.0, -0.09), emissive=True))
    m.add(head, rot_y(yaw), (0.0, 1.86, 0.0))
    out = Mesh()
    out.add(m, t=(x, 0.0, z))
    return out


def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def _ridge_height(x, z, pad, eye):
    """Continuous Carpathian gorge terrain height:
    - Flat y = 0.0 inside the r <= 18 m evacuation clearing around ``pad``.
    - Steep pine-and-granite sniper ridge spur under ``eye`` plunging smoothly
      below the -15 deg sightline while cascading up the left/right valley flanks.
    - Smoothly rolling +22..+74 m Carpathian mountain walls framing the valley.
    """
    px, _, pz = pad
    ex, ey, ez = eye
    vx, vz = ex - px, ez - pz
    ln = math.hypot(vx, vz) or 1.0
    fx, fz = -vx / ln, -vz / ln
    rx_u, rz_u = fz, -fx

    dx_e, dz_e = x - ex, z - ez
    fwd = dx_e * fx + dz_e * fz
    lat = dx_e * rx_u + dz_e * rz_u
    r_pad = math.hypot(x - px, z - pz)
    if r_pad <= 18.0:
        return 0.0

    # Sniper ridge spur (crest around fwd <= 0.8, dropping sharply to 0 by fwd = 38.8)
    if fwd <= 0.8:
        u_back = _clamp((-fwd - 6.0) / 48.0, 0.0, 1.0)
        prof_fwd = 1.0 - 0.55 * (u_back * u_back)
    else:
        u_fwd = _clamp((fwd - 0.8) / 38.0, 0.0, 1.0)
        prof_fwd = (1.0 - u_fwd) ** 2.6
    u_lat = _clamp((abs(lat) - 8.0) / 58.0, 0.0, 1.0)
    prof_lat = max(0.0, 1.0 - u_lat * u_lat) ** 1.4
    spur_h = max(0.0, (ey - 0.85) * prof_fwd * prof_lat)

    # Gently curved gorge highway path behind the clearing: fwd_road(lat)
    road_fwd = 152.0 + 14.0 * math.sin(lat * 0.018 + 0.4)
    road_clear = _clamp((abs(fwd - road_fwd) - 7.5) / 16.0, 0.0, 1.0)

    # Smooth V-shaped valley walls rising on both flanks (starts right outside shooting lane)
    clear_k = _clamp((r_pad - 18.0) / 20.0, 0.0, 1.0)
    lane_half = 11.0 + 0.16 * max(0.0, min(fwd, 125.0))
    flank_u = _clamp((abs(lat) - lane_half) / 96.0, 0.0, 1.0)
    far_u = _clamp((fwd - road_fwd - 10.0) / 105.0, 0.0, 1.0)
    sight_clear = 1.0 if abs(lat) > 26.0 else _clamp((fwd - 136.0) / 36.0, 0.0, 1.0)
    wall_u = max(flank_u, far_u * sight_clear)
    wall_s = wall_u * wall_u * (3.0 - 2.0 * wall_u)
    undul = (6.5 * math.sin(x * 0.026 + 0.6) * math.cos(z * 0.024)
             + 3.5 * math.cos((x - z) * 0.038))
    gorge_h = max(0.0, (68.0 * (wall_s ** 1.25) + undul * wall_s) * clear_k * road_clear)

    # Gentle snowdrifts across the valley floor outside the clearing so it never reads flat
    drift_k = _clamp((r_pad - 20.0) / 18.0, 0.0, 1.0) * _clamp((fwd - 34.0) / 18.0, 0.0, 1.0)
    drifts = (0.75 + 0.65 * math.sin(x * 0.055) * math.cos(z * 0.052)) * drift_k * road_clear

    # Keep the secondary flank crash clearing (fwd ~ 70, lat ~ -46) low and open
    crash_d = math.hypot(fwd - 70.0, lat + 46.0)
    if crash_d < 16.0:
        gorge_h *= _clamp((crash_d - 6.0) / 10.0, 0.0, 1.0)
    return max(spur_h, gorge_h + drifts)


def _ridge_terrain_mesh(pad, eye):
    """Smoothly sampled Carpathian gorge heightfield with nocturnal snow/granite shading."""
    px, _, pz = pad
    m = Mesh()
    snow = tex("snow", like=(82, 96, 122), tint=True)
    snow_slope = tex("snow", like=(54, 66, 90), tint=True)
    rock = tex("ashlar", like=(26, 32, 44), tint=True)
    snow_clear = tex("snow_trod", like=(74, 86, 108), tint=True)

    # Smooth uniform 10 m grid across the active valley & ridge slopes (zero origami spikes)
    xs = [px + float(v) for v in range(-180, 181, 12)]
    zs = [pz + float(v) for v in range(-180, 181, 12)]
    pts = [[(x, _ridge_height(x, z, pad, eye), z) for x in xs] for z in zs]

    for iz in range(len(zs) - 1):
        for ix in range(len(xs) - 1):
            p00 = pts[iz][ix]
            p01 = pts[iz + 1][ix]
            p11 = pts[iz + 1][ix + 1]
            p10 = pts[iz][ix + 1]
            mx = 0.25 * (p00[0] + p01[0] + p11[0] + p10[0])
            mz = 0.25 * (p00[2] + p01[2] + p11[2] + p10[2])
            dy = max(p00[1], p01[1], p11[1], p10[1]) - min(p00[1], p01[1], p11[1], p10[1])
            span = max(xs[ix + 1] - xs[ix], zs[iz + 1] - zs[iz])
            slope = dy / max(1.0, span)
            if math.hypot(mx - px, mz - pz) <= 14.0:
                col = snow_clear
            elif slope >= 0.48:
                col = rock
            elif slope >= 0.22:
                col = snow_slope
            else:
                col = snow
            m.face([p00, p01, p11], col, layer=0)
            m.face([p00, p11, p10], col, layer=0)
    return m


def _wire_span(m, a, b, thick, col):
    """3D tensioned overhead power line between two world points."""
    from engine3d.core import m_mul
    dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    ln = math.sqrt(dx * dx + dy * dy + dz * dz)
    if ln < 1e-3:
        return
    yaw = math.degrees(math.atan2(dx, dz))
    pitch = math.degrees(math.atan2(dy, max(1e-4, math.hypot(dx, dz))))
    mid = (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]), 0.5 * (a[2] + b[2]))
    m.add(box(thick, thick, ln, col), m_mul(rot_y(yaw), rot_x(-pitch)), mid)


def _gorge_pylon(h=25.0):
    """Local-space high-voltage Carpathian A-frame lattice transmission pylon."""
    p = Mesh()
    steel = (44, 50, 62)
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            _wire_span(p, (sx * 2.4, 0.0, sz * 1.8), (sx * 0.65, h, sz * 0.55), 0.34, steel)
    for y_ring in (6.5, 13.0, 19.0):
        w = 4.6 * (1.0 - 0.68 * (y_ring / h))
        d = 3.4 * (1.0 - 0.68 * (y_ring / h))
        p.add(box(w, 0.30, d, steel, center=(0.0, y_ring, 0.0)))
    p.add(box(10.6, 0.48, 0.52, steel, center=(0.0, h - 4.2, 0.0)))
    p.add(box(7.8, 0.42, 0.46, steel, center=(0.0, h - 1.0, 0.0)))
    p.add(box(0.65, 0.65, 0.65, (242, 54, 42), center=(0.0, h + 0.45, 0.0), emissive=True))
    return p


def ridge_forest(pad, eye):
    """Contoured Northern Ridge Gorge clearing around ``pad`` with crash trench,
    gorge highway & power pylons, flank crash-site glow, grounded granite sniper
    perch at ``eye``, and 360-deg Carpathian mountain perimeter."""
    key = ("ridge_forest", int(pad[0]), int(pad[2]), int(eye[0]), int(eye[2]))
    m = _CACHE.get(key)
    if m is not None:
        return m
    m = _CACHE[key] = Mesh()
    px, _, pz = pad
    ex, ey, ez = eye
    vx, vz = ex - px, ez - pz
    ln = math.hypot(vx, vz) or 1.0
    vx, vz = vx / ln, vz / ln
    # Left-handed horizontal forward/right basis from EYE toward PAD
    fx, fz = -vx, -vz
    rx_u, rz_u = fz, -fx
    rng = random.Random(8490)
    snow = tex("snow", like=(88, 102, 128), tint=True)
    snow_hi = tex("snow", like=(122, 138, 166), tint=True)
    asphalt = tex("pavement", like=(34, 38, 46), tint=True)
    gravel = tex("m7_gravel", like=(48, 52, 60), tint=True)
    dirt = W7._t("dirt", (34, 28, 24))
    scorch = tex("scorch", like=(16, 15, 18))
    rock = tex("ashlar", like=(36, 42, 54), tint=True)
    rock_dark = tex("ashlar", like=(22, 26, 36), tint=True)
    bark = tex("m7_bark", like=(28, 21, 17), tint=True)
    timber = tex("m7_plank", like=(46, 36, 28), tint=True)
    olive = (54, 62, 46)
    sandbag = (118, 108, 88)
    steel = (44, 48, 54)
    rail_c = (62, 68, 76)
    ridge_col = (9, 14, 24)
    ridge_far = (14, 19, 30)

    # Contoured gorge terrain (flat y=0 at PAD, steep spur at EYE, rising walls around)
    m.add(_ridge_terrain_mesh(pad, eye))

    # Organic snow-cleared evacuation apron (octagonal frozen gravel + weathered asphalt center)
    m.add(disc_xz(px, pz + 1.0, 13.8, 0.018, gravel, n=12, layer=1))
    m.add(disc_xz(px, pz + 1.5, 9.6, 0.024, asphalt, n=10, layer=1))
    pad_col = (112, 110, 96)
    for sx in (-4.8, 4.8):
        m.add(box(0.20, 0.012, 8.2, pad_col, center=(px + sx, 0.030, pz + 1.8)))
    for sz in (-2.4, 6.0):
        m.add(box(8.4, 0.012, 0.20, pad_col, center=(px, 0.030, pz + sz)))

    # Subtle flat scorch skid mark trailing into the downed VIP helicopter at (+9.4, -3.6)
    # (strictly clear of PRES_AT=(+2.6,-1.0) and UCILEV_AT=(+1.67,-1.59) - zero white curb walls)
    trench = Mesh()
    trench.add(quad_xz(-1.8, -5.8, 1.8, 3.0, 0.028, dirt, layer=1, seg=3.0))
    trench.add(quad_xz(-1.2, -4.4, 1.2, 2.4, 0.034, scorch, layer=1, seg=2.5))
    m.add(trench, rot_y(225.0), (px + 11.6, 0.0, pz - 1.6))

    # Sheared helicopter rotor blade & charred cowling panel beside the wreck
    m.add(box(0.22, 0.06, 3.8, (22, 24, 28)), rot_y(24.0), (px + 6.4, 0.07, pz + 1.2))
    m.add(box(0.85, 0.22, 1.35, (24, 26, 30)), rot_y(-18.0), (px + 12.2, 0.11, pz - 0.4))

    # Tactical crates, sandbag cover, and field radio box near the evac site
    for cx_o, cz_o, yw in ((-3.4, 2.0, 16.0), (-2.6, 2.5, 12.0), (5.2, 3.6, -24.0)):
        m.add(box(0.92, 0.56, 0.62, olive, center=(0.0, 0.28, 0.0)), rot_y(yw), (px + cx_o, 0.0, pz + cz_o))
    for i in range(3):
        m.add(box(1.6, 0.34, 0.48, sandbag, center=(0.0, 0.17 + i * 0.28, 0.0)),
              rot_y(32.0), (px - 5.4, 0.0, pz + 0.6 + i * 0.05))
    m.add(box(0.58, 0.44, 0.44, olive, center=(px + 3.8, 0.22, pz + 0.2)))
    m.add(box(0.32, 0.26, 0.22, steel, center=(px + 3.8, 0.57, pz + 0.2)))

    # 4 physical tripod floodlight stands (placed wide of Ucilev's silhouette)
    for lx, lz in ((-7.8, -2.0), (10.4, -9.2), (-8.0, 9.6), (9.8, 9.2)):
        m.add(_tripod_light(px + lx, pz + lz, yaw=_yaw_to_2d(px + lx, pz + lz, px, pz)))

    # Small red emergency flares along the pad edge
    for fx_o, fz_o in ((-4.2, -4.8), (4.6, 5.0)):
        m.add(box(0.08, 0.22, 0.08, (180, 34, 28), center=(px + fx_o, 0.11, pz + fz_o)))
        m.add(box(0.09, 0.08, 0.09, (255, 110, 60), center=(px + fx_o, 0.24, pz + fz_o), emissive=True))

    # Curved Route 12 / Northern Gorge mountain highway winding past the far valley floor
    n_rseg = 18
    for si in range(n_rseg):
        l0 = -150.0 + 300.0 * si / n_rseg
        l1 = -150.0 + 300.0 * (si + 1) / n_rseg
        f0 = 152.0 + 14.0 * math.sin(l0 * 0.018 + 0.4)
        f1 = 152.0 + 14.0 * math.sin(l1 * 0.018 + 0.4)
        ax0, az0 = ex + fx * f0 + rx_u * l0, ez + fz * f0 + rz_u * l0
        ax1, az1 = ex + fx * f1 + rx_u * l1, ez + fz * f1 + rz_u * l1
        # Road ribbon (left-handed upward quad)
        w_h = 5.2
        p00 = (ax0 - fx * w_h, _ridge_height(ax0 - fx * w_h, az0 - fz * w_h, pad, eye) + 0.07, az0 - fz * w_h)
        p01 = (ax0 + fx * w_h, _ridge_height(ax0 + fx * w_h, az0 + fz * w_h, pad, eye) + 0.07, az0 + fz * w_h)
        p11 = (ax1 + fx * w_h, _ridge_height(ax1 + fx * w_h, az1 + fz * w_h, pad, eye) + 0.07, az1 + fz * w_h)
        p10 = (ax1 - fx * w_h, _ridge_height(ax1 - fx * w_h, az1 - fz * w_h, pad, eye) + 0.07, az1 - fz * w_h)
        m.face([p00, p01, p11, p10], asphalt, layer=1)
        # Guardrail posts along the near shoulder
        _wire_span(m, (p00[0], p00[1] + 0.45, p00[2]), (p10[0], p10[1] + 0.45, p10[2]), 0.22, rail_c)
        if si % 4 == 1:
            ly_p = p00[1]
            m.add(box(0.20, 7.2, 0.20, (36, 40, 48), center=(p00[0] - fx * 0.9, ly_p + 3.6, p00[2] - fz * 0.9)))
            m.add(box(0.55, 0.14, 0.28, (255, 194, 114),
                      center=(p00[0] + fx * 0.3, ly_p + 7.1, p00[2] + fz * 0.3), emissive=True))

    # Properly oriented high-voltage gorge power pylons + overhead transmission lines
    road_yaw = math.degrees(math.atan2(rx_u, rz_u))
    pylon_m = _gorge_pylon(26.0)
    pylon_tops = []
    for lat_p in (-76.0, 8.0, 92.0):
        f_p = 172.0 + 14.0 * math.sin(lat_p * 0.018 + 0.4)
        px_p = ex + fx * f_p + rx_u * lat_p
        pz_p = ez + fz * f_p + rz_u * lat_p
        py_p = _ridge_height(px_p, pz_p, pad, eye)
        m.add(pylon_m, rot_y(road_yaw), (px_p, py_p - 0.4, pz_p))
        pylon_tops.append((px_p, py_p + 21.4, pz_p))
    for pa, pb in zip(pylon_tops, pylon_tops[1:]):
        for off in (-3.2, 3.2):
            a = (pa[0] + fx * off, pa[1], pa[2] + fz * off)
            b = (pb[0] + fx * off, pb[1], pb[2] + fz * off)
            mid = (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]) - 2.6, 0.5 * (a[2] + b[2]))
            _wire_span(m, a, mid, 0.10, (54, 60, 72))
            _wire_span(m, mid, b, 0.10, (54, 60, 72))

    # Flank crash clearing scar (fwd=70, lat=-46) tying back to Maru's wreck across the spur
    mc_x = ex + fx * 70.0 - rx_u * 46.0
    mc_z = ez + fz * 70.0 - rz_u * 46.0
    mc_y = _ridge_height(mc_x, mc_z, pad, eye)
    m.add(quad_xz(mc_x - 5.5, mc_z - 5.5, mc_x + 5.5, mc_z + 5.5, mc_y + 0.08, scorch, layer=1, seg=3.0))
    m.add(box(1.8, 1.1, 4.4, (22, 22, 26)), rot_y(36.0), (mc_x, mc_y + 0.65, mc_z))

    # Granite crag outcrops breaking up the valley walls & lower clearing perimeter
    for i in range(22):
        d_fwd = rng.uniform(22.0, 145.0)
        side = -1.0 if (i % 2 == 0) else 1.0
        min_lat = 12.5 + 0.18 * d_fwd
        d_lat = side * rng.uniform(min_lat, min_lat + 32.0)
        gx = ex + fx * d_fwd + rx_u * d_lat
        gz = ez + fz * d_fwd + rz_u * d_lat
        gy = _ridge_height(gx, gz, pad, eye)
        rw, rh = rng.uniform(2.6, 5.2), rng.uniform(1.8, 3.8)
        m.add(W7._bipyr(gx, gy - 0.5, gz, rw, rh, 0.6, rock, n=6))
        m.add(W7._bipyr(gx, gy + rh * 0.38, gz, rw * 0.72, rh * 0.38, 0.12, snow_hi, n=6))

    # Dense dark Carpathian spruces carpeting the valley walls & mountain flanks
    # (strictly clear of the PAD clearing & EYE->PAD shooting funnel)
    for i in range(132):
        ang = math.tau * i / 132.0 + rng.uniform(-0.04, 0.04)
        rad = rng.uniform(20.0, 138.0)
        tx = px + math.cos(ang) * rad
        tz = pz + math.sin(ang) * rad
        d_fwd = (tx - ex) * fx + (tz - ez) * fz
        d_lat = abs((tx - ex) * rx_u + (tz - ez) * rz_u)
        lane = 11.5 + 0.17 * max(0.0, min(d_fwd, 125.0))
        if d_fwd < 146.0 and d_lat < lane:
            continue
        if 110.0 <= d_fwd <= 165.0 and d_lat < 20.0:
            continue  # keep far background directly behind PAD open so no tree blocks the clearing
        if math.hypot(d_fwd - 70.0, (tx - ex) * rx_u + (tz - ez) * rz_u + 46.0) < 9.0:
            continue
        road_f = 152.0 + 14.0 * math.sin(((tx - ex) * rx_u + (tz - ez) * rz_u) * 0.018 + 0.4)
        if abs(d_fwd - road_f) < 8.5:
            continue
        ty = _ridge_height(tx, tz, pad, eye)
        m.add(_snow_pine(1200 + i, rng.uniform(11.5, 21.0)), rot_y(rng.uniform(0.0, 360.0)), (tx, ty - 0.4, tz))

    # Organic jagged Carpathian granite sniper notch around EYE:
    # - Center firing notch dips to -28.1 deg (7.5 deg BELOW the x4 scope rim, zero bar in lens!)
    # - Rugged snow-dusted granite cheek outcrops & overhanging spruce boughs sit at +-20..26 deg
    #   horizontal: cleanly INSIDE the 54-deg peripheral view and OUTSIDE the +-16 deg scope tube.
    ledge_yaw = math.degrees(math.atan2(fx, fz))
    ledge = Mesh()
    pine_fg = tex("m7_leaf", like=(12, 24, 18), tint=True)
    # Low uneven granite rock sill across the bottom of the firing notch (-28..-32 deg)
    for rx_o, rz_o, rw, rh, snow_k in (
        (-0.52, 2.45, 0.72, 0.42, 0.72),
        (0.05, 2.52, 0.68, 0.36, 0.68),
        (0.58, 2.42, 0.74, 0.44, 0.74),
    ):
        ledge.add(W7._bipyr(rx_o, -1.56, rz_o, rw, rh, 0.45, rock_dark, n=6))
        ledge.add(W7._bipyr(rx_o, -1.56 + rh * 0.62, rz_o, rw * snow_k, rh * 0.30, 0.08, snow_hi, n=6))
    # Rolled dark olive canvas rifle rest tucked low in the notch (-29 deg)
    ledge.add(box(0.36, 0.10, 0.22, (36, 42, 34)), rot_y(11.0), (0.04, -1.24, 2.25))
    # Rugged flanking granite cheek crags & broken snow-crusted spruce boughs framing left/right sides
    for side in (-1.0, 1.0):
        # Near crag cluster (z=2.6..3.2, lat=+-1.12..1.55 -> +-22..26 deg horizontal)
        ledge.add(W7._bipyr(side * 1.18, -1.55, 2.65, 0.74, 0.95, 0.55, rock, n=6))
        ledge.add(W7._bipyr(side * 1.18, -0.88, 2.65, 0.56, 0.28, 0.10, snow_hi, n=6))
        ledge.add(W7._bipyr(side * 1.56, -1.45, 3.35, 0.95, 1.15, 0.60, rock_dark, n=6))
        ledge.add(W7._bipyr(side * 1.56, -0.62, 3.35, 0.68, 0.30, 0.10, snow_hi, n=6))
        # Mid granite shoulder dropping down the cliff lip (z=4.8, lat=+-2.15 -> +-24 deg)
        ledge.add(W7._bipyr(side * 2.15, -1.85, 4.80, 1.35, 1.40, 0.70, rock, n=6))
        ledge.add(W7._bipyr(side * 2.15, -0.82, 4.80, 0.92, 0.36, 0.12, snow_hi, n=6))
        # Leaning dark weathered spruce trunk & low evergreen bough tufts on the outer flanks
        ledge.add(box(0.18, 2.6, 0.18, bark), rot_z(side * -14.0), (side * 2.25, -0.95, 4.35))
        for bi, (by_o, br) in enumerate(((-0.75, 0.78), (-0.18, 0.64), (0.34, 0.48))):
            ledge.add(W7._bipyr(side * 2.08, by_o, 4.25, br, 0.44, 0.14, pine_fg, n=6))
            ledge.add(W7._bipyr(side * 2.08, by_o + 0.14, 4.25, br * 0.72, 0.14, 0.04, snow_hi, n=6))
    # One broken weathered wooden snow-fence post tilted into the left granite shoulder
    ledge.add(box(0.13, 1.25, 0.13, timber), rot_z(16.0), (-1.42, -0.92, 3.05))
    m.add(ledge, rot_y(ledge_yaw), (ex, ey, ez))

    # Flanking foreground & cascading mid-slope spruces creating a natural Carpathian canyon funnel
    for side in (-1.0, 1.0):
        for k, (d_fwd, d_lat, th, y_bias) in enumerate((
            (6.8, 3.9, 8.5, -1.2), (11.5, 6.4, 10.5, -0.5),
            (19.0, 9.8, 12.5, -0.4), (30.0, 13.2, 14.0, -0.4),
            (44.0, 16.5, 15.0, -0.4), (60.0, 19.5, 15.5, -0.4),
            (78.0, 23.0, 16.5, -0.4), (96.0, 27.0, 17.0, -0.4),
        )):
            ptx = ex + fx * d_fwd + rx_u * (side * d_lat)
            ptz = ez + fz * d_fwd + rz_u * (side * d_lat)
            pty = _ridge_height(ptx, ptz, pad, eye)
            m.add(_snow_pine(1600 + k * 2 + (1 if side > 0 else 0), th),
                  rot_y(k * 47.0), (ptx, pty + y_bias, ptz))

    # Layered 360-degree Carpathian mountain horizon perimeter (zero flat horizon leak)
    for r_ring, base_h, amp_a, amp_b, rcol in (
        (205.0, 46.0, 18.0, 11.0, ridge_col),
        (262.0, 86.0, 26.0, 16.0, ridge_far),
    ):
        n_seg = 32
        for i in range(n_seg):
            a0, a1 = math.tau * i / float(n_seg), math.tau * (i + 1) / float(n_seg)
            x0, z0 = px + math.sin(a0) * r_ring, pz + math.cos(a0) * r_ring
            x1, z1 = px + math.sin(a1) * r_ring, pz + math.cos(a1) * r_ring
            h0 = base_h + amp_a * math.sin(i * 1.7) + amp_b * math.cos(i * 2.9)
            h1 = base_h + amp_a * math.sin((i + 1) * 1.7) + amp_b * math.cos((i + 1) * 2.9)
            m.face([(x0, -4.0, z0), (x1, -4.0, z1), (x1, h1, z1), (x0, h0, z0)],
                   rcol, layer=0, double=True)
    return m


def _yaw_to_2d(ax, az, bx, bz):
    return math.degrees(math.atan2(bx - ax, bz - az)) % 360.0


def ridge_renderer(pad, eye, size=(640, 448)):
    """Dedicated cached Renderer with the snowy Carpathian ridge baked statically once."""
    key = ("ridge_r", int(pad[0]), int(pad[2]))
    r = _CACHE.get(key)
    if r is not None:
        return r
    from engine3d import Renderer
    r = Renderer(size[0], size[1], fog=(10, 14, 24), fog_start=52.0, fog_end=250.0)
    r.light = Light(direction=(-0.38, 0.56, -0.68), ambient=0.17, diffuse=0.42,
                    sky=0.11, tint=(0.68, 0.80, 1.0))
    r.bake(ridge_forest(pad, eye))
    _CACHE[key] = r
    return r


def ridge_frame(pad, eye, tgt, fov, t=0, size=(640, 448), lights=(), pools=(), roll=0.0):
    """Set sniper scope camera, cold Carpathian sky, fog, and pad lights."""
    r = ridge_renderer(pad, eye, size)
    r.resize(size[0], size[1])
    r.hdr = False
    r.set_camera(eye, tgt, fov, roll)
    r.fog, r.fog_start, r.fog_end = (10, 14, 24), 52.0, 250.0
    r.light = Light(direction=(-0.38, 0.56, -0.68), ambient=0.17, diffuse=0.42,
                    sky=0.11, tint=(0.68, 0.80, 1.0))
    try:
        r.set_lights(list(lights))
        r.set_pools(list(pools))
    except Exception:
        pass
    W7.sky(r, r.surface, t, "raid")
    r.begin()
    r.add_static()
    return r
