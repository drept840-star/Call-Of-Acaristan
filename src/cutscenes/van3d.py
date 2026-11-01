"""van3d.py - engine3d take of the KRAP van establishing shot (scene ``van_exterior``).

The van is the imported ``krap_van`` mesh, parked at the world origin (nose +x)
while the street scrolls past it, so the parallax, the wheel roll and the
headlight pool on the wet road all come from real geometry and real lights.
Same contract as the other takes: ``fn(surface, t_ms)`` draws only the scene
band; captions stay with the CutscenePlayer.  When the 3D stack declines
(``ACARISTAN_CUTSCENE3D=0``, no asset, any exception) the painted 2D shot in
``cutscenes.route12`` draws instead and 3D stays off for the run.
"""
import math
import os
import random

import pygame

from core.config import SCENE_H, SCENE_TOP, WIDTH, font_location_sub
from cutscenes.route12 import draw_van_exterior as _draw_2d
from engine.text import T as _T

__all__ = ["draw_van_exterior_take", "van3d_enabled", "prepare"]

RES = 0.64                      # same internal scale as the PS2-look films
RW, RH = int(WIDTH * RES), int(SCENE_H * RES)
SPEED = 9.0                     # m/s the street slides past
WHEEL_R = 0.6441
FOG = (9, 11, 17)
_WHEELS = {10: (1.8, -1.2875), 11: (1.8, 1.2875), 12: (-2.1, -1.2875), 13: (-2.1, 1.2875)}
_HEAD, _TAIL = (3.12, 1.1), (-3.3, 1.2)
_LAMP_P, _LAMP_Z = 24.0, 6.9
_S = {"r": None, "buf": None, "van": None, "mesh": {}, "rows": {},
      "failed": False, "err": None}


def van3d_enabled():
    if os.environ.get("ACARISTAN_CUTSCENE3D", "1").strip() == "0":
        return False
    return not _S["failed"]


def _h(i, salt=0):
    return (math.sin((i + 1) * 12.9898 + salt * 78.233) * 43758.5453) % 1.0


def _faces(m):
    return [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces]


def _compact(verts, faces):
    """Faces of one part with their own, re-indexed vertex list."""
    remap, out_v, out_f = {}, [], []
    for idx, col, layer, ds, nrm, em in faces:
        new = []
        for i in idx:
            j = remap.get(i)
            if j is None:
                j = remap[i] = len(out_v)
                out_v.append(verts[i])
            new.append(j)
        out_f.append((tuple(new), col, layer, ds, nrm, em))
    return out_v, out_f


# ── street meshes (built once, drawn shifted along x) ──────────────────────
def _window(m, x0, x1, y0, y1, z, col):
    m.face([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], col, 1, True, True)


def _windows(m, rng, x0, x1, y0, y1, zf, step, size, prob):
    pal = [(150, 115, 60), (104, 90, 62), (86, 110, 128)]
    ww, wh = size
    x = x0 + step * 0.5
    while x + ww < x1 - 0.2:
        y = y0 + 1.1
        while y + wh < y1 - 0.4:
            if rng.random() < prob:
                col = rng.choice(pal)
                _window(m, x, x + ww, y, y + wh, zf - 0.03, col)
            y += step * 1.15
        x += step


def _strip(period, z_front, depth, hmin, hmax, wmin, wmax, seed, palette,
           win_prob, win_size, step, gap=(0.3, 1.6)):
    from engine3d.core import Mesh, box
    rng = random.Random(seed)
    m = Mesh()
    x = -period / 2.0
    while x < period / 2.0 - 0.5:
        w = rng.uniform(wmin, wmax)
        if x + w > period / 2.0 - 1.0:
            w = period / 2.0 - x
        h = rng.uniform(hmin, hmax)
        col = rng.choice(palette)
        cols = {"top": tuple(min(255, c + 8) for c in col)}
        m.add(box(w, h, depth, col, center=(x + w / 2, h / 2, z_front + depth / 2),
                  cols=cols, layer=1))
        _windows(m, rng, x + 0.2, x + w - 0.2, 0.0, h, z_front, step, win_size, win_prob)
        x += w + rng.uniform(*gap)
    return m


