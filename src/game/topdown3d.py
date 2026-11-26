"""Shared 2.5D host for the top-down game: camera, sim<->world mapping, aim.

The top-down missions and the multiplayer arena keep their rules in 2D sim
pixels; only the frame changes. This module owns what every 2.5D view needs
and nothing mission-specific:

  * ``K`` / ``to3`` / ``yaw_of`` - sim pixel (x, y) to the floor plane at K
    metres a pixel, x -> x, y (down the screen) -> -z, so north on the map
    is away from the camera.
  * ``Cam`` presets and ``View`` - a camera snapshot built from pure math
    (the same basis ``engine3d.Renderer.set_camera`` builds), so aim and
    label projection work without touching the renderer.
  * ``enabled`` / ``disable`` - ``ACA_TD_2D=1`` forces the 2D top-down
    view; a renderer error drops to 2D for a few seconds (logged to
    ``crash_reports/td3d``), and repeated errors turn 3D off for the run.
  * small draw helpers (``put``, ``ring``, ``dot``, ``blood_pool``).
"""
from collections import OrderedDict
import math
import os

import pygame

from core.config import TILE_SIZE, WIDTH, HEIGHT

K = 1.6 / TILE_SIZE              # metres per sim pixel: a tile is 1.6 m

_STATE = {"ok": None}


class Cam(object):
    """A fixed north-up chase camera: pitch (deg down), distance (m) from
    the focus, horizontal fov (deg), internal buffer size, focus height."""
    __slots__ = ("pitch", "dist", "fov", "res", "look_h")

    def __init__(self, pitch, dist, fov, res=(WIDTH, HEIGHT), look_h=0.6):
        self.pitch, self.dist, self.fov = pitch, dist, fov
        self.res, self.look_h = res, look_h


# Per-mission camera, keyed by ``STATE.active_mission``. A mission is 2.5D
# when it has an entry here (and ``enabled()``); aim reads it from here so
# it works before the mission's draw module is imported.
CAMS = {
    # steeper than the arena so walls hide less, about the 2D view's width
    "MISSION1": Cam(64.0, 25.0, 50.0),
    "MISSION2": Cam(64.0, 25.0, 50.0),
    "MISSION3": Cam(64.0, 25.0, 50.0),
    "MISSION4": Cam(64.0, 25.0, 50.0),
    "MISSION5": Cam(64.0, 25.0, 50.0),
    "MISSION6": Cam(64.0, 25.0, 50.0),
}
# Optional per-mission gate: the mission is 2.5D only while its gate returns
# True (Mission 3 draws only the cell block in 3D; the other wings stay 2D).
GATES = {}


RETRY_MS = 3000                  # 2D cover after a renderer error before 3D retries
MAX_FAILS = 5                    # this many errors and 3D stays off for the run


def enabled():
    """2.5D top-down on? ``ACA_TD_2D=1`` or 3D Quality LOW forces the 2D view
    (about half the frame cost: the low-end PC path)."""
    from game.render3d_bridge import quality_3d  # lazy: settings bridge
    if os.environ.get("ACA_TD_2D", "") == "1" or quality_3d() <= 0:
        return False
    if _STATE["ok"] is None:
        try:
            import engine3d  # noqa: F401
            _STATE["ok"] = True
        except Exception:
            _STATE["ok"] = False
    from engine.core import now_ms as _now_ms
    if _STATE["ok"] and _STATE.get("until", 0) > _now_ms():
        return False
    return _STATE["ok"]


def disable():
    """A renderer failed: 2D for ``RETRY_MS``, then 3D again; off for the
    run after ``MAX_FAILS``. Called from the caller's ``except`` block, so
    the live exception goes to ``crash_reports/td3d``."""
    import sys
    from engine.core import now_ms as _now_ms
    fails = _STATE["fails"] = _STATE.get("fails", 0) + 1
    if fails >= MAX_FAILS:
        _STATE["ok"] = False
    _STATE["until"] = _now_ms() + RETRY_MS
    exc = sys.exc_info()[1]
    if exc is not None and fails <= MAX_FAILS:
        try:
            from core.state import STATE
            from engine.core import write_crash_report
            write_crash_report("crash_reports/td3d", exc,
                               extra={"mission": getattr(STATE, "active_mission", None), "fails": fails})
        except Exception:
            pass


