"""make_art_pack.py - author assets/art/*.png (phases 1, 2, 4 art).

Regenerates the loaded-art tier. Every sprite is drawn with pygame
primitives at 1:1, palette-locked to the colours the procedural renderers
already use, in the project's house style (flat vector, motivated lighting)
plus the three things procedural-per-frame art could never afford:
2-3 tone shading, 1 px contact outlines, and baked ambient occlusion.

    python tools/make_art_pack.py

Missing PNGs are fine at runtime: entities.sprite_lib / core.artpack return
None and each call site falls back to its procedural renderer.
"""
import math
import os
import random
import sys

import pygame

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
pygame.init()

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "..", "assets", "art")
FONTS = os.path.join(ROOT, "..", "assets", "fonts")
os.makedirs(OUT, exist_ok=True)

T = 64  # TILE_SIZE

# ── palette lifted from the live renderers ──
FLOOR = {
    # "g" is Mission 3's exterior compound ground: fine grey aggregate over a
    # compacted base, and the largest single surface in every M3 frame.  It
    # went mud brown (40, 36, 32) -> warm grey (43, 42, 38) -> neutral grey
    # here: even the warm version kept reading as wet dirt next to the neutral
    # concrete interiors, so the surface is now colourless and the night
    # lighting is the only thing tinting it.  Mirrored in
    # missions/m3/systems.py::_TILE_BASE.
    ".": (32, 33, 33), "g": (46, 46, 48), "O": (29, 36, 38),
    # M2 open-ground families.  These two used to have NO art tile at all:
    # _render_m2_bg fell through to a flat pygame.draw.rect, so the ditch and
    # the service road rendered as two 23x15-tile slabs of one unbroken
    # colour - the hard-edged rectangles that made the overview look like
    # misplaced terrain.  They are authored here like every other floor.
    "d": (29, 35, 34), "s": (34, 37, 35),
    "L": (34, 42, 44), "Y": (45, 45, 42), "M": (31, 34, 32),
}
CHK = {
    "K": ((60, 62, 66), (45, 48, 52), (35, 38, 42)),
    "L": ((36, 46, 48), (30, 39, 42), (23, 29, 31)),
    "Y": ((48, 48, 44), (42, 42, 39), (34, 34, 31)),
    "M": ((34, 36, 34), (27, 31, 30), (20, 24, 23)),
}
WALL = (45, 46, 44)
WALL_CAP = (64, 66, 60)
WALL_DARK = (24, 25, 24)
BARRIER = (60, 50, 40)
GLASS = (60, 90, 100)
SPINES = ((96, 54, 74), (54, 74, 96), (74, 64, 44),
          (64, 44, 86), (44, 59, 54), (110, 84, 52))
SHELF_WOOD = (34, 28, 24)
SHELF_EDGE = (74, 62, 50)
CAB_BODY = (28, 24, 34)
CAB_EDGE = (70, 58, 88)
SKIN = (210, 180, 140)
UNIFORM = (60, 70, 50)
PAPER = (214, 196, 158)
RED = (178, 42, 42)


