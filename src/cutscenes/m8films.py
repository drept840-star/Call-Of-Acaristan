"""Mission 8 Revenge films: the meet at Route 12, Old Friends on the catwalk,
and the epilogue.

Scene renderers take ``(surface, t_ms)`` and are registered lazily from
``missions/m8/meta.py`` (``M8_SCENES``); the shots, captions and pacing live
in the ``m8.*`` timelines.  The meet and Old Friends play on the trap set
(``set3d``), the epilogue on the chase set (``chase_set``) and the two small
stages ``epilogue3d`` builds off the road.  Every shot moves: eased cranes,
dollies and push-ins, with the cast walking, turning and gesturing on cue.
"""
import math

import pygame

from core.config import WIDTH, font_terminal_small, font_title
from core.outfits import OUTFIT_GUARD
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from engine3d import Mesh, POSES, blend, box
from engine3d.core import Light, m_apply, m_mul, rot_y, v_add, v_sub
from engine3d.hold import hold_cached as _hold_cached
from engine3d.hold import POLES, solve_arm_safe
from missions.m7 import raid3d as R
from missions.m8.revenge import chase_set as CS
from missions.m8.revenge import epilogue3d as E
from missions.m8.revenge import set3d as S3

FILM = (640, int(_w.FILM_H * 640 / WIDTH))       # letterbox buffer, crisp x1.5625
BIRI = ("biribel", OUTFIT_GUARD)
BODI = ("ally", "bodi")
TX, TZ, TYAW = S3.TRUCK_AT
CY, CZ = S3.CATWALK_Y, S3.CATWALK_Z
VASILE = S3.VASILE_AT
BIRI_CAT = (6.2, CY, CZ)


# --- shared -------------------------------------------------------------------


def k(t, start, length):
    """Clamped smoothstep over [start, start + length] ms."""
    x = max(0.0, min(1.0, (t - start) / float(length)))
    return x * x * (3.0 - 2.0 * x)


