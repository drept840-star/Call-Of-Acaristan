"""Mission 8 Duty 3D films: Approach (aerial over the estate, the gate) and
Liftoff (Biribel out on the terrace under Retardovici's climbing helicopter,
Retardovici in its door, Maru's gunship rising beside the terrace with the
white tactical LMG at the door).
"""
import math

import pygame

from core.config import WIDTH
from core.outfits import OUTFIT_GUARD
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from engine3d import Mesh, POSES, blend, box
from engine3d.core import m_apply, rot_y, v_add
from missions.m7 import raid3d as R
from missions.m8.duty import mansion_set as MS
from missions.m8.revenge import chase_set as CS

FILM = (640, int(_w.FILM_H * 640 / WIDTH))
BIRI = ("biribel", OUTFIT_GUARD)
BODI = ("ally", "bodi")
ALEX = ("ally", "alex")

_TLMG = []


def _tactical_lmg():
    if not _TLMG:
        try:
            from game.render3d_bridge import load_mesh_asset
            verts, faces = load_mesh_asset("tactical_lmg")
            m = Mesh()
            m.verts = [tuple(float(c) for c in v) for v in verts]
            m.faces = [(tuple(f[0]), tuple(f[1]), 2, True, False) for f in faces]
            _TLMG.append(m)
        except Exception:
            _TLMG.append(CS.lmg_body())
    return _TLMG[0]


def _k(t, start, length):
    x = max(0.0, min(1.0, (t - start) / float(length)))
    return x * x * (3.0 - 2.0 * x)


