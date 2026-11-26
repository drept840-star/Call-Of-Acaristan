"""route12_3d.py - engine3d takes for Mission 2's narrative cutscenes.

Converts the seven big narrative / spatial shots of Mission 2 to 3D while
leaving the dossier/bulletin/radio/blackout inserts in polished 2D:

    route12_checkpoint   rainy Route 12 toll plaza, booths, barrier, patrol
    route12_aftermath    burning checkpoint aftermath, fuel tanker inferno, Biribel
    route12_broadcast    State TV studio with Retardovici & Balaceanu at podium
    krap_door_kickin     safehouse apartment breach: splintering door & IPA rush
    seby_pickup_body     night highway looking down at fallen Seby & his OS-12
    seby_pickup_reach    kneeling POV reaching for Seby's OS-12 on wet asphalt
    seby_pickup_raise    OS-12 raised into moonlight + tactical weapon stat card

Falls back cleanly to the existing 2D renderers when ``ACARISTAN_CUTSCENE3D=0``
or if the 3D stack raises. No mission imports (boundary-clean).
"""
import math
import os
import random

import pygame

from core.config import (
    C_KRAP_BLUE, C_ORANGE, HEIGHT, SCENE_H, SCENE_TOP, WIDTH,
    font_dialogue, font_prompt, font_speaker, font_terminal, font_terminal_small,
)
from engine.text import T as _T

__all__ = ["SCENES", "route12_3d_enabled"]

RES = 0.64
RW, RH = int(WIDTH * RES), int(SCENE_H * RES)

SCENES = (
    "route12_checkpoint",
    "route12_aftermath",
    "route12_broadcast",
    "krap_door_kickin",
    "seby_pickup_body",
    "seby_pickup_reach",
    "seby_pickup_raise",
)

_S = {"sets": {}, "rigs": {}, "meshes": {}, "failed": False, "err": None}


def route12_3d_enabled():
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


def _rig(who, **kw):
    key = (who, tuple(sorted(kw.items())))
    if key not in _S["rigs"]:
        from cutscenes.cast3d import humanoid3d
        _S["rigs"][key] = humanoid3d(who, **kw)
    return _S["rigs"][key]


def _set(key, fog, fog_s, fog_e, builder):
    if key not in _S["sets"]:
        from engine3d import Renderer
        r = Renderer(RW, RH, fog=fog, fog_start=fog_s, fog_end=fog_e)
        r.light_cap = 8
        builder(r)
        _S["sets"][key] = (r, pygame.Surface((RW, RH)))
    return _S["sets"][key]


def _rain(r, t, n=120, xspan=18.0, z0=-4.0, z1=28.0, ymax=11.0):
    sec = t * 0.001
    for i in range(n):
        u = ((i * 0.6180339) % 1.0)
        v = ((i * 0.3819660 + 0.17) % 1.0)
        w = ((i * 0.7548776) % 1.0)
        x = (u * 2.0 - 1.0) * xspan
        z = z0 + v * (z1 - z0)
        y = ymax - (sec * 12.5 + w * ymax) % ymax
        r.add_line3d((x, y, z), (x - 0.14, y - 0.62, z), (108, 124, 152), 1, layer=3)


# ── 1. Route 12 Checkpoint & Aftermath set ────────────────────────────────

def _build_checkpoint(r):
    from engine3d.core import Mesh, box, quad_xz
    from cutscenes.ps2mat import mesh as textured

    def bake(m):
        r.bake(textured(m))

    # Wet asphalt highway & dark verges
    bake(quad_xz(-42, -14, 42, 68, -0.05, (14, 17, 20), seg=5.0))
    bake(quad_xz(-12, -14, 12, 68, 0.0, (28, 31, 36), seg=3.0))
    for lx in (-12.2, 12.2):
        bake(box(0.55, 0.24, 82.0, (56, 60, 64), center=(lx, 0.12, 27.0), seg=4.0))
        bake(box(0.14, 0.78, 82.0, (92, 98, 102), center=(lx * 1.04, 0.55, 27.0), seg=4.0))
    for z in range(-10, 64, 6):
        bake(quad_xz(-0.12, z, 0.12, z + 2.8, 0.015, (164, 146, 74), layer=1))

    # Overhead toll gantry canopy across the highway at z = 14
    bake(box(24.0, 1.35, 3.8, (46, 54, 62), center=(0.0, 5.85, 14.0), seg=2.0))
    bake(box(24.4, 0.22, 4.1, (76, 86, 94), center=(0.0, 6.62, 14.0), seg=2.0))
    # Signage fascia
    bake(box(9.6, 0.84, 0.18, (22, 34, 46), center=(0.0, 5.85, 12.02)))
    bake(box(9.2, 0.10, 0.06, (218, 176, 88), center=(0.0, 6.22, 11.92), emissive=True))
    # Concrete toll booths (4 lanes) + pillars supporting canopy
    for bx in (-9.0, -3.2, 3.2, 9.0):
        bake(box(1.9, 3.1, 3.2, (58, 66, 72), center=(bx, 1.55, 14.0)))
        bake(box(0.55, 2.5, 0.55, (64, 70, 76), center=(bx, 4.3, 14.0)))
        # Lit glass booth windows
        bake(box(1.42, 0.92, 0.06, (168, 198, 212), center=(bx, 2.05, 12.36), emissive=True))
        bake(box(1.42, 0.92, 0.06, (124, 152, 168), center=(bx, 2.05, 15.64), emissive=True))
        # Red/white concrete crash island nose
        bake(box(1.5, 0.72, 1.8, (76, 80, 84), center=(bx, 0.36, 11.4)))
        bake(box(1.54, 0.18, 0.5, (180, 56, 48), center=(bx, 0.52, 10.75)))
    # Striped barrier arms
    for bx in (-6.1, 0.0, 6.1):
        bake(box(3.8, 0.12, 0.12, (206, 206, 200), center=(bx, 1.15, 12.2)))
        for k in range(-2, 3):
            bake(box(0.35, 0.13, 0.13, (186, 46, 38), center=(bx + k * 0.78, 1.15, 12.2)))

    # Highway streetlamps along both shoulders
    for side in (-1, 1):
        for z in (-2.0, 10.0, 26.0, 42.0):
            x = side * 12.8
            bake(box(0.20, 6.8, 0.20, (34, 38, 44), center=(x, 3.4, z)))
            bake(box(1.8, 0.12, 0.14, (34, 38, 44), center=(x - side * 0.85, 6.75, z)))
            bake(box(0.55, 0.10, 0.30, (255, 212, 148),
                     center=(x - side * 1.65, 6.66, z), emissive=True))

    # Distant dark industrial/hill silhouettes on horizon
    rng = random.Random(212)
    for i in range(-9, 10):
        bx = i * 4.5
        bh = rng.uniform(4.5, 13.0)
        bake(box(3.6, bh, 4.0, (16, 19, 25), center=(bx, bh * 0.5, 58.0 + (i % 3) * 3.0), seg=2.0))


