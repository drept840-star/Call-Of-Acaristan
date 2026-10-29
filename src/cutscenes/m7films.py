"""Mission 7 films: the dawn drop-off (beat 1), the raid lead-in (beat 5) and the burning farm (beat 6).

Scene renderers take ``(surface, t_ms)``.  They are registered lazily from
``missions/m7/meta.py`` (``M7_SCENES`` maps scene id -> module and function), so
this module, and the 3D stack behind it, loads on first draw.
"""
import math

import pygame

from core.outfits import OUTFIT_GUARD
from engine3d.core import Mesh, box
from engine3d.hold import hold_cached as _hold_cached
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from cutscenes import m7world3d as F

_BIRI = ("biribel", OUTFIT_GUARD)
_BODI = "bodi"

FIELD_PAD = (-45.0, 0.0, 15.0)
BODI_FENCE = (-24.6, 0.0, 10.0)


def _pose(**kw):
    return F.stand_pose(**kw)


def _face(a, b):
    return _w.yaw_to(a, b)


def dropoff_lift(surface, t):
    """Maru's helicopter lifts off the stubble field; Biribel shields his face."""
    u = F.k(t, 0, 4200)
    eye = F.mix((-28.5, 1.25, 4.5), (-29.5, 1.5, 5.4), u)
    tgt = F.mix((-42.0, 1.9, 13.0), (-54.0, 9.5, 16.0), F.k(t, 1000, 3200))
    r, buf = F.stage("dawn", t, eye, tgt, 50, hh=0.010, seed=11)
    F.mist(r, t, seed=11)
    F.sun(r, t, (96.0, 9.0, 40.0))
    lift = F.k(t, 700, 3300)
    # departure: keeps the lift's heading, gathers speed, noses down and climbs out of frame
    dep = F.k(t, 3600, 4400)
    go = dep * dep
    hp = (FIELD_PAD[0] - 26.0 * lift ** 1.5 - 150.0 * go,
          20.0 * lift ** 1.7 + 25.0 * dep,
          FIELD_PAD[2] + 5.0 * lift + 21.0 * go)
    yaw = _face(FIELD_PAD, (-95.0, 0.0, 22.0))
    if dep < 1.0:
        _w.helicopter(r, t, hp, yaw=yaw, rotor_speed=0.95, pitch=7.0 * lift + 8.0 * dep,
                      bank=-5.0 * lift * (1.0 - dep), blur=0.9)
    wash = max(0.0, 1.0 - lift * 1.15)
    if wash > 0.02:
        r.add_sprite((FIELD_PAD[0], 0.4, FIELD_PAD[2]),
                     _fx.powder(t, seed=4, spread_m=6.0 + 4.0 * lift, intensity=0.75 * wash,
                                col=(182, 156, 116)), layer=_fx.FX_LAYER)
    shield = 1.0 - F.k(t, 2700, 900)
    me = (-35.0, 0.0, 9.5)
    pose = _pose(lsh_p=105 * shield, lsh_r=10, lel=120 * shield + 12, spine=3 + 8 * shield,
                 head_p=8 * shield)
    _w.actor(r, _BIRI, pose, me, _face(me, hp), t, seed=52, amp=0.30, expression="neutral")
    F.finish(surface, r, buf, 11, "M7", t)


def dropoff_field(surface, t):
    """Biribel crosses the stubble toward the fence, mist and low sun."""
    u = max(0.0, min(1.0, t / 4200.0))
    x = -42.0 + 11.0 * u
    eye = (x - 0.4, 1.55, 4.0)
    tgt = (x + 2.0, 1.45, 10.0)
    r, buf = F.stage("dawn", t, eye, tgt, 46, hh=0.008, seed=17)
    F.mist(r, t, seed=17, n=12, intensity=0.12)
    F.sun(r, t, (96.0, 9.0, 40.0))
    me = (x, 0.0, 10.0)
    _w.actor(r, _BIRI, F.walk_pose(t, 0.8, tired=0.6), me, _face(me, (x + 1.0, 0.0, 10.0)), t,
             seed=52, amp=0.25, expression="neutral")
    F.finish(surface, r, buf, 17, "M7", t)


def dropoff_fence(surface, t):
    """Bodi at the fence with a feed bucket; Biribel stops opposite him."""
    u = max(0.0, min(1.0, t / 3600.0))
    eye = F.mix((-26.2, 1.5, 2.2), (-26.1, 1.5, 3.6), u)
    tgt = (-26.3, 1.45, 10.0)
    r, buf = F.stage("dawn", t, eye, tgt, 38, hh=0.006, seed=23)
    F.mist(r, t, seed=23, n=8, intensity=0.09)
    F.sun(r, t, (96.0, 9.0, 40.0))
    b = Mesh()
    b.add(box(0.34, 0.36, 0.34, F.METAL, center=(-24.95, 0.19, 9.4)))
    b.add(box(0.26, 0.02, 0.26, F.HAY, center=(-24.95, 0.37, 9.4)))
    _w.add(r, b)
    arrive = F.k(t, 0, 1300)
    me = (-29.6 + 1.6 * arrive, 0.0, 10.0)
    walking = 1.0 - arrive
    me_pose = F.walk_pose(t, 0.8, tired=0.5) if walking > 0.05 else _pose(spine=5, head_p=4)
    _w.actor(r, _BIRI, me_pose, me, _face(me, BODI_FENCE), t, seed=52, amp=0.25,
             expression="neutral")
    _w.actor(r, _BODI, _pose(spine=5, head_p=3, rsh_p=14), BODI_FENCE, _face(BODI_FENCE, me), t,
             seed=61, amp=0.30, expression="neutral")
    F.finish(surface, r, buf, 23, "M7", t)


