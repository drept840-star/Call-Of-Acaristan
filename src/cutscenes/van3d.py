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

__all__ = [
    "draw_van_exterior_take",
    "draw_van_interior_take",
    "draw_van_volkov_photo_take",
    "draw_van_handoff_weapon_take",
    "draw_van_handoff_molotovs_take",
    "van3d_enabled",
    "prepare",
]

RES = 0.64                      # same internal scale as the PS2-look films
RW, RH = int(WIDTH * RES), int(SCENE_H * RES)
SPEED = 9.0                     # m/s the street slides past
WHEEL_R = 0.6441
FOG = (9, 11, 17)
_WHEELS = {10: (1.8, -1.2875), 11: (1.8, 1.2875), 12: (-2.1, -1.2875), 13: (-2.1, 1.2875)}
_HEAD, _TAIL = (3.12, 1.1), (-3.3, 1.2)
_LAMP_P, _LAMP_Z = 24.0, 6.9
_S = {"r": None, "buf": None, "van": None, "mesh": {}, "rows": {},
      "cr": None, "cbuf": None, "rigs": {}, "pistol": None, "molotov": None,
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


def _fx_mods():
    """Shared lazy import of the 3D sky/grade helpers (keeps W1 edge count minimal)."""
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx
    return _m5, _fx


def _draw(surface, t):
    from engine3d.core import Light
    _m5, _fx = _fx_mods()
    from cutscenes import weather3d
    if _S["r"] is None:
        _build()
    r, buf = _S["r"], _S["buf"]
    m, van = _S["mesh"], _S["van"]
    dist = SPEED * t * 0.001
    r.light = Light(direction=(-0.3, 0.8, -0.5), ambient=0.66, diffuse=0.28, sky=0.06,
                    tint=(0.82, 0.90, 1.10))
    r.light_albedo, r.light_gain = True, 3.1
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
        {"pos": (_HEAD[0] + 0.1, _HEAD[1], 0.0), "color": (255, 240, 190), "intensity": 1.65,
         "range": 20.0, "kind": "spot", "dir": (1.0, -0.13, 0.0), "cone": 0.86},
        {"pos": (_TAIL[0] - 0.2, _TAIL[1], 0.0), "color": (255, 44, 32), "intensity": 1.1,
         "range": 6.5},
        # Cool-blue wet street fill on the camera-facing flank so KRAP van armor & stripe pop
        {"pos": (1.8, 2.5, -5.4), "color": (168, 194, 232), "intensity": 0.85, "range": 12.0},
    ]
    for x in lamps[:2]:
        lights.append({"pos": (x, 5.0, _LAMP_Z - 1.45), "color": (255, 192, 114),
                       "intensity": 1.2, "range": 11.0})
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
                 _m5.wet_reflection((255, 40, 30), t, length_m=2.4, width_m=0.55,
                                    intensity=0.60), layer=2)
    r.add_sprite((_HEAD[0] + 4.4, 0.02, -0.3),
                 _m5.wet_reflection((255, 232, 182), t, seed=3, length_m=4.6, width_m=1.0,
                                    intensity=0.42), layer=2)
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


# ── 3D KRAP van cabin interior (van_interior / volkov_photo / handoffs) ──

_CABIN_FOG = (10, 11, 16)


def _cabin_rigs():
    if not _S["rigs"]:
        from cutscenes.cast3d import humanoid3d
        _S["rigs"]["vasile"] = humanoid3d("vasile")
        _S["rigs"]["biribel"] = humanoid3d("biribel")
    return _S["rigs"]


def _pistol_mesh():
    if _S["pistol"] is not None:
        return _S["pistol"]
    from engine3d.core import Mesh, box
    try:
        from game.render3d_bridge import load_mesh_asset
        verts, faces = load_mesh_asset("pistol")
        m = Mesh()
        m.verts = [tuple(v) for v in verts]
        m.faces = [(tuple(f[0]), tuple(f[1]), 2, False, False) for f in faces]
        _S["pistol"] = m
    except Exception:
        m = Mesh()
        m.add(box(0.036, 0.044, 0.21, (54, 58, 64), center=(0.0, 0.03, 0.07)))
        m.add(box(0.030, 0.030, 0.16, (30, 33, 38), center=(0.0, 0.0, 0.05)))
        m.add(box(0.032, 0.11, 0.055, (26, 28, 32), center=(0.0, -0.055, -0.01)))
        _S["pistol"] = m
    return _S["pistol"]


