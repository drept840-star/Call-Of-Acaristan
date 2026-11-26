#!/usr/bin/env python3
"""AE IMPORT SNIPER - bolt-action suppressed sniper rifle (assets/3D/lowpoly_sniper_rifle.glb).

    python tools/ae_import_sniper.py [--cell 0.0015] [--length 1.18]

Reuses the GLB reader of tools/ae_import_k93d.py. The source already faces
+z (muzzle) with +y up and +x right (bolt handle on the right); it is scaled
to ``--length`` metres overall with its origin on the pistol grip.

Output: src/game/content/meshes/sniper_rifle.mesh.json
    meta  muzzle, butt, guard and fore (left-hand) points in gun space; the
          same numbers live in engine3d.hold GRIPS["sniper_rifle"].
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ae_import_k93d as K  # noqa: E402

ROOT = K.ROOT
SRC = os.path.join(ROOT, "assets", "3D", "lowpoly_sniper_rifle.glb")
OUT = os.path.join(ROOT, "src", "game", "content", "meshes", "sniper_rifle.mesh.json")

# GLB PBR baseColorFactors converted to sRGB house tones.
COLOURS = {
    0: (179, 152, 112),   # Mat_Primary: tan/FDE chassis, stock & handguard
    1: (61, 56, 50),      # Mat_Metal: receiver, fluted barrel, scope tube
    2: (14, 15, 18),      # Mat_Bore: ejection port & suppressor bore
    3: (52, 45, 38),      # Mat_Secondary: grip, mag, buttpad, cheekrest, suppressor
    4: (202, 178, 139),   # Mat_Accent: bolt handle, turrets, floorplate, collar
    5: (235, 154, 24),    # Mat_Lens: amber scope lenses
}
GRAIN = {0: 0.08, 1: 0.07, 2: 0.03, 3: 0.08, 4: 0.07, 5: 0.02}

# Source-space landmarks (GLB metres, muzzle on +z, +y up).
GRIP = (0.0, -0.058, -0.112)     # right hand: middle-upper pistol grip
BUTT = (0.0, -0.016, -0.418)     # shoulder contact on the buttpad
GUARD = (0.0, -0.018, 0.140)     # front of magwell / chassis
FORE = (0.0, -0.014, 0.250)      # left hand cupping the handguard


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", type=float, default=0.0015,
                    help="vertex-cluster cell in metres (default 1.5 mm)")
    ap.add_argument("--length", type=float, default=1.18,
                    help="overall length in metres (default 1.18)")
    args = ap.parse_args()

    g, binbuf = K._gltf(SRC)
    verts, tris0, _focus = K._scan(g, binbuf)
    span = max(v[2] for v in verts) - min(v[2] for v in verts)
    s = args.length / span

    def to_gun(x, y, z):
        return ((x - GRIP[0]) * s, (y - GRIP[1]) * s, (z - GRIP[2]) * s)

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
        k *= 1.0 + GRAIN.get(mat, 0.07) * ((((h >> 16) & 0xFFFF) / 65535.0) * 2 - 1)
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
        "id": "sniper_rifle",
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
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    print("AE IMPORT SNIPER: %d raw tris -> %d faces / %d verts  (cell %.4f)"
          % (len(tris0), len(out_f), len(out_v), args.cell))
    print("  muzzle", data["meta"]["muzzle"], " butt", data["meta"]["butt"],
          " guard", data["meta"]["guard"], " fore", data["meta"]["fore"])
    print("  ->", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
