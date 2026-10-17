"""inspect_art.py - painters for the Mission 5 first-person inspect shots.

Every shot paints onto an oversized canvas (CW x CH, 1.3x the screen) so the
camera in inspect_fpv.py can push and pan across it. Each shot is split in a
static painter (run once, cached) and an optional dynamic painter (per frame:
tickers, rain, embers). Shared helpers live here; the street/storeroom shots
are in inspect_art_street.py.
"""
import math
import random

import pygame

from core.config import WIDTH, HEIGHT, _load_font, _MONO_B, _DISP

CW, CH = int(WIDTH * 1.3), int(HEIGHT * 1.3)
_fonts = {}
_cache = {}
GUARD_RED = (168, 30, 32)
GOLD = (176, 146, 86)


# -- helpers --
def font(size, kind="mono"):
    """Bundled house faces (IBM Plex Mono Bold / Oswald), like the rest of the
    UI. These painters are frozen into assets/baked/m5/inspect_art_*.png and
    the smoke test compares bake vs live render, so the fonts must not depend
    on what the machine has installed; the system names are a last resort."""
    f = _fonts.get((size, kind))
    if f is None:
        if kind == "mono":
            f = _load_font(_MONO_B, size, "consolas,couriernew,dejavusansmono", True)
        else:
            f = _load_font(_DISP, size, "impact,arialblack,arial")
            f.set_bold(True)   # Oswald emboldened: the Impact-weight headline the shots were cut for
        _fonts[(size, kind)] = f
    return f


def mix(a, b, u):
    return tuple(int(x + (y - x) * u) for x, y in zip(a, b))


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def grad(s, rect, top, bot):
    x, y, w, h = [int(v) for v in rect]
    for i in range(h):
        pygame.draw.line(s, mix(top, bot, i / max(1, h - 1)), (x, y + i), (x + w - 1, y + i))


def soft(r, col, a=255, p=1.6):
    """Radial alpha falloff sprite (2r x 2r)."""
    k = ("soft", r, col, a, p)
    s = _cache.get(k)
    if s is None:
        s = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
        for i in range(r, 0, -1):
            pygame.draw.circle(s, (*col, int(a * (1 - i / r) ** p)), (r, r), i)
        _cache[k] = s
    return s


def addlight(s, cx, cy, r, col, k=1.0):
    """Additive light pool (premultiplied, BLEND_RGB_ADD)."""
    key = ("add", r, col)
    spr = _cache.get(key)
    if spr is None:
        spr = pygame.Surface((2 * r, 2 * r))
        for i in range(r, 0, -2):
            f = (1 - i / r) ** 2
            pygame.draw.circle(spr, tuple(int(c * f) for c in col), (r, r), i)
        _cache[key] = spr
    if k < 0.999:
        spr = spr.copy()
        spr.fill(tuple(int(255 * max(0.0, k)) for _ in range(3)), special_flags=pygame.BLEND_RGB_MULT)
    s.blit(spr, (int(cx - r), int(cy - r)), special_flags=pygame.BLEND_RGB_ADD)


