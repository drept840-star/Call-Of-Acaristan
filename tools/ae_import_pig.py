#!/usr/bin/env python3
"""AE IMPORT PIG - the low-poly pig (assets/3D/low_poly_pig.glb).

    python tools/ae_import_pig.py [--cell 0.01] [--scale 0.25]

Reuses the GLB walker from tools/ae_import_k93d.py, like the truck import.
The source is in arbitrary units with its long axis on x and up on +y; it is
centred on x and z, set on y = 0, and scaled to metres with --scale.

Output: src/game/content/meshes/pig.mesh.json
"""
import argparse
import json
import os

import ae_import_k93d as K

ROOT = K.ROOT
SRC = os.path.join(ROOT, "assets", "3D", "low_poly_pig.glb")
OUT = os.path.join(ROOT, "src", "game", "content", "meshes", "pig.mesh.json")
GREY = (128, 128, 128)


def _srgb(c):
    c = max(0.0, min(1.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", type=float, default=0.01)
    ap.add_argument("--scale", type=float, default=0.25)
    args = ap.parse_args()

    g, binbuf = K._gltf(SRC)
    verts, tris0, _ = K._scan(g, binbuf)
    cols = []
    for m in g.get("materials", []):
        f = m.get("pbrMetallicRoughness", {}).get("baseColorFactor")
        if f is None:
            cols.append(GREY)
            continue
        cols.append(tuple(int(round(_srgb(c) * 255)) for c in f[:3]))

    sc = args.scale
    y0 = min(v[1] for v in verts)
    cx = (min(v[0] for v in verts) + max(v[0] for v in verts)) / 2
    cz = (min(v[2] for v in verts) + max(v[2] for v in verts)) / 2
    verts = [((p[0] - cx) * sc, (p[1] - y0) * sc, (p[2] - cz) * sc) for p in verts]

    tris = []
    for idx, mat, _group, _uv in tris0:
        col = cols[mat] if mat < len(cols) else GREY
        tris.append((idx, mat, 0, None, col))

    out_v, out_f = K._cluster(verts, tris, args.cell)
    xs = [v[0] for v in out_v]
    zs = [v[2] for v in out_v]
    data = {
        "schema": "ae.mesh/1",
        "id": "pig",
        "verts": [[round(c, 4) for c in v] for v in out_v],
        "faces": [[f[0], f[1], f[2]] for f in out_f],
        "tris": len(out_f),
        "source": os.path.basename(SRC),
        "meta": {
            "scale": sc,
            "cell_m": args.cell,
            "bounds_xz": [round(min(xs), 3), round(max(xs), 3),
                          round(min(zs), 3), round(max(zs), 3)],
            "raw_tris": len(tris0),
        },
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    print("AE IMPORT PIG: %d raw tris -> %d faces / %d verts  (cell %.4f)"
          % (len(tris0), len(out_f), len(out_v), args.cell))
    print("  bounds x/z", data["meta"]["bounds_xz"],
          " height", round(max(v[1] for v in out_v), 3))
    print("  ->", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