def _near_strip():
    from engine3d.core import Mesh, box
    pal = [(36, 22, 20), (18, 26, 38), (30, 30, 34), (20, 30, 24)]
    m = Mesh()
    for i, (cx, w, h) in enumerate(((-15, 6.0, 2.6), (-8, 6.0, 2.6), (-8, 6.0, 5.2),
                                     (3, 6.0, 2.6), (13, 7.0, 2.6))):
        y = h / 2 if h < 3 else 3.9
        hh = 2.6
        col = pal[i % 4]
        m.add(box(w, hh, 2.4, col, center=(cx, y if h >= 3 else hh / 2, 9.5),
                  cols={"top": tuple(c + 7 for c in col)}, layer=1))
        for rib in range(int(w / 0.6)):
            rx = cx - w / 2 + 0.3 + rib * 0.6
            m.add(box(0.08, hh - 0.2, 0.06, (6, 7, 9),
                      center=(rx, (y if h >= 3 else hh / 2), 8.27), layer=1))
    m.add(box(9.0, 5.2, 4.0, (13, 15, 20), center=(-1.5, 2.6, 13.0), layer=1))
    _windows(m, random.Random(5), -5.8, 2.8, 0.0, 5.2, 11.0, 1.6, (0.55, 0.7), 0.4)
    return m


def _lamp_mesh():
    from engine3d.core import Mesh, box
    m = Mesh()
    m.add(box(0.16, 5.4, 0.16, (9, 10, 12), center=(0, 2.7, _LAMP_Z), layer=1))
    m.add(box(0.1, 0.1, 1.6, (9, 10, 12), center=(0, 5.35, _LAMP_Z - 0.7), layer=1))
    m.add(box(0.5, 0.1, 0.3, (255, 214, 150), center=(0, 5.25, _LAMP_Z - 1.45),
              layer=1, emissive=True))
    return m


_POLE_P, _POLE_Z = 17.0, -5.6


def _pole_mesh():
    """Roadside pole between the camera and the van: the foreground parallax layer."""
    from engine3d.core import Mesh, box
    m = Mesh()
    m.add(box(0.2, 6.0, 0.2, (8, 9, 11), center=(0, 3.0, _POLE_Z), layer=1))
    m.add(box(0.12, 0.12, 1.8, (8, 9, 11), center=(0, 5.9, _POLE_Z + 0.8), layer=1))
    m.add(box(0.5, 0.1, 0.34, (255, 214, 150), center=(0, 5.8, _POLE_Z + 1.6),
              layer=1, emissive=True))
    return m


def _road_mesh():
    from engine3d.core import Mesh, box, quad_xz
    seg = 3.0 if "gl" in str(getattr(_S["r"], "backend", "")).lower() else 8.0
    m = Mesh()
    m.add(quad_xz(-150, -20, 150, 6.0, 0.0, (11, 13, 17), layer=0, seg=seg))
    m.add(box(300, 0.15, 3.2, (24, 25, 29), center=(0, 0.075, 7.6),
              cols={"top": (20, 21, 25)}, layer=1))
    m.add(box(300, 0.16, 0.3, (40, 42, 47), center=(0, 0.08, 6.1), layer=1))
    m.add(quad_xz(-150, -5.4, 150, -5.3, 0.012, (58, 60, 64), layer=1))
    return m


def _dash_mesh():
    """Lane dashes, one 6 m period; slid along x with the street."""
    from engine3d.core import Mesh, quad_xz
    m = Mesh()
    for k in range(-25, 25):
        x0 = k * 6.0
        m.add(quad_xz(x0, -3.1, x0 + 2.4, -2.95, 0.012, (74, 76, 80), layer=1))
    return m


