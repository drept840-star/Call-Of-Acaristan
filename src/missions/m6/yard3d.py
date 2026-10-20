"""Mission 6 - "Who fired?": the third-person fight after Volkov's death.

The train is gone.  Biribel stands up from the body with one question - who
was on that tower - and the only place in the yard that can answer it is the
Guard terminal in the signal box behind the freight siding.  Three waves stand
between him and it: the two torch Guards already on the strip, the truck
squad, and the men holding the box.  At the terminal the M6 ending film
takes over; its first shot is that terminal reading Ucilev's file.

Over-the-shoulder camera, WASD + relative mouse look, RMB tightens the
shoulder aim, LMB fires the K9, R reloads, Shift sprints, E uses the
terminal.  A death restarts this fight only.

The set is the train scene's: the post-departure live set it already packed
(platform, station, the yard and its lights) is replayed verbatim, the truck
stays parked, and the carriage is long gone.
"""
import math

import pygame

from core.config import (
    HEIGHT, WIDTH, audio, draw_vignette, font_prompt, font_terminal,
    font_terminal_small,
)
from core.outfits import OUTFIT_GUARD
from core.state import STATE
from engine3d import POSES, blend, box, clamp, pose_run

from . import hud3d as H
from . import train3d as T

_w = T._w
_fx = T._fx

# ── the player ────────────────────────────────────────────────────────────
START_POS = (12.0, 0.04, -0.9)     # standing up from the body
START_YAW = 27.0                   # facing the strip and the siding
                                   # (the lens clears the gantry post)
WALK, SPRINT, AIM_WALK = 3.0, 5.2, 1.8
BODY_R = 0.32                      # collision radius
STEP_UP = 0.62                     # the platform edge is climbable
EYE_H = 1.55                       # camera pivot above the feet
# Far enough right that the K9's line to the crosshair clears his shoulder.
BOOM = (2.40, 0.80, 0.06)          # back, right, up (hip)
BOOM_ADS = (1.40, 0.70, 0.02)      # tight shoulder aim
BLADE = 12.0                       # stance angle: the gun shoulder to the lens
# The third-person gun is seen from behind, its shadow side to the lens: more
# of the viewmodel's cool lift, or the black anodising vanishes on the night.
K9_TINT = ((150, 162, 182), 0.22)
FOV, FOV_ADS = 62.0, 44.0
SENS = 0.12                        # degrees per mouse count
PITCH_LIM = (-38.0, 32.0)
MAG, RESERVE = 30, 120
FIRE_GAP = 0.08                    # K9 cyclic, s
RELOAD_S = 1.6
HP_REGEN_DELAY, HP_REGEN = 4.0, 9.0
HIT_BODY, HIT_HEAD = 22, 64

# ── the terminal ──────────────────────────────────────────────────────────
TERMINAL = (T.SIGNAL_BOX[0] + 1.0, T.SIGNAL_BOX[1] + 1.75)   # at the door
TERMINAL_R = 1.6
# The siding is a wall of wagons between him and the box: the marker leads
# round its east end first.
SIDING_END = (22.6, -6.6)

# ── the world: walkable heights and blockers (x0, y0, z0, x1, y1, z1) ────
# The yard is walled: west and south concrete, the station and two short
# walls to the north, and to the east a pair of lowered booms where the
# tracks leave.  The walls sit just outside BOUNDS.
WALL_W, WALL_E, WALL_S, WALL_N = -28.8, 29.8, -19.8, 12.0
BOUNDS = (-28.2, 29.2, -19.2, 8.6)
ROAD_GATE = (T.TRUCK_X - 2.0, T.TRUCK_X + 2.2)      # x span of the road gates
EAST_GAP = (-7.0, 3.4)                               # z span where tracks leave
WEST_DOORS = (-12.4, -7.0)                           # z of the personnel doors
LAMPS = ((-26.6, -17.6), (-26.6, -1.0), (-26.6, 9.0), (-8.0, -17.8),
         (7.0, -17.8), (27.6, -17.6), (27.6, -9.6), (27.6, 7.0))


def _blockers():
    b = [
        (-2.5, 0.0, 9.0, 16.5, 2.6, 12.2),          # station
        (-17.1, 0.0, 9.8, -2.1, 2.2, 11.6),         # its left wing
        (17.4, 0.0, 7.9, 18.6, 7.0, 9.1),           # signal tower
        (T.TRUCK_X - 1.15, 0.0, T.TRUCK_STOP_Z - T.TRUCK_HALF_L,
         T.TRUCK_X + 1.15, 2.6, T.TRUCK_STOP_Z + T.TRUCK_HALF_L),
        (T.FREIGHT_END_X - 0.3, 0.0, T.FREIGHT_Z - 1.5,
         T.FREIGHT_END_X + 0.3, 1.1, T.FREIGHT_Z + 1.5),  # buffer stop
        (T.SIGNAL_BOX[0] - 1.6, 0.0, T.SIGNAL_BOX[1] - 1.3,
         T.SIGNAL_BOX[0] + 1.6, 2.8, T.SIGNAL_BOX[1] + 1.3),
        (T.SIGNAL_BOX[0] - 3.3, 0.0, T.SIGNAL_BOX[1] - 0.4,
         T.SIGNAL_BOX[0] - 1.9, 0.9, T.SIGNAL_BOX[1] + 1.2),  # oil drums
        (-3.6, 0.0, -7.65, -1.4, 0.75, -6.75),      # sleeper stack
        (27.8, 0.0, -10.4, 29.8, 3.4, -8.8),        # relay hut
        # the walls: never reached on foot (BOUNDS stops him first), but
        # they keep the camera boom inside the yard
        (WALL_W - 0.4, 0.0, WALL_S - 0.4, WALL_W + 0.25, 2.6, WALL_N + 0.4),
        (WALL_E - 0.25, 0.0, WALL_S - 0.4, WALL_E + 0.4, 2.6, WALL_N + 0.4),
        (WALL_W - 0.4, 0.0, WALL_S - 0.4, WALL_E + 0.4, 2.6, WALL_S + 0.25),
    ]
    for gx in (-7.0, 13.0):                         # gantry posts
        for gz in (1.8, -7.2):
            b.append((gx - 0.12, 0.0, gz - 0.12, gx + 0.12, 6.3, gz + 0.12))
    for cx, kind, _col in T._FREIGHT_CARS:
        top = {"box": 3.9, "tank": 3.5}.get(kind, 2.85)
        b.append((cx - T._FREIGHT_L * 0.5, 0.0, T.FREIGHT_Z - 1.45,
                  cx + T._FREIGHT_L * 0.5, top, T.FREIGHT_Z + 1.45))
    for cx, cz, hw, hd, top in T._CRATES:
        b.append((cx - hw, T._SLOT_GROUND, cz - hd, cx + hw, top, cz + hd))
    return tuple(b)


BLOCKERS = _blockers()


def _screen_right(yaw):
    """The direction that is right on screen (``T._right`` is mirrored)."""
    r = T._right(yaw)
    return (-r[0], 0.0, -r[2])


def ground_y(x, z):
    """Walkable height: platform (and the strip under the station wall), the
    steps off its east end, ballast and yard."""
    if -21.0 <= x <= 21.0 and 2.7 <= z <= (9.0 if -2.5 <= x <= 16.5 else 7.7):
        return T._SLOT_GROUND
    if 21.0 < x <= 22.5 and 5.2 <= z <= 6.6:
        return T._SLOT_GROUND * (1.0 - (x - 21.0) / 1.5)
    return 0.04


_SET_CACHE = {}
_WALL = (44, 47, 54)
_POST = (34, 36, 42)
_SNOW = (176, 186, 202)


