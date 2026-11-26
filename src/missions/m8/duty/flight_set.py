"""Mission 8 Duty - Dedicated night aerial chase corridor for Last Flight.

Baked once and frustum-culled (GL auto-slices into 32 m XZ chunks). Runs
z = -160 .. 5800 m across four distinct night zones with a 360-deg horizon ring:
  1. Curfew Boulevard (z -160..1120): curved wet 4-lane avenue, paved sidewalks,
     stranded trams, tram catenary portals, deep +-260 m cross-streets, stalled
     convoys, multi-tier brutalist blocks out to +-280 m, industrial silhouettes.
  2. The Radio Station (z 1120..2220): highway flyover with entry/exit ramps,
     fortified Broadcast Plaza completely wrapped by ministries & Tier 2-4 skyline,
     concrete bunkers, armored trucks, microwave dishes, guy-wired 88 m lattice
     tower, and gradual industrial/rail-yard transition (z 1980..2240) to Route 12.
  3. Route 12 Highway (z 2220..3360): Carpathian valley highway flanked by continuous
     spruce-topped foothills (+-65..380 m), parallel electrified railway, roadside
     poplars, village cottages, lit fuel depot (z 2420), expanded Toll Plaza (z 2680),
     high-voltage substation (z 2920), and mountain-approach viaduct (z 3160).
  4. Northern Ridge Gorge (z 3360..5800): steep +45..108 m canyon walls, Retardovici's
     burning crash clearing, Iron Gorge trestle bridge, ridge relay outpost,
     cliff-shelf power pylons, terraced spruces, and an alpine basin past z 5220.
"""
import math
import random

from cutscenes import fire3d as F3D
from cutscenes import m6fx3d as _fx
from cutscenes import m7world3d as W7
from engine3d import Mesh, box
from engine3d.core import Light, m_apply, m_mul, rot_x, rot_y, rot_z, v_add
from engine3d.textures import tex

RES = (720, 504)
FOG = (12, 17, 30)
FOG_START = 100.0
FOG_END = 375.0
_HORIZON_BIAS = 300.0

_CACHE = {}


def corridor_x(z):
    """Smooth sweeping S-curve avenue/highway centreline."""
    return 18.0 * math.sin(z / 210.0) + 8.0 * math.sin(z / 92.0 + 0.9)


def corridor_yaw(z):
    """Tangent heading in degrees along the corridor."""
    dx = corridor_x(z + 2.0) - corridor_x(z - 2.0)
    return math.degrees(math.atan2(dx, 4.0))


def surface_y(x, z):
    """Ground height: flat in the urban core, continuous rising foothills on
    Route 12, and steep +45..95 m canyon walls in the Northern Ridge gorge."""
    if z <= 2040.0:
        return 0.0
    dx = abs(x - corridor_x(z))
    if z <= 2220.0:
        # Gradual suburban outskirts rise on outer flanks
        tu = (z - 2040.0) / 180.0
        if dx > 55.0:
            fu = min(1.0, (dx - 55.0) / 220.0)
            return 22.0 * tu * fu * fu
        return 0.0
    if z <= 3360.0:
        # Route 12 valley: roadbed climbs gently toward the pass while foothills rise on both flanks
        ru = max(0.0, (z - 2220.0) / 1140.0)
        base = 4.0 * ru * ru
        if dx > 34.0:
            fu = min(1.0, (dx - 34.0) / 210.0)
            hill = (28.0 + 22.0 * ru) * (fu ** 1.45)
            ridge_wobble = 4.5 * math.sin(z * 0.025 + dx * 0.04) * fu
            return base + max(0.0, hill + ridge_wobble)
        return base
    # Northern Ridge Gorge (z > 3360): steep canyon walls rising +45..108 m above the roadbed,
    # opening gently into a pine-rimmed alpine basin around z=5280..5550 so orbits stay clear.
    u = min(1.0, (z - 3360.0) / 1800.0)
    base = 4.0 + 20.0 * u * u
    b_in = max(0.0, min(1.0, (z - 5180.0) / 130.0))
    b_out = max(0.0, min(1.0, (z - 5550.0) / 160.0))
    basin_u = b_in * (1.0 - b_out)
    wall_start = 52.0 + 68.0 * basin_u
    if dx > wall_start:
        fu = min(1.0, (dx - wall_start) / 145.0)
        wall_h = (64.0 + 44.0 * u) * (fu ** 1.15)
        crag = 7.5 * math.sin(z * 0.024 + dx * 0.038) * fu
        return base + max(0.0, wall_h + crag)
    return base


def _ribbon(m, z0, z1, off_l, off_r, col, y_off=0.0, layer=1, emissive=False, seg_x=1):
    """Curve-following watertight ground/road strip with +Y upward winding."""
    cx0, cx1 = corridor_x(z0), corridor_x(z1)
    n = max(1, int(seg_x))
    step = (off_r - off_l) / n
    for i in range(n):
        a = off_l + i * step
        b = a + step
        x00, x10 = cx0 + a, cx0 + b
        x01, x11 = cx1 + a, cx1 + b
        p00 = (x00, surface_y(x00, z0) + y_off, z0)
        p01 = (x01, surface_y(x01, z1) + y_off, z1)
        p11 = (x11, surface_y(x11, z1) + y_off, z1)
        p10 = (x10, surface_y(x10, z0) + y_off, z0)
        m.face([p00, p01, p11, p10], col, layer=layer, emissive=emissive)


def _curve_beam(m, z0, z1, off, w, h, col, y_off=0.0, emissive=False):
    """Curve-aligned 3D kerb, median, rail, or tram track running from z0 to z1."""
    x0, x1 = corridor_x(z0) + off, corridor_x(z1) + off
    y0, y1 = surface_y(x0, z0) + y_off, surface_y(x1, z1) + y_off
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    ln = math.sqrt(dx * dx + dy * dy + dz * dz) + 0.14
    yaw = math.degrees(math.atan2(dx, dz))
    pitch = math.degrees(math.atan2(dy, max(1e-4, math.hypot(dx, dz))))
    mid = (0.5 * (x0 + x1), 0.5 * (y0 + y1) + h * 0.5, 0.5 * (z0 + z1))
    mat = rot_y(yaw) if abs(pitch) < 0.05 else m_mul(rot_y(yaw), rot_x(-pitch))
    m.add(box(w, h, ln, col, emissive=emissive), mat, mid)


def _wire_beam(m, a, b, thick, col):
    """3D tensioned guy-wire or structural strut between two 3D points."""
    dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    ln = math.sqrt(dx * dx + dy * dy + dz * dz)
    if ln < 1e-3:
        return
    yaw = math.degrees(math.atan2(dx, dz))
    pitch = math.degrees(math.atan2(dy, max(1e-4, math.hypot(dx, dz))))
    mid = (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]), 0.5 * (a[2] + b[2]))
    m.add(box(thick, thick, ln, col), m_mul(rot_y(yaw), rot_x(-pitch)), mid)


def _add_tram_car(m, x, z, yaw):
    """Stranded Eastern-bloc articulated crimson/cream tram car on the center rails."""
    t = Mesh()
    crimson = (118, 32, 34)
    cream = (182, 176, 158)
    dark = (26, 28, 34)
    steel = (72, 76, 84)
    win_glow = (232, 184, 106)
    # Bogie chassis + lower crimson skirt + upper cream window band + roof
    t.add(box(2.35, 0.55, 13.4, dark, center=(0.0, 0.42, 0.0)))
    t.add(box(2.50, 1.15, 13.8, crimson, center=(0.0, 1.25, 0.0)))
    t.add(box(2.46, 1.10, 13.6, cream, center=(0.0, 2.35, 0.0)))
    t.add(box(2.30, 0.24, 13.2, (52, 56, 62), center=(0.0, 3.02, 0.0)))
    # Dim emergency-lit tram windows along both flanks + head/tail lamps
    for sx in (-1.25, 1.25):
        for wz in (-4.8, -2.4, 0.0, 2.4, 4.8):
            col = win_glow if (int(abs(wz * 10)) % 4 != 0) else (28, 34, 44)
            t.add(box(0.06, 0.76, 1.75, col, center=(sx, 2.35, wz), emissive=(col == win_glow)))
    for sz, lcol in ((6.92, (244, 212, 142)), (-6.92, (218, 48, 38))):
        for lx in (-0.75, 0.75):
            t.add(box(0.26, 0.22, 0.08, lcol, center=(lx, 1.05, sz), emissive=True))
    # Overhead pantograph frame reaching toward the catenary wire
    t.add(box(1.4, 0.12, 1.8, steel, center=(0.0, 3.22, 1.2)))
    t.add(box(0.08, 1.85, 0.08, steel), m=rot_x(28.0), t=(0.0, 4.0, 0.8))
    t.add(box(0.08, 1.85, 0.08, steel), m=rot_x(-28.0), t=(0.0, 4.0, 1.6))
    t.add(box(1.65, 0.08, 0.12, steel, center=(0.0, 4.85, 1.2)))
    m.add(t, rot_y(yaw), (x, 0.0, z))


