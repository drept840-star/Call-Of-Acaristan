"""Route 12 toll plaza, built for the low-poly sniper cinematic.

World layout (metres): the highway runs north along +z. The toll canopy
and booths sit at z = 0, the squad forms up in the open lanes just north of
it (z 6..9), a row of jersey barriers at z = 3.4 is the only cover, the
sign gantry with the sniper is at z = 58 and an overpass closes the view at
z = 120. Squad approaches from the south.
"""
import math
import random

from engine3d import (Mesh, box, prism, quad_xz, disc_xz, rot_y, rot_x, M_IDENT)

ASPHALT = (50, 52, 56)
ASPHALT_B = (46, 48, 52)
WET = (60, 64, 72)
SHOULDER = (58, 56, 50)
GRASS = (46, 54, 40)
GRASS_B = (42, 50, 37)
CONCRETE = (138, 134, 124)
CONCRETE_D = (104, 100, 92)
PAINT_W = (196, 196, 186)
PAINT_Y = (196, 160, 52)
STEEL = (78, 84, 90)
STEEL_D = (52, 56, 62)
SIGN_G = (24, 92, 58)
RUST = (92, 56, 36)
CHAR = (36, 32, 30)

BARRIER_Z = 6.0            # south face of the jersey barrier row (south side = safe)
PLAZA_DZ = -2.6            # toll plaza shifted south of the barrier row
GANTRY_Z = 58.0
SNIPER_POS = (3.6, 7.05, 58.6)       # prone sniper on the catwalk (pelvis)
SNIPER_SCOPE = (3.6, 7.42, 57.35)    # scope eye point
SNIPER_MUZZLE = (3.6, 7.33, 56.1)
FIELD_RADIO = (6.7, 0.0, 9.0)

# jersey barrier segments (x0, x1); gap at x 0.6..2.6 is the lane Seby runs through
BARRIERS = [(-9.6, -6.6), (-6.6, -3.6), (-3.6, -0.6), (2.6, 5.6), (5.6, 8.6)]


def jersey(x0, x1, z):
    prof = [(-0.33, 0.0), (0.33, 0.0), (0.18, 0.28), (0.11, 0.82), (-0.11, 0.82), (-0.18, 0.28)]
    m = prism(prof, x1 - x0, CONCRETE, cols={"front": CONCRETE_D, "back": CONCRETE_D}, seg=1.5)
    # prism extrudes along z; rotate so it runs along x
    out = Mesh()
    out.add(m, rot_y(90), (x0, 0.0, z + 0.33))
    # hazard stripe
    out.add(box(x1 - x0 - 0.1, 0.07, 0.01, (170, 120, 40), center=((x0 + x1) / 2, 0.6, z + 0.0 + 0.215)), M_IDENT)
    return out


def car(col, burned=False, rng=None):
    rng = rng or random
    m = Mesh()
    body = col if not burned else CHAR
    trim = (24, 22, 22)
    m.add(box(1.8, 0.62, 4.3, body, center=(0, 0.62, 0), seg=1.6,
              cols={"top": body if not burned else (46, 38, 34)}))
    cab_prof = [(-0.86, 0.0), (0.86, 0.0), (0.72, 0.52), (-0.72, 0.52)]
    cab = prism(cab_prof, 2.1, body if not burned else (30, 27, 26), seg=1.1,
                cols={"front": (20, 22, 26) if not burned else (16, 14, 14),
                      "back": (20, 22, 26) if not burned else (16, 14, 14)})
    m.add(cab, M_IDENT, (0, 0.93, -1.25))
    # windows strip
    win = (34, 40, 50) if not burned else (12, 11, 11)
    m.add(box(1.76, 0.3, 1.8, win, center=(0, 1.16, -0.2)))
    for wx in (-0.86, 0.86):
        for wz in (-1.35, 1.35):
            m.add(box(0.24, 0.62, 0.62, trim if not burned else (14, 13, 13), center=(wx, 0.31, wz)))
    if burned:
        m.add(box(1.5, 0.05, 0.9, RUST, center=(0, 0.95, 1.7)))
        m.add(box(0.4, 0.04, 1.3, RUST, center=(-0.5, 1.46, -0.3)))
    else:
        m.add(box(0.36, 0.12, 0.02, (200, 190, 150), center=(-0.62, 0.72, 2.16)), M_IDENT)
        m.add(box(0.36, 0.12, 0.02, (200, 190, 150), center=(0.62, 0.72, 2.16)), M_IDENT)
    return m


