"""Mission 1 escape cut (timeline m1.escape) in 3D.

``frame(surface, t)`` paints one frame of the cut at its 60 fps frame
clock ``t`` (0-1080) through a free camera over the M1 set
(``draw3d.render_world`` in film mode). Four beats, matching the shot
windows of ``draw._escape_scene``:

  * 0-135   the spark: Biribel leans into the cab, the starter catches
  * 135-300 low at the grille, headlights in the lens: "Hold on."
  * 300-500 outside the gate: the truck rams the van out through the
            container wall, the camera whips round to follow
  * 500-    crane up while the tail lights go into the rain

False when the renderer failed; the caller paints the 2D cut instead.
"""
import math
import random

import pygame

from core.config import HEIGHT, LETTER_H, TILE_SIZE, WIDTH
from core.state import STATE
from game import topdown3d as td
from missions.m1 import draw3d as _d3

FPS = 60.0
S_COUGH, S_CATCH = 1.25, 1.75      # starter turns over, engine catches
S_GO = 4.7                         # truck lurches
A1 = 6.0                           # launch acceleration, m/s^2
GAP = 2.7                          # truck nose to van nose when parked
S_HIT = S_GO + math.sqrt(2.0 * GAP / A1)
V1, A2, VMAX = 3.0, 7.0, 14.0      # after the hit
ROAD_Z = -49.6
GONE = {(27, 30), (27, 31)}        # the container gate
LAMP_XS = (50.0, 66.0, 82.0, 98.0, 114.0, 130.0)
LAMP_Z, LAMP_H = -45.8, 5.0
SODIUM = (255, 176, 96)
HEAD = (255, 230, 160)
TAIL = (226, 44, 32)


class _FreeView(td.View):
    """A camera from an explicit eye and target (no follow preset)."""

    def __init__(self, eye, tgt, fov, roll=0.0):
        self.cam = td.Cam(0.0, 1.0, fov, _d3.CAM.res)
        self.size = (WIDTH, HEIGHT)
        self.eye, self.tgt, self.roll = eye, tgt, roll
        f = td._norm((tgt[0] - eye[0], tgt[1] - eye[1], tgt[2] - eye[2]))
        r = td._norm(td._cross((0.0, 1.0, 0.0), f))
        self.right, self.up, self.fwd = r, td._cross(f, r), f
        self.w, self.h = self.cam.res
        self.focal = (self.w / 2.0) / math.tan(math.radians(fov) / 2.0)

    def apply(self, r):
        r.set_camera(self.eye, self.tgt, self.cam.fov, self.roll)


def _ease(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3.0 - 2.0 * k)


def _lerp3(a, b, k):
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(3))


