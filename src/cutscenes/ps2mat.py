"""ps2mat.py - PS2 pixel textures for sets authored in flat colour.

The M6 PS2 look is half frame (0.64 buffer, ``m6fx3d.grade_cine``, crisp
present) and half surfaces: real pixel textures from ``assets/tex3d``.  The
M5 sets were built in plain colours, so ``faces`` gives their larger faces a
tinted texture picked from the colour: grey -> concrete (steel on small
props), brown -> planks on floors and grain on deep-brown walls (beige walls
are plaster: concrete), red -> brick on big walls and rust elsewhere.  A
tinted texture keeps the authored colour and adds only its light and dark, so
palette and exposure stay put.  Emissive, small and
saturated cool faces (water, glass, screens, paint) stay flat, and so do the
blocky characters, which never pass through here.  GL only: the software
backend draws the colour, as before.
"""
import colorsys

MIN_AREA = 0.09           # m^2: below this a face is a prop detail, keep it flat
BIG = 1.0                 # m^2: walls this size take brick instead of rust

_kind = {}                # rgb -> colour class (None = stays flat)
_texs = {}                # (name, rgb) -> Tex


def _cross(verts, idx):
    """-> (area, |normal y| share) of a planar polygon.  A quad's area is half
    its diagonals' cross product; anything else is fanned from vertex 0."""
    if len(idx) == 4:
        a, b, c, d = verts[idx[0]], verts[idx[1]], verts[idx[2]], verts[idx[3]]
        ux, uy, uz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        vx, vy, vz = d[0] - b[0], d[1] - b[1], d[2] - b[2]
        ax, ay, az = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    else:
        ax = ay = az = 0.0
        p0 = verts[idx[0]]
        for i in range(1, len(idx) - 1):
            a, b = verts[idx[i]], verts[idx[i + 1]]
            ux, uy, uz = a[0] - p0[0], a[1] - p0[1], a[2] - p0[2]
            vx, vy, vz = b[0] - p0[0], b[1] - p0[1], b[2] - p0[2]
            ax += uy * vz - uz * vy
            ay += uz * vx - ux * vz
            az += ux * vy - uy * vx
    n = (ax * ax + ay * ay + az * az) ** 0.5
    return 0.5 * n, (abs(ay) / n if n else 0.0)


def _class(col):
    key = (col[0], col[1], col[2])
    kind = _kind.get(key, 0)
    if kind == 0:
        h, s, _v = colorsys.rgb_to_hsv(col[0] / 255.0, col[1] / 255.0, col[2] / 255.0)
        h *= 360.0
        if s < 0.22:
            kind = "grey"
        elif 10.0 <= h < 50.0:
            kind = "wood" if s >= 0.4 else "beige"
        elif (h < 10.0 or h >= 340.0) and s >= 0.3:
            kind = "red"
        else:
            kind = None
        _kind[key] = kind
    return kind


def _material(kind, area, flat):
    big = area >= BIG
    if kind == "grey":
        return "concrete" if flat or big else "steel"
    if kind == "wood":
        return "crate" if flat else "sleeper"
    if kind == "beige":                       # floors are boards, walls plaster
        return "crate" if flat else "concrete"
    return "brick" if not flat and big else "rust"


def faces(verts, faces):
    """Mesh faces ``(idx, col, layer, double, emissive)`` -> the same list with
    eligible flat colours swapped for tinted ``engine3d.textures.Tex``."""
    from engine3d.textures import Tex, tex  # lazy: numpy stack
    out = []
    for f in faces:
        idx, col = f[0], f[1]
        kind = None if f[4] or isinstance(col, Tex) or len(idx) < 3 else _class(col)
        if kind is not None:
            area, ny = _cross(verts, idx)
            if area >= MIN_AREA:
                name = _material(kind, area, ny > 0.9)
                key = (name, col[0], col[1], col[2])
                t = _texs.get(key)
                if t is None:
                    t = _texs[key] = tex(name, like=col, tint=True)
                f = (idx, t) + tuple(f[2:])
        out.append(f)
    return out


def mesh(m):
    """A textured copy of Mesh ``m`` (cached set meshes stay untouched)."""
    return type(m)(m.verts, faces(m.verts, m.faces))
