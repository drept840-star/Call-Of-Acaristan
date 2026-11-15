#!/usr/bin/env python3
"""AE IMPORT FOOTBALL - ending-credits football & goalpost GLB assets.

    python tools/ae_import_football.py
    python tools/ae_import_football.py --check

Reads:
    assets/3D/low_poly_football.glb   -> src/game/content/meshes/football.mesh.json
    assets/3D/low_poly_goal_post.glb  -> src/game/content/meshes/goal_post.mesh.json

Both assets stay well within ADR-024's 1500-tri budget without clustering, so
panel seams and net cords remain crisp. Face winding is aligned to the GLB's
own transformed normals for engine3d's left-handed cross product.
"""
import argparse
import json
import math
import os
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import ae_import_k93d as K  # noqa: E402

ROOT = K.ROOT
ASSETS_3D = os.path.join(ROOT, "assets", "3D")
MESHES_DIR = os.path.join(ROOT, "src", "game", "content", "meshes")

BALL_DIAMETER_M = 0.29   # ~1.3x real size-5 for clear readability in 3D credits
GOAL_SCALE = 0.85        # 4.22 m wide x 1.94 m high; proportional to ~1.7 m box rigs


def _srgb(c):
    c = max(0.0, min(1.0, float(c)))
    return c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055