def _add_building(m, x, z, w, h, d, wall_col, rng, beacons, roofs, side,
                  allow_roof=True, tier=1, detailed=True):
    """Eastern-bloc brutalist apartment/ministry block with 4-sided lit windows,
    stairwell shafts, balcony ribs, ground-floor plinth, and rooftop silhouette."""
    wall = tex("stucco", like=wall_col, tint=True, density=48.0)
    stone = tex("ashlar", like=(68, 70, 76), tint=True, density=32.0)
    roof_c = tex("concrete", like=(38, 42, 48), tint=True)
    trim_c = (54, 58, 66)
    steel_c = (72, 78, 86)
    seed_h = int(abs(x * 3 + z * 5))
    y0 = surface_y(x, z)

    # Main mass + heavier ground-floor stone plinth + stepped cornice parapet
    m.add(box(w, h, d, wall, center=(x, y0 + h * 0.5, z)))
    if tier == 1:
        m.add(box(w + 0.6, 3.6, d + 0.6, stone, center=(x, y0 + 1.8, z)))
        face_s = x - side * (w * 0.5 + 0.34)
        for ci in range(max(2, int(d // 6.0))):
            wz = z - d * 0.5 + 3.2 + ci * ((d - 6.4) / max(1, int(d // 6.0) - 1))
            if (ci + int(abs(z))) % 3 != 0:
                col = (242, 178, 96) if (ci % 2 == 0) else (134, 184, 214)
                m.add(box(0.08, 1.9, 2.8, col, center=(face_s, y0 + 1.7, wz), emissive=True))
    else:
        m.add(box(w + 0.3, 2.2, d + 0.3, stone, center=(x, y0 + 1.1, z)))
    m.add(box(w + 0.7, 0.75, d + 0.7, roof_c, center=(x, y0 + h + 0.38, z)))

    # Horizontal floor/balcony bands on Tier-1 streetfront blocks
    if tier == 1 and detailed:
        face_s = x - side * (w * 0.5 + 0.35)
        for by in range(7, int(h - 2), 7):
            m.add(box(0.65, 0.28, d * 0.86, trim_c, center=(face_s, y0 + float(by), z)))
        sw_col = (146, 206, 232) if rng.random() < 0.55 else (238, 188, 108)
        st_z = z + rng.uniform(-d * 0.22, d * 0.22)
        m.add(box(0.10, h - 4.8, 1.4, sw_col,
                  center=(x - side * (w * 0.5 + 0.05), y0 + 3.8 + (h - 4.8) * 0.5, st_z),
                  emissive=True))
        if seed_h % 4 == 0:
            sign_c = (232, 84, 58) if (seed_h % 8 == 0) else (88, 198, 224)
            m.add(box(0.18, 0.95, min(7.2, d * 0.42), sign_c,
                      center=(x - side * (w * 0.5 + 0.42), y0 + 4.2, z), emissive=True))

    # Rooftop penthouse / water tank / microwave dish array / antenna mast
    ry = y0 + h + 0.75
    if rng.random() < 0.78:
        pw, pd, ph = w * 0.34, d * 0.34, rng.uniform(2.0, 3.8)
        px_off = side * w * 0.16
        m.add(box(pw, ph, pd, roof_c, center=(x + px_off, ry + ph * 0.5, z)))
        if detailed and (seed_h % 3 == 0):
            # Rooftop water tank on steel stilts or microwave drum dish
            tx_r = x - px_off * 0.8
            tz_r = z + (d * 0.24 if (seed_h % 2 == 0) else -d * 0.24)
            m.add(box(0.9, 1.4, 0.9, steel_c, center=(tx_r, ry + 0.7, tz_r)))
            m.add(box(1.9, 2.1, 1.9, (58, 62, 68), center=(tx_r, ry + 2.3, tz_r)))
        if h >= 20.0:
            m.add(box(0.18, 4.6, 0.18, (96, 100, 108),
                      center=(x + px_off, ry + ph + 2.3, z)))
            if detailed:
                m.add(box(1.4, 0.12, 0.12, steel_c, center=(x + px_off, ry + ph + 3.4, z)))
            beacons.append((x + px_off, ry + ph + 4.7, z))
    elif h >= 26.0:
        beacons.append((x, ry + 0.6, z))

    if allow_roof and 13.0 <= h <= 26.5:
        roofs.append((x - side * (w * 0.34), ry, z, side))

    floors = max(3, int((h - 4.2) // 3.4))
    if detailed:
        cols_z = max(2, int(d // 4.2))
        face_x = x - side * (w * 0.5 + 0.05)
        for fl in range(floors):
            wy = y0 + 4.8 + fl * 3.4
            for ci in range(cols_z):
                wz = z - d * 0.5 + 2.4 + ci * ((d - 4.8) / max(1, cols_z - 1))
                hv = (fl * 13 + ci * 7 + seed_h) % 13
                if hv < 4:
                    col = (255, 202, 122) if hv != 2 else (142, 206, 246)
                    m.add(box(0.08, 1.45, 1.85, col, center=(face_x, wy, wz), emissive=True))
                elif hv < 8 and tier == 1:
                    m.add(box(0.08, 1.45, 1.85, (18, 22, 32), center=(face_x, wy, wz)))

        cols_x = max(2, int(w // 4.6))
        for z_dir in (-1.0, 1.0):
            if z_dir > 0 and tier >= 2:
                continue
            fz = z + z_dir * (d * 0.5 + 0.05)
            for fl in range(floors):
                wy = y0 + 4.8 + fl * 3.4
                for ci in range(cols_x):
                    wx = x - w * 0.5 + 2.4 + ci * ((w - 4.8) / max(1, cols_x - 1))
                    hv = (fl * 9 + ci * 5 + seed_h + int(z_dir > 0) * 3) % 11
                    if hv < 3:
                        col = (248, 192, 114) if hv != 1 else (136, 198, 236)
                        m.add(box(1.85, 1.45, 0.08, col, center=(wx, wy, fz), emissive=True))
    else:
        face_x = x - side * (w * 0.5 + 0.06)
        n_bands = 2 if tier >= 3 else 3
        for bi in range(n_bands):
            wy = y0 + 7.5 + bi * max(5.5, (h - 10.0) / max(1, n_bands))
            if wy < y0 + h - 2.0:
                col = (242, 184, 108) if ((bi + seed_h) % 3 != 0) else (128, 186, 226)
                m.add(box(0.10, 1.45, d * 0.68, col, center=(face_x, wy, z), emissive=True))
        if seed_h % 2 == 0 and h > 22.0:
            m.add(box(0.12, h - 7.0, 1.6, (236, 182, 104),
                      center=(face_x, y0 + 3.5 + (h - 7.0) * 0.5, z), emissive=True))


def _add_industrial_silhouette(m, x, z, side, rng, beacons):
    """Low-poly Eastern-bloc industrial factory hall, smokestack & gasholder behind Tier 3."""
    y0 = surface_y(x, z)
    hall_c = (28, 32, 42)
    stack_c = (36, 40, 50)
    band_c = (156, 48, 42)
    glow_c = (232, 158, 76)
    w, d, h = rng.uniform(28.0, 42.0), rng.uniform(32.0, 48.0), rng.uniform(14.0, 22.0)
    m.add(box(w, h, d, hall_c, center=(x, y0 + h * 0.5, z)))
    # Clerestory amber factory glass strip
    m.add(box(0.14, 1.6, d * 0.78, glow_c,
              center=(x - side * (w * 0.5 + 0.08), y0 + h * 0.72, z), emissive=True))
    # Tall tapered brick/concrete smokestack
    sx = x + side * (w * 0.25)
    sz = z + rng.uniform(-10.0, 10.0)
    sh = rng.uniform(48.0, 74.0)
    m.add(box(3.4, sh, 3.4, stack_c, center=(sx, y0 + sh * 0.5, sz)))
    m.add(box(3.7, 2.4, 3.7, band_c, center=(sx, y0 + sh - 5.0, sz)))
    m.add(box(3.7, 2.4, 3.7, band_c, center=(sx, y0 + sh - 12.0, sz)))
    beacons.append((sx, y0 + sh + 0.8, sz))


def _add_spruce(m, px, py, pz, h, bark, pine_a, pine_b, low_poly=False):
    """Dense Carpathian spruce; low_poly=True uses a 2-tier silhouette for far slopes."""
    if low_poly:
        m.add(W7._bipyr(px, py + h * 0.36, pz, h * 0.25, h * 0.54, h * 0.08, pine_a, n=4))
        m.add(W7._bipyr(px, py + h * 0.68, pz, h * 0.16, h * 0.36, h * 0.05, pine_b, n=4))
        return
    m.add(box(0.46, h * 0.28, 0.46, bark, center=(px, py + h * 0.14, pz)))
    for y_frac, rad_f, up_f, col in (
        (0.24, 0.24, 0.42, pine_a),
        (0.46, 0.19, 0.36, pine_b),
        (0.68, 0.13, 0.32, pine_a),
    ):
        m.add(W7._bipyr(px, py + h * y_frac, pz, h * rad_f, h * up_f, h * 0.06, col, n=6))


def _add_cliff_ridge(m, cx, base_y, cz, rx, rz, h, dark_col, rock_col, frost_col, rng, n=8):
    """Broad, rugged Carpathian granite cliff shoulder running parallel to the gorge wall.
    Deeply skirted into the rising mountainside with a wide irregular ridgeline (no pointy cones)."""
    ang0 = rng.uniform(0.0, math.tau)
    r_jit = [rng.uniform(0.82, 1.18) for _ in range(n)]
    h_jit1 = [rng.uniform(-4.5, 4.5) for _ in range(n)]
    h_jit2 = [rng.uniform(-3.0, 3.0) for _ in range(n)]
    y0 = base_y
    y1 = base_y + h * 0.56
    y2 = base_y + h * 0.88
    top = (cx + rng.uniform(-rx * 0.10, rx * 0.10),
           base_y + h + rng.uniform(1.0, 4.0),
           cz + rng.uniform(-rz * 0.12, rz * 0.12))
    ring0, ring1, ring2 = [], [], []
    for i in range(n):
        a = ang0 + math.tau * i / float(n)
        ca, sa = math.cos(a), math.sin(a)
        rj = r_jit[i]
        ring0.append((cx + ca * rx * rj, y0, cz + sa * rz * rj))
        ring1.append((cx + ca * rx * 0.74 * rj, y1 + h_jit1[i], cz + sa * rz * 0.78 * rj))
        ring2.append((cx + ca * rx * 0.34 * rj, y2 + h_jit2[i], cz + sa * rz * 0.44 * rj))
    for i in range(n):
        j = (i + 1) % n
        # Left-handed outward winding: [low_i, high_i, high_j, low_j] -> normal points outward
        m.face([ring0[i], ring1[i], ring1[j], ring0[j]], dark_col, layer=2)
        m.face([ring1[i], ring2[i], ring2[j], ring1[j]], rock_col, layer=2)
        m.face([ring2[i], top, ring2[j]], frost_col, layer=2)


def _add_valley_cottage(m, x, z, yaw):
    """Dark Carpathian valley cottage with pitched roof and tiny warm window lights."""
    y0 = surface_y(x, z)
    wall = tex("stucco", like=(54, 52, 50), tint=True)
    roof = tex("m7_tile", like=(38, 26, 24), tint=True)
    win = (244, 188, 102)
    c = Mesh()
    c.add(box(7.2, 3.4, 5.6, wall, center=(0.0, 1.7, 0.0)))
    c.add(box(7.8, 1.8, 6.2, roof, center=(0.0, 4.1, 0.0)))
    for sx in (-1.8, 1.8):
        c.add(box(0.95, 0.95, 0.10, win, center=(sx, 1.8, 2.84), emissive=True))
        c.add(box(0.95, 0.95, 0.10, win, center=(sx, 1.8, -2.84), emissive=True))
    m.add(c, rot_y(yaw), (x, y0 - 0.3, z))


def _urban_horizon_ring():
    """Cached 360-deg low-poly urban horizon silhouette ring (r ≈ 335-365 m) with
    brutalist apartment blocks, chimneys, cranes, and muted horizon haze."""
    m = _CACHE.get("horizon_urban")
    if m is not None:
        return m
    m = _CACHE["horizon_urban"] = Mesh()
    n_seg = 36
    r_base = 338.0
    r_back = 364.0
    sil_a = (15, 20, 32)
    sil_b = (19, 25, 38)
    haze_band = (54, 42, 34)
    for i in range(n_seg):
        a0 = math.tau * i / n_seg
        a1 = math.tau * (i + 1) / n_seg
        am = 0.5 * (a0 + a1)
        x0, z0 = math.sin(a0) * r_base, math.cos(a0) * r_base
        x1, z1 = math.sin(a1) * r_base, math.cos(a1) * r_base
        h_wall = 24.0 + (i * 11 % 22)
        m.face([(x0, -8.0, z0), (x1, -8.0, z1), (x1, h_wall, z1), (x0, h_wall, z0)],
               sil_a if i % 2 == 0 else sil_b, layer=0, double=True)
        # Outer taller monolith silhouette wall
        bx0, bz0 = math.sin(a0) * r_back, math.cos(a0) * r_back
        bx1, bz1 = math.sin(a1) * r_back, math.cos(a1) * r_back
        h_back = 38.0 + (i * 17 % 34)
        m.face([(bx0, -8.0, bz0), (bx1, -8.0, bz1), (bx1, h_back, bz1), (bx0, h_back, bz0)],
               sil_a, layer=0, double=True)
        # Subtle fog-blended sodium city horizon haze (non-emissive so cloud/distance fog hides it)
        gx0, gz0 = math.sin(a0) * (r_base - 3.0), math.cos(a0) * (r_base - 3.0)
        gx1, gz1 = math.sin(a1) * (r_base - 3.0), math.cos(a1) * (r_base - 3.0)
        m.face([(gx0, 0.0, gz0), (gx1, 0.0, gz1), (gx1, 6.5, gz1), (gx0, 6.5, gz0)],
               haze_band, layer=0, double=True)
        # Factory chimneys & tower cranes breaking the upper skyline
        xm, zm = math.sin(am) * (r_base + 6.0), math.cos(am) * (r_base + 6.0)
        yaw_s = math.degrees(am)
        if i % 4 == 0:
            ch = 64.0 + (i % 3) * 10.0
            m.add(box(4.2, ch, 4.2, sil_b, center=(xm, ch * 0.5, zm), layer=0))
        elif i % 4 == 2:
            # Tower crane mast + horizontal jib
            ch = 58.0 + (i % 3) * 8.0
            m.add(box(2.2, ch, 2.2, sil_b, center=(xm, ch * 0.5, zm), layer=0))
            m.add(box(28.0, 1.6, 1.6, sil_b, layer=0), rot_y(yaw_s + 25.0), (xm, ch - 2.0, zm))
    return m


def _mountain_horizon_ring():
    """Cached 360-deg low-poly Carpathian ridge ring (r ≈ 330-370 m) with layered
    dark pine-clad mountain peaks rising above the horizon line."""
    m = _CACHE.get("horizon_mountain")
    if m is not None:
        return m
    m = _CACHE["horizon_mountain"] = Mesh()
    n_seg = 36
    r_in = 332.0
    r_out = 366.0
    ridge_near = (11, 18, 22)
    ridge_far = (14, 20, 32)
    snow_crest = (38, 46, 62)
    for i in range(n_seg):
        a0 = math.tau * i / n_seg
        a1 = math.tau * (i + 1) / n_seg
        am = 0.5 * (a0 + a1)
        x0, z0 = math.sin(a0) * r_in, math.cos(a0) * r_in
        x1, z1 = math.sin(a1) * r_in, math.cos(a1) * r_in
        h0 = 46.0 + 18.0 * math.sin(i * 1.7) + 11.0 * math.cos(i * 2.9)
        h1 = 46.0 + 18.0 * math.sin((i + 1) * 1.7) + 11.0 * math.cos((i + 1) * 2.9)
        m.face([(x0, -12.0, z0), (x1, -12.0, z1), (x1, h1, z1), (x0, h0, z0)],
               ridge_near, layer=0, double=True)
        # Outer higher Carpathian summit ring
        ox0, oz0 = math.sin(a0) * r_out, math.cos(a0) * r_out
        ox1, oz1 = math.sin(a1) * r_out, math.cos(a1) * r_out
        oh0 = 76.0 + 26.0 * math.cos(i * 1.3 + 0.6) + 14.0 * math.sin(i * 2.3)
        oh1 = 76.0 + 26.0 * math.cos((i + 1) * 1.3 + 0.6) + 14.0 * math.sin((i + 1) * 2.3)
        m.face([(ox0, -12.0, oz0), (ox1, -12.0, oz1), (ox1, oh1, oz1), (ox0, oh0, oz0)],
               ridge_far, layer=0, double=True)
        # Jagged snow-dusted summit ridge cap on high peaks
        if oh0 > 84.0 or oh1 > 84.0:
            xm, zm = math.sin(am) * r_out, math.cos(am) * r_out
            peak_y = max(oh0, oh1) + 10.0
            m.face([(ox0, oh0 - 6.0, oz0), (ox1, oh1 - 6.0, oz1), (xm, peak_y, zm)],
                   snow_crest, layer=0, double=True)
    return m


def _submit_ring(r, key, mesh, pos):
    if hasattr(r, "add_packed"):
        pk = _CACHE.setdefault("ring_pack", {})
        rk = (id(r), key)
        rows = pk.get(rk)
        if rows is None:
            faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces]
            rows = pk[rk] = r.pack(mesh.verts, faces, bias=_HORIZON_BIAS)
        if rows is not None:
            import numpy as np
            out = rows.copy()
            out[:, 0:3] += np.asarray(pos, dtype=rows.dtype)
            r.add_packed(out)
            return
    verts = [(v[0] + pos[0], v[1] + pos[1], v[2] + pos[2]) for v in mesh.verts]
    r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces],
                  bias=_HORIZON_BIAS)


def draw_horizon_ring(r, hpos):
    """Submit camera-anchored 360-deg distant horizon silhouette ring(s) centered
    on (hpos[0], hpos[2]), cross-fading smoothly from urban to Carpathian ridge."""
    tag = (id(r), round(hpos[0], 1), round(hpos[2], 1))
    if _CACHE.get("_last_ring_tag") == tag:
        return
    _CACHE["_last_ring_tag"] = tag
    hx, _, hz = hpos
    gy = surface_y(corridor_x(hz), hz)
    if hz < 1740.0:
        _submit_ring(r, "horizon_urban", _urban_horizon_ring(), (hx, 0.0, hz))
    elif hz <= 2200.0:
        u = (hz - 1740.0) / 460.0
        u_e = u * u * (3.0 - 2.0 * u)
        _submit_ring(r, "horizon_urban", _urban_horizon_ring(), (hx, -64.0 * u_e, hz))
        _submit_ring(r, "horizon_mountain", _mountain_horizon_ring(), (hx, gy - 85.0 * (1.0 - u_e), hz))
    else:
        _submit_ring(r, "horizon_mountain", _mountain_horizon_ring(), (hx, gy * 0.65, hz))


def _build_corridor():
    rng = random.Random(8842)
    m = Mesh()
    lamps = []
    beacons = []
    fires = []
    roofs = []
    searchlights = []
    mist_spots = []

    try:
        from missions.m8.revenge import chase_set as _CS
        wreck_car = _CS._charred(_CS.jeep(), 0.78)
        guard_truck = _CS.gun_truck()
    except Exception:
        wreck_car = None
        guard_truck = None

    city_ground = tex("pavement", like=(34, 38, 48), tint=True)
    sidewalk_c = tex("ashlar", like=(68, 72, 82), tint=True)
    steppe_c = tex("m7_grass", like=(24, 32, 28), tint=True)
    foothill_c = tex("m7_grass", like=(13, 20, 17), tint=True)
    canyon_c = tex("ashlar", like=(20, 25, 34), tint=True)
    asphalt = tex("pavement", like=(46, 50, 60), tint=True)
    ballast_c = tex("m7_gravel", like=(42, 40, 38), tint=True)
    kerb = tex("concrete", like=(72, 76, 82), tint=True)
    rail_c = (86, 90, 96)
    lane_col = (194, 188, 166)
    amber_line = (212, 164, 78)
    pole_col = (40, 44, 52)
    lamp_glow = (255, 202, 126)
    bark = tex("m7_bark", like=(24, 19, 15), tint=True)
    pine_a = tex("m7_leaf", like=(11, 24, 17), tint=True)
    pine_b = tex("m7_leaf", like=(16, 30, 21), tint=True)
    rock_dark = tex("ashlar", like=(24, 28, 36), tint=True)
    rock_c = tex("ashlar", like=(32, 38, 48), tint=True)
    frost_c = tex("ashlar", like=(46, 54, 68), tint=True)
    hill_c = tex("m7_grass", like=(16, 24, 20), tint=True)

    # 1. Seamless curve-following ground out to +-460 m, sidewalks, roadbed, medians & rails
    z = -160.0
    while z < 5800.0:
        step_z = 20.0 if z < 3360.0 else 28.0
        z_next = min(5800.0, z + step_z)
        in_city = z < 2220.0
        on_hwy = 2220.0 <= z < 3360.0
        rw = 18.0 if in_city else (16.0 if on_hwy else 10.0)
        hw = rw * 0.5
        gcol_in = city_ground if in_city else (steppe_c if on_hwy else foothill_c)
        gcol_out = city_ground if in_city else (foothill_c if on_hwy else canyon_c)
        # Inner terrain ribbon (+-hw .. +-170 m) + wide coarse outer horizon skirt (+-170 .. +-460 m)
        _ribbon(m, z, z_next, -170.0, -hw, gcol_in, y_off=0.0, layer=0, seg_x=3 if not in_city else 1)
        _ribbon(m, z, z_next, hw, 170.0, gcol_in, y_off=0.0, layer=0, seg_x=3 if not in_city else 1)
        _ribbon(m, z, z_next, -460.0, -170.0, gcol_out, y_off=0.0, layer=0, seg_x=2 if not in_city else 1)
        _ribbon(m, z, z_next, 170.0, 460.0, gcol_out, y_off=0.0, layer=0, seg_x=2 if not in_city else 1)
        # Smooth continuous curved roadway
        _ribbon(m, z, z_next, -hw, hw, asphalt, y_off=0.06, layer=1, seg_x=1)
        if in_city:
            _ribbon(m, z, z_next, -hw - 13.0, -hw, sidewalk_c, y_off=0.14, layer=1, seg_x=1)
            _ribbon(m, z, z_next, hw, hw + 13.0, sidewalk_c, y_off=0.14, layer=1, seg_x=1)
            _curve_beam(m, z, z_next, -hw - 0.25, 0.50, 0.22, kerb, y_off=0.0)
            _curve_beam(m, z, z_next, hw + 0.25, 0.50, 0.22, kerb, y_off=0.0)
            # Center tram rails & double amber curfew lines
            _curve_beam(m, z, z_next, -1.15, 0.10, 0.04, rail_c, y_off=0.07)
            _curve_beam(m, z, z_next, 1.15, 0.10, 0.04, rail_c, y_off=0.07)
            _curve_beam(m, z, z_next, -0.32, 0.14, 0.03, amber_line, y_off=0.07)
            _curve_beam(m, z, z_next, 0.32, 0.14, 0.03, amber_line, y_off=0.07)
            if int(z // 20) % 2 == 0:
                for sx in (-1.0, 1.0):
                    _curve_beam(m, z + 3.0, z_next - 3.0, sx * 4.6, 0.16, 0.03, lane_col, y_off=0.07)
        elif on_hwy:
            # Divided Route 12 highway: concrete jersey median, steel guardrails, timbered verges
            _curve_beam(m, z, z_next, 0.0, 0.65, 0.78, kerb, y_off=0.05)
            for sx in (-1.0, 1.0):
                _curve_beam(m, z, z_next, sx * (hw + 0.55), 0.22, 0.62, rail_c, y_off=0.22)
                _curve_beam(m, z, z_next, sx * (hw - 0.45), 0.16, 0.03, lane_col, y_off=0.07)
                if int(z // 20) % 2 == 0:
                    _curve_beam(m, z + 3.0, z_next - 3.0, sx * 4.0, 0.16, 0.03, lane_col, y_off=0.07)
            # Parallel electrified railway track bed along the west valley shelf (off = -23.5 m)
            _ribbon(m, z, z_next, -26.5, -20.5, ballast_c, y_off=0.12, layer=1, seg_x=1)
            _curve_beam(m, z, z_next, -24.3, 0.12, 0.10, rail_c, y_off=0.16)
            _curve_beam(m, z, z_next, -22.7, 0.12, 0.10, rail_c, y_off=0.16)
        else:
            for sx in (-1.0, 1.0):
                _curve_beam(m, z, z_next, sx * (hw + 0.35), 0.24, 0.58, rail_c, y_off=0.18)
            if int(z // 28) % 2 == 0:
                _curve_beam(m, z + 4.0, z_next - 4.0, 0.0, 0.18, 0.03, amber_line, y_off=0.07)
        z = z_next

    # 2. Streetlamps (sidewalk poles in city, tall twin-arm median masts on Route 12)
    lz = -80.0
    while lz < 3320.0:
        cx = corridor_x(lz)
        if lz < 2220.0:
            for side in (-1.0, 1.0):
                px = cx + side * 10.4
                m.add(box(0.18, 6.8, 0.18, pole_col, center=(px, 3.4, lz)))
                m.add(box(1.7, 0.14, 0.18, pole_col, center=(px - side * 0.80, 6.8, lz)))
                m.add(box(0.62, 0.14, 0.28, lamp_glow, center=(px - side * 1.45, 6.72, lz), emissive=True))
                lamps.append((px - side * 1.45, 6.55, lz))
            lz += 42.0
        else:
            py_m = surface_y(cx, lz)
            m.add(box(0.22, 8.8, 0.22, pole_col, center=(cx, py_m + 4.4, lz)))
            m.add(box(3.8, 0.16, 0.18, pole_col, center=(cx, py_m + 8.8, lz)))
            for side in (-1.0, 1.0):
                m.add(box(0.66, 0.14, 0.30, lamp_glow, center=(cx + side * 1.7, py_m + 8.70, lz), emissive=True))
            lamps.append((cx, py_m + 8.5, lz))
            lz += 56.0

    # 3. Zone 1: Curfew Boulevard (z -120..1120) - deep +-260 m cross-streets, trams, convoys & 4 tiers
    block_cols = ((92, 94, 102), (84, 88, 98), (104, 98, 92), (76, 82, 92), (96, 92, 88))
    bz = -100.0
    cross_next = 140.0
    while bz < 1105.0:
        cx = corridor_x(bz)
        if bz >= cross_next:
            # Deep cross-street cutting laterally to +-260 m with receding Tier 2/3 blocks & sodium lamps
            _ribbon(m, bz - 6.5, bz + 6.5, -260.0, -9.0, asphalt, y_off=0.07, layer=1)
            _ribbon(m, bz - 6.5, bz + 6.5, 9.0, 260.0, asphalt, y_off=0.07, layer=1)
            _ribbon(m, bz - 11.5, bz - 6.5, -250.0, -18.0, sidewalk_c, y_off=0.13, layer=1)
            _ribbon(m, bz + 6.5, bz + 11.5, -250.0, -18.0, sidewalk_c, y_off=0.13, layer=1)
            _ribbon(m, bz - 11.5, bz - 6.5, 18.0, 250.0, sidewalk_c, y_off=0.13, layer=1)
            _ribbon(m, bz + 6.5, bz + 11.5, 18.0, 250.0, sidewalk_c, y_off=0.13, layer=1)
            for side in (-1.0, 1.0):
                for dist in (24.0, 52.0, 82.0, 114.0, 148.0, 184.0, 222.0):
                    lx = cx + side * dist
                    m.add(box(0.16, 6.2, 0.16, pole_col, center=(lx, 3.1, bz + 7.2)))
                    m.add(box(0.48, 0.12, 0.24, lamp_glow, center=(lx, 6.15, bz + 6.8), emissive=True))
                    if dist <= 114.0:
                        lamps.append((lx, 6.0, bz + 6.8))
                for bx_o in (56.0, 96.0, 142.0, 192.0, 242.0):
                    for z_s in (-20.0, 20.0):
                        _add_building(m, cx + side * bx_o, bz + z_s, rng.uniform(22.0, 32.0),
                                      rng.uniform(22.0, 48.0), 16.0, rng.choice(block_cols),
                                      rng, beacons, roofs, side, allow_roof=False,
                                      tier=2 if bx_o < 130.0 else 3,
                                      detailed=(bx_o < 110.0))
            cross_next += 145.0
            bz += 36.0
            continue
        for side in (-1.0, 1.0):
            w = rng.uniform(15.0, 22.0)
            d = rng.uniform(18.0, 25.0)
            h = rng.uniform(16.0, 26.5)
            off = 22.5 + w * 0.5 + rng.uniform(0.0, 1.5)
            _add_building(m, cx + side * off, bz, w, h, d, rng.choice(block_cols),
                          rng, beacons, roofs, side, tier=1, detailed=True)
            if rng.random() < 0.45:
                m.add(box(2.2, 2.5, 4.4, (44, 50, 58), center=(cx + side * 14.5, 1.25, bz)))
                m.add(box(0.16, 1.2, 3.8, (242, 186, 102), center=(cx + side * 13.3, 1.5, bz), emissive=True))
            if rng.random() < 0.96:
                sw, sh, sd = rng.uniform(18.0, 28.0), rng.uniform(28.0, 52.0), rng.uniform(20.0, 30.0)
                sx = cx + side * (48.0 + sw * 0.5 + rng.uniform(0.0, 10.0))
                _add_building(m, sx, bz + rng.uniform(-8.0, 8.0), sw, sh, sd,
                              (62, 66, 76), rng, beacons, roofs, side, allow_roof=False,
                              tier=2, detailed=False)
            if rng.random() < 0.94:
                dw, dh, dd = rng.uniform(22.0, 34.0), rng.uniform(42.0, 72.0), rng.uniform(24.0, 34.0)
                dx_off = cx + side * (88.0 + dw * 0.5 + rng.uniform(0.0, 16.0))
                _add_building(m, dx_off, bz + rng.uniform(-12.0, 12.0), dw, dh, dd,
                              (42, 46, 56), rng, beacons, roofs, side, allow_roof=False,
                              tier=3, detailed=False)
            if rng.random() < 0.90:
                fw, fh, fd = rng.uniform(26.0, 40.0), rng.uniform(48.0, 86.0), rng.uniform(26.0, 38.0)
                fx_off = cx + side * (138.0 + fw * 0.5 + rng.uniform(0.0, 26.0))
                _add_building(m, fx_off, bz + rng.uniform(-14.0, 14.0), fw, fh, fd,
                              (32, 37, 48), rng, beacons, roofs, side, allow_roof=False,
                              tier=3, detailed=False)
            if int(bz) % 75 < 28:
                _add_industrial_silhouette(m, cx + side * rng.uniform(195.0, 255.0),
                                           bz + rng.uniform(-15.0, 15.0), side, rng, beacons)
        bz += rng.uniform(23.0, 27.5)

    # Stranded articulated tram cars on the center rails along Curfew Boulevard
    for tz_tram in (155.0, 445.0, 735.0, 965.0):
        _add_tram_car(m, corridor_x(tz_tram), tz_tram, corridor_yaw(tz_tram))

    # Overhead tram catenary portals & burning curfew barricades / stalled Guard convoys
    for gz in range(110, 1090, 130):
        gx = corridor_x(float(gz))
        gyaw = corridor_yaw(float(gz))
        gm = Mesh()
        for side in (-1.0, 1.0):
            gm.add(box(0.32, 8.8, 0.32, pole_col, center=(side * 10.6, 4.4, 0.0)))
        gm.add(box(21.6, 0.24, 0.24, pole_col, center=(0.0, 8.7, 0.0)))
        gm.add(box(21.2, 0.08, 0.08, (76, 80, 86), center=(0.0, 7.6, 0.0)))
        m.add(gm, rot_y(gyaw), (gx, 0.0, float(gz)))
    for idx_b, bz_f in enumerate((95.0, 195.0, 310.0, 410.0, 530.0, 620.0, 760.0, 865.0, 995.0)):
        bx = corridor_x(bz_f) + (-4.2 if idx_b % 2 == 0 else 4.2)
        m.add(box(4.6, 0.95, 0.80, kerb, center=(bx, 0.48, bz_f)))
        # Burning oil barrels beside the concrete jersey roadblock
        for b_off in (-2.6, 2.6):
            m.add(box(0.58, 0.88, 0.58, (72, 38, 28), center=(bx + b_off, 0.44, bz_f - 0.8)))
            m.add(box(0.48, 0.18, 0.48, (255, 168, 62), center=(bx + b_off, 0.92, bz_f - 0.8), emissive=True))
        if guard_truck is not None and idx_b % 2 == 1:
            m.add(guard_truck, rot_y(corridor_yaw(bz_f) + 18.0), (bx - 1.8, 0.0, bz_f + 4.8))
        if wreck_car is not None:
            m.add(wreck_car, rot_y(rng.uniform(-45.0, 45.0)), (bx + 2.2, 0.0, bz_f + 2.4))
        else:
            m.add(box(1.9, 0.85, 4.0, (28, 30, 34), center=(bx + 2.2, 0.45, bz_f + 2.4)), rot_y(28.0))
        fires.append((bx + 2.2, 0.7, bz_f + 2.4))

    # Concrete curfew flyover arch at z = 680
    ax = corridor_x(680.0)
    m.add(box(48.0, 1.8, 7.5, kerb, center=(ax, 8.4, 680.0)))
    for sx in (-12.5, 12.5):
        m.add(box(2.2, 8.2, 2.2, kerb, center=(ax + sx, 4.1, 680.0)))

    # 4. Zone 2: The Radio Station (z 1120..2220 — Stage 3)
    # 4a. Highway flyover at z = 1320 with lateral entry/exit ramps & enclosing ministry blocks (zero hole)
    ox = corridor_x(1320.0)
    _ribbon(m, 1313.0, 1327.0, -260.0, 260.0, asphalt, y_off=0.08, layer=1)
    m.add(box(88.0, 1.7, 10.5, kerb, center=(ox, 8.0, 1320.0)))
    m.add(box(88.0, 0.35, 0.40, lamp_glow, center=(ox, 9.0, 1314.8), emissive=True))
    for sx in (-14.5, 14.5, -28.0, 28.0, -42.0, 42.0):
        m.add(box(1.8, 7.8, 1.8, kerb, center=(ox + sx, 3.9, 1320.0)))
    # Sloped concrete highway entry/exit ramps flanking the z = 1320 overpass
    for side in (-1.0, 1.0):
        ramp_x = ox + side * 66.0
        m.add(box(48.0, 1.2, 8.5, kerb), m=rot_y(90.0), t=(ramp_x, 4.2, 1320.0))
        for r_off in (34.0, 66.0, 104.0, 148.0, 196.0):
            for z_off in (-28.0, 28.0):
                _add_building(m, ox + side * r_off, 1320.0 + z_off, rng.uniform(20.0, 28.0),
                              rng.uniform(22.0, 48.0), 22.0, rng.choice(block_cols),
                              rng, beacons, roofs, side, allow_roof=(r_off < 45.0),
                              tier=1 if r_off < 45.0 else (2 if r_off < 115.0 else 3),
                              detailed=(r_off < 115.0))

    # 4b. Grand M4 Broadcast Plaza & Fortified Station Complex (z = 1500..1760 — zero gap, wrapped to +-280 m)
    px = corridor_x(1620.0)
    plaza_col = tex("ashlar", like=(74, 74, 78), tint=True)
    _ribbon(m, 1500.0, 1760.0, -96.0, 96.0, plaza_col, y_off=0.09, layer=1, seg_x=4)
    # Lateral avenues bordering north and south edges of Broadcast Plaza out to +-260 m
    for pz_edge in (1505.0, 1755.0):
        _ribbon(m, pz_edge - 6.0, pz_edge + 6.0, -260.0, -9.0, asphalt, y_off=0.08, layer=1)
        _ribbon(m, pz_edge - 6.0, pz_edge + 6.0, 9.0, 260.0, asphalt, y_off=0.08, layer=1)
        for side in (-1.0, 1.0):
            for dist in (28.0, 58.0, 92.0, 128.0, 168.0, 210.0):
                lx = corridor_x(pz_edge) + side * dist
                m.add(box(0.16, 6.4, 0.16, pole_col, center=(lx, 3.2, pz_edge + 6.5)))
                m.add(box(0.48, 0.12, 0.24, lamp_glow, center=(lx, 6.35, pz_edge + 6.2), emissive=True))
                if dist <= 92.0:
                    lamps.append((lx, 6.2, pz_edge + 6.2))

    # Broadcast House (east wing) + north/south colonnaded annexes + illuminated glass studio bays
    _add_building(m, px + 34.0, 1620.0, 24.0, 21.0, 62.0, (118, 114, 110), rng, beacons, roofs, 1.0)
    _add_building(m, px + 32.0, 1546.0, 22.0, 19.0, 38.0, (104, 102, 98), rng, beacons, roofs, 1.0)
    _add_building(m, px + 32.0, 1696.0, 22.0, 19.0, 38.0, (104, 102, 98), rng, beacons, roofs, 1.0)
    for cz in range(1594, 1648, 6):
        m.add(box(0.88, 8.4, 0.88, (128, 124, 118), center=(px + 20.4, 4.2, float(cz))))
    m.add(box(2.8, 1.2, 56.0, (104, 102, 100), center=(px + 20.8, 8.8, 1620.0)))
    # Illuminated street-level & mezzanine broadcast studio bays
    for sz_bay in (1604.0, 1620.0, 1636.0):
        m.add(box(0.14, 3.4, 10.5, (255, 214, 138), center=(px + 21.8, 3.2, sz_bay), emissive=True))
        m.add(box(0.14, 2.4, 10.5, (148, 214, 248), center=(px + 21.8, 11.4, sz_bay), emissive=True))
    # Rooftop microwave dish array on Broadcast House
    for dz_d in (-16.0, 0.0, 16.0):
        m.add(box(1.2, 2.8, 1.2, (74, 78, 86), center=(px + 26.0, 23.2, 1620.0 + dz_d)))
        m.add(box(0.45, 2.2, 2.2, (212, 216, 224), center=(px + 25.1, 24.4, 1620.0 + dz_d)))

    # Opposing Ministry of Information Complex (west wing + north/south plaza wings)
    _add_building(m, px - 36.0, 1602.0, 22.0, 18.5, 48.0, (98, 100, 106), rng, beacons, roofs, -1.0)
    _add_building(m, px - 34.0, 1542.0, 22.0, 21.0, 38.0, (92, 96, 104), rng, beacons, roofs, -1.0)
    _add_building(m, px - 34.0, 1704.0, 22.0, 20.0, 38.0, (92, 96, 104), rng, beacons, roofs, -1.0)
    m.add(box(0.14, 2.8, 28.0, (248, 196, 116), center=(px - 24.8, 5.2, 1602.0), emissive=True))

    # Concrete Guard bunkers, fortified sandbag/jersey revetments, parked armored trucks & plaza fires
    bunker_c = tex("concrete", like=(62, 66, 72), tint=True)
    slit_glow = (255, 164, 78)
    for bx_p, bz_p, byaw in (
        (px - 15.5, 1548.0, 18.0), (px + 15.5, 1554.0, -18.0),
        (px - 16.0, 1622.0, 12.0), (px + 15.5, 1642.0, -15.0),
        (px - 15.0, 1692.0, 8.0), (px + 15.0, 1698.0, -12.0),
    ):
        bk = Mesh()
        bk.add(box(5.4, 2.4, 4.4, bunker_c, center=(0.0, 1.2, 0.0)))
        bk.add(box(5.8, 0.38, 4.8, (48, 52, 58), center=(0.0, 2.55, 0.0)))
        bk.add(box(3.4, 0.28, 0.12, slit_glow, center=(0.0, 1.55, -2.22), emissive=True))
        bk.add(box(6.4, 0.95, 0.75, kerb, center=(0.0, 0.48, -3.4)))
        m.add(bk, rot_y(byaw), (bx_p, 0.0, bz_p))
        if guard_truck is not None:
            m.add(guard_truck, rot_y(byaw + 72.0), (bx_p + (3.8 if bx_p > px else -3.8), 0.0, bz_p - 6.5))
        fires.append((bx_p + (1.8 if bx_p < px else -1.8), 0.7, bz_p - 4.2))

    # Multi-tier brutalist skyline walls (Tiers 2, 3, 4) wrapping Broadcast Plaza out to +-280 m
    for pz_ring in range(1500, 1770, 34):
        cx_r = corridor_x(float(pz_ring))
        for side in (-1.0, 1.0):
            for t_idx, (x_base, h_lo, h_hi, col_t) in enumerate((
                (68.0, 32.0, 52.0, (58, 62, 72)),
                (114.0, 44.0, 72.0, (44, 48, 58)),
                (168.0, 52.0, 86.0, (34, 38, 48)),
                (228.0, 48.0, 82.0, (28, 32, 44)),
            )):
                bw = rng.uniform(24.0, 36.0)
                bd = rng.uniform(24.0, 34.0)
                bh = rng.uniform(h_lo, h_hi)
                _add_building(m, cx_r + side * (x_base + bw * 0.5), float(pz_ring),
                              bw, bh, bd, col_t, rng, beacons, roofs, side,
                              allow_roof=False, tier=2 if t_idx == 0 else 3,
                              detailed=(t_idx == 0))

    # 88 m Tapered Red/White Broadcast Lattice Tower with tensioned guy-wires, microwave drums & vivid beacons
    tx, tz = px - 25.0, 1658.0
    red_b = (196, 44, 38)
    wht_b = (218, 216, 210)
    m.add(box(7.6, 2.4, 7.6, kerb, center=(tx, 1.2, tz)))
    for tier in range(8):
        y0 = 2.0 + tier * 10.0
        w0 = 5.8 - tier * 0.58
        col = red_b if tier % 2 == 0 else wht_b
        for sx in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                m.add(box(0.38, 10.3, 0.38, col, center=(tx + sx * w0 * 0.5, y0 + 5.0, tz + sz * w0 * 0.5)))
        m.add(box(w0 + 0.28, 0.44, w0 + 0.28, col, center=(tx, y0 + 9.8, tz)))
        m.add(box(w0 + 0.12, 0.24, w0 + 0.12, col, center=(tx, y0 + 5.0, tz)))
        # Diagonal lattice cross-bracing bars
        _wire_beam(m, (tx - w0 * 0.5, y0 + 0.4, tz - w0 * 0.5), (tx + w0 * 0.5, y0 + 9.6, tz - w0 * 0.5), 0.16, col)
        _wire_beam(m, (tx + w0 * 0.5, y0 + 0.4, tz + w0 * 0.5), (tx - w0 * 0.5, y0 + 9.6, tz + w0 * 0.5), 0.16, col)
        if tier in (3, 5):
            pw_t = 6.2 if tier == 3 else 5.6
            m.add(box(pw_t, 1.2, pw_t, (72, 76, 82), center=(tx, y0 + 8.0, tz)))
            m.add(box(pw_t + 0.2, 0.28, pw_t + 0.2, (255, 198, 118), center=(tx, y0 + 8.8, tz), emissive=True))
            # High-gain microwave relay drums on the tower platforms
            for d_sx in (-1.0, 1.0):
                m.add(box(0.55, 1.8, 1.8, wht_b, center=(tx + d_sx * (pw_t * 0.5 + 0.3), y0 + 8.4, tz)))
    m.add(box(0.42, 13.0, 0.42, red_b, center=(tx, 88.5, tz)))
    m.add(box(1.1, 1.1, 1.1, (255, 68, 52), center=(tx, 95.2, tz), emissive=True))
    # Tensioned steel guy-wires anchored to 4 concrete anchor blocks around the tower base
    guy_col = (84, 90, 102)
    for gx_o, gz_o in ((-26.0, -26.0), (14.0, -26.0), (-26.0, 26.0), (14.0, 26.0)):
        ax_g, az_g = tx + gx_o, tz + gz_o
        m.add(box(2.4, 1.8, 2.4, kerb, center=(ax_g, 0.9, az_g)))
        _wire_beam(m, (ax_g, 1.6, az_g), (tx, 44.0, tz), 0.09, guy_col)
        _wire_beam(m, (ax_g, 1.6, az_g), (tx, 72.0, tz), 0.08, guy_col)
    for by in (22.0, 38.0, 52.0, 66.0, 80.0, 95.5):
        beacons.append((tx, by, tz))

    # 4c. Continuous flanking urban blocks (z = 1120..1980) + Gradual City-to-Highway Outskirts (z = 1980..2240)
    wh_col = tex("metal_rib", like=(46, 50, 58), tint=True)
    brick_col = tex("brick", like=(68, 46, 42), tint=True)
    bz = 1125.0
    while bz < 1980.0:
        if not (1500.0 <= bz <= 1760.0) and abs(bz - 1320.0) > 18.0:
            cx = corridor_x(bz)
            for side in (-1.0, 1.0):
                w = rng.uniform(16.0, 22.0)
                d = rng.uniform(20.0, 26.0)
                h = rng.uniform(16.0, 26.5)
                _add_building(m, cx + side * (22.5 + w * 0.5), bz, w, h, d,
                              rng.choice(block_cols), rng, beacons, roofs, side, tier=1, detailed=True)
                sw, sh, sd = rng.uniform(18.0, 28.0), rng.uniform(28.0, 48.0), rng.uniform(20.0, 28.0)
                _add_building(m, cx + side * (52.0 + sw * 0.5), bz, sw, sh, sd,
                              (58, 62, 72), rng, beacons, roofs, side, allow_roof=False,
                              tier=2, detailed=False)
                dw, dh, dd = rng.uniform(22.0, 34.0), rng.uniform(42.0, 68.0), rng.uniform(24.0, 32.0)
                _add_building(m, cx + side * (94.0 + dw * 0.5), bz, dw, dh, dd,
                              (38, 42, 52), rng, beacons, roofs, side, allow_roof=False,
                              tier=3, detailed=False)
                fw, fh, fd = rng.uniform(26.0, 38.0), rng.uniform(48.0, 82.0), rng.uniform(26.0, 36.0)
                _add_building(m, cx + side * (146.0 + fw * 0.5), bz, fw, fh, fd,
                              (30, 34, 46), rng, beacons, roofs, side, allow_roof=False,
                              tier=3, detailed=False)
                if int(bz) % 84 < 28:
                    _add_industrial_silhouette(m, cx + side * rng.uniform(198.0, 255.0),
                                               bz, side, rng, beacons)
        bz += 26.0

    # 4d. Gradual City-to-Highway Outskirts Transition (z = 1980..2240):
    # Industrial depots, rail marshalling yard with freight boxcars, ring-road overpass & sparse outer towers
    _ribbon(m, 1990.0, 2230.0, -78.0, -20.0, ballast_c, y_off=0.08, layer=1, seg_x=2)
    for track_x in (-26.0, -34.0, -42.0):
        _curve_beam(m, 1990.0, 2230.0, track_x - 0.8, 0.12, 0.10, rail_c, y_off=0.12)
        _curve_beam(m, 1990.0, 2230.0, track_x + 0.8, 0.12, 0.10, rail_c, y_off=0.12)
    boxcar_c = tex("boxcar", like=(78, 42, 38), tint=True)
    tankcar_c = tex("steel", like=(54, 58, 64), tint=True)
    for rz_yard in range(2005, 2215, 26):
        cx_y = corridor_x(float(rz_yard))
        cyaw_y = corridor_yaw(float(rz_yard))
        # Freight boxcars and oil tank cars parked on the marshalling sidings
        m.add(box(3.1, 3.8, 14.5, boxcar_c if (rz_yard % 52 == 0) else tankcar_c),
              rot_y(cyaw_y), (cx_y - 34.0, 2.0, float(rz_yard)))
        if rz_yard % 52 == 0:
            m.add(box(3.1, 3.8, 14.5, tankcar_c), rot_y(cyaw_y), (cx_y - 42.0, 2.0, float(rz_yard) + 8.0))
        # Yard floodlight mast
        if rz_yard % 78 == 0:
            m.add(box(0.35, 16.0, 0.35, pole_col, center=(cx_y - 50.0, 8.0, float(rz_yard))))
            m.add(box(2.4, 0.35, 0.45, lamp_glow, center=(cx_y - 49.0, 16.0, float(rz_yard)), emissive=True))
            lamps.append((cx_y - 49.0, 15.6, float(rz_yard)))
        # Low industrial depots, heating plant & receding outer apartment blocks on both flanks
        u_out = (rz_yard - 1980.0) / 260.0
        for side in (-1.0, 1.0):
            depot_off = (56.0 if side < 0 else 28.0) + u_out * 12.0
            dh_d = rng.uniform(9.5, 15.0) * (1.0 - 0.30 * u_out)
            dw_d = rng.uniform(18.0, 26.0)
            m.add(box(dw_d, dh_d, 20.0, wh_col if side > 0 else brick_col,
                      center=(cx_y + side * depot_off, dh_d * 0.5, float(rz_yard))))
            m.add(box(0.14, 1.3, 12.0, (242, 184, 102),
                      center=(cx_y + side * (depot_off - side * dw_d * 0.5 - side * 0.08), dh_d * 0.62, float(rz_yard)),
                      emissive=True))
            if side > 0 and dh_d >= 12.0:
                roofs.append((cx_y + side * (depot_off - 5.0), dh_d, float(rz_yard), side))
            # Sparse outer socialist housing monoliths stepping down into the valley
            if rng.random() < (0.85 - 0.45 * u_out):
                th_o = rng.uniform(26.0, 48.0) * (1.0 - 0.35 * u_out)
                _add_building(m, cx_y + side * rng.uniform(86.0, 148.0), float(rz_yard),
                              rng.uniform(20.0, 28.0), th_o, 22.0, (44, 48, 58),
                              rng, beacons, roofs, side, allow_roof=False, tier=3, detailed=False)
    # Concrete Ring-Road Overpass Bridge marking the city-limit gateway at z = 2190
    rx_ring = corridor_x(2190.0)
    m.add(box(96.0, 1.8, 11.0, kerb, center=(rx_ring, 8.6, 2190.0)))
    m.add(box(16.0, 2.2, 0.28, (30, 108, 62), center=(rx_ring, 8.8, 2184.3), emissive=True))
    for sx in (-36.0, -14.5, 14.5, 36.0):
        m.add(box(2.0, 8.4, 2.2, kerb, center=(rx_ring + sx, 4.2, 2190.0)))

    # City & Plaza rooftop sweeping searchlight stations
    for sz, sx_o, sy in ((320.0, -36.0, 26.0), (740.0, 38.0, 28.0), (1320.0, 36.0, 24.0),
                         (1560.0, -34.0, 19.0), (1620.0, 34.0, 22.0), (1685.0, -32.0, 20.0),
                         (2060.0, -48.0, 16.0), (2680.0, 24.0, 10.0), (2920.0, 36.0, 12.0)):
        searchlights.append((corridor_x(sz) + sx_o, sy, sz))

    # 5. Zone 3: Route 12 Highway Valley (z 2220..3360)
    # 5a. Continuous rising Carpathian foothills, spruce lines, railway catenary poles, poplars & cottages
    vz = 2230.0
    while vz < 3355.0:
        cx = corridor_x(vz)
        cyaw = corridor_yaw(vz)
        # Electrified railway catenary mast along the west track (off = -23.5 m)
        ry_cat = surface_y(cx - 26.2, vz)
        m.add(box(0.24, 7.6, 0.24, (58, 62, 68), center=(cx - 26.2, ry_cat + 3.8, vz)))
        m.add(box(3.4, 0.16, 0.16, (68, 72, 78), center=(cx - 24.6, ry_cat + 7.2, vz)))
        # Roadside poplar lines & timbered verges
        for side in (-1.0, 1.0):
            px_pop = cx + side * (29.5 if side < 0 else 16.5)
            if not (2385.0 <= vz <= 2465.0 and side > 0) and not (2645.0 <= vz <= 2715.0):
                py_pop = surface_y(px_pop, vz)
                _add_spruce(m, px_pop, py_pop, vz, rng.uniform(11.0, 16.5), bark, pine_a, pine_b)
            # Continuous layered Carpathian foothill spruce bands (+-58..230 m)
            for b_idx, band in enumerate((56.0, 92.0, 138.0, 192.0)):
                tx_h = cx + side * (band + rng.uniform(-8.0, 8.0))
                tz_h = vz + rng.uniform(-12.0, 12.0)
                ty_h = surface_y(tx_h, tz_h)
                _add_spruce(m, tx_h, ty_h, tz_h, rng.uniform(14.0, 24.0),
                            bark, pine_a, pine_b, low_poly=(b_idx >= 2))
        # Flanking valley hill masses & scattered village cottages with warm windows
        if int(vz) % 84 < 38:
            for side in (-1.0, 1.0):
                rx_h = cx + side * rng.uniform(95.0, 165.0)
                ry_h = surface_y(rx_h, vz) * 0.45
                m.add(W7._bipyr(rx_h, ry_h, vz, rng.uniform(48.0, 74.0),
                                rng.uniform(32.0, 56.0), 1.0, foothill_c, n=6))
                if rng.random() < 0.55 and not (2880.0 <= vz <= 2960.0 and side > 0):
                    cot_x = cx + side * rng.uniform(46.0, 78.0)
                    _add_valley_cottage(m, cot_x, vz + rng.uniform(-10.0, 10.0),
                                        cyaw - side * 90.0 + rng.uniform(-15.0, 15.0))
        # High-voltage transmission pylons marching along the valley slopes
        if int(vz) % 114 < 38:
            side_p = 1.0 if (int(vz) // 114) % 2 == 0 else -1.0
            px_p = cx + side_p * 42.0
            py_p = surface_y(px_p, vz)
            m.add(box(0.65, 24.0, 0.65, (68, 72, 78), center=(px_p, py_p + 12.0, vz)))
            m.add(box(9.2, 0.38, 0.38, (68, 72, 78), center=(px_p, py_p + 19.0, vz)))
            m.add(box(6.6, 0.38, 0.38, (68, 72, 78), center=(px_p, py_p + 22.8, vz)))
        vz += 36.0

    # 5b. Landmark 1 — Lit Highway Fuel Depot & Petrol Station (z = 2420, east flank)
    fx_d = corridor_x(2420.0) + 24.0
    fy_d = surface_y(fx_d, 2420.0)
    _ribbon(m, 2388.0, 2456.0, 8.0, 44.0, asphalt, y_off=0.08, layer=1, seg_x=2)
    # Illuminated red/amber petrol canopy + columns + fuel island pumps
    m.add(box(14.0, 0.65, 24.0, (196, 52, 42), center=(fx_d - 4.0, fy_d + 5.8, 2420.0), emissive=True))
    m.add(box(13.2, 0.18, 23.2, (255, 224, 156), center=(fx_d - 4.0, fy_d + 5.42, 2420.0), emissive=True))
    for cz_p in (2411.0, 2420.0, 2429.0):
        for cx_p in (fx_d - 8.5, fx_d + 0.5):
            m.add(box(0.45, 5.4, 0.45, (186, 190, 196), center=(cx_p, fy_d + 2.7, cz_p)))
        m.add(box(1.1, 1.8, 2.2, (188, 48, 38), center=(fx_d - 4.0, fy_d + 0.9, cz_p)))
        m.add(box(0.8, 0.55, 1.4, (255, 214, 138), center=(fx_d - 4.0, fy_d + 1.45, cz_p), emissive=True))
    # Service station building + 3 pressurized white/red bulk fuel storage tanks
    m.add(box(10.0, 4.6, 18.0, (82, 86, 94), center=(fx_d + 8.5, fy_d + 2.3, 2416.0)))
    m.add(box(0.14, 2.2, 13.5, (255, 206, 126), center=(fx_d + 3.4, fy_d + 2.0, 2416.0), emissive=True))
    for tz_tk in (2434.0, 2442.0, 2450.0):
        m.add(box(5.6, 4.8, 5.6, (176, 180, 186), center=(fx_d + 8.5, fy_d + 2.4, tz_tk)))
        m.add(box(5.8, 0.85, 5.8, (192, 48, 38), center=(fx_d + 8.5, fy_d + 2.6, tz_tk), emissive=True))
    lamps.append((fx_d - 4.0, fy_d + 5.2, 2420.0))
    roofs.append((fx_d + 5.5, fy_d + 4.6, 2416.0, 1.0))

    # 5c. Landmark 2 — Expanded Route 12 Toll Plaza (z = 2680, echoing M8 Revenge)
    gx = corridor_x(2680.0)
    gy_t = surface_y(gx, 2680.0)
    _ribbon(m, 2652.0, 2712.0, -24.0, 24.0, asphalt, y_off=0.08, layer=1, seg_x=2)
    for sx in (-17.0, -8.5, 0.0, 8.5, 17.0):
        m.add(box(0.85, 9.6, 0.85, (86, 90, 96), center=(gx + sx, gy_t + 4.8, 2680.0)))
    for bx_o in (-12.8, -6.2, 6.2, 12.8):
        m.add(box(2.4, 3.2, 4.4, kerb, center=(gx + bx_o, gy_t + 1.6, 2680.0)))
        m.add(box(2.0, 1.1, 0.16, (255, 206, 124), center=(gx + bx_o, gy_t + 2.1, 2677.7), emissive=True))
        m.add(box(0.16, 1.1, 2.8, (255, 206, 124), center=(gx + bx_o - 1.22, gy_t + 2.1, 2680.0), emissive=True))
    # Full 36 m overhead toll canopy + illuminated green highway signboard + soffit lighting
    m.add(box(36.4, 1.1, 6.8, (76, 80, 88), center=(gx, gy_t + 9.4, 2680.0)))
    m.add(box(34.0, 0.22, 4.8, (255, 214, 140), center=(gx, gy_t + 8.82, 2680.0), emissive=True))
    m.add(box(18.5, 2.6, 0.28, (30, 108, 62), center=(gx, gy_t + 9.2, 2676.4), emissive=True))
    m.add(box(14.0, 0.38, 0.32, (238, 238, 230), center=(gx, gy_t + 9.3, 2676.2), emissive=True))
    beacons.append((gx - 17.0, gy_t + 10.2, 2680.0))
    beacons.append((gx + 17.0, gy_t + 10.2, 2680.0))
    lamps.append((gx - 8.5, gy_t + 8.4, 2680.0))
    lamps.append((gx + 8.5, gy_t + 8.4, 2680.0))
    if guard_truck is not None:
        m.add(guard_truck, rot_y(32.0), (gx - 9.5, gy_t, 2666.0))
        m.add(guard_truck, rot_y(-26.0), (gx + 10.2, gy_t, 2692.0))

    # 5d. Landmark 3 — High-Voltage Power Substation (z = 2920, east valley shelf)
    sx_s = corridor_x(2920.0) + 28.0
    sy_s = surface_y(sx_s, 2920.0)
    m.add(box(24.0, 1.4, 34.0, kerb, center=(sx_s, sy_s + 0.3, 2920.0)))
    m.add(box(8.5, 5.2, 12.0, brick_col, center=(sx_s + 4.5, sy_s + 3.4, 2912.0)))
    m.add(box(0.16, 1.6, 8.0, (214, 236, 174), center=(sx_s + 0.15, sy_s + 3.8, 2912.0), emissive=True))
    for tz_tr in (2920.0, 2927.0, 2934.0):
        m.add(box(3.8, 3.6, 3.4, (58, 64, 68), center=(sx_s - 3.5, sy_s + 2.6, tz_tr)))
        for bx_i in (-1.1, 0.0, 1.1):
            m.add(box(0.24, 1.6, 0.24, (212, 214, 208), center=(sx_s - 3.5 + bx_i, sy_s + 5.1, tz_tr)))
        m.add(box(8.4, 0.32, 0.32, (72, 76, 82), center=(sx_s - 3.5, sy_s + 7.8, tz_tr)))
        for gx_p in (-7.2, 0.2):
            m.add(box(0.32, 7.2, 0.32, (72, 76, 82), center=(sx_s + gx_p, sy_s + 4.4, tz_tr)))
    # Amber floodlights illuminating the substation yard
    m.add(box(1.8, 0.35, 1.8, (255, 192, 104), center=(sx_s - 3.5, sy_s + 8.1, 2927.0), emissive=True))
    lamps.append((sx_s - 3.5, sy_s + 7.8, 2927.0))
    beacons.append((sx_s + 4.5, sy_s + 6.4, 2912.0))
    roofs.append((sx_s + 2.0, sy_s + 6.0, 2912.0, 1.0))

    # 5e. Landmark 4 — Concrete Mountain-Approach Viaduct & Broken Guard Convoy (z = 3160)
    vx_v = corridor_x(3160.0)
    vy_v = surface_y(vx_v, 3160.0)
    m.add(box(76.0, 2.4, 9.5, kerb, center=(vx_v, vy_v + 11.5, 3160.0)))
    m.add(box(76.0, 0.32, 0.32, (255, 194, 112), center=(vx_v, vy_v + 12.8, 3155.1), emissive=True))
    for sx in (-28.0, -13.5, 13.5, 28.0):
        m.add(box(2.4, 11.5, 2.6, kerb, center=(vx_v + sx, vy_v + 5.6, 3160.0)))
    for wz in (2370.0, 2530.0, 2672.0, 2820.0, 3090.0, 3155.0, 3172.0, 3260.0):
        wx = corridor_x(wz) + rng.choice((-5.4, 5.4))
        wy_w = surface_y(wx, wz)
        if wreck_car is not None:
            m.add(wreck_car, rot_y(rng.uniform(-45.0, 45.0)), (wx, wy_w, wz))
        else:
            m.add(box(1.9, 0.8, 4.2, (32, 34, 38), center=(wx, wy_w + 0.4, wz)), rot_y(rng.uniform(-35, 35)))
        fires.append((wx, wy_w + 0.65, wz))

    # 6. Zone 4: Northern Ridge Gorge (z 3360..5800)
    # Steep +45..108 m canyon walls blanketed with 6 terraced spruce bands & snow-dusted rock crags
    fz = 3365.0
    while fz < 5770.0:
        cx = corridor_x(fz)
        gy_c = surface_y(cx, fz)
        b_in = max(0.0, min(1.0, (fz - 5180.0) / 130.0))
        b_out = max(0.0, min(1.0, (fz - 5550.0) / 160.0))
        basin_u = b_in * (1.0 - b_out)
        if int(fz) % 84 < 28:
            mist_spots.append((cx + rng.uniform(-12.0, 12.0), gy_c + 3.5, fz))
        for side in (-1.0, 1.0):
            for b_idx, band in enumerate((18.0, 34.0, 54.0, 80.0, 112.0, 148.0)):
                tx_p = cx + side * (band + 66.0 * basin_u + rng.uniform(-4.5, 6.5))
                tz_p = fz + rng.uniform(-10.0, 10.0)
                py = surface_y(tx_p, tz_p)
                _add_spruce(m, tx_p, py, tz_p, rng.uniform(14.0, 24.0),
                            bark, pine_a, pine_b, low_poly=(b_idx >= 3))
            # Broad dark Carpathian granite cliff buttresses set back on the high canyon walls
            # (keeps the valley corridor & basin clear for Ucilev's gunship passes)
            if int(fz) % 84 < 28:
                rx = cx + side * (rng.uniform(112.0, 168.0) + 64.0 * basin_u)
                ry = surface_y(rx, fz)
                _add_cliff_ridge(m, rx, ry - 22.0, fz,
                                 rng.uniform(34.0, 52.0), rng.uniform(58.0, 86.0),
                                 rng.uniform(48.0, 82.0),
                                 rock_dark, rock_c, frost_c, rng, n=8)
        fz += 28.0

    # 6a. Zone-4 Landmark 1 — Retardovici's Burning Crash Clearing (z = 3460, east valley shelf)
    rx_c = corridor_x(3460.0) + 18.0
    ry_c = surface_y(rx_c, 3460.0)
    m.add(box(14.0, 0.22, 16.0, (24, 24, 26), center=(rx_c, ry_c + 0.10, 3460.0)))
    m.add(box(2.1, 1.4, 5.4, (28, 26, 26)), m_mul(rot_y(42.0), rot_z(24.0)), (rx_c, ry_c + 0.72, 3460.0))
    m.add(box(0.55, 0.52, 3.2, (24, 24, 26)), rot_y(115.0), (rx_c + 2.4, ry_c + 0.35, 3457.2))
    m.add(box(0.26, 0.08, 4.4, (34, 36, 40)), rot_y(18.0), (rx_c - 1.8, ry_c + 0.25, 3462.5))
    fires.append((rx_c, ry_c + 0.85, 3460.0))
    fires.append((rx_c + 2.0, ry_c + 0.55, 3457.6))
    lamps.append((rx_c, ry_c + 2.4, 3460.0))

    # 6b. Zone-4 Landmark 2 — High Iron Gorge Trestle Bridge (z = 3820, 34 m overhead span)
    bx_t = corridor_x(3820.0)
    by_t = surface_y(bx_t, 3820.0)
    steel_g = (44, 48, 56)
    deck_y = by_t + 34.0
    m.add(box(96.0, 1.6, 6.2, steel_g, center=(bx_t, deck_y, 3820.0)))
    m.add(box(96.0, 0.65, 5.4, kerb, center=(bx_t, deck_y + 1.0, 3820.0)))
    for side in (-1.0, 1.0):
        px_t = bx_t + side * 44.0
        py_base = surface_y(px_t, 3820.0)
        pier_h = max(8.0, (deck_y + 12.0) - py_base)
        m.add(box(4.6, pier_h, 5.4, kerb, center=(px_t, py_base + pier_h * 0.5, 3820.0)))
        beacons.append((px_t, deck_y + 12.6, 3820.0))
    for kx in range(-36, 37, 12):
        _wire_beam(m, (bx_t + kx, deck_y + 0.8, 3817.2), (bx_t + kx + 12.0, deck_y + 5.8, 3817.2), 0.34, steel_g)
        _wire_beam(m, (bx_t + kx + 12.0, deck_y + 5.8, 3817.2), (bx_t + kx + 12.0, deck_y + 0.8, 3817.2), 0.30, steel_g)
        _wire_beam(m, (bx_t + kx, deck_y + 0.8, 3822.8), (bx_t + kx + 12.0, deck_y + 5.8, 3822.8), 0.34, steel_g)
    m.add(box(86.0, 0.42, 0.42, steel_g, center=(bx_t, deck_y + 5.8, 3817.2)))
    m.add(box(86.0, 0.42, 0.42, steel_g, center=(bx_t, deck_y + 5.8, 3822.8)))
    for lx_off in (-28.0, 0.0, 28.0):
        m.add(box(0.55, 0.25, 0.55, lamp_glow, center=(bx_t + lx_off, deck_y - 0.85, 3820.0), emissive=True))
        lamps.append((bx_t + lx_off, deck_y - 1.1, 3820.0))

    # 6c. Zone-4 Landmark 3 — Ridge Relay Bunker & Searchlight Outpost (z = 4280, east shelf)
    ox_r = corridor_x(4280.0) + 42.0
    oy_r = surface_y(ox_r, 4280.0)
    m.add(box(12.5, 5.2, 10.5, kerb, center=(ox_r, oy_r + 2.6, 4280.0)))
    m.add(box(0.22, 1.1, 6.4, (248, 186, 98), center=(ox_r - 6.3, oy_r + 3.4, 4280.0), emissive=True))
    m.add(box(1.4, 24.0, 1.4, steel_g, center=(ox_r + 2.2, oy_r + 17.0, 4282.0)))
    m.add(box(5.6, 0.45, 0.45, steel_g, center=(ox_r + 2.2, oy_r + 24.5, 4282.0)))
    beacons.append((ox_r + 2.2, oy_r + 29.4, 4282.0))
    searchlights.append((ox_r - 2.0, oy_r + 5.6, 4280.0))
    lamps.append((ox_r - 5.5, oy_r + 5.2, 4280.0))

    # 6d. Zone-4 Landmark 4 — High-Voltage Gorge Pylons & Overhead Span (z = 4780)
    px_c = corridor_x(4780.0)
    py_tops = []
    for side in (-1.0, 1.0):
        px_p = px_c + side * 62.0
        py_p = surface_y(px_p, 4780.0)
        top_y = py_p + 38.0
        m.add(box(2.2, 38.0, 2.2, steel_g, center=(px_p, py_p + 19.0, 4780.0)))
        m.add(box(9.6, 0.55, 0.85, steel_g, center=(px_p, top_y - 3.5, 4780.0)))
        m.add(box(7.4, 0.45, 0.75, steel_g, center=(px_p, top_y - 10.5, 4780.0)))
        beacons.append((px_p, top_y + 0.6, 4780.0))
        py_tops.append((px_p, top_y - 3.5))
    for w_z in (4777.0, 4780.0, 4783.0):
        _wire_beam(m, (py_tops[0][0], py_tops[0][1], w_z), (py_tops[1][0], py_tops[1][1], w_z), 0.16, (68, 74, 84))

    # Horizon ridge closing north end of the gorge
    cx_end = corridor_x(5750.0)
    gy_end = surface_y(cx_end, 5750.0)
    for k in range(-5, 6):
        col_m = rock_c if k % 2 else hill_c
        m.add(W7._bipyr(cx_end + k * 52.0, gy_end + 8.0, 5840.0, 68.0,
                        64.0 + (k % 2) * 18.0, 1.0, col_m, n=6))

    _CACHE["lamps"] = lamps
    _CACHE["beacons"] = beacons
    _CACHE["fires"] = fires
    _CACHE["roofs"] = roofs
    _CACHE["searchlights"] = searchlights
    _CACHE["mist_spots"] = mist_spots
    return m


def roof_spots():
    """Cached list of (x, roof_y, z, side) rooftop positions for RPG teams."""
    if "roofs" not in _CACHE:
        renderer()
    return _CACHE.get("roofs", ())


def renderer():
    """Return cached (renderer, None, 0, None) with baked night corridor."""
    got = _CACHE.get("r")
    if got is not None:
        return got
    from engine3d import Renderer
    r = Renderer(RES[0], RES[1], fog=FOG, fog_start=FOG_START, fog_end=FOG_END)
    r.light = Light(direction=(-0.38, 0.56, -0.68), ambient=0.34, diffuse=0.62,
                    sky=0.18, tint=(0.74, 0.84, 1.0))
    m = _build_corridor()
    _CACHE["faces"] = len(m.faces)
    r.bake(m)
    _CACHE["r"] = (r, None, 0, None)
    return _CACHE["r"]


def _nearest_lamps(focus, cap=18):
    fx, _, fz = focus
    lamps = _CACHE.get("lamps", ())
    near = [p for p in lamps if abs(p[2] - fz) < 210.0]
    near.sort(key=lambda p: (p[0] - fx) ** 2 + (p[2] - fz) ** 2)
    return near[:cap]


def frame(eye, tgt, fov, t=0, size=None, lights=(), pools=(), roll=0.0):
    """Set camera, night sky, fog, lights and queue the baked corridor."""
    r = renderer()[0]
    r.resize(*(size or RES))
    r.set_camera(eye, tgt, fov, roll)
    r.fog, r.fog_start, r.fog_end = FOG, FOG_START, FOG_END
    r.light = Light(direction=(-0.38, 0.56, -0.68), ambient=0.34, diffuse=0.62,
                    sky=0.18, tint=(0.74, 0.84, 1.0))

    dx, dz = tgt[0] - eye[0], tgt[2] - eye[2]
    dm = math.hypot(dx, dz) or 1.0
    focus = (eye[0] + (dx / dm) * 55.0, 0.0, eye[2] + (dz / dm) * 55.0)
    lamp_pts = _nearest_lamps(focus, cap=18)
    all_lights = list(lights) + [
        {"pos": p, "color": (255, 192, 110), "intensity": 1.20, "range": 30.0}
        for p in lamp_pts
    ]
    try:
        r.set_lights(all_lights[:26])
    except Exception:
        pass
    all_pools = list(pools) + [
        {"pos": (p[0], 0.4, p[2]), "range": 14.5, "color": (255, 194, 116), "intensity": 1.75}
        for p in _nearest_lamps(focus, cap=22)
    ]
    try:
        r.set_pools(all_pools[:28])
    except Exception:
        pass

    W7.sky(r, r.surface, t, "raid")
    r.begin()
    _CACHE["_last_ring_tag"] = None
    r.add_static()
    return r


def draw_corridor_fx(r, hpos, tm):
    """Submit 360-deg horizon ring, streetlamp halos, beacons, fires, searchlights & gorge mist."""
    draw_horizon_ring(r, hpos)
    hz = hpos[2]
    for lx, ly, lz in _CACHE.get("lamps", ()):
        if -60.0 < lz - hz < 340.0:
            r.add_sprite((lx, ly, lz),
                         _fx.glow((255, 200, 122), 0.95, int(tm), intensity=1.15, max_px=30),
                         layer=_fx.FX_LAYER)
    for i, (bx, by, bz) in enumerate(_CACHE.get("beacons", ())):
        if -60.0 < bz - hz < 340.0:
            r.add_sprite((bx, by, bz),
                         _fx.beacon((255, 54, 40), 0.75, int(tm), period_ms=1100.0, phase=i * 190.0),
                         layer=_fx.FX_LAYER)
    for i, (fx, fy, fz) in enumerate(_CACHE.get("fires", ())):
        if -50.0 < fz - hz < 250.0:
            F3D.emit_fire(r, (fx, fy, fz), tm, seed=700 + i, size=1.35, heat=1.2,
                          smoky=True, embers=False, bed=True, layer=2)
    # Sweeping nocturnal curfew searchlight beams piercing the haze
    ts = tm * 0.001
    for i, (sx, sy, sz) in enumerate(_CACHE.get("searchlights", ())):
        if -80.0 < sz - hz < 350.0:
            ang_x = math.sin(ts * (0.45 + 0.08 * i) + i * 2.1) * 0.34
            ang_z = math.cos(ts * (0.37 + 0.06 * i) + i * 1.4) * 0.28
            r.add_sprite((sx, sy, sz),
                         _fx.glow((214, 232, 255), 1.35, int(tm), intensity=1.25, max_px=34),
                         layer=_fx.FX_LAYER)
            for step_k, dist_m in enumerate((12.0, 28.0, 48.0, 72.0)):
                bp = (sx + ang_x * dist_m, sy + dist_m * 0.92, sz + ang_z * dist_m)
                r.add_sprite(bp, _fx.haze((182, 208, 246), 1.6 + dist_m * 0.09, int(tm),
                                          seed=810 + i * 7 + step_k,
                                          intensity=0.22 * (1.0 - step_k * 0.21)),
                             layer=_fx.FX_LAYER)
    # Drifting low valley mist sprites in the Northern Ridge Gorge (cp=4)
    if hz > 3200.0:
        for i, (mx, my, mz) in enumerate(_CACHE.get("mist_spots", ())):
            if -40.0 < mz - hz < 260.0:
                drift = math.sin(ts * 0.35 + i * 1.7) * 4.5
                r.add_sprite((mx + drift, my, mz),
                             _fx.haze((142, 164, 198), 4.2, int(tm),
                                      seed=920 + i, intensity=0.18),
                             layer=2)


def present(r, surface):
    if getattr(r, "backend", "") == "gl":
        r.hdr = True
        r.flush_to(surface, post={
            "bloom": 0.38, "bloom_knee": 0.84,
            "lut": _fx.cine_curve(), "dither_step": _fx.DITHER_STEP,
        })
        return
    surf = r.surface
    r.flush(surf)
    try:
        _fx.grade_cine(surf)
    except Exception:
        pass
    _fx.present_crisp(surf, surface)