def _molotov_asset():
    """Real baked 3D Molotov glass bottle with a tucked draped cloth rag wick."""
    if _S["molotov"] is not None:
        return _S["molotov"]
    from engine3d.core import Mesh, box
    try:
        from game.render3d_bridge import load_mesh_asset
        verts, faces = load_mesh_asset("molotov")
        # Scale to ~0.27m glass bottle height with flat base resting cleanly at y = 0.0
        sc = 0.46
        m = Mesh()
        m.verts = [(v[0] * sc, (v[1] + 0.25) * sc, v[2] * sc) for v in verts]
        out_f = []
        for f in faces:
            idx, col = tuple(f[0]), tuple(f[1])
            grp = f[2] if len(f) > 2 else 0
            # Skip grp 1 (lit flame tip used when thrown); grp 0 already carries the bottle + wick
            if grp == 1:
                continue
            col = (min(255, int(col[0] * 0.95)), min(255, int(col[1] * 1.02)),
                   min(255, int(col[2] * 0.92)))
            out_f.append((idx, col, 2, False, False))
        m.faces = out_f
        _S["molotov"] = m
    except Exception:
        m = Mesh()
        m.add(box(0.088, 0.17, 0.088, (54, 108, 52), center=(0.0, 0.085, 0.0)))
        m.add(box(0.064, 0.045, 0.064, (64, 118, 60), center=(0.0, 0.19, 0.0)))
        m.add(box(0.034, 0.075, 0.034, (70, 124, 66), center=(0.0, 0.245, 0.0)))
        m.add(box(0.026, 0.055, 0.024, (206, 194, 168), center=(0.0, 0.305, 0.0)))
        _S["molotov"] = m
    return _S["molotov"]


def _molotov_mesh(cx, cy, cz, tilt_z=0.0, yaw=0.0):
    """Place one 3D Molotov bottle at (cx, cy, cz) with subtle tilt and yaw."""
    from engine3d.core import Mesh, m_mul, rot_y, rot_z
    out = Mesh()
    out.add(_molotov_asset(), m=m_mul(rot_y(yaw), rot_z(tilt_z)), t=(cx, cy, cz))
    return out