def mix(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def _yaw(a, b):
    return math.degrees(math.atan2(b[0] - a[0], b[2] - a[2]))


def _finish(surface, r, t, seed, tint=None):
    buf = r.surface
    r.flush(buf)
    if tint is not None:
        buf.fill(tint, special_flags=pygame.BLEND_MULT)
    try:
        _fx.grade_cine(buf)
    except Exception:
        pass
    band = surface.subsurface((0, _w.SAFE_TOP, WIDTH, _w.FILM_H))
    _fx.present_crisp(buf, band)
    try:
        from cutscenes.post3d import apply_post  # lazy: numpy stack
        apply_post(band, {"grain": 0.14, "vignette": 0.30}, int(t), "m8_film_%d" % seed)
    except Exception:
        pass


def _plaza(eye, tgt, fov, t):
    r = S3.frame(eye, tgt, fov, t=int(t), size=FILM)
    del _w.LAST[:]
    return r


def _road(eye, tgt, fov, t, look="dawn", lights=()):
    r = CS.frame(eye, tgt, fov, t=int(t), size=FILM, look=look, lights=lights)
    del _w.LAST[:]
    return r


def _arms(pose, src):
    out = dict(pose)
    for key in R._ARMS:
        if key in src:
            out[key] = src[key]
    return out


def _walk(t, speed=0.8, **kw):
    """The M7 film walk: legs, arm swing and a light bob."""
    ph = t * 0.0062 * speed
    s = math.sin(ph)
    p = dict(POSES["stand"])
    p.update(lhip_p=24 * s, rhip_p=-24 * s, lkn=max(0.0, -s) * 34, rkn=max(0.0, s) * 34,
             lsh_p=-16 * s, rsh_p=16 * s, lel=12, rel=12, spine=4)
    p.update(kw)
    return p


def _biri_gun(pose, mode="ready"):
    """Biribel's pose with the shotgun held (``ready`` low, ``aim`` shouldered)."""
    hum = _w.hum(BIRI, flags=("shotgun",))
    return R._held(hum, pose, "shotgun", mode, ("m7player", mode))


def _bodi_gun(pose):
    hum = _w.hum(BODI, flags=("os12",))
    return R._held(hum, pose, "os12", "ready", ("m8_bodi_os12", "ready"))


def _biri(r, pose, pos, yaw, t, gun=True, **kw):
    kw.setdefault("expression", "neutral")
    return _w.actor(r, BIRI, pose, pos, yaw, t, seed=93, amp=kw.pop("amp", 0.25),
                    rifle_on=gun, flags=("shotgun",) if gun else (), **kw)


def _bodi(r, pose, pos, yaw, t, **kw):
    kw.setdefault("expression", "neutral")
    return _w.actor(r, BODI, pose, pos, yaw, t, seed=61, amp=kw.pop("amp", 0.3),
                    rifle_on=True, flags=("os12",), **kw)


def _vasile(r, pose, yaw, t, pos=VASILE, **kw):
    kw.setdefault("expression", "stern")
    return _w.actor(r, "vasile", pose, pos, yaw, t, seed=71, amp=kw.pop("amp", 0.3), **kw)


def _talk(t, start=250, length=3000):
    """Mouth flap for a line that starts ``start`` ms in."""
    if t < start or t > start + length:
        return 0.0
    return abs(math.sin((t - start) * 0.011)) * 0.8 * (0.6 + 0.4 * abs(math.sin(t * 0.0023)))


def _sodium(t):
    """The two M2 street lamps nearest the truck, cold dawn left on."""
    out = []
    for col, row in ((16, 69), (16, 61)):
        x, z = S3.tile(col, row)
        out.append({"pos": (x, 3.6, z), "color": (255, 168, 96), "intensity": 0.7, "range": 16.0})
    return out


# --- the meet -------------------------------------------------------------------

B_MEET = (TX + 0.7, 0.0, TZ + 3.5)       # Bodi, off the bonnet
Q_MEET = (TX + 2.2, 0.0, TZ + 2.4)       # Biribel, beside him


def meet_dawn(surface, t):
    """Dawn on Route 12: a crane down from the gantry to the farm truck."""
    u = k(t, 0, 5600)
    eye = mix((TX + 12.2, 9.5, TZ - 25.0), (TX + 6.8, 2.1, TZ - 10.5), u)
    tgt = mix((S3.VASILE_AT[0], 5.6, CZ), (TX + 0.8, 1.1, TZ + 1.0), k(t, 500, 4800))
    r = _plaza(eye, tgt, 50.0, t)
    # Bodi comes round the bonnet; Biribel stands at the door, looking north
    w = k(t, 1200, 3400)
    bp = mix((TX - 1.2, 0.0, TZ + 2.7), B_MEET, w)
    moving = 0.05 < w < 0.97
    pose = _walk(t, 0.8) if moving else dict(POSES["stand"])
    _bodi(r, _bodi_gun(pose), bp, 90.0 if moving else _yaw(B_MEET, Q_MEET), t, mouth=0.0)
    look = dict(POSES["stand"], head_p=-6, spine=2)
    _biri(r, _biri_gun(look), Q_MEET, 4.0, t, mouth=0.0)
    _finish(surface, r, t, 1)


def meet_drive(surface, t):
    """Over Biribel's shoulder onto Bodi: "I'll drive. You think." """
    d = (B_MEET[0] - Q_MEET[0], B_MEET[2] - Q_MEET[2])
    n = math.hypot(*d)
    fx, fz = d[0] / n, d[1] / n
    rx, rz = fz, -fx
    push = k(t, 0, 3800) * 0.35
    eye = (Q_MEET[0] - fx * (1.05 - push) + rx * 0.42, 1.74, Q_MEET[2] - fz * (1.05 - push) + rz * 0.42)
    tgt = (B_MEET[0], 1.52, B_MEET[2])
    r = _plaza(eye, tgt, 34.0, t)
    nod = math.sin(k(t, 1500, 600) * math.pi) * 8.0
    bp = dict(POSES["talk_turn"], head_p=nod, spine=3)
    _bodi(r, _bodi_gun(bp), B_MEET, _yaw(B_MEET, Q_MEET) - 8.0, t, mouth=_talk(t, 300, 1800))
    _biri(r, _biri_gun(dict(POSES["stand"])), Q_MEET, _yaw(Q_MEET, B_MEET), t, mouth=0.0)
    _finish(surface, r, t, 2)


def meet_gantry(surface, t):
    """Biribel looks up the road: the catwalk where the sniper lay.  A slow zoom
    finds Vasile at the rail."""
    zoom = k(t, 600, 3800)
    dx, dz = VASILE[0] - Q_MEET[0], VASILE[2] - Q_MEET[2]
    n = math.hypot(dx, dz)
    fx, fz = dx / n, dz / n
    eye = (Q_MEET[0] - fx * 0.85 + fz * 0.5, 1.62 + 0.05 * zoom, Q_MEET[2] - fz * 0.85 - fx * 0.5)
    tgt = mix((Q_MEET[0] + dx * 0.3, 2.6, Q_MEET[2] + dz * 0.3), (VASILE[0], CY + 1.9, VASILE[2]),
              k(t, 0, 2600))
    r = _plaza(eye, tgt, 46.0 - 37.0 * zoom, t)
    _biri(r, _biri_gun(dict(POSES["stand"], head_p=-12, spine=1)), Q_MEET,
          _yaw(Q_MEET, VASILE), t, mouth=0.0)
    _vasile(r, dict(POSES["stand"], head_p=6), 180.0, t, mouth=0.0)
    _finish(surface, r, t, 3)


def meet_walk(surface, t):
    """They walk up the road toward the plaza, toward us; the camera backs off."""
    u = k(t, 0, 4000)
    z0 = TZ + 3.0 + 4.6 * (t / 4000.0)
    eye = (TX + 1.6, 1.36 + 0.14 * u, z0 + 5.2 + 1.2 * u)
    tgt = (TX + 1.4, 1.22, z0)
    r = _plaza(eye, tgt, 44.0, t)
    _bodi(r, _bodi_gun(_walk(t, 0.85)), (TX + 0.6, 0.0, z0 - 0.4), 2.0, t, mouth=0.0)
    _biri(r, _biri_gun(_walk(t + 400, 0.85)), (TX + 2.2, 0.0, z0 + 0.2), 2.0, t, mouth=0.0,
          expression="angry")
    _finish(surface, r, t, 4)


# --- Old Friends ------------------------------------------------------------------


def _friends(r, t, vpose=None, vyaw=90.0, bmode="ready", bpos=BIRI_CAT, bmouth=0.0, vmouth=0.0):
    _vasile(r, vpose or dict(POSES["stand"]), vyaw, t, mouth=vmouth)
    _biri(r, _biri_gun(dict(POSES["stand"]), bmode), bpos, _yaw(bpos, VASILE), t,
          mouth=bmouth, expression="angry", amp=0.15)


def friends_catwalk(surface, t):
    """Biribel comes along the catwalk; Vasile, at the rail, turns to meet him."""
    u = k(t, 0, 4400)
    eye = mix((12.6, CY - 2.8, CZ - 7.6), (10.4, CY - 1.4, CZ - 6.2), u)
    tgt = mix((8.0, CY + 1.0, CZ), (5.0, CY + 1.2, CZ), u)
    r = _plaza(eye, tgt, 44.0, t)
    w = k(t, 0, 3000)
    bpos = mix((8.6, CY, CZ), BIRI_CAT, w)
    pose = _walk(t, 0.6, spine=6) if w < 0.97 else dict(POSES["stand"])
    _biri(r, _biri_gun(pose), bpos, 270.0, t, mouth=0.0, expression="angry", amp=0.15)
    turn = k(t, 2600, 1300)
    _vasile(r, dict(POSES["stand"], head_y=30.0 * (1.0 - turn)), 180.0 - 90.0 * turn, t, mouth=0.0)
    _finish(surface, r, t, 10)


def friends_four(surface, t):
    """Over Biribel onto Vasile: "You picked the four over the three hundred." """
    d = k(t, 0, 4200)
    eye = (7.4 - 0.25 * d, CY + 1.76, CZ + 0.52)
    r = _plaza(eye, (VASILE[0], CY + 1.52, VASILE[2]), 36.0 - 3.0 * d, t)
    _friends(r, t, dict(POSES["stand"], head_p=-2), vmouth=_talk(t, 300, 2600))
    _finish(surface, r, t, 11)


def friends_desk(surface, t):
    """Over Vasile onto Biribel: "You didn't pick the three hundred.  You picked the desk." """
    d = k(t, 0, 4200)
    eye = (2.35 + 0.25 * d, CY + 1.76, CZ + 0.45)
    r = _plaza(eye, (BIRI_CAT[0], CY + 1.52, BIRI_CAT[2]), 36.0 - 3.0 * d, t)
    _friends(r, t, bmouth=_talk(t, 300, 2800))
    _finish(surface, r, t, 12)


def friends_matter(surface, t):
    """Wide from the south, the road below: Vasile looks down at it."""
    d = k(t, 0, 5000)
    eye = (4.9 + 0.6 * d, CY + 1.5, CZ - 6.4 - 0.6 * d)
    r = _plaza(eye, (4.9, CY + 1.25, CZ), 50.0, t)
    look = k(t, 900, 1100)
    vp = dict(POSES["stand"], head_y=-38.0 * look, head_p=8.0 * look, spine=2.0 * look)
    _friends(r, t, vp, vmouth=_talk(t, 1200, 2600))
    _finish(surface, r, t, 13)


def friends_taught(surface, t):
    """Close on Vasile, a slow push: the cold barrel, the steady hands."""
    d = k(t, 0, 5200)
    eye = (6.0 - 0.6 * d, CY + 1.7, CZ - 1.5 + 0.3 * d)
    r = _plaza(eye, (VASILE[0], CY + 1.62, VASILE[2]), 34.0 - 4.0 * d, t)
    hands = k(t, 1400, 900) * (1.0 - k(t, 3800, 900))
    vp = dict(POSES["stand"], lsh_p=24 * hands, lel=60 * hands, rsh_p=24 * hands, rel=60 * hands,
              head_p=-3)
    _friends(r, t, vp, vmouth=_talk(t, 300, 3600))
    _finish(surface, r, t, 14)


def friends_chose(surface, t):
    """Tight over Biribel: "I chose the many.  You chose the four." """
    d = k(t, 0, 4200)
    eye = (6.95 - 0.2 * d, CY + 1.72, CZ + 0.4)
    r = _plaza(eye, (VASILE[0], CY + 1.5, VASILE[2]), 31.0 - 4.0 * d, t)
    _friends(r, t, dict(POSES["stand"], head_p=-4, spine=-2), vmouth=_talk(t, 300, 2400))
    _finish(surface, r, t, 15)


def friends_raise(surface, t):
    """Low profile on the catwalk: the shotgun comes up.  Vasile does not move."""
    eye = mix((4.9, CY + 0.5, CZ - 3.6), (4.9, CY + 0.7, CZ - 3.1), k(t, 0, 2800))
    r = _plaza(eye, (4.9, CY + 1.3, CZ), 46.0, t)
    up = k(t, 400, 900)
    hum = _w.hum(BIRI, flags=("shotgun",))
    low = R._held(hum, dict(POSES["stand"]), "shotgun", "ready", ("m7player", "ready"))
    aim = R._held(hum, dict(POSES["stand"]), "shotgun", "aim", ("m7player", "aim"))
    _vasile(r, dict(POSES["stand"], head_p=-2), 90.0, t, mouth=0.0)
    _biri(r, blend(low, aim, up), BIRI_CAT, _yaw(BIRI_CAT, VASILE), t, mouth=0.0,
          expression="angry", amp=0.1)
    _finish(surface, r, t, 16)


# --- the descent ----------------------------------------------------------------
# From the kill to the chase: he leaves Vasile on the grating when headlights
# show on the plain to the east, climbs down, Bodi has the tractor at the ladder
# foot, and the last shot lands on the chase's own opening camera.

LX, LZ = S3.LADDER_X, S3.LADDER_Z - 0.28        # on the rungs (S3.ladder_climb mark)
TRAC_AT = (11.2, 0.0, 52.2)                     # the tractor at the ladder foot, facing the road


def _convoy(r, t, x=95.0, n=3):
    """Convoy on a farm road across the plain east of the plaza, running north
    toward Route 12: the chase's own Guard cars, their lamps lit at the nose.
    Past x=95 the map's hedge stays below the sight line to the cars."""
    for i in range(n):
        p = (x + i * 2.0, 0.0, CZ - 50.0 + t * 0.012 - i * 9.0)
        CS.put_wheeled(r, "jeep", p, 0.0, 0.0, t * 0.012)
        r.add_blob_shadow((p[0], 0.06, p[2]), 1.15, 2.4, 0.5)
        for dx in (-0.6, 0.6):
            r.add_sprite((p[0] + dx, p[1] + 0.9, p[2] + 2.2),
                         _fx.glow((255, 232, 196), 1.4, int(t), flicker=0.1, seed=i,
                                  core=(255, 250, 236), intensity=1.0, max_px=36),
                         layer=_fx.FX_LAYER)


def _body(r, t):
    from missions.m8.revenge import kill3d as K
    _vasile(r, K._full(K._GROUND), 90.0, t, pos=(VASILE[0], CY, VASILE[2] - 0.03),
            amp=0.0, mouth=0.0, expression="neutral", hd=True, wound=3, bloody=True,
            rifle_on=False, flags=("cig_dropped",))
    _w.add(r, K._pool_mesh(VASILE[0] - 0.45, VASILE[2] - 0.03, 0.62, (52, 5, 9), CY + 0.007, 3.7))
    _w.add(r, K._pool_mesh(VASILE[0] - 0.06, VASILE[2] - 0.03, 0.42, (54, 5, 9), CY + 0.007, 1.1))


def _rig(tractor):
    """A drawing-only chase scene (no audio, never begun): its tractor, trailer,
    LMG mount, Bodi and Biribel at the gun.  ``tractor`` pins the rig to a
    (pos, yaw) off the chase road, for the plaza."""
    from missions.m8.revenge import chase3d as C
    sc = C.ChaseScene()
    (x, y, zz), yaw = tractor
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    trailer = ((x - C.HITCH * s, y, zz - C.HITCH * c), yaw)
    sc.tractor_pos = lambda: tractor
    sc.tractor_pitch = lambda: 0.0
    sc.trailer_pos = lambda: trailer
    return sc


def descent_body(surface, t):
    """From beyond the body, down the catwalk: he stands over Vasile, looks up
    at headlights on the plain, turns his back and walks for the ladder."""
    d = k(t, 0, 4200)
    eye = mix((-0.9, CY + 1.6, CZ - 0.9), (-0.6, CY + 1.7, CZ - 1.0), d)
    r = _plaza(eye, mix((5.0, CY + 0.6, CZ), (5.8, CY + 0.85, CZ), d), 52.0, t)
    _body(r, t)
    _convoy(r, t)
    turn = k(t, 2300, 700)
    w = k(t, 2800, 1400)
    pos = mix(BIRI_CAT, (LX - 0.4, CY, CZ - 0.15), w)
    up = k(t, 1300, 700)                       # the lights on the plain: he looks up
    look = dict(POSES["stand"], head_p=22 * (1.0 - up), spine=4 * (1.0 - up))
    pose = _walk(t, 0.6) if w > 0.02 else look
    _biri(r, _biri_gun(pose), pos, 270.0 + 180.0 * turn, t, mouth=0.0, expression="sad", amp=0.1)
    _finish(surface, r, t, 30)


def descent_ladder(surface, t):
    """Wide from the road below: down the ladder, back to us."""
    u_cam = k(t, 0, 5200)
    eye = mix((14.2, 1.1, 45.2), (13.0, 1.3, 46.6), u_cam)
    hum = _w.hum(BIRI)
    if t < 900:          # back over the lip onto the top rungs
        u = 1.0 - (1.0 - S3.LADDER_CLIMB_UP) * k(t, 0, 900)
        pose, pos, yaw, _r = S3.ladder_climb(hum, u)
    elif t < 4800:       # rung by rung down to the ground
        u = S3.LADDER_CLIMB_UP * (1.0 - k(t, 900, 3900))
        pose, pos, yaw, _r = S3.ladder_climb(hum, u)
    else:                # off the bottom rung, turning for the tractor
        off = k(t, 4800, 400)
        pose0, pos0, _y, _r = S3.ladder_climb(hum, 0.0)
        pose = blend(pose0, POSES["stand"], off)
        pos = (pos0[0], 0.0, pos0[2] - 0.3 * off)
        yaw = 90.0 * off
    tgt = mix((LX, CY + 0.6, LZ), (LX, max(1.2, pos[1] + 0.6), LZ), k(t, 600, 4200))
    r = _plaza(eye, tgt, 50.0, t)
    _body(r, t)
    _biri(r, pose, pos, yaw, t, gun=False, mouth=0.0, amp=0.0)
    _finish(surface, r, t, 31)


def descent_geton(surface, t):
    """The ladder foot: Bodi on the tractor seat, engine running.  "Get on." """
    from missions.m8.revenge import chase3d as C
    d = k(t, 0, 3600)
    eye = mix((2.8, 2.0, 50.0), (3.2, 2.05, 50.4), d)     # the tractor's near side
    r = _plaza(eye, mix((10.4, 1.4, 50.0), (10.8, 1.5, 50.4), d), 46.0, t)
    _body(r, t)
    sc = _rig(tractor=(TRAC_AT, CS.road_yaw(C.PULL_Z0)))  # the heading the chase starts on
    jit = 0.012 * math.sin(t * 0.09)           # the idle shakes the whole machine
    (tx, ty, tz), tyaw = sc.tractor_pos()
    CS.put_wheeled(r, "tractor", (tx, ty + jit, tz), tyaw, 0.0, 0.0)
    (lx, ly, lz), lyaw = sc.trailer_pos()
    CS.put_wheeled(r, "trailer", (lx, ly, lz), lyaw, 0.0, 0.0)
    r.add_blob_shadow((tx, 0.06, tz), 1.4, 2.1, 0.5)
    r.add_blob_shadow((lx, 0.06, lz), 1.3, 2.1, 0.5)
    sc._draw_mount(r)
    seat = C._local((tx, ty + jit, tz), tyaw, (0.0, 0.62, -0.75))
    turn = k(t, 0, 700)
    bp = dict(C._SEATED, head_y=-70 * turn, spine=6 + 4 * turn)
    _w.actor(r, BODI, bp, seat, tyaw, int(t), seed=61, amp=0.2, rifle_on=False,
             mouth=_talk(t, 500, 700), expression="neutral")
    # Biribel from the ladder foot to the trailer's side, then up onto the bed
    w = k(t, 0, 2200)
    side = (lx - 1.25, 0.0, lz - 0.6)
    p = mix((LX, 0.0, LZ - 0.3), side, w)
    climb = k(t, 2600, 700)
    if climb > 0.0:
        p = mix(side, (lx - 0.4, C.FEET, lz - 0.6), climb)
        pose = blend(dict(POSES["kneel"], lsh_p=60, rsh_p=60), POSES["stand"], climb)
    else:
        pose = _walk(t, 0.9) if 0.02 < w < 0.98 else dict(POSES["stand"])
    _biri(r, _biri_gun(pose), p, _yaw(p, (lx, 0.0, lz)) if w < 0.98 else 90.0, t, mouth=0.0,
          expression="angry")
    _finish(surface, r, t, 32)


def descent_pullout(surface, t):
    """The farm track: the tractor pulls away from standstill and the jeeps come
    up behind.  The film draws the chase's own scene (``pullout_scene``); the
    camera swings round behind him onto the chase's opening camera, so the last
    frame is the first frame of the chase."""
    from missions.m8.revenge import chase3d as C
    s = min(t, C.PULL_S * 1000.0) / 1000.0
    sc = C.pullout_scene(s)
    (tx, ty, tz), _ = sc.tractor_pos()
    end_eye, end_tgt, end_fov = sc.camera()
    side_eye = (CS.road_x(tz + 4.0) + 6.0, 1.4, tz + 4.0)
    side_tgt = (tx, 1.3, tz - 2.0)
    u = k(t, 2000, 2500)
    sc.render(surface, mix(side_eye, end_eye, u), mix(side_tgt, end_tgt, u),
              48.0 + (end_fov - 48.0) * u)


# --- the epilogue -------------------------------------------------------------

RX, XZ = E.RX, E.CZ
SX, SZ = E.STUDIO
FX, FZ = E.FUNERAL


def _crossing_cast(r, t, train, bodi=True):
    CS.put(r, "train", CS.train, (train, 0.0, XZ), 0.0)
    CS.put_wheeled(r, "tractor_dark" if bodi else "tractor",
                   (RX, 0.0, XZ - 0.3), CS.road_yaw(XZ))
    CS.put(r, "barrier_arm", CS.barrier_arm, (RX - 3.0, 0.05, CS.BARRIER_Z + 3.0), 210.0)
    if bodi:
        _w.actor(r, BODI, dict(E._SEATED, spine=22, head_p=30), (RX, 0.62, XZ - 1.05),
                 CS.road_yaw(XZ), int(t), seed=61, amp=0.0, mouth=0.0)
        sec = t / 1000.0
        for i in range(4):
            a = (sec * 0.35 + i * 0.25) % 1.0
            r.add_sprite((RX + 0.3 * a, 2.2 + 2.6 * a, XZ + 0.6 + 0.8 * a),
                         _fx.glow((56, 54, 56), 0.5 + a * 1.2, int(t),
                                  intensity=0.5 * (1.0 - a)),
                         layer=_fx.FX_LAYER)


def epi_radio(surface, t):
    """The last car's rear step, under way: Alex on the radio."""
    x = E.train_x(t / 1000.0, 50.0, 7.0)
    sway = math.sin(t * 0.0021) * 0.05
    eye = (x - 5.0 + 0.6 * k(t, 0, 5000), 2.55 + sway, XZ - 2.3)
    r = _road(eye, (x - 0.3, 2.45, XZ), 42.0, t)
    _crossing_cast(r, t, x, bodi=False)
    radio = dict(POSES["radio"], head_p=10, spine=8)
    _biri(r, radio, (x - 0.3, 1.26, XZ), 270.0, t, gun=False, mouth=0.0, amp=0.2)
    _finish(surface, r, t, 20, tint=(214, 206, 226))
    _static(surface, t)


def _studio_lights():
    return [
        {"pos": (SX - 1.6, 2.7, SZ - 2.0), "color": (255, 228, 192), "intensity": 0.95, "range": 8.0},  # warm key
        {"pos": (SX + 2.4, 2.2, SZ - 2.4), "color": (130, 165, 225), "intensity": 0.28, "range": 8.0},  # cool fill
        {"pos": (SX + 0.4, 2.6, SZ + 2.5), "color": (110, 165, 255), "intensity": 0.70, "range": 6.5},  # rim
    ]


def _studio(eye, tgt, fov, t):
    """Indoor studio frame: night skybox (no outdoor dawn sun/clouds), low indoor
    ambient and no short-range distance fog washing out the back wall."""
    r = _road(eye, tgt, fov, t, look="night", lights=_studio_lights())
    r.light = Light(direction=(0.45, 0.55, -0.70), ambient=0.18, diffuse=0.40,
                    sky=0.04, tint=(0.94, 0.96, 1.0))
    r.fog_start, r.fog_end = 80.0, 400.0
    return r


def epi_president(surface, t):
    """State TV: the President seated at the desk, a slow push on the broadcast."""
    d = k(t, 0, 5000)
    eye = (SX + 0.12 * d, 1.56, SZ - 4.8 + 0.7 * d)
    r = _studio(eye, (SX, 1.46, SZ + 1.4), 42.0, t)
    CS.put(r, "studio", E.studio, (0.0, 0.0, 0.0))
    beat = k(t, 1600, 500) * (1.0 - k(t, 2800, 600))
    upper = dict(lsh_p=52 + 8 * beat, lsh_r=4, lsh_y=24, lel=58 + 10 * beat,
                 rsh_p=52, rsh_r=4, rsh_y=-24, rel=58, spine=6, head_p=-2)
    pose = _w.sit_pose(_w.hum("president"), 0.46, upper)
    _w.actor(r, "president", pose, (SX, 0.0, SZ + 1.38), 180.0, int(t), seed=12, amp=0.18,
             mouth=_talk(t, 200, 3400), expression="stern", flags=("bare_sleeve",))
    _finish(surface, r, t, 21)
    _tv(surface, t, "STATE ADDRESS")


def epi_estate(surface, t):
    """Night.  The estate, lit and empty; a closed funeral in the grounds."""
    u = k(t, 0, 6000)
    eye = mix((FX + 4.0, 7.5, FZ - 30.0), (FX + 1.4, 3.0, FZ - 14.0), u)
    tgt = mix((FX, 5.0, FZ + 16.0), (FX, 1.6, FZ + 2.0), u)
    r = _road(eye, tgt, 50.0, t, look="night", lights=E.estate_lights())
    _funeral_cast(r, t)
    _finish(surface, r, t, 22)


MARU_Y = 1.24   # root height: back rests on the satin lining (top ~1.475)


def _funeral_cast(r, t):
    CS.put(r, "funeral", E.funeral, (0.0, 0.0, 0.0))
    pos = (FX - 0.02, 1.24, FZ)
    _w.actor(r, "maru", E.maru_pose(pos, 90.0), pos, 90.0, int(t), seed=5,
             amp=0.0, mouth=0.0, expression="closed", flags=("suit",))
    honour_pose = _hold_cached(_w.hum(("guard", "officer"), flags=("os12",)),
                               dict(POSES["stand"], head_p=4),
                               "os12", "ready", key="guard_honour_ready")
    for i, (dx, dz, yaw) in enumerate(E.HONOUR):
        _w.actor(r, ("guard", "officer"), honour_pose, (FX + dx, 0.30, FZ + dz), yaw,
                 int(t), seed=40 + i, amp=0.05, mouth=0.0, rifle_on=True, flags=("os12",))
    E.lamp_glows(r, t)


def epi_casket(surface, t):
    """Maru in the open casket: high 3/4 angle looking down at his face and folded hands."""
    d = k(t, 0, 5200)
    eye = mix((FX + 0.22, 3.12, FZ - 2.24), (FX - 0.14, 2.84, FZ - 1.92), d)
    r = _road(eye, (FX - 0.28, 1.34, FZ), 46.0, t, look="night", lights=E.estate_lights())
    _funeral_cast(r, t)
    _finish(surface, r, t, 23)


def epi_commander(surface, t):
    """State TV again: the new Commander of the Presidential Guard."""
    from engine3d.rig import solve_look

    d = k(t, 0, 5000)
    eye = (SX - 0.08 + 0.10 * d, 1.66 - 0.04 * d, SZ - 4.55 + 0.75 * d)
    tgt = (SX - 0.02, 1.46, SZ + 1.48)
    r = _studio(eye, tgt, 40.0 - 3.0 * d, t)
    CS.put(r, "studio_stand", lambda: E.studio(False), (0.0, 0.0, 0.0))

    p_pos, p_yaw = (SX - 0.50, 0.08, SZ + 1.52), 120.0
    u_pos, u_yaw = (SX + 0.50, 0.08, SZ + 1.44), 236.0

    engage = k(t, 200, 700) * (1.0 - k(t, 3150, 900))
    reach_u = k(t, 350, 850)
    rel_u = k(t, 3000, 850)
    hand_on = reach_u * (1.0 - rel_u)

    u_pump = max(0.0, min(1.0, (t - 1360.0) / 1500.0))
    pump_env = math.sin(math.pi * u_pump) ** 0.7 if 0.0 < u_pump < 1.0 else 0.0
    settle = -0.012 * k(t, 1200, 160) * (1.0 - k(t, 2800, 200))
    pump_y = settle + 0.036 * pump_env * math.sin(4.0 * math.pi * u_pump)
    nod = math.sin(math.pi * max(0.0, min(1.0, (t - 1450.0) / 900.0))) * 4.0

    p_hum = _w.hum("president", flags=("bare_sleeve",))
    u_hum = _w.hum("ucilev")

    p_base = dict(POSES["stand"], spine=3.0 + 5.0 * engage, twist=-20.0 * engage,
                  lsh_p=10.0, lsh_r=6.0, lel=18.0)
    u_base = dict(POSES["stand"], spine=3.0 + 7.0 * engage, twist=18.0 * engage,
                  lsh_p=6.0, lsh_r=5.0, lel=12.0)

    # Solve breathing before arm IK and pass amp=0.0 so clasped hands stay locked.
    p_live = _w.life_pose(p_base, int(t), 0.10, 12)
    u_live = _w.life_pose(u_base, int(t), 0.08, 34)

    _, pj0, _ = p_hum.pose_world(p_live, p_pos, p_yaw, rifle_on=False)
    _, uj0, _ = u_hum.pose_world(u_live, u_pos, u_yaw, rifle_on=False)
    cam_look = (eye[0], 1.62, eye[2])
    p_gaze = mix(cam_look, uj0["head"], engage)
    u_gaze = mix(cam_look, pj0["head"], engage)
    phy, php = solve_look(pj0["head"], p_gaze, p_yaw + p_live["twist"])
    uhy, uhp = solve_look(uj0["head"], u_gaze, u_yaw + u_live["twist"])
    p_live["head_y"], p_live["head_p"] = phy, php - p_live["spine"] + nod
    u_live["head_y"], u_live["head_p"] = uhy, uhp - u_live["spine"] + nod * 1.2

    if hand_on > 0.0:
        _, pj, _ = p_hum.pose_world(p_live, p_pos, p_yaw, rifle_on=False)
        _, uj, _ = u_hum.pose_world(u_live, u_pos, u_yaw, rifle_on=False)
        clasp = (SX - 0.01, 1.42 + pump_y, SZ + 1.42)
        p_clasp_pt = (clasp[0] - 0.018, clasp[1] - 0.004, clasp[2] - 0.024)
        u_clasp_pt = (clasp[0] + 0.018, clasp[1] + 0.004, clasp[2] + 0.024)
        arc = math.sin(math.pi * hand_on)
        p_tgt = tuple(mix(pj["rhand"], p_clasp_pt, hand_on)[i] + (0.06, 0.02, -0.09)[i] * arc
                      for i in range(3))
        u_tgt = tuple(mix(uj["rhand"], u_clasp_pt, hand_on)[i] + (-0.06, 0.02, 0.05)[i] * arc
                      for i in range(3))
        shake_poles = ((0.70, -0.95, -0.45),) + POLES
        p_ik = solve_arm_safe(p_hum, p_live, p_pos, p_yaw, "r", p_tgt, poles=shake_poles)
        u_ik = solve_arm_safe(u_hum, u_live, u_pos, u_yaw, "r", u_tgt, poles=shake_poles)
        w_ik = min(1.0, hand_on / 0.15)
        p_pose = blend(p_live, p_ik, w_ik) if w_ik < 1.0 else p_ik
        u_pose = blend(u_live, u_ik, w_ik) if w_ik < 1.0 else u_ik
    else:
        p_pose, u_pose = p_live, u_live

    _w.actor(r, "president", p_pose, p_pos, p_yaw, int(t), seed=12, amp=0.0,
             mouth=0.0, expression="stern", flags=("bare_sleeve",))
    _w.actor(r, "ucilev", u_pose, u_pos, u_yaw, int(t), seed=34, amp=0.0,
             mouth=0.0, expression="stern")
    _finish(surface, r, t, 24)
    _tv(surface, t, "NEW COMMANDER: UCILEV")


def epi_crossing(surface, t):
    """The Kim Kim crossing: the tractor dead on the rails, the train going."""
    tx = E.train_x(t / 1000.0, 6.0, 3.0)
    u = k(t, 0, 6000)
    eye = mix((RX - 15.0, 3.6, XZ - 10.0), (RX - 11.5, 2.4, XZ - 7.5), u)
    r = _road(eye, mix((RX + 4.0, 1.4, XZ), (RX + 18.0, 1.6, XZ + 1.0), u), 48.0, t)
    _crossing_cast(r, t, tx)
    _finish(surface, r, t, 25)


def _photo_card(r, hand, yaw):
    """Biribel's photo in Ucilev's hand: white card, portrait on both faces."""
    M = rot_y(yaw)
    parts = (box(0.09, 0.12, 0.011, (236, 236, 232), center=(0.0, 0.06, 0.0)),
             box(0.08, 0.11, 0.0015, (54, 58, 62), center=(0.0, 0.06, 0.0065)),
             box(0.08, 0.11, 0.0015, (54, 58, 62), center=(0.0, 0.06, -0.0065)))
    for m in parts:
        verts = [tuple(a + b for a, b in zip(m_apply(M, v), hand)) for v in m.verts]
        r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces])


