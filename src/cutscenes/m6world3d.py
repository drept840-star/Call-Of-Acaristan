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
from cutscenes import m6fx3d as _fx
from cutscenes.cast3d import humanoid3d, spec3d

SAFE_TOP = SCENE_TOP + 6
SAFE_BOT = HEIGHT - 158
FILM_H = SAFE_BOT - SAFE_TOP
RES = 0.6
RW, RH = int(WIDTH * RES), int(FILM_H * RES)
# The PS2 look (insertion films): the train's 0.64 buffer, ordered dither and
# crisp present.  Opt-in per renderer through rend_ps2()/present_ps2().
RES_PS2 = 0.64
PW, PH = int(WIDTH * RES_PS2), int(FILM_H * RES_PS2)
PS2_LIGHT_CAP = 8

SNOW = (176, 188, 206)
SNOW_DARK = (44, 54, 70)
NIGHT = (7, 10, 18)
SODIUM = _fx.SODIUM
WARM = _fx.SODIUM
COLD = (120, 156, 206)

_cache = {"r": {}, "hum": {}, "grade": {}, "puff": {}, "err": None}
# Actors drawn this frame (cleared by rend()): the probe and tests read the
# final pose/joints from here instead of re-posing anything.
LAST = []

__all__ = [
    "SAFE_TOP", "SAFE_BOT", "FILM_H", "RW", "RH", "SNOW", "NIGHT", "WARM",
    "COLD", "SODIUM", "rend", "present", "rend_ps2", "present_ps2", "PW", "PH", "cam", "add", "film_xy", "project_xy",
    "grade", "finish", "hum", "actor", "air_actor", "life_pose", "yaw_to",
    "current_shot", "speaker", "talking", "snow3d", "breath", "hills",
    "terrain", "height_at", "crossing_far", "LZ", "LZ_Y", "border_compound", "helicopter",
    "heli_xform", "heli_solids", "HELI_SILL_Y", "HELI_SKID_X", "HELI_SKID_Y",
    "HELI_DOOR_Z", "HELI_ROTOR_R", "HELI_BENCH_H", "HELI_FLOOR_Y",
    "HELI_ROOF_Y", "heli_pilot", "boxcar_interior", "rail_platform",
    "terminal_office", "vasile_office", "night", "warm_lamp",
    "LAST", "STANCE", "ease5", "travel", "yaw_mix", "leg_ik", "path",
    "walk_stride", "walk_span", "walk", "walk_slip", "sit_pose", "ankles",
    "planted_pos", "reach", "SOLIDS", "solids", "penetration", "LANTERN",
    "knees", "head_stats", "RUN_P", "run_x", "run_dx", "run_ddx",
    "run_height", "run_valley",
]


# ── plumbing ───────────────────────────────────────────────────────────────
def rend(w=RW, h=RH):
    key = (int(w), int(h))
    if key not in _cache["r"]:
        from engine3d import Renderer  # lazy: the 2D fallback owns import errors
        _cache["r"][key] = (Renderer(key[0], key[1]), pygame.Surface(key))
    del LAST[:]
    r = _cache["r"][key][0]
    # pools persist on the renderer and the films share it: a shot that
    # lights the snow must not leave its pools on the next shot's set
    r.pools = []
    _cache["last_r"] = r
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


def rend_ps2():
    """The film renderer at the train's PS2 resolution, eight lights and
    snow glitter.  Present it with ``present_ps2``."""
    r, buf = rend(PW, PH)
    r.light_cap = PS2_LIGHT_CAP
    r.glitter = 1.0
    return r, buf


def present_ps2(surface, buf, x=0, w=WIDTH):
    """Train grade (contrast curve, split tone, ink floor, Bayer dither) on
    the small buffer, then a crisp nearest-x2 + box upscale into the film."""
    _fx.grade_cine(buf)
    _fx.present_crisp(buf, surface.subsurface((x, SAFE_TOP, w, FILM_H)))


def film_xy(p, x0=0, w=WIDTH, rw=RW):
    s = w / float(rw)
    return int(x0 + p[0] * s), int(SAFE_TOP + p[1] * s)


def project_xy(r, p, x0=0, w=WIDTH):
    q = r.project(p)
    return None if q is None else film_xy(q, x0, w, rw=r.w)


def cam(r, t, eye, tgt, fov, hh=0.0, seed=0, roll=0.0, shk=None):
    return _fx.set_cam(r, t, eye, tgt, fov, hh=hh, seed=seed, roll=roll, shk=shk)


def add(r, m, bias=0.0):
    if _STATIC_BUILD["active"]:
        if _STATIC_BUILD["rebuild"]:
            r.bake(m)
        return
    if _PACK_MEMO["on"]:
        _memo_add(r, m, bias)
        return
    faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces]
    r.add_dynamic(m.verts, faces, bias=bias)


_STATIC_BUILD = {"active": False, "rebuild": False}
_STATIC_SIG = None

# Live (not baked) sets whose meshes repeat frame to frame: the per-face
# Python packing, not the GPU, was the frame cost.  Rows are light-independent
# (shading happens in the shader), so they are kept per ``add`` call slot and
# re-packed only when that slot's mesh signature changes.
_PACK_MEMO = {"on": False, "key": None, "i": 0, "rows": [], "chunk": None}


def drop_renderer_caches():
    """Forget the set bake and the pack memo (a renderer was replaced).

    Both caches are keyed by ``id(renderer)``; a new renderer built after a
    resolution change could in principle land on a recycled id and be handed
    the old, empty batch.  Clearing them costs one rebuild and removes the
    whole class of bug.
    """
    global _STATIC_SIG
    _STATIC_SIG = None
    _PACK_MEMO["on"] = False
    _PACK_MEMO["key"] = None
    _PACK_MEMO["chunk"] = None
    _PACK_MEMO["rows"] = []


def pack_memo(r, key):
    """Begin a frame of live set geometry; pair with ``pack_memo_end``.
    No-op on renderers without ``add_packed`` (software backend)."""
    if not hasattr(r, "add_packed"):
        return
    k = (id(r), key)
    if _PACK_MEMO["key"] != k:
        _PACK_MEMO["key"] = k
        _PACK_MEMO["rows"] = []
        _PACK_MEMO["chunk"] = None
    _PACK_MEMO["i"] = 0
    _PACK_MEMO["on"] = True


def pack_memo_end(ok=True):
    """Close a memo frame.  A complete one is concatenated into ``chunk`` so
    later frames can replay the whole set with one queue call."""
    memo = _PACK_MEMO
    memo["on"] = False
    if not ok or not memo["rows"]:
        memo["chunk"] = None
        memo["key"] = None
        return
    rows = [r for _sig, r in memo["rows"] if r is not None]
    if not rows:
        memo["chunk"] = None
        return
    import numpy as np
    memo["chunk"] = rows[0] if len(rows) == 1 else np.concatenate(rows)


def pack_memo_ready(r, key):
    """True when the set built under ``key`` can be replayed verbatim."""
    return (hasattr(r, "add_packed") and _PACK_MEMO["key"] == (id(r), key)
            and _PACK_MEMO["chunk"] is not None)


def pack_memo_replay(r):
    if _PACK_MEMO["chunk"] is not None:
        # the chunk never changes: a GL renderer keeps it on the card
        (getattr(r, "add_resident", None) or r.add_packed)(_PACK_MEMO["chunk"])


