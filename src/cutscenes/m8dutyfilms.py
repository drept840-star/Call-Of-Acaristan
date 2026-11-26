"""Mission 8 Duty 3D films: Approach, Liftoff, Crash (wooded ridge clearing +
grounded rifle handoff), and Duty Epilogue (Capital Square Palace of Justice).

Cameras are placed by ``_eye``: the letterbox buffer is ~2.2:1 and the engine
fov is horizontal, so a shot's vertical coverage is ``0.912 * d * tan(fov/2)``.
Every shot picks its vertical span in metres (face 0.75, medium close 1.3,
two-shot 1.6, wide 15) and let the distance fall out of that, instead of
guessing a distance and cropping heads.
"""
import math

import pygame
import traceback

from core.config import WIDTH
from core.outfits import OUTFIT_GUARD
from cutscenes import fire3d as _f3d
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from cutscenes import m7world3d as W7
from engine.anim import locomotion_pose, mask_pose
from engine3d import Mesh, POSES, blend, box
from engine3d.core import Light, m_apply, m_mul, rot_x, rot_y, rot_z, v_add
from engine3d.hold import GRIPS, POLES, hold_cached, hold_weapon, solve_arm_safe
from engine3d.ik import shoulder_world
from engine3d.rig import rifle_mesh, solve_look
from missions.m7 import raid3d as R
from missions.m8.duty import flight_fx as FX
from missions.m8.duty import mansion_set as MS
from missions.m8.revenge import chase_set as CS

from . import m8duty_crowd as DC
from . import m8duty_sets as DS

FILM = (640, int(_w.FILM_H * 640 / WIDTH))
BIRI = ("biribel", OUTFIT_GUARD)
BODI = ("ally", "bodi")
ALEX = ("ally", "alex")

_TLMG = []
_SNIPER_MESH = []
_VIP_OPEN = {}


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


def _sniper_prop():
    if not _SNIPER_MESH:
        try:
            from cutscenes.cast3d import weapon_asset
            mesh, _muzzle = weapon_asset("sniper_rifle")
        except Exception:
            mesh = None
        if mesh is None:
            mesh = rifle_mesh(scope=True)
        _SNIPER_MESH.append(mesh)
    return _SNIPER_MESH[0]


def _k(t, start, length):
    x = max(0.0, min(1.0, (t - start) / float(length)))
    return x * x * (3.0 - 2.0 * x)