def _build_cabin():
    from engine3d import Renderer
    from engine3d.core import Mesh, box, quad_xz
    from cutscenes.ps2mat import mesh as textured
    r = Renderer(RW, RH, fog=_CABIN_FOG, fog_start=7.0, fog_end=26.0)
    r.light_cap = 8
    _S["cr"], _S["cbuf"] = r, pygame.Surface((RW, RH))

    def bake(m):
        r.bake(textured(m))

    # Floor (ribbed rubberized steel; extended forward to z = -3.05 for clean two-shot framing)
    bake(quad_xz(-1.9, -3.05, 1.9, 2.7, 0.0, (24, 26, 30), seg=0.9))
    for z in (-2.4, -1.6, -0.8, 0.0, 0.8, 1.6, 2.3):
        bake(box(3.4, 0.014, 0.06, (34, 38, 44), center=(0.0, 0.007, z)))

    # Side walls (subdivided for safe near-clipping) + structural ribs + gear racks
    for side in (-1, 1):
        bake(box(0.14, 2.26, 5.8, (34, 38, 46), center=(side * 1.88, 1.13, -0.18), seg=0.9))
        bake(box(0.06, 0.82, 5.7, (24, 28, 36), center=(side * 1.79, 0.44, -0.18), seg=0.9))
        # Subtle KRAP tactical blue trim stripe along upper side walls
        bake(box(0.03, 0.06, 5.6, (44, 96, 164), center=(side * 1.79, 1.64, -0.18), seg=1.2))
        for z in (-2.6, -1.5, -0.4, 0.7, 1.8, 2.5):
            bake(box(0.11, 2.22, 0.12, (46, 52, 62), center=(side * 1.76, 1.11, z)))
        # Side padded tactical benches
        bake(box(0.56, 0.46, 3.4, (28, 30, 36), center=(side * 1.48, 0.23, 0.48), seg=0.8))
        bake(box(0.60, 0.10, 3.45, (44, 48, 56), center=(side * 1.46, 0.50, 0.48), seg=0.8))
        bake(box(0.10, 0.58, 3.4, (38, 42, 50), center=(side * 1.74, 0.88, 0.48), seg=0.8))
        # Overhead grab rail + wall-mounted tactical gear pouch / rifle rack
        bake(box(0.04, 0.04, 2.8, (64, 70, 80), center=(side * 1.56, 2.02, 0.45)))
        bake(box(0.09, 0.22, 0.68, (46, 54, 44), center=(side * 1.75, 1.38, 1.65)))
        bake(box(0.07, 0.08, 0.78, (28, 30, 34), center=(side * 1.76, 1.42, -0.65)))

    # Ceiling (y = 2.26 for generous headroom) + structural ribs
    bake(box(3.8, 0.14, 5.9, (26, 30, 36), center=(0.0, 2.26, -0.18), seg=0.9))
    for z in (-2.4, -1.3, -0.2, 0.9, 2.0):
        bake(box(3.6, 0.10, 0.12, (44, 49, 58), center=(0.0, 2.16, z)))

    # Front bulkhead (z = -3.02) with tactical radio rack & route screen
    bake(box(3.8, 2.26, 0.18, (24, 28, 35), center=(0.0, 1.13, -3.02), seg=0.9))
    bake(box(3.5, 0.08, 0.02, (44, 98, 168), center=(0.0, 1.58, -2.92)))
    bake(box(0.86, 0.62, 0.30, (22, 26, 30), center=(-0.95, 1.18, -2.78)))
    bake(box(0.72, 0.18, 0.03, (28, 68, 52), center=(-0.95, 1.27, -2.62), emissive=True))
    for k in range(5):
        col = (80, 224, 118) if k != 3 else (228, 146, 54)
        bake(box(0.036, 0.036, 0.03, col, center=(-1.22 + k * 0.12, 1.06, -2.62), emissive=True))
    bake(box(0.98, 0.68, 0.06, (18, 22, 28), center=(0.15, 1.30, -2.90)))
    bake(box(0.88, 0.56, 0.02, (36, 54, 68), center=(0.15, 1.30, -2.86), emissive=True))

    # Rear bulkhead (z = 2.60) with twin armored window apertures looking out at the wet night city
    bake(box(3.8, 0.96, 0.18, (28, 32, 38), center=(0.0, 0.48, 2.60), seg=0.9))
    bake(box(3.8, 0.44, 0.18, (28, 32, 38), center=(0.0, 2.04, 2.60), seg=0.9))
    bake(box(0.56, 0.92, 0.18, (30, 34, 42), center=(-1.62, 1.40, 2.60)))
    bake(box(0.32, 0.92, 0.18, (30, 34, 42), center=(0.0, 1.40, 2.60)))
    bake(box(0.56, 0.92, 0.18, (30, 34, 42), center=(1.62, 1.40, 2.60)))
    # Armored door latch & window rubber gaskets
    bake(box(0.10, 0.24, 0.08, (64, 68, 74), center=(0.0, 0.72, 2.48)))
    for wx in (-0.75, 0.75):
        bake(box(1.18, 0.05, 0.21, (16, 18, 22), center=(wx, 0.97, 2.60)))
        bake(box(1.18, 0.05, 0.21, (16, 18, 22), center=(wx, 1.83, 2.60)))

    # Center briefing table (heavy bolted steel)
    bake(box(0.76, 0.06, 1.52, (48, 52, 60), center=(0.0, 0.68, 0.50)))
    bake(box(0.72, 0.02, 1.48, (34, 38, 44), center=(0.0, 0.715, 0.50)))
    for dz in (-0.54, 0.54):
        bake(box(0.10, 0.68, 0.10, (36, 40, 46), center=(0.0, 0.34, 0.50 + dz)))
        bake(box(0.48, 0.05, 0.12, (36, 40, 46), center=(0.0, 0.025, 0.50 + dz)))
    # Tactical olive gear crate under the rear bench
    bake(box(0.48, 0.30, 0.66, (54, 62, 46), center=(0.0, 0.15, 1.82)))
    bake(box(0.50, 0.04, 0.68, (70, 78, 58), center=(0.0, 0.31, 1.82)))


