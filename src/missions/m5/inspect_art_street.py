"""inspect_art_street.py - storeroom + Lower Quarter inspect shots
(paint tins, shop TV through the shutter, the burned tram). Helpers and the
canvas size come from inspect_art.py.
"""
import math
import random

import pygame

from missions.m5.inspect_art import (CW, CH, GUARD_RED, mix, grad, soft, addlight, blobs,
                                     speckle, text, font, crest, crt, blit_screen)


# -- 4. paint tins --
def _tin(s, cx, by, r, h, shade=1.0, rnd=None, label=True):
    def c(col):
        return tuple(int(v * shade) for v in col)
    ey = int(r * 0.32)
    body = pygame.Rect(cx - r, by - h, 2 * r, h)
    pygame.draw.ellipse(s, c((20, 20, 22)), (cx - r, by - ey, 2 * r, 2 * ey))
    pygame.draw.rect(s, c((46, 46, 50)), body)
    pygame.draw.rect(s, c((76, 76, 82)), (cx - r + int(r * .22), by - h, int(r * .2), h))
    pygame.draw.rect(s, c((28, 28, 31)), (cx + r - int(r * .36), by - h, int(r * .36), h))
    for f in (0.1, 0.9):
        pygame.draw.line(s, c((88, 88, 94)), (cx - r, by - int(h * f)), (cx + r - 1, by - int(h * f)), 2)
    if label:
        ly0, ly1 = by - int(h * 0.8), by - int(h * 0.22)
        off = rnd.randint(-int(r * .1), int(r * .1)) if rnd else 0   # label fits the can (G4)
        s.set_clip(body)
        pygame.draw.rect(s, c((214, 208, 194)), (cx - r, ly0, 2 * r, ly1 - ly0))
        pygame.draw.rect(s, c(GUARD_RED), (cx - r, ly0 + 5, 2 * r, 7))
        fs = max(8, int(r * 0.24))
        lh = ly1 - ly0
        text(s, "GUARD BLACK", fs, c((18, 18, 22)), (cx + off, ly0 + int(lh * .42)), center=True)
        text(s, "40 LITRES", fs, c((18, 18, 22)), (cx + off, ly0 + int(lh * .72)), center=True)
        dk = pygame.Surface((int(r * .36), lh), pygame.SRCALPHA)
        dk.fill((0, 0, 0, 100))
        s.blit(dk, (cx + r - int(r * .36), ly0))
        s.set_clip(None)
    pygame.draw.ellipse(s, c((98, 98, 104)), (cx - r, by - h - ey, 2 * r, 2 * ey))
    pygame.draw.ellipse(s, c((62, 62, 68)), (cx - r + 6, by - h - ey + 3, 2 * r - 12, 2 * ey - 6))


def paint_static(s):
    grad(s, (0, 0, CW, 640), (64, 62, 58), (44, 42, 40))
    grad(s, (0, 640, CW, CH - 640), (72, 70, 66), (46, 44, 42))
    pygame.draw.line(s, (34, 32, 30), (0, 640), (CW, 640), 3)
    blobs(s, (0, 0, CW, 640), 26, (30, 28, 24), 41, 40, 140, 40)
    blobs(s, (0, 650, CW, 260), 12, (30, 28, 26), 42, 30, 90, 50)
    pygame.draw.lines(s, (40, 38, 36), False, [(120, 910), (210, 800), (236, 742), (300, 700)], 2)
    rnd = random.Random(43)
    for row, by in enumerate((612, 502)):                 # the rest of the order, behind
        x = 50 + row * 46
        while x < CW - 20:
            if rnd.random() > 0.12:
                _tin(s, x, by, 44, 108, 0.5, rnd)
            x += 92 + rnd.randint(-4, 6)
    pygame.draw.rect(s, (94, 70, 44), (238, 768, 600, 30))  # pallet
    for xx in range(244, 834, 60):
        pygame.draw.line(s, (66, 48, 30), (xx, 770), (xx, 796), 3)
    for by, xs in ((770, (330, 462, 594, 724)), (616, (398, 528, 662)), (462, (462, 600))):
        for x in xs:
            _tin(s, x + rnd.randint(-5, 5), by, 62, 150, 1.0, rnd)
    # the open one: lid off, brush across the rim, still dripping
    pygame.draw.ellipse(s, (8, 8, 10), (900, 836, 190, 34))
    pygame.draw.ellipse(s, (60, 60, 66), (950, 842, 50, 8))
    _tin(s, 1010, 846, 74, 124, 1.0, rnd)
    ey = int(74 * .32)
    pygame.draw.ellipse(s, (126, 126, 132), (936, 722 - ey, 148, 2 * ey))
    pygame.draw.ellipse(s, (10, 10, 12), (942, 722 - ey + 4, 136, 2 * ey - 8))
    pygame.draw.ellipse(s, (70, 70, 78), (990, 714, 44, 7))
    for dx, ln in ((-52, 46), (-22, 92), (48, 28)):
        x = 1010 + dx
        pygame.draw.rect(s, (10, 10, 12), (x - 4, 726, 9, ln))
        pygame.draw.circle(s, (10, 10, 12), (x, 726 + ln), 6)
        pygame.draw.line(s, (80, 80, 88), (x - 2, 730), (x - 2, 722 + ln), 1)
    pygame.draw.ellipse(s, (96, 96, 102), (1114, 690, 50, 150))     # lid against it
    pygame.draw.ellipse(s, (130, 130, 136), (1120, 696, 38, 138))
    pygame.draw.ellipse(s, (14, 14, 16), (1128, 740, 18, 60))        # paint on the underside
    pygame.draw.line(s, (150, 104, 60), (1046, 716), (1196, 752), 14)  # brush
    pygame.draw.line(s, (176, 176, 182), (1026, 712), (1050, 717), 18)
    pygame.draw.polygon(s, (12, 12, 14), [(980, 696), (1028, 702), (1026, 724), (976, 722)])
    pygame.draw.line(s, (10, 10, 12), (1184, 758), (1186, 790), 4)
    pygame.draw.circle(s, (10, 10, 12), (1186, 792), 4)
    addlight(s, 420, -20, 760, (70, 62, 46))