def _wall_run(add, x0, z0, x1, z1, h=2.6):
    """An axis-aligned concrete run with posts every 4 m and a snow cap."""
    along_x = abs(x1 - x0) >= abs(z1 - z0)
    length = abs(x1 - x0) if along_x else abs(z1 - z0)
    if length < 0.05:
        return
    cx, cz = (x0 + x1) * 0.5, (z0 + z1) * 0.5
    w, d = (length, 0.4) if along_x else (0.4, length)
    seg = max(1, int(length / 4.0))
    add(box(w, h, d, _WALL, center=(cx, h * 0.5, cz), seg=seg))
    add(box(w + 0.08, 0.08, d + 0.08, _SNOW, center=(cx, h + 0.04, cz), seg=seg))
    add(box(w, 0.35, d + 0.5, _SNOW, center=(cx, 0.12, cz), seg=seg))
    for i in range(seg + 1):
        k = i / float(seg)
        px = x0 + (x1 - x0) * k
        pz = z0 + (z1 - z0) * k
        add(box(0.5, h + 0.25, 0.5, _POST, center=(px, (h + 0.25) * 0.5, pz)))


def _gate(add, x0, x1, z):
    """A shut chain-link road gate across x0..x1 at z."""
    for gx in (x0, x1):
        add(box(0.22, 2.9, 0.22, _POST, center=(gx, 1.45, z)))
    for gy in (0.25, 1.25, 2.25):
        add(box(x1 - x0, 0.07, 0.07, (70, 74, 82), center=((x0 + x1) * 0.5, gy, z)))
    n = int((x1 - x0) / 0.45)
    for i in range(1, n):
        add(box(0.03, 2.0, 0.03, (62, 66, 74),
                center=(x0 + (x1 - x0) * i / n, 1.25, z)))
    add(box(0.5, 0.35, 0.05, (176, 52, 40), center=((x0 + x1) * 0.5, 1.6, z - 0.06)))


def _boom(add, x, z0, z1):
    """A lowered red-and-white boom across the track gap."""
    add(box(0.3, 1.2, 0.3, _POST, center=(x, 0.6, z0)))
    n = 8
    for i in range(n):
        za = z0 + (z1 - z0) * i / n
        zb = z0 + (z1 - z0) * (i + 1) / n
        add(box(0.14, 0.14, abs(zb - za), (210, 40, 34) if i % 2 else (226, 222, 214),
                center=(x, 1.0, (za + zb) * 0.5)))


def _perimeter_mesh():
    m = _SET_CACHE.get("perimeter")
    if m is not None:
        return m
    from engine3d import Mesh
    from engine3d.core import quad_xz
    m = Mesh()
    add = m.add
    # ground out to the horizon: no edge of the world past the walls
    add(quad_xz(-160, -160, 160, 160, -0.02, (46, 54, 68), seg=12))
    g0, g1 = ROAD_GATE
    # south: concrete, the road gate
    _wall_run(add, WALL_W, WALL_S, g0, WALL_S)
    _gate(add, g0, g1, WALL_S)
    _wall_run(add, g1, WALL_S, WALL_E, WALL_S)
    # west: concrete, two personnel doors the Guard comes through
    _wall_run(add, WALL_W, WALL_S, WALL_W, WALL_N)
    for dz in WEST_DOORS:
        add(box(0.08, 2.1, 1.1, (26, 28, 32), center=(WALL_W + 0.24, 1.05, dz)))
        add(box(0.10, 0.12, 1.3, _POST, center=(WALL_W + 0.25, 2.16, dz)))
        add(box(0.06, 0.12, 0.3, (255, 214, 150), center=(WALL_W + 0.3, 2.45, dz),
                emissive=True))
    # east: concrete either side of the gap the tracks leave through
    e0, e1 = EAST_GAP
    _wall_run(add, WALL_E, WALL_S, WALL_E, e0)
    _wall_run(add, WALL_E, e1, WALL_E, WALL_N)
    _boom(add, WALL_E - 0.3, e0 + 0.2, -2.2)
    _boom(add, WALL_E - 0.3, -2.0, e1 - 0.2)
    # north: the station is the wall; short runs and the road gate fill in
    _wall_run(add, WALL_W, WALL_N, -17.2, WALL_N)
    _wall_run(add, 16.6, WALL_N, g0, WALL_N)
    _gate(add, g0, g1, WALL_N)
    _wall_run(add, g1, WALL_N, WALL_E, WALL_N)
    # lamp masts inside the walls
    for lx, lz in LAMPS:
        add(box(0.16, 6.4, 0.16, (34, 38, 44), center=(lx, 3.2, lz)))
        add(box(0.5, 0.16, 0.36, (255, 222, 168), center=(lx, 6.3, lz),
                emissive=True))
    _SET_CACHE["perimeter"] = m
    return m


def _perimeter_sprites(r, tm):
    for i, (lx, lz) in enumerate(LAMPS):
        r.add_sprite((lx, 6.2, lz), _fx.sodium_lamp(tm, seed=480 + i,
                                                     radius_m=2.6, intensity=0.6),
                     layer=_fx.FX_LAYER)
        r.add_sprite((lx, 0.05, lz), _fx.window_glow((255, 186, 118), 3.6, 3.0, 0.16),
                     layer=_fx.FX_LAYER)
    for dz in WEST_DOORS:
        r.add_sprite((WALL_W + 0.35, 2.45, dz),
                     _fx.glow((255, 210, 150), 0.6, tm, intensity=0.7),
                     layer=_fx.FX_LAYER)


def _blocked(x, z, feet, r=BODY_R):
    if not (BOUNDS[0] <= x <= BOUNDS[1] and BOUNDS[2] <= z <= BOUNDS[3]):
        return True
    if ground_y(x, z) > feet + STEP_UP:
        return True
    for x0, y0, z0, x1, y1, z1 in BLOCKERS:
        if y1 <= feet + STEP_UP or y0 >= feet + 1.7:
            continue
        if x0 - r < x < x1 + r and z0 - r < z < z1 + r:
            return True
    return False


def _sight_blocked(a, b):
    """True when a blocker stands between two points (eye/chest lines)."""
    d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    dist = math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2])
    if dist < 1e-6:
        return False
    d = (d[0] / dist, d[1] / dist, d[2] / dist)
    for x0, y0, z0, x1, y1, z1 in BLOCKERS:
        hit = T._ray_aabb(a, d, (x0, y0, z0), (x1, y1, z1))
        if hit is not None and hit < dist - 0.2:
            return True
    return False


