"""Sprite -> wall decal mesh for the M5 3D cutscenes.

A baked ``art.m5`` sprite is turned into real coplanar quads (one per merged
rectangle of equal colour) instead of a screen-space texture pass, so a
poster is lit, fogged and depth-sorted like any other face in BOTH the
software painter and the GL backend - characters walking in front of it
occlude it correctly (``m5mid3d._map_quad`` cannot do that).

Meshes are built once per placement and cached; per frame it is one
``add_dynamic`` call. Returns False when the sprite is unavailable so the
caller can draw its legacy flat box instead.
"""
from art import m5 as _art

# viewer side -> (right, up) in world space; "-z" = the usual front wall
_AXES = {
    "-z": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    "+z": ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    "+x": ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
    "-x": ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
}
_MESH = {}
_RECTS = {}


def _rects(surf, q=4, alpha_min=100):
    """Greedy merge: horizontal runs of equal (quantised) colour, then stack
    identical runs of consecutive rows. -> [(x0, y0, x1, y1, rgb)] in px."""
    w, h = surf.get_size()
    open_ = {}
    out = []
    for y in range(h + 1):
        runs = {}
        if y < h:
            x = 0
            while x < w:
                r, g, b, a = surf.get_at((x, y))
                if a < alpha_min:
                    x += 1
                    continue
                c = (r // q * q, g // q * q, b // q * q)
                x1 = x + 1
                while x1 < w:
                    r2, g2, b2, a2 = surf.get_at((x1, y))
                    if a2 < alpha_min or (r2 // q * q, g2 // q * q, b2 // q * q) != c:
                        break
                    x1 += 1
                runs[(x, x1, c)] = True
                x = x1
        nxt = {}
        for key, y0 in open_.items():
            if key in runs:
                nxt[key] = y0
            else:
                out.append((key[0], y0, key[1], y, key[2]))
        for key in runs:
            if key not in nxt:
                nxt[key] = y
        open_ = nxt
    return out


def rect_count(name, variant=0):
    s = _art.get(name, variant)
    return len(_rects(s)) if s is not None else 0


def add(r, name, variant, center, size, facing="-z", bias=0.8, emissive=False, layer=2):
    """Pin sprite ``name``/``variant`` on a wall. ``center`` = world centre of
    the decal plane, ``size`` = (w, h) metres, ``facing`` = the side the
    viewer stands on. ``emissive``: False, True, or a luma threshold (0-255)
    above which a texel is self-lit (sign bulbs)."""
    key = (name, variant, center, size, facing, emissive, layer)
    m = _MESH.get(key)
    if m is None:
        surf = _art.get(name, variant)
        if surf is None:
            return False
        rk = (name, variant)
        rects = _RECTS.get(rk)
        if rects is None:
            rects = _RECTS[rk] = _rects(surf)
        sw, sh = surf.get_size()
        (rx, ry, rz), (ux, uy, uz) = _AXES[facing]
        cx, cy, cz = center
        w, h = size
        verts, faces = [], []

        def p(px, py):
            a = px / sw - 0.5
            b = 0.5 - py / sh
            return (cx + rx * a * w + ux * b * h, cy + ry * a * w + uy * b * h,
                    cz + rz * a * w + uz * b * h)

        for x0, y0, x1, y1, col in rects:
            if emissive is True:
                em = True
            elif emissive is False:
                em = False
            else:
                em = (col[0] * 299 + col[1] * 587 + col[2] * 114) // 1000 >= emissive
            base = len(verts)
            # same winding as engine3d.core.box "front": (a0,b0) (a0,b1) (a1,b1) (a1,b0)
            verts += [p(x0, y1), p(x0, y0), p(x1, y0), p(x1, y1)]
            faces.append(((base, base + 1, base + 2, base + 3), col, layer, False, None, em))
        m = _MESH[key] = (verts, faces)
    r.add_dynamic(m[0], m[1], bias=-abs(bias))
    return True