def _xf_vec(m, v):
    x, y, z = v
    return (
        m[0] * x + m[4] * y + m[8] * z,
        m[1] * x + m[5] * y + m[9] * z,
        m[2] * x + m[6] * y + m[10] * z,
    )


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _tone(rgb, grain_key):
    # Lift near-black panels slightly above INK and tone bright whites gently
    # below 225 so directional shading models every facet cleanly.
    r, g, b = rgb
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    if lum > 224.0:
        s = 224.0 / lum
        r, g, b = r * s, g * s, b * s
    elif lum < 36.0:
        add = 34.0 - lum
        r, g, b = min(255.0, r + add), min(255.0, g + add), min(255.0, b + add)
    h = (grain_key[0] * 374761393 + grain_key[1] * 668265263 + grain_key[2] * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    k = 0.965 + 0.07 * ((h & 0xFFFF) / 65535.0)
    return [
        max(0, min(255, int(round(r * k)))),
        max(0, min(255, int(round(g * k)))),
        max(0, min(255, int(round(b * k)))),
    ]


def _material_colours(g):
    cols = []
    for mat in g.get("materials", []):
        pbr = mat.get("pbrMetallicRoughness", {})
        f = pbr.get("baseColorFactor", [0.8, 0.8, 0.8, 1.0])
        cols.append(tuple(int(round(_srgb(c) * 255.0)) for c in f[:3]))
    return cols


def _load_triangles(glb_path, outward_from_origin=False):
    g, binbuf = K._gltf(glb_path)
    mat_cols = _material_colours(g)
    verts = []
    faces = []

    def walk(ni, m):
        nd = g["nodes"][ni]
        if "matrix" in nd:
            m = K._mul(m, nd["matrix"])
        elif any(k in nd for k in ("translation", "rotation", "scale")):
            m = K._mul(m, K._trs(nd))
        if "mesh" in nd:
            for pr in g["meshes"][nd["mesh"]].get("primitives", []):
                mode = pr.get("mode", 4)
                if mode not in (4, 5):
                    continue
                attrs = pr.get("attributes", {})
                if "POSITION" not in attrs:
                    continue
                raw_pos = K._acc(g, binbuf, attrs["POSITION"])
                raw_nrm = K._acc(g, binbuf, attrs["NORMAL"]) if "NORMAL" in attrs else None
                base = len(verts)
                verts.extend(K._xf(m, p) for p in raw_pos)
                wn = [_xf_vec(m, n) for n in raw_nrm] if raw_nrm is not None else None

                if "indices" in pr:
                    idx = [x[0] for x in K._acc(g, binbuf, pr["indices"])]
                else:
                    idx = list(range(len(raw_pos)))

                tris = []
                if mode == 4:
                    for k in range(0, len(idx) - 2, 3):
                        tris.append((idx[k], idx[k + 1], idx[k + 2]))
                else:
                    for k in range(len(idx) - 2):
                        a, b, c = idx[k], idx[k + 1], idx[k + 2]
                        tris.append((a, c, b) if (k % 2) else (a, b, c))

                mat_id = pr.get("material", 0)
                base_col = mat_cols[mat_id] if 0 <= mat_id < len(mat_cols) else (200, 200, 200)
                for a, b, c in tris:
                    if a == b or b == c or a == c:
                        continue
                    va, vb, vc = verts[base + a], verts[base + b], verts[base + c]
                    gn = _cross(_sub(vb, va), _sub(vc, va))
                    if _dot(gn, gn) < 1e-14:
                        continue
                    if wn is not None:
                        na, nb, nc = wn[a], wn[b], wn[c]
                        avg_n = (na[0] + nb[0] + nc[0], na[1] + nb[1] + nc[1], na[2] + nb[2] + nc[2])
                        if _dot(gn, avg_n) < 0.0:
                            b, c = c, b
                    elif outward_from_origin:
                        cen = ((va[0] + vb[0] + vc[0]) / 3.0,
                               (va[1] + vb[1] + vc[1]) / 3.0,
                               (va[2] + vb[2] + vc[2]) / 3.0)
                        if _dot(gn, cen) < 0.0:
                            b, c = c, b

                    gk = (
                        round((va[0] + vb[0] + vc[0]) * 1600),
                        round((va[1] + vb[1] + vc[1]) * 1600),
                        round((va[2] + vb[2] + vc[2]) * 1600),
                    )
                    faces.append(([base + a, base + b, base + c], _tone(base_col, gk)))

        for ch in nd.get("children", ()):
            walk(ch, m)

    scene_idx = g.get("scene", 0)
    roots = g.get("scenes", [{"nodes": []}])[scene_idx].get("nodes", [])
    for ni in roots:
        walk(ni, K.I4)

    used = sorted({i for idx, _ in faces for i in idx})
    remap = {old: new for new, old in enumerate(used)}
    out_v = [verts[i] for i in used]
    out_f = [[[remap[i] for i in idx], col] for idx, col in faces]
    return out_v, out_f


def build_football():
    src = os.path.join(ASSETS_3D, "low_poly_football.glb")
    verts, faces = _load_triangles(src, outward_from_origin=True)
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    cx = 0.5 * (min(xs) + max(xs))
    cy = 0.5 * (min(ys) + max(ys))
    cz = 0.5 * (min(zs) + max(zs))
    raw_d = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    scale = BALL_DIAMETER_M / max(1e-5, raw_d)
    out_v = [
        [round((x - cx) * scale, 5), round((y - cy) * scale, 5), round((z - cz) * scale, 5)]
        for x, y, z in verts
    ]
    radius = round(0.5 * BALL_DIAMETER_M, 5)
    assert len(faces) <= 1500
    assert all(math.isfinite(c) for v in out_v for c in v)
    return {
        "schema": "ae.mesh/1",
        "id": "football",
        "verts": out_v,
        "faces": faces,
        "tris": len(faces),
        "source": "low_poly_football.glb",
        "meta": {
            "radius": radius,
            "diameter_m": BALL_DIAMETER_M,
            "scale": round(scale, 6),
            "raw_tris": len(faces),
        },
    }


def build_goal_post():
    src = os.path.join(ASSETS_3D, "low_poly_goal_post.glb")
    verts, faces = _load_triangles(src, outward_from_origin=False)
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    cx = 0.5 * (min(xs) + max(xs))
    y0 = min(ys)
    # Keep z=0 at the front post centerline; negative z extends back into the net.
    out_v = [
        [round((x - cx) * GOAL_SCALE, 5), round((y - y0) * GOAL_SCALE, 5), round(z * GOAL_SCALE, 5)]
        for x, y, z in verts
    ]
    oxs = [v[0] for v in out_v]
    oys = [v[1] for v in out_v]
    ozs = [v[2] for v in out_v]
    assert len(faces) <= 1500
    assert all(math.isfinite(c) for v in out_v for c in v)
    return {
        "schema": "ae.mesh/1",
        "id": "goal_post",
        "verts": out_v,
        "faces": faces,
        "tris": len(faces),
        "source": "low_poly_goal_post.glb",
        "meta": {
            "scale": GOAL_SCALE,
            "bounds_x": [round(min(oxs), 4), round(max(oxs), 4)],
            "bounds_y": [round(min(oys), 4), round(max(oys), 4)],
            "bounds_z": [round(min(ozs), 4), round(max(ozs), 4)],
            "mouth_hw": round(0.5 * (max(oxs) - min(oxs)) - 0.067, 3),
            "mouth_h": round(max(oys) - 0.067, 3),
            "depth": round(abs(min(ozs)), 3),
            "raw_tris": len(faces),
        },
    }


BUILDERS = (
    ("football", build_football),
    ("goal_post", build_goal_post),
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify baked files match the GLBs")
    args = ap.parse_args()

    os.makedirs(MESHES_DIR, exist_ok=True)
    for asset_id, builder in BUILDERS:
        data = builder()
        out_path = os.path.join(MESHES_DIR, f"{asset_id}.mesh.json")
        payload = json.dumps(data, separators=(",", ":")) + "\n"
        if args.check:
            if not os.path.isfile(out_path):
                print(f"AE IMPORT FOOTBALL: MISSING {os.path.relpath(out_path, ROOT)}")
                return 1
            with open(out_path, encoding="utf-8") as fh:
                if fh.read() != payload:
                    print(f"AE IMPORT FOOTBALL: STALE {os.path.relpath(out_path, ROOT)}")
                    return 1
        else:
            with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(payload)
            print(
                f"AE IMPORT FOOTBALL: {asset_id} ({data['tris']} tris, {len(data['verts'])} verts)"
                f" -> {os.path.relpath(out_path, ROOT)}"
            )
    if args.check:
        print("AE IMPORT FOOTBALL: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
