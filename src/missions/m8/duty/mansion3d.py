"""Mission 8 Duty - Phase 2: The Mansion (3D third-person fight).

Storm Retardovici's estate - the same house the Revenge funeral films - with
Bodi and Alex, through five areas, each a checkpoint:
- THE GATES (cp 0): up the hedged drive, then the forecourt: staff cars that
  burn, riflemen on the balconies, a gunner on the portico roof, and the
  breachers that pour out of the front doors.
- THE GRAND HALL (cp 1): the double-height hall, gallery riflemen above, two
  chandeliers that can be shot down onto the guards below, Andrei M. in the
  security room behind the hall.
- THE GALLERY (cp 2): Bodi and Alex hold the hall while Biribel climbs the
  grand staircase into the counter-push along the galleries.
- THE STUDY (cp 3): kick the study door; his personal guard waits inside.
- THE HELIPAD (cp 4): the terrace behind the study, his last men, and his
  helicopter spinning up.  It lifts off when the terrace is clear or the
  rotors are up to speed, then Liftoff.
Weapons: OS-12 (1), Fallow 12 (2), Q/wheel swaps.
"""
import math
import random
import traceback

import pygame
from engine3d.core import v_len, v_norm
from core.config import HEIGHT, WIDTH, audio, draw_vignette
from core.outfits import OUTFIT_GUARD
from core.state import STATE
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from cutscenes import revive3d as REV
from cutscenes import m7world3d as W7
from engine3d import Mesh, POSES, blend, box, clamp, disc_xz
from engine3d.core import m_apply, m_mul, rot_x, rot_y, rot_z, v_add
from engine.anim import gait_cycle_m, locomotion_pose, mask_pose
from engine.render3d import VehicleDestructionManager
from engine3d.hold import POLES, hold_cached as _hold_cached, solve_arm_safe as _solve_arm_safe
from game.vehicle_fx import default_vehicle_fx
from missions.m7 import raid3d as R
from missions.m7 import raid_world as RW
from missions.m8.revenge import chase3d as C
from missions.m8.revenge import chase_set as CS
from missions.m8.revenge import trap3d as T

from . import mansion_brain as B
from . import mansion_hud as HUD
from . import mansion_set as MS
from . import mansion_props as MP
from . import mansion_world as W

WPN_SPECS = {
    "rifle": dict(label="OS-12", cal="5.56X45", kind="stick", mag=30, reserve0=120,
                  cap=180, gap=0.115, reload_s=1.45, fov_ads=44.0),
    "shotgun": dict(label="FALLOW 12", cal="12GA", kind="shell", mag=6, reserve0=30,
                    cap=42, gap=0.92, reload_s=2.2, fov_ads=48.0),
}
WPN_ORDER = ("rifle", "shotgun")
GF, FF = MS.GF, MS.FF
# cp: (x, z, yaw, y)
CP_STATE = {
    0: (0.0, -41.0, 0.0, 0.0),
    1: (0.0, 4.6, 0.0, GF),
    2: (0.0, 16.2, 0.0, GF),
    3: (0.0, 27.4, 0.0, FF),
    4: (0.0, 40.2, 0.0, FF),
}
AREAS = {
    0: ("THE GATES", "Retardovici's estate  -  the drive and the forecourt"),
    1: ("THE GRAND HALL", "Ground floor  -  the hall, the galleries, the security room"),
    2: ("THE GALLERY", "Up the grand staircase"),
    3: ("THE STUDY", "First floor  -  his rooms"),
    4: ("THE HELIPAD", "The terrace  -  stop the helicopter"),
}
LAST_CP = 4
STEP_M = 0.8
CAR_HP = 110.0
CAR_BLAST_R = 5.5
CHAND_R = 0.95
HELI_SPIN = 75.0
LIFT_S = 4.2
KICK_DUR = 0.78
KICK_HIT_S = 0.25
KICK_LOCK_S = 0.54


ANDREI_SHOT_S, ANDREI_HIT_S, ANDREI_ZAP_S = B.ANDREI_SHOT_S, B.ANDREI_HIT_S, B.ANDREI_ZAP_S
ANDREI_SIT_S = 3.2        # slid down the rack onto the floor
ANDREI_DOWN_S = 3.8       # tipped over onto his side at the rack's foot
ANDREI_RACK_DX = -3.75    # root travel from ANDREI_AT to back-against-the-rack

_A_AIM = dict(POSES["stand"], rsh_p=68, rel=22, lsh_p=42, lsh_r=28, spine=-4)
_A_RECOIL = dict(POSES["stand"], spine=-16, head_p=-24, rsh_p=162, rsh_r=10, rel=8,
                 lsh_p=96, lsh_r=52, lel=40, lhip_p=-10, rkn=14)
_A_SHOT = dict(POSES["stand"], body_p=-8, spine=-18, head_p=-28, rsh_p=36, rsh_r=44, rel=28,
               lsh_p=46, lsh_r=40, lel=52, lhip_p=-12, rkn=18)
_A_PINNED = dict(POSES["stand"], body_p=-9, spine=-18, head_p=-34, lsh_p=34, lsh_r=92, lel=16,
                 rsh_p=38, rsh_r=92, rel=18, lhip_r=11, rhip_r=11)
# legs out flat: bent knees would put the feet lowest and hold his seat off the floor
_A_SIT = dict(POSES["stand"], body_p=-8, spine=22, head_p=40, head_y=16, lhip_p=88, lhip_r=12,
              lkn=6, rhip_p=86, rhip_r=8, rkn=10, lank=20, rank=20, lsh_p=6, lsh_r=26,
              lel=18, rsh_p=12, rsh_r=30, rel=28)
_A_DOWN = dict(POSES["dead_side"], lhip_p=46, lkn=34, rhip_p=58, rkn=52, head_p=30)

_NOTE_MESH = None
_WOUND_CACHE = {}
_HEAD_WOUND_CACHE = {}


def _banknote_mesh():
    global _NOTE_MESH
    if _NOTE_MESH is None:
        m = Mesh()
        m.face([(-0.075, 0.0, -0.039), (0.075, 0.0, -0.039), (0.075, 0.0, 0.039), (-0.075, 0.0, 0.039)],
               (128, 136, 114), layer=2, double=True)
        m.face([(-0.024, 0.001, -0.038), (0.024, 0.001, -0.038), (0.024, 0.001, 0.038), (-0.024, 0.001, 0.038)],
               (74, 86, 68), layer=2, double=True)
        _NOTE_MESH = m
    return _NOTE_MESH


def _wound_patch_mesh(shot_blood, charred, fz=0.142):
    """Flush torso decals in humanoid S-space (origin at pelvis)."""
    key = (bool(shot_blood), bool(charred), round(float(fz), 3))
    got = _WOUND_CACHE.get(key)
    if got is None:
        m = Mesh()
        flat_f = ("back", "left", "right", "top", "bottom")
        flat_b = ("front", "left", "right", "top", "bottom")
        zf = fz + 0.003
        zb = -(fz + 0.003)
        if charred:
            m.add(box(0.20, 0.24, 0.004, (22, 18, 18), center=(0.0, 0.34, zb), skip=flat_b))
            m.add(box(0.14, 0.17, 0.004, (32, 22, 20), center=(0.0, 0.35, zf), skip=flat_f))
        if shot_blood:
            blood, clot = (86, 9, 13), (42, 5, 8)
            m.add(box(0.11, 0.14, 0.004, blood, center=(0.03, 0.36, zf), skip=flat_f), m=rot_z(8))
            m.add(box(0.045, 0.055, 0.004, clot, center=(0.04, 0.37, zf + 0.0015), skip=flat_f))
            for dx_, ln in ((-0.01, 0.08), (0.04, 0.11), (0.08, 0.06)):
                m.add(box(0.014, ln, 0.004, blood, center=(dx_, 0.29 - ln * 0.5, zf + 0.0015), skip=flat_f))
            m.add(box(0.13, 0.16, 0.004, blood, center=(-0.02, 0.37, zb - 0.001), skip=flat_b))
            m.add(box(0.04, 0.04, 0.004, clot, center=(-0.02, 0.38, zb - 0.002), skip=flat_b))
        got = _WOUND_CACHE[key] = m
    return got


def _head_wound_mesh(hw=1.0):
    """Flush skull decals in humanoid H-space (origin at neck)."""
    key = round(float(hw), 3)
    got = _HEAD_WOUND_CACHE.get(key)
    if got is None:
        m = Mesh()
        flat_f = ("back", "left", "right", "top", "bottom")
        flat_b = ("front", "left", "right", "top", "bottom")
        blood, clot = (86, 9, 13), (42, 5, 8)
        m.add(box(0.062, 0.066, 0.004, blood, center=(0.024 * hw, 0.148, 0.123), skip=flat_f))
        m.add(box(0.028, 0.032, 0.004, clot, center=(0.026 * hw, 0.150, 0.124), skip=flat_f))
        for dx_, ln in ((0.006, 0.065), (0.028, 0.085), (0.048, 0.050)):
            m.add(box(0.011, ln, 0.004, blood, center=(dx_ * hw, 0.112 - ln * 0.5, 0.1235), skip=flat_f))
        m.add(box(0.095, 0.105, 0.004, blood, center=(-0.01 * hw, 0.15, -0.103), skip=flat_b))
        m.add(box(0.042, 0.048, 0.004, clot, center=(-0.01 * hw, 0.15, -0.104), skip=flat_b))
        got = _HEAD_WOUND_CACHE[key] = m
    return got


def _dropped_pistol_xform(drop_age, p0, base_yaw, floor_y):
    """Ballistic drop and rest transform for Andrei's knocked-free pistol."""
    vx, vy0, vz = 1.15, 0.95, 0.55
    g = 9.8
    y0 = max(floor_y, p0[1])
    t1 = (vy0 + math.sqrt(vy0 * vy0 + 2.0 * g * (y0 - floor_y))) / g
    vy1 = abs(vy0 - g * t1) * 0.26
    t_b = 2.0 * vy1 / g
    if drop_age <= t1:
        px = p0[0] + vx * drop_age
        py = y0 + vy0 * drop_age - 0.5 * g * drop_age * drop_age
        pz = p0[2] + vz * drop_age
        rot = m_mul(rot_y(base_yaw + 140.0 * drop_age),
                    m_mul(rot_x(-380.0 * drop_age), rot_z(min(90.0, 150.0 * drop_age))))
    elif drop_age < t1 + t_b:
        u = drop_age - t1
        px = p0[0] + vx * (t1 + u * 0.45)
        py = floor_y + vy1 * u - 0.5 * g * u * u
        pz = p0[2] + vz * (t1 + u * 0.45)
        rot = m_mul(rot_y(base_yaw + 140.0 * t1 + 45.0 * u), rot_z(90.0))
    else:
        px = p0[0] + vx * (t1 + t_b * 0.45)
        py = floor_y
        pz = p0[2] + vz * (t1 + t_b * 0.45)
        rot = m_mul(rot_y(base_yaw + 140.0 * t1 + 45.0 * t_b), rot_z(90.0))
    px = clamp(px, -12.35, -4.15)
    pz = clamp(pz, 26.55, 35.15)
    return (px, py, pz), rot


def _andrei_death_anim(age, cause="misfire", hit_zone="chest", shot_yaw=90.0, had_gun=True):
    """Pose, root offset (dx, 0, dz) and yaw for Andrei M.'s death: the pistol
    goes off into the ceiling, he backpedals into the server rack, it pins and
    shakes him, then he slides down it and tips over onto the floor."""
    hit_s, zap_s, sit_s, down_s = B.andrei_timings(cause)
    if cause == "player":
        yaw_k = R._ease(clamp(age / 0.40, 0.0, 1.0))
        yaw = shot_yaw + R._wrap(90.0 - shot_yaw) * yaw_k
        if age < hit_s:
            u = clamp(age / max(0.01, hit_s), 0.0, 1.0)
            head_k = -40.0 if hit_zone == "head" else -26.0
            if u < 0.14:
                jolt = R._ease(u / 0.14)
                travel = 0.08 * jolt
                ph = 0.0
            else:
                s = (u - 0.14) / 0.86
                travel = 0.08 + 0.92 * (s * s * (1.45 - 0.45 * s))
                ph = s * math.pi * 4.0
            sw = math.sin(ph)
            stagger = dict(_A_SHOT, head_p=head_k, lhip_p=-22.0 * sw, rhip_p=22.0 * sw,
                           lkn=12.0 + 24.0 * max(0.0, -sw), rkn=12.0 + 24.0 * max(0.0, sw),
                           lift=0.020 * abs(sw))
            start_pose = _A_AIM if had_gun else POSES["stand"]
            return blend(start_pose, stagger, R._ease(min(1.0, age / 0.18))), (ANDREI_RACK_DX * travel, 0.0, 0.0), yaw
    else:
        if age < ANDREI_SHOT_S:
            u = R._ease(age / ANDREI_SHOT_S)
            return blend(_A_AIM, dict(_A_AIM, rsh_p=86, spine=-8, lsh_p=70, lsh_r=40), u), (0.0, 0.0, 0.0), 90.0
        if age < ANDREI_SHOT_S + 0.2:
            u = R._ease((age - ANDREI_SHOT_S) / 0.2)
            return blend(dict(_A_AIM, rsh_p=86), _A_RECOIL, u), (0.0, 0.0, 0.0), 90.0
        if age < hit_s:
            t0 = ANDREI_SHOT_S + 0.2
            k = (age - t0) / (hit_s - t0)
            ph = k * math.pi * 4.0                          # four stumbling steps backwards
            sw = math.sin(ph)
            flail = math.sin(age * 19.0)
            pose = dict(_A_RECOIL, body_p=-7.0 - 5.0 * k, spine=-12.0, head_p=-12.0,
                        lhip_p=-26.0 * sw, rhip_p=26.0 * sw,
                        lkn=10.0 + 30.0 * max(0.0, -sw), rkn=10.0 + 30.0 * max(0.0, sw),
                        rsh_p=150.0 + 18.0 * flail, rsh_r=14.0 + 10.0 * flail,
                        lsh_p=90.0 - 40.0 * flail, lsh_r=60.0, lel=46.0,
                        lift=0.03 * abs(math.sin(ph)))
            return pose, (ANDREI_RACK_DX * k * k * (1.6 - 0.6 * k), 0.0, 0.0), 90.0
    if age < zap_s:
        j = math.sin(age * 71.0)
        k = math.sin(age * 53.0 + 1.3)
        sp = math.sin(age * 41.0)
        pose = dict(_A_PINNED, body_p=-9.0 + 4.0 * k, spine=-18.0 + 9.0 * j,
                    head_p=-34.0 + 16.0 * k, head_y=18.0 * j,
                    lsh_p=34.0 + 22.0 * k, lsh_r=92.0 + 16.0 * j, lel=16.0 + 24.0 * k,
                    rsh_p=38.0 - 22.0 * j, rsh_r=92.0 - 16.0 * k, rel=18.0 + 24.0 * j,
                    lhip_p=18.0 + 18.0 * j, rhip_p=18.0 - 18.0 * k,
                    lkn=18.0 + 22.0 * abs(k), rkn=18.0 + 22.0 * abs(j),
                    lank=28.0 * j, rank=-28.0 * k,
                    lift=0.02 + 0.035 * abs(sp))
        return pose, (ANDREI_RACK_DX + 0.025 * j, 0.0, 0.025 * k), 90.0
    if age < sit_s:
        u = R._ease((age - zap_s) / (sit_s - zap_s))
        return blend(_A_PINNED, _A_SIT, u), (ANDREI_RACK_DX, 0.0, 0.0), 90.0
    u = clamp((age - sit_s) / (down_s - sit_s), 0.0, 1.0)
    return blend(_A_SIT, _A_DOWN, u * u), (ANDREI_RACK_DX + 0.25 * u, 0.0, 0.0), 90.0