def _tanker_mesh(cx, cz, yaw_deg=12.0, burnt=False):
    from engine3d.core import Mesh, box, rot_y
    m = Mesh()
    cab_col = (34, 34, 36) if burnt else (58, 66, 74)
    tank_col = (44, 38, 36) if burnt else (128, 124, 114)
    stripe = (92, 34, 28) if burnt else (168, 44, 38)
    # Chassis & cab
    m.add(box(2.3, 0.65, 7.6, (26, 28, 30), center=(0.0, 0.72, 0.0)))
    m.add(box(2.25, 1.65, 2.0, cab_col, center=(0.0, 1.82, 2.75)))
    m.add(box(1.92, 0.62, 0.08, (24, 30, 38), center=(0.0, 2.05, 3.76)))
    # Cylindrical-ish faceted fuel tank
    m.add(box(2.1, 1.65, 5.2, tank_col, center=(0.0, 1.88, -1.0)))
    m.add(box(1.7, 1.90, 5.1, tank_col, center=(0.0, 1.88, -1.0)))
    m.add(box(2.14, 0.28, 5.15, stripe, center=(0.0, 1.88, -1.0)))
    # Wheels
    for wx in (-1.05, 1.05):
        for wz in (-2.6, -1.3, 2.6):
            m.add(box(0.38, 0.88, 0.88, (16, 16, 18), center=(wx, 0.44, wz)))
    out = Mesh()
    out.add(m, m=rot_y(yaw_deg), t=(cx, 0.0, cz))
    return out


