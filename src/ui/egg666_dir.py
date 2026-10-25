"""egg666_dir.py - the director of the 3D "666" scare: what happens at which frame.

Pure math, no GL: a seeded Plan (flicker windows, demon stations, which way
the head tilts) and per-frame functions for the lamp, the eyes, the pose, the
camera and the post levels.  Everything is a function of (seed, frame), so a
frame is reproducible and the tests need no GPU.  Frames run at 60 fps:

    0-90      black and silent; one flicker shows the empty vault        beat 1
    90-240    five flickers, the demon nearer each time, never seen moving  beat 2
    240-390   view locked, slow dolly; the head snaps to the lens (262),
              the lamp dies (276-306), the jaw opens (322-386)           beat 3
    390-508   hard cut to the face; dead quiet (430); the lunge (440) with
              the red flash, the scream and the tears; the picture dies (508)
    508-540   black and silent, then the fake crash
"""
import math
import random

TOTAL = 540
CUT_F = 390                  # hard cut to the face close-up
QUIET_F = 430                # every bed stops: dead quiet before the lunge
LUNGE_F = 440                # the lunge, the red flash and the scream
BLACK_F = 508                # picture and sound die
LUNGE_DIST = 0.26            # metres the demon rushes the lens
DRONE_F, BREATH_F, CRACK_F, GROAN_F = 196, 205, 260, 322
FLICKS = ((40, 63), (90, 104), (131, 147), (168, 184), (195, 206), (215, 276))

REST = dict(x=0.0, z=0.0, dy=0.0, yaw=0.0, twist=0.0, bend=0.0, lean_lo=0.0, lean_hi=0.0,
            n1=0.0, n2=0.0, n3=0.0, nz1=0.0, nz2=0.0, nz3=0.0, h_rx=0.0, h_ry=0.0, h_rz=0.0,
            jaw=0.0, face=0.0, aL_rx=0.0, aL_rz=-3.0, eL=3.0, wL_rx=0.0, wL_rz=0.0,
            aR_rx=0.0, aR_rz=3.0, eR=3.0, wR_rx=0.0, wR_rz=0.0, hip=-14.0, knee=30.0, ankle=-16.0)

# Where it stands at each flicker (angles in degrees; rx < 0 leans toward the lens).
_ST = (None,
       dict(x=0.8, z=6.0, yaw=-6.0, lean_lo=-1.0, lean_hi=-2.0, n1=-2.0, n2=-3.0, n3=-4.0, nz2=2.0, nz3=4.0,
            face=-4.0, h_ry=-10.0, h_rz=18.0, jaw=3.0, aL_rz=-3.0, aR_rz=3.0, eL=3.0, eR=5.0),
       dict(x=-1.1, z=5.0, yaw=10.0, lean_lo=-4.0, lean_hi=-6.0, n1=-6.0, n2=-8.0, n3=-10.0, nz2=-4.0,
            nz3=-8.0, face=-6.0, h_ry=12.0, h_rz=-34.0, jaw=6.0, aL_rz=-5.0, aR_rz=9.0, aR_rx=10.0,
            eL=4.0, eR=16.0),
       dict(x=0.6, z=3.9, yaw=-4.0, lean_lo=-8.0, lean_hi=-10.0, n1=-10.0, n2=-12.0, n3=-14.0, nz2=3.0,
            nz3=7.0, face=-8.0, h_ry=-16.0, h_rz=52.0, jaw=12.0, aL_rx=8.0, aR_rx=5.0, eL=12.0, eR=10.0),
       dict(x=-0.45, z=2.9, yaw=6.0, lean_lo=-12.0, lean_hi=-14.0, n1=-14.0, n2=-16.0, n3=-18.0, nz1=3.0,
            nz2=-6.0, nz3=-10.0, face=-10.0, h_ry=10.0, h_rz=-64.0, jaw=20.0, aL_rx=12.0, aR_rx=14.0,
            eL=16.0, eR=20.0),
       dict(x=0.05, z=1.8, yaw=0.0, lean_lo=-22.0, lean_hi=-26.0, n1=-22.0, n2=-22.0, n3=-20.0, nz1=5.0,
            nz2=8.0, nz3=12.0, face=-12.0, h_ry=-24.0, h_rz=76.0, jaw=10.0, aL_rx=14.0, aR_rx=16.0,
            aL_rz=-6.0, aR_rz=6.0, eL=18.0, eR=22.0))


