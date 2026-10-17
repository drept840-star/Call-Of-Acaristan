"""decor_paint.py - Mission 5 static set dressing painters (round 2).

Pure painters: each paints world-space props onto a world-size cache surface
(see decor.py). No game state is read here, so this part has no import cycles.
"""
import math
import random

import pygame

from core.config import TILE_SIZE
from missions.m5 import tram_wreck as _tram

C_M5_ARMBAND = (200, 30, 30)   # mirrors draw.C_M5_ARMBAND (draw imports us, not vice versa)

T = TILE_SIZE
_TAR = (38, 38, 42)
_BRICK = (104, 54, 42)
_GUARD_RED = (176, 30, 32)
_KRAP_BLUE = (52, 86, 150)
_fonts = {}

# Solid prop rects (world px). Kept off every NPC tile, spawn and lane.
HQ_SOLIDS = [
    (1 * T + 4, 9 * T, 7 * T - 8, 22),               # locker bank
    (3 * T + 8, 11 * T + 40, 2 * T + 40, 16),          # bench
    (int(14.8 * T), 10 * T + 2, int(1.4 * T), 26),     # sign-up desk
    (24 * T + 4, 10 * T + 2, 2 * T - 8, 22),           # armory workbench
    (int(27.55 * T), 10 * T + 6, int(0.45 * T), 3 * T - 30),  # rifle racks
    (int(27.4 * T), 4 * T, int(0.6 * T), 2 * T),       # filing cabinets
]
Q_SOLIDS = [
    (int(32.15 * T), int(17.7 * T), int(0.8 * T), int(1.9 * T)),   # MAG van
    (int(33.15 * T), int(10.6 * T), int(0.8 * T), int(1.2 * T)),   # paper bales
]
PRINTWORKS_ROOF = pygame.Rect(34 * T, 9 * T, 5 * T, 13 * T)
SIGN_RECT = pygame.Rect(int(31.55 * T), int(13.25 * T), int(2.35 * T), 28)


def font(size):
    if size not in _fonts:
        _fonts[size] = pygame.font.SysFont("consolas,dejavusansmono,monospace", size, bold=True)
    return _fonts[size]


