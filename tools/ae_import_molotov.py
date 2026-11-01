#!/usr/bin/env python3
"""AE IMPORT MOLOTOV - the thrown molotov cocktail (assets/3D/low-poly-molotov.glb).

    python tools/ae_import_molotov.py [--scale 0.18] [--cell 0.001]

Reuses the GLB reader of tools/ae_import_k93d.py, so the node matrices are
applied: the label decals, the torn rag and the three flame shells land where
Blender put them instead of piling up at the origin.

Source space: bottle on +y, 4.11 units from the glass base to the flame tip,
so a unit is a decimetre.  At 0.1 the bottle is its real 28 cm; the M1
camera sits 25 m back, which is 8 px for 28 cm, so the default is 0.18 - a
50 cm bottle, half a human, the same exaggeration the 2D bottle drew.

Face colours are the GLB's baseColorFactor gamma-decoded to the sRGB flat
fills the renderer draws (no palette snap: the house texture palette has no
dark green glass, and snapping turned the flame tan).  The flame materials
are tagged group 1 and drawn emissive.

The mesh is centred on the bottle body's mid-height, so a thrown bottle
tumbles about its own centre; ``meta.base`` is how far the glass bottom sits
below the origin.

Output: src/game/content/meshes/molotov.mesh.json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ae_import_k93d as K  # noqa: E402

ROOT = K.ROOT
SRC = os.path.join(ROOT, "assets", "3D", "low-poly-molotov.glb")
OUT = os.path.join(ROOT, "src", "game", "content", "meshes", "molotov.mesh.json")

# Materials that burn: Flame_Outer / Flame_Tip / Flame_Core.
FLAME = {6, 7}


def _srgb(c):
    """glTF baseColorFactor (linear) -> 0-255 sRGB."""
    c = max(0.0, min(1.0, c))
    v = c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055
    return int(round(v * 255))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=0.18,
                    help="source units (dm) -> metres (default 0.18 = a 50 cm bottle, "
                         "1.8x life for readability at the M1 camera; 0.1 = real size)")
    ap.add_argument("--cell", type=float, default=0.001,
                    help="vertex-cluster cell in metres (default 1 mm)")
    args = ap.parse_args()

    g, binbuf = K._gltf(SRC)
    verts, tris0, _focus = K._scan(g, binbuf)
    mats = [m.get("pbrMetallicRoughness", {}).get("baseColorFactor", [0.5, 0.5, 0.5, 1.0])
            for m in g.get("materials", [])]

    # Bottle axis on the origin in x/z: the glass, not the rag, is what spins.
    body = [v for t in tris0 if t[1] == 0 for v in (verts[t[0][0]], verts[t[0][1]], verts[t[0][2]])]
    y_mid = (min(v[1] for v in body) + max(v[1] for v in body)) / 2.0
    sc = args.scale
    verts = [(v[0] * sc, (v[1] - y_mid) * sc, v[2] * sc) for v in verts]

    tris = []
    for idx, mat, _group, _uv in tris0:
        col = tuple(_srgb(c) for c in mats[mat][:3])
        # deterministic per-face grain: flat fills read as one slab otherwise
        a, b, c = verts[idx[0]], verts[idx[1]], verts[idx[2]]
        h = (round((a[0] + b[0] + c[0]) * 5000) * 374761393
             + round((a[1] + b[1] + c[1]) * 5000) * 668265263
             + round((a[2] + b[2] + c[2]) * 5000) * 2147483647) & 0xFFFFFFFF
        h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
        h ^= h >> 16
        k = 0.93 + 0.14 * ((h & 0xFFFF) / 65535.0)
        col = tuple(min(255, max(0, int(v * k))) for v in col)
        tris.append((idx, mat, 1 if mat in FLAME else 0, _uv, col))

    out_v, out_f = K._cluster(verts, tris, args.cell / sc)
    ys = [v[1] for v in out_v]
    body_ys = [v[1] for t in tris0 if t[1] == 0 for v in (verts[t[0][0]], verts[t[0][1]], verts[t[0][2]])]
    flame = [v for t in tris0 if t[1] in FLAME
             for v in (verts[t[0][0]], verts[t[0][1]], verts[t[0][2]])]
    meta = {
        "scale": sc,
        "cell_m": args.cell,
        "base": round(-min(ys), 4),
        "body_top": round(max(body_ys), 4),
        "tip": round(max(ys), 4),
        "flame": [round(sum(v[i] for v in flame) / len(flame), 4) for i in range(3)] if flame else None,
        "raw_tris": len(tris0),
    }
    data = {
        "schema": "ae.mesh/1",
        "id": "molotov",
        "verts": [[round(c, 5) for c in v] for v in out_v],
        "faces": [[f[0], f[1], f[2]] for f in out_f],
        "tris": len(out_f),
        "source": os.path.basename(SRC),
        "meta": meta,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    print("AE IMPORT MOLOTOV: %d raw tris -> %d faces / %d verts  (cell %.1f mm)"
          % (len(tris0), len(out_f), len(out_v), args.cell * 1000.0))
    print("  base %.3f m  body top %.3f m  tip %.3f m  flame %s"
          % (meta["base"], meta["body_top"], meta["tip"], meta["flame"]))
    print("  ->", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
