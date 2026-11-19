"""Live engine3d dioramas for the MISSION_COMPLETE dossier exhibit frame.

Each mission renders an isolated 3D aftermath scene using the game's actual
meshes, textures, Humanoid box-rigs and FX kits, with full layered backgrounds
(skyline/riverfront/border hills/treelines) so no vista opens into an empty void.
"""
import math
import os
import traceback

import pygame

OUT_W, OUT_H = 320, 190

_S = {
    "r": None,
    "buf": None,
    "size": None,
    "key": None,
    "route": None,
    "epoch": 0,
    "cached_surf": None,
    "last_draw_ms": -1,
    "failed": False,
    "bad_keys": frozenset(),
    "printed_err": False,
    "beacons": [],
}
_MESH_CACHE = {}


def enabled():
    if os.environ.get("ACA_MC_2D", "").strip() == "1":
        return False
    return not _S["failed"]


def enter():
    """Clear baked diorama geometry and cached frame when entering MISSION_COMPLETE."""
    _S["key"] = None
    _S["route"] = None
    _S["epoch"] += 1
    _S["cached_surf"] = None
    _S["last_draw_ms"] = -1
    _S["beacons"] = []
    r = _S["r"]
    if r is not None:
        r.objs.clear()
        inv = getattr(r, "invalidate_static", None)
        if inv:
            inv()


def _renderer():
    from engine3d import Renderer
    if _S["r"] is None:
        r = Renderer(OUT_W, OUT_H, fog=(14, 18, 26), fog_start=18.0, fog_end=76.0)
        is_gl = "gl" in str(getattr(r, "backend", "")).lower()
        size = (OUT_W * 2, OUT_H * 2) if is_gl else (OUT_W, OUT_H)
        if r.resize(*size):
            _S["buf"] = pygame.Surface(size)
            _S["size"] = size
        else:
            _S["buf"] = pygame.Surface((OUT_W, OUT_H))
            _S["size"] = (OUT_W, OUT_H)
        _S["r"] = r
    return _S["r"], _S["buf"]


def _dyn_faces(mesh):
    return [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces]


def _bake(r, mesh, pos=(0.0, 0.0, 0.0), yaw=0.0):
    from engine3d.core import M_IDENT, rot_y
    r.bake(mesh, rot_y(yaw) if yaw else M_IDENT, pos)


def _fit_mesh(mesh, height_m=None, length_m=None, yaw=0.0, ground=True):
    """Rotate, uniformly scale to target height/footprint, centre X/Z, ground at y=0."""
    from engine3d.core import Mesh, m_apply, rot_y
    if mesh is None or not mesh.verts:
        return None
    m = rot_y(yaw) if yaw else None
    pts = [m_apply(m, v) for v in mesh.verts] if m else list(mesh.verts)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    zs = [p[2] for p in pts]
    span_y = max(1e-4, max(ys) - min(ys))
    span_xz = max(1e-4, max(xs) - min(xs), max(zs) - min(zs))
    s = 1.0
    if height_m is not None:
        s = height_m / span_y
    elif length_m is not None:
        s = length_m / span_xz
    pts = [(x * s, y * s, z * s) for x, y, z in pts]
    cx = 0.5 * (min(p[0] for p in pts) + max(p[0] for p in pts))
    cz = 0.5 * (min(p[2] for p in pts) + max(p[2] for p in pts))
    y0 = min(p[1] for p in pts) if ground else 0.0
    return Mesh([(x - cx, y - y0, z - cz) for x, y, z in pts], list(mesh.faces))


def _prop_fitted(ref, height_m=None, length_m=None, yaw=0.0, screen=None):
    cache_key = (ref, height_m, length_m, yaw, screen)
    if cache_key in _MESH_CACHE:
        return _MESH_CACHE[cache_key]
    from game import scenery3d
    raw = scenery3d.prop(ref, screen=screen)
    m = _fit_mesh(raw, height_m=height_m, length_m=length_m, yaw=yaw) if raw is not None else None
    _MESH_CACHE[cache_key] = m
    return m


def _krap_van_mesh():
    """Load krap_van with emissive headlights (grp 1) and taillights (grp 2)."""
    if "krap_van" in _MESH_CACHE:
        return _MESH_CACHE["krap_van"]
    from engine3d.core import Mesh
    try:
        from game.render3d_bridge import load_mesh_asset
        verts, faces = load_mesh_asset("krap_van")
        m = Mesh()
        m.verts = [tuple(float(c) for c in v) for v in verts]
        for idx, col, grp in faces:
            if grp == 1:
                m.faces.append((tuple(idx), (255, 244, 200), 2, False, True))
            elif grp == 2:
                m.faces.append((tuple(idx), (255, 62, 48), 2, False, True))
            else:
                m.faces.append((tuple(idx), tuple(col), 3 if grp == 9 else 2, False, False))
        m = _fit_mesh(m, length_m=6.4, ground=True)
    except Exception:
        from engine3d.core import box
        m = box(5.8, 2.2, 2.2, (42, 62, 92), center=(0.0, 1.1, 0.0))
    _MESH_CACHE["krap_van"] = m
    return m


def _tx(name, col, tint=False):
    from engine3d import tex
    return tex(name, like=col, tint=tint)


_POST_PROFILES = {
    "MISSION0": {"grade": "night_warm", "bloom": 0.30, "vignette": 0.42, "grain": 0.14},
    "MISSION1": {"grade": "cold_blue", "bloom": 0.36, "vignette": 0.48, "grain": 0.16},
    "MISSION2": {"grade": "cold_blue", "bloom": 0.34, "vignette": 0.46, "grain": 0.16},
    "MISSION3": {"grade": "night_warm", "bloom": 0.34, "vignette": 0.44, "grain": 0.14},
    "MISSION4": {"grade": "faded_stock", "bloom": 0.28, "vignette": 0.36, "grain": 0.12},
    "MISSION5": {"grade": "night_warm", "bloom": 0.38, "vignette": 0.50, "grain": 0.15},
    "MISSION6": {"grade": "cold_blue", "bloom": 0.34, "vignette": 0.46, "grain": 0.16},
    "MISSION7": {"grade": "night_warm", "bloom": 0.40, "vignette": 0.48, "grain": 0.15},
    "MISSION8_duty": {"grade": "faded_stock", "bloom": 0.34, "vignette": 0.40, "grain": 0.14},
    "MISSION8_revenge": {"grade": "cold_blue", "bloom": 0.32, "vignette": 0.44, "grain": 0.15},
}


def _pose_actor(actor_key, base_pose, pos, yaw, look_tgt, flags=(), mode=None, **overrides):
    from cutscenes import m6world3d as _w
    from engine3d.hold import hold_cached, weapon_of
    from engine3d.rig import solve_look
    p = dict(base_pose)
    if mode is not None:
        h = _w.hum(actor_key, flags=flags)
        wpn = weapon_of(h)
        if wpn:
            p = hold_cached(h, p, wpn, mode, key=("mc3d", actor_key, flags, mode))
    p.update(overrides)
    eye = (pos[0], pos[1] + 1.56, pos[2])
    hy, hp = solve_look(eye, look_tgt, yaw)
    p["head_y"] = hy
    p["head_p"] = hp
    return p


def _ground_shadow(r, pos, rx=0.45, rz=0.45, strength=0.42):
    r.add_blob_shadow((pos[0], pos[1] + 0.01, pos[2]), rx, rz, strength=strength, layer=1)


def _water_shimmer(r, x, y, z, width_m, length_m, col, t_ms, seed=0):
    """Flat 3D water/puddle reflection strips in true perspective (no screen-space circles)."""
    from engine3d.core import Mesh, quad_xz
    m = Mesh()
    steps = 5
    step_l = length_m / float(steps)
    for i in range(steps):
        f = i / float(steps)
        w = width_m * (0.45 + 0.55 * (1.0 - f)) * (0.85 + 0.15 * math.sin(t_ms * 0.0014 + i * 1.7 + seed))
        k = (1.0 - 0.55 * f) * (0.78 + 0.22 * math.sin(t_ms * 0.0018 + i * 2.1 + seed))
        c = tuple(max(0, min(255, int(ch * k))) for ch in col)
        z0 = z + i * step_l
        m.add(quad_xz(x - w * 0.5, z0 + 0.04, x + w * 0.5, z0 + step_l * 0.72, y, c, layer=1, emissive=True))
    r.add_dynamic(m.verts, _dyn_faces(m))


def _lattice_tower(x, z, height=7.2, base_w=1.4):
    from engine3d.core import Mesh, box, rot_y
    m = Mesh()
    col = (38, 42, 48)
    segs = 5
    sh = height / segs
    for s in range(segs):
        w0 = base_w * (1.0 - 0.55 * (s / segs))
        w1 = base_w * (1.0 - 0.55 * ((s + 1) / segs))
        wm = 0.5 * (w0 + w1)
        yc = (s + 0.5) * sh
        for sx in (-1, 1):
            for sz in (-1, 1):
                m.add(box(0.09, sh + 0.03, 0.09, col,
                          center=(x + sx * wm * 0.42, yc, z + sz * wm * 0.42)))
        ry = (s + 1) * sh
        bw = w1 * 0.86
        m.add(box(bw, 0.07, 0.07, col, center=(x, ry, z - bw / 2)))
        m.add(box(bw, 0.07, 0.07, col, center=(x, ry, z + bw / 2)))
        m.add(box(0.07, 0.07, bw, col, center=(x - bw / 2, ry, z)))
        m.add(box(0.07, 0.07, bw, col, center=(x + bw / 2, ry, z)))
    # Microwave dish & whip mast
    dish = box(0.72, 0.72, 0.16, (166, 174, 182))
    m.add(dish, rot_y(-25), (x - 0.46, height * 0.72, z + 0.18))
    m.add(box(0.07, 1.35, 0.07, (148, 154, 160), center=(x, height + 0.68, z)))
    m.add(box(0.16, 0.16, 0.16, (240, 70, 56), center=(x, height + 1.38, z), emissive=True))
    return m


def _ridge_band(x0, x1, z_front, base_y, peaks, col, depth=8.0):
    """Build a multi-peaked faceted ridge silhouette using convex triangle pairs."""
    from engine3d.core import Mesh
    m = Mesh()
    n = len(peaks)
    if n < 2:
        return m
    span = x1 - x0
    z_back = z_front + depth
    for i in range(n - 1):
        xa = x0 + span * (i / float(n - 1))
        xb = x0 + span * ((i + 1) / float(n - 1))
        xm = 0.5 * (xa + xb)
        ha = peaks[i]
        hb = peaks[i + 1]
        hm = 0.5 * (ha + hb) + (0.6 if i % 2 == 0 else -0.3)
        c_a = tuple(max(0, min(255, c + (3 if i % 2 == 0 else -2))) for c in col)
        c_b = tuple(max(0, min(255, c - 4)) for c in col)
        m.face([(xa, base_y, z_front), (xb, base_y, z_front), (xm, base_y + hm, z_front + depth * 0.45)],
               c_a, 2, True)
        m.face([(xa, base_y, z_front), (xm, base_y + hm, z_front + depth * 0.45), (xa, base_y + ha, z_back)],
               c_b, 2, True)
        m.face([(xb, base_y, z_front), (xb, base_y + hb, z_back), (xm, base_y + hm, z_front + depth * 0.45)],
               c_b, 2, True)
    return m