def _burn(t, eye, tgt, fov, seed, grow=1.0, fall=0.0, boost=0.0, hh=0.008, extra=()):
    r, buf = F.stage("burn", t, eye, tgt, fov, lights=F.burn_lights(t, boost) + list(extra),
                     hh=hh, seed=seed)
    F.burn_fx(r, t, grow, layer=2)
    F.burn_roof(r, fall)
    return r, buf


def _bodi_seated(r, t, face_to, **kw):
    yaw = _face(F.SEAT_BURN, face_to)
    # Soles on the footplate; the leg solve rests the thighs on the cushion.
    pos = (F.SEAT_BURN[0], F.SEAT_BURN[1] - F.SEAT_H, F.SEAT_BURN[2])
    pose = _w.sit_pose(_w.hum(_BODI), F.SEAT_H, F.sit_pose(**kw))
    _w.actor(r, _BODI, pose, pos, yaw, t, seed=61, amp=0.20, rifle_on=True,
             expression="neutral")


def burn_wide(surface, t):
    """Night. The farmhouse and the barn burn."""
    u = F.k(t, 0, 4600)
    eye = F.mix((-7.0, 2.4, -22.0), (-3.0, 2.2, -19.0), u)
    r, buf = _burn(t, eye, (8.0, 4.2, 12.0), 56, 31, grow=F.k(t, 0, 3600))
    F.finish(surface, r, buf, 31, "M7", t)


def burn_tractor(surface, t):
    """The barn roof falls in; Bodi watches from the tractor seat."""
    collapse = 1700
    fall = F.k(t, collapse, 650)
    burst = max(0.0, 1.0 - (t - collapse) / 900.0) if t >= collapse else 0.0
    u = F.k(t, 0, 4600)
    eye = F.mix((-1.8, 2.25, -8.4), (-0.8, 2.2, -7.2), u)
    r, buf = _burn(t, eye, (7.0, 2.9, 3.0), 50, 37, grow=1.0, fall=fall, boost=0.8 * burst,
                   extra=_KEY_BACK)
    r.add_sprite((BARN_TOP[0], BARN_TOP[1], BARN_TOP[2]), F.sparks(t, collapse, seed=5),
                 layer=_fx.FX_LAYER)
    if burst > 0.02:
        r.add_sprite((BARN_TOP[0], BARN_TOP[1] - 1.0, BARN_TOP[2]),
                     _fx.glow((255, 170, 80), 9.0, t, intensity=0.9 * burst, core=(255, 230, 170),
                              max_px=170), layer=_fx.FX_LAYER)
    _bodi_seated(r, t, (13.0, 0.0, 12.0))
    F.finish(surface, r, buf, 37, "M7", t)


def burn_bodi(surface, t):
    """'They'll come back.' Bodi in profile, the barn lighting his side."""
    u = max(0.0, min(1.0, t / 4200.0))
    eye = F.mix((4.2, 2.3, -6.8), (3.8, 2.3, -6.0), u)
    r, buf = _burn(t, eye, (1.7, 2.4, -3.5), 38, 41, fall=1.0, hh=0.005, extra=_KEY)
    _bodi_seated(r, t, (13.0, 0.0, 12.0), head_p=3 - 3 * u)
    F.finish(surface, r, buf, 41, "M7", t)


def burn_face(surface, t):
    """'I'm coming with you.' Bodi turns toward the camera, the fire in his face."""
    u = max(0.0, min(1.0, t / 3000.0))
    eye = F.mix((4.8, 2.5, -0.5), (4.3, 2.5, -0.9), u)
    r, buf = _burn(t, eye, (1.65, 2.45, -3.5), 36, 43, fall=1.0, hh=0.004, extra=_KEY)
    turn = F.k(t, 200, 1200)
    face = F.mix((13.0, 0.0, 12.0), (eye[0], 0.0, eye[2]), turn)
    _bodi_seated(r, t, face, head_p=8 - 10 * turn, spine=8 - 4 * turn)
    F.finish(surface, r, buf, 43, "M7", t)


BARN_TOP = (F.BARN_AT[0] + 0.5, 6.4, F.BARN_AT[1] - 1.0)

# Warm fill the burning barn would throw on Bodi's near side.
_KEY = [{"pos": (4.4, 2.6, -2.2), "color": (255, 150, 80), "intensity": 0.95, "range": 7.5}]
# Same warmth from the camera side, so Bodi's back is not a black cut-out in the wide.
_KEY_BACK = [{"pos": (-0.2, 2.9, -6.2), "color": (255, 150, 80), "intensity": 0.8, "range": 7.0}]


