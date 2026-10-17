#!/usr/bin/env python3
"""AE IMPORT MESH - Blender/glTF/OBJ -> ae.mesh/1 asset (ADR-024).

    python3 tools/ae_import_mesh.py assets/import/barrel.obj barrel
    python3 tools/ae_import_mesh.py model.glb guard_prop --scale 0.01

Stdlib only. Face colours snap to the house palette (union of the
content/textures palettes); scale is linted as metres; a triangle
budget (default 1500) is enforced. Output lands in
src/game/content/meshes/<id>.mesh.json for set `mesh` nodes.
"""
import argparse
import base64
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESHES = os.path.join(ROOT, "src", "game", "content", "meshes")
TEXTURES = os.path.join(ROOT, "src", "game", "content", "textures")

_MTL_DEFAULTS = {"wood": (146, 110, 66), "metal": (58, 62, 68),
                 "dark": (30, 30, 34), "cloth": (70, 76, 60)}


def _palette():
    cols = set()
    for name in sorted(os.listdir(TEXTURES)):
        if name.endswith(".texture.json"):
            with open(os.path.join(TEXTURES, name), encoding="utf-8") as fh:
                for rgb in json.load(fh)["palette"].values():
                    cols.add(tuple(rgb))
    return sorted(cols)


def _snap(col, palette):
    best, best_d = None, 1e18
    for p in palette:
        d = sum((a - b) ** 2 for a, b in zip(col, p))
        if d < best_d:
            best, best_d = p, d
    return best, best_d ** 0.5


# ── loaders: each returns (verts, [(indices, colour), ...]) ─────────
def _read_accessor(data, gltf, binbuf, idx):
    acc = gltf["accessors"][idx]
    view = gltf["bufferViews"][acc["bufferView"]]
    off = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    n, ctype = acc["count"], acc["componentType"]
    fmt, size = {5126: ("f", 4), 5125: ("I", 4), 5123: ("H", 2)}[ctype]
    ncomp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[acc["type"]]
    stride = view.get("byteStride") or size * ncomp
    out = []
    for i in range(n):
        vals = struct.unpack_from("<" + fmt * ncomp, binbuf,
                                  off + i * stride)
        out.append(vals[0] if ncomp == 1 else tuple(vals))
    return out


def load_gltf(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    binbuf = b""
    if raw[:4] == b"glTF":  # GLB container
        ln_json, _t = struct.unpack_from("<II", raw, 12)
        gltf = json.loads(raw[20:20 + ln_json])
        off = 20 + ln_json
        if off < len(raw):
            ln_bin, _t2 = struct.unpack_from("<II", raw, off)
            binbuf = raw[off + 8:off + 8 + ln_bin]
    else:
        gltf = json.loads(raw.decode("utf-8"))
        uri = gltf["buffers"][0]["uri"]
        if uri.startswith("data:"):
            binbuf = base64.b64decode(uri.split(",", 1)[1])
        else:
            with open(os.path.join(os.path.dirname(path), uri), "rb") as fh:
                binbuf = fh.read()
    verts, faces = [], []
    for mesh in gltf.get("meshes", []):
        for prim in mesh["primitives"]:
            base = len(verts)
            pos = _read_accessor(None, gltf, binbuf, prim["attributes"]["POSITION"])
            verts.extend([tuple(float(c) for c in p) for p in pos])
            idxs = _read_accessor(None, gltf, binbuf, prim["indices"])
            col = (255, 255, 255)
            mat = prim.get("material")
            if mat is not None:
                factor = gltf["materials"][mat].get(
                    "pbrMetallicRoughness", {}).get("baseColorFactor")
                if factor:
                    col = tuple(int(round(c * 255)) for c in factor[:3])
            for i in range(0, len(idxs) - 2, 3):
                faces.append(((base + idxs[i], base + idxs[i + 1],
                               base + idxs[i + 2]), col))
    return verts, faces


def load_obj(path, mtl_colours):
    verts, faces = [], []
    col = mtl_colours.get("default", (200, 200, 200))
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            if not parts:
                continue
            if parts[0] == "v":
                verts.append(tuple(float(c) for c in parts[1:4]))
            elif parts[0] == "usemtl":
                col = mtl_colours.get(parts[1], col)
            elif parts[0] == "f":
                idx = []
                for tok in parts[1:]:
                    i = int(tok.split("/")[0])
                    idx.append(i - 1 if i > 0 else len(verts) + i)
                for i in range(1, len(idx) - 1):
                    faces.append(((idx[0], idx[i], idx[i + 1]), col))
    return verts, faces


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("id")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--budget", type=int, default=1500)
    ap.add_argument("--color", default=None, help="OBJ default #RRGGBB")
    ap.add_argument("--mtl", action="append", default=[],
                    help="OBJ material colour name=#RRGGBB (repeatable)")
    ap.add_argument("--strict", action="store_true",
                    help="fail on palette snaps farther than 24/channel")
    ap.add_argument("--no-ground", action="store_true")
    args = ap.parse_args()

    mtl = dict(_MTL_DEFAULTS)
    for kv in args.mtl:
        name, hexv = kv.split("=", 1)
        mtl[name] = tuple(int(hexv[i:i + 2], 16) for i in (0, 2, 4))
    if args.color:
        hexv = args.color.lstrip("#")
        mtl["default"] = tuple(int(hexv[i:i + 2], 16) for i in (0, 2, 4))

    if args.src.lower().endswith((".glb", ".gltf")):
        verts, faces = load_gltf(args.src)
    else:
        verts, faces = load_obj(args.src, mtl)
    if not verts or not faces:
        print("AE IMPORT MESH: FAIL (no geometry)")
        return 1

    palette = _palette()
    worst = 0.0
    snapped = []
    for idx, col in faces:
        p, d = _snap(col, palette)
        worst = max(worst, d)
        snapped.append((idx, list(p)))
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    height = (max(ys) - min(ys)) * args.scale
    print(f"AE IMPORT MESH: {args.src}: {len(verts)} verts, "
          f"{len(faces)} tris, bbox {max(xs)-min(xs):.2f} x "
          f"{height:.2f} x {max(zs)-min(zs):.2f} m (after scale), "
          f"worst palette snap {worst:.1f}")
    if len(faces) > args.budget:
        print(f"AE IMPORT MESH: FAIL ({len(faces)} tris > budget "
              f"{args.budget}; raise --budget deliberately if intended)")
        return 1
    if not (0.05 <= height <= 40.0):
        print(f"AE IMPORT MESH: FAIL (height {height:.2f} m outside "
              "0.05-40 m - wrong units? pass --scale)")
        return 1
    if args.strict and worst > 42.0:
        print("AE IMPORT MESH: FAIL (strict palette snap > 42)")
        return 1

    lift = 0.0 if args.no_ground else -min(ys)
    out_verts = [[round((v[0]) * args.scale, 5),
                  round((v[1] + lift) * args.scale, 5),
                  round(v[2] * args.scale, 5)] for v in verts]
    out_faces = [[list(idx), col] for idx, col in snapped]
    os.makedirs(MESHES, exist_ok=True)
    path = os.path.join(MESHES, args.id + ".mesh.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"schema": "ae.mesh/1", "id": args.id,
                   "verts": out_verts, "faces": out_faces,
                   "tris": len(out_faces),
                   "source": os.path.basename(args.src)}, fh, indent=1)
        fh.write("\n")
    print(f"AE IMPORT MESH: OK -> {os.path.relpath(path, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
