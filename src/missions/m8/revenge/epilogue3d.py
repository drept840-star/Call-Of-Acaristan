"""Mission 8 Revenge - phase 7: the epilogue, one 3D shot per line.

Staged on the chase set (``chase_set``): the train running east from the Kim
Kim crossing with Biribel on the last car's step, Bodi's tractor dead on the
tracks, Ucilev at the border hut with the photo.  The state TV studio and the
funeral in the mansion grounds are small stages built off the road, far out
in the fields, until the Duty mansion set exists.

``draw(surface, line, t)`` renders line ``line`` of ``meta.BEATS[epilogue]``
``t`` seconds after it came up; ``beats`` owns the plate and the input.
"""
import math

import pygame

from core.config import HEIGHT, WIDTH, font_terminal_small, font_title
from core.outfits import OUTFIT_GUARD
from cutscenes import m6world3d as _w
from cutscenes import m7world3d as W7
from engine3d import POSES, Mesh, box
from engine3d.core import quad_xz, rot_y, rot_z

from . import chase_set as S

RX = S.road_x(S.CROSSING_Z)
CZ = S.CROSSING_Z
STUDIO = (-150.0, 420.0)        # x, z: state TV, out in the west fields
FUNERAL = (150.0, 600.0)        # the mansion grounds, east fields
NIGHT = (58, 68, 108)
DUSK = (104, 112, 152)
TV_TINT = (210, 222, 236)

# laid out: flat on his back, legs straight, arms at his sides
LYING = dict(POSES["dead_back"], body_r=0, head_y=0, head_p=0, lhip_p=0, lhip_r=0, lkn=0,
             rhip_p=0, rhip_r=0, rkn=0, lsh_p=0, lsh_r=0, lel=6, rsh_p=0, rsh_r=0, rel=6)
_SEATED = dict(POSES["stand"], lhip_p=88, lkn=86, rhip_p=88, rkn=86, lsh_p=46, lel=40,
               rsh_p=46, rel=40, spine=6)


# --- the off-road stages -----------------------------------------------------

NAVY, RED, GOLD = (26, 36, 62), (150, 30, 32), (230, 200, 120)


def _flag(m, x, z, h=2.75, w=0.7):
    """A hanging state flag on a pole: navy over red, four fold strips."""
    m.add(box(0.05, h, 0.05, (150, 140, 108), center=(x, h / 2, z)))
    m.add(box(0.09, 0.07, 0.09, GOLD, center=(x, h + 0.03, z)))
    m.add(box(w, 0.03, 0.03, (150, 140, 108), center=(x + w / 2, h - 0.13, z)))
    n = 4
    for i in range(n):
        sh = 1.0 - 0.15 * (i % 2)
        cx, cz = x + (i + 0.5) * w / n, z + (0.035 if i % 2 else -0.01)
        m.add(box(w / n, h * 0.2, 0.02, tuple(int(c * sh) for c in NAVY), center=(cx, h - 0.42, cz)))
        m.add(box(w / n, h * 0.2, 0.02, tuple(int(c * sh) for c in RED), center=(cx, h - 0.97, cz)))


