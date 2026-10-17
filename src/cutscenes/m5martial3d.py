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
Renderers come from ``engine3d.Renderer`` (GL when moderngl + GL 3.3 exist,
silent SoftwareRenderer fallback; force with ACARISTAN_RENDERER) at 0.6x film
res with a smooth upscale. The production layers - practical-light sprites,
world-space rain, parallax night sky, handheld/shake camera - come from
cutscenes.m5fx3d; all non-scripted camera motion is zeroed under reduced motion.
The film lives inside SAFE_TOP..SAFE_BOT so the dialogue box never covers it.
"""
import math
import os

import pygame

from core.config import (HEIGHT, LETTER_H, WIDTH, font_terminal_small)
from cutscenes.m5martial import (SAFE_TOP, SAFE_BOT, _CREST, _GUARD_RED, _LIAISON,
                                 _RIVER, _SODIUM, _rain_streaks, _scanlines,
                                 _studio_backdrop, _tag)
from cutscenes.m3cell import _m3_noise
from cutscenes.m3ko import _ko_tint
from cutscenes.m5studio import ANCHOR_WARDROBE, BULLETIN_CAPTION, news_wall_tex
from core.outfits import OUTFIT_GUARD, biribel_3d, scene_outfit
from cutscenes import m5fx3d as _fx
from cutscenes import m5decal as _decal
from cutscenes import m5ending3d as _ending

# M5 Biribel rigs are keyed by outfit: ("biribel", outfit). Never use the bare
# "biribel" key in M5 - that is his KRAP kit and would leak into post-change shots.
_BIRI_GUARD = ("biribel", OUTFIT_GUARD)

__all__ = ["draw_m5_scene_3d", "draw_m5_tv_bulletin_3d", "draw_m5_river_gate_3d",
           "m5_3d_enabled", "M5_3D_SCENES"]

_FILM_H = SAFE_BOT - SAFE_TOP
_RES = 0.6
_RW, _RH = int(WIDTH * _RES), int(_FILM_H * _RES)
_LENS_RAD = _FILM_H // 2 - 2          # the optic fills the film height
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
        from engine3d import Renderer  # lazy: 2D fallback if the 3D stack breaks
        _cache["r"][key] = (Renderer(w, h), pygame.Surface((w, h)))
    return _cache["r"][key]


def _cam(r, t, eye, tgt, fov, hh=0.0, seed=0, roll=0.0, shk=None):
    """Camera with handheld drift / roll / shake (all off under reduced motion)."""
    return _fx.set_cam(r, t, eye, tgt, fov, hh=hh, seed=seed, roll=roll, shk=shk)


def _spr(r, pos, fn):
    # These screen-down sprites paint through nearby geometry. Floor sheen
    # and motivated fixture meshes replace them in the ending set.
    if fn.__qualname__.split('.')[0] in ('light_shaft','haze','wet_reflection'):
        return
    r.add_sprite(pos, fn, layer=_fx.FX_LAYER)


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
            fk.update(ANCHOR_WARDROBE)          # same man as the 2D fallback
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
        elif isinstance(key, tuple) and key[0] == "biribel":
            h = humanoid3d("biribel", **biribel_3d(key[1]))   # core.outfits kit
        else:
            h = humanoid3d(key)
        h = Humanoid(dict(h.spec, articulated_hands=True))
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
        s = font_terminal_small.render(_T("m5martial3d.live"), True, (230, 60, 50))
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


def _tag_left(surface, text, col):
    """Location slate pinned top-LEFT: the top-center tag sat on the actors'
    faces in every tight take of the standoff."""
    if not text:
        return
    surf = font_terminal_small.render(text, True, col)
    pad_x, pad_y = 10, 3
    plate = pygame.Surface((surf.get_width() + pad_x * 2, surf.get_height() + pad_y * 2),
                           pygame.SRCALPHA)
    plate.fill((4, 6, 10, 190))
    pygame.draw.rect(plate, (*col, 90), plate.get_rect(), 1)
    surface.blit(plate, (24, SAFE_TOP + 6))
    surface.blit(surf, (24 + pad_x, SAFE_TOP + 6 + pad_y))


def _finish(surface, seed, tag, col=(120, 200, 220), grade=True):
    if grade:
        _grade(surface)
    _m3_noise(surface, seed, count=20, alpha=12)
    _ko_tint(surface)
    _tag_left(surface, tag, col)


def _walk(ph, amp=1.0, rifle_p=80):
    s = math.sin(ph)
    return dict(spine=4, lhip_p=24 * s * amp, rhip_p=-24 * s * amp,
                lkn=10 + 26 * max(0.0, -math.cos(ph)) * amp,
                rkn=10 + 26 * max(0.0, math.cos(ph)) * amp,
                lift=0.03 * abs(s) * amp,
                lsh_p=-14 * s * amp + 6, rsh_p=14 * s * amp + 6, lel=20, rel=20,
                rifle_p=rifle_p)


# ── secondary life: every M5 actor breathes, shifts weight and blinks ──
def _life_pose(pose, t, amp=1.0, seed=0):
    """Authored pose + breathing/weight-shift/posture, added (never replacing)
    so a solved grip or an aimed rifle is never overwritten."""
    pose = dict(pose)
    for k, v in _ending.idle_pose(t, amp, seed).items():
        pose[k] = pose.get(k, 0) + v
    return pose


def _life(r, hum, pose, pos, yaw, t, seed=0, amp=1.0, rifle_on=False, blink=True):
    """add_humanoid + secondary animation. The rig has no idle system, and a
    perfectly still actor reads as a mannequin: breathing, a slow weight
    shift, posture settle (all far below the walk cycle), plus a blink when
    the head faces the lens. -> joints."""
    original = pose
    pose = _life_pose(pose, t, amp, seed)
    if rifle_on and amp and "rifle_p" in pose:
        # Torso breathing must not detach the support palm from its grip.
        from engine3d.core import m_apply, v_add
        _, joints, R, _ = hum.placements(pose)
        _, oldj, oldR, _ = hum.placements(original)
        delta = tuple(a-b for a,b in zip(oldj['lhand'], oldj['rhand']))
        sc = sum(oldR[i]**2 for i in (0, 3, 6))
        grip = tuple(sum(oldR[j*3+i]*delta[j] for j in range(3))/sc for i in range(3))
        pose = _ending.solve_hand(hum, pose, 'l', v_add(joints['rhand'], m_apply(R, grip)))
    j = r.add_humanoid(hum, pose, pos, yaw, rifle_on=rifle_on)
    _ending.draw_palms(r, hum, pose, pos, yaw)
    if blink:
        _ending.add_blink_lids(r, hum, pose, pos, yaw, _ending.blink_at(t, seed),
                               rifle_on=rifle_on)
    return j


def _wet(r, hum, pose, pos, yaw, t, seed=0, col=(138, 148, 162), amp=.5, idle=0.0):
    """Compatibility hook: character-attached glow sprites are forbidden."""
    return


def _cig(r, hum, pose, pos, yaw, t, seed=0):
    """The cigarette's life: the rig's ember is a static emissive box, so add
    the ember's glow (breathing with the smoke's pull) and the wisp itself.
    Anchor = the tip of the paper in face2-local coordinates."""
    from engine3d.core import m_apply, v_add  # lazy: see _rend
    if not hum.spec.get("cig"):
        return
    places, _j, root = hum.pose_world(pose, pos, yaw, rifle_on=False)
    hp = next((p for p in places if p[0] == 2), None)
    if hp is None:
        return
    M, neck = hp[2], hp[3]
    tip = v_add(v_add(neck, m_apply(M, (0.0585, 0.0412, 0.1933))), root)
    r.add_sprite(tip, _fx.cig_smoke(t, seed=seed + 9, intensity=.12), layer=_fx.FX_LAYER)


# ── shared sets ──
def _river_world(r, t, *, roof=True, door=0.0):
    """Quay, water, gate, sodium lamp, tunnel mouth and the far bank with
    Ucilev's roof (parapet + stair hut). Used by five shots."""
    from engine3d.core import box, quad_xz
    _add(r, quad_xz(-14, -8, 14, 2.6, 0.0, (28, 28, 34), seg=4))
    _add(r, box(28, 0.25, 0.3, (44, 44, 50), center=(0, 0.05, 2.75)))
    wcol = lambda x, z: (14, 22 + int(5 * math.sin(x * .7 + z * .5 + t * .003)), 36)
    _add(r, quad_xz(-40, 2.9, 90, 60, -0.6, (14, 22, 32), seg=8, colfn=wcol))
    _ending.bank(r, t, _add, _spr, _fx)
    _ending.quay_destination(r, t, _add, _spr, _fx)
    _ending.east_quay(r, t, _add, _spr, _fx)
    if roof:
        _ending.roof_set(r, t, _SNIPER, door, _add, _spr, _fx)
    _ending.wet_ground(r, t)
    # Tunnel mouth (left).
    _add(r, box(0.6, 3.4, 3.0, (38, 38, 44), center=(-6.0, 1.7, 0.5)))
    _add(r, box(3.0, 0.6, 3.0, (38, 38, 44), center=(-7.5, 3.4, 0.5)))
    _add(r, box(2.4, 2.8, 0.1, (8, 9, 12), center=(-7.5, 1.4, -0.9)))
    # River access gate ACROSS the eastbound quay, not standing in the river.
    # Masonry/fence ties it to the site. The leaf is already swung open east;
    # Maru passes through its opening on dry ground in every camera angle.
    for z in (-1.4, 2.5):
        _add(r, box(0.4, 3.25, 0.4, (48, 46, 44), center=(6.9, 1.625, z)))
        _add(r, box(0.5, 0.16, 0.5, (76, 72, 66), center=(6.9, 3.3, z)))
    _add(r, box(0.4, 2.5, 6.4, (48, 46, 44), center=(6.9, 1.25, -4.8)))
    for b in range(10):
        _add(r, box(0.06, 2.65, 0.06, (62, 66, 70),
                    center=(7.05 + b * 0.28, 1.38, -1.12)))
    for y in (0.3, 1.95, 2.75):
        _add(r, box(2.8, 0.07, 0.07, (62, 66, 70), center=(8.35, y, -1.12)))
    # Continuous riverside rail; keep the walkway clearly separate from water.
    for x in (-10, -6, -2, 2, 6, 10, 14):
        _add(r, box(0.06, 0.9, 0.06, (56, 58, 62), center=(x, 0.45, 2.48)))
    _add(r, box(24, 0.06, 0.06, (64, 66, 70), center=(2, 0.88, 2.48)))
    # Sodium lamp + reflection.
    _add(r, box(0.1, 4.4, 0.1, (38, 38, 44), center=(2.6, 2.2, 1.8)))
    _add(r, box(0.3, 0.22, 0.3, (255, 214, 150), center=(2.6, 4.45, 1.8), emissive=True))
    # Reflection supplies the practical spill; no square yellow 'carpet'.
    _spr(r, _LAMP, _fx.sodium_lamp(t, 1, radius_m=2.4))
    _spr(r, (2.6, 0.02, 1.7), _fx.wet_reflection(_fx.SODIUM, t, 1, 2.2, 0.55, 0.32))
    _spr(r, (2.6, -0.58, 3.2), _fx.wet_reflection(_fx.SODIUM, t, 2, 4.5, 0.8, 0.28))
    # The lamp actually lights its surroundings: a VOLUME of haze down the
    # shaft, a lit pool on the deck under it, and ground fog the shaft reads
    # against - a floating yellow sticker no longer passes for a street lamp.
    _add(r, quad_xz(0.9, 0.4, 4.3, 3.2, 0.006, (66, 52, 30), seg=2, emissive=True))
    _spr(r, _LAMP, _fx.light_shaft(_fx.SODIUM, 4.4, 0.55, 2.0, t, 1, intensity=0.30))
    _spr(r, (2.6, 0.10, 1.9), _fx.haze(_fx.SODIUM, 2.6, t, 1, intensity=0.13))
    _spr(r, (2.6, 0.60, 1.9), _fx.haze(_fx.SODIUM, 1.5, t, 2, intensity=0.07))
    _spr(r, (-7.5, 2.95, -1.12), _fx.light_shaft((110, 122, 146), 2.9, 0.35, 1.2, t, 4,
                                                  intensity=0.16))
    _add(r, box(0.14, 0.1, 0.14, (200, 210, 230), center=(-7.5, 2.98, -1.05), emissive=True))
    _spr(r, (-7.5, 2.95, -1.12), _fx.glow((110, 122, 146), 0.8, t, flicker=0.15, seed=4,
                                          intensity=0.55))           # tunnel caged bulb
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
    # cool moon/sky key (M2's tint); the warmth comes from the sodium practicals
    r.light = Light(direction=(0.4, 0.8, -0.35), ambient=0.53, diffuse=0.62,
                    tint=(0.96, 0.96, 1.03))   # cool, but skin must not go grey


