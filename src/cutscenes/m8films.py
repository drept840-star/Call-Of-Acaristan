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
from engine3d import POSES, blend, box
from engine3d.core import m_apply, rot_y
from engine3d.hold import hold_cached as _hold_cached
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
    hum = _w.hum(BODI)
    return R._held(hum, pose, R._ally_gun(BODI), "ready", BODI)


def _biri(r, pose, pos, yaw, t, gun=True, **kw):
    kw.setdefault("expression", "neutral")
    return _w.actor(r, BIRI, pose, pos, yaw, t, seed=93, amp=kw.pop("amp", 0.25),
                    rifle_on=gun, flags=("shotgun",) if gun else (), **kw)


def _bodi(r, pose, pos, yaw, t, **kw):
    kw.setdefault("expression", "neutral")
    return _w.actor(r, BODI, pose, pos, yaw, t, seed=61, amp=kw.pop("amp", 0.3),
                    rifle_on=True, **kw)


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
    eye = (TX + 1.6, 0.85 + 0.25 * u, z0 + 5.2 + 1.2 * u)
    tgt = (TX + 1.4, 1.35, z0)
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

LX, LZ = S3.LADDER_X, S3.LADDER_Z - 0.38        # on the rungs (trap3d's climb mark)
TRAC_AT = (11.2, 0.0, 52.2)                     # the tractor at the ladder foot, facing the road


def _rung_pose(y, over=0.0):
    """trap3d's climb pose (hand over hand, one rung per step); ``over`` eases
    it to standing for the step over the deck lip."""
    sw = math.sin(y / 0.64 * 2.0 * math.pi)
    up = dict(POSES["stand"], spine=6, head_p=-18,
              lsh_p=158 + 14 * sw, lsh_r=10, lel=36 - 22 * sw,
              rsh_p=158 - 14 * sw, rsh_r=10, rel=36 + 22 * sw,
              lhip_p=44 + 30 * sw, lkn=70 + 40 * sw, rhip_p=44 - 30 * sw, rkn=70 - 40 * sw,
              lank=-10, rank=-10)
    if over <= 0.0:
        return up
    step = math.sin(over * math.pi)
    return blend(dict(up, lhip_p=up["lhip_p"] + 30 * step, lkn=up["lkn"] + 20 * step),
                 POSES["stand"], over)


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
            amp=0.0, mouth=0.0, expression="neutral", bloody=True, rifle_on=False)


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
    u = k(t, 0, 5200)
    eye = mix((14.2, 1.1, 45.2), (13.0, 1.3, 46.6), u)
    down = k(t, 900, 3900)
    y = S3.CATWALK_Y * (1.0 - down)
    tgt = mix((LX, CY + 0.6, LZ), (LX, max(1.2, y + 0.6), LZ), k(t, 600, 4200))
    r = _plaza(eye, tgt, 50.0, t)
    _body(r, t)
    if t < 900:          # back over the lip, onto the top rung
        over = 1.0 - k(t, 0, 900)
        z = LZ + (CZ - 0.15 - LZ) * over
        _biri(r, _rung_pose(CY, over), (LX, CY, z), 0.0, t, gun=False, mouth=0.0, amp=0.0)
    elif t < 4800:
        _biri(r, _rung_pose(y), (LX, y, LZ), 0.0, t, gun=False, mouth=0.0, amp=0.0)
    else:                # off the bottom rung, turning for the tractor
        off = k(t, 4800, 400)
        _biri(r, blend(_rung_pose(0.0), POSES["stand"], off), (LX, 0.0, LZ - 0.3 * off),
              90.0 * off, t, gun=False, mouth=0.0, amp=0.0)
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
    CS.put(r, "tractor", CS.tractor, (RX, 0.0, XZ - 0.3), CS.road_yaw(XZ))
    CS.put(r, "barrier_arm", CS.barrier_arm, (RX - 3.0, 0.05, CS.BARRIER_Z + 3.0), 210.0)
    if bodi:
        _w.actor(r, BODI, dict(E._SEATED, spine=22, head_p=30), (RX, 0.62, XZ - 1.05),
                 CS.road_yaw(XZ), int(t), seed=61, amp=0.0, mouth=0.0)


def epi_radio(surface, t):
    """The last car's rear step, under way: Alex on the radio."""
    x = E.train_x(t / 1000.0)
    sway = math.sin(t * 0.0021) * 0.05
    eye = (x - 5.0 + 0.6 * k(t, 0, 5000), 2.55 + sway, XZ - 2.3)
    r = _road(eye, (x - 0.3, 2.45, XZ), 42.0, t)
    _crossing_cast(r, t, x, bodi=False)
    radio = dict(POSES["radio"], head_p=10, spine=8)
    _biri(r, radio, (x - 0.3, 1.26, XZ), 270.0, t, gun=False, mouth=0.0, amp=0.2)
    _finish(surface, r, t, 20, tint=(214, 206, 226))
    _static(surface, t)


def _studio_lights():
    return [{"pos": (SX - 2.4, 4.0, SZ - 2.0), "color": (255, 240, 220), "intensity": 1.1, "range": 9.0},
            {"pos": (SX + 2.4, 4.0, SZ - 2.0), "color": (220, 230, 255), "intensity": 0.9, "range": 9.0}]