def studio():
    """State TV, studio A: a navy set wall with light strips, the crest, two
    flags, an angled anchor desk with a lit front, the truss and the cameras."""
    m = Mesh()
    sx, sz = STUDIO
    m.add(box(16.0, 0.06, 12.0, W7._t("plank", (34, 36, 46)), center=(sx, 0.03, sz)))
    m.add(box(9.0, 0.02, 4.0, (22, 30, 58), center=(sx, 0.07, sz + 1.2)))          # carpet
    m.add(box(12.0, 5.2, 0.3, (24, 30, 54), center=(sx, 2.6, sz + 3.4)))
    for dx in (-6.4, 6.4):                                                          # side flats
        m.add(box(0.3, 5.2, 4.6, (20, 26, 46), center=(sx + dx, 2.6, sz + 1.2)))
    for y in (0.5, 4.4):                                                            # light strips
        m.add(box(11.6, 0.06, 0.04, (150, 190, 255), center=(sx, y, sz + 3.23), emissive=True))
    for dx in (-4.9, -2.1, 2.1, 4.9):
        m.add(box(0.05, 3.7, 0.04, (90, 120, 200), center=(sx + dx, 2.45, sz + 3.23), emissive=True))
    # the crest: a gold ring and star on a navy plate
    m.add(box(2.0, 2.0, 0.08, (18, 24, 44), center=(sx, 3.55, sz + 3.2)))
    for i in range(16):
        a = 2 * math.pi * i / 16
        m.add(box(0.3, 0.08, 0.05, GOLD), rot_z(math.degrees(a) + 90),
              (sx + 0.72 * math.cos(a), 3.55 + 0.72 * math.sin(a), sz + 3.13))
    for i in range(5):
        a = 90 + i * 72
        m.add(box(0.12, 0.5, 0.04, GOLD, center=(0.0, 0.25, 0.0)), rot_z(a - 90), (sx, 3.55, sz + 3.12))
    # side monitors: lit panels with a bar graphic
    for dx in (-3.5, 3.5):
        m.add(box(2.2, 1.3, 0.08, (12, 14, 18), center=(sx + dx, 2.9, sz + 3.18)))
        m.add(box(2.0, 1.1, 0.02, (40, 70, 140), center=(sx + dx, 2.9, sz + 3.13), emissive=True))
        for j in range(4):
            h = 0.2 + 0.16 * j
            m.add(box(0.26, h, 0.01, (200, 210, 240),
                      center=(sx + dx - 0.6 + j * 0.4, 2.45 + h / 2, sz + 3.11), emissive=True))
    _flag(m, sx - 5.4, sz + 2.8)
    _flag(m, sx + 4.7, sz + 2.8)
    # anchor desk: body, top, two angled wings, lit front strip, gold badge
    body, top, strip = (22, 26, 40), (70, 68, 74), (120, 170, 255)
    m.add(box(2.6, 1.05, 0.7, body, center=(sx, 0.525, sz + 0.8)))
    m.add(box(2.7, 0.06, 0.82, top, center=(sx, 1.08, sz + 0.8)))
    for s in (-1, 1):
        wing = Mesh()
        wing.add(box(1.4, 1.05, 0.66, body, center=(0.0, 0.525, 0.0)))
        wing.add(box(1.5, 0.06, 0.78, top, center=(0.0, 1.08, 0.0)))
        wing.add(box(1.36, 0.05, 0.02, strip, center=(0.0, 0.86, -0.34), emissive=True))
        m.add(wing, rot_y(-s * 28), (sx + s * 1.85, 0.0, sz + 1.12))
    m.add(box(2.5, 0.05, 0.02, strip, center=(sx, 0.86, sz + 0.44), emissive=True))
    m.add(box(0.7, 0.36, 0.03, GOLD, center=(sx, 0.5, sz + 0.44)))
    m.add(box(0.5, 0.2, 0.02, NAVY, center=(sx, 0.5, sz + 0.425)))
    m.add(box(0.36, 0.02, 0.26, (230, 226, 210), center=(sx - 0.4, 1.12, sz + 0.7)))  # papers
    m.add(box(0.05, 0.3, 0.05, (30, 30, 32), center=(sx + 0.5, 1.25, sz + 0.62)))     # desk mic
    # the truss and its lamps; two studio cameras on the floor
    for z in (sz - 2.6, sz + 0.4):
        m.add(box(14.0, 0.14, 0.14, (40, 40, 44), center=(sx, 5.4, z)))
        for i in range(6):
            x = sx - 5.0 + i * 2.0
            m.add(box(0.3, 0.34, 0.38, (30, 30, 34), center=(x, 5.1, z)))
            m.add(box(0.22, 0.2, 0.03, (255, 244, 220), center=(x, 5.06, z - 0.2), emissive=True))
    for dx in (-2.8, 2.8):
        cam = Mesh()
        cam.add(box(0.06, 1.3, 0.06, (40, 40, 42), center=(0.0, 0.65, 0.0)))
        cam.add(box(0.5, 0.44, 0.8, (52, 54, 58), center=(0.0, 1.5, 0.0)))
        cam.add(box(0.26, 0.26, 0.12, (14, 14, 16), center=(0.0, 1.5, 0.45)))
        cam.add(box(0.06, 0.06, 0.06, (255, 40, 40), center=(0.18, 1.76, 0.3), emissive=True))
        for a in (0, 120, 240):
            cam.add(box(0.05, 0.05, 0.8, (40, 40, 42), center=(0.0, 0.05, 0.4)), rot_y(a))
        m.add(cam, rot_y(-dx * 4), (sx + dx, 0.0, sz - 4.8))
    return m


