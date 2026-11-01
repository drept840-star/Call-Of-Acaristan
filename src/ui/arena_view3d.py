"""2.5D renderer for multiplayer arena matches.

A tilted chase camera over the same match ``ui.arena_view`` draws in 2D. The
rules stay where they were: ``missions.arena`` is headless and 2D (sim pixels
on the floor plane), the wire carries the same snapshots, and this module only
changes what a frame looks like. Everything that is not the world - HUD, kill
feed, loadout strip, reticle, audio, the shot feel timers - is inherited.

Sim pixels map onto the floor at ``K`` metres a pixel: x -> x, y (down the
screen) -> -z, so north on the 2D map is away from the camera. Walls are the
map's merged collision rects extruded, doorways (``+``) are waist-high cover,
players are box rigs from ``ui.mp3d`` wearing their catalog look and gun.

Aim: the mouse is unprojected onto a plane at gun height, so the cursor sits
on whatever it covers and the angle sent to the host is the same kind of
number the 2D view sent.

Any renderer error drops this view back to the 2D draw for the rest of the
run (``mp3d.disable``); a broken GPU never ends a match.
"""
import math

import pygame

from core.config import TILE_SIZE, WIDTH, HEIGHT
from core.state import STATE
from missions import arena as AR
from net import protocol as P
from ui import mp3d
from ui.arena_view import ArenaView, MUZZLE_FRAMES, color_for

K = 1.6 / TILE_SIZE              # metres per sim pixel: a tile is 1.6 m
RES = (640, 448)                 # internal buffer, x1.5625 to the 1000x700 canvas
WALL_H = 2.1
COVER_H = 0.95
AIM_H = 1.3                      # the mouse ray meets the floor at gun height
CAM_DIST = 21.0
CAM_PITCH = 58.0
CAM_FOV = 54.0
WALK_RAD_PER_M = 2.6
CORPSE_FALL_FRAMES = 36
PICKUP_COL = {"health": (90, 230, 130), "armour": (110, 170, 255)}
WEAPON_PICKUP_COL = {P.WPN_OS12: (235, 150, 70), P.WPN_K9: (200, 120, 235),
                     P.WPN_SHOTGUN: (176, 200, 112)}
PICKUP_RIG = {P.WPN_OS12: "os12", P.WPN_K9: "k9_smg", P.WPN_SHOTGUN: "shotgun"}

# Per-map dressing: texture + brightness for floor, walls and cover, the void
# colour past the walls, and the lamp colour.
THEMES = {
    "yard": dict(floor=("concrete", (58, 60, 64)), wall=("concrete", (104, 106, 112)),
                 cap=(70, 72, 78), cover=("crate", (112, 88, 58)), void=(10, 12, 16),
                 lamp=(255, 196, 120), key=(1.0, 0.97, 0.92)),
    "crossfire": dict(floor=("steel", (56, 60, 66)), wall=("brick", (98, 64, 50)),
                      cap=(66, 58, 54), cover=("metal_rib", (70, 76, 84)), void=(9, 10, 14),
                      lamp=(200, 220, 255), key=(0.94, 0.98, 1.06)),
    "foundry": dict(floor=("concrete", (64, 56, 50)), wall=("rust", (96, 60, 42)),
                    cap=(62, 50, 44), cover=("steel", (84, 88, 94)), void=(12, 9, 8),
                    lamp=(255, 150, 80), key=(1.06, 0.94, 0.84)),
}


def to3(x, y, h=0.0):
    """Sim pixel (x, y) at height h metres -> world point."""
    return (x * K, h, -y * K)


def yaw_of(angle_deg):
    """2D aim angle (degrees, y down) -> rig yaw (degrees, +z forward)."""
    a = math.radians(angle_deg)
    return math.degrees(math.atan2(math.cos(a), -math.sin(a)))


def make_view(map_name="yard"):
    """The match's view: 3D when the stack is there, else the 2D one."""
    if mp3d.enabled():
        try:
            return ArenaView3D(map_name)
        except Exception:
            mp3d.disable()
    return ArenaView(map_name)


class _Meta3D(object):
    __slots__ = ("x", "y", "phase", "speed")

    def __init__(self):
        self.x = self.y = None
        self.phase = 0.0
        self.speed = 0.0


