"""Mission 8 Duty - Last Flight 3D cabin, pintle LMG, rockets, AA trucks, and FX."""
from collections import OrderedDict
import math

import pygame

from cutscenes import fire3d as F3D
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from engine3d import Mesh, POSES, box, clamp, disc_xz
from engine3d.core import m_apply, m_mul, rot_x, rot_y, rot_z, v_add
from engine3d.textures import tex
from missions.m7 import raid3d as R
from missions.m8.revenge import chase3d as C
from missions.m8.revenge import chase_set as CS

_CACHE = {}
_PUFF_SPRITES = OrderedDict()
_RETICLE_CACHE = OrderedDict()

SIGHT_Y = 0.160
OPTIC_Z = 0.045
BORE_LOCAL = (0.0, 0.068, 0.735)
PINTLE_PIVOT_LOCAL = (0.94, 1.22, 0.30)
TRUNNION_LOCAL = (0.0, -0.055, 0.180)
AMMO_FEED_LOCAL = (0.80, 0.874, 0.48)
FEED_TRAY_LOCAL = (-0.048, 0.025, 0.10)
EJECT_PORT_LOCAL = (0.055, 0.032, 0.08)
FPV_PINTLE_TOP = PINTLE_PIVOT_LOCAL
FPV_PILOT_SEAT = (-0.42, 0.62, 1.92)
FPV_ROTOR_HUB = (0.0, 3.03, 0.25)

_PILOT_POSE = dict(
    POSES["stand"],
    lhip_p=86, lkn=84, rhip_p=86, rkn=84,
    lsh_p=42, lel=46, rsh_p=46, rel=42,
    spine=8, head_p=2,
)


def _clamp01(v):
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def _ease(k):
    k = _clamp01(k)
    return k * k * (3.0 - 2.0 * k)


def _submit(r, key, mesh, mat, pos):
    if hasattr(r, "add_packed"):
        pk = _CACHE.setdefault("pack", {})
        rk = (id(r), key)
        rows = pk.get(rk)
        if rows is None:
            faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces]
            rows = pk[rk] = r.pack(mesh.verts, faces)
        if rows is not None:
            import numpy as np
            rt = np.asarray(mat, dtype=rows.dtype).reshape(3, 3).T
            out = rows.copy()
            out[:, 0:3] = rows[:, 0:3] @ rt
            out[:, 0:3] += np.asarray(pos, dtype=rows.dtype)
            out[:, 6:9] = rows[:, 6:9] @ rt
            r.add_packed(out)
            return
    verts = [v_add(pos, m_apply(mat, v)) for v in mesh.verts]
    r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces])


def cabin_mesh():
    """Legacy open twin-door cabin mesh kept for compatibility."""
    return fpv_gunship_mesh()


def fpv_gunship_mesh():
    """Sightline-engineered open-bay first-person assault gunship interior.

    Eye sits at y=1.56 along an unobstructed 360-deg panoramic gunner bay.
    Floor/sills stay <= 0.18, port cockpit console <= 0.94, canopy roof >= 2.28,
    and zero door jambs or side pillars cross the aim cone.
    """
    m = _CACHE.get("fpv_cabin")
    if m is not None:
        return m
    m = _CACHE["fpv_cabin"] = Mesh()
    olive = tex("metal_rib", like=(46, 54, 42), tint=True)
    dark = tex("steel", like=(28, 30, 34), tint=True)
    steel = (64, 68, 74)
    pad = (22, 24, 26)
    warn = (198, 152, 42)
    brass = (182, 148, 62)

    # Low armored floor deck + non-slip mat + caution doorway sills
    m.add(box(1.88, 0.10, 2.70, olive, center=(0.0, 0.05, 0.35)))
    m.add(box(1.36, 0.02, 2.00, pad, center=(0.0, 0.11, 0.25)))
    for sx in (-1.0, 1.0):
        m.add(box(0.11, 0.025, 2.20, warn, center=(sx * 0.88, 0.115, 0.20)))
        m.add(box(0.09, 0.06, 2.50, dark, center=(sx * 0.92, 0.13, 0.30)))

    # Center pintle pedestal post (low floor swivel, clear of downward aim)
    m.add(box(0.32, 0.04, 0.32, steel, center=(0.0, 0.12, 0.0)))
    m.add(box(0.09, 0.92, 0.09, dark, center=(0.0, 0.58, 0.0)))
    m.add(box(0.14, 0.07, 0.14, steel, center=(0.0, 1.04, 0.0)))
    # Coiled brass ammo feed chute at base
    m.add(box(0.24, 0.20, 0.30, (44, 52, 40), center=(-0.22, 0.22, -0.05)))
    m.add(box(0.12, 0.04, 0.22, brass, center=(-0.12, 0.34, -0.02)))

    # Forward-port cockpit console (kept port-biased & low so forward-down view is open)
    m.add(box(1.76, 0.26, 0.10, olive, center=(0.0, 0.24, 1.32)))
    m.add(box(1.72, 0.16, 1.08, dark, center=(0.0, 0.13, 2.15)))
    m.add(box(0.96, 0.38, 0.58, dark, center=(-0.42, 0.60, 2.24)))
    m.add(box(0.82, 0.24, 0.06, (20, 22, 26), center=(-0.44, 0.78, 2.04)), m=rot_x(24))
    # Emissive avionics gauges & artificial horizon
    for dx, col in ((-0.62, (64, 232, 134)), (-0.48, (64, 232, 134)), (-0.34, (248, 178, 56)),
                    (-0.20, (248, 178, 56)), (-0.62, (234, 68, 54)), (-0.34, (84, 194, 255))):
        m.add(box(0.06, 0.038, 0.02, col, center=(dx, 0.80, 2.00), emissive=True))
    # Pilot seat
    m.add(box(0.46, 0.46, 0.46, (34, 36, 40), center=(-0.46, 0.34, 1.62)))
    # Low nose chin sill
    m.add(box(1.64, 0.10, 0.42, olive, center=(0.0, 0.36, 2.64)))

    # High overhead roof canopy (y >= 2.28) & slim far-forward peripheral windshield frame
    m.add(box(1.86, 0.08, 2.20, olive, center=(0.0, 2.34, 0.32)))
    for rz in (-0.65, 0.00, 0.65, 1.25):
        m.add(box(1.74, 0.04, 0.07, steel, center=(0.0, 2.28, rz)))
    # Warm amber cabin utility strip lamp
    m.add(box(0.32, 0.025, 0.08, (255, 152, 74), center=(0.0, 2.27, 0.32), emissive=True))
    for sx in (-1.0, 1.0):
        # Far-forward slim angled windshield A-pillars (outside central aim cone)
        m.add(box(0.042, 1.42, 0.048, dark), m=rot_x(-30), t=(sx * 0.94, 1.50, 2.34))
        # Landing skids & aft-mounted stub wings / rocket pods (clear of side-bay downward aim)
        m.add(box(0.09, 0.09, 3.40, dark, center=(sx * 1.28, -0.52, 0.55)))
        for sz in (-0.50, 1.10):
            m.add(box(0.065, 0.68, 0.075, dark), m=rot_z(sx * 24.0), t=(sx * 1.06, -0.24, sz))
        m.add(box(0.66, 0.12, 0.50, olive, center=(sx * 1.26, 0.36, -0.58)))
        m.add(box(0.24, 0.24, 0.88, (44, 48, 42), center=(sx * 1.50, 0.24, -0.56)))
    return m


def rotor_mesh():
    """Spinning main rotor hub + 4 swept blades + translucent motion-blur disc."""
    m = _CACHE.get("rotor")
    if m is not None:
        return m
    m = _CACHE["rotor"] = Mesh()
    hub = (32, 34, 38)
    blade = (24, 26, 28)
    tip = (196, 174, 68)
    m.add(box(0.34, 0.24, 0.34, hub, center=(0.0, 0.0, 0.0)))
    for i in range(4):
        rot = rot_y(i * 90.0)
        b = Mesh()
        b.add(box(0.22, 0.03, 4.6, blade, center=(0.0, 0.06, 2.45)))
        b.add(box(0.23, 0.035, 0.32, tip, center=(0.0, 0.06, 4.65)))
        m.add(b, rot, (0.0, 0.0, 0.0))
    return m


