"""New staged scenes for the dark trailer, built on the Mission 7 farm set.

Each takes ``(surface, t_ms)`` like the game's films (cutscenes/m7films.py) and
uses the same stage, cast and fire kit, but none of them is in the game or an
earlier trailer.  Looks: "night" (before dawn), "dawn", "raid", "burn".
"""
import math

from core.outfits import OUTFIT_GUARD
from engine3d.core import Mesh, box
from engine3d.hold import hold_cached
from engine3d.rig import POSES, blend, pose_run
from cutscenes import m6fx3d as fx
from cutscenes import m6world3d as W
from cutscenes import m7world3d as F

BIRI = ("biribel", OUTFIT_GUARD)
BODI = ("ally", "bodi")             # the ally rig carries his M7 rifle
ALEX = ("ally", "alex")
GUARD = ("guard", "rifle")
SUN = (96.0, 9.0, 40.0)
ORCH = (34.0, 0.0, 2.0)
SG = ("shotgun",)
k, mix, face = F.k, F.mix, W.yaw_to
# gunfire (ms into each scene), read by the trailer's score
SHOTS = {"cover_fire": (900, 1900, 2800), "guard_aim": (1300, 1500, 1700),
         "bodi_aim": (700, 1900), "alex_fire": (900, 1100, 1300, 1550),
         "biribel_run": (400, 1300, 2100)}
HITS = {"alex_pinned": (300, 900, 1250, 2100), "guard_down": (350,)}


def pose(**kw):
    return F.stand_pose(**kw)


def held(key, base, mode, hd=False, flags=()):
    """``base`` with the arms solved on the rig that is drawn (hd and flags must match the
    actor call: Biribel's HD rig drops the shotgun, so he stays non-HD when armed)."""
    h = W.hum(key, hd, flags=flags)
    aim = None
    if mode == "aim" and isinstance(key, tuple) and key[0] == "ally":
        base = dict(base, twist=30.0, head_y=-24.0)     # allies blade the torso to shoulder it
        aim = (0.0, 1.45, 10.0)
    return hold_cached(h, base, getattr(h, "_weapon", "rifle"), mode, aim=aim,
                       key=("dark", key, hd, flags))


def ahead(a, b, d, y):
    dx, dz = b[0] - a[0], b[2] - a[2]
    n = math.hypot(dx, dz) or 1.0
    return (a[0] + dx / n * d, y, a[2] + dz / n * d)


def muzzle(r, t, at, shots, seed=0, col=(255, 214, 150)):
    """Flash sprites at ``at`` for each shot time in ``shots``; returns the light it throws."""
    lights = []
    for i, s in enumerate(shots):
        age = t - s
        if 0 <= age < 140:
            r.add_sprite(at, fx.flash(age, col, radius_m=0.9, dur_ms=140), layer=fx.FX_LAYER)
            lights.append({"pos": at, "color": col, "intensity": 0.9 * (1 - age / 140.0),
                           "range": 5.0})
    return lights


def molotov(r, t, at):
    """A bottle held by the neck at ``at``, the rag in it alight; returns its light."""
    x, y, z = at
    m = Mesh()
    m.add(box(0.09, 0.2, 0.09, (66, 92, 58), center=(x, y - 0.06, z)))
    m.add(box(0.04, 0.08, 0.04, (80, 108, 70), center=(x, y + 0.08, z)))
    m.add(box(0.05, 0.05, 0.05, (190, 176, 150), center=(x, y + 0.14, z)))
    W.add(r, m)
    F.fire(r, (x, y + 0.17, z), t, seed=33, size=0.13, smoky=False)
    return {"pos": (x, y + 0.2, z), "color": (255, 150, 70), "intensity": 0.8, "range": 4.0}


def lamp(r, t, at, seed, col=(214, 226, 255)):
    """A Guard flashlight: a cold hot-spot and a short halo."""
    r.add_sprite(at, fx.glow(col, 0.5, t, flicker=0.05, seed=seed, core=(250, 252, 255),
                             intensity=0.9, max_px=40), layer=fx.FX_LAYER)


def guard(r, t, pos, look, seed, walk=0.0, gun="ready", base=None, expression="stern", lit=True):
    """An HD Guard with his rifle; ``lit`` mounts a flashlight on the barrel so the black
    rifle reads against the black uniform.  Returns the muzzle point (or None)."""
    p = base or (F.walk_pose(t + seed * 97, walk) if walk else pose(spine=6))
    p = held(GUARD, p, gun, hd=True)
    j = W.actor(r, GUARD, p, pos, face(pos, look), t, seed=seed, amp=0.25, rifle_on=True, hd=True,
                mouth=0.0, expression=expression)
    m = j.get("muzzle") if j else None
    if m is not None and lit:
        lamp(r, t, m, seed)
        mid = ((m[0] + pos[0]) * 0.5, m[1] + 0.25, (m[2] + pos[2]) * 0.5)
        r.set_lights(list(r.lights) + [{"pos": mid, "color": (200, 214, 240), "intensity": 0.7,
                                        "range": 1.6}])
    return m