# ── the waves ─────────────────────────────────────────────────────────────
# Each Guard: kind, start (x, y, z), route to his post (last point = post),
# and the post's pose.  Wave 1 is already there (the torch Guards on the
# strip); waves 2 and 3 enter from the truck and from the signal box door.
_TRUCK_DROP = (T.TRUCK_X, 0.04, T.TRUCK_STOP_Z - T.TRUCK_HALF_L - 0.55)
_BOX_DOOR = (T.SIGNAL_BOX[0] + 1.0, 0.04, T.SIGNAL_BOX[1] + 1.6)
WAVES = (
    (   # the strip: the torch Guards, and a rifleman coming down it
        ("rifle", (14.8, 0.04, -7.1), ((14.6, 0.04, -7.3),), "cover", True, 0.0),
        ("rifle", (16.9, 0.04, -7.5), ((17.4, 0.04, -7.4),), "cover", True, 0.0),
        ("rifle", (-27.9, 0.04, -7.0), ((-6.0, 0.04, -6.3), (4.2, 0.04, -6.4),
                                        (8.4, 0.04, -6.6)), "cover", False, 1.0),
    ),
    (   # the truck squad, in two drops off the tailgate
        ("rusher", _TRUCK_DROP, ((22.8, 0.04, 3.6), (19.5, 0.04, 2.4),
                                 (15.5, 0.04, 2.0)), "crouch", False, 0.0),
        ("heavy", _TRUCK_DROP, ((22.8, 0.04, 3.4), (21.8, 0.04, 2.0)),
         "stand", False, 0.6),
        ("rifle", _TRUCK_DROP, ((22.8, 0.04, 5.6), (21.0, 0.58, 5.9),
                                (19.6, 0.58, 4.4)), "cover", False, 1.2),
        ("officer", _TRUCK_DROP, ((23.0, 0.04, 2.0), (23.0, 0.04, -4.0),
                                  (22.3, 0.04, -7.6)), "cover", False, 9.0),
        ("rifle", _TRUCK_DROP, ((22.6, 0.04, 2.0), (22.6, 0.04, -3.2)),
         "crouch", False, 9.8),
    ),
    (   # the men holding the signal box, and two round the far side
        ("officer", _BOX_DOOR, ((T.SIGNAL_BOX[0] - 1.4, 0.04, -12.4),),
         "cover", False, 0.0),
        ("rifle", _BOX_DOOR, ((20.6, 0.04, -12.6), (22.4, 0.04, -9.8)),
         "cover", False, 0.7),
        ("rifle", _BOX_DOOR, ((19.8, 0.04, -12.2),), "cover", False, 1.4),
        ("heavy", _BOX_DOOR, ((16.2, 0.04, -12.3),), "stand", False, 2.2),
        ("rifle", (-27.9, 0.04, -12.4), ((8.0, 0.04, -12.4), (12.6, 0.04, -12.4)),
         "cover", False, 2.0),
        ("rusher", (-27.9, 0.04, -12.4), ((10.0, 0.04, -12.3), (20.8, 0.04, -12.3)),
         "crouch", False, 3.0),
    ),
)
# Clear lanes across the yard (every edge was checked against BLOCKERS: the
# Guard walk straight lines and do not collide).  A Guard who has not seen
# Biribel for HUNT_AFTER seconds walks the lanes toward him.
NAV = {
    "body": (12.0, 0.04, -1.0), "cross": (22.6, 0.04, -1.0),
    "road": (22.6, 0.04, -5.0), "box_e": (22.6, 0.04, -12.4),
    "box": (18.5, 0.04, -12.6), "far": (12.6, 0.04, -12.4),
    "far_w": (4.0, 0.04, -12.4), "far_ww": (-6.0, 0.04, -12.4),
    "strip": (15.0, 0.04, -6.4), "strip_m": (8.4, 0.04, -6.4),
    "strip_w": (-5.0, 0.04, -6.3), "track_e": (19.5, 0.04, 2.0),
    "track_w": (5.0, 0.04, 1.6),
}
NAV_EDGES = (
    ("body", "cross"), ("body", "strip"), ("body", "track_e"), ("body", "track_w"),
    ("cross", "road"), ("cross", "track_e"), ("road", "box_e"), ("road", "strip"),
    ("box_e", "box"), ("box", "far"), ("far", "far_w"), ("far_w", "far_ww"),
    ("strip", "strip_m"), ("strip_m", "strip_w"), ("strip_m", "track_w"),
)
HUNT_AFTER = 5.0
WAVE2_AT = 30.0                    # the truck comes even if he hides
BOX_WAKE_R = 9.0                   # the box wakes when he gets this close
ENTRY_SPEED = {"rifle": 2.8, "rusher": 4.2, "heavy": 1.9, "officer": 3.2,
               "marksman": 2.4}


def _make_guard(wave, i, spec, now):
    kind, start, route, post_pose, torch, delay = spec
    prof = T._guard_profile(kind)
    return {
        "kind": kind, "wave": wave, "slot": 10 * wave + i, "pos": tuple(start),
        "route": tuple(route), "wp": 0, "post_pose": post_pose,
        "torch": torch, "hp": prof["hp"], "alive": True, "dead_t": -9.0,
        "yaw": 0.0, "moving": False, "posted": False,
        "next_burst": now + 1.2 + 0.7 * i, "burst_left": 0, "burst_next": 0.0,
        "last_shot_t": -9.0, "hit_t": -9.0, "hit_dir": None,
        "react": now + delay + (1.0 if wave == 0 else 0.4),
        "spawn_at": now + delay,
        "last_seen": now + delay,
    }


def _nav_near(p):
    return min(NAV, key=lambda k: math.hypot(NAV[k][0] - p[0], NAV[k][2] - p[2]))


def _nav_path(a, b):
    """Breadth-first lane path between two nav nodes."""
    nbr = {k: [] for k in NAV}
    for u, v in NAV_EDGES:
        nbr[u].append(v)
        nbr[v].append(u)
    prev, todo = {a: None}, [a]
    while todo:
        u = todo.pop(0)
        if u == b:
            break
        for v in nbr[u]:
            if v not in prev:
                prev[v] = u
                todo.append(v)
    if b not in prev:
        return []
    out = []
    while b is not None:
        out.append(NAV[b])
        b = prev[b]
    return out[::-1]


# The aim's torso and head; the arms are IK'd onto the K9 itself.
_AIM = dict(POSES["aim"])


# ── the K9 in third person ────────────────────────────────────────────────
# The authored K93D (the first-person asset) without the first-person gloves,
# in gun space: +z muzzle, +y up, +x the shooter's right, origin at the
# trigger.  It is mounted with the stock in Biribel's shoulder pocket and
# aimed down the actual aim; both hands are IK'd onto it, so the hold is a
# real two-handed, shouldered hold instead of a pose with a gun near it.
K9_GRIP = (0.012, -0.100, -0.105)     # right hand: pistol grip
K9_FORE = (-0.006, 0.035, 0.195)      # left hand: angled foregrip
K9_MAGWELL = (0.0, -0.120, 0.060)     # left hand mid-reload
K9_PORT = (0.045, 0.040, 0.030)       # ejection port
K9_STOCK = 0.27                       # trigger ahead of the shoulder pocket
# Patrol carry: muzzle down and out at the right hip, where the lens behind
# his right shoulder can see it (across the chest it is hidden by his back).
CARRY_PITCH, CARRY_YAW = -34.0, -12.0
KICK_BACK, KICK_UP = 0.055, 5.0       # per shot: gun into the shoulder, muzzle rise
CAM_KICK, CAM_SHAKE = 0.9, 0.030      # per shot: view punch (deg), lens shake (m)
AIM_CLIMB = 0.30                      # per shot: how far the aim itself climbs
_K9 = {}


