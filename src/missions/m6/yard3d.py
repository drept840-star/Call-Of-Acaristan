"""Mission 6 - "Who is Ucilev?": the third-person fight after Volkov's death.

The train is gone.  Biribel stands up from the body with one question -
who Ucilev is - and the only place that can name him is the Guard terminal
in the signal box behind the freight siding.  Three waves stand between him
and it: the two torch Guards already on the strip, the truck squad, and the
men holding the box.  At the terminal the M6 ending film takes over; its
first shot is that terminal reading Ucilev's file.

Over-the-shoulder camera, WASD + relative mouse look, RMB tightens the
shoulder aim, LMB fires the K9, R reloads, Shift sprints, E uses the
terminal.  A death restarts this fight only.

The set is the train scene's: the post-departure live set it already packed
(platform, station, the yard and its lights) is replayed verbatim, the truck
stays parked, and the carriage is long gone.
"""
from engine3d.hold import hold_cached as _hold_cached
import math
import sys

import pygame

from core.config import (
    HEIGHT, WIDTH, audio, draw_vignette, font_prompt, font_terminal,
)
from core.outfits import OUTFIT_GUARD
from core.state import STATE
from engine3d import NEUTRAL, POSES, Light, blend, box, clamp, pose_run, tex

from . import hud3d as H
from . import palette3d as P
from . import perf as _perf
from . import train3d as T
from . import yard_brain as B
from . import yard_dress as D
from . import yard_hud as U

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
BOOM_ADS = (1.65, 0.56, 0.10)      # tight over the shoulder, the K9 into frame
# Stance: the torso turned off the aim, support shoulder forward, so the
# left hand reaches the handguard and the K9 clears his body for the lens.
BLADE = 30.0
# Strafe locomotion: the torso stays on the aim and only the hips turn into
# the move (at most this far); a backpedal cycles the legs backward.
HIP_TURN = 55.0
# The third-person gun is seen from behind, its shadow side to the lens: more
# of the viewmodel's cool lift, or the black anodising vanishes on the night.
K9_TINT = ((150, 162, 182), 0.22)
FOV, FOV_ADS = 62.0, 48.0
SENS = 0.12                        # degrees per mouse count
PITCH_LIM = (-38.0, 32.0)
MAG, RESERVE = 30, 120
FIRE_GAP = 0.08                    # K9 cyclic, s
RELOAD_S = 1.6
HP_REGEN_DELAY, HP_REGEN = 5.0, 7.0
HIT_BODY, HIT_HEAD = 22, 64
# Dead Guards carry K9-compatible mags: walk over the body to take them.
LOOT_R = 1.5                       # pickup radius, m
LOOT_MAGS = {"heavy": 2, "officer": 2}   # everyone else carries one
RESERVE_CAP = 4 * MAG              # four spare mags on him, the panel's MAGS: 4
# Melee: a punch for whoever is in arm's reach (F or V; LMB when dry).
MELEE_R, MELEE_CONE = 1.9, 0.55    # reach (m), min cos to the aim
MELEE_DMG, MELEE_GAP, MELEE_S = 45, 0.65, 0.48   # damage, cooldown, swing time
# A punch drops a Guard without killing him: he falls, lies stunned, gets
# back up.  A second punch while he's down (or one from behind) finishes
# him.  The heavies take punches on their feet, MELEE_DMG at a time.
KNOCK_DMG = 12
KNOCK_FALL, KNOCK_DOWN, KNOCK_RISE = 0.35, 3.0, 0.9   # s: falling, on the snow, up
STURDY = ("heavy",)
# The punch's beats as fractions of MELEE_S: the fist is cocked, it lands,
# the hold ends.  The hit resolves on the landing frame, not the key press.
PUNCH_COCK, PUNCH_LAND, PUNCH_HOLD = 0.26, 0.38, 0.52
MELEE_HIT_S = PUNCH_LAND * MELEE_S
PUNCH_TWIST = (14.0, 46.0)         # torso wound back / thrown through, deg
PUNCH_LUNGE = 0.24                 # the body's drive into the punch, m
PUNCH_CLOSE = (1.05, 3.5)          # he steps in to this range, at this speed
HITSTOP_S, HITSTOP_RATE = 0.07, 0.15   # the world crawls a beat on contact
SHOVE_M, SHOVE_S = 0.45, 0.18      # a punched Guard reels back this far
# The yard's difficulty (the train's guard profiles stay as they are): they
# hit harder and tougher, aim better and come back at him sooner.
GUARD_HP, GUARD_DMG = 1.15, 1.55
GUARD_AIM, GUARD_REST = 0.05, 0.85     # extra hit chance, burst-rest scale

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
# The masts' sodium pools on the snow (GL; train3d.SET_POOLS has the set's)
LAMP_POOLS = [{"pos": (lx, 6.3, lz), "range": 8.5, "color": P.SODIUM,
               "hot": (255, 210, 126), "intensity": 1.3} for lx, lz in LAMPS]


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
    b.extend(D.blockers())                          # yard clutter
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


CAM_R = 0.24                       # the lens keeps this far off every surface


def _box_gap(p, lo, hi):
    """Distance from p to the box (0 inside)."""
    g = 0.0
    for i in range(3):
        g = max(g, lo[i] - p[i], p[i] - hi[i])
    return g


def _boom_clear(o, d, want, floor):
    """How far along d from o the lens can sit, up to ``want``, with CAM_R of
    air to every blocker.  A box the origin already hugs shrinks its margin so
    the start is never inside it."""
    dist = want
    for x0, y0, z0, x1, y1, z1 in BLOCKERS:
        lo, hi = (x0, y0, z0), (x1, y1, z1)
        gap = _box_gap(o, lo, hi)
        if gap <= 0.0:
            continue
        m = min(CAM_R, gap * 0.5)
        hit = T._ray_aabb(o, d, (x0 - m, y0 - m, z0 - m), (x1 + m, y1 + m, z1 + m))
        if hit is not None and hit < dist:
            dist = max(floor, hit)
    return dist


def _push_out(p):
    """Last resort: nudge the lens out of any blocker (plus margin) along the
    shortest axis, so a corner graze can never put it inside geometry."""
    x, y, z = p
    for _ in range(3):
        moved = False
        for x0, y0, z0, x1, y1, z1 in BLOCKERS:
            m = CAM_R * 0.5
            if not (x0 - m < x < x1 + m and y0 - m < y < y1 + m and z0 - m < z < z1 + m):
                continue
            opts = ((x - (x0 - m), 0, -1), (x1 + m - x, 0, 1),
                    (z - (z0 - m), 2, -1), (z1 + m - z, 2, 1),
                    (y1 + m - y, 1, 1))
            _, ax, sg = min(opts)
            if ax == 0:
                x = x0 - m if sg < 0 else x1 + m
            elif ax == 2:
                z = z0 - m if sg < 0 else z1 + m
            else:
                y = y1 + m
            moved = True
        if not moved:
            break
    return (x, y, z)



def _screen_right(yaw):
    """The direction that is right on screen (``T._right`` is mirrored)."""
    r = T._right(yaw)
    return (-r[0], 0.0, -r[2])


def _wrap(deg):
    return (deg + 180.0) % 360.0 - 180.0


def ground_y(x, z):
    """Walkable height: platform (and the strip under the station wall), the
    steps off its east end, ballast and yard."""
    if -21.0 <= x <= 21.0 and 2.7 <= z <= (9.0 if -2.5 <= x <= 16.5 else 7.7):
        return T._SLOT_GROUND
    if 21.0 < x <= 22.5 and 5.2 <= z <= 6.6:
        return T._SLOT_GROUND * (1.0 - (x - 21.0) / 1.5)
    return 0.04


