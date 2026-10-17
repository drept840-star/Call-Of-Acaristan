"""m5mid3d.py - Mission 5 mid-mission cutscenes (round 2).

    m5x_pw_arrival_wide / m5x_pw_arrival_door   Biribel reaches the MAG Print Works
    m5x_vasile_wide / _close / _biribel / _lean  Vasile's office
    m5x_maru_two / _close / _biribel             Maru's back office
    m5x_breach_lights / m5x_breach               the Guard breach (Ucilev: faceless
                                                 silhouette only)

Entry point: draw_m5x(scene, surface, t) - 3D take via the m5martial3d plumbing,
2D fallback (draw_m5x_2d) if the 3D stack is off or fails. engine.py dispatches
any scene starting with "m5x_" here. This module imports m5martial3d, never the
other way round (keeps imports acyclic).
"""
import math
import random

import pygame

from core.config import (HEIGHT, WIDTH, font_location, font_terminal, font_terminal_small)
from cutscenes.m5martial import SAFE_TOP, SAFE_BOT, _GUARD_RED, _LIAISON, _rain_streaks, _tag
from cutscenes import m5martial3d as _m3d
import game.render3d_bridge as _bridge  # RPE6 P8: set3d data path
from cutscenes import m5fx3d as _fx
from cutscenes import m5decal as _decal

__all__ = ["draw_m5x", "draw_m5x_2d", "M5X_SCENES"]

_RW, _RH = _m3d._RW, _m3d._RH
_add, _k, _hum, _yaw_to = _m3d._add, _m3d._k, _m3d._hum, _m3d._yaw_to
from core.outfits import OUTFIT_GUARD, KRAP_MARK, biribel_2d, scene_outfit
_BIRI_GUARD = _m3d._BIRI_GUARD
from engine3d.core import lerp
from engine.text import T as _T  # RPE6 Phase 4 text table
_BRICK = (74, 44, 36)
_SIL = {}
_spr = _m3d._spr
_STREET_LIGHTS = (((-5, 4.6, 8.0), _fx.SODIUM), ((0, 0.6, 9.4), (255, 200, 130)))


def _dec(r, m, bias=0.8):
    """Wall decal: same as _add but depth-biased so the painter sort never
    buries a flat poster/map behind the big wall face it is pinned to."""
    # sort key is layer*1e6 - depth - bias: a NEGATIVE bias pulls the face nearer
    r.add_dynamic(m.verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces],
                  bias=-abs(bias))


