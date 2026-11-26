"""Mission 8 Duty - Phase 4: Last Flight (3D door-gunner chase).

Maru flies, Biribel mans the open-bay 360-deg pintle LMG. Five checkpointed
sections: the mansion front lawn (gunship pylon turn over the lit facade and
gate), a banking mist handoff onto Curfew Boulevard, The Radio Station, Route 12,
and Ucilev's gunship duel ending in the shootdown.

Controls: mouse aims 360 deg, hold RMB to brace/zoom ADS, hold LMB to fire
(manage barrel heat), F pops magnesium decoy flares.
"""
import math
import random
import traceback

import pygame

from core.config import HEIGHT, WIDTH, audio, draw_vignette, font_terminal, font_terminal_small
from core.state import STATE
from cutscenes import death3d as D
from cutscenes import fire3d as F3D
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from engine.render3d import VehicleDestructionManager
from engine3d import POSES, clamp
from engine3d.core import m_apply, v_add
from game.vehicle_fx import default_vehicle_fx
from missions.m6 import hud3d as H
from missions.m7 import raid3d as R
from missions.m7 import raid_brain as RB
from missions.m7 import raid_hud as RH
from missions.m8.revenge import chase3d as C
from missions.m8.revenge import chase_set as CS
from missions.m8.revenge import trap3d as T

from . import flight_fx as FX
from . import flight_set as FS
from . import mansion_set as MS
from . import mansion_world as MW

SENS = 0.105
ADS_SENS = 0.052
ADS_UP = 12.0
ADS_DOWN = 8.0
REL_YAW_LIM = (8.0, 152.0)
YAW_LIM = 72.0
PITCH_LIM = (-62.0, 20.0)
FOV = 62.0
FOV_ADS = 38.0
FIRE_GAP = 1.0 / 13.8
HEAT_SHOT = 0.0142
HEAT_COOL = 0.42
FLARES = 5
FLARE_S = 2.1
ROCKET_BOOST_V = 18.0
ROCKET_RPG_V = 52.0
ROCKET_SAM_V = 60.0
ROCKET_V = 58.0
ROCKET_ROAD_V = 60.0
ROCKET_AIR_V = 62.0
SAM_TURN_DEG_S = 62.0
ROCKET_TELE_S = 1.0
ROCKET_DMG = 18.0
HULL = 100.0
HELI_V = 34.0
UCILEV_V = 28.0
ALT = 19.5
ESCAPE_R = 175.0
ESCAPE_S = 8.0
LAWN_C = (0.0, 0.0, -18.0)
LAWN_R = 38.5
START_A_DEG = 104.0
HANDOFF_S = 1.65

# Exact cp=0 t=0 starting state for seamless liftoff_maru match cut
START_HPOS = (
    LAWN_C[0] + math.sin(math.radians(START_A_DEG)) * LAWN_R,
    14.5,
    LAWN_C[2] + math.cos(math.radians(START_A_DEG)) * LAWN_R,
)
START_AIM_YAW = R._yaw(LAWN_C[0] - START_HPOS[0], LAWN_C[2] - START_HPOS[2])
START_HYAW = (START_AIM_YAW - 90.0) % 360.0
START_HPITCH = -3.0
START_HROLL = 10.5
START_AIM_PITCH = -14.0

# (title, set, z0, z1, seconds); road sections run z0 -> z1 at HELI_V (cp=4 at UCILEV_V).
SECTIONS = (
    ("MANSION LAWN", "estate", 0.0, 0.0, 0.0),
    ("CURFEW BOULEVARD", "road", 40.0, 1120.0, 33.0),
    ("THE RADIO STATION", "road", 1120.0, 2220.0, 33.0),
    ("ROUTE 12", "road", 2220.0, 3360.0, 35.0),
    ("UCILEV", "road", 3360.0, 5400.0, 72.0),
)
LAWN_SPAWNS = (
    ("guard", -3.2, -11.0), ("guard", 3.2, -11.0), ("guard", -9.5, -14.0),
    ("guard", 9.5, -14.0), ("guard", -6.0, -28.0), ("guard", 6.0, -28.0),
    ("guard", -10.5, -36.0), ("guard", 10.5, -36.0),
    ("aa", -13.0, -24.0), ("aa", 13.0, -24.0),
    ("tanker", -8.5, -20.0), ("tanker", 8.5, -20.0),
)
# (kind, z, x offset from the corridor); spawned as the heli closes in.
ROAD_SPAWNS = {
    1: (
        ("rpg", 170, -22), ("tanker", 200, 5), ("aa", 212, 9), ("guard", 220, -2),
        ("rpg", 335, 22), ("jeep", 390, 4), ("aa", 420, -6), ("tanker", 430, -2),
        ("rpg", 545, -22), ("gunship", 630, 16), ("rpg", 745, 22), ("aa", 775, 9),
        ("tanker", 785, 5), ("guard", 865, -3), ("rpg", 955, -22), ("aa", 1005, 8),
        ("tanker", 1015, 4),
    ),
    2: (
        ("gunship", 1210, 16), ("rpg", 1310, 22), ("aa", 1340, 10), ("tanker", 1352, 5),
        ("rpg", 1545, -22), ("aa", 1560, 14), ("tanker", 1572, 8), ("gunship", 1605, 22),
        ("aa", 1645, 14), ("tanker", 1656, 8), ("rpg", 1700, 22), ("gunship", 1850, 18),
        ("rpg", 1950, -22), ("aa", 2060, 12), ("tanker", 2072, 6), ("guard", 2145, 4),
    ),
    3: (
        ("jeep", 2310, 4), ("tanker", 2418, 18), ("aa", 2432, 14), ("rpg", 2416, 28),
        ("jeep", 2540, 4), ("aa", 2668, 10), ("tanker", 2678, 5), ("rpg", 2682, 16),
        ("gunship", 2760, 18), ("jeep", 2850, 4), ("aa", 2918, 16), ("tanker", 2928, 12),
        ("rpg", 2912, 26), ("jeep", 3040, 4), ("tanker", 3154, 5), ("aa", 3168, 9),
        ("jeep", 3250, 4),
    ),
    4: (),
}
HP = {"guard": 24.0, "rpg": 26.0, "aa": 120.0, "tanker": 46.0, "jeep": 78.0, "gunship": 195.0}
SPHERE = {"guard": ((1.1, 0.85),), "rpg": ((1.1, 0.85),), "aa": ((1.1, 2.4),),
          "tanker": ((1.6, 2.8),), "jeep": ((0.9, 2.1),), "gunship": ((1.2, 3.0),)}
CALLOUTS = {
    "rocket_f": "Rocket, dead ahead!", "rocket_l": "Rocket, left!", "rocket_r": "Rocket, right!",
    "hit": "Taking heavy fire - keep shooting!", "light": "Searchlight - kill it!", "hold": "Hold on!",
}
TAIL_HP_MAX = 380.0
UCILEV_SUB_HP = {
    "spotlight": 1100.0,
    "pod_l": 950.0,
    "pod_r": 950.0,
    "turbine": 550.0,
}
UCILEV_HP_MAX = sum(UCILEV_SUB_HP.values())
UCILEV_P2_HP = UCILEV_SUB_HP["pod_l"] + UCILEV_SUB_HP["pod_r"] + UCILEV_SUB_HP["turbine"]
UCILEV_FLOOR_HP = 0.0
UCILEV_ANCHORS = {
    "spotlight": (0.0, 0.56, 5.72),
    "pod_l": (-1.68, 1.05, 0.98),
    "pod_r": (1.68, 1.05, 0.98),
    "turbine": (0.0, 2.55, 0.35),
}
UCILEV_ORBIT_R = 46.0


def _road_pt(z, xo=0.0, y=0.0):
    return (FS.corridor_x(z) + xo, y, z)


def _settings_fx():
    try:
        from core.user_settings import SETTINGS
        return (
            bool(SETTINGS.reduced_motion),
            bool(SETTINGS.flash_reduction),
            clamp(float(SETTINGS.shake_scale), 0.0, 1.5),
        )
    except Exception:
        return False, False, 1.0