def _k9_asset():
    """(mesh, muzzle) of the K93D without gloves; the procedural K9 (hands
    and all) only if the authored asset is missing."""
    if "mesh" in _K9:
        return _K9["mesh"], _K9["muzzle"]
    mesh, muzzle = None, (0.0, 0.035, T.VM_MUZZLE_Z)
    try:
        import json
        import os
        from engine3d.core import Mesh
        from game.render3d_bridge import MESHES_DIR
        with open(os.path.join(MESHES_DIR, "k93d.mesh.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        m = Mesh()
        m.verts = [tuple(float(c) for c in v) for v in data["verts"]]
        m.faces = [(tuple(f[0]), tuple(f[1]), 2, True, False) for f in data["faces"]]
        muzzle = tuple(float(c) for c in
                       data.get("meta", {}).get("muzzle", (0.0, 0.083, 0.595)))
        mesh = m
    except Exception:
        mesh = None
    if mesh is None:
        mesh = T._vm_mesh()
    _K9["mesh"], _K9["muzzle"] = mesh, muzzle
    return mesh, muzzle


def _gun_pt(O, B, g):
    """Gun-space point -> world, for origin O and basis rows B (right, up, fwd)."""
    return tuple(O[i] + B[0][i] * g[0] + B[1][i] * g[1] + B[2][i] * g[2]
                 for i in range(3))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _gun_basis(yaw, pitch, roll=0.0):
    """(right, up, fwd) for a gun aimed at (yaw, pitch), rolled about its bore."""
    f = T._forward(yaw, pitch)
    rgt = _screen_right(yaw)
    up = _cross(f, rgt)
    if roll:
        c, sn = math.cos(math.radians(roll)), math.sin(math.radians(roll))
        rgt, up = (tuple(rgt[i] * c + up[i] * sn for i in range(3)),
                   tuple(up[i] * c - rgt[i] * sn for i in range(3)))
    return (rgt, up, f)


def _draw_k9(r, O, B):
    mesh, _muzzle = _k9_asset()
    if hasattr(r, "add_packed"):
        import numpy as np
        rows = _K9.get("rows")
        if rows is None:
            rows = _K9["rows"] = r.pack(
                mesh.verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces],
                tint=K9_TINT)
        if rows is None:
            return
        M = np.array(B, dtype=np.float32)
        out = rows.copy()
        out[:, 0:3] = rows[:, 0:3] @ M + np.array(O, dtype=np.float32)
        out[:, 6:9] = rows[:, 6:9] @ M
        r.add_packed(out)
        return
    from engine3d import Mesh
    m = Mesh()
    m.verts = [_gun_pt(O, B, v) for v in mesh.verts]
    m.faces = list(mesh.faces)
    _w.add(r, m)


def _flash_mesh(O, B, muzzle, seed):
    """A three-blade muzzle star at the muzzle, a new twist every shot."""
    from engine3d import Mesh
    m = Mesh()
    tw = (seed * 37 % 90) * math.pi / 180.0
    c, sn = math.cos(tw), math.sin(tw)
    mz = muzzle[2] + 0.06
    parts = [box(0.035, 0.035, 0.20, (255, 220, 150), center=(muzzle[0], muzzle[1], mz + 0.05),
                 emissive=True)]
    for w, h in ((0.22, 0.03), (0.03, 0.22)):
        parts.append(box(w, h, 0.03, (255, 200, 120), center=(0.0, 0.0, 0.0),
                         emissive=True))
    for i, part in enumerate(parts):
        if i:
            part.verts = [(v[0] * c - v[1] * sn + muzzle[0],
                           v[0] * sn + v[1] * c + muzzle[1], v[2] + mz)
                          for v in part.verts]
        part.verts = [_gun_pt(O, B, v) for v in part.verts]
        m.add(part)
    return m


class YardScene:
    def __init__(self):
        self._active = False
        self.paused = False
        self.audio = None
        self.restart()

    # ── lifecycle ──────────────────────────────────────────────────────
    def restart(self):
        self.t = 0.0
        self.pos = START_POS
        self.yaw = START_YAW
        self.pitch = -6.0
        self.body_yaw = _w.yaw_to((0, 0, 0), T._forward(START_YAW, 0.0))
        self.vel = (0.0, 0.0)
        self.stride = 0.0
        self.ads = 0.0
        self.aiming = False
        self.firing = False
        self.sprint = False
        self.keys = set()
        self.mag, self.reserve = MAG, RESERVE
        self.reloading = 0.0
        self.last_fire = -9.0
        self.recoil = 0.0
        self.gun_kick = 0.0          # 1 on a shot, springs back
        self.cam_kick = 0.0          # view punch
        self.shake = 0.0             # lens shake
        self.shots = 0
        self.brass = []              # (t0, pos, vel, seed)
        self.impacts = []            # (t0, pos, kind)
        self.hurt = 0.0
        self.last_hurt = -9.0
        self.hit_mark = -9.0
        self.dmg_marks = []
        self.tracers = []
        self.sparks = []
        self.guards = []
        self.pending = []
        self.wave = -1
        self._start_wave(0)
        self.dying = False
        self.death_t = 0.0
        self.done = False
        self.result = None
        self.near_terminal = False
        self.route_stage = 0
        self._muzzle = None
        p = STATE.player
        if p is not None:
            p.hp = getattr(p, "max_hp", 115) or 115

    def begin(self):
        self.restart()
        self._active = True
        self.paused = False
        STATE.m6_yard_active = True
        STATE.m6_yard_result = None
        if self.audio is None:
            try:
                from .m6_audio import M6TrainAudio
                self.audio = M6TrainAudio(audio)
            except Exception:
                self.audio = None
        self._grab(True)
        # pay the set build now, not on the first visible frame
        try:
            self.draw(pygame.Surface((WIDTH, HEIGHT)))
        except Exception:
            pass

    def active(self):
        return self._active

    def _grab(self, on):
        try:
            pygame.event.set_grab(bool(on))
            pygame.mouse.set_visible(not on)
            pygame.mouse.get_rel()
        except Exception:
            pass

    def set_paused(self, paused):
        self.paused = bool(paused)
        self._grab(self._active and not self.paused)

    def finish(self, result="win"):
        if self.done:
            return False
        self.done = True
        self.result = result
        self._active = False
        STATE.m6_yard_active = False
        STATE.m6_yard_result = result
        self._grab(False)
        from . import flow as _flow
        return _flow.on_yard_done(result)

    # ── input ──────────────────────────────────────────────────────────
    def handle_event(self, event):
        if not self._active or self.paused:
            return
        if event.type == pygame.MOUSEMOTION and not self.dying:
            dx, dy = event.rel
            sens = SENS * (1.0 - 0.35 * self.ads)
            # engine3d's screen-right is -x at yaw 0: mouse right turns
            # the yaw down (same convention as the train's mouse look)
            self.yaw = (self.yaw - dx * sens) % 360.0
            self.pitch = clamp(self.pitch - dy * sens, *PITCH_LIM)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.firing = True
            elif event.button == 3:
                self.aiming = True
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.firing = False
            elif event.button == 3:
                self.aiming = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self._begin_reload()
            elif event.key == pygame.K_e and self.near_terminal:
                self.finish("win")

    # ── update ─────────────────────────────────────────────────────────
    def update(self, keys=None):
        if not self._active or self.paused:
            return
        dt = clamp(float(getattr(STATE, "dt", 1.0 / 60.0)), 0.0, 0.05)
        self.t += dt
        if self.dying:
            self.death_t += dt
            if self.death_t >= 2.6:
                self.restart()          # this fight only, from the body
            return
        self._move(keys, dt)
        self.ads += ((1.0 if self.aiming and not self.reloading else 0.0)
                     - self.ads) * min(1.0, dt * 12.0)
        if self.reloading:
            self.reloading = max(0.0, self.reloading - dt)
            if not self.reloading:
                n = min(MAG - self.mag, self.reserve)
                self.mag += n
                self.reserve -= n
        if self.firing and not self.reloading:
            self._fire()
        self.recoil = max(0.0, self.recoil - dt * 6.0)
        self.gun_kick = max(0.0, self.gun_kick - dt * 13.0)
        self.cam_kick *= math.exp(-dt * 11.0)
        self.shake = max(0.0, self.shake - dt * 4.5)
        self.brass = [b for b in self.brass if self.t - b[0] < 4.0][-30:]
        self.impacts = [x for x in self.impacts if self.t - x[0] < 0.6]
        self._update_guards(dt)
        self._update_waves()
        self._update_player_hp(dt)
        tx, tz = TERMINAL
        self.near_terminal = (self._all_clear()
                              and math.hypot(self.pos[0] - tx,
                                             self.pos[2] - tz) <= TERMINAL_R)
        if self.route_stage == 0 and (
                math.hypot(self.pos[0] - SIDING_END[0], self.pos[2] - SIDING_END[1]) < 3.0
                or self.pos[2] < T.FREIGHT_Z - 1.6):
            self.route_stage = 1
        now = self.t
        self.tracers = [x for x in self.tracers if now - x[0] < 0.10]
        self.sparks = [x for x in self.sparks if now - x[0] < 0.45]
        self.dmg_marks = [m for m in self.dmg_marks if now - m[0] < 0.9]

    def _move(self, keys, dt):
        k = keys if keys is not None else pygame.key.get_pressed()

        def down(*codes):
            try:
                return any(k[c] for c in codes)
            except Exception:
                return False

        fwd_in = (1 if down(pygame.K_w, pygame.K_UP) else 0) - \
            (1 if down(pygame.K_s, pygame.K_DOWN) else 0)
        side_in = (1 if down(pygame.K_d, pygame.K_RIGHT) else 0) - \
            (1 if down(pygame.K_a, pygame.K_LEFT) else 0)
        self.sprint = down(pygame.K_LSHIFT, pygame.K_RSHIFT) and fwd_in > 0 \
            and self.ads < 0.3 and not self.firing
        f = T._forward(self.yaw, 0.0)
        rgt = _screen_right(self.yaw)
        mx = f[0] * fwd_in + rgt[0] * side_in
        mz = f[2] * fwd_in + rgt[2] * side_in
        n = math.hypot(mx, mz)
        speed = SPRINT if self.sprint else (AIM_WALK if self.ads > 0.5 else WALK)
        want = (mx / n * speed, mz / n * speed) if n > 1e-6 else (0.0, 0.0)
        a = min(1.0, dt * 10.0)
        self.vel = (self.vel[0] + (want[0] - self.vel[0]) * a,
                    self.vel[1] + (want[1] - self.vel[1]) * a)
        x, y, z = self.pos
        nx, nz = x + self.vel[0] * dt, z + self.vel[1] * dt
        if not _blocked(nx, z, y):
            x = nx
        else:
            self.vel = (0.0, self.vel[1])
        if not _blocked(x, nz, y):
            z = nz
        else:
            self.vel = (self.vel[0], 0.0)
        gy = ground_y(x, z)
        y = gy if gy >= y else max(gy, y - dt * 6.0)   # step up, drop down
        self.pos = (x, y, z)
        sp = math.hypot(*self.vel)
        self.stride += sp * dt
        # Facing: the aim when aiming or shooting, else the way he moves.
        if self.ads > 0.2 or self.firing or self.t - self.last_fire < 0.6:
            want_yaw = self._aim_body_yaw() + BLADE
        elif sp > 0.4:
            want_yaw = _w.yaw_to((0, 0, 0), (self.vel[0], 0, self.vel[1]))
        else:
            want_yaw = self._aim_body_yaw() + BLADE
        self.body_yaw = _w.yaw_mix(self.body_yaw, want_yaw, min(1.0, dt * 12.0))

    def _aim_body_yaw(self):
        f = T._forward(self.yaw, 0.0)
        return _w.yaw_to((0, 0, 0), (f[0], 0, f[2]))

    # ── camera and aim ─────────────────────────────────────────────────
    def camera(self):
        """(eye, target, fov) for the over-the-shoulder rig.  The boom is
        shortened when a blocker stands between the shoulder and the lens."""
        back, right, up = (BOOM[i] + (BOOM_ADS[i] - BOOM[i]) * self.ads
                           for i in range(3))
        x, y, z = self.pos
        pivot = (x, y + EYE_H + up, z)
        f = T._forward(self.yaw, self.pitch)
        rgt = _screen_right(self.yaw)
        shoulder = (pivot[0] + rgt[0] * right, pivot[1], pivot[2] + rgt[2] * right)
        d = (-f[0], -f[1], -f[2])
        dist = back
        for x0, y0, z0, x1, y1, z1 in BLOCKERS:
            hit = T._ray_aabb(shoulder, d, (x0, y0, z0), (x1, y1, z1))
            if hit is not None and hit < dist:
                dist = max(0.35, hit - 0.2)
        eye = (shoulder[0] + d[0] * dist, max(y + 0.3, shoulder[1] + d[1] * dist),
               shoulder[2] + d[2] * dist)
        if self.shake > 0.0:
            k = CAM_SHAKE * self.shake
            eye = (eye[0] + math.sin(self.t * 71.0) * k,
                   eye[1] + math.sin(self.t * 59.0 + 1.3) * k,
                   eye[2] + math.sin(self.t * 83.0 + 2.1) * k)
        # the view punches up with each shot and settles
        fv = T._forward(self.yaw, self.pitch + CAM_KICK * self.cam_kick)
        tgt = (eye[0] + fv[0] * 10.0, eye[1] + fv[1] * 10.0, eye[2] + fv[2] * 10.0)
        if self.dying:
            k = clamp(self.death_t / 1.2, 0.0, 1.0)
            eye = (eye[0], eye[1] + 1.4 * k, eye[2])
            tgt = (x, y + 0.3, z)
        fov = FOV + (FOV_ADS - FOV) * self.ads - 1.4 * self.cam_kick
        return eye, tgt, fov, dist

    def _aim_ray(self):
        eye, _tgt, _fov, dist = self.camera()
        f = T._forward(self.yaw + self.recoil * 0.3, self.pitch + self.recoil)
        # start the ray at the shoulder, so nothing behind him is ever hit
        o = (eye[0] + f[0] * dist, eye[1] + f[1] * dist, eye[2] + f[2] * dist)
        return o, f

    def _begin_reload(self):
        if self.reloading or self.mag >= MAG or self.reserve <= 0:
            return
        self.reloading = RELOAD_S
        if self.audio:
            self.audio.reload()

    def _fire(self):
        if self.t - self.last_fire < FIRE_GAP:
            return
        if self.mag <= 0:
            if self.t - self.last_fire > 0.3:
                self.last_fire = self.t
                if self.audio:
                    self.audio.dry()
                self._begin_reload()
            return
        self.mag -= 1
        self.last_fire = self.t
        self.shots += 1
        self.recoil = min(3.0, self.recoil + 0.55)
        self.gun_kick = 1.0
        self.cam_kick = min(2.2, self.cam_kick + 1.0)
        self.shake = min(1.0, self.shake + 0.35)
        # the aim itself climbs a little: hold it down on a long burst
        self.pitch = clamp(self.pitch + AIM_CLIMB, *PITCH_LIM)
        self.yaw = (self.yaw + 0.22 * math.sin(self.shots * 2.39)) % 360.0
        self._eject()
        if self.audio:
            self.audio.shot(suppressed=True)
        o, d = self._aim_ray()
        best, best_g, head = 60.0, None, False
        for x0, y0, z0, x1, y1, z1 in BLOCKERS:
            hit = T._ray_aabb(o, d, (x0, y0, z0), (x1, y1, z1))
            if hit is not None and hit < best:
                best = hit
        if d[1] < -1e-6:
            gy = (0.04 - o[1]) / d[1]
            if 0.0 < gy < best:
                best = gy
        for g in self.guards:
            if not g["alive"]:
                continue
            gx, gy0, gz = g["pos"]
            big = g["kind"] == "heavy"
            for zi, (dy, rad) in enumerate(((1.30, 0.42 if big else 0.38),
                                            (1.58, 0.34 if big else 0.30))):
                hit = T._ray_sphere(o, d, (gx, gy0 + dy, gz), rad)
                if hit is not None and hit < best:
                    best, best_g, head = hit, g, zi == 1
        end = (o[0] + d[0] * best, o[1] + d[1] * best, o[2] + d[2] * best)
        src = self._muzzle or o
        self.tracers.append((self.t, src, end, (255, 214, 150)))
        if best_g is None:
            self.sparks.append((self.t, end))
            self.impacts.append((self.t, end, "dust"))
            if self.audio:
                self.audio.impact(on_enemy=False)
            return
        g = best_g
        self.impacts.append((self.t, end, "blood"))
        g["hp"] -= HIT_HEAD if head else HIT_BODY
        g["hit_t"] = self.t
        g["hit_dir"] = (d[0], d[2])
        self.hit_mark = self.t
        if self.audio:
            (self.audio.headshot if head else
             (lambda: self.audio.impact(on_enemy=True)))()
        if g["hp"] <= 0:
            g["alive"] = False
            g["dead_t"] = self.t
            g["dead_pose"] = "dead_back" if (int(g["slot"]) % 2) else "dead_front"

    # ── the Guard ──────────────────────────────────────────────────────
    def _living(self, wave=None):
        return sum(1 for g in self.guards
                   if g["alive"] and (wave is None or g["wave"] == wave))

    def _start_wave(self, wave):
        self.wave = wave
        self.pending += [_make_guard(wave, i, spec, self.t)
                         for i, spec in enumerate(WAVES[wave])]
        if self.audio and wave == 1:
            self.audio.tailgate()
        if self.audio and wave == 2:
            self.audio.door_creak()

    def _all_clear(self):
        """Every wave started, every Guard down, nobody still on the way."""
        return self.wave >= 2 and not self.pending and self._living() == 0

    def _wave_clear(self, wave):
        return (self._living(wave) == 0
                and not any(g["wave"] == wave for g in self.pending))

    def _update_waves(self):
        due = [g for g in self.pending if self.t >= g["spawn_at"]]
        if due:
            self.pending = [g for g in self.pending if self.t < g["spawn_at"]]
            self.guards += due
        if self.wave == 0 and (self._wave_clear(0) or self.t >= WAVE2_AT):
            self._start_wave(1)
        box = math.hypot(self.pos[0] - T.SIGNAL_BOX[0],
                         self.pos[2] - T.SIGNAL_BOX[1])
        if self.wave == 1 and (self._wave_clear(1) or box <= BOX_WAKE_R):
            self._start_wave(2)

    def _player_chest(self):
        return (self.pos[0], self.pos[1] + 1.25, self.pos[2])

    def _update_guards(self, dt):
        chest = self._player_chest()
        for g in self.guards:
            if not g["alive"] or self.t < g["react"] - (0.0 if g["wave"] else 1.0):
                continue
            prof = T._guard_profile(g["kind"])
            route = g["route"]
            g["moving"] = False
            if g["wp"] < len(route):
                tx, ty, tz = route[g["wp"]]
                x, y, z = g["pos"]
                dx, dz = tx - x, tz - z
                dist = math.hypot(dx, dz)
                speed = ENTRY_SPEED.get(g["kind"], 2.8)
                if dist > 0.08 and self.t >= g["react"]:
                    step = min(dist, speed * dt)
                    k = step / dist
                    g["pos"] = (x + dx * k, y + (ty - y) * k, z + dz * k)
                    g["moving"] = True
                elif dist <= 0.08:
                    g["pos"] = (tx, ty, tz)
                    g["wp"] += 1
            else:
                g["posted"] = True
            gc = (g["pos"][0], g["pos"][1] + 1.38, g["pos"][2])
            sees = not _sight_blocked(gc, chest)
            if sees:
                g["last_seen"] = self.t
            elif g["posted"] and self.t - g["last_seen"] > HUNT_AFTER:
                # hunt: walk the lanes to the node nearest him, then hold
                path = _nav_path(_nav_near(g["pos"]), _nav_near(self.pos))
                if len(path) > 1:
                    g["route"] = tuple(path)
                    g["wp"] = 0
                    g["posted"] = False
                g["last_seen"] = self.t
            rusher = g["kind"] == "rusher"
            if not (g["posted"] or rusher) or not sees:
                continue
            if g["burst_left"] <= 0 and self.t >= g["next_burst"]:
                g["burst_left"] = int(prof["burst"])
                g["burst_next"] = self.t + float(prof.get("telegraph", 0.3))
            if g["burst_left"] > 0 and self.t >= g["burst_next"]:
                self._guard_shot(g, prof, gc, chest)

    def _guard_shot(self, g, prof, src, chest):
        g["burst_left"] -= 1
        g["last_shot_t"] = self.t
        gap = float(prof.get("gap", 0.1))
        g["burst_next"] = self.t + gap
        if g["burst_left"] <= 0:
            g["next_burst"] = self.t + 1.5 + 0.9 * ((g["slot"] * 7 + int(self.t)) % 3)
        dist = math.dist(src, chest)
        moving = math.hypot(*self.vel) > 1.0
        p_hit = clamp(0.62 - dist * 0.016 - (0.22 if moving else 0.0)
                      - (0.12 if self.sprint else 0.0), 0.12, 0.8)
        roll = (math.sin(self.t * 91.7 + g["slot"] * 13.1) + 1.0) * 0.5
        hit = roll < p_hit
        wob = 0.0 if hit else 0.9
        dst = (chest[0] + math.sin(self.t * 8.3 + g["slot"]) * wob,
               chest[1] + 0.2, chest[2] + math.cos(self.t * 6.1 + g["slot"]) * wob)
        self.tracers.append((self.t, src, dst, (255, 208, 150)))
        if self.audio:
            self.audio.guard_shot()
            if not hit:
                self.audio.whiz()
        if not hit:
            return
        p = STATE.player
        if p is None:
            return
        dmg = int(prof["damage"] * 0.8) + 1
        p.hp = max(0, p.hp - dmg)
        self.hurt = max(self.hurt, 0.25 + dmg * 0.025)
        self.last_hurt = self.t
        bearing = (_w.yaw_to(self.pos, g["pos"]) - self._aim_body_yaw()
                   + 180.0) % 360.0 - 180.0
        self.dmg_marks.append((self.t, bearing))
        if p.hp <= 0 and not self.dying:
            self.dying = True
            self.death_t = 0.0
            self.firing = self.aiming = False

    def _update_player_hp(self, dt):
        self.hurt = max(0.0, self.hurt - dt * 1.4)
        p = STATE.player
        if p is None or self.dying:
            return
        top = getattr(p, "max_hp", 115) or 115
        if self.t - self.last_hurt > HP_REGEN_DELAY and p.hp < top:
            p.hp = min(top, p.hp + HP_REGEN * dt)

    # ── draw ───────────────────────────────────────────────────────────
    def draw(self, surface):
        if not self._active:
            return
        r = T._renderer()
        ts = T.scene()
        set_t = T.DURATION + self.t       # the set's clock, after the cut
        tm = set_t * 1000.0
        eye, tgt, fov, _dist = self.camera()
        flashes = []
        if self.t - self.last_fire < 0.05 and self._muzzle:
            flashes.append({"pos": self._muzzle, "color": (255, 196, 120),
                            "intensity": 1.4, "range": 5.0})
        flashes += [
            {"pos": (T.YARD_MAST[0], 5.6, T.YARD_MAST[1] + 0.8),
             "color": (255, 196, 126), "intensity": 0.9, "range": 11.0},
            {"pos": (T.SIGNAL_BOX[0] - 0.5, 1.7, T.SIGNAL_BOX[1] + 2.0),
             "color": (255, 190, 120), "intensity": 0.6, "range": 5.0},
            {"pos": (T.TRUCK_X, 2.6, T.TRUCK_STOP_Z - T.TRUCK_HALF_L - 0.3),
             "color": (255, 214, 150), "intensity": 0.6, "range": 5.0},
        ]
        T._light(r, flashes=flashes)
        r.set_camera(eye, tgt, fov)
        # The GL pass starts from r.surface: repaint the sky every frame, or
        # last frame's additive glows pile up wherever the sky shows.
        r.surface.fill((6, 8, 14))
        _w.night(r, r.surface, tm, top=(4, 6, 13), bot=T.SKY_HORIZON,
                 stars=90, moon=(112.0, 13.0), sodium=(42, 28, 18), seed=71,
                 star_cut=0.62)
        r.begin()
        del _w.LAST[:]
        far = 400.0                       # the carriage is long gone
        if _w.pack_memo_ready(r, "m6_yard_set"):
            _w.pack_memo_replay(r)
        else:
            # The train's set, built for every side (no platform-view cull),
            # inside the walled perimeter.
            _w.pack_memo(r, "m6_yard_set")
            ok = False
            T._FULL_SET = True
            try:
                _w.add(r, _perimeter_mesh())
                _w.rail_platform(r, tm, train=False, snow=1.0)
                ts._draw_station(r, set_t)
                ok = True
            finally:
                T._FULL_SET = False
                _w.pack_memo_end(ok=ok)
        ts._draw_yard_wires(r)
        ts._draw_static_lights(r, set_t, train_offset=far, snow_n=120, beacon=True)
        _perimeter_sprites(r, tm)
        ts._draw_entrances(r, set_t)
        self._draw_volkov(r, set_t)
        self._draw_player(r, tm)
        self._draw_guards(r, tm)
        self._draw_fx(r, tm)
        self._marker_screen = self._project(r, self._objective_point())
        r.flush(r.surface)
        T._grade_play(r.surface, self._wounded())
        pygame.transform.smoothscale(r.surface, (WIDTH, HEIGHT), surface)
        draw_vignette(surface)
        self._draw_hud(surface)

    def _wounded(self):
        p = STATE.player
        top = getattr(p, "max_hp", 115) or 115 if p else 115
        return p is not None and p.hp < top * 0.35

    def _draw_volkov(self, r, set_t):
        st = _SET_CACHE.get("volkov")
        if st is None:      # he does not move again: pose him once
            st = _SET_CACHE["volkov"] = T._volkov_death_state(T.DURATION)
        pos, pose, yaw, _j = st
        _w.actor(r, "volkov", pose, pos, yaw, int(set_t * 1000), seed=91,
                 amp=0.0, rifle_on=False, expression="sad", hd=True,
                 wound=T._wound_stage(T.DURATION - T.HIT_AT),
                 flags=T._volkov_flags(T.DURATION - T.HIT_AT))

    def _eject(self):
        """A casing out of the port: right, up and a little back."""
        if not getattr(self, "_gun", None):
            return
        O, B = self._gun
        port = _gun_pt(O, B, K9_PORT)
        n = self.shots
        rgt, up, f = B
        sp = 2.2 + 0.5 * math.sin(n * 1.7)
        v = tuple(rgt[i] * sp + up[i] * (1.6 + 0.4 * math.sin(n * 2.3))
                  - f[i] * 0.6 for i in range(3))
        self.brass.append((self.t, port, v, n))

    def _gun_frame(self, chest, reload_p):
        """(origin, basis) of the K9 this frame: shouldered on the aim, or at
        low ready, with the recoil kick and the reload tilt on top."""
        aiming = self.ads > 0.3 or self.firing or self.t - self.last_fire < 0.6
        a = 0.0 if (self.sprint or reload_p is not None) else (1.0 if aiming else 0.0)
        self._gun_aim = getattr(self, "_gun_aim", a)
        self._gun_aim += (a - self._gun_aim) * 0.35
        k = self._gun_aim
        carry = 1.0 - k
        tilt = 0.0
        if reload_p is not None:
            tilt = math.sin(math.pi * clamp(reload_p, 0.0, 1.0))
        yaw = self.yaw + CARRY_YAW * carry + 10.0 * tilt
        pitch = (self.pitch * k + CARRY_PITCH * carry + KICK_UP * self.gun_kick
                 - 16.0 * tilt)
        B = _gun_basis(yaw, pitch, roll=-32.0 * tilt)
        rgt_b = _screen_right(self.yaw)
        pocket = (chest[0] + rgt_b[0] * 0.19, chest[1] + 0.17, chest[2] + rgt_b[2] * 0.19)
        f = B[2]
        back = K9_STOCK - KICK_BACK * self.gun_kick - 0.06 * tilt
        # shouldered: up at the cheek, receiver over the shoulder line;
        # carried: out and down by the right hip
        O = (pocket[0] + f[0] * back + rgt_b[0] * 0.12 * carry,
             pocket[1] + f[1] * back + 0.07 * k - 0.26 * carry - 0.05 * tilt,
             pocket[2] + f[2] * back + rgt_b[2] * 0.12 * carry)
        return O, B

    def _draw_player(self, r, tm):
        key = ("biribel", OUTFIT_GUARD)
        h = _w.hum(key, True, 0, True)
        sp = math.hypot(*self.vel)
        if self.dying:
            k = clamp(self.death_t / 0.6, 0.0, 1.0)
            pose = blend("kneel", "dead_back", k)
            _w.actor(r, key, pose, self.pos, self.body_yaw, int(tm), seed=93,
                     amp=0.0, rifle_on=False, hd=True, bloody=True,
                     expression="angry", shadow=T._shadow_for(self.pos[2]))
            self._gun = None
            return
        if sp > 0.5:
            pose = pose_run(self.stride / (2.4 if self.sprint else 1.9) * 2.0
                            * math.pi, lean=20 if self.sprint else 10)
        else:
            pose = dict(POSES["stand"])
        # the torso and head of the aim, kicked by the shot
        for key_ in ("spine", "head_p", "twist"):
            pose[key_] = pose.get(key_, 0.0) + _AIM.get(key_, 0.0)
        pose["spine"] = pose.get("spine", 0.0) - 3.0 * self.gun_kick
        pose["head_p"] = pose.get("head_p", 0.0) - self.pitch * 0.6
        _pl, j0, _root = h.pose_world(pose, self.pos, self.body_yaw, rifle_on=False)
        reload_p = (1.0 - self.reloading / RELOAD_S) if self.reloading else None
        O, B = self._gun_frame(j0["chest"], reload_p)
        self._gun = (O, B)
        rt = _gun_pt(O, B, K9_GRIP)
        lt = _gun_pt(O, B, K9_FORE)
        if reload_p is not None:
            # the support hand drops to the mag well and comes back
            k = math.sin(math.pi * clamp((reload_p - 0.15) / 0.7, 0.0, 1.0))
            mw = _gun_pt(O, B, K9_MAGWELL)
            lt = tuple(lt[i] + (mw[i] - lt[i]) * k for i in range(3))
        pose = _w.reach(h, pose, "r", rt, self.pos, self.body_yaw)
        pose = _w.reach(h, pose, "l", lt, self.pos, self.body_yaw)
        _w.actor(r, key, pose, self.pos, self.body_yaw, int(tm), seed=93,
                 amp=0.15, rifle_on=False, hd=True, bloody=True,
                 expression="angry", shadow=T._shadow_for(self.pos[2]))
        _draw_k9(r, O, B)
        _mesh, muzzle = _k9_asset()
        self._muzzle = _gun_pt(O, B, muzzle)
        if self.t - self.last_fire < 0.035:
            _w.add(r, _flash_mesh(O, B, muzzle, self.shots))

    def _draw_guards(self, r, tm):
        for g in self.guards:
            x, y, z = g["pos"]
            kind = g["kind"]
            prof = T._guard_profile(kind)
            if not g["alive"]:
                k = clamp((self.t - g["dead_t"]) / 0.45, 0.0, 1.0)
                pose = blend(POSES.get(g["post_pose"], POSES["stand"]),
                             g.get("dead_pose", "dead_back"), k)
                _w.actor(r, ("guard", kind), pose, (x, y, z), g["yaw"],
                         int(tm), seed=100 + g["slot"], amp=0.0,
                         rifle_on=False, hd=True, shadow=T._shadow_for(z))
                continue
            face = _w.yaw_to((x, 0, z), (self.pos[0], 0, self.pos[2]))
            if g["moving"]:
                route = g["route"]
                tx, _ty, tz = route[min(g["wp"], len(route) - 1)]
                face = _w.yaw_to((x, 0, z), (tx, 0, tz))
                pose = pose_run(self.t * (9.0 if kind == "rusher" else 7.0)
                                + g["slot"], lean=18)
            else:
                pose = dict(POSES.get(g["post_pose"], POSES["cover"]))
                if g["burst_left"] > 0 or self.t - g["last_shot_t"] < 0.4:
                    pose = blend(pose, "aim", 0.75)
            stag = max(0.0, 1.0 - (self.t - g["hit_t"]) / 0.3)
            if stag > 0.0:
                pose = dict(pose, spine=pose.get("spine", 8) - 12.0 * stag)
            g["yaw"] = _w.yaw_mix(g["yaw"], face, 0.25)
            joints = _w.actor(r, ("guard", kind), pose, (x, y, z), g["yaw"],
                              int(tm), seed=100 + g["slot"], amp=0.4,
                              rifle_on=True, hd=True, shadow=T._shadow_for(z))
            ch = joints.get("chest", (x, y + 1.3, z))
            lamp = (ch[0], ch[1] + 0.20, ch[2])
            if math.sin(self.t * 7.0 + g["slot"]) > -0.3:
                _w.add(r, box(0.09, 0.09, 0.09, (255, 40, 30), center=lamp,
                              emissive=True))
            r.add_sprite(lamp, _fx.glow(prof.get("lamp", (220, 50, 40)), 0.4,
                                        tm, seed=470 + g["slot"]),
                         layer=_fx.FX_LAYER)
            m = joints.get("muzzle")
            if m is not None:
                if g["torch"]:
                    r.add_sprite(m, _fx.glow((226, 236, 255), 0.62, tm,
                                             seed=450 + g["slot"]),
                                 layer=_fx.FX_LAYER)
                if self.t - g["last_shot_t"] < 0.05:
                    r.add_sprite(m, _fx.glow((255, 200, 120), 0.9, tm,
                                             seed=g["slot"], intensity=1.0),
                                 layer=_fx.FX_LAYER)

    def _draw_fx(self, r, tm):
        now = self.t
        for t0, a, b, col in self.tracers:
            # a short streak that travels down the line, not a laser
            k = (now - t0) / 0.06
            head, tail = min(1.0, k), max(0.0, k - 0.35)
            if tail < 1.0:
                pa = tuple(a[i] + (b[i] - a[i]) * tail for i in range(3))
                pb = tuple(a[i] + (b[i] - a[i]) * head for i in range(3))
                r.add_line3d(pa, pb, col, 2, layer=3)
        for t0, p in self.sparks:
            r.add_sprite(p, _fx.sparks(7, (now - t0) * 1000.0, n=10,
                                       speed_m=2.0, dur_ms=420),
                         layer=_fx.FX_LAYER)
        for t0, p, kind in self.impacts:
            col = (150, 24, 20) if kind == "blood" else (150, 150, 156)
            r.add_sprite(p, _fx.dust_motes(int((now - t0) * 1000.0), seed=int(t0 * 97),
                                           count=12, spread_m=(0.45, 0.4), col=col),
                         layer=_fx.FX_LAYER)
        if self.brass and hasattr(r, "add_packed"):
            rows = T._brass_rows(r, (0.012, 0.012, 0.030))
            if rows is not None:
                for t0, p0, v, _sd in self.brass:
                    q = self._brass_at(p0, v, now - t0)
                    out = rows.copy()
                    out[:, 0] += q[0]
                    out[:, 1] += q[1]
                    out[:, 2] += q[2]
                    r.add_packed(out)
        if now - self.last_fire < 0.05 and self._muzzle:
            r.add_sprite(self._muzzle, _fx.glow((255, 206, 130), 1.1, tm,
                                                intensity=1.0),
                         layer=_fx.FX_LAYER)

    def _brass_at(self, p0, v, a):
        """A casing's flight: one arc, one small bounce, then it lies there."""
        g = ground_y(p0[0], p0[2]) + 0.01
        disc = v[1] * v[1] + 19.6 * max(0.0, p0[1] - g)
        a1 = (v[1] + math.sqrt(disc)) / 9.8
        if a < a1:
            return (p0[0] + v[0] * a, p0[1] + v[1] * a - 4.9 * a * a, p0[2] + v[2] * a)
        bt = a - a1
        vy = (9.8 * a1 - v[1]) * 0.25
        hop = max(0.0, vy * bt - 4.9 * bt * bt)
        roll = min(bt, 0.3) * 0.3
        return (p0[0] + v[0] * (a1 + roll), g + hop, p0[2] + v[2] * (a1 + roll))

    # ── guidance and HUD ───────────────────────────────────────────────
    def _objective_point(self):
        if self.route_stage == 0:
            return (SIDING_END[0], 1.4, SIDING_END[1])
        return (TERMINAL[0], 1.6, TERMINAL[1])

    def _project(self, r, p):
        """World point -> (x, y, in_front) in screen pixels."""
        try:
            x, y, z = r.to_cam(p)
        except Exception:
            return (WIDTH / 2.0, 0.0, False)
        k = WIDTH / float(r.w)
        if z <= 0.05:
            return (WIDTH / 2.0 + x * 1000.0, HEIGHT / 2.0 - y * 1000.0, False)
        return ((r.w / 2 + x / z * r.focal) * k, (r.h / 2 - y / z * r.focal) * k, True)

    def _minimap_data(self):
        rects = []
        for x0, y0, z0, x1, y1, z1 in BLOCKERS:
            if x1 - x0 > 50 or z1 - z0 > 25:
                continue                # the walls are the frame
            rects.append((x0, z0, x1, z1, (86, 92, 104)))
        rects.insert(0, (-21.0, 2.7, 21.0, 7.7, (40, 46, 56)))     # platform
        lines = [((-28, z), (29, z), (58, 62, 72))
                 for z in (0.0, T.CARRIAGE_TRACK_Z, T.FREIGHT_Z)]
        lines.append(((T.TRUCK_X, -19), (T.TRUCK_X, 8.6), (52, 56, 66)))
        seen = [(g["pos"][0], g["pos"][2]) for g in self.guards
                if g["alive"] and (self.t - g.get("last_seen", -9) < 0.6
                                   or self.t - g["last_shot_t"] < 2.0)]
        f = T._forward(self.yaw, 0.0)
        return rects, lines, seen, (f[0], f[2])

    def _draw_hud(self, surface):
        if self.hurt > 0.02:
            surface.fill((int(60 * clamp(self.hurt, 0.0, 1.0)), 0, 0),
                         special_flags=pygame.BLEND_RGB_ADD)
        cx, cy = WIDTH // 2, HEIGHT // 2
        if self.dying:
            k = clamp(self.death_t / 2.2, 0.0, 1.0)
            veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            veil.fill((0, 0, 0, int(255 * k)))
            surface.blit(veil, (0, 0))
            img = font_terminal.render("BIRIBEL DOWN  -  AGAIN, FROM THE BODY",
                                       True, (220, 200, 190))
            surface.blit(img, img.get_rect(center=(cx, cy)))
            return
        # objective, with the distance to the next point on the route
        target = self._objective_point()
        dist = math.hypot(target[0] - self.pos[0], target[2] - self.pos[2])
        if self.near_terminal:
            head, sub = "[E] Use the Guard terminal", "Who was on that tower?"
        elif self._all_clear():
            head, sub = "Get to the Guard terminal", "The signal box is clear."
        elif self.route_stage == 0:
            head, sub = "Get round the freight siding", "The signal box is behind it."
        else:
            head, sub = "Clear the signal box", "Who fired? The Guard terminal knows."
        H.objective(surface, head, sub, dist=dist)
        screen = getattr(self, "_marker_screen", None)
        if screen is not None and not self.near_terminal:
            H.marker(surface, screen, dist,
                     "SIGNAL BOX" if self.route_stage else None)
        rects, lines, seen, fwd = self._minimap_data()
        H.minimap(surface, BOUNDS, rects, lines, (self.pos[0], self.pos[2]), fwd,
                  objective=(target[0], target[2]), enemies=seen)
        # crosshair, hits, damage
        gap = int(8 - 3 * self.ads + 3 * self.recoil)
        H.crosshair(surface, gap,
                    reload_frac=(1.0 - self.reloading / RELOAD_S) if self.reloading else 0.0,
                    hit_age=self.t - self.hit_mark, tight=self.ads > 0.5)
        H.damage_arcs(surface, self.dmg_marks, self.t, life=0.9)
        # vitals, the Guard, the weapon
        p = STATE.player
        top = (getattr(p, "max_hp", 115) or 115) if p else 115
        slots = (["alive" if g["alive"] else "down" for g in self.guards]
                 + ["due"] * len(self.pending))
        H.vitals(surface, p.hp if p else 0, top, wounded=self._wounded(),
                 alive=self._living(), slots=slots)
        H.ammo(surface, "K9", self.mag, MAG, "%d" % self.reserve,
               reloading=(1.0 - self.reloading / RELOAD_S) if self.reloading else 0.0)


_scene = YardScene()


def begin():
    return _scene.begin()


def active():
    return _scene.active()


def update(keys=None):
    return _scene.update(keys)


def draw(surface):
    return _scene.draw(surface)


def handle_event(event):
    return _scene.handle_event(event)


def set_paused(paused):
    return _scene.set_paused(paused)


def force_finish(result="win"):
    return _scene.finish(result)


def scene():
    return _scene