LAMP_H = 3.2
ESTATE_LAMPS = tuple((FUNERAL[0] + s * 3.4, FUNERAL[1] + z) for z in (-22.0, -16.0, -10.0)
                     for s in (-1, 1))
CANDLES = tuple((FUNERAL[0] + dx, FUNERAL[1] + dz) for dx in (-1.6, 1.6) for dz in (-0.75, 0.75))
HONOUR = ((-1.95, 0.0, 90.0), (1.95, 0.0, 270.0), (-0.9, 1.35, 180.0), (0.9, 1.35, 180.0))


def _lamp_post(m, x, z, h=LAMP_H):
    m.add(box(0.36, 0.3, 0.36, (40, 40, 42), center=(x, 0.15, z)))
    m.add(box(0.11, h, 0.11, (30, 30, 32), center=(x, h / 2, z)))
    m.add(box(0.34, 0.08, 0.34, (30, 30, 32), center=(x, h + 0.04, z)))
    m.add(box(0.26, 0.4, 0.26, (255, 226, 160), center=(x, h + 0.28, z), emissive=True))
    m.add(box(0.38, 0.1, 0.38, (30, 30, 32), center=(x, h + 0.52, z)))


def _window(m, x, y, z):
    m.add(box(1.5, 2.1, 0.08, (226, 222, 210), center=(x, y, z)))
    m.add(box(1.2, 1.8, 0.04, (238, 206, 140), center=(x, y, z - 0.05), emissive=True))
    m.add(box(1.2, 0.05, 0.02, (60, 50, 40), center=(x, y, z - 0.08)))
    m.add(box(0.05, 1.8, 0.02, (60, 50, 40), center=(x, y, z - 0.08)))
    for s in (-1, 1):
        m.add(box(0.5, 1.9, 0.05, (52, 66, 54), center=(x + s * 1.0, y, z - 0.04)))
    m.add(box(1.7, 0.12, 0.2, (226, 222, 210), center=(x, y - 1.1, z - 0.08)))


