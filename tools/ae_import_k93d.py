#!/usr/bin/env python3
"""AE IMPORT K93D - the first authored 3D weapon asset (assets/3D/K93D.glb).

    python tools/ae_import_k93d.py [--cell 0.008] [--scale 0.34]

Unlike tools/ae_import_mesh.py this importer understands a multi-node GLB:
node matrices/TRS are applied, embedded base-colour textures are sampled per
triangle (the engine is flat-shaded), and the merged gun is vertex-clustered
into the ae.mesh/1 vertex/triangle budget the renderers can afford.

Output: src/game/content/meshes/k93d.mesh.json
    verts/faces  ae.mesh/1 (faces may carry an optional emissive flag)
    meta         muzzle/sight points and the magazine face group, in gun
                 space (+z muzzle, +y up, origin at the trigger).
"""
import argparse
import io
import json
import os
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "3D", "K93D.glb")
OUT = os.path.join(ROOT, "src", "game", "content", "meshes", "k93d.mesh.json")

# Material id -> (house tint, texture detail contrast). Tints are lifted for
# the night scene: the real factors are near black and die under the fill.
MATERIALS = {
    0: ((104, 110, 124), 0.60),   # Upper_Anodized_Alloy (brushed metal)
    1: ((48, 52, 62), 0.50),      # Nitride_Barrel_Steel
    2: ((126, 134, 148), 0.55),   # Machined_Titanium_Accent
    3: ((44, 48, 54), 1.25),      # Lower_Carbon_Polymer (weave)
    4: ((90, 94, 104), 1.10),     # Magazine_Molded_Polymer
    5: ((64, 52, 40), 0.55),      # Stippled_Overmold_Grip
    6: ((80, 240, 130), 0.0),     # Green_Laser_Diode
    7: ((18, 92, 112), 0.65),     # Holographic_Reticle_Lens
}

I4 = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


def _gltf(path):
    raw = open(path, "rb").read()
    if raw[:4] != b"glTF":
        raise SystemExit("AE IMPORT K93D: FAIL (not a GLB)")
    ln, _ = struct.unpack_from("<II", raw, 12)
    g = json.loads(raw[20:20 + ln])
    off = 20 + ln
    lnb, _ = struct.unpack_from("<II", raw, off)
    return g, raw[off + 8:off + 8 + lnb]


def _acc(g, binbuf, i):
    a = g["accessors"][i]
    v = g["bufferViews"][a["bufferView"]]
    off = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    n, ct = a["count"], a["componentType"]
    fmt, size = {5126: ("f", 4), 5125: ("I", 4), 5123: ("H", 2), 5121: ("B", 1)}[ct]
    ncomp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
    stride = v.get("byteStride") or size * ncomp
    return [struct.unpack_from("<" + fmt * ncomp, binbuf, off + k * stride)
            for k in range(n)]


def _mul(a, b):
    out = [0.0] * 16
    for c in range(4):
        for r in range(4):
            out[c * 4 + r] = sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4))
    return out


def _trs(nd):
    t = nd.get("translation", [0, 0, 0])
    q = nd.get("rotation", [0, 0, 0, 1])
    s = nd.get("scale", [1, 1, 1])
    x, y, z, w = q
    r = [1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w), 0,
         2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w), 0,
         2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y), 0,
         0, 0, 0, 1]
    sm = [s[0], 0, 0, 0, 0, s[1], 0, 0, 0, 0, s[2], 0, 0, 0, 0, 1]
    tm = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, t[0], t[1], t[2], 1]
    return _mul(tm, _mul(r, sm))


def _xf(m, p):
    x, y, z = p
    return (m[0] * x + m[4] * y + m[8] * z + m[12],
            m[1] * x + m[5] * y + m[9] * z + m[13],
            m[2] * x + m[6] * y + m[10] * z + m[14])


def _textures(g, binbuf):
    """Decode embedded images -> (w, h, rows of RGB, mean luma) or None."""
    try:
        import numpy as np
        from PIL import Image
    except Exception:
        return {}
    out = {}
    for i, img in enumerate(g.get("images", [])):
        bv = g["bufferViews"][img["bufferView"]]
        off = bv.get("byteOffset", 0)
        data = binbuf[off:off + bv["byteLength"]]
        im = Image.open(io.BytesIO(data)).convert("RGBA")
        a = np.asarray(im, dtype=np.float32)
        lum = 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]
        mask = a[:, :, 3] > 16
        mean = float(lum[mask].mean()) if mask.any() else float(lum.mean())
        out[i] = (im.width, im.height, a[:, :, :3].astype(np.uint8), max(1.0, mean))
    return out