def _draw_checkpoint_3d(surface, t, aftermath=False):
    from engine3d.core import Light, Mesh, box
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx
    from cutscenes import m6world3d as W
    from cutscenes import fire3d

    r, buf = _set("checkpoint", (14, 15, 20) if not aftermath else (26, 15, 12),
                  14.0, 74.0, _build_checkpoint)
    sec = t * 0.001
    u = _smooth(min(1.0, t / 6500.0))

    if not aftermath:
        r.light = Light(direction=(-0.35, 0.85, -0.4), ambient=0.38, diffuse=0.45,
                        sky=0.08, tint=(0.76, 0.84, 1.02))
        eye = (-4.5 + 3.2 * u, 2.4 - 0.35 * u, -4.5 + 3.8 * u)
        tgt = (0.4, 2.3, 14.0)
        lights = [
            {"pos": (-11.1, 6.4, 10.0), "color": (255, 194, 118), "intensity": 1.4, "range": 18.0},
            {"pos": (11.1, 6.4, 10.0), "color": (255, 194, 118), "intensity": 1.4, "range": 18.0},
            {"pos": (-5.5, 1.2, 6.0), "color": (255, 232, 184), "intensity": 1.2, "range": 14.0,
             "kind": "spot", "dir": (0.2, -0.1, 0.96), "cone": 0.82},
            {"pos": (0.0, 3.8, 12.2), "color": (120, 182, 224), "intensity": 0.9, "range": 12.0},
        ]
        top, bot = (6, 9, 16), (22, 24, 32)
    else:
        flick = 0.85 + 0.15 * math.sin(sec * 11.3) + 0.08 * math.sin(sec * 23.7)
        r.light = Light(direction=(0.15, 0.72, 0.65), ambient=0.32, diffuse=0.42,
                        sky=0.06, tint=(1.08, 0.76, 0.56))
        eye = (2.6 - 1.4 * u, 1.72, 1.8 + 1.4 * u)
        tgt = (-0.2, 1.75, 13.5)
        lights = [
            {"pos": (-1.5, 2.2, 11.2), "color": (255, 136, 48), "intensity": 2.4 * flick, "range": 22.0},
            {"pos": (3.2, 1.8, 13.2), "color": (255, 108, 38), "intensity": 1.8 * flick, "range": 18.0},
            {"pos": (-6.0, 2.0, 14.5), "color": (255, 124, 44), "intensity": 1.4 * flick, "range": 16.0},
        ]
        top, bot = (12, 8, 10), (46, 22, 16)

    r.light_albedo, r.light_gain = True, 2.4
    r.set_lights(lights, cap=8)
    _m5.set_cam(r, t, eye, tgt, 46, hh=0.02, seed=41)
    buf.fill(bot)
    _m5.night_sky(r, buf, t, top, bot, stars=0, clouds=2,
                  sodium=(56, 28, 18) if aftermath else (30, 24, 20), mist=bot)
    r.begin()
    r.add_static()

    # Vehicles & actors
    _add(r, _tanker_mesh(-1.2 if aftermath else 6.2, 12.2 if aftermath else 16.5,
                         yaw_deg=24.0 if aftermath else 6.0, burnt=aftermath))
    # Parked sedan on west lane
    car = Mesh()
    car.add(box(1.9, 0.85, 4.2, (48, 56, 66), center=(-6.2, 0.65, 8.2)))
    car.add(box(1.65, 0.65, 2.1, (38, 46, 56), center=(-6.2, 1.32, 7.9)))
    car.add(box(0.32, 0.16, 0.08, (255, 236, 186), center=(-6.8, 0.72, 10.32), emissive=True))
    car.add(box(0.32, 0.16, 0.08, (255, 236, 186), center=(-5.6, 0.72, 10.32), emissive=True))
    _add(r, car)

    lay = _fx.FX_LAYER
    if not aftermath:
        # Patrolling IPA guards
        ipa = _rig("ipa", rifle="rifle")
        from engine3d import POSES
        g1 = W.life_pose(dict(POSES["ready"]), t, amp=0.8, seed=1)
        g2 = W.life_pose(dict(POSES["stand"]), t, amp=0.8, seed=2)
        r.add_humanoid(ipa, g1, (-1.0 + math.sin(sec * 0.6) * 0.6, 0.0, 10.8), 185.0, rifle_on=True)
        r.add_humanoid(ipa, g2, (2.2, 0.0, 11.4), 160.0, rifle_on=True)
        # Headlight & lamp halos + wet reflections
        for x, z in ((-11.15, 10.0), (11.15, 10.0), (-11.15, 26.0), (11.15, 26.0)):
            r.add_sprite((x, 6.6, z), _fx.sodium_lamp(t, seed=int(x + z), radius_m=2.8), layer=lay)
            r.add_sprite((x, 0.04, z), _m5.wet_reflection((255, 186, 104), t, seed=int(z),
                                                          length_m=3.6, width_m=0.6, intensity=0.45), layer=2)
        for hx in (-6.8, -5.6):
            r.add_sprite((hx, 0.74, 10.35),
                         _fx.glow((255, 236, 184), 1.0, t, core=(255, 250, 224), intensity=0.9), layer=lay)
        _rain(r, t, n=130)
    else:
        # Biribel standing in silhouette watching the burning wreck
        bir = _rig("biribel")
        from engine3d import POSES
        bp = W.life_pose(dict(POSES["stand"], head_p=-4), t, amp=0.5, seed=7)
        r.add_humanoid(bir, bp, (0.55, 0.0, 5.2), 8.0, rifle_on=False)
        # Burning fuel pool + tanker inferno + smoke plumes
        fire_spots = [
            (-1.4, 1.9, 11.8, 1.85),
            (0.4, 0.25, 10.8, 1.50),
            (-3.6, 0.25, 12.6, 1.35),
            (2.8, 0.30, 13.0, 1.25),
            (-6.0, 0.40, 14.2, 1.15),
        ]
        for idx, (fx0, fy0, fz0, sz) in enumerate(fire_spots):
            fire3d.emit_fire(r, (fx0, fy0, fz0), t, seed=101 + idx * 17, size=sz,
                             smoky=True, layer=lay)
            r.add_sprite((fx0, fy0 + 0.6, fz0),
                         _fx.glow((255, 126, 44), sz * 2.2, t, seed=idx, intensity=0.75), layer=lay)
        # Drifting embers
        for i in range(36):
            age = (sec * 0.45 + i / 36.0) % 1.0
            ex = -7.0 + ((i * 1.73) % 14.0) + math.sin(sec * 2.0 + i) * 0.8
            ey = 0.4 + age * 6.5
            ez = 9.0 + ((i * 2.31) % 8.0)
            r.add_line3d((ex, ey, ez), (ex + 0.08, ey + 0.14, ez), (255, 178, 76), 1, layer=lay)

    r.flush(buf)
    _fx.grade_cine(buf)
    _fx.present_crisp(buf, surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_H)))

    # Crisp location/status plate
    lbl = ("CHECKPOINT 12 // ROUTE 12 // AFTERMATH" if aftermath
           else "CHECKPOINT 12 // ROUTE 12 // PUBLIC LABEL: MAG BOMBING")
    tag = font_terminal_small.render(lbl, True, (226, 168, 112) if aftermath else (154, 192, 224))
    bg = pygame.Surface((tag.get_width() + 24, tag.get_height() + 8), pygame.SRCALPHA)
    bg.fill((8, 10, 14, 175))
    pygame.draw.rect(bg, (196, 68, 44) if aftermath else C_KRAP_BLUE, (0, 0, 4, bg.get_height()))
    surface.blit(bg, (32, SCENE_TOP + 18))
    surface.blit(tag, (44, SCENE_TOP + 22))


