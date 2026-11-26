"""m4aftermath3d.py - 3D engine3d takes for Mission 4's intro and ending cutscenes.

Serves all five M4 cutscene scene IDs with automatic 2D fallback under
ACARISTAN_CUTSCENE3D=0:

    m4_street_curfew    abandoned curfew boulevard, barricades, glowing screens
    m4_city_curfew      elevated capital skyline under fire & sweeping searchlights
    m4_arrest_screen    State Assembly televised arrest on a public broadcast CRT
    m4_maru_silhouette  dark transmitter hall racks, backlit 3D Maru & wall screen
    m4_roof_dawn        broadcast station roof at sunrise, Biribel & Vasile watching

Pure functions of t; zero mission imports.
"""
import math
import os
import random

import pygame

from core.config import (
    HEIGHT, SCENE_H, SCENE_TOP, WIDTH,
    font_terminal, font_terminal_small,
)
from cutscenes.cast3d import humanoid3d

__all__ = ["SCENES", "m4aftermath3d_enabled", "draw_scene"]

SCENES = (
    "m4_street_curfew",
    "m4_city_curfew",
    "m4_arrest_screen",
    "m4_maru_silhouette",
    "m4_roof_dawn",
)

RES = 0.64
RW, RH = int(WIDTH * RES), int(SCENE_H * RES)

_S = {"sets": {}, "rigs": {}, "failed": False, "err": None}


def m4aftermath3d_enabled():
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
        _S["rigs"][key] = humanoid3d(who, **kw)
    return _S["rigs"][key]


def _set(key, fog, fs, fe, builder):
    if key not in _S["sets"]:
        from engine3d import Renderer
        r = Renderer(RW, RH, fog=fog, fog_start=fs, fog_end=fe)
        r.light_cap = 8
        builder(r)
        _S["sets"][key] = (r, pygame.Surface((RW, RH)))
    return _S["sets"][key]