def funeral():
    """The estate at night: a plastered mansion with a tile roof, a portico on
    four columns and every window lit; a gravel drive between hedges, lamp
    posts and poplars; the gate piers; the flag-draped bier on its dais."""
    m = Mesh()
    fx, fz = FUNERAL
    stone = W7._t("stone", (150, 146, 136))
    plaster = W7._t("plaster", (198, 190, 170))
    tile = W7._t("tile", (122, 60, 48))
    gravel = (92, 90, 86)
    gravel_at = W7._vary(gravel, 2)
    m.add(quad_xz(fx - 60, fz - 45, fx + 60, fz + 45, 0.06, W7._t("grass", (52, 68, 44)), layer=1, seg=10.0))
    m.add(quad_xz(fx - 2.4, fz - 31, fx + 2.4, fz - 4.5, 0.09, gravel, layer=1, seg=1.0, colfn=gravel_at))
    m.add(quad_xz(fx - 8.0, fz - 4.5, fx + 8.0, fz + 11.5, 0.09, gravel, layer=1, seg=1.0, colfn=gravel_at))
    # the mansion: plinth, two floors, string course, cornice, gable roof, chimneys
    mz, mw, md = fz + 16.0, 26.0, 8.0
    front = mz - md / 2
    m.add(box(mw + 0.4, 0.8, md + 0.4, stone, center=(fx, 0.4, mz)))
    m.add(box(mw, 8.4, md, plaster, center=(fx, 4.6, mz)))
    m.add(box(mw + 0.3, 0.22, md + 0.3, stone, center=(fx, 4.6, mz)))
    m.add(box(mw + 0.6, 0.4, md + 0.6, stone, center=(fx, 8.9, mz)))
    m.add(W7._gable_z(md + 0.6, mw + 0.2, 0.0, 3.0, tile, plaster, oh=0.4), rot_y(90), (fx, 9.1, mz))
    for dx in (-8.0, 8.0):
        m.add(box(0.9, 2.6, 0.9, plaster, center=(fx + dx, 11.4, mz + 1.2)))
        m.add(box(1.1, 0.2, 1.1, stone, center=(fx + dx, 12.75, mz + 1.2)))
    for s in (-1, 1):                                                               # the wings
        wx = fx + s * 17.0
        m.add(box(8.4, 0.8, 7.4, stone, center=(wx, 0.4, mz + 2.0)))
        m.add(box(8.0, 5.6, 7.0, plaster, center=(wx, 3.2, mz + 2.0)))
        m.add(box(8.4, 0.3, 7.4, stone, center=(wx, 6.1, mz + 2.0)))
        m.add(W7._gable_z(7.4, 8.4, 0.0, 2.2, tile, plaster, oh=0.3), rot_y(90), (wx, 6.25, mz + 2.0))
        for i in range(3):
            _window(m, wx - 2.6 + i * 2.6, 2.6, mz + 2.0 - 3.52)
    for i in range(9):                                                              # windows
        x = fx - 11.2 + i * 2.8
        for y in (2.6, 6.6):
            if abs(x - fx) > 1.0 or y > 5.0:
                _window(m, x, y, front - 0.02)
    m.add(box(1.6, 2.8, 0.1, (60, 40, 30), center=(fx, 2.2, front - 0.03)))
    m.add(box(1.3, 2.5, 0.04, (236, 210, 150), center=(fx, 2.15, front - 0.09), emissive=True))
    # portico: steps, four columns, entablature, pediment
    for k in range(3):
        m.add(box(7.4 - k * 0.5, 0.2, 2.6 - k * 0.5, stone,
                  center=(fx, 0.1 + k * 0.2, front - 1.3 + k * 0.25)))
    for dx in (-2.7, -0.9, 0.9, 2.7):
        m.add(box(0.5, 0.25, 0.5, stone, center=(fx + dx, 0.72, front - 2.0)))
        m.add(box(0.36, 4.6, 0.36, (226, 222, 210), center=(fx + dx, 3.15, front - 2.0)))
        m.add(box(0.5, 0.22, 0.5, stone, center=(fx + dx, 5.55, front - 2.0)))
    m.add(box(6.6, 0.6, 2.6, (226, 222, 210), center=(fx, 5.95, front - 1.1)))
    m.add(W7._gable_z(6.8, 2.8, 0.0, 1.4, tile, (226, 222, 210), oh=0.2), t=(fx, 6.25, front - 1.1))
    # hedges, poplars, trees in the grounds, lamp posts along the drive
    for s in (-1, 1):
        m.add(W7._hedgerow(fx + s * 3.4, fz - 30.0, fx + s * 3.4, fz - 24.0, seed=3 + s))
        m.add(W7._hedgerow(fx + s * 3.4, fz - 21.0, fx + s * 3.4, fz - 5.0, seed=5 + s))
        m.add(W7._hedgerow(fx + s * 9.5, fz - 4.0, fx + s * 9.5, fz + 9.0, seed=7 + s))
        for k in range(5):
            m.add(W7._poplar(k * 3 + (s > 0), 10.0 + (k * 7) % 3), t=(fx + s * 8.0, 0.0, fz - 28.0 + k * 5.5))
        for k in range(3):
            m.add(W7.tree(k + (s > 0) * 5), t=(fx + s * (24.0 + 4.0 * k), 0.0, fz + 2.0 - 6.0 * k))
    for x, z in ESTATE_LAMPS:
        _lamp_post(m, x, z)
    # gate piers, the iron gate standing open, the low wall
    gz = fz - 31.0
    for s in (-1, 1):
        m.add(box(1.0, 3.0, 1.0, stone, center=(fx + s * 3.2, 1.5, gz)))
        m.add(box(1.2, 0.3, 1.2, stone, center=(fx + s * 3.2, 3.15, gz)))
        m.add(box(0.6, 0.5, 0.6, GOLD, center=(fx + s * 3.2, 3.55, gz)))
        m.add(box(30.0, 1.1, 0.5, stone, center=(fx + s * 18.7, 0.55, gz)))
        leaf = Mesh()
        for k in range(8):
            leaf.add(box(0.05, 2.3, 0.05, (24, 24, 26), center=(0.15 + k * 0.33, 1.15, 0.0)))
        for y in (0.3, 2.2):
            leaf.add(box(2.7, 0.08, 0.06, (24, 24, 26), center=(1.35, y, 0.0)))
        m.add(leaf, rot_y(-70 if s < 0 else -110), (fx + s * 2.7, 0.0, gz))
    # the bier: dais, black cloth, the casket draped from the waist, candles, wreaths
    m.add(box(5.0, 0.3, 3.6, stone, center=(fx, 0.15, fz)))
    m.add(box(2.6, 0.7, 1.0, (20, 20, 24), center=(fx, 0.65, fz)))
    m.add(box(2.2, 0.45, 0.8, (70, 42, 28), center=(fx, 1.225, fz)))
    m.add(box(2.0, 0.03, 0.62, (226, 214, 190), center=(fx, 1.46, fz)))
    m.add(box(2.2, 0.06, 0.06, GOLD, center=(fx, 1.0, fz - 0.41)))
    m.add(box(1.1, 0.04, 0.86, NAVY, center=(fx + 0.6, 1.47, fz)))                  # the flag
    m.add(box(1.1, 0.28, 0.02, NAVY, center=(fx + 0.6, 1.34, fz - 0.43)))
    m.add(box(1.1, 0.12, 0.02, RED, center=(fx + 0.6, 1.14, fz - 0.43)))
    m.add(box(0.2, 0.2, 0.02, GOLD, center=(fx + 0.6, 1.36, fz - 0.442)))
    for x, z in CANDLES:
        m.add(box(0.06, 1.3, 0.06, (150, 130, 80), center=(x, 0.95, z)))
        m.add(box(0.24, 0.05, 0.24, (150, 130, 80), center=(x, 1.62, z)))
        m.add(box(0.05, 0.22, 0.05, (240, 232, 212), center=(x, 1.75, z)))
    for dx in (-0.6, 0.6):
        for i in range(10):
            a = 2 * math.pi * i / 10
            col = (52, 82, 46) if i % 3 else (200, 40, 40)
            m.add(box(0.16, 0.16, 0.08, col,
                      center=(fx + dx + 0.32 * math.cos(a), 0.75 + 0.32 * math.sin(a), fz - 1.75)))
        m.add(box(0.04, 0.6, 0.04, (60, 50, 40), center=(fx + dx, 0.3, fz - 1.72)))
    for row in range(3):                                                            # empty chairs
        for i in range(-3, 4):
            if i == 0:
                continue
            x, z = fx + i * 0.9, fz - 4.6 - row * 1.1
            m.add(box(0.46, 0.06, 0.46, (36, 34, 36), center=(x, 0.46, z)))
            m.add(box(0.46, 0.5, 0.05, (36, 34, 36), center=(x, 0.74, z - 0.21)))
            for lx in (-0.2, 0.2):
                m.add(box(0.04, 0.44, 0.04, (30, 30, 32), center=(x + lx, 0.22, z)))
    return m


