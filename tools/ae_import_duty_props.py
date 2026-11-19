#!/usr/bin/env python3
"""AE IMPORT DUTY PROPS - bake unused GLBs in assets/3D/ for Mission 8 Duty.

    python tools/ae_import_duty_props.py

Produces:
    src/game/content/meshes/moneystack.mesh.json        (prop, 3-item faces)
    src/game/content/meshes/ammo_crate.mesh.json        (prop, 3-item faces)
    src/game/content/meshes/tactical_lmg.mesh.json      (weapon, 2-item faces + meta)
    src/game/content/meshes/suppressed_pistol.mesh.json (weapon, 2-item faces + meta)
"""
import io
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ae_import_k93d as K  # noqa: E402

ROOT = K.ROOT
MESHES_OUT = os.path.join(ROOT, "src", "game", "content", "meshes")


def _srgb(c):
    return round(255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055))


def _flat_colour(g, material):
    pbr = g["materials"][material].get("pbrMetallicRoughness", {})
    factor = pbr.get("baseColorFactor", [0.6, 0.6, 0.6, 1.0])
    rgb = [_srgb(max(0.0, min(1.0, c))) for c in factor[:3]]
    return tuple(max(12, min(240, c)) for c in rgb)


_GLYPHS = {
    "A": ((0, 0, 1, 4), (2, 0, 1, 4), (0, 4, 3, 1), (1, 2, 1, 1)),
    "M": ((0, 0, 1, 5), (4, 0, 1, 5), (1, 3, 1, 1), (2, 2, 1, 1), (3, 3, 1, 1)),
    "O": ((0, 1, 1, 3), (2, 1, 1, 3), (1, 0, 1, 1), (1, 4, 1, 1)),
}


def _is_alpha_decal(g, buf, mat):
    m = g["materials"][mat]
    if m.get("alphaMode") in ("BLEND", "MASK"):
        return True
    btex = m.get("pbrMetallicRoughness", {}).get("baseColorTexture")
    if not btex:
        return False
    img_idx = g.get("textures", [])[btex["index"]].get("source")
    if img_idx is None:
        return False
    img = g.get("images", [])[img_idx]
    if "bufferView" not in img:
        return False
    bv = g["bufferViews"][img["bufferView"]]
    off = bv.get("byteOffset", 0)
    raw = buf[off:off + bv["byteLength"]]
    try:
        import pygame
        surf = pygame.image.load(io.BytesIO(raw))
        if surf.get_masks()[3] or (surf.get_flags() & pygame.SRCALPHA):
            arr = pygame.surfarray.array_alpha(surf)
            return int(arr.min()) < 250
        return False
    except Exception:
        return len(raw) > 26 and raw[:4] == b"\x89PNG" and (raw[25] in (4, 6) or b"tRNS" in raw[:4096])


def _stencil_ammo_faces(decal_tris, verts, floor, col=(214, 206, 188)):
    planes = {}
    for idx in decal_tris:
        pts = [verts[i] for i in idx]
        xs, ys, zs = [p[0] for p in pts], [p[1] - floor for p in pts], [p[2] for p in pts]
        dx, dy, dz = max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)
        if dz < 0.01:
            key = ("z", round((min(zs) + max(zs)) * 0.5, 3))
        elif dy < 0.01:
            key = ("y", round((min(ys) + max(ys)) * 0.5, 3))
        else:
            continue
        planes.setdefault(key, []).extend((p[0], p[1] - floor, p[2]) for p in pts)
    out_v, out_f = [], []
    for (axis, _), pts in planes.items():
        x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
        y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
        z0, z1 = min(p[2] for p in pts), max(p[2] for p in pts)
        cx = (x0 + x1) * 0.5
        if axis == "z":
            z, cy, w, h = (z0 + z1) * 0.5, y0 + (y1 - y0) * 0.62, (x1 - x0) * 0.66, (y1 - y0) * 0.34
            sx = 1.0 if z < 0.0 else -1.0
            pt = lambda gx, gy: [round(cx + (gx / 19.0 - 0.5) * w * sx, 6), round(cy + (gy / 5.0 - 0.5) * h, 6), round(z, 6)]
        else:
            y, cz, w, h = (y0 + y1) * 0.5, z0 + (z1 - z0) * 0.62, (x1 - x0) * 0.66, (z1 - z0) * 0.34
            pt = lambda gx, gy: [round(cx + (gx / 19.0 - 0.5) * w, 6), round(y, 6), round(cz + (gy / 5.0 - 0.5) * h, 6)]
        ox = 0
        for ch in "AMMO":
            gw = 5 if ch == "M" else 3
            for gx, gy, rw, rh in _GLYPHS[ch]:
                i = len(out_v)
                out_v.extend([pt(ox + gx, gy), pt(ox + gx + rw, gy), pt(ox + gx + rw, gy + rh), pt(ox + gx, gy + rh)])
                out_f.append(([i, i + 1, i + 2], list(col), 0))
                out_f.append(([i, i + 2, i + 3], list(col), 0))
            ox += gw + 1
    return out_v, out_f


def _write_mesh(ref, data):
    path = os.path.join(MESHES_OUT, f"{ref}.mesh.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    print("AE IMPORT DUTY: %s: %d -> %d faces (%d verts)"
          % (ref, data["meta"]["raw_tris"], data["tris"], len(data["verts"])))