def epi_ucilev(surface, t):
    """Ucilev at the border post with Biribel's photo; he watches the train go."""
    tx = E.train_x(t / 1000.0, 22.0, 5.0)
    up = k(t, 600, 1200)
    u = k(t, 0, 6000)
    ux, uz = RX - 5.6, XZ - 11.0
    yaw = _yaw((ux, 0, uz), (tx, 0, XZ))
    fx, fz = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    back = 2.6 - 0.5 * u                              # over his right shoulder, easing in
    eye = (ux - fx * back + fz * 0.42, 1.86, uz - fz * back - fx * 0.42)
    r = _road(eye, mix((ux, 1.6, uz), (tx - 4.0, 1.7, XZ), 0.55), 50.0 - 6.0 * u, t)
    _crossing_cast(r, t, tx)
    photo = dict(POSES["stand"], rsh_p=30 + 24 * up, rel=50 + 30 * up, head_p=8 - 10 * k(t, 2600, 1400))
    joints = _w.actor(r, "ucilev", photo, (ux, 0.0, uz), yaw, int(t), seed=34,
                      amp=0.12, mouth=0.0)
    _photo_card(r, joints["rhand"], yaw)
    _finish(surface, r, t, 26)


def epi_names(surface, t):
    """Close on the step: "Gabi, Seby, Darius.  It's done." """
    x = E.train_x(t / 1000.0, 120.0, 6.0)
    sway = math.sin(t * 0.0021) * 0.04
    eye = (x - 3.3 - 0.3 * k(t, 0, 5000), 2.9 + sway, XZ - 1.8)
    r = _road(eye, (x - 0.3, 2.72, XZ), 32.0, t)
    _crossing_cast(r, t, x, bodi=False)
    _biri(r, dict(POSES["stand"], head_p=10, spine=6), (x - 0.3, 1.26, XZ), 270.0, t, gun=False,
          mouth=_talk(t, 300, 2800), amp=0.2)
    _finish(surface, r, t, 27)