def _tag(surface, text, col=(142, 206, 224)):
    s = font_terminal_small.render(text, True, col)
    bg = pygame.Surface((s.get_width() + 24, s.get_height() + 8), pygame.SRCALPHA)
    bg.fill((8, 10, 14, 175))
    surface.blit(bg, (WIDTH // 2 - bg.get_width() // 2, SCENE_TOP + 12))
    surface.blit(s, (WIDTH // 2 - s.get_width() // 2, SCENE_TOP + 16))


# ── 1. Abandoned Curfew Boulevard (m4_street_curfew) ──────────────────────

def _build_street_curfew(r):
    from engine3d.core import box, quad_xz
    from cutscenes.ps2mat import mesh as textured

    def bake(m):
        r.bake(textured(m))

    # Wet asphalt avenue + sidewalks
    bake(quad_xz(-18, -6, 18, 66, 0.0, (18, 20, 26), seg=2.5))
    for side in (-1, 1):
        bake(box(5.0, 0.16, 72.0, (32, 35, 42), center=(side * 11.0, 0.08, 30.0), seg=3.0))
        # Flanking brutalist city blocks
        rng = random.Random(401 if side < 0 else 402)
        for z in (6.0, 18.0, 30.0, 44.0, 58.0):
            bh = rng.uniform(11.0, 19.0)
            bake(box(8.0, bh, 10.5, (20, 23, 32), center=(side * 16.5, bh * 0.5, z), seg=2.5))
            for wy in range(3, int(bh) - 1, 3):
                for wz in (-3.0, 0.0, 3.0):
                    if rng.random() < 0.36:
                        bake(box(0.08, 1.1, 0.85, (148, 134, 96),
                                 center=(side * 12.45, wy, z + wz), emissive=True))
    # Abandoned checkpoint barricades & tilted barrier arm across boulevard at z = 14
    for bx in (-4.4, -1.6, 1.8, 4.6):
        bake(box(2.1, 0.92, 0.62, (62, 66, 70), center=(bx, 0.46, 14.0)))
        bake(box(2.14, 0.16, 0.64, (192, 152, 46), center=(bx, 0.72, 14.0)))
        # Amber barricade blinker housing
        bake(box(0.18, 0.22, 0.18, (242, 184, 58), center=(bx, 1.04, 14.0), emissive=True))
    # Empty checkpoint guard booth on east curb
    bake(box(2.0, 2.8, 2.2, (46, 52, 58), center=(7.2, 1.4, 15.2)))
    bake(box(1.5, 0.9, 0.06, (88, 118, 128), center=(7.2, 1.85, 14.06), emissive=True))
    # Giant glowing broadcast screens on left/right facades STILL running the address/Vostral
    bake(box(0.24, 3.8, 6.2, (16, 20, 26), center=(-12.3, 5.2, 19.0)))
    bake(box(0.10, 3.3, 5.6, (28, 72, 86), center=(-12.14, 5.2, 19.0), emissive=True))
    bake(box(0.12, 2.3, 3.4, (218, 214, 192), center=(-12.08, 5.3, 19.0), emissive=True))
    bake(box(0.24, 3.2, 5.2, (16, 20, 26), center=(12.3, 6.4, 29.0)))
    bake(box(0.10, 2.8, 4.6, (94, 28, 28), center=(12.14, 6.4, 29.0), emissive=True))
    # Distant silhouette skyline wall
    bake(box(48.0, 22.0, 4.0, (12, 14, 22), center=(0.0, 11.0, 65.0), seg=4.0))


def _draw_street_curfew_3d(surface, t):
    from engine3d.core import Light
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx
    from cutscenes import fire3d

    r, buf = _set("m4_street", (11, 13, 21), 12.0, 62.0, _build_street_curfew)
    sec = t * 0.001
    u = _smooth(min(1.0, t / 6000.0))
    blink = 1.0 if (int(t) // 480) % 2 == 0 else 0.25

    r.light = Light(direction=(-0.25, 0.80, -0.55), ambient=0.32, diffuse=0.40,
                    sky=0.08, tint=(0.76, 0.84, 1.06))
    r.light_albedo, r.light_gain = True, 2.5
    r.set_lights([
        {"pos": (-9.5, 5.0, 19.0), "color": (122, 194, 214), "intensity": 1.6, "range": 18.0},
        {"pos": (9.5, 6.0, 28.0), "color": (218, 72, 58), "intensity": 1.2, "range": 16.0},
        {"pos": (0.0, 1.5, 13.5), "color": (248, 178, 56), "intensity": 1.15 * blink, "range": 11.0},
        {"pos": (-5.5, 1.4, 22.0), "color": (255, 132, 48), "intensity": 1.5, "range": 14.0},
    ], cap=8)

    eye = (-1.6 + 2.4 * u, 1.65 + 0.30 * u, 1.0 + 4.8 * u)
    tgt = (-0.6, 2.6, 22.0)
    _m5.set_cam(r, t, eye, tgt, 50, hh=0.014, seed=41)
    buf.fill((10, 12, 20))
    _m5.night_sky(r, buf, t, (6, 8, 16), (22, 18, 28), stars=16, clouds=2,
                  sodium=(42, 24, 20), mist=(14, 16, 24))
    r.begin()
    r.add_static()

    lay = _fx.FX_LAYER
    # Burning barricade drum fire & drifting ash embers
    fire3d.emit_fire(r, (-5.4, 0.4, 22.0), t, seed=401, size=1.15, smoky=True, layer=lay)
    fire3d.emit_fire(r, (4.8, 0.3, 34.0), t, seed=409, size=1.45, smoky=True, layer=lay)
    for bx in (-4.4, -1.6, 1.8, 4.6):
        r.add_sprite((bx, 1.06, 14.0),
                     _fx.glow((255, 186, 62), 0.85, t, intensity=0.85 * blink), layer=lay)
    r.add_sprite((-12.0, 5.2, 19.0), _fx.glow((120, 210, 220), 4.2, t, intensity=0.45), layer=lay)
    r.add_sprite((-5.2, 0.04, 17.0), _m5.wet_reflection((118, 194, 210), t, seed=3,
                                                        length_m=6.0, width_m=1.4, intensity=0.42), layer=2)
    for i in range(28):
        age = (sec * 0.32 + i / 28.0) % 1.0
        ex = -9.0 + ((i * 2.17) % 18.0) + math.sin(sec * 1.8 + i) * 0.6
        ey = 0.3 + age * 7.5
        ez = 8.0 + ((i * 3.11) % 24.0)
        r.add_line3d((ex, ey, ez), (ex + 0.07, ey + 0.12, ez), (255, 164, 72), 1, layer=lay)

    r.flush(buf)
    _fx.grade_cine(buf)
    _fx.present_crisp(buf, surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_H)))
    _tag(surface, "THE CAPITAL // 48H AFTER THE VOSTRAL", (152, 206, 226))


# ── 2. Capital Curfew Skyline on Fire (m4_city_curfew) ────────────────────

def _build_city_skyline(r):
    from engine3d.core import box, quad_xz
    from cutscenes.ps2mat import mesh as textured

    def bake(m):
        r.bake(textured(m))

    bake(quad_xz(-70, -10, 70, 95, 0.0, (10, 12, 18), seg=8.0))
    rng = random.Random(2048)
    for row, zbase in enumerate((22.0, 38.0, 56.0, 74.0)):
        for ix in range(-7, 8):
            bx = ix * 8.2 + (row % 2) * 3.5 + rng.uniform(-1.0, 1.0)
            bw = rng.uniform(5.2, 7.6)
            bd = rng.uniform(5.2, 7.6)
            bh = rng.uniform(10.0, 26.0) + row * 3.2
            col = (18 + row * 2, 20 + row * 2, 29 + row * 3)
            bake(box(bw, bh, bd, col, center=(bx, bh * 0.5, zbase), seg=3.0))
            # Lit apartment windows on front faces
            if row < 3:
                for wy in range(3, int(bh) - 2, 3):
                    for wx_i in (-1, 0, 1):
                        if rng.random() < 0.32:
                            c = (214, 178, 108) if rng.random() < 0.6 else (120, 152, 194)
                            bake(box(0.85, 1.15, 0.08, c,
                                     center=(bx + wx_i * (bw * 0.28), wy, zbase - bd * 0.5 - 0.04),
                                     emissive=True))


def _draw_city_curfew_3d(surface, t):
    from engine3d.core import Light
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx
    from cutscenes import fire3d

    r, buf = _set("m4_skyline", (16, 14, 24), 24.0, 105.0, _build_city_skyline)
    sec = t * 0.001
    u = _smooth(min(1.0, t / 7000.0))
    flick = 0.85 + 0.15 * math.sin(sec * 8.0)

    r.light = Light(direction=(0.2, 0.72, -0.65), ambient=0.34, diffuse=0.40,
                    sky=0.10, tint=(0.94, 0.82, 0.92))
    r.light_albedo, r.light_gain = True, 2.3
    r.set_lights([
        {"pos": (-14.0, 20.0, 32.0), "color": (255, 128, 48), "intensity": 2.6 * flick, "range": 34.0},
        {"pos": (12.0, 22.0, 44.0), "color": (255, 110, 42), "intensity": 2.4 * flick, "range": 36.0},
        {"pos": (0.0, 18.0, 26.0), "color": (164, 198, 244), "intensity": 1.3, "range": 30.0},
    ], cap=8)

    eye = (-9.0 + 18.0 * u, 26.5 - 1.5 * u, -14.0 + 5.0 * u)
    tgt = (0.0, 14.5, 42.0)
    _m5.set_cam(r, t, eye, tgt, 54, hh=0.012, seed=42)
    buf.fill((14, 12, 22))
    _m5.night_sky(r, buf, t, (8, 10, 20), (38, 24, 34), stars=18, clouds=3,
                  sodium=(64, 34, 24), mist=(24, 18, 26))
    r.begin()
    r.add_static()

    lay = _fx.FX_LAYER
    # Rooftop fires & smoke columns
    for idx, (fx0, fy0, fz0, sz) in enumerate((
        (-14.0, 16.5, 34.0, 2.8),
        (11.5, 19.0, 42.0, 3.2),
        (-2.5, 22.0, 56.0, 2.6),
    )):
        fire3d.emit_fire(r, (fx0, fy0, fz0), t, seed=501 + idx * 19, size=sz, smoky=True, layer=lay)
        r.add_sprite((fx0, fy0 + 2.0, fz0),
                     _fx.glow((255, 124, 48), sz * 3.4, t, seed=idx, intensity=0.65), layer=lay)

    r.flush(buf)
    _fx.grade_cine(buf)
    _fx.present_crisp(buf, surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_H)))
    # Soft volumetric searchlight cones sweeping across the curfew sky
    beams = pygame.Surface((WIDTH, SCENE_H), pygame.SRCALPHA)
    for bx, ph in ((210, 0.0), (520, 1.9), (810, 3.7)):
        sway = math.sin(sec * 0.72 + ph) * 210.0
        top_x = int(bx + sway)
        pygame.draw.polygon(beams, (168, 198, 236, 22),
                            [(bx - 16, SCENE_H), (bx + 16, SCENE_H), (top_x + 76, 0), (top_x - 76, 0)])
        pygame.draw.polygon(beams, (196, 220, 248, 16),
                            [(bx - 7, SCENE_H), (bx + 7, SCENE_H), (top_x + 34, 0), (top_x - 34, 0)])
    surface.blit(beams, (0, SCENE_TOP))
    _tag(surface, "THE CAPITAL // 3RD CURFEW NIGHT", (228, 162, 114))


# ── 3. Televised Arrest of Balaceanu (m4_arrest_screen) ───────────────────

def _build_assembly_hall(r):
    from engine3d.core import box, quad_xz
    from cutscenes.ps2mat import mesh as textured

    def bake(m):
        r.bake(textured(m))

    bake(quad_xz(-10, -5, 10, 11, 0.0, (28, 30, 38), seg=1.5))
    bake(box(9.4, 0.30, 4.2, (38, 40, 50), center=(0.0, 0.15, 3.6), seg=1.5))
    bake(box(20.0, 6.8, 0.4, (24, 28, 38), center=(0.0, 3.4, 7.6), seg=2.0))
    # State blue/crimson pillars & Retardovici gold triple-crest backdrop
    for cx in (-4.8, -2.4, 2.4, 4.8):
        col = (34, 62, 116) if abs(cx) > 3.0 else (128, 34, 36)
        bake(box(0.56, 6.0, 0.46, col, center=(cx, 3.0, 7.1)))
        bake(box(0.66, 0.18, 0.56, (216, 184, 96), center=(cx, 5.95, 7.1)))
    # Gold triple-crest emblem above podium
    for ox in (-0.62, 0.0, 0.62):
        bake(box(0.42, 0.84, 0.12, (226, 194, 104), center=(-1.35 + ox, 3.65, 7.30)))
    # State podium on left (Retardovici speaks)
    bake(box(1.9, 1.24, 0.86, (58, 42, 32), center=(-1.35, 0.92, 2.85)))
    bake(box(2.04, 0.10, 0.98, (82, 60, 44), center=(-1.35, 1.56, 2.85)))
    bake(box(0.90, 0.32, 0.06, (218, 186, 98), center=(-1.35, 1.18, 2.39)))


def _draw_arrest_screen_3d(surface, t):
    from engine3d.core import Light
    from engine3d import POSES, pose_run
    from engine3d.rig import mouth_flap
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx
    from cutscenes import m6world3d as W

    # Match m4aftermath's exact 0..14800ms clamp contract (checked by smoke_test).
    t = max(0.0, min(14800.0, float(t)))
    r, buf = _set("m4_assembly", (16, 18, 26), 10.0, 38.0, _build_assembly_hall)
    sec = t * 0.001
    u = _smooth(min(1.0, t / 14000.0))

    r.light = Light(direction=(0.0, 0.85, -0.55), ambient=0.45, diffuse=0.58,
                    sky=0.08, tint=(1.0, 0.97, 0.93))
    r.light_albedo, r.light_gain = True, 2.2
    r.set_lights([
        {"pos": (-1.4, 4.6, 1.0), "color": (255, 236, 196), "intensity": 1.7, "range": 12.0},
        {"pos": (1.8, 4.0, 1.5), "color": (200, 218, 248), "intensity": 1.3, "range": 11.0},
        {"pos": (0.0, 3.6, 5.8), "color": (228, 194, 112), "intensity": 1.0, "range": 10.0},
    ], cap=8)

    # Multi-angle broadcast cut: wide hall (0..2600ms) -> push onto escort & podium
    if t < 2600:
        eye = (0.25 - 0.55 * u, 1.88, -2.05 + 0.45 * u)
        tgt = (0.15, 1.55, 3.3)
        fov = 46
    else:
        u2 = _smooth((t - 2600.0) / 3400.0)
        eye = (1.35 - 0.45 * u2, 1.72, -0.95 + 0.50 * u2)
        tgt = (0.35 + 0.55 * u2, 1.52, 3.4)
        fov = 40
    _m5.set_cam(r, t, eye, tgt, fov, hh=0.008, seed=77)
    buf.fill((16, 18, 26))
    r.begin()
    r.add_static()

    # Retardovici smiling at podium on left
    pres = _rig("president")
    p_pose = W.life_pose(dict(POSES["stand"], rsh_p=24, rel=48, head_y=-8), t, amp=0.7, seed=1)
    pres.set_expression("smile", mouth_flap(t, 13))
    r.add_humanoid(pres, p_pose, (-1.35, 0.30, 3.45), 184.0, rifle_on=False)

    # Balaceanu escorted slowly right by two Guards
    walk_x = 1.25 + 1.15 * u
    bal = _rig("balaceanu")
    b_pose = W.life_pose(dict(POSES["stand"], spine=14, head_p=18, rsh_p=-16, lsh_p=-16,
                              rel=38, lel=38), t, amp=0.6, seed=2)
    bal.set_expression("sad", 0.0)
    r.add_humanoid(bal, b_pose, (walk_x, 0.30, 3.65), 150.0, rifle_on=False)

    guard = _rig("ipa", rifle="rifle")
    g_pose = pose_run(sec * 2.2, lean=4) if u < 0.95 else dict(POSES["ready"])
    r.add_humanoid(guard, g_pose, (walk_x - 0.85, 0.30, 3.55), 130.0, rifle_on=True)
    r.add_humanoid(guard, g_pose, (walk_x + 0.85, 0.30, 3.70), 140.0, rifle_on=True)

    r.flush(buf)
    _fx.grade_cine(buf)

    # Public CRT broadcast frame
    surface.fill((7, 8, 12))
    frame = pygame.Rect(68, SCENE_TOP + 16, WIDTH - 136, SCENE_H - 32)
    pygame.draw.rect(surface, (18, 20, 26), frame.inflate(22, 18), border_radius=12)
    pygame.draw.rect(surface, (56, 62, 74), frame.inflate(22, 18), 2, border_radius=12)
    _fx.present_crisp(buf, surface.subsurface(frame))

    hdr_bg = pygame.Surface((frame.w, 30), pygame.SRCALPHA)
    hdr_bg.fill((22, 34, 58, 215))
    surface.blit(hdr_bg, (frame.x, frame.y))
    surface.blit(font_terminal.render("ACARISTAN STATE BROADCAST // SPECIAL SESSION",
                                      True, (236, 224, 188)), (frame.x + 14, frame.y + 5))
    if (int(t) // 420) % 2 == 0:
        pygame.draw.circle(surface, (242, 68, 58), (frame.right - 64, frame.y + 15), 5)
    surface.blit(font_terminal_small.render("LIVE", True, (248, 228, 216)), (frame.right - 50, frame.y + 7))

    bot_bg = pygame.Surface((frame.w, 38), pygame.SRCALPHA)
    bot_bg.fill((18, 22, 30, 226))
    pygame.draw.rect(bot_bg, (226, 194, 106), (0, 0, frame.w, 4))
    surface.blit(bot_bg, (frame.x, frame.bottom - 38))
    surface.blit(font_terminal_small.render(
        "PM BALACEANU RELIEVED OF OFFICE  //  PRESIDENT RETARDOVICI ASSUMES EMERGENCY POWERS",
        True, (242, 232, 204),
    ), (frame.x + 14, frame.bottom - 26))
    for sy in range(frame.y, frame.bottom, 4):
        pygame.draw.line(surface, (0, 0, 0), (frame.x, sy), (frame.right, sy), 1)
    pygame.draw.rect(surface, (46, 52, 64), frame, 3, border_radius=4)


# ── 4. Transmitter Hall — Maru Silhouette (m4_maru_silhouette) ────────────

def _build_transmitter_hall(r):
    from engine3d.core import box, quad_xz
    from cutscenes.ps2mat import mesh as textured

    def bake(m):
        r.bake(textured(m))

    bake(quad_xz(-5.5, -4.0, 5.5, 11.0, 0.0, (16, 20, 22), seg=1.2))
    bake(box(11.0, 0.16, 15.0, (16, 20, 24), center=(0.0, 4.2, 3.5), seg=1.5))
    for side in (-1, 1):
        bake(box(0.24, 4.2, 15.0, (22, 28, 32), center=(side * 5.4, 2.1, 3.5), seg=1.5))
    bake(box(11.0, 4.2, 0.24, (18, 24, 28), center=(0.0, 2.1, 10.9), seg=1.5))

    # Towering steel transmitter & server racks lining both sides + back
    for side in (-1, 1):
        for z in (1.4, 3.6, 5.8, 8.0):
            rx = side * 3.1
            bake(box(1.3, 3.4, 1.3, (22, 28, 32), center=(rx, 1.7, z)))
            for ly in (0.7, 1.3, 1.9, 2.5, 3.0):
                col = (96, 214, 146) if int(ly * 10 + z) % 3 != 0 else (232, 168, 72)
                bake(box(0.06, 0.06, 0.08, col,
                         center=(rx - side * 0.67, ly, z - 0.30), emissive=True))
    # Back center broadcast monitor showing Retardovici's broadcast glow
    bake(box(2.8, 1.8, 0.30, (16, 20, 24), center=(0.0, 2.45, 9.6)))
    bake(box(2.5, 1.5, 0.05, (64, 96, 132), center=(0.0, 2.45, 9.42), emissive=True))
    bake(box(0.70, 0.72, 0.06, (176, 142, 114), center=(0.0, 2.45, 9.38), emissive=True))
    bake(box(2.3, 0.16, 0.06, (222, 188, 98), center=(0.0, 1.85, 9.38), emissive=True))


def _draw_maru_silhouette_3d(surface, t):
    from engine3d.core import Light
    from engine3d import POSES
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx
    from cutscenes import m6world3d as W

    r, buf = _set("m4_tx_hall", (8, 14, 15), 5.0, 22.0, _build_transmitter_hall)
    u = _smooth(min(1.0, t / 5500.0))

    r.light = Light(direction=(0.0, 0.65, 0.75), ambient=0.22, diffuse=0.38,
                    sky=0.05, tint=(0.76, 0.98, 0.90))
    r.light_albedo, r.light_gain = True, 2.5
    r.set_lights([
        {"pos": (0.0, 2.4, 8.2), "color": (132, 184, 232), "intensity": 1.8, "range": 11.0},
        {"pos": (-2.4, 2.0, 4.6), "color": (92, 212, 144), "intensity": 1.05, "range": 7.5},
        {"pos": (2.4, 2.0, 4.6), "color": (92, 212, 144), "intensity": 1.05, "range": 7.5},
    ], cap=8)

    eye = (0.0, 1.48 + 0.08 * u, 0.4 + 1.2 * u)
    tgt = (0.0, 1.52, 6.2)
    _m5.set_cam(r, t, eye, tgt, 46, hh=0.010, seed=83)
    buf.fill((7, 12, 14))
    r.begin()
    r.add_static()

    # Backlit Maru standing in the transmitter aisle, facing the distant screen / turning slightly
    maru = _rig("maru")
    mp = W.life_pose(dict(POSES["stand"], head_y=-18 + 26 * u, head_p=-4), t, amp=0.5, seed=3)
    maru.set_expression("neutral", 0.0)
    r.add_humanoid(maru, mp, (0.0, 0.0, 4.9), 24.0 - 18.0 * u, rifle_on=False)

    lay = _fx.FX_LAYER
    r.add_sprite((0.0, 2.45, 9.2), _fx.glow((128, 188, 236), 3.4, t, intensity=0.65), layer=lay)
    r.add_sprite((0.0, 0.04, 6.2), _m5.wet_reflection((104, 214, 152), t, seed=4,
                                                      length_m=4.8, width_m=1.2, intensity=0.35), layer=2)

    r.flush(buf)
    _fx.grade_cine(buf)
    _fx.present_crisp(buf, surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_H)))
    _tag(surface, "TRANSMITTER HALL // THE MEET", (118, 214, 152))