def endcard(surface, t):
    """Dark ground with slow drifting embers behind the title text."""
    w, h = surface.get_size()
    surface.fill((6, 8, 12))
    for i in range(46):
        h1 = ((i * 7919) % 1000) / 1000.0
        h2 = ((i * 6007 + 311) % 997) / 997.0
        age = ((t * 0.00011 * (0.5 + h2)) + h1) % 1.0
        x = int(w * (0.08 + 0.84 * h1) + math.sin(t * 0.0007 + i) * 14)
        y = int(h * (1.02 - age * 1.05))
        a = int(190 * (1.0 - age))
        if 0 <= x < w and 0 <= y < h and a > 20:
            surface.fill((a, int(a * 0.5), int(a * 0.18)), (x, y, 2, 2))


def _raidin_convoy(r, t):
    """The Guard convoy, still far up the valley: three trucks crawling north
    from the far end of the track, headlights small through the night fog.
    They never reach the yard in this film - in the raid the trucks come up
    the track only in wave 2, and that is when Alex calls them (VO_226)."""
    from missions.m7 import raid_world as RW  # lazy: the raid meshes, loaded on first draw
    z = -84.0 + 6.0 * F.k(t, 0, 4200)          # ~1.5 m/s crawl; the lead ends near wave 2's start
    truck = RW.truck()
    for dz in (0.0, -7.5, -15.0):
        zz = z + dz
        RW.put(r, truck, 0.0, 0.0, zz, 0.0)
        for sx in (-0.68, 0.68):
            r.add_sprite((sx, 1.46, zz + 2.95),
                         _fx.glow((255, 236, 200), 0.5, t, core=(255, 248, 230), intensity=0.7,
                                  max_px=18), layer=_fx.FX_LAYER)


def _ally(r, name, pos, face, t, seed):
    key = ("ally", name)
    pose = _hold_cached(_w.hum(key), _pose(), getattr(_w.hum(key), "_weapon", "rifle"), "ready",
                        key=("m7film", name))
    _w.actor(r, key, pose, pos, _face(pos, face), t, seed=seed, amp=0.2, rifle_on=True, mouth=0.0)


def raidin_road(surface, t):
    """Night. Far up the valley the Guard convoy crawls, headlights on; the
    track below the yard stays empty.  The trucks are wave 2's problem."""
    eye = (2.6, 2.4, 2.0)
    tgt = (0.0, 1.1, -40.0)
    r, buf = F.stage("raid", t, eye, tgt, 40, hh=0.006, seed=47)
    _raidin_convoy(r, t)
    F.finish(surface, r, buf, 47, "M7", t)


def raidin_yard(surface, t):
    """'Eyes on the trees, not the track.' Biribel, Bodi and Alex at the east
    gate: raid wave 1's vanguard - the dog, then two riflemen - works in from
    the orchard treeline while the convoy lights stay far up the valley."""
    from missions.m7 import raid_world as RW  # lazy: the raid meshes, loaded on first draw
    me, bodi, alex = (17.2, 0.0, 0.3), (15.2, 0.0, 2.2), (16.8, 0.0, -1.9)
    orch = (34.0, 0.0, 2.0)
    eye, tgt = (-5.4, 2.05, 7.6), (24.0, 1.25, 1.2)
    r, buf = F.stage("raid", t, eye, tgt, 46, hh=0.006, seed=53)
    # the vanguard, staged like raid_brain.ORCHARD: the dog trots in first,
    # two riflemen thread the trees behind it (east -> the gate at x 20).
    du = F.k(t, 200, 3600)
    d = F.mix((37.5, 0.0, 5.5), (26.0, 0.0, 1.4), du)
    gait = du * 12.2                            # metres walked so far
    RW.put(r, RW.dog("Run", gait / RW.DOG_RUN_M * RW.dog_clip_s("Run")),  # the raid's
           d[0], 0.0, d[2], _face(d, (20.0, 0.0, 0.4)))                   # run cycle
    for seed, a, b, delay in ((71, (42.5, 0.0, 9.0), (33.5, 0.0, 5.0), 0),
                              (72, (44.0, 0.0, -4.5), (36.5, 0.0, -1.5), 500)):
        g = F.mix(a, b, F.k(t, delay, 3800))
        _w.actor(r, ("guard", "rifle"), F.walk_pose(t + delay, 0.75), g,
                 _face(g, (20.0, 0.0, 0.0)), t, seed=seed, amp=0.25, rifle_on=True,
                 hd=True, mouth=0.0, expression="neutral")
    gun = _hold_cached(_w.hum(_BIRI, flags=("shotgun",)), _pose(), "shotgun", "ready",
                       key=("m7film", "biribel"))
    _w.actor(r, _BIRI, gun, me, _face(me, orch), t, seed=52, amp=0.2, rifle_on=True,
             flags=("shotgun",), expression="neutral")
    _ally(r, "bodi", bodi, orch, t, 61)
    _ally(r, "alex", alex, orch, t, 62)
    F.finish(surface, r, buf, 53, "M7", t)