_LAMP = (2.6, 4.45, 1.8)                       # the quay's sodium lamp head
_RIVER_LIGHTS = ((_LAMP, _fx.SODIUM), ((2.6, 1.0, 1.8), _fx.SODIUM))


def _river_sky(r, buf, t):
    _fx.night_sky(r, buf, t, (10, 13, 22), (34, 30, 34), stars=70, star_cut=0.55,
                  moon=(-38.0, 24.0), clouds=4, sodium=(44, 28, 14), seed=5)


def _flags(r, x, z, h=2.6):
    from engine3d.core import box
    _add(r, box(0.05, h, 0.05, (160, 148, 112), center=(x, h / 2, z)))
    _add(r, box(0.08, 0.08, 0.08, _CREST, center=(x, h + 0.04, z)))
    _add(r, box(0.75, 0.42, 0.03, (24, 34, 58), center=(x + 0.4, h - 0.3, z)))
    _add(r, box(0.75, 0.42, 0.03, (150, 30, 32), center=(x + 0.4, h - 0.72, z)))


# ── 1. bulletin ──
_ANCHOR_POS = (0.0, 0.0, 2.2)
_DESK_TOP = 1.05
# news wall: the opening in the centre flat is x -1.70..1.70, y 1.35..3.15;
# the texture plate is a hair larger so the bezel always covers its edge
_SCREEN_Q = ((-1.74, 3.19, 4.22), (1.74, 3.19, 4.22), (1.74, 1.31, 4.22), (-1.74, 1.31, 4.22))