def _mix(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def _eye(tgt, dirv, vspan, fov):
    """Camera eye ``vspan`` metres of vertical coverage away from ``tgt``.
    ``dirv`` is the view direction (eye -> target); the eye sits at
    ``tgt - dirv * d``.  The film buffer's aspect makes the vertical span
    0.912 * d * tan(fov/2), so d falls out of the framing."""
    d = vspan * FILM[0] / (2.0 * FILM[1] * math.tan(math.radians(fov) * 0.5))
    n = math.sqrt(sum(c * c for c in dirv)) or 1.0
    return tuple(t - c / n * d for t, c in zip(tgt, dirv))


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


def _finish_full(surface, r, bar_frac=0.0):
    """Full-frame gameplay-graded presentation with smoothly retracting letterbox bars
    for seamless zero-fade match-cuts into playable 3D scenes."""
    from core.config import HEIGHT, draw_vignette
    MS.present(r, surface)
    draw_vignette(surface)
    bh = int(round(_w.SAFE_TOP * max(0.0, min(1.0, bar_frac))))
    if bh > 0:
        surface.fill((0, 0, 0), (0, 0, WIDTH, bh))
        surface.fill((0, 0, 0), (0, HEIGHT - bh, WIDTH, bh))


def _guard_line(r, t):
    for gx, gz, gyaw in ((-3.4, -6.0, 180.0), (3.4, -6.0, 180.0), (-6.0, -26.0, 90.0), (6.0, -20.0, 270.0)):
        _w.actor(r, "guard", dict(POSES["ready"]), (gx, 0.0, gz), gyaw, int(t),
                 seed=int(abs(gx) * 10 + abs(gz)), rifle_on=True, flags=("os12",))


def approach_aerial(surface, t):
    """Aerial night orbit over Retardovici's estate: the drive, the house, the parked helicopter."""
    u = _k(t, 0, 5600)
    eye = _mix((20.0, 12.5, -24.0), (-22.0, 15.0, 14.0), u)
    tgt = _mix((0.0, 3.8, 4.0), (0.0, 5.0, 36.0), u)
    r = MS.frame(eye, tgt, 46.0, t=int(t), size=FILM)
    del _w.LAST[:]
    MS.draw_dynamic_props(r, t)
    CS.put_helicopter(r, MS.HELIPAD_AT, MS.HELI_YAW, 0.0, 0.0, 0.0, 0.0)
    _guard_line(r, t)
    _finish(surface, r, t, 1)


def approach_gate(surface, t):
    """Low at the gate: Biribel, Bodi and Alex stack up, then camera pushes smoothly
    into Biribel's over-the-shoulder MansionScene cp=0 start camera as bars retract."""
    u = _k(t, 0, 3000)
    push_u = _k(t, 2750, 1850)
    gz = MS.GATE_Z
    eye_cine = _mix((-2.6, 1.55, gz - 8.8), (-1.4, 1.64, gz - 6.2), u)
    tgt_cine = (0.3, 1.9, gz + 14.0)
    # Exact MansionScene cp=0 t=0 camera pose
    eye_play = (0.85, 1.8382, -44.0981)
    tgt_play = (0.85, 1.4892, -34.1042)
    eye = _mix(eye_cine, eye_play, push_u)
    tgt = _mix(tgt_cine, tgt_play, push_u)
    fov = 46.0 + (62.0 - 46.0) * push_u

    r = MS.frame(eye, tgt, fov, t=int(t))
    del _w.LAST[:]
    MS.draw_dynamic_props(r, t)
    CS.put_helicopter(r, MS.HELIPAD_AT, MS.HELI_YAW, 0.0, 0.0, 0.0, 0.0)
    _guard_line(r, t)

    step_u = _k(t, 2200, 2100)
    b_pos = _mix((-0.8, 0.0, gz - 4.0), (0.0, 0.0, -41.0), step_u)
    bd_pos = _mix((-2.1, 0.0, gz - 2.6), (-1.8, 0.0, -40.5), step_u)
    al_pos = _mix((2.1, 0.0, gz - 2.6), (1.8, 0.0, -40.5), step_u)

    bp = _w.hum(BIRI, flags=("os12",))
    _w.actor(r, BIRI, R._held(bp, dict(POSES["ready"]), "os12", "ready", ("m8_biri_os12", "ready")),
             b_pos, 0.0, int(t), seed=93, rifle_on=True, flags=("os12",))
    _w.actor(r, BODI, blend(POSES["crouch"], POSES["ready"], step_u), bd_pos,
             12.0 * (1.0 - step_u), int(t), seed=61, rifle_on=True, flags=("os12",))
    _w.actor(r, ALEX, blend(POSES["crouch"], POSES["ready"], step_u), al_pos,
             (348.0 + 12.0 * step_u) % 360.0, int(t), seed=62, rifle_on=True)
    _finish_full(surface, r, bar_frac=1.0 - push_u)


# --- Maru's gunship: the open-bay cabin the player flies, not the closed VIP hull ---

def _gunship(r, t, pos, yaw, pitch, roll, spin, burned=False, pilot=False,
             tail_on=True, main_on=True, fpv=False):
    _f, _b, _mr, _tr, info = CS.maru_gunship_parts()
    hmat = FX.heli_matrix(yaw, pitch, roll)
    # CS._xf/_rot_rt uses rot_z(+roll) while FX.heli_matrix uses rot_z(-roll)
    CS.put_maru_gunship(r, pos, yaw, pitch, -roll, spin, (spin * 1.65) % 360.0,
                        tail_on=tail_on, main_on=main_on, burned=burned, fpv=fpv)
    if not burned and tail_on:
        r.add_sprite(v_add(pos, m_apply(hmat, info["roof_beacon"])),
                     _fx.beacon((255, 72, 52), 0.30, int(t), period_ms=850.0),
                     layer=_fx.FX_LAYER)
    if pilot:
        _w.actor(r, "maru", dict(FX._PILOT_POSE), v_add(pos, m_apply(hmat, info["pilot_seat"])),
                 yaw, int(t), seed=71, amp=0.12, rifle_on=False, expression="stern")


# Liftoff: the in-game rise ends ~15 m over the pad; the films pick it up there.
def _reduced_motion():
    try:
        from core.user_settings import SETTINGS
        return bool(SETTINGS.reduced_motion)
    except Exception:
        return False


def _handheld(t, amp=0.04, roll_amp=0.8, seed=0):
    """Organic multi-harmonic rotor-wash / handheld camera tremor."""
    if _reduced_motion():
        return (0.0, 0.0, 0.0), 0.0
    s = t * 0.001
    dx = (math.sin(s * 11.3 + seed) * 0.55 + math.sin(s * 23.7 + seed * 1.7) * 0.45) * amp
    dy = (math.cos(s * 13.1 + seed * 0.9) * 0.55 + math.sin(s * 29.3 + seed * 2.1) * 0.45) * amp
    dz = (math.sin(s * 9.7 + seed * 1.3) * 0.6 + math.cos(s * 19.1 + seed) * 0.4) * amp * 0.6
    rl = (math.sin(s * 7.4 + seed * 1.4) * 0.65 + math.cos(s * 16.9 + seed * 0.5) * 0.35) * roll_amp
    return (dx, dy, dz), rl


def _rotor_wash(r, center, t, seed=0, n=14, radius=6.4, intensity=1.0):
    """Swirling downwash mist and radial grit streaks across the helipad deck."""
    s = t * 0.001
    cx, cy, cz = center
    for i in range(n):
        phase = (s * (1.35 + (i % 4) * 0.22) + i / float(n) + seed * 0.13) % 1.0
        ang = i * 2.39996 + s * 1.85 + phase * 1.4
        rad = 1.1 + phase * radius
        px = cx + math.cos(ang) * rad
        pz = cz + math.sin(ang) * rad
        py = cy + 0.16 + 0.85 * (phase ** 1.35) + 0.18 * math.sin(ang * 2.0 + s * 6.0)
        fade = math.sin(phase * math.pi)
        if i % 2 == 0:
            r.add_sprite((px, py, pz),
                         _fx.haze((174, 186, 208), 0.42 + 0.65 * phase, int(t),
                                  seed=seed * 31 + i, intensity=0.22 * fade * intensity),
                         layer=2)
        else:
            tx = -math.sin(ang) * 0.55 + math.cos(ang) * 0.72
            tz = math.cos(ang) * 0.55 + math.sin(ang) * 0.72
            ln = 0.55 + 0.75 * phase
            col = (int(142 * fade + 40), int(152 * fade + 42), int(172 * fade + 46))
            r.add_line3d((px, py, pz), (px + tx * ln, py + 0.12 * phase, pz + tz * ln),
                         col, 1, layer=2)


def _air_streaks(r, pos, hmat, t, seed=0, n=10):
    """High-speed night air streaks whipping past an airborne helicopter, kept
    clear of the central doorway sightline so no line cuts across the face."""
    if _reduced_motion():
        return
    s = t * 0.001
    for i in range(n):
        u = (s * (2.2 + (i % 3) * 0.45) + i * 0.173 + seed * 0.11) % 1.0
        # Place streaks above/below the cabin or behind the starboard flank
        band = i % 3
        if band == 0:
            lx, ly = 1.9 + (i % 4) * 0.65, -0.4 + ((i * 5) % 9) * 0.35
        elif band == 1:
            lx, ly = -2.2 - (i % 3) * 0.7, -0.35 - (i % 3) * 0.32
        else:
            lx, ly = -2.2 - (i % 3) * 0.7, 2.55 + (i % 3) * 0.35
        lz = 4.6 - u * 11.2
        p0 = v_add(pos, m_apply(hmat, (lx, ly, lz)))
        p1 = v_add(pos, m_apply(hmat, (lx, ly - 0.14, lz - 1.35)))
        r.add_line3d(p0, p1, (108, 124, 156), 1, layer=2)


def _heli_nav_lights(r, pos, yaw, pitch, roll, t, searchlight=True):
    """Port/starboard nav lamps (aft of the doorway), anti-collision strobes and landing light cone."""
    # Red port / green starboard navigation lights on tail stabilizer tips
    r.add_sprite(CS._xf((-0.95, 2.35, -4.65), pos, yaw, pitch, roll),
                 _fx.glow((255, 64, 52), 0.34, int(t), intensity=0.90, max_px=16),
                 layer=_fx.FX_LAYER)
    r.add_sprite(CS._xf((0.95, 2.35, -4.65), pos, yaw, pitch, roll),
                 _fx.glow((64, 244, 118), 0.34, int(t), intensity=0.90, max_px=16),
                 layer=_fx.FX_LAYER)
    # Anti-collision red strobes (belly + tail fin)
    r.add_sprite(CS._xf((0.0, 0.18, -1.6), pos, yaw, pitch, roll),
                 _fx.beacon((255, 68, 48), 0.30, int(t), period_ms=880.0, phase=0.0),
                 layer=_fx.FX_LAYER)
    r.add_sprite(CS._xf((0.20, 3.32, -5.05), pos, yaw, pitch, roll),
                 _fx.beacon((255, 68, 48), 0.32, int(t), period_ms=880.0, phase=440.0),
                 layer=_fx.FX_LAYER)
    if searchlight:
        nose = CS._xf((0.0, 0.56, 4.95), pos, yaw, pitch, roll)
        r.add_sprite(nose, _fx.glow((238, 246, 255), 0.52, int(t), intensity=1.15, max_px=26),
                     layer=_fx.FX_LAYER)
        for idx, dist in enumerate((2.4, 5.0, 8.2, 11.8)):
            bp = CS._xf((0.0, 0.56 - dist * 0.62, 4.95 + dist * 0.78), pos, yaw, pitch, roll)
            r.add_sprite(bp, _fx.haze((212, 226, 255), 0.55 + dist * 0.17, int(t),
                                      seed=700 + idx, intensity=0.22 * max(0.25, 1.0 - idx * 0.22)),
                         layer=_fx.FX_LAYER)


def _gunship_lights(r, pos, hmat, t, spot=1.0):
    """Maru's gunship nav lights, warm bay lamp, and nose searchlight flare."""
    r.add_sprite(v_add(pos, m_apply(hmat, (-1.85, 0.85, 0.35))),
                 _fx.glow((255, 64, 52), 0.32, int(t), intensity=0.85, max_px=16),
                 layer=_fx.FX_LAYER)
    r.add_sprite(v_add(pos, m_apply(hmat, (1.85, 0.85, 0.35))),
                 _fx.glow((72, 242, 122), 0.32, int(t), intensity=0.85, max_px=16),
                 layer=_fx.FX_LAYER)
    r.add_sprite(v_add(pos, m_apply(hmat, (0.0, 1.92, 0.30))),
                 _fx.glow((255, 184, 112), 0.42, int(t), intensity=0.65, max_px=20),
                 layer=_fx.FX_LAYER)
    if spot > 0.05:
        nose = v_add(pos, m_apply(hmat, (0.0, 0.62, 4.65)))
        r.add_sprite(nose, _fx.glow((232, 242, 255), 0.46, int(t), intensity=1.05 * spot, max_px=24),
                     layer=_fx.FX_LAYER)
        for idx, dist in enumerate((2.2, 4.6, 7.6)):
            bp = v_add(pos, m_apply(hmat, (0.0, 0.62 - dist * 0.45, 4.65 + dist * 0.88)))
            r.add_sprite(bp, _fx.haze((206, 224, 255), 0.50 + dist * 0.16, int(t),
                                      seed=740 + idx, intensity=0.20 * spot * (1.0 - idx * 0.25)),
                         layer=_fx.FX_LAYER)


def _vip_heli(t, t0=0.0):
    """Retardovici's helicopter climbing and banking away north-east from the terrace pad."""
    hx, hy, hz = MS.HELIPAD_AT
    u = max(0.0, (t - t0) / 1000.0)
    bank_k = _k(t, 0, 4600)
    pos = (hx + 1.2 + 1.55 * u, hy + 5.2 + 2.35 * u, hz + 2.2 + 1.95 * u)
    yaw = MS.HELI_YAW - 24.0 - 4.8 * u
    pitch = -6.5 - 5.5 * bank_k
    roll = 4.5 + 9.5 * bank_k
    return pos, yaw, pitch, roll


def _heli_lights(pos):
    """Terrace floods and the cabin glow, so the helicopter reads cleanly at night."""
    return [{"pos": (pos[0], pos[1] - 2.6, pos[2]), "color": (196, 214, 255), "intensity": 1.15, "range": 14.0},
            {"pos": (pos[0], pos[1] + 0.9, pos[2]), "color": (255, 196, 140), "intensity": 0.72, "range": 5.5}]


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


def _clip_poly_plane(poly, axis, bound, keep_le):
    """Clip a 3D polygon against ``p[axis] <= bound`` (or ``>=`` if not ``keep_le``)."""
    if not poly:
        return []
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        va = (a[axis] <= bound) if keep_le else (a[axis] >= bound)
        vb = (b[axis] <= bound) if keep_le else (b[axis] >= bound)
        if va:
            out.append(a)
            if not vb:
                denom = b[axis] - a[axis]
                u = (bound - a[axis]) / denom if abs(denom) > 1e-8 else 0.0
                out.append((a[0] + (b[0] - a[0]) * u,
                            a[1] + (b[1] - a[1]) * u,
                            a[2] + (b[2] - a[2]) * u))
        elif vb:
            denom = b[axis] - a[axis]
            u = (bound - a[axis]) / denom if abs(denom) > 1e-8 else 0.0
            out.append((a[0] + (b[0] - a[0]) * u,
                        a[1] + (b[1] - a[1]) * u,
                        a[2] + (b[2] - a[2]) * u))
    return out


def _subtract_door_rect(tri, z0, z1, y0, y1):
    """Split a port-wall triangle into disjoint pieces outside ``[z0,z1] x [y0,y1]``."""
    zs = [p[2] for p in tri]
    ys = [p[1] for p in tri]
    if max(zs) <= z0 or min(zs) >= z1 or max(ys) <= y0 or min(ys) >= y1:
        return [tri]
    out = []
    for poly in (
        _clip_poly_plane(tri, 2, z0, True),
        _clip_poly_plane(tri, 2, z1, False),
        _clip_poly_plane(_clip_poly_plane(_clip_poly_plane(tri, 2, z0, False), 2, z1, True), 1, y0, True),
        _clip_poly_plane(_clip_poly_plane(_clip_poly_plane(tri, 2, z0, False), 2, z1, True), 1, y1, False),
    ):
        if len(poly) >= 3:
            out.append(poly)
    return out


def _vip_open_body():
    """The VIP hull with a clean doorway cut in the port cabin wall and a dark,
    fitted presidential interior (leather bench, mahogany/brass trim, grab rail,
    ceiling sconce, forward cockpit avionics)."""
    got = _VIP_OPEN.get("body")
    if got is not None:
        return got
    body, _mr, _tr, _info = CS.helicopter_parts()
    z0, z1, y0, y1 = -0.08, 1.42, 0.56, 2.16
    m = Mesh()
    for f in body.faces:
        pts = [body.verts[i] for i in f[0]]
        is_port = min(p[0] for p in pts) < -0.52 and max(p[0] for p in pts) < -0.15
        pieces = _subtract_door_rect(pts, z0, z1, y0, y1) if is_port else [pts]
        for poly in pieces:
            base = len(m.verts)
            m.verts.extend(poly)
            for k in range(1, len(poly) - 1):
                m.faces.append(((base, base + k, base + k + 1),) + tuple(f[1:]))
    # Sealed dark cabin shell behind the cut (no sky leak, rich moody VIP interior)
    cab_dark = (22, 23, 27)
    wall_panel = (34, 28, 30)
    mahog = (58, 30, 24)
    brass = (164, 134, 74)
    leather = (66, 24, 26)
    leather_hi = (84, 32, 34)
    carpet = (38, 22, 24)
    m.add(box(1.56, 0.08, 1.96, cab_dark, center=(-0.05, 0.52, 0.67)))
    m.add(box(1.36, 0.02, 1.66, carpet, center=(-0.10, 0.555, 0.66)))
    m.add(box(0.08, 1.70, 1.96, wall_panel, center=(0.70, 1.36, 0.67)))
    m.add(box(1.56, 1.70, 0.08, cab_dark, center=(-0.05, 1.36, 1.61)))
    m.add(box(1.56, 1.70, 0.08, cab_dark, center=(-0.05, 1.36, -0.28)))
    m.add(box(1.56, 0.08, 1.96, cab_dark, center=(-0.05, 2.20, 0.67)))
    # Interior mahogany wainscoting, brass waist trim & acoustic ribs on starboard bulkhead
    m.add(box(0.04, 0.54, 1.82, mahog, center=(0.64, 0.88, 0.67)))
    m.add(box(0.04, 0.035, 1.84, brass, center=(0.635, 1.16, 0.67)))
    m.add(box(0.04, 0.035, 1.84, brass, center=(0.635, 1.86, 0.67)))
    for rz in (0.05, 0.52, 0.99, 1.40):
        m.add(box(0.04, 0.66, 0.05, (28, 26, 30), center=(0.64, 1.51, rz)))
    # Forward cockpit partition console + subtle glowing avionics indicators
    m.add(box(1.24, 0.05, 0.04, brass, center=(-0.05, 1.24, 1.56)))
    for dx, col in ((-0.38, (64, 212, 128)), (-0.22, (64, 212, 128)), (-0.06, (238, 168, 56)),
                    (0.12, (238, 168, 56)), (0.28, (220, 68, 56))):
        m.add(box(0.07, 0.045, 0.025, col, center=(dx, 1.14, 1.56), emissive=True))
    # Plush burgundy leather VIP bench seat + tufted backrest + side bolster
    m.add(box(0.76, 0.28, 1.66, (30, 24, 26), center=(0.24, 0.70, 0.66)))
    m.add(box(0.82, 0.14, 1.68, leather_hi, center=(0.20, 0.89, 0.66)))
    m.add(box(0.18, 0.68, 1.64, leather, center=(0.54, 1.30, 0.66)))
    m.add(box(0.20, 0.16, 1.60, leather_hi, center=(0.52, 1.66, 0.66)))
    for bz in (-0.12, 1.44):
        m.add(box(0.72, 0.22, 0.10, leather, center=(0.22, 1.04, bz)))
    # Overhead warm sconce strip + headliner ribs + vertical steel grab rail at aft jamb
    for rz in (0.14, 0.67, 1.20):
        m.add(box(1.42, 0.04, 0.06, (36, 38, 44), center=(-0.05, 2.15, rz)))
    m.add(box(0.16, 0.03, 0.52, (255, 206, 142), center=(-0.18, 2.15, 0.67), emissive=True))
    m.add(box(0.035, 1.08, 0.035, (148, 152, 160), center=(-0.81, 1.48, 0.02)))
    for gy in (1.02, 1.94):
        m.add(box(0.08, 0.035, 0.035, (92, 96, 104), center=(-0.84, gy, 0.02)))
    # Flush doorway trim + rail-mounted slid-aft cabin door with recessed window
    frame_col = (38, 40, 46)
    for zc in (z0, z1):
        m.add(box(0.08, 1.62, 0.08, frame_col, center=(-0.84, 1.36, zc)))
    m.add(box(0.08, 0.08, 1.58, frame_col, center=(-0.84, 2.14, 0.67)))
    m.add(box(0.14, 0.07, 1.58, (88, 92, 98), center=(-0.84, 0.54, 0.67)))
    m.add(box(0.04, 0.04, 2.65, (42, 44, 50), center=(-0.92, 2.10, 0.05)))
    m.add(box(0.04, 0.04, 2.65, (42, 44, 50), center=(-0.92, 0.56, 0.05)))
    m.add(box(0.06, 0.68, 1.12, (198, 198, 194), center=(-0.96, 0.90, -0.68)))
    m.add(box(0.06, 0.16, 1.12, (198, 198, 194), center=(-0.96, 1.86, -0.68)))
    m.add(box(0.06, 0.56, 0.18, (198, 198, 194), center=(-0.96, 1.50, -0.21)))
    m.add(box(0.06, 0.56, 0.18, (198, 198, 194), center=(-0.96, 1.50, -1.15)))
    m.add(box(0.07, 0.58, 0.78, (32, 34, 40), center=(-0.96, 1.50, -0.68)))
    m.add(box(0.04, 0.50, 0.70, (24, 34, 46), center=(-0.965, 1.50, -0.68)))
    m.add(box(0.04, 0.14, 0.05, (28, 30, 34), center=(-1.00, 1.04, -0.26)))
    _VIP_OPEN["body"] = m
    return m


def _vip_base_pose():
    """Cached seated-forward-lean base pose verified against Retardovici's 2.276 m
    rig so his boots sit on the y=0.55 cabin floor while his head clears the
    y=2.14 doorway lintel with generous headroom."""
    got = _VIP_OPEN.get("base_pose")
    if got is not None:
        return dict(got)
    hum = _w.hum("retardovici")
    p = dict(POSES["stand"], lhip_p=116, lkn=128, lank=10, rhip_p=106, rkn=118, rank=10,
             lhip_r=10, rhip_r=14, spine=36, head_p=-16, head_y=-6,
             rsh_p=42, rsh_r=14, rel=38)
    for _ in range(8):
        verts = hum.build(p, (-0.28, 0.55, 0.62), -90.0, rifle_on=False)[0]
        if max(v[1] for v in verts) <= 1.98:
            break
        p["lhip_p"] += 3
        p["rhip_p"] += 3
        p["lkn"] += 3
        p["rkn"] += 3
        p["spine"] += 2
        p["head_p"] -= 1
    _VIP_OPEN["base_pose"] = dict(p)
    return dict(p)


def _vip_pose(t=0.0):
    """Animated seated pose: left hand locked onto the doorway grab-rail while
    the right hand delivers a smug dismissive wave outward toward the estate."""
    hum = _w.hum("retardovici")
    p = _vip_base_pose()
    # Beat 1 (0..2100ms): proud composed posture, open-arm dismissive wave toward the house
    # Beat 2 (2100..3500ms): assured upward gesture ("back by Monday")
    # Beat 3 (3500..4600ms): leans slightly back into the leather bench with a cold sneer
    g1 = _k(t, 200, 850) * (1.0 - _k(t, 1650, 600))
    g2 = _k(t, 2100, 700) * (1.0 - _k(t, 3400, 850))
    lean_back = _k(t, 3450, 1050)
    p["spine"] = p["spine"] - 6.0 - 4.0 * lean_back + 2.0 * g1
    p["twist"] = -8.0 * g1 + 6.0 * g2
    p["head_p"] = p["head_p"] + 2.0 + 3.0 * g1 - 2.0 * g2 - 2.0 * lean_back
    p["head_y"] = -10.0 + 14.0 * _k(t, 1750, 1400) - 6.0 * lean_back
    p["rsh_p"] = 34.0 + 48.0 * g1 + 54.0 * g2 - 8.0 * lean_back
    p["rsh_r"] = 22.0 + 36.0 * g1 + 16.0 * g2
    p["rel"] = 42.0 - 20.0 * g1 - 14.0 * g2 + 10.0 * lean_back
    # Left hand grips the vertical steel grab-rail at (-0.81, 1.54, 0.02)
    p = solve_arm_safe(hum, p, (-0.28, 0.55, 0.62), -90.0, "l", (-0.81, 1.54, 0.02),
                       poles=((-0.5, -0.4, -0.7),) + POLES)
    return p


def _draw_vip_open(r, t, pos, yaw, pitch, roll):
    """VIP hull with dark leather presidential cabin; Retardovici leans out from
    the bench gripping the doorway rail, pilot visible in the cockpit."""
    body = _vip_open_body()
    _b, main_r, tail_r, info = CS.helicopter_parts()
    CS.put(r, "m8d_vip_open", lambda: body, pos, yaw, pitch, roll)
    if main_r.faces:
        mh = CS._xf(info["main_hub"], pos, yaw, pitch, roll)
        CS._put_spun(r, "heli_main", main_r, mh, yaw, pitch, roll, spin_y=(t * 1.6) % 360.0)
    if tail_r.faces:
        th = CS._xf(info["tail_hub"], pos, yaw, pitch, roll)
        CS._put_spun(r, "heli_tail", tail_r, th, yaw, pitch, roll, spin_x=(t * 2.6) % 360.0)
    # Pilot silhouette in front cockpit seat
    pilot_p = CS._xf(info["pilot_seat"], pos, yaw, pitch, roll)
    _w.actor(r, "guard", dict(FX._PILOT_POSE), pilot_p, yaw, int(t), seed=19, amp=0.06,
             rifle_on=False, expression="stern")
    feet = CS._xf((-0.28, 0.55, 0.62), pos, yaw, pitch, roll)
    pose = _vip_pose(t)
    expr = "grin" if t < 3100 else "angry"
    _w.actor(r, "retardovici", pose, feet, yaw - 90.0, int(t), seed=12, amp=0.04,
             expression=expr, mouth=_talk(t, 220, 3900))
    return feet


def liftoff_study(surface, t):
    """The terrace doors burst open: Biribel sprints out into the roaring downwash,
    skids to a halt and fires a desperate burst up at the climbing VIP helicopter."""
    hx, hy, hz = MS.HELIPAD_AT
    u = t / 1000.0
    climb_k = _k(t, 0, 4000)
    # VIP heli lifts steadily off the terrace pad, banking NE (kept fully inside frame)
    pos = (hx + 0.4 + 0.85 * u, hy + 1.8 + 1.15 * u + 0.14 * u * u, hz + 1.2 + 1.35 * u)
    yaw = MS.HELI_YAW - 6.0 - 7.5 * u
    pitch = -2.5 - 5.5 * climb_k
    roll = 2.0 + 4.5 * climb_k

    # Biribel sprints from the terrace doorway onto the pad, then brakes and raises OS-12
    run = _k(t, 0, 1750)
    stop_u = _k(t, 1650, 550)
    bx = -1.6 + 1.15 * run
    bz = 37.8 + 4.8 * run
    bpos = (bx, hy, bz)
    byaw_run = math.degrees(math.atan2(1.15, 4.8))
    byaw_aim = math.degrees(math.atan2(pos[0] - bx, pos[2] - bz))
    byaw = byaw_run + (byaw_aim - byaw_run) * stop_u

    # Camera: low-angle urgent push beside Biribel, keeping BOTH Biribel in the
    # lower-left foreground AND the full climbing VIP helicopter cleanly in frame
    cam_u = _k(t, 0, 3800)
    jit, jroll = _handheld(t, amp=0.040 * (1.0 - 0.35 * climb_k) + 0.018, roll_amp=0.65, seed=31)
    eye = _mix((-5.2, hy + 1.25, 35.6), (-3.6, hy + 1.35, 38.2), cam_u)
    eye = v_add(eye, jit)
    mid_y = hy + 2.15 + (pos[1] - hy - 1.55) * (0.42 + 0.16 * climb_k)
    tgt = _mix((bx + 0.9, hy + 2.25, bz + 3.0),
               (pos[0] * 0.52 + bx * 0.48, mid_y, pos[2] * 0.55 + bz * 0.45),
               0.35 + 0.65 * cam_u)
    dutch = -2.2 + 3.6 * cam_u + jroll

    # Muzzle-flash lighting on Biribel's 3-round futile burst (2350, 2520, 2690 ms)
    shots = (2350.0, 2520.0, 2690.0)
    flash_k = 0.0
    shot_idx = -1
    for i, st in enumerate(shots):
        age = t - st
        if 0.0 <= age < 110.0:
            flash_k = max(flash_k, 1.0 - age / 110.0)
            shot_idx = i
    lights = list(_heli_lights(pos))
    lights.append({"pos": (hx, hy + 2.2, hz - 1.5), "color": (210, 224, 255),
                   "intensity": 0.95, "range": 14.0})
    if flash_k > 0.05:
        lights.append({"pos": (bx + 0.3, hy + 1.55, bz + 0.7), "color": (255, 198, 102),
                       "intensity": 1.65 * flash_k, "range": 7.5})

    r = MS.frame(eye, tgt, 56.0 + 3.0 * cam_u, lights=lights, t=int(t), size=FILM, roll=dutch)
    del _w.LAST[:]
    MS.draw_dynamic_props(r, t, cams_alive=False, front_open=True, study_open=True, terrace_open=True)
    _draw_vip(r, t, pos, yaw, pitch, roll)
    _heli_nav_lights(r, pos, yaw, pitch, roll, t, searchlight=True)
    _rotor_wash(r, (hx, hy, hz), t, seed=3, n=16, radius=6.8, intensity=1.15 - 0.35 * climb_k)

    # Biribel: physical locomotion_pose sprint -> smooth blend into upward IK aim at the chopper
    bp = _w.hum(BIRI, flags=("os12",))
    dist_m = math.hypot(1.15, 4.8) * run
    phase = dist_m * (math.tau / 1.82)
    run_speed = 5.4 * (1.0 - stop_u)
    lower = locomotion_pose(run_speed, 0.0, phase, sprint=1.0 - stop_u)
    upper_run = R._held(bp, dict(POSES["ready"], spine=14.0, head_p=-10.0),
                        "os12", "ready", ("m8_biri_os12", "ready_run"))
    p_run = mask_pose(lower, upper_run)
    # Upward aimed pose targeting the climbing VIP helicopter directly via hold_weapon IK
    recoil = 7.5 * flash_k
    aim_base = dict(POSES["stand"], lhip_p=16.0, lkn=22.0, rhip_p=-14.0, rkn=18.0,
                    spine=-12.0 - recoil * 0.45, head_p=-24.0 - recoil * 0.3, head_y=0.0)
    aim_tgt = (pos[0] - 0.4, pos[1] + 0.9, pos[2] - 0.5)
    p_aim = hold_weapon(bp, aim_base, bpos, byaw, "os12", "aim", aim=aim_tgt)
    if flash_k > 0.0:
        p_aim["rifle_p"] = p_aim.get("rifle_p", 0.0) - recoil
    pose = blend(p_run, p_aim, stop_u)
    joints = _w.actor(r, BIRI, pose, bpos, byaw, int(t), seed=93, amp=0.05 * stop_u,
                      rifle_on=True, flags=("os12",), expression="angry",
                      mouth=_talk(t, 280, 1500))

    # Muzzle flash + amber tracer streaks + belly skid spark ping on shot 2
    if joints and "rhand" in joints and "rifle_m" in joints:
        muzzle = v_add(joints["rhand"], m_apply(joints["rifle_m"], (0.0, 0.04, 0.64)))
        if flash_k > 0.05:
            r.add_sprite(muzzle, _fx.glow((255, 224, 138), 0.34 + 0.14 * flash_k, int(t),
                                          seed=810 + shot_idx, intensity=1.6 * flash_k, max_px=26),
                         layer=_fx.FX_LAYER)
        for i, st in enumerate(shots):
            age = t - st
            if 0.0 <= age < 140.0:
                tu = age / 140.0
                miss = ((-0.65, 0.8, 0.2), (-0.15, 0.32, 0.1), (0.85, 1.35, -0.3))[i]
                end = v_add(pos, miss)
                p0 = _mix(muzzle, end, max(0.0, tu - 0.32))
                p1 = _mix(muzzle, end, min(1.0, tu + 0.12))
                r.add_line3d(p0, p1, (255, 218, 122), 2, layer=3)
            if i == 1 and 35.0 <= age < 185.0:
                sk = 1.0 - (age - 35.0) / 150.0
                hit_p = v_add(pos, (-0.15, 0.32, 0.10))
                r.add_sprite(hit_p, _fx.glow((255, 232, 168), 0.28, int(t),
                                             seed=822, intensity=1.4 * sk, max_px=20),
                             layer=_fx.FX_LAYER)
                for sp in range(5):
                    sa = sp * 1.25 + 0.4
                    r.add_line3d(hit_p,
                                 (hit_p[0] + math.cos(sa) * 0.55 * (1.0 - sk),
                                  hit_p[1] - 0.35 * (1.0 - sk) + math.sin(sa) * 0.25,
                                  hit_p[2] + math.sin(sa) * 0.45 * (1.0 - sk)),
                                 (255, 210, 118), 1, layer=3)

    # Bodi bursts out behind Biribel from the open terrace doors, looking up at the bird
    bodi_run = _k(t, 280, 1550)
    bodi_stop = _k(t, 1550, 500)
    bd_pos = (1.55 + 0.45 * bodi_run, hy, 36.8 + 2.5 * bodi_run)
    bd_yaw = math.degrees(math.atan2(pos[0] - bd_pos[0], pos[2] - bd_pos[2]))
    bd_hum = _w.hum(BODI, flags=("os12",))
    bd_lower = locomotion_pose(3.8 * (1.0 - bodi_stop), 0.0, bodi_run * 7.4, sprint=0.6 * (1.0 - bodi_stop))
    bd_upper = R._held(bd_hum, dict(POSES["ready"], spine=8.0 - 16.0 * bodi_stop, head_p=-22.0 * bodi_stop),
                       "os12", "ready", ("m8_bodi_os12", "ready_lift"))
    _w.actor(r, BODI, mask_pose(bd_lower, bd_upper), bd_pos, bd_yaw, int(t),
             seed=61, amp=0.06, rifle_on=True, flags=("os12",), expression="worried")
    _finish(surface, r, t, 3)


def liftoff_window(surface, t):
    """Aerial 3/4-port climbing shot: Retardovici leans out from the dark leather
    presidential cabin bench gripping the doorway rail, gesturing smugly down at
    the receding estate as his helicopter banks into the night."""
    pos, yaw, pitch, roll = _vip_heli(t, -1800.0)
    u = _k(t, 0, 4600)
    hmat = m_mul(rot_y(yaw), m_mul(rot_x(-pitch), rot_z(roll)))
    jit, jroll = _handheld(t, amp=0.032, roll_amp=0.65, seed=41)
    # Slightly elevated aerial camera looking gently down past the doorway so the
    # glowing estate and grounds recede beneath the banking helicopter
    eye_local = (-3.6 - 2.2 * u, 1.58 + 0.52 * u, 1.85 - 0.35 * u)
    tgt_local = (-0.28, 1.42 - 0.14 * u, 0.56)
    eye = v_add(CS._xf(eye_local, pos, yaw, pitch, roll), jit)
    tgt = CS._xf(tgt_local, pos, yaw, pitch, roll)
    # Controlled moody lighting: warm cabin reading key on Retardovici's face,
    # cool moonlight exterior rim, and pulsing red anti-collision strobe spill
    dome = {"pos": CS._xf((-0.52, 1.94, 1.12), pos, yaw, pitch, roll),
            "color": (255, 184, 110), "intensity": 0.64, "range": 2.9}
    rim = {"pos": CS._xf((-3.6, 2.4, 2.2), pos, yaw, pitch, roll),
           "color": (128, 166, 244), "intensity": 0.62, "range": 9.5}
    strobe_on = 1.0 if ((int(t) % 880) < 130) else 0.0
    lights = [dome, rim,
              {"pos": (pos[0], pos[1] - 3.2, pos[2]), "color": (184, 206, 255),
               "intensity": 0.78, "range": 13.0}]
    if strobe_on > 0.0:
        lights.append({"pos": CS._xf((0.0, 0.2, -1.6), pos, yaw, pitch, roll),
                       "color": (255, 62, 44), "intensity": 0.95, "range": 6.0})

    cam_roll = -1.8 - 3.2 * u + jroll
    r = MS.frame(eye, tgt, 42.0 + 3.5 * u, lights=lights, t=int(t), size=FILM, roll=cam_roll)
    del _w.LAST[:]
    MS.draw_dynamic_props(r, t, cams_alive=False, front_open=True, study_open=True, terrace_open=True)
    _draw_vip_open(r, t, pos, yaw, pitch, roll)
    _heli_nav_lights(r, pos, yaw, pitch, roll, t, searchlight=True)
    _air_streaks(r, pos, hmat, t, seed=4, n=12)
    _finish(surface, r, t, 4)


def _liftoff_lmg_pose(eye_w, gy_world, gp):
    """FlightScene hip-fire LMG placement lifted slightly for the letterbox band
    so the receiver, reflex optic and pintle read crisply on the match cut."""
    f = R._fwd(gy_world, gp)
    rg = R._right(gy_world)
    up = (
        f[1] * rg[2] - f[2] * rg[1],
        f[2] * rg[0] - f[0] * rg[2],
        f[0] * rg[1] - f[1] * rg[0],
    )
    at = (
        eye_w[0] + f[0] * 0.76 + rg[0] * 0.215 + up[0] * (-0.195),
        eye_w[1] + f[1] * 0.76 + rg[1] * 0.215 + up[1] * (-0.195),
        eye_w[2] + f[2] * 0.76 + rg[2] * 0.215 + up[2] * (-0.195),
    )
    basis = m_mul(rot_y(gy_world - 5.0), m_mul(rot_x(-(gp + 4.5)), rot_z(3.5)))
    return basis, at


def liftoff_maru(surface, t):
    """Maru's gunship flares in east of the x=+9.0 terrace rail, spotlight raking
    the concrete; Biribel sprints across, vaults the balustrade into the open bay,
    and the camera whips cleanly into the FlightScene gunner-eye behind the fixed-trunnion LMG."""
    from missions.m8.duty import flight3d as F3
    hx, hy, hz = MS.HELIPAD_AT
    u = _k(t, 0, 2150)
    flare = math.sin(u * math.pi)
    climb = _k(t, 3400, 1200)
    hover = (12.4, hy + 0.35, hz - 0.5)
    # Match FlightScene cp=0 t=0 exact starting state over the east-front lawn
    end_pos = F3.START_HPOS
    base = _mix((22.0, hy + 2.4, hz + 5.5), hover, u)
    bob = 0.14 * math.sin(t * 0.0055) * (1.0 - climb) * u
    hpos = _mix((base[0], base[1] + bob, base[2]), end_pos, climb)
    gyaw = (212.0 - 47.0 * u) * (1.0 - climb) + F3.START_HYAW * climb
    gpitch = (-4.0 * (1.0 - u) + 8.5 * flare) * (1.0 - climb) + F3.START_HPITCH * climb
    groll = (-14.0 * (1.0 - u) - 4.0 * flare) * (1.0 - climb) + F3.START_HROLL * climb
    hmat = FX.heli_matrix(gyaw, gpitch, groll)

    # Biribel sprints along z = hz-1.05 aligned with the open starboard cabin bay,
    # vaults cleanly over the x=9.0 balustrade into the doorway center, and lands inside.
    run = _k(t, 550, 1800)
    jump = _k(t, 2350, 1000)
    door = v_add(hover, m_apply(FX.heli_matrix(165.0, 0.0, 0.0), (0.85, 0.58, 0.45)))
    p_run = (0.4 + 7.6 * run, hy, hz - 1.10)
    arc = 1.24 * math.sin(math.pi * min(1.0, jump * 1.04)) * (1.0 - climb)
    p_jump = _mix((8.0, hy, hz - 1.10), door, jump)
    p_jump = (p_jump[0], p_jump[1] + arc, p_jump[2])
    p_in = v_add(hpos, m_apply(hmat, (0.46, 0.574, 0.22)))
    bpos = p_run if t < 2350 else _mix(p_jump, p_in, climb)

    # Exterior tracking camera -> seamless match-cut whip into FlightScene cp=0 gunner_eye
    jit, jroll = _handheld(t, amp=0.034 * (1.0 - climb), roll_amp=0.70 * (1.0 - climb), seed=52)
    eye_ext = _mix((-1.6, hy + 2.25, hz - 5.6), (4.8, hy + 2.15, hz - 6.2), _k(t, 0, 3100))
    eye_ext = v_add(eye_ext, jit)
    tgt_ext = _mix((hpos[0] - 1.4, hpos[1] + 1.35, hpos[2]),
                   (bpos[0] + 1.2, bpos[1] + 1.05, bpos[2] + 0.15),
                   _k(t, 2000, 1100))
    _f, _b, _mr, _tr, ginfo = CS.maru_gunship_parts()
    rel_y = R._wrap(F3.START_AIM_YAW - F3.START_HYAW)
    cab_eye = FX.gunner_eye(hpos, hmat, rel_y, 0.0, t * 0.001, 0.0,
                            reduced_motion=True, gp=F3.START_AIM_PITCH, gy_world=F3.START_AIM_YAW)
    aim_dir = R._fwd(F3.START_AIM_YAW, F3.START_AIM_PITCH)
    cab_tgt = (cab_eye[0] + aim_dir[0] * 10.0,
               cab_eye[1] + aim_dir[1] * 10.0,
               cab_eye[2] + aim_dir[2] * 10.0)
    whip_u = _k(t, 3450, 920)
    eye = _mix(eye_ext, cab_eye, whip_u)
    tgt = _mix(tgt_ext, cab_tgt, whip_u)
    end_roll = 0.0 if _reduced_motion() else max(-7.0, min(7.0, F3.START_HROLL * 0.32))
    cam_roll = (-2.2 * flare + jroll) * (1.0 - whip_u) + end_roll * whip_u
    fov = 54.0 + (F3.FOV - 54.0) * whip_u

    lights = list(_heli_lights(hpos))
    fy = float(ginfo.get("floor_y", 0.574))
    lights.append({"pos": v_add(hpos, m_apply(hmat, (0.15, fy + 1.48, 0.55))),
                   "color": (255, 168, 92), "intensity": 0.62, "range": 4.2})
    if climb < 0.7:
        lights.append({"pos": (9.2, hy + 1.5, hz - 0.4), "color": (208, 224, 255),
                       "intensity": 0.95 * (1.0 - climb), "range": 10.0})

    r = MS.frame(eye, tgt, fov, lights=lights, t=int(t), roll=cam_roll)
    r.light_cap = 64
    r.wetness = 0.48
    del _w.LAST[:]
    MS.draw_dynamic_props(r, t, cams_alive=False, front_open=True, study_open=True, terrace_open=True)
    in_fpv = (whip_u >= 0.78)
    _gunship(r, t, hpos, gyaw, gpitch, groll, (t * 1.45) % 360.0,
             pilot=True, fpv=in_fpv)
    if in_fpv:
        FX._submit(r, "m8d_maru_accents", FX._maru_interior_accents(ginfo), hmat, hpos)
    _gunship_lights(r, hpos, hmat, t, spot=max(0.2, 1.0 - climb * 0.7))
    if climb < 0.85:
        _rotor_wash(r, (9.4, hy, hz - 0.4), t, seed=5, n=14, radius=5.6, intensity=1.05 * (1.0 - climb))

    # Fixed-trunnion starboard doorway pintle LMG + swivel yoke + linked brass ammo belt
    lmg_mesh = FX.tactical_lmg_mesh(_tactical_lmg())
    pivot_w = v_add(hpos, m_apply(hmat, FX.PINTLE_PIVOT_LOCAL))
    gun_u = _k(t, 3420, 820)
    cur_gun_yaw = (gyaw + 72.0) * (1.0 - gun_u) + F3.START_AIM_YAW * gun_u
    cur_gun_pitch = (gpitch - 12.0) * (1.0 - gun_u) + F3.START_AIM_PITCH * gun_u
    gun_basis = m_mul(rot_y(cur_gun_yaw), rot_x(-cur_gun_pitch))
    gun_at = v_add(pivot_w, tuple(-c for c in m_apply(gun_basis, FX.TRUNNION_LOCAL)))
    yoke_basis = m_mul(hmat, rot_y(R._wrap(cur_gun_yaw - gyaw)))
    FX._submit(r, "m8d_pintle_yoke", FX._pintle_yoke_mesh(), yoke_basis, pivot_w)
    ammo_src_w = v_add(hpos, m_apply(hmat, FX.AMMO_FEED_LOCAL))
    ammo_dst_w = v_add(gun_at, m_apply(gun_basis, FX.FEED_TRAY_LOCAL))
    FX._draw_ammo_belt(r, ammo_src_w, ammo_dst_w, gun_basis)
    FX._submit(r, "m8d_tlmg_optic", lmg_mesh, gun_basis, gun_at)

    # Bodi & Alex covering from the back of the terrace as Biribel sprints and leaps
    if whip_u < 0.55:
        _w.actor(r, BODI, dict(POSES["ready"], head_y=-12), (-2.6, hy, 39.2), 78.0, int(t),
                 seed=61, amp=0.08, rifle_on=True, flags=("os12",))
        _w.actor(r, ALEX, dict(POSES["crouch"], head_y=-8), (-1.2, hy, 38.0), 72.0, int(t),
                 seed=62, amp=0.08, rifle_on=True)

    # Biribel's physical sprint -> athletic balustrade vault -> cabin landing crouch
    # (steps out of third-person render once the camera enters his first-person gunner eye)
    if whip_u < 0.72:
        bp = _w.hum(BIRI, flags=("os12",))
        if t < 2350:
            dist_m = 7.6 * run
            run_v = 5.6 * (1.0 if 0.02 < run < 0.98 else 0.0)
            lower = locomotion_pose(run_v, 0.0, dist_m * (math.tau / 1.85), sprint=1.0 if run_v > 0.1 else 0.0)
            upper = R._held(bp, dict(POSES["ready"], spine=14.0 if run_v > 0.1 else 4.0),
                            "os12", "ready", ("m8_biri_os12", "maru_run"))
            pose = mask_pose(lower, upper)
        elif t < 3350:
            vault_launch = dict(POSES["stand"], spine=24.0, head_p=-10.0,
                                lhip_p=76.0, lkn=84.0, rhip_p=-32.0, rkn=28.0,
                                lsh_p=68.0, lel=30.0, rsh_p=34.0, rel=54.0, rifle_p=18.0)
            vault_land = dict(POSES["crouch"], spine=26.0, head_p=-6.0,
                              lhip_p=72.0, lkn=96.0, rhip_p=62.0, rkn=88.0,
                              lsh_p=42.0, lel=52.0, rsh_p=36.0, rel=58.0, rifle_p=14.0)
            pose = blend(vault_launch, vault_land, _k(t, 2820, 520))
        else:
            land_k = _k(t, 3350, 420)
            crouch_p = dict(POSES["crouch"], spine=22.0, lhip_p=68.0, lkn=92.0, rhip_p=60.0, rkn=84.0)
            stand_p = R._held(bp, dict(POSES["ready"], spine=8.0), "os12", "ready", ("m8_biri_os12", "maru_in"))
            pose = blend(crouch_p, stand_p, land_k)
        byaw = 90.0 + (206.0 - 90.0) * climb
        _w.actor(r, BIRI, pose, bpos, byaw, int(t), seed=93, amp=0.04,
                 rifle_on=True, flags=("os12",), expression="angry")
    _finish_full(surface, r, bar_frac=1.0 - whip_u)


# --- The Crash -----------------------------------------------------------------
# Wooded ridge clearing past Route 12: Maru's gunship comes down in the pines.

CRASH_AT = (0.0, 0.0, 0.0)
_MARU_CRASH_AT = (0.55, 0.0, 0.15)
_BIRI_CRASH_AT = (-0.65, 0.0, -1.05)
_HULL_CRASH_AT = (-2.20, 0.0, 4.80)
_DEBRIS_FIRE_AT = (-4.80, 0.25, -2.60)
_CRASH_WARMED = False


def warm_crash():
    """Pre-bake the crash clearing renderer, charred gunship, sniper mesh, and rigs
    during Last Flight so the Ucilev shootdown hard-cut never freezes."""
    global _CRASH_WARMED
    if _CRASH_WARMED:
        return
    try:
        r = DS.crash_renderer(FILM)
        _sniper_prop()
        _w.hum("maru")
        b_hum = _w.hum(BIRI, flags=("sniper_rifle",))
        b_wpn = getattr(b_hum, "_weapon", "sniper")
        hold_cached(b_hum, dict(POSES["kneel"], spine=14.0, head_p=12.0),
                    b_wpn, "ready", key=("m8_biri_sniper", b_wpn, "ready"))
        CS.maru_gunship_parts()
        CS.helicopter_parts()
        # Pre-populate the charred hull & tail-off pack caches on the crash renderer
        r.begin()
        CS.put_maru_gunship(r, _HULL_CRASH_AT, 112.0, -12.0, -22.0, 0.0, 0.0,
                            tail_on=False, main_on=False, burned=True)
        CS.put_maru_gunship(r, (0.0, 12.0, 8.0), 0.0, -16.0, 0.0, 0.0, 0.0,
                            tail_on=False, main_on=True, burned=False)
        _CRASH_WARMED = True
    except Exception:
        traceback.print_exc()


def _talk(t, start, length):
    if t < start or t > start + length:
        return 0.0
    return abs(math.sin((t - start) * 0.011)) * 0.8


def _fire(r, at, t, seed, size=1.0):
    _f3d.emit_fire(r, at, t, seed=seed, size=0.95 * size, heat=1.25,
                   smoky=True, embers=True, bed=True, layer=2)
    _f3d.emit_fire(r, (at[0] - 0.8 * size, at[1] + 0.2, at[2] + 0.7 * size), t,
                   seed=seed + 11, size=0.60 * size, heat=1.05,
                   smoky=False, embers=True, bed=False, layer=2)


def _crash_embers(r, t, n=18):
    """Drifting glowing embers rising gently through the night clearing."""
    s = t * 0.001
    for i in range(n):
        u = (s * (0.28 + (i % 4) * 0.07) + i * 0.137) % 1.0
        ang = i * 2.39996 + math.sin(s * 1.1 + i) * 0.25
        rad = 1.2 + (i % 5) * 1.15
        ex = -1.2 + math.cos(ang) * rad + math.sin(s * 1.8 + i) * 0.45
        ez = 1.6 + math.sin(ang) * rad + math.cos(s * 1.5 + i) * 0.35
        ey = 0.25 + u * 3.6
        fade = math.sin(u * math.pi)
        if fade > 0.1:
            r.add_sprite((ex, ey, ez),
                         _fx.glow((255, 148, 52), 0.10 + (i % 3) * 0.04, int(t),
                                  core=(255, 232, 168), intensity=0.85 * fade, max_px=7),
                         layer=_fx.FX_LAYER)


def _fire_lights(t, close_key=None):
    """Balanced split noir lighting: warm flickering wreck/debris rims against cool moonlight."""
    f = 0.80 + 0.20 * math.sin(t * 0.019) * math.sin(t * 0.0131)
    out = [
        {"pos": (_HULL_CRASH_AT[0] + 0.6, 1.85, _HULL_CRASH_AT[2] - 0.8),
         "color": (255, 134, 52), "intensity": 1.15 * f, "range": 10.5},
        {"pos": (_DEBRIS_FIRE_AT[0] + 0.3, 0.95, _DEBRIS_FIRE_AT[2] + 0.2),
         "color": (255, 122, 46), "intensity": 0.72 * f, "range": 7.8},
        {"pos": (3.2, 6.0, -5.5), "color": (108, 138, 206),
         "intensity": 0.42, "range": 22.0},
    ]
    if close_key is not None:
        out.append(close_key)
    return out


def _fire_pools(t):
    f = 0.80 + 0.20 * math.sin(t * 0.019)
    return [
        {"pos": (_HULL_CRASH_AT[0] + 0.5, 0.4, _HULL_CRASH_AT[2] - 0.5),
         "range": 7.5, "color": (255, 126, 44), "intensity": 1.35 * f},
        {"pos": (_DEBRIS_FIRE_AT[0], 0.3, _DEBRIS_FIRE_AT[2]),
         "range": 5.0, "color": (255, 118, 42), "intensity": 0.95 * f},
    ]


def crash_spin(surface, t):
    """Low-angle clearing view: Ucilev banks off into the night mist as Maru's tail-less
    gunship corkscrews down into the spruces and erupts on impact (zero hull clipping)."""
    u = max(0.0, min(1.0, t / 3600.0))
    p_u = u ** 1.35
    hpos = _mix((18.0, 24.0, 18.0), (-2.2, 1.6, 4.8), p_u)
    imp_u = _k(t, 3120, 480)
    jit, jroll = _handheld(t, amp=0.045 + 0.14 * imp_u, roll_amp=1.4 + 4.5 * imp_u, seed=66)
    eye = v_add(_mix((-6.5, 2.5, -14.5), (-3.8, 2.2, -11.5), u), jit)
    tgt = _mix((hpos[0], hpos[1] - 0.6, hpos[2]), (-2.2, 2.6, 4.8), 0.35 * _k(t, 2400, 1200))

    hyaw = (t * 0.44) % 360.0
    hpitch = -14.0 - 16.0 * u
    hroll = 26.0 * math.sin(t * 0.0055)
    hmat = FX.heli_matrix(hyaw, hpitch, hroll)
    tail_root = v_add(hpos, m_apply(hmat, (0.0, 1.80, -1.35)))

    # Place firelight at the severed tail engine bay (not under the belly) for dramatic edge-lit metal
    lights = [
        {"pos": tail_root, "color": (255, 134, 50), "intensity": 1.45 + 1.8 * imp_u, "range": 14.0 + 14.0 * imp_u},
        {"pos": (-10.0, 16.0, -14.0), "color": (98, 128, 194), "intensity": 0.42, "range": 55.0},
    ]
    r = DS.crash_frame(eye, tgt, 46.0 - 4.0 * u, t=int(t), size=FILM, lights=lights, roll=jroll)
    del _w.LAST[:]
    if t < 2000:
        u_fly = _k(t, 0, 2000)
        upos = _mix((18.0, 26.0, 34.0), (-2.0, 33.0, 56.0), u_fly)
        CS.put_helicopter(r, upos, 318.0, -8.0, -24.0, (t * 1.5) % 360.0, (t * 2.4) % 360.0)
        FX.draw_ucilev_fx(
            r, upos, 318.0, -8.0, -24.0, t,
            {"spotlight": 0.0, "pod_l": 0.0, "pod_r": 0.0, "turbine": 0.0},
            3, now=t * 0.001, seed=99,
        )
        for k in range(1, 6):
            pu = max(0.0, u_fly - 0.045 * k)
            spos = _mix((18.0, 26.0, 34.0), (-2.0, 33.0, 56.0), pu)
            r.add_sprite((spos[0], spos[1] + 2.2, spos[2]),
                         _f3d.emit_smoke(t, seed=70 + k, size_m=1.4 + 0.35 * k, heat=0.72 - 0.1 * k),
                         layer=2)
    _gunship(r, t, hpos, hyaw, hpitch, hroll, (t * 1.6) % 360.0, tail_on=False)
    _f3d.emit_fire(r, tail_root, t, seed=4, size=1.35, heat=1.45,
                   smoky=True, embers=True, bed=False, layer=2)
    # Thick corkscrewing smoke & ember ribbon trailing along the descent arc
    for k in range(1, 9):
        pu = max(0.0, u - 0.038 * k)
        tpos = _mix((18.0, 24.0, 18.0), (-2.2, 1.6, 4.8), pu ** 1.35)
        r.add_sprite((tpos[0], tpos[1] + 1.2, tpos[2]),
                     _f3d.emit_smoke(t, seed=20 + k, size_m=1.6 + 0.36 * k, heat=0.82 - 0.08 * k),
                     layer=2)
        if k <= 4:
            r.add_sprite((tpos[0], tpos[1] + 1.0, tpos[2]),
                         _fx.glow((255, 138, 48), 0.75 - 0.12 * k, int(t),
                                  intensity=0.75 * (1.0 - 0.18 * k), max_px=22),
                         layer=_fx.FX_LAYER)
    # Impact fireball & spark spray across the treeline right before the smash-cut to crash_black
    if imp_u > 0.0:
        ip = (-2.2, 2.4, 4.8)
        r.add_sprite(ip, _fx.glow((255, 148, 52), 5.2 * imp_u, int(t), core=(255, 242, 206),
                                  intensity=2.4 * imp_u, max_px=180),
                     layer=_fx.FX_LAYER)
        _f3d.emit_fire(r, ip, t, seed=88, size=2.2 * imp_u, heat=1.6,
                       smoky=True, embers=True, bed=False, layer=2)
    _finish(surface, r, t, 6)


def crash_black(surface, t):
    """Impact. Black. Rising firelight and drifting embers creep in at the bottom of the frame."""
    band = surface.subsurface((0, _w.SAFE_TOP, WIDTH, _w.FILM_H))
    band.fill((0, 0, 0))
    a = _k(t, 600, 1400) * (0.72 + 0.28 * math.sin(t * 0.013) * math.cos(t * 0.007))
    if a > 0.0:
        h = band.get_height()
        halo = _f3d._soft_halo((int(178 * a), int(68 * a), int(16 * a)), 220)
        halo_w = pygame.transform.smoothscale(halo, (int(WIDTH * 1.15), int(h * 1.35)))
        band.blit(halo_w, (int(-WIDTH * 0.075), int(h * 0.34)), special_flags=pygame.BLEND_RGB_ADD)
        s = t * 0.001
        for i in range(26):
            eu = (s * (0.42 + (i % 4) * 0.13) + i * 0.143) % 1.0
            ex = int((0.10 + 0.80 * ((i * 37) % 23) / 22.0) * WIDTH + math.sin(s * 2.8 + i) * 18.0)
            ey = int(h * (1.03 - eu * 0.74))
            ea = int(220 * a * (1.0 - eu))
            if ea > 12:
                col = (min(255, ea + 40), int(ea * (0.55 + 0.32 * (1.0 - eu))), int(ea * 0.18))
                rad = 2 if (i % 3 != 0) else 1
                pygame.draw.circle(band, col, (ex, ey), rad)


def _crash_set(r, t):
    _gunship(r, t, _HULL_CRASH_AT, 112.0, -12.0, 22.0, 0.0, burned=True, tail_on=False, main_on=False)
    hmat = FX.heli_matrix(112.0, -12.0, 22.0)
    _fire(r, v_add(_HULL_CRASH_AT, m_apply(hmat, (0.2, 1.45, -0.85))), t, 10, 1.05)
    _fire(r, v_add(_HULL_CRASH_AT, m_apply(hmat, (0.5, 0.35, 1.15))), t, 17, 0.78)
    _f3d.emit_fire(r, _DEBRIS_FIRE_AT, t, seed=29, size=0.72, heat=1.1,
                   smoky=True, embers=True, bed=True, layer=2)
    _crash_embers(r, t, n=18)


def _interp_rot(m0, m1, u):
    """Orthonormal smooth interpolation between two 3x3 left-handed rotation matrices."""
    if u <= 0.0:
        return m0
    if u >= 1.0:
        return m1
    y0, y1 = (m0[1], m0[4], m0[7]), (m1[1], m1[4], m1[7])
    z0, z1 = (m0[2], m0[5], m0[8]), (m1[2], m1[5], m1[8])
    yh, zh = _mix(y0, y1, u), _mix(z0, z1, u)
    zn = math.sqrt(sum(c * c for c in zh)) or 1.0
    Z = tuple(c / zn for c in zh)
    X = (yh[1] * Z[2] - yh[2] * Z[1], yh[2] * Z[0] - yh[0] * Z[2], yh[0] * Z[1] - yh[1] * Z[0])
    xn = math.sqrt(sum(c * c for c in X)) or 1.0
    X = tuple(c / xn for c in X)
    Y = (Z[1] * X[2] - Z[2] * X[1], Z[2] * X[0] - Z[0] * X[2], Z[0] * X[1] - Z[1] * X[0])
    return (X[0], Y[0], Z[0], X[1], Y[1], Z[1], X[2], Y[2], Z[2])


def _draw_sniper_world(r, pos, rot):
    m = _sniper_prop()
    verts = [v_add(pos, m_apply(rot, v)) for v in m.verts]
    r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces])