# -- tiny deterministic helpers -----------------------------------------------
def h01(*k):
    """A reproducible pseudo-random float in [0, 1) from integers."""
    h = 2166136261
    for v in k:
        h = ((h ^ (int(v) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
        h ^= h >> 15
        h = (h * 0x2C1B3C6D) & 0xFFFFFFFF
        h ^= h >> 12
    return (h & 0xFFFFFF) / 16777216.0


def sm(x):
    x = 0.0 if x < 0.0 else 1.0 if x > 1.0 else x
    return x * x * (3.0 - 2.0 * x)


def ramp(f, a, b):
    return sm((f - a) / float(b - a))


def lerp(a, b, t):
    return a + (b - a) * t


def vnoise(seed, x, k):
    """Smooth value noise in [-1, 1]."""
    i = math.floor(x)
    a, b = h01(seed, i, k), h01(seed, i + 1, k)
    return (a + (b - a) * sm(x - i)) * 2.0 - 1.0


# -- the plan ------------------------------------------------------------------
class Plan:
    pass


def make_plan(seed):
    rg = random.Random(int(seed))
    p = Plan()
    p.seed = int(seed)
    p.mirror = -1.0 if rg.random() < 0.5 else 1.0
    wins = []
    for i, (a, b) in enumerate(FLICKS):
        if i > 1:                                          # the first demon flicker opens at 1.5 s sharp
            a += rg.randint(-2, 2)
        if i < len(FLICKS) - 1:
            b += rg.randint(-1, 2)
        drops = set()
        if i == 0:
            drops.update((a + 4, a + 5))                      # the first flicker stutters
        elif i < 5 and b - a >= 10:
            s = a + rg.randint(3, 5)                       # reveal, stutter, reveal
            drops.update(range(s, s + rg.randint(1, 2)))
        wins.append((a, b, frozenset(drops)))
    p.wins = tuple(wins)
    stations = [None]
    for i in range(1, 6):
        d = dict(REST)
        d.update(_ST[i])
        for k in ("x", "yaw", "h_ry", "h_rz", "nz1", "nz2", "nz3", "bend", "twist"):
            d[k] *= p.mirror
        d["x"] += rg.uniform(-0.15, 0.15)
        d["z"] += rg.uniform(-0.10, 0.10)
        for k in ("face", "h_rz", "n2", "n3"):
            d[k] += rg.uniform(-3.0, 3.0)
        stations.append(d)
    p.stations = tuple(stations)
    p.lamp_ph = (rg.uniform(0.0, 6.28), rg.uniform(0.0, 6.28))
    return p


def station(f, plan):
    """0 = the empty vault, 1..5 = where it stands (it changes in the dark)."""
    k = 0
    for i, w in enumerate(plan.wins):
        if f >= w[0]:
            k = i
    return k


def lamp(f, plan):
    """Lamp brightness 0..1: the flicker windows, a buzzing steady light, its death throes."""
    s = plan.seed
    for i, (a, b, drops) in enumerate(plan.wins):
        if a <= f < b:
            if f in drops:
                return 0.0
            if i == 5:
                return 0.58 + 0.12 * math.sin(f * 0.83) + 0.22 * h01(s, f // 2, 2)
            return (0.80 + 0.20 * h01(s, f, 1)) * (0.55 if f == a else 1.0)
    if 276 <= f < 306 and h01(s, f // 2, 4) < 0.8 * (1.0 - (f - 276) / 30.0):
        return 0.30 + 0.45 * h01(s, f, 3)
    return 0.0


def lamp_swing(f, plan):
    """The bulb's pendulum (degrees about x and z): every flicker finds it elsewhere."""
    return (11.0 * math.sin(f * 0.037 + plan.lamp_ph[0]), 14.0 * math.sin(f * 0.026 + plan.lamp_ph[1]))


def eyes(f, plan, lamp_k):
    """Brightness of the three eye pairs: the face, the forehead, the cheeks."""
    if f >= CUT_F:
        k = 1.0 if f >= LUNGE_F else 0.9 + 0.1 * h01(plan.seed, f // 2, 5)
        return (k, k, k)
    s = station(f, plan)
    if s < 1 or not (lamp_k > 0.0 or f >= 296):
        return (0.0, 0.0, 0.0)
    e1, e2, e3 = 0.30 + 0.07 * s, (0.40 if s >= 3 else 0.0), 0.0
    if f >= 262:
        e1, e2 = lerp(0.55, 1.0, ramp(f, 262, 330)), lerp(0.45, 0.95, ramp(f, 262, 340))
        e3 = 0.9 * ramp(f, 326, 350)
    return (e1, e2, e3)


def marks(f, lamp_k):
    """Glow of the ritual marks: dark in the first black, an ember in the gaps."""
    if lamp_k > 0.0:
        base = 0.9
    elif f >= 96:
        base = 0.26 + 0.40 * ramp(f, 300, 380)
    else:
        return 0.0
    return base * (0.85 + 0.15 * math.sin(f * 0.11))


def flashlight(f, plan):
    """The beam on the face in the close-up: it flickers, showing a little more each time."""
    if f < CUT_F or f >= BLACK_F:
        return 0.0
    for a, b in ((396, 402), (410, 414), (420, 428), (434, 440)):
        if a <= f < b:
            return 0.55 + 0.45 * h01(plan.seed, f, 6)
    if f >= LUNGE_F + 2:
        return 0.15 + 0.2 * h01(plan.seed, f // 2, 7)
    return 0.0


# -- sound clock ---------------------------------------------------------------
def beat_frames():
    out, f = [], 244
    while f < QUIET_F:
        out.append(f)
        f += int(round(lerp(52.0, 15.0, ramp(f, 240, QUIET_F))))
    return tuple(out)


BEATS = beat_frames()


def pulse(f):
    """0..1 heartbeat thump, for the marks and the eyes to hammer with."""
    k = 0.0
    for b in BEATS:
        if b <= f < b + 24:
            k = max(k, math.exp(-(f - b) / 6.0))
    return k


def demon_bed_level(f):
    """How loud assets/demon.mp3 (the optional bed) plays under the scare."""
    if f < 300 or f >= BLACK_F or QUIET_F <= f < LUNGE_F:
        return 0.0
    return 0.4 * ramp(f, 300, 390) if f < QUIET_F else 0.9


# -- the demon ------------------------------------------------------------------
def pose(f, plan):
    """Joint angles (degrees) and root position of the demon at frame ``f``."""
    P = dict(plan.stations[max(1, station(f, plan))])
    s, m = plan.seed, plan.mirror
    fb = min(f, CUT_F)
    if fb >= 262:                                  # the head snaps to the lens, the body does not
        t = (fb - 262) / 5.0
        v = 0.0 if t <= 0.0 else (1.25 * (t / 0.6) ** 0.8 if t < 0.6 else 1.25 - 0.25 * min(1.0, (t - 0.6) / 0.4))
        P["face"] = lerp(P["face"], -12.0, v)
        P["h_ry"] = lerp(P["h_ry"], 0.0, v)
        P["h_rz"] = lerp(P["h_rz"], -4.0 * m, v)
        if fb >= 272:
            P["h_rz"] += (h01(s, fb // 4, 12) - 0.5) * 4.0
        e = ramp(fb, 300, 385)                     # the neck cranes in, the arms reach, in 10 fps steps
        for k in ("n1", "n2", "n3"):
            P[k] -= 6.0 * e
        P["lean_hi"] -= 4.0 * e
        ea = ramp(fb - fb % 6, 300, 385)
        P["aL_rx"] += 34.0 * ea
        P["aR_rx"] += 40.0 * ea
        P["eL"] += 20.0 * ea
        P["eR"] += 26.0 * ea
        P["aL_rz"] -= 6.0 * ea
        P["aR_rz"] += 8.0 * ea
        P["jaw"] = lerp(P["jaw"], 68.0, ramp(fb - fb % 5, GROAN_F, 386))   # the jaw ratchets open
    # the head keeps its face on the lens whatever the chain of leans adds up to
    P["h_rx"] = P["face"] - (P["lean_lo"] + P["lean_hi"] + P["n1"] + P["n2"] + P["n3"])
    if fb >= 272:
        P["h_rx"] += (h01(s, fb // 4, 11) - 0.5) * 3.0
    lunge = 0.0
    if f >= CUT_F:
        q = f // 2
        k = ramp(f, 400, LUNGE_F)
        P["h_rx"] += (h01(s, q, 21) - 0.5) * (2.0 + 6.0 * k)
        P["h_rz"] += (h01(s, q, 22) - 0.5) * (3.0 + 8.0 * k)
        P["jaw"] = 68.0 + 6.0 * ramp(f, CUT_F, QUIET_F) + 3.0 * (h01(s, f // 3, 23) - 0.5)
        if f >= LUNGE_F:
            P["jaw"] = lerp(P["jaw"], 94.0, ramp(f, LUNGE_F, LUNGE_F + 3))
            lunge = LUNGE_DIST * min(1.0, (f - LUNGE_F) / 5.0) ** 0.5
    P["jaw_rx"] = -P["jaw"]
    P["lunge"] = lunge
    return P


def camera(f, plan, cu, calm=1.0):
    """-> (pos, target, horizontal fov, roll) in world space.  ``cu`` is
    (face centre, face forward) at the hard cut; ``calm`` < 1 tames the shake."""
    s, m = plan.seed, plan.mirror
    if f < CUT_F:                                  # the player's eyes, then the locked slow dolly
        u = ramp(f, 240, CUT_F)
        amp = (0.10 + 0.55 * u ** 1.4) * calm
        pitch = math.radians(3.0 + 6.0 * ramp(f, 100, 240) + 9.0 * u + amp * vnoise(s, f * 0.19, 32))
        yaw = math.radians(amp * vnoise(s, f * 0.21, 31))
        pos = (0.015 * vnoise(s, f * 0.05, 34),
               1.55 + 0.012 * math.sin(f * 0.045) + 0.01 * vnoise(s, f * 0.09, 35),
               -1.25 + 0.70 * u)
        tgt = (pos[0] + 10.0 * math.sin(yaw) * math.cos(pitch), pos[1] + 10.0 * math.sin(pitch),
               pos[2] + 10.0 * math.cos(yaw) * math.cos(pitch))
        roll = 1.8 * ramp(f, 300, CUT_F) * m + 0.3 * amp * vnoise(s, f * 0.17, 33)
        return pos, tgt, 72.0 + 8.0 * u, roll
    (hx, hy, hz), (fx, fy, fz) = cu
    push = ramp(f, CUT_F, QUIET_F + 6)
    d = 0.64 - 0.18 * push
    lunge = 0.0 if f < LUNGE_F else math.exp(-(f - LUNGE_F) / 14.0)
    amp = (0.004 + 0.010 * ramp(f, CUT_F, LUNGE_F) + 0.06 * lunge) * calm
    ox, oy = amp * vnoise(s, f * 0.9, 41), amp * vnoise(s, f * 0.9, 42)
    pos = (hx + fx * d + ox, hy + fy * d + oy, hz + fz * d)
    tgt = (hx - ox * 0.5, hy - oy * 0.5, hz)
    fov = 58.0 + 6.0 * push + 20.0 * ramp(f, LUNGE_F, LUNGE_F + 4)
    roll = 5.0 * m * (0.4 + 0.6 * push) + 7.0 * lunge * vnoise(s, f * 0.7, 43)
    return pos, tgt, fov, roll


# -- the picture's treatment -----------------------------------------------------
def post(f, plan):
    """-> whole-number levels for egg666_post, and the squeeze while the picture dies."""
    s = plan.seed
    if f < 330:
        barrel = 0
    elif f < CUT_F:
        barrel = int(3.0 * ramp(f, 330, CUT_F) + 0.5)
    else:
        barrel = 4 + int(2.0 * ramp(f, QUIET_F, LUNGE_F)) + (1 if f >= LUNGE_F else 0)
    chroma = int(round(3.0 * ramp(f, 260, CUT_F)))
    if f >= CUT_F:
        chroma = 3 + int(round(3.0 * ramp(f, 400, LUNGE_F)))
    if f >= LUNGE_F:
        chroma = int(round(9.0 - 5.0 * ramp(f, LUNGE_F + 4, BLACK_F)))
    tears, tear_amp = 0, 0
    if 300 <= f < CUT_F and h01(s, f, 51) < 0.22 + 0.3 * ramp(f, 300, CUT_F):
        tears, tear_amp = 1 + int(2.0 * h01(s, f, 52)), 4 + int(24.0 * ramp(f, 300, CUT_F))
    elif CUT_F <= f < LUNGE_F and h01(s, f, 53) < 0.5:
        tears, tear_amp = 1 + int(3.0 * ramp(f, CUT_F, LUNGE_F)), 20 + int(30.0 * ramp(f, CUT_F, LUNGE_F))
    elif f >= LUNGE_F:
        tears, tear_amp = 5 + int(8.0 * h01(s, f, 54)), 50 + int(60.0 * h01(s, f, 55))
    squeeze = None
    if f >= 500:
        squeeze = max(0.02, 1.0 - (f - 499) / 9.0)
    return dict(vig=min(8, 3 + int(3.0 * ramp(f, 100, CUT_F)) + (2 if f >= CUT_F else 0)),
                barrel=barrel, chroma=chroma, tears=tears, tear_amp=tear_amp,
                grain=1 if f < 240 else 2, roll=int((f - 484) ** 1.6 * 3.0) if f >= 484 else 0,
                squeeze=squeeze)


def flash_rgb(f, scale=1.0):
    """The full-screen red flash at the lunge and its afterglow, as an additive tint."""
    a = f - LUNGE_F
    if a < 0 or a >= 50:
        return (0, 0, 0)
    k = 1.0 if a < 2 else (1.0 - 0.72 * (a - 2) / 8.0 if a < 10 else 0.28 * (1.0 - (a - 10) / 40.0))
    k *= scale
    g = 0.34 if a < 2 else 0.22
    return (int(255 * k), int(255 * k * g), int(255 * k * g * 0.7))