def build(r):
    """Bake the static set into renderer ``r``. Returns dict of handles."""
    rng = random.Random(1212)
    H = {}
    # ground ----------------------------------------------------------------
    def road_col(i, j):
        return ASPHALT if (i + j) % 2 else ASPHALT_B

    r.bake(quad_xz(-14, -40, 14, 30, 0.0, ASPHALT, layer=0, seg=3.5, colfn=lambda i, j: (
        WET if rng.random() < 0.10 else road_col(i, j))))
    r.bake(quad_xz(-14, 30, 14, 150, 0.0, ASPHALT, layer=0, seg=8.0, colfn=road_col))
    for sx0, sx1 in ((-24, -14), (14, 24)):
        r.bake(quad_xz(sx0, -40, sx1, 150, -0.02, SHOULDER, layer=0, seg=10.0))
    for sx0, sx1 in ((-160, -24), (24, 160)):
        r.bake(quad_xz(sx0, -40, sx1, 260, -0.05, GRASS, layer=0, seg=34.0,
                       colfn=lambda i, j: GRASS if (i + j) % 2 else GRASS_B))
    r.bake(quad_xz(-24, 150, 24, 260, -0.03, ASPHALT_B, layer=0, seg=30.0))
    # paint (decal layer)
    paint = Mesh()
    for lx in (-7.0, 0.0, 7.0):
        z = -38.0
        while z < 148:
            if not (-10 < z < 7):
                paint.add(quad_xz(lx - 0.07, z, lx + 0.07, z + 3.0, 0.01, PAINT_W, layer=1))
            z += 9.0
    for ex in (-13.6, 13.6):
        paint.add(quad_xz(ex - 0.09, -40, ex + 0.09, 150, 0.01, PAINT_Y, layer=1, seg=12.0))
    # stop line + toll lane chevrons
    paint.add(quad_xz(-14, 2.4, 14, 2.75, 0.01, PAINT_W, layer=1, seg=4.0))
    r.bake(paint)
    # puddles
    for _ in range(26):
        px, pz = rng.uniform(-12, 12), rng.uniform(-18, 40)
        r.bake(disc_xz(px, pz, rng.uniform(0.5, 1.6), 0.012, (72, 78, 88), n=8,
                       wobble=[rng.uniform(.7, 1.2) for _ in range(8)]))
    # toll plaza -------------------------------------------------------------
    plaza = Mesh()
    for ix in (-10.5, -3.5, 3.5, 10.5):
        plaza.add(box(1.4, 0.25, 11, (120, 116, 106), center=(ix, 0.125, -0.5 + PLAZA_DZ), seg=2.8))
        # yellow/black nose
        plaza.add(box(1.42, 0.6, 0.6, (190, 150, 40), center=(ix, 0.3, 5.3 + PLAZA_DZ)))
        if ix not in (-10.5, 10.5) or True:
            plaza.add(box(1.25, 2.4, 2.6, (150, 146, 136), center=(ix, 1.45, -1.0 + PLAZA_DZ),
                          cols={"back": (150, 146, 136)}))
            plaza.add(box(1.28, 0.9, 1.9, (30, 38, 48), center=(ix, 1.75, -1.0 + PLAZA_DZ), skip=("top", "bottom")))
            plaza.add(box(1.5, 0.18, 2.9, (90, 40, 34), center=(ix, 2.74, -1.0 + PLAZA_DZ)))
        # canopy pillars
        plaza.add(box(0.5, 6.0, 0.5, CONCRETE_D, center=(ix, 3.0, 2.8 + PLAZA_DZ), seg=2.0))
        plaza.add(box(0.5, 6.0, 0.5, CONCRETE_D, center=(ix, 3.0, -4.8 + PLAZA_DZ), seg=2.0))
    r.bake(plaza)
    canopy = Mesh()
    canopy.add(box(30, 0.8, 9.5, (170, 166, 156), center=(0, 6.4, -1.0 + PLAZA_DZ), seg=3.2,
                   cols={"bottom": (92, 90, 86), "front": (176, 48, 40), "back": (176, 48, 40)}))
    # canopy fascia stripe + lights
    for lx in range(-13, 14, 3):
        canopy.add(box(0.6, 0.06, 0.6, (230, 220, 180), center=(lx, 5.98, 1.6 + PLAZA_DZ), emissive=True))
    r.bake(canopy)
    # boom barriers (one per lane, some smashed)
    boom = Mesh()
    for i, (px, lane_dir, ang) in enumerate(((-10.5, 1, 0), (-3.5, 1, 32), (3.5, 1, 0), (10.5, -1, 74))):
        boom.add(box(0.36, 1.1, 0.36, (200, 200, 190), center=(px + 0.5 * lane_dir, 0.8, 4.3 + PLAZA_DZ)))
        seg = Mesh()
        for k in range(7):
            c = (200, 30, 30) if k % 2 == 0 else (225, 225, 215)
            seg.add(box(0.8, 0.12, 0.1, c, center=(0.4 + 0.8 * k, 0, 0)))
        rot = (1.0 if lane_dir > 0 else -1.0)
        m = rot_y(0 if lane_dir > 0 else 180)
        from engine3d import m_mul, rot_z
        m = m_mul(m, rot_z(-ang))
        boom.add(seg, m, (px + 0.5 * lane_dir, 1.25, 4.3 + PLAZA_DZ))
    r.bake(boom)
    # jersey barrier row: the only cover in the lane
    jb = Mesh()
    for x0, x1 in BARRIERS:
        jb.add(jersey(x0, x1, BARRIER_Z))
    H["barriers"] = r.bake(jb)
    # field radio dropped in the lane
    rad = Mesh()
    rad.add(box(0.42, 0.26, 0.24, (54, 62, 46), center=(FIELD_RADIO[0], 0.13, FIELD_RADIO[2])))
    rad.add(box(0.02, 0.6, 0.02, (16, 16, 16), center=(FIELD_RADIO[0] + 0.15, 0.55, FIELD_RADIO[2] - 0.05)))
    rad.add(box(0.1, 0.05, 0.18, (18, 18, 18), center=(FIELD_RADIO[0] - 0.32, 0.03, FIELD_RADIO[2] + 0.1)))
    H["radio"] = r.bake(rad)
    # cars -------------------------------------------------------------------
    cars = [((-9.0, 14.0), 18, True), ((4.5, 21.0), -24, True), ((-3.0, 30.0), 70, True),
            ((10.0, 34.0), 8, False), ((-10.5, 42.0), -12, True), ((2.0, 47.0), 30, True),
            ((-6.0, -14.0), 4, False), ((8.5, -20.0), -6, True)]
    pal = [(112, 40, 36), (60, 74, 92), (140, 132, 112)]
    for (cx, cz), yaw, burned in cars:
        r.bake(car(rng.choice(pal), burned, rng), rot_y(yaw), (cx, 0.0, cz))
    H["fire_cars"] = [(-3.0, 1.2, 30.0), (2.0, 1.1, 47.0)]
    # gantry -------------------------------------------------------------------
    g = Mesh()
    for gx in (-15.5, 15.5):
        g.add(box(0.7, 8.6, 0.7, STEEL, center=(gx, 4.3, GANTRY_Z), seg=2.2))
        g.add(box(1.6, 0.4, 1.6, CONCRETE_D, center=(gx, 0.2, GANTRY_Z)))
    g.add(box(31.5, 0.5, 0.5, STEEL, center=(0, 8.2, GANTRY_Z), seg=2.5))
    g.add(box(31.5, 0.3, 0.3, STEEL_D, center=(0, 6.9, GANTRY_Z), seg=2.5))
    # truss diagonals as thin boxes
    for k in range(-15, 16, 2):
        g.add(box(0.12, 1.3, 0.12, STEEL_D, center=(k, 7.55, GANTRY_Z)))
    # catwalk on the south side + railing
    g.add(box(31.0, 0.08, 1.3, (60, 64, 70), center=(0, 6.72, GANTRY_Z - 0.9), seg=3.0))
    g.add(box(31.0, 0.05, 0.05, STEEL_D, center=(0, 7.75, GANTRY_Z - 1.5), seg=3.0))
    for k in range(-15, 16, 3):
        g.add(box(0.05, 1.0, 0.05, STEEL_D, center=(k, 7.25, GANTRY_Z - 1.5)))
    # sign panels (face south, toward the plaza)
    for sx, w, txt in ((-8.0, 7.5, 3), (1.5, 6.0, 2), (9.5, 6.5, 2)):
        g.add(box(w, 2.6, 0.18, SIGN_G, center=(sx, 9.6, GANTRY_Z + 0.2), seg=2.0,
                  cols={"front": SIGN_G}))
        g.add(box(w - 0.3, 0.07, 0.02, (220, 230, 220), center=(sx, 10.75, GANTRY_Z + 0.1)))
        for k in range(txt):
            g.add(box(w * 0.62, 0.32, 0.02, (225, 232, 225), center=(sx - w * 0.1, 10.1 - k * 0.62, GANTRY_Z + 0.09)))
        g.add(box(0.35, 0.9, 0.02, (225, 232, 225), center=(sx + w * 0.36, 9.2, GANTRY_Z + 0.09)))
    H["gantry"] = r.bake(g)
    # light poles ----------------------------------------------------------------
    lp = Mesh()
    for z in range(-30, 140, 22):
        for side in (-1, 1):
            x = 15.2 * side
            lp.add(box(0.22, 9.0, 0.22, STEEL_D, center=(x, 4.5, z)))
            lp.add(box(2.4, 0.15, 0.2, STEEL_D, center=(x - 1.1 * side, 9.0, z)))
            lp.add(box(0.6, 0.12, 0.3, (210, 200, 160), center=(x - 2.1 * side, 8.9, z), emissive=True))
    r.bake(lp)
    # overpass -----------------------------------------------------------------
    op = Mesh()
    op.add(box(80, 1.6, 9, (118, 114, 106), center=(0, 7.4, 120), seg=8,
               cols={"front": (100, 96, 90)}))
    op.add(box(80, 0.9, 0.4, (130, 126, 118), center=(0, 8.6, 115.7), seg=8))
    for px in (-20, -6, 6, 20):
        op.add(box(1.4, 6.6, 1.4, CONCRETE_D, center=(px, 3.3, 120), seg=3))
    r.bake(op)
    # distant skyline + hills ----------------------------------------------------
    sk = Mesh()
    for i in range(46):
        x = -230 + i * 10 + rng.uniform(-3, 3)
        z = 215 + rng.uniform(0, 60)
        h = rng.uniform(8, 26) if abs(x) > 40 else rng.uniform(14, 40)
        w = rng.uniform(6, 14)
        c = rng.randint(50, 60)
        sk.add(box(w, h, w, (c, c + 2, c + 10), center=(x, h / 2, z), skip=("bottom",), emissive=True))
        for _ in range(rng.randint(0, 5)):
            wy = rng.uniform(2, h - 2)
            wx = x + rng.uniform(-w / 2 + 1, w / 2 - 1)
            sk.add(box(0.9, 0.7, 0.1, (150, 128, 82), center=(wx, wy, z - w / 2 - 0.06), emissive=True))
    r.bake(sk)
    hills = Mesh()
    for i in range(14):
        x = -260 + i * 40
        hills.add(prism([(-30, 0), (30, 0), (0, rng.uniform(10, 22))], 6, (44, 48, 50)),
                  M_IDENT, (x, -0.5, 300))
    hills.faces = [(i, c, l, d, True) for i, c, l, d, e in hills.faces]
    r.bake(hills)
    # trash/debris near the plaza
    deb = Mesh()
    for _ in range(40):
        x, z = rng.uniform(-12, 12), rng.uniform(-6, 30)
        if abs(z - BARRIER_Z - 0.3) < 1.2 or -9 < z < 3:
            continue
        s = rng.uniform(0.08, 0.3)
        deb.add(box(s, s * 0.5, s * 1.2, rng.choice([(40, 40, 40), (90, 80, 60), (120, 118, 110)]),
                    center=(x, s * 0.25, z)), rot_y(rng.uniform(0, 90)))
    r.bake(deb)
    return H


