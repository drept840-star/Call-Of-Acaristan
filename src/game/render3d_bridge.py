"""game.render3d_bridge - apply ae.set3d/1 data to a live 3D renderer (RPE6 Phase 8).

The bridge is the game half of §6.7: ``engine.render3d`` flattens a set
into ordered primitives; this module walks them onto an ``engine3d``
renderer through the host's own callbacks (``add``/``dec``/``spr``/
``decal_add`` - the take modules' existing helpers, so the painter-sort
and bias semantics stay exactly the legacy ones).  A decal primitive
whose asset is unavailable emits its geometric ``fallback`` primitives,
as §6.7 requires.  ``sprite3d`` primitives name an FX constructor on the
host ``fx`` module (``glow``, ``window_glow``, ...); its ``params`` are
passed as keyword arguments with colours converted back to tuples.

``ACA_SET_SRC=legacy`` is the strangler fallback: hosts keep their
imperative builders and skip the data path entirely.
"""
from __future__ import annotations

import os

from engine.render3d import blend_lighting, build, load_preset_library, load_set3d, resolve_lighting
from engine3d.core import Light, box, quad_xz

__all__ = ["SETS_DIR", "PRESETS_DIR", "PROP_LIBRARY", "use_legacy", "set_prims", "apply_set",
           "presets", "set_lighting", "quality_3d", "emit_lights", "build_mesh",
           "shadow_prims", "emit_shadows", "load_texture", "push_textures", "flicker_at",
           "load_mesh_asset", "mesh_for_prim", "MESHES_DIR",
           "dynamic_faces", "render_scale_3d", "render_size_3d",
           "bake_cast_shadows", "humanoid_meshes", "TEXTURES_DIR"]

SETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content", "sets")
PRESETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content", "lighting3d")
TEXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content", "textures")
MESHES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content", "meshes")

_mesh_cache: dict = {}


