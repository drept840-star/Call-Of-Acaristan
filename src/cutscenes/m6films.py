"""m6films.py - engine3d takes and 2D fallbacks for every Mission 6 film.

Registered scene ids (exact contract from ``docs/MISSION6_PLOT.md``):

    insertion   m6_insert_chase, m6_insert_cabin, m6_insert_valley,
                m6_insert_jump, m6_insert_ground
    boxcar      m6_boxcar_wide, m6_boxcar_notebook, m6_boxcar_volkov,
                m6_boxcar_biribel, m6_boxcar_exit
    ending      m6_customs_return, m6_customs_terminal,
                m6_radio_vasile (four authored shots), m6_radio_silence,
                m6_radio_maru, m6_cut_line, m6_helicopter

``cutscenes.engine`` resolves these through ``core.cutscene_registry``.  Each
take draws the engine3d version and, when the 3D stack declines (backend
missing, ``ACARISTAN_CUTSCENE3D=0``, or a previous failure), a complete
hand-authored 2D scene draws instead.  Captions, typewriter, skip and pause
stay property of the app's CutscenePlayer; renderers never draw dialogue.

This module must not import ``missions.m6`` (shot data lives there and imports
this module); it reads the current shot through ``core.cutscene_registry``.
"""
import math
import random

import pygame

from core.config import HEIGHT, SCENE_BOT, SCENE_TOP, WIDTH, font_terminal_small
from core.outfits import OUTFIT_GUARD
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from core.cutscene_registry import register_scene_renderers as _register

__all__ = ["draw_m6_scene_3d", "m6_3d_enabled", "prepare", "M6_3D_SCENES"]

_BIRI = ("biribel", OUTFIT_GUARD)
_cache = {"failed": False, "err": None}
_FONT_CACHE = {}
_SCAN_CACHE = {}


def _mono(size, bold=True):
    key = (size, bold)
    font = _FONT_CACHE.get(key)
    if font is None:
        font = pygame.font.SysFont("Consolas", size, bold=bold)
        _FONT_CACHE[key] = font
    return font

CRT_LINES = (
    ("KRAP BORDER CUSTOMS", "GUARD PERSONNEL // RESTRICTED"),
    ("ID", "4471-K"),
    ("NAME", "VELICU, B."),
    ("INTAKE", "KRAP 4 // Y-3"),
    ("CLASS", "TOP OF CLASS"),
    ("STATUS", "KIA - Y-2"),
)
CRT_FOOT = "CALLSIGN: UCILEV NADGOB IERDNA"
CRT_CALLSIGN = "ANDREI BOGDAN VELICU"
_CRT_SOURCE = "UCILEV NADGOB IERDNA"

def m6_3d_enabled():
    import os
    if os.environ.get("ACARISTAN_CUTSCENE3D", "1").strip() == "0":
        return False
    return not _cache["failed"]


def _k(t, start, length):
    from engine3d.core import smooth
    return smooth(max(0.0, min(1.0, (t - start) / float(length))))


def _mix(a, b, k):
    from engine3d.rig import blend
    return blend(a, b, k)


def _rig_insert(r, heli=None, cabin=0.0, amb=0.19, dif=0.46,
                fill=(-0.30, 0.52, 0.60), bounce=None,
                yaw=None, bank=None, extra=None):
    """Moonlit exterior: a camera-side cold key, plus the red cabin practical
    only when the lens is close enough to the door for it to model a face."""
    from engine3d.core import Light
    if yaw is None:
        yaw = _HELI_YAW
    if bank is None:
        bank = _HELI_BANK
    r.light = Light(direction=fill, ambient=amb, diffuse=dif, sky=0.07,
                    tint=(0.78, 0.87, 1.07))
    lights = []
    if cabin > 0.0 and heli is not None:
        lights.append({"pos": _w.heli_xform(heli, yaw, bank)(
            0.72, 1.62, 0.86), "color": (255, 92, 64), "intensity": cabin,
            "range": 2.2})
    if bounce is not None:
        lights.append(bounce)
    if extra:
        lights.extend(extra)
    r.set_lights(lights)


def _cam(r, t, eye, tgt, fov, hh=0.0, seed=0, roll=0.0, shk=None):
    return _w.cam(r, t, eye, tgt, fov, hh=hh, seed=seed, roll=roll, shk=shk)


def _shot_text():
    shot = _w.current_shot() or {}
    return str(shot.get("text") or "")


# ═══════════════════════════════════════════════════════════════════════════
# insertion
# ═══════════════════════════════════════════════════════════════════════════
# Geography: the border compound sits on the valley floor (z 6..19); the
# snow ridge climbs south of it and the LZ is its crest shelf (~16.7 m).
# The Huey comes up the ridge nose-north with the open right door to the
# east, pedal-turns nose-west over the shelf so the door faces the crossing
# (m6world3d.crossing_far, 80-100 m north) and settles to a ~2 m hover;
# Biribel drops off the sill into the powder and walks north.
_PICKUP_XZ = (-2.0, 15.5)
_PICKUP_GROUND = _w.height_at(*_PICKUP_XZ)
# Door toward the runner from the east, tail pointed back between the lot
# lamps and the hut: the 6.2 m disc and the boom clear the compound.
_PICKUP_YAW = -30.0
_HOVER_XZ = (-1.0, -47.55)
_LZ_GROUND = _w.height_at(*_HOVER_XZ)
_HOVER_Y = _LZ_GROUND + 1.96            # skid bottom (y + 0.045) ~2 m over the shelf
_HELI_YAW = -90.0                       # the hover: nose west, door to the crossing
_HELI_BANK = 2.5
_SETTLE = 2.6                           # metres above the hover when the jump shot opens
_APPROACH_MS = 5000                     # reveal shot; the hover clock carries on from here
_TURN0, _TURN_MS = 1200, 2600           # the reveal's pedal turn
_JUMP_MS = 4400
_LAND = (_HOVER_XZ[0] - _w.HELI_DOOR_Z, _HOVER_XZ[1] + 2.55)
_SINK = 0.30                            # knee-deep in powder, on top of the 5 cm snow skin
_ROOT_DROP = 0.05
_PUSH, _LEAVE, _AIR = 1900, 2350, 600    # jump clock: push-off, feet leave, flight
_LAND_T = _LEAVE + _AIR


def hover_pos(t, climb=0.0, drift=(0.0, 0.0)):
    """The hover for the jump and ground shots; the ground shot passes
    climb/drift to leave.  The sway is deliberately larger than the rotor bob
    so a locked-off wide shot reads as a helicopter holding station."""
    bob = 0.18 * math.sin(t * 0.0016) + 0.06 * math.sin(t * 0.0029 + 1.3)
    sway_x = 0.55 * math.sin(t * 0.0011 + 0.4)
    sway_z = 0.38 * math.sin(t * 0.0009 + 2.0)
    return (_HOVER_XZ[0] + drift[0] + sway_x, _HOVER_Y + climb + bob,
            _HOVER_XZ[1] + drift[1] + sway_z)


def hover_yaw(t):
    # translation alone sells the hover; turning the airframe would swing the
    # seated feet across the skid AABB and eat the 2 cm contact budget.
    return _HELI_YAW


def hover_bank(t):
    # keep the roll steady: the door seat is posed against the skid top, and a
    # rolling skid changes the foot contact by more than the 2 cm budget.
    return _HELI_BANK


def _approach_e(t):
    q = max(0.0, min(1.0, t / float(_APPROACH_MS)))
    return 1.0 - (1.0 - q) * (1.0 - q)


def approach_pos(t):
    """Reveal shot: the Huey comes up the ridge from the south and flares
    into the hover; the last frame equals the jump shot's first."""
    e = _approach_e(t)
    a = (_HOVER_XZ[0] - 3.0, _HOVER_Y + _SETTLE + 6.0, -72.0)
    b = hover_pos(t, climb=_SETTLE)
    return tuple(a[i] + (b[i] - a[i]) * e for i in range(3))


def approach_yaw(t):
    """Nose north up the ridge, then a pedal turn to nose west that swings
    the open door off the slope onto the crossing."""
    return _HELI_YAW * _w.ease5(t, _TURN0, _TURN_MS)


def approach_pitch(t):
    # nose down for the climb, a flare as it slows, level in the hover
    return (4.0 * (1.0 - _w.ease5(t, 0, 2200))
            - 3.0 * math.sin(math.pi * _w.ease5(t, 1800, 3200)))


def jump_heli(t):
    """The hover during the jump shot: it settles the last 2.6 m while he
    shifts his weight, then holds."""
    return hover_pos(_APPROACH_MS + t,
                     climb=_SETTLE * (1.0 - _w.ease5(t, 0, 1500)))


def cabin_heli(t, ang=None):
    """The briefing flies the chase's river run, further up the valley, with
    the bank eased so the cabin holds still enough to talk in."""
    if ang is None:
        ang = _cabin_angle()
    p, yaw, bank, _pitch = run_heli(_CABIN_T0 + (3600.0 if ang == 2 else 0.0) + t)
    return p, yaw, 0.4 * bank, 2.5


_SEAT = {}


def _door_seat(key, upper, z=_w.HELI_DOOR_Z):
    """Seated door pose + airframe-local root: pelvis over the sill, soles on
    the skid, shins hanging outside the open door."""
    h = _w.hum(key)
    pose = _w.sit_pose(h, _w.HELI_SILL_Y - _w.HELI_SKID_Y, upper)
    a = _w.ankles(h, pose, (0.0, _w.HELI_SKID_Y, 0.0), 90.0)
    dx = 0.5 * (a["l"][0] + a["r"][0])
    dz = 0.5 * (a["l"][2] + a["r"][2])
    return pose, (_w.HELI_SKID_X - dx, _w.HELI_SKID_Y, z - dz)


def heli_seat():
    d = _SEAT.get("v")
    if d is None:
        d = _SEAT["v"] = _door_seat(_BIRI, dict(spine=7, head_p=1, lsh_p=12,
                                                lel=30, rsh_p=10, rsh_r=2,
                                                rel=26))
    return d


def seated_door(t):
    """Biribel on the sill during the approach -> (pose, world pos, yaw)."""
    pose, root = heli_seat()
    hp, hy, hb, hpit = heli_at("m6_insert_valley", t)
    return pose, _w.heli_xform(hp, hy, hb, hpit)(*root), hy + 90.0


def _landed_pose():
    return _mix("kneel_over", "kneel_over", 0.0)


def _landed_root():
    """Root that plants the crouch on ``_LAND``, knee-deep in the powder."""
    pos = _w.planted_pos(_w.hum(_BIRI), _landed_pose(), _HELI_YAW + 90.0, _LAND)
    return (pos[0], _w.height_at(*_LAND) - _ROOT_DROP - _SINK, pos[2])


# the rifle at port arms, as the rack in the briefing leaves it
_PORT_ARMS = dict(rsh_p=48, rsh_r=10, rel=78, lsh_p=58, lsh_r=4, lel=54,
                  rifle_y=-28, rifle_p=-22)


def jump_stage(t):
    """Weight shift on the sill, a leg push, a short ballistic drop and a
    crouch into the powder -> (pose, root, yaw, heli).  The feet do not move
    before the push, so nothing skates on the skid; the rifle stays at port
    arms all the way down."""
    pose0, root = heli_seat()
    heli = jump_heli(t)
    L = _w.heli_xform(heli, hover_yaw(t), hover_bank(t))
    yaw = hover_yaw(t) + 90.0
    wind = _w.ease5(t, 900, 600)
    lean = _w.ease5(t, 1400, 450)
    push = _w.ease5(t, _PUSH, 450)
    pose = dict(pose0, **_PORT_ARMS)
    pose["spine"] = 7 + 5 * wind + 13 * lean + 8 * push
    pose["head_p"] = 6 - 4 * wind - 7 * lean + 4 * push
    pose["rsh_p"] = _PORT_ARMS["rsh_p"] - 6 * lean
    pose["lsh_p"] = _PORT_ARMS["lsh_p"] - 8 * lean
    leap = dict(pose, spine=24, head_p=-6,
                lhip_p=-16, rhip_p=-8, lkn=58, rkn=46)
    if push > 0.0:
        pose = _mix(pose, leap, push)
    if t <= _LEAVE:
        out = 0.82 * min(1.0, push * 1.6)
        sm = max(0.0, (push - 0.85) / 0.15)
        drop = 0.52 * sm * sm
        return pose, L(root[0] + out, root[1] - drop, root[2]), yaw, heli
    _p, p0, _y, _h = jump_stage(_LEAVE)
    q = min(1.0, (t - _LEAVE) / float(_AIR))
    end = _landed_root()
    land = _mix(leap, "kneel_over", _w.ease5(t, _LEAVE + 150, 450))
    x = p0[0] + (end[0] - p0[0]) * q
    z = p0[2] + (end[2] - p0[2]) * q
    y = p0[1] + (end[1] + _SINK - p0[1]) * q * q + 0.22 * math.sin(math.pi * q)
    y -= _SINK * _w.ease5(t, _LAND_T, 380)
    return land, (x, y, z), yaw, heli


_GROUND_ROUTE = {}
_W0 = 3100
_WALK_MS = 4200                 # longer than the shot: he is still walking at the cut
_READY_KEYS = ("lsh_p", "lsh_r", "lel", "rsh_p", "rsh_r", "rel", "rifle_p")


def ground_route():
    r = _GROUND_ROUTE.get("v")
    if r is None:
        r = _GROUND_ROUTE["v"] = _w.path([_LAND, (_LAND[0] - 0.15, _LAND[1] + 4.2)])
    return r


def ground_watch(t):
    """0..1: how far he has turned to watch the Huey climb away."""
    return _w.ease5(t, 1300, 700) * (1.0 - _w.ease5(t, 2450, 600))


def ground_stage(t):
    """Rises out of the powder facing the crossing, turns to watch the Huey
    climb away, faces north again and walks toward the floodlights."""
    hum = _w.hum(_BIRI)
    rise = _w.ease5(t, 200, 1100)
    if t < _W0:
        watch = ground_watch(t)
        yaw = _HELI_YAW + 90.0 + 35.0 * watch
        pose = _mix("kneel_over", "ready", rise)
        pose["spine"] = pose.get("spine", 0) + 8 * math.sin(math.pi * rise)
        pos = _w.planted_pos(hum, pose, yaw, _LAND)
        sink = _SINK * (1.0 - rise)
        root = (pos[0], _w.height_at(*_LAND) - _ROOT_DROP - sink, pos[2])
        if watch > 0.0:
            hp = heli_depart(t)[0]
            tw, hy = _look(root, yaw, hp, twist_max=25.0, head_max=45.0,
                           share=0.4)
            up = max(-30.0, _pitch_to((root[0], root[1] + 1.6, root[2]), hp))
            pose["twist"] = pose.get("twist", 0) + tw * watch
            pose["head_y"] = pose.get("head_y", 0) + hy * watch
            pose["head_p"] = pose.get("head_p", 0) + up * watch
        return pose, root, yaw
    route = ground_route()
    stride = _w.walk_stride(route.length, 0.56)
    g0, g1 = _w.walk_span(route.length, stride)
    g = g0 + (g1 - g0) * _w.travel(t, _W0, _WALK_MS)
    pose, pos, wyaw = _w.walk(hum, route, g, stride, speed=1.05,
                              ground=lambda x, z: _w.height_at(x, z) - _ROOT_DROP)
    from engine3d.rig import POSES
    for k in _READY_KEYS:
        pose[k] = POSES["ready"][k]
    pose["head_p"] = pose.get("head_p", 0) - 2.0
    return pose, pos, wyaw


def heli_depart(t):
    """The hover lifts, pedal-turns nose south-south-east and climbs away
    back over the ridge, gathering speed, lights out ->
    (pos, yaw, bank, pitch)."""
    q = max(0.0, (t - 300) / 5700.0)
    q2 = q * q
    turn = _w.ease5(t, 700, 2400)
    return (hover_pos(_APPROACH_MS + _JUMP_MS + t,
                      climb=3.0 * _w.ease5(t, 300, 1600) + 26.0 * q2,
                      drift=(10.0 * q2, -38.0 * q2)),
            _HELI_YAW - 105.0 * turn,
            _HELI_BANK - 6.0 * math.sin(math.pi * turn), 9.0 * q2)


def pickup_pos(t):
    """The Huey coming down into the customs lot, then holding at the skid."""
    k = _w.ease5(t, 0, 3200)
    bob = 0.08 * math.sin(t * 0.0016) + 0.03 * math.sin(t * 0.0031 + 1.2)
    sway = 0.25 * math.sin(t * 0.0011 + 0.4)
    return (_PICKUP_XZ[0] + sway,
            _PICKUP_GROUND + 0.75 + 8.5 * (1.0 - k) + bob,
            _PICKUP_XZ[1] + 0.18 * math.sin(t * 0.0009 + 2.0))


def heli_at(scene, t):
    """Airframe placement ``scene`` draws at ``t`` -> (pos, yaw, bank, pitch);
    None for sets without a helicopter.  The probe and tests read this."""
    if scene == "m6_insert_chase":
        return run_heli(t)
    if scene == "m6_insert_cabin":
        return cabin_heli(t)
    if scene == "m6_insert_valley":
        return approach_pos(t), approach_yaw(t), _HELI_BANK, approach_pitch(t)
    if scene == "m6_insert_jump":
        return jump_heli(t), hover_yaw(t), hover_bank(t), 0.0
    if scene == "m6_insert_ground":
        return heli_depart(t)
    if scene == "m6_helicopter":
        t = min(t, 12000)
        if t < 4600:
            return pickup_pos(t), _PICKUP_YAW, 1.5, 0.0
        if t < 8200:
            k = _w.ease5(t, 4600, 650)
            p = pickup_pos(4600)
            # turn the open right door toward the capital (+z) for the cabin
            return ((p[0], p[1] + 0.90 * k, p[2]),
                    _PICKUP_YAW + (-90.0 - _PICKUP_YAW) * k, 1.5 - 3.0 * k,
                    -1.0 * k)
        # Lift off nose-west, then a right turn that ends flying north at
        # the hills: the path is a quadratic curve from west to north.
        q = _w.travel(t, 8200, 3800)
        p = pickup_pos(4600)
        base = (p[0], p[1] + 0.90, p[2])
        s = q * q
        k = 2.0 * s * (1.0 - s)
        return ((base[0] - 9.0 * k - 12.0 * s * s,
                 base[1] + 3.0 * k + 15.0 * s * s,
                 base[2] - 32.0 * s * s),
                -90.0 - 95.0 * _w.ease5(t, 8200, 3200),
                1.5 + 17.0 * math.sin(math.pi * q), -4.0 * q)
    return None


def walk_metrics(scene, second=None):
    """(hum, route, stride, speed) for the walking shots, else None."""
    if scene == "m6_boxcar_exit":
        if second is None:
            second = _exit_second()
        route = _route_b() if second else _route_a()
        return (_w.hum("volkov"), route, _w.walk_stride(route.length, 0.58),
                0.9)
    if scene == "m6_insert_ground":
        route = ground_route()
        return (_w.hum(_BIRI), route, _w.walk_stride(route.length, 0.56), 1.05)
    return None


def _cabin_angle():
    """1: Maru turns from the controls; 2: Biribel at the door answers."""
    return 1 if "notebook" in _shot_text() else 2


_CABIN_T0 = 9000.0              # run clock the briefing starts on
_GREEN = (80, 236, 150)         # instrument light
_MOON = (150, 184, 236)
_RACK_MS = 900


def _strobe(t, hz=7.0, depth=0.38):
    """Moonlight chopped by the rotor: 1 between blades, 1 - depth under one.
    Calmer under the reduced-flash setting, steady with reduced motion."""
    if _fx.reduced_motion():
        return 1.0
    ph = (t * hz / 1000.0) % 1.0
    return 1.0 - depth * _fx.flash_scale() * (1.0 if ph < 0.22 else 0.0)


def _run_light():
    """The run's moon key.  Chase and briefing share it, so the valley bakes
    once for the three shots."""
    from engine3d.core import Light
    return Light(direction=(0.70, 0.42, 0.58), ambient=0.24, diffuse=0.78,
                 sky=0.10, tint=(0.80, 0.89, 1.10))


def maru_look(t, ang):
    """Maru's turn from the windscreen to the man at the door ->
    (twist, head_y) in the pilot rig's frame."""
    if ang != 1:
        return 0.0, 0.0
    _pp, proot = _w.heli_pilot()
    _bp, broot = heli_seat()
    tw, hy = _look(proot, 0.0, (broot[0] + 0.2, 1.4, broot[2]),
                   twist_max=20.0, head_max=40.0, share=0.4)
    k = _w.ease5(t, 250, 650)
    return tw * k, hy * k


