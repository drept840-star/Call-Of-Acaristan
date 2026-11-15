#!/usr/bin/env python3
"""AE IMPORT TELEPHONE - Retardovici's rotary phone in M8 Chase
(assets/3D/telephone-base-balanced-jet.glb and
assets/3D/telephone-handset-balanced-jet.glb).

    python tools/ae_import_telephone.py

Reuses the GLB reader of tools/ae_import_k93d.py. Converts both GLBs into
``ae.mesh/1`` assets in metre scale:
  - telephone_base.mesh.json     grounded at y=0, dial +z, rear cord -z
  - telephone_handset.mesh.json  canonical grip frame: origin at handle center,
                                 +x earpiece, -x mouthpiece/collar, +y spine,
                                 -y acoustic grills
"""
import io
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ae_import_k93d as K  # noqa: E402

ROOT = K.ROOT
MESHES_DIR = os.path.join(ROOT, "src", "game", "content", "meshes")
BASE_SRC = os.path.join(ROOT, "assets", "3D", "telephone-base-balanced-jet.glb")
HANDSET_SRC = os.path.join(ROOT, "assets", "3D", "telephone-handset-balanced-jet.glb")


def _srgb(c):
    return round(255 * (12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055))


def _load_textures(g, binbuf):
    tex = K._textures(g, binbuf)
    if tex or not g.get("images"):
        return tex
    try:
        import numpy as np
        import pygame
    except Exception:
        return tex
    out = {}
    for i, img in enumerate(g.get("images", [])):
        bv = g["bufferViews"][img["bufferView"]]
        off = bv.get("byteOffset", 0)
        data = binbuf[off:off + bv["byteLength"]]
        surf = pygame.image.load(io.BytesIO(data))
        arr = pygame.surfarray.array3d(surf).swapaxes(0, 1)
        lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        out[i] = (surf.get_width(), surf.get_height(), arr.astype(np.uint8), max(1.0, float(lum.mean())))
    return out


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(v):
    n = math.sqrt(_dot(v, v)) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _grain(verts, idx, amp):
    a, b, c = verts[idx[0]], verts[idx[1]], verts[idx[2]]
    h = (
        round((a[0] + b[0] + c[0]) * 5000) * 374761393
        + round((a[1] + b[1] + c[1]) * 5000) * 668265263
        + round((a[2] + b[2] + c[2]) * 5000) * 2147483647
    ) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    return 1.0 + amp * ((((h >> 16) & 0xFFFF) / 65535.0) * 2.0 - 1.0)


def _scan_named(g, binbuf):
    """World-space triangles with node name and interpolated UV triple."""
    verts, tris, node_mats = [], [], {}

    def walk(ni, m):
        nd = g["nodes"][ni]
        if "matrix" in nd:
            m = K._mul(m, nd["matrix"])
        elif any(k in nd for k in ("translation", "rotation", "scale")):
            m = K._mul(m, K._trs(nd))
        name = nd.get("name", "")
        if "mesh" in nd:
            node_mats[name] = m
            for pr in g["meshes"][nd["mesh"]]["primitives"]:
                base = len(verts)
                pos = K._acc(g, binbuf, pr["attributes"]["POSITION"])
                verts.extend(K._xf(m, p) for p in pos)
                idx = (
                    K._acc(g, binbuf, pr["indices"])
                    if "indices" in pr
                    else [(k,) for k in range(len(pos))]
                )
                uv = (
                    K._acc(g, binbuf, pr["attributes"]["TEXCOORD_0"])
                    if "TEXCOORD_0" in pr["attributes"]
                    else None
                )
                mat_id = pr.get("material", 0)
                for k in range(0, len(idx) - 2, 3):
                    a, b, c = idx[k][0], idx[k + 1][0], idx[k + 2][0]
                    uv_tri = None
                    if uv is not None and max(a, b, c) < len(uv):
                        uv_tri = (uv[a], uv[b], uv[c])
                    tris.append(((base + a, base + b, base + c), mat_id, name, uv_tri))
        for ch in nd.get("children", []):
            walk(ch, m)

    for ni in g["scenes"][0]["nodes"]:
        walk(ni, K.I4)
    return verts, tris, node_mats


