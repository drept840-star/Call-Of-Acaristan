"""3D kit for multiplayer: soldier rigs, guns and Outfitter portraits.

The 3D arena (``ui.arena_view3d``) and the Outfitter both build their bodies
here, so what the shop sells is the rig the match renders, the same promise
the 2D sprite path made (see ``ui.shop``).

A look is the catalog appearance from ``core.appearance``: identifiers in,
RGB out through ``appearance.resolve``. Nothing in this module accepts a
colour from outside the catalog.

Everything degrades to ``None``: a missing GL context, a missing mesh asset or
a renderer error makes the caller fall back to the 2D art, never crash a menu.
"""
import json
import math
import os

import pygame

from core import appearance

# Wire/sprite rig name -> engine3d.hold GRIPS key.
HOLD_BY_RIG = {"pistol": "pistol", "os12": "os12", "k9_smg": "k9", "shotgun": "shotgun"}
# Catalog finish key per rig (the shotgun has no finishes).
FINISH_BY_RIG = {"pistol": "pistol", "os12": "os12", "k9_smg": "k9", "shotgun": "shotgun"}
_ARMS = ("lsh_p", "lsh_r", "lsh_y", "lel", "rsh_p", "rsh_r", "rsh_y", "rel", "rifle_p", "rifle_y")
HAIR = (34, 28, 22)
BOOTS = (22, 20, 18)
BELT = (26, 24, 20)
GOGGLE = (18, 22, 26)
# K-9 asset: its pistol grip sits here in mesh space (missions.m6.yard3d.K9_GRIP).
K9_GRIP = (0.012, -0.100, -0.105)

_HUMS = {}
_GUNS = {}
_HOLDS = {}
_ICONS = {}
_STATE = {"ok": None}


def enabled():
    """3D multiplayer art on? ``ACA_MP_2D=1`` forces the 2D sprites."""
    if os.environ.get("ACA_MP_2D", "") == "1":
        return False
    if _STATE["ok"] is None:
        try:
            import engine3d  # noqa: F401
            _STATE["ok"] = True
        except Exception:
            _STATE["ok"] = False
    return _STATE["ok"]


def disable():
    """Turn the 3D art off for this run (a renderer failed)."""
    _STATE["ok"] = False


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


# ── guns ────────────────────────────────────────────────────────────────

def pistol_mesh():
    """Service pistol in the rig's gun frame: origin at the right hand on the
    grip, +z muzzle. Colours are appearance.GUN_BASE["pistol"] verbatim so a
    finish maps role for role."""
    from engine3d import Mesh, box, rot_x
    c = appearance.GUN_BASE["pistol"]
    m = Mesh()
    m.add(box(0.030, 0.105, 0.042, c["grip"]), m=rot_x(-14), t=(0.0, -0.040, -0.004))
    m.add(box(0.032, 0.032, 0.17, c["frame"], center=(0.0, 0.018, 0.075)))
    m.add(box(0.036, 0.030, 0.19, c["slide"], center=(0.0, 0.048, 0.080)))
    m.add(box(0.038, 0.006, 0.19, c["slide_edge"], center=(0.0, 0.034, 0.080)))
    m.add(box(0.014, 0.014, 0.02, c["barrel"], center=(0.0, 0.046, 0.180)))
    m.add(box(0.008, 0.008, 0.004, c["bore"], center=(0.0, 0.046, 0.191)))
    m.add(box(0.014, 0.012, 0.012, c["optic"], center=(0.0, 0.070, 0.020)))
    m.add(box(0.006, 0.020, 0.040, c["frame"], center=(0.0, -0.012, 0.050)))
    return m, 0.19