def _smoke_puff_fn(radius_m, alpha, warmth, variant):
    def draw(s, sx, sy, scale, z):
        if scale < 0.35:
            return
        rad = max(2, min(64, int(radius_m * scale)))
        rad = max(2, (rad // 2) * 2)
        a = max(4, min(220, (int(alpha) // 16) * 16))
        if a < 16:
            return
        img = W7._smoke_img(rad, a, warmth, variant)
        s.blit(img, (int(sx - rad), int(sy - rad)))
    draw.bounds_m = (radius_m * 1.25, radius_m * 1.25)
    draw.bounds_cap_px = (130, 130)
    return draw


class _OneEnemy:
    """Brain stand-in so the shared enemy drawer sees one enemy at a time."""

    def __init__(self, brain, e):
        self._b = brain
        self.enemies = [e]

    def __getattr__(self, name):
        return getattr(self._b, name)


class MansionScene:
    MAG = WPN_SPECS["rifle"]["mag"]
    RELOAD_S = WPN_SPECS["rifle"]["reload_s"]
    HELI_SPIN = HELI_SPIN

    _grab = R.RaidScene._grab
    set_paused = R.RaidScene.set_paused
    _snd = R.RaidScene._snd
    say = R.RaidScene.say
    tracer = R.RaidScene.tracer
    hp = R.RaidScene.hp
    hp_max = R.RaidScene.hp_max
    _aim_ray = R.RaidScene._aim_ray
    _player_pose = R.RaidScene._player_pose
    _guard_pose = R.RaidScene._guard_pose
    _project = R.RaidScene._project
    _ground_move = R.RaidScene._move
    _anim_ctl = R.RaidScene._anim_ctl
    _wall_probe_dist = R.RaidScene._wall_probe_dist
    _update_wall_k = R.RaidScene._update_wall_k

    def __init__(self):
        self._active = False
        self.paused = False
        self.done = False
        self.result = None
        self.audio = None
        self.t = 0.0
        self._last_snd = -9.0
        self._pistol_mesh = None
        self._money_mesh = None
        self._floor_hint = 0.0
        self._setup(int(getattr(STATE, "m8_mansion_cp", 0) or 0))

    def begin(self):
        self.t = 0.0
        self.done = False
        self.result = None
        self._active = True
        self.paused = False
        STATE.m8_mansion_active = True
        try:
            from .. import m8_audio as _m8_audio
            self.audio = _m8_audio.instance(audio)
            self.audio.warm()
        except Exception:
            self.audio = None
        self._setup(int(getattr(STATE, "m8_mansion_cp", 0) or 0))
        self._grab(True)
        try:
            self._warm()
        except Exception:
            traceback.print_exc()

    def _warm(self):
        self._pistol_mesh = MS.pistol_mesh()
        self._money_mesh = MS.money_bundle(2)
        self._money_mesh_1 = MS.money_bundle(1)
        _banknote_mesh()
        _wound_patch_mesh(True, True, 0.142)
        _head_wound_mesh(1.0)
        _hold_cached(_w.hum("andrei_m"), dict(POSES["ready"]), "pistol", "pistol_aim", key=("andrei_pistol", "aim"))
        hum = _w.hum(("biribel", OUTFIT_GUARD), flags=("shotgun", "nopump"))
        for mode in ("ready", "aim"):
            R._sg_holds(hum, mode, ("m7player_sg", mode))
        R._wall_down_hold(hum, "shotgun", ("m7player_sg", "wall"))
        R._sg_reload_keys(hum)
        rhum = _w.hum(("biribel", OUTFIT_GUARD), flags=("os12", "nomag"))
        for mode in ("ready", "aim"):
            R._held(rhum, POSES["ready"], "os12", mode, ("m8_biri_os12", mode))
        R._wall_down_hold(rhum, "os12", ("m8_biri_os12", "wall"))
        T._os12_reload_keys(rhum)
        T._os12_mag_mesh_cached()
        aim_st = dict(blend(POSES["stand"], "aim", 0.85), twist=R.AIM_TWIST, head_y=-0.8 * R.AIM_TWIST)
        for name, gun, flags in (("bodi", "os12", ("os12",)), ("alex", "m7rifle", ())):
            ahum = _w.hum(("ally", name), flags=flags)
            _hold_cached(ahum, dict(POSES["ready"]), gun, "ready", key=("m8d_" + name, "ready"))
            for i in range(-4, 5):
                sl = i / 10.0
                _hold_cached(ahum, aim_st, gun, "aim", aim=(0.0, 1.45 + 10.0 * sl, 10.0), key=("m8d_" + name, sl))
        g_pose = dict(POSES["ready"])
        for gkind in set(R.GUARD_VIEW) | {"heavy"}:
            gh = _w.hum(("guard", gkind), True, flags=("os12",))
            _hold_cached(gh, g_pose, "os12", "ready", key=("m8_guard", gkind))
        for _x, _z, _yaw, paint in MS.CARS:
            MS.car_mesh(paint, False)
            MS.car_mesh(paint, True)
        MS.chandelier_mesh()
        MP.study_door_leaf(-1)
        MP.study_door_leaf(1)
        MS._crate_parts()
        _w.hum("retardovici")
        MS.renderer()
        self.world.nav()
        REV.warm()

    def active(self):
        return self._active

    def finish(self, result="win"):
        if self.done:
            return False
        self.done = True
        self.result = result
        self._active = False
        STATE.m8_mansion_active = False
        self._grab(False)
        if self.audio is not None:
            try:
                self.audio.stop_loops()
            except Exception:
                pass
        from .. import flow as _flow
        return _flow.on_mansion_done(result)

    def _setup(self, cp):
        cp = max(0, min(LAST_CP, cp))
        self.cp = cp
        REV.reset(self)
        STATE.m8_mansion_cp = cp
        self.world = W.World()
        self.px, self.pz, self.yaw, y = CP_STATE[cp]
        self.py = self.world.surface_y(self.px, self.pz, y)
        self.world.cur_y = self.py
        self.world.front_open = cp >= 1
        self.world.study_open = cp >= 4
        self.world.terrace_open = cp >= 4
        self.cams_alive = cp < 2
        self.cars = [dict(x=x, z=z, yaw=yaw, paint=paint, hp=CAR_HP, burned=False, boom_t=-9.0)
                     for x, z, yaw, paint in MS.CARS]
        self.world.cars = [W.car_box(c["x"], c["z"], c["yaw"]) for c in self.cars]
        self.chand = [dict(x=x, y=y, z=z, state="up", vy=0.0, t0=-9.0) for x, y, z in MS.CHANDELIERS]
        self.weapon = "rifle"
        self.wpns = {k: [sp["mag"], sp["reserve0"]] for k, sp in WPN_SPECS.items()}
        self._sync_weapon_attrs()
        self.pitch = -2.0
        self.body_yaw = self.yaw
        self.vel = (0.0, 0.0)
        self.stride = 0.0
        self._step_i = 0
        self.pmoving = False
        self.sprint = False
        self.firing = False
        self.aiming = False
        self.ads = 0.0
        self.gun_up = 0.0
        self.wall_k = 0.0
        self.swapping = 0.0
        self._swap_dur = T.SWAP_S
        self._swap_from = self.weapon
        self._swap_to = self.weapon
        self._swap_snd_at = 1e9
        self.reloading = 0.0
        self._reload_dur = self.RELOAD_S
        self._reload_n = 0
        self._reload_dry = False
        self._reload_t_in = ()
        self._reload_pump_at = 1e9
        self._shell_i = 0
        self._pump_done = False
        self.pump_at = -9.0
        self.pump_snd_at = 1e9
        self.last_fire = -9.0
        self.last_flash = -9.0
        self.flash_seed = 0
        self._flash_basis = None
        self.heat = 0.0
        self.recoil = 0.0
        self.cam_kick = 0.0
        self.slowmo_until = -1.0
        self.hurt = 0.0
        self.last_hurt = -9.0
        self.hit_mark = -9.0
        self.dmg_marks = []
        self.tracers = []
        self.sparks = []
        self.impacts = []
        self.flashes = []
        self.booms = []
        self.lines = []
        self.debris = []
        self.smoke_puffs = []
        self.veh_fx = VehicleDestructionManager(seed=601 + cp * 23, fx=default_vehicle_fx(_fx))
        self.scorches = [(MS.ANDREI_RACK_AT[0] + 0.48, GF + 0.026, MS.ANDREI_RACK_AT[2], 1.35)] if cp >= 2 else []
        self.scattered_cash = []
        self.cash_bricks = []
        self.cash_notes = []
        self.blood_drops = []
        self._notes_settled_mesh = None
        if getattr(self, "_fx_pool", None) is not None:
            self._fx_pool.clear()
        self.crates_taken = set()
        self.crate_anims = {}
        self.crate_pops = set()
        self.crate_act = None
        self.study_kick_t = None
        self._kick_opened = False
        self._kick_p0 = None
        self._kick_yaw0 = 0.0
        self.toast = None
        self.cp_toast = 0.0
        self.area_card = (self.t, ) + AREAS[cp]
        self.kills = 0
        self.dying = False
        self.death_t = 0.0
        self.death_msg = ""
        self.hold = 0.0
        self._e_prev = False
        self.marker_screen = None
        self._muzzle = None
        self.turn = None
        self.doors_at = None
        self.heli_t0 = None
        self.lift_t0 = None
        self.rotor = 0.0
        self._phase_at = self.t
        self.brain = B.Brain(self, cp)
        p = STATE.player
        if p is not None:
            p.hp = getattr(p, "max_hp", 115) or 115
        if cp == 0:
            self.phase = "drive"
            self.brain.start_wave(1)
            self.say("ALEX", "Gate's open. Guards on the drive - stay off the gravel!", 3.2)
        elif cp == 1:
            self.phase = "hall"
            self.brain.start_wave(3)
            self.say("BODI", "Hall! Watch the galleries - they've got the high ground.", 3.2)
        elif cp == 2:
            self.phase = "gallery"
            self.brain.start_wave(4)
            self.say("BODI", "We hold the hall. Get up those stairs!", 3.0)
        elif cp == 3:
            self.phase = "study_door"
            self.say("VASILE", "His study is behind that door. Kick it.", 2.8)
        else:
            self._start_helipad()

    def _start_helipad(self):
        self.phase = "helipad"
        self.heli_t0 = self.t
        self.brain.start_wave(6)
        self.say("RETARDOVICI", "Kill him! Somebody kill him - I pay you enough!", 3.2)

    def _sync_weapon_attrs(self):
        sp = WPN_SPECS[self.weapon]
        self.MAG = sp["mag"]
        self.RELOAD_S = sp["reload_s"]
        self.mag, self.reserve = self.wpns[self.weapon]

    def _switch_weapon(self, target=None):
        if target is None:
            want = WPN_ORDER[(WPN_ORDER.index(self.weapon) + 1) % len(WPN_ORDER)]
        else:
            want = target
        if want == self.weapon or want not in self.wpns:
            return
        vis_weapon = self.weapon
        if self.swapping > 0.0:
            elapsed = self._swap_dur - self.swapping
            if elapsed < self._swap_dur * 0.5:
                vis_weapon = self._swap_from
        self.wpns[self.weapon] = [self.mag, self.reserve]
        self._swap_from = vis_weapon
        self._swap_to = want
        self.weapon = want
        self.reloading = 0.0
        self._reload_n = 0
        self._reload_dry = False
        self._reload_t_in = ()
        self._pump_done = False
        self.firing = False
        self.heat = 0.0
        self.last_flash = -9.0
        self.pump_at = -9.0
        self.pump_snd_at = 1e9
        self._sync_weapon_attrs()
        dur = T.SWAP_S * 0.65
        self._swap_dur = dur
        self.swapping = dur
        self._swap_snd_at = self.t + dur * 0.5
        self._snd("pickup")
        self.toast = (self.t, WPN_SPECS[want]["label"])

    def _begin_reload(self):
        if self.reloading or self.swapping > 0.0 or self.mag >= self.MAG or self.reserve <= 0:
            return
        self._shell_i = 0
        self._pump_done = False
        if self.weapon == "shotgun":
            n = min(self.MAG - self.mag, self.reserve)
            dry = (self.mag == 0)
            self._reload_n = n
            self._reload_dry = dry
            self._reload_dur = R.sg_reload_dur(n, dry)
            self._reload_t_in = R.sg_shell_times(n)
            self._reload_pump_at = R.sg_pump_time(n) if dry else 1e9
            self.reloading = self._reload_dur
            self._snd("reload")
        else:
            self._reload_n = 0
            self._reload_dry = False
            self._reload_dur = self.RELOAD_S
            self.reloading = self._reload_dur
            self._snd("dry")

    def reload_total(self):
        return self._reload_dur if self.reloading > 0.0 else self.RELOAD_S

    def reload_shell_info(self):
        if self.reloading <= 0.0 or self.weapon != "shotgun" or self._reload_n <= 0:
            return None, None
        return R.sg_shell_slot_prog(self._reload_dur - self.reloading, self._reload_n)

    def heli_left(self):
        if self.heli_t0 is None:
            return None
        return max(0.0, HELI_SPIN - (self.t - self.heli_t0))

    def _ensure_fx_pool(self):
        pool = getattr(self, "_fx_pool", None)
        if pool is None:
            from engine3d.particles import ParticlePool
            pool = self._fx_pool = ParticlePool(1024, seed=808)
        return pool

    def _spawn_blood_spray(self, pos, dir_vec, n=14, speed=4.2):
        rng = random.Random(int(self.t * 1000) + len(self.blood_drops))
        pool = self._ensure_fx_pool()
        from engine3d.particles import PKIND_DEBRIS, PKIND_DUST
        dx, dy, dz = dir_vec
        ln = max(1e-4, math.hypot(dx, math.hypot(dy, dz)))
        ux, uy, uz = dx / ln, dy / ln, dz / ln
        for i in range(int(n)):
            sp = rng.uniform(0.55, 1.25) * speed
            vx = ux * sp + rng.uniform(-0.85, 0.85)
            vy = uy * sp + rng.uniform(0.2, 1.6)
            vz = uz * sp + rng.uniform(-0.85, 0.85)
            if i % 2 == 0:
                pool.emit(PKIND_DEBRIS, pos, (vx, vy, vz), col=(92, 10, 12),
                          size0=0.026, size1=0.015, life=rng.uniform(0.24, 0.44),
                          gravity=9.8, drag=1.1, bounce=0.08, alpha=0.95)
            else:
                pool.emit(PKIND_DUST, pos, (vx * 0.72, vy * 0.8, vz * 0.72), col=(104, 12, 14),
                          size0=0.042, size1=0.024, life=rng.uniform(0.18, 0.34),
                          gravity=7.0, drag=2.8, alpha=0.78)
            self.blood_drops.append([pos[0], pos[1], pos[2], vx, vy, vz, 0.0, rng.uniform(0.30, 0.52)])
        del self.blood_drops[:-64]

    def on_andrei_shot(self, a):
        """Player shot Andrei: immediate bloody burst and stagger toward the rack."""
        pos = a.get("hit_pos") or (a["x"], a["y"] + (1.60 if a.get("hit_zone") == "head" else 1.15), a["z"])
        ray = a.get("hit_ray") or (-1.0, 0.08, 0.0)
        self._spawn_blood_spray(pos, (min(-0.6, ray[0]), ray[1] + 0.15, ray[2]), n=14, speed=4.0)
        self.impacts.append((self.t, pos, "blood"))

    def on_andrei_ceiling_shot(self, a):
        """Misfire shot into the ceiling: plaster dust and smoke puff overhead."""
        cx, cy, cz = a["x"] + 0.3, a["y"] + 4.02, a["z"] - 0.2
        self.impacts.append((self.t, (cx, cy, cz), "dust"))
        self.sparks.append((self.t, (cx, cy, cz)))
        for i in range(4):
            self.smoke_puffs.append(dict(
                age=-0.02 * i, dur=1.4, x=cx + (i - 1.5) * 0.14, y=cy - 0.1, z=cz,
                vx=(i - 1.5) * 0.4, vy=-0.8, vz=0.2 * (i % 2 - 0.5),
                lift=0.15, r0=0.12, r1=0.45, alpha=110, warm=0, var=i % 6,
            ))

    def on_andrei_smoke(self, a, hot=True):
        """Thermal electrical smoke + small orange embers off rack and scorched body."""
        rx, ry, rz = MS.ANDREI_RACK_AT
        rng = random.Random(int(self.t * 1000) + len(self.smoke_puffs))
        sx = rx + rng.uniform(0.10, 0.55)
        sy = ry + rng.uniform(0.75, 1.75)
        sz = rz + rng.uniform(-0.35, 0.35)
        self.smoke_puffs.append(dict(
            age=0.0, dur=rng.uniform(1.8, 3.0), x=sx, y=sy, z=sz,
            vx=rng.uniform(0.05, 0.35), vy=rng.uniform(0.75, 1.35), vz=rng.uniform(-0.22, 0.22),
            lift=0.45, r0=0.14, r1=rng.uniform(0.58, 0.92),
            alpha=138 if hot else 92, warm=1 if hot else 0, var=rng.randrange(6),
        ))
        if hot:
            from engine3d.particles import PKIND_EMBER
            pool = self._ensure_fx_pool()
            for _ in range(3):
                pool.emit(PKIND_EMBER, (sx, sy, sz),
                          (rng.uniform(0.6, 2.2), rng.uniform(1.2, 3.2), rng.uniform(-1.0, 1.0)),
                          col=(255, 148, 52), size0=0.055, size1=0.02,
                          life=rng.uniform(0.35, 0.75), gravity=5.5, drag=1.4, bounce=0.25)

    def on_andrei_breaker_pop(self):
        """Breaker trips at ANDREI_ZAP_S: cameras & monitors snap off, sparks pop."""
        self.cams_alive = False
        rx, ry, rz = MS.ANDREI_RACK_AT
        pan = self._pan(rx, rz)
        self._snd("breaker_pop", pan)
        self._snd("spark_pop", pan)
        self.sparks.append((self.t, (rx + 0.2, ry + 2.15, rz)))
        self.flashes.append((self.t, (rx + 0.2, ry + 2.15, rz)))

    def on_andrei_rack_hit(self):
        """Called at impact frame of Andrei M.'s animated crash into the server rack."""
        rx, ry, rz = MS.ANDREI_RACK_AT
        self._snd("barrel_boom", self._pan(rx, rz), math.hypot(rx - self.px, rz - self.pz))
        self.sparks.append((self.t, (rx + 0.4, ry + 1.5, rz)))
        self.flashes.append((self.t, (rx + 0.4, ry + 1.5, rz)))
        self.cam_kick = min(3.0, self.cam_kick + 2.2)
        self.scorches.append((rx + 0.48, ry + 0.026, rz, 1.35))
        if self.brain.andrei.get("cause") == "player":
            self._spawn_blood_spray((rx + 0.35, ry + 1.18, rz + 0.15), (0.7, 0.2, 0.15), n=8, speed=2.6)
        # the payroll servers were full of cash: it bursts out and flutters down
        rng = random.Random(42)
        self.cash_bricks = []
        self.cash_notes = []
        self._notes_settled_mesh = None
        for i in range(7):
            self.cash_bricks.append(dict(
                x=rx + rng.uniform(0.28, 0.52), y=ry + rng.uniform(0.95, 1.85), z=rz + rng.uniform(-0.45, 0.45),
                vx=rng.uniform(1.8, 5.4), vy=rng.uniform(2.6, 5.6), vz=rng.uniform(-2.6, 2.6),
                rx=rng.uniform(0.0, 360.0), ry=rng.uniform(0.0, 360.0), rz=rng.uniform(0.0, 360.0),
                vrx=rng.uniform(-480.0, 480.0), vry=rng.uniform(-360.0, 360.0), vrz=rng.uniform(-480.0, 480.0),
                cnt=1 if (i % 2) else 2, settled=False,
            ))
        for i in range(44):
            self.cash_notes.append(dict(
                x=rx + rng.uniform(0.25, 0.55), y=ry + rng.uniform(0.85, 2.05), z=rz + rng.uniform(-0.55, 0.55),
                vx=rng.uniform(3.5, 8.0), vy=rng.uniform(1.6, 5.0), vz=rng.uniform(-3.6, 3.6),
                yaw=rng.uniform(0.0, 360.0), pitch=0.0, roll=0.0,
                phase=rng.uniform(0.0, math.tau), freq=rng.uniform(6.5, 10.5),
                amp=rng.uniform(0.9, 1.6), age=0.0, settled=False,
            ))
        self.say("VASILE", "Cameras down in three, two... well. That works too.", 3.4)

    def _pan(self, x, z):
        d = max(1.0, math.hypot(x - self.px, z - self.pz))
        rg = R._right(self.yaw)
        return ((x - self.px) * rg[0] + (z - self.pz) * rg[2]) / d

    def flash(self, pos, sniper=False):
        self.flashes.append((self.t, pos))
        del self.flashes[:-6]
        d = math.hypot(pos[0] - self.px, pos[2] - self.pz)
        if d < 45.0 and self.t - self._last_snd > 0.07:
            self._last_snd = self.t
            self._snd("guard_shot", 0.8 * self._pan(pos[0], pos[2]), d)

    def hurt_player(self, dmg, src=None):
        p = STATE.player
        if p is None or self.dying:
            return
        p.hp -= dmg
        self.hurt = min(1.0, self.hurt + dmg / 28.0)
        self.last_hurt = self.t
        self._snd("hurt", dmg)
        if src is not None:
            bearing = R._wrap(R._yaw(src[0] - self.px, src[1] - self.pz) - self.yaw)
            self.dmg_marks.append((self.t, -bearing))
        if p.hp <= 0:
            self.dying = True
            self.death_t = 0.0
            self.death_msg = "BIRIBEL DOWN  -  AGAIN FROM THE CHECKPOINT"
            self.firing = False
            self._snd("down")

    def _floor(self, x, z):
        return self.world.surface_y(x, z, self._floor_hint)

    def _kick_locking(self):
        return self.study_kick_t is not None and (self.t - self.study_kick_t) < KICK_LOCK_S

    def _spawn_door_splinters(self):
        bx, by, bz = MS.STUDY_DOOR_AT[0], FF + 1.05, MS.ROOMS_Z + 0.12
        rng = random.Random(int(self.t * 1000) + 77)
        for i in range(16):
            col = (212, 176, 86) if i == 0 else rng.choice(((88, 48, 28), (112, 66, 38), (62, 34, 22)))
            self.debris.append(dict(
                t0=self.t,
                x=bx + rng.uniform(-0.28, 0.28),
                y=by + rng.uniform(-0.45, 0.55),
                z=bz,
                vx=rng.uniform(-2.4, 2.4),
                vy=rng.uniform(0.6, 3.6),
                vz=rng.uniform(3.4, 7.6),
                rx=rng.uniform(0.0, 360.0),
                ry=rng.uniform(0.0, 360.0),
                vrx=rng.uniform(-540.0, 540.0),
                vry=rng.uniform(-480.0, 480.0),
                sx=rng.uniform(0.04, 0.14),
                sy=rng.uniform(0.02, 0.05),
                sz=rng.uniform(0.14, 0.34),
                col=col,
                hot=False,
            ))
        for i in range(6):
            ang = rng.uniform(-0.9, 0.9)
            spd = rng.uniform(1.2, 3.2)
            self.smoke_puffs.append(dict(
                age=-0.015 * i, dur=rng.uniform(0.85, 1.35),
                x=bx + rng.uniform(-0.4, 0.4), y=by + rng.uniform(-0.3, 0.5), z=bz + 0.1,
                vx=math.sin(ang) * spd, vy=rng.uniform(0.2, 0.9), vz=math.cos(ang) * spd,
                lift=0.35, r0=0.14, r1=0.62, alpha=118, warm=0, var=i % 6,
            ))
        self.sparks.append((self.t, (bx, FF + 1.08, MS.ROOMS_Z + 0.05)))
        self.impacts.append((self.t, (bx, FF + 1.05, MS.ROOMS_Z + 0.08), "dust"))

    def _step_study_kick(self, dt):
        if self.study_kick_t is None:
            return
        kage = self.t - self.study_kick_t
        px0, pz0 = self._kick_p0 or (self.px, self.pz)
        tx = clamp(px0, -0.32, 0.32)
        if kage < 0.22:
            u = R._ease(kage / 0.22)
            wx = px0 + (tx - px0) * u
            wz = pz0 + (MS.ROOMS_Z - 0.94 - pz0) * u
            nx, nz = self.world.move(self.px, self.pz, wx - self.px, wz - self.pz, y=self.py)
            self.px, self.pz = nx, nz
            self.body_yaw = (self._kick_yaw0 + R._wrap(0.0 - self._kick_yaw0) * u) % 360.0
            self.yaw = (self.yaw + R._wrap(0.0 - self.yaw) * min(1.0, dt * 6.5)) % 360.0
        if kage >= KICK_HIT_S and not self._kick_opened:
            self._kick_opened = True
            self.world.study_open = True
            self.cam_kick = min(2.6, self.cam_kick + 1.85)
            self._snd("door_kick")
            self._spawn_door_splinters()
            self.phase = "study"
            self.brain.start_wave(5)
            self.say("RETARDOVICI", "(intercom) You walked into my house. You will not walk out.", 3.4)
        if KICK_HIT_S <= kage < KICK_LOCK_S:
            u = R._ease((kage - KICK_HIT_S) / (KICK_LOCK_S - KICK_HIT_S))
            wz = (MS.ROOMS_Z - 0.94) + 0.42 * u
            nx, nz = self.world.move(self.px, self.pz, tx - self.px, wz - self.pz, y=self.py)
            self.px, self.pz = nx, nz
            self.body_yaw = _w.yaw_mix(self.body_yaw, 0.0, min(1.0, dt * 12.0))
        if kage >= KICK_DUR:
            self.study_kick_t = None

    # --- update --------------------------------------------------------------------

    def update(self, keys=None):
        if not self._active or self.paused:
            return
        dt = clamp(float(getattr(STATE, "dt", 1.0 / 60.0)), 0.0, 0.05)
        if self.t < self.slowmo_until:
            dt *= 0.35
        self.t += dt
        if self.heli_t0 is not None:
            spin = 1.0 if self.lift_t0 is not None else clamp((self.t - self.heli_t0) / HELI_SPIN, 0.15, 1.0)
            self.rotor = (self.rotor + dt * (90.0 + 1500.0 * spin)) % 360.0
            self._snd("bed", "helipad", spin)
        else:
            self._snd("bed", "mansion")
        self._snd("update", dt)
        if self.dying:
            self.study_kick_t = None
            self.death_t += dt
            if self.death_t >= 2.4:
                self._setup(self.cp)
            return
        k = keys if keys is not None else pygame.key.get_pressed()
        self._step_study_kick(dt)
        kick_lock = self._kick_locking()
        if self.swapping > 0.0:
            self.swapping = max(0.0, self.swapping - dt)
        for cidx, ct0 in self.crate_anims.items():
            if cidx not in self.crate_pops and self.t - ct0 >= 0.12:
                self.crate_pops.add(cidx)
                cx, cy, cz, cyaw = MS.CRATE_SPOTS[cidx]
                cy = 0.03 if cy == 0.0 else cy + 0.015
                lp = v_add((cx, cy, cz), m_apply(rot_y(cyaw), (0.0, 0.40, -0.24)))
                self.sparks.append((self.t, lp))
                self._snd("pickup")
        if self.crate_act is not None:
            ct0, _cidx, cx, _cy, cz, _cyaw = self.crate_act
            if (self.t - ct0 >= 0.85 or math.hypot(cx - self.px, cz - self.pz) > 2.6
                    or self.firing or self.aiming
                    or self.sprint or self.reloading > 0.0 or self.swapping > 0.0):
                self.crate_act = None
        if self.t >= self._swap_snd_at:
            self._swap_snd_at = 1e9
            self._snd("pump" if self.weapon == "shotgun" else "rifle_handle")
        self.ads += ((1.0 if self.aiming and not self.reloading and self.swapping <= 0.0 and not kick_lock else 0.0) - self.ads) \
            * min(1.0, dt * 12.0)
        up = self.ads > 0.3 or self.firing or self.t - self.last_fire < 0.6
        up = 0.0 if (self.sprint or self.reloading or self.swapping > 0.0 or kick_lock or not up) else 1.0
        self.gun_up += (up - self.gun_up) * min(1.0, dt * 14.0)
        if not self.firing or self.reloading or self.weapon != "rifle":
            self.heat = max(0.0, self.heat - dt * 1.4)
        self.world.cur_y = self.py
        if kick_lock:
            self.vel = (0.0, 0.0)
            self.pmoving = False
            self.sprint = False
            self._anim_ctl().update(
                dt, vel_xz=(0.0, 0.0), yaw_deg=self.body_yaw,
                aiming=False, sprint=False, crouch=False,
                floor_fn=getattr(self, "_floor", None),
                pos=(self.px, self.py, self.pz),
            )
        else:
            self._ground_move(k, dt)
        self.py = self.world.surface_y(self.px, self.pz, self.py)
        self.world.cur_y = self.py
        self._update_wall_k(dt)
        step = int(self.stride / STEP_M)
        if step != self._step_i:
            self._step_i = step
            self._snd("step", step, False)
        if self.reloading:
            self.reloading = max(0.0, self.reloading - dt)
            elapsed = self._reload_dur - self.reloading
            if self.weapon == "shotgun":
                while self._shell_i < len(self._reload_t_in) and elapsed >= self._reload_t_in[self._shell_i]:
                    self._shell_i += 1
                    if self.mag < self.MAG and self.reserve > 0:
                        self.mag += 1
                        self.reserve -= 1
                        self.wpns[self.weapon] = [self.mag, self.reserve]
                    self._snd("shell_in")
                if self._reload_dry and elapsed >= self._reload_pump_at and not self._pump_done:
                    self._pump_done = True
                    self._snd("pump")
            if not self.reloading:
                if self.weapon == "shotgun":
                    n = max(0, min(self._reload_n - self._shell_i, self.MAG - self.mag, self.reserve))
                else:
                    n = min(self.MAG - self.mag, self.reserve)
                self.mag += n
                self.reserve -= n
                self.wpns[self.weapon] = [self.mag, self.reserve]
                if self.weapon == "shotgun" and self._reload_dry and not self._pump_done and self.mag > 0:
                    self._snd("pump")
                self._reload_n = 0
                self._reload_dry = False
                self._pump_done = False
        if self.t >= self.pump_snd_at:
            self.pump_snd_at = 1e9
            self._snd("pump")
        if self.firing and not self.reloading and self.swapping <= 0.0 and not REV.is_locking(self) and not kick_lock:
            self._fire()
        self._loot()
        self.recoil = max(0.0, self.recoil - dt * 6.0)
        self.cam_kick *= math.exp(-dt * 11.0)
        if not kick_lock:
            self._hold(k, dt)
        self._chandeliers(dt)
        self.brain.update(dt)
        self._waves()
        self.hurt = max(0.0, self.hurt - dt * 1.4)
        p = STATE.player
        if p is not None and self.t - self.last_hurt > R.HP_REGEN_DELAY and p.hp < self.hp_max():
            p.hp = min(self.hp_max(), p.hp + R.HP_REGEN * 0.45 * dt)
        now = self.t
        if self.tracers:
            self.tracers = [x for x in self.tracers if now - x[0] < 0.10]
        if self.sparks:
            self.sparks = [x for x in self.sparks if now - x[0] < 0.45]
        if self.impacts:
            self.impacts = [x for x in self.impacts if now - x[0] < 0.6]
        if self.flashes:
            self.flashes = [x for x in self.flashes if now - x[0] < 0.2]
        if self.booms:
            self.booms = [x for x in self.booms if now - x[0] < 1.8]
        if self.debris:
            kept = []
            for d in self.debris:
                if now - d["t0"] >= 4.2:
                    continue
                d["vy"] -= 9.8 * dt
                d["x"] += d["vx"] * dt
                d["y"] += d["vy"] * dt
                d["z"] += d["vz"] * dt
                d["rx"] += d["vrx"] * dt
                d["ry"] += d["vry"] * dt
                fl = self.world.surface_y(d["x"], d["z"], d["y"] + 0.15) + 0.04
                if d["y"] <= fl:
                    d["y"] = fl
                    d["vy"] = abs(d["vy"]) * 0.26 if abs(d["vy"]) > 0.7 else 0.0
                    d["vx"] *= 0.62
                    d["vz"] *= 0.62
                    d["vrx"] *= 0.45
                    d["vry"] *= 0.45
                kept.append(d)
            self.debris = kept[-42:]
        if self.smoke_puffs:
            self._step_smoke(dt)
        self.veh_fx.update(dt, floor_fn=lambda x, z: 0.0)
        if self.cash_bricks or self.cash_notes:
            self._step_cash(dt)
        if self.blood_drops:
            self._step_blood_drops(dt)
        if self.dmg_marks:
            self.dmg_marks = [m for m in self.dmg_marks if now - m[0] < 0.9]

    def _loot(self):
        for e in self.brain.enemies:
            if e["alive"] or not e["mags"] or abs(e["y"] - self.py) >= 1.8:
                continue
            bx, bz = e.get("rest", (e["x"], e["z"]))
            if math.hypot(bx - self.px, bz - self.pz) > R.LOOT_R:
                continue
            self.wpns[self.weapon] = [self.mag, self.reserve]
            if all(self.wpns[k][1] >= WPN_SPECS[k]["cap"] for k in ("shotgun", "rifle")):
                return      # both guns full: the bodies keep their ammo for later
            e["mags"] = 0
            self.wpns["shotgun"][1] = min(WPN_SPECS["shotgun"]["cap"], self.wpns["shotgun"][1] + 4)
            self.wpns["rifle"][1] = min(WPN_SPECS["rifle"]["cap"], self.wpns["rifle"][1] + 20)
            self._sync_weapon_attrs()
            self.toast = (self.t, "+AMMO")
            self._snd("pickup")

    # --- set pieces ------------------------------------------------------------------

    def _cash_floor_y(self, x, z, include_body=False):
        if (-10.9 <= x <= -6.1 and 34.1 <= z <= 35.1) or (-11.35 <= x <= -10.45 and 27.7 <= z <= 30.3):
            return GF + 0.785
        if include_body:
            an = self.brain.andrei
            if an["state"] in ("dying", "done"):
                _hit_s, _zap_s, _sit_s, down_s = B.andrei_timings(an.get("cause", "misfire"))
                if self.t - an["dead_t"] >= down_s - 0.25 and abs(x - (-11.1)) < 0.72 and abs(z - 31.2) < 0.52:
                    return GF + 0.22
        return GF + 0.036

    def _step_cash(self, dt):
        for b in self.cash_bricks:
            if b["settled"]:
                continue
            b["vy"] -= 9.8 * dt
            b["x"] += b["vx"] * dt
            b["y"] += b["vy"] * dt
            b["z"] += b["vz"] * dt
            if b["x"] < -11.40:
                b["x"] = -11.40
                b["vx"] = abs(b["vx"]) * 0.4
            elif b["x"] > -3.95:
                b["x"] = -3.95
                b["vx"] = -abs(b["vx"]) * 0.4
            if b["z"] < 26.45:
                b["z"] = 26.45
                b["vz"] = abs(b["vz"]) * 0.4
            elif b["z"] > 34.02:
                b["z"] = 34.02
                b["vz"] = -abs(b["vz"]) * 0.4
            b["rx"] += b["vrx"] * dt
            b["ry"] += b["vry"] * dt
            b["rz"] += b["vrz"] * dt
            fl = self._cash_floor_y(b["x"], b["z"], include_body=False) - 0.006
            if b["y"] <= fl:
                b["y"] = fl
                if abs(b["vy"]) > 0.9:
                    b["vy"] = abs(b["vy"]) * 0.22
                    b["vx"] *= 0.55
                    b["vz"] *= 0.55
                    b["vrx"] *= 0.40
                    b["vrz"] *= 0.40
                else:
                    b["vx"] = b["vy"] = b["vz"] = b["vrx"] = b["vry"] = b["vrz"] = 0.0
                    b["rx"] = b["rz"] = 0.0
                    b["settled"] = True
        drag = math.exp(-4.6 * dt)
        for n in self.cash_notes:
            if n["settled"]:
                continue
            n["age"] += dt
            n["vx"] *= drag
            n["vz"] *= drag
            n["vy"] = max(-2.85, n["vy"] - 9.8 * dt)
            sp_h = math.hypot(n["vx"], n["vz"])
            sway = math.sin(n["age"] * n["freq"] + n["phase"]) * n["amp"] if sp_h < 2.2 else 0.0
            yr = math.radians(n["yaw"])
            n["x"] = clamp(n["x"] + (n["vx"] + math.cos(yr) * sway) * dt, -11.42, -3.90)
            n["z"] = clamp(n["z"] + (n["vz"] - math.sin(yr) * sway) * dt, 26.40, 35.25)
            n["y"] += n["vy"] * dt
            n["pitch"] = 28.0 * math.sin(n["age"] * n["freq"] * 1.15 + n["phase"])
            n["roll"] = 36.0 * math.cos(n["age"] * n["freq"] * 0.9 + n["phase"])
            fl = self._cash_floor_y(n["x"], n["z"], include_body=True)
            if n["y"] <= fl:
                n["y"] = fl
                n["pitch"] = 0.0
                n["roll"] = 0.0
                n["settled"] = True

    def _step_blood_drops(self, dt):
        kept = []
        for d in self.blood_drops:
            d[6] += dt
            if d[6] >= d[7]:
                continue
            d[4] -= 9.8 * dt
            d[0] += d[3] * dt
            d[1] += d[4] * dt
            d[2] += d[5] * dt
            if d[1] > GF + 0.016:
                kept.append(d)
        self.blood_drops = kept

    def _step_smoke(self, dt):
        drag = math.exp(-dt * 1.7)
        kept = []
        for pf in self.smoke_puffs:
            pf["age"] += dt
            if pf["age"] >= pf["dur"]:
                continue
            pf["vx"] *= drag
            pf["vz"] *= drag
            pf["vy"] = pf["vy"] * math.exp(-dt * 0.8) + pf["lift"] * dt
            pf["x"] += pf["vx"] * dt
            pf["y"] += pf["vy"] * dt
            pf["z"] += pf["vz"] * dt
            kept.append(pf)
        self.smoke_puffs = kept[-48:]

    def _spawn_car_blast(self, c):
        cx, cz = c["x"], c["z"]
        rng = random.Random(int(abs(cx) * 131 + abs(cz) * 37) + len(self.scorches))
        self.scorches.append((cx, cz, 3.2))
        for i in range(14):
            ang = (i / 14.0) * math.tau + rng.uniform(-0.22, 0.22)
            spd = rng.uniform(3.2, 8.8)
            hot = (i % 2 == 0)
            col = rng.choice(((34, 30, 30), (46, 42, 44), tuple(max(18, v // 2) for v in c["paint"])))
            self.debris.append(dict(
                t0=self.t, x=cx + math.cos(ang) * 0.6, y=rng.uniform(0.5, 1.3), z=cz + math.sin(ang) * 0.6,
                vx=math.cos(ang) * spd, vy=rng.uniform(4.2, 9.2), vz=math.sin(ang) * spd,
                rx=rng.uniform(0.0, 360.0), ry=rng.uniform(0.0, 360.0),
                vrx=rng.uniform(-420.0, 420.0), vry=rng.uniform(-380.0, 380.0),
                sx=rng.uniform(0.14, 0.34), sy=rng.uniform(0.05, 0.14), sz=rng.uniform(0.16, 0.36),
                col=col, hot=hot,
            ))
        for i in range(14):
            ang = (i / 14.0) * math.tau + rng.uniform(-0.3, 0.3)
            ring = (i < 6)
            spd = rng.uniform(4.5, 7.2) if ring else rng.uniform(0.6, 2.2)
            self.smoke_puffs.append(dict(
                age=-0.03 * i, dur=rng.uniform(1.6, 2.4) if ring else rng.uniform(2.6, 3.8),
                x=cx + math.cos(ang) * 0.5, y=0.35 if ring else rng.uniform(0.8, 1.5),
                z=cz + math.sin(ang) * 0.5,
                vx=math.cos(ang) * spd, vy=rng.uniform(0.4, 1.0) if ring else rng.uniform(2.2, 3.6),
                vz=math.sin(ang) * spd, lift=0.35 if ring else 1.25,
                r0=0.45 if ring else 0.65, r1=1.55 if ring else 2.45,
                alpha=145 if ring else 180, warm=1 if ring else 3, var=i % 6,
            ))

    def _explode(self, pos, radius, player_dmg=45.0, enemy_dmg=420.0, visual=True):
        x, y, z = pos
        if visual:
            self.booms.append((self.t, pos))
        self.flashes.append((self.t, pos))
        for k in range(5):
            a = k * 1.3
            self.sparks.append((self.t, (x + math.cos(a) * 0.8, y + 0.3 * k, z + math.sin(a) * 0.8)))
            self.impacts.append((self.t, (x + math.cos(a) * 1.4, y, z + math.sin(a) * 1.4), "dust"))
        d = math.dist(pos, (self.px, self.py + 0.9, self.pz))
        self._snd("barrel_boom", self._pan(x, z), d)
        self.cam_kick = min(3.0, self.cam_kick + max(0.0, 3.0 - d * 0.12))
        for e in self.brain.enemies:
            if e["alive"] and e["live"]:
                de = math.dist(pos, (e["x"], e["y"] + 0.9, e["z"]))
                if de < radius:
                    self.brain.hurt_enemy(e, enemy_dmg * (1.0 - de / radius) + 60.0, (x, z),
                                          hit_ctx=dict(weapon="blast", blast=(pos, 16.0, radius)))
        # walls shield the player; lift the origin clear of the wreck's own box
        if d < radius and self.world.los3d((x, y + 1.0, z), (self.px, self.py + 1.0, self.pz)):
            self.hurt_player(player_dmg * (1.0 - d / radius), (x, z))

    def _car_cookoff(self, vd, ck):
        d = math.dist(vd.pos, (self.px, self.py + 0.9, self.pz))
        self.cam_kick = min(3.0, self.cam_kick + max(0.0, 1.4 - d * 0.08))
        self._snd("barrel_boom", self._pan(vd.pos[0], vd.pos[2]), d)

    def _hit_car(self, c, dmg):
        c["hp"] -= dmg
        if c["hp"] <= 0.0 and not c["burned"]:
            c["burned"] = True
            c["boom_t"] = self.t
            self.veh_fx.trigger(
                "car", (c["x"], 0.0, c["z"]),
                yaw=c["yaw"], paint=c["paint"],
                seed=int(abs(c["x"]) * 131 + abs(c["z"]) * 37),
                tag=id(c), floor_fn=lambda x, z: 0.0,
                on_cookoff=self._car_cookoff,
            )
            self._explode((c["x"], 0.9, c["z"]), CAR_BLAST_R, visual=False)
            if sum(1 for cc in self.cars if cc["burned"]) == 1:
                self.say("ALEX", "Ha! Cars burn. Do it again!", 2.4)

    def _car_spheres(self, c):
        a = math.radians(c["yaw"])
        fx, fz = math.sin(a), math.cos(a)
        return [((c["x"] + fx * k, 0.85, c["z"] + fz * k), 1.0) for k in (-1.4, 0.0, 1.4)]

    def _drop_chandelier(self, ch):
        if ch["state"] != "up":
            return
        ch["state"] = "fall"
        ch["t0"] = self.t
        ch["vy"] = 0.0
        self._snd("metal")

    def _chandeliers(self, dt):
        for ch in self.chand:
            if ch["state"] != "fall":
                continue
            ch["vy"] += 14.0 * dt
            ch["y"] -= ch["vy"] * dt
            if ch["y"] <= GF + 0.5:
                ch["y"] = GF + 0.5
                ch["state"] = "down"
                pos = (ch["x"], GF + 0.4, ch["z"])
                self._explode(pos, 3.0, player_dmg=30.0, enemy_dmg=600.0)
                if self.brain.andrei["state"] not in ("intro", "dying"):
                    self.say("BODI", "Ha! Mind the lighting!", 2.2)

    def _start_gallery(self):
        self._checkpoint(2)
        self.phase = "gallery"
        self.brain.start_wave(4)
        self.say("BODI", "More on the landing! We hold the hall - you take the stairs!", 3.4)

    def _waves(self):
        b = self.brain
        if self.phase == "drive":
            alive1 = sum(1 for e in b.enemies if e["alive"] and e["wave"] == 1)
            if alive1 <= 2 or self.pz > -18.0:
                self.phase = "forecourt"
                self.doors_at = self.t + 8.6
                b.start_wave(2)
                self.say("VASILE", "Balconies, both sides. And a gunner on the portico roof.", 3.2)
        elif self.phase == "forecourt":
            if self.doors_at is not None and self.t >= self.doors_at:
                self.doors_at = None
                self.world.front_open = True
                self._snd("metal")
                self.say("BODI", "Front doors! Here they come!", 2.4)
            if not b.pending(1) and not b.pending(2):
                self.phase = "enter"
                self.world.front_open = True
                b.revive_allies()
                self.say("BODI", "Forecourt's ours. Inside - go, go!", 2.8)
        elif self.phase == "enter":
            if self.pz > 1.2 and self.py > 0.5:
                self._checkpoint(1)
                self.phase = "hall"
                b.start_wave(3)
                self.say("ALEX", "Galleries! Up top, both sides!", 2.6)
        elif self.phase == "hall" and not b.pending(3):
            if b.andrei["state"] != "done":
                self.phase = "andrei"
                self.say("VASILE", "Before the stairs: security room, back left. Andrei M. runs the cameras. Shut him down.", 3.8)
            else:
                self._start_gallery()
        elif self.phase == "andrei" and b.andrei["state"] == "done":
            self._start_gallery()
        elif self.phase == "gallery" and not b.pending(4):
            self._checkpoint(3)
            self.phase = "study_door"
            self.say("VASILE", "Landing's clear. His study's straight ahead.", 2.8)
        elif self.phase == "study" and not b.pending(5):
            self.phase = "to_terrace"
            self.world.terrace_open = True
            self.heli_t0 = self.t - 10.0
            self._snd("metal")
            self.say("MARU", "Biribel, his helicopter's spinning up on the terrace! Move!", 3.2)
        elif self.phase == "to_terrace" and self.pz > MS.HZ + 0.6 and self.py > 4.6:
            self._checkpoint(4)
            t0 = self.heli_t0
            self._start_helipad()
            self.heli_t0 = t0
        elif self.phase == "helipad":
            left = self.heli_left()
            if not b.pending(6) or left <= 0.0:
                self.phase = "liftoff"
                self.lift_t0 = self.t
                self.world.heli_parked = False
                self.say("BIRIBEL", "He's lifting off!", 2.4)
        elif self.phase == "liftoff":
            u = (self.t - self.lift_t0) / LIFT_S
            if self.t - self._phase_at > 0.2:
                self._phase_at = self.t
                hp = self.heli_pos()
                self.tracer((hp[0] - 1.0, hp[1] + 1.2, hp[2]),
                            (self.px + random.uniform(-2, 2), self.py + 0.5, self.pz + random.uniform(-2, 2)))
                self.flash((hp[0] - 1.0, hp[1] + 1.2, hp[2]))
            if u >= 1.0:
                self.finish("win")

    def _checkpoint(self, cp):
        self.cp = cp
        STATE.m8_mansion_cp = cp
        self.cp_toast = self.t
        self.area_card = (self.t, ) + AREAS[cp]
        self.brain.revive_allies()
        p = STATE.player
        if p is not None:
            p.hp = max(p.hp, self.hp_max() * 0.6)

    def heli_pos(self):
        hx, hy, hz = MS.HELIPAD_AT
        if self.lift_t0 is None:
            return (hx, hy, hz)
        u = clamp((self.t - self.lift_t0) / LIFT_S, 0.0, 1.0)
        return (hx + 4.0 * u * u, hy + 14.0 * u * u + 1.2 * u, hz + 9.0 * u * u)

    # --- interaction -------------------------------------------------------------------

    def _hold_action(self):
        if self.brain.near_revive() is not None:
            return "revive"
        if self.phase == "study_door" and self.study_kick_t is None and self.py >= FF - 0.5:
            sx, _, sz = MS.STUDY_DOOR_AT
            if math.hypot(self.px - sx, self.pz - sz) < 2.4:
                return "study_door"
        for idx, (cx, cy, cz, _) in enumerate(MS.CRATE_SPOTS):
            if idx not in self.crates_taken and abs(self.py - cy) < 1.2 and math.hypot(self.px - cx, self.pz - cz) < 2.1:
                return ("crate", idx)
        return None

    def _hold(self, k, dt):
        try:
            held = bool(k[pygame.K_e])
        except Exception:
            held = False
        just = held and not self._e_prev
        self._e_prev = held
        action = self._hold_action()
        REV.step(self, dt, self.brain.near_revive() if action == "revive" else None, held, 1.6, self.brain.help_done)
        if isinstance(action, tuple) and action[0] == "crate":
            self.hold = 0.0
            if just:
                self.crates_taken.add(action[1])
                self.crate_anims[action[1]] = self.t
                cx, cy, cz, cyaw = MS.CRATE_SPOTS[action[1]]
                self.crate_act = (self.t, action[1], cx, cy, cz, cyaw)
                p = STATE.player
                if p is not None:
                    p.hp = min(self.hp_max(), p.hp + 40.0)
                for wname, bonus in (("shotgun", 10), ("rifle", 60)):
                    self.wpns[wname][1] = min(WPN_SPECS[wname]["cap"], self.wpns[wname][1] + bonus)
                self._sync_weapon_attrs()
                self._snd("rifle_handle")
                self.toast = (self.t, "CRATE RESUPPLY")
            return
        if action == "study_door":
            self.hold = 0.0
            if just:
                self.study_kick_t = self.t
                self._kick_opened = False
                self._kick_p0 = (self.px, self.pz)
                self._kick_yaw0 = self.body_yaw
                self.reloading = 0.0
                self.swapping = 0.0
                self.firing = False
                self.aiming = False
                self._snd("step", 0, False)
            return
        if action == "revive":
            if not held:
                self.hold = 0.0
            return
        if not held:
            self.hold = 0.0
            return

    def camera(self):
        back, right, up = (R.BOOM[i] + (R.BOOM_ADS[i] - R.BOOM[i]) * self.ads for i in range(3))
        kick_fov = 0.0
        if self.study_kick_t is not None:
            kage = clamp(self.t - self.study_kick_t, 0.0, KICK_DUR)
            env = R._ease(kage / 0.16) if kage < 0.16 else (1.0 - R._ease((kage - 0.30) / (KICK_DUR - 0.30)) if kage > 0.30 else 1.0)
            back -= 0.28 * env
            right += 0.14 * env
            up -= 0.06 * env
            kick_fov = 3.6 * max(0.0, 1.0 - abs(kage - KICK_HIT_S) / 0.24)
        pivot = (self.px, self.py + R.EYE_H + up, self.pz)
        f = R._fwd(self.yaw, self.pitch)
        rg = R._right(self.yaw)
        right = min(right, max(0.0, self.world.ray_hit(pivot, (rg[0], 0.0, rg[2]), right + 0.3) - 0.3))
        shoulder = (pivot[0] + rg[0] * right, pivot[1], pivot[2] + rg[2] * right)
        d = (-f[0], -f[1], -f[2])
        dist = max(0.45, min(back, self.world.ray_hit(shoulder, d, back + 0.35) - 0.35))
        eye = (shoulder[0] + d[0] * dist, max(self.py + 0.35, shoulder[1] + d[1] * dist),
               shoulder[2] + d[2] * dist)
        fv = R._fwd(self.yaw, self.pitch + 1.6 * self.cam_kick)
        tgt = (eye[0] + fv[0] * 10.0, eye[1] + fv[1] * 10.0, eye[2] + fv[2] * 10.0)
        if self.dying:
            kk = clamp(self.death_t / 1.2, 0.0, 1.0)
            eye = (eye[0], eye[1] + 1.4 * kk, eye[2])
            tgt = (self.px, self.py + 0.3, self.pz)
        fov = R.FOV + (WPN_SPECS[self.weapon]["fov_ads"] - R.FOV) * self.ads - 1.4 * self.cam_kick - kick_fov
        eye, tgt, fov = REV.adjust_camera(self, eye, tgt, fov)
        return eye, tgt, fov, dist

    def _fire(self):
        if self.swapping > 0.0:
            return
        sp = WPN_SPECS[self.weapon]
        if self.t - self.last_fire < sp["gap"]:
            return
        if self.wall_k > 0.65:
            return
        if self.mag <= 0:
            if self.t - self.last_fire > 0.3:
                self.last_fire = self.t
                self._snd("dry")
                self._begin_reload()
            return
        self.mag -= 1
        self.wpns[self.weapon][0] = self.mag
        self.last_fire = self.t
        self.last_flash = self.t
        self.flash_seed += 1
        o, _d = self._aim_ray()
        look_pitch = self.pitch + 1.6 * self.cam_kick

        if self.weapon == "shotgun":
            self.pump_at = self.t
            self.pump_snd_at = self.t + R.PUMP_S
            self.recoil = min(3.0, self.recoil + 1.4)
            self.cam_kick = min(2.6, self.cam_kick + 2.0)
            self.pitch = clamp(self.pitch + 0.55, *R.PITCH_LIM)
            self._snd("shot", True)
            cone = 0.65 if self.ads > 0.5 else 1.0
            rays = [R._fwd(self.yaw + dy * cone, look_pitch + dp * cone) for dy, dp in R.PELLET_FAN]
            body_dmg, head_dmg = R.PELLET_BODY, R.PELLET_HEAD
        else:
            self.heat = min(1.0, self.heat + 0.14)
            spread = (0.22 + 1.45 * self.heat) * (0.45 if self.ads > 0.5 else 1.0)
            ang = random.uniform(0.0, math.tau)
            rad = spread * math.sqrt(random.random())
            self.recoil = min(2.4, self.recoil + 0.45)
            self.cam_kick = min(1.5, self.cam_kick + 0.45)
            self.pitch = clamp(self.pitch + (0.14 if self.ads > 0.5 else 0.28), *R.PITCH_LIM)
            self._snd("rifle_shot")
            rays = [R._fwd(self.yaw + math.cos(ang) * rad, look_pitch + math.sin(ang) * rad)]
            body_dmg, head_dmg = 26.0, 56.0

        src = self._muzzle or o
        hits, impact_pts, lanes = {}, [], []
        farthest, any_enemy, any_head, hit_andrei = 0.0, False, False, False
        car_hits, chand_hits = {}, set()
        an = self.brain.andrei
        andrei_zone, andrei_end, andrei_dd = "chest", None, None
        can_hit_andrei = (an["state"] == "intro"
                          or (an["state"] == "idle" and B.in_security_room(self.px, self.py, self.pz)))

        for dd in rays:
            best = self.world.ray_hit(o, dd, 75.0)
            hit_kind, hit_obj, head, zone = "world", None, False, "chest"
            if can_hit_andrei:
                for c, rad, sz in (((an["x"], an["y"] + 1.1, an["z"]), 0.55, "chest"),
                                   ((an["x"], an["y"] + 1.62, an["z"]), 0.28, "head")):
                    h = B.RB._ray_sphere(o, dd, c, rad)
                    if h is not None and h < best:
                        best, hit_kind, hit_obj, head, zone = h, "andrei", an, (sz == "head"), sz
            for e in self.brain.enemies:
                if not e["alive"] or not e["live"]:
                    continue
                for zi, (c, rad, is_head) in enumerate(self.brain.spheres(e)):
                    h = B.RB._ray_sphere(o, dd, c, rad)
                    if h is not None and h < best:
                        best, hit_kind, hit_obj, head = h, "enemy", e, is_head
                        zone = "head" if is_head else ("chest", "head", "gut", "leg")[min(zi, 3)]
            for i, ch in enumerate(self.chand):
                if ch["state"] == "up":
                    h = B.RB._ray_sphere(o, dd, (ch["x"], ch["y"] - 0.1, ch["z"]), CHAND_R)
                    if h is not None and h < best:
                        best, hit_kind, hit_obj = h, "chand", i
            for i, car in enumerate(self.cars):
                if car["burned"]:
                    continue
                for c, rad in self._car_spheres(car):
                    h = B.RB._ray_sphere(o, dd, c, rad)
                    if h is not None and h < best + 0.6:
                        best, hit_kind, hit_obj = min(best, h), "car", i
            end = (o[0] + dd[0] * best, o[1] + dd[1] * best, o[2] + dd[2] * best)
            lanes.append(end)
            farthest = max(farthest, best)
            if hit_kind == "andrei":
                any_enemy = hit_andrei = True
                any_head = any_head or head
                if head or andrei_zone != "head":
                    andrei_zone, andrei_end, andrei_dd = zone, end, dd
                impact_pts.append((end, "blood"))
            elif hit_kind == "enemy":
                any_enemy = True
                any_head = any_head or head
                pdmg = head_dmg if head else body_dmg
                rec = hits.get(id(hit_obj))
                if rec is None:
                    hits[id(hit_obj)] = [hit_obj, pdmg, head, zone, end, dd, best]
                else:
                    rec[1] += pdmg
                    rec[6] = min(rec[6], best)
                    if head and not rec[2]:
                        rec[2], rec[3], rec[4], rec[5] = True, "head", end, dd
                impact_pts.append((end, "blood"))
            elif hit_kind == "car":
                car_hits[hit_obj] = car_hits.get(hit_obj, 0.0) + body_dmg
                self.sparks.append((self.t, end))
                impact_pts.append((end, "dust"))
            elif hit_kind == "chand":
                chand_hits.add(hit_obj)
                self.sparks.append((self.t, end))
            else:
                impact_pts.append((end, "dust"))

        for end in lanes:
            self.tracers.append((self.t, src, end, (255, 226, 160)))
        for end, kind in impact_pts:
            self.impacts.append((self.t, end, kind))
        if hit_andrei:
            self.brain.trigger_andrei_death(
                cause="player",
                hit_zone=andrei_zone,
                hit_pos=andrei_end,
                hit_ray=andrei_dd,
            )
        for e, dmg, is_hd, hz, hp, hray, hdist in hits.values():
            self.brain.hurt_enemy(e, dmg, (o[0], o[2]), hit_ctx=dict(
                is_head=is_hd, hit_zone=hz, hit_pos=hp, hit_ray=hray,
                weapon=self.weapon, dmg=dmg, hit_dist=hdist,
            ))
            self._spawn_blood_spray(hp, hray, n=8 if is_hd else 5, speed=3.2 if is_hd else 2.4)
        for i, dmg in car_hits.items():
            self._hit_car(self.cars[i], dmg)
        for i in chand_hits:
            self._drop_chandelier(self.chand[i])
        if any_enemy:
            self.hit_mark = self.t
            self._snd("headshot" if any_head else "impact", *(farthest,) if any_head else (True, farthest))
        else:
            self._snd("impact", False, farthest)

    # --- objectives -----------------------------------------------------------------------

    def _stragglers(self):
        """The last few of a wave, so nobody hides unseen in a side room."""
        if self.phase not in ("drive", "forecourt", "hall", "gallery", "study", "helipad"):
            return []
        b = self.brain
        left = [e for e in b.enemies if e["alive"] and e["wave"] == b.wave]
        if not left or len(left) > 3 or any(self.t < e["spawn_at"] for e in left):
            return []
        return sorted(left, key=lambda e: math.hypot(e["x"] - self.px, e["z"] - self.pz))

    def objective_point(self):
        rev = self.brain.near_revive()
        if rev is not None:
            a = self.brain.bodi if rev == "bodi" else self.brain.alex
            return a["x"], a["z"]
        left = self._stragglers()
        if left:
            return left[0]["x"], left[0]["z"]
        if self.phase == "enter":
            return MS.FRONT_DOOR_AT[0], MS.FRONT_DOOR_AT[2]
        if self.phase == "andrei":
            an = self.brain.andrei
            if an["state"] != "idle" or (-12.5 <= self.px <= -3.75 and 26.25 <= self.pz <= 35.5
                                          and abs(self.py - GF) < 0.6):
                return an["x"], an["z"]
            return -6.0, MS.BACK_Z
        if self.phase == "gallery" and self.py < 3.0:
            return 0.0, MS.STAIR_Z0
        if self.phase == "study_door":
            return MS.STUDY_DOOR_AT[0], MS.STUDY_DOOR_AT[2]
        if self.phase == "to_terrace":
            return MS.TERRACE_DOOR_AT[0], MS.TERRACE_DOOR_AT[2]
        if self.phase in ("helipad", "liftoff"):
            return MS.HELIPAD_AT[0], MS.HELIPAD_AT[2]
        return None, None

    def _objective_y(self):
        left = self._stragglers()
        if left:
            return left[0]["y"] + 1.5
        if self.phase in ("study_door", "to_terrace", "helipad", "liftoff"):
            return FF + 1.5
        if self.phase == "gallery" and self.py < 3.0:
            return GF + 1.5
        return GF + 1.5 if self.phase in ("enter", "andrei") else 1.5

    def objective_text(self):
        tx, tz = self.objective_point()
        dist = None if tx is None else math.hypot(tx - self.px, tz - self.pz)
        texts = {
            "drive": ("Fight up the drive", None),
            "forecourt": ("Clear the forecourt", None),
            "enter": ("Enter the house", dist),
            "hall": ("Take the grand hall", None),
            "andrei": ("Shut down Andrei M. in the security room", dist),
            "gallery": ("Climb the stairs and clear the galleries", dist if self.py < 3.0 else None),
            "study_door": ("Kick in Retardovici's study", dist),
            "study": ("Kill his personal guard", None),
            "to_terrace": ("Get to the helipad terrace", dist),
            "helipad": ("Clear the helipad before he lifts off", None),
            "liftoff": ("He's getting away", None),
        }
        left = self._stragglers()
        if left and self.brain.near_revive() is None:
            return ("Take out the last of them" if len(left) > 1 else "Take out the last one"), dist
        return texts.get(self.phase, ("Storm the mansion", None))

    def prompt(self):
        act = self._hold_action()
        if act == "revive":
            return "Help ally up", "E", (self.hold / 1.6) if self.hold > 0.0 else None
        if act == "study_door":
            return "Kick the study door", "E", None
        if isinstance(act, tuple) and act[0] == "crate":
            return "Take ammo & medical supplies", "E", None
        if self.toast and self.t - self.toast[0] < 1.6:
            return self.toast[1], None, None
        return None

    # --- draw -------------------------------------------------------------------------------

    def _fire_lights(self):
        out = []
        an = self.brain.andrei
        if an["state"] in ("dying", "done"):
            age = self.t - an["dead_t"]
            hit_s, zap_s, _, _ = B.andrei_timings(an.get("cause", "misfire"))
            if hit_s <= age < zap_s:
                st = 0.5 + 0.5 * math.sin(self.t * 89.0) * math.cos(self.t * 37.0)
                out.append({"pos": (-11.35, GF + 1.5, 31.1), "color": (140, 220, 255),
                            "intensity": 1.6 + 2.8 * (st * st), "range": 10.0 + 3.0 * st})
        for c in self.cars:
            if c["burned"] and not self.veh_fx.has_tag(id(c)):
                age = max(0.0, self.t - c["boom_t"])
                fl = 0.75 + 0.25 * math.sin(self.t * 17.0 + c["x"])
                spike = 3.4 * math.exp(-age * 7.5)
                out.append({
                    "pos": (c["x"], 1.6, c["z"]),
                    "color": (255, 224, 160) if age < 0.2 else (255, 138, 52),
                    "intensity": 1.25 * fl + spike,
                    "range": 10.5 + 7.5 * math.exp(-age * 4.0),
                })
        out.extend(self.veh_fx.active_lights(cap=3))
        for t0, pos in self.booms:
            k = max(0.0, 1.0 - (self.t - t0) / 1.1)
            if k > 0.02:
                out.append({"pos": (pos[0], pos[1] + 1.1, pos[2]), "color": (255, 190, 100),
                            "intensity": 2.8 * k, "range": 15.0})
        out.sort(key=lambda L: math.dist(L["pos"], (self.px, self.py, self.pz)))
        return out[:4]

    def _andrei_scene_fx(self, tm):
        """Compute dynamic rack state, monitor surge index, and security room light level."""
        an = self.brain.andrei
        led_phase = int(tm // 280) % 2
        if an["state"] in ("idle", "intro"):
            return ("intact", 0.0, led_phase), 0, 1.0
        age = self.t - an["dead_t"]
        hit_s, zap_s, _, _ = B.andrei_timings(an.get("cause", "misfire"))
        if age < hit_s:
            return ("intact", 0.0, led_phase), 0, 1.0
        u_hit = age - hit_s
        if u_hit < 0.45:
            tilt = 5.0 + 2.1 * math.exp(-u_hit * 8.5) * math.sin(u_hit * 26.0)
        else:
            tilt = 5.0
        if age < zap_s:
            st = 0.5 + 0.5 * math.sin(self.t * 89.0) * math.cos(self.t * 37.0)
            surge = 1 + (int(age / 0.045) % 3)
            return ("surge", tilt, int(age / 0.05) % 3), surge, 0.55 + 0.85 * st
        u_pop = age - zap_s
        if u_pop < 0.18:
            sec_l = 2.4 * (1.0 - u_pop / 0.18) + 0.10
        else:
            sec_l = 0.10
        return ("ember", tilt, 0), 0, sec_l

    def draw(self, surface):
        if not self._active:
            return
        tm = self.t * 1000.0
        eye, tgt, fov, _ = self.camera()
        up = tuple(ch["state"] == "up" for ch in self.chand)
        rack_state, mon_surge, sec_light = self._andrei_scene_fx(tm)
        r = MS.frame(eye, tgt, fov, lights=self._fire_lights(), t=int(tm),
                     chandeliers_up=up, sec_light=sec_light)
        del _w.LAST[:]
        chs = [(ch["x"], ch["y"], ch["z"]) if ch["state"] != "down" else None for ch in self.chand]
        crates = []
        for idx in range(len(MS.CRATE_SPOTS)):
            if idx in self.crate_anims:
                age = self.t - self.crate_anims[idx]
                open_u = clamp(age / 0.68, 0.0, 1.0)
                raw_l = age / 0.85
                loot_u = 0.0 if raw_l < 0.45 else (-1.0 if raw_l >= 0.78 else clamp((raw_l - 0.45) / 0.33, 0.0, 1.0))
                crates.append((open_u, loot_u))
            elif idx in self.crates_taken:
                crates.append((1.0, -1.0))
            else:
                crates.append((0.0, 0.0))
        car_rows = []
        for c in self.cars:
            if c["burned"] and self.veh_fx.has_tag(id(c)):
                dy, dp, dr = self.veh_fx.hull_transform(id(c))
                car_rows.append((c["x"], c["z"], c["yaw"], c["paint"], True, dy, dp, dr))
            else:
                car_rows.append((c["x"], c["z"], c["yaw"], c["paint"], c["burned"]))
        MS.draw_dynamic_props(r, tm, cams_alive=self.cams_alive, front_open=self.world.front_open,
                              study_open=self.world.study_open, terrace_open=self.world.terrace_open,
                              chandeliers=chs,
                              cars=car_rows,
                              crates=crates, rack_state=rack_state, monitor_surge=mon_surge,
                              study_open_u=(clamp((self.t - self.study_kick_t - KICK_HIT_S) / 0.44, 0.0, 1.0)
                                            if self.study_kick_t is not None else None))
        self._draw_wrecks(r, tm)
        if self.cash_bricks:
            if self._money_mesh is None:
                self._money_mesh = MS.money_bundle(2)
            if getattr(self, "_money_mesh_1", None) is None:
                self._money_mesh_1 = MS.money_bundle(1)
            for b in self.cash_bricks:
                bm = self._money_mesh_1 if b["cnt"] == 1 else self._money_mesh
                if b["settled"]:
                    RW.put(r, bm, b["x"], b["y"], b["z"], b["ry"])
                else:
                    MS._dyn(r, bm, m_mul(rot_y(b["ry"]), m_mul(rot_x(b["rx"]), rot_z(b["rz"]))),
                            (b["x"], b["y"], b["z"]))
        if self.cash_notes and r.visible_sphere((-8.0, GF + 1.0, 31.0), 6.5):
            nm = _banknote_mesh()
            if self._notes_settled_mesh is not None:
                _w.add(r, self._notes_settled_mesh)
            else:
                all_done = all(n["settled"] for n in self.cash_notes)
                notes_m = Mesh()
                for n in self.cash_notes:
                    rot = rot_y(n["yaw"]) if n["settled"] else m_mul(rot_y(n["yaw"]), m_mul(rot_x(n["pitch"]), rot_z(n["roll"])))
                    notes_m.add(nm, rot, (n["x"], n["y"], n["z"]))
                if all_done:
                    self._notes_settled_mesh = notes_m
                _w.add(r, notes_m)
        self._draw_heli(r, tm)
        self._draw_allies(r, tm)
        self._draw_player(r, tm)
        self._draw_andrei(r, tm)
        self._draw_enemies(r, tm)
        self._draw_fx(r, tm)
        f_dur = R.FLASH_S_SUPP if self.weapon != "shotgun" else R.FLASH_S
        f_age = self.t - self.last_flash
        if 0.0 <= f_age < f_dur and self._flash_basis is not None:
            tip, fvec, rx, ry = self._flash_basis
            R.handheld_flash(r, tm, tip, fvec, rx, ry, f_age, self.flash_seed, self.weapon)
        tx, tz = self.objective_point()
        self.marker_screen = self._project(r, (tx, self._objective_y(), tz)) if tx is not None else None
        MS.present(r, surface)
        draw_vignette(surface)
        HUD.draw(surface, self)

    def _draw_wrecks(self, r, tm):
        r.light_cap = 64
        in_house = (-MS.HX <= self.px <= MS.HX and 0.0 <= self.pz <= MS.HZ)
        in_sec = (self.px < -3.5 and self.pz > 25.5 and self.py < 3.0)
        r.marble_refl = 0.34 if (in_house and not in_sec and self.py < MS.FF - 0.5) else 0.0
        r.wetness = 0.28 if self.cp in (0, 4) else 0.0
        r.height_fog = (0.0, 0.0, 1.0, (12, 16, 24)) if self.cp in (1, 2, 3) else (0.018, 0.0, 1.4, (12, 16, 24))
        cam = getattr(r, "cam", None)
        use_gpu = getattr(r, "backend", "") == "gl"
        if self.scorches:
            if use_gpu:
                import numpy as np
                from engine3d.particles import DKIND_SCORCH
                d_rows = []
                for sc in self.scorches:
                    sx, sy, sz, srad = (sc[0], 0.028, sc[1], sc[2]) if len(sc) == 3 else sc
                    if r.visible_sphere((sx, sy, sz), srad + 0.2):
                        d_rows.append((sx, sy, sz, srad, 0.0, 0.086, 0.074, 0.074, 0.90, float(DKIND_SCORCH), 0.0))
                if d_rows:
                    r.add_decals(np.asarray(d_rows, dtype=np.float32))
            else:
                sm = Mesh()
                for sc in self.scorches:
                    sx, sy, sz, srad = (sc[0], 0.028, sc[1], sc[2]) if len(sc) == 3 else sc
                    sm.add(disc_xz(sx, sz, srad, sy, (22, 19, 19), n=12, layer=2 if sy > 0.2 else 1))
                _w.add(r, sm)
        an = self.brain.andrei
        if an["state"] in ("dying", "done"):
            cause = an.get("cause", "misfire")
            age = self.t - an["dead_t"]
            hit_s, zap_s, sit_s, _ = B.andrei_timings(cause)
            blood_pts = []
            if cause == "player":
                sx0, _sy0, sz0 = an.get("shot_pos") or MS.ANDREI_AT
                if age >= 0.08:
                    blood_pts.extend(((sx0 - 0.36, GF + 0.015, sz0 + 0.08, 0.18),
                                      (sx0 - 0.72, GF + 0.015, sz0 - 0.10, 0.12)))
                if age >= hit_s * 0.45:
                    blood_pts.append((sx0 + ANDREI_RACK_DX * 0.45, GF + 0.015, sz0 + 0.05, 0.12))
                if age >= hit_s * 0.80:
                    blood_pts.append((sx0 + ANDREI_RACK_DX * 0.80, GF + 0.015, sz0 - 0.06, 0.14))
                if age >= hit_s:
                    blood_pts.extend(((-11.40, GF + 0.015, 31.18, 0.24), (-11.28, GF + 0.015, 30.96, 0.16)))
                if age >= sit_s - 0.15:
                    u_pool = clamp((age - (sit_s - 0.15)) / 3.2, 0.0, 1.0)
                    ek = R._ease(u_pool)
                    blood_pts.extend(((-11.08, GF + 0.016, 31.20, 0.14 + 0.32 * ek),
                                      (-10.92, GF + 0.016, 31.34, 0.09 + 0.17 * ek),
                                      (-11.24, GF + 0.016, 31.06, 0.08 + 0.14 * ek)))
            if blood_pts:
                if use_gpu:
                    import numpy as np
                    from engine3d.particles import DKIND_BLOOD
                    b_rows = [(bx, by, bz, brad, (bx * 1.3 + bz * 0.7) % math.tau, 0.26, 0.028, 0.032, 0.93,
                               float(DKIND_BLOOD), 0.78) for bx, by, bz, brad in blood_pts]
                    r.add_decals(np.asarray(b_rows, dtype=np.float32))
                else:
                    bm = Mesh()
                    for bx, by, bz, brad in blood_pts:
                        bm.add(disc_xz(bx, bz, brad, by, (68, 10, 12), n=10, layer=2))
                    _w.add(r, bm)
        if not use_gpu and self.blood_drops:
            for bx, by, bz, vx, vy, vz, _age, _life in self.blood_drops:
                r.add_line3d((bx, by, bz), (bx - vx * 0.025, max(GF + 0.016, by - vy * 0.025), bz - vz * 0.025),
                             (108, 14, 16), 2, layer=3)
        for ch in self.chand:
            if ch["state"] == "down":
                MS._dyn(r, MS.chandelier_mesh(), rot_x(16.0), (ch["x"], GF + 0.35, ch["z"]))
        if self.debris:
            dm = Mesh()
            for d in self.debris:
                hot = d["hot"] and self.t - d["t0"] < 1.05
                col = (246, 136, 46) if hot else d["col"]
                dm.add(box(d["sx"], d["sy"], d["sz"], col, emissive=hot),
                       m_mul(rot_y(d["ry"]), rot_x(d["rx"])), (d["x"], d["y"], d["z"]))
            _w.add(r, dm)
        if self.smoke_puffs:
            for pf in self.smoke_puffs:
                age = pf["age"]
                if age < 0.0:
                    continue
                k = clamp(age / pf["dur"], 0.0, 1.0)
                alpha = int(pf["alpha"] * min(1.0, k * 5.0) * (1.0 - k) ** 1.25)
                if alpha >= 16:
                    rad_m = pf["r0"] + (pf["r1"] - pf["r0"]) * math.sqrt(k)
                    warmth = max(0, int(pf["warm"] * (1.0 - k * 1.8)))
                    r.add_sprite((pf["x"], pf["y"], pf["z"]), _smoke_puff_fn(rad_m, alpha, warmth, pf["var"]), layer=2)
        self.veh_fx.draw(r, tm)
        for c in self.cars:
            a = math.radians(c["yaw"])
            fx, fz = math.sin(a), math.cos(a)
            if not r.visible_sphere((c["x"], 1.5, c["z"]), 3.6):
                continue
            if not c["burned"]:
                if c["hp"] < CAR_HP * 0.45:
                    r.add_sprite((c["x"] + fx * 1.2, 1.15, c["z"] + fz * 1.2),
                                 W7.smoke(tm, seed=int(abs(c["x"]) * 13), size_m=0.72), layer=2)
                continue
            if self.veh_fx.has_tag(id(c)):
                continue
            seed = int(abs(c["x"]) * 17 + abs(c["z"]) * 7)
            _w.add(r, W7.flame_mesh((c["x"] + fx * 1.15, 0.85, c["z"] + fz * 1.15),
                                    tm, seed=seed, size=0.82, heat=1.15, cam=cam))
            _w.add(r, W7.flame_mesh((c["x"] - fx * 0.25, 1.05, c["z"] - fz * 0.25),
                                    tm, seed=seed + 5, size=0.68, heat=1.0, cam=cam))
            r.add_sprite((c["x"], 0.05, c["z"]),
                         W7.pool((255, 118, 34), 3.1, intensity=0.38, squash=0.5), layer=_fx.FX_LAYER)
            r.add_sprite((c["x"] + fx * 0.5, 1.35, c["z"] + fz * 0.5),
                         _fx.glow((255, 132, 48), 1.4, int(tm), flicker=0.32,
                                  seed=seed, intensity=0.85, max_px=72), layer=_fx.FX_LAYER)
            r.add_sprite((c["x"] + fx * 0.6, 2.0, c["z"] + fz * 0.6),
                         W7.smoke(tm, seed=seed, size_m=1.45), layer=2)
        for t0, pos in self.booms:
            age = self.t - t0
            bx, by, bz = pos
            seed = int(abs(bx) * 29 + abs(bz) * 11 + t0 * 10)
            if age < 0.34:
                f = (1.0 - age / 0.34) ** 1.8
                r.add_sprite((bx, by + 0.6, bz),
                             _fx.flash(age * 1000.0, col=(255, 228, 168), radius_m=4.6, dur_ms=340),
                             layer=_fx.FX_LAYER)
                r.add_sprite((bx, by + 0.7, bz),
                             _fx.glow((255, 178, 72), 2.6 + age * 9.5, int(tm),
                                      core=(255, 252, 230), intensity=2.2 * f, max_px=220),
                             layer=_fx.FX_LAYER)
            if age < 1.6:
                for i in range(6):
                    a = age - 0.028 * i
                    if not (0.0 <= a < 1.4):
                        continue
                    ang = i * 2.399963 + seed * 0.1
                    exp_k = 1.0 - math.exp(-a * 6.5)
                    col_k = 1.0 - R._ease(clamp((a - 0.4) / 0.95, 0.0, 1.0))
                    rad = (0.62 + 1.05 * exp_k) * col_k
                    spread = (0.3 + 1.7 * exp_k) * (0.65 + 0.35 * (i % 2))
                    if rad > 0.05:
                        fpos = (bx + math.cos(ang) * spread,
                                max(0.08, by + a * (1.35 + 0.18 * i)),
                                bz + math.sin(ang) * spread)
                        _w.add(r, W7.flame_mesh(fpos, tm, seed=seed + i * 13, size=rad, heat=1.35, cam=cam))
            if age < 0.8:
                pk = (1.0 - age / 0.8) ** 1.4
                r.add_sprite((bx, 0.05, bz),
                             W7.pool((255, 148, 56), 4.8 * (0.4 + 0.6 * min(1.0, age * 4.5)),
                                     intensity=0.62 * pk, squash=0.5),
                             layer=_fx.FX_LAYER)
            if age < 1.35:
                for i in range(14):
                    ang = i * 2.399963 + seed * 0.3
                    spd = 4.5 + (i % 5) * 1.4
                    vx, vz = math.cos(ang) * spd, math.sin(ang) * spd
                    vy = 5.0 + (i % 6) * 1.1
                    py = max(0.05, by + 0.3 + vy * age - 4.9 * age * age)
                    if py <= 0.06:
                        continue
                    ta = max(0.0, age - 0.04)
                    ty = max(0.05, by + 0.3 + vy * ta - 4.9 * ta * ta)
                    hot = max(0.0, 1.0 - age / 1.35)
                    col = (int(130 + 125 * hot), int(54 + 160 * hot), int(24 + 80 * hot))
                    r.add_line3d((bx + vx * ta, ty, bz + vz * ta),
                                 (bx + vx * age, py, bz + vz * age), col, 2 if i % 4 == 0 else 1, layer=2)
                r.add_sprite((bx, by + 0.4, bz),
                             W7.sparks(tm, t0 * 1000.0, seed=seed, n=32, speed=10.5, life=1.35),
                             layer=_fx.FX_LAYER)

    def _draw_heli(self, r, tm):
        if self.heli_t0 is None and self.cp < 3:
            return
        pos = self.heli_pos()
        u = 0.0 if self.lift_t0 is None else clamp((self.t - self.lift_t0) / LIFT_S, 0.0, 1.0)
        yaw = MS.HELI_YAW + 25.0 * u
        CS.put_helicopter(r, pos, yaw, -8.0 * u, 5.0 * u, self.rotor, (self.rotor * 2.0) % 360.0)
        _b, _m, _t, info = CS.helicopter_parts()
        seat = CS._xf(info["gunner_seat"], pos, yaw, -8.0 * u, 5.0 * u)
        pose = dict(POSES["stand"], rsh_p=40, rel=30, lsh_p=70, lsh_r=30, spine=-6)
        _w.actor(r, "retardovici", pose, seat, yaw - 90.0, int(tm), seed=12, amp=0.0,
                 expression="angry")
        for k in range(2):
            r.add_sprite(CS._xf((0.0, 0.2, -2.0 - k), pos, yaw, 0.0, 0.0),
                         _fx.beacon((255, 70, 50), 0.28, int(tm), period_ms=900.0, phase=k * 450.0),
                         layer=_fx.FX_LAYER)

    def _door_kick_pose(self, hum, base_pose, kage, use_sg):
        """Full-body breach kick: chamber right knee, snap boot through lock, stride in."""
        wpn_key = "shotgun" if use_sg else "os12"
        cache_key = ("m7player_sg" if use_sg else "m8_biri_os12", "wall")
        tuck = R._wall_down_hold(hum, wpn_key, cache_key)

        chamber = dict(
            POSES["stand"], body_p=-5.0, body_r=-4.0, spine=-6.0, spine_r=-5.0,
            twist=18.0, head_y=-18.0, head_p=6.0, lift=0.0,
            lhip_p=20.0, lhip_r=4.0, lkn=26.0, lank=-8.0,
            rhip_p=94.0, rhip_r=-4.0, rkn=112.0, rank=18.0,
        )
        strike = dict(
            POSES["stand"], body_p=-10.0, body_r=-6.0, spine=-16.0, spine_r=-6.0,
            twist=-16.0, head_y=14.0, head_p=14.0, lift=0.0,
            lhip_p=-14.0, lhip_r=5.0, lkn=18.0, lank=12.0,
            rhip_p=84.0, rhip_r=2.0, rkn=8.0, rank=12.0,
        )
        follow = dict(
            POSES["stand"], body_p=0.0, body_r=0.0, spine=10.0, spine_r=2.0,
            twist=6.0, head_y=-6.0, head_p=4.0, lift=0.0,
            lhip_p=-22.0, lhip_r=3.0, lkn=26.0, lank=10.0,
            rhip_p=36.0, rhip_r=2.0, rkn=30.0, rank=-6.0,
        )
        for st in (chamber, strike, follow):
            for kn in R._ARMS:
                if kn in tuck:
                    st[kn] = tuck[kn]
            st["rifle_p"] = tuck.get("rifle_p", 0.0) + st["spine"] - tuck.get("spine", 0.0)
            st["rifle_y"] = tuck.get("rifle_y", 0.0) + st["twist"] - tuck.get("twist", 0.0)

        if kage < 0.18:
            return R._blend_pose(base_pose, chamber, R._ease(kage / 0.18))
        if kage < KICK_HIT_S:
            q = (kage - 0.18) / max(0.01, KICK_HIT_S - 0.18)
            return R._blend_pose(chamber, strike, q * q * (3.0 - 2.0 * q))
        if kage < 0.34:
            return R._blend_pose(strike, strike, 0.0)
        if kage < 0.48:
            return R._blend_pose(strike, follow, R._ease((kage - 0.34) / 0.14))
        return R._blend_pose(follow, base_pose, R._ease(clamp((kage - 0.48) / (KICK_DUR - 0.48), 0.0, 1.0)))

    def _draw_player(self, r, tm):
        key = ("biribel", OUTFIT_GUARD)
        at = (self.px, self.py, self.pz)
        if self.dying:
            kk = clamp(self.death_t / 0.6, 0.0, 1.0)
            _w.actor(r, key, blend("kneel", "dead_back", kk), at, self.body_yaw, int(tm),
                     seed=93, amp=0.0, rifle_on=False, flags=(), expression="angry",
                     shadow=(2, -0.35))
            self._muzzle = self._flash_basis = None
            return
        swapping = (self.swapping > 0.0)
        swap_u = clamp((self._swap_dur - self.swapping) / max(0.01, self._swap_dur), 0.0, 1.0) if swapping else 1.0
        draw_weapon = self._swap_from if (swapping and swap_u < 0.5) else self.weapon
        use_sg = (draw_weapon == "shotgun")
        flags = ("shotgun", "nopump") if use_sg else ("os12", "nomag")
        hum = _w.hum(key, flags=flags)
        pose = self._player_pose()
        aim_on = (self.ads > 0.5 or self.t - self.last_fire < 0.45)
        pump = 0.0
        sg_shell = False
        mag_mode, mag_t = "attached", 0.0
        mode = "aim" if aim_on else "ready"
        if swapping:
            pose = T._swap_pose(hum, pose, draw_weapon, swap_u)
            if self._swap_from == "shotgun" and self._swap_to == "rifle":
                blade_k = 1.0 - R._ease(swap_u)
            elif self._swap_from == "rifle" and self._swap_to == "shotgun":
                blade_k = R._ease(swap_u)
            else:
                blade_k = 1.0 if use_sg else 0.0
            draw_yaw = self.body_yaw + R.SG_BLADE_YAW * blade_k
            if swap_u > 0.65:
                settle = math.sin((swap_u - 0.65) / 0.35 * math.pi)
                pose["rifle_p"] = pose.get("rifle_p", 0.0) - 3.5 * settle
        elif use_sg:
            if self.reloading > 0.0:
                pose, pump, sg_shell = R.sg_reload_pose(
                    hum, pose, self._reload_dur - self.reloading, self._reload_dur,
                    shells=self._reload_n, dry=self._reload_dry)
                if self.wall_k > 0.005:
                    pose["rifle_p"] = pose.get("rifle_p", 0.0) + 38.0 * self.wall_k
                    pose["rsh_p"] = pose.get("rsh_p", 0.0) - 12.0 * self.wall_k
                    pose["lsh_p"] = pose.get("lsh_p", 0.0) - 10.0 * self.wall_k
            else:
                pump = R._pump_k(self.t - self.pump_at)
                pose = R._shotgun_hold(hum, pose, mode, ("m7player_sg", mode), pump)
            draw_yaw = self.body_yaw + R.SG_BLADE_YAW
        else:
            if self.reloading > 0.0:
                pose, mag_mode, mag_t = T._os12_reload_pose(
                    hum, pose, self.RELOAD_S - self.reloading, self.RELOAD_S)
                if self.wall_k > 0.005:
                    pose["rifle_p"] = pose.get("rifle_p", 0.0) + 38.0 * self.wall_k
                    pose["rsh_p"] = pose.get("rsh_p", 0.0) - 12.0 * self.wall_k
                    pose["lsh_p"] = pose.get("lsh_p", 0.0) - 10.0 * self.wall_k
            else:
                pose = R._held(hum, pose, "os12", mode, ("m8_biri_os12", mode))
            draw_yaw = self.body_yaw
        pose, draw_yaw, rev_active = (
            REV.apply_player_revive(self, hum, pose, at, draw_yaw, use_sg) if not swapping else (pose, draw_yaw, False)
        )
        kick_active = (not rev_active and not swapping and self.study_kick_t is not None)
        if kick_active:
            pose = self._door_kick_pose(hum, pose, self.t - self.study_kick_t, use_sg)
            draw_yaw = self.body_yaw
        if not rev_active and not swapping and self.reloading <= 0.0 and self.crate_act is not None:
            ct0, _cidx, cx, cy, cz, cyaw = self.crate_act
            cage = self.t - ct0
            u = clamp(cage / 0.85, 0.0, 1.0)
            bk = R._ease(u / 0.16) if u < 0.16 else (1.0 - R._ease((u - 0.76) / 0.24) if u > 0.76 else 1.0)
            rel_yaw = clamp(R._wrap(R._yaw(cx - self.px, cz - self.pz) - draw_yaw), -55.0, 55.0)
            pose = dict(pose)
            pose["spine"] = pose.get("spine", 0.0) + 22.0 * bk
            pose["twist"] = pose.get("twist", 0.0) + rel_yaw * 0.55 * bk
            pose["head_y"] = pose.get("head_y", 0.0) + rel_yaw * 0.45 * bk
            pose["head_p"] = pose.get("head_p", 0.0) + 24.0 * bk
            if not self.pmoving:
                for k_leg, amt in (("lhip_p", 18.0), ("rhip_p", 14.0), ("lkn", 26.0), ("rkn", 22.0)):
                    pose[k_leg] = pose.get(k_leg, 0.0) + amt * bk
            cradle = {"rsh_p": -10.0, "rsh_r": 14.0, "rsh_y": 0.0, "rel": 58.0,
                      "rifle_p": pose.get("spine", 0.0) + 26.0, "rifle_y": -24.0}
            for kn, vb in cradle.items():
                va = pose.get(kn, 0.0)
                pose[kn] = va + ((vb - va + 180.0) % 360.0 - 180.0) * bk
            cy_w = 0.03 if cy == 0.0 else cy + 0.015
            lid_ang = MS.crate_lid_angle(clamp(cage / 0.68, 0.0, 1.0))
            hinge = (0.0, 0.3955, 0.236)
            local_p = m_apply(rot_y(-cyaw), (self.px - cx, 0.0, self.pz - cz))
            grip_x = clamp(local_p[0], -0.24, 0.24)
            lip_dip = -0.025 * math.sin(min(1.0, cage / 0.14) * math.pi) if cage < 0.14 else 0.0
            lip_w = v_add((cx, cy_w, cz),
                          m_apply(rot_y(cyaw), v_add(hinge, m_apply(rot_x(lid_ang), (grip_x, 0.02 + lip_dip, -0.45)))))
            tray_w = (cx, cy_w + 0.36, cz)
            dy_r = math.radians(draw_yaw)
            chest_w = (self.px + math.sin(dy_r) * 0.14, self.py + 1.02, self.pz + math.cos(dy_r) * 0.14)
            if u < 0.48:
                tgt = lip_w
            elif u < 0.64:
                q = R._ease((u - 0.48) / 0.16)
                tgt = tuple(lip_w[i] + (tray_w[i] - lip_w[i]) * q for i in range(3))
            else:
                q = R._ease((u - 0.64) / 0.22)
                tgt = tuple(tray_w[i] + (chest_w[i] - tray_w[i]) * q for i in range(3))
            ik_pose = _solve_arm_safe(hum, pose, at, draw_yaw, "l", tgt, ((0.5, -1.0, 0.1),) + POLES)
            for kn in ("lsh_p", "lsh_r", "lsh_y", "lel"):
                va, vb = pose.get(kn, 0.0), ik_pose.get(kn, 0.0)
                pose[kn] = va + ((vb - va + 180.0) % 360.0 - 180.0) * bk
        elif not rev_active and not swapping and not kick_active and self.reloading <= 0.0:
            if self.wall_k > 0.005:
                pose = R.apply_wall_down(
                    hum, pose, "shotgun" if use_sg else "os12", self.wall_k,
                    ("m7player_sg" if use_sg else "m8_biri_os12", "wall"),
                )
        if rev_active:
            pump = 0.0
            sg_shell = False
            mag_mode = "attached"
        joints = _w.actor(r, key, pose, at, draw_yaw, int(tm), seed=93, amp=0.0 if (rev_active or kick_active) else 0.12,
                          rifle_on=True, flags=flags, expression="stern" if rev_active else "angry",
                          shadow=(2, -0.35))
        if use_sg and joints:
            R.draw_shotgun_pump(r, joints.get("rhand"), joints.get("rifle_m"), pump)
            if sg_shell:
                R.draw_sg_shell(r, joints.get("lhand"), joints.get("rifle_m"))
        elif not use_sg and joints:
            T.TrapScene._draw_os12_mag(self, r, joints, mag_mode, mag_t)
        rm = joints.get("rifle_m") if joints else None
        hand = joints.get("rhand") if joints else None
        if not rev_active and not kick_active and rm is not None and hand is not None:
            off = m_apply(rm, R.BORE_LOCAL["shotgun" if use_sg else "rifle"])
            tip = (hand[0] + off[0], hand[1] + off[1], hand[2] + off[2])
            self._flash_basis = (tip, C._f_unit(m_apply(rm, (0.0, 0.0, 1.0))),
                                 C._f_unit(m_apply(rm, (1.0, 0.0, 0.0))),
                                 C._f_unit(m_apply(rm, (0.0, 1.0, 0.0))))
            self._muzzle = tip
        else:
            self._muzzle = (self.px, self.py + 1.38, self.pz)
            self._flash_basis = None

    def _ally_pose(self, a, gun, hum, tag):
        if a["state"] == "down":
            return dict(POSES["slump"])
        stance = _hold_cached(hum, dict(POSES["ready"]), gun, "ready", key=(tag, "ready"))
        aiming = self.t - a.get("aim", -9.0) < B.ALLY_HOLD
        if aiming:
            slope = round(clamp(a.get("slope", 0.0), -0.4, 0.4), 1)
            aim_st = dict(blend(POSES["stand"], "aim", 0.85),
                          twist=R.AIM_TWIST, head_y=-0.8 * R.AIM_TWIST)
            aim_pose = _hold_cached(hum, aim_st, gun, "aim",
                                    aim=(0.0, 1.45 + 10.0 * slope, 10.0),
                                    key=(tag, slope))
            up = clamp((self.t - a.get("raised", -9.0)) / B.ALLY_RAISE, 0.0, 1.0)
            stance = aim_pose if up >= 1.0 else blend(stance, aim_pose, R._ease(up))
        k = a.get("walk_k", 0.0)
        if k <= 0.0:
            return stance
        phase = a.get("gait", 0.0) / gait_cycle_m(3.4) * math.tau
        lower = locomotion_pose(3.4, 0.0, phase)
        run = mask_pose(lower, stance)
        d_tw = lower.get("twist", 0.0) * (0.45 if aiming else 0.65)
        d_sp = lower.get("spine", 0.0) * (0.45 if aiming else 0.60)
        run["body_r"] = lower.get("body_r", 0.0)
        run["spine_r"] = lower.get("spine_r", 0.0) * 0.85
        run["spine"] = stance.get("spine", 0.0) + d_sp
        run["twist"] = stance.get("twist", R.AIM_TWIST if aiming else 0.0) + d_tw
        run["head_y"] = stance.get("head_y", 0.0) - d_tw * 0.8
        run["rifle_p"] = stance.get("rifle_p", 0.0) + d_sp
        run["rifle_y"] = stance.get("rifle_y", 0.0) + d_tw
        return run if k >= 1.0 else blend(stance, run, R._ease(k))

    def _draw_allies(self, r, tm):
        for name, a, seed in (("bodi", self.brain.bodi, 61), ("alex", self.brain.alex, 62)):
            key = ("ally", name)
            gun = "os12" if name == "bodi" else "m7rifle"
            flags = ("os12",) if name == "bodi" else ()
            hum = _w.hum(key, flags=flags)
            base_pose = self._ally_pose(a, gun, hum, "m8d_" + name)
            pose, armed, expr, _ = REV.ally_pose_and_hand(
                self, name, a, hum, base_pose, a["yaw"], seed=seed,
            )
            if not armed:
                REV.draw_ground_rifle(r, a, gun)
            living_down = (a["state"] == "down" or REV.is_reviving(self, name))
            joints = _w.actor(r, key, pose, (a["x"], a["y"], a["z"]), a["yaw"], int(tm),
                              seed=seed, amp=0.0 if living_down else 0.25, rifle_on=armed,
                              flags=flags, expression=expr, mouth=0.0, shadow=(2, -0.35))
            a["muzzle"] = joints.get("muzzle") if joints else None
            if a["state"] == "down" and not REV.is_reviving(self, name):
                r.add_sprite((a["x"], a["y"] + 1.6, a["z"]), _fx.glow((255, 90, 70), 0.28, tm, intensity=0.75,
                                                                       core=(255, 160, 140), flicker=0.3),
                             layer=_fx.FX_LAYER)

    def _draw_lightning_bolt(self, r, p0, p1, segs, rng, spread=0.14):
        pts = [p0]
        dx, dy, dz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
        for i in range(1, segs):
            u = i / segs
            env = math.sin(u * math.pi)
            pts.append((
                p0[0] + dx * u + rng.uniform(-spread, spread) * env,
                p0[1] + dy * u + rng.uniform(-spread, spread) * env,
                p0[2] + dz * u + rng.uniform(-spread, spread) * env,
            ))
        pts.append(p1)
        for i in range(segs):
            r.add_line3d(pts[i], pts[i + 1], (70, 170, 255), width=3, layer=4)
            r.add_line3d(pts[i], pts[i + 1], (235, 252, 255), width=1, layer=4)

    def _torso_basis_from_joints(self, joints, yaw, pose, fallback_pos):
        if joints and joints.get("torso_m") is not None:
            return joints["torso_m"], joints.get("chest") or fallback_pos
        p_ch = joints.get("chest") if joints else None
        p_hd = joints.get("head") if joints else None
        if p_ch is not None and p_hd is not None and v_len((p_hd[0] - p_ch[0], p_hd[1] - p_ch[1], p_hd[2] - p_ch[2])) > 0.05:
            up = v_norm((p_hd[0] - p_ch[0], p_hd[1] - p_ch[1], p_hd[2] - p_ch[2]))
            yr = math.radians(yaw)
            f_hint = (math.sin(yr), 0.0, math.cos(yr))
            # right = up x f_hint, fwd = right x up (left-handed basis columns)
            rx, ry_, rz = up[1] * f_hint[2] - up[2] * f_hint[1], up[2] * f_hint[0] - up[0] * f_hint[2], up[0] * f_hint[1] - up[1] * f_hint[0]
            if v_len((rx, ry_, rz)) < 1e-3:
                rx, ry_, rz = 1.0, 0.0, 0.0
            right = v_norm((rx, ry_, rz))
            fwd = (right[1] * up[2] - right[2] * up[1], right[2] * up[0] - right[0] * up[2], right[0] * up[1] - right[1] * up[0])
            rot = (right[0], up[0], fwd[0], right[1], up[1], fwd[1], right[2], up[2], fwd[2])
            return rot, p_ch
        rot = m_mul(rot_y(yaw), m_mul(rot_x(pose.get("body_p", 0.0)), rot_z(pose.get("body_r", 0.0))))
        return rot, p_ch or (fallback_pos[0], fallback_pos[1] + 1.15, fallback_pos[2])

    def _draw_andrei(self, r, tm):
        a = self.brain.andrei
        if not r.visible_sphere((a["x"], a["y"] + 0.9, a["z"]), 2.8):
            return
        hum = _w.hum("andrei_m")
        if a["state"] == "idle":
            pose = dict(POSES["stand"], spine=8, head_p=6)
            _w.actor(r, "andrei_m", pose, (a["x"], a["y"], a["z"]), a["yaw"], int(tm),
                     seed=44, amp=0.15, mouth=0.0, expression="neutral", shadow=(2, -0.35))
        elif a["state"] == "intro":
            pose = R._held(hum, dict(POSES["stand"]), "pistol", "pistol_aim", ("andrei_pistol", "aim"))
            joints = _w.actor(r, "andrei_m", pose, (a["x"], a["y"], a["z"]), a["yaw"], int(tm),
                              seed=44, amp=0.2, expression="angry", shadow=(2, -0.35))
            if joints and joints.get("rhand") is not None:
                if self._pistol_mesh is None:
                    self._pistol_mesh = MS.pistol_mesh()
                a["drop_p0"] = joints["rhand"]
                a["drop_yaw"] = a["yaw"]
                gun_rot = m_mul(rot_y(a["yaw"]),
                                m_mul(rot_y(pose.get("rifle_y", 0.0)), rot_x(pose.get("rifle_p", 0.0))))
                m = Mesh()
                m.add(self._pistol_mesh, gun_rot, joints["rhand"])
                _w.add(r, m)
        else:
            age = self.t - a["dead_t"]
            cause = a.get("cause", "misfire")
            hit_zone = a.get("hit_zone", "chest")
            hit_s, zap_s, _sit_s, _down_s = B.andrei_timings(cause)
            pose, off, yaw = _andrei_death_anim(
                age, cause=cause, hit_zone=hit_zone,
                shot_yaw=a.get("shot_yaw", 90.0),
                had_gun=a.get("had_gun", True),
            )
            pos = (a["x"] + off[0], a["y"], a["z"] + off[2])
            zapping = (hit_s <= age < zap_s)
            expr = "surprised" if (zapping or (cause == "player" and age < zap_s) or (cause == "misfire" and ANDREI_SHOT_S <= age < zap_s)) else "closed"
            mouth = 0.85 if zapping else 0.0
            joints = _w.actor(r, "andrei_m", pose, pos, yaw, int(tm), seed=44, amp=0.0, mouth=mouth,
                              expression=expr, shadow=(2, -0.35))
            shot_blood = (cause == "player")
            charred = (age >= hit_s)
            need_places = (shot_blood or charred or (cause == "misfire" and age < hit_s))
            by_slot, root_w = None, (0.0, 0.0, 0.0)
            if need_places:
                places_w, _jw, root_w = hum.pose_world(pose, pos, yaw, rifle_on=False)
                by_slot = {pl[0]: (pl[2], pl[3]) for pl in places_w}
            if (shot_blood or charred) and by_slot and 1 in by_slot:
                t_rot, t_org = by_slot[1]
                t_pos = v_add(t_org, root_w)
                fz = 0.142 if hum.spec.get("vest") is None else 0.152
                MS._dyn(r, _wound_patch_mesh(shot_blood, charred, fz), t_rot, t_pos)
            if shot_blood and hit_zone == "head" and by_slot and 2 in by_slot:
                h_rot, h_org = by_slot[2]
                h_pos = v_add(h_org, root_w)
                MS._dyn(r, _head_wound_mesh(hum.spec.get("head_w", 1.0)), h_rot, h_pos)
            if zapping:
                tick = int(age / 0.035)
                rng = random.Random(9100 + tick)
                rx, ry, rz = MS.ANDREI_RACK_AT
                chest = (joints.get("chest") if joints else None) or (pos[0], pos[1] + 1.15, pos[2])
                head = (joints.get("head") if joints else None) or (pos[0], pos[1] + 1.55, pos[2])
                lhand = (joints.get("lhand") if joints else None) or (pos[0] + 0.10, pos[1] + 1.25, pos[2] - 0.42)
                rhand = (joints.get("rhand") if joints else None) or (pos[0] + 0.10, pos[1] + 1.25, pos[2] + 0.42)
                bus_a = (rx - 0.06, ry + 1.25, rz - 0.18)
                bus_b = (rx - 0.06, ry + 0.95, rz + 0.18)
                bus_c = (rx - 0.06, ry + 1.52, rz + 0.04)
                for src, dst, segs in ((bus_a, chest, 6), (bus_b, chest, 5), (bus_c, head, 6),
                                       (chest, lhand, 4), (chest, rhand, 4)):
                    self._draw_lightning_bolt(r, src, dst, segs, rng, spread=0.14)
                # secondary jumps to adjacent racks and overhead conduit
                self._draw_lightning_bolt(r, (rx - 0.08, ry + 1.8, rz - 0.42), (-11.65, ry + 1.75, 28.45), 7, rng, spread=0.22)
                self._draw_lightning_bolt(r, (rx - 0.08, ry + 1.8, rz + 0.42), (-11.65, ry + 1.75, 33.55), 7, rng, spread=0.22)
                self._draw_lightning_bolt(r, (rx - 0.12, ry + 2.05, rz), (-12.0, ry + 2.38, rz), 4, rng, spread=0.10)
                for gp in (bus_a, chest, lhand, rhand):
                    r.add_sprite(gp, _fx.glow((140, 225, 255), 0.52, int(tm), core=(245, 252, 255),
                                              intensity=1.55, max_px=48), layer=_fx.FX_LAYER)
            if self._pistol_mesh is None:
                self._pistol_mesh = MS.pistol_mesh()
            m = Mesh()
            if cause == "misfire" and age < hit_s:
                if joints and joints.get("rhand") is not None:
                    a["rack_drop_p0"] = joints["rhand"]
                    if by_slot and 12 in by_slot:
                        f_rot = by_slot[12][0]
                        sc = getattr(hum, "_scale", 1.0) or 1.0
                        if sc != 1.0:
                            f_rot = tuple(v / sc for v in f_rot)
                        gun_rot = m_mul(f_rot, rot_x(90.0))
                    else:
                        gun_rot = m_mul(rot_y(yaw), rot_x(90.0 - pose["rsh_p"] - pose["rel"] - pose["spine"]))
                    m.add(self._pistol_mesh, gun_rot, joints["rhand"])
            elif cause == "misfire":
                p0 = a.get("rack_drop_p0") or (a["x"] + ANDREI_RACK_DX + 0.30, a["y"] + 1.50, a["z"] + 0.20)
                dp, drot = _dropped_pistol_xform(age - hit_s, p0, yaw, a["y"] + 0.032)
                m.add(self._pistol_mesh, drot, dp)
            elif a.get("had_gun", True):
                p0 = a.get("drop_p0") or (a["x"] + 0.25, a["y"] + 1.22, a["z"] + 0.15)
                dp, drot = _dropped_pistol_xform(age, p0, a.get("drop_yaw", yaw), a["y"] + 0.032)
                m.add(self._pistol_mesh, drot, dp)
            if m.faces:
                _w.add(r, m)

    def _draw_enemies(self, r, tm):
        real = self.brain
        one = getattr(self, "_one_enemy", None)
        if one is None:
            one = self._one_enemy = _OneEnemy(real, {})
        one._b = real
        try:
            for e in real.enemies:
                if e["alive"] and not e["live"] and self.t < e["spawn_at"]:
                    continue
                spawn_y = e.setdefault("_spawn_y", e["y"])
                fall = e.get("fall")
                if not e["alive"] and fall is not None and fall.rest is not None:
                    if not r.visible_sphere((e["x"], e["y"] + 0.3, e["z"]), 1.8):
                        continue
                self._floor_hint = min(spawn_y, fall.rag.pos["pelvis"][1] + 0.5) if fall is not None else spawn_y
                one.enemies = [e]
                self.brain = one
                T.TrapScene._draw_enemies(self, r, tm)
                if e["alive"] and e["y"] >= GF - 0.1:
                    r.add_blob_shadow((e["x"], e["y"] + 0.02, e["z"]), 0.34, 0.30, 0.40,
                                      layer=2, bias=-0.35)
                if not e["alive"] and e.get("fall") is not None:
                    e["y"] = e["fall"].support_y
        finally:
            self.brain = real
            self._floor_hint = self.py

    def _draw_fx(self, r, tm):
        an = self.brain.andrei
        sec_floor = MS.GF if (an["state"] in ("dying", "done") and abs(self.py - MS.GF) < 1.5) else self.py
        if self.blood_drops and getattr(r, "backend", "") == "gl":
            self._ensure_fx_pool()
        if getattr(r, "backend", "") == "gl":
            now = self.t
            if self._muzzle and now - self.last_fire < 0.025:
                if getattr(self, "_fx_muzzle_t", -1.0) != self.last_fire:
                    self._fx_muzzle_t = self.last_fire
                    pool = getattr(self, "_fx_pool", None)
                    if pool is None:
                        from engine3d.particles import ParticlePool
                        pool = self._fx_pool = ParticlePool(1024, seed=808)
                    pool.burst_muzzle(self._muzzle, R._fwd(self.yaw, self.pitch), n=4)
            if getattr(self, "_fx_pool", None) is not None:
                dt = max(0.0, min(0.05, now - getattr(self, "_fx_last_t", now)))
                self._fx_last_t = now
                self._fx_pool.update(dt, floor_y=sec_floor)
                self._fx_pool.submit(r)
        saved_imp = self.impacts
        if getattr(r, "backend", "") == "gl" or self.blood_drops:
            self.impacts = [it for it in saved_imp if it[2] != "blood"]
        try:
            T.TrapScene._draw_fx(self, r, tm)
        finally:
            self.impacts = saved_imp

    def handle_event(self, event):
        if not self._active or self.paused:
            return
        if not self.dying and not REV.is_locking(self) and not self._kick_locking():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    self._switch_weapon()
                    return
                if event.key == pygame.K_1:
                    self._switch_weapon("rifle")
                    return
                if event.key == pygame.K_2:
                    self._switch_weapon("shotgun")
                    return
            elif event.type == pygame.MOUSEWHEEL and event.y:
                self._switch_weapon()
                return
        if self._kick_locking() and event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
            return
        R.RaidScene.handle_event(self, event)


_SCENE = None


def scene():
    global _SCENE
    if _SCENE is None:
        _SCENE = MansionScene()
    return _SCENE


def begin():
    return scene().begin()


def active():
    return _SCENE is not None and _SCENE.active()


def update(keys=None):
    return scene().update(keys)


def draw(surface):
    return scene().draw(surface)


def handle_event(event):
    return scene().handle_event(event)


def set_paused(paused):
    if _SCENE is not None:
        _SCENE.set_paused(paused)


def abort():
    if _SCENE is not None and _SCENE.active():
        _SCENE._active = False
        _SCENE.paused = False
        STATE.m8_mansion_active = False
        _SCENE._grab(False)
        if _SCENE.audio is not None:
            try:
                _SCENE.audio.stop_loops()
            except Exception:
                pass


def force_finish(reason="fallback"):
    if _SCENE is not None:
        return _SCENE.finish(reason)
    return False