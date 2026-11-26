"""Spoiler-safe bespoke 3D & real-gameplay scenes for "THE CALL" trailer.

Fixes applied in the v2 overhaul:
  - Zero beige lamp squares / horizon dome / duplicate terrain() in cold_snow.
  - Masked white office windows & dense warm-underlit rising smoke in ember_barn.
  - Zero red chest IFF dots bleeding through soldiers' backs/chests.
  - Nocturnal moonlit mansion, hedge-clear drive path & full-body guard framing.
  - Velocity-matched strides, head tracking, recoil kicks, impact sparks & falls.
  - Dark gunmetal FFX.tactical_lmg_mesh() with reflex optic, recoil & brass.
  - Blown-open collapsed burned truck chassis (no intact hoops) & clean background.
  - Flashing red/blue strobe lightbar + ricochet sparks (no hidden sedan gunner).
  - Properly exposed gunship in terrace_wash with soldiers bracing vs downwash.
  - Real road spotlight pool & volumetric beam in gorge_pass.
  - 4 dedicated real-gameplay sequences (OTS mansion, trailer LMG, gunship ADS,
    checkpoint Fallow 12 shotgun) + 100% non-recycled Act III flash montage.
"""
from __future__ import annotations

import math
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

from core.outfits import OUTFIT_GUARD  # noqa: E402
from cutscenes import fire3d as F3D  # noqa: E402
from cutscenes import m6fx3d as FX6  # noqa: E402
from cutscenes import m6world3d as W6  # noqa: E402
from cutscenes import m7world3d as W7  # noqa: E402
from engine3d import Mesh, POSES, blend, box, pose_run  # noqa: E402
from engine3d.core import Light, m_apply, m_mul, rot_x, rot_y, rot_z, v_add  # noqa: E402
from engine3d.hold import hold_cached, hold_weapon  # noqa: E402
from engine3d.rig import solve_look  # noqa: E402

RENDER_SIZE = (960, 402)        # 2.39:1 half-res -> crisp 2x into 1920x804
BIRI = ("biribel", OUTFIT_GUARD)
BIRI_OS12 = ("os12",)
BIRI_SG = ("shotgun",)
GUARD = ("guard", "rifle")

_MODS = {}
_SURFS = {}
_VDM_CACHE = {}
_TLMG = []
_TRUCK_WRECK = []
_TOLL_SIGN = []


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def _smooth(u: float) -> float:
    u = _clamp(u)
    return u * u * (3.0 - 2.0 * u)


def _mix(a: float, b: float, u: float) -> float:
    return a + (b - a) * u