def estate_lights():
    """The local lights the estate shots share: candles, the porch, two drive lamps."""
    fx, fz = FUNERAL
    out = [{"pos": (x, 1.9, z), "color": (255, 196, 120), "intensity": 0.55, "range": 5.0}
           for x, z in CANDLES]
    out.append({"pos": (fx, 4.6, fz + 10.0), "color": (255, 214, 150), "intensity": 0.9, "range": 14.0})
    out += [{"pos": (x, LAMP_H + 0.3, z), "color": (255, 214, 150), "intensity": 0.7, "range": 9.0}
            for x, z in ESTATE_LAMPS[-2:]]
    return out


def lamp_glows(r, t):
    from cutscenes import m6fx3d as _fx  # lazy: numpy stack
    for x, z in ESTATE_LAMPS:
        r.add_sprite((x, LAMP_H + 0.28, z), _fx.glow((255, 214, 150), 0.9, int(t), flicker=0.05,
                                                     seed=int(x * 7 + z)), layer=_fx.FX_LAYER)
    for i, (x, z) in enumerate(CANDLES):
        r.add_sprite((x, 1.9, z), _fx.glow((255, 190, 110), 0.35, int(t), flicker=0.35, seed=i),
                     layer=_fx.FX_LAYER)


# --- shots -------------------------------------------------------------------