# -- 5. shop TV through a half-down shutter --
SHOP_SCREEN = (500, 446, 250, 190)
SHOP_TICKER = ("CURFEW IN THE LOWER QUARTER IS FOR YOUR PROTECTION  \u00b7  "
               "MAG PUBLICATIONS ARE NOW CLASSIFIED AS FOREIGN AGITATION  \u00b7  ")
_SHUTTER_Y = 405


def shop_static(s):
    grad(s, (0, 0, CW, CH), (100, 76, 50), (60, 44, 30))
    rnd = random.Random(51)
    for sy in (190, 340, 490):
        pygame.draw.rect(s, (70, 50, 34), (110, sy, 1080, 12))
        x = 124
        while x < 1170:
            w, h = rnd.randint(28, 70), rnd.randint(40, 112)
            col = rnd.choice(((150, 120, 70), (120, 60, 46), (84, 96, 110), (170, 150, 110),
                              (96, 110, 70), (140, 90, 60), (200, 190, 160)))
            pygame.draw.rect(s, col, (x, sy - h, w, h))
            pygame.draw.rect(s, mix(col, (0, 0, 0), .35), (x, sy - h, w, h), 2)
            x += w + rnd.randint(2, 16)
    grad(s, (60, 664, 1180, 246), (122, 88, 56), (78, 56, 36))
    pygame.draw.line(s, (156, 118, 78), (60, 664), (1240, 664), 4)
    tv = pygame.Rect(462, 418, 372, 248)
    pygame.draw.rect(s, (30, 26, 22), tv.move(8, 10), border_radius=18)
    pygame.draw.rect(s, (62, 58, 54), tv, border_radius=18)
    pygame.draw.rect(s, (16, 16, 18), (488, 434, 274, 214), border_radius=18)
    for yy in (470, 530):
        pygame.draw.circle(s, (40, 38, 36), (796, yy), 15)
    pygame.draw.line(s, (40, 38, 36), (650, 418), (610, 330), 3)        # rabbit ears
    pygame.draw.line(s, (40, 38, 36), (660, 418), (740, 344), 3)
    addlight(s, 930, 110, 460, (96, 70, 36))
    # the shutter, pulled half down from the street side
    for yy in range(0, _SHUTTER_Y, 26):
        grad(s, (80, yy, 1140, 26), (140, 142, 146), (88, 90, 96))
        pygame.draw.line(s, (56, 58, 62), (80, yy + 25), (1219, yy + 25), 2)
    blobs(s, (80, 0, 1140, _SHUTTER_Y), 22, (110, 64, 34), 52, 20, 70, 90)
    blobs(s, (680, 220, 200, 120), 2, (40, 40, 44), 53, 40, 60, 80)        # a dent
    pygame.draw.rect(s, (62, 64, 70), (80, _SHUTTER_Y - 6, 1140, 22))
    pygame.draw.rect(s, (40, 42, 46), (80, _SHUTTER_Y + 14, 1140, 3))
    pygame.draw.rect(s, (30, 30, 34), (586, _SHUTTER_Y + 2, 110, 10), border_radius=4)
    for x0, x1 in ((0, 80), (1220, CW)):                                     # window frame
        pygame.draw.rect(s, (24, 22, 24), (x0, 0, x1 - x0, CH))
        pygame.draw.line(s, (70, 74, 86), (x0 + 12, 0), (x0 + 12, CH), 2)
    pygame.draw.rect(s, (30, 30, 34), (0, 866, CW, 44))
    for x in (140, 420, 760, 1060):
        pygame.draw.line(s, (120, 100, 70), (x, 872), (x + 90, 872), 2)