class _Part:
    """A rigid mesh drawn at an x/y offset (GL: packed rows slid per frame)."""

    def __init__(self, verts, faces, centre=None):
        self.verts, self.faces, self.centre = verts, faces, centre
        self.rows = None
        self.rid = None

    def _packed(self, r):
        if self.rid != id(r):
            self.rows, self.rid = r.pack(self.verts, self.faces), id(r)
        return self.rows

    def put(self, r, dx=0.0, dy=0.0, spin=0.0):
        if hasattr(r, "add_packed"):
            rows = self._packed(r)
            if rows is None:
                return
            if dx or dy or spin:
                rows = rows.copy()
                if spin:
                    cx, cy, _cz = self.centre
                    c, s = math.cos(spin), math.sin(spin)
                    px, py = rows[:, 0] - cx, rows[:, 1] - cy
                    nx, ny = rows[:, 6].copy(), rows[:, 7].copy()
                    rows[:, 0], rows[:, 1] = cx + px * c - py * s, cy + px * s + py * c
                    rows[:, 6], rows[:, 7] = nx * c - ny * s, nx * s + ny * c
                rows[:, 0] += dx
                rows[:, 1] += dy
            r.add_packed(rows)
            return
        verts = self.verts
        if spin:
            cx, cy, _cz = self.centre
            c, s = math.cos(spin), math.sin(spin)
            verts = [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c, z)
                     for x, y, z in verts]
        if dx or dy:
            verts = [(x + dx, y + dy, z) for x, y, z in verts]
        r.add_dynamic(verts, self.faces)


def _van_parts():
    from game.render3d_bridge import load_mesh_asset
    verts, faces = load_mesh_asset("krap_van")
    vv = [tuple(v) for v in verts]
    body, wheels = [], {g: [] for g in _WHEELS}
    for idx, col, grp in faces:
        idx, col = tuple(idx), tuple(col)
        if grp == 1:
            body.append((idx, (255, 246, 208), 2, False, None, True))
        elif grp == 2:
            body.append((idx, (255, 70, 56), 2, False, None, True))
        elif grp in wheels:
            wheels[grp].append((idx, col, 2, False, None, False))
        else:
            body.append((idx, col, 3 if grp == 9 else 2, False, None, False))
    bv, bf = _compact(vv, body)
    parts = {"body": _Part(bv, bf)}
    for g, (wx, wz) in _WHEELS.items():
        wv, wf = _compact(vv, wheels[g])
        parts[g] = _Part(wv, wf, centre=(wx, WHEEL_R, wz))
    return parts


def _of_mesh(m):
    return _Part(m.verts, _faces(m))


def _build():
    from engine3d import Renderer
    from engine3d.core import Mesh, box, quad_xz
    r = Renderer(RW, RH, fog=FOG, fog_start=30.0, fog_end=110.0)
    r.light_cap = 8
    _S["r"], _S["buf"] = r, pygame.Surface((RW, RH))
    pal_far = [(13, 15, 20), (16, 17, 22), (18, 16, 18)]
    ground = Mesh().add(quad_xz(-150, 9.0, 150, 40.0, 0.0, (7, 8, 10), layer=0, seg=14.0))
    _S["mesh"] = {
        "road": _of_mesh(_road_mesh()),
        "ground": _of_mesh(ground),
        "dash": _of_mesh(_dash_mesh()),
        "far": _of_mesh(_strip(60.0, 24.0, 8.0, 5.0, 15.0, 3.5, 7.0, 91, pal_far,
                               0.42, (0.7, 0.9), 2.2)),
        "near": _of_mesh(_near_strip()),
        "lamp": _of_mesh(_lamp_mesh()),
        "pole": _of_mesh(_pole_mesh()),
    }
    _S["van"] = _van_parts()


_SOFT = {}