def train_x(t, start=30.0, speed=7.0):
    """The last car's rear, well under way: ``start`` m past the crossing."""
    return RX + S.TRAIN_LAST_X + start + speed * min(t, 20.0)


def shot(line, t):
    """(eye, target, fov, grade) for line ``line`` at ``t`` s; grade is
    "night", "dusk" (close on the train), "tv", "funeral" or "title"."""
    if line == 0:                                    # Alex on the radio, the rear step
        x = train_x(t)
        return (x - 5.4, 2.6, CZ - 2.4), (x - 0.3, 2.5, CZ), 44.0, "dusk"
    if line == 1:                                    # the President on state TV
        sx, sz = STUDIO
        return (sx + 0.1 * t, 1.65, sz - 3.4), (sx, 1.55, sz + 1.4), 32.0, "tv"
    if line == 2:                                    # the estate, the closed funeral
        fx, fz = FUNERAL
        return (fx + 1.0, 3.2, fz - 9.0 - 0.35 * t), (fx, 1.8, fz + 6.0), 50.0, "funeral"
    if line == 3:                                    # Maru in the casket
        fx, fz = FUNERAL
        return (fx - 0.3, 2.7, fz - 2.7 - 0.03 * t), (fx, 1.3, fz), 44.0, "funeral"
    if line == 4:                                    # Ucilev made Commander
        sx, sz = STUDIO
        return (sx + 0.6, 1.6, sz - 3.6 + 0.05 * t), (sx + 0.6, 1.5, sz + 1.4), 36.0, "tv"
    if line == 5:                                    # the crossing: the tractor, the train going
        return (RX - 14.0, 3.0, CZ - 9.0), (RX + 20.0, 1.5, CZ + 1.0), 50.0, "night"
    if line == 6:                                    # Ucilev at the border hut
        return ((RX - 7.6 - 0.04 * t, 2.0, CZ - 12.8), (RX + 22.0, 1.4, CZ + 2.0), 46.0, "night")
    if line == 7:                                    # close, on the step
        x = train_x(t, 120.0, 6.0)
        return (x - 3.6, 2.95, CZ - 1.9), (x - 0.3, 2.75, CZ), 34.0, "dusk"
    if line == 8:                                    # the train pulls away from us
        x = train_x(t, 150.0, 6.0)
        return (x - 12.0 - 2.0 * t, 3.4, CZ - 5.0), (x + 12.0, 2.0, CZ), 46.0, "night"
    return (RX + 60.0, 6.0, CZ - 34.0), (RX + 170.0, 2.0, CZ), 40.0, "title"


def _train_at(line, t):
    if line == 0:
        return train_x(t)
    if line == 5:
        return train_x(t, 6.0, 3.0)
    if line == 6:
        return train_x(t, 12.0, 4.0)
    if line == 7:
        return train_x(t, 120.0, 6.0)
    if line == 8:
        return train_x(t, 150.0, 6.0)
    return train_x(t, 180.0, 6.0)


