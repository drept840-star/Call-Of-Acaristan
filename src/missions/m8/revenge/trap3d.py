"""Mission 8 Revenge - phases 2 and 3: the Trap and the Gantry, one third-person scene.

Dawn on the Route 12 toll plaza (the M2 kill box, rebuilt).  Instead of three
timed waves fought from spawn cover, Biribel and Bodi fight north booth by
booth through Vasile's orchestrated ambush:
- Beat 1 (the wrecks): floodlights snap on, a gantry overwatch laser pins the
  apron, breachers push out of the burned convoy while Vasile comes over the
  plaza PA.
- Beat 2 (the booths): advancing past the wrecks unlocks the resupply crate and
  the toll kiosk, whose barrier bypass triggers the Guard convoy truck down the
  north lane; shooting its engine or detonating the lane drum crashes it early
  before it dismounts a heavy squad.
- Beat 3 (the gantry foot): pushing past the burnt tanker draws out Vasile
  above the catwalk rail and springs the final control-yard defense around the
  gantry legs.

Biribel carries two guns: the Fallow 12 buckshot for close work and the OS-12
for the 40-80 m sniper and truck lanes (Q, 1, 2 or the wheel swaps them).
Every Guard on Route 12 carries the same OS-12.  The Guard answers a camper
with smoke canisters that break the overwatch lock.

Contract (as ``missions.m7.raid3d``): ``begin`` / ``active`` / ``update`` /
``draw`` / ``handle_event`` / ``set_paused`` / ``abort`` / ``force_finish``.
Checkpoints: 0 start, 1 and 2 after the first two beats, 3 the gantry.
"""
from functools import lru_cache
import math
import random

import pygame

from core.config import HEIGHT, WIDTH, audio, draw_vignette
from core.outfits import OUTFIT_GUARD
from core.state import STATE
from cutscenes import death3d as D
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from cutscenes import m7world3d as F
from engine3d import Mesh, POSES, blend, box, clamp
from engine3d.core import disc_xz, m_apply, rot_x, rot_y, rot_z
from engine3d.hold import POLES, hold_cached as _hold_cached, hold_frame as _hold_frame, solve_arm_safe as _solve_arm_safe
from engine3d.rig import os12_mag_mesh as _os12_mag_mesh
from missions.m7 import raid3d as R
from missions.m7 import raid_world as RW

from . import chase3d as C
from . import set3d as S3
from . import trap_brain as B
from . import trap_hud as HUD
from . import trap_world as W

RES = S3.RES
MAG, RESERVE0, RELOAD_S = R.MAG, R.RESERVE0, R.RELOAD_S
CP_STATE = {1: (-60.0, -2.0, 40.0), 2: (-34.0, 26.0, 35.0), 3: (6.0, 50.0, 20.0)}
CLIMB_HOLD_S = 0.35
CLIMB_S = 5.6
STEP_M = 0.8                    # stride metres per footstep
RUNGS = len(S3.LADDER_RUNG_YS)
CLIMB_UP = S3.LADDER_CLIMB_UP   # share of the climb on the rungs; the rest steps onto the deck
LADDER_FOOT = (S3.LADDER_X, S3.LADDER_Z - 0.45)
CATWALK_X = (-1.6, 8.8)
CATWALK_HALF = 0.5
VASILE_REACH = 2.8

BARREL_DMG = 135.0
BARREL_R = 6.2
BARREL_TRUCK_DMG = 260.0
APPROACH_ADV_Z = -10.5          # stepping out onto the apron springs the ambush
ADVANCE_1_PT = (-45.0, 14.0)    # mid-plaza booths & supply crate
ADVANCE_2_PT = (-22.0, 38.0)    # past the burnt tanker toward the gantry yard
FORCE_ADV_S = 24.0              # safety net so stalling between waves never locks

# Biribel's two guns: the Fallow 12 buckshot and the OS-12.
WPN_SPECS = {
    "shotgun": dict(label="FALLOW 12", cal="12GA", kind="shell", mag=6, reserve0=24,
                    cap=36, gap=0.92, reload_s=2.2, fov_ads=48.0),
    "rifle": dict(label="OS-12", cal="5.56X45", kind="stick", mag=30, reserve0=90,
                  cap=150, gap=0.115, reload_s=1.45, fov_ads=44.0),
}

# The handheld muzzle flash lives in M7's raid so both missions share it.
FLASH_S, FLASH_S_SUPP, BORE_LOCAL = R.FLASH_S, R.FLASH_S_SUPP, R.BORE_LOCAL
handheld_flash = R.handheld_flash


_fwd, _right, _wrap, _yaw, _ease = R._fwd, R._right, R._wrap, R._yaw, R._ease


def _barrel_mesh():
    m = Mesh()
    rust = (146, 48, 34)
    band = (44, 42, 46)
    m.add(box(0.62, 0.94, 0.62, rust, center=(0.0, 0.47, 0.0)))
    for yy in (0.24, 0.72):
        m.add(box(0.66, 0.08, 0.66, band, center=(0.0, yy, 0.0)))
    m.add(box(0.18, 0.06, 0.18, (222, 166, 54), center=(0.12, 0.97, 0.12)))
    return m


def _tower_mesh():
    h = W.TOWER_H
    hw = W.TOWER_HALF
    steel = (58, 64, 72)
    deck = (74, 72, 68)
    m = Mesh()
    for sx in (-hw + 0.1, hw - 0.1):
        for sz in (-hw + 0.1, hw - 0.1):
            m.add(box(0.14, h, 0.14, steel, center=(sx, h * 0.5, sz)))
    m.add(box(hw * 2.0, 0.12, hw * 2.0, deck, center=(0.0, h - 0.06, 0.0)))
    for side in (-1.0, 1.0):
        m.add(box(hw * 2.0, 0.07, 0.07, steel, center=(0.0, h + 0.85, side * (hw - 0.06))))
        m.add(box(0.07, 0.07, hw * 2.0, steel, center=(side * (hw - 0.06), h + 0.85, 0.0)))
        for sx in (-hw + 0.1, hw - 0.1):
            m.add(box(0.07, 0.9, 0.07, steel, center=(sx, h + 0.45, side * (hw - 0.06))))
    return m


def _fusebox_mesh(alive=True):
    m = Mesh()
    m.add(box(0.28, 1.35, 0.28, (54, 58, 62), center=(0.0, 0.675, 0.0)))
    m.add(box(0.56, 0.64, 0.36, (84, 88, 92) if alive else (36, 36, 38),
              center=(0.0, 1.15, 0.0)))
    col = (240, 186, 64) if alive else (40, 32, 28)
    m.add(box(0.12, 0.12, 0.04, col, center=(0.0, 1.24, -0.19), emissive=alive))
    return m


def _supply_mesh(full=True):
    m = Mesh()
    m.add(box(0.84, 0.46, 0.54, (64, 72, 54), center=(0.0, 0.23, 0.0)))
    m.add(box(0.88, 0.08, 0.58, (82, 88, 68), center=(0.0, 0.48, 0.0)))
    if full:
        m.add(box(0.32, 0.14, 0.24, (190, 44, 38), center=(-0.16, 0.58, 0.0)))
        m.add(box(0.20, 0.10, 0.14, (152, 44, 36), center=(0.22, 0.56, 0.05)))
    return m


def _pole_mesh(lit=True):
    m = Mesh()
    m.add(box(0.18, W.FLOOD_H, 0.18, (58, 62, 68), center=(0.0, W.FLOOD_H * 0.5, 0.0)))
    m.add(box(0.58, 0.22, 0.26, (44, 48, 52), center=(0.0, W.FLOOD_H + 0.06, 0.0)))
    col = (255, 224, 166) if lit else (42, 44, 48)
    m.add(box(0.44, 0.14, 0.06, col, center=(0.0, W.FLOOD_H + 0.04, -0.14), emissive=lit))
    return m


def _kiosk_mesh(open_=False):
    """The toll kiosk by the north lane: a lit green panel once it is bypassed."""
    m = Mesh()
    m.add(box(0.54, 1.26, 0.42, (62, 68, 74), center=(0.0, 0.63, 0.0)))
    m.add(box(0.58, 0.08, 0.46, (44, 48, 54), center=(0.0, 1.28, 0.0)))
    col = (118, 224, 132) if open_ else (238, 88, 64)
    m.add(box(0.14, 0.14, 0.04, col, center=(0.0, 1.04, -0.22), emissive=True))
    return m


def _barrier_arm_mesh(pitch=0.0):
    """The north-lane barrier arm, striped red and white.

    ``pitch`` lifts the arm about its hinge (degrees) so the open gate reads.
    """
    m = Mesh()
    m.add(box(0.36, 0.96, 0.36, (56, 60, 66), center=(0.0, 0.48, 0.0)))
    arm = Mesh()
    for i in range(6):
        col = (212, 48, 42) if i % 2 == 0 else (228, 224, 214)
        arm.add(box(0.90, 0.10, 0.10, col, center=(0.45 + i * 0.90, 0.0, 0.0)))
    if pitch:
        m.add(arm, rot_z(math.radians(pitch)), (0.0, 0.88, 0.0))
    else:
        m.add(arm)
    return m


def _grenade_mesh():
    """Low-poly segmented frag grenade: dark-olive ribbed body, fuze neck, spoon."""
    m = Mesh()
    olive, groove, steel, brass = (68, 78, 52), (42, 48, 34), (96, 102, 108), (176, 146, 74)
    m.add(box(0.082, 0.096, 0.082, olive, center=(0.0, 0.0, 0.0)))
    m.add(box(0.088, 0.016, 0.088, groove, center=(0.0, 0.018, 0.0)))
    m.add(box(0.088, 0.016, 0.088, groove, center=(0.0, -0.018, 0.0)))
    m.add(box(0.038, 0.032, 0.038, steel, center=(0.0, 0.060, 0.0)))
    m.add(box(0.044, 0.014, 0.044, brass, center=(0.0, 0.078, 0.0)))
    m.add(box(0.016, 0.080, 0.014, steel), m=rot_x(16), t=(0.0, 0.034, 0.046))
    return m


_BLAST_PUFF_COL = {
    "soot": ((32, 30, 30), (68, 58, 54)),
    "dust": ((112, 102, 90), (154, 142, 126)),
}


@lru_cache(maxsize=128)
def _blast_puff_img(kind, rad, alpha, variant):
    shade, lit = _BLAST_PUFF_COL[kind]
    small = pygame.Surface((32, 32), pygame.SRCALPHA)
    rng = random.Random(variant * 31 + 7)
    for col, dy, k in ((shade, 2, 1.0), (lit, -2, 0.65)):
        for i in range(4):
            a = math.tau * i / 4.0 + variant * 0.8
            cx = 16 + math.cos(a) * 5 * k
            cy = 16 + dy + math.sin(a) * 4 * k
            rr = (6 + rng.randrange(3)) * k
            pts = [(int(cx + math.cos(b) * rr), int(cy + math.sin(b) * rr * 0.9))
                   for b in (math.tau * j / 6.0 for j in range(6))]
            pygame.draw.polygon(small, col + (alpha,), pts)
    return pygame.transform.scale(small, (rad * 2, rad * 2))


