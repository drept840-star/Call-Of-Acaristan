#!/usr/bin/env python3
"""AE BUILD AK74 - the AK-74 (6P20) authored in code, with no GLB source.

    python tools/ae_build_ak74.py [--length 0.940] [--finish wood|plum|poly]
                                  [--out <path>] [--dump]

House rule: art is authored by code.  Every other weapon in
``src/game/content/meshes`` is an imported GLB (ae_import_k93d /
ae_import_akrifle / ae_import_m7rifle); this one is built from real AK-74
dimensions so it can be re-scaled, re-finished and re-cut without a source
file, a licence or a modelling pass.

Gun space is the ae.mesh/1 weapon convention already used by engine3d.hold and
engine3d.rig: +z = muzzle, +y = up, +x = right, origin = the right hand on the
pistol grip.  A mesh built here drops into ``Humanoid._rifle`` untouched.

Layout is driven by distances from the muzzle (``D``), so every part is placed
by a measured number rather than a hand-tuned offset:

    D part                note
    0.000  muzzle         5.45 brake-compensator, two up-facing oval ports
    0.116  front sight     hooded post on a tapered base, left sling bar
    0.156  gas block       45-degree port, tube rises to the gas-tube axis
    0.180  handguards      wood upper cover + grooved lower, to the trunnion
    0.432  rear sight      tangent leaf on the receiver front (sight radius 316)
    0.455  receiver front  front trunnion / barrel screw
    0.522  magazine        30-round 5.45 box, curved ~18 deg forward
    0.585  trigger         inside the stamped guard
    0.630  GRIP ORIGIN     right hand, z = 0 of gun space
    0.700  receiver rear   rear trunnion, stock tang
    0.940  buttplate       length of pull 0.355, overall 0.940

Output: src/game/content/meshes/ak74.mesh.json
    meta  muzzle / butt / guard / fore landmarks.  engine3d.hold GRIPS["ak74"]
          mirrors them, and tools/smoke_test.py fails if the two drift apart.
"""
import argparse
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import ae_import_k93d as K  # noqa: E402  (reuse its vertex-cluster welder)

OUT = os.path.join(ROOT, "src", "game", "content", "meshes", "ak74.mesh.json")

# ── gun-space frame ─────────────────────────────────────────────────────
MZ = 0.630          # grip origin -> muzzle (m); overall length is 0.940
BORE = 0.040        # bore axis above the grip origin (m)
LEN = 0.940         # real AK-74 overall length (m)

# ── distances from the muzzle (m) ───────────────────────────────────────
D = dict(
    brake=0.058,        # muzzle brake length
    fs_front=0.100,     # front sight base, front face
    fs_rear=0.132,      # front sight base, rear face
    gas_front=0.140,    # gas block
    gas_rear=0.172,
    hg_front=0.180,     # handguards (upper cover + lower)
    hg_rear=0.455,
    trunnion=0.475,     # front trunnion rear face / receiver front region
    sight_front=0.462,  # rear sight base, front face (just behind the handguard)
    sight_back=0.494,   # rear sight base, rear face
    mag_front=0.490,    # magazine well
    mag_rear=0.555,
    guard_front=0.560,  # trigger guard
    guard_rear=0.625,
    trigger=0.585,
    grip_front=0.610,   # pistol grip
    grip_rear=0.680,
    recv_rear=0.675,    # receiver rear / rear trunnion, where the stock bolts on
    cover_front=0.494,  # dust cover, from the rear sight base back
    cover_rear=0.670,
    butt=0.940,         # buttplate face
)

# ── palette ─────────────────────────────────────────────────────────────
STEEL = (54, 58, 66)        # receiver, barrel, gas tube, sights, trunnions
STEEL_D = (38, 41, 47)      # machined steel: gas block, front trunnion
BLACK = (24, 26, 30)        # muzzle brake, bore, small parts
WOOD_D = (86, 44, 26)       # darker lamination, finger grooves

# furniture, furniture-dark, grip, magazine, furniture grain, magazine grain
FINISHES = {
    # AK-74: laminated varnished wood with the plum 5.45 bakelite magazine
    "wood": ((128, 68, 34), WOOD_D, (120, 62, 32), (92, 46, 44), 0.13, 0.10),
    # AK-74M plum polymer furniture
    "plum": ((82, 46, 48), (58, 32, 34), (76, 42, 44), (88, 44, 46), 0.08, 0.09),
    # AK-74M / AK-100 black polymer
    "poly": ((38, 36, 36), (24, 23, 23), (34, 32, 32), (30, 29, 29), 0.06, 0.05),
}


