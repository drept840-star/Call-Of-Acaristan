"""m6world3d.py - engine3d sets and actor kit for the Mission 6 films.

Used by ``cutscenes.m6films`` only.  Never imports ``missions.m6``: the shot
data lives in the mission, the renderers live here (same boundary as M5).

Sets
    hills / border crossing    snowy night terrain, the customs compound and
                               its frozen car queue, sodium work lights
    helicopter                 box/faceted airframe, spinning main + tail rotor,
                               nav lights, open cabin door, down-wash
    boxcar interior            plank walls and ribs, open door onto the yard,
                               hanging lantern, crates, the black notebook
    rail platform              tracks, waiting passenger train with lit
                               windows, signal tower, floodlight masts
    terminal office            Guard terminal, CRT, radio desk, window snow
    Vasile's office            empty chair, desk, blinds, city glow

Actors
    ``actor`` adds a cast3d rig (Biribel in Guard black via core.outfits,
    Volkov, Maru, Guard troopers) with breathing, weight shift and a talking
    mouth for the shot's current speaker.  All motion is time-driven and
    reduced-motion aware through ``m5fx3d.set_cam``.

The film buffer is rendered at 0.6x of the SAFE_TOP..SAFE_BOT band and
smooth-scaled up; captions stay property of the CutscenePlayer.
"""
import math
import random

import pygame

from core.config import HEIGHT, SCENE_TOP, WIDTH, font_terminal_small
from core.outfits import OUTFIT_GUARD, biribel_3d
from cutscenes import m5fx3d as _fx
from cutscenes.cast3d import humanoid3d, spec3d

SAFE_TOP = SCENE_TOP + 6
SAFE_BOT = HEIGHT - 158
FILM_H = SAFE_BOT - SAFE_TOP
RES = 0.6
RW, RH = int(WIDTH * RES), int(FILM_H * RES)

SNOW = (176, 188, 206)
SNOW_DARK = (44, 54, 70)
NIGHT = (7, 10, 18)
SODIUM = (255, 176, 96)
WARM = (255, 208, 150)
COLD = (120, 156, 206)

_cache = {"r": {}, "hum": {}, "grade": {}, "puff": {}, "err": None}
# Actors drawn this frame (cleared by rend()): the probe and tests read the
# final pose/joints from here instead of re-posing anything.
LAST = []

__all__ = [
    "SAFE_TOP", "SAFE_BOT", "FILM_H", "RW", "RH", "SNOW", "NIGHT", "WARM",
    "COLD", "SODIUM", "rend", "present", "cam", "add", "film_xy", "project_xy",
    "grade", "finish", "hum", "actor", "air_actor", "life_pose", "yaw_to",
    "current_shot", "speaker", "talking", "snow3d", "breath", "hills",
    "terrain", "height_at", "LZ", "LZ_Y", "border_compound", "helicopter",
    "heli_xform", "heli_solids", "HELI_SILL_Y", "HELI_SKID_X", "HELI_SKID_Y",
    "HELI_DOOR_Z", "HELI_ROTOR_R", "boxcar_interior", "rail_platform",
    "terminal_office", "vasile_office", "night", "warm_lamp",
    "LAST", "STANCE", "ease5", "travel", "yaw_mix", "leg_ik", "path",
    "walk_stride", "walk_span", "walk", "walk_slip", "sit_pose", "ankles",
    "planted_pos", "reach", "SOLIDS", "solids", "penetration", "LANTERN",
    "knees", "head_stats",
]


# ── plumbing ───────────────────────────────────────────────────────────────
def rend(w=RW, h=RH):
    key = (int(w), int(h))
    if key not in _cache["r"]:
        from engine3d import Renderer  # lazy: the 2D fallback owns import errors
        _cache["r"][key] = (Renderer(key[0], key[1]), pygame.Surface(key))
    del LAST[:]
    _cache["last_r"] = _cache["r"][key][0]
    return _cache["r"][key]


def present(surface, buf, x=0, w=WIDTH):
    """Gamma-grade the small buffer before the upscale: the LUT runs on
    ~165k pixels instead of ~460k, and the vignette stays at full res."""
    key = (0.82, 0.40)
    entry = _cache["grade"].get(key)
    if entry is not None:
        lut = entry[0]
        try:
            import numpy as np
            arr = pygame.surfarray.pixels3d(buf)
            arr[...] = np.asarray(lut, dtype=np.uint8)[arr]
            del arr
            _cache["graded_buf"] = True
        except Exception:
            _cache["graded_buf"] = False
    surface.blit(pygame.transform.smoothscale(buf, (w, FILM_H)), (x, SAFE_TOP))


def film_xy(p, x0=0, w=WIDTH, rw=RW):
    s = w / float(rw)
    return int(x0 + p[0] * s), int(SAFE_TOP + p[1] * s)


def project_xy(r, p, x0=0, w=WIDTH):
    q = r.project(p)
    return None if q is None else film_xy(q, x0, w)


def cam(r, t, eye, tgt, fov, hh=0.0, seed=0, roll=0.0, shk=None):
    return _fx.set_cam(r, t, eye, tgt, fov, hh=hh, seed=seed, roll=roll, shk=shk)


def add(r, m, bias=0.0):
    if _STATIC_BUILD["active"]:
        if _STATIC_BUILD["rebuild"]:
            r.bake(m)
        return
    faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces]
    r.add_dynamic(m.verts, faces, bias=bias)


_STATIC_BUILD = {"active": False, "rebuild": False}
_STATIC_SIG = None


def _light_sig(light):
    if light is None:
        return None
    return (tuple(round(float(v), 4) for v in light.dir),
            round(float(light.ambient), 4), round(float(light.diffuse), 4),
            round(float(light.sky), 4),
            tuple(round(float(v), 4) for v in light.tint))


def static_scene(r, key):
    """Begin a static batch for a set/rig; True on the first frame.

    Exterior sets never move, so bake them once instead of re-packing hundreds
    of little objects every frame.  Call before the set builders and
    ``static_end`` after them; dynamic actors/helicopters follow.
    """
    global _STATIC_SIG
    sig = (id(r), key, _light_sig(getattr(r, "light", None)))
    _STATIC_BUILD["active"] = True
    if sig == _STATIC_SIG:
        _STATIC_BUILD["rebuild"] = False
        return False
    r.objs.clear()
    invalidate = getattr(r, "invalidate_static", None)
    if invalidate:
        invalidate()
    _STATIC_SIG = sig
    _STATIC_BUILD["rebuild"] = True
    return True


def static_end(r, ok=True):
    """Close a static batch opened by ``static_scene``.

    ``ok=False`` means the set builder raised partway: the half-built batch
    must not be committed, and the signature is cleared so the next frame
    rebuilds the set in full instead of reusing the fragment.
    """
    global _STATIC_SIG
    _STATIC_BUILD["active"] = False
    _STATIC_BUILD["rebuild"] = False
    if not ok:
        _STATIC_SIG = None
        r.objs.clear()
        invalidate = getattr(r, "invalidate_static", None)
        if invalidate:
            invalidate()
        return
    r.add_static()


def yaw_to(src, dst):
    """Yaw (deg) turning a +z-facing rig at ``src`` toward ``dst``."""
    from engine3d.core import m_apply, rot_y
    sgn = 1.0 if m_apply(rot_y(90), (0, 0, 1))[0] > 0 else -1.0
    return sgn * math.degrees(math.atan2(dst[0] - src[0], dst[2] - src[2]))


def current_shot():
    try:
        from core.cutscene_registry import current_shot as _cur
        return _cur()
    except Exception:
        return None


def speaker():
    shot = current_shot() or {}
    return str(shot.get("speaker") or "").strip().upper()


def talking(who):
    return speaker() == who


# ── film grade ─────────────────────────────────────────────────────────────
def grade(surface, gamma=0.82, vig=0.40):
    """Lift crushed software shadows and pull the corners down."""
    band = surface.subsurface((0, SAFE_TOP, WIDTH, FILM_H))
    key = (gamma, vig)
    if key not in _cache["grade"]:
        lut = [min(255, int(255 * (i / 255.0) ** gamma + 0.5)) for i in range(256)]
        small = pygame.Surface((48, 24))
        for y in range(24):
            for x in range(48):
                dx, dy = (x - 23.5) / 23.5, (y - 11.5) / 11.5
                v = max(0.0, 1.0 - vig * (0.55 * dx * dx + 0.45 * dy * dy) ** 1.2)
                small.set_at((x, y), (int(255 * v),) * 3)
        _cache["grade"][key] = (lut, pygame.transform.smoothscale(small, (WIDTH, FILM_H)))
    lut, vmask = _cache["grade"][key]
    if not _cache.pop("graded_buf", False):
        try:
            import numpy as np
            arr = pygame.surfarray.pixels3d(band)
            arr[...] = np.asarray(lut, dtype=np.uint8)[arr]
            del arr
        except Exception:
            pass
    band.blit(vmask, (0, 0), special_flags=pygame.BLEND_MULT)


def finish(surface, seed, tag="", col=(120, 190, 220)):
    grade(surface)
    # Fine grain: a fixed pattern shifted by the clock, never global RNG.
    if not _cache.get("noise"):
        rng = random.Random(99)
        n = pygame.Surface((WIDTH, FILM_H), pygame.SRCALPHA)
        n.fill((0, 0, 0, 0))
        for _ in range(1400):
            x, y = rng.randrange(WIDTH), rng.randrange(FILM_H)
            v = rng.randrange(10, 26)
            n.set_at((x, y), (v, v, v, 255))
        _cache["noise"] = n
    band = surface.subsurface((0, SAFE_TOP, WIDTH, FILM_H))
    x = int((seed * 37) % WIDTH)
    band.blit(_cache["noise"], (-x, 0))
    band.blit(_cache["noise"], (WIDTH - x, 0))
    if tag:
        surf = font_terminal_small.render(tag, True, col)
        plate = pygame.Surface((surf.get_width() + 20, surf.get_height() + 6),
                               pygame.SRCALPHA)
        plate.fill((4, 6, 10, 186))
        pygame.draw.rect(plate, (*col, 90), plate.get_rect(), 1)
        surface.blit(plate, (24, SAFE_TOP + 6))
        surface.blit(surf, (34, SAFE_TOP + 9))


# ── actors ────────────────────────────────────────────────────────────────
# Guard variants for the interactive train.  The plain ``"guard"`` spec stays
# the film extra; the tuple keys add silhouettes the player can tell apart at
# thirty metres (beret line infantry, beanie/mask rusher, pale marksman,
# helmeted heavy, peaked-cap officer).  Keys are additive: every field that
# ``cast3d.spec3d`` does not translate (headgear, mask, backpack, long coat)
# is passed straight to ``Humanoid``.
_GUARD_VARIANTS = {
    "rifle": dict(
        rifle="rifle",
        head=dict(beret=(26, 28, 32)),
        body=dict(coat=(24, 25, 28), lapel=(17, 18, 21), vest=(36, 38, 42),
                  trousers=(28, 30, 34), shirt=(50, 52, 56),
                  patch=(70, 118, 196), armband=(176, 38, 34),
                  glove=(18, 19, 22)),
    ),
    "rusher": dict(
        rifle="os12",
        head=dict(beanie=(52, 56, 62), mask=(26, 29, 34)),
        body=dict(coat=(42, 46, 54), lapel=(30, 34, 40), vest=(50, 56, 64),
                  trousers=(34, 38, 44), shoes=(14, 16, 20), shirt=(72, 76, 84),
                  patch=(176, 44, 38), armband=(196, 46, 38),
                  glove=(22, 24, 28), bulk=0.98),
    ),
    "marksman": dict(
        rifle="sniper",
        head=dict(beanie=(132, 138, 142), mask=(70, 74, 80)),
        body=dict(coat=(112, 118, 122), lapel=(80, 86, 92), vest=(88, 94, 98),
                  trousers=(68, 74, 80), shoes=(32, 34, 38), shirt=(140, 146, 150),
                  patch=(130, 150, 174), armband=(110, 118, 126),
                  glove=(26, 28, 32), bulk=0.97, height=254),
    ),
    "heavy": dict(
        rifle="rifle",
        head=dict(helmet=(46, 50, 58), mask=(30, 32, 36)),
        body=dict(coat=(28, 30, 34), lapel=(19, 21, 24), vest=(48, 52, 58),
                  trousers=(24, 26, 30), shoes=(14, 16, 18), shirt=(60, 64, 70),
                  patch=(176, 42, 36), armband=(190, 44, 38),
                  glove=(16, 18, 20), bulk=1.34, height=272,
                  backpack=(30, 32, 36)),
    ),
    "officer": dict(
        rifle="os12",
        head=dict(cap=(30, 36, 50)),
        body=dict(coat=(38, 44, 58), lapel=(26, 31, 42), vest=(30, 34, 44),
                  trousers=(22, 26, 34), shoes=(10, 12, 16), shirt=(150, 148, 138),
                  patch=(190, 154, 74), armband=(194, 160, 80),
                  glove=(20, 22, 26), bulk=1.04, long_coat=(38, 44, 58)),
    ),
}