def _mesh_sig(m, bias):
    v, f = m.verts, m.faces
    if not v or not f:
        return (len(v), len(f), bias)
    return (len(v), len(f), v[0], v[len(v) // 2], v[-1],
            f[0][1], f[len(f) // 2][1], f[-1][1], bias)


def _memo_add(r, m, bias):
    memo = _PACK_MEMO
    i = memo["i"]
    memo["i"] = i + 1
    rows = memo["rows"]
    sig = _mesh_sig(m, bias)
    if i < len(rows) and rows[i][0] == sig:
        r.add_packed(rows[i][1])
        return
    faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces]
    entry = (sig, r.pack(m.verts, faces, bias=bias))
    if i < len(rows):
        rows[i] = entry
    else:
        rows.append(entry)
    r.add_packed(entry[1])


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


def finish(surface, seed, tag="", col=(120, 190, 220), t=0, ps2=False):
    grade(surface, gamma=1.0 if ps2 else 0.82, vig=0.30 if ps2 else 0.40)
    # Fine grain: a signed luminance wobble over every pixel, re-seeded at
    # film rate.  The old hard single-pixel black specks (full alpha, value
    # 10..26) sat on faces and read as acne in every close-up.
    band = surface.subsurface((0, SAFE_TOP, WIDTH, FILM_H))
    try:
        from cutscenes.post3d import apply_post  # lazy: numpy stack
        apply_post(band, {"grain": 0.10 if ps2 else 0.26}, int(t), "m6_film_%s" % seed)
    except Exception:
        pass
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


def _guard_humanoid(kind, extra=None):
    from engine3d import Humanoid
    fk, variant = guard_spec(kind)
    out = spec3d(fk, rifle=variant["rifle"])
    for key, value in variant.get("head", {}).items():
        out[key] = value
    for key in ("backpack", "coat_len", "long_coat", "pouches"):
        if key in variant.get("body", {}):
            out[key] = variant["body"][key]
    if extra:
        out.update(extra)
    return Humanoid(out)


# HD train cast (opt-in; the films keep the plain rigs): the coats are lifted a
# few values and cooled so a warm key lights cloth, skin and ballast as three
# different values instead of one brown.  Only colours that already exist in
# the spec are touched.
_HD_TINTS = {
    "volkov": dict(jacket=(31, 35, 47), long_coat=(31, 35, 47), lapel=(20, 23, 32),
                   pants=(24, 27, 36), glove=(24, 24, 30)),
    "biribel": dict(jacket=(27, 31, 41), vest=(43, 47, 57), pants=(31, 35, 45)),
}


def _hd_extra(key, wound=0, bloody=False, flags=()):
    """Spec overrides for the HD variant of ``key``."""
    who = key[0] if isinstance(key, tuple) else key
    extra = dict(detail="hd")
    extra.update(_HD_TINTS.get(who, {}))
    if wound:
        extra["wound"] = int(wound)
    if bloody:
        extra["blood_hands"] = True
    for f in flags:
        extra[f] = True
    return extra


def _k9_rig_mesh():
    """The K-9 Biribel carries in the yard, as the rig's rifle: its pistol grip
    at the hand joint, +z muzzle."""
    from engine3d.core import Mesh
    from missions.m6.yard3d import K9_GRIP, _k9_asset
    src, _muzzle = _k9_asset()
    m = Mesh()
    m.verts = [(x - K9_GRIP[0], y - K9_GRIP[1], z - K9_GRIP[2]) for x, y, z in src.verts]
    m.faces = src.faces
    return m


def hum(key, hd=False, wound=0, bloody=False, flags=()):
    """Humanoid for ``key``.  ``hd`` selects the detailed train rig (optionally
    with a wound stage 1-3 / bloody gloves); each variant is its own cached rig,
    so switching stage costs one GPU template, never a per-frame rebuild.
    Outside ``hd``, ``flags`` = ("rifle",) arms Biribel's film rig."""
    if hd:
        ck = ("hd", key, int(wound), bool(bloody), tuple(flags))
    else:
        ck = (key, tuple(flags)) if flags else key
    h = _cache["hum"].get(ck)
    if h is None:
        extra = _hd_extra(key, wound, bloody, flags) if hd else {}
        if isinstance(key, tuple) and key[0] == "biribel":
            kw = dict(biribel_3d(key[1]))
            kw.update(extra)
            h = humanoid3d("biribel", **kw)
            if "rifle" in flags and not hd:
                h._rifle = _k9_rig_mesh()
                h._weapon = "k9"
            elif "shotgun" in flags and not hd:
                from engine3d.rig import shotgun_mesh
                h._rifle = shotgun_mesh()
                h._weapon = "shotgun"
                h._muzzle_z = 0.70
                # GL caches rig VBOs by spec repr; the shotgun needs its own.
                h._gl_spec_key = repr(sorted(h.spec.items())) + "|shotgun"
        elif isinstance(key, tuple) and key[0] == "guard":
            h = _guard_humanoid(key[1], extra)
        elif isinstance(key, tuple) and key[0] == "ally":
            h = humanoid3d(key[1], rifle="rifle", **extra)
        elif key == "guard":
            from engine3d import Humanoid
            h = Humanoid(spec3d(_base_guard_spec(), rifle="rifle", **extra))
        elif key == "ucilev":
            h = humanoid3d("ucilev", rifle="sniper", **extra)
        else:
            h = humanoid3d(key, **extra)
        _cache["hum"][ck] = h
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
          expression=None, mouth=None, bias=0.0, hd=False, wound=0,
          bloody=False, shadow=None, flags=()):
    h = hum(key, hd, wound, bloody, flags)
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
    if shadow is not None:
        joints = r.add_humanoid(h, p, pos, yaw, rifle_on=rifle_on, bias=bias,
                                shadow=shadow)
    else:
        joints = r.add_humanoid(h, p, pos, yaw, rifle_on=rifle_on, bias=bias)
    if len(LAST) < 16:
        LAST.append({"key": key, "joints": joints, "pos": tuple(pos),
                     "yaw": yaw, "pose": p, "hd": hd, "flags": tuple(flags),
                     "rifle": rifle_on})
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


def reach(hum, pose, side, target, pos, yaw, pole=None):
    """Arm IK onto a WORLD point for an actor drawn at (pos, yaw).  The elbow
    swivels toward ``pole`` (torso-local; default ik.solve_arm's relaxed out,
    down and back) so a hand held in front of the chest keeps its forearm
    outside the torso.  Reaches across the body want a forward, outward pole."""
    from engine3d.hold import POLES, solve_arm_safe
    sx = -1 if side == "l" else 1
    poles = POLES if pole is None else ((pole[0] * sx, pole[1], pole[2]),) + POLES
    return solve_arm_safe(hum, pose, pos, yaw, side, target, poles)


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
        "floor": ((-1.22, 0.42, -1.52), (1.22, 0.62, 1.92)),
        "roof": ((-1.22, 2.20, -1.52), (1.22, 2.56, 1.92)),
        "wall_l": ((-1.24, 0.58, -1.52), (-1.15, 2.20, 1.92)),
        "wall_r_rear": ((1.15, 0.58, -1.52), (1.24, 2.20, 0.25)),
        "wall_r_front": ((1.15, 0.58, 1.75), (1.24, 2.20, 1.92)),
        "door_header": ((1.15, 2.02, 0.25), (1.24, 2.20, 1.75)),
        "bulkhead_r": ((-1.22, 0.58, -1.52), (1.22, 2.20, -1.42)),
        "seat_pan_l": ((-0.80, 0.94, 2.00), (-0.30, 1.02, 2.46)),
        "seat_pan_r": ((0.30, 0.94, 2.00), (0.80, 1.02, 2.46)),
        "seat_back_l": ((-0.80, 0.62, 1.92), (-0.30, 1.80, 2.00)),
        "seat_back_r": ((0.30, 0.62, 1.92), (0.80, 1.80, 2.00)),
        "engine": ((-0.74, 2.50, -1.75), (0.74, 2.98, 0.85)),
        "boom": ((-0.50, 1.10, -7.95), (0.50, 2.50, -1.50)),
        "fin": ((-0.05, 2.06, -8.40), (0.05, 3.28, -7.50)),
        "skid_r": ((1.22, 0.045, -1.45), (1.38, 0.135, 2.30)),
        "skid_l": ((-1.38, 0.045, -1.45), (-1.22, 0.135, 2.30)),
        "door_panel": ((1.22, 0.62, -1.39), (1.27, 2.02, 0.07)),
        "bench_cushion": ((-1.08, 0.94, -0.30), (-0.60, 1.02, 1.00)),
        "bench_skirt": ((-0.66, 0.62, -0.30), (-0.62, 0.94, 1.00)),
        "bench_back": ((-1.15, 1.02, -0.30), (-1.08, 1.62, 1.00)),
    },
    # H2's fold-down seat by the door (airframe-local, not on the airframe).
    "heli_cabin": {
        "jump_cushion": ((0.60, 0.94, 0.15), (1.08, 1.02, 0.75)),
        "jump_leg_f": ((0.62, 0.62, 0.18), (0.66, 0.94, 0.72)),
        "jump_leg_b": ((1.02, 0.62, 0.18), (1.06, 0.94, 0.72)),
    },
}


HELI_SILL_Y = 0.62
HELI_SKID_X = 1.30
HELI_SKID_Y = 0.135
HELI_DOOR_Z = 0.95
HELI_ROTOR_R = 6.2
HELI_FLOOR_Y = 0.62
HELI_ROOF_Y = 2.20      # cabin ceiling
HELI_HUB_Y = 3.30
HELI_TR_Y = 2.96        # tail rotor hub, on the fin's left face
HELI_BENCH_H = 0.40     # seat top above the cabin floor


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
        cx, cy = (int(q[0] * xk), int(q[1] * yk)) if full else film_xy(q, rw=r.w)
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


