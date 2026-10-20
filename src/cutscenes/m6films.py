"""m6films.py - engine3d takes and 2D fallbacks for every Mission 6 film.

Registered scene ids (exact contract from ``docs/MISSION6_PLOT.md``):

    insertion   m6_insert_heli, m6_insert_jump, m6_insert_fall, m6_insert_ground
    boxcar      m6_boxcar_wide, m6_boxcar_notebook, m6_boxcar_volkov,
                m6_boxcar_biribel, m6_boxcar_exit
    ending      m6_customs_terminal, m6_radio_vasile (four authored shots),
                m6_radio_maru, m6_helicopter

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
from cutscenes import m5fx3d as _fx
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
                yaw=None, bank=None):
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
# snow ridge climbs south of it and the LZ is its crest shelf (~16.6 m).
# The Huey hovers nose-north on the shelf; Biribel sits in the open right
# (east) door, soles on the skid, and drops north into the valley.
_HOVER_XZ = (-1.0, -47.55)
_LZ_GROUND = _w.height_at(*_HOVER_XZ)
_HOVER_Y = _LZ_GROUND + 4.60
_HELI_YAW = 0.0
_HELI_BANK = 2.5
_LAND = (0.55, -36.40)


def hover_pos(t, climb=0.0, drift=(0.0, 0.0)):
    """The same hover for shots 1-3; shot 4 passes climb/drift to leave.
    The sway is deliberately larger than the rotor bob so a locked-off wide
    shot reads as a helicopter holding station, not a parked prop."""
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


_SEAT = {}


def _chute_pack(r, pose, pos, yaw):
    """Static-line parachute pack on his back; drawn in every insertion shot."""
    from engine3d.core import Mesh, box, rot_y
    chest = _joints(_BIRI, pose, pos, yaw)["chest"]
    back = _local(chest, yaw, fwd=-0.19, up=0.07)
    m = Mesh()
    m.add(box(0.36, 0.40, 0.16, (52, 54, 44)))
    m.add(box(0.30, 0.06, 0.17, (36, 38, 32)), t=(0, -0.12, 0))
    for sx in (-1, 1):
        m.add(box(0.05, 0.28, 0.17, (30, 32, 28)), t=(sx * 0.16, 0.02, 0))
    out = Mesh()
    out.add(m, m=rot_y(yaw), t=back)
    _w.add(r, out)


def _chute_mesh(center, radius, open_k=1.0, collapse=0.0, tilt=8.0):
    """Low-poly round canopy -> (mesh, rim points). Collapse flattens it for
    the landing pile; tilt leans it into the descent."""
    from engine3d.core import Mesh
    n = 12
    rad = radius * max(0.05, open_k)
    h = 0.62 * rad * (1.0 - 0.75 * collapse)
    ang = math.radians(tilt)
    rings = ((1.0, 0.0), (0.86, 0.34), (0.55, 0.68), (0.0, 0.92))
    pts = []
    for rf, yf in rings:
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n
            dx = math.cos(a) * rad * rf
            dz = math.sin(a) * rad * rf
            yy = h * yf
            ring.append((center[0] + dx,
                         center[1] + yy * math.cos(ang) - dz * math.sin(ang),
                         center[2] + yy * math.sin(ang) + dz * math.cos(ang)))
        pts.append(ring)
    mesh = Mesh()
    for ri in range(len(rings) - 1):
        for i in range(n):
            quad = [pts[ri][i], pts[ri][(i + 1) % n],
                    pts[ri + 1][(i + 1) % n], pts[ri + 1][i]]
            col = (_CHUTE_RED if i in (0, 6)
                   else (_CHUTE_ALT if i % 2 else _CHUTE_TOP))
            mesh.face(quad, col, 2, True, False)
    return mesh, pts[0]


_CHUTE_TOP = (64, 70, 56)
_CHUTE_ALT = (78, 82, 66)
_CHUTE_RED = (92, 38, 34)
_CHUTE_LINE = (168, 176, 186)


def _draw_chute(r, pose, pos, yaw, offset=(0.0, 2.35, 0.0), open_k=1.0,
                collapse=0.0, tilt=8.0, lines=True):
    chest = _joints(_BIRI, pose, pos, yaw)["chest"]
    center = tuple(chest[i] + offset[i] for i in range(3))
    mesh, rim = _chute_mesh(center, 1.62, open_k, collapse, tilt)
    _w.add(r, mesh)
    if lines and open_k > 0.3:
        anchor = (chest[0], chest[1] + 0.24, chest[2])
        for i in range(0, 12, 2):
            r.add_line3d(rim[i], anchor, _CHUTE_LINE, 1, layer=4)


def _draw_chute_ground(r, x, z):
    """The canopy he just stepped out of, flat on the snow behind the LZ."""
    from engine3d.core import box
    gy = _w.height_at(x - 0.8, z - 1.1) + 0.05
    mesh, _rim = _chute_mesh((x - 0.8, gy, z - 1.1), 1.45, 1.0,
                             collapse=1.0, tilt=0.0)
    _w.add(r, mesh)
    for i in range(5):
        u = _w._u(i, 71, 1)
        v = _w._u(i, 71, 2)
        _w.add(r, box(0.30 + 0.3 * u, 0.06, 0.22 + 0.2 * v,
                      _CHUTE_ALT if i % 2 else _CHUTE_TOP,
                      center=(x - 1.2 + u * 0.9, gy + 0.05,
                              z - 1.7 + v * 1.1)))


def heli_seat():
    """Seated door pose + airframe-local root: pelvis over the sill, soles on
    the skid, shins hanging outside the open door."""
    d = _SEAT.get("v")
    if d is None:
        h = _w.hum(_BIRI)
        pose = _w.sit_pose(h, _w.HELI_SILL_Y - _w.HELI_SKID_Y,
                           dict(spine=7, head_p=1, lsh_p=12, lel=30,
                                rsh_p=10, rsh_r=-5, rel=26))
        a = _w.ankles(h, pose, (0.0, _w.HELI_SKID_Y, 0.0), 90.0)
        dx = 0.5 * (a["l"][0] + a["r"][0])
        dz = 0.5 * (a["l"][2] + a["r"][2])
        d = _SEAT["v"] = (pose, (_w.HELI_SKID_X - dx, _w.HELI_SKID_Y,
                                 _w.HELI_DOOR_Z - dz))
    return d


def seated_door(t):
    """Biribel on the sill at the hover -> (pose, world pos, yaw)."""
    pose, root = heli_seat()
    L = _w.heli_xform(hover_pos(t), hover_yaw(t), hover_bank(t))
    return pose, L(*root), hover_yaw(t) + 90.0


def jump_stage(t):
    """Weight shift on the sill, then a leg push out of the door at 2150 ms.
    The feet do not move before the push, so nothing skates on the skid."""
    pose0, root = heli_seat()
    heli = hover_pos(t)
    wind = _w.ease5(t, 500, 900)
    lean = _w.ease5(t, 1500, 560)
    push = _w.ease5(t, 2150, 620)
    pose = dict(pose0)
    pose["spine"] = 7 + 5 * wind + 13 * lean + 8 * push
    pose["head_p"] = 1 - 2 * wind - 7 * lean + 4 * push
    pose["lsh_p"] = 12 + 22 * wind + 26 * push
    pose["rsh_p"] = 10 + 18 * wind + 22 * push
    pose["lel"] = 30 + 18 * wind
    pose["rel"] = 26 + 14 * wind
    if push > 0.0:
        leap = dict(pose, spine=24, head_p=-12,
                    lhip_p=-16, rhip_p=-8, lkn=58, rkn=46,
                    lsh_p=54, rsh_p=46, lel=22, rel=28)
        pose = _mix(pose, leap, push)
    L = _w.heli_xform(heli, hover_yaw(t), hover_bank(t))
    out = 0.82 * push
    drop = 0.52 * push * push
    return pose, L(root[0] + out, root[1] - drop, root[2]), \
        hover_yaw(t) + 90.0, heli


_FALL_A = (0.88, 20.86, -46.55)
_FALL_B = (0.55, 9.85, -36.40)


def fall_stage(t):
    """Freefall, canopy opening, then a slow chute descent down the slope."""
    q = max(0.0, min(1.0, (t - 100) / 2500.0))
    # forward momentum is constant; vertical speed settles under the canopy
    e = 0.30 * q + 0.70 * q * q
    open_k = _w.ease5(t, 700, 900)
    pos = (_FALL_A[0] + (_FALL_B[0] - _FALL_A[0]) * q,
           _FALL_A[1] + (_FALL_B[1] - _FALL_A[1]) * e,
           _FALL_A[2] + (_FALL_B[2] - _FALL_A[2]) * q)
    sway = 2.4 * math.sin(t * 0.0011)
    free = dict(body_p=18, spine=8, head_p=-8,
                lhip_p=-18, rhip_p=10, lkn=40, rkn=26,
                lsh_p=70, rsh_p=58, lel=34, rel=30)
    chute = dict(body_p=10, spine=6, head_p=-2,
                 twist=sway * 0.9, head_y=-sway * 0.6,
                 lhip_p=-9, rhip_p=-7, lkn=20, rkn=17,
                 lsh_p=104, rsh_p=100, lel=20, rel=22)
    pose = _mix(free, chute, open_k)
    return pose, pos, 74.0 + 8.0 * q + sway


def chute_open(t):
    """Canopy deployment 0..1 (also drives the fallback and the probe)."""
    return _w.ease5(t, 700, 900)


_GROUND_ROUTE = {}


def ground_route():
    r = _GROUND_ROUTE.get("v")
    if r is None:
        r = _GROUND_ROUTE["v"] = _w.path([_LAND, (0.35, -33.40)])
    return r


def ground_stage(t):
    """Landing crouch -> planted rise -> four gait steps downhill north."""
    hum = _w.hum(_BIRI)
    rise = _w.ease5(t, 620, 900)
    if t < 1520:
        pose = _mix("kneel_over", "stand", rise)
        pose["spine"] = pose.get("spine", 0) + 14 * math.sin(math.pi * rise)
        pos = _w.planted_pos(hum, pose, 0.0, _LAND)
        return pose, (pos[0], _w.height_at(pos[0], pos[2]) - 0.05, pos[2]), 0.0
    route = ground_route()
    stride = _w.walk_stride(route.length, 0.56)
    g0, g1 = _w.walk_span(route.length, stride)
    g = g0 + (g1 - g0) * _w.travel(t, 1500, 1550)
    pose, pos, yaw = _w.walk(hum, route, g, stride, speed=1.05,
                             ground=lambda x, z: _w.height_at(x, z) - 0.06)
    pose["head_p"] = pose.get("head_p", 0) - 2.0
    return pose, pos, yaw


def heli_depart(t):
    """The hover climbs away south-east as he walks off -> (pos, yaw, bank,
    pitch).  It stays in frame above the ridge line behind him."""
    q = _w.travel(t, 0, 3100)
    return (hover_pos(t, climb=8.0 * q, drift=(-10.0 * q, 8.0 * q)),
            hover_yaw(t) + 64.0 * q, hover_bank(t) - 17.0 * q, -3.0 * q)


def heli_at(scene, t):
    """Airframe placement ``scene`` draws at ``t`` -> (pos, yaw, bank, pitch);
    None for sets without a helicopter.  The probe and tests read this."""
    if scene in ("m6_insert_heli", "m6_insert_jump", "m6_insert_fall"):
        return hover_pos(t), hover_yaw(t), hover_bank(t), 0.0
    if scene == "m6_insert_ground":
        return heli_depart(t)
    if scene == "m6_helicopter":
        k = _w.travel(min(t, 5200), 0, 5200)
        return ((10.0 + 5.0 * k, 16.2 + 3.1 * k, -9.0 - 2.0 * k),
                4.0 + 100.0 * k, -18.0 * min(1.0, k * 1.3), -3.0)
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


def _insert_heli(surface, t):
    t = min(t, 3200)
    r, buf = _w.rend()
    r.fog, r.fog_start, r.fog_end = (11, 15, 24), 38.0, 190.0
    heli = hover_pos(t)
    pose, seat, yaw = seated_door(t)
    head = _joints(_BIRI, pose, seat, yaw)["head"]
    _rig_insert(r, heli, cabin=0.18, amb=0.25, fill=(0.50, 0.42, -0.45),
                yaw=hover_yaw(t), bank=hover_bank(t),
                bounce={"pos": (head[0] + 0.30, head[1] + 0.18, head[2] + 0.15),
                        "color": (150, 170, 200), "intensity": 0.22,
                        "range": 1.8})
    _cam(r, t, (12.8, 26.0, -62.5), (-0.6, 22.8, -45.5), 44,
         hh=0.03, seed=1, roll=0.12 * math.sin(t * 0.0007))
    _w.night(r, buf, t, top=(5, 8, 16), bot=(18, 26, 44), stars=58,
             moon=(28, 0.30), sodium=(70, 44, 26), seed=3)
    _w.static_scene(r, "m6_insert_heli")
    r.begin()
    _w.terrain(r, t)
    _w.border_compound(r, t)
    _w.static_end(r)
    _w.helicopter(r, t, heli, yaw=hover_yaw(t), rotor_speed=1.0,
                  bank=hover_bank(t))
    _w.actor(r, _BIRI, pose, seat, yaw, t, seed=2, amp=0.28,
             expression="stern")
    _chute_pack(r, pose, seat, yaw)
    down = (heli[0], _LZ_GROUND + 0.45, heli[2])
    r.add_sprite(down, _fx.haze((176, 190, 212), 8.5, t, seed=4,
                                intensity=0.22), layer=_fx.FX_LAYER)
    r.add_sprite(down, _fx.dust_motes(t, seed=4, count=46,
                                      spread_m=(4.6, 1.0),
                                      col=(176, 190, 208)),
                 layer=_fx.FX_LAYER)
    r.add_sprite((heli[0], _LZ_GROUND + 0.2, heli[2]),
                 _fx.dust_motes(t, seed=5, count=30, spread_m=(2.2, 0.8),
                                col=(210, 220, 236)),
                 layer=_fx.FX_LAYER)
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, 6101, "RIDGE ABOVE KIM KIM // INSERTION")


def _insert_jump(surface, t):
    t = min(t, 2900)
    r, buf = _w.rend()
    r.fog, r.fog_start, r.fog_end = (10, 13, 20), 14.0, 105.0
    pose, seat, yaw, heli = jump_stage(t)
    chest = _joints(_BIRI, pose, seat, yaw)["chest"]
    shk = _fx.shake(t, 2150, 560, 0.022)
    _rig_insert(r, heli, cabin=0.30, amb=0.20, dif=0.50,
                fill=(0.62, 0.40, 0.30),
                yaw=hover_yaw(t), bank=hover_bank(t))
    _cam(r, t, (5.60, heli[1] + 1.62, -46.90),
         (chest[0] + 0.10, chest[1] - 0.28, chest[2] - 0.14), 44,
         hh=0.02, seed=7, roll=0.30 * math.sin(t * 0.0009), shk=shk)
    _w.night(r, buf, t, top=(5, 8, 15), bot=(19, 27, 44), stars=44,
             moon=(24, 0.28), sodium=(54, 34, 22), seed=8)
    _w.static_scene(r, "m6_insert_jump")
    r.begin()
    _w.terrain(r, t, lights=False)
    _w.border_compound(r, t, warm=0.8)
    _w.static_end(r)
    _w.helicopter(r, t, heli, yaw=hover_yaw(t), rotor_speed=1.0,
                  bank=hover_bank(t))
    _w.actor(r, _BIRI, pose, seat, yaw, t, seed=9, amp=0.30,
             expression="stern")
    _chute_pack(r, pose, seat, yaw)
    stream = _w.ease5(t, 2340, 520)
    if stream > 0.01:
        _draw_chute(r, pose, seat, yaw,
                    offset=(0.35, 1.05 + 0.28 * stream, -0.55),
                    open_k=0.12 + 0.20 * stream, tilt=20.0, lines=False)
    # rotor wash: streaking snow swept down and out of the door
    for i in range(18):
        u, v = _w._u(i, 5, 1), _w._u(i, 5, 2)
        x = seat[0] + 0.4 + u * 3.4
        y = seat[1] - 1.9 + v * 1.6
        z = seat[2] - 2.0 + ((v * 6.4 + t * 0.005) % 6.4)
        r.add_line3d((x, y, z), (x + 0.55, y + 0.22, z + 0.9),
                     (162, 176, 198), 1, layer=4)
    down = (heli[0], _LZ_GROUND + 0.4, heli[2])
    r.add_sprite(down, _fx.haze((176, 190, 212), 6.5, t, seed=10,
                                intensity=0.20), layer=_fx.FX_LAYER)
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, 6102, "DOOR // 12 METRES")


def _insert_fall(surface, t):
    t = min(t, 2900)
    pose, pos, yaw = fall_stage(t)
    r, buf = _w.rend()
    r.fog, r.fog_start, r.fog_end = (8, 11, 20), 24.0, 150.0
    heli = hover_pos(t)
    chest = _joints(_BIRI, pose, pos, yaw)["chest"]
    shk = _fx.shake(t, 0, 700, 0.020)
    _rig_insert(r, heli, cabin=0.24, amb=0.20, dif=0.46,
                fill=(0.40, 0.46, 0.30),
                yaw=hover_yaw(t), bank=hover_bank(t),
                bounce={"pos": (chest[0] + 0.5, chest[1] + 2.0, chest[2] + 0.6),
                        "color": (150, 166, 192), "intensity": 0.36,
                        "range": 5.5})
    eye = (pos[0] + 8.50, pos[1] + 2.50, pos[2] + 5.00)
    tgt = (pos[0], pos[1] + 2.00, pos[2])
    _cam(r, t, eye, tgt, 56, hh=0.025, seed=12,
         roll=0.30 * math.sin(t * 0.0012), shk=shk)
    _w.night(r, buf, t, top=(4, 6, 12), bot=(16, 22, 38), stars=30,
             sodium=(48, 30, 20), seed=13, star_cut=0.7)
    _w.static_scene(r, "m6_insert_fall")
    r.begin()
    _w.terrain(r, t)
    _w.border_compound(r, t)
    _w.static_end(r)
    _w.helicopter(r, t, heli, yaw=hover_yaw(t), rotor_speed=1.0,
                  bank=hover_bank(t))
    _w.air_actor(r, _BIRI, pose, pos, yaw, t, seed=14,
                 expression="stern", mouth=0.2)
    _chute_pack(r, pose, pos, yaw)
    ok = chute_open(t)
    if ok > 0.02:
        _draw_chute(r, pose, pos, yaw,
                    offset=(0.18, 0.25 + 2.10 * ok, 0.12),
                    open_k=0.12 + 0.88 * ok, tilt=7.0,
                    lines=ok > 0.30)
    # fast snow streaks rising past the lens
    for i in range(24):
        u, v = _w._u(i, 15, 1), _w._u(i, 15, 2)
        x = -4.0 + u * 12.0
        z = -50.0 + v * 9.0
        yy = (v * 18 + t * 0.014) % 18 + _LZ_GROUND - 4.0
        r.add_line3d((x, yy, z), (x, yy + 1.6 + u * 1.2, z), (172, 186, 206),
                     1, layer=4)
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, 6103, "DROP")


def _insert_ground(surface, t):
    t = min(t, 3100)
    pose, pos, yaw = ground_stage(t)
    r, buf = _w.rend()
    r.fog, r.fog_start, r.fog_end = (12, 16, 26), 26.0, 130.0
    shk = _fx.shake(t, 0, 420, 0.024)
    _rig_insert(r, amb=0.22, dif=0.48, fill=(-0.12, 0.46, 0.70),
                bounce={"pos": (pos[0] + 0.45, pos[1] + 0.40, pos[2] + 1.05),
                        "color": (168, 186, 214), "intensity": 0.34,
                        "range": 3.4})
    eye = (pos[0] + 6.20, pos[1] + 1.75, pos[2] + 1.60)
    _cam(r, t, eye, (pos[0], pos[1] + 0.95, pos[2]), 50,
         hh=0.02, seed=16, shk=shk)
    _w.night(r, buf, t, top=(6, 9, 17), bot=(19, 27, 44), stars=46,
             moon=(26, 0.26), sodium=(70, 46, 26), seed=17)
    _w.static_scene(r, "m6_insert_ground")
    r.begin()
    _w.terrain(r, t)
    _w.border_compound(r, t)
    _w.static_end(r)
    hpos, hyaw, hbank, hpitch = heli_depart(t)
    _w.helicopter(r, t, hpos, yaw=hyaw, rotor_speed=1.0, bank=hbank,
                  pitch=hpitch)
    _w.actor(r, _BIRI, pose, pos, yaw, t, seed=18, amp=0.45,
             expression="stern")
    _chute_pack(r, pose, pos, yaw)
    _draw_chute_ground(r, *_LAND)
    # the wash falls away as the Huey climbs
    wash = max(0.0, 1.0 - _w.travel(t, 0, 2200))
    if wash > 0.02:
        down = (hpos[0], _LZ_GROUND + 0.45, hpos[2])
        r.add_sprite(down, _fx.haze((200, 212, 232), 6.0, t, seed=19,
                                    intensity=0.18 * wash),
                     layer=_fx.FX_LAYER)
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, 6104, "THE CROSSING // 02:40")


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
_OFFER_L = (-0.476, 1.16, 1.048)
_OFFER_R = (-0.524, 1.16, 0.712)
_OFFER_YAW = -82.0
_OFFER_PITCH = -28.0
_TAKE = (-0.50, 1.10, 0.84)


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


def _hand(key, pose, pos, yaw, side, target):
    return _w.reach(_w.hum(key), pose, side, target, pos, yaw)


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
                  _knee_grip("volkov", p, _V_SEAT, _V_YAW, side))
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
    vp = _v_rest(16 + 9 * ext, _look(_V_SEAT, _V_YAW, bh))
    knee_r = _knee_grip("volkov", vp, _V_SEAT, _V_YAW, "r")
    knee_l = _knee_grip("volkov", vp, _V_SEAT, _V_YAW, "l")
    vp = _hand("volkov", vp, _V_SEAT, _V_YAW, "r",
               _lerp3(knee_r, _OFFER_R, ext))
    vp = _hand("volkov", vp, _V_SEAT, _V_YAW, "l",
               _lerp3(knee_l, _OFFER_L, ext))

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
    bp = _hand(_BIRI, bp, _B_MARK, _B_YAW, "l", lt)
    bp = _hand(_BIRI, bp, _B_MARK, _B_YAW, "r", _lerp3(rest_r, read_r, both))
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
                             _knee_grip("volkov", pose, pos, _V_YAW, side))
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
    rest_l = _rest_hand(_BIRI, bp, _B_MARK, _B_YAW, "l")
    rest_r = _rest_hand(_BIRI, bp, _B_MARK, _B_YAW, "r")
    edge_l = _local(nb_c, _B_YAW, right=-half, up=-0.02)
    edge_r = _local(nb_c, _B_YAW, right=half, up=-0.02)
    coat = _local(_B_MARK, _B_YAW, right=-0.05, up=1.28, fwd=0.14)
    bp = _hand(_BIRI, bp, _B_MARK, _B_YAW, "l",
               _lerp3(edge_l, rest_l, _w.ease5(t, 1000, 700)))
    bp = _hand(_BIRI, bp, _B_MARK, _B_YAW, "r",
               _lerp3(_lerp3(edge_r, coat, tuck), rest_r, back))
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
        _w.finish(surface, seed, tag)
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
    quad: header, ID photo block, labelled rows, red KIA stamp, scanlines."""
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
    head_h = max(10, int(h * 0.17))
    pygame.draw.rect(panel, (14, 42, 25), (0, 0, w, head_h))
    title = f_head.render(lines[0][0], True, (150, 236, 176))
    panel.blit(title, (pad, max(1, head_h // 2 - title.get_height() // 2)))
    tag = f_small.render("RESTRICTED", True, (84, 144, 106))
    if pad + title.get_width() + tag.get_width() + pad * 2 < w:
        panel.blit(tag, (w - pad - tag.get_width(),
                         max(1, head_h // 2 - tag.get_height() // 2)))
    pygame.draw.line(panel, (46, 104, 66), (0, head_h), (w, head_h), 1)

    body_y = head_h + max(3, int(h * 0.055))
    pw = max(22, int(w * 0.20))
    ph = max(20, int(h * 0.40))
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
    row_h = max(8, int(h * 0.095))
    reveal = max(0, int((t - 450) / 24))
    used = 0
    for row, (label, value) in enumerate(lines[1:]):
        if used >= reveal:
            break
        yy = body_y + row * row_h
        if yy + row_h > h - 14:
            break
        lab = f_small.render(label, True, (72, 126, 92))
        panel.blit(lab, (fx, yy))
        used += len(label) + 2
        avail = max(0, reveal - used)
        if avail:
            val = value[:avail]
            maxw = fw - label_w
            while val and f_body.size(val)[0] > maxw:
                val = val[:-1]
            col = (212, 92, 74) if label == "STATUS" else (122, 230, 158)
            panel.blit(f_body.render(val, True, col), (fx + label_w, yy))
        used += len(value) + 4
        if label == "STATUS":
            pygame.draw.line(panel, (58, 30, 24),
                             (fx + label_w, yy + row_h - 3),
                             (fx + label_w + f_body.size(value)[0],
                              yy + row_h - 3), 1)
    # moving scanline and the footer barcode
    sy = int((t * 0.035) % max(1, h))
    line = pygame.Surface((w, 1), pygame.SRCALPHA)
    line.fill((120, 230, 150, 26))
    panel.blit(line, (0, sy))
    foot = f_small.render(CRT_FOOT, True, (58, 112, 76))
    panel.blit(foot, (pad, h - pad - foot.get_height()))
    if pad + foot.get_width() + 58 < w:
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
    surface.blit(panel, (x, y))
    pygame.draw.rect(surface, (26, 58, 38), (x, y, w, h), 1)


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


def _customs_terminal(surface, t):
    t = min(t, 5200)
    k = _k(t, 0, 4200)
    r, buf = _w.rend()
    r.fog, r.fog_start, r.fog_end = (10, 11, 10), 9.0, 26.0
    _rig_terminal(r, fill=(0.45, 0.50, -0.70), lamp=0.55)
    eye = (2.6 - k * 2.2, 2.0 - k * 0.52, -2.6 + k * 1.7)
    tgt = (-0.9 + k * 0.1, 1.30, 1.35)
    _cam(r, t, eye, tgt, 48 - k * 16, hh=0.006, seed=37)
    buf.fill((9, 9, 9))
    r.begin()
    crt = _w.terminal_office(r, t)
    rect = _quad_rect(r, crt, 0.34, 0.24, -0.02)
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, 6301, "")
    if rect:
        _crt_panel(surface, rect, t)


def _radio_variant():
    text = _shot_text()
    if "Route 12" in text:
        return 0
    if "Three hundred" in text:
        return 1
    if "You'd have done" in text:
        return 2
    return 3


# Biribel stands off the front edge of the desk (z 1.15), the radio set at
# his right shoulder; the handset is in his radio-side hand so the cord drops
# straight to the set instead of crossing his chest.
_R_MARK = (0.55, 0.0, 0.86)
_R_YAW = -118.0
_R_JACK = (0.50, 1.00, 1.47)


def _head_point(pose, pos, yaw, right=0.0, up=0.0, fwd=0.0):
    """Point fixed to the head (head-centre local offsets, metres x scale)."""
    sc = _w.hum(_BIRI)._scale
    head = _joints(_BIRI, pose, pos, yaw)["head"]
    pt = math.radians(pose.get("spine", 0.0) + pose.get("head_p", 0.0))
    u = (up * math.cos(pt) - fwd * math.sin(pt)) * sc
    f = (fwd * math.cos(pt) + up * math.sin(pt)) * sc
    hy = yaw + pose.get("twist", 0.0) + pose.get("head_y", 0.0)
    return _local(head, hy, right=right * sc, up=u, fwd=f)


def _handset_pose(pose, pos, yaw):
    """Right hand holding the handset to the right ear -> (pose, ear, mouth)."""
    ear = _head_point(pose, pos, yaw, right=0.140, up=0.000, fwd=0.010)
    mouth = _head_point(pose, pos, yaw, right=0.118, up=-0.125, fwd=0.095)
    grip = _head_point(pose, pos, yaw, right=0.175, up=-0.055, fwd=0.045)
    return _hand(_BIRI, pose, pos, yaw, "r", grip), ear, mouth


def radio_stage(variant, t):
    """Biribel on the radio at the terminal desk -> ([cast], handset) for
    ``m6_radio_vasile`` variants 0/1 and ``"maru"``."""
    if variant == "maru":
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


def _draw_handset(r, hs, joints, yaw):
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
    side = (math.cos(math.radians(yaw)), -math.sin(math.radians(yaw)))
    n = 19
    for i in range(1, n):
        u = i / float(n)
        p = _lerp3(mouth, _R_JACK, u)
        bell = 4 * u * (1 - u)
        c = (p[0] + side[0] * 0.09 * bell, p[1] - 0.17 * bell,
             p[2] + side[1] * 0.09 * bell)
        _w.add(r, box(0.0135, 0.0135, 0.0135, (16, 16, 18), center=c))


_RADIO_CAMS = {
    0: ((-0.80, 1.74, -0.75), (0.47, 1.66, 0.82), 40, 0.006),
    1: ((-1.10, 1.52, -2.00), (0.45, 1.36, 0.95), 44, 0.008),
    # the voice on the set: dial, jack, the cord climbing to his hand
    2: ((1.30, 1.16, 1.00), (0.66, 1.03, 1.55), 42, 0.005),
    "maru": ((-0.02, 1.66, -1.26), (0.47, 1.62, 0.85), 40, 0.007),
}
_RADIO_FILL = {0: (-0.62, 0.42, -0.66), 1: (-0.70, 0.40, -0.55),
               2: (-0.40, 0.50, -0.75), "maru": (-0.30, 0.45, -0.85)}


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
    _w.finish(surface, seed, tag)


def _radio_vasile(surface, t):
    variant = _radio_variant()
    if variant == 3:
        from engine3d.core import Light
        r, buf = _w.rend()
        r.fog, r.fog_start, r.fog_end = (12, 11, 11), 10.0, 26.0
        r.light = Light(direction=(0.30, 0.55, 0.38), ambient=0.30, diffuse=0.78,
                        tint=(1.12, 1.00, 0.84))
        r.set_lights([
            {"pos": (1.00, 1.00, 1.10), "color": (255, 190, 120),
             "intensity": 0.70, "range": 4.6},
            {"pos": (2.80, 1.80, 4.40), "color": (86, 110, 160),
             "intensity": 0.55, "range": 7.0},
            {"pos": (0.20, 1.30, -0.60), "color": (90, 112, 150),
             "intensity": 0.50, "range": 2.2},
        ])
        k = _k(t, 0, 6800)
        _cam(r, t, (2.50 - k * 0.18, 1.62, -2.40 + k * 0.16),
             (-0.30, 1.05, 2.60), 50, hh=0.008, seed=38)
        buf.fill((9, 8, 8))
        r.begin()
        _w.vasile_office(r, t)
        r.flush(buf)
        _w.present(surface, buf)
        _w.finish(surface, 6304, "GUARD HQ // VASILE'S OFFICE")
        return
    _radio_take(surface, t, variant, 6300 + variant, "")


def _radio_maru(surface, t):
    _radio_take(surface, t, "maru", 6306, "THE CALL // NOT TONIGHT")


def _helicopter(surface, t):
    t = min(t, 5200)
    r, buf = _w.rend()
    r.fog, r.fog_start, r.fog_end = (12, 14, 22), 55.0, 260.0
    heli, hyaw, hbank, hpitch = heli_at("m6_helicopter", t)
    # camera-side moon key: the valley and the near faces of the capital read
    # as volumes under the skyline instead of one black wall.  A warm local
    # city light keeps the distant airframe solid under its rotor blur.
    _rig_insert(r, amb=0.24, dif=0.52, fill=(-0.38, 0.60, -0.62),
                bounce={"pos": (heli[0] + 3.0, heli[1] - 4.0, heli[2] + 4.0),
                        "color": (255, 176, 112), "intensity": 0.95,
                        "range": 20.0})
    _cam(r, t, (-9.0, 21.8, -66.0), (6.0, 8.5, 40.0), 42,
         hh=0.015, seed=45, roll=0.10 * math.sin(t * 0.0006))
    _w.night(r, buf, t, top=(5, 7, 14), bot=(22, 24, 40), stars=64,
             moon=(-8, 11.0), sodium=(96, 52, 28), seed=46, star_cut=0.35)
    _w.static_scene(r, "m6_helicopter")
    r.begin()
    _w.terrain(r, t)
    _w.border_compound(r, t)
    _w.dark_hills(r)
    _w.capital(r, t)
    _w.static_end(r)
    _w.helicopter(r, t, heli, yaw=hyaw, rotor_speed=0.8,
                  bank=hbank, pitch=hpitch, blur=0.55)
    _w.snow3d(r, t, seed=47, n=64, spread=22, height=15, speed=1.0)
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, 6307, "THE LAST SIGNAL")


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
    _fb_ridge(surface, 330)
    if mode == "heli":
        _fb_rotor(surface, 560 - t * 0.006, 214, 1.25, t)
        _fb_heli(surface, 560 - t * 0.006, 236, 1.25, t)
        _fb_snow(surface, t, 3)
        _fb_tag(surface, "RIDGE ABOVE KIM KIM // INSERTION")
        return
    if mode == "jump":
        pygame.draw.rect(surface, (14, 17, 22), (170, 90, 660, 360))
        pygame.draw.rect(surface, (30, 35, 44), (250, 120, 500, 260))
        pygame.draw.rect(surface, (16, 20, 28), (700, 140, 130, 270))
        for i in range(5):
            pygame.draw.rect(surface, (226, 180, 116),
                             (710, 180 + i * 40, 5, 5))
        pygame.draw.polygon(surface, (18, 20, 24),
                            [(560, 260), (610, 250), (620, 400), (565, 415)])
        for i in range(26):
            rng = random.Random(40 + i)
            x = 210 + rng.randrange(360)
            y = SCENE_TOP + rng.randrange(_w.FILM_H)
            pygame.draw.line(surface, (150, 164, 186), (x, y),
                             (x - 16, y + 20), 1)
        _fb_snow(surface, t, 4, 80)
        _fb_tag(surface, "DOOR // 12 METRES")
        return
    if mode == "fall":
        _fb_rotor(surface, 270, 120, 0.7, t)
        pygame.draw.polygon(surface, (24, 28, 34),
                            [(180, 136), (290, 122), (360, 146), (255, 168)])
        pygame.draw.polygon(surface, (56, 62, 50),
                            [(400, 176), (440, 150), (560, 150), (610, 178),
                             (560, 206), (445, 206)])
        pygame.draw.polygon(surface, (78, 82, 66),
                            [(425, 168), (450, 158), (545, 158), (575, 170),
                             (545, 190), (455, 190)])
        pygame.draw.polygon(surface, (104, 42, 38),
                            [(470, 156), (520, 156), (530, 184), (485, 190)])
        for lx in (415, 450, 495, 540, 585):
            pygame.draw.line(surface, (168, 176, 190), (lx, 205), (500, 262), 1)
        pygame.draw.polygon(surface, (16, 18, 24),
                            [(470, 250), (520, 270), (545, 360), (500, 390),
                             (470, 340)])
        for i in range(44):
            rng = random.Random(i)
            x, y = rng.randrange(WIDTH), SCENE_TOP + rng.randrange(_w.FILM_H)
            pygame.draw.line(surface, (150, 164, 186), (x, y),
                             (x, y - 16), 1)
        _fb_tag(surface, "DROP")
        return
    pygame.draw.polygon(surface, (18, 20, 26),
                        [(350, 400), (380, 370), (420, 365), (450, 395),
                         (450, 540), (350, 540)])
    _fb_rotor(surface, 760, 150 - t * 0.004, 0.8, t)
    _fb_heli(surface, 760, 172 - t * 0.004, 0.75, t, tilt=0.2)
    for i in range(8):
        pygame.draw.rect(surface, (226, 178, 108),
                         (180 + i * 34, 430, 5, 5))
    _fb_snow(surface, t, 6)
    _fb_tag(surface, "THE CROSSING // 02:40")


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


def _fb_radio(surface, t, variant):
    pygame.draw.rect(surface, (18, 16, 15), (0, SCENE_TOP, WIDTH, _w.FILM_H))
    pygame.draw.rect(surface, (28, 26, 24), (0, 330, WIDTH, 290))
    pygame.draw.rect(surface, (12, 20, 34), (640, 120, 260, 210))
    _fb_snow(surface, t, 9, 34)
    if variant == 3:
        pygame.draw.rect(surface, (40, 30, 22), (300, 340, 420, 30))
        pygame.draw.rect(surface, (26, 24, 22), (470, 300, 90, 150))
        pygame.draw.rect(surface, (20, 20, 20), (500, 260, 30, 60))
        pygame.draw.rect(surface, (120, 104, 74), (600, 110, 170, 160))
        _fb_tag(surface, "GUARD HQ // EMPTY OFFICE")
        return
    if variant == 2:
        for i in range(8):
            pygame.draw.rect(surface, (96, 86, 66), (250, 130 + i * 36, 460, 8))
        _fb_snow(surface, t, 10, 90)
        pygame.draw.rect(surface, (34, 32, 28), (380, 430, 140, 50))
        pygame.draw.circle(surface, (255, 170, 90), (450, 440), 4)
        _fb_tag(surface, "THE CALL")
        return
    pygame.draw.polygon(surface, (18, 18, 20),
                        [(250, 240), (310, 230), (330, 470), (255, 470)])
    pygame.draw.circle(surface, (96, 74, 60), (282, 222), 24)
    pygame.draw.rect(surface, (40, 38, 34), (620, 330, 180, 70))
    pygame.draw.circle(surface, (255, 160, 80), (700, 352), 4)
    _fb_tag(surface, "THE CALL" if variant else "WIRE // ROUTE 12")


def _fb_helicopter(surface, t):
    _fb_gradient(surface, (6, 8, 15), (30, 28, 42))
    # capital skyline beyond the dark hills
    for i, x in enumerate(range(30, WIDTH, 84)):
        h = 50 + (i * 41) % 120
        pygame.draw.rect(surface, (18 + i % 3, 20 + i % 3, 30 + i % 4),
                         (x, 330 - h, 66, h + 60))
        for j in range(3):
            pygame.draw.rect(surface, (222, 176, 106) if j != 1 else (176, 194, 222),
                             (x + 10 + j * 19, 340 - h + 12 + (i * 7) % 30, 4, 5))
    pygame.draw.polygon(surface, (13, 15, 21),
                        [(560, 340), (700, 270), (860, 320), (980, 250),
                         (WIDTH, 300), (WIDTH, 340)])
    pygame.draw.rect(surface, (24, 20, 30), (0, 330, WIDTH, 290))
    s = 0.9 - 0.12 * (t / 5200.0)
    _fb_rotor(surface, 640 + t * 0.016, 168 - t * 0.004, s, t)
    _fb_heli(surface, 640 + t * 0.016, 192 - t * 0.004, s, t, tilt=0.35)
    _fb_snow(surface, t, 11, 60)
    _fb_tag(surface, "THE LAST SIGNAL")


# ═══════════════════════════════════════════════════════════════════════════
# dispatch / registration
# ═══════════════════════════════════════════════════════════════════════════
M6_3D_SCENES = {
    "m6_insert_heli": _insert_heli,
    "m6_insert_jump": _insert_jump,
    "m6_insert_fall": _insert_fall,
    "m6_insert_ground": _insert_ground,
    "m6_boxcar_wide": _boxcar_wide,
    "m6_boxcar_notebook": _boxcar_notebook,
    "m6_boxcar_volkov": _boxcar_volkov,
    "m6_boxcar_biribel": _boxcar_biribel,
    "m6_boxcar_exit": _boxcar_exit,
    "m6_customs_terminal": _customs_terminal,
    "m6_radio_vasile": _radio_vasile,
    "m6_radio_maru": _radio_maru,
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
    "m6_insert_heli": _take("m6_insert_heli", _insert_fb("heli")),
    "m6_insert_jump": _take("m6_insert_jump", _insert_fb("jump")),
    "m6_insert_fall": _take("m6_insert_fall", _insert_fb("fall")),
    "m6_insert_ground": _take("m6_insert_ground", _insert_fb("ground")),
    "m6_boxcar_wide": _take("m6_boxcar_wide", _boxcar_fb("wide")),
    "m6_boxcar_notebook": _take("m6_boxcar_notebook", _boxcar_fb("notebook")),
    "m6_boxcar_volkov": _take("m6_boxcar_volkov", _boxcar_fb("volkov")),
    "m6_boxcar_biribel": _take("m6_boxcar_biribel", _boxcar_fb("biribel")),
    "m6_boxcar_exit": _take("m6_boxcar_exit", _boxcar_fb("exit")),
    "m6_customs_terminal": _take("m6_customs_terminal", _fb_terminal),
    "m6_radio_vasile": _take("m6_radio_vasile",
                             lambda surface, t: _fb_radio(surface, t,
                                                          _radio_variant())),
    "m6_radio_maru": _take("m6_radio_maru",
                           lambda surface, t: _fb_radio(surface, t, 1)),
    "m6_helicopter": _take("m6_helicopter", _fb_helicopter),
})