def _base_guard_spec():
    from cutscenes.figure_kit import SPECS
    fk = dict(SPECS["krap"])
    fk.update(coat=(26, 26, 28), lapel=(19, 19, 21), shirt=(44, 44, 46),
              vest=(38, 38, 41), trousers=(30, 30, 32), shoes=(16, 16, 18),
              belt=(14, 14, 16), patch=(70, 118, 196), armband=(176, 36, 36),
              beret=(24, 24, 26), glove=(20, 20, 22), height=262)
    return fk


def guard_spec(kind="rifle"):
    """figure_kit spec for a train Guard variant (``"rifle"`` by default)."""
    variant = _GUARD_VARIANTS.get(kind, _GUARD_VARIANTS["rifle"])
    fk = _base_guard_spec()
    fk.update(variant.get("body", {}))
    return fk, variant


def _guard_humanoid(kind):
    from engine3d import Humanoid
    fk, variant = guard_spec(kind)
    out = spec3d(fk, rifle=variant["rifle"])
    for key, value in variant.get("head", {}).items():
        out[key] = value
    for key in ("backpack", "coat_len", "long_coat", "pouches"):
        if key in variant.get("body", {}):
            out[key] = variant["body"][key]
    return Humanoid(out)


def hum(key):
    h = _cache["hum"].get(key)
    if h is None:
        if isinstance(key, tuple) and key[0] == "biribel":
            h = humanoid3d("biribel", **biribel_3d(key[1]))
        elif isinstance(key, tuple) and key[0] == "guard":
            h = _guard_humanoid(key[1])
        elif key == "guard":
            from engine3d import Humanoid
            h = Humanoid(spec3d(_base_guard_spec(), rifle="rifle"))
        elif key == "ucilev":
            h = humanoid3d("ucilev", rifle="sniper")
        else:
            h = humanoid3d(key)
        _cache["hum"][key] = h
    return h


def life_pose(pose, t, amp=1.0, seed=0):
    """Author pose + breath/weight/posture added, never replacing it."""
    p = dict(pose)
    a = t * 0.001
    br = amp * math.sin(a * 1.55 + seed * 1.7)
    p["spine"] = p.get("spine", 0) + 0.75 * br
    p["body_p"] = p.get("body_p", 0) + 0.18 * amp * math.sin(a * 0.83 + seed * 2.3)
    p["head_y"] = p.get("head_y", 0) + 1.1 * amp * math.sin(a * 0.57 + seed * 3.1)
    p["head_p"] = p.get("head_p", 0) + 0.45 * amp * math.sin(a * 0.71 + seed * 1.3)
    p["lsh_p"] = p.get("lsh_p", 0) + 0.5 * br
    p["rsh_p"] = p.get("rsh_p", 0) + 0.4 * br
    return p


def actor(r, key, pose, pos, yaw, t, seed=0, amp=1.0, rifle_on=False,
          expression=None, mouth=None, bias=0.0):
    h = hum(key)
    expr = expression or "neutral"
    if mouth is None:
        mouth = 0.0
        try:
            from engine3d.rig import mouth_flap
            if talking(str(key).upper() if not isinstance(key, tuple) else "BIRIBEL"):
                mouth = mouth_flap(int(t), seed)
        except Exception:
            pass
    if getattr(h, "_m6_face", None) != (expr, round(mouth, 2) if mouth else 0.0):
        h.set_expression(expr, mouth)
        h._m6_face = (expr, round(mouth, 2) if mouth else 0.0)
    p = life_pose(pose, t, amp, seed)
    joints = r.add_humanoid(h, p, pos, yaw, rifle_on=rifle_on, bias=bias)
    if len(LAST) < 16:
        LAST.append({"key": key, "joints": joints, "pos": tuple(pos),
                     "yaw": yaw, "pose": p})
    return joints


def air_actor(r, key, pose, pos, yaw, t, seed=0, expression=None, mouth=0.0,
              tint=None):
    """Un-grounded actor (falling/tumbling): no ground contact, no shadow."""
    h = hum(key)
    if expression:
        h.set_expression(expression, mouth)
    elif mouth:
        h.set_expression(None, mouth)
    verts, faces, joints = h.build(life_pose(pose, t, 0, seed), pos, yaw,
                                   rifle_on=False)
    r.add_dynamic(verts, faces, tint=tint)
    return joints


# ── motion kit ────────────────────────────────────────────────────────────
# Ported from cutscenes.m5shadow3d (it imports missions.m5, so the films may
# not).  Distance, never time, drives the legs: a planted foot stays planted
# whatever the speed profile, and stops land in double support.
STANCE = 0.56
_LEG = 0.45  # thigh = shin, rig units


def ease5(t, start, length):
    p = max(0.0, min(1.0, (float(t) - start) / float(length)))
    return p * p * p * (p * (p * 6 - 15) + 10)


def travel(t, start, duration):
    """0..1 distance: smooth start and stop, steady middle."""
    p = max(0.0, min(1.0, (t - start) / float(duration)))
    a = 0.16
    if p < a:
        q = p * p / (2 * a)
    elif p > 1 - a:
        q = 1 - a - (1 - p) * (1 - p) / (2 * a)
    else:
        q = p - a / 2
    return q / (1 - a)


def yaw_mix(a, b, p):
    return a + ((b - a + 180) % 360 - 180) * p


def leg_ik(foot_z, foot_y):
    """Two-link leg in rig space (hip -> ankle). -> hip_p, knee (deg)."""
    r = min(0.897, math.hypot(foot_y, foot_z))
    c = (r * r - 2 * _LEG * _LEG) / (2 * _LEG * _LEG)
    knee = math.acos(max(-1.0, min(1.0, c)))
    return (math.degrees(math.atan2(foot_z, -foot_y) + knee * 0.5),
            math.degrees(knee))


def path(points, smooth=0.3):
    """Floor route through [(x, z)] or [(x, y, z)] -> route(d) -> (pos, yaw).
    Heading is the chord over +-``smooth`` m, so corners turn, never snap."""
    pts = [(p[0], p[1] if len(p) == 3 else 0.0, p[-1]) for p in points]
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[2] - a[2]))
    total = cum[-1]

    def at(d):
        d = max(0.0, min(total, d))
        for i in range(len(pts) - 1):
            if d <= cum[i + 1] or i == len(pts) - 2:
                a, b = pts[i], pts[i + 1]
                u = (d - cum[i]) / max(1e-9, cum[i + 1] - cum[i])
                return tuple(a[j] + (b[j] - a[j]) * u for j in range(3))
        return pts[-1]

    def route(d):
        return at(d), yaw_to(at(d - smooth), at(d + smooth))

    route.length = total
    return route


def walk_stride(length, nominal=0.62):
    """Stride that lands the stop in double support, feet together."""
    m = max(1, int(round(length / nominal - 0.09)))
    return length / (m + 0.09)


def walk_span(length, stride):
    """Gait parameter range: feet together at the route start .. its end."""
    h = 0.44 * stride
    return -h, length + h


def _walk_body(g, length, s):
    # Body eases out of and into the stand while the first/last step lands.
    h = 0.44 * s
    if length < 2 * h:
        u = max(0.0, min(1.0, (g + h) / (length + 2 * h)))
        return length * u * u * (3 - 2 * u)
    if g < h:
        return max(0.0, g + h) ** 2 / (4 * h)
    if g > length - h:
        return length - max(0.0, length + h - g) ** 2 / (4 * h)
    return g


def walk(hum, route, g, stride, speed=1.2, ground=None):
    """Planted-foot walk along ``route`` (see ``path``) from a stand to a stand.

    ``g`` runs over ``walk_span(route.length, stride)``: both feet together at
    the route start, then at its end.  Each contact is laid on the route and
    held fixed in WORLD space for STANCE of the cycle; both legs are solved by
    IK every frame, so turns and stops never slide a foot.  ``ground(x, z)``
    gives terrain height.  -> (pose, pos, yaw) for ``actor``.
    """
    s = stride
    length = route.length
    scale = hum._scale
    g0, g1 = walk_span(length, s)
    g = max(g0, min(g1, g))
    ramp = max(0.0, min(1.0, (g - g0) / (1.2 * s), (g1 - g) / (1.2 * s)))
    amp = max(0.0, min(1.0, speed / 1.35)) * ramp
    reach_d = STANCE * s / 2
    ph_l = (g / s) % 1.0
    pelvis = -2.2 * amp * math.cos(2 * math.pi * (ph_l - 0.02))
    pos, yaw = route(_walk_body(g, length, s))
    if ground is not None:
        pos = (pos[0], ground(pos[0], pos[2]), pos[2])
    yaw += pelvis
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    pose = {}
    fwd, phases, feet = {}, {}, {}
    for side, offset, lat in (("l", 0.0, -1), ("r", 0.5, 1)):
        c = g / s + offset
        n = math.floor(c)
        ph = c - n
        phases[side] = ph

        def plant(nn, offset=offset, lat=lat):
            d = max(0.0, min(length, (nn - offset) * s + reach_d + 0.03 * scale))
            p, yw = route(d)
            a = math.radians(yw)
            w = 0.112 * scale * lat
            x, z = p[0] + w * math.cos(a), p[2] - w * math.sin(a)
            return x, (ground(x, z) if ground is not None else p[1]), z

        if ph < STANCE:
            fx, gy, fz = plant(n)
            fy = -(0.858 + 0.022 * math.sin(math.pi * ph / STANCE) * amp)
            up = 0.0
        else:
            q = (ph - STANCE) / (1 - STANCE)
            e = q * q * (3 - 2 * q)
            a0, a1 = plant(n), plant(n + 1)
            fx, gy, fz = (a0[i] + (a1[i] - a0[i]) * e for i in range(3))
            step = math.hypot(a1[0] - a0[0], a1[2] - a0[2])
            up = ((0.048 + 0.018 * amp) * min(1.0, step / (0.3 * s))
                  * math.sin(math.pi * min(1.0, q * 1.1)))
            fy = -0.858 + up
        fy += (gy - pos[1]) / scale
        dx, dz = fx - pos[0], fz - pos[2]
        lx = (dx * cy - dz * sy) / scale
        lz = (dx * sy + dz * cy) / scale
        hip, knee = leg_ik(lz, fy)
        pose[side + "hip_p"] = hip
        pose[side + "kn"] = knee
        out = max(-0.12, min(0.20, (lx - lat * 0.1) * lat / 0.86))
        pose[side + "hip_r"] = math.degrees(math.asin(out))
        fwd[side] = max(-1.0, min(1.0, lz / max(1e-6, reach_d / scale)))
        feet[side] = (fy, gy + up * scale)
    # Ground contact puts the lowest sole on pos.y; on a slope lift it onto
    # that foot's own ground instead.
    low = min(feet.values())
    pose["lift"] = low[1] - pos[1]
    sway = math.cos(2 * math.pi * (phases["l"] - 0.30))
    pose["body_r"] = 0.0
    pose["spine_r"] = -1.6 * sway * amp
    pose["twist"] = -pelvis * 1.7
    pose["head_y"] = -(pelvis + pose["twist"])
    pose["head_p"] = 0.0
    pose["spine"] = 4 + 2 * amp
    for side, other in (("l", "r"), ("r", "l")):
        pose[side + "sh_p"] = 10 + 19 * amp * fwd[other]
        pose[side + "sh_r"] = 7
        pose[side + "el"] = 16 + 14 * amp * max(0.0, fwd[other])
    return pose, pos, yaw


