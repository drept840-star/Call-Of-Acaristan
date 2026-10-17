"""Shared pixel-art kit for the Mission 5 sprites.

Conventions (see previews/m5_gauntlet/NITPICKS.md):
  * KEY LIGHT FROM THE UPPER-LEFT: bevels/highlights on top+left edges,
    shade on bottom+right edges, cast shadows fall down-right.
  * Flat colour areas (no per-pixel noise) so the 3D decal mesher can merge
    runs into few faces, and so the art reads as deliberate pixel art.
  * pygame only - no game imports (safe for tools/bake_m5_sprites.py).
"""
import pygame

INK = (28, 24, 22)
CREAM = (214, 200, 164)
PAPER = (222, 214, 190)
RED = (150, 30, 28)
GUARD_RED = (180, 40, 40)
BRASS = (176, 140, 62)
GOLD_HI = (232, 200, 120)
GOLD_LO = (112, 84, 36)
GUARD_BLACK = (24, 22, 24)
KRAP_BLUE = (52, 86, 150)
CLEAR = (0, 0, 0, 0)

# classic 5x7 column font (LSB = top row)
_F = {
    "A": (0x7E, 0x11, 0x11, 0x11, 0x7E), "B": (0x7F, 0x49, 0x49, 0x49, 0x36),
    "C": (0x3E, 0x41, 0x41, 0x41, 0x22), "D": (0x7F, 0x41, 0x41, 0x22, 0x1C),
    "E": (0x7F, 0x49, 0x49, 0x49, 0x41), "F": (0x7F, 0x09, 0x09, 0x09, 0x01),
    "G": (0x3E, 0x41, 0x49, 0x49, 0x7A), "H": (0x7F, 0x08, 0x08, 0x08, 0x7F),
    "I": (0x00, 0x41, 0x7F, 0x41, 0x00), "J": (0x20, 0x40, 0x41, 0x3F, 0x01),
    "K": (0x7F, 0x08, 0x14, 0x22, 0x41), "L": (0x7F, 0x40, 0x40, 0x40, 0x40),
    "M": (0x7F, 0x02, 0x0C, 0x02, 0x7F), "N": (0x7F, 0x04, 0x08, 0x10, 0x7F),
    "O": (0x3E, 0x41, 0x41, 0x41, 0x3E), "P": (0x7F, 0x09, 0x09, 0x09, 0x06),
    "Q": (0x3E, 0x41, 0x51, 0x21, 0x5E), "R": (0x7F, 0x09, 0x19, 0x29, 0x46),
    "S": (0x46, 0x49, 0x49, 0x49, 0x31), "T": (0x01, 0x01, 0x7F, 0x01, 0x01),
    "U": (0x3F, 0x40, 0x40, 0x40, 0x3F), "V": (0x1F, 0x20, 0x40, 0x20, 0x1F),
    "W": (0x3F, 0x40, 0x38, 0x40, 0x3F), "X": (0x63, 0x14, 0x08, 0x14, 0x63),
    "Y": (0x07, 0x08, 0x70, 0x08, 0x07), "Z": (0x61, 0x51, 0x49, 0x45, 0x43),
    "0": (0x3E, 0x51, 0x49, 0x45, 0x3E), "1": (0x00, 0x42, 0x7F, 0x40, 0x00),
    "2": (0x42, 0x61, 0x51, 0x49, 0x46), "3": (0x21, 0x41, 0x45, 0x4B, 0x31),
    "4": (0x18, 0x14, 0x12, 0x7F, 0x10), "5": (0x27, 0x45, 0x45, 0x45, 0x39),
    "6": (0x3C, 0x4A, 0x49, 0x49, 0x30), "7": (0x01, 0x71, 0x09, 0x05, 0x03),
    "8": (0x36, 0x49, 0x49, 0x49, 0x36), "9": (0x06, 0x49, 0x49, 0x29, 0x1E),
    "-": (0x08, 0x08, 0x08, 0x08, 0x08), ".": (0x00, 0x60, 0x60, 0x00, 0x00),
    "!": (0x00, 0x00, 0x5F, 0x00, 0x00), ":": (0x00, 0x36, 0x36, 0x00, 0x00),
    "/": (0x20, 0x10, 0x08, 0x04, 0x02), " ": (0, 0, 0, 0, 0),
}


def new(w, h, fill=CLEAR):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill(fill)
    return s


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def shade(c, f):
    return tuple(max(0, min(255, int(c[i] * f))) for i in range(3))


def text_w(s, sp=1, sx=1):
    return (len(s) * (5 + sp) - sp) * sx


def text(surf, s, x, y, col, sp=1, sx=1, sy=1, skip=()):
    """Blit ``s`` in the 5x7 font; ``skip`` = char indices drawn in col[1]
    when ``col`` is a (lit, dead) pair (sign letters that have blown)."""
    lit, dead = (col if isinstance(col[0], tuple) else (col, col))
    for n, ch in enumerate(s.upper()):
        cols = _F.get(ch, _F[" "])
        c = dead if n in skip else lit
        for i, bits in enumerate(cols):
            for j in range(7):
                if bits >> j & 1:
                    surf.fill(c, (x + i * sx, y + j * sy, sx, sy))
        x += (5 + sp) * sx


def text_c(surf, s, cx, y, col, sp=1, sx=1, sy=1, skip=()):
    text(surf, s, cx - text_w(s, sp, sx) // 2, y, col, sp, sx, sy, skip)


def bevel(surf, rect, hi, lo, t=1):
    """Raised edge, lit from the upper-left."""
    x, y, w, h = rect
    for k in range(t):
        surf.fill(hi, (x + k, y + k, w - 2 * k, 1))
        surf.fill(hi, (x + k, y + k, 1, h - 2 * k))
        surf.fill(lo, (x + k, y + h - 1 - k, w - 2 * k, 1))
        surf.fill(lo, (x + w - 1 - k, y + k, 1, h - 2 * k))


def curl(surf, col, a=70):
    """Paper lifting off the wall: 1 px shade on the bottom+right edges."""
    w, h = surf.get_size()
    sh = new(w, h)
    sh.fill((*col, a), (0, h - 1, w, 1))
    sh.fill((*col, a), (w - 1, 0, 1, h))
    surf.blit(sh, (0, 0))


def lines(surf, x, y, w, rows, col, gap=3, seed=1):
    """Fine print too small to read: ragged grey bars."""
    v = seed * 7919
    for r in range(rows):
        v = (v * 1103515245 + 12345) & 0x7FFFFFFF
        ln = w - (v >> 8) % max(1, w // 3) if r % 4 != 3 else w // 2
        surf.fill(col, (x, y + r * gap, ln, 1))


def fade(surf, toward, t):
    """Sun/rain-bleached: pull every opaque pixel toward ``toward``."""
    w, h = surf.get_size()
    for y in range(h):
        for x in range(w):
            r, g, b, a = surf.get_at((x, y))
            if a:
                surf.set_at((x, y), (*mix((r, g, b), toward, t), a))


def scaled(surf, scale):
    if scale == 1:
        return surf
    w, h = surf.get_size()
    return pygame.transform.scale(surf, (max(1, int(w * scale)), max(1, int(h * scale))))
