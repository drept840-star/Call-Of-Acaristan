"""decor_interior.py - Mission 5 interior set dressing (gauntlet pass).

Pure painters for the two stages that used to render as bare tile grids:
the MAG Print Works interior (STAGE_PRINTWORKS + STAGE_RAID share the map)
and the flooded tunnel to the river. Same contract as decor_paint: paint
world-space props onto a cache surface, read no game state, add no solids
(stacked props only sit on tiles that are already solid 'B'/'H'), so
collision, A*, MiniMap and the smoke-test grids are untouched.
"""
import random

import pygame

from core.config import TILE_SIZE
from missions.m5.decor_paint import box, shadow, text, _puddle

T = TILE_SIZE
_PAPER = (214, 208, 190)
_PAPER_D = (176, 170, 152)
_INK = (24, 26, 34)
_STRAP = (150, 40, 34)
_STEEL = (70, 76, 84)
_STEEL_D = (40, 44, 50)
_WOOD = (112, 80, 52)
_HAZ = (196, 160, 40)
_MAG = (230, 190, 120)


def _r(c, r, w=1, h=1, inset=0):
    return pygame.Rect(int(c * T) + inset, int(r * T) + inset, int(w * T) - 2 * inset,
                       int(h * T) - 2 * inset)


# ── props ──
def _baked_bale(r, label):
    try:
        from art import m5 as _art
        from art.m5.bale import variant_for
        v = variant_for(r.w, r.h, label)
        return None if v is None else _art.get("bale", v)
    except Exception:
        return None