def epi_volkov(surface, t):
    """The train pulls away: "Volkov - I caught your train." """
    x = E.train_x(t / 1000.0, 14.0, 6.0)
    eye = (RX + 8.0, 3.0, XZ - 4.2)
    r = _road(eye, (x + 6.0, 2.0, XZ), 40.0 - 8.0 * k(t, 0, 6000), t)
    _crossing_cast(r, t, x, bodi=False)
    _biri(r, dict(POSES["stand"], head_y=-25, spine=3), (x - 0.3, 1.26, XZ), 270.0, t, gun=False,
          mouth=_talk(t, 300, 2400), amp=0.2)
    _finish(surface, r, t, 28)


def epi_title(surface, t):
    """The train small on the plain; the title."""
    x = E.train_x(t / 1000.0, 180.0, 6.0)
    eye = (RX + 60.0, 6.0 + 2.0 * k(t, 0, 6000), XZ - 34.0)
    r = _road(eye, (RX + 170.0, 2.0, XZ), 40.0, t)
    _crossing_cast(r, t, x, bodi=False)
    _finish(surface, r, t, 29)
    a = k(t, 500, 1800)
    img = font_title.render("CALL OF ACARISTAN", True, (232, 226, 210))
    img.set_alpha(int(255 * a))
    surface.blit(img, ((WIDTH - img.get_width()) // 2, _w.SAFE_TOP + int(_w.FILM_H * 0.38)))


# --- the gunship arrives (mid-chase cut) --------------------------------------


def _heli_sc_at(z_off):
    """Read-only snapshot rig for chase-road cutscene frames (never mutates live chase state)."""
    from missions.m8.revenge import chase3d as C
    sc = C._SCENE
    if sc is None or not sc.active():
        sc = C.ChaseScene()
        sc.z = CS.SECTIONS[3]
    z = sc.z + z_off
    pos = (CS.road_x(z) + sc.lane, CS.ditch_y(z), z)
    yaw = CS.road_yaw(z)
    lz = z - C.HITCH
    lpos = (CS.road_x(lz) + sc.lane, CS.ditch_y(lz), lz)
    lyaw = CS.road_yaw(lz)
    return sc, z, pos, yaw, lpos, lyaw


def _draw_cut_rig(r, sc, pos, yaw, lpos, lyaw, odo, tm):
    CS.put_wheeled(r, "tractor", pos, yaw, 0.0, odo)
    r.add_blob_shadow((pos[0], pos[1] + 0.06, pos[2]), 1.4, 2.1, 0.5)
    CS.put_wheeled(r, "trailer", lpos, lyaw, 0.0, odo)
    r.add_blob_shadow((lpos[0], lpos[1] + 0.06, lpos[2]), 1.3, 2.1, 0.5)
    old_t, old_l = sc.tractor_pos, sc.trailer_pos
    sc.tractor_pos = lambda: (pos, yaw)
    sc.trailer_pos = lambda: (lpos, lyaw)
    sc._rig_key = None                 # the moved rig is not the cached live one
    try:
        sc._draw_mount(r)
        g = sc._rig()
    finally:
        sc.tractor_pos, sc.trailer_pos = old_t, old_l
    return g


def heli_road(surface, t):
    """Shot 1: Static cuts into the radio on Route 12; Bodi glances back."""
    from missions.m8.revenge import chase3d as C
    s = t / 1000.0
    sc, _z, pos, yaw, lpos, lyaw = _heli_sc_at(7.5 * s)
    u = k(t, 0, 3400)
    eye = C._local(lpos, lyaw, (-5.0 + 0.8 * u, 2.85 - 0.15 * u, -5.0 + 1.4 * u))
    tgt = C._local(lpos, lyaw, (0.0, 1.05, 0.9))     # the rig in frame, Bodi past it
    r = _road(eye, tgt, 50.0, t)
    g = _draw_cut_rig(r, sc, pos, yaw, lpos, lyaw, sc.odo + 7.5 * s, int(t))
    glance = k(t, 350, 750)
    _w.actor(
        r, BODI,
        dict(C._SEATED, head_y=-62 * glance, head_p=-4, spine=6),
        C._local(pos, yaw, (0.0, 0.62, -0.75)), yaw, int(t),
        seed=61, amp=0.2, rifle_on=False, mouth=_talk(t, 450, 2600),
    )
    _biri(r, dict(g["pose"], head_y=28 * glance, head_p=-6 * glance),
          g["feet"], sc.yaw, t, gun=False, mouth=0.0, expression="angry", amp=0.1)
    _finish(surface, r, t, 40)


def _norm3(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross3(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _mat_to_quat(m):
    tr = m[0] + m[4] + m[8]
    if tr > 0.0:
        s = math.sqrt(tr + 1.0) * 2.0
        return ((m[7] - m[5]) / s, (m[2] - m[6]) / s, (m[3] - m[1]) / s, 0.25 * s)
    if m[0] > m[4] and m[0] > m[8]:
        s = math.sqrt(1.0 + m[0] - m[4] - m[8]) * 2.0
        return (0.25 * s, (m[1] + m[3]) / s, (m[2] + m[6]) / s, (m[7] - m[5]) / s)
    if m[4] > m[8]:
        s = math.sqrt(1.0 + m[4] - m[0] - m[8]) * 2.0
        return ((m[1] + m[3]) / s, 0.25 * s, (m[5] + m[7]) / s, (m[2] - m[6]) / s)
    s = math.sqrt(1.0 + m[8] - m[0] - m[4]) * 2.0
    return ((m[2] + m[6]) / s, (m[5] + m[7]) / s, 0.25 * s, (m[3] - m[1]) / s)


def _quat_to_mat(q):
    x, y, z, w = q
    return (
        1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w),
        2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w),
        2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y),
    )


def _quat_slerp(qa, qb, u):
    dot = sum(a * b for a, b in zip(qa, qb))
    if dot < 0.0:
        qb = tuple(-b for b in qb)
        dot = -dot
    if dot > 0.9995:
        q = tuple(qa[i] + (qb[i] - qa[i]) * u for i in range(4))
        n = math.sqrt(sum(c * c for c in q)) or 1.0
        return tuple(c / n for c in q)
    th0 = math.acos(max(-1.0, min(1.0, dot)))
    th = th0 * u
    s0 = math.cos(th) - dot * math.sin(th) / math.sin(th0)
    s1 = math.sin(th) / math.sin(th0)
    return tuple(s0 * qa[i] + s1 * qb[i] for i in range(4))


def _head_world(hum, pose, pos, yaw):
    """(neck_world, orthonormal head rotation matrix) from the posed rig."""
    places, _joints, root = hum.pose_world(pose, pos, yaw, rifle_on=False)
    sc = hum._scale
    for slot, _key, M, org, _g, _fb in places:
        if slot == 2:
            return v_add(org, root), tuple(c / sc for c in M)
    return pos, rot_y(yaw)


def _place_handset(r, mesh, scale, pos, R):
    placed = Mesh()
    placed.verts = [
        v_add(pos, m_apply(R, (v[0] * scale, v[1] * scale, v[2] * scale)))
        for v in mesh.verts
    ]
    placed.faces = list(mesh.faces)
    _w.add(r, placed)


def _phone_cord(r, jack_w, collar_w, desk_y=0.90):
    """Segmented sagging handset cord between base jack and handset collar."""
    m = Mesh()
    col = (24, 26, 32)
    pts = []
    n_seg = 12
    sag_y = max(desk_y + 0.010, min(jack_w[1], collar_w[1]) - 0.14)
    ctrl = (
        0.5 * (jack_w[0] + collar_w[0]) + 0.05,
        sag_y,
        0.5 * (jack_w[2] + collar_w[2]) - 0.02,
    )
    for i in range(n_seg + 1):
        u = i / float(n_seg)
        w0, w1, w2 = (1.0 - u) ** 2, 2.0 * (1.0 - u) * u, u * u
        px = w0 * jack_w[0] + w1 * ctrl[0] + w2 * collar_w[0]
        py = max(desk_y + 0.008, w0 * jack_w[1] + w1 * ctrl[1] + w2 * collar_w[1])
        pz = w0 * jack_w[2] + w1 * ctrl[2] + w2 * collar_w[2]
        pts.append((px, py, pz))
    for a, b in zip(pts[:-1], pts[1:]):
        mid = (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]), 0.5 * (a[2] + b[2]))
        d = math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2)
        m.add(box(0.013, max(0.013, d * 0.65), 0.013, col, center=mid))
    _w.add(r, m)