def door_pose(t, ang):
    """Biribel on the sill with the rifle: across his knees while Maru
    talks; raised and racked as he answers (rack at ``_RACK_MS``)."""
    pose, _root = heli_seat()
    p = dict(pose)
    p.update(rsh_p=34, rsh_r=10, rel=70, lsh_p=40, lsh_r=4, lel=72,
             rifle_y=-58, rifle_p=8, head_p=6)
    if ang != 2:
        p["head_y"], p["twist"] = 22.0, 6.0
        return p
    up = _w.ease5(t, 150, 420)
    pull = _w.ease5(t, _RACK_MS, 90) * (1.0 - _w.ease5(t, _RACK_MS + 130, 110))
    p.update(rsh_p=34 + 14 * up - 8 * pull, rel=70 + 8 * up + 22 * pull,
             rifle_y=-58 + 30 * up, rifle_p=8 - 30 * up - 6 * pull,
             lsh_p=40 + 18 * up, lel=72 - 18 * up,
             head_p=6 + 6 * up - 4 * _w.ease5(t, 1300, 500),
             head_y=-6 + 10 * _w.ease5(t, 1300, 500))
    return p


def cabin_cam(ang, t, L):
    """Eye/target (world) for one briefing angle, rigid with the airframe."""
    k = min(1.0, t / 3200.0)
    if ang == 1:
        # in the open windscreen, right of her: her face over the coaming,
        # the man at the door past her shoulder, clear of her seat back
        eye = (0.96 - 0.03 * k, 2.02, 3.40 - 0.12 * k)
        tgt = (0.72, 1.75, 1.92)
        fov = 58.0
    else:
        # in the slipstream ahead of the door, looking aft along the skin:
        # his profile against the dark cabin, the snow streaming past
        eye = (1.98 - 0.05 * k, 1.64, 2.60 - 0.12 * k)
        tgt = (1.12, 1.40, 0.92)
        fov = 50.0
    return L(*eye), L(*tgt), fov


def _cabin_snow(r, t, L, n=30, seed=0):
    """Snow outside the airframe, in its frame: streams aft past the open door."""
    a = t * 0.001
    for i in range(n):
        u, v, w = _w._u(i, seed, 1), _w._u(i, seed, 2), _w._u(i, seed, 3)
        vel = (-0.4, -1.0, -24.0 - 6.0 * u)
        x = 1.35 + u * 3.5
        y = -0.8 + ((v * 4.0 - 0.6 * a) % 4.0)
        z = 4.0 - ((w * 10.0 + 26.0 * a * (1.0 + 0.2 * u)) % 10.0)
        p0 = L(x, y, z)
        p1 = L(x - vel[0] * 0.03, y - vel[1] * 0.03, z - vel[2] * 0.03)
        _w.flake_sprite(r, p0, p1, (150, 162, 186))


def _insert_cabin(surface, t):
    """INT. Huey, the briefing on the run.  Angle 1: Maru, lit green by the
    instruments, turns from the controls; Biribel sits at the open door
    behind her.  Angle 2: Biribel in profile against the door, the moon
    chopped by the rotor, snow streaming past; he racks the rifle."""
    t = min(t, 6000)
    ang = _cabin_angle()
    r, buf = _w.rend_ps2()
    r.fog, r.fog_start, r.fog_end = (12, 16, 26), 40.0, 175.0
    heli, hyaw, hbank, hpitch = cabin_heli(t, ang)
    L = _w.heli_xform(heli, hyaw, hbank, hpitch)
    _lamp, hit = _lamp_ray(L, hyaw, hpitch)
    r.light = _run_light()
    moon = _strobe(t)
    lights = [
        {"pos": L(0.52, 1.36, 2.80), "color": _GREEN, "intensity": 0.80,
         "range": 1.25},
        {"pos": L(0.36, 2.02, 0.42), "color": (255, 84, 58),
         "intensity": 0.55, "range": 2.2},
    ]
    if ang == 1:
        lights.append({"pos": L(2.3, 2.2, 1.1), "color": _MOON,
                       "intensity": 0.85 * moon, "range": 4.0})
    else:
        # the rim: moon behind him, outside and aft of the door; the
        # cockpit's green on the side of his face that the lens sees
        lights.append({"pos": L(2.5, 2.4, -0.9), "color": _MOON,
                       "intensity": 1.2 * moon, "range": 4.2})
        lights.append({"pos": L(0.45, 1.35, 2.30), "color": _GREEN,
                       "intensity": 0.7, "range": 2.2})
    r.set_lights(lights)
    r.set_pools([{"pos": (hit[0], hit[1] + 5.0, hit[2]), "range": 6.0,
                  "color": (230, 206, 160), "hot": (255, 250, 236),
                  "intensity": 2.6}])
    eye, tgt, fov = cabin_cam(ang, t, L)
    shk = None
    if ang == 2 and t >= _RACK_MS and not _fx.reduced_motion():
        shk = _fx.shake(t, _RACK_MS + 60, 260, 0.010 * _fx.shake_scale())
    _cam(r, t, eye, tgt, fov, hh=0.006, seed=20 + ang, shk=shk)
    _w.night(r, buf, t, top=(5, 8, 17), bot=(20, 28, 46), stars=60,
             moon=(50, 25.0), sodium=None, seed=33, star_cut=0.25)
    _w.static_scene(r, _RUN_SET)
    r.begin()
    _w.run_valley(r, t)
    _w.static_end(r)
    _w.helicopter(r, t, heli, yaw=hyaw, rotor_speed=1.0, bank=hbank,
                  pitch=hpitch, door=1.0, blur=0.5, pilot=False)
    ppose, proot = _w.heli_pilot()
    tw, hy = maru_look(t, ang)
    _air_actor(r, "maru", dict(ppose, twist=tw, head_y=hy), proot, 0.0, t, L,
               seed=61, amp=0.15, expression="neutral", mouth=0.0)
    _bp, broot = heli_seat()
    bpose, gun_o, gun_r = _k9_hold(door_pose(t, ang), broot, 90.0, t, ang)
    _air_actor(r, _BIRI, bpose, broot, 90.0, t, L, seed=34, amp=0.22, mouth=0.0)
    _k9_draw(r, L, gun_o, gun_r)
    _cabin_snow(r, t, L, seed=35)
    r.flush(buf)
    _w.present_ps2(surface, buf)
    _w.finish(surface, 6101, "", t=t, ps2=True)


def _wash(r, heli, t, k, seed):
    """Rotor wash on the powder under the hover: puffs and haze, no streaks."""
    gy = _w.height_at(heli[0], heli[2]) + 0.25
    at = (heli[0], gy, heli[2])
    r.add_sprite(at, _fx.powder(t, seed, 4.8, 0.55 * k), layer=_fx.FX_LAYER)
    r.add_sprite(at, _fx.powder(t + 700, seed + 1, 3.0, 0.45 * k),
                 layer=_fx.FX_LAYER)
    r.add_sprite((heli[0], gy + 0.2, heli[2]),
                 _fx.haze((176, 190, 212), 6.5, t, seed=seed + 2,
                          intensity=0.22 * k), layer=_fx.FX_LAYER)


# ── chase: the Huey up the frozen river ──
# The run valley (m6world3d.run_valley) repeats every RUN_P metres, so the
# airframe and the camera ride ``s = s0 + v t (mod RUN_P)`` together and the
# radio line can hold the shot as long as it likes.
_RUN_V = 0.028                  # m/ms along the river, ~100 km/h
_RUN_ALT = 7.0                  # skids over the ice, rotor level with the pines
_RUN_S0 = 26.0
_RUN_BANK = 400.0               # deg of bank per rad/m of turn (~10 deg peak)
_RUN_PITCH = 4.0                # cruise nose-down
_LAMP_DOWN = 0.44               # landing light's tilt below the nose line
_LAMP_COL = (255, 238, 204)
_RUN_SET = "m6_run"             # static key: chase and briefing share the bake


def run_s(t):
    return (_RUN_S0 + t * _RUN_V) % _w.RUN_P


def run_frame(z):
    """(forward, right) unit vectors of the river at ``z``."""
    d = _w.run_dx(z)
    n = math.hypot(d, 1.0)
    return (d / n, 0.0, 1.0 / n), (1.0 / n, 0.0, -d / n)


def run_heli(t, s=None):
    """The Huey on the river -> (pos, yaw, bank, pitch): yaw from the
    tangent, bank into the bends, a slow rotor bob."""
    z = run_s(t) if s is None else s
    d = _w.run_dx(z)
    turn = _w.run_ddx(z) / (1.0 + d * d)
    bob = 0.22 * math.sin(t * 0.0013) + 0.07 * math.sin(t * 0.0031 + 0.7)
    return ((_w.run_x(z), _RUN_ALT + bob, z), math.degrees(math.atan2(d, 1.0)),
            max(-11.0, min(11.0, -turn * _RUN_BANK)), _RUN_PITCH)


def chase_cam(t):
    """The camera ship: it opens low on the east bank ahead of the Huey,
    lets it roar past and climbs into a 3/4 rear chase with the landing
    light's pool sliding over the ice in frame -> (eye, tgt, fov)."""
    s = run_s(t)
    heli, yaw, _bank, pitch = run_heli(t, s)
    f, rt = run_frame(s)
    u = _w.ease5(t, 0, 3000)
    k = _w.ease5(t, 2400, 1800)
    dx = 12.0 + 6.5 * u + 0.9 * k * math.sin(t * 0.00061)
    dz = 22.0 - 30.0 * u + 1.6 * k * math.sin(t * 0.00047 + 2.0)
    ex, ez = heli[0] + rt[0] * dx + f[0] * dz, heli[2] + rt[2] * dx + f[2] * dz
    ey = 2.4 + 8.4 * u + 0.5 * k * math.sin(t * 0.00093 + 1.0)
    ey = max(ey, _w.run_height(ex, ez) + 1.8)
    _lamp, hit = _lamp_ray(_w.heli_xform(heli, yaw, 0.0, pitch), yaw, pitch)
    c = (heli[0], heli[1] + 1.4, heli[2])
    m = 0.30 + 0.14 * u
    tgt = tuple(c[i] + (hit[i] - c[i]) * m for i in range(3))
    return (ex, ey, ez), tgt, 58.0 - 6.0 * u


def _run_ground(x, z):
    return _w.run_height(x, z) if _w.RUN_Z0 < z < _w.RUN_Z1 else 0.0


def _lamp_ray(L, yaw, pitch, down=_LAMP_DOWN, ground=_run_ground):
    """Landing light under the chin -> (lamp, ground hit) in world space;
    ``down`` tilts it below the nose line, ``ground`` is the set's floor."""
    lamp = L(0.0, 0.52, 3.30)
    a, p = math.radians(yaw), math.radians(pitch) + down
    d = (math.sin(a) * math.cos(p), -math.sin(p), math.cos(a) * math.cos(p))
    hit = lamp
    for _i in range(3):
        g = ground(hit[0], hit[2])
        k = (lamp[1] - g) / max(0.05, -d[1])
        hit = (lamp[0] + d[0] * k, g, lamp[2] + d[2] * k)
    return lamp, hit


def _beam(r, a, b, w0, w1, col, k, steps=4, segs=6):
    """A cone of lit air from ``a`` to ``b``: tapered quads projected now,
    posterised in ``steps`` bands across and fading over ``segs`` lengths,
    added to the frame.  A per-pixel light, so the airframe in front of it
    masks it."""
    if k <= 0.02:
        return
    pts = []
    for j in range(segs + 1):
        q = j / float(segs)
        p = r.project(tuple(a[i] + (b[i] - a[i]) * q for i in range(3)))
        if p is None:
            return
        pts.append((p[0], p[1], (w0 + (w1 - w0) * q) * r.focal / p[2]))
    rad = max(p[2] for p in pts)
    x0 = int(min(p[0] for p in pts) - rad) - 2
    y0 = int(min(p[1] for p in pts) - rad) - 2
    x1 = int(max(p[0] for p in pts) + rad) + 2
    y1 = int(max(p[1] for p in pts) + rad) + 2
    if x1 - x0 > 2000 or y1 - y0 > 2000 or x1 - x0 < 3:
        return
    size = (x1 - x0, y1 - y0)
    img = pygame.Surface(size)
    img.fill((0, 0, 0))
    layer = pygame.Surface(size)
    for j in range(segs):
        (ax, ay, ra), (bx, by, rb) = pts[j], pts[j + 1]
        n = math.hypot(bx - ax, by - ay)
        if n < 0.5:
            continue
        nx, ny = -(by - ay) / n, (bx - ax) / n
        fade = 1.0 - 0.75 * j / float(segs)
        for i in range(steps):
            w = 1.0 - i / float(steps)
            c = tuple(int(v * k * fade / steps) for v in col)
            layer.fill((0, 0, 0))
            pygame.draw.polygon(layer, c, [
                (ax + nx * ra * w - x0, ay + ny * ra * w - y0),
                (bx + nx * rb * w - x0, by + ny * rb * w - y0),
                (bx - nx * rb * w - x0, by - ny * rb * w - y0),
                (ax - nx * ra * w - x0, ay - ny * ra * w - y0)])
            img.blit(layer, (0, 0), special_flags=pygame.BLEND_ADD)

    def draw(s, sx, sy, scale, z):
        s.blit(img, (x0, y0), special_flags=pygame.BLEND_ADD)
    draw.light = True
    draw.bounds = (x0, y0, size[0], size[1])
    mid = tuple(a[i] + (b[i] - a[i]) * 0.35 for i in range(3))
    r.add_sprite(mid, draw, layer=_fx.FX_LAYER)


def _ground_glow(r, at, radius_m, col, k):
    """Software stand-in for a GL pool: a flat ellipse on the ground,
    squashed by the view's grazing angle."""
    if getattr(r, "backend", "") == "gl" or k <= 0.02:
        return
    cam = r.cam
    dist = math.dist(cam, at) or 1.0
    flat = max(0.12, min(1.0, abs(cam[1] - at[1]) / dist))

    def draw(s, sx, sy, scale, z):
        rx = min(300, radius_m * scale)
        if rx < 2:
            return
        ry = max(1.5, rx * flat)
        kk = round(k * 32.0) / 32.0
        stops = ((0.0, _fx._m5._scale(col, kk)),
                 (1.0, _fx._m5._scale(col, kk * 0.2)))
        _fx._m5._add_at(s, _fx._halo_img(stops, rx, ry, power=2.2, levels=9,
                                     peak=1.0), sx, sy)
    draw.bounds_m = (radius_m, radius_m)
    draw.bounds_cap_px = (300, 300)
    r.add_sprite(at, draw, layer=_fx.FX_LAYER)


def _streak_snow(r, t, vel, seed=0, n=150, spread=14.0, height=9.0,
                 exposure=0.035, col=(150, 160, 182), lamp=None):
    """World-anchored flakes wrapped round the lens, each drawn as the path
    it makes across the shutter: at chase speed they stream past as
    streaks.  ``vel`` is the camera's velocity (m/s).  ``spread`` should
    divide RUN_P / 2 so a wrap of the run is invisible.  ``lamp`` =
    (pos, dir, cos_cone) lights the flakes inside the landing-light cone."""
    cx, cy, cz = r.cam
    span = 2.0 * spread
    a = t * 0.001
    segs = []
    for i in range(n):
        u, v, w = _w._u(i, seed, 1), _w._u(i, seed, 2), _w._u(i, seed, 3)
        fall = 1.1 + 0.9 * w
        x = cx + ((u * span + 0.6 * a - cx + spread) % span) - spread
        z = cz + ((v * span - cz + spread) % span) - spread
        y = cy + ((((w * 37.0) % 1.0) * height - fall * a - cy + height / 2)
                  % height) - height / 2
        rel = (0.6 - vel[0], -fall - vel[1], -vel[2])
        tail = (x - rel[0] * exposure, y - rel[1] * exposure, z - rel[2] * exposure)
        c = col
        if lamp is not None:
            lp, ld, cone = lamp
            dv = (x - lp[0], y - lp[1], z - lp[2])
            dn = math.sqrt(dv[0] ** 2 + dv[1] ** 2 + dv[2] ** 2) or 1.0
            ca = (dv[0] * ld[0] + dv[1] * ld[1] + dv[2] * ld[2]) / dn
            if ca > cone and dn < 26.0:
                c = (236, 230, 214)
        segs.append(((x, y, z), tail, c, 1))
    batch = getattr(r, "add_lines3d", None)
    if batch is not None:
        batch(segs, layer=4, depth_test=False)
    else:
        for p0, p1, c, wd in segs:
            r.add_line3d(p0, p1, c, wd, layer=4)