def done(surface, r, buf, seed, t):
    F.finish(surface, r, buf, seed, "", t)


# --- before dawn ---------------------------------------------------------------------
def cold_farm(surface, t):
    """Before dawn: the farm in the dark, one window lit, a slow push up the track."""
    u = k(t, 0, 6500)
    eye = mix((1.5, 1.4, -44.0), (0.8, 1.7, -30.0), u)
    r, buf = F.stage("night", t, eye, (-8.0, 2.4, 10.0), 34, hh=0.004, seed=3)
    F.mist(r, t, seed=3, n=12, intensity=0.07)
    r.add_sprite((-10.0, 2.2, 7.9), fx.window_glow((255, 178, 96), 0.9, 1.0, 0.7, t, 0.08, 3),
                 layer=fx.FX_LAYER)
    done(surface, r, buf, 3, t)


# --- dawn ---------------------------------------------------------------------------
def heli_leave(surface, t):
    """Maru's helicopter climbs away into the dawn; Biribel alone in the stubble, backlit."""
    eye = mix((-33.0, 0.5, -4.0), (-33.4, 0.55, -3.2), k(t, 0, 3200))
    r, buf = F.stage("dawn", t, eye, (-44.0, 9.0, 26.0), 52, hh=0.006, seed=5)
    F.mist(r, t, seed=5, n=14, intensity=0.12)
    F.sun(r, t, (-58.0, 8.0, 60.0))
    go = k(t, 0, 3400)
    hp = (-46.0 - 18.0 * go, 9.0 + 14.0 * go, 30.0 + 26.0 * go)
    W.helicopter(r, t, hp, yaw=face((-46.0, 0, 30.0), (-70.0, 0, 60.0)), rotor_speed=0.95,
                 pitch=9.0, bank=-6.0, blur=0.8, pilot=False)
    me = (-36.2, 0.0, 4.0)
    W.actor(r, BIRI, pose(spine=4, head_p=-8 + 4 * go, lsh_p=6, rsh_p=6), me, face(me, hp), t,
            seed=52, amp=0.3, expression="neutral")
    done(surface, r, buf, 5, t)


def well(surface, t):
    """Chores: Biribel carries two full buckets from the well, tracked side-on."""
    z = 5.2 - 1.1 * t / 1000.0
    me = (2.5, 0.0, z)                              # just east of the well, walking south
    eye = (6.6, 1.4, -1.6 - 0.3 * t / 1000.0)       # sun at our back, the well beside him
    r, buf = F.stage("dawn", t, eye, (2.0, 1.0, z), 36, hh=0.004, seed=7)
    F.mist(r, t, seed=7, n=8, intensity=0.08)
    F.sun(r, t, SUN)
    p = dict(F.walk_pose(t, 0.45), lsh_p=4.0, rsh_p=4.0, lel=4.0, rel=4.0, spine=8.0)
    j = W.actor(r, BIRI, p, me, face(me, (2.5, 0.0, z - 5.0)), t, seed=52, amp=0.2,
                expression="neutral")
    m = Mesh()
    for hand in ("lhand", "rhand"):
        hx, hy, hz = j[hand]
        m.add(box(0.012, 0.16, 0.012, (60, 60, 62), center=(hx, hy - 0.06, hz)))     # handle
        m.add(box(0.26, 0.28, 0.26, (128, 132, 136), center=(hx, hy - 0.28, hz)))
        m.add(box(0.22, 0.01, 0.22, (52, 74, 86), center=(hx, hy - 0.135, hz)))      # water
    W.add(r, m)
    done(surface, r, buf, 7, t)


def valley(surface, t):
    """Biribel and Bodi at the yard gate, backs to us, looking down the empty valley."""
    eye = mix((0.6, 1.55, -10.0), (0.4, 1.6, -11.4), k(t, 0, 3600))
    r, buf = F.stage("dawn", t, eye, (0.0, 0.6, -70.0), 44, hh=0.004, seed=9)
    F.mist(r, t, seed=9, n=14, intensity=0.12)
    F.sun(r, t, SUN)
    me, bodi = (-0.9, 0.0, -14.6), (1.1, 0.0, -14.9)
    W.actor(r, BIRI, pose(spine=3, head_p=4), me, face(me, (-2.0, 0, -60.0)), t, seed=52,
            amp=0.3)
    W.actor(r, BODI, pose(spine=5, head_p=6, rsh_p=10), bodi, face(bodi, (4.0, 0, -60.0)), t,
            seed=61, amp=0.3)
    done(surface, r, buf, 9, t)