def walk_slip(hum, route, stride, speed=1.0, samples=200):
    """Worst horizontal drift of a planted ankle while it is stationary over
    the whole route -> {"l": m, "r": m}.  Stance is where consecutive samples
    move under 1 mm; a sliding contact would accumulate drift inside a run."""
    g0, g1 = walk_span(route.length, stride)
    prev = None
    runs = {"l": None, "r": None}
    worst = {"l": 0.0, "r": 0.0}

    def close(side):
        r = runs[side]
        if r is not None:
            worst[side] = max(worst[side],
                              math.hypot(r[1][0] - r[0][0], r[1][2] - r[0][2]))
            runs[side] = None

    for i in range(samples + 1):
        g = g0 + (g1 - g0) * i / samples
        pose, pos, yaw = walk(hum, route, g, stride, speed=speed)
        a = ankles(hum, pose, pos, yaw)
        if prev is not None:
            for side in "lr":
                d = math.hypot(a[side][0] - prev[side][0],
                               a[side][2] - prev[side][2])
                if d < 0.001:
                    if runs[side] is None:
                        runs[side] = [prev[side], a[side]]
                    else:
                        runs[side][1] = a[side]
                else:
                    close(side)
        prev = a
    for side in "lr":
        close(side)
    return worst


_SIT_LEGS = {}


def _sit_legs(u):
    d = 32.0 * u if u > 0 else 0.0     # thighs slope down to the knee
    s = -42.0 * u if u < 0 else 0.0    # shins reach forward
    hip = 90.0 - d
    return {"lhip_p": hip, "rhip_p": hip, "lkn": hip - s, "rkn": hip - s,
            # 1.5 deg splay = the walk's track width, so a rise steps off clean
            "lhip_r": 1.5, "rhip_r": 1.5, "body_p": 0.0, "body_r": 0.0,
            "lift": 0.0}


def _seat_contact(hum, pose):
    """Lowest point of the buttocks/rear thighs with the soles on y = 0."""
    places, _j, root = hum.pose_world(pose, (0.0, 0.0, 0.0), 0.0)
    uniq = hum._unique_verts()
    low = 1e9
    for _slot, key, M, org, _g, _fb in places:
        if key not in ("pelvis", "thigh"):
            continue
        for x, y, z in uniq[key]:
            if key == "thigh" and y < -0.25:
                continue
            low = min(low, M[3] * x + M[4] * y + M[5] * z + org[1])
    return low + root[1]


def sit_pose(hum, seat_y, upper=None):
    """Seated legs: rear thighs resting on a seat top ``seat_y`` m above the
    floor the soles stand on.  Upper-body keys come from ``upper``."""
    key = (id(hum), round(seat_y, 3))
    legs = _SIT_LEGS.get(key)
    if legs is None:
        lo, hi = -1.0, 1.0
        for _ in range(30):
            mid = 0.5 * (lo + hi)
            if _seat_contact(hum, _sit_legs(mid)) > seat_y:
                hi = mid
            else:
                lo = mid
        legs = _SIT_LEGS[key] = _sit_legs(0.5 * (lo + hi))
    p = dict(upper or {})
    p.update(legs)
    return p


def ankles(hum, pose, pos, yaw):
    """World ankle points of a posed actor -> {"l": xyz, "r": xyz}."""
    places, _j, root = hum.pose_world(pose, pos, yaw)
    out = {}
    for slot, key, _M, org, _g, _fb in places:
        if key == "foot":
            out["l" if slot == 9 else "r"] = (org[0] + root[0], org[1] + root[1],
                                              org[2] + root[2])
    return out


def knees(hum, pose, pos, yaw):
    """World knee points (shin origins) -> {"l": xyz, "r": xyz}."""
    places, _j, root = hum.pose_world(pose, pos, yaw)
    out = {}
    for slot, key, _M, org, _g, _fb in places:
        if key == "shin":
            out["l" if slot == 8 else "r"] = (org[0] + root[0], org[1] + root[1],
                                              org[2] + root[2])
    return out


def planted_pos(hum, pose, yaw, mid_xz, y=0.0):
    """Root that puts the ankle midpoint on ``mid_xz``: rises and crouches
    keep the feet where they are while the body travels over them."""
    a = ankles(hum, pose, (0.0, y, 0.0), yaw)
    return (mid_xz[0] - 0.5 * (a["l"][0] + a["r"][0]), y,
            mid_xz[1] - 0.5 * (a["l"][2] + a["r"][2]))


def reach(hum, pose, side, target, pos, yaw):
    """Arm IK onto a WORLD point for an actor drawn at (pos, yaw)."""
    from cutscenes.m5ending3d import solve_hand  # lazy: math + engine3d only
    p = dict(pose)
    p[side + "sh_y"] = 0.0
    _pl, _j, root = hum.pose_world(p, pos, yaw)
    dx, dy, dz = (target[i] - root[i] for i in range(3))
    a = math.radians(yaw)
    c, s = math.cos(a), math.sin(a)
    return solve_hand(hum, p, side, (dx * c - dz * s, dy, dx * s + dz * c))


# Blocking volumes per set, world AABBs ((x0, y0, z0), (x1, y1, z1)).  The set
# builders draw these exact boxes; the probe and the clearance tests read them.
SOLIDS = {
    "boxcar": {
        "seat_crate": ((-1.55, 0.0, 1.05), (-0.45, 0.40, 1.95)),
        "seat_lid": ((-1.60, 0.40, 1.00), (-0.40, 0.47, 2.00)),
        "stack_low": ((-1.70, 0.0, 2.10), (-0.80, 0.80, 3.00)),
        "stack_top": ((-1.55, 0.80, 2.20), (-0.85, 1.30, 2.90)),
        "wall_left": ((-1.75, 0.0, -4.0), (-1.65, 2.65, 4.0)),
        "wall_right_a": ((1.65, 0.0, -4.0), (1.75, 2.65, -1.40)),
        "wall_right_b": ((1.65, 0.0, 2.00), (1.75, 2.65, 4.0)),
        "lantern": ((0.44, 2.10, 1.44), (0.66, 2.40, 1.66)),
    },
    "terminal": {
        "desk_top": ((-2.70, 0.76, 1.15), (1.90, 0.88, 2.65)),
        "desk_side_l": ((-2.66, 0.0, 1.25), (-2.54, 0.78, 2.55)),
        "desk_side_r": ((1.74, 0.0, 1.25), (1.86, 0.78, 2.55)),
        "desk_back": ((-2.60, 0.03, 2.55), (1.80, 0.79, 2.65)),
        "crt": ((-1.35, 0.90, 1.37), (-0.45, 1.62, 2.13)),
        "radio": ((0.44, 0.88, 1.49), (1.06, 1.14, 1.91)),
        "chair_seat": ((-1.12, 0.41, 0.18), (-0.58, 0.51, 0.72)),
        "chair_back": ((-1.12, 0.46, 0.08), (-0.58, 1.30, 0.17)),
        "cabinet_a": ((-5.05, 0.0, 3.00), (-4.15, 2.0, 3.80)),
        "cabinet_b": ((-3.75, 0.0, 3.00), (-2.85, 2.0, 3.80)),
        "wall_back": ((-7.0, 0.0, 4.12), (7.0, 3.2, 4.28)),
    },
    # Local-space airframe parts: transform with ``heli_solids`` at query time.
    "heli": {
        "floor": ((-1.22, 0.50, -1.52), (1.22, 0.62, 1.92)),
        "roof": ((-1.22, 1.86, -1.52), (1.22, 2.36, 1.92)),
        "wall_l": ((-1.24, 0.58, -1.52), (-1.15, 2.02, 1.92)),
        "wall_r_rear": ((1.15, 0.58, -1.52), (1.24, 2.02, 0.25)),
        "wall_r_front": ((1.15, 0.58, 1.75), (1.24, 2.02, 1.92)),
        "door_header": ((1.15, 1.78, 0.25), (1.24, 2.02, 1.75)),
        "bulkhead_f": ((-1.22, 0.58, 1.84), (1.22, 1.94, 1.94)),
        "bulkhead_r": ((-1.22, 0.58, -1.52), (1.22, 1.94, -1.42)),
        "engine": ((-0.78, 2.22, -1.53), (0.78, 2.62, 0.63)),
        "boom": ((-0.28, 1.45, -8.05), (0.28, 1.99, -1.50)),
        "fin": ((-0.02, 1.52, -8.25), (0.52, 2.95, -7.85)),
        "skid_r": ((1.22, 0.045, -1.45), (1.38, 0.135, 2.30)),
        "skid_l": ((-1.38, 0.045, -1.45), (-1.22, 0.135, 2.30)),
        "door_panel": ((1.21, 0.60, -1.39), (1.27, 1.80, 0.07)),
    },
}


HELI_SILL_Y = 0.62
HELI_SKID_X = 1.30
HELI_SKID_Y = 0.135
HELI_DOOR_Z = 0.95
HELI_ROTOR_R = 6.2


def solids(set_key):
    return SOLIDS.get(set_key, {})


def _solid(r, lohi, col, **kw):
    from engine3d.core import box
    (x0, y0, z0), (x1, y1, z1) = lohi
    add(r, box(x1 - x0, y1 - y0, z1 - z0, col,
               center=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), **kw))


def _mesh_solid(m, lohi, col, **kw):
    from engine3d.core import box
    (x0, y0, z0), (x1, y1, z1) = lohi
    m.add(box(x1 - x0, y1 - y0, z1 - z0, col,
              center=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), **kw))


_BODY = ("pelvis", "torso", "head", "thigh", "shin", "foot")


def penetration(hum, pose, pos, yaw, boxes, parts=_BODY):
    """Deepest posed-body vertex inside any box -> (metres, part, box name);
    (0.0, None, None) when the body is clear."""
    places, _j, root = hum.pose_world(pose, pos, yaw)
    uniq = hum._unique_verts()
    worst = (0.0, None, None)
    items = list(boxes.items())
    for _slot, key, M, org, _g, _fb in places:
        if key not in parts:
            continue
        ox, oy, oz = org[0] + root[0], org[1] + root[1], org[2] + root[2]
        for x, y, z in uniq[key]:
            wx = M[0] * x + M[1] * y + M[2] * z + ox
            wy = M[3] * x + M[4] * y + M[5] * z + oy
            wz = M[6] * x + M[7] * y + M[8] * z + oz
            for name, (lo, hi) in items:
                d = min(wx - lo[0], hi[0] - wx, wy - lo[1], hi[1] - wy,
                        wz - lo[2], hi[2] - wz)
                if d > worst[0]:
                    worst = (d, key, name)
    return worst


def head_stats(surface, r=None, full=False):
    """Exposure of every face drawn in the last frame, read off the FINAL
    (graded) surface: [{key, mean, p95, facing, px}] with luma 0..255.
    ``facing`` is the cosine between the head's forward and the camera ray
    (1 = full face to lens, < 0 = back of the head).

    ``r`` defaults to the film renderer; pass the train's renderer with
    ``full=True`` to map the whole surface (no safe-area offset)."""
    import numpy as np
    if r is None:
        r = _cache.get("last_r")
    if r is None:
        return []
    arr = pygame.surfarray.array3d(surface).astype(np.float32)
    luma = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
    sw, sh = luma.shape
    top, bot = (0, sh) if full else (SAFE_TOP, SAFE_BOT)
    xk = surface.get_width() / float(r.w)
    yk = surface.get_height() / float(r.h)
    out = []
    for a in LAST:
        head = a["joints"].get("head")
        q = r.project(head) if head else None
        if q is None:
            continue
        scale = hum(a["key"])._scale
        cx, cy = (int(q[0] * xk), int(q[1] * yk)) if full else film_xy(q)
        rad = 0.06 * scale * r.focal / q[2] * xk
        if rad < 3:
            continue
        x0, x1 = max(0, int(cx - rad)), min(sw, int(cx + rad) + 1)
        y0, y1 = max(top, int(cy - rad)), min(min(sh, bot), int(cy + rad) + 1)
        if x1 <= x0 or y1 <= y0:
            continue
        xx, yy = np.mgrid[x0:x1, y0:y1]
        sel = luma[x0:x1, y0:y1][(xx - cx) ** 2 + (yy - cy) ** 2 <= rad * rad]
        if sel.size < 8:
            continue
        p = a["pose"]
        hy = math.radians(a["yaw"] + p.get("twist", 0.0) + p.get("head_y", 0.0))
        fwd = (math.sin(hy), math.cos(hy))
        dx, dz = r.cam[0] - head[0], r.cam[2] - head[2]
        n = math.hypot(dx, dz) or 1.0
        out.append({"key": a["key"], "mean": float(sel.mean()),
                    "p95": float(np.percentile(sel, 95)),
                    "facing": (fwd[0] * dx + fwd[1] * dz) / n, "px": rad})
    return out