def sky(w, h, pitch_span=900):
    """Tall gradient strip; blit with an offset that follows the horizon."""
    import pygame
    surf = pygame.Surface((w, pitch_span))
    top = (26, 30, 40)
    mid = (74, 76, 86)
    hor = (138, 118, 104)
    hy = pitch_span // 2
    for y in range(pitch_span):
        if y < hy:
            t = y / hy
            c = tuple(int(top[i] + (mid[i] - top[i]) * t ** 1.6) for i in range(3))
            if t > 0.82:
                k = (t - 0.82) / 0.18
                c = tuple(int(c[i] + (hor[i] - c[i]) * k) for i in range(3))
        else:
            c = (60, 62, 60)
        pygame.draw.line(surf, c, (0, y), (w, y))
    # cloud bands: long soft streaks
    rng = random.Random(4)
    band = pygame.Surface((w, pitch_span), pygame.SRCALPHA)
    for _ in range(40):
        y = rng.randint(int(hy * 0.30), int(hy * 0.95))
        x = rng.randint(-200, w)
        ww = rng.randint(140, 420)
        hh = rng.randint(2, 6)
        v = rng.randint(70, 110)
        pygame.draw.ellipse(band, (v, v - 4, v - 2, rng.randint(25, 60)), (x, y, ww, hh))
    surf.blit(band, (0, 0))
    return surf, hy
