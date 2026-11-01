#!/usr/bin/env python3
"""AE EXPORT AK74 GLB - the code-authored AK-74 written back out as a GLB source.

    python tools/ae_export_ak74_glb.py [--finish wood|plum|poly] [--length 0.940]
                                       [--out assets/3D/ak74-style-rifle.glb]
                                       [--dump] [--no-verify]

House rule is that art is authored by code (tools/ae_build_ak74.py) and baked to
ae.mesh/1.  This writes the same geometry out as a GLB so the weapon also exists
as an asset beside the imported ones in assets/3D - openable in Blender, and
readable by any importer that reuses tools/ae_import_k93d.py's GLB reader.

Source space matches assets/3D/ak-style-rifle.glb: muzzle on +x, +y up, metres,
origin = the right hand on the pistol grip.  That makes ae_import_akrifle's
``to_gun()`` the exact inverse at ``GRIP = (0.0, 0.0)`` and ``s = 1``:

    src_x = gun_z     src_y = gun_y     src_z = -gun_x

The map has determinant +1, so it is a pure rotation: triangle winding and
outward normals survive untouched.  The file is checked after it is written -
container layout, accessor min/max against the stored data, and a triangle
multiset round trip through tools/ae_import_k93d.py's reader, where each key
carries its normal so a flipped winding cannot pass.  ``--no-verify`` skips it.

Colours: one named glTF material per base palette entry, metallic/roughness
chosen by material class.  The per-face grain dither that ae_build_ak74 adds so
the flat renderer does not band a big wood or steel slab is a renderer-side
trick and is not carried into the GLB; the build here bypasses ``_grain`` so
every face keeps its exact palette colour and the material list stays small.
That leaves the vertices bit-identical, which the round-trip check asserts.

Structure mirrors the other sources: one named node per authored part, one mesh
per node, one primitive per (part, material).  Primitives are non-indexed with
per-triangle normals, which keeps every face hard-edged the way the flat-shaded
engine wants it - Suppressed_Pistol.glb is non-indexed too, and _scan handles it.

Output: assets/3D/ak74-style-rifle.glb
"""
import argparse
import json
import math
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import ae_build_ak74 as B  # noqa: E402

OUT = os.path.join(ROOT, "assets", "3D", "ak74-style-rifle.glb")

# glTF bufferView targets and primitive mode
ARRAY_BUFFER = 34962
TRIANGLES = 4

# authored part -> node name
NODE_NAMES = {
    "brake": "Muzzle brake",
    "barrel": "Barrel",
    "front_sight": "Front sight",
    "gas_block": "Gas block",
    "gas_tube": "Gas tube",
    "rear_sight": "Rear sight",
    "handguards": "Handguards",
    "receiver": "Receiver",
    "magazine": "Magazine",
    "trigger": "Trigger and guard",
    "grip": "Pistol grip",
    "stock": "Stock",
}



def _lin(c8):
    """sRGB 0..255 channel -> glTF linear 0..1."""
    c = c8 / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _palette(finish):
    """colour tuple -> material name, for the base palette of ``finish``."""
    furn, furn_d, grip, mag, _gf, _gm = B.FINISHES[finish]
    furniture = {"wood": "Varnished laminate", "plum": "Plum polymer furniture",
                 "poly": "Black polymer furniture"}[finish]
    magazine = {"wood": "Plum bakelite magazine", "plum": "Plum polymer magazine",
                "poly": "Black polymer magazine"}[finish]
    return {
        tuple(B.STEEL): "Blued steel",
        tuple(B.STEEL_D): "Machined steel",
        tuple(B.BLACK): "Blackened steel",
        (12, 12, 14): "Sight notch",
        furn: furniture,
        furn_d: "Furniture shadow",
        grip: "Grip",
        mag: magazine,
    }


def _material(col, name):
    metal = any(k in name.lower() for k in ("steel", "notch"))
    return {
        "name": name,
        "doubleSided": False,
        "pbrMetallicRoughness": {
            "baseColorFactor": [round(_lin(c), 6) for c in col] + [1.0],
            "metallicFactor": 0.72 if metal else 0.0,
            "roughnessFactor": 0.46 if metal else 0.74,
        },
    }


def _normal(a, b, c):
    """Unit CCW normal of (a,b,c), or None if degenerate."""
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length <= 1e-12:
        return None
    return (nx / length, ny / length, nz / length)


def _to_src(v):
    """Gun space -> this file's source space (see the module docstring)."""
    x, y, z = v
    return (z, y, -x)