# ── 5. Studio Roof at First Dawn (m4_roof_dawn) ───────────────────────────

def _build_roof_dawn(r):
    from engine3d.core import box, quad_xz
    from cutscenes.ps2mat import mesh as textured

    def bake(m):
        r.bake(textured(m))

    # Gravel/tar rooftop deck + concrete parapet wall at z = 6.2
    bake(quad_xz(-9.0, -4.0, 9.0, 6.4, 0.0, (28, 26, 32), seg=1.5))
    bake(box(18.0, 1.05, 0.42, (44, 40, 48), center=(0.0, 0.525, 6.2), seg=1.5))
    bake(box(18.2, 0.12, 0.54, (64, 58, 66), center=(0.0, 1.08, 6.2), seg=1.5))
    # Rooftop HVAC vents & radio mast truss on right edge
    bake(box(1.8, 0.95, 1.4, (38, 38, 44), center=(-5.4, 0.48, 3.8)))
    bake(box(0.24, 9.5, 0.24, (46, 46, 54), center=(6.2, 4.75, 5.2)))
    bake(box(0.22, 0.22, 0.22, (238, 66, 52), center=(6.2, 9.5, 5.2), emissive=True))
    # Distant Acaristan skyline silhouettes across the dawn valley
    rng = random.Random(707)
    for ix in range(-9, 10):
        bx = ix * 6.4
        bh = rng.uniform(10.0, 26.0)
        bake(box(4.8, bh, 5.0, (24, 22, 32), center=(bx, bh * 0.5 - 12.0, 52.0 + (ix % 3) * 6.0), seg=3.0))