def _slab(a, b, y0, h, d, col, emissive=False, seg=None):
    """A box of height ``h`` and thickness ``d`` standing on the floor-plan
    line a->b ((x, z) points), bottom at ``y0``: angled set flats, desk wings,
    floor cable. Handedness-safe: the yaw is checked against rot_y."""
    from engine3d.core import box, m_apply, rot_y  # lazy: see _rend
    dx, dz = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dz)
    yaw = math.degrees(math.atan2(-dz, dx))
    v = m_apply(rot_y(yaw), (1, 0, 0))
    if abs(v[0] * dx + v[2] * dz - ln) > 1e-3 * ln:
        yaw = -yaw
    m = box(ln, h, d, col, seg=seg, emissive=emissive)
    R = rot_y(yaw)
    mid = ((a[0] + b[0]) / 2, y0 + h / 2, (a[1] + b[1]) / 2)
    m.verts = [tuple(c + o for c, o in zip(m_apply(R, p), mid)) for p in m.verts]
    return m


def _anchor_pose(t):
    """Both palms flat on the desk either side of his script (arm IK solved
    once, cached), head level with a newsreader's small turns - no nodding."""
    base = _cache.get("anchor_pose")
    if base is None:
        from cutscenes.m5mid3d import _reach  # lazy: m5mid3d imports this module
        hum, pos = _hum("anchor"), _ANCHOR_POS
        base = dict(spine=7, head_p=0, lsh_p=30, lsh_r=12, lel=50, rsh_p=30, rsh_r=12, rel=50)
        _pl, j, _o = hum.pose_world(base, pos, 180.0, rifle_on=False)
        for side in ("r", "l"):
            x = 0.24 if j[side + "hand"][0] > pos[0] else -0.24
            base = _reach(hum, base, pos, 180.0, (x, _DESK_TOP + 0.05, 1.74), side)
        _cache["anchor_pose"] = base
    return dict(base, head_p=1.5 * math.sin(t * 0.0029),
                head_y=5.0 * math.sin(t * 0.0011 + 0.6) + 2.0 * math.sin(t * 0.0037))


def _studio_set(r, t):
    """Cheap 90s state-TV set: a centre flat holding the news wall, two
    angled flats with recessed light coves, the set ending at 3.2-3.6 m under
    a black void where the lamp truss hangs. Colour: one cold studio blue,
    gold + red only as accents, everything off-set falls to near-black."""
    from engine3d.core import box, quad_xz  # lazy: see _rend
    navy, flat, trim = (22, 28, 42), (22, 27, 41), (11, 13, 19)
    cove = (66, 98, 152)
    _add(r, quad_xz(-10, -8, 10, 6, 0.0, (13, 15, 21), seg=5))
    _add(r, quad_xz(-2.7, 0.15, 2.7, 1.15, 0.005, (24, 28, 38), emissive=True))  # key spill
    # centre flat, built around the news-wall opening (the wall graphic is
    # blitted into the frame first, so the anchor still paints over it)
    z = 4.35
    _add(r, box(4.8, 1.35, 0.2, navy, center=(0, 0.675, z), seg=1.2))
    _add(r, box(4.8, 0.45, 0.2, navy, center=(0, 3.375, z)))
    for s in (-1, 1):
        _add(r, box(0.7, 1.8, 0.2, navy, center=(s * 2.05, 2.25, z)))
        _dec(r, box(0.07, 1.94, 0.04, trim, center=(s * 1.72, 2.25, 4.21)), 0.4)    # bezel
    for y in (1.33, 3.17):
        _dec(r, box(3.5, 0.07, 0.04, trim, center=(0, y, 4.21)), 0.4)
    _add(r, box(4.95, 0.12, 0.34, trim, center=(0, 3.66, z)))                       # header
    _dec(r, box(4.8, 0.022, 0.02, (150, 124, 72), center=(0, 1.16, 4.24)), 0.5)       # gold rule
    _dec(r, box(4.6, 0.035, 0.02, (40, 58, 92), center=(0, 0.32, 4.24), emissive=True), 0.5)
    # angled flats, each with two light coves at uneven spacing
    for s in (-1, 1):
        a, b = (s * 2.45, 4.32), (s * 4.75, 2.95)
        _add(r, _slab(a, b, 0.0, 3.2, 0.16, flat, seg=1.1))
        _add(r, _slab(a, b, 3.2, 0.1, 0.3, trim))
        dx, dz = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dz)
        n = (dz / ln, -dx / ln)
        if n[1] > 0:                                     # face the studio, not the void
            n = (-n[0], -n[1])
        for f in ((0.27, 0.66) if s < 0 else (0.33, 0.71)):
            px, pz = a[0] + dx * f + n[0] * 0.1, a[1] + dz * f + n[1] * 0.1
            ux, uz = dx / ln * 0.03, dz / ln * 0.03
            _add(r, _slab((px - ux, pz - uz), (px + ux, pz + uz), 0.3, 2.6, 0.025, cove,
                          emissive=True))
    # lamp truss in the void: irregular fixtures, one dark (a real rig)
    _add(r, box(10.0, 0.07, 0.07, (36, 37, 42), center=(0, 4.55, 2.4)))
    _add(r, box(10.0, 0.07, 0.07, (36, 37, 42), center=(0, 4.55, 0.3)))
    for x, zz, lit in ((-3.4, 2.4, True), (-1.1, 0.3, True), (0.5, 2.4, False),
                       (1.3, 0.3, True), (3.0, 2.4, True)):
        _add(r, box(0.24, 0.3, 0.3, (27, 28, 32), center=(x, 4.3, zz)))
        _add(r, box(0.17, 0.04, 0.17, (250, 232, 198) if lit else (40, 40, 44),
                    center=(x, 4.13, zz), emissive=lit))
    # one hanging state flag, left: four fold strips, alternate shade + depth
    fx, fz = -3.0, 3.35
    _add(r, box(0.045, 2.75, 0.045, (150, 140, 108), center=(fx, 1.375, fz)))
    _add(r, box(0.08, 0.06, 0.08, _CREST, center=(fx, 2.78, fz)))
    _add(r, box(0.7, 0.03, 0.03, (150, 140, 108), center=(fx + 0.36, 2.62, fz)))
    for i in range(4):
        sh = 1.0 - 0.14 * (i % 2)
        cx, cz = fx + 0.11 + i * 0.16, fz + (0.035 if i % 2 else -0.01)
        _add(r, box(0.16, 0.56, 0.02, tuple(int(c * sh) for c in (26, 36, 62)),
                    center=(cx, 2.32, cz)))
        _add(r, box(0.16, 0.56, 0.02, tuple(int(c * sh) for c in (150, 30, 32)),
                    center=(cx, 1.76, cz)))
    # desk: centre block + two angled wings, lit front strip, station badge
    body, top = (24, 28, 40), (60, 58, 62)
    _add(r, box(2.4, 1.0, 0.7, body, center=(0, 0.5, 1.55)))
    _add(r, box(2.5, 0.05, 0.8, top, center=(0, _DESK_TOP - 0.025, 1.55)))
    for s in (-1, 1):
        a, b = (s * 1.18, 1.52), (s * 2.0, 1.98)
        _add(r, _slab(a, b, 0.0, 1.0, 0.66, body))
        _add(r, _slab(a, b, 1.0, 0.05, 0.76, top))
    _dec(r, box(2.4, 0.018, 0.02, (90, 112, 152), center=(0, 0.965, 1.19), emissive=True), 0.3)
    _dec(r, box(1.3, 0.2, 0.02, (150, 30, 32), center=(0, 0.76, 1.19), emissive=True), 0.3)
    _dec(r, box(1.3, 0.014, 0.02, (170, 140, 80), center=(0, 0.63, 1.19)), 0.3)
    _add(r, box(0.46, 0.008, 0.3, (226, 224, 216), center=(0.0, _DESK_TOP + 0.004, 1.66)))
    _add(r, box(0.08, 0.1, 0.08, (176, 176, 170), center=(0.92, 1.1, 1.48)))      # mug
    # the studio's floor camera, foreground left, cable run to the desk
    cx, cz = -3.35, -3.75             # just inside frame-left at the start of the push
    _add(r, box(0.7, 0.12, 0.7, (26, 27, 30), center=(cx, 0.06, cz)))
    _add(r, box(0.1, 1.28, 0.1, (44, 46, 50), center=(cx, 0.76, cz)))
    _add(r, box(0.36, 0.34, 0.6, (30, 32, 36), center=(cx, 1.55, cz + 0.05)))
    _add(r, box(0.17, 0.17, 0.22, (14, 14, 16), center=(cx, 1.55, cz + 0.45)))
    _add(r, box(0.22, 0.16, 0.18, (36, 38, 42), center=(cx + 0.03, 1.8, cz - 0.17)))
    _add(r, box(0.05, 0.03, 0.03, (230, 40, 36), center=(cx, 1.74, cz + 0.3), emissive=True))
    _add(r, _slab((cx, cz), (-2.4, -1.4), 0.0, 0.02, 0.035, (8, 8, 10)))
    _add(r, _slab((-2.4, -1.4), (-1.5, 1.05), 0.0, 0.02, 0.035, (8, 8, 10)))
    # practicals: the floor camera's tally, the lit truss lamps, the news wall's
    # cool spill, the coves, and dust hanging in the anchor's key light
    _spr(r, (cx, 1.74, cz + 0.32), _fx.glow((255, 40, 30), 0.35, t, pulse=0.15,
                                            core=(255, 170, 150)))
    for x, zz in ((-3.4, 2.4), (-1.1, 0.3), (1.3, 0.3), (3.0, 2.4)):
        _spr(r, (x, 4.1, zz), _fx.glow((255, 226, 180), 0.7, core=(255, 246, 226), intensity=0.7))
        _spr(r, (x, 4.02, zz), _fx.light_shaft((255, 226, 180), 2.5, 0.22, 0.95, t, x, intensity=0.15))
    _spr(r, (0.0, 2.25, 4.15), _fx.crt_bloom(t, (60, 90, 150), 1.9, 1.0, 0.35, seed=2))
    for s in (-1, 1):
        _spr(r, (s * 3.5, 1.6, 3.55), _fx.window_glow((40, 62, 110), 0.25, 1.4, 0.45))
    _spr(r, (0.0, 2.3, 1.4), _fx.dust_motes(t, 11, 30, (1.5, 1.1), (110, 106, 96)))