def _tri_colour(g, tex, mat_id, node_name, uv_tri, verts, idx):
    mat = g.get("materials", [{}])[mat_id] if mat_id < len(g.get("materials", [])) else {}
    pbr = mat.get("pbrMetallicRoughness", {})
    factor = pbr.get("baseColorFactor", [1.0, 1.0, 1.0, 1.0])
    if len(factor) >= 4 and factor[3] < 0.5:
        return None
    rgb = [_srgb(c) for c in factor[:3]]
    ref = pbr.get("baseColorTexture")
    if ref is not None and uv_tri is not None and tex:
        src = g.get("textures", [])[ref["index"]].get("source")
        image = tex.get(src)
        if image is not None:
            w, h, px, _ = image
            tf = ref.get("extensions", {}).get("KHR_texture_transform", {})
            sc = tf.get("scale", [1.0, 1.0])
            off = tf.get("offset", [0.0, 0.0])
            uc = (uv_tri[0][0] + uv_tri[1][0] + uv_tri[2][0]) / 3.0
            vc = (uv_tri[0][1] + uv_tri[1][1] + uv_tri[2][1]) / 3.0
            samples = [(uc, vc)] + [
                (0.6 * uc + 0.4 * uv_tri[i][0], 0.6 * vc + 0.4 * uv_tri[i][1])
                for i in range(3)
            ]
            acc = [0.0, 0.0, 0.0]
            for su, sv in samples:
                u = (su * sc[0] + off[0]) % 1.0
                v = (sv * sc[1] + off[1]) % 1.0
                x = min(w - 1, max(0, int(u * w)))
                y = min(h - 1, max(0, int(v * h)))
                acc[0] += float(px[y, x, 0]) * factor[0]
                acc[1] += float(px[y, x, 1]) * factor[1]
                acc[2] += float(px[y, x, 2]) * factor[2]
            rgb = [round(c / len(samples)) for c in acc]
    # Lift dark Bakelite slightly so bevels catch light in the night command room.
    luma = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    if luma < 45 and "Dial" not in node_name and "Grill" not in node_name:
        if max(rgb) >= 28:
            rgb = [int(c * 1.24 + 2) for c in rgb]
        else:
            rgb = [max(20, int(c * 1.25)) for c in rgb]
    k = _grain(verts, idx, 0.055 if luma < 60 else 0.03)
    return tuple(max(16, min(236, int(c * k))) for c in rgb)


def _cluster_keep_order(verts, tris, cell, budget=1400):
    while True:
        out_v, out_f = K._cluster(verts, tris, cell)
        if len(out_f) <= budget or cell >= 0.01:
            break
        cell *= 1.25
    used = sorted({i for f in out_f for i in f[0]})
    remap = {old: new for new, old in enumerate(used)}
    final_v = [[round(out_v[i][0], 6), round(out_v[i][1], 6), round(out_v[i][2], 6)] for i in used]
    faces = [[[remap[i] for i in idx], col] for idx, col, _grp in out_f]
    return final_v, faces, cell


def _write_mesh(asset_id, src_name, verts, faces, meta):
    os.makedirs(MESHES_DIR, exist_ok=True)
    out_path = os.path.join(MESHES_DIR, f"{asset_id}.mesh.json")
    data = {
        "schema": "ae.mesh/1",
        "id": asset_id,
        "verts": verts,
        "faces": faces,
        "tris": len(faces),
        "source": src_name,
        "meta": meta,
    }
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    return out_path


def import_base(cell=0.001):
    g, binbuf = K._gltf(BASE_SRC)
    tex = _load_textures(g, binbuf)
    verts, raw, _nm = _scan_named(g, binbuf)

    min_y = min(v[1] for v in verts)
    verts = [(v[0], v[1] - min_y, v[2]) for v in verts]

    body_pts = [
        verts[i]
        for idx, _m, name, _uv in raw
        if "Base_Bakelite_Body" in name
        for i in idx
    ]
    saddle_pts = [
        v for v in body_pts
        if 0.031 <= abs(v[0]) <= 0.043 and -0.046 <= v[2] <= -0.022 and v[1] > 0.088
    ]
    saddle_y = min(v[1] for v in saddle_pts) if saddle_pts else 0.095
    cradle_z = (
        0.5 * (min(v[2] for v in saddle_pts) + max(v[2] for v in saddle_pts))
        if saddle_pts
        else -0.034
    )
    horn_top_y = max(v[1] for v in body_pts) if body_pts else 0.114

    def priority(item):
        _idx, _mat, name, _uv = item
        if "Dial_Number_Faceplate" in name:
            return 0
        if "Chrome" in name or "Switchhook" in name:
            return 1
        if "Cable" in name or "Plug" in name:
            return 2
        return 3

    tris = []
    for idx, mat_id, name, uv_tri in sorted(raw, key=priority):
        col = _tri_colour(g, tex, mat_id, name, uv_tri, verts, idx)
        if col is None:
            continue
        tris.append((idx, mat_id, 0, None, col))

    out_v, out_f, used_cell = _cluster_keep_order(verts, tris, cell)
    meta = {
        "cell_m": round(used_cell, 5),
        "raw_tris": len(raw),
        "cradle_saddle_y": round(saddle_y, 5),
        "cradle_z": round(cradle_z, 5),
        "horn_top_y": round(horn_top_y, 5),
        "cord_jack": [0.060, 0.022, -0.025],
    }
    path = _write_mesh("telephone_base", os.path.basename(BASE_SRC), out_v, out_f, meta)
    print(
        "AE IMPORT TELEPHONE BASE: %d raw -> %d faces / %d verts (saddle_y=%.4f z=%.4f) -> %s"
        % (len(raw), len(out_f), len(out_v), saddle_y, cradle_z, os.path.relpath(path, ROOT))
    )