def _cast(r, line, t, tm):
    if line in (1, 4):
        sx, sz = STUDIO
        S.put(r, "studio", studio, (0.0, 0.0, 0.0))
        talk = abs(math.sin(t * 11.0)) * 0.8 if line == 1 and t < 3.6 else 0.0
        _w.actor(r, "president", dict(POSES["stand"], lsh_p=24, lel=30, rsh_p=24, rel=30),
                 (sx, 0.0, sz + 1.4), 180.0 if line == 1 else 196.0, tm, seed=12, amp=0.3,
                 mouth=talk, expression="stern")
        if line == 4:
            _w.actor(r, "ucilev", dict(POSES["stand"]), (sx + 1.3, 0.0, sz + 1.5), 180.0, tm,
                     seed=34, amp=0.15, mouth=0.0)
        return
    if line in (2, 3):
        fx, fz = FUNERAL
        S.put(r, "funeral", funeral, (0.0, 0.0, 0.0))
        _w.actor(r, "maru", LYING, (fx - 0.04, 1.17, fz), 90.0, tm, seed=5, amp=0.0, mouth=0.0)
        for i, (dx, dz, yaw) in enumerate(((-1.9, -0.9, 60.0), (1.9, -0.9, 300.0),
                                           (-1.9, 0.9, 120.0), (1.9, 0.9, 240.0))):
            _w.actor(r, ("guard", "officer"), dict(POSES["stand"]), (fx + dx, 0.0, fz + dz), yaw, tm,
                     seed=40 + i, amp=0.08, mouth=0.0)
        return
    tx = _train_at(line, t)
    S.put(r, "train", S.train, (tx, 0.0, CZ), 0.0)
    S.put(r, "tractor", S.tractor, (RX, 0.0, CZ - 0.3), S.road_yaw(CZ))
    S.put(r, "barrier_arm", S.barrier_arm, (RX - 3.0, 0.05, S.BARRIER_Z + 3.0), 210.0)
    _w.actor(r, ("ally", "bodi"), dict(_SEATED, spine=22, head_p=30),
             (RX, 0.62, CZ - 1.05), S.road_yaw(CZ), tm, seed=61, amp=0.0, mouth=0.0)
    from cutscenes import m6fx3d as _fx
    for k in range(4):                                   # the dead engine smokes
        a = ((t * 0.35 + k * 0.25) % 1.0)
        r.add_sprite((RX + 0.3 * a, 2.2 + 2.6 * a, CZ + 0.6 + 0.8 * a),
                     _fx.glow((56, 54, 56), 0.5 + a * 1.2, tm, intensity=0.5 * (1.0 - a)),
                     layer=_fx.FX_LAYER)
    if line in (0, 7, 8):
        key = ("biribel", OUTFIT_GUARD)
        pose = POSES["radio"] if line == 0 else dict(POSES["stand"], head_p=8)
        _w.actor(r, key, dict(pose), (tx - 0.3, 1.26, CZ), 270.0, tm, seed=93, amp=0.25, mouth=0.0)
    if line in (5, 6):
        photo = dict(POSES["stand"], rsh_p=40, rel=70, head_p=4)
        _w.actor(r, "ucilev", photo, (RX - 5.6, 0.0, CZ - 11.0), 64.0, tm, seed=34, amp=0.12,
                 mouth=0.0)


def draw(surface, line, t):
    eye, tgt, fov, grade = shot(line, t)
    r = S.frame(eye, tgt, fov)
    del _w.LAST[:]
    _cast(r, line, t, int(t * 1000.0) + line * 7919)
    _present(r, surface, grade)
    if grade == "tv":
        _tv(surface, t)
    elif line == 0:
        _static(surface, t)
    if grade == "title":
        _title(surface, t)


def _present(r, surface, grade):
    from cutscenes import m6fx3d as _fx  # lazy: numpy stack
    surf = r.surface
    r.flush(surf)
    if grade in ("night", "title"):
        surf.fill(NIGHT, special_flags=pygame.BLEND_MULT)
    elif grade == "dusk":
        surf.fill(DUSK, special_flags=pygame.BLEND_MULT)
    elif grade == "funeral":
        surf.fill((84, 90, 124), special_flags=pygame.BLEND_MULT)
    elif grade == "tv":
        surf.fill(TV_TINT, special_flags=pygame.BLEND_MULT)
    try:
        _fx.grade_cine(surf)
    except Exception:
        pass
    _fx.present_crisp(surf, surface)


def _tv(surface, t):
    lines = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for y in range(0, HEIGHT, 3):
        pygame.draw.line(lines, (0, 0, 0, 70), (0, y), (WIDTH, y))
    surface.blit(lines, (0, 0))
    bug = font_terminal_small.render("TVR 1  -  LIVE", True, (236, 230, 210))
    pygame.draw.rect(surface, (150, 30, 30), (36, 30, bug.get_width() + 16, 24))
    surface.blit(bug, (44, 34))


def _static(surface, t):
    k = int(t * 30.0)
    for i in range(14):
        y = (k * 53 + i * 131) % HEIGHT
        a = 40 + (k * 17 + i * 29) % 60
        band = pygame.Surface((WIDTH, 1 + (i % 3)), pygame.SRCALPHA)
        band.fill((200, 200, 200, a))
        surface.blit(band, (0, y))


def _title(surface, t):
    a = max(0.0, min(1.0, (t - 0.4) / 1.6))
    img = font_title.render("CALL OF ACARISTAN", True, (232, 226, 210))
    img.set_alpha(int(255 * a))
    surface.blit(img, ((WIDTH - img.get_width()) // 2, int(HEIGHT * 0.36)))