def _scan(g, binbuf):
    """World-space triangles: (points, material, group, uv_rgb_hint)."""
    verts, tris = [], []
    focus = {}

    def walk(ni, m):
        nd = g["nodes"][ni]
        if "matrix" in nd:
            m = _mul(m, nd["matrix"])
        elif any(k in nd for k in ("translation", "rotation", "scale")):
            m = _mul(m, _trs(nd))
        name = nd.get("name", "")
        if "mesh" in nd:
            for pr in g["meshes"][nd["mesh"]]["primitives"]:
                base = len(verts)
                pos = _acc(g, binbuf, pr["attributes"]["POSITION"])
                world = [_xf(m, p) for p in pos]
                verts.extend(world)
                idx = (_acc(g, binbuf, pr["indices"]) if "indices" in pr
                       else [(k,) for k in range(len(pos))])
                uv = None
                if "TEXCOORD_0" in pr["attributes"]:
                    uv = _acc(g, binbuf, pr["attributes"]["TEXCOORD_0"])
                group = 1 if name.startswith("Magazine") else 0
                if name in ("Optic_Reflex_Glass", "Curved_Trigger") or name.startswith("Suppressor"):
                    xs = [p[0] for p in world]; ys = [p[1] for p in world]
                    zs = [p[2] for p in world]
                    focus.setdefault(name, []).append(
                        ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                         (min(zs) + max(zs)) / 2, max(zs),
                         max(xs) - min(xs), max(ys) - min(ys)))
                for k in range(0, len(idx) - 2, 3):
                    a, b, c = idx[k][0], idx[k + 1][0], idx[k + 2][0]
                    u = None
                    if uv is not None and max(a, b, c) < len(uv):
                        u = ((uv[a][0] + uv[b][0] + uv[c][0]) / 3,
                             (uv[a][1] + uv[b][1] + uv[c][1]) / 3)
                    tris.append(((base + a, base + b, base + c),
                                 pr.get("material", 0), group, u))
        for ch in nd.get("children", []):
            walk(ch, m)

    for ni in g["scenes"][0]["nodes"]:
        walk(ni, I4)
    return verts, tris, focus


def _face_colour(g, tex, mat_id, uv):
    tint, contrast = MATERIALS.get(mat_id, ((110, 110, 110), 0.6))
    mat = g.get("materials", [{}])[mat_id] if mat_id < len(g.get("materials", [])) else {}
    pbr = mat.get("pbrMetallicRoughness", {})
    texref = pbr.get("baseColorTexture")
    if texref is None or uv is None:
        return tint
    src = g.get("textures", [])[texref["index"]].get("source")
    img = tex.get(src)
    if img is None:
        return tint
    w, h, px, mean = img
    tf = texref.get("extensions", {}).get("KHR_texture_transform", {})
    scale = tf.get("scale", [1.0, 1.0])
    off = tf.get("offset", [0.0, 0.0])
    u = (uv[0] * scale[0] + off[0]) % 1.0
    v = (uv[1] * scale[1] + off[1]) % 1.0
    x = min(w - 1, max(0, int(u * w)))
    y = min(h - 1, max(0, int(v * h)))
    r, gg, b = (float(px[y, x, 0]), float(px[y, x, 1]), float(px[y, x, 2]))
    lum = 0.299 * r + 0.587 * gg + 0.114 * b
    k = 1.0 + (lum / mean - 1.0) * contrast
    k = max(0.55, min(1.45, k))
    return tuple(min(255, max(0, int(c * k))) for c in tint)


def _cluster(verts, tris, cell):
    keymap, reps, remap = {}, [], []
    for v in verts:
        key = (round(v[0] / cell), round(v[1] / cell), round(v[2] / cell))
        i = keymap.get(key)
        if i is None:
            i = len(reps)
            keymap[key] = i
            reps.append([0.0, 0.0, 0.0, 0])
        r = reps[i]
        r[0] += v[0]; r[1] += v[1]; r[2] += v[2]; r[3] += 1
        remap.append(i)
    out = [tuple(c / r[3] for c in r[:3]) for r in reps]
    faces, seen = [], set()
    for (idx, mat, group, uv, col) in tris:
        a, b, c = remap[idx[0]], remap[idx[1]], remap[idx[2]]
        if a == b or b == c or a == c:
            continue
        key = tuple(sorted((a, b, c)))
        if key in seen:
            continue
        seen.add(key)
        faces.append(([a, b, c], list(col), group))
    return out, faces


