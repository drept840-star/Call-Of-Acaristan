#!/usr/bin/env python3
"""AE IMPORT KRAP VAN - the KRAP van (assets/3D/krap_van.glb).

    python tools/ae_import_krap_van.py

Reuses the GLB walker helpers from tools/ae_import_k93d.py.
Output: src/game/content/meshes/krap_van.mesh.json (ae.mesh/1).

Frame: +x = nose, +y = up, tyres on y = 0, centred on x, metres. The GLB is
right-handed (+z = starboard); the engine is left-handed, so z is negated and
the triangle winding swapped. With the nose pointing east, -z is the south
flank, the side a camera at -z looking +z sees.

Faces are [indices, rgb, group]:
    0 body        1 headlamp (emissive)   2 tail lamp (emissive)
    3 indicator   9 livery lettering (flat quads, layer above the flank)
    10..13        wheels FR, FL, RR, RL (meta.wheels gives each axle centre)
The three alpha-blended decal quads are not meshed. The two on the south flank
are rasterised into run-length quads (group 9) in the lettering's own colour.
"""
import io
import json
import os

import ae_import_k93d as K

ROOT = K.ROOT
SRC = os.path.join(ROOT, "assets", "3D", "krap_van.glb")
OUT = os.path.join(ROOT, "src", "game", "content", "meshes", "krap_van.mesh.json")

DECAL_MATS = (9, 10, 11)
DECAL_NODES = (174, 176)          # glTF nodes on the +z (south after flip) flank
WHEELS = {"FR": 10, "FL": 11, "RR": 12, "RL": 13}
CELL = 0.014                      # lettering raster cell, metres
LETTER_LIFT = 0.012               # lettering floats this far off the flank


def _walk(g, binbuf):
    """-> [(world verts, indices, material, wheel name or None, node index)]."""
    out = []

    def go(ni, m, wheel):
        nd = g["nodes"][ni]
        if "matrix" in nd:
            m = K._mul(m, nd["matrix"])
        elif any(k in nd for k in ("translation", "rotation", "scale")):
            m = K._mul(m, K._trs(nd))
        name = nd.get("name") or ""
        if name.startswith("Wheel_"):
            wheel = name[6:]
        if "mesh" in nd:
            for pr in g["meshes"][nd["mesh"]]["primitives"]:
                pos = K._acc(g, binbuf, pr["attributes"]["POSITION"])
                idx = ([i[0] for i in K._acc(g, binbuf, pr["indices"])]
                       if "indices" in pr else list(range(len(pos))))
                out.append(([K._xf(m, p) for p in pos], idx,
                            pr.get("material", 0), wheel, ni))
        for ch in nd.get("children", []):
            go(ch, m, wheel)

    for ni in g["scenes"][0]["nodes"]:
        go(ni, K.I4, None)
    return out