def bodi_look(surface, t):
    """Close on Bodi at the fence: he looks at the newcomer and says nothing."""
    me, bodi = (-26.9, 0.0, 9.7), (-24.6, 0.0, 10.0)
    eye = mix((-27.9, 1.7, 9.0), (-27.7, 1.68, 9.15), k(t, 0, 3000))
    r, buf = F.stage("dawn", t, eye, (-24.6, 1.5, 10.1), 26, hh=0.003, seed=13)
    F.mist(r, t, seed=13, n=6, intensity=0.06)
    F.sun(r, t, SUN)
    turn = k(t, 600, 900)
    W.actor(r, BIRI, pose(spine=4), me, face(me, bodi), t, seed=52, amp=0.25)
    look = mix((-22.0, 0, 0.0), me, turn)
    W.actor(r, BODI, pose(spine=5, head_p=2, rsh_p=14), bodi, face(bodi, look), t, seed=61,
            amp=0.25, hd=True, expression="stern")
    done(surface, r, buf, 13, t)


def porch(surface, t):
    """The quiet: Biribel on a crate by the house, elbows on his knees, the valley going blue."""
    me = (-13.6, 0.0, 5.6)
    eye = mix((-12.6, 1.0, 2.4), (-12.9, 0.98, 3.0), k(t, 0, 5500))
    r, buf = F.stage("night", t, eye, (-13.6, 0.95, 5.6), 40, hh=0.003, seed=15)
    seat = 0.46
    b = Mesh()
    b.add(box(0.6, seat, 0.5, F.WOOD_D, center=(me[0], seat / 2, me[2] + 0.18)))
    W.add(r, b)
    up = pose(spine=30, head_p=14 - 8 * k(t, 1500, 2000), lsh_p=52, lel=96, rsh_p=50, rel=100)
    W.actor(r, BIRI, W.sit_pose(W.hum(BIRI), seat, up), me, face(me, (-12.2, 0.0, 1.0)), t,
            seed=52, amp=0.15, hd=True, expression="sad")
    lit = {"pos": (-12.4, 1.8, 4.2), "color": (255, 170, 100), "intensity": 0.9, "range": 5.0}
    r.set_lights([lit])
    r.add_sprite((-10.0, 2.63, 6.6), fx.glow((255, 170, 100), 0.4, t, flicker=0.06, seed=15,
                                             core=(255, 220, 170), max_px=30), layer=fx.FX_LAYER)
    done(surface, r, buf, 15, t)


# --- the raid -----------------------------------------------------------------------
def torchline(surface, t):
    """The sweep line comes through the orchard: flashlights, a dog, helmets in the fog."""
    eye = mix((21.5, 0.45, 1.0), (21.9, 0.5, 1.2), k(t, 0, 3000))
    r, buf = F.stage("raid", t, eye, (34.0, 1.3, 2.0), 44, hh=0.005, seed=21)
    from missions.m7 import raid_world as RW
    du = k(t, 0, 3400)
    d = mix((34.0, 0.0, 3.0), (27.5, 0.0, 1.8), du)
    RW.put(r, RW.dog("Run", du * 6.5 / RW.DOG_RUN_M * RW.dog_clip_s("Run")), d[0], 0.0, d[2],
           face(d, eye))
    for i, (x, z) in enumerate(((38.5, -3.5), (37.0, 1.0), (39.0, 5.5), (41.5, 9.0))):
        g = (x - 3.0 * k(t, i * 200, 3400), 0.0, z * 0.9)
        guard(r, t, g, (20.0, 0.0, 1.0), 70 + i, walk=0.7)
    done(surface, r, buf, 21, t)


def headlights(surface, t):
    """A Guard truck grinds up the track into the camera, lights full in our eyes."""
    from missions.m7 import raid_world as RW
    z = -42.0 + 16.0 * k(t, 0, 3600)
    eye = mix((-1.4, 0.35, -16.0), (-1.3, 0.4, -16.6), k(t, 0, 3600))
    r, buf = F.stage("raid", t, eye, (0.0, 1.4, z), 40, hh=0.007, seed=25)
    RW.put(r, RW.truck(), 0.0, 0.0, z, 0.0)
    for sx in (-0.68, 0.68):
        r.add_sprite((sx, 1.46, z + 2.95), fx.glow((255, 240, 210), 1.3, t, core=(255, 252, 240),
                                                   intensity=1.0, max_px=120), layer=fx.FX_LAYER)
    for i, dx in enumerate((-2.0, 2.1)):
        g = (dx, 0.0, z + 1.0 + 0.6 * i)
        guard(r, t, g, (dx, 0.0, z + 20.0), 80 + i, walk=0.55)
    done(surface, r, buf, 25, t)


def cover_fire(surface, t):
    """Behind the tractor Biribel rises and fires the shotgun into the dark."""
    me = (-15.4, 0.0, -0.8)
    tgt = (6.0, 1.2, -12.0)
    eye = mix((-12.2, 1.15, -3.6), (-12.5, 1.2, -3.3), k(t, 0, 3000))
    rise = k(t, 300, 400)
    shots = SHOTS["cover_fire"]
    m = ahead(me, tgt, 1.05, 1.42)
    r, buf = F.stage("raid", t, eye, (-15.6, 1.15, -0.6), 40, hh=0.006, seed=27)
    lights = muzzle(r, t, m, shots)
    r.set_lights(lights)
    base = pose(spine=34 - 26 * rise, head_p=-10 + 14 * rise, lhip_p=96 * (1 - rise),
                lkn=128 * (1 - rise), rhip_p=84 * (1 - rise), rkn=132 * (1 - rise))
    kick_ = max(0.0, 1.0 - min(abs(t - s) for s in shots) / 160.0)
    base["spine"] = base["spine"] - 6 * kick_
    p = held(BIRI, base, "aim" if rise > 0.5 else "ready", flags=SG)
    W.actor(r, BIRI, p, (me[0], -0.55 * (1 - rise), me[2]), face(me, tgt), t, seed=52, amp=0.15,
            rifle_on=True, flags=SG, expression="angry")
    done(surface, r, buf, 27, t)


