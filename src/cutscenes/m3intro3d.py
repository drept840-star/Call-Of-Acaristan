"""m3intro3d.py - 3D engine3d takes for Mission 3's cold-open interrogation intro.

One shared Stabilization Center interrogation cell + a State Broadcast studio
feed for the wall monitor, serving the four M3 intro scene IDs:

    cell_ceiling        waking POV up at the buzzing fluorescent cage & dome cam
    cell_restraints     low POV down at Biribel's cuffed wrists on the steel chair
    interrogation_room  archive wide: restrained Biribel, pacing Balaceanu, wall CRT
    monitor_broadcast   push onto the bolted wall CRT showing 22:00 State Address

Falls back cleanly to cutscenes.m3cell 2D takes when ACARISTAN_CUTSCENE3D=0
or if 3D raises. Pure functions of t; zero mission imports.
"""
import math
import os

import pygame

from core.config import (
    HEIGHT, SCENE_H, SCENE_TOP, WIDTH,
    font_terminal, font_terminal_small,
)
from cutscenes.cast3d import humanoid3d

__all__ = ["SCENES", "m3intro3d_enabled", "draw_scene"]

SCENES = ("cell_ceiling", "cell_restraints", "interrogation_room", "monitor_broadcast")
RES = 0.64
RW, RH = int(WIDTH * RES), int(SCENE_H * RES)

_PRISONER = dict(
    jacket=(88, 64, 46), pants=(88, 64, 46), vest=None,
    pouches=False, accent=None, armband=(88, 64, 46), belt=None,
    buckle=None, cuff=(56, 42, 32), lapel=None, shirt=None,
)

_S = {"sets": {}, "rigs": {}, "failed": False, "err": None}


def m3intro3d_enabled():
    if os.environ.get("ACARISTAN_CUTSCENE3D", "1").strip() == "0":
        return False
    return not _S["failed"]


def _smooth(v):
    v = max(0.0, min(1.0, float(v)))
    return v * v * (3.0 - 2.0 * v)


def _faces(m):
    return [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces]


def _add(r, m):
    r.add_dynamic(m.verts, _faces(m))


def _rig(who):
    if who not in _S["rigs"]:
        _S["rigs"][who] = humanoid3d(who, **(_PRISONER if who == "biribel" else {}))
    return _S["rigs"][who]


def _set(key, fog, fs, fe, builder):
    if key not in _S["sets"]:
        from engine3d import Renderer
        r = Renderer(RW, RH, fog=fog, fog_start=fs, fog_end=fe)
        r.light_cap = 8
        builder(r)
        _S["sets"][key] = (r, pygame.Surface((RW, RH)))
    return _S["sets"][key]


