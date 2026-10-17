"""m5martial3d.py - W7: true-3D (engine3d) takes of every Mission 5 cutscene.

    m5_tv_bulletin     studio dolly from the TV camera rig to the anchor desk
    m5_safehouse_tv    Biribel at the rain window, the CRT playing the bulletin
    m5_retardovici_tv  the address: hall, podium, crest, a silent audience
    m5_river_gate      Maru through the gate; reverse on Biribel as the dot lands
    m5_ucilev_scope    POV through Ucilev's optic - crosshair, mil dots, breath sway
    m5_ucilev_reveal   Ucilev on the far-bank roof, coming off the rifle
    m5_ucilev_leaves   he walks to the roof stair hut and doesn't turn
    m5_radio           split frame: Biribel on the quay / Vasile in his office

engine.py calls ``draw_m5_scene_3d(scene, surface, t)`` first; it returns
False when the 3D path can't run (engine3d error, or ACARISTAN_CUTSCENE3D=0)
and the 2D m5martial scene draws instead (2D stays as the fallback).
SoftwareRenderer at 0.6x film res with a smooth upscale - no GPU needed.
The film lives inside SAFE_TOP..SAFE_BOT so the dialogue box never covers it.
"""
import math
import os
import random

import pygame

from core.config import *
from cutscenes.m5martial import (SAFE_TOP, SAFE_BOT, _CREST, _GUARD_RED, _LIAISON,
                                 _RIVER, _SODIUM, _rain_streaks, _scanlines,
                                 _studio_backdrop, _tag)
from cutscenes.m3cell import _m3_noise
from cutscenes.m3ko import _ko_tint

__all__ = ["draw_m5_scene_3d", "draw_m5_tv_bulletin_3d", "draw_m5_river_gate_3d",
           "m5_3d_enabled", "M5_3D_SCENES"]

_FILM_H = SAFE_BOT - SAFE_TOP
_RES = 0.6
_RW, _RH = int(WIDTH * _RES), int(_FILM_H * _RES)
_cache = {"r": {}, "hum": {}, "sky": {}, "failed": False, "err": None,
          "qa_no_marks": False}   # qa_no_marks: tools only (hide dot/reticle)

_SNIPER = (-16.0, 9.2, 37.0)      # Ucilev's roof on the far bank (feet)
_BIRIBEL = (0.0, 0.0, 0.4)


def m5_3d_enabled():
    """3D takes on unless ACARISTAN_CUTSCENE3D=0 or a previous frame failed."""
    if os.environ.get("ACARISTAN_CUTSCENE3D", "1").strip() == "0":
        return False
    return not _cache["failed"]


# ── plumbing ──
def _rend(w=_RW, h=_RH):
    key = (w, h)
    if key not in _cache["r"]:
        from engine3d.core import SoftwareRenderer  # lazy: 2D fallback if the 3D stack breaks
        _cache["r"][key] = (SoftwareRenderer(w, h), pygame.Surface((w, h)))
    return _cache["r"][key]


def _sky(w, h, top, bot):
    key = (w, h, top, bot)
    s = _cache["sky"].get(key)
    if s is None:
        s = pygame.Surface((w, h))
        for y in range(h):
            f = y / max(1, h - 1)
            pygame.draw.line(s, tuple(int(a + (b - a) * f) for a, b in zip(top, bot)),
                             (0, y), (w, y))
        _cache["sky"][key] = s
    return s


def _hum(key):
    h = _cache["hum"].get(key)
    if h is None:
        from cutscenes.cast3d import humanoid3d, spec3d  # lazy: see _rend
        from cutscenes.figure_kit import SPECS
        from engine3d import Humanoid
        if key == "anchor":
            # A studio face of the regime - not a recoloured Vasile.
            fk = dict(SPECS["vasile"])
            fk.update(cig=False, epaulets=None, buttons=None, belt=None, stubble=False,
                      coat=(28, 34, 52), lapel=(22, 26, 40), shirt=(228, 228, 232),
                      tie=(160, 28, 30), trousers=(26, 28, 36), hair_style="swept",
                      hair=(150, 146, 140), skin=(222, 186, 160), iris=(70, 60, 50),
                      jaw=0.94, height=248, bulk=0.96)
            h = Humanoid(spec3d(fk, glasses=(24, 24, 28), stubble_t=0.0))
        elif key == "vasile":
            # Vasile must never read as Retardovici in a close-up: older, greyer,
            # weathered, heavy-browed and broad-jawed (the President is smooth,
            # dark swept hair, narrow face).
            h = humanoid3d("vasile", hair=(118, 112, 106), skin=(176, 136, 108),
                           brow_t=5, head_w=1.1, stubble=True, stubble_t=0.16,
                           creases=(128, 94, 76), iris=(34, 44, 62))
        elif key == "ucilev":
            h = humanoid3d("ucilev", rifle="sniper")
        else:
            h = humanoid3d(key)
        _cache["hum"][key] = h
    return h


def _yaw_to(src, dst):
    """Yaw (deg) that turns a +z-facing rig at ``src`` to face ``dst``."""
    from engine3d.core import m_apply, rot_y
    sgn = 1.0 if m_apply(rot_y(90), (0, 0, 1))[0] > 0 else -1.0
    return sgn * math.degrees(math.atan2(dst[0] - src[0], dst[2] - src[2]))


def _add(r, m):
    r.add_dynamic(m.verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces])


def _dec(r, m, bias=0.8):
    """Wall decal: like _add, but pulled nearer in the painter sort (key is
    layer*1e6 - depth - bias, so a NEGATIVE bias wins) so a flat screen/poster
    never vanishes behind the big wall face it hangs on."""
    r.add_dynamic(m.verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces],
                  bias=-abs(bias))


def _k(t, start, length):
    from engine3d.core import smooth
    return smooth(max(0.0, min(1.0, (t - start) / float(length))))


def _present(surface, buf, x=0, w=WIDTH):
    surface.blit(pygame.transform.smoothscale(buf, (w, _FILM_H)), (x, SAFE_TOP))


def _film_xy(p, x0=0, w=WIDTH, rw=_RW):
    """Render-buffer point -> screen point."""
    s = w / float(rw)
    return int(x0 + p[0] * s), int(SAFE_TOP + p[1] * s)