def _crash_actors(r, t, maru_mouth=0.0, biri_mouth=0.0, handoff_u=0.0, has_rifle=True, nod=0.0,
                  body_p=-32.0, head_p=2.0, head_y=-4.0, biri_look_maru=False, biri_brace=0.0):
    m_hum = _w.hum("maru")
    b_hum = _w.hum(BIRI, flags=("sniper_rifle",))
    b_weapon = getattr(b_hum, "_weapon", "sniper")
    fore_local = GRIPS.get(b_weapon, GRIPS["sniper"])["fore"]
    m_yaw = 225.0
    b_yaw = 45.0

    # Maru slumped solidly back against the 0.72 m mossy log; right leg pinned flat under girder
    lean_m = _k(handoff_u, 0.0, 0.20) * (1.0 - _k(handoff_u, 0.52, 0.42)) if (has_rifle and handoff_u < 1.0) else 0.0
    m_base = dict(POSES["dead_back"], body_p=body_p, spine=14.0 + 10.0 * lean_m, head_p=head_p + nod,
                  head_y=head_y, lhip_p=78.0, lkn=54.0, lank=18.0,
                  rhip_p=54.0, rkn=18.0, rank=24.0)
    m_base = solve_arm_safe(m_hum, m_base, _MARU_CRASH_AT, m_yaw, "l",
                            (_MARU_CRASH_AT[0] + 0.46, 0.10, _MARU_CRASH_AT[2] - 0.16),
                            poles=((0.7, -0.6, -0.3),) + POLES)

    b_kneel_base = dict(POSES["kneel"], spine=14.0 + 4.0 * biri_brace, head_p=10.0)
    if biri_look_maru:
        m_head = m_hum.pose_world(m_base, _MARU_CRASH_AT, m_yaw, rifle_on=False)[1]["head"]
        hy_lk, hp_lk = solve_look((_BIRI_CRASH_AT[0] + 0.08, 1.24, _BIRI_CRASH_AT[2] + 0.08), m_head, b_yaw)
        b_kneel_base["head_y"] = hy_lk
        b_kneel_base["head_p"] = hp_lk
    b_final = hold_cached(b_hum, b_kneel_base, b_weapon, "ready",
                          key=("m8_biri_sniper", b_weapon, "ready"))

    if not has_rifle:
        m_pose = dict(m_base, rsh_p=12.0, rsh_r=14.0, rel=32.0)
        _w.actor(r, "maru", m_pose, _MARU_CRASH_AT, m_yaw, int(t), seed=71, amp=0.14,
                 expression="sad", mouth=maru_mouth)
        b_pose = dict(b_kneel_base, rsh_p=24.0, rel=48.0, lsh_p=24.0, lel=48.0)
        _w.actor(r, BIRI, b_pose, _BIRI_CRASH_AT, b_yaw, int(t), seed=93, amp=0.10,
                 rifle_on=False, expression="worried", mouth=biri_mouth)
        return

    if handoff_u < 1.0:
        # Maru holds the sniper rifle across chest/lap height and extends it outward toward Biribel;
        # Biribel leans gently to take it cleanly with zero knee/boot or face-in-gun collision.
        m_sh = shoulder_world(m_hum, m_base, _MARU_CRASH_AT, m_yaw, "r")
        offer = _k(handoff_u, 0.0, 0.35)
        m_hold_tgt = (m_sh[0] - 0.26 - 0.08 * offer, max(0.46, m_sh[1] - 0.14 + 0.07 * offer),
                      m_sh[2] - 0.24 - 0.08 * offer)
        m_reach = solve_arm_safe(m_hum, m_base, _MARU_CRASH_AT, m_yaw, "r", m_hold_tgt,
                                 poles=((0.4, -0.3, -0.8),) + POLES)
        m_rhand = m_hum.pose_world(m_reach, _MARU_CRASH_AT, m_yaw, rifle_on=False)[1]["rhand"]
        rel_m = _k(handoff_u, 0.48, 0.34)
        m_rest = dict(m_base, rsh_p=12.0, rsh_r=14.0, rel=32.0)
        m_pose = blend(m_reach, m_rest, rel_m)
        _w.actor(r, "maru", m_pose, _MARU_CRASH_AT, m_yaw, int(t), seed=71, amp=0.0,
                 expression="sad", mouth=maru_mouth)

        R_start = m_mul(rot_y(132.0), rot_x(-6.0))
        m_grip_off = m_apply(R_start, (0.0, 0.02, fore_local[2] * 0.72))
        O_start = (m_rhand[0] - m_grip_off[0], m_rhand[1] - m_grip_off[1], m_rhand[2] - m_grip_off[2])
        _pl, b_end_j, _rt = b_hum.pose_world(b_final, _BIRI_CRASH_AT, b_yaw, rifle_on=True)
        O_end, R_end = b_end_j["rhand"], b_end_j["rifle_m"]

        grab_u = _k(handoff_u, 0.10, 0.34)
        pull_u = _k(handoff_u, 0.48, 0.50)
        lean_b = _k(handoff_u, 0.05, 0.32) * (1.0 - _k(handoff_u, 0.48, 0.48))
        b_pos = _mix(_BIRI_CRASH_AT, (_BIRI_CRASH_AT[0] + 0.18, 0.0, _BIRI_CRASH_AT[2] + 0.18), lean_b)

        O_cur = _mix(O_start, O_end, pull_u)
        R_cur = _interp_rot(R_start, R_end, pull_u)
        l_local = _mix((0.0, 0.01, fore_local[2] * 0.45), fore_local, pull_u)
        l_off = m_apply(R_cur, l_local)
        l_tgt = (O_cur[0] + l_off[0], O_cur[1] + l_off[1], O_cur[2] + l_off[2])

        b_wait = dict(POSES["kneel"], spine=12.0 + 14.0 * lean_b, head_p=14.0, head_y=-4.0,
                      rsh_p=24.0, rel=48.0, lsh_p=24.0, lel=48.0)
        b_hold = solve_arm_safe(b_hum, b_wait, b_pos, b_yaw, "r", O_cur,
                                poles=((0.6, -0.8, -0.4),) + POLES)
        b_hold = solve_arm_safe(b_hum, b_hold, b_pos, b_yaw, "l", l_tgt,
                                poles=((-0.6, -0.8, 0.4),) + POLES)
        b_pose = blend(b_wait, b_hold, grab_u)
        if pull_u > 0.0:
            b_pose = blend(b_pose, b_final, pull_u * pull_u)

        b_cur_j = b_hum.pose_world(b_pose, b_pos, b_yaw, rifle_on=False)[1]
        O_draw = _mix(O_cur, b_cur_j["rhand"], _k(pull_u, 0.0, 0.35))
        _w.actor(r, BIRI, b_pose, b_pos, b_yaw, int(t), seed=93, amp=0.0,
                 rifle_on=False, expression="worried", mouth=biri_mouth)
        _draw_sniper_world(r, O_draw, R_cur)
    else:
        m_pose = dict(m_base, rsh_p=12.0, rsh_r=14.0, rel=32.0)
        _w.actor(r, "maru", m_pose, _MARU_CRASH_AT, m_yaw, int(t), seed=71, amp=0.14,
                 expression="sad", mouth=maru_mouth)
        _w.actor(r, BIRI, b_final, _BIRI_CRASH_AT, b_yaw, int(t), seed=93, amp=0.06,
                 rifle_on=True, flags=("sniper_rifle",), expression="angry", mouth=biri_mouth)
    return m_pose


