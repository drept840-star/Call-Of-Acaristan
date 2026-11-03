#!/usr/bin/env python3
"""AE IMPORT CAR - the Mission 2 civilian car (assets/3D/low-poly-car_green.glb).

    python tools/ae_import_car.py [--cell 0.01] [--scale 0.68]

Reuses the GLB walker from tools/ae_import_k93d.py, with the truck import's
sRGB colours and per-face dither. The GLB is untextured (nine flat materials).

Output: src/game/content/meshes/car_m2.mesh.json: +x forward, +y up, wheels on
y = 0, centred on x and z. At the default scale the car is about 2.95 long,
matching the 118 px vehicle rects of the M2 highway. Faces carry a third
field: 1 = headlight, 2 = tail lamp (both emissive), 3 = body paint, which
missions/m2/draw3d.py recolours per car.
"""
import argparse
import json
import os

import ae_import_k93d as K

ROOT = K.ROOT
SRC = os.path.join(ROOT, "assets", "3D", "low-poly-car_green.glb")
OUT = os.path.join(ROOT, "src", "game", "content", "meshes", "car_m2.mesh.json")

GROUP = {0: 3, 4: 1, 6: 2}    # material id -> face group
HEADLIGHT = 4


def _srgb(c):
    c = max(0.0, min(1.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", type=float, default=0.01)
    ap.add_argument("--scale", type=float, default=0.68)
    args = ap.parse_args()

    g, binbuf = K._gltf(SRC)
    verts, tris0, _ = K._scan(g, binbuf)
    cols = []
    for m in g.get("materials", []):
        f = m.get("pbrMetallicRoughness", {}).get("baseColorFactor", [0.5, 0.5, 0.5, 1])
        cols.append(tuple(int(round(_srgb(c) * 255)) for c in f[:3]))

    sc = args.scale
    y0 = min(v[1] for v in verts)
    cx = (min(v[0] for v in verts) + max(v[0] for v in verts)) / 2
    cz = (min(v[2] for v in verts) + max(v[2] for v in verts)) / 2
    hx = [verts[i][0] for idx, mat, _g, _uv in tris0 if mat == HEADLIGHT for i in idx]
    flip = -1 if hx and sum(hx) / len(hx) < cx else 1
    verts = [((p[0] - cx) * sc * flip, (p[1] - y0) * sc, (p[2] - cz) * sc * flip)
             for p in verts]

    tris = []
    for idx, mat, _group, uv in tris0:
        col = cols[mat]
        a, b, c = verts[idx[0]], verts[idx[1]], verts[idx[2]]
        h = (round((a[0] + b[0] + c[0]) * 5000) * 374761393
             + round((a[1] + b[1] + c[1]) * 5000) * 668265263
             + round((a[2] + b[2] + c[2]) * 5000) * 2147483647) & 0xFFFFFFFF
        h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
        h ^= h >> 16
        k = 0.95 + 0.10 * ((h & 0xFFFF) / 65535.0)
        k *= 1.0 + 0.05 * ((((h >> 16) & 0xFFFF) / 65535.0) * 2 - 1)
        col = tuple(min(255, max(0, int(v * k))) for v in col)
        tris.append((idx, mat, GROUP.get(mat, 0), uv, col))

    out_v, out_f = K._cluster(verts, tris, args.cell)
    xs = [v[0] for v in out_v]
    zs = [v[2] for v in out_v]
    data = {
        "schema": "ae.mesh/1",
        "id": "car_m2",
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
    print("AE IMPORT CAR: %d raw tris -> %d faces / %d verts  (cell %.4f, flip %d)"
          % (len(tris0), len(out_f), len(out_v), args.cell, flip))
    print("  bounds x/z", data["meta"]["bounds_xz"],
          " height", round(max(v[1] for v in out_v), 3))
    for grp, name in ((1, "headlights"), (2, "tail lamps"), (3, "paint")):
        ps = [out_v[i] for f in out_f if f[2] == grp for i in f[0]]
        if ps:
            print("  %s x %.2f y %.2f |z| %.2f" % (name, sum(p[0] for p in ps) / len(ps),
                  sum(p[1] for p in ps) / len(ps), sum(abs(p[2]) for p in ps) / len(ps)))
    print("  ->", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
