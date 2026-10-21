"""Cyrillic signage for the Bloc: rooftop letters, boards, stars, billboards, banners.

Everything is built from axis-aligned boxes, one per pixel run, so a sign costs
one box per stroke rather than one per letter pixel. Signs are laid out in the
glyph grid of ``font`` and then walked across the face in metres; the facing
decides which axis the reading direction runs along, so the same text reads
left to right for anyone standing in front of it.
"""
from __future__ import annotations

from engine3d.core import box
from missions.m6 import palette3d as P

from .colours import only  # noqa: E402
from .colours import LETTER_CREAM, NEON_RED, PROP_RED, _hash, dim
from .font import GLYPH_H, GLYPHS, layout, width

# Unit vectors, indexed by facing: (u, v, w) = reading right, up, outward normal.
# The engine's screen-right is (fz, 0, -fx) for a view direction f, so a viewer
# facing a "+z" sign (looking down -z) reads it toward -x.
_FACES = {
    "+z": ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "-z": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, -1.0)),
    "+x": ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)),
    "-x": ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0)),
}

# 5-point star as runs (col, row, length) on a 9x9 grid, row 0 = top.
STAR_MASK = (
    (4, 0, 1),
    (3, 1, 3),
    (2, 2, 5),
    (1, 3, 7),
    (0, 4, 9),
    (1, 5, 2), (5, 5, 2),
    (1, 6, 2), (4, 6, 3),
    (0, 7, 3), (5, 7, 2),
    (0, 8, 2), (6, 8, 3),
)
STAR_W = 9


def _place(u, v, w, c, du, dv, dw):
    """Offset from ``c`` by ``du`` along reading, ``dv`` up and ``dw`` outward."""
    return (c[0] + u[0] * du + v[0] * dv + w[0] * dw,
            c[1] + u[1] * du + v[1] * dv + w[1] * dw,
            c[2] + u[2] * du + v[2] * dv + w[2] * dw)


def _slab(add, c, facing, du, dv, dw, su, sv, sw, col, emissive=False, seg=None,
          skip=()):
    """A box whose sizes are given along the face's reading, up and normal axes."""
    u, v, w = _FACES[facing]
    size = tuple(abs(u[i]) * su + abs(v[i]) * sv + abs(w[i]) * sw for i in range(3))
    add(box(size[0], size[1], size[2], col, center=_place(u, v, w, c, du, dv, dw),
            seg=seg, emissive=emissive, skip=skip))


def _cell_centre(col, row, total_cols):
    """Centre of a glyph-grid pixel, measured from the text block's centre."""
    return (col + 0.5 - total_cols / 2.0, (GLYPH_H / 2.0) - (row + 0.5))


def letters(add, text, center, facing, px=0.12, col=NEON_RED, emissive=True, depth=0.04):
    """Text as one box per run, centred on ``center`` with boxes proud of the face."""
    cols = width(text)
    if cols <= 0:
        return 0
    n = 0
    for c, r, length in layout(text):
        du, dv = _cell_centre(c + length / 2.0 - 0.5, r, cols)
        _slab(add, center, facing, du * px, dv * px, depth / 2.0,
              length * px, px, depth, col, emissive, skip=only(facing))
        n += 1
    return n


def board(add, text, center, facing, px=0.12, col=LETTER_CREAM, bg=PROP_RED, margin=2,
          frame=P.SLATE_DEEP, emissive=False):
    """A painted board with the letters on its front face; returns its (w, h)."""
    fw = 0.1
    bw = (width(text) + 2 * margin) * px
    bh = (GLYPH_H + 2 * margin) * px
    _slab(add, center, facing, 0.0, 0.0, 0.0, bw, bh, 0.08, bg)
    # 1-px frame: four strips laid over the board's edges.
    hw, hh = bw / 2.0 - px / 2.0, bh / 2.0 - px / 2.0
    _slab(add, center, facing, 0.0, hh, 0.0, bw, px, fw, frame)
    _slab(add, center, facing, 0.0, -hh, 0.0, bw, px, fw, frame)
    _slab(add, center, facing, -hw, 0.0, 0.0, px, bh - 2 * px, fw, frame)
    _slab(add, center, facing, hw, 0.0, 0.0, px, bh - 2 * px, fw, frame)
    u, v, w = _FACES[facing]
    letters(add, text, _place(u, v, w, center, 0.0, 0.0, 0.04), facing, px=px, col=col,
            emissive=emissive, depth=0.04)
    return bw, bh