def _build_cell(r):
    from engine3d.core import box, quad_xz
    from cutscenes.ps2mat import mesh as textured

    def bake(m):
        r.bake(textured(m))

    # Cold concrete floor, ceiling & walls (subdivided for near-clip safety)
    bake(quad_xz(-3.4, -3.0, 3.4, 4.4, 0.0, (44, 47, 48), seg=0.9))
    bake(box(6.8, 0.16, 7.4, (36, 39, 41), center=(0.0, 3.16, 0.7), seg=1.0))
    for side in (-1, 1):
        bake(box(0.20, 3.2, 7.4, (50, 54, 56), center=(side * 3.3, 1.6, 0.7), seg=0.9))
        bake(box(0.06, 0.96, 7.3, (30, 38, 40), center=(side * 3.18, 0.48, 0.7), seg=0.9))
    bake(box(6.8, 3.2, 0.22, (46, 50, 53), center=(0.0, 1.6, 4.3), seg=0.9))
    bake(box(6.8, 3.2, 0.22, (40, 44, 46), center=(0.0, 1.6, -2.9), seg=0.9))

    # Ceiling beams, pipes & caged fluorescent fixture at (0, 2.96, 1.45)
    for z in (-1.2, 0.4, 2.2, 3.6):
        bake(box(6.5, 0.16, 0.18, (32, 36, 38), center=(0.0, 3.02, z), seg=1.2))
    for px in (-1.35, -1.18, 1.45):
        bake(box(0.06, 0.06, 7.0, (66, 70, 68), center=(px, 2.86, 0.7), seg=1.0))
    bake(box(1.52, 0.10, 0.24, (28, 30, 32), center=(0.0, 2.98, 1.45)))
    bake(box(1.36, 0.045, 0.14, (206, 224, 228), center=(0.0, 2.91, 1.45), emissive=True))
    # Corner dome security camera
    bake(box(0.24, 0.16, 0.24, (22, 24, 26), center=(2.45, 2.94, 3.65)))
    bake(box(0.06, 0.06, 0.06, (236, 44, 38), center=(2.36, 2.86, 3.56), emissive=True))

    # Floor drainage grate + bolted anchor plate under chair
    bake(box(0.95, 0.015, 0.32, (22, 24, 26), center=(0.0, 0.008, 2.7)))
    bake(box(1.25, 0.03, 1.15, (28, 28, 28), center=(-0.65, 0.015, 1.55)))

    # Bolted steel interrogation chair at (-0.65, 0.0, 1.55), facing +x / slightly forward
    cx, cz = -0.65, 1.55
    bake(box(0.64, 0.08, 0.62, (42, 42, 40), center=(cx, 0.48, cz)))
    for dx in (-0.28, 0.28):
        for dz in (-0.26, 0.26):
            bake(box(0.07, 0.48, 0.07, (32, 32, 30), center=(cx + dx, 0.24, cz + dz)))
            bake(box(0.14, 0.04, 0.14, (58, 56, 52), center=(cx + dx, 0.03, cz + dz)))
    # Tall steel chair back + headrest brace
    bake(box(0.64, 0.96, 0.09, (36, 36, 35), center=(cx, 0.96, cz + 0.28)))
    bake(box(0.46, 0.22, 0.12, (26, 26, 26), center=(cx, 1.32, cz + 0.24)))
    # Wide bolted steel arm rails aligned directly under Biribel's seated forearms
    for sx in (-1, 1):
        bake(box(0.26, 0.09, 0.78, (44, 44, 42), center=(cx + sx * 0.36, 0.71, cz - 0.13)))
        bake(box(0.08, 0.71, 0.08, (32, 32, 30), center=(cx + sx * 0.42, 0.355, cz - 0.40)))
        bake(box(0.14, 0.04, 0.14, (58, 56, 52), center=(cx + sx * 0.42, 0.03, cz - 0.40)))

    # Back wall: one-way observation mirror (left) + glowing State Address monitor (right)
    bake(box(2.35, 1.24, 0.10, (24, 26, 30), center=(-1.25, 1.85, 4.18)))
    bake(box(2.15, 1.04, 0.04, (14, 20, 26), center=(-1.25, 1.85, 4.12)))
    # Wall monitor housing & glowing crimson screen
    bake(box(1.42, 0.96, 0.36, (20, 22, 26), center=(1.42, 2.02, 4.02)))
    bake(box(1.24, 0.78, 0.04, (118, 24, 24), center=(1.42, 2.02, 3.82), emissive=True))
    bake(box(1.10, 0.12, 0.05, (218, 72, 58), center=(1.42, 1.72, 3.80), emissive=True))

    # Heavy steel cell door on right wall with lit hallway observation slit
    bake(box(0.12, 2.32, 1.12, (36, 40, 42), center=(3.18, 1.16, 1.45)))
    bake(box(0.06, 0.14, 0.56, (186, 214, 228), center=(3.10, 1.62, 1.45), emissive=True))


def _build_balaceanu_tv(r):
    from engine3d.core import box, quad_xz
    from cutscenes.ps2mat import mesh as textured

    def bake(m):
        r.bake(textured(m))

    bake(quad_xz(-7, -5, 7, 8, 0.0, (20, 16, 20), seg=1.5))
    bake(box(14.0, 5.4, 0.3, (26, 14, 18), center=(0.0, 2.7, 5.2), seg=1.5))
    for cx in (-3.2, -1.7, 1.7, 3.2):
        bake(box(0.46, 5.0, 0.38, (132, 28, 30), center=(cx, 2.5, 4.85)))
        bake(box(0.54, 0.14, 0.44, (196, 162, 82), center=(cx, 4.95, 4.85)))
    bake(box(1.8, 1.24, 0.78, (54, 38, 30), center=(0.0, 0.62, 1.85)))
    bake(box(1.94, 0.10, 0.90, (74, 52, 38), center=(0.0, 1.26, 1.85)))
    bake(box(0.84, 0.30, 0.05, (202, 168, 84), center=(0.0, 0.92, 1.44)))