def _bulletin(surface, t):
    """State TV, 21:58: a studio-floor camera push from the wide, past the
    floor camera (it leaves frame by the move), into the on-air medium shot
    with the news wall behind the anchor's head."""
    from engine3d.core import Light, v_lerp, lerp  # lazy: see _rend
    r, buf = _rend()
    r.fog, r.fog_start, r.fog_end = (6, 7, 11), 9.0, 26.0
    r.light = Light(direction=(0.42, 0.62, -0.66), ambient=0.3, diffuse=1.0,
                    tint=(0.94, 0.98, 1.08))
    k = _k(t, 0, 5600)
    cam = v_lerp((-3.3, 2.25, -5.4), (-0.6, 1.78, -2.3), k)
    tgt = v_lerp((0.25, 1.45, 2.6), (0.05, 1.78, 2.4), k)
    _cam(r, t, cam, tgt, lerp(54, 37, k), hh=0.012, seed=1)
    buf.blit(_sky(_RW, _RH, (4, 5, 8), (8, 10, 15)), (0, 0))
    _tv_feed_quad(r, buf, news_wall_tex(), _SCREEN_Q, strips=48, glow=False)
    r.begin()
    _studio_set(r, t)
    _life(r, _hum("anchor"), _anchor_pose(t), _ANCHOR_POS, 180.0, t, seed=7, amp=0.55)
    r.flush(buf)
    surface.fill((0, 0, 0))
    _present(surface, buf)
    _grade(surface, gamma=0.82, vig=0.62)       # set edges fall off into the dark
    _chyron(surface, t, BULLETIN_CAPTION, (220, 90, 70))
    _live(surface, t)
    _finish(surface, 5151, "STATE TELEVISION // 21:58", grade=False)


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


