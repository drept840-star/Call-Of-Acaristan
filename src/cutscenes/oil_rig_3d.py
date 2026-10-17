"""True-3D Oil Rig Bombing cutscene (engine3d). Timeline-driven; VO gates shots.
Hook-up: replace the ATK_* frame-count triggers in missions/walking_sim.py with
OilRigCutscene.update(dt_ms) + .render(surface); call vo_started/vo_finished from voice."""
import math
from engine3d.core import (SoftwareRenderer, Light, Mesh, box, disc_xz, quad_xz,
                           lerp, smooth, v_lerp)

TAIL_MS = 1500
LEAD_MS = 1500
# (id, min_ms, vo_id, est_vo_ms)  -> duration = max(min_ms, vo_len + TAIL_MS)
SHOTS = [
    ("establish", 10000, None, 0),
    ("fisher_intro", 16000, "VO_185", 4000),
    ("craft_approach", 18000, "VO_186", 7000),
    ("strike_center", 14000, "VO_187", 3000),
    ("fisher_react", 10000, None, 0),
    ("strike_left", 16000, "VO_188", 3500),
    ("strike_right", 22000, "VO_189", 5000),
    ("craft_exit", 10000, None, 0),
    ("closing_a", 14000, "VO_190", 6000),
    ("closing_b", 10000, "VO_191", 3000),
    ("fade", 6000, None, 0),
]
RIGS = [(-40, 55, "left"), (0, 35, "center"), (45, 80, "right")]  # x, z depth
CAM = {  # shot -> (pos_a, pos_b, target_a, target_b, fov)
    "establish": ((-30, 3, -20), (-10, 6, 0), (0, 10, 60), (0, 12, 60), 55),
    "fisher_intro": ((2, 3.2, 3), (-2, 3, 4), (0, 2.8, 0), (0, 4, 40), 40),
    "craft_approach": ((-20, 6, 10), (25, 6, 20), (-10, 2, 40), (20, 2, 50), 50),
    "strike_center": ((0, 8, -10), (0, 8, -10), (0, 14, 35), (0, 14, 35), 45),
    "fisher_react": ((0.5, 3.1, 2), (0.2, 3.0, 1.2), (0, 3, 0), (0, 3, 0), 28),
    "strike_left": ((-30, 1, 20), (-34, 1, 24), (-40, 8, 55), (-40, 3, 55), 45),
    "strike_right": ((0, 4, -5), (0, 22, -25), (45, 10, 80), (20, 10, 70), 50),
    "craft_exit": ((0, 8, -5), (0, 8, -5), (10, 6, 90), (10, 6, 90), 60),
    "closing_a": ((5, 3, 3), (-5, 3, 3), (0, 3, 0), (0, 3, 0), 38),
    "closing_b": ((-4, 3, 2.5), (-4, 3.5, 2.2), (0, 3, 0), (0, 3, 0), 35),
    "fade": ((-4, 3.5, 2.2), (-4, 14, -12), (0, 3, 0), (0, 8, 50), 50),
}


def _rig_mesh():
    m = Mesh()
    steel, dark = (70, 74, 80), (45, 48, 54)
    for dx in (-5, 5):
        for dz in (-5, 5):
            m.add(box(1.2, 18, 1.2, steel, center=(dx, 3, dz)))
    m.add(box(16, 2, 16, dark, center=(0, 11, 0)))
    m.add(box(8, 5, 8, (90, 84, 76), center=(0, 14.5, 0)))
    m.add(box(0.5, 14, 0.5, steel, center=(6, 19, 0)))
    m.add(box(1, 1, 1, (255, 60, 40), center=(6, 26.5, 0), emissive=True))
    return m