def flake_sprite(r, p0, p1, col):
    """Queue one flake streak p0 -> p1 as a sprite.  Line batches are not
    depth-tested, so a streak behind a wall would draw over it; a sprite
    takes its depth from the world, so walls and the airframe hide it."""
    a, b = r.project(p0), r.project(p1)
    if a is None or b is None:
        return
    dx, dy = b[0] - a[0], b[1] - a[1]

    def draw(s, sx, sy, scale, z):
        pygame.draw.line(s, col, (sx, sy), (sx + dx, sy + dy), 1)
    r.add_sprite(p0, draw, layer=2)


def snow3d(r, t, seed=0, n=130, spread=18.0, height=14.0, speed=1.5,
           col=SNOW, near=0.0, skip=None, depth=False):
    """World-lattice snow around the camera; deterministic, dt-free.
    ``skip(p)`` drops any flake it returns True for; ``depth`` queues the
    flakes as depth-tested sprites (see ``flake_sprite``)."""
    cx, cy, cz = r.cam
    a = t * 0.001 * speed
    batch = getattr(r, "add_lines3d", None)
    segs = [] if batch is not None else None
    for i in range(n):
        u, v, w = _u(i, seed, 1), _u(i, seed, 2), _u(i, seed, 3)
        x = cx + (u * 2 - 1) * spread
        z = cz + (v * 2 - 1) * spread
        y = cy + height * 0.55 - ((a * (0.45 + 0.9 * w) + v * height) % height)
        if skip is not None and skip((x, y, z)):
            continue
        ln = 0.045 + 0.06 * w            # a flake, not a streak
        c = col if w > near else (int(col[0] * .6), int(col[1] * .65), int(col[2] * .7))
        tail = (x - 0.55 * ln, y - 0.8 * ln, z + 0.3 * ln)
        if depth:
            flake_sprite(r, (x, y, z), tail, c)
        elif segs is not None:
            segs.append(((x, y, z), tail, c, 1))
        else:
            r.add_line3d((x, y, z), tail, c, 1, layer=4)
    if segs:
        batch(segs, layer=4, depth_test=False)


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

    draw.bounds_m = (0.32, 0.40)
    return draw


# ── sky / light helpers ──────────────────────────────────────────────────
def night(r, buf, t, top=(5, 8, 15), bot=(18, 26, 42), stars=55, moon=False,
          sodium=(44, 30, 20), seed=0, star_cut=0.45):
    _fx.night_sky(r, buf, t, top, bot, stars=stars, moon=moon, clouds=3,
                  sodium=sodium, mist=(18, 22, 32), seed=seed, star_cut=star_cut)


def warm_lamp(r, pos, t, seed=0, radius_m=1.6, col=WARM, intensity=0.9):
    """One practical = one core + one halo.  A little haze only when the set
    is actually foggy; the old glow+haze+shaft stack read as three flat
    shapes on every lamp."""
    r.add_sprite(pos, _fx.glow(col, radius_m, t, flicker=0.05, seed=seed,
                               core=(255, 236, 200), intensity=intensity),
                 layer=_fx.FX_LAYER)
    if getattr(r, "fog_end", 200.0) < 60.0:
        r.add_sprite(pos, _fx.haze(_fx.SODIUM, radius_m * 1.8, t, seed=seed,
                                   intensity=0.05), layer=_fx.FX_LAYER)


# ── insertion sets ───────────────────────────────────────────────────────
LZ = (0.0, -48.0)
LZ_Y = 17.0
TERRAIN_HALF = 77.5
TERRAIN_STEP = 155.0 / 28.0
CROSSING_X = 42.0               # half-width of the levelled crossing apron


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
    # the Kim Kim crossing sits on a levelled apron
    apron = _s01(max(abs(x) - CROSSING_X, 24.0 - z, z - 56.0, 0.0) / 10.0)
    return (ridge + north + side + roll) * flat * apron


def _terrain_col(x, z, h, slope):
    """Ground albedo on the 2D palette: slate snow low, pale snow up on the
    ridge, trodden snow near the border road, bare rock on the steep faces.
    ``tex`` keeps the brightness and takes the texture's hue; the software
    backend draws the plain mean colour."""
    from engine3d import tex
    from missions.m6 import palette3d as P   # lazy: no missions.m6 at load
    lit = max(0.0, min(1.0, h / LZ_Y))
    j = 1.0 + 0.05 * math.sin(x * 0.91 + z * 1.27)
    like = tuple(int((P.SLATE_HI[i] * (0.62 + 0.38 * lit)
                      + P.SNOW_DIM[i] * 0.22 * lit) * j) for i in range(3))
    if slope > 0.55:
        k = min(1.0, (slope - 0.55) / 0.35)
        rock = (P.SLATE_MID[0] + 6, P.SLATE_MID[1] + 6, P.SLATE_MID[2] + 8)
        like = tuple(int(like[i] * (1 - k) + rock[i] * k) for i in range(3))
        return tex("concrete", like=like)
    if h < 3.0 and abs(x) < 38.0 and -2.0 < z < 24.0:
        return tex("snow_trod", like=tuple(int(c * 0.8) for c in like))
    return tex("snow", like=like)


def _static_skip():
    """Inside a static batch, later frames skip rebuilding set geometry."""
    return _STATIC_BUILD["active"] and not _STATIC_BUILD["rebuild"]