# ── particles ─────────────────────────────────────────────────────────────
def _u(i, seed, salt=0.0):
    v = math.sin((i + 1) * 12.9898 + seed * 78.233 + salt * 37.719) * 43758.5453
    return v - math.floor(v)


def snow3d(r, t, seed=0, n=130, spread=18.0, height=14.0, speed=1.5,
           col=SNOW, near=0.0):
    """World-lattice snow around the camera; deterministic, dt-free."""
    cx, cy, cz = r.cam
    a = t * 0.001 * speed
    for i in range(n):
        u, v, w = _u(i, seed, 1), _u(i, seed, 2), _u(i, seed, 3)
        x = cx + (u * 2 - 1) * spread
        z = cz + (v * 2 - 1) * spread
        y = cy + height * 0.55 - ((a * (0.45 + 0.9 * w) + v * height) % height)
        ln = 0.10 + 0.16 * w
        c = col if w > near else (int(col[0] * .6), int(col[1] * .65), int(col[2] * .7))
        r.add_line3d((x, y, z), (x - 0.10 * ln, y - ln, z + 0.05 * ln), c, 1, layer=4)


def breath(pos, t, seed=0, intensity=0.22):
    """Cold-air breath: small alpha puffs rising and fading from the mouth."""
    puffs = [( _u(i, seed, 7), _u(i, seed, 8)) for i in range(4)]

    def draw(s, sx, sy, scale, z):
        if scale < 1.2:
            return
        life = 1400.0
        for ph, sp in puffs:
            age = ((t + ph * life) % life) / life
            if age < 0.03:
                continue
            rad = (0.035 + 0.11 * age) * scale * (0.8 + sp * 0.4)
            if rad < 1:
                continue
            a = int(90 * intensity / 0.22 * (1 - age) ** 1.5)
            if a < 3:
                continue
            key = (int(rad) // 2) * 2
            img = _cache["puff"].get(key)
            if img is None:
                rr = max(3, key)
                img = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
                for k in range(rr, 0, -1):
                    f = (1 - k / rr) ** 1.7
                    pygame.draw.circle(img, (188, 196, 208, int(70 * f)), (rr, rr), k)
                _cache["puff"][key] = img
            img = pygame.transform.scale(img, (max(2, int(rad * 2)),) * 2)
            img.set_alpha(min(255, a))
            s.blit(img, (int(sx - rad), int(sy - rad * 1.2 - age * 10)))

    return draw


# ── sky / light helpers ──────────────────────────────────────────────────
def night(r, buf, t, top=(5, 8, 15), bot=(18, 26, 42), stars=55, moon=False,
          sodium=(44, 30, 20), seed=0, star_cut=0.45):
    _fx.night_sky(r, buf, t, top, bot, stars=stars, moon=moon, clouds=3,
                  sodium=sodium, mist=(18, 22, 32), seed=seed, star_cut=star_cut)


def warm_lamp(r, pos, t, seed=0, radius_m=1.6, col=WARM, intensity=0.9):
    r.add_sprite(pos, _fx.glow(col, radius_m, t, flicker=0.05, seed=seed,
                               core=(255, 236, 200), intensity=intensity),
                 layer=_fx.FX_LAYER)
    r.add_sprite(pos, _fx.haze((255, 190, 130), radius_m * 2.2, t, seed=seed,
                               intensity=0.10), layer=_fx.FX_LAYER)
    k = min(1.0, radius_m / 1.1)
    r.add_sprite(pos, _fx.light_shaft((255, 188, 120), 2.1 * k, 0.25, 0.9, t, seed,
                                      intensity=0.12 * k), layer=_fx.FX_LAYER)


# ── insertion sets ───────────────────────────────────────────────────────
LZ = (0.0, -48.0)
LZ_Y = 17.0
TERRAIN_HALF = 77.5
TERRAIN_STEP = 155.0 / 28.0


def _s01(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3.0 - 2.0 * u)


def _smooth_ramp(u, a, b):
    """0 below ``a``, 1 above ``b``: linear with rounded ends."""
    p = max(0.0, min(1.0, (u - a) / float(b - a)))
    e = 0.16
    if p < e:
        q = p * p / (2 * e)
    elif p > 1 - e:
        q = 1 - e - (1 - p) * (1 - p) / (2 * e)
    else:
        q = p - e / 2
    return q / (1 - e)


def height_at(x, z):
    """Ground height of the insertion valley: border plain at 0, southern
    ridge crest ~17 m at the LZ shelf (z -48), rolling sides and a low
    northern rise behind the compound."""
    ridge = LZ_Y * _smooth_ramp(-z, 6.0, 52.0)
    north = 6.0 * _s01((z - 58.0) / 20.0)
    side = 6.0 * _s01((abs(x) - 46.0) / 26.0)
    roll = (0.55 * math.sin(x * 0.17 + 1.3) * math.cos(z * 0.13)
            + 0.35 * math.sin(x * 0.07 - z * 0.11))
    flat = _s01((math.hypot(x * 0.8, z - 8.0) - 22.0) / 30.0)
    return (ridge + north + side + roll) * flat


def _terrain_col(x, z, h, slope):
    lit = max(0.0, min(1.0, h / LZ_Y))
    base = (38 + 22 * lit, 46 + 24 * lit, 62 + 28 * lit)
    if slope > 0.55:
        k = min(1.0, (slope - 0.55) / 0.35)
        base = tuple(int(base[i] * (1 - k) + (28 + 3 * i) * k) for i in range(3))
    j = int(3.0 * math.sin(x * 0.91 + z * 1.27)) - 1
    return tuple(max(0, min(255, int(c) + j)) for c in base)


def _static_skip():
    """Inside a static batch, later frames skip rebuilding set geometry."""
    return _STATIC_BUILD["active"] and not _STATIC_BUILD["rebuild"]


def terrain(r, t, lights=True):
    """Snow ridge above the border: one 28x28 heightfield, rock on the steep
    faces, sparse pines, the border road and its sodium lamps."""
    from engine3d.core import Mesh, box, quad_xz
    if not _static_skip():
        m = Mesh()
        N = 28
        st = TERRAIN_STEP
        hs = [[height_at(-TERRAIN_HALF + i * st, -TERRAIN_HALF + j * st)
               for j in range(N + 1)] for i in range(N + 1)]
        for i in range(N):
            xa = -TERRAIN_HALF + i * st
            xb = xa + st
            for j in range(N):
                za = -TERRAIN_HALF + j * st
                zb = za + st
                ha, hb = hs[i][j], hs[i + 1][j]
                hc, hd = hs[i + 1][j + 1], hs[i][j + 1]
                slope = max(abs(hb - ha), abs(hd - ha), abs(hc - ha),
                            abs(hb - hd), abs(hc - hb), abs(hc - hd)) / st
                c = _terrain_col(xa + st / 2, za + st / 2,
                                 (ha + hb + hc + hd) / 4, slope)
                m.face([(xa, ha, za), (xa, hd, zb), (xb, hc, zb), (xb, hb, za)],
                       c, 0)
        add(r, m)
        # pines on the ridge, clear of the landing shelf
        rng = random.Random(9)
        pine = (17, 21, 27)
        for k in range(48):
            x = rng.uniform(-70, 70)
            z = rng.uniform(-75, -20)
            if math.hypot(x - LZ[0], z - LZ[1]) < 14.0:
                continue
            gy = height_at(x, z)
            if gy < 5.0:
                continue
            hh = rng.uniform(2.4, 4.8)
            rad = hh * rng.uniform(0.24, 0.31)
            base = [(x + math.cos(a) * rad, gy - 0.15, z + math.sin(a) * rad)
                    for a in (math.radians(90 + 72 * i) for i in range(5))]
            tip = (x, gy + hh, z)
            mm = Mesh()
            for i in range(5):
                mm.face([base[i], base[(i + 1) % 5], tip], pine, 2)
            add(r, mm)
        # border road cut and sodium lamp posts
        add(r, quad_xz(-34, 10, 34, 18, 0.03, (30, 33, 40), seg=8))
        if lights:
            for i, x in enumerate((-26, -13, 0, 13, 26)):
                z = 15.4
                y = height_at(x, z)
                add(r, box(0.08, 4.6, 0.08, (28, 30, 36), center=(x, y + 2.3, z)))
                add(r, box(0.16, 0.2, 0.16, (255, 186, 110),
                           center=(x, y + 4.5, z), emissive=True))
                add(r, quad_xz(x - 2.2, z - 1.8, x + 2.2, z + 1.8, 0.04,
                               (92, 72, 48), seg=2))
    if lights:
        for i, x in enumerate((-26, -13, 0, 13, 26)):
            z = 15.4
            y = height_at(x, z)
            r.add_sprite((x, y + 4.6, z),
                         _fx.sodium_lamp(t, seed=i, radius_m=2.4, intensity=0.6),
                         layer=_fx.FX_LAYER)
    snow3d(r, t, seed=11, n=56, spread=26, height=18, speed=1.1)


def hills(r, t, lights=True):
    """Kept for the train-facing helpers; the insertion uses ``terrain``."""
    return terrain(r, t, lights=lights)


_CAP_BLOCKS = (
    (-46, 62, 12, 14, 10), (-33, 68, 9, 21, 9), (-21, 58, 11, 10, 8),
    (-10, 66, 8, 26, 9), (2, 60, 13, 17, 10), (14, 70, 9, 23, 8),
    (25, 58, 10, 12, 9), (37, 66, 12, 19, 10), (50, 60, 9, 9, 8),
)


def capital(r, t):
    """Distant skyline: varied blocks, clustered lit windows, sodium dome and
    blinking aviation lights on the tall roofs."""
    from engine3d.core import box
    if not _static_skip():
        for i, (x, z, w, h, d) in enumerate(_CAP_BLOCKS):
            gy = height_at(x, z) - 0.5
            add(r, box(w, h, d, (26 + i % 3, 28 + i % 3, 37 + i % 4),
                       center=(x, gy + h / 2, z), seg=6))
            rng = random.Random(70 + i)
            for _ in range(rng.randint(7, 14)):
                wx = x + rng.uniform(-w * 0.36, w * 0.36)
                wy = gy + rng.uniform(0.18, 0.86) * h
                warm = rng.random() < 0.7
                add(r, box(0.45, 0.35, 0.10,
                           (255, 208, 142) if warm else (190, 206, 230),
                           center=(wx, wy, z - d / 2 - 0.02), emissive=True))
    for i, (x, z, w, h, d) in enumerate(_CAP_BLOCKS):
        if h >= 21 and int(t // 650 + i) % 2 == 0:
            gy = height_at(x, z) - 0.5
            r.add_sprite((x, gy + h + 0.4, z),
                         _fx.glow((255, 44, 36), 1.0, t, seed=i, intensity=0.9),
                         layer=_fx.FX_LAYER)
    r.add_sprite((2, 10, 66), _fx.haze((255, 170, 100), 44.0, t, seed=3,
                                       intensity=0.20), layer=_fx.FX_LAYER)
    r.add_sprite((0, 5, 62), _fx.window_glow((255, 176, 108), 36.0, 8.0, 0.10),
                 layer=_fx.FX_LAYER)


def dark_hills(r):
    """Low rounded ridge silhouettes beyond the capital, on the eastward
    turn.  Irregular profiles so they never read as walls."""
    from engine3d.core import prism
    if _static_skip():
        return
    for i, (x, z, w, h, d) in enumerate(((44, 98, 36, 21, 26),
                                         (70, 110, 44, 27, 30),
                                         (96, 102, 34, 18, 24))):
        prof = [(x - w, 0.0), (x - w * 0.58, h * 0.30),
                (x - w * 0.26, h * 0.66), (x - w * 0.04, h * 0.90),
                (x + w * 0.14, h), (x + w * 0.42, h * 0.62),
                (x + w * 0.74, h * 0.26), (x + w, 0.0)]
        add(r, prism(prof, d, (15 + i, 17 + i, 24 + i), z0=z - d / 2))


def border_compound(r, t, warm=1.0):
    """The customs post seen from the hills: fence, gate, hut, car queue."""
    from engine3d.core import box, quad_xz
    if not _static_skip():
        fence = (48, 52, 58)
        for x in range(-24, 25, 3):
            add(r, box(0.08, 2.0, 0.08, fence, center=(x, 1.0, 6.4)))
        for y in (0.55, 1.35, 1.95):
            add(r, box(48, 0.06, 0.06, fence, center=(0, y, 6.4)))
        # gate mouth and posts
        add(r, box(0.5, 2.8, 0.5, (66, 66, 70), center=(-2.4, 1.4, 6.4)))
        add(r, box(0.5, 2.8, 0.5, (66, 66, 70), center=(2.4, 1.4, 6.4)))
        add(r, box(4.2, 0.22, 0.24, (86, 84, 78), center=(0, 2.6, 6.4)))
        # guard hut with a lit window
        add(r, box(3.4, 2.5, 2.8, (52, 50, 48), center=(7.2, 1.25, 9.4), seg=4))
        add(r, box(3.0, 0.24, 3.1, (34, 34, 36), center=(7.2, 2.6, 9.4)))
        add(r, box(0.9, 0.7, 0.06, (255, 206, 140), center=(6.2, 1.55, 8.0),
                   emissive=True))
        # frozen queue: cars waiting since before the border closed
        for i, z in enumerate((11.6, 15.0, 18.4)):
            x = -14 + i * 0.4
            add(r, box(2.0, 0.85, 4.0, (34, 38, 44), center=(x, 0.55, z), seg=4))
            add(r, box(1.8, 0.55, 2.0, (24, 28, 34), center=(x, 1.2, z - 0.2), seg=4))
            add(r, box(1.86, 0.30, 0.06, (70, 80, 94),
                       center=(x, 1.18, z - 1.18), emissive=True))
        # work lamps
        for i, x in enumerate((-4.4, 4.4)):
            add(r, box(0.14, 5.6, 0.14, (40, 42, 48), center=(x, 2.8, 7.6)))
            add(r, box(0.5, 0.22, 0.34, (255, 214, 156), center=(x, 5.62, 7.55),
                       emissive=True))
            add(r, quad_xz(x - 3.4, 9.0, x + 3.4, 13.0, 0.04, (84, 68, 48), seg=4))
    r.add_sprite((6.2, 1.55, 7.9), _fx.window_glow((255, 196, 120), 0.8, 0.6,
                                                  intensity=0.55 * warm),
                 layer=_fx.FX_LAYER)
    for i, x in enumerate((-4.4, 4.4)):
        r.add_sprite((x, 5.6, 7.5), _fx.sodium_lamp(t, seed=20 + i, radius_m=3.4,
                                                    intensity=0.85),
                     layer=_fx.FX_LAYER)
    snow3d(r, t, seed=21, n=64, spread=22, height=16, speed=1.4)


def heli_xform(pos, yaw, bank=0.0, pitch=0.0, scale=1.0):
    """Local airframe point -> world.  Pitch tips the nose, bank rolls about
    the long axis, yaw turns; scale is applied first."""
    from engine3d.core import m_apply, rot_x, rot_y, rot_z
    x, y, z = pos
    S = scale

    def L(lx, ly, lz):
        v = m_apply(rot_x(pitch), (lx * S, ly * S, lz * S))
        v = m_apply(rot_z(bank), v)
        v = m_apply(rot_y(yaw), v)
        return (x + v[0], y + v[1], z + v[2])

    return L


def heli_solids(pos, yaw, bank=0.0, pitch=0.0, scale=1.0):
    """World AABBs of the airframe parts (SOLIDS["heli"] is local space)."""
    L = heli_xform(pos, yaw, bank, pitch, scale)
    out = {}
    for name, (lo, hi) in SOLIDS["heli"].items():
        pts = [L(px, py, pz) for px in (lo[0], hi[0])
               for py in (lo[1], hi[1]) for pz in (lo[2], hi[2])]
        out[name] = (tuple(min(p[i] for p in pts) for i in range(3)),
                     tuple(max(p[i] for p in pts) for i in range(3)))
    return out


def helicopter(r, t, pos, yaw=-18.0, rotor_speed=1.0, lit=True, scale=1.0,
               door=True, bank=0.0, pitch=0.0, blur=1.0):
    """Huey-like airframe: glazed nose, open right door, skids, tail boom and
    a translucent two-blade rotor blurred out to the blade radius.  ``blur``
    scales only the additive blur, so a distant airframe stays solid under it.
    Returns world anchors: door_sill (point, outward normal), skid_top_r, hub,
    belly, nose, rotor_radius, blur_radius."""
    from engine3d.core import Mesh, box, m_apply, prism, rot_x, rot_y, rot_z
    S = scale
    L = heli_xform(pos, yaw, bank, pitch, S)

    def place(mesh, bias=0.4):
        mesh.verts = [L(*v) for v in mesh.verts]
        add(r, mesh, bias=bias)

    hull, hull_d, dark, glass = (34, 38, 43), (25, 29, 34), (15, 17, 21), (9, 15, 26)
    body = Mesh()
    # cabin shell: floor/sill, arched roof, walls with the open right door
    body.add(box(2.44, 0.12, 3.44, hull_d), t=(0, 0.56, 0.20))
    body.add(prism([(-1.22, 1.86), (-1.04, 2.18), (-0.55, 2.34), (0.55, 2.34),
                    (1.04, 2.18), (1.22, 1.86)], 3.44, hull, seg=1.2),
             t=(0, 0, -1.52))
    body.add(box(0.09, 1.44, 3.44, hull), t=(-1.175, 1.30, 0.20))
    body.add(box(0.09, 1.44, 1.77, hull), t=(1.175, 1.30, -0.685))
    body.add(box(0.09, 1.44, 0.17, hull), t=(1.175, 1.30, 1.835))
    body.add(box(0.09, 0.24, 1.50, hull), t=(1.175, 1.90, 1.00))
    body.add(box(2.44, 1.30, 0.08, hull_d), t=(0, 1.24, -1.48))
    body.add(box(2.44, 1.30, 0.08, hull_d), t=(0, 1.24, 1.88))
    # seats along the left wall, visible through the door
    body.add(box(0.46, 0.09, 1.30, (22, 24, 27)), t=(-0.72, 0.70, 0.35))
    body.add(box(0.08, 0.50, 1.30, (20, 22, 25)), t=(-1.00, 0.98, 0.35))
    # cabin dome light: the red practical seen through the open door
    body.add(box(0.13, 0.05, 0.13, (255, 66, 46), center=(0.0, 2.19, 0.55),
                 emissive=True))
    if door:
        # the right-hand door slid back on its rail: dark pane, handle
        body.add(box(0.05, 1.20, 1.45, hull), t=(1.235, 1.20, -0.66))
        body.add(box(0.02, 0.50, 0.95, glass, emissive=True),
                 t=(1.265, 1.44, -0.66))
        body.add(box(0.04, 0.10, 0.18, dark), t=(1.27, 1.02, -0.02))
        body.add(box(0.04, 0.05, 2.80, dark), t=(1.22, 1.82, -0.10))
        body.add(box(0.05, 0.04, 1.50, (70, 74, 78)), t=(1.21, 0.63, 1.00))
    # nose: hull, chin, glazed windscreen and cockpit side panes
    body.add(box(2.06, 1.05, 1.05, hull), t=(0, 1.28, 2.38))
    body.add(box(1.66, 0.36, 0.92, hull_d), t=(0, 0.83, 2.46))
    body.add(box(2.00, 0.10, 1.05, hull), t=(0, 1.83, 2.38))
    body.face([(-0.82, 1.24, 2.87), (-0.06, 1.26, 2.93), (0.06, 1.26, 2.93),
               (0.82, 1.24, 2.87), (0.70, 1.78, 2.55), (-0.70, 1.78, 2.55)],
              glass, 2, True, True)
    body.add(box(0.05, 0.52, 0.06, dark), t=(0, 1.53, 2.76))
    for sx in (-1, 1):
        body.face([(sx * 1.035, 1.22, 2.10), (sx * 1.035, 1.22, 2.60),
                   (sx * 1.035, 1.72, 2.52), (sx * 1.035, 1.72, 2.14)],
                  glass, 2, True, True)
    # engine cowling, intake, exhaust, mast
    body.add(box(1.55, 0.40, 2.15, hull_d), t=(0, 2.42, -0.45))
    body.add(box(1.10, 0.16, 0.06, dark), t=(0, 2.46, 0.64))
    body.add(box(0.28, 0.26, 0.55, dark), t=(0.62, 2.36, -1.48))
    body.add(box(0.18, 0.50, 0.18, dark), t=(0, 2.79, 0.15))
    body.add(box(0.30, 0.18, 0.30, dark), t=(0, 3.02, 0.15))
    # tail boom, fairing, stabiliser, swept fin
    body.add(box(0.54, 0.54, 5.60, hull), t=(0, 1.72, -4.30))
    body.add(box(0.38, 0.38, 1.00, hull_d), t=(0, 1.80, -7.55))
    body.add(box(0.36, 0.10, 5.40, hull_d), t=(0, 2.02, -4.25))
    body.add(box(1.70, 0.07, 0.46, dark), t=(0, 1.78, -7.05))
    body.add(prism([(-0.02, 1.52), (0.30, 1.52), (0.52, 2.20), (0.34, 2.95),
                    (-0.02, 2.90)], 0.40, hull_d), t=(0, 0, -8.25))
    # skids: tubes with upturned toes, cross tubes and belly struts
    for sx in (-1, 1):
        body.add(box(0.09, 0.09, 3.60, dark), t=(sx * HELI_SKID_X, 0.09, 0.35))
        body.add(box(0.09, 0.09, 0.70, dark), m=rot_x(-24),
                 t=(sx * HELI_SKID_X, 0.13, 2.45))
        for zz in (-0.55, 0.95):
            body.add(box(0.07, 0.20, 0.07, dark), t=(sx * HELI_SKID_X, 0.235, zz))
            body.add(box(0.07, 0.18, 0.07, dark), t=(sx * 0.95, 0.43, zz))
    for zz in (-0.55, 0.95):
        body.add(box(2.72, 0.075, 0.075, dark), t=(0, 0.36, zz))
    place(body)

    # main rotor: one bar = two blades of radius R, readable 140 deg/s
    spin = (t * 0.001 * 140.0 * rotor_speed) % 360.0
    rotor = Mesh()
    rotor.add(box(2 * HELI_ROTOR_R, 0.045, 0.30, (13, 15, 18)),
              m=rot_y(spin), t=(0, 3.03, 0.15))
    rotor.add(box(0.20, 0.06, 0.34, (22, 24, 28)), m=rot_y(spin),
              t=(HELI_ROTOR_R - 0.10, 3.03, 0.15))
    rotor.add(box(0.20, 0.06, 0.34, (22, 24, 28)), m=rot_y(spin),
              t=(-HELI_ROTOR_R + 0.10, 3.03, 0.15))
    place(rotor)
    tr_spin = (t * 0.001 * 620.0 * rotor_speed) % 360.0
    tail = Mesh()
    tail.add(box(0.05, 2.30, 0.10, (14, 16, 20)), m=rot_x(tr_spin),
             t=(-0.30, 2.20, -8.05))
    tail.add(box(0.12, 0.14, 0.14, dark), t=(-0.30, 2.20, -8.05))
    place(tail)

    # rotor blur: one inner disc at the hub, eight outer sectors at 0.78R, so
    # every sprite stays inside the GL depth-reach box of its anchor
    hub = L(0.0, 3.03, 0.15)

    def rim(rad, a):
        return L(math.cos(a) * rad, 3.03, 0.15 + math.sin(a) * rad)

    def poly_img(pts, col):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x0, y0 = int(min(xs)) - 2, int(min(ys)) - 2
        w, h = int(max(xs)) + 2 - x0, int(max(ys)) + 2 - y0
        if not (0 < w < 3000 and 0 < h < 3000):
            return None
        img = pygame.Surface((max(1, w), max(1, h)))
        img.fill((0, 0, 0))
        pygame.draw.polygon(img, col, [(p[0] - x0, p[1] - y0) for p in pts])
        return img, x0, y0

    def sane(pp):
        return all(pp) and all(-2500 < p[0] < 2500 and -1500 < p[1] < 1500
                               for p in pp)

    def dim(col):
        return tuple(max(0, min(255, int(v * blur))) for v in col)

    def add_blur(anchor, img_xy):
        if img_xy is None:
            return
        img, x0, y0 = img_xy

        def draw(s, sx, sy, scale_, z):
            s.blit(img, (x0, y0), special_flags=pygame.BLEND_ADD)

        r.add_sprite(anchor, draw, layer=_fx.FX_LAYER)

    blur_radius = 0.0
    inner_pts = [rim(3.25, 2 * math.pi * i / 24.0) for i in range(24)]
    pin = [r.project(p) for p in inner_pts]
    if sane(pin):
        inner = poly_img(pin, dim((4, 5, 6)))
        mid_pts = [rim(1.75, 2 * math.pi * i / 16.0) for i in range(16)]
        pmid = [r.project(p) for p in mid_pts]
        if sane(pmid):
            pygame.draw.polygon(inner[0], dim((2, 3, 4)),
                                [(p[0] - inner[1], p[1] - inner[2]) for p in pmid])
        add_blur(hub, inner)
        blur_radius = max(math.dist(p, hub) for p in inner_pts)
    for k in range(8):
        a0 = 2 * math.pi * k / 8.0
        a1 = 2 * math.pi * (k + 1) / 8.0
        pts = [rim(HELI_ROTOR_R, a0 + (a1 - a0) * u / 4.0) for u in range(5)]
        pts += [rim(3.25, a1 + (a0 - a1) * u / 4.0) for u in range(5)]
        pp = [r.project(p) for p in pts]
        anchor = rim(0.78 * HELI_ROTOR_R, (a0 + a1) / 2.0)
        if sane(pp):
            add_blur(anchor, poly_img(pp, dim((5, 6, 7))))
            blur_radius = max(blur_radius,
                              max(math.dist(p, hub) for p in pts))
    # the blade-tip path is the one bright part of the blur
    for k in range(8):
        a0 = 2 * math.pi * k / 8.0
        a1 = 2 * math.pi * (k + 1) / 8.0
        pts = [rim(HELI_ROTOR_R, a0 + (a1 - a0) * u / 3.0) for u in range(4)]
        pts += [rim(HELI_ROTOR_R - 0.30, a1 + (a0 - a1) * u / 3.0)
                for u in range(4)]
        pp = [r.project(p) for p in pts]
        anchor = rim(0.97 * HELI_ROTOR_R, (a0 + a1) / 2.0)
        if sane(pp):
            add_blur(anchor, poly_img(pp, dim((6, 7, 8))))

    if lit:
        for sx, col, seed in ((-1.0, (255, 46, 38), 3), (1.0, (42, 224, 96), 4)):
            r.add_sprite(L(sx * 1.06, 1.28, 2.55),
                         _fx.glow(col, 0.30, t, pulse=0.15, seed=seed,
                                  intensity=0.85), layer=_fx.FX_LAYER)
        r.add_sprite(L(0.30, 2.90, -8.05),
                     _fx.glow((255, 248, 226), 0.22, t, seed=5, intensity=0.7),
                     layer=_fx.FX_LAYER)
        if int(t // 700) % 2 == 0:
            r.add_sprite(L(0.0, 2.98, -7.70),
                         _fx.glow((255, 40, 32), 0.45, t, seed=6,
                                  intensity=1.0), layer=_fx.FX_LAYER)
        r.add_sprite(L(0.0, 2.18, 0.55),
                     _fx.glow((255, 70, 52), 0.30, t, seed=7, flicker=0.10,
                              intensity=0.55), layer=_fx.FX_LAYER)
    normal = (m_apply(rot_y(yaw), m_apply(rot_z(bank),
              m_apply(rot_x(pitch), (1.0, 0.0, 0.0)))))
    return {
        "door_sill": (L(1.20, HELI_SILL_Y, HELI_DOOR_Z), normal),
        "skid_top_r": L(HELI_SKID_X, HELI_SKID_Y, HELI_DOOR_Z),
        "hub": hub,
        "belly": L(0.0, 0.46, 0.30),
        "nose": L(0.0, 1.25, 2.92),
        "rotor_radius": HELI_ROTOR_R * S,
        "blur_radius": blur_radius,
    }


# ── boxcar interior ──────────────────────────────────────────────────────
_BOX = dict(wood=(50, 40, 30), rib=(38, 30, 24), floor=(34, 29, 24),
            roof=(30, 26, 22), dark=(14, 14, 16), crate=(58, 46, 32))


LANTERN = (0.55, 2.25, 1.55)


def _boxcar_dressing(m, L, Wd, H):
    """Lived-in freight-car clutter: straw, sacks, a stove, chains, stencils.

    Painted into the set mesh only - nothing here is a collision solid, and
    every piece sits on the floor or flat against the -x wall so no actor,
    no route and no lens can clip it.
    """
    from engine3d.core import box, quad_xz
    wall = -Wd / 2
    # Floor planks: seams along the car so the deck is not one flat quad.
    for i in range(8):
        x = -Wd / 2 + 0.22 + i * 0.42
        m.add(box(0.014, 0.010, L - 0.3, (24, 20, 16), center=(x, 0.006, 0)))
    # Horizontal plank lines on the long -x wall.
    for y in (0.42, 0.86, 1.30, 1.74, 2.18):
        m.add(box(0.012, 0.020, L - 0.2, (36, 29, 22),
                  center=(wall + 0.06, y, 0)))
    # Stencilled freight marks: chalk-white blocks of lettering.
    for i, (z, h) in enumerate(((-1.05, 0.16), (-0.55, 0.10), (0.30, 0.14))):
        m.add(box(0.010, h, 0.42 - i * 0.06, (118, 110, 92),
                  center=(wall + 0.065, 1.62, z)))
    m.add(box(0.010, 0.34, 0.020, (118, 110, 92), center=(wall + 0.065, 1.30, 0.86)))
    m.add(box(0.010, 0.020, 0.34, (118, 110, 92), center=(wall + 0.065, 1.30, 0.69)))
    # A coat on a nail, and a coil of rope beside it.
    m.add(box(0.10, 0.52, 0.30, (40, 38, 34), center=(wall + 0.12, 1.28, 1.62)))
    m.add(box(0.06, 0.10, 0.26, (32, 30, 28), center=(wall + 0.13, 1.54, 1.62)))
    for i in range(3):
        m.add(box(0.05, 0.26, 0.26, (58, 52, 40),
                  center=(wall + 0.14, 1.66 - i * 0.05, -2.05)))
    # Straw strewn where the car was last swept out.
    straw = (88, 76, 46)
    for i in range(16):
        u = ((i * 37) % 100) / 100.0
        v = ((i * 61) % 100) / 100.0
        x = -1.35 + u * 2.5
        z = -3.4 + v * 5.6
        if -0.9 < x < 0.6 and 0.4 < z < 2.2:
            continue                      # keep the actors' floor clear
        m.add(quad_xz(x, z, x + 0.05, z + 0.22 + (i % 3) * 0.06, 0.012, straw))
    # Sacks in the dark corner.
    for i, (x, z, y) in enumerate(((-1.30, -3.35, 0.22), (-0.86, -3.45, 0.20),
                                   (-1.08, -3.40, 0.58))):
        m.add(box(0.44, 0.40, 0.50, (76, 68, 54), center=(x, y, z), seg=2))
        m.add(box(0.46, 0.05, 0.52, (58, 52, 42), center=(x, y + 0.20, z)))
    # A tarpaulin thrown over the crate stack.
    m.add(box(0.78, 0.04, 0.84, (46, 50, 44), center=(-1.20, 1.33, 2.55)))
    m.add(box(0.80, 0.16, 0.06, (42, 46, 40), center=(-1.20, 1.26, 2.96)))
    # Iron stove against the wall, with its flue up to the roof.
    m.add(box(0.42, 0.56, 0.42, (44, 42, 40), center=(wall + 0.30, 0.28, -1.40)))
    m.add(box(0.30, 0.05, 0.03, (150, 74, 40), center=(wall + 0.30, 0.22, -1.19),
              emissive=True))
    m.add(box(0.44, 0.05, 0.44, (58, 56, 54), center=(wall + 0.30, 0.58, -1.40)))
    m.add(box(0.12, H - 0.60, 0.12, (34, 34, 36),
              center=(wall + 0.30, (H + 0.60) / 2, -1.40)))
    # Chains and a bucket hook under the roof.
    for i, z in enumerate((-3.20, -2.55)):
        m.add(box(0.05, 1.10 - i * 0.12, 0.05, (34, 34, 38),
                  center=(0.95, H - 0.55 - i * 0.06, z)))
    m.add(box(0.28, 0.30, 0.28, (54, 56, 60), center=(-1.32, 0.15, -2.60)))
    m.add(box(0.30, 0.04, 0.30, (74, 76, 80), center=(-1.32, 0.30, -2.60)))
    # A lantern bracket by the door and a boot scraper on the threshold.
    m.add(box(0.22, 0.03, 0.03, (40, 40, 44), center=(Wd / 2 - 0.15, 2.05, -1.30)))
    m.add(box(0.12, 0.16, 0.12, (255, 206, 146), center=(Wd / 2 - 0.26, 1.96, -1.30),
              emissive=True))
    m.add(box(0.44, 0.06, 0.16, (52, 54, 58), center=(Wd / 2 - 0.34, 0.03, 0.10)))


def boxcar_interior(r, t, lantern=1.0, door_open=1.0, snow=1.0, glow=1.1):
    """Interior set. Door in the +x wall over z=-1.4..2.0 (open to the yard).
    ``glow`` is the lantern flare radius: keep it small in close-ups.
    Returns the lantern world position.  One merged mesh per frame: the local
    lantern/door lights still shade every face, but the packer sees one call."""
    from engine3d.core import Mesh, box, quad_xz
    m = Mesh()
    L, Wd, H = 8.0, 3.4, 2.65
    m.add(quad_xz(-Wd / 2, -L / 2, Wd / 2, L / 2, 0.0, _BOX["floor"], seg=4))
    m.add(box(Wd, 0.12, L, _BOX["roof"], center=(0, H, 0), seg=4))
    # long walls, with the right wall open on the door span
    m.add(box(0.10, H, L, _BOX["wood"], center=(-Wd / 2, H / 2, 0), seg=4))
    m.add(box(0.10, H, 2.6, _BOX["wood"], center=(Wd / 2, H / 2, -2.7), seg=4))
    m.add(box(0.10, H, 2.0, _BOX["wood"], center=(Wd / 2, H / 2, 3.0), seg=4))
    m.add(box(0.10, 0.5, L, _BOX["wood"], center=(Wd / 2, H - 0.25, 0), seg=4))
    # end walls
    for z in (-L / 2, L / 2):
        m.add(box(Wd, H, 0.10, _BOX["wood"], center=(0, H / 2, z), seg=4))
    # vertical ribs
    for z in (-3.4, -2.2, -1.0, 0.2, 1.4, 2.6, 3.6):
        for x in (-Wd / 2 + 0.09,):
            m.add(box(0.08, H - 0.2, 0.12, _BOX["rib"], center=(x, H / 2, z)))
        if not (-1.0 < z < 2.1):
            m.add(box(0.08, H - 0.2, 0.12, _BOX["rib"],
                      center=(Wd / 2 - 0.09, H / 2, z)))
    # sliding door leaf, parked left of the opening
    m.add(box(0.12, 2.2, 1.6, (46, 38, 30),
              center=(Wd / 2 + 0.16, 1.1, -2.4), seg=3))
    if door_open > 0.1:
        # cold night outside: snow ground, yard lights, a distant mast
        m.add(quad_xz(Wd / 2 + 0.2, -4.5, Wd / 2 + 16, 4.5, -0.02,
                      (54, 64, 82), seg=6))
        m.add(box(0.14, 4.2, 0.14, (34, 36, 42),
                  center=(Wd / 2 + 6.0, 2.1, 2.4)))
        m.add(box(0.4, 0.18, 0.3, (255, 208, 150),
                  center=(Wd / 2 + 6.0, 4.2, 2.35), emissive=True))
    # crates: Volkov's seat (lid overhangs the box) and a stack against the wall
    S = SOLIDS["boxcar"]
    _mesh_solid(m, S["seat_crate"], _BOX["crate"], seg=2)
    _mesh_solid(m, S["seat_lid"], (70, 56, 40))
    _mesh_solid(m, S["stack_low"], _BOX["crate"], seg=2)
    _mesh_solid(m, S["stack_top"], (64, 50, 36), seg=2)
    # ── lived-in dressing ────────────────────────────────────────────────
    # The close-ups shoot into the -x wall, so a bare plank backdrop read as
    # an empty stage.  Everything here is low or against a wall: no solid is
    # added, no actor or lens is crossed.
    _boxcar_dressing(m, L, Wd, H)
    # hanging lantern, high under the roof: a key, not a face-level flare
    lx, ly, lz = LANTERN
    m.add(box(0.02, 2.59 - (ly + 0.15), 0.02, (26, 26, 28),
              center=(lx, (2.59 + ly + 0.15) / 2, lz)))
    m.add(box(0.20, 0.24, 0.20, (255, 214, 150), center=LANTERN, emissive=True))
    m.add(box(0.24, 0.05, 0.24, (60, 50, 40), center=(lx, ly + 0.15, lz)))
    m.add(box(0.22, 0.04, 0.22, (60, 50, 40), center=(lx, ly - 0.13, lz)))
    add(r, m)
    if door_open > 0.1:
        r.add_sprite((Wd / 2 + 6.0, 4.2, 2.3),
                     _fx.sodium_lamp(t, seed=33, radius_m=2.6, intensity=0.65),
                     layer=_fx.FX_LAYER)
        r.add_sprite((Wd / 2 + 0.9, 1.3, 0.4),
                     _fx.window_glow((110, 140, 180), 1.2, 2.0, 0.22),
                     layer=_fx.FX_LAYER)
        if snow and r.cam[0] > Wd / 2:
            snow3d(r, t, seed=41, n=24, spread=9, height=7, speed=0.9)
        elif snow:
            # snow lines paint over every face; from inside, only the yard
            # beyond the door may show it, so use a depth-masked sprite
            r.add_sprite((Wd / 2 + 1.4, 1.2, 0.3),
                         _fx.dust_motes(t, seed=41, count=36, spread_m=(1.3, 1.1),
                                        col=(196, 206, 224)),
                         layer=_fx.FX_LAYER)
    if lantern:
        warm_lamp(r, LANTERN, t, seed=5, radius_m=glow, intensity=0.7 * lantern)
    return LANTERN


# ── rail platform / terminal / office ───────────────────────────────────
def _train_detail_mesh():
    """Cached local-space passenger train: body, real door hole, windows,
    livery, underframe, roof, lit vestibule and markers.  Rail platform is
    train-scene-only; the interactive scene rebuilds it every cinematic frame,
    so the mesh is built once and translated by ``train_offset``."""
    m = _cache.get("train_detail")
    if m is not None:
        return m
    from engine3d.core import Mesh, box
    m = Mesh()
    add = m.add
    BODY = (30, 35, 43)
    SKIRT = (20, 23, 28)
    STRIPE = (104, 86, 56)
    ROOF = (40, 47, 58)
    SEAM = (17, 19, 23)
    FRAME = (16, 18, 22)
    # Body split around a real 1.6 x 1.65 doorway at local x=10.9.
    add(box(33.1, 3.1, 3.0, BODY, center=(-6.45, 1.85, -4.4), seg=8))
    add(box(11.3, 3.1, 3.0, BODY, center=(17.35, 1.85, -4.4), seg=4))
    add(box(1.6, 0.70, 3.0, BODY, center=(10.9, 3.05, -4.4)))
    add(box(1.6, 0.75, 3.0, BODY, center=(10.9, 0.675, -4.4)))
    add(box(46, 0.5, 3.2, (24, 28, 34), center=(0, 3.55, -4.4), seg=8))
    # Livery, skirt and panel seams.
    for x0, x1 in ((-23.0, 10.1), (11.7, 23.0)):
        cx, w = (x0 + x1) * 0.5, x1 - x0
        add(box(w, 0.10, 0.03, STRIPE, center=(cx, 1.45, -2.885)))
        add(box(w, 0.30, 0.04, SKIRT, center=(cx, 0.45, -2.885)))
        add(box(w, 0.02, 0.02, SEAM, center=(cx, 2.00, -2.895)))
    for sx in (-22.5, -19.5, -16.5, -13.5, -10.5, -7.5, -4.5, -1.5,
               1.5, 4.5, 7.5, 13.5, 16.5, 19.5):
        add(box(0.03, 3.1, 0.02, SEAM, center=(sx, 1.85, -2.895)))
    # Window row: frames, two panes, mullion, snow sill.  Skip x=12: the
    # frame would overlap the doorway.  Warm/dim/cool panes vary by index.
    for i, wx in enumerate(range(-21, 22, 3)):
        if wx == 12:
            continue
        pane = ((232, 196, 144) if i % 5 else (154, 120, 88)) \
            if i % 7 else (150, 176, 196)
        add(box(1.56, 0.96, 0.05, FRAME, center=(wx, 2.45, -2.885)))
        add(box(0.64, 0.78, 0.03, pane, center=(wx - 0.34, 2.45, -2.855),
                emissive=True))
        add(box(0.64, 0.78, 0.03, pane, center=(wx + 0.34, 2.45, -2.855),
                emissive=True))
        add(box(0.05, 0.82, 0.04, FRAME, center=(wx, 2.45, -2.848)))
        add(box(1.70, 0.06, 0.12, (150, 162, 180),
                center=(wx, 1.94, -2.842)))
    # Door frame + vestibule.  The leaves themselves are animated in train3d.
    add(box(1.60, 1.65, 0.06, (54, 38, 26), center=(10.9, 1.85, -3.28)))
    add(box(1.20, 0.05, 0.10, (255, 214, 150),
            center=(10.9, 2.72, -3.12), emissive=True))
    for jx in (10.06, 11.74):
        add(box(0.08, 1.65, 0.40, (30, 22, 18), center=(jx, 1.85, -3.06)))
    add(box(1.80, 0.10, 0.10, (26, 28, 32), center=(10.9, 2.73, -2.92)))
    for jx in (10.04, 11.76):
        add(box(0.10, 1.75, 0.10, (26, 28, 32), center=(jx, 1.85, -2.92)))
    add(box(1.80, 0.06, 0.55, (60, 58, 54), center=(10.9, 0.98, -2.65)))
    # Underframe, bogies, wheels; the consist used to float 0.3 m up.
    add(box(46, 0.22, 2.6, (14, 15, 18), center=(0, 0.19, -4.4)))
    for bx in (-14.0, 0.0, 14.0):
        add(box(2.4, 0.30, 2.0, (24, 26, 30), center=(bx, 0.35, -4.4)))
        for wz in (-2.98, -5.82):
            add(box(0.55, 0.55, 0.16, (18, 18, 20), center=(bx, 0.30, wz)))
            add(box(0.20, 0.20, 0.03, (70, 66, 56),
                    center=(bx, 0.30, wz + (0.08 if wz > -4.4 else -0.08))))
    # Roof drip rail, snow lip and vents.
    add(box(46, 0.08, 0.12, ROOF, center=(0, 3.82, -2.92)))
    add(box(46, 0.05, 0.20, (150, 162, 180), center=(0, 3.86, -2.94)))
    for vx in (-15.0, -5.0, 5.0, 15.0):
        add(box(0.5, 0.12, 0.6, ROOF, center=(vx, 3.84, -4.4)))
    # Tail lamp (rear) and white marker.
    add(box(0.14, 0.14, 0.14, (228, 56, 42), center=(-23.02, 2.0, -2.90),
            emissive=True))
    add(box(0.12, 0.12, 0.12, (255, 240, 210), center=(23.02, 2.0, -2.90),
            emissive=True))
    _cache["train_detail"] = m
    return m


def _train_detail(r, tx):
    m = _train_detail_mesh()
    if abs(tx) < 1e-6:
        add(r, m)
        return
    from engine3d.core import Mesh
    shifted = Mesh()
    shifted.verts = [(v[0] + tx, v[1], v[2]) for v in m.verts]
    shifted.faces = list(m.faces)
    add(r, shifted)


def rail_platform(r, t, train=True, snow=1.0, train_offset=0.0):
    from engine3d.core import box, quad_xz
    add(r, quad_xz(-40, -40, 40, 40, 0.0, (52, 60, 74), seg=12))
    # ballast + rails
    add(r, quad_xz(-30, -2.0, 30, 2.6, 0.06, (40, 40, 44), seg=8))
    for z in (-1.5, 1.5):
        add(r, box(60, 0.10, 0.10, (86, 88, 92), center=(0, 0.16, z)))
        for x in range(-28, 29, 2):
            add(r, box(0.4, 0.08, 1.9, (58, 50, 40), center=(x, 0.10, 0)))
    # platform
    add(r, box(42, 0.55, 5.0, (62, 66, 74), center=(0, 0.28, 5.2), seg=6))
    add(r, box(42, 0.06, 0.5, (110, 108, 96), center=(0, 0.58, 2.95)))
    # broken snow patches on the catch-side ballast
    for dx, dz, dw in ((8.6, 2.20, 0.9), (10.8, 2.35, 1.2),
                       (12.6, 2.10, 0.8), (14.2, 2.40, 1.0)):
        add(r, box(dw, 0.02, 0.5, (150, 162, 180),
                   center=(dx, 0.068, dz)))
    if train:
        # Waiting passenger train.  The body/detail mesh is cached and only
        # translated by the departure offset; the glows stay sprites.
        tx = float(train_offset)
        _train_detail(r, tx)
        for cx in (-12.0, 0.0, 9.0, 15.0, 21.0):
            r.add_sprite((tx + cx, 2.45, -2.80),
                         _fx.window_glow((255, 198, 128), 4.2, 1.2, 0.20),
                         layer=_fx.FX_LAYER)
        for sx in (6.0, 11.0, 16.0):
            r.add_sprite((tx + sx, 0.10, -2.45),
                         _fx.window_glow((255, 180, 110), 2.4, 0.6, 0.16),
                         layer=_fx.FX_LAYER)
        r.add_sprite((tx + 10.9, 1.85, -2.80),
                     _fx.window_glow((255, 196, 130), 1.2, 1.4, 0.22),
                     layer=_fx.FX_LAYER)
        r.add_sprite((tx - 23.02, 2.0, -2.80),
                     _fx.glow((228, 56, 42), 0.35, t, intensity=0.55),
                     layer=_fx.FX_LAYER)
    # signal tower + floodlight masts
    add(r, box(1.2, 7.0, 1.2, (44, 46, 50), center=(18, 3.5, 8.5), seg=3))
    add(r, box(2.2, 1.6, 2.0, (54, 56, 60), center=(18, 7.8, 8.5), seg=3))
    add(r, box(1.2, 0.7, 0.06, (255, 206, 140), center=(18, 7.8, 7.45),
               emissive=True))
    # Ladder up the near face, roof rail and a red beacon: without them the
    # tower shot is a featureless box and the removed scope glint leaves
    # nothing to read.
    for ry in range(8):
        add(r, box(0.50, 0.04, 0.04, (62, 66, 74),
                   center=(18.0, 0.9 + ry * 0.78, 7.86)))
    for rx in (17.78, 18.22):
        add(r, box(0.04, 6.6, 0.04, (52, 56, 64),
                   center=(rx, 3.6, 7.86)))
    for px, pz in ((16.95, 7.55), (19.05, 7.55),
                   (16.95, 9.45), (19.05, 9.45)):
        add(r, box(0.05, 0.50, 0.05, (58, 62, 70),
                   center=(px, 8.85, pz)))
    add(r, box(2.20, 0.04, 0.04, (58, 62, 70), center=(18, 9.05, 7.55)))
    add(r, box(2.20, 0.04, 0.04, (58, 62, 70), center=(18, 9.05, 9.45)))
    add(r, box(0.12, 0.12, 0.12, (228, 56, 42),
               center=(19.0, 8.72, 7.9), emissive=True))
    r.add_sprite((19.0, 8.72, 7.9), _fx.glow((240, 70, 50), 0.45, t,
                                             intensity=0.50),
                 layer=_fx.FX_LAYER)
    for i, x in enumerate((-18, -6, 6, 18)):
        add(r, box(0.18, 8.0, 0.18, (38, 40, 46), center=(x, 4.0, 11.5)))
        add(r, box(0.7, 0.26, 0.5, (255, 226, 178), center=(x, 8.0, 11.4),
                   emissive=True))
        r.add_sprite((x, 8.0, 11.3), _fx.sodium_lamp(t, seed=50 + i,
                                                     radius_m=3.6,
                                                     intensity=0.55),
                     layer=_fx.FX_LAYER)
        r.add_sprite((x, 0.6, 8.0), _fx.haze((220, 210, 190), 4.0, t,
                                             seed=50 + i, intensity=0.10),
                     layer=_fx.FX_LAYER)
    if snow:
        snow3d(r, t, seed=61, n=120, spread=22, height=16, speed=1.3)


def window_snow3d(r, t, center, hw, hh, seed=0, n=46):
    """Snow beyond a window plane facing -z, as a depth-masked sprite: anyone
    standing in front of the glass occludes it (``window_snow`` cannot)."""
    corners = []
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        q = r.project((center[0] + sx * hw, center[1] + sy * hh, center[2]))
        if q is None:
            return
        corners.append((q[0], q[1]))
    (blx, bly), (brx, bry), (tlx, tly), (trx, try_) = corners
    rng = random.Random(seed + 31)
    dots = [(rng.random(), rng.random()) for _ in range(n)]

    def draw(s, sx, sy, scale, z):
        for i, (u, v) in enumerate(dots):
            w = 1.0 - ((v + t * 0.00006 * (0.5 + u)) % 1.0)
            x = (blx + (brx - blx) * u) * (1 - w) + (tlx + (trx - tlx) * u) * w
            y = (bly + (bry - bly) * u) * (1 - w) + (tly + (try_ - tly) * u) * w
            a = 90 + int(70 * u)
            s.fill((190 * a // 255, 200 * a // 255, 216 * a // 255),
                   (int(x), int(y), 1 + (i % 2), 1))

    r.add_sprite((center[0], center[1], center[2] - 0.05), draw, layer=_fx.FX_LAYER)


def _handset_rest(m):
    """Handset in its cradle on top of the radio set, cord to the jack."""
    from engine3d.core import box
    col, cap = (64, 70, 52), (48, 52, 40)
    m.add(box(0.20, 0.034, 0.040, col, center=(0.75, 1.160, 1.66)))
    for x in (0.64, 0.86):
        m.add(box(0.072, 0.056, 0.066, cap, center=(x, 1.170, 1.66)))
    for i in range(1, 13):
        u = i / 13.0
        if u < 0.6:
            q = u / 0.6
            c = (0.61 - 0.08 * q, 1.165, 1.66 - 0.19 * q)
        else:
            q = (u - 0.6) / 0.4
            c = (0.53 - 0.03 * q, 1.165 - 0.165 * q, 1.462)
        m.add(box(0.0135, 0.0135, 0.0135, (16, 16, 18), center=c))


def terminal_office(r, t, lamp=1.0, radio=True, crt=True, handset=True, voice=0.0):
    """Guard signal office: desk, CRT, cabinets, window onto snow."""
    from engine3d.core import Mesh, box, quad_xz
    m = Mesh()
    m.add(quad_xz(-7, -7, 7, 5, 0.0, (36, 34, 32), seg=4))
    m.add(box(14, 3.2, 0.16, (40, 38, 36), center=(0, 1.6, 4.2), seg=6))
    m.add(box(14, 0.2, 10, (28, 27, 26), center=(0, 3.2, 0), seg=6))
    for x in (-6.6, 5.4):
        m.add(box(0.16, 3.2, 11.0, (34, 33, 31), center=(x, 1.6, -1.3), seg=6))
    m.add(box(1.1, 0.8, 0.03, (52, 50, 44), center=(5.31, 1.6, 0.2), seg=2))
    for i, (dy, dz) in enumerate(((0.18, -0.25), (-0.10, 0.05), (0.12, 0.38))):
        m.add(box(0.02, 0.22, 0.17, (170 - i * 18, 164 - i * 14, 146),
                   center=(5.29, 1.6 + dy, 0.2 + dz)))
    # window: night snow beyond, warm reflection band
    m.add(box(3.4, 1.5, 0.06, (18, 26, 40), center=(2.4, 1.85, 4.10),
               emissive=True))
    m.add(box(3.6, 0.10, 0.10, (66, 62, 58), center=(2.4, 1.05, 4.05)))
    m.add(box(3.6, 0.10, 0.10, (66, 62, 58), center=(2.4, 2.65, 4.05)))
    for x in (0.9, 2.4, 3.9):
        m.add(box(0.08, 1.7, 0.10, (66, 62, 58), center=(x, 1.85, 4.05)))
    window_snow3d(r, t, (2.4, 1.85, 4.06), 1.6, 0.72, seed=5)
    m.add(box(0.9, 2.0, 0.8, (42, 40, 38), center=(-4.6, 1.0, 3.4), seg=3))
    m.add(box(0.9, 2.0, 0.8, (42, 40, 38), center=(-3.3, 1.0, 3.4), seg=3))
    # desk
    m.add(box(4.6, 0.12, 1.5, (58, 48, 38), center=(-0.4, 0.82, 1.9), seg=4))
    m.add(box(4.4, 0.76, 0.1, (46, 38, 30), center=(-0.4, 0.41, 2.6)))
    m.add(box(0.12, 0.78, 1.3, (46, 38, 30), center=(-2.6, 0.39, 1.9)))
    m.add(box(0.12, 0.78, 1.3, (46, 38, 30), center=(1.8, 0.39, 1.9)))
    # CRT terminal
    if crt:
        m.add(box(0.9, 0.72, 0.76, (64, 62, 56), center=(-0.9, 1.26, 1.75),
                   seg=2))
        m.add(box(0.74, 0.52, 0.04, (28, 54, 38), center=(-0.9, 1.30, 1.35),
                   emissive=True))
        m.add(box(0.9, 0.10, 0.66, (74, 70, 62), center=(-0.9, 0.90, 1.78)))
        m.add(box(0.72, 0.06, 0.30, (54, 50, 44), center=(-0.9, 0.88, 1.28)))
        r.add_sprite((-0.9, 1.30, 1.30),
                     _fx.crt_bloom(t, (120, 190, 140), 0.55, 0.4, 0.5),
                     layer=_fx.FX_LAYER)
    # radio set
    if radio:
        m.add(box(0.62, 0.30, 0.42, (38, 40, 38), center=(0.75, 0.99, 1.70)))
        # front panel: speaker grille, tuning scale with a needle, knobs, meter
        for i in range(5):
            m.add(box(0.13, 0.012, 0.008, (26, 28, 26),
                       center=(0.585, 1.030 - i * 0.026, 1.484)))
        m.add(box(0.42, 0.054, 0.008, (148, 136, 102),
                   center=(0.74, 1.100, 1.484), emissive=True))
        for i in range(7):
            m.add(box(0.005, 0.030, 0.006, (52, 48, 38),
                       center=(0.560 + i * 0.060, 1.100, 1.478)))
        v = max(0.0, min(1.0, voice))
        nx = 0.580 + 0.32 * (0.15 + 0.8 * v) + 0.008 * math.sin(t * 0.013)
        m.add(box(0.007, 0.046, 0.006, (208, 64, 48),
                   center=(nx, 1.100, 1.476)))
        for x in (0.88, 0.97):
            m.add(box(0.052, 0.052, 0.020, (30, 32, 30),
                       center=(x, 0.945, 1.486)))
            m.add(box(0.020, 0.040, 0.014, (120, 116, 100),
                       center=(x, 0.945, 1.478)))
        for i in range(5):
            lit = i < int(0.5 + v * 5)
            col = ((96, 190, 110) if i < 3 else
                   (222, 168, 70) if i == 3 else (204, 72, 56))
            m.add(box(0.026, 0.030, 0.008, col if lit else (38, 44, 40),
                       center=(0.700 + i * 0.030, 0.945, 1.482), emissive=lit))
        m.add(box(0.05, 0.05, 0.02, (60, 62, 58), center=(0.50, 1.00, 1.48)))
        if handset:
            _handset_rest(m)
    # desk lamp, far end of the desk
    m.add(box(0.06, 0.34, 0.06, (44, 42, 36), center=(-2.1, 1.02, 1.9)))
    m.add(box(0.22, 0.10, 0.18, (255, 216, 158), center=(-2.1, 1.22, 1.9),
               emissive=True))
    if lamp:
        warm_lamp(r, (-2.1, 1.20, 1.9), t, seed=8, radius_m=1.1,
                  intensity=0.6 * lamp)
    # chair, pushed out from the CRT and left empty
    S = SOLIDS["terminal"]
    _mesh_solid(m, S["chair_seat"], (34, 32, 30))
    _mesh_solid(m, S["chair_back"], (34, 32, 30))
    m.add(box(0.08, 0.41, 0.08, (26, 26, 26), center=(-0.85, 0.205, 0.45)))
    m.add(box(0.46, 0.03, 0.06, (26, 26, 26), center=(-0.85, 0.03, 0.45)))
    m.add(box(0.06, 0.03, 0.46, (26, 26, 26), center=(-0.85, 0.03, 0.45)))
    add(r, m)
    return (-0.9, 1.30, 1.35)


def vasile_office(r, t):
    """The empty office: desk, chair, blinds, cold city light."""
    from engine3d.core import Mesh, box, quad_xz
    m = Mesh()
    m.add(quad_xz(-8, -8, 8, 6, 0.0, (30, 28, 28), seg=4))
    m.add(box(16, 3.6, 0.16, (34, 32, 32), center=(0, 1.8, 4.6), seg=6))
    for i in range(8):
        m.add(box(2.0, 0.07, 0.02, (118, 104, 76),
                   center=(-2.4, 1.45 + i * 0.17, 4.50), emissive=True))
    m.add(box(0.10, 3.4, 0.10, (44, 42, 40), center=(-3.5, 1.7, 4.4)))
    m.add(box(0.10, 3.4, 0.10, (44, 42, 40), center=(-1.3, 1.7, 4.4)))
    # desk + empty chair
    m.add(box(3.8, 0.12, 1.6, (48, 36, 26), center=(0.2, 0.82, 1.4), seg=4))
    m.add(box(3.6, 0.76, 0.1, (38, 30, 22), center=(0.2, 0.41, 2.12)))
    m.add(box(0.1, 0.78, 1.4, (38, 30, 22), center=(-1.5, 0.39, 1.4)))
    m.add(box(0.1, 0.78, 1.4, (38, 30, 22), center=(1.9, 0.39, 1.4)))
    m.add(box(0.62, 0.12, 0.60, (26, 24, 24), center=(0.2, 0.50, -0.2)))
    m.add(box(0.62, 1.05, 0.10, (26, 24, 24), center=(0.2, 1.02, -0.52)))
    m.add(box(0.10, 0.48, 0.10, (20, 20, 20), center=(0.2, 0.24, -0.2)))
    m.add(box(0.5, 0.9, 0.5, (30, 28, 26), center=(0.2, 0.95, -0.2)))
    m.add(box(0.30, 0.06, 0.30, (255, 206, 150), center=(1.0, 0.90, 1.1),
               emissive=True))
    add(r, m)
    warm_lamp(r, (1.0, 0.93, 1.1), t, seed=12, radius_m=1.2, intensity=0.5)
    add(r, box(0.4, 0.02, 0.3, (206, 202, 190), center=(0.1, 0.90, 1.5)))
    r.add_sprite((2.8, 1.6, 4.4), _fx.window_glow((70, 84, 110), 2.4, 2.2, 0.22),
                 layer=_fx.FX_LAYER)