class OilRigCutscene:
    def __init__(self, w, h, vo_len_ms=None):
        self.r = SoftwareRenderer(w, h, fog=(70, 50, 48), fog_start=40, fog_end=220)
        self.r.light = Light(direction=(-0.4, 0.5, 0.6), ambient=0.35, diffuse=0.7,
                             tint=(1.0, 0.72, 0.55))
        self.vo_len = vo_len_ms or {}   # {"VO_185": real_ms}; falls back to estimates
        self.rig_mesh = _rig_mesh()
        self.i, self.t, self.vo_fired = 0, 0, False
        self.finished = False

    def _dur(self, i):
        """max(shot_time, lead + vo_length + tail): 1.5s silence before and after the line."""
        sid, mn, vo, est = SHOTS[i]
        if not vo:
            return mn
        return max(mn, LEAD_MS + self.vo_len.get(vo, est) + TAIL_MS)

    def update(self, dt_ms):
        """Advance timeline. Returns a VO id exactly once, when its line should start."""
        if self.finished:
            return None
        self.t += dt_ms
        sid, _, vo, _ = SHOTS[self.i]
        event = None
        if vo and not self.vo_fired and self.t >= LEAD_MS:
            self.vo_fired = True
            event = vo
        if self.t >= self._dur(self.i) and (not vo or self.vo_fired):
            if self.i + 1 >= len(SHOTS):
                self.finished = True
            else:
                self.i += 1
                self.t = 0
                self.vo_fired = False
        return event

    def render(self, surface, ms):
        sid = SHOTS[self.i][0]
        k = smooth(min(1.0, self.t / self._dur(self.i)))
        pa, pb, ta, tb, fov = CAM[sid]
        r = self.r
        r.set_camera(v_lerp(pa, pb, k), v_lerp(ta, tb, k), fov)
        surface.fill((60, 38, 34))
        r.begin()
        # ocean: displaced grid
        sea = Mesh()
        n, size = 14, 260.0
        for gx in range(-n, n):
            for gz in range(-4, n):
                def y(x, z): return 0.5 * math.sin(x * .09 + ms * .0012) + .4 * math.sin(z * .13 + ms * .0009)
                x0, z0 = gx * size / n, gz * size / n
                x1, z1 = x0 + size / n, z0 + size / n
                sea.face([(x0, y(x0, z0), z0), (x0, y(x0, z1), z1), (x1, y(x1, z1), z1), (x1, y(x1, z0), z0)],
                         (22, 30, 40), layer=0, double=True)
        r.add_dynamic(sea.verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in sea.faces])
        hit = {"center": ("strike_center", 0), "left": ("strike_left", 0), "right": ("strike_right", 0)}
        order = [s[0] for s in SHOTS]
        for x, z, name in RIGS:
            struck = order.index(hit[name][0]) < self.i or (SHOTS[self.i][0] == hit[name][0] and self.t > 4000)
            sink = 0.0
            if struck:
                since = (self.t - 4000) if SHOTS[self.i][0] == hit[name][0] else 1e5
                sink = min(1.0, since / 9000) * (14 if name == "left" else 5 if name == "center" else 1)
            tilt = -sink * 0.0
            m = self.rig_mesh
            r.add_dynamic([(vx + x, vy - sink, vz + z) for vx, vy, vz in m.verts],
                          [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces])
            if struck:  # fire: emissive flickering boxes rising with depth-correct parallax
                for j in range(6):
                    fl = box(2.4 - j * .3, 2, 2.4 - j * .3, (255, 140 - j * 15, 30),
                             center=(x, 14 - sink + j * 1.8 + math.sin(ms * .01 + j) * .4, z), emissive=True)
                    r.add_dynamic(fl.verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in fl.faces])
        # attack craft
        if SHOTS[self.i][0] in ("craft_approach", "strike_center", "strike_left", "strike_right", "craft_exit"):
            cx = lerp(-60, 60, (self.i - 2 + k) / 6.0 % 1.0)
            c = box(3, 1, 6, (60, 64, 70), center=(cx, 5, 25))
            r.add_dynamic(c.verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in c.faces])
        r.flush(surface)
        # fade-to-black on last shot, letterbox
        if sid == "fade":
            ov = surface.copy(); ov.fill((0, 0, 0)); ov.set_alpha(int(255 * k)); surface.blit(ov, (0, 0))
        bar = int(surface.get_height() * 0.09)
        surface.fill((0, 0, 0), (0, 0, surface.get_width(), bar))
        surface.fill((0, 0, 0), (0, surface.get_height() - bar, surface.get_width(), bar))