def _k9_mesh():
    from engine3d import Mesh
    from game.render3d_bridge import MESHES_DIR
    with open(os.path.join(MESHES_DIR, "k93d.mesh.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    m = Mesh()
    g = K9_GRIP
    m.verts = [(float(v[0]) - g[0], float(v[1]) - g[1], float(v[2]) - g[2]) for v in data["verts"]]
    m.faces = [(tuple(f[0]), tuple(f[1]), 2, True, False) for f in data["faces"]]
    muzzle = data.get("meta", {}).get("muzzle", (0.0, 0.083, 0.595))
    return m, float(muzzle[2]) - g[2]


def _base_gun(rig):
    from engine3d import os12_mesh, shotgun_mesh
    if rig == "pistol":
        return pistol_mesh()
    if rig == "k9_smg":
        try:
            return _k9_mesh()
        except Exception:
            from engine3d import rifle_mesh
            return rifle_mesh(), 0.62
    if rig == "shotgun":
        return shotgun_mesh(), 0.70
    return os12_mesh(), 0.64


def _finish_col(col, base, roles):
    """A face colour under a finish: the nearest base role's finish colour at
    the face's own brightness. Brightness, not RGB ratio, so a warm stock
    under a pale finish turns pale instead of drifting blue."""
    best, best_d = None, 1e9
    for role, rgb in base.items():
        d = sum((col[i] - rgb[i]) ** 2 for i in range(3))
        if d < best_d:
            best, best_d = role, d
    if best is None or roles[best] == base[best]:
        return col
    k = max(0.45, min(2.2, (_lum(col) + 6.0) / (_lum(base[best]) + 6.0)))
    t = roles[best]
    return tuple(min(255, int(c * k)) for c in t)


def gun(rig, finish=None):
    """(mesh, muzzle_z) for a rig name, recoloured by a finish id."""
    rig = rig if rig in HOLD_BY_RIG else "pistol"
    key = (rig, finish)
    if key in _GUNS:
        return _GUNS[key]
    from engine3d import Mesh
    mesh, muzzle = _base_gun(rig)
    gk = FINISH_BY_RIG.get(rig)
    if gk and finish and finish in appearance.FINISHES and finish != appearance.DEFAULT_FINISH_ID % gk:
        base = appearance.GUN_BASE[gk]
        roles = dict(base)
        for role, rgb in appearance.FINISHES[finish]["roles"].items():
            if role in roles:
                roles[role] = tuple(rgb)
        out = Mesh()
        out.verts = list(mesh.verts)
        out.faces = [(f[0], _finish_col(tuple(f[1][:3]), base, roles)) + tuple(f[2:])
                     for f in mesh.faces]
        mesh = out
    _GUNS[key] = (mesh, muzzle)
    return _GUNS[key]


# ── soldiers ────────────────────────────────────────────────────────────

def spec(look):
    """Humanoid spec for a catalog appearance."""
    res = appearance.resolve(look)
    uni = res["uniform"]
    out = dict(
        skin=res["skin"], hair=HAIR, jacket=uni, vest=res["kevlar"],
        pants=_mix(uni, (0, 0, 0), 0.22), boots=BOOTS, glove=res["kevlar_edge"],
        accent=res["kevlar_ridge"], ears=True, hair_style="crop", brow_t=2,
        pouches=True, belt=BELT, buckle=(120, 110, 80), armband=res["kevlar_ridge"],
        stubble_t=0.18, scale=1.0, bulk=1.06, iris=res["eyes"],
    )
    head = res["head"]
    if head == "head_peaked_cap":
        out["cap"] = res["helmet"]
    elif head == "head_beret":
        out["beret"] = res["helmet_arc"]
    elif head == "head_balaclava":
        out["beanie"] = res["helmet"]
        out["mask"] = res["helmet"]
    elif head == "head_goggles":
        out["helmet"] = res["helmet"]
        out["glasses"] = GOGGLE
    elif head == "head_heavy_helmet":
        out["helmet"] = res["helmet_rim"]
        out["mask"] = res["kevlar_edge"]
        out["bulk"] = 1.12
    else:
        out["helmet"] = res["helmet"]
    return out


def hum(look, rig):
    """Cached rig.Humanoid wearing ``look`` and carrying ``rig``'s gun."""
    look = appearance.normalize(look)
    rig = rig if rig in HOLD_BY_RIG else "pistol"
    gk = FINISH_BY_RIG.get(rig)
    finish = look["finish"].get(gk) if gk else None
    key = (look["palette"], look["head"], rig, finish)
    h = _HUMS.get(key)
    if h is None:
        from engine3d import Humanoid
        s = spec(look)
        h = Humanoid(s)
        mesh, muzzle = gun(rig, finish)
        h._rifle = mesh
        h._weapon = HOLD_BY_RIG[rig]
        h._muzzle_z = muzzle
        # GL caches rig templates by spec repr: every gun and finish needs its own.
        h._gl_spec_key = repr(sorted(s.items())) + "|mp|%s|%s" % (rig, finish)
        _HUMS[key] = h
    return h


def held(h, base, rig, mode="aim"):
    """``base`` (legs, spine) with the arms of the cached hold for ``rig``.

    One arm solve per (gun, mode) for the whole match: every soldier shares
    proportions, so the solve does not depend on the look."""
    from engine3d import POSES
    from engine3d.hold import hold_cached
    weapon = HOLD_BY_RIG.get(rig, "pistol")
    ref = POSES["ready"]
    key = (weapon, mode)
    arms = _HOLDS.get(key)
    if arms is None:
        try:
            arms = hold_cached(h, ref, weapon, mode, key=("mp3d", weapon, mode))
        except Exception:
            arms = dict(POSES["aim" if mode == "aim" else "ready"])
        _HOLDS[key] = arms
    out = dict(base)
    out.update((k, arms[k]) for k in _ARMS if k in arms)
    out["rifle_p"] = arms.get("rifle_p", 0.0) + base.get("spine", 0.0) - ref["spine"]
    return out


def warm(look=None):
    """Pay the arm solves up front (20-60 ms each), behind a menu."""
    h = hum(look or appearance.default_appearance(), "os12")
    from engine3d import POSES
    for rig in HOLD_BY_RIG:
        for mode in ("aim", "ready"):
            held(hum(look or appearance.default_appearance(), rig), POSES["stand"], rig, mode)
    return h


# ── portraits (the Outfitter) ───────────────────────────────────────────

def _light():
    from engine3d import Light
    return Light(direction=(-0.55, 0.72, 0.55), ambient=0.50, diffuse=0.72, sky=0.22,
                 tint=(1.0, 0.98, 0.94))


def render(size, eye, tgt, fov, draw_fn):
    """Render ``draw_fn(r)`` into a transparent ``size`` square. -> Surface or None."""
    if not enabled():
        return None
    try:
        from cutscenes import m6world3d as _w
        r, _buf = _w.rend(size, size)
        if r.objs:
            r.objs.clear()
            inv = getattr(r, "invalidate_static", None)
            if inv:
                inv()
        saved = (r.light, r.fog, r.fog_start, r.fog_end)
        r.light = _light()
        r.fog, r.fog_start, r.fog_end = (8, 12, 10), 80.0, 200.0
        r.set_lights([])
        r.set_camera(eye, tgt, fov)
        r.begin()
        draw_fn(r)
        out = pygame.Surface((size, size), pygame.SRCALPHA)
        out.fill((0, 0, 0, 0))
        r.flush(out)
        r.light, r.fog, r.fog_start, r.fog_end = saved
        return out
    except Exception:
        disable()
        return None


def _body_pose(h, rig, t):
    from engine3d import POSES
    pose = held(h, dict(POSES["stand"]), rig, "ready")
    a = t * 1.6
    pose["spine"] = pose.get("spine", 0.0) + 0.8 * math.sin(a)
    pose["head_y"] = pose.get("head_y", 0.0) + 6.0 * math.sin(a * 0.4)
    return pose


def portrait(look, rig, size, yaw=200.0, focus="body", t=0.0):
    """A soldier (``focus`` body|head) or a lone gun (``gun``) on alpha."""
    look = appearance.normalize(look)
    if focus == "gun":
        gk = FINISH_BY_RIG.get(rig)
        mesh, _mz = gun(rig, look["finish"].get(gk) if gk else None)

        # Spin about the gun's own centre and frame its widest radius, so a
        # turntable never swings the barrel or the stock out of the square.
        lo = [min(v[i] for v in mesh.verts) for i in range(3)]
        hi = [max(v[i] for v in mesh.verts) for i in range(3)]
        c = [(lo[i] + hi[i]) / 2.0 for i in range(3)]
        rad = max(0.06, max(math.hypot(v[0] - c[0], v[2] - c[2]) for v in mesh.verts))

        def draw(r):
            from engine3d import Mesh, rot_y
            m = Mesh([(v[0] - c[0], v[1] - c[1], v[2] - c[2]) for v in mesh.verts], mesh.faces)
            m = Mesh().add(m, m=rot_y(yaw - 180.0))
            r.add_dynamic(m.verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces])
        fov = 30.0
        dist = rad / (0.92 * math.tan(math.radians(fov / 2.0)))
        return render(size, (dist, dist * 0.14, 0.0), (0.0, 0.0, 0.0), fov, draw)
    h = hum(look, rig)

    def draw(r):
        r.add_humanoid(h, _body_pose(h, rig, t), (0.0, 0.0, 0.0), yaw, rifle_on=True)
    if focus == "head":
        return render(size, (0.45, 2.06, 1.22), (0.0, 1.70, 0.0), 30.0, draw)
    return render(size, (0.0, 1.35, 3.9), (0.0, 0.93, 0.0), 34.0, draw)


def icon(look, rig, size, focus="body", yaw=200.0):
    """Cached still portrait for a shop cell or a HUD slot."""
    key = (appearance.key_of(look), rig, int(size), focus, round(yaw, 1))
    if key not in _ICONS:
        _ICONS[key] = portrait(look, rig, int(size), yaw=yaw, focus=focus)
    return _ICONS[key]
