"""m3ending3d.py - 3D engine3d takes for Mission 3's broadcast finale and 22:00 fail cut.

Serves six scene IDs with automatic 2D fallback (ACARISTAN_CUTSCENE3D=0):
    m3_end_studio         over Biribel & Volkov at booth console, red ON AIR wall
    m3_end_cut            monitor wall push: address tears to emerald Vostral record
    m3_end_nation         Acaristan 22:07 night street: every screen shows Vostral
    m3_end_booth_dark     darkened booth aftermath, red emergency beacons, OFF AIR
    m3_bcast_fail_studio  studio lost under spinning crimson lockdown strobe
    m3_bcast_fail_pa      6-screen wall push showing Balaceanu's completed address

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

__all__ = ["SCENES", "m3ending3d_enabled", "draw_scene"]

SCENES = (
    "m3_end_studio",
    "m3_end_cut",
    "m3_end_nation",
    "m3_end_booth_dark",
    "m3_bcast_fail_studio",
    "m3_bcast_fail_pa",
)

RES = 0.64
RW, RH = int(WIDTH * RES), int(SCENE_H * RES)

_PRISONER = dict(
    jacket=(88, 64, 46), pants=(88, 64, 46), vest=None,
    pouches=False, accent=None, armband=(88, 64, 46), belt=None,
    buckle=None, cuff=(56, 42, 32), lapel=None, shirt=None,
)

_S = {"sets": {}, "rigs": {}, "failed": False, "err": None}


def m3ending3d_enabled():
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


# ── Set 1: Broadcast Control Booth ────────────────────────────────────────

def _build_booth(r):
    from engine3d.core import box, quad_xz
    from cutscenes.ps2mat import mesh as textured

    def bake(m):
        r.bake(textured(m))

    # Floor, ceiling, side acoustic-baffle walls, back monitor wall
    bake(quad_xz(-4.2, -3.2, 4.2, 5.2, 0.0, (24, 24, 30), seg=1.0))
    bake(box(8.4, 0.16, 8.4, (22, 22, 28), center=(0.0, 3.6, 1.0), seg=1.2))
    for side in (-1, 1):
        bake(box(0.22, 3.6, 8.4, (32, 30, 38), center=(side * 4.1, 1.8, 1.0), seg=1.0))
        for z in (-1.2, 0.4, 2.0, 3.6):
            bake(box(0.10, 2.2, 1.1, (24, 22, 28), center=(side * 3.94, 1.85, z)))
        # Side wall red emergency beacon housing
        bake(box(0.14, 0.24, 0.28, (44, 24, 24), center=(side * 3.92, 2.55, 1.8)))
    bake(box(8.4, 3.6, 0.24, (28, 26, 34), center=(0.0, 1.8, 4.9), seg=1.0))

    # Studio mixing console desk at z = 2.1
    bake(box(4.6, 0.92, 1.05, (38, 36, 46), center=(0.0, 0.46, 2.15), seg=1.0))
    bake(box(4.75, 0.08, 1.16, (56, 54, 66), center=(0.0, 0.94, 2.15)))
    # Sloped mixer button bank + faders
    bake(box(2.0, 0.12, 0.48, (26, 26, 34), center=(-0.75, 1.02, 2.02)))
    for i in range(7):
        col = (218, 86, 62) if i % 3 == 0 else (98, 212, 148)
        bake(box(0.06, 0.04, 0.10, col, center=(-1.55 + i * 0.26, 1.09, 2.02), emissive=True))
    # Retro uplink terminal on right side of console
    bake(box(0.76, 0.56, 0.52, (46, 48, 52), center=(1.05, 1.26, 2.22)))
    bake(box(0.62, 0.40, 0.04, (26, 76, 52), center=(1.05, 1.28, 1.94), emissive=True))
    bake(box(0.68, 0.05, 0.24, (66, 68, 72), center=(1.05, 1.00, 1.76)))

    # 3 monitor housings along back wall (z = 4.65); screens themselves are dynamic
    for mx in (-2.35, 0.0, 2.35):
        bake(box(2.05, 1.38, 0.34, (18, 18, 24), center=(mx, 2.18, 4.66)))
    # ON AIR lightbox above center monitor
    bake(box(1.18, 0.34, 0.22, (24, 14, 16), center=(0.0, 3.16, 4.68)))


def _monitor_screens_mesh(mode, t):
    """Build dynamic monitor screen faces: 'red' (Balaceanu), 'record' (Vostral),
    'dark' (OFF AIR), or 'six' (6-panel fail wall)."""
    from engine3d.core import Mesh, box
    m = Mesh()
    if mode == "six":
        for row, my in enumerate((1.62, 2.66)):
            for mx in (-2.35, 0.0, 2.35):
                m.add(box(1.92, 0.88, 0.08, (20, 18, 24), center=(mx, my, 4.50)))
                m.add(box(1.76, 0.74, 0.03, (96, 22, 24), center=(mx, my, 4.44), emissive=True))
                # Balaceanu podium silhouette inside each screen
                m.add(box(0.32, 0.30, 0.035, (148, 66, 58), center=(mx, my - 0.10, 4.42), emissive=True))
                m.add(box(0.14, 0.14, 0.035, (194, 114, 96), center=(mx, my + 0.14, 4.42), emissive=True))
                m.add(box(1.56, 0.07, 0.035, (218, 72, 62), center=(mx, my - 0.28, 4.42), emissive=True))
        m.add(box(1.04, 0.22, 0.04, (238, 56, 48), center=(0.0, 3.16, 4.55), emissive=True))
        return m

    for mx in (-2.35, 0.0, 2.35):
        if mode == "dark":
            m.add(box(1.86, 1.18, 0.03, (16, 17, 22), center=(mx, 2.18, 4.47)))
        elif mode == "record":
            m.add(box(1.86, 1.18, 0.03, (18, 64, 42), center=(mx, 2.18, 4.47), emissive=True))
            # Illuminated Vostral document sheet centered on each monitor
            m.add(box(1.12, 0.94, 0.04, (222, 218, 192), center=(mx, 2.18, 4.45), emissive=True))
            for k in range(5):
                m.add(box(0.86, 0.04, 0.045, (58, 76, 68),
                          center=(mx, 2.48 - k * 0.15, 4.43), emissive=True))
            # Red authenticity stamp on the record
            m.add(box(0.24, 0.16, 0.045, (188, 48, 42), center=(mx + 0.30, 1.84, 4.43), emissive=True))
        else:  # red address
            m.add(box(1.86, 1.18, 0.03, (88, 20, 22), center=(mx, 2.18, 4.47), emissive=True))
            m.add(box(0.46, 0.44, 0.04, (148, 68, 60), center=(mx, 2.08, 4.45), emissive=True))
            m.add(box(0.20, 0.20, 0.04, (196, 118, 98), center=(mx, 2.42, 4.45), emissive=True))
            m.add(box(1.64, 0.10, 0.04, (224, 72, 60), center=(mx, 1.72, 4.45), emissive=True))

    # ON AIR lightbox state
    if mode == "dark":
        m.add(box(1.04, 0.22, 0.04, (44, 18, 18), center=(0.0, 3.16, 4.55)))
    elif mode == "record":
        m.add(box(1.04, 0.22, 0.04, (96, 226, 152), center=(0.0, 3.16, 4.55), emissive=True))
    else:
        m.add(box(1.04, 0.22, 0.04, (242, 58, 48), center=(0.0, 3.16, 4.55), emissive=True))
    return m


def _tag(surface, text, col=(142, 208, 226)):
    s = font_terminal_small.render(text, True, col)
    bg = pygame.Surface((s.get_width() + 24, s.get_height() + 8), pygame.SRCALPHA)
    bg.fill((8, 10, 14, 175))
    surface.blit(bg, (WIDTH // 2 - bg.get_width() // 2, SCENE_TOP + 12))
    surface.blit(s, (WIDTH // 2 - s.get_width() // 2, SCENE_TOP + 16))


def _draw_booth_shot(surface, t, kind):
    from engine3d.core import Light
    from engine3d import POSES
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx
    from cutscenes import m6world3d as W

    r, buf = _set("m3_booth", (10, 10, 16), 5.0, 20.0, _build_booth)
    sec = t * 0.001
    u = _smooth(min(1.0, t / 3600.0))

    if kind == "end_studio":
        mode = "red"
        eye = (-1.15 + 0.35 * u, 1.66 - 0.06 * u, -0.55 + 0.35 * u)
        tgt = (0.20, 1.85, 4.4)
        fov = 50
        lights = [
            {"pos": (0.0, 2.3, 3.6), "color": (232, 68, 58), "intensity": 1.6, "range": 9.0},
            {"pos": (1.05, 1.35, 1.7), "color": (92, 222, 148), "intensity": 0.85, "range": 4.0},
            {"pos": (-2.4, 2.4, 3.4), "color": (210, 58, 52), "intensity": 0.9, "range": 6.5},
        ]
        tag = "BROADCAST WING // FEED LIVE"
    elif kind == "end_cut":
        flipped = t >= 900.0
        mode = "record" if flipped else "red"
        eye = (0.0, 2.15, 0.45 + 1.05 * u)
        tgt = (0.0, 2.18, 4.6)
        fov = 44
        col = (96, 236, 158) if flipped else (238, 62, 54)
        lights = [
            {"pos": (0.0, 2.2, 3.4), "color": col, "intensity": 2.0, "range": 9.0},
            {"pos": (-2.2, 2.2, 3.4), "color": col, "intensity": 1.1, "range": 7.0},
            {"pos": (2.2, 2.2, 3.4), "color": col, "intensity": 1.1, "range": 7.0},
        ]
        tag = "CARRIER LOST // VOSTRAL ON AIR" if flipped else "STATE ADDRESS // 22:00"
    elif kind == "end_dark":
        mode = "dark"
        pulse = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(sec * 3.8))
        eye = (-0.85 + 0.25 * u, 1.56, -0.75 + 0.20 * u)
        tgt = (0.15, 1.62, 3.8)
        fov = 50
        lights = [
            {"pos": (-3.6, 2.55, 1.8), "color": (236, 56, 46), "intensity": 1.45 * pulse, "range": 8.0},
            {"pos": (3.6, 2.55, 1.8), "color": (236, 56, 46), "intensity": 1.45 * (1.2 - pulse * 0.5), "range": 8.0},
        ]
        tag = "BROADCAST WING // 22:07 // OFF AIR"
    elif kind == "fail_studio":
        mode = "red"
        strobe = 0.5 + 0.5 * math.sin(sec * 9.0)
        eye = (1.10 - 0.35 * u, 1.72, -0.65 + 0.30 * u)
        tgt = (-0.15, 1.78, 4.2)
        fov = 52
        lights = [
            {"pos": (0.0, 2.8, 2.8), "color": (244, 46, 38), "intensity": 1.8 + 1.1 * strobe, "range": 10.0},
            {"pos": (-3.5, 2.5, 1.8), "color": (244, 46, 38), "intensity": 1.5 * strobe, "range": 7.5},
        ]
        tag = "STATE STUDIO // FEED LOST"
    else:  # fail_pa
        mode = "six"
        eye = (0.0, 2.12, 0.30 + 0.90 * u)
        tgt = (0.0, 2.15, 4.5)
        fov = 46
        lights = [
            {"pos": (0.0, 2.2, 3.2), "color": (244, 52, 46), "intensity": 2.1, "range": 9.0},
            {"pos": (-2.4, 2.2, 3.2), "color": (232, 48, 42), "intensity": 1.2, "range": 7.0},
            {"pos": (2.4, 2.2, 3.2), "color": (232, 48, 42), "intensity": 1.2, "range": 7.0},
        ]
        tag = "STATE ADDRESS // 22:00 COMPLETE"

    r.light = Light(direction=(0.0, 0.8, -0.5), ambient=0.28 if kind != "end_dark" else 0.16,
                    diffuse=0.45, sky=0.05, tint=(0.94, 0.92, 0.98))
    r.light_albedo, r.light_gain = True, 2.4
    r.set_lights(lights, cap=8)
    _m5.set_cam(r, t, eye, tgt, fov, hh=0.012, seed=81)
    buf.fill((9, 9, 14))
    r.begin()
    r.add_static()
    _add(r, _monitor_screens_mesh(mode, t))

    if kind in ("end_studio", "end_dark", "fail_studio"):
        bir = _rig("biribel")
        vol = _rig("volkov")
        bp = W.life_pose(dict(POSES["stand"], rsh_p=36 if kind == "end_studio" else 10,
                              rel=56 if kind == "end_studio" else 22, head_p=-10), t, amp=0.6, seed=1)
        r.add_humanoid(bir, bp, (0.52 if kind != "fail_studio" else -0.35, 0.0, 1.38),
                       14.0 if kind != "fail_studio" else -10.0, rifle_on=False)
        if kind in ("end_studio", "end_dark"):
            vp = W.life_pose(dict(POSES["stand"], head_y=-14 if kind == "end_dark" else 10, head_p=-8),
                             t, amp=0.6, seed=2)
            r.add_humanoid(vol, vp, (-1.15 if kind == "end_studio" else 1.55, 0.0, 1.32),
                           16.0 if kind == "end_studio" else -35.0, rifle_on=False)

    # Glow sprites on screens & emergency beacons
    lay = _fx.FX_LAYER
    if mode in ("red", "record", "six"):
        gcol = (104, 236, 162) if mode == "record" else (242, 62, 54)
        for mx in (-2.35, 0.0, 2.35):
            r.add_sprite((mx, 2.18, 4.40), _fx.glow(gcol, 1.9, t, intensity=0.55), layer=lay)
    if kind in ("end_dark", "fail_studio"):
        for sx in (-3.85, 3.85):
            r.add_sprite((sx, 2.55, 1.8), _fx.glow((244, 56, 46), 1.5, t, intensity=0.85), layer=lay)

    r.flush(buf)
    _fx.grade_cine(buf)
    _fx.present_crisp(buf, surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_H)))

    # Cut static burst during the 780..1080ms signal hijack moment
    if kind == "end_cut" and 760 < t < 1120:
        rng = random.Random(int(t // 25))
        tear = pygame.Surface((WIDTH, SCENE_H), pygame.SRCALPHA)
        for _ in range(28):
            sy = rng.randint(0, SCENE_H - 6)
            sh = rng.randint(2, 10)
            col = (140, 244, 180, 120) if t >= 900 else (244, 84, 72, 110)
            pygame.draw.rect(tear, col, (0, sy, WIDTH, sh))
        surface.blit(tear, (0, SCENE_TOP))

    _tag(surface, tag, (132, 236, 174) if mode == "record" else (228, 126, 116))


# ── Set 2: Acaristan 22:07 Night Street (m3_end_nation) ───────────────────

def _build_nation_street(r):
    from engine3d.core import box, quad_xz
    from cutscenes.ps2mat import mesh as textured

    def bake(m):
        r.bake(textured(m))

    # Wet asphalt avenue & sidewalks
    bake(quad_xz(-22, -8, 22, 48, 0.0, (16, 19, 26), seg=2.5))
    bake(box(44.0, 0.16, 5.2, (34, 38, 46), center=(0.0, 0.08, 10.6), seg=2.5))
    # Brutalist facade & storefront row along z = 13.5 with 5 glowing emerald Vostral TV windows
    bake(box(38.0, 16.0, 4.0, (22, 26, 36), center=(0.0, 8.0, 15.6), seg=2.5))
    rng = random.Random(303)
    for row in range(3):
        for col_i in range(-7, 8):
            if rng.random() < 0.58:
                wx = col_i * 2.2
                wy = 5.4 + row * 2.8
                c = (152, 214, 176) if rng.random() < 0.45 else (186, 168, 118)
                bake(box(0.95, 1.25, 0.08, c, center=(wx, wy, 13.56), emissive=True))
    # 5 large storefront showcase screens all broadcasting the emerald Vostral record
    for sx in (-8.4, -4.2, 0.0, 4.2, 8.4):
        bake(box(3.4, 2.35, 0.24, (14, 18, 22), center=(sx, 1.85, 13.52)))
        bake(box(3.05, 1.98, 0.06, (28, 92, 60), center=(sx, 1.85, 13.38), emissive=True))
        bake(box(1.85, 1.56, 0.08, (224, 224, 200), center=(sx, 1.85, 13.34), emissive=True))
        for k in range(5):
            bake(box(1.38, 0.06, 0.09, (48, 72, 60),
                     center=(sx, 2.36 - k * 0.24, 13.32), emissive=True))
        bake(box(0.36, 0.22, 0.09, (186, 48, 42), center=(sx + 0.52, 1.28, 13.32), emissive=True))
    # Giant rooftop Vostral billboard above center block
    bake(box(10.4, 4.2, 0.30, (16, 22, 26), center=(0.0, 10.6, 13.45)))
    bake(box(9.8, 3.6, 0.08, (46, 136, 88), center=(0.0, 10.6, 13.28), emissive=True))
    bake(box(5.4, 2.9, 0.10, (226, 226, 204), center=(0.0, 10.6, 13.24), emissive=True))
    # Flanking side apartment blocks framing the boulevard
    for side in (-1, 1):
        bake(box(5.0, 15.0, 26.0, (16, 20, 28), center=(side * 16.5, 7.5, 4.0), seg=3.0))


def _draw_nation_3d(surface, t):
    from engine3d.core import Light
    from engine3d import POSES
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx
    from cutscenes import m6world3d as W

    r, buf = _set("m3_nation", (10, 18, 22), 12.0, 56.0, _build_nation_street)
    u = _smooth(min(1.0, t / 5000.0))
    r.light = Light(direction=(0.0, 0.72, -0.68), ambient=0.34, diffuse=0.42,
                    sky=0.08, tint=(0.76, 1.04, 0.90))
    r.light_albedo, r.light_gain = True, 2.5
    r.set_lights([
        {"pos": (0.0, 3.0, 11.2), "color": (108, 240, 168), "intensity": 2.0, "range": 18.0},
        {"pos": (-6.4, 2.4, 11.4), "color": (104, 232, 162), "intensity": 1.5, "range": 14.0},
        {"pos": (6.4, 2.4, 11.4), "color": (104, 232, 162), "intensity": 1.5, "range": 14.0},
        {"pos": (0.0, 10.5, 11.0), "color": (118, 244, 174), "intensity": 1.4, "range": 20.0},
    ], cap=8)

    eye = (-2.6 + 5.2 * u, 1.85 + 0.55 * u, -2.4 + 2.2 * u)
    tgt = (0.0, 3.2, 13.4)
    _m5.set_cam(r, t, eye, tgt, 52, hh=0.015, seed=97)
    buf.fill((8, 14, 20))
    _m5.night_sky(r, buf, t, (6, 10, 18), (14, 26, 26), stars=24, clouds=2,
                  sodium=(28, 54, 42), mist=(12, 22, 22))
    r.begin()
    r.add_static()

    # Crowd of silhouetted citizens stopped on the wet street staring up at the Vostral
    civ = _rig("civilian")
    crowd = [
        (-5.2, 7.2, 8.0), (-2.8, 6.4, 4.0), (-0.6, 5.8, -6.0),
        (1.6, 6.6, -12.0), (3.9, 6.1, -18.0), (6.4, 7.6, -24.0),
    ]
    for i, (cx, cz, cyaw) in enumerate(crowd):
        cp = W.life_pose(dict(POSES["stand"], head_p=-18), t, amp=0.55, seed=10 + i)
        r.add_humanoid(civ, cp, (cx, 0.0, cz), cyaw, rifle_on=False)

    lay = _fx.FX_LAYER
    for sx in (-8.4, -4.2, 0.0, 4.2, 8.4):
        r.add_sprite((sx, 1.9, 13.1), _fx.glow((108, 240, 168), 2.8, t, intensity=0.52), layer=lay)
        r.add_sprite((sx, 0.04, 8.6), _m5.wet_reflection((98, 232, 158), t, seed=int(sx),
                                                         length_m=4.6, width_m=1.2, intensity=0.45), layer=2)

    r.flush(buf)
    _fx.grade_cine(buf)
    _fx.present_crisp(buf, surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_H)))
    _tag(surface, "ACARISTAN // 22:07 // VOSTRAL LIVE ON ALL CHANNELS", (136, 240, 178))


_DISPATCH = {
    "m3_end_studio": lambda s, t: _draw_booth_shot(s, t, "end_studio"),
    "m3_end_cut": lambda s, t: _draw_booth_shot(s, t, "end_cut"),
    "m3_end_nation": _draw_nation_3d,
    "m3_end_booth_dark": lambda s, t: _draw_booth_shot(s, t, "end_dark"),
    "m3_bcast_fail_studio": lambda s, t: _draw_booth_shot(s, t, "fail_studio"),
    "m3_bcast_fail_pa": lambda s, t: _draw_booth_shot(s, t, "fail_pa"),
}


def draw_scene(scene_id, surface, t):
    if not m3ending3d_enabled():
        return False
    fn = _DISPATCH.get(scene_id)
    if fn is None:
        return False
    try:
        fn(surface, t)
        return True
    except Exception as e:
        _S["failed"], _S["err"] = True, e
        print(f"m3ending3d: disabled ({scene_id}: {e!r}), using 2D")
        return False
