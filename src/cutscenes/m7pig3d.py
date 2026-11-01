"""Bodi's low-poly pig and distance-driven, cached walk poses.

Local +x is forward, y is up.  Keeping the walk poses as meshes means
both RPE6 backends use exactly the same geometry without a per-frame rebuild.
"""
import math
from functools import lru_cache

from engine3d.core import Mesh, box, m_apply, rot_z

SKIN = (215, 151, 147)
LIGHT = (225, 162, 157)
DARK = (170, 109, 106)
SNOUT = (211, 135, 133)
HOOF = (78, 57, 54)
EYE = (37, 29, 29)
NOSTRIL = (108, 63, 63)
FRAMES = 32
STRIDE = 0.48  # metres travelled in a complete walk cycle
STANCE = 0.68  # portion of the cycle that each hoof stays planted


def _oval(m, center, radius, col, rings=8, sides=10):
    """Faceted ellipsoid with its longitudinal axis along x."""
    cx, cy, cz = center
    rx, ry, rz = radius
    rows = []
    for i in range(rings + 1):
        a = -math.pi / 2 + math.pi * i / rings
        rows.append([(cx + rx * math.sin(a),
                      cy + ry * math.cos(a) * math.cos(math.tau * j / sides),
                      cz + rz * math.cos(a) * math.sin(math.tau * j / sides))
                     for j in range(sides)])
    for i in range(rings):
        for j in range(sides):
            k = (j + 1) % sides
            if i == 0:
                pts = (rows[i][j], rows[i+1][j], rows[i+1][k])
            elif i == rings - 1:
                pts = (rows[i][j], rows[i+1][j], rows[i][k])
            else:
                pts = (rows[i][j], rows[i+1][j], rows[i+1][k], rows[i][k])
            m.face(pts, col, 2, True)


def _ear(m, side, bob):
    """Broad floppy ear, with a smaller inset on its outward-facing surface."""
    outer = [(0.17, 0.56, 0.14), (0.19, 0.65, 0.17),
             (0.18, 0.69, 0.25), (0.28, 0.64, 0.30),
             (0.36, 0.57, 0.19)]
    front = [(x, y + bob, side * z) for x, y, z in outer]
    back = [(x, y + bob, side * (z - 0.018)) for x, y, z in outer]
    m.face(front, LIGHT, 2, True)
    m.face(back, DARK, 2, True)
    for i in range(len(front)):
        j = (i + 1) % len(front)
        m.face((front[i], front[j], back[j], back[i]), SKIN, 2, True)
    # Inset sits on the visible side rather than floating above the ear.
    inner = [(0.205, 0.586, 0.166), (0.215, 0.638, 0.187),
             (0.205, 0.672, 0.247), (0.278, 0.631, 0.281),
             (0.325, 0.582, 0.194)]
    m.face([(x, y + bob, side * (z + 0.004)) for x, y, z in inner],
           SNOUT, 2, True)


def _disk(m, axis, center, radius, col, sides=10):
    """Flat oval facing the snout (+x) or cheek (z)."""
    x, y, z = center
    pts = []
    for j in range(sides):
        a = math.tau * j / sides
        if axis == "x":
            pts.append((x, y + radius[0] * math.cos(a), z + radius[1] * math.sin(a)))
        else:
            pts.append((x + radius[0] * math.cos(a), y + radius[1] * math.sin(a), z))
    m.face(pts, col, 2, True)


def _snout(m, bob):
    """A single rounded snout with a broad, flat nose and visible nostrils."""
    cy, n = 0.37 + bob, 10
    back = [(0.545, cy + 0.092 * math.cos(math.tau*j/n),
             0.121 * math.sin(math.tau*j/n)) for j in range(n)]
    front = [(0.632, cy + 0.099 * math.cos(math.tau*j/n),
              0.137 * math.sin(math.tau*j/n)) for j in range(n)]
    for j in range(n):
        k = (j + 1) % n
        m.face((back[j], back[k], front[k], front[j]), SNOUT, 2, True)
    # Build the nose as small coplanar polygons, with the nostrils as actual
    # surface patches. This keeps them visible in the software painter too.
    cuts = (-1.0, -0.65, -0.47, -0.25, 0.0, 0.25, 0.47, 0.65, 1.0)
    levels = (-1.0, -0.45, 0.0, 0.45, 1.0)
    def point(z, y):
        return (0.632, cy + 0.099 * math.sqrt(max(0.0, 1.0-z*z)) * y, 0.137*z)
    for i in range(len(cuts)-1):
        for j in range(len(levels)-1):
            a, b = cuts[i], cuts[i+1]
            u, v = levels[j], levels[j+1]
            color = NOSTRIL if i in (2, 5) and j == 2 else (224, 151, 147)
            if b == 1.0:
                pts = (point(a,u), point(b,u), point(a,v))
            elif a == -1.0:
                pts = (point(a,u), point(b,u), point(b,v))
            else:
                pts = (point(a,u), point(b,u), point(b,v), point(a,v))
            m.face(pts, color, 2, True)


