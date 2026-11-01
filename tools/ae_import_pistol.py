#!/usr/bin/env python3
"""AE IMPORT PISTOL - the multiplayer service pistol (assets/3D/pistol_lowpoly.glb).

    python tools/ae_import_pistol.py [--cell 0.0015]

Reuses the GLB reader of tools/ae_import_k93d.py. The source is authored in
metres with its muzzle on +x; it is turned into the rig's gun frame (+z
muzzle, +y up, origin = right hand on the grip) at its own scale.

Faces take core.appearance.GUN_BASE["pistol"] role colours verbatim, so the
Outfitter finishes map role for role (ui.mp3d._finish_col).

Output: src/game/content/meshes/pistol.mesh.json
    meta  muzzle point in gun space.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ae_import_k93d as K  # noqa: E402

ROOT = K.ROOT
SRC = os.path.join(ROOT, "assets", "3D", "pistol_lowpoly.glb")
OUT = os.path.join(ROOT, "src", "game", "content", "meshes", "pistol.mesh.json")

sys.path.insert(0, os.path.join(ROOT, "src"))
from core.appearance import GUN_BASE  # noqa: E402

# Source material name -> GUN_BASE["pistol"] role.
ROLES = {
    "Pistol_Slide": "slide",
    "Pistol_Dark": "slide_edge",
    "Pistol_Frame": "frame",
    "Pistol_Barrel": "barrel",
    "Pistol_Dot": "optic",
    "Pistol_Grip": "grip",
    "Pistol_Screw": "barrel",
}

# Source-space right hand: top of the grip, level with the frame rail, so the
# bore sits ~46 mm above the hand like the old box pistol.
GRIP = (-0.080, 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", type=float, default=0.0015,
                    help="vertex-cluster cell in metres (default 1.5 mm)")
    args = ap.parse_args()

    g, binbuf = K._gltf(SRC)
    verts, tris0, _focus = K._scan(g, binbuf)
    base = GUN_BASE["pistol"]
    names = [m.get("name", "") for m in g.get("materials", [])]

    def to_gun(x, y, z=0.0):
        return (-z, y - GRIP[1], x - GRIP[0])

    verts = [to_gun(*v) for v in verts]
    tris = []
    for idx, mat, group, uv in tris0:
        name = names[mat] if mat is not None and mat < len(names) else ""
        tris.append((idx, mat, group, uv, base[ROLES.get(name, "frame")]))

    out_v, out_f = K._cluster(verts, tris, args.cell)
    zmax = max(v[2] for v in out_v)
    near = [v for v in out_v if v[2] > zmax - 0.003]
    muzzle = [0.0, sum(v[1] for v in near) / len(near), zmax]

    data = {
        "schema": "ae.mesh/1",
        "id": "pistol",
        "verts": [[round(c, 5) for c in v] for v in out_v],
        "faces": [[f[0], f[1]] for f in out_f],
        "tris": len(out_f),
        "source": os.path.basename(SRC),
        "meta": {
            "cell_m": args.cell,
            "muzzle": [round(c, 4) for c in muzzle],
            "raw_tris": len(tris0),
        },
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    print("AE IMPORT PISTOL: %d raw tris -> %d faces / %d verts  (cell %.4f)"
          % (len(tris0), len(out_f), len(out_v), args.cell))
    print("  muzzle", data["meta"]["muzzle"])
    print("  ->", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