def crash_fire(surface, t):
    """3/4 two-shot in the firelit clearing: Maru pinned under a heavy sheared girder passes
    the sniper rifle to Biribel while the burning gunship glows behind them."""
    u = _k(t, 0, 4600)
    jit, jroll = _handheld(t, amp=0.014, roll_amp=0.25, seed=72)
    eye = v_add(_mix((2.85, 1.32, -4.15), (2.45, 1.26, -3.75), u), jit)
    tgt = _mix((-0.42, 0.72, 0.15), (-0.36, 0.74, 0.18), u)
    r = DS.crash_frame(eye, tgt, 46.0 - 2.0 * u, t=int(t), size=FILM,
                       lights=_fire_lights(t), pools=_fire_pools(t), roll=jroll)
    del _w.LAST[:]
    _crash_set(r, t)
    _crash_actors(r, t, maru_mouth=_talk(t, 250, 4000), handoff_u=_k(t, 1200, 3200), has_rifle=True)
    _finish(surface, r, t, 7)


def crash_promise(surface, t):
    """3/4 front medium close-up on Biribel kneeling with the rifle: 'I'll come back for you.'
    Split warm/cool noir lighting with burning tail wreckage and embers behind him."""
    u = _k(t, 0, 3000)
    jit, jroll = _handheld(t, amp=0.010, roll_amp=0.20, seed=73)
    eye = v_add(_mix((1.30, 1.28, -0.68), (1.08, 1.26, -0.74), u), jit)
    tgt = _mix((-0.62, 1.14, -1.04), (-0.62, 1.15, -1.04), u)
    r = DS.crash_frame(eye, tgt, 38.0 - 2.0 * u, t=int(t), size=FILM,
                       lights=_fire_lights(t), pools=_fire_pools(t), roll=jroll)
    del _w.LAST[:]
    _crash_set(r, t)
    _crash_actors(r, t, biri_mouth=_talk(t, 200, 2200), handoff_u=1.0, has_rifle=True,
                  biri_look_maru=True, biri_brace=_k(t, 400, 1800))
    _finish(surface, r, t, 14)