def _round_column(width, height, depth, color, sides=8):
    """An eight-sided, softly faceted leg or hoof, centred at the origin."""
    m = Mesh()
    rings = [[(width * 0.5 * math.cos(math.tau*j/sides), y,
               depth * 0.5 * math.sin(math.tau*j/sides)) for j in range(sides)]
             for y in (-height/2, height/2)]
    m.face(rings[0], color, 2, True)
    m.face(rings[1], color, 2, True)
    for j in range(sides):
        k = (j + 1) % sides
        m.face((rings[0][j], rings[0][k], rings[1][k], rings[1][j]), color, 2, True)
    return m


def _tail(m, bob):
    """A short rounded corkscrew, rather than a rigid square peg."""
    points = [(-0.50, 0.49), (-0.57, 0.50), (-0.61, 0.54),
              (-0.64, 0.58), (-0.69, 0.58), (-0.72, 0.55),
              (-0.71, 0.51), (-0.67, 0.50), (-0.64, 0.52),
              (-0.65, 0.55)]
    for i, (x, y) in enumerate(points):
        if i == len(points) - 1:
            break
        x2, y2 = points[i+1]
        dx, dy = x2-x, y2-y
        length = math.hypot(dx, dy)
        angle = math.degrees(math.atan2(-dx, dy))
        radius = 0.030 if i < 2 else 0.024
        m.add(_round_column(radius, length + 0.009, radius, SKIN, 6), rot_z(angle),
              t=((x+x2)/2, (y+y2)/2 + bob, 0))


def foot_target(cycle, offset):
    """Hoof offset and lift in local space for one staggered step.

    The stance travels backwards at exactly the body's forward speed, so a
    planted hoof stays in the same world position. During swing it arcs forward.
    """
    t = (cycle + offset) % 1.0
    half_step = STRIDE * STANCE / 2.0
    if t < STANCE:
        return half_step - STRIDE * t, 0.0
    u = (t - STANCE) / (1.0 - STANCE)
    smooth = 0.5 - 0.5 * math.cos(math.pi * u)
    return -half_step + 2.0 * half_step * smooth, 0.075 * math.sin(math.pi * u)