def guard_aim(surface, t):
    """A Guard rifleman steps out of the fog, levels the rifle at us and fires."""
    g = (24.0, 0.0, 1.2)
    target = (19.4, 1.4, 3.4)                       # off to our left: the rifle in profile
    eye = mix((20.9, 1.5, -2.2), (21.2, 1.5, -1.9), k(t, 0, 2400))
    step = k(t, 0, 700)
    pos = mix((25.0, 0.0, 1.6), g, step)
    r, buf = F.stage("raid", t, eye, (pos[0] - 0.7, 1.4, pos[2] + 0.2), 32, hh=0.006, seed=29)
    m = guard(r, t, pos, target, 90, gun="aim" if step > 0.5 else "ready", expression="angry")
    if m is not None:
        r.set_lights(list(r.lights) + muzzle(r, t, m, SHOTS["guard_aim"]))
    done(surface, r, buf, 29, t)


def alex_pinned(surface, t):
    """Alex pinned behind the hay bales, rounds kicking straw over him."""
    me = (7.7, 0.0, 2.6)
    eye = mix((10.4, 1.0, -1.4), (10.1, 0.95, -1.1), k(t, 0, 3000))
    r, buf = F.stage("raid", t, eye, (7.6, 0.6, 2.6), 32, hh=0.006, seed=31)
    hits = HITS["alex_pinned"]
    for i, s in enumerate(hits):
        age = t - s
        if 0 <= age < 600:
            r.add_sprite((6.9 + 0.5 * (i % 3), 1.1, 3.4 + 0.2 * i),
                         fx.powder(age, seed=i, spread_m=0.8, intensity=0.8 * (1 - age / 600.0),
                                   col=(196, 170, 104), puffs=8), layer=fx.FX_LAYER)
    flinch = max(0.0, 1.0 - min(abs(t - s - 60) for s in hits) / 260.0)
    p = held(ALEX, pose(**dict(F.POSES["cover_tight"], head_p=22 + 18 * flinch)), "ready", hd=True)
    W.actor(r, ALEX, p, (me[0], -0.1, me[2]), face(me, (1.0, 0.0, -2.0)), t, seed=62, amp=0.4,
            rifle_on=True, hd=True, expression="worried")
    done(surface, r, buf, 31, t)


# --- the burning --------------------------------------------------------------------
HOUSE_FIRES = ((-11.0, 0.35, 6.7, 1.0), (-12.4, 0.5, 6.85, 0.8), (-10.1, 1.1, 6.75, 0.7),
               (-13.3, 3.05, 7.0, 0.75), (-10.6, 3.05, 7.1, 0.9), (-12.0, 4.6, 9.4, 1.2))


def torch_house(surface, t):
    """A Guard walks to the porch with a burning rag and throws it; the porch goes up."""
    throw = 1500
    g = mix((-7.6, 0.0, 2.2), (-9.6, 0.0, 4.4), k(t, 0, 1300))
    eye = mix((-12.6, 0.9, 0.6), (-12.9, 1.0, 1.2), k(t, 0, 3600))      # side on, torch in view
    r, buf = F.stage("raid", t, eye, (-9.8, 1.3, 5.4), 46, hh=0.005, seed=33)
    lights = []
    if throw <= t < throw + 450:                    # the bottle in the air
        u = (t - throw) / 450.0
        a0, a1 = ahead(g, (-11.5, 0.0, 6.8), 0.5, 1.8), (-11.0, 0.35, 6.7)
        at = (mix(a0, a1, u)[0], mix(a0, a1, u)[1] + 1.2 * math.sin(math.pi * u), mix(a0, a1, u)[2])
        lights.append(molotov(r, t, at))
    catch = t - throw - 450
    if catch >= 0:
        r.add_sprite((-11.0, 0.6, 6.6), fx.flash(catch, (255, 170, 80), radius_m=2.6, dur_ms=380),
                     layer=fx.FX_LAYER)
        for i, (x, y, z, size) in enumerate(HOUSE_FIRES):
            grow = k(catch, i * 260, 900)
            if grow > 0.02:
                F.fire(r, (x, y, z), t, seed=91 + i * 11, size=size * grow, smoky=i in (0, 3, 5))
        heat = k(catch, 0, 1200)
        lights.append({"pos": (-11.0, 1.4, 5.8), "color": (255, 140, 60), "intensity": 0.4 + 1.1 * heat,
                       "range": 4.0 + 8.0 * heat})
    arm = k(t, 1100, 400) - k(t, throw, 200)       # wind up, then the throw follows through
    base = F.walk_pose(t, 0.7) if t < 1300 else pose(spine=6 + 14 * k(t, throw, 200))
    base.update(rsh_p=40 + 120 * arm - 30 * k(t, throw, 200), rel=20 + 40 * arm, lsh_p=20)
    back = k(t, throw + 700, 900)
    pos = (g[0] + 1.4 * back, 0.0, g[2] - 1.6 * back)
    j = W.actor(r, GUARD, base, pos, face(pos, (-11.5, 0.0, 6.8)), t, seed=95, amp=0.2,
                rifle_on=False, hd=True, mouth=0.0)
    if t < throw and j:
        lights.append(molotov(r, t, j["rhand"]))
    r.set_lights(lights)
    done(surface, r, buf, 33, t)