def crash_better(surface, t):
    """Front 3/4 close-up on Maru's firelit face: 'You'd better.' — then a clean upward
    crane above the clearing toward the dark Carpathian pine ridge."""
    u = _k(t, 0, 2600)
    lift_u = _k(t, 1850, 750)
    m = _MARU_CRASH_AT
    nod = 6.0 * math.sin(_k(t, 600, 900) * math.pi)
    m_hum = _w.hum("maru")
    m_pose = dict(POSES["dead_back"], body_p=-32.0, spine=14.0, head_p=2.0 + nod,
                  head_y=-4.0, lhip_p=78.0, lkn=54.0, lank=18.0,
                  rhip_p=54.0, rkn=18.0, rank=24.0)
    head_j = m_hum.pose_world(m_pose, m, 225.0, rifle_on=False)[1]["head"]
    # Camera strictly in front of Maru's SW (225 deg) face vector, clear of Biribel behind it
    tgt_maru = (head_j[0] - 0.04, head_j[1] - 0.06, head_j[2])
    eye_maru = _mix((0.18, 1.06, -1.16), (0.22, 1.04, -1.02), u)
    eye_ridge = (0.35, 2.15, -1.35)
    tgt_ridge = (-1.20, 5.20, 9.50)
    jit, jroll = _handheld(t, amp=0.010, roll_amp=0.18, seed=74)
    eye = v_add(_mix(eye_maru, eye_ridge, lift_u), jit)
    tgt = _mix(tgt_maru, tgt_ridge, lift_u)
    fov = 36.0 - 2.0 * u + 10.0 * lift_u
    face_key = {"pos": (head_j[0] - 1.1, head_j[1] + 0.25, head_j[2] - 0.8),
                "color": (236, 178, 124), "intensity": 0.42, "range": 4.5}
    r = DS.crash_frame(eye, tgt, fov, t=int(t), size=FILM,
                       lights=_fire_lights(t, close_key=face_key), pools=_fire_pools(t), roll=jroll)
    del _w.LAST[:]
    _crash_set(r, t)
    _crash_actors(r, t, maru_mouth=_talk(t, 200, 1800), handoff_u=1.0, has_rifle=True,
                  nod=nod, body_p=-32.0, head_p=2.0, head_y=-4.0)
    _finish(surface, r, t, 15)


