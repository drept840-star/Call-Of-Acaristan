#!/usr/bin/env python3
"""Bake the six office/medical GLBs; no source model is loaded during play.

python tools/ae_import_workstation_props.py
Node transforms and embedded base-colour images are honoured. Screen faces
are tagged for procedural live displays; transparent CRT glare is omitted.
"""
import json
import math
import os

import ae_import_k93d as K

# id, source stem, target height (metres), clustering cell, face budget
ASSETS = (
    ("pc_zarya", "soviet_pc_zarya_pk86", 0.165, 0.009, 2200),
    ("pc_tall", "soviet_pc_tall", 0.52, 0.008, 1400),
    ("monitor_crt", "low_poly_crt_monitor", 0.46, 0.002, 500),
    ("monitor_lcd", "lowpoly_retro_lcd_monitor", 0.42, 0.002, 550),
    ("medkit", "low_poly_medkit", 0.30, 0.001, 250),
    ("pill_bottle", "low-poly-pill-bottle", 0.14, 0.0005, 400),
)
SCREEN_MATERIAL = {"monitor_crt": 3, "monitor_lcd": 2}


def _srgb(c):
    return round(255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055))


def _colour(g, textures, material, uv):
    pbr = g["materials"][material].get("pbrMetallicRoughness", {})
    factor = pbr.get("baseColorFactor", [1, 1, 1, 1])
    rgb = [_srgb(c) for c in factor[:3]]
    ref = pbr.get("baseColorTexture")
    if ref is not None and uv is not None:
        image = textures.get(g["textures"][ref["index"]]["source"])
        if image is not None:
            w, h, px, _ = image
            tf = ref.get("extensions", {}).get("KHR_texture_transform", {})
            scale, off = tf.get("scale", [1, 1]), tf.get("offset", [0, 0])
            u, v = [(uv[i] * scale[i] + off[i]) % 1 for i in (0, 1)]
            rgb = [round(int(c) * factor[i]) for i, c in enumerate(px[min(h - 1, int(v * h)), min(w - 1, int(u * w))])]
    return tuple(max(12, min(240, c)) for c in rgb)


def build(asset):
    ref, source, height, cell, budget = asset
    path = os.path.join(K.ROOT, "assets", "3D", source + ".glb")
    g, buf = K._gltf(path)
    verts, raw, _ = K._scan(g, buf)
    textures = K._textures(g, buf)
    if g.get("images") and not textures:
        raise RuntimeError("Pillow and numpy are required to bake embedded images")
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    sc = height / (hi[1] - lo[1])
    origin = ((lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2)
    verts = [tuple((v[i] - origin[i]) * sc for i in range(3)) for v in verts]
    tris = []
    for idx, mat, _, uv in raw:
        material = g["materials"][mat]
        alpha = material.get("pbrMetallicRoughness", {}).get("baseColorFactor", [1, 1, 1, 1])[3]
        if alpha < 0.5:
            continue  # flat opaque renderers must not turn glare into a white card
        screen = mat == SCREEN_MATERIAL.get(ref, -1)
        col = (8, 22, 18) if screen else _colour(g, textures, mat, uv)
        tris.append((idx, mat, int(screen), None, col))
    out_v, out_f = K._cluster(verts, tris, cell)
    # The Zarya has hundreds of tiny screws/ports. Increase the deterministic
    # clustering cell deliberately until it meets the scenery budget.
    while len(out_f) > budget:
        cell *= 1.15
        out_v, out_f = K._cluster(verts, tris, cell)
    # Remove isolated representatives and ground the resulting mesh exactly.
    used = sorted({i for f in out_f for i in f[0]})
    remap = {old: new for new, old in enumerate(used)}
    floor = min(out_v[i][1] for i in used)
    final_v = [[round(out_v[i][0], 6), round(out_v[i][1] - floor, 6), round(out_v[i][2], 6)] for i in used]
    faces = [[[remap[i] for i in idx], col, group] for idx, col, group in out_f]
    assert all(math.isfinite(c) for v in final_v for c in v)
    return {"schema": "ae.mesh/1", "id": ref, "verts": final_v, "faces": faces,
            "tris": len(faces), "source": source + ".glb",
            "meta": {"height_m": height, "cell_m": round(cell, 6),
                     "raw_tris": len(raw), "screen_group": 1 if ref in SCREEN_MATERIAL else None}}


def main():
    for asset in ASSETS:
        data = build(asset)
        path = os.path.join(K.ROOT, "src", "game", "content", "meshes", data["id"] + ".mesh.json")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, separators=(",", ":"))
            fh.write("\n")
        print("AE IMPORT PROPS: %s: %d -> %d faces" % (data["id"], data["meta"]["raw_tris"], data["tris"]))


if __name__ == "__main__":
    main()