def _mix(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def _finish(surface, r, t, seed):
    buf = r.surface
    r.flush(buf)
    try:
        _fx.grade_cine(buf)
    except Exception:
        pass
    band = surface.subsurface((0, _w.SAFE_TOP, WIDTH, _w.FILM_H))
    _fx.present_crisp(buf, band)
    try:
        from cutscenes.post3d import apply_post
        apply_post(band, {"grain": 0.14, "vignette": 0.30}, int(t), "m8d_film_%d" % seed)
    except Exception:
        pass


def _guard_line(r, t):
    for gx, gz, gyaw in ((-3.4, -6.0, 180.0), (3.4, -6.0, 180.0), (-6.0, -26.0, 90.0), (6.0, -20.0, 270.0)):
        _w.actor(r, "guard", dict(POSES["ready"]), (gx, 0.0, gz), gyaw, int(t),
                 seed=int(abs(gx) * 10 + abs(gz)), rifle_on=True, flags=("os12",))


def approach_aerial(surface, t):
    """Aerial night orbit over Retardovici's estate: the drive, the house, the parked helicopter."""
    u = _k(t, 0, 5600)
    eye = _mix((36.0, 26.0, -54.0), (-30.0, 22.0, -40.0), u)
    tgt = _mix((2.0, 3.0, 6.0), (-2.0, 4.0, 18.0), u)
    r = MS.frame(eye, tgt, 50.0, t=int(t), size=FILM)
    del _w.LAST[:]
    MS.draw_dynamic_props(r, t)
    CS.put_helicopter(r, MS.HELIPAD_AT, MS.HELI_YAW, 0.0, 0.0, 0.0, 0.0)
    _guard_line(r, t)
    _finish(surface, r, t, 1)


def approach_gate(surface, t):
    """Low at the gate: Biribel, Bodi and Alex stack up, the lit house up the drive."""
    u = _k(t, 0, 4600)
    gz = MS.GATE_Z
    eye = _mix((0.6, 1.5, gz - 8.4), (0.2, 1.6, gz - 7.2), u)
    r = MS.frame(eye, (0.0, 1.5, -6.0), 46.0, t=int(t), size=FILM)
    del _w.LAST[:]
    MS.draw_dynamic_props(r, t)
    CS.put_helicopter(r, MS.HELIPAD_AT, MS.HELI_YAW, 0.0, 0.0, 0.0, 0.0)
    _guard_line(r, t)
    bp = _w.hum(BIRI, flags=("os12",))
    _w.actor(r, BIRI, R._held(bp, dict(POSES["ready"]), "os12", "ready", ("m8_biri_os12", "ready")),
             (-0.8, 0.0, gz - 4.0), 0.0, int(t), seed=93, rifle_on=True, flags=("os12",))
    _w.actor(r, BODI, dict(POSES["crouch"]), (-2.1, 0.0, gz - 2.6), 12.0, int(t),
             seed=61, rifle_on=True, flags=("os12",))
    _w.actor(r, ALEX, dict(POSES["crouch"]), (2.1, 0.0, gz - 2.6), 348.0, int(t),
             seed=62, rifle_on=True)
    _finish(surface, r, t, 2)


# Liftoff: the in-game rise ends ~15 m over the pad; the films pick it up there.
def _vip_heli(t, t0=0.0):
    """Retardovici's helicopter climbing away north-east from the terrace pad."""
    hx, hy, hz = MS.HELIPAD_AT
    u = max(0.0, (t - t0) / 1000.0)
    pos = (hx + 1.0 + 1.4 * u, hy + 5.0 + 2.2 * u, hz + 2.0 + 1.8 * u)
    return pos, MS.HELI_YAW - 25.0 - 4.0 * u, -8.0, 5.0


def _heli_lights(pos):
    """Terrace floods and the cabin glow, so the black helicopter reads at night."""
    return [{"pos": (pos[0], pos[1] - 2.5, pos[2]), "color": (196, 210, 255), "intensity": 1.1, "range": 12.0},
            {"pos": (pos[0], pos[1] + 0.9, pos[2]), "color": (255, 196, 140), "intensity": 0.8, "range": 5.0}]


def _draw_vip(r, t, pos, yaw, pitch, roll, aim=False):
    CS.put_helicopter(r, pos, yaw, pitch, roll, (t * 1.6) % 360.0, (t * 2.6) % 360.0)
    _b, _m, _t, info = CS.helicopter_parts()
    seat = CS._xf(info["gunner_seat"], pos, yaw, pitch, roll)
    if aim:
        pose = dict(POSES["stand"], rsh_p=80, rel=8, lsh_p=60, lsh_r=30, spine=-6)
    else:
        pose = dict(POSES["stand"], rsh_p=40, rel=30, lsh_p=70, lsh_r=30, spine=-6)
    _w.actor(r, "retardovici", pose, seat, yaw - 90.0, int(t), seed=12, amp=0.0, expression="angry")
    return seat


def liftoff_study(surface, t):
    """The terrace doors burst open: Biribel runs out under the climbing helicopter."""
    hx, hy, hz = MS.HELIPAD_AT
    # skids just off the pad, climbing: keeps him in frame over Biribel's shoulder
    u = t / 1000.0
    pos = (hx + 0.4 * u, hy + 0.9 + 1.3 * u, hz + 0.8 * u)
    yaw, pitch, roll = MS.HELI_YAW - 8.0 * u, -3.0 * min(1.0, u), 3.0 * min(1.0, u)
    # camera stays out on the terrace (never inside the study), heli kept high in frame
    bz = _mix((MS.HZ + 2.4,), (hz - 3.6,), _k(t, 0, 1900))[0]
    eye = _mix((2.0, hy + 1.5, MS.HZ + 0.9), (1.6, hy + 1.4, MS.HZ + 1.8), _k(t, 0, 2600))
    tgt = _mix((0.2, hy + 2.0, hz), (pos[0], hy + 2.9, hz + 1.0), _k(t, 600, 2600))
    r = MS.frame(eye, tgt, 54.0, lights=_heli_lights(pos), t=int(t), size=FILM)
    del _w.LAST[:]
    MS.draw_dynamic_props(r, t, cams_alive=False, front_open=True, study_open=True, terrace_open=True)
    _draw_vip(r, t, pos, yaw, pitch, roll)
    bp = _w.hum(BIRI, flags=("os12",))
    mode = "aim" if t > 1700 else "ready"
    pose = R._held(bp, dict(POSES["ready"]), "os12", mode, ("m8_biri_os12", mode))
    _w.actor(r, BIRI, pose, (0.0, hy, bz), 0.0, int(t), seed=93, rifle_on=True, flags=("os12",),
             expression="angry")
    _finish(surface, r, t, 3)


def liftoff_window(surface, t):
    """Low angle on the helicopter: Retardovici in the open door, pistol out."""
    pos, yaw, pitch, roll = _vip_heli(t, -4000.0)
    cx, cy, cz = pos
    _b, _m, _t, info = CS.helicopter_parts()
    seat = CS._xf(info["gunner_seat"], pos, yaw, pitch, roll)
    ox, oz = seat[0] - cx, seat[2] - cz
    n = max(0.01, math.hypot(ox, oz))
    ox, oz = ox / n, oz / n
    eye = (seat[0] + ox * 8.5 - oz * 1.5, seat[1] - 2.4, seat[2] + oz * 8.5 + ox * 1.5)
    key = {"pos": (eye[0] * 0.5 + seat[0] * 0.5, seat[1] - 0.5, eye[2] * 0.5 + seat[2] * 0.5),
           "color": (255, 214, 160), "intensity": 1.3, "range": 9.0}
    r = MS.frame(eye, (seat[0], seat[1] + 0.9, seat[2]), 40.0, lights=[key] + _heli_lights(pos),
                 t=int(t), size=FILM)
    del _w.LAST[:]
    MS.draw_dynamic_props(r, t, cams_alive=False, front_open=True, study_open=True, terrace_open=True)
    _draw_vip(r, t, pos, yaw, pitch, roll, aim=True)
    for k in range(2):
        r.add_sprite(CS._xf((0.0, 0.2, -2.0 - k), pos, yaw, pitch, roll),
                     _fx.beacon((255, 70, 50), 0.28, int(t), period_ms=900.0, phase=k * 450.0),
                     layer=_fx.FX_LAYER)
    _finish(surface, r, t, 4)


def liftoff_maru(surface, t):
    """Maru's gunship rises beside the terrace, LMG at the door; Biribel runs and jumps."""
    hx, hy, hz = MS.HELIPAD_AT
    u = _k(t, 0, 2600)
    hpos = _mix((24.0, hy - 7.0, hz + 6.0), (11.6, hy + 0.6, hz), u)
    gyaw = 180.0
    eye = _mix((-5.0, hy + 2.4, hz - 5.0), (-3.0, hy + 2.0, hz - 3.4), u)
    r = MS.frame(eye, (hpos[0] - 1.0, hpos[1] + 0.6, hpos[2]), 50.0, lights=_heli_lights(hpos),
                 t=int(t), size=FILM)
    del _w.LAST[:]
    MS.draw_dynamic_props(r, t, cams_alive=False, front_open=True, study_open=True, terrace_open=True)
    CS.put_helicopter(r, hpos, gyaw, -6.0 * (1.0 - u), 12.0 * (1.0 - u),
                      (t * 1.4) % 360.0, (t * 2.3) % 360.0)
    gun_at = v_add(hpos, m_apply(rot_y(gyaw), (1.05, 0.72, 0.35)))
    CS.put(r, "m8d_tlmg", _tactical_lmg, gun_at, gyaw + 90.0)
    # run to the balustrade, then the jump across to the open door
    run = _k(t, 1200, 2200)
    jump = _k(t, 3400, 900)
    bx = 1.0 + 7.2 * run + 1.6 * jump
    by = hy + 1.4 * math.sin(math.pi * min(1.0, jump * 1.2)) + (hpos[1] + 0.3 - hy) * jump
    bp = _w.hum(BIRI, flags=("os12",))
    pose = R._held(bp, dict(POSES["ready"]), "os12", "ready", ("m8_biri_os12", "ready"))
    if 0.0 < jump < 1.0:
        pose = blend(pose, dict(POSES["dive"]), 0.5)
    _w.actor(r, BIRI, pose, (bx, by, hz), 90.0, int(t), seed=93, rifle_on=True, flags=("os12",))
    _finish(surface, r, t, 5)


# --- The Crash -----------------------------------------------------------------
# Night chase set, past Route 12: Maru's gunship spins in beyond the ridge.

CRASH_AT = (CS.road_x(2200.0) + 40.0, 0.0, 2200.0)


def _talk(t, start, length):
    if t < start or t > start + length:
        return 0.0
    return abs(math.sin((t - start) * 0.011)) * 0.8


def _fire(r, at, t, seed, size=1.0):
    for i in range(3):
        p = (at[0] + (i - 1) * 0.9 * size, 0.4 + 0.3 * i, at[2] + 0.5 * (i % 2))
        r.add_sprite(p, _fx.glow((255, 120 + 30 * i, 50), 1.6 * size, int(t), flicker=0.8,
                                 seed=seed + i), layer=_fx.FX_LAYER)


def _fire_lights(at, t):
    f = 0.75 + 0.25 * math.sin(t * 0.021) * math.sin(t * 0.0137)
    return [{"pos": (at[0], 1.6, at[2]), "color": (255, 140, 60), "intensity": 1.3 * f, "range": 18.0}]


def crash_spin(surface, t):
    """The tail is gone: the gunship spins down toward the trees."""
    u = _k(t, 0, 3600)
    hpos = _mix((CRASH_AT[0] + 30.0, 34.0, CRASH_AT[2] - 40.0), (CRASH_AT[0], 2.0, CRASH_AT[2]), u * u)
    eye = (CRASH_AT[0] - 30.0, 8.0, CRASH_AT[2] - 70.0)
    r = CS.frame(eye, hpos, 46.0 - 8.0 * u, t=int(t), size=FILM, look="night")
    del _w.LAST[:]
    CS.put_helicopter(r, hpos, (t * 0.32) % 360.0, -10.0, 18.0 * math.sin(t * 0.004),
                      (t * 1.6) % 360.0, 0.0)
    r.add_sprite((hpos[0], hpos[1] + 0.6, hpos[2]),
                 _fx.glow((255, 150, 70), 1.4, int(t), flicker=0.9, seed=4), layer=_fx.FX_LAYER)
    _finish(surface, r, t, 6)


def crash_black(surface, t):
    """Impact. Black. Fire light creeps in at the bottom of the frame."""
    band = surface.subsurface((0, _w.SAFE_TOP, WIDTH, _w.FILM_H))
    band.fill((0, 0, 0))
    a = _k(t, 1400, 1600) * (0.6 + 0.4 * math.sin(t * 0.013))
    if a > 0.0:
        glow = int(70 * a)
        h = band.get_height()
        for i in range(6):
            pygame.draw.rect(band, (glow // (i + 1), glow // (2 * i + 3), 0),
                             (0, h - 40 * (i + 1), WIDTH, 40))


def crash_fire(surface, t):
    """Forest fire light. Maru pinned under the hull; he hands Biribel the rifle."""
    u = _k(t, 0, 6000)
    c = CRASH_AT
    eye = _mix((c[0] - 1.2, 1.4, c[2] + 3.6), (c[0] - 0.9, 1.2, c[2] + 3.0), u)
    r = CS.frame(eye, (c[0] + 0.2, 0.5, c[2]), 50.0, t=int(t), size=FILM, look="night",
                 lights=_fire_lights(c, t))
    del _w.LAST[:]
    CS.put_helicopter(r, (c[0] + 3.6, 0.0, c[2] - 1.2), 120.0, 6.0, 38.0, 0.0, 0.0, burned=True)
    _fire(r, (c[0] + 4.6, 0.0, c[2] - 2.6), t, 10, 1.4)
    _w.actor(r, "maru", dict(POSES["dead_back"], head_p=-25, rsh_p=60, rel=40),
             (c[0] + 0.9, 0.0, c[2] + 0.2), 90.0, int(t), seed=71, amp=0.2,
             mouth=_talk(t, 400, 3000))
    hand = _k(t, 2600, 1400)
    kneel = dict(POSES["kneel_over"], rsh_p=40 + 30 * hand, rel=40)
    _w.actor(r, BIRI, kneel, (c[0] - 0.6, 0.0, c[2] - 0.4), 70.0, int(t), seed=93, amp=0.15,
             rifle_on=hand > 0.5, mouth=_talk(t, 3600, 1600))
    _finish(surface, r, t, 7)


# --- Duty epilogue: the inauguration --------------------------------------------
# The courthouse stands on the east field where the Revenge funeral is staged.

CH = (150.0, 0.0, 600.0)
STONE = (196, 190, 176)
STEP_C = (172, 166, 154)
ROOF = (120, 116, 110)
TOP = 1.28


def _courthouse():
    from missions.m8.revenge import epilogue3d as E
    m = Mesh()
    x, _, z = CH
    for i in range(4):                                   # four steps, the front faces -z
        m.add(box(18.0 - i * 0.8, 0.32, 6.0 - i * 1.0, STEP_C, center=(x, 0.16 + 0.32 * i, z + i * 0.5)))
    for i in range(6):                                   # columns
        cx = x - 6.5 + i * 2.6
        m.add(box(0.7, 6.0, 0.7, STONE, center=(cx, TOP + 3.0, z + 0.6)))
        m.add(box(0.95, 0.3, 0.95, STEP_C, center=(cx, TOP + 0.15, z + 0.6)))
    m.add(box(17.0, 0.8, 3.0, STONE, center=(x, TOP + 6.4, z + 1.4)))
    m.add(box(15.0, 1.2, 2.6, ROOF, center=(x, TOP + 7.4, z + 1.4)))
    m.add(box(16.0, 7.0, 0.4, (150, 142, 128), center=(x, TOP + 3.5, z + 3.6)))
    m.add(box(2.4, 4.2, 0.2, (70, 54, 40), center=(x, TOP + 2.1, z + 3.38)))     # door
    m.add(box(1.0, 1.15, 0.5, (90, 70, 46), center=(x, TOP + 0.58, z - 0.9)))    # podium
    m.add(box(0.06, 0.32, 0.06, (40, 40, 44), center=(x, TOP + 1.3, z - 1.05)))  # microphone
    E._flag(m, x - 2.2, z - 0.6)
    E._flag(m, x + 2.2, z - 0.6)
    return m


VAS_AT = (CH[0], TOP, CH[2] - 0.3)
CROWD_Z = CH[2] - 7.5
BIRI_AT = (CH[0] - 1.4, 0.0, CROWD_Z - 1.0)
MARU_AT = (CH[0] - 0.5, 0.0, CROWD_Z - 1.1)
BODI_AT = (CH[0] - 1.8, 0.0, CROWD_Z - 2.3)
ALEX_AT = (CH[0] - 0.8, 0.0, CROWD_Z - 2.4)


def _inaug(eye, tgt, fov, t):
    lights = [{"pos": (CH[0], 6.0, CH[2] - 8.0), "color": (255, 226, 190), "intensity": 0.5, "range": 30.0}]
    r = CS.frame(eye, tgt, fov, t=int(t), size=FILM, look="dawn", lights=lights)
    del _w.LAST[:]
    CS.put(r, "m8d_courthouse", _courthouse, (0.0, 0.0, 0.0))
    return r


def _crowd(r, t, mains=True):
    for i in range(28):
        row, col = divmod(i, 7)
        x = CH[0] - 6.0 + col * 2.0 + (row % 2) * 0.9
        z = CROWD_Z - row * 1.3 + 0.3 * math.sin(i * 1.7)
        if mains and abs(x - (CH[0] - 1.1)) < 1.6 and row < 2:
            continue
        _w.actor(r, "civilian", dict(POSES["stand"]), (x, 0.0, z), 0.0, int(t), seed=500 + i,
                 amp=0.3, mouth=0.0)
    if not mains:
        return
    _w.actor(r, BIRI, dict(POSES["stand"]), BIRI_AT, 0.0, int(t), seed=93, amp=0.15)
    _w.actor(r, "maru", dict(POSES["stand"], lsh_p=24, rsh_p=24), MARU_AT, 352.0, int(t),
             seed=71, amp=0.2)
    for side in (-0.42, 0.42):                           # crutches
        x0 = MARU_AT[0] + side
        r.add_line3d((x0, 0.0, MARU_AT[2] + 0.15), (x0, 1.2, MARU_AT[2] + 0.05), (90, 90, 96))
    _w.actor(r, BODI, dict(POSES["stand"]), BODI_AT, 6.0, int(t), seed=61, amp=0.2)
    _w.actor(r, ALEX, dict(POSES["stand"]), ALEX_AT, 354.0, int(t), seed=62, amp=0.2)


def _vasile(r, t, mouth=0.0, **pose):
    _w.actor(r, "vasile", dict(POSES["stand"], **pose), VAS_AT, 180.0, int(t), seed=33,
             amp=0.1, mouth=mouth)


def inauguration(surface, t):
    """State TV: the courthouse steps at dawn, the oath."""
    u = _k(t, 0, 6000)
    eye = _mix((CH[0] + 10.0, 5.0, CH[2] - 22.0), (CH[0] + 6.0, 4.0, CH[2] - 17.0), u)
    r = _inaug(eye, (CH[0], 2.6, CH[2]), 44.0, t)
    _vasile(r, t)
    _crowd(r, t)
    _finish(surface, r, t, 8)
    from cutscenes.m8films import _tv
    _tv(surface, t, "INTERIM PRESIDENT VASILE TAKES THE OATH")


def vasile_speech(surface, t):
    """Close on Vasile at the podium."""
    u = _k(t, 0, 5000)
    eye = _mix((CH[0] + 1.4, 2.9, CH[2] - 4.4), (CH[0] + 1.0, 2.95, CH[2] - 3.8), u)
    r = _inaug(eye, (VAS_AT[0], VAS_AT[1] + 1.55, VAS_AT[2]), 34.0, t)
    _vasile(r, t, mouth=_talk(t, 300, 3600))
    _finish(surface, r, t, 9)


def crowd(surface, t):
    """In the crowd: Biribel, Maru on crutches beside him, Bodi and Alex a row behind."""
    u = _k(t, 0, 5600)
    eye = _mix((CH[0] - 0.4, 1.7, CROWD_Z + 2.6), (CH[0] - 0.9, 1.65, CROWD_Z + 2.2), u)
    r = _inaug(eye, (CH[0] - 1.1, 1.4, CROWD_Z - 1.6), 42.0, t)
    _crowd(r, t)
    _finish(surface, r, t, 10)


def eyes(surface, t):
    """Vasile finds Biribel in the crowd. A tiny nod."""
    nod = 8.0 * _k(t, 2200, 500) * (1.0 - _k(t, 2900, 500))
    eye = (VAS_AT[0] - 0.5, VAS_AT[1] + 1.95, VAS_AT[2] - 2.6)
    r = _inaug(eye, (VAS_AT[0], VAS_AT[1] + 1.85, VAS_AT[2]), 30.0, t)
    look = R._wrap(R._yaw(BIRI_AT[0] - VAS_AT[0], BIRI_AT[2] - VAS_AT[2]) - 180.0)
    _vasile(r, t, head_y=look * 0.6, head_p=nod)
    _finish(surface, r, t, 11)


def biribel_vo(surface, t):
    """Biribel in the crowd, face on, while the speech goes on behind him."""
    u = _k(t, 0, 6000)
    eye = _mix((BIRI_AT[0] + 0.2, 1.7, BIRI_AT[2] + 2.2), (BIRI_AT[0] + 0.1, 1.68, BIRI_AT[2] + 1.8), u)
    r = _inaug(eye, (BIRI_AT[0], 1.6, BIRI_AT[2]), 34.0, t)
    _crowd(r, t)
    _finish(surface, r, t, 12)


def title_card(surface, t):
    """The courthouse small in the dawn; the title."""
    from core.config import font_title
    eye = (CH[0] + 30.0, 9.0 + 2.0 * _k(t, 0, 6000), CH[2] - 44.0)
    r = _inaug(eye, (CH[0], 3.0, CH[2]), 40.0, t)
    _vasile(r, t)
    _crowd(r, t, mains=False)
    _finish(surface, r, t, 13)
    a = _k(t, 500, 1800)
    img = font_title.render("CALL OF ACARISTAN", True, (232, 226, 210))
    img.set_alpha(int(255 * a))
    surface.blit(img, ((WIDTH - img.get_width()) // 2, _w.SAFE_TOP + int(_w.FILM_H * 0.38)))