# ── 2. Route 12 State Television Broadcast (3D studio inside CRT) ─────────

def _build_tv_studio(r):
    from engine3d.core import box, quad_xz
    from cutscenes.ps2mat import mesh as textured

    def bake(m):
        r.bake(textured(m))

    # Polished slate studio floor & raised dais
    bake(quad_xz(-9, -6, 9, 10, 0.0, (24, 26, 34), seg=1.5))
    bake(box(7.8, 0.26, 3.6, (34, 36, 46), center=(0.0, 0.13, 3.0), seg=1.5))
    bake(box(8.0, 0.05, 3.8, (148, 38, 36), center=(0.0, 0.27, 3.0)))
    # Back studio wall + IPA red/blue vertical columns
    bake(box(18.0, 6.2, 0.4, (22, 24, 34), center=(0.0, 3.1, 6.6), seg=1.5))
    for cx in (-4.4, -2.6, 2.6, 4.4):
        col = (124, 30, 32) if abs(cx) < 3.5 else (30, 56, 104)
        bake(box(0.55, 5.6, 0.45, col, center=(cx, 2.8, 6.2)))
        bake(box(0.64, 0.16, 0.54, (198, 166, 86), center=(cx, 5.45, 6.2)))
    # Gold presidential/state emblem behind podium
    bake(box(2.8, 2.2, 0.12, (28, 32, 44), center=(0.0, 3.25, 6.32)))
    bake(box(1.1, 1.1, 0.16, (206, 174, 88), center=(0.0, 3.32, 6.26)))
    bake(box(0.62, 0.62, 0.18, (142, 34, 32), center=(0.0, 3.32, 6.22)))
    # Heavy walnut & brass State Podium
    bake(box(2.5, 1.24, 0.92, (58, 42, 32), center=(0.0, 0.88, 2.25)))
    bake(box(2.65, 0.10, 1.05, (78, 56, 40), center=(0.0, 1.52, 2.25)))
    bake(box(1.10, 0.34, 0.06, (198, 166, 84), center=(0.0, 1.12, 1.76)))
    # Twin microphones
    for mx in (-0.52, 0.52):
        bake(box(0.03, 0.24, 0.03, (28, 30, 34), center=(mx, 1.66, 2.08)))
        bake(box(0.06, 0.06, 0.09, (56, 60, 66), center=(mx, 1.78, 2.04)))