def import_handset(cell=0.001):
    g, binbuf = K._gltf(HANDSET_SRC)
    tex = _load_textures(g, binbuf)
    verts, raw, node_mats = _scan_named(g, binbuf)

    m_body = node_mats.get("Handset_Bakelite_Body", K.I4)
    x_ax = _norm((m_body[0], m_body[1], m_body[2]))
    y_ax = _norm((m_body[4], m_body[5], m_body[6]))

    def centroid(substr):
        pts = [verts[i] for idx, _m, name, _uv in raw if substr in name for i in idx]
        if not pts:
            return (0.0, 0.0, 0.0)
        n = float(len(pts))
        return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n, sum(p[2] for p in pts) / n)

    body_c = centroid("Handset_Bakelite_Body")
    collar_c = centroid("Handset_Cord_Collar")
    grill_c = centroid("Handset_Acoustic_Grills")

    if _dot(collar_c, x_ax) > _dot(body_c, x_ax):
        x_ax = (-x_ax[0], -x_ax[1], -x_ax[2])
    if _dot(grill_c, y_ax) > _dot(body_c, y_ax):
        y_ax = (-y_ax[0], -y_ax[1], -y_ax[2])
    z_ax = _norm(_cross(x_ax, y_ax))
    y_ax = _norm(_cross(z_ax, x_ax))

    proj = [(_dot(v, x_ax), _dot(v, y_ax), _dot(v, z_ax)) for v in verts]

    grill_pts = [
        proj[i]
        for idx, _m, name, _uv in raw
        if "Handset_Acoustic_Grills" in name
        for i in idx
    ]
    x_mid_0 = 0.5 * (min(v[0] for v in grill_pts) + max(v[0] for v in grill_pts))

    body_proj = [
        proj[i]
        for idx, _m, name, _uv in raw
        if "Handset_Bakelite_Body" in name
        for i in idx
    ]
    handle_pts = [v for v in body_proj if abs(v[0] - x_mid_0) < 0.025]
    y_mid_0 = 0.5 * (min(v[1] for v in handle_pts) + max(v[1] for v in handle_pts))
    z_mid_0 = 0.5 * (min(v[2] for v in handle_pts) + max(v[2] for v in handle_pts))

    canon = [(v[0] - x_mid_0, v[1] - y_mid_0, v[2] - z_mid_0) for v in proj]

    def shifted_pts(substr, pred=None):
        pts = [canon[i] for idx, _m, name, _uv in raw if substr in name for i in idx]
        if pred is not None:
            pts = [p for p in pts if pred(p)]
        n = float(len(pts)) or 1.0
        return pts, (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n, sum(p[2] for p in pts) / n)

    _, ear_grill = shifted_pts("Handset_Acoustic_Grills", lambda p: p[0] > 0.0)
    _, mouth_grill = shifted_pts("Handset_Acoustic_Grills", lambda p: p[0] < 0.0)
    _, cord_collar = shifted_pts("Handset_Cord_Collar")
    h_pts, _ = shifted_pts("Handset_Bakelite_Body", lambda p: abs(p[0]) < 0.025)
    saddle_pts, _ = shifted_pts("Handset_Bakelite_Body", lambda p: 0.031 <= abs(p[0]) <= 0.043)

    handle_bounds_yz = [
        round(min(p[1] for p in h_pts), 5),
        round(max(p[1] for p in h_pts), 5),
        round(min(p[2] for p in h_pts), 5),
        round(max(p[2] for p in h_pts), 5),
    ]
    cradle_rest_y = min(p[1] for p in saddle_pts) if saddle_pts else handle_bounds_yz[0]

    def priority(item):
        _idx, _mat, name, _uv = item
        if "Grill" in name:
            return 0
        if "Collar" in name:
            return 1
        return 2

    tris = []
    for idx, mat_id, name, uv_tri in sorted(raw, key=priority):
        col = _tri_colour(g, tex, mat_id, name, uv_tri, canon, idx)
        if col is None:
            continue
        tris.append((idx, mat_id, 0, None, col))

    out_v, out_f, used_cell = _cluster_keep_order(canon, tris, cell)
    meta = {
        "cell_m": round(used_cell, 5),
        "raw_tris": len(raw),
        "ear_grill": [round(c, 5) for c in ear_grill],
        "mouth_grill": [round(c, 5) for c in mouth_grill],
        "cord_collar": [round(c, 5) for c in cord_collar],
        "handle_bounds_yz": handle_bounds_yz,
        "cradle_rest_y": round(cradle_rest_y, 5),
    }
    path = _write_mesh("telephone_handset", os.path.basename(HANDSET_SRC), out_v, out_f, meta)
    print(
        "AE IMPORT TELEPHONE HANDSET: %d raw -> %d faces / %d verts "
        "(ear=%s mouth=%s cradle_rest_y=%.4f) -> %s"
        % (
            len(raw), len(out_f), len(out_v),
            [round(c, 4) for c in ear_grill],
            [round(c, 4) for c in mouth_grill],
            cradle_rest_y,
            os.path.relpath(path, ROOT),
        )
    )


def main():
    import_base()
    import_handset()


if __name__ == "__main__":
    main()