def heli_retardovici(surface, t):
    """Shot 2: Retardovici seated at the command desk ordering the gunship in."""
    cx, cz = E.CMD_ROOM
    u = k(t, 0, 4800)
    # Slight right-front 3/4 framing keeps phone pickup on desk and ear hold clearly visible.
    eye = (cx - 0.54 + 0.16 * u, 1.52 - 0.04 * u, cz - 3.90 + 0.72 * u)
    tgt = (cx - 0.14 + 0.04 * u, 1.32 + 0.04 * u, cz + 1.25)
    r = _road(eye, tgt, 40.0 - 5.0 * u, t, look="night", lights=E.command_lights())
    r.light = Light(direction=(0.45, 0.55, -0.70), ambient=0.18, diffuse=0.40,
                    sky=0.04, tint=(0.94, 0.96, 1.0))
    r.fog_start, r.fog_end = 80.0, 400.0
    CS.put(r, "cmd_room", E.command_room, (0.0, 0.0, 0.0))

    reach_u = k(t, 0, 440)
    lift_u = k(t, 580, 760)
    reach_lean = reach_u * (1.0 - lift_u)
    beat = k(t, 1900, 450) * (1.0 - k(t, 3300, 600))
    upper = dict(
        spine=6.0 + 6.0 * reach_lean,
        twist=2.0 + 7.0 * reach_lean,
        head_y=-3.0 + 16.0 * reach_lean,
        head_p=-2.0 + 10.0 * reach_lean + 3.0 * beat,
    )
    r_pos, r_yaw = (cx, 0.0, cz + 1.38), 180.0
    hum = _w.hum("retardovici")
    pose = _w.sit_pose(hum, 0.46, upper)
    pose = _w.life_pose(pose, int(t), 0.14, 12)

    meta = E.telephone_meta()
    S = E.PHONE_SCALE
    bm, hm = meta["base"], meta["handset"]
    grip_local = (0.0, hm["handle_bounds_yz"][1] + 0.007, 0.0)
    grip_s = (grip_local[0] * S, grip_local[1] * S, grip_local[2] * S)

    # Cradle resting pose on the telephone base.
    cradle_y = (bm["cradle_saddle_y"] - hm["cradle_rest_y"]) * S
    H_cradle = v_add(E.PHONE_POS, m_apply(rot_y(E.PHONE_YAW), (0.0, cradle_y, bm["cradle_z"] * S)))
    R_cradle = rot_y(E.PHONE_YAW + 180.0)
    G_cradle = v_add(H_cradle, m_apply(R_cradle, grip_s))

    # Head-locked ear hold pose (earpiece on right ear, mouthpiece clear of right jaw).
    neck_w, R_head = _head_world(hum, pose, r_pos, r_yaw)
    ear_head = (0.142, 0.155, 0.0)
    mouth_head = (0.118, 0.048, 0.165)
    u_long = _norm3(v_sub(ear_head, mouth_head))
    outward = _norm3((0.97, 0.0, 0.24))
    d_ol = u_long[0] * outward[0] + u_long[1] * outward[1] + u_long[2] * outward[2]
    u_back = _norm3((
        outward[0] - d_ol * u_long[0],
        outward[1] - d_ol * u_long[1],
        outward[2] - d_ol * u_long[2],
    ))
    u_side = _norm3(_cross3(u_long, u_back))
    R_ear_head = (
        u_long[0], u_back[0], u_side[0],
        u_long[1], u_back[1], u_side[1],
        u_long[2], u_back[2], u_side[2],
    )
    R_ear = m_mul(R_head, R_ear_head)
    ear_world = v_add(neck_w, m_apply(R_head, ear_head))
    eg = hm["ear_grill"]
    H_ear = v_sub(ear_world, m_apply(R_ear, (eg[0] * S, eg[1] * S, eg[2] * S)))
    G_ear = v_add(H_ear, m_apply(R_ear, grip_s))

    if t < 440:
        idle = (cx - 0.30, 0.965, cz + 1.04)
        r_target = (
            idle[0] + (G_cradle[0] - idle[0]) * reach_u,
            idle[1] + (G_cradle[1] - idle[1]) * reach_u + 0.055 * math.sin(math.pi * reach_u),
            idle[2] + (G_cradle[2] - idle[2]) * reach_u,
        )
        R_phone, H_pos = R_cradle, H_cradle
    else:
        rot_u = k(t, 670, 670)
        R_phone = _quat_to_mat(_quat_slerp(_mat_to_quat(R_cradle), _mat_to_quat(R_ear), rot_u))
        arc = (
            -0.07 * math.sin(math.pi * lift_u),
            0.07 * (math.sin(math.pi * lift_u) ** 0.7),
            -0.04 * math.sin(math.pi * lift_u),
        )
        r_target = tuple((G_cradle[i] + (G_ear[i] - G_cradle[i]) * lift_u) + arc[i] for i in range(3))
        H_pos = v_sub(r_target, m_apply(R_phone, grip_s))

    # Solve both arms against the already-breathed pose and pass amp=0.0 so joints match exactly.
    pose = solve_arm_safe(hum, pose, r_pos, r_yaw, "l", (cx + 0.28, 0.955, cz + 0.88),
                          poles=((0.7, -0.5, -0.6),) + POLES)
    pole_r = (0.75 + 0.15 * lift_u, -0.45 - 0.55 * lift_u, -0.55 + 0.75 * lift_u)
    pose = solve_arm_safe(hum, pose, r_pos, r_yaw, "r", r_target, poles=(pole_r,) + POLES)

    _, solved_j, _ = hum.pose_world(pose, r_pos, r_yaw, rifle_on=False)
    if t >= 440:
        H_pos = v_add(H_pos, v_sub(solved_j["rhand"], r_target))

    _w.actor(r, "retardovici", pose, r_pos, r_yaw, int(t), seed=12, amp=0.0,
             mouth=_talk(t, 1100, 3450), expression="stern", flags=("bare_sleeve",))

    _place_handset(r, E.telephone_handset_mesh(), S, H_pos, R_phone)
    cc = hm["cord_collar"]
    cj = bm["cord_jack"]
    collar_w = v_add(H_pos, m_apply(R_phone, (cc[0] * S, cc[1] * S, cc[2] * S)))
    jack_w = v_add(E.PHONE_POS, m_apply(rot_y(E.PHONE_YAW), (cj[0] * S, cj[1] * S, cj[2] * S)))
    _phone_cord(r, jack_w, collar_w, desk_y=0.90)

    o_turn = k(t, 400, 700)
    _w.actor(
        r, ("guard", "officer"),
        dict(POSES["stand"], head_y=28 * o_turn, head_p=2, lsh_p=18, lel=34),
        (cx - 1.65, 0.0, cz + 2.15), 165.0, int(t), seed=41, amp=0.08, mouth=0.0,
        flags=("os12",),
    )
    _finish(surface, r, t, 41)