def _soft(px, alpha):
    key = (px, alpha // 6)
    s = _SOFT.get(key)
    if s is None:
        s = pygame.Surface((px * 2, px * 2), pygame.SRCALPHA)
        for i in range(px, 0, -2):
            a = int(alpha * (1.0 - i / px) ** 1.4)
            pygame.draw.circle(s, (104, 112, 126, a), (px, px), i)
        _SOFT[key] = s
    return s


def _puff(radius_m, alpha):
    def draw(s, sx, sy, scale, z):
        px = max(2, min(40, int(radius_m * scale)))
        s.blit(_soft(px, alpha), (int(sx - px), int(sy - px)))
    draw.bounds_m = (radius_m, radius_m)
    draw.bounds_cap_px = (40, 40)
    return draw


def _rain(r, t):
    """World-lattice streaks in the van's frame: leaning back with the speed,
    bright where the headlight beam crosses them."""
    sec = t * 0.001
    for i in range(190):
        front = i < 130
        u, v, w = _h(i, 1), _h(i, 2), _h(i, 3)
        x = 1.0 + (u * 2 - 1) * 17.0
        z = -2.1 - v * 9.0 if front else 2.0 + v * 5.0
        y = 9.5 - (sec * 11.0 + w * 9.5) % 9.5
        lit = 3.2 < x < 17.0 and abs(z) < 4.5 and y < 3.6
        col = (226, 228, 204) if lit else (92 + int(30 * w), 106 + int(30 * w), 140)
        r.add_line3d((x, y, z), (x - 0.22, y - 0.65, z), col, 1, layer=3 if front else 1)


REACH = 130.0                   # metres either side of the van that must stay dressed


def _copies(dist, period, reach=REACH):
    """Every x offset of a repeating strip that lands within ``reach`` m of the
    van.  The camera looks down the street at an angle, so two copies of a
    strip leave bare ground in view; this keeps the street continuous."""
    s = (-dist) % period
    k0 = int(math.floor((-reach - s) / period))
    k1 = int(math.ceil((reach - s) / period))
    return [s + k * period for k in range(k0, k1 + 1)]


def _tag_plate(surface):
    tag = font_location_sub.render(_T("route12.acaristan_city_slum_district"), True, (130, 150, 170))
    bg = pygame.Surface((tag.get_width() + 24, tag.get_height() + 10), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 150))
    surface.blit(bg, (42, SCENE_TOP + 24))
    surface.blit(tag, (54, SCENE_TOP + 29))