_SET_CACHE = {}
_WALL = (54, 58, 68)
_POST = (38, 41, 49)
_SNOW = (176, 186, 202)


def _wall_run(add, x0, z0, x1, z1, h=2.6):
    """An axis-aligned concrete run with poured panels, control joints and a
    snow cap: the inside of the yard gets construction detail, not one slab."""
    along_x = abs(x1 - x0) >= abs(z1 - z0)
    length = abs(x1 - x0) if along_x else abs(z1 - z0)
    if length < 0.05:
        return
    cx, cz = (x0 + x1) * 0.5, (z0 + z1) * 0.5
    w, d = (length, 0.4) if along_x else (0.4, length)
    seg = max(1, int(length / 4.0))
    snow = tex("snow", like=_SNOW)
    add(box(w, h, d, tex("concrete", like=_WALL), center=(cx, h * 0.5, cz), seg=seg))
    add(box(w + 0.08, 0.08, d + 0.08, snow, center=(cx, h + 0.04, cz), seg=seg))
    add(box(w, 0.35, d + 0.5, snow, center=(cx, 0.12, cz), seg=seg))
    # dark base plinth and a horizontal shutter line
    add(box(w + 0.06, 0.38, d + 0.06, _POST, center=(cx, 0.19, cz), seg=seg))
    add(box(w + 0.03, 0.035, d + 0.03, (36, 39, 46),
            center=(cx, h * 0.54, cz), seg=seg))
    post = tex("concrete", like=_POST)
    for i in range(seg + 1):
        k = i / float(seg)
        px = x0 + (x1 - x0) * k
        pz = z0 + (z1 - z0) * k
        add(box(0.5, h + 0.25, 0.5, post, center=(px, (h + 0.25) * 0.5, pz)))
    # control joints every 2 m, plus two weather streaks on the yard face
    for i in range(1, max(1, int(length / 2.0))):
        t = i / float(max(1, int(length / 2.0)))
        px = x0 + (x1 - x0) * t
        pz = z0 + (z1 - z0) * t
        if along_x:
            add(box(0.045, h - 0.42, d + 0.02, (32, 35, 42),
                    center=(px, h * 0.5, cz)))
        else:
            add(box(w + 0.02, h - 0.42, 0.045, (32, 35, 42),
                    center=(cx, h * 0.5, pz)))
    for i, t in enumerate((0.27, 0.62, 0.83)):
        px = x0 + (x1 - x0) * t
        pz = z0 + (z1 - z0) * t
        stain = (28, 30, 35) if i % 2 else (43, 39, 34)
        if along_x:
            add(box(0.16, h * 0.58, d + 0.025, stain,
                    center=(px, h * 0.30, cz)))
        else:
            add(box(w + 0.025, h * 0.58, 0.16, stain,
                    center=(cx, h * 0.30, pz)))


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
    add(quad_xz(-160, -160, 160, 160, -0.02, tex("snow", like=(56, 64, 78)), seg=12))
    g0, g1 = ROAD_GATE
    # the gate road: trodden, gravelly snow inside the wall
    add(quad_xz(g0 + 0.2, WALL_S, g1 - 0.2, WALL_N, 0.045,
                tex("snow_trod", like=(64, 72, 86)), seg=4))
    for i, (px, pz, pw, pd) in enumerate(((-18.0, -11.5, 5.5, 2.6),
                                          (-6.0, -8.5, 4.2, 2.1),
                                          (14.0, -11.0, 5.8, 2.4),
                                          (22.0, 4.2, 3.0, 4.6))):
        add(quad_xz(px - pw * 0.5, pz - pd * 0.5, px + pw * 0.5,
                    pz + pd * 0.5, 0.04,
                    tex("snow_trod", like=(70, 78, 94)), seg=2))
    for i, (px, pz, pw, pd) in enumerate(((-23.0, -5.5, 4.8, 1.8),
                                          (7.0, -14.0, 5.2, 2.0),
                                          (-1.5, 0.5, 3.8, 1.5))):
        add(quad_xz(px, pz, px + pw, pz + pd, 0.043, (52, 64, 82)))
    for lane in (-0.55, 0.55):
        add(quad_xz(g0 + 1.9 + lane, WALL_S + 1.0, g0 + 2.35 + lane,
                    WALL_N - 1.0, 0.053, (84, 92, 106)))
    # south: concrete, the road gate
    _wall_run(add, WALL_W, WALL_S, g0, WALL_S)
    _gate(add, g0, g1, WALL_S)
    _wall_run(add, g1, WALL_S, WALL_E, WALL_S)
    # west: concrete, two personnel doors the Guard comes through
    _wall_run(add, WALL_W, WALL_S, WALL_W, WALL_N)
    for dz in WEST_DOORS:
        add(box(0.08, 2.1, 1.1, (26, 28, 32), center=(WALL_W + 0.24, 1.05, dz)))
        add(box(0.10, 0.12, 1.3, _POST, center=(WALL_W + 0.25, 2.16, dz)))
        add(box(0.06, 0.12, 0.3, P.SODIUM_PALE, center=(WALL_W + 0.3, 2.45, dz),
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
        add(box(0.5, 0.16, 0.36, P.SODIUM_PALE, center=(lx, 6.3, lz),
                emissive=True))
    D.dress(add, WALL_W, WALL_E, WALL_S, T.TRUCK_X)
    _SET_CACHE["perimeter"] = m
    return m


def _perimeter_sprites(r, tm):
    for i, (lx, lz) in enumerate(LAMPS):
        r.add_sprite((lx, 6.2, lz), _fx.sodium_lamp(tm, seed=480 + i,
                                                     radius_m=2.1, intensity=0.6),
                     layer=_fx.FX_LAYER)
        if r.backend != "gl":            # GL: LAMP_POOLS light the snow
            r.add_sprite((lx, 0.05, lz), _fx.window_glow(P.SODIUM, 3.6, 3.0, 0.16),
                         layer=_fx.FX_LAYER)
    for dz in WEST_DOORS:
        r.add_sprite((WALL_W + 0.35, 2.45, dz),
                     _fx.glow(P.SODIUM, 0.6, tm, intensity=0.7),
                     layer=_fx.FX_LAYER)
    for i, p in enumerate(getattr(D, "BEACONS", ())):       # aviation lamps
        r.add_sprite(p, _fx.beacon((228, 56, 42), 0.30, tm, phase=0.23 * i),
                     layer=_fx.FX_LAYER)
    for i, p in enumerate(getattr(D, "SIGN_LAMPS", ())):
        r.add_sprite(p, _fx.glow(P.SODIUM_PALE, 0.7, tm, seed=640 + i, intensity=0.6),
                     layer=_fx.FX_LAYER)
    for i, (p, _face) in enumerate(getattr(D, "SEARCHLIGHTS", ())):
        r.add_sprite(p, _fx.glow(P.LAMP_WHITE, 1.4, tm, seed=660 + i, core=P.LAMP_WHITE,
                                 intensity=0.8),
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
        ("rusher", (29.0, 0.04, 1.0), ((24.0, 0.04, -2.0), (18.5, 0.04, -5.2)),
         "crouch", False, 4.5),
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
        ("rusher", _TRUCK_DROP, ((22.8, 0.04, 3.0), (17.0, 0.04, 0.6),
                                 (12.5, 0.04, -2.0)), "crouch", False, 11.5),
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
        ("heavy", (-27.9, 0.04, -12.4), ((5.0, 0.04, -12.4), (9.5, 0.04, -12.3)),
         "stand", False, 4.0),
        ("rusher", (-27.9, 0.04, -12.4), ((10.0, 0.04, -12.3), (20.8, 0.04, -12.3)),
         "crouch", False, 3.0),
    ),
)
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
        "torch": torch, "hp": int(prof["hp"] * GUARD_HP), "alive": True, "dead_t": -9.0,
        "yaw": 0.0, "moving": False, "posted": False,
        "next_burst": now + 1.2 + 0.7 * i, "burst_left": 0, "burst_next": 0.0,
        "last_shot_t": -9.0, "hit_t": -9.0, "hit_dir": None,
        "react": now + delay + (1.0 if wave == 0 else 0.4),
        "spawn_at": now + delay,
        "last_seen": now + delay,
    }


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
K9_GUARD = (-0.006, 0.020, 0.070)     # left hand: rear of the handguard
K9_MAGWELL = (0.0, -0.120, 0.060)     # left hand mid-reload
ARM_REACH = 0.58                      # shoulder to hand, nearly straight
K9_PORT = (0.045, 0.040, 0.030)       # ejection port
K9_SIGHT_Y = 0.181                    # optic line above the trigger
K9_BUTT_Z = -0.437                    # butt plate behind the trigger
# Shouldered, in gun axes from his head and right shoulder: the stock beside
# the right cheek (the head box is 0.10 to a side), the optic line just under
# the eye, the butt plate in the shoulder pocket.
ADS_CHEEK, ADS_DROP, ADS_POCKET = 0.13, 0.03, 0.05
# Low ready: muzzle down and a touch out, the butt tucked at the front of the
# right shoulder, where the lens behind that shoulder can still see the gun.
CARRY_PITCH, CARRY_YAW = -20.0, -8.0
CARRY_OUT, CARRY_DROP, CARRY_POCKET = -0.04, 0.08, 0.08
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