def _export_reticle(g, tex):
    """Save the holo-sight lens texture as a transparent reticle sprite."""
    try:
        import numpy as np
        from PIL import Image
    except Exception:
        return None
    mat = next((m for m in g.get("materials", [])
                if m.get("name") == "Holographic_Reticle_Lens"), None)
    if mat is None:
        return None
    ref = mat.get("pbrMetallicRoughness", {}).get("baseColorTexture")
    if ref is None:
        return None
    src = g.get("textures", [])[ref["index"]].get("source")
    img = tex.get(src)
    if img is None:
        return None
    _w, _h, px, _mean = img
    lum = 0.299 * px[:, :, 0] + 0.587 * px[:, :, 1] + 0.114 * px[:, :, 2]
    # The lens background is a dark teal pane; key it out so only the
    # projected ring/dot/glow survives, as a real holographic reticle does.
    alpha = np.clip((lum - 58.0) * 2.2, 0, 255).astype(np.uint8)
    rgba = np.dstack([px, alpha])
    out = os.path.join(ROOT, "assets", "3D", "K93D_reticle.png")
    Image.fromarray(rgba, "RGBA").resize((128, 128), Image.LANCZOS).save(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", type=float, default=0.008,
                    help="vertex-cluster cell in metres (default 8 mm)")
    ap.add_argument("--scale", type=float, default=0.34)
    args = ap.parse_args()

    g, binbuf = _gltf(SRC)
    tex = _textures(g, binbuf)
    verts, tris0, focus = _scan(g, binbuf)
    trigger = focus.get("Curved_Trigger", [(0, 0, 0, 0)])[0]
    glass = focus.get("Optic_Reflex_Glass", [(0, 0.53, 0, 0)])[0]
    z0, y0 = trigger[2], trigger[1]

    def to_gun(p):
        return (p[0] * args.scale, (p[1] - y0) * args.scale,
                (p[2] - z0) * args.scale)

    verts = [to_gun(v) for v in verts]
    # face grain: the engine is flat-shaded, so per-material variation is what
    # keeps anodised metal / carbon polymer from reading as one grey slab.
    grain = {0: 0.09, 1: 0.06, 2: 0.09, 3: 0.16, 4: 0.14, 5: 0.20}
    tris = []
    for idx, mat, group, uv in tris0:
        if mat == 7:
            # The flat lens pane is replaced at runtime by the transparent
            # reticle sprite: an opaque teal slab is what made the optic read
            # fake in the flat-shaded renderer.
            continue
        col = _face_colour(g, tex, mat, uv)
        # deterministic per-face dither breaks flat fill bands on big slabs
        a, b, c = verts[idx[0]], verts[idx[1]], verts[idx[2]]
        h = (round((a[0] + b[0] + c[0]) * 5000) * 374761393
             + round((a[1] + b[1] + c[1]) * 5000) * 668265263
             + round((a[2] + b[2] + c[2]) * 5000) * 2147483647) & 0xFFFFFFFF
        h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
        h ^= h >> 16
        k = 0.94 + 0.12 * ((h & 0xFFFF) / 65535.0)
        k *= 1.0 + grain.get(mat, 0.08) * ((((h >> 16) & 0xFFFF) / 65535.0) * 2 - 1)
        col = tuple(min(255, max(0, int(v * k))) for v in col)
        tris.append((idx, mat, group, uv, col))

    out_v, out_f = _cluster(verts, tris, args.cell)
    mag = [i for i, f in enumerate(out_f) if f[2] == 1]
    zmax = max(v[2] for v in out_v)
    near = [v for v in out_v if v[2] > zmax - 0.004]
    muzzle = [0.0, sum(v[1] for v in near) / len(near), zmax]
    sight = [glass[0] * args.scale, (glass[1] - y0) * args.scale,
             (glass[2] - z0) * args.scale]
    glass_size = [glass[4] * args.scale, glass[5] * args.scale]
    reticle = _export_reticle(g, tex)

    data = {
        "schema": "ae.mesh/1",
        "id": "k93d",
        "verts": [[round(c, 5) for c in v] for v in out_v],
        "faces": [[f[0], f[1]] for f in out_f],
        "tris": len(out_f),
        "source": os.path.basename(SRC),
        "meta": {
            "scale": args.scale,
            "cell_m": args.cell,
            "muzzle": [round(c, 5) for c in muzzle],
            "sight": [round(c, 5) for c in sight],
            "glass_size": [round(c, 5) for c in glass_size],
            "mag_faces": mag,
            "raw_tris": len(tris0),
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    print("AE IMPORT K93D: %d raw tris -> %d faces / %d verts  (cell %.4f)"
          % (len(tris0), len(out_f), len(out_v), args.cell))
    print("  muzzle", [round(c, 3) for c in muzzle],
          " sight", [round(c, 3) for c in sight], " mag faces", len(mag))
    if reticle:
        print("  reticle", os.path.relpath(reticle, ROOT))
    print("  ->", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