def _build_prop(ref, src_name, height_m, cell, budget):
    path = os.path.join(ROOT, "assets", "3D", src_name)
    g, buf = K._gltf(path)
    verts, raw, _ = K._scan(g, buf)
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    sc = height_m / max(1e-5, hi[1] - lo[1])
    origin = ((lo[0] + hi[0]) * 0.5, lo[1], (lo[2] + hi[2]) * 0.5)
    sverts = [tuple((v[i] - origin[i]) * sc for i in range(3)) for v in verts]
    alpha_mats = {i for i in range(len(g.get("materials", ()))) if _is_alpha_decal(g, buf, i)}
    decal_tris = [idx for idx, mat, _, _ in raw if mat in alpha_mats]
    tris = [(idx, mat, 0, None, _flat_colour(g, mat)) for idx, mat, _, _ in raw if mat not in alpha_mats]
    out_v, out_f = K._cluster(sverts, tris, cell)
    while len(out_f) > budget:
        cell *= 1.15
        out_v, out_f = K._cluster(sverts, tris, cell)
    used = sorted({i for f in out_f for i in f[0]})
    remap = {old: new for new, old in enumerate(used)}
    floor = min(out_v[i][1] for i in used)
    final_v = [[round(out_v[i][0], 6), round(out_v[i][1] - floor, 6), round(out_v[i][2], 6)] for i in used]
    faces = [[[remap[i] for i in idx], col, group] for idx, col, group in out_f]
    if ref == "ammo_crate" and decal_tris:
        sv, sf = _stencil_ammo_faces(decal_tris, sverts, floor)
        base = len(final_v)
        final_v.extend(sv)
        faces.extend([[[base + i for i in idx], col, grp] for idx, col, grp in sf])
    assert all(math.isfinite(c) for v in final_v for c in v)
    return {
        "schema": "ae.mesh/1",
        "id": ref,
        "verts": final_v,
        "faces": faces,
        "tris": len(faces),
        "source": src_name,
        "meta": {"height_m": height_m, "cell_m": round(cell, 6), "raw_tris": len(raw), "screen_group": None},
    }


def _muzzle_sign_x(verts):
    """Return +1 if +x is the thinner barrel tip, -1 if -x is."""
    xs = [v[0] for v in verts]
    x0, x1 = min(xs), max(xs)
    band = max(1e-4, (x1 - x0) * 0.12)
    lo_y = [v[1] for v in verts if v[0] <= x0 + band]
    hi_y = [v[1] for v in verts if v[0] >= x1 - band]
    span_lo = (max(lo_y) - min(lo_y)) if lo_y else 999.0
    span_hi = (max(hi_y) - min(hi_y)) if hi_y else 999.0
    return 1.0 if span_hi <= span_lo else -1.0


def _build_weapon(ref, src_name, length_m, grip_frac_x, grip_frac_y, cell, budget):
    path = os.path.join(ROOT, "assets", "3D", src_name)
    g, buf = K._gltf(path)
    verts, raw, _ = K._scan(g, buf)
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    span_x = max(1e-5, hi[0] - lo[0])
    span_y = max(1e-5, hi[1] - lo[1])
    sgn = _muzzle_sign_x(verts)
    rear_x = lo[0] if sgn > 0 else hi[0]
    grip_x = rear_x + sgn * grip_frac_x * span_x
    grip_y = lo[1] + grip_frac_y * span_y
    s = length_m / span_x

    def to_gun(x, y, z):
        return (-sgn * z * s, (y - grip_y) * s, sgn * (x - grip_x) * s)

    gverts = [to_gun(*v) for v in verts]
    tris = [(idx, mat, group, None, _flat_colour(g, mat)) for idx, mat, group, _ in raw]
    out_v, out_f = K._cluster(gverts, tris, cell)
    while len(out_f) > budget:
        cell *= 1.15
        out_v, out_f = K._cluster(gverts, tris, cell)
    used = sorted({i for f in out_f for i in f[0]})
    remap = {old: new for new, old in enumerate(used)}
    final_v = [[round(out_v[i][0], 5), round(out_v[i][1], 5), round(out_v[i][2], 5)] for i in used]
    faces = [[[remap[i] for i in idx], col] for idx, col, _group in out_f]
    zmax = max(v[2] for v in final_v)
    near = [v for v in final_v if v[2] > zmax - 0.015]
    muzzle = [0.0, round(sum(v[1] for v in near) / max(1, len(near)), 4), round(zmax, 4)]
    assert all(math.isfinite(c) for v in final_v for c in v)
    return {
        "schema": "ae.mesh/1",
        "id": ref,
        "verts": final_v,
        "faces": faces,
        "tris": len(faces),
        "source": src_name,
        "meta": {"length_m": length_m, "cell_m": round(cell, 6), "muzzle": muzzle, "raw_tris": len(raw)},
    }


def main():
    os.makedirs(MESHES_OUT, exist_ok=True)
    _write_mesh("moneystack", _build_prop("moneystack", "moneystack.glb", 0.09, 0.002, 600))
    _write_mesh("ammo_crate", _build_prop("ammo_crate", "farm-ammo-crate-bare.glb", 0.46, 0.006, 1000))
    _write_mesh("tactical_lmg", _build_weapon("tactical_lmg", "tactical_lmg(white).glb",
                                              1.05, 0.30, 0.50, 0.005, 1800))
    _write_mesh("suppressed_pistol", _build_weapon("suppressed_pistol", "Suppressed_Pistol.glb",
                                                   0.32, 0.18, 0.62, 0.003, 1400))


if __name__ == "__main__":
    main()