# --- Duty epilogue: Capital Square inauguration --------------------------------

CH = DS.CH
TOP = DS.TOP
VAS_AT = DS.VAS_AT
CROWD_Z = DS.CROWD_Z
BIRI_AT = (CH[0] - 1.35, 0.08, CROWD_Z - 1.2)
MARU_AT = (CH[0] - 0.35, 0.08, CROWD_Z - 1.35)
BODI_AT = (CH[0] - 1.85, 0.08, CROWD_Z - 2.6)
ALEX_AT = (CH[0] - 0.75, 0.08, CROWD_Z - 2.7)


def _sq_grade(r):
    """Dawn with a low raking key and late haze: the square keeps its contrast
    and the ministries behind it still read through the fog."""
    r.light = Light(direction=(0.80, 0.34, -0.42), ambient=0.34, diffuse=0.78,
                    sky=0.14, tint=(1.0, 0.87, 0.74))
    r.fog, r.fog_start, r.fog_end = (184, 176, 184), 55.0, 220.0


def _inaug(eye, tgt, fov, t):
    r = CS.frame(eye, tgt, fov, t=int(t), size=FILM, look="dawn", lights=DS.courthouse_lights())
    _sq_grade(r)
    del _w.LAST[:]
    CS.put(r, "m8d_courthouse_sq", DS.courthouse_square, (0.0, 0.0, 0.0))
    # Ceremonial honor guard flanking the top terrace
    g_pose = dict(POSES["stand"], lsh_p=12, lel=22, rsh_p=12, rel=22)
    for gx, gyaw in ((-5.4, 180.0), (5.4, 180.0), (-8.6, 170.0), (8.6, 190.0)):
        _w.actor(r, ("guard", "officer"), g_pose, (CH[0] + gx, TOP, CH[2] - 0.9),
                 gyaw, int(t), seed=int(abs(gx) * 10), amp=0.05, rifle_on=True, flags=("os12",))
    return r