def fire_walk(surface, t):
    """Guards walk away from the burning barn, shapes against the fire."""
    eye = mix((11.0, 1.2, -15.0), (11.6, 1.2, -14.0), k(t, 0, 3600))
    r, buf = F.stage("burn", t, eye, (13.0, 2.6, 8.0), 50, lights=F.burn_lights(t), hh=0.005,
                     seed=35)
    F.burn_fx(r, t, 0.8)
    fall = k(t, 1500, 650)
    F.burn_roof(r, fall)
    if t > 1500:
        r.add_sprite((13.5, 6.4, 11.0), F.sparks(t, 1500, seed=5), layer=fx.FX_LAYER)
    for i, (x, z) in enumerate(((10.4, 1.0), (14.5, 2.2), (17.2, 0.4))):
        g = (x + 0.3 * i, 0.0, z - 3.0 - 3.2 * k(t, i * 150, 3600))
        guard(r, t, g, (x, 0.0, -20.0), 100 + i, walk=0.6, expression="neutral")
    done(surface, r, buf, 35, t)


def biribel_fire(surface, t):
    """Biribel in front of the burning house, the fire on his face, slow push in."""
    me = (-12.0, 0.0, -2.0)
    eye = mix((-9.0, 1.6, -5.6), (-9.6, 1.6, -4.8), k(t, 0, 4000))
    r, buf = F.stage("burn", t, eye, (-12.0, 1.62, -2.0), 26,
                     lights=F.burn_lights(t, 0.4) +
                     [{"pos": (-12.0, 2.5, 0.5), "color": (255, 140, 70), "intensity": 1.1,
                       "range": 6.0}], hh=0.003, seed=37)
    F.burn_fx(r, t, 1.0)
    turn = k(t, 900, 1300)
    look = mix((-12.0, 0.0, 10.0), (eye[0], 0.0, eye[2]), turn)
    W.actor(r, BIRI, pose(spine=3, head_p=-2 * turn), me, face(me, look), t, seed=52, amp=0.2,
            hd=True, expression="angry")
    done(surface, r, buf, 37, t)


def bodi_rifle(surface, t):
    """Bodi walks out of the smoke toward us with the rifle, the farm burning behind him."""
    eye = mix((1.0, 1.5, -12.0), (1.0, 1.5, -12.6), k(t, 0, 3200))
    z = -4.5 - 3.0 * k(t, 0, 3200)
    me = (1.4, 0.0, z)
    r, buf = F.stage("burn", t, eye, (1.3, 1.4, z), 24,
                     lights=F.burn_lights(t, 0.3) +
                     [{"pos": (1.0, 2.8, z + 2.0), "color": (255, 150, 80), "intensity": 1.0,
                       "range": 6.0}], hh=0.004, seed=39)
    F.burn_fx(r, t, 1.0)
    F.burn_roof(r, 1.0)
    p = held(BODI, F.walk_pose(t, 0.7), "ready", hd=True)
    W.actor(r, BODI, p, me, face(me, (eye[0], 0.0, eye[2])), t, seed=61, amp=0.2, rifle_on=True,
            hd=True, expression="stern")
    done(surface, r, buf, 39, t)


# --- more dawn ----------------------------------------------------------------------
def field_wide(surface, t):
    """A small figure crossing the furrows under a huge pale sky; the camera rises."""
    u = k(t, 0, 3400)
    eye = mix((-62.0, 0.9, -10.0), (-62.0, 3.4, -10.5), u)
    r, buf = F.stage("dawn", t, eye, (-40.0, 2.4, 14.0), 52, hh=0.004, seed=41)
    F.mist(r, t, seed=41, n=16, intensity=0.13)
    F.sun(r, t, SUN)
    me = (-46.0 + 2.6 * u, 0.0, 12.0)
    W.actor(r, BIRI, F.walk_pose(t, 0.8, tired=0.6), me, face(me, (-30.0, 0.0, 12.0)), t,
            seed=52, amp=0.25)
    done(surface, r, buf, 41, t)