def text(s, txt, pos, col, size=13, center=False, rot=0, alpha=255):
    img = font(size).render(txt, True, col)
    if rot:
        img = pygame.transform.rotate(img, rot)
    if alpha < 255:
        img.set_alpha(alpha)
    if center:
        pos = (pos[0] - img.get_width() // 2, pos[1] - img.get_height() // 2)
    s.blit(img, pos)


def shadow(s, rect, alpha=90):
    r = pygame.Rect(rect)
    sh = pygame.Surface((r.w + 8, r.h + 8), pygame.SRCALPHA)
    pygame.draw.rect(sh, (0, 0, 0, alpha), sh.get_rect(), border_radius=6)
    s.blit(sh, (r.x + 2, r.y + 4))


def box(s, rect, col):
    r = pygame.Rect(rect)
    pygame.draw.rect(s, col, r)
    pygame.draw.line(s, tuple(min(255, c + 26) for c in col), r.topleft, (r.right - 1, r.y))
    pygame.draw.line(s, tuple(max(0, c - 22) for c in col), (r.x, r.bottom - 1),
                     (r.right - 1, r.bottom - 1))
    pygame.draw.rect(s, tuple(max(0, c - 34) for c in col), r, 1)


def _wall_band(s, x0, x1, y, h, split):
    """KRAP blue left of ``split``, Guard black/red right: the repaint is half done."""
    pygame.draw.rect(s, _KRAP_BLUE, (x0, y, split - x0, h))
    pygame.draw.rect(s, (220, 222, 226), (x0, y + h // 2 - 1, split - x0, 3))
    pygame.draw.rect(s, (22, 22, 26), (split, y, x1 - split, h))
    pygame.draw.rect(s, _GUARD_RED, (split, y + h // 2 - 1, x1 - split, 3))
    rnd = random.Random(x0 + y)
    for _ in range(9):
        dx = split - rnd.randint(0, 22)
        pygame.draw.line(s, (22, 22, 26), (dx, y), (dx, y + rnd.randint(3, h)), 2)


def _portrait(s, cx, y, w=34, h=12):
    pygame.draw.rect(s, (150, 120, 60), (cx - w // 2, y, w, h))
    pygame.draw.rect(s, (40, 34, 30), (cx - w // 2 + 3, y + 2, w - 6, h - 4))
    pygame.draw.ellipse(s, (206, 170, 140), (cx - 5, y + 2, 10, h - 4))
    pygame.draw.rect(s, (20, 20, 24), (cx - 7, y + h - 4, 14, 2))


def _banner(s, x, y, length=30):
    pygame.draw.rect(s, (18, 18, 22), (x, y, 14, length))
    pygame.draw.rect(s, _GUARD_RED, (x, y + length // 3, 14, length // 3))
    pygame.draw.circle(s, (200, 170, 90), (x + 7, y + length // 2), 4)


def _flag_stand(s, x, y):
    pygame.draw.circle(s, (60, 54, 44), (x, y), 7)
    pygame.draw.line(s, (180, 160, 110), (x, y), (x + 1, y - 30), 2)
    pygame.draw.rect(s, (18, 18, 22), (x + 2, y - 30, 22, 8))
    pygame.draw.rect(s, _GUARD_RED, (x + 2, y - 22, 22, 8))


def _lamp_post(s, x, y, dy):
    pygame.draw.circle(s, (20, 22, 26), (x, y), 6)
    pygame.draw.circle(s, (70, 72, 78), (x, y), 4)
    pygame.draw.line(s, (60, 62, 68), (x, y), (x, y + dy * 26), 3)
    pygame.draw.rect(s, (30, 30, 34), (x - 7, y + dy * 26 - 4, 14, 8))
    pygame.draw.rect(s, (255, 214, 150), (x - 5, y + dy * 26 - 2, 10, 4))


def _sandbags(s, rect):
    r = pygame.Rect(rect)
    rnd = random.Random(r.x * 7 + r.y)
    for row in range(2):
        y, x = r.y + row * 12, r.x - 6 + row * 9
        while x < r.right + 4:
            w = rnd.choice((16, 18, 20))
            c = 110 + rnd.randint(-10, 10)
            pygame.draw.rect(s, (c - 46, c - 54, c - 70), (x, y, w, 12))          # seam/outline
            pygame.draw.rect(s, (c, c - 12, c - 40), (x + 1, y + 1, w - 2, 9))
            pygame.draw.line(s, (c + 18, c + 6, c - 22), (x + 2, y + 2), (x + w - 3, y + 2))
            pygame.draw.line(s, (c - 30, c - 40, c - 60), (x + w // 2, y + 3), (x + w // 2, y + 8))
            x += w


def _puddle(s, x, y, w, a=46):
    """Hard-edged, stepped water patch (no soft ellipse) + one sky glint line."""
    h = max(6, w // 3)
    p = pygame.Surface((w, h), pygame.SRCALPHA)
    col = (70, 86, 110, a + 50)
    pygame.draw.rect(p, col, (4, 0, w - 10, h))
    pygame.draw.rect(p, col, (0, 2, w, h - 4))
    pygame.draw.line(p, (150, 170, 200, a + 70), (6, 2), (w // 2, 2))
    s.blit(p, (x, y))


# ── Guard HQ ──
def paint_hq(s):
    rnd = random.Random(55)
    # Locker hall: runner, locker bank (names taped over), bench, kit bag.
    runner = pygame.Rect(1 * T + 16, 10 * T + 30, 7 * T - 32, 2 * T + 20)
    pygame.draw.rect(s, (64, 50, 40), runner)                               # worn runner
    pygame.draw.rect(s, (96, 76, 52), runner, 3)
    pygame.draw.rect(s, (52, 40, 32), runner.inflate(-16, -16), 1)
    for i in range(14):
        x = 1 * T + 6 + i * 31
        if x + 28 > 8 * T:
            break
        box(s, (x, 9 * T, 28, 22), (70, 78, 86) if i % 3 else (62, 70, 78))
        for vy in range(9 * T + 4, 9 * T + 12, 3):
            pygame.draw.line(s, (40, 44, 50), (x + 5, vy), (x + 22, vy))
        tape = i in (2, 6, 9)
        pygame.draw.rect(s, (10, 10, 12) if tape else (210, 206, 190),
                         (x + 4, 9 * T + 14, 20, 5))
    bench = HQ_SOLIDS[1]
    shadow(s, bench)
    box(s, bench, (112, 82, 52))
    for k in range(4):
        pygame.draw.line(s, (86, 62, 40), (bench[0], bench[1] + 3 + k * 3),
                         (bench[0] + bench[2] - 1, bench[1] + 3 + k * 3))
    pygame.draw.ellipse(s, (54, 62, 46), (6 * T + 4, 11 * T + 36, 40, 22))
    pygame.draw.circle(s, (210, 210, 200), (3 * T + 2, 12 * T + 10), 5)
    pygame.draw.circle(s, _KRAP_BLUE, (5 * T + 30, 13 * T + 20), 7)          # torn-off patch
    pygame.draw.circle(s, (230, 230, 230), (5 * T + 30, 13 * T + 20), 7, 1)
    box(s, (2 * T + 40, 15 * T - 20, 74, 18), (24, 24, 28))                 # wall TV
    # Corridor: half-done repaint, drop cloth, ladder, paint tins.
    split = int(18.3 * T)
    _wall_band(s, 9 * T, 24 * T, 10 * T, 12, split)
    _wall_band(s, 9 * T, 24 * T, 13 * T - 12, 12, split + 40)
    pygame.draw.rect(s, (182, 180, 170), (split - 50, 10 * T + 12, 110, 40))
    for _ in range(18):
        pygame.draw.circle(s, (24, 24, 28), (split - 46 + rnd.randint(0, 100),
                                             10 * T + 14 + rnd.randint(0, 34)), rnd.randint(1, 3))
    for i in range(6):
        pygame.draw.line(s, (150, 120, 70), (split - 30, 10 * T + 14 + i * 7),
                         (split - 6, 10 * T + 14 + i * 7), 2)
    for lx in (split - 30, split - 6):
        pygame.draw.line(s, (170, 140, 80), (lx, 10 * T + 12), (lx, 10 * T + 52), 3)
    pygame.draw.circle(s, (60, 60, 64), (split + 26, 10 * T + 30), 9)
    pygame.draw.circle(s, (16, 16, 18), (split + 26, 10 * T + 30), 6)
    pygame.draw.circle(s, (60, 60, 64), (split + 44, 10 * T + 40), 8)
    pygame.draw.circle(s, _GUARD_RED, (split + 44, 10 * T + 40), 5)
    for px in (int(11.2 * T), int(20.6 * T)):
        _portrait(s, px, 13 * T - 13)
    _portrait(s, int(17.4 * T), 13 * T - 15, w=44, h=14)
    for bx in (int(12.3 * T), int(15.3 * T), int(21.3 * T)):
        _banner(s, bx, 10 * T + 12)
    nb = int(16.3 * T)                                                       # notice board
    box(s, (nb, 10 * T + 2, 88, 16), (120, 90, 58))
    for i in range(6):
        pygame.draw.rect(s, (226, 224, 214), (nb + 5 + i * 14, 10 * T + 5, 10, 10))
    pygame.draw.line(s, _GUARD_RED, (nb + 33, 10 * T + 5), (nb + 43, 10 * T + 15), 2)
    dx, dy, dw, dh = HQ_SOLIDS[2]                                            # sign-up desk
    shadow(s, (dx, dy, dw, dh))
    box(s, (dx, dy, dw, dh), (92, 66, 46))
    pygame.draw.rect(s, (40, 30, 24), (dx + 6, dy + 4, 22, 16))
    for i in range(4):
        pygame.draw.rect(s, C_M5_ARMBAND, (dx + 8, dy + 6 + i * 3, 18, 2))
    pygame.draw.rect(s, (222, 218, 200), (dx + 40, dy + 5, 26, 16))
    pygame.draw.line(s, (60, 60, 70), (dx + 53, dy + 5), (dx + 53, dy + 21))
    for i in range(5):                                                       # queue tape
        pygame.draw.rect(s, (200, 170, 40), (int(13.2 * T) + i * 24, 12 * T + 44, 12, 4))
    # Briefing room: projector screen with the new crest, lectern, chairs, flags.
    box(s, (12 * T, 2 * T + 2, 5 * T, 14), (226, 226, 230))
    pygame.draw.circle(s, (20, 20, 24), (int(14.5 * T), 2 * T + 9), 6)
    pygame.draw.circle(s, _GUARD_RED, (int(14.5 * T), 2 * T + 9), 3)
    box(s, (int(14.2 * T), 2 * T + 30, 38, 22), (90, 64, 44))
    for cx in range(11, 18):
        for ry in (5.55, 6.45):
            if cx == 12 and ry > 6:
                continue   # the recruit stands here
            box(s, (int(cx * T) + 18, int(ry * T), 26, 20), (58, 62, 70))
    _flag_stand(s, 10 * T + 20, 3 * T)
    _flag_stand(s, 18 * T + 34, 3 * T)
    # Vasile's office: rug, flags, blinds, portrait, cabinets, plant, chair.
    rug = pygame.Rect(int(20.6 * T), int(4.2 * T), int(6.6 * T), int(3.2 * T))
    pygame.draw.rect(s, (92, 30, 32), rug)
    pygame.draw.rect(s, (160, 128, 64), rug, 3)
    pygame.draw.rect(s, (120, 42, 40), rug.inflate(-20, -20), 2)
    _flag_stand(s, 20 * T + 20, 2 * T + 40)
    _flag_stand(s, 27 * T + 10, 2 * T + 40)
    box(s, (int(20.8 * T), 2 * T + 1, int(1.6 * T), 10), (200, 190, 160))
    for i in range(5):
        x = int(20.8 * T) + 3 + i * 20
        pygame.draw.line(s, (120, 110, 90), (x, 2 * T + 2), (x, 2 * T + 10))
    _portrait(s, int(24.5 * T), 2 * T + 1, w=52, h=16)
    for i in range(2):
        cab = (int(27.4 * T), 4 * T + i * T, int(0.6 * T), T - 4)
        box(s, cab, (84, 90, 84))
        for oy in (14, 38):
            pygame.draw.rect(s, (40, 44, 40), (cab[0] + 8, cab[1] + oy, 20, 4))
    pc = (int(21 * T), int(7.4 * T))
    pygame.draw.circle(s, (70, 50, 34), pc, 12)
    for a in range(7):
        pygame.draw.circle(s, (46, 96, 50), (int(pc[0] + math.cos(a * 0.9) * 10),
                                            int(pc[1] + math.sin(a * 0.9) * 10)), 8)
    box(s, (int(23.7 * T), int(4.05 * T), 50, 30), (40, 30, 26))
    # Armory: workbench, rifle racks, ammo crates, motor-pool window.
    wb = HQ_SOLIDS[3]
    box(s, wb, (88, 76, 60))
    for i in range(5):
        pygame.draw.rect(s, (150, 150, 156), (wb[0] + 8 + i * 22, wb[1] + 6, 12, 4))
    rk = HQ_SOLIDS[4]
    box(s, rk, (58, 50, 42))
    for i in range(8):
        y = rk[1] + 6 + i * 20
        pygame.draw.line(s, (24, 24, 26), (rk[0] + 3, y), (rk[0] + rk[2] - 3, y), 4)
        pygame.draw.line(s, (90, 70, 46), (rk[0] + 3, y), (rk[0] + 9, y), 4)
    for cx, cy in ((24.2, 12.6), (24.7, 12.65), (24.3, 12.2)):
        box(s, (int(cx * T), int(cy * T), 30, 20), (70, 84, 50))
        pygame.draw.rect(s, (220, 200, 90), (int(cx * T) + 4, int(cy * T) + 8, 10, 3))
    box(s, (28 * T + 2, int(10.8 * T), 12, int(1.4 * T)), (24, 28, 34))
    for wy in (10.9, 11.5):          # vans outside, freshly painted black
        pygame.draw.rect(s, (12, 12, 14), (28 * T + 4, int(wy * T), 8, 30))
    for _ in range(40):
        x, y = rnd.randint(9 * T, 24 * T), rnd.randint(10 * T + 14, 13 * T - 14)
        pygame.draw.line(s, (60, 64, 70), (x, y), (x + rnd.randint(4, 14), y + rnd.randint(-2, 2)))
    _puddle(s, int(10.5 * T), int(11.8 * T), 46)
    _puddle(s, int(22.2 * T), int(12.1 * T), 30)


# ── Lower Quarter + MAG Print Works exterior ──
def _paint_printworks(s):
    rnd = random.Random(34)
    r = PRINTWORKS_ROOF
    pygame.draw.rect(s, _TAR, r)
    for y in range(r.y, r.bottom, 22):
        pygame.draw.line(s, (30, 30, 34), (r.x, y), (r.right, y))
    for _ in range(900):
        c = rnd.randint(44, 62)
        s.set_at((rnd.randint(r.x, r.right - 1), rnd.randint(r.y, r.bottom - 1)), (c, c, c + 2))
    text(s, "MAG  PRINT  WORKS", (r.centerx + 20, r.centery), (150, 146, 136), size=44,
         center=True, rot=90, alpha=70)
    pygame.draw.rect(s, (112, 96, 82), r, 10)                                  # parapet
    pygame.draw.rect(s, (70, 60, 52), r.inflate(-20, -20), 2)
    for x in range(r.x, r.right, 16):
        pygame.draw.line(s, (88, 74, 62), (x, r.y), (x, r.y + 9))
        pygame.draw.line(s, (88, 74, 62), (x, r.bottom - 10), (x, r.bottom - 1))
    fx = r.x                                                                  # west facade
    pygame.draw.rect(s, _BRICK, (fx, r.y, 22, r.h))
    for y in range(r.y, r.bottom, 8):
        pygame.draw.line(s, (78, 40, 32), (fx, y), (fx + 22, y))
        for x in range(fx + (6 if (y // 8) % 2 else 0), fx + 22, 12):
            pygame.draw.line(s, (78, 40, 32), (x, y), (x, y + 8))
    for row in range(9, 22):
        if row in (15, 18, 19):
            continue
        lit = row in (11, 12, 16, 20)
        pygame.draw.rect(s, (40, 30, 26), (fx + 4, row * T + 12, 14, T - 24))
        pygame.draw.rect(s, (238, 196, 120) if lit else (30, 36, 46),
                         (fx + 6, row * T + 14, 10, T - 28))
        pygame.draw.line(s, (40, 30, 26), (fx + 6, row * T + T // 2), (fx + 16, row * T + T // 2))
    pygame.draw.rect(s, (24, 18, 14), (fx, 15 * T + 4, 22, T - 8))            # door
    pygame.draw.rect(s, (70, 46, 30), (fx + 4, 15 * T + 8, 14, T - 16))
    pygame.draw.line(s, (30, 20, 14), (fx + 4, 15 * T + T // 2), (fx + 18, 15 * T + T // 2), 2)
    pygame.draw.rect(s, (200, 170, 90), (fx + 8, 15 * T + 18, 6, 4))
    for i in range(2):                                                        # steps
        g = 120 - i * 14
        pygame.draw.rect(s, (g, g - 2, g - 8), (fx - 10 - i * 10, 15 * T + 6 - i * 3, 10, T - 12 + i * 6))
    can = pygame.Surface((30, T + 18), pygame.SRCALPHA)                       # canopy
    for i in range(0, T + 18, 9):
        pygame.draw.rect(can, (40, 92, 66, 235) if (i // 9) % 2 else (220, 210, 180, 235), (0, i, 30, 9))
    pygame.draw.rect(can, (20, 30, 24, 255), can.get_rect(), 1)
    s.blit(can, (fx - 26, 15 * T - 9))
    sh = pygame.Rect(fx, 18 * T + 6, 22, 2 * T - 12)                          # loading shutter
    pygame.draw.rect(s, (96, 100, 104), sh)
    for y in range(sh.y, sh.bottom, 5):
        pygame.draw.line(s, (70, 74, 78), (sh.x, y), (sh.right, y))
    text(s, "SAVE THE PRESS", (fx - 4, 18 * T + 64), (200, 40, 40), size=12, center=True, rot=90)
    for row in (11, 14, 17):                                                  # skylights
        sk = pygame.Rect(int(35.4 * T), row * T + 8, int(2.2 * T), T - 16)
        pygame.draw.rect(s, (60, 64, 70), sk.inflate(8, 8))
        pygame.draw.rect(s, (54, 50, 40), sk)
        for i in range(1, 4):
            x = sk.x + i * sk.w // 4
            pygame.draw.line(s, (80, 84, 90), (x, sk.y), (x, sk.bottom), 2)
    ch = pygame.Rect(int(37.6 * T), int(9.5 * T), 40, 40)                     # chimney
    shadow(s, ch, 120)
    pygame.draw.rect(s, (120, 60, 46), ch)
    for y in range(ch.y, ch.bottom, 7):
        pygame.draw.line(s, (86, 40, 32), (ch.x, y), (ch.right, y))
    pygame.draw.rect(s, (20, 18, 18), ch.inflate(-16, -16))
    tk = (int(37.3 * T), int(20.2 * T))                                       # water tank
    pygame.draw.circle(s, (0, 0, 0), (tk[0] + 4, tk[1] + 6), 30)
    pygame.draw.circle(s, (112, 84, 56), tk, 30)
    for rr in (24, 16, 8):
        pygame.draw.circle(s, (88, 64, 42), tk, rr, 2)
    for vx, vy in ((35.0, 10.2), (35.0, 20.6), (37.9, 13.2)):                 # vents
        box(s, (int(vx * T), int(vy * T), 34, 26), (110, 114, 118))
        pygame.draw.circle(s, (60, 62, 66), (int(vx * T) + 17, int(vy * T) + 13), 9)
    box(s, (int(37.6 * T), int(16.4 * T), 30, 30), (80, 70, 56))             # roof hatch
    sg = SIGN_RECT                                                            # blade sign
    pygame.draw.line(s, (40, 40, 44), (sg.right, sg.centery), (fx, sg.centery), 3)
    shadow(s, sg, 140)
    pygame.draw.rect(s, (110, 24, 26), sg)
    pygame.draw.rect(s, (220, 196, 140), sg, 2)
    text(s, "MAG PRINT WORKS", sg.center, (246, 228, 190), size=14, center=True)
    pb = Q_SOLIDS[1]                                                          # paper bales
    for i in range(3):
        for j in range(2):
            b = pygame.Rect(pb[0] + j * 26, pb[1] + i * 25, 24, 22)
            pygame.draw.rect(s, (226, 222, 210), b)
            pygame.draw.rect(s, (160, 156, 146), b, 1)
            pygame.draw.line(s, (150, 110, 60), (b.centerx, b.y), (b.centerx, b.bottom))
    v = pygame.Rect(Q_SOLIDS[0])                                              # MAG van
    shadow(s, v, 130)
    pygame.draw.rect(s, (214, 206, 182), v, border_radius=8)
    pygame.draw.rect(s, (40, 46, 56), (v.x + 5, v.y + 6, v.w - 10, 20), border_radius=4)
    pygame.draw.rect(s, (110, 24, 26), (v.x + 6, v.y + 46, v.w - 12, 34))
    text(s, "MAG", (v.centerx, v.y + 63), (240, 226, 190), size=14, center=True, rot=90)
    pygame.draw.rect(s, (60, 56, 50), v, 2, border_radius=8)


def _paint_tram(s):
    for y in (14.65, 15.35):                                                  # rails
        pygame.draw.line(s, (90, 92, 96), (2 * T, int(y * T)), (int(23.4 * T), int(y * T)), 2)
    pygame.draw.line(s, (90, 92, 96), (int(27.6 * T), int(15.1 * T)), (int(33.5 * T), int(15.1 * T)), 2)
    _tram.bake(s)          # burned-out wreck: see missions/m5/tram_wreck.py


def paint_quarter(s):
    rnd = random.Random(77)
    _paint_tram(s)
    for c, rr in ((9, 14), (9, 16), (20, 14), (20, 15), (30, 15), (30, 16)):
        _sandbags(s, (c * T - 8, rr * T + T - 24, T + 16, 24))
    for c, rr in ((9, 13.4), (20, 13.4), (30, 14.4)):
        _flag_stand(s, c * T + 10, int(rr * T))
    tw = pygame.Rect(int(9.25 * T), int(13.05 * T), 30, 30)                  # floodlight tower
    pygame.draw.rect(s, (40, 42, 46), tw)
    pygame.draw.rect(s, (90, 92, 96), tw, 2)
    pygame.draw.line(s, (90, 92, 96), tw.topleft, tw.bottomright, 2)
    pygame.draw.line(s, (90, 92, 96), tw.topright, tw.bottomleft, 2)
    for c in range(6, 33, 5):                                                 # lamp posts
        _lamp_post(s, c * T + 32, 13 * T + 10, 1)
        _lamp_post(s, c * T + 8, 18 * T - 10, -1)
    sw = pygame.Rect(16 * T, 13 * T - 12, 2 * T, 12)                          # shop window + TV
    pygame.draw.rect(s, (30, 40, 60), sw)
    pygame.draw.rect(s, (130, 120, 100), sw, 2)
    box(s, (int(16.7 * T), 13 * T - 10, 34, 9), (20, 20, 24))
    for c in (7, 11.2, 15, 22.5, 26, 28.4):                                    # posters
        x = int(c * T)
        for y in (13 * T - 9, 18 * T + 1):
            curfew = int(c * 10) % 3 == 0
            from art import m5 as _art                    # baked sprite, old rects as fallback
            spr = _art.get("wall_posters", 5 if curfew else 6)
            if spr is not None:
                s.blit(spr, (x, y))
                continue
            pygame.draw.rect(s, (200, 190, 160) if curfew else (150, 26, 30), (x, y, 26, 8))
            pygame.draw.rect(s, (30, 26, 24), (x + 4, y + 2, 18, 3))
    for c in range(3, 34):                                                    # kerb stones + drains
        for ky in (13 * T + 2, 18 * T - 6):
            pygame.draw.rect(s, (74, 74, 78), (c * T, ky, T - 2, 4))
        if c % 4 == 1:
            gx, gy = c * T + 20, 18 * T - 18
            pygame.draw.rect(s, (22, 22, 24), (gx, gy, 22, 10))
            for k in range(4):
                pygame.draw.line(s, (80, 80, 84), (gx + 3 + k * 5, gy + 1), (gx + 3 + k * 5, gy + 8))
    for c in range(4, 33, 3):                                                 # lane dashes
        pygame.draw.rect(s, (150, 140, 96), (c * T + 8, int(15.0 * T) - 2, 26, 4))
    for _ in range(36):                                                       # MAG leaflets (axis-aligned)
        x = rnd.randint(4 * T, 33 * T) // 4 * 4
        y = (rnd.randint(13 * T + 30, 17 * T + 30) if rnd.random() < 0.7 else rnd.randint(4 * T, 6 * T)) // 4 * 4
        w, h = (8, 6) if rnd.random() < 0.5 else (6, 8)
        pygame.draw.rect(s, (214, 210, 196), (x, y, w, h))
        pygame.draw.line(s, (90, 86, 80), (x + 1, y + 2), (x + w - 2, y + 2))
    for _ in range(8):                                                        # few, crisp puddles
        _puddle(s, rnd.randint(3 * T, 33 * T) // 8 * 8, rnd.randint(13 * T + 40, 17 * T + 20) // 8 * 8,
                rnd.choice((32, 48, 64)), 40)
    gr = random.Random(5)                                                     # graffiti
    for c, r, msg in ((3.1, 12.6, "KRAP = GUARD?"), (13.6, 18.2, "MAG TELLS"),
                      (24.4, 18.2, "NO"), (30.6, 12.6, "FREE PRESS")):
        text(s, msg, (int(c * T), int(r * T)), (gr.choice([(210, 60, 60), (230, 230, 230)])), size=11)
    _paint_printworks(s)