def _dither(a, b, c):
    h = (round((a[0] + b[0] + c[0]) * 5000) * 374761393
         + round((a[1] + b[1] + c[1]) * 5000) * 668265263
         + round((a[2] + b[2] + c[2]) * 5000) * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    k = 0.96 + 0.08 * ((h & 0xFFFF) / 65535.0)
    return k * (1.0 + 0.04 * ((((h >> 16) & 0xFFFF) / 65535.0) * 2 - 1))


def _lettering(g, binbuf, node, to_out):
    """Decal quad -> run-length quads [(verts4, rgb)] on the flank plane."""
    from PIL import Image
    nd = g["nodes"][node]
    pr = g["meshes"][nd["mesh"]]["primitives"][0]
    pos = K._acc(g, binbuf, pr["attributes"]["POSITION"])
    w = max(p[0] for p in pos) - min(p[0] for p in pos)
    h = max(p[1] for p in pos) - min(p[1] for p in pos)
    tex = g["materials"][pr["material"]]["pbrMetallicRoughness"]["baseColorTexture"]["index"]
    img = g["images"][g["textures"][tex]["source"]]
    bv = g["bufferViews"][img["bufferView"]]
    off = bv.get("byteOffset", 0)
    im = Image.open(io.BytesIO(binbuf[off:off + bv["byteLength"]])).convert("RGBA")
    cols, rows = max(1, round(w / CELL)), max(1, round(h / CELL))
    im = im.resize((cols, rows), Image.BOX)
    px = im.load()
    t = nd["translation"]
    quads = []
    for r in range(rows):
        c = 0
        while c < cols:
            if px[c, r][3] < 128:
                c += 1
                continue
            c0 = c
            while c < cols and px[c, r][3] >= 128:
                c += 1
            rgb = tuple(int(sum(px[k, r][i] for k in range(c0, c)) / (c - c0)) for i in range(3))
            x0, x1 = t[0] - w / 2 + w * c0 / cols, t[0] - w / 2 + w * c / cols
            y1, y0 = t[1] + h / 2 - h * r / rows, t[1] + h / 2 - h * (r + 1) / rows
            z = t[2] + LETTER_LIFT
            quads.append(([to_out((x0, y0, z)), to_out((x1, y0, z)),
                           to_out((x1, y1, z)), to_out((x0, y1, z))], rgb))
    return quads


def main():
    g, binbuf = K._gltf(SRC)
    prims = _walk(g, binbuf)
    allv = [p for pv, *_ in prims for p in pv]
    y0 = min(p[1] for p in allv)
    cx = (min(p[0] for p in allv) + max(p[0] for p in allv)) / 2

    def to_out(p):
        return (p[0] - cx, p[1] - y0, -p[2])

    cols = []
    for m in g.get("materials", []):
        f = m.get("pbrMetallicRoughness", {}).get("baseColorFactor")
        # The factors are the authored hex colours (28/255 = 0.1098...), so
        # they are read as sRGB directly.
        cols.append(tuple(int(round(c * 255)) for c in f[:3]) if f else (128, 128, 128))

    verts, faces = [], []
    wheel_pts = {}
    for pv, idx, mat, wheel, _ni in prims:
        if mat in DECAL_MATS:
            continue
        ov = [to_out(p) for p in pv]
        base = len(verts)
        verts.extend(ov)
        for k in range(0, len(idx) - 2, 3):
            a, b, c = idx[k], idx[k + 1], idx[k + 2]
            cen = ((ov[a][0] + ov[b][0] + ov[c][0]) / 3, (ov[a][1] + ov[b][1] + ov[c][1]) / 3)
            if wheel in WHEELS:
                grp = WHEELS[wheel]
                wheel_pts.setdefault(wheel, []).extend((ov[a], ov[b], ov[c]))
            elif mat == 8 and cen[0] > 2.9 and cen[1] < 1.6:
                grp = 1
            elif mat == 6 and cen[0] < 0:
                grp = 2
            elif mat == 7:
                grp = 3
            else:
                grp = 0
            col = [min(255, max(0, int(v * _dither(ov[a], ov[b], ov[c])))) for v in cols[mat]]
            # z is mirrored, so swap two indices to keep the winding outward.
            faces.append([[base + a, base + c, base + b], col, grp])

    wheels = []
    for name, grp in WHEELS.items():
        pts = wheel_pts[name]
        wheels.append({"name": name, "group": grp,
                       "centre": [round((min(p[i] for p in pts) + max(p[i] for p in pts)) / 2, 4)
                                  for i in range(3)],
                       "radius": round((max(p[1] for p in pts) - min(p[1] for p in pts)) / 2, 4)})

    n_letters = 0
    try:
        for node in DECAL_NODES:
            for quad, rgb in _lettering(g, binbuf, node, to_out):
                base = len(verts)
                verts.extend(quad)
                # quad corners run left -> right on the -z flank seen from -z
                faces.append([[base, base + 1, base + 2, base + 3], list(rgb), 9])
                n_letters += 1
    except ImportError:
        print("AE IMPORT KRAP VAN: Pillow missing, lettering skipped")

    used = sorted({i for f in faces for i in f[0]})
    remap = {old: new for new, old in enumerate(used)}
    out_v = [[round(c, 4) for c in verts[i]] for i in used]
    out_f = [[[remap[i] for i in f[0]], f[1], f[2]] for f in faces]
    xs, ys, zs = ([v[i] for v in out_v] for i in range(3))
    data = {
        "schema": "ae.mesh/1", "id": "krap_van",
        "verts": out_v, "faces": out_f, "tris": len(out_f),
        "source": os.path.basename(SRC),
        "meta": {"bounds": [[round(min(a), 3), round(max(a), 3)] for a in (xs, ys, zs)],
                 "wheels": wheels,
                 "groups": {"1": "headlamp", "2": "tail lamp", "3": "indicator",
                            "9": "lettering", "10-13": "wheels"}},
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    print("AE IMPORT KRAP VAN: %d faces / %d verts (%d lettering quads), bounds %s"
          % (len(out_f), len(out_v), n_letters, data["meta"]["bounds"]))
    for w in wheels:
        print("  wheel", w["name"], w["centre"], "r", w["radius"])
    print("  ->", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