def load_mesh_asset(ref: str):
    """Load an ae.mesh/1 asset (ADR-024) -> (verts, faces) raw data."""
    if ref in _mesh_cache:
        return _mesh_cache[ref]
    import json

    path = os.path.join(MESHES_DIR, f"{ref}.mesh.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("schema") != "ae.mesh/1":
        raise ValueError(f"{path}: schema must be ae.mesh/1")
    _mesh_cache[ref] = (data["verts"], data["faces"])
    return _mesh_cache[ref]


def mesh_for_prim(prim):
    """Instantiate an imported mesh prim (pos/yaw/scale) as a Mesh."""
    import math

    from engine3d.core import Mesh

    verts, faces = load_mesh_asset(prim["ref"])
    sc = float(prim.get("scale", 1.0) or 1.0)
    yaw = math.radians(float(prim.get("yaw", 0) or 0))
    cy, sy = math.cos(yaw), math.sin(yaw)
    px, py, pz = (float(v) for v in prim.get("pos", (0, 0, 0)))
    out = Mesh()
    out.verts = [(px + (x * cy + z * sy) * sc, py + y * sc,
                  pz + (-x * sy + z * cy) * sc) for x, y, z in verts]
    out.faces = [(tuple(idx), tuple(col), 2, False, False)
                 for idx, col in faces]
    return out

_tex_cache: dict = {}


def load_texture(tex_id: str):
    """Load an ae.texture/1 palette texture -> numpy (h, w, 3) uint8.

    Rows are palette-indexed strings (nearest-sampled by the software
    renderer, P11 step 9); bad data raises ValueError naming the file.
    """
    if tex_id in _tex_cache:
        return _tex_cache[tex_id]
    import json

    import numpy as np

    path = os.path.join(TEXTURES_DIR, f"{tex_id}.texture.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("schema") != "ae.texture/1":
        raise ValueError(f"{path}: schema must be ae.texture/1")
    w, h = data["size"]
    rows, palette = data["rows"], data["palette"]
    if len(rows) != h or any(len(r) != w for r in rows):
        raise ValueError(f"{path}: rows must be {h} strings of {w} chars")
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch not in palette:
                raise ValueError(f"{path}: char {ch!r} not in palette")
            arr[y, x] = palette[ch]
    _tex_cache[tex_id] = arr
    return arr


def push_textures(r, prims) -> None:
    """Register a set's textures on a software renderer (GL: flat)."""
    if not hasattr(r, "set_texture"):
        return
    for p in prims:
        tid = p.get("texture")
        if tid:
            r.set_texture(tid, load_texture(tid))


def dynamic_faces(mesh) -> list:
    """Mesh faces -> renderer add_dynamic faces (carries texture UV
    payloads past the hosts' tuple conversions, P11 step 9)."""
    out = []
    for f in mesh.faces:
        row = (f[0], f[1], f[2], f[3], None, f[4])
        if len(f) > 5:
            row = row + (0.0, f[5])
        out.append(row)
    return out

_presets_cache: dict = {}


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def presets() -> dict:
    """The ae.lighting3d/1 preset library (Phase 11 step 1)."""
    if "lib" not in _presets_cache:
        _presets_cache["lib"] = load_preset_library(PRESETS_DIR)
    return _presets_cache["lib"]


def _scene(set_id: str):
    if set_id not in _cache:
        _cache[set_id] = load_set3d(os.path.join(SETS_DIR, f"{set_id}.set3d.json"))
    return _cache[set_id]


def set_lighting(set_id: str, blend=None) -> dict:
    """Resolved {key, fog, sky} for a set; ``blend`` = (spec_a, spec_b, k)."""
    scene = _scene(set_id)
    lib = presets()
    if blend is not None:
        return blend_lighting(blend[0], blend[1], blend[2], lib)
    resolved = resolve_lighting(scene.data.get("lighting"), lib)
    for field, block in (("key", scene.data.get("light")), ("fog", scene.data.get("fog"))):
        for k, v in (block or {}).items():
            resolved[field][k] = v
    return resolved

# Reusable sub-sets (prop_ref targets), as data.  m5/flags is the crest
# pole pair from cutscenes/m5martial3d._flags, centres relative to `at`.
PROP_LIBRARY: dict[str, list] = {
    "m5/flags": [
        {"type": "box", "size": [0.05, 2.6, 0.05], "center": [0, 1.3, 0], "color": [160, 148, 112]},
        {"type": "box", "size": [0.08, 0.08, 0.08], "center": [0, 2.64, 0], "color": [230, 200, 120]},
        {"type": "box", "size": [0.75, 0.42, 0.03], "center": [0.4, 2.3, 0], "color": [24, 34, 58]},
        {"type": "box", "size": [0.75, 0.42, 0.03], "center": [0.4, 1.88, 0], "color": [150, 30, 32]},
    ],
}

_cache: dict = {}


def use_legacy() -> bool:
    return os.environ.get("ACA_SET_SRC", "").strip().lower() == "legacy"


def flicker_at(seed: float, t_ms: float) -> float:
    """Deterministic bulb flicker 0.15..1.0 (P11 step 10): smooth mains
    wobble plus seeded dropouts. Closed-form - goldens stay exact."""
    import math

    t = t_ms / 1000.0
    s = float(seed)
    v = 0.86 + 0.14 * math.sin(t * 23.0 + s * 3.1) * math.sin(t * 7.3 + s * 1.7)
    cell = int(t * 9.0 + s * 13.0)
    h = (math.sin(cell * 12.9898 + s * 78.233) * 43758.5453) % 1.0
    if h < 0.10:
        v *= 0.3
    return max(0.15, min(1.0, v))


def _apply_flicker(prims, t_ms: float) -> None:
    for p in prims:
        seed = p.get("flicker")
        if seed is None:
            continue
        f = flicker_at(seed, t_ms)
        if p["kind"] in ("point_light", "spot_light"):
            p["intensity"] = float(p.get("intensity", 1.0)) * f
        elif p["kind"] == "box" and p.get("emissive"):
            k = 0.3 + 0.7 * f
            p["color"] = [max(0, min(255, int(c * k))) for c in p["color"]]


def set_prims(set_id: str, params=None) -> list:
    """Ordered renderer primitives for ``set_id`` (e.g. ``m5.vasile_office``).

    ``params`` may carry ``t`` (seconds): set fields written as timeline
    expressions (``sin(t*2)``...) animate, and ``flicker``-seeded bulbs
    drive their emissive part + attached light (P11 step 10).
    """
    prims = build(_scene(set_id), params=params, library=PROP_LIBRARY, presets=presets())
    if params and _is_num(params.get("t")):
        _apply_flicker(prims, float(params["t"]) * 1000.0)
    _annotate_ao(prims)
    return prims


def _annotate_ao(prims) -> None:
    """Phase 11 step 4 (baked AO): tag prims with the set floor height
    and wall footprints; ``_mesh`` darkens faces near the ground line
    and floor faces near walls. Baked into face colours - zero
    per-frame cost, cached with the mesh by construction."""
    floors = [p["y"] for p in prims if p["kind"] == "quad_xz"]
    fy = min(floors) if floors else 0.0
    walls = []
    for p in prims:
        if p["kind"] != "box":
            continue
        w, h, d = p["size"]
        cx, cy, cz = p["center"]
        p["ao_base"] = cy - h / 2
        if abs(p["ao_base"] - fy) <= 0.08 and h >= 0.8:
            walls.append((cx - w / 2, cz - d / 2, cx + w / 2, cz + d / 2))
    for p in prims:
        if p["kind"] == "quad_xz":
            p["ao_walls"] = walls
            p["ao_base"] = p["y"]


def _col(v):
    return tuple(v) if isinstance(v, list) else v


def build_mesh(prim):
    """Public mesh builder for hosts that emit prims themselves (M0)."""
    return _mesh(prim)


def _darken(col, f):
    return (max(0, int(col[0] * f)), max(0, int(col[1] * f)), max(0, int(col[2] * f)))


def _apply_ao(mesh, prim):
    """Bake corner darkening into face colours (see _annotate_ao)."""
    if prim.get("emissive") or quality_3d() <= 0:
        return mesh
    base = prim.get("ao_base")
    if base is None:
        return mesh
    walls = prim.get("ao_walls")
    faces = []
    for face in mesh.faces:
        idx, col = face[0], face[1]
        cx = sum(mesh.verts[i][0] for i in idx) / len(idx)
        cy = sum(mesh.verts[i][1] for i in idx) / len(idx)
        cz = sum(mesh.verts[i][2] for i in idx) / len(idx)
        f = 1.0
        h = cy - base
        if prim["kind"] == "box" and h < 0.7:
            f = 0.60 + 0.40 * max(0.0, h) / 0.7
        if walls:
            for (x0, z0, x1, z1) in walls:
                dx = max(x0 - cx, 0.0, cx - x1)
                dz = max(z0 - cz, 0.0, cz - z1)
                dist = (dx * dx + dz * dz) ** 0.5
                if dist < 0.55:
                    f = min(f, 0.70 + 0.30 * dist / 0.55)
        faces.append((idx, _darken(col, f)) + tuple(face[2:]) if f < 1.0 else face)
    mesh.faces = faces
    return mesh


def _apply_texture(mesh, prim):
    """Attach planar world-space UVs + texture id to each face (P11
    step 9). UVs tile every ``tex_scale`` metres on the face's dominant
    plane; quality 0 keeps the flat colour (no payload)."""
    tex_id = prim.get("texture")
    if not tex_id or quality_3d() <= 0:
        return mesh
    scale = float(prim.get("tex_scale", 1.0) or 1.0)
    faces = []
    for face in mesh.faces:
        idx = face[0]
        pts = [mesh.verts[i] for i in idx]
        ux, uy, uz = (pts[1][0] - pts[0][0], pts[1][1] - pts[0][1],
                      pts[1][2] - pts[0][2])
        vx, vy, vz = (pts[2][0] - pts[0][0], pts[2][1] - pts[0][1],
                      pts[2][2] - pts[0][2])
        n = (abs(uy * vz - uz * vy), abs(uz * vx - ux * vz),
             abs(ux * vy - uy * vx))
        axes = (0, 2) if n[1] >= n[0] and n[1] >= n[2] else \
            (2, 1) if n[0] >= n[2] else (0, 1)
        uvs = tuple((p[axes[0]] / scale, p[axes[1]] / scale) for p in pts)
        faces.append(tuple(face) + ((tex_id, uvs),))
    mesh.faces = faces
    return mesh


def _mesh(prim):
    kind = prim["kind"]
    seg = prim.get("seg")
    if seg is not None and prim.get("texture"):
        # textured prims rasterize per face in software (step 9): cap the
        # tessellation so a lit floor stays affordable; shading banding
        # at 0.85 m is the accepted trade (bench3d records the cost).
        seg = max(float(seg), 0.85)
    if kind == "box":
        w, h, d = prim["size"]
        return _apply_texture(_apply_ao(box(w, h, d, _col(prim["color"]), center=tuple(prim["center"]),
                             seg=seg, emissive=bool(prim.get("emissive", False))), prim), prim)
    if kind == "quad_xz":
        x0, z0, x1, z1 = prim["rect"]
        return _apply_texture(_apply_ao(quad_xz(x0, z0, x1, z1, prim["y"], _col(prim["color"]),
                                 seg=seg, emissive=bool(prim.get("emissive", False))), prim), prim)
    raise ValueError(f"no mesh builder for primitive kind {kind!r}")


def _emit(r, prim, add, dec) -> None:
    mesh = _mesh(prim)
    if "bias" in prim:
        dec(r, mesh, prim["bias"])
    else:
        add(r, mesh)


_RENDER_SCALE_3D = {0: 0.6, 1: 0.75, 2: 1.0}


def render_scale_3d() -> float:
    """Internal render scale for set-driven 3D hosts, by quality tier.

    Low-end machines render the 3D buffer smaller and upscale (the hosts
    already present through a smoothscale); tier 2 is the authored size.
    """
    return _RENDER_SCALE_3D.get(quality_3d(), 1.0)


def render_size_3d(base_w: int = 480, base_h: int = 270) -> tuple:
    s = render_scale_3d()
    return (max(160, int(base_w * s) // 2 * 2),
            max(90, int(base_h * s) // 2 * 2))


def quality_3d() -> int:
    """The §6.18 quality setting for Phase 11 features (0 off, 1 low, 2 high)."""
    try:
        from core.user_settings import SETTINGS  # lazy: settings owner
        return int(SETTINGS.quality_3d)
    except Exception:
        return 2


def _light_dict(prim) -> dict:
    from engine3d.core import v_norm
    d = {"pos": tuple(prim["pos"]), "color": _col(prim.get("color", (255, 255, 255))),
         "intensity": float(prim.get("intensity", 1.0)),
         "range": float(prim.get("range", 6.0)),
         "kind": prim["kind"].replace("_light", "")}
    if d["kind"] == "spot":
        d["dir"] = v_norm(tuple(prim["direction"]))
        d["cone"] = float(prim.get("cone", 0.7))
    return d


def emit_lights(r, prims) -> None:
    """Push a set's local lights onto the renderer (quality-gated)."""
    if not hasattr(r, "set_lights"):
        return
    q = quality_3d()
    if q <= 0:
        r.set_lights([])
        return
    lights = [_light_dict(p) for p in prims
              if p["kind"] in ("point_light", "spot_light")]
    r.set_lights(lights, cap=8 if q >= 2 else 4)


def shadow_prims(prims) -> list:
    """Contact-shadow ellipses for boxes resting on the set floor
    (Phase 11 step 3): footprint-sized, wall slabs excluded."""
    floors = [p["y"] for p in prims if p["kind"] == "quad_xz"]
    fy = min(floors) if floors else 0.0
    out = []
    for p in prims:
        if p["kind"] != "box":
            continue
        w, h, d = p["size"]
        cx, cy, cz = p["center"]
        if h < 0.15 or abs((cy - h / 2) - fy) > 0.08:
            continue
        if min(w, d) < 0.22 and max(w, d) > 2.0:
            continue  # a wall, not furniture
        out.append({"pos": (cx, fy + 0.02, cz), "rx": w * 0.62,
                    "rz": d * 0.62, "strength": 0.34})
    return out


def emit_shadows(r, prims) -> None:
    """Quality-gate + emit a set's contact shadows onto the renderer."""
    if not hasattr(r, "add_blob_shadow"):
        return
    r.blob_shadows = quality_3d() >= 1
    if not r.blob_shadows:
        return
    for s in shadow_prims(prims):
        r.add_blob_shadow(s["pos"], s["rx"], s["rz"], s["strength"])


def _ray_aabb(o, d, lo, hi):
    """Slab test: smallest positive t where ray o+d*t enters the box."""
    tmin, tmax = 0.02, float("inf")
    for i in range(3):
        if abs(d[i]) < 1e-9:
            if o[i] < lo[i] or o[i] > hi[i]:
                return None
            continue
        inv = 1.0 / d[i]
        t0, t1 = (lo[i] - o[i]) * inv, (hi[i] - o[i]) * inv
        if t0 > t1:
            t0, t1 = t1, t0
        tmin, tmax = max(tmin, t0), min(tmax, t1)
        if tmax < tmin:
            return None
    return tmin


_BAKE_CACHE: dict = {}


def _bake_fingerprint(pairs, prims, lights):
    # positions quantised to 0.25 m: animated props (step 10 sway/flicker
    # hosts rebuild prims per frame) must not rebake every frame.
    def q3(v):
        return tuple(round(float(x) * 4) / 4 for x in v)

    parts = []
    for p in prims:
        if p["kind"] == "box":
            parts.append(("b", q3(p["center"]), p["size"]))
        elif p["kind"] == "quad_xz":
            parts.append(("q", p["rect"], p["y"]))
    for lp in lights:
        parts.append(("l", q3(lp["pos"]), lp.get("range", 6.0)))
    parts.append(tuple(len(m.faces) for _, m in pairs))
    return hash(repr(parts))


def bake_cast_shadows(pairs, prims) -> None:
    """ADR-023: darken faces occluded from any ``cast_shadows`` light.

    ``pairs`` is a list of (prim, mesh) for the set's box/quad prims;
    occlusion is an exact ray-AABB test against the set's boxes. Results
    are cached on a geometry fingerprint - hosts that rebuild prims every
    frame pay the bake once; both backends consume the baked colours.
    """
    if quality_3d() <= 0:
        return
    lights = [p for p in prims
              if p["kind"] in ("point_light", "spot_light")
              and p.get("cast_shadows")]
    if not lights:
        return
    fp = _bake_fingerprint(pairs, prims, lights)
    cached = _BAKE_CACHE.get(fp)
    if cached is not None and len(cached) == len(pairs):
        for (prim, mesh), factors in zip(pairs, cached):
            if len(factors) == len(mesh.faces):
                mesh.faces = [(f[0], _darken(f[1], fac)) + tuple(f[2:])
                              if fac < 1.0 else f
                              for f, fac in zip(mesh.faces, factors)]
        return
    all_factors = []
    boxes = []
    for p in prims:
        if p["kind"] == "box":
            cx, cy, cz = p["center"]
            w, h, d = p["size"]
            boxes.append((p, (cx - w / 2, cy - h / 2, cz - d / 2),
                          (cx + w / 2, cy + h / 2, cz + d / 2)))
    for prim, mesh in pairs:
        if prim.get("emissive"):
            all_factors.append([1.0] * len(mesh.faces))
            continue
        faces = []
        factors = []
        for face in mesh.faces:
            idx, col = face[0], face[1]
            pts = [mesh.verts[i] for i in idx]
            c = tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))
            ux, uy, uz = (pts[1][0] - pts[0][0], pts[1][1] - pts[0][1],
                          pts[1][2] - pts[0][2])
            vx, vy, vz = (pts[2][0] - pts[0][0], pts[2][1] - pts[0][1],
                          pts[2][2] - pts[0][2])
            n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
            nl = (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5 or 1.0
            o = tuple(c[i] + n[i] / nl * 0.03 for i in range(3))
            f = 1.0
            for lp in lights:
                d = tuple(lp["pos"][i] - o[i] for i in range(3))
                dist = (d[0] ** 2 + d[1] ** 2 + d[2] ** 2) ** 0.5
                if dist < 1e-6 or dist > float(lp.get("range", 6.0)) * 1.6:
                    continue
                d = tuple(v / dist for v in d)
                for bp, lo, hi in boxes:
                    if bp is prim:
                        continue
                    t = _ray_aabb(o, d, lo, hi)
                    if t is not None and t < dist - 0.05:
                        f = min(f, 0.45)
                        break
                if f <= 0.45:
                    break
            faces.append((idx, _darken(col, f)) + tuple(face[2:]) if f < 1.0 else face)
            factors.append(f)
        mesh.faces = faces
        all_factors.append(factors)
    if len(_BAKE_CACHE) > 8:
        _BAKE_CACHE.clear()
    _BAKE_CACHE[fp] = all_factors


_HUM3D: dict = {}
_LOOK_STATE: dict = {}


def _is_speaking(prim, t) -> bool:
    """Mouth drive from dialogue data (P11 step 8): the current shot's
    speaker, typed at the house rate of 50 ms/char (m5shadow3d)."""
    if prim.get("speaking") is False:
        return False
    shot = None
    try:
        from core.cutscene_registry import current_shot  # lazy: registry
        shot = current_shot()
    except Exception:
        shot = None
    if not shot or not shot.get("text"):
        return bool(prim.get("speaking"))
    sp = str(shot.get("speaker", "")).strip().lower()
    if not sp or sp == "narrator":
        return False
    names = {str(prim["cast"]).lower()}
    from cutscenes.cast3d import CAST3D_ALIASES  # lazy: cast owner
    for a, b in CAST3D_ALIASES.items():
        if names & {a, b}:
            names |= {a, b}
    if sp not in names:
        return False
    return t <= len(str(shot["text"])) * 50 + 500


def humanoid_meshes(prim, t: int = 0):
    """Pose a set's humanoid prim for this frame -> (verts, faces).

    Expression comes from the prim (set data); the mouth flaps while the
    shot's dialogue names this cast member; ``look_at`` solves clamped
    head angles with exponential smoothing across frames.
    """
    import math
    import zlib

    from cutscenes.cast3d import humanoid3d  # lazy: cast owner
    from engine3d.rig import POSES, mouth_flap, solve_look  # lazy: rig

    cast = prim["cast"]
    hum = _HUM3D.get(cast)
    if hum is None:
        hum = _HUM3D[cast] = humanoid3d(cast)
    mouth = mouth_flap(int(t), zlib.crc32(cast.encode("utf-8")) % 997) \
        if _is_speaking(prim, t) else 0.0
    hum.set_expression(prim.get("expression", "neutral"), mouth)
    pdata = prim.get("pose") or "stand"
    pose = dict(POSES.get(pdata, {}) if isinstance(pdata, str) else pdata)
    pos = tuple(prim.get("pos", (0, 0, 0)))
    yaw = float(prim.get("yaw", 0) or 0)
    target = prim.get("look_at")
    if target:
        _places, joints, _org = hum.pose_world(pose, pos, yaw)
        want_y, want_p = solve_look(joints["head"], tuple(target), yaw)
        key = (cast, prim.get("as"), pos)
        prev = _LOOK_STATE.get(key)
        if prev is None or t < prev[2] or t - prev[2] > 1000:
            cur_y, cur_p = want_y, want_p
        else:
            a = 1.0 - math.exp(-(t - prev[2]) / 160.0)
            cur_y = prev[0] + (want_y - prev[0]) * a
            cur_p = prev[1] + (want_p - prev[1]) * a
        _LOOK_STATE[key] = (cur_y, cur_p, t)
        pose["head_y"], pose["head_p"] = cur_y, cur_p
    verts, faces, _joints = hum.build(pose, pos, yaw)
    return verts, faces


def apply_set(r, prims, *, add, dec, spr, decal_add, fx, t: int = 0) -> None:
    """Walk ``prims`` onto renderer ``r`` via the host's legacy helpers."""
    emit_lights(r, prims)
    emit_shadows(r, prims)
    push_textures(r, prims)
    _pairs = [(p, _mesh(p)) for p in prims if p["kind"] in ("box", "quad_xz")]
    bake_cast_shadows(_pairs, prims)
    _built = {id(p): m for p, m in _pairs}
    for prim in prims:
        kind = prim["kind"]
        if kind in ("point_light", "spot_light", "weather", "emitter", "fog_layer"):
            continue  # lights handled above; weather via cutscenes.weather3d.attach
        if kind == "puddle":
            # faked reflection (P11 step 6): dark sheen quad + a glint
            # sprite under every local light - no reflection pass.
            if quality_3d() > 0:
                x0, z0, x1, z1 = prim["rect"]
                add(r, quad_xz(x0, z0, x1, z1, prim.get("y", 0.011), (24, 28, 36), seg=0.8))
                refl = float(prim.get("reflect", 0.5))
                for lp in prims:
                    if lp["kind"] in ("point_light", "spot_light"):
                        spr(r, (lp["pos"][0], prim.get("y", 0.011) + 0.02, lp["pos"][2]),
                            fx.glow(_col(lp.get("color", (255, 255, 255))), 0.7,
                                    intensity=0.4 * refl))
            continue
        if kind == "fog":
            r.fog, r.fog_start, r.fog_end = _col(prim["color"]), prim["start"], prim["end"]
        elif kind == "light":
            r.light = Light(direction=tuple(prim["direction"]), ambient=prim["ambient"],
                            diffuse=prim["diffuse"], tint=tuple(prim["tint"]))
        elif kind in ("box", "quad_xz"):
            mesh = _built[id(prim)]
            if "bias" in prim:
                dec(r, mesh, prim["bias"])
            else:
                add(r, mesh)
        elif kind == "mesh":
            mesh = mesh_for_prim(prim)
            if "bias" in prim:
                dec(r, mesh, prim["bias"])
            else:
                add(r, mesh)
            if quality_3d() >= 1 and hasattr(r, "add_blob_shadow"):
                p0 = prim.get("pos", (0, 0, 0))
                r.add_blob_shadow((p0[0], p0[1] + 0.02, p0[2]), 0.36, 0.36, 0.38)
        elif kind == "humanoid":
            verts, faces = humanoid_meshes(prim, t)
            if hasattr(r, "add_dynamic"):
                r.add_dynamic(verts, faces)
            else:  # host add() wants mesh-shaped faces (5-tuples)
                class _M:  # minimal mesh shim
                    pass
                m = _M()
                m.verts = verts
                m.faces = [(f[0], f[1], f[2], f[3], f[5]) for f in faces]
                add(r, m)
            if quality_3d() >= 1 and hasattr(r, "add_blob_shadow"):
                p0 = prim.get("pos", (0, 0, 0))
                r.add_blob_shadow((p0[0], p0[1] + 0.02, p0[2]), 0.34, 0.3, 0.4)
        elif kind == "decal":
            ok = decal_add(r, prim["asset"], prim.get("variant", 0), tuple(prim["center"]),
                           tuple(prim["size"]), facing=prim.get("facing", "-z"),
                           bias=prim.get("bias", 0.8), emissive=prim.get("emissive", False))
            if not ok:
                for sub in prim.get("fallback", []):
                    _emit(r, sub, add, dec)
        elif kind == "sprite3d":
            params = {k: _col(v) for k, v in (prim.get("params") or {}).items()}
            if "color" not in params and "color" in prim:
                params["color"] = _col(prim["color"])
            if "color" in params:            # host fx constructors spell it `col`
                params["col"] = params.pop("color")
            fn = getattr(fx, prim["asset"])(**params)
            spr(r, tuple(prim["pos"]), fn)
        else:  # pragma: no cover - the validator keeps kinds closed
            raise ValueError(f"unhandled primitive kind {kind!r}")