def _draw_cell_ceiling_3d(surface, t):
    from engine3d.core import Light
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx

    r, buf = _set("m3_cell", (8, 10, 12), 4.0, 14.0, _build_cell)
    sec = t * 0.001
    flick = 0.84 + 0.12 * math.sin(sec * 11.0) + 0.04 * math.sin(sec * 37.0)
    r.light = Light(direction=(0.0, 1.0, 0.0), ambient=0.28, diffuse=0.42,
                    sky=0.05, tint=(0.86, 0.94, 1.0))
    r.light_albedo, r.light_gain = True, 2.4
    r.set_lights([
        {"pos": (0.0, 2.82, 1.45), "color": (196, 220, 232), "intensity": 1.65 * flick, "range": 7.5},
        {"pos": (2.3, 2.82, 3.5), "color": (255, 48, 42), "intensity": 0.45, "range": 2.4},
    ], cap=8)

    focus = _smooth(t / 2200.0)
    sway_x = math.sin(sec * 0.9) * (0.14 - 0.08 * focus)
    sway_z = math.cos(sec * 0.7) * (0.12 - 0.06 * focus)
    eye = (-0.65 + sway_x, 1.15, 1.42 + sway_z)
    tgt = (0.18, 3.05, 1.85)
    _m5.set_cam(r, t, eye, tgt, 58, hh=0.02, roll=math.sin(sec * 0.5) * 4.0, seed=13)
    buf.fill((7, 9, 11))
    r.begin()
    r.add_static()
    r.add_sprite((0.0, 2.90, 1.45),
                 _fx.glow((196, 224, 236), 1.45, t, core=(244, 250, 255),
                          intensity=0.95 * flick), layer=_fx.FX_LAYER)
    if (int(t) // 460) % 2 == 0:
        r.add_sprite((2.36, 2.86, 3.56),
                     _fx.glow((255, 54, 46), 0.35, t, intensity=0.85), layer=_fx.FX_LAYER)
    r.flush(buf)
    _fx.grade_cine(buf)
    _fx.present_crisp(buf, surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_H)))

    # Slow groggy eyelid opening + one involuntary blink
    eye_open = 0.14 + 0.86 * _smooth((t - 180.0) / 1500.0)
    if 760 < t < 1040:
        eye_open *= 0.65
    lid_h = int((SCENE_H * 0.5) * max(0.0, 1.0 - eye_open))
    if lid_h > 0:
        lid = pygame.Surface((WIDTH, SCENE_H), pygame.SRCALPHA)
        pygame.draw.rect(lid, (2, 3, 4, 245), (0, 0, WIDTH, lid_h))
        pygame.draw.rect(lid, (2, 3, 4, 245), (0, SCENE_H - lid_h, WIDTH, lid_h))
        surface.blit(lid, (0, SCENE_TOP))


