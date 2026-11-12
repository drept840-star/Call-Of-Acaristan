"""Mission 8 Revenge - the tractor chase set: the back roads from Route 12 to
the Kim Kim rail crossing, baked once.

The road runs along +z on a gentle curve (``road_x``); the four sections sit
end to end: farm track, hay bales and the ditch, the Route 12 wrecks, the
crossing.  Moving things (tractor, trailer, Guard cars, gun truck, barrier
arm, train) are cached meshes queued per frame through ``put``.

The look is the M7 farm's dawn: its textures, light and sky, patchwork fields,
hedgerows, poplar rows, farmsteads, villages and far ridges along the route.
The Guard cars are the ``car_m2`` model repainted, the gun truck is the M7
``truck_m7`` with a gun on the bed.

Axes: x east, y up, z north (the direction of travel).
"""
import math
import random

from engine3d import Mesh, box, quad_xz
from engine3d.core import Light, rot_y
from engine3d.textures import tex
from cutscenes import m7world3d as W7
from cutscenes import m7palette3d as P

RES = (640, 448)
LOOK = W7.LOOKS["dawn"]
FOG = LOOK["fog"]
FOG_START, FOG_END = 45.0, 270.0
SET_Z0 = -520.0    # the set runs this far back down the road: chasers spawn ~350 m behind the eye

SECTIONS = (0.0, 380.0, 960.0, 1540.0)   # farm, ditch, wrecks, crossing start z
DITCH_Z = 700.0
CROSSING_Z = 1960.0                      # the rails cross the road here
BARRIER_Z = CROSSING_Z - 9.0
END_Z = CROSSING_Z
ROAD_W = 7.0
# Each chase section has its own near-road silhouettes, visible from the
# rear-facing trailer camera.  The distant villages/field patches alone read
# as the same scenery repeated when travelling at 11 m/s.
ROADSIDE_SITES = (
    ("farm_gate", 135.0, 1, 16.0), ("orchard", 315.0, -1, 20.0),
    ("hay_yard", 490.0, 1, 19.0), ("pump_house", 830.0, -1, 19.0),
    ("guard_post", 1050.0, 1, 18.0), ("memorial", 1410.0, -1, 19.0),
    ("freight_depot", 1670.0, 1, 21.0), ("watchtower", 1840.0, -1, 20.0),
)
# Near-road set pieces, one stretch each, so no two minutes of the chase look
# alike: (name, z0, z1).  The power line skips the woods and the cutting.
ZONES = (
    ("hamlet", 150.0, 260.0), ("woods", 420.0, 600.0), ("pond", 615.0, 690.0),
    ("kolkhoz", 760.0, 900.0), ("petrol", 1000.0, 1080.0), ("cutting", 1150.0, 1300.0),
    ("bus_stop", 1340.0, 1460.0), ("siding", 1555.0, 1645.0), ("border_fence", 1700.0, 1900.0),
)
NO_POLES = ((410.0, 610.0), (1140.0, 1310.0))
NO_VERGE = ((420.0, 600.0), (1150.0, 1300.0), (1340.0, 1460.0), (1700.0, 1900.0))
CUT_H = 5.5                              # cutting depth below the fields
OVERPASS_Z = 1232.0
TRAIN_LAST_X = 6.5                       # the last car's rear, east of the road
ASPHALT_FROM = SECTIONS[2] - 40.0        # Route 12 tarmac from here on

# Guard car (car_m2 at CAR_S), local forward +z
CAR_S = 1.4
CAR_TYRES = tuple((sx, 0.39, sz) for sz in (1.25, -1.25) for sx in (-0.82, 0.82))
CAR_TYRE_R = 0.42
CAR_SEAT = (-0.42, 0.12, -0.2)           # driver pelvis
CAR_DRIVER = (-0.42, 1.0, -0.2)          # driver head/chest hit point
# gun truck (truck_m7), local forward +z
TRUCK_TYRES = tuple((sx, 0.45, sz) for sz in (1.9, -1.0, -2.0) for sx in (-0.85, 0.85))
TRUCK_TYRE_R = 0.48
TRUCK_SEAT = (-0.5, 1.45, 0.55)
TRUCK_DRIVER = (-0.5, 2.3, 0.55)
TRUCK_BED = (0.0, 1.29, -1.9)            # gunner's feet
TRUCK_GUN = (0.0, 2.45, 0.45)            # muzzle end, over the cab

# Collision footprints in the x/z plane (metres).  Circles sized from the body
# hit spheres in chase3d.targets() and the tyre spans above: a jeep is ~2.5 m
# long and ~2.4 m wide, the truck a little longer.  Used for the push-out so
# cars, the tractor/trailer and the burned wrecks read as solid.
CAR_R = 1.35
TRUCK_R = 1.70
TRACTOR_R = 1.60
TRAILER_R = 1.60
WRECK_R = 1.50

# Biribel's LMG rides a pintle post bolted through the trailer bed; the gun
# swings on a yoke at its top and Biribel walks round the post with it.
MOUNT = (0.0, -0.85)                     # trailer-local x, z of the post
POST_TOP = 2.22                          # trailer-local height of the swivel collar
# gun space (right, up, forward; origin on the pistol grip), tools/ae_import_lmg.py
LMG_PIVOT = (0.0, 0.035, 0.31)           # trunnion pin under the handguard root
LMG_CAN = (0.0, -0.059, 0.192)           # centre of the belt can under the receiver
LMG_HINGE = (0.0, 0.125, 0.255)          # feed cover hinge, front of the receiver
LMG_MUZZLE = (0.0, 0.0877, 0.7932)
STOCK_CUT_Z = -0.10                 # faces wholly behind this are the shoulder
                                    # stock: cut, the gun rides a pintle
RACK = (-0.34, -0.14, (-0.09, 0.09))     # yoke-local spare can tray: x, top y, can z

GUARD_PAINT = (66, 74, 56)

_cache = {}


def road_x(z):
    if z >= CROSSING_Z - 120.0:
        k = min(1.0, (z - (CROSSING_Z - 120.0)) / 80.0)
        return _curve(z) * (1.0 - k)
    return _curve(z)


def _curve(z):
    return 7.0 * math.sin(z / 95.0) + 3.0 * math.sin(z / 41.0 + 1.3)


def road_yaw(z):
    dx = road_x(z + 1.0) - road_x(z - 1.0)
    return math.degrees(math.atan2(dx, 2.0))


def ditch_y(z):
    """The ditch jump: the track climbs the culvert embankment over the
    drainage ditch and the tractor flies off the far side.  Never below the
    fields."""
    d = z - DITCH_Z
    if -16.0 < d < -6.0:
        return 1.0 * math.sin(0.5 * math.pi * (d + 16.0) / 10.0)
    if -6.0 <= d < 0.0:
        return 1.0 - 1.0 * ((d + 6.0) / 6.0) ** 2
    return 0.0


def ditch_pitch(z):
    """Nose-up degrees for a body on the track at ``z``."""
    return math.degrees(math.atan2(ditch_y(z + 0.8) - ditch_y(z - 0.8), 1.6))


# --- meshes ------------------------------------------------------------------


def _asset(ref, scale=1.0, paint=None, burned=0.0, emissive=True):
    """A GLB-imported mesh turned so its +x nose points +z, scaled,
    optionally repainted (group 3) and charred."""
    from game.render3d_bridge import load_mesh_asset
    verts, faces = load_mesh_asset(ref)
    m = Mesh()
    rot = rot_y(-90)
    for x, y, z in verts:
        m.verts.append((rot[0] * x + rot[2] * z, y, rot[6] * x + rot[8] * z))
    if scale != 1.0:
        m.verts = [(x * scale, y * scale, z * scale) for x, y, z in m.verts]
    base = 1.0
    if paint is not None:
        p = [sum(f[1]) for f in faces if f[2] == 3]
        base = (sum(p) / float(len(p))) if p else 1.0
    char = (26, 22, 20)
    for idx, col, grp in faces:
        col = tuple(col)
        if paint is not None and grp == 3:
            k = sum(col) / base
            col = tuple(max(0, min(255, int(c * k))) for c in paint)
        lit = emissive and grp in (1, 2) and not burned
        if burned:
            col = tuple(int(a + (b - a) * 0.85 * burned) for a, b in zip(col, char))
        m.faces.append((tuple(idx), col, 2, True, lit))
    return m


def tractor():
    """Bodi's tractor, local forward +z."""
    m = _cache.get("tractor")
    if m is None:
        m = _cache["tractor"] = Mesh()
        m.add(W7.tractor(lit=True), rot_y(-90), (0.0, 0.0, 0.0))
    return m


def trailer():
    """The hay trailer Biribel rides, local forward +z (hitch at +z)."""
    m = _cache.get("trailer")
    if m is None:
        m = _cache["trailer"] = Mesh()
        wood = W7._t("plank", P.WOOD_MID)
        side = W7._t("barnboard", W7.BARN)
        dark, steel = (34, 32, 30), (70, 72, 70)
        m.add(box(2.3, 0.14, 3.8, wood, center=(0, 0.92, 0)))
        m.add(box(2.1, 0.16, 3.6, dark, center=(0, 0.78, 0)))             # chassis
        for sx in (-1.12, 1.12):
            m.add(box(0.08, 0.42, 3.8, side, center=(sx, 1.2, 0)))
            for z in (-1.85, -0.6, 0.6, 1.85):
                m.add(box(0.12, 0.6, 0.12, wood, center=(sx, 1.12, z)))
        m.add(box(2.3, 0.42, 0.08, side, center=(0, 1.2, -1.88)))
        m.add(box(2.3, 0.42, 0.08, side, center=(0, 1.2, 1.88)))
        m.add(box(0.16, 0.16, 1.7, steel, center=(0, 0.74, 2.6)))         # drawbar
        m.add(box(0.8, 0.12, 0.12, steel, center=(0, 0.74, 1.95)))
        for sx in (-1.0, 1.0):       # the wheels turn: see TRAILER_WHEELS / wheeled()
            m.add(box(0.5, 0.06, 1.1, dark, center=(sx * 1.02, 0.9, -0.3)))  # mudguard
        m.add(box(0.2, 0.1, 0.06, (200, 30, 26), center=(-0.85, 0.95, -1.93), emissive=True))
        m.add(box(0.2, 0.1, 0.06, (200, 30, 26), center=(0.85, 0.95, -1.93), emissive=True))
        m.add(W7.hay(1), rot_y(90), (0.6, 0.99, 1.15))
        m.add(W7.hay(1), rot_y(90), (-0.62, 0.99, 1.2))
        m.add(W7.hay(1), rot_y(88), (0.0, 1.69, 1.18))
        plate = tex("steel", like=(62, 66, 60), tint=True)
        mx, mz = MOUNT        # the LMG pintle: base plate, gussets, post to the collar
        m.add(box(0.52, 0.04, 0.52, plate, center=(mx, 1.01, mz)))
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            m.add(box(0.03 if dz else 0.15, 0.22, 0.15 if dz else 0.03, steel,
                      center=(mx + 0.12 * dx, 1.14, mz + 0.12 * dz)))
        m.add(box(0.11, POST_TOP - 1.03, 0.11, steel, center=(mx, (POST_TOP + 1.03) / 2.0, mz)))
        m.add(box(0.15, 0.06, 0.15, dark, center=(mx, POST_TOP - 0.03, mz)))
    return m


