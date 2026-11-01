#!/usr/bin/env python3
"""AE IMPORT AKRIFLE - the Guard/shared third-person rifle (assets/3D/ak-style-rifle.glb).

    python tools/ae_import_akrifle.py [--cell 0.004] [--length 0.88]

Reuses the GLB reader of tools/ae_import_k93d.py.  The source is an assembled
AK-pattern visual asset with its muzzle on +x and +y up; it is turned into the
rig's rifle frame (+z muzzle, +y up, origin = right hand on the pistol grip)
and scaled to ``--length`` metres overall.

Unlike the K93D there are no functional groups (the magazine/bolt do not move),
so this is the third-person / cutscene rifle; the GL viewmodel stays the K93D.

Output: src/game/content/meshes/akrifle.mesh.json
    meta  muzzle, butt, guard and fore (left-hand) points in gun space; the
          same numbers live in engine3d.hold GRIPS["akrifle"].
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ae_import_k93d as K  # noqa: E402

ROOT = K.ROOT
SRC = os.path.join(ROOT, "assets", "3D", "ak-style-rifle.glb")
OUT = os.path.join(ROOT, "src", "game", "content", "meshes", "akrifle.mesh.json")

# Material id -> house colour (the source factors are linear and near black).
COLOURS = {
    0: (50, 54, 62),      # receiver, dust cover, rivets: blued steel
    1: (26, 29, 34),      # mag, muzzle brake, rail: black
    2: (120, 62, 32),     # stock, grip, handguard: varnished wood
    3: (74, 38, 22),      # handguard insets, grip cap: dark wood trim
}
GRAIN = {0: 0.08, 1: 0.06, 2: 0.14, 3: 0.10}

# Source-space landmarks (GLB units, muzzle on +x, +y up).
GRIP = (-0.98, 1.42)      # right hand: top of the wooden pistol grip
BUTT = (-2.925, 1.446)    # shoulder contact on the butt plate
GUARD = (-0.255, 1.346)   # front of the trigger guard (reach check)
FORE = (0.95, 1.58)       # left hand: centre of the lower handguard


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", type=float, default=0.004,
                    help="vertex-cluster cell in metres (default 4 mm)")
    ap.add_argument("--length", type=float, default=0.88,
                    help="overall length in metres (default 0.88)")
    args = ap.parse_args()

    g, binbuf = K._gltf(SRC)
    verts, tris0, _focus = K._scan(g, binbuf)
    span = max(v[0] for v in verts) - min(v[0] for v in verts)
    s = args.length / span

    def to_gun(x, y, z=0.0):
        return (-z * s, (y - GRIP[1]) * s, (x - GRIP[0]) * s)

    verts = [to_gun(*v) for v in verts]
    tris = []
    for idx, mat, group, uv in tris0:
        col = COLOURS.get(mat, (90, 90, 90))
        a, b, c = verts[idx[0]], verts[idx[1]], verts[idx[2]]
        h = (round((a[0] + b[0] + c[0]) * 5000) * 374761393
             + round((a[1] + b[1] + c[1]) * 5000) * 668265263
             + round((a[2] + b[2] + c[2]) * 5000) * 2147483647) & 0xFFFFFFFF
        h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
        h ^= h >> 16
        k = 0.94 + 0.12 * ((h & 0xFFFF) / 65535.0)
        k *= 1.0 + GRAIN.get(mat, 0.08) * ((((h >> 16) & 0xFFFF) / 65535.0) * 2 - 1)
        col = tuple(min(255, max(0, int(v * k))) for v in col)
        tris.append((idx, mat, group, uv, col))

    out_v, out_f = K._cluster(verts, tris, args.cell)
    zmax = max(v[2] for v in out_v)
    near = [v for v in out_v if v[2] > zmax - 0.004]
    muzzle = [0.0, sum(v[1] for v in near) / len(near), zmax]

    def pt(p):
        return [round(c, 4) for c in to_gun(*p)]

    data = {
        "schema": "ae.mesh/1",
        "id": "akrifle",
        "verts": [[round(c, 5) for c in v] for v in out_v],
        "faces": [[f[0], f[1]] for f in out_f],
        "tris": len(out_f),
        "source": os.path.basename(SRC),
        "meta": {
            "length_m": args.length,
            "cell_m": args.cell,
            "muzzle": [round(c, 4) for c in muzzle],
            "butt": pt(BUTT),
            "guard": pt(GUARD),
            "fore": pt(FORE),
            "raw_tris": len(tris0),
        },
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    print("AE IMPORT AKRIFLE: %d raw tris -> %d faces / %d verts  (cell %.4f)"
          % (len(tris0), len(out_f), len(out_v), args.cell))
    print("  muzzle", data["meta"]["muzzle"], " butt", data["meta"]["butt"],
          " guard", data["meta"]["guard"], " fore", data["meta"]["fore"])
    print("  ->", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