def _vmix(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def _surf(key, size):
    k = (key, size)
    s = _SURFS.get(k)
    if s is None:
        s = _SURFS[k] = pygame.Surface(size)
    return s


def _mods():
    if not _MODS:
        from cutscenes import m8duty_sets as DS
        from engine.render3d.vehicle_destruction import VehicleDestructionManager
        from game.vehicle_fx import default_vehicle_fx
        from missions.m7 import raid3d as R7
        from missions.m8.duty import flight_fx as FFX
        from missions.m8.duty import flight_set as FS
        from missions.m8.duty import mansion_set as MS
        from missions.m8.revenge import chase3d as C3
        from missions.m8.revenge import chase_set as CS
        from missions.m8.revenge import set3d as S3
        _MODS.update(DS=DS, VDM=VehicleDestructionManager, vfx=default_vehicle_fx,
                     R7=R7, FFX=FFX, FS=FS, MS=MS, C3=C3, CS=CS, S3=S3)
    return _MODS


def _tactical_lmg():
    """Dark gunmetal LMG with clear front sight + open-window reflex optic."""
    if not _TLMG:
        M = _mods()
        FFX = M["FFX"]
        try:
            from game.render3d_bridge import load_mesh_asset
            verts, faces = load_mesh_asset("tactical_lmg")
            raw = Mesh()
            raw.verts = [tuple(float(c) for c in v) for v in verts]
            raw.faces = [(tuple(f[0]), tuple(f[1]), 2, True, False) for f in faces]
            _TLMG.append(FFX.tactical_lmg_mesh(raw))
        except Exception:
            _TLMG.append(M["CS"].lmg_body())
    return _TLMG[0]


def _truck_wreck_mesh():
    """Blown-open charred cargo truck: strips intact canopy hoops & upper cab roof."""
    if not _TRUCK_WRECK:
        M = _mods()
        CS = M["CS"]
        src = CS._asset("truck_m7", scale=1.0, burned=1.0, emissive=False)
        wreck = Mesh()
        wreck.verts = list(src.verts)
        kept = []
        for f in src.faces:
            pts = [wreck.verts[i] for i in f[0]]
            ys = [p[1] for p in pts]
            zs = [p[2] for p in pts]
            # Strip intact canvas canopy hoop bars & blown-off cab roof / tailgate
            if max(ys) > 1.76:
                continue
            if min(zs) < -2.55 and max(ys) > 1.15:
                continue
            c = f[1]
            if isinstance(c, tuple) and len(c) >= 3:
                c = (int(c[0] * 0.62), int(c[1] * 0.58), int(c[2] * 0.56))
            kept.append((f[0], c, f[2], f[3], False))
        wreck.faces = kept
        # Add bent, collapsed hoop ribs & buckled cab steel so silhouette reads wrecked
        char = (24, 21, 20)
        rust = (62, 34, 24)
        wreck.add(box(1.9, 0.08, 0.08, char), m=rot_z(24.0), t=(0.18, 1.78, -0.4))
        wreck.add(box(1.7, 0.08, 0.08, rust), m=rot_z(-34.0), t=(-0.22, 1.66, -1.65))
        wreck.add(box(1.5, 0.09, 1.1, char), m=m_mul(rot_x(18.0), rot_z(-14.0)), t=(-0.12, 1.82, 1.05))
        _TRUCK_WRECK.append(wreck)
    return _TRUCK_WRECK[0]


def _held(key, base, mode="aim", flags=()):
    h = W6.hum(key, hd=False, flags=flags)
    return hold_cached(h, base, getattr(h, "_weapon", "rifle"), mode, key=("tcall2", key, mode, flags))


def _aimed(key, base, pos, yaw, target, mode="aim", flags=(), recoil_k=0.0):
    """Exact world-target IK aim with asymmetric recoil impulse + head look."""
    h = W6.hum(key, hd=False, flags=flags)
    p = dict(base)
    hy, hp = solve_look((pos[0], pos[1] + 1.56, pos[2]), target, yaw)
    p["head_y"] = hy
    p["head_p"] = hp
    p = hold_weapon(h, p, pos, yaw, getattr(h, "_weapon", "rifle"), mode=mode, aim=target)
    if recoil_k > 0.005:
        p = dict(p)
        p["spine"] = p.get("spine", 0.0) - 5.5 * recoil_k
        p["rsh_p"] = p.get("rsh_p", 0.0) + 11.0 * recoil_k
        p["lsh_p"] = p.get("lsh_p", 0.0) + 8.5 * recoil_k
        p["rifle_p"] = p.get("rifle_p", 0.0) - 9.0 * recoil_k
    return p


def _walk_pose(dist_m: float, phase_off: float = 0.0, lean: float = 4.5, stride_m: float = 1.25):
    """Velocity-coupled grounded walk cycle driven by actual distance travelled."""
    phase = (dist_m / max(0.4, stride_m)) * math.tau + phase_off
    p = pose_run(phase, lean=lean)
    # Tame jog knee-lift down to weighted tactical stride
    for k in ("lhip_p", "rhip_p", "lkn", "rkn"):
        if k in p:
            p[k] = p[k] * 0.68
    p["lift"] = 0.0
    return p


def _recoil_env(tm_ms: float, shots_ms, decay_ms: float = 170.0) -> float:
    best = 0.0
    for s in shots_ms:
        age = tm_ms - s
        if 0.0 <= age < decay_ms:
            k = math.exp(-age / (decay_ms * 0.34))
            if k > best:
                best = k
    return best


def _s3_frame(eye, tgt, fov, lights=(), t=0, size=None):
    """Route 12 dawn host WITHOUT the harsh horizontal stratus sky line."""
    S3 = _mods()["S3"]
    r = S3.renderer()[0]
    r.resize(*(size or S3.RES))
    r.set_camera(eye, tgt, fov, 0.0)
    r.fog, r.fog_start, r.fog_end = S3.FOG, S3.FOG_START, S3.FOG_END
    r.light = Light(**S3.LIGHT)
    try:
        r.set_lights(list(lights))
    except Exception:
        pass
    from cutscenes import m5fx3d as _sky
    _sky.night_sky(r, r.surface, t, S3.SKY_TOP, S3.SKY_BOT, stars=32, moon=False,
                   clouds=0, sodium=S3.SODIUM, mist=None, seed=8)
    r.begin()
    r.add_static()
    return r


_FONT3X5 = {
    "A": ("010", "101", "111", "101", "101"),
    "E": ("111", "100", "110", "100", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "O": ("010", "101", "101", "101", "010"),
    "R": ("110", "101", "110", "101", "101"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "010"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("110", "001", "010", "100", "111"),
    "-": ("000", "000", "111", "000", "000"),
    " ": ("000", "000", "000", "000", "000"),
}


def _toll_sign_mesh(gx: float, gy: float) -> Mesh:
    """Blocky 3D highway text 'ROUTE 12 - VAMA' over the blank white toll-gantry bar."""
    if not _TOLL_SIGN:
        m = Mesh()
        z_bg = 2676.02
        z_tx = 2675.92
        # Clean dark highway-green faceplate covering the placeholder white bar
        m.add(box(18.0, 2.45, 0.14, (24, 94, 54), center=(gx, gy + 9.25, z_bg), emissive=True))
        m.add(box(18.2, 0.14, 0.18, (222, 224, 214), center=(gx, gy + 10.42, z_tx), emissive=True))
        m.add(box(18.2, 0.14, 0.18, (222, 224, 214), center=(gx, gy + 8.08, z_tx), emissive=True))
        txt = "ROUTE 12 - VAMA"
        px = 0.24
        char_w = 4 * px
        total_w = len(txt) * char_w - px
        x0 = gx - total_w * 0.5
        y_top = gy + 9.85
        for ci, ch in enumerate(txt):
            rows = _FONT3X5.get(ch, _FONT3X5[" "])
            for ry, row in enumerate(rows):
                for rx, bit in enumerate(row):
                    if bit == "1":
                        m.add(box(px * 0.92, px * 0.92, 0.10, (240, 240, 232),
                                  center=(x0 + ci * char_w + rx * px, y_top - ry * px, z_tx),
                                  emissive=True))
        _TOLL_SIGN.append(m)
    return _TOLL_SIGN[0]


def _flat_dead_pose(side: bool = True) -> dict:
    """Grounded fallen pose with ankles flattened so boots never point vertically upward."""
    base = dict(POSES["dead_side" if side else "dead_back"])
    base["lank"] = 64.0
    base["rank"] = 62.0
    base["lkn"] = 18.0 if side else 12.0
    base["rkn"] = 24.0 if side else 14.0
    return base


def _open_s3_pos(S3, x: float, z: float) -> tuple[float, float, float]:
    """Snap (x, z) to the nearest open '.' asphalt tile clear of booths, barriers, cars & sandbags."""
    def _is_clear(cx: float, cz: float) -> bool:
        col0 = int((cx - S3.OX) / S3.TS)
        row0 = int((S3.OZ - cz) / S3.TS)
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if S3._glyph(col0 + dc, row0 + dr) != ".":
                    return False
        for (car_x, car_z), _yaw, _b in S3.CARS:
            if math.hypot(cx - car_x, cz - car_z) < 4.6:
                return False
        for sb_x, sb_z, _l, _d, _y in S3.SANDBAGS:
            if math.hypot(cx - sb_x, cz - sb_z) < 2.2:
                return False
        (tk_x, tk_z), _tl, _tw = S3.TANKER
        if math.hypot(cx - tk_x, cz - tk_z) < 6.0:
            return False
        return True

    if _is_clear(x, z):
        return (x, 0.0, z)
    for r_step in (1.2, 2.4, 3.6, 4.8):
        for ang_deg in range(0, 360, 30):
            tx = x + math.cos(math.radians(ang_deg)) * r_step
            tz = z + math.sin(math.radians(ang_deg)) * r_step
            if _is_clear(tx, tz):
                return (tx, 0.0, tz)
    return (x, 0.0, z)


def _present_w6(r, buf, surface):
    r.flush(buf)
    try:
        FX6.grade_cine(buf)
    except Exception:
        pass
    FX6.present_crisp(buf, surface)


def _draw_bore_flash(r, j, tm, shot_times_ms, seed=1, scale=0.72):
    """True 3D bore-aligned flash_star + tight glow at the weapon's exact muzzle."""
    if not j:
        return None
    muz = j.get("muzzle")
    rm = j.get("rifle_m")
    if muz is None or rm is None:
        return None
    C3 = _mods()["C3"]
    f_b = m_apply(rm, (0.0, 0.0, 1.0))
    rx_b = m_apply(rm, (1.0, 0.0, 0.0))
    ry_b = m_apply(rm, (0.0, 1.0, 0.0))
    tip = v_add(muz, tuple(c * 0.05 for c in f_b))
    for i, s in enumerate(shot_times_ms):
        age = tm - s
        if 0 <= age < 78:
            k = (1.0 - age / 78.0) ** 1.3
            fm = C3.flash_star(tip, f_b, rx_b, ry_b, k, seed + i * 17, scale=scale)
            W6.add(r, fm)
            r.add_sprite(v_add(tip, tuple(c * 0.08 for c in f_b)),
                         FX6.glow((255, 206, 114), 0.36, int(tm),
                                  core=(255, 252, 226), intensity=1.30 * k, max_px=34),
                         layer=FX6.FX_LAYER)
    return tip


def _emit_sparks(r, origin, tm, hit_times_ms, seed=1, n=7, dust=True):
    """Deterministic ballistic marble/metal impact sparks + dust puff on hit frames."""
    for idx, s in enumerate(hit_times_ms):
        age = (tm - s) * 0.001
        if not (0.0 <= age < 0.42):
            continue
        if dust and age < 0.38:
            u = age / 0.38
            r.add_sprite((origin[0], origin[1] + age * 0.45, origin[2]),
                         FX6.haze((196, 192, 182), 0.25 + 0.55 * u, int(tm),
                                  seed=seed + idx * 13, intensity=0.45 * (1.0 - u)),
                         layer=2)
        if age < 0.08:
            r.add_sprite(origin, FX6.glow((255, 212, 126), 0.42, int(tm),
                                          core=(255, 252, 232), intensity=1.45 * (1.0 - age / 0.08),
                                          max_px=24), layer=FX6.FX_LAYER)
        for k in range(n):
            ang = k * 2.39996 + (seed + idx * 7) * 0.71
            spd = 2.6 + (k % 4) * 1.15
            vx = math.cos(ang) * spd
            vz = math.sin(ang) * spd
            vy = 1.6 + (k % 3) * 1.1
            p1 = (origin[0] + vx * age, origin[1] + vy * age - 4.9 * age * age, origin[2] + vz * age)
            ta = max(0.0, age - 0.032)
            p0 = (origin[0] + vx * ta, origin[1] + vy * ta - 4.9 * ta * ta, origin[2] + vz * ta)
            r.add_line3d(p0, p1, (255, 216, 128), 2 if k % 2 == 0 else 1, layer=2)


def _emit_breath(r, j, yaw_deg, tm, seed=0):
    """Visible cold night breath drifting from an actor's face."""
    if not j or "head" not in j:
        return
    hd = j["head"]
    yr = math.radians(yaw_deg)
    fx, fz = math.sin(yr), math.cos(yr)
    cycle = ((tm * 0.001 + seed * 0.73) % 2.8)
    if cycle < 1.15:
        u = cycle / 1.15
        p = (hd[0] + fx * (0.14 + u * 0.48), hd[1] - 0.03 + u * 0.24, hd[2] + fz * (0.14 + u * 0.48))
        inten = 0.24 * math.sin(u * math.pi)
        r.add_sprite(p, FX6.haze((204, 218, 236), 0.10 + 0.24 * u, int(tm), seed=seed + 3, intensity=inten),
                     layer=2)


def _get_vdm(key, kind, pos, yaw, trigger_s, target_s, seed):
    M = _mods()
    dt = 1.0 / 30.0
    state = _VDM_CACHE.get(key)
    if state is None or target_s < state["t"] - 1e-4:
        vdm = M["VDM"](seed=seed, fx=M["vfx"]())
        state = {"vdm": vdm, "t": 0.0, "triggered": False}
        _VDM_CACHE[key] = state
    vdm = state["vdm"]
    while state["t"] < target_s - 1e-5:
        if not state["triggered"] and state["t"] >= trigger_s:
            vdm.trigger(kind, pos, yaw=yaw, seed=seed, tag=key)
            state["triggered"] = True
        vdm.update(dt)
        state["t"] += dt
    return vdm, state["triggered"]


# ---------------------------------------------------------------------------
# Shot-level diegetic SFX schedule (local seconds -> kind) for score.py
# ---------------------------------------------------------------------------

SHOT_EVENTS = {
    "cold_snow": [(0.0, "wind_cold"), (0.6, "steps_snow")],
    "ember_barn": [(0.0, "fire_crackle"), (0.4, "steps_snow")],
    "patrol_march": [(0.0, "wind_cold"), (0.1, "steps_patrol")],
    "dawn_road": [(0.0, "wind_cold"), (0.35, "steps_solo")],
    "estate_gate": [(0.0, "wind_cold")],
    "gp_mansion_ots": [
        (0.55, "steps_solo"),
        (1.05, "shot"), (1.20, "shot"), (1.36, "shot"), (1.42, "ricochet"),
        (2.15, "shot"), (2.35, "ricochet"),
        (2.85, "shot"), (3.00, "shot"), (3.16, "shot"), (3.22, "ricochet"),
        (3.85, "reload"),
    ],
    "city_hover": [
        (0.0, "rotor_far"), (0.9, "shot"), (1.1, "shot"),
        (2.1, "explosion"), (3.0, "shot"), (3.2, "shot"),
    ],
    "hall_breach": [
        (0.45, "shot"), (0.62, "shot"), (0.80, "shot"), (0.85, "ricochet"),
        (1.55, "shot"), (1.75, "shot"), (1.82, "ricochet"),
        (2.45, "shot"), (2.62, "shot"), (2.80, "shot"), (2.86, "ricochet"),
        (3.60, "shot"), (3.80, "ricochet"),
    ],
    "chase_dust": [
        (0.0, "engine_pass"), (0.15, "siren"),
        (0.85, "lmg"), (1.00, "lmg"), (1.06, "ricochet"),
        (2.05, "lmg"), (2.20, "lmg"), (2.28, "ricochet"),
    ],
    "gp_chase_lmg": [
        (0.0, "engine_pass"), (0.05, "siren"),
        (0.32, "lmg"), (0.44, "lmg"), (0.56, "lmg"), (0.68, "lmg"), (0.74, "ricochet"),
        (1.30, "lmg"), (1.42, "lmg"), (1.54, "lmg"), (1.66, "lmg"), (1.72, "ricochet"),
    ],
    "gp_door_gunner": (
        [(0.0, "rotor_in")]
        + [(0.75 + i * 0.11, "lmg") for i in range(11)]
        + [(2.05, "explosion"), (2.75, "cookoff")]
        + [(3.00 + i * 0.11, "lmg") for i in range(9)]
        + [(3.85, "flare"), (4.10, "flare")]
    ),
    "convoy_boom": [(0.55, "explosion"), (1.45, "cookoff"), (0.8, "fire_crackle")],
    "gp_checkpoint_ots": [
        (0.38, "shotgun"), (0.72, "pump"), (0.44, "ricochet"),
        (1.20, "shot"), (1.36, "ricochet"),
        (1.65, "shotgun"), (1.98, "pump"),
    ],
    "terrace_wash": [(0.0, "rotor_close"), (0.2, "wind_cold")],
    "rocket_streak": [(0.10, "rocket"), (0.82, "flare"), (1.02, "flare"), (1.22, "flare"), (1.62, "explosion")],
    "gorge_pass": [(0.10, "rotor_pass"), (0.0, "wind_ridge")],
    "flash_01": [(0.14, "reload"), (0.55, "shot")],
    "flash_02": [(0.08, "pump"), (0.36, "shot"), (0.52, "shot"), (0.58, "ricochet")],
    "flash_03": [(0.0, "rotor_pass"), (0.30, "explosion")],
    "flash_04": [(0.12, "shotgun"), (0.42, "pump")],
    "flash_05": [(0.0, "rotor_far"), (0.15, "wind_cold")],
    "flash_06": [(0.05, "steps_solo"), (0.12, "fire_crackle")],
    "flash_07": [(0.05, "rotor_pass"), (0.0, "wind_ridge")],
    "flash_08": [(0.0, "rotor_pass"), (0.22, "explosion")],
    "climax_surge": [
        (0.10, "lmg"), (0.22, "lmg"), (0.34, "lmg"), (0.55, "explosion"),
        (1.22, "shotgun"), (1.32, "ricochet"),
        (2.22, "lmg"), (2.34, "lmg"), (2.42, "ricochet"),
        (3.05, "explosion"), (3.72, "rocket"), (4.15, "rotor_pass"),
    ],
    "scope_breath": [(0.0, "wind_ridge"), (1.15, "exhale"), (2.95, "bolt"), (3.52, "sniper_shot")],
}


# ---------------------------------------------------------------------------
# ACT I — Atmospheric Setup + First Gameplay Hook (0.0 .. 28.8s)
# ---------------------------------------------------------------------------

def _cold_snow(surface, tm, size):
    """M6 frozen border night: soft GL sodium pools (zero beige squares) & clean horizon."""
    u = _clamp(tm / 4800.0)
    r, buf = W6.rend(*size, hdr=False)
    eye = (_mix(-11.5, -2.5, u), _mix(5.8, 3.3, u), _mix(-21.0, -9.5, u))
    tgt = (_mix(1.5, 6.5, u), 1.4, 21.0)
    r.fog, r.fog_start, r.fog_end = (10, 15, 26), 18.0, 125.0

    # Real soft sodium point lights & circular ground pools (replaces hard beige quad_xz)
    lamp_xs = (-26.0, -13.0, 0.0, 13.0, 26.0)
    lamp_lights = [
        {"pos": (lx, W6.height_at(lx, 15.4) + 4.4, 15.4), "color": (255, 192, 114),
         "intensity": 1.05, "range": 15.0}
        for lx in lamp_xs
    ]
    lamp_pools = [
        {"pos": (lx, W6.height_at(lx, 15.4) + 0.3, 15.4), "range": 7.5,
         "color": (255, 186, 108), "intensity": 1.05}
        for lx in lamp_xs
    ]
    try:
        r.set_lights(lamp_lights)
        r.set_pools(lamp_pools)
    except Exception:
        pass

    W6.cam(r, tm, eye, tgt, 52.0, hh=0.18, seed=11)
    # sodium=None removes the bright horizon semicircle artifact behind the snow ridge
    W6.night(r, buf, tm, top=(5, 8, 16), bot=(14, 21, 35), stars=65, moon=(18.0, 24.0),
             sodium=None, seed=11)
    r.begin()
    # lights=False omits the hard beige quad_xz tiles; draw clean poles + halos ourselves (once!)
    W6.terrain(r, tm, lights=False)
    poles = Mesh()
    for lx in lamp_xs:
        ly = W6.height_at(lx, 15.4)
        poles.add(box(0.08, 4.6, 0.08, (26, 28, 34), center=(lx, ly + 2.3, 15.4)))
        poles.add(box(0.18, 0.22, 0.18, FX6.SODIUM_PALE, center=(lx, ly + 4.55, 15.4), emissive=True))
    W6.add(r, poles)
    for i, lx in enumerate(lamp_xs):
        ly = W6.height_at(lx, 15.4)
        r.add_sprite((lx, ly + 4.6, 15.4), FX6.sodium_lamp(tm, seed=i, radius_m=1.7, intensity=0.72),
                     layer=FX6.FX_LAYER)

    # Widely separated lateral patrol lines so silhouettes never overlap along camera sightline
    for idx, (ox, oz, spd) in enumerate(((-5.8, 5.2, 1.30), (-0.4, 8.6, 1.28), (5.0, 11.4, 1.26))):
        dist = u * 4.8 * spd
        px = ox + dist * 0.90
        pz = oz + dist * 0.42
        py = W6.height_at(px, pz)
        base = _walk_pose(dist, phase_off=idx * 2.1, lean=5.5)
        base["head_y"] = 14.0 * math.sin(tm * 0.0014 + idx * 1.9)
        gp = _held(GUARD, base, mode="ready")
        j = W6.actor(r, GUARD, gp, (px, py, pz), 65.0 + 4.0 * math.sin(idx), tm,
                     seed=12 + idx, amp=0.14, rifle_on=True, expression="stern")
        _emit_breath(r, j, 65.0, tm, seed=12 + idx)

    W6.snow3d(r, tm, seed=11, n=165, spread=22.0, height=12.0, speed=1.9)
    _present_w6(r, buf, surface)


def _ember_barn(surface, tm, size):
    """M7 burning night fallout: charred fire-lit windows, billowing smoke, dynamic Guards."""
    u = _clamp(tm / 4800.0)
    eye = (_mix(11.6, 6.8, u), _mix(1.85, 2.20, u), _mix(-8.2, -2.0, u))
    tgt = (_mix(-2.4, -4.4, u), 2.35, 9.6)
    flick = 0.86 + 0.14 * math.sin(tm * 0.017)
    lights = [
        {"pos": (-4.5, 2.8, 9.4), "color": (255, 126, 42), "intensity": 1.75 * flick, "range": 24.0},
        {"pos": (2.6, 2.4, 11.4), "color": (255, 102, 34), "intensity": 1.45 * flick, "range": 19.0},
        {"pos": (-11.0, 2.2, 6.2), "color": (255, 118, 44), "intensity": 0.95 * flick, "range": 12.0},
    ]
    r, buf = W7.stage("burn", tm, eye, tgt, 50.0, lights=lights, hh=0.22, seed=21, size=size)

    # Mask the sterile white WIN_LIT farmhouse windows & porch bulb with charred fire-lit panes
    mask_m = Mesh()
    f_col = (int(78 * flick), int(30 * flick), int(12 * flick))
    for wx in (-15.0, -12.8, -8.4):
        mask_m.add(box(1.04, 0.94, 0.08, (22, 18, 16), center=(wx, 1.75, 6.84)))
        mask_m.add(box(0.84, 0.72, 0.04, f_col, center=(wx, 1.75, 6.79), emissive=True))
    mask_m.add(box(0.24, 0.22, 0.24, (24, 22, 22), center=(-10.0, 2.63, 6.56)))
    W6.add(r, mask_m)

    # Multi-layered fires + unmistakable billowing smoke columns (warm fire-lit base -> dense soot)
    fire_spots = ((-5.2, 0.2, 9.6), (-1.4, 0.4, 12.4), (3.4, 0.2, 10.6), (-7.4, 1.6, 11.6))
    ts = tm * 0.001

    def _plume_puff(warmth, pseed, rad_m, alpha, col):
        def _draw(s, sx, sy, scale, z):
            rad = max(5, min(92, int(rad_m * scale)))
            if rad < 4:
                return
            img = F3D.smoke_puff_surface(warmth, pseed % 6, rad, alpha, shade_col=col)
            s.blit(img, (int(sx - rad), int(sy - rad)))
        _draw.bounds_m = (rad_m * 1.15, rad_m * 1.15)
        _draw.bounds_cap_px = (184, 184)
        return _draw

    for idx, pos in enumerate(fire_spots):
        sz = 1.50 + 0.25 * (idx % 2)
        F3D.emit_fire(r, pos, tm, seed=210 + idx, size=sz, heat=1.35,
                      smoky=False, embers=True, bed=True, layer=2)
        # 8 explicit world-space rising smoke puffs per fire: bright amber underlit -> dense black soot
        for k in range(8):
            age = (ts * 0.34 + k / 8.0 + idx * 0.19) % 1.0
            rise = 1.6 + age * 8.2
            drift_x = age * age * 2.4 + math.sin(age * 5.2 + idx * 2.1) * 0.55
            drift_z = age * 0.8 + math.cos(age * 4.4 + k) * 0.35
            rad_m = (0.85 + 2.55 * (age ** 0.78)) * (0.9 + 0.18 * (idx % 2))
            fade = min(1.0, age / 0.14) * ((1.0 - age) ** 0.95)
            alpha = int(224 * fade) // 8 * 8
            if alpha >= 16:
                warmth = 4 if age < 0.24 else (2 if age < 0.48 else 0)
                col = (118, 72, 48) if age < 0.30 else ((52, 42, 42) if age < 0.58 else (16, 15, 18))
                r.add_sprite((pos[0] + drift_x, pos[1] + rise, pos[2] + drift_z),
                             _plume_puff(warmth, idx * 13 + k, rad_m, alpha, col), layer=2)

    # Armed Guards sweeping clear of the stone well & fires (velocity-matched strides, no red dots)
    g1_d = u * 3.4
    g1_pos = (-4.8 + g1_d * 0.85, 0.0, 3.6 + g1_d * 0.52)
    g1_p = _aimed(GUARD, _walk_pose(g1_d, 0.4, 6.0), g1_pos, 52.0, (2.0, 1.4, 8.0), mode="aim")
    W6.actor(r, GUARD, g1_p, g1_pos, 52.0, tm, seed=22, amp=0.14, rifle_on=True, expression="angry")

    g2_pos = (5.4, 0.0, 2.4)
    g2_base = dict(POSES["crouch"])
    g2_base["spine"] = 20.0 + 3.0 * math.sin(tm * 0.003)
    g2_p = _aimed(GUARD, g2_base, g2_pos, 325.0, (-6.0, 1.5, 9.0), mode="aim")
    W6.actor(r, GUARD, g2_p, g2_pos, 325.0, tm, seed=23, amp=0.18, rifle_on=True, expression="stern")

    g3_d = u * 3.0
    g3_pos = (5.4 - g3_d * 0.65, 0.0, 5.8 + g3_d * 0.76)
    g3_p = _aimed(GUARD, _walk_pose(g3_d, 2.2, 5.0), g3_pos, 318.0, (-3.0, 1.5, 11.0), mode="ready")
    W6.actor(r, GUARD, g3_p, g3_pos, 318.0, tm, seed=24, amp=0.14, rifle_on=True, expression="stern")

    _present_w6(r, buf, surface)


def _patrol_march(surface, tm, size):
    """Curfew Boulevard night patrol: staggered natural strides, head scans, wet lamp pools."""
    M = _mods()
    FS = M["FS"]
    u = _clamp(tm / 3600.0)
    z = 362.0
    cx = FS.corridor_x(z)
    eye = (cx - 1.8 + 1.1 * u, 1.32, z - 8.2 + 1.4 * u)
    tgt = (cx + 0.6, 1.58, z + 15.0)
    pools = [
        {"pos": (cx, 0.3, z + dz), "range": 14.0, "color": (255, 192, 114), "intensity": 1.35}
        for dz in (-2.0, 12.0, 28.0)
    ]
    r = FS.frame(eye, tgt, 46.0, t=tm, size=size, pools=pools)
    FS.draw_corridor_fx(r, eye, tm)

    # Staggered patrol formation with distinct speeds, lateral shifts & active head scanning
    squad = (
        (-3.5, 1.2, 1.38, 174.0, 0.0),
        (-1.2, 4.4, 1.28, 184.0, 1.6),
        (1.4, 2.4, 1.42, 178.0, 3.1),
        (3.7, 5.2, 1.32, 188.0, 4.4),
        (-0.2, 7.8, 1.35, 180.0, 2.3),
    )
    for idx, (ox, oz, spd, yaw, ph) in enumerate(squad):
        dist = u * 3.6 * spd
        gz = z + oz - dist
        gx = cx + ox
        base = _walk_pose(dist, phase_off=ph, lean=4.8)
        base["head_y"] = 18.0 * math.sin(tm * 0.0018 + idx * 1.7)
        base["head_p"] = 3.0 * math.sin(tm * 0.0024 + idx)
        gp = _held(GUARD, base, mode="ready")
        W6.actor(r, GUARD, gp, (gx, 0.0, gz), yaw, tm, seed=25 + idx, amp=0.14,
                 rifle_on=True, expression="stern")
    FS.present(r, surface)


def _dawn_road(surface, tm, size):
    """Route 12 before dawn: readable tractor rim light, velocity-coupled Biribel & pacing Guards."""
    M = _mods()
    S3 = M["S3"]
    u = _clamp(tm / 4800.0)
    dist = u * 6.2
    pz = -41.5 + dist
    px = S3.south_road_x(pz) - 1.15
    eye = (px - 2.3 + 0.65 * u, 1.54 + 0.12 * u, pz - 4.4)
    tgt = (px + 0.9, 1.48, pz + 17.5)
    # Warm sunrise rim lights lift Bodi's tractor and roadblock out of crushed black
    lights = [
        {"pos": (-72.5, 2.4, -23.5), "color": (255, 188, 134), "intensity": 1.15, "range": 18.0},
        {"pos": (-76.0, 2.8, -14.0), "color": (228, 178, 152), "intensity": 0.90, "range": 22.0},
    ]
    r = _s3_frame(eye, tgt, 48.0, lights=lights, t=tm, size=size)
    b_base = _walk_pose(dist, phase_off=0.2, lean=4.5)
    b_base["head_y"] = 8.0 * math.sin(tm * 0.0012)
    walk_p = _held(BIRI, b_base, mode="carry", flags=BIRI_OS12)
    W6.actor(r, BIRI, walk_p, (px, 0.0, pz), 3.0, tm, seed=31, amp=0.15,
             rifle_on=True, flags=BIRI_OS12, expression="stern")

    # Roadblock Guards placed on distinct lateral lanes (zero perspective overlap at 00:16-00:17!)
    for idx, (ox, oz, pace_amp, yaw) in enumerate(((-3.9, -18.2, 0.55, 162.0), (3.8, -15.6, -0.55, 206.0),
                                                   (1.9, -9.2, 0.0, 184.0))):
        g_shift = pace_amp * math.sin(u * math.pi)
        gx = S3.south_road_x(oz) + ox + g_shift
        if abs(pace_amp) > 0.1:
            gbase = _walk_pose(abs(pace_amp) * u * 2.2, phase_off=idx * 2.0, lean=3.5)
        else:
            gbase = dict(POSES["ready"])
            gbase["spine"] = 3.0 + 2.0 * math.sin(tm * 0.002)
        gbase["head_y"] = 20.0 * math.sin(tm * 0.0016 + idx * 2.1)
        gp = _held(GUARD, gbase, mode="ready")
        W6.actor(r, GUARD, gp, (gx, 0.0, oz), yaw, tm, seed=33 + idx, amp=0.18,
                 rifle_on=True, expression="stern")
    S3.present(r, surface)


def _estate_gate(surface, tm, size):
    """Deep nocturnal raid atmosphere: dark moonlit facade with only 5 warm lit rooms."""
    M = _mods()
    MS = M["MS"]
    u = _clamp(tm / 3600.0)
    # Centered strictly inside x in [-0.7, +0.6], clear of the x=+-3.4 hedges!
    eye = (_mix(-0.7, 0.6, u), _mix(2.05, 2.40, u), _mix(-30.5, -21.8, u))
    tgt = (0.0, _mix(3.2, 4.1, u), 4.0)
    r = MS.frame(eye, tgt, 50.0, lights=(), t=tm, size=size)
    # True 03:40 moonlight: 50% darker ambient + restrained portico/lamp pools only
    r.light = Light(direction=(-0.55, 0.42, -0.72), ambient=0.06, diffuse=0.14,
                    sky=0.02, tint=(0.44, 0.56, 0.92))
    try:
        r.set_lights([
            {"pos": (0.0, 3.0, -2.6), "color": (255, 198, 128), "intensity": 0.48, "range": 10.5},
            {"pos": (-3.4, 3.3, -22.0), "color": (255, 200, 132), "intensity": 0.44, "range": 8.5},
            {"pos": (3.4, 3.3, -22.0), "color": (255, 200, 132), "intensity": 0.44, "range": 8.5},
        ])
        r.set_pools([
            {"pos": (0.0, 5.4, -1.4), "range": 6.0, "color": (255, 198, 132), "intensity": 0.46},
            {"pos": (-3.4, 3.4, -22.0), "range": 6.0, "color": (255, 200, 132), "intensity": 0.55},
            {"pos": (3.4, 3.4, -22.0), "range": 6.0, "color": (255, 200, 132), "intensity": 0.55},
            {"pos": (-3.4, 3.4, -28.0), "range": 6.0, "color": (255, 200, 132), "intensity": 0.50},
            {"pos": (3.4, 3.4, -28.0), "range": 6.0, "color": (255, 200, 132), "intensity": 0.50},
        ])
    except Exception:
        pass
    MS.draw_dynamic_props(r, tm, front_open=False, study_open=False, terrace_open=False)

    # Black out most mansion facade & wing windows so only 5 warm rooms glow at 03:40!
    dark_wins = Mesh()
    keep_lit = {(-5.6, 6.6), (0.0, 6.6), (2.8, 6.6), (-8.4, 2.6), (5.6, 2.6)}
    for i in range(9):
        wx = -11.2 + i * 2.8
        for wy in (2.6, 6.6):
            if (abs(wx) > 1.0 or wy > 5.0) and (round(wx, 1), wy) not in keep_lit:
                dark_wins.add(box(1.26, 1.86, 0.05, (14, 20, 32), center=(wx, wy, -0.09)))
    for s in (-1, 1):
        wx0 = s * 17.0
        for i in range(3):
            dark_wins.add(box(1.26, 1.86, 0.05, (14, 20, 32), center=(wx0 - 2.6 + i * 2.6, 2.6, 2.41)))
    W6.add(r, dark_wins)

    # Full-body Guard patrols cleanly framed inside the forecourt (never sliced at bottom edge)
    g1_d = u * 3.6
    g1_p = _held(GUARD, _walk_pose(g1_d, 0.5, 4.0), mode="ready")
    W6.actor(r, GUARD, g1_p, (-6.2 + g1_d, 0.0, -11.5), 88.0, tm, seed=42, amp=0.16,
             rifle_on=True, expression="stern")
    g2_d = u * 3.2
    g2_p = _held(GUARD, _walk_pose(g2_d, 2.3, 4.0), mode="ready")
    W6.actor(r, GUARD, g2_p, (6.0 - g2_d, 0.0, -9.8), 270.0, tm, seed=43, amp=0.16,
             rifle_on=True, expression="stern")
    for idx, (gx, yaw) in enumerate(((-2.9, 174.0), (2.9, 186.0))):
        base = dict(POSES["ready"])
        base["head_y"] = 16.0 * math.sin(tm * 0.0015 + idx * 2.4)
        W6.actor(r, GUARD, _held(GUARD, base, mode="ready"), (gx, MS.GF, -1.8), yaw,
                 tm, seed=44 + idx, amp=0.18, rifle_on=True, expression="stern")

    W6.snow3d(r, tm, seed=41, n=72, spread=18.0, height=11.0, speed=1.1, col=(165, 182, 212))
    MS.present(r, surface)


# ---------------------------------------------------------------------------
# GAMEPLAY #1 — 3rd-Person Tactical OTS Breach in the Grand Hall (4.8s)
# ---------------------------------------------------------------------------

def _gp_mansion_ots(surface, tm, size):
    """True over-the-shoulder tactical shooter gameplay in Retardovici's Grand Hall."""
    M = _mods()
    MS = M["MS"]
    u = _clamp(tm / 4800.0)
    biri_shots = (1050, 1200, 1360, 2850, 3000, 3160)
    guard_shots = (2150, 2320)

    # Player steps smoothly out from left column (0..0.95s), plants to fire burst 1 (1.05..1.5s),
    # sidesteps slightly (1.6..2.6s), plants & eliminates upper balcony Guard (2.85..3.3s)
    move1 = _smooth(_clamp(u / 0.22))
    move2 = _smooth(_clamp((u - 0.34) / 0.20))
    bx = -4.2 + 1.55 * move1 + 0.65 * move2
    bz = 10.6 + 1.10 * move1 + 0.70 * move2
    bpos = (bx, MS.GF, bz)

    # Aim transitions from right stair Guard -> upper balcony Guard
    t1_pos = (2.2, MS.GF + 2.35, 20.6)
    t2_pos = (-1.6, MS.FF + 1.35, 26.8)
    aim_u = _smooth(_clamp((u - 0.44) / 0.14))
    aim_tgt = _vmix(t1_pos, t2_pos, aim_u)
    byaw = math.degrees(math.atan2(aim_tgt[0] - bx, aim_tgt[2] - bz))

    # Over-the-right-shoulder tactical camera with tight ADS pull-in & recoil punch
    rec = _recoil_env(tm, biri_shots, 185.0)
    ads_u = _smooth(_clamp((u - 0.15) / 0.12)) * (1.0 - 0.35 * _smooth(_clamp((u - 0.78) / 0.18)))
    yr = math.radians(byaw)
    fx, fz = math.sin(yr), math.cos(yr)
    rx, rz = math.cos(yr), -math.sin(yr)
    cam_back = _mix(2.55, 1.82, ads_u)
    cam_right = _mix(0.68, 0.58, ads_u)
    eye = (bx - fx * cam_back + rx * cam_right, MS.GF + 1.62 + rec * 0.045, bz - fz * cam_back + rz * cam_right)
    tgt = (aim_tgt[0], aim_tgt[1] + rec * 0.22, aim_tgt[2])
    fov = _mix(58.0, 44.0, ads_u)

    extra_l = []
    if rec > 0.25:
        extra_l.append({"pos": (bx + fx * 1.1, MS.GF + 1.5, bz + fz * 1.1),
                        "color": (255, 206, 124), "intensity": 1.55 * rec, "range": 12.0})
    r = MS.frame(eye, tgt, fov, lights=extra_l, t=tm, size=size)
    r.marble_refl = 0.34
    MS.draw_dynamic_props(r, tm, front_open=True, study_open=False, terrace_open=False)

    # Biribel with velocity-coupled footwork while moving, rock-steady planted stance while firing
    moving_k = (1.0 if (0.01 < move1 < 0.99 or 0.01 < move2 < 0.99) else 0.0)
    b_base = _walk_pose(move1 * 1.9 + move2 * 1.0, 0.0, 5.0) if moving_k else dict(POSES["aim"])
    bp = _aimed(BIRI, b_base, bpos, byaw, aim_tgt, mode="aim", flags=BIRI_OS12, recoil_k=rec)
    j_b = W6.actor(r, BIRI, bp, bpos, byaw, tm, seed=601, amp=0.10, rifle_on=True,
                   flags=BIRI_OS12, expression="angry")
    b_muz = _draw_bore_flash(r, j_b, tm, biri_shots, seed=601, scale=0.82)

    # Guard 1 on stairs: aims back -> hit flinch at 1200ms -> collapses cleanly by 1950ms
    g1_pos = (2.2, MS.GF + 1.25, 20.6)
    if tm < 1220:
        g1_p = _aimed(GUARD, POSES["crouch"], g1_pos, 204.0, (bx, MS.GF + 1.4, bz), mode="aim")
        g1_gun = True
    elif tm < 1460:
        fl = _smooth((tm - 1220.0) / 240.0)
        stagger = dict(POSES["stand"], spine=-22.0 * fl, head_p=-24.0 * fl, lsh_p=36.0 * fl, rsh_p=42.0 * fl)
        g1_p = blend(_held(GUARD, POSES["crouch"], mode="ready"), stagger, fl)
        g1_gun = True
    else:
        fk = _smooth((tm - 1460.0) / 520.0)
        g1_p = blend(dict(POSES["crouch"], spine=-20.0), _flat_dead_pose(side=True), fk)
        g1_gun = False
    W6.actor(r, GUARD, g1_p, g1_pos, 204.0, tm, seed=602, amp=0.14, rifle_on=g1_gun, expression="angry")

    # Guard 2 on upper landing: collapses sideways with flattened boots (zero boots sticking out of floor!)
    g2_pos = (-2.2, MS.FF, 26.4)
    g2_rec = _recoil_env(tm, guard_shots, 160.0)
    if tm < 3020:
        g2_p = _aimed(GUARD, POSES["aim"], g2_pos, 188.0, (bx, MS.GF + 1.4, bz), mode="aim", recoil_k=g2_rec)
        g2_gun = True
    else:
        fk2 = _smooth((tm - 3020.0) / 520.0)
        g2_p = blend(dict(POSES["crouch"], spine=32.0, head_p=24.0), _flat_dead_pose(side=True), fk2)
        g2_pos = (-2.2 - 0.35 * fk2, MS.FF, 26.4)
        g2_gun = False
    j_g2 = W6.actor(r, GUARD, g2_p, g2_pos, 188.0, tm, seed=603, amp=0.14, rifle_on=g2_gun, expression="angry")
    g2_muz = _draw_bore_flash(r, j_g2, tm, guard_shots, seed=603, scale=0.68)

    # Guard 3 flanking right gallery
    g3_pos = (4.6, MS.FF, 26.8)
    g3_p = _aimed(GUARD, POSES["crouch"], g3_pos, 212.0, (bx, MS.GF + 1.4, bz), mode="aim")
    W6.actor(r, GUARD, g3_p, g3_pos, 212.0, tm, seed=604, amp=0.14, rifle_on=True, expression="stern")

    # Crisp bore-rooted tracers + marble impact sparks
    if b_muz:
        for i, s in enumerate(biri_shots):
            age = tm - s
            if 0 <= age < 85:
                frac = age / 85.0
                end = t1_pos if i < 3 else t2_pos
                r.add_line3d(_vmix(b_muz, end, max(0.0, frac - 0.35)),
                             _vmix(b_muz, end, min(1.0, frac + 0.30)), (255, 228, 148), 2, layer=4)
    if g2_muz:
        for s in guard_shots:
            age = tm - s
            if 0 <= age < 90:
                frac = age / 90.0
                end = (-7.6, MS.GF + 1.65, 10.2)
                r.add_line3d(_vmix(g2_muz, end, max(0.0, frac - 0.32)),
                             _vmix(g2_muz, end, min(1.0, frac + 0.28)), (255, 188, 108), 2, layer=4)
    _emit_sparks(r, (2.2, MS.GF + 2.1, 20.4), tm, (1120, 1280), seed=611)
    _emit_sparks(r, (-7.5, MS.GF + 1.65, 10.2), tm, (2230, 2400), seed=612)
    _emit_sparks(r, (-1.6, MS.FF + 1.2, 26.6), tm, (2920, 3080), seed=613)
    MS.present(r, surface)


# ---------------------------------------------------------------------------
# ACT II — Two Roads Escalation + Gameplay Showcase (28.8 .. 57.6s)
# ---------------------------------------------------------------------------

def _city_hover(surface, tm, size):
    """Low dramatic Curfew Boulevard canyon sweep over stranded tram & lit wet asphalt."""
    M = _mods()
    FS, FFX = M["FS"], M["FFX"]
    u = _clamp(tm / 4800.0)
    z = _mix(105.0, 275.0, u)
    cx = FS.corridor_x(z)
    # Lower, closer banked sweep through the buildings (escapes the 'sterile high tube' feel)
    eye = (cx - 6.8 + 10.5 * math.sin(u * math.pi * 0.85), _mix(14.5, 10.8, u), z)
    tgt_z = z + 68.0
    tgt = (FS.corridor_x(tgt_z) + 1.5, 3.8, tgt_z)
    roll = -9.5 * math.sin(u * math.pi * 0.90)
    # Strong warm asphalt lamp pools down the center tram corridor
    road_pools = [
        {"pos": (FS.corridor_x(z + dz), 0.35, z + dz), "range": 17.0,
         "color": (255, 188, 112), "intensity": 1.65}
        for dz in (18.0, 44.0, 72.0, 104.0, 138.0)
    ]
    r = FS.frame(eye, tgt, 58.0, t=tm, size=size, pools=road_pools, roll=roll)
    FS.draw_corridor_fx(r, eye, tm)

    # Placed on clear stretches well away from baked barricades/trucks at z=195 and z=310 (zero clipping!)
    for idx, (tz, xo) in enumerate(((234.0, 5.6), (348.0, 5.4))):
        tx = FS.corridor_x(tz) + xo
        FFX.draw_aa_truck(r, (tx, 0.0, tz), FS.corridor_yaw(tz) + 166.0, eye, True, tm, seed=60 + idx)
    tank_z = 270.0
    FFX.draw_tanker(r, (FS.corridor_x(tank_z) - 4.2, 0.0, tank_z), FS.corridor_yaw(tank_z), True, tm, seed=65)

    # Fixed world-space AA flak burst ahead in the canyon + real moving ballistic tracer bolts (no tethered laser!)
    flak_pos = (FS.corridor_x(215.0) + 4.5, 14.5, 215.0)
    FFX.draw_flak_bursts(r, [(2.10, flak_pos, 77)], tm * 0.001, tm)
    aa1_muz = (FS.corridor_x(234.0) + 5.6, 2.85, 234.0)
    for bi, bt in enumerate((900, 1100, 1550, 1750, 3000, 3200)):
        age = tm - bt
        if 0 <= age < 260 and 234.0 > eye[2] + 18.0:
            frac = age / 260.0
            dst = (flak_pos[0] + ((bi % 3) - 1) * 2.4, flak_pos[1] + (bi % 2) * 1.8, flak_pos[2] - 12.0)
            r.add_line3d(_vmix(aa1_muz, dst, max(0.0, frac - 0.18)),
                         _vmix(aa1_muz, dst, min(1.0, frac + 0.08)), (255, 198, 96), 2, layer=2)
            if age < 75:
                r.add_sprite(aa1_muz, FX6.glow((255, 210, 120), 0.75, int(tm),
                                               core=(255, 250, 224), intensity=1.4, max_px=28),
                             layer=FX6.FX_LAYER)

    for idx, (gz, xo) in enumerate(((196.0, -4.4), (204.0, 3.0), (242.0, -5.4), (250.0, 4.8))):
        gx = FS.corridor_x(gz) + xo
        sky_tgt = (FS.corridor_x(gz - 24.0) + 3.0, 15.0, gz - 24.0)
        gp = _aimed(GUARD, POSES["crouch"], (gx, 0.0, gz), 180.0, sky_tgt, mode="aim")
        j = W6.actor(r, GUARD, gp, (gx, 0.0, gz), 180.0, tm, seed=66 + idx, amp=0.16, rifle_on=True)
        if idx in (2, 3) and gz > eye[2] + 20.0:
            shots = (920 + idx * 140, 1120 + idx * 140, 3020 + (idx - 2) * 180)
            muz = _draw_bore_flash(r, j, tm, shots, seed=66 + idx)
            if muz:
                for s in shots:
                    age = tm - s
                    if 0 <= age < 220:
                        frac = age / 220.0
                        r.add_line3d(_vmix(muz, sky_tgt, max(0.0, frac - 0.16)),
                                     _vmix(muz, sky_tgt, min(1.0, frac + 0.08)), (255, 218, 128), 2, layer=2)
    FS.present(r, surface)


def _hall_breach(surface, tm, size):
    """Rebuilt marble Grand Hall firefight: planted stances, real aim, recoil, sparks & fall."""
    M = _mods()
    MS = M["MS"]
    u = _clamp(tm / 4800.0)
    biri_shots = (450, 620, 800, 2450, 2620, 2800, 3600)
    guard_shots = (1550, 1750, 3100, 3280)

    # Biribel stays firmly planted in tactical firing stance behind left newel/column (zero gliding!)
    bpos = (-2.6, MS.GF, 13.4)
    tgt_g1 = (4.2, MS.GF + 1.32, 20.2)
    tgt_g2 = (1.5, MS.GF + 2.35, 20.8)
    tgt_g3 = (-2.4, MS.FF + 1.32, 26.8)
    if tm < 1500:
        b_tgt = tgt_g1
    elif tm < 2950:
        b_tgt = _vmix(tgt_g1, tgt_g2, _smooth((tm - 1500.0) / 380.0))
    else:
        b_tgt = _vmix(tgt_g2, tgt_g3, _smooth((tm - 2950.0) / 350.0))
    byaw = math.degrees(math.atan2(b_tgt[0] - bpos[0], b_tgt[2] - bpos[2]))

    b_rec = _recoil_env(tm, biri_shots, 175.0)
    g_rec = _recoil_env(tm, guard_shots, 165.0)
    eye = (_mix(-0.8, 0.3, u), MS.GF + 1.65 + b_rec * 0.035, _mix(8.6, 10.6, u))
    tgt = (_mix(0.6, 1.0, u), MS.GF + 2.15, _mix(20.5, 22.8, u))

    extra_l = []
    if b_rec > 0.25:
        extra_l.append({"pos": (bpos[0] + 0.8, bpos[1] + 1.5, bpos[2] + 1.0),
                        "color": (255, 206, 124), "intensity": 1.5 * b_rec, "range": 12.0})
    if g_rec > 0.25:
        extra_l.append({"pos": (1.5, MS.GF + 2.4, 20.8),
                        "color": (255, 198, 118), "intensity": 1.3 * g_rec, "range": 11.0})

    r = MS.frame(eye, tgt, 54.0, lights=extra_l, t=tm, size=size)
    r.marble_refl = 0.34
    MS.draw_dynamic_props(r, tm, front_open=True, study_open=False, terrace_open=False)

    bp = _aimed(BIRI, POSES["aim"], bpos, byaw, b_tgt, mode="aim", flags=BIRI_OS12, recoil_k=b_rec)
    j_b = W6.actor(r, BIRI, bp, bpos, byaw, tm, seed=61, amp=0.10, rifle_on=True,
                   flags=BIRI_OS12, expression="angry")
    b_muz = _draw_bore_flash(r, j_b, tm, biri_shots, seed=610, scale=0.80)

    # Guard 1 (right floor): takes hit at 680ms -> flinches backward -> collapses realistically by 1400ms
    g1_pos = (4.2, MS.GF, 20.2)
    if tm < 680:
        g1_p = _aimed(GUARD, POSES["aim"], g1_pos, 218.0, (bpos[0], MS.GF + 1.4, bpos[2]), mode="aim")
        g1_gun = True
    elif tm < 960:
        fk = _smooth((tm - 680.0) / 280.0)
        g1_p = blend(POSES["aim"], dict(POSES["stand"], spine=-26.0, head_p=-24.0, rsh_p=46.0, lsh_p=34.0), fk)
        g1_gun = True
    else:
        fk = _smooth((tm - 960.0) / 480.0)
        g1_p = blend(dict(POSES["crouch"], spine=-22.0), _flat_dead_pose(side=True), fk)
        g1_pos = (4.2 + fk * 0.45, MS.GF, 20.2 + fk * 0.65)
        g1_gun = False
    W6.actor(r, GUARD, g1_p, g1_pos, 218.0, tm, seed=62, amp=0.12, rifle_on=g1_gun, expression="angry")

    # Guard 2 (staircase): advances up 3 steps smoothly -> plants -> fires back -> hit flinch at 2680ms!
    stair_u = _smooth(_clamp((tm - 900.0) / 1100.0))
    g2_z = _mix(20.0, 21.8, stair_u)
    g2_y = MS.GF + (MS.FF - MS.GF) * _clamp((g2_z - MS.STAIR_Z0) / (MS.STAIR_Z1 - MS.STAIR_Z0))
    g2_pos = (1.5, g2_y, g2_z)
    g2_yaw = math.degrees(math.atan2(bpos[0] - g2_pos[0], bpos[2] - g2_pos[2]))
    if tm < 2680:
        g2_base = _walk_pose(stair_u * 2.1, 1.1, 6.0) if 0.02 < stair_u < 0.98 else dict(POSES["crouch"])
        g2_p = _aimed(GUARD, g2_base, g2_pos, g2_yaw, (bpos[0], MS.GF + 1.4, bpos[2]), mode="aim", recoil_k=g_rec)
        g2_gun = True
    else:
        fk2 = _smooth((tm - 2680.0) / 520.0)
        g2_p = blend(dict(POSES["crouch"], spine=-18.0), _flat_dead_pose(side=True), fk2)
        g2_gun = False
    j_g2 = W6.actor(r, GUARD, g2_p, g2_pos, g2_yaw, tm, seed=63, amp=0.12, rifle_on=g2_gun, expression="angry")
    g_muz2 = _draw_bore_flash(r, j_g2, tm, (1550, 1750), seed=620, scale=0.70)

    # Guard 3 & 4 on upper balcony returning fire
    g3_pos = (-2.4, MS.FF, 26.8)
    g3_p = _aimed(GUARD, POSES["aim"], g3_pos, 182.0, (bpos[0], MS.GF + 1.4, bpos[2]), mode="aim", recoil_k=g_rec)
    j_g3 = W6.actor(r, GUARD, g3_p, g3_pos, 182.0, tm, seed=64, amp=0.14, rifle_on=True, expression="angry")
    g_muz3 = _draw_bore_flash(r, j_g3, tm, (3100, 3280), seed=630, scale=0.70)
    g4_pos = (3.8, MS.FF, 26.8)
    W6.actor(r, GUARD, _aimed(GUARD, POSES["aim"], g4_pos, 206.0, (bpos[0], MS.GF + 1.4, bpos[2]), mode="aim"),
             g4_pos, 206.0, tm, seed=65, amp=0.14, rifle_on=True, expression="stern")

    # Crossing tracers + marble impact sparks on pillar/stairs
    if b_muz:
        for i, s in enumerate(biri_shots):
            age = tm - s
            if 0 <= age < 90:
                frac = age / 90.0
                end = tgt_g1 if i < 3 else (tgt_g2 if i < 6 else tgt_g3)
                r.add_line3d(_vmix(b_muz, end, max(0.0, frac - 0.32)),
                             _vmix(b_muz, end, min(1.0, frac + 0.28)), (255, 228, 152), 2, layer=4)
    for g_muz, s_list in ((g_muz2, (1550, 1750)), (g_muz3, (3100, 3280))):
        if g_muz:
            for s in s_list:
                age = tm - s
                if 0 <= age < 95:
                    frac = age / 95.0
                    end = (-3.2, MS.GF + 1.45, 13.8)
                    r.add_line3d(_vmix(g_muz, end, max(0.0, frac - 0.30)),
                                 _vmix(g_muz, end, min(1.0, frac + 0.25)), (255, 194, 114), 2, layer=4)

    _emit_sparks(r, (4.1, MS.GF + 1.35, 20.0), tm, (680, 860), seed=640)
    _emit_sparks(r, (-3.1, MS.GF + 1.38, 13.8), tm, (1620, 1820, 3180), seed=641)
    _emit_sparks(r, (1.5, g2_y + 1.25, g2_z - 0.1), tm, (2540, 2680), seed=642)
    MS.present(r, surface)


def _strobe_lights(CS, jpos, jyaw, tm):
    """Animated alternating red/blue police lightbar strobes splashing onto hood & road."""
    phase = (tm % 420) / 420.0
    # Crisp double-flash police strobe pattern (red on 0..0.44, blue on 0.50..0.94)
    red_on = (0.00 <= phase < 0.14) or (0.22 <= phase < 0.38)
    blue_on = (0.50 <= phase < 0.64) or (0.72 <= phase < 0.88)
    p_blue = CS._xf((-0.30, 1.66, -0.10), jpos, jyaw, 0.0, 0.0)
    p_red = CS._xf((0.30, 1.66, -0.10), jpos, jyaw, 0.0, 0.0)
    lights = []
    if red_on:
        lights.append({"pos": (p_red[0], p_red[1] + 0.12, p_red[2] + 0.35),
                       "color": (255, 42, 34), "intensity": 2.1, "range": 12.5})
    if blue_on:
        lights.append({"pos": (p_blue[0], p_blue[1] + 0.12, p_blue[2] + 0.35),
                       "color": (46, 128, 255), "intensity": 2.2, "range": 12.5})
    return lights, (p_red, red_on), (p_blue, blue_on)


def _chase_dust(surface, tm, size):
    """Dawn Route 12 pursuit: scenic farmland stretch, flashing red/blue strobes, ricochets."""
    M = _mods()
    CS = M["CS"]
    u = _clamp(tm / 3600.0)
    # Scenic curve between burned farmstead & village (z=145..245: varied verge trees, no orchard loop/puddle)
    z = _mix(145.0, 245.0, u)
    jz = z - 7.5
    jx = CS.road_x(jz) + 2.2 + 0.65 * math.sin(u * math.tau)
    jy = CS.surface_y(jx, jz)
    jyaw = CS.road_yaw(jz) + 5.0 * math.cos(u * math.tau)
    lz = z + 12.0
    lx = CS.road_x(lz) - 1.1
    ly = CS.surface_y(lx, lz)
    lyaw = CS.road_yaw(lz)

    eye = (jx - 4.8 + 1.2 * math.sin(u * math.pi), jy + 1.48, jz + 6.6)
    tgt = (jx + 0.25, jy + 1.15, jz - 1.4)

    s_lights, (p_red, red_on), (p_blue, blue_on) = _strobe_lights(CS, (jx, jy, jz), jyaw, tm)
    lights = [{"pos": (jx, jy + 1.05, jz + 2.8), "color": (255, 218, 164), "intensity": 0.65, "range": 16.0}] + s_lights

    r = CS.frame(eye, tgt, 54.0, t=tm, size=size, look="dawn", lights=lights)
    CS.put_wheeled(r, "jeep", (jx, jy, jz), yaw=jyaw, odo=jz)
    CS.put_wheeled(r, "tractor", (lx, ly, lz), yaw=lyaw, odo=lz)

    # Flashing strobe flares on the roof lightbar!
    if red_on:
        r.add_sprite(p_red, FX6.glow((255, 48, 38), 0.95, int(tm), core=(255, 224, 216),
                                     intensity=1.95, max_px=52), layer=FX6.FX_LAYER)
    if blue_on:
        r.add_sprite(p_blue, FX6.glow((54, 138, 255), 0.95, int(tm), core=(224, 240, 255),
                                      intensity=2.05, max_px=52), layer=FX6.FX_LAYER)

    # Incoming hero LMG tracers striking the jeep's armored ram-bar & hood (NO hidden interior gunner!)
    hood_hit = CS._xf((0.22, 0.92, 1.55), (jx, jy, jz), jyaw, 0.0, 0.0)
    bumper_hit = CS._xf((-0.45, 0.64, 2.15), (jx, jy, jz), jyaw, 0.0, 0.0)
    src_pt = (lx, ly + 1.85, lz - 3.2)
    for s_ms, hit_p in ((850, hood_hit), (1000, bumper_hit), (2050, hood_hit), (2200, bumper_hit)):
        age = tm - s_ms
        if 0 <= age < 95:
            frac = age / 95.0
            r.add_line3d(_vmix(src_pt, hit_p, max(0.0, frac - 0.35)),
                         _vmix(src_pt, hit_p, min(1.0, frac + 0.25)), (255, 226, 144), 2, layer=4)
    _emit_sparks(r, hood_hit, tm, (910, 2110), seed=710, n=8, dust=False)
    _emit_sparks(r, bumper_hit, tm, (1060, 2260), seed=711, n=8, dust=False)

    # Headlights + billowing tire dust
    for hx in (-0.72, 0.72):
        hp = CS._xf((hx, 0.92, 2.08), (jx, jy, jz), jyaw, 0.0, 0.0)
        r.add_sprite(hp, FX6.glow((255, 232, 186), 0.72, int(tm), intensity=1.35, max_px=36),
                     layer=FX6.FX_LAYER)
    for k in range(10):
        dz = jz - 2.3 - k * 2.1
        dx = CS.road_x(dz) + 2.0 + math.sin(k * 1.7 + tm * 0.006) * 1.0
        r.add_sprite((dx, CS.surface_y(dx, dz) + 0.50 + k * 0.16, dz),
                     FX6.haze((188, 160, 128), 1.35 + k * 0.26, int(tm), seed=70 + k, intensity=0.32),
                     layer=2)
    CS.present(r, surface)


# ---------------------------------------------------------------------------
# GAMEPLAY #2 — Highway Hay-Trailer Pintle LMG Turret Defense (2.4s)
# ---------------------------------------------------------------------------

def _gp_chase_lmg(surface, tm, size):
    """Over-the-pintle-LMG gameplay defending the speeding hay trailer on Route 12."""
    M = _mods()
    CS, C3 = M["CS"], M["C3"]
    u = _clamp(tm / 2400.0)
    ts = tm * 0.001
    tz = _mix(198.0, 254.0, u)
    tx = CS.road_x(tz) - 0.6
    ty = CS.surface_y(tx, tz)
    tyaw = CS.road_yaw(tz)

    # Pursuing strobe-lit Guard jeep reacts violently to LMG hits (swerve, chassis roll, engine smoke!)
    jz = tz - _mix(16.5, 13.0, u)
    hit1 = _smooth(_clamp((ts - 0.55) / 0.35)) * math.exp(-max(0.0, ts - 0.70) * 2.2)
    hit2 = _smooth(_clamp((ts - 1.48) / 0.30)) * math.exp(-max(0.0, ts - 1.62) * 2.0)
    swerve = 1.6 * math.sin(u * math.pi * 1.3) + 1.15 * hit1 - 1.25 * hit2
    jx = CS.road_x(jz) + swerve
    jy = CS.surface_y(jx, jz)
    jyaw = CS.road_yaw(jz) + 5.0 * math.cos(u * math.pi * 1.3) + 13.0 * hit1 - 15.0 * hit2
    jroll = -6.5 * hit1 + 7.5 * hit2

    mount = getattr(CS, "MOUNT", (0.0, -0.55))
    post_top = float(getattr(CS, "POST_TOP", 1.95))
    gun_pos = CS._xf((mount[0], post_top + 0.14, mount[1]), (tx, ty, tz), tyaw, 0.0, 0.0)

    # Exterior surface impact targets proud of the armored hood & windscreen (never occluded inside body!)
    hood_ext = CS._xf((0.22, 1.12, 1.56), (jx, jy, jz), jyaw, 0.0, jroll)
    shield_ext = CS._xf((-0.26, 1.34, 0.86), (jx, jy, jz), jyaw, 0.0, jroll)
    aim_p = hood_ext if ts < 1.15 else shield_ext
    dx, dy, dz = aim_p[0] - gun_pos[0], aim_p[1] - gun_pos[1], aim_p[2] - gun_pos[2]
    gy = math.degrees(math.atan2(dx, dz))
    gp = math.degrees(math.atan2(dy, max(1.0, math.hypot(dx, dz))))

    bursts = (320, 440, 560, 680, 1300, 1420, 1540, 1660)
    rec = _recoil_env(tm, bursts, 115.0)
    gmat = m_mul(rot_y(gy), rot_x(-(gp + rec * 1.8)))
    f_b = m_apply(gmat, (0.0, 0.0, 1.0))
    rx_b = m_apply(gmat, (1.0, 0.0, 0.0))
    ry_b = m_apply(gmat, (0.0, 1.0, 0.0))

    # Gunner camera anchored tightly over the LMG receiver with high-speed road rumble + recoil
    rumble_y = 0.025 * math.sin(ts * 32.0) + rec * 0.032
    rumble_x = 0.018 * math.cos(ts * 27.0)
    eye = (
        gun_pos[0] - f_b[0] * 0.72 + ry_b[0] * (0.24 + rumble_y) + rx_b[0] * (-0.06 + rumble_x),
        gun_pos[1] - f_b[1] * 0.72 + ry_b[1] * (0.24 + rumble_y) + rx_b[1] * (-0.06 + rumble_x),
        gun_pos[2] - f_b[2] * 0.72 + ry_b[2] * (0.24 + rumble_y) + rx_b[2] * (-0.06 + rumble_x),
    )
    tgt = (aim_p[0], aim_p[1] + rec * 0.25, aim_p[2])

    s_lights, (p_red, red_on), (p_blue, blue_on) = _strobe_lights(CS, (jx, jy, jz), jyaw, tm)
    lights = list(s_lights)
    if rec > 0.35:
        lights.append({"pos": v_add(gun_pos, tuple(c * 0.8 for c in f_b)),
                       "color": (255, 206, 120), "intensity": 1.6 * rec, "range": 10.0})

    # Tighter 48 deg FOV locks tightly onto the sparking, smoking, swerving patrol car
    r = CS.frame(eye, tgt, 48.0, t=tm, size=size, look="dawn", lights=lights)
    CS.put_wheeled(r, "trailer", (tx, ty, tz), yaw=tyaw, odo=tz)
    CS.put(r, "gp_yoke", lambda: CS.lmg_yoke(0.18),
           CS._xf((mount[0], post_top, mount[1]), (tx, ty, tz), tyaw, 0.0, 0.0), yaw=gy)
    CS.put(r, "gp_lmg", CS.lmg_body, gun_pos, yaw=gy, pitch=gp + rec * 1.8)
    CS.put_wheeled(r, "jeep", (jx, jy, jz), yaw=jyaw, odo=jz, roll=jroll)

    if red_on:
        r.add_sprite(p_red, FX6.glow((255, 48, 38), 0.90, int(tm), core=(255, 224, 216),
                                     intensity=1.9, max_px=48), layer=FX6.FX_LAYER)
    if blue_on:
        r.add_sprite(p_blue, FX6.glow((54, 138, 255), 0.90, int(tm), core=(224, 240, 255),
                                      intensity=2.0, max_px=48), layer=FX6.FX_LAYER)

    tip = v_add(gun_pos, tuple(c * 0.82 for c in f_b))
    for i, s in enumerate(bursts):
        age = tm - s
        if 0 <= age < 65:
            k = (1.0 - age / 65.0) ** 1.3
            W6.add(r, C3.flash_star(tip, f_b, rx_b, ry_b, k, 740 + i, scale=0.72))
        if 0 <= age < 110:
            frac = age / 110.0
            r.add_line3d(_vmix(tip, aim_p, max(0.05, frac - 0.30)),
                         _vmix(tip, aim_p, min(1.0, frac + 0.24)), (255, 228, 146), 2, layer=4)
    # Bright metal ricochet sparks + pierced engine hood smoke & flame licks!
    _emit_sparks(r, hood_ext, tm, (390, 510, 630, 740), seed=745, n=10, dust=False)
    _emit_sparks(r, shield_ext, tm, (1370, 1490, 1610, 1720), seed=746, n=10, dust=False)
    if ts >= 0.65:
        F3D.emit_fire(r, hood_ext, tm, seed=748, size=0.58 if ts < 1.5 else 0.85,
                      heat=1.15, smoky=True, embers=True, bed=False, layer=2)
    for k in range(8):
        dz_d = jz - 2.0 - k * 2.2
        dx_d = CS.road_x(dz_d) + math.sin(k * 1.9 + ts * 5.0) * 1.1
        r.add_sprite((dx_d, CS.surface_y(dx_d, dz_d) + 0.55 + k * 0.14, dz_d),
                     FX6.haze((186, 158, 126), 1.3 + k * 0.25, int(tm), seed=750 + k, intensity=0.28),
                     layer=2)
    CS.present(r, surface)


# ---------------------------------------------------------------------------
# GAMEPLAY #3 — First-Person Door-Gunner ADS Combat (4.8s)
# ---------------------------------------------------------------------------

def _gp_door_gunner(surface, tm, size, *, key="dg_tanker"):
    """FPV starboard door-gunner gameplay: dark gunmetal LMG, RMB ADS, recoil, brass & blast."""
    M = _mods()
    FS, FFX, R7 = M["FS"], M["FFX"], M["R7"]
    u = _clamp(tm / 4800.0)
    ts = tm * 0.001
    z = _mix(215.0, 348.0, u)
    hpos = (FS.corridor_x(z) - 6.0, 21.0 + 0.55 * math.sin(ts * 1.4), z)
    hyaw = FS.corridor_yaw(z) - 32.0
    hpitch = -4.0
    hroll = 6.0 + 2.4 * math.sin(ts * 1.1)
    hmat = FFX.heli_matrix(hyaw, hpitch, hroll)

    tank_z = 368.0
    tank_pos = (FS.corridor_x(tank_z) + 1.5, 0.0, tank_z)
    aa_z = 392.0
    aa_pos = (FS.corridor_x(aa_z) - 3.5, 0.0, aa_z)
    aim_tgt = _vmix((tank_pos[0], 1.6, tank_pos[2]), (aa_pos[0], 1.8, aa_pos[2]),
                    _smooth((u - 0.52) * 2.0))

    dx = aim_tgt[0] - hpos[0]
    dy = aim_tgt[1] - (hpos[1] + 1.1)
    dz = aim_tgt[2] - hpos[2]
    gy_world = math.degrees(math.atan2(dx, dz)) % 360.0
    gp = _clamp(math.degrees(math.atan2(dy, max(1.0, math.hypot(dx, dz)))), -52.0, -4.0)

    burst_times = [0.75 + i * 0.11 for i in range(11)] + [3.00 + i * 0.11 for i in range(9)]
    last_fire = max((bt for bt in burst_times if bt <= ts), default=-9.0)
    fire_age = ts - last_fire

    # Smooth RMB ADS pull-in before firing -> holds tight reflex sight -> relaxes after blast
    ads = _smooth(_clamp((ts - 0.35) / 0.45)) * (1.0 - 0.55 * _smooth(_clamp((ts - 3.85) / 0.55)))
    # Live heat climbs during bursts & cools between them
    shots_so_far = sum(1 for bt in burst_times if bt <= ts)
    heat = _clamp(0.12 + shots_so_far * 0.032 - max(0.0, ts - 1.95) * (0.14 if ts < 3.0 else 0.06), 0.12, 0.78)
    # Visceral recoil shake + tanker detonation shockwave jolt
    blast_jolt = 1.65 * math.exp(-(ts - 2.05) * 4.5) if ts >= 2.05 else 0.0
    recoil_shake = (0.78 * math.exp(-fire_age * 16.0) if 0.0 <= fire_age < 0.22 else 0.0) + blast_jolt
    gp_kick = gp + (1.45 * math.exp(-fire_age * 18.0) if 0.0 <= fire_age < 0.20 else 0.0)

    rel_yaw = (gy_world - hyaw) % 360.0
    stub = types.SimpleNamespace(
        t=ts, last_fire=last_fire, heat=heat, overheat=False,
        rotor=(ts * 880.0) % 360.0, flash_seed=int(ts * 30), ads=ads, hull=100.0,
        lines=(), _heli_tilt=lambda: (hpitch, hroll),
    )

    eye = FFX.gunner_eye(hpos, hmat, rel_yaw, ads, ts, recoil_shake,
                         reduced_motion=False, gp=gp_kick, gy_world=gy_world)
    fwd = R7._fwd(gy_world, gp_kick)
    tgt = (eye[0] + fwd[0] * 35.0, eye[1] + fwd[1] * 35.0, eye[2] + fwd[2] * 35.0)
    fov = _mix(64.0, 44.0, ads)

    vdm, tank_blown = _get_vdm(key, "tanker", tank_pos, FS.corridor_yaw(tank_z), 2.05, ts, 404)
    extra_l = list(vdm.active_lights(cap=4))
    if 0.0 <= fire_age < 0.06:
        extra_l.append({"pos": (eye[0] + fwd[0] * 1.4, eye[1] + fwd[1] * 1.4, eye[2] + fwd[2] * 1.4),
                        "color": (255, 206, 128), "intensity": 1.65, "range": 10.0})

    r = FS.frame(eye, tgt, fov, t=tm, size=size, lights=extra_l,
                 roll=hroll * 0.35 + blast_jolt * 1.8 * math.sin(ts * 29.0))
    FS.draw_corridor_fx(r, hpos, tm)

    dy_h, dp_h, dr_h = vdm.hull_transform(key) if tank_blown else (0.0, 0.0, 0.0)
    FFX.draw_tanker(r, (tank_pos[0], dy_h, tank_pos[2]), FS.corridor_yaw(tank_z),
                    not tank_blown, tm, seed=404, pitch=dp_h, roll=dr_h)
    FFX.draw_aa_truck(r, aa_pos, FS.corridor_yaw(aa_z) + 172.0, hpos, True, tm, seed=405)
    vdm.draw(r, tm)

    # Street Guards firing back
    for idx, (ox, gz) in enumerate(((-5.5, 344.0), (5.2, 348.0), (-4.2, 362.0), (5.8, 376.0))):
        gx = FS.corridor_x(gz) + ox
        gp_a = _aimed(GUARD, POSES["aim"], (gx, 0.0, gz), 180.0, hpos, mode="aim")
        j = W6.actor(r, GUARD, gp_a, (gx, 0.0, gz), 180.0, tm, seed=410 + idx, amp=0.18, rifle_on=True)
        g_shots = (950 + idx * 450, 2400 + idx * 380)
        g_muz = _draw_bore_flash(r, j, tm, g_shots, seed=410 + idx, scale=0.65)
        if g_muz:
            for gs in g_shots:
                age = tm - gs
                if 0 <= age < 140:
                    frac = age / 140.0
                    end = (hpos[0] + 2.5, hpos[1] - 1.5, hpos[2] + 4.0)
                    r.add_line3d(_vmix(g_muz, end, max(0.0, frac - 0.25)),
                                 _vmix(g_muz, end, min(1.0, frac + 0.25)), (255, 166, 98), 2, layer=4)

    tip, basis = FFX.draw_cabin_and_gun(r, stub, hpos, hmat, hyaw, eye, gy_world, gp_kick,
                                        _tactical_lmg(), tm, hpitch=hpitch, hroll=hroll)
    FFX.draw_air_streaks(r, hpos, 32.0, ts, reduced_motion=False, hyaw=FS.corridor_yaw(z))

    # Ejecting brass shell casings from EJECT_PORT_LOCAL on each shot!
    brass = []
    ej_w = v_add(tip, m_apply(basis, (0.06, -0.02, -0.62)))
    rg_b = m_apply(basis, (1.0, 0.0, 0.0))
    for i, bt in enumerate(burst_times):
        age = ts - bt
        if 0.0 <= age < 0.45:
            brass.append({
                "x": ej_w[0] + rg_b[0] * (1.8 * age),
                "y": ej_w[1] + 0.55 * age - 4.9 * age * age,
                "z": ej_w[2] + rg_b[2] * (1.8 * age),
                "ry": (age * 620.0 + i * 53.0) % 360.0,
            })
    if brass:
        FFX.draw_booms_and_debris(r, (), (), (), brass, ts, tm)

    # Tracers streaking cleanly from dark gunmetal LMG bore into tanker & AA truck
    for bt in burst_times:
        age = ts - bt
        if 0.0 <= age < 0.42:
            frac = age / 0.42
            r.add_line3d(_vmix(tip, aim_tgt, max(0.02, frac - 0.24)),
                         _vmix(tip, aim_tgt, min(1.0, frac + 0.08)), (255, 224, 128), 2, layer=4)
            if 0.30 <= age < 0.41:
                r.add_sprite((aim_tgt[0] + math.sin(bt * 19) * 1.2, aim_tgt[1] + 0.6,
                              aim_tgt[2] + math.cos(bt * 13) * 1.2),
                             FX6.glow((255, 214, 122), 1.35, int(tm), core=(255, 252, 230),
                                      intensity=1.6, max_px=34), layer=FX6.FX_LAYER)
    FS.present(r, surface)


def _convoy_boom(surface, tm, size, *, key="convoy_boom", trigger_s=0.55, seed=808):
    """Roadblock truck detonation -> collapsed blown-open charred wreck, clean background."""
    M = _mods()
    S3, CS = M["S3"], M["CS"]
    ts = tm * 0.001
    u = _clamp(ts / 3.6)
    # Wide-open asphalt apron (>8 m clear of CARS[1] at (-40, 10) and CARS[3] at (-30, 22))
    truck_pos = (-32.0, 0.0, 10.5)
    truck_yaw = 152.0
    vdm, blown = _get_vdm(key, "truck", truck_pos, truck_yaw, trigger_s, ts, seed)

    blast_age = max(0.0, ts - trigger_s)
    sh = 0.28 * math.exp(-blast_age * 4.5) if blown else 0.0
    eye = (truck_pos[0] + 10.2 - 1.8 * u + sh * math.sin(ts * 41.0),
           3.05 + 0.40 * u + sh * math.cos(ts * 37.0),
           truck_pos[2] + 10.8 - 2.0 * u)
    tgt = (truck_pos[0] - 0.6, 1.72, truck_pos[2] - 0.4)

    r = _s3_frame(eye, tgt, 50.0, lights=vdm.active_lights(cap=6), t=tm, size=size)
    dy, dp, dr = vdm.hull_transform(key) if blown else (0.0, 0.0, 0.0)
    if blown and blast_age >= 0.16:
        # Swap to the stripped, collapsed burned chassis (zero intact hoops!)
        CS.put(r, "truck_wreck_collapsed", _truck_wreck_mesh,
               (truck_pos[0], dy, truck_pos[2]), yaw=truck_yaw, pitch=dp, roll=dr)
        # Extra billowing dark smoke column rising out of the ruptured bed
        r.add_sprite((truck_pos[0], 2.4, truck_pos[2]),
                     F3D.emit_smoke(tm, seed=815, size_m=2.6, heat=1.35, shade_col=(44, 40, 42)), layer=2)
    else:
        CS.put(r, "truck_clean", lambda: CS._asset("truck_m7", scale=1.0, burned=0.0),
               (truck_pos[0], dy, truck_pos[2]), yaw=truck_yaw, pitch=dp, roll=dr)

    # Roadblock Guards diving & fleeing away from the blast
    guards = (
        (-5.2, -3.2, 235.0, True),
        (-4.2, 3.4, 288.0, False),
        (5.0, -2.6, 118.0, True),
        (3.8, 4.4, 62.0, False),
    )
    for idx, (ox, oz, away_yaw, dives) in enumerate(guards):
        if blast_age > 0.08:
            if dives:
                k = _smooth(min(1.0, (blast_age - 0.08) / 0.42))
                pose = blend(POSES["ready"], POSES["prone"], k)
                pos = (truck_pos[0] + ox + math.sin(math.radians(away_yaw)) * k * 1.9,
                       0.0, truck_pos[2] + oz + math.cos(math.radians(away_yaw)) * k * 1.9)
            else:
                run_d = (blast_age - 0.08) * 3.8
                pose = _held(GUARD, _walk_pose(run_d, idx * 1.4, lean=14.0, stride_m=1.45), mode="carry")
                pos = (truck_pos[0] + ox + math.sin(math.radians(away_yaw)) * run_d,
                       0.0, truck_pos[2] + oz + math.cos(math.radians(away_yaw)) * run_d)
        else:
            pose = _held(GUARD, POSES["ready"], mode="ready")
            pos = (truck_pos[0] + ox, 0.0, truck_pos[2] + oz)
        W6.actor(r, GUARD, pose, pos, away_yaw, tm, seed=82 + idx, amp=0.14,
                 rifle_on=(not dives or blast_age < 0.22))
    vdm.draw(r, tm)
    S3.present(r, surface)


# ---------------------------------------------------------------------------
# GAMEPLAY #4 — Route 12 Checkpoint Fallow 12 Shotgun OTS Combat (2.4s)
# ---------------------------------------------------------------------------

def _gp_checkpoint_ots(surface, tm, size):
    """Third-person OTS Fallow 12 shotgun gameplay behind Route 12 sandbag cover."""
    M = _mods()
    S3 = M["S3"]
    u = _clamp(tm / 2400.0)
    sg_shots = (380, 1650)
    g_shots = (1200,)

    # Biribel leaning cleanly around the Route 12 sandbag emplacement at (-44.5, 19.0)
    bpos = (-45.0 + 0.55 * _smooth(_clamp((u - 0.35) / 0.30)), 0.0, 17.6)
    g1_pos = _open_s3_pos(S3, -41.5, 25.0)
    g2_pos = _open_s3_pos(S3, -36.2, 23.2)
    aim_u = _smooth(_clamp((u - 0.42) / 0.22))
    aim_tgt = _vmix((g1_pos[0], 1.28, g1_pos[2]), (g2_pos[0], 1.28, g2_pos[2]), aim_u)
    byaw = math.degrees(math.atan2(aim_tgt[0] - bpos[0], aim_tgt[2] - bpos[2]))

    rec = _recoil_env(tm, sg_shots, 260.0)
    yr = math.radians(byaw)
    fx, fz = math.sin(yr), math.cos(yr)
    rx, rz = math.cos(yr), -math.sin(yr)
    eye = (bpos[0] - fx * 2.15 + rx * 0.62, 1.56 + rec * 0.07, bpos[2] - fz * 2.15 + rz * 0.62)
    tgt = (aim_tgt[0], aim_tgt[1] + rec * 0.38, aim_tgt[2])

    # Tempered side fire rim (prevents bright flat-beige overexposure on center enemy)
    lights = [{"pos": (-44.5, 2.0, 29.0), "color": (255, 148, 72), "intensity": 0.44, "range": 16.0}]
    if rec > 0.25:
        lights.append({"pos": (bpos[0] + fx * 1.1, 1.5, bpos[2] + fz * 1.1),
                       "color": (255, 206, 118), "intensity": 1.65 * rec, "range": 12.0})

    r = _s3_frame(eye, tgt, 52.0, lights=lights, t=tm, size=size)
    # Wreck fire positioned on left flank so g1 isn't washed out directly in front of the flame
    F3D.emit_fire(r, (-44.2, 0.65, 31.4), tm, seed=855, size=1.35, heat=1.25, smoky=True, embers=True, bed=True, layer=2)

    bp = _aimed(BIRI, POSES["aim"], bpos, byaw, aim_tgt, mode="aim", flags=BIRI_SG, recoil_k=rec * 1.35)
    j_b = W6.actor(r, BIRI, bp, bpos, byaw, tm, seed=851, amp=0.10, rifle_on=True,
                   flags=BIRI_SG, expression="angry")
    b_muz = _draw_bore_flash(r, j_b, tm, sg_shots, seed=851, scale=1.08)

    # Guard 1 crouched in tactical cover aiming back -> reactive hit flinch -> grounded dead_side (ZERO A-pose!)
    if tm < 440:
        g1_p = _aimed(GUARD, POSES["crouch"], g1_pos, 202.0, (bpos[0], 1.3, bpos[2]), mode="aim")
        g1_gun = True
    else:
        fk = _smooth((tm - 440.0) / 480.0)
        flinch = dict(POSES["crouch"], spine=-22.0, head_p=-20.0, lsh_p=42.0, lel=68.0, rsh_p=52.0, rel=52.0)
        g1_p = blend(flinch, _flat_dead_pose(side=True), fk)
        g1_pos = (g1_pos[0] + 0.55 * fk, 0.0, g1_pos[2] + 1.15 * fk)
        g1_gun = False
    W6.actor(r, GUARD, g1_p, g1_pos, 202.0, tm, seed=852, amp=0.12, rifle_on=g1_gun, expression="angry")

    # Guard 2 firing back at 1200ms -> staggered by second blast at 1710ms
    if tm < 1710:
        g2_p = _aimed(GUARD, POSES["crouch"], g2_pos, 224.0, (bpos[0], 1.4, bpos[2]), mode="aim")
        g2_gun = True
    else:
        fk2 = _smooth((tm - 1710.0) / 460.0)
        g2_p = blend(dict(POSES["crouch"], spine=-20.0, lsh_p=38.0, rsh_p=44.0), _flat_dead_pose(side=True), fk2)
        g2_gun = False
    j_g2 = W6.actor(r, GUARD, g2_p, g2_pos, 224.0, tm, seed=853, amp=0.14, rifle_on=g2_gun, expression="angry")
    g2_muz = _draw_bore_flash(r, j_g2, tm, g_shots, seed=853, scale=0.68)

    # Pellet buckshot streaks + impact sparks
    if b_muz:
        for i, s in enumerate(sg_shots):
            age = tm - s
            if 0 <= age < 75:
                frac = age / 75.0
                base_end = g1_pos if i == 0 else g2_pos
                for p_i in range(5):
                    ox = (p_i - 2) * 0.22
                    oy = 1.18 + ((p_i * 3) % 5 - 2) * 0.14
                    end = (base_end[0] + ox, oy, base_end[2])
                    r.add_line3d(_vmix(b_muz, end, max(0.0, frac - 0.38)),
                                 _vmix(b_muz, end, min(1.0, frac + 0.30)), (255, 228, 146), 2, layer=4)
    if g2_muz and 0 <= tm - 1200 < 95:
        frac = (tm - 1200) / 95.0
        end = (-44.4, 0.85, 19.0)
        r.add_line3d(_vmix(g2_muz, end, max(0.0, frac - 0.30)),
                     _vmix(g2_muz, end, min(1.0, frac + 0.25)), (255, 188, 108), 2, layer=4)
    _emit_sparks(r, (-44.4, 0.85, 19.0), tm, (1280,), seed=860)
    _emit_sparks(r, (g1_pos[0], 1.25, g1_pos[2]), tm, (430,), seed=861)
    _emit_sparks(r, (g2_pos[0], 1.15, g2_pos[2]), tm, (1700,), seed=862)
    S3.present(r, surface)


# ---------------------------------------------------------------------------
# ACT III — Kinetic Climax & 100% Brand-New Flash Montage (57.6 .. 76.8s)
# ---------------------------------------------------------------------------

def _terrace_wash(surface, tm, size):
    """Gunship hovering outside rain-slick terrace: properly exposed hull + downwash bracing."""
    M = _mods()
    MS, CS = M["MS"], M["CS"]
    u = _clamp(tm / 2400.0)
    ts = tm * 0.001
    hpos = (_mix(14.2, 11.4, _smooth(u)), MS.FF + 2.05 + 0.22 * math.sin(ts * 3.1), 43.6)
    hyaw = _mix(215.0, 192.0, u)
    hroll = -8.0 * (1.0 - 0.45 * u)
    eye = (-4.5 + 1.6 * u, MS.FF + 1.55, 38.4)
    tgt = (6.6, MS.FF + 2.25, 43.2)

    # Restrained lights placed OFF the fuselage (on terrace floor & cabin) so hull never clips white!
    spot_l = [
        {"pos": (6.2, MS.FF + 1.2, 43.2), "color": (192, 214, 248), "intensity": 0.85, "range": 18.0},
        {"pos": (hpos[0], hpos[1] + 2.4, hpos[2]), "color": (255, 62, 46), "intensity": 0.55, "range": 12.0},
    ]
    r = MS.frame(eye, tgt, 55.0, lights=spot_l, t=tm, size=size, roll=-2.2 * math.sin(ts * 4.8))
    r.light = Light(direction=(-0.35, 0.56, -0.68), ambient=0.16, diffuse=0.30,
                    sky=0.07, tint=(0.64, 0.74, 0.98))
    MS.draw_dynamic_props(r, tm, terrace_open=True)
    CS.put_maru_gunship(r, hpos, hyaw, 4.0, -hroll, (ts * 920.0) % 360.0, (ts * 1650.0) % 360.0, fpv=False)
    # Controlled nose beacon (not a whiteout sun over the hull)
    r.add_sprite((hpos[0] - 1.5, hpos[1] + 0.3, hpos[2] - 2.3),
                 FX6.glow((208, 228, 255), 0.95, int(tm), intensity=0.82, max_px=38), layer=FX6.FX_LAYER)

    # Biribel & Guards visibly crouched & shielding faces against violent rotor downwash!
    brace_b = dict(POSES["crouch"], spine=34.0 + 4.0 * math.sin(ts * 11.0),
                   head_p=24.0, lsh_p=96.0, lel=108.0, lsh_r=14.0)
    bp = _held(BIRI, brace_b, mode="ready", flags=BIRI_OS12)
    bp["lsh_p"] = 96.0
    bp["lel"] = 108.0
    bp["head_p"] = 22.0
    W6.actor(r, BIRI, bp, (3.2, MS.FF, 42.4), 76.0, tm, seed=101, amp=0.35, rifle_on=True,
             flags=BIRI_OS12, expression="angry")

    for idx, (gx0, gz0) in enumerate(((-1.2, 39.2), (1.3, 38.6))):
        dist = u * 2.2
        gpos = (gx0 + dist * 0.85, MS.FF, gz0 + dist * 0.52)
        gbase = _walk_pose(dist, idx * 1.9, lean=24.0)
        gbase["head_p"] = 24.0
        gp = _held(GUARD, gbase, mode="carry")
        gp["lsh_p"] = 88.0 + 6.0 * math.sin(ts * 12.0 + idx)
        gp["lel"] = 104.0
        W6.actor(r, GUARD, gp, gpos, 64.0, tm, seed=103 + idx, amp=0.28, rifle_on=True, expression="angry")

    # Swirling horizontal rotor-wash spray blowing outward across the wet terrace
    for k in range(10):
        ang = k * 0.63 + ts * 2.4
        rad_w = 1.8 + ((ts * 5.5 + k * 0.7) % 5.8)
        sp = (hpos[0] - 2.0 - math.cos(ang) * rad_w, MS.FF + 0.45 + 0.25 * (rad_w / 5.8),
              hpos[2] + math.sin(ang) * rad_w)
        r.add_sprite(sp, FX6.haze((178, 196, 224), 0.75 + rad_w * 0.20, int(tm),
                                  seed=110 + k, intensity=0.24 * (1.0 - rad_w / 7.8)), layer=2)
    W6.snow3d(r, tm, seed=101, n=95, spread=16.0, height=10.0, speed=4.2, col=(180, 196, 220))
    MS.present(r, surface)


def _rocket_streak(surface, tm, size):
    """AA SAM climbs straight onto the gunship -> flares decoy it -> massive mid-air detonation at 1.62s!"""
    M = _mods()
    FS, FFX, CS = M["FS"], M["FFX"], M["CS"]
    u = _clamp(tm / 2400.0)
    ts = tm * 0.001
    z = 820.0
    cx = FS.corridor_x(z)

    aa_pos = (cx - 4.2, 0.0, z + 17.0)

    def _hpos_at(t_s: float):
        tu = _clamp(t_s / 2.4)
        evade = _smooth(_clamp((t_s - 0.85) / 0.80))
        return (
            cx + _mix(11.0, -7.5, tu) - 3.2 * evade,
            _mix(15.8, 21.5, tu) + 2.6 * evade,
            z + _mix(36.0, 52.0, tu),
        )

    hpos = _hpos_at(ts)
    evade_now = _smooth(_clamp((ts - 0.85) / 0.75))
    hyaw = _mix(320.0, 276.0, u)
    hroll = _mix(-20.0, -42.0, evade_now)

    # Decoy flares deployed starting at 0.82s as gunship breaks sharply away
    flares = []
    def _flare_pos_at(idx: int, t_s: float):
        ft0 = 0.82 + idx * 0.20
        age = max(0.0, t_s - ft0)
        sp = _hpos_at(ft0)
        side = 1.0 if idx % 2 == 0 else -1.0
        return (sp[0] + side * age * 3.8, sp[1] - 0.5 - age * 4.4 - 1.9 * age * age, sp[2] - 1.2 - age * 2.8)

    for i in range(4):
        ft0 = 0.82 + i * 0.20
        if ts >= ft0:
            if i == 0 and ts >= 1.62:
                continue  # Lead decoy flare consumed in the mid-air SAM blast at 1.62s!
            age = ts - ft0
            fp = _flare_pos_at(i, ts)
            ftrail = []
            for j in range(6):
                tj = max(ft0, ts - j * 0.065)
                pj = _flare_pos_at(i, tj)
                ftrail.append((pj[0], pj[1], pj[2], tj, 300 + i * 11 + j))
            flares.append({"pos": fp, "t0": ft0, "dur": 2.2, "trail": ftrail})

    # Curved quadratic Bezier SAM flight path: climbs straight at gunship -> hooks into lead flare at 1.62s!
    t_launch, t_hit = 0.10, 1.62
    rk_start = (aa_pos[0] + 0.4, 3.2, aa_pos[2] + 0.6)
    p_hit = _flare_pos_at(0, t_hit)
    # Control point aims directly at the gunship's fuselage before the flare pulls it aside!
    h_mid = _hpos_at(1.05)
    p_ctrl = (h_mid[0] + 1.2, h_mid[1] + 0.8, h_mid[2] - 1.0)

    def _rk_at(t_s: float):
        w = _clamp((t_s - t_launch) / (t_hit - t_launch))
        iw = 1.0 - w
        return (
            iw * iw * rk_start[0] + 2.0 * iw * w * p_ctrl[0] + w * w * p_hit[0],
            iw * iw * rk_start[1] + 2.0 * iw * w * p_ctrl[1] + w * w * p_hit[1],
            iw * iw * rk_start[2] + 2.0 * iw * w * p_ctrl[2] + w * w * p_hit[2],
        )

    rk_alive = t_launch <= ts < t_hit
    rk_p = _rk_at(min(ts, t_hit))
    rk_prev = _rk_at(max(t_launch, min(ts, t_hit) - 0.03))
    vx, vy, vz = rk_p[0] - rk_prev[0], rk_p[1] - rk_prev[1], rk_p[2] - rk_prev[2]
    vn = math.sqrt(vx * vx + vy * vy + vz * vz) or 1.0
    trail, puffs = [], []
    if rk_alive:
        for k in range(22, 0, -1):
            tk = max(t_launch, ts - k * 0.042)
            tp = _rk_at(tk)
            trail.append(tp)
            if k % 2 == 0 and tk > t_launch + 0.02:
                puffs.append((tp[0], tp[1], tp[2], tk, 30 + k))
    rk = {
        "p": rk_p, "dir": (vx / vn, vy / vn, vz / vn),
        "t0": t_launch, "id_seed": 7, "phase": "boost" if ts < 0.45 else "cruise",
        "trail": trail, "puffs": puffs,
    }

    # Camera tracks smoothly up into the intercept & jolts on the 1.62s mid-air explosion!
    blast_age = max(0.0, ts - t_hit)
    sh = 0.42 * math.exp(-blast_age * 5.0) if ts >= t_hit else 0.0
    eye = (cx + 9.2 - 1.8 * u + sh * math.sin(ts * 47.0),
           2.6 + 0.5 * u + sh * math.cos(ts * 41.0), z + 2.5)
    tgt = (cx + 1.0 - 1.8 * evade_now, 10.6 + 3.4 * u, z + 35.0)

    lights = []
    if rk_alive:
        lights.append({"pos": rk_p, "color": (255, 168, 72), "intensity": 0.65, "range": 18.0})
    elif ts >= t_hit:
        fl_i = 2.6 * math.exp(-blast_age * 4.5)
        lights.append({"pos": p_hit, "color": (255, 186, 86), "intensity": fl_i, "range": 32.0})
    for fl in flares[:2]:
        lights.append({"pos": (fl["pos"][0], fl["pos"][1] - 1.5, fl["pos"][2]),
                       "color": (255, 222, 168), "intensity": 0.38, "range": 15.0})

    r = FS.frame(eye, tgt, 56.0, t=tm, size=size, lights=lights, roll=-3.2 * u)
    FS.draw_corridor_fx(r, eye, tm)
    FFX.draw_aa_truck(r, aa_pos, FS.corridor_yaw(z) + 28.0, hpos, True, tm, seed=312)
    FFX.draw_launch_backblasts(r, [(t_launch, rk_start, 7, "sam", False)], ts, tm)
    for idx, (ox, oz) in enumerate(((-8.0, 15.2), (-1.2, 16.2), (2.2, 21.5))):
        gp = _aimed(GUARD, POSES["crouch"], (cx + ox, 0.0, z + oz), 15.0, hpos, mode="aim")
        W6.actor(r, GUARD, gp, (cx + ox, 0.0, z + oz), 15.0, tm, seed=315 + idx, amp=0.16, rifle_on=True)
    CS.put_maru_gunship(r, hpos, hyaw, -8.0, -hroll, (ts * 960.0) % 360.0, (ts * 1720.0) % 360.0, fpv=False)
    if rk_alive:
        FFX.draw_rocket(r, rk, ts, tm)
    elif ts >= t_hit:
        # Dramatic mid-air SAM flare-intercept fireball + expanding flak smoke cloud right behind escaping chopper!
        FFX.draw_booms_and_debris(r, [(t_hit, p_hit, 4.8, 707, "boom")], (), (), (), ts, tm)
        FFX.draw_flak_bursts(r, [(t_hit, p_hit, 708), (t_hit + 0.06, (p_hit[0] + 1.4, p_hit[1] + 0.9, p_hit[2]), 709)],
                             ts, tm)
    if flares:
        FFX.draw_flares(r, flares, ts, tm)
    FS.present(r, surface)


def _gorge_pass(surface, tm, size):
    """Snowy Northern Ridge gorge pass: helicopter searchlight casts a live pool onto the road!"""
    M = _mods()
    FS, CS, FFX = M["FS"], M["CS"], M["FFX"]
    u = _clamp(tm / 2400.0)
    ts = tm * 0.001
    z = 4180.0
    cx = FS.corridor_x(z)
    eye = (cx - 10.5, 19.5, z)
    hpos = (cx + _mix(22.0, -14.0, u), _mix(28.0, 19.5, u), z + _mix(58.0, 24.0, u))
    tgt = (hpos[0] * 0.58 + cx * 0.42, hpos[1] - 4.2, hpos[2])
    hyaw = _mix(216.0, 252.0, u)
    hroll = _mix(-26.0, -14.0, u)

    # Searchlight cone lands squarely on the snowy road & patrol jeep below!
    spot_nose = CS._xf((0.0, 0.55, 4.6), hpos, hyaw, -10.0, -hroll)
    gz = z + 42.0
    gx = FS.corridor_x(gz)
    gy = FS.surface_y(gx, gz)
    beam_ground = (_mix(gx + 6.0, gx - 2.0, u), gy + 0.35, _mix(gz + 8.0, gz - 4.0, u))

    lights = [
        {"pos": (beam_ground[0], beam_ground[1] + 2.4, beam_ground[2]),
         "color": (214, 234, 255), "intensity": 2.35, "range": 30.0},
        {"pos": (spot_nose[0], spot_nose[1] - 2.0, spot_nose[2]),
         "color": (200, 224, 255), "intensity": 0.95, "range": 20.0},
    ]
    pools = [
        {"pos": beam_ground, "range": 19.5, "color": (218, 236, 255), "intensity": 2.65},
    ]
    r = FS.frame(eye, tgt, 56.0, t=tm, size=size, lights=lights, pools=pools, roll=-5.5 * math.sin(u * math.pi))
    FS.draw_corridor_fx(r, eye, tm)

    # Ground patrol jeep + Guards caught right inside the sweeping spotlight beam
    CS.put_wheeled(r, "jeep", (gx + 1.4, gy, gz), yaw=FS.corridor_yaw(gz), odo=0.0)
    for idx, ox in enumerate((-3.4, 5.0)):
        gp = _aimed(GUARD, POSES["crouch"], (gx + ox, gy, gz - 3.0), 10.0, hpos, mode="aim")
        W6.actor(r, GUARD, gp, (gx + ox, gy, gz - 3.0), 10.0, tm, seed=420 + idx, amp=0.16, rifle_on=True)

    CS.put_maru_gunship(r, hpos, hyaw, -10.0, -hroll, (ts * 960.0) % 360.0, (ts * 1700.0) % 360.0, fpv=False)
    r.add_sprite(spot_nose, FX6.glow((225, 240, 255), 1.65, int(tm), intensity=1.25, max_px=64),
                 layer=FX6.FX_LAYER)
    # Volumetric light shaft descending from nose lens straight down into the bright road pool!
    for k in range(1, 9):
        ku = k / 8.5
        bp = _vmix(spot_nose, beam_ground, ku)
        r.add_sprite(bp, FX6.haze((194, 220, 255), 0.75 + ku * 3.8, int(tm),
                                  seed=410 + k, intensity=0.26 * (1.0 - ku * 0.45)), layer=FX6.FX_LAYER)
    # Bright specular core where the beam hits the wet snow/asphalt
    r.add_sprite((beam_ground[0], beam_ground[1] + 0.15, beam_ground[2]),
                 FX6.glow((214, 234, 255), 3.4, int(tm), intensity=0.72, max_px=96), layer=FX6.FX_LAYER)
    FFX.draw_gorge_snow(r, eye, 28.0, ts, reduced_motion=False, hyaw=FS.corridor_yaw(z))
    FS.present(r, surface)


# ---------------------------------------------------------------------------
# 100% BRAND-NEW Climax Flash-Montage (64.8 .. 72.0s — ZERO recycled shots!)
# ---------------------------------------------------------------------------

def _flash_01(surface, tm, size):
    """Clean 3/4 heroic tactical close-up: single IK aim sweep + muzzle burst (ZERO arm clipping!)."""
    M = _mods()
    MS = M["MS"]
    u = _clamp(tm / 1200.0)
    bpos = (-3.0, MS.GF, 14.0)
    aim_pt = (_mix(3.6, 1.8, _smooth(u)), MS.GF + _mix(1.38, 1.58, _smooth(u)), 22.2)
    byaw = 26.0
    rec = _recoil_env(tm, (550,), 180.0)
    eye = (bpos[0] + 2.15 - 0.30 * u, bpos[1] + 1.52, bpos[2] + 1.65)
    tgt = (bpos[0] + 0.22, bpos[1] + 1.42, bpos[2] + 0.30)
    rim_l = [{"pos": (bpos[0] - 1.4, bpos[1] + 2.1, bpos[2] - 1.0),
              "color": (255, 168, 86), "intensity": 1.25 + 1.4 * rec, "range": 10.0}]
    r = MS.frame(eye, tgt, 40.0, lights=rim_l, t=tm, size=size)
    r.marble_refl = 0.34
    MS.draw_dynamic_props(r, tm, front_open=False)
    # Single continuous IK solve (never blends two conflicting IK poses!)
    bp = _aimed(BIRI, POSES["aim"], bpos, byaw, aim_pt, mode="aim", flags=BIRI_OS12, recoil_k=rec)
    j = W6.actor(r, BIRI, bp, bpos, byaw, tm, seed=111, amp=0.08, rifle_on=True,
                 flags=BIRI_OS12, expression="angry")
    _draw_bore_flash(r, j, tm, (550,), seed=111, scale=0.85)
    MS.present(r, surface)


def _flash_02(surface, tm, size):
    """Dynamic Study double-door breach: doors burst open as Biribel surges through firing!"""
    M = _mods()
    MS = M["MS"]
    u = _clamp(tm / 1200.0)
    door_u = _smooth(_clamp(u / 0.45))
    shots = (360, 520)
    rec = _recoil_env(tm, shots, 175.0)
    eye = (-2.4 + 1.1 * u, MS.FF + 1.45, 31.8 + 0.8 * u)
    tgt = (0.0, MS.FF + 1.38, MS.ROOMS_Z - 0.8)
    extra_l = [{"pos": (0.0, MS.FF + 1.8, MS.ROOMS_Z + 0.6), "color": (255, 206, 124),
                "intensity": 1.8 * rec, "range": 10.0}] if rec > 0.2 else []
    r = MS.frame(eye, tgt, 52.0, lights=extra_l, t=tm, size=size, roll=-3.5 * (1.0 - door_u))
    MS.draw_dynamic_props(r, tm, study_open_u=door_u)
    dist = u * 2.8
    bpos = (0.0, MS.FF, MS.ROOMS_Z - 1.4 + dist)
    bp = _aimed(BIRI, _walk_pose(dist, 0.2, lean=9.0), bpos, 12.0, (1.8, MS.FF + 1.3, 34.0),
                mode="aim", flags=BIRI_OS12, recoil_k=rec)
    j = W6.actor(r, BIRI, bp, bpos, 12.0, tm, seed=115, amp=0.10, rifle_on=True,
                 flags=BIRI_OS12, expression="angry")
    _draw_bore_flash(r, j, tm, shots, seed=115, scale=0.88)
    _emit_sparks(r, (0.0, MS.FF + 1.1, MS.ROOMS_Z + 0.2), tm, (80, 140), seed=118, n=9, dust=True)
    MS.present(r, surface)


def _flash_03(surface, tm, size):
    """Route 12 Toll Plaza (z=2680) aerial strike with blocky 'ROUTE 12 - VAMA' gantry sign."""
    M = _mods()
    FS, FFX, CS = M["FS"], M["FFX"], M["CS"]
    u = _clamp(tm / 1200.0)
    ts = tm * 0.001
    gx = FS.corridor_x(2680.0)
    gy = FS.surface_y(gx, 2680.0)
    aa_pos = (gx + 5.0, gy, 2674.0)
    vdm, blown = _get_vdm("flash_toll", "aa_truck", aa_pos, 195.0, 0.25, ts, 912)
    hpos = (gx - _mix(14.0, -8.0, u), gy + _mix(15.5, 19.0, u), 2666.0 + 18.0 * u)
    eye = (gx - 18.0 + 4.0 * u, gy + 6.5, 2642.0 + 6.0 * u)
    tgt = (gx + 2.0, gy + 8.5, 2678.0)
    r = FS.frame(eye, tgt, 56.0, t=tm, size=size, lights=vdm.active_lights(cap=4), roll=-5.0)
    FS.draw_corridor_fx(r, eye, tm)
    W6.add(r, _toll_sign_mesh(gx, gy))
    FFX.draw_aa_truck(r, aa_pos, 195.0, hpos, not blown, tm, seed=912, turret_blown=blown)
    vdm.draw(r, tm)
    CS.put_maru_gunship(r, hpos, 38.0, -6.0, 26.0, (ts * 960.0) % 360.0, (ts * 1700.0) % 360.0, fpv=False)
    FS.present(r, surface)


def _flash_04(surface, tm, size):
    """Clean front-3/4 Fallow 12 shotgun muzzle blast (open silhouette, zero center block)."""
    M = _mods()
    S3 = M["S3"]
    u = _clamp(tm / 600.0)
    bpos = (-32.0, 0.0, 24.0)
    aim_p = (-24.0, 1.35, 32.0)
    byaw = 45.0
    rec = _recoil_env(tm, (120,), 240.0)
    eye = (bpos[0] + 2.85 - 0.35 * u, 1.35 + rec * 0.04, bpos[2] + 0.95)
    tgt = (bpos[0] + 0.35, 1.32, bpos[2] + 0.35)
    lights = [
        {"pos": (bpos[0] + 1.2, 1.6, bpos[2] + 0.8), "color": (255, 204, 122),
         "intensity": 0.65 + 2.2 * rec, "range": 12.0},
    ]
    r = _s3_frame(eye, tgt, 46.0, lights=lights, t=tm, size=size)
    bp = _aimed(BIRI, POSES["aim"], bpos, byaw, aim_p, mode="aim", flags=BIRI_SG, recoil_k=rec * 1.35)
    j = W6.actor(r, BIRI, bp, bpos, byaw, tm, seed=920, amp=0.10, rifle_on=True,
                 flags=BIRI_SG, expression="angry")
    _draw_bore_flash(r, j, tm, (120,), seed=920, scale=1.18)
    S3.present(r, surface)


def _flash_05(surface, tm, size):
    """NEW! 88 m Broadcast Tower dramatic upward whip-pan through sweeping night searchlights."""
    M = _mods()
    FS = M["FS"]
    u = _clamp(tm / 600.0)
    tx = FS.corridor_x(1620.0) - 25.0
    tz = 1658.0
    eye = (tx + 38.0 - 4.0 * u, 9.0 + 3.0 * u, tz - 42.0)
    tgt = (tx, _mix(28.0, 62.0, _smooth(u)), tz)
    r = FS.frame(eye, tgt, 58.0, t=tm, size=size, roll=-6.0 + 4.0 * u)
    FS.draw_corridor_fx(r, (tx, 20.0, tz - 20.0), tm)
    FS.present(r, surface)


def _flash_06(surface, tm, size):
    """NEW! Low tracking sprint past a burning staff car across the moonlit mansion forecourt."""
    M = _mods()
    MS = M["MS"]
    u = _clamp(tm / 600.0)
    dist = u * 3.4
    bz = -17.5 + dist
    eye = (-2.4, 0.78, bz + 2.5)
    tgt = (-0.4, 1.18, bz)
    fl_l = [{"pos": (-6.4, 1.6, -13.6), "color": (255, 132, 46), "intensity": 2.0, "range": 18.0}]
    r = MS.frame(eye, tgt, 50.0, lights=fl_l, t=tm, size=size, roll=-5.0)
    r.light = Light(direction=(-0.38, 0.54, -0.68), ambient=0.16, diffuse=0.28,
                    sky=0.06, tint=(0.58, 0.70, 0.96))
    cars = [(x, z, yaw, paint, idx == 0) for idx, (x, z, yaw, paint) in enumerate(MS.CARS)]
    MS.draw_dynamic_props(r, tm, cars=cars)
    F3D.emit_fire(r, (-6.4, 0.95, -13.6), tm, seed=940, size=1.35, heat=1.35, smoky=True, embers=True, layer=2)
    bbase = _walk_pose(dist, 0.3, lean=16.0, stride_m=1.45)
    W6.actor(r, BIRI, _held(BIRI, bbase, mode="carry", flags=BIRI_OS12), (0.0, 0.0, bz), 0.0,
             tm, seed=121, amp=0.10, rifle_on=True, flags=BIRI_OS12, expression="angry")
    MS.present(r, surface)


def _flash_07(surface, tm, size):
    """NEW! Gunship banking steeply beneath the 34 m Iron Gorge Trestle Bridge in blowing snow."""
    M = _mods()
    FS, CS, FFX = M["FS"], M["CS"], M["FFX"]
    u = _clamp(tm / 900.0)
    ts = tm * 0.001
    bx = FS.corridor_x(3820.0)
    by = FS.surface_y(bx, 3820.0)
    hpos = (bx + _mix(-18.0, 14.0, u), by + _mix(24.0, 21.0, u), 3820.0 + _mix(-24.0, 12.0, u))
    eye = (bx + 18.0, by + 16.0, 3772.0)
    tgt = (hpos[0] * 0.7 + bx * 0.3, by + 26.0, 3818.0)
    r = FS.frame(eye, tgt, 56.0, t=tm, size=size, roll=5.0)
    FS.draw_corridor_fx(r, eye, tm)
    CS.put_maru_gunship(r, hpos, 52.0, -8.0, -32.0, (ts * 980.0) % 360.0, (ts * 1720.0) % 360.0, fpv=False)
    FFX.draw_gorge_snow(r, eye, 30.0, ts, reduced_motion=False, hyaw=FS.corridor_yaw(3820.0))
    FS.present(r, surface)


def _flash_08(surface, tm, size):
    """Broadcast Plaza night aerial strike: gunship banking past lit colonnade & exploding AA bunker."""
    M = _mods()
    FS, FFX, CS = M["FS"], M["FFX"], M["CS"]
    u = _clamp(tm / 900.0)
    ts = tm * 0.001
    px = FS.corridor_x(1620.0)
    aa_pos = (px + 10.5, 0.0, 1612.0)
    vdm, blown = _get_vdm("flash_plaza_aa", "aa_truck", aa_pos, 210.0, 0.22, ts, 966)
    hpos = (px + _mix(-14.0, 8.0, u), _mix(17.5, 14.5, u), 1598.0 + 26.0 * u)
    eye = (px - 18.0 + 3.5 * u, 6.2 + 1.2 * u, 1564.0 + 6.0 * u)
    tgt = (px + 6.0, 8.2, 1616.0)
    r = FS.frame(eye, tgt, 58.0, t=tm, size=size, lights=vdm.active_lights(cap=4), roll=5.5)
    FS.draw_corridor_fx(r, eye, tm)
    FFX.draw_aa_truck(r, aa_pos, 210.0, hpos, not blown, tm, seed=966, turret_blown=blown)
    vdm.draw(r, tm)
    CS.put_maru_gunship(r, hpos, 34.0, -7.0, -28.0, (ts * 980.0) % 360.0, (ts * 1740.0) % 360.0, fpv=False)
    FS.present(r, surface)


def _climax_surge(surface, tm, size):
    """Accelerating 6-beat kinetic combat crescendo (replaces static dual_horizon)."""
    # Accelerating cuts: 1.10s, 1.00s, 0.85s, 0.75s, 0.60s, 0.50s (total 4.80s)
    cuts = (0, 1100, 2100, 2950, 3700, 4300, 4800)
    idx = 0
    for i in range(len(cuts) - 1):
        if tm >= cuts[i]:
            idx = i
    sub = tm - cuts[idx]
    if idx == 0:
        # 1. Door-gunner bursting into exploding boulevard convoy (fresh offset at AA explosion)
        _gp_door_gunner(surface, 1880 + sub, size, key="surge_dg")
    elif idx == 1:
        # 2. High-energy close-range Grand Hall OTS kill flash (never repeats static balcony!)
        _gp_mansion_ots(surface, 2800 + sub, size)
    elif idx == 2:
        # 3. Trailer turret LMG spraying strobe-lit patrol jeep
        _gp_chase_lmg(surface, 1240 + sub, size)
    elif idx == 3:
        # 4. Route 12 Toll Plaza explosion strike
        _flash_03(surface, 180 + sub, size)
    elif idx == 4:
        # 5. Checkpoint Fallow 12 shotgun blast
        _flash_04(surface, sub, size)
    else:
        # 6. Gorge gunship searchlight pass rushing toward lens into total silence
        _gorge_pass(surface, 1650 + sub, size)


# ---------------------------------------------------------------------------
# THE BREATH — Dual-Pass Winter Gorge Scope (composited at native 1920x804)
# ---------------------------------------------------------------------------

def _scope_sentries(r, pad, tm, u):
    """Unnamed Presidential Guard patrol in snowy clearing — natural movement & breath."""
    M = _mods()
    CS = M["CS"]
    ts = tm * 0.001
    trk = (pad[0] + 6.5, 0.0, pad[2] + 3.5)
    CS.put(r, "ridge_guard_truck", lambda: CS._asset("truck_m7", scale=1.0, burned=0.0), trk, yaw=230.0)
    r.add_sprite((trk[0] - 1.9, 1.05, trk[2] - 1.5),
                 FX6.glow((255, 224, 162), 1.4, int(tm), intensity=1.4, max_px=36), layer=FX6.FX_LAYER)

    # Lead Guard sentry: takes 2 real patrol steps onto his mark (0..1.55s), halts, raises rifle & scans
    step_u = _smooth(_clamp(ts / 1.55))
    lead_pos = (pad[0] - 1.45 + 1.15 * step_u, 0.0, pad[2] - 1.35 + 0.45 * step_u)
    if ts < 1.55:
        lead_yaw = _mix(178.0, 216.0, step_u)
        lead_base = _walk_pose(step_u * 1.45, 0.2, lean=4.5)
        lead_p = _held(GUARD, lead_base, mode="ready")
        lead_p["head_y"] = -18.0 * (1.0 - step_u) + 12.0 * step_u
    else:
        su = _clamp((ts - 1.55) / 2.05)
        scan = math.sin(su * math.pi * 1.25)
        lead_yaw = 216.0 + 18.0 * scan
        aim_pt = (pad[0] - 18.0 + 16.0 * scan, 3.2 + 2.5 * su, pad[2] - 14.0)
        lead_base = dict(POSES["ready"], spine=4.0 + 2.0 * math.sin(ts * 2.0), spine_r=3.0 * scan)
        lead_p = _aimed(GUARD, lead_base, lead_pos, lead_yaw, aim_pt, mode="ready")
        lead_p["head_y"] = 28.0 * math.sin(su * math.pi * 1.4 - 0.35)
        lead_p["head_p"] = -8.0 * _smooth(_clamp((su - 0.55) / 0.35))
    j0 = W6.actor(r, GUARD, lead_p, lead_pos, lead_yaw, tm,
                  seed=510, amp=0.18, rifle_on=True, expression="stern")
    _emit_breath(r, j0, lead_yaw, tm, seed=510)

    # Flanking sentries walking naturally
    flank1 = (pad[0] - 5.2 + 2.4 * u, 0.0, pad[2] + 1.8)
    flank2 = (pad[0] + 3.4 - 1.6 * u, 0.0, pad[2] - 4.2)
    W6.actor(r, GUARD, _held(GUARD, _walk_pose(2.4 * u, 0.4, 4.5), mode="ready"), flank1, 128.0, tm,
             seed=511, amp=0.16, rifle_on=True, expression="stern")
    W6.actor(r, GUARD, _held(GUARD, _walk_pose(1.6 * u, 2.1, 4.0), mode="ready"), flank2, 245.0, tm,
             seed=512, amp=0.16, rifle_on=True, expression="stern")
    return lead_pos


def render_scope_passes(tm: int, size=RENDER_SIZE) -> tuple[pygame.Surface, pygame.Surface]:
    """Render blurred 1x peripheral pass + sharp zoomed pass for native 1920x804 scope mask."""
    M = _mods()
    DS, CS = M["DS"], M["CS"]
    u = _clamp(tm / 3600.0)
    ts = tm * 0.001
    pad = (CS.road_x(2300.0) + 70.0, 0.0, 2300.0)
    eye = (pad[0] - 42.0, 12.5, pad[2] - 28.0)

    # Crosshair tracks with natural human lag onto his patrol mark -> settles dead-center on chest
    track_u = _smooth(_clamp((ts - 0.15) / 1.75))
    lead_x = pad[0] - 1.15 + 0.85 * track_u
    lead_z = pad[2] - 1.25 + 0.35 * track_u
    sway_k = 1.0 - _smooth(_clamp((u - 0.12) / 0.72))
    breath_y = math.sin(ts * 1.65) * 0.58 * sway_k
    breath_x = math.cos(ts * 1.15) * 0.75 * sway_k
    tgt = (lead_x + breath_x, 1.34 + breath_y, lead_z)

    ridge_lights = [
        {"pos": (pad[0] - 8.0, 10.0, pad[2] - 10.0), "color": (172, 206, 250), "intensity": 0.68, "range": 48.0},
        {"pos": (pad[0] + 7.5, 5.5, pad[2] + 4.0), "color": (255, 198, 132), "intensity": 0.62, "range": 36.0},
    ]
    ridge_pools = [
        {"pos": (pad[0] - 0.5, 0.4, pad[2] - 1.0), "range": 18.0, "color": (186, 204, 230), "intensity": 0.72},
        {"pos": (pad[0] + 4.5, 0.4, pad[2] + 1.5), "range": 16.0, "color": (255, 194, 128), "intensity": 0.58},
    ]

    w, h = size
    # 1) Defocused 1x peripheral pass (quarter-res smoothscale blur + moonlight tint)
    periph_small = _surf("scope_p_small", (max(64, w // 4), max(32, h // 4)))
    r_p = DS.ridge_frame(pad, eye, tgt, 54.0, t=tm, size=periph_small.get_size(),
                         lights=ridge_lights, pools=ridge_pools)
    _scope_sentries(r_p, pad, tm, u)
    W6.snow3d(r_p, tm, seed=501, n=65, spread=22.0, height=14.0, speed=1.4)
    r_p.flush(periph_small)
    periph = _surf("scope_p_full", size)
    pygame.transform.smoothscale(periph_small, size, periph)
    periph.fill((124, 138, 162), special_flags=pygame.BLEND_RGB_MULT)

    # 2) Crisp zoomed optic pass (12.2 -> 6.8 deg pull-in onto the Guard sentry)
    zoom_fov = _mix(12.2, 6.8, _smooth(u))
    scope_buf = _surf("scope_buf", size)
    r_s = DS.ridge_frame(pad, eye, tgt, zoom_fov, t=tm, size=size,
                         lights=ridge_lights, pools=ridge_pools)
    _scope_sentries(r_s, pad, tm, u)
    W6.snow3d(r_s, tm, seed=502, n=90, spread=18.0, height=12.0, speed=1.2)
    r_s.flush(scope_buf)
    try:
        FX6.grade_cine(scope_buf)
    except Exception:
        pass
    return periph, scope_buf


def _scope_breath(surface, tm, size):
    """Fallback single-surface entry (ScopeBreathShot in render.py composites at 1920x804)."""
    periph, scope_buf = render_scope_passes(tm, size)
    surface.blit(scope_buf, (0, 0))


SCENES = {
    "cold_snow": _cold_snow,
    "ember_barn": _ember_barn,
    "patrol_march": _patrol_march,
    "dawn_road": _dawn_road,
    "estate_gate": _estate_gate,
    "gp_mansion_ots": _gp_mansion_ots,
    "city_hover": _city_hover,
    "hall_breach": _hall_breach,
    "chase_dust": _chase_dust,
    "gp_chase_lmg": _gp_chase_lmg,
    "gp_door_gunner": _gp_door_gunner,
    "convoy_boom": _convoy_boom,
    "gp_checkpoint_ots": _gp_checkpoint_ots,
    "terrace_wash": _terrace_wash,
    "rocket_streak": _rocket_streak,
    "gorge_pass": _gorge_pass,
    "flash_01": _flash_01,
    "flash_02": _flash_02,
    "flash_03": _flash_03,
    "flash_04": _flash_04,
    "flash_05": _flash_05,
    "flash_06": _flash_06,
    "flash_07": _flash_07,
    "flash_08": _flash_08,
    "climax_surge": _climax_surge,
    "scope_breath": _scope_breath,
}


def render_scene(name: str, surface: pygame.Surface, t_ms: int, size=RENDER_SIZE) -> None:
    """Render one spoiler-safe 3D or gameplay shot into ``surface``."""
    SCENES[name](surface, int(t_ms), size)