def _lmg_split():
    """The imported LMG cut into the parts the reload moves: body (origin on
    the trunnion), belt can (origin at its centre) and feed cover (origin on
    its hinge).

    The shoulder stock is cut (``STOCK_CUT_Z`` and behind): the gun rides a
    pintle, and the stock's 24 cm tail behind the grip is what ran through
    Biribel's chest at every yaw - no stance clears it with the grip in reach
    of the hands.  A pintle gun is a stockless gun (M240D-style); the
    receiver's own rear plate (at the cut plane) stays and seals the body
    part, so the gun reads closed from behind."""
    got = _cache.get("lmg_split")
    if got is None:
        from cutscenes import m6world3d as _w
        src = _w._gun_mesh("lmg")[0]
        parts = {k: Mesh() for k in ("body", "can", "cover")}
        origin = {"body": LMG_PIVOT, "can": LMG_CAN, "cover": LMG_HINGE}
        for k, m in parts.items():
            o = origin[k]
            m.verts = [(v[0] - o[0], v[1] - o[1], v[2] - o[2]) for v in src.verts]
            m.faces = []
        for f in src.faces:
            vs = [src.verts[i] for i in f[0]]
            cy = sum(v[1] for v in vs) / 3.0
            cz = sum(v[2] for v in vs) / 3.0
            if cz < STOCK_CUT_Z:
                continue
            if 0.105 < cz < 0.285 and cy < 0.03:
                k = "can"
            elif min(v[1] for v in vs) >= 0.115 and -0.15 < cz < 0.26:
                k = "cover"
            else:
                k = "body"
            parts[k].faces.append(f)
        got = _cache["lmg_split"] = parts
    return got


def lmg_body():
    return _lmg_split()["body"]


def lmg_can():
    return _lmg_split()["can"]


def lmg_cover():
    return _lmg_split()["cover"]


def lmg_yoke(h):
    """The swivel head on the trailer post, local forward +z with the gun: the
    collar, a U-cradle up to the trunnion ``h`` m above it and, on its left, the
    tray the spare belt cans ride in."""
    key = ("lmg_yoke", round(h, 2))
    m = _cache.get(key)
    if m is None:
        m = _cache[key] = Mesh()
        plate = tex("steel", like=(62, 66, 60), tint=True)
        steel, dark = (70, 72, 70), (30, 30, 32)
        m.add(box(0.17, 0.09, 0.17, dark, center=(0.0, 0.045, 0.0)))           # collar
        m.add(box(0.26, 0.05, 0.12, steel, center=(0.0, 0.115, 0.0)))          # cradle base
        arm = max(0.04, h - 0.12)
        for sx in (-1.0, 1.0):
            m.add(box(0.035, arm, 0.08, steel, center=(sx * 0.11, 0.14 + arm / 2.0, 0.0)))
        m.add(box(0.27, 0.035, 0.035, dark, center=(0.0, h, 0.0)))             # trunnion pin
        tx, ty, tz = RACK
        m.add(box(abs(tx) - 0.06, 0.04, 0.05, steel, center=(tx / 2.0 - 0.02, 0.06, 0.0)))  # tray arm
        m.add(box(0.05, 0.2, 0.05, steel, center=(tx + 0.09, -0.04, 0.0)))
        m.add(box(0.18, 0.03, 0.42, plate, center=(tx, ty - 0.015, 0.0)))     # tray
        for sz in (-1.0, 1.0):
            m.add(box(0.18, 0.08, 0.02, plate, center=(tx, ty + 0.04, sz * 0.2)))
        m.add(box(0.02, 0.08, 0.42, plate, center=(tx - 0.09, ty + 0.04, 0.0)))
    return m


def jeep(col=GUARD_PAINT):
    """A Guard car (car_m2 repainted), local forward +z."""
    key = ("car", col)
    m = _cache.get(key)
    if m is None:
        try:
            m = _asset("car_m2", CAR_S, paint=col)
        except (OSError, ValueError):
            m = _car_blocks(col)
        _cache[key] = m
        m.add(box(0.5, 0.1, 0.24, (30, 70, 160), center=(-0.3, 1.58, -0.1), emissive=True))  # beacon
        m.add(box(0.5, 0.1, 0.24, (180, 30, 30), center=(0.3, 1.58, -0.1), emissive=True))
        m.add(box(1.0, 0.06, 0.3, (40, 40, 42), center=(0.0, 1.53, -0.1)))
        _armour(m)
    return m


def _armour(m):
    """Bolt-on steel for the Guard cars (they chase a machine gun now): a
    windscreen shield with a vision slit, door plates and a ram bar."""
    steel = tex("steel", like=(62, 66, 60), tint=True)
    edge = (44, 46, 42)
    # the windscreen runs from (z 0.87, y 1.02) up to (z 0.42, y 1.47)
    for (k0, k1) in ((0.0, 0.52), (0.68, 1.0)):
        za, ya = 0.90 - 0.47 * k0, 1.0 + 0.47 * k0
        zb, yb = 0.90 - 0.47 * k1, 1.0 + 0.47 * k1
        m.face([(-0.78, ya, za), (0.78, ya, za), (0.78, yb, zb), (-0.78, yb, zb)], steel, 2, True)
    for sx in (-1.0, 1.0):
        m.add(box(0.05, 0.42, 1.5, steel, center=(sx * 1.04, 0.84, -0.05)))
        for z in (-0.7, 0.0, 0.62):
            m.add(box(0.06, 0.05, 0.05, edge, center=(sx * 1.07, 1.0, z)))       # bolt heads
        m.add(box(0.1, 0.5, 0.1, edge, center=(sx * 0.62, 0.62, 2.12)))          # ram bar posts
    for y in (0.5, 0.78):
        m.add(box(1.7, 0.09, 0.09, edge, center=(0.0, y, 2.18)))


def _car_blocks(col):
    m = Mesh()
    m.add(box(1.9, 0.7, 4.1, col, center=(0, 0.75, 0)))
    m.add(box(1.7, 0.6, 2.0, (40, 48, 56), center=(0, 1.35, -0.2)))
    for sx, y, sz in CAR_TYRES:
        m.add(box(0.3, 0.8, 0.8, (24, 24, 26), center=(sx, y, sz)))
    return m


def _tyre(rad, wid, rubber=(26, 26, 28), rim=P.HAY_MID, n=14):
    """A round tyre on axis x, centred on its hub: tread lugs and three painted
    rim spokes, so the wheel reads as turning."""
    m = Mesh()
    ang = [math.tau * k / n for k in range(n)]
    ring = [(math.cos(a), math.sin(a)) for a in ang]
    h = wid / 2.0
    for k in range(n):
        (ya, za), (yb, zb) = ring[k], ring[(k + 1) % n]
        col = rubber if k % 2 else tuple(min(255, c + 34) for c in rubber)
        m.face([(-h, ya * rad, za * rad), (h, ya * rad, za * rad),
                (h, yb * rad, zb * rad), (-h, yb * rad, zb * rad)], col, 2, True)
        for sx in (-1.0, 1.0):
            x = sx * h
            for r0, r1, c in ((1.0, 0.62, rubber), (0.62, 0.0, (64, 62, 58))):
                m.face([(x, ya * rad * r0, za * rad * r0), (x, yb * rad * r0, zb * rad * r0),
                        (x, yb * rad * r1, zb * rad * r1), (x, ya * rad * r1, za * rad * r1)], c, 2, True)
    _spokes(m, rad * 0.62, h + 0.006, rim)
    return m


def _spokes(m, rad, x, col):
    """Three painted spokes on both hub faces at +-``x`` (axis x).  A dark
    under-stroke wider than the light core keeps the turning star readable on
    both light and dark hub faces."""
    w = 0.10 * rad
    for sx in (-1.0, 1.0):
        for k in range(3):
            a = math.tau * k / 3.0
            dy, dz = math.cos(a), math.sin(a)
            for ww, xx, c in ((w * 2.0, x, (38, 36, 34)), (w, x + sx * 0.006, col)):
                ny, nz = -dz * ww, dy * ww
                m.face([(sx * xx, ny, nz), (sx * xx, dy * rad + ny, dz * rad + nz),
                        (sx * xx, dy * rad - ny, dz * rad - nz), (sx * xx, -ny, -nz)], c, 2, True)


TRAILER_WHEELS = tuple(((sx * 1.02, 0.42, -0.3), 0.42) for sx in (-1.0, 1.0))