def _chyron(surface, t, text, col, start=1400):
    n = int(len(text) * max(0.0, min(1.0, (t - start) / 1400.0)))
    if not n:
        return
    bar_h = 30
    box_top = HEIGHT - LETTER_H - 14 - (36 + 2 * 30 + 24)   # 2-line dialogue box
    bar_y = box_top - bar_h - 10
    bar_x, bar_w = 60, WIDTH - 120                          # aligned with the box
    bar = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
    bar.fill((10, 12, 20, 225))
    surface.blit(bar, (bar_x, bar_y))
    pygame.draw.rect(surface, col, (bar_x, bar_y, 4, bar_h))
    txt = font_terminal_small.render(text[:n], True, col)
    surface.blit(txt, (bar_x + 18, bar_y + bar_h // 2 - txt.get_height() // 2))


def _live(surface, t):
    if (t // 500) % 2 == 0:
        s = font_terminal_small.render("LIVE", True, (230, 60, 50))
        surface.blit(s, (WIDTH - s.get_width() - 24, SAFE_TOP + 9))


_GRADE = {}


def _grade(surface, gamma=0.8, vig=0.42):
    """Film grade for every M5 3D take: lift the crushed software-render
    shadows (gamma LUT) and pull the corners down (vignette) so the eye lands
    on the actors instead of a flat dark frame."""
    band = surface.subsurface((0, SAFE_TOP, WIDTH, _FILM_H))
    key = (gamma, vig)
    if key not in _GRADE:
        lut = [min(255, int(255 * (i / 255.0) ** gamma + 0.5)) for i in range(256)]
        small = pygame.Surface((48, 24))
        for y in range(24):
            for x in range(48):
                dx, dy = (x - 23.5) / 23.5, (y - 11.5) / 11.5
                v = max(0.0, 1.0 - vig * (0.55 * dx * dx + 0.45 * dy * dy) ** 1.2)
                small.set_at((x, y), (int(255 * v),) * 3)
        _GRADE[key] = (lut, pygame.transform.smoothscale(small, (WIDTH, _FILM_H)))
    lut, vmask = _GRADE[key]
    try:
        import numpy as np  # lazy: grade is optional polish
        arr = pygame.surfarray.pixels3d(band)
        arr[...] = np.asarray(lut, dtype=np.uint8)[arr]
        del arr
    except Exception:
        pass
    band.blit(vmask, (0, 0), special_flags=pygame.BLEND_MULT)


def _finish(surface, seed, tag, col=(120, 200, 220), grade=True):
    if grade:
        _grade(surface)
    _m3_noise(surface, seed, count=20, alpha=12)
    _ko_tint(surface)
    _tag(surface, tag, col)


def _walk(ph, amp=1.0, rifle_p=80):
    s = math.sin(ph)
    return dict(spine=4, lhip_p=24 * s * amp, rhip_p=-24 * s * amp,
                lkn=10 + 26 * max(0.0, -math.cos(ph)) * amp,
                rkn=10 + 26 * max(0.0, math.cos(ph)) * amp,
                lsh_p=-14 * s * amp + 6, rsh_p=14 * s * amp + 6, lel=20, rel=20,
                rifle_p=rifle_p)


# ── shared sets ──
def _river_world(r, t, *, roof=True):
    """Quay, water, gate, sodium lamp, tunnel mouth and the far bank with
    Ucilev's roof (parapet + stair hut). Used by five shots."""
    from engine3d.core import box, quad_xz
    _add(r, quad_xz(-14, -8, 14, 2.6, 0.0, (28, 28, 34), seg=4))
    _add(r, box(28, 0.25, 0.3, (44, 44, 50), center=(0, 0.05, 2.75)))
    wcol = lambda x, z: (14, 22 + int(5 * math.sin(x * .7 + z * .5 + t * .003)), 36)
    _add(r, quad_xz(-40, 2.9, 30, 60, -0.6, (14, 22, 32), seg=8, colfn=wcol))
    rng = random.Random(903)
    for i in range(10):
        bx = -34 + i * 7
        if abs(bx - _SNIPER[0]) < 5:
            continue
        bh = rng.uniform(6, 13)
        _add(r, box(6, bh, 4, (13, 15, 21), center=(bx, bh / 2 - 0.6, 39)))
        for _w in range(4):
            if rng.random() < 0.5:
                _add(r, box(0.6, 0.5, 0.05, (130, 108, 74),
                           center=(bx + rng.uniform(-2, 2), rng.uniform(1, bh - 1), 36.96),
                           emissive=True))
    for i in range(12):                     # far skyline beyond the bank: depth + rim
        bx = -60 + i * 10 + rng.uniform(-2, 2)
        bh = rng.uniform(14, 26)
        _add(r, box(8, bh, 4, (20, 24, 34), center=(bx, bh / 2 - 0.6, 64)))
        for _w in range(5):
            if rng.random() < 0.55:
                _add(r, box(0.8, 0.6, 0.05, (150, 120, 80),
                           center=(bx + rng.uniform(-3, 3), rng.uniform(2, bh - 2), 61.96),
                           emissive=True))
    if roof:   # Ucilev's building: roof top at _SNIPER[1]
        sx, sy, sz = _SNIPER
        _add(r, box(8, sy + 0.6, 9, (17, 18, 24), center=(sx, sy / 2 - 0.3, sz + 3.5)))
        _add(r, box(8, 0.5, 0.25, (30, 30, 36), center=(sx, sy + 0.25, sz - 0.9)))
        _add(r, box(2.2, 2.3, 2.0, (24, 25, 30), center=(sx, sy + 1.15, sz + 6.6)))
        _dec(r, box(0.9, 1.9, 0.04, (170, 136, 88), center=(sx, sy + 0.95, sz + 5.58),
                   emissive=True), 0.3)                              # stair door, lit
        _add(r, quad_xz(sx - 1.0, sz + 3.4, sx + 1.0, sz + 5.5, sy + 0.01, (46, 38, 28),
                        emissive=True))                              # its spill on the roof
        _add(r, box(0.06, 3.0, 0.06, (40, 40, 46), center=(sx + 2.6, sy + 1.5, sz + 4)))
        _add(r, box(0.12, 0.12, 0.12, (220, 40, 40), center=(sx + 2.6, sy + 3.0, sz + 4),
                   emissive=True))                                   # antenna light
    # Tunnel mouth (left).
    _add(r, box(0.6, 3.4, 3.0, (38, 38, 44), center=(-6.0, 1.7, 0.5)))
    _add(r, box(3.0, 0.6, 3.0, (38, 38, 44), center=(-7.5, 3.4, 0.5)))
    _add(r, box(2.4, 2.8, 0.1, (8, 9, 12), center=(-7.5, 1.4, -0.9)))
    # Iron gate (right).
    for b in range(8):
        _add(r, box(0.08, 3.0, 0.08, (60, 64, 72), center=(3.6 + b * 0.42, 1.5, 2.2)))
    for y in (0.4, 2.2, 2.95):
        _add(r, box(3.4, 0.08, 0.08, (60, 64, 72), center=(5.07, y, 2.2)))
    for x in (3.3, 6.9):
        _add(r, box(0.3, 3.4, 0.3, (44, 46, 52), center=(x, 1.7, 2.2)))
    # Sodium lamp + reflection.
    _add(r, box(0.1, 4.4, 0.1, (38, 38, 44), center=(2.6, 2.2, 1.8)))
    _add(r, box(0.3, 0.22, 0.3, (255, 214, 150), center=(2.6, 4.45, 1.8), emissive=True))
    _add(r, quad_xz(1.2, -0.8, 4.0, 2.4, 0.01, (84, 66, 44), emissive=True))  # lamp pool
    for bx in (-4.0, -1.2, 1.6, 8.4):                                         # bollards
        _add(r, box(0.32, 0.6, 0.32, (34, 34, 40), center=(bx, 0.3, 2.35)))
        _add(r, box(0.4, 0.08, 0.4, (44, 44, 52), center=(bx, 0.62, 2.35)))
    for px, pz, pw in ((-2.6, -1.4, 1.4), (0.6, -2.6, 1.0), (4.6, -0.6, 1.2)):  # puddles
        _add(r, quad_xz(px, pz, px + pw, pz + pw * 0.5, 0.008, (40, 46, 60), emissive=True))
    for i in range(6):
        a = 0.6 + 0.4 * math.sin(t * 0.004 + i * 1.7)
        _add(r, box(0.5 + i * 0.1, 0.01, 0.12, tuple(int(c * a * 0.6) for c in _SODIUM),
                   center=(2.6 + math.sin(t * .002 + i) * .2, -0.58, 4.0 + i * 1.4),
                   emissive=True))


def _night(r, fog_end=70.0):
    from engine3d.core import Light
    r.fog, r.fog_start, r.fog_end = (14, 18, 26), 12.0, fog_end
    r.light = Light(direction=(0.4, 0.8, -0.35), ambient=0.46, diffuse=0.8,
                    tint=(1.1, 0.9, 0.7))


def _flags(r, x, z, h=2.6):
    from engine3d.core import box
    _add(r, box(0.05, h, 0.05, (160, 148, 112), center=(x, h / 2, z)))
    _add(r, box(0.08, 0.08, 0.08, _CREST, center=(x, h + 0.04, z)))
    _add(r, box(0.75, 0.42, 0.03, (24, 34, 58), center=(x + 0.4, h - 0.3, z)))
    _add(r, box(0.75, 0.42, 0.03, (150, 30, 32), center=(x + 0.4, h - 0.72, z)))


# ── 1. bulletin ──
def _bulletin(surface, t):
    from engine3d.core import Light, box, quad_xz, v_lerp, lerp
    r, buf = _rend()
    r.fog, r.fog_start, r.fog_end = (8, 10, 16), 8.0, 30.0
    r.light = Light(direction=(0.35, 0.65, -0.7), ambient=0.42, diffuse=0.74,
                    tint=(0.95, 0.97, 1.08))
    k = _k(t, 0, 5600)
    cam = v_lerp((-3.8, 2.4, -5.6), (-0.9, 1.85, -2.3), k)
    tgt = v_lerp((0.4, 1.5, 2.0), (0.25, 1.62, 2.1), k)
    r.set_camera(cam, tgt, lerp(50, 34, k), roll=lerp(-2.0, 0.0, k))
    buf.fill((7, 9, 15))
    r.begin()
    _add(r, quad_xz(-9, -7, 9, 9, 0.0, (18, 20, 28), seg=6))
    _add(r, box(18, 6, 0.2, (24, 24, 30), center=(0, 3, 5.6)))
    glow = 0.85 + 0.15 * math.sin(t * 0.004)
    _dec(r, box(4.6, 2.7, 0.08, (12, 12, 14), center=(2.2, 2.55, 5.45)), 0.5)
    _dec(r, box(4.3, 2.4, 0.04, tuple(int(c * glow) for c in (70, 112, 172)),
               center=(2.2, 2.55, 5.4), emissive=True), 0.8)
    for i in range(5):                                       # map grid on the wall screen
        _dec(r, box(4.3, 0.015, 0.02, (90, 130, 180), center=(2.2, 1.75 + i * 0.4, 5.37),
                   emissive=True), 1.0)
    _dec(r, box(1.6, 1.0, 0.03, (30, 44, 70), center=(1.6, 2.7, 5.36), emissive=True), 1.1)
    _dec(r, box(0.5, 0.5, 0.03, (170, 40, 36), center=(2.9, 2.9, 5.36), emissive=True), 1.1)
    _dec(r, box(4.3, 0.28, 0.03, (190, 40, 36), center=(2.2, 1.48, 5.37), emissive=True), 1.1)
    _dec(r, box(1.2, 1.2, 0.06, _CREST, center=(-2.4, 2.8, 5.45), emissive=True), 0.8)
    _dec(r, box(0.8, 0.8, 0.04, (110, 86, 40), center=(-2.4, 2.8, 5.42)), 1.0)
    for i in range(9):                                       # studio light strip
        _dec(r, box(0.9, 0.06, 0.03, (120, 140, 180), center=(-4.0 + i * 1.0, 4.4, 5.45),
                   emissive=True), 0.8)
    for fx in (-3.8, -1.3):
        _flags(r, fx, 5.0)
    r.add_humanoid(_hum("anchor"),
                   dict(spine=4, head_p=math.sin(t * 0.006) * 3, head_y=math.sin(t * .0013) * 6,
                        lsh_p=36, lsh_r=10, lel=84, rsh_p=36 + math.sin(t * .004) * 6,
                        rsh_r=10, rel=84),
                   (0.0, 0.0, 2.2), 180.0, rifle_on=False)
    _add(r, box(3.8, 1.05, 1.1, (26, 30, 44), center=(0, 0.52, 1.55)))
    _add(r, box(3.9, 0.06, 1.2, (66, 60, 56), center=(0, 1.08, 1.55)))
    _add(r, box(0.5, 0.01, 0.34, (224, 224, 218), center=(0.25, 1.12, 1.45)))
    _dec(r, box(1.6, 0.18, 0.02, (190, 40, 36), center=(0, 0.82, 0.99), emissive=True), 0.3)
    _dec(r, box(3.8, 0.03, 0.02, (110, 120, 150), center=(0, 1.0, 0.99), emissive=True), 0.3)
    if k < 0.6:   # the studio's TV camera rig, foreground left
        _add(r, box(0.5, 0.45, 0.8, (30, 32, 36), center=(-3.0, 1.3, -3.4)))
        _add(r, box(0.06, 1.1, 0.06, (40, 42, 46), center=(-3.0, 0.55, -3.4)))
        _add(r, box(0.08, 0.08, 0.08, (220, 40, 40), center=(-2.85, 1.58, -3.05),
                   emissive=True))
    r.flush(buf)
    surface.fill((0, 0, 0))
    _present(surface, buf)
    _chyron(surface, t, "BALACEANU DEATH 'SUICIDE'  ·  MORE AT 22:00", (220, 90, 70))
    _live(surface, t)
    _finish(surface, 5151, "STATE TELEVISION // 21:58")


# ── 2. safehouse ──
def _safehouse_feed(t):
    from cutscenes.cast import draw_balaceanu  # lazy: cast import only on demand
    fw, fh = 150, 110
    feed = pygame.Surface((fw, fh))
    _studio_backdrop(feed, fw // 2, fh // 2, fw, fh)
    draw_balaceanu(feed, fw // 2, fh - 12, scale=fh / 460.0, facing_right=False)
    pygame.draw.rect(feed, (150, 34, 30), (0, fh - 22, fw, 12))
    _scanlines(feed, (0, 0, fw, fh))
    return feed


def _tv_feed_quad(r, buf, feed, quad, strips=40):
    """Map ``feed`` onto a world-space quad (TL, TR, BR, BL) after flush:
    perspective-correct per vertical strip (each strip's ends are projected
    from 3D), plus a soft additive phosphor bloom around the glass."""
    tl, tr, br, bl = quad
    fw, fh = feed.get_size()
    pts = []
    for i in range(strips + 1):
        u = i / strips
        top = tuple(a + (b - a) * u for a, b in zip(tl, tr))
        bot = tuple(a + (b - a) * u for a, b in zip(bl, br))
        pt, pb = r.project(top), r.project(bot)
        if pt is None or pb is None:
            return
        pts.append((pt, pb))
    if pts[-1][0][0] <= pts[0][0][0]:
        return                                   # back of the set faces us
    for i in range(strips):
        (t0, b0), (t1, _b1) = pts[i], pts[i + 1]
        x0, x1 = int(t0[0]), int(math.ceil(t1[0]))
        y0, y1 = int(t0[1]), int(b0[1])
        if x1 <= x0 or y1 <= y0:
            continue
        c0 = int(fw * i / strips)
        c1 = max(c0 + 1, int(fw * (i + 1) / strips))
        col = feed.subsurface((c0, 0, c1 - c0, fh))
        buf.blit(pygame.transform.smoothscale(col, (x1 - x0, y1 - y0)), (x0, y0))
    cx = sum(p[0][0] + p[1][0] for p in (pts[0], pts[-1])) / 4
    cy = sum(p[0][1] + p[1][1] for p in (pts[0], pts[-1])) / 4
    rad = int(max(8, abs(pts[-1][0][0] - pts[0][0][0]) * 1.1))
    glow = _cache["sky"].get(("tvglow", rad))
    if glow is None:
        glow = pygame.Surface((rad * 2, rad * 2))
        for k in range(rad, 0, -2):
            f = (1 - k / rad) ** 2
            pygame.draw.circle(glow, (int(18 * f), int(26 * f), int(40 * f)), (rad, rad), k)
        _cache["sky"][("tvglow", rad)] = glow
    buf.blit(glow, (int(cx - rad), int(cy - rad)), special_flags=pygame.BLEND_ADD)


def _safehouse(surface, t):
    from engine3d.core import Light, box, quad_xz, v_lerp, lerp
    r, buf = _rend()
    r.fog, r.fog_start, r.fog_end = (8, 8, 10), 6.0, 20.0
    r.light = Light(direction=(-0.4, 0.8, -0.3), ambient=0.44, diffuse=0.82,
                    tint=(1.18, 0.98, 0.78))                   # bare bulb, warm
    k = _k(t, 0, 7000)
    r.set_camera(v_lerp((-2.9, 1.7, -1.6), (-2.3, 1.62, -0.9), k),
                 (1.0, 1.15, 2.7), lerp(60, 52, k))
    buf.fill((8, 8, 10))
    r.begin()
    _add(r, quad_xz(-5, -5, 5, 4.2, 0.0, (34, 28, 24), seg=2))
    wall = (30, 28, 30)
    _add(r, box(3.2, 3.2, 0.2, wall, center=(-3.4, 1.6, 4.2)))        # back wall L
    _add(r, box(4.4, 3.2, 0.2, wall, center=(2.8, 1.6, 4.2)))         # back wall R
    _add(r, box(2.4, 0.9, 0.2, wall, center=(-0.6, 0.45, 4.2)))       # under window
    _add(r, box(2.4, 0.5, 0.2, wall, center=(-0.6, 2.95, 4.2)))       # over window
    _add(r, box(0.2, 3.2, 9, (26, 24, 26), center=(-5.0, 1.6, 0)))
    _add(r, box(0.2, 3.2, 9, (26, 24, 26), center=(5.0, 1.6, 0)))
    _add(r, box(2.4, 1.8, 0.04, (16, 22, 34), center=(-0.6, 1.8, 4.3), emissive=True))
    for i in range(10):                                               # rain on glass
        y = 2.6 - ((t * 0.0009 + i * 0.37) % 1.6)
        _add(r, box(0.015, 0.16, 0.01, (54, 68, 88),
                   center=(-1.7 + i * 0.24, y, 4.26), emissive=True))
    _add(r, box(0.06, 1.8, 0.06, (40, 38, 40), center=(-0.6, 1.8, 4.22)))
    _add(r, box(0.012, 0.8, 0.012, (40, 40, 44), center=(1.4, 2.8, 1.6)))
    _add(r, box(0.14, 0.18, 0.14, (255, 222, 170), center=(1.4, 2.32, 1.6), emissive=True))
    _add(r, box(1.6, 0.9, 0.8, (54, 40, 34), center=(-3.4, 0.45, 2.6)))  # sofa
    _add(r, quad_xz(-1.4, 0.6, 1.2, 2.6, 0.012, (44, 30, 24), seg=2))       # rug
    # ── the CRT: a proper set on a crate, turned toward Biribel / the lens ──
    # (it used to be an axis-aligned grey cube seen side-on, with the feed
    # pasted as a flat rectangle hanging off its edge)
    piv = (2.4, 0.0, 2.6)
    yaw = math.atan2(-0.874, 0.486)            # front (-z) -> toward (-1.2, 0.6)
    cs, sn = math.cos(yaw), math.sin(yaw)

    def _w(p):                                  # TV-local -> world
        return (piv[0] + p[0] * cs - p[2] * sn, piv[1] + p[1],
                piv[2] + p[0] * sn + p[2] * cs)

    def _tv(m, dec=0.0):
        m.verts = [_w(v) for v in m.verts]
        (_dec(r, m, dec) if dec else _add(r, m))

    _tv(box(1.0, 0.6, 0.7, (40, 32, 26), center=(0, 0.3, 0)))                 # crate
    _tv(box(0.04, 0.6, 0.72, (30, 24, 20), center=(0.3, 0.3, 0)))             # crate slat
    _tv(box(0.86, 0.64, 0.34, (58, 48, 40), center=(0, 0.92, -0.12),
            cols={"top": (70, 58, 48), "front": (62, 52, 44)}))               # cabinet
    _tv(box(0.6, 0.46, 0.3, (36, 36, 40), center=(0, 0.92, 0.18)))            # tube back
    _tv(box(0.64, 0.5, 0.02, (14, 14, 16), center=(-0.08, 0.95, -0.295)), 0.3)  # bezel
    _tv(box(0.56, 0.42, 0.01, (70, 96, 130), center=(-0.08, 0.95, -0.305),
            emissive=True), 0.5)                                               # glass
    for ky in (1.04, 0.92):                                                    # knobs
        _tv(box(0.07, 0.07, 0.04, (150, 140, 120), center=(0.32, ky, -0.3)), 0.6)
    for gy in range(4):                                                        # speaker
        _tv(box(0.12, 0.012, 0.01, (24, 20, 18), center=(0.32, 0.8 - gy * 0.03, -0.296)), 0.6)
    _tv(quad_xz(-0.9, -1.9, 0.9, -0.36, 0.011, (24, 32, 48), emissive=True))  # screen spill
    _tv(box(0.24, 0.02, 0.14, (30, 30, 34), center=(0, 1.25, 0.06)))          # antenna foot
    _add(r, box(0.9, 0.05, 0.6, (60, 44, 32), center=(-1.6, 0.72, 0.6)))      # table + mug
    for lx, lz in ((-1.95, 0.4), (-1.25, 0.4), (-1.95, 0.8), (-1.25, 0.8)):
        _add(r, box(0.05, 0.7, 0.05, (44, 32, 24), center=(lx, 0.35, lz)))
    _add(r, box(0.08, 0.1, 0.08, (180, 170, 150), center=(-1.5, 0.8, 0.6)))
    _add(r, box(0.36, 0.02, 0.26, (200, 196, 186), center=(-1.8, 0.76, 0.6)))
    _dec(r, box(0.6, 0.8, 0.03, (120, 104, 80), center=(3.2, 1.9, 4.08)), 0.8)   # calendar
    _dec(r, box(0.5, 0.2, 0.03, (170, 40, 36), center=(3.2, 2.2, 4.06)), 1.0)
    bpos = (-0.3, 0.0, 1.7)
    r.add_humanoid(_hum("biribel"),
                   dict(head_p=4 + math.sin(t * 0.0015) * 3, lsh_p=-6, lsh_r=10, lel=40,
                        rsh_p=-6, rsh_r=10, rel=40),
                   bpos, _yaw_to(bpos, (2.4, 0, 2.6)), rifle_on=False)
    for sx_ in (-1, 1):                                       # rabbit-ear antenna
        r.add_line3d(_w((0, 1.26, 0.06)), _w((sx_ * 0.32, 1.72, 0.14)), (120, 122, 130), 1)
    r.flush(buf)
    _tv_feed_quad(r, buf, _safehouse_feed(t),
                  [_w(p) for p in ((-0.35, 1.16, -0.312), (0.19, 1.16, -0.312),
                                   (0.19, 0.74, -0.312), (-0.35, 0.74, -0.312))])
    surface.fill((0, 0, 0))
    _present(surface, buf)
    _finish(surface, 4004, "SAFEHOUSE // KRAP FLAT 4C", _LIAISON)


# ── 3. the address ──
def _address(surface, t):
    from engine3d.core import Light, box, quad_xz, v_lerp, lerp
    r, buf = _rend()
    r.fog, r.fog_start, r.fog_end = (10, 12, 18), 10.0, 34.0
    r.light = Light(direction=(0.2, 0.75, -0.65), ambient=0.4, diffuse=0.78,
                    tint=(1.06, 1.0, 0.9))
    k = _k(t, 0, 7000)
    r.set_camera(v_lerp((0.8, 2.1, -7.2), (0.3, 1.95, -4.8), k), (0.0, 1.7, 2.0),
                 lerp(42, 34, k))
    buf.fill((10, 12, 18))
    r.begin()
    _add(r, quad_xz(-10, -10, 10, 8, 0.0, (22, 20, 22), seg=6))
    _add(r, quad_xz(-3, 0.6, 3, 4, 0.35, (60, 24, 26)))               # red stage carpet
    _add(r, box(6, 0.35, 3.4, (34, 30, 30), center=(0, 0.17, 2.3)))
    _add(r, box(20, 7, 0.2, (24, 28, 40), center=(0, 3.5, 5.0)))
    for fx in (-2.6, -1.8, 1.0, 1.8):
        _flags(r, fx, 4.6, h=3.4)
    _dec(r, box(1.6, 1.6, 0.06, (150, 120, 62), center=(0, 3.7, 4.86), emissive=True), 0.8)
    _dec(r, box(1.1, 1.1, 0.04, (120, 92, 44), center=(0, 3.7, 4.82)), 1.0)
    for dx in (-3.6, -0.9, 0.9, 3.6):                        # state drapes
        _dec(r, box(0.8, 5.2, 0.04, (96, 22, 26), center=(dx, 3.4, 4.88)), 0.6)
        _dec(r, box(0.8, 0.12, 0.03, (160, 130, 64), center=(dx, 1.0, 4.85), emissive=True), 0.8)
    _dec(r, box(14, 0.08, 0.03, (150, 130, 80), center=(0, 6.2, 4.88), emissive=True), 0.6)
    r.add_humanoid(_hum("president"),
                   dict(spine=4, head_p=math.sin(t * .005) * 4, head_y=math.sin(t * .0011) * 12,
                        lsh_p=34, lsh_r=10, lel=80,
                        rsh_p=40 + 18 * max(0.0, math.sin(t * .0035)), rsh_r=16,
                        rel=70 + 20 * math.sin(t * .0035)),
                   (0.0, 0.35, 2.4), 180.0, rifle_on=False)
    _add(r, box(1.2, 1.25, 0.7, (26, 30, 44), center=(0, 0.97, 1.7)))  # podium
    _add(r, box(0.42, 0.42, 0.02, (150, 120, 62), center=(0, 1.05, 1.34), emissive=True))
    _add(r, box(0.26, 0.26, 0.02, (70, 52, 30), center=(0, 1.05, 1.32)))
    for row in range(3):                                              # the audience
        z = -1.2 - row * 1.1
        for i in range(9):
            x = -4.0 + i * 1.0 + (row % 2) * 0.5
            _add(r, box(0.55, 0.9, 0.4, (10, 12, 18), center=(x, 0.45 + row * 0.15, z)))
            _add(r, box(0.26, 0.3, 0.26, (14, 15, 20), center=(x, 1.08 + row * 0.15, z)))
    r.flush(buf)
    surface.fill((0, 0, 0))
    _present(surface, buf)
    _chyron(surface, t, "PRESIDENT RETARDOVICI  ·  ADDRESS TO THE NATION", _CREST, 1600)
    _live(surface, t)
    _finish(surface, 5152, "ADDRESS TO THE NATION // PARLIAMENT SUSPENDED")


# ── 4. river gate ──
def _river(surface, t):
    from engine3d.core import v_lerp, lerp
    r, buf = _rend()
    t = max(0, min(t, 7200))
    _night(r)
    reverse = t >= 3400
    if not reverse:   # A: wide from behind Biribel, watching Maru go
        k = _k(t, 0, 3400)
        r.set_camera(v_lerp((-3.4, 2.3, -5.6), (-2.4, 2.0, -4.4), k), (3.0, 1.4, 2.6),
                     lerp(50, 44, k))
    else:             # B: reverse medium on his face as the dot finds him
        k = _k(t, 3400, 3800)
        r.set_camera(v_lerp((1.0, 1.6, 2.5), (0.7, 1.55, 2.05), k), (0.0, 1.5, 0.4),
                     lerp(44, 36, k))
    buf.blit(_sky(_RW, _RH, (18, 22, 34), (8, 10, 14)), (0, 0))
    r.begin()
    _river_world(r, t)
    mk = _k(t, 0, 3400)
    if mk < 1.0:
        mpos = (lerp(4.4, 9.5, mk), 0.0, lerp(2.9, 4.2, mk))
        r.add_humanoid(_hum("maru"), _walk(t * 0.011), mpos,
                       _yaw_to(mpos, (12, 0, 5)), rifle_on=False)
    face_gate = _yaw_to(_BIRIBEL, (5.0, 0, 3.0))
    face_bank = _yaw_to(_BIRIBEL, _SNIPER)
    turn = _k(t, 2600, 1400)
    j = r.add_humanoid(_hum("biribel"), dict(head_p=-4 * turn),
                       _BIRIBEL, lerp(face_gate, face_bank, turn), rifle_on=False)
    if not _cache["qa_no_marks"]:
        from engine3d.rig import POSES
        r.add_humanoid(_hum("ucilev"), POSES["aim"], _SNIPER, _yaw_to(_SNIPER, _BIRIBEL))
    chest = j.get("chest") or j.get("spine") or j.get("pelvis")
    dk = _k(t, 3700, 1300) if not _cache["qa_no_marks"] else 0.0
    aim = None
    if dk > 0 and chest:
        drift = (1 - dk) * 0.5
        aim = (chest[0] + drift, chest[1] + 0.05 + drift * 0.4, chest[2] + 0.18)
        r.add_line3d((_SNIPER[0], _SNIPER[1] + 1.4, _SNIPER[2]), aim, (120, 18, 18), 1)
    r.flush(buf)
    surface.fill((0, 0, 0))
    _present(surface, buf)
    p = r.project(aim) if aim else None
    if p:
        cx, cy = _film_xy(p)
        pulse = 0.7 + 0.3 * math.sin(t * 0.012)
        halo = pygame.Surface((44, 44), pygame.SRCALPHA)
        pygame.draw.circle(halo, (255, 40, 30, int(80 * dk * pulse)), (22, 22), 16)
        surface.blit(halo, (cx - 22, cy - 22))
        pygame.draw.circle(surface, (255, 50, 36), (cx, cy), 3)
    _rain_streaks(surface, t, 77)
    _finish(surface, 2202, "RIVER GATE // EAST CHANNEL", _RIVER)


# ── 5. the scope (crosshair POV) ──
def _scope(surface, t):
    from engine3d.core import lerp
    r, buf = _rend()
    t = max(0, min(t, 9200))
    _night(r, fog_end=120.0)
    settle = _k(t, 1200, 2400)
    sway = (math.sin(t * 0.0021) * 0.22 * (1 - settle) + math.sin(t * .0007) * 0.02,
            math.cos(t * 0.0017) * 0.16 * (1 - settle))
    eye = (_SNIPER[0] + 0.15, _SNIPER[1] + 1.25, _SNIPER[2] - 0.6)
    tgt = (_BIRIBEL[0] + sway[0], 1.38 + sway[1], _BIRIBEL[2])
    r.set_camera(eye, tgt, lerp(9.0, 5.5, _k(t, 0, 3000)))
    buf.blit(_sky(_RW, _RH, (18, 22, 34), (8, 10, 14)), (0, 0))
    r.begin()
    _river_world(r, t, roof=False)
    r.add_humanoid(_hum("biribel"), dict(head_y=math.sin(t * .0009) * 10),
                   _BIRIBEL, _yaw_to(_BIRIBEL, (_SNIPER[0], 0, _SNIPER[2])), rifle_on=False)
    r.flush(buf)
    surface.fill((0, 0, 0))
    _present(surface, buf)
    _rain_streaks(surface, t, 12, n=50)
    if not _cache["qa_no_marks"]:
        _reticle(surface, t)
    _m3_noise(surface, 8808, count=50, alpha=14)
    _ko_tint(surface)
    _tag(surface, "OPTIC // FAR BANK", _GUARD_RED)


def _reticle(surface, t):
    """Round optic over the film: black outside the glass, vignette ring,
    duplex crosshair with mil dots, lit centre dot, etched range data."""
    cx, cy = WIDTH // 2, SAFE_TOP + _FILM_H // 2
    rad = _FILM_H // 2 - 8
    mask = pygame.Surface((WIDTH, _FILM_H), pygame.SRCALPHA)
    mask.fill((0, 0, 0, 255))
    pygame.draw.circle(mask, (0, 0, 0, 0), (cx, _FILM_H // 2), rad)
    for i in range(14):
        pygame.draw.circle(mask, (0, 0, 0, 200 - i * 14), (cx, _FILM_H // 2), rad - i, 1)
    surface.blit(mask, (0, SAFE_TOP))
    ink = (8, 8, 10)
    gap, thick = 26, rad * 0.55
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):     # thick outer posts
        a = (cx + dx * rad, cy + dy * rad)
        b = (cx + dx * thick, cy + dy * thick)
        pygame.draw.line(surface, ink, a, b, 5)
        pygame.draw.line(surface, ink, b, (cx + dx * gap, cy + dy * gap), 1)
    pygame.draw.line(surface, ink, (cx - gap + 8, cy), (cx + gap - 8, cy), 1)
    pygame.draw.line(surface, ink, (cx, cy - gap + 8), (cx, cy + gap - 8), 1)
    for k in range(1, 6):                                # mil dots
        for dx, dy in ((-1, 0), (1, 0), (0, 1)):
            pygame.draw.circle(surface, ink, (cx + dx * k * 22, cy + dy * k * 22), 2)
    pulse = 0.75 + 0.25 * math.sin(t * 0.008)
    pygame.draw.circle(surface, (int(255 * pulse), 50, 40), (cx, cy), 2)
    etched = (150, 165, 175)
    hud = font_terminal_small.render("Y-3  INTAKE MATCH", True, etched)
    surface.blit(hud, (cx - hud.get_width() // 2, cy + rad - 34))
    rng_txt = font_terminal_small.render("RANGE 240m  ·  WIND L2", True, (120, 135, 145))
    surface.blit(rng_txt, (cx - rng_txt.get_width() // 2, cy + rad - 56))


# ── 6. reveal ──
def _reveal(surface, t):
    from engine3d.core import v_lerp, lerp
    from engine3d.rig import blend
    r, buf = _rend()
    t = max(0, min(t, 8400))
    _night(r)
    k = _k(t, 0, 8000)
    sx, sy, sz = _SNIPER
    r.set_camera(v_lerp((sx + 2.6, sy + 1.1, sz - 3.4), (sx + 1.7, sy + 1.45, sz - 2.4), k),
                 (sx, sy + 1.35, sz + 0.2), lerp(46, 38, k))
    buf.blit(_sky(_RW, _RH, (22, 26, 38), (10, 12, 16)), (0, 0))
    r.begin()
    _river_world(r, t)
    lift = _k(t, 900, 2200)
    lower = _k(t, 3400, 2600)
    low = dict(spine=4, head_p=4, lsh_p=34, lsh_r=6, lel=56, rsh_p=22, rsh_r=14, rel=60,
               rifle_p=40)
    down = dict(low, rifle_p=78, lsh_p=20, lel=40, head_p=8)
    pose = blend(blend("aim", low, lift), down, lower)
    r.add_humanoid(_hum("ucilev"), pose, _SNIPER,
                   _yaw_to(_SNIPER, _BIRIBEL) + 10 * lift)
    r.flush(buf)
    surface.fill((0, 0, 0))
    _present(surface, buf)
    _rain_streaks(surface, t, 33, n=80)
    _finish(surface, 4411, "UCILEV NADGOB IERDNA // LISTED DEAD", _GUARD_RED)


# ── 7. he leaves ──
def _leaves(surface, t):
    from engine3d.core import lerp
    r, buf = _rend()
    t = max(0, min(t, 6800))
    _night(r)
    sx, sy, sz = _SNIPER
    r.set_camera((sx + 0.7, sy + 2.0, sz - 4.6), (sx, sy + 1.2, sz + 5.6), 50)
    buf.blit(_sky(_RW, _RH, (22, 26, 38), (10, 12, 16)), (0, 0))
    r.begin()
    _river_world(r, t)
    walk = _k(t, 400, 5400)
    pos = (sx, sy, lerp(sz, sz + 5.3, walk))
    if walk < 0.995:
        r.add_humanoid(_hum("ucilev"), _walk(t * 0.009, amp=0.9 if walk < .98 else 0),
                       pos, _yaw_to(pos, (sx, sy, sz + 10)))
    r.flush(buf)
    surface.fill((0, 0, 0))
    _present(surface, buf)
    _rain_streaks(surface, t, 55, n=100)
    _finish(surface, 4412, "EAST CHANNEL // HE DOESN'T TURN", _RIVER)


# ── 8. radio (split) ──
def _handset(r, j):
    from engine3d.core import box
    h = j.get("lhand")
    if h:
        _add(r, box(0.05, 0.2, 0.06, (20, 20, 22), center=(h[0], h[1] + 0.06, h[2])))


_RADIO = dict(spine=4, head_p=4, head_y=-10, lsh_p=40, lsh_r=60, lel=150,
              rsh_p=10, rsh_r=10, rel=30)


def _radio(surface, t):
    from engine3d.core import Light, box, quad_xz, lerp
    t = max(0, min(t, 8800))
    hw = _RW // 2
    k = _k(t, 0, 8000)
    # LEFT - Biribel on the quay, handset up, gate lamp behind him.
    r, buf = _rend(hw, _RH)
    _night(r)
    r.set_camera((-0.3, 1.7, -1.9 + k * 0.3), (0.2, 1.6, 0.5), lerp(46, 40, k))
    buf.blit(_sky(hw, _RH, (18, 22, 34), (8, 10, 14)), (0, 0))
    r.begin()
    _river_world(r, t)
    j = r.add_humanoid(_hum("biribel"), _RADIO, _BIRIBEL, _yaw_to(_BIRIBEL, (-1.2, 0, -3)),
                       rifle_on=False)
    _handset(r, j)
    r.flush(buf)
    surface.fill((0, 0, 0))
    _present(surface, buf, 0, WIDTH // 2)
    # RIGHT - Vasile's office: desk, flag, desk lamp, blinds. No rain.
    r, buf = _rend(hw, _RH)
    r.fog, r.fog_start, r.fog_end = (12, 11, 10), 8.0, 24.0
    r.light = Light(direction=(-0.5, 0.7, -0.5), ambient=0.42, diffuse=0.78,
                    tint=(1.14, 1.0, 0.84))
    r.set_camera((0.7, 1.68, -1.5 + k * 0.3), (-0.05, 1.55, 1.2), lerp(46, 40, k))
    buf.fill((14, 12, 12))
    r.begin()
    _add(r, quad_xz(-5, -5, 5, 3.2, 0.0, (40, 30, 26), seg=2))
    _add(r, box(10, 3.2, 0.2, (44, 40, 38), center=(0, 1.6, 3.2)))
    for i in range(7):                                                # blinds, streetlight
        _add(r, box(1.6, 0.06, 0.02, (110, 96, 70), center=(-1.6, 1.3 + i * 0.18, 3.08),
                   emissive=True))
    _flags(r, 1.6, 2.6)
    _add(r, box(1.0, 1.0, 0.04, (120, 96, 52), center=(0.2, 2.3, 3.08)))
    _add(r, box(0.6, 0.6, 0.03, (60, 46, 28), center=(0.2, 2.3, 3.05)))
    j = r.add_humanoid(_hum("vasile"), dict(_RADIO, head_y=12, lsh_r=60),
                       (0.0, 0.0, 1.5), _yaw_to((0, 0, 1.5), (1.2, 0, -3)), rifle_on=False)
    _handset(r, j)
    _add(r, box(2.2, 0.8, 0.9, (48, 34, 26), center=(0.0, 0.4, 0.75)))   # desk
    _add(r, box(2.3, 0.05, 1.0, (70, 52, 40), center=(0.0, 0.82, 0.75)))
    _add(r, box(0.06, 0.4, 0.06, (40, 38, 34), center=(-0.8, 1.05, 0.9)))
    _add(r, box(0.26, 0.14, 0.26, (255, 220, 160), center=(-0.8, 1.28, 0.9), emissive=True))
    _add(r, box(0.4, 0.08, 0.3, (24, 24, 26), center=(0.5, 0.88, 0.7)))   # phone base
    _add(r, box(0.5, 0.01, 0.34, (210, 206, 196), center=(-0.2, 0.85, 0.6)))
    r.flush(buf)
    _present(surface, buf, WIDTH // 2, WIDTH - WIDTH // 2)
    pygame.draw.line(surface, (70, 76, 86), (WIDTH // 2, SAFE_TOP), (WIDTH // 2, SAFE_BOT), 2)
    _rain_streaks_left = pygame.Surface((WIDTH // 2, HEIGHT), pygame.SRCALPHA)
    _rain_streaks(_rain_streaks_left, t, 91, n=40)
    surface.blit(_rain_streaks_left, (0, 0))
    _finish(surface, 6006, "WIRE // QUAY <-> GUARD HQ", _LIAISON)


# ── dispatch ──
M5_3D_SCENES = {
    "m5_tv_bulletin": _bulletin, "m5_safehouse_tv": _safehouse,
    "m5_retardovici_tv": _address, "m5_river_gate": _river,
    "m5_ucilev_scope": _scope, "m5_ucilev_reveal": _reveal,
    "m5_ucilev_leaves": _leaves, "m5_radio": _radio,
}


def draw_m5_scene_3d(scene, surface, t):
    """-> True if the 3D take was drawn, False to fall back to the 2D scene."""
    fn = M5_3D_SCENES.get(scene)
    if fn is None or not m5_3d_enabled():
        return False
    try:
        fn(surface, t)
        return True
    except Exception as e:  # any 3D failure -> permanent 2D fallback this run
        _cache["failed"], _cache["err"] = True, e
        print(f"m5martial3d: 3D cutscenes disabled, using 2D ({e!r})")
        return False


def draw_m5_tv_bulletin_3d(surface, t):
    return draw_m5_scene_3d("m5_tv_bulletin", surface, t)


def draw_m5_river_gate_3d(surface, t):
    return draw_m5_scene_3d("m5_river_gate", surface, t)