class _Glb:
    """Minimal GLB 2.0 writer: one buffer, f32 VEC3 attributes, no images."""

    def __init__(self):
        self.buf = bytearray()
        self.buffer_views = []
        self.accessors = []

    def _view(self, data, target):
        while len(self.buf) % 4:
            self.buf.append(0)
        off = len(self.buf)
        self.buf.extend(data)
        self.buffer_views.append({"buffer": 0, "byteOffset": off,
                                  "byteLength": len(data), "target": target})
        return len(self.buffer_views) - 1

    def vec3(self, vals, target=ARRAY_BUFFER):
        """-> accessor index.  Values are quantised through f32 first so the
        declared min/max can never fall outside what is actually stored."""
        raw = b"".join(struct.pack("<3f", *v) for v in vals)
        f32 = [struct.unpack_from("<3f", raw, i * 12) for i in range(len(vals))]
        acc = {"bufferView": self._view(raw, target), "componentType": 5126,
               "count": len(f32), "type": "VEC3",
               "min": [min(v[i] for v in f32) for i in range(3)],
               "max": [max(v[i] for v in f32) for i in range(3)]}
        self.accessors.append(acc)
        return len(self.accessors) - 1


def _flat_build(finish, length):
    """``B.build`` with the per-face grain dither bypassed, so every face carries
    its exact palette colour and the material list stays small.  The dither is a
    renderer-side anti-banding trick; it never moves a vertex."""
    saved = B._grain
    B._grain = lambda col, pts, amt: tuple(col)
    try:
        return B.build(finish, length)
    finally:
        B._grain = saved