class FlightScene:
    set_paused = R.RaidScene.set_paused
    _grab = R.RaidScene._grab
    _snd = R.RaidScene._snd
    say = R.RaidScene.say
    _project = R.RaidScene._project

    def __init__(self):
        self._active = False
        self.paused = False
        self.done = False
        self.result = None
        self.audio = None
        self.t = 0.0
        self._floor_hint = 0.0
        self._veil_cache = {}
        self._setup(0)

    # --- lifecycle -------------------------------------------------------------

    def begin(self):
        self.t = 0.0
        self.done = False
        self.result = None
        self._active = True
        self.paused = False
        STATE.m8_flight_active = True
        try:
            from .. import m8_audio as _m8_audio
            self.audio = _m8_audio.instance(audio)
            self.audio.warm()
        except Exception:
            self.audio = None
        self._setup(int(getattr(STATE, "m8_flight_cp", 0) or 0))
        self._grab(True)
        try:
            self._warm()
        except Exception:
            traceback.print_exc()

    def _warm(self):
        _lmg()
        CS.maru_gunship_fpv_parts()
        FX.tanker_mesh(False)
        CS.helicopter_parts()
        CS.rocket()
        CS.gun_truck()
        CS.jeep()
        _w.hum("maru")
        for kind in set(R.GUARD_VIEW) | {"heavy"}:
            _w.hum(("guard", kind), True, flags=("os12",))
        if SECTIONS[self.cp][1] == "estate":
            MS.renderer()
        else:
            FS.renderer()
        FS._urban_horizon_ring()
        FS._mountain_horizon_ring()
        try:
            F3D.smoke_puff_surface(0, 0, 16, 128)
            F3D.smoke_puff_surface(3, 0, 16, 128)
        except Exception:
            pass
        try:
            from cutscenes import m8dutyfilms as _m8df
            _m8df.warm_crash()
        except Exception:
            traceback.print_exc()

    def active(self):
        return self._active

    def finish(self, result="win"):
        if self.done:
            return False
        self.done = True
        self.result = result
        self._active = False
        STATE.m8_flight_active = False
        STATE.m8_ucilev_cp = None
        self.ucilev_cp = None
        self._grab(False)
        if self.audio is not None and result != "win":
            try:
                self.audio.stop_loops()
            except Exception:
                pass
        from .. import flow as _flow
        return _flow.on_flight_done(result)

    def _setup(self, cp):
        self.cp = cp = max(0, min(len(SECTIONS) - 1, cp))
        STATE.m8_flight_cp = cp
        self.sec_t = 0.0
        self.road_t = max(0.0, (SECTIONS[cp][2] - SECTIONS[1][2]) / HELI_V) if cp >= 1 else 0.0
        self.hull = HULL
        self.heat = 0.0
        self.overheat = False
        self.flares = FLARES
        self.flare_at = -9.0
        self.flare_fx = []
        self.firing = False
        self.aiming = False
        self.ads = 0.0
        self.last_fire = -9.0
        self.flash_seed = 0
        self.gy = 0.0 if cp == 0 else 10.0
        self.gp = START_AIM_PITCH if cp == 0 else -6.5
        self.rotor = 0.0
        self.shake = 0.0
        self.hit_mark = -9.0
        self.hit_kind = None
        self.hurt = 0.0
        self.last_hurt = -9.0
        self._glare = 0.0
        self.dying = False
        self.death_t = 0.0
        self.death_msg = ""
        self.targets = []
        self.rockets = []
        self.backblasts = []
        self.booms = []
        self.flak_bursts = []
        self.debris = []
        self.smoke_puffs = []
        self.brass = []
        self.bullets = []
        self.veh_fx = VehicleDestructionManager(seed=701 + cp * 37, fx=default_vehicle_fx(_fx))
        self.world = None
        if SECTIONS[cp][1] == "estate":
            self.world = MW.World()
            self.world.front_open = self.world.study_open = self.world.terrace_open = True
            self.world.heli_parked = False
        self.tracers, self.sparks, self.impacts, self.flashes = [], [], [], []
        self.lines = []
        self.dmg_marks = []
        self.spawned = set()
        self.rdist = 58.0
        self.escape = 0.0
        self.tail_hp = TAIL_HP_MAX
        self.r_down = -1.0
        self.r_boom = False
        self.ucilev = None
        self.shootdown = -1.0
        self.kill_shot = False
        self.kills = 0
        self.handoff_t = -1.0
        self._cloud_exit_t = -1.0
        self._next_flak = 0.8
        self.rng = random.Random(4100 + cp)
        self._said = set()
        self._next_rk_seed = 1
        self._evade_roll = 0.0
        self._evade_y = 0.0
        self._hitstop = 0.0
        self._ucilev_marks = []
        title = SECTIONS[cp][0]
        if cp < 4:
            if self._active:
                STATE.m8_ucilev_cp = None
            self.ucilev_cp = None
            self._ucilev_cp_sec_t = 0.0
            self._cp_toast_label = ("CHECKPOINT - " + title) if cp > 0 else ""
            self.cp_toast = self.t if cp > 0 else -9.0
        else:
            ucp = getattr(STATE, "m8_ucilev_cp", None)
            if isinstance(ucp, dict) and isinstance(ucp.get("subs"), dict):
                self.ucilev_cp = {**ucp, "subs": dict(ucp["subs"])}
                self.sec_t = max(0.0, float(self.ucilev_cp.get("sec_t", 0.0)))
                self.road_t = max(0.0, (SECTIONS[cp][2] - SECTIONS[1][2]) / HELI_V + self.sec_t)
                self._ucilev_cp_sec_t = self.sec_t
                self._cp_toast_label = "CHECKPOINT - " + str(self.ucilev_cp.get("label", title))
            else:
                self.ucilev_cp = None
                self._ucilev_cp_sec_t = 0.0
                self._cp_toast_label = "CHECKPOINT - " + title
            self.cp_toast = self.t
        if cp == 0:
            for i, (kind, x, z) in enumerate(LAWN_SPAWNS):
                y0 = self.world.surface_y(x, z, 8.0) if (kind == "guard" and abs(z) < 3.0) else 0.0
                self._spawn(kind, (x, y0, z), i)
            self.say("MARU", "Hold on! Hit the fuel trucks by the AA guns - blow the gate wide open!", 3.6)
        elif cp == 1:
            self.say("MARU", "There he is! Don't lose him over the boulevard!", 3.0)
        elif cp == 2:
            self.say("MARU", "Broadcast station ahead - Guard birds incoming!", 3.0)
        elif cp == 3:
            self.say("MARU", "Route 12. Shred his tail rotor - put him down!", 3.4)
        else:
            self._spawn_ucilev(self.ucilev_cp)
        self._clamp_gy()
        self._title = title

    def _spawn_ucilev(self, ucp=None):
        hp = self._heli_pos()
        hy = self._heli_yaw()
        if isinstance(ucp, dict) and ucp.get("subs"):
            subs = {k: max(0.0, float(ucp["subs"].get(k, v))) for k, v in UCILEV_SUB_HP.items()}
            phase = int(ucp.get("phase", 1))
            if subs.get("spotlight", 0.0) <= 0.0 and phase < 2:
                phase = 2
            if subs.get("pod_l", 0.0) <= 0.0 and subs.get("pod_r", 0.0) <= 0.0 and phase < 3:
                phase = 3
            light_on = subs.get("spotlight", 0.0) > 0.0
            wb = math.radians(hy + 56.0)
            rx = math.sin(wb) * 44.0
            rz = math.cos(wb) * 44.0
            ry = 4.0
            self.ucilev = self._spawn("gunship", (hp[0] + rx, hp[1] + ry, hp[2] + rz), 99)
            man0 = "close_duel" if phase >= 3 else "strafe_arc"
            self.ucilev.update(
                hp=sum(subs.values()), max_hp=UCILEV_HP_MAX, ucilev=True,
                subs=subs, phase=phase, light_on=light_on, ang=0.0,
                rx=rx, ry=ry, rz=rz, dive_t0=self.t - 3.0,
                yaw=R._yaw(-rx, -rz), pitch=-8.0, roll=10.0,
                maneuver=man0, maneuver_t=0.0, maneuver_id=0, maneuver_fired_rk=-1,
                stagger_until=-9.0, climax_t=-1.0, salvo_at=-9.0, salvo_pod=None,
                pass_snd_t=-9.0, smoke_t=self.t, sub_hit_t=-9.0, sub_hit_part=None,
                next=self.t + 1.15, rk_tele=False, tele=0.0, burst=0,
            )
            eye = self.eye()
            ux, uy, uz = self.ucilev["x"], self.ucilev["y"] + 1.4, self.ucilev["z"]
            self.gy = R._wrap(math.degrees(math.atan2(ux - eye[0], uz - eye[2])) - self.mount_yaw())
            self.gp = clamp(math.degrees(math.atan2(uy - eye[1], math.hypot(ux - eye[0], uz - eye[2]))), *PITCH_LIM)
            if phase >= 3:
                self.say("MARU", "Pods down - shred the dorsal turbine!", 3.2)
            elif subs.get("pod_l", 0.0) > 0.0 and subs.get("pod_r", 0.0) > 0.0:
                self.say("MARU", "Spotlight's out - hit his rocket pods!", 3.2)
            else:
                self.say("MARU", "One pod left - finish it!", 3.2)
            return
        wb = math.radians(hy + 26.0)
        rx = math.sin(wb) * 106.0
        rz = math.cos(wb) * 106.0
        ry = 26.0
        self.ucilev = self._spawn("gunship", (hp[0] + rx, hp[1] + ry, hp[2] + rz), 99)
        self.ucilev.update(
            hp=UCILEV_HP_MAX, max_hp=UCILEV_HP_MAX, ucilev=True,
            subs=dict(UCILEV_SUB_HP), phase=1, light_on=True, ang=0.0,
            rx=rx, ry=ry, rz=rz, dive_t0=self.t,
            maneuver="dive", maneuver_t=0.0, maneuver_id=0, maneuver_fired_rk=-1,
            stagger_until=-9.0, climax_t=-1.0, salvo_at=-9.0, salvo_pod=None,
            pass_snd_t=-9.0, smoke_t=0.0, sub_hit_t=-9.0, sub_hit_part=None,
        )
        self.say("MARU", "UCILEV! Shoot out that spotlight!", 3.4)

    def _advance_section(self, cp):
        """Seamless continuous leg transition along the corridor (and cp=0 -> cp=1 cloud bank)."""
        self.cp = cp
        STATE.m8_flight_cp = cp
        self.sec_t = 0.0
        self.road_t = max(0.0, (SECTIONS[cp][2] - SECTIONS[1][2]) / HELI_V)
        self.hull = min(HULL, self.hull + 30.0)
        self.flares = min(FLARES, self.flares + 2)
        self.cp_toast = self.t
        self._title = SECTIONS[cp][0]
        self._cp_toast_label = "CHECKPOINT - " + self._title
        self._evade_roll = 0.0
        self._evade_y = 0.0
        if cp == 1:
            self.world = None
            self.targets = []
            self.rockets = []
            self.backblasts = []
            self.bullets = []
            self.booms = []
            self.debris = []
            self.smoke_puffs = []
            self.handoff_t = -1.0
            self._cloud_exit_t = self.t
            self.say("MARU", "There he is! Don't lose him over the boulevard!", 3.0)
        elif cp == 2:
            self.say("MARU", "Broadcast station ahead - Guard birds incoming!", 3.2)
        elif cp == 3:
            self.say("MARU", "Route 12. Shred his tail rotor - put him down!", 3.4)
        elif cp == 4:
            self.ucilev_cp = None
            STATE.m8_ucilev_cp = None
            self._ucilev_cp_sec_t = 0.0
            self._spawn_ucilev()
        self._clamp_gy()

    # --- geometry --------------------------------------------------------------

    def _gorge_pose(self, t, rt):
        """Continuous gorge corridor -> clockwise basin orbit past z=5400 so cp=4 never stalls."""
        _name, _kind, z0, z1, _dur = SECTIONS[4]
        z_lin = z0 + t * UCILEV_V
        if z_lin <= z1:
            wf = clamp((z1 - z_lin) / 120.0, 0.0, 1.0)
            hx = FS.corridor_x(z_lin) - 10.0 + 1.1 * wf * math.sin(rt * 0.42)
            return hx, z_lin, FS.corridor_yaw(z_lin), wf, False
        t_orb = (z_lin - z1) / UCILEV_V
        cy0 = FS.corridor_yaw(z1)
        x0 = FS.corridor_x(z1) - 10.0
        cy_r = math.radians(cy0)
        cx_o = x0 + math.cos(cy_r) * UCILEV_ORBIT_R
        cz_o = z1 - math.sin(cy_r) * UCILEV_ORBIT_R
        d_ang = math.degrees(t_orb * UCILEV_V / UCILEV_ORBIT_R)
        a_rad = math.radians(cy0 - 90.0 + d_ang)
        hx = cx_o + math.sin(a_rad) * UCILEV_ORBIT_R
        hz = cz_o + math.cos(a_rad) * UCILEV_ORBIT_R
        return hx, hz, (cy0 + d_ang) % 360.0, 0.0, True

    def _heli_pos(self, t=None):
        t = self.sec_t if t is None else t
        name, kind, z0, z1, dur = SECTIONS[self.cp]
        if kind == "estate":
            # Continuous clockwise pylon orbit (monotonic a_deg increase, zero backwards reversal)
            a_deg = START_A_DEG + t * 8.2
            a = math.radians(a_deg)
            lift = clamp(t / 3.5, 0.0, 1.0)
            lift_e = lift * lift * (3.0 - 2.0 * lift)
            climb_extra = 0.0
            if self.handoff_t >= 0.0:
                hu = clamp((self.t - self.handoff_t) / HANDOFF_S, 0.0, 1.0)
                climb_extra = 16.0 * hu * hu
            r_cur = LAWN_R + 3.5 * lift_e
            ca = math.cos(a)
            rz = r_cur if ca <= 0.0 else 16.0
            return (LAWN_C[0] + math.sin(a) * r_cur,
                    14.5 + 7.5 * lift_e + climb_extra,
                    LAWN_C[2] + ca * rz)
        rt = self.road_t if t == self.sec_t else ((z0 - SECTIONS[1][2]) / HELI_V + t)
        if self.cp == 4:
            hx, z, _fyaw, _wf, _orb = self._gorge_pose(t, rt)
            gy = FS.surface_y(hx, z)
            return (hx, gy + ALT + 2.0 * math.sin(rt * 0.55) + clamp(self._evade_y, -2.4, 2.4), z)
        z = min(z1, z0 + t * HELI_V)
        dive = 0.0
        if self.cp == 1 and t < 1.6:
            du = 1.0 - t / 1.6
            dive = 6.0 * du * du
        alt_base = 21.0 if self.cp in (1, 2) else ALT
        # Fly along the west flank (corridor_x - 9..11 m) so all corridor threats sit in the starboard doorway
        hx = FS.corridor_x(z) - 10.0 + 1.1 * math.sin(rt * 0.42)
        gy = FS.surface_y(hx, z)
        return (hx, gy + alt_base + 2.0 * math.sin(rt * 0.55) + dive, z)

    def _heli_vel(self):
        eps = 0.05
        t0 = self.sec_t
        dur = SECTIONS[self.cp][4]
        if SECTIONS[self.cp][1] == "road" and self.cp < 4 and dur > 0.0 and t0 + eps > dur:
            p0 = self._heli_pos(max(0.0, t0 - eps))
            p1 = self._heli_pos(t0)
        else:
            p0 = self._heli_pos(t0)
            p1 = self._heli_pos(t0 + eps)
        return ((p1[0] - p0[0]) / eps, (p1[1] - p0[1]) / eps, (p1[2] - p0[2]) / eps)

    def _rocket_lead_point(self, p, tgt_now, vh, speed, max_lead=1.6):
        """Damped proportional-navigation lead point with a capped <=1.6 s lead window
        (no discriminant speed-warp hack)."""
        rx, ry, rz = tgt_now[0] - p[0], tgt_now[1] - p[1], tgt_now[2] - p[2]
        dist = math.sqrt(rx * rx + ry * ry + rz * rz)
        if dist < 1e-3:
            return tgt_now
        radial_v = (rx * vh[0] + ry * vh[1] + rz * vh[2]) / dist
        v_close = max(24.0, speed - radial_v * 0.65)
        t_lead = clamp((dist / v_close) * 0.78, 0.0, max_lead)
        return (
            tgt_now[0] + vh[0] * t_lead,
            tgt_now[1] + vh[1] * t_lead * 0.5,
            tgt_now[2] + vh[2] * t_lead,
        )

    @staticmethod
    def _rotate_dir_bounded(cur, tgt, max_rad):
        """Rotate unit direction ``cur`` toward ``tgt`` by at most ``max_rad`` radians."""
        dot = clamp(cur[0] * tgt[0] + cur[1] * tgt[1] + cur[2] * tgt[2], -1.0, 1.0)
        ang = math.acos(dot)
        if ang <= 1e-5 or ang <= max_rad:
            return tgt
        u = max_rad / ang
        nx = cur[0] + (tgt[0] - cur[0]) * u
        ny = cur[1] + (tgt[1] - cur[1]) * u
        nz = cur[2] + (tgt[2] - cur[2]) * u
        nm = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        return (nx / nm, ny / nm, nz / nm)

    def _heli_yaw(self):
        name, kind, z0, z1, dur = SECTIONS[self.cp]
        if kind == "estate":
            hx, _, hz = self._heli_pos()
            base = (R._yaw(LAWN_C[0] - hx, LAWN_C[2] - hz) - 90.0) % 360.0
            if self.handoff_t >= 0.0:
                hu = clamp((self.t - self.handoff_t) / HANDOFF_S, 0.0, 1.0)
                base = (base - 35.0 * hu * hu) % 360.0
            return base
        if self.cp == 4:
            _hx, _hz, fyaw, wf, _orb = self._gorge_pose(self.sec_t, self.road_t)
            return (fyaw - 33.0 + 3.0 * wf * math.sin(self.road_t * 0.42)) % 360.0
        z = self._heli_pos()[2]
        # Purposeful port crab (corridor_yaw - 30..-36 deg) keeps boulevard & east/west roofs in starboard bay
        return FS.corridor_yaw(z) - 33.0 + 3.0 * math.sin(self.road_t * 0.42)

    def _heli_tilt(self):
        """Return (pitch_deg, roll_deg) of Maru's gunship."""
        if self.shootdown >= 0.0:
            k = self.t - self.shootdown
            return -14.0 * k, 24.0 * math.sin(k * 9.0)
        if SECTIONS[self.cp][1] == "estate":
            roll = 10.5 + 2.0 * math.sin(self.sec_t * 0.45)
            pitch = -3.0
            if self.handoff_t >= 0.0:
                hu = clamp((self.t - self.handoff_t) / HANDOFF_S, 0.0, 1.0)
                roll += 18.0 * hu
                pitch += 10.0 * hu
            return pitch, roll
        rt = self.road_t
        if self.cp == 4:
            _hx, z, _fyaw, _wf, in_orb = self._gorge_pose(self.sec_t, rt)
            curve = 9.0 if in_orb else clamp(
                R._wrap(FS.corridor_yaw(z + 18.0) - FS.corridor_yaw(max(0.0, z - 18.0))) * 0.42,
                -10.0, 10.0,
            )
            roll = 3.5 + curve + 4.5 * math.cos(rt * 0.42) + clamp(self._evade_roll, -16.0, 16.0)
            pitch = -5.2 + 2.2 * math.cos(rt * 0.55)
            return pitch, roll
        z = self._heli_pos()[2]
        curve = clamp(R._wrap(FS.corridor_yaw(z + 18.0) - FS.corridor_yaw(max(0.0, z - 18.0))) * 0.42, -10.0, 10.0)
        roll = 3.5 + curve + 4.5 * math.cos(rt * 0.42)
        pitch = -5.2 + 2.2 * math.cos(rt * 0.55)
        return pitch, roll

    def mount_yaw(self):
        """Reference mount yaw; gunner traverse is clamped to REL_YAW_LIM in the starboard doorway."""
        if SECTIONS[self.cp][1] == "estate":
            hx, _, hz = self._heli_pos()
            return R._yaw(LAWN_C[0] - hx, LAWN_C[2] - hz)
        if self.cp == 4:
            return self._gorge_pose(self.sec_t, self.road_t)[2]
        return FS.corridor_yaw(self._heli_pos()[2])

    def _rel_yaw_cabin(self):
        return R._wrap((self.mount_yaw() + self.gy) - self._heli_yaw())

    def _clamp_gy(self, dx_deg=0.0):
        """Clamp gunner traverse strictly to the open starboard doorway (+8..+152 deg)
        with gentle resistance damping near the fore/aft doorframe stops."""
        cur_rel = self._rel_yaw_cabin()
        if dx_deg != 0.0:
            lo, hi = REL_YAW_LIM
            if dx_deg < 0.0 and cur_rel < lo + 14.0:
                dx_deg *= clamp((cur_rel - lo) / 14.0, 0.14, 1.0)
            elif dx_deg > 0.0 and cur_rel > hi - 14.0:
                dx_deg *= clamp((hi - cur_rel) / 14.0, 0.14, 1.0)
            cur_rel += dx_deg
        clamped_rel = clamp(cur_rel, REL_YAW_LIM[0], REL_YAW_LIM[1])
        self.gy = R._wrap((self._heli_yaw() + clamped_rel) - self.mount_yaw())

    def eye(self):
        hpos = self._heli_pos()
        hyaw = self._heli_yaw()
        hpitch, hroll = self._heli_tilt()
        hmat = FX.heli_matrix(hyaw, hpitch, hroll)
        red, _fl, shk_s = _settings_fx()
        return FX.gunner_eye(hpos, hmat, self._rel_yaw_cabin(), self.ads,
                             self.t, self.shake * shk_s, reduced_motion=red,
                             gp=self.gp, gy_world=self.mount_yaw() + self.gy)

    def aim_dir(self):
        return R._fwd(self.mount_yaw() + self.gy, self.gp)

    def retardovici_pos(self):
        if self.cp == 0:
            if self.sec_t > 12.0:
                return None
            u = self.sec_t
            return (14.0 + 5.0 * u, 20.0 + 3.2 * u, 30.0 + 18.0 * u)
        if SECTIONS[self.cp][1] != "road" or self.cp >= 4:
            return None
        hx, hy, hz = self._heli_pos()
        z = hz + self.rdist
        weave = 7.5 * math.sin(self.t * 0.65)
        rx = FS.corridor_x(z) + weave + (8.0 * (self.t - self.r_down) if self.r_down >= 0.0 else 0.0)
        gy = FS.surface_y(rx, z)
        alt_base = 21.0 if self.cp in (1, 2) else ALT
        y = gy + alt_base + 2.5 + 1.8 * math.sin(self.t * 0.9)
        if self.r_down >= 0.0:
            k = self.t - self.r_down
            y = max(gy + 2.5, y - k * 3.5 - k * k * 3.2)
            z += k * 8.0
        return (rx, y, z)

    def retardovici_yaw(self):
        p = self.retardovici_pos()
        if p is None:
            return 0.0
        if self.cp == 0:
            return 22.0
        if self.r_down >= 0.0:
            return FS.corridor_yaw(p[2]) + (self.t - self.r_down) * 260.0
        wobble = 14.0 * math.sin(self.t * 5.2) if (self.cp == 3 and self.tail_hp < 140.0) else 0.0
        return FS.corridor_yaw(p[2]) + wobble

    def retardovici_roll(self):
        if self.cp == 0 or self.r_down >= 0.0:
            return 0.0
        return -20.0 * math.cos(self.t * 0.65)

    def tail_point(self):
        p = self.retardovici_pos()
        if p is None:
            return None
        _b, _m, _t, info = CS.helicopter_parts()
        return CS._xf(info["tail_hub"], p, self.retardovici_yaw(), 0.0, 0.0)

    # --- targets ---------------------------------------------------------------

    def _spawn(self, kind, pos, key):
        ki = abs(hash(str(key)))
        e = dict(kind=kind, x=pos[0], y=pos[1], z=pos[2], hp=HP[kind], max_hp=HP[kind],
                 alive=True, dead_t=-9.0, next=self.t + 1.2 + self.rng.random() * 1.4,
                 yaw=0.0, key=key, key_i=ki, slot=ki % 32, ang=0.0, ucilev=False,
                 light=(kind == "aa"), tele=0.0, rk_tele=False, burst=0, state="fly",
                 pose=dict(POSES["ready"]), fall=None, fall_dir=(0.0, 0.0), death_ctx=None,
                 vx=0.0, vy=0.0, vz=0.0, pitch=-4.0, roll=0.0, bounces=0,
                 impact_t=None, cooked_off=False, smoke_acc=0.0, seed=ki % 997, hit_t=-9.0)
        if kind == "gunship":
            slot_x = 14.0 if len(self.targets) % 2 == 0 else 30.0
            e["off"] = (slot_x, 6.0, 82.0)
        self.targets.append(e)
        self.spawned.add(key)
        return e

    def _road_spawns(self):
        hp = self._heli_pos()
        hz = hp[2]
        for i, (kind, z, xo) in enumerate(ROAD_SPAWNS.get(self.cp, ())):
            key = (self.cp, i)
            if key in self.spawned or z - hz > 300.0:
                continue
            if kind == "gunship":
                spawn_p = (hp[0] + (18.0 if i % 2 == 0 else 36.0), hp[1] + 8.0, hp[2] + 104.0)
                self._spawn(kind, spawn_p, key)
                self.say("MARU", "Guard bird closing in!", 2.6)
            elif kind == "jeep":
                e = self._spawn(kind, _road_pt(z, xo), key)
                e["v"] = 28.0
                e["xo"] = xo
            elif kind == "tanker":
                e = self._spawn(kind, _road_pt(z, xo, FS.surface_y(FS.corridor_x(z) + xo, z)), key)
                e["v"] = 24.0 if self.cp == 3 else 0.0
                e["xo"] = xo
            elif kind == "rpg":
                # Snap to nearest building roof if available in this stretch
                roofs = [r for r in FS.roof_spots() if abs(r[2] - z) < 42.0]
                if roofs:
                    rx, ry, rz, _side = min(roofs, key=lambda r: abs(r[2] - z))
                    self._spawn(kind, (rx, ry, rz), key)
                else:
                    self._spawn(kind, _road_pt(z, xo, FS.surface_y(FS.corridor_x(z) + xo, z)), key)
            else:
                self._spawn(kind, _road_pt(z, xo, FS.surface_y(FS.corridor_x(z) + xo, z)), key)

    def _ucilev_spheres(self, e):
        """Return (center, radius, is_head, part_name) hit spheres for Ucilev's gunship."""
        pos = (e["x"], e["y"], e["z"])
        yaw = e.get("yaw", 0.0)
        pitch = e.get("pitch", -4.0)
        roll = e.get("roll", 0.0)
        subs = e.get("subs", {})
        phase = e.get("phase", 1)
        out = [
            (CS._xf((0.0, 1.30, 1.80), pos, yaw, pitch, roll), 2.35, False, None),
            (CS._xf((0.0, 1.65, -2.10), pos, yaw, pitch, roll), 2.15, False, None),
        ]
        if phase == 1 and subs.get("spotlight", 0.0) > 0.0:
            out.append((CS._xf(UCILEV_ANCHORS["spotlight"], pos, yaw, pitch, roll), 1.85, True, "spotlight"))
        elif phase == 2:
            for pk in ("pod_l", "pod_r"):
                if subs.get(pk, 0.0) > 0.0:
                    out.append((CS._xf(UCILEV_ANCHORS[pk], pos, yaw, pitch, roll), 1.65, True, pk))
        elif phase >= 3 and subs.get("turbine", 0.0) > 0.0:
            out.append((CS._xf(UCILEV_ANCHORS["turbine"], pos, yaw, pitch, roll), 2.35, True, "turbine"))
        return out

    def spheres(self, e):
        """Return hit spheres as (center, radius, is_head)."""
        if e["kind"] in ("guard", "rpg"):
            return [
                ((e["x"], e["y"] + 1.15, e["z"]), 0.85, False),
                ((e["x"], e["y"] + 1.66, e["z"]), 0.48, True),
            ]
        if e["kind"] == "gunship":
            if e.get("ucilev"):
                return [(c, rad, hd) for c, rad, hd, _part in self._ucilev_spheres(e)]
            return [
                ((e["x"], e["y"] + 1.25, e["z"]), 2.9, False),
                ((e["x"], e["y"] + 2.25, e["z"]), 1.75, True),
            ]
        if e["kind"] == "aa":
            return [((e["x"], e["y"] + 1.3, e["z"]), 2.8, False)]
        if e["kind"] == "tanker":
            return [((e["x"], e["y"] + 1.8, e["z"]), 3.0, False)]
        return [((e["x"], e["y"] + 0.9, e["z"]), 2.4, False)]

    def _threats(self):
        hp = self._heli_pos()
        return sum(1 for e in self.targets if e["alive"] and e["kind"] in ("aa", "gunship", "rpg")
                   and math.dist((e["x"], e["y"], e["z"]), hp) < 220.0)

    def _save_ucilev_checkpoint(self, e, toast_label, death_label):
        subs = e.get("subs", {})
        snap = {
            "phase": int(e.get("phase", 1)),
            "light_on": bool(subs.get("spotlight", 0.0) > 0.0),
            "subs": {k: max(0.0, float(subs.get(k, 0.0))) for k in UCILEV_SUB_HP},
            "sec_t": float(self.sec_t),
            "label": str(death_label),
        }
        self.ucilev_cp = snap
        STATE.m8_ucilev_cp = {**snap, "subs": dict(snap["subs"])}
        self._ucilev_cp_sec_t = self.sec_t
        self.cp_toast = self.t
        self._cp_toast_label = toast_label

    def _on_ucilev_subsys_break(self, e, part):
        pos_u = (e["x"], e["y"], e["z"])
        pw = CS._xf(UCILEV_ANCHORS[part], pos_u, e.get("yaw", 0.0), e.get("pitch", -4.0), e.get("roll", 0.0))
        _, _, shk_s = _settings_fx()
        self._snd("subsys_boom", self._pan(pw[0], pw[2]), math.dist(pw, self._heli_pos()))
        self._snd("spark_pop", self._pan(pw[0], pw[2]))
        if part == "spotlight":
            e["phase"] = 2
            e["light_on"] = False
            e["maneuver"] = "stagger"
            e["maneuver_t"] = 0.0
            e["maneuver_id"] = e.get("maneuver_id", 0) + 1
            e["stagger_until"] = self.t + 1.35
            e["rk_tele"] = False
            e["tele"] = 0.0
            e["burst"] = 0
            self._spawn_boom(pw, 6.0, 91, "heli_mid", n_deb=22)
            self.shake = min(1.5, self.shake + 0.55 * shk_s)
            self._hitstop = 0.18
            self._evade_roll = clamp(self._evade_roll + 9.0, -16.0, 16.0)
            self.hull = min(HULL, self.hull + 15.0)
            if self.flares < FLARES:
                self.flares = min(FLARES, self.flares + 1)
            self._save_ucilev_checkpoint(e, "CHECKPOINT - SPOTLIGHT DOWN", "SPOTLIGHT DOWN")
            self.say("MARU", "Spotlight's blown! Watch his pods!", 3.2)
        elif part in ("pod_l", "pod_r"):
            subs = e["subs"]
            both_down = (subs.get("pod_l", 0.0) <= 0.0 and subs.get("pod_r", 0.0) <= 0.0)
            self._spawn_boom(pw, 6.4 if both_down else 5.4, 93 if part == "pod_l" else 94,
                             "heli_mid", n_deb=20 if both_down else 16)
            self.shake = min(1.5, self.shake + (0.60 if both_down else 0.36) * shk_s)
            self._hitstop = 0.20 if both_down else 0.12
            self._evade_roll = clamp(self._evade_roll - 11.0, -16.0, 16.0)
            if both_down:
                e["phase"] = 3
                e["maneuver"] = "stagger"
                e["maneuver_t"] = 0.0
                e["maneuver_id"] = e.get("maneuver_id", 0) + 1
                e["stagger_until"] = self.t + 1.35
                e["rk_tele"] = False
                e["tele"] = 0.0
                e["burst"] = 0
                e["salvo_at"] = -9.0
                self.hull = min(HULL, self.hull + 35.0)
                if self.flares < FLARES:
                    self.flares = min(FLARES, self.flares + 2)
                self._save_ucilev_checkpoint(e, "CHECKPOINT - TURBINE EXPOSED", "PHASE III: TURBINE")
                self.say("MARU", "Both pods wrecked - hit the turbine!", 3.2)
            else:
                side_lbl = "Port" if part == "pod_l" else "Starboard"
                short_lbl = "PORT" if part == "pod_l" else "STBD"
                self.hull = min(HULL, self.hull + 15.0)
                if self.flares < FLARES:
                    self.flares = min(FLARES, self.flares + 1)
                self._save_ucilev_checkpoint(e, f"CHECKPOINT - {short_lbl} POD DOWN", f"{short_lbl} POD DOWN")
                self.say("MARU", f"{side_lbl} pod down - take the other!", 2.8)
        else:
            e["phase"] = 3
            e["climax_t"] = self.t
            e["maneuver"] = "climax"
            e["maneuver_t"] = 0.0
            e["maneuver_id"] = e.get("maneuver_id", 0) + 1
            e["rk_tele"] = False
            e["tele"] = 0.0
            e["burst"] = 0
            e["salvo_at"] = -9.0
            self._spawn_boom(pw, 7.2, 97, "heli_mid", n_deb=26)
            self._snd("barrel_boom", self._pan(pw[0], pw[2]), 25.0)
            self.shake = min(1.5, self.shake + 0.78 * shk_s)
            self._hitstop = 0.24
            self._evade_roll = clamp(self._evade_roll + 13.0, -16.0, 16.0)
            self.say("MARU", "Turbine's blown! Wait - hold on!", 3.0)

    def hurt_target(self, e, dmg, is_head=False, hit_pos=None, hit_ray=None, hit_dist=None, hit_part=None):
        if not e["alive"]:
            return
        e["hit_t"] = self.t
        if e["ucilev"]:
            if self.t < e.get("stagger_until", -9.0) or e.get("climax_t", -1.0) >= 0.0:
                return
            subs = e.setdefault("subs", dict(UCILEV_SUB_HP))
            phase = e.get("phase", 1)
            if phase == 1:
                active_parts = ("spotlight",) if subs.get("spotlight", 0.0) > 0.0 else ()
            elif phase == 2:
                active_parts = tuple(p for p in ("pod_l", "pod_r") if subs.get(p, 0.0) > 0.0)
            else:
                active_parts = ("turbine",) if subs.get("turbine", 0.0) > 0.0 else ()
            if not active_parts:
                return
            target_part = hit_part if hit_part in active_parts else None
            if target_part is None and is_head:
                target_part = active_parts[0]
            if target_part is not None:
                eff = dmg * 1.25
                e["sub_hit_t"] = self.t
                e["sub_hit_part"] = target_part
            else:
                eff = dmg * (0.70 if phase >= 3 else 0.35)
                hp_pos = self._heli_pos()
                pos_u = (e["x"], e["y"], e["z"])
                target_part = min(
                    active_parts,
                    key=lambda pk: math.dist(
                        hp_pos,
                        CS._xf(UCILEV_ANCHORS[pk], pos_u, e.get("yaw", 0.0),
                               e.get("pitch", -4.0), e.get("roll", 0.0)),
                    ),
                )
            subs[target_part] = max(0.0, subs.get(target_part, 0.0) - eff)
            e["hp"] = sum(max(0.0, v) for v in subs.values())
            e["light_on"] = subs.get("spotlight", 0.0) > 0.0
            if subs[target_part] <= 0.0:
                self._on_ucilev_subsys_break(e, target_part)
            return
        eff_dmg = dmg * (1.85 if is_head else 1.0)
        prev = e["hp"]
        e["hp"] -= eff_dmg
        if e["hp"] <= 0.0:
            e["alive"] = False
            e["dead_t"] = self.t
            e["tele"] = 0.0
            e["rk_tele"] = False
            self.kills += 1
            if hit_ray is not None:
                hm = math.hypot(hit_ray[0], hit_ray[2]) or 1.0
                e["fall_dir"] = (hit_ray[0] / hm, hit_ray[2] / hm)
            e["death_ctx"] = dict(
                is_head=bool(is_head),
                hit_zone="head" if is_head else "chest",
                hit_pos=hit_pos,
                hit_ray=hit_ray,
                weapon="lmg",
                dmg=eff_dmg,
                overkill=max(0.0, eff_dmg - prev),
                hit_dist=hit_dist,
            )
            if e["kind"] == "gunship":
                e["state"] = "crashing"
                side = 1.0 if e["x"] < self._heli_pos()[0] else -1.0
                e["vx"] = side * self.rng.uniform(7.5, 11.5)
                e["vy"] = self.rng.uniform(2.0, 4.5)
                e["vz"] = HELI_V * 0.75
                self.veh_fx.trigger(
                    "gunship_air", (e["x"], e["y"] + 1.2, e["z"]),
                    yaw=e["yaw"], pitch=e["pitch"], roll=e["roll"],
                    vel=(e["vx"], e["vy"], e["vz"]), seed=e["seed"],
                )
                self._snd("barrel_boom", self._pan(e["x"], e["z"]),
                          math.dist((e["x"], e["y"], e["z"]), self._heli_pos()))
            elif e["kind"] == "tanker":
                _, _, shk_s = _settings_fx()
                self.shake = min(1.4, self.shake + 0.36 * shk_s)
                self.veh_fx.trigger(
                    "tanker", (e["x"], e["y"], e["z"]),
                    yaw=e["yaw"], seed=e["seed"], tag=id(e),
                    floor_fn=self._floor, on_cookoff=self._veh_cookoff,
                )
                self._snd("barrel_boom", self._pan(e["x"], e["z"]),
                          math.dist((e["x"], e["y"], e["z"]), self._heli_pos()))
                self._snd("crash", self._pan(e["x"], e["z"]))
                # Chain detonation splash onto nearby troops, jeeps & AA trucks
                for other in self.targets:
                    if other["alive"] and other is not e and other["kind"] != "gunship":
                        if math.dist((other["x"], other["y"], other["z"]), (e["x"], e["y"], e["z"])) <= 16.5:
                            self.hurt_target(other, 95.0)
            elif e["kind"] in ("aa", "jeep"):
                self.veh_fx.trigger(
                    "aa_truck" if e["kind"] == "aa" else "jeep",
                    (e["x"], e["y"], e["z"]),
                    yaw=e["yaw"], seed=e["seed"], tag=id(e),
                    floor_fn=self._floor, on_cookoff=self._veh_cookoff,
                )
                self._snd("barrel_boom", 0.0, math.dist((e["x"], e["y"], e["z"]), self._heli_pos()))
            else:
                self._snd("enemy_down", 30.0)

    def _veh_cookoff(self, vd, ck):
        d = math.dist(vd.pos, self._heli_pos())
        if d < 140.0:
            _, _, shk_s = _settings_fx()
            self.shake = min(1.2, self.shake + max(0.0, 0.25 - d * 0.002) * shk_s)
            self._snd("barrel_boom", self._pan(vd.pos[0], vd.pos[2]), d)

    def _pan(self, x, z):
        ex, _, ez = self.eye()
        d = max(1.0, math.hypot(x - ex, z - ez))
        rg = R._right(self.mount_yaw() + self.gy)
        return clamp(((x - ex) * rg[0] + (z - ez) * rg[2]) / d, -1.0, 1.0)

    def _spawn_boom(self, pos, rad, seed, kind="boom", n_deb=14):
        self.booms.append((self.t, pos, rad, seed, kind))
        sc = clamp(rad / 3.5, 0.6, 2.0)
        cols = ((38, 36, 34), (62, 54, 46), (128, 52, 32), (24, 24, 26))
        for i in range(n_deb):
            ang = self.rng.uniform(0.0, math.tau)
            spd = self.rng.uniform(3.5, 9.5) * sc
            sz = self.rng.uniform(0.08, 0.22) * sc
            self.debris.append(dict(
                x=pos[0], y=max(0.2, pos[1]), z=pos[2],
                vx=math.cos(ang) * spd, vy=self.rng.uniform(3.2, 8.8) * sc, vz=math.sin(ang) * spd,
                rx=self.rng.uniform(0, 360), ry=self.rng.uniform(0, 360),
                vrx=self.rng.uniform(-440, 440), vry=self.rng.uniform(-440, 440),
                sx=sz * 1.4, sy=sz * 0.5, sz=sz,
                col=cols[i % len(cols)], hot=(i % 2 == 0), t0=self.t, bounces=0,
            ))
        del self.debris[:-54]
        for i in range(5):
            ang = self.rng.uniform(0.0, math.tau)
            spd = self.rng.uniform(0.6, 2.2) * sc
            self.smoke_puffs.append(dict(
                x=pos[0] + self.rng.uniform(-0.5, 0.5), y=pos[1] + 0.5, z=pos[2] + self.rng.uniform(-0.5, 0.5),
                vx=math.cos(ang) * spd, vy=self.rng.uniform(1.8, 3.4) * sc, vz=math.sin(ang) * spd,
                born=self.t + i * 0.04, dur=self.rng.uniform(2.2, 3.4),
                r0=0.55 * sc, r1=2.2 * sc, alpha=168, warm=3, seed=(seed + i) % 6,
            ))
        del self.smoke_puffs[:-64]

    def hurt_hull(self, dmg, src=None):
        if self.dying or self.shootdown >= 0.0:
            return
        if self.ucilev is not None and self.ucilev.get("climax_t", -1.0) >= 0.0:
            return
        _, _, shk_s = _settings_fx()
        self.hull -= dmg
        self.hurt = min(1.0, self.hurt + dmg / 30.0)
        self.last_hurt = self.t
        self.shake = min(1.5, self.shake + (dmg / 20.0) * shk_s)
        self._snd("hull_hit")
        if src is not None:
            ex, _, ez = self.eye()
            sx, sz = (src[0], src[2]) if len(src) >= 3 else (src[0], src[1])
            bearing = R._wrap(R._yaw(sx - ex, sz - ez) - (self.mount_yaw() + self.gy))
            self.dmg_marks.append((self.t, -bearing))
        if self.hull <= 30.0 and "hit" not in self._said:
            self._said.add("hit")
            self.say("MARU", CALLOUTS["hit"], 2.8)
        if self.hull <= 0.0:
            self.dying = True
            self.death_t = 0.0
            if self.cp == 4 and getattr(self, "ucilev_cp", None):
                lbl = self.ucilev_cp.get("label", "CHECKPOINT")
                self.death_msg = f"MARU'S BIRD IS DOWN  -  AGAIN FROM {lbl}"
            elif self.cp > 0:
                self.death_msg = f"MARU'S BIRD IS DOWN  -  AGAIN FROM {SECTIONS[self.cp][0]}"
            else:
                self.death_msg = "MARU'S BIRD IS DOWN  -  AGAIN FROM THE SECTION"
            self.firing = False
            self._snd("crash")

    def _can_launch_rocket(self, src, air_launched=False, min_dz=None, kind="sam",
                           telegraphed=False, bypass_dz=False):
        """Guarantee rockets only ever launch inside clear visual range and the starboard bay arc."""
        hp = self._heli_pos()
        hyaw = self._heli_yaw()
        dx, dz = src[0] - hp[0], src[2] - hp[2]
        dist_xz = math.hypot(dx, dz)
        rel_yaw = R._wrap(R._yaw(dx, dz) - hyaw)
        rel_lo = 10.0 if telegraphed else 18.0
        rel_hi = 142.0 if (telegraphed or bypass_dz) else 115.0
        if not (rel_lo <= rel_yaw <= rel_hi):
            return False
        if bypass_dz:
            return 22.0 <= dist_xz <= 155.0
        if SECTIONS[self.cp][1] == "road":
            min_r = 32.0 if telegraphed else (60.0 if kind == "rpg" else 65.0)
            max_r = 128.0 if kind == "rpg" else 148.0
            dz_floor = (32.0 if air_launched else 44.0) if telegraphed else (48.0 if air_launched else 62.0)
            if min_dz is not None:
                dz_floor = min(dz_floor, min_dz)
            return dz >= dz_floor and (min_r <= dist_xz <= max_r)
        min_r = 22.0 if telegraphed else 26.0
        return min_r <= dist_xz <= 135.0

    def _fire_rocket(self, src, air_launched=False, telegraphed=False, kind=None, bypass_dz=False):
        max_rk = 3 if self.cp >= 1 else 2
        if sum(1 for rk in self.rockets if rk["alive"] and not rk["unstoppable"]) >= max_rk:
            return
        rk_kind = kind or ("sam" if air_launched else "sam")
        min_dz = (32.0 if air_launched else 46.0) if telegraphed else None
        if not self._can_launch_rocket(src, air_launched=air_launched, min_dz=min_dz,
                                       kind=rk_kind, telegraphed=telegraphed, bypass_dz=bypass_dz):
            return
        hp = self._heli_pos()
        vh = self._heli_vel()
        cruise_v = ROCKET_RPG_V if rk_kind == "rpg" else (ROCKET_AIR_V if air_launched else ROCKET_SAM_V)
        lead_max = 1.25 if rk_kind == "rpg" else 1.6
        tgt_0 = self._rocket_lead_point(src, (hp[0], hp[1] + 0.85, hp[2]), vh, cruise_v, max_lead=lead_max)
        dx, dy, dz = tgt_0[0] - src[0], tgt_0[1] - src[1], tgt_0[2] - src[2]
        if rk_kind == "rpg":
            # Semi-ballistic loft compensation calculated once at launch
            dy += math.hypot(dx, dz) * 0.048
        d = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        lead_dir = (dx / d, dy / d, dz / d)

        # Stage 1 initial launch attitude: ground pops upward +22..30 deg; air drops off pod with ignition dip
        horiz = max(1e-3, math.hypot(lead_dir[0], lead_dir[2]))
        hx_u, hz_u = lead_dir[0] / horiz, lead_dir[2] / horiz
        if air_launched:
            dip_ang = math.radians(-10.0)
            init_dir = (hx_u * math.cos(dip_ang), math.sin(dip_ang), hz_u * math.cos(dip_ang))
        elif rk_kind == "sam":
            pop_ang = math.radians(26.0)
            init_dir = (hx_u * math.cos(pop_ang), math.sin(pop_ang), hz_u * math.cos(pop_ang))
        else:
            init_dir = lead_dir
        init_v = ROCKET_BOOST_V

        seed = self._next_rk_seed
        self._next_rk_seed += 1
        self.backblasts.append((self.t, src, seed, rk_kind, bool(air_launched)))
        self.rockets.append(dict(
            p=src, t0=self.t, alive=True, unstoppable=False,
            trail=[src], puffs=[(src[0], src[1], src[2], self.t, seed % 6)],
            last_puff=self.t, dir=init_dir, lead_dir=lead_dir,
            vel=(init_dir[0] * init_v, init_dir[1] * init_v, init_dir[2] * init_v),
            speed=init_v, cruise_speed=cruise_v,
            phase="boost", kind=rk_kind, ballistic_t=-1.0,
            id_seed=seed, decoy=None, decoy_t=0.0, air=bool(air_launched),
        ))
        self._snd("rocket")
        self._snd("missile_warn")
        mx = self.mount_yaw() + self.gy
        side = R._wrap(R._yaw(src[0] - hp[0], src[2] - hp[2]) - mx)
        if self.t - getattr(self, "_rocket_call", -9.0) > 3.0:
            self._rocket_call = self.t
            if abs(side) < 22.0:
                key = "rocket_f"
            elif side < 0:
                key = "rocket_l"
            else:
                key = "rocket_r"
            self.say("MARU", CALLOUTS[key], 2.2)

    # --- update ----------------------------------------------------------------

    def update(self, keys=None):
        if not self._active or self.paused:
            return
        raw_dt = clamp(float(getattr(STATE, "dt", 1.0 / 60.0)), 0.0, 0.05)
        if self._hitstop > 0.0:
            self._hitstop = max(0.0, self._hitstop - raw_dt)
            red, _, _ = _settings_fx()
            dt = raw_dt * (0.65 if red else 0.25)
        else:
            dt = raw_dt
        self.t += dt
        if SECTIONS[self.cp][1] == "road":
            self.road_t += dt
        self.rotor = (self.rotor + dt * 1550.0) % 360.0
        self._snd("bed", "flight")
        self._snd("update", raw_dt)
        if self.dying:
            self.death_t += dt
            if self.death_t >= 2.6:
                self._setup(self.cp)
            return
        self.sec_t += dt
        self._clamp_gy()
        want_ads = 1.0 if (self.aiming and self.shootdown < 0.0) else 0.0
        ads_rate = ADS_UP if want_ads > self.ads else ADS_DOWN
        self.ads = clamp(self.ads + (want_ads - self.ads) * min(1.0, dt * ads_rate), 0.0, 1.0)
        self.shake = max(0.0, self.shake - raw_dt * 1.8)
        self.hurt = max(0.0, self.hurt - raw_dt * 1.2)
        ev_decay = math.exp(-3.2 * dt)
        self._evade_roll *= ev_decay
        self._evade_y *= ev_decay
        if self.overheat:
            self.heat = max(0.0, self.heat - dt * HEAT_COOL)
            self.overheat = self.heat > 0.22
        elif not self.firing:
            self.heat = max(0.0, self.heat - dt * HEAT_COOL)
        elif self.t - self.last_fire > FIRE_GAP * 1.15:
            self.heat = max(0.0, self.heat - dt * HEAT_COOL * 0.3)
        if self.firing and not self.overheat and self.shootdown < 0.0 and self.handoff_t < 0.0:
            self._fire()
        if SECTIONS[self.cp][1] == "road":
            self._road_spawns()
        self._targets_update(dt)
        self._bullets_update(dt)
        self._rockets_update(dt)
        self._fx_step(dt)
        self.veh_fx.update(dt, floor_fn=self._floor)
        self._chase_update(dt)
        self._section_update()
        if self.t - self.last_hurt > 6.0 and self.hull < 50.0 and self.shootdown < 0.0:
            self.hull = min(50.0, self.hull + 1.8 * dt)

        # Compute searchlight glare from active AA trucks or Ucilev
        hp = self._heli_pos()
        d_aim = self.aim_dir()
        glare = 0.0
        for e in self.targets:
            if e["alive"] and (e["kind"] == "aa" or (e.get("ucilev") and e.get("light_on", True))):
                vx, vy, vz = e["x"] - hp[0], (e["y"] + 2.0) - hp[1], e["z"] - hp[2]
                dist = math.sqrt(vx * vx + vy * vy + vz * vz) or 1.0
                if dist < 140.0:
                    dot = (vx * d_aim[0] + vy * d_aim[1] + vz * d_aim[2]) / dist
                    if e.get("ucilev") and e.get("maneuver") == "spotlight_sweep":
                        if dot > 0.48:
                            glare = max(glare, 0.28 + 0.65 * ((dot - 0.48) / 0.52))
                    elif dot > 0.72:
                        glare = max(glare, (dot - 0.72) / 0.28 * (1.0 - dist / 140.0))
        self._glare += (glare - self._glare) * min(1.0, dt * 8.0)

        now = self.t
        if self.tracers:
            self.tracers = [x for x in self.tracers if now - x[0] < 0.12]
        if self.sparks:
            self.sparks = [x for x in self.sparks if now - x[0] < 0.45]
        if self.impacts:
            self.impacts = [x for x in self.impacts if now - x[0] < 0.6]
        if self.flashes:
            self.flashes = [x for x in self.flashes if now - x[0] < 0.2]
        if self.booms:
            self.booms = [x for x in self.booms if now - x[0] < 3.2]
        if self.flak_bursts:
            self.flak_bursts = [f for f in self.flak_bursts if now - f[0] < 1.45]
        if self.dmg_marks:
            self.dmg_marks = [m for m in self.dmg_marks if now - m[0] < 0.9]
        if self.flare_fx:
            self.flare_fx = [f for f in self.flare_fx if now - f["t0"] < f["dur"]]
        if self.smoke_puffs:
            self.smoke_puffs = [p for p in self.smoke_puffs if now - p["born"] < p["dur"]]
        if self.backblasts:
            self.backblasts = [b for b in self.backblasts if now - b[0] < 1.55]

    def _fire(self):
        if self.t - self.last_fire < FIRE_GAP:
            return
        self.last_fire = self.t
        self.flash_seed += 1
        self.heat = min(1.0, self.heat + HEAT_SHOT)
        if self.heat >= 1.0:
            self.overheat = True
            self._snd("overheat")
            self.say("MARU", "Barrel's cooking - let it breathe!", 2.0)
        _, _, shk_s = _settings_fx()
        ads_k = FX._ease(self.ads)
        self.shake = min(0.85, self.shake + 0.055 * (1.0 - 0.65 * ads_k) * shk_s)
        self._snd("lmg_shot")
        o = self.eye()
        base_sp = 0.34 - 0.24 * ads_k
        heat_sp = (0.56 - 0.34 * ads_k) * self.heat
        spread = base_sp + heat_sp
        d = R._fwd(self.mount_yaw() + self.gy + self.rng.uniform(-spread, spread),
                    self.gp + self.rng.uniform(-spread, spread))

        basis_f, at_f, mz, _ = FX.lmg_xform(o, self.mount_yaw() + self.gy, self.gp, self)
        ej = v_add(at_f, m_apply(basis_f, FX.EJECT_PORT_LOCAL))
        rg_b = m_apply(basis_f, (1.0, 0.0, 0.0))
        up_b = m_apply(basis_f, (0.0, 1.0, 0.0))
        vh = self._heli_vel()
        self.brass.append(dict(
            x=ej[0], y=ej[1], z=ej[2],
            vx=vh[0] + rg_b[0] * 1.45 - up_b[0] * 0.65 + self.rng.uniform(-0.35, 0.35),
            vy=vh[1] - 0.85 + self.rng.uniform(-0.25, 0.35),
            vz=vh[2] + rg_b[2] * 1.45 - up_b[2] * 0.65 + self.rng.uniform(-0.35, 0.35),
            ry=self.rng.uniform(0, 360), vry=self.rng.uniform(-520, 520), t0=self.t,
        ))
        del self.brass[:-24]

        best = 400.0
        if d[1] < -1e-6:
            best = min(best, -o[1] / d[1])
        if self.world is not None:
            best = min(best, self.world.ray_hit(o, d, best))
        hit = None
        for e in self.targets:
            if not e["alive"]:
                continue
            if e.get("ucilev"):
                u_best = best
                u_pick = None
                for c, rad, is_head, pname in self._ucilev_spheres(e):
                    h = RB._ray_sphere(o, d, c, rad)
                    if h is not None and h < best:
                        score = h - (2.4 if pname is not None else 0.0)
                        if score < u_best:
                            u_best = score
                            u_pick = (h, ("t", e, is_head, pname))
                if u_pick is not None:
                    best, hit = u_pick
            else:
                for c, rad, is_head in self.spheres(e):
                    h = RB._ray_sphere(o, d, c, rad)
                    if h is not None and h < best:
                        best, hit = h, ("t", e, is_head, None)
        for rk in self.rockets:
            if rk["alive"] and not rk["unstoppable"] and rk.get("phase") != "ballistic":
                r_dist = math.dist(o, rk["p"])
                r_rad = 1.35 + 0.15 * clamp(r_dist / 110.0, 0.0, 1.0)
                h = RB._ray_sphere(o, d, rk["p"], r_rad)
                if h is not None and h < best:
                    best, hit = h, ("r", rk, False, None)
        tail = self.tail_point() if self.cp == 3 and self.r_down < 0.0 else None
        if tail is not None:
            h = RB._ray_sphere(o, d, tail, 2.8)
            if h is not None and h < best:
                best, hit = h, ("tail", None, False, None)
        end = (o[0] + d[0] * best, o[1] + d[1] * best, o[2] + d[2] * best)
        tr_col = (255, 134, 72) if (self.flash_seed % 3 == 0) else (255, 232, 162)
        self.tracers.append((self.t, mz, end, tr_col))
        if hit is None:
            if best < 399.0:
                self.impacts.append((self.t, end, "dust"))
            return
        self.hit_mark = self.t
        self.sparks.append((self.t, end))
        if hit[0] == "t":
            is_hd = bool(hit[2])
            h_part = hit[3]
            if hit[1].get("ucilev"):
                self.hit_kind = "head" if h_part is not None else None
            else:
                self.hit_kind = "head" if is_hd else ("kill" if hit[1]["hp"] <= 16.0 else None)
            self.hurt_target(hit[1], 16.0, is_head=is_hd, hit_pos=end, hit_ray=d,
                             hit_dist=best, hit_part=h_part)
            if hit[1]["kind"] in ("guard", "rpg"):
                self.impacts.append((self.t, end, "blood"))
                self._snd("headshot" if is_hd else "impact", True)
            else:
                vol_m = 0.42 if (hit[1].get("ucilev") and h_part is not None) else 0.34
                self._snd("metal", self._pan(end[0], end[2]), vol_m)
        elif hit[0] == "r":
            self.hit_kind = "kill"
            hit[1]["alive"] = False
            self._spawn_boom(hit[1]["p"], 3.5, hit[1].get("id_seed", 7), "rocket", n_deb=12)
            self._snd("barrel_boom", self._pan(*hit[1]["p"][::2]), best)
        else:
            self.hit_kind = "head"
            self.tail_hp -= 16.0
            self._snd("metal", self._pan(end[0], end[2]), 0.40)
            tp = self.tail_point() or self.retardovici_pos()
            if self.tail_hp <= TAIL_HP_MAX * 0.66 and "tail_1" not in self._said:
                self._said.add("tail_1")
                if tp is not None:
                    self._spawn_boom(tp, 2.4, 84, "rocket", n_deb=8)
                self.say("MARU", "Tail boom's smoking - keep chewing through it!", 2.8)
            elif self.tail_hp <= TAIL_HP_MAX * 0.33 and "tail_2" not in self._said:
                self._said.add("tail_2")
                if tp is not None:
                    self._spawn_boom(tp, 3.2, 86, "rocket", n_deb=10)
                self.say("MARU", "He's losing tail authority - put him in the trees!", 2.8)
            if self.tail_hp <= 0.0:
                self.r_down = self.t
                if tp is not None:
                    self._spawn_boom(tp, 4.4, 88, "tail", n_deb=14)
                self._snd("crash")
                self._snd("barrel_boom", 0.0, 45.0)
                self.say("MARU", "He's going down! He's going -", 3.0)

    def _targets_update(self, dt):
        hp = self._heli_pos()
        hz = hp[2]
        aa_active = False
        shooters = 0
        for e in self.targets:
            if not e["alive"]:
                if e["kind"] == "gunship":
                    self._step_crashing_gunship(e, dt)
                continue
            kind = e["kind"]
            if kind == "aa" and math.dist((e["x"], e["y"], e["z"]), hp) < 210.0:
                aa_active = True
            if kind in ("jeep", "tanker") and e.get("v", 0.0) > 0.0:
                e["z"] += e["v"] * dt
                e["x"] = FS.corridor_x(e["z"]) + e.get("xo", 0.0)
                e["y"] = FS.surface_y(e["x"], e["z"])
                e["yaw"] = FS.corridor_yaw(e["z"])
            elif kind == "gunship":
                if e["ucilev"]:
                    self._update_ucilev(e, dt, hp)
                    if self.shootdown < 0.0:
                        self._ucilev_combat(e, hp)
                    continue
                else:
                    ox, oy, oz = e["off"]
                    e["x"] += (hp[0] + ox + math.sin(self.t * 0.75 + e["key_i"]) * 10.0 - e["x"]) * min(1.0, dt * 1.1)
                    e["y"] += (hp[1] + oy - e["y"]) * min(1.0, dt * 1.1)
                    e["z"] += (hp[2] + oz - e["z"]) * min(1.0, dt * 1.1)
                    e["yaw"] = R._yaw(hp[0] - e["x"], hp[2] - e["z"])
                    e["pitch"] = -5.0
                    e["roll"] = 14.0 * math.sin(self.t * 1.1 + e["key_i"])
            elif kind == "tanker":
                e["yaw"] = FS.corridor_yaw(e["z"]) if SECTIONS[self.cp][1] == "road" else 0.0
                continue
            else:
                e["yaw"] = R._yaw(hp[0] - e["x"], hp[2] - e["z"])
            if SECTIONS[self.cp][1] == "road" and e["z"] < hz - 75.0 and not e["ucilev"]:
                e["alive"] = False
                continue
            if kind in ("guard", "rpg"):
                aim_pose = dict(POSES["ready"], spine=4, lsh_p=80, rsh_p=80)
                if kind == "rpg":
                    aim_pose = dict(POSES["ready"], rsh_p=146.0, rel=58.0, lsh_p=118.0, lel=42.0)
                e["pose"] = aim_pose
            if self.t < e["next"] or self.shootdown >= 0.0:
                continue
            d = math.dist((e["x"], e["y"], e["z"]), hp)
            max_d = 185.0 if kind in ("rpg", "aa") else 210.0
            if d > max_d:
                e["next"] = self.t + 1.0
                continue
            src = (e["x"], e["y"] + (1.4 if kind in ("guard", "rpg") else 1.8), e["z"])
            if self.world is not None and not self.world.los3d(src, (hp[0], hp[1] + 1.0, hp[2])):
                e["next"] = self.t + 0.4
                continue
            if kind == "aa":
                # AA trucks alternate dramatic flak tracer streams & seeker missiles
                if e.get("rk_tele"):
                    if not self._can_launch_rocket(src, air_launched=False, min_dz=48.0, kind="sam"):
                        e["tele"] = 0.0
                        e["rk_tele"] = False
                        e["next"] = self.t + 1.0
                    elif self.t >= e["tele"]:
                        e["tele"] = 0.0
                        e["rk_tele"] = False
                        self._fire_rocket(src, air_launched=False, telegraphed=True, kind="sam")
                        e["next"] = self.t + 4.4 + self.rng.random() * 1.6
                    continue
                if (e.get("burst", 0) <= 0 and e.get("tele", 0.0) <= 0.0
                        and self._can_launch_rocket(src, air_launched=False, kind="sam") and self.rng.random() < 0.42):
                    e["tele"] = self.t + ROCKET_TELE_S
                    e["rk_tele"] = True
                    e["next"] = self.t + ROCKET_TELE_S
                    self._snd("missile_warn")
                    continue
            if kind == "rpg" or (kind == "gunship" and (
                    e.get("rk_tele") or (e.get("burst", 0) <= 0 and e.get("tele", 0.0) <= 0.0
                                         and self.rng.random() < (0.48 if e.get("phase", 1) >= 2 else 0.34)))):
                air_src = (kind == "gunship")
                rk_kind = "sam" if air_src else "rpg"
                min_dz = (32.0 if air_src else 42.0) if e.get("rk_tele") else None
                if not self._can_launch_rocket(src, air_launched=air_src, min_dz=min_dz, kind=rk_kind):
                    e["tele"] = 0.0
                    e["rk_tele"] = False
                    e["next"] = self.t + 1.0
                    continue
                if not e.get("rk_tele"):
                    e["tele"] = self.t + ROCKET_TELE_S
                    e["rk_tele"] = True
                    e["next"] = self.t + ROCKET_TELE_S
                    if rk_kind == "sam":
                        self._snd("missile_warn")
                elif self.t >= e["tele"]:
                    e["tele"] = 0.0
                    e["rk_tele"] = False
                    self._fire_rocket(src, air_launched=air_src, telegraphed=True, kind=rk_kind)
                    if e.get("ucilev") and e.get("phase", 1) >= 2:
                        e["salvo_at"] = self.t + 0.48
                        e["next"] = self.t + 3.8 + self.rng.random() * 1.0
                    else:
                        e["next"] = self.t + (5.2 if kind == "rpg" else 4.6) + self.rng.random() * 1.6
                continue
            if shooters >= 5 and e.get("burst", 0) <= 0:
                e["next"] = self.t + 0.5
                continue
            shooters += 1
            if e.get("burst", 0) <= 0 and e.get("tele", 0.0) <= 0.0:
                e["tele"] = self.t + 0.35
                e["next"] = self.t + 0.35
                continue
            if e.get("burst", 0) <= 0:
                e["tele"] = 0.0
                if e.get("ucilev"):
                    e["burst"] = 8 if e.get("phase", 1) >= 2 else 6
                else:
                    e["burst"] = 5 if kind in ("gunship", "aa") else 3
            e["burst"] -= 1
            dmg = {"guard": 1.3, "jeep": 1.8, "aa": 2.2, "gunship": 2.5}.get(kind, 1.3)
            acc = clamp(0.42 - d * 0.0018, 0.12, 0.40)
            hit = self.rng.random() < acc
            speed = 135.0 if kind == "gunship" else 118.0
            dur = clamp(d / speed, 0.10, 1.15)
            end = (hp[0] + (0.0 if hit else self.rng.uniform(-4.5, 4.5)),
                   hp[1] + (0.8 if hit else self.rng.uniform(-2.0, 2.5)),
                   hp[2] + (HELI_V * dur if SECTIONS[self.cp][1] == "road" else 0.0)
                   + (0.0 if hit else self.rng.uniform(-4.5, 4.5)))
            self.bullets.append(dict(
                t0=self.t, dur=dur, start=src, end=end, hit=hit,
                dmg=dmg, src=(e["x"], e["z"]), heavy=(kind == "gunship"),
                flak=(kind == "aa"),
            ))
            self.flashes.append((self.t, src))
            self._snd("guard_shot", self._pan(src[0], src[2]), d)
            if e["burst"] > 0:
                e["next"] = self.t + (0.10 if kind in ("gunship", "aa") else 0.13)
            else:
                e["next"] = self.t + (1.7 if kind in ("gunship", "aa") else 2.2) + self.rng.random() * 1.2

        # Atmospheric mid-air AA flak airbursts popping near Maru's corridor when AA or Ucilev is active
        if (aa_active or self.cp in (1, 2, 4)) and self.shootdown < 0.0 and self.t >= self._next_flak:
            self._next_flak = self.t + self.rng.uniform(0.65, 1.45 if aa_active else 2.2)
            hyaw = self.mount_yaw() if SECTIONS[self.cp][1] == "road" else self._heli_yaw()
            fw = R._fwd(hyaw, 0.0)
            rg = R._right(hyaw)
            side = self.rng.choice((-1.0, 1.0)) * self.rng.uniform(10.0, 26.0)
            ahead = self.rng.uniform(18.0, 56.0)
            by = max(6.0, hp[1] + self.rng.uniform(-5.0, 7.0))
            bpos = (hp[0] + fw[0] * ahead + rg[0] * side, by, hp[2] + fw[2] * ahead + rg[2] * side)
            self.flak_bursts.append((self.t, bpos, self.rng.randrange(6)))
            del self.flak_bursts[:-18]
            _, _, shk_s = _settings_fx()
            self.shake = min(1.0, self.shake + 0.08 * shk_s)
            self._snd("flak_pop", self._pan(bpos[0], bpos[2]), math.dist(hp, bpos))

    _UCILEV_NEXT = {
        "dive": (2.4, "stalk"),
        "stalk": (3.4, "spotlight_sweep"),
        "spotlight_sweep": (3.2, "sam_hover"),
        "sam_hover": (2.6, "stalk"),
        "strafe_arc": (3.4, "pod_salvo"),
        "pod_salvo": (3.0, "canyon_pass"),
        "canyon_pass": (3.0, "strafe_arc"),
        "close_duel": (3.0, "cliff_feint"),
        "cliff_feint": (2.8, "ram_pass"),
        "ram_pass": (2.6, "close_duel"),
    }

    def _update_ucilev(self, e, dt, hp):
        e["maneuver_t"] = e.get("maneuver_t", 0.0) + dt
        mt = e["maneuver_t"]
        phase = e.get("phase", 1)
        man = e.get("maneuver", "dive")
        hy_u = self._heli_yaw()
        _, _, shk_s = _settings_fx()

        if man == "stagger" and mt >= 1.35:
            nxt = "pod_salvo" if phase == 2 else "close_duel"
            e["maneuver"], e["maneuver_t"] = nxt, 0.0
            e["maneuver_id"] = e.get("maneuver_id", 0) + 1
            mt, man = 0.0, nxt
        elif man == "climax":
            if mt >= 1.45 and not self.kill_shot and self.shootdown < 0.0:
                self._ucilev_kill_shot()
        elif man in self._UCILEV_NEXT:
            dur_m, nxt = self._UCILEV_NEXT[man]
            if mt >= dur_m:
                e["maneuver"], e["maneuver_t"] = nxt, 0.0
                e["maneuver_id"] = e.get("maneuver_id", 0) + 1
                mt, man = 0.0, nxt

        if man == "dive":
            du = clamp(mt / 2.4, 0.0, 1.0)
            de = du * du * (3.0 - 2.0 * du)
            rel_b = 26.0 + 30.0 * de
            dist_u = 104.0 - 56.0 * de
            dy = 24.0 * (1.0 - de) + 4.0 * de
            t_pitch = -22.0 * (1.0 - de) - 6.0 * de
            t_roll = 34.0 * (1.0 - de) + 12.0 * de
            lerp_rate = 14.0
            if du > 0.50 and e.get("pass_snd_t", -9.0) < 0.0:
                e["pass_snd_t"] = self.t
                self._snd("rotor_pass", self._pan(e["x"], e["z"]))
            if e.get("light_on"):
                self._glare = max(self._glare, 0.65 * math.sin(du * math.pi))
        elif man == "stagger":
            rel_b, dist_u, dy = 68.0, 52.0, 6.0
            t_pitch = 8.0 + 10.0 * math.cos(mt * 5.0)
            t_roll = -46.0 * math.sin(mt * 4.2)
            lerp_rate = 3.5
        elif man == "climax":
            if mt < 1.35:
                rel_b, dist_u, dy = 74.0, 44.0, -3.0
                t_pitch, t_roll = -20.0, -48.0 * math.sin(mt * 5.0)
                lerp_rate = 3.8
            else:
                rel_b, dist_u, dy = 48.0, 30.0, 1.5
                t_pitch, t_roll = -8.0, 26.0
                lerp_rate = 7.5
        elif man == "stalk":
            rel_b = 58.0 + 26.0 * math.sin(mt * 1.4)
            dist_u = 46.0 + 8.0 * math.cos(mt * 1.1)
            dy = 4.0 + 3.0 * math.sin(mt * 1.8)
            t_pitch, t_roll = -8.0 - 3.0 * math.cos(mt * 1.4), 24.0 * math.cos(mt * 1.4)
            lerp_rate = 4.5
        elif man == "spotlight_sweep":
            rel_b = 54.0 + 14.0 * math.sin(mt * 0.9)
            dist_u = 38.0 + 4.0 * math.cos(mt * 1.0)
            dy = 2.5 + 1.5 * math.sin(mt * 1.2)
            t_pitch, t_roll = -5.0, 14.0 * math.cos(mt * 0.9)
            lerp_rate = 4.2
        elif man == "sam_hover":
            rel_b = 52.0 + 12.0 * math.sin(mt * 0.8)
            dist_u, dy = 56.0, 8.0
            t_pitch, t_roll = 6.0, 10.0 * math.cos(mt)
            lerp_rate = 3.8
        elif man == "strafe_arc":
            rel_b = 64.0 + 34.0 * math.sin(mt * 1.5)
            dist_u = 44.0 + 10.0 * math.cos(mt * 1.3)
            dy = 3.5 + 4.5 * math.sin(mt * 2.0)
            t_pitch, t_roll = -11.0, 34.0 * math.cos(mt * 1.5)
            lerp_rate = 4.8
        elif man == "pod_salvo":
            rel_b = 54.0 + 16.0 * math.sin(mt * 1.0)
            dist_u, dy = 52.0, 7.5
            t_pitch, t_roll = 4.0, 18.0 * math.cos(mt)
            lerp_rate = 4.0
        elif man == "canyon_pass":
            u_p = clamp(mt / 3.0, 0.0, 1.0)
            rel_b = 22.0 + 94.0 * u_p
            dist_u = 27.0 + 14.0 * abs(u_p - 0.5) * 2.0
            dy = 0.5 + 3.0 * math.sin(u_p * math.pi)
            t_pitch, t_roll = -14.0, 44.0
            lerp_rate = 6.5
            if 0.34 <= u_p <= 0.66 and self.t - e.get("pass_snd_t", -9.0) > 2.2:
                e["pass_snd_t"] = self.t
                self._snd("rotor_pass", self._pan(e["x"], e["z"]))
                self.shake = min(1.2, self.shake + 0.22 * shk_s)
                self._evade_roll = clamp(self._evade_roll - 12.0, -16.0, 16.0)
                self._evade_y = clamp(self._evade_y - 1.5, -2.4, 2.4)
        elif man == "close_duel":
            rel_b = 62.0 + 32.0 * math.sin(mt * 1.85)
            dist_u = 36.0 + 7.0 * math.cos(mt * 1.6)
            dy = 2.5 + 4.0 * math.sin(mt * 2.2)
            t_pitch, t_roll = -12.0, 38.0 * math.cos(mt * 1.85)
            lerp_rate = 5.4
        elif man == "cliff_feint":
            u_c = clamp(mt / 2.8, 0.0, 1.0)
            rel_b = 48.0 + 20.0 * math.sin(mt * 1.4)
            dist_u = 46.0
            dy = 2.0 + 10.5 * math.sin(u_c * math.pi)
            t_pitch = 10.0 * math.cos(u_c * math.pi)
            t_roll = -36.0 * math.sin(u_c * math.tau)
            lerp_rate = 4.6
        else:  # "ram_pass"
            u_r = clamp(mt / 2.6, 0.0, 1.0)
            rel_b = 112.0 - 88.0 * u_r
            dist_u = 26.5 + 12.0 * abs(u_r - 0.5) * 2.0
            dy = -2.5 + 2.5 * math.cos(mt * 2.0)
            t_pitch, t_roll = -15.0, -44.0
            lerp_rate = 6.8
            if 0.34 <= u_r <= 0.66 and self.t - e.get("pass_snd_t", -9.0) > 2.2:
                e["pass_snd_t"] = self.t
                self._snd("rotor_pass", self._pan(e["x"], e["z"]))
                self.shake = min(1.2, self.shake + 0.24 * shk_s)
                self._evade_roll = clamp(self._evade_roll + 13.0, -16.0, 16.0)
                self._evade_y = clamp(self._evade_y + 1.4, -2.4, 2.4)

        wb = math.radians(hy_u + rel_b)
        tgt_rx = math.sin(wb) * dist_u
        tgt_rz = math.cos(wb) * dist_u
        tgt_ry = max(dy, (FS.surface_y(hp[0] + tgt_rx, hp[2] + tgt_rz) + 12.5) - hp[1])
        k_p = min(1.0, dt * lerp_rate)
        e["rx"] = e.get("rx", tgt_rx) + (tgt_rx - e.get("rx", tgt_rx)) * k_p
        e["ry"] = e.get("ry", tgt_ry) + (tgt_ry - e.get("ry", tgt_ry)) * k_p
        e["rz"] = e.get("rz", tgt_rz) + (tgt_rz - e.get("rz", tgt_rz)) * k_p
        e["x"] = hp[0] + e["rx"]
        e["z"] = hp[2] + e["rz"]
        e["y"] = max(hp[1] + e["ry"], FS.surface_y(e["x"], e["z"]) + 12.0)
        e["yaw"] = R._yaw(hp[0] - e["x"], hp[2] - e["z"])
        e["pitch"] = e.get("pitch", -6.0) + (t_pitch - e.get("pitch", -6.0)) * min(1.0, dt * 6.0)
        e["roll"] = e.get("roll", 0.0) + (t_roll - e.get("roll", 0.0)) * min(1.0, dt * 6.0)

        if phase >= 2 and self.t - e.get("smoke_t", -9.0) >= (0.045 if phase >= 3 else 0.065):
            e["smoke_t"] = self.t
            self.smoke_puffs.append(dict(
                x=e["x"] + self.rng.uniform(-0.7, 0.7), y=e["y"] + 1.5,
                z=e["z"] + self.rng.uniform(-0.7, 0.7),
                vx=self.rng.uniform(-1.0, 1.0), vy=1.4, vz=UCILEV_V * 0.25,
                born=self.t, dur=2.0 if phase >= 3 else 1.8,
                r0=0.72 if phase >= 3 else 0.65, r1=2.9 if phase >= 3 else 2.4,
                alpha=182 if phase >= 3 else 168, warm=3 if phase >= 3 else 2,
                seed=self.rng.randrange(6),
            ))
            del self.smoke_puffs[:-64]

        if e.get("salvo_at", -9.0) > 0.0 and self.t >= e["salvo_at"] and self.shootdown < 0.0:
            e["salvo_at"] = -9.0
            spod = e.pop("salvo_pod", None)
            if spod is None or e.get("subs", {}).get(spod, 0.0) > 0.0:
                loc = UCILEV_ANCHORS[spod] if spod in UCILEV_ANCHORS else (2.2, 1.2, 0.0)
                src_s = CS._xf(loc, (e["x"], e["y"], e["z"]), e["yaw"], e["pitch"], e["roll"])
                self._fire_rocket(src_s, air_launched=True, telegraphed=True, kind="sam", bypass_dz=True)

    def _ucilev_combat(self, e, hp):
        man = e.get("maneuver", "dive")
        phase = e.get("phase", 1)
        if man in ("stagger", "climax") or (man == "dive" and e.get("maneuver_t", 0.0) < 1.1):
            e["rk_tele"] = False
            e["tele"] = 0.0
            return
        if e.get("rk_tele"):
            if self.t >= e["tele"]:
                e["rk_tele"] = False
                e["tele"] = 0.0
                e["maneuver_fired_rk"] = e.get("maneuver_id", 0)
                pos_u = (e["x"], e["y"], e["z"])
                subs = e.get("subs", {})
                if phase == 2:
                    intact = [p for p in ("pod_l", "pod_r") if subs.get(p, 0.0) > 0.0]
                    if intact:
                        src0 = CS._xf(UCILEV_ANCHORS[intact[0]], pos_u, e["yaw"], e["pitch"], e["roll"])
                        self._fire_rocket(src0, air_launched=True, telegraphed=True, kind="sam", bypass_dz=True)
                        if len(intact) >= 2:
                            e["salvo_at"] = self.t + 0.45
                            e["salvo_pod"] = intact[1]
                else:
                    src0 = CS._xf((0.0, 0.48, 2.2), pos_u, e["yaw"], e["pitch"], e["roll"])
                    self._fire_rocket(src0, air_launched=True, telegraphed=True, kind="sam", bypass_dz=True)
                e["next"] = self.t + 0.8
            return
        if man in ("sam_hover", "pod_salvo", "cliff_feint") and e.get("maneuver_fired_rk") != e.get("maneuver_id"):
            if phase == 1 or (phase == 2 and any(e.get("subs", {}).get(p, 0.0) > 0.0 for p in ("pod_l", "pod_r"))):
                e["rk_tele"] = True
                e["tele"] = self.t + ROCKET_TELE_S
                e["burst"] = 0
                self._snd("missile_warn")
                return
        if self.t < e["next"]:
            return
        if e.get("burst", 0) <= 0 and e.get("tele", 0.0) <= 0.0:
            e["tele"] = self.t + 0.30
            e["next"] = self.t + 0.30
            return
        if e.get("burst", 0) <= 0:
            e["tele"] = 0.0
            e["burst"] = 7 if phase >= 3 else (8 if (phase == 2 or man == "spotlight_sweep") else 6)
        e["burst"] -= 1
        src = CS._xf((0.0, 0.62, 5.10), (e["x"], e["y"], e["z"]), e["yaw"], e["pitch"], e["roll"])
        d = math.dist(src, hp)
        dmg = 2.0 if phase >= 3 else (2.5 if phase == 2 else 2.2)
        acc = clamp(0.44 - d * 0.0018, 0.16, 0.42)
        hit = self.rng.random() < acc
        dur = clamp(d / 138.0, 0.10, 1.10)
        vh = self._heli_vel()
        end = (
            hp[0] + vh[0] * dur + (0.0 if hit else self.rng.uniform(-4.0, 4.0)),
            hp[1] + 0.8 + vh[1] * dur + (0.0 if hit else self.rng.uniform(-1.8, 2.2)),
            hp[2] + vh[2] * dur + (0.0 if hit else self.rng.uniform(-4.0, 4.0)),
        )
        self.bullets.append(dict(
            t0=self.t, dur=dur, start=src, end=end, hit=hit,
            dmg=dmg, src=(e["x"], e["z"]), heavy=True, flak=False,
        ))
        self.flashes.append((self.t, src))
        self._snd("guard_shot", self._pan(src[0], src[2]), d)
        if e["burst"] > 0:
            e["next"] = self.t + (0.085 if phase >= 3 else 0.095)
        else:
            e["next"] = self.t + (1.20 if phase >= 3 else 1.25)

    def _step_crashing_gunship(self, e, dt):
        st = e.get("state", "crashing")
        if st == "crashing":
            e["vy"] -= 11.2 * dt
            e["x"] += e["vx"] * dt
            e["y"] += e["vy"] * dt
            e["z"] += e["vz"] * dt
            e["yaw"] = (e["yaw"] + 310.0 * dt) % 360.0
            e["pitch"] = clamp(e.get("pitch", -5.0) - 24.0 * dt, -38.0, 12.0)
            e["roll"] = clamp(e.get("roll", 0.0) + (46.0 if e["vx"] >= 0 else -46.0) * dt, -76.0, 76.0)
            e["smoke_acc"] += 22.0 * dt
            while e["smoke_acc"] >= 1.0:
                e["smoke_acc"] -= 1.0
                self.smoke_puffs.append(dict(
                    x=e["x"] + self.rng.uniform(-0.8, 0.8), y=e["y"] + 1.0,
                    z=e["z"] + self.rng.uniform(-0.8, 0.8),
                    vx=self.rng.uniform(-1.2, 1.2), vy=2.0, vz=e["vz"] * 0.25,
                    born=self.t, dur=2.8, r0=0.65, r1=2.6, alpha=172, warm=3,
                    seed=self.rng.randrange(6),
                ))
            gy = 0.0 if SECTIONS[self.cp][1] == "estate" else FS.surface_y(e["x"], e["z"])
            if e["y"] <= gy + 0.95 and e["vy"] < 0.0:
                e["y"] = gy + 0.95
                if e["impact_t"] is None:
                    e["impact_t"] = self.t
                    e["cooked_off"] = True
                    self.veh_fx.trigger(
                        "gunship", (e["x"], gy, e["z"]),
                        yaw=e["yaw"], pitch=e["pitch"], roll=e["roll"],
                        vel=(e["vx"], 0.0, e["vz"]), seed=e["seed"] + 5,
                        tag=id(e), follow=True, floor_fn=self._floor,
                        on_cookoff=self._veh_cookoff,
                    )
                self._snd("crash", self._pan(e["x"], e["z"]))
                self._snd("barrel_boom", self._pan(e["x"], e["z"]),
                          math.dist((e["x"], e["y"], e["z"]), self._heli_pos()))
                if e["bounces"] == 0:
                    e["bounces"] = 1
                    e["vy"] = 3.8
                    e["vx"] *= 0.55
                    e["vz"] *= 0.45
                else:
                    e["state"] = "skidding"
                    e["vy"] = 0.0
        elif st == "skidding":
            e["x"] += e["vx"] * dt
            e["z"] += e["vz"] * dt
            e["vx"] *= math.exp(-3.6 * dt)
            e["vz"] *= math.exp(-3.6 * dt)
            gy = 0.0 if SECTIONS[self.cp][1] == "estate" else FS.surface_y(e["x"], e["z"])
            e["y"] = gy + 0.95
            e["roll"] += ((82.0 if e["roll"] >= 0 else -82.0) - e["roll"]) * min(1.0, dt * 6.0)
            self.veh_fx.sync_pose(id(e), (e["x"], gy, e["z"]), e["yaw"], e["pitch"], e["roll"])
            if math.hypot(e["vx"], e["vz"]) < 0.7:
                e["state"] = "crashed"
        elif st == "crashed":
            gy = 0.0 if SECTIONS[self.cp][1] == "estate" else FS.surface_y(e["x"], e["z"])
            self.veh_fx.sync_pose(id(e), (e["x"], gy, e["z"]), e["yaw"], e["pitch"], e["roll"])

    def _bullets_update(self, dt):
        keep = []
        for b in self.bullets:
            if self.t < b["t0"] + b["dur"]:
                keep.append(b)
                continue
            if b["hit"]:
                self.hurt_hull(b["dmg"], b["src"])
        self.bullets = keep

    def _fx_step(self, dt):
        for fl in self.flare_fx:
            fl["vy"] -= 9.8 * dt
            fl["vx"] *= math.exp(-1.2 * dt)
            fl["vz"] *= math.exp(-1.2 * dt)
            p = fl["pos"]
            fl["pos"] = (p[0] + fl["vx"] * dt, max(0.2, p[1] + fl["vy"] * dt), p[2] + fl["vz"] * dt)
            if self.t - fl["last_p"] >= 0.045:
                fl["last_p"] = self.t
                fl["trail"] = (fl["trail"] + [(fl["pos"][0], fl["pos"][1], fl["pos"][2],
                                                self.t, self.rng.randrange(6))])[-18:]
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
            gy = 0.0 if SECTIONS[self.cp][1] == "estate" else FS.surface_y(d["x"], d["z"])
            if d["y"] <= gy + 0.05 and d["vy"] < 0.0:
                d["y"] = gy + 0.05
                if d["bounces"] == 0 and d["vy"] < -2.0:
                    d["bounces"] = 1
                    d["vy"] *= -0.32
                    d["vx"] *= 0.45
                    d["vz"] *= 0.45
                else:
                    d["vx"] = d["vy"] = d["vz"] = d["vrx"] = d["vry"] = 0.0
            keep_deb.append(d)
        self.debris = keep_deb
        hp_b = self._heli_pos()
        sill_y = hp_b[1] + 0.59
        for br in self.brass:
            br["vy"] -= 9.8 * dt
            br["x"] += br["vx"] * dt
            br["y"] += br["vy"] * dt
            br["z"] += br["vz"] * dt
            if br["y"] <= sill_y and br["vy"] < 0.0 and math.hypot(br["x"] - hp_b[0], br["z"] - hp_b[2]) < 1.35:
                br["y"] = sill_y
                br["vy"] *= -0.28
                br["vx"] *= 0.55
                br["vz"] *= 0.55
            br["ry"] = (br["ry"] + br["vry"] * dt) % 360.0
        self.brass = [br for br in self.brass if self.t - br["t0"] < 0.75]
        for pf in self.smoke_puffs:
            pf["x"] += pf["vx"] * dt
            pf["y"] += pf["vy"] * dt
            pf["z"] += pf["vz"] * dt
            pf["vx"] *= math.exp(-1.4 * dt)
            pf["vz"] *= math.exp(-1.4 * dt)

    def _rockets_update(self, dt):
        hp = self._heli_pos()
        vh = self._heli_vel()
        tgt_heli = (hp[0], hp[1] + 0.9, hp[2])
        flare_on = self.t - self.flare_at < FLARE_S
        on_road = (SECTIONS[self.cp][1] == "road")
        for rk in self.rockets:
            if not rk["alive"]:
                continue
            p = rk["p"]
            age = self.t - rk["t0"]
            r_kind = rk.get("kind", "sam" if rk.get("air") else "rpg")
            phase = rk.get("phase", "cruise")
            v_cruise = float(rk.get("cruise_speed", ROCKET_SAM_V if r_kind == "sam" else ROCKET_RPG_V))

            # Active flare decoy takeover
            if flare_on and not rk["unstoppable"] and self.flare_fx and phase in ("boost", "cruise"):
                phase = rk["phase"] = "decoyed"

            if phase == "decoyed":
                if not self.flare_fx:
                    phase = rk["phase"] = "ballistic"
                else:
                    if rk.get("decoy") is None or rk["decoy"] not in self.flare_fx:
                        rk["decoy"] = min(self.flare_fx, key=lambda fl: math.dist(p, fl["pos"]))
                    rk["decoy_t"] = rk.get("decoy_t", 0.0) + dt
                    tgt = rk["decoy"]["pos"]
                    dx, dy, dz = tgt[0] - p[0], tgt[1] - p[1], tgt[2] - p[2]
                    d_fl = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
                    rk["dir"] = self._rotate_dir_bounded(
                        rk["dir"], (dx / d_fl, dy / d_fl, dz / d_fl), math.radians(84.0) * dt
                    )
                    rk["speed"] = v_cruise
                    step = rk["speed"] * dt
                    rk["p"] = (p[0] + rk["dir"][0] * step, p[1] + rk["dir"][1] * step, p[2] + rk["dir"][2] * step)
                    rk["vel"] = (rk["dir"][0] * rk["speed"], rk["dir"][1] * rk["speed"], rk["dir"][2] * rk["speed"])
                    if not rk["trail"] or math.dist(rk["trail"][-1], rk["p"]) >= 0.6:
                        rk["trail"] = (rk["trail"] + [rk["p"]])[-32:]
                    if self.t - rk.get("last_puff", -9.0) >= 0.026:
                        rk["last_puff"] = self.t
                        tail_p = (p[0] - rk["dir"][0] * 0.9, p[1] - rk["dir"][1] * 0.9, p[2] - rk["dir"][2] * 0.9)
                        rk["puffs"] = (rk["puffs"] + [(tail_p[0], tail_p[1], tail_p[2],
                                                       self.t, self.rng.randrange(6))])[-32:]
                    if d_fl < 3.5 or rk["decoy_t"] > 1.6:
                        rk["alive"] = False
                        self._spawn_boom(rk["p"], 3.2, rk.get("id_seed", 3), "rocket", n_deb=9)
                        self._snd("barrel_boom", self._pan(p[0], p[2]), d_fl)
                    continue

            dx, dy, dz = tgt_heli[0] - p[0], tgt_heli[1] - p[1], tgt_heli[2] - p[2]
            d = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
            to_heli = (dx / d, dy / d, dz / d)

            # Check transition into physical doorway flyby ("ballistic") on close miss or aft pass
            if phase != "ballistic" and not rk["unstoppable"] and age > 0.35:
                dot_fwd = to_heli[0] * rk["dir"][0] + to_heli[1] * rk["dir"][1] + to_heli[2] * rk["dir"][2]
                if (d < 10.0 and dot_fwd < -0.08) or (on_road and dot_fwd < -0.22 and d > 7.5):
                    phase = rk["phase"] = "ballistic"
                    rk["ballistic_t"] = 0.0
                    if not rk.get("flyby_snd"):
                        rk["flyby_snd"] = True
                        self._snd("rocket", self._pan(p[0], p[2]), max(2.5, d))

            if phase == "boost":
                boost_dur = 0.32 if r_kind == "sam" else 0.45
                u_b = clamp(age / boost_dur, 0.0, 1.0)
                v_now = ROCKET_BOOST_V + (v_cruise - ROCKET_BOOST_V) * (u_b * u_b)
                rk["speed"] = v_now
                aim_pt = self._rocket_lead_point(p, tgt_heli, vh, v_cruise)
                ax, ay, az = aim_pt[0] - p[0], aim_pt[1] - p[1], aim_pt[2] - p[2]
                ad = math.sqrt(ax * ax + ay * ay + az * az) or 1.0
                want_dir = (ax / ad, ay / ad, az / ad)
                if rk["unstoppable"]:
                    rk["dir"] = want_dir
                elif r_kind == "sam":
                    rk["dir"] = self._rotate_dir_bounded(
                        rk["dir"], want_dir, math.radians(SAM_TURN_DEG_S * 0.65) * dt
                    )
                else:
                    rk["dir"] = self._rotate_dir_bounded(
                        rk["dir"], rk.get("lead_dir", want_dir), math.radians(32.0) * dt
                    )
                if age >= boost_dur:
                    rk["phase"] = "cruise"
            elif phase == "cruise":
                rk["speed"] = v_cruise
                aim_pt = self._rocket_lead_point(p, tgt_heli, vh, v_cruise)
                ax, ay, az = aim_pt[0] - p[0], aim_pt[1] - p[1], aim_pt[2] - p[2]
                ad = math.sqrt(ax * ax + ay * ay + az * az) or 1.0
                want_dir = (ax / ad, ay / ad, az / ad)
                if rk["unstoppable"]:
                    rk["dir"] = want_dir
                elif r_kind == "sam":
                    rk["dir"] = self._rotate_dir_bounded(
                        rk["dir"], want_dir, math.radians(SAM_TURN_DEG_S) * dt
                    )
                else:
                    # Stage 2 RPG: semi-ballistic along lead vector with subtle spiral motor wobble & drop
                    steered = self._rotate_dir_bounded(
                        rk["dir"], want_dir, math.radians(24.0) * dt
                    )
                    wob = 0.014 * math.sin(age * 16.0 + rk.get("id_seed", 1))
                    nx = steered[0] + wob
                    ny = steered[1] - 0.025 * dt
                    nz = steered[2] - wob * 0.5
                    nm = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
                    rk["dir"] = (nx / nm, ny / nm, nz / nm)
            else:
                # "ballistic" doorway flyby: streak past on tangent vector for 1.2 s
                rk["ballistic_t"] = rk.get("ballistic_t", 0.0) + dt
                rk["speed"] = v_cruise
                nx, ny, nz = rk["dir"][0], rk["dir"][1] - 0.04 * dt, rk["dir"][2]
                nm = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
                rk["dir"] = (nx / nm, ny / nm, nz / nm)

            v_step = rk.get("speed", v_cruise)
            step = (min(d, v_step * dt) if rk["unstoppable"] else v_step * dt)
            rk["p"] = (p[0] + rk["dir"][0] * step, p[1] + rk["dir"][1] * step, p[2] + rk["dir"][2] * step)
            rk["vel"] = (rk["dir"][0] * v_step, rk["dir"][1] * v_step, rk["dir"][2] * v_step)
            if not rk["trail"] or math.dist(rk["trail"][-1], rk["p"]) >= 0.6:
                rk["trail"] = (rk["trail"] + [rk["p"]])[-32:]
            if self.t - rk.get("last_puff", -9.0) >= 0.026:
                rk["last_puff"] = self.t
                tail_p = (p[0] - rk["dir"][0] * 0.9, p[1] - rk["dir"][1] * 0.9, p[2] - rk["dir"][2] * 0.9)
                rk["puffs"] = (rk["puffs"] + [(tail_p[0], tail_p[1], tail_p[2],
                                               self.t, self.rng.randrange(6))])[-32:]
            if self.world is not None and not self.world.los3d(p, rk["p"]):
                rk["alive"] = False
                self._spawn_boom(p, 3.0, rk.get("id_seed", 5), "rocket", n_deb=8)
                continue
            if phase == "ballistic":
                if rk.get("ballistic_t", 0.0) >= 1.2 or age > 10.0:
                    rk["alive"] = False
                    self._spawn_boom(rk["p"], 2.8, rk.get("id_seed", 6), "rocket", n_deb=6)
                continue
            d_new = math.dist(rk["p"], tgt_heli)
            if d_new < 2.8 or age > 10.0:
                rk["alive"] = False
                if rk["unstoppable"]:
                    self._spawn_boom(rk["p"], 4.4, rk.get("id_seed", 9), "tail", n_deb=14)
                    self._begin_crash()
                elif d_new < 2.8:
                    self._spawn_boom(rk["p"], 3.4, rk.get("id_seed", 7), "rocket", n_deb=10)
                    self.hurt_hull(ROCKET_DMG, p)
        self.rockets = [rk for rk in self.rockets if rk["alive"]]

    def _chase_update(self, dt):
        if SECTIONS[self.cp][1] != "road" or self.cp >= 4 or self.r_down >= 0.0:
            self.escape = 0.0
            return
        if self._threats() > 0:
            self.rdist = min(220.0, self.rdist + 1.5 * dt)
        else:
            self.rdist = max(44.0, self.rdist - 3.6 * dt)
        if self.rdist > ESCAPE_R:
            self.escape += dt
            if self.escape >= ESCAPE_S:
                self.dying = True
                self.death_t = 0.0
                self.death_msg = "RETARDOVICI GOT AWAY  -  AGAIN FROM THE SECTION"
                self.firing = False
        else:
            self.escape = max(0.0, self.escape - dt * 2.0)

    def _section_update(self):
        name, kind, z0, z1, dur = SECTIONS[self.cp]
        if self.cp == 0:
            aa_left = any(e["alive"] and e["kind"] == "aa" for e in self.targets)
            if self.handoff_t < 0.0 and self.sec_t >= 6.5 and not aa_left:
                self.handoff_t = self.t
                self.firing = False
                self.say("MARU", "Lawn's clear - banking north! He's making for the boulevard!", 2.8)
            if self.handoff_t >= 0.0 and self.t - self.handoff_t >= HANDOFF_S:
                self._advance_section(1)
            return
        if self.cp == 2 and self.sec_t > 14.0 and "roof" not in self._said:
            self._said.add("roof")
            self.say("MARU", "That's the roof. ...Keep shooting.", 3.0)
        if self.cp == 3:
            if self.r_down >= 0.0:
                if not self.r_boom and self.t - self.r_down > 2.2:
                    self.r_boom = True
                    rp = self.retardovici_pos()
                    if rp is not None:
                        self._spawn_boom(rp, 5.6, 102, "heli_ground", n_deb=18)
                        self._snd("barrel_boom", 0.0, 50.0)
                if self.t - self.r_down > 3.2:
                    self._advance_section(4)
            elif self.sec_t >= dur and self.r_down < 0.0:
                self.dying = True
                self.death_t = 0.0
                self.death_msg = "HE CROSSED THE RIDGE  -  AGAIN FROM ROUTE 12"
                return
            if self.sec_t > 18.0 and "where" not in self._said:
                self._said.add("where")
                self.say("MARU", "This is where they died, isn't it?", 3.2)
            return
        if self.cp == 4:
            u = self.ucilev
            cp_el = self.sec_t - getattr(self, "_ucilev_cp_sec_t", 0.0)
            if self.shootdown < 0.0 and not self.kill_shot:
                if u is not None and u.get("climax_t", -1.0) < 0.0 and cp_el > 82.0:
                    self._on_ucilev_subsys_break(u, "turbine")
                elif u is None and cp_el > 84.0:
                    self._ucilev_kill_shot()
            if self.shootdown >= 0.0 and self.t - self.shootdown > 2.2:
                self.finish("win")
            return
        if self.sec_t >= dur:
            self._advance_section(self.cp + 1)

    def _ucilev_kill_shot(self):
        self.kill_shot = True
        u = self.ucilev
        if u is not None:
            src = CS._xf((0.0, 0.48, 2.2), (u["x"], u["y"], u["z"]),
                         u.get("yaw", 0.0), u.get("pitch", -4.0), u.get("roll", 0.0))
        else:
            src = self._heli_pos()
        hp = self._heli_pos()
        tgt_0 = self._rocket_lead_point(src, hp, self._heli_vel(), ROCKET_SAM_V)
        dx, dy, dz = tgt_0[0] - src[0], tgt_0[1] - src[1], tgt_0[2] - src[2]
        d = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        ld = (dx / d, dy / d, dz / d)
        self.rockets.append(dict(
            p=src, t0=self.t, alive=True, unstoppable=True, trail=[src],
            puffs=[], last_puff=-9.0, dir=ld, lead_dir=ld,
            vel=(ld[0] * ROCKET_BOOST_V, ld[1] * ROCKET_BOOST_V, ld[2] * ROCKET_BOOST_V),
            speed=ROCKET_BOOST_V, cruise_speed=ROCKET_SAM_V,
            id_seed=99, decoy=None, decoy_t=0.0, air=True,
            kind="sam", phase="boost", ballistic_t=0.0,
        ))
        self.backblasts.append((self.t, src, 99, "sam", True))
        self.flares = 0
        self._snd("rocket")
        self._snd("missile_warn")
        self.say("MARU", "Lock-on - flares are dry! BRACE!", 2.6)

    def _begin_crash(self):
        self.shootdown = self.t
        self.firing = False
        self.aiming = False
        self.shake = 1.8
        self._snd("crash")
        self._snd("klaxon")
        self._snd("barrel_boom", 0.0, 2.0)

    # --- input -----------------------------------------------------------------

    def handle_event(self, event):
        if not self._active or self.paused or self.dying:
            return
        if event.type == pygame.MOUSEMOTION:
            dx, dy = event.rel
            sens = SENS + (ADS_SENS - SENS) * FX._ease(self.ads)
            self._clamp_gy(dx * sens)
            self.gp = clamp(self.gp - dy * sens, *PITCH_LIM)
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
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_f:
            self.pop_flares()

    def pop_flares(self):
        if self.flares <= 0 or self.t - self.flare_at < 1.5 or self.shootdown >= 0.0:
            return False
        self.flares -= 1
        self.flare_at = self.t
        hp = self._heli_pos()
        hyaw = self._heli_yaw()
        rg = R._right(hyaw)
        fw = R._fwd(hyaw, 0.0)
        hvx, hvy, hvz = self._heli_vel()
        for side in (1.0, -0.55):
            for k in range(3):
                lat = (4.2 + k * 1.55) * (1.0 if side > 0 else 0.75)
                aft = 1.4 + k * 0.75
                self.flare_fx.append(dict(
                    pos=(hp[0] + rg[0] * side * 1.35 - fw[0] * 0.45,
                         hp[1] + 0.32,
                         hp[2] + rg[2] * side * 1.35 - fw[2] * 0.45),
                    vx=hvx * 0.86 + rg[0] * side * lat - fw[0] * aft,
                    vy=hvy * 0.5 + 1.8 + k * 0.95,
                    vz=hvz * 0.86 + rg[2] * side * lat - fw[2] * aft,
                    t0=self.t, dur=FLARE_S + 0.35 * k, last_p=-9.0, trail=[],
                ))
        self._snd("flare_pop")
        return True

    # --- draw ------------------------------------------------------------------

    def _lights(self, tm):
        out = []
        now = self.t
        # Warm interior cabin fill light so the clipped maru_gunship.glb steel & Maru stay readable at night
        hpos = self._heli_pos()
        hyaw = self._heli_yaw()
        hpitch, hroll = self._heli_tilt()
        hmat = FX.heli_matrix(hyaw, hpitch, hroll)
        _, _, _, _, info = CS.maru_gunship_parts()
        fy = float(info.get("floor_y", 0.574))
        dome_p = v_add(hpos, m_apply(hmat, (0.15, fy + 1.48, 0.55)))
        out.append({"pos": dome_p, "color": (255, 168, 92), "intensity": 0.62, "range": 4.2})
        if 0.0 <= now - self.last_fire < 0.055:
            _red, fl_red, _shk = _settings_fx()
            fk = 0.55 if fl_red else 1.0
            ex, ey, ez = self.eye()
            d = self.aim_dir()
            out.append({"pos": (ex + d[0] * 1.0, ey + d[1] * 1.0, ez + d[2] * 1.0),
                        "color": (255, 208, 128), "intensity": 2.0 * fk, "range": 9.5})
            bounce_p = v_add(hpos, m_apply(hmat, (0.68, fy + 0.95, 0.92)))
            out.append({"pos": bounce_p, "color": (255, 188, 98), "intensity": 1.15 * fk, "range": 3.8})
        if self.ucilev is not None and self.ucilev.get("alive"):
            u = self.ucilev
            upos = (u["x"], u["y"], u["z"])
            uy, up, ur = u.get("yaw", 0.0), u.get("pitch", -4.0), u.get("roll", 0.0)
            if u.get("light_on", True):
                sp_w = CS._xf(UCILEV_ANCHORS["spotlight"], upos, uy, up, ur)
                sw = 2.4 if u.get("maneuver") == "spotlight_sweep" else 1.75
                out.append({"pos": sp_w, "color": (205, 228, 255), "intensity": sw, "range": 46.0})
            else:
                tb_w = CS._xf(UCILEV_ANCHORS["turbine"], upos, uy, up, ur)
                p3 = u.get("phase", 1) >= 3
                out.append({"pos": tb_w, "color": (255, 134, 48),
                            "intensity": 2.35 if p3 else 1.75, "range": 32.0})
        for b in self.booms[-3:]:
            age = now - b[0]
            if 0.0 <= age < 2.0:
                sp = math.exp(-age * 6.0)
                glow = max(0.0, 1.0 - age / 2.0)
                out.append({"pos": (b[1][0], b[1][1] + 1.2, b[1][2]),
                            "color": (255, 198, 108) if age < 0.25 else (255, 132, 46),
                            "intensity": 2.8 * sp + 1.1 * glow, "range": 18.0 + 10.0 * sp})
        for rk in self.rockets[-2:]:
            if rk["alive"]:
                out.append({"pos": rk["p"], "color": (255, 152, 62),
                            "intensity": 1.25, "range": 12.0})
        for fl in self.flare_fx[:2]:
            out.append({"pos": fl["pos"], "color": (255, 224, 134),
                        "intensity": 1.35, "range": 18.0})
        if len(out) < 8:
            out.extend(self.veh_fx.active_lights(cap=8 - len(out)))
        if len(out) < 8:
            for e in self.targets:
                if not e["alive"] and e["kind"] in ("aa", "tanker", "gunship") and not self.veh_fx.has_tag(id(e)):
                    out.append({"pos": (e["x"], e["y"] + 1.4, e["z"]),
                                "color": (255, 136, 52), "intensity": 1.15, "range": 15.0})
                    if len(out) >= 8:
                        break
        return out[:8]

    def _road_pools(self):
        out = []
        hp = self._heli_pos()
        for e in self.targets:
            if e["kind"] == "aa" and e["alive"]:
                out.append({"pos": (hp[0], 1.2, hp[2] + 8.0), "range": 10.0,
                            "color": (196, 214, 248), "intensity": 1.1})
                out.append({"pos": (e["x"], 1.0, e["z"] + 4.0), "range": 6.0,
                            "color": (255, 224, 172), "intensity": 1.4})
            elif e["kind"] in ("jeep", "tanker") and e["alive"]:
                out.append({"pos": (e["x"], 0.8, e["z"] + 5.5), "range": 5.0,
                            "color": (255, 226, 178), "intensity": 1.3})
            elif not e["alive"] and e["kind"] in ("aa", "tanker", "jeep", "gunship"):
                out.append({"pos": (e["x"], 1.0, e["z"]), "range": 7.0,
                            "color": (255, 128, 42), "intensity": 1.5})
        return out[:10]

    def _frame(self, eye, tgt, fov, tm, roll=0.0):
        lights = self._lights(tm)
        if SECTIONS[self.cp][1] == "estate":
            r = MS.frame(eye, tgt, fov, lights=lights, t=int(tm), roll=roll)
            del _w.LAST[:]
            MS.draw_dynamic_props(r, tm, cams_alive=False, front_open=True, study_open=True)
            return r
        r = FS.frame(eye, tgt, fov, t=int(tm), lights=lights, pools=self._road_pools(), roll=roll)
        del _w.LAST[:]
        return r

    def draw(self, surface):
        if not self._active:
            return
        tm = self.t * 1000.0
        eye = self.eye()
        d = self.aim_dir()
        if self.shootdown >= 0.0:
            k = self.t - self.shootdown
            yaw = self.mount_yaw() + self.gy + k * k * 140.0
            d = R._fwd(yaw, self.gp - 14.0 * k)
        elif self.dying:
            d = R._fwd(self.mount_yaw() + self.gy + self.death_t * 160.0, self.gp - 10.0 * self.death_t)
        tgt = (eye[0] + d[0] * 10.0, eye[1] + d[1] * 10.0, eye[2] + d[2] * 10.0)
        fov = FOV + (FOV_ADS - FOV) * FX._ease(self.ads)
        red, flash_red, _shk = _settings_fx()
        hpitch, hroll = self._heli_tilt()
        cam_roll = 0.0 if red else clamp(hroll * 0.32, -7.0, 7.0)
        r = self._frame(eye, tgt, fov, tm, roll=cam_roll)

        r.light_cap = 64
        r.wetness = 0.48
        fog_d = 0.0028
        cloud_k = 0.0
        if self.handoff_t >= 0.0:
            hu = clamp((self.t - self.handoff_t) / HANDOFF_S, 0.0, 1.0)
            fog_d += 0.14 * hu
            cloud_k = clamp((hu - 0.12) / 0.88, 0.0, 1.0)
        elif self.cp == 1 and getattr(self, "_cloud_exit_t", -1.0) >= 0.0 and (self.t - self._cloud_exit_t) < 0.95:
            cloud_k = 1.0 - clamp((self.t - self._cloud_exit_t) / 0.95, 0.0, 1.0)
        if cloud_k > 0.01:
            ck = cloud_k * cloud_k * (3.0 - 2.0 * cloud_k)
            r.fog_start = max(2.3, r.fog_start * (1.0 - 0.965 * ck))
            r.fog_end = max(4.8, r.fog_end * (1.0 - 0.975 * ck))
        r.height_fog = (fog_d, 0.0, 2.2, FS.FOG)

        hpos = self._heli_pos()
        if SECTIONS[self.cp][1] == "road":
            FS.draw_horizon_ring(r, hpos)
            FS.draw_corridor_fx(r, hpos, tm)

        self._draw_targets(r, tm)
        rp = self.retardovici_pos()
        if rp is not None:
            FX.draw_vip_helicopter(
                r, rp, self.retardovici_yaw(), -6.0, self.retardovici_roll(), tm,
                tail_hp_frac=self.tail_hp / TAIL_HP_MAX, down_t=self.r_down,
                target_tail=(self.cp == 3 and self.r_down < 0.0),
            )
        FX.draw_launch_backblasts(r, self.backblasts, self.t, tm, flash_reduction=flash_red)
        for rk in self.rockets:
            FX.draw_rocket(r, rk, self.t, tm, flash_reduction=flash_red)
        self.veh_fx.draw(r, tm, flash_reduction=flash_red)
        FX.draw_booms_and_debris(r, self.booms, self.debris, self.smoke_puffs,
                                 self.brass, self.t, tm, flash_reduction=flash_red)
        FX.draw_flak_bursts(r, self.flak_bursts, self.t, tm, flash_reduction=flash_red)
        FX.draw_flares(r, self.flare_fx, self.t, tm)
        self._draw_enemy_bullets(r, tm)
        T.TrapScene._draw_fx(self, r, tm)
        hyaw = self._heli_yaw()
        flow_yaw = self.mount_yaw() if SECTIONS[self.cp][1] == "road" else hyaw
        air_spd = UCILEV_V if self.cp == 4 else (HELI_V if SECTIONS[self.cp][1] == "road" else 8.5)
        FX.draw_air_streaks(r, hpos, air_spd, self.t, reduced_motion=red, hyaw=flow_yaw)
        if self.cp == 4:
            FX.draw_gorge_snow(r, hpos, UCILEV_V, self.t, reduced_motion=red, hyaw=flow_yaw)

        hmat = FX.heli_matrix(hyaw, hpitch, hroll)
        if cloud_k > 0.01:
            # Live 3D volumetric cloud bank rushing past the open starboard bay during cp=0 -> cp=1
            for ci in range(16):
                cu = (self.t * (1.85 + (ci % 4) * 0.35) + ci * 0.163) % 1.0
                cx_l = 1.85 + (ci % 4) * 1.15
                cy_l = 0.25 + ((ci * 5) % 7) * 0.42
                cz_l = 3.8 - cu * 8.4
                cp_w = v_add(hpos, m_apply(hmat, (cx_l, cy_l, cz_l)))
                fade_c = math.sin(cu * math.pi) * cloud_k
                if fade_c > 0.04:
                    r.add_sprite(cp_w,
                                 _fx.haze((148, 162, 188), 1.45 + (ci % 3) * 0.55, int(tm),
                                          seed=860 + ci, intensity=0.55 * fade_c),
                                 layer=2)
        FX.draw_cabin_and_gun(r, self, hpos, hmat, hyaw, eye, self.mount_yaw() + self.gy,
                              self.gp, _lmg(), tm, hpitch=hpitch, hroll=hroll)

        self._rocket_markers = [
            (self._project(r, rk["p"]), math.dist(eye, rk["p"]), rk["unstoppable"], rk["p"], rk.get("phase", "cruise"))
            for rk in self.rockets if rk["alive"]
        ]
        if self.cp == 3 and self.r_down < 0.0:
            tp = self.tail_point()
            self._tail_screen = (self._project(r, tp), math.dist(eye, tp)) if tp is not None else None
        else:
            self._tail_screen = None

        self._ucilev_marks = []
        u = self.ucilev
        if self.cp == 4 and u is not None and u.get("alive") and u.get("climax_t", -1.0) < 0.0:
            upos = (u["x"], u["y"], u["z"])
            uy, up, ur = u.get("yaw", 0.0), u.get("pitch", -4.0), u.get("roll", 0.0)
            subs = u.get("subs", {})
            ph = u.get("phase", 1)
            pts = []
            if ph == 1 and subs.get("spotlight", 0.0) > 0.0:
                pts.append(("SPOTLIGHT", UCILEV_ANCHORS["spotlight"]))
            elif ph == 2:
                if subs.get("pod_l", 0.0) > 0.0:
                    pts.append(("PORT POD", UCILEV_ANCHORS["pod_l"]))
                if subs.get("pod_r", 0.0) > 0.0:
                    pts.append(("STBD POD", UCILEV_ANCHORS["pod_r"]))
            elif ph >= 3 and subs.get("turbine", 0.0) > 0.0:
                pts.append(("TURBINE", UCILEV_ANCHORS["turbine"]))
            for lbl, loc in pts:
                wp = CS._xf(loc, upos, uy, up, ur)
                self._ucilev_marks.append((self._project(r, wp), math.dist(eye, wp), lbl))

        FS.present(r, surface) if SECTIONS[self.cp][1] == "road" else MS.present(r, surface)
        if self._glare > 0.05 and not flash_red:
            ga = int(42 * clamp(self._glare, 0.0, 1.0))
            if ga > 2:
                surface.fill((ga, ga, int(ga * 1.1)), special_flags=pygame.BLEND_RGB_ADD)
        draw_vignette(surface)
        self._hud(surface)

    def _draw_enemy_bullets(self, r, tm):
        for b in self.bullets:
            u = clamp((self.t - b["t0"]) / max(1e-4, b["dur"]), 0.0, 1.0)
            a, c = b["start"], b["end"]
            u0 = max(0.0, u - (0.20 if b.get("heavy") else 0.14))
            p0 = tuple(a[i] + (c[i] - a[i]) * u0 for i in range(3))
            p1 = tuple(a[i] + (c[i] - a[i]) * u for i in range(3))
            if b.get("flak"):
                col = (255, 112, 64)
            else:
                col = (255, 186, 98) if b["heavy"] else (255, 218, 146)
            r.add_line3d(p0, p1, col, 3 if b.get("flak") else (2 if b["heavy"] else 1), layer=2)

    def _floor(self, x, z):
        if SECTIONS[self.cp][1] == "estate":
            return self.world.surface_y(x, z, self._floor_hint)
        return FS.surface_y(x, z)

    def _draw_targets(self, r, tm):
        hp = self._heli_pos()
        estate = (SECTIONS[self.cp][1] == "estate")
        for e in self.targets:
            dead = not e["alive"]
            if dead and e["kind"] not in ("gunship", "guard", "rpg", "aa", "tanker", "jeep"):
                continue
            if dead and e["kind"] in ("aa", "tanker", "jeep") and self.t - e["dead_t"] > 10.0:
                continue
            if dead and e["kind"] in ("guard", "rpg") and self.t - e["dead_t"] > 12.0:
                continue
            kind = e["kind"]
            pos = (e["x"], e["y"], e["z"])
            if kind in ("guard", "rpg"):
                gk = ("guard", "heavy" if kind == "rpg" else R.GUARD_VIEW[e["slot"] % len(R.GUARD_VIEW)])
                if dead:
                    fall = e.get("fall")
                    if fall is None:
                        ux, uz = e.get("fall_dir", (0.0, 0.0))
                        track = D.track_for(True, e["slot"])
                        bw = getattr(self.world, "box_world", None) if estate else None
                        boxes = self.world.ragdoll_boxes() if (estate and hasattr(self.world, "ragdoll_boxes")) else ()
                        fall = e["fall"] = D.Fall(
                            _w.hum(gk, True, flags=("os12",)), e.get("pose") or POSES["stand"],
                            track, pos, e["yaw"], (ux * R.GUARD_PUSH_M, uz * R.GUARD_PUSH_M), e["slot"],
                            box_world=bw, boxes=boxes, **(e.get("death_ctx") or {}),
                        )
                    self._floor_hint = min(e["y"], fall.rag.pos["pelvis"][1] + 0.5)
                    pose, root, yaw = fall.at(self.t - e["dead_t"], self._floor)
                    _w.actor(r, gk, pose, root, yaw, int(tm), seed=200 + e["slot"], amp=0.0,
                             rifle_on=fall.rifle_on, hd=True, flags=("os12",),
                             expression=fall.expression)
                    fall.draw_gun(r)
                else:
                    pose = e.get("pose") or dict(POSES["ready"])
                    _w.actor(r, gk, pose, pos, e["yaw"], int(tm), seed=200 + e["slot"],
                             amp=0.3, rifle_on=(kind == "guard"), hd=True, flags=("os12",))
                    if kind == "rpg" and not estate:
                        r.add_sprite((e["x"], e["y"] + 1.2, e["z"]),
                                     _fx.glow((255, 136, 72), 0.55, int(tm), intensity=0.65, max_px=18),
                                     layer=_fx.FX_LAYER)
                    if e.get("rk_tele"):
                        r.add_sprite((e["x"], e["y"] + 1.55, e["z"]),
                                     _fx.glow((255, 118, 48), 0.85, int(tm), core=(255, 246, 218),
                                              intensity=1.65, max_px=30), layer=_fx.FX_LAYER)
                    elif e.get("tele", 0.0) > 0.0:
                        r.add_sprite((e["x"], e["y"] + 1.5, e["z"]),
                                     _fx.glow((255, 86, 56), 0.42, int(tm), core=(255, 224, 180),
                                              intensity=1.2, max_px=22), layer=_fx.FX_LAYER)
            elif kind == "aa":
                hp_f = e["hp"] / max(1.0, float(e.get("max_hp", 120.0)))
                dy, dp, dr = self.veh_fx.hull_transform(id(e)) if dead else (0.0, 0.0, 0.0)
                has_fx = dead and self.veh_fx.has_tag(id(e))
                FX.draw_aa_truck(r, (pos[0], pos[1] + dy, pos[2]), e["yaw"], hp, not dead, tm,
                                 seed=e["seed"], hp_frac=hp_f, pitch=dp, roll=dr,
                                 turret_blown=has_fx, draw_fire=not has_fx)
                if not dead and e.get("rk_tele"):
                    r.add_sprite((e["x"], e["y"] + 2.2, e["z"]),
                                 _fx.glow((255, 128, 52), 0.95, int(tm), core=(255, 248, 222),
                                          intensity=1.7, max_px=32), layer=_fx.FX_LAYER)
            elif kind == "tanker":
                dy, dp, dr = self.veh_fx.hull_transform(id(e)) if dead else (0.0, 0.0, 0.0)
                has_fx = dead and self.veh_fx.has_tag(id(e))
                FX.draw_tanker(r, (pos[0], pos[1] + dy, pos[2]), e["yaw"], not dead, tm,
                               seed=e["seed"], pitch=dp, roll=dr, draw_fire=not has_fx)
            elif kind == "jeep":
                dy, dp, dr = self.veh_fx.hull_transform(id(e)) if dead else (0.0, 0.0, 0.0)
                CS.put(r, ("m8d_jeep", dead), lambda dd=dead: _charred_jeep() if dd else CS.jeep(),
                       (pos[0], pos[1] + dy, pos[2]), e["yaw"], dp, dr)
                if not dead:
                    for sx in (-0.62, 0.62):
                        hl = CS._xf((sx, 0.72, 2.2), pos, e["yaw"], 0.0)
                        r.add_sprite(hl, _fx.glow((255, 226, 170), 0.45, int(tm),
                                                  core=(255, 248, 228), intensity=0.85, max_px=18),
                                     layer=_fx.FX_LAYER)
                elif not self.veh_fx.has_tag(id(e)):
                    F3D.emit_fire(r, (e["x"], e["y"] + 0.8, e["z"]), tm, seed=e["seed"],
                                  size=1.15, heat=1.1, smoky=True, embers=False, bed=True, layer=2)
            else:
                FX.draw_gunship(r, e, self.t, tm,
                                draw_wreck_fire=not self.veh_fx.has_tag(id(e)),
                                player_pos=hp)
                if not dead and e.get("rk_tele") and not e.get("ucilev"):
                    r.add_sprite((e["x"], e["y"] + 1.3, e["z"]),
                                 _fx.glow((255, 128, 52), 0.95, int(tm), core=(255, 248, 222),
                                          intensity=1.7, max_px=32), layer=_fx.FX_LAYER)

    def _veil(self, alpha, col=(0, 0, 0)):
        key = (col, int(alpha) // 4 * 4)
        v = self._veil_cache.get(key)
        if v is None:
            if len(self._veil_cache) > 32:
                self._veil_cache.clear()
            v = self._veil_cache[key] = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            v.fill((*col, key[1]))
        return v

    def _hud(self, surface):
        if self.hurt > 0.02:
            surface.fill((int(68 * clamp(self.hurt, 0.0, 1.0)), 0, 0), special_flags=pygame.BLEND_RGB_ADD)
        cx, cy = WIDTH // 2, HEIGHT // 2
        if self.dying:
            k = clamp(self.death_t / 2.0, 0.0, 1.0)
            surface.blit(_get_veil(int(255 * k)), (0, 0))
            img = font_terminal.render(self.death_msg, True, (220, 200, 190))
            surface.blit(img, img.get_rect(center=(cx, cy)))
            return
        if self.shootdown >= 0.0:
            red_a = int(65 * math.sin(self.t * 14.0) ** 2)
            if red_a > 4:
                surface.fill((red_a, 6, 4), special_flags=pygame.BLEND_RGB_ADD)
            RH.callouts(surface, self)
            return

        # 1. Top-Left: Objective plate
        H.objective(surface, self._title, self.objective_text())

        # 2. Top-Center: Starboard Bay Threat Compass Tape
        comp_w, comp_h = 260, 22
        comp_x, comp_y = cx - comp_w // 2, 18
        pygame.draw.rect(surface, (14, 18, 26, 170), (comp_x, comp_y, comp_w, comp_h))
        pygame.draw.line(surface, (164, 152, 120), (cx, comp_y), (cx, comp_y + 6), 2)
        cur_rel = self._rel_yaw_cabin()
        for stop_deg, foot_dir in ((REL_YAW_LIM[0], 4), (REL_YAW_LIM[1], -4)):
            d_stop = stop_deg - cur_rel
            if abs(d_stop) <= 95.0:
                sx_stop = int(cx + (d_stop / 95.0) * (comp_w * 0.46))
                near = abs(d_stop) < 12.0
                tcol = (218, 176, 86) if near else (88, 94, 108)
                pygame.draw.line(surface, tcol, (sx_stop, comp_y + 3), (sx_stop, comp_y + comp_h - 4), 2 if near else 1)
                pygame.draw.line(surface, tcol, (sx_stop, comp_y + 3), (sx_stop + foot_dir, comp_y + 3), 1)
                pygame.draw.line(surface, tcol, (sx_stop, comp_y + comp_h - 4), (sx_stop + foot_dir, comp_y + comp_h - 4), 1)
        aim_yaw = self.mount_yaw() + self.gy
        ex, _, ez = self.eye()
        for e in self.targets:
            if e["alive"] and e["kind"] in ("aa", "gunship"):
                rel = R._wrap(R._yaw(e["x"] - ex, e["z"] - ez) - aim_yaw)
                if abs(rel) <= 95.0:
                    px = int(cx + (rel / 95.0) * (comp_w * 0.46))
                    col = H.DANGER if e.get("ucilev") else (255, 168, 62)
                    pygame.draw.circle(surface, col, (px, comp_y + 13), 4 if e.get("ucilev") else 3)
        rp = self.retardovici_pos()
        if rp is not None:
            rel = R._wrap(R._yaw(rp[0] - ex, rp[2] - ez) - aim_yaw)
            if abs(rel) <= 95.0:
                px = int(cx + (rel / 95.0) * (comp_w * 0.46))
                pygame.draw.polygon(surface, H.ACCENT, [(px, comp_y + 8), (px - 4, comp_y + 16), (px + 4, comp_y + 16)])
        for rk in self.rockets:
            if rk["alive"] and not rk["unstoppable"] and rk.get("phase") != "ballistic":
                rel = R._wrap(R._yaw(rk["p"][0] - ex, rk["p"][2] - ez) - aim_yaw)
                if abs(rel) <= 95.0:
                    px = int(cx + (rel / 95.0) * (comp_w * 0.46))
                    pygame.draw.circle(surface, H.DANGER, (px, comp_y + 13), 4)

        # 3. Top-Right: Contextual Target Card
        if SECTIONS[self.cp][1] == "road" and self.cp < 4 and self.r_down < 0.0:
            frac = clamp(1.0 - (self.rdist - 44.0) / (ESCAPE_R - 44.0), 0.0, 1.0)
            col = H.DANGER if self.rdist > ESCAPE_R * 0.8 else H.ACCENT
            H._text(surface, font_terminal_small, "RETARDOVICI  %d M" % int(self.rdist), col,
                    (WIDTH - 24, 18), "topright")
            H._bar(surface, WIDTH - 204, 38, 180, frac, col, h=6)
            if self.cp == 3:
                H._text(surface, font_terminal_small, "TAIL ROTOR", H.TEXT, (WIDTH - 24, 52), "topright")
                H._bar(surface, WIDTH - 204, 72, 180, max(0.0, self.tail_hp) / TAIL_HP_MAX, H.DANGER, h=6)
        elif self.cp == 4 and self.ucilev is not None:
            u = self.ucilev
            subs = u.get("subs", {})
            ph = u.get("phase", 1)
            climax = u.get("climax_t", -1.0) >= 0.0
            if climax:
                ulbl = "UCILEV  //  CRITICAL"
            elif ph == 1:
                ulbl = "UCILEV  //  I: SEARCHLIGHT"
            elif ph == 2:
                ulbl = "UCILEV  //  II: ROCKET PODS"
            else:
                ulbl = "UCILEV  //  III: TURBINE"
            H._text(surface, font_terminal_small, ulbl, H.DANGER, (WIDTH - 24, 18), "topright")
            seg_fracs = (
                clamp(subs.get("spotlight", 0.0) / UCILEV_SUB_HP["spotlight"], 0.0, 1.0),
                clamp((subs.get("pod_l", 0.0) + subs.get("pod_r", 0.0))
                      / (UCILEV_SUB_HP["pod_l"] + UCILEV_SUB_HP["pod_r"]), 0.0, 1.0),
                clamp(subs.get("turbine", 0.0) / UCILEV_SUB_HP["turbine"], 0.0, 1.0),
            )
            hit_flash = (self.t - u.get("sub_hit_t", -9.0)) < 0.10
            seg_w, gap_w = 66, 6
            x0 = WIDTH - 24 - (seg_w * 3 + gap_w * 2)
            for si, sf in enumerate(seg_fracs):
                sx = x0 + si * (seg_w + gap_w)
                if si + 1 < ph or (climax and si + 1 <= ph):
                    H._bar(surface, sx, 38, seg_w, 0.0, H.DIM, h=6, back=(34, 38, 44))
                elif si + 1 == ph and not climax:
                    col = (255, 224, 148) if hit_flash else H.DANGER
                    H._bar(surface, sx, 38, seg_w, sf, col, h=6, back=(58, 34, 34))
                else:
                    H._bar(surface, sx, 38, seg_w, sf, (124, 62, 58), h=6, back=(38, 30, 34))

        # 4. Upper-Mid Alert Banner
        if any(not rk["unstoppable"] and rk.get("phase") != "ballistic" for rk in self.rockets):
            H._text(surface, font_terminal_small, "ROCKET INBOUND  -  SHOOT IT OR [F]", H.DANGER,
                    (cx, 54), "midtop")
        elif self.escape > 0.0:
            H._text(surface, font_terminal_small, "HE'S PULLING AWAY - CLEAR THE GUNS", H.DANGER,
                    (cx, 54), "midtop")
        if getattr(self, "cp_toast", -9.0) >= 0.0 and 0.0 <= self.t - self.cp_toast < 2.6:
            cp_lbl = getattr(self, "_cp_toast_label", "") or "CHECKPOINT"
            cp_alpha = int(255 * clamp((2.6 - (self.t - self.cp_toast)) / 0.6, 0.0, 1.0))
            H._text(surface, font_terminal, cp_lbl, H.GOOD, (cx, 84), "midtop", cp_alpha)

        # 5. Crosshair & Damage Arcs
        ads_k = FX._ease(self.ads)
        gap = int((7.0 - 3.5 * ads_k) + 10.0 * self.heat)
        H.crosshair(surface, gap, hit_age=self.t - self.hit_mark, hit_kind=self.hit_kind,
                    tight=(ads_k > 0.45), lines=(ads_k < 0.45))
        H.damage_arcs(surface, self.dmg_marks, self.t, life=0.9)

        if getattr(self, "_tail_screen", None) is not None:
            scr, dist = self._tail_screen
            H.marker(surface, scr, dist, "TAIL ROTOR", col=H.DANGER)
        u_marks = getattr(self, "_ucilev_marks", ())
        if u_marks:
            off_drawn = False
            for scr, dist, lbl in u_marks:
                sx, sy, front = scr
                inside = front and 36 <= sx <= WIDTH - 36 and 36 <= sy <= HEIGHT - 36
                if inside or not off_drawn:
                    if not inside:
                        off_drawn = True
                    H.marker(surface, scr, dist, lbl, col=H.DANGER)

        # 6. Edge Threat Chevrons (clamped away from HUD corners)
        rk_marks = getattr(self, "_rocket_markers", ())
        eye_h = self.eye()
        f_h = R._fwd(aim_yaw, self.gp)
        rg_h = R._right(aim_yaw)
        up_h = (f_h[1] * rg_h[2] - f_h[2] * rg_h[1],
                f_h[2] * rg_h[0] - f_h[0] * rg_h[2],
                f_h[0] * rg_h[1] - f_h[1] * rg_h[0])
        for item in rk_marks:
            (sx, sy, front), dist, unstop, rpos = item[:4]
            r_phase = item[4] if len(item) > 4 else "cruise"
            if unstop or r_phase == "ballistic":
                continue
            pad_x, pad_y = 64, 84
            inside = front and pad_x <= sx <= WIDTH - pad_x and pad_y <= sy <= HEIGHT - pad_y
            col = H.DANGER if dist < 60.0 else H.ACCENT
            if inside:
                if dist < 130.0:
                    H.diamond(surface, int(sx), int(sy), col, 7, 1)
                    H._text(surface, font_terminal_small, "%dM" % int(round(dist)), col,
                            (int(sx), int(sy) + 10), "midtop")
                else:
                    H.diamond(surface, int(sx), int(sy), (168, 146, 98), 5, 1)
            else:
                if front:
                    dx, dy = sx - cx, sy - cy
                else:
                    vx, vy, vz = rpos[0] - eye_h[0], rpos[1] - eye_h[1], rpos[2] - eye_h[2]
                    dx = vx * rg_h[0] + vy * rg_h[1] + vz * rg_h[2]
                    dy = -(vx * up_h[0] + vy * up_h[1] + vz * up_h[2])
                if abs(dx) < 1e-3 and abs(dy) < 1e-3:
                    dy = 1.0
                sc = min((WIDTH / 2.0 - pad_x) / max(1e-3, abs(dx)),
                         (HEIGHT / 2.0 - pad_y) / max(1e-3, abs(dy)))
                ex_s, ey_s = int(cx + dx * sc), int(cy + dy * sc)
                H.diamond(surface, ex_s, ey_s, col, 8, 0)
                h_anc = "left" if ex_s < 110 else ("right" if ex_s > WIDTH - 110 else "mid")
                v_anc = "bottom" if ey_s > HEIGHT // 2 else "top"
                anc = ("mid" + v_anc) if h_anc == "mid" else (v_anc + h_anc)
                H._text(surface, font_terminal_small, "M %dM" % int(round(dist)), col,
                        (ex_s, ey_s - 12 if ey_s > HEIGHT // 2 else ey_s + 12), anc)

        # 7. Bottom-Left: Gunner Readout Card
        x, y = 24, HEIGHT - 102
        pygame.draw.rect(surface, (12, 14, 20, 175), (x - 8, y - 8, 268, 86))
        H._text(surface, font_terminal_small, "HULL", H.TEXT, (x, y))
        H._bar(surface, x + 70, y + 7, 180, self.hull / HULL, H.DANGER if self.hull < 35 else H.ACCENT, h=6)
        H._text(surface, font_terminal_small, "BARREL" + ("  OVERHEAT" if self.overheat else ""),
                H.DANGER if self.overheat else H.TEXT, (x, y + 24))
        H._bar(surface, x + 70, y + 31, 180, self.heat, H.DANGER if self.heat > 0.75 else H.TEXT, h=6)
        H._text(surface, font_terminal_small, "FLARES [F]", H.TEXT, (x, y + 48))
        for fi in range(FLARES):
            fcol = H.ACCENT if fi < self.flares else (48, 52, 60)
            pygame.draw.rect(surface, fcol, (x + 92 + fi * 18, y + 51, 12, 10))

        # 8. Bottom-Right: Controls Legend
        H._text(surface, font_terminal_small, "LMB FIRE   RMB ADS   [F] FLARES", (156, 152, 138),
                (WIDTH - 24, HEIGHT - 22), "bottomright", 200)

        # 9. Bottom-Center: Radio Callouts
        RH.callouts(surface, self)

    def objective_text(self):
        if self.cp == 0:
            return "Kill the AA trucks on the lawn"
        if self.cp == 3:
            return "Shred his tail rotor" if self.r_down < 0.0 else "He's going down"
        if self.cp == 4:
            if self.ucilev is not None:
                if self.ucilev.get("climax_t", -1.0) >= 0.0:
                    return "Brace!"
                ph = self.ucilev.get("phase", 1)
                if ph == 1:
                    return "Shoot out Ucilev's searchlight"
                if ph == 2:
                    return "Destroy his rocket pods"
                return "Hit his exposed turbine"
            return "Survive Ucilev"
        return "Keep Retardovici in range"


_LMG = []


def _lmg():
    if not _LMG:
        from cutscenes.m8dutyfilms import _tactical_lmg
        _LMG.append(FX.tactical_lmg_mesh(_tactical_lmg()))
    return _LMG[0]


def _charred_jeep():
    return CS._charred(CS.jeep(), 0.8)


_SCENE = None
_VEIL = [None]


def _get_veil(alpha):
    v = _VEIL[0]
    if v is None:
        v = _VEIL[0] = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    v.fill((0, 0, 0, alpha))
    return v


def scene():
    global _SCENE
    if _SCENE is None:
        _SCENE = FlightScene()
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
        STATE.m8_flight_active = False
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