def _unit(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-9 else (0.0, 0.0, 0.0)


def _gait_cycle(v):
    """Metres per gait cycle (two steps) at speed v: longer strides as he
    speeds up, so the cadence runs about 2.4 steps/s walking to 3.8 sprinting."""
    return clamp(0.75 + 0.38 * v, 1.0, 2.8)


def _gait(phase, v, ux, uz, scale):
    """Planted-foot legs at speed ``v`` (m/s) along the body-local unit
    (ux, uz); ``phase`` counts cycles.  Each stance foot moves back under the
    hips at exactly the body's speed, so it holds still on the ground, and
    leg IK bends the knee to reach it.  Walk, jog and sprint differ only in
    stance share, knee bend, foot lift and lean.  -> pose dict."""
    k = clamp((v - 1.5) / 1.5, 0.0, 1.0)          # walk -> jog
    s2 = clamp((v - 3.0) / 2.2, 0.0, 1.0)         # jog -> sprint
    amp = clamp(v / 1.2, 0.0, 1.0)                # settles to a stand
    beta = 0.60 - 0.18 * k - 0.07 * s2            # stance share of a cycle
    drop = 0.05 + 0.05 * k + 0.03 * s2            # knee bend under load (rig)
    lift = (0.07 + 0.08 * k + 0.10 * s2) * amp
    half = beta * _gait_cycle(v) / 2.0 / scale * amp
    stand_y = -(0.858 - drop)
    pose = dict(spine=3.0 + 4.0 * k + 7.0 * s2, head_p=-2.0 * k)
    for side, off, lat in (("l", 0.0, -1), ("r", 0.5, 1)):
        ph = (phase + off) % 1.0
        if ph < beta:
            u = half * (1.0 - 2.0 * ph / beta)
            fy = stand_y - 0.02 * math.sin(math.pi * ph / beta) * amp
        else:
            q = (ph - beta) / (1.0 - beta)
            u = -half + 2.0 * half * q * q * (3.0 - 2.0 * q)
            fy = stand_y + lift * math.sin(math.pi * q)
        hip, knee = _w.leg_ik(uz * u, fy)
        pose[side + "hip_p"], pose[side + "kn"] = hip, knee
        out = clamp(ux * u * lat / 0.86, -0.12, 0.20)
        pose[side + "hip_r"] = math.degrees(math.asin(out))
        # the planted sole lies flat; in the air the toes hang a little
        pose[side + "ank"] = (knee - hip) * (1.0 if ph < beta else 0.6)
    # a short float between steps once he runs
    f = phase % 0.5
    if beta < 0.5 and f > beta:
        pose["lift"] = (0.025 * k + 0.035 * s2) * math.sin(math.pi * (f - beta) / (0.5 - beta))
    return pose


def _smooth(x):
    x = clamp(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _punch_beats(u):
    """The punch at ``u`` (0..1 of MELEE_S) -> (leg, k, coil, drive, gun).
    ``leg`` is the fist's stretch of path (0 grip -> cocked, 1 cocked ->
    landed, 2 held out, 3 back to the grip), ``k`` how far along it;
    ``coil`` winds the torso back, ``drive`` throws it through and ``gun`` is
    how far the K9 has gone over to the left hand."""
    gun = _smooth(u / 0.16) if u < 0.6 else 1.0 - _smooth((u - 0.6) / 0.4)
    if u < PUNCH_COCK:
        a = _smooth(u / PUNCH_COCK)
        return 0, a, a, 0.0, gun
    if u < PUNCH_LAND:
        k = 1.0 - (1.0 - (u - PUNCH_COCK) / (PUNCH_LAND - PUNCH_COCK)) ** 3
        return 1, k, 1.0 - k, k, gun            # snaps out, slows into the face
    if u < PUNCH_HOLD:
        return 2, 1.0, 0.0, 1.0, gun
    q = _smooth((u - PUNCH_HOLD) / (1.0 - PUNCH_HOLD))
    return 3, q, 0.0, 1.0 - q, gun


# Elbow poles in torso axes (+x outward from that side, +y up, +z forward):
# the trigger elbow out and down, the support elbow down under the handguard.
POLE_R, POLE_L = (0.8, -1.0, -0.1), (0.4, -1.0, 0.0)
POLE_COCK, POLE_PUNCH = (0.35, -1.0, -0.3), (1.0, -0.45, 0.0)   # elbow tucked / out
POLE_HANG = (0.1, -0.3, -1.0)          # the left arm with the K9 hung off it
UARM, FARM = 0.30, 0.31                # rig shoulder->elbow, elbow->hand


def _arm_ik(hum, pose, side, target, pos, yaw, pole):
    """Two-bone arm IK onto a WORLD point with the elbow swung toward
    ``pole``.  The rig's own solve keeps the elbow in one fixed plane, which
    folds an arm reaching across the chest straight through the torso; here
    the elbow goes round the body and the hand still lands on the target."""
    p = dict(pose)
    places, _j, root = hum.pose_world(p, pos, yaw, rifle_on=False)
    S = next(m for slot, _k, m, _o, _g, _f in places if slot == 1)
    sh = next(o for slot, _k, _m, o, _g, _f in places
              if slot == (4 if side == "l" else 10))
    sc2 = S[0] * S[0] + S[3] * S[3] + S[6] * S[6]
    d = [target[i] - root[i] - sh[i] for i in range(3)]
    t = [(S[i] * d[0] + S[3 + i] * d[1] + S[6 + i] * d[2]) / sc2 for i in range(3)]
    th = _unit(t)
    dist = clamp(math.sqrt(sum(x * x for x in t)), 0.05, UARM + FARM - 0.002)
    t = [x * dist for x in th]
    # the elbow circle about the shoulder->hand line, swung toward the pole
    along = (UARM * UARM - FARM * FARM + dist * dist) / (2.0 * dist)
    rho = math.sqrt(max(0.0, UARM * UARM - along * along))
    sx = -1.0 if side == "l" else 1.0
    n = (pole[0] * sx, pole[1], pole[2])
    k = sum(n[i] * th[i] for i in range(3))
    n = _unit([n[i] - k * th[i] for i in range(3)])
    elbow = [th[i] * along + n[i] * rho for i in range(3)]
    u = _unit(elbow)                                  # upper arm, down its length
    v = _unit([t[i] - elbow[i] for i in range(3)])    # forearm
    cu = sum(v[i] * u[i] for i in range(3))
    w = [v[i] - cu * u[i] for i in range(3)]
    sw = math.sqrt(sum(x * x for x in w))
    w = _unit(w) if sw > 1e-5 else _unit([n[i] - sum(n[j] * u[j] for j in range(3)) * u[i]
                                          for i in range(3)])
    el = math.atan2(sw, cu)
    # U = rot_z(sh_r * sx) . rot_x(-sh_p) . rot_y(sh_y) with U(-y) = u, U(+z) = w
    a = math.atan2(u[0], -u[1])
    b = math.asin(clamp(-u[2], -1.0, 1.0))
    ca, sa = math.cos(a), math.sin(a)
    wx, wy = ca * w[0] + sa * w[1], -sa * w[0] + ca * w[1]
    g = math.atan2(wx, -math.sin(b) * wy + math.cos(b) * w[2])
    p[side + "sh_r"] = math.degrees(a) * sx
    p[side + "sh_p"] = -math.degrees(b)
    p[side + "sh_y"] = math.degrees(g)
    p[side + "el"] = math.degrees(el)
    return p


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


def _guard_flash_mesh(m, d, seed):
    """An irregular muzzle burst along the shot line d: a hot core spike and
    six petals of uneven length.  Guards fire at the camera, so it has to read
    end-on, as a star and not a disc."""
    from engine3d import Mesh
    n = math.sqrt(sum(c * c for c in d)) or 1.0
    f = tuple(c / n for c in d)
    up = (0.0, 1.0, 0.0) if abs(f[1]) < 0.95 else (1.0, 0.0, 0.0)
    rx = (up[1] * f[2] - up[2] * f[1], up[2] * f[0] - up[0] * f[2],
          up[0] * f[1] - up[1] * f[0])
    ln = math.sqrt(sum(c * c for c in rx)) or 1.0
    rx = tuple(c / ln for c in rx)
    ry = (f[1] * rx[2] - f[2] * rx[1], f[2] * rx[0] - f[0] * rx[2],
          f[0] * rx[1] - f[1] * rx[0])
    parts = [box(0.05, 0.05, 0.34, (255, 235, 190), center=(0.0, 0.0, 0.17), emissive=True)]
    for i in range(6):
        ang = (seed * 29 % 60 + i * 60 + (i % 2) * 11) * math.pi / 180.0
        pl = (0.30, 0.17, 0.38, 0.14, 0.26, 0.20)[(i + seed) % 6]
        p = box(pl, 0.028, 0.02, (255, 176, 80), center=(pl * 0.5, 0.0, 0.03), emissive=True)
        ca, sa = math.cos(ang), math.sin(ang)
        p.verts = [(v[0] * ca - v[1] * sa, v[0] * sa + v[1] * ca, v[2]) for v in p.verts]
        parts.append(p)
    out = Mesh()
    for part in parts:
        part.verts = [tuple(m[k] + rx[k] * v[0] + ry[k] * v[1] + f[k] * v[2]
                            for k in range(3)) for v in part.verts]
        out.add(part)
    return out


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
        self.gait = 0.0              # gait cycles walked (see _gait)
        self.stride_dir = 1.0        # -1 on a backpedal
        self.twist = 0.0             # torso back onto the aim from the hips
        self.gun_up = 0.0            # 0 low ready .. 1 shouldered
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
        self.brain = B.Brain(self, sys.modules[__name__])
        self.wave = -1
        self._start_wave(0)
        self.dying = False
        self.death_t = 0.0
        self.done = False
        self.result = None
        self.near_terminal = False
        self.route_stage = 0
        self.melee_t = -9.0            # start of the last punch
        self.melee_g = None            # who it was thrown at
        self.melee_due = False         # the hit still to land
        self.hitstop = 0.0
        self.toast = None              # (t, text) pickup / melee note
        self._muzzle = None
        p = STATE.player
        if p is not None:
            p.hp = getattr(p, "max_hp", 115) or 115

    def begin(self):
        self.restart()
        self._active = True
        self.paused = False
        _perf.watchdog_reset()
        STATE.m6_yard_active = True
        STATE.m6_yard_result = None
        if self.audio is None:
            try:
                from .m6_audio import M6TrainAudio
                self.audio = M6TrainAudio(audio)
                self.audio.warm()      # synth the one-shots at load, not mid-wave
            except Exception:
                self.audio = None
        T._prewarm_ambience()
        self._grab(True)
        # pay the set build now, not on the first visible frame
        try:
            scratch = pygame.Surface((WIDTH, HEIGHT))
            self.draw(scratch)
            # The yard shares the train's renderer, so it inherits whatever
            # scale was measured there; entering straight from a checkpoint
            # measures here, still before the first visible frame (every step
            # re-bakes the set, and the fight cannot afford that mid-wave).
            _perf.plan("m6_yard", lambda: self.draw(scratch))
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
            elif event.key in (pygame.K_f, pygame.K_v) and not self.dying:
                self._melee()
            elif event.key == pygame.K_e and self.near_terminal:
                self.finish("win")

    # ── update ─────────────────────────────────────────────────────────
    def update(self, keys=None):
        if not self._active or self.paused:
            return
        dt = clamp(float(getattr(STATE, "dt", 1.0 / 60.0)), 0.0, 0.05)
        if self.hitstop > 0.0:
            self.hitstop -= dt
            dt *= HITSTOP_RATE
        self.t += dt
        if self.dying:
            self.death_t += dt
            if self.death_t >= 2.6:
                self.restart()          # this fight only, from the body
            return
        self.ads += ((1.0 if self.aiming and not self.reloading else 0.0)
                     - self.ads) * min(1.0, dt * 12.0)
        up = (self.ads > 0.3 or self.firing or self.t - self.last_fire < 0.6)
        punching = self.t - self.melee_t < MELEE_S * 0.8
        up = 0.0 if (self.sprint or self.reloading or punching or not up) else 1.0
        self.gun_up += (up - self.gun_up) * min(1.0, dt * 16.0)
        self._move(keys, dt)
        if self.reloading:
            self.reloading = max(0.0, self.reloading - dt)
            if not self.reloading:
                n = min(MAG - self.mag, self.reserve)
                self.mag += n
                self.reserve -= n
        if self.firing and not self.reloading:
            if self.mag <= 0 and self.reserve <= 0:
                self._melee()          # dry: the fists
            elif not punching:
                self._fire()
        self._melee_tick(dt)
        self._loot()
        self.recoil = max(0.0, self.recoil - dt * 6.0)
        self.gun_kick = max(0.0, self.gun_kick - dt * 13.0)
        self.cam_kick *= math.exp(-dt * 11.0)
        self.shake = max(0.0, self.shake - dt * 4.5)
        self.brass = [b for b in self.brass if self.t - b[0] < 4.0][-30:]
        self.impacts = [x for x in self.impacts if self.t - x[0] < 0.6]
        self._update_guards(dt)
        self._reel(dt)
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
        self.gait += sp * dt / _gait_cycle(sp)
        # Facing: the torso always on the aim (bladed when the gun is up), so
        # the K9 never swings off his chest; the hips turn into a strafe and
        # stay square on a backpedal, where the legs cycle backward.
        aim = self._aim_body_yaw()
        torso = aim + BLADE
        hips = torso
        if sp > 0.4:
            rel = _wrap(_w.yaw_to((0, 0, 0), (self.vel[0], 0, self.vel[1])) - aim)
            back = abs(rel) > 100.0
            self.stride_dir = -1.0 if back else 1.0
            if back:
                rel = _wrap(rel - 180.0)
            hips = torso + clamp(_wrap(rel - BLADE), -HIP_TURN, HIP_TURN)
        self.body_yaw = _w.yaw_mix(self.body_yaw, hips, min(1.0, dt * 10.0))
        self.twist = clamp(_wrap(torso - self.body_yaw), -70.0, 70.0)

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
        # two legs, each kept clear of every blocker: the head out to the
        # shoulder, then the boom back from the shoulder
        right = _boom_clear(pivot, (rgt[0], 0.0, rgt[2]), right, 0.0)
        shoulder = (pivot[0] + rgt[0] * right, pivot[1], pivot[2] + rgt[2] * right)
        d = (-f[0], -f[1], -f[2])
        dist = _boom_clear(shoulder, d, back, 0.35)
        ex, ez = shoulder[0] + d[0] * dist, shoulder[2] + d[2] * dist
        eye = (ex, max(ground_y(ex, ez) + 0.3, shoulder[1] + d[1] * dist), ez)
        eye = _push_out(eye)
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
            for zi, (dy, rad) in enumerate(self.brain.spheres(g)):
                hit = T._ray_sphere(o, d, (gx, gy0 + dy, gz), rad)
                if hit is not None and hit < best:
                    best, best_g, head = hit, g, zi == 1
        end = (o[0] + d[0] * best, o[1] + d[1] * best, o[2] + d[2] * best)
        src = self._muzzle or o
        self.tracers.append((self.t, src, end, (255, 214, 150)))
        self.brain.suppress(o, end)
        if best_g is None:
            self.sparks.append((self.t, end))
            self.impacts.append((self.t, end, "dust"))
            if self.audio:
                self.audio.impact(on_enemy=False)
            return
        g = best_g
        self.impacts.append((self.t, end, "blood"))
        if self.audio:
            (self.audio.headshot if head else
             (lambda: self.audio.impact(on_enemy=True)))()
        self._hurt_guard(g, HIT_HEAD if head else HIT_BODY, (d[0], d[2]))

    def _hurt_guard(self, g, dmg, hit_dir):
        g["hp"] -= dmg
        g["hit_t"] = self.t
        g["hit_dir"] = hit_dir
        self.hit_mark = self.t
        if g["hp"] <= 0:
            g["alive"] = False
            g["dead_t"] = self.t
            g["dead_pose"] = "dead_back" if (int(g["slot"]) % 2) else "dead_front"
            g["mags"] = LOOT_MAGS.get(g["kind"], 1)

    def _loot(self):
        """Take the mags off any body he walks over, whole mags up to the
        four spares he can carry; the rest stay on the body for later."""
        px, _py, pz = self.pos
        for g in self.guards:
            room = RESERVE_CAP - self.reserve
            if room <= 0:
                return
            if g["alive"] or not g.get("mags"):
                continue
            if math.hypot(g["pos"][0] - px, g["pos"][2] - pz) > LOOT_R:
                continue
            take = min(g["mags"], -(-room // MAG))
            got = min(take * MAG, room)
            g["mags"] -= take
            self.reserve += got
            self.toast = (self.t, "+%d K9 ROUNDS" % got)
            if self.audio:
                self.audio.reload()
            if self.mag <= 0:
                self._begin_reload()

    def _melee_target(self):
        f = T._forward(self.yaw, 0.0)
        fx, fz = f[0], f[2]
        n = math.hypot(fx, fz) or 1.0
        fx, fz = fx / n, fz / n
        best, best_d = None, MELEE_R
        for g in self.guards:
            if not g["alive"]:
                continue
            dx, dz = g["pos"][0] - self.pos[0], g["pos"][2] - self.pos[2]
            d = math.hypot(dx, dz)
            if d < best_d and d > 1e-6 and (dx * fx + dz * fz) / d >= MELEE_CONE \
                    and abs(g["pos"][1] - self.pos[1]) < 1.0:
                best, best_d = g, d
        return best, (fx, fz)

    def _melee(self):
        """Throw a punch: it lands MELEE_HIT_S later (see _melee_tick)."""
        if self.t - self.melee_t < MELEE_GAP or self.reloading:
            return
        self.melee_t = self.t
        self.firing = False if (self.mag <= 0 and self.reserve <= 0) else self.firing
        self.melee_g = self._melee_target()[0]
        self.melee_due = True

    def _melee_tick(self, dt):
        """He steps in on the wind-up; the fist lands on its frame, on
        whoever is still in reach then."""
        since = self.t - self.melee_t
        g = self.melee_g
        if g is not None and g["alive"] and since < MELEE_HIT_S:
            dx, dz = g["pos"][0] - self.pos[0], g["pos"][2] - self.pos[2]
            d = math.hypot(dx, dz)
            step = min(d - PUNCH_CLOSE[0], PUNCH_CLOSE[1] * dt)
            if step > 0.0:
                x, z = self.pos[0] + dx / d * step, self.pos[2] + dz / d * step
                if not _blocked(x, z, self.pos[1]):
                    self.pos = (x, self.pos[1], z)
        if not self.melee_due or since < MELEE_HIT_S:
            return
        self.melee_due = False
        self.shake = min(1.0, self.shake + 0.3)
        g, (fx, fz) = self._melee_target()
        if g is None:
            return
        # from behind (he faces away from Biribel) or on the snow: a takedown
        gx, gz = B._dir(g["yaw"])
        sturdy = g["kind"] in STURDY
        down = self.t < g.get("down_until", -9.0)
        behind = not sturdy and (gx * fx + gz * fz) > 0.35
        if down or behind:
            dmg = g["hp"]
        else:
            dmg = MELEE_DMG if sturdy else min(KNOCK_DMG, g["hp"] - 1)
        self.cam_kick = min(2.2, self.cam_kick + 1.1)
        self.shake = min(1.0, self.shake + 0.45)
        self.hitstop = HITSTOP_S
        self.impacts.append((self.t, (g["pos"][0], g["pos"][1] + 1.6, g["pos"][2]), "blood"))
        if self.audio:
            self.audio.thud()
            self.audio.impact(on_enemy=True)
        self._hurt_guard(g, dmg, (fx, fz))
        g["punch_t"] = self.t
        g["shove"] = (fx, fz)
        if not g["alive"]:
            self.toast = (self.t, "TAKEDOWN")
        elif not sturdy:
            g["fall_from"] = g.get("pose") or POSES["stand"]
            g["down_t"] = self.t
            g["up_at"] = self.t + KNOCK_FALL + KNOCK_DOWN
            g["down_until"] = g["up_at"] + KNOCK_RISE
            self.toast = (self.t, "KNOCKED DOWN")

    def _reel(self, dt):
        """A punched Guard reels back a step (never into cover)."""
        for g in self.guards:
            sv = g.get("shove")
            if sv is None:
                continue
            if self.t - g["punch_t"] > SHOVE_S:
                g["shove"] = None
                continue
            k = 2.0 * (1.0 - (self.t - g["punch_t"]) / SHOVE_S)   # fast, then easing
            x = g["pos"][0] + sv[0] * SHOVE_M / SHOVE_S * k * dt
            z = g["pos"][2] + sv[1] * SHOVE_M / SHOVE_S * k * dt
            if not _blocked(x, z, g["pos"][1]):
                g["pos"] = (x, g["pos"][1], z)

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
        self.brain.update(dt)          # yard_brain: senses, squad, the tree

    def _guard_shot(self, g, prof, src, chest):
        g["burst_left"] -= 1
        g["last_shot_t"] = self.t
        gap = float(prof.get("gap", 0.1))
        g["burst_next"] = self.t + gap
        if g["burst_left"] <= 0:
            g["next_burst"] = self.t + GUARD_REST * (
                1.5 + 0.9 * ((g["slot"] * 7 + int(self.t)) % 3))
        dist = math.dist(src, chest)
        moving = math.hypot(*self.vel) > 1.0
        p_hit = clamp(0.62 + GUARD_AIM - dist * 0.014 - (0.16 if moving else 0.0)
                      - (0.08 if self.sprint else 0.0), 0.2, 0.9)
        roll = (math.sin(self.t * 91.7 + g["slot"] * 13.1) + 1.0) * 0.5
        hit = roll < p_hit
        wob = 0.0 if hit else 0.9
        dst = (chest[0] + math.sin(self.t * 8.3 + g["slot"]) * wob,
               chest[1] + 0.2, chest[2] + math.cos(self.t * 6.1 + g["slot"]) * wob)
        self.tracers.append((self.t, src, dst, (255, 208, 150)))
        g["shot_dir"] = tuple(dst[i] - src[i] for i in range(3))
        if self.audio:
            self.audio.guard_shot()
            if not hit:
                self.audio.whiz()
        if not hit:
            return
        p = STATE.player
        if p is None:
            return
        dmg = int(prof["damage"] * 0.8 * GUARD_DMG) + 1
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
        T.scene()._snapshot_for_blend(surface)
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
             "color": P.SODIUM, "intensity": 1.05, "range": 13.0},
            {"pos": (T.SIGNAL_BOX[0] - 0.5, 1.7, T.SIGNAL_BOX[1] + 2.0),
             "color": P.SODIUM, "intensity": 0.78, "range": 7.0},
            {"pos": (T.TRUCK_X, 2.6, T.TRUCK_STOP_Z - T.TRUCK_HALF_L - 0.3),
             "color": P.LAMP_WHITE, "intensity": 0.72, "range": 6.0},
            {"pos": (0.0, 3.4, 8.3), "color": P.SODIUM,
             "intensity": 0.62, "range": 13.0},
        ]
        T._light(r, flashes=flashes, pools=LAMP_POOLS)
        r.light = Light(direction=(-0.38, 0.68, -0.42), ambient=0.44,
                        diffuse=0.70, sky=0.30, tint=(0.88, 0.93, 1.08))
        r.set_camera(eye, tgt, fov)
        T._sky(r, tm)
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
        ts._draw_static_lights(r, set_t, train_offset=far, snow_n=150, beacon=True)
        _perimeter_sprites(r, tm)
        ts._draw_entrances(r, set_t)
        self._draw_volkov(r, set_t)
        self._draw_player(r, tm)
        self._draw_guards(r, tm)
        # Low air over the tracks and a cool haze behind the siding: the yard
        # reads as a deep space instead of a flat backdrop.
        for i, (hx, hz, hr, hc) in enumerate((
                (-10.0, -3.0, 6.0, (150, 164, 190)),
                (8.0, -5.0, 7.0, (146, 160, 188)),
                (22.0, -9.0, 6.0, (132, 148, 176)))):
            r.add_sprite((hx, 0.55, hz),
                         _fx.haze(hc, hr, tm, seed=730 + i, intensity=0.085),
                         layer=_fx.FX_LAYER)
        for i, (lx, lz) in enumerate((LAMPS[0], LAMPS[4], LAMPS[6])):
            r.add_sprite((lx, 6.1, lz),
                         _fx.light_shaft((255, 188, 108), 5.8, 0.42, 1.9,
                                         tm, seed=740 + i, intensity=0.10),
                         layer=_fx.FX_LAYER)
        self._draw_fx(r, tm)
        self._marker_screen = self._project(r, self._objective_point())
        r.flush(r.surface)
        T._grade_play(r.surface, self._wounded())
        T._present(r.surface, surface)
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

    def _gun_frame(self, head, shoulder, reload_p):
        """(origin, basis) of the K9 this frame, placed from his posed head
        and right shoulder: shouldered on the aim or at low ready, with the
        recoil kick and the reload tilt on top."""
        k = self.gun_up
        carry = 1.0 - k
        tilt = 0.0
        if reload_p is not None:
            tilt = math.sin(math.pi * clamp(reload_p, 0.0, 1.0))
        yaw = self.yaw + CARRY_YAW * carry - 4.0 * tilt
        pitch = (self.pitch * k + CARRY_PITCH * carry + KICK_UP * self.gun_kick
                 - 16.0 * tilt)
        B = _gun_basis(yaw, pitch, roll=-32.0 * tilt)

        def dot(p, axis):
            return p[0] * axis[0] + p[1] * axis[1] + p[2] * axis[2]

        # gun-axis coordinates of the trigger
        sh = [dot(shoulder, a) for a in B]
        ads = (dot(head, B[0]) + ADS_CHEEK,
               dot(head, B[1]) - ADS_DROP - K9_SIGHT_Y,
               sh[2] + ADS_POCKET - K9_BUTT_Z)
        low = (sh[0] + CARRY_OUT, sh[1] - CARRY_DROP,
               sh[2] + CARRY_POCKET - K9_BUTT_Z)
        c = [ads[i] * k + low[i] * carry for i in range(3)]
        c[2] -= KICK_BACK * self.gun_kick - 0.04 * tilt
        c[1] -= 0.05 * tilt
        O = tuple(B[0][i] * c[0] + B[1][i] * c[1] + B[2][i] * c[2] for i in range(3))
        return O, B

    def _gun_to_left(self, O, B, shoulder, w):
        """The K9 handed over to the left hand for a punch: it swings on the
        foregrip down to his left hip, muzzle to the snow ahead of him."""
        f = T._forward(self.yaw, 0.0)
        rgt = _screen_right(self.yaw)
        hang = (shoulder[0] + f[0] * 0.12 - rgt[0] * 0.03, shoulder[1] - 0.54,
                shoulder[2] + f[2] * 0.12 - rgt[2] * 0.03)
        Bm = _gun_basis(self.yaw + 30.0, -64.0, roll=-25.0)
        fwd = _unit(tuple(B[2][i] + (Bm[2][i] - B[2][i]) * w for i in range(3)))
        up = tuple(B[1][i] + (Bm[1][i] - B[1][i]) * w for i in range(3))
        d = sum(up[i] * fwd[i] for i in range(3))
        up = _unit(tuple(up[i] - fwd[i] * d for i in range(3)))
        Bw = (_cross(up, fwd), up, fwd)
        F = _gun_pt(O, B, K9_FORE)
        F = tuple(F[i] + (hang[i] - F[i]) * w for i in range(3))
        O = tuple(F[i] - sum(Bw[j][i] * K9_FORE[j] for j in range(3)) for i in range(3))
        return O, Bw

    def _fist(self, beats, grip, shoulder):
        """The punching (right) fist: cocked by the jaw, driven on a slight
        hook into the Guard's face (or straight down the aim) and back."""
        leg, k = beats[0], beats[1]
        f = T._forward(self.yaw, 0.0)
        rgt = _screen_right(self.yaw)
        cock = (shoulder[0] + f[0] * 0.07 + rgt[0] * 0.10, shoulder[1] - 0.08,
                shoulder[2] + f[2] * 0.07 + rgt[2] * 0.10)
        if leg == 0:
            return tuple(grip[i] + (cock[i] - grip[i]) * k for i in range(3))
        g = self.melee_g
        if g is not None and math.hypot(g["pos"][0] - shoulder[0],
                                        g["pos"][2] - shoulder[2]) < MELEE_R + 0.4:
            low = self.melee_t < g.get("up_at", -9.0)      # down: hit him there
            aim = (g["pos"][0], g["pos"][1] + (0.35 if low else 1.58), g["pos"][2])
        else:
            fp = T._forward(self.yaw, self.pitch * 0.5)
            aim = (shoulder[0] + fp[0] - rgt[0] * 0.12, shoulder[1] + fp[1] - 0.04,
                   shoulder[2] + fp[2] - rgt[2] * 0.12)
        d = _unit(tuple(aim[i] - shoulder[i] for i in range(3)))
        hit = tuple(shoulder[i] + d[i] * (UARM + FARM - 0.03) for i in range(3))
        if leg == 1:
            mid = [(cock[i] + hit[i]) * 0.5 + rgt[i] * 0.20 for i in range(3)]
            mid[1] += 0.05
            a, b = (1.0 - k) * (1.0 - k), 2.0 * k * (1.0 - k)
            return tuple(cock[i] * a + mid[i] * b + hit[i] * k * k for i in range(3))
        if leg == 2:
            return hit
        return tuple(hit[i] + (grip[i] - hit[i]) * k for i in range(3))

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
        if sp > 0.05:
            # the move direction in the hips' own axes
            a = math.radians(self.body_yaw)
            cy, sy = math.cos(a), math.sin(a)
            vx, vz = self.vel[0] / sp, self.vel[1] / sp
            pose = _gait(self.gait, sp, vx * cy - vz * sy, vx * sy + vz * cy, h._scale)
        else:
            pose = dict(POSES["stand"])
        # The torso turns back onto the aim from the hips and leans with the
        # pitch; shouldered, the head dips and leans onto the stock.
        k = self.gun_up
        pose["twist"] = pose.get("twist", 0.0) + self.twist
        pose["spine"] = (pose.get("spine", 3.0) + _AIM["spine"] * k
                         - 0.35 * self.pitch - 3.0 * self.gun_kick)
        pose["head_p"] = (pose.get("head_p", 0.0) + (_AIM["head_p"] + 4.0) * k
                          - 0.55 * self.pitch)
        u = (self.t - self.melee_t) / MELEE_S
        beats = _punch_beats(u) if 0.0 <= u < 1.0 else None
        at, ptw = self.pos, 0.0
        if beats:
            # wind the torso back, then throw it through behind the fist:
            # the lean and a step in carry the weight onto the front foot
            _leg, _k, coil, drive, _g = beats
            ptw = PUNCH_TWIST[0] * coil - PUNCH_TWIST[1] * drive
            pose["twist"] += ptw
            pose["spine"] += -5.0 * coil + 16.0 * drive
            pose["head_p"] -= 4.0 * coil + 10.0 * drive
            still = clamp(1.0 - sp / 2.0, 0.0, 1.0)
            for jk, v in (("lhip_p", 6.0 * coil + 22.0 * drive),
                          ("lkn", 8.0 * coil + 18.0 * drive),
                          ("rhip_p", -4.0 * coil - 16.0 * drive),
                          ("rkn", 16.0 * coil + 10.0 * drive),
                          ("rank", 20.0 * drive)):
                pose[jk] = pose.get(jk, NEUTRAL[jk]) + v * still
            f = T._forward(self.yaw, 0.0)
            lunge = PUNCH_LUNGE * drive - 0.05 * coil
            at = (at[0] + f[0] * lunge, at[1], at[2] + f[2] * lunge)
        pose["head_y"] = _wrap(self._aim_body_yaw() - self.body_yaw - self.twist - ptw)
        pose["head_x"] = 0.03 * k
        pl, j0, root = h.pose_world(pose, at, self.body_yaw, rifle_on=False)
        sh = {slot: (root[0] + o[0], root[1] + o[1], root[2] + o[2])
              for slot, _k, _m, o, _g, _f in pl if slot in (4, 10)}
        reload_p = (1.0 - self.reloading / RELOAD_S) if self.reloading else None
        O, B = self._gun_frame(j0["head"], sh[10], reload_p)
        if beats and beats[4] > 0.0:
            O, B = self._gun_to_left(O, B, sh[4], beats[4])
        self._gun = (O, B)
        rt = _gun_pt(O, B, K9_GRIP)
        lt = _gun_pt(O, B, K9_FORE)
        # the support hand slides back along the handguard rather than
        # hanging off a straight arm short of the foregrip
        guard = _gun_pt(O, B, K9_GUARD)
        for _i in range(4):
            if math.dist(sh[4], lt) <= ARM_REACH:
                break
            lt = tuple(lt[i] + (guard[i] - lt[i]) * 0.4 for i in range(3))
        if reload_p is not None:
            # the support hand drops to the mag well and comes back
            k = math.sin(math.pi * clamp((reload_p - 0.15) / 0.7, 0.0, 1.0))
            mw = _gun_pt(O, B, K9_MAGWELL)
            lt = tuple(lt[i] + (mw[i] - lt[i]) * k for i in range(3))
        pole = POLE_R
        if beats:
            rt = self._fist(beats, rt, sh[10])
            # elbow tucked under the cocked fist, out behind the landed one
            out = {0: beats[1] * 0.5, 1: 0.5 + 0.5 * beats[1], 2: 1.0}.get(beats[0], 1.0 - beats[1])
            base = POLE_COCK if beats[0] < 3 else POLE_R
            pole = tuple(base[i] + (POLE_PUNCH[i] - base[i]) * out for i in range(3))
        pose = _arm_ik(h, pose, "r", rt, at, self.body_yaw, pole)
        pole_l = POLE_L
        if beats:
            # the gun hand hangs: its elbow folds back, not out like a wing
            pole_l = tuple(POLE_L[i] + (POLE_HANG[i] - POLE_L[i]) * beats[4] for i in range(3))
        pose = _arm_ik(h, pose, "l", lt, at, self.body_yaw, pole_l)
        joints = _w.actor(r, key, pose, at, self.body_yaw, int(tm), seed=93,
                          amp=0.15, rifle_on=False, hd=True, bloody=True,
                          expression="angry", shadow=T._shadow_for(self.pos[2]))
        head = joints.get("head")
        if head is not None:
            r.add_sprite(head, _w.breath(head, tm + 600, seed=93, intensity=0.10),
                         layer=_fx.FX_LAYER)
        _draw_k9(r, O, B)
        _mesh, muzzle = _k9_asset()
        self._muzzle = _gun_pt(O, B, muzzle)
        if self.t - self.last_fire < 0.035:
            _w.add(r, _flash_mesh(O, B, muzzle, self.shots))

    def _guard_pose(self, g):
        """The pose his brain's stance asks for (see yard_brain)."""
        kind, st = g["kind"], g.get("stance", "post")
        if st in ("run", "walk") and g["moving"]:
            rate = (9.0 if kind == "rusher" else 7.0) if st == "run" else 4.6
            return pose_run(self.t * rate + g["slot"], lean=18 if st == "run" else 6)
        if st == "hide_low":
            return dict(POSES["cover_tight"])
        if st == "hide_high":
            pose = dict(POSES["ready"])
        elif st == "aim":
            pose = blend(POSES["stand"], "aim", 0.85)
        else:
            pose = dict(POSES.get(g["post_pose"], POSES["cover"]))
        if g["burst_left"] > 0 or self.t - g["last_shot_t"] < 0.4:
            pose = blend(pose, "aim", 0.75)
        return pose

    def _knocked_pose(self, g, want):
        """Punched off his feet: over on his back, a few dazed seconds on
        the snow, then up through a kneel into what his brain wants."""
        since = self.t - g["down_t"]
        if since < KNOCK_FALL:
            return blend(g["fall_from"], "dead_back", _smooth(since / KNOCK_FALL))
        q = (self.t - g["up_at"]) / KNOCK_RISE
        if q < 0.0:
            roll = math.sin(self.t * 2.6 + g["slot"])
            return dict(POSES["dead_back"], head_y=20.0 + 24.0 * roll,
                        head_p=-4.0 - 10.0 * abs(roll))
        if q < 0.55:
            return blend(POSES["dead_back"], "kneel", _smooth(q / 0.55))
        return blend(POSES["kneel"], want, _smooth((q - 0.55) / 0.45))

    def _draw_guards(self, r, tm):
        for g in self.guards:
            x, y, z = g["pos"]
            kind = g["kind"]
            prof = T._guard_profile(kind)
            if not g["alive"]:
                k = clamp((self.t - g["dead_t"]) / 0.45, 0.0, 1.0)
                was = g.get("pose") or POSES.get(g["post_pose"], POSES["stand"])
                pose = blend(was, g.get("dead_pose", "dead_back"), k)
                _w.actor(r, ("guard", kind), pose, (x, y, z), g["yaw"],
                         int(tm), seed=100 + g["slot"], amp=0.0,
                         rifle_on=False, hd=True, shadow=T._shadow_for(z))
                if g.get("mags") and k >= 1.0:
                    gx, gz = B._dir(g["yaw"])
                    mp = (x - gz * 0.45, y + 0.08, z + gx * 0.45)
                    for i in range(g["mags"]):
                        _w.add(r, box(0.07, 0.05, 0.2, (40, 44, 50),
                                      center=(mp[0] + 0.1 * i, mp[1], mp[2])))
                    pulse = 0.5 + 0.5 * math.sin(self.t * 4.0 + g["slot"])
                    r.add_sprite((mp[0], mp[1] + 0.12, mp[2]),
                                 _fx.glow((255, 214, 140), 0.28, tm,
                                          intensity=0.35 + 0.35 * pulse),
                                 layer=_fx.FX_LAYER)
                continue
            # ease between stances (a run cycle is already continuous)
            want = self._guard_pose(g)
            dt = clamp(self.t - g.get("pose_t", self.t), 0.0, 0.1)
            g["pose_t"] = self.t
            if self.t < g.get("down_until", -9.0):
                pose = g["pose"] = self._knocked_pose(g, want)
            else:
                if g.get("pose") is None or (g["moving"] and g.get("stance") in ("run", "walk")):
                    pose = want
                else:
                    pose = blend(g["pose"], want, min(1.0, dt * 14.0))
                g["pose"] = pose
                stag = max(0.0, 1.0 - (self.t - g["hit_t"]) / 0.3)
                if stag > 0.0:
                    pose = dict(pose, spine=pose.get("spine", 8) - 12.0 * stag)
                rock = 1.0 - (self.t - g.get("punch_t", -9.0)) / 0.55
                if 0.0 < rock <= 1.0:
                    rock = rock * rock * (3.0 - 2.0 * rock)
                    pose = dict(pose, spine=pose.get("spine", 8) - 14.0 * rock,
                                head_p=pose.get("head_p", 0) - 34.0 * rock,
                                head_y=pose.get("head_y", 0) + 22.0 * rock,
                                twist=pose.get("twist", 0) + 16.0 * rock,
                                lsh_r=pose.get("lsh_r", 8) + 24.0 * rock,
                                rkn=pose.get("rkn", 2) + 18.0 * rock)
            if not (g["moving"] and g.get("stance") in ("run", "walk")):
                pose = _hold_cached(_w.hum(("guard", kind), True), pose, "rifle", "ready",
                                    key=("guard", kind))
            joints = _w.actor(r, ("guard", kind), pose, (x, y, z), g["yaw"],
                              int(tm), seed=100 + g["slot"], amp=0.4,
                              rifle_on=True, hd=True, shadow=T._shadow_for(z))
            ch = joints.get("chest", (x, y + 1.3, z))
            lamp = (ch[0], ch[1] + 0.20, ch[2])
            if math.sin(self.t * 7.0 + g["slot"]) > -0.3:
                _w.add(r, box(0.06, 0.06, 0.06, (255, 40, 30), center=lamp,
                              emissive=True))
            lc = prof.get("lamp", (220, 50, 40))
            r.add_sprite(lamp, _fx.glow(lc, 0.12, tm, seed=470 + g["slot"],
                                        core=lc, intensity=0.6),
                         layer=_fx.FX_LAYER)
            m = joints.get("muzzle")
            if m is not None:
                if g["torch"]:
                    r.add_sprite(m, _fx.glow((226, 236, 255), 0.12, tm,
                                             seed=450 + g["slot"], core=(226, 236, 255),
                                             intensity=0.7),
                                 layer=_fx.FX_LAYER)
                if self.t - g["last_shot_t"] < 0.05:
                    sd = g.get("shot_dir") or B._dir(g["yaw"])
                    sd = sd if len(sd) == 3 else (sd[0], 0.0, sd[1])
                    _w.add(r, _guard_flash_mesh(m, sd, g["slot"] + int(g["last_shot_t"] * 60)))

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
        # The top-down game's HUD (yard_hud): HOSTILES and OBJECTIVE top
        # left, the tiled minimap top right, K-9 panel over the HP strip.
        target = self._objective_point()
        dist = math.hypot(target[0] - self.pos[0], target[2] - self.pos[2])
        if self.near_terminal:
            head = "Use the Guard terminal - who was on that tower?"
        elif self._all_clear():
            head = "Get to the Guard terminal - the signal box is clear"
        elif self.route_stage == 0:
            head = "Get round the freight siding - the signal box is behind it"
        else:
            head = "Clear the signal box - who fired? The Guard terminal knows"
        U.hostiles(surface, self._living() + len(self.pending))
        U.objective(surface, "%s (%d m)." % (head, int(round(dist))))
        screen = getattr(self, "_marker_screen", None)
        if screen is not None and not self.near_terminal:
            H.marker(surface, screen, dist, "SIGNAL BOX" if self.route_stage else None,
                     col=U.OBJECTIVE_COL)
        U.build_minimap(BOUNDS, BLOCKERS, (-21.0, 2.7, 21.0, 7.7),
                        (0.0, T.CARRIAGE_TRACK_Z, T.FREIGHT_Z), T.TRUCK_X)
        _rects, _lines, seen, fwd = self._minimap_data()
        U.minimap(surface, (self.pos[0], self.pos[2]), fwd, seen, (target[0], target[2]))
        # the reticle, hits, damage
        U.reticle(surface, int(3 * self.recoil - 2 * self.ads))
        H.crosshair(surface, 0, lines=False,
                    reload_frac=(1.0 - self.reloading / RELOAD_S) if self.reloading else 0.0,
                    hit_age=self.t - self.hit_mark)
        H.damage_arcs(surface, self.dmg_marks, self.t, life=0.9)
        p = STATE.player
        top = (getattr(p, "max_hp", 115) or 115) if p else 115
        U.weapon(surface, p.hp if p else 0, top, self.mag, MAG, self.reserve,
                 self.reloading, RELOAD_S)
        if self.toast and self.t - self.toast[0] < 1.6:
            U.prompt(surface, self.toast[1])
        elif self.near_terminal:
            U.prompt(surface, "Use the Guard terminal", "E")
        elif self.mag <= 0 and self.reserve <= 0:
            U.prompt(surface, "Dry - punch, or take mags off the bodies", "F")
        elif self._melee_target()[0] is not None:
            U.prompt(surface, "Melee", "F")
        # Frame-time watchdog: drop a render tier if the fight is not holding
        # the frame (see perf.py).  The next frame re-targets the off-screen
        # frame at the new buffer size and cross-fades the step.
        _perf.govern("m6_yard", surface=surface)
        T.scene()._resolution_blend(surface)


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