def _draw_broadcast_3d(surface, t):
    from engine3d.core import Light
    from engine3d import POSES
    from engine3d.rig import mouth_flap
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx
    from cutscenes import m6world3d as W
    from core.cutscene_registry import current_shot

    r, buf = _set("tv_studio", (16, 14, 22), 10.0, 36.0, _build_tv_studio)
    shot = current_shot() or {}
    spk = (shot.get("speaker") or "").upper()
    bal_talking = "BALACEANU" in spk
    u = _smooth(min(1.0, t / 5000.0))

    r.light = Light(direction=(0.0, 0.82, -0.58), ambient=0.44, diffuse=0.58,
                    sky=0.08, tint=(1.0, 0.96, 0.94))
    r.light_albedo, r.light_gain = True, 2.2
    r.set_lights([
        {"pos": (0.0, 4.4, 0.6), "color": (255, 244, 226), "intensity": 1.6, "range": 12.0},
        {"pos": (-3.0, 3.2, 4.5), "color": (220, 68, 58), "intensity": 1.1, "range": 9.0},
        {"pos": (3.0, 3.2, 4.5), "color": (72, 118, 212), "intensity": 1.1, "range": 9.0},
    ], cap=8)

    # Subtle television camera push onto active speaker
    tx = 0.58 if bal_talking else -0.45
    eye = (tx * 0.45, 1.82, -1.75 + 0.55 * u)
    tgt = (tx * 0.55, 1.62, 2.6)
    _m5.set_cam(r, t, eye, tgt, 42, hh=0.008, seed=71)
    buf.fill((16, 14, 22))
    r.begin()
    r.add_static()

    pres = _rig("president")
    bal = _rig("balaceanu")
    p_pose = W.life_pose(dict(POSES["stand"], rsh_p=24 if not bal_talking else 6,
                              rel=54 if not bal_talking else 22, head_y=-6), t, amp=0.7, seed=1)
    b_pose = W.life_pose(dict(POSES["stand"], rsh_p=28 if bal_talking else 8,
                              rel=48 if bal_talking else 18, head_y=8), t, amp=0.7, seed=2)
    pres.set_expression("stern", mouth_flap(t, 31) if not bal_talking else 0.0)
    bal.set_expression("angry" if bal_talking else "stern", mouth_flap(t, 47) if bal_talking else 0.0)
    r.add_humanoid(pres, p_pose, (-0.64, 0.26, 2.86), 184.0, rifle_on=False)
    r.add_humanoid(bal, b_pose, (0.64, 0.26, 2.86), 176.0, rifle_on=False)

    r.flush(buf)
    _fx.grade_cine(buf)

    # Present inside a physical CRT monitor bezel + State Broadcast chyrons
    surface.fill((7, 8, 11))
    frame = pygame.Rect(68, SCENE_TOP + 16, WIDTH - 136, SCENE_H - 32)
    pygame.draw.rect(surface, (18, 20, 25), frame.inflate(22, 18), border_radius=12)
    pygame.draw.rect(surface, (52, 58, 68), frame.inflate(22, 18), 2, border_radius=12)
    _fx.present_crisp(buf, surface.subsurface(frame))
    # Broadcast top bug + LIVE dot
    top_bar = pygame.Surface((frame.w, 30), pygame.SRCALPHA)
    top_bar.fill((120, 22, 24, 210))
    surface.blit(top_bar, (frame.x, frame.y))
    hdr = font_terminal.render("ACARISTAN STATE TELEVISION // SPECIAL ADDRESS - ROUTE 12",
                               True, (244, 232, 218))
    surface.blit(hdr, (frame.x + 14, frame.y + 5))
    if (int(t) // 420) % 2 == 0:
        pygame.draw.circle(surface, (255, 76, 66), (frame.right - 64, frame.y + 15), 5)
    live = font_terminal_small.render("LIVE", True, (255, 224, 210))
    surface.blit(live, (frame.right - 50, frame.y + 7))
    # Lower-third breaking chyron
    ch_h = 40
    chy = pygame.Surface((frame.w, ch_h), pygame.SRCALPHA)
    chy.fill((16, 20, 28, 220))
    pygame.draw.rect(chy, (196, 36, 32), (0, 0, frame.w, 4))
    surface.blit(chy, (frame.x, frame.bottom - ch_h))
    brk = font_terminal.render(
        "BREAKING: KRAP DISCIPLINE FAILURE CITED IN ROUTE 12 DISASTER",
        True, (242, 228, 210),
    )
    surface.blit(brk, (frame.x + 18, frame.bottom - ch_h + 10))
    # Subtle CRT raster lines
    for sy in range(frame.y, frame.bottom, 4):
        pygame.draw.line(surface, (0, 0, 0), (frame.x, sy), (frame.right, sy), 1)
    pygame.draw.rect(surface, (42, 46, 54), frame, 3, border_radius=4)


# ── 3. KRAP Safehouse Door Kick-In Breach (3D dramatic action) ────────────

def _build_safehouse(r):
    from engine3d.core import box, quad_xz
    from cutscenes.ps2mat import mesh as textured

    def bake(m):
        r.bake(textured(m))

    # Dark safehouse interior floor & walls
    bake(quad_xz(-3.4, -3.5, 3.4, 7.5, 0.0, (28, 24, 22), seg=1.0))
    for side in (-1, 1):
        bake(box(0.24, 3.1, 11.0, (34, 30, 28), center=(side * 3.4, 1.55, 2.0), seg=1.0))
    bake(box(7.0, 0.20, 11.0, (22, 20, 20), center=(0.0, 3.12, 2.0), seg=1.2))
    # Door wall at z = 3.2 with open doorway x in [-0.68, +0.68], y in [0, 2.22]
    bake(box(2.75, 3.1, 0.28, (38, 34, 30), center=(-2.05, 1.55, 3.2), seg=1.0))
    bake(box(2.75, 3.1, 0.28, (38, 34, 30), center=(2.05, 1.55, 3.2), seg=1.0))
    bake(box(1.42, 0.90, 0.28, (38, 34, 30), center=(0.0, 2.67, 3.2)))
    # Wooden door frame jambs
    for sx in (-0.70, 0.70):
        bake(box(0.10, 2.26, 0.34, (64, 44, 28), center=(sx, 1.13, 3.2)))
    bake(box(1.50, 0.10, 0.34, (64, 44, 28), center=(0.0, 2.25, 3.2)))
    # Exterior corridor beyond the doorway (z = 3.3..7.4)
    bake(box(6.8, 3.1, 0.24, (44, 52, 66), center=(0.0, 1.55, 7.3), seg=1.0))
    # Small side table & toppled lamp inside safehouse
    bake(box(0.92, 0.74, 0.56, (52, 38, 26), center=(-2.2, 0.37, 1.4)))
    bake(box(0.32, 0.20, 0.24, (28, 32, 36), center=(-2.1, 0.84, 1.4)))


def _draw_door_kickin_3d(surface, t):
    from engine3d.core import Light, Mesh, box, rot_y, rot_z, m_mul
    from engine3d import POSES, pose_run
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx
    from cutscenes import m6world3d as W

    r, buf = _set("safehouse_breach", (6, 8, 14), 5.0, 20.0, _build_safehouse)
    phase = min(1.0, t / 6000.0)
    sec = t * 0.001
    breach = _smooth((phase - 0.24) / 0.14)  # slams open at t ~ 1440..2280ms
    rush = _smooth((phase - 0.36) / 0.34)    # IPA rush in

    # Strobe blue/red police/IPA lights pulsing in hallway
    strobe_b = 0.5 + 0.5 * math.sin(sec * 16.0)
    strobe_r = 0.5 + 0.5 * math.sin(sec * 16.0 + math.pi)

    r.light = Light(direction=(0.0, 0.75, 0.65), ambient=0.22 + 0.12 * breach,
                    diffuse=0.45, sky=0.05, tint=(0.74, 0.86, 1.15))
    r.light_albedo, r.light_gain = True, 2.8
    lights = [
        {"pos": (0.0, 1.8, 5.2), "color": (126, 178, 255), "intensity": 0.9 + 2.8 * breach, "range": 11.0},
        {"pos": (-1.4, 2.2, 4.8), "color": (56, 108, 255), "intensity": 1.6 * strobe_b, "range": 9.0},
        {"pos": (1.4, 2.2, 4.8), "color": (255, 58, 48), "intensity": 1.3 * strobe_r, "range": 8.0},
        {"pos": (-1.8, 1.3, 1.4), "color": (255, 176, 98), "intensity": 0.55 * (1.0 - 0.5 * breach), "range": 4.2},
    ]
    r.set_lights(lights, cap=8)

    # Camera impact jolt on breach, pulling back slightly as breachers surge in
    jolt = math.exp(-max(0.0, t - 1440.0) / 360.0) * (1.0 if t >= 1440.0 else 0.0)
    jx = math.sin(t * 0.075) * 0.14 * jolt
    jy = math.cos(t * 0.091) * 0.11 * jolt
    eye = (jx, 1.48 + jy - 0.24 * rush, -0.85 - 0.55 * rush)
    tgt = (0.0, 1.32 - 0.10 * rush, 3.4)
    _m5.set_cam(r, t, eye, tgt, 52 + 8 * breach, hh=0.025 + 0.05 * jolt,
                roll=math.sin(t * 0.04) * 5.0 * jolt, seed=91)

    buf.fill((4, 6, 12))
    r.begin()
    r.add_static()

    # Hinged wooden door leaf slamming open inward around x = -0.66, z = 3.2
    door_angle = -112.0 * breach
    dm = Mesh()
    dm.add(box(1.30, 2.18, 0.08, (68, 44, 26), center=(0.65, 1.09, 0.0)))
    dm.add(box(0.96, 0.78, 0.095, (52, 34, 20), center=(0.65, 1.56, 0.0)))
    dm.add(box(0.96, 0.78, 0.095, (52, 34, 20), center=(0.65, 0.62, 0.0)))
    dm.add(box(0.14, 0.05, 0.14, (196, 168, 92), center=(1.16, 1.04, 0.0)))
    door_w = Mesh()
    door_w.add(dm, m=rot_y(door_angle), t=(-0.65, 0.0, 3.16))
    _add(r, door_w)

    # Flying splinters on breach impact
    if breach > 0.02:
        sp = Mesh()
        age = max(0.0, (t - 1440.0) / 1000.0)
        for i in range(14):
            rng = random.Random(301 + i)
            vx = rng.uniform(-1.8, 1.8)
            vy = rng.uniform(0.4, 2.6)
            vz = rng.uniform(-3.6, -1.2)
            px = 0.45 + vx * age
            py = max(0.05, 1.05 + vy * age - 4.4 * age * age)
            pz = 3.1 + vz * age
            rot = m_mul(rot_y(i * 47 + age * 280), rot_z(i * 31 + age * 220))
            sp.add(box(0.05, 0.24, 0.04, (148, 108, 66)), m=rot, t=(px, py, pz))
        _add(r, sp)

    # Backlit IPA breachers storming through doorway
    if breach > 0.25:
        ipa = _rig("ipa", rifle="rifle")
        positions = [
            (0.05, 0.0, 4.4 - 3.3 * rush, 182.0),
            (-0.62, 0.0, 5.2 - 2.6 * rush, 174.0),
            (0.68, 0.0, 5.6 - 2.4 * rush, 190.0),
        ]
        for idx, (ax, ay, az, ayaw) in enumerate(positions):
            gp = pose_run(sec * 7.0 + idx * 1.4, lean=18)
            gp["rsh_p"] = 64
            gp["lsh_p"] = 58
            gp["rel"] = 48
            gp["lel"] = 52
            r.add_humanoid(ipa, gp, (ax, ay, az), ayaw, rifle_on=True)
            # Tactical weapon flashlight glare
            r.add_sprite((ax, 1.34, az - 0.45),
                         _fx.glow((210, 232, 255), 0.72, t, core=(255, 255, 255),
                                  intensity=1.05 * breach), layer=_fx.FX_LAYER)

    # Hallway floodlight & dust burst
    if breach > 0.05:
        r.add_sprite((0.0, 1.45, 3.6),
                     _fx.glow((128, 178, 255), 2.8, t, core=(230, 242, 255),
                              intensity=0.95 * breach), layer=_fx.FX_LAYER)
    else:
        # Flashing blue light leaking under closed door threshold
        r.add_sprite((0.0, 0.08, 3.12),
                     _fx.glow((64, 118, 255), 1.4, t, intensity=0.55 * strobe_b), layer=_fx.FX_LAYER)

    r.flush(buf)
    _fx.grade_cine(buf)
    _fx.present_crisp(buf, surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_H)))

    # Final blackout fade (t = 5.0..6.0s)
    if phase > 0.83:
        fade = (phase - 0.83) / 0.17
        blk = pygame.Surface((WIDTH, SCENE_H), pygame.SRCALPHA)
        blk.fill((0, 0, 0, int(255 * min(1.0, fade))))
        surface.blit(blk, (0, SCENE_TOP))