def epi_president(surface, t):
    """State TV: the President at the desk, a slow push on the broadcast."""
    d = k(t, 0, 5000)
    eye = (SX + 0.15 * d, 1.8, SZ - 5.6 + 0.8 * d)
    r = _road(eye, (SX, 1.62, SZ + 1.4), 34.0, t, lights=_studio_lights())
    CS.put(r, "studio", E.studio, (0.0, 0.0, 0.0))
    beat = k(t, 1600, 500) * (1.0 - k(t, 2800, 600))
    pose = dict(POSES["stand"], lsh_p=30 + 10 * beat, lel=36 + 14 * beat, rsh_p=30, rel=36,
                head_p=-2)
    _w.actor(r, "president", pose, (SX, 0.0, SZ + 1.4), 180.0, int(t), seed=12, amp=0.25,
             mouth=_talk(t, 200, 3400), expression="stern")
    _finish(surface, r, t, 21, tint=(222, 228, 240))
    _tv(surface, t, "STATE ADDRESS")


def epi_estate(surface, t):
    """Night.  The estate, lit and empty; a closed funeral in the grounds."""
    u = k(t, 0, 6000)
    eye = mix((FX + 4.0, 7.5, FZ - 30.0), (FX + 1.4, 3.0, FZ - 14.0), u)
    tgt = mix((FX, 5.0, FZ + 16.0), (FX, 1.6, FZ + 2.0), u)
    r = _road(eye, tgt, 50.0, t, look="night", lights=E.estate_lights())
    _funeral_cast(r, t)
    _finish(surface, r, t, 22)


def _funeral_cast(r, t):
    CS.put(r, "funeral", E.funeral, (0.0, 0.0, 0.0))
    _w.actor(r, "maru", E.LYING, (FX - 0.04, 1.17, FZ), 90.0, int(t), seed=5, amp=0.0, mouth=0.0)
    for i, (dx, dz, yaw) in enumerate(E.HONOUR):
        pose = _hold_cached(_w.hum(("guard", "officer")), dict(POSES["stand"], head_p=4),
                            "rifle", "port", key="guard_honour")
        _w.actor(r, ("guard", "officer"), pose, (FX + dx, 0.30, FZ + dz), yaw,
                 int(t), seed=40 + i, amp=0.06, mouth=0.0, rifle_on=True)
    E.lamp_glows(r, t)


def epi_casket(surface, t):
    """Maru in the open casket, the guard of honour still."""
    d = k(t, 0, 5200)
    eye = (FX - 1.6 + 0.6 * d, 2.5 - 0.2 * d, FZ - 4.4 + 0.6 * d)
    r = _road(eye, (FX + 0.1, 1.35, FZ + 0.3), 44.0, t, look="night", lights=E.estate_lights())
    _funeral_cast(r, t)
    _finish(surface, r, t, 23)


def epi_commander(surface, t):
    """State TV again: the new Commander of the Presidential Guard."""
    d = k(t, 0, 5000)
    eye = (SX + 0.60 - 0.15 * d, 1.76, SZ - 5.4 + 0.6 * d)
    r = _road(eye, (SX + 0.60, 1.42, SZ + 1.45), 38.0, t, lights=_studio_lights())
    CS.put(r, "studio", E.studio, (0.0, 0.0, 0.0))

    p_pos, p_yaw = (SX + 0.22, 0.0, SZ + 1.48), 110.0
    u_pos, u_yaw = (SX + 0.98, 0.0, SZ + 1.48), 250.0
    p_base = dict(POSES["stand"], head_p=-2, head_y=-10)
    u_base = dict(POSES["stand"], head_p=-2, head_y=10)

    shake = k(t, 1200, 700) * (1.0 - k(t, 3900, 800))
    pump = math.sin((t - 1900) * 0.011) * 0.025 * k(t, 1900, 250) * (1.0 - k(t, 3400, 450))
    clasp = (SX + 0.54, 1.15 + pump, SZ + 1.42)

    if shake > 0.0:
        p_clasp = _w.reach(_w.hum("president"), p_base, "r", clasp, p_pos, p_yaw)
        u_clasp = _w.reach(_w.hum("ucilev"), u_base, "r", clasp, u_pos, u_yaw)
        p_pose = blend(p_base, p_clasp, shake)
        u_pose = blend(u_base, u_clasp, shake)
    else:
        p_pose, u_pose = p_base, u_base

    _w.actor(r, "president", p_pose, p_pos, p_yaw, int(t), seed=12, amp=0.10,
             mouth=0.0, expression="stern")
    _w.actor(r, "ucilev", u_pose, u_pos, u_yaw, int(t), seed=34, amp=0.08,
             mouth=0.0)
    _finish(surface, r, t, 24, tint=(222, 228, 240))
    _tv(surface, t, "NEW COMMANDER")


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
    tx = E.train_x(t / 1000.0, 12.0, 4.0)
    up = k(t, 600, 1200)
    u = k(t, 0, 6000)
    ux, uz = RX - 5.6, XZ - 11.0
    yaw = _yaw((ux, 0, uz), (tx, 0, XZ))
    fx, fz = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    back = 2.6 - 0.5 * u                              # over his right shoulder, easing in
    eye = (ux - fx * back - fz * 0.42, 1.86, uz - fz * back + fx * 0.42)
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
        for y in range(0, h, 3):
            pygame.draw.line(s, (0, 0, 0, 60), (0, y), (WIDTH, y))
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