def _flyby_heli_at(u, base_z):
    """Smooth continuous gunship path diving over the tractor without angle snaps."""
    hz = base_z + 115.0 - 148.0 * u
    hx = CS.road_x(hz) + 15.0 * (1.0 - u) - 8.5 * math.sin(math.pi * u)
    hy = 24.0 - 18.0 * math.sin(min(1.0, u * 1.12) * math.pi * 0.5) + 4.5 * max(0.0, u - 0.62) ** 1.3
    return hx, hy, hz


def heli_flyby(surface, t):
    """Shot 3: Rig-locked front camera; the gunship dives smoothly right over the cab."""
    from missions.m8.revenge import chase3d as C
    s = t / 1000.0
    u = max(0.0, min(1.0, t / 3800.0))
    sc, z, pos, yaw, lpos, lyaw = _heli_sc_at(21.0 + 9.0 * s)

    p0 = _flyby_heli_at(max(0.0, u - 0.015), z)
    p1 = _flyby_heli_at(u, z)
    p2 = _flyby_heli_at(min(1.0, u + 0.015), z)
    vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
    hyaw = math.degrees(math.atan2(vx, vz)) % 360.0
    hpitch = math.degrees(math.atan2(vy, math.hypot(vx, vz)))
    hroll = -28.0 * math.sin(u * math.pi)

    flyover = max(0.0, 1.0 - abs(t - 2850.0) / 550.0)
    sh = (math.sin(t * 0.055) * 0.11 * flyover, math.cos(t * 0.048) * 0.11 * flyover)
    # Behind/beside the trailer looking forward so tractor, Biribel, and incoming chopper stay framed.
    eye = C._local(lpos, lyaw, (-3.6 + sh[0], 1.85 + sh[1], -3.6))
    tgt = mix((p1[0] * 0.6 + pos[0] * 0.4, max(3.0, p1[1] * 0.45 + 1.8), pos[2] + 24.0),
              (pos[0], 3.8, pos[2] + 4.0), k(t, 2100, 1400))

    r = _road(eye, tgt, 54.0, t)
    g = _draw_cut_rig(r, sc, pos, yaw, lpos, lyaw, sc.odo + 21.0 + 9.0 * s, int(t))
    CS.put_helicopter(r, p1, hyaw, hpitch, hroll, (t * 1.45) % 360.0, (t * 2.4) % 360.0)
    r.add_blob_shadow((p1[0], CS.surface_y(p1[0], p1[2]) + 0.06, p1[2]),
                      3.8, 5.2, 0.45 / (1.0 + max(0.0, p1[1])))
    _w.actor(r, BODI, dict(C._SEATED, head_p=-16),
             C._local(pos, yaw, (0.0, 0.62, -0.75)), yaw, int(t), seed=61, amp=0.2,
             rifle_on=False, mouth=0.0)
    _biri(r, dict(g["pose"], head_p=-18), g["feet"], sc.yaw, t, gun=False,
          mouth=_talk(t, 300, 1800), expression="angry", amp=0.1)
    _finish(surface, r, t, 42)