def _draw(surface, t):
    from engine3d.core import Light
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx
    from cutscenes import weather3d
    if _S["r"] is None:
        _build()
    r, buf = _S["r"], _S["buf"]
    m, van = _S["mesh"], _S["van"]
    dist = SPEED * t * 0.001
    r.light = Light(direction=(-0.3, 0.8, -0.5), ambient=0.62, diffuse=0.22, sky=0.05,
                    tint=(0.78, 0.88, 1.08))
    r.light_albedo, r.light_gain = True, 3.0
    # Low 3/4 front camera: orbits from the flank toward the nose and dollies
    # in over the shot, so the van turns in perspective instead of sliding by.
    k = min(1.0, t / 9000.0)
    k = k * k * (3.0 - 2.0 * k)
    az = 0.5 + 0.5 * k
    rad = 14.5 - 4.5 * k
    tgt = (0.6, 1.25, 0.0)
    eye = (tgt[0] + math.sin(az) * rad, 0.85 + 0.6 * k, tgt[2] - math.cos(az) * rad)
    _m5.set_cam(r, t, eye, tgt, 40, hh=0.03)

    bob = math.sin(t * 0.011) * 0.012 + math.sin(t * 0.027) * 0.006
    lamps = sorted(_copies(dist, _LAMP_P, 70.0), key=abs)
    lights = [
        {"pos": (_HEAD[0] + 0.1, _HEAD[1], 0.0), "color": (255, 240, 190), "intensity": 1.5,
         "range": 19.0, "kind": "spot", "dir": (1.0, -0.13, 0.0), "cone": 0.86},
        {"pos": (_TAIL[0] - 0.2, _TAIL[1], 0.0), "color": (255, 44, 32), "intensity": 1.0,
         "range": 6.0},
    ]
    for x in lamps[:2]:
        lights.append({"pos": (x, 5.0, _LAMP_Z - 1.45), "color": (255, 188, 110),
                       "intensity": 1.1, "range": 10.0})
    r.set_lights(lights, cap=8)

    top, bot = (6, 8, 13), (26, 19, 22)
    buf.fill(bot)
    _m5.night_sky(r, buf, t, top, bot, stars=0, clouds=2, sodium=(34, 20, 15),
                  mist=(20, 22, 30))
    r.begin()
    m["ground"].put(r)
    m["road"].put(r)
    m["dash"].put(r, dx=-(dist % 6.0))
    for x in _copies(dist, 60.0):
        m["far"].put(r, dx=x)
    for x in _copies(dist, 40.0):
        m["near"].put(r, dx=x)
    for x in lamps:
        m["lamp"].put(r, dx=x)
    poles = sorted(_copies(dist, _POLE_P, 70.0), key=abs)
    for x in poles:
        m["pole"].put(r, dx=x)

    van["body"].put(r, dy=bob)
    spin = -dist / WHEEL_R
    for g in _WHEELS:
        van[g].put(r, spin=spin)
    r.add_blob_shadow((0.0, 0.02, 0.0), 3.7, 1.5, 0.7)

    lay = _fx.FX_LAYER
    for z in (-0.8, 0.8):
        r.add_sprite((_HEAD[0] + 0.06, _HEAD[1], z),
                     _fx.glow((255, 236, 180), 1.0, t, core=(255, 250, 225), intensity=0.9),
                     layer=lay)
        r.add_sprite((_TAIL[0] - 0.05, _TAIL[1], z * 1.1),
                     _fx.glow((255, 40, 30), 0.9, t, flicker=0.02, seed=z, intensity=0.95),
                     layer=lay)
    r.add_sprite((8.0, 0.25, 0.0), _fx.haze((210, 200, 150), 5.0, t, seed=2, intensity=0.12),
                 layer=lay)
    for i, x in enumerate(lamps):
        r.add_sprite((x, 5.0, _LAMP_Z - 1.45), _fx.sodium_lamp(t, seed=i, radius_m=2.6),
                     layer=lay)
        r.add_sprite((x, 0.02, _LAMP_Z - 1.45),
                     _m5.wet_reflection((255, 180, 100), t, seed=i, length_m=3.2,
                                        width_m=0.5, intensity=0.4), layer=2)
    for i, x in enumerate(poles):
        r.add_sprite((x, 5.8, _POLE_Z + 1.6), _fx.sodium_lamp(t, seed=10 + i, radius_m=2.2),
                     layer=lay)
    r.add_sprite((_TAIL[0] - 0.4, 0.02, -0.9),
                 _m5.wet_reflection((255, 40, 30), t, length_m=2.2, width_m=0.5,
                                    intensity=0.55), layer=2)
    for i in range(6):
        age = ((t / 520.0) + i / 6.0) % 1.0
        r.add_sprite((-3.7 - age * 5.0, 0.5 + age * 0.4, -0.5 + 0.2 * math.sin(i * 2.0)),
                     _puff(0.35 + age * 0.9, int(70 * (1 - age) ** 1.6)), layer=3)
    _rain(r, t)
    r.flush(buf)
    _fx.grade_cine(buf)
    _fx.present_crisp(buf, surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_H)))
    _tag_plate(surface)


def prepare():
    """Warm the renderer and meshes before the shot clock starts."""
    if not van3d_enabled():
        return False
    try:
        if _S["r"] is None:
            _build()
        return True
    except Exception as e:
        _S["failed"], _S["err"] = True, e
        print(f"van3d: warmup failed, using 2D ({e!r})")
        return False


def draw_van_exterior_take(surface, t):
    if van3d_enabled():
        try:
            _draw(surface, t)
            return
        except Exception as e:  # any 3D failure -> permanent 2D fallback this run
            _S["failed"], _S["err"] = True, e
            print(f"van3d: 3D cutscene disabled, using 2D ({e!r})")
    _draw_2d(surface, t)


from core.cutscene_registry import register_scene_renderer as _register  # noqa: E402

_register("van_exterior", draw_van_exterior_take)