def _components(m):
    par = list(range(len(m.verts)))

    def root(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for f in m.faces:
        idx = f[0]
        for j in idx[1:]:
            a, b = root(idx[0]), root(j)
            if a != b:
                par[a] = b
    out = {}
    for k, f in enumerate(m.faces):
        out.setdefault(root(f[0][0]), []).append(k)
    return list(out.values())


def _split_wheels(m):
    """(body, ((hub, radius, wheel mesh centred on the hub), ...)): the round
    parts touching the ground (tyre, rim and hub caps inside its cylinder) cut
    out of an imported vehicle so they can turn.  Axis x, forward +z."""
    comps = []
    for fl in _components(m):
        vs = sorted({i for k in fl for i in m.faces[k][0]})
        lo = [min(m.verts[i][a] for i in vs) for a in range(3)]
        hi = [max(m.verts[i][a] for i in vs) for a in range(3)]
        comps.append((fl, vs, lo, hi))
    wheels = []
    for fl, vs, lo, hi in sorted(comps, key=lambda c: c[3][1] - c[2][1], reverse=True):
        ey, ez, ex = hi[1] - lo[1], hi[2] - lo[2], hi[0] - lo[0]
        if ey > 0.3 and abs(ey - ez) < 0.15 * ey and ex < 0.7 and lo[1] < 0.15:
            hub = tuple((lo[a] + hi[a]) / 2.0 for a in range(3))
            if not any(abs(hub[0] - w[0][0]) < 0.5 and abs(hub[2] - w[0][2]) < w[1] for w in wheels):
                wheels.append((hub, ey / 2.0, ex / 2.0, []))
    taken = set()
    for ci, (fl, vs, lo, hi) in enumerate(comps):
        for hub, rad, hw, got in wheels:
            # Rim discs, hub caps and lug nuts sit a little outboard of the
            # tread, and the tread lugs (small blocks) stand proud of it: take
            # them too, so the whole wheel turns as one piece.
            reach = rad + (0.11 if len(fl) <= 12 else 0.03)
            if all(abs(m.verts[i][0] - hub[0]) <= hw + 0.16
                   and math.hypot(m.verts[i][1] - hub[1], m.verts[i][2] - hub[2]) <= reach
                   for i in vs):
                got.append(ci)
                taken.add(ci)
                break
    body = Mesh()
    body.verts = list(m.verts)
    body.faces = [m.faces[k] for ci, c in enumerate(comps) if ci not in taken for k in c[0]]
    out = []
    for hub, rad, hw, got in wheels:
        w = Mesh()
        remap = {}
        for ci in got:
            for k in comps[ci][0]:
                f = m.faces[k]
                idx = []
                for i in f[0]:
                    if i not in remap:
                        remap[i] = len(w.verts)
                        v = m.verts[i]
                        w.verts.append((v[0] - hub[0], v[1] - hub[1], v[2] - hub[2]))
                    idx.append(remap[i])
                w.faces.append((tuple(idx),) + tuple(f[1:]))
        # Coarse two-tone sectors on the tread (6) and the rim face (4): few
        # enough that the turn does not alias into a standstill at chase speed.
        recol = []
        for idx, c, lay, dbl, emi in w.faces:
            ys = [w.verts[i][1] for i in idx]
            zs = [w.verts[i][2] for i in idx]
            rs = [math.hypot(y, z) for y, z in zip(ys, zs)]
            a = math.atan2(sum(zs), sum(ys)) % math.tau
            xs = [w.verts[i][0] for i in idx]
            if max(rs) > rad + 0.03:
                pass                                   # a tread lug: keeps its own rubber
            elif min(rs) >= rad * 0.78:
                c = (72, 70, 66) if int(a / math.tau * 6) % 2 else (28, 28, 30)
            elif max(xs) - min(xs) < 0.01 and max(rs) <= rad * 0.7 and max(rs) > rad * 0.2:
                if int(a / math.tau * 4) % 2:
                    c = tuple(int(v * 0.62) for v in c)
            recol.append((idx, c, lay, dbl, emi))
        w.faces = recol
        out.append((hub, rad, w))
    return body, tuple(out)


def _charred(m, k):
    """A copy of ``m`` scorched ``k`` of the way to char, lamps out."""
    char = (26, 22, 20)
    out = Mesh()
    out.verts = m.verts
    out.faces = [(f[0], tuple(int(a + (b - a) * k) for a, b in zip(f[1], char))) + tuple(f[2:4])
                 + (False,) + tuple(f[5:]) for f in m.faces]
    return out


def wheeled(key):
    """(body, ((hub, radius, wheel), ...)) for ``key`` in tractor / trailer /
    jeep / gun_truck; built once."""
    got = _cache.get(("wheeled", key))
    if got is None:
        if key == "trailer":
            tyre = _tyre(0.42, 0.3)
            got = (trailer(), tuple((hub, rad, tyre) for hub, rad in TRAILER_WHEELS))
        elif key.endswith("_burnt"):       # engine blew, paint scorched (tractor, jeep, gun_truck)
            body, wheels = wheeled(key[:-6])
            got = (_charred(body, 0.8), tuple((hub, rad, _charred(w, 0.5)) for hub, rad, w in wheels))
        elif key.endswith("_dark"):        # lamps out, paint as is: a car still deep in the fog
            body, wheels = wheeled(key[:-5])
            got = (_charred(body, 0.0), wheels)
        else:
            got = _split_wheels({"tractor": tractor, "jeep": jeep, "gun_truck": gun_truck}[key]())
        _cache[("wheeled", key)] = got
    return got


def _xf(p, pos, yaw, pitch, roll=0.0):
    """``p`` (local) to world, as ``put`` turns a mesh: roll, pitch, then yaw."""
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    x, y, z = p
    if roll:
        cr, sr = math.cos(math.radians(roll)), math.sin(math.radians(roll))
        x, y = x * cr - y * sr, x * sr + y * cr
    y, z = y * cp + z * sp, z * cp - y * sp
    return (x * cy + z * sy + pos[0], y + pos[1], z * cy - x * sy + pos[2])


WHEEL_SPIN = 0.45    # drawn turn rate vs true roll: keeps the pattern under the strobe limit


def put_wheeled(r, key, pos, yaw=0.0, pitch=0.0, odo=0.0, roll=0.0):
    """``put`` for a vehicle whose wheels roll ``odo`` metres (the body and
    each wheel are their own cached rows)."""
    body, wheels = wheeled(key)
    put(r, (key, "body"), lambda: body, pos, yaw, pitch, roll)
    for i, (hub, rad, w) in enumerate(wheels):
        # shortcut: a rolled body (a wreck, wheels locked) drops the tread turn, which
        # would need spin applied before roll.
        spin = 0.0 if roll else math.degrees(WHEEL_SPIN * odo / rad) % 360.0
        put(r, (key, "wheel", i), lambda w=w: w, _xf(hub, pos, yaw, pitch, roll), yaw, pitch - spin, roll)


def gun_truck():
    """The Guard truck (truck_m7) with a pintle gun on the bed, local forward +z."""
    m = _cache.get("gun_truck")
    if m is None:
        try:
            from missions.m7 import raid_world as RW
            src = RW.truck()
            m = Mesh()
            m.add(src, rot_y(-90))
        except Exception:
            m = Mesh()
            m.add(box(2.4, 2.4, 6.0, GUARD_PAINT, center=(0, 1.4, 0)))
        steel, dark = (64, 68, 66), (26, 26, 28)
        bx, by, bz = TRUCK_BED
        m.add(box(0.16, 1.0, 0.16, steel, center=(bx, by + 0.5, bz + 1.0)))     # post
        m.add(box(0.6, 0.4, 0.06, steel, center=(bx, by + 1.1, bz + 0.85)))     # shield
        m.add(box(0.14, 0.16, 1.5, dark, center=(bx, by + 1.16, bz + 1.6)))     # barrel over the cab
        m.add(box(0.26, 0.26, 0.5, dark, center=(bx, by + 1.12, bz + 0.85)))    # receiver
        m.add(box(0.3, 0.3, 0.4, (80, 86, 60), center=(bx + 0.3, by + 0.95, bz + 0.85)))  # ammo can
        plate = tex("steel", like=(62, 66, 60), tint=True)
        for sx in (-1.0, 1.0):       # bed walls raised with steel: the gunner fights from cover
            m.add(box(0.06, 0.7, 3.0, plate, center=(sx * 1.2, by + 0.75, bz - 0.1)))
        m.add(box(2.4, 0.7, 0.06, plate, center=(0.0, by + 0.75, bz - 1.6)))
        _cache["gun_truck"] = m
    return m


def barrier_arm():
    m = _cache.get("barrier_arm")
    if m is None:
        m = _cache["barrier_arm"] = Mesh()
        for i in range(8):
            col = (210, 40, 36) if i % 2 == 0 else (230, 226, 216)
            m.add(box(1.0, 0.14, 0.14, col, center=(-0.5 - i * 1.0, 0.0, 0.0)))
        m.add(box(0.06, 0.4, 0.06, (40, 40, 42), center=(-7.6, -0.22, 0.0)))   # drop leg
    return m


def train():
    """Four carriages along +x, the last car's rear at local x 0: a passenger
    car with an open rear vestibule, then three box cars."""
    m = _cache.get("train")
    if m is None:
        m = _cache["train"] = Mesh()
        green = tex("metal_rib", like=(58, 78, 66), tint=True)
        boxcar = tex("boxcar", like=(108, 62, 44))
        roof = tex("steel", like=(78, 80, 82))
        dark, steel = (30, 30, 32), (86, 88, 90)
        win = (220, 200, 140)
        for i in range(4):
            x0 = i * 21.0
            cx = x0 + 10.0
            body = green if i == 0 else boxcar
            m.add(box(19.4, 2.9, 3.0, body, center=(cx, 2.55, 0.0)))
            m.add(box(19.6, 0.3, 3.1, roof, center=(cx, 4.12, 0.0)))
            m.add(box(19.0, 0.5, 2.4, dark, center=(cx, 0.95, 0.0)))        # underframe
            for bx in (x0 + 3.0, x0 + 17.0):                                  # bogies
                m.add(box(2.6, 0.5, 2.2, dark, center=(bx, 0.55, 0.0)))
                for wx in (-0.75, 0.75):
                    for sz in (-0.78, 0.78):
                        m.add(box(0.8, 0.8, 0.12, (20, 20, 22), center=(bx + wx, 0.42, sz)))
            m.add(box(0.5, 0.3, 0.3, steel, center=(x0 + 20.6, 1.1, 0.0)))   # coupler
            if i == 0:
                for k in range(6):
                    for sz in (-1.52, 1.52):
                        m.add(box(1.2, 0.8, 0.04, win, center=(x0 + 3.4 + k * 2.6, 3.0, sz), emissive=True))
                m.add(box(19.4, 0.12, 0.05, (200, 186, 120), center=(cx, 2.2, -1.53)))
                m.add(box(19.4, 0.12, 0.05, (200, 186, 120), center=(cx, 2.2, 1.53)))
            else:
                for sz in (-1.52, 1.52):
                    m.add(box(3.0, 2.4, 0.06, tex("rust", like=(90, 54, 40)), center=(cx, 2.4, sz)))
        # the rear vestibule: platform, rails, steps and a red tail lamp
        m.add(box(1.2, 0.12, 2.6, steel, center=(-0.3, 1.2, 0.0)))
        for sz in (-1.2, 1.2):
            m.add(box(1.2, 0.06, 0.06, steel, center=(-0.3, 2.2, sz)))
            m.add(box(0.06, 1.0, 0.06, steel, center=(-0.88, 1.7, sz)))
        m.add(box(0.06, 0.06, 2.4, steel, center=(-0.88, 2.2, 0.0)))
        m.add(box(0.5, 0.08, 0.6, steel, center=(-0.6, 0.8, 1.45)))
        m.add(box(0.14, 0.14, 0.14, (230, 50, 40), center=(-0.05, 3.4, 1.2), emissive=True))
        m.add(box(0.14, 0.14, 0.14, (230, 50, 40), center=(-0.05, 3.4, -1.2), emissive=True))
        m.add(box(0.06, 2.0, 1.0, (38, 40, 44), center=(0.02, 2.3, 0.0)))  # rear door
    return m


# --- the baked set -------------------------------------------------------------


def _span(z0, z1):
    xs = [road_x(z0 + (z1 - z0) * i / 6.0) for i in range(7)]
    return min(xs), max(xs)


def _ground(m, rng):
    """Base grass, then a patchwork of fields both sides of the road with
    hedgerows and poplar rows on their edges."""
    grass = W7._t("grass", W7.GRASS)
    m.add(quad_xz(-320.0, SET_Z0 - 20.0, 320.0, END_Z + 300.0, 0.0, grass, layer=0, seg=20.0,
                  colfn=_mottle(grass, 5, 1)))
    m.add(quad_xz(320.0, CROSSING_Z - 160.0, 580.0, CROSSING_Z + 160.0, 0.0, grass, layer=0, seg=20.0,
                  colfn=_mottle(grass, 5, 1)))
    detail = random.Random(5150)     # rows and mottling: the main stream stays as it was
    # The road passes distinct land uses; otherwise every field reads as the
    # same stubble/grass strip for the entire three-minute chase.
    fields = (
        (("stubble", W7.STUBBLE), ("furrow", P.TRACK_D), ("grass", W7._v(W7.GRASS, -10)),
         ("stubble", W7._v(W7.STUBBLE, 8)), ("furrow", W7.FURROW)),
        (("grass", W7._v(W7.GRASS, -18)), ("furrow", W7._v(P.TRACK_D, -18)),
         ("stubble", W7._v(W7.STUBBLE, -14)), ("grass", W7._v(W7.GRASS, -24))),
        (("furrow", W7._v(W7.DIRT, -24)), ("stubble", W7._v(W7.STUBBLE, -25)),
         ("grass", W7._v(W7.GRASS, -28)), ("furrow", W7._v(P.TRACK_D, -24))),
        (("grass", W7._v(W7.GRASS, -8)), ("ballast", (126, 120, 108)),
         ("stubble", W7._v(W7.STUBBLE, 4)), ("grass", W7._v(W7.GRASS, -14))),
    )
    hay_spots = []
    z = -100.0
    while z < END_Z + 260.0:
        z1 = z + rng.uniform(55.0, 95.0)
        section = max(i for i, start in enumerate(SECTIONS) if start <= max(0.0, (z + z1) / 2.0))
        kinds = fields[section]
        lo, hi = _span(z, z1)
        for side in (-1, 1):
            x = (hi + 9.0) if side > 0 else (lo - 9.0)
            first = True
            while abs(x) < 250.0:
                w = rng.uniform(28.0, 70.0)
                x1 = x + side * w
                if rng.random() < 0.82 and not (CROSSING_Z - 8.0 < z1 and z < CROSSING_Z + 8.0):
                    name, col = kinds[rng.randrange(len(kinds))]
                    a, b = sorted((x, x1))
                    tcol = W7._t(name, col)
                    m.add(quad_xz(a, z + 0.6, b, z1 - 0.6, 0.02, tcol, layer=1, seg=12.0,
                                  colfn=_mottle(tcol, 4, detail.randrange(997))))
                    _field_rows(m, detail, name, tcol, a, b, z + 0.6, z1 - 0.6)
                    if name == "stubble" and abs(x) < 110.0 and rng.random() < 0.7 and section < 2:
                        hay_spots.append((a, b, z, z1))
                if first and rng.random() < 0.3 and z > -40.0 and not _near_crossing(z, z1):
                    m.add(W7._hedgerow(x - side * 1.2, z, x - side * 1.2, z1, seed=int(z) % 97))
                elif abs(x) < 120.0 and rng.random() < 0.28 and not _near_crossing(z, z1):
                    m.add(W7._hedgerow(x, z, x, z1, seed=int(z * 3) % 89))
                first = False
                x = x1
            reach = rng.uniform(60.0, 170.0)
            xa = (hi + 9.0) if side > 0 else (lo - 9.0)
            if _near_crossing(z, z + 1.0):
                continue
            roll = rng.random()
            if roll < 0.45:
                m.add(W7._hedgerow(xa, z, xa + side * reach, z, seed=int(z) % 53))
            elif roll < 0.68:
                k = 0
                xp = xa + side * 3.0
                while abs(xp - xa) < reach:
                    h = rng.uniform(9.0, 16.5)
                    m.add(W7._poplar(rng.randrange(1000), h), rot_y(rng.uniform(0.0, 360.0)), (xp, 0.0, z))
                    xp += side * rng.uniform(5.5, 7.5)
                    k += 1
        z = z1
    for a, b, z0, z1 in hay_spots:
        n = rng.randint(2, 6)
        for _ in range(n):
            m.add(W7.hay(rng.choice((1, 1, 2, 3))), rot_y(rng.choice((0, 90)) + rng.uniform(-8, 8)),
                  (rng.uniform(a + 4, b - 4), 0.02, rng.uniform(z0 + 5, z1 - 5)))


def _mottle(base, amp, seed):
    """Per-cell colour: brightness and a warm/cool shift, so a field reads as
    patchy ground past the distance where its texture mips away."""
    def f(i, j):
        h = (((i + 31 * seed) * 73856093) ^ ((j + 17 * seed) * 19349663)) & 0xFFFF
        k = (h % 7 - 3) * amp
        w = ((h >> 5) % 5 - 2) * amp * 0.7
        rgb = tuple(max(0, min(255, int(c + k + d))) for c, d in zip(base, (w, w * 0.4, -w * 0.4)))
        return base.with_rgb(rgb) if hasattr(base, "with_rgb") else rgb
    return f


def _field_rows(m, rng, name, col, x0, x1, z0, z1):
    """Plough furrows and stubble swathes as long strips: they hold their
    contrast at range and stream past the trailer."""
    if name == "furrow":
        gap, wid, k = rng.uniform(1.5, 2.1), rng.uniform(0.55, 0.8), -22
    elif name == "stubble" and rng.random() < 0.7:
        gap, wid, k = rng.uniform(3.0, 4.2), rng.uniform(0.7, 1.1), 16
    else:
        return
    dark = W7._v(col, k)
    if rng.random() < 0.6:                     # rows parallel to the road
        x = x0 + gap * 0.5
        while x + wid < x1:
            m.face([(x, 0.035, z0), (x, 0.035, z1), (x + wid, 0.035, z1), (x + wid, 0.035, z0)], dark, 1)
            x += gap
    else:
        z = z0 + gap * 0.5
        while z + wid < z1:
            m.face([(x0, 0.035, z), (x0, 0.035, z + wid), (x1, 0.035, z + wid), (x1, 0.035, z)], dark, 1)
            z += gap


_TUFT_COLS = ((58, 78, 40), (66, 86, 42), (76, 90, 44), (92, 92, 48), (52, 70, 38), (104, 98, 56))
_FLOWER_COLS = ((196, 48, 36), (232, 226, 206), (92, 110, 188), (214, 184, 64))


def _verge_y(z, d):
    """Ground height ``d`` metres off the road centre line at ``z``."""
    h = ROAD_W / 2.0
    y0 = ditch_y(z) + 0.04
    if d < h + 0.9:
        return y0 - 0.06
    f = h + 2.6 + y0 * 2.0
    if d < f:
        k = (d - h - 0.9) / max(0.1, f - h - 0.9)
        return (y0 - 0.06) * (1.0 - k) + 0.02 * k
    return 0.02


def _tuft(m, rng, x, y, z, hgt, col):
    """Three to five thin blades fanned from one root, each its own lean."""
    n = rng.randint(3, 5)
    a0 = rng.uniform(0.0, math.pi)
    for i in range(n):
        a = a0 + math.pi * i / n
        ca, sa = math.cos(a), math.sin(a)
        w = hgt * rng.uniform(0.07, 0.12)
        lean = hgt * rng.uniform(0.15, 0.45)
        h = hgt * rng.uniform(0.7, 1.0)
        tip = (x - sa * lean, y + h, z + ca * lean)
        m.face([(x - ca * w, y, z - sa * w), (x + ca * w, y, z + sa * w), tip],
               col if i % 2 else W7._v(col, -8), 2, True)
    return (x, y + hgt * 0.85, z)


_NO_TUFT = tuple((z0, z1) for n, z0, z1 in ZONES if n in ("petrol", "pond", "siding", "kolkhoz"))


def _verge_grass(m):
    """Grass tufts, weeds and the odd wildflower along both verges: thin
    fanned blades, cheap, so the near ground has something on it."""
    rng = random.Random(7243)
    zc = DITCH_Z - 11.0
    z = -60.0
    while z < CROSSING_Z - 30.0:
        z += rng.uniform(0.6, 1.3)
        if _in(z, NO_VERGE) or _in(z, _NO_TUFT) or abs(z - zc) < 3.2:
            continue
        tar = z >= ASPHALT_FROM
        rx = road_x(z)
        for side in (-1, 1):
            if any(abs(z - sz) < r + 4.0 and side == ss for _n, sz, ss, r in ROADSIDE_SITES):
                continue
            # clumps: a few tufts round one spot, the way verge grass grows
            cd = ROAD_W / 2.0 + (1.0 if tar else 0.3) + rng.random() ** 1.4 * 8.0
            for _ in range(rng.choice((1, 2, 2, 3, 4))):
                d = cd + rng.uniform(-0.5, 0.5)
                x, zz = rx + side * d, z + rng.uniform(-0.5, 0.5)
                y = _verge_y(zz, d)
                hgt = rng.uniform(0.14, 0.42) * (1.5 if d > ROAD_W / 2.0 + 4.0 else 1.0)
                col = _TUFT_COLS[rng.randrange(len(_TUFT_COLS))]
                tx, ty, tz = _tuft(m, rng, x, y, zz, hgt, col)
                if rng.random() < 0.06:
                    fc = _FLOWER_COLS[rng.randrange(len(_FLOWER_COLS))]
                    s = 0.05
                    m.face([(tx - s, ty, tz - s), (tx - s, ty, tz + s), (tx + s, ty, tz + s),
                            (tx + s, ty, tz - s)], fc, 2, True)


# Dawn cloud banks: (azimuth, elevation, width, rows) in degrees.  Long thin
# stratus streaks, lit peach underneath toward the sun, fading into the haze.
_CLOUD_BANKS = (
    (8, 3.0, 46, 3), (34, 6.5, 28, 2), (62, 4.0, 54, 4), (96, 8.5, 22, 2),
    (128, 5.0, 40, 3), (166, 2.6, 60, 3), (190, 7.5, 30, 3), (214, 4.4, 36, 2),
    (246, 9.5, 26, 2), (272, 3.4, 50, 3), (300, 6.0, 34, 3), (334, 8.0, 24, 2),
    (182, 11.0, 20, 2), (350, 5.0, 30, 2))
DAWN_CLOUDS = dict(key="dawn", hor=LOOK["sky_bot"], sun=LOOK["light"]["direction"],
                   rim=((214, 150, 132), (255, 216, 174)), body=(184, 155, 164))


def _cloud_img(i, wpx, px_deg, pal):
    key = ("cloud", pal["key"], i, wpx)
    img = _cache.get(key)
    if img is not None:
        return img
    import pygame
    az, el, _cw, rows = _CLOUD_BANKS[i]
    sd = pal["sun"]
    sun = 0.5 + 0.5 * math.cos(math.radians(az - math.degrees(math.atan2(sd[0], sd[2]))))
    haze = _clamp01(1.0 - el / 11.0)
    hor = pal["hor"]

    def mix(c, k):
        return tuple(int(a + (b - a) * k) for a, b in zip(c, hor))
    lo, hi = pal["rim"]
    rim = mix(tuple(int(a + (b - a) * sun) for a, b in zip(lo, hi)), haze * 0.45)
    body = mix(pal["body"], haze * 0.5)
    rng = random.Random(900 + i)
    bar = max(2, int(px_deg * rng.uniform(0.45, 0.7)))
    hpx = rows * (bar + 1) + bar
    surf = pygame.Surface((wpx, hpx), pygame.SRCALPHA)
    for k in range(rows):                      # bottom row first, widest
        frac = 1.0 - 0.22 * k * rng.uniform(0.7, 1.3)
        L = int(wpx * max(0.25, frac))
        x0 = int((wpx - L) * rng.uniform(0.2, 0.8))
        y = hpx - (k + 1) * (bar + 1)
        rad = bar // 2
        pygame.draw.rect(surf, body + (255,), (x0, y, L, bar), border_radius=rad)
        if k == 0:                              # the lit underside
            pygame.draw.rect(surf, rim + (255,), (x0 + bar, y + bar - max(1, bar // 3), L - 2 * bar,
                                                  max(1, bar // 3)))
        if rng.random() < 0.6:                  # a short broken piece off the end
            L2 = int(L * rng.uniform(0.12, 0.3))
            x2 = x0 + L + bar if rng.random() < 0.5 else x0 - L2 - bar
            if 0 <= x2 and x2 + L2 <= wpx:
                pygame.draw.rect(surf, body + (255,), (x2, y, L2, bar), border_radius=rad)
    surf.set_alpha(int(110 + 90 * (1.0 - haze)))
    _cache[key] = surf
    return surf


def stratus(r, buf, t, pal=DAWN_CLOUDS):
    """Thin stratus streaks round the horizon, hard-edged, lit underneath
    toward ``pal["sun"]``.  Shared with the Route 12 trap's dusk sky."""
    w = buf.get_width()
    hy = r.horizon_y()
    yaw = math.degrees(math.atan2(r.fwd[0], r.fwd[2]))
    px_deg = w / max(1.0, r.fov)
    for i, (az, el, cw, _rows) in enumerate(_CLOUD_BANKS):
        wpx = int(cw * px_deg)
        x = w / 2 + ((az + t * 0.00004 - yaw + 180) % 360 - 180) * px_deg
        if x + wpx < 0 or x - wpx > w:
            continue
        img = _cloud_img(i, wpx, px_deg, pal)
        buf.blit(img, (int(x - wpx / 2), int(hy - el * px_deg - img.get_height())))


def _near_crossing(z0, z1):
    return z1 > CROSSING_Z - 30.0 and z0 < CROSSING_Z + 30.0


def _road(m):
    z = SET_Z0
    step = 4.0
    track = W7._t("dirt", W7.TRACK)
    rut = W7._t("dirt", W7._v(W7.TRACK, -26))
    ditch_track = W7._t("dirt", W7._v(W7.TRACK, -15))
    ditch_rut = W7._t("dirt", W7._v(W7.TRACK, -37))
    asphalt = tex("pavement", like=(78, 76, 74), tint=True)
    verge = W7._t("grass", W7._v(W7.GRASS, -6))
    gravel = tex("ballast", like=(112, 104, 92), tint=True)
    line = (214, 210, 196)
    while z < END_Z + 260.0:
        z1 = z + step
        a0, a1 = road_x(z), road_x(z1)
        y0, y1 = ditch_y(z) + 0.04, ditch_y(z1) + 0.04
        tar = z >= ASPHALT_FROM
        wet = SECTIONS[1] <= z < ASPHALT_FROM
        h = ROAD_W / 2.0
        m.face([(a0 - h, y0, z), (a0 + h, y0, z), (a1 + h, y1, z1), (a1 - h, y1, z1)],
               asphalt if tar else ditch_track if wet else track, 1, True)
        for side in (-1, 1):
            e0, e1 = a0 + side * h, a1 + side * h
            s0, s1 = a0 + side * (h + 0.9), a1 + side * (h + 0.9)
            f0, f1 = a0 + side * (h + 2.6 + y0 * 2.0), a1 + side * (h + 2.6 + y1 * 2.0)
            m.face([(e0, y0 - 0.005, z), (s0, y0 - 0.06, z), (s1, y1 - 0.06, z1), (e1, y1 - 0.005, z1)],
                   gravel if tar else verge, 1, True)
            m.face([(s0, y0 - 0.06, z), (f0, 0.02, z), (f1, 0.02, z1), (s1, y1 - 0.06, z1)], verge, 1, True)
        if not tar:
            for c in (-1.05, 1.05):
                w = 0.32
                m.face([(a0 + c - w, y0 + 0.006, z), (a0 + c + w, y0 + 0.006, z),
                        (a1 + c + w, y1 + 0.006, z1), (a1 + c - w, y1 + 0.006, z1)],
                       ditch_rut if wet else rut, 1, True)
        if tar:
            n = int(round(z / step))
            mx0, mx1 = (a0 + a1) / 2.0, (a0 + a1) / 2.0
            if n % 3 == 0:
                m.add(box(0.14, 0.01, step * 0.6, line, center=(mx0, max(y0, y1) + 0.005, z + step / 2.0), layer=1))
            for side in (-1, 1):
                m.add(box(0.12, 0.01, step, (190, 186, 172),
                          center=(mx1 + side * (h - 0.25), max(y0, y1) + 0.005, z + step / 2.0), layer=1))
        z = z1


def _road_wear(m):
    """Puddles and potholes on the farm track, tar patches and cracks on
    Route 12: the road surface stops reading as one flat strip."""
    rng = random.Random(3307)
    track = W7._t("dirt", W7._v(W7.TRACK, -30))
    sky = (152, 134, 130)
    tar = (34, 34, 36)
    crack = (24, 24, 26)
    z = -40.0
    while z < CROSSING_Z - 12.0:
        z += rng.uniform(5.0, 13.0)
        if abs(z - (DITCH_Z - 11.0)) < 9.0:
            continue
        rx = road_x(z)
        y = ditch_y(z) + 0.052
        if z < ASPHALT_FROM:
            wet = SECTIONS[1] <= z
            cx = rx + rng.choice((-1.05, 1.05, 0.0, rng.uniform(-2.6, 2.6)))
            rw, rd = rng.uniform(0.35, 1.0), rng.uniform(0.5, 1.6)
            pts = [(cx + math.cos(a) * rw * rng.uniform(0.8, 1.15), y, z + math.sin(a) * rd * rng.uniform(0.8, 1.15))
                   for a in (-2 * math.pi * i / 7 for i in range(7))]
            if rng.random() < (0.55 if wet else 0.2):
                m.face(pts, sky, 1, False, True)            # puddle: holds the dawn sky
                m.face([(p[0] + (p[0] - cx) * 0.25, y - 0.004, p[2] + (p[2] - z) * 0.2) for p in pts], track, 1)
            else:
                m.face(pts, track, 1)
        else:
            cx = rx + rng.uniform(-2.8, 2.8)
            if rng.random() < 0.5:
                w, d = rng.uniform(0.8, 2.6), rng.uniform(0.8, 3.5)
                m.face([(cx - w, y, z - d), (cx - w, y, z + d), (cx + w, y, z + d), (cx + w, y, z - d)], tar, 1)
            else:
                x0, z0 = cx, z
                for _ in range(rng.randint(3, 6)):
                    x1, z1 = x0 + rng.uniform(-0.6, 0.6), z0 + rng.uniform(0.4, 1.1)
                    m.face([(x0 - 0.03, y, z0), (x1 - 0.03, y, z1), (x1 + 0.03, y, z1), (x0 + 0.03, y, z0)], crack, 1)
                    x0, z0 = x1, z1


def _ditch(m, rng):
    """The drainage ditch across the fields and the culvert embankment the
    track climbs over it: flat water and mud, reeds, concrete headwalls."""
    zc = DITCH_Z - 11.0
    rx = road_x(zc)
    mud = W7._t("dirt", W7._v(W7.DIRT, -30))
    water = (52, 62, 66)
    for side in (-1, 1):
        x0, x1 = sorted((rx + side * (ROAD_W / 2.0 + 3.0), rx + side * 240.0))
        m.add(quad_xz(x0, zc - 2.6, x1, zc + 2.6, 0.03, mud, layer=1, seg=20.0))
        m.add(quad_xz(x0, zc - 1.2, x1, zc + 1.2, 0.045, water, layer=1, seg=40.0))
        for bank in (-1, 1):
            x = x0
            while x < x1 and abs(x - rx) < 130.0:
                if rng.random() < 0.6:
                    h = rng.uniform(0.7, 1.3)
                    m.add(box(0.08, h, 0.08, (118, 112, 64), center=(x, h / 2.0, zc + bank * 1.6)))
                    m.add(box(0.06, h * 0.8, 0.06, (96, 100, 54), center=(x + 0.3, h * 0.4, zc + bank * 1.75)))
                x += rng.uniform(0.6, 2.2)
        hx = rx + side * (ROAD_W / 2.0 + 2.2)
        m.add(box(0.5, 1.2, 5.6, tex("concrete", like=(150, 146, 136)), center=(hx, 0.45, zc)))
        m.add(box(0.06, 0.5, 1.6, (20, 22, 24), center=(hx + side * 0.27, 0.35, zc)))  # pipe mouth
    for side in (-1, 1):                     # warning posts on the embankment
        for dz in (-5.0, 5.0):
            px = road_x(zc + dz) + side * (ROAD_W / 2.0 + 0.5)
            m.add(box(0.14, 1.0, 0.14, (230, 228, 220), center=(px, ditch_y(zc + dz) + 0.5, zc + dz)))
            m.add(box(0.15, 0.16, 0.15, (200, 40, 34), center=(px, ditch_y(zc + dz) + 0.86, zc + dz)))


def _in(z, spans):
    return any(a <= z <= b for a, b in spans)


def _clamp01(v):
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


def _poles(m):
    """Power line with sagging wires: west verge to the ditch, east verge after,
    and none through the woods or the cutting."""
    z = SET_Z0         # on the same 46 m grid as the old -60 start
    tops = []
    runs = []
    while z < CROSSING_Z - 20.0:
        side = -1.0 if z < DITCH_Z else 1.0
        if _in(z, NO_POLES) or (tops and (tops[-1][0] - road_x(tops[-1][2])) * side < 0.0):
            runs.append(tops)            # a gap, or the line crosses the road: new run
            tops = []
        if not _in(z, NO_POLES):
            x = road_x(z) + side * (ROAD_W / 2.0 + 5.5)
            m.add(W7._pole(), rot_y(road_yaw(z)), (x, 0.0, z))
            tops.append((x, W7.POLE_H - 0.06, z))
        z += 46.0
    runs.append(tops)
    wire = (34, 34, 36)
    for a, b in ((a, b) for run in runs for a, b in zip(run[:-1], run[1:])):
        for dx in (-0.7, 0.7):
            pa, pb = (a[0] + dx, a[1], a[2]), (b[0] + dx, b[1], b[2])
            mid = ((pa[0] + pb[0]) / 2.0, pa[1] - 0.9, (pa[2] + pb[2]) / 2.0)
            for p, q in ((pa, mid), (mid, pb)):
                m.face([p, q, (q[0], q[1] - 0.035, q[2]), (p[0], p[1] - 0.035, p[2])], wire, 2, True)


def _verge_trees(m, rng):
    z = -60.0
    while z < CROSSING_Z - 40.0:
        rx = road_x(z)
        for side in (-1, 1):
            if rng.random() < 0.32:
                pick = rng.random()
                pos = (rx + side * rng.uniform(9.0, 24.0), 0.0, z + rng.uniform(-6, 6))
                if _in(pos[2], NO_VERGE):    # a set piece owns this stretch (draws kept)
                    continue
                if pick < 0.4:
                    m.add(W7.tree(rng.randrange(7)), rot_y(rng.uniform(0, 360)), pos)
                elif pick < 0.75:
                    m.add(W7._shelter_tree(rng.randrange(9)), rot_y(rng.uniform(0, 360)), pos)
                else:
                    m.add(W7._walnut(rng.randrange(9)), rot_y(rng.uniform(0, 360)), pos)
        z += 14.0


def _backstretch(m):
    """Verge trees on the road behind the farm, where the chasers enter.  Own
    RNG, so the main stream (fields, wrecks) stays as it was."""
    rng = random.Random(4417)
    z = SET_Z0
    while z < -60.0:
        rx = road_x(z)
        for side in (-1, 1):
            if rng.random() < 0.32:
                pos = (rx + side * rng.uniform(9.0, 24.0), 0.0, z + rng.uniform(-6, 6))
                m.add(W7.tree(rng.randrange(7)), rot_y(rng.uniform(0, 360)), pos)
        z += 14.0


def _farm(lit, seed, burn=False):
    """One farmstead, front (local -z) toward the road."""
    rng = random.Random(seed)
    m = Mesh()
    m.add(quad_xz(-16.0, -13.0, 30.0, 19.0, 0.03, W7._t("dirt", W7.DIRT), layer=1, seg=8.0))
    m.add(W7.house_ruin() if burn else W7.house(lit=lit))
    m.add(W7.barn_ruin() if burn else W7.barn(), rot_y(rng.choice((0, 90))), (17.0, 0.0, 8.0))
    m.add(W7.shed(), rot_y(180), (-10.5, 0.0, 6.5))
    m.add(W7._farm_silo(), t=(26.0, 0.0, -4.0))
    if rng.random() < 0.6:
        m.add(W7._farm_windpump(), t=(-9.0, 0.0, -8.5))
    m.add(W7.hay(3), rot_y(90), (9.5, 0.0, -6.0))
    m.add(W7.hay(2), rot_y(rng.uniform(-10, 10)), (22.0, 0.0, 15.5))
    m.add(W7._fence(-16.0, -13.0, 30.0, -13.0, gap=(-2.0, 3.0)))
    m.add(W7._fence(-16.0, -13.0, -16.0, 19.0))
    m.add(W7._fence(30.0, -13.0, 30.0, 19.0))
    m.add(W7._fence(-16.0, 19.0, 30.0, 19.0))
    for i, (x, z) in enumerate(((-13.0, 14.0), (3.5, 16.5), (-14.0, -9.0))):
        m.add(W7._walnut(seed + i), rot_y(i * 97), (x, 0.0, z))
    return m


def _farmsteads(m, rng):
    z = 110.0
    side = 1
    while z < CROSSING_Z - 110.0:
        d = rng.uniform(42.0, 70.0)
        rx = road_x(z)
        fx = rx + side * d
        lit = rng.random() < 0.5
        # Farmyards belong to the dirt-road stretch, not every section of the
        # highway and border approach.  Still consume the seeded layout draw
        # for each site even when its buildings are left out.
        if z < SECTIONS[2] - 80.0:
            # The first farmstead is Bodi's, burned by the Guard in M7.
            m.add(_farm(lit, int(z), burn=z == 110.0), rot_y(90 if side > 0 else -90), (fx, 0.0, z))
            a, b = sorted((rx + side * (ROAD_W / 2.0 + 2.4), fx - side * 13.0))
            m.add(quad_xz(a, z - 2.1, b, z + 1.1, 0.035,
                          W7._t("track", W7.TRACK), layer=1, seg=8.0))
        z += rng.uniform(190.0, 260.0)
        side = -side


def _house_small(col, lit):
    m = Mesh()
    wall = W7._t("plaster", col)
    m.add(box(6.0, 2.8, 5.0, wall, center=(0, 1.4, 0)))
    m.add(W7._gable_z(5.0, 6.0, 2.8, 1.7, W7._t("tile", W7.TILE), wall), rot_y(90))
    for x in (-1.6, 1.6):
        m.add(box(0.9, 0.8, 0.06, W7.WIN_LIT if lit else W7.WIN, center=(x, 1.6, -2.53), emissive=lit))
    return m


def _church():
    m = Mesh()
    wall = W7._t("plaster", (196, 188, 170))
    m.add(box(7.0, 6.0, 14.0, wall, center=(0, 3.0, 0)))
    m.add(W7._gable_z(7.0, 14.0, 6.0, 3.0, W7._t("tin", W7.ROOF_METAL), wall))
    m.add(box(3.6, 11.0, 3.6, wall, center=(0, 5.5, -8.2)))
    m.add(W7._bipyr(0, 11.0, -8.2, 2.6, 5.5, 0.01, W7._t("tin", P.GALV), n=4))
    m.add(box(0.16, 1.6, 0.16, (200, 176, 90), center=(0, 17.2, -8.2)))
    m.add(box(0.9, 0.16, 0.16, (200, 176, 90), center=(0, 17.4, -8.2)))
    return m


def _villages(m, rng):
    cols = ((214, 200, 170), (196, 176, 140), (170, 182, 176), (206, 186, 160), (188, 160, 130))
    for z, side, d in ((260.0, -1, 135.0), (720.0, 1, 150.0), (1180.0, -1, 125.0), (1650.0, 1, 140.0),
                       (2140.0, -1, 120.0)):
        cx = road_x(min(z, CROSSING_Z)) + side * d
        # A farm village and a border town, not five copies of the same church.
        keep = z in (260.0, 1650.0)
        if keep:
            m.add(_church(), rot_y(90 if side > 0 else -90), (cx + side * 10.0, 0.0, z))
        for i in range(12):
            a = rng.uniform(0, math.tau)
            r = rng.uniform(14.0, 42.0)
            lit = rng.random() < 0.4
            yaw = rng.choice((0, 90, 180, 270))
            if keep:
                m.add(_house_small(cols[i % len(cols)], lit), rot_y(yaw),
                      (cx + math.cos(a) * r, 0.0, z + math.sin(a) * r * 1.4))
        for i in range(8):
            a = rng.uniform(0, math.tau)
            r = rng.uniform(10.0, 50.0)
            h = rng.uniform(10.0, 15.0)
            if keep:
                m.add(W7._poplar(i, h), t=(cx + math.cos(a) * r, 0.0, z + math.sin(a) * r))


def _roadside_site(name):
    """One recognisable silhouette at trailer-camera distance, not a tile loop."""
    m = Mesh()
    stone = W7._t("stone", (128, 126, 112))
    timber = W7._t("plank", P.WOOD_MID)
    steel = W7._t("steel", (94, 100, 98))
    if name == "farm_gate":
        for x in (-5.0, 5.0):
            m.add(box(0.8, 2.2, 0.8, stone, center=(x, 1.1, -2.0)))
            m.add(box(1.0, 0.16, 1.0, timber, center=(x, 2.28, -2.0)))
        m.add(box(9.0, 0.28, 0.25, timber, center=(0, 1.65, -2.0)))
        m.add(W7._farm_windpump(), t=(3.0, 0, 6.0))
    elif name == "orchard":
        for row in range(3):
            for col in range(3):
                m.add(W7.tree(210 + row * 3 + col), t=(-6.0 + col * 5.5, 0, -8.0 + row * 6.5))
        m.add(W7._fence(-9.0, -11.0, 9.0, -11.0, gap=(-2.5, 2.5)))
        m.add(W7._fence(9.0, -11.0, 9.0, 9.0))
    elif name == "hay_yard":
        m.add(W7.barn(), rot_y(90), (1.0, 0, 7.0))
        for i, (x, z) in enumerate(((-6, -7), (-3, -7), (0, -8), (4, -6), (-5, -3))):
            m.add(W7.hay(1 + i % 3), rot_y(90 if i % 2 else 0), (x, 0, z))
        m.add(W7._fence(-9.0, -11.0, 8.0, -11.0, gap=(-3.0, 3.0)))
    elif name == "pump_house":
        brick = W7._t("brick", (128, 103, 86))
        m.add(box(5.0, 3.2, 4.2, brick, center=(1.0, 1.6, 1.0)))
        m.add(box(5.8, 0.25, 4.8, steel, center=(1.0, 3.3, 1.0)))
        for x in (-1.0, 2.8):
            m.add(box(0.2, 5.0, 0.2, steel, center=(x, 2.5, -5.0)))
        m.add(box(5.0, 1.6, 2.8, steel, center=(0.9, 5.3, -5.0)))
        m.add(box(0.8, 0.8, 0.2, (36, 52, 58), center=(1.0, 1.3, -1.12)))
    elif name == "guard_post":
        concrete = tex("concrete", like=(134, 133, 127))
        m.add(box(6.0, 2.8, 3.8, concrete, center=(0, 1.4, 2.0)))
        m.add(box(7.0, 0.3, 4.8, steel, center=(0, 3.0, 2.0)))
        m.add(box(2.4, 0.8, 0.08, (38, 62, 52), center=(0, 2.1, -0.02)))
        for x in (-4.5, 4.5):
            m.add(box(0.7, 0.9, 2.8, concrete, center=(x, 0.45, -5.0)))
        m.add(box(0.18, 7.0, 0.18, steel, center=(3.0, 3.5, 4.0)))
        m.add(box(1.1, 0.3, 0.5, (184, 42, 38), center=(3.0, 6.7, 4.0)))
    elif name == "memorial":
        m.add(quad_xz(-6, -9, 7, 8, 0.035, stone, layer=1, seg=8.0))
        m.add(box(8.0, 0.8, 1.2, stone, center=(0, 0.4, 5.0)))
        for i, x in enumerate((-4.0, -1.4, 1.4, 4.0)):
            h = 2.2 + 0.35 * (i % 2)
            m.add(box(0.85, h, 0.6, stone, center=(x, h / 2, 0)))
            m.add(box(0.5, 0.55, 0.03, (44, 47, 46), center=(x, 1.5, -0.32)))
        m.add(box(0.6, 0.12, 0.6, (144, 56, 42), center=(-2.0, 0.13, -2.0)))
    elif name == "freight_depot":
        wall = W7._t("brick", (135, 122, 105))
        m.add(box(11.0, 5.2, 9.0, wall, center=(1.0, 2.6, 3.0)))
        m.add(box(12.0, 0.4, 10.0, steel, center=(1.0, 5.4, 3.0)))
        for x in (-2.5, 1.0, 4.5):
            m.add(box(2.5, 3.2, 0.12, (50, 62, 62), center=(x, 1.6, -1.55)))
        for x, z in ((-6, -5), (-3, -6), (7, -6), (8, -3)):
            m.add(box(1.8, 1.5, 1.8, timber, center=(x, 0.75, z)))
        m.add(W7._farm_silo(), t=(9.0, 0, 8.0))
    elif name == "watchtower":
        concrete = tex("concrete", like=(151, 145, 130))
        for x in (-1.7, 1.7):
            for z in (-1.7, 1.7):
                m.add(box(0.4, 6.5, 0.4, steel, center=(x, 3.25, z)))
        m.add(box(4.5, 0.35, 4.5, concrete, center=(0, 6.5, 0)))
        m.add(box(3.4, 2.2, 3.4, concrete, center=(0, 7.8, 0)))
        m.add(box(4.4, 0.24, 4.4, steel, center=(0, 9.05, 0)))
        for x in (-1.0, 1.0):
            m.add(box(0.9, 0.7, 0.06, (45, 63, 73), center=(x, 7.8, -1.74)))
        m.add(box(0.18, 2.8, 0.18, steel, center=(1.4, 10.5, 0)))
        m.add(box(1.4, 0.6, 0.08, (190, 43, 40), center=(0.7, 11.4, 0)))
    else:
        raise ValueError("Unknown chase landmark: " + name)
    return m


def _roadside_landmarks(m):
    for name, z, side, distance in ROADSIDE_SITES:
        m.add(_roadside_site(name), rot_y(180 if side < 0 else 0),
              (road_x(z) + side * distance, 0.0, z))


def _zone_hamlet(m, rng, z0, z1):
    """A lane-side hamlet: small houses both sides behind front-garden fences."""
    cols = ((214, 200, 170), (176, 186, 168), (206, 172, 150), (190, 190, 200))
    z, side = z0, 1
    while z < z1:
        rx = road_x(z)
        d = rng.uniform(15.0, 19.0)
        m.add(_house_small(cols[int(z) % len(cols)], rng.random() < 0.5),
              rot_y(90 if side > 0 else -90), (rx + side * d, 0.0, z))
        fx = rx + side * (d - 5.5)
        m.add(W7._fence(fx, z - 6.0, fx, z + 6.0, h=0.9, every=1.6, gap=(z - 1.0, z + 1.0)))
        if rng.random() < 0.6:
            m.add(W7.tree(int(z) % 7), t=(rx + side * (d + 7.0), 0.0, z + 4.0))
        z += rng.uniform(16.0, 24.0)
        side = -side if rng.random() < 0.7 else side


def _zone_woods(m, rng, z0, z1):
    """A woodland corridor close on both verges: the sky narrows to the road."""
    z = z0
    while z < z1:
        rx = road_x(z)
        for side in (-1, 1):
            for _ in range(2):
                pos = (rx + side * rng.uniform(8.0, 34.0), 0.0, z + rng.uniform(-2.5, 2.5))
                k = rng.random()
                if k < 0.45:
                    m.add(W7.tree(rng.randrange(7)), rot_y(rng.uniform(0, 360)), pos)
                elif k < 0.8:
                    m.add(W7._shelter_tree(rng.randrange(9)), rot_y(rng.uniform(0, 360)), pos)
                else:
                    m.add(W7._poplar(rng.randrange(9), rng.uniform(11.0, 16.0)), t=pos)
        z += 5.0
    for side in (-1, 1):
        a, b = sorted((road_x(z0) + side * 6.5, road_x(z0) + side * 40.0))
        m.add(quad_xz(a, z0, b, z1, 0.02, W7._t("dirt", W7._v(W7.DIRT, -30)), layer=1, seg=10.0))


def _zone_pond(m, rng, z0, z1):
    """A wet meadow with a pond, reeds and willows on the west side."""
    cx, cz = road_x((z0 + z1) / 2.0) - 24.0, (z0 + z1) / 2.0
    m.add(quad_xz(cx - 15.0, cz - 30.0, cx + 15.0, cz + 30.0, 0.03,
                  W7._t("grass", W7._v(W7.GRASS, -30)), layer=1, seg=10.0))
    m.add(quad_xz(cx - 12.0, cz - 26.0, cx + 12.0, cz + 26.0, 0.04, P.WATER, layer=1, seg=12.0))
    reed = (96, 104, 58)
    for _ in range(70):
        a = rng.uniform(0.0, math.tau)
        x, z = cx + math.cos(a) * rng.uniform(11.0, 14.0), cz + math.sin(a) * rng.uniform(24.0, 29.0)
        h = rng.uniform(0.8, 1.6)
        m.add(box(0.08, h, 0.08, reed, center=(x, h / 2.0, z)))
    for i, (dx, dz) in enumerate(((-15.0, -18.0), (14.0, 6.0), (-13.0, 22.0))):
        m.add(W7._shelter_tree(30 + i), t=(cx + dx, 0.0, cz + dz))
    m.add(box(1.2, 0.12, 6.0, W7._t("plank", P.WOOD_MID), center=(cx + 11.0, 0.35, cz - 4.0)))


def _shed_long(length, wall, roof):
    m = Mesh()
    m.add(box(9.0, 3.2, length, wall, center=(0, 1.6, 0)))
    m.add(W7._gable_z(9.0, length, 3.2, 2.2, roof, wall))
    for z in range(int(-length / 2) + 3, int(length / 2) - 2, 5):
        m.add(box(0.06, 0.7, 1.6, W7.WIN, center=(-4.53, 2.3, z)))
    return m


def _zone_kolkhoz(m, rng, z0, z1):
    """The collective farm east of the road: two long cow sheds, a water tower, silos."""
    zc = (z0 + z1) / 2.0
    rx = road_x(zc)
    wall = W7._t("plaster", (184, 178, 160))
    roof = W7._t("tin", W7.ROOF_METAL)
    m.add(quad_xz(rx + 14.0, z0, rx + 60.0, z1, 0.03, W7._t("dirt", W7.DIRT), layer=1, seg=10.0))
    m.add(_shed_long(56.0, wall, roof), t=(rx + 26.0, 0.0, z0 + 40.0))
    m.add(_shed_long(48.0, wall, roof), t=(rx + 44.0, 0.0, z0 + 92.0))
    m.add(W7._landscape_water_tower(), t=(rx + 22.0, 0.0, z0 + 92.0))
    for k in range(3):
        m.add(W7._farm_silo(), t=(rx + 50.0 + k * 4.5, 0.0, z0 + 22.0))
    m.add(W7._fence(rx + 13.0, z0, rx + 13.0, z1, gap=(zc - 3.0, zc + 3.0)))
    m.add(box(0.2, 3.4, 0.2, (90, 94, 96), center=(rx + 12.0, 1.7, zc - 4.0)))
    m.add(box(0.1, 1.0, 3.2, (150, 46, 40), center=(rx + 12.0, 3.0, zc - 4.0)))


def _zone_petrol(m, rng, z0, z1):
    """A roadside petrol station on the west side, the canopy lit at dawn."""
    zc = (z0 + z1) / 2.0
    rx = road_x(zc) - 15.0
    conc = tex("concrete", like=(150, 148, 140))
    steel = W7._t("steel", (94, 100, 98))
    red = (170, 42, 36)
    m.add(quad_xz(rx - 10.0, zc - 22.0, rx + 10.5, zc + 22.0, 0.04, conc, layer=1, seg=8.0))
    for x in (rx - 4.0, rx + 4.0):
        for z in (zc - 5.0, zc + 5.0):
            m.add(box(0.35, 4.4, 0.35, steel, center=(x, 2.2, z)))
    m.add(box(11.0, 0.7, 14.0, (214, 210, 196), center=(rx, 4.75, zc)))
    m.add(box(11.2, 0.25, 14.2, red, center=(rx, 4.5, zc)))
    m.add(box(9.6, 0.06, 12.6, (255, 236, 196), center=(rx, 4.38, zc), emissive=True))
    for z in (zc - 2.5, zc + 2.5):
        m.add(box(0.8, 1.6, 1.2, (200, 196, 184), center=(rx, 0.8, z)))
        m.add(box(0.82, 0.4, 1.0, red, center=(rx, 1.3, z)))
    m.add(box(7.0, 3.0, 5.0, W7._t("plaster", (206, 200, 186)), center=(rx - 4.0, 1.5, zc + 15.0)))
    m.add(box(0.06, 1.2, 3.6, W7.WIN_LIT, center=(rx - 0.47, 1.5, zc + 15.0), emissive=True))
    m.add(box(0.3, 7.0, 0.3, steel, center=(rx + 9.5, 3.5, zc - 16.0)))
    m.add(box(0.2, 2.0, 2.6, red, center=(rx + 9.5, 7.6, zc - 16.0)))


def _zone_cutting(m, rng, z0, z1):
    """Route 12 drops into a cutting: grass banks both sides and a concrete
    overpass, the only stretch where the horizon disappears."""
    turf = W7._v(W7.GRASS, -12)
    top = W7._v(W7.GRASS, -4)
    ramp, step = 30.0, 10.0
    z = z0
    while z < z1:
        za, zb = z, min(z1, z + step)
        ha = CUT_H * _clamp01(min(za - z0, z1 - za) / ramp)
        hb = CUT_H * _clamp01(min(zb - z0, z1 - zb) / ramp)
        for side in (-1.0, 1.0):
            ia = road_x(za) + side * (ROAD_W / 2.0 + 2.5)
            ib = road_x(zb) + side * (ROAD_W / 2.0 + 2.5)
            oa, ob = ia + side * (2.0 * ha + 0.5), ib + side * (2.0 * hb + 0.5)
            fa, fb = oa + side * 30.0, ob + side * 30.0
            m.face([(ia, 0.0, za), (ib, 0.0, zb), (ob, hb, zb), (oa, ha, za)], turf, 2, True)
            m.face([(oa, ha, za), (ob, hb, zb), (fb, hb, zb), (fa, ha, za)], top, 2, True)
        z = zb
    conc = tex("concrete", like=(156, 152, 142))
    rx = road_x(OVERPASS_Z)
    span = ROAD_W / 2.0 + 2.5 + 2.0 * CUT_H + 4.0
    m.add(box(span * 2.0, 0.9, 7.0, conc, center=(rx, CUT_H + 0.45, OVERPASS_Z)))
    for side in (-1.0, 1.0):
        m.add(box(1.0, CUT_H, 6.0, conc, center=(rx + side * (ROAD_W / 2.0 + 1.6), CUT_H / 2.0, OVERPASS_Z)))
        m.add(box(span * 2.0, 1.0, 0.25, conc, center=(rx, CUT_H + 1.4, OVERPASS_Z + side * 3.4)))
    m.add(box(4.5, 0.9, 0.08, (40, 92, 60), center=(rx, CUT_H - 0.2, OVERPASS_Z - 3.55)))


def _panel_block(floors, length):
    m = Mesh()
    wall = tex("concrete", like=(170, 166, 156))
    h = floors * 2.8
    m.add(box(11.0, h, length, wall, center=(0, h / 2.0, 0)))
    m.add(box(11.4, 0.4, length + 0.4, (110, 108, 104), center=(0, h + 0.2, 0)))
    for f in range(floors):
        for k in range(int(length // 3.2)):
            z = -length / 2.0 + 1.6 + k * 3.2
            lit = (f * 7 + k * 3) % 11 == 0
            m.add(box(0.06, 1.2, 1.5, W7.WIN_LIT if lit else W7.WIN,
                      center=(-5.53, 1.4 + f * 2.8, z), emissive=lit))
    return m


def _zone_bus_stop(m, rng, z0, z1):
    """Edge of a town: a concrete bus shelter and panel blocks east of the road."""
    zc = (z0 + z1) / 2.0
    rx = road_x(zc)
    conc = tex("concrete", like=(150, 146, 138))
    sx = rx + ROAD_W / 2.0 + 2.6
    sz = zc - 30.0
    m.add(box(0.25, 2.4, 4.6, conc, center=(sx + 1.4, 1.2, sz)))
    m.add(box(1.8, 0.2, 5.0, conc, center=(sx + 0.7, 2.5, sz)))
    m.add(box(0.6, 0.45, 3.6, W7._t("plank", P.WOOD_MID), center=(sx + 0.9, 0.45, sz)))
    m.add(box(0.1, 2.6, 0.1, (200, 196, 184), center=(sx - 0.4, 1.3, sz - 5.0)))
    m.add(box(0.06, 0.6, 0.6, (230, 200, 60), center=(sx - 0.4, 2.7, sz - 5.0)))
    for i, (dz, floors, length) in enumerate(((-34.0, 5, 30.0), (6.0, 9, 22.0), (40.0, 5, 34.0))):
        m.add(_panel_block(floors, length), t=(rx + 34.0 + 6.0 * (i % 2), 0.0, zc + dz))


def _zone_siding(m, rng, z0, z1):
    """A rail siding west of the road: a spur track and parked boxcars."""
    rx = road_x(z0) - 20.0
    m.add(quad_xz(rx - 4.0, z0, rx + 4.0, z1, 0.05, W7._t("track", (120, 114, 102)), layer=1, seg=6.0))
    for dx in (-0.72, 0.72):
        m.add(box(0.1, 0.16, z1 - z0, (72, 70, 66), center=(rx + dx, 0.18, (z0 + z1) / 2.0)))
    z = z0 + 0.5
    while z < z1:
        m.add(box(2.4, 0.1, 0.25, (70, 56, 44), center=(rx, 0.08, z)))
        z += 0.9
    cols = ((110, 62, 44), (96, 74, 52), (88, 94, 84))
    for k in range(4):
        zc = z0 + 14.0 + k * 14.5
        car = cols[k % len(cols)]
        m.add(box(3.0, 3.0, 13.0, W7._t("plank", car), center=(rx, 2.3, zc)))
        m.add(box(3.2, 0.25, 13.2, (60, 60, 58), center=(rx, 3.9, zc)))
        m.add(box(0.06, 2.4, 3.0, W7._v(car, -26), center=(rx + 1.53, 2.2, zc)))
        for dz in (-4.5, 4.5):
            m.add(box(2.0, 0.6, 1.6, (36, 36, 38), center=(rx, 0.55, zc + dz)))


def _zone_border_fence(m, rng, z0, z1):
    """The border fence on the east verge: posts, wire, floodlights."""
    steel = (96, 100, 100)
    wire = (120, 126, 124)
    z = z0
    prev = None
    while z <= z1:
        x = road_x(z) + 13.0
        m.add(box(0.14, 3.4, 0.14, steel, center=(x, 1.7, z)))
        m.add(box(0.5, 0.08, 0.08, steel, center=(x - 0.2, 3.45, z)))
        if prev is not None:
            px, pz = prev
            for y in (0.4, 1.3, 2.2, 3.1):
                m.face([(px, y, pz), (x, y, z), (x, y + 0.04, z), (px, y + 0.04, pz)], wire, 2, True)
        if int(z - z0) % 40 == 0:
            m.add(box(0.22, 8.0, 0.22, steel, center=(x + 1.5, 4.0, z)))
            m.add(box(1.2, 0.5, 0.6, (230, 230, 214), center=(x + 1.0, 8.0, z), emissive=True))
        prev = (x, z)
        z += 4.0
    m.add(quad_xz(road_x(z0) + 11.0, z0, road_x(z0) + 15.0, z1, 0.03,
                  W7._t("track", (120, 114, 102)), layer=1, seg=6.0))


_ZONE_BUILDERS = {
    "hamlet": _zone_hamlet, "woods": _zone_woods, "pond": _zone_pond, "kolkhoz": _zone_kolkhoz,
    "petrol": _zone_petrol, "cutting": _zone_cutting, "bus_stop": _zone_bus_stop,
    "siding": _zone_siding, "border_fence": _zone_border_fence,
}


def _zones(m):
    rng = random.Random(2024)            # own stream: the wreck and spawn layout stays put
    for name, z0, z1 in ZONES:
        _ZONE_BUILDERS[name](m, rng, z0, z1)


def _ridges(m, rng):
    """Far wooded ridges both sides, and low hills nearer in."""
    for side in (-1, 1):
        z = -200.0
        while z < END_Z + 420.0:
            r = rng.uniform(70.0, 110.0)
            cx = side * rng.uniform(250.0, 300.0)
            h = rng.uniform(26.0, 46.0)
            col = W7._v(W7.HILL_F, rng.randint(-6, 6))
            if abs(z - CROSSING_Z) > r + 24.0:
                m.add(W7._bipyr(cx, 0.0, z, r, h, 1.0, col, n=7))
            z += rng.uniform(70.0, 110.0)
        z = -100.0
        while z < END_Z + 300.0:
            if rng.random() < 0.55:
                r = rng.uniform(35.0, 60.0)
                cx = side * rng.uniform(185.0, 225.0)
                h = rng.uniform(8.0, 16.0)
                if abs(z - CROSSING_Z) > r + 24.0:
                    m.add(W7._bipyr(cx, 0.0, z, r, h, 1.0,
                                    W7._t("grass", W7._v(W7.HILL_N, 30)), n=8))
                for k in range(rng.randint(3, 7)):
                    tx = side * rng.uniform(170.0, 200.0)
                    tz = z + rng.uniform(-30, 30)
                    if abs(tz - CROSSING_Z) > 22.0:
                        m.add(W7._shelter_tree(k), t=(tx, 0.0, tz))
            z += rng.uniform(80.0, 140.0)
    # the hills that close the view north, over the border
    for k in range(9):
        m.add(W7._bipyr(-240.0 + k * 60.0, 0.0, END_Z + 360.0 + rng.uniform(-20, 20), rng.uniform(70, 100),
                        rng.uniform(30.0, 55.0), 1.0, W7._v(W7.HILL_F, -6), n=7))


def _wrecks(m, rng):
    """Burned squad cars along Route 12; returns their (x, z) for the scene."""
    out = []
    try:
        shell = _asset("car_m2", CAR_S, paint=(70, 76, 86), burned=1.0)
    except (OSError, ValueError):
        shell = _car_blocks((40, 40, 44))
    scorch = tex("scorch", like=(40, 34, 30))
    z = SECTIONS[2] + 40.0
    while z < SECTIONS[3] - 30.0:
        side = rng.choice((-1, 1))
        x = road_x(z) + side * rng.uniform(2.6, 4.8)
        yaw = rng.uniform(-40, 40) + (90 if rng.random() < 0.3 else 0)
        m.add(quad_xz(x - 3.2, z - 3.6, x + 3.2, z + 3.6, 0.055, scorch, layer=1, seg=8.0))
        m.add(shell, rot_y(yaw), (x, 0.0, z))
        for _ in range(rng.randint(2, 4)):
            m.add(box(rng.uniform(0.2, 0.6), 0.06, rng.uniform(0.2, 0.7), (30, 28, 26),
                      center=(x + rng.uniform(-3, 3), 0.07, z + rng.uniform(-3, 3))))
        out.append((x, z))
        z += rng.uniform(34.0, 52.0)
    # Route 12 furniture: jersey barriers, km posts, a sign gantry
    conc = tex("concrete", like=(160, 156, 146))
    z = ASPHALT_FROM + 10.0
    while z < CROSSING_Z - 40.0:
        rx = road_x(z)
        if rng.random() < 0.35:
            side = rng.choice((-1, 1))
            m.add(box(0.6, 0.82, 3.2, conc, center=(rx + side * (ROAD_W / 2.0 + 1.6), 0.41, z)), )
        if int(z) % 5 == 0:
            m.add(box(0.12, 0.9, 0.12, (230, 228, 220), center=(rx + ROAD_W / 2.0 + 1.0, 0.45, z)))
        z += 20.0
    zs = SECTIONS[2] + 10.0
    rx = road_x(zs)
    for side in (-1, 1):
        m.add(box(0.2, 5.4, 0.2, (90, 94, 96), center=(rx + side * (ROAD_W / 2.0 + 1.0), 2.7, zs)))
    m.add(box(ROAD_W + 2.4, 1.4, 0.1, (40, 92, 60), center=(rx, 5.2, zs)))
    m.add(box(ROAD_W + 2.0, 0.1, 0.06, (220, 220, 210), center=(rx, 5.1, zs - 0.06)))
    return out


def _crossing(m, rng):
    rx = road_x(CROSSING_Z)
    ballast = tex("ballast", like=(96, 92, 88))
    sleeper = tex("sleeper", like=(70, 56, 44))
    rail = tex("steel", like=(120, 122, 126))
    m.add(quad_xz(-320.0, CROSSING_Z - 2.6, 560.0, CROSSING_Z + 2.6, 0.05, ballast, layer=1, seg=20.0))
    for dz in (-0.75, 0.75):
        m.add(box(880.0, 0.14, 0.1, rail, center=(120.0, 0.17, CROSSING_Z + dz), seg=40.0))
    x = -300.0
    while x < 540.0:
        if abs(x - rx) > ROAD_W / 2.0:
            m.add(box(0.26, 0.08, 2.6, sleeper, center=(x, 0.09, CROSSING_Z)))
        x += 1.3
    m.add(box(ROAD_W, 0.08, 3.0, W7._t("plank", P.WOOD_MID), center=(rx, 0.1, CROSSING_Z)))
    # barrier posts and warning lamps
    for side in (-1, 1):
        px = rx + side * (ROAD_W / 2.0 + 0.8)
        m.add(box(0.4, 1.1, 0.4, (200, 196, 186), center=(px, 0.55, BARRIER_Z)))
        m.add(box(0.12, 3.2, 0.12, (40, 40, 42), center=(px, 1.6, BARRIER_Z + 1.5)))
        m.add(box(0.9, 0.12, 0.08, (230, 228, 220), center=(px, 2.6, BARRIER_Z + 1.5)))
        m.add(box(0.5, 0.5, 0.1, (220, 40, 30), center=(px, 3.1, BARRIER_Z + 1.5), emissive=True))
    # the border post: hut (the epilogue films keep its footprint), flag, sign
    hx, hz = rx - 10.0, CROSSING_Z - 12.0
    wall = W7._t("plaster", (178, 174, 160))
    m.add(box(3.0, 2.6, 2.4, wall, center=(hx, 1.3, hz)))
    m.add(box(3.1, 0.3, 2.5, W7._t("stone", P.STONE_D), center=(hx, 0.15, hz)))
    m.add(box(3.6, 0.16, 3.0, W7._t("tin", W7.ROOF_METAL), center=(hx, 2.72, hz)))
    m.add(box(1.2, 0.8, 0.06, W7.WIN_LIT, center=(hx + 0.5, 1.6, hz + 1.23), emissive=True))
    m.add(box(1.0, 0.8, 0.06, W7.WIN_LIT, center=(hx + 1.53, 1.6, hz), emissive=True))
    m.add(box(0.06, 1.9, 0.9, W7._t("plank", W7.WOOD_D), center=(hx - 1.53, 0.95, hz)))
    for i in range(6):
        col = (210, 40, 36) if i % 2 == 0 else (236, 232, 222)
        m.add(box(0.3, 0.42, 0.3, col, center=(hx + 2.2, 0.21 + 0.42 * i, hz + 1.8)))
    m.add(box(0.1, 7.0, 0.1, (180, 180, 176), center=(hx - 2.6, 3.5, hz - 1.0)))
    for i, col in enumerate(((30, 60, 150), (230, 196, 40), (196, 36, 40))):
        m.add(box(0.03, 0.9, 0.5, col, center=(hx - 2.6, 6.4, hz - 1.0 + 0.3 + i * 0.5)), )
    m.add(box(2.4, 1.0, 0.08, (36, 70, 140), center=(rx + ROAD_W / 2.0 + 2.4, 2.2, CROSSING_Z - 18.0)))
    m.add(box(2.2, 0.08, 0.1, (230, 230, 220), center=(rx + ROAD_W / 2.0 + 2.4, 2.0, CROSSING_Z - 18.05)))
    for side in (-1, 1):
        m.add(box(0.12, 2.6, 0.12, (90, 94, 96), center=(rx + ROAD_W / 2.0 + 2.4 + side * 1.0, 1.3, CROSSING_Z - 18.0)))
    # border fence north of the line, with the road gap
    steel = (88, 92, 94)
    x = -160.0
    while x < 160.0:
        if abs(x - rx) > ROAD_W / 2.0 + 2.0:
            m.add(box(0.1, 2.4, 0.1, steel, center=(x, 1.2, CROSSING_Z + 7.0)))
            nx = x + 3.0
            if abs(nx - rx) > ROAD_W / 2.0 + 2.0:
                for y in (0.6, 1.4, 2.2):
                    m.add(box(3.0, 0.03, 0.03, steel, center=(x + 1.5, y, CROSSING_Z + 7.0)))
        x += 3.0
    # telegraph poles along the line
    x = -280.0
    while x < 520.0:
        if abs(x - rx) > 12.0:
            m.add(W7._pole(), rot_y(90), (x, 0.0, CROSSING_Z - 5.0))
        x += 48.0


def renderer():
    """(renderer, None, 0, wreck spots), built on first use."""
    got = _cache.get("r")
    if got is not None:
        return got
    from engine3d import Renderer  # lazy: the caller owns renderer import errors
    r = Renderer(RES[0], RES[1], fog=FOG, fog_start=FOG_START, fog_end=FOG_END)
    r.light = Light(**LOOK["light"])
    rng = random.Random(812)
    m = Mesh()
    _ground(m, rng)
    _road(m)
    _road_wear(m)
    _ditch(m, rng)
    _poles(m)
    _verge_trees(m, rng)
    _farmsteads(m, rng)
    _villages(m, rng)
    _ridges(m, rng)
    wrecks = _wrecks(m, rng)
    _crossing(m, rng)
    _roadside_landmarks(m)  # static detail, no extra RNG in the wreck/spawn path
    _zones(m)
    _verge_grass(m)
    _backstretch(m)
    _cache["faces"] = len(m.faces)
    r.bake(m)
    _cache["r"] = (r, None, 0, wrecks)
    return _cache["r"]


def wrecks():
    return renderer()[3]


def frame(eye, tgt, fov, t=0, size=None, look="dawn", lights=()):
    """Camera, light and sky (dawn, or ``look`` night for the epilogue's
    estate); static set queued.  ``t`` in ms.  ``size`` is the films'
    letterbox buffer; play frames go back to ``RES``."""
    r = renderer()[0]
    r.resize(*(size or RES))
    r.set_camera(eye, tgt, fov, 0.0)
    lk = W7.LOOKS[look]
    if look == "dawn":
        r.fog, r.fog_start, r.fog_end = FOG, FOG_START, FOG_END
    else:
        r.fog, r.fog_start, r.fog_end = lk["fog"], 30.0, 220.0
    r.light = Light(**lk["light"])
    try:
        r.set_lights(list(lights))
    except Exception:
        pass
    W7.sky(r, r.surface, t, look)
    if look == "dawn":
        stratus(r, r.surface, t)
    r.begin()
    r.add_static()
    if look != "dawn":
        return r
    ex, ey, ez = eye
    d = LOOK["light"]["direction"]
    try:
        from cutscenes import m6fx3d as _fx
        r.add_sprite((ex + d[0] * 400.0, ey + 40.0, ez + d[2] * 400.0),
                     _fx.glow((255, 196, 128), 70, t, intensity=0.8, core=(255, 232, 190), max_px=120),
                     layer=_fx.FX_LAYER)
    except Exception:
        pass
    return r


def put(r, key, build, pos, yaw=0.0, pitch=0.0, roll=0.0):
    """Queue a cached rigid mesh at ``pos`` turned by ``yaw`` (nosed by
    ``pitch``, rolled over its long axis by ``roll``): GL packs it once and
    transforms the columns; software copies."""
    m = _cache.get(key)
    if m is None:
        m = _cache[key] = build()
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    if hasattr(r, "add_packed"):
        rows = _cache.get(("rows", key))
        if rows is None:
            rows = _cache[("rows", key)] = r.pack(
                m.verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces])
        if rows is None:
            return
        import numpy as np
        rt = np.array(((cy, 0.0, -sy),
                       (-sy * sp, cp, -cy * sp),
                       (sy * cp, sp, cy * cp)), dtype=rows.dtype)   # pitch then yaw, transposed
        if roll:
            cr, sr = math.cos(math.radians(roll)), math.sin(math.radians(roll))
            rt = np.array(((cr, sr, 0.0), (-sr, cr, 0.0), (0.0, 0.0, 1.0)), dtype=rows.dtype) @ rt
        out = rows.copy()
        out[:, 0:3] = rows[:, 0:3] @ rt
        out[:, 0:3] += np.asarray(pos, dtype=rows.dtype)
        out[:, 6:9] = rows[:, 6:9] @ rt
        r.add_packed(out)
        return
    from cutscenes import m6world3d as _w
    s = Mesh()
    verts = []
    for p in m.verts:
        verts.append(_xf(p, pos, yaw, pitch, roll))
    s.verts = verts
    s.faces = list(m.faces)
    _w.add(r, s)


def present(r, surface):
    from cutscenes import m6fx3d as _fx  # lazy: numpy stack
    surf = r.surface
    r.flush(surf)
    try:
        _fx.grade_cine(surf)
    except Exception:
        pass
    _fx.present_crisp(surf, surface)