def _draw_roof_dawn_3d(surface, t):
    from engine3d.core import Light
    from engine3d import POSES
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx
    from cutscenes import m6world3d as W

    r, buf = _set("m4_roof", (58, 42, 44), 18.0, 96.0, _build_roof_dawn)
    u = _smooth(min(1.0, t / 8000.0))

    r.light = Light(direction=(0.32, 0.28, 0.90), ambient=0.38, diffuse=0.56,
                    sky=0.14, tint=(1.12, 0.84, 0.68))
    r.light_albedo, r.light_gain = True, 2.2
    r.set_lights([
        {"pos": (8.0, 6.0, 26.0), "color": (255, 168, 102), "intensity": 2.4, "range": 42.0},
        {"pos": (0.0, 2.2, 7.2), "color": (236, 154, 98), "intensity": 1.1, "range": 12.0},
    ], cap=8)

    eye = (-0.8 + 1.4 * u, 1.66 + 0.12 * u, -0.45 + 0.85 * u)
    tgt = (0.15, 1.48, 6.2)
    _m5.set_cam(r, t, eye, tgt, 48, hh=0.010, seed=91)
    # Warm first-light dawn sky gradient
    buf.fill((48, 36, 46))
    _m5.night_sky(r, buf, t, (28, 28, 46), (176, 102, 74), stars=6, clouds=3,
                  sodium=(228, 148, 92), mist=(132, 84, 72))
    r.begin()
    r.add_static()

    # Biribel and Vasile standing side by side at the roof parapet watching the sunrise
    bir = _rig("biribel")
    vas = _rig("vasile")
    bp = W.life_pose(dict(POSES["stand"], head_y=8, head_p=-4), t, amp=0.5, seed=1)
    vp = W.life_pose(dict(POSES["stand"], head_y=-10, head_p=-4), t, amp=0.5, seed=2)
    bir.set_expression("neutral", 0.0)
    vas.set_expression("stern", 0.0)
    r.add_humanoid(bir, bp, (-0.75, 0.0, 4.95), 14.0, rifle_on=False)
    r.add_humanoid(vas, vp, (0.85, 0.0, 5.05), -12.0, rifle_on=False)

    # Low rising sun bloom breaking above the distant skyline
    lay = _fx.FX_LAYER
    r.add_sprite((14.0, 8.5, 62.0),
                 _fx.glow((255, 182, 114), 11.0, t, core=(255, 232, 186), intensity=0.95), layer=lay)
    if (int(t) // 700) % 2 == 0:
        r.add_sprite((6.2, 9.5, 5.2), _fx.glow((255, 72, 58), 0.9, t, intensity=0.9), layer=lay)

    r.flush(buf)
    _fx.grade_cine(buf)
    surface.fill((8, 8, 12))
    _fx.present_crisp(buf, surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_H)))
    _tag(surface, "SUNRISE // THE CURFEW LIFTS", (236, 166, 112))


_DISPATCH = {
    "m4_street_curfew": _draw_street_curfew_3d,
    "m4_city_curfew": _draw_city_curfew_3d,
    "m4_arrest_screen": _draw_arrest_screen_3d,
    "m4_maru_silhouette": _draw_maru_silhouette_3d,
    "m4_roof_dawn": _draw_roof_dawn_3d,
}


def draw_scene(scene_id, surface, t):
    if not m4aftermath3d_enabled():
        return False
    fn = _DISPATCH.get(scene_id)
    if fn is None:
        return False
    try:
        fn(surface, t)
        return True
    except Exception as e:
        _S["failed"], _S["err"] = True, e
        print(f"m4aftermath3d: disabled ({scene_id}: {e!r}), using 2D")
        return False