def _add_mesh(r, m):
    r.add_dynamic(m.verts, _faces(m))


def _cabin_sit_pose(t, seed, upper):
    """Seated posture with gentle breathing/jostle (self-contained, no m6world3d import)."""
    sec = t * 0.001
    br = math.sin(sec * 2.1 + seed * 1.7)
    p = {
        "lhip_p": 86.0, "rhip_p": 86.0, "lkn": 90.0, "rkn": 90.0,
        "lhip_r": 6.0, "rhip_r": -6.0, "lift": 0.04,
        "spine": 6.0 + br * 1.4,
        "head_p": 4.0 + br * 1.2,
    }
    p.update(upper)
    return p


def _render_cabin(surface, t, mode="interior", item=None):
    from engine3d.core import Light, Mesh, box, rot_y, rot_z
    _m5, _fx = _fx_mods()
    from core.cutscene_registry import current_shot

    if _S["cr"] is None:
        _build_cabin()
    r, buf = _S["cr"], _S["cbuf"]
    sec = t * 0.001
    shot = current_shot() or {}
    spk = (shot.get("speaker") or "").upper()

    # Road vibration + swinging tactical dome lamp
    jolt = math.sin(sec * 8.4) * 0.007 + math.sin(sec * 19.2) * 0.003
    swing = math.sin(sec * 2.2) * 0.14 + math.sin(sec * 5.3) * 0.025
    lamp_pos = (swing, 2.00, 0.48)
    flick = 0.86 if (int(t) // 90) % 37 == 5 else 1.0

    # Passing sodium streetlight outside the rear window sweeps across the cabin
    pass_u = (sec * 0.55) % 1.0
    sweep_x = -6.0 + pass_u * 12.0
    sweep_i = max(0.0, 1.0 - abs(sweep_x) / 4.2) * 1.45

    r.light = Light(direction=(0.15, 0.85, -0.45), ambient=0.34, diffuse=0.40,
                    sky=0.05, tint=(0.86, 0.90, 1.02))
    r.light_albedo, r.light_gain = True, 1.85

    lights = [
        {"pos": lamp_pos, "color": (255, 168, 102), "intensity": 1.05 * flick, "range": 5.4},
        {"pos": (-0.65, 1.32, -1.55), "color": (106, 160, 198), "intensity": 0.34, "range": 3.8},
        {"pos": (0.65, 1.32, -1.55), "color": (106, 160, 198), "intensity": 0.30, "range": 3.8},
    ]
    if mode == "handoff":
        lights.append({"pos": (0.04, 1.36, 0.18), "color": (255, 220, 168), "intensity": 0.65,
                       "range": 2.6})
    if sweep_i > 0.05:
        lights.append({"pos": (sweep_x * 0.35, 1.50, 2.25), "color": (255, 186, 108),
                       "intensity": sweep_i * 0.72, "range": 5.2})
    r.set_lights(lights, cap=8)

    # Camera framing per beat — wide enough so BOTH Vasile & Biribel sit cleanly framed
    # with full heads and comfortable headroom, never cropped at the top or sides.
    if mode == "handoff":
        u = min(1.0, t / 1800.0)
        u = u * u * (3.0 - 2.0 * u)
        if item == "molotovs":
            eye = (0.38 - 0.10 * u, 1.30 - 0.06 * u + jolt, -0.78 + 0.08 * u)
            tgt = (0.02, 0.92, 0.48)
            fov = 44
        else:
            eye = (0.34 - 0.10 * u, 1.24 - 0.06 * u + jolt, -0.58 + 0.06 * u)
            tgt = (0.02, 0.80, 0.48)
            fov = 42
    elif mode == "photo":
        eye = (0.0, 1.40 + jolt, -2.04)
        tgt = (0.0, 1.18, 0.60)
        fov = 54
    else:
        if "BIRIBEL" in spk:
            eye = (-0.54, 1.38 + jolt, -1.58)
            tgt = (0.52, 1.20, 0.56)
            fov = 48
        else:
            k = min(1.0, t / 6500.0)
            eye = (0.12 - 0.16 * k, 1.38 + jolt, -2.06 + 0.14 * k)
            tgt = (-0.04, 1.18, 0.60)
            fov = 54

    _m5.set_cam(r, t, eye, tgt, fov, hh=0.016, seed=17)

    buf.fill((9, 12, 18))
    r.begin()
    r.add_static()

    # Layered scrolling wet night skyline & glowing windows outside the rear glass
    ext = Mesh()
    scroll = (sec * 4.8) % 6.0
    for i in range(-3, 5):
        bx = i * 1.95 - scroll * 0.9
        bh = 2.6 + ((i * 37) & 3) * 0.65
        ext.add(box(1.55, bh, 1.2, (15, 19, 28), center=(bx, bh * 0.5, 6.4)))
        for wy in (1.18, 1.54, 1.90):
            if wy < bh - 0.25 and ((i * 7 + int(wy * 10)) % 3 != 0):
                wcol = (224, 170, 96) if (i + int(wy * 5)) % 2 == 0 else (142, 178, 214)
                ext.add(box(0.24, 0.22, 0.04, wcol,
                            center=(bx - 0.30, wy, 5.76), emissive=True))
                ext.add(box(0.24, 0.22, 0.04, wcol,
                            center=(bx + 0.26, wy, 5.76), emissive=True))
    _add_mesh(r, ext)

    # Swinging tactical dome lamp fixture with protective wire cage
    lamp_m = Mesh()
    lamp_m.add(box(0.025, 0.18, 0.025, (42, 42, 44), center=(swing * 0.5, 2.11, 0.48)))
    lamp_m.add(box(0.26, 0.07, 0.14, (52, 48, 48), center=(swing, 2.02, 0.48)))
    lcol = (255, 124, 82) if flick > 0.9 else (164, 68, 48)
    lamp_m.add(box(0.20, 0.035, 0.09, lcol, center=(swing, 1.98, 0.48), emissive=True))
    _add_mesh(r, lamp_m)

    # Seated 3D actors: Vasile (left bench, facing Biribel/camera) & Biribel (right bench)
    rigs = _cabin_rigs()
    v_hum, b_hum = rigs["vasile"], rigs["biribel"]
    v_pose = _cabin_sit_pose(t, 1, {"spine": 6, "head_y": -14 if mode != "handoff" else -26,
                                    "head_p": 4 if mode != "handoff" else 22,
                                    "rsh_p": 24, "rel": 54, "lsh_p": 18, "lel": 44})
    b_pose = _cabin_sit_pose(t, 2, {"spine": 7, "head_y": 14 if mode != "handoff" else 22,
                                    "head_p": 4 if mode != "handoff" else 20,
                                    "rsh_p": 18, "rel": 48, "lsh_p": 18, "lel": 48})
    if mode == "handoff":
        u = min(1.0, t / 1200.0)
        u = u * u * (3.0 - 2.0 * u)
        v_pose["rsh_p"] = 32 + 26 * u
        v_pose["rel"] = 58 - 22 * u
        b_pose["rsh_p"] = 22 + 24 * u
        b_pose["rel"] = 56 - 20 * u

    from engine3d.rig import mouth_flap
    v_mouth = mouth_flap(t, 11) if "VASILE" in spk else 0.0
    b_mouth = mouth_flap(t, 23) if "BIRIBEL" in spk else 0.0
    v_hum.set_expression("stern", v_mouth)
    b_hum.set_expression("neutral", b_mouth)

    r.add_humanoid(v_hum, v_pose, (-0.88, 0.0, 0.64), 76.0, rifle_on=False)
    r.add_humanoid(b_hum, b_pose, (0.88, 0.0, 0.56), -78.0, rifle_on=False)

    # Table props (briefing folder + coffee thermos in interior; pistol case or 3D Molotov crate in handoffs)
    props = Mesh()
    if mode != "handoff":
        # Open Volkov dossier folder, clipped surveillance photo, pen & steel thermos
        props.add(box(0.30, 0.012, 0.38, (192, 174, 136), center=(-0.06, 0.73, 0.48)))
        props.add(box(0.11, 0.015, 0.14, (54, 58, 66), center=(0.0, 0.736, 0.44)))
        props.add(box(0.08, 0.19, 0.08, (64, 72, 82), center=(0.19, 0.82, 0.72)))
        props.add(box(0.084, 0.04, 0.084, (132, 138, 146), center=(0.19, 0.92, 0.72)))
    elif item == "weapon":
        u = min(1.0, t / 1100.0)
        u = 1.0 - (1.0 - u) ** 3
        slide_x = -0.22 + 0.28 * u
        # Open foam-lined hard sidearm case + hinged lid + chrome latches + 9mm ammo box
        props.add(box(0.38, 0.042, 0.26, (30, 34, 40), center=(slide_x, 0.745, 0.48)))
        props.add(box(0.34, 0.022, 0.22, (16, 18, 22), center=(slide_x, 0.768, 0.48)))
        props.add(box(0.38, 0.20, 0.032, (28, 32, 38), center=(slide_x, 0.85, 0.62)))
        for lx in (-0.11, 0.11):
            props.add(box(0.034, 0.026, 0.018, (158, 166, 176), center=(slide_x + lx, 0.752, 0.348)))
        # Spare 9mm magazine + brass cartridge tip
        props.add(box(0.032, 0.016, 0.11, (54, 58, 66), center=(slide_x + 0.09, 0.780, 0.53)))
        props.add(box(0.022, 0.012, 0.020, (206, 172, 78), center=(slide_x + 0.09, 0.786, 0.482)))
        # Compact 9x19mm cardboard box beside case
        props.add(box(0.11, 0.046, 0.08, (96, 86, 62), center=(slide_x + 0.26, 0.748, 0.52)))
        # Real 3D pistol asset laid flat on the foam
        pm = _pistol_mesh()
        p_rot = rot_y(78.0 + 8.0 * u)
        from engine3d.core import m_mul
        p_xf = m_mul(p_rot, rot_z(90.0))
        props.add(pm, m=p_xf, t=(slide_x - 0.02, 0.788, 0.46))
    elif item == "molotovs":
        u = min(1.0, t / 1100.0)
        u = 1.0 - (1.0 - u) ** 3
        slide_x = -0.20 + 0.26 * u
        # Detailed open wooden slat crate with corner posts + center divider + two real 3D Molotovs
        wood = (92, 68, 44)
        wood_d = (66, 48, 30)
        props.add(box(0.36, 0.025, 0.22, wood_d, center=(slide_x, 0.738, 0.48)))
        for dz in (-0.10, 0.10):
            props.add(box(0.36, 0.048, 0.018, wood, center=(slide_x, 0.774, 0.48 + dz)))
            props.add(box(0.36, 0.048, 0.018, wood, center=(slide_x, 0.836, 0.48 + dz)))
        for dx in (-0.172, 0.172):
            props.add(box(0.018, 0.13, 0.22, wood_d, center=(slide_x + dx, 0.805, 0.48)))
        props.add(box(0.016, 0.11, 0.19, wood_d, center=(slide_x, 0.795, 0.48)))
        props.add(_molotov_mesh(slide_x - 0.082, 0.752, 0.48, tilt_z=5.0, yaw=18.0))
        props.add(_molotov_mesh(slide_x + 0.082, 0.752, 0.48, tilt_z=-4.0, yaw=-26.0))
    _add_mesh(r, props)

    # Atmospheric sprites: dome lamp halo + passing sodium glare through rear glass + rain streaks
    lay = _fx.FX_LAYER
    r.add_sprite(lamp_pos, _fx.glow((255, 146, 92), 0.82, t, core=(255, 224, 174),
                                    intensity=0.88 * flick), layer=lay)
    if sweep_i > 0.10:
        r.add_sprite((sweep_x * 0.25, 1.40, 2.52),
                     _fx.glow((255, 192, 112), 1.55, t, intensity=0.62 * sweep_i), layer=lay)
    for i in range(22):
        rx = -1.25 + ((i * 0.41 + sec * 0.8) % 2.5)
        ry = 1.78 - ((i * 0.29 + sec * 1.9) % 0.80)
        r.add_line3d((rx, ry, 2.55), (rx - 0.03, ry - 0.13, 2.55), (132, 152, 182), 1, layer=3)

    r.flush(buf)
    _fx.grade_cine(buf)
    _fx.present_crisp(buf, surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_H)))

    # Crisp loadout header strip for handoff shots
    if mode == "handoff":
        from core.config import font_terminal_small, C_KRAP_BLUE
        label = (
            "LOADOUT TRANSFER // SERVICE SIDEARM // 9x19MM"
            if item == "weapon"
            else "LOADOUT TRANSFER // 2x MOLOTOV // FIELD EXPEDIENT"
        )
        tag = font_terminal_small.render(label, True, (186, 212, 232))
        bar = pygame.Surface((tag.get_width() + 28, tag.get_height() + 10), pygame.SRCALPHA)
        bar.fill((8, 12, 18, 185))
        pygame.draw.rect(bar, C_KRAP_BLUE, (0, 0, 4, bar.get_height()))
        pygame.draw.rect(bar, (58, 76, 98), bar.get_rect(), 1)
        surface.blit(bar, (36, SCENE_TOP + 22))
        surface.blit(tag, (50, SCENE_TOP + 27))