def buffer_res(cam):
    """Internal 3D buffer size for ``cam`` at the player's 3D quality tier.
    View projections are buffer-size independent, so only the render target
    shrinks; slow PCs win back the readback, composite and upscale cost."""
    from game.render3d_bridge import render_scale_3d  # lazy: settings bridge
    s = render_scale_3d()
    w, h = cam.res
    return max(160, int(w * s) // 2 * 2), max(112, int(h * s) // 2 * 2)


def to3(x, y, h=0.0):
    """Sim pixel (x, y) at height h metres -> world point."""
    return (x * K, h, -y * K)


def to2(p):
    """World point -> sim pixel (x, y) on the floor."""
    return (p[0] / K, -p[2] / K)


def yaw_of(angle_deg):
    """2D aim angle (degrees, y down) -> rig yaw (degrees, +z forward)."""
    a = math.radians(angle_deg)
    return math.degrees(math.atan2(math.cos(a), -math.sin(a)))


def yaw_rad(angle_rad):
    """2D angle in radians (atan2, y down) -> rig yaw (degrees)."""
    return math.degrees(math.atan2(math.cos(angle_rad), -math.sin(angle_rad)))


def _norm(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


class View(object):
    """One frame's camera, looking at sim pixel (fx, fy).

    ``size`` is the canvas the frame is presented on; projections answer in
    canvas pixels."""

    def __init__(self, cam, fx, fy, size=(WIDTH, HEIGHT)):
        self.cam = cam
        self.size = size
        tx, _, tz = to3(fx, fy)
        p = math.radians(cam.pitch)
        self.tgt = (tx, cam.look_h, tz)
        self.eye = (tx, cam.look_h + math.sin(p) * cam.dist, tz - math.cos(p) * cam.dist)
        f = _norm((self.tgt[0] - self.eye[0], self.tgt[1] - self.eye[1], self.tgt[2] - self.eye[2]))
        r = _norm(_cross((0.0, 1.0, 0.0), f))
        self.right, self.up, self.fwd = r, _cross(f, r), f
        self.w, self.h = cam.res
        self.focal = (self.w / 2.0) / math.tan(math.radians(cam.fov) / 2.0)

    def apply(self, r):
        """Point renderer ``r`` through this view."""
        r.set_camera(self.eye, self.tgt, self.cam.fov)

    def screen(self, p):
        """World point -> canvas pixel, or None behind the camera."""
        e, f, rt, u = self.eye, self.fwd, self.right, self.up
        d = (p[0] - e[0], p[1] - e[1], p[2] - e[2])
        z = d[0] * f[0] + d[1] * f[1] + d[2] * f[2]
        if z <= 0.06:
            return None
        x = d[0] * rt[0] + d[1] * rt[1] + d[2] * rt[2]
        y = d[0] * u[0] + d[1] * u[1] + d[2] * u[2]
        sw, sh = self.size
        return ((self.w / 2.0 + x / z * self.focal) * sw / float(self.w),
                (self.h / 2.0 - y / z * self.focal) * sh / float(self.h))

    def screen_sim(self, x, y, h=0.0):
        """Sim pixel at height h -> canvas pixel, or None."""
        return self.screen(to3(x, y, h))

    def ground(self, mouse, h=0.0):
        """Canvas pixel -> sim pixel where its ray meets the plane at height
        h metres, or None when the ray never comes down."""
        sw, sh = self.size
        bx = mouse[0] * self.w / float(sw)
        by = mouse[1] * self.h / float(sh)
        xs, ys = (bx - self.w / 2.0) / self.focal, (self.h / 2.0 - by) / self.focal
        d = [self.fwd[i] + self.right[i] * xs + self.up[i] * ys for i in range(3)]
        if d[1] >= -1e-4:
            return None
        t = (h - self.eye[1]) / d[1]
        return ((self.eye[0] + d[0] * t) / K, -(self.eye[2] + d[2] * t) / K)


def active_cam():
    """The 2.5D camera of the running mission, or None (2D)."""
    from core.state import STATE
    key = getattr(STATE, "active_mission", None)
    cam = CAMS.get(key)
    gate = GATES.get(key)
    return cam if cam is not None and (gate is None or gate()) and enabled() else None


def mouse_world(h=0.0):
    """Sim pixel under the mouse at height h metres, seen from the shake-free
    follow camera (``STATE.camera_x/y``). 2D missions get the flat sum."""
    from core.config import get_scaled_mouse
    from core.state import STATE
    mx, my = get_scaled_mouse()
    cam = active_cam()
    if cam is not None:
        p = View(cam, STATE.camera_x + WIDTH / 2.0, STATE.camera_y + HEIGHT / 2.0).ground((mx, my), h)
        if p is not None:
            return p
    return mx + STATE.camera_x, my + STATE.camera_y


# ── cast ───────────────────────────────────────────────────────────────

_ARMED = {}
_HOLDS_WARMED = False


def armed(who, rig="pistol", **overrides):
    """Cached Humanoid of cast member ``who`` (``engine.anim.SPECS`` key)
    carrying the multiplayer mesh of ``rig`` (pistol / os12 / k9_smg /
    shotgun). ``overrides`` go to the spec (e.g. jacket=)."""
    global _HOLDS_WARMED
    from ui import mp3d
    if not _HOLDS_WARMED:
        _HOLDS_WARMED = True
        mp3d.warm()
    rig = rig if rig in mp3d.HOLD_BY_RIG else "pistol"
    key = (who, rig, tuple(sorted(overrides.items())))
    h = _ARMED.get(key)
    if h is None:
        from engine3d import Humanoid
        from cutscenes.cast3d import spec3d
        s = spec3d(who, **overrides)
        h = Humanoid(s)
        mesh, muzzle = mp3d.gun(rig)
        h._rifle = mesh
        h._weapon = mp3d.HOLD_BY_RIG[rig]
        h._muzzle_z = muzzle
        h._gl_spec_key = repr(sorted(s.items())) + "|td|%s" % rig
        _ARMED[key] = h
    return h


def held(h, base, rig, mode="aim"):
    """``base`` legs/spine with the cached arm hold for ``rig``."""
    from ui import mp3d
    return mp3d.held(h, base, rig, mode)


_SWAP_TUCK = {
    "rsh_p": -18.0, "rsh_r": 16.0, "rsh_y": 0.0, "rel": 58.0,
    "lsh_p": -10.0, "lsh_r": 14.0, "lsh_y": 0.0, "lel": 42.0,
    "rifle_p": 64.0, "rifle_y": -34.0,
}


def apply_swap_pose(pose, k):
    """Blend ``pose`` toward a hip/sling tuck by ``k`` (0..1) for 2.5D swaps."""
    if k <= 0.0:
        return pose
    k = min(1.0, float(k))
    out = dict(pose)
    spine = out.get("spine", 0.0)
    for jk, tgt in _SWAP_TUCK.items():
        if jk == "rifle_p":
            tgt = tgt + spine
        va = out.get(jk, 0.0)
        d = (tgt - va + 180.0) % 360.0 - 180.0
        out[jk] = va + d * k
    out["twist"] = out.get("twist", 0.0) - 18.0 * k
    out["spine"] = spine + 6.0 * k
    out["head_p"] = out.get("head_p", 0.0) + 8.0 * k
    out["head_y"] = out.get("head_y", 0.0) + 10.0 * k
    return out


# ── draw helpers ───────────────────────────────────────────────────────

def put(r, mesh, pos, yaw=0.0, roll=0.0, scale=1.0, cache=None, pitch=0.0, static=True):
    """A small rigid mesh at pos. On GL it is packed once (into ``cache``)
    and moved with numpy each frame; re-packing in Python cost ~4 ms a prop.
    ``pitch`` tumbles the mesh about its own x after the yaw (the molotov's
    end-over-end throw); 0 leaves the old yaw/roll-only transform."""
    from engine3d import Mesh, m_mul, rot_x, rot_y, rot_z
    rot = rot_y(yaw)
    if pitch:
        rot = m_mul(rot, rot_x(pitch))
    m = m_mul(rot, rot_z(roll))
    if cache is None or not hasattr(r, "add_packed"):
        src = Mesh([(v[0] * scale, v[1] * scale, v[2] * scale) for v in mesh.verts], mesh.faces)
        out = Mesh().add(src, m=m, t=pos)
        r.add_dynamic(out.verts, [(f[0], f[1], f[2], f[3], None, f[4], *f[5:]) for f in out.faces])
        return
    import numpy as np
    key = (id(mesh), scale)
    # walls and roof clutter sit still: reuse last frame's placed rows
    # (add_packed only reads them) instead of re-transforming ~100 a frame
    placed = pkey = None
    if static:
        placed = cache.get("placed")
        if placed is None:
            placed = cache["placed"] = OrderedDict()
        pkey = (key, tuple(pos), yaw, roll, pitch)
        out = placed.get(pkey)
        if out is not None:
            placed.move_to_end(pkey)
            r.add_packed(out)
            return
        if len(placed) >= 4096:
            placed.popitem(last=False)
    arr = cache.get(key)
    if arr is None:
        verts = [(v[0] * scale, v[1] * scale, v[2] * scale) for v in mesh.verts]
        arr = r.pack(verts, [(f[0], f[1], f[2], f[3], None, f[4], *f[5:]) for f in mesh.faces])
        if arr is None:
            return
        cache[key] = arr
    rot = np.asarray(m, dtype=np.float32).reshape(3, 3)
    out = arr.copy()
    out[:, 0:3] = arr[:, 0:3] @ rot.T + np.asarray(pos, dtype=np.float32)
    out[:, 6:9] = arr[:, 6:9] @ rot.T
    if placed is not None:
        placed[pkey] = out
    r.add_packed(out)


def ring(r, x, z, rad, col, n=16, width=1, y=0.03):
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        r.add_line3d((x + math.cos(a0) * rad, y, z + math.sin(a0) * rad),
                     (x + math.cos(a1) * rad, y, z + math.sin(a1) * rad), col, width)


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def dot(col, size):
    """Sprite callback: a hard square dot (particles, casings)."""
    def draw(s, sx, sy, scale, z):
        rad = max(1, int(size * 0.5 + scale * 0.02))
        pygame.draw.rect(s, col, (int(sx) - rad // 2, int(sy) - rad // 2, rad + 1, rad + 1))
    # the GL composite depth-tests only this box; without it every dot
    # masks the generic 3.5 m reach (a molotov burst is 200+ dots)
    draw.bounds_m = (0.03 + size * 0.01, 0.03 + size * 0.01)
    return draw


_DOT_UNIT = []


def dots(r, pts, layer=2):
    """Many ``dot``s at once: ``pts`` = [(pos, col, size)]. On GL they go as
    one batch of small emissive cubes; a sprite each cost a Python depth
    test per dot in the composite, and a molotov's burst is 300+ dots."""
    if not pts:
        return
    if hasattr(r, "add_particles"):
        from engine3d.particles import pack_dots
        arr = pack_dots(pts)
        if arr is not None:
            r.add_particles(arr)
        return
    if not hasattr(r, "add_packed"):
        for pos, col, size in pts:
            r.add_sprite(pos, dot(col, size), layer=layer)
        return
    import numpy as np
    if not _DOT_UNIT:
        from engine3d import box
        m = box(1.0, 1.0, 1.0, (255, 255, 255), emissive=True)
        _DOT_UNIT.append(r.pack(m.verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces]))
    unit = _DOT_UNIT[0]
    k = len(unit)
    pos = np.repeat(np.asarray([p[0] for p in pts], dtype=np.float32), k, axis=0)
    col = np.repeat(np.asarray([p[1][:3] for p in pts], dtype=np.float32), k, axis=0)
    side = np.repeat(np.asarray([0.04 + 0.018 * p[2] for p in pts], dtype=np.float32), k)
    out = np.tile(unit, (len(pts), 1))
    out[:, 0:3] = out[:, 0:3] * side[:, None] + pos
    out[:, 3:6] = col
    r.add_packed(out)


_SOFT = OrderedDict()
SQUASH = 0.86                      # a floor circle seen from the top-down cameras


def _soft_surf(key, w, h, build):
    s = _SOFT.get(key)
    if s is None:
        if len(_SOFT) >= 256:
            _SOFT.popitem(last=False)
        import numpy as np
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.hypot((x - (w - 1) / 2.0) / (w / 2.0), (y - (h - 1) / 2.0) / (h / 2.0))
        a = np.arctan2(y - (h - 1) / 2.0, x - (w - 1) / 2.0)
        rgb, alpha = build(d, a)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        s.fill(rgb + (0,))
        pygame.surfarray.pixels_alpha(s)[:] = np.clip(alpha, 0, 255).astype(np.uint8).T
        _SOFT[key] = s
    else:
        _SOFT.move_to_end(key)
    return s


def shadow(half_w, half_d=None, alpha=130):
    """Sprite callback: a soft drop shadow on the floor, ``half_w`` x
    ``half_d`` metres, darkest under the middle."""
    half_d = half_w * SQUASH if half_d is None else half_d * SQUASH

    def draw(s, sx, sy, scale, z):
        w, h = int(scale * half_w * 2) // 2 * 2, int(scale * half_d * 2) // 2 * 2
        if w < 4 or h < 4:
            return
        w, h = min(w, s.get_width() * 2), min(h, s.get_height() * 2)
        # one gradient per alpha, scaled to size: keyed by (w, h) every car
        # shadow built a fresh numpy surface each frame as the camera moved
        img = _soft_surf(("sh", 128, 128, alpha), 128, 128,
                         lambda d, a: ((0, 0, 0), alpha * (1.0 - d.clip(0, 1) ** 2) ** 1.4))
        img = pygame.transform.smoothscale(img, (w, h))
        s.blit(img, (int(sx) - w // 2, int(sy) - h // 2))
    draw._gl_spec = {
        "kind": "blob", "col": (0.0, 0.0, 0.0),
        "rx_m": float(half_w), "ry_m": float(half_d),
        "strength": float(alpha) / 255.0,
    }
    draw.bounds_m = (half_w + 0.1, half_d + 0.1)
    return draw


# Cast shadows. One stylised shadow direction for every top-down view, kept
# apart from the key light so the sun can stay put for readable wall faces:
# floor metres per metre of height - east, and a little toward the camera so
# the shadow is not hidden behind its own wall.
SHADOW_DIR = (0.55, -0.16)
SHADOW_COL = (4, 6, 16)
SUN_HALF = 22.0                  # GL sun map covers 44 m round the view's focus
CHAR_POP = 1.5                   # GL: top light + rim on rigs so they read off dark floors
TEX_SCALE = 1 / 3.0              # GL: 3x bigger texels, so walls and floors read as chunky pixels like the 3D missions


def _hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1])
                                     - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(p)
        return out
    lo, up = half(pts), half(reversed(pts))
    return lo[:-1] + up[:-1]


def _sweep(x0, x1, z0, z1, h):
    ox, oz = SHADOW_DIR[0] * h, SHADOW_DIR[1] * h
    c = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    return _hull(c + [(x + ox, z + oz) for x, z in c])


def _body_hull(x, z, h=1.75, r=0.26):
    ox, oz = SHADOW_DIR[0] * h, SHADOW_DIR[1] * h
    ring = [(x + r * math.cos(a * math.pi / 4.0), z + r * 0.8 * math.sin(a * math.pi / 4.0))
            for a in range(8)]
    head = [(x + ox * 0.98 + 0.14 * math.cos(a * math.pi / 4.0),
             z + oz * 0.98 + 0.14 * math.sin(a * math.pi / 4.0)) for a in range(8)]
    return _hull(ring + head)


_CAST = {}


def cast_shadows(r, alpha=100, col=SHADOW_COL):
    """Shared top-down cast shadows. Call once per frame just before
    ``r.flush``: every ground-standing mesh baked by ``m6world3d.static_scene``
    (``r.shadow_boxes``) and every humanoid queued this frame
    (``r.actor_log``) throws a hard shadow along ``SHADOW_DIR``. All of them
    go into one layer-1 sprite written without blending, so overlapping
    shadows do not double up; walls (layer 2) still hide it.

    On GL this is a real sun shadow map instead: every queued mesh and rig
    casts its true shape onto floors, walls and other actors."""
    fy = r.fwd[1] or -1e-6
    t = -r.cam[1] / fy
    focus = (r.cam[0] + r.fwd[0] * t, 0.0, r.cam[2] + r.fwd[2] * t)
    r.char_pop = CHAR_POP
    r.tex_scale = TEX_SCALE
    if r.set_sun_shadow((SHADOW_DIR[0], -1.0, SHADOW_DIR[1]), focus, SUN_HALF, alpha / 255.0):
        return
    import numpy as np
    boxes = getattr(r, "shadow_boxes", None) or ()
    st = _CAST.get(id(boxes))
    if st is None:
        _CAST.clear()
        hulls = [_sweep(*b) for b in boxes]
        st = _CAST[id(boxes)] = (hulls, [len(h) for h in hulls],
                                 np.asarray([p for h in hulls for p in h], dtype=np.float64).reshape(-1, 2))
    hulls, sizes, pts = st
    actors = getattr(r, "actor_log", ())
    if actors:
        body = _CAST.get("body")
        if body is None:
            body = _CAST["body"] = np.asarray(_body_hull(0.0, 0.0), dtype=np.float64)
        at = np.asarray([(p[0], p[2]) for p in actors], dtype=np.float64)
        pts = np.concatenate([pts, (body[None, :, :] + at[:, None, :]).reshape(-1, 2)])
        sizes = sizes + [len(body)] * len(actors)
    if not sizes:
        return
    # one vectorised pass of SoftwareRenderer.project over every hull corner
    # (a Python call per corner was ~2 ms a frame)
    W, H = r.w, r.h
    cam, rt, up, fw = r.cam, r.right, r.up, r.fwd
    dx, dy, dz = pts[:, 0] - cam[0], -cam[1], pts[:, 1] - cam[2]
    cz = dx * fw[0] + dy * fw[1] + dz * fw[2]
    bad = cz <= r.NEAR
    cz = np.where(bad, 1.0, cz)
    sx = W / 2 + (dx * rt[0] + dy * rt[1] + dz * rt[2]) / cz * r.focal
    sy = H / 2 - (dx * up[0] + dy * up[1] + dz * up[2]) / cz * r.focal
    starts = np.concatenate(([0], np.cumsum(sizes)[:-1]))
    keep = ~np.logical_or.reduceat(bad, starts)
    keep &= ~((np.maximum.reduceat(sx, starts) < 0) | (np.minimum.reduceat(sx, starts) > W)
              | (np.maximum.reduceat(sy, starts) < 0) | (np.minimum.reduceat(sy, starts) > H))
    idx = np.nonzero(keep)[0]
    if not len(idx):
        return
    i0 = int(idx[0])
    a = int(starts[i0])
    anchor = (float(pts[a, 0]), 0.02, float(pts[a, 1]))
    xy = np.stack((sx, sy), axis=1)
    scr = [xy[starts[i]:starts[i] + sizes[i]].tolist() for i in idx]
    sel = np.concatenate([np.arange(starts[i], starts[i] + sizes[i]) for i in idx])
    # composite only the shadows' box, not the whole frame
    x0 = max(0, int(math.floor(sx[sel].min())) - 1)
    y0 = max(0, int(math.floor(sy[sel].min())) - 1)
    x1 = min(W, int(math.ceil(sx[sel].max())) + 2)
    y1 = min(H, int(math.ceil(sy[sel].max())) + 2)
    if x1 <= x0 or y1 <= y0:
        return
    box = pygame.Rect(x0, y0, x1 - x0, y1 - y0)
    layer = _CAST.get(("surf", W, H))
    if layer is None:
        layer = _CAST[("surf", W, H)] = pygame.Surface((W, H), pygame.SRCALPHA)

    def draw(s, sx, sy, scale, z):
        layer.fill((0, 0, 0, 0), box)
        c = col + (alpha,)
        for p in scr:
            pygame.draw.polygon(layer, c, p)
        s.blit(layer, box.topleft, box)
    draw.bounds = (x0, y0, x1 - x0, y1 - y0)
    draw.strict_occ = True     # always mask: in a tight box an actor is under the 12% stray-pixel cut
    r.add_sprite(anchor, draw, layer=1, bias=-200.0)

def tac_ring(rad, col, shade=0.52):
    """Sprite callback: the tactical floor marker - a soft drop shadow, a
    faint glow just inside the ring, and a thin ring cut into eight
    segments."""
    def draw(s, sx, sy, scale, z):
        w = int(scale * rad * 2.5) // 2 * 2
        h = int(w * SQUASH) // 2 * 2
        if w < 6 or h < 6:
            return
        k = 1.25                       # ring radius 1.0 sits at d = 1 / k

        def build(d, a):
            import numpy as np
            seg = (np.mod(a, np.pi / 4.0) < np.pi / 4.0 * 0.74).astype(np.float32)
            dd = d * k
            ring = 205.0 * np.exp(-((dd - 1.0) / 0.045) ** 2) * seg
            glow = 46.0 * np.exp(-((dd - 0.88) / 0.16) ** 2)
            return col, np.maximum(ring, glow)

        sh = _soft_surf(("sh", w, h, int(shade * 255)), w, h,
                        lambda d, a: ((0, 0, 0), shade * 255 * (1.0 - (d * k * 1.1).clip(0, 1) ** 2) ** 1.4))
        img = _soft_surf(("ring", w, h, col), w, h, build)
        s.blit(sh, (int(sx) - w // 2, int(sy) - h // 2))
        s.blit(img, (int(sx) - w // 2, int(sy) - h // 2))

    def _gl_surf(sx, sy, scale, z):
        w = int(scale * rad * 2.5) // 2 * 2
        h = int(w * SQUASH) // 2 * 2
        if w < 6 or h < 6:
            return ()
        k = 1.25
        def build(d, a):
            import numpy as np
            seg = (np.mod(a, np.pi / 4.0) < np.pi / 4.0 * 0.74).astype(np.float32)
            dd = d * k
            ring = 205.0 * np.exp(-((dd - 1.0) / 0.045) ** 2) * seg
            glow = 46.0 * np.exp(-((dd - 0.88) / 0.16) ** 2)
            return col, np.maximum(ring, glow)
        sh = _soft_surf(("sh", w, h, int(shade * 255)), w, h,
                        lambda d, a: ((0, 0, 0), shade * 255 * (1.0 - (d * k * 1.1).clip(0, 1) ** 2) ** 1.4))
        img = _soft_surf(("ring", w, h, col), w, h, build)
        x0, y0 = int(sx) - w // 2, int(sy) - h // 2
        return (("ring_sh", w, h, int(shade * 255)), sh, x0, y0, w, h, False), \
               (("ring", w, h, col), img, x0, y0, w, h, False)
    draw._gl_surf = _gl_surf
    draw.bounds_m = (rad * 1.3, rad * 1.2)
    return draw


def blood_pool(k, col=(82, 14, 16)):
    """Sprite callback: a floor blood pool grown to k (0..1)."""
    def draw(s, sx, sy, scale, z):
        w = int(scale * (0.5 + 0.7 * k))
        h = max(2, int(w * 0.75))
        if w < 2:
            return
        pygame.draw.ellipse(s, col, (int(sx) - w // 2, int(sy) - h // 2, w, h))
    r_m = 0.25 + 0.35 * k
    draw._gl_spec = {
        "kind": "blob", "col": (col[0] / 255.0, col[1] / 255.0, col[2] / 255.0),
        "rx_m": float(r_m), "ry_m": float(r_m * 0.75), "strength": 1.0, "hard": True,
    }
    draw.bounds_m = (0.3 + 0.35 * k, 0.25 + 0.3 * k)
    return draw


def add_player_rim(r, flashes, x, y, angle=None, spot=False):
    """Add a cool upper-left rim light (and optional tactical spot beam on GL)."""
    px3, _, pz3 = to3(x, y)
    if hasattr(r, "add_packed"):
        flashes.insert(0, {
            "pos": (px3 - 0.48, 1.95, pz3 + 0.48),
            "color": (162, 212, 255), "intensity": 0.90, "range": 2.35,
        })
        if spot and angle is not None:
            dx, dy = math.cos(angle), math.sin(angle)
            flashes.insert(0, {
                "pos": (px3 + dx * 0.35, 1.35, pz3 - dy * 0.35),
                "color": (218, 236, 255), "intensity": 1.10, "range": 7.4,
                "kind": "spot", "dir": (dx, -0.22, -dy), "cone": 0.86, "shadow": True,
            })
    else:
        flashes.append({
            "pos": (px3, 1.7, pz3), "color": (182, 204, 232),
            "intensity": 0.85, "range": 3.0,
        })