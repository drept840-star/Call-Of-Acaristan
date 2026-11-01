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
    view; any renderer error turns 3D off for the rest of the run.
  * small draw helpers (``put``, ``ring``, ``dot``, ``blood_pool``).
"""
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

    def __init__(self, pitch, dist, fov, res=(640, 448), look_h=0.6):
        self.pitch, self.dist, self.fov = pitch, dist, fov
        self.res, self.look_h = res, look_h


# Per-mission camera, keyed by ``STATE.active_mission``. A mission is 2.5D
# when it has an entry here (and ``enabled()``); aim reads it from here so
# it works before the mission's draw module is imported.
CAMS = {
    # steeper than the arena so walls hide less, about the 2D view's width
    "MISSION1": Cam(64.0, 25.0, 50.0),
}


def enabled():
    """2.5D top-down on? ``ACA_TD_2D=1`` forces the 2D view."""
    if os.environ.get("ACA_TD_2D", "") == "1":
        return False
    if _STATE["ok"] is None:
        try:
            import engine3d  # noqa: F401
            _STATE["ok"] = True
        except Exception:
            _STATE["ok"] = False
    return _STATE["ok"]


def disable():
    """Turn 2.5D off for this run (a renderer failed)."""
    _STATE["ok"] = False


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
    cam = CAMS.get(getattr(STATE, "active_mission", None))
    return cam if cam is not None and enabled() else None


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


def armed(who, rig="pistol", **overrides):
    """Cached Humanoid of cast member ``who`` (``engine.anim.SPECS`` key)
    carrying the multiplayer mesh of ``rig`` (pistol / os12 / k9_smg /
    shotgun). ``overrides`` go to the spec (e.g. jacket=)."""
    from ui import mp3d
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


# ── draw helpers ───────────────────────────────────────────────────────

def put(r, mesh, pos, yaw=0.0, roll=0.0, scale=1.0, cache=None, pitch=0.0):
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
        r.add_dynamic(out.verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in out.faces])
        return
    import numpy as np
    key = (id(mesh), scale)
    arr = cache.get(key)
    if arr is None:
        verts = [(v[0] * scale, v[1] * scale, v[2] * scale) for v in mesh.verts]
        arr = r.pack(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces])
        if arr is None:
            return
        cache[key] = arr
    rot = np.asarray(m, dtype=np.float32).reshape(3, 3)
    out = arr.copy()
    out[:, 0:3] = arr[:, 0:3] @ rot.T + np.asarray(pos, dtype=np.float32)
    out[:, 6:9] = arr[:, 6:9] @ rot.T
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
    return draw


def blood_pool(k, col=(82, 14, 16)):
    """Sprite callback: a floor blood pool grown to k (0..1)."""
    def draw(s, sx, sy, scale, z):
        w = int(scale * (0.5 + 0.7 * k))
        h = max(2, int(w * 0.75))
        if w < 2:
            return
        pygame.draw.ellipse(s, col, (int(sx) - w // 2, int(sy) - h // 2, w, h))
    return draw