def _z(d):
    """Distance from the muzzle -> gun-space z."""
    return MZ - d


# ── geometry helpers ────────────────────────────────────────────────────
def _grain(col, pts, amt):
    """Deterministic per-face dither (same hash the GLB importers use), so the
    flat-shaded renderer does not band a big wood or steel slab."""
    if amt <= 0.0:
        return tuple(col)
    n = len(pts)
    h = (round(sum(p[0] for p in pts) / n * 5000) * 374761393
         + round(sum(p[1] for p in pts) / n * 5000) * 668265263
         + round(sum(p[2] for p in pts) / n * 2147483647) & 0xFFFFFFFF)
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    k = 0.94 + 0.12 * ((h & 0xFFFF) / 65535.0)
    k *= 1.0 + amt * ((((h >> 16) & 0xFFFF) / 65535.0) * 2 - 1)
    return tuple(min(255, max(0, int(v * k))) for v in col)


class Acc:
    """Face accumulator: verts + (idx, colour) faces in gun space."""

    def __init__(self):
        self.verts = []
        self.faces = []

    def fan(self, pts, col):
        """Convex polygon -> triangles.  ae.mesh/1 assets are triangulated
        (GL packs rig templates as tris), so nothing wider leaves here."""
        for i in range(1, len(pts) - 1):
            b = len(self.verts)
            self.verts.extend((pts[0], pts[i], pts[i + 1]))
            self.faces.append(((b, b + 1, b + 2), col))

    def __len__(self):
        return len(self.faces)


def _rect(cx, cy, hx, hy):
    """Rectangle, counter-clockwise in (x, y) seen from +z."""
    return [(cx - hx, cy - hy), (cx + hx, cy - hy),
            (cx + hx, cy + hy), (cx - hx, cy + hy)]


def _ngon(cx, cy, r, n, phase=0.0, ry=None):
    """Regular n-gon, counter-clockwise in (x, y) seen from +z."""
    ry = r if ry is None else ry
    return [(cx + r * math.cos(phase + 2.0 * math.pi * i / n),
             cy + ry * math.sin(phase + 2.0 * math.pi * i / n))
            for i in range(n)]


def _loft(acc, sections, col, grain=0.0, caps=True):
    """Stitch cross-sections into a solid.

    ``sections`` is [(z, [(x, y), ...]), ...] with an equal point count; it is
    sorted by z, so a part can be written muzzle-first.  Profiles run CCW seen
    from +z, which makes every stitched quad and both caps face outward - the
    renderer is flat-shaded and lights from the normal, so a wound-back face
    reads as a black hole."""
    sections = sorted(sections, key=lambda s: s[0])
    n = len(sections[0][1])
    if any(len(s[1]) != n for s in sections):
        raise ValueError("loft profiles must share a point count")
    for k in range(len(sections) - 1):
        z0, a = sections[k]
        z1, b = sections[k + 1]
        for i in range(n):
            j = (i + 1) % n
            q = [(a[i][0], a[i][1], z0), (a[j][0], a[j][1], z0),
                 (b[j][0], b[j][1], z1), (b[i][0], b[i][1], z1)]
            acc.fan(q, _grain(col, q, grain))
    if caps:
        acc.fan([(x, y, sections[0][0]) for x, y in reversed(sections[0][1])],
                _grain(col, [(x, y, sections[0][0]) for x, y in sections[0][1]], grain))
        acc.fan([(x, y, sections[-1][0]) for x, y in sections[-1][1]],
                _grain(col, [(x, y, sections[-1][0]) for x, y in sections[-1][1]], grain))
    return acc


def _tube(acc, d0, d1, cy, r0, r1, n, col, grain=0.0, cx=0.0, caps=True,
          ry0=None, ry1=None):
    """Tapered round barrel/tube along z between two muzzle distances."""
    return _loft(acc, [(_z(d0), _ngon(cx, cy, r0, n, math.pi / n, ry0)),
                       (_z(d1), _ngon(cx, cy, r1, n, math.pi / n, ry1))],
                 col, grain, caps)


def _mmul(a, b):
    """Row-major 3x3 A.B, matching engine3d.core.m_mul's element order."""
    return tuple(sum(a[i * 3 + k] * b[k * 3 + j] for k in range(3))
                 for i in range(3) for j in range(3))