def build_glb(finish="wood", length=B.LEN):
    """-> (bytes, report) of the exported GLB."""
    gverts, gtris, meta = _flat_build(finish, length)

    faces = [(tuple(t[0]), tuple(t[4])) for t in gtris]
    names = _palette(finish)

    # materials, in first-use order so the bytes are deterministic
    mat_of, materials, detail = {}, [], 0
    for _idx, col in faces:
        if col not in mat_of:
            name = names.get(col)
            if name is None:
                detail += 1
                name = "Detail %02d" % detail
            mat_of[col] = len(materials)
            materials.append(_material(col, name))

    # meta["parts"] counts faces per part, in the order build() emitted them
    order = list(meta["parts"])
    parts, cursor = [], 0
    for name in order:
        n = meta["parts"][name]
        parts.append((name, faces[cursor:cursor + n]))
        cursor += n
    if cursor != len(faces):
        raise SystemExit("AE EXPORT AK74 GLB: FAIL (parts cover %d of %d faces)"
                         % (cursor, len(faces)))

    glb = _Glb()
    meshes, nodes = [], []
    kept = dropped = 0
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for name, flist in parts:
        groups = {}
        for idx, col in flist:
            groups.setdefault(col, []).append(idx)
        prims = []
        for col, idxs in groups.items():
            pos, nrm = [], []
            for idx in idxs:
                # quantise first: the stored normal must be the normal of the
                # vertices actually in the file, not of their float64 originals
                tri = [_f32(_to_src(gverts[i])) for i in idx]
                n = _normal(*tri)
                if n is None:
                    dropped += 1
                    continue
                pos.extend(tri)
                nrm.extend((n, n, n))
                kept += 1
                for p in tri:
                    for i in range(3):
                        lo[i] = min(lo[i], p[i])
                        hi[i] = max(hi[i], p[i])
            if not pos:
                continue
            prims.append({"attributes": {"POSITION": glb.vec3(pos),
                                         "NORMAL": glb.vec3(nrm)},
                          "material": mat_of[col], "mode": TRIANGLES})
        if prims:
            label = NODE_NAMES.get(name, name.replace("_", " ").title())
            meshes.append({"name": label, "primitives": prims})
            nodes.append({"name": label, "mesh": len(meshes) - 1})

    root = len(nodes)
    nodes.append({"name": "ak74-style-rifle", "children": list(range(root))})
    bin_len = (len(glb.buf) + 3) // 4 * 4
    gltf = {
        "asset": {"version": "2.0",
                  "generator": "tools/ae_export_ak74_glb.py",
                  "copyright": "Call of Acaristan - code-authored AK-74 (6P20)"},
        "scene": 0,
        "scenes": [{"name": "ak74-style-rifle", "nodes": [root]}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "accessors": glb.accessors,
        "bufferViews": glb.buffer_views,
        "buffers": [{"byteLength": bin_len}],
    }

    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * ((-len(js)) % 4)
    binbuf = bytes(glb.buf) + b"\x00" * ((-len(glb.buf)) % 4)
    total = 12 + 8 + len(js) + 8 + len(binbuf)
    out = bytearray()
    out += struct.pack("<4sII", b"glTF", 2, total)
    out += struct.pack("<II", len(js), 0x4E4F534A)
    out += js
    out += struct.pack("<II", len(binbuf), 0x004E4942)
    out += binbuf

    report = dict(tris=len(faces), kept=kept, dropped=dropped,
                  verts=kept * 3, parts=len(nodes) - 1,
                  materials=[m["name"] for m in materials],
                  json_bytes=len(js), bin_bytes=len(binbuf), total_bytes=total,
                  bbox=[tuple(lo), tuple(hi)], span_x=hi[0] - lo[0],
                  meta=meta, finish=finish, length=length)
    return bytes(out), report


def _landmarks(meta):
    """Gun-space landmarks -> (src x, src y), the pair an importer needs."""
    out = {}
    for key in ("muzzle", "butt", "guard", "fore"):
        p = meta[key]
        s = _to_src(p)
        out[key] = (round(s[0], 4), round(s[1], 4))
    return out


def _f32(p):
    """Round a point through float32, the way the writer stores it."""
    return struct.unpack("<3f", struct.pack("<3f", *p))


def _sig(tri, n):
    """Order-independent identity of a triangle: sorted corners plus its normal.

    Sorting the corners makes the key immune to emission order; carrying the
    normal is what makes it sensitive to winding, since a flipped triangle has
    the same corner set and the opposite normal."""
    corners = tuple(sorted(tuple(round(c, 3) for c in p) for p in tri))
    return corners + (tuple(round(c, 3) for c in n),)


def verify(path, finish, length):
    """-> list of failures for the GLB at ``path``.  Empty means it is sound."""
    from collections import Counter

    import ae_import_k93d as K

    fails = []

    def check(ok, msg):
        if not ok:
            fails.append(msg)
        return ok

    raw = open(path, "rb").read()
    if not check(raw[:4] == b"glTF", "not a GLB (bad magic)"):
        return fails
    ver, total = struct.unpack_from("<II", raw, 4)
    check(ver == 2, "glTF version %d, expected 2" % ver)
    check(total == len(raw), "header length %d != file %d bytes" % (total, len(raw)))
    if len(raw) < 28:
        fails.append("file too short to hold two chunks")
        return fails
    l0, t0 = struct.unpack_from("<II", raw, 12)
    l1, t1 = struct.unpack_from("<II", raw, 20 + l0)
    check(t0 == 0x4E4F534A, "chunk 0 type %#x is not JSON" % t0)
    check(t1 == 0x004E4942, "chunk 1 type %#x is not BIN" % t1)
    check(l0 % 4 == 0 and l1 % 4 == 0, "chunk lengths %d/%d are not 4-byte aligned" % (l0, l1))
    check(12 + 8 + l0 + 8 + l1 == len(raw), "chunk lengths do not sum to the file size")
    if fails:
        return fails

    g = json.loads(raw[20:20 + l0])
    binbuf = raw[20 + l0 + 8:20 + l0 + 8 + l1]
    check(len(g.get("buffers", [])) == 1, "expected exactly one buffer")
    check(g["buffers"][0].get("byteLength", -1) <= l1,
          "buffer byteLength exceeds the BIN chunk")
    check(g.get("scene") == 0 and g.get("scenes"), "no default scene")

    for i, bv in enumerate(g["bufferViews"]):
        off = bv.get("byteOffset", 0)
        check(off + bv["byteLength"] <= len(binbuf),
              "bufferView %d runs past the BIN chunk" % i)
        check(off % 4 == 0, "bufferView %d byteOffset %d is not aligned" % (i, off))

    for i, a in enumerate(g["accessors"]):
        check(0 <= a["bufferView"] < len(g["bufferViews"]),
              "accessor %d has a bad bufferView" % i)
        if a["type"] == "VEC3" and "min" in a:
            vals = K._acc(g, binbuf, i)
            for axis in range(3):
                got = [v[axis] for v in vals]
                check(abs(min(got) - a["min"][axis]) < 1e-5,
                      "accessor %d min[%d] %.6f != data %.6f" % (i, axis, a["min"][axis], min(got)))
                check(abs(max(got) - a["max"][axis]) < 1e-5,
                      "accessor %d max[%d] %.6f != data %.6f" % (i, axis, a["max"][axis], max(got)))

    def walk(ni):
        nd = g["nodes"][ni]
        check("matrix" not in nd
              and not any(k in nd for k in ("translation", "rotation", "scale")),
              "node %r carries a transform (positions are baked)" % nd.get("name"))
        if "mesh" in nd:
            for pr in g["meshes"][nd["mesh"]]["primitives"]:
                yield pr
        for ch in nd.get("children", []):
            for sub in walk(ch):
                yield sub

    prims = [pr for ni in g["scenes"][0]["nodes"] for pr in walk(ni)]
    check(len(prims) > 0, "no primitives reachable from the scene")

    got = Counter()
    for pr in prims:
        check(pr.get("mode", TRIANGLES) == TRIANGLES, "primitive mode is not TRIANGLES")
        check(0 <= pr.get("material", 0) < len(g["materials"]),
              "primitive has an out-of-range material")
        check("POSITION" in pr["attributes"] and "NORMAL" in pr["attributes"],
              "primitive lacks POSITION or NORMAL")
        pos = K._acc(g, binbuf, pr["attributes"]["POSITION"])
        nrm = K._acc(g, binbuf, pr["attributes"]["NORMAL"])
        check(len(pos) == len(nrm) and len(pos) % 3 == 0,
              "primitive has %d positions / %d normals" % (len(pos), len(nrm)))
        for k in range(0, len(pos) - 2, 3):
            got[_sig(pos[k:k + 3], nrm[k])] += 1

    # what the generator says, transformed and quantised the same way
    plain_v, plain_t, _ = _flat_build(finish, length)
    grain_v, grain_t, _ = B.build(finish, length)

    check(len(grain_v) == len(plain_v)
          and all(a == b for a, b in zip(grain_v, plain_v)),
          "bypassing the grain moved the vertices")
    check(len(grain_t) == len(plain_t),
          "bypassing the grain changed the face count")

    want = Counter()
    for t in plain_t:
        tri = [_f32(_to_src(plain_v[i])) for i in t[0]]
        n = _normal(*tri)
        if n is not None:
            want[_sig(tri, n)] += 1

    check(sum(want.values()) == sum(got.values()),
          "triangle count %d in the file, %d expected" % (sum(got.values()), sum(want.values())))
    for key, n in want.items():
        if got.get(key, 0) != n:
            check(False, "triangle missing or wound differently: %s (file %d, expected %d)"
                  % (str(key[3]), got.get(key, 0), n))
            break
    for key, n in got.items():
        if want.get(key, 0) != n:
            check(False, "unexpected triangle in the file: %s (file %d, expected %d)"
                  % (str(key[3]), n, want.get(key, 0)))
            break
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--finish", default="wood", choices=sorted(B.FINISHES),
                    help="furniture to export (default wood)")
    ap.add_argument("--length", type=float, default=B.LEN,
                    help="overall length in metres (default %.3f)" % B.LEN)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--dump", action="store_true", help="print the part and material tables")
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the container + round-trip check of the written file")
    args = ap.parse_args()

    raw, rep = build_glb(args.finish, args.length)
    path = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(raw)

    print("AE EXPORT AK74 GLB: %d tris / %d verts across %d named parts"
          % (rep["kept"], rep["verts"], rep["parts"]))
    print("  finish %s   length %.3f m   %d materials" %
          (rep["finish"], rep["length"], len(rep["materials"])))
    if rep["dropped"]:
        print("  %d degenerate triangles skipped" % rep["dropped"])
    print("  json %d B + bin %d B = %d B" % (rep["json_bytes"], rep["bin_bytes"],
                                             rep["total_bytes"]))
    lo, hi = rep["bbox"]
    print("  source space: muzzle +x, +y up, metres, origin = right hand on the grip")
    print("  bbox x %+.4f..%+.4f  y %+.4f..%+.4f  z %+.4f..%+.4f"
          % (lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
    print("  to_gun GRIP = (0.000, 0.000); span-scaled import gives s = %.5f"
          % (args.length / rep["span_x"]))
    print("    (span x %.4f exceeds the nominal %.3f: the buttplate stands proud)"
          % (rep["span_x"], args.length))
    for key, pt in _landmarks(rep["meta"]).items():
        print("    %-7s (%+.4f, %+.4f)" % (key, pt[0], pt[1]))
    if args.dump:
        print("  parts:")
        for name, n in rep["meta"]["parts"].items():
            print("    %-12s %-20s %4d tris" % (name, NODE_NAMES.get(name, name), n))
        print("  materials:")
        for i, name in enumerate(rep["materials"]):
            print("    %d  %s" % (i, name))
    if not args.no_verify:
        bad = verify(path, args.finish, args.length)
        if bad:
            for msg in bad[:12]:
                print("  FAIL:", msg)
            raise SystemExit("AE EXPORT AK74 GLB: FAIL (%d checks)" % len(bad))
        print("  verify: container, accessors and a %d-triangle round trip match the generator"
              % rep["kept"])
    print("  ->", os.path.relpath(path, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