# ── 4. Seby OS-12 Pickup (3D night highway + 3D OS-12 rifle inspect) ──────

def _build_seby_highway(r):
    from engine3d.core import box, quad_xz
    from cutscenes.ps2mat import mesh as textured

    def bake(m):
        r.bake(textured(m))

    bake(quad_xz(-24, -8, 24, 52, 0.0, (24, 27, 32), seg=2.5))
    for x in (-9.0, 9.0):
        bake(box(0.5, 0.25, 60.0, (54, 58, 62), center=(x, 0.12, 22.0), seg=3.0))
    for z in range(-4, 48, 5):
        bake(quad_xz(-0.1, z, 0.1, z + 2.2, 0.012, (156, 138, 68), layer=1))
    # Distant toll gantry silhouette + streetlamp pole on right
    bake(box(19.0, 1.1, 1.6, (28, 34, 42), center=(0.0, 5.4, 28.0), seg=2.0))
    for gx in (-8.5, 8.5):
        bake(box(0.65, 5.4, 0.65, (32, 38, 46), center=(gx, 2.7, 28.0)))
    bake(box(0.18, 6.2, 0.18, (30, 34, 40), center=(4.8, 3.1, 7.5)))
    bake(box(1.8, 0.10, 0.12, (30, 34, 40), center=(3.9, 6.1, 7.5)))
    bake(box(0.45, 0.08, 0.24, (255, 206, 138), center=(3.1, 6.04, 7.5), emissive=True))
    # Dark crimson pool beside Seby
    from engine3d.core import disc_xz
    r.bake(disc_xz(-0.25, 2.55, 0.72, 0.014, (74, 14, 14), n=12, layer=1))