def _park():
    """Parked truck centre (x, z), from the exfil tile."""
    pos = STATE.EXFIL_POS or (22 * TILE_SIZE + TILE_SIZE // 2, 31 * TILE_SIZE + TILE_SIZE // 2)
    x, _, z = td.to3(*pos)
    return x - 1.0, z


def _truck_x(s):
    """Distance the truck has rolled at cut second s."""
    if s <= S_GO:
        return 0.0
    if s <= S_HIT:
        return 0.5 * A1 * (s - S_GO) ** 2
    w = s - S_HIT
    w_cap = (VMAX - V1) / A2
    if w <= w_cap:
        return GAP + V1 * w + 0.5 * A2 * w * w
    return GAP + V1 * w_cap + 0.5 * A2 * w_cap ** 2 + VMAX * (w - w_cap)


def _stage(s):
    """Where the truck, van and gate container are at cut second s."""
    tx0, tz0 = _park()
    d = _truck_x(s)
    tx = tx0 + d
    tz = tz0 + (ROAD_Z - tz0) * _ease((tx - 40.0) / 15.0)
    dz = (ROAD_Z - tz0) * (_ease((tx + 0.5 - 40.0) / 15.0) - _ease((tx - 0.5 - 40.0) / 15.0))
    yaw = -math.degrees(math.atan2(dz, 1.0))
    nose = 0.0
    if S_GO < s < S_HIT:
        nose = 2.2 * math.sin(math.pi * min(1.0, (s - S_GO) / 0.5))
    w = s - S_HIT
    if 0.0 <= w < 0.4:
        nose -= 3.0 * math.sin(math.pi * w / 0.4)
    idle = 0.0 if s < S_COUGH else (0.6 if s < S_CATCH else 0.25)
    shake = idle * math.sin(s * 70.0) if s < S_HIT + 0.4 else 0.0
    out = {"truck": (tx, tz, yaw, nose + shake), "w": w}
    vx, vz, vyaw = tx0 + 1.9 + GAP + 1.8, -50.0, 180.0
    cx, cz, cyaw = 44.0, -49.6, 0.0
    if w > 0.0:
        wv = min(w, 1.5)
        vx += 9.0 * wv - 3.0 * wv * wv
        vz -= 3.0 * _ease(w / 0.9)
        vyaw -= 70.0 * _ease(w / 1.2)
        wc = min(w, 11.0 / 8.0)
        cx += 11.0 * wc - 4.0 * wc * wc
        cz += 3.4 * _ease(w / 1.0)
        cyaw = 38.0 * _ease(w / 1.1)
    out["van"] = (vx, vz, vyaw)
    out["box"] = (cx, cz, cyaw)
    return out


# ── exterior set ───────────────────────────────────────────────────────

def _ground_mesh():
    """The harbour road east of the gate: dark verge, road, dashes and
    lamp posts, with hard stepped pools baked under each lamp."""
    from engine3d import Mesh, box, quad_xz
    m = Mesh()
    x0, x1, z0, z1, cell = 44.8, 160.0, -70.0, -30.0, 1.6

    def shade(base, x, z):
        near = min(math.hypot(x - lx, z - LAMP_Z) for lx in LAMP_XS)
        k = 0.5 if near < 3.0 else 0.28 if near < 6.0 else 0.12 if near < 9.0 else 0.0
        return td.mix(base, SODIUM, k)

    nu = int((x1 - x0) / cell)
    nv = int((z1 - z0) / cell)
    road = (ROAD_Z - 3.0, ROAD_Z + 3.0)

    def colfn(i, j):
        x, z = x0 + (i + 0.5) * cell, z0 + (j + 0.5) * cell
        on = road[0] <= z <= road[1]
        return shade((20, 22, 25) if on else (14, 17, 15), x, z)

    m.add(quad_xz(x0, z0, x0 + nu * cell, z0 + nv * cell, 0.0, (16, 18, 20), seg=cell, colfn=colfn))
    for x in range(48, 160, 6):
        m.add(box(2.4, 0.02, 0.14, (120, 112, 84), center=(x, 0.02, ROAD_Z)))
    for lx in LAMP_XS:
        m.add(box(0.16, LAMP_H, 0.16, (40, 42, 44), center=(lx, LAMP_H / 2.0, LAMP_Z)))
        m.add(box(0.9, 0.12, 0.2, (40, 42, 44), center=(lx, LAMP_H, LAMP_Z - 0.4)))
        m.add(box(0.36, 0.08, 0.18, SODIUM, center=(lx, LAMP_H - 0.08, LAMP_Z - 0.75), emissive=True))
    for x in range(46, 160, 3):         # chain fence along the north verge
        m.add(box(0.06, 1.8, 0.06, (52, 54, 56), center=(x, 0.9, -43.6)))
    m.add(box(114.0, 0.04, 0.03, (52, 54, 56), center=(103.0, 1.75, -43.6)))
    return m


def _lamp_fx(r, tm, grade):
    from cutscenes import m6fx3d as _fx
    for lx in LAMP_XS:
        p = (lx, LAMP_H - 0.15, LAMP_Z - 0.75)
        r.add_sprite(p, _fx.glow(SODIUM, 0.5, tm, intensity=0.9, max_px=22), layer=_fx.FX_LAYER)
        grade.append(("pool", (lx, 0.0, LAMP_Z - 1.2), SODIUM, 4.5, 0.32))
        grade.append(("glow", p, SODIUM, 0.9, 0.4))


# ── props in motion ────────────────────────────────────────────────────

def _debris(r, w, at):
    """Container skin, glass and van trim thrown from the impact point."""
    if w <= 0.0:
        return
    rng = random.Random(3117)
    for i in range(36):
        vx = rng.uniform(3.0, 9.0)
        vz = rng.uniform(-3.5, 3.5)
        vy = rng.uniform(1.0, 5.0)
        size = rng.choice((0.12, 0.2, 0.32))
        col = rng.choice(((122, 44, 36), (92, 94, 96), (40, 52, 64), (34, 36, 40)))
        t_land = 2.0 * vy / 9.8
        ft = min(w, t_land)
        x = at[0] + vx * ft
        z = at[2] + vz * ft
        y = max(size * 0.3, at[1] + vy * ft - 4.9 * ft * ft)
        if w > t_land:                   # skid a little, then rest
            k = min(1.0, (w - t_land) / 0.4)
            x += vx * 0.15 * k
            z += vz * 0.15 * k
        spin = 0.0 if w > t_land + 0.4 else w * rng.uniform(300.0, 900.0)
        mesh = _d3._mesh(("esc_bit", size, col), lambda s=size, c=col: _d3._box(s, s * 0.35, s * 0.8, c))
        _d3._put(r, mesh, (x, y, z), yaw=i * 37.0 + spin, roll=spin * 0.6)


def _sparks(r, tm, at, n, reach, seed):
    rng = random.Random(seed + tm // 50)
    for _ in range(n):
        a = rng.uniform(0.0, 2.0 * math.pi)
        l = rng.uniform(0.2, reach)
        b = (at[0] + math.cos(a) * l, at[1] + rng.uniform(-0.2, 0.5) * l, at[2] + math.sin(a) * l)
        r.add_line3d(at, b, rng.choice(((255, 236, 170), (255, 180, 80))), 1)


def _actors(s, tm, grade):
    from cutscenes import m6fx3d as _fx
    from engine3d import blend

    def draw(r, flashes, tm_):
        _d3._draw_corpses(r, flashes, tm_)
        st = _stage(s)
        tx, tz, yaw, nose = st["truck"]
        _d3._put(r, _d3._mesh("esc_ground", _ground_mesh), (0.0, 0.0, 0.0))
        _lamp_fx(r, tm, grade)
        r.add_sprite((tx, 0.02, tz), td.shadow(2.1, 0.95, 150), layer=0)
        _d3._put(r, _d3._truck(), (tx, 0.0, tz), yaw=yaw, roll=nose)
        c, sn = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))

        def on_truck(lx, ly, lz):
            return (tx + lx * c + lz * sn, ly, tz - lx * sn + lz * c)

        if s >= S_CATCH:
            for side in (-0.42, 0.42):
                p = on_truck(1.85, 0.9, side)
                r.add_sprite(p, _fx.glow(HEAD, 0.35, tm, intensity=0.9, max_px=26), layer=_fx.FX_LAYER)
                q = on_truck(-1.9, 0.71, side)
                r.add_sprite(q, _fx.glow(TAIL, 0.22, tm, intensity=0.8, max_px=16), layer=_fx.FX_LAYER)
                grade.append(("glow", q, TAIL, 0.4, 0.35))
            flashes.append({"pos": on_truck(4.0, 0.8, 0.0), "color": HEAD, "intensity": 1.2, "range": 9.0})
            flashes.append({"pos": on_truck(-2.4, 0.7, 0.0), "color": TAIL, "intensity": 0.25, "range": 2.0})
        vx, vz, vyaw = st["van"]
        r.add_sprite((vx, 0.02, vz), td.shadow(2.0, 0.95, 150), layer=0)
        _d3._put(r, _d3._mesh("van", lambda: _d3._van((34, 36, 40))), (vx, 0.0, vz), yaw=vyaw)
        if st["w"] < 0.0:                # its lamps die in the crash
            for side in (-0.55, 0.55):
                p = (vx - 1.88, 0.66, vz + side)
                r.add_sprite(p, _fx.glow(HEAD, 0.4, tm, intensity=0.85, max_px=30), layer=_fx.FX_LAYER)
                grade.append(("glow", p, HEAD, 0.8, 0.45))
            flashes.append({"pos": (vx - 3.0, 0.7, vz), "color": HEAD, "intensity": 0.6, "range": 6.0})
        bx, bz, byaw = st["box"]
        var = next((b[5] for b in _d3._wall_boxes() if b[1] <= 27 < b[1] + b[3] and b[2] <= 30 < b[2] + b[4]), 0)
        box = _d3._mesh(("esc_gate", var), lambda: _d3._wall_mesh("container", 1.6, 3.2, _d3.CONTAINER_H, var))
        _d3._put(r, box, (bx, 0.0, bz), yaw=byaw)
        if s < 2.4:                      # Biribel at the cab, then straightening
            hum, _rig = _d3.player_hum()
            k = 0.6 * (1.0 - _ease((s - 1.8) / 0.4))
            r.add_humanoid(hum, blend("stand", "kneel_over", k), (tx + 1.05, 0.0, tz + 1.05),
                           td.yaw_rad(math.pi / 2.0), rifle_on=False)
        if 0.4 < s < S_CATCH + 0.2:      # the wires
            at = on_truck(1.2, 1.0, 0.5)
            hot = int(s * 9) % 3 != 0
            if hot:
                _sparks(r, tm, at, 5, 0.35, 11)
                flashes.append({"pos": at, "color": (255, 210, 140), "intensity": 0.8, "range": 2.5})
        w = st["w"]
        if 0.0 <= w < 0.6:
            at = (43.2, 1.0, -50.0)
            _sparks(r, tm, at, 18, 2.2 * (1.0 - w), 29)
            if w < 0.15:
                flashes.append({"pos": at, "color": (255, 220, 160), "intensity": 2.0, "range": 10.0})
                grade.append(("glow", at, (255, 220, 160), 3.0, 0.7 * (1.0 - w / 0.15)))
        _debris(r, w, (43.4, 1.1, -50.0))
    return draw