# ── sets ──
def _street_set(r, t, door=None):
    """Lower Quarter street + the MAG Print Works: a real four-storey
    industrial block - brick, sawtooth roof, chimney, loading shutter, sign.

    ``door`` = None: shutter shut (solid block). ``door`` = 0..1: the loading
    door is a real opening in the facade, the shutter rolls up into its
    housing by that fraction and the press hall behind it is built
    (``_pw_interior``) - T10: it used to be a flat glowing card."""
    from engine3d.core import box, quad_xz
    wet = lambda x, z: (24, 26 + int(4 * math.sin(x * 1.3 + z * 0.7)), 32)
    _add(r, quad_xz(-20, -10, 20, 9.6, 0.0, (26, 27, 32), seg=6, colfn=wet))
    # Big slabs are subdivided (seg): the painter sorts by the average depth of
    # the near-CLIPPED face, so in the close door shot one 16 m facade face (and
    # the 40 m kerb) sorted nearer than the shutter and flickered over it.
    _add(r, box(40, 0.18, 2.2, (40, 40, 46), center=(0, 0.09, 8.6), seg=2.0))  # kerb/pavement
    # main block
    if door is None:
        _add(r, box(16, 11, 6, _BRICK, center=(0, 5.5, 13), seg=2.0))
    else:
        # same block minus its front face; the facade is rebuilt around a
        # PW_DOOR_W x PW_DOOR_H opening so nothing is drawn across the doorway
        _add(r, box(16, 11, 6, _BRICK, center=(0, 5.5, 13), seg=2.0, skip=("front",)))
        side = (16 - PW_DOOR_W) / 2
        for sx in (-1, 1):
            _add(r, box(side, 11, 0.06, _BRICK, center=(sx * (8 - side / 2), 5.5, 10.03), seg=2.0))
        _add(r, box(PW_DOOR_W, 11 - PW_DOOR_H, 0.06, _BRICK,
                    center=(0, PW_DOOR_H + (11 - PW_DOOR_H) / 2, 10.03), seg=2.0))
    for i in range(8):                                                          # pilasters
        px = -7.6 + i * 2.17
        if abs(px) < 2.4:   # over the loading door: start above the shutter, never through it
            _add(r, box(0.5, 7.3, 0.3, (62, 36, 30), center=(px, 7.35, 9.9)))
        else:
            _add(r, box(0.5, 11, 0.3, (62, 36, 30), center=(px, 5.5, 9.9)))
    _add(r, box(16.4, 0.4, 0.5, (52, 50, 50), center=(0, 11.1, 9.9)))          # cornice
    for j in range(5):                                                          # sawtooth roof
        _add(r, box(3.0, 1.4, 6, (44, 44, 50), center=(-6 + j * 3.0, 11.9, 13)))
        _add(r, box(2.6, 0.9, 0.05, (110, 120, 110), center=(-6 + j * 3.0, 12.0, 9.95),
                   emissive=True))
    _add(r, box(1.2, 7, 1.2, (60, 34, 28), center=(6.5, 14, 14)))               # chimney
    rng = random.Random(55)
    for fl in range(3):                                                         # windows
        for c in range(7):
            x = -6.5 + c * 2.17
            if abs(x) < 2.6 and fl == 0:
                continue
            lit = rng.random() < 0.3
            col = (150, 120, 70) if lit else (22, 28, 36)
            _add(r, box(1.2, 1.6, 0.05, col, center=(x, 3.2 + fl * 2.8, 9.88), emissive=lit))
    # sign board: dark plate + lit letters strip
    _add(r, box(8.4, 1.3, 0.2, (20, 20, 24), center=(0, 9.2, 9.75)))
    flick = 0.75 + 0.25 * (1 if (t // 170) % 7 else 0)
    # baked sprite (art.m5.printworks_sign): "MAG PRINT WORKS", the R blows on the flicker beat
    if not _decal.add(r, "printworks_sign", 1 if flick < 1 else 0, (0, 9.2, 9.64), (8.4, 1.3),
                      bias=0.6, emissive=150):
        for i in range(14):
            if i in (3, 9):
                continue
            _add(r, box(0.42, 0.8, 0.05, tuple(int(c * flick) for c in (230, 190, 120)),
                       center=(-3.6 + i * 0.55, 9.2, 9.62), emissive=True))
    # loading shutter + doorway light
    if door is None:
        _add(r, box(4.2, 3.6, 0.3, (36, 36, 40), center=(0, 1.8, 9.85), seg=1.0))
        # (light strip + pool sit ON the kerb top (y 0.18), not buried inside it)
        _add(r, box(3.6, 0.12, 0.05, (255, 210, 140), center=(0, 0.24, 9.66), emissive=True))
    else:
        _pw_door(r, t, door)
        _pw_interior(r, t, door)
    if _decal.add(r, "guard_plate", 0, (2.55, 3.9, 9.397), (0.9, 0.5), emissive=True):  # Guard notice
        _add(r, box(0.9, 0.5, 0.4, (70, 16, 16), center=(2.55, 3.9, 9.6), skip=("front",)))
    else:
        _add(r, box(0.9, 0.5, 0.4, (200, 40, 40), center=(2.55, 3.9, 9.6), emissive=True))
    if door is None:
        _add(r, quad_xz(-2, 8.2, 2, 9.6, 0.19, (70, 54, 34), emissive=True))   # door light pool
    # street lamp + parked van + posters
    _add(r, box(0.12, 4.6, 0.12, (36, 36, 40), center=(-5, 2.3, 8.0)))
    _add(r, box(0.4, 0.25, 0.4, (255, 214, 150), center=(-5, 4.6, 8.0), emissive=True))
    _spr(r, (-5, 4.55, 8.0), _fx.sodium_lamp(t, 7, radius_m=2.6))
    _spr(r, (-5, 0.02, 7.6), _fx.wet_reflection(_fx.SODIUM, t, 7, 3.0, 0.6, 0.3))
    if door is None:
        _spr(r, (0, 0.3, 9.5), _fx.window_glow((150, 110, 60), 2.2, 0.35, 0.6))  # door light strip
        _spr(r, (0, 0.03, 8.4), _fx.wet_reflection((255, 200, 130), t, 8, 2.4, 1.4, 0.22))
    _spr(r, (0, 9.2, 9.5), _fx.window_glow((120, 90, 50), 4.2, 0.6, 0.5 * flick))  # sign
    _spr(r, (2.55, 3.9, 9.35), _fx.glow((220, 40, 36), 0.7, t, pulse=0.2, intensity=0.6))
    _add(r, box(4.2, 2.0, 1.9, (52, 58, 52), center=(6.5, 1.1, 7.0)))
    _add(r, box(1.3, 1.0, 1.8, (60, 66, 60), center=(8.9, 0.8, 7.0)))
    for i in range(4):   # posters: proud of the pilaster faces (z 9.75), clear of the shutter
        if not _decal.add(r, "posters", (0, 1, 2, 3)[i], (-5.0 + i * 0.75, 1.6, 9.71), (0.64, 0.88)):
            _dec(r, box(0.6, 1.0, 0.02, (170 - i * 20, 160, 140), center=(-5.0 + i * 0.75, 1.6, 9.72)))
    # neighbours
    for x, h, c in ((-13, 8, (40, 40, 48)), (13, 9, (46, 40, 40))):
        _add(r, box(10, h, 6, c, center=(x, h / 2, 13), seg=3.0))


# ── MAG Print Works loading door + press hall behind it (T10) ──
PW_DOOR_W = 4.0          # facade opening (m)
PW_DOOR_H = 3.5
PW_FLOOR_Y = 0.18        # hall floor flush with the pavement / kerb top
PW_HALL = (-4.5, 10.03, 4.5, 18.0)   # x0, z0, x1, z1: 8 m deep behind the facade
PW_LAMPS = ((-1.6, 12.6), (1.5, 15.6))   # hanging work lights (x, z)
_PW_WARM = (255, 200, 140)


def _pw_door(r, t, k):
    """Shutter that physically rolls up into a drum housing, guide rails,
    door reveals, and the warm spill growing on the wet pavement with it."""
    from engine3d.core import box, quad_xz
    hw = PW_DOOR_W / 2
    h = (PW_DOOR_H - 0.12) * k                       # bottom edge of the shutter
    for sx in (-1, 1):                               # brick reveals + steel guide rails
        _add(r, box(0.12, PW_DOOR_H, 0.6, (58, 34, 28), center=(sx * (hw + 0.06), PW_DOOR_H / 2, 10.3)))
        _add(r, box(0.1, PW_DOOR_H, 0.14, (40, 42, 46), center=(sx * (hw - 0.02), PW_DOOR_H / 2, 9.95)))
    _add(r, box(PW_DOOR_W + 0.5, 0.5, 0.56, (44, 46, 50), center=(0, PW_DOOR_H + 0.2, 9.75)))  # drum housing
    _add(r, box(PW_DOOR_W + 0.5, 0.05, 0.6, (30, 32, 36), center=(0, PW_DOOR_H - 0.05, 9.75)))
    sh = PW_DOOR_H - h
    if sh > 0.02:
        _add(r, box(PW_DOOR_W - 0.04, sh, 0.06, (54, 56, 60), center=(0, h + sh / 2, 9.97), seg=1.0))
        for i in range(int(sh / 0.22)):                               # slats
            _dec(r, box(PW_DOOR_W - 0.04, 0.03, 0.02, (30, 32, 36),
                        center=(0, h + 0.11 + i * 0.22, 9.93)), 0.5)
        lip = tuple(int(c + (150 - c) * k) for c in (70, 70, 74))       # bottom bar catches the light
        _add(r, box(PW_DOOR_W - 0.04, 0.07, 0.1, lip, center=(0, h + 0.035, 9.95)))
    # warm spill on the pavement / road, growing with the opening
    a = min(1.0, h / 1.2)
    if a > 0.01:
        w = 1.6 + 0.9 * a
        col = (int(36 + 70 * a), int(28 + 52 * a), int(18 + 30 * a))
        z0 = 9.7 - (0.5 + 2.6 * a)
        _add(r, quad_xz(-w, max(7.5, z0), w, 9.7, 0.19, col, emissive=True))
        if z0 < 7.5:
            dim = tuple(int(c * 0.7) for c in col)
            _add(r, quad_xz(-w * 1.1, z0, w * 1.1, 7.5, 0.012, dim, emissive=True))
        _spr(r, (0, 0.03, 8.2), _fx.wet_reflection(_PW_WARM, t, 8, 2.0 + 2.2 * a, 1.0 + 1.2 * a, 0.12 + 0.3 * a))
    if k > 0.02:                                     # light shaft out of the doorway + motes
        _spr(r, (0, min(h, PW_DOOR_H) / 2 + 0.1, 9.9),
             _fx.window_glow(_PW_WARM, PW_DOOR_W * 0.95, max(0.3, min(h, PW_DOOR_H)), 0.1 * a))
        _spr(r, (0, 1.5, 9.6), _fx.dust_motes(t, 41, int(10 + 22 * a), (1.8, 1.3), (170, 150, 116)))


def _pw_interior(r, t, k):
    """The press hall seen through the loading door: same building as
    _press_set (palette, presses, paper stacks, drying line of posters, type
    cases, warm bulbs), 8 m deep so the push-in shows parallax. Brighter and
    warmer than the street so it reads as the focus; Maru is at the press
    and looks up as the shutter rises."""
    from engine3d.core import box, quad_xz
    x0, z0, x1, z1 = PW_HALL
    fy = PW_FLOOR_Y
    # sprites are not occluded by the shutter geometry: fade the hall's
    # glows / motes in with the opening so none of them bleed through it
    h_open = (PW_DOOR_H - 0.12) * k
    def seen(y):     # ~ when the rising shutter edge clears the sight line to height y
        return max(0.0, min(1.0, (h_open - y * 0.85) / 0.5))
    hh = 4.6
    def floor_col(x, z):     # concrete, a touch warmer near the lamps
        warm = max(0.0, 1.0 - min(math.hypot(x - lx, z - lz) for lx, lz in PW_LAMPS) / 3.2)
        return (int(64 + 36 * warm), int(56 + 26 * warm), int(46 + 14 * warm))
    _add(r, quad_xz(x0, z0, x1, z1, fy, (64, 56, 46), seg=1.0, colfn=floor_col))
    wall = (96, 80, 62)
    _add(r, box(0.2, hh, z1 - z0, wall, center=(x0 - 0.1, fy + hh / 2, (z0 + z1) / 2), seg=1.0))
    _add(r, box(0.2, hh, z1 - z0, (90, 74, 58), center=(x1 + 0.1, fy + hh / 2, (z0 + z1) / 2), seg=1.0))
    _add(r, box(x1 - x0 + 0.4, hh, 0.2, (100, 84, 64), center=(0, fy + hh / 2, z1 + 0.1), seg=1.0))
    _add(r, box(x1 - x0 + 0.4, 0.2, z1 - z0, (46, 40, 34), center=(0, fy + hh + 0.1, (z0 + z1) / 2), seg=1.5))
    _add(r, box(x1 - x0, 0.5, 0.12, (60, 50, 40), center=(0, fy + 0.25, z1 - 0.06)))      # skirting
    # hanging work lights: cord, green enamel shade, bulb, glow + floor pool
    for i, (lx, lz) in enumerate(PW_LAMPS):
        _add(r, box(0.02, 1.1, 0.02, (30, 30, 30), center=(lx, fy + hh - 0.55, lz)))
        _add(r, box(0.46, 0.14, 0.46, (40, 62, 44), center=(lx, fy + hh - 1.15, lz)))
        _add(r, box(0.16, 0.06, 0.16, (255, 232, 176), center=(lx, fy + hh - 1.25, lz), emissive=True))
        _spr(r, (lx, fy + hh - 1.3, lz), _fx.glow(_PW_WARM, 1.3, t, flicker=0.04, seed=11 + i,
                                                  core=(255, 240, 210), intensity=0.8 * seen(fy + hh - 1.3)))
        _add(r, quad_xz(lx - 0.9, lz - 0.8, lx + 0.9, lz + 0.8, fy + 0.006, (96, 78, 54), emissive=True))
    if seen(fy + 1.9) > 0.05:
        _spr(r, (PW_LAMPS[0][0], fy + 1.9, PW_LAMPS[0][1]),
             _fx.dust_motes(t, 31, int(24 * seen(fy + 1.9)), (1.3, 1.0), (120, 110, 92)))
    # paper pallets by the door (left), stacks of irregular height like _press_set
    for (px, pz) in ((-3.0, 11.2), (-3.3, 13.0)):
        _add(r, box(1.3, 0.12, 1.0, (70, 52, 34), center=(px, fy + 0.06, pz)))
        for j, (dx, hgt, tone) in enumerate(((-0.32, 0.62, 0), (0.3, 0.44, 10), (0.0, 0.3, -8))):
            col = tuple(max(0, min(255, c + tone)) for c in (178, 172, 156))
            _add(r, box(0.56, hgt, 0.44, col, center=(px + dx, fy + 0.12 + hgt / 2, pz - 0.2 + 0.2 * j),
                        cols={"top": tuple(min(255, c + 14) for c in col)}))
            _add(r, box(0.57, 0.03, 0.03, (120, 40, 36), center=(px + dx, fy + 0.12 + hgt * 0.6, pz - 0.43 + 0.2 * j)))
    # ink drums (right of the door)
    for (dx, dz) in ((3.4, 11.1), (3.95, 11.7), (3.25, 12.3)):
        _add(r, box(0.56, 0.86, 0.56, (30, 34, 48), center=(dx, fy + 0.43, dz)))
        _add(r, box(0.6, 0.04, 0.6, (62, 66, 82), center=(dx, fy + 0.86, dz)))
        _add(r, box(0.6, 0.04, 0.6, (62, 66, 82), center=(dx, fy + 0.3, dz)))
    # the press, deep in the hall (same dims / steel as _press_set's presses)
    px, pz = 1.0, 16.2
    _add(r, box(2.6, 1.5, 1.3, (40, 46, 52), center=(px, fy + 0.75, pz)))
    _add(r, box(2.0, 0.45, 0.9, (60, 66, 72), center=(px, fy + 1.72, pz)))
    _add(r, box(0.34, 0.34, 1.4, (90, 84, 70), center=(px + 0.8, fy + 1.25, pz)))
    _add(r, box(0.9, 0.05, 1.0, (214, 208, 190), center=(px - 1.75, fy + 1.0, pz)))     # paper feed
    _add(r, box(0.08, 1.0, 0.08, (40, 46, 52), center=(px - 2.1, fy + 0.5, pz)))
    _add(r, box(0.1, 0.07, 0.04, (60, 210, 96), center=(px + 1.0, fy + 1.3, pz - 0.67), emissive=True))
    _spr(r, (px + 1.0, fy + 1.3, pz - 0.7), _fx.glow((60, 210, 96), 0.25, t, pulse=0.3, intensity=0.5 * seen(fy + 1.3)))
    # drying line of posters along the left wall (faces the doorway)
    _add(r, box(0.02, 0.02, 6.2, (30, 30, 30), center=(x0 + 0.15, 3.0 + fy, 14.0)))
    for i in range(7):
        cz = 11.2 + i * 0.86
        if not _decal.add(r, "posters", 5 if i % 2 else 4, (x0 + 0.16, 2.65 + fy, cz), (0.46, 0.62),
                          facing="+x"):
            _dec(r, box(0.02, 0.62, 0.46, (214, 208, 190) if i % 2 else (176, 46, 40),
                        center=(x0 + 0.17, 2.65 + fy, cz)))
    # back wall: type cases, pinned proofs, a work lamp
    for i in range(4):
        _add(r, box(0.9, 1.1, 0.4, (88, 62, 40), center=(-3.4 + i * 1.1, fy + 0.55, z1 - 0.22)))
        _add(r, box(0.8, 0.05, 0.36, (180, 170, 140), center=(-3.4 + i * 1.1, fy + 1.12, z1 - 0.22)))
    for bx, pv, pc in ((-2.6, 4, (176, 46, 40)), (-1.7, 5, (206, 198, 176)), (2.9, 4, (176, 46, 40))):
        if not _decal.add(r, "posters", pv, (bx, fy + 2.2, z1 - 0.01), (0.6, 0.85), bias=1.0):
            _dec(r, box(0.6, 0.85, 0.03, pc, center=(bx, fy + 2.2, z1 - 0.02)), 1.0)
    _dec(r, box(0.3, 0.16, 0.24, (255, 220, 160), center=(-0.6, fy + 2.7, z1 - 0.12), emissive=True), 1.0)
    _spr(r, (-0.6, fy + 2.6, z1 - 0.3), _fx.glow((255, 210, 150), 0.6, intensity=0.5 * seen(fy + 2.6)))
    # The hall is empty on arrival. Maru is in the back office, where the
    # player must actually find him; do not reveal him at the loading door.


def _office_set(r):
    if not _bridge.use_legacy():      # RPE6 P8: Vasile's office renders from set data
        _bridge.apply_set(r, _bridge.set_prims("m5.vasile_office"),
                          add=_add, dec=_dec, spr=_spr, decal_add=_decal.add, fx=_fx)
        return
    from engine3d.core import Light, box, quad_xz
    r.fog, r.fog_start, r.fog_end = (12, 11, 10), 8.0, 24.0
    r.light = Light(direction=(-0.45, 0.65, -0.6), ambient=0.46, diffuse=0.86, tint=(1.14, 1.0, 0.84))
    _add(r, quad_xz(-3.5, -3.5, 5, 3.1, 0.0, (52, 38, 30), seg=1))
    # Complete the room, including reverse/low-angle coverage. The old
    # three-wall set exposed the background beyond its open side and roof.
    _add(r, box(0.2, 3.2, 7, (50, 46, 42), center=(5.1, 1.6, 0), seg=1))
    _add(r, box(8.8, 0.2, 7, (38, 35, 32), center=(0.7, 3.3, 0), seg=1))
    _spr(r, (-0.85, 1.15, 1.0), _fx.glow((255, 196, 120), 0.9, core=(255, 238, 200), intensity=0.65))
    _spr(r, (-2.2, 2.1, -3.4), _fx.glow((255, 200, 140), 0.55, intensity=0.55))   # sconce
    _spr(r, (-3.45, 1.7, -0.6), _fx.window_glow((60, 70, 90), 0.4, 1.0, 0.5))      # window
    _spr(r, (-1.6, 1.84, 3.0), _fx.window_glow((70, 50, 28), 0.9, 0.7, 0.45))      # blinds
    _add(r, box(10, 3.2, 0.2, (58, 54, 50), center=(0, 1.6, 3.2)))
    _add(r, box(10, 1.0, 0.05, (40, 46, 40), center=(0, 0.5, 3.08)))           # wainscot
    _add(r, quad_xz(-1.6, 0.0, 1.4, 1.6, 0.01, (88, 64, 40), emissive=True))  # lamp pool
    if not _decal.add(r, "guard_banner", 0, (2.6, 1.9, 3.05), (1.2, 1.9)):    # Guard banner
        _dec(r, box(1.2, 1.9, 0.04, (24, 22, 22), center=(2.6, 1.9, 3.07)))
        _dec(r, box(1.2, 0.5, 0.05, (170, 30, 32), center=(2.6, 1.7, 3.05)), 1.0)
    # reverse-angle side: back wall, door, coat stand, filing cabinet
    _add(r, box(10, 3.2, 0.2, (54, 50, 46), center=(0, 1.6, -3.6)))
    _add(r, box(10, 1.0, 0.05, (40, 46, 40), center=(0, 0.5, -3.48)))
    _add(r, box(1.0, 2.2, 0.06, (66, 46, 32), center=(1.2, 1.1, -3.46)))       # door
    _add(r, box(0.9, 0.5, 0.04, (150, 140, 110), center=(1.2, 2.0, -3.44), emissive=True))
    _add(r, box(0.6, 1.3, 0.5, (70, 76, 70), center=(-1.6, 0.65, -3.2)))      # cabinet
    _add(r, box(0.06, 1.8, 0.06, (40, 30, 24), center=(-0.4, 0.9, -3.1)))     # coat stand
    _add(r, box(0.5, 0.7, 0.2, (36, 40, 34), center=(-0.4, 1.45, -3.1)))
    if not _decal.add(r, "district_map", 0, (-0.9, 1.75, -3.44), (1.3, 0.9), facing="+z"):
        _dec(r, box(1.3, 0.9, 0.04, (150, 136, 100), center=(-0.9, 1.75, -3.46)))   # district map
    for i in range(4):
        _dec(r, box(0.05, 0.05, 0.02, (190, 40, 36), center=(-1.3 + i * 0.27, 1.6 + (i % 2) * 0.3, -3.43)), 1.0)
    _dec(r, box(0.9, 0.5, 0.01, (70, 56, 40), center=(-2.2, 2.0, -3.47), emissive=True))
    _dec(r, box(0.16, 0.22, 0.1, (255, 214, 150), center=(-2.2, 2.1, -3.44), emissive=True), 1.0)  # sconce
    _add(r, box(0.2, 3.2, 7, (50, 46, 42), center=(-3.6, 1.6, 0)))
    _add(r, box(0.05, 1.2, 1.6, (120, 130, 140), center=(-3.48, 1.7, -0.6), emissive=True))  # window
    for i in range(7):
        _add(r, box(1.6, 0.06, 0.02, (110, 96, 70), center=(-1.6, 1.3 + i * 0.18, 3.08), emissive=True))
    _m3d._flags(r, 1.6, 2.6)
    if not _decal.add(r, "portrait_frame", 0, (0.2, 2.3, 3.06), (1.0, 1.0), bias=0.5):
        _add(r, box(1.0, 1.0, 0.04, (120, 96, 52), center=(0.2, 2.3, 3.08)))  # portrait frame
    _add(r, box(2.2, 0.8, 0.9, (48, 34, 26), center=(0.0, 0.4, 0.75)))         # desk
    _add(r, box(2.3, 0.05, 1.0, (70, 52, 40), center=(0.0, 0.82, 0.75)))
    _add(r, box(0.14, 0.03, 0.14, (30, 30, 28), center=(-0.85, 0.86, 1.0)))     # desk lamp
    _add(r, box(0.025, 0.34, 0.025, (40, 40, 36), center=(-0.85, 1.03, 1.0)))
    _add(r, box(0.26, 0.12, 0.26, (34, 62, 44), center=(-0.85, 1.22, 1.0)))
    _add(r, box(0.16, 0.02, 0.16, (255, 224, 170), center=(-0.85, 1.155, 1.0), emissive=True))
    _add(r, box(0.5, 0.01, 0.34, (210, 206, 196), center=(-0.2, 0.85, 0.6)))   # Maru's file


def _press_set(r, t, alarm=0.0, door=False):
    """Print-works back office / press hall: presses, paper stacks, hanging bulb."""
    from engine3d.core import Light, box, quad_xz
    r.fog, r.fog_start, r.fog_end = (14, 13, 12), 6.0, 22.0
    r.light = Light(direction=(0.35, 0.8, -0.5), ambient=0.43, diffuse=0.88, tint=(1.12, 1.0, 0.84))
    _add(r, quad_xz(-5.1, -4.1, 5.9, 4.1, 0.0, (56, 50, 44), seg=1))
    _add(r, box(0.2, 3.6, 8.6, (54, 48, 44), center=(6.0, 1.8, 0), seg=1))
    _add(r, box(11.4, 0.2, 8.6, (36, 33, 30), center=(0.4, 3.7, 0), seg=1))
    _spr(r, (0.0, 2.75, 1.4), _fx.glow((255, 200, 140), 1.1, t, flicker=0.04, seed=5,
                                       core=(255, 240, 210), intensity=0.75))   # hanging bulb
    _spr(r, (0.0, 1.9, 1.4), _fx.dust_motes(t, 31, 24, (1.2, 0.9), (120, 110, 92)))
    _spr(r, (-3.0, 2.6, -3.95), _fx.glow((255, 210, 150), 0.6, intensity=0.55))    # work lamp
    if alarm > 0.05:                                                         # siren through the glass
        blue = (t // 220) % 2 == 0
        _spr(r, (0.0, 2.5, 4.0), _fx.window_glow((30, 50, 200) if blue else (200, 30, 30),
                                                 4.0, 1.2, 0.55 * alarm))
    _add(r, quad_xz(-1.4, -0.2, 2.4, 2.4, 0.01, (92, 74, 48), emissive=True))  # bulb pool
    _add(r, box(0.02, 0.02, 6.0, (30, 30, 30), center=(-5.0, 2.95, 0.0)))      # drying line
    for i in range(7):                                                          # posters on it
        if not _decal.add(r, "posters", 5 if i % 2 else 4, (-5.01, 2.6, -2.7 + i * 0.85),
                          (0.46, 0.62), facing="+x"):
            _dec(r, box(0.02, 0.62, 0.46, (214, 208, 190) if i % 2 else (176, 46, 40),
                       center=(-5.02, 2.6, -2.7 + i * 0.85)))
    _add(r, box(12, 3.6, 0.2, (58, 52, 46), center=(0, 1.8, 4.2)))
    _add(r, box(0.2, 3.6, 10, (54, 48, 44), center=(-5.2, 1.8, 0)))
    _add(r, box(12, 3.6, 0.2, (52, 46, 42), center=(0, 1.8, -4.2)))           # reverse wall
    for i in range(4):                                                          # type cases
        _add(r, box(0.9, 1.1, 0.4, (88, 62, 40), center=(-3.4 + i * 1.1, 0.55, -3.9)))
        _add(r, box(0.8, 0.05, 0.36, (180, 170, 140), center=(-3.4 + i * 1.1, 1.12, -3.9)))
    for px, pc, pv in ((-2.3, (176, 46, 40), 4), (-1.4, (206, 198, 176), 5), (-0.6, (176, 46, 40), 4)):
        if not _decal.add(r, "posters", pv, (px, 2.0, -4.07), (0.6, 0.85), facing="+z", bias=1.0):
            _dec(r, box(0.6, 0.85, 0.03, pc, center=(px, 2.0, -4.08)), 1.0)    # pinned proofs
    _dec(r, box(1.6, 0.9, 0.01, (74, 60, 42), center=(-2.6, 2.3, -4.09), emissive=True))
    _dec(r, box(0.3, 0.16, 0.24, (255, 220, 160), center=(-3.0, 2.6, -4.0), emissive=True), 1.0)  # work lamp
    _add(r, box(1.3, 0.8, 0.04, (200, 190, 160), center=(2.6, 2.1, -4.08), emissive=True))
    _add(r, box(1.0, 0.5, 0.05, (190, 50, 44), center=(2.6, 2.1, -4.06)))
    for i, x in enumerate((-3.4, 2.8)):                                         # presses
        _add(r, box(1.8, 1.5, 1.2, (40, 46, 52), center=(x, 0.75, 2.6)))
        _add(r, box(1.4, 0.4, 0.8, (60, 66, 72), center=(x, 1.7, 2.6)))
        _add(r, box(0.3, 0.3, 1.3, (90, 84, 70), center=(x + 0.6, 1.2, 2.6)))
    _add(r, box(3.2, 0.12, 0.5, (70, 52, 34), center=(-0.2, 0.06, 3.4)))       # pallet
    # paper stacks: irregular heights / widths / tones, some with a second
    # bundle dropped on top at an offset, so they stop reading as copies (N15)
    for (sx, hh, sw, tone, dz, top) in ((-1.42, 0.34, 0.50, 0, 0.00, 0.16),
                                        (-0.78, 0.22, 0.44, 10, 0.05, 0.0),
                                        (-0.22, 0.47, 0.52, -8, -0.03, 0.12),
                                        (0.40, 0.29, 0.46, 6, 0.04, 0.0),
                                        (1.02, 0.40, 0.50, -4, -0.02, 0.18)):
        col = tuple(max(0, min(255, c + tone)) for c in (178, 172, 156))
        _add(r, box(sw, hh, 0.36, col, center=(sx, 0.12 + hh / 2, 3.4 + dz),
                    cols={"top": tuple(min(255, c + 14) for c in col)}))
        _add(r, box(sw, 0.03, 0.04, (120, 40, 36), center=(sx, 0.12 + hh * 0.6, 3.21 + dz)))
        if top:
            _add(r, box(sw * 0.8, top, 0.3, tuple(min(255, c + 8) for c in col),
                        center=(sx + 0.05, 0.12 + hh + top / 2, 3.38 + dz)))
            _add(r, box(0.03, top, 0.31, (120, 40, 36), center=(sx + 0.05, 0.12 + hh + top / 2, 3.38 + dz)))
    # windows on the back wall: the street outside
    for i in range(3):
        if door and i == 1:                     # the breach door sits there
            continue
        a = alarm * (0.5 + 0.5 * math.sin(t * 0.02 + i))
        blue = ((t // 220) + i) % 2 == 0
        col = (int(40 + 200 * a * (0 if blue else 1)), 40, int(60 + 190 * a * (1 if blue else 0)))
        _dec(r, box(1.3, 0.9, 0.04, col, center=(-2.6 + i * 2.6, 2.5, 4.08), emissive=True))
        _dec(r, box(1.42, 0.08, 0.03, (34, 32, 30), center=(-2.6 + i * 2.6, 2.5, 4.04)), 1.0)   # mullions
        _dec(r, box(0.08, 1.0, 0.03, (34, 32, 30), center=(-2.6 + i * 2.6, 2.5, 4.04)), 1.0)
        _add(r, box(1.5, 0.08, 0.12, (40, 38, 34), center=(-2.6 + i * 2.6, 2.0, 4.04)))   # sill
    _add(r, box(0.02, 0.8, 0.02, (30, 30, 30), center=(0.0, 3.2, 1.4)))
    _add(r, box(0.2, 0.2, 0.2, (255, 220, 160), center=(0.0, 2.75, 1.4), emissive=True))
    _add(r, box(1.6, 0.75, 0.8, (60, 44, 32), center=(1.0, 0.38, 0.6)))        # Maru's table
    _add(r, box(0.6, 0.02, 0.4, (220, 214, 196), center=(1.0, 0.77, 0.6)))


def _night_street(r):
    from engine3d.core import Light
    r.fog, r.fog_start, r.fog_end = (18, 20, 30), 16.0, 52.0
    r.light = Light(direction=(0.3, 0.75, -0.6), ambient=0.52, diffuse=0.8, tint=(1.0, 0.92, 0.82))


# ── helpers ──
_TALK = dict(spine=4, head_p=2, lsh_p=10, rsh_p=24, rel=60, lel=20)
_LEAN = dict(spine=22, head_p=-12, lsh_p=40, rsh_p=40, lel=50, rel=50)
_IDLE = dict(spine=3, head_p=4, lsh_p=6, rsh_p=8, lel=14, rel=18)
# KRAP depot (T2): reading, weight on one leg, painting - so nobody in the
# locker room stands in the same idle facing the lens.
_READ = dict(spine=2, head_p=-7, lsh_p=5, lsh_r=7, lel=12, rsh_p=4, rsh_r=6, rel=16,
             lhip_p=-3, lkn=9, rhip_p=3, rkn=2)          # chin up at the board
_WEIGHT = dict(spine=3, head_p=3, lsh_p=6, lsh_r=9, lel=14, rsh_p=7, rsh_r=8, rel=18,
               lhip_p=4, lkn=2, rhip_p=-3, rkn=10)       # weight on the left leg
_PAINTING = dict(spine=8, head_p=-10, lsh_p=12, lsh_r=10, lel=34,
                 lhip_p=6, lkn=8, rhip_p=-2, rkn=4)      # right arm: IK on the roller


def _person(r, key, pose, pos, look):
    if key == "biribel":      # every _person shot is after m5x_change: Guard black
        key = _BIRI_GUARD
    return r.add_humanoid(_hum(key), pose, pos, _yaw_to(pos, look), rifle_on=False)


def _shot(surface, t, cam, target, fov, build, sky=((16, 18, 28), (8, 9, 12)), rain=False,
          tag="", col=_LIAISON, post=None, dof=None, hh=0.01, roll=0.0, shk=None,
          seed=None):
    """``dof`` = camera distance (m) past which the set is softened, so the
    actors stay sharp against a defocused room (flush_split, both backends).
    ``hh`` = handheld drift (m); ``rain`` = world-space rain + night sky.
    ``tag`` = location/slate plate only - never a character name (T8).
    ``seed`` = handheld/sky/grain seed; defaults to ``len(tag)``. Shots whose
    old name tag was blanked pass the old length so motion stays identical."""
    if seed is None:
        seed = len(tag)
    r, buf = _m3d._rend()
    _m3d._cam(r, t, cam, target, fov, hh=hh, seed=seed % 7, roll=roll, shk=shk)
    if rain:
        _fx.night_sky(r, buf, t, sky[0], sky[1], stars=40, star_cut=0.7, clouds=4,
                      sodium=(40, 26, 14), seed=seed)
    else:
        buf.blit(_m3d._sky(_RW, _RH, sky[0], sky[1]), (0, 0))
    r.begin()
    build(r)
    if rain:
        _fx.rain3d(r, t, 77, lights=_STREET_LIGHTS)
    if dof is None:
        r.flush(buf)
    else:
        def _soften(s):
            w, h = s.get_size()
            sm = pygame.transform.smoothscale
            s.blit(sm(sm(s, (max(2, w // 3), max(2, h // 3))), (w, h)), (0, 0))
        r.flush_split(buf, dof, _soften)
    surface.fill((0, 0, 0))
    _m3d._present(surface, buf)
    if post is not None:            # full-res pass (paper text, backlight blur...)
        post(surface, r)
    _m3d._finish(surface, 7000 + seed, tag, col)


def _sil_hum():
    """Ucilev for the breach: his real kit and skin (a re-dyed black body read
    as blackface), but helmeted and balaclava'd, so the doorway backlight +
    _backlit_blur leave a blurred stranger - no face until the ending."""
    h = _SIL.get("hum")
    if h is None:
        from cutscenes.cast3d import humanoid3d  # lazy: see _m3d._hum
        h = humanoid3d("ucilev", rifle="sniper", hair_style="crop", helmet=(30, 31, 36),
                       mask=(34, 34, 38), brow_t=2)
        _SIL["hum"] = h
    return h


def _feather(w, h):
    """White RGBA card whose alpha falls off softly to the edges (ellipse)."""
    base = _SIL.get("feather")
    if base is None:
        base = pygame.Surface((48, 48), pygame.SRCALPHA)
        for y in range(48):
            for x in range(48):
                d = math.hypot((x - 23.5) / 23.5, (y - 23.5) / 23.5)
                a = max(0.0, min(1.0, (1.0 - d) / 0.45))
                base.set_at((x, y), (255, 255, 255, int(255 * a * a * (3 - 2 * a))))
        _SIL["feather"] = base
    return pygame.transform.smoothscale(base, (max(2, w), max(2, h)))


def _backlit_blur(surface, rect, k=0.07):
    """Heavy soft blur over ``rect`` (feathered), so a backlit figure dissolves
    into the glare: a blurry shape, not a drawn-in black face."""
    rect = pygame.Rect(rect).clip(pygame.Rect(0, SAFE_TOP, WIDTH, SAFE_BOT - SAFE_TOP))
    w, h = rect.size
    if w < 8 or h < 8:
        return
    sm = pygame.transform.smoothscale
    q = (max(2, w // 4), max(2, h // 4))
    s = sm(sm(surface.subsurface(rect).copy(), q), (max(2, int(w * k)), max(2, int(h * k))))
    s = sm(sm(s, q), (w, h))
    layer = pygame.Surface((w, h), pygame.SRCALPHA)
    layer.blit(s, (0, 0))
    layer.blit(_feather(w, h), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(layer, rect.topleft)


def _glare(surface, cx, cy, rad, col=(120, 104, 84), streak=True):
    """Additive warm bloom (+ anamorphic streak) - the light eats the edges."""
    rad = max(8, int(rad))
    key = ("glare", rad, col)
    g = _SIL.get(key)
    if g is None:
        g = pygame.Surface((rad * 2, rad * 2))
        for r_ in range(rad, 0, -2):
            f = (1 - r_ / rad) ** 1.6
            pygame.draw.circle(g, tuple(int(c * f) for c in col), (rad, rad), r_)
        _SIL[key] = g
    surface.blit(g, (int(cx - rad), int(cy - rad)), special_flags=pygame.BLEND_ADD)
    if streak:
        st = pygame.Surface((rad * 5, max(4, rad // 9)))
        hh = st.get_height()
        for y in range(hh):
            f = 1 - abs(y - hh / 2) / (hh / 2)
            pygame.draw.line(st, tuple(int(c * 0.45 * f) for c in col), (0, y), (rad * 5, y))
        st = pygame.transform.smoothscale(pygame.transform.smoothscale(st, (24, hh)),
                                          (rad * 5, hh))
        surface.blit(st, (int(cx - rad * 2.5), int(cy - hh / 2)), special_flags=pygame.BLEND_ADD)


def _silhouette(h=300):
    """2D fallback Ucilev: a soft, blurred charcoal shape with a warm rim -
    reads as a backlit figure, never as a flat black-painted person."""
    if h in _SIL:
        return _SIL[h]
    from cutscenes import figure_kit  # lazy: heavy module, only used for the breach
    tmp = pygame.Surface((h, h + 20), pygame.SRCALPHA)
    try:
        figure_kit.draw_character(tmp, "ucilev", h // 2, h + 10, h / 310.0, True)
    except Exception:
        pygame.draw.ellipse(tmp, (0, 0, 0), (h // 2 - 22, 20, 44, 52))
        pygame.draw.rect(tmp, (0, 0, 0), (h // 2 - 40, 70, 80, h - 70))
    mask = pygame.mask.from_surface(tmp)
    rim = mask.to_surface(setcolor=(255, 214, 170, 150), unsetcolor=(0, 0, 0, 0))
    body = mask.to_surface(setcolor=(52, 48, 50, 225), unsetcolor=(0, 0, 0, 0))
    out = pygame.Surface(tmp.get_size(), pygame.SRCALPHA)
    for dx, dy in ((-3, 0), (3, 0), (0, -3)):
        out.blit(rim, (dx, dy))
    out.blit(body, (0, 0))
    w, hh = out.get_size()
    sm = pygame.transform.smoothscale
    out = sm(sm(sm(out, (max(2, w // 9), max(2, hh // 9))), (w // 3, hh // 3)), (w, hh))
    _SIL[h] = out
    return out


# ── intro: the decree + the barracks (allegiance and old friends) ──
_KRAP_BLUE = (52, 86, 150)
_GUARD_BLACK = (26, 27, 31)
_SQUAD = (   # ex-KRAP squadmates: (skin, hair, kit) - kit: krap / half / guard
    ((176, 140, 112), (34, 28, 24), "krap"),
    ((198, 160, 128), (70, 50, 34), "half"),
    ((150, 112, 88), (20, 18, 16), "guard"),
    ((208, 170, 140), (110, 84, 54), "guard"),
)


def _squad_hum(i):
    key = ("squad", i)
    h = _SIL.get(key)
    if h is None:
        from cutscenes.cast3d import humanoid3d  # lazy: see _m3d._hum
        skin, hair, kit = _SQUAD[i]
        kw = dict(skin=skin, hair=hair)
        if kit == "krap":
            kw.update(beret=_KRAP_BLUE)
        elif kit == "half":     # Guard tunic on, KRAP beret still on his head
            kw.update(beret=_KRAP_BLUE, jacket=_GUARD_BLACK, vest=(38, 39, 44),
                      armband=(176, 36, 36), accent=_KRAP_BLUE)
        else:
            kw.update(helmet=(30, 31, 36), jacket=_GUARD_BLACK, vest=(38, 39, 44),
                      pants=(30, 31, 35), armband=(176, 36, 36), accent=(176, 36, 36),
                      pouches=True)
        h = humanoid3d("krap", **kw)
        _SIL[key] = h
    return h


_GUARD_ARMBAND = (176, 36, 36)


def _biribel_guard():
    """Pre-change Biribel (decree/squadmate): his own kit plus the Guard's red
    armband - the one visible sign on him that he now answers to the
    President. Cached by outfit in _m3d._cache["hum"] (core.outfits)."""
    return _hum(("biribel", "krap_armband"))


def _biribel_in(r, pose, pos, look, outfit="krap_armband"):
    return r.add_humanoid(_hum(("biribel", outfit)), pose, pos, _yaw_to(pos, look),
                          rifle_on=False)


def _decree_tex():
    tex = _SIL.get("decree")
    if tex is not None:
        return tex
    w, h = 420, 540
    tex = pygame.Surface((w, h))
    tex.fill((226, 220, 200))
    for y in range(0, h, 3):                                  # paper tooth
        pygame.draw.line(tex, (219, 212, 192), (0, y), (w, y))
    pygame.draw.rect(tex, (150, 120, 62), (10, 10, w - 20, h - 20), 2)
    pygame.draw.circle(tex, (176, 140, 70), (w // 2, 52), 26)
    pygame.draw.circle(tex, (226, 220, 200), (w // 2, 52), 18)
    pygame.draw.circle(tex, (150, 30, 32), (w // 2, 52), 10)

    def line(font, text, y, col=(30, 28, 30)):
        s = font.render(text, True, col)
        tex.blit(s, (w // 2 - s.get_width() // 2, y))
        return y + s.get_height()

    y = line(font_terminal_small, "REPUBLIC OF ACARISTAN", 86, (90, 70, 40))
    y = line(font_terminal, "PRESIDENTIAL DECREE No. 1", y + 6)
    pygame.draw.line(tex, (60, 50, 40), (40, y + 8), (w - 40, y + 8), 2)
    y = line(font_location, "KRAP IS DISSOLVED", y + 18, (150, 26, 28))
    for txt in ("ALL KRAP PERSONNEL ARE", "TRANSFERRED TO THE", "PRESIDENTIAL GUARD.",
                "", "THE GUARD ANSWERS TO", "THE PRESIDENT ALONE."):
        y = line(font_terminal, txt, y + 4) if txt else y + 10
    y = line(font_terminal_small, "- EFFECTIVE IMMEDIATELY -", y + 14, (150, 26, 28))
    pygame.draw.lines(tex, (30, 30, 60), False,                 # signature
                      [(250, h - 70), (268, h - 92), (280, h - 66), (300, h - 90),
                       (318, h - 70), (350, h - 78)], 3)
    sig = font_terminal_small.render(_T("m5mid3d.s_retardovici"), True, (60, 56, 60))
    tex.blit(sig, (250, h - 56))
    stamp = pygame.Surface((120, 120), pygame.SRCALPHA)
    pygame.draw.circle(stamp, (170, 30, 34, 170), (60, 60), 54, 5)
    pygame.draw.circle(stamp, (170, 30, 34, 120), (60, 60), 42, 2)
    gs = font_terminal.render(_T("m5mid3d.guard"), True, (170, 30, 34))
    stamp.blit(gs, (60 - gs.get_width() // 2, 60 - gs.get_height() // 2))
    tex.blit(pygame.transform.rotate(stamp, 18), (40, h - 150))
    _SIL["decree"] = tex
    return tex


def _photo_tex():
    """The squad photo pinned beside the decree: Y-3 intake, KRAP blue."""
    tex = _SIL.get("photo")
    if tex is not None:
        return tex
    w, h = 300, 210
    tex = pygame.Surface((w, h))
    tex.fill((236, 232, 220))
    pygame.draw.rect(tex, (120, 128, 120), (12, 12, w - 24, h - 52))
    pygame.draw.rect(tex, (84, 92, 84), (12, 12 + (h - 52) * 2 // 3, w - 24, (h - 52) // 3))
    try:
        from cutscenes import figure_kit  # lazy: see _silhouette
        for i, who in enumerate(("krap", "krap", "biribel", "krap", "krap")):
            cx = 44 + i * 53
            figure_kit.draw_character(tex, who, cx, h - 42, 0.5, i < 2)
            pygame.draw.ellipse(tex, _KRAP_BLUE, (cx - 17, h - 42 - 132, 34, 14))   # berets
    except Exception:
        pass
    cap = font_terminal_small.render(_T("m5mid3d.krap_4_y_3_intake"), True, (40, 40, 50))
    tex.blit(cap, (w // 2 - cap.get_width() // 2, h - 32))
    _SIL["photo"] = tex
    return tex


def _map_quad(surface, r, tex, quad, strips=24, tint=(235, 228, 212)):
    """Full-resolution texture on a camera-facing world quad (TL, TR, BR, BL):
    each vertical strip's ends are projected from 3D, so text stays crisp
    instead of going through the 0.6x render buffer."""
    tl, tr, br, bl = quad
    pts = []
    for i in range(strips + 1):
        u = i / strips
        top = tuple(a + (b - a) * u for a, b in zip(tl, tr))
        bot = tuple(a + (b - a) * u for a, b in zip(bl, br))
        pt, pb = r.project(top), r.project(bot)
        if pt is None or pb is None:
            return
        pts.append((_m3d._film_xy(pt), _m3d._film_xy(pb)))
    if pts[-1][0][0] <= pts[0][0][0]:
        return
    tw, th = tex.get_size()
    shade = tex.copy()
    shade.fill(tint, special_flags=pygame.BLEND_MULT)
    old_clip = surface.get_clip()
    surface.set_clip(pygame.Rect(0, SAFE_TOP, WIDTH, SAFE_BOT - SAFE_TOP))
    for i in range(strips):
        (t0, b0), (t1, b1) = pts[i], pts[i + 1]
        x0, x1 = t0[0], max(t0[0] + 1, t1[0])
        y0, y1 = min(t0[1], t1[1]), max(b0[1], b1[1])
        if y1 <= y0:
            continue
        c0 = int(tw * i / strips)
        c1 = max(c0 + 1, int(tw * (i + 1) / strips))
        col = shade.subsurface((c0, 0, c1 - c0, th))
        surface.blit(pygame.transform.smoothscale(col, (x1 - x0, y1 - y0)), (x0, y0))
    surface.set_clip(old_clip)


def _occl_mask(build_actors):
    """Full-res keep-mask (alpha 255 = may draw) for a paper post pass: the
    actors re-rendered alone into a transparent buffer, so the crisp quads can
    be punched out where a NEARER body covers them. The post pass draws after
    the whole 3D frame and would otherwise lay the paper over whoever stands
    between lens and board - which in the depot shots is every actor."""
    r, _buf = _m3d._rend()
    m = pygame.Surface((_RW, _RH), pygame.SRCALPHA)
    r.begin()
    build_actors(r)
    r.flush(m)
    keep = pygame.Surface((_RW, _RH), pygame.SRCALPHA)
    pygame.mask.from_surface(m).to_surface(keep, setcolor=(0, 0, 0, 0),
                                           unsetcolor=(255, 255, 255, 255))
    return pygame.transform.smoothscale(keep, (WIDTH, HEIGHT))


_BOARD = (-2.8, 1.55, 2.86)        # notice board centre on the depot's back wall
_DECREE_Q = ((-3.22, 1.98, 2.84), (-2.52, 1.98, 2.84), (-2.52, 1.08, 2.84), (-3.22, 1.08, 2.84))
_PHOTO_Q = ((-2.4, 1.92, 2.84), (-1.86, 1.92, 2.84), (-1.86, 1.54, 2.84), (-2.4, 1.54, 2.84))


_LOCKER_X = tuple(-0.4 + i * 0.62 for i in range(6))
_LOCKER_FACE_Z = 2.37            # front face of the locker row
_WET = (19, 20, 23)              # fresh Guard black
# Locker 3's black coat (0..1, left to right) as the intro plays: the set
# carries the beat - KRAP green going under the President's black.
_PAINT_DECREE = (0.20, 0.46)     # decree shot start/end: the painter at work
_PAINT_SQUAD = 0.48              # he stopped mid-stroke to watch the handshake
_PAINT_CHANGE = 0.62
_PAINT_DONE = 1.0                # barracks: the room is theirs now
_PAINTER = 0                     # squad man 0: still in KRAP blue, painting it out
_TRAY = (1.98, 0.0, 2.02)        # paint tray on the drop cloth
_HEAD_Y_SIGN = 1.0               # rig head_y sign vs _yaw_to (verified in shots)


def _head_turn(pos, yaw, look, lim=70.0):
    """head_y (deg) that turns a body at ``pos``/``yaw`` toward ``look``."""
    d = (_yaw_to(pos, look) - yaw + 180.0) % 360.0 - 180.0
    return max(-lim, min(lim, d)) * _HEAD_Y_SIGN


def _beam(r, a, b, w, h, col, bias=-0.04):
    """Box of cross-section ``w`` x ``h`` from point ``a`` to point ``b``."""
    from engine3d.core import box, m_apply, m_mul, rot_x, rot_y  # lazy: see _m3d._rend
    d = tuple(q - p for p, q in zip(a, b))
    ln = max(1e-4, math.sqrt(sum(c * c for c in d)))
    yaw = math.degrees(math.atan2(d[0], d[2]))
    pitch = -math.degrees(math.asin(max(-1.0, min(1.0, d[1] / ln))))
    R = m_mul(rot_y(yaw), rot_x(pitch))
    mid = tuple((p + q) / 2 for p, q in zip(a, b))
    m = box(w, h, ln, col)
    verts = [tuple(c + e for c, e in zip(mid, m_apply(R, v))) for v in m.verts]
    r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces], bias=bias)


def _roller(r, hand, head):
    """Paint roller: wooden handle from the fist to an x-aligned black sleeve."""
    from engine3d.core import box  # lazy: see _m3d._rend
    _beam(r, hand, (head[0], head[1] - 0.04, head[2] - 0.05), 0.026, 0.026, (150, 120, 70))
    _add(r, box(0.24, 0.065, 0.065, _WET, center=head))
    _add(r, box(0.25, 0.012, 0.012, (120, 122, 126), center=(head[0], head[1] - 0.04, head[2] - 0.03)))


def _painter_pose(t, paint, watch=0.0, look=None):
    """Solved pose for _painter (the IK reach is the costly part, so the
    decree shot solves it once and draws it twice: scene + occlusion mask)."""
    edge = _LOCKER_X[3] - 0.29 + 0.58 * paint
    pos = (edge - 0.02, 0, 1.72)
    yaw = _yaw_to(pos, (edge - 0.02, 0, 3.0))
    cyc = _work_cycle(t, 1600.0)
    y = lerp(0.62 + 0.9 * cyc, 1.18, watch)
    head = (edge - 0.02, y, _LOCKER_FACE_Z - 0.045)
    grip = (head[0] + 0.06, y - 0.30, head[2] - 0.36)
    pose = dict(_PAINTING, head_p=_PAINTING["head_p"] - 14 * (y - 1.0))
    if look is not None and watch > 0.0:
        pose["head_y"] = _head_turn(pos, yaw, look, 80.0) * watch
        pose["head_p"] = lerp(pose["head_p"], 2.0, watch)
        pose["spine"] = lerp(pose["spine"], 3.0, watch)
    hum = _squad_hum(_PAINTER)
    pose = _reach(hum, pose, pos, yaw, grip, "r", 1.0)
    return hum, pose, pos, yaw, head


def _painter_draw(r, pp):
    hum, pose, pos, yaw, head = pp
    j = r.add_humanoid(hum, pose, pos, yaw, rifle_on=False)
    _roller(r, j["rhand"], head)
    return pos


def _painter(r, t, paint, watch=0.0, look=None):
    """Squad man 0 (still in KRAP blue) rolling black over locker 3's leading
    edge. ``watch`` 0..1 stops him mid-stroke, roller parked on the door,
    and turns his head toward ``look``."""
    return _painter_draw(r, _painter_pose(t, paint, watch, look))


def _depot_set(r, t, bench=True, paint=_PAINT_DONE, roller=True):
    """The old KRAP depot locker room, mid-repaint: KRAP blue going under
    Guard black, a crate of black vests, the decree on the board.
    ``bench=False`` drops the long bench (it sliced through legs and arms
    in the barracks take). ``paint`` = how far locker 3's black coat has
    got (0..1, left to right); ``roller=False`` when the painter has the
    roller in his hand, otherwise it rests in the tray. The open corridor
    door on the left wall motivates the cold key light."""
    from engine3d.core import Light, box, quad_xz
    r.fog, r.fog_start, r.fog_end = (12, 13, 14), 7.0, 22.0
    r.light = Light(direction=(0.25, 0.85, -0.45), ambient=0.56, diffuse=0.8,
                    tint=(1.0, 1.04, 1.06))                       # cold fluorescent
    _add(r, quad_xz(-6, -5, 6, 3.0, 0.0, (50, 52, 50), seg=3))
    _add(r, box(12, 3.4, 0.2, (64, 70, 66), center=(0, 1.7, 3.0)))
    _add(r, box(5.6, 1.1, 0.05, _KRAP_BLUE, center=(-3.2, 0.55, 2.88)))      # KRAP blue dado
    _add(r, box(6.4, 1.1, 0.05, (24, 25, 28), center=(2.8, 0.55, 2.88)))     # ...painted black
    _add(r, box(0.08, 3.4, 9, (58, 62, 60), center=(-5.0, 1.7, -1.0)))
    for i in range(6):                                                       # lockers
        x = _LOCKER_X[i]
        # the far two are black already; locker 3 is being painted right now
        _add(r, box(0.58, 1.9, 0.5, (70, 82, 74) if i < 4 else (40, 41, 46), center=(x, 0.95, 2.62)))
        _add(r, box(0.04, 0.2, 0.02, (150, 150, 140), center=(x + 0.2, 1.05, 2.36)))
    if paint > 0.0:
        w = 0.58 * min(1.0, paint)
        x0 = _LOCKER_X[3] - 0.29
        _dec(r, box(w, 1.88, 0.01, _WET, center=(x0 + w / 2, 0.95, _LOCKER_FACE_Z - 0.012)), 0.5)
        if paint < 1.0:   # wet leading edge, a shade lighter so the stroke reads
            _dec(r, box(0.03, 1.88, 0.01, (46, 48, 52),
                        center=(x0 + w, 0.95, _LOCKER_FACE_Z - 0.014)), 0.6)
    _add(r, box(0.56, 1.86, 0.03, (78, 90, 82), center=(-0.06, 0.95, 2.1)))  # an open door
    # the KRAP crest, half covered by the Guard banner
    if not _decal.add(r, "presidential_crest", 1, (1.6, 2.6, 2.86), (1.0, 1.0), bias=0.6):
        _dec(r, box(1.0, 1.0, 0.04, _KRAP_BLUE, center=(1.6, 2.6, 2.88)), 0.6)
        _dec(r, box(0.5, 0.5, 0.03, (200, 190, 150), center=(1.6, 2.6, 2.85)), 0.8)
    if not _decal.add(r, "guard_banner", 0, (2.3, 2.35, 2.83), (0.9, 1.5), bias=1.0):
        _dec(r, box(0.9, 1.5, 0.03, (22, 22, 26), center=(2.3, 2.35, 2.84)), 1.0)
        _dec(r, box(0.9, 0.22, 0.02, (176, 34, 36), center=(2.3, 2.5, 2.82)), 1.2)
    # notice board (decree + squad photo get a full-res pass) + black armband
    bx, by, bz = _BOARD
    _dec(r, box(1.9, 1.3, 0.05, (120, 92, 60), center=(bx + 0.33, by, bz + 0.06)), 0.4)
    _dec(r, box(0.72, 0.92, 0.01, (200, 194, 176), center=(-2.87, 1.53, bz - 0.01)), 0.8)
    _dec(r, box(0.56, 0.4, 0.01, (200, 196, 186), center=(-2.13, 1.73, bz - 0.01)), 0.8)
    if not _decal.add(r, "armband", 0, (-2.13, 1.3, bz - 0.02), (0.5, 0.16), bias=1.0):
        _dec(r, box(0.5, 0.09, 0.02, (24, 24, 28), center=(-2.13, 1.3, bz - 0.02)), 1.0)
        _dec(r, box(0.5, 0.03, 0.01, (176, 34, 36), center=(-2.13, 1.3, bz - 0.035)), 1.2)
    # bench + crate of black vests and helmets
    if bench:
        _add(r, box(2.6, 0.1, 0.4, (96, 74, 50), center=(0.6, 0.45, 1.2)))
        for x in (-0.5, 1.7):
            _add(r, box(0.08, 0.42, 0.34, (40, 40, 44), center=(x, 0.21, 1.2)))
    _add(r, box(1.0, 0.55, 0.7, (70, 66, 50), center=(3.0, 0.28, 1.6)))
    for j in range(4):
        _add(r, box(0.8, 0.07, 0.55, (30, 31, 35), center=(3.0, 0.6 + j * 0.075, 1.6)))
    for hx in (2.75, 3.25):
        _add(r, box(0.26, 0.14, 0.28, (32, 33, 38), center=(hx, 0.95, 1.6)))
    _add(r, box(0.26, 0.05, 0.26, _KRAP_BLUE, center=(2.4, 0.03, 1.1)))       # dropped beret
    for i in range(3):                                                       # fluorescent tubes
        _add(r, box(1.4, 0.06, 0.12, (220, 232, 236), center=(-2.4 + i * 2.6, 3.2, 1.2),
                   emissive=True))
    _add(r, quad_xz(-3.6, 0.2, 3.6, 2.4, 0.01, (66, 70, 70), emissive=True))  # light on the floor
    # open corridor door on the left wall + its spill: the cold key comes from here
    _add(r, box(0.04, 2.2, 1.1, (188, 196, 200), center=(-4.95, 1.1, -0.7), emissive=True))
    _add(r, box(0.06, 0.08, 1.26, (40, 42, 44), center=(-4.93, 2.24, -0.7)))
    _add(r, quad_xz(-4.95, -1.35, -3.4, -0.05, 0.012, (72, 76, 76), emissive=True))
    # drop cloth, tray and tin under locker 3: the repaint is a job in progress
    _add(r, quad_xz(0.9, 1.72, 2.5, 2.34, 0.006, (128, 126, 118)))
    for sx, sz in ((1.2, 1.9), (1.55, 2.2), (2.2, 1.85), (1.75, 1.8)):
        _add(r, quad_xz(sx, sz, sx + 0.07, sz + 0.05, 0.009, _WET))
    tx, _ty, tz = _TRAY
    _add(r, box(0.34, 0.04, 0.24, (72, 72, 76), center=(tx, 0.026, tz)))
    _add(r, box(0.28, 0.01, 0.17, _WET, center=(tx, 0.05, tz)))
    _add(r, box(0.22, 0.28, 0.22, (148, 148, 144), center=(2.3, 0.15, 2.16)))   # paint tin
    _add(r, box(0.23, 0.01, 0.23, _WET, center=(2.3, 0.295, 2.16)))
    if roller:
        _roller(r, (tx + 0.42, 0.06, tz - 0.06), (tx, 0.08, tz))


# Decree beats (ms). The line types for ~6000 ms; the camera keeps drifting
# until 7400 so the frame never freezes while text is still coming in.
_DC_PUSH = (0, 4400)        # wide on the repaint -> over Biribel's shoulder on the board
_DC_DRIFT = (4400, 3000)    # slow settle after the push
_DC_TURN = (5000, 700)      # "We all are." - he turns from the board to the room
_DC_WATCH = (5300, 600)     # ...and the painter stops mid-stroke to look back
_DC_BPOS = (-1.35, 0, 1.62)


def _decree(surface, t):
    """Establish + decree. Opens wide on the depot being repainted (a KRAP
    man rolling black over his own locker, the blue dado, the Guard banner
    over the crest), then pushes in over Biribel's right shoulder until the
    decree is readable. On "We all are." he turns from the board toward the
    room and the painter stops to look back: that look motivates the cut to
    the squadmate walking in from screen right."""
    k = _k(t, *_DC_PUSH)
    drift = _k(t, *_DC_DRIFT)
    turn, watch = _k(t, *_DC_TURN), _k(t, *_DC_WATCH)
    paint = lerp(_PAINT_DECREE[0], _PAINT_DECREE[1], min(1.0, t / 5300.0))
    bpos = _DC_BPOS
    byaw = _yaw_to(bpos, (-2.75, 0, 2.86))
    br = math.sin(t * 0.0021)
    biri = dict(_READ, head_p=_READ["head_p"] + 7 * turn + br,
                head_y=_head_turn(bpos, byaw, (1.4, 0, 1.7), 75.0) * turn,
                spine=_READ["spine"] + 2 * turn)
    pp = _painter_pose(t, paint, watch, look=(bpos[0], 0, bpos[2]))

    def build_set(r):
        _depot_set(r, t, bench=False, paint=paint, roller=False)

    def build_actors(r):
        r.add_humanoid(_biribel_guard(), biri, bpos, byaw, rifle_on=False)
        _painter_draw(r, pp)

    def build(r):
        build_set(r)
        build_actors(r)

    def post(s, r):
        # crisp paper on a layer, masked by the actors: they stand between the
        # lens and the board, so an unmasked blit laid the photo over Biribel's
        # head as the push closed in
        layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        _map_quad(layer, r, _decree_tex(), _DECREE_Q)
        _map_quad(layer, r, _photo_tex(), _PHOTO_Q, strips=12)
        layer.blit(_occl_mask(build_actors), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        s.blit(layer, (0, 0))

    # (fov is horizontal: the end frame keeps Biribel head-to-waist, board left)
    cam = (lerp(1.5, -0.25, k) - 0.06 * drift, lerp(1.9, 1.74, k), lerp(-3.5, -1.75, k) + 0.08 * drift)
    target = (lerp(-0.6, -2.1, k), lerp(1.2, 1.56, k), lerp(2.4, 2.84, k))
    _shot(surface, t, cam, target, lerp(62, 42, k) - 1.5 * drift,
          build, sky=((14, 14, 16), (10, 10, 12)), tag="KRAP DEPOT // DECREE No. 1",
          col=_GUARD_RED, post=post)


def _reach(hum, pose, pos, yaw, target, side="r", w=1.0, lim=None):
    """Arm IK: blend ``side``'s arm (sh_p, sh_r, el) from the authored pose
    toward the angles that put that hand on ``target``. Coordinate descent
    with ``Humanoid.pose_world`` as the FK oracle - skeleton only, nothing is
    drawn while probing (the old solver probed with r.add_humanoid and left
    100-300 ghost bodies in every frame). ``w`` 0..1 = how far along the
    reach is, so the arm travels instead of snapping."""
    if w <= 0.0:
        return pose
    from engine3d.core import v_sub, v_len  # lazy: see _m3d._rend
    ks = (side + "sh_p", side + "sh_r", side + "el")
    src = [pose.get(ks[0], 8), pose.get(ks[1], 8), pose.get(ks[2], 12)]
    hand = side + "hand"

    # ``lim`` = ((lo, hi) sh_p, (lo, hi) sh_r, (lo, hi) el): keeps the solver
    # out of anatomically wrong minima (shoulder winging up/out behind the hand)
    lim = lim or ((-180.0, 180.0), (-180.0, 180.0), (0.0, 150.0))
    src = [max(lo, min(hi, v)) for v, (lo, hi) in zip(src, lim)]

    def err(a):
        if any(not (lo <= v <= hi) for v, (lo, hi) in zip(a, lim)):
            return 1e9
        p = dict(pose, **{ks[0]: a[0], ks[1]: a[1], ks[2]: a[2]})
        return v_len(v_sub(hum.pose_world(p, pos, yaw, rifle_on=False)[1][hand], target))

    cur, best, step = list(src), err(src), 12.0
    while step > 0.75:
        improved = True
        while improved:
            improved = False
            for i in range(3):
                for s in (step, -step):
                    cand = list(cur)
                    cand[i] += s
                    e = err(cand)
                    if e < best:
                        cur, best, improved = cand, e, True
        step /= 2
    cur[2] = max(0.0, min(150.0, cur[2]))
    return dict(pose, **{k: lerp(a, b, w) for k, a, b in zip(ks, src, cur)})


def _grip(r, clasp, yaw, skin_a, skin_b, s=1.0):
    """Two interlocked palms + thumb wraps at ``clasp``, aligned to the line
    between the two men (``yaw``), sized like hands - not a beige brick."""
    from engine3d.core import Mesh, box, m_apply, rot_y, mix_col  # lazy: see _m3d._rend
    m = Mesh()
    m.add(box(0.10, 0.045, 0.085, skin_a, center=(0.0, -0.018, 0.012)))      # his palm, under
    m.add(box(0.10, 0.045, 0.085, skin_b, center=(0.0, 0.022, -0.012)))      # the other, over
    m.add(box(0.03, 0.03, 0.06, mix_col(skin_a, (0, 0, 0), 0.12), center=(0.035, 0.05, 0.0)))
    m.add(box(0.03, 0.03, 0.06, mix_col(skin_b, (0, 0, 0), 0.12), center=(-0.035, -0.048, 0.0)))
    if s != 1.0:
        m.verts = [tuple(c * s for c in v) for v in m.verts]
    R = rot_y(yaw)
    verts = [tuple(c + d for c, d in zip(clasp, m_apply(R, v))) for v in m.verts]
    r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces], bias=-0.04)


def _fist(r, at, yaw, skin):
    """Closed hand wrapped over a shoulder at ``at``: the rig's own hand box
    vanishes against the tunic at this size, the prop keeps the grip legible."""
    from engine3d.core import Mesh, box, m_apply, rot_y, mix_col  # lazy: see _m3d._rend
    m = Mesh()
    m.add(box(0.09, 0.075, 0.11, skin))
    m.add(box(0.035, 0.03, 0.07, mix_col(skin, (0, 0, 0), 0.15), center=(0.0, 0.045, 0.03)))
    R = rot_y(yaw)
    verts = [tuple(c + d for c, d in zip(at, m_apply(R, v))) for v in m.verts]
    r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces], bias=-0.06)


def _held_vest(r, lh, rh, col=(30, 31, 35)):
    """A folded carrier held open in both hands. Built BETWEEN the rig's own
    solved hand joints, so both palms provably sit on it. The body of the vest
    hangs BELOW the grip line: a slab that straddles the hands swallows the
    palms at this buffer size and reads as a tray."""
    from engine3d.core import Mesh, box, m_apply, rot_y  # lazy: see _m3d._rend
    mid = tuple((a + b) / 2 for a, b in zip(lh, rh))
    w = math.dist(lh, rh)                      # local +z spans hand to hand
    m = Mesh()
    # read as a TUNIC, not a slab (M5 N07): lifted cloth tone, standing collar,
    # brass button placket, sleeves folded across the front with the red
    # armband showing, darker hem. Details sit on both broad faces (+-x).
    body = tuple(min(255, c + 12) for c in col)
    m.add(box(0.055, 0.26, w, body, center=(0.0, -0.17, 0.0),
              cols={"bottom": (18, 18, 20)}))                              # body, hanging
    m.add(box(0.075, 0.06, w * 0.46, (20, 20, 23), center=(0.0, -0.015, 0.0)))  # collar
    for sx in (-1, 1):
        fx = sx * 0.031
        m.add(box(0.006, 0.2, 0.022, (22, 22, 25), center=(fx, -0.16, 0.0)))   # placket
        for k in range(4):
            m.add(box(0.008, 0.014, 0.014, (176, 140, 62), center=(fx * 1.08, -0.07 - k * 0.05, 0.0)))
        m.add(box(0.008, 0.05, w * 0.9, (20, 20, 23), center=(sx * 0.032, -0.135, 0.0)))  # folded sleeves
        m.add(box(0.01, 0.045, 0.06, (176, 36, 36), center=(sx * 0.036, -0.135, w * 0.28)))  # armband
        m.add(box(0.006, 0.03, w * 0.96, (18, 18, 20), center=(sx * 0.03, -0.285, 0.0)))  # hem
    R = rot_y(_yaw_to(lh, rh))
    verts = [tuple(c + d for c, d in zip(mid, m_apply(R, v))) for v in m.verts]
    r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces], bias=-0.05)


# Squadmate handshake timing (ms from shot start; the line holds >= 4200 ms).
# State | start | length | notes
_SM_WALK = (0, 1000)      # mate closes the gap, walk cycle easing out
_SM_REACH = (380, 720)    # his hand comes up while he's still walking (anticipation)
_SM_TAKE = (760, 600)     # Biribel's hand: a beat late - he's not sure about the black
_SM_PUMP = (1300, 950)    # contact -> 2.5 pumps, decaying
_SM_CLAP = (1650, 520)    # left hand lands on Biribel's shoulder and stays
_SM_CLOSE = (1500, 800)   # the pumps pull the two in to bro-grip distance
_SM_PUMP_AMP = 0.055      # m, first pump
_SM_GAP = 0.95            # m between them at the clasp
_SM_GAP_HELD = 0.84       # m once the grip pulls them in (0.74 left 0.24 m between chests:
                          # the clap arm had nowhere to go but through Biribel's chest)
_SM_DOUBT = (4300, 700)   # "Y-3 intake -": his eyes drop
_SM_UP = (6400, 500)      # ...and come back up to the mate
_SM_NOD = 7150            # the smallest nod on "Right?"
_SM_LEN = 7400            # camera push spans the whole typed line (~7.5 s)
_SM_CLASP_Y = 1.25        # m, chest-high clasp: reads against the wall, not the belt


def _squadmate(surface, t):
    """The old squadmate (Guard tunic, KRAP beret still on) walks up and
    shakes Biribel's hand, then claps his shoulder - establishes that the men
    in black are his friends."""
    k = _k(t, 0, _SM_LEN)
    walk = _k(t, *_SM_WALK)
    reach, take = _k(t, *_SM_REACH), _k(t, *_SM_TAKE)
    clap, close = _k(t, *_SM_CLAP), _k(t, *_SM_CLOSE)
    hold = min(reach, take)
    u = max(0.0, min(1.0, (t - _SM_PUMP[0]) / _SM_PUMP[1]))
    pump = (_SM_PUMP_AMP * math.sin(u * 5 * math.pi) * (1 - u) ** 1.5) if 0 < u < 1 else 0.0
    hit = math.exp(-((t - _SM_PUMP[0]) / 160.0) ** 2)     # contact accent: lean + nod

    bpos = (-0.9, 0, 0.7)
    m0 = (0.75, 0, 1.55)
    d2 = (m0[0] - bpos[0], m0[2] - bpos[2])
    dl = math.hypot(*d2)
    d = (d2[0] / dl, d2[1] / dl)                          # axis Biribel -> mate
    gap = lerp(_SM_GAP, _SM_GAP_HELD, close)
    m1 = (bpos[0] + d[0] * gap, 0, bpos[2] + d[1] * gap)
    mpos = tuple(lerp(a, b, walk) for a, b in zip(m0, m1))
    yaw_m, yaw_b = _yaw_to(mpos, bpos), _yaw_to(bpos, mpos)
    mid = ((bpos[0] + mpos[0]) / 2, (bpos[2] + mpos[2]) / 2)
    clasp = (mid[0], _SM_CLASP_Y + pump, mid[1])

    stride = (1 - walk) ** 0.6 * (1.0 if t < _SM_WALK[1] else 0.0)
    # Distance-driven phase (4.65 rad/m = 1.35 m cycle): the old t-driven
    # cycle skated - 11 rad over ~0.95 m is a 0.54 m shuffle at 2x cadence.
    walked = walk * max(0.0, dl - gap)
    mate = dict(_m3d._walk(walked * 4.65, 0.85 * stride), rifle_p=60)
    mate.update(spine=4 + 7 * reach + 4 * hit, head_p=-4 + 7 * hit + 6 * hold, head_y=0,
                rsh_p=lerp(6, 45, reach), rsh_r=lerp(8, -20, reach), rel=lerp(20, 30, reach),
                lsh_p=lerp(mate.get("lsh_p", 6), 10, walk), lsh_r=8, lel=lerp(20, 30, walk))
    # "we've always covered each other": his eyes drop to the black sleeve on
    # his hand, come back up, and he gives the smallest nod on "Right?"
    doubt = _k(t, *_SM_DOUBT) * (1.0 - _k(t, *_SM_UP))
    nod = math.exp(-((t - _SM_NOD) / 170.0) ** 2)
    lean = _k(t, _SM_UP[0], 500)
    mate["spine"] += 3 * lean
    biri = dict(_IDLE, spine=3 + 5 * take + 3 * hit, head_p=2 + 6 * hit + 5 * hold + 13 * doubt + 7 * nod,
                head_y=0,
                rsh_p=lerp(8, 45, take), rsh_r=lerp(8, -20, take), rel=lerp(18, 30, take))
    # each hand travels toward where the clasp WILL be, so they meet in the middle
    mate = _reach(_squad_hum(1), mate, mpos, yaw_m, clasp, "r", reach)
    biri = _reach(_biribel_guard(), biri, bpos, yaw_b, clasp, "r", take)
    if clap > 0:   # bro grip: mate's free hand on Biribel's right shoulder
        _pl, j, _off = _biribel_guard().pose_world(biri, bpos, yaw_b, rifle_on=False)
        rb = (d[1], -d[0])                                # Biribel's right, world (x,z)
        # target the TOP SURFACE of the shoulder, a little toward the mate - the
        # old target (chest + 0.30 lateral) was the joint inside the torso, so
        # the IK buried the forearm in his chest to reach it
        sh = (j["chest"][0] + rb[0] * 0.19 + d[0] * 0.05, j["chest"][1] + 0.17,
              j["chest"][2] + rb[1] * 0.19 + d[1] * 0.05)
        mate = _reach(_squad_hum(1), mate, mpos, yaw_m, sh, "l", clap)

    def build(r):
        _depot_set(r, t, paint=_PAINT_SQUAD, roller=False)
        ja = r.add_humanoid(_squad_hum(1), mate, mpos, yaw_m, rifle_on=False)
        jb = r.add_humanoid(_biribel_guard(), biri, bpos, yaw_b, rifle_on=False)
        if min(reach, take) > 0.9 and math.dist(ja["rhand"], jb["rhand"]) < 0.22:
            c = tuple((a + b) / 2 for a, b in zip(ja["rhand"], jb["rhand"]))
            _grip(r, c, yaw_b, _squad_hum(1).spec["skin"], _biribel_guard().spec["skin"], 1.35)
        if clap > 0.85:
            _fist(r, ja["lhand"], yaw_m, _squad_hum(1).spec["skin"])
        # the room keeps moving: the painter from the decree shot has stopped
        # mid-stroke, roller parked on the locker, and watches the two of them
        _painter(r, t, _PAINT_SQUAD, 1.0, look=(mid[0], 0, mid[1]))

    # profile two-shot from Biribel's right: his reaching arm is the near arm
    # and the clasp hangs in open space against the lockers, never behind a back
    perp = (d[1], -d[0])
    side = 2.90 - 0.20 * k
    axial = -0.45 + 0.20 * k
    cam = (mid[0] + perp[0] * side + d[0] * axial, 1.52 - 0.04 * k,
           mid[1] + perp[1] * side + d[1] * axial)
    # aim between the clasp and the faces so neither head is cut by the frame top
    target = (mid[0] + d[0] * 0.10, 1.50 - 0.03 * k, mid[1] + d[1] * 0.10)
    focus = math.dist(cam, (mid[0], _SM_CLASP_Y, mid[1]))
    _shot(surface, t, cam, target, 52 - 4 * k, build, sky=((14, 14, 16), (10, 10, 12)),
          tag="KRAP 4 // Y-3 INTAKE", col=_GUARD_RED, dof=focus + 1.4)


def _work_cycle(t, period, phase=0.0):
    """Effort curve for repetitive hand work: pull, wrestle, settle, rest.
    A plain sine at these amplitudes reads as waving both arms."""
    from engine3d.core import smooth  # lazy: see _m3d._rend
    u = (t / float(period) + phase) % 1.0
    if u < 0.35:
        return smooth(u / 0.35)
    if u < 0.55:
        return 1.0
    if u < 0.85:
        return 1.0 - smooth((u - 0.55) / 0.30)
    return 0.0


_BR_LEN = 6400             # push spans the typed line (~6.4 s)
_BR_TURN = (3500, 900)     # "If this turns" - the man in black turns to Biribel
_BR_LOOKUP = (4700, 700)   # the one still in blue looks up from his vest


def _barracks(surface, t):
    """The unit kitting up into the President's black while Biribel watches.

    Rebuilt for legibility. The old take IK-pinned every hand to its own
    chest (straps, collars, a vest at arm's length), nodded every head 10-16
    degrees and ran the bench straight through the group: at this buffer size
    that read as missing legs, limbs sinking into torsos and a room full of
    drowsy men. Now: no bench, no IK, no props crossing a body, heads level,
    every actor fully in frame with clear air around him (>= 0.9 m apart,
    >= 0.5 m off the lockers/crate so the software painter can't interleave
    them). The story beat is carried by blocking alone: three men in black,
    one still in KRAP blue with the vest hanging from his hand, and the
    fully-changed man turning to meet Biribel's eyes late in the shot."""
    from engine3d.core import smooth  # lazy: see _m3d._rend
    k = _k(t, 0, _BR_LEN)
    turn = _k(t, *_BR_TURN)                           # 2 turns to Biribel on "If this turns"
    look_up = _k(t, *_BR_LOOKUP)                      # 0 lifts his eyes off the vest
    bpos = (-2.25, 0, -0.80)
    hang = dict(lsh_p=6, lsh_r=9, lel=10, rsh_p=6, rsh_r=9, rel=10)   # arms loose, off the hip

    p0, p1, p2, p3 = (2.85, 0, 0.30), (-0.15, 0, 1.60), (1.05, 0, 0.30), (0.90, 0, 1.75)
    y0 = _yaw_to(p0, (0.6, 0, -1.2))                  # 0: half-turned to the room
    y1 = _yaw_to(p1, p3)                               # 1 and 3: talking to each other
    y3 = _yaw_to(p3, p1)
    ya, yb = _yaw_to(p2, (0.4, 0, -1.6)), _yaw_to(p2, bpos)
    yb = ya + ((yb - ya + 180.0) % 360.0 - 180.0)      # shortest way round
    y2 = lerp(ya, yb, turn)
    # tiny breathing/nod so nobody is a statue, never enough to read as a nod-off
    br = lambda ph: 1.2 * math.sin(t * 0.0021 + ph)
    pose0 = dict(_IDLE, spine=3 + 3 * (1 - look_up), head_p=2 + 14 * (1 - look_up) + br(0.0),
                 lsh_p=10, lsh_r=16, lel=14,
                 rsh_p=6, rsh_r=9, rel=10)            # left hand held out, clear of the thigh
    pose1 = dict(_IDLE, spine=3, head_p=1 + br(1.3), **hang)
    pose2 = dict(_IDLE, spine=2, head_p=1 + br(2.1), **hang)
    pose3 = dict(_WEIGHT, head_p=1 + br(0.7), **hang)

    def build(r):
        _depot_set(r, t, bench=False)
        j0 = r.add_humanoid(_squad_hum(0), pose0, p0, y0, rifle_on=False)
        _hanging_vest(r, j0["lhand"], y0)          # lens-side hand, so the vest reads
        r.add_humanoid(_squad_hum(1), pose1, p1, y1, rifle_on=False)
        r.add_humanoid(_squad_hum(2), pose2, p2, y2, rifle_on=False)
        r.add_humanoid(_squad_hum(3), pose3, p3, y3, rifle_on=False)
        # Biribel: three-quarter back to the lens, looking across his unit
        # already in the black (m5x_change): bare head among helmets
        _biribel_in(r, dict(_IDLE, head_p=1, lsh_p=5, lsh_r=8, rsh_p=5, rsh_r=8,
                            head_y=-12.0 * _HEAD_Y_SIGN * turn),
                    bpos, (0.9, 0, 1.0), OUTFIT_GUARD)

    # wide-ish two-plane frame from behind Biribel's left side, slow push-in;
    # everyone head to boots in shot
    cam = (-3.55 + 0.25 * k, 1.62, -3.35 + 0.30 * k)
    target = (0.85, 1.12, 0.95)
    _shot(surface, t, cam, target, 50 - 2 * k, build, sky=((14, 14, 16), (10, 10, 12)),
          tag="KRAP DEPOT // NOW PRESIDENTIAL GUARD", col=_GUARD_RED,
          dof=math.dist(cam, target) + 2.2)


def _hanging_vest(r, hand, yaw, col=(30, 31, 35), band=(176, 36, 36)):
    """A Guard vest dangling from one hand by its shoulder strap, hanging
    straight down outside the thigh - no second hand, no IK."""
    from engine3d.core import Mesh, box, m_apply, rot_y  # lazy: see _m3d._rend
    m = Mesh()
    m.add(box(0.03, 0.10, 0.03, (24, 25, 28), center=(0.0, -0.05, 0.0)))     # strap in the fist
    # panel spans the actor's forward axis (local z), so it hangs parallel to
    # his leg instead of cutting across it
    m.add(box(0.05, 0.40, 0.32, col, center=(0.0, -0.30, 0.0)))             # vest panel
    if band:
        m.add(box(0.055, 0.04, 0.33, band, center=(0.0, -0.22, 0.0)))  # red band
    R = rot_y(yaw)
    verts = [tuple(c + d for c, d in zip(hand, m_apply(R, v))) for v in m.verts]
    r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces], bias=-0.03)


# Change beat timing (ms from shot start). The quartermaster's line types
# for ~6300 ms; meta min_ms == _CH_END, so the patch close-up and its silent
# beat always play before the player can move on.
# State             | start | length | notes
_CH_SLIDE = (0, 1150)       # QM slides the folded black tunic across the counter
_CH_DOWN = (250, 700)       # "Tunic, armband, helmet." - Biribel's eyes drop to it
_CH_TAP = (2250, 650)       # "Sign for them." - QM taps the docket
_CH_UP = (2500, 600)        # ...Biribel looks up at him
_CH_REACH = (3750, 600)     # "The blue goes in the bin" - fingers to the old patch
_CH_RIP = (4500, 200)       # the tear: fast, up and out, the old vest drops
_CH_CUT = 5000              # match cut on the patch -> close-up on his new black chest
_CH_PRESS = (5000, 520)     # CU: the hand brings the patch in
_CH_SET = (5520, 160)       # contact: one hard press
_CH_LEAVE = (6250, 450)     # the hand slides away - blue on black, no words
_CH_LIFT = (6750, 800)      # camera tilts up as his head comes up level
_CH_END = 7700              # == meta min_ms; then the frame holds on his face
_CH_BPOS = (0.25, 0, 1.80)  # Biribel, lockers side of the issue counter
_CH_QPOS = (1.0, 0, 0.60)   # quartermaster, camera side
_COUNTER = (0.65, 0.92, 1.12)   # issue counter: centre x, top y, centre z
_TUNIC_A, _TUNIC_B = (0.9, 0.955, 1.02), (0.55, 0.955, 1.2)
_DOCKET = (1.48, 0.924, 1.02)
_OLD_GREEN = (60, 72, 62)       # his KRAP field vest


def _qm_hum():
    h = _SIL.get("qm")
    if h is None:
        from cutscenes.cast3d import humanoid3d  # lazy: see _m3d._hum
        h = humanoid3d("krap", skin=(186, 146, 118), hair=(96, 92, 88), beret=_GUARD_BLACK,
                       jacket=_GUARD_BLACK, vest=(38, 39, 44), pants=(30, 31, 35),
                       armband=_GUARD_ARMBAND, accent=_GUARD_ARMBAND)
        _SIL["qm"] = h
    return h


def _fwd(yaw):
    """(forward, right) unit vectors in world x/z for a body at ``yaw``."""
    f = (math.sin(math.radians(yaw)), math.cos(math.radians(yaw)))
    return f, (f[1], -f[0])


def _patch(r, at, yaw, col=KRAP_MARK, s=1.0, bias=-0.08):
    """The KRAP patch (or its dark ghost / a cover) as a thin plate facing ``yaw``."""
    from engine3d.core import box, m_apply, rot_y  # lazy: see _m3d._rend
    m = box(0.11 * s, 0.075 * s, 0.012, col)
    R = rot_y(yaw)
    verts = [tuple(c + d for c, d in zip(at, m_apply(R, v))) for v in m.verts]
    r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces], bias=bias)


def _palm(r, at, yaw, skin):
    """Open hand pressed flat (close-up scale): palm, thumb, finger line."""
    from engine3d.core import Mesh, box, m_apply, rot_y, mix_col  # lazy: see _m3d._rend
    m = Mesh()
    m.add(box(0.085, 0.10, 0.028, skin))
    m.add(box(0.026, 0.05, 0.026, mix_col(skin, (0, 0, 0), 0.1), center=(0.05, -0.02, 0.004)))
    m.add(box(0.086, 0.006, 0.03, mix_col(skin, (0, 0, 0), 0.22), center=(0.0, 0.022, 0.0)))
    R = rot_y(yaw)
    verts = [tuple(c + d for c, d in zip(at, m_apply(R, v))) for v in m.verts]
    r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces], bias=-0.1)


def _issue_counter(r, t):
    """QM's issue counter (replaces the bench in this shot) + the kit on it:
    folded black tunic sliding over, Guard helmet, docket and pen."""
    from engine3d.core import box  # lazy: see _m3d._rend
    cx, top, cz = _COUNTER
    _add(r, box(2.1, 0.05, 0.42, (104, 80, 54), center=(cx, top - 0.025, cz)))
    _add(r, box(2.1, 0.86, 0.03, (66, 60, 50), center=(cx, 0.45, cz - 0.2)))   # front panel
    s = _k(t, *_CH_SLIDE)
    tun = tuple(lerp(a, b, s) for a, b in zip(_TUNIC_A, _TUNIC_B))
    _add(r, box(0.4, 0.06, 0.3, (30, 31, 35), center=tun))
    _add(r, box(0.41, 0.012, 0.06, _GUARD_ARMBAND, center=(tun[0], tun[1] + 0.036, tun[2] - 0.07)))
    _add(r, box(0.26, 0.14, 0.28, (32, 33, 38), center=(1.18, top + 0.07, 1.22)))   # helmet
    _add(r, box(0.27, 0.025, 0.06, _GUARD_ARMBAND, center=(1.18, top + 0.1, 1.09)))
    _add(r, box(0.22, 0.008, 0.3, (214, 208, 190), center=_DOCKET))
    _add(r, box(0.012, 0.012, 0.16, (30, 30, 34),
                center=(_DOCKET[0] + 0.14, _DOCKET[1] + 0.01, _DOCKET[2])))
    return tun


def _quartermaster(r, t, tun):
    """Back to the lens, left shoulder in the foreground of the OTS: slides
    the tunic over, then taps the docket on "Sign for them."."""
    pos = _CH_QPOS
    yaw = _yaw_to(pos, _CH_BPOS)
    hum = _qm_hum()
    pose = dict(_WEIGHT, head_p=4)
    sw = _k(t, 0, 200) * (1.0 - _k(t, 1050, 350))
    if sw > 0.0:
        pose["spine"] = 3 + 12 * sw
        pose["head_p"] = 4 + 14 * sw
        pose = _reach(hum, pose, pos, yaw, (tun[0], tun[1] + 0.05, tun[2]), "r", sw)
    tw = _k(t, _CH_TAP[0] - 200, 200) * (1.0 - _k(t, _CH_TAP[0] + _CH_TAP[1], 300))
    if tw > 0.0:
        u = max(0.0, min(1.0, (t - _CH_TAP[0]) / float(_CH_TAP[1])))
        bob = 0.05 * abs(math.sin(u * 2 * math.pi))          # two taps
        pose["spine"] = pose.get("spine", 3) + 6 * tw
        pose = _reach(hum, pose, pos, yaw, (_DOCKET[0], _DOCKET[1] + 0.03 + bob, _DOCKET[2]),
                      "r", tw)
    r.add_humanoid(hum, pose, pos, yaw, rifle_on=False)


def _change_ots(surface, t):
    """Over the quartermaster's left shoulder (Biribel stays screen-left,
    looking right, as in the squadmate two-shot). He holds his old KRAP vest
    at the waist; on "the blue goes in the bin" he tears its patch off."""
    from engine3d.core import ease_out, v_lerp  # lazy: see _m3d._rend
    bpos = _CH_BPOS
    byaw = _yaw_to(bpos, _CH_QPOS)
    f, rg = _fwd(byaw)
    br = math.sin(t * 0.0021)
    down = _k(t, *_CH_DOWN) * (1.0 - _k(t, *_CH_UP))
    reach = _k(t, *_CH_REACH)
    rip_u = max(0.0, min(1.0, (t - _CH_RIP[0]) / float(_CH_RIP[1])))
    torn = rip_u >= 0.35
    look_up = _k(t, _CH_RIP[0] + 100, 300)
    pose = dict(_IDLE, spine=3 + 3 * down + 6 * reach - 3 * look_up,
                head_p=4 + 18 * down + lerp(22 * reach, 9, look_up) + br,
                lsh_p=28, lsh_r=10, lel=72, rsh_p=28, rsh_r=10, rel=72)
    hum = _hum(("biribel", "krap_armband"))
    _pl, j0, _o = hum.pose_world(pose, bpos, byaw, rifle_on=False)     # grip: both hands on the vest
    lh, rh = j0["lhand"], j0["rhand"]
    mid = tuple((a + b) / 2 for a, b in zip(lh, rh))
    dl = max(1e-4, math.dist(lh, rh))
    u = tuple((b - a) / dl for a, b in zip(lh, rh))
    patch = (mid[0] + f[0] * 0.036 + u[0] * 0.07, mid[1] - 0.12, mid[2] + f[1] * 0.036 + u[2] * 0.07)
    if reach > 0.0:
        on = (patch[0] + f[0] * 0.02, patch[1], patch[2] + f[1] * 0.02)
        out = (patch[0] + rg[0] * 0.16 + f[0] * 0.10, patch[1] + 0.40,
               patch[2] + rg[1] * 0.16 + f[1] * 0.10)
        pose = _reach(hum, pose, bpos, byaw, v_lerp(on, out, ease_out(rip_u)), "r", reach)
    k = _k(t, 3500, 1500)                    # push in on the decision

    def build(r):
        _depot_set(r, t, bench=False, paint=_PAINT_CHANGE)
        tun = _issue_counter(r, t)
        j = r.add_humanoid(hum, pose, bpos, byaw, rifle_on=False)
        if not torn:
            _held_vest(r, lh, rh, col=_OLD_GREEN)
            _patch(r, patch, byaw)
        else:
            _hanging_vest(r, j["lhand"], byaw + 90.0, col=_OLD_GREEN, band=None)
            g = j["lhand"]
            _patch(r, (g[0] + f[0] * 0.03, g[1] - 0.25, g[2] + f[1] * 0.03), byaw, (34, 40, 36))
            h = j["rhand"]
            _patch(r, (h[0] + f[0] * 0.04, h[1] + 0.02, h[2] + f[1] * 0.04), byaw)
        _quartermaster(r, t, tun)

    # behind and 0.8 m left of the QM: his head/shoulder hold frame right,
    # Biribel left of centre, ~14 deg of clear air between them
    cam = (lerp(1.12, 1.02, k), lerp(1.8, 1.76, k), lerp(-1.45, -1.15, k))
    target = (0.42, lerp(1.46, 1.42, k), 1.6)
    _shot(surface, t, cam, target, lerp(46, 40, k), build, sky=((14, 14, 16), (10, 10, 12)),
          tag="KRAP DEPOT // ISSUE: PRESIDENTIAL BLACK", col=_GUARD_RED,
          dof=math.dist(cam, target) + 1.4)


def _change_cu(surface, t):
    """Close-up on his new black chest, from the quartermaster's eyeline: his
    right hand brings the torn blue patch in, presses it on hard, slides
    away. Silence. The camera tilts up as his head comes up level - bare
    head, blue on black - and holds."""
    from engine3d.core import m_apply, rot_y, v_lerp  # lazy: see _m3d._rend
    bpos = _CH_BPOS
    byaw = _yaw_to(bpos, _CH_QPOS)
    f, rg = _fwd(byaw)
    hum = _hum(_BIRI_GUARD)
    lift = _k(t, *_CH_LIFT)
    br = math.sin(t * 0.0021)
    sp = 4.0 - 1.5 * lift
    pose = dict(_IDLE, spine=sp, head_p=lerp(26, 3, _k(t, _CH_LIFT[0] + 150, 650)) + br,
                rsh_p=18, rsh_r=10, rel=30)
    _pl, j, _o = hum.pose_world(pose, bpos, byaw, rifle_on=False)
    c, s_ = math.cos(math.radians(sp)), math.sin(math.radians(sp))
    off = m_apply(rot_y(byaw), (-0.1, 0.42 * c - 0.16 * s_, 0.16 * c + 0.42 * s_))
    patch = tuple(a + b for a, b in zip(j["pelvis"], off))
    fw = (f[0], 0.0, f[1])
    rw = (rg[0], 0.0, rg[1])
    at = lambda o, a, b, c3: tuple(o[i] + rw[i] * a + fw[i] * c3 + (b if i == 1 else 0.0)
                                  for i in range(3))
    press, leave = _k(t, *_CH_PRESS), _k(t, *_CH_LEAVE)
    hit = math.exp(-((t - (_CH_SET[0] + 60)) / 90.0) ** 2)
    contact = t >= _CH_SET[0]
    on = at(patch, 0.0, 0.0, 0.03 - 0.012 * hit)
    palm = v_lerp(v_lerp(at(patch, 0.34, -0.30, 0.30), on, press), at(patch, 0.36, -0.34, 0.22), leave)
    elbow = at(palm, 0.30, -0.25, 0.06)
    skin = hum.spec["skin"]

    def build(r):
        _depot_set(r, t, bench=False, paint=_PAINT_CHANGE)
        r.add_humanoid(hum, pose, bpos, byaw, rifle_on=False)
        if not contact:      # the patch isn't on him yet: hide the rig's own
            _patch(r, at(patch, 0.0, -0.004, 0.022), byaw, (38, 38, 41), 1.4, -0.07)
        if leave < 1.0:
            _beam(r, elbow, palm, 0.075, 0.075, _GUARD_BLACK, bias=-0.09)
            _palm(r, palm, byaw, skin)
            if not contact:
                _patch(r, at(palm, -0.004, 0.0, -0.02), byaw)

    k = _k(t, _CH_CUT, 2700)
    # the lift dollies back as it tilts up: patch at the bottom edge, bare
    # head at the top (fov is horizontal)
    cam = at(patch, -0.05, 0.05 + 0.17 * lift, 0.84 - 0.06 * k + 0.56 * lift)
    target = at(patch, 0.03, 0.02 + 0.2 * lift, 0.0)
    _shot(surface, t, cam, target, 30 + 10 * lift, build, sky=((14, 14, 16), (10, 10, 12)),
          tag="KRAP DEPOT // ISSUE: PRESIDENTIAL BLACK", col=_GUARD_RED,
          dof=0.84 + 0.5)


def _change(surface, t):
    """m5x_change - Biribel is issued the President's black (T2 re-stage).

    OTS over the quartermaster: the tunic slides across the counter, he taps
    the docket, and on "The blue goes in the bin" Biribel tears the KRAP
    patch off his old vest. Match cut on the patch to a close-up of his new
    black chest: he presses it on, the hand leaves, silence, the camera
    tilts up to his bare head. The Guard helmet stays on the counter: bare
    head + blue patch keep him readable among the Guard for the rest of M5.
    The costume change happens across the cut - no on-screen undressing."""
    if t < _CH_CUT:
        _change_ots(surface, t)
    else:
        _change_cu(surface, t)


# ── scenes (3D) ──
def _arrival_wide(surface, t):
    k = _k(t, 0, 5200)
    z = -2.0 + 5.0 * k
    def build(r):
        _night_street(r)
        _street_set(r, t)
        # stride follows distance walked (no foot-slide on the ease-out), fades to a stand
        # 4.65 rad/m = 1.35 m per full cycle (2 steps), same as the finale gait.
        _person(r, "biribel", _m3d._walk(4.65 * 5.0 * k, 0.9 * min(1.0, (1.0 - k) / 0.12)),
                (0.4, 0, z), (0, 0, 12))
    if t < 3000:     # angle 1: low follow from behind, the street ahead
        _shot(surface, t, (-3.4, 0.6, z - 8.0), (0.3, 4.4, 10), 72,
              build, sky=((22, 24, 36), (40, 30, 30)), rain=True,
              tag="LOWER QUARTER // MAG PRINT WORKS", col=(230, 190, 120))
    else:            # angle 2: low 3/4 side, the print works rising behind her
        _shot(surface, t, (3.4, 1.2, z - 0.2), (0.4, 1.5, z + 1.2), 62,
              build, sky=((22, 24, 36), (40, 30, 30)), rain=True, hh=0.015,
              tag="LOWER QUARTER // MAG PRINT WORKS", col=(230, 190, 120))


def _arrival_door(surface, t):
    k = _k(t, 300, 3200)
    def build(r):
        _night_street(r)
        _street_set(r, t, door=k)       # real opening + press hall + rolling shutter (T10)
        # rim light: the hall spills warm light onto her back as it opens
        _spr(r, (-1.0, 1.45, 8.55), _fx.glow(_PW_WARM, 0.95, intensity=0.42 * k))
        _person(r, "biribel", _IDLE, (-1.0, 0.18, 8.3), (0.3, 1, 10))   # stands on the kerb
    _shot(surface, t, (2.1, 1.55, 5.9 + k * 0.3), (-0.3, 1.5, 9.6), 58, build,
          sky=((22, 24, 36), (40, 30, 30)), rain=True, tag="MAG PRINT WORKS", col=(230, 190, 120))


def _rack(t, near, t0=0, dur=700, far=40.0):
    """Rack focus for close-ups: the cut lands with the whole room sharp, then
    focus pulls in to the speaker (``near`` m) and the set behind softens.
    Reduced motion -> no pull, already settled."""
    if _fx.reduced_motion():
        return near
    k = _k(t, t0, dur)
    return far + (near - far) * k


def _vasile_base(surface, t, cam, target, fov, vpose, tag, dof=None, seed=None):
    def build(r):
        _office_set(r)
        _person(r, "vasile", vpose, (0.0, 0, 1.5), (0, 0, -1.2))
        _person(r, "biribel", _IDLE, (0.3, 0, -1.3), (0, 0, 1.5))
    _shot(surface, t, cam, target, fov, build, sky=((14, 12, 12), (10, 9, 9)), tag=tag, dof=dof,
          seed=seed)


def _vasile_wide(surface, t):
    # 5 s take -> two angles: slow lateral wide, then a cut to a low reverse
    # wide over Vasile's desk side so the long line doesn't sit on one frame
    if t < 2600:
        k = _k(t, 0, 2600)
        _vasile_base(surface, t, (-2.3 + k * 0.3, 1.65, -3.0), (0.15, 1.15, 0.6), 58, _TALK,
                     "GUARD HQ // COMMANDER'S OFFICE")
    else:
        k = _k(t, 2600, 2400)
        _vasile_base(surface, t, (2.3 - k * 0.25, 1.5, 2.8), (-0.1, 1.3, -0.8), 60, _TALK,
                     "GUARD HQ // COMMANDER'S OFFICE")


def _vasile_close(surface, t):
    k = _k(t, 0, 4000)
    _vasile_base(surface, t, (0.42, 1.74, -0.1 + k * 0.12), (0.0, 1.72, 1.5), 48, _TALK, "",
                 dof=_rack(t, 2.4), seed=len("VASILE"))


def _vasile_biribel(surface, t):
    def build(r):
        _office_set(r)
        _person(r, "vasile", _TALK, (0.0, 0, 1.5), (0, 0, -1.2))
        _person(r, "biribel", _IDLE, (0.3, 0, -1.3), (0, 0, 1.5))
    _shot(surface, t, (-0.25, 1.7, 0.4), (0.3, 1.64, -1.3), 50, build,
          sky=((14, 12, 12), (10, 9, 9)), tag="", dof=_rack(t, 2.5), seed=len("BIRIBEL"))


def _vasile_lean(surface, t):
    k = _k(t, 0, 1600)
    pose = {key: v * k + _TALK.get(key, 0) * (1 - k) for key, v in _LEAN.items()}
    _vasile_base(surface, t, (0.7, 1.6, -0.45), (0.05, 1.5, 1.3), 54, pose, "",
                 seed=len("VASILE"))


def _maru_base(surface, t, cam, target, fov, mpose, bpose, tag, alarm=0.0, dof=None, seed=None):
    def build(r):
        _press_set(r, t, alarm)
        _person(r, "maru", mpose, (1.0, 0, 1.4), (0.0, 0, -1.0))
        _person(r, "biribel", bpose, (-0.4, 0, -1.0), (1.0, 0, 1.4))
    _shot(surface, t, cam, target, fov, build, sky=((16, 14, 12), (10, 9, 8)), tag=tag,
          col=(230, 190, 120), dof=dof, seed=seed)


def _maru_two(surface, t):
    # 5 s take -> two angles: the side two-shot, then a profile two-shot
    # from the presses' side (keeps both faces, opposite screen depth)
    if t < 2600:
        k = _k(t, 0, 2600)
        # (was (-2.6, 1.6, -2.5): 13 deg between them from the lens, so Biribel's
        # back filled ~40% of frame and Maru was squeezed - M5 gauntlet N11)
        _maru_base(surface, t, (-3.2 + k * 0.3, 1.6, 0.1), (0.3, 1.3, 0.2), 56, _TALK, _IDLE,
                   "MAG PRINT WORKS // BACK OFFICE")
    else:
        k = _k(t, 2600, 2400)
        _maru_base(surface, t, (3.7, 1.55, -1.7 + k * 0.3), (0.3, 1.35, 0.2), 54, _TALK, _IDLE,
                   "MAG PRINT WORKS // BACK OFFICE")


def _maru_close(surface, t):
    _maru_base(surface, t, (0.3, 1.64, 0.15), (1.0, 1.6, 1.4), 48, _TALK, _IDLE, "",
               dof=_rack(t, 2.2), seed=len("MARU"))


def _maru_biribel(surface, t):
    _maru_base(surface, t, (0.8, 1.7, 0.6), (-0.4, 1.66, -1.0), 50, _TALK, _IDLE, "",
               dof=_rack(t, 2.8), seed=len("BIRIBEL"))


def _breach_lights(surface, t):
    a = _k(t, 0, 1200)
    turn = _k(t, 900, 900)
    look = (0.0, 0, 4.0)
    def build(r):
        from engine3d.core import quad_xz
        _press_set(r, t, a)
        blue = (t // 220) % 2 == 0
        wash = (int(30 + 90 * a * (0 if blue else 1)), 20, int(30 + 90 * a * (1 if blue else 0)))
        _add(r, quad_xz(-4.5, 2.4, 3.5, 4.0, 0.012, wash, emissive=True))     # siren wash on the floor
        _person(r, "maru", dict(_IDLE, head_y=40 * turn), (1.0, 0, 1.4), look)
        _person(r, "biribel", dict(_IDLE, rsh_p=40 * turn), (-0.4, 0, -1.0), look)
    _shot(surface, t, (-2.2, 1.45, -2.8), (0.3, 1.45, 2.4), 58, build,
          sky=((16, 14, 12), (10, 9, 8)), tag="GUARD RAID", col=_GUARD_RED)
    if (t // 220) % 2 == 0:
        flash = pygame.Surface((WIDTH, SAFE_BOT - SAFE_TOP), pygame.SRCALPHA)
        flash.fill((200, 30, 30, int(26 * a)))
        surface.blit(flash, (0, SAFE_TOP))


def _blur_figure(buf, base, k=0.16, veil=(46, 40, 32)):
    """``buf`` = frame with Ucilev, ``base`` = the same frame without him. The
    pixels he changed become a soft mask; his region is blurred hard, veiled
    with door light and laid back over ``base`` -> a blurry backlit figure."""
    import numpy as np  # lazy: only for the breach take
    a = pygame.surfarray.array3d(buf).astype(np.int16)
    b = pygame.surfarray.array3d(base).astype(np.int16)
    m = np.abs(a - b).sum(axis=2) > 10
    if not m.any():
        return
    xs, ys = np.nonzero(m)
    w0, h0 = buf.get_size()
    pad = max(4, int((ys.max() - ys.min()) * 0.12))
    x0, x1 = max(0, xs.min() - pad), min(w0, xs.max() + pad + 1)
    y0, y1 = max(0, ys.min() - pad), min(h0, ys.max() + pad + 1)
    rect = pygame.Rect(x0, y0, x1 - x0, y1 - y0)
    w, h = rect.size
    sm = pygame.transform.smoothscale
    small = (max(2, int(w * k)), max(2, int(h * k)))
    fig = sm(sm(buf.subsurface(rect).copy(), small), (w, h))
    fig.fill(veil, special_flags=pygame.BLEND_RGB_ADD)
    alpha = pygame.Surface((w, h), pygame.SRCALPHA)
    alpha.fill((255, 255, 255, 0))
    pa = pygame.surfarray.pixels_alpha(alpha)
    pa[...] = (m[x0:x1, y0:y1] * 245).astype(np.uint8)
    del pa
    alpha = sm(sm(alpha, (max(2, int(w * k * 1.6)), max(2, int(h * k * 1.6)))), (w, h))
    layer = pygame.Surface((w, h), pygame.SRCALPHA)
    layer.blit(fig, (0, 0))
    layer.blit(alpha, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    out = base.copy()
    out.blit(layer, rect.topleft)
    buf.blit(out, (0, 0))


def _breach(surface, t):
    blow = _k(t, 400, 300)
    with_u = [False]
    _fs = _fx.flash_scale()          # RPE6 P9: flash reduction (1.0 = legacy)
    def build(r):
        from engine3d.core import box
        _press_set(r, t, 1.0, door=True)
        # the double door in the back wall, blown in -> blinding backlight
        _door = tuple(int(c * (0.4 + 0.6 * _fs)) for c in (255, 236, 200))
        _add(r, box(2.0, 2.6, 0.05, _door if blow > 0.5 else (50, 44, 40),
                   center=(0.0, 1.3, 4.06), emissive=blow > 0.5))
        for s in (-1, 1):
            off = blow * 1.4
            _add(r, box(1.0, 2.6, 0.1, (64, 58, 50), center=(s * (0.5 + off * 0.6), 1.3, 4.0 - off)))
        if blow > 0.5:                                                   # light spill through the door
            from engine3d.core import quad_xz
            _add(r, quad_xz(-1.2, 1.2, 1.2, 4.0, 0.012, (150, 132, 108), emissive=True))
        _person(r, "biribel", dict(spine=6, rsh_p=70, lsh_p=70, rel=20, lel=40), (-1.2, 0, 0.4), (0, 0, 4))
        _person(r, "maru", dict(spine=10, head_p=-6), (-2.0, 0, 0.9), (0, 0, 4))
        if True:                           # blast FX: identical in both passes (_blur_figure diffs them)
            _spr(r, (0.0, 1.4, 3.9), _fx.flash(t - 520, radius_m=3.4, dur_ms=520))
            _spr(r, (-0.6, 1.2, 3.8), _fx.sparks(41, t - 520, n=22, speed_m=5.0))
            _spr(r, (0.7, 1.7, 3.8), _fx.sparks(42, t - 560, n=14, speed_m=4.0))
        if blow > 0.5 and with_u[0]:       # Ucilev: helmeted, masked, lost in the backlight
            r.add_humanoid(_sil_hum(), dict(spine=4, rsh_p=30, rel=60, lsh_p=40, lel=80),
                           upos, _yaw_to(upos, (-1.9, 0, -2.2)), rifle_on=True)
    upos = (0.45, 0, 3.9 - 0.5 * _k(t, 900, 2600))
    cam, tgt, fov = (-1.9, 1.45, -2.2), (0.0, 1.62, 4.0), 56
    r, buf = _m3d._rend()

    shk = _fx.shake(t, 520, 900, 0.07)    # door blows at ~520 ms

    def render():
        _m3d._cam(r, t, cam, tgt, fov, hh=0.016, seed=5, shk=shk)
        buf.blit(_m3d._sky(_RW, _RH, (16, 14, 12), (10, 9, 8)), (0, 0))
        r.begin()
        build(r)
        r.flush(buf)
    render()
    if blow > 0.5:            # second pass with him in it -> blurred into the glare
        base = buf.copy()
        with_u[0] = True
        render()
        _blur_figure(buf, base)
    surface.fill((0, 0, 0))
    _m3d._present(surface, buf)
    if blow > 0.5:
        door = r.project((0.25, 1.75, 4.06))
        if door:
            dx, dy = _m3d._film_xy(door)
            # bloom only: the anamorphic streak read as a stock lens-flare filter
            _glare(surface, dx, dy, (SAFE_BOT - SAFE_TOP) * 0.36,
                   tuple(int(c * (0.5 + 0.5 * _fs)) for c in (96, 84, 66)), streak=False)
    _m3d._finish(surface, 7000, "", _GUARD_RED)
    if _fs < 1.0:
        _fx.cap_flash(surface)       # RPE6 P9: cap the white-out under the threshold
    if blow > 0.5:
        glow = pygame.Surface((WIDTH, SAFE_BOT - SAFE_TOP), pygame.SRCALPHA)
        glow.fill((255, 230, 200, int(140 * _fs * max(0.0, 1.0 - (t - 700) / 600.0))))
        surface.blit(glow, (0, SAFE_TOP))
    _tag(surface, "GUARD SPECIAL UNIT", _GUARD_RED)


# East checkpoint: existing cast rigs, one coherent set, four camera takes.
def _faces_set(r):
    from engine3d.core import box, quad_xz
    _night_street(r)
    _add(r, quad_xz(-12, -10, 12, 12, 0, (32, 36, 44), seg=4))
    _add(r, box(22, 7, 1, (48, 44, 46), center=(0, 3.5, 8)))
    for x in (-8, -4, 0, 4, 8):
        _add(r, box(1.1, 1.7, 0.05, (88, 80, 66), center=(x, 3.8, 7.45), emissive=True))
    # Leave the central passage clear: barricades sit to either side.
    for x in (-4.2, 4.2):
        _add(r, box(3.8, 0.8, 0.55, (76, 74, 66), center=(x, 0.4, 2.8)))
        for j in range(5):
            _add(r, box(0.32, 0.18, 0.03, (166, 134, 66), center=(x - 1.4 + j * 0.7, 0.65, 2.5)))
    _add(r, box(0.12, 4.2, 0.12, (36, 40, 46), center=(-3.2, 2.1, 3.5)))
    _add(r, box(0.45, 0.18, 0.45, (246, 208, 146), center=(-3.2, 4.25, 3.5), emissive=True))
    _add(r, quad_xz(-4.5, -1, 1.2, 4.5, 0.012, (58, 54, 46), emissive=True))
    _add(r, box(1.3, 2.2, 1.3, (42, 48, 54), center=(5.4, 1.1, 5.0)))
    # kiosk front: a curfew order + Guard poster (was one blank red block)
    # (pasted low so they never sit tangent to Biribel's head in the wide - N12)
    ok = _decal.add(r, "posters", 1, (5.05, 1.0, 4.345), (0.52, 0.7))
    ok = _decal.add(r, "posters", 0, (5.72, 1.0, 4.345), (0.52, 0.7)) and ok
    if not ok:
        _add(r, box(1.36, 0.45, 0.02, _GUARD_RED, center=(5.4, 1.6, 4.33)))


def _faces_take(surface, t, take):
    k = _k(t, 200, 2200)
    release = take == "release"
    bpos = (-0.35, 0, -1.1 + (2.0 * k if release else 0))
    kp = (-1.35 - (0.35 * k if release else 0), 0, 1.4)
    sp = (1.35 + (0.4 * k if release else 0), 0, 2.4)
    cameras = {
        # (was x -3.4: Sandu's head sat 4 deg from Biribel's shoulder, tangent - N12)
        "wide": ((-4.2 + 0.25 * k, 1.65, -5.0), (0, 1.1, 1.0), 58),
        "kovac": ((0.5, 1.7, -1.3), (-1.35, 1.62, 1.4), 48),
        "sandu": ((-0.3, 1.7, -0.3), (1.35, 1.62, 2.4), 48),
        "release": ((-3.0, 1.6, -4.4), (0, 1.15, 1.4), 58),
    }
    def build(r):
        _faces_set(r)
        # Release: stride is driven by distance walked and fades out as he
        # stops - the old t-driven cycle kept him walking in place after k=1.
        # 4.65 rad/m = 1.35 m per full cycle (2 steps).
        pose = (_m3d._walk(4.65 * 2.0 * k, 0.55 * min(1.0, (1.0 - k) / 0.12))
                if release and k < 1.0 else _IDLE)
        _person(r, "biribel", pose, bpos, (0, 0, 6))
        r.add_humanoid(_squad_hum(2), dict(_IDLE, head_p=2,
                       rsh_p=12 + (16 * (1 - k) if take == "wide" else 0), rel=30),
                       kp, _yaw_to(kp, bpos), rifle_on=False)
        r.add_humanoid(_squad_hum(3), dict(_IDLE, head_y=-12 * k,
                       lsh_p=24 if take == "sandu" else 8, lel=45),
                       sp, _yaw_to(sp, (4, 0, 6) if release else bpos), rifle_on=False)
    cam, target, fov = cameras[take]
    _shot(surface, t, cam, target, fov, build, rain=True,
          tag="EAST CHECKPOINT // KOVAC & SANDU" if take in ("wide", "release") else "",
          col=(170, 190, 210),
          seed=None if take in ("wide", "release") else len(take.upper()))


def _stair_height(z):
    """Match the twelve solid treads, not a ramp buried inside them."""
    return max(0.0, 2.4 - 0.2 * max(0, int(z / 0.5)))


def _basement_stair_set(r, t):
    """A closed masonry stairwell: upper door, flight, lower tunnel landing.

    Keep the shell subdivided for near clipping / software painter sorting.
    Cameras belong inside this volume; there is no cutaway wall or sky card.
    """
    from engine3d.core import box, quad_xz, Light
    r.fog, r.fog_start, r.fog_end = (32, 29, 25), 12.0, 26.0
    r.light = Light(direction=(-0.4, 0.8, -0.3), ambient=0.62, diffuse=0.65,
                    tint=(1.08, 1.0, 0.88))
    _add(r, quad_xz(-2.3, -3, 2.3, 12, 0, (48, 45, 40), seg=1))
    for x in (-2.45, 2.45):
        _add(r, box(0.3, 5.8, 15.6, (84, 76, 63), center=(x, 2.9, 4.5), seg=1))
    for z in (-3.15, 12.15):
        _add(r, box(5.2, 5.8, 0.3, (78, 70, 58), center=(0, 2.9, z), seg=1))
    _add(r, box(5.2, 0.2, 15.6, (46, 42, 36), center=(0, 5.9, 4.5), seg=1))
    _add(r, box(4.6, 2.4, 3, (61, 55, 46), center=(0, 1.2, -1.5), seg=1))
    for i in range(12):
        top, z = 2.4 - i * 0.2, i * 0.5
        _add(r, box(4.6, top, 0.5, (86 - i, 79 - i, 66 - i),
                    center=(0, top / 2, z + 0.25), seg=0.75))
        _add(r, box(4.6, 0.025, 0.06, (124, 113, 89), center=(0, top + 0.0125, z + 0.47)))
        # Wall-mounted rails leave both actors' path unobstructed.
        if i % 3 == 0:
            for x in (-2.22, 2.22):
                _add(r, box(0.16, 0.04, 0.06, (76, 70, 58), center=(x, top + 0.9, z)))
    for x in (-2.12, 2.12):
        r.add_line3d((x, 3.3, 0), (x, 0.9, 6), (132, 117, 88), 3, layer=2)
    # Doors sit on the landings, with lintels and jambs physically attached.
    for z, base in ((-2.96, 2.4), (11.96, 0.0)):
        _add(r, box(1.45, 2.45, 0.06, (42, 51, 48), center=(0, base + 1.225, z), seg=0.6))
        for x in (-0.8, 0.8):
            _add(r, box(0.12, 2.6, 0.14, (121, 106, 78), center=(x, base + 1.3, z)))
        _add(r, box(1.72, 0.12, 0.14, (121, 106, 78), center=(0, base + 2.6, z)))
    # Masonry courses, conduit and beams explain the space, not random props.
    for y in (2.8, 3.4, 4.0, 4.6, 5.2):
        _add(r, box(4.6, 0.025, 0.02, (67, 60, 50), center=(0, y, -2.98), seg=1))
    for z in (-1.8, 2.8, 7.4):
        _add(r, box(4.6, 0.18, 0.22, (63, 55, 44), center=(0, 5.65, z), seg=1))
    _add(r, box(0.05, 0.05, 14.8, (58, 55, 47), center=(2.27, 5.0, 4.5), seg=1))
    for z, y in ((-0.8, 4.3), (3.0, 3.4), (7.0, 2.6)):
        _add(r, box(0.12, 0.4, 0.28, (46, 44, 38), center=(2.22, y, z)))
        _add(r, box(0.04, 0.22, 0.2, (246, 205, 139), center=(2.14, y, z), emissive=True))


def _stair_actor(t, wounded=False):
    """Distance-owned gait, easing into a planted stance at the lower floor."""
    start, duration = (450, 3350) if wounded else (200, 3400)
    z = 6.0 * _k(t, start, duration)
    # Settle during the last half metre; phase cannot advance after z stops.
    settle = max(0.0, min(1.0, (z - 5.5) / 0.5))
    settle = settle * settle * (3.0 - 2.0 * settle)
    walk = _m3d._walk(z * 6.0 + (0.7 if wounded else 0), amp=0.5 if wounded else 0.65)
    idle = dict(_IDLE, lhip_p=0, rhip_p=0, lkn=0, rkn=0)
    pose = {name: lerp(walk.get(name, 0), idle.get(name, 0), settle)
            for name in walk.keys() | idle.keys()}
    if wounded:
        pose.update(lsh_p=30, lel=95)
    return z, pose


def _basement_descent(surface, t):
    """Track inside the room; retain production timing and tunnel handoff."""
    bz, bpose = _stair_actor(t)
    mz, mpose = _stair_actor(t, wounded=True)

    def build(r):
        _basement_stair_set(r, t)
        _person(r, "biribel", bpose,
                (-0.45, _stair_height(bz), bz), (-0.45, 0, bz + 3))
        _person(r, "maru", mpose, (0.55, _stair_height(mz), mz), (0.55, 0, mz + 3))

    # Retreat down the flight ahead of them, looking uphill. All walls remain
    # present, and the continuous stair/landing fills the frame behind them.
    cy = max(0.0, 2.4 - bz * 0.4)
    _shot(surface, t, (-1.45, cy + 1.85, bz + 3.8),
          (0, cy + 1.1, bz - 0.4), 64, build,
          sky=((32, 29, 25), (32, 29, 25)),
          tag="PRINT WORKS // BASEMENT STAIR", hh=0.006, seed=26)


def _basement_descent_2d(surface, t):
    """Matching motion when 3D is disabled; never a blank transition."""
    from cutscenes import figure_kit  # lazy: facade load order
    surface.fill((0, 0, 0))
    # A side-on view of the same enclosed masonry room, not free-floating
    # steps on an empty plate when the 3D stack is unavailable.
    band = pygame.Rect(0, SAFE_TOP, WIDTH, SAFE_BOT - SAFE_TOP)
    pygame.draw.rect(surface, (74, 66, 54), band)
    for row, yy in enumerate(range(SAFE_TOP + 20, SAFE_BOT, 30)):
        pygame.draw.line(surface, (59, 53, 44), (0, yy), (WIDTH, yy), 1)
        for xx in range((row % 2) * 44, WIDTH, 88):
            pygame.draw.line(surface, (59, 53, 44), (xx, yy - 29), (xx, yy), 1)
    pygame.draw.rect(surface, (43, 39, 33), (0, SAFE_TOP, WIDTH, 18))
    pygame.draw.rect(surface, (44, 42, 35), (0, SAFE_BOT - 36, WIDTH, 36))
    y0 = SAFE_TOP + 110
    pygame.draw.rect(surface, (121, 106, 78), (72, y0 - 88, 74, 92))
    pygame.draw.rect(surface, (42, 51, 48), (78, y0 - 82, 62, 86))
    pygame.draw.rect(surface, (54, 50, 42), (72, y0, 90, SAFE_BOT - y0))
    for xx, yy in ((300, y0 - 60), (740, y0 + 55)):
        pygame.draw.rect(surface, (46, 44, 38), (xx - 3, yy - 3, 20, 28))
        pygame.draw.rect(surface, (246, 205, 139), (xx, yy, 14, 22))
    for i in range(12):
        x, y = 160 + i * 46, y0 + i * 14
        pygame.draw.rect(surface, (50, 49, 45), (x, y, 48, SAFE_BOT - y))
        pygame.draw.line(surface, (112, 106, 90), (x, y), (x + 47, y), 2)
    for who, wounded, offset in (("biribel", False, 0), ("maru", True, 8)):
        z, _ = _stair_actor(t, wounded)
        p = z / 6.0
        x, y = int(180 + p * 520), int(y0 + p * 158 + offset)
        figure_kit.draw_character(surface, who, x, y, 0.55, True,
                                  wardrobe=biribel_2d(OUTFIT_GUARD) if who == "biribel" else None)
    pygame.draw.line(surface, (124, 118, 102), (145, y0 - 70), (715, y0 + 98), 4)
    _tag(surface, "PRINT WORKS // BASEMENT STAIR", _LIAISON)


M5X_SCENES = {
    "m5x_faces_wide": lambda s, t: _faces_take(s, t, "wide"),
    "m5x_faces_kovac": lambda s, t: _faces_take(s, t, "kovac"),
    "m5x_faces_sandu": lambda s, t: _faces_take(s, t, "sandu"),
    "m5x_faces_release": lambda s, t: _faces_take(s, t, "release"),
    "m5x_pw_arrival_wide": _arrival_wide, "m5x_pw_arrival_door": _arrival_door,
    "m5x_vasile_wide": _vasile_wide, "m5x_vasile_close": _vasile_close,
    "m5x_vasile_biribel": _vasile_biribel, "m5x_vasile_lean": _vasile_lean,
    "m5x_maru_two": _maru_two, "m5x_maru_close": _maru_close, "m5x_maru_biribel": _maru_biribel,
    "m5x_breach_lights": _breach_lights, "m5x_breach": _breach,
    "m5x_decree": _decree, "m5x_squadmate": _squadmate, "m5x_change": _change,
    "m5x_barracks": _barracks,
    "m5x_basement_descent": _basement_descent,
}


# ── 2D fallback ──
_2D_CAST = {
    "faces": (("biribel", 0.24), ("krap", 0.5), ("krap", 0.76)),
    "pw": (("biribel", 0.5),), "vasile": (("biribel", 0.32), ("vasile", 0.66)),
    "maru": (("biribel", 0.32), ("maru", 0.66)), "breach": (("biribel", 0.28), ("maru", 0.4)),
    "decree": (("biribel", 0.78),), "squadmate": (("biribel", 0.34), ("krap", 0.62)),
    "change": (("biribel", 0.5),),
    "barracks": (("biribel", 0.18), ("krap", 0.46), ("krap", 0.64), ("krap", 0.82)),
}
_2D_BG = {"faces": ((22, 26, 38), (38, 36, 34)), "pw": ((22, 24, 36), (40, 30, 30)), "vasile": ((30, 24, 20), (12, 10, 9)),
          "maru": ((34, 30, 24), (12, 10, 8)), "breach": ((40, 16, 16), (10, 8, 8)),
          "decree": ((50, 54, 52), (20, 22, 22)), "squadmate": ((50, 54, 52), (20, 22, 22)),
          "barracks": ((50, 54, 52), (20, 22, 22)), "change": ((50, 54, 52), (20, 22, 22))}


def draw_m5x_2d(scene, surface, t):
    if scene == "m5x_basement_descent":
        _basement_descent_2d(surface, t)
        return
    key = scene.split("_")[1]
    key = "pw" if key == "pw" else key
    top, bot = _2D_BG.get(key, _2D_BG["pw"])
    surface.blit(pygame.transform.smoothscale(_m3d._sky(64, 64, top, bot), (WIDTH, HEIGHT)), (0, 0))
    fy = SAFE_BOT - 30
    if key == "faces":
        pygame.draw.rect(surface, (48, 44, 46), (0, SAFE_TOP + 36, WIDTH, fy - SAFE_TOP - 36))
        for x in range(60, WIDTH, 140):
            pygame.draw.rect(surface, (88, 80, 66), (x, SAFE_TOP + 58, 48, 72))
        for x in (40, WIDTH - 220):
            pygame.draw.rect(surface, (76, 74, 66), (x, fy - 64, 180, 64))
            for j in range(5):
                pygame.draw.rect(surface, (166, 134, 66), (x + 8 + j * 34, fy - 50, 16, 10))
        _tag(surface, "EAST CHECKPOINT // KOVAC & SANDU", (170, 190, 210))
    elif key == "pw":
        pygame.draw.rect(surface, _BRICK, (WIDTH // 2 - 260, SAFE_TOP + 40, 520, fy - SAFE_TOP - 40))
        pygame.draw.rect(surface, (20, 20, 24), (WIDTH // 2 - 150, SAFE_TOP + 60, 300, 40))
        txt = font_terminal_small.render(_T("m5mid3d.mag_print_works"), True, (230, 190, 120))
        surface.blit(txt, (WIDTH // 2 - txt.get_width() // 2, SAFE_TOP + 70))
        bx, by, bw = WIDTH // 2 - 260, SAFE_TOP + 40, 520
        for i, yy in enumerate(range(by + 14, fy, 14)):              # brick courses
            pygame.draw.line(surface, (92, 44, 34), (bx, yy), (bx + bw, yy), 1)
            for xx in range(bx + (i % 2) * 18, bx + bw, 36):
                pygame.draw.line(surface, (92, 44, 34), (xx, yy - 14), (xx, yy), 1)
        pygame.draw.rect(surface, (34, 30, 30), (WIDTH // 2 - 90, SAFE_TOP + 120, 180, fy - SAFE_TOP - 120))
        for yy in range(SAFE_TOP + 128, fy, 10):                    # shutter slats
            pygame.draw.line(surface, (52, 48, 46), (WIDTH // 2 - 86, yy), (WIDTH // 2 + 86, yy), 2)
        pygame.draw.rect(surface, (255, 214, 150), (WIDTH // 2 - 70, fy - 6, 140, 6))
    elif key == "vasile":                                    # office: window, portrait, desk
        pygame.draw.rect(surface, (40, 44, 54), (90, SAFE_TOP + 50, 150, 170))
        for i in range(8):
            pygame.draw.line(surface, (70, 66, 56), (90, SAFE_TOP + 58 + i * 20), (239, SAFE_TOP + 58 + i * 20), 3)
        pygame.draw.rect(surface, (52, 46, 40), (WIDTH // 2 - 50, SAFE_TOP + 40, 100, 110))
        pygame.draw.ellipse(surface, (150, 120, 96), (WIDTH // 2 - 18, SAFE_TOP + 62, 36, 42))
        pygame.draw.rect(surface, (40, 52, 70), (WIDTH // 2 - 34, SAFE_TOP + 104, 68, 46))
        pygame.draw.rect(surface, (120, 96, 52), (WIDTH // 2 - 50, SAFE_TOP + 40, 100, 110), 6)
        pygame.draw.rect(surface, (170, 30, 32), (WIDTH - 200, SAFE_TOP + 40, 70, 200))
        pygame.draw.rect(surface, (48, 34, 26), (WIDTH // 2 + 90, fy - 120, 300, 120))
        pygame.draw.rect(surface, (70, 52, 40), (WIDTH // 2 + 82, fy - 128, 316, 12))
    elif key in ("maru", "breach"):                         # press room: presses + bulb
        for px in (60, WIDTH - 320):
            pygame.draw.rect(surface, (40, 46, 52), (px, fy - 170, 260, 170))
            pygame.draw.rect(surface, (60, 66, 72), (px + 20, fy - 200, 220, 34))
            for i in range(5):
                pygame.draw.rect(surface, (26, 28, 32), (px + 30 + i * 44, fy - 150, 16, 120))
        pygame.draw.line(surface, (30, 30, 30), (WIDTH // 2, SAFE_TOP), (WIDTH // 2, SAFE_TOP + 60), 2)
        glow = pygame.Surface((240, 240), pygame.SRCALPHA)
        for r, a in ((120, 18), (80, 30), (40, 50)):
            pygame.draw.circle(glow, (255, 214, 150, a), (120, 120), r)
        surface.blit(glow, (WIDTH // 2 - 120, SAFE_TOP - 50))
        pygame.draw.circle(surface, (255, 230, 180), (WIDTH // 2, SAFE_TOP + 68), 9)
    pygame.draw.rect(surface, tuple(max(0, c - 6) for c in bot), (0, fy, WIDTH, SAFE_BOT - fy))
    pygame.draw.line(surface, tuple(min(255, c + 24) for c in bot), (0, fy), (WIDTH, fy), 2)
    scale = (fy - SAFE_TOP - 34) / 310.0       # whole figure, head to boots, inside the film band
    if key == "decree":
        tex = _decree_tex()
        ph = fy - SAFE_TOP - 40
        pw = int(ph * tex.get_width() / tex.get_height())
        surface.blit(pygame.transform.smoothscale(tex, (pw, ph)), (WIDTH // 2 - pw // 2 - 120, SAFE_TOP + 20))
    if scene == "m5x_breach" and t > 500:
        pygame.draw.rect(surface, (255, 236, 200), (WIDTH // 2 + 60, SAFE_TOP + 40, 170, fy - SAFE_TOP - 40))
        sil = _silhouette(int(fy - SAFE_TOP - 50))
        surface.blit(sil, (WIDTH // 2 + 145 - sil.get_width() // 2, fy - sil.get_height() + 10))
    try:
        from cutscenes import figure_kit  # lazy: see _silhouette
        for who, fx in _2D_CAST.get(key, ()):
            sh = pygame.Surface((140, 22), pygame.SRCALPHA)        # contact shadow
            pygame.draw.ellipse(sh, (0, 0, 0, 110), sh.get_rect())
            surface.blit(sh, (int(WIDTH * fx) - 70, fy - 11))
            if key == "faces" and who == "krap":
                # Same black/red Guard kit as gameplay, distinct faces, not KRAP green.
                spec = dict(figure_kit.SPECS["krap"])
                spec.update(coat=_GUARD_BLACK, jacket=_GUARD_BLACK, vest=(38, 39, 44),
                            trousers=(28, 29, 34), armband=_GUARD_RED, patch=None, cap=True,
                            skin=(150, 112, 88) if fx < 0.6 else (208, 170, 140))
                figure_kit.draw_character(surface, who, int(WIDTH * fx), fy, scale, False, wardrobe=spec)
            elif who == "biribel":
                # same kit as the 3D take (core.outfits); m5x_change swaps at the cut
                outfit = scene_outfit(scene)
                if scene == "m5x_change" and t < _CH_CUT:
                    outfit = scene_outfit("m5x_squadmate")
                figure_kit.draw_character(surface, who, int(WIDTH * fx), fy, scale, fx < 0.5,
                                          wardrobe=biribel_2d(outfit) or None)
            else:
                figure_kit.draw_character(surface, who, int(WIDTH * fx), fy, scale, fx < 0.5)
    except Exception:
        pass
    if key in ("pw", "faces"):
        layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        _rain_streaks(layer, t, 77, n=60)
        surface.blit(layer, (0, 0))
    vig = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)      # soft edge vignette
    for i, a in enumerate((26, 20, 16)):
        w = 60 + i * 50
        pygame.draw.rect(vig, (0, 0, 0, a), (0, 0, w, HEIGHT))
        pygame.draw.rect(vig, (0, 0, 0, a), (WIDTH - w, 0, w, HEIGHT))
    surface.blit(vig, (0, 0))


def draw_m5x(scene, surface, t):
    """Always draws something: the 3D take, or the 2D fallback."""
    fn = M5X_SCENES.get(scene)
    if fn is not None and _m3d.m5_3d_enabled():
        try:
            fn(surface, t)
            return True
        except Exception as e:  # same policy as m5martial3d: permanent 2D fallback
            _m3d._cache["failed"], _m3d._cache["err"] = True, e
            print(f"m5mid3d: 3D cutscenes disabled, using 2D ({e!r})")
    draw_m5x_2d(scene, surface, t)
    return True
