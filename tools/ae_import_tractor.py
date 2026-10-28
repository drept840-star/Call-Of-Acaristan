#!/usr/bin/env python3
"""AE IMPORT TRACTOR - the Mission 7 tractor asset (assets/3D/TractorM7.glb).

    python tools/ae_import_tractor.py [--cell 0.004] [--scale 0.955]

Reuses the GLB walker from tools/ae_import_k93d.py. The GLB has no textures,
only flat base colours (linear), so each face takes its material's sRGB colour
plus the same deterministic per-face dither the K93D uses.

Output: src/game/content/meshes/tractor_m7.mesh.json, in the tractor frame the
M7 farm builder expects: +x forward (the GLB nose is -z), +y up, wheels on
y = 0, the seat at x -0.65 / top 1.51 like the old procedural tractor.
Faces carry a third field: 1 = headlight lens, 2 = rear lamp (emissive when
the tractor is lit).
"""
import argparse
import json
import os

import ae_import_k93d as K

ROOT = K.ROOT
SRC = os.path.join(ROOT, "assets", "3D", "TractorM7.glb")
OUT = os.path.join(ROOT, "src", "game", "content", "meshes", "tractor_m7.mesh.json")

SEAT_X = -0.65          # seat centre along local x (old tractor)
SEAT_GLB_Z = 0.99       # seat cushion centre in the GLB (its node carries no transform)
LAMP = {5: 1, 9: 2}     # material id -> face group
GRAIN = {0: 0.08, 1: 0.08, 2: 0.08, 7: 0.14, 8: 0.14}


def _srgb(c):
    c = max(0.0, min(1.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", type=float, default=0.004)
    ap.add_argument("--scale", type=float, default=0.955)
    args = ap.parse_args()

    g, binbuf = K._gltf(SRC)
    verts, tris0, _ = K._scan(g, binbuf)
    cols = []
    for m in g.get("materials", []):
        f = m.get("pbrMetallicRoughness", {}).get("baseColorFactor", [0.5, 0.5, 0.5, 1])
        cols.append(tuple(int(round(_srgb(c) * 255)) for c in f[:3]))

    sc = args.scale
    dx = SEAT_X + SEAT_GLB_Z * sc
    y0 = min(v[1] for v in verts)
    # GLB nose is -z: local x = -z, local z = x (a proper rotation, no mirror).
    verts = [(-p[2] * sc + dx, (p[1] - y0) * sc, p[0] * sc) for p in verts]

    tris = []
    for idx, mat, _group, uv in tris0:
        col = cols[mat] if mat < len(cols) else (110, 110, 110)
        a, b, c = verts[idx[0]], verts[idx[1]], verts[idx[2]]
        h = (round((a[0] + b[0] + c[0]) * 5000) * 374761393
             + round((a[1] + b[1] + c[1]) * 5000) * 668265263
             + round((a[2] + b[2] + c[2]) * 5000) * 2147483647) & 0xFFFFFFFF
        h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
        h ^= h >> 16
        k = 0.95 + 0.10 * ((h & 0xFFFF) / 65535.0)
        k *= 1.0 + GRAIN.get(mat, 0.05) * ((((h >> 16) & 0xFFFF) / 65535.0) * 2 - 1)
        col = tuple(min(255, max(0, int(v * k))) for v in col)
        tris.append((idx, mat, LAMP.get(mat, 0), uv, col))

    out_v, out_f = K._cluster(verts, tris, args.cell)
    xs = [v[0] for v in out_v]
    zs = [v[2] for v in out_v]
    data = {
        "schema": "ae.mesh/1",
        "id": "tractor_m7",
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
    print("AE IMPORT TRACTOR: %d raw tris -> %d faces / %d verts  (cell %.4f)"
          % (len(tris0), len(out_f), len(out_v), args.cell))
    print("  bounds x/z", data["meta"]["bounds_xz"],
          " height", round(max(v[1] for v in out_v), 3))
    print("  ->", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