def _crowd(r, t, mains=True):
    DC.draw_crowd(r, t, CH, VAS_AT, CROWD_Z)
    if not mains:
        return
    _w.actor(r, BIRI, dict(POSES["stand"], spine=2), BIRI_AT, 34.0, int(t), seed=93, amp=0.12)
    DC.draw_maru_with_crutches(r, t, MARU_AT, 20.0)
    _w.actor(r, "bodi", dict(POSES["stand"]), BODI_AT, 26.0, int(t), seed=61, amp=0.15)
    _w.actor(r, "alex", dict(POSES["stand"]), ALEX_AT, 340.0, int(t), seed=62, amp=0.15)


def _vasile(r, t, mouth=0.0, **pose):
    _w.actor(r, "vasile", dict(POSES["stand"], **pose), VAS_AT, 180.0, int(t), seed=33,
             amp=0.1, mouth=mouth)


def _crt_power_on(surface, t):
    """Sharp State TV CRT power-on phosphor scanline & static snap-in on the opening 380 ms."""
    if t >= 380:
        return
    try:
        from core.user_settings import SETTINGS
        flash_red = bool(SETTINGS.flash_reduction)
    except Exception:
        flash_red = False
    band = surface.subsurface((0, _w.SAFE_TOP, WIDTH, _w.FILM_H))
    h = band.get_height()
    cy = h // 2
    u = max(0.0, min(1.0, t / 380.0))
    # CRT vertical deflection expansion from a bright center horizontal scanline
    open_k = u * u * (3.0 - 2.0 * u)
    half_h = max(2, int(cy * open_k))
    top_mask = max(0, cy - half_h)
    if top_mask > 0:
        band.fill((6, 8, 10), (0, 0, WIDTH, top_mask))
        band.fill((6, 8, 10), (0, cy + half_h, WIDTH, h - (cy + half_h)))
    # Horizontal phosphor beam flash + static snow bars
    fk = (0.45 if flash_red else 1.0) * (1.0 - u)
    beam_c = (min(255, max(0, int(210 * fk + 24))),
              min(255, max(0, int(230 * fk + 24))),
              min(255, max(0, int(245 * fk + 24))))
    if top_mask > 0:
        pygame.draw.line(band, beam_c, (0, top_mask), (WIDTH, top_mask), 2)
        pygame.draw.line(band, beam_c, (0, min(h - 1, cy + half_h)), (WIDTH, min(h - 1, cy + half_h)), 2)
    for i in range(10):
        sy = int((cy - half_h) + ((i * 67 + int(t * 3)) % max(1, 2 * half_h)))
        sc = min(240, max(0, int((140 if not flash_red else 75) * (1.0 - u))))
        if sc > 8:
            pygame.draw.line(band, (sc, min(255, sc + 8), min(255, sc + 12)), (0, sy), (WIDTH, sy), 1)