def _draw_seby_stat_card(surface, t):
    u = _smooth(t / 700.0)
    cw, ch = 368, 174
    cx = WIDTH - cw - 34
    cy = SCENE_TOP + SCENE_H - ch - 26 + int((1.0 - u) * 28)
    card = pygame.Surface((cw, ch), pygame.SRCALPHA)
    pygame.draw.rect(card, (10, 13, 18, int(226 * u)), (0, 0, cw, ch), border_radius=5)
    pygame.draw.rect(card, (68, 86, 108, int(230 * u)), (0, 0, cw, ch), 2, border_radius=5)
    pygame.draw.rect(card, (194, 152, 68, int(240 * u)), (0, 0, 5, ch))
    hdr = font_terminal_small.render("SEBY'S OS-12 - ACQUIRED", True, (226, 184, 96))
    card.blit(hdr, (16, 10))
    name = font_speaker.render("OS-12", True, (238, 242, 248))
    card.blit(name, (16, 28))
    cls = font_terminal_small.render("ASSAULT RIFLE  //  5.56 x 45 MM", True, (148, 186, 214))
    card.blit(cls, (112, 36))
    pygame.draw.line(card, (46, 58, 72, int(200 * u)), (16, 62), (cw - 16, 62), 1)
    rows = [
        ("MAGAZINE", "25 ROUNDS (FULL AUTO)"),
        ("ROLE", "MID-RANGE SUSTAINED FIRE"),
    ]
    for i, (k, v) in enumerate(rows):
        y = 72 + i * 24
        card.blit(font_terminal_small.render(k, True, (112, 130, 148)), (16, y))
        card.blit(font_terminal_small.render(v, True, (218, 224, 232)), (118, y))
    flav = font_terminal_small.render("Lower per-shot damage than pistol. Spray to suppress.",
                                      True, (168, 176, 184))
    card.blit(flav, (16, 134))
    surface.blit(card, (cx, cy))