# --- more raid ----------------------------------------------------------------------
def _convoy(r, t, z0, n=3):
    from missions.m7 import raid_world as RW
    for i in range(n):
        z = z0 - 7.5 * i
        RW.put(r, RW.truck(), 0.0, 0.0, z, 0.0)
        for sx in (-0.68, 0.68):
            r.add_sprite((sx, 1.46, z + 2.95), fx.glow((255, 236, 200), 0.6, t, core=(255, 248, 230),
                                                       intensity=0.8, max_px=26), layer=fx.FX_LAYER)


def dusk_road(surface, t):
    """From the yard, high: far down the valley the convoy's lights come round the bend."""
    eye = mix((-3.0, 6.0, -9.0), (-2.6, 5.7, -11.0), k(t, 0, 3400))
    r, buf = F.stage("raid", t, eye, (0.0, 0.0, -90.0), 30, hh=0.004, seed=43)
    _convoy(r, t, -110.0 + 10.0 * k(t, 0, 3400))
    done(surface, r, buf, 43, t)


def dog_run(surface, t):
    """Ground level in the orchard grass: the dog comes straight at us, lights behind it."""
    from missions.m7 import raid_world as RW
    x = max(23.2, 37.0 - 6.4 * t / 1000.0)
    d = (x, 0.0, 1.6)
    eye = (21.8, 0.28, 1.1)
    r, buf = F.stage("raid", t, eye, (30.0, 0.7, 2.0), 40, hh=0.008, seed=45)
    clip = RW.dog_clip_s("Run")
    RW.put(r, RW.dog("Run", (t / 1000.0) % clip), d[0], 0.0, d[2], face(d, eye))
    for i, (gx, gz) in enumerate(((39.0, -1.5), (41.0, 4.5))):
        g = (gx - 1.2 * t / 1000.0, 0.0, gz)
        guard(r, t, g, eye, 110 + i, walk=0.8)
        lamp(r, t, ahead(g, eye, 0.75, 1.32), 110 + i)
    done(surface, r, buf, 45, t)


def three_gate(surface, t):
    """Biribel, Bodi and Alex walk into the yard toward us, guns up, slow."""
    u = k(t, 0, 3000)
    eye = mix((-3.0, 0.45, -5.4), (-3.0, 0.45, -6.2), u)
    r, buf = F.stage("raid", t, eye, (-3.0, 1.5, 3.0), 44, hh=0.005, seed=47)
    tt = t * 0.6                                         # the walk in slow motion
    for key, x, dz, ph, kw in ((BIRI, -3.0, 0.0, 0, dict(flags=SG)),
                               (BODI, -4.7, 0.7, 300, dict(hd=True)),
                               (ALEX, -1.4, 0.9, 650, dict(hd=True))):
        z = 4.6 + dz - 2.6 * u
        me = (x, 0.0, z)
        p = held(key, F.walk_pose(tt + ph, 0.75), "ready", **kw)
        W.actor(r, key, p, me, face(me, (x, 0.0, -20.0)), t, seed=52 + ph, amp=0.2, rifle_on=True,
                expression="stern", **kw)
    done(surface, r, buf, 47, t)


def guard_down(surface, t):
    """A Guard walking in through the trees is hit and folds onto his back."""
    hit = HITS["guard_down"][0]
    eye = mix((21.2, 1.1, -1.6), (21.4, 1.05, -1.4), k(t, 0, 2400))
    walk = min(t, hit)
    pos = (27.0 - 1.1 * walk / 1000.0, 0.0, 1.0)
    r, buf = F.stage("raid", t, eye, (pos[0], 0.8, pos[2]), 36, hh=0.006, seed=49)
    fall = k(t, hit, 650)
    if t >= hit:
        r.add_sprite((pos[0], 1.35, pos[2]), fx.powder(t - hit, seed=3, spread_m=0.5,
                     intensity=0.7 * max(0.0, 1 - (t - hit) / 500.0), col=(120, 30, 24), puffs=6),
                     layer=fx.FX_LAYER)
    stand = held(GUARD, F.walk_pose(walk, 0.75), "ready", hd=True)
    p = blend(stand, "dead_back", fall)
    back = (pos[0] + 0.9 * fall, 0.18 * fall, pos[2])
    W.actor(r, GUARD, p, back, face(pos, (20.0, 0.0, 1.0)), t, seed=97, amp=0.2 * (1 - fall),
            rifle_on=fall < 0.35, hd=True, mouth=0.0, expression="surprised" if t > hit else "stern")
    if fall >= 0.35:                                      # the rifle drops beside him
        m = Mesh()
        m.add(box(0.06, 0.06, 0.9, (30, 30, 32), center=(pos[0] - 0.4, 0.04, 0.3)))
        W.add(r, m)
    done(surface, r, buf, 49, t)