def star(add, center, facing, size=1.0, col=NEON_RED, emissive=True):
    """A five-point star from the 9x9 mask, ``size`` metres wide. Returns boxes added."""
    px = size / STAR_W
    for c, r, length in STAR_MASK:
        du, dv = _cell_centre(c + length / 2.0 - 0.5, r, STAR_W)
        _slab(add, center, facing, du * px, dv * px, 0.0,
              length * px, px, 0.04, col, emissive)
    return len(STAR_MASK)


def billboard(add, lines, center_xz, facing, top=7.0, col=LETTER_CREAM, bg=PROP_RED,
              px=0.16):
    """Roadside propaganda billboard; returns the two lamp head positions."""
    u, v, w = _FACES[facing]
    cx, cz = center_xz
    lines = list(lines)[:2]
    margin = 3
    star_cols = 8
    text_w = max([width(t) for t in lines] or [0])
    bw = max(1, star_cols + text_w + 2 * margin) * px
    line_h = (GLYPH_H + 1) * px
    bh = line_h * len(lines) + 1 * px + 2 * px
    bm = (cx, top - bh / 2.0, cz)            # board centre on the ground point

    # Legs: two dark steel posts down to the ground.
    leg_h = top - bh * 0.2
    leg_y = leg_h / 2.0
    for side in (-1.0, 1.0):
        du = side * (bw / 2.0 - 0.5)
        p = (cx + u[0] * du, leg_y, cz + u[2] * du)
        add(box(0.3, leg_h, 0.3, (40, 44, 52), center=p))

    _slab(add, bm, facing, 0.0, 0.0, 0.0, bw, bh, 0.12, bg)
    left = -bw / 2.0 + margin * px + star_cols * px / 2.0
    star(add, _place(u, v, w, bm, left, 0.0, 0.06), facing, size=star_cols * px * 0.9,
         col=col, emissive=False)
    for i, text in enumerate(lines):
        dv = (bh / 2.0) - px - line_h * (i + 0.5)
        letters(add, text, _place(u, v, w, bm, margin * px, dv, 0.06), facing,
                px=px, col=col, emissive=False, depth=0.04)

    # Snow cap on the top edge, slightly proud of the board.
    _slab(add, bm, facing, 0.0, bh / 2.0 + 0.05, 0.0, bw + 0.1, 0.1, 0.2, P.SNOW)

    # Two lamp heads on short arms above the top edge.
    lamps = []
    for side in (-1.0, 1.0):
        du = side * (bw / 2.0 - 0.6)
        arm = _place(u, v, w, bm, du, bh / 2.0 + 0.15, 0.35)
        _slab(add, arm, facing, 0.0, 0.0, -0.1, 0.08, 0.08, 0.5, (40, 44, 52))
        head = _place(u, v, w, bm, du, bh / 2.0 + 0.2, 0.6)
        _slab(add, head, facing, 0.0, 0.0, 0.0, 0.3, 0.12, 0.25, P.SODIUM_PALE, True)
        lamps.append(head)
    return lamps


def banner(add, text, center, facing, px=0.10, col=LETTER_CREAM, bg=PROP_RED):
    """A vertical red cloth with one glyph per row; returns its height."""
    chars = [ch for ch in text.upper() if ch in GLYPHS and ch.strip()][:12]
    gw = 7 * px                     # 5 glyph columns plus a pixel either side
    gh = len(chars) * GLYPH_H * px + 2 * px
    _slab(add, center, facing, 0.0, 0.0, 0.0, gw, gh, 0.04, bg)
    for i, ch in enumerate(chars):
        row = GLYPHS[ch]
        for r in range(GLYPH_H):
            c = row[r].find("#")
            while c >= 0:
                run = len(row[r][c:]) - len(row[r][c:].lstrip("#"))
                row_idx = i * GLYPH_H + r
                du = (c + run / 2.0 - 2.5) * px
                dv = (gh / 2.0) - px - (row_idx + 0.5) * px
                _slab(add, center, facing, du, dv, 0.03, run * px, px, 0.02, col)
                c = row[r].find("#", c + run)
    # Pole stub on top.
    _slab(add, center, facing, 0.0, gh / 2.0 + 0.25, 0.0, 0.08, 0.5, 0.08, (40, 44, 52))
    return gh