def _draw_seby_pickup_3d(surface, t, beat):
    from engine3d.core import Light, Mesh, box, rot_x, rot_y, rot_z, m_mul
    from engine3d import POSES
    from engine3d.rig import os12_mesh
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx

    r, buf = _set("seby_highway", (11, 13, 18), 10.0, 58.0, _build_seby_highway)
    r.light = Light(direction=(0.3, 0.85, -0.45), ambient=0.38, diffuse=0.46,
                    sky=0.08, tint=(0.82, 0.88, 1.06))
    r.light_albedo, r.light_gain = True, 2.5
    r.set_lights([
        {"pos": (3.0, 5.8, 7.5), "color": (255, 198, 124), "intensity": 1.6, "range": 16.0},
        {"pos": (0.2, 1.6, 1.6), "color": (164, 196, 236), "intensity": 0.9, "range": 6.5},
    ], cap=8)

    if beat == "body":
        u = _smooth(t / 2200.0)
        eye = (0.05, 1.56 - 0.14 * u, 0.35 + 0.15 * u)
        tgt = (-0.10, 0.18, 2.45)
        fov = 48
    elif beat == "reach":
        u = _smooth(t / 1400.0)
        eye = (0.05, 1.42 - 0.56 * u, 0.50 + 0.55 * u)
        tgt = (0.12, 0.12, 2.25)
        fov = 46
    else:  # raise
        u = _smooth(t / 1400.0)
        eye = (0.05, 0.86 + 0.42 * u, 1.05 - 0.20 * u)
        tgt = (0.04, 0.52 + 0.52 * u, 2.45)
        fov = 44

    _m5.set_cam(r, t, eye, tgt, fov, hh=0.015, seed=53)
    buf.fill((10, 12, 18))
    _m5.night_sky(r, buf, t, (6, 8, 14), (20, 22, 30), stars=18, clouds=1,
                  sodium=(32, 24, 18), mist=(16, 18, 24))
    r.begin()
    r.add_static()

    # Fallen Seby (KRAP operator in dead_back pose)
    seby = _rig("biribel", vest=(34, 48, 66), jacket=(46, 62, 82))
    r.add_humanoid(seby, dict(POSES["dead_back"]), (-0.28, 0.0, 2.55), 32.0, rifle_on=False)

    # 3D OS-12 rifle: on asphalt in body/reach, lifted and angled for inspect in raise
    if "os12" not in _S["meshes"]:
        _S["meshes"]["os12"] = os12_mesh(with_mag=True)
    gun = _S["meshes"]["os12"]
    gm = Mesh()
    if beat == "body":
        xf = m_mul(rot_y(58.0), rot_z(88.0))
        gm.add(gun, m=xf, t=(0.36, 0.06, 2.15))
    elif beat == "reach":
        u = _smooth(t / 1400.0)
        xf = m_mul(rot_y(58.0 - 14.0 * u), rot_z(88.0 - 28.0 * u))
        gm.add(gun, m=xf, t=(0.36 - 0.12 * u, 0.06 + 0.18 * u, 2.15 - 0.25 * u))
        # Reaching gloved forearms in 3D foreground
        arm = Mesh()
        arm.add(box(0.085, 0.085, 0.52, (42, 54, 68), center=(0.24 - 0.08 * u, 0.56 - 0.30 * u, 1.48 + 0.32 * u)))
        arm.add(box(0.092, 0.075, 0.12, (28, 30, 34), center=(0.22 - 0.06 * u, 0.54 - 0.34 * u, 1.78 + 0.28 * u)))
        _add(r, arm)
    else:
        u = _smooth(t / 1400.0)
        wobble = math.sin(t * 0.0022) * 5.0
        xf = m_mul(rot_y(76.0 + wobble), rot_x(-8.0 + 4.0 * u))
        gm.add(gun, m=xf, t=(-0.10, 0.72 + 0.38 * u, 1.62))
        # Support & trigger gloved hands holding the OS-12
        hands = Mesh()
        hands.add(box(0.08, 0.09, 0.10, (28, 30, 34), center=(-0.18, 0.68 + 0.38 * u, 1.64)))
        hands.add(box(0.08, 0.09, 0.10, (28, 30, 34), center=(0.14, 0.70 + 0.38 * u, 1.60)))
        _add(r, hands)
    _add(r, gm)

    r.add_sprite((3.1, 6.0, 7.5), _fx.sodium_lamp(t, seed=9, radius_m=2.6), layer=_fx.FX_LAYER)
    _rain(r, t, n=85, xspan=10.0, z0=0.5, z1=22.0)

    r.flush(buf)
    _fx.grade_cine(buf)
    _fx.present_crisp(buf, surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_H)))
    if beat == "raise":
        _draw_seby_stat_card(surface, t)


# ── Public wrappers & registration ────────────────────────────────────────

def _wrap(scene_id, fn3d, fn2d):
    def draw(surface, t):
        if route12_3d_enabled():
            try:
                fn3d(surface, t)
                return
            except Exception as e:
                _S["failed"], _S["err"] = True, e
                print(f"route12_3d: disabled ({scene_id}: {e!r}), using 2D")
        fn2d(surface, t)
    return draw


def _fallback_seby(beat):
    def _fn(surface, t):
        from missions.m2 import draw_route12_seby_pickup
        draw_route12_seby_pickup(surface, {"scene": f"seby_pickup_{beat}", "lighting": (10, 10, 12)}, t)
    return _fn


def _register_all():
    from core.cutscene_registry import register_scene_renderer
    from cutscenes.route12 import (
        draw_krap_door_kickin, draw_route12_aftermath,
        draw_route12_broadcast, draw_route12_checkpoint,
    )
    register_scene_renderer(
        "route12_checkpoint",
        _wrap("route12_checkpoint", lambda s, t: _draw_checkpoint_3d(s, t, aftermath=False),
              draw_route12_checkpoint),
    )
    register_scene_renderer(
        "route12_aftermath",
        _wrap("route12_aftermath", lambda s, t: _draw_checkpoint_3d(s, t, aftermath=True),
              draw_route12_aftermath),
    )
    register_scene_renderer(
        "route12_broadcast",
        _wrap("route12_broadcast", _draw_broadcast_3d, draw_route12_broadcast),
    )
    register_scene_renderer(
        "krap_door_kickin",
        _wrap("krap_door_kickin", _draw_door_kickin_3d, draw_krap_door_kickin),
    )
    for beat in ("body", "reach", "raise"):
        sid = f"seby_pickup_{beat}"
        register_scene_renderer(
            sid,
            _wrap(sid, lambda s, t, _b=beat: _draw_seby_pickup_3d(s, t, _b),
                  _fallback_seby(beat)),
        )


_register_all()