def blobs(s, rect, n, col, seed, rmin=30, rmax=120, a=60):
    rnd = random.Random(seed)
    x, y, w, h = rect
    for _ in range(n):
        r = max(10, int(rnd.randint(rmin, rmax) // 10 * 10))
        s.blit(soft(r, col, a), (x + rnd.randrange(max(1, w)) - r, y + rnd.randrange(max(1, h)) - r))


def speckle(s, rect, n, cols, seed, size=(1, 2)):
    rnd = random.Random(seed)
    x, y, w, h = rect
    for _ in range(n):
        r = rnd.randint(*size)
        pygame.draw.rect(s, rnd.choice(cols), (x + rnd.randrange(w), y + rnd.randrange(h), r, r))


def text(s, txt, size, col, pos, kind="mono", center=False, alpha=255, angle=0):
    img = font(size, kind).render(txt, True, col)
    if angle:
        img = pygame.transform.rotate(img, angle)
    if alpha < 255:
        img.set_alpha(alpha)
    x, y = pos
    if center:
        x, y = x - img.get_width() // 2, y - img.get_height() // 2
    s.blit(img, (int(x), int(y)))
    return img.get_size()


def crest(s, cx, cy, r, ring=GUARD_RED, fill=(24, 20, 26), gold=GOLD):
    """Guard crest: the state's three gold diamonds inside a red ring."""
    pygame.draw.circle(s, ring, (cx, cy), r)
    pygame.draw.circle(s, fill, (cx, cy), int(r * 0.84))
    d, hh, ww = int(r * 0.32), int(r * 0.5), int(r * 0.14)
    for dx in (-d, 0, d):
        pygame.draw.polygon(s, gold, [(cx + dx, cy - hh), (cx + dx + ww, cy + int(r * .05)),
                                      (cx + dx, cy + hh), (cx + dx - ww, cy + int(r * .05))])


def crt(s, rect, t, seed=0):
    """Scanlines, a slow roll bar and a corner glare over a CRT picture."""
    x, y, w, h = rect
    key = ("scan", w, h)
    sc = _cache.get(key)
    if sc is None:
        sc = pygame.Surface((w, h), pygame.SRCALPHA)
        for yy in range(0, h, 3):
            pygame.draw.line(sc, (0, 0, 0, 70), (0, yy), (w, yy))
        pygame.draw.polygon(sc, (255, 255, 255, 16), [(0, 0), (int(w * .42), 0), (int(w * .18), h // 2), (0, int(h * .62))])
        _cache[key] = sc
    s.blit(sc, (x, y))
    ry = int((t * 0.05 + seed * 97) % (h + 60)) - 30
    bar = pygame.Surface((w, 26), pygame.SRCALPHA)
    bar.fill((255, 255, 255, 12))
    s.blit(bar, (x, y + ry))


def rounded_mask(w, h, rad):
    key = ("mask", w, h, rad)
    m = _cache.get(key)
    if m is None:
        m = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(m, (255, 255, 255, 255), (0, 0, w, h), border_radius=rad)
        _cache[key] = m
    return m


def blit_screen(s, scr, pos, rad):
    w, h = scr.get_size()
    a = _to_alpha(scr)
    a.blit(rounded_mask(w, h, rad), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    s.blit(a, pos)


def _to_alpha(scr):
    a = pygame.Surface(scr.get_size(), pygame.SRCALPHA)
    a.blit(scr, (0, 0))
    return a


def pin(s, x, y, col=(186, 40, 36)):
    s.blit(soft(10, (0, 0, 0), 140), (x - 6, y - 4))
    pygame.draw.circle(s, mix(col, (0, 0, 0), .35), (x, y + 1), 9)
    pygame.draw.circle(s, col, (x, y), 8)
    pygame.draw.circle(s, mix(col, (255, 255, 255), .55), (x - 3, y - 3), 3)


def rot_blit(s, surf, angle, center):
    img = pygame.transform.rotate(surf, angle)
    s.blit(img, img.get_rect(center=center))


def shadow_of(surf, a=90):
    sh = surf.copy()
    sh.fill((0, 0, 0, a), special_flags=pygame.BLEND_RGBA_MULT)
    return sh


def type_bars(s, x, y, rows, rnd, col, step=22, maxw=300):
    """Illegible typed lines (old notices, small print)."""
    for i in range(rows):
        w = rnd.randint(int(maxw * .45), maxw)
        xx = x
        while xx < x + w:
            ww = rnd.randint(14, 46)
            pygame.draw.rect(s, col, (xx, y + i * step, min(ww, x + w - xx), 6))
            xx += ww + rnd.randint(5, 9)


# -- 1. notice board --
def _strike(p, x0, x1, y, rnd, heavy=False):
    col = (178, 28, 30)
    if heavy:      # scribbled out until nothing reads
        pts, x = [], x0 - 6
        while x < x1 + 8:
            pts.append((x, y + rnd.randint(-13, 11)))
            x += rnd.randint(9, 16)
        pygame.draw.lines(p, col, False, pts, 5)
        pygame.draw.lines(p, (150, 22, 26), False, [(a + 5, b + 4) for a, b in pts], 3)
    else:
        a = rnd.uniform(-4, 4)
        pts = [(x0 - 10, y + a), ((x0 + x1) / 2, y + a * .3 + rnd.uniform(-2, 2)), (x1 + 12, y - a)]
        pygame.draw.lines(p, col, False, pts, 5)


def notice_static(s):
    grad(s, (0, 0, CW, CH), (80, 86, 80), (50, 54, 50))
    blobs(s, (0, 0, CW, CH), 30, (24, 26, 22), 11, 40, 140, 50)
    bx, by, bw, bh = 110, 60, 1080, 790
    pygame.draw.rect(s, (66, 44, 26), (bx - 24, by - 24, bw + 48, bh + 48))
    pygame.draw.line(s, (122, 88, 56), (bx - 22, by - 22), (bx + bw + 22, by - 22), 3)
    pygame.draw.line(s, (40, 26, 16), (bx - 22, by + bh + 22), (bx + bw + 22, by + bh + 22), 4)
    grad(s, (bx, by, bw, bh), (160, 120, 78), (134, 98, 60))
    speckle(s, (bx, by, bw, bh), 4200, [(110, 78, 46), (178, 140, 96), (96, 66, 40), (146, 108, 68)], 12)
    rnd = random.Random(13)
    for _ in range(46):          # holes from a hundred old notices
        pygame.draw.circle(s, (72, 50, 30), (bx + rnd.randrange(bw), by + rnd.randrange(bh)), 2)
    # an older notice behind, mostly covered, and a small card bottom right
    back = pygame.Surface((380, 500), pygame.SRCALPHA)
    grad(back, (0, 0, 380, 500), (206, 192, 150), (180, 164, 122))
    pygame.draw.rect(back, (96, 86, 70), (28, 30, 220, 16))
    type_bars(back, 28, 80, 17, random.Random(14), (118, 106, 88), 24, 320)
    rot_blit(s, shadow_of(back, 70), 5, (412, 412))
    rot_blit(s, back, 5, (404, 404))
    card = pygame.Surface((190, 120), pygame.SRCALPHA)
    grad(card, (0, 0, 190, 120), (196, 204, 210), (172, 180, 186))
    type_bars(card, 14, 18, 5, random.Random(16), (90, 96, 104), 18, 160)
    rot_blit(s, shadow_of(card, 70), -7, (1046, 738))
    rot_blit(s, card, -7, (1040, 732))
    pin(s, 1010, 690, (60, 110, 170))
    # the transfer list
    pw, ph = 540, 720
    p = pygame.Surface((pw, ph), pygame.SRCALPHA)
    grad(p, (0, 0, pw, ph), (234, 230, 216), (212, 206, 188))
    pygame.draw.line(p, (198, 192, 174), (0, ph // 2 + 6), (pw, ph // 2 - 4), 2)   # fold
    text(p, "KRAP SQUAD 4", 56, (28, 30, 36), (pw // 2, 72), kind="head", center=True)
    text(p, "- TRANSFERRED -", 26, (44, 44, 50), (pw // 2, 128), center=True)
    pygame.draw.line(p, (60, 60, 66), (40, 158), (pw - 40, 158), 2)
    rows = (("KOVAC", 1), (None, 2), ("SANDU", 1), (None, 2), (None, 2), (None, 2), ("BIRIBEL", 0))
    rnd = random.Random(15)
    for i, (name, cross) in enumerate(rows):
        y = 196 + i * 64
        text(p, "%02d." % (i + 1), 22, (74, 74, 80), (50, y + 4))
        if name:
            w, _h = text(p, name, 32, (26, 28, 34), (118, y - 4))
        else:
            w = rnd.randint(150, 240)
            type_bars(p, 118, y + 8, 1, rnd, (52, 54, 62), 0, w)
        if cross:
            _strike(p, 118, 118 + w, y + 13, rnd, heavy=cross == 2)
    torn = [(pw, ph - 170), (pw - 22, ph - 140), (pw - 38, ph - 118), (pw - 70, ph - 92),
            (pw - 96, ph - 58), (pw - 130, ph - 36), (pw - 176, ph), (pw, ph)]
    pygame.draw.polygon(p, (0, 0, 0, 0), torn)
    pygame.draw.lines(p, (246, 242, 232), False, torn[:-1], 2)
    rot_blit(s, shadow_of(p, 100), -1.6, (662, 484))
    rot_blit(s, p, -1.6, (650, 470))
    pin(s, 404, 134)
    pin(s, 894, 122)
    pin(s, 300, 176, (210, 180, 60))
    addlight(s, 560, 120, 620, (40, 36, 26))


# -- 2. HQ TV on its bracket --
TV_SCREEN = (356, 224, 528, 384)
TV_TICKER = ("...THE REPUBLICAN GUARD THANKS KRAP FOR ITS YEARS OF SERVICE  \u00b7  "
             "PATRIOTS WILL BE WELCOMED INTO THE NEW STRUCTURE...")


def tv_static(s):
    grad(s, (0, 0, CW, CH), (50, 54, 62), (28, 30, 36))
    pygame.draw.polygon(s, (36, 38, 46), [(0, 0), (CW, 0), (CW, 84), (0, 136)])     # ceiling
    pygame.draw.line(s, (66, 70, 80), (0, 136), (CW, 84), 3)
    blobs(s, (0, 140, CW, CH), 18, (18, 20, 24), 21, 50, 150, 45)
    pygame.draw.rect(s, (56, 60, 68), (1080, 96, 84, 150))                          # wall plate
    for by in (112, 226):
        pygame.draw.circle(s, (88, 92, 100), (1098, by), 5)
        pygame.draw.circle(s, (88, 92, 100), (1146, by), 5)
    pygame.draw.polygon(s, (74, 78, 86), [(1080, 150), (1080, 186), (1000, 300), (968, 280)])
    pygame.draw.polygon(s, (50, 54, 62), [(1080, 186), (1092, 200), (1012, 312), (1000, 300)])
    pygame.draw.rect(s, (52, 56, 64), (262, 722, 800, 22))                         # shelf
    pygame.draw.polygon(s, (44, 48, 56), [(1062, 744), (1062, 760), (1150, 860), (1150, 830)])
    body = pygame.Rect(290, 170, 740, 552)
    pygame.draw.rect(s, (18, 18, 20), body.move(12, 16), border_radius=30)
    pygame.draw.rect(s, (60, 60, 64), body, border_radius=30)
    pygame.draw.rect(s, (82, 82, 88), (body.x + 10, body.y + 6, body.w - 20, 22), border_radius=11)
    pygame.draw.rect(s, (42, 42, 46), (body.x, body.bottom - 46, body.w, 46),
                     border_bottom_left_radius=30, border_bottom_right_radius=30)
    pygame.draw.rect(s, (16, 16, 18), (336, 204, 568, 424), border_radius=34)        # bezel
    for yy in (276, 368):                                                          # knobs
        pygame.draw.circle(s, (30, 30, 34), (966, yy + 3), 24)
        pygame.draw.circle(s, (40, 40, 44), (964, yy), 23)
        pygame.draw.line(s, (120, 120, 126), (964, yy), (964 + int(16 * math.cos(yy)), yy - 15), 3)
    for yy in range(440, 650, 12):                                                 # grille
        pygame.draw.line(s, (36, 36, 40), (930, yy), (1000, yy), 5)
    pygame.draw.rect(s, (200, 196, 184), (930, 664, 66, 22))                       # asset tag
    type_bars(s, 936, 671, 1, random.Random(22), (90, 90, 96), 0, 52)


def tv_dyn(s, t):
    x, y, w, h = TV_SCREEN
    scr = pygame.Surface((w, h))
    grad(scr, (0, 0, w, h), (18, 24, 44), (6, 8, 16))
    crest(scr, w // 2, 146, 92)
    text(scr, "REPUBLICAN GUARD", 22, (198, 170, 106), (w // 2, 262), center=True)
    pygame.draw.rect(scr, GOLD, (0, h - 64, w, 2))
    pygame.draw.rect(scr, (128, 24, 26), (0, h - 62, w, 38))
    img = font(22).render(TV_TICKER, True, (246, 238, 226))
    scr.blit(img, (int(70 - t * 0.11), h - 43 - img.get_height() // 2))
    text(scr, "VOL", 18, (130, 230, 150), (18, 16))
    for i in range(20):                                    # volume all but gone
        pygame.draw.rect(scr, (130, 230, 150) if i < 2 else (34, 62, 42), (64 + i * 11, 19, 7, 14))
    crt(scr, (0, 0, w, h), t)
    blit_screen(s, scr, (x, y), 30)
    addlight(s, x + w // 2, y + h // 2, 420, (16, 22, 40))


# -- 3. the president's portrait --
_PALE = pygame.Rect(410, 112, 480, 590)


def portrait_static(s):
    from cutscenes import figure_kit  # lazy: cast art only when the shot is built
    wall = (146, 152, 128)
    grad(s, (0, 0, CW, 760), wall, (120, 126, 106))
    grad(s, (0, 760, CW, CH - 760), (70, 84, 72), (50, 60, 52))
    pygame.draw.rect(s, (96, 104, 88), (0, 752, CW, 12))
    blobs(s, (0, 0, CW, 760), 60, (60, 62, 44), 31, 40, 140, 38)
    speckle(s, (0, 0, CW, 760), 1600, [(118, 122, 100), (162, 166, 142)], 32)
    # where the KRAP crest hung: the wall stayed clean behind it
    pale = (168, 172, 148)
    for i, c in enumerate((mix(wall, pale, .35), mix(wall, pale, .7), pale)):
        pygame.draw.rect(s, c, _PALE.inflate(-i * 4, -i * 4), border_radius=6)
    ring = pygame.Surface((440, 440), pygame.SRCALPHA)
    pygame.draw.circle(ring, (90, 94, 74, 40), (220, 220), 214, 7)
    s.blit(ring, (_PALE.centerx - 220, _PALE.centery - 236))
    for hx, hy in ((432, 134), (868, 130), (436, 680), (864, 684), (650, 126)):
        pygame.draw.circle(s, (196, 198, 180), (hx + 1, hy + 1), 7)
        pygame.draw.circle(s, (44, 40, 32), (hx, hy), 4)
    pygame.draw.line(s, (120, 120, 116), (868, 130), (874, 120), 3)        # a nail left in
    # new gilt frame, hung a little off-centre over the old patch
    fx, fy, fw, fh = 500, 186, 304, 408
    sh = pygame.Surface((fw, fh), pygame.SRCALPHA)
    sh.fill((0, 0, 0, 90))
    s.blit(sh, (fx + 12, fy + 16))
    for i, c in enumerate(((104, 78, 32), (176, 140, 62), (232, 200, 120), (204, 166, 86),
                           (150, 116, 50), (96, 72, 28))):
        pygame.draw.rect(s, c, (fx + i * 4, fy + i * 4, fw - i * 8, fh - i * 8), 4)
    for cx, cy in ((fx + 4, fy + 4), (fx + fw - 5, fy + 4), (fx + 4, fy + fh - 5), (fx + fw - 5, fy + fh - 5)):
        pygame.draw.circle(s, (236, 206, 128), (cx, cy), 7)
    cw, chh = fw - 48, fh - 48
    card = pygame.Surface((cw, chh))
    grad(card, (0, 0, cw, chh), (120, 32, 34), (56, 16, 18))
    # official head-and-shoulders crop: draw him big, measure where the head
    # really starts, and hang that 22 px under the frame
    # (figure_kit direct: the cached cast wrapper clips figures past ~460 px)
    fig = pygame.Surface((cw, 1400), pygame.SRCALPHA)
    figure_kit.draw_character(fig, "president", cw // 2, 1390, scale=2.5, facing_right=True,
                              look=0)
    top = fig.get_bounding_rect(min_alpha=40).top
    card.blit(fig, (0, 22 - top))
    glare = pygame.Surface((cw, chh), pygame.SRCALPHA)
    pygame.draw.polygon(glare, (255, 255, 255, 22), [(0, 0), (int(cw * .5), 0), (0, int(chh * .55))])
    card.blit(glare, (0, 0))
    s.blit(card, (fx + 24, fy + 24))
    pygame.draw.rect(s, (196, 166, 92), (594, 616, 116, 26))
    pygame.draw.rect(s, (140, 112, 52), (594, 616, 116, 26), 2)
    text(s, "RETARDOVICI", 15, (40, 30, 14), (652, 629), center=True)
    addlight(s, 650, 40, 640, (34, 32, 24))