def _soviet_block(cx, cz, w, h, d, seed=0, col=(24, 28, 36), lit=0.28):
    """Non-snowy Soviet panel tower for city skylines (M1/M4/M5)."""
    from engine3d.core import Mesh, box
    m = Mesh()
    m.add(box(w, h, d, _tx("concrete", col), center=(cx, h / 2.0, cz), skip=("bottom",)))
    # Parapet & lift house
    rim = tuple(max(0, c - 6) for c in col)
    m.add(box(w + 0.25, 0.36, d + 0.25, rim, center=(cx, h + 0.18, cz)))
    if w >= 5.0:
        m.add(box(w * 0.36, 1.3, d * 0.42, rim, center=(cx - w * 0.14, h + 0.85, cz)))
    if seed % 2 == 0:
        ax = cx + w * 0.22
        m.add(box(0.08, 2.4, 0.08, (76, 82, 90), center=(ax, h + 1.4, cz)))
        m.add(box(0.95, 0.05, 0.05, (76, 82, 90), center=(ax, h + 2.1, cz)))
    # Window grid on -z face
    wz = cz - d / 2.0 - 0.03
    cols = max(2, int((w - 0.8) // 1.35))
    rows = max(2, int((h - 1.4) // 2.1))
    win_cols = ((226, 184, 114), (162, 186, 214), (198, 152, 92))
    for r_i in range(rows):
        wy = 1.5 + r_i * 2.0
        if wy > h - 0.8:
            break
        m.add(box(w + 0.08, 0.06, 0.06, rim, center=(cx, wy - 0.72, wz + 0.01)))
        for c_i in range(cols):
            wx = cx - w * 0.36 + c_i * (w * 0.72 / max(1, cols - 1))
            hv = ((seed * 37 + r_i * 19 + c_i * 13) % 100) / 100.0
            if hv < lit:
                wc, em = win_cols[(seed + r_i + c_i) % 3], True
            else:
                wc, em = (14, 18, 24), False
            m.add(box(0.66, 0.84, 0.04, wc, center=(wx, wy, wz), emissive=em))
    return m


def _crate_prop(w=1.0, h=0.72, d=1.0, band_col=None):
    from engine3d.core import Mesh, box
    m = Mesh()
    wood = _tx("crate", (96, 76, 52))
    trim = _tx("m7_plank", (74, 58, 38))
    m.add(box(w, h, d, wood, center=(0.0, h / 2.0, 0.0)))
    for sx in (-1, 1):
        m.add(box(0.08, h + 0.02, d + 0.04, trim, center=(sx * (w / 2.0 - 0.04), h / 2.0, 0.0)))
    m.add(box(w + 0.04, 0.07, d + 0.04, trim, center=(0.0, h - 0.035, 0.0)))
    m.add(box(w + 0.04, 0.07, d + 0.04, trim, center=(0.0, 0.035, 0.0)))
    if band_col is not None:
        m.add(box(w * 0.78, 0.14, 0.03, band_col, center=(0.0, h * 0.56, -d / 2.0 - 0.015)))
    return m


def _notebook_prop():
    from engine3d.core import Mesh, box, rot_y
    m = Mesh()
    m.add(box(0.28, 0.035, 0.36, (18, 20, 24), center=(0.0, 0.018, 0.0)))
    m.add(box(0.24, 0.025, 0.32, (218, 210, 188), center=(0.01, 0.036, 0.0)))
    m.add(box(0.26, 0.016, 0.34, (24, 26, 30)), rot_y(-8), (-0.02, 0.052, 0.0))
    m.add(box(0.06, 0.02, 0.09, (182, 146, 76), center=(0.12, 0.04, 0.0)))
    return m


def _field_radio_prop():
    from engine3d.core import Mesh, box, rot_z
    m = Mesh()
    olive = (48, 56, 44)
    panel = (28, 32, 30)
    m.add(box(0.58, 0.36, 0.34, olive, center=(0.0, 0.18, 0.0)))
    m.add(box(0.52, 0.28, 0.04, panel, center=(0.0, 0.18, -0.16)))
    # Two frequency channel dials (Duty/Vasile amber vs Revenge/Maru green)
    m.add(box(0.14, 0.08, 0.02, (244, 168, 72), center=(-0.13, 0.22, -0.18), emissive=True))
    m.add(box(0.14, 0.08, 0.02, (98, 224, 142), center=(0.13, 0.22, -0.18), emissive=True))
    m.add(box(0.18, 0.09, 0.02, (42, 46, 42), center=(0.0, 0.10, -0.18)))
    # Whip antenna
    m.add(box(0.025, 0.85, 0.025, (148, 154, 158)), rot_z(6), (0.21, 0.72, 0.08))
    return m


def _studio_camera_prop():
    from engine3d.core import Mesh, box, rot_z
    m = Mesh()
    dark = (26, 28, 32)
    metal = (96, 102, 108)
    for ang, ox, oz in ((14, -0.22, -0.18), (-14, 0.22, -0.18), (0, 0.0, 0.24)):
        m.add(box(0.05, 1.24, 0.05, metal), rot_z(ang), (ox, 0.60, oz))
    m.add(box(0.24, 0.10, 0.24, dark, center=(0.0, 1.20, 0.0)))
    m.add(box(0.32, 0.30, 0.56, (44, 48, 54), center=(0.0, 1.40, 0.0)))
    m.add(box(0.20, 0.18, 0.20, dark, center=(0.0, 1.40, 0.36)))
    m.add(box(0.08, 0.06, 0.08, (238, 48, 42), center=(0.0, 1.58, 0.20), emissive=True))
    return m


def _bench_mesh():
    """Slatted wooden platform bench (avoids reading as a crate block)."""
    from engine3d.core import Mesh, box
    m = Mesh()
    wood = _tx("m7_plank", (92, 72, 52))
    iron = (28, 30, 34)
    for lx in (-0.72, 0.72):
        m.add(box(0.08, 0.44, 0.52, iron, center=(lx, 0.22, 0.0)))
        m.add(box(0.06, 0.48, 0.06, iron, center=(lx, 0.66, 0.22)))
    for sz in (-0.16, 0.0, 0.16):
        m.add(box(1.72, 0.05, 0.12, wood, center=(0.0, 0.45, sz)))
    for sy in (0.64, 0.82):
        m.add(box(1.72, 0.11, 0.05, wood, center=(0.0, sy, 0.20)))
    return m


def _customs_hut(x, z, yaw=0.0):
    from engine3d.core import Mesh, box
    m = Mesh()
    wall = _tx("m7_plaster", (76, 78, 72))
    roof = _tx("m7_tin", (46, 50, 56))
    m.add(box(4.2, 2.9, 3.2, wall, center=(0.0, 1.45, 0.0)))
    m.add(box(4.6, 0.24, 3.6, roof, center=(0.0, 3.0, 0.0)))
    m.add(box(1.15, 0.95, 0.08, (242, 198, 118), center=(-0.7, 1.65, -1.62), emissive=True))
    m.add(box(0.95, 2.0, 0.08, (42, 34, 28), center=(1.05, 1.0, -1.62)))
    return m, (x, 0.0, z), yaw


def _pendant_lamp(x, y, z, col=(255, 214, 148)):
    from engine3d.core import Mesh, box
    m = Mesh()
    m.add(box(0.04, 0.8, 0.04, (24, 26, 28), center=(x, y + 0.44, z)))
    m.add(box(0.54, 0.14, 0.54, (40, 44, 48), center=(x, y + 0.04, z)))
    m.add(box(0.24, 0.10, 0.24, col, center=(x, y - 0.04, z), emissive=True))
    return m


def _setup_static(r, key, route):
    """Bake static set + background vista once per (mission, route)."""
    from engine3d.core import Light, Mesh, box, disc_xz, quad_xz, rot_x, rot_y, rot_z
    from cutscenes import m6world3d as _w
    from cutscenes import m7world3d as F
    from game import scenery3d
    from missions.m6.bloc3d import stacks as _b_stacks, tower as _b_tower
    from missions.m8.revenge import chase_set as S

    r.objs.clear()
    _S["beacons"] = []
    inv = getattr(r, "invalidate_static", None)
    if inv:
        inv()
    r.light_albedo = False
    r.light_gain = 1.0

    if key == "MISSION0":
        r.light = Light(direction=(-0.55, 0.78, -0.35), ambient=0.38, diffuse=0.68, sky=0.08, tint=(1.0, 0.94, 0.84))
        r.fog, r.fog_start, r.fog_end = (14, 16, 20), 12.0, 36.0
        _bake(r, quad_xz(-9, -9, 10, 9, 0.0, _tx("concrete", (38, 40, 42)), seg=1.5))
        # Safety floor stripes
        _bake(r, quad_xz(-1.4, -3.5, 4.6, -3.25, 0.01, (164, 134, 48)))
        _bake(r, quad_xz(1.1, 3.8, 3.6, 4.05, 0.01, (164, 134, 48)))
        # Corrugated walls + exposed structural I-beams + roof trusses
        _bake(r, box(14.0, 4.8, 0.3, _tx("steel", (46, 50, 54)), center=(0.5, 2.4, 5.1)))
        _bake(r, box(0.3, 4.8, 12.0, _tx("steel", (40, 44, 48)), center=(-4.6, 2.4, 0.0)))
        _bake(r, box(0.3, 4.8, 12.0, _tx("steel", (36, 40, 44)), center=(5.3, 2.4, 0.0)))
        _bake(r, box(11.0, 0.25, 12.0, (20, 22, 26), center=(0.5, 4.8, 0.0)))
        for px in (-3.2, 0.5, 4.2):
            _bake(r, box(0.24, 4.8, 0.28, (30, 34, 38), center=(px, 2.4, 4.85)))
        for tz in (-0.8, 1.8, 4.0):
            _bake(r, box(10.0, 0.22, 0.18, (28, 32, 36), center=(0.5, 4.45, tz)))
        # Bay roll-up door + exit beacon + yellow bollards
        _bake(r, box(2.3, 3.0, 0.14, _tx("metal_rib", (34, 38, 42)), center=(2.3, 1.5, 4.9)))
        _bake(r, box(0.68, 0.22, 0.10, (78, 198, 108), center=(2.3, 3.22, 4.88), emissive=True))
        for bx in (1.0, 3.6):
            _bake(r, box(0.16, 0.92, 0.16, (186, 136, 36), center=(bx, 0.46, 4.45)))
        # Hero pallet + strapped supply crate + medical supplies + barrel + rack
        _bake(r, box(1.45, 0.14, 1.45, _tx("m7_plank", (74, 58, 40)), center=(-0.35, 0.07, 0.55)))
        _bake(r, _crate_prop(1.12, 0.78, 1.12, band_col=(168, 46, 42)), (-0.35, 0.14, 0.55))
        _bake(r, scenery3d.medical_supplies(), (-0.38, 0.92, 0.45), yaw=-18.0)
        _bake(r, box(0.26, 0.03, 0.34, (218, 212, 194), center=(0.02, 0.935, 0.32)), yaw=14.0)
        _bake(r, box(1.5, 2.2, 0.78, (34, 38, 42), center=(3.3, 1.1, 3.2)))
        _bake(r, _crate_prop(0.95, 0.65, 0.65), (3.25, 2.2, 3.2))
        barrel = _prop_fitted("barrel", height_m=0.95) or box(0.58, 0.95, 0.58, (88, 66, 48), center=(0, 0.475, 0))
        _bake(r, barrel, (1.15, 0.0, 1.05))
        _bake(r, box(1.45, 0.78, 0.80, (36, 40, 44), center=(0.0, 0.39, 0.0)), (-2.85, 0.0, 3.2), yaw=16.0)
        ws = scenery3d.workstation("pc_zarya", "monitor_crt", live=True)
        wdisp = scenery3d.workstation_display("pc_zarya", "monitor_crt", (88, 214, 134))
        if ws is not None:
            _bake(r, ws, (-2.85, 0.78, 3.2), yaw=196.0)
            if wdisp is not None:
                _bake(r, wdisp, (-2.85, 0.78, 3.2), yaw=196.0)
        _bake(r, _pendant_lamp(-0.35, 3.55, 0.55))

    elif key == "MISSION1":
        r.light = Light(direction=(-0.35, 0.82, -0.45), ambient=0.40, diffuse=0.46, sky=0.06, tint=(0.82, 0.90, 1.08))
        r.light_albedo, r.light_gain = True, 2.0
        r.fog, r.fog_start, r.fog_end = (10, 13, 19), 20.0, 74.0
        _bake(r, quad_xz(-18, -14, 5.2, 26, 0.0, _tx("pavement", (16, 18, 22)), seg=2.5))
        # Harbor water + stone quay + timber mooring bollards on the right
        _bake(r, quad_xz(5.2, -14, 42, 42, -0.65, (10, 18, 28), seg=3.0))
        _bake(r, box(1.2, 0.85, 38.0, _tx("concrete", (34, 38, 42)), center=(5.2, -0.25, 6.0)))
        for bz in (-2.0, 4.5, 11.0, 17.5):
            _bake(r, box(0.28, 0.45, 0.28, (32, 34, 36), center=(5.1, 0.35, bz)))
        # Warehouse wall & canopy on left
        _bake(r, box(0.5, 5.4, 24.0, _tx("metal_rib", (36, 40, 46)), center=(-5.4, 2.7, 6.0)))
        _bake(r, box(1.6, 0.18, 6.8, (28, 32, 36), center=(-4.5, 3.4, 2.5)))
        _bake(r, box(0.14, 3.1, 4.2, (24, 28, 32), center=(-5.12, 1.55, 2.5)))
        _bake(r, box(0.10, 0.34, 0.65, (238, 184, 98), center=(-5.10, 3.22, 2.5), emissive=True))
        # Shipping containers + dock crane + Soviet waterfront warehouses & smokestack
        _bake(r, box(2.5, 2.5, 6.0, _tx("metal_rib", (48, 60, 74)), center=(3.2, 1.25, 13.5)))
        _bake(r, box(2.5, 2.5, 6.0, _tx("rust", (82, 46, 38)), center=(0.4, 1.25, 15.8)))
        _bake(r, box(0.55, 14.5, 0.55, (28, 32, 38), center=(11.5, 7.25, 18.5)))
        _bake(r, box(10.0, 0.45, 0.45, (32, 36, 42), center=(8.5, 14.3, 18.5)))
        _bake(r, _soviet_block(-9.0, 26.0, 9.0, 11.0, 6.0, seed=11, lit=0.25))
        _bake(r, _soviet_block(1.5, 28.0, 8.5, 14.0, 6.0, seed=12, col=(20, 24, 32), lit=0.32))
        _bake(r, _soviet_block(12.5, 29.0, 9.5, 10.5, 6.0, seed=13, lit=0.22))
        _S["beacons"].extend(_b_stacks.smokestack(lambda m: _bake(r, m), 17.5, 27.0, 18.0))
        # Streetlamp, KRAP van, crate with Black Notebook, barrel & scorch + molotov
        _bake(r, box(0.14, 4.8, 0.14, (14, 16, 18), center=(-4.2, 2.4, 3.6)))
        _bake(r, box(0.12, 0.12, 1.2, (14, 16, 18), center=(-4.2, 4.75, 3.0)))
        _bake(r, box(0.42, 0.08, 0.24, (255, 214, 148), center=(-4.2, 4.68, 2.4), emissive=True))
        _bake(r, _krap_van_mesh(), (0.95, 0.0, 1.2), yaw=-24.0)
        _bake(r, quad_xz(-4.2, -0.3, -2.4, 1.5, 0.015, _tx("scorch", (18, 16, 16))))
        _bake(r, _crate_prop(0.86, 0.68, 0.86), (-2.85, 0.0, -0.55), yaw=14.0)
        _bake(r, _notebook_prop(), (-2.85, 0.68, -0.55), yaw=-12.0)
        barrel = _prop_fitted("barrel", height_m=0.95)
        if barrel is not None:
            _bake(r, barrel, (-3.65, 0.0, 0.65))
        mol = _prop_fitted("molotov", height_m=0.38)
        if mol is not None:
            _bake(r, mol, (-3.05, 0.68, -0.35), yaw=32.0)

    elif key == "MISSION2":
        r.light = Light(direction=(-0.40, 0.80, -0.45), ambient=0.36, diffuse=0.52, sky=0.08, tint=(0.80, 0.90, 1.06))
        r.light_albedo, r.light_gain = True, 1.8
        r.fog, r.fog_start, r.fog_end = (11, 15, 22), 18.0, 68.0
        _bake(r, quad_xz(-24, -14, 24, 7.0, 0.0, _tx("pavement", (20, 22, 26)), seg=2.0))
        _bake(r, quad_xz(-28, 7.0, 28, 38.0, 0.0, (16, 20, 18), seg=3.0))
        for k in range(-4, 5):
            _bake(r, quad_xz(k * 4.5, 0.8, k * 4.5 + 2.0, 1.0, 0.015, (148, 138, 108)))
        # Highway guardrail + Overhead Route 12 Steel Gantry
        _bake(r, box(36.0, 0.18, 0.14, (84, 88, 92), center=(0.0, 0.65, 5.2)))
        for gx in range(-14, 16, 3):
            _bake(r, box(0.12, 0.72, 0.12, (56, 60, 64), center=(float(gx), 0.36, 5.25)))
        for gz in (-4.8, 4.8):
            _bake(r, box(0.32, 4.8, 0.32, (42, 46, 50), center=(-4.2, 2.4, gz)))
        _bake(r, box(0.38, 0.45, 10.6, (44, 48, 54), center=(-4.2, 4.75, 0.0)))
        _bake(r, box(0.10, 0.85, 2.6, (28, 66, 52), center=(-4.02, 4.75, 0.6)))
        _bake(r, box(0.24, 0.24, 0.24, (242, 162, 56), center=(-4.0, 5.15, -1.8), emissive=True))
        # Control-04 Concrete Guardhouse Booth on shoulder with illuminated interior window
        booth = Mesh()
        wall_c = _tx("concrete", (46, 50, 54))
        booth.add(box(3.4, 2.8, 0.22, wall_c, center=(0.0, 1.4, 1.4)))
        booth.add(box(0.22, 2.8, 2.8, wall_c, center=(1.6, 1.4, 0.0)))
        booth.add(box(0.22, 2.8, 2.8, wall_c, center=(-1.6, 1.4, 0.0)))
        booth.add(box(3.6, 0.24, 3.2, (32, 36, 40), center=(0.0, 2.88, 0.0)))
        booth.add(box(3.4, 0.96, 0.22, wall_c, center=(0.0, 0.48, -1.3)))
        booth.add(box(3.4, 0.55, 0.22, wall_c, center=(0.0, 2.52, -1.3)))
        booth.add(box(1.9, 0.78, 0.72, (42, 46, 50), center=(0.0, 0.39, -0.35)))
        _bake(r, booth, (2.25, 0.0, 2.15), yaw=-24.0)
        ws = scenery3d.workstation("pc_zarya", "monitor_crt", live=True)
        wdisp = scenery3d.workstation_display("pc_zarya", "monitor_crt", (78, 228, 132))
        if ws is not None:
            _bake(r, ws, (2.05, 0.78, 1.85), yaw=156.0)
            if wdisp is not None:
                _bake(r, wdisp, (2.05, 0.78, 1.85), yaw=156.0)
        tel = _prop_fitted("telephone_base", height_m=0.14)
        if tel is not None:
            _bake(r, tel, (2.68, 0.78, 2.08), yaw=165.0)
        # Jersey barriers, scorch, car_m2, pine treeline & faceted mountain ridge
        _bake(r, box(2.2, 0.82, 0.48, _tx("concrete", (68, 70, 72)), center=(0.0, 0.41, 0.0)), (-0.1, 0.0, 1.6), yaw=-14.0)
        _bake(r, box(2.2, 0.82, 0.48, _tx("concrete", (68, 70, 72)), center=(0.0, 0.41, 0.0)), (-3.6, 0.0, 2.1), yaw=16.0)
        _bake(r, quad_xz(-3.4, -0.6, -1.0, 1.4, 0.014, _tx("scorch", (16, 15, 16))))
        car = _prop_fitted("car_m2", length_m=4.1)
        if car is not None:
            _bake(r, car, (-2.1, 0.0, 1.15), yaw=34.0)
        _bake(r, _lattice_tower(-7.2, 9.6, height=5.8, base_w=1.1), (0.0, 0.0, 0.0))
        for tx, tz in ((-11.5, 11.0), (-5.8, 10.5), (-1.2, 11.2), (4.8, 10.8), (8.6, 11.5), (12.0, 12.5)):
            _bake(r, F.tree(int(abs(tx) * 11 + tz)), (tx, 0.0, tz))
        _bake(r, _ridge_band(-28.0, 28.0, 21.0, 0.0, (4.2, 7.8, 5.5, 9.6, 6.2, 8.8, 4.6), (18, 24, 34), depth=11.0))

    elif key == "MISSION3":
        r.light = Light(direction=(-0.50, 0.75, -0.42), ambient=0.38, diffuse=0.58, sky=0.10, tint=(0.94, 0.98, 0.94))
        r.fog, r.fog_start, r.fog_end = (8, 12, 14), 14.0, 44.0
        _bake(r, quad_xz(-9, -8, 9, 10, 0.0, _tx("concrete", (24, 28, 28)), seg=1.5))
        # Control booth walls & acoustic panels + server/tape reel racks on left
        _bake(r, box(0.3, 4.2, 12.0, (20, 24, 28), center=(-4.2, 2.1, 2.0)))
        _bake(r, box(0.3, 4.2, 12.0, (20, 24, 28), center=(4.2, 2.1, 2.0)))
        _bake(r, box(9.0, 0.25, 12.0, (14, 16, 20), center=(0.0, 4.0, 2.0)))
        _bake(r, box(9.0, 1.0, 0.25, (20, 24, 28), center=(0.0, 0.5, 3.2)))
        _bake(r, box(9.0, 1.4, 0.25, (20, 24, 28), center=(0.0, 3.3, 3.2)))
        for mx in (-2.4, 0.0, 2.4):
            _bake(r, box(0.10, 1.65, 0.14, (24, 28, 32), center=(mx, 1.82, 3.16)))
        _bake(r, box(1.3, 0.38, 0.12, (186, 36, 36), center=(0.0, 2.82, 3.04), emissive=True))
        # Broadcast tape racks on left booth wall
        for rz in (1.5, 2.4):
            _bake(r, box(0.7, 2.2, 0.78, (26, 30, 36), center=(-3.5, 1.1, rz)))
            _bake(r, box(0.04, 0.12, 0.42, (74, 210, 126), center=(-3.14, 1.75, rz), emissive=True))
            _bake(r, box(0.04, 0.08, 0.28, (236, 154, 68), center=(-3.14, 1.45, rz), emissive=True))
        # Studio A visible through control window: State TV blue news wall, crest, truss & camera
        _bake(r, box(10.4, 4.2, 0.3, (16, 30, 66), center=(0.0, 2.1, 7.6)))
        _bake(r, box(10.4, 0.48, 0.08, (150, 28, 30), center=(0.0, 0.95, 7.42), emissive=True))
        _bake(r, box(10.4, 0.08, 0.08, (176, 146, 86), center=(0.0, 1.22, 7.42)))
        _bake(r, box(2.4, 1.35, 0.08, (36, 62, 118), center=(0.0, 2.15, 7.42)))
        _bake(r, box(0.95, 0.95, 0.08, (168, 138, 78), center=(1.85, 2.15, 7.40)))
        _bake(r, box(2.6, 0.85, 0.72, (24, 28, 42), center=(0.0, 0.425, 5.5)))
        _bake(r, box(7.0, 0.12, 0.14, (32, 34, 40), center=(0.0, 3.45, 5.2)))
        for lx in (-2.0, -0.7, 0.7, 2.0):
            _bake(r, box(0.24, 0.14, 0.24, (244, 224, 184), center=(lx, 3.34, 5.2), emissive=True))
        _bake(r, _studio_camera_prop(), (1.85, 0.0, 4.45), yaw=-152.0)
        # Foreground console desk, VU meter bridge, workstations, phone & Vostral file
        _bake(r, box(3.2, 0.82, 0.94, (28, 32, 36), center=(0.0, 0.41, 1.35)))
        _bake(r, box(3.3, 0.06, 1.00, (54, 58, 60), center=(0.0, 0.85, 1.35)))
        _bake(r, box(2.6, 0.22, 0.22, (34, 38, 42), center=(0.0, 0.98, 1.62)))
        for vx in (-0.85, -0.35, 0.15):
            _bake(r, box(0.32, 0.07, 0.04, (92, 226, 134), center=(vx, 0.99, 1.50), emissive=True))
        ws = scenery3d.workstation("pc_zarya", "monitor_crt", live=True)
        wdisp = scenery3d.workstation_display("pc_zarya", "monitor_crt", (144, 214, 152))
        if ws is not None:
            _bake(r, ws, (-0.58, 0.88, 1.32), yaw=166.0)
            if wdisp is not None:
                _bake(r, wdisp, (-0.58, 0.88, 1.32), yaw=166.0)
        lcd = _prop_fitted("monitor_lcd", height_m=0.46, screen=(232, 134, 82))
        if lcd is not None:
            _bake(r, lcd, (0.58, 0.88, 1.35), yaw=196.0)
        tel = _prop_fitted("telephone_base", height_m=0.14)
        if tel is not None:
            _bake(r, tel, (1.18, 0.88, 1.24), yaw=172.0)
        _bake(r, _notebook_prop(), (0.04, 0.88, 1.15), yaw=18.0)

    elif key == "MISSION4":
        r.light = Light(direction=(0.55, 0.48, 0.65), ambient=0.42, diffuse=0.72, sky=0.18, tint=(1.04, 0.92, 0.82))
        r.fog, r.fog_start, r.fog_end = (74, 78, 102), 20.0, 86.0
        # Dark tar roof membrane + raised concrete paver slabs (visible expansion seams)
        _bake(r, quad_xz(-7.5, -6.5, 8.2, 5.0, 0.0, (20, 22, 26), seg=2.0))
        for px_i, px in enumerate((-5.1, -1.7, 1.7, 5.1)):
            for pz_i, pz in enumerate((-3.8, -0.5, 2.8)):
                col = (52, 56, 62) if (px_i + pz_i) % 2 == 0 else (46, 50, 56)
                _bake(r, box(3.24, 0.05, 3.14, _tx("concrete", col), center=(px, 0.025, pz), skip=("bottom",)))
        # Lower city floor under distant blocks so skyline is grounded
        _bake(r, quad_xz(-44.0, 8.0, 44.0, 56.0, -5.5, (18, 22, 30), seg=6.0))
        # Shallow rainwater puddle + cable run to the radio mast
        _bake(r, quad_xz(-2.2, -0.6, 0.3, 1.4, 0.054, (28, 36, 48), seg=1.0))
        _bake(r, box(9.0, 0.06, 0.24, (28, 30, 34), center=(-0.4, 0.08, 3.25)))
        # Parapet walls with coping stone, stairwell bulkhead, HVAC + ducting & sandbag cover
        _bake(r, box(15.2, 0.88, 0.42, _tx("concrete", (56, 60, 64)), center=(0.4, 0.44, 4.6)))
        _bake(r, box(15.4, 0.10, 0.54, (74, 78, 84), center=(0.4, 0.92, 4.6)))
        _bake(r, box(0.42, 0.88, 11.5, _tx("concrete", (52, 56, 60)), center=(-6.9, 0.44, -1.0)))
        _bake(r, box(0.54, 0.10, 11.7, (74, 78, 84), center=(-6.9, 0.92, -1.0)))
        _bake(r, box(0.42, 0.88, 12.0, _tx("concrete", (52, 56, 60)), center=(7.8, 0.44, -1.0)))
        _bake(r, box(0.54, 0.10, 12.2, (74, 78, 84), center=(7.8, 0.92, -1.0)))
        _bake(r, box(2.4, 2.2, 2.2, _tx("concrete", (46, 50, 56)), center=(-5.2, 1.1, 2.4)))
        _bake(r, box(0.92, 1.85, 0.08, (32, 36, 40), center=(-4.9, 0.92, 1.28)))
        _bake(r, box(0.32, 0.14, 0.10, (244, 188, 108), center=(-4.9, 1.98, 1.24), emissive=True))
        _bake(r, box(1.9, 1.15, 1.5, (48, 52, 58), center=(4.8, 0.58, 2.6)))
        _bake(r, box(1.4, 0.32, 0.32, (62, 66, 72), center=(3.5, 0.45, 2.6)))
        # Low concrete roof vent hatch in right foreground
        _bake(r, box(1.25, 0.34, 0.95, _tx("concrete", (58, 62, 66)), center=(1.8, 0.22, -0.35)))
        _bake(r, box(1.36, 0.08, 1.06, (38, 42, 46), center=(1.8, 0.42, -0.35)))
        # Siege sandbags & supply crate along parapet
        for sx, sz, sy in ((-1.1, 3.85, 0.19), (-0.4, 3.9, 0.19), (-0.75, 3.88, 0.45)):
            _bake(r, box(0.68, 0.24, 0.40, (98, 88, 66), center=(sx, sy, sz)))
        _bake(r, _crate_prop(0.75, 0.52, 0.55), (0.65, 0.05, 3.9), yaw=-18.0)
        _bake(r, _lattice_tower(3.8, 4.3, height=3.6, base_w=1.15))
        # Layered dawn Capital skyline
        sky_m = Mesh()
        for cx, cz, w, h, d, sd, col, lit in (
            (-13.5, 21.0, 6.0, 12.5, 5.0, 1, (30, 34, 46), 0.22),
            (-6.5, 24.0, 5.8, 15.0, 5.0, 2, (26, 30, 42), 0.28),
            (-0.2, 27.5, 6.4, 18.0, 5.5, 3, (24, 28, 40), 0.26),
            (6.5, 23.0, 5.6, 13.5, 5.0, 4, (28, 32, 44), 0.24),
            (13.0, 25.5, 6.2, 16.0, 5.0, 5, (24, 28, 40), 0.20),
            (-10.0, 36.0, 8.5, 21.0, 6.0, 6, (36, 40, 54), 0.14),
            (2.8, 40.0, 9.5, 23.5, 6.0, 7, (38, 42, 56), 0.16),
            (14.0, 38.0, 8.5, 19.0, 6.0, 8, (34, 38, 52), 0.12),
        ):
            sky_m.add(_soviet_block(cx, cz, w, h, d, seed=sd, col=col, lit=lit), t=(0.0, -5.5, 0.0))
        _bake(r, sky_m)
        _S["beacons"].extend(_b_stacks.smokestack(lambda m: _bake(r, m, (0.0, -5.5, 0.0)), -16.5, 32.0, 24.0))
        _S["beacons"].extend(_b_stacks.radio_mast(lambda m: _bake(r, m, (0.0, -5.5, 0.0)), 10.5, 34.0, 26.0))

    elif key == "MISSION5":
        r.light = Light(direction=(-0.25, 0.80, -0.50), ambient=0.34, diffuse=0.56, sky=0.08, tint=(1.0, 0.86, 0.72))
        r.fog, r.fog_start, r.fog_end = (12, 16, 26), 16.0, 62.0
        brick = _tx("brick", (58, 42, 38))
        conc = _tx("concrete", (28, 32, 36))
        # Tunnel channel floor + right concrete catwalk ledge + dark moonlit river outside
        _bake(r, quad_xz(-2.8, -6.0, 2.8, 7.0, 0.0, conc, seg=1.0))
        _bake(r, box(1.1, 0.22, 12.2, _tx("concrete", (42, 46, 50)), center=(1.85, 0.11, 0.9)))
        _bake(r, quad_xz(-22.0, 7.0, 22.0, 28.0, -0.45, (12, 20, 30), seg=2.5))
        # Vertical brick tunnel walls + stone curb + iron pipe runs
        for sx in (-2.45, 2.45):
            _bake(r, box(0.55, 1.75, 12.2, brick, center=(sx, 0.875, 0.9)))
        _bake(r, box(0.28, 0.26, 12.2, (36, 38, 40), center=(-2.12, 0.13, 0.9)))
        for py in (1.35, 1.58):
            _bake(r, box(0.08, 0.08, 12.0, _tx("rust", (76, 48, 38)), center=(-2.12, py, 0.9)))
        # Arched vaulted brick ceiling + masonry arch ribs (convex segments)
        arch_r = 2.45
        arch_y0 = 1.65
        segs = 8
        vault = Mesh()
        for i in range(segs):
            a0 = math.pi * (i / segs)
            a1 = math.pi * ((i + 1) / segs)
            x0, y0 = arch_r * math.cos(a0), arch_y0 + arch_r * math.sin(a0)
            x1, y1 = arch_r * math.cos(a1), arch_y0 + arch_r * math.sin(a1)
            vault.face([(x0, y0, -5.2), (x1, y1, -5.2), (x1, y1, 7.0), (x0, y0, 7.0)], brick, 2, True)
            for rz in (-1.6, 1.4, 4.4, 6.4):
                mx, my = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
                ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
                ln = math.hypot(x1 - x0, y1 - y0) + 0.06
                vault.add(box(ln, 0.22, 0.34, _tx("stone", (44, 42, 42))), rot_z(ang), (mx, my - 0.06, rz))
        _bake(r, vault)
        # River gate: left leaf closed, right leaf swung open
        for gx in (-2.05, -1.75, -1.45, -1.15, -0.85):
            top_y = arch_y0 + math.sqrt(max(0.0, arch_r * arch_r - gx * gx)) - 0.08
            _bake(r, box(0.07, top_y, 0.07, (30, 32, 36), center=(gx, top_y / 2.0, 6.4)))
        _bake(r, box(1.35, 0.08, 0.08, (30, 32, 36), center=(-1.45, 1.25, 6.4)))
        open_leaf = Mesh()
        for ox in (0.15, 0.45, 0.75, 1.05):
            open_leaf.add(box(0.07, 2.15, 0.07, (30, 32, 36), center=(ox, 1.08, 0.0)))
        open_leaf.add(box(1.15, 0.08, 0.08, (30, 32, 36), center=(0.60, 1.25, 0.0)))
        _bake(r, open_leaf, (2.10, 0.0, 6.4), yaw=-118.0)
        # Wall lantern cages inside tunnel
        for lx, lz in ((-2.10, 0.8), (2.10, 4.2)):
            _bake(r, box(0.18, 0.28, 0.18, (255, 190, 108), center=(lx, 2.45, lz), emissive=True))
        # Outside: stone quay, moored skiff, arched stone bridge & riverfront skyline
        _bake(r, box(44.0, 2.2, 2.4, _tx("concrete", (28, 30, 34)), center=(0.0, 0.75, 22.0)))
        _bake(r, box(2.4, 0.45, 0.9, _tx("m7_plank", (68, 50, 36)), center=(-2.6, -0.32, 10.5)), yaw=24.0)
        # Bridge spans across river at z=16.5
        _bake(r, box(32.0, 0.65, 2.4, _tx("stone", (34, 36, 40)), center=(0.0, 2.55, 16.5)))
        for px in (-6.5, 0.0, 6.5):
            _bake(r, box(1.2, 3.2, 2.5, _tx("stone", (30, 32, 36)), center=(px, 0.9, 16.5)))
        for lx in (-4.8, 0.4, 5.6):
            _bake(r, box(0.14, 2.8, 0.14, (16, 18, 22), center=(lx, 4.2, 15.8)))
            _bake(r, box(0.32, 0.16, 0.32, (255, 198, 118), center=(lx, 5.65, 15.8), emissive=True))
        wf = Mesh()
        for cx, cz, w, h, d, sd, col, lit in (
            (-10.0, 27.0, 7.0, 10.5, 5.0, 21, (20, 22, 28), 0.24),
            (-2.0, 28.5, 7.2, 13.0, 5.0, 22, (18, 20, 26), 0.28),
            (6.0, 26.5, 6.8, 9.8, 5.0, 23, (20, 22, 28), 0.22),
            (13.5, 29.0, 7.5, 13.5, 5.0, 24, (16, 20, 26), 0.20),
        ):
            wf.add(_soviet_block(cx, cz, w, h, d, seed=sd, col=col, lit=lit), t=(0.0, 0.8, 0.0))
        _bake(r, wf)
        _S["beacons"].extend(_b_stacks.smokestack(lambda m: _bake(r, m, (0.0, 0.8, 0.0)), -15.0, 31.0, 17.0))

    elif key == "MISSION6":
        r.light = Light(direction=(-0.35, 0.75, -0.55), ambient=0.38, diffuse=0.52, sky=0.12, tint=(0.82, 0.90, 1.08))
        r.fog, r.fog_start, r.fog_end = (14, 18, 30), 20.0, 76.0
        _bake(r, quad_xz(-20, -14, 24, 4.0, 0.0, _tx("snow", (166, 174, 186)), seg=2.0))
        _bake(r, quad_xz(-20, 4.0, 24, 10.0, -0.4, _tx("ballast", (42, 44, 48)), seg=2.0))
        _bake(r, quad_xz(-24, 10.0, 26, 38.0, -0.25, _tx("snow", (128, 136, 150)), seg=3.0))
        _bake(r, box(40.0, 0.22, 0.4, (74, 76, 80), center=(0.0, -0.08, 3.9)))
        for rz in (5.0, 6.4):
            _bake(r, box(40.0, 0.12, 0.10, (96, 100, 108), center=(0.0, -0.32, rz)))
        for sx in range(-12, 14, 2):
            _bake(r, box(0.22, 0.08, 2.0, _tx("sleeper", (54, 42, 34)), center=(float(sx), -0.38, 5.7)))
        # Station shelter, bench with Velicu dossier folder, station nameplate & catenary poles
        _bake(r, _bench_mesh(), (-2.2, 0.0, 1.3), yaw=8.0)
        _bake(r, _notebook_prop(), (-1.85, 0.48, 1.25), yaw=24.0)
        _bake(r, box(3.8, 0.18, 2.3, _tx("m7_tin", (46, 52, 58)), center=(-4.4, 2.68, 2.1)))
        _bake(r, box(3.8, 0.10, 2.3, (176, 184, 196), center=(-4.4, 2.81, 2.1)))
        _bake(r, box(0.14, 2.6, 0.14, (28, 30, 34), center=(-5.9, 1.3, 2.8)))
        _bake(r, box(0.14, 2.6, 0.14, (28, 30, 34), center=(-2.9, 1.3, 2.8)))
        _bake(r, box(1.9, 0.42, 0.08, (28, 42, 68), center=(-4.4, 2.25, 2.82)))
        _bake(r, box(0.14, 4.4, 0.14, (22, 24, 28), center=(-3.6, 2.2, 2.8)))
        _bake(r, box(0.36, 0.14, 0.36, (255, 206, 128), center=(-3.6, 4.45, 2.8), emissive=True))
        for cx in (-6.5, 4.2):
            _bake(r, box(0.16, 5.2, 0.16, (44, 48, 54), center=(cx, 2.6, 3.6)))
            _bake(r, box(0.12, 0.12, 3.2, (44, 48, 54), center=(cx, 5.05, 5.1)))
        _bake(r, S.train(), (4.8, -0.36, 5.7), yaw=0.0)
        # Border perimeter: customs hut, bloc3d barbed-wire fence & watchtower, snow pines & faceted ridge
        hut, hpos, hyaw = _customs_hut(-4.8, 13.5, yaw=12.0)
        _bake(r, hut, hpos, yaw=hyaw)
        _b_tower.fence_run(lambda m: _bake(r, m, (0.0, -0.25, 0.0)), -16.0, 10.6, 16.0, 10.6, h=2.3, post_every=3.0)
        lens_pos, _ = _b_tower.watchtower(lambda m: _bake(r, m, (0.0, -0.25, 0.0)), 7.2, 16.5, h=5.6, facing="-z")
        _S["beacons"].append((lens_pos[0], lens_pos[1] - 0.25, lens_pos[2]))
        for tx, tz in ((-10.2, 15.5), (-1.4, 16.5), (2.4, 17.8), (11.2, 17.0), (14.5, 19.5)):
            _bake(r, F.tree(int(abs(tx) * 9 + tz)), (tx, -0.25, tz))
        _bake(r, _ridge_band(-32.0, 34.0, 26.0, -0.25, (5.5, 9.8, 6.8, 11.4, 7.6, 10.2, 5.8), (24, 32, 46), depth=12.0))

    elif key == "MISSION7":
        # Farm + foreground Field Receiver table baked into single static batch
        _w.static_scene(r, ("mc3d", key, route, _S["epoch"]))
        try:
            F.setup(r, "burn")
            F.build_static(r, "burn")
            radio_grp = Mesh()
            radio_grp.add(_crate_prop(0.96, 0.64, 0.64), rot_y(16.0), (-0.55, 0.0, -4.45))
            radio_grp.add(_field_radio_prop(), rot_y(18.0), (-0.62, 0.64, -4.42))
            tel = _prop_fitted("telephone_handset", height_m=0.12)
            if tel is not None:
                radio_grp.add(tel, rot_y(42.0), (-0.28, 0.64, -4.46))
            radio_grp.add(box(0.14, 0.24, 0.14, (255, 188, 96), center=(-0.20, 0.76, -4.25), emissive=True))
            _w.add(r, radio_grp)
        except Exception:
            _w.static_end(r, ok=False)
            raise
        _w.static_end(r)

    else:  # MISSION8
        if route == "duty":
            r.light = Light(direction=(0.45, 0.65, 0.60), ambient=0.40, diffuse=0.66, sky=0.15, tint=(0.86, 0.92, 1.06))
            r.fog, r.fog_start, r.fog_end = (24, 30, 42), 20.0, 86.0
            _bake(r, quad_xz(-16, -12, 16, 14, 0.0, _tx("snow", (162, 170, 182)), seg=2.0))
            _bake(r, quad_xz(-24, 12, 24, 48, -3.5, _tx("pavement", (32, 36, 42)), seg=3.0))
            # Snowy ridge balustrade & barrier
            _bake(r, box(14.0, 0.55, 0.38, _tx("stone", (62, 66, 72)), center=(0.0, 0.275, 3.6)))
            for tx, tz in ((-4.2, 4.8), (-5.8, 7.2), (4.4, 5.2), (6.0, 8.0), (-8.5, 9.5)):
                _bake(r, F.tree(int(abs(tx) * 10)), (tx, 0.0, tz))
            # Concrete Helipad with painted H + scorch + Guard jeep on approach
            _bake(r, box(7.0, 0.18, 7.0, (54, 58, 62), center=(1.5, -3.41, 21.8)))
            for hx in (0.6, 2.4):
                _bake(r, quad_xz(hx - 0.18, 20.2, hx + 0.18, 23.4, -3.31, (186, 152, 62)))
            _bake(r, quad_xz(0.6, 21.62, 2.4, 21.98, -3.31, (186, 152, 62)))
            _bake(r, quad_xz(-0.6, 19.5, 3.8, 23.8, -3.30, _tx("scorch", (18, 16, 16))))
            _bake(r, S.jeep(), (-5.6, -3.5, 16.5), yaw=56.0)
            # Monumental Presidential Palace colonnade in background
            pal = Mesh()
            stone = _tx("m7_plaster", (66, 70, 78))
            trim = _tx("stone", (46, 50, 58))
            pal.add(box(24.0, 1.4, 8.0, trim, center=(0.0, 0.7, 37.0)))
            pal.add(box(20.0, 0.5, 2.4, trim, center=(0.0, 0.25, 32.5)))
            pal.add(box(22.0, 8.5, 6.5, stone, center=(0.0, 5.65, 37.5)))
            pal.add(box(12.0, 10.5, 7.2, stone, center=(0.0, 6.65, 37.2)))
            pal.add(box(13.0, 0.8, 8.0, trim, center=(0.0, 12.2, 37.2)))
            pal.add(box(8.0, 1.8, 7.2, trim, center=(0.0, 13.4, 37.2)))
            for cx in (-4.8, -2.9, -1.0, 1.0, 2.9, 4.8):
                pal.add(box(0.55, 8.4, 0.55, (86, 90, 98), center=(cx, 5.6, 33.0)))
            for wx in (-8.5, -6.5, 6.5, 8.5):
                for wy in (4.2, 7.4):
                    pal.add(box(0.95, 1.65, 0.08, (238, 196, 118), center=(wx, wy, 34.2), emissive=True))
            for bx in (-3.8, 3.8):
                pal.add(box(0.85, 3.6, 0.08, (148, 34, 32), center=(bx, 6.2, 33.4)))
                pal.add(box(0.90, 0.22, 0.10, (196, 162, 78), center=(bx, 8.05, 33.4)))
            _bake(r, pal, (0.0, -3.5, 0.0))
            _bake(r, _ridge_band(-36.0, 36.0, 44.0, -3.5, (7.0, 11.5, 8.5, 13.0, 9.0, 11.0, 6.5), (26, 32, 44), depth=10.0))
        else:
            r.light = Light(direction=(-0.35, 0.65, -0.58), ambient=0.34, diffuse=0.46, sky=0.10, tint=(0.76, 0.84, 1.02))
            r.fog, r.fog_start, r.fog_end = (16, 22, 34), 20.0, 82.0
            _bake(r, quad_xz(-24, -16, 26, 18, 0.0, _tx("snow", (142, 150, 166)), seg=2.5))
            _bake(r, quad_xz(-24, 4.0, 26, 9.0, 0.02, _tx("ballast", (46, 46, 50)), seg=2.0))
            _bake(r, quad_xz(-26, 9.0, 28, 38.0, 0.0, _tx("snow", (118, 126, 142)), seg=3.0))
            for rz in (5.6, 7.0):
                _bake(r, box(48.0, 0.12, 0.10, (98, 102, 110), center=(0.0, 0.08, rz)))
            for sx in range(-12, 16, 2):
                _bake(r, box(0.22, 0.06, 2.0, _tx("sleeper", (54, 42, 34)), center=(float(sx), 0.03, 6.3)))
            _bake(r, S.tractor(), (-2.4, 0.0, 1.9), yaw=22.0)
            _bake(r, S.barrier_arm(), (-4.1, 0.05, 3.6), yaw=205.0)
            _bake(r, S.train(), (6.0, 0.04, 6.3), yaw=0.0)
            # Customs hut, bloc3d barbed wire + watchtower, signal mast, pines & faceted mountain ridge
            hut, hpos, hyaw = _customs_hut(-5.6, 12.2, yaw=18.0)
            _bake(r, hut, hpos, yaw=hyaw)
            _b_tower.fence_run(lambda m: _bake(r, m), -18.0, 10.6, 18.0, 10.6, h=2.3, post_every=3.0)
            lens_pos, _ = _b_tower.watchtower(lambda m: _bake(r, m), 7.4, 16.5, h=5.8, facing="-z")
            _S["beacons"].append(lens_pos)
            _bake(r, box(0.14, 4.4, 0.14, (30, 32, 36), center=(-1.8, 2.2, 9.2)))
            _bake(r, box(1.2, 0.10, 0.10, (30, 32, 36), center=(-1.8, 4.1, 9.2)))
            _bake(r, box(0.22, 0.22, 0.14, (238, 64, 52), center=(-1.8, 3.6, 9.08), emissive=True))
            for tx, tz in ((-10.5, 13.5), (-1.4, 15.0), (2.5, 16.5), (10.8, 16.0), (14.2, 18.5)):
                _bake(r, F.tree(int(abs(tx) * 10 + tz)), (tx, 0.0, tz))
            _bake(r, _ridge_band(-34.0, 36.0, 26.0, 0.0, (5.8, 10.2, 7.2, 12.0, 8.0, 10.6, 6.0), (24, 30, 44), depth=12.0))


def _draw_dynamic_and_fx(r, buf, key, route, t_ms, drift):
    from core.outfits import OUTFIT_GUARD
    from cutscenes import m5fx3d as _m5
    from cutscenes import m6fx3d as _fx
    from cutscenes import m6world3d as _w
    from cutscenes import m7world3d as F
    from engine3d.rig import POSES

    del _w.LAST[:]
    lay = _fx.FX_LAYER

    if key == "MISSION0":
        eye = (-2.85 + 0.18 * drift, 1.82 + 0.04 * math.sin(t_ms * 0.0008), -3.45)
        tgt = (0.25, 0.92, 1.15)
        r.set_camera(eye, tgt, 45.0)
        r.set_lights([
            {"pos": (-0.35, 3.3, 0.55), "color": (255, 212, 148), "intensity": 1.25, "range": 9.5},
            {"pos": (-2.6, 1.4, 2.8), "color": (88, 214, 134), "intensity": 0.55, "range": 4.5},
        ])
        buf.fill((14, 16, 20))
        r.begin()
        r.add_static()
        bpos = (-1.45, 0.0, -0.35)
        byaw = _w.yaw_to(bpos, (-0.35, 0.0, 0.55))
        bpose = _pose_actor(("biribel", "krap"), POSES["ready"], bpos, byaw, (-0.35, 0.92, 0.50), mode="ready", spine=10)
        _ground_shadow(r, bpos, 0.42, 0.42, 0.44)
        _ground_shadow(r, (-0.35, 0.0, 0.55), 0.85, 0.85, 0.40)
        _ground_shadow(r, (1.15, 0.0, 1.05), 0.42, 0.42, 0.40)
        _w.actor(r, ("biribel", "krap"), bpose, bpos, byaw, t_ms, seed=5, amp=0.18, rifle_on=True, expression="stern", mouth=0.0)
        r.add_sprite((-0.35, 0.03, 0.55), F.pool((255, 200, 132), 2.8, intensity=0.28, squash=0.55), layer=lay)
        r.add_sprite((-0.35, 3.48, 0.55), _fx.sodium_lamp(t_ms, seed=1, radius_m=1.6), layer=lay)
        r.add_sprite((-0.35, 3.40, 0.55), _m5.light_shaft((255, 210, 148), height_m=3.5, top_m=0.45, bot_m=1.8, t=t_ms, seed=2, intensity=0.22), layer=lay)
        r.add_sprite((-2.85, 1.18, 3.10), _fx.crt_bloom(t_ms, col=(88, 214, 134), w_m=0.42, h_m=0.34, intensity=0.55), layer=lay)
        r.add_sprite((-0.35, 1.6, 0.55), _m5.dust_motes(t_ms, seed=3, count=22, spread_m=(1.8, 1.3)), layer=lay)

    elif key == "MISSION1":
        eye = (-4.5 + 0.28 * drift, 1.48, -5.2 + 0.14 * drift)
        tgt = (0.25, 1.02, 1.45)
        r.set_camera(eye, tgt, 45.0)
        r.set_lights([
            {"pos": (3.8, 1.1, 1.3), "color": (255, 236, 185), "intensity": 1.4, "range": 14.0,
             "kind": "spot", "dir": (0.95, -0.15, -0.3), "cone": 0.82},
            {"pos": (-4.2, 4.6, 2.4), "color": (255, 190, 118), "intensity": 1.05, "range": 10.0},
            {"pos": (-2.4, 1.1, -0.6), "color": (255, 60, 44), "intensity": 0.65, "range": 5.5},
        ])
        _m5.night_sky(r, buf, t_ms, (6, 8, 13), (20, 22, 30), stars=0, clouds=2, sodium=(30, 20, 16))
        r.begin()
        r.add_static()
        bpos = (-1.95, 0.0, -1.25)
        byaw = _w.yaw_to(bpos, (0.95, 0.0, 1.2))
        bpose = _pose_actor(("biribel", "krap"), POSES["stand"], bpos, byaw, (0.95, 1.1, 1.2), mode="carry")
        _ground_shadow(r, bpos, 0.42, 0.42, 0.44)
        _ground_shadow(r, (0.95, 0.0, 1.2), 2.8, 1.4, 0.45)
        _w.actor(r, ("biribel", "krap"), bpose, bpos, byaw, t_ms, seed=11, amp=0.18, rifle_on=True, expression="stern", mouth=0.0)
        r.add_sprite((-4.2, 4.68, 2.4), _fx.sodium_lamp(t_ms, seed=3, radius_m=2.2), layer=lay)
        r.add_sprite((-3.8, 0.04, 2.4), F.pool((255, 196, 128), 3.0, intensity=0.28, squash=0.5), layer=lay)
        _water_shimmer(r, -2.0, 0.02, 0.8, 0.55, 2.0, (128, 36, 32), t_ms, seed=1)
        _water_shimmer(r, 6.4, -0.62, 11.0, 0.75, 4.8, (132, 108, 72), t_ms, seed=4)
        for bx, by, bz in _S["beacons"]:
            r.add_sprite((bx, by, bz), _fx.beacon((240, 68, 54), radius_m=0.38, t=t_ms, period_ms=1600.0), layer=lay)
        _m5.rain3d(r, t_ms, seed=7, n_near=38, n_far=76)

    elif key == "MISSION2":
        eye = (3.2 + 0.22 * drift, 1.58, -4.9 + 0.12 * drift)
        tgt = (-0.6, 1.05, 1.1)
        r.set_camera(eye, tgt, 45.0)
        r.set_lights([
            {"pos": (2.0, 1.5, 1.4), "color": (90, 235, 140), "intensity": 1.15, "range": 6.5},
            {"pos": (-1.8, 1.8, 1.2), "color": (255, 176, 82), "intensity": 1.0, "range": 10.5},
        ])
        _m5.night_sky(r, buf, t_ms, (6, 9, 15), (18, 24, 34), stars=24, clouds=2)
        r.begin()
        r.add_static()
        bpos = (0.45, 0.0, -0.85)
        byaw = _w.yaw_to(bpos, (-2.1, 0.0, 1.15))
        bpose = _pose_actor(("biribel", "krap"), POSES["ready"], bpos, byaw, (-2.1, 0.9, 1.15), mode="ready")
        _ground_shadow(r, bpos, 0.42, 0.42, 0.44)
        _ground_shadow(r, (-2.1, 0.0, 1.15), 2.1, 1.2, 0.46)
        _w.actor(r, ("biribel", "krap"), bpose, bpos, byaw, t_ms, seed=18, amp=0.18, rifle_on=True, expression="stern", mouth=0.0)
        r.add_sprite((1.95, 1.15, 1.72), _fx.crt_bloom(t_ms, col=(82, 228, 132), w_m=0.52, h_m=0.40, intensity=0.68), layer=lay)
        r.add_sprite((-1.2, 0.12, -0.6), _fx.glow((255, 132, 48), 1.3, t_ms, flicker=0.18, seed=12, intensity=0.75, max_px=34), layer=lay)
        r.add_sprite((-1.2, 0.04, -0.6), F.pool((255, 132, 48), 2.2, intensity=0.30, squash=0.5), layer=lay)
        r.add_sprite((-4.0, 5.15, -1.8), _fx.beacon((255, 164, 58), radius_m=0.36, t=t_ms, period_ms=1400.0), layer=lay)
        _water_shimmer(r, -1.6, 0.02, -0.6, 0.45, 1.8, (138, 78, 36), t_ms, seed=2)
        _m5.rain3d(r, t_ms, seed=19, n_near=30, n_far=60)

    elif key == "MISSION3":
        eye = (0.45 + 0.20 * drift, 1.62, -2.65)
        tgt = (-0.05, 1.22, 1.65)
        r.set_camera(eye, tgt, 46.0)
        r.set_lights([
            {"pos": (0.0, 2.5, 3.0), "color": (210, 62, 54), "intensity": 0.75, "range": 6.5},
            {"pos": (-0.5, 1.4, 0.9), "color": (140, 218, 150), "intensity": 0.80, "range": 5.0},
            {"pos": (0.6, 1.4, 0.9), "color": (235, 152, 86), "intensity": 0.65, "range": 4.5},
            {"pos": (0.0, 2.8, 5.8), "color": (180, 200, 240), "intensity": 0.85, "range": 9.0},
        ])
        buf.fill((8, 12, 14))
        r.begin()
        r.add_static()
        bpos = (1.15, 0.0, 0.45)
        byaw = _w.yaw_to(bpos, (-0.2, 0.0, 1.4))
        bpose = _pose_actor(("biribel", "krap"), POSES["stand"], bpos, byaw, (-0.45, 1.15, 1.32), mode="carry", spine=10)
        vpos = (-1.25, 0.0, 0.65)
        vyaw = _w.yaw_to(vpos, bpos)
        vpose = _pose_actor("volkov", POSES["talk_turn"], vpos, vyaw, (1.15, 1.56, 0.45), expression="stern")
        _ground_shadow(r, bpos, 0.42, 0.42, 0.44)
        _ground_shadow(r, vpos, 0.42, 0.42, 0.44)
        _w.actor(r, ("biribel", "krap"), bpose, bpos, byaw, t_ms, seed=21, amp=0.18, rifle_on=True, expression="stern", mouth=0.0)
        _w.actor(r, "volkov", vpose, vpos, vyaw, t_ms, seed=22, amp=0.16, expression="stern", mouth=0.0)
        r.add_sprite((-0.58, 1.18, 1.18), _fx.crt_bloom(t_ms, col=(144, 214, 152), w_m=0.5, h_m=0.38, intensity=0.55), layer=lay)
        r.add_sprite((0.0, 2.82, 3.0), _fx.glow((220, 56, 48), 1.2, t_ms, intensity=0.55, max_px=32), layer=lay)
        r.add_sprite((0.0, 3.3, 5.2), _m5.light_shaft((180, 200, 238), height_m=3.2, top_m=0.8, bot_m=2.2, t=t_ms, seed=5, intensity=0.20), layer=lay)
        r.add_sprite((0.0, 1.5, 1.2), _m5.dust_motes(t_ms, seed=23, count=18, spread_m=(1.6, 1.0)), layer=lay)

    elif key == "MISSION4":
        eye = (-4.1 + 0.25 * drift, 2.02, -3.4)
        tgt = (0.3, 1.30, 3.6)
        r.set_camera(eye, tgt, 55.0)
        r.set_lights([
            {"pos": (4.0, 3.2, 8.0), "color": (255, 196, 134), "intensity": 1.15, "range": 18.0},
            {"pos": (-4.9, 2.0, 1.2), "color": (255, 192, 114), "intensity": 0.70, "range": 6.5},
        ])
        _m5.night_sky(r, buf, t_ms, (22, 34, 58), (168, 114, 78), stars=10, clouds=3, sodium=(190, 120, 82), mist=(90, 86, 104))
        r.begin()
        r.add_static()
        # Guy wires anchoring the rooftop broadcast mast
        for gx, gz in ((0.8, 2.4), (6.4, 2.4), (1.2, 4.5), (6.2, 4.5)):
            r.add_line3d((3.8, 3.5, 4.3), (gx, 0.92, gz), (44, 48, 54), 1, layer=2)
        bpos = (-1.35, 0.05, 2.55)
        vpos = (0.45, 0.05, 2.85)
        mpos = (-2.55, 0.05, 2.15)
        byaw, vyaw, myaw = 16.0, -28.0, 34.0
        bpose = _pose_actor(("biribel", "krap"), POSES["stand"], bpos, byaw, (1.5, 1.8, 12.0), mode="carry")
        vpose = _pose_actor("vasile", POSES["talk_turn"], vpos, vyaw, (bpos[0], 1.30, bpos[2]), expression="stern")
        r.add_sprite((-4.9, 0.08, 0.4), F.pool((255, 192, 114), 2.8, intensity=0.30, squash=0.55), layer=lay)
        r.add_sprite((-1.0, 0.08, 0.4), _m5.wet_reflection((214, 152, 108), t_ms, seed=11, length_m=1.8, width_m=0.55, intensity=0.35), layer=2)
        r.add_sprite((3.8, 4.98, 4.3), _fx.beacon((240, 74, 58), radius_m=0.45, t=t_ms, period_ms=1400.0), layer=lay)
        mpose = _pose_actor("maru", POSES["stand"], mpos, myaw, (5.0, 2.0, 14.0), spine=6, expression="neutral")
        for p in (bpos, vpos, mpos):
            _ground_shadow(r, p, 0.40, 0.40, 0.36)
        _w.actor(r, ("biribel", "krap"), bpose, bpos, byaw, t_ms, seed=31, amp=0.18, rifle_on=True, expression="neutral", mouth=0.0)
        _w.actor(r, "vasile", vpose, vpos, vyaw, t_ms, seed=32, amp=0.16, expression="stern", mouth=0.0)
        _w.actor(r, "maru", mpose, mpos, myaw, t_ms, seed=33, amp=0.18, expression="neutral", mouth=0.0)
        r.add_sprite((2.6, 8.18, 3.6), _fx.beacon((240, 74, 58), radius_m=0.45, t=t_ms, period_ms=1400.0), layer=lay)
        r.add_sprite((6.5, 4.2, 16.0), _fx.haze((212, 152, 114), 7.0, t_ms, seed=35, intensity=0.18), layer=lay)
        for bx, by, bz in _S["beacons"]:
            r.add_sprite((bx, by, bz), _fx.beacon((240, 68, 54), radius_m=0.45, t=t_ms, period_ms=1700.0), layer=lay)

    elif key == "MISSION5":
        eye = (-0.55 + 0.18 * drift, 1.45, -3.3)
        tgt = (0.15, 1.35, 4.5)
        r.set_camera(eye, tgt, 46.0)
        r.set_lights([
            {"pos": (-1.9, 2.5, 0.8), "color": (255, 168, 92), "intensity": 1.0, "range": 7.5},
            {"pos": (1.9, 2.5, 4.2), "color": (255, 168, 92), "intensity": 0.95, "range": 7.5},
            {"pos": (0.4, 5.2, 16.0), "color": (255, 198, 118), "intensity": 1.15, "range": 14.0},
        ])
        _m5.night_sky(r, buf, t_ms, (6, 10, 16), (22, 32, 44), stars=0, clouds=2, sodium=(34, 24, 18))
        r.begin()
        r.add_static()
        bpos = (1.55, 0.22, 1.45)
        byaw = _w.yaw_to(bpos, (-0.55, 0.0, 3.15))
        bpose = _pose_actor(("biribel", OUTFIT_GUARD), POSES["ready"], bpos, byaw, (-0.55, 1.45, 3.15), mode="ready")
        mpos = (-0.55, 0.0, 3.15)
        myaw = _w.yaw_to(mpos, (0.5, 0.0, 14.0))
        mpose = _pose_actor("maru", POSES["stand"], mpos, myaw, (0.5, 1.6, 16.0), spine=8, expression="worried")
        _ground_shadow(r, bpos, 0.40, 0.40, 0.44)
        _ground_shadow(r, mpos, 0.40, 0.40, 0.44)
        _w.actor(r, ("biribel", OUTFIT_GUARD), bpose, bpos, byaw, t_ms, seed=41, amp=0.18, rifle_on=True, expression="stern", mouth=0.0)
        _w.actor(r, "maru", mpose, mpos, myaw, t_ms, seed=42, amp=0.18, expression="worried", mouth=0.0)
        r.add_sprite((-2.0, 2.45, 0.8), _fx.glow((255, 176, 98), 0.75, t_ms, flicker=0.1, seed=1, max_px=26), layer=lay)
        r.add_sprite((2.0, 2.45, 4.2), _fx.glow((255, 176, 98), 0.75, t_ms, flicker=0.1, seed=2, max_px=26), layer=lay)
        r.add_sprite((-0.6, 0.04, 0.9), F.pool((255, 172, 96), 2.4, intensity=0.28, squash=0.55), layer=lay)
        r.add_sprite((0.5, 0.04, 4.1), F.pool((255, 172, 96), 2.2, intensity=0.26, squash=0.55), layer=lay)
        for idx, lx in enumerate((-4.8, 0.4, 5.6)):
            r.add_sprite((lx, 5.65, 15.8), _fx.sodium_lamp(t_ms, seed=20 + idx, radius_m=2.0), layer=lay)
            _water_shimmer(r, lx, -0.43, 8.8, 0.55, 5.2, (132, 96, 58), t_ms, seed=idx)
        r.add_sprite((0.0, 0.6, 12.0), _fx.haze((68, 86, 108), 5.5, t_ms, seed=9, intensity=0.24), layer=lay)
        for bx, by, bz in _S["beacons"]:
            r.add_sprite((bx, by, bz), _fx.beacon((240, 68, 54), radius_m=0.36, t=t_ms, period_ms=1700.0), layer=lay)

    elif key == "MISSION6":
        eye = (-4.5 + 0.26 * drift, 1.62, -4.4 + 0.12 * drift)
        tgt = (0.7, 1.38, 2.6)
        r.set_camera(eye, tgt, 45.0)
        r.set_lights([
            {"pos": (-3.6, 4.2, 2.8), "color": (255, 206, 128), "intensity": 1.0, "range": 12.0},
            {"pos": (7.2, 6.2, 15.5), "color": (255, 214, 144), "intensity": 0.90, "range": 14.0},
        ])
        _w.night(r, buf, t_ms, top=(6, 10, 18), bot=(22, 30, 48), stars=42, moon=(118.0, 14.0), seed=6)
        r.begin()
        r.add_static()
        # Overhead railway catenary wires
        r.add_line3d((-6.5, 5.05, 6.3), (12.0, 5.05, 6.3), (38, 42, 48), 1, layer=2)
        r.add_line3d((-6.5, 4.85, 5.0), (12.0, 4.85, 5.0), (38, 42, 48), 1, layer=2)
        bpos = (-1.15, 0.0, -0.35)
        byaw = _w.yaw_to(bpos, (4.8, 0.0, 5.7))
        bpose = _pose_actor(("biribel", OUTFIT_GUARD), POSES["stand"], bpos, byaw, (5.2, 1.6, 5.7), mode="carry", spine=6)
        _ground_shadow(r, bpos, 0.42, 0.42, 0.36)
        _ground_shadow(r, (-2.2, 0.0, 1.3), 0.9, 0.45, 0.32)
        _w.actor(r, ("biribel", OUTFIT_GUARD), bpose, bpos, byaw, t_ms, seed=51, amp=0.18, rifle_on=True, expression="sad", mouth=0.0)
        r.add_sprite((-3.6, 4.45, 2.8), _fx.sodium_lamp(t_ms, seed=8, radius_m=2.0), layer=lay)
        r.add_sprite((-3.2, 0.04, 2.0), F.pool((255, 200, 126), 3.4, intensity=0.28, squash=0.55), layer=lay)
        for bx, by, bz in _S["beacons"]:
            r.add_sprite((bx, by, bz), _fx.sodium_lamp(t_ms, seed=9, radius_m=1.8), layer=lay)
        _w.snow3d(r, t_ms, seed=66, n=85, spread=14.0, height=10.0, speed=1.3)

    elif key == "MISSION7":
        eye = F.mix((-2.35, 2.02, -7.75), (-1.70, 1.95, -7.15), 0.5 + 0.5 * drift)
        tgt = (5.2, 2.15, 4.5)
        r.set_camera(eye, tgt, 48.0)
        r.set_lights(F.burn_lights(t_ms, 0.0) + [
            {"pos": (-0.35, 1.35, -4.45), "color": (255, 178, 92), "intensity": 0.95, "range": 6.5},
        ])
        F.sky(r, buf, t_ms, "burn", seed=37)
        r.begin()
        r.add_static()
        F.burn_fx(r, t_ms, grow=1.0, layer=2)
        F.burn_roof(r, 1.0)
        # Loop rising spark bursts from the collapsing barn roof
        spark_t0 = (int(t_ms) // 2400) * 2400
        r.add_sprite((12.5, 4.2, 10.5), F.sparks(t_ms, spark_t0, seed=70 + (spark_t0 // 2400) % 5, n=36, speed=6.5, life=2.4), layer=lay)
        r.add_sprite((-0.20, 0.78, -4.25), _fx.glow((255, 178, 86), 0.9, t_ms, flicker=0.08, seed=14, intensity=0.75, max_px=26), layer=lay)
        r.add_sprite((-0.55, 0.05, -4.45), F.pool((255, 178, 92), 2.2, intensity=0.28, squash=0.5), layer=lay)
        # Bodi seated with rifle looking at burning barn + Alex standing watch
        yaw = _w.yaw_to(F.SEAT_BURN, (13.0, 0.0, 12.0))
        pos = (F.SEAT_BURN[0], F.SEAT_BURN[1] - F.SEAT_H, F.SEAT_BURN[2])
        pose = _pose_actor(("ally", "bodi"), F.sit_pose(), pos, yaw, (13.0, 3.2, 12.0), expression="sad")
        _w.actor(r, ("ally", "bodi"), pose, pos, yaw, t_ms, seed=61, amp=0.18, rifle_on=True, expression="sad", mouth=0.0)
        apos = (-3.6, 0.0, -2.0)
        ayaw = _w.yaw_to(apos, (13.0, 0.0, 12.0))
        apose = _pose_actor(("ally", "alex"), POSES["ready"], apos, ayaw, (13.0, 2.8, 12.0), mode="ready")
        _ground_shadow(r, apos, 0.42, 0.42, 0.40)
        _w.actor(r, ("ally", "alex"), apose, apos, ayaw, t_ms, seed=62, amp=0.18, rifle_on=True, expression="worried", mouth=0.0)

    else:  # MISSION8
        if route == "duty":
            eye = (-3.6 + 0.24 * drift, 1.92, -3.6)
            tgt = (0.6, 0.5, 12.0)
            r.set_camera(eye, tgt, 46.0)
            r.set_lights([
                {"pos": (1.5, 2.0, 18.0), "color": (255, 164, 84), "intensity": 1.25, "range": 22.0},
                {"pos": (-5.6, -1.6, 16.5), "color": (120, 160, 255), "intensity": 0.65, "range": 10.0},
                {"pos": (-2.4, 2.8, -3.2), "color": (160, 188, 232), "intensity": 0.55, "range": 12.0},
            ])
            _m5.night_sky(r, buf, t_ms, (12, 18, 30), (54, 62, 82), stars=18, clouds=3)
            r.begin()
            r.add_static()
            _w.helicopter(r, t_ms, (1.5, -3.3, 21.8), yaw=-35.0, rotor_speed=0.0, lit=False, bank=12.0, pitch=-7.0, pilot=False)
            bpos = (-1.1, 0.0, 0.7)
            byaw = _w.yaw_to(bpos, (1.5, -3.0, 21.8))
            bpose = _pose_actor(("biribel", OUTFIT_GUARD), POSES["stand"], bpos, byaw, (1.5, -1.5, 21.8), flags=("ak74",), mode="carry")
            _ground_shadow(r, bpos, 0.42, 0.42, 0.38)
            _w.actor(r, ("biribel", OUTFIT_GUARD), bpose, bpos, byaw, t_ms, seed=81, amp=0.18, rifle_on=True, flags=("ak74",), expression="stern", mouth=0.0)
            F.fire(r, (2.2, -3.3, 21.0), t_ms, seed=82, size=1.45)
            spark_t0 = (int(t_ms) // 2600) * 2600
            r.add_sprite((2.0, -2.5, 21.0), F.sparks(t_ms, spark_t0, seed=83, n=28, speed=5.5, life=2.2), layer=lay)
            r.add_sprite((-5.6, -1.7, 16.5), _fx.beacon((220, 48, 44), radius_m=0.45, t=t_ms, period_ms=700.0), layer=lay)
            r.add_sprite((0.0, -1.0, 26.0), _fx.haze((110, 120, 142), 8.0, t_ms, seed=85, intensity=0.20), layer=lay)
        else:
            eye = (-4.8 + 0.28 * drift, 1.72, -4.6)
            tgt = (1.8, 1.50, 4.5)
            r.set_camera(eye, tgt, 46.0)
            r.set_lights([
                {"pos": (-1.2, 1.4, 3.0), "color": (255, 224, 164), "intensity": 0.90, "range": 10.0},
                {"pos": (7.4, 6.0, 15.8), "color": (255, 214, 148), "intensity": 0.85, "range": 14.0},
            ])
            _w.night(r, buf, t_ms, top=(12, 16, 28), bot=(36, 44, 64), stars=22, moon=False, seed=88)
            r.begin()
            r.add_static()
            bodipos = (-0.35, 0.0, 0.65)
            biripos = (5.65, 1.30, 6.3)
            bodiyaw = _w.yaw_to(bodipos, biripos)
            biriyaw = _w.yaw_to(biripos, bodipos)
            bodipose = _pose_actor(("ally", "bodi"), POSES["stand"], bodipos, bodiyaw, (biripos[0], biripos[1] + 1.56, biripos[2]), mode="carry")
            biripose = _pose_actor(("biribel", OUTFIT_GUARD), POSES["talk_turn"], biripos, biriyaw, (bodipos[0], bodipos[1] + 1.56, bodipos[2]))
            _ground_shadow(r, bodipos, 0.42, 0.42, 0.36)
            _ground_shadow(r, (-2.4, 0.0, 1.9), 1.6, 1.2, 0.40)
            _w.actor(r, ("ally", "bodi"), bodipose, bodipos, bodiyaw, t_ms, seed=61, amp=0.18, rifle_on=True, expression="sad", mouth=0.0)
            _w.actor(r, ("biribel", OUTFIT_GUARD), biripose, biripos, biriyaw, t_ms, seed=93, amp=0.18, expression="sad", mouth=0.0)
            r.add_sprite((-1.8, 3.6, 9.0), _fx.beacon((238, 64, 52), radius_m=0.35, t=t_ms, period_ms=1100.0), layer=lay)
            r.add_sprite((-0.6, 0.04, 3.6), F.pool((255, 224, 158), 3.0, intensity=0.22, squash=0.5), layer=lay)
            for bx, by, bz in _S["beacons"]:
                r.add_sprite((bx, by, bz), _fx.sodium_lamp(t_ms, seed=18, radius_m=1.8), layer=lay)
            _w.snow3d(r, t_ms, seed=88, n=55, spread=14.0, height=10.0, speed=1.1)

    r.flush(buf)


def render(key, route, elapsed_ms, reduced_motion=False):
    """Return a 320x190 graded 3D Surface for the dossier exhibit, or None."""
    if key in _S["bad_keys"]:
        return None
    if not enabled():
        return None
    try:
        r, buf = _renderer()
        is_sw = "gl" not in str(getattr(r, "backend", "")).lower()
        t_anim = 0 if reduced_motion else int(elapsed_ms)

        if _S["key"] == key and _S["route"] == route and _S["cached_surf"] is not None:
            if reduced_motion or (is_sw and _S["last_draw_ms"] >= 0 and t_anim - _S["last_draw_ms"] < 140):
                return _S["cached_surf"]

        if _S["key"] != key or _S["route"] != route:
            _setup_static(r, key, route)
            _S["key"] = key
            _S["route"] = route

        drift = 0.0 if reduced_motion else math.sin(t_anim * 0.00055)
        _draw_dynamic_and_fx(r, buf, key, route, t_anim, drift)

        if buf.get_size() != (OUT_W, OUT_H):
            out = pygame.transform.smoothscale(buf, (OUT_W, OUT_H))
        else:
            out = buf.copy()

        prof_key = f"{key}_{route}" if key == "MISSION8" and route in ("duty", "revenge") else key
        post_spec = _POST_PROFILES.get(prof_key)
        graded = False
        if post_spec:
            try:
                from cutscenes import post3d as _post
                if _post._quality() > 0:
                    _post.apply_post(out, post_spec, t_anim, scene_id=prof_key)
                    graded = True
            except Exception:
                traceback.print_exc()
        if not graded:
            try:
                from cutscenes import m6fx3d as _fx
                _fx.grade_cine(out)
            except Exception:
                pass

        _S["cached_surf"] = out
        _S["last_draw_ms"] = t_anim
        return out
    except Exception:
        _S["bad_keys"] = frozenset(set(_S["bad_keys"]) | {key})
        if not _S["printed_err"]:
            _S["printed_err"] = True
            traceback.print_exc()
        return None