def _mapply(m, v):
    return (m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
            m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
            m[6] * v[0] + m[7] * v[1] + m[8] * v[2])


def _rx(a):
    """+deg tips +y toward +z (matches engine3d.core.rot_x)."""
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return (1.0, 0.0, 0.0, 0.0, c, -s, 0.0, s, c)


def _rz(a):
    """+deg swings -y out toward +x (matches engine3d.core.rot_z)."""
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return (c, -s, 0.0, s, c, 0.0, 0.0, 0.0, 1.0)


def _obox(acc, hx, hy, hz, col, centre, rz=0.0, rx=0.0, grain=0.0):
    """Box of half-extents at ``centre``, spun about z then about x.

    One deterministic tint per box (from its centre), so a panel of identical
    boxes - magazine ribs, receiver rivets - still reads as separate parts."""
    col = _grain(col, [centre], grain)
    t = Acc()
    _loft(t, [(-hz, _rect(0.0, 0.0, hx, hy)), (hz, _rect(0.0, 0.0, hx, hy))],
          col, 0.0)
    m = _mmul(_rz(rz), _rx(rx)) if (rz or rx) else None
    cx, cy, cz = centre
    for v in t.verts:
        p = _mapply(m, v) if m else v
        acc.verts.append((p[0] + cx, p[1] + cy, p[2] + cz))
    acc.faces.extend(t.faces)
    return acc