def heli_lockon(surface, t):
    """Shot 4: Gunship banks into its pursuit orbit as the camera lands on the LMG."""
    from core.config import draw_vignette
    from missions.m8.revenge import chase3d as C
    s = min(t, 2400.0) / 1000.0
    u = k(t, 0, 2200)
    sc = C._SCENE
    if sc is None or not sc.active():
        sc = C.ChaseScene()
        sc.z = CS.SECTIONS[3]
    saved = (sc.z, sc.odo, sc.yaw, sc.pitch, sc.ads, sc.shake)
    try:
        sc.z = saved[0] + 55.0 - 21.6 + 9.0 * s
        sc.odo = saved[1] + 55.0 - 21.6 + 9.0 * s
        sc.yaw, sc.pitch, sc.ads, sc.shake = 180.0, 6.0, 0.0, 0.0
        pos, yaw = sc.tractor_pos()
        lpos, lyaw = sc.trailer_pos()
        end_eye, end_tgt, end_fov = sc.camera()
        start_eye = C._local(lpos, lyaw, (4.4, 2.2, -3.2))
        hx = CS.road_x(sc.z) + 19.0 - 8.0 * u
        hy = 10.0 - 3.0 * u
        hz = lpos[2] - 20.0 - 11.0 * u
        hyaw = math.degrees(math.atan2(lpos[0] - hx, lpos[2] - hz)) % 360.0
        start_tgt = (hx, hy, hz)

        eye = mix(start_eye, end_eye, u)
        tgt = mix(start_tgt, end_tgt, u)
        fov = 50.0 + (end_fov - 50.0) * u

        r = CS.frame(eye, tgt, fov, int(t))
        del _w.LAST[:]
        sc._draw_vehicles(r, int(t))
        CS.put_helicopter(r, (hx, hy, hz), hyaw, -6.0, 22.0 * (1.0 - u),
                          (t * 1.45) % 360.0, (t * 2.4) % 360.0)
        r.add_blob_shadow((hx, CS.surface_y(hx, hz) + 0.06, hz),
                          3.8, 5.2, 0.45 / (1.0 + max(0.0, hy)))
        info = CS.helicopter_parts()[3]
        pilot = CS._xf(info["pilot_seat"], (hx, hy, hz), hyaw, -6.0, 22.0 * (1.0 - u))
        seat = CS._xf(info["gunner_seat"], (hx, hy, hz), hyaw, -6.0, 22.0 * (1.0 - u))
        _w.actor(r, ("guard", "rifle"), dict(C._SEATED), pilot, hyaw, int(t), seed=150, amp=0.0,
                 rifle_on=False, flags=("os12",))
        _w.actor(r, ("guard", "heavy"), blend(POSES["stand"], "aim", 0.9), seat,
                 (hyaw - 55.0) % 360.0, int(t), seed=151, amp=0.15, rifle_on=True,
                 flags=("os12",))
        sc._draw_people(r, int(t))
        sc._draw_smoke(r, int(t))
        CS.present(r, surface)
        draw_vignette(surface)
    finally:
        sc.z, sc.odo, sc.yaw, sc.pitch, sc.ads, sc.shake = saved