def _heat_sleeve_mesh(col):
    cq = tuple(int(c // 16 * 16) for c in col)
    m = _CACHE.get(("hs", cq))
    if m is None:
        m = _CACHE[("hs", cq)] = box(0.028, 0.028, 0.34, cq, center=(0.0, 0.032, 0.50), emissive=True)
    return m


def _gunner_hands_mesh():
    """Articulated dark gloved hands & olive-drab forearms anchored to grip and handguard."""
    m = _CACHE.get("gunner_hands")
    if m is not None:
        return m
    m = _CACHE["gunner_hands"] = Mesh()
    glove = (26, 28, 32)
    knuckle = (38, 42, 46)
    cuff = (44, 50, 42)
    sleeve = (38, 44, 36)
    # Right trigger hand wrapping pistol grip + thumb + angled forearm
    m.add(box(0.046, 0.068, 0.062, glove, center=(0.010, -0.042, -0.014)))
    m.add(box(0.050, 0.022, 0.048, knuckle, center=(0.012, -0.016, 0.004)))
    m.add(box(0.022, 0.024, 0.044, glove, center=(-0.016, -0.012, -0.008)))
    m.add(box(0.056, 0.058, 0.065, cuff), m=rot_x(20), t=(0.024, -0.068, -0.068))
    m.add(box(0.064, 0.066, 0.18, sleeve), m=m_mul(rot_y(-8), rot_x(24)), t=(0.038, -0.105, -0.175))
    # Left support hand clamping forward handguard + thumb over rail + forearm
    m.add(box(0.052, 0.054, 0.086, glove, center=(-0.032, -0.018, 0.255)))
    m.add(box(0.036, 0.020, 0.058, knuckle, center=(-0.018, 0.014, 0.258)))
    m.add(box(0.058, 0.058, 0.064, cuff), m=rot_y(-24), t=(-0.068, -0.038, 0.205))
    m.add(box(0.066, 0.066, 0.20, sleeve), m=m_mul(rot_y(-28), rot_x(16)), t=(-0.125, -0.078, 0.095))
    return m


def _pintle_yoke_mesh():
    """Rigid swiveling steel pintle U-yoke + trunnion pin anchored at PINTLE_PIVOT_LOCAL."""
    m = _CACHE.get("pintle_yoke")
    if m is not None:
        return m
    m = _CACHE["pintle_yoke"] = Mesh()
    steel = (68, 74, 82)
    dark = (32, 36, 42)
    pin = (94, 100, 108)
    # Swivel stem & U-cradle base
    m.add(box(0.046, 0.044, 0.046, dark, center=(0.0, -0.056, 0.0)))
    m.add(box(0.106, 0.024, 0.068, steel, center=(0.0, -0.028, 0.0)))
    # Left and right yoke fork cheeks embracing the LMG receiver lug
    for sx in (-1.0, 1.0):
        m.add(box(0.018, 0.064, 0.054, steel, center=(sx * 0.044, 0.008, 0.0)))
    # Horizontal trunnion bolt & locking nut
    m.add(box(0.122, 0.018, 0.018, pin, center=(0.0, 0.004, 0.0)))
    return m


def _ammo_link_mesh():
    """Single cached brass cartridge + dark disintegrating link segment for the feed belt."""
    m = _CACHE.get("ammo_link")
    if m is not None:
        return m
    m = _CACHE["ammo_link"] = Mesh()
    brass = (206, 168, 68)
    copper = (184, 108, 56)
    link = (36, 40, 44)
    m.add(box(0.014, 0.014, 0.054, brass, center=(0.0, 0.0, -0.006)))
    m.add(box(0.010, 0.010, 0.020, copper, center=(0.0, 0.0, 0.028)))
    m.add(box(0.022, 0.018, 0.026, link, center=(0.0, 0.0, -0.004)))
    return m


def _draw_ammo_belt(r, p_box, p_tray, basis):
    """Render a 7-segment catenary linked brass ammo belt from the floor box into the feed tray."""
    link_m = _ammo_link_mesh()
    b_fwd = m_apply(basis, (0.0, 0.0, 1.0))
    b_rg = m_apply(basis, (1.0, 0.0, 0.0))
    yaw_gun = math.degrees(math.atan2(b_fwd[0], b_fwd[2]))
    n_seg = 7
    for k in range(n_seg):
        u = (k + 0.5) / float(n_seg)
        arch = math.sin(u * math.pi)
        px = p_box[0] + (p_tray[0] - p_box[0]) * u - b_rg[0] * (0.045 * arch)
        py = p_box[1] + (p_tray[1] - p_box[1]) * u - 0.055 * arch
        pz = p_box[2] + (p_tray[2] - p_box[2]) * u - b_rg[2] * (0.045 * arch)
        roll_k = -18.0 + 34.0 * u
        pitch_k = -10.0 * (1.0 - u)
        lmat = m_mul(rot_y(yaw_gun), m_mul(rot_x(pitch_k), rot_z(roll_k)))
        _submit(r, "ammo_link", link_m, lmat, (px, py, pz))


def _maru_interior_accents(info):
    """Intact cabin ceiling lintel, port wall seal, rigid sill pintle stanchion,
    bolted olive ammo box, caution sill stripes, cockpit gauges & warm bay lamp."""
    m = _CACHE.get("maru_accents")
    if m is not None:
        return m
    m = _CACHE["maru_accents"] = Mesh()
    fy = float(info.get("floor_y", 0.574))
    px, py, pz = PINTLE_PIVOT_LOCAL
    sx, sy, sz = info.get("pilot_seat", (-0.42, 0.62, 1.92))
    steel = (64, 68, 74)
    dark = (26, 30, 34)
    olive = (46, 54, 42)
    pad = (32, 34, 38)
    brass = (196, 158, 64)
    warn_y = (214, 164, 38)

    # Seal the port doorway opening from the inside so the port cabin wall is intact
    m.add(box(0.06, 1.66, 1.92, (34, 38, 34), center=(-1.02, fy + 0.83, 0.28)))
    for rz in (-0.30, 0.28, 0.86):
        m.add(box(0.08, 1.58, 0.05, dark, center=(-0.99, fy + 0.81, rz)))

    # Starboard doorway ceiling lintel & padded header + fore/aft jambs (hides rotor mast)
    m.add(box(0.18, 0.14, 1.94, pad, center=(0.96, 2.15, 0.28)))
    m.add(box(0.24, 0.08, 1.96, dark, center=(0.92, 2.23, 0.28)))
    m.add(box(0.12, 1.62, 0.10, pad, center=(0.98, fy + 0.81, 1.20)))
    m.add(box(0.12, 1.62, 0.10, pad, center=(0.98, fy + 0.81, -0.65)))

    # High-contrast yellow/black hazard caution sill along the starboard doorway edge
    for i in range(8):
        sz0 = -0.56 + i * 0.22
        scol = warn_y if (i % 2 == 0) else dark
        m.add(box(0.14, 0.032, 0.21, scol, center=(0.98, fy + 0.012, sz0)))

    # Rigid floor-to-trunnion steel pintle stanchion post bolted to the starboard sill
    post_top_y = py - 0.055
    post_h = max(0.12, post_top_y - fy)
    m.add(box(0.22, 0.036, 0.24, steel, center=(px - 0.03, fy + 0.018, pz)))
    m.add(box(0.076, post_h, 0.076, dark, center=(px, fy + post_h * 0.5, pz)))
    m.add(box(0.054, 0.36, 0.054, steel), m=rot_z(24.0), t=(px - 0.08, fy + 0.17, pz))
    m.add(box(0.118, 0.048, 0.118, steel, center=(px, post_top_y, pz)))

    # Bolted olive-drab 7.62mm ammo chest beside the pintle post + brass belt guide throat
    ax, az = 0.78, 0.50
    m.add(box(0.24, 0.26, 0.32, olive, center=(ax, fy + 0.13, az)))
    m.add(box(0.25, 0.035, 0.33, dark, center=(ax, fy + 0.26, az)))
    m.add(box(0.08, 0.045, 0.10, steel, center=(ax + 0.02, fy + 0.29, az - 0.02)))
    m.add(box(0.05, 0.025, 0.08, brass, center=AMMO_FEED_LOCAL))

    # Emissive instrument cluster on the forward cockpit glare-shield
    dash_z = sz + 0.52
    dash_y = sy + 0.62
    for dx, dy, col in (
        (-0.20, 0.02, (64, 234, 136)),
        (-0.08, 0.02, (64, 234, 136)),
        (0.05, 0.02, (248, 178, 58)),
        (0.18, 0.02, (248, 178, 58)),
        (-0.14, -0.05, (84, 194, 255)),
        (0.10, -0.05, (238, 72, 56)),
    ):
        m.add(box(0.055, 0.032, 0.018, col, center=(sx + dx, dash_y + dy, dash_z), emissive=True))
    # Warm low-intensity amber cabin utility strip tucked below the ceiling beam
    m.add(box(0.28, 0.022, 0.08, (232, 146, 68), center=(0.15, 2.15, 0.35), emissive=True))
    return m


def tanker_mesh(burned=False):
    """Explosive Guard fuel tanker truck (gun-truck chassis + pressurized red-rust tank)."""
    key = ("tanker", bool(burned))
    m = _CACHE.get(key)
    if m is not None:
        return m
    m = _CACHE[key] = Mesh()
    tank_col = (34, 32, 30) if burned else tex("steel", like=(138, 46, 36), tint=True)
    band_col = (44, 42, 40) if burned else (214, 168, 52)
    frame_col = (24, 26, 28)
    m.add(box(1.95, 1.38, 3.65, tank_col, center=(0.0, 2.24, -0.55)))
    m.add(box(1.62, 0.24, 3.55, tank_col, center=(0.0, 3.00, -0.55)))
    for bz in (-1.85, -0.55, 0.75):
        m.add(box(2.02, 1.44, 0.14, band_col, center=(0.0, 2.24, bz), emissive=not burned))
    m.add(box(0.32, 0.22, 0.32, frame_col, center=(0.0, 3.16, -0.55)))
    return m


def _aa_turret_mesh(lit=True):
    """Dual-barrel AA turret & searchlight yoke mounted on the gun-truck bed."""
    key = ("aa_turret", bool(lit))
    m = _CACHE.get(key)
    if m is not None:
        return m
    m = _CACHE[key] = Mesh()
    steel = (54, 58, 62)
    dark = (26, 28, 32)
    m.add(box(0.68, 0.52, 0.68, steel, center=(0.0, 0.26, 0.0)))
    for sx in (-0.16, 0.16):
        m.add(box(0.08, 0.09, 1.55, dark, center=(sx, 0.62, 0.68)))
    m.add(box(0.46, 0.44, 0.44, (44, 48, 52), center=(0.0, 0.72, 0.12)))
    lens = (242, 246, 255) if lit else (40, 44, 50)
    m.add(box(0.36, 0.34, 0.06, lens, center=(0.0, 0.72, 0.36), emissive=lit))
    return m


def _rocket_plume_mesh(seed_q, k):
    """3D incandescent booster flame spindle in rocket local space (tail at -z)."""
    key = ("rplume", seed_q % 4, int(round(k * 6.0)))
    m = _CACHE.get(key)
    if m is not None:
        return m
    m = _CACHE[key] = Mesh()
    z0 = -CS.ROCKET_LEN * 0.48
    ln = (2.15 + 0.38 * (seed_q % 3)) * (0.85 + 0.25 * k)
    r = 0.24
    c_core = (255, 252, 224)
    c_mid = (255, 168, 62)
    c_tip = (224, 82, 24)
    pts_b = [(math.cos(i * math.tau / 4.0) * r, math.sin(i * math.tau / 4.0) * r, z0) for i in range(4)]
    pts_m = [(math.cos(i * math.tau / 4.0) * r * 1.15, math.sin(i * math.tau / 4.0) * r * 1.15, z0 - ln * 0.34)
             for i in range(4)]
    apex = (0.0, 0.0, z0 - ln)
    for i in range(4):
        j = (i + 1) % 4
        m.face([pts_b[i], pts_b[j], pts_m[j]], c_core, 2, True, True)
        m.face([pts_b[i], pts_m[j], pts_m[i]], c_mid, 2, True, True)
        m.face([pts_m[i], pts_m[j], apex], c_tip, 2, True, True)
    return m


def heli_matrix(hyaw, hpitch, hroll):
    """Airframe world rotation matrix (+Z nose, +X starboard, +Y up)."""
    return m_mul(rot_y(hyaw), m_mul(rot_x(-hpitch), rot_z(-hroll)))


def cs_matrix(yaw, pitch, roll):
    """Airframe rotation matching chase_set._xf / CS.put (rot_y * rot_x(-pitch) * rot_z(+roll))."""
    return m_mul(rot_y(yaw), m_mul(rot_x(-pitch), rot_z(roll)))


def _ucilev_trim_mesh():
    """Commander gunship armor sponsons, stub-wing pylons, and crimson livery stripes."""
    m = _CACHE.get("ucilev_trim")
    if m is not None:
        return m
    m = _CACHE["ucilev_trim"] = Mesh()
    armor = (18, 20, 24)
    crimson = (148, 28, 28)
    crimson_hi = (176, 38, 34)
    steel = (52, 56, 62)
    # Armored nose cheek fairings + commander stripes
    for sx in (-1.0, 1.0):
        m.add(box(0.14, 0.44, 1.35, armor, center=(sx * 0.52, 1.04, 4.32)))
        m.add(box(0.16, 0.12, 1.18, crimson, center=(sx * 0.54, 1.20, 4.35)))
        # Heavy mid-cabin gun sponsons + crimson flank bands
        m.add(box(0.14, 0.54, 1.85, armor, center=(sx * 1.10, 1.48, 0.92)))
        m.add(box(0.16, 0.16, 1.72, crimson_hi, center=(sx * 1.12, 1.66, 0.92)))
        # Extended stub-wing weapon pylons out to +-1.68 m
        m.add(box(0.86, 0.14, 0.72, armor, center=(sx * 1.36, 1.16, 0.98)))
        m.add(box(0.18, 0.22, 0.54, steel, center=(sx * 1.68, 1.08, 0.98)))
    # Dorsal turbine armor collar + tail fin crimson ace stripe
    m.add(box(1.92, 0.24, 1.65, armor, center=(0.0, 2.28, 0.35)))
    m.add(box(0.18, 0.58, 1.05, crimson_hi, center=(0.0, 3.22, -4.95)))
    return m


def _ucilev_spotlight_mesh():
    """Chin-mounted armored searchlight turret and high-output emissive lens."""
    m = _CACHE.get("ucilev_spot")
    if m is not None:
        return m
    m = _CACHE["ucilev_spot"] = Mesh()
    housing = (24, 26, 30)
    bezel = (68, 74, 82)
    m.add(box(0.32, 0.28, 0.32, (42, 46, 52), center=(0.0, 0.78, 5.64)))
    m.add(box(0.56, 0.48, 0.62, housing, center=(0.0, 0.56, 5.72)))
    m.add(box(0.60, 0.52, 0.10, bezel, center=(0.0, 0.56, 6.02)))
    m.add(box(0.46, 0.38, 0.08, (242, 248, 255), center=(0.0, 0.56, 6.06), emissive=True))
    return m


def _ucilev_pod_mesh(side):
    """Stub-wing 7-tube armored rocket pod mounted at (side*1.68, 1.05, 0.98)."""
    s = -1.0 if side < 0.0 else 1.0
    key = ("ucilev_pod", int(s))
    m = _CACHE.get(key)
    if m is not None:
        return m
    m = _CACHE[key] = Mesh()
    cx, cy, cz = s * 1.68, 1.05, 0.98
    tube = (26, 28, 32)
    band = (158, 34, 30)
    face = (46, 50, 56)
    tip = (214, 72, 48)
    m.add(box(0.52, 0.50, 1.62, tube, center=(cx, cy, cz)))
    m.add(box(0.56, 0.54, 0.24, band, center=(cx, cy, cz + 0.48)))
    m.add(box(0.54, 0.52, 0.14, face, center=(cx, cy, cz + 0.80)))
    for dx, dy in ((0.0, 0.0), (-0.13, 0.10), (0.13, 0.10), (-0.13, -0.10), (0.13, -0.10)):
        m.add(box(0.08, 0.08, 0.10, tip, center=(cx + dx, cy + dy, cz + 0.88), emissive=True))
    return m


def _ucilev_turbine_core_mesh():
    """Cracked dorsal twin-turbine nacelle housing glowing molten orange in Phase 3."""
    m = _CACHE.get("ucilev_turb")
    if m is not None:
        return m
    m = _CACHE["ucilev_turb"] = Mesh()
    cowl = (22, 22, 26)
    core = (255, 132, 38)
    hot = (255, 224, 142)
    m.add(box(2.26, 0.52, 1.38, cowl, center=(0.0, 2.55, 0.35)))
    for sx in (-1.0, 1.0):
        m.add(box(0.14, 0.42, 1.12, core, center=(sx * 1.14, 2.55, 0.35), emissive=True))
        m.add(box(0.10, 0.22, 0.72, hot, center=(sx * 1.18, 2.56, 0.32), emissive=True))
    m.add(box(1.56, 0.18, 1.16, core, center=(0.0, 2.84, 0.30), emissive=True))
    return m


def tactical_lmg_mesh(base_mesh):
    """Dark gunmetal LMG with clear front post + open-window reflex optic."""
    m = _CACHE.get("tlmg_optic")
    if m is not None:
        return m
    m = Mesh()
    m.verts = list(base_mesh.verts)
    kept = []
    for f in base_mesh.faces:
        pts = [m.verts[i] for i in f[0]]
        if (all(-0.052 <= p[2] <= -0.047 and abs(p[0]) <= 0.011 for p in pts)
                and any(p[1] > 0.140 for p in pts)):
            continue
        col = f[1]
        if isinstance(col, (tuple, list)) and len(col) >= 3:
            avg = (col[0] + col[1] + col[2]) / 3.0
            if avg > 150:
                col = (int(col[0] * 0.34), int(col[1] * 0.36), int(col[2] * 0.40))
        kept.append((f[0], col) + tuple(f[2:]))
    m.faces = kept

    dark = (30, 34, 40)
    steel = (52, 58, 66)
    hood = (38, 42, 48)

    # Restore center front sight post between protective wings + tritium tip
    m.add(box(0.0036, 0.017, 0.004, (28, 32, 36), center=(0.0, 0.128, 0.545)))
    m.add(box(0.0032, 0.0034, 0.0036, (145, 245, 155), center=(0.0, 0.137, 0.545), emissive=True))

    # Open-window holographic / reflex sight mounted on the top Picatinny rail
    m.add(box(0.036, 0.014, 0.104, dark, center=(0.0, 0.133, 0.040)))
    for bz in (0.008, 0.070):
        m.add(box(0.004, 0.006, 0.008, (74, 80, 88), center=(-0.019, 0.133, bz)))
    m.add(box(0.008, 0.016, 0.052, steel, center=(0.028, 0.147, 0.040)))
    m.add(box(0.050, 0.0045, 0.036, hood, center=(0.0, 0.1415, OPTIC_Z)))
    m.add(box(0.016, 0.003, 0.012, (22, 24, 28), center=(0.0, 0.143, 0.022)))
    m.add(box(0.051, 0.0045, 0.032, hood, center=(0.0, 0.1805, OPTIC_Z)))
    m.add(box(0.044, 0.0025, 0.028, steel, center=(0.0, 0.1835, OPTIC_Z)))
    for sx in (-1.0, 1.0):
        m.add(box(0.0040, 0.038, 0.034, hood, center=(sx * 0.0235, 0.1605, OPTIC_Z)))
    _CACHE["tlmg_optic"] = m
    return m


def _reticle_surface(px):
    """Crisp pixel-exact holographic reticle surface cached by pixel size."""
    px = max(7, int(px))
    surf = _RETICLE_CACHE.get(px)
    if surf is not None:
        return surf
    if len(_RETICLE_CACHE) > 48:
        _RETICLE_CACHE.popitem(last=False)
    surf = pygame.Surface((px, px), pygame.SRCALPHA)
    c = px // 2
    r = max(3, int(round(px * 0.36)))
    w = 2 if px >= 30 else 1
    halo = (255, 72, 42, 72)
    ring = (255, 96, 58, 240)
    core = (255, 236, 196, 255)
    pygame.draw.circle(surf, halo, (c, c), r, w + 2)
    pygame.draw.circle(surf, ring, (c, c), r, w)
    gap = max(2, r // 3)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        pygame.draw.line(surf, (0, 0, 0, 0),
                         (c + dx * (r - 2), c + dy * (r - 2)),
                         (c + dx * (r + 2), c + dy * (r + 2)), w + 2)
        pygame.draw.line(surf, ring,
                         (c + dx * max(2, r - gap), c + dy * max(2, r - gap)),
                         (c + dx * (r + 1), c + dy * (r + 1)), 1)
    if px >= 18:
        pygame.draw.rect(surf, core, (c - 1, c - 1, 2, 2))
    else:
        surf.set_at((c, c), core)
    _RETICLE_CACHE[px] = surf
    return surf


def gunner_eye(hpos, hmat, rel_yaw_deg, ads, t, shake, reduced_motion=False,
               gp=-12.0, gy_world=None):
    """Starboard door-gunner eye positioned physically behind the receiver/stock
    around PINTLE_PIVOT_LOCAL, shifting cleanly along the receiver axis into the
    open reflex optic window (SIGHT_Y, OPTIC_Z) on RMB ADS."""
    pivot_w = v_add(hpos, m_apply(hmat, PINTLE_PIVOT_LOCAL))
    if gy_world is not None:
        f = R._fwd(gy_world, gp)
        rg = R._right(gy_world)
    else:
        f_loc = R._fwd(rel_yaw_deg, gp)
        rg_loc = R._right(rel_yaw_deg)
        f = m_apply(hmat, f_loc)
        rg = m_apply(hmat, rg_loc)
    up = (
        f[1] * rg[2] - f[2] * rg[1],
        f[2] * rg[0] - f[0] * rg[2],
        f[0] * rg[1] - f[1] * rg[0],
    )
    ads_k = _ease(ads)
    back = 0.56 + (0.44 - 0.56) * ads_k
    up_ads = SIGHT_Y - TRUNNION_LOCAL[1]
    up_off = 0.295 + (up_ads - 0.295) * ads_k
    side_off = -0.125 * (1.0 - ads_k)
    vib = (0.006 if not reduced_motion else 0.0) * (1.0 - 0.85 * ads_k)
    vx = math.sin(t * 43.0) * (vib + 0.026 * shake)
    vy = math.cos(t * 37.0) * (vib + 0.026 * shake)
    return (
        pivot_w[0] - f[0] * back + up[0] * (up_off + vy) + rg[0] * (side_off + vx),
        pivot_w[1] - f[1] * back + up[1] * (up_off + vy) + rg[1] * (side_off + vx),
        pivot_w[2] - f[2] * back + up[2] * (up_off + vy) + rg[2] * (side_off + vx),
    )


def lmg_xform(eye_w, gy_world, gp, scene, hpos=None, hmat=None):
    """Return ``(basis, at, tip, ads_k)`` for the fixed-trunnion pintle LMG.

    Locks the LMG's under-receiver trunnion lug strictly to ``pivot_w`` on the
    starboard doorway sill, damping recoil linearly/pitch-wise inside the cradle.
    """
    ads_k = _ease(getattr(scene, "ads", 0.0))
    if hpos is None or hmat is None:
        hpos = scene._heli_pos()
        hyaw = scene._heli_yaw()
        hpitch, hroll = scene._heli_tilt()
        hmat = heli_matrix(hyaw, hpitch, hroll)
    pivot_w = v_add(hpos, m_apply(hmat, PINTLE_PIVOT_LOCAL))
    age_shot = getattr(scene, "t", 0.0) - getattr(scene, "last_fire", -9.0)
    kick_z = (0.032 * (1.0 - 0.40 * ads_k)) * math.exp(-age_shot * 28.0) if 0.0 <= age_shot < 0.22 else 0.0
    kick_p = (2.1 * (1.0 - 0.68 * ads_k)) * math.exp(-age_shot * 18.0) if 0.0 <= age_shot < 0.28 else 0.0
    basis = m_mul(rot_y(gy_world), rot_x(-(gp + kick_p)))
    trun_off = m_apply(basis, (TRUNNION_LOCAL[0], TRUNNION_LOCAL[1], TRUNNION_LOCAL[2] + kick_z))
    at = (pivot_w[0] - trun_off[0], pivot_w[1] - trun_off[1], pivot_w[2] - trun_off[2])
    tip = v_add(at, m_apply(basis, BORE_LOCAL))
    return basis, at, tip, ads_k


def draw_cabin_and_gun(r, scene, hpos, hmat, hyaw, eye_w, gy_world, gp, lmg_mesh, tm,
                       hpitch=None, hroll=None):
    """Render the intact starboard-door maru_gunship.glb bay, interior accents,
    Maru, fixed-trunnion sill pintle, linked ammo belt, hands, LMG, and FX."""
    if hpitch is None or hroll is None:
        hpitch, hroll = scene._heli_tilt()
    _, _, _, _, info = CS.maru_gunship_parts()
    # CS._xf/_rot_rt use rot_z(+roll) while FX.heli_matrix uses rot_z(-roll) -> pass -hroll
    CS.put_maru_gunship(r, hpos, hyaw, hpitch, -hroll,
                        scene.rotor, (scene.rotor * 1.8) % 360.0, fpv=True)
    _submit(r, "maru_accents", _maru_interior_accents(info), hmat, hpos)

    # Subtle high outer blade-tip disc blur far outside the roof edge when pitching upward
    if gp > 2.0:
        hub_y = float(info.get("main_hub", (0.0, 3.03, 0.25))[1])
        for i in range(4):
            ba = math.radians((scene.rotor + i * 90.0) % 360.0)
            lx = math.sin(ba) * 4.55
            lz = 0.25 + math.cos(ba) * 4.55
            if lx > 1.35:
                tip_p = v_add(hpos, m_apply(hmat, (lx, hub_y + 0.14, lz)))
                r.add_sprite(tip_p, _fx.haze((156, 166, 184), 0.52, int(tm),
                                             seed=410 + i, intensity=0.11), layer=2)

    # Maru in the GLB port cockpit seat
    maru_pos = v_add(hpos, m_apply(hmat, info.get("pilot_seat", (-0.42, 0.62, 1.92))))
    pose = dict(_PILOT_POSE)
    lines = getattr(scene, "lines", ())
    if lines and scene.t - lines[-1][0] < 2.2:
        pose["head_y"] = 22.0 * math.sin(scene.t * 2.5)
    _w.actor(r, "maru", pose, maru_pos, hyaw, int(tm), seed=71, amp=0.12,
             rifle_on=False, expression="stern")

    # Tail/roof beacon on Maru's gunship
    bcn = v_add(hpos, m_apply(hmat, info.get("roof_beacon", (0.0, 3.09, -6.18))))
    r.add_sprite(bcn, _fx.beacon((255, 62, 46), 0.34, int(tm), period_ms=920.0, phase=0.0),
                 layer=_fx.FX_LAYER)

    # Hull damage sparks & smoke inside the bay when heavily damaged or crashing
    if getattr(scene, "hull", 100.0) < 40.0 or getattr(scene, "shootdown", -1.0) >= 0.0:
        fy = float(info.get("floor_y", 0.574))
        spk_pos = v_add(hpos, m_apply(hmat, (-0.46, fy + 0.85, 2.05)))
        if int(tm * 0.02) % 3 == 0:
            r.add_sprite(spk_pos, _fx.glow((255, 198, 94), 0.22, int(tm),
                                           intensity=1.2, max_px=18), layer=_fx.FX_LAYER)

    # Fixed-trunnion pintle yoke + tactical LMG + gloved hands + dynamic brass ammo belt
    pivot_w = v_add(hpos, m_apply(hmat, PINTLE_PIVOT_LOCAL))
    _submit(r, "pintle_yoke", _pintle_yoke_mesh(), rot_y(gy_world), pivot_w)
    basis, at, tip, ads_k = lmg_xform(eye_w, gy_world, gp, scene, hpos=hpos, hmat=hmat)
    _submit(r, "tactical_lmg", lmg_mesh, basis, at)
    _submit(r, "gunner_hands", _gunner_hands_mesh(), basis, at)
    p_box = v_add(hpos, m_apply(hmat, AMMO_FEED_LOCAL))
    p_tray = v_add(at, m_apply(basis, FEED_TRAY_LOCAL))
    _draw_ammo_belt(r, p_box, p_tray, basis)

    # Progressive barrel heat shroud glow + rising barrel heat haze
    if scene.heat > 0.30:
        hk = _clamp01((scene.heat - 0.30) / 0.70)
        col = (
            int(120 + 135 * hk),
            int(28 + 130 * (hk ** 1.6)),
            int(12 + 44 * (hk ** 2.4)),
        )
        _submit(r, ("hs_draw", int(hk * 8)), _heat_sleeve_mesh(col), basis, at)
    if scene.heat > 0.48 or scene.overheat:
        rate = 1.0 if scene.overheat else _clamp01((scene.heat - 0.48) / 0.52)
        for i in range(2):
            age_h = (scene.t * 1.4 + i * 0.5) % 1.0
            sp_pos = (
                tip[0] + math.sin(scene.t * 4.0 + i) * 0.06,
                tip[1] + 0.04 + age_h * 0.42,
                tip[2] + math.cos(scene.t * 3.5 + i) * 0.06,
            )
            r.add_sprite(sp_pos, _fx.haze((188, 192, 200), 0.06 + 0.14 * age_h, int(tm),
                                          seed=300 + i, intensity=0.35 * rate * (1.0 - age_h)),
                         layer=2)

    # Projected holographic reticle centered inside the open optic window
    if ads_k > 0.30:
        opt_pos = v_add(at, m_apply(basis, (0.0, SIGHT_Y, OPTIC_Z)))
        alpha = int(245 * _clamp01((ads_k - 0.30) / 0.45))

        def _reticle(surface, sx, sy, scale, z, _a=alpha):
            tile = _reticle_surface(int(round(0.023 * scale)))
            if _a < 255:
                tile = tile.copy()
                tile.set_alpha(_a)
            surface.blit(tile, (int(sx - tile.get_width() * 0.5),
                                int(sy - tile.get_height() * 0.5)))

        _reticle.bounds_m = (0.022, 0.022)
        _reticle.bounds_cap_px = (64, 64)
        r.add_sprite(opt_pos, _reticle, layer=2)

    # 3D axial muzzle flash rooted cleanly at the LMG bore
    age_shot = scene.t - scene.last_fire
    if 0.0 <= age_shot < 0.055:
        k = (1.0 - age_shot / 0.055) ** 1.4
        f_b = m_apply(basis, (0.0, 0.0, 1.0))
        rx_b = m_apply(basis, (1.0, 0.0, 0.0))
        ry_b = m_apply(basis, (0.0, 1.0, 0.0))
        fm = C.flash_star(tip, f_b, rx_b, ry_b, k, scene.flash_seed,
                          scale=0.82 - 0.36 * ads_k)
        _w.add(r, fm)
        r.add_sprite(v_add(tip, tuple(c * 0.16 for c in f_b)),
                     _fx.glow((255, 196, 98), 0.28, int(tm), core=(255, 248, 212),
                              intensity=(1.05 - 0.38 * ads_k) * k, max_px=34),
                     layer=_fx.FX_LAYER)
    return tip, basis


def draw_vip_helicopter(r, pos, yaw, pitch, roll, tm, tail_hp_frac=1.0, down_t=-1.0, target_tail=False):
    """Render Retardovici's VIP helicopter with nav lights, strobes, searchlight, and tail damage."""
    burned = down_t >= 0.0
    t_spin = (tm * 2.2) % 360.0 if not burned else 0.0
    CS.put_helicopter(r, pos, yaw, pitch, roll, (tm * 1.4) % 360.0, t_spin, burned=burned)

    # Port/starboard nav lights on tail stabilizer tips + belly/tail strobes
    r.add_sprite(CS._xf((-0.95, 2.35, -4.65), pos, yaw, pitch, roll),
                 _fx.glow((255, 62, 50), 0.42, int(tm), intensity=1.0, max_px=18), layer=_fx.FX_LAYER)
    r.add_sprite(CS._xf((0.95, 2.35, -4.65), pos, yaw, pitch, roll),
                 _fx.glow((64, 244, 118), 0.42, int(tm), intensity=1.0, max_px=18), layer=_fx.FX_LAYER)
    r.add_sprite(CS._xf((0.0, 0.18, -1.6), pos, yaw, pitch, roll),
                 _fx.beacon((255, 68, 48), 0.36, int(tm), period_ms=820.0, phase=0.0), layer=_fx.FX_LAYER)

    # Sweeping nose searchlight cone
    nose = CS._xf((0.0, 0.58, 4.90), pos, yaw, pitch, roll)
    r.add_sprite(nose, _fx.glow((238, 246, 255), 0.56, int(tm), intensity=1.15, max_px=24),
                 layer=_fx.FX_LAYER)
    for idx, dist in enumerate((3.0, 6.8, 11.5)):
        bp = CS._xf((0.0, 0.58 - dist * 0.52, 4.90 + dist * 0.85), pos, yaw, pitch, roll)
        r.add_sprite(bp, _fx.haze((208, 224, 255), 0.60 + dist * 0.18, int(tm),
                                  seed=910 + idx, intensity=0.20 * (1.0 - idx * 0.24)), layer=_fx.FX_LAYER)

    _b, _m, _t, info = CS.helicopter_parts()
    tp = CS._xf(info["tail_hub"], pos, yaw, pitch, roll)
    if burned:
        F3D.emit_fire(r, tp, tm, seed=33, size=1.65, heat=1.45, smoky=True, embers=True, bed=False, layer=2)
    elif tail_hp_frac < 0.72:
        F3D.emit_fire(r, tp, tm, seed=33, size=0.90 + 0.75 * (1.0 - tail_hp_frac),
                      heat=0.85 + 0.65 * (1.0 - tail_hp_frac), smoky=True,
                      embers=(tail_hp_frac < 0.48), bed=False, layer=2)
    elif target_tail:
        r.add_sprite(tp, _fx.glow((255, 96, 68), 0.95, int(tm), pulse=0.5,
                                  core=(255, 224, 180), max_px=32), layer=_fx.FX_LAYER)


def draw_aa_truck(r, pos, yaw, heli_pos, alive, tm, seed=0, hp_frac=1.0,
                  pitch=0.0, roll=0.0, turret_blown=False, draw_fire=True):
    """Draw a distinct M7 AA gun-truck with long sweeping searchlight beam."""
    if alive:
        CS.put_wheeled(r, "gun_truck", pos, yaw, pitch, 0.0, roll)
        turret_at = CS._xf((0.0, 2.05, -0.55), pos, yaw, pitch, roll)
        dx = heli_pos[0] - turret_at[0]
        dy = (heli_pos[1] + 0.8) - turret_at[1]
        dz = heli_pos[2] - turret_at[2]
        sweep = 7.0 * math.sin(tm * 0.0018 + seed * 1.7)
        tyaw = math.degrees(math.atan2(dx, dz)) + sweep
        tpitch = clamp(math.degrees(math.atan2(dy, max(1.0, math.hypot(dx, dz)))), -10.0, 68.0)
        tmat = m_mul(rot_y(tyaw), rot_x(-tpitch))
        _submit(r, "aa_turret_on", _aa_turret_mesh(True), tmat, turret_at)
        lens_w = v_add(turret_at, m_apply(tmat, (0.0, 0.72, 0.42)))
        r.add_sprite(lens_w, _fx.glow((224, 238, 255), 1.15, int(tm), core=(255, 255, 248),
                                      intensity=1.45, max_px=48), layer=_fx.FX_LAYER)
        bdir = m_apply(tmat, (0.0, 0.0, 1.0))
        for k, (dist_m, rad_m, inten) in enumerate((
            (2.5, 0.65, 0.30),
            (6.0, 1.05, 0.24),
            (10.5, 1.55, 0.18),
            (16.0, 2.15, 0.13),
            (22.5, 2.80, 0.09),
            (30.0, 3.50, 0.06),
        )):
            bp = (
                lens_w[0] + bdir[0] * dist_m,
                lens_w[1] + bdir[1] * dist_m,
                lens_w[2] + bdir[2] * dist_m,
            )
            r.add_sprite(bp, _fx.haze((188, 210, 242), rad_m, int(tm),
                                      seed=seed * 13 + k, intensity=inten), layer=_fx.FX_LAYER)
        for sx in (-0.68, 0.68):
            hl = CS._xf((sx, 1.05, 2.95), pos, yaw, pitch, roll)
            r.add_sprite(hl, _fx.glow((255, 228, 176), 0.48, int(tm), core=(255, 248, 228),
                                      intensity=0.85, max_px=20), layer=_fx.FX_LAYER)
        if hp_frac < 0.55:
            F3D.emit_fire(r, (pos[0], pos[1] + 1.4, pos[2]), tm, seed=510 + seed,
                          size=0.85, heat=0.85, smoky=True, embers=(hp_frac < 0.30),
                          bed=False, layer=2)
    else:
        CS.put_wheeled(r, "gun_truck_burnt", pos, yaw, pitch, 0.0, roll)
        if not turret_blown:
            turret_at = CS._xf((0.0, 2.05, -0.55), pos, yaw, pitch, roll)
            _submit(r, "aa_turret_off", _aa_turret_mesh(False), rot_y(yaw + 25.0), turret_at)
        if draw_fire:
            F3D.emit_fire(r, (pos[0], pos[1] + 1.0, pos[2]), tm, seed=500 + seed,
                          size=1.45, heat=1.2, smoky=True, embers=True, bed=True, layer=2)


def draw_tanker(r, pos, yaw, alive, tm, seed=0, pitch=0.0, roll=0.0, draw_fire=True):
    """Draw a volatile red-striped fuel tanker (chain-explosive priority target)."""
    CS.put_wheeled(r, "gun_truck" if alive else "gun_truck_burnt", pos, yaw, pitch, 0.0, roll)
    tmat = m_mul(rot_y(yaw), m_mul(rot_x(-pitch), rot_z(roll))) if (pitch or roll) else rot_y(yaw)
    _submit(r, ("tanker_body", alive), tanker_mesh(not alive), tmat, pos)
    if alive:
        for sx in (-0.68, 0.68):
            hl = CS._xf((sx, 1.05, 2.95), pos, yaw, pitch, roll)
            r.add_sprite(hl, _fx.glow((255, 226, 172), 0.48, int(tm), core=(255, 248, 228),
                                      intensity=0.85, max_px=20), layer=_fx.FX_LAYER)
        top = CS._xf((0.0, 3.25, -0.55), pos, yaw, pitch, roll)
        r.add_sprite(top, _fx.beacon((255, 128, 42), 0.68, int(tm), period_ms=720.0,
                                     phase=seed * 53.0), layer=_fx.FX_LAYER)
    elif draw_fire:
        F3D.emit_fire(r, (pos[0], pos[1] + 1.3, pos[2]), tm, seed=620 + seed,
                      size=2.1, heat=1.55, smoky=True, embers=True, bed=True, layer=2)


def draw_rocket(r, rk, now, tm, flash_reduction=False):
    """High-visibility 2-stage spinning rocket + 3D motor flame + 32-seg contrail."""
    p = rk["p"]
    dx, dy, dz = rk.get("dir", (0.0, 0.0, 1.0))
    yaw = math.degrees(math.atan2(dx, dz))
    pitch = math.degrees(math.atan2(dy, max(1e-4, math.hypot(dx, dz))))
    roll = ((now - rk["t0"]) * 520.0 + rk.get("id_seed", 0) * 37.0) % 360.0
    rmat = m_mul(rot_y(yaw), m_mul(rot_x(-pitch), rot_z(roll)))
    _submit(r, "rocket_body", CS.rocket(), rmat, p)

    phase = rk.get("phase", "cruise")
    boost_k = 1.28 if phase == "boost" else (1.12 if phase == "ballistic" else 1.0)
    fl_k = (0.78 + 0.22 * math.sin(now * 46.0 + rk.get("id_seed", 0))) * boost_k
    plume_m = _rocket_plume_mesh(rk.get("id_seed", 0), fl_k)
    _submit(r, ("rplume_sub", rk.get("id_seed", 0) % 4, int(round(fl_k * 6.0))), plume_m, rmat, p)
    tail = v_add(p, m_apply(rmat, (0.0, 0.0, -CS.ROCKET_LEN * 0.56)))
    nose = v_add(p, m_apply(rmat, (0.0, 0.0, CS.ROCKET_LEN * 0.48)))
    fk = 0.65 if flash_reduction else 1.0
    # Omnidirectional motor flare (extra punch during Stage-1 boost & doorway flyby)
    r.add_sprite(tail, _fx.glow((255, 162, 58), 1.85 * boost_k, int(tm), flicker=0.30,
                                core=(255, 254, 232), intensity=2.35 * boost_k * fk,
                                max_px=38 if flash_reduction else 52),
                 layer=_fx.FX_LAYER)
    r.add_sprite(nose, _fx.glow((255, 96, 48), 0.85, int(tm), pulse=0.35,
                                core=(255, 240, 200), intensity=1.70 * fk, max_px=24),
                 layer=_fx.FX_LAYER)

    # Smooth 32-segment contrail ribbon tracing the missile cleanly back to its launcher
    trail = rk.get("trail", ())
    if trail:
        pts = list(trail) + [p]
        n_seg = len(pts) - 1
        for i in range(n_seg):
            u = (i + 1) / float(n_seg)
            if u > 0.72:
                col = (255, int(178 + 65 * u), int(88 + 115 * u))
                w_px = 3
            elif u > 0.30:
                c_g = int(130 + 100 * u)
                col = (min(255, c_g + 24), min(255, c_g + 12), c_g)
                w_px = 2
            else:
                c_g = int(95 + 115 * u)
                col = (c_g + 14, c_g + 10, c_g)
                w_px = 1
            r.add_line3d(pts[i], pts[i + 1], col, w_px, layer=2)

    for px, py, pz, born, pseed in rk.get("puffs", ()):
        age = now - born
        if not (0.0 <= age < 2.35):
            continue
        u = age / 2.35
        fade = _clamp01(age / 0.04) * ((1.0 - u) ** 1.15)
        alpha = int(212 * fade) // 8 * 8
        if alpha < 8:
            continue
        rad_m = 0.58 + 2.25 * math.sqrt(u)
        warmth = max(0, min(4, int((1.0 - u * 3.2) * 4.0)))
        img_fn = _rocket_puff_fn(warmth, pseed, rad_m, alpha)
        r.add_sprite((px, py + age * 0.60, pz), img_fn, layer=2)


def draw_launch_backblasts(r, backblasts, now, tm, flash_reduction=False):
    """Unmistakable bright orange backblast flash + rising white exhaust column at launch origin."""
    fk = 0.55 if flash_reduction else 1.0
    for item in backblasts:
        t0, pos, seed = item[0], item[1], item[2]
        kind = item[3] if len(item) > 3 else "sam"
        air = item[4] if len(item) > 4 else False
        age = now - t0
        if not (0.0 <= age < 1.55):
            continue
        flash_dur = 0.32 if kind == "rpg" else 0.42
        if age < flash_dur:
            u_f = 1.0 - age / flash_dur
            rad_f = (2.2 if kind == "rpg" else 2.8) * (0.7 + 0.6 * (1.0 - u_f))
            r.add_sprite((pos[0], pos[1] + 0.35, pos[2]),
                         _fx.glow((255, 158, 52), rad_f, int(tm),
                                  core=(255, 252, 224),
                                  intensity=(2.45 if not air else 1.85) * (u_f ** 1.3) * fk,
                                  max_px=46 if flash_reduction else 74),
                         layer=_fx.FX_LAYER)
        # Rising white exhaust column marking the rooftop / AA truck launcher
        n_col = 3 if air else 4
        for k in range(n_col):
            ca = age - k * 0.04
            if ca <= 0.0:
                continue
            cu = min(1.0, ca / 1.45)
            alpha = int(208 * _clamp01(ca / 0.05) * ((1.0 - cu) ** 1.15)) // 8 * 8
            if alpha < 8:
                continue
            rad_m = (0.75 + 0.25 * k) + (1.85 + 0.35 * k) * math.sqrt(cu)
            lift = (0.35 + k * 0.65) + ca * (1.6 + k * 0.55) if not air else (-0.25 * k + ca * 0.65)
            warm = 3 if ca < 0.18 else (1 if ca < 0.42 else 0)
            r.add_sprite((pos[0], pos[1] + lift, pos[2]),
                         _rocket_puff_fn(warm, seed + k, rad_m, alpha), layer=2)


def _rocket_puff_fn(warmth, seed, rad_m, alpha):
    def draw(s, sx, sy, scale, z):
        rad = max(4, min(84, int(rad_m * scale)))
        if rad < 3:
            return
        surf = F3D.smoke_puff_surface(warmth, seed % 6, rad, alpha, shade_col=(204, 206, 218))
        s.blit(surf, (int(sx - rad), int(sy - rad)))
    draw.bounds_m = (rad_m * 1.15, rad_m * 1.15)
    draw.bounds_cap_px = (144, 144)
    return draw


def draw_booms_and_debris(r, booms, debris, puffs, brass, now, tm, flash_reduction=False):
    """Volumetric multi-stage fireballs, shrapnel debris, smoke plumes, and brass casings."""
    for b in booms:
        t0, pos, rad = b[0], b[1], b[2]
        seed = b[3] if len(b) > 3 else int(t0 * 100)
        kind = b[4] if len(b) > 4 else "boom"
        age = now - t0
        if age < 0.0 or age > 3.2:
            continue
        bx, by, bz = pos
        sc = clamp(rad / 3.5, 0.55, 2.2)

        flash_dur = 0.30 if not flash_reduction else 0.22
        if age < flash_dur:
            fk = (1.0 - age / flash_dur) ** 1.7
            inten = (1.1 if flash_reduction else 2.4) * fk
            r.add_sprite((bx, by + 0.5, bz),
                         _fx.flash(age * 1000.0, col=(255, 214, 138),
                                   radius_m=rad * (0.9 if flash_reduction else 1.3),
                                   dur_ms=int(flash_dur * 1000)),
                         layer=_fx.FX_LAYER)
            r.add_sprite((bx, by + 0.6, bz),
                         _fx.glow((255, 168, 62), rad * (0.75 + age * 1.8), int(tm),
                                  core=(255, 250, 224), intensity=inten, max_px=150 if flash_reduction else 210),
                         layer=_fx.FX_LAYER)

        fb_dur = 1.35 * min(1.4, sc)
        if age < fb_dur:
            lobes = 5 if kind == "tanker" else (4 if kind != "rocket" else 2)
            for i in range(lobes):
                a = age - 0.03 * i
                if a < 0.0:
                    continue
                ang = i * 2.39996 + seed * 0.2
                exp_k = 1.0 - math.exp(-a * 6.0)
                col_k = 1.0 - _ease(_clamp01((a - 0.32 * sc) / max(0.25, fb_dur - 0.35 * sc)))
                fsize = (0.55 + 0.72 * exp_k) * sc * col_k
                spread = (0.25 + 1.25 * exp_k) * sc
                if fsize > 0.08:
                    F3D.emit_fire(
                        r,
                        (bx + math.cos(ang) * spread, max(0.05, by + a * 1.35), bz + math.sin(ang) * spread),
                        tm, seed=seed + i * 17, size=fsize, heat=1.25 * col_k + 0.2,
                        smoky=False, embers=(i == 0), bed=False, glow=False, layer=2,
                    )

        if age < 1.5:
            r.add_sprite(pos, F3D.embers_sprite(tm, seed=seed + 9, spread_m=1.4 * sc,
                                                height_m=3.2 * sc, n=12, heat=max(0.2, 1.2 - age * 0.8)),
                         layer=2)

    if debris:
        dm = Mesh()
        for d in debris:
            hot = d["hot"] and (now - d["t0"]) < 1.15
            col = (248, 138, 48) if hot else d["col"]
            dm.add(box(d["sx"], d["sy"], d["sz"], col, emissive=hot),
                   m_mul(rot_y(d["ry"]), rot_x(d["rx"])), (d["x"], d["y"], d["z"]))
        _w.add(r, dm)

    if brass:
        bm = Mesh()
        for br in brass:
            bm.add(box(0.014, 0.014, 0.052, (224, 186, 78), emissive=False),
                   rot_y(br["ry"]), (br["x"], br["y"], br["z"]))
        _w.add(r, bm)

    for pf in puffs:
        age = now - pf["born"]
        if not (0.0 <= age < pf["dur"]):
            continue
        u = age / pf["dur"]
        alpha = int(pf["alpha"] * _clamp01(age / 0.14) * ((1.0 - u) ** 1.25)) // 8 * 8
        if alpha < 8:
            continue
        rad_m = pf["r0"] + (pf["r1"] - pf["r0"]) * math.sqrt(u)
        warmth = max(0, min(4, int(pf["warm"] * (1.0 - u * 2.2))))
        r.add_sprite((pf["x"], pf["y"], pf["z"]), _smoke_puff_fn(warmth, pf["seed"], rad_m, alpha), layer=2)


def _smoke_puff_fn(warmth, seed, rad_m, alpha):
    def draw(s, sx, sy, scale, z):
        rad = max(3, min(86, int(rad_m * scale)))
        if rad < 3:
            return
        surf = F3D.smoke_puff_surface(warmth, seed % 6, rad, alpha, shade_col=(44, 44, 48))
        s.blit(surf, (int(sx - rad), int(sy - rad)))
    draw.bounds_m = (rad_m * 1.15, rad_m * 1.15)
    draw.bounds_cap_px = (172, 172)
    return draw


def draw_flak_bursts(r, bursts, now, tm, flash_reduction=False):
    """Render dramatic mid-air AA flak detonations (incandescent snap + dark smoke cloud)."""
    for t0, pos, seed in bursts:
        age = now - t0
        if not (0.0 <= age < 1.45):
            continue
        if age < 0.22:
            fk = (1.0 - age / 0.22) ** 1.5
            inten = (1.0 if flash_reduction else 2.2) * fk
            r.add_sprite(pos, _fx.glow((255, 168, 68), 1.6 + age * 4.5, int(tm),
                                       core=(255, 250, 224), intensity=inten,
                                       max_px=72 if flash_reduction else 118),
                         layer=_fx.FX_LAYER)
        u = age / 1.45
        alpha = int(192 * _clamp01(age / 0.05) * ((1.0 - u) ** 1.15)) // 8 * 8
        if alpha >= 8:
            rad_m = 0.85 + 2.6 * math.sqrt(u)
            warmth = 3 if age < 0.26 else (1 if age < 0.55 else 0)
            r.add_sprite((pos[0], pos[1] + age * 0.45, pos[2]),
                         _smoke_puff_fn(warmth, seed, rad_m, alpha), layer=2)


def draw_flares(r, flares, now, tm):
    """Draw decoy flares with magnesium cores, dynamic illumination, and smoke ribbons."""
    for fl in flares:
        age = now - fl["t0"]
        if not (0.0 <= age < fl["dur"]):
            continue
        pos = fl["pos"]
        k = 1.0 - (age / fl["dur"]) ** 1.8
        r.add_sprite(pos, _fx.glow((255, 220, 128), 1.65 * k + 0.45, int(tm),
                                   flicker=0.45, core=(255, 255, 244),
                                   intensity=1.95 * k, max_px=64),
                     layer=_fx.FX_LAYER)
        for sx, sy, sz, born, sseed in fl.get("trail", ()):
            sage = now - born
            if 0.0 <= sage < 1.4:
                su = sage / 1.4
                a = int(148 * _clamp01(sage / 0.05) * ((1.0 - su) ** 1.25)) // 8 * 8
                if a >= 8:
                    r.add_sprite((sx, sy + sage * 0.4, sz),
                                 _rocket_puff_fn(1 if su < 0.25 else 0, sseed, 0.26 + 1.05 * su, a),
                                 layer=2)


def draw_ucilev_fx(r, pos, yaw, pitch, roll, tm, subs, phase, *,
                   player_pos=None, sweeping=False, rk_tele=False, tele=0.0,
                   sub_hit_t=-9.0, hit_part=None, now=0.0, seed=99):
    """Render Ucilev's elite commander trim, destructible mounted subsystems, and battle damage."""
    umat = cs_matrix(yaw, pitch, roll)
    _submit(r, "ucilev_trim", _ucilev_trim_mesh(), umat, pos)

    spot_hp = float(subs.get("spotlight", 0.0))
    if spot_hp > 0.0:
        _submit(r, "ucilev_spot", _ucilev_spotlight_mesh(), umat, pos)
        nose = CS._xf((0.0, 0.56, 6.08), pos, yaw, pitch, roll)
        inten = 2.45 if sweeping else 1.80
        mpx = 86 if sweeping else 66
        r.add_sprite(nose, _fx.glow((235, 244, 255), 1.75 if sweeping else 1.55, int(tm),
                                      pulse=0.35, core=(255, 255, 255), intensity=inten, max_px=mpx),
                     layer=_fx.FX_LAYER)
        b_dir = None
        if sweeping and player_pos is not None:
            dx = player_pos[0] - nose[0]
            dy = (player_pos[1] + 0.7) - nose[1]
            dz = player_pos[2] - nose[2]
            dm = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
            b_dir = (dx / dm, dy / dm, dz / dm)
        for idx, dist in enumerate((3.5, 8.5, 14.5, 22.0, 30.5, 39.5)):
            if b_dir is not None:
                bp = (nose[0] + b_dir[0] * dist, nose[1] + b_dir[1] * dist, nose[2] + b_dir[2] * dist)
            else:
                bp = CS._xf((0.0, 0.56 - dist * 0.14, 6.08 + dist * 0.98), pos, yaw, pitch, roll)
            r.add_sprite(bp, _fx.haze((212, 230, 255), 0.76 + dist * (0.19 if sweeping else 0.16),
                                      int(tm), seed=960 + idx,
                                      intensity=(0.36 if sweeping else 0.28) * max(0.22, 1.0 - idx * 0.14)),
                         layer=_fx.FX_LAYER)
    else:
        spot_w = CS._xf((0.0, 0.56, 5.72), pos, yaw, pitch, roll)
        F3D.emit_fire(r, spot_w, tm, seed=seed + 1, size=0.65, heat=0.9,
                      smoky=True, embers=False, bed=False, layer=2)

    for pkey, side in (("pod_l", -1.0), ("pod_r", 1.0)):
        pod_w = CS._xf((side * 1.68, 1.05, 0.98), pos, yaw, pitch, roll)
        if float(subs.get(pkey, 0.0)) > 0.0:
            _submit(r, pkey, _ucilev_pod_mesh(side), umat, pos)
            if rk_tele:
                pod_tip = CS._xf((side * 1.68, 1.05, 1.88), pos, yaw, pitch, roll)
                r.add_sprite(pod_tip, _fx.glow((255, 118, 48), 0.92, int(tm), flicker=0.45,
                                                 core=(255, 248, 220), intensity=1.75, max_px=34),
                             layer=_fx.FX_LAYER)
        else:
            F3D.emit_fire(r, pod_w, tm, seed=seed + (3 if side < 0 else 7),
                          size=1.02, heat=1.3, smoky=True, embers=True, bed=False, layer=2)
            r.add_sprite(pod_w, _fx.glow((255, 138, 48), 1.35, int(tm), flicker=0.35,
                                         core=(255, 224, 152), intensity=1.15, max_px=38),
                         layer=_fx.FX_LAYER)

    if phase >= 3 or float(subs.get("turbine", 1.0)) <= 0.0:
        _submit(r, "ucilev_turb", _ucilev_turbine_core_mesh(), umat, pos)
        turb_w = CS._xf((0.0, 2.55, 0.35), pos, yaw, pitch, roll)
        F3D.emit_fire(r, turb_w, tm, seed=seed + 11, size=1.45, heat=1.55,
                      smoky=True, embers=True, bed=False, layer=2)
        r.add_sprite(turb_w, _fx.glow((255, 136, 44), 2.1, int(tm), flicker=0.35,
                                      core=(255, 236, 174), intensity=1.65, max_px=62),
                     layer=_fx.FX_LAYER)
        r.add_sprite(turb_w, F3D.embers_sprite(tm, seed=94, spread_m=2.6, height_m=3.0, n=16, heat=1.35),
                     layer=2)

    if tele > 0.0:
        chin = CS._xf((0.0, 0.62, 4.95), pos, yaw, pitch, roll)
        r.add_sprite(chin, _fx.glow((255, 92, 56), 0.85, int(tm), flicker=0.55,
                                      core=(255, 228, 182), intensity=1.5, max_px=38),
                     layer=_fx.FX_LAYER)

    anchors = {
        "spotlight": (0.0, 0.56, 5.72),
        "pod_l": (-1.68, 1.05, 0.98),
        "pod_r": (1.68, 1.05, 0.98),
        "turbine": (0.0, 2.55, 0.35),
    }
    if now - sub_hit_t < 0.14 and hit_part in anchors:
        hw = CS._xf(anchors[hit_part], pos, yaw, pitch, roll)
        r.add_sprite(hw, _fx.glow((255, 242, 168), 1.55, int(tm), core=(255, 255, 245),
                                    intensity=1.95, max_px=56),
                     layer=_fx.FX_LAYER)


def draw_gunship(r, e, now, tm, draw_wreck_fire=True, player_pos=None):
    """Draw active, damaged, crashing, skidding, or crashed enemy gunship."""
    st = e.get("state", "fly")
    pos = (e["x"], e["y"], e["z"])
    yaw = e.get("yaw", 0.0)
    pitch = e.get("pitch", -4.0)
    roll = e.get("roll", 0.0)
    burned = st in ("skidding", "crashed")
    m_spin = (tm * 1.5) % 360.0 if st == "fly" else ((tm * 0.55) % 360.0 if st == "crashing" else 0.0)
    t_spin = (tm * 2.4) % 360.0 if st == "fly" else 0.0
    CS.put_helicopter(r, pos, yaw, pitch, roll, m_spin, t_spin, burned=burned)

    hp_frac = e["hp"] / max(1.0, float(e.get("max_hp", 240.0)))
    if st == "fly":
        # Wingtip nav lights
        r.add_sprite(CS._xf((-1.15, 0.85, 0.2), pos, yaw, pitch, roll),
                     _fx.glow((255, 62, 50), 0.36, int(tm), intensity=0.9, max_px=16), layer=_fx.FX_LAYER)
        r.add_sprite(CS._xf((1.15, 0.85, 0.2), pos, yaw, pitch, roll),
                     _fx.glow((64, 244, 118), 0.36, int(tm), intensity=0.9, max_px=16), layer=_fx.FX_LAYER)
        if e.get("ucilev"):
            draw_ucilev_fx(
                r, pos, yaw, pitch, roll, tm, e.get("subs", {}), e.get("phase", 1),
                player_pos=player_pos,
                sweeping=(e.get("maneuver") == "spotlight_sweep"),
                rk_tele=bool(e.get("rk_tele")),
                tele=float(e.get("tele", 0.0)),
                sub_hit_t=float(e.get("sub_hit_t", -9.0)),
                hit_part=e.get("sub_hit_part"),
                now=now,
                seed=int(e.get("seed", 99)),
            )
            if now - e.get("hit_t", -9.0) < 0.12 and now - e.get("sub_hit_t", -9.0) >= 0.12:
                r.add_sprite((e["x"], e["y"] + 1.3, e["z"]),
                             _fx.glow((220, 226, 238), 1.0, int(tm), core=(255, 255, 248),
                                      intensity=1.25, max_px=38),
                             layer=_fx.FX_LAYER)
            return
        if e.get("tele", 0.0) > 0.0:
            r.add_sprite((e["x"], e["y"] + 0.9, e["z"]),
                         _fx.glow((255, 86, 56), 0.82, int(tm), flicker=0.6,
                                  core=(255, 224, 180), intensity=1.4, max_px=36),
                         layer=_fx.FX_LAYER)
        if hp_frac < 0.62:
            F3D.emit_fire(r, (e["x"], e["y"] + 1.5, e["z"]), tm, seed=int(e.get("seed", 11)),
                          size=1.10, heat=1.1, smoky=True, embers=(hp_frac < 0.38),
                          bed=False, layer=2)
        if now - e.get("hit_t", -9.0) < 0.12:
            r.add_sprite((e["x"], e["y"] + 1.3, e["z"]),
                         _fx.glow((255, 232, 164), 1.35, int(tm), core=(255, 255, 240),
                                  intensity=1.65, max_px=52),
                         layer=_fx.FX_LAYER)
    elif st == "crashing":
        F3D.emit_fire(r, (e["x"], e["y"] + 1.1, e["z"]), tm, seed=int(e.get("seed", 19)),
                      size=1.45, heat=1.4, smoky=True, embers=True, bed=False, layer=2)
    elif st in ("skidding", "crashed") and draw_wreck_fire:
        F3D.emit_fire(r, (e["x"], e["y"] + 0.7, e["z"]), tm, seed=int(e.get("seed", 23)),
                      size=1.65, heat=1.2, smoky=True, embers=True, bed=True, layer=2)


def draw_gorge_snow(r, hpos, hv, now, reduced_motion=False, hyaw=0.0):
    """Diagonal high-altitude gale snow whipping across the Northern Ridge Gorge."""
    if reduced_motion or hv < 2.0:
        return
    col = (146, 164, 196)
    yr = math.radians(hyaw)
    fx, fz = math.sin(yr), math.cos(yr)
    rx, rz = math.cos(yr), -math.sin(yr)
    ln = 0.85
    for i in range(26):
        df = ((i * 1.75 - now * (hv * 0.85)) % 36.0) - 18.0
        ox = 3.4 + ((i * 67) % 23) * 0.85
        oy = (((i * 37) % 19 - 7) - (now * 3.8 + i * 0.4) % 9.0) * 0.45
        p0 = (
            hpos[0] + fx * df + rx * ox,
            max(2.0, hpos[1] + oy),
            hpos[2] + fz * df + rz * ox,
        )
        p1 = (p0[0] - fx * ln - rx * 0.24, p0[1] - 0.34, p0[2] - fz * ln - rz * 0.24)
        r.add_line3d(p0, p1, col, 1, layer=2)


def draw_air_streaks(r, hpos, hv, now, reduced_motion=False, hyaw=0.0):
    """Layered night mist/wind streaks flowing past the helicopter to convey airspeed."""
    if reduced_motion or hv < 2.0:
        return
    col = (56, 68, 92)
    yr = math.radians(hyaw)
    fx, fz = math.sin(yr), math.cos(yr)
    rx, rz = math.cos(yr), -math.sin(yr)
    ln = 1.45 if hv > 20.0 else 0.75
    for i in range(22):
        df = ((i * 2.1 - now * hv) % 44.0) - 22.0
        ox = ((i * 73) % 31 - 15) * 1.15
        oy = ((i * 41) % 15 - 5) * 0.55
        if abs(ox) < 3.4:
            ox += 3.8 if ox >= 0 else -3.8
        p0 = (
            hpos[0] + fx * df + rx * ox,
            max(2.0, hpos[1] + oy),
            hpos[2] + fz * df + rz * ox,
        )
        p1 = (p0[0] - fx * ln, p0[1], p0[2] - fz * ln)
        r.add_line3d(p0, p1, col, 1, layer=2)


def draw_radio_mast(r, z_pos, tm):
    """Landmark tall steel radio mast with blinking aviation warning beacons."""
    x = CS.road_x(z_pos) - 24.0
    m = _CACHE.get(("mast", int(z_pos)))
    if m is None:
        m = _CACHE[("mast", int(z_pos))] = Mesh()
        steel = (52, 58, 66)
        red = (164, 44, 40)
        white = (196, 194, 188)
        m.add(box(2.2, 1.4, 2.2, (74, 78, 82), center=(x, 0.7, z_pos)))
        for s in range(6):
            y0 = 1.4 + s * 6.5
            w = 1.6 - s * 0.16
            col = red if s % 2 else white
            m.add(box(w, 6.5, w, steel, center=(x, y0 + 3.25, z_pos)))
            m.add(box(w + 0.12, 0.35, w + 0.12, col, center=(x, y0 + 6.3, z_pos)))
        m.add(box(0.28, 7.0, 0.28, red, center=(x, 43.9, z_pos)))
    _w.add(r, m)
    for by in (24.0, 38.0, 47.2):
        r.add_sprite((x, by, z_pos), _fx.beacon((255, 58, 42), 0.75, int(tm), period_ms=1100.0,
                                                phase=by * 12.0), layer=_fx.FX_LAYER)