def terrain(r, t, lights=True):
    """Snow ridge above the border: one 28x28 heightfield, rock on the steep
    faces, sparse pines, the border road and its sodium lamps."""
    from engine3d import tex
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
        # snow-capped pines on the ridge, clear of the landing shelf
        rng = random.Random(9)
        needle = (13, 19, 19)
        capcol = tex("snow", like=(124, 136, 154))
        for k in range(52):
            x = rng.uniform(-70, 70)
            z = rng.uniform(-75, -20)
            if math.hypot(x - LZ[0], z - LZ[1]) < 14.0:
                continue
            gy = height_at(x, z)
            if gy < 5.0:
                continue
            hh = rng.uniform(2.6, 5.0)
            rad = hh * rng.uniform(0.27, 0.34)
            mm = Mesh()
            tiers = ((0.0, 0.46, 1.0), (0.26, 0.40, 0.76), (0.50, 0.34, 0.52))
            for y0, hf, rf in tiers:
                yb = gy - 0.15 + y0 * hh
                rb = rad * rf
                yt = yb + hf * hh * 1.5
                ang = [math.radians(90 + 60 * i) for i in range(6)]
                ring = [(x + math.cos(a_) * rb, yb, z + math.sin(a_) * rb)
                        for a_ in ang]
                tip = (x, yt, z)
                cut = 0.52               # snow rides the upper half of the tier
                rc = rb * (1.0 - cut) + 0.04
                yc = yb + (yt - yb) * cut
                cap = [(x + math.cos(a_) * rc, yc, z + math.sin(a_) * rc)
                       for a_ in ang]
                for i in range(6):
                    mm.face([ring[i], ring[(i + 1) % 6], cap[(i + 1) % 6], cap[i]],
                            needle, 2)
                    mm.face([cap[i], cap[(i + 1) % 6], tip], capcol, 2)
            add(r, mm)
        # border road cut and sodium lamp posts
        add(r, quad_xz(-34, 10, 34, 18, 0.03, tex("snow_trod", like=(34, 37, 45)), seg=8))
        if lights:
            for i, x in enumerate((-26, -13, 0, 13, 26)):
                z = 15.4
                y = height_at(x, z)
                add(r, box(0.08, 4.6, 0.08, (28, 30, 36), center=(x, y + 2.3, z)))
                add(r, box(0.16, 0.2, 0.16, _fx.SODIUM_PALE,
                           center=(x, y + 4.5, z), emissive=True))
                add(r, quad_xz(x - 2.2, z - 1.8, x + 2.2, z + 1.8, 0.04,
                               (92, 72, 48), seg=2))
    if lights:
        for i, x in enumerate((-26, -13, 0, 13, 26)):
            z = 15.4
            y = height_at(x, z)
            r.add_sprite((x, y + 4.6, z),
                         _fx.sodium_lamp(t, seed=i, radius_m=1.6, intensity=0.6),
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


def capital(r, t, dz=0.0, dx=0.0):
    """Distant skyline: panel blocks, a neon slogan, sodium dome and
    blinking aviation lights on the tall roofs.  ``dx``/``dz`` slide the
    whole skyline (a shot that needs it elsewhere on the horizon)."""
    from engine3d.core import Mesh
    from missions.m6 import bloc3d as B
    blocks = tuple((x + dx, z + dz, w, h, d) for x, z, w, h, d in _CAP_BLOCKS)
    if not _static_skip():
        def lifted(m, gy):
            # panel_block builds on y = 0; ``add``'s bias is depth, not height
            m.verts = [(vx, vy + gy, vz) for vx, vy, vz in m.verts]
            add(r, m)

        for i, (x, z, w, h, d) in enumerate(blocks):
            m = Mesh()
            B.panel_block(m.add, x, z, w, h, d, "-z", seed=70 + i,
                          col=(26 + i % 3, 28 + i % 3, 37 + i % 4), lit=0.3,
                          budget=max(6, int(w * h * 0.06)))
            lifted(m, height_at(x, z) - 0.5)
        tall = max(blocks, key=lambda b: b[3])
        x, z, w, h, d = tall
        gy = height_at(x, z) - 0.5
        pos, face = B.roof_sign_pos(x, z, w, h, d, "-z")
        B.letters(lambda mm: lifted(mm, gy), "АКАРИСТАН", pos, face, px=0.6,
                  col=B.NEON_RED, emissive=True)
    for i, (x, z, w, h, d) in enumerate(blocks):
        if h >= 21:
            gy = height_at(x, z) - 0.5
            r.add_sprite((x, gy + h + 0.4, z),
                         _fx.beacon((255, 44, 36), 0.30, t, phase=0.37 * i),
                         layer=_fx.FX_LAYER)
    r.add_sprite((2 + dx, 10, 66 + dz), _fx.haze(_fx.SODIUM, 44.0, t, seed=3,
                                                 intensity=0.20),
                 layer=_fx.FX_LAYER)
    r.add_sprite((dx, 5, 62 + dz), _fx.window_glow(_fx.SODIUM, 36.0, 8.0, 0.10),
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
        add(r, box(0.9, 0.7, 0.06, (255, 203, 109), center=(6.2, 1.55, 8.0),
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
            add(r, box(0.5, 0.22, 0.34, _fx.SODIUM_PALE, center=(x, 5.62, 7.55),
                       emissive=True))
            add(r, quad_xz(x - 3.4, 9.0, x + 3.4, 13.0, 0.04, (84, 68, 48), seg=4))
    r.add_sprite((6.2, 1.55, 7.9), _fx.window_glow(_fx.SODIUM, 0.8, 0.6,
                                                  intensity=0.55 * warm),
                 layer=_fx.FX_LAYER)
    for i, x in enumerate((-4.4, 4.4)):
        r.add_sprite((x, 5.6, 7.5), _fx.sodium_lamp(t, seed=20 + i, radius_m=1.9,
                                                    intensity=0.85),
                     layer=_fx.FX_LAYER)
    snow3d(r, t, seed=21, n=64, spread=22, height=16, speed=1.4)


def crossing_far(r, t, warm=1.0):
    """Kim Kim seen from the ridge, north of the compound: customs line,
    floodlit no-man's land between two gates, the rail yard with its lit
    passenger train and boxcars, and a signal tower with a red lamp (the
    one Ucilev will answer).  Low poly, built big enough to read at 80 m;
    light is emissive geometry plus a few halos."""
    from engine3d import tex
    from engine3d.core import box, quad_xz
    steel = (44, 49, 58)
    lampx = (-34.0, -12.0, 12.0, 34.0)
    if not _static_skip():
        dark = (20, 23, 30)
        # the floodlit strip: trodden snow the towers have turned amber
        add(r, quad_xz(-CROSSING_X, 29.5, CROSSING_X, 41.5, 0.05,
                       tex("snow_trod", like=(112, 92, 62)), seg=6))
        # wire fences either side of it
        for z in (29.0, 42.0):
            for x in range(-40, 41, 4):
                add(r, box(0.14, 2.6, 0.14, steel, center=(x, 1.3, z)))
            for y in (0.6, 1.6, 2.5):
                add(r, box(80, 0.07, 0.07, steel, center=(0, y, z)))
        # both gates: posts, a lowered barrier striped red/white
        for gz in (29.0, 42.0):
            for gx in (-3.0, 3.0):
                add(r, box(0.6, 3.4, 0.6, (70, 70, 74), center=(gx, 1.7, gz)))
            add(r, box(5.4, 0.2, 0.2, (150, 40, 36), center=(0, 3.2, gz)))
            for i in range(-2, 3):
                add(r, box(0.5, 0.22, 0.22, (190, 190, 186),
                           center=(i * 1.0, 3.2, gz - 0.02)))
        # customs post: low block, a lit window, a flat snowed roof
        add(r, box(9.0, 3.4, 5.0, tex("brick", like=(40, 38, 40)),
                   center=(-14.0, 1.7, 25.0), seg=3))
        add(r, box(9.6, 0.4, 5.6, dark, center=(-14.0, 3.6, 25.0)))
        add(r, box(8.6, 0.10, 5.0, tex("snow", like=(150, 160, 176)),
                   center=(-14.0, 3.85, 25.0)))
        add(r, box(2.6, 1.3, 0.1, _fx.SODIUM_PALE, center=(-16.0, 2.0, 22.45),
                   emissive=True))
        add(r, box(2.2, 1.3, 0.1, _fx.SODIUM_PALE, center=(-11.0, 2.0, 22.45),
                   emissive=True))
        # floodlight towers along the strip, heads aimed in
        for i, x in enumerate(lampx):
            for z in (30.5, 40.5):
                add(r, box(0.5, 10.0, 0.5, steel, center=(x, 5.0, z)))
                add(r, box(1.9, 0.6, 0.9, _fx.SODIUM_PALE, center=(x, 10.2, z),
                           emissive=True))
        # the rail yard: two tracks, ballast and sleepers
        for z in (47.0, 52.0):
            add(r, box(84, 0.12, 3.2, tex("ballast", like=(46, 50, 60)),
                       center=(0, 0.06, z), seg=6))
            for x in range(-40, 41, 3):
                add(r, box(0.5, 0.14, 2.4, tex("sleeper", like=(50, 44, 36)),
                           center=(x, 0.13, z)))
            for dz in (-0.72, 0.72):
                add(r, box(84, 0.14, 0.12, (86, 88, 92), center=(0, 0.24, z + dz)))
        # passenger train on the near track: a lit consist, locomotive west
        x0 = -30.0
        add(r, box(9.0, 3.6, 3.0, tex("steel", like=(30, 34, 42), tint=True),
                   center=(x0 + 3.0, 2.0, 47.0), seg=3))
        add(r, box(2.6, 1.0, 0.1, _fx.SODIUM_PALE, center=(x0 + 3.0, 3.0, 45.45),
                   emissive=True))
        for k in range(4):
            cx = x0 + 11.5 + k * 13.0
            add(r, box(12.4, 3.4, 3.0, tex("steel", like=(34, 40, 52), tint=True),
                       center=(cx, 2.0, 47.0), seg=3))
            add(r, box(12.0, 0.18, 3.2, tex("snow", like=(140, 150, 166)),
                       center=(cx, 3.8, 47.0)))
            for w in range(5):
                add(r, box(1.6, 0.9, 0.06, (255, 206, 120) if (k + w) % 3 else
                           (150, 118, 76), center=(cx - 4.8 + w * 2.4, 2.5, 45.47),
                           emissive=True))
        # boxcars standing dark on the siding
        for i, cx in enumerate((-33.0, -19.0, -5.0, 9.0, 23.0)):
            add(r, box(12.0, 3.2, 2.9, tex("boxcar", like=(34, 32, 30), tint=True),
                       center=(cx, 1.9, 52.0), seg=3))
            add(r, box(12.2, 0.14, 3.0, tex("snow", like=(120, 130, 146)),
                       center=(cx, 3.6, 52.0)))
        # signal tower: lattice mast, booth, red lamp on top
        sx, sz = 31.0, 44.5
        add(r, box(0.4, 9.0, 0.4, steel, center=(sx - 0.8, 4.5, sz - 0.8)))
        add(r, box(0.4, 9.0, 0.4, steel, center=(sx + 0.8, 4.5, sz - 0.8)))
        add(r, box(0.4, 9.0, 0.4, steel, center=(sx - 0.8, 4.5, sz + 0.8)))
        add(r, box(0.4, 9.0, 0.4, steel, center=(sx + 0.8, 4.5, sz + 0.8)))
        add(r, box(3.2, 2.0, 3.2, dark, center=(sx, 9.9, sz)))
        add(r, box(1.4, 0.8, 0.1, _fx.SODIUM_PALE, center=(sx, 10.0, sz - 1.65),
                   emissive=True))
        add(r, box(0.5, 0.5, 0.5, (255, 54, 40), center=(sx, 11.2, sz),
                   emissive=True))
    for i, x in enumerate(lampx):
        for j, z in enumerate((30.5, 40.5)):
            r.add_sprite((x, 10.0, z),
                         _fx.sodium_lamp(t, seed=60 + 2 * i + j, radius_m=4.2,
                                         intensity=0.8 * warm),
                         layer=_fx.FX_LAYER)
    r.add_sprite((0, 3.0, 36.0), _fx.haze(_fx.SODIUM, 34.0, t, seed=5,
                                          intensity=0.22 * warm),
                 layer=_fx.FX_LAYER)
    r.add_sprite((-14.0, 2.0, 22.4), _fx.window_glow(_fx.SODIUM, 7.0, 1.6, 0.4 * warm),
                 layer=_fx.FX_LAYER)
    for k in range(4):
        r.add_sprite((-18.5 + k * 13.0, 2.5, 45.4),
                     _fx.window_glow(_fx.SODIUM, 11.0, 1.2, 0.32 * warm),
                     layer=_fx.FX_LAYER)
    r.add_sprite((31.0, 11.2, 44.5), _fx.beacon((255, 54, 40), 0.55, t, phase=0.2),
                 layer=_fx.FX_LAYER)
    snow3d(r, t, seed=31, n=40, spread=30, height=20, speed=1.2)


# ── the valley run (intro chase) ─────────────────────────────────────────
# Its own space, not the insertion terrain: a frozen river the Huey follows
# north at treetop height.  Everything in it is periodic in z with RUN_P, so
# a shot can wrap its distance along the river (s mod RUN_P) and run for any
# length without a visible jump.  Lateral offsets (``lat``) are measured from
# the river's centreline, + to the east.
RUN_P = 112.0
RUN_Z0, RUN_Z1 = -150.0, RUN_P + 190.0
_RUN_K = 2.0 * math.pi / RUN_P
_RUN_LATS = (-78, -62, -50, -40, -32, -25, -19, -14, -10, -7, -5, -3.2,
             3.2, 5, 7, 10, 14, 19, 25, 32, 40, 50, 62, 78)


def run_x(z):
    """River centreline x at ``z``."""
    return 3.0 * math.sin(_RUN_K * z) + 1.2 * math.sin(2 * _RUN_K * z + 0.9)


def run_dx(z):
    """dx/dz of the centreline."""
    return _RUN_K * (3.0 * math.cos(_RUN_K * z)
                     + 2.4 * math.cos(2 * _RUN_K * z + 0.9))


def run_ddx(z):
    return -_RUN_K * _RUN_K * (3.0 * math.sin(_RUN_K * z)
                               + 4.8 * math.sin(2 * _RUN_K * z + 0.9))


def run_height(x, z):
    """Valley floor: river ice at 0, low snow banks, walls climbing to a
    ~34 m moorland either side, with periodic folds so the walls never read
    as a straight cut."""
    lat = x - run_x(z)
    a = abs(lat)
    side = 1.0 if lat > 0 else -1.0
    bank = 0.6 * _s01((a - 3.2) / 4.5)
    wall = 26.0 * _s01((a - 15.0) / 40.0) + 0.32 * max(0.0, a - 55.0)
    fold = (1.6 * math.sin(3 * _RUN_K * z + 0.8 * side + 0.05 * lat)
            + 0.9 * math.sin(5 * _RUN_K * z + 0.11 * lat + 2.0))
    return bank + wall + fold * _s01((a - 9.0) / 16.0)


def _run_col(lat, h, slope):
    from engine3d import tex
    from missions.m6 import palette3d as P   # lazy: no missions.m6 at load
    up = max(0.0, min(1.0, h / 30.0))
    j = 1.0 + 0.05 * math.sin(lat * 0.91 + h * 1.27)
    like = tuple(int((P.SLATE_HI[i] * (0.66 + 0.34 * up)
                      + P.SNOW_DIM[i] * 0.24 * up) * j) for i in range(3))
    if slope > 0.62:
        k = min(1.0, (slope - 0.62) / 0.3)
        rock = (P.SLATE_MID[0] + 4, P.SLATE_MID[1] + 4, P.SLATE_MID[2] + 6)
        like = tuple(int(like[i] * (1 - k) + rock[i] * k) for i in range(3))
        return tex("concrete", like=like)
    return tex("snow", like=like)


def _run_pine(m, x, z, gy, hh, needle, capcol):
    rad = hh * 0.30
    for y0, hf, rf in ((0.0, 0.46, 1.0), (0.28, 0.40, 0.74), (0.52, 0.34, 0.50)):
        yb = gy - 0.2 + y0 * hh
        rb = rad * rf
        yt = yb + hf * hh * 1.5
        ang = [math.radians(90 + 60 * i) for i in range(6)]
        ring = [(x + math.cos(a_) * rb, yb, z + math.sin(a_) * rb) for a_ in ang]
        rc = rb * 0.48 + 0.04
        yc = yb + (yt - yb) * 0.52
        cap = [(x + math.cos(a_) * rc, yc, z + math.sin(a_) * rc) for a_ in ang]
        for i in range(6):
            m.face([ring[i], ring[(i + 1) % 6], cap[(i + 1) % 6], cap[i]], needle, 2)
            m.face([cap[i], cap[(i + 1) % 6], (x, yt, z)], capcol, 2)


def run_valley(r, t):
    """The frozen river valley: a curvilinear heightfield that follows the
    river, an ice ribbon down its middle, bank boulders and snow-capped pines.
    Pines and rocks repeat every RUN_P; the east bank keeps a clear lane for
    the chase camera (lat 3..23)."""
    from engine3d import tex
    from engine3d.core import Mesh, box, rot_y
    if _static_skip():
        return
    m = Mesh()
    zs = [RUN_Z0 + 4.0 * i for i in range(int((RUN_Z1 - RUN_Z0) / 4.0) + 1)]
    rows = []
    for z in zs:
        cx = run_x(z)
        rows.append([(cx + lat, run_height(cx + lat, z), z) for lat in _RUN_LATS])
    ice = tex("snow_trod", like=(54, 66, 86))
    for j in range(len(zs) - 1):
        ra, rb = rows[j], rows[j + 1]
        for i in range(len(_RUN_LATS) - 1):
            a, b, c, d = ra[i], ra[i + 1], rb[i + 1], rb[i]
            lat = 0.5 * (_RUN_LATS[i] + _RUN_LATS[i + 1])
            if abs(lat) < 1.0:
                m.face([a, d, c, b], ice, 0)
                continue
            w = math.hypot(b[0] - a[0], b[2] - a[2]) or 1.0
            slope = max(abs(b[1] - a[1]) / w, abs(d[1] - a[1]) / 4.0)
            m.face([a, d, c, b], _run_col(lat, (a[1] + b[1] + c[1] + d[1]) / 4,
                                          slope), 0)
    add(r, m)
    rng = random.Random(23)
    needle = (13, 19, 19)
    capcol = tex("snow", like=(124, 136, 154))
    pines = []
    for k in range(46):
        z = rng.uniform(0.0, RUN_P)
        if rng.random() < 0.55:
            lat = -rng.uniform(7.0, 60.0)
        else:
            lat = rng.uniform(24.0, 62.0)
        pines.append((z, lat, rng.uniform(3.6, 7.4)))
    rocks = [(rng.uniform(0.0, RUN_P), rng.choice((-1, 1)) * rng.uniform(3.6, 6.5),
              rng.uniform(0.5, 1.3), rng.uniform(0, 90)) for _k in range(12)]
    reps = range(int(math.floor(RUN_Z0 / RUN_P)), int(math.ceil(RUN_Z1 / RUN_P)) + 1)
    for n in reps:
        mm = Mesh()
        for z0, lat, hh in pines:
            z = z0 + n * RUN_P
            if not (RUN_Z0 + 4.0 < z < RUN_Z1 - 4.0):
                continue
            x = run_x(z) + lat
            _run_pine(mm, x, z, run_height(x, z), hh, needle, capcol)
        for z0, lat, s, ang in rocks:
            z = z0 + n * RUN_P
            if not (RUN_Z0 < z < RUN_Z1):
                continue
            x = run_x(z) + lat
            gy = run_height(x, z)
            mm.add(box(s * 1.3, s * 0.7, s, (34, 38, 46)), m=rot_y(ang),
                   t=(x, gy + s * 0.22, z))
            mm.add(box(s * 1.1, 0.12, s * 0.85, tex("snow", like=(150, 160, 178))),
                   m=rot_y(ang), t=(x, gy + s * 0.60, z))
        add(r, mm)


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


def _heli_sec(hw, yb, yt, cb, ct):
    """Chamfered airframe cross-section, counter-clockwise from the belly:
    0 bottom, 1/7 lower chamfers, 2/6 sides, 3/5 upper chamfers, 4 top."""
    return [(-hw + cb, yb), (hw - cb, yb), (hw, yb + cb), (hw, yt - ct),
            (hw - ct, yt), (-hw + ct, yt), (-hw, yt - ct), (-hw, yb + cb)]


def _heli_loft(m, rings, col, paint, skip, caps=False):
    """Join [(z, section)] rings into a double-sided shell; ``paint`` maps
    (ring, side) to a colour, ``skip`` leaves (ring, side) open."""
    for k in range(len(rings) - 1):
        za, pa = rings[k]
        zb, pb = rings[k + 1]
        for i in range(len(pa)):
            if (k, i) in skip:
                continue
            j = (i + 1) % len(pa)
            m.face([(pa[i][0], pa[i][1], za), (pa[j][0], pa[j][1], za),
                    (pb[j][0], pb[j][1], zb), (pb[i][0], pb[i][1], zb)],
                   paint.get((k, i), col), 2, True)
    if caps:
        for z, sec in (rings[0], rings[-1]):
            m.face([(x, y, z) for x, y in sec], col, 2, True)


def _heli_bar(m, a, b, w, col):
    """Thin flat frame member from a to b (spread across x, or across y when
    it runs along x)."""
    off = (0.0, w, 0.0) if abs(a[0] - b[0]) > abs(a[2] - b[2]) else (w, 0.0, 0.0)
    m.face([tuple(a[i] - off[i] for i in range(3)),
            tuple(a[i] + off[i] for i in range(3)),
            tuple(b[i] + off[i] for i in range(3)),
            tuple(b[i] - off[i] for i in range(3))], col, 2, True)


_PILOT = {}


def heli_pilot():
    """Maru in the right-hand seat -> (pose, airframe-local root): rear on
    the pan, back against the seat back, hands forward on the controls."""
    d = _PILOT.get("v")
    if d is None:
        h = hum("maru")
        pose = sit_pose(h, HELI_BENCH_H,
                        dict(spine=5, head_p=-3, lsh_p=34, lsh_r=4, lel=52,
                             rsh_p=40, rsh_r=-4, rel=58))
        places, _j, root = h.pose_world(pose, (0.0, HELI_FLOOR_Y, 0.0), 0.0)
        uniq = h._unique_verts()
        back = min(M[6] * x + M[7] * y + M[8] * z + org[2]
                   for _s, key, M, org, _g, _fb in places
                   if key in ("pelvis", "torso")
                   for x, y, z in uniq[key]) + root[2]
        seat_back = SOLIDS["heli"]["seat_back_r"][1][2]
        d = _PILOT["v"] = (pose, (0.55, HELI_FLOOR_Y, seat_back + 0.03 - back))
    return d


def _heli_pilot(r, t, L, look):
    """Built in airframe space and carried through ``L`` so she banks and
    pitches with the cockpit instead of sliding out of it."""
    pose, root = heli_pilot()
    h = hum("maru")
    if getattr(h, "_m6_face", None) != ("neutral", 0.0):
        h.set_expression("neutral", 0.0)
        h._m6_face = ("neutral", 0.0)
    p = dict(pose)
    if look is not True:
        p["twist"], p["head_y"] = look
    verts, faces, _j = h.build(life_pose(p, t, 0.15, 61), root, 0.0,
                               rifle_on=False)
    r.add_dynamic([L(*v) for v in verts], faces)


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
               door=True, bank=0.0, pitch=0.0, blur=1.0, pilot=True):
    """Huey-like airframe: glazed nose, open right door, skids, tail boom and
    a translucent two-blade rotor blurred out to the blade radius.  ``blur``
    scales only the additive blur, so a distant airframe stays solid under it.
    ``pilot``: True seats Maru at the controls looking ahead, a (twist,
    head_y) pair turns her head, False leaves the cockpit empty.
    Returns world anchors: door_sill (point, outward normal), skid_top_r, hub,
    belly, nose, rotor_radius, blur_radius."""
    from engine3d.core import Mesh, box, m_apply, prism, rot_x, rot_y, rot_z
    S = scale
    L = heli_xform(pos, yaw, bank, pitch, S)

    def place(mesh, bias=0.4):
        mesh.verts = [L(*v) for v in mesh.verts]
        add(r, mesh, bias=bias)

    hull, top, belly = (60, 68, 49), (72, 80, 59), (42, 48, 36)
    dark, glass, cab = (17, 19, 17), (26, 38, 50), (36, 39, 34)
    H = SOLIDS["heli"]
    body = Mesh()
    # cabin pod: belly chamfer, floor, walls with the open right door, roof
    body.add(prism([(-1.22, 0.62), (-1.02, 0.42), (1.02, 0.42), (1.22, 0.62)],
                   3.44, belly, z0=-1.52))
    body.add(box(2.36, 0.04, 4.60, cab, center=(0, 0.60, 0.78)))
    _mesh_solid(body, H["wall_l"], hull)
    _mesh_solid(body, H["wall_r_rear"], hull)
    _mesh_solid(body, H["wall_r_front"], hull)
    _mesh_solid(body, H["door_header"], hull)
    _mesh_solid(body, H["bulkhead_r"], cab)
    body.add(prism([(-1.24, HELI_ROOF_Y), (1.24, HELI_ROOF_Y), (0.88, 2.56),
                    (-0.88, 2.56)], 3.44, top, z0=-1.52))
    # bench along the left wall, visible through the door
    _mesh_solid(body, H["bench_cushion"], (30, 33, 29))
    _mesh_solid(body, H["bench_skirt"], (24, 27, 23))
    _mesh_solid(body, H["bench_back"], (28, 31, 27))
    # cabin construction: insulated wall panels, exposed ribs, floor treads,
    # belts and a stowed extinguisher.  These read in the close briefing shot
    # and give the green cabin wall a scale it did not have.
    for i, pz in enumerate((-1.05, -0.28, 0.49, 1.24)):
        for sx in (-1.17, 1.17):
            if sx > 0 and 0.25 < pz < 1.75:
                continue                    # no rib across the open door
            body.add(box(0.035, 1.18, 0.08, (47, 50, 42)
                         if sx < 0 else (50, 53, 45),
                         center=(sx, 1.32, pz)))
        body.add(box(1.20, 0.045, 0.055, (38, 41, 35),
                     center=(0, 2.13, pz)))
    for i, pz in enumerate((-1.25, -0.55, 0.15, 0.85, 1.55)):
        body.add(box(2.26, 0.018, 0.12, (25, 27, 25),
                     center=(0, 0.625, pz)))
    for i, pz in enumerate((-0.85, -0.05, 0.75)):
        for sx in (-0.78, 0.18):
            body.add(box(0.045, 0.60, 0.035, (82, 72, 54),
                         center=(sx, 1.32, pz)))
    body.add(box(0.24, 0.48, 0.18, (88, 38, 32),
                 center=(-0.82, 0.92, 1.58)))
    body.add(box(0.10, 0.06, 0.06, (25, 24, 22),
                 center=(-0.82, 1.20, 1.58)))
    # cabin dome light: the red practical seen through the open door
    body.add(box(0.13, 0.04, 0.13, (255, 66, 46),
                 center=(0.0, HELI_ROOF_Y - 0.03, 0.55), emissive=True))
    # The right-hand door slides on its rail: 1 = open (leaf back over the
    # wall), 0 = closed across the opening.  The old bool still works.
    open_k = (1.0 if door is True else 0.0 if door is False
              else max(0.0, min(1.0, float(door))))
    leaf_z = -0.66 + (0.975 + 0.66) * (1.0 - open_k)
    body.add(box(0.05, 1.40, 1.45, hull), t=(1.245, 1.32, leaf_z))
    body.add(box(0.02, 0.50, 0.95, glass), t=(1.275, 1.62, leaf_z))
    body.add(box(0.04, 0.10, 0.18, dark), t=(1.28, 1.12, leaf_z + 0.62))
    body.add(box(0.04, 0.05, 2.80, dark), t=(1.25, 2.05, -0.10))
    body.add(box(0.05, 0.04, 1.50, (80, 84, 76)), t=(1.23, 0.63, 1.00))

    # nose: lofted sections taper from the cabin to the chin; the upper
    # windscreen is left open so the pilot reads through it at night
    rings = [(1.92, _heli_sec(1.22, 0.42, 2.56, 0.20, 0.36)),
             (2.55, _heli_sec(1.18, 0.44, 2.46, 0.20, 0.40)),
             (3.05, _heli_sec(1.04, 0.52, 2.00, 0.20, 0.34)),
             (3.40, _heli_sec(0.80, 0.66, 1.46, 0.18, 0.24)),
             (3.58, _heli_sec(0.46, 0.84, 1.12, 0.12, 0.14))]
    open_ = {(1, 3), (1, 4), (1, 5), (2, 3), (2, 4), (2, 5)}
    paint = {(k, i): top for k in range(4) for i in (3, 4, 5)}
    paint.update({(k, i): belly for k in range(4) for i in (0, 1, 7)})
    paint.update({(1, 2): glass, (1, 6): glass, (2, 1): glass, (2, 7): glass})
    _heli_loft(body, rings, hull, paint, open_)
    body.face([(x, y, 3.58) for x, y in rings[-1][1]], hull, 2, True)
    # windscreen frame: centre post and the header bow
    _heli_bar(body, (0, 2.48, 2.55), (0, 1.48, 3.38), 0.035, dark)
    _heli_bar(body, (-1.10, 2.10, 2.55), (1.10, 2.10, 2.55), 0.04, dark)
    # cockpit: pedestal, instrument panel with its green glow, seats
    body.add(box(0.30, 0.46, 0.70, cab, center=(0, 0.85, 2.62)))
    body.add(box(1.70, 0.30, 0.12, dark, center=(0, 1.42, 2.98)))
    body.add(box(1.50, 0.20, 0.02, (16, 52, 40), center=(0, 1.44, 2.91),
                 emissive=True))
    body.add(box(1.80, 0.05, 0.30, dark, center=(0, 1.59, 2.92)))
    # seats skip the airframe's depth bias: the pilot sits within 0.4 m of
    # the seat back, and a biased back lets her draw through it from the cabin
    seats = Mesh()
    for side in ("l", "r"):
        _mesh_solid(seats, H["seat_pan_" + side], (40, 43, 37))
        _mesh_solid(seats, H["seat_back_" + side], (32, 35, 30))
    place(seats, bias=0.0)

    # transmission/engine cowling, intake, exhaust, mast
    _heli_loft(body, [(0.85, _heli_sec(0.52, 2.50, 2.62, 0.02, 0.06)),
                      (0.55, _heli_sec(0.74, 2.50, 2.98, 0.02, 0.14)),
                      (-1.30, _heli_sec(0.74, 2.50, 2.98, 0.02, 0.14)),
                      (-1.75, _heli_sec(0.50, 2.40, 2.80, 0.02, 0.12))],
               top, {}, (), caps=True)
    body.add(box(0.86, 0.12, 0.05, dark), t=(0, 2.84, 0.57))
    body.add(box(0.30, 0.24, 0.40, dark), m=rot_x(-20), t=(0.0, 2.86, -1.78))
    body.add(box(0.18, 0.30, 0.18, dark), t=(0, 3.13, 0.15))
    # tail boom: tapered, with the elevator, fin, red tip and tail skid
    _heli_loft(body, [(-1.52, _heli_sec(0.50, 1.10, 2.50, 0.16, 0.18)),
                      (-2.60, _heli_sec(0.36, 1.55, 2.36, 0.10, 0.12)),
                      (-7.60, _heli_sec(0.16, 1.86, 2.16, 0.04, 0.05)),
                      (-7.95, _heli_sec(0.14, 1.90, 2.12, 0.04, 0.04))],
               hull, {(k, i): top for k in range(3) for i in (3, 4, 5)},
               (), caps=True)
    body.add(box(2.00, 0.05, 0.40, hull), t=(0, 1.96, -5.20))
    for sx in (-1, 1):
        body.add(box(0.04, 0.22, 0.42, belly), t=(sx * 1.00, 1.96, -5.20))
    fin = prism([(-7.50, 2.10), (-7.95, 2.06), (-8.40, 3.20), (-8.15, 3.28)],
                0.10, hull, z0=-0.05)
    body.add(fin, m=rot_y(-90))
    body.add(box(0.11, 0.16, 0.30, (128, 38, 32)), t=(0, 3.18, -8.28))
    body.add(box(0.05, 0.26, 0.05, dark), t=(0, 1.73, -7.70))
    # stencils: a pale number block on the boom and a cabin panel line
    for sx in (-1, 1):
        body.add(box(0.01, 0.10, 0.56, (150, 150, 136)),
                 t=(sx * 0.32, 2.02, -3.40))
        body.add(box(0.01, 0.04, 0.80, (98, 104, 86)),
                 t=(sx * 1.245, 1.86, -0.95))
    # skids: tubes with upturned toes, cross tubes and belly struts
    for sx in (-1, 1):
        body.add(box(0.09, 0.09, 3.60, dark), t=(sx * HELI_SKID_X, 0.09, 0.35))
        body.add(box(0.09, 0.09, 0.70, dark), m=rot_x(-24),
                 t=(sx * HELI_SKID_X, 0.13, 2.45))
        for zz in (-0.55, 0.95):
            body.add(box(0.07, 0.20, 0.07, dark), t=(sx * HELI_SKID_X, 0.235, zz))
            body.add(box(0.07, 0.10, 0.07, dark), t=(sx * 1.02, 0.39, zz))
    for zz in (-0.55, 0.95):
        body.add(box(2.72, 0.075, 0.075, dark), t=(0, 0.36, zz))
    place(body)
    if pilot:
        _heli_pilot(r, t, L, pilot)

    # main rotor: one bar = two blades of radius R, readable 140 deg/s
    spin = (t * 0.001 * 140.0 * rotor_speed) % 360.0
    rotor = Mesh()
    rotor.add(box(2 * HELI_ROTOR_R, 0.045, 0.30, (20, 22, 20)),
              m=rot_y(spin), t=(0, HELI_HUB_Y, 0.15))
    for sx in (-1, 1):
        rotor.add(box(0.30, 0.05, 0.31, (150, 132, 52)), m=rot_y(spin),
                  t=(sx * (HELI_ROTOR_R - 0.15), HELI_HUB_Y, 0.15))
    rotor.add(box(0.36, 0.12, 0.36, dark), t=(0, HELI_HUB_Y, 0.15))
    place(rotor)
    tr_spin = (t * 0.001 * 620.0 * rotor_speed) % 360.0
    tail = Mesh()
    tail.add(box(0.05, 2.30, 0.10, (20, 22, 20)), m=rot_x(tr_spin),
             t=(-0.16, HELI_TR_Y, -8.12))
    tail.add(box(0.12, 0.14, 0.14, dark), t=(-0.12, HELI_TR_Y, -8.12))
    place(tail)

    # rotor blur: one inner disc at the hub, eight outer sectors at 0.78R, so
    # every sprite stays inside the GL depth-reach box of its anchor
    hub = L(0.0, HELI_HUB_Y, 0.15)

    def rim(rad, a):
        return L(math.cos(a) * rad, HELI_HUB_Y, 0.15 + math.sin(a) * rad)

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
            r.add_sprite(L(sx * 1.10, 1.05, 2.95),
                         _fx.beacon(col, 0.24, t, period_ms=1400.0,
                                    phase=0.0 if seed == 3 else 0.5,
                                    intensity=0.95),
                         layer=_fx.FX_LAYER)
        r.add_sprite(L(0.08, 3.30, -8.16),
                     _fx.beacon((255, 248, 226), 0.20, t, period_ms=1200.0,
                                phase=0.25, intensity=0.8),
                     layer=_fx.FX_LAYER)
        r.add_sprite(L(0.0, 2.66, -1.62),
                     _fx.beacon((255, 40, 32), 0.30, t, period_ms=1000.0,
                                phase=0.75),
                     layer=_fx.FX_LAYER)
        r.add_sprite(L(0.0, HELI_ROOF_Y - 0.04, 0.55),
                     _fx.glow((255, 70, 52), 0.30, t, seed=7, flicker=0.10,
                              intensity=0.55), layer=_fx.FX_LAYER)
        r.add_sprite(L(0.0, 1.46, 2.86),
                     _fx.glow((70, 190, 130), 0.28, t, seed=8,
                              intensity=0.35), layer=_fx.FX_LAYER)
    normal = (m_apply(rot_y(yaw), m_apply(rot_z(bank),
              m_apply(rot_x(pitch), (1.0, 0.0, 0.0)))))
    return {
        "door_sill": (L(1.20, HELI_SILL_Y, HELI_DOOR_Z), normal),
        "skid_top_r": L(HELI_SKID_X, HELI_SKID_Y, HELI_DOOR_Z),
        "hub": hub,
        "belly": L(0.0, 0.46, 0.30),
        "nose": L(0.0, 1.00, 3.58),
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
    m.add(box(0.12, 0.16, 0.12, _fx.SODIUM_PALE, center=(Wd / 2 - 0.26, 1.96, -1.30),
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
        m.add(box(0.4, 0.18, 0.3, _fx.SODIUM_PALE,
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
    m.add(box(0.20, 0.24, 0.20, _fx.SODIUM_PALE, center=LANTERN, emissive=True))
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
    from engine3d import tex
    from engine3d.core import Mesh, box
    m = Mesh()
    add = m.add
    BODY = tex("steel", like=(30, 35, 43), tint=True)
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
    add(box(46, 0.5, 3.2, tex("metal_rib", like=(24, 28, 34), tint=True),
            center=(0, 3.55, -4.4), seg=8))
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
        pane = ((255, 203, 109) if i % 5 else (154, 120, 88)) \
            if i % 7 else (150, 176, 196)
        add(box(1.56, 0.96, 0.05, FRAME, center=(wx, 2.45, -2.885)))
        add(box(0.64, 0.78, 0.03, pane, center=(wx - 0.34, 2.45, -2.855),
                emissive=True))
        add(box(0.64, 0.78, 0.03, pane, center=(wx + 0.34, 2.45, -2.855),
                emissive=True))
        add(box(0.05, 0.82, 0.04, FRAME, center=(wx, 2.45, -2.848)))
        add(box(1.70, 0.06, 0.12, (150, 162, 180),
                center=(wx, 1.94, -2.842)))
        if i % 3:
            add(box(0.20, 0.82, 0.012, (74, 44, 40) if i % 2 else (44, 54, 64),
                    center=(wx - 0.50, 2.45, -2.835)))
            add(box(0.10, 0.82, 0.014, (28, 26, 27),
                    center=(wx + 0.52, 2.45, -2.834)))
        if i in (2, 6, 9):
            add(box(0.24, 0.56, 0.010, (24, 26, 30),
                    center=(wx + 0.12, 2.36, -2.831)))
            add(box(0.14, 0.16, 0.012, (38, 42, 48),
                    center=(wx + 0.12, 2.62, -2.830)))
    # Door frame + vestibule.  The leaves themselves are animated in train3d.
    add(box(1.60, 1.65, 0.06, (54, 38, 26), center=(10.9, 1.85, -3.28)))
    add(box(1.20, 0.05, 0.10, _fx.SODIUM_PALE,
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


def train_body(r, tx):
    """The waiting carriage alone, shifted by ``tx``: the set memo excludes it
    because it is the one part of the live station that moves."""
    _train_detail(r, tx)


def _train_detail(r, tx):
    m = _train_detail_mesh()
    if hasattr(r, "add_packed") and not _STATIC_BUILD["active"]:
        # GL: pack the cached mesh once, then only slide its x column.
        ent = _cache.get("train_detail_rows")
        if ent is None or ent[0] is not m:
            faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces]
            ent = _cache["train_detail_rows"] = (m, r.pack(m.verts, faces))
        rows = ent[1]
        if rows is not None and abs(tx) >= 1e-6:
            rows = rows.copy()
            rows[:, 0] += tx
        r.add_packed(rows)
        return
    if abs(tx) < 1e-6:
        add(r, m)
        return
    from engine3d.core import Mesh
    shifted = Mesh()
    shifted.verts = [(v[0] + tx, v[1], v[2]) for v in m.verts]
    shifted.faces = list(m.faces)
    add(r, shifted)


def rail_platform(r, t, train=True, snow=1.0, train_offset=0.0):
    from engine3d import tex
    from engine3d.core import box, quad_xz
    add(r, quad_xz(-40, -40, 40, 40, 0.0, tex("snow", like=(52, 60, 74)), seg=12))
    # ballast + rails
    add(r, quad_xz(-30, -2.0, 30, 2.6, 0.06, tex("ballast", like=(40, 40, 44)), seg=8))
    for z in (-1.5, 1.5):
        add(r, box(60, 0.10, 0.10, (86, 88, 92), center=(0, 0.16, z)))
    # Ties: one set across both rails (this loop used to sit inside the rail
    # loop and doubled every tie).  Under the catch (x 9.5..14.5) they are sunk
    # flush with the ballast, so a kneeling pair and a lowered body rest on
    # the bed instead of 8 cm inside a sleeper.
    for x in range(-28, 29, 2):
        if 9.5 <= x <= 14.5:
            add(r, box(0.4, 0.012, 1.9, tex("sleeper", like=(46, 40, 34)),
                       center=(x, 0.066, 0)))
        else:
            add(r, box(0.4, 0.08, 1.9, tex("sleeper", like=(58, 50, 40)),
                       center=(x, 0.10, 0)))
    # platform
    add(r, box(42, 0.55, 5.0, tex("concrete", like=(62, 66, 74)), center=(0, 0.28, 5.2),
               seg=6))
    add(r, box(42, 0.06, 0.5, tex("concrete", like=(110, 108, 96)),
               center=(0, 0.58, 2.95)))
    # broken snow patches on the catch-side ballast
    for dx, dz, dw in ((8.6, 2.20, 0.9), (10.8, 2.35, 1.2),
                       (12.6, 2.10, 0.8), (14.2, 2.40, 1.0)):
        add(r, box(dw, 0.02, 0.5, tex("snow", like=(150, 162, 180)),
                   center=(dx, 0.068, dz)))
    if train:
        # Waiting passenger train.  The body/detail mesh is cached and only
        # translated by the departure offset; the glows stay sprites.
        tx = float(train_offset)
        _train_detail(r, tx)
        for cx in (-12.0, 0.0, 9.0, 15.0, 21.0):
            r.add_sprite((tx + cx, 2.45, -2.80),
                         _fx.window_glow(_fx.SODIUM, 2.4, 0.9, 0.16),
                         layer=_fx.FX_LAYER)
        if getattr(r, "backend", "") != "gl":   # GL: carriage pool, not a billboard
            for sx in (6.0, 11.0, 16.0):
                r.add_sprite((tx + sx, 0.10, -2.45),
                             _fx.window_glow(_fx.SODIUM, 2.4, 0.6, 0.16),
                             layer=_fx.FX_LAYER)
        r.add_sprite((tx + 10.9, 1.85, -2.80),
                     _fx.window_glow(_fx.SODIUM, 1.2, 1.4, 0.22),
                     layer=_fx.FX_LAYER)
        r.add_sprite((tx - 23.02, 2.0, -2.80),
                     _fx.beacon((228, 56, 42), 0.22, t, phase=0.29),
                     layer=_fx.FX_LAYER)
    # signal tower + floodlight masts
    add(r, box(1.2, 7.0, 1.2, tex("concrete", like=(44, 46, 50)), center=(18, 3.5, 8.5),
               seg=3))
    add(r, box(2.2, 1.6, 2.0, tex("metal_rib", like=(54, 56, 60), tint=True),
               center=(18, 7.8, 8.5), seg=3))
    add(r, box(1.2, 0.7, 0.06, (255, 203, 109), center=(18, 7.8, 7.45),
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
    r.add_sprite((19.0, 8.72, 7.9), _fx.beacon((240, 70, 50), 0.25, t,
                                              phase=0.55),
                 layer=_fx.FX_LAYER)
    for i, x in enumerate((-18, -6, 6, 18)):
        add(r, box(0.18, 8.0, 0.18, (38, 40, 46), center=(x, 4.0, 11.5)))
        add(r, box(0.7, 0.26, 0.5, _fx.SODIUM_PALE, center=(x, 8.0, 11.4),
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
    m.add(box(0.22, 0.10, 0.18, _fx.SODIUM_PALE, center=(-2.1, 1.22, 1.9),
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
    m.add(box(0.30, 0.06, 0.30, _fx.SODIUM_PALE, center=(1.0, 0.90, 1.1),
               emissive=True))
    add(r, m)
    warm_lamp(r, (1.0, 0.93, 1.1), t, seed=12, radius_m=1.2, intensity=0.5)
    add(r, box(0.4, 0.02, 0.3, (206, 202, 190), center=(0.1, 0.90, 1.5)))
    r.add_sprite((2.8, 1.6, 4.4), _fx.window_glow((70, 84, 110), 2.4, 2.2, 0.22),
                 layer=_fx.FX_LAYER)