# --- overlays -------------------------------------------------------------------


def _tv(surface, t, strap):
    band = surface.subsurface((0, _w.SAFE_TOP, WIDTH, _w.FILM_H))
    h = band.get_height()
    lines = _cache_lines(h)
    band.blit(lines, (0, 0))
    bug = font_terminal_small.render("TVR 1   LIVE", True, (236, 230, 210))
    pygame.draw.rect(band, (150, 30, 30), (28, 22, bug.get_width() + 16, 24))
    band.blit(bug, (36, 26))
    a = k(t, 700, 500)
    if a > 0.0:
        y = h - 70
        w = int((WIDTH - 120) * a)
        pygame.draw.rect(band, (18, 30, 78), (60, y, w, 30))
        pygame.draw.rect(band, (196, 160, 60), (60, y, 6, 30))
        txt = font_terminal_small.render(strap, True, (236, 232, 220))
        if w > txt.get_width() + 30:
            band.blit(txt, (80, y + 6))


_LINES = {}


def _cache_lines(h):
    s = _LINES.get(h)
    if s is None:
        s = _LINES[h] = pygame.Surface((WIDTH, h), pygame.SRCALPHA)
        for y in range(0, h, 4):
            pygame.draw.line(s, (0, 0, 0, 26), (0, y), (WIDTH, y))
    return s


def _static(surface, t):
    band = surface.subsurface((0, _w.SAFE_TOP, WIDTH, _w.FILM_H))
    n = int(t / 33.0)
    for i in range(10):
        y = (n * 53 + i * 131) % band.get_height()
        a = 26 + (n * 17 + i * 29) % 46
        s = pygame.Surface((WIDTH, 1 + (i % 2)), pygame.SRCALPHA)
        s.fill((210, 210, 210, a))
        band.blit(s, (0, y))