def _tv_feed_quad(r, buf, feed, quad, strips=40, glow=True):
    """Map ``feed`` onto a world-space quad (TL, TR, BR, BL) after flush:
    perspective-correct per vertical strip (each strip's ends are projected
    from 3D), plus a soft additive phosphor bloom around the glass.
    ``glow=False``: no bloom (used BEFORE flush as a backplate)."""
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
    if not glow:
        return
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
    r.light = Light(direction=(-0.4, 0.8, -0.3), ambient=0.36, diffuse=0.8,
                    tint=(1.16, 0.98, 0.8))                    # bare bulb, warm
    k = _k(t, 0, 7000)
    _cam(r, t, v_lerp((-2.9, 1.7, -1.6), (-2.3, 1.62, -0.9), k),
         (1.0, 1.15, 2.7), lerp(60, 52, k), hh=0.015, seed=2)
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
    _spr(r, (1.4, 2.32, 1.6), _fx.glow((255, 196, 130), 0.9, t, flicker=0.05, seed=3,
                                       core=(255, 238, 200), intensity=0.75))   # bare bulb
    _spr(r, (-0.6, 1.8, 4.2), _fx.window_glow((34, 46, 70), 1.3, 1.0, 0.55))      # rain window
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
    # screen spill: stepped falloff (N09) instead of one flat blue slab
    for (sx, sz, sy, scol) in ((0.9, -1.9, 0.011, (40, 33, 30)),
                               (0.62, -1.35, 0.012, (44, 39, 40)),
                               (0.38, -0.85, 0.013, (50, 47, 52))):
        # floor-brown tinted towards the screen blue: reads as light, not a rug
        _tv(quad_xz(-sx, sz, sx, -0.36, sy, scol, emissive=True))
    _tv(box(0.24, 0.02, 0.14, (30, 30, 34), center=(0, 1.25, 0.06)))          # antenna foot
    _add(r, box(0.9, 0.05, 0.6, (60, 44, 32), center=(-1.6, 0.72, 0.6)))      # table + mug
    for lx, lz in ((-1.95, 0.4), (-1.25, 0.4), (-1.95, 0.8), (-1.25, 0.8)):
        _add(r, box(0.05, 0.7, 0.05, (44, 32, 24), center=(lx, 0.35, lz)))
    _add(r, box(0.08, 0.1, 0.08, (180, 170, 150), center=(-1.5, 0.8, 0.6)))
    _add(r, box(0.36, 0.02, 0.26, (200, 196, 186), center=(-1.8, 0.76, 0.6)))
    if not _decal.add(r, "calendar", 0, (3.2, 1.9, 4.06), (0.6, 0.8)):          # calendar
        _dec(r, box(0.6, 0.8, 0.03, (120, 104, 80), center=(3.2, 1.9, 4.08)), 0.8)
        _dec(r, box(0.5, 0.2, 0.03, (170, 40, 36), center=(3.2, 2.2, 4.06)), 1.0)
    bpos = (-0.3, 0.0, 1.7)
    _life(r, _hum(("biribel", scene_outfit("m5_safehouse_tv"))),
          dict(head_p=4 + math.sin(t * 0.0015) * 3, lsh_p=-6, lsh_r=10, lel=40,
               rsh_p=-6, rsh_r=10, rel=40),
          bpos, _yaw_to(bpos, (2.4, 0, 2.6)), t, seed=8, amp=0.7)
    _spr(r, (1.4, 2.0, 1.6), _fx.light_shaft((255, 196, 130), 2.0, 0.20, 0.9, t, 3,
                                              intensity=0.18))
    _spr(r, (1.4, 1.1, 1.6), _fx.haze((255, 196, 130), 1.2, t, 3, intensity=0.10))
    for sx_ in (-1, 1):                                       # rabbit-ear antenna
        r.add_line3d(_w((0, 1.26, 0.06)), _w((sx_ * 0.32, 1.72, 0.14)), (120, 122, 130), 1)
    _spr(r, _w((-0.08, 0.95, -0.36)), _fx.crt_bloom(t, (90, 130, 200), 0.56, 0.42, 0.75, seed=4))
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
    # a hard top spot on the podium; the hall falls away into the dark
    r.light = Light(direction=(0.1, 0.95, -0.3), ambient=0.3, diffuse=0.95,
                    tint=(1.08, 1.0, 0.9))
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
    # presidential seal (art.m5.presidential_crest): gold parts self-lit in the spot
    # (centre 2.9 / 1.15 m, a halo behind his head: at 3.7 the seal sat above
    # the push-in frame and only its rim showed)
    if not _decal.add(r, "presidential_crest", 0, (0, 2.9, 4.83), (1.15, 1.15), emissive=110):
        _dec(r, box(1.6, 1.6, 0.06, (150, 120, 62), center=(0, 3.7, 4.86), emissive=True), 0.8)
        _dec(r, box(1.1, 1.1, 0.04, (120, 92, 44), center=(0, 3.7, 4.82)), 1.0)
    for dx in (-3.6, -0.9, 0.9, 3.6):                        # state drapes
        _dec(r, box(0.8, 5.2, 0.04, (96, 22, 26), center=(dx, 3.4, 4.88)), 0.6)
        _dec(r, box(0.8, 0.12, 0.03, (160, 130, 64), center=(dx, 1.0, 4.85), emissive=True), 0.8)
    _dec(r, box(14, 0.08, 0.03, (150, 130, 80), center=(0, 6.2, 4.88), emissive=True), 0.6)
    # Lectern grip: both hands land on the podium top (shoulder ~30 deg fwd, elbow
    # ~70 deg) and the right hand lifts off in eased, rolled-out beats. The old
    # fists-up pose foreshortened the upper arms to nothing from this camera, so
    # the forearms read as floating stumps.
    beat = max(0.0, math.sin(t * .0021 - 0.6))
    g = beat * beat * (3 - 2 * beat)                       # smoothstep: hold, rise, settle
    _life(r, _hum("president"),
          dict(spine=6 + 3 * g, head_p=math.sin(t * .005) * 3 - 4 * g,
               head_y=math.sin(t * .0011) * 10,
               lsh_p=30, lsh_r=8, lel=70,
               rsh_p=30 + 24 * g, rsh_r=10 + 16 * g, rel=70 - 8 * g),
          (0.0, 0.35, 2.4), 180.0, t, seed=9, amp=0.5)
    _add(r, box(1.2, 1.25, 0.7, (26, 30, 44), center=(0, 0.97, 1.7)))  # podium
    _add(r, box(0.42, 0.42, 0.02, (150, 120, 62), center=(0, 1.05, 1.34), emissive=True))
    _add(r, box(0.26, 0.26, 0.02, (70, 52, 30), center=(0, 1.05, 1.32)))
    _spr(r, (0.0, 2.9, 4.78), _fx.window_glow((90, 70, 30), 0.9, 0.9, 0.5))        # crest catches the spot
    _spr(r, (0.0, 6.6, 1.9), _fx.glow((255, 238, 200), 0.9, core=(255, 250, 236), intensity=0.6))
    _spr(r, (0.0, 6.35, 1.9), _fx.light_shaft((255, 238, 200), 3.5, 0.45, 1.7, t, 5,
                                               intensity=0.13))
    _spr(r, (0.0, 3.4, 2.0), _fx.haze((255, 238, 200), 1.5, t, 5, intensity=0.08))
    _spr(r, (0.0, 2.6, 2.0), _fx.dust_motes(t, 23, 36, (1.0, 1.8), (120, 114, 100)))
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
def _soften(s):
    w, h = s.get_size()
    sm = pygame.transform.smoothscale
    s.blit(sm(sm(s, (max(2, w // 3), max(2, h // 3))), (w, h)), (0, 0))


def _flush_rack(r, buf, t, near, t0, dur=900, far=40.0):
    """Close-up flush with a rack focus: the cut lands with the set sharp,
    then focus pulls to ``near`` m and everything past it softens
    (flush_split, both backends). Reduced motion: focus already settled."""
    k = 1.0 if _fx.reduced_motion() else _k(t, t0, dur)
    r.flush_split(buf, far + (near - far) * k, _soften)


def _river(surface, t):
    """Four beats of coverage: OTS wide, tracking medium, threshold silhouette,
    lit reverse on Biribel as the dot lands. No beat is an empty frame."""
    from engine3d.core import v_lerp, lerp, Light
    r, buf = _rend()
    t = max(0, min(t, 9600))
    _night(r)
    dk = _k(t, 7400, 900) if not _cache["qa_no_marks"] else 0.0
    mpos, distance = _ending.maru_block(t)
    walk_weight = _ending.maru_move_weight(t)
    wounded_walk = dict(_ending.stride(distance, .62 * walk_weight), lsh_p=30, lel=95,
                        rsh_p=9, rel=16, body_r=1.6)
    face_gate = _yaw_to(_BIRIBEL, (6.9, 0, 0.6))
    face_bank = _yaw_to(_BIRIBEL, _SNIPER)
    turn = _k(t, 6800, 1400)
    if t < 2200:        # A: over Biribel's shoulder - lamp, gate, lit doorway,
        k = _k(t, 0, 2200)   # Maru a dark shape walking into the light.
        _cam(r, t, v_lerp((-2.3, 1.66, 0.15), (-2.1, 1.62, 0.25), k),
             (7.5, 1.15, -0.9), 58, hh=0.012, seed=3)
    elif t < 5400:      # B: tracking medium on Maru's back, through his turn
        yaw = math.radians(_ending.maru_yaw(t))
        fwd = (math.sin(yaw), 0.0, math.cos(yaw))
        back = (-fwd[0], 0.0, -fwd[2])
        right = (fwd[2], 0.0, -fwd[0])
        eye = (mpos[0] + back[0] * 3.05 + right[0] * 0.85, 1.78,
               mpos[2] + back[2] * 3.05 + right[2] * 0.85)
        tgt = (mpos[0] + fwd[0] * 2.2, 1.28, mpos[2] + fwd[2] * 2.2)
        _cam(r, t, eye, tgt, 46, hh=0.014, seed=3)
    elif t < 6600:      # C: threshold from inside - he crosses the light pool
        k = _k(t, 5400, 1200)
        _cam(r, t, v_lerp((10.3, 1.78, -6.25), (10.3, 1.76, -6.15), k),
             (10.3, 1.48, -2.6), 58, hh=0.006, seed=4)
    else:               # D: waist-up reverse on Biribel; the lamp keys his face
        k = _k(t, 6600, 3000)
        _cam(r, t, v_lerp((1.65, 1.86, 3.7), (1.50, 1.80, 3.5), k),
             (0.0, 1.52, 0.4), lerp(50, 48, k), hh=0.006, seed=4,
             roll=0.5 * dk)
        r.light = Light(direction=(0.62, 0.66, 0.34), ambient=0.52, diffuse=0.95,
                        tint=(1.12, 0.94, 0.72))
    _river_sky(r, buf, t)
    r.begin()
    _river_world(r, t)
    _fx.rain3d(r, t, 77, n_near=26, n_far=70, lights=_RIVER_LIGHTS,
               near_d0=3.0, near_ln=.26, surface=_ending.rain_surface)
    if dk > 0:        # the optic catches the lamp on the far roof as the dot lands
        g = dk * (0.6 + 0.4 * math.sin(t * 0.01))
        _spr(r, (_SNIPER[0] + 0.3, _SNIPER[1] + 1.45, _SNIPER[2] - 0.5), _fx.scope_glint(g))
    # A short eased palm contact on the entrance jamb supports the wounded
    # turn. Reach is solved after torso participation, with a delayed wrist.
    mh = _hum("maru")
    reach = _ending.beat(t, 3820, 420) * (1 - _ending.beat(t, 4380, 420))
    mp = _life_pose(wounded_walk, t, .35, 1)
    if reach > 0:
        mp = _ending.door_reach(mh, mp, mpos, _ending.maru_yaw(t),
                                (10.94, 1.35, -1.12), reach)
    j = _life(r, mh, mp, mpos, _ending.maru_yaw(t), t, seed=1, amp=0)
    turn_yaw = lerp(face_gate, face_bank, turn)
    biri = dict(head_p=-4 * turn)
    _life(r, _hum(_BIRI_GUARD), biri, _BIRIBEL, turn_yaw, t, seed=2, amp=0.8)
    _wet(r, _hum(_BIRI_GUARD), biri, _BIRIBEL, turn_yaw, t, seed=2, amp=0.5, idle=0.8)
    if not _cache["qa_no_marks"]:
        hum = _hum("ucilev")
        aim = _ending.rifle_pose(hum, _ending.AIM_PITCH, t=t)
        _life(r, hum, aim, _SNIPER, _yaw_to(_SNIPER, _BIRIBEL), t, seed=3, amp=0.5, rifle_on=True)
        _wet(r, hum, aim, _SNIPER, _yaw_to(_SNIPER, _BIRIBEL), t, seed=3, amp=0.4, idle=0.5)
    chest = j.get("chest") or j.get("spine") or j.get("pelvis")
    aim = None
    if dk > 0 and chest:
        drift = (1 - dk) * 0.5
        # centre vest, BELOW the radio pouch - on the pouch the beat vanished
        aim = (chest[0] + drift, chest[1] + 0.12 + drift * 0.4, chest[2] + 0.02)
        # Only the contact dot is visible in rain, not a solid red beam.
    r.flush(buf)
    surface.fill((0, 0, 0))
    _present(surface, buf)
    p = r.project(aim) if aim else None
    if p:
        cx, cy = _film_xy(p)
        pulse = 0.7 + 0.3 * math.sin(t * 0.012)
        halo = pygame.Surface((52, 52), pygame.SRCALPHA)
        pygame.draw.circle(halo, (255, 40, 30, int(50 * dk * pulse)), (26, 26), 10)
        surface.blit(halo, (cx - 26, cy - 26))
        pygame.draw.circle(surface, (255, 50, 36), (cx, cy), 4)
    _finish(surface, 2202, "RIVER GATE // EAST CHANNEL", _RIVER)


# ── 5. the scope (crosshair POV) ──
def _scope(surface, t):
    """POV through the optic: the lens fills the film height, hood and housing
    replace the black void, and etched data never crosses the target's face.

    The hold is tuned for a 240 m lane: a slow wander (the position creeping
    off and being walked back), the breath cycle, and a tremor. The reticle
    barely moves - it is etched on the glass and rides WITH the tube - while
    the IMAGE drifts several times further, magnified, which is what makes a
    long shot read as long instead of a screenshot under a circle."""
    from engine3d.core import lerp
    r, buf = _rend()
    t = max(0, min(t, 9200))
    _night(r)
    settle = _k(t, 1200, 2400)
    breath = 0.0 if _fx.reduced_motion() else 1.0     # breath sway is motion, not story
    wander = (1.0 - 0.65 * settle)                     # the hold settles as he commits
    sway_x = breath * wander * (math.sin(t * 0.00042) * 0.55
                                 + math.sin(t * 0.00017 + 1.3) * 0.34)
    sway_y = breath * wander * (math.sin(t * 0.00031 + 0.7) * 0.30
                                 + math.sin(t * 0.00053) * 0.17)
    sway_x += breath * (1.0 - settle) * math.sin(t * 0.0021) * 0.10
    sway_y += breath * (1.0 - settle) * math.cos(t * 0.0017) * 0.08
    tremor = breath * 0.012 * (math.sin(t * 0.0131) + math.sin(t * 0.0071 + 2.0) * 0.8)
    eye = (_SNIPER[0] + 0.15, _SNIPER[1] + 1.25, _SNIPER[2] - 0.6)
    tgt = (_BIRIBEL[0] + sway_x + tremor, 1.38 + sway_y, _BIRIBEL[2] + tremor * 0.5)
    r.set_camera(eye, tgt, lerp(9.0, 5.5, _k(t, 0, 3000)))
    _river_sky(r, buf, t)
    r.begin()
    _river_world(r, t, roof=False)
    # Body three-quarter to the lens, head turned back towards it: a person,
    # not a symmetrical target dummy.
    biri = dict(head_y=math.sin(t * .0009) * 8 - 6, head_p=-2)
    yaw_b = _yaw_to(_BIRIBEL, (_SNIPER[0], 0, _SNIPER[2])) - 24
    _life(r, _hum(_BIRI_GUARD), biri, _BIRIBEL, yaw_b, t, seed=1, amp=0.8)
    _wet(r, _hum(_BIRI_GUARD), biri, _BIRIBEL, yaw_b, t, seed=1, amp=0.35, idle=0.8)
    r.flush(buf)
    surface.fill((0, 0, 0))
    _present(surface, buf)
    if not _cache["qa_no_marks"]:
        # The image drifts through the glass; the reticle only rides the tube.
        _reticle(surface, t, sway=(tremor * 26.0, tremor * 20.0))
        p = r.project(_LAMP)
        if p:                      # sodium flare on the glass once settled
            cx, cy = _film_xy(p)
            flare = pygame.Surface((150, 26), pygame.SRCALPHA)
            a = int(70 * settle)
            pygame.draw.ellipse(flare, (255, 214, 150, a), (0, 9, 150, 8))
            pygame.draw.circle(flare, (255, 226, 180, min(90, a + 25)), (75, 13), 7)
            surface.blit(flare, (cx - 75, cy - 13), special_flags=pygame.BLEND_ADD)
        _optic_ring(surface)
        _optic_hood(surface)
    _rain_streaks(surface, t, 12, n=22)   # POV through glass: drops, not wires
    _m3_noise(surface, 8808, count=50, alpha=14)
    _ko_tint(surface)
    _tag_left(surface, "OPTIC // FAR BANK", _GUARD_RED)


def _reticle(surface, t, sway=(0.0, 0.0)):
    """Round optic over the film: black outside the glass, vignette ring,
    duplex crosshair with mil dots, lit centre dot, etched range data.

    ``sway`` is the TUBE's own motion (px) - a few pixels at most: the glass
    rides the scope, while the magnified image behind it drifts far more."""
    cx, cy = WIDTH // 2 + int(sway[0]), SAFE_TOP + _FILM_H // 2 + int(sway[1])
    rad = _LENS_RAD
    mask = _RING.get("mask")
    if mask is None:                                     # cached: was rebuilt every frame
        mask = pygame.Surface((WIDTH, _FILM_H), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 255))
        pygame.draw.circle(mask, (0, 0, 0, 0), (cx, _FILM_H // 2), rad)
        for i in range(14):
            pygame.draw.circle(mask, (0, 0, 0, 200 - i * 14), (cx, _FILM_H // 2), rad - i, 1)
        _RING["mask"] = mask
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
    # Etched data on the LOWER stadia only - across the target's chest/face
    # it read as subtitles printed on Biribel.
    etched, dim = (150, 165, 175), (120, 135, 145)
    labels = _RING.get("labels")
    if labels is None:
        labels = _RING["labels"] = [font_terminal_small.render(s, True, c) for s, c in (
            ("RNG 240m", dim), ("WIND L2", dim), ("Y-3 INTAKE", etched), ("MATCH", etched))]
    ly = cy + int(rad * 0.42)
    for img, x, above in ((labels[0], cx - 96 - labels[0].get_width(), True),
                          (labels[1], cx - 96 - labels[1].get_width(), False),
                          (labels[2], cx + 96, True), (labels[3], cx + 96, False)):
        surface.blit(img, (x, ly - img.get_height() - 4 if above else ly + 4))


_RING = {}


def _optic_hood(surface):
    """Eyelash vignette + optic housing shoulders: the glass sits inside a
    tube, not a small circle floating in a black void."""
    hood = _RING.get("hood")
    if hood is None:
        hood = pygame.Surface((WIDTH, _FILM_H), pygame.SRCALPHA)
        cx, cy = WIDTH // 2, _FILM_H // 2
        rad = _LENS_RAD
        for i in range(30):
            f = i / 29.0
            a = int(225 * f ** 1.7)
            pygame.draw.circle(hood, (12, 10, 9, a), (cx, cy), rad + 30 - i, 1)
        pygame.draw.ellipse(hood, (14, 13, 12, 235),
                            (cx - rad - 80, cy + rad - 34, 2 * rad + 160, 190))
        pygame.draw.ellipse(hood, (14, 13, 12, 235),
                            (cx - rad - 80, cy - rad - 156, 2 * rad + 160, 190))
        _RING["hood"] = hood
    surface.blit(hood, (0, SAFE_TOP))


def _optic_ring(surface):
    """Faint chromatic fringe on the inside edge of the glass (cached)."""
    ring = _RING.get("r")
    if ring is None:
        rad = _LENS_RAD
        ring = pygame.Surface((WIDTH, _FILM_H))
        ring.fill((0, 0, 0))
        cx, cy = WIDTH // 2, _FILM_H // 2
        for i, col in enumerate(((26, 6, 4), (18, 10, 4), (4, 10, 22), (2, 6, 16))):
            pygame.draw.circle(ring, col, (cx + (i - 1.5) * 0.8, cy), rad - 14 - i * 2, 3)
        _RING["r"] = ring
    surface.blit(ring, (0, SAFE_TOP), special_flags=pygame.BLEND_ADD)


# ── 6. reveal ──
def _reveal(surface, t):
    """Continuous stabilized medium coverage: no throat insert or lens jump."""
    from engine3d.core import v_lerp, lerp
    r, buf = _rend()
    t = max(0, min(t, 8400))
    _night(r)
    sx, sy, sz = _SNIPER
    k = _ending.beat(t, 600, 5400)
    _cam(r, t, v_lerp((sx + 2.6, sy + 1.85, sz - 3.6),
                      (sx + 2.3, sy + 1.85, sz - 3.2), k),
         (sx, sy + 1.48, sz + .05), lerp(46, 44, k), hh=.004, seed=6)
    _river_sky(r, buf, t)
    r.begin()
    _river_world(r, t)
    _fx.rain3d(r, t, 33, n_near=18, n_far=70, ground=sy,
               near_d0=3.0, near_ln=.24, surface=_ending.rain_surface)
    hum = _hum("ucilev")
    pose = _ending.reveal_pose(hum, t)
    yaw_u = _yaw_to(_SNIPER, _BIRIBEL) + 10 * _k(t, 900, 2200)
    _life(r, hum, pose, _SNIPER, yaw_u, t, seed=3, amp=.65, rifle_on=True)
    r.flush(buf)
    surface.fill((0, 0, 0))
    _present(surface, buf)
    _finish(surface, 4411, "UCILEV NADGOB IERDNA // LISTED DEAD", _GUARD_RED)


# ── 7. he leaves ──
def _leaves(surface, t):
    """Follow to the handle, then cut to black BEFORE any stair descent."""
    from engine3d.core import v_lerp
    surface.fill((0, 0, 0))
    if t >= 3550:
        return
    r, buf = _rend()
    _night(r)
    sx, sy, sz = _SNIPER
    initial_yaw = _yaw_to(_SNIPER, _BIRIBEL) + 10
    pos, yaw, distance, reaching = _ending.ucilev_block(t, _SNIPER, initial_yaw)
    # One uninterrupted side/back track; never crosses the hut or actor.
    k = _ending.travel(t, 650, 2650)
    eye = v_lerp((sx + 3.6, sy + 2.3, sz - 4.2),
                 (sx + 2.1, sy + 2.1, sz + 1.0), k)
    _cam(r, t, eye, (pos[0], sy + 1.36, pos[2] + .25), 52, hh=.004, seed=8)
    _river_sky(r, buf, t)
    r.begin()
    _river_world(r, t, door=0.0)
    _fx.rain3d(r, t, 55, n_near=16, n_far=55, ground=sy,
               near_d0=3.0, near_ln=.24, surface=_ending.rain_surface)
    hum = _hum("ucilev")
    moving = _ending.move_weight(t, 650, 2650)
    pose = _life_pose(_ending.patrol_carry(hum, distance, moving), t, .35, 2)
    if reaching > 0:
        pose = _ending.door_reach(hum, pose, pos, yaw,
             _ending.door_handle(sx, sy, sz + _ending.ROOF_DOOR_Z, 0), reaching)
    _life(r, hum, pose, pos, yaw, t, seed=2, amp=0, rifle_on=True)
    _ending.rifle_sling(r, hum, pose, pos, yaw)
    r.flush(buf)
    _present(surface, buf)
    _finish(surface, 4412, "EAST CHANNEL // HE DOESN'T TURN", _RIVER)


# ── 8. radio (split) ──
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
    r.light = Light(direction=(0.62, 0.66, 0.34), ambient=0.52, diffuse=0.95,
                    tint=(1.12, 0.94, 0.72))      # the gate lamp keys his face
    # Reverse side matches the preceding quay shot: the warehouse remains
    # behind Biribel instead of cutting to an unrelated bare river skyline.
    _cam(r, t, (1.15, 1.66, 2.6 - k * 0.26), (0.05, 1.50, 0.4), lerp(40, 35, k), hh=0.02, seed=9)
    _river_sky(r, buf, t)
    r.begin()
    _river_world(r, t)
    _fx.rain3d(r, t, 91, n_near=50, n_far=70, lights=_RIVER_LIGHTS, surface=_ending.rain_surface)
    hum = _hum(_BIRI_GUARD)
    pose = _ending.radio_pose(hum, _life_pose(_RADIO, t, .7, 4))
    yaw_b = _yaw_to(_BIRIBEL, _SNIPER)
    _life(r, hum, pose, _BIRIBEL, yaw_b, t, seed=4, amp=0)
    _ending.draw_handset(r, hum, pose, _BIRIBEL, yaw_b, t,
                         base=(_BIRIBEL[0] - 0.10, 0.95, _BIRIBEL[2] + 0.42))
    _wet(r, hum, pose, _BIRIBEL, yaw_b, t, seed=4, amp=0.55, idle=0.7)
    r.flush(buf)
    surface.fill((0, 0, 0))
    _present(surface, buf, 0, WIDTH // 2)
    # RIGHT - Vasile's office: desk, flag, desk lamp, blinds. No rain.
    r, buf = _rend(hw, _RH)
    r.fog, r.fog_start, r.fog_end = (12, 11, 10), 8.0, 24.0
    r.light = Light(direction=(-0.5, 0.7, -0.5), ambient=0.42, diffuse=0.78,
                    tint=(1.14, 1.0, 0.84))
    _cam(r, t, (0.62, 1.64, -0.95 + k * 0.24), (-0.02, 1.52, 1.2), lerp(40, 35, k), hh=0.007, seed=10)
    buf.fill((14, 12, 12))
    r.begin()
    _add(r, quad_xz(-5, -5, 5, 3.2, 0.0, (40, 30, 26), seg=2))
    _add(r, box(10, 3.2, 0.2, (44, 40, 38), center=(0, 1.6, 3.2)))
    for i in range(7):                                                # blinds, streetlight
        _add(r, box(1.6, 0.06, 0.02, (110, 96, 70), center=(-1.6, 1.3 + i * 0.18, 3.08),
                   emissive=True))
    _flags(r, 1.6, 2.6)
    # President's portrait (was an empty gilt frame - N17), same decal as m5mid3d's office
    if not _decal.add(r, "portrait_frame", 0, (0.2, 2.3, 3.06), (1.0, 1.0), bias=0.5):
        _add(r, box(1.0, 1.0, 0.04, (120, 96, 52), center=(0.2, 2.3, 3.08)))
        _add(r, box(0.6, 0.6, 0.03, (60, 46, 28), center=(0.2, 2.3, 3.05)))
    hum = _hum("vasile")
    pose = _ending.radio_pose(hum, _life_pose(dict(_RADIO, head_y=12), t, .6, 6))
    vpos = (0.0, 0.0, 1.5)
    yaw_v = _yaw_to(vpos, (1.2, 0, -3))
    _life(r, hum, pose, vpos, yaw_v, t, seed=6, amp=0)
    _ending.draw_handset(r, hum, pose, vpos, yaw_v, t, base=(0.5, 0.88, 0.7))
    _cig(r, hum, pose, vpos, yaw_v, t, seed=6)
    _add(r, box(2.2, 0.8, 0.9, (48, 34, 26), center=(0.0, 0.4, 0.75)))   # desk
    _add(r, box(2.3, 0.05, 1.0, (70, 52, 40), center=(0.0, 0.82, 0.75)))
    _add(r, box(0.06, 0.4, 0.06, (40, 38, 34), center=(-0.8, 1.05, 0.9)))
    _add(r, box(0.26, 0.14, 0.26, (255, 220, 160), center=(-0.8, 1.28, 0.9), emissive=True))
    # Desk bulb is geometry only; no camera-facing flare over the officer.
    _spr(r, (-1.6, 1.84, 3.0), _fx.window_glow((70, 50, 28), 0.9, 0.7, 0.5))   # streetlight through blinds
    # No screen-down shaft: it painted onto faces instead of the desk.
    _add(r, box(0.4, 0.08, 0.3, (24, 24, 26), center=(0.5, 0.88, 0.7)))   # phone base
    _add(r, box(0.5, 0.01, 0.34, (210, 206, 196), center=(-0.2, 0.85, 0.6)))
    r.flush(buf)
    _present(surface, buf, WIDTH // 2, WIDTH - WIDTH // 2)
    pygame.draw.line(surface, (70, 76, 86), (WIDTH // 2, SAFE_TOP), (WIDTH // 2, SAFE_BOT), 2)
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


# RPE6 Phase 2 (A-003 take registry): the cutscene scene ids this module owns.
# cutscenes.engine.draw_cutscene_scene finds them through core.cutscene_registry
# instead of importing this module by name (boundary rule 4 / W1).
from core.cutscene_registry import register_scene_renderers as _register_takes  # noqa: E402
from cutscenes.m5martial import (  # noqa: E402  (2D fallbacks of the 3D takes)
    _draw_m5_radio, _draw_m5_retardovici_tv, _draw_m5_river_gate, _draw_m5_safehouse_tv, _draw_m5_tv_bulletin, _draw_m5_ucilev_leaves, _draw_m5_ucilev_reveal, _draw_m5_ucilev_scope)
from engine.text import T as _T  # RPE6 Phase 4 text table


def _take_3d_or_2d(scene, fallback_2d):
    """W7 policy kept verbatim: draw the 3D take; when it declines (3D off, no backend), draw the 2D scene."""
    def _take(surface, t):
        if not draw_m5_scene_3d(scene, surface, t):
            fallback_2d(surface, t)
    return _take


_register_takes({
    "m5_tv_bulletin": _take_3d_or_2d("m5_tv_bulletin", _draw_m5_tv_bulletin),
    "m5_safehouse_tv": _take_3d_or_2d("m5_safehouse_tv", _draw_m5_safehouse_tv),
    "m5_retardovici_tv": _take_3d_or_2d("m5_retardovici_tv", _draw_m5_retardovici_tv),
    "m5_river_gate": _take_3d_or_2d("m5_river_gate", _draw_m5_river_gate),
    "m5_ucilev_scope": _take_3d_or_2d("m5_ucilev_scope", _draw_m5_ucilev_scope),
    "m5_ucilev_reveal": _take_3d_or_2d("m5_ucilev_reveal", _draw_m5_ucilev_reveal),
    "m5_ucilev_leaves": _take_3d_or_2d("m5_ucilev_leaves", _draw_m5_ucilev_leaves),
    "m5_radio": _take_3d_or_2d("m5_radio", _draw_m5_radio),
})