def bodi_aim(surface, t):
    """Tight on Bodi at the barn corner: aim, fire, work the bolt, fire."""
    me = (8.4, 0.0, 2.4)
    tgt = (30.0, 1.4, -2.0)
    eye = mix((8.6, 1.6, -0.4), (8.75, 1.58, -0.2), k(t, 0, 3000))
    r, buf = F.stage("raid", t, eye, (8.9, 1.45, 2.3), 36, hh=0.004, seed=51)
    shots = SHOTS["bodi_aim"]
    bolt = k(t, 900, 250) - k(t, 1500, 250)
    base = pose(spine=6, head_p=4 + 6 * bolt)
    r.set_lights(muzzle(r, t, ahead(me, tgt, 1.25, 1.5), shots))
    p = held(BODI, base, "aim", hd=True)
    W.actor(r, BODI, p, me, face(me, tgt), t, seed=61, amp=0.12, rifle_on=True, hd=True,
            expression="stern")
    done(surface, r, buf, 51, t)


def gate_entry(surface, t):
    """Guards file in through the south gate, backlit by the truck's lights."""
    from missions.m7 import raid_world as RW
    eye = mix((4.2, 0.9, -4.0), (3.9, 0.9, -4.6), k(t, 0, 3000))
    r, buf = F.stage("raid", t, eye, (0.0, 1.3, -16.0), 40, hh=0.006, seed=53)
    RW.put(r, RW.truck(), 0.0, 0.0, -30.0, 0.0)
    for sx in (-0.68, 0.68):
        r.add_sprite((sx, 1.46, -27.05), fx.glow((255, 240, 210), 1.5, t, core=(255, 252, 240),
                                                 intensity=1.0, max_px=140), layer=fx.FX_LAYER)
    r.set_lights([{"pos": (0.0, 1.5, -26.0), "color": (230, 236, 255), "intensity": 1.2,
                   "range": 18.0}])
    for i, dx in enumerate((-0.9, 0.6, -0.4, 1.1)):
        z = -21.0 + 1.3 * t / 1000.0 - 1.6 * i
        guard(r, t, (dx, 0.0, z), (dx * 3, 0.0, 10.0), 120 + i, walk=0.8)
    done(surface, r, buf, 53, t)


def biribel_run(surface, t):
    """Tracking Biribel as he sprints across the yard, shotgun up, fire from the trees."""
    x = -7.0 + 4.2 * t / 1000.0
    me = (x, 0.0, -1.0)
    eye = (x - 1.2, 1.2, -5.0)
    r, buf = F.stage("raid", t, eye, (x + 0.6, 1.1, -1.0), 40, hh=0.012, seed=55)
    r.set_lights(muzzle(r, t, (24.0, 1.4, 0.0), SHOTS["biribel_run"], col=(255, 200, 140)))
    p = held(BIRI, pose_run(t * 0.012, lean=14), "ready", flags=SG)
    W.actor(r, BIRI, p, me, face(me, (x + 5.0, 0.0, -1.0)), t, seed=52, amp=0.1, rifle_on=True,
            flags=SG, expression="angry")
    done(surface, r, buf, 55, t)


def officer_lamp(surface, t):
    """A Guard officer sweeps his flashlight across the yard; it finds the lens."""
    me = (27.0, 0.0, 1.2)
    eye = mix((23.6, 1.5, -0.4), (23.8, 1.5, -0.3), k(t, 0, 3000))
    r, buf = F.stage("raid", t, eye, (me[0], 1.55, me[2]), 30, hh=0.005, seed=57)
    sweep = math.radians(-50 + 60 * k(t, 0, 1600))
    look = (me[0] - 6 * math.cos(sweep), 0.0, me[2] + 6 * math.sin(sweep))
    hand = ahead(me, look, 0.6, 1.35)
    on_us = max(0.0, 1.0 - abs(face(me, look) - face(me, eye)) / 25.0)
    r.add_sprite(hand, fx.glow((220, 230, 255), 0.5 + 2.2 * on_us, t, core=(255, 255, 255),
                                intensity=0.9, max_px=40 + int(220 * on_us)), layer=fx.FX_LAYER)
    base = pose(spine=6, rsh_p=72, rel=20)
    W.actor(r, ("guard", "officer"), base, me, face(me, look), t, seed=99, amp=0.2, rifle_on=False,
            hd=True, mouth=0.0, expression="stern")
    done(surface, r, buf, 57, t)


def alex_fire(surface, t):
    """Alex comes up off the hay and empties the rifle into the dark, shouting."""
    me = (7.7, 0.0, 2.6)
    tgt = (30.0, 1.4, 0.0)
    eye = mix((10.2, 1.25, 0.6), (10.0, 1.25, 0.8), k(t, 0, 2400))
    r, buf = F.stage("raid", t, eye, (7.8, 1.25, 2.6), 34, hh=0.007, seed=59)
    rise = k(t, 200, 500)
    r.set_lights(muzzle(r, t, ahead(me, tgt, 1.2, 1.45), SHOTS["alex_fire"]))
    base = blend("cover_tight", "stand", rise)
    p = held(ALEX, base, "aim" if rise > 0.6 else "ready", hd=True)
    W.actor(r, ALEX, p, (me[0], -0.1 * (1 - rise), me[2]), face(me, tgt), t, seed=62, amp=0.3,
            rifle_on=True, hd=True, expression="angry", mouth=0.6 if t > 900 else 0.0)
    done(surface, r, buf, 59, t)