def _add_restrained_biribel(r, t, head_y=0.0, head_p=20.0, strain=0.0):
    """Place seated Biribel in the bolted chair with symmetrical forearms on the
    steel armrests and heavy sealed steel cuffs bolted around both wrists."""
    from engine3d.core import Mesh, box
    from cutscenes import m6world3d as W

    bir = _rig("biribel")
    pos = (-0.65, 0.0, 1.55)
    yaw = 180.0  # facing -Z toward camera
    tug = strain * 180.0  # small wrist-tug tremor while locked in cuffs
    b_pose = W.sit_pose(bir, 0.50, {
        "spine": 8.0 + abs(tug) * 1.2,
        "head_p": head_p,
        "head_y": head_y,
        "lsh_p": 14.0 + tug * 0.5,
        "rsh_p": 14.0 - tug * 0.5,
        "lsh_r": 22.0,
        "rsh_r": 22.0,
        "lel": 76.0,
        "rel": 76.0,
    })
    b_pose = W.life_pose(b_pose, t, amp=0.25, seed=1)
    bir.set_expression("stern", 0.0)
    joints = r.add_humanoid(bir, b_pose, pos, yaw, rifle_on=False)

    # Heavy sealed U-shaped steel cuffs bolted directly over Biribel's real wrist joints
    # onto the steel armrests (top of rail = y 0.755; wrist joint = y ~0.797).
    restraints = Mesh()
    for key, sx in (("lhand", 1), ("rhand", -1)):
        hx, hy, hz = joints[key]
        wx, wy, wz = hx, hy, hz + 0.065
        # Sealed steel shackle collar: top arch + left/right walls down to rail top (0.755)
        restraints.add(box(0.155, 0.038, 0.11, (162, 162, 154), center=(wx, wy + 0.064, wz)))
        restraints.add(box(0.034, 0.125, 0.11, (128, 128, 122), center=(wx - 0.066, 0.815, wz)))
        restraints.add(box(0.034, 0.125, 0.11, (128, 128, 122), center=(wx + 0.066, 0.815, wz)))
        # Bolted steel base plate + side lock block + specular bolt heads
        restraints.add(box(0.22, 0.024, 0.14, (74, 74, 70), center=(wx, 0.764, wz)))
        restraints.add(box(0.048, 0.058, 0.058, (92, 92, 88), center=(wx + sx * 0.095, 0.795, wz)))
        restraints.add(box(0.024, 0.026, 0.024, (220, 222, 214), center=(wx + sx * 0.095, 0.832, wz)))
        restraints.add(box(0.022, 0.022, 0.022, (206, 208, 200), center=(wx - sx * 0.088, 0.782, wz)))

    # Horizontal tactical chest restraint strap & steel buckle strapping torso to chair
    if "chest" in joints:
        cx0, cy0, cz0 = joints["chest"]
        restraints.add(box(0.46, 0.075, 0.32, (34, 38, 40), center=(cx0, cy0 - 0.04, cz0 + 0.02)))
        restraints.add(box(0.11, 0.085, 0.04, (152, 150, 142), center=(cx0, cy0 - 0.04, cz0 - 0.145)))
    _add(r, restraints)
    return joints


def _draw_cell_restraints_3d(surface, t):
    from engine3d.core import Light
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx

    r, buf = _set("m3_cell", (8, 10, 12), 4.0, 14.0, _build_cell)
    sec = t * 0.001
    flick = 0.88 + 0.12 * math.sin(sec * 13.0)
    r.light = Light(direction=(0.0, 1.0, -0.2), ambient=0.34, diffuse=0.52,
                    sky=0.06, tint=(0.90, 0.96, 1.0))
    r.light_albedo, r.light_gain = True, 2.5
    r.set_lights([
        {"pos": (-0.65, 2.75, 1.25), "color": (208, 226, 234), "intensity": 1.75 * flick, "range": 6.5},
        {"pos": (1.42, 2.0, 3.4), "color": (210, 52, 46), "intensity": 0.65, "range": 5.5},
    ], cap=8)

    # Front-3/4 close-up on restrained Biribel seated in the bolted chair:
    # shows his bowed head, chest strap, both forearms, and both wrists sealed in steel cuffs.
    u = _smooth(min(1.0, t / 3000.0))
    strain = math.sin(sec * 3.8) * 0.012
    eye = (-0.42 - 0.14 * u, 1.38 - 0.04 * u, -0.34 + 0.16 * u)
    tgt = (-0.65, 0.98, 1.40)
    _m5.set_cam(r, t, eye, tgt, 48, hh=0.010, seed=29)
    buf.fill((7, 9, 11))
    r.begin()
    r.add_static()

    _add_restrained_biribel(r, t, head_y=-4.0, head_p=20.0, strain=strain)

    r.flush(buf)
    _fx.grade_cine(buf)
    _fx.present_crisp(buf, surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_H)))