def _cbox(acc, x0, y0, z0, x1, y1, z1, col, grain=0.0):
    """Axis-aligned box from two corners."""
    hx, hy = (x1 - x0) / 2.0, (y1 - y0) / 2.0
    return _obox(acc, hx, hy, abs(z1 - z0) / 2.0, col,
                 ((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0), grain=grain)


# ── parts ───────────────────────────────────────────────────────────────
def _brake(acc, P):
    """5.45 mm brake-compensator: a slotted sleeve with two large oval ports
    angled up-and-out (they vent gas up so the muzzle stays down), a front
    crown and a dark bore.  This is what separates an AK-74 from an AKM,
    whose slant brake is a plain angled cut."""
    furn, furn_d, grip, mag, gf, gm = P
    sec = [(_z(d), _ngon(0.0, BORE, r, 10, math.pi / 10))
           for d, r in ((0.000, 0.0100), (0.005, 0.0112), (0.038, 0.0112),
                        (0.046, 0.0096), (0.058, 0.0086))]
    _loft(acc, sec, BLACK, 0.05, caps=False)
    # front crown + bore
    crown = _ngon(0.0, BORE, 0.0112, 10, math.pi / 10)
    acc.fan([(x, y, MZ) for x, y in crown], _grain(BLACK, [(0, BORE, MZ)], 0.04))
    bore = _ngon(0.0, BORE, 0.0060, 8, math.pi / 8)
    # +z winding, so the dark disc faces the camera at the muzzle and wins the
    # painter sort against the crown behind it
    acc.fan([(x, y, MZ + 0.0005) for x, y in bore], (10, 10, 12))
    # two oval ports, angled up and out
    for side in (-1, 1):
        _obox(acc, 0.0035, 0.0055, 0.0095, (12, 12, 14),
              (side * 0.0072, BORE + 0.0062, _z(0.024)), rz=side * 38.0, grain=0.0)
    # the brake's rear step, where it threads onto the barrel
    _tube(acc, 0.055, 0.062, BORE, 0.0092, 0.0082, 8, STEEL, 0.06)


def _barrel(acc, P):
    """Exposed barrel only: muzzle brake -> front sight base, then the span
    from the front sight base through the gas block to the handguard.  The
    chamber end is inside the front trunnion, so building it would be hidden
    tris the painter still has to sort."""
    _tube(acc, 0.060, 0.102, BORE, 0.0070, 0.0074, 8, STEEL, 0.05)
    _tube(acc, 0.130, 0.184, BORE, 0.0074, 0.0078, 8, STEEL, 0.05)


def _front_sight(acc, P):
    """Hooded front post on a tapered base, with the left-side sling bar and
    the cleaning-rod guide underneath."""
    _loft(acc, [(_z(D["fs_front"]), _rect(0.0, BORE + 0.006, 0.0115, 0.0200)),
                (_z(D["fs_rear"]), _rect(0.0, BORE + 0.004, 0.0095, 0.0170))],
          STEEL, 0.07)
    # hood: two ears + a top bridge, the post inside
    for side in (-1, 1):
        _obox(acc, 0.0018, 0.0150, 0.0095, STEEL_D,
              (side * 0.0062, BORE + 0.0390, _z(0.116)), grain=0.07)
    _cbox(acc, -0.0080, BORE + 0.0520, _z(0.126), 0.0080, BORE + 0.0570, _z(0.106),
          STEEL_D, 0.06)
    _obox(acc, 0.0013, 0.0105, 0.0022, (16, 17, 19),
          (0.0, BORE + 0.0330, _z(0.114)), grain=0.0)
    # left sling bar
    _obox(acc, 0.0022, 0.0050, 0.0070, STEEL_D, (-0.0125, BORE - 0.0080, _z(0.126)),
          grain=0.06)


def _gas_block(acc, P):
    """Gas block at the 5.45 port, angled back into the gas tube, with the
    cleaning-rod guide lug below."""
    _loft(acc, [(_z(D["gas_front"]), _rect(0.0, BORE + 0.002, 0.0098, 0.0135)),
                (_z(0.156), _rect(0.0, BORE + 0.014, 0.0092, 0.0200)),
                (_z(D["gas_rear"]), _rect(0.0, BORE + 0.024, 0.0082, 0.0110))],
          STEEL_D, 0.07)
    _obox(acc, 0.0055, 0.0040, 0.0100, STEEL_D, (0.0, BORE - 0.0260, _z(0.158)),
          grain=0.06)


def _gas_tube(acc, P):
    """Gas tube.  Only the span between the upper handguard's rear and the rear
    sight base is exposed, so only that is built: the covered length would be
    hidden tris the painter still sorts, and under a double-sided submit they
    can win against the wood at a glancing angle."""
    _tube(acc, D["hg_rear"], D["sight_front"], BORE + 0.028, 0.0070, 0.0072, 8,
          STEEL, 0.05)


def _rear_sight(acc, P):
    """Tangent rear sight: the base on the receiver front with the leaf folded
    down into it, the notch, and the leaf pivot pin.  Mounted here rather than
    at the receiver's rear, which is what gives the AK its 362 mm sight radius."""
    y0 = BORE + 0.012
    _cbox(acc, -0.0128, y0, _z(D["sight_back"]), 0.0128, y0 + 0.0200,
          _z(D["sight_front"]), STEEL, 0.07)
    # the leaf, folded down and tapering toward the shooter
    _loft(acc, [(_z(D["sight_back"] - 0.004), _rect(0.0, y0 + 0.0245, 0.0092, 0.0048)),
                (_z(D["sight_front"] + 0.004), _rect(0.0, y0 + 0.0220, 0.0098, 0.0058))],
          STEEL_D, 0.07)
    # notch
    _obox(acc, 0.0016, 0.0030, 0.0024, (12, 12, 14),
          (0.0, y0 + 0.0300, _z((D["sight_front"] + D["sight_back"]) / 2.0)))
    # leaf pivot pin
    _obox(acc, 0.0136, 0.0016, 0.0016, STEEL_D,
          (0.0, y0 + 0.0060, _z(D["sight_front"] + 0.012)), grain=0.05)


def _handguards(acc, P):
    """Wood furniture over the barrel: the lower handguard (finger grooves on
    both sides, a steel heat shield inside) and the upper cover over the gas
    tube.  The two meet at the gas-tube axis so no barrel shows through."""
    furn, furn_d, grip, mag, gf, gm = P
    top, bot = BORE + 0.010, BORE - 0.032
    # lower handguard: swells toward the hand then tapers to the gas block
    _loft(acc, [(_z(D["hg_front"]), _rect(0.0, bot + 0.0200, 0.0140, 0.0195)),
                (_z(0.240), _rect(0.0, bot + 0.0215, 0.0172, 0.0210)),
                (_z(0.330), _rect(0.0, bot + 0.0215, 0.0186, 0.0215)),
                (_z(D["hg_rear"]), _rect(0.0, bot + 0.0210, 0.0178, 0.0210))],
          furn, gf)
    # finger grooves: two darker ribs per side, following the swell
    for side in (-1, 1):
        for i, dz in enumerate((0.250, 0.320, 0.390)):
            _obox(acc, 0.0022, 0.0055, 0.0330, furn_d,
                  (side * 0.0172, bot + 0.0210 - 0.0070 + i * 0.0130, _z(dz)),
                  grain=gf * 0.7)
    # upper handguard cover over the gas tube
    _loft(acc, [(_z(D["hg_front"]), _rect(0.0, BORE + 0.0270, 0.0135, 0.0165)),
                (_z(0.240), _rect(0.0, BORE + 0.0275, 0.0158, 0.0172)),
                (_z(D["hg_rear"]), _rect(0.0, BORE + 0.0270, 0.0152, 0.0168))],
          furn, gf)
    # the cover's steel retention lip at the front
    _cbox(acc, -0.0142, BORE + 0.0130, _z(D["hg_front"] + 0.012), 0.0142,
          BORE + 0.0230, _z(D["hg_front"]), STEEL_D, 0.06)
    # cleaning rod under the barrel, running the full handguard length with
    # its hooked end just behind the front sight base
    _tube(acc, 0.134, D["hg_rear"] - 0.003, BORE - 0.0330, 0.0030, 0.0030, 6,
          STEEL_D, 0.05)
    _obox(acc, 0.0030, 0.0030, 0.0055, STEEL_D, (0.0, BORE - 0.0300, _z(0.132)),
          rx=32.0, grain=0.05)


def _receiver(acc, P):
    """Stamped receiver: 1 mm sheet steel, no lightening cuts above the mag
    well (those are an AKM feature), a ribbed dust cover, the rivet rows and
    the right-side selector lever."""
    y0, y1 = BORE - 0.025, BORE + 0.012
    _cbox(acc, -0.0165, y0, _z(D["recv_rear"]), 0.0165, y1, _z(D["trunnion"]),
          STEEL, 0.07)
    # front trunnion: the heavier block the barrel and handguard screw into
    _cbox(acc, -0.0175, y0 - 0.006, _z(D["trunnion"]), 0.0175, y1 + 0.004,
          _z(D["hg_rear"]), STEEL_D, 0.06)
    # dust cover, hinged at the rear, with its longitudinal stiffening rib
    _cbox(acc, -0.0156, y1, _z(D["cover_rear"]), 0.0156, y1 + 0.0150, _z(D["cover_front"]),
          STEEL, 0.07)
    _cbox(acc, -0.0058, y1 + 0.0150, _z(D["cover_rear"] - 0.010), 0.0058,
          y1 + 0.0210, _z(D["cover_front"] + 0.006), STEEL, 0.06)
    # recoil-spring housing / cover latch at the rear
    _cbox(acc, -0.0140, y0 - 0.004, _z(D["recv_rear"] + 0.014), 0.0140, y1 + 0.008,
          _z(D["recv_rear"]), STEEL_D, 0.06)
    # rivet rows: three above the mag well on each side
    for side in (-1, 1):
        for dz in (0.478, 0.512, 0.546):
            _obox(acc, 0.0018, 0.0018, 0.0018, STEEL_D,
                  (side * 0.0172, y0 + 0.0200, _z(dz)), grain=0.04)
    # selector lever, stamped, down in the automatic position
    _loft(acc, [(_z(0.470), _rect(0.0195, y1 - 0.004, 0.0016, 0.0075)),
                (_z(0.560), _rect(0.0198, y0 + 0.0235, 0.0016, 0.0085)),
                (_z(0.612), _rect(0.0198, y0 + 0.0060, 0.0016, 0.0070))],
          STEEL, 0.08)
    # magazine catch, ahead of the trigger guard
    _obox(acc, 0.0048, 0.0052, 0.0070, STEEL_D, (0.0, y0 - 0.0060, _z(0.552)),
          grain=0.06)


def _magazine(acc, P):
    """30-round 5.45 box magazine.  Curved ~18 deg forward (the taper a
    double-stack box needs to feed), ribs on both flanks, a thicker steel
    floorplate and the catch notch at the rear top.  The 5.45 mag is plum
    bakelite by default; --finish poly gives the black AK-74M one."""
    furn, furn_d, grip, mag, gf, gm = P
    # (y, z_front, z_rear, half-width): the front face sweeps further forward
    rows = ((0.012, 0.140, 0.075, 0.0145),
            (-0.035, 0.148, 0.080, 0.0145),
            (-0.080, 0.157, 0.090, 0.0142),
            (-0.120, 0.172, 0.104, 0.0138),
            (-0.152, 0.192, 0.122, 0.0134))
    _mag_body(acc, rows, mag, gm)
    # floorplate: a slightly proud steel lip
    y, zf, zr, hx = rows[-1]
    zc, hz = (zf + zr) / 2.0, (zf - zr) / 2.0
    _obox(acc, hx + 0.0012, 0.0048, hz + 0.0012, STEEL_D,
          (0.0, y - 0.0060, zc), rx=-20.0, grain=0.05)
    # flank ribs (bakelite mags are moulded with them; they also break up the
    # biggest flat slab on the gun, which is what bands under flat shading)
    for side in (-1, 1):
        for i in range(4):
            y = 0.000 - i * 0.040
            zf, zr = _mag_z(rows, y)
            zc, hz = (zf + zr) / 2.0, (zf - zr) / 2.0
            hx = _mag_hx(rows, y)
            _obox(acc, 0.0016, 0.0055, hz * 0.72, mag,
                  (side * (hx + 0.0004), y, zc), rx=-6.0 - i * 3.0, grain=gm)
    # catch notch at the rear top
    _obox(acc, 0.0090, 0.0048, 0.0035, STEEL_D, (0.0, 0.0100, rows[0][2] + 0.0010),
          grain=0.05)


def _mag_z(rows, y):
    """Interpolated (z_front, z_rear) of the magazine wall at height y."""
    for i in range(len(rows) - 1):
        y0, zf0, zr0, _ = rows[i]
        y1, zf1, zr1, _ = rows[i + 1]
        if y <= y0 and y >= y1:
            t = (y0 - y) / max(1e-9, y0 - y1)
            return zf0 + (zf1 - zf0) * t, zr0 + (zr1 - zr0) * t
    return rows[-1][1], rows[-1][2]


def _mag_hx(rows, y):
    for i in range(len(rows) - 1):
        y0, _a, _b, hx0 = rows[i]
        y1, _c, _d, hx1 = rows[i + 1]
        if y <= y0 and y >= y1:
            t = (y0 - y) / max(1e-9, y0 - y1)
            return hx0 + (hx1 - hx0) * t
    return rows[-1][3]


def _mag_body(acc, rows, col, grain):
    """Stack the magazine rows into a ring loft.

    The magazine's long axis is y, not z, so ``_loft`` (which stitches along z)
    does not apply: each row is a closed rectangle in (x, z) at a height, and
    the walls are stitched downward.  That makes the curve a real loft instead
    of a column of tilted boxes, which is what reads as "AK magazine"."""
    for i in range(len(rows) - 1):
        y0, zf0, zr0, hx0 = rows[i]
        y1, zf1, zr1, hx1 = rows[i + 1]
        zc0, hz0 = (zf0 + zr0) / 2.0, (zf0 - zr0) / 2.0
        zc1, hz1 = (zf1 + zr1) / 2.0, (zf1 - zr1) / 2.0
        r0 = [(x, y0, z) for x, z in ((-hx0, zc0 - hz0), (hx0, zc0 - hz0),
                                      (hx0, zc0 + hz0), (-hx0, zc0 + hz0))]
        r1 = [(x, y1, z) for x, z in ((-hx1, zc1 - hz1), (hx1, zc1 - hz1),
                                      (hx1, zc1 + hz1), (-hx1, zc1 + hz1))]
        for k in range(4):
            j = (k + 1) % 4
            q = [r0[k], r0[j], r1[j], r1[k]]
            acc.fan(q, _grain(col, q, grain))
    # top and bottom caps
    y0, zf0, zr0, hx0 = rows[0]
    zc0, hz0 = (zf0 + zr0) / 2.0, (zf0 - zr0) / 2.0
    top = [(-hx0, y0, zc0 - hz0), (hx0, y0, zc0 - hz0),
           (hx0, y0, zc0 + hz0), (-hx0, y0, zc0 + hz0)]
    acc.fan(list(reversed(top)), _grain(col, top, grain))


def _trigger(acc, P):
    """Stamped trigger guard and the curved trigger inside it."""
    y0 = BORE - 0.030
    # guard: front riser, bottom bow, rear riser
    _cbox(acc, -0.0032, y0 - 0.0320, _z(D["guard_front"]), 0.0032, y0 + 0.0080,
          _z(D["guard_front"] - 0.010), STEEL_D, 0.06)
    _cbox(acc, -0.0032, y0 - 0.0360, _z(D["guard_rear"] - 0.008), 0.0032,
          y0 - 0.0280, _z(D["guard_front"] - 0.008), STEEL_D, 0.06)
    _cbox(acc, -0.0032, y0 - 0.0320, _z(D["guard_rear"]), 0.0032, y0 + 0.0100,
          _z(D["guard_rear"] - 0.010), STEEL_D, 0.06)
    # trigger, curved back toward the grip
    _loft(acc, [(_z(0.578), _rect(0.0, y0 - 0.0030, 0.0028, 0.0100)),
                (_z(0.592), _rect(0.0, y0 - 0.0150, 0.0028, 0.0085)),
                (_z(0.600), _rect(0.0, y0 - 0.0240, 0.0028, 0.0060))],
          BLACK, 0.05)


def _grip(acc, P):
    """Pistol grip, raked ~20 deg back from the receiver.  The gun-space
    origin is its top, so the right hand lands where the wood is."""
    furn, furn_d, grip, mag, gf, gm = P
    # (y, z_front, z_rear, half-width) top -> bottom; raked 17 deg back, which
    # is the AK's grip angle.  The top deck sits on the gun-space origin, so
    # the rig's right-hand joint lands in the web of the hand.
    rows = ((0.012, 0.016, -0.030, 0.0135),
            (-0.020, 0.006, -0.042, 0.0148),
            (-0.062, -0.006, -0.058, 0.0152),
            (-0.100, -0.018, -0.072, 0.0145),
            (-0.132, -0.028, -0.084, 0.0138))
    for i in range(len(rows) - 1):
        y0, f0, r0, w0 = rows[i]
        y1, f1, r1, w1 = rows[i + 1]
        a = [(-w0, y0, f0), (w0, y0, f0), (w0, y0, r0), (-w0, y0, r0)]
        b = [(-w1, y1, f1), (w1, y1, f1), (w1, y1, r1), (-w1, y1, r1)]
        for k in range(4):
            j = (k + 1) % 4
            q = [a[k], a[j], b[j], b[k]]
            acc.fan(q, _grain(grip, q, gf))
    # the grip's top deck (the web of the hand rests here, at the origin)
    y0, f0, r0, w0 = rows[0]
    deck = [(-w0, y0, f0), (w0, y0, f0), (w0, y0, r0), (-w0, y0, r0)]
    acc.fan(list(reversed(deck)), _grain(grip, deck, gf))
    # bottom cap
    y1, f1, r1, w1 = rows[-1]
    base = [(-w1, y1, f1), (w1, y1, f1), (w1, y1, r1), (-w1, y1, r1)]
    acc.fan(base, _grain(furn_d, base, gf))
    # chequered panels on both flanks, following the grip's own rake
    for side in (-1, 1):
        _obox(acc, 0.0012, 0.0380, 0.0220, furn_d,
              (side * 0.0152, -0.0560, -0.0330), grain=gf * 0.6)


def _stock(acc, P):
    """Fixed wooden stock with the AK's slight downward slope to the butt, a
    steel buttplate, the left-side rear sling swivel and the stock tang that
    bolts into the rear trunnion."""
    furn, furn_d, grip, mag, gf, gm = P
    # (z, half-width, y_bottom, y_top) from the receiver rear to the butt.  The
    # wrist comes down to y -0.020 so it closes the junction with the grip's
    # backstrap - leaving it at the receiver's underside put a 55 mm hole in
    # the side silhouette between the two parts.
    rows = ((-0.045, 0.0140, -0.020, 0.052),
            (-0.085, 0.0140, -0.024, 0.050),
            (-0.140, 0.0162, -0.028, 0.046),
            (-0.200, 0.0192, -0.034, 0.040),
            (-0.258, 0.0210, -0.042, 0.034),
            (-0.308, 0.0218, -0.046, 0.032))
    sec = [(z, [(x, y) for x, y in ((-hx, yb), (hx, yb), (hx, yt), (-hx, yt))])
           for z, hx, yb, yt in rows]
    _loft(acc, sec, furn, gf, caps=False)
    # butt face (wood) + the stamped steel buttplate proud of it
    z, hx, yb, yt = rows[-1]
    cap = [(-hx, yb, z), (hx, yb, z), (hx, yt, z), (-hx, yt, z)]
    acc.fan(list(reversed(cap)), _grain(furn, cap, gf))
    _loft(acc, [(z - 0.012, _rect(0.0, (yb + yt) / 2.0, hx + 0.0012, (yt - yb) / 2.0 + 0.0012)),
                (z, _rect(0.0, (yb + yt) / 2.0, hx + 0.0018, (yt - yb) / 2.0 + 0.0018))],
          STEEL_D, 0.05)
    # the buttplate's centre ridge
    _obox(acc, 0.0022, 0.0380, 0.0016, STEEL, (0.0, (yb + yt) / 2.0, z - 0.0138),
          grain=0.05)
    # rear sling swivel, left side
    _obox(acc, 0.0022, 0.0060, 0.0090, STEEL_D, (-0.0200, -0.0300, -0.250), grain=0.05)


def build(finish="wood", length=LEN):
    """-> (verts, faces, meta) in gun space, scaled to ``length`` overall."""
    if finish not in FINISHES:
        raise ValueError("unknown finish %r (wood|plum|poly)" % finish)
    P = FINISHES[finish]
    acc = Acc()
    counts = {}
    for name, fn in (("brake", _brake), ("barrel", _barrel),
                     ("front_sight", _front_sight), ("gas_block", _gas_block),
                     ("gas_tube", _gas_tube), ("rear_sight", _rear_sight),
                     ("handguards", _handguards), ("receiver", _receiver),
                     ("magazine", _magazine), ("trigger", _trigger),
                     ("grip", _grip), ("stock", _stock)):
        before = len(acc)
        fn(acc, P)
        counts[name] = len(acc) - before

    # landmarks, straight from the frame constants
    butt_y = (0.032 + -0.046) / 2.0
    meta = {
        "length_m": round(length, 4),
        "finish": finish,
        "muzzle": [0.0, round(BORE, 4), round(MZ, 4)],
        "butt": [0.0, round(butt_y, 4), round(-0.310, 4)],
        "guard": [0.0, round(BORE - 0.030, 4), round(_z(D["guard_front"]), 4)],
        "fore": [0.0, round(BORE - 0.011, 4),
                 round((_z(D["hg_front"]) + _z(D["hg_rear"])) / 2.0, 4)],
        "bore_y": round(BORE, 4),
        "sight_radius_m": round((D["sight_front"] + D["sight_back"]) / 2.0 - 0.116, 4),
        "lop_m": round(MZ - D["trigger"] + 0.310, 4),
        "parts": counts,
    }

    verts = [tuple(v) for v in acc.verts]
    tris = [(f[0], 0, 0, None, f[1]) for f in acc.faces]
    if abs(length - LEN) > 1e-9:
        s = length / LEN
        verts = [(x * s, y * s, z * s) for x, y, z in verts]
        for k in ("muzzle", "butt", "guard", "fore"):
            meta[k] = [round(c * s, 4) for c in meta[k]]
        meta["length_m"] = round(length, 4)
        meta["sight_radius_m"] = round(meta["sight_radius_m"] * s, 4)
        meta["lop_m"] = round(meta["lop_m"] * s, 4)
    return verts, tris, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--length", type=float, default=LEN,
                    help="overall length in metres (default %.3f, the real 6P20)" % LEN)
    ap.add_argument("--finish", default="wood", choices=sorted(FINISHES),
                    help="furniture: wood (default), plum or poly AK-74M")
    ap.add_argument("--cell", type=float, default=0.004,
                    help="vertex-cluster cell in metres (default 4 mm)")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--dump", action="store_true", help="print the per-part tri table")
    args = ap.parse_args()

    verts, tris, meta = build(args.finish, args.length)
    out_v, out_f = K._cluster(verts, tris, args.cell)

    data = {
        "schema": "ae.mesh/1",
        "id": "ak74",
        "verts": [[round(c, 5) for c in v] for v in out_v],
        "faces": [[f[0], f[1]] for f in out_f],
        "tris": len(out_f),
        "source": "tools/ae_build_ak74.py",
        "meta": {k: v for k, v in meta.items()},
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")

    print("AE BUILD AK74: %d tris / %d verts  (finish %s, %.3f m, cell %.4f)"
          % (len(out_f), len(out_v), args.finish, args.length, args.cell))
    print("  muzzle", data["meta"]["muzzle"], " butt", data["meta"]["butt"])
    print("  guard", data["meta"]["guard"], " fore", data["meta"]["fore"])
    print("  sight radius %.3f m   length of pull %.3f m"
          % (data["meta"]["sight_radius_m"], data["meta"]["lop_m"]))
    if args.dump:
        for name, n in sorted(meta["parts"].items(), key=lambda kv: -kv[1]):
            print("    %-12s %4d tris" % (name, n))
    print("  ->", os.path.relpath(os.path.abspath(args.out), ROOT))


if __name__ == "__main__":
    main()
