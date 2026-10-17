"""m5studio.py - the state-TV studio shared by the M5 bulletin's 3D take
(m5martial3d._bulletin) and its 2D fallback (m5martial._draw_m5_tv_bulletin).

    ANCHOR_WARDROBE    the anchor's look on Vasile's frame (2D + 3D agree)
    news_wall_tex()    the news-wall graphic behind the anchor (full texture)
    draw_bulletin_2d   the 2D fallback composition

Imports m5martial at load time; m5martial imports this module lazily inside
_draw_m5_tv_bulletin only (keeps the import graph acyclic).
"""
import pygame

from core.config import (WIDTH, font_terminal, font_terminal_small)
from cutscenes.cast import draw_balaceanu
from cutscenes.route12 import _draw_vertical_gradient
from cutscenes.m3cell import _m3_clamp01, _m3_noise
from cutscenes.m3ko import _ko_tint
from cutscenes.m5martial import SAFE_TOP, SAFE_BOT, _tag
from engine.text import T as _T  # RPE6 Phase 4 text table

__all__ = ["ANCHOR_WARDROBE", "BULLETIN_CAPTION", "news_wall_tex", "draw_bulletin_2d"]

ANCHOR_WARDROBE = dict(cig=False, epaulets=None, buttons=None, belt=None, stubble=False,
                       coat=(28, 34, 52), lapel=(22, 26, 40), shirt=(228, 228, 232),
                       tie=(160, 28, 30), trousers=(26, 28, 36), hair_style="swept",
                       hair=(150, 146, 140), skin=(222, 186, 160), iris=(70, 60, 50),
                       jaw=0.94, height=248, bulk=0.96)
BULLETIN_CAPTION = "BALACEANU DEATH 'SUICIDE'  \u00b7  MORE AT 22:00"
_TEX = {}


def _greyscale(s):
    try:
        return pygame.transform.grayscale(s)
    except Exception:   # pygame < 2.1.4
        g = s.copy()
        for y in range(g.get_height()):
            for x in range(g.get_width()):
                r, gg, b = g.get_at((x, y))[:3]
                v = int(0.3 * r + 0.59 * gg + 0.11 * b)
                g.set_at((x, y), (v, v, v))
        return g