def _draw_interrogation_room_3d(surface, t):
    from engine3d.core import Light, Mesh, box, m_mul, rot_x, rot_y, rot_z
    from engine3d import POSES
    from engine3d.rig import mouth_flap
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx
    from cutscenes import m6world3d as W
    from core.cutscene_registry import current_shot

    r, buf = _set("m3_cell", (8, 10, 12), 4.0, 14.0, _build_cell)
    sec = t * 0.001
    shot = current_shot() or {}
    spk = (shot.get("speaker") or "").upper()
    bal_talking = "BALACEANU" in spk
    flick = 0.88 + 0.12 * math.sin(sec * 12.0)

    r.light = Light(direction=(-0.2, 0.9, -0.35), ambient=0.34, diffuse=0.50,
                    sky=0.06, tint=(0.90, 0.94, 0.98))
    r.light_albedo, r.light_gain = True, 2.5
    r.set_lights([
        {"pos": (0.0, 2.82, 1.45), "color": (204, 224, 232), "intensity": 1.65 * flick, "range": 8.0},
        {"pos": (1.42, 2.02, 3.55), "color": (224, 52, 46), "intensity": 1.15, "range": 6.5},
        {"pos": (2.90, 1.62, 1.45), "color": (162, 198, 222), "intensity": 0.70, "range": 4.2},
    ], cap=8)

    # Framed to keep Balaceanu's full head with headroom AND show both of Biribel's cuffed wrists.
    u = _smooth(min(1.0, t / 5000.0))
    eye = (-2.28 + 0.36 * u, 1.68 - 0.06 * u, -2.02 + 0.38 * u)
    tgt = (0.20, 1.18, 1.62)
    _m5.set_cam(r, t, eye, tgt, 48, hh=0.010, seed=43)
    buf.fill((7, 9, 12))
    r.begin()
    r.add_static()

    # Restrained Biribel seated in bolted chair with sealed steel wrist cuffs
    _add_restrained_biribel(r, t, head_y=-30.0, head_p=8.0, strain=0.0)

    # Prime Minister Balaceanu looming across from Biribel, holding Vostral dossier naturally by its top edge
    bal = _rig("balaceanu")
    pace = math.sin(sec * 0.7) * 0.12 if bal_talking else 0.0
    bal_pose = W.life_pose(dict(
        POSES["stand"],
        spine=5,
        head_y=12,
        rsh_p=36 if bal_talking else 14,
        rel=62 if bal_talking else 36,
        lsh_p=10,
        lsh_r=6,
        lel=18,
    ), t, amp=0.65, seed=2)
    bal.set_expression("angry" if bal_talking else "stern",
                       mouth_flap(t, 19) if bal_talking else 0.0)
    bal_pos = (1.16 + pace, 0.0, 1.50)
    joints = r.add_humanoid(bal, bal_pose, bal_pos, -88.0, rifle_on=False)

    # Vostral manila dossier held cleanly by its top edge in Balaceanu's hanging left hand
    if joints and "lhand" in joints:
        hx, hy, hz = joints["lhand"]
        raw = Mesh()
        # Local folder: top gripped edge at y=0, body hanging down to y=-0.28, thin along X
        raw.add(box(0.024, 0.28, 0.21, (208, 194, 154), center=(0.0, -0.145, 0.0)))
        raw.add(box(0.028, 0.28, 0.022, (176, 160, 122), center=(0.0, -0.145, -0.098)))
        raw.add(box(0.028, 0.048, 0.14, (176, 46, 38), center=(0.0, -0.095, 0.01)))
        xf = m_mul(rot_y(-82.0), rot_x(8.0))
        fm = Mesh()
        fm.add(raw, m=xf, t=(hx, hy - 0.02, hz))
        _add(r, fm)

    r.add_sprite((0.0, 2.90, 1.45), _fx.glow((200, 224, 234), 1.2, t, intensity=0.8 * flick),
                 layer=_fx.FX_LAYER)
    r.add_sprite((1.42, 2.02, 3.80), _fx.glow((226, 54, 48), 1.4, t, intensity=0.65),
                 layer=_fx.FX_LAYER)

    r.flush(buf)
    _fx.grade_cine(buf)
    _fx.present_crisp(buf, surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_H)))

    # Archive surveillance camera HUD overlay (matches "INTERROGATION RECORDING")
    rec_on = (int(t) // 480) % 2 == 0
    if rec_on:
        pygame.draw.circle(surface, (236, 54, 46), (42, SCENE_TOP + 26), 5)
    lbl = font_terminal_small.render("STATE SECURITY ARCHIVE // CELL 04 // REC", True, (186, 206, 214))
    surface.blit(lbl, (56, SCENE_TOP + 18))
    tc = font_terminal_small.render(f"21:42:{int(t // 1000) % 60:02d}", True, (158, 178, 188))
    surface.blit(tc, (WIDTH - tc.get_width() - 34, SCENE_TOP + 18))


def _draw_monitor_broadcast_3d(surface, t):
    from engine3d.core import Light
    from engine3d import POSES
    from engine3d.rig import mouth_flap
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx
    from cutscenes import m6world3d as W

    r, buf = _set("m3_bal_tv", (20, 12, 16), 8.0, 28.0, _build_balaceanu_tv)
    r.light = Light(direction=(0.0, 0.85, -0.5), ambient=0.42, diffuse=0.58,
                    sky=0.06, tint=(1.04, 0.90, 0.90))
    r.light_albedo, r.light_gain = True, 2.2
    r.set_lights([
        {"pos": (0.0, 3.8, 0.4), "color": (255, 232, 214), "intensity": 1.6, "range": 10.0},
        {"pos": (-2.4, 2.6, 3.6), "color": (232, 54, 48), "intensity": 1.3, "range": 8.0},
        {"pos": (2.4, 2.6, 3.6), "color": (232, 54, 48), "intensity": 1.3, "range": 8.0},
    ], cap=8)

    u = _smooth(min(1.0, t / 3600.0))
    eye = (0.0, 1.72, -1.25 + 0.55 * u)
    tgt = (0.0, 1.58, 2.2)
    _m5.set_cam(r, t, eye, tgt, 40, hh=0.008, seed=67)
    buf.fill((20, 12, 16))
    r.begin()
    r.add_static()

    bal = _rig("balaceanu")
    bp = W.life_pose(dict(POSES["stand"], rsh_p=30, rel=52, head_p=2), t, amp=0.8, seed=5)
    bal.set_expression("angry", mouth_flap(t, 29))
    r.add_humanoid(bal, bp, (0.0, 0.0, 2.38), 180.0, rifle_on=False)

    r.flush(buf)
    _fx.grade_cine(buf)

    # Bolted dark cell wall behind heavy CRT television bezel
    surface.fill((7, 8, 10))
    frame = pygame.Rect(88, SCENE_TOP + 22, WIDTH - 176, SCENE_H - 44)
    pygame.draw.rect(surface, (18, 18, 22), frame.inflate(28, 24), border_radius=14)
    pygame.draw.rect(surface, (58, 56, 62), frame.inflate(28, 24), 2, border_radius=14)
    _fx.present_crisp(buf, surface.subsurface(frame))

    # Broadcast banner + LIVE 22:00 bug + naming-slot lower third
    hdr_bg = pygame.Surface((frame.w, 30), pygame.SRCALPHA)
    hdr_bg.fill((138, 22, 24, 215))
    surface.blit(hdr_bg, (frame.x, frame.y))
    surface.blit(font_terminal.render("ACARISTAN STATE ADDRESS  //  22:00 NAMING SLOT",
                                      True, (248, 232, 220)), (frame.x + 14, frame.y + 5))
    if (int(t) // 400) % 2 == 0:
        pygame.draw.circle(surface, (255, 70, 62), (frame.right - 96, frame.y + 15), 5)
    surface.blit(font_terminal_small.render("LIVE 22:00", True, (255, 220, 206)),
                 (frame.right - 84, frame.y + 7))
    bot_bg = pygame.Surface((frame.w, 38), pygame.SRCALPHA)
    bot_bg.fill((22, 12, 14, 225))
    pygame.draw.rect(bot_bg, (214, 46, 38), (0, 0, frame.w, 4))
    surface.blit(bot_bg, (frame.x, frame.bottom - 38))
    surface.blit(font_terminal.render("ROUTE 12 PERPETRATOR: BIRIBEL  //  KRAP OPERATIVE",
                                      True, (248, 224, 212)), (frame.x + 18, frame.bottom - 29))
    for sy in range(frame.y, frame.bottom, 4):
        pygame.draw.line(surface, (0, 0, 0), (frame.x, sy), (frame.right, sy), 1)
    pygame.draw.rect(surface, (46, 42, 46), frame, 3, border_radius=4)


_DISPATCH = {
    "cell_ceiling": _draw_cell_ceiling_3d,
    "cell_restraints": _draw_cell_restraints_3d,
    "interrogation_room": _draw_interrogation_room_3d,
    "monitor_broadcast": _draw_monitor_broadcast_3d,
}


def draw_scene(scene_id, surface, t):
    if not m3intro3d_enabled():
        return False
    fn = _DISPATCH.get(scene_id)
    if fn is None:
        return False
    try:
        fn(surface, t)
        return True
    except Exception as e:
        _S["failed"], _S["err"] = True, e
        print(f"m3intro3d: disabled ({scene_id}: {e!r}), using 2D")
        return False