def draw_van_interior_take(surface, t):
    if van3d_enabled():
        try:
            _render_cabin(surface, t, mode="interior")
            return
        except Exception as e:
            _S["failed"], _S["err"] = True, e
            print(f"van3d: cabin 3D disabled, using 2D ({e!r})")
    from cutscenes.route12 import draw_van_interior
    draw_van_interior(surface, t)


def draw_van_volkov_photo_take(surface, t):
    if van3d_enabled():
        try:
            _render_cabin(surface, t, mode="photo")
            dim = pygame.Surface((WIDTH, SCENE_H), pygame.SRCALPHA)
            dim.fill((4, 6, 10, 96))
            surface.blit(dim, (0, SCENE_TOP))
            from cutscenes.engine import draw_volkov_dossier_overlay
            draw_volkov_dossier_overlay(surface, t)
            return
        except Exception as e:
            _S["failed"], _S["err"] = True, e
            print(f"van3d: photo 3D disabled, using 2D ({e!r})")
    from cutscenes.route12 import draw_van_interior
    from cutscenes.engine import draw_volkov_dossier_overlay
    draw_van_interior(surface, t)
    dim = pygame.Surface((WIDTH, SCENE_H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 70))
    surface.blit(dim, (0, SCENE_TOP))
    draw_volkov_dossier_overlay(surface, t)


def draw_van_handoff_weapon_take(surface, t):
    if van3d_enabled():
        try:
            _render_cabin(surface, t, mode="handoff", item="weapon")
            return
        except Exception as e:
            _S["failed"], _S["err"] = True, e
            print(f"van3d: handoff 3D disabled, using 2D ({e!r})")
    from cutscenes.route12 import draw_van_handoff
    draw_van_handoff(surface, t, item="weapon")


def draw_van_handoff_molotovs_take(surface, t):
    if van3d_enabled():
        try:
            _render_cabin(surface, t, mode="handoff", item="molotovs")
            return
        except Exception as e:
            _S["failed"], _S["err"] = True, e
            print(f"van3d: handoff 3D disabled, using 2D ({e!r})")
    from cutscenes.route12 import draw_van_handoff
    draw_van_handoff(surface, t, item="molotovs")


from core.cutscene_registry import register_scene_renderer as _register  # noqa: E402

_register("van_exterior", draw_van_exterior_take)
_register("van_interior", draw_van_interior_take)
_register("van_volkov_photo", draw_van_volkov_photo_take)
_register("van_handoff_weapon", draw_van_handoff_weapon_take)
_register("van_handoff_molotovs", draw_van_handoff_molotovs_take)