def shop_dyn(s, t):
    x, y, w, h = SHOP_SCREEN
    flick = 0.88 + 0.12 * math.sin(t * 0.031) * math.sin(t * 0.0071)
    scr = pygame.Surface((w, h))
    grad(scr, (0, 0, w, h), (20, 26, 46), (6, 8, 16))
    pygame.draw.rect(scr, (150, 26, 28), (0, 12, w, 36))
    text(scr, "MAG = FOREIGN AGITATION", 17, (248, 242, 232), (w // 2, 30), center=True)
    crest(scr, w // 2, 98, 36)
    pygame.draw.rect(scr, (90, 18, 20), (0, h - 34, w, 24))
    img = font(15).render(SHOP_TICKER, True, (240, 232, 220))
    scr.blit(img, (int(24 - t * 0.085), h - 22 - img.get_height() // 2))
    crt(scr, (0, 0, w, h), t, 3)
    if flick < 0.999:
        scr.fill(tuple(int(255 * flick) for _ in range(3)), special_flags=pygame.BLEND_RGB_MULT)
    blit_screen(s, scr, (x, y), 16)
    addlight(s, x + w // 2, 690, 300, (30, 40, 70), flick)
    lay = pygame.Surface((CW, CH), pygame.SRCALPHA)                       # rain, street side
    rnd = random.Random(77)
    for _ in range(150):
        x0, y0 = rnd.randrange(CW), rnd.randrange(CH)
        v, ln = rnd.uniform(0.9, 1.5), rnd.randint(16, 40)
        yy = (y0 + t * v) % (CH + 60) - 30
        xx = x0 - yy * 0.1
        pygame.draw.line(lay, (180, 190, 210, rnd.randint(40, 90)), (xx, yy), (xx - 4, yy + ln), 1)
    s.blit(lay, (0, 0))


# -- 6. the burned tram --
_WIN_X = (110, 330, 550, 770, 990)
_WIN_Y, _WIN_W, _WIN_H = 282, 180, 200


def tram_static(s):
    grad(s, (0, 0, CW, CH), (14, 16, 26), (30, 24, 24))
    rnd = random.Random(61)
    x = 0
    while x < CW:                                      # far blocks
        w, h = rnd.randint(90, 200), rnd.randint(140, 300)
        pygame.draw.rect(s, (22, 22, 30), (x, 220 - h // 3, w, 600))
        for _ in range(rnd.randint(0, 2)):
            pygame.draw.rect(s, (150, 120, 70), (x + rnd.randint(10, w - 30), 240 - h // 3 + rnd.randint(0, 60), 14, 18))
        x += w + rnd.randint(4, 30)
    grad(s, (0, 800, CW, 110), (34, 30, 30), (16, 14, 14))
    for x in (120, 380, 700, 1000):
        pygame.draw.line(s, (90, 60, 34), (x, 840), (x + 140, 842), 2)
    pygame.draw.rect(s, (52, 54, 58), (60, 206, 1180, 50), border_top_left_radius=26, border_top_right_radius=26)
    pygame.draw.lines(s, (36, 36, 40), False, [(600, 206), (640, 150), (700, 170), (760, 120)], 4)  # pantograph
    grad(s, (60, 256, 1180, 264), (100, 36, 30), (86, 30, 26))
    grad(s, (60, 520, 1180, 40), (168, 150, 112), (140, 124, 92))
    grad(s, (60, 560, 1180, 182), (104, 36, 32), (80, 28, 24))
    pygame.draw.rect(s, (22, 20, 20), (60, 742, 1180, 54))
    for wx in (210, 330, 940, 1060):
        pygame.draw.circle(s, (30, 30, 32), (wx, 792), 38)
        pygame.draw.circle(s, (64, 64, 70), (wx, 792), 38, 4)
    for i, wx in enumerate(_WIN_X):
        r = pygame.Rect(wx, _WIN_Y, _WIN_W, _WIN_H)
        grad(s, r, (24, 26, 36), (14, 12, 12))
        pygame.draw.rect(s, (40, 44, 60), (wx + 20, _WIN_Y + 22, _WIN_W - 40, 60))   # far-side window
        for sx in (wx + 14, wx + 96):                                              # empty seats
            pygame.draw.rect(s, (30, 22, 18), (sx, _WIN_Y + 110, 70, 90), border_top_left_radius=12,
                             border_top_right_radius=12)
            for k in range(3):
                pygame.draw.line(s, (90, 90, 96), (sx + 10 + k * 20, _WIN_Y + 130), (sx + 18 + k * 20, _WIN_Y + 190), 1)
        if i != 2:                                     # glass gone, shards in the frame
            for _ in range(5):
                ex = wx + rnd.randint(0, _WIN_W)
                top = rnd.random() < .5
                ey = _WIN_Y if top else _WIN_Y + _WIN_H
                d = 26 if top else -26
                pygame.draw.polygon(s, (60, 74, 90), [(ex - 12, ey), (ex + 12, ey), (ex + rnd.randint(-8, 8), ey + d + rnd.randint(-10, 10))])
        else:
            g = pygame.Surface((_WIN_W, _WIN_H), pygame.SRCALPHA)
            g.fill((90, 90, 96, 70))
            s.blit(g, r)
            pygame.draw.lines(s, (150, 156, 168), False, [(wx + 40, _WIN_Y + 30), (wx + 80, _WIN_Y + 90), (wx + 70, _WIN_Y + 150), (wx + 120, _WIN_Y + 196)], 1)
        pygame.draw.rect(s, (14, 12, 12), r, 8)
    for i, wx in enumerate(_WIN_X):                    # the fire climbed out of the windows
        blobs(s, (wx - 30, 200, _WIN_W + 60, 120), 4, (8, 6, 6), 62 + i, 60, 120, 170)
    blobs(s, (600, 260, 640, 480), 14, (10, 8, 8), 70, 50, 150, 150)
    blobs(s, (60, 600, 300, 140), 5, (10, 8, 8), 71, 40, 90, 120)
    blobs(s, (120, 230, 1000, 100), 8, (70, 72, 100), 72, 40, 80, 70)
    speckle(s, (60, 256, 1180, 486), 900, [(150, 92, 70), (60, 20, 18), (120, 110, 90)], 73, (1, 3))
    # fresh Guard paint over the scorch
    word = font(108, "head").render("PROVOCATEURS", True, (8, 8, 10))
    over = pygame.transform.smoothscale(word, (word.get_width() // 4, word.get_height() // 4))
    over = pygame.transform.smoothscale(over, word.get_size())
    over.set_alpha(110)
    wx0, wy0 = 300, 570
    s.blit(pygame.transform.rotate(over, 3), (wx0 - 6, wy0 - 4))
    shine = font(108, "head").render("PROVOCATEURS", True, (120, 120, 130))
    s.blit(pygame.transform.rotate(shine, 3), (wx0 - 3, wy0 - 3))
    s.blit(pygame.transform.rotate(word, 3), (wx0, wy0))
    for _ in range(16):                                # runs from the fresh paint
        x = wx0 + 30 + rnd.randint(0, word.get_width() - 60)
        y0 = wy0 + 120 - int((x - wx0) * math.tan(math.radians(3)))
        ln = rnd.randint(14, 70)
        pygame.draw.line(s, (8, 8, 10), (x, y0), (x, y0 + ln), rnd.choice((2, 3)))
        pygame.draw.circle(s, (8, 8, 10), (x, y0 + ln), 3)


def tram_dyn(s, t):
    wx = _WIN_X[3]
    k = 0.7 + 0.3 * math.sin(t * 0.004) * math.sin(t * 0.0013 + 1)
    addlight(s, wx + _WIN_W // 2, _WIN_Y + _WIN_H - 20, 150, (140, 60, 16), k)     # still smouldering
    addlight(s, 650, 960, 700, (60, 26, 8), 0.8 + 0.2 * k)
    rnd = random.Random(81)
    for _ in range(9):                                 # smoke, blowing east
        x0, y0, r = rnd.randrange(CW), rnd.randint(80, 520), rnd.choice((90, 120, 150))
        x = (x0 + t * rnd.uniform(0.02, 0.05)) % (CW + 300) - 150
        s.blit(soft(r, (70, 66, 66), 110), (int(x - r), int(y0 - t * 0.012 - r)))
    for _ in range(60):                                # embers
        x0, y0 = rnd.randrange(80, CW - 80), rnd.randint(300, 800)
        v, ph = rnd.uniform(0.03, 0.08), rnd.uniform(0, 6.28)
        rise = (t * v + ph * 40) % 420
        x = x0 + 14 * math.sin(t * 0.002 + ph) + rise * 0.25
        f = 1 - rise / 420
        col = mix((255, 200, 90), (200, 60, 20), 1 - f)
        pygame.draw.circle(s, col, (int(x), int(y0 - rise)), 2 if f > .4 else 1)
