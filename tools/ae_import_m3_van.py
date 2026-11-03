#!/usr/bin/env python3
"""AE IMPORT M3 VAN - Volkov's armoured van (assets/3D/M3van.glb).

    python tools/ae_import_m3_van.py [--cell 0.2]

Reuses the GLB walker from tools/ae_import_krap_van.py (and k93d).
Output: src/game/content/meshes/m3_van.mesh.json (ae.mesh/1), in metres.

Frame: +x = nose (the glass end), +y = up, tyres on y = 0, centred on x and
z. The source long axis is glTF z; it is rotated onto x with a proper
rotation (det +1), so no winding flip. The mesh is not scaled to the map:
missions/m3/wings3d.py fits it to the kill-order footprint, as M1 does for
krap_van.

Faces are [indices, rgb, group]; group 0 for every face.
"""
import argparse
import json
import os

import ae_import_k93d as K
import ae_import_krap_van as KV

ROOT = K.ROOT
SRC = os.path.join(ROOT, "assets", "3D", "M3van.glb")
OUT = os.path.join(ROOT, "src", "game", "content", "meshes", "m3_van.mesh.json")


def _srgb(c):
    c = max(0.0, min(1.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _dither(a, b, c):
    h = (round((a[0] + b[0] + c[0]) * 5000) * 374761393
         + round((a[1] + b[1] + c[1]) * 5000) * 668265263
         + round((a[2] + b[2] + c[2]) * 5000) * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    k = 0.95 + 0.10 * ((h & 0xFFFF) / 65535.0)
    return k * (1.0 + 0.05 * ((((h >> 16) & 0xFFFF) / 65535.0) * 2 - 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", type=float, default=0.2)
    args = ap.parse_args()

    g, binbuf = K._gltf(SRC)
    cols = []
    for m in g.get("materials", []):
        f = m.get("pbrMetallicRoughness", {}).get("baseColorFactor", [0.5, 0.5, 0.5, 1])
        cols.append(tuple(int(round(_srgb(c) * 255)) for c in f[:3]))

    prims = KV._walk(g, binbuf)
    allv = [p for pv, _i, _m, _w, _n in prims for p in pv]
    cx = (min(v[0] for v in allv) + max(v[0] for v in allv)) / 2
    cz = (min(v[2] for v in allv) + max(v[2] for v in allv)) / 2
    y0 = min(v[1] for v in allv)
    glass = [p for pv, _i, _m, _w, n in prims
             if (g["nodes"][n].get("name") or "").endswith("glass") for p in pv]
    gz = sum(p[2] for p in glass) / len(glass) if glass else cz
    s = -1 if gz > cz else 1          # puts the glass (nose) end on +x

    def to_m(p):
        return (-s * (p[2] - cz), p[1] - y0, s * (p[0] - cx))

    flat, tris, base = [], [], 0
    for pv, idx, mat, _wheel, _n in prims:
        vs = [to_m(p) for p in pv]
        col = cols[mat] if mat < len(cols) else (128, 128, 128)
        for t in range(0, len(idx) - 2, 3):
            a, b, c = idx[t], idx[t + 1], idx[t + 2]
            k = _dither(vs[a], vs[b], vs[c])
            shade = tuple(min(255, max(0, int(v * k))) for v in col)
            tris.append(((a + base, b + base, c + base), mat, 0, None, shade))
        flat.extend(vs)
        base += len(vs)

    out_v, out_f = K._cluster(flat, tris, args.cell)
    xs = [v[0] for v in out_v]
    zs = [v[2] for v in out_v]
    data = {
        "schema": "ae.mesh/1",
        "id": "m3_van",
        "verts": [[round(c, 4) for c in v] for v in out_v],
        "faces": [[f[0], f[1], f[2]] for f in out_f],
        "tris": len(out_f),
        "source": os.path.basename(SRC),
        "meta": {
            "unit": "metre",
            "cell_m": args.cell,
            "length_x": round(max(xs) - min(xs), 3),
            "width_z": round(max(zs) - min(zs), 3),
            "height_y": round(max(v[1] for v in out_v), 3),
            "raw_tris": len(tris),
        },
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    print("AE IMPORT M3 VAN: %d raw tris -> %d faces / %d verts" % (len(tris), len(out_f), len(out_v)))
    print("  length %.2f m  width %.2f m  height %.2f m"
          % (data["meta"]["length_x"], data["meta"]["width_z"], data["meta"]["height_y"]))
    print("  ->", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