def _blast_puff_fn(kind, rad_m, alpha, variant):
    def draw(s, sx, sy, scale, z):
        rad = max(2, min(56, int(rad_m * scale) // 4 * 4))
        if rad < 4:
            return
        s.blit(_blast_puff_img(kind, rad, alpha, variant), (int(sx) - rad, int(sy) - rad))
    draw.bounds_m = (rad_m, rad_m)
    draw.bounds_cap_px = (60, 60)
    return draw


_OS12_RELOAD_KEYS = {}
_OS12_MAG_MESH = None
_OS12_ARMS = ("lsh_p", "lsh_r", "lsh_y", "lel", "rsh_p", "rsh_r", "rsh_y", "rel",
              "rifle_p", "rifle_y")


def _os12_mag_mesh_cached():
    global _OS12_MAG_MESH
    if _OS12_MAG_MESH is None:
        _OS12_MAG_MESH = _os12_mag_mesh()
    return _OS12_MAG_MESH


def _os12_reload_keys(hum):
    """Cached OS-12 reload keyframes (mag out, pouch swap, seat, under-rack charge)."""
    ck = getattr(hum, "_gl_spec_key", None) or id(hum)
    keys = _OS12_RELOAD_KEYS.get(ck)
    if keys is None:
        ref = dict(POSES["ready"], twist=18.0, head_y=-14.0, head_p=10.0)
        aim_pt = (-3.0, 2.2, 10.0)
        base, O, Rr = _hold_frame(hum, ref, (0.0, 0.0, 0.0), 0.0, "os12", "ready", aim=aim_pt)
        _pl, joints, _root = hum.pose_world(base, (0.0, 0.0, 0.0), 0.0, rifle_on=True)
        pel = joints["pelvis"]
        poles_l = ((0.5, -1.0, 0.1),) + POLES

        def g_pt(pt):
            off = m_apply(Rr, pt)
            return (O[0] + off[0], O[1] + off[1], O[2] + off[2])

        pouch_tgt = (pel[0] - 0.23, pel[1] + 0.02, pel[2] + 0.07)
        keys = {
            "_spine": ref["spine"],
            "mag_grip": _solve_arm_safe(hum, dict(base, head_p=12.0, head_y=-12.0),
                                        (0.0, 0.0, 0.0), 0.0, "l", g_pt((0.0, -0.15, 0.15)), poles_l),
            "mag_pull": _solve_arm_safe(hum, dict(base, head_p=14.0, head_y=-14.0,
                                                  rifle_p=base.get("rifle_p", 0.0) + 2.0),
                                        (0.0, 0.0, 0.0), 0.0, "l", g_pt((0.0, -0.30, 0.16)), poles_l),
            "pouch": _solve_arm_safe(hum, dict(base, head_p=16.0, head_y=-20.0),
                                     (0.0, 0.0, 0.0), 0.0, "l", pouch_tgt, poles_l),
            "mag_app": _solve_arm_safe(hum, dict(base, head_p=12.0, head_y=-12.0),
                                       (0.0, 0.0, 0.0), 0.0, "l", g_pt((0.0, -0.25, 0.16)), poles_l),
            "mag_seat": _solve_arm_safe(hum, dict(base, head_p=10.0, head_y=-10.0,
                                                  rifle_p=base.get("rifle_p", 0.0) - 3.0),
                                        (0.0, 0.0, 0.0), 0.0, "l", g_pt((0.0, -0.14, 0.15)), poles_l),
            "charge_fwd": _solve_arm_safe(hum, dict(base, head_p=8.0, head_y=-10.0),
                                          (0.0, 0.0, 0.0), 0.0, "l", g_pt((0.032, -0.01, 0.15)), poles_l),
            "charge_back": _solve_arm_safe(hum, dict(base, head_p=8.0, head_y=-12.0,
                                                   rifle_p=base.get("rifle_p", 0.0) + 2.5),
                                           (0.0, 0.0, 0.0), 0.0, "l", g_pt((0.032, -0.01, 0.04)), poles_l),
        }
        _OS12_RELOAD_KEYS[ck] = keys
    return keys


def _os12_reload_pose(hum, base_pose, elapsed, reload_s=1.45):
    """OS-12 reload: release & drop empty mag, pouch grab, rock-in fresh mag, rack bolt.

    Returns (pose, mag_mode, mag_t).
    """
    keys = _os12_reload_keys(hum)
    ready = R._held(hum, dict(POSES["ready"]), "os12", "ready", ("m8_biri_os12", "ready"))
    u = clamp(elapsed * (1.45 / max(0.1, float(reload_s))), 0.0, 1.45)
    mag_mode, mag_t = "attached", 0.0
    if u < 0.16:
        rel = R._blend_pose(ready, keys["mag_grip"], _ease(u / 0.16))
    elif u < 0.36:
        q = _ease((u - 0.16) / 0.20)
        rel = R._blend_pose(keys["mag_grip"], keys["mag_pull"], q)
        mag_mode, mag_t = "pulling", q
    elif u < 0.56:
        rel = R._blend_pose(keys["mag_pull"], keys["pouch"], _ease((u - 0.36) / 0.20))
        mag_mode = "none"
    elif u < 0.78:
        q = _ease((u - 0.56) / 0.22)
        rel = R._blend_pose(keys["pouch"], keys["mag_app"], q)
        mag_mode, mag_t = "in_hand", 0.0
    elif u < 0.96:
        q = _ease((u - 0.78) / 0.18)
        rel = R._blend_pose(keys["mag_app"], keys["mag_seat"], q)
        mag_mode, mag_t = "in_hand", q
    elif u < 1.12:
        rel = R._blend_pose(keys["mag_seat"], keys["charge_fwd"], _ease((u - 0.96) / 0.16))
    elif u < 1.32:
        q = (u - 1.12) / 0.20
        k = _ease(q / 0.48) if q < 0.48 else 1.0 - _ease((q - 0.48) / 0.52)
        rel = R._blend_pose(keys["charge_fwd"], keys["charge_back"], k)
    else:
        rel = R._blend_pose(keys["charge_fwd"], ready, _ease((u - 1.32) / 0.13))

    out = dict(base_pose)
    for k_name in _OS12_ARMS + ("twist", "head_y", "head_p"):
        if k_name in rel:
            out[k_name] = rel[k_name]
    out["rifle_p"] = rel.get("rifle_p", 0.0) + base_pose.get("spine", 0.0) - keys["_spine"]
    return out, mag_mode, mag_t


class TrapScene:
    MAG = MAG
    RELOAD_S = RELOAD_S

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
    _ally_pose = R.RaidScene._ally_pose
    _cover_pose = R.RaidScene._cover_pose
    _project = R.RaidScene._project
    _ground_move = R.RaidScene._move

    def __init__(self):
        self._active = False
        self.paused = False
        self.done = False
        self.result = None
        self.audio = None
        self.cp_state = None
        self.t = 0.0
        self._truck = None
        self._truck_crashed = None
        self._meshes = {}
        self._last_snd = -9.0
        self._setup(0)

    # --- lifecycle -------------------------------------------------------------

    def begin(self):
        self.t = 0.0
        self.cp_state = None
        self.done = False
        self.result = None
        self._active = True
        self.paused = False
        STATE.m8_trap_active = True
        try:
            from .. import m8_audio as _m8_audio
            self.audio = _m8_audio.instance(audio)
            self.audio.warm()
        except Exception:
            self.audio = None
        self._setup(int(getattr(STATE, "m8_trap_cp", 0) or 0))
        self._grab(True)
        try:
            self._warm()
        except Exception:
            pass

    def _warm(self):
        """Arm solves and the truck pack behind the cut, not mid-fight."""
        hum = _w.hum(("biribel", OUTFIT_GUARD), flags=("shotgun", "nopump"))
        for mode in ("ready", "aim"):
            R._sg_holds(hum, mode, ("m7player_sg", mode))
        R._sg_reload_keys(hum)
        rhum = _w.hum(("biribel", OUTFIT_GUARD), flags=("os12", "nomag"))
        for mode in ("ready", "aim"):
            R._held(rhum, POSES["ready"], "os12", mode, ("m8_biri_os12", mode))
        _os12_reload_keys(rhum)
        stances = (dict(POSES["ready"]), blend(POSES["stand"], "aim", 0.85))
        for kind in set(R.GUARD_VIEW) | {"heavy"}:
            gk = ("guard", kind)
            gh = _w.hum(gk, True, flags=("os12",))
            for pose in stances:
                _hold_cached(gh, pose, "os12", "ready", key=("m8_guard", kind))
        key = ("ally", "bodi")
        bhum = _w.hum(key, flags=("os12",))
        for pose in stances + (dict(POSES["crouch"]),):
            _hold_cached(bhum, pose, "os12", "ready", key=("m8_bodi_os12", "ready"))
        for i in range(-4, 5):
            st = dict(blend(POSES["stand"], "aim", 0.85), twist=R.AIM_TWIST,
                      head_y=-0.8 * R.AIM_TWIST)
            _hold_cached(bhum, st, "os12", "aim",
                         aim=(0.0, 1.45 + 10.0 * (i / 10.0), 10.0),
                         key=("m8_bodi_os12", round(i / 10.0, 1)))
        if self._truck is None:
            self._truck = RW.truck()
        if self._truck_crashed is None:
            mt = Mesh()
            mt.add(self._truck, rot_z(-3.5), (0.0, 0.16, 0.0))
            self._truck_crashed = mt
        self._ensure_meshes()
        S3.renderer()

    def _ensure_meshes(self):
        if self._meshes:
            return
        self._meshes = {
            "barrel": _barrel_mesh(),
            "tower": _tower_mesh(),
            "fuse_on": _fusebox_mesh(True),
            "fuse_off": _fusebox_mesh(False),
            "supply_on": _supply_mesh(True),
            "supply_off": _supply_mesh(False),
            "pole_on": _pole_mesh(True),
            "pole_off": _pole_mesh(False),
            "kiosk_closed": _kiosk_mesh(False),
            "kiosk_open": _kiosk_mesh(True),
            "barrier_arm": _barrier_arm_mesh(),
            "barrier_arm_open": _barrier_arm_mesh(72.0),
            "grenade": _grenade_mesh(),
        }

    def active(self):
        return self._active

    def finish(self, result="win"):
        if self.done:
            return False
        self.done = True
        self.result = result
        self._active = False
        STATE.m8_trap_active = False
        self._grab(False)
        if self.audio is not None:
            try:
                self.audio.stop_loops()
            except Exception:
                pass
        from .. import flow as _flow
        return _flow.on_trap_done(result)

    def _setup(self, cp):
        """(Re)build the fight at checkpoint ``cp``; the clock keeps running."""
        self.cp = cp
        p = STATE.player
        self.world = W.World()
        st = self.cp_state if cp and self.cp_state else None
        if cp == 0:
            self.px, self.pz, self.yaw = -73.4, -16.6, 40.0
            self.mag, self.reserve = MAG, RESERVE0
        else:
            x, z, yaw = CP_STATE[cp]
            if self.world.blocked(x, z):
                x, z = W._clear_point(x, z, W.BODY_R + 0.15)
            self.px, self.pz, self.yaw = (st["px"], st["pz"], st["yaw"]) if st else (x, z, yaw)
            self.mag, self.reserve = (st["mag"], st["reserve"]) if st else (MAG, RESERVE0)
        self.weapon = "shotgun"
        self.wpns = {
            "shotgun": [WPN_SPECS["shotgun"]["mag"], WPN_SPECS["shotgun"]["reserve0"]],
            "rifle": [WPN_SPECS["rifle"]["mag"], WPN_SPECS["rifle"]["reserve0"]],
        }
        self._sync_weapon_attrs()
        self.heat = 0.0
        self.last_flash = -9.0
        self.flash_seed = 0
        self._flash_basis = None
        self.gate_open = cp >= 2
        self.grenades = []
        self.grenade_markers = []
        self.debris = []
        self.scorches = []
        self._scorch_mesh = None
        self._scorch_n = 0
        self.smoke_puffs = []
        self.dropped_mags = []
        self.py = 0.0
        self.pitch = -4.0
        self.body_yaw = self.yaw
        self.vel = (0.0, 0.0)
        self.stride = 0.0
        self._step_i = 0
        self._rung = -1
        self.pmoving = False
        self.sprint = False
        self.firing = False
        self.aiming = False
        self.ads = 0.0
        self.gun_up = 0.0
        self.reloading = 0.0
        self._reload_dur = self.RELOAD_S
        self._reload_n = 0
        self._reload_dry = False
        self._reload_t_in = ()
        self._reload_pump_at = 1e9
        self._shell_i = 0
        self._pump_done = False
        self._os12_mag_dropped = False
        self._os12_mag_seated = False
        self._os12_bolt_pulled = False
        self._last_mag_pos = None
        self.pump_at = -9.0
        self.pump_snd_at = 1e9
        self.last_fire = -9.0
        self.recoil = 0.0
        self.cam_kick = 0.0
        self.hurt = 0.0
        self.last_hurt = -9.0
        self.hit_mark = -9.0
        self.dmg_marks = []
        self.tracers = []
        self.sparks = []
        self.impacts = []
        self.flashes = []
        self.blasts = []
        self.lines = []
        self.toast = None
        self.cp_toast = 0.0
        self.kills = 0
        self.dying = False
        self.death_t = 0.0
        self.death_msg = ""
        self.hold = 0.0
        self._e_prev = False
        self.climb_t = None
        self._climb_start = None
        self._climb_pose_cur = None
        self.marker_screen = None
        self._muzzle = None
        self.turn = None                     # the raid's borrowed methods read it
        self.sniper_locked = False
        self.floods_on = cp < 3
        self.flood_poles = [True for _ in W.FLOOD_POLES]
        self.fuse_alive = True
        self.supply_left = cp <= 1
        self.radio_checked = cp >= 3
        self.vasile_out = cp >= 3
        self.vasile_yaw = 180.0
        self._pa_beat = cp
        self._phase_at = self.t
        self._init_props(cp)

        post = B.BODI_FOOT if cp == 3 else (B.BODI_POSTS.get(cp) if cp else (-74.8, -17.0))
        self.brain = B.Brain(self, post)
        if cp == 3:
            self.phase = "clear"
        elif cp == 2:
            self.phase = "advance2"
        elif cp == 1:
            self.phase = "advance1"
        else:
            self.phase = "approach"
        if p is not None:
            p.hp = getattr(p, "max_hp", 115) or 115
        if cp == 0:
            self.say("BODI", "Quiet. Too quiet for a man who picked the place.", 3.2)

    def _init_props(self, cp):
        self.barrels = []
        for idx, (bx, bz) in enumerate(W.BARREL_COORDS):
            alive = not (cp >= 2 and idx == 0)
            b_box = (bx - W.BARREL_R, bz - W.BARREL_R, bx + W.BARREL_R, bz + W.BARREL_R, W.BARREL_H)
            self.barrels.append(dict(id=idx, x=bx, z=bz, hp=22.0, alive=alive,
                                     box=b_box, prop_idx=len(self.world.props)))
            self.world.props.append(b_box if alive else None)
        fx, fz = W.FUSEBOX_AT
        self.fuse_box = (fx - 0.35, fz - 0.35, fx + 0.35, fz + 0.35, 1.5)
        self.fuse_prop_idx = len(self.world.props)
        self.world.props.append(self.fuse_box)
        sx, sz = W.SUPPLY_AT
        s_box = (sx - 0.5, sz - 0.35, sx + 0.5, sz + 0.35, 0.65)
        self.world.props.append(s_box)
        kx, kz = W.KIOSK_AT
        self.world.props.append((kx - 0.35, kz - 0.30, kx + 0.35, kz + 0.30, 1.3))

    def _fail(self, msg):
        if self.dying:
            return
        self.dying = True
        self.death_t = 0.0
        self.death_msg = msg
        self.firing = False
        self._snd("down")

    # --- weapons ----------------------------------------------------------------

    def _sync_weapon_attrs(self):
        sp = WPN_SPECS[self.weapon]
        self.MAG = sp["mag"]
        self.RELOAD_S = sp["reload_s"]
        self.mag, self.reserve = self.wpns[self.weapon]

    def _switch_weapon(self, target=None):
        want = target or ("rifle" if self.weapon == "shotgun" else "shotgun")
        if want == self.weapon or want not in self.wpns:
            return
        self.wpns[self.weapon] = [self.mag, self.reserve]
        self.weapon = want
        self.reloading = 0.0
        self._reload_n = 0
        self._reload_dry = False
        self._reload_t_in = ()
        self.firing = False
        self._pump_done = False
        self._os12_mag_dropped = False
        self._os12_mag_seated = False
        self._os12_bolt_pulled = False
        self.heat = 0.0
        self.last_flash = -9.0
        self.pump_at = -9.0
        self.pump_snd_at = 1e9
        self._sync_weapon_attrs()
        self._snd("pickup")
        self.toast = (self.t, WPN_SPECS[want]["label"])

    def _begin_reload(self):
        if self.reloading or self.mag >= self.MAG or self.reserve <= 0:
            return
        self._shell_i = 0
        self._pump_done = False
        self._os12_mag_dropped = False
        self._os12_mag_seated = False
        self._os12_bolt_pulled = False
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

    def throw_grenade(self, src3, dst2):
        """A Guard frag grenade lobbed at Biribel's cover; bounces and explodes."""
        dx, dz = dst2[0] - src3[0], dst2[1] - src3[2]
        d = max(1.0, math.hypot(dx, dz))
        ux, uz = dx / d, dz / d
        tx = clamp(dst2[0] + random.uniform(-0.85, 0.85) - ux * 0.65,
                   W.BOUNDS[0] + 1.0, W.BOUNDS[1] - 1.0)
        tz = clamp(dst2[1] + random.uniform(-0.85, 0.85) - uz * 0.65,
                   W.BOUNDS[2] + 1.0, W.BOUNDS[3] - 1.0)
        # Stop short of tall walls/booths so grenades never sail through concrete.
        td = math.hypot(tx - src3[0], tz - src3[2]) or 1.0
        hit = self.world.ray_hit_static((src3[0], 1.35, src3[2]),
                                        ((tx - src3[0]) / td, 0.0, (tz - src3[2]) / td), td)
        if hit < td - 0.35:
            scale = max(0.25, (hit - 0.45) / td)
            tx = src3[0] + (tx - src3[0]) * scale
            tz = src3[2] + (tz - src3[2]) * scale
        flight = clamp(math.hypot(tx - src3[0], tz - src3[2]) / 20.0, 0.65, 1.05)
        rx = clamp(tx + ux * 0.85, W.BOUNDS[0] + 0.6, W.BOUNDS[1] - 0.6)
        rz = clamp(tz + uz * 0.85, W.BOUNDS[2] + 0.6, W.BOUNDS[3] - 0.6)
        if self.world.blocked(rx, rz, 0.15):
            rx, rz = tx, tz
        self.grenades.append(dict(
            src=src3, dst=(tx, 0.06, tz), roll=(rx, 0.06, rz),
            pos=src3, t0=self.t, flight=flight, fuse=flight + 1.30,
            arc=clamp(1.6 + td * 0.09, 1.8, 3.8), landed=False,
        ))
        del self.grenades[:-4]

    throw_smoke = throw_grenade

    def in_smoke(self, x, z):
        return False

    def _spawn_debris(self, x, y, z, count=14, speed=7.0, big=False):
        cols = ((44, 42, 40), (62, 54, 46), (110, 48, 32), (28, 28, 30))
        for i in range(count):
            ang = random.uniform(0.0, math.tau)
            spd = speed * random.uniform(0.35, 1.15)
            vy = random.uniform(3.8, 8.8 if big else 6.8)
            sz = random.uniform(0.07, 0.20 if big else 0.14)
            self.debris.append(dict(
                x=x + random.uniform(-0.35, 0.35),
                y=max(0.15, y + random.uniform(0.0, 0.5)),
                z=z + random.uniform(-0.35, 0.35),
                vx=math.cos(ang) * spd, vy=vy, vz=math.sin(ang) * spd,
                rx=random.uniform(0.0, 360.0), ry=random.uniform(0.0, 360.0),
                vrx=random.uniform(-480.0, 480.0), vry=random.uniform(-480.0, 480.0),
                sx=sz * random.uniform(0.8, 1.8), sy=sz * random.uniform(0.4, 0.9), sz=sz,
                col=cols[i % len(cols)], hot=random.random() < 0.35,
                t0=self.t, bounces=0,
            ))
        del self.debris[:-54]

    def _spawn_blast_puffs(self, x, y, z, kind):
        big = (kind == "truck")
        scale = 1.45 if big else (1.1 if kind == "barrel" else 0.88)
        for i in range(6):
            if len(self.smoke_puffs) >= 56:
                break
            ang = i * (math.tau / 6.0) + random.uniform(-0.2, 0.2)
            spd = random.uniform(4.8, 7.2) * scale
            self.smoke_puffs.append([
                0.0, 0.85, x, y + 0.25, z, math.cos(ang) * spd, 0.45, math.sin(ang) * spd,
                0.45 * scale, 1.35 * scale, 128, "dust", i % 4,
            ])
        n_soot = 10 if big else 7
        for i in range(n_soot):
            if len(self.smoke_puffs) >= 56:
                break
            ang = random.uniform(0.0, math.tau)
            spd = random.uniform(0.3, 1.4) * scale
            self.smoke_puffs.append([
                -0.06 * i, random.uniform(3.0, 4.2),
                x + random.uniform(-0.5, 0.5) * scale, y + 0.5, z + random.uniform(-0.5, 0.5) * scale,
                math.cos(ang) * spd, random.uniform(1.8, 2.7), math.sin(ang) * spd,
                0.55 * scale, 2.1 * scale, 144, "soot", i % 4,
            ])

    def _detonate_grenade(self, gr):
        gx, gy, gz = gr["pos"]
        dist = math.hypot(gx - self.px, gz - self.pz)
        pan = self._pan(gx, gz)
        self._snd("barrel_boom", pan, dist)
        self.blasts.append(dict(t0=self.t, x=gx, y=gy, z=gz, kind="grenade", seed=int(self.t * 97) & 255))
        self._spawn_blast_puffs(gx, gy, gz, "grenade")
        self.scorches.append((gx, gz, 1.35))
        del self.scorches[:-16]
        self.flashes.append((self.t + 0.04, (gx, gy + 0.7, gz)))
        self._spawn_debris(gx, gy + 0.15, gz, count=14, speed=7.5, big=False)
        self.cam_kick = max(self.cam_kick, clamp(2.1 - dist * 0.09, 0.15, 1.9))
        d3 = math.sqrt((gx - self.px) ** 2 + (gy - self.py) ** 2 + (gz - self.pz) ** 2)
        if d3 < 5.2 and not self.dying:
            cov = 1.0 if self.world.los3d((gx, gy + 0.35, gz), (self.px, self.py + 1.0, self.pz)) else 0.25
            self.hurt_player(56.0 * (1.0 - d3 / 5.2) * cov, (gx, gz))
        for e in self.brain.enemies:
            if e["alive"] and e["live"]:
                ed = math.hypot(e["x"] - gx, e["z"] - gz) + abs(e["y"] - gy) * 0.5
                if ed < 4.8:
                    self.brain.hurt_enemy(e, 75.0 * (1.0 - ed / 4.8), (gx, gz))
        for bar in self.barrels:
            if bar["alive"] and math.hypot(bar["x"] - gx, bar["z"] - gz) < 4.6:
                self._detonate_barrel(bar, 1)

    def _update_grenades_and_debris(self, dt):
        keep_gr = []
        for gr in self.grenades:
            el = self.t - gr["t0"]
            if el >= gr["fuse"]:
                self._detonate_grenade(gr)
                continue
            fl = gr["flight"]
            if el < fl:
                u = el / fl
                sx, sy, sz = gr["src"]
                dx, dy, dz = gr["dst"]
                gr["pos"] = (
                    sx + (dx - sx) * u,
                    sy * (1.0 - u) + dy * u + gr["arc"] * 4.0 * u * (1.0 - u),
                    sz + (dz - sz) * u,
                )
            else:
                if not gr["landed"]:
                    gr["landed"] = True
                    self._snd("metal", self._pan(gr["dst"][0], gr["dst"][2]), 0.44)
                bu = clamp((el - fl) / 0.34, 0.0, 1.0)
                dx, dy, dz = gr["dst"]
                rx, ry, rz = gr["roll"]
                gr["pos"] = (
                    dx + (rx - dx) * bu,
                    dy + 0.24 * math.sin(math.pi * bu),
                    dz + (rz - dz) * bu,
                )
            keep_gr.append(gr)
        self.grenades = keep_gr

        keep_deb = []
        for d in self.debris:
            if self.t - d["t0"] > 3.6:
                continue
            d["vy"] -= 9.8 * dt
            d["x"] += d["vx"] * dt
            d["y"] += d["vy"] * dt
            d["z"] += d["vz"] * dt
            d["rx"] = (d["rx"] + d["vrx"] * dt) % 360.0
            d["ry"] = (d["ry"] + d["vry"] * dt) % 360.0
            if d["y"] <= 0.04 and d["vy"] < 0.0:
                d["y"] = 0.04
                if d["bounces"] == 0 and d["vy"] < -1.8:
                    d["bounces"] = 1
                    d["vy"] *= -0.35
                    d["vx"] *= 0.45
                    d["vz"] *= 0.45
                    d["vrx"] *= 0.4
                    d["vry"] *= 0.4
                else:
                    d["vx"] = d["vy"] = d["vz"] = 0.0
                    d["vrx"] = d["vry"] = 0.0
            keep_deb.append(d)
        self.debris = keep_deb

        keep_mags = []
        for dm in self.dropped_mags:
            if self.t - dm["t0"] > 12.0:
                continue
            if not dm["rest"]:
                dm["vy"] -= 9.8 * dt
                dm["x"] += dm["vx"] * dt
                dm["y"] += dm["vy"] * dt
                dm["z"] += dm["vz"] * dt
                dm["rx"] = (dm["rx"] + dm["vrx"] * dt) % 360.0
                floor_y = self._floor(dm["x"], dm["z"]) + 0.03
                if dm["y"] <= floor_y and dm["vy"] < 0.0:
                    dm["y"] = floor_y
                    if dm["bounces"] == 0 and dm["vy"] < -1.2:
                        dm["bounces"] = 1
                        dm["vy"] *= -0.25
                        dm["vx"] *= 0.4
                        dm["vz"] *= 0.4
                        self._snd("metal", self._pan(dm["x"], dm["z"]), 0.24)
                    else:
                        dm["rest"] = True
                        dm["vx"] = dm["vy"] = dm["vz"] = 0.0
            keep_mags.append(dm)
        self.dropped_mags = keep_mags

        drag = max(0.0, 1.0 - dt * 1.9)
        keep_puffs = []
        for pf in self.smoke_puffs:
            pf[0] += dt
            if pf[0] < pf[1]:
                if pf[0] >= 0.0:
                    pf[2] += pf[5] * dt
                    pf[3] += pf[6] * dt
                    pf[4] += pf[7] * dt
                    pf[5] *= drag
                    pf[7] *= drag
                keep_puffs.append(pf)
        self.smoke_puffs = keep_puffs

    # --- PA & battlefield helpers --------------------------------------------

    def _pa(self, text, dur=3.4):
        self._snd("pa_squelch")
        self.say("VASILE (PA)", text, dur)

    def in_floodlight(self, x, z):
        if not self.floods_on:
            return False
        for on, (fx, fz) in zip(self.flood_poles, W.FLOOD_POLES):
            if on and math.hypot(x - fx, z - fz) <= W.FLOOD_R:
                return True
        return False

    def _kill_power(self, idx=None):
        if idx is None:
            if not self.fuse_alive:
                return
            self.fuse_alive = False
            self.floods_on = False
            for i in range(len(self.flood_poles)):
                self.flood_poles[i] = False
            fx, fz = W.FUSEBOX_AT
            pan = self._pan(fx, fz)
            self._snd("spark_pop", pan)
            self.sparks.append((self.t, (fx, 1.2, fz)))
            self.toast = (self.t, "PLAZA FLOODLIGHTS OUT")
            if self._pa_beat < 10:
                self._pa_beat = 10
                self._pa("Cutting the lights won't shorten this road, Biribel.", 3.2)
        else:
            if not self.flood_poles[idx]:
                return
            self.flood_poles[idx] = False
            fx, fz = W.FLOOD_POLES[idx]
            self._snd("spark_pop", self._pan(fx, fz))
            self.sparks.append((self.t, (fx, W.FLOOD_H, fz)))
            if not any(self.flood_poles):
                self.floods_on = False

    def _detonate_barrel(self, bar, depth=0):
        if not bar["alive"]:
            return
        bar["alive"] = False
        self.world.props[bar["prop_idx"]] = None
        bx, bz = bar["x"], bar["z"]
        self.blasts.append(dict(t0=self.t, x=bx, y=0.05, z=bz, kind="barrel",
                                seed=bar["id"] * 37 + 19))
        self._spawn_blast_puffs(bx, 0.05, bz, "barrel")
        self.scorches.append((bx, bz, 2.0))
        del self.scorches[:-16]
        self._spawn_debris(bx, 0.5, bz, count=18, speed=8.8, big=False)
        self.flashes.append((self.t + 0.05, (bx, 0.9, bz)))
        dist = math.hypot(bx - self.px, bz - self.pz)
        self._snd("barrel_boom", self._pan(bx, bz), dist)
        self.cam_kick = max(self.cam_kick, clamp(2.4 - dist * 0.08, 0.25, 2.2))
        for e in self.brain.enemies:
            if not e["alive"] or not e["live"]:
                continue
            d = math.hypot(e["x"] - bx, e["z"] - bz) + abs(e["y"]) * 0.4
            if d < BARREL_R:
                self.brain.hurt_enemy(e, BARREL_DMG * (1.0 - 0.55 * d / BARREL_R), (bx, bz))
        for t in self.brain.trucks:
            if t["state"] in ("drive", "stopped") and not t["crashed"]:
                if math.hypot(t["x"] - bx, t["z"] - bz) < BARREL_R + 1.5:
                    self.brain.damage_truck(t, BARREL_TRUCK_DMG)
        if dist < 4.5:
            self.hurt_player(45.0 * (1.0 - dist / 4.5), (bx, bz))
        if depth < 2:
            for other in self.barrels:
                if other["alive"] and math.hypot(other["x"] - bx, other["z"] - bz) < BARREL_R * 0.85:
                    self._detonate_barrel(other, depth + 1)

    def _pan(self, x, z):
        d = max(1.0, math.hypot(x - self.px, z - self.pz))
        rg = _right(self.yaw)
        return ((x - self.px) * rg[0] + (z - self.pz) * rg[2]) / d

    # --- scene contract used by trap_brain -------------------------------------

    def flash(self, pos, sniper=False):
        self.flashes.append((self.t, pos))
        del self.flashes[:-6]
        d = math.hypot(pos[0] - self.px, pos[2] - self.pz)
        if sniper:
            self._snd("sniper_shot", 0.85 * self._pan(pos[0], pos[2]), d)
        elif d < 55.0 and self.t - self._last_snd > 0.07:
            self._last_snd = self.t
            self._snd("guard_shot", 0.8 * self._pan(pos[0], pos[2]), d)

    def on_truck_start(self, t):
        self._snd("horn", 0.50)
        self._snd("truck_arrive")

    def on_truck_stop(self, t):
        self._snd("tailgate")

    def on_truck_crash(self, t):
        t["crash_t"] = self.t
        t["cookoff_done"] = False
        bx, bz = t["x"], t["z"] - 1.8
        dist = math.hypot(bx - self.px, bz - self.pz)
        pan = self._pan(bx, bz)
        self.blasts.append(dict(t0=self.t, x=bx, y=0.25, z=bz, kind="truck", seed=401))
        self._spawn_blast_puffs(bx, 0.25, bz, "truck")
        self.scorches.append((t["x"], t["z"], 3.4))
        del self.scorches[:-16]
        self._spawn_debris(bx, 1.1, bz, count=22, speed=9.5, big=True)
        self.flashes.append((self.t + 0.04, (bx, 1.5, bz)))
        self.cam_kick = max(self.cam_kick, clamp(2.8 - dist * 0.05, 0.45, 2.5))
        self._snd("barrel_boom", pan, dist)
        self._snd("crash", pan)
        for e in self.brain.enemies:
            if e["alive"] and e["live"]:
                d = math.hypot(e["x"] - bx, e["z"] - bz)
                if d < 6.5:
                    self.brain.hurt_enemy(e, 125.0 * (1.0 - 0.5 * d / 6.5), (bx, bz))
        for bar in self.barrels:
            if bar["alive"] and math.hypot(bar["x"] - bx, bar["z"] - bz) < 6.5:
                self._detonate_barrel(bar, 1)
        self.toast = (self.t, "CONVOY TRUCK DISABLED")
        self.say("BODI", "Engine's dead! Take the stragglers!", 3.0)

    def bodi_lost(self):
        self._fail("BODI BLED OUT  -  AGAIN FROM THE CHECKPOINT")

    def hurt_player(self, dmg, src=None, forced=False):
        p = STATE.player
        if p is None or self.dying:
            return
        p.hp -= dmg
        self.hurt = min(1.0, self.hurt + dmg / 28.0)
        self.last_hurt = self.t
        self._snd("hurt", dmg)
        if src is not None:
            bearing = _wrap(_yaw(src[0] - self.px, src[1] - self.pz) - self.yaw)
            self.dmg_marks.append((self.t, -bearing))
        if p.hp <= 0:
            self._fail("BIRIBEL DOWN  -  AGAIN FROM THE CHECKPOINT")

    def _floor(self, x, z):
        for t in self.brain.trucks:
            if t["state"] != "wait" and abs(x - t["x"]) <= 1.2 and abs(z - t["z"]) <= 3.0:
                return R.BED_TOP
        return self.world.surface_y(x, z)

    # --- update ----------------------------------------------------------------

    def update(self, keys=None):
        if not self._active or self.paused:
            return
        dt = clamp(float(getattr(STATE, "dt", 1.0 / 60.0)), 0.0, 0.05)
        self.t += dt
        self._snd("bed", "gantry" if self.phase in ("clear", "climb", "catwalk") else "trap")
        self._snd("update", dt)
        if self.dying:
            self.death_t += dt
            if self.death_t >= 2.4:
                self._setup(self.cp)
            return
        k = keys if keys is not None else pygame.key.get_pressed()
        self.ads += ((1.0 if self.aiming and not self.reloading else 0.0) - self.ads) \
            * min(1.0, dt * 12.0)
        up = self.ads > 0.3 or self.firing or self.t - self.last_fire < 0.6
        up = 0.0 if (self.sprint or self.reloading or not up or self.climb_t is not None) else 1.0
        self.gun_up += (up - self.gun_up) * min(1.0, dt * 14.0)
        if not self.firing or self.reloading or self.weapon != "rifle":
            self.heat = max(0.0, self.heat - dt * 1.4)
        if self.phase == "climb":
            self._climb(dt)
        elif self.phase == "catwalk":
            self._catwalk_move(k, dt)
        else:
            self._ground_move(k, dt)
        step = int(self.stride / STEP_M)
        if step != self._step_i:
            self._step_i = step
            self._snd("step", step, self.phase == "catwalk")
        if self.reloading:
            self.reloading = max(0.0, self.reloading - dt)
            elapsed = self._reload_dur - self.reloading
            if self.weapon == "shotgun":
                while (self._shell_i < len(self._reload_t_in)
                       and elapsed >= self._reload_t_in[self._shell_i]):
                    self._shell_i += 1
                    if self.mag < self.MAG and self.reserve > 0:
                        self.mag += 1
                        self.reserve -= 1
                        self.wpns[self.weapon] = [self.mag, self.reserve]
                    self._snd("shell_in")
                if self._reload_dry and elapsed >= self._reload_pump_at and not self._pump_done:
                    self._pump_done = True
                    self._snd("pump")
            else:
                if elapsed >= 0.36 and not self._os12_mag_dropped:
                    self._os12_mag_dropped = True
                    mp = self._last_mag_pos or (self.px, self.py + 1.05, self.pz)
                    rg = _right(self.yaw)
                    self.dropped_mags.append(dict(
                        x=mp[0], y=mp[1], z=mp[2],
                        vx=-rg[0] * 1.1 + random.uniform(-0.3, 0.3),
                        vy=0.4,
                        vz=-rg[2] * 1.1 + random.uniform(-0.3, 0.3),
                        rx=15.0, ry=self.body_yaw, vrx=320.0,
                        t0=self.t, bounces=0, rest=False,
                    ))
                if elapsed >= 0.94 and not self._os12_mag_seated:
                    self._os12_mag_seated = True
                    self._snd("pickup")
                if elapsed >= 1.18 and not self._os12_bolt_pulled:
                    self._os12_bolt_pulled = True
                    self._snd("rifle_handle")
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
        if self.firing and not self.reloading and self.phase not in ("climb",):
            self._fire()
        self._loot()
        self.recoil = max(0.0, self.recoil - dt * 6.0)
        self.cam_kick *= math.exp(-dt * 11.0)
        self._hold(k, dt)
        self.brain.update(dt)
        for tr in self.brain.trucks:
            if tr["crashed"] and not tr.get("cookoff_done") and self.t - tr.get("crash_t", self.t) >= 0.58:
                tr["cookoff_done"] = True
                cx, cz = tr["x"], tr["z"] + 0.6
                dist = math.hypot(cx - self.px, cz - self.pz)
                self.blasts.append(dict(t0=self.t, x=cx, y=0.35, z=cz, kind="truck", seed=409))
                self._spawn_blast_puffs(cx, 0.35, cz, "truck")
                self._spawn_debris(cx, 1.3, cz, count=16, speed=8.5, big=True)
                self.flashes.append((self.t + 0.04, (cx, 1.6, cz)))
                self.cam_kick = max(self.cam_kick, clamp(2.0 - dist * 0.05, 0.25, 1.7))
                self._snd("barrel_boom", self._pan(cx, cz), dist)
            if tr["state"] != "wait" and (tr["crashed"] or tr["hp"] / max(1.0, tr["max_hp"]) < 0.65):
                if self.t - tr.get("smoke_t", 0.0) >= 0.24 and len(self.smoke_puffs) < 56:
                    tr["smoke_t"] = self.t
                    big = tr["crashed"]
                    sx = tr["x"] + (0.35 if big else 0.0)
                    sz = tr["z"] - (2.4 if big else 2.2)
                    self.smoke_puffs.append([
                        0.0, 2.8 if big else 1.8, sx, 1.6, sz,
                        random.uniform(-0.35, 0.35), 2.1 if big else 1.5, random.uniform(-0.35, 0.35),
                        0.55 if big else 0.38, 1.9 if big else 1.2, 128 if big else 96,
                        "soot", random.randrange(4),
                    ])
        self._waves()
        self._update_vasile_yaw(dt)
        self._update_grenades_and_debris(dt)
        # Smoke breaks the overwatch laser lock.
        self.sniper_locked = (not self.in_smoke(self.px, self.pz)) and any(
            e["alive"] and e["live"] and e["kind"] == "overwatch" and e["tele"] > 0.0
            for e in self.brain.enemies
        )
        self.hurt = max(0.0, self.hurt - dt * 1.4)
        p = STATE.player
        if p is not None and self.t - self.last_hurt > R.HP_REGEN_DELAY and p.hp < self.hp_max():
            p.hp = min(self.hp_max(), p.hp + R.HP_REGEN * 0.45 * dt)
        now = self.t
        self.tracers = [x for x in self.tracers if now - x[0] < 0.10]
        self.sparks = [x for x in self.sparks if now - x[0] < 0.45]
        self.impacts = [x for x in self.impacts if now - x[0] < 0.6]
        self.flashes = [x for x in self.flashes if now - x[0] < 0.2]
        self.blasts = [b for b in self.blasts if now - b["t0"] < (12.0 if b["kind"] == "truck" else 9.0)]
        self.dmg_marks = [m for m in self.dmg_marks if now - m[0] < 0.9]

    def _loot(self):
        """Shells and OS-12 rounds off the bodies, for whichever gun is in hand."""
        for e in self.brain.enemies:
            if e["alive"] or not e["mags"] or abs(e["y"] - self.py) >= 1.8:
                continue
            bx, bz = e.get("rest", (e["x"], e["z"]))
            if math.hypot(bx - self.px, bz - self.pz) > R.LOOT_R:
                continue
            e["mags"] = 0
            self.wpns[self.weapon] = [self.mag, self.reserve]
            sg_got = min(4, WPN_SPECS["shotgun"]["cap"] - self.wpns["shotgun"][1])
            os_got = min(15, WPN_SPECS["rifle"]["cap"] - self.wpns["rifle"][1])
            self.wpns["shotgun"][1] += max(0, sg_got)
            self.wpns["rifle"][1] += max(0, os_got)
            self._sync_weapon_attrs()
            self.toast = (self.t, "+%d SH / +%d 5.56" % (max(0, sg_got), max(0, os_got)))
            self._snd("pickup")
            if self.mag <= 0:
                self._begin_reload()

    def _update_vasile_yaw(self, dt):
        if not self.vasile_out:
            return
        want = 180.0
        if self.phase == "catwalk":
            want = _yaw(self.px - S3.VASILE_AT[0], self.pz - S3.VASILE_AT[2])
        self.vasile_yaw = _w.yaw_mix(self.vasile_yaw, want, min(1.0, dt * 4.5))

    def _catwalk_move(self, k, dt):
        def down(*codes):
            try:
                return any(k[c] for c in codes)
            except Exception:
                return False

        fwd_in = (1 if down(pygame.K_w, pygame.K_UP) else 0) - (1 if down(pygame.K_s, pygame.K_DOWN) else 0)
        side_in = (1 if down(pygame.K_d, pygame.K_RIGHT) else 0) - (1 if down(pygame.K_a, pygame.K_LEFT) else 0)
        self.sprint = False
        f, rg = _fwd(self.yaw, 0.0), _right(self.yaw)
        mx = f[0] * fwd_in + rg[0] * side_in
        mz = f[2] * fwd_in + rg[2] * side_in
        n = math.hypot(mx, mz)
        speed = R.AIM_WALK if self.ads > 0.5 else R.WALK * 0.8
        want = (mx / n * speed, mz / n * speed) if n > 1e-6 else (0.0, 0.0)
        a = min(1.0, dt * 10.0)
        self.vel = (self.vel[0] + (want[0] - self.vel[0]) * a, self.vel[1] + (want[1] - self.vel[1]) * a)
        self.px = clamp(self.px + self.vel[0] * dt, *CATWALK_X)
        self.pz = clamp(self.pz + self.vel[1] * dt, S3.CATWALK_Z - CATWALK_HALF, S3.CATWALK_Z + CATWALK_HALF)
        vx, vy, vz = S3.VASILE_AT
        if math.hypot(self.px - vx, self.pz - vz) < 0.8:     # he does not get walked through
            dx, dz = self.px - vx, self.pz - vz
            n = math.hypot(dx, dz) or 1.0
            self.px, self.pz = vx + dx / n * 0.8, vz + dz / n * 0.8
        sp = math.hypot(*self.vel)
        self.pmoving = sp > 0.6
        self.stride += sp * dt
        self.body_yaw = _w.yaw_mix(self.body_yaw, self.yaw, min(1.0, dt * 10.0))

    def _climb(self, dt):
        self.climb_t += dt
        k = clamp(self.climb_t / CLIMB_S, 0.0, 1.0)
        self.vel = (0.0, 0.0)
        self.pmoving = False
        hum = _w.hum(("biribel", OUTFIT_GUARD), flags=("shotgun",))
        align_k = 0.05
        if k < align_k:
            a = _ease(k / align_k)
            pose, pos0, _yaw0, _r = S3.ladder_climb(hum, 0.0)
            sx, sz, syaw = self._climb_start or (self.px, self.pz, self.body_yaw)
            self.px = sx + (pos0[0] - sx) * a
            self.py = pos0[1]
            self.pz = sz + (pos0[2] - sz) * a
            self.body_yaw = _w.yaw_mix(syaw, 0.0, a)
            self._climb_pose_cur = pose
        else:
            u = (k - align_k) / (1.0 - align_k)
            pose, pos, yaw, rung = S3.ladder_climb(hum, u)
            self.px, self.py, self.pz = pos
            self.body_yaw = yaw
            self._climb_pose_cur = pose
            if rung != self._rung and u <= S3.LADDER_CLIMB_UP:
                self._rung = rung
                self._snd("rung")
        if k >= 1.0:
            self.phase = "catwalk"
            self.climb_t = None
            self._climb_start = None
            self._climb_pose_cur = None
            self.yaw = self.body_yaw = 270.0       # along the catwalk, toward him
            self.say("VASILE", "Took your time.", 2.6)

    def _hold(self, k, dt):
        try:
            held = bool(k[pygame.K_e])
        except Exception:
            held = False
        just_pressed = held and not self._e_prev
        self._e_prev = held
        action = self._hold_action()
        if action in ("supply", "radio", "kiosk"):
            self.hold = 0.0
            if just_pressed:
                if action == "supply":
                    self._take_supply()
                elif action == "radio":
                    self._check_radio()
                else:
                    self._open_gate()
            return
        if action is None or not held:
            self.hold = 0.0
            return
        self.hold += dt
        if action == "bodi" and self.hold >= R.HOLD_S["bodi"]:
            self.hold = 0.0
            self.brain.help_done("bodi")
        elif action == "climb" and self.hold >= CLIMB_HOLD_S:
            self.hold = 0.0
            self.phase = "climb"
            self.climb_t = 0.0
            self._climb_start = (self.px, self.pz, self.body_yaw)
            self._climb_pose_cur = None
            self._rung = -1
            self.aiming = self.firing = False
            if self.weapon != "shotgun":
                self._switch_weapon("shotgun")

    def _take_supply(self):
        if not self.supply_left:
            return
        self.supply_left = False
        p = STATE.player
        if p is not None:
            p.hp = min(self.hp_max(), p.hp + 50.0)
        got = min(12, WPN_SPECS["shotgun"]["cap"] - self.wpns["shotgun"][1])
        self.wpns["shotgun"][1] += got
        self._sync_weapon_attrs()
        self._snd("pickup")
        self.toast = (self.t, "BANDAGE + %d SHELLS" % got if got else "PATCHED UP")
        self.say("BODI", "Good - stay ahead of the booths.", 2.4)

    def _check_radio(self):
        if self.radio_checked:
            return
        self.radio_checked = True
        self._snd("pa_squelch")
        self.say("BIRIBEL", "Darius's set. Still tuned to channel four.", 3.0)
        self.say("BODI", "Leave it. Keep your eyes on the tanker.", 2.8)

    def _open_gate(self):
        """The toll kiosk: the barrier lifts, the north lane opens, wave 2 rolls in."""
        fresh = not self.gate_open
        self.gate_open = True
        if fresh:
            self._snd("metal")
            self._snd("horn", 0.35)
            self.toast = (self.t, "NORTH LANE OPEN")
        for e in self.brain.enemies:
            if e["wave"] == 1:
                e["wave"] = 2
        self.cp = 1
        self.cp_state = dict(px=self.px, pz=self.pz, yaw=self.yaw, mag=self.mag,
                             reserve=max(self.reserve, RESERVE0))
        STATE.m8_trap_cp = 1
        self.cp_toast = self.t
        p = STATE.player
        if p is not None:
            p.hp = min(self.hp_max(), max(p.hp, self.hp_max() * 0.65))
        self.say("BODI", "Lane's open. Move up, booth by booth.", 3.0)
        self._begin_wave(2)

    def _hold_action(self):
        if self.brain.near_revive() is not None:
            return "bodi"
        if self.phase == "clear" and math.hypot(self.px - LADDER_FOOT[0], self.pz - LADDER_FOOT[1]) < 1.3:
            return "climb"
        if (self.phase in ("w1", "advance1")
                and (self.phase == "advance1" or self.brain.alive_in_wave(1) <= 2)
                and self.py < 1.0
                and math.hypot(self.px - W.KIOSK_AT[0], self.pz - W.KIOSK_AT[1]) < 2.3):
            return "kiosk"
        if self.supply_left and self.py < 1.0 and math.hypot(self.px - W.SUPPLY_AT[0],
                                                             self.pz - W.SUPPLY_AT[1]) < 2.2:
            return "supply"
        if not self.radio_checked and self.py < 1.0 and math.hypot(self.px - W.RADIO_AT[0],
                                                                   self.pz - W.RADIO_AT[1]) < 2.2:
            return "radio"
        return None

    # --- camera and fire ---------------------------------------------------------

    def camera(self):
        back, right, up = (R.BOOM[i] + (R.BOOM_ADS[i] - R.BOOM[i]) * self.ads for i in range(3))
        pivot = (self.px, self.py + R.EYE_H + up, self.pz)
        f = _fwd(self.yaw, self.pitch)
        rg = _right(self.yaw)
        right = min(right, max(0.0, self.world.ray_hit(pivot, (rg[0], 0.0, rg[2]), right + 0.3) - 0.3))
        shoulder = (pivot[0] + rg[0] * right, pivot[1], pivot[2] + rg[2] * right)
        d = (-f[0], -f[1], -f[2])
        dist = max(0.45, min(back, self.world.ray_hit(shoulder, d, back + 0.35) - 0.35))
        eye = (shoulder[0] + d[0] * dist, max(self.py + 0.35, shoulder[1] + d[1] * dist),
               shoulder[2] + d[2] * dist)
        fv = _fwd(self.yaw, self.pitch + 1.6 * self.cam_kick)
        tgt = (eye[0] + fv[0] * 10.0, eye[1] + fv[1] * 10.0, eye[2] + fv[2] * 10.0)
        if self.phase == "climb":
            # a rear quarter off the open east side, the ladder in profile
            eye = (self.px + 2.6, self.py + 1.5, self.pz - 2.3)
            tgt = (self.px - 0.2, self.py + 1.1, self.pz + 0.3)
        elif self.phase == "catwalk":
            # No fight up here, and the boom would hit the pillar behind him:
            # a rear quarter off the catwalk's south side, along it toward Vasile.
            eye = (self.px + 2.6, self.py + 2.0, self.pz - 2.4)
            tgt = (self.px - 3.0, self.py + 1.2, self.pz)
        if self.dying:
            kk = clamp(self.death_t / 1.2, 0.0, 1.0)
            eye = (eye[0], eye[1] + 1.4 * kk, eye[2])
            tgt = (self.px, self.py + 0.3, self.pz)
        fov_ads = WPN_SPECS[self.weapon]["fov_ads"]
        fov = R.FOV + (fov_ads - R.FOV) * self.ads - 1.4 * self.cam_kick
        return eye, tgt, fov, dist

    def _fire(self):
        sp = WPN_SPECS[self.weapon]
        if self.t - self.last_fire < sp["gap"]:
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
        o, d = self._aim_ray()
        look_pitch = self.pitch + 1.6 * self.cam_kick

        if self.weapon == "shotgun":
            self.pump_at = self.t
            self.pump_snd_at = self.t + R.PUMP_S
            self.recoil = min(3.0, self.recoil + 1.4)
            self.cam_kick = min(2.6, self.cam_kick + 2.0)
            self.pitch = clamp(self.pitch + 0.55, *R.PITCH_LIM)
            self._snd("shot", True)
            cone = 0.65 if self.ads > 0.5 else 1.0
            rays = [_fwd(self.yaw + dy * cone, look_pitch + dp * cone) for dy, dp in R.PELLET_FAN]
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
            rays = [_fwd(self.yaw + math.cos(ang) * rad, look_pitch + math.sin(ang) * rad)]
            body_dmg, head_dmg = 24.0, 52.0

        src = self._muzzle or o
        hits, impact_pts, lanes = {}, [], []
        barrel_hits, truck_hits = {}, {}
        fuse_hit, lamp_hit = False, None
        farthest, any_enemy, any_head, any_metal = 0.0, False, False, False

        active_trucks = [(t, W.guard_truck_at(t["x"], t["z"]).world_box())
                         for t in self.brain.trucks if t["state"] in ("drive", "stopped")]

        for dd in rays:
            # Static terrain only, so the truck's own hull cannot eat a round
            # aimed at the gunner riding in its bed.
            best = self.world.ray_hit_static(o, dd, 90.0)
            hit_kind, hit_obj, head = "world", None, False

            for e in self.brain.enemies:
                if not e["alive"] or not e["live"] or e["truck"] is None:
                    continue
                for c, rad, is_head in self.brain.spheres(e):
                    h = B._ray_sphere(o, dd, c, rad)
                    if h is not None and h < best:
                        best, hit_kind, hit_obj, head = h, "enemy", e, is_head

            for t, wb in active_trucks:
                tb = (wb[0], wb[2], wb[3], wb[5], wb[4])
                h = RW._ray_box(o, dd, tb)
                if h is not None and h < best:
                    best, hit_kind, hit_obj, head = h, "truck", t, False

            for e in self.brain.enemies:
                if not e["alive"] or not e["live"] or e["truck"] is not None:
                    continue
                for c, rad, is_head in self.brain.spheres(e):
                    h = B._ray_sphere(o, dd, c, rad)
                    if h is not None and h < best:
                        best, hit_kind, hit_obj, head = h, "enemy", e, is_head

            for bar in self.barrels:
                if not bar["alive"]:
                    continue
                h = RW._ray_box(o, dd, bar["box"])
                if h is not None and h < best:
                    best, hit_kind, hit_obj, head = h, "barrel", bar, False

            if self.fuse_alive:
                h = RW._ray_box(o, dd, self.fuse_box)
                if h is not None and h < best:
                    best, hit_kind, hit_obj, head = h, "fuse", None, False

            for idx, (on, (lx, lz)) in enumerate(zip(self.flood_poles, W.FLOOD_POLES)):
                if not on:
                    continue
                h = B._ray_sphere(o, dd, (lx, W.FLOOD_H, lz), 0.55)
                if h is not None and h < best:
                    best, hit_kind, hit_obj, head = h, "lamp", idx, False

            end = (o[0] + dd[0] * best, o[1] + dd[1] * best, o[2] + dd[2] * best)
            lanes.append(end)
            farthest = max(farthest, best)

            if hit_kind == "enemy":
                any_enemy = True
                any_head = any_head or head
                rec = hits.setdefault(id(hit_obj), [hit_obj, 0.0])
                rec[1] += head_dmg if head else body_dmg
                impact_pts.append((end, "blood"))
            elif hit_kind == "barrel":
                any_metal = True
                rec = barrel_hits.setdefault(hit_obj["id"], [hit_obj, 0.0])
                rec[1] += 14.0 if self.weapon == "shotgun" else 12.0
                impact_pts.append((end, "spark"))
            elif hit_kind == "fuse":
                any_metal = fuse_hit = True
                impact_pts.append((end, "spark"))
            elif hit_kind == "lamp":
                any_metal = True
                lamp_hit = hit_obj
                impact_pts.append((end, "spark"))
            elif hit_kind == "truck":
                any_metal = True
                rec = truck_hits.setdefault(id(hit_obj), [hit_obj, 0.0])
                engine_zone = (end[2] < hit_obj["z"] - 0.2 and end[1] < 2.2)
                dmg = (9.0 if self.weapon == "shotgun" else 15.0) if engine_zone \
                    else (5.0 if self.weapon == "shotgun" else 9.5)
                rec[1] += dmg
                impact_pts.append((end, "spark"))
            else:
                impact_pts.append((end, "dust"))

        for end in lanes:
            self.tracers.append((self.t, src, end, (255, 226, 160)))
        for end, kind in impact_pts:
            self.impacts.append((self.t, end, kind))
        ld = _fwd(self.yaw, look_pitch)
        self.sparks.append((self.t, (o[0] + ld[0] * farthest, o[1] + ld[1] * farthest,
                                     o[2] + ld[2] * farthest)))
        for e, dmg in hits.values():
            self.brain.hurt_enemy(e, dmg, (o[0], o[2]))
        for bar, dmg in barrel_hits.values():
            bar["hp"] -= dmg
            if bar["hp"] <= 0.0:
                self._detonate_barrel(bar)
        if fuse_hit:
            self._kill_power(None)
        elif lamp_hit is not None:
            self._kill_power(lamp_hit)
        for tr, dmg in truck_hits.values():
            if not tr["crashed"]:
                self.brain.damage_truck(tr, dmg)
                self._snd("hull_hit")

        if any_enemy:
            self.hit_mark = self.t
            if any_head:
                self._snd("headshot", farthest)
            else:
                self._snd("impact", True, farthest)
        elif any_metal:
            self.hit_mark = self.t
            self._snd("metal")
        else:
            self._snd("impact", False, farthest)

    # --- waves & spatial advance -----------------------------------------------

    def _begin_wave(self, n):
        self.phase = "w%d" % n
        self._phase_at = self.t
        if n == 1:
            self.floods_on = True
            self._pa("Leave the road, Biribel. Bodi - take the tractor back to Valea Seaca.", 3.6)
            self.say("BODI", "Wrecks and catwalk! Watch the red sniper dot!", 3.2)
        elif n == 2:
            self._pa("Keep him off the booths. Don't let him past the tanker.", 3.4)
            self.say("BODI", "Truck in the north lane! Hit the engine or that red drum!", 3.4)
        else:
            self.vasile_out = True
            self._pa("No more half-measures. Hold the gantry stairs.", 3.2)
            self.say("BODI", "Gantry base and catwalk - push right up to the pillars!", 3.2)
        self.brain.start_wave(n)

    def _waves(self):
        b = self.brain
        if self.phase == "approach":
            if self.pz >= APPROACH_ADV_Z or self.px >= -67.0 or (self.t - self._phase_at) >= 3.5:
                self._begin_wave(1)
        elif self.phase == "w1" and not b.pending(1):
            self._clear(1)
        elif self.phase == "advance1":
            elapsed = self.t - self._phase_at
            if (elapsed >= 2.2 and (self.pz >= 8.0 or self.px >= -51.0)) or elapsed >= FORCE_ADV_S:
                self._begin_wave(2)
        elif self.phase == "w2" and not b.pending(2):
            self._clear(2)
        elif self.phase == "advance2":
            elapsed = self.t - self._phase_at
            if (elapsed >= 2.2 and (self.pz >= 30.0 or self.px >= -25.0)) or elapsed >= FORCE_ADV_S:
                self._begin_wave(3)
        elif self.phase == "w3" and not b.pending(3):
            self._road_clear()
        elif self.phase == "catwalk":
            vx, _vy, vz = S3.VASILE_AT
            if math.hypot(self.px - vx, self.pz - vz) < VASILE_REACH:
                self.finish("win")

    def _clear(self, n):
        self.phase = "advance%d" % n
        self._phase_at = self.t
        self.cp = n
        if n == 1:
            self.gate_open = True      # the plaza is clear: the north lane opens
        self.cp_state = dict(px=self.px, pz=self.pz, yaw=self.yaw, mag=self.mag,
                             reserve=max(self.reserve, RESERVE0))
        STATE.m8_trap_cp = n
        self.cp_toast = self.t
        p = STATE.player
        if p is not None:
            p.hp = min(self.hp_max(), max(p.hp, self.hp_max() * 0.65))
        b = self.brain.bodi
        if b["state"] == "up":
            b["goal"] = B.BODI_POSTS.get(n + 1)
        if n == 1:
            self.say("BODI", "Apron's clear. Supply box by the middle booths - move up.", 3.4)
            self._pa("You brought him up the same ditch. You remember where the tanker went?", 3.4)
        else:
            self.say("BIRIBEL", "He knew we'd come up the road.", 2.6)
            self.say("BODI", "He taught you the road. Push past the tanker.", 2.8)

    def _road_clear(self):
        self.phase = "clear"
        self._phase_at = self.t
        self.cp = 3
        self.cp_state = None
        STATE.m8_trap_cp = 3
        self.cp_toast = self.t
        self.vasile_out = True
        p = STATE.player
        if p is not None:
            p.hp = self.hp_max()
        b = self.brain.bodi
        if b["state"] == "up":
            b["goal"] = B.BODI_FOOT
        self._pa("Leave the ladder. Let him come up.", 2.8)
        self.say("BODI", "Road's clear. He's up there.", 2.6)
        self.say("BODI", "This part's yours.", 3.0)
        from .. import flow as _flow
        _flow.on_gantry_reached()

    # --- guidance ------------------------------------------------------------------

    def pending_count(self):
        return self.brain.pending_count()

    def active_truck(self):
        for t in self.brain.trucks:
            if t["state"] in ("drive", "stopped") and not t["crashed"]:
                return t
        return None

    def objective_point(self):
        b = self.brain.bodi
        if b["state"] == "down":
            return b["x"], b["z"]
        if self.phase == "advance1":
            return W.SUPPLY_AT if self.supply_left else ADVANCE_1_PT
        if self.phase == "advance2":
            return ADVANCE_2_PT
        if self.phase == "clear":
            return LADDER_FOOT
        if self.phase == "catwalk":
            return S3.VASILE_AT[0], S3.VASILE_AT[2]
        return None, None

    def objective_text(self):
        tx, tz = self.objective_point()
        if self.brain.bodi["state"] == "down":
            return "Get to Bodi - he is down", math.hypot(tx - self.px, tz - self.pz)
        if self.phase == "clear":
            return "Climb the gantry ladder", math.hypot(tx - self.px, tz - self.pz)
        if self.phase == "catwalk":
            return "Walk to Vasile", math.hypot(tx - self.px, tz - self.pz)
        if self.phase == "climb":
            return "Climb", None
        if self.phase == "advance1":
            return "Push north to the toll booths", math.hypot(tx - self.px, tz - self.pz)
        if self.phase == "advance2":
            return "Advance past the burnt tanker", math.hypot(tx - self.px, tz - self.pz)
        if self.phase == "w3":
            return "Break the Guard holdout at the gantry foot", None
        if self.phase == "w2":
            if self.active_truck() is not None:
                return "Stop the Guard truck in the north lane", None
            return "Clear the toll plaza squad", None
        if self.phase == "w1":
            return "Break the ambush in the wrecks", None
        return "Step up onto Route 12", None

    def prompt(self):
        action = self._hold_action()
        if action is not None:
            if action == "bodi":
                need = R.HOLD_S["bodi"]
                return "Pull Bodi up", "E", (self.hold / need) if self.hold > 0.0 else None
            if action == "climb":
                return "Climb", "E", (self.hold / CLIMB_HOLD_S) if self.hold > 0.0 else None
            if action == "kiosk":
                return "Bypass toll gate", "E", None
            if action == "supply":
                return "Take medical kit & shells", "E", None
            if action == "radio":
                return "Check Darius's radio", "E", None
        if self.toast and self.t - self.toast[0] < 1.6:
            return self.toast[1], None, None
        if self.mag <= 0 and self.reserve <= 0:
            return "Dry - take shells off the bodies", None, None
        return None

    # --- draw ----------------------------------------------------------------------

    def _lights(self):
        now = self.t
        out = [{"pos": pos, "color": (255, 196, 120), "intensity": 1.35, "range": 5.5}
               for t0, pos in self.flashes[-2:] if now - t0 < 0.07]
        flash_dur = FLASH_S if self.weapon == "shotgun" else FLASH_S_SUPP
        if 0.0 <= now - self.last_flash < max(0.04, flash_dur) and len(out) < 6:
            lpos = self._muzzle or (self.px, self.py + 1.4, self.pz)
            suppressed = (self.weapon != "shotgun")
            out.append({
                "pos": lpos,
                "color": (255, 198, 124) if suppressed else (255, 204, 132),
                "intensity": 0.55 if suppressed else 1.45,
                "range": 3.2 if suppressed else 5.5,
            })
        for t in self.brain.trucks:
            if t["state"] == "drive" and not t["crashed"] and len(out) < 5:
                out.append({"pos": (t["x"], 1.3, t["z"] - 4.0), "color": (255, 232, 186),
                            "intensity": 1.45, "range": 14.0})
        if self.floods_on:
            for on, (fx, fz) in zip(self.flood_poles, W.FLOOD_POLES):
                if on and len(out) < 6:
                    out.append({"pos": (fx, W.FLOOD_H - 0.3, fz), "color": (255, 204, 134),
                                "intensity": 1.15, "range": 15.0})
        for b in self.blasts[-3:]:
            age = now - b["t0"]
            if 0.0 <= age < 5.5:
                flash = math.exp(-age * 11.0)
                fire_k = max(0.0, 1.0 - age / 5.5) ** 1.3
                big = b["kind"] == "truck"
                out.append({
                    "pos": (b["x"], b["y"] + 1.2, b["z"]),
                    "color": (255, 224, 166) if age < 0.14 else (255, 138, 46),
                    "intensity": (4.2 if big else 3.2) * flash + (1.9 if big else 1.2) * fire_k,
                    "range": (16.0 if big else 11.0) + 6.0 * flash,
                })
        for tr in self.brain.trucks:
            if tr["crashed"]:
                age = now - tr.get("crash_t", now)
                if age < 35.0:
                    fl = 0.85 + 0.15 * math.sin(self.t * 11.3)
                    out.append({"pos": (tr["x"], 1.5, tr["z"] - 1.6), "color": (255, 132, 44),
                                "intensity": 1.5 * fl * max(0.25, 1.0 - age / 35.0), "range": 13.0})
        return out[:6]

    def draw(self, surface):
        if not self._active:
            return
        self._ensure_meshes()
        tm = self.t * 1000.0
        eye, tgt, fov, _dist = self.camera()
        r = S3.frame(eye, tgt, fov, self._lights())
        del _w.LAST[:]
        if self._truck is None:
            self._truck = RW.truck()
        if self._truck_crashed is None:
            mt = Mesh()
            mt.add(self._truck, rot_z(-3.5), (0.0, 0.16, 0.0))
            self._truck_crashed = mt
        self._draw_props(r, tm)
        cam = getattr(r, "cam", None)
        for t in self.brain.trucks:
            if t["state"] != "wait":
                if t["crashed"]:
                    ct = clamp((self.t - t.get("crash_t", self.t)) / 0.48, 0.0, 1.0)
                    sw = _ease(ct)
                    yaw = 180.0 - 16.0 * sw
                    mesh_tr = self._truck_crashed if ct > 0.18 else self._truck
                    RW.put(r, mesh_tr, t["x"] + 0.35 * sw, 0.0, t["z"] - 0.5 * sw, yaw)
                    ex, ez = t["x"] + 0.35 * sw, t["z"] - 2.1 - 0.5 * sw
                    if self.t - t.get("crash_t", self.t) < 28.0:
                        _w.add(r, F.flame_mesh((ex, 0.55, ez), tm, seed=81, size=1.15, heat=1.2, cam=cam))
                        r.add_sprite((ex, 0.06, ez), F.pool((255, 118, 34), 3.2, intensity=0.45, squash=0.5),
                                     layer=_fx.FX_LAYER)
                else:
                    RW.put(r, self._truck, t["x"], 0.0, t["z"], 180.0)
                    frac = t["hp"] / max(1.0, t["max_hp"])
                    if frac < 0.32:
                        _w.add(r, F.flame_mesh((t["x"], 1.15, t["z"] - 2.3), tm, seed=89, size=0.55, cam=cam))
                if not t["crashed"]:
                    for sx in (-0.68, 0.68):
                        r.add_sprite((t["x"] + sx, 1.46, t["z"] - 2.95),
                                     _fx.glow((255, 236, 200), 0.52, tm, core=(255, 250, 236),
                                              intensity=1.1, max_px=30), layer=_fx.FX_LAYER)
        self._draw_player(r, tm)
        self._draw_bodi(r, tm)
        self._draw_vasile(r, tm)
        self._draw_enemies(r, tm)
        self._draw_blasts(r, tm)
        self._draw_fx(r, tm)
        # the bore-aligned 3D muzzle flash at the gun's own bore
        f_dur = FLASH_S if self.weapon == "shotgun" else FLASH_S_SUPP
        f_age = self.t - self.last_flash
        if 0.0 <= f_age < f_dur and self._flash_basis is not None:
            tip, fvec, rx, ry = self._flash_basis
            handheld_flash(r, tm, tip, fvec, rx, ry, f_age, self.flash_seed, self.weapon)
        self.grenade_markers = [
            (self._project(r, gr["pos"]),
             math.hypot(gr["pos"][0] - self.px, gr["pos"][2] - self.pz),
             clamp(1.0 - (self.t - gr["t0"]) / gr["fuse"], 0.0, 1.0))
            for gr in self.grenades
        ]
        tx, tz = self.objective_point()
        ty = S3.CATWALK_Y + 1.6 if self.phase == "catwalk" else 1.6
        self.marker_screen = self._project(r, (tx, ty, tz)) if tx is not None else None
        S3.present(r, surface)
        draw_vignette(surface)
        HUD.draw(surface, self)

    def _draw_fx(self, r, tm):
        """Player/enemy tracers as layer-2 3D cross-quad ribbons.

        The raid's inherited version queues unoccluded layer-3 lines, which
        painted straight over Biribel's back and shoulder in the
        over-the-shoulder cameras."""
        now = self.t
        m = Mesh()
        for t0, a, b, col in self.tracers:
            k = (now - t0) / 0.06
            head, tail = min(1.0, k), max(0.0, k - 0.35)
            if tail >= 1.0:
                continue
            pa = tuple(a[i] + (b[i] - a[i]) * tail for i in range(3))
            pb = tuple(a[i] + (b[i] - a[i]) * head for i in range(3))
            dv = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
            ln = math.sqrt(dv[0] * dv[0] + dv[1] * dv[1] + dv[2] * dv[2])
            if ln < 1e-4:
                continue
            u = (dv[0] / ln, dv[1] / ln, dv[2] / ln)
            ref = (0.0, 1.0, 0.0) if abs(u[1]) < 0.9 else (1.0, 0.0, 0.0)
            s = C._f_unit(C._f_cross(u, ref))
            up = C._f_unit(C._f_cross(s, u))
            w = 0.011
            for ax in (s, up):
                p0 = (pa[0] - ax[0] * w, pa[1] - ax[1] * w, pa[2] - ax[2] * w)
                p1 = (pa[0] + ax[0] * w, pa[1] + ax[1] * w, pa[2] + ax[2] * w)
                p2 = (pb[0] + ax[0] * w, pb[1] + ax[1] * w, pb[2] + ax[2] * w)
                p3 = (pb[0] - ax[0] * w, pb[1] - ax[1] * w, pb[2] - ax[2] * w)
                m.face([p0, p1, p2, p3], col, 2, True, True)
        if m.faces:
            _w.add(r, m)
        for t0, p in self.sparks:
            r.add_sprite(p, _fx.sparks(7, (now - t0) * 1000.0, n=10, speed_m=2.0, dur_ms=420),
                         layer=_fx.FX_LAYER)
        for t0, p, kind in self.impacts:
            if now - t0 < 0.22:
                col = (176, 26, 22) if kind == "blood" else (238, 226, 176)
                for ax, ay, az in R.FLECK_ARMS:
                    r.add_line3d(p, (p[0] + ax, p[1] + ay, p[2] + az), col, 1, layer=2)
        for t0, pos in self.flashes:
            if now - t0 < 0.06:
                for ax, ay, az in R.FLASH_ARMS:
                    r.add_line3d(pos, (pos[0] + ax, pos[1] + ay, pos[2] + az), (255, 238, 190), 2,
                                 layer=2)

    def _draw_props(self, r, tm):
        RW.put(r, self._meshes["tower"], W.TOWER_AT[0], 0.0, W.TOWER_AT[1], 0.0)
        for bar in self.barrels:
            if bar["alive"]:
                RW.put(r, self._meshes["barrel"], bar["x"], 0.0, bar["z"], 0.0)
                r.add_sprite((bar["x"], 1.08, bar["z"]),
                             _fx.glow((255, 130, 56), 0.22, tm, intensity=0.45, max_px=14),
                             layer=_fx.FX_LAYER)
        fuse_key = "fuse_on" if self.fuse_alive else "fuse_off"
        RW.put(r, self._meshes[fuse_key], W.FUSEBOX_AT[0], 0.0, W.FUSEBOX_AT[1], 0.0)
        if self.fuse_alive:
            r.add_sprite((W.FUSEBOX_AT[0], 1.24, W.FUSEBOX_AT[1] - 0.22),
                         _fx.glow((255, 198, 64), 0.28, tm, intensity=0.7, max_px=16),
                         layer=_fx.FX_LAYER)
        sup_key = "supply_on" if self.supply_left else "supply_off"
        RW.put(r, self._meshes[sup_key], W.SUPPLY_AT[0], 0.0, W.SUPPLY_AT[1], 18.0)
        if self.supply_left:
            r.add_sprite((W.SUPPLY_AT[0], 0.9, W.SUPPLY_AT[1]),
                         _fx.glow((118, 224, 132), 0.26, tm, intensity=0.55, max_px=16),
                         layer=_fx.FX_LAYER)
        for on, (fx, fz) in zip(self.flood_poles, W.FLOOD_POLES):
            RW.put(r, self._meshes["pole_on" if on else "pole_off"], fx, 0.0, fz, 0.0)
            if on:
                r.add_sprite((fx, W.FLOOD_H, fz - 0.16),
                             _fx.glow((255, 224, 160), 0.72, tm, core=(255, 248, 226),
                                      intensity=1.0, max_px=34), layer=_fx.FX_LAYER)
        # the toll kiosk and its barrier arm (the arm lifts once the lane opens)
        RW.put(r, self._meshes["kiosk_open" if self.gate_open else "kiosk_closed"],
               W.KIOSK_AT[0], 0.0, W.KIOSK_AT[1], 0.0)
        RW.put(r, self._meshes["barrier_arm_open" if self.gate_open else "barrier_arm"],
               -32.2, 0.0, 15.8, 0.0)          # toll-lane barrier post
        if self.scorches:
            key = tuple(self.scorches)
            if self._scorch_n != key or self._scorch_mesh is None:
                sm = Mesh()
                for sx, sz, srad in self.scorches:
                    sm.add(disc_xz(sx, sz, srad, 0.024, (22, 20, 20), n=10, layer=1))
                self._scorch_mesh = sm
                self._scorch_n = key
            _w.add(r, self._scorch_mesh)
        for gr in self.grenades:
            el = self.t - gr["t0"]
            gx, gy, gz = gr["pos"]
            m_gr = Mesh()
            rot = rot_x(el * 540.0) if not gr["landed"] else rot_x(clamp(1.0 - (el - gr["flight"]) / 0.34, 0.0, 1.0) * 180.0 + 86.0)
            m_gr.add(self._meshes["grenade"], rot, (gx, gy, gz))
            _w.add(r, m_gr)
            # Fuze fizz spark on the cap + urgent subtle pulse near detonation
            r.add_sprite((gx, gy + 0.07, gz),
                         _fx.sparks(int(gr["t0"] * 100) + int(el * 12), (el % 0.18) * 1000.0,
                                    col=(255, 205, 110), n=4, speed_m=1.4, dur_ms=170),
                         layer=2)
            rem = max(0.0, gr["fuse"] - el)
            pulse = 1.0 if (rem < 0.65 and int(el * 14.0) % 2 == 0) else 0.45
            g_sp = _fx.glow((255, 92, 48), 0.12 if rem < 0.65 else 0.08, tm,
                            core=(255, 232, 164), intensity=pulse, max_px=12)
            g_sp.light = False
            g_sp.strict_occ = True
            r.add_sprite((gx, gy + 0.08, gz), g_sp, layer=2)
        if self.debris:
            m_deb = Mesh()
            for d in self.debris:
                hot = d["hot"] and self.t - d["t0"] < 0.95
                col = (242, 132, 46) if hot else d["col"]
                m_deb.add(box(d["sx"], d["sy"], d["sz"], col, emissive=hot),
                          rot_y(d["ry"]), (d["x"], d["y"], d["z"]))
            _w.add(r, m_deb)
        for pf in self.smoke_puffs:
            if pf[0] < 0.0:
                continue
            k = pf[0] / pf[1]
            alpha = int(pf[10] * min(1.0, k * 6.0) * (1.0 - k) ** 1.3) // 16 * 16
            if alpha >= 16:
                rad_m = pf[8] + (pf[9] - pf[8]) * math.sqrt(k)
                r.add_sprite((pf[2], pf[3], pf[4]), _blast_puff_fn(pf[11], rad_m, alpha, pf[12]), layer=2)
        for dm in self.dropped_mags:
            mm = Mesh()
            mm.add(_os12_mag_mesh_cached(), rot_x(dm["rx"]), (dm["x"], dm["y"], dm["z"]))
            _w.add(r, mm)

    def _draw_blasts(self, r, tm):
        now = self.t
        cam = getattr(r, "cam", None)
        for b in self.blasts:
            t0, bx, by, bz, kind, seed = b["t0"], b["x"], b["y"], b["z"], b["kind"], b["seed"]
            age = now - t0
            big = (kind == "truck")
            med = (kind == "barrel")
            scale = 1.65 if big else (1.15 if med else 0.92)

            # 1. White-hot core ignition flash
            if age < 0.32:
                f = (1.0 - age / 0.32) ** 1.8
                r.add_sprite((bx, by + 0.55 * scale, bz),
                             _fx.flash(age * 1000.0, col=(255, 224, 158),
                                       radius_m=(3.6 if big else 2.2) * scale, dur_ms=320),
                             layer=_fx.FX_LAYER)
                r.add_sprite((bx, by + 0.65, bz),
                             _fx.glow((255, 168, 62), (2.2 + age * 8.0) * scale, tm,
                                      core=(255, 250, 226), intensity=2.4 * f, max_px=180),
                             layer=_fx.FX_LAYER)

            # 2. Multi-lobe expanding 3D cel fireball (F.flame_mesh)
            fb_dur = 1.65 if big else (1.25 if med else 0.95)
            if age < fb_dur:
                n_lobes = 5 if big else 4
                for i in range(n_lobes):
                    a = age - 0.025 * i
                    if not (0.0 <= a < fb_dur - 0.15):
                        continue
                    ang = i * 2.399963 + seed * 0.1
                    exp_k = 1.0 - math.exp(-a * 6.5)
                    col_k = 1.0 - _ease(clamp((a - 0.35 * scale) / (fb_dur - 0.5), 0.0, 1.0))
                    rad = (0.48 + 0.85 * exp_k) * scale * col_k
                    spread = (0.25 + 1.45 * exp_k) * scale * (0.65 + 0.35 * (i % 2))
                    if rad > 0.04:
                        pos = (bx + math.cos(ang) * spread,
                               max(0.08, by + a * (1.2 + 0.15 * i) * scale),
                               bz + math.sin(ang) * spread)
                        _w.add(r, F.flame_mesh(pos, tm, seed=seed + i * 13, size=rad, heat=1.35, cam=cam))

            # 3. Ground flash pool
            if age < 0.75:
                pk = (1.0 - age / 0.75) ** 1.4
                r.add_sprite((bx, 0.05, bz),
                             F.pool((255, 146, 54), 3.6 * scale * (0.4 + 0.6 * min(1.0, age * 4.0)),
                                    intensity=0.55 * pk, squash=0.5),
                             layer=_fx.FX_LAYER)

            # 4. Ballistic cooling fragment streaks + ember sparks
            streak_dur = 1.45 if big else 1.05
            if age < streak_dur:
                n_st = 16 if big else 11
                for i in range(n_st):
                    ang = i * 2.399963 + seed * 0.3
                    spd = (3.6 + (i % 5) * 1.1) * scale
                    vx, vz = math.cos(ang) * spd, math.sin(ang) * spd
                    vy = (4.2 + (i % 6) * 0.9) * scale
                    py = max(0.05, by + 0.3 + vy * age - 4.9 * age * age)
                    if py <= 0.06:
                        continue
                    ta = max(0.0, age - 0.04)
                    ty = max(0.05, by + 0.3 + vy * ta - 4.9 * ta * ta)
                    hot = max(0.0, 1.0 - age / streak_dur)
                    col = (int(130 + 125 * hot), int(54 + 160 * hot), int(24 + 80 * hot))
                    r.add_line3d((bx + vx * ta, ty, bz + vz * ta),
                                 (bx + vx * age, py, bz + vz * age),
                                 col, 2 if i % 4 == 0 else 1, layer=2)
                r.add_sprite((bx, by + 0.4, bz),
                             F.sparks(tm, t0 * 1000.0, seed=seed, n=28 if big else 18,
                                      speed=8.5 * scale, life=streak_dur),
                             layer=_fx.FX_LAYER)

            # 5. Residual burning fuel puddle on the ground for barrels
            if med and 0.4 < age < 7.5:
                rf = clamp(1.0 - max(0.0, age - 4.5) / 3.0, 0.0, 1.0)
                _w.add(r, F.flame_mesh((bx, 0.06, bz), tm, seed=seed + 91, size=0.72 * rf, cam=cam))
                r.add_sprite((bx, 0.05, bz), F.pool((255, 118, 32), 2.1 * rf, intensity=0.35 * rf, squash=0.5),
                             layer=_fx.FX_LAYER)

    def _draw_enemies(self, r, tm):
        for e in self.brain.enemies:
            if not e["live"] and e["alive"]:
                continue
            x, y, z = e["x"], e["y"], e["z"]
            if e["kind"] in ("gunner", "breacher"):
                kind = "heavy"
            elif e["kind"] in ("overwatch", "officer"):
                kind = "officer"
            else:
                kind = R.GUARD_VIEW[e["slot"] % len(R.GUARD_VIEW)]
            gk = ("guard", kind)
            if not e["alive"]:
                if e["truck"] is not None and (e.get("fall") is None or e["fall"].rest is None):
                    x, z = e["truck"]["x"], e["truck"]["z"] + 1.15
                fall = e.get("fall")
                if fall is None:
                    ux, uz = e.get("fall_dir", (0.0, 0.0))
                    track = D.track_for(e.get("dead_pose") == "dead_back", e["slot"])
                    fall = e["fall"] = D.Fall(_w.hum(gk, True, flags=("os12",)),
                                              e.get("pose") or POSES["stand"],
                                              track, (x, y, z), e["yaw"],
                                              (ux * R.GUARD_PUSH_M, uz * R.GUARD_PUSH_M), e["slot"])
                pose, root, yaw = fall.at(self.t - e["dead_t"], self._floor)
                _w.actor(r, gk, pose, root, yaw, int(tm), seed=100 + e["slot"], amp=0.0,
                         rifle_on=False, hd=True, flags=("os12",))
                e["rest"] = fall.chest
                if e["mags"] and fall.rest is not None:
                    a = e["slot"] * 1.9
                    mx = fall.chest[0] + math.cos(a) * 0.42
                    mz = fall.chest[1] + math.sin(a) * 0.42
                    my = self._floor(mx, mz)
                    _w.add(r, R._shell_drop_mesh(mx, my, mz, e["yaw"] + 35.0))
                continue
            gh = _w.hum(gk, True, flags=("os12",))
            pose = self._guard_pose(e)
            if not e["moving"]:
                pose = _hold_cached(gh, pose, "os12", "ready", key=("m8_guard", kind))
            th_age = self.t - e.get("throw_t", -9.0)
            if 0.0 <= th_age < 0.55:
                if th_age < 0.28:
                    wk = _ease(th_age / 0.28)
                    pose = dict(pose, spine=pose.get("spine", 6) - 16.0 * wk,
                                rsh_p=152.0 * wk, rsh_r=22.0, rel=52.0,
                                lsh_p=42.0, lsh_r=14.0, lel=48.0)
                else:
                    fk = _ease((th_age - 0.28) / 0.27)
                    pose = dict(pose, spine=pose.get("spine", 6) + 18.0 * fk,
                                rsh_p=152.0 - 110.0 * fk, rsh_r=14.0, rel=14.0,
                                lsh_p=36.0, lsh_r=12.0, lel=52.0)
            stag = max(0.0, 1.0 - (self.t - e["hit_t"]) / 0.3)
            if stag > 0.0:
                pose = dict(pose, spine=pose.get("spine", 8) - 12.0 * stag)
                if not e["moving"]:
                    pose["rifle_p"] = pose.get("rifle_p", 0.0) - 12.0 * stag
            e["pose"] = pose
            holding_gun = not (0.0 <= th_age < 0.55)
            joints = _w.actor(r, gk, pose, (x, y, z), e["yaw"], int(tm), seed=100 + e["slot"],
                              amp=0.4, rifle_on=holding_gun, hd=True, flags=("os12",))
            if 0.0 <= th_age < 0.28 and joints and joints.get("rhand") is not None:
                mg = Mesh()
                mg.add(self._meshes["grenade"], t=joints["rhand"])
                _w.add(r, mg)
            m = joints.get("muzzle") if joints else None
            if m is not None and e["tele"] > 0.0:
                if e["kind"] == "overwatch":
                    rem = max(0.0, e["tele"] - self.t)
                    dur = max(0.1, e.get("tele_dur", B.OVERWATCH_TELE))
                    tight = clamp(1.0 - rem / dur, 0.0, 1.0)
                    wobble = (1.0 - tight) * 0.55
                    tx = self.px + math.sin(self.t * 8.0 + e["slot"]) * wobble
                    ty = self.py + 1.18 + math.cos(self.t * 6.5) * wobble * 0.35
                    tz = self.pz
                    dx, dy, dz = tx - m[0], ty - m[1], tz - m[2]
                    dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
                    ux, uy, uz = dx / dist, dy / dist, dz / dist
                    hit = self.world.ray_hit(m, (ux, uy, uz), 105.0)
                    ph = B._ray_sphere(m, (ux, uy, uz), (self.px, self.py + 1.18, self.pz), 0.36)
                    if ph is not None and ph < hit:
                        hit = ph
                    end = (m[0] + ux * hit, m[1] + uy * hit, m[2] + uz * hit)
                    # Depth-tested segmented 3D laser ribbon on layer 2 (occluded by player & cover)
                    cam_pos = getattr(r, "cam", m)
                    ref_up = (0.0, 1.0, 0.0) if abs(uy) < 0.9 else (1.0, 0.0, 0.0)
                    s_ax = C._f_unit(C._f_cross((ux, uy, uz), ref_up))
                    u_ax = C._f_unit(C._f_cross(s_ax, (ux, uy, uz)))
                    locked = rem < 0.45
                    pulse = 0.72 + 0.28 * math.sin(self.t * (28.0 if locked else 10.0))
                    c_hot = (255, int(115 * pulse), int(105 * pulse)) if locked else (228, 52, 44)
                    bm = Mesh()
                    n_seg = max(1, min(20, int(math.ceil(hit / 3.0))))
                    for si in range(n_seg):
                        f0, f1 = si / float(n_seg), (si + 1) / float(n_seg)
                        pa = (m[0] + (end[0] - m[0]) * f0, m[1] + (end[1] - m[1]) * f0, m[2] + (end[2] - m[2]) * f0)
                        pb = (m[0] + (end[0] - m[0]) * f1, m[1] + (end[1] - m[1]) * f1, m[2] + (end[2] - m[2]) * f1)
                        da = math.dist(cam_pos, pa)
                        db = math.dist(cam_pos, pb)
                        wa = clamp(0.0045 + da * (0.0014 if locked else 0.0011), 0.005, 0.032)
                        wb = clamp(0.0045 + db * (0.0014 if locked else 0.0011), 0.005, 0.032)
                        for ax in (s_ax, u_ax):
                            bm.face([
                                (pa[0] - ax[0] * wa, pa[1] - ax[1] * wa, pa[2] - ax[2] * wa),
                                (pa[0] + ax[0] * wa, pa[1] + ax[1] * wa, pa[2] + ax[2] * wa),
                                (pb[0] + ax[0] * wb, pb[1] + ax[1] * wb, pb[2] + ax[2] * wb),
                                (pb[0] - ax[0] * wb, pb[1] - ax[1] * wb, pb[2] - ax[2] * wb),
                            ], c_hot, 2, True, True)
                    if bm.faces:
                        _w.add(r, bm)
                    gl = _fx.glow((255, 110, 96), 0.26, tm, seed=e["slot"],
                                  core=(255, 226, 214), intensity=0.55 + 0.45 * tight, max_px=22)
                    gl.bounds_m = (0.45, 0.45)
                    gl.strict_occ = True
                    r.add_sprite(m, gl, layer=2)
                    dot_pos = (end[0] - ux * 0.04, end[1] - uy * 0.04, end[2] - uz * 0.04)
                    dot = _fx.glow((255, 48, 38), 0.11 if locked else 0.08, tm, seed=e["slot"],
                                   core=(255, 224, 212), intensity=1.1 * pulse, max_px=9)
                    dot.light = False
                    dot.strict_occ = True
                    r.add_sprite(dot_pos, dot, layer=2)
                else:
                    r.add_sprite(m, _fx.glow((255, 70, 50), 0.14, tm, seed=e["slot"],
                                             core=(255, 120, 90), intensity=0.8),
                                 layer=_fx.FX_LAYER)

    def _draw_player(self, r, tm):
        key = ("biribel", OUTFIT_GUARD)
        at = (self.px, self.py, self.pz)
        if self.dying:
            kk = clamp(self.death_t / 0.6, 0.0, 1.0)
            _w.actor(r, key, blend("kneel", "dead_back", kk), at, self.body_yaw, int(tm), seed=93,
                     amp=0.0, rifle_on=False, flags=("shotgun",), expression="angry")
            self._muzzle = None
            self._flash_basis = None
            return
        if self.phase == "climb":
            pose = self._climb_pose()
            _w.actor(r, key, pose, at, self.body_yaw, int(tm), seed=93, amp=0.0,
                     rifle_on=False, flags=("shotgun",), expression="angry")
            self._muzzle = None
            self._flash_basis = None
            return
        use_sg = (self.weapon == "shotgun")
        flags = ("shotgun", "nopump") if use_sg else ("os12", "nomag")
        hum = _w.hum(key, flags=flags)
        pose = self._player_pose()
        pump = 0.0
        sg_shell = False
        mag_mode, mag_t = "attached", 0.0
        aim_hold = 0.50 if use_sg else 0.40
        mode = "aim" if (self.ads > 0.5 or self.t - self.last_fire < aim_hold) else "ready"
        if use_sg:
            if self.reloading > 0.0:
                pose, pump, sg_shell = R.sg_reload_pose(
                    hum, pose, self._reload_dur - self.reloading, self._reload_dur,
                    shells=self._reload_n, dry=self._reload_dry)
            else:
                pump = R._pump_k(self.t - self.pump_at)
                pose = R._shotgun_hold(hum, pose, mode, ("m7player_sg", mode), pump)
            draw_yaw = self.body_yaw + R.SG_BLADE_YAW
        else:
            if self.reloading > 0.0:
                pose, mag_mode, mag_t = _os12_reload_pose(hum, pose, self.RELOAD_S - self.reloading, self.RELOAD_S)
            else:
                pose = R._held(hum, pose, "os12", mode, ("m8_biri_os12", mode))
            draw_yaw = self.body_yaw
        joints = _w.actor(r, key, pose, at, draw_yaw, int(tm), seed=93,
                          amp=0.12, rifle_on=True, flags=flags, expression="angry")
        if use_sg and joints:
            R.draw_shotgun_pump(r, joints.get("rhand"), joints.get("rifle_m"), pump)
            if sg_shell:
                R.draw_sg_shell(r, joints.get("lhand"), joints.get("rifle_m"))
        elif not use_sg and joints:
            self._draw_os12_mag(r, joints, mag_mode, mag_t)
        rm = joints.get("rifle_m") if joints else None
        hand = joints.get("rhand") if joints else None
        if rm is not None and hand is not None:
            off = m_apply(rm, BORE_LOCAL["shotgun" if use_sg else "rifle"])
            tip = (hand[0] + off[0], hand[1] + off[1], hand[2] + off[2])
            fvec = C._f_unit(m_apply(rm, (0.0, 0.0, 1.0)))
            rx = C._f_unit(m_apply(rm, (1.0, 0.0, 0.0)))
            ry = C._f_unit(m_apply(rm, (0.0, 1.0, 0.0)))
            self._flash_basis = (tip, fvec, rx, ry)
            self._muzzle = tip
        else:
            f, rg = _fwd(self.yaw, 0.0), _right(self.yaw)
            self._muzzle = (self.px + f[0] * 0.7 + rg[0] * 0.25, self.py + 1.38,
                            self.pz + f[2] * 0.7 + rg[2] * 0.25)
            self._flash_basis = None

    def _draw_os12_mag(self, r, joints, mag_mode, mag_t):
        hand = joints.get("rhand")
        lhand = joints.get("lhand")
        rm = joints.get("rifle_m")
        if rm is None:
            return
        mag = _os12_mag_mesh_cached()
        if mag_mode == "none":
            return
        if mag_mode == "attached" and hand is not None:
            off = m_apply(rm, (0.0, -0.075, 0.135))
            origin = (hand[0] + off[0], hand[1] + off[1], hand[2] + off[2])
        elif mag_mode == "pulling" and hand is not None:
            off = m_apply(rm, (0.0, -0.075 - 0.16 * mag_t, 0.135 + 0.02 * mag_t))
            origin = (hand[0] + off[0], hand[1] + off[1], hand[2] + off[2])
            self._last_mag_pos = origin
        elif mag_mode == "in_hand" and lhand is not None:
            seat_off = m_apply(rm, (0.0, -0.075, 0.135))
            seat = (hand[0] + seat_off[0], hand[1] + seat_off[1], hand[2] + seat_off[2]) if hand else lhand
            h_off = m_apply(rm, (0.0, 0.06, -0.01))
            hp = (lhand[0] + h_off[0], lhand[1] + h_off[1], lhand[2] + h_off[2])
            origin = tuple(hp[i] + (seat[i] - hp[i]) * mag_t for i in range(3))
        else:
            return
        verts = [tuple(a + b for a, b in zip(m_apply(rm, v), origin)) for v in mag.verts]
        faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in mag.faces]
        r.add_dynamic(verts, faces)

    def _climb_pose(self):
        """Exact IK ladder pose solved onto S3.LADDER_RUNG_YS and the top grab rails."""
        if self._climb_pose_cur is not None:
            return self._climb_pose_cur
        hum = _w.hum(("biribel", OUTFIT_GUARD), flags=("shotgun",))
        k = clamp((self.climb_t or 0.0) / CLIMB_S, 0.0, 1.0)
        u = max(0.0, (k - 0.05) / 0.95)
        return S3.ladder_climb(hum, u)[0]

    def _draw_bodi(self, r, tm):
        a = self.brain.bodi
        key = ("ally", "bodi")
        yaw = a["yaw"]
        if self.phase in ("clear", "climb", "catwalk") and a["state"] == "up" and not a["moving"]:
            yaw = _yaw(S3.LADDER_X - a["x"], S3.LADDER_Z - a["z"])   # he watches the ladder
        joints = _w.actor(r, key, self._bodi_pose(a, key), (a["x"], a["y"], a["z"]), yaw, int(tm),
                          seed=61, amp=0.3, rifle_on=True, flags=("os12",), mouth=0.0)
        a["muzzle"] = joints.get("muzzle") if joints else None
        if a["state"] == "down":
            r.add_sprite((a["x"], 1.6, a["z"]), _fx.glow((255, 90, 70), 0.3, tm, intensity=0.8,
                                                          core=(255, 160, 140), flicker=0.3),
                         layer=_fx.FX_LAYER)

    def _bodi_pose(self, a, key):
        """Bodi's stance with the OS-12: the raid's ally poses, re-posed for his gun."""
        if a["state"] == "down":
            return dict(POSES["slump"])
        hum = _w.hum(key, flags=("os12",))
        stance = _hold_cached(hum, dict(POSES["ready"]), "os12", "ready",
                              key=("m8_bodi_os12", "ready"))
        if self.t - a["aim"] < B.ALLY_HOLD:
            aim_st = dict(blend(POSES["stand"], "aim", 0.85), twist=R.AIM_TWIST,
                          head_y=-0.8 * R.AIM_TWIST)
            aim_pose = _hold_cached(hum, aim_st, "os12", "aim",
                                    aim=(0.0, 1.45 + 10.0 * a["slope"], 10.0),
                                    key=("m8_bodi_os12", round(a["slope"], 1)))
            up = clamp((self.t - a["raised"]) / B.ALLY_RAISE, 0.0, 1.0)
            stance = aim_pose if up >= 1.0 else blend(stance, aim_pose, _ease(up))
        k = a.get("walk_k", 0.0)
        if k > 0.0:
            run = R._held(hum, R.pose_run(a.get("gait", 0.0) * 1.9, lean=6), "os12", "ready",
                         ("m8_bodi_os12", "ready"))
            stance = run if k >= 1.0 else blend(stance, run, k * k * (3.0 - 2.0 * k))
        dk = a.get("duck_k", 0.0)
        if dk > 0.0 and a["state"] == "up":
            cov = _hold_cached(hum, dict(POSES["crouch"]), "os12", "ready",
                               key=("m8_bodi_os12", "crouch"))
            stance = blend(stance, cov, _ease(dk))
        return stance

    def _draw_vasile(self, r, tm):
        if not self.vasile_out:
            return
        x, y, z = S3.VASILE_AT
        _w.actor(r, "vasile", dict(POSES["stand"]), (x, y, z), self.vasile_yaw, int(tm),
                 seed=71, amp=0.25, rifle_on=False, mouth=0.0)
        r.add_sprite((x + 0.16, y + 1.66, z - 0.12),
                     _fx.glow((255, 120, 42), 0.10, tm, flicker=0.25,
                              core=(255, 220, 150), intensity=0.6, max_px=10),
                     layer=_fx.FX_LAYER)

    # --- input --------------------------------------------------------------------

    def handle_event(self, event):
        if not self._active or self.paused:
            return
        if not self.dying and self.phase not in ("climb", "catwalk"):
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    self._switch_weapon()
                    return
                if event.key == pygame.K_1:
                    self._switch_weapon("shotgun")
                    return
                if event.key == pygame.K_2:
                    self._switch_weapon("rifle")
                    return
            elif event.type == pygame.MOUSEWHEEL and event.y:
                self._switch_weapon()
                return
        R.RaidScene.handle_event(self, event)


_SCENE = None


def scene():
    global _SCENE
    if _SCENE is None:
        _SCENE = TrapScene()
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
    """Drop the scene without finishing (mission restart, quit to menu)."""
    if _SCENE is not None and _SCENE.active():
        _SCENE._active = False
        _SCENE.paused = False
        STATE.m8_trap_active = False
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