class _Corpse3D(object):
    """A body in ``ArenaView._corpses``: frozen where it fell, aged by
    ``advance_corpses`` (``t``), dropped by ``sync`` on respawn."""
    __slots__ = ("x", "y", "yaw", "kind", "head_id", "rig_name", "t")

    def __init__(self, x, y, yaw, kind, head_id, rig_name):
        self.x, self.y, self.yaw, self.kind = x, y, yaw, kind
        self.head_id, self.rig_name = head_id, rig_name
        self.t = 0


class ArenaView3D(ArenaView):
    """``ArenaView`` with the world drawn in 3D. Same calls, same state."""

    def __init__(self, map_name="yard"):
        self._m3 = {}
        self._cam3 = None
        self._surf_size = (WIDTH, HEIGHT)
        self._crates = {}
        self._packed = {}
        super().__init__(map_name)
        mp3d.warm()

    def set_map(self, map_name):
        super().set_map(map_name)
        self._m3 = {}
        self.theme = THEMES.get(self.map_name, THEMES["yard"])
        self._lamps = self._lamp_spots()

    # ── aim ────────────────────────────────────────────────────────────

    def aim_point(self, mouse):
        """Screen point -> sim pixel under it at gun height, or None."""
        c = self._cam3
        if c is None:
            return None
        eye, right, up, fwd, focal, w, h = c
        sw, sh = self._surf_size
        bx = mouse[0] * w / float(sw)
        by = mouse[1] * h / float(sh)
        xs, ys = (bx - w / 2.0) / focal, (h / 2.0 - by) / focal
        d = [fwd[i] + right[i] * xs + up[i] * ys for i in range(3)]
        if d[1] >= -1e-4:
            return None
        t = (AIM_H - eye[1]) / d[1]
        return ((eye[0] + d[0] * t) / K, -(eye[2] + d[2] * t) / K)

    def aim_angle(self, mouse, origin):
        p = self.aim_point(mouse)
        if p is None:
            return super().aim_angle(mouse, origin)
        return math.degrees(math.atan2(p[1] - origin[1], p[0] - origin[0])) % 360.0

    # ── set ────────────────────────────────────────────────────────────

    def _lamp_spots(self):
        """Wall-top lamps over the longest inner walls, at most six."""
        inner = [w for w in self.walls
                 if w.left > 0 and w.top > 0 and w.right < self.map_w and w.bottom < self.map_h]
        inner.sort(key=lambda w: -(w.w * w.h))
        spots = [(w.centerx, w.centery) for w in inner[:4]]
        spots += [(self.map_w * 0.25, self.map_h * 0.5), (self.map_w * 0.75, self.map_h * 0.5)]
        return spots[:6]

    def _build_set(self, r):
        from cutscenes import m6world3d as _w
        from engine3d import box, quad_xz, disc_xz, tex
        th = self.theme
        floor = tex(th["floor"][0], like=th["floor"][1], tint=True)
        cap = tex(th["wall"][0], like=th["cap"], tint=True)
        wall = tex(th["wall"][0], like=th["wall"][1])
        cover = tex(th["cover"][0], like=th["cover"][1])
        _w.add(r, quad_xz(0.0, -self.map_h * K, self.map_w * K, 0.0, 0.0, floor, layer=0, seg=4.8))
        for wr in self.walls:
            cx, _, cz = to3(wr.centerx, wr.centery)
            _w.add(r, box(wr.w * K, WALL_H, wr.h * K, wall, center=(cx, WALL_H / 2.0, cz),
                          cols={"top": cap}, seg=3.2))
        for ri, row in enumerate(self.map_rows):
            for ci, ch in enumerate(row):
                x, y = ci * TILE_SIZE + TILE_SIZE / 2.0, ri * TILE_SIZE + TILE_SIZE / 2.0
                if ch in AR.PASSABLE_TILES:
                    cx, _, cz = to3(x, y)
                    s = TILE_SIZE * K
                    _w.add(r, box(s * 0.92, COVER_H, s * 0.92, cover,
                                  center=(cx, COVER_H / 2.0, cz)))
                elif ch in AR.SPAWN_TILES:
                    cx, _, cz = to3(x, y)
                    _w.add(r, disc_xz(cx, cz, 0.42, 0.012, _mix(th["floor"][1], (120, 150, 190), 0.35),
                                      n=12, layer=1))
        for lx, ly in self._lamps:
            cx, _, cz = to3(lx, ly)
            _w.add(r, box(0.34, 0.12, 0.34, (40, 40, 44), center=(cx, WALL_H + 0.06, cz)))
            _w.add(r, box(0.26, 0.05, 0.26, th["lamp"], center=(cx, WALL_H + 0.145, cz),
                          emissive=True))

    # ── camera ─────────────────────────────────────────────────────────

    def _camera(self, vw, vh):
        fx = self.cam_x + vw / 2.0
        fy = self.cam_y + vh / 2.0
        tx, _, tz = to3(fx, fy)
        p = math.radians(CAM_PITCH)
        tgt = (tx, 0.6, tz)
        eye = (tx, 0.6 + math.sin(p) * CAM_DIST, tz - math.cos(p) * CAM_DIST)
        return eye, tgt

    # ── draw ───────────────────────────────────────────────────────────

    def draw(self, surface, world, local_id, scoreboard=(), **hud):
        if not mp3d.enabled():
            return super().draw(surface, world, local_id, scoreboard, **hud)
        try:
            return self._draw3d(surface, world, local_id, scoreboard, hud)
        except Exception:
            import traceback
            traceback.print_exc()
            mp3d.disable()
            self._cam3 = None
            self._corpses.clear()        # 3D bodies; the 2D draw rebuilds its own
            self._corpse_age.clear()
            return super().draw(surface, world, local_id, scoreboard, **hud)

    def _draw3d(self, surface, world, local_id, scoreboard, hud):
        from cutscenes import m6fx3d as _fx
        from cutscenes import m6world3d as _w
        from engine3d import Light
        self._local_id = local_id
        self._respawn_remote = hud.get("respawn") or {}
        vw, vh = surface.get_width(), surface.get_height()
        self._surf_size = (vw, vh)
        self.update_camera(world, local_id, vw, vh)
        posed = self.sync(world)
        th = self.theme
        tm = self._anim_t * (1000.0 / 60.0)

        r, buf = _w.rend(*RES)
        saved = (r.light, r.fog, r.fog_start, r.fog_end, r.light_cap)
        try:
            r.light = Light(direction=(-0.35, 0.82, -0.45), ambient=0.46, diffuse=0.66,
                            sky=0.24, tint=th["key"])
            r.fog, r.fog_start, r.fog_end = th["void"], 34.0, 70.0
            r.light_cap = 8
            eye, tgt = self._camera(vw, vh)
            r.set_camera(eye, tgt, CAM_FOV)
            self._cam3 = (r.cam, r.right, r.up, r.fwd, r.focal, r.w, r.h)
            lights = [{"pos": to3(lx, ly, WALL_H + 0.6), "color": th["lamp"],
                       "intensity": 0.9, "range": 9.0} for lx, ly in self._lamps[:4]]
            flashes = []
            buf.fill(th["void"])
            r.begin()
            first = _w.static_scene(r, ("mp_arena3d", self.map_name))
            ok = False
            try:
                if first:
                    self._build_set(r)
                ok = True
            finally:
                _w.static_end(r, ok)
            self._draw_pickups3d(r, hud.get("pickups"), tm)
            tags = self._draw_players3d(r, posed, local_id, flashes, tm)
            self._draw_fx3d(r, tm)
            r.set_lights(lights + flashes, cap=8)
            r.flush(buf)
        finally:
            r.light, r.fog, r.fog_start, r.fog_end, r.light_cap = saved
        _fx.present_crisp(buf, surface)
        sx, sy = vw / float(RES[0]), vh / float(RES[1])
        for tag in tags:
            self._tag3d(surface, sx, sy, *tag)
        self.draw_hud(surface, world, local_id, scoreboard, self.map_name, **hud)
        from ui.hud import draw_combat_reticle
        me = world.get(local_id) if world else None
        if me is not None and me[6] != P.PS_DEAD and not getattr(self, "aim_frozen", False):
            draw_combat_reticle(surface, require_player=False)
        self._draw_feel(surface)
        return posed

    def _screen(self, p):
        """World point -> canvas pixel through the last frame's camera."""
        c = self._cam3
        if c is None:
            return None
        eye, right, up, fwd, focal, w, h = c
        d = (p[0] - eye[0], p[1] - eye[1], p[2] - eye[2])
        z = d[0] * fwd[0] + d[1] * fwd[1] + d[2] * fwd[2]
        if z <= 0.06:
            return None
        x = d[0] * right[0] + d[1] * right[1] + d[2] * right[2]
        y = d[0] * up[0] + d[1] * up[1] + d[2] * up[2]
        sw, sh = self._surf_size
        return ((w / 2.0 + x / z * focal) * sw / float(w), (h / 2.0 - y / z * focal) * sh / float(h))

    # ── pickups ────────────────────────────────────────────────────────

    def _crate(self, kind, value):
        key = (kind, value)
        if key not in self._crates:
            from engine3d import Mesh, box, tex
            m = Mesh()
            if kind == "weapon":
                col = WEAPON_PICKUP_COL.get(value, (200, 200, 200))
                m.add(box(0.62, 0.10, 0.62, (34, 36, 40), center=(0.0, 0.05, 0.0)))
                m.add(box(0.50, 0.02, 0.50, col, center=(0.0, 0.11, 0.0), emissive=True))
            else:
                col = PICKUP_COL.get(kind, (200, 200, 200))
                body = tex("crate", like=(150, 150, 146)) if kind == "health" else (40, 58, 92)
                m.add(box(0.46, 0.34, 0.46, body, center=(0.0, 0.17, 0.0)))
                if kind == "health":
                    for w, d in ((0.30, 0.09), (0.09, 0.30)):
                        m.add(box(w, 0.012, d, (200, 40, 40), center=(0.0, 0.346, 0.0),
                                  emissive=True))
                else:
                    m.add(box(0.40, 0.03, 0.40, col, center=(0.0, 0.355, 0.0), emissive=True))
            self._crates[key] = m
        return self._crates[key]

    def _put(self, r, mesh, pos, yaw=0.0, roll=0.0, scale=1.0):
        """A small rigid mesh at pos. On GL it is packed once and moved with
        numpy each frame; re-packing in Python cost ~4 ms a pickup."""
        from engine3d import Mesh, m_mul, rot_y, rot_z
        m = m_mul(rot_y(yaw), rot_z(roll))
        if not hasattr(r, "add_packed"):
            src = Mesh([(v[0] * scale, v[1] * scale, v[2] * scale) for v in mesh.verts], mesh.faces)
            out = Mesh().add(src, m=m, t=pos)
            r.add_dynamic(out.verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in out.faces])
            return
        import numpy as np
        key = (id(mesh), scale)
        arr = self._packed.get(key)
        if arr is None:
            verts = [(v[0] * scale, v[1] * scale, v[2] * scale) for v in mesh.verts]
            arr = r.pack(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces])
            if arr is None:
                return
            self._packed[key] = arr
        rot = np.asarray(m, dtype=np.float32).reshape(3, 3)
        out = arr.copy()
        out[:, 0:3] = arr[:, 0:3] @ rot.T + np.asarray(pos, dtype=np.float32)
        out[:, 6:9] = arr[:, 6:9] @ rot.T
        r.add_packed(out)

    def _draw_pickups3d(self, r, live, tm):
        from cutscenes import m6fx3d as _fx
        items = (live if live is not None
                 else [(px, py, kind, value, 0) for (px, py, kind, value) in AR.pickups(self.map_rows)])
        t = self._anim_t / 60.0
        for i, (px, py, kind, value, ready_at) in enumerate(items):
            x, _, z = to3(px, py)
            if live is not None and ready_at > self._host_tick:
                self._ghost_ring(r, x, z, ready_at)
                continue
            spin = (t * 70.0 + i * 40.0) % 360.0
            bob = 0.05 * math.sin(t * 2.4 + i)
            self._put(r, self._crate(kind, value), (x, 0.0, z), yaw=spin * 0.3)
            if kind == "weapon":
                mesh, _mz = mp3d.gun(PICKUP_RIG.get(value, "os12"))
                self._put(r, mesh, (x, 0.62 + bob, z), yaw=spin, scale=1.25)

    def _ghost_ring(self, r, x, z, ready_at):
        total = max(1, int(getattr(AR, "PICKUP_RESPAWN_TICKS", 720)))
        frac = 1.0 - min(1.0, max(0, int(ready_at) - int(self._host_tick)) / float(total))
        n = 20
        for i in range(n):
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 0.5) / n
            r.add_line3d((x + math.cos(a0) * 0.36, 0.03, z + math.sin(a0) * 0.36),
                         (x + math.cos(a1) * 0.36, 0.03, z + math.sin(a1) * 0.36),
                         (84, 90, 102), 1)
        for i in range(int(frac * n)):
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            r.add_line3d((x + math.sin(a0) * 0.46, 0.03, z + math.cos(a0) * 0.46),
                         (x + math.sin(a1) * 0.46, 0.03, z + math.cos(a1) * 0.46),
                         (120, 128, 144), 2)

    # ── players ────────────────────────────────────────────────────────

    def _draw_players3d(self, r, posed, local_id, flashes, tm):
        from cutscenes import m6fx3d as _fx
        from engine3d import POSES, blend, pose_run
        tags = []
        waiting = set(self._respawn_waiting or ())
        for pid in [p for p in self._m3 if p not in posed]:
            del self._m3[pid]
        for pid, (v, ent) in posed.items():
            m3 = self._m3.setdefault(pid, _Meta3D())
            look = self.look_for(pid)
            rig = getattr(v, "rig_weapon", None) or "pistol"
            h = mp3d.hum(look, rig)
            px, py = ent[2], ent[3]
            yaw = yaw_of(ent[4])
            if ent[6] == P.PS_DEAD or pid in waiting:
                head = v.look.get("head") or "head_kevlar"
                body = self._corpses.get(pid)
                if not isinstance(body, _Corpse3D) or body.head_id != head or body.rig_name != rig:
                    body = _Corpse3D(px, py, yaw, ("dead_back", "dead_front", "dead_side")[pid % 3],
                                     head, rig)
                    self._corpses[pid] = body
                    self._corpse_age[pid] = 0
                age = self._corpse_age.get(pid, 0)
                k = min(1.0, age / float(CORPSE_FALL_FRAMES))
                dyaw = body.yaw
                pose = blend("kneel", body.kind, k) if k > 0.4 else blend("stand", "kneel", k / 0.4)
                at = to3(body.x, body.y)
                if k >= 1.0:
                    r.add_sprite((at[0], 0.02, at[2]),
                                 _blood_pool(min(1.0, (age - CORPSE_FALL_FRAMES) / 90.0)), layer=0)
                    mesh, _mz = mp3d.gun(rig)
                    self._put(r, mesh, (at[0] + 0.5, 0.04, at[2] - 0.2), yaw=dyaw + 70.0, roll=90.0)
                r.add_humanoid(h, pose, at, dyaw, rifle_on=False)
                tags.append(("dead", pid, local_id, v, ent, at))
                m3.x = None
                continue
            if m3.x is None:
                m3.x, m3.y = px, py
            step = math.hypot(px - m3.x, py - m3.y) * K
            if step > 1.0:
                step = 0.0           # respawn or a correction: a jump, not a stride
            fwd = math.cos(math.radians(ent[4])) * (px - m3.x) + math.sin(math.radians(ent[4])) * (py - m3.y)
            m3.speed = m3.speed * 0.8 + step * 60.0 * 0.2
            m3.phase += step * WALK_RAD_PER_M * (1.0 if fwd >= 0.0 else -1.0)
            m3.x, m3.y = px, py
            moving = m3.speed > 0.6
            meta = self._view_meta.get(pid)
            reloading = ent[6] == P.PS_RELOADING
            base = pose_run(m3.phase, lean=4) if moving else dict(POSES["stand"])
            pose = mp3d.held(h, base, rig, "ready" if reloading else "aim")
            muzzle = meta.muzzle if meta is not None else 0
            if muzzle > 0:
                kick = muzzle / float(MUZZLE_FRAMES)
                pose["rifle_p"] = pose.get("rifle_p", 0.0) - 7.0 * kick
                pose["spine"] = pose.get("spine", 0.0) - 2.0 * kick
            at = to3(px, py)
            joints = r.add_humanoid(h, pose, at, yaw, rifle_on=True)
            if ent[8] & P.F_INVULNERABLE:
                self._ring(r, at[0], at[2], 0.55, (150, 210, 255))
            if pid == local_id:
                self._ring(r, at[0], at[2], 0.46, color_for(pid, local_id))
            if muzzle > 0 and joints:
                mz = joints.get("muzzle")
                if mz is not None:
                    flashes.append({"pos": mz, "color": (255, 196, 120), "intensity": 1.4,
                                    "range": 5.0})
                    r.add_sprite(mz, _fx.glow((255, 214, 150), 0.32, tm, core=(255, 250, 236),
                                              intensity=1.3, max_px=28), layer=_fx.FX_LAYER)
            tags.append(("live", pid, local_id, v, ent, at))
        return tags

    def _ring(self, r, x, z, rad, col):
        n = 16
        for i in range(n):
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            r.add_line3d((x + math.cos(a0) * rad, 0.03, z + math.sin(a0) * rad),
                         (x + math.cos(a1) * rad, 0.03, z + math.sin(a1) * rad), col, 1)

    def _tag3d(self, surface, sx, sy, state, pid, local_id, v, ent, at):
        head = self._screen((at[0], 2.15, at[2]))
        if head is None:
            return
        x, y = int(head[0]), int(head[1])
        col = color_for(pid, local_id)
        if state == "dead":
            if pid != local_id:
                foot = self._screen((at[0], 0.0, at[2])) or head
                self._draw_name_tag(surface, x, int(foot[1]) - 6 + 31, pid, col, dimmed=True)
                self._draw_remote_respawn(surface, x, int(foot[1]) - 4, pid, col)
            return
        lift = 38 if pid == local_id else 31
        self._draw_name_tag(surface, x, y - 24 + lift, pid, col)
        bw = 26
        pygame.draw.rect(surface, (18, 18, 22), (x - bw // 2 - 1, y - 4, bw + 2, 6))
        fill = max(0, min(bw, int(bw * v.hp / 100.0)))
        hp_col = ((90, 230, 130) if v.hp > 50 else (240, 200, 80) if v.hp > 25 else (235, 90, 80))
        pygame.draw.rect(surface, hp_col, (x - bw // 2, y - 3, fill, 4))

    # ── fx ─────────────────────────────────────────────────────────────

    def _draw_fx3d(self, r, tm):
        from cutscenes import m6fx3d as _fx
        from core.config import C_BULLET
        for b in self._bolts:
            f = min(1.0, b["t"] / float(max(1, b["life"])))
            hx = b["x"] + b["dx"] * b["travel"] * f
            hy = b["y"] + b["dy"] * b["travel"] * f
            back = min(b["travel"] * f, 34.0)
            head = to3(hx, hy, AIM_H)
            r.add_line3d(to3(hx - b["dx"] * back, hy - b["dy"] * back, AIM_H), head,
                         (255, 220, 140), 2, layer=4)
            r.add_sprite(head, _fx.glow(C_BULLET, 0.12, tm, intensity=0.9, max_px=10),
                         layer=_fx.FX_LAYER)
        for p in STATE.particles:
            r.add_sprite(to3(p.x, p.y, 0.25 + 0.03 * getattr(p, "life", 0)),
                         _dot(tuple(p.color[:3]), getattr(p, "size", 2)), layer=_fx.FX_LAYER)
        for c in STATE.casings:
            r.add_sprite(to3(c.x, c.y, 0.03), _dot((200, 160, 70), 2), layer=1)

    def _draw_feel(self, surface):
        floaters, self._floaters = self._floaters, []
        try:
            super()._draw_feel(surface)
        finally:
            self._floaters = floaters
        from ui.arena_view import _small_font
        font = _small_font()
        for f in self._floaters:
            if f[2] <= 0:
                continue
            p = self._screen(to3(f[0], f[1], AIM_H + 0.6))
            if p is None:
                continue
            surf = font.render(f[3], True, f[4])
            surface.blit(surf, (int(p[0] - surf.get_width() // 2), int(p[1])))


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _dot(col, size):
    def draw(s, sx, sy, scale, z):
        rad = max(1, int(size * 0.5 + scale * 0.02))
        pygame.draw.rect(s, col, (int(sx) - rad // 2, int(sy) - rad // 2, rad + 1, rad + 1))
    return draw


def _blood_pool(k):
    def draw(s, sx, sy, scale, z):
        w = int(scale * (0.5 + 0.7 * k))
        h = max(2, int(w * 0.75))
        if w < 2:
            return
        pygame.draw.ellipse(s, (82, 14, 16), (int(sx) - w // 2, int(sy) - h // 2, w, h))
    return draw