def _insert_chase(surface, t):
    """EXT: the Huey screams low up the frozen river under the moon, the
    camera ship alongside; the Guard intercept plays over it."""
    r, buf = _w.rend_ps2()
    r.fog, r.fog_start, r.fog_end = (12, 16, 26), 40.0, 175.0
    s = run_s(t)
    heli, hyaw, hbank, hpitch = run_heli(t, s)
    L = _w.heli_xform(heli, hyaw, hbank, hpitch)
    f, rt = run_frame(s)
    lamp, hit = _lamp_ray(L, hyaw, hpitch)
    # the moon rides behind the camera ship's shoulder (north-east): the
    # west wall and the ice take the key, the door side catches it
    r.light = _run_light()
    r.set_lights([
        {"pos": L(0.72, 1.62, 0.86), "color": (255, 92, 64), "intensity": 0.75,
         "range": 2.6},
        {"pos": (heli[0] + rt[0] * 7.0, heli[1] + 3.5, heli[2] + rt[2] * 7.0),
         "color": (150, 178, 226), "intensity": 0.55, "range": 13.0},
        {"pos": (hit[0], hit[1] + 1.5, hit[2]), "color": _LAMP_COL,
         "intensity": 0.7, "range": 8.0},
    ])
    gy = hit[1]
    # the pool lands on dark ice: it needs ~3x a lamp pool's gain to read
    r.set_pools([{"pos": (hit[0], gy + 5.0, hit[2]), "range": 6.0,
                  "color": (230, 206, 160), "hot": (255, 250, 236),
                  "intensity": 2.6}])
    eye, tgt, fov = chase_cam(t)
    e0, _t0, _f0 = chase_cam(t - 40.0)
    vel = tuple((eye[i] - e0[i]) / 0.040 for i in range(3))
    _cam(r, t, eye, tgt, fov, hh=0.03, seed=31, roll=0.25 * hbank)
    _w.night(r, buf, t, top=(5, 8, 17), bot=(20, 28, 46), stars=60,
             moon=(50, 25.0), sodium=None, seed=33, star_cut=0.25)
    _w.static_scene(r, _RUN_SET)
    r.begin()
    _w.run_valley(r, t)
    _w.static_end(r)
    _w.helicopter(r, t, heli, yaw=hyaw, rotor_speed=1.0, bank=hbank,
                  pitch=hpitch, blur=0.8)
    pose, root = heli_seat()
    _air_actor(r, _BIRI, dict(pose, head_p=4.0), root, 90.0, t, L, seed=34,
               amp=0.3)
    r.add_sprite(lamp, _fx.glow(_LAMP_COL, 0.9, core=_LAMP_COL, max_px=26),
                 layer=_fx.FX_LAYER)
    _beam(r, lamp, hit, 0.14, 0.16 * math.dist(lamp, hit), _LAMP_COL, 0.26)
    _ground_glow(r, hit, 6.0, (230, 214, 180), 0.55)
    # downwash: powder kicked off the ice behind the Huey, world-anchored
    step = 8.0
    base = math.floor(s / step) * step
    for i in range(6):
        sz = base - i * step
        age = (s - sz) / _RUN_V
        k = 0.42 * math.exp(-age / 900.0)
        if k < 0.03:
            continue
        r.add_sprite((_w.run_x(sz), 1.0, sz),
                     _fx.powder(age, 40 + int(sz // step) % 7, 4.0 + age * 0.003,
                                k, puffs=8), layer=_fx.FX_LAYER)
    ld = tuple((hit[i] - lamp[i]) / (math.dist(hit, lamp) or 1.0) for i in range(3))
    _streak_snow(r, t, vel, seed=35, lamp=(lamp, ld, 0.96))
    r.flush(buf)
    _w.present_ps2(surface, buf)
    _w.finish(surface, 6100, "", t=t, ps2=True)


def _air_actor(r, key, pose, root, yaw, t, L, seed=0, amp=0.2,
               expression="stern", mouth=None, rifle_on=False):
    """An actor built in airframe space and carried through ``L``, so he
    banks and pitches with the Huey.  Logged in ``LAST`` with world joints
    for the exposure checks.  ``rifle_on`` arms Biribel's rig."""
    h = _w.hum(key, flags=("rifle",) if rifle_on and key == _BIRI else ())
    if mouth is None:
        mouth = 0.0
        if _w.talking(str(key).upper() if not isinstance(key, tuple) else "BIRIBEL"):
            from engine3d.rig import mouth_flap
            mouth = mouth_flap(int(t), seed)
    face = (expression, round(mouth, 2))
    if getattr(h, "_m6_face", None) != face:
        h.set_expression(expression, mouth)
        h._m6_face = face
    p = _w.life_pose(pose, t, amp, seed)
    verts, faces, joints = h.build(p, root, yaw, rifle_on=rifle_on)
    r.add_dynamic([L(*v) for v in verts], faces)
    world = {k: L(*v) for k, v in joints.items() if v is not None and len(v) == 3}
    if len(_w.LAST) < 16:
        a0, a1 = L(0.0, 0.0, 0.0), L(math.sin(math.radians(yaw)), 0.0,
                                     math.cos(math.radians(yaw)))
        wyaw = math.degrees(math.atan2(a1[0] - a0[0], a1[2] - a0[2]))
        _w.LAST.append({"key": key, "joints": world, "pos": L(*root),
                        "yaw": wyaw, "pose": p})
    return world


# ── the ridge: reveal, drop, alone ──
# One static set and one moon key for the three shots, so the ridge bakes
# once.  The moon stands north-north-east over the crossing: the door side
# of the hover and his face as he drops take the key, and from behind him on
# the walk it rims him against the floodlights.
_RIDGE_SET = "m6_ridge"
_RIDGE_FOG = ((10, 14, 22), 40.0, 230.0)
_SEARCH_COL = (236, 240, 255)


def _ridge_light():
    from engine3d.core import Light
    return Light(direction=(0.37, 0.50, 0.78), ambient=0.25, diffuse=0.62,
                 sky=0.08, tint=(0.78, 0.87, 1.07))


def _ridge(r, buf, t, seed):
    """Night sky and the shared ridge set: snow, pines, the border road, the
    crossing and the hills beyond it; no capital."""
    _w.night(r, buf, t, top=(5, 8, 16), bot=(18, 26, 44), stars=56,
             moon=(25, 24.0), sodium=(54, 36, 24), seed=seed, star_cut=0.3)
    _w.static_scene(r, _RIDGE_SET)
    r.begin()
    _w.terrain(r, t)
    _w.crossing_far(r, t)
    _w.dark_hills(r)
    _w.static_end(r)


def searchlight_hits(t):
    """Near-row floodlight towers sweeping the approach south of the strip,
    each on its own slow figure -> [(head, ground hit)].  ``t`` is the
    insertion clock, so the sweep carries across the cuts."""
    out = []
    for i, x in enumerate((-34.0, -12.0, 12.0, 34.0)):
        hx = x * 0.7 + 13.0 * math.sin(t * 0.00038 + 1.7 * i)
        hz = 19.0 + 8.0 * math.sin(t * 0.00027 + 3.4 * i)
        out.append(((x, 10.6, 30.0), (hx, _w.height_at(hx, hz), hz)))
    return out


def _searchlights(r, t, k=1.0):
    """Cold search beams off the towers -> their ground pools."""
    pools = []
    for i, (head, hit) in enumerate(searchlight_hits(t)):
        r.add_sprite(head, _fx.glow(_SEARCH_COL, 0.8, t, seed=70 + i,
                                    core=(255, 255, 255), intensity=0.9 * k,
                                    max_px=18), layer=_fx.FX_LAYER)
        _beam(r, head, hit, 0.35, 0.12 * math.dist(head, hit), _SEARCH_COL,
              0.22 * k)
        pools.append({"pos": (hit[0], hit[1] + 6.0, hit[2]), "range": 4.5,
                      "color": (200, 212, 236), "hot": (250, 252, 255),
                      "intensity": 1.6 * k})
        _ground_glow(r, hit, 4.5, (190, 200, 224), 0.5 * k)
    return pools


_VEIL = {}


def _veil(buf, k, col=(176, 188, 210)):
    """Downwash whiteout over the frame: powder thickest at the bottom,
    ``k`` 0..1 at the floor of the picture."""
    if k <= 0.01:
        return
    w, h = buf.get_size()
    ramp = _VEIL.get((w, h))
    if ramp is None:
        ramp = pygame.Surface((w, h))
        for y in range(h):
            v = int(255 * (0.35 + 0.65 * (y / float(h - 1)) ** 1.4))
            pygame.draw.line(ramp, (v, v, v), (0, y), (w, y))
        _VEIL[(w, h)] = ramp
    k = min(1.0, k)
    kr = ramp.copy()
    kr.fill((int(255 * k),) * 3, special_flags=pygame.BLEND_RGB_MULT)
    keep = pygame.Surface((w, h))
    keep.fill((255, 255, 255))
    keep.blit(kr, (0, 0), special_flags=pygame.BLEND_RGB_SUB)
    buf.blit(keep, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    kr.fill(col, special_flags=pygame.BLEND_RGB_MULT)
    buf.blit(kr, (0, 0), special_flags=pygame.BLEND_RGB_ADD)


def reveal_cam(t, L):
    """Over his left shoulder from inside the cabin, rigid with the airframe:
    down at the ridge streaming under the skid, then the pedal turn pans the
    door onto the crossing as the lens tilts up to it."""
    k = min(1.0, t / float(_APPROACH_MS))
    up = _w.ease5(t, _TURN0 + 300, 2800)
    return (L(0.05 + 0.08 * k, 1.98, 1.45 - 0.05 * k),
            L(10.0, -5.0 + 3.6 * up, -1.0 - 0.8 * up), 56.0)


def reveal_look(t, seat, yaw):
    """He turns his head onto the crossing before the airframe gets there
    -> (twist, head_y)."""
    tw, hy = _look(seat, yaw, (0.0, 3.0, 36.0), twist_max=20.0, head_max=40.0,
                   share=0.4)
    k = _w.ease5(t, _TURN0 + 600, 1400)
    return tw * k, hy * k


def _insert_valley(surface, t):
    """EXT/INT: over his shoulder at the open door as the Huey comes up the
    ridge and pedal-turns; the crossing swings into the doorway below, the
    floodlights sweeping, the lit train in the yard."""
    t = min(t, _APPROACH_MS)
    r, buf = _w.rend_ps2()
    r.fog, r.fog_start, r.fog_end = _RIDGE_FOG
    heli, hyaw, hbank, hpitch = heli_at("m6_insert_valley", t)
    L = _w.heli_xform(heli, hyaw, hbank, hpitch)
    pose, root = heli_seat()
    pose = dict(pose, **_PORT_ARMS)
    pose["head_p"] = 8.0
    pose["twist"], pose["head_y"] = reveal_look(t, L(*root), hyaw + 90.0)
    r.light = _ridge_light()
    r.set_lights([
        {"pos": L(0.36, 2.02, 0.42), "color": (255, 84, 58),
         "intensity": 0.28 * (1.0 - 0.6 * _w.ease5(t, _TURN0, 2000)),
         "range": 2.0},
        {"pos": L(3.0, 2.6, 1.6), "color": _MOON,
         "intensity": 1.0 * _strobe(t), "range": 4.5},
    ])
    eye, tgt, fov = reveal_cam(t, L)
    h0 = heli_at("m6_insert_valley", max(0.0, t - 40.0))
    e0, _t0, _f0 = reveal_cam(t, _w.heli_xform(*h0))
    vel = tuple((eye[i] - e0[i]) / 0.040 for i in range(3))
    _cam(r, t, eye, tgt, fov, hh=0.012, seed=1)
    _ridge(r, buf, t, seed=3)
    r.set_pools(_searchlights(r, t))
    _w.helicopter(r, t, heli, yaw=hyaw, rotor_speed=1.0, bank=hbank,
                  pitch=hpitch, door=1.0, blur=0.5)
    _air_actor(r, _BIRI, pose, root, 90.0, t, L, seed=2, amp=0.22,
               rifle_on=True)
    _streak_snow(r, t, vel, seed=5, n=110, spread=12.0, height=8.0)
    r.flush(buf)
    _w.present_ps2(surface, buf)
    _w.finish(surface, 6102, "KIM KIM BORDER // 02:40", t=t, ps2=True)


def drop_cam(t):
    """Off the lip of the shelf north of the door, at the height of the
    snow he lands in: up at the man on the sill against the airframe, then
    down onto the powder -> (eye, target, fov)."""
    u = _w.ease5(t, 0, _JUMP_MS)
    g = _w.height_at(*_LAND)
    ex, ez = _LAND[0] - 1.5 + 0.3 * u, _LAND[1] + 6.4 - 0.5 * u
    eye = (ex, max(_w.height_at(ex, ez) + 0.5, g + 1.25 + 0.2 * u), ez)
    a = (_LAND[0] - 0.4, g + 3.0, _LAND[1] - 1.6)
    b = (_LAND[0] + 0.3, g + 0.9, _LAND[1] - 0.4)
    k = _w.ease5(t, _LEAVE - 100, 700)
    return eye, tuple(a[i] + (b[i] - a[i]) * k for i in range(3)), 64.0


def _drop_veil(t, heli):
    """Whiteout strength: a base off the downwash that thickens as the hover
    settles, and a burst when he hits the powder."""
    low = 1.0 - max(0.0, min(1.0, (heli[1] - _HOVER_Y) / _SETTLE))
    k = 0.06 + 0.07 * low + 0.02 * math.sin(t * 0.0021)
    if t > _LAND_T:
        k += 0.62 * _fx.flash_scale() * math.exp(-(t - _LAND_T) / 380.0)
    return k


def _insert_jump(surface, t):
    """EXT: low hover in the downwash, the landing light's cone on the
    snow; he drops off the skid and the powder hits the lens."""
    t = min(t, _JUMP_MS)
    r, buf = _w.rend_ps2()
    r.fog, r.fog_start, r.fog_end = _RIDGE_FOG
    pose, seat, yaw, heli = jump_stage(t)
    hyaw, hbank = hover_yaw(t), hover_bank(t)
    L = _w.heli_xform(heli, hyaw, hbank)
    lamp, hit = _lamp_ray(L, hyaw, 0.0, down=1.05, ground=_w.height_at)
    head = _joints(_BIRI, pose, seat, yaw)["head"]
    r.light = _ridge_light()
    r.set_lights([
        {"pos": (head[0] + 0.8, head[1] + 0.6, head[2] + 2.4), "color": _MOON,
         "intensity": 0.9, "range": 4.6},
        {"pos": L(0.36, 2.02, 0.42), "color": (255, 84, 58),
         "intensity": 0.55, "range": 2.4},
        {"pos": (hit[0], hit[1] + 1.2, hit[2]), "color": _LAMP_COL,
         "intensity": 0.8, "range": 5.0},
    ])
    eye, tgt, fov = drop_cam(t)
    shk = None
    if not _fx.reduced_motion():
        shk = _fx.shake(t, _LAND_T, 420, 0.026 * _fx.shake_scale())
    _cam(r, t, eye, tgt, fov, hh=0.03, seed=7, shk=shk)
    _ridge(r, buf, t, seed=8)
    pools = _searchlights(r, _APPROACH_MS + t)
    pools.append({"pos": (hit[0], hit[1] + 4.0, hit[2]), "range": 3.2,
                  "color": (230, 206, 160), "hot": (255, 250, 236),
                  "intensity": 2.2})
    r.set_pools(pools)
    _w.helicopter(r, t, heli, yaw=hyaw, rotor_speed=1.0, bank=hbank,
                  door=1.0, pilot=False)
    _w.actor(r, _BIRI, pose, seat, yaw, t, seed=9, amp=0.30,
             expression="stern", rifle_on=True, flags=("rifle",))
    r.add_sprite(lamp, _fx.glow(_LAMP_COL, 0.7, core=_LAMP_COL, max_px=30),
                 layer=_fx.FX_LAYER)
    _beam(r, lamp, hit, 0.12, 0.30 * math.dist(lamp, hit), _LAMP_COL, 0.34)
    _ground_glow(r, hit, 1.8, (230, 214, 180), 0.6)
    k = 0.55 + 0.45 * (1.0 - (heli[1] - _HOVER_Y) / _SETTLE)
    _wash(r, heli, t, max(0.4, min(1.0, k)), 10)
    g = _w.height_at(*_LAND)
    if t > _LAND_T:
        age = t - _LAND_T
        fade = max(0.0, 1.0 - age / 1100.0)
        r.add_sprite((_LAND[0], g + 0.2, _LAND[1]),
                     _fx.powder(age, 14, 1.8, 0.7 * fade, puffs=9),
                     layer=_fx.FX_LAYER)
        # the burst the downwash throws at the lens
        f = tuple(tgt[i] - eye[i] for i in range(3))
        n = math.sqrt(sum(c * c for c in f)) or 1.0
        near = tuple(eye[i] + f[i] / n * 1.6 for i in range(3))
        r.add_sprite(near, _fx.powder(age, 15, 1.4, 0.55 * fade * fade,
                                      puffs=10), layer=_fx.FX_LAYER)
    _streak_snow(r, t, (2.0, -1.5, 3.5), seed=11, n=120, spread=9.0,
                 height=7.0, exposure=0.05, col=(168, 178, 198))
    r.flush(buf)
    _veil(buf, _drop_veil(t, heli))
    _w.present_ps2(surface, buf)
    _w.finish(surface, 6103, "", t=t, ps2=True)


def ground_cam(t, pos):
    """Orbits him clockwise from just off his front, round his right side as
    he watches the Huey go, to behind him over the crossing as he walks
    -> (eye, target, fov)."""
    u = _w.ease5(t, 500, 5300)
    g = _w.height_at(*_LAND)
    hx, hy, hz = pos[0], pos[1] + 1.5, pos[2]
    ang = math.radians(-20.0 + 200.0 * u)
    rad = 5.0 + 2.4 * u
    ex, ez = hx + rad * math.sin(ang), hz + rad * math.cos(ang)
    ey = max(_w.height_at(ex, ez) + 0.8, g + 1.0 + 1.2 * u)
    up = 0.7 * (1.0 - _w.ease5(t, 600, 2200))       # the Huey over him
    lead = 5.0 * _w.ease5(t, 2800, 3000)            # then the crossing ahead
    return (ex, ey, ez), (hx, hy - 0.3 + up, hz + lead), 52.0


def _insert_ground(surface, t):
    """EXT: the Huey lifts off him and climbs away dark over the ridge; the
    snow settles; he rises, watches it go and walks for the floodlights."""
    t = min(t, 6000)
    pose, pos, yaw = ground_stage(t)
    hpos, hyaw, hbank, hpitch = heli_depart(t)
    r, buf = _w.rend_ps2()
    r.fog, r.fog_start, r.fog_end = _RIDGE_FOG
    r.light = _ridge_light()
    head = _joints(_BIRI, pose, pos, yaw)["head"]
    r.set_lights([
        {"pos": (head[0] + 1.6, head[1] + 0.8, head[2] + 2.2), "color": _MOON,
         "intensity": 0.95, "range": 5.0},
        {"pos": (head[0] - 0.6, head[1] + 0.4, head[2] + 3.6),
         "color": (255, 196, 128), "intensity": 0.45, "range": 5.0},
    ])
    eye, tgt, fov = ground_cam(t, pos)
    shk = None
    if not _fx.reduced_motion():
        shk = _fx.shake(t, 0, 380, 0.020 * _fx.shake_scale())
    _cam(r, t, eye, tgt, fov, hh=0.02, seed=16, shk=shk)
    _ridge(r, buf, t, seed=17)
    r.set_pools(_searchlights(r, _APPROACH_MS + _JUMP_MS + t))
    _w.helicopter(r, t, hpos, yaw=hyaw, rotor_speed=1.0, bank=hbank,
                  pitch=hpitch, door=1.0, lit=t < 1500, pilot=False)
    _w.actor(r, _BIRI, pose, pos, yaw, t, seed=18, amp=0.45,
             expression="stern", rifle_on=True, flags=("rifle",))
    wash = max(0.0, 1.0 - _w.travel(t, 0, 2600))
    if wash > 0.03:
        _wash(r, hpos, t + 2000, wash, 19)
    r.flush(buf)
    _veil(buf, 0.16 * wash)
    _w.present_ps2(surface, buf)
    _w.finish(surface, 6104, "", t=t, ps2=True)


# ═══════════════════════════════════════════════════════════════════════════
# boxcar
# ═══════════════════════════════════════════════════════════════════════════
# Staging is pure (shot clock -> placements) so the probe and the clearance
# tests pose exactly what the renderer draws.  Volkov sits on the door-side
# corner of the lid with his shins hanging clear of both edges; Biribel stands
# off his right knee, between him and the open door.
_SEAT_Y = 0.47
_V_SEAT = (-0.72, 0.0, 1.18)
_V_YAW = 110.0
_B_MARK = (-0.30, 0.0, 0.20)
_B_YAW = -12.0
# Open notebook offered across the gap: spine across the two actors, pages
# tilted toward the receiver, both of Volkov's hands under the outer edges.
# Held 15 cm out toward Biribel: closer in, his leaning chest swallows the
# left hand.
_OFFER_L = (-0.416, 1.16, 0.908)
_OFFER_R = (-0.464, 1.16, 0.572)
_OFFER_YAW = -82.0
_OFFER_PITCH = -28.0
_TAKE = (-0.44, 1.10, 0.70)


def _local(pos, yaw, right=0.0, up=0.0, fwd=0.0):
    a = math.radians(yaw)
    c, s = math.cos(a), math.sin(a)
    return (pos[0] + right * c + fwd * s, pos[1] + up, pos[2] - right * s + fwd * c)


def _lerp3(a, b, k):
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(3))


def _look(pos, yaw, target, twist_max=30.0, head_max=55.0, share=0.35):
    """Twist + head yaw that turn a planted actor's gaze onto ``target``."""
    rel = (_w.yaw_to(pos, target) - yaw + 180.0) % 360.0 - 180.0
    tw = max(-twist_max, min(twist_max, rel * share))
    return tw, max(-head_max, min(head_max, rel - tw))


def _pitch_to(src, dst, cap=42.0):
    """head_p (+ = down) aiming from ``src`` onto ``dst``; the eyes do the
    rest past ``cap``, a head never folds onto the chest to read."""
    return min(cap, math.degrees(math.atan2(
        src[1] - dst[1], math.hypot(dst[0] - src[0], dst[2] - src[2]))))


def _joints(key, pose, pos, yaw):
    return _w.hum(key).pose_world(pose, pos, yaw)[1]


def _seated(upper):
    return _w.sit_pose(_w.hum("volkov"), _SEAT_Y, upper)


def _knee_grip(key, pose, pos, yaw, side, back=0.07, up=0.075):
    kn = _w.knees(_w.hum(key), pose, pos, yaw)[side]
    f = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    return (kn[0] - f[0] * back, kn[1] + up, kn[2] - f[1] * back)


def _hand(key, pose, pos, yaw, side, target, pole=None):
    return _w.reach(_w.hum(key), pose, side, target, pos, yaw, pole)


def _unit(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _k9_hold(pose, root, yaw, t, ang):
    """Biribel's K-9 hold, built on his body: the grip in front of the chest
    and both hands IK'd onto the gun; angle 2 raises it as he racks it.
    The left hand takes the foregrip if his arm reaches, else slides back
    along the handguard (as the yard hold does).
    -> (pose, trigger origin O, gun axes R), airframe-local."""
    from engine3d.core import m_apply, rot_y
    from missions.m6.yard3d import ARM_REACH, K9_FORE, K9_GRIP, K9_GUARD
    places, j, base = _w.hum(_BIRI).pose_world(pose, root, yaw, rifle_on=False)
    fwd = m_apply(rot_y(yaw), (0.0, 0.0, 1.0))
    side = m_apply(rot_y(yaw), (1.0, 0.0, 0.0))
    chest = j["chest"]
    if ang == 2:
        k = _w.ease5(t, 150, 420)
        grip = [chest[i] + 0.24 * fwd[i] for i in range(3)]
        grip[1] += -0.10 + 0.06 * k
        aim = (fwd[0], fwd[1] + 0.20, fwd[2])
    else:
        grip = [chest[i] + 0.20 * fwd[i] for i in range(3)]
        grip[1] += -0.25
        aim = (fwd[0], fwd[1] - 0.10, fwd[2])
    grip = tuple(grip)
    f = _unit(aim)
    r = _unit(_cross((0.0, 1.0, 0.0), f))
    u = _cross(f, r)
    R = (r[0], u[0], f[0], r[1], u[1], f[1], r[2], u[2], f[2])
    d = m_apply(R, K9_GRIP)
    O = tuple(grip[i] - d[i] for i in range(3))

    def on_gun(g):
        d = m_apply(R, g)
        return tuple(O[i] + d[i] for i in range(3))
    pose = _hand(_BIRI, pose, root, yaw, "r", grip, _OUT["r"])
    sh = next(o for slot, _k, _m, o, _g, _f in places if slot == 4)
    sh = tuple(base[i] + sh[i] for i in range(3))
    lt, guard = on_gun(K9_FORE), on_gun(K9_GUARD)
    for _ in range(4):
        if math.dist(sh, lt) <= ARM_REACH:
            break
        lt = tuple(lt[i] + (guard[i] - lt[i]) * 0.4 for i in range(3))
    return _hand(_BIRI, pose, root, yaw, "l", lt, _OUT["l"]), O, R


def _k9_draw(r, L, O, R):
    """The K-9 with its trigger at O and gun axes R (airframe-local), via L."""
    from engine3d.core import m_apply
    from missions.m6.yard3d import K9_TINT, _k9_asset
    mesh, _muzzle = _k9_asset()
    faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces]
    verts = []
    for v in mesh.verts:
        d = m_apply(R, v)
        verts.append(L(O[0] + d[0], O[1] + d[1], O[2] + d[2]))
    r.add_dynamic(verts, faces, tint=K9_TINT)


# Elbow pole for a hand crossing the body (torso-local): forward and out over
# the reaching side, so the forearm passes in front of the chest, not through.
# elbow poles that swing the elbow out past the ribs, not through them
_OUT = {"l": (-1.0, -1.0, 0.0), "r": (1.0, -1.0, 0.0)}
_CROSS = {"l": (-1.0, 0.0, 0.3), "r": (0.6, -0.3, 0.75)}


def _b_head():
    return _joints(_BIRI, {}, _B_MARK, _B_YAW)["head"]


def _v_rest(spine=16.0, head=None, extra=None):
    """Seated Volkov, both hands resting on his thighs above the knees."""
    up = dict(spine=spine, head_p=2.0 if head is None else -8.0)
    up.update(extra or {})
    if head is not None:
        up["twist"], up["head_y"] = head
    p = _seated(up)
    for side in "lr":
        p = _hand("volkov", p, _V_SEAT, _V_YAW, side,
                  _knee_grip("volkov", p, _V_SEAT, _V_YAW, side), _OUT[side])
    return p


def _b_base(spine=4.0):
    return dict(spine=spine, lsh_p=10, lsh_r=8, lel=16, rsh_p=10, rsh_r=8, rel=16)


def _read_point(open_k=1.0, lift=0.0):
    return _local(_B_MARK, _B_YAW, up=1.22 + lift, fwd=0.34)


def _low_point():
    """Open notebook lowered to the belt line while he listens."""
    return _local(_B_MARK, _B_YAW, up=1.04, fwd=0.28)


def _b_reading(pose, open_k=1.0, lift=0.0, page=0.0):
    """Both hands on the outer edges of the notebook held at reading height."""
    c = _read_point(open_k, lift)
    half = 0.085 + 0.085 * open_k + 0.02
    for side, sgn in (("l", -1), ("r", 1)):
        tgt = _local(c, _B_YAW, right=sgn * half, up=-0.02)
        if side == "r" and page > 0:
            k = math.sin(math.pi * page)
            tgt = _lerp3(tgt, _local(c, _B_YAW, right=0.06, up=0.03), k)
        pose = _hand(_BIRI, pose, _B_MARK, _B_YAW, side, tgt)
    return pose


def _rest_hand(key, pose, pos, yaw, side):
    return _joints(key, pose, pos, yaw)[side + "hand"]


def _cast(key, pose, pos, yaw, seed, expr, amp=0.4):
    return {"key": key, "pose": pose, "pos": tuple(pos), "yaw": yaw,
            "seed": seed, "expr": expr, "amp": amp}


def _stage_wide(t):
    ext = _w.ease5(t, 500, 1100) * (1.0 - _w.ease5(t, 3500, 1100))
    take = _w.ease5(t, 2500, 900)
    read = _w.ease5(t, 3700, 1300)
    both = _w.ease5(t, 4300, 800)
    open_k = _w.ease5(t, 5100, 500)
    bh = _b_head()
    vp = _v_rest(16 + 4 * ext, _look(_V_SEAT, _V_YAW, bh))
    knee_r = _knee_grip("volkov", vp, _V_SEAT, _V_YAW, "r")
    knee_l = _knee_grip("volkov", vp, _V_SEAT, _V_YAW, "l")
    vp = _hand("volkov", vp, _V_SEAT, _V_YAW, "r",
               _lerp3(knee_r, _OFFER_R, ext), _OUT["r"])
    vp = _hand("volkov", vp, _V_SEAT, _V_YAW, "l",
               _lerp3(knee_l, _OFFER_L, ext), _CROSS["l"])

    vhead = _joints("volkov", vp, _V_SEAT, _V_YAW)["head"]
    tw, hd = _look(_B_MARK, _B_YAW, vhead)
    bp = _b_base(4 + 9 * take * (1 - read))
    bp["twist"], bp["head_y"] = tw * (1 - read), hd * (1 - read)
    nb_c = _read_point(open_k)
    bp["head_p"] = _pitch_to(bh, _TAKE) * take * (1 - read) + \
        _pitch_to(bh, nb_c) * read
    rest_l = _rest_hand(_BIRI, bp, _B_MARK, _B_YAW, "l")
    rest_r = _rest_hand(_BIRI, bp, _B_MARK, _B_YAW, "r")
    half = 0.085 + 0.085 * open_k + 0.02
    read_l = _local(nb_c, _B_YAW, right=-half, up=-0.02)
    read_r = _local(nb_c, _B_YAW, right=half, up=-0.02)
    lt = _lerp3(_lerp3(rest_l, _TAKE, take), read_l, read)
    bp = _hand(_BIRI, bp, _B_MARK, _B_YAW, "l", lt, _OUT["l"])
    bp = _hand(_BIRI, bp, _B_MARK, _B_YAW, "r", _lerp3(rest_r, read_r, both),
               _OUT["r"])
    if t < 3300:
        nb = {"mode": "offer", "who": 0}
    elif both < 0.98:
        nb = {"mode": "hand_flat", "who": 1, "side": "l",
              "yaw": _OFFER_YAW, "pitch": _OFFER_PITCH}
    else:
        nb = {"mode": "hands", "who": 1, "open": open_k}
    return [_cast("volkov", vp, _V_SEAT, _V_YAW, 22, "sad"),
            _cast(_BIRI, bp, _B_MARK, _B_YAW, 23, "stern")], nb


def _stage_notebook(t):
    page = max(0.0, min(1.0, (t - 2350) / 700.0))
    bp = _b_base(9)
    c = _read_point()
    bp["head_p"] = _pitch_to(_b_head(), c) + 4
    bp = _b_reading(bp, page=page)
    return [_cast(_BIRI, bp, _B_MARK, _B_YAW, 26, "worried", 0.3)], \
        {"mode": "hands", "who": 0, "open": 1.0, "page": page}


def _stage_volkov(t):
    up = _w.ease5(t, 1700, 900)
    bh = _b_head()
    tw, hd = _look(_V_SEAT, _V_YAW, bh)
    p = _seated(dict(spine=24 - 6 * up, head_p=22 - 36 * up,
                     twist=tw * (0.4 + 0.6 * up), head_y=hd * up))
    kn = _w.knees(_w.hum("volkov"), p, _V_SEAT, _V_YAW)
    mid = _lerp3(kn["l"], kn["r"], 0.5)
    clasp = _local(mid, _V_YAW, up=-0.06, fwd=0.02)
    for side, sgn in (("l", -1), ("r", 1)):
        p = _hand("volkov", p, _V_SEAT, _V_YAW, side,
                  _local(clasp, _V_YAW, right=sgn * 0.035))
    biri = _b_base(6)
    nb_c = _low_point()
    for side, sgn in (("l", -1), ("r", 1)):
        biri = _hand(_BIRI, biri, _B_MARK, _B_YAW, side,
                     _local(nb_c, _B_YAW, right=sgn * 0.19, up=-0.02))
    return [_cast("volkov", p, _V_SEAT, _V_YAW, 28, "sad", 0.45),
            _cast(_BIRI, biri, _B_MARK, _B_YAW, 29, "worried", 0.3)], \
        {"mode": "hands", "who": 1, "open": 1.0}


def _stage_biribel(t):
    vp = _v_rest(18, _look(_V_SEAT, _V_YAW, _b_head()))
    vhead = _joints("volkov", vp, _V_SEAT, _V_YAW)["head"]
    lift = _w.ease5(t, 600, 900)
    tw, hd = _look(_B_MARK, _B_YAW, vhead)
    bp = _b_base(6 - 2 * lift)
    bp["twist"], bp["head_y"] = tw * lift, hd * lift
    bh = _b_head()
    nb_c = _low_point()
    bp["head_p"] = _pitch_to(bh, nb_c) * (1 - lift) + _pitch_to(bh, vhead) * lift
    for side, sgn in (("l", -1), ("r", 1)):
        bp = _hand(_BIRI, bp, _B_MARK, _B_YAW, side,
                   _local(nb_c, _B_YAW, right=sgn * 0.19, up=-0.02))
    return [_cast("volkov", vp, _V_SEAT, _V_YAW, 30, "sad"),
            _cast(_BIRI, bp, _B_MARK, _B_YAW, 32, "worried", 0.35)], \
        {"mode": "hands", "who": 1, "open": 1.0}


_ROUTE = {}


def _route_a():
    """Sit-to-stand lands on the seated ankle midpoint; two steps on."""
    r = _ROUTE.get("a")
    if r is None:
        p = _v_rest()
        a = _w.ankles(_w.hum("volkov"), p, _V_SEAT, _V_YAW)
        m0 = ((a["l"][0] + a["r"][0]) / 2, (a["l"][2] + a["r"][2]) / 2)
        f = math.sin(math.radians(_V_YAW)), math.cos(math.radians(_V_YAW))
        m1 = (m0[0] + f[0] * 0.62, m0[1] + f[1] * 0.62)
        r = _ROUTE["a"] = _w.path([m0, m1])
        r.m0 = m0
    return r


def _route_b():
    r = _ROUTE.get("b")
    if r is None:
        a = _route_a()
        p0 = a(a.length)[0]
        f = math.sin(math.radians(_V_YAW)), math.cos(math.radians(_V_YAW))
        p1 = (p0[0] + f[0] * 0.30, p0[2] + f[1] * 0.30)
        r = _ROUTE["b"] = _w.path([(p0[0], p0[2]), p1, (1.02, 0.56), (1.40, 0.58)])
    return r


def _gait(route, t, start, dur):
    s = _w.walk_stride(route.length, 0.58)
    g0, g1 = _w.walk_span(route.length, s)
    g = g0 + (g1 - g0) * _w.travel(t, start, dur)
    return _w.walk(_w.hum("volkov"), route, g, s, speed=0.9)


def _v_exit1(t):
    """Seated -> lean -> planted rise -> two steps toward the door."""
    lean = _w.ease5(t, 3000, 700)
    rise = _w.ease5(t, 3700, 1100)
    vh = _w.hum("volkov")
    route = _route_a()
    if t < 4800:
        seat = _v_rest(16 + 22 * lean, (0.0, 0.0), dict(head_p=-6 * lean))
        stand, _pos0, _y0 = _gait(route, 0, 4900, 1400)
        pose = _mix(seat, stand, rise)
        pose["spine"] = pose.get("spine", 0) + 30 * math.sin(math.pi * rise) * (rise < 1)
        pose["head_p"] = pose.get("head_p", 0) - 10 * math.sin(math.pi * rise)
        if rise < 0.6:
            for side in "lr":
                # hands ride the thighs until the knees straighten
                pos = _w.planted_pos(vh, pose, _V_YAW, route.m0)
                pose = _hand("volkov", pose, pos, _V_YAW, side,
                             _knee_grip("volkov", pose, pos, _V_YAW, side),
                             _OUT[side])
        pos = _w.planted_pos(vh, pose, _V_YAW, route.m0)
        return pose, pos, _V_YAW
    return _gait(route, t, 4900, 1400)


def _v_exit2(t):
    pose, pos, yaw = _gait(_route_b(), t, 300, 2300)
    turn = _w.ease5(t, 3000, 800)
    if turn > 0:
        tw, hd = _look(pos, yaw, _b_head(), twist_max=34, head_max=70, share=0.3)
        pose["twist"] = pose.get("twist", 0) * (1 - turn) + tw * turn
        pose["head_y"] = pose.get("head_y", 0) * (1 - turn) + hd * turn
        pose["head_p"] = pose.get("head_p", 0) + 5 * turn
    return pose, pos, yaw


def _b_track(t, vfn, lag=260.0):
    """Biribel's gaze follows Volkov with a reaction lag; feet stay put."""
    pose, pos, yaw = vfn(max(0.0, t - lag))
    head = _joints("volkov", pose, pos, yaw)["head"]
    return _look(_B_MARK, _B_YAW, head), head


def _arc(a, b, k, bulge=0.14):
    """a -> b bowed out in front of Biribel, so the forearm clears his coat."""
    return _local(_lerp3(a, b, k), _B_YAW, fwd=bulge * math.sin(math.pi * k))


def _stage_exit(t, second):
    if second:
        vpose, vpos, vyaw = _v_exit2(t)
        (tw, hd), vhead = _b_track(t, _v_exit2)
        bp = _b_base(4)
        bp["twist"], bp["head_y"] = tw, hd
        bp["head_p"] = _pitch_to(_b_head(), vhead)
        return [_cast("volkov", vpose, vpos, vyaw, 35, "sad", 0.3),
                _cast(_BIRI, bp, _B_MARK, _B_YAW, 36, "worried", 0.35)], None
    vpose, vpos, vyaw = _v_exit1(t)
    (tw, hd), vhead = _b_track(t, _v_exit1)
    close = _w.ease5(t, 500, 450)
    tuck = _w.ease5(t, 1000, 1100)
    back = _w.ease5(t, 2200, 800)
    up = _w.ease5(t, 900, 700)
    bp = _b_base(6 - 2 * up)
    bp["twist"], bp["head_y"] = tw * up, hd * up
    bh = _b_head()
    nb_c = _low_point()
    bp["head_p"] = _pitch_to(bh, nb_c) * (1 - up) + _pitch_to(bh, vhead) * up
    half = 0.19 - 0.085 * close
    # the closing notebook comes forward so the narrower grip clears his belly
    nb_c = _local(nb_c, _B_YAW, fwd=0.12 * close, up=0.06 * close)
    rest_l = _rest_hand(_BIRI, bp, _B_MARK, _B_YAW, "l")
    rest_r = _rest_hand(_BIRI, bp, _B_MARK, _B_YAW, "r")
    edge_l = _local(nb_c, _B_YAW, right=-half, up=-0.02)
    edge_r = _local(nb_c, _B_YAW, right=half, up=-0.02)
    coat = _local(_B_MARK, _B_YAW, right=-0.05, up=1.28, fwd=0.27)
    drop = _w.ease5(t, 1000, 700)
    bp = _hand(_BIRI, bp, _B_MARK, _B_YAW, "l",
               _arc(edge_l, rest_l, drop), _OUT["l"])
    bp = _hand(_BIRI, bp, _B_MARK, _B_YAW, "r",
               _arc(_lerp3(edge_r, coat, tuck), rest_r, back),
               _lerp3(_CROSS["r"], _OUT["r"], back))
    if t < 1000:
        nb = {"mode": "hands", "who": 1, "open": 1.0 - close}
    elif t < 2150:
        nb = {"mode": "hand", "who": 1, "side": "r", "open": 0.0}
    else:
        nb = None
    return [_cast("volkov", vpose, vpos, vyaw, 35, "sad", 0.3),
            _cast(_BIRI, bp, _B_MARK, _B_YAW, 36, "worried", 0.35)], nb


def _exit_second():
    return "wanted to get out" in _shot_text()


def boxcar_stage(scene, t, second=None):
    """Placements for a boxcar shot: ([cast...], notebook-or-None)."""
    if scene == "m6_boxcar_wide":
        return _stage_wide(t)
    if scene == "m6_boxcar_notebook":
        return _stage_notebook(t)
    if scene == "m6_boxcar_volkov":
        return _stage_volkov(t)
    if scene == "m6_boxcar_biribel":
        return _stage_biribel(t)
    if second is None:
        second = _exit_second()
    return _stage_exit(t, second)


_NB_LINES = ((0.068, 0.118, 0.104, 0.122, 0.0, 0.090, 0.112, 0.060),
             (0.112, 0.096, 0.124, 0.074, 0.085, 0.0, 0.118, 0.052))


def _notebook_mesh(center, yaw, pitch=0.0, open_k=0.0, page=0.0):
    from engine3d.core import Mesh, box, m_mul, rot_x, rot_y, rot_z
    nb = Mesh()
    if open_k < 0.5:
        nb.add(box(0.17, 0.03, 0.24, (10, 10, 12)))
        nb.add(box(0.006, 0.022, 0.226, (190, 184, 166)), t=(0.084, 0.0, 0.0))
    else:
        ink = (92, 88, 80)
        nb.add(box(0.34, 0.022, 0.25, (10, 10, 12)))
        nb.add(box(0.315, 0.010, 0.225, (206, 200, 182)), t=(0, 0.015, 0.0))
        # handwriting: ragged lines from the top (+z, away from the reader)
        for page, x0 in ((0, -0.145), (1, 0.020)):
            for i, ln in enumerate(_NB_LINES[page]):
                if ln:
                    nb.add(box(ln, 0.004, 0.007, ink),
                           t=(x0 + ln / 2, 0.022, 0.085 - i * 0.026))
        # Vasile's authorization code, underlined in red on the right page
        nb.add(box(0.085, 0.004, 0.004, (150, 34, 28)),
               t=(0.020 + 0.0425, 0.023, 0.085 - 4 * 0.026 - 0.008))
        # rail-office stamp, top of the left page
        nb.add(box(0.034, 0.004, 0.026, (120, 52, 46)), t=(-0.040, 0.022, 0.080))
        nb.add(box(0.012, 0.012, 0.225, (72, 68, 62)), t=(0.0, 0.020, 0.0))
        if 0.0 < page < 1.0:
            leaf = box(0.15, 0.004, 0.22, (214, 208, 190))
            hinge = Mesh().add(leaf, t=(0.075, 0.0, 0.0))
            nb.add(hinge, m=rot_z(180.0 * page), t=(0.0, 0.024, 0.0))
    out = Mesh()
    out.add(nb, m=m_mul(rot_y(yaw), rot_x(pitch)), t=center)
    return out


def _draw_notebook(r, nb, drawn, cast):
    if not nb:
        return
    who = cast[nb["who"]]
    j = drawn[nb["who"]]
    if nb["mode"] == "offer":
        lh, rh = j["lhand"], j["rhand"]
        c = ((lh[0] + rh[0]) / 2, (lh[1] + rh[1]) / 2 + 0.015,
             (lh[2] + rh[2]) / 2)
        _w.add(r, _notebook_mesh(c, _OFFER_YAW, _OFFER_PITCH, 1.0))
        return
    if nb["mode"] == "hand_flat":
        h = j[nb["side"] + "hand"]
        dx, dz = h[0] - who["pos"][0], h[2] - who["pos"][2]
        n = math.hypot(dx, dz) or 1.0
        c = (h[0] + dx / n * 0.10, h[1] + 0.06, h[2] + dz / n * 0.10)
        _w.add(r, _notebook_mesh(c, nb["yaw"], nb["pitch"], 1.0))
        return
    lh, rh = j["lhand"], j["rhand"]
    c = ((lh[0] + rh[0]) / 2, (lh[1] + rh[1]) / 2 + 0.02, (lh[2] + rh[2]) / 2)
    yaw = math.degrees(math.atan2(rh[0] - lh[0], rh[2] - lh[2])) - 90.0
    _w.add(r, _notebook_mesh(c, yaw, -38.0, nb.get("open", 1.0),
                             nb.get("page", 0.0)))


def _rig_boxcar(r, key=0.60, door=0.25, bounce=0.0, amb=0.24, dif=0.44,
                fill=(0.62, 0.55, -0.20)):
    """Lantern high key + cold door spill; the directional term is fill only.
    Point lights add without albedo, so faces near a bright one wash out."""
    from engine3d.core import Light, v_norm
    r.light = Light(direction=fill, ambient=amb, diffuse=dif,
                    sky=0.05, tint=(0.94, 0.97, 1.04))
    lights = [
        {"pos": _w.LANTERN, "color": (255, 182, 112), "intensity": key,
         "range": 4.5},
        {"pos": (2.70, 1.55, 0.30), "kind": "spot",
         "dir": v_norm((-1.0, -0.14, 0.05)), "cone": 0.62,
         "color": (108, 138, 188), "intensity": door, "range": 6.0},
    ]
    if bounce:
        lights.append({"pos": (-0.45, 0.58, 0.85), "color": (190, 120, 76),
                       "intensity": bounce, "range": 1.8})
    r.set_lights(lights)


_BOXCAR_CAMS = {
    # Every lens stays on the door (+x) side of the Volkov-Biribel line; the
    # 2.1:1 band leaves ~28 deg of vertical field, so two-shots shoot in
    # through the open door from the yard.
    "m6_boxcar_wide": ((2.55, 1.58, 0.45), (-0.45, 1.36, 0.70), 50, 0.010),
    "m6_boxcar_notebook": "ots",
    "m6_boxcar_volkov": ((0.36, 1.48, 0.02), (-0.53, 1.34, 1.05), 50, 0.006),
    "m6_boxcar_biribel": ((0.30, 1.52, 1.70), (-0.33, 1.68, 0.33), 46, 0.006),
    "exit1": ((2.45, 1.62, 0.10), (-0.15, 1.38, 0.85), 62, 0.010),
    "exit2": ((0.15, 1.58, -1.85), (0.60, 1.55, 0.50), 62, 0.010),
}
_BOXCAR_FX = {
    "m6_boxcar_wide": (6201, "MARKED BOXCAR // 03:06", 1.0, 0.0),
    "m6_boxcar_notebook": (6202, "THE NOTEBOOK", 0.6, 0.0),
    "m6_boxcar_volkov": (6203, "VOLKOV // THE LAST COPY", 0.7, 0.20),
    "m6_boxcar_biribel": (6204, "BIRIBEL // WHAT HE CARRIED", 0.7, 0.0),
    "exit1": (6205, "HE JUST WANTED OUT", 1.0, 0.0),
    "exit2": (6206, "HE JUST WANTED OUT", 0.3, 0.0),
}
# close-up key: the two-shot's default lantern level leaves the pitched face
# under the brim at the bottom of the readable range
_BOXCAR_KEY = {"m6_boxcar_volkov": 0.66}
# camera-side fill for the doorway two-shot (the face turned back into the
# car); a flatter yard fill for the rise, whose face leans toward the floor
_BOXCAR_FILL = {"exit1": (0.62, 0.30, -0.20), "exit2": (-0.50, 0.55, -0.65)}


def _boxcar_cam(key):
    cam = _BOXCAR_CAMS[key]
    if cam == "ots":
        # reader's POV: the lens hangs under his chin, so the pitched head
        # sits entirely behind the near plane; thumbs frame the spread
        return (_local(_B_MARK, _B_YAW, up=1.56, fwd=0.30),
                _local(_B_MARK, _B_YAW, up=1.22, fwd=0.38), 64, 0.004)
    return cam


def _boxcar_scene(scene):
    def draw(surface, t):
        second = scene == "m6_boxcar_exit" and _exit_second()
        key = scene if scene != "m6_boxcar_exit" else ("exit2" if second else "exit1")
        seed, tag, glow, bounce = _BOXCAR_FX[key]
        r, buf = _w.rend()
        r.fog, r.fog_start, r.fog_end = (16, 13, 10), 10.0, 26.0
        _rig_boxcar(r, key=_BOXCAR_KEY.get(key, 0.60), bounce=bounce,
                    **({"fill": _BOXCAR_FILL[key]} if key in _BOXCAR_FILL else {}))
        eye, tgt, fov, hh = _boxcar_cam(key)
        _cam(r, t, eye, tgt, fov, hh=hh, seed=seed)
        _w.night(r, buf, t, top=(5, 8, 15), bot=(20, 27, 42), stars=30,
                 sodium=(52, 36, 24), seed=seed)
        r.begin()
        _w.boxcar_interior(r, t, glow=glow)
        cast, nb = boxcar_stage(scene, t, second)
        drawn = [_w.actor(r, a["key"], a["pose"], a["pos"], a["yaw"], t,
                          seed=a["seed"], amp=a["amp"], expression=a["expr"])
                 for a in cast]
        _draw_notebook(r, nb, drawn, cast)
        for a, j in zip(cast, drawn):
            if a["key"] == "volkov":
                f = math.radians(a["yaw"] + a["pose"].get("twist", 0)
                                 + a["pose"].get("head_y", 0))
                m = (j["head"][0] + 0.11 * math.sin(f), j["head"][1] - 0.05,
                     j["head"][2] + 0.11 * math.cos(f))
                r.add_sprite(m, _w.breath(m, t, seed=seed, intensity=0.18),
                             layer=_fx.FX_LAYER)
        r.flush(buf)
        _w.present(surface, buf)
        _w.finish(surface, seed, tag, t=t)
    return draw


_boxcar_wide = _boxcar_scene("m6_boxcar_wide")
_boxcar_notebook = _boxcar_scene("m6_boxcar_notebook")
_boxcar_volkov = _boxcar_scene("m6_boxcar_volkov")
_boxcar_biribel = _boxcar_scene("m6_boxcar_biribel")
_boxcar_exit = _boxcar_scene("m6_boxcar_exit")


# ═══════════════════════════════════════════════════════════════════════════
# ending
# ═══════════════════════════════════════════════════════════════════════════
def _crt_panel(surface, rect, t, lines=CRT_LINES):
    """Diegetic personnel record, drawn at final resolution over the screen
    quad: typed query, rows revealing in order, then the callsign anagram
    sorting itself into the name it hides.  The reveal is the shot."""
    x, y, w, h = rect
    if w < 60 or h < 40:
        return
    pad = max(3, int(w * 0.028))
    panel = pygame.Surface((w, h))
    panel.fill((8, 22, 14))
    font_h = max(7, min(15, int(h * 0.082)))
    f_head = _mono(font_h, True)
    f_body = _mono(max(6, font_h - 1), True)
    f_small = _mono(max(6, font_h - 2), False)
    head_h = max(10, int(h * 0.155))
    pygame.draw.rect(panel, (14, 42, 25), (0, 0, w, head_h))
    title = f_head.render(lines[0][0], True, (150, 236, 176))
    panel.blit(title, (pad, max(1, head_h // 2 - title.get_height() // 2)))
    pygame.draw.line(panel, (46, 104, 66), (0, head_h), (w, head_h), 1)

    # search field: the query is typed, then the record answers it
    query = "UCILEV"
    typed = max(0, min(len(query), int((t - 500) / 150)))
    qy = head_h + 1
    q = "> " + query[:typed] + ("_" if int(t // 300) % 2 == 0 and typed < len(query) else "")
    panel.blit(f_small.render(q, True, (104, 200, 132)), (pad, qy))
    if t >= 2400:
        found = f_small.render("1 RECORD", True, (196, 168, 74))
        panel.blit(found, (w - pad - found.get_width(), qy))

    body_y = qy + f_small.get_height() + 2
    pw = max(22, int(w * 0.19))
    ph = max(20, int(h * 0.37))
    pr = pygame.Rect(pad, body_y, pw, ph)
    pygame.draw.rect(panel, (5, 13, 8), pr)
    pygame.draw.rect(panel, (40, 86, 56), pr, 1)
    cx = pr.centerx
    pygame.draw.circle(panel, (44, 92, 60), (cx, pr.y + int(ph * 0.32)),
                       max(4, int(pw * 0.17)))
    pygame.draw.polygon(panel, (38, 82, 54),
                        [(cx - pw // 3, pr.bottom - 2),
                         (cx - pw // 4, pr.y + int(ph * 0.56)),
                         (cx + pw // 4, pr.y + int(ph * 0.56)),
                         (cx + pw // 3, pr.bottom - 2)])
    noimg = f_small.render("NO PHOTO", True, (34, 70, 46))
    panel.blit(noimg, (pr.centerx - noimg.get_width() // 2, pr.bottom - 10))
    stamp = f_small.render("DECEASED", True, (192, 66, 52))
    stamp = pygame.transform.rotate(stamp, 8)
    if stamp.get_width() <= pr.width + pad:
        panel.blit(stamp, (pr.centerx - stamp.get_width() // 2,
                           pr.bottom - stamp.get_height() - 2))

    fx = pr.right + pad
    fw = w - fx - pad
    label_w = max(f_small.size(label)[0] for label, _v in lines[1:]) + 3
    label_w = min(label_w, max(20, fw // 2))
    row_h = max(8, int(h * 0.088))
    reveal = max(0, int((t - 2600) / 20))
    used = 0
    hi = _k(t, 6200, 700)
    for row, (label, value) in enumerate(lines[1:]):
        if used >= reveal:
            break
        yy = body_y + row * row_h
        if yy + row_h > h - 14:
            break
        key_row = label in ("NAME", "STATUS")
        if key_row and hi > 0.02:
            band = pygame.Surface((fw + pad, row_h - 1), pygame.SRCALPHA)
            band.fill((44, 120, 64, int(90 * hi)))
            panel.blit(band, (fx - 2, yy - 1))
            if int(t // 120) % 2 == 0 and hi > 0.6:
                pygame.draw.rect(panel, (110, 220, 140),
                                 (fx - 2, yy - 1, fw + pad, row_h - 1), 1)
        lab_col = (150, 240, 176) if key_row and hi > 0.4 else (72, 126, 92)
        panel.blit(f_small.render(label, True, lab_col), (fx, yy))
        used += len(label) + 2
        avail = max(0, reveal - used)
        if avail:
            val = value[:avail]
            maxw = fw - label_w
            while val and f_body.size(val)[0] > maxw:
                val = val[:-1]
            col = (232, 102, 82) if label == "STATUS" else (122, 230, 158)
            if key_row and hi > 0.4:
                col = tuple(min(255, int(c + (255 - c) * 0.35 * hi)) for c in col)
            panel.blit(f_body.render(val, True, col), (fx + label_w, yy))
        used += len(value) + 4
        if label == "STATUS":
            pygame.draw.line(panel, (58, 30, 24),
                             (fx + label_w, yy + row_h - 3),
                             (fx + label_w + f_body.size(value)[0],
                              yy + row_h - 3), 1)
    # callsign: the anagram sorts into the dead man's name
    fy = h - pad - f_small.get_height()
    sort_k = _k(t, 4200, 2100)
    prefix = "CALLSIGN: "
    px = pad
    panel.blit(f_small.render(prefix, True, (58, 112, 76)), (px, fy))
    x0 = px + f_small.size(prefix)[0]
    avail = max(24, w - x0 - pad - (58 if w > 260 else 6))
    cell = max(3.0, min(float(f_small.size("M")[0] + 1),
                        avail / float(len(_CRT_SOURCE))))
    used_t = set()
    target_idx = []
    for ch in _CRT_SOURCE:
        for i, tc in enumerate(CRT_CALLSIGN):
            if i not in used_t and tc == ch:
                used_t.add(i)
                target_idx.append(i)
                break
        else:
            target_idx.append(0)
    for i, ch in enumerate(_CRT_SOURCE):
        if ch == " ":
            continue
        xs = x0 + i * cell
        xt = x0 + target_idx[i] * cell
        k = sort_k
        xx = xs + (xt - xs) * k
        yy = fy - int(math.sin(math.pi * k) * 7)
        col = (58 + int(140 * k), 112 + int(120 * k), 76 + int(90 * k))
        panel.blit(f_small.render(ch, True, col), (int(xx), int(yy)))
    if sort_k >= 0.999:
        match = f_small.render("MATCH", True, (230, 210, 120))
        mx = x0 + len(CRT_CALLSIGN) * cell + 6
        if mx + match.get_width() < w - pad - 4:
            panel.blit(match, (mx, fy))
    # moving scanline and the footer barcode
    sy = int((t * 0.035) % max(1, h))
    line = pygame.Surface((w, 1), pygame.SRCALPHA)
    line.fill((120, 230, 150, 26))
    panel.blit(line, (0, sy))
    if pad + f_small.size(prefix)[0] + len(CRT_CALLSIGN) * cell + 64 < w:
        for i in range(16):
            bx = w - pad - 46 + i * 3
            bh = 4 + (i * 37) % max(4, h // 7)
            pygame.draw.line(panel, (40, 96, 60), (bx, h - pad - bh),
                             (bx, h - pad), 1)
    scan = _SCAN_CACHE.get((w, h))
    if scan is None:
        scan = pygame.Surface((w, h), pygame.SRCALPHA)
        for yy in range(0, h, 3):
            pygame.draw.line(scan, (0, 0, 0, 34), (0, yy), (w, yy))
        _SCAN_CACHE[(w, h)] = scan
    panel.blit(scan, (0, 0))
    if (int(t // 90) % 7) == 0:
        panel.fill((14, 34, 20), (0, 0, w, h), special_flags=pygame.BLEND_ADD)
    clip = surface.get_clip()
    surface.set_clip(pygame.Rect(0, _w.SAFE_TOP, WIDTH, _w.FILM_H))
    surface.blit(panel, (x, y))
    pygame.draw.rect(surface, (26, 58, 38), (x, y, w, h), 1)
    surface.set_clip(clip)


def _quad_rect(r, center, hw, hh, zoff=0.0):
    pts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            q = _w.project_xy(r, (center[0] + sx * hw, center[1] + sy * hh,
                                  center[2] + zoff))
            if q is None:
                return None
            pts.append(q)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def _rig_terminal(r, fill=(-0.55, 0.45, -0.70), amb=0.20, dif=0.48, lamp=0.45,
                  crt=0.25, window=0.40):
    """Desk lamp far end (>= 2.8 m from his mark), green CRT, cold window
    spill; the directional term is a camera-side fill only."""
    from engine3d.core import Light, v_norm
    r.light = Light(direction=fill, ambient=amb, diffuse=dif, sky=0.05,
                    tint=(0.90, 0.95, 1.06))
    r.set_lights([
        {"pos": (-2.10, 1.30, 1.90), "color": (255, 190, 120),
         "intensity": lamp, "range": 5.0},
        {"pos": (-0.90, 1.30, 1.28), "color": (96, 186, 128),
         "intensity": crt, "range": 2.6},
        {"pos": (2.40, 1.95, 3.95), "kind": "spot",
         "dir": v_norm((-0.35, -0.30, -1.0)), "cone": 0.70,
         "color": (100, 132, 186), "intensity": window, "range": 6.5},
        {"pos": (0.66, 1.03, 1.45), "color": (255, 150, 70),
         "intensity": 0.12, "range": 1.2},
    ])


_CUSTOMS_RETURN_ROUTE = {}


def _customs_return_route():
    route = _CUSTOMS_RETURN_ROUTE.get("v")
    if route is None:
        route = _CUSTOMS_RETURN_ROUTE["v"] = _w.path(
            [(14.5, 18.5), (9.8, 9.6)])
    return route


def _customs_return_stage(t):
    hum = _w.hum(_BIRI)
    route = _customs_return_route()
    stride = _w.walk_stride(route.length, 0.60)
    g0, g1 = _w.walk_span(route.length, stride)
    g = g0 + (g1 - g0) * _w.travel(t, 700, 3200)
    pose, pos, yaw = _w.walk(
        hum, route, g, stride, speed=1.05,
        ground=lambda x, z: _w.height_at(x, z) - 0.04)
    pose["head_p"] = -2.0 - 3.0 * _w.ease5(t, 3000, 900)
    return pose, pos, yaw


def _customs_return(surface, t):
    """E1: the customs post at night, the frozen queue, Biribel walking back
    alone with the notebook.  Answers where we are before the terminal."""
    t = min(t, 4500)
    r, buf = _w.rend()
    r.fog, r.fog_start, r.fog_end = (10, 13, 18), 18.0, 110.0
    from engine3d.core import Light
    r.light = Light(direction=(-0.35, 0.70, -0.45), ambient=0.34,
                    diffuse=0.64, sky=0.12, tint=(0.86, 0.92, 1.06))
    r.set_lights([
        {"pos": (6.2, 1.60, 8.0), "color": (255, 198, 122),
         "intensity": 0.80, "range": 6.5},
        {"pos": (-4.4, 5.5, 7.6), "color": (255, 196, 120),
         "intensity": 0.65, "range": 9.0},
        {"pos": (4.4, 5.5, 7.6), "color": (255, 196, 120),
         "intensity": 0.65, "range": 9.0},
        # camera-side cold rim so the lone walker reads against the snow
        {"pos": (13.5, 3.0, 20.5), "color": (120, 150, 200),
         "intensity": 0.80, "range": 11.0},
    ])
    k = _k(t, 0, 4300)
    eye = (18.0 - 1.8 * k, 2.9 - 0.5 * k, 22.0 - 2.6 * k)
    _cam(r, t, eye, (-2.0 + 10.0 * k, 1.30, 11.0), 54,
         hh=0.010, seed=73)
    _w.night(r, buf, t, top=(5, 8, 15), bot=(18, 26, 42), stars=60,
             moon=(28, 0.30), sodium=(60, 40, 26), seed=73)
    _w.static_scene(r, "m6_customs_return")
    r.begin()
    _w.terrain(r, t, lights=False)
    _w.border_compound(r, t)
    # the hut's lit doorway, on the side the camera can see
    from engine3d.core import box as _box
    _w.add(r, _box(0.07, 1.95, 0.95, (255, 203, 109),
                   center=(8.92, 0.98, 9.4), emissive=True))
    _w.add(r, _box(0.14, 0.16, 1.15, (40, 40, 42),
                   center=(8.90, 2.03, 9.4)))
    r.add_sprite((9.02, 1.25, 9.4),
                 _fx.window_glow(_fx.SODIUM, 0.75, 0.9, 0.34),
                 layer=_fx.FX_LAYER)
    _w.static_end(r)
    pose, pos, yaw = _customs_return_stage(t)
    joints = _w.actor(r, _BIRI, pose, pos, yaw, t, seed=52, amp=0.35,
                      expression="neutral")
    hand = joints.get("lhand")
    if hand is not None:
        _notebook_prop(r, _local(hand, yaw, up=0.035), yaw, carry=True)
    _w.snow3d(r, t, seed=74, n=90, spread=20, height=14, speed=1.2)
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, 6309, "KRAP BORDER CUSTOMS // 04:10", t=t)


def _customs_terminal(surface, t):
    t = min(t, 7500)
    k = _k(t, 0, 6200)
    r, buf = _w.rend()
    r.fog, r.fog_start, r.fog_end = (10, 11, 10), 9.0, 26.0
    _rig_terminal(r, fill=(0.45, 0.50, -0.70), lamp=0.55)
    # push until the CRT is the frame, not a prop on a desk
    eye = (2.6 + (0.28 - 2.6) * k, 2.0 + (1.44 - 2.0) * k,
           -2.6 + (0.45 + 2.6) * k)
    tgt = (-0.9 + k * 0.1, 1.30, 1.35)
    _cam(r, t, eye, tgt, 48 - k * 12, hh=0.006, seed=37)
    buf.fill((9, 9, 9))
    r.begin()
    crt = _w.terminal_office(r, t)
    rect = _quad_rect(r, crt, 0.34, 0.24, -0.02)
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, 6301, "", t=t)
    if rect:
        _crt_panel(surface, rect, t)


def _radio_variant():
    text = _shot_text()
    if "Route 12" in text:
        return 0           # Biribel, the leaf, the handset
    if "Three hundred" in text:
        return 1           # Vasile at his window
    if "You'd have done" in text:
        return 2           # Biribel, close, no answer
    return 3               # Vasile turns to the desk map


# Biribel stands off the front edge of the desk (z 1.15), the radio set at
# his right shoulder; the handset is in his radio-side hand so the cord drops
# straight to the set instead of crossing his chest.
_R_MARK = (0.55, 0.0, 0.86)
_R_YAW = -118.0
_R_JACK = (0.50, 1.00, 1.47)


def _head_point(pose, pos, yaw, right=0.0, up=0.0, fwd=0.0, key=_BIRI):
    """Point fixed to the head (head-centre local offsets, metres x scale)."""
    sc = _w.hum(key)._scale
    head = _joints(key, pose, pos, yaw)["head"]
    pt = math.radians(pose.get("spine", 0.0) + pose.get("head_p", 0.0))
    u = (up * math.cos(pt) - fwd * math.sin(pt)) * sc
    f = (fwd * math.cos(pt) + up * math.sin(pt)) * sc
    hy = yaw + pose.get("twist", 0.0) + pose.get("head_y", 0.0)
    return _local(head, hy, right=right * sc, up=u, fwd=f)


def _handset_pose_key(key, pose, pos, yaw, pole=None):
    """Right hand holding the handset to the right ear -> (pose, ear, mouth)."""
    ear = _head_point(pose, pos, yaw, right=0.140, up=0.000, fwd=0.010, key=key)
    mouth = _head_point(pose, pos, yaw, right=0.118, up=-0.125, fwd=0.095, key=key)
    grip = _head_point(pose, pos, yaw, right=0.175, up=-0.055, fwd=0.045, key=key)
    return _hand(key, pose, pos, yaw, "r", grip, pole), ear, mouth


def _handset_pose(pose, pos, yaw):
    return _handset_pose_key(_BIRI, pose, pos, yaw)


def radio_stage(variant, t):
    """Biribel on the radio at the terminal desk -> ([cast], handset) for
    ``m6_radio_vasile`` variants 0/2, ``"maru"`` and ``"silence"``."""
    if variant == "silence":
        k = _w.ease5(t, 400, 1500)
        spine, head_p, look, expr, seed = 6 + 2 * k, 6 + 7 * k, \
            (-0.7, 0.9, -1.3), "sad", 45
    elif variant == "maru":
        k = _w.ease5(t, 1300, 1000)
        spine, head_p, look, expr, seed = 7 + 3 * k, 4 + 9 * k, (-0.9, 1.1, -1.4), \
            "worried", 44
    elif variant == 1:
        k = _w.ease5(t, 3800, 1400)
        spine, head_p, look, expr, seed = 5 + 3 * k, 2 + 11 * k, (-1.3, 1.45, -0.9), \
            "stern", 40
    else:
        k = _w.ease5(t, 2600, 900)
        spine, head_p, look, expr, seed = 6, 1 + 4 * k, (-1.1, 1.55, -1.0), \
            "stern", 42
    p = _b_base(spine)
    p["twist"], p["head_y"] = _look(_R_MARK, _R_YAW, look, twist_max=12, head_max=28)
    p["head_p"] = head_p
    p["lsh_p"], p["lel"] = 8, 22
    p, ear, mouth = _handset_pose(p, _R_MARK, _R_YAW)
    hand = _joints(_BIRI, p, _R_MARK, _R_YAW)["rhand"]
    return [_cast(_BIRI, p, _R_MARK, _R_YAW, seed, expr, 0.35)], \
        {"ear": ear, "mouth": mouth, "hand": hand}


def _draw_handset(r, hs, joints, yaw, jack=_R_JACK, cord=True):
    """Handset follows the drawn hand; a coiled cord sags to the set."""
    from engine3d.core import Mesh, box, m_mul, rot_x, rot_y
    d = [joints["rhand"][i] - hs["hand"][i] for i in range(3)]
    ear = tuple(hs["ear"][i] + d[i] for i in range(3))
    mouth = tuple(hs["mouth"][i] + d[i] for i in range(3))
    ax = [mouth[i] - ear[i] for i in range(3)]
    ln = math.sqrt(sum(a * a for a in ax)) or 1.0
    ya = math.degrees(math.atan2(ax[0], ax[2]))
    pa = -math.degrees(math.asin(max(-1.0, min(1.0, ax[1] / ln))))
    col, cap = (64, 70, 52), (48, 52, 40)
    m = Mesh()
    m.add(box(0.040, 0.034, ln, col))
    m.add(box(0.066, 0.056, 0.072, cap), t=(0.0, 0.0, -ln / 2))
    m.add(box(0.066, 0.056, 0.072, cap), t=(0.0, 0.0, ln / 2))
    out = Mesh()
    out.add(m, m=m_mul(rot_y(ya), rot_x(pa)), t=_lerp3(ear, mouth, 0.5))
    _w.add(r, out)
    if cord:
        side = (math.cos(math.radians(yaw)), -math.sin(math.radians(yaw)))
        n = 19
        for i in range(1, n):
            u = i / float(n)
            p = _lerp3(mouth, jack, u)
            bell = 4 * u * (1 - u)
            c = (p[0] + side[0] * 0.09 * bell, p[1] - 0.17 * bell,
                 p[2] + side[1] * 0.09 * bell)
            _w.add(r, box(0.0135, 0.0135, 0.0135, (16, 16, 18), center=c))


_RADIO_CAMS = {
    0: ((-0.80, 1.74, -0.75), (0.47, 1.66, 0.82), 40, 0.006),
    1: ((-1.10, 1.52, -2.00), (0.45, 1.36, 0.95), 44, 0.008),
    # Biribel, close, on "You'd have done the same."
    2: ((-1.02, 1.60, -1.22), (0.48, 1.52, 0.84), 38, 0.006),
    "silence": ((-0.88, 1.60, -1.08), (0.48, 1.48, 0.84), 37, 0.005),
    "maru": ((-0.02, 1.66, -1.26), (0.47, 1.62, 0.85), 40, 0.007),
}
_RADIO_FILL = {0: (-0.62, 0.42, -0.66), 1: (-0.70, 0.40, -0.55),
               2: (-0.40, 0.50, -0.75), "silence": (-0.35, 0.45, -0.80),
               "maru": (-0.30, 0.45, -0.85)}


def _radio_take(surface, t, variant, seed, tag):
    r, buf = _w.rend()
    r.fog, r.fog_start, r.fog_end = (11, 12, 11), 10.0, 28.0
    _rig_terminal(r, fill=_RADIO_FILL[variant])
    eye, tgt, fov, hh = _RADIO_CAMS[variant]
    if variant == 1:
        eye = _lerp3(eye, tgt, 0.12 * _k(t, 0, 6600))
    _cam(r, t, eye, tgt, fov, hh=hh, seed=seed)
    buf.fill((9, 9, 9))
    r.begin()
    from engine3d.rig import mouth_flap
    live = _w.talking("VASILE") or _w.talking("MARU")
    voice = mouth_flap(int(t), seed + 5) * (0.9 if live else 0.15)
    _w.terminal_office(r, t, handset=False, voice=voice)
    cast, hs = radio_stage(variant, t)
    for a in cast:
        j = _w.actor(r, a["key"], a["pose"], a["pos"], a["yaw"], t,
                     seed=a["seed"], amp=a["amp"], expression=a["expr"])
        _draw_handset(r, hs, j, a["yaw"])
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, seed, tag, t=t)


def _route12_leaf(r, center, yaw=8.0, accent=(170, 42, 38)):
    """The Route 12 movement order: a pale leaf with a red code block and a
    circled authorization number.  Flat on the desk."""
    from engine3d.core import Mesh, box, rot_y
    m = Mesh()
    m.add(box(0.30, 0.004, 0.21, (208, 203, 190)))
    for i in range(4):
        m.add(box(0.17, 0.003, 0.008, (126, 120, 108)),
              t=(-0.03, 0.004, -0.062 + i * 0.034))
    # the authorization block, circled
    for dx, dz, w, d in ((0.06, -0.050, 0.11, 0.006),
                         (0.06, 0.012, 0.11, 0.006),
                         (0.010, -0.019, 0.006, 0.068),
                         (0.112, -0.019, 0.006, 0.068)):
        m.add(box(w, 0.005, d, accent), t=(dx, 0.005, dz))
    m.add(box(0.085, 0.004, 0.022, (196, 64, 52)),
          t=(0.06, 0.006, -0.019))
    out = Mesh()
    out.add(m, m=rot_y(yaw), t=center)
    _w.add(r, out)


def _notebook_prop(r, pos, yaw, cover=(26, 28, 32), carry=True):
    """The black notebook; ``carry`` holds it flat in a hand, otherwise it
    lies open at reading height."""
    from engine3d.core import Mesh, box, m_mul, rot_x, rot_y
    m = Mesh()
    m.add(box(0.16, 0.022, 0.22, cover))
    m.add(box(0.148, 0.006, 0.205, (198, 194, 182)), t=(0, 0.012, 0))
    for i in range(3):
        m.add(box(0.004, 0.002, 0.20, (120, 116, 106)),
              t=(0.055, 0.016, 0))
    m.add(box(0.014, 0.026, 0.225, (116, 30, 30)))
    out = Mesh()
    rot = m_mul(rot_y(yaw), rot_x(-62.0 if carry else -18.0))
    out.add(m, m=rot, t=pos)
    _w.add(r, out)


def _desk_phone(r, center):
    """Bakelite desk set in Vasile's office -> the cord jack position."""
    from engine3d.core import Mesh, box
    m = Mesh()
    m.add(box(0.26, 0.09, 0.20, (34, 32, 30), center=center))
    m.add(box(0.22, 0.025, 0.05, (52, 48, 42),
              center=(center[0], center[1] + 0.06, center[2])))
    for sx in (-1, 1):
        m.add(box(0.05, 0.035, 0.06, (24, 22, 20),
                  center=(center[0] + sx * 0.10, center[1] + 0.075, center[2])))
    _w.add(r, m)
    return (center[0] + 0.12, center[1] + 0.03, center[2] - 0.06)


def _desk_map(r, t):
    """Vasile's operations map; the mansion is circled from 4.5 s."""
    from engine3d.core import Mesh, box
    m = Mesh()
    m.add(box(0.46, 0.004, 0.32, (196, 190, 172), center=(0.18, 0.906, 1.43)))
    for i in range(5):
        m.add(box(0.40, 0.003, 0.006, (140, 132, 118),
                  center=(0.18, 0.910, 1.31 + i * 0.055)))
    for i in range(3):
        m.add(box(0.006, 0.003, 0.26, (140, 132, 118),
                  center=(-0.01 + i * 0.18, 0.910, 1.43)))
    _w.add(r, m)
    if t >= 4500:
        k = _w.ease5(t, 4500, 500)
        rad = 0.035 + 0.015 * k
        for dx, dz, w, d in ((rad, 0, 0.004, rad * 2),
                             (-rad, 0, 0.004, rad * 2),
                             (0, rad, rad * 2, 0.004),
                             (0, -rad, rad * 2, 0.004)):
            _w.add(r, box(max(0.004, w), 0.004, max(0.004, d),
                          (204, 54, 42), center=(0.20 + dx, 0.914, 1.40 + dz)))


def _vasile_office_pose(t, line):
    h = _w.hum("vasile")
    turn = _w.ease5(t, 2200, 1500) if line == 3 else 0.0
    stand = (0.82, 0.0, 2.95)
    desk = (0.32, 0.0, 2.34)
    pos = tuple(stand[i] + (desk[i] - stand[i]) * turn for i in range(3))
    # line 2: his back is to the window, his face to the lens
    yaw_win = _w.yaw_to(pos, (0.2, 0.0, -2.0))
    yaw_desk = _w.yaw_to(pos, (0.2, 0.0, 1.4))
    yaw = yaw_win + (yaw_desk - yaw_win) * turn
    pose = dict(spine=2 + 14 * turn, lsh_p=8, lsh_r=6, lel=14,
                rsh_p=12, rsh_r=8, rel=18)
    pose["head_p"] = -1.0 + 24.0 * turn
    pose["head_y"] = -10.0 * turn
    # still on the line: the handset stays at his ear while the free hand
    # comes down flat on the desk by the near edge
    # the phone elbow opens out as he leans, so it clears his chest
    pose, ear, mouth = _handset_pose_key(
        "vasile", pose, pos, yaw, _lerp3((0.45, -1.0, -0.35), _OUT["r"], turn))
    if turn > 0.0:
        rest = _joints("vasile", pose, pos, yaw)["lhand"]
        pose = _hand("vasile", pose, pos, yaw, "l",
                     _lerp3(rest, (0.46, 0.92, 1.98), turn), _OUT["l"])
    joints = _joints("vasile", pose, pos, yaw)
    hs = {"ear": ear, "mouth": mouth, "hand": joints["rhand"]}
    return h, pose, pos, yaw, hs


def _vasile_office_take(surface, t, line):
    r, buf = _w.rend()
    r.fog, r.fog_start, r.fog_end = (12, 11, 11), 10.0, 26.0
    from engine3d.core import Light
    r.light = Light(direction=(0.30, 0.55, 0.38), ambient=0.36, diffuse=0.85,
                    tint=(1.12, 1.00, 0.84))
    r.set_lights([
        {"pos": (1.00, 1.00, 1.10), "color": (255, 190, 120),
         "intensity": 0.85, "range": 4.6},
        {"pos": (2.80, 1.80, 4.40), "color": (86, 110, 160),
         "intensity": 0.65, "range": 7.0},
        {"pos": (0.20, 1.30, -0.60), "color": (90, 112, 150),
         "intensity": 0.50, "range": 2.2},
        {"pos": (2.30, 1.55, -1.20), "color": (150, 168, 198),
         "intensity": 0.40, "range": 3.2},
    ])
    turn = _w.ease5(t, 2200, 1500) if line == 3 else 0.0
    eye = _lerp3((2.70, 1.72, -2.35), (2.60, 1.75, -2.20), turn)
    tgt = _lerp3((0.25, 1.36, 2.85), (0.25, 1.30, 1.60), turn)
    _cam(r, t, eye, tgt, 42 + 4 * turn, hh=0.008, seed=38)
    buf.fill((8, 8, 8))
    r.begin()
    _w.vasile_office(r, t)
    jack = _desk_phone(r, (1.38, 0.90, 1.28))
    _desk_map(r, t)
    h, pose, pos, yaw, hs = _vasile_office_pose(t, line)
    joints = _w.actor(r, "vasile", pose, pos, yaw, t, seed=39, amp=0.22,
                      expression="stern" if line == 1 else "neutral")
    if hs is not None:
        _draw_handset(r, hs, joints, yaw, jack=jack)
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, 6304 + line, "GUARD HQ // VASILE'S OFFICE", t=t)


def _radio_insert(surface, t):
    """E3 insert: the Route 12 leaf, the circled code, a hand lifting the
    handset, the GUARD HQ channel lamp lighting."""
    r, buf = _w.rend()
    r.fog, r.fog_start, r.fog_end = (11, 12, 11), 10.0, 26.0
    _rig_terminal(r, fill=(-0.58, 0.46, -0.68), lamp=0.65)
    k = _k(t, 0, 1100)
    eye = (1.45 - k * 0.10, 1.40 + k * 0.02, 0.80 - k * 0.05)
    _cam(r, t, eye, (0.18, 0.98, 1.55), 36, hh=0.004, seed=46)
    buf.fill((8, 9, 8))
    r.begin()
    _w.terminal_office(r, t, handset=True)
    _route12_leaf(r, (0.08, 0.886, 1.55), yaw=6)
    # the handset hand comes up over the first second
    from engine3d.core import Mesh, box
    hx = 0.60 - 0.04 * k
    hy = 1.20 + 0.16 * k
    hz = 1.60 - 0.14 * k
    m = Mesh()
    m.add(box(0.095, 0.055, 0.075, (128, 102, 84), center=(hx, hy, hz)))
    m.add(box(0.11, 0.07, 0.09, (42, 44, 42),
              center=(hx - 0.02, hy - 0.06, hz + 0.02)))
    _w.add(r, m)
    # channel lamps on the set: GUARD HQ red, OPEN dark
    _w.add(r, box(0.036, 0.028, 0.012, (222, 82, 58),
                  center=(0.60, 1.18, 1.482), emissive=True))
    _w.add(r, box(0.036, 0.028, 0.012, (36, 52, 44),
                  center=(0.90, 1.18, 1.482), emissive=False))
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, 6310, "THE CALL // ROUTE 12", t=t)


def _maru_insert(surface, t):
    """The second channel opens: OPEN CHANNEL lamp, needle jump."""
    r, buf = _w.rend()
    r.fog, r.fog_start, r.fog_end = (11, 12, 11), 10.0, 24.0
    _rig_terminal(r, fill=(-0.45, 0.44, -0.78))
    _cam(r, t, (1.32, 1.18, 1.02), (0.72, 1.04, 1.55), 34, hh=0.004, seed=47)
    buf.fill((8, 9, 8))
    r.begin()
    from engine3d.core import box
    _w.terminal_office(r, t, handset=True, voice=1.0)
    _w.add(r, box(0.036, 0.028, 0.012, (222, 82, 58),
                  center=(0.60, 1.18, 1.482), emissive=True))
    on = t >= 250
    if on:
        col = (70, 218, 132) if (int(t // 110) % 5) else (36, 92, 60)
    else:
        col = (36, 52, 44)
    _w.add(r, box(0.036, 0.028, 0.012, col,
                  center=(0.90, 1.18, 1.482), emissive=on))
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, 6311, "MARU // OPEN CHANNEL", t=t)


def _radio_vasile(surface, t):
    variant = _radio_variant()
    if variant == 0 and t < 1200:
        _radio_insert(surface, t)
        return
    if variant in (1, 3):
        _vasile_office_take(surface, t, variant)
        return
    _radio_take(surface, t, variant, 6300 + variant, "")


def _radio_silence(surface, t):
    """E7: he does not answer.  The silence is the beat."""
    _radio_take(surface, t, "silence", 6308, "THE CALL // NO ANSWER")


def _radio_maru(surface, t):
    """E8: the second channel opens, then Maru on the voice line."""
    if t < 900:
        _maru_insert(surface, t)
        return
    _radio_take(surface, t, "maru", 6306, "MARU // OPEN CHANNEL")


def _cut_line(surface, t):
    """E9: the switch, the dead channel lamp, the notebook going inside the
    coat.  The choice, on screen, with no line."""
    if t < 1500:
        r, buf = _w.rend()
        r.fog, r.fog_start, r.fog_end = (11, 12, 11), 10.0, 24.0
        _rig_terminal(r, fill=(-0.55, 0.44, -0.72))
        _cam(r, t, (1.30, 1.20, 0.98), (0.70, 1.04, 1.55), 34,
             hh=0.004, seed=48)
        buf.fill((8, 9, 8))
        r.begin()
        from engine3d.core import Mesh, box
        _w.terminal_office(r, t, handset=True, voice=0.0)
        on = t < 650
        _w.add(r, box(0.036, 0.028, 0.012,
                      (222, 82, 58) if on else (34, 40, 38),
                      center=(0.60, 1.18, 1.482), emissive=on))
        _w.add(r, box(0.036, 0.028, 0.012, (36, 52, 44),
                      center=(0.90, 1.18, 1.482), emissive=False))
        push = _w.ease5(t, 320, 280)
        m = Mesh()
        m.add(box(0.055, 0.032, 0.048, (128, 102, 84),
                  center=(0.51, 1.00 - 0.015 * push, 1.49)))
        m.add(box(0.07, 0.05, 0.06, (42, 44, 42),
                  center=(0.56, 0.96 - 0.015 * push, 1.49)))
        _w.add(r, m)
        r.flush(buf)
        _w.present(surface, buf)
        _w.finish(surface, 6312, "THE CALL // CUT", t=t)
        return
    r, buf = _w.rend()
    r.fog, r.fog_start, r.fog_end = (12, 12, 11), 10.0, 28.0
    _rig_terminal(r, fill=(-0.60, 0.42, -0.70), lamp=0.45)
    _cam(r, t, (-1.25, 1.62, -1.55), (0.42, 1.28, 0.88), 38,
         hh=0.006, seed=49)
    buf.fill((8, 8, 8))
    r.begin()
    _w.terminal_office(r, t, handset=False)
    pose = _b_base(6)
    pose["head_p"] = 12
    nb = _local(_R_MARK, _R_YAW, up=1.12, fwd=0.30)
    for side, sgn in (("l", -1), ("r", 1)):
        pose = _hand(_BIRI, pose, _R_MARK, _R_YAW, side,
                     _local(nb, _R_YAW, right=sgn * 0.072))
    _w.actor(r, _BIRI, pose, _R_MARK, _R_YAW, t, seed=50, amp=0.25,
             expression="sad")
    _notebook_prop(r, nb, _R_YAW, carry=False)
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, 6313, "THE CALL // CUT", t=t)


_PICKUP_ROUTE = {}
_BENCH = {}


def _pickup_route():
    route = _PICKUP_ROUTE.get("v")
    if route is None:
        route = _PICKUP_ROUTE["v"] = _w.path([(9.5, 17.0), (-0.75, 17.3)])
    return route


def _bench_seat(key, x, z, floor_y, upper, yaw=90.0):
    """Seated rig on a bench: soles on the cabin floor at (x, z), thighs on a
    seat top ``HELI_BENCH_H`` above it."""
    h = _w.hum(key)
    pose = _w.sit_pose(h, _w.HELI_BENCH_H, upper)
    a = _w.ankles(h, pose, (0.0, floor_y, 0.0), yaw)
    dx = 0.5 * (a["l"][0] + a["r"][0])
    dz = 0.5 * (a["l"][2] + a["r"][2])
    return pose, (x - dx, floor_y, z - dz)


def _door_jump_seat(r, L):
    """Fold-down seat by the door for H2 only: the insertion's door sitter
    would clip it, so the airframe does not carry it."""
    from engine3d.core import Mesh
    m = Mesh()
    for name, lohi in _w.solids("heli_cabin").items():
        _w._mesh_solid(m, lohi, (22, 24, 27) if "cushion" in name
                       else (40, 43, 47))
    m.verts = [L(*v) for v in m.verts]
    _w.add(r, m, bias=0.4)


def _north_ridge(r):
    """The dark hills north of the border, on the away-turn."""
    from engine3d.core import prism
    for i, (x, z, w, h, d) in enumerate(((38, -44, 42, 21, 26),
                                        (78, -54, 50, 28, 30),
                                        (114, -40, 36, 18, 24))):
        prof = [(x - w, 0.0), (x - w * 0.58, h * 0.30),
                (x - w * 0.26, h * 0.66), (x - w * 0.04, h * 0.90),
                (x + w * 0.14, h), (x + w * 0.42, h * 0.62),
                (x + w * 0.74, h * 0.26), (x + w, 0.0)]
        _w.add(r, prism(prof, d, (14 + i, 16 + i, 23 + i), z0=z - d / 2))


def _turn_ridge(r):
    """Soft dark hills north-west of the border for the away-turn."""
    from engine3d.core import prism
    for i, (x, z, w, h, d) in enumerate(((-30, -30, 38, 17, 24),
                                        (-72, -36, 46, 24, 28),
                                        (-112, -28, 34, 15, 22))):
        n = 14
        prof = []
        for j in range(n + 1):
            u = j / n
            hh = h * math.sin(math.pi * u) ** 1.2 * (
                0.78 + 0.22 * math.sin(u * 17.0 + i * 2.3))
            prof.append((x - w + 2.0 * w * u, hh))
        _w.add(r, prism(prof, d, (26 + 2 * i, 32 + 2 * i, 50 + 3 * i),
                        z0=z - d / 2))


def _heli_pickup(surface, t):
    """H1: the Huey comes down into the lot; Biribel runs under the disc."""
    t = min(t, 4600)
    r, buf = _w.rend()
    r.fog, r.fog_start, r.fog_end = (11, 14, 22), 24.0, 150.0
    heli, hyaw, hbank, hpitch = heli_at("m6_helicopter", t)
    L = _w.heli_xform(heli, hyaw, hbank, hpitch)
    from engine3d.core import Light
    r.light = Light(direction=(-0.30, 0.55, -0.55), ambient=0.23,
                    diffuse=0.50, sky=0.08, tint=(0.80, 0.88, 1.06))
    # Biribel runs west under the rotor; the camera trails him.
    hum = _w.hum(_BIRI)
    route = _pickup_route()
    stride = _w.walk_stride(route.length, 0.92)
    g0, g1 = _w.walk_span(route.length, stride)
    run = _w.travel(t, 500, 3000)
    g = g0 + (g1 - g0) * run
    pose, pos, yaw = _w.walk(
        hum, route, g, stride, speed=2.2,
        ground=lambda x, z: _w.height_at(x, z) - 0.03)
    pose["spine"] = 9 + 7 * run
    pose["head_p"] = -4
    climb = _w.ease5(t, 3600, 700)
    if climb > 0.0:
        pose["lhip_p"] = -20.0 * climb
        pose["lkn"] = 58.0 * climb
        pose["rsh_p"] = 64.0 * climb
        pose["rel"] = 20.0
        pose["spine"] = 9 + 5 * climb
        pose["lift"] = 0.24 * climb
    r.set_lights([
        {"pos": (6.2, 1.60, 8.0), "color": (255, 198, 122),
         "intensity": 0.60, "range": 6.0},
        {"pos": (heli[0] + 1.2, heli[1] + 1.2, heli[2]),
         "color": (255, 88, 60), "intensity": 0.45, "range": 2.4},
        {"pos": (17.0, 4.0, 21.0), "color": (120, 150, 200),
         "intensity": 0.60, "range": 14.0},
        # moon rim on the airframe so it separates from the night
        {"pos": (heli[0] - 5.0, heli[1] + 5.0, heli[2] - 4.0),
         "color": (150, 180, 230), "intensity": 2.2, "range": 14.0},
        # cold key and amber kicker on Biribel so the runner reads against
        # the dark airframe
        {"pos": (pos[0] + 2.2, pos[1] + 2.4, pos[2] + 3.0),
         "color": (176, 200, 240), "intensity": 1.5, "range": 6.5},
        {"pos": (pos[0] - 1.6, pos[1] + 1.4, pos[2] + 1.2),
         "color": (255, 176, 104), "intensity": 0.8, "range": 4.0},
        # nose light: a cold spot raking the snow under the disc
        {"pos": L(0.0, 0.95, 3.40), "kind": "spot",
         "dir": (0.0, -0.94, 0.34), "cone": 0.72,
         "color": (255, 240, 200), "intensity": 1.4, "range": 13.0},
    ])
    descend = _w.ease5(t, 0, 3200)
    eye = (16.0 - 2.0 * run, 2.8 - 0.4 * run, 23.0 - 1.0 * run)
    tgt = (-1.0 + 0.5 * run, 1.3 + 6.6 * (1.0 - descend), 15.5)
    _cam(r, t, eye, tgt, 60, hh=0.014, seed=74,
         roll=0.35 * math.sin(t * 0.0011))
    _w.night(r, buf, t, top=(5, 8, 15), bot=(20, 27, 44), stars=54,
             moon=(26, 0.28), sodium=(62, 40, 26), seed=75, star_cut=0.42)
    _w.static_scene(r, "m6_heli_pickup")
    r.begin()
    _w.terrain(r, t, lights=False)
    _w.border_compound(r, t)
    _w.static_end(r)
    _w.helicopter(r, t, heli, yaw=hyaw, rotor_speed=0.95, bank=hbank,
                  pitch=hpitch, blur=0.6)
    r.add_sprite(L(0.0, 0.98, 3.52),
                 _fx.glow((255, 242, 210), 0.42, t, seed=90,
                          intensity=1.0), layer=_fx.FX_LAYER)
    joints = _w.actor(r, _BIRI, pose, pos, yaw, t, seed=76, amp=0.32,
                      expression="stern")
    hand = joints.get("lhand")
    if hand is not None:
        _notebook_prop(r, _local(hand, yaw, up=0.035), yaw, carry=True)
    # rotor wash on the snow: haze, motes and radial streaks
    ground = _w.height_at(heli[0], heli[2]) + 0.35
    down = (heli[0], ground, heli[2])
    r.add_sprite(down, _fx.haze((176, 190, 212), 4.8, t, seed=78,
                                intensity=0.20), layer=_fx.FX_LAYER)
    r.add_sprite(down, _fx.dust_motes(t, seed=78, count=40,
                                      spread_m=(4.2, 1.0),
                                      col=(190, 202, 220)),
                 layer=_fx.FX_LAYER)
    for i in range(14):
        u, v = _w._u(i, 78, 1), _w._u(i, 78, 2)
        a = u * 6.283
        rad = 0.5 + v * 4.6
        x = heli[0] + math.cos(a) * rad
        z = heli[2] + math.sin(a) * rad
        r.add_line3d((x, ground + 0.15, z),
                     (x + math.cos(a) * 0.9, ground + 0.45,
                      z + math.sin(a) * 0.9), (92, 104, 128), 1, layer=4)
    _w.snow3d(r, t, seed=79, n=58, spread=22, height=15, speed=0.9)
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, 6314, "KRAP BORDER CUSTOMS // 04:12", t=t)


def _in_cabin(pos, yaw, bank, pitch):
    """Test for world points inside the airframe's cabin pod, so snow never
    draws indoors.  Inverts heli_xform: undo yaw, bank, then pitch."""
    from engine3d.core import m_apply, rot_x, rot_y, rot_z

    def inside(p):
        v = m_apply(rot_y(-yaw), (p[0] - pos[0], p[1] - pos[1], p[2] - pos[2]))
        v = m_apply(rot_z(-bank), v)
        v = m_apply(rot_x(-pitch), v)
        return (abs(v[0]) < 1.22 and _w.HELI_FLOOR_Y < v[1] < _w.HELI_ROOF_Y
                and -1.52 < v[2] < 1.92)
    return inside


def _heli_cabin(surface, t):
    """H2: inside the door. Biribel seated, the capital behind him, Maru
    at the controls up front, the door sliding shut on the lights."""
    t = min(t, 8200)
    r, buf = _w.rend()
    r.fog, r.fog_start, r.fog_end = (10, 12, 18), 18.0, 140.0
    heli, hyaw, hbank, hpitch = heli_at("m6_helicopter", t)
    L = _w.heli_xform(heli, hyaw, hbank, hpitch)
    open_k = 1.0 - _w.ease5(t, 6600, 900)
    from engine3d.core import Light
    r.light = Light(direction=(0.42, 0.38, -0.55), ambient=0.32,
                    diffuse=0.60, sky=0.05, tint=(1.02, 0.92, 0.84))
    r.set_lights([
        {"pos": L(-0.2, 1.85, 0.4), "color": (255, 76, 50),
         "intensity": 0.55, "range": 2.1},
        {"pos": L(0.6, 1.25, -0.7), "color": (70, 190, 130),
         "intensity": 0.30, "range": 1.6},
        {"pos": L(-0.9, 1.60, -0.8), "color": (140, 160, 190),
         "intensity": 0.45, "range": 2.6},
    ])
    # Biribel has his back to the open door, so the capital's lights sit
    # behind him; Maru flies from the right-hand seat ahead of him.
    pose, root = _bench_seat(
        _BIRI, 0.28, 0.45, 0.62,
        dict(spine=4, head_p=1, lsh_p=12, lel=26, rsh_p=10, rel=24), yaw=-90.0)
    seat = L(*root)
    yaw = hyaw - 90.0
    look_out = L(7.0, 1.3, 4.0)          # over his shoulder, out the door
    look_front = L(-2.0, 1.5, 0.5)       # back toward the lens
    _ppose, proot = _w.heli_pilot()
    phead = (proot[0], 1.92, proot[2] + 0.10)
    look_at = (look_out if 5600 < t < 6900
               else (L(*phead) if t >= 6900 else look_front))
    pose["twist"], pose["head_y"] = _look(seat, yaw, look_at)
    pose["head_p"] = 1.0 if t > 6400 else -4.0
    # she checks over her shoulder once the door is shut
    glance = _w.ease5(t, 7000, 500)
    tw, hy = _look(proot, 0.0, (root[0], 1.90, root[2]))
    pilot = (tw * glance, hy * glance)
    eye = L(-0.80, 1.86, -1.30)
    tgt = L(0.30, 1.48, 1.30)
    _cam(r, t, eye, tgt, 72, hh=0.008, seed=80)
    _w.night(r, buf, t, top=(5, 7, 14), bot=(22, 24, 40), stars=40,
             moon=(-8, 11.0), sodium=(96, 52, 28), seed=81, star_cut=0.45)
    _w.static_scene(r, "m6_heli_cabin")
    r.begin()
    _w.capital(r, t)
    _north_ridge(r)
    _w.static_end(r)
    _w.helicopter(r, t, heli, yaw=hyaw, rotor_speed=0.85, bank=hbank,
                  pitch=hpitch, door=open_k, blur=0.5, pilot=pilot)
    # the capital's lights, seen through the open door behind him
    r.add_sprite(L(8.0, 1.1, 6.0),
                 _fx.window_glow(_fx.SODIUM, 6.0, 2.2, 0.12),
                 layer=_fx.FX_LAYER)
    r.add_sprite(L(10.0, 0.7, 8.0),
                 _fx.window_glow(_fx.SODIUM, 9.0, 1.8, 0.08),
                 layer=_fx.FX_LAYER)
    for i in range(7):
        r.add_sprite(L(12.0 + (i % 3) * 1.2, 0.7 + (i % 4) * 0.45,
                       5.0 + (i * 1.7) % 6.0),
                     _fx.glow(_fx.SODIUM_PALE, 0.22, t, seed=91 + i,
                              intensity=0.45),
                     layer=_fx.FX_LAYER)
    _door_jump_seat(r, L)
    _w.actor(r, _BIRI, pose, seat, yaw, t, seed=82, amp=0.22,
             expression="sad" if t > 5200 else "neutral")
    _notebook_prop(r, _local(seat, yaw, up=1.02, fwd=0.33), yaw,
                   carry=False)
    _w.snow3d(r, t, seed=84, n=30, spread=8, height=6, speed=1.2,
              skip=_in_cabin(heli, hyaw, hbank, hpitch), depth=True)
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, 6315, "EN ROUTE // KRAP BORDER", t=t)


def _heli_turn(surface, t):
    """H3: exterior from the east. Capital low on the left, dark hills on
    the right; the nose swings from the one to the other and the lights
    shrink into the dark."""
    t = min(t, 12000)
    r, buf = _w.rend()
    r.fog, r.fog_start, r.fog_end = (11, 13, 21), 70.0, 260.0
    heli, hyaw, hbank, hpitch = heli_at("m6_helicopter", t)
    q = _w.travel(t, 8200, 3800)
    lift = heli_at("m6_helicopter", 8200)[0]
    _rig_insert(r, amb=0.26, dif=0.50, fill=(0.40, 0.55, -0.45),
                bounce={"pos": (heli[0] + 3.0, heli[1] - 4.0, heli[2] + 4.0),
                        "color": (255, 176, 112), "intensity": 0.95,
                        "range": 20.0})
    eye = (lift[0] + 48.0, lift[1] + 7.0 + 3.0 * q, lift[2] + 11.0)
    anchor = (lift[0] - 10.0, lift[1] + 6.0, lift[2] - 4.0)
    f = 0.55
    tgt = tuple(anchor[i] * (1.0 - f) + heli[i] * f for i in range(3))
    _cam(r, t, eye, tgt, 50, hh=0.012, seed=45,
         roll=-0.16 * math.sin(math.pi * q))
    _w.night(r, buf, t, top=(5, 7, 14), bot=(22, 24, 40), stars=64,
             moon=(-8, 11.0), sodium=(96, 52, 28), seed=46, star_cut=0.35)
    _w.static_scene(r, "m6_heli_turn")
    r.begin()
    _w.terrain(r, t, lights=False)
    _w.border_compound(r, t, warm=0.35)
    _w.capital(r, t, dx=-60.0, dz=-10.0)
    _w.static_end(r)
    _w.helicopter(r, t, heli, yaw=hyaw, rotor_speed=0.8,
                  bank=hbank, pitch=hpitch, blur=0.55)
    # at this range the stock nav lights are sub-pixel: bigger strobes so
    # the airframe still reads as it shrinks into the dark
    L = _w.heli_xform(heli, hyaw, hbank, hpitch)
    r.add_sprite(L(0.0, 2.66, -1.62),
                 _fx.beacon((255, 40, 32), 0.9, t, period_ms=1000.0,
                            phase=0.75, intensity=1.0), layer=_fx.FX_LAYER)
    r.add_sprite(L(0.08, 3.30, -8.16),
                 _fx.beacon((255, 248, 226), 0.7, t, period_ms=1200.0,
                            phase=0.25, intensity=0.9), layer=_fx.FX_LAYER)
    _w.snow3d(r, t, seed=47, n=56, spread=24, height=16, speed=1.0)
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, 6307, "THE LAST SIGNAL", t=t)


def _helicopter(surface, t):
    if t < 4600:
        _heli_pickup(surface, t)
    elif t < 8200:
        _heli_cabin(surface, t)
    else:
        _heli_turn(surface, t)


# ═══════════════════════════════════════════════════════════════════════════
# 2D fallbacks (complete scenes, used when engine3d declines)
# ═══════════════════════════════════════════════════════════════════════════
def _fb_gradient(surface, top, bot):
    area = surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_BOT - SCENE_TOP))
    h = area.get_height()
    for y in range(h):
        f = y / max(1, h - 1)
        area.fill(tuple(int(a + (b - a) * f) for a, b in zip(top, bot)),
                  (0, y, WIDTH, 1))


def _fb_snow(surface, t, seed=0, n=110):
    rng = random.Random(seed)
    clip = surface.get_clip()
    surface.set_clip(pygame.Rect(0, SCENE_TOP, WIDTH, _w.FILM_H))
    for i in range(n):
        u, v, s = rng.random(), rng.random(), rng.uniform(0.4, 2.4)
        x = int(u * WIDTH)
        y = int(SCENE_TOP + ((v + t * 0.00004 * s) % 1.0) * _w.FILM_H)
        c = 140 + int(80 * u)
        surface.fill((c, c + 8, c + 20), (x, y, max(1, int(s)), max(1, int(s))))
    surface.set_clip(clip)


def _fb_hills(surface, y, moon=True):
    pygame.draw.rect(surface, (26, 32, 46), (0, y, WIDTH, SCENE_BOT - y))
    rng = random.Random(12)
    for layer in range(3):
        col = (24 + layer * 5, 30 + layer * 5, 44 + layer * 6)
        pts = [(0, y + 30)]
        for x in range(0, WIDTH + 120, 120):
            pts.append((x, y + 10 + layer * 16 - rng.randint(0, 26)))
        pts += [(WIDTH, y + 40), (WIDTH, SCENE_BOT), (0, SCENE_BOT)]
        pygame.draw.polygon(surface, col, pts)
    for i, x in enumerate((90, 300, 510, 720, 900)):
        pygame.draw.rect(surface, (18, 20, 28), (x, y + 40, 18, 24))
        pygame.draw.rect(surface, (226, 176, 104), (x + 5, y + 46, 4, 4))


def _fb_heli(surface, x, y, s, t, tilt=0.0):
    body = [(x - 60 * s, y), (x + 40 * s, y - 16 * s), (x + 84 * s, y - 4 * s),
            (x + 70 * s, y + 18 * s), (x - 50 * s, y + 20 * s)]
    pygame.draw.polygon(surface, (24, 28, 34), body)
    pygame.draw.polygon(surface, (18, 22, 28),
                        [(x - 60 * s, y + 2), (x - 30 * s, y - 4),
                         (x - 8 * s, y + 8), (x - 34 * s, y + 12)])
    pygame.draw.line(surface, (24, 28, 34), (x - 58 * s, y + 4),
                     (x - 130 * s, y - 6), max(2, int(6 * s)))
    pygame.draw.polygon(surface, (18, 22, 28),
                        [(x - 126 * s, y - 20 * s), (x - 118 * s, y - 2),
                         (x - 138 * s, y - 2)])
    pygame.draw.line(surface, (18, 22, 28), (x - 30 * s, y + 20),
                     (x - 26 * s, y + 34 * s), max(2, int(3 * s)))
    pygame.draw.line(surface, (18, 22, 28), (x + 40 * s, y + 18),
                     (x + 44 * s, y + 32 * s), max(2, int(3 * s)))
    pygame.draw.line(surface, (18, 22, 28), (x - 34 * s, y + 33),
                     (x + 50 * s, y + 31), max(2, int(3 * s)))
    spin = (t * 0.02) % 360
    for a in (spin, spin + 90):
        dx, dy = math.cos(math.radians(a)), math.sin(math.radians(a)) * 0.18
        pygame.draw.line(surface, (96, 104, 116),
                         (x, y - 18), (x + dx * 150 * s, y - 18 + dy * 150 * s),
                         max(1, int(2 * s)))
    pygame.draw.circle(surface, (255, 70, 50), (int(x + 60 * s), int(y + 2 * s)), 2)
    pygame.draw.circle(surface, (50, 220, 110), (int(x - 40 * s), int(y + 14 * s)), 2)


def _fb_ridge(surface, crest=330):
    """Snow ridge above the border valley: crest in the foreground, compound
    and sodium lamps down in the dark below, hills behind."""
    pygame.draw.polygon(surface, (22, 27, 39),
                        [(0, crest + 18), (WIDTH * 0.28, crest - 26),
                         (WIDTH * 0.55, crest + 6), (WIDTH * 0.8, crest - 14),
                         (WIDTH, crest + 10), (WIDTH, SCENE_BOT),
                         (0, SCENE_BOT)])
    pygame.draw.polygon(surface, (36, 44, 62),
                        [(0, crest + 30), (WIDTH * 0.3, crest - 6),
                         (WIDTH * 0.58, crest + 14), (WIDTH * 0.82, crest - 2),
                         (WIDTH, crest + 18), (WIDTH, SCENE_BOT),
                         (0, SCENE_BOT)])
    for i, x in enumerate(range(70, WIDTH, 120)):
        pygame.draw.rect(surface, (18, 20, 28), (x, crest + 44, 14, 20))
        pygame.draw.rect(surface, (226, 176, 104), (x + 4, crest + 48, 4, 4))
    for i, x in enumerate((150, 240, 330)):
        pygame.draw.rect(surface, (24, 28, 36), (x, crest + 78, 8, 26))
        pygame.draw.rect(surface, (255, 206, 140), (x + 1, crest + 82, 5, 5))


def _fb_rotor(surface, x, y, s, t):
    """Faint translucent rotor disc, radius = the blade span."""
    disc = pygame.Surface((int(320 * s), int(64 * s)), pygame.SRCALPHA)
    pygame.draw.ellipse(disc, (120, 132, 150, 26), disc.get_rect())
    pygame.draw.ellipse(disc, (90, 100, 116, 40), disc.get_rect(), 1)
    surface.blit(disc, (int(x - 160 * s), int(y - 32 * s)))
    spin = (t * 0.02) % 360
    for a in (spin, spin + 90):
        dx, dy = math.cos(math.radians(a)), math.sin(math.radians(a)) * 0.18
        pygame.draw.line(surface, (96, 104, 116),
                         (x, y), (x + dx * 150 * s, y + dy * 150 * s),
                         max(1, int(2 * s)))


def _fb_insert(surface, t, mode):
    _fb_gradient(surface, (6, 9, 17), (22, 30, 46))
    _fb_hills(surface, 300, moon=False)
    if mode == "cabin":
        pygame.draw.rect(surface, (14, 17, 22), (170, 90, 660, 360))
        pygame.draw.rect(surface, (30, 35, 44), (250, 120, 500, 260))
        pygame.draw.rect(surface, (16, 20, 28), (700, 140, 130, 270))
        pygame.draw.polygon(surface, (18, 20, 24),
                            [(360, 260), (410, 250), (420, 400), (365, 415)])
        pygame.draw.circle(surface, (150, 40, 34), (520, 190), 7)
        pygame.draw.circle(surface, (70, 170, 110), (560, 330), 5)
        _fb_snow(surface, t, 4, 80)
        return
    if mode == "chase":
        x = 300 + 260 * _w.ease5(t, 0, 2800)
        _fb_rotor(surface, x, 250, 1.1, t)
        _fb_heli(surface, x, 272, 1.1, t, tilt=-0.08)
        pygame.draw.polygon(surface, (226, 214, 180),
                            [(x + 48, 300), (x + 64, 300), (x + 190, 452),
                             (x + 90, 452)])
        _fb_snow(surface, t, 9, 120)
        return
    _fb_ridge(surface, 330)
    for i in range(8):
        pygame.draw.rect(surface, (226, 178, 108), (180 + i * 34, 392, 5, 5))
    if mode == "valley":
        _fb_rotor(surface, 560 - t * 0.02, 214, 1.25, t)
        _fb_heli(surface, 560 - t * 0.02, 236, 1.25, t)
        _fb_snow(surface, t, 3)
        _fb_tag(surface, "KIM KIM BORDER // 02:40")
        return
    if mode == "jump":
        _fb_heli(surface, 700, 150, 1.0, t)
        pygame.draw.polygon(surface, (18, 20, 26),
                            [(350, 400 + min(60, t * 0.02)), (380, 370),
                             (420, 365), (450, 395), (450, 540), (350, 540)])
        _fb_snow(surface, t, 5)
        return
    pygame.draw.polygon(surface, (18, 20, 26),
                        [(350, 400), (380, 370), (420, 365), (450, 395),
                         (450, 540), (350, 540)])
    _fb_rotor(surface, 760, 150 - t * 0.004, 0.8, t)
    _fb_heli(surface, 760, 172 - t * 0.004, 0.75, t, tilt=0.2)
    _fb_snow(surface, t, 6)


def _fb_tag(surface, text, col=(120, 190, 220)):
    surf = font_terminal_small.render(text, True, col)
    plate = pygame.Surface((surf.get_width() + 20, surf.get_height() + 6),
                           pygame.SRCALPHA)
    plate.fill((4, 6, 10, 186))
    surface.blit(plate, (24, SCENE_TOP + 6))
    surface.blit(surf, (34, SCENE_TOP + 9))


def _fb_boxcar(surface, t, mode):
    pygame.draw.rect(surface, (30, 24, 18), (0, SCENE_TOP, WIDTH, _w.FILM_H))
    for x in range(0, WIDTH, 90):
        pygame.draw.rect(surface, (40, 32, 24), (x, SCENE_TOP, 10, _w.FILM_H))
    pygame.draw.rect(surface, (24, 20, 16), (0, SCENE_TOP, WIDTH, 54))
    pygame.draw.rect(surface, (24, 20, 16), (0, SCENE_BOT - 48, WIDTH, 48))
    pygame.draw.rect(surface, (14, 20, 32), (700, 120, 210, 300))
    pygame.draw.rect(surface, (48, 60, 82), (700, 380, 210, 60))
    _fb_snow(surface, t, 8, 40)
    pygame.draw.rect(surface, (22, 18, 14), (760, 100, 26, 300))
    lamp = (520, 150)
    pygame.draw.line(surface, (16, 14, 12), (520, SCENE_TOP), (520, 150), 2)
    pygame.draw.circle(surface, (255, 220, 160), lamp, 12)
    glow = pygame.Surface((220, 220), pygame.SRCALPHA)
    for r in range(100, 4, -4):
        pygame.draw.circle(glow, (255, 196, 120, 3), (110, 110), r)
    surface.blit(glow, (lamp[0] - 110, lamp[1] - 110))
    if mode == "notebook":
        pygame.draw.polygon(surface, (12, 12, 14),
                            [(360, 280), (620, 250), (660, 400), (400, 440)])
        pygame.draw.polygon(surface, (206, 200, 184),
                            [(380, 292), (606, 264), (640, 388), (414, 420)])
        for i in range(7):
            pygame.draw.line(surface, (104, 100, 90),
                             (410, 306 + i * 15), (600, 286 + i * 15), 1)
    else:
        pygame.draw.polygon(surface, (20, 18, 16),
                            [(240, 250), (300, 240), (320, 470), (250, 470)])
        pygame.draw.circle(surface, (92, 70, 58), (272, 232), 24)
        pygame.draw.polygon(surface, (16, 14, 14),
                            [(560, 270), (610, 262), (625, 470), (568, 470)])
        pygame.draw.circle(surface, (104, 80, 66), (588, 252), 22)
    _fb_tag(surface, "MARKED BOXCAR" if mode != "notebook" else "THE NOTEBOOK")


def _fb_terminal(surface, t):
    pygame.draw.rect(surface, (14, 14, 14), (0, SCENE_TOP, WIDTH, _w.FILM_H))
    pygame.draw.rect(surface, (44, 44, 40), (250, 130, 500, 360))
    pygame.draw.rect(surface, (12, 32, 20), (280, 160, 440, 300))
    glow = pygame.Surface((620, 420), pygame.SRCALPHA)
    for r in range(300, 8, -8):
        pygame.draw.circle(glow, (90, 150, 110, 2), (310, 210), r)
    surface.blit(glow, (200, 70))
    _crt_panel(surface, (280, 160, 440, 300), t)
    _fb_tag(surface, "SIGNAL OFFICE")


def _fb_figure(surface, x, foot_y, s=1.0, coat=(18, 20, 24),
               skin=(96, 74, 60), facing=1):
    """Cheap 2D silhouette for the fallbacks: readable shape, not a blob."""
    w = 26 * s
    h = 150 * s
    pygame.draw.polygon(surface, coat,
                        [(x - w * 0.65, foot_y), (x - w * 0.5, foot_y - h * 0.72),
                         (x + w * 0.5, foot_y - h * 0.72),
                         (x + w * 0.65, foot_y)])
    pygame.draw.rect(surface, coat,
                     (x - w * 0.5, foot_y - h * 0.95, w, h * 0.28))
    pygame.draw.circle(surface, skin, (int(x + facing * 3 * s),
                                       int(foot_y - h * 1.04)), int(11 * s))


def _fb_radio(surface, t, variant):
    pygame.draw.rect(surface, (18, 16, 15), (0, SCENE_TOP, WIDTH, _w.FILM_H))
    pygame.draw.rect(surface, (28, 26, 24), (0, 330, WIDTH, 290))
    pygame.draw.rect(surface, (12, 20, 34), (640, 120, 260, 210))
    _fb_snow(surface, t, 9, 34)
    if variant in (1, 3):
        # Vasile's office: window blinds, a man at the glass, the desk below.
        pygame.draw.rect(surface, (16, 18, 24), (620, 96, 300, 250))
        for i in range(9):
            pygame.draw.rect(surface, (120, 104, 74),
                             (632, 108 + i * 25, 276, 5))
        _fb_figure(surface, 760, 400, 1.05, coat=(14, 16, 20),
                   skin=(110, 84, 66), facing=-1)
        pygame.draw.rect(surface, (34, 28, 22), (120, 330, 430, 26))
        pygame.draw.rect(surface, (24, 22, 20), (180, 356, 40, 90))
        pygame.draw.rect(surface, (24, 22, 20), (450, 356, 40, 90))
        if variant == 3 and t > 4200:
            pygame.draw.rect(surface, (196, 190, 172), (200, 300, 250, 30))
            pygame.draw.circle(surface, (210, 62, 48), (330, 315), 9)
        _fb_tag(surface, "GUARD HQ // VASILE'S OFFICE")
        return
    if variant == "maru" and t < 900:
        pygame.draw.rect(surface, (40, 38, 34), (360, 300, 280, 70))
        pygame.draw.rect(surface, (22, 22, 20), (420, 270, 150, 40))
        pygame.draw.circle(surface, (220, 82, 58), (450, 286), 4)
        pygame.draw.circle(surface, (90, 220, 140) if t > 250 else (36, 52, 44),
                           (520, 286), 4)
        _fb_tag(surface, "MARU // OPEN CHANNEL")
        return
    if variant == 0 and t < 1200:
        pygame.draw.rect(surface, (58, 48, 38), (300, 340, 420, 40))
        pygame.draw.rect(surface, (206, 202, 190), (400, 330, 190, 22))
        pygame.draw.rect(surface, (172, 42, 38), (470, 334, 70, 14))
        pygame.draw.circle(surface, (128, 102, 84), (580, 330), 14)
        _fb_tag(surface, "THE CALL // ROUTE 12")
        return
    if variant in (2, "silence"):
        _fb_figure(surface, 500, 470, 2.1, coat=(16, 18, 22),
                   skin=(100, 78, 62), facing=1)
        pygame.draw.rect(surface, (58, 60, 52), (474, 208, 16, 40))
        _fb_tag(surface, "THE CALL // NO ANSWER" if variant == "silence"
                else "THE CALL")
        return
    _fb_figure(surface, 330, 470, 1.35, facing=1)
    pygame.draw.rect(surface, (40, 38, 34), (620, 330, 180, 70))
    pygame.draw.circle(surface, (255, 160, 80), (700, 352), 4)
    _fb_tag(surface, "THE CALL" if variant else "WIRE // ROUTE 12")


def _fb_silence(surface, t):
    _fb_radio(surface, t, "silence")


def _fb_cut_line(surface, t):
    if t < 1500:
        pygame.draw.rect(surface, (26, 24, 22), (0, SCENE_TOP, WIDTH, _w.FILM_H))
        pygame.draw.rect(surface, (40, 38, 34), (340, 300, 320, 90))
        pygame.draw.rect(surface, (22, 22, 20), (400, 260, 180, 46))
        pygame.draw.circle(surface, (220, 82, 58) if t < 650 else (34, 40, 38),
                           (460, 280), 5)
        pygame.draw.circle(surface, (36, 52, 44), (540, 280), 5)
        pygame.draw.circle(surface, (128, 102, 84),
                           (480, 316 - int(6 * min(1.0, t / 600))), 12)
        _fb_tag(surface, "THE CALL // CUT")
        return
    pygame.draw.rect(surface, (20, 18, 17), (0, SCENE_TOP, WIDTH, _w.FILM_H))
    pygame.draw.rect(surface, (30, 28, 26), (0, 340, WIDTH, 280))
    _fb_figure(surface, 520, 480, 1.9, coat=(14, 16, 20), facing=1)
    pygame.draw.rect(surface, (30, 30, 34), (486, 322, 66, 30))
    pygame.draw.rect(surface, (196, 192, 180), (492, 326, 54, 18))
    _fb_tag(surface, "THE CALL // CUT")


def _fb_customs_return(surface, t):
    _fb_gradient(surface, (6, 9, 16), (24, 30, 44))
    _fb_snow(surface, t, 20, 80)
    pygame.draw.rect(surface, (46, 50, 58), (0, 360, WIDTH, 270))
    # the frozen queue
    for i, x in enumerate((60, 160, 260)):
        pygame.draw.rect(surface, (30, 34, 40), (x, 360 - 52, 74, 52))
        pygame.draw.rect(surface, (22, 26, 32), (x + 8, 360 - 78, 58, 30))
        pygame.draw.rect(surface, (70, 80, 94), (x + 10, 360 - 76, 54, 8))
    # fence, gate, hut with the lit window
    pygame.draw.rect(surface, (52, 56, 62), (320, 300, 300, 5))
    for x in range(320, 620, 24):
        pygame.draw.rect(surface, (52, 56, 62), (x, 300, 4, 64))
    pygame.draw.rect(surface, (52, 50, 48), (700, 250, 150, 120))
    pygame.draw.rect(surface, (34, 34, 36), (694, 244, 162, 12))
    pygame.draw.rect(surface, (255, 203, 109), (730, 290, 48, 30))
    # work lamps
    for x in (430, 610):
        pygame.draw.rect(surface, (40, 42, 48), (x, 190, 5, 174))
        pygame.draw.rect(surface, (255, 236, 154), (x - 3, 184, 12, 8))
    # Biribel walks into frame with the notebook
    k = min(1.0, max(0.0, (t - 500) / 3000.0))
    x = 900 - 260 * (k * k * (3 - 2 * k))
    _fb_figure(surface, x, 430, 1.0, coat=(20, 22, 28), facing=-1)
    pygame.draw.rect(surface, (196, 192, 180), (x - 22, 360, 16, 22))
    _fb_snow(surface, t, 21, 60)
    _fb_tag(surface, "KRAP BORDER CUSTOMS // 04:10")


def _fb_helicopter(surface, t):
    """Three beats: the pickup, the cabin, the turn away from the capital."""
    _fb_gradient(surface, (6, 8, 15), (30, 28, 42))
    if t < 4600:
        # customs lot: hut, fence, queue, Huey coming down
        pygame.draw.rect(surface, (44, 48, 56), (0, 380, WIDTH, 250))
        pygame.draw.rect(surface, (52, 50, 48), (700, 270, 150, 110))
        pygame.draw.rect(surface, (255, 203, 109), (730, 306, 46, 28))
        for x in (430, 610):
            pygame.draw.rect(surface, (40, 42, 48), (x, 190, 5, 190))
            pygame.draw.rect(surface, (255, 236, 154), (x - 3, 184, 12, 8))
        k = min(1.0, t / 3200.0)
        s = 0.45 + 0.55 * k
        hx, hy = 470, 70 + 210 * k
        _fb_rotor(surface, hx, hy - 18 * s, s, t)
        _fb_heli(surface, hx, hy, s, t, tilt=0.1)
        pygame.draw.polygon(surface, (120, 132, 150),
                            [(hx, hy + 16), (hx - 120 * s, 430),
                             (hx + 30 * s, 430)])
        run = min(1.0, max(0.0, (t - 400) / 3200.0))
        _fb_figure(surface, 900 - 420 * run, 430, 1.0,
                   coat=(20, 22, 28), facing=-1)
        _fb_snow(surface, t, 20, 80)
        _fb_tag(surface, "KRAP BORDER CUSTOMS // 04:12")
        return
    if t < 8200:
        # cabin: dark interior, city through the open door, the door closing
        pygame.draw.rect(surface, (10, 12, 16), (0, SCENE_TOP, WIDTH, _w.FILM_H))
        pygame.draw.rect(surface, (22, 25, 30), (120, 70, 220, 420), 6)
        pygame.draw.rect(surface, (18, 20, 26), (340, 60, 660, 440), 8)
        win = pygame.Rect(540, 120, 300, 220)
        pygame.draw.rect(surface, (8, 10, 18), win)
        for i, x in enumerate(range(560, 830, 34)):
            h = 40 + (i * 37) % 90
            pygame.draw.rect(surface, (18 + i % 3, 20 + i % 3, 30 + i % 4),
                             (x, 340 - h, 26, h))
            pygame.draw.rect(surface, (222, 176, 106), (x + 5, 336 - h + 12, 3, 4))
        shut = min(1.0, max(0.0, (t - 6600) / 900.0))
        if shut > 0:
            pygame.draw.rect(surface, (26, 28, 32),
                             (win.x, win.y, int(win.w * shut), win.h))
        _fb_figure(surface, 330, 470, 1.7, coat=(14, 16, 20), facing=1)
        _fb_figure(surface, 780, 470, 1.5, coat=(18, 20, 24), facing=-1)
        pygame.draw.circle(surface, (255, 70, 50), (470, 110), 4)
        _fb_tag(surface, "EN ROUTE // KRAP BORDER")
        return
    # turn away: capital lights left, dark hills right
    for i, x in enumerate(range(30, 640, 84)):
        h = 50 + (i * 41) % 120
        pygame.draw.rect(surface, (18 + i % 3, 20 + i % 3, 30 + i % 4),
                         (x, 330 - h, 66, h + 60))
        for j in range(3):
            pygame.draw.rect(surface, (222, 176, 106) if j != 1 else (176, 194, 222),
                             (x + 10 + j * 19, 340 - h + 12 + (i * 7) % 30, 4, 5))
    pygame.draw.polygon(surface, (13, 15, 21),
                        [(600, 360), (700, 290), (820, 330), (930, 260),
                         (WIDTH, 310), (WIDTH, 370)])
    pygame.draw.rect(surface, (24, 20, 30), (0, 350, WIDTH, 280))
    q = min(1.0, max(0.0, (t - 8200) / 3800.0))
    hx = 300 + 440 * q
    hy = 220 - 120 * q
    _fb_rotor(surface, hx, hy - 18, 0.85, t)
    _fb_heli(surface, hx, hy, 0.85, t, tilt=0.55 * math.sin(math.pi * q))
    pygame.draw.circle(surface, (255, 70, 50), (int(hx + 60 * 0.85), int(hy + 2)), 2)
    pygame.draw.circle(surface, (50, 220, 110), (int(hx - 40 * 0.85), int(hy + 14)), 2)
    _fb_snow(surface, t, 11, 60)
    _fb_tag(surface, "THE LAST SIGNAL")


# ═══════════════════════════════════════════════════════════════════════════
# dispatch / registration
# ═══════════════════════════════════════════════════════════════════════════
M6_3D_SCENES = {
    "m6_insert_chase": _insert_chase,
    "m6_insert_cabin": _insert_cabin,
    "m6_insert_valley": _insert_valley,
    "m6_insert_jump": _insert_jump,
    "m6_insert_ground": _insert_ground,
    "m6_boxcar_wide": _boxcar_wide,
    "m6_boxcar_notebook": _boxcar_notebook,
    "m6_boxcar_volkov": _boxcar_volkov,
    "m6_boxcar_biribel": _boxcar_biribel,
    "m6_boxcar_exit": _boxcar_exit,
    "m6_customs_return": _customs_return,
    "m6_customs_terminal": _customs_terminal,
    "m6_radio_vasile": _radio_vasile,
    "m6_radio_silence": _radio_silence,
    "m6_radio_maru": _radio_maru,
    "m6_cut_line": _cut_line,
    "m6_helicopter": _helicopter,
}


def draw_m6_scene_3d(scene, surface, t):
    fn = M6_3D_SCENES.get(scene)
    if fn is None or not m6_3d_enabled():
        return False
    try:
        fn(surface, t)
        return True
    except Exception as e:  # any 3D failure -> permanent 2D fallback this run
        _cache["failed"], _cache["err"] = True, e
        print(f"m6films: 3D cutscenes disabled, using 2D ({e!r})")
        return False


def prepare():
    """Warm the renderer, sets and rigs before the shot clock starts."""
    if not m6_3d_enabled():
        return False
    try:
        _w.rend()
        _w.hum(_BIRI)
        _w.hum("volkov")
        _w.hum("maru")
        _w.hum("guard")
        return True
    except Exception as e:
        _cache["failed"], _cache["err"] = True, e
        print(f"m6films: warmup failed, using 2D ({e!r})")
        return False


def _take(scene, fallback):
    def take(surface, t):
        if not draw_m6_scene_3d(scene, surface, t):
            fallback(surface, t)
    return take


def _insert_fb(mode):
    return lambda surface, t: _fb_insert(surface, t, mode)


def _boxcar_fb(mode):
    return lambda surface, t: _fb_boxcar(surface, t, mode)


_register({
    "m6_insert_chase": _take("m6_insert_chase", _insert_fb("chase")),
    "m6_insert_cabin": _take("m6_insert_cabin", _insert_fb("cabin")),
    "m6_insert_valley": _take("m6_insert_valley", _insert_fb("valley")),
    "m6_insert_jump": _take("m6_insert_jump", _insert_fb("jump")),
    "m6_insert_ground": _take("m6_insert_ground", _insert_fb("ground")),
    "m6_boxcar_wide": _take("m6_boxcar_wide", _boxcar_fb("wide")),
    "m6_boxcar_notebook": _take("m6_boxcar_notebook", _boxcar_fb("notebook")),
    "m6_boxcar_volkov": _take("m6_boxcar_volkov", _boxcar_fb("volkov")),
    "m6_boxcar_biribel": _take("m6_boxcar_biribel", _boxcar_fb("biribel")),
    "m6_boxcar_exit": _take("m6_boxcar_exit", _boxcar_fb("exit")),
    "m6_customs_return": _take("m6_customs_return", _fb_customs_return),
    "m6_customs_terminal": _take("m6_customs_terminal", _fb_terminal),
    "m6_radio_vasile": _take("m6_radio_vasile",
                             lambda surface, t: _fb_radio(surface, t,
                                                          _radio_variant())),
    "m6_radio_silence": _take("m6_radio_silence", _fb_silence),
    "m6_radio_maru": _take("m6_radio_maru",
                           lambda surface, t: _fb_radio(surface, t, "maru")),
    "m6_cut_line": _take("m6_cut_line", _fb_cut_line),
    "m6_helicopter": _take("m6_helicopter", _fb_helicopter),
})