# --- more burning -------------------------------------------------------------------
def fire_window(surface, t):
    """Close on the farmhouse window: flames climbing out of it, smoke over the eaves."""
    eye = mix((-7.4, 1.5, 2.6), (-7.8, 1.6, 3.2), k(t, 0, 3000))
    r, buf = F.stage("burn", t, eye, (-9.8, 2.0, 7.0), 42, lights=F.burn_lights(t, 0.5), hh=0.004,
                     seed=61)
    F.burn_fx(r, t, 1.0)
    for i, (x, y) in enumerate(((-9.7, 1.5), (-9.4, 2.3), (-10.0, 2.9))):
        F.fire(r, (x, y, 6.85), t, seed=200 + i * 13, size=0.6 + 0.15 * i, smoky=i == 2)
    r.set_lights(F.burn_lights(t, 0.5) + [{"pos": (-9.6, 2.0, 6.2), "color": (255, 140, 60),
                                           "intensity": 1.3 + 0.2 * math.sin(t / 70.0), "range": 6.0}])
    done(surface, r, buf, 61, t)


def house_wide_burn(surface, t):
    """Wide from the orchard: house and barn ablaze, the trucks pulling out, tail lights."""
    from missions.m7 import raid_world as RW
    eye = mix((18.0, 1.6, -24.0), (17.0, 1.7, -23.0), k(t, 0, 3400))
    r, buf = F.stage("burn", t, eye, (-2.0, 3.0, 8.0), 54, lights=F.burn_lights(t), hh=0.004,
                     seed=63)
    F.burn_fx(r, t, 1.0)
    for i in range(2):
        z = -20.0 - 6.0 * t / 1000.0 - 8.0 * i
        RW.put(r, RW.truck(), 0.0, 0.0, z, 180.0)
        for sx in (-0.7, 0.7):
            r.add_sprite((sx, 1.15, z + 3.1), fx.glow((255, 40, 30), 0.25, t, core=(255, 120, 100),
                                                      intensity=0.9, max_px=14), layer=fx.FX_LAYER)
    done(surface, r, buf, 63, t)


def ember_sky(surface, t):
    """Looking up past the burning barn roof: sparks into black smoke."""
    eye = mix((10.6, 0.9, 1.2), (10.9, 0.9, 1.6), k(t, 0, 3000))
    r, buf = F.stage("burn", t, eye, (13.0, 9.0, 11.0), 62, lights=F.burn_lights(t, 0.6), hh=0.006,
                     seed=65)
    F.burn_fx(r, t, 1.0)
    for i, t0 in enumerate((-1200, 0, 1100, 2200)):
        if t >= t0:
            r.add_sprite((12.0 + 1.5 * i, 6.2, 10.5), F.sparks(t, t0, seed=7 + i), layer=fx.FX_LAYER)
    done(surface, r, buf, 65, t)


def bodi_grief(surface, t):
    """Bodi on his knees in the yard, his farm burning in front of him."""
    me = (-4.0, 0.0, -6.0)
    eye = mix((-2.4, 0.9, -11.0), (-2.8, 0.95, -10.2), k(t, 0, 3000))
    r, buf = F.stage("burn", t, eye, (-5.0, 2.2, 4.0), 46, lights=F.burn_lights(t, 0.3), hh=0.004,
                     seed=67)
    F.burn_fx(r, t, 1.0)
    F.burn_roof(r, 1.0)
    p = pose(**dict(POSES["kneel"], spine=24, head_p=26 - 14 * k(t, 1400, 1200), lsh_p=10, lel=10,
                    rsh_p=10, rel=10))
    W.actor(r, BODI, p, me, face(me, (-10.0, 0.0, 10.0)), t, seed=61, amp=0.35, hd=True)
    done(surface, r, buf, 67, t)


# --- stills for the thumbnails (tools/trailer_rpe6/dark_short.py) ---------------------
def thumb_hero(surface, t):
    """Biribel, shotgun at the ready, the farmhouse burning behind him."""
    me = (-7.4, 0.0, -4.0)
    eye = (-8.4, 1.0, -7.6)
    r, buf = F.stage("burn", t, eye, (-8.0, 2.3, 6.0), 46,
                     lights=F.burn_lights(t, 0.6) +
                     [{"pos": (-8.0, 2.6, -1.5), "color": (255, 140, 70), "intensity": 1.4, "range": 7.0},
                      {"pos": (-8.8, 2.0, -5.6), "color": (255, 190, 140), "intensity": 0.5, "range": 4.0}],
                     hh=0.003, seed=37)
    F.burn_fx(r, t, 1.0)
    for i, (x, y, z, size) in enumerate(HOUSE_FIRES):
        F.fire(r, (x, y, z), t, seed=91 + i * 11, size=size, smoky=i in (0, 3, 5))
    p = held(BIRI, pose(spine=4), "ready", flags=SG)
    W.actor(r, BIRI, p, me, face(me, (eye[0], 0.0, eye[2])), t, seed=52, amp=0.0, rifle_on=True,
            flags=SG, expression="angry", mouth=0.0)
    done(surface, r, buf, 37, t)