def inauguration(surface, t):
    """State TV: the Capital Square courthouse steps at dawn, the oath."""
    u = _k(t, 0, 6000)
    eye = _mix((CH[0] + 15.0, 5.2, CH[2] - 34.0), (CH[0] + 11.0, 4.6, CH[2] - 28.0), u)
    tgt = _mix((CH[0], 5.8, CH[2] + 2.0), (CH[0], 6.0, CH[2] + 1.0), u)
    r = _inaug(eye, tgt, 55.0 - 3.0 * u, t)
    _vasile(r, t)
    _crowd(r, t)
    _finish(surface, r, t, 8)
    _crt_power_on(surface, t)
    from cutscenes.m8films import _tv
    _tv(surface, t, "INTERIM PRESIDENT VASILE TAKES THE OATH")


def vasile_speech(surface, t):
    """Medium close on Vasile at the podium beneath the columns and crest."""
    u = _k(t, 0, 5000)
    eye = _mix((CH[0] + 1.7, 2.62, CH[2] - 6.9), (CH[0] + 1.2, 2.58, CH[2] - 6.1), u)
    r = _inaug(eye, (VAS_AT[0], 2.86, VAS_AT[2]), 40.0, t)
    _vasile(r, t, mouth=_talk(t, 300, 3600))
    _crowd(r, t)
    _finish(surface, r, t, 9)


def crowd(surface, t):
    """In the Capital Square crowd: Biribel, Maru on crutches beside him, Bodi and Alex behind."""
    u = _k(t, 0, 5600)
    eye = _mix((CH[0] + 2.6, 1.60, CROWD_Z + 2.3), (CH[0] + 2.0, 1.55, CROWD_Z + 1.8), u)
    r = _inaug(eye, (CH[0] - 1.0, 1.15, CROWD_Z - 1.5), 46.0, t)
    _vasile(r, t)
    _crowd(r, t)
    _finish(surface, r, t, 10)


def eyes(surface, t):
    """Vasile finds Biribel in the plaza crowd below. A tiny nod."""
    u = _k(t, 0, 4200)
    nod = 8.0 * _k(t, 2200, 500) * (1.0 - _k(t, 2900, 500))
    eye = _mix((VAS_AT[0] - 1.05, VAS_AT[1] + 1.62, VAS_AT[2] - 2.75),
               (VAS_AT[0] - 0.95, VAS_AT[1] + 1.60, VAS_AT[2] - 2.55), u)
    r = _inaug(eye, (VAS_AT[0], VAS_AT[1] + 1.52, VAS_AT[2]), 34.0, t)
    look = R._wrap(R._yaw(BIRI_AT[0] - VAS_AT[0], BIRI_AT[2] - VAS_AT[2]) - 180.0)
    _vasile(r, t, head_y=look * 0.6, head_p=nod)
    _crowd(r, t)
    _finish(surface, r, t, 11)


def biribel_vo(surface, t):
    """Biribel in the square, face on from the front, the crowd massed behind him."""
    u = _k(t, 0, 6000)
    eye = _mix((BIRI_AT[0] + 1.1, 1.62, BIRI_AT[2] + 3.4),
               (BIRI_AT[0] + 0.85, 1.58, BIRI_AT[2] + 3.1), u)
    r = _inaug(eye, (BIRI_AT[0], 1.50, BIRI_AT[2]), 40.0, t)
    _vasile(r, t)
    _crowd(r, t)
    _finish(surface, r, t, 12)


def title_card(surface, t):
    """Wide dawn crane over Capital Square; the title sits cleanly in the sky above the pediment."""
    from core.config import font_title
    u = _k(t, 0, 6000)
    eye = (CH[0] + 12.0, 6.5 + 3.0 * u, CH[2] - 44.0)
    r = _inaug(eye, (CH[0], 8.2 + 1.2 * u, CH[2] + 2.0), 50.0, t)
    _vasile(r, t)
    _crowd(r, t, mains=True)
    _finish(surface, r, t, 13)
    a = _k(t, 500, 1800)
    img = font_title.render("CALL OF ACARISTAN", True, (232, 226, 210))
    img.set_alpha(int(255 * a))
    surface.blit(img, ((WIDTH - img.get_width()) // 2, _w.SAFE_TOP + int(_w.FILM_H * 0.14)))