def S(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def O(w, h):
    """Opaque surface. Main sprite bodies must be opaque: pygame.draw does
    NOT alpha-blend into a surface, so low-alpha draws on a SRCALPHA body
    would punch transparency holes when blitted."""
    return pygame.Surface((w, h))


def mix(c1, c2, f):
    """Solid stand-in for 'c2 at alpha f over c1'."""
    return tuple(int(c1[i] + (c2[i] - c1[i]) * f) for i in range(3))


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def lit(c, f):
    return tuple(max(0, min(255, int(v + (255 - v) * f))) for v in c[:3])


def save(name, surf):
    pygame.image.save(surf, os.path.join(OUT, name + ".png"))


def grain(surf, n, dark, light, seed, alpha=26):
    rnd = random.Random(seed)
    w, h = surf.get_size()
    f = alpha / 255.0
    for _ in range(n):
        x, y = rnd.randrange(w), rnd.randrange(h)
        base = surf.get_at((x, y))[:3]
        c = dark if rnd.random() < 0.55 else light
        surf.set_at((x, y), mix(base, c, f))


def ao_bottom(surf, height, strength=110):
    w, h = surf.get_size()
    g = S(w, height)
    for i in range(height):
        a = int(strength * (1 - i / height))
        pygame.draw.line(g, (0, 0, 0, a), (0, height - 1 - i),
                         (w, height - 1 - i))
    surf.blit(g, (0, h - height))


def ao_top(surf, height, strength=70):
    w, _ = surf.get_size()
    g = S(w, height)
    for i in range(height):
        a = int(strength * (1 - i / height))
        pygame.draw.line(g, (0, 0, 0, a), (0, i), (w, i))
    surf.blit(g, (0, 0))


def contact_shadow(surf, cx, cy, rx, ry, a=70):
    s = S(rx * 2, ry * 2)
    pygame.draw.ellipse(s, (0, 0, 0, a), (0, 0, rx * 2, ry * 2))
    s = pygame.transform.smoothscale(s, (rx * 2, ry * 2))
    surf.blit(s, (cx - rx, cy - ry))


# ───────────────────────────── floors ─────────────────────────────
def floor_tile(code, vi):
    s = O(T, T)
    base = FLOOR[code]
    s.fill(base + (255,))
    # Stable seed.  This used to be ``hash((code, vi))``, but Python randomises
    # str hashing per process (PYTHONHASHSEED), so every regeneration produced
    # DIFFERENT floor tiles - re-running this tool silently re-textured every
    # map.  Derive the seed arithmetically instead so output is reproducible.
    rnd = random.Random((ord(code) * 2654435761 + vi * 40503) & 0xFFFFFFFF)

    # IMPORTANT: variants are MICRO-DETAIL ONLY. They all keep the same base
    # colour; otherwise the spatial variant hash creates a visible 64px quilt.
    # Broad variation belongs in a world-space renderer where it can cross
    # tile boundaries smoothly.
    #
    # Second, equally important rule: no motif may be stamped into EVERY
    # variant.  Every "." variant used to carry the same hairline crack, so
    # the highway showed a zig-zag lattice repeating on a perfect 64px grid -
    # the eye locks onto that long before it notices any tone difference, and
    # no amount of mean-colour balancing hides it.  Each variant therefore
    # gets its own *set* of features, with a matched ink budget so the means
    # stay within a fraction of a level of each other.
    dk = shade(base, 0.70)
    lt = lit(base, 0.14)
    ink_d = mix(base, dk, 0.60)      # faint dark ink
    ink_l = mix(base, lt, 0.55)      # faint light ink

    if code == ".":
        # No tile-edge seam. Balanced aggregate flecks keep all variants at
        # nearly the same mean colour.
        for k in range(28):
            x, y = rnd.randrange(T), rnd.randrange(T)
            d = 2 if k % 2 else -2
            s.set_at((x, y), tuple(max(0, min(255, c + d)) for c in base))
        if vi == 0:                      # hairline crack
            y0 = 8 + rnd.randrange(12)
            pygame.draw.lines(s, ink_d, False,
                              [(6, y0), (20, y0 + 10),
                               (34, y0 + 8), (56, y0 + 24)], 1)
        elif vi == 1:                    # trowelled patch outline
            px, py = rnd.randrange(4, 24), rnd.randrange(6, 34)
            pygame.draw.rect(s, ink_l, (px, py, 30, 20), 1)
        elif vi == 2:                    # two aggregate chips
            for _ in range(2):
                x, y = rnd.randrange(6, T - 8), rnd.randrange(6, T - 8)
                pygame.draw.rect(s, ink_l, (x, y, 5, 3))
        else:                            # scuff
            x, y = rnd.randrange(4, T - 34), rnd.randrange(6, T - 14)
            pygame.draw.line(s, ink_d, (x, y), (x + 26, y + 6), 2)
    elif code == "g":
        # Exterior compound ground: neutral aggregate over a compacted base.
        # Uniform grit plus ONE small, low-contrast feature per variant.  The
        # old family stamped a 28x16 dark ellipse, a 2 px full-height rut and
        # a bright three-blade tuft into every repeat - on the largest surface
        # in the map that read as 64 px wallpaper at play scale, and the tuft
        # and the dark ellipse read as weeds and damp patches on the ground.
        # Broad variation belongs in world space:
        # missions/m3/draw.py::_draw_m3_exterior_ground.
        for k in range(30):
            x, y = rnd.randrange(T), rnd.randrange(T)
            d = 3 if k % 2 else -3
            col = tuple(max(0, min(255, c + d)) for c in base)
            pygame.draw.circle(s, col, (x, y), 1)
        if vi == 0:                      # loose pebbles
            for _ in range(5):
                x, y = rnd.randrange(5, T - 6), rnd.randrange(5, T - 4)
                pygame.draw.rect(s, ink_l, (x, y, 2, 1))
        elif vi == 1:                    # faint drag scrape
            x, y = rnd.randrange(6, T - 30), rnd.randrange(6, T - 10)
            pygame.draw.line(s, mix(base, dk, 0.30),
                             (x, y),
                             (x + rnd.randrange(16, 26), y + rnd.randrange(-3, 4)), 1)
        elif vi == 2:                    # aggregate ridge (was: weed sprig)
            for _ in range(3):
                x, y = rnd.randrange(10, T - 14), rnd.randrange(10, T - 12)
                pygame.draw.rect(s, ink_l, (x, y, rnd.choice((3, 4, 5)), 2))
                pygame.draw.rect(s, ink_d, (x + 2, y + 2, 2, 1))
        else:                            # compacted tread (soft, low contrast)
            x, y = rnd.randrange(4, T - 34), rnd.randrange(4, T - 24)
            pygame.draw.ellipse(s, mix(base, ink_d, 0.14), (x, y, 30, 20))
            pygame.draw.ellipse(s, mix(base, ink_l, 0.16), (x + 7, y + 5, 16, 9))
    elif code == "O":
        # Interior panels: identical 32px joints, moving only tiny scratches.
        joint = shade(base, 0.82)
        pygame.draw.line(s, joint, (32, 0), (32, T - 1), 1)
        pygame.draw.line(s, joint, (0, 32), (T - 1, 32), 1)
        for _ in range(4):
            x, y = rnd.randrange(5, T - 12), rnd.randrange(5, T - 5)
            pygame.draw.line(s, shade(base, 0.72), (x, y), (x + 6, y), 1)
    elif code == "d":
        # Drainage ditch: damp silt, uniform grit, and exactly one standing
        # water glint per variant so the family mean never drifts.
        for k in range(26):
            x, y = rnd.randrange(T), rnd.randrange(T)
            d = 3 if k % 2 else -3
            col = tuple(max(0, min(255, c + d)) for c in base)
            pygame.draw.circle(s, col, (x, y), 1)
        gx = rnd.randrange(6, T - 26)
        gy = rnd.randrange(8, T - 10)
        pygame.draw.ellipse(s, mix(base, (120, 150, 170), 0.30), (gx, gy, 20, 5))
        pygame.draw.ellipse(s, mix(base, (60, 80, 90), 0.35), (gx + 2, gy + 1, 12, 2))
        pygame.draw.line(s, mix(base, dk, 0.45),
                         (0, rnd.randrange(6, T - 6)), (T, rnd.randrange(6, T - 6)), 1)
    elif code == "s":
        # Service road: worn asphalt, same grit budget as the ditch, one
        # surface blemish per variant.  The continuous wheel-wear lines are a
        # WORLD-SPACE feature and live in m2/draw.py - drawing them per tile
        # would restart them at every 64px edge.
        for k in range(26):
            x, y = rnd.randrange(T), rnd.randrange(T)
            d = 2 if k % 2 else -2
            s.set_at((x, y), tuple(max(0, min(255, c + d)) for c in base))
        if vi % 2 == 0:
            x, y = rnd.randrange(4, T - 30), rnd.randrange(6, T - 18)
            pygame.draw.rect(s, ink_d, (x, y, 24, 12), 1)
        else:
            x = rnd.randrange(8, T - 24)
            pygame.draw.line(s, ink_l, (x, 10), (x + 18, T - 12), 1)
    elif code == "L":
        for gx in (0, 32):
            pygame.draw.line(s, shade(base, 0.72) + (150,), (gx, 0), (gx, T), 1)
        pygame.draw.line(s, shade(base, 0.72) + (150,), (0, 32), (T, 32), 1)
        if vi in (1, 3):
            pygame.draw.ellipse(s, lit(base, 0.10) + (36,), (8, 12, 44, 30))
    elif code == "Y":
        pygame.draw.line(s, shade(base, 0.75) + (120,), (0, T - 1), (T, T - 1), 1)
        if vi == 2:
            pygame.draw.line(s, (120, 112, 60, 70), (0, 20), (T, 20), 4)
        for _ in range(8):
            x, y = rnd.randrange(T), rnd.randrange(T)
            s.set_at((x, y), mix(base, shade(base, 0.8), 0.25))
    elif code == "M":
        pygame.draw.rect(s, shade(base, 1.15) + (50,), (3, 3, T - 6, T - 6), 1)
        for cx, cy in ((8, 8), (T - 8, 8), (8, T - 8), (T - 8, T - 8)):
            pygame.draw.circle(s, lit(base, 0.2) + (110,), (cx, cy), 2)
    # M2's main floor families must stay colour-uniform.  The old common grain
    # pass included 220 high-contrast pixels per 64px tile; combined with the
    # four variants that made the road/shoulder/interior read as a quilt.
    if code not in ".gOds":
        grain(s, 220, shade(base, 0.7), lit(base, 0.14), vi + ord(code), 22)
    return s


def checker_tile(code, ab):
    s = O(T, T)
    a, b, edge = CHK[code]
    base = a if ab == "a" else b
    s.fill(base + (255,))
    rnd = random.Random(ord(code) * 7 + (0 if ab == "a" else 1))
    for _ in range(2):
        r = rnd.randint(12, 24)
        x, y = rnd.randrange(T), rnd.randrange(T)
        pygame.draw.ellipse(s, mix(base, shade(base, 0.9), 0.10), (x - r, y - r, r * 2, r * 2))
    if code == "K":  # server room: brushed plate + seam
        for i in range(0, T, 4):
            pygame.draw.line(s, mix(base, lit(base, 0.05), 0.08), (0, i), (T, i), 1)
        pygame.draw.rect(s, edge + (150,), (0, 0, T, T), 1)
    elif code == "L":
        pygame.draw.rect(s, edge + (150,), (0, 0, T, T), 1)
        pygame.draw.ellipse(s, mix(base, lit(base, 0.12), 0.12), (10, 18, 40, 26))
    elif code == "Y":
        pygame.draw.rect(s, edge + (140,), (0, 0, T, T), 1)
        for _ in range(6):
            s.set_at((rnd.randrange(T), rnd.randrange(T)), shade(base, 0.85) + (70,))
    else:
        pygame.draw.rect(s, edge + (150,), (0, 0, T, T), 1)
        pygame.draw.line(s, shade(base, 0.7) + (90,), (6, 40), (40, 46), 1)
    grain(s, 160, shade(base, 0.75), lit(base, 0.1), ord(code) + (0 if ab == "a" else 5), 20)
    return s


# ───────────────────────────── walls ─────────────────────────────
def wall_tile(vi):
    s = O(T, T)
    s.fill(WALL + (255,))
    rnd = random.Random(900 + vi)
    # vertical panel seams
    for sx in (0, 32):
        pygame.draw.line(s, shade(WALL, 0.78) + (160,), (sx, 10), (sx, T), 1)
        pygame.draw.line(s, lit(WALL, 0.10) + (90,), (sx + 1, 10), (sx + 1, T), 1)
    # top cap
    pygame.draw.rect(s, WALL_CAP + (255,), (0, 0, T, 9))
    pygame.draw.line(s, lit(WALL_CAP, 0.25) + (255,), (0, 0), (T, 0), 1)
    pygame.draw.line(s, shade(WALL_CAP, 0.6) + (255,), (0, 9), (T, 9), 1)
    # face tonal variation
    for _ in range(3):
        r = rnd.randint(8, 18)
        x, y = rnd.randrange(T), rnd.randrange(10, T)
        c = shade(WALL, 0.88) if rnd.random() < 0.6 else lit(WALL, 0.07)
        pygame.draw.ellipse(s, mix(WALL, c, 0.12), (x - r, y - r, r * 2, r * 2))
    if vi == 1:  # crack
        pygame.draw.lines(s, shade(WALL, 0.55) + (150,), False,
                          [(20, 10), (26, 24), (22, 36), (30, 52)], 1)
    if vi == 2:  # damp stain from cap
        st = S(T, T)
        pygame.draw.ellipse(st, (24, 26, 24, 60), (30, 0, 26, 40))
        st = pygame.transform.smoothscale(st, (T, T))
        s.blit(st, (0, 0))
    if vi == 3:  # scuff
        for i in range(5):
            pygame.draw.line(s, shade(WALL, 0.7) + (60,),
                             (8 + i * 3, 40 + (i % 2)), (18 + i * 3, 46), 1)
    grain(s, 200, shade(WALL, 0.7), lit(WALL, 0.12), 40 + vi, 24)
    ao_bottom(s, 14, 120)   # baked contact occlusion where wall meets floor
    return s


def barrier_tile(vi):
    s = O(T, T)
    s.fill(BARRIER + (255,))
    for i in range(-T, T, 16):
        pts = [(i, T), (i + 8, T), (i + 8 + T, 0), (i + T, 0)]
        pygame.draw.polygon(s, (150, 128, 52, 200) if vi == 0 else (120, 104, 44, 200),
                            [(max(0, min(T, x)), max(0, min(T, y))) for x, y in pts])
    pygame.draw.rect(s, shade(BARRIER, 0.6) + (255,), (0, 0, T, T), 2)
    pygame.draw.line(s, lit(BARRIER, 0.2) + (200,), (2, 2), (T - 2, 2), 1)
    ao_bottom(s, 10, 100)
    return s


def glass_tile():
    s = S(T, T)  # intentionally translucent
    s.fill(GLASS + (110,))
    for off in range(-T, T, 8):
        pygame.draw.line(s, (90, 130, 140, 90), (off, 0), (off + T, T), 1)
    pygame.draw.line(s, (200, 240, 250, 120), (6, T - 6), (T - 6, 6), 3)
    pygame.draw.rect(s, (38, 52, 56, 220), (0, 0, T, T), 2)
    return s


# ───────────────────────────── shelves ─────────────────────────────
def book_row(s, x, y, w, h, rnd, gapChance=0.14):
    cx = x
    while cx < x + w - 5:
        if rnd.random() < gapChance:
            cx += rnd.randint(4, 10)
            continue
        bw = rnd.randint(4, 8)
        bh = h - rnd.randint(0, 8)
        col = SPINES[rnd.randrange(len(SPINES))]
        lean = rnd.random() < 0.10
        if lean:
            pts = [(cx, y + h), (cx + bw, y + h),
                   (cx + bw + 4, y + h - bh), (cx + 4, y + h - bh)]
            pygame.draw.polygon(s, col + (255,), pts)
            pygame.draw.line(s, shade(col, 0.65) + (255,),
                             (cx + bw, y + h), (cx + bw + 4, y + h - bh), 1)
        else:
            pygame.draw.rect(s, col + (255,), (cx, y + h - bh, bw, bh))
            pygame.draw.line(s, lit(col, 0.22),
                             (cx, y + h - bh), (cx, y + h - bh + bh - 1), 1)
            pygame.draw.line(s, shade(col, 0.6),
                             (cx + bw - 1, y + h - bh), (cx + bw - 1, y + h), 1)
            if bh > 18 and rnd.random() < 0.5:  # title band
                pygame.draw.line(s, mix(col, lit(col, 0.4), 0.8),
                                 (cx + 1, y + h - bh + 5), (cx + bw - 1, y + h - bh + 5), 1)
        cx += bw + 1
    # horizontal stack in some gaps
    if rnd.random() < 0.35:
        sx = x + rnd.randint(0, max(1, w - 26))
        for i in range(rnd.randint(2, 3)):
            col = SPINES[rnd.randrange(len(SPINES))]
            pygame.draw.rect(s, col + (255,), (sx, y + h - 4 - i * 5, 22, 4))
            pygame.draw.line(s, lit(col, 0.2), (sx, y + h - 4 - i * 5),
                             (sx + 21, y + h - 4 - i * 5), 1)


def shelf_sprite(seed):
    w, h = 64, 192
    s = O(w, h)
    rnd = random.Random(seed)
    s.fill(SHELF_WOOD + (255,))
    pygame.draw.rect(s, shade(SHELF_WOOD, 0.6) + (255,), (0, 0, w, h), 1)
    pygame.draw.line(s, SHELF_EDGE, (1, 1), (1, h - 2), 1)
    pygame.draw.line(s, mix(SHELF_WOOD, SHELF_EDGE, 0.6), (w - 2, 1), (w - 2, h - 2), 1)
    n_sh = 4
    for i in range(n_sh):
        sy = 8 + i * 46
        # cavity
        pygame.draw.rect(s, shade(SHELF_WOOD, 0.5) + (255,), (4, sy, w - 8, 38))
        ao_top(s, 0)  # noop guard
        cav = S(w - 8, 38)
        for yy in range(10):
            pygame.draw.line(cav, (0, 0, 0, int(90 * (1 - yy / 10))), (0, yy), (w - 8, yy))
        s.blit(cav, (4, sy))
        book_row(s, 5, sy + 2, w - 10, 34, rnd)
        # plank with lit top edge
        pygame.draw.rect(s, SHELF_WOOD + (255,), (2, sy + 38, w - 4, 6))
        pygame.draw.line(s, lit(SHELF_EDGE, 0.25), (2, sy + 38), (w - 2, sy + 38), 1)
        pygame.draw.line(s, shade(SHELF_WOOD, 0.55) + (255,), (2, sy + 43), (w - 2, sy + 43), 1)
    # dust + flat stacks on top
    pygame.draw.line(s, mix(SHELF_WOOD, (150, 140, 120), 0.25), (2, 2), (w - 2, 2), 1)
    for i in range(2):
        col = SPINES[rnd.randrange(len(SPINES))]
        pygame.draw.rect(s, col + (255,), (8 + i * 26, 3 - 0, 20, 4))
    ao_bottom(s, 16, 130)
    return s


def shelf_top():
    s = O(64, 16)
    s.fill(SHELF_WOOD + (255,))
    pygame.draw.line(s, lit(SHELF_EDGE, 0.3), (0, 0), (64, 0), 1)
    pygame.draw.line(s, mix(SHELF_WOOD, (150, 140, 120), 0.3), (1, 1), (63, 1), 1)
    rnd = random.Random(5)
    for i in range(2):
        col = SPINES[rnd.randrange(len(SPINES))]
        pygame.draw.rect(s, col + (255,), (10 + i * 24, 4, 18, 4))
        pygame.draw.rect(s, shade(col, 0.8) + (255,), (12 + i * 24, 8, 16, 4))
    ao_bottom(s, 5, 90)
    return s


def ladder():
    s = O(32, 128)
    for x in (4, 24):
        pygame.draw.rect(s, (96, 88, 72, 255), (x, 0, 4, 128))
        pygame.draw.line(s, (140, 130, 108, 255), (x, 0), (x, 127), 1)
    for y in range(8, 128, 14):
        pygame.draw.rect(s, (84, 78, 64, 255), (4, y, 24, 3))
        pygame.draw.line(s, (120, 112, 94, 255), (4, y), (28, y), 1)
    return s


def library_cart():
    s = O(64, 64)
    contact_shadow(s, 32, 58, 26, 7)
    pygame.draw.rect(s, (70, 66, 58, 255), (6, 12, 4, 44))
    pygame.draw.rect(s, (70, 66, 58, 255), (54, 12, 4, 44))
    for y in (24, 42):
        pygame.draw.rect(s, SHELF_WOOD + (255,), (6, y, 52, 5))
        pygame.draw.line(s, lit(SHELF_EDGE, 0.2), (6, y), (58, y), 1)
        book_row(s, 9, y - 16, 46, 16, random.Random(y), gapChance=0.2)
    pygame.draw.circle(s, (30, 30, 32, 255), (12, 58), 5)
    pygame.draw.circle(s, (30, 30, 32, 255), (52, 58), 5)
    pygame.draw.circle(s, (90, 90, 94, 255), (12, 58), 2)
    pygame.draw.circle(s, (90, 90, 94, 255), (52, 58), 2)
    return s


# ───────────────────────────── props ─────────────────────────────
# NOTE: these are silhouette sprites blitted over floors/walls, so they use
# S() (SRCALPHA) - not O().  Every body draw below passes alpha 255 (or a
# 3-tuple, which pygame maps to opaque on SRCALPHA), and contact_shadow()
# blits a partial-alpha gradient that composites correctly.  Unpainted pixels
# stay (0,0,0,0) and survive pygame.image.save as PNG color type 6 (RGBA),
# so no black box is blitted in-game.  See O()'s docstring for why full
# bodies (floors, walls) must stay opaque.
def crate_stack():
    s = S(96, 96)
    contact_shadow(s, 48, 90, 40, 8)
    OUT = (34, 25, 15)

    def vgrad(rect, c_top, c_bot):
        x, y, w, h = rect
        for yy in range(h):
            t = yy / max(1, h - 1)
            col = tuple(int(c_top[i] + (c_bot[i] - c_top[i]) * t) for i in range(3))
            pygame.draw.line(s, col + (255,), (x, y + yy), (x + w - 1, y + yy))

    def crate(x, y, w, h, base, brace=True, stencil=False):
        vgrad((x, y, w, h), lit(base, 0.28), shade(base, 0.72))
        pygame.draw.rect(s, OUT + (255,), (x, y, w, h), 1)
        for fy in (0.36, 0.68):
            yy = y + int(h * fy)
            pygame.draw.line(s, shade(base, 0.55) + (255,), (x + 1, yy), (x + w - 2, yy))
            pygame.draw.line(s, lit(base, 0.14) + (255,), (x + 1, yy + 1), (x + w - 2, yy + 1))
        pygame.draw.line(s, lit(base, 0.42) + (255,), (x + 1, y + 1), (x + w - 2, y + 1))
        if brace:
            pygame.draw.line(s, lit(base, 0.12) + (255,), (x + 2, y + 2), (x + w - 3, y + h - 3), 2)
            pygame.draw.line(s, OUT + (255,), (x + 2, y + 3), (x + w - 3, y + h - 2), 1)
        if stencil:
            pygame.draw.rect(s, (52, 40, 26, 255), (x + w - 14, y + 4, 10, 7))
            pygame.draw.line(s, (128, 104, 66), (x + w - 12, y + 7), (x + w - 6, y + 7))

    # pallet
    vgrad((6, 90, 84, 6), (92, 70, 42), (56, 42, 24))
    pygame.draw.rect(s, OUT + (255,), (6, 90, 84, 6), 1)
    for fx in (30, 58):
        pygame.draw.line(s, (40, 30, 18, 255), (fx, 91), (fx, 95))
    crate(8, 52, 44, 38, (96, 72, 42), True, True)
    crate(50, 58, 38, 32, (84, 64, 38), True, False)
    crate(20, 16, 40, 36, (108, 82, 48), False, True)
    pygame.draw.line(s, (48, 38, 24, 255), (32, 17), (32, 51), 2)
    return s


def barrels():
    s = S(96, 64)
    contact_shadow(s, 48, 60, 42, 7)
    # Slightly more saturated hues so the drums separate from the dark floor
    # instead of reading as pale washed cylinders.
    HUES = ((86, 96, 88), (74, 86, 98), (98, 78, 56))

    def hgrad(rect, c_l, c_r):
        x, y, w, h = rect
        for xx in range(w):
            t = xx / max(1, w - 1)
            col = tuple(int(c_l[i] + (c_r[i] - c_l[i]) * t) for i in range(3))
            pygame.draw.line(s, col + (255,), (x + xx, y), (x + xx, y + h - 1))

    for i, (bx, bw) in enumerate(((8, 30), (38, 32), (68, 26))):
        base = HUES[i % 3]
        hgrad((bx, 12, bw, 48), lit(base, 0.34), shade(base, 0.52))
        pygame.draw.rect(s, (22, 26, 24, 255), (bx, 12, bw, 48), 1)
        # specular band down the lit third + deep shade on the right edge
        hx = bx + int(bw * 0.28)
        pygame.draw.line(s, lit(base, 0.62) + (255,), (hx, 14), (hx, 57), 2)
        pygame.draw.line(s, lit(base, 0.42) + (255,), (hx + 3, 15), (hx + 3, 56), 1)
        pygame.draw.line(s, shade(base, 0.36) + (255,),
                         (bx + bw - 2, 13), (bx + bw - 2, 58), 2)
        # top rim: lit lip over a dark inner well (reads as a closed head)
        pygame.draw.ellipse(s, lit(base, 0.5) + (255,), (bx, 7, bw, 10))
        pygame.draw.ellipse(s, (22, 26, 24, 255), (bx, 7, bw, 10), 1)
        pygame.draw.ellipse(s, shade(base, 0.45) + (255,), (bx + 3, 8, bw - 6, 7))
        pygame.draw.ellipse(s, (18, 21, 20, 255), (bx + 5, 9, bw - 10, 5))
        # bung
        pygame.draw.circle(s, (30, 34, 32, 255), (bx + bw - 7, 11), 2)
        pygame.draw.circle(s, lit(base, 0.3) + (255,), (bx + bw - 7, 11), 2, 1)
        # rolling hoops: dark band + lit lip
        for ry in (25, 41):
            pygame.draw.line(s, shade(base, 0.42) + (255,),
                             (bx + 1, ry), (bx + bw - 2, ry), 3)
            pygame.draw.line(s, lit(base, 0.4) + (255,),
                             (bx + 1, ry + 3), (bx + bw - 2, ry + 3), 1)
        # grime streak
        pygame.draw.line(s, mix(base, (110, 66, 38), 0.5) + (255,),
                         (bx + 5, 16), (bx + 5, 56))
    return s


def cable_coil():
    """Coiled cable on the ground.

    Drawn as concentric RINGS (circle with width) rather than stacked filled
    discs: the old version painted a dark disc over a dark floor and read as
    a tyre.  Rings keep a real hole in the middle, and each loop gets its own
    lit crown / shaded underside so the bundle reads as wrapped cable.
    """
    s = S(64, 64)
    contact_shadow(s, 32, 55, 24, 6)
    cx, cy = 32, 32
    RUBBER = (54, 51, 44)
    RUBBER_DK = (26, 25, 22)
    LIT = (152, 148, 128)
    LIT_HOT = (198, 194, 170)
    for r in (21, 15, 9):
        pygame.draw.circle(s, RUBBER_DK + (255,), (cx, cy), r, 6)
        pygame.draw.circle(s, RUBBER + (255,), (cx, cy), r, 4)
        box = (cx - r, cy - r, r * 2, r * 2)
        # lit crown (top-left) + hot specular
        pygame.draw.arc(s, LIT + (255,), box,
                        math.radians(100), math.radians(205), 2)
        pygame.draw.arc(s, LIT_HOT + (255,), box,
                        math.radians(133), math.radians(178), 1)
        # shaded underside (bottom-right)
        pygame.draw.arc(s, (17, 16, 14, 255), box,
                        math.radians(-25), math.radians(70), 2)
    # Strap holding the bundle together.
    a = math.radians(28)
    dx, dy = math.cos(a) * 24, math.sin(a) * 24
    pygame.draw.line(s, (62, 58, 46, 255),
                     (cx - dx, cy - dy), (cx + dx, cy + dy), 5)
    pygame.draw.line(s, (104, 98, 78, 255),
                     (cx - dx, cy - dy - 1), (cx + dx, cy + dy - 1), 1)
    # Loose tail curling out to a plug.
    pygame.draw.lines(s, (46, 44, 38, 255), False,
                      [(cx + 19, cy + 11), (cx + 28, cy + 19),
                       (cx + 25, cy + 27)], 3)
    pygame.draw.circle(s, (34, 33, 30, 255), (cx + 25, cy + 28), 3)
    pygame.draw.circle(s, (124, 120, 102, 255), (cx + 25, cy + 28), 1)
    return s


def mop_bucket():
    """Bucket + wringer with a mop leaning in it.

    The old mop was a 3px handle plus four hairlines, which read as a bare
    stick at gameplay scale.  The handle is now 5px with a lit edge and the
    head is a real tapered bundle under a ferrule band.
    """
    s = S(48, 64)
    contact_shadow(s, 24, 60, 18, 5)
    body = (58, 66, 72)
    pygame.draw.polygon(s, body + (255,), [(6, 26), (42, 26), (38, 58), (10, 58)])
    pygame.draw.polygon(s, (22, 26, 30, 255), [(6, 26), (42, 26), (38, 58), (10, 58)], 1)
    pygame.draw.line(s, lit(body, 0.4) + (255,), (9, 29), (12, 56), 3)
    pygame.draw.line(s, shade(body, 0.62) + (255,), (39, 29), (36, 56), 2)
    # rim + water + glint
    pygame.draw.ellipse(s, lit(body, 0.46) + (255,), (5, 22, 38, 9))
    pygame.draw.ellipse(s, (22, 26, 30, 255), (5, 22, 38, 9), 1)
    pygame.draw.ellipse(s, (32, 44, 46, 255), (9, 23, 30, 6))
    pygame.draw.arc(s, (128, 158, 158), (12, 23, 14, 5),
                    math.radians(200), math.radians(320), 1)
    # wringer basket
    pygame.draw.rect(s, (76, 84, 86, 255), (25, 14, 17, 11), border_radius=1)
    pygame.draw.rect(s, (28, 32, 36, 255), (25, 14, 17, 11), 1, border_radius=1)
    for gx in (29, 33, 37):
        pygame.draw.line(s, (44, 50, 52, 255), (gx, 16), (gx, 24))
    # ── mop: thick handle, ferrule band, tapered head bundle ──
    pygame.draw.line(s, (96, 72, 42, 255), (34, 15), (46, 0), 5)
    pygame.draw.line(s, (172, 136, 88, 255), (33, 15), (45, 0), 2)
    pygame.draw.line(s, (152, 152, 146, 255), (29, 23), (37, 17), 4)
    head = [(28, 21), (39, 17), (42, 29), (34, 40), (25, 33)]
    pygame.draw.polygon(s, (132, 124, 96, 255), head)
    pygame.draw.polygon(s, (84, 78, 58, 255), head, 1)
    for i in range(5):
        t = i / 4.0
        pygame.draw.line(s, (158, 150, 120, 255),
                         (29 + t * 8, 21 + t * 2), (27 + t * 12, 35 + t * 3), 1)
    return s


def service_cart():
    s = S(96, 64)
    contact_shadow(s, 48, 60, 40, 6)
    post = (66, 72, 74)
    for px in (10, 83):
        pygame.draw.rect(s, post + (255,), (px, 12, 3, 40))
        pygame.draw.line(s, lit(post, 0.4) + (255,), (px, 12), (px, 51))
    for rect, c in (((6, 12, 84, 6), (84, 92, 92)), ((8, 34, 80, 5), (70, 76, 76))):
        x, y, w, h = rect
        for yy in range(h):
            t = yy / max(1, h - 1)
            col = tuple(int(lit(c, 0.1)[i] + (shade(c, 0.7)[i] - lit(c, 0.1)[i]) * t) for i in range(3))
            pygame.draw.line(s, col + (255,), (x, y + yy), (x + w - 1, y + yy))
        pygame.draw.rect(s, (24, 28, 28, 255,), rect, 1)
    # lip rail
    pygame.draw.line(s, (96, 104, 104, 255), (6, 9), (90, 9))
    for lx in (6, 34, 62, 89):
        pygame.draw.line(s, (72, 80, 80, 255), (lx, 9), (lx, 12))
    # load
    pygame.draw.rect(s, (96, 104, 98, 255), (14, 6, 18, 6), border_radius=1)
    pygame.draw.rect(s, (78, 88, 84, 255), (15, 3, 16, 4), border_radius=1)
    pygame.draw.rect(s, (58, 78, 88, 255), (40, 4, 5, 8), border_radius=1)
    pygame.draw.rect(s, (40, 56, 64, 255), (41, 1, 3, 3))
    pygame.draw.rect(s, (88, 70, 46, 255), (52, 5, 14, 7), border_radius=1)
    pygame.draw.rect(s, (48, 36, 22, 255), (52, 5, 14, 7), 1, border_radius=1)
    pygame.draw.rect(s, (54, 60, 62, 255), (30, 28, 14, 6), border_radius=1)
    # handle
    pygame.draw.lines(s, (96, 104, 104, 255), False, [(86, 10), (92, 10), (92, 30)], 2)
    # casters
    for wx in (18, 78):
        pygame.draw.rect(s, (52, 56, 56, 255), (wx - 1, 50, 3, 4))
        pygame.draw.circle(s, (14, 14, 14, 255), (wx, 56), 4)
        pygame.draw.circle(s, (76, 76, 72, 255), (wx, 56), 1)
    return s


def pipe_h():
    s = S(64, 16)
    for yy in range(3, 13):
        t = (yy - 3) / 9.0
        col = tuple(int(88 + (34 - 88) * t) for _ in range(1))
        c = (int(88 + (36 - 88) * t), int(92 + (38 - 92) * t), int(84 + (34 - 84) * t))
        pygame.draw.line(s, c + (255,), (0, yy), (64, yy))
    pygame.draw.line(s, (110, 114, 104), (0, 4), (64, 4), 1)
    pygame.draw.line(s, (22, 22, 20, 255), (0, 13), (64, 13), 1)
    pygame.draw.line(s, (22, 22, 20, 255), (0, 2), (64, 2), 1)
    # coupling + bracket
    pygame.draw.rect(s, (78, 82, 74, 255), (29, 1, 6, 14), border_radius=1)
    pygame.draw.rect(s, (24, 24, 22, 255), (29, 1, 6, 14), 1, border_radius=1)
    pygame.draw.circle(s, (28, 28, 26, 255), (32, 14), 2)
    for fx in (0, 61):
        pygame.draw.rect(s, (70, 74, 68, 255), (fx, 0, 3, 16))
    return s


def pipe_v():
    s = pygame.transform.rotate(pipe_h(), -90)
    return s


# ───────────────────────────── comms / office ─────────────────────────────
def rack(frame):
    s = O(64, 192)
    body = (20, 24, 22)
    pygame.draw.rect(s, body + (255,), (6, 0, 52, 188))
    pygame.draw.rect(s, (86, 98, 86, 255), (6, 0, 52, 188), 1)
    pygame.draw.line(s, mix(body, (120, 132, 120), 0.5), (7, 1), (7, 187), 1)
    rnd = random.Random(11)
    y = 5
    u = 0
    while y < 178:
        uh = rnd.choice((12, 16, 20))
        # unit face plate, lighter than the chassis so units read as units
        plate = (44, 54, 50) if u % 2 else (38, 47, 44)
        pygame.draw.rect(s, plate + (255,), (9, y, 46, uh - 3))
        pygame.draw.line(s, lit(plate, 0.22), (9, y), (55, y), 1)
        pygame.draw.line(s, (12, 15, 14, 255), (9, y + uh - 3), (55, y + uh - 3), 1)
        # vent slots on the left two thirds
        for vx in range(12, 36, 4):
            pygame.draw.line(s, shade(plate, 0.55),
                             (vx, y + 3), (vx, y + uh - 6), 1)
        # status LED cluster on the right
        leds = ((80, 220, 120), (220, 180, 60), (80, 220, 120), (200, 70, 60))
        for i, lx in enumerate((44, 49, 53)):
            if frame == 0:
                on = (i + u) % 3 != 2
            elif frame == 1:
                on = (i + u) % 2 == 0
            else:
                on = (i * 2 + u) % 3 != 1
            col = leds[(i + u) % 4]
            c = col if on else shade(col, 0.22)
            pygame.draw.circle(s, c + (255,), (lx, y + (uh - 3) // 2), 1)
            if on:
                g = S(9, 9)
                pygame.draw.circle(g, c + (70,), (4, 4), 4)
                s.blit(g, (lx - 4, y + (uh - 3) // 2 - 4),
                       special_flags=pygame.BLEND_ADD)
        y += uh
        u += 1
    # cable bundle down the right flank
    for i in range(3):
        pygame.draw.lines(s, (20 + i * 8, 22, 26, 220), False,
                          [(58, 8 + i * 40), (62, 28 + i * 40), (58, 52 + i * 40)], 2)
    ao_bottom(s, 12, 120)
    return s


def crt(frame):
    s = O(64, 64)
    pygame.draw.rect(s, (10, 18, 18, 255), (4, 6, 56, 44))
    pygame.draw.rect(s, (66, 95, 88, 255), (4, 6, 56, 44), 1)
    scr = S(48, 34)
    scr.fill((8, 26, 18, 255))
    rnd = random.Random(frame)
    y = 4
    for ln in range(7):
        w = rnd.randint(14, 40)
        pygame.draw.line(scr, (50, 255, 150, 200), (4, y), (4 + w, y), 1)
        y += 4
    pygame.draw.line(scr, (50, 255, 150, 90), (4, 30 - (frame * 7) % 30, ),
                     (44, 30 - (frame * 7) % 30), 2) if False else None
    scan = (frame * 9) % 34
    pygame.draw.line(scr, (120, 255, 180, 60), (0, scan), (48, scan), 1)
    s.blit(scr, (8, 11))
    pygame.draw.line(s, mix((8, 26, 18), (200, 255, 220), 0.25), (8, 11), (30, 11), 1)
    pygame.draw.rect(s, (16, 22, 22, 255), (24, 50, 16, 6))
    pygame.draw.rect(s, (12, 16, 16, 255), (18, 56, 28, 4))
    return s


def cork_board():
    s = O(100, 48)
    s.fill((92, 68, 40, 255))
    grain(s, 300, (70, 50, 28), (120, 92, 58), 3, 40)
    pygame.draw.rect(s, (140, 110, 70, 255), (0, 0, 100, 48), 2)
    papers = ((6, 6, 28, 16, (220, 210, 180)), (38, 8, 24, 14, (200, 190, 160)),
              (66, 6, 26, 18, (210, 200, 170)), (12, 26, 32, 14, (190, 185, 160)),
              (50, 28, 36, 12, (200, 195, 170)))
    for px, py, pw, ph, pc in papers:
        pygame.draw.rect(s, pc + (255,), (px, py, pw, ph))
        pygame.draw.line(s, shade(pc, 0.7) + (255,), (px, py + ph - 1),
                         (px + pw, py + ph - 1), 1)
        for i in range(2):
            pygame.draw.line(s, (120, 115, 100, 160), (px + 3, py + 4 + i * 4),
                             (px + pw - 3, py + 4 + i * 4), 1)
        pygame.draw.circle(s, (160, 40, 40, 255), (px + 3, py + 3), 2)
    return s


def plaque():
    font = pygame.font.Font(os.path.join(FONTS, "IBMPlexMono-SemiBold.ttf"), 13)
    label = font.render("CLERK 07 - RESTRICTED", True, (240, 214, 130))
    w = label.get_width() + 24
    s = S(w, 24)
    pygame.draw.rect(s, (48, 38, 22, 255), (0, 0, w, 24), border_radius=2)
    pygame.draw.rect(s, (180, 150, 70, 255), (0, 0, w, 24), 1, border_radius=2)
    pygame.draw.line(s, (120, 100, 50, 200), (2, 22), (w - 2, 22), 1)
    s.blit(label, (12, 5))
    for cx in (6, w - 6):
        pygame.draw.circle(s, (210, 180, 90, 255), (cx, 12), 2)
    return s


def cab_dossier():
    s = O(40, 110)
    pygame.draw.rect(s, CAB_BODY + (255,), (0, 0, 40, 110), border_radius=2)
    pygame.draw.rect(s, CAB_EDGE + (255,), (0, 0, 40, 110), 1, border_radius=2)
    rnd = random.Random(21)
    for row in range(5):
        ry = 8 + row * 20
        pygame.draw.line(s, (50, 42, 62, 255), (3, ry), (37, ry), 1)
        for b in range(4):
            bc = ((90, 50, 70), (50, 70, 100), (70, 60, 40), (60, 40, 90))[(row + b) % 4]
            h = rnd.randint(10, 14)
            pygame.draw.rect(s, bc + (255,), (5 + b * 8, ry - h, 6, h))
            pygame.draw.line(s, lit(bc, 0.25) + (255,), (5 + b * 8, ry - h),
                             (5 + b * 8, ry - 1), 1)
    pygame.draw.circle(s, (160, 140, 90, 255), (20, 98), 2)
    ao_bottom(s, 8, 90)
    return s


# ───────────────────────────── icons / panel ─────────────────────────────
def _icon_base():
    return S(32, 32)


def i_molotov():
    s = _icon_base()
    pygame.draw.rect(s, (96, 120, 90, 255), (11, 12, 10, 16), border_radius=2)
    pygame.draw.rect(s, (70, 92, 68, 255), (13, 8, 6, 5))
    pygame.draw.line(s, (200, 190, 170, 255), (16, 8), (22, 2), 2)
    pygame.draw.circle(s, (255, 170, 60, 255), (23, 3), 3)
    pygame.draw.line(s, (220, 240, 220, 160), (13, 15), (13, 25), 1)
    return s


def i_dossier():
    s = _icon_base()
    pygame.draw.rect(s, PAPER + (255,), (8, 5, 16, 22), border_radius=1)
    pygame.draw.line(s, RED + (255,), (10, 9), (22, 9), 2)
    for i in range(4):
        pygame.draw.line(s, (120, 108, 84, 220), (10, 13 + i * 3), (22, 13 + i * 3), 1)
    pygame.draw.line(s, shade(PAPER, 0.7) + (255,), (24, 5), (24, 27), 1)
    return s


def i_keycard():
    s = _icon_base()
    pygame.draw.rect(s, (70, 110, 150, 255), (6, 10, 20, 13), border_radius=2)
    pygame.draw.rect(s, (220, 220, 230, 255), (8, 12, 6, 4))
    pygame.draw.line(s, (40, 60, 90, 255), (16, 14), (24, 14), 1)
    pygame.draw.line(s, (40, 60, 90, 255), (16, 17), (24, 17), 1)
    return s


def i_relay():
    s = _icon_base()
    pygame.draw.rect(s, (60, 70, 66, 255), (12, 14, 8, 14))
    pygame.draw.line(s, (200, 200, 210, 255), (16, 14), (16, 6), 2)
    pygame.draw.circle(s, (255, 190, 70, 255), (16, 5), 2)
    for i, r in enumerate((6, 10)):
        pygame.draw.arc(s, (120, 220, 160, 220), (16 - r, 5 - r, r * 2, r * 2),
                        math.radians(200), math.radians(340), 1)
    return s


def i_radio():
    s = _icon_base()
    pygame.draw.rect(s, (52, 56, 60, 255), (9, 10, 14, 18), border_radius=2)
    pygame.draw.rect(s, (120, 200, 140, 255), (11, 12, 10, 5))
    pygame.draw.circle(s, (200, 200, 210, 255), (13, 22), 2)
    pygame.draw.line(s, (200, 200, 210, 255), (21, 10), (25, 3), 2)
    return s


def i_bandage():
    s = _icon_base()
    pygame.draw.rect(s, (220, 210, 190, 255), (6, 12, 20, 9), border_radius=4)
    for dx in (12, 16, 20):
        for dy in (15, 18):
            s.set_at((dx, dy), (160, 150, 130, 255))
    return s


def i_arrow():
    s = _icon_base()
    pygame.draw.polygon(s, (255, 200, 80, 255), [(16, 4), (26, 18), (19, 18),
                                                (19, 28), (13, 28), (13, 18), (6, 18)])
    pygame.draw.polygon(s, (120, 80, 20, 255), [(16, 4), (26, 18), (19, 18),
                                               (19, 28), (13, 28), (13, 18), (6, 18)], 1)
    return s


def door_leaf():
    """Sliding prison door leaf, 56x56; callers blit a left sub-rect whose
    width tracks (1 - open_progress) so the slide keeps all authored detail."""
    s = O(56, 56)
    base = (52, 60, 72)
    dark = (22, 28, 36)
    hi = (82, 92, 108)
    mid = (38, 44, 54)
    s.fill(base)
    pygame.draw.rect(s, dark, (0, 0, 56, 56), 2)
    pygame.draw.line(s, hi, (2, 1), (53, 1), 1)
    pygame.draw.line(s, dark, (2, 54), (53, 54), 1)
    for rx in range(8, 48, 10):
        pygame.draw.line(s, dark, (rx, 6), (rx, 49), 3)
        pygame.draw.line(s, hi, (rx - 1, 6), (rx - 1, 49), 1)
    for frac in (0.33, 0.66):
        by = int(56 * frac)
        pygame.draw.line(s, dark, (4, by), (51, by), 2)
        pygame.draw.line(s, hi, (4, by - 1), (51, by - 1), 1)
    vp = pygame.Rect(6, 8, 26, 15)
    pygame.draw.rect(s, (6, 8, 12), vp)
    pygame.draw.rect(s, (70, 82, 96), vp, 1)
    for bx in range(vp.x + 5, vp.right - 2, 5):
        pygame.draw.line(s, (65, 75, 88), (bx, vp.y + 1), (bx, vp.bottom - 1), 2)
        pygame.draw.line(s, (105, 118, 135), (bx - 1, vp.y + 1), (bx - 1, vp.bottom - 1), 1)
    pygame.draw.rect(s, mid, (40, 30, 11, 16), border_radius=1)
    pygame.draw.rect(s, dark, (40, 30, 11, 16), 1, border_radius=1)
    pygame.draw.circle(s, (190, 200, 214), (45, 38), 2)
    grain(s, 120, shade(base, 0.8), lit(base, 0.12), 71, 20)
    return s


def door_open_inner():
    """Dark doorway with jamb occlusion + lintel highlight, 56x56."""
    s = O(56, 56)
    s.fill((4, 5, 7))
    for i in range(8):
        a = 120 - i * 15
        pygame.draw.line(s, mix((4, 5, 7), (0, 0, 0), 0.0), (i, 0), (i, 56), 1)
        s.set_at((i, 28), mix((4, 5, 7), (0, 0, 0), 0.5 - i * 0.06))
        s.set_at((55 - i, 28), mix((4, 5, 7), (0, 0, 0), 0.5 - i * 0.06))
    pygame.draw.line(s, (58, 62, 70), (0, 0), (55, 0), 1)
    pygame.draw.line(s, (30, 33, 38), (0, 55), (55, 55), 1)
    for i in range(6):
        pygame.draw.line(s, mix((4, 5, 7), (0, 0, 0), 0.6 - i * 0.1),
                         (i, 0), (i, 56), 1)
        pygame.draw.line(s, mix((4, 5, 7), (0, 0, 0), 0.6 - i * 0.1),
                         (55 - i, 0), (55 - i, 56), 1)
    return s


def panel9():
    s = S(24, 24)  # translucent UI panel
    s.fill((16, 17, 20, 225))
    pygame.draw.rect(s, (74, 78, 86, 255), (0, 0, 24, 24), 1)
    pygame.draw.line(s, (120, 126, 138, 200), (1, 1), (22, 1), 1)
    pygame.draw.line(s, (0, 0, 0, 160), (1, 22), (22, 22), 1)
    g = S(24, 8)
    for i in range(8):
        pygame.draw.line(g, (255, 255, 255, int(14 * (1 - i / 8))), (0, i), (24, i))
    s.blit(g, (0, 2))
    return s


# ───────────────────────────── hands / dossier ─────────────────────────────
def _capsule(s, p0, p1, w, col):
    pygame.draw.line(s, col + (255,), p0, p1, w)
    pygame.draw.circle(s, col + (255,), (int(p0[0]), int(p0[1])), w // 2)
    pygame.draw.circle(s, col + (255,), (int(p1[0]), int(p1[1])), w // 2)


def _hand(pose_name):
    """First-person hand, wrist entering from bottom-right, fingers fanning
    up-left. Three-tone: dark outline capsule, skin capsule, rim highlight."""
    w, h = 264, 240
    s = S(w, h)
    sleeve = shade(UNIFORM, 0.62)
    cuff = (40, 44, 36)
    dark = shade(SKIN, 0.62)
    rim = lit(SKIN, 0.30)
    mid = shade(SKIN, 0.86)

    A = math.radians(215)              # forearm axis: up-left
    dx, dy = math.cos(A), math.sin(A)
    px_, py_ = -dy, dx                 # perpendicular
    wrist = (w - 62, h - 52)
    palm_c = (wrist[0] + dx * 46, wrist[1] + dy * 46)

    # sleeve + cuff behind everything
    sl = [(wrist[0] - px_ * 34, wrist[1] - py_ * 34),
          (wrist[0] + px_ * 34, wrist[1] + py_ * 34),
          (w + 10, h - 10 + py_ * 34), (w + 10, h + 20)]
    pygame.draw.polygon(s, sleeve + (255,), sl)
    pygame.draw.polygon(s, cuff + (255,),
                        [(wrist[0] - px_ * 36, wrist[1] - py_ * 36),
                         (wrist[0] + px_ * 36, wrist[1] + py_ * 36),
                         (wrist[0] + px_ * 36 + dx * 16, wrist[1] + py_ * 36 + dy * 16),
                         (wrist[0] - px_ * 36 + dx * 16, wrist[1] - py_ * 36 + dy * 16)])

    curls = {"open": 0.10, "pinch": 0.50, "grip": 0.95, "stamp": 0.30}[pose_name]
    lens = (60, 68, 62, 48)
    widths = (15, 15, 14, 12)

    def finger(bx, by, ang, length, width, curl, thumb=False):
        p = (bx, by)
        a = ang
        for i in range(3):
            sl_ = length / 3.0
            a = a + curl * 0.45
            q = (p[0] + math.cos(a) * sl_, p[1] + math.sin(a) * sl_)
            ww = max(5, int(width * (1 - i * 0.18)))
            _capsule(s, p, q, ww + 3, dark)
            _capsule(s, p, q, ww, SKIN if i == 0 else mid)
            off = (math.cos(a + math.pi / 2) * -ww * 0.28,
                   math.sin(a + math.pi / 2) * -ww * 0.28)
            pygame.draw.line(s, rim,
                             (p[0] + off[0], p[1] + off[1]),
                             (q[0] + off[0], q[1] + off[1]), 2)
            p = q
        # knuckle dot at the tip joint
        pygame.draw.circle(s, shade(SKIN, 0.78), (int(p[0]), int(p[1])), 3)
        return p

    # palm: six-sided slab along the axis, drawn under the fingers
    pts = []
    for t, rr in ((0.0, 30), (0.5, 36), (1.0, 32), (1.0, -32), (0.5, -36), (0.0, -30)):
        pts.append((palm_c[0] + dx * (t * 44 - 8) + px_ * rr,
                    palm_c[1] + dy * (t * 44 - 8) + py_ * rr))
    pygame.draw.polygon(s, dark + (255,),
                        [(x + (x - palm_c[0]) * 0.10, y + (y - palm_c[1]) * 0.10)
                         for x, y in pts])
    pygame.draw.polygon(s, SKIN + (255,), pts)
    pygame.draw.polygon(s, mid + (255,), pts, 2)
    # thenar shading + rim on the top edge
    pygame.draw.ellipse(s, mix(SKIN, mid, 0.5),
                        (int(palm_c[0] - 26), int(palm_c[1] - 6), 44, 30))
    pygame.draw.line(s, rim,
                     (palm_c[0] + px_ * -30, palm_c[1] + py_ * -30),
                     (palm_c[0] + dx * 40 + px_ * -28, palm_c[1] + dy * 40 + py_ * -28), 2)

    # four fingers fanned across the far edge of the palm
    for i in range(4):
        off = (i - 1.5) * 15
        base = (palm_c[0] + dx * 34 + px_ * off,
                palm_c[1] + dy * 34 + py_ * off)
        ang = A + math.radians((i - 1.5) * 7)
        finger(base[0], base[1], ang, lens[i], widths[i], curls)
    # thumb from the near side
    tb = (palm_c[0] + px_ * -30 + dx * 4, palm_c[1] + py_ * -30 + dy * 4)
    finger(tb[0], tb[1], A - math.radians(52), 54, 16,
           0.15 if pose_name != "pinch" else 0.75, thumb=True)
    return s


def _dossier(stamp):
    w, h = 220, 280
    s = S(w, h)
    pygame.draw.rect(s, shade(PAPER, 0.82) + (255,), (4, 4, w - 8, h - 8))
    pygame.draw.rect(s, PAPER + (255,), (0, 0, w - 6, h - 6))
    grain(s, 900, shade(PAPER, 0.8), lit(PAPER, 0.12), 8, 26)
    pygame.draw.line(s, shade(PAPER, 0.7) + (255,), (w - 6, 0), (w - 6, h - 6), 2)
    f1 = pygame.font.Font(os.path.join(FONTS, "IBMPlexMono-Bold.ttf"), 26)
    f2 = pygame.font.Font(os.path.join(FONTS, "IBMPlexMono-Regular.ttf"), 13)
    t = f1.render("VOSTRAL", True, RED)
    s.blit(t, (18, 20))
    pygame.draw.line(s, RED + (255,), (18, 54), (18 + t.get_width(), 54), 2)
    s.blit(f2.render("SERVICE RECORD", True, (110, 96, 70)), (18, 62))
    for i in range(9):
        y = 100 + i * 15
        lw = (150, 170, 140, 160, 120, 165, 150, 130, 90)[i]
        pygame.draw.line(s, (140, 126, 96, 150), (18, y), (18 + lw, y), 1)
    pygame.draw.rect(s, (160, 146, 116, 255), (150, 96, 48, 58), 1)
    pygame.draw.rect(s, (90, 84, 70, 255), (154, 100, 40, 50))
    pygame.draw.circle(s, (120, 112, 96, 255), (174, 118), 10)
    pygame.draw.polygon(s, (120, 112, 96, 255), [(158, 148), (190, 148),
                                                (182, 128), (166, 128)])
    pygame.draw.circle(s, (60, 56, 48), (30, 20), 5)  # punch hole
    if stamp:
        st = S(w, h)
        f3 = pygame.font.Font(os.path.join(FONTS, "IBMPlexMono-Bold.ttf"), 30)
        txt = f3.render(stamp, True, (200, 40, 40, 235))
        pygame.draw.rect(st, (200, 40, 40, 235),
                         (txt.get_rect(center=(w // 2, h - 70)).inflate(24, 14)), 3)
        st.blit(txt, txt.get_rect(center=(w // 2, h - 70)))
        st = pygame.transform.rotate(st, -14)
        s.blit(st, (-(st.get_width() - w) // 2, -(st.get_height() - h) // 2))
    return s


# ───────────────────────────── lights / rain ─────────────────────────────
def L_radial():
    s = O(256, 256)
    s.fill((0, 0, 0))
    for r in range(128, 0, -2):
        a = int(255 * (1 - r / 128) ** 1.8)
        pygame.draw.circle(s, (a, a, a), (128, 128), r)
    return s


def L_cone():
    s = O(256, 512)
    s.fill((0, 0, 0))
    pygame.draw.polygon(s, (210, 210, 210), [(128, 0), (256, 512), (0, 512)])
    s = pygame.transform.smoothscale(s, (64, 128))
    return pygame.transform.smoothscale(s, (256, 512))


def L_dot():
    s = O(48, 48)
    s.fill((0, 0, 0))
    for r in range(24, 0, -1):
        a = int(255 * (1 - r / 24) ** 2.4)
        pygame.draw.circle(s, (a, a, a), (24, 24), r)
    return s


def rain_streak(i):
    """Wind-slanted streak matching the drop velocity (dx = -0.4 * dy).
    i 0-2: length tiers at normal alpha; i 3-5: same lengths, dimmer tier."""
    tier = i % 3
    dim = i >= 3
    ln = (12, 17, 22)[tier]
    w = int(ln * 0.4) + 2
    a = 78 if dim else 112
    s = S(w, ln + 2)
    col = (150, 160, 180, a)
    pygame.draw.line(s, col, (w - 1, 0), (0, ln), 1)
    pygame.draw.line(s, (196, 206, 220, int(a * 0.7)), (w - 1, 0),
                     (w - 3, 4), 1)
    return s


def splash():
    s = S(16, 8)
    pygame.draw.arc(s, (200, 214, 230, 255), (0, 0, 16, 12), math.radians(200),
                    math.radians(340), 1)
    s.set_at((3, 1), (220, 232, 245, 160))
    s.set_at((12, 2), (220, 232, 245, 140))
    return s


def main():
    n = 0
    for code in (".", "g", "O", "d", "s", "L", "Y", "M"):
        for vi in range(4):
            name = "t_%s_%d" % ("dot" if code == "." else code, vi)
            save(name, floor_tile(code, vi)); n += 1
    for code in "KLYM":
        for ab in "ab":
            save("t_%s_%s" % (code, ab), checker_tile(code, ab)); n += 1
    for vi in range(4):
        save("w_C_%d" % vi, wall_tile(vi)); n += 1
    for vi in range(2):
        save("w_B_%d" % vi, barrier_tile(vi)); n += 1
    save("w_S", glass_tile()); n += 1
    for i, seed in enumerate((1, 2, 3)):
        save("shelf_%s" % "abc"[i], shelf_sprite(seed)); n += 1
    save("shelf_top", shelf_top()); n += 1
    save("ladder", ladder()); n += 1
    save("library_cart", library_cart()); n += 1
    save("prop_crate", crate_stack()); n += 1
    save("prop_barrels", barrels()); n += 1
    save("prop_coil", cable_coil()); n += 1
    save("prop_mop", mop_bucket()); n += 1
    save("prop_cart", service_cart()); n += 1
    save("pipe_h", pipe_h()); n += 1
    save("pipe_v", pipe_v()); n += 1
    for f in range(3):
        save("rack_%d" % f, rack(f)); n += 1
    for f in range(4):
        save("crt_%d" % f, crt(f)); n += 1
    save("cork", cork_board()); n += 1
    save("plaque", plaque()); n += 1
    save("cab_dossier", cab_dossier()); n += 1
    for nm, fn in (("molotov", i_molotov), ("dossier", i_dossier),
                   ("keycard", i_keycard), ("relay", i_relay),
                   ("radio", i_radio), ("bandage", i_bandage),
                   ("arrow", i_arrow)):
        save("i_" + nm, fn()); n += 1
    save("panel9", panel9()); n += 1
    save("door_leaf", door_leaf()); n += 1
    save("door_open_inner", door_open_inner()); n += 1
    for p in ("open", "pinch", "grip", "stamp"):
        save("hand_" + p, _hand(p)); n += 1
    for st, nm in ((None, "dossier_plain"), ("EVIDENCE", "dossier_evidence"),
                   ("CONFIRMED", "dossier_confirmed")):
        save(nm, _dossier(st)); n += 1
    save("L_radial", L_radial()); n += 1
    save("L_cone", L_cone()); n += 1
    save("L_dot", L_dot()); n += 1
    for i in range(6):
        save("rain_%d" % i, rain_streak(i)); n += 1
    save("splash", splash()); n += 1
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    print("wrote %d sprites, %.2f MB" % (n, total / 1048576))


if __name__ == "__main__":
    main()