def _bale(s, rect, rnd, label=True):
    """Stack of strapped newspaper bundles seen from above."""
    r = pygame.Rect(rect)
    shadow(s, r, 110)
    spr = _baked_bale(r, label)
    if spr is not None:                       # baked sprite (src/game/art/m5/bale.py)
        for _ in range(max(1, r.h // 22)):    # keep the shared rnd stream identical
            rnd.randint(-3, 3)
        s.blit(spr, r.topleft)
        return
    pygame.draw.rect(s, _PAPER_D, r)
    rows = max(1, r.h // 22)
    for i in range(rows):
        y = r.y + i * (r.h // rows)
        hh = r.h // rows - 2
        off = rnd.randint(-3, 3)
        b = pygame.Rect(r.x + 2 + off, y + 1, r.w - 4, hh)
        pygame.draw.rect(s, _PAPER, b)
        pygame.draw.line(s, (236, 232, 218), b.topleft, (b.right - 1, b.y))
        for k in range(3, b.h - 1, 4):                      # page edges
            pygame.draw.line(s, _PAPER_D, (b.x + 2, b.y + k), (b.right - 3, b.y + k))
        pygame.draw.rect(s, _STRAP, (b.x + b.w // 3, b.y, 3, b.h))
        pygame.draw.rect(s, _STRAP, (b.x + 2 * b.w // 3, b.y, 3, b.h))
        pygame.draw.rect(s, (120, 116, 104), b, 1)
    if label and r.w > 40:
        pygame.draw.rect(s, _INK, (r.x + 6, r.y + 6, 26, 11))
        text(s, "MAG", (r.x + 8, r.y + 5), _MAG, size=10)


def _pallet(s, rect, rnd, load=True):
    r = pygame.Rect(rect)
    shadow(s, r, 80)
    for i in range(5):
        pygame.draw.rect(s, (96, 70, 46), (r.x, r.y + i * r.h // 5, r.w, r.h // 5 - 3))
        pygame.draw.line(s, (128, 98, 66), (r.x, r.y + i * r.h // 5), (r.right - 1, r.y + i * r.h // 5))
    pygame.draw.rect(s, (60, 44, 30), r, 1)
    if load:
        _bale(s, r.inflate(-12, -12), rnd, label=rnd.random() < 0.6)


def _press(s, rect, alarm=False):
    """Two-tile offset press: steel bed, ink rollers, paper feed and delivery."""
    r = pygame.Rect(rect)
    shadow(s, r, 130)
    try:                                      # baked sprite (src/game/art/m5/press.py)
        from art import m5 as _art
        spr = _art.get("press", 1 if alarm else 0)
    except Exception:
        spr = None
    if spr is not None and r.size == (116, 52):
        s.blit(spr, (r.x - 18, r.y - 6))
        return
    pygame.draw.rect(s, (20, 22, 26), r.inflate(10, 6))                # base plinth
    pygame.draw.rect(s, _HAZ, r.inflate(16, 12), 2)                     # floor safety line
    box(s, r, _STEEL_D)
    body = r.inflate(-10, -14)
    box(s, body, _STEEL)
    for i in range(5):                                                  # roller train
        x = body.x + 10 + i * (body.w - 20) // 4
        pygame.draw.rect(s, (30, 32, 36), (x - 4, body.y + 2, 8, body.h - 4))
        pygame.draw.rect(s, (130, 134, 140), (x - 2, body.y + 3, 3, body.h - 6))
    pygame.draw.rect(s, _INK, (body.x + 6, body.y + body.h // 2 - 3, body.w - 12, 6))
    feed = pygame.Rect(r.x - 18, r.y + 10, 16, r.h - 20)                # paper feed
    pygame.draw.rect(s, _PAPER, feed)
    pygame.draw.rect(s, _PAPER_D, feed, 1)
    out = pygame.Rect(r.right + 2, r.y + 12, 18, r.h - 24)              # delivery pile
    pygame.draw.rect(s, (236, 232, 218), out)
    for k in range(2, out.h, 3):
        pygame.draw.line(s, _PAPER_D, (out.x + 1, out.y + k), (out.right - 2, out.y + k))
    pygame.draw.rect(s, (200, 40, 34) if alarm else (60, 200, 90), (r.right - 12, r.y + 4, 6, 6))


def _leaflets(s, rect, rnd, n=14, col=_PAPER):
    """Dropped leaflets: few, readable sheets (shadow, headline, text lines)
    instead of a dusting of white specks."""
    r = pygame.Rect(rect)
    for _ in range(max(2, n // 3)):
        w, h = rnd.choice(((16, 12), (12, 16), (18, 13)))
        x = rnd.randint(r.x, max(r.x, r.right - w))
        y = rnd.randint(r.y, max(r.y, r.bottom - h))
        c = tuple(max(0, v - rnd.randint(0, 24)) for v in col)
        skew = rnd.choice((-2, -1, 1, 2))
        pts = [(x, y + skew), (x + w, y), (x + w - skew, y + h), (x - skew, y + h - skew)]
        pygame.draw.polygon(s, (14, 12, 10, 90), [(px + 2, py + 2) for px, py in pts])
        pygame.draw.polygon(s, c, pts)
        pygame.draw.line(s, _STRAP if rnd.random() < 0.5 else _INK, (x + 3, y + 3), (x + w - 4, y + 3), 2)
        for k in range(7, h - 2, 3):
            pygame.draw.line(s, (120, 116, 106), (x + 3, y + k), (x + w - 5, y + k))


def _floors(s, grid, office=None, rnd=None):
    """Painted floor finish under the props: worn concrete slabs in the halls,
    lino checks in the shop, planks in Maru's office, wet screed in corridors.
    Semi-opaque so the tile renderer's own shading still reads through."""
    rnd = rnd or random.Random(311)
    office = pygame.Rect(office) if office else None
    for ry, row in enumerate(grid):
        for cx, ch in enumerate(row):
            x, y = cx * T, ry * T
            if office and office.collidepoint(cx, ry) and ch not in "CHB":
                pygame.draw.rect(s, (92, 66, 44, 215), (x, y, T, T))         # planks
                for k in range(0, T, 12):
                    pygame.draw.line(s, (62, 44, 30, 230), (x, y + k), (x + T - 1, y + k))
                    j = (k * 7 + cx * 23) % T
                    pygame.draw.line(s, (62, 44, 30, 230), (x + j, y + k), (x + j, y + k + 11))
                continue
            if ch in "OPN":
                v = 60 + (cx * 7 + ry * 13) % 7
                pygame.draw.rect(s, (v, v - 4, v - 10, 200), (x, y, T, T))
                if cx % 2 == 0:
                    pygame.draw.line(s, (36, 34, 30, 200), (x, y), (x, y + T - 1))
                if ry % 2 == 0:
                    pygame.draw.line(s, (36, 34, 30, 200), (x, y), (x + T - 1, y))
            elif ch == "F":
                for i in range(2):
                    for j in range(2):
                        c = (78, 72, 62, 205) if (i + j + cx + ry) % 2 else (52, 48, 44, 205)
                        pygame.draw.rect(s, c, (x + i * T // 2, y + j * T // 2, T // 2, T // 2))
            elif ch == "L":
                v = 48 + (cx * 5 + ry * 11) % 6
                pygame.draw.rect(s, (v, v - 2, v - 6, 200), (x, y, T, T))
                if cx % 3 == 0:
                    pygame.draw.line(s, (30, 30, 28, 200), (x, y), (x, y + T - 1))
            elif ch == "D":
                pygame.draw.rect(s, (70, 64, 56, 210), (x, y, T, T))
                pygame.draw.rect(s, (110, 100, 80, 220), (x + 4, y + 4, T - 8, T - 8), 2)
            else:
                continue
            if rnd.random() < 0.22:                                         # wear + oil
                wx, wy = x + rnd.randint(4, T - 24), y + rnd.randint(4, T - 18)
                pygame.draw.ellipse(s, (24, 22, 20, 70), (wx, wy, rnd.randint(14, 26), rnd.randint(8, 14)))
            if rnd.random() < 0.15:
                wx, wy = x + rnd.randint(2, T - 10), y + rnd.randint(2, T - 6)
                pygame.draw.line(s, (90, 86, 78, 120), (wx, wy), (wx + rnd.randint(5, 14), wy + rnd.randint(-3, 3)))


def _poster(s, x, y, w, h, bg, txt, fg=(20, 20, 24)):
    # baked sprite (art.m5.wall_posters) when there is one for this bill
    from art import m5 as _art
    from art.m5.wall_posters import TEXTS
    spr = _art.get("wall_posters", TEXTS[txt]) if txt in TEXTS else None
    if spr is not None and spr.get_size() == (w, h):
        s.blit(spr, (x, y))
        return
    pygame.draw.rect(s, bg, (x, y, w, h))
    pygame.draw.rect(s, tuple(max(0, c - 50) for c in bg), (x, y, w, h), 1)
    text(s, txt, (x + w // 2, y + h // 2), fg, size=9, center=True)


def _rug(s, rect, col):
    r = pygame.Rect(rect)
    pygame.draw.rect(s, col, r)
    pygame.draw.rect(s, tuple(min(255, c + 30) for c in col), r.inflate(-8, -8), 2)
    pygame.draw.rect(s, tuple(max(0, c - 20) for c in col), r, 2)


def _desk(s, rect, rnd):
    r = pygame.Rect(rect)
    shadow(s, r, 120)
    box(s, r, _WOOD)
    pygame.draw.rect(s, (88, 62, 40), r.inflate(-6, -6), 1)
    tw = pygame.Rect(r.x + 14, r.y + 10, 30, 22)                         # typewriter
    box(s, tw, (46, 50, 46))
    for i in range(3):
        pygame.draw.line(s, (150, 150, 140), (tw.x + 4, tw.y + 8 + i * 4), (tw.right - 5, tw.y + 8 + i * 4))
    pygame.draw.rect(s, (236, 232, 218), (tw.x + 5, tw.y - 7, 20, 8))
    _leaflets(s, (r.x + 52, r.y + 6, r.w - 60, r.h - 14), rnd, n=6)
    pygame.draw.circle(s, (30, 30, 30), (r.right - 16, r.y + 16), 7)     # desk lamp
    pygame.draw.circle(s, (255, 220, 150), (r.right - 16, r.y + 16), 4)
    pygame.draw.circle(s, (120, 60, 30), (r.x + 58, r.bottom - 14), 5)   # coffee ring/cup
    pygame.draw.circle(s, (40, 24, 16), (r.x + 58, r.bottom - 14), 3)


def _cot(s, x, y):
    r = pygame.Rect(x, y, 30, 62)
    shadow(s, r, 80)
    box(s, r, (66, 72, 56))
    pygame.draw.rect(s, (190, 186, 172), (x + 4, y + 4, 22, 12))
    pygame.draw.rect(s, (84, 92, 70), (x + 3, y + 22, 24, 36))


def _hazard(s, rect):
    r = pygame.Rect(rect)
    clip = s.get_clip()
    s.set_clip(r)
    for x in range(r.x - r.h, r.right, 16):
        pygame.draw.polygon(s, _HAZ, ((x, r.bottom), (x + 8, r.bottom), (x + 8 + r.h, r.y), (x + r.h, r.y)))
    s.set_clip(clip)
    pygame.draw.rect(s, (30, 26, 14), r, 1)


def _pipe_h(s, x0, x1, y, col=(84, 70, 56), w=8):
    pygame.draw.rect(s, tuple(max(0, c - 30) for c in col), (x0, y, x1 - x0, w))
    pygame.draw.rect(s, col, (x0, y + 1, x1 - x0, w - 3))
    pygame.draw.line(s, tuple(min(255, c + 40) for c in col), (x0, y + 2), (x1, y + 2))
    for x in range(x0 + 20, x1, 96):                                    # flanges/brackets
        pygame.draw.rect(s, (40, 40, 44), (x, y - 2, 6, w + 4))


def _cage_lamp(s, x, y, col=(200, 230, 210)):
    pygame.draw.rect(s, (24, 26, 28), (x - 7, y - 5, 14, 10))
    pygame.draw.rect(s, col, (x - 4, y - 2, 8, 4))
    for k in (-4, 0, 4):
        pygame.draw.line(s, (60, 62, 66), (x + k, y - 5), (x + k, y + 5))


def _ink_stain(s, x, y, w, rnd):
    p = pygame.Surface((w, w // 2), pygame.SRCALPHA)
    for _ in range(4):
        ww = rnd.randint(w // 3, w)
        pygame.draw.rect(p, (10, 12, 18, 110), (rnd.randint(0, w - ww), rnd.randint(0, w // 4), ww, w // 4))
    s.blit(p, (x, y))


# ── MAG Print Works interior (26 x 20) ──
def paint_print(s, alarm=False, grid=None):
    rnd = random.Random(505)
    if grid:
        _floors(s, grid, office=(17, 2, 7, 6))
    # loading bay (F, cols 1-8, rows 15-18): pallets of tonight's run, tyre marks
    for x in (2 * T + 10, 2 * T + 40):                                    # trolley tyre marks
        pygame.draw.line(s, (34, 30, 26, 120), (x, 15 * T + 14), (x + 30, 19 * T - 10), 4)
    pygame.draw.rect(s, (60, 40, 30, 200), _r(1.4, 17.8, 1.4, 0.9))      # door mat
    text(s, "MAG", (int(2.1 * T), int(18.25 * T)), (150, 120, 70), size=10, center=True)
    _hazard(s, (1 * T + 2, 15 * T + 2, 8 * T - 4, 10))
    _pallet(s, _r(5.2, 15.25, 1.3, 1.1), rnd)
    _pallet(s, _r(6.7, 15.25, 1.3, 1.1), rnd)
    _pallet(s, _r(6.7, 17.55, 1.3, 1.1), rnd, load=False)
    _ink_stain(s, 4 * T + 20, 18 * T + 10, 50, rnd)
    hand = pygame.Rect(5 * T + 30, 17 * T + 30, 18, 34)                  # hand truck
    pygame.draw.rect(s, (160, 40, 34), hand, 2)
    pygame.draw.line(s, (160, 40, 34), (hand.x, hand.bottom), (hand.right, hand.bottom), 4)
    _leaflets(s, _r(1.2, 15.6, 3.5, 3.2), rnd, n=10)
    # back corridor (L, cols 10-23, rows 15-18): bundles, notice board, stair
    _pipe_h(s, 10 * T, 24 * T, 15 * T + 2)
    for c in (15, 16):                                                  # strapped bundles on the B blocks
        _bale(s, _r(c, 17, 1, 1, 4), rnd)
    pygame.draw.rect(s, (98, 74, 52), (18 * T, 15 * T + 14, 70, 26))
    for i, col in enumerate(((236, 232, 218), (210, 60, 50), (236, 232, 218))):
        pygame.draw.rect(s, col, (18 * T + 6 + i * 21, 15 * T + 18, 16, 18))
    _hazard(s, (21 * T + 52, 15 * T + 52, 10, T + 24))
    _hazard(s, (23 * T - 2, 15 * T + 52, 10, T + 24))
    text(s, "BASEMENT", (22 * T + 32, 15 * T + 40), (200, 170, 60), size=10, center=True)
    _leaflets(s, _r(10.5, 16.2, 4, 2.4), rnd, n=8)
    # press hall (O, cols 1-15, rows 7-13): three presses per row
    _pipe_h(s, 1 * T, 16 * T, 7 * T + 2, col=(70, 74, 82))
    for row in (8, 11):
        for c in (3, 7, 11):
            _press(s, _r(c, row, 2, 1, 6), alarm)
            _ink_stain(s, c * T + 20, row * T + T + 6, 70, rnd)
    for c in (1.3, 14.2):
        for row in (9.2, 12.2):
            _pallet(s, _r(c, row, 0.9, 0.9), rnd)
    _leaflets(s, _r(1.2, 9.5, 14, 1.2), rnd, n=18)
    _leaflets(s, _r(1.2, 12.4, 14, 1.3), rnd, n=14)
    # paper store (O, cols 1-14, rows 2-5): reels and bales on the B stacks
    for c, r0, h in ((3, 3, 2), (8, 3, 2), (12, 4, 2)):
        _bale(s, _r(c, r0, 1, h, 3), rnd)
    for i in range(4):                                                  # paper reels
        cx, cy = int((5.2 + i * 0.7) * T), int(2.55 * T)
        shadow(s, (cx - 20, cy - 20, 40, 40), 90)
        pygame.draw.circle(s, _PAPER_D, (cx, cy), 20)
        pygame.draw.circle(s, _PAPER, (cx, cy), 17)
        pygame.draw.circle(s, (120, 90, 60), (cx, cy), 6)
    _leaflets(s, _r(1.2, 4.6, 13.5, 1.2), rnd, n=12)
    for i, (bg, t) in enumerate((((210, 60, 50), "FREE"), ((236, 232, 218), "MAG"),
                                 ((40, 50, 80), "TRUTH"))):
        _poster(s, int((2 + i * 4) * T), 2 * T - 2, 54, 16, bg, t,
                fg=(236, 232, 218) if bg[0] < 100 else (20, 20, 24))
    # Maru's back office (O, cols 17-23, rows 2-7)
    _rug(s, _r(18.2, 3.2, 3.6, 3.2), (86, 40, 36))
    pygame.draw.rect(s, (20, 22, 26), _r(19, 5, 2, 1, 2))
    _desk(s, _r(19, 5, 2, 1, 4), rnd)
    for i in range(3):                                                  # filing cabinets
        box(s, (23 * T + 18, int((2.3 + i * 0.8) * T), 40, 46), (82, 88, 80))
        pygame.draw.rect(s, (40, 44, 40), (23 * T + 32, int((2.3 + i * 0.8) * T) + 8, 12, 4))
    _poster(s, 17 * T + 10, 2 * T - 2, 60, 16, (236, 232, 218), "MAG 1991")
    _poster(s, 21 * T + 10, 2 * T - 2, 60, 16, (210, 60, 50), "FREE PRESS",
            fg=(236, 232, 218))
    _leaflets(s, _r(17.3, 6.0, 6, 1.6), rnd, n=10)
    # back room (O, cols 17-24, rows 9-12): the night crew's cots + radio
    for i in range(3):
        _cot(s, int((17.4 + i * 1.1) * T), 9 * T + 10)
    box(s, (22 * T + 6, 9 * T + 12, 70, 40), _WOOD)
    box(s, (22 * T + 14, 9 * T + 18, 30, 20), (40, 44, 40))
    pygame.draw.circle(s, (220, 190, 70), (22 * T + 20, 9 * T + 28), 3)
    _leaflets(s, _r(17.3, 11.3, 7, 1.4), rnd, n=8)


# ── tunnel to the river (48 x 12) ──
def paint_tunnel(s, grid=None):
    rnd = random.Random(707)
    if grid:
        _floors(s, grid)
    rows = len(grid or ())
    for r in range(1, rows - 1):                                        # concrete support ribs
        for c in range(2, len(grid[r]) - 1, 3):
            if grid[r][c] != "C":
                continue
            for nr, y in ((r + 1, (r + 1) * T - 6), (r - 1, r * T - 4)):
                if grid[nr][c] not in "CHB":
                    pygame.draw.rect(s, (70, 64, 58), (c * T + 20, y, 24, 10))
                    pygame.draw.rect(s, (40, 36, 32), (c * T + 20, y, 24, 10), 1)
    for c, r in ((6, 4), (17, 3), (20, 8), (31, 5), (35, 6), (41, 4), (41, 7)):   # on the B debris tiles
        if rnd.random() < 0.5:
            box(s, (c * T + 6, r * T + 6, 30, 26), (96, 72, 48))
            pygame.draw.line(s, (60, 44, 30), (c * T + 6, r * T + 6), (c * T + 36, r * T + 32), 2)
        else:
            shadow(s, (c * T + 6, r * T + 8, 28, 28), 90)
            pygame.draw.circle(s, (70, 80, 64), (c * T + 20, r * T + 22), 13)
            pygame.draw.circle(s, (96, 108, 86), (c * T + 20, r * T + 22), 13, 2)
            pygame.draw.circle(s, (40, 46, 36), (c * T + 20, r * T + 22), 4)
    g_cols = range(1, 47)
    runs = [(1, 14, 4, 7), (10, 28, 2, 9), (24, 38, 4, 7), (38, 47, 3, 8)]
    for c0, c1, r0, r1 in runs:                                         # pipes on both walls
        _pipe_h(s, c0 * T, c1 * T, r0 * T + 2, col=(90, 72, 54))
        _pipe_h(s, c0 * T, c1 * T, (r1 + 1) * T - 12, col=(64, 70, 74), w=6)
        for c in range(c0 + 1, c1, 4):
            _cage_lamp(s, c * T + 32, r0 * T + 16)
        for c in range(c0 + 3, c1, 4):                                   # lower-wall lamps
            _cage_lamp(s, c * T + 32, (r1 + 1) * T - 22)
        for c in range(c0, c1, 2):                                       # damp streaks
            if rnd.random() < 0.4:
                pygame.draw.rect(s, (30, 34, 30, 110), (c * T + rnd.randint(0, 40), r0 * T,
                                                       rnd.randint(8, 18), rnd.randint(14, 30)))
    for txt, (c, r), col in (("KRAP 4", (16, 2), (150, 40, 34)), ("MAG", (30, 4), (230, 190, 120)),
                             ("NEVER FORGET", (8, 4), (200, 200, 190)), ("1989", (43, 3), (150, 40, 34))):
        text(s, txt, (c * T + 10, r * T + 34), col, size=12)
    for c in g_cols:                                                    # old rail along the floor
        if c in range(14, 24):
            continue
        y = int(6.5 * T)
        for k in range(0, T, 16):                                       # sleepers under the rails
            pygame.draw.rect(s, (70, 50, 34), (c * T + k, y - 2, 8, 34))
            pygame.draw.rect(s, (44, 32, 22), (c * T + k, y - 2, 8, 34), 1)
        for ry in (y + 4, y + 22):
            pygame.draw.rect(s, (40, 36, 34), (c * T, ry + 1, T, 4))
            pygame.draw.rect(s, (118, 112, 104), (c * T, ry, T, 3))
            pygame.draw.line(s, (170, 162, 150), (c * T, ry), (c * T + T, ry))
    for _ in range(14):                                                 # puddles + rubble
        c, r = rnd.randint(2, 45), rnd.choice((4, 5, 7, 8))
        _puddle(s, c * T + rnd.randint(0, 30), r * T + rnd.randint(10, 40), rnd.randint(24, 46), a=30)
    for _ in range(40):
        c, r = rnd.randint(2, 45), rnd.choice((3, 4, 7, 8))
        v = rnd.randint(50, 80)
        pygame.draw.rect(s, (v, v - 6, v - 12), (c * T + rnd.randint(0, 56), r * T + rnd.randint(4, 56),
                                                 rnd.randint(3, 7), rnd.randint(3, 6)))
    for x, y in ((8 * T, 7 * T + 40), (19 * T, 2 * T + 30), (42 * T, 7 * T + 40)):   # drains
        pygame.draw.rect(s, (20, 22, 24), (x, y, 30, 14))
        for k in range(4, 30, 6):
            pygame.draw.line(s, (70, 74, 78), (x + k, y + 1), (x + k, y + 12))
    for c, r in ((4, 4), (13, 2), (27, 2), (36, 4), (44, 3)):           # peeling old posters
        x, y = c * T + 14, r * T + 6
        pygame.draw.rect(s, (150, 132, 96), (x, y, 26, 20))
        pygame.draw.rect(s, (150, 40, 34), (x + 2, y + 2, 22, 6))
        pygame.draw.line(s, (90, 80, 60), (x + 3, y + 12), (x + 22, y + 12))
        pygame.draw.polygon(s, (110, 98, 70), ((x + 20, y + 20), (x + 26, y + 14), (x + 26, y + 20)))
    for c in range(2, 46, 5):                                           # stencilled distance marks
        text(s, str(100 + c * 10), (c * T + 20, int(8.5 * T) + 8), (170, 160, 120), size=9)
    text(s, "RAU  ->", (39 * T + 20, 3 * T + 30), (90, 200, 220), size=11)
    text(s, "1957", (12 * T, 2 * T + 22), (120, 112, 100), size=10)


# Lights per interior stage: (x, y, radius, colour, flicker-kind)
PRINT_LIGHTS = (
    [(int(c * T), int(3.6 * T), 170, (255, 214, 150), "") for c in (3.5, 7.5, 11.5)]
    + [(int(c * T), int(r * T), 160, (255, 220, 170), "bad" if (c, r) == (12, 12.4) else "")
       for c in (4, 8, 12) for r in (9.6, 12.4)]
    + [(int(20.4 * T), int(4.6 * T), 190, (255, 200, 130), ""),
       (int(20.5 * T), int(10.6 * T), 160, (255, 214, 160), ""),
       (int(4.5 * T), int(16.6 * T), 190, (220, 230, 255), ""),
       (int(13.5 * T), int(16.6 * T), 150, (255, 214, 150), ""),
       (int(19 * T), int(16.6 * T), 150, (255, 214, 150), ""),
       (int(22.5 * T), int(16.5 * T), 110, (120, 255, 150), "")]
)
RAID_LIGHTS = PRINT_LIGHTS + list(
    [(int(c * T), int(r * T), 200, (255, 40, 40), "sirenA") for c, r in ((1.5, 10), (20, 2.5))]
    + [(int(c * T), int(r * T), 200, (60, 90, 255), "sirenB") for c, r in ((1.5, 16.5), (24.5, 11))]
)
TUNNEL_LIGHTS = (
    [(int(c * T + 32), int(r * T + 52), 140, (250, 200, 130), "bad" if c == 21 else "")
     for c0, c1, r0, _r1 in ((1, 14, 4, 7), (10, 28, 2, 9), (24, 38, 4, 7), (38, 47, 3, 8))
     for c in range(c0 + 1, c1, 4) for r in (r0,)]
    + [(int(c * T + 32), int((r1 + 1) * T - 56), 124, (250, 200, 130), "")
       for c0, c1, _r0, r1 in ((1, 14, 4, 7), (10, 28, 2, 9), (24, 38, 4, 7), (38, 47, 3, 8))
       for c in range(c0 + 3, c1, 4)]
    + [(int(45.5 * T), int(6.5 * T), 220, (120, 220, 240), "")]
)