def _bone(m, a, b, width, depth, col):
    """A tapered-looking two-piece leg: connect a joint to its neighbour."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    # Local box y points up; rotation of a downward vector points toward b.
    angle = math.degrees(math.atan2(dx, -dy))
    m.add(_round_column(width, length + 0.018, depth, col), rot_z(angle),
          t=((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, a[2]))


@lru_cache(maxsize=FRAMES + 1)
def pig_pose(frame=-1):
    """Standing pose (-1), or one of 32 staggered walking poses."""
    m = Mesh()
    phase = math.tau * (frame % FRAMES) / FRAMES if frame >= 0 else 0.0
    bob = 0.004 * math.sin(phase * 2) if frame >= 0 else 0.0
    # Plump silhouette with a softly faceted shoulder and cheek.
    _oval(m, (-0.09, 0.38 + bob, 0), (0.46, 0.255, 0.255), SKIN)
    _oval(m, (0.29, 0.415 + bob, 0), (0.25, 0.205, 0.205), LIGHT)
    _oval(m, (0.46, 0.37 + bob, 0), (0.13, 0.12, 0.15), LIGHT, 6, 10)
    _snout(m, bob)
    for side in (-1, 1):
        _ear(m, side, bob)
        # Small dark eyes and warm highlights, seated on either cheek.
        _disk(m, "z", (0.375, 0.487 + bob, side * 0.191), (0.026, 0.024), EYE, 8)
        _disk(m, "z", (0.383, 0.496 + bob, side * 0.193), (0.007, 0.007),
              (252, 227, 209), 8)
    # Four distinct footfalls: rear left, front left, rear right, front right.
    # Feet remain level; the shoulder, knee and ankle articulate independently.
    cycle = (frame % FRAMES) / FRAMES if frame >= 0 else 0.0
    for x in (-0.34, 0.21):
        for side in (-1, 1):
            offset = {(False, -1): 0.0, (True, -1): 0.75,
                      (False, 1): 0.5, (True, 1): 0.25}[(x > 0, side)]
            dx, lift = foot_target(cycle, offset) if frame >= 0 else (0.0, 0.0)
            z = side * 0.15
            hip = (x, 0.30 + bob, z)
            ankle = (x + dx, 0.071 + lift, z)
            # A small natural knee bend, reversed between front and hind legs.
            knee = ((hip[0] + ankle[0]) * 0.5 + (0.025 if x > 0 else -0.025),
                    (hip[1] + ankle[1]) * 0.5 + 0.015, z)
            _bone(m, hip, knee, 0.13, 0.13, SKIN)
            _bone(m, knee, ankle, 0.095, 0.105, SKIN)
            m.add(_round_column(0.145, 0.07, 0.135, HOOF),
                  t=(x + dx, 0.035 + lift, z))
            # Subtle cloven split on the front of each hoof.
            m.add(box(0.005, 0.035, 0.012, (50, 36, 34)),
                  t=(x + dx + 0.073, 0.026 + lift, z))
    _tail(m, bob)
    return m


def walking_frame(distance):
    return int((distance / STRIDE % 1.0) * FRAMES) % FRAMES


# ── the fall, and what is left of it ────────────────────────────────────────
# Bodi's pig can be shot in the raid.  The house convention is local +x
# forward, y up, so the body falls by rolling about z: a negative angle
# swings its back away from +x and lays it on one flank (``rot_z``).
PIVOT = (0.0, 0.38, 0.0)                 # the body's centre: it turns about this
HITBOX = (0.02, 0.34, 0.0, 0.36)         # one sphere: centre x, y, z and radius
HIT_PTS = (1.0, 0.7, 0.5)                # where along the ray pellets stop, by hit offset
HIT_MID = HITBOX[3]                      # a hit at most this far off-centre stops at the side
DEAD_PAD = 0.02                          # the carcass lies a little lower: no gap at the shoulder
FALL_S = 0.55                            # knife-edge to down, over this long
HOP = 0.07                               # how far the hooves leave the dirt, twice
HOP_AT = (0.16, 0.44, 0.72)              # the fall fractions between those kicks
FALL_DEG = 64.0                          # keeled over onto its flank
SETTLE_DEG = 58.0                        # what it rocks back to once it lands
GROUND_DROP = 0.10                       # the body turns about a centre this far up


def _hoof_lift(k):
    """How far the hooves leave the dirt ``k`` into the fall: it kicks off,
    lands, and the shoulder takes the second bump."""
    out = 0.0
    for start, end in zip(HOP_AT[::2], HOP_AT[1::2]):
        if start < k < end:
            out += HOP * math.sin(math.pi * (k - start) / (end - start))
    return out


def _falling(m, k, out=None):
    """The pig ``k`` 0..1 through the fall: it kicks off, goes over, hits the
    dirt and rocks back a few degrees there before it stops.  It always ends
    with its lowest point on the ground, so no part sinks into it.  Returns a
    new mesh, or the reused ``out`` when one is handed in."""
    deg = -FALL_DEG * k
    if k >= 1.0:
        deg = -SETTLE_DEG
    px, py, pz = PIVOT
    rot = rot_z(deg)
    if out is None:
        out = Mesh()
        out.faces = list(m.faces)
        out.verts = [None] * len(m.verts)
    for i, (x, y, z) in enumerate(m.verts):
        rx, ry, rz = m_apply(rot, (x - px, y - py, z - pz))
        out.verts[i] = (rx + px, ry + py + GROUND_DROP, rz + pz)
    low = min(v[1] for v in out.verts) - _hoof_lift(k) + DEAD_PAD
    if low != 0.0:
        out.verts = [(x, y - low, z) for x, y, z in out.verts]
    return out


@lru_cache(maxsize=8)
def pig_dead(step=0):
    """The fall as canned meshes, so a dying pig costs no per-frame rebuild:
    ``step`` 0-3 is the quarter of ``FALL_S`` it is in (``step`` 4 is the
    landed, settled body).  Never mutate the result: ``put`` caches packed
    rows by identity."""
    return _falling(pig_pose(-1), min(1.0, (step + 1) / 4.0))


@lru_cache(maxsize=1)
def pig_flat():
    """What is left on the farm: the standing pose and its fall to the dirt
    together.  A dev jump straight to a dead pig therefore shows no hole
    where the shoulder was.  Floor is y=0."""
    m = Mesh()
    m.add(pig_pose(-1))
    m.add(_falling(pig_pose(-1), 1.0))
    low = min(v[1] for v in m.verts)
    m.verts = [(x, y - low - 0.01, z) for x, y, z in m.verts]
    return m