def news_wall_tex():
    """Balaceanu's official portrait gone grey under a mourning band, the
    state crest, one red BREAKING band. Palette held to state blue + a gold
    accent; red appears only in the band."""
    tex = _TEX.get("news")
    if tex is not None:
        return tex
    w, h = 512, 272
    tex = pygame.Surface((w, h))
    _draw_vertical_gradient(tex, 0, 0, w, h, (28, 52, 98), (9, 18, 40))
    for i, x in enumerate((-60, 30, 140, 205, 330, 410)):          # sweep lines, uneven
        pygame.draw.line(tex, (34, 60, 108) if i % 2 else (31, 56, 102), (x, 0), (x + 120, h), 2)
    cx, cy = int(w * 0.74), int(h * 0.42)                          # the crest, quiet
    pygame.draw.circle(tex, (66, 78, 102), (cx, cy), 80, 4)
    pygame.draw.circle(tex, (30, 46, 82), (cx, cy), 68)
    for dx in (-26, 0, 26):
        pygame.draw.polygon(tex, (156, 132, 82), [(cx + dx, cy - 40), (cx + dx + 11, cy + 4),
                                                  (cx + dx, cy + 40), (cx + dx - 11, cy + 4)])
    px, py, pw, ph = 36, 26, 146, 164                              # official portrait
    pygame.draw.rect(tex, (196, 194, 186), (px - 5, py - 5, pw + 10, ph + 10))
    card = pygame.Surface((pw, ph))
    _draw_vertical_gradient(card, 0, 0, pw, ph, (132, 136, 142), (82, 86, 94))
    # head-and-shoulders crop: the 2D figure is ~281 px tall at scale 1
    draw_balaceanu(card, pw // 2, 12 + int(281 * 1.35), scale=1.35, facing_right=True)
    tex.blit(_greyscale(card), (px, py))
    pygame.draw.polygon(tex, (12, 12, 14), [(px - 5, py + 26), (px + 26, py - 5),
                                            (px + 44, py - 5), (px - 5, py + 44)])
    # text kept short and large: the 3D take samples this at 0.6x
    name = font_terminal.render(_T("m5studio.balaceanu"), True, (236, 236, 232))
    tex.blit(name, (px + pw // 2 - name.get_width() // 2, py + ph + 12))
    pygame.draw.rect(tex, (150, 28, 30), (0, h - 34, w, 34))       # breaking band
    pygame.draw.rect(tex, (176, 146, 86), (0, h - 35, w, 2))
    bt = font_terminal.render(_T("m5studio.breaking"), True, (244, 238, 228))
    tex.blit(bt, (16, h - 17 - bt.get_height() // 2))
    tm = font_terminal.render(_T("m5studio.21_58"), True, (232, 206, 140))
    tex.blit(tm, (w - tm.get_width() - 16, h - 17 - tm.get_height() // 2))
    _TEX["news"] = tex
    return tex


def draw_bulletin_2d(surface, t):
    """2D fallback, same composition as the 3D take: centre wall + news wall,
    two angled flats with light coves, the set ending under a black void with
    a lamp truss, the anchor behind his desk, flag on the left only."""
    from cutscenes import figure_kit  # lazy: only the fallback draws 2D cast
    surface.fill((5, 6, 10))
    top, fy, cx = SAFE_TOP, SAFE_BOT, WIDTH // 2
    fh = fy - top
    set_top = top + int(fh * 0.13)
    cw = int(WIDTH * 0.30)
    ty = top + int(fh * 0.05)
    pygame.draw.line(surface, (30, 31, 36), (0, ty), (WIDTH, ty), 3)          # truss
    for lx in (0.17, 0.41, 0.55, 0.79):
        x = int(WIDTH * lx)
        pygame.draw.rect(surface, (26, 27, 31), (x - 8, ty, 16, 18))
        pygame.draw.rect(surface, (220, 204, 170), (x - 5, ty + 14, 10, 4))
    for s in (-1, 1):                                                          # angled flats
        x0, x1 = cx + s * cw, cx + s * (WIDTH // 2 + 40)
        pygame.draw.polygon(surface, (17, 21, 32), [(x0, set_top), (x1, set_top + 40),
                                                     (x1, fy), (x0, fy)])
        for f in (0.3, 0.64):
            x = int(x0 + (x1 - x0) * f)
            pygame.draw.line(surface, (62, 92, 142), (x, set_top + 30 + int(40 * f)),
                             (x, fy - 30), 2)
    pygame.draw.rect(surface, (22, 28, 42), (cx - cw, set_top - 16, cw * 2, fy - set_top + 16))
    pygame.draw.rect(surface, (12, 14, 20), (cx - cw - 4, set_top - 22, cw * 2 + 8, 8))
    tex = news_wall_tex()
    sw = int(cw * 1.5)
    sh = sw * tex.get_height() // tex.get_width()
    sx, sy = cx - sw // 2, set_top + 6
    pygame.draw.rect(surface, (8, 8, 10), (sx - 6, sy - 6, sw + 12, sh + 12))
    surface.blit(pygame.transform.smoothscale(tex, (sw, sh)), (sx, sy))
    pygame.draw.line(surface, (150, 124, 72), (cx - cw, sy + sh + 14), (cx + cw, sy + sh + 14), 1)
    fx = cx - cw - int(WIDTH * 0.06)                                           # flag
    pygame.draw.line(surface, (150, 140, 108), (fx, set_top - 10), (fx, fy - 20), 3)
    for i in range(4):
        shade = 1.0 - 0.12 * (i % 2)
        pygame.draw.rect(surface, tuple(int(c * shade) for c in (26, 36, 62)),
                         (fx + 3 + i * 10, set_top, 10, 46))
        pygame.draw.rect(surface, tuple(int(c * shade) for c in (150, 30, 32)),
                         (fx + 3 + i * 10, set_top + 46, 10, 46))
    desk_y = fy - int(fh * 0.17)
    head_y = sy + int(sh * 0.40)
    figure_kit.draw_character(surface, "vasile", cx + int(cw * 0.12), fy + 30,
                              scale=(fy + 30 - head_y) / 250.0,
                              facing_right=False, wardrobe=ANCHOR_WARDROBE, t=t, look=0)
    dw = int(cw * 1.1)
    pygame.draw.polygon(surface, (24, 28, 40), [(cx - dw, desk_y), (cx + dw, desk_y),
                                                (cx + int(cw * 1.2), fy), (cx - int(cw * 1.2), fy)])
    pygame.draw.rect(surface, (60, 58, 62), (cx - dw - 4, desk_y - 7, dw * 2 + 8, 9))
    pygame.draw.rect(surface, (226, 224, 216), (cx - 40, desk_y - 9, 80, 3))
    pygame.draw.line(surface, (90, 110, 150), (cx - dw, desk_y + 4), (cx + dw, desk_y + 4), 1)
    pygame.draw.rect(surface, (150, 30, 32), (cx - 80, desk_y + 26, 160, 16))
    pygame.draw.line(surface, (170, 140, 80), (cx - 80, desk_y + 48), (cx + 80, desk_y + 48), 1)
    n = int(len(BULLETIN_CAPTION) * _m3_clamp01((t - 1400) / 1400.0))
    if n:                                                                      # lower third
        bar = pygame.Surface((WIDTH - 120, 30), pygame.SRCALPHA)
        bar.fill((10, 12, 20, 225))
        surface.blit(bar, (60, fy - 44))
        pygame.draw.rect(surface, (220, 90, 70), (60, fy - 44, 4, 30))
        txt = font_terminal_small.render(BULLETIN_CAPTION[:n], True, (220, 90, 70))
        surface.blit(txt, (78, fy - 29 - txt.get_height() // 2))
    _m3_noise(surface, 5151, count=40, alpha=14)
    _ko_tint(surface)
    _tag(surface, "STATE TELEVISION // 21:58")