# ── cameras ────────────────────────────────────────────────────────────

def _camera(s):
    st = _stage(s)
    tx, tz = st["truck"][0], st["truck"][1]
    x0, z0 = _park()
    roll = 0.0
    if s < 2.25:                         # beat 1: in the aisle at the cab
        k = s / 2.25
        eye = (x0 + 5.4 - 0.8 * k, 1.7, -48.3)
        tgt = (x0 + 1.0, 1.0, -49.6)
        fov = 46.0 - 6.0 * k
    elif s < 5.0:                        # beat 2: low at the grille, the lamps in our face
        k = (s - 2.25) / 2.75
        eye = (x0 + 4.4, 0.75, z0 - 0.7)
        tgt = (x0 + 0.2, 1.25 - 0.1 * k, z0 + 0.3)
        fov = 58.0 - 8.0 * k
    elif s < 500 / FPS:                  # beat 3: outside the gate
        gate = (43.5, 1.2, -49.8)
        follow = (tx, 1.0, tz)
        k = _ease((st["w"] - 0.3) / 0.9)
        eye = (55.0, 1.9, -54.6)
        tgt = _lerp3(gate, follow, k)
        fov = 54.0
    else:                                # beat 4: crane up, the road goes on
        k = _ease((s - 500 / FPS) / 7.0)
        eye = _lerp3((57.0, 1.9, -54.2), (54.0, 13.0, -58.0), k)
        tgt = _lerp3((tx, 1.0, tz), (95.0, 0.0, -50.0), k)
        fov = 50.0
    w = st["w"]
    if 0.0 <= w < 0.8:                   # impact shake
        a = 0.25 * (1.0 - w / 0.8)
        eye = (eye[0], eye[1] + a * math.sin(s * 91.0), eye[2] + a * math.sin(s * 67.0))
        roll = 3.0 * (1.0 - w / 0.8) * math.sin(s * 53.0)
    elif S_COUGH <= s < S_GO:            # the engine through the floor
        a = 0.02 if s >= S_CATCH else 0.05
        eye = (eye[0], eye[1] + a * math.sin(s * 80.0), eye[2])
    return _FreeView(eye, tgt, fov, roll)


def _rain(surface, t):
    rng = random.Random(92)
    for _ in range(140):
        rx = (rng.randint(0, WIDTH) + t * 4) % WIDTH
        ry = (rng.randint(LETTER_H, HEIGHT - LETTER_H) + t * 11) % (HEIGHT - 2 * LETTER_H) + LETTER_H
        pygame.draw.line(surface, (74, 88, 108), (rx, ry), (rx - 4, ry + 16), 1)


def frame(surface, t):
    """Paint cut frame t in 3D. False when the renderer failed."""
    s = t / FPS
    grade = []
    v = _camera(s)
    film = {"gone": GONE, "grade": grade}
    if not _d3.render_world(surface, v, _actors(s, int(s * 1000), grade), film=film):
        return False
    _rain(surface, t)
    return True
