"""HUD magazine-icon shells (weapon panel). The shell art is static per kind
and state, so it is baked; only the live round count (witness holes / round
stack / shell ports) is overlaid at runtime by draw._draw_m5_mag_icon and
missions/m6/draw._panel_mag_icon.

Variant = kind * 3 + state, kind 0 = stick (K-9 / OS-12), 1 = tapered box
mag, 2 = Fallow 12 shell tube; state 0 = empty, 1 = active, 2 = idle.
Stick sprite: 26 x 55, blit at (mx, my - 3). Box sprite: 25 x 47 at (mx, my).
Shell sprite: 26 x 55, blit at (mx, my - 3); six shell ports at (12, 8 + i*5),
filled bottom-up by the runtime overlay.
Key light upper-left: lit left flank strip on every kind."""
import pygame

from game.art.m5 import _kit as K

VARIANTS = 9
VARIANT_NAMES = {"stick.empty": 0, "stick.active": 1, "stick.idle": 2,
                 "box.empty": 3, "box.active": 4, "box.idle": 5,
                 "shell.empty": 6, "shell.active": 7, "shell.idle": 8}
C_TERMINAL = (50, 255, 150)
STICK_OFFSET = (0, -3)
BOX_OFFSET = (0, 0)
SHELL_OFFSET = (0, -3)


def _stick(state):
    s = K.new(26, 55)
    bx, by, mw, mh = 5, 3, 14, 52
    if state == 0:
        base, rim, hi = (24, 28, 28), (52, 62, 58), (36, 42, 40)
    elif state == 1:
        base, rim, hi = (36, 48, 44), (120, 230, 180), (70, 92, 84)
    else:
        base, rim, hi = (32, 38, 36), (86, 112, 102), (54, 66, 62)
    right, bottom = bx + mw, by + mh
    poly = [(bx + 1, by), (right - 1, by + 1), (right - 3, bottom), (bx + 3, bottom)]
    pygame.draw.polygon(s, base, poly)
    pygame.draw.polygon(s, rim if state == 1 else (64, 70, 66), poly, 1)
    pygame.draw.line(s, hi, (bx + 4, by + 4), (bx + 5, bottom - 5), 1)
    pygame.draw.rect(s, (80, 86, 78), (bx + 2, by - 3, mw - 2, 4), border_radius=1)
    pygame.draw.rect(s, (18, 20, 20), (bx + 1, bottom - 4, mw - 1, 5), border_radius=1)
    for row_i in range(12):                       # empty witness holes
        wy = bottom - 8 - row_i * 3
        for wx_off in (5, 9):
            pygame.draw.circle(s, (18, 20, 20), (bx + wx_off, wy), 1)
    if state == 1:
        pygame.draw.line(s, (120, 230, 180), (right + 3, by + 4), (right + 3, bottom - 4), 2)
    return s


def _box(state):
    s = K.new(25, 47)
    top_w, bot_w, h = 24, 20, 46
    taper = (top_w - bot_w) // 2
    pts = [(0, 0), (top_w, 0), (taper + bot_w, h), (taper, h)]
    if state == 0:
        base, hl, rim = (45, 42, 38), (55, 52, 48), (55, 50, 45)
    elif state == 1:
        base, hl, rim = (90, 86, 78), (115, 110, 100), (70, 66, 58)
    else:
        base, hl, rim = (72, 68, 62), (92, 88, 80), (60, 56, 50)
    pygame.draw.polygon(s, base, pts)
    pygame.draw.polygon(s, hl, [(1, 2), (5, 2), (taper + 3, h - 3), (taper + 1, h - 3)])
    pygame.draw.polygon(s, C_TERMINAL if state == 1 else rim, pts, 1)
    dark = (40, 38, 35) if state == 0 else (55, 52, 48)
    for bi in range(12):                          # empty round stack
        pygame.draw.circle(s, dark, (top_w // 2, 8 + bi * 3), 2)
    return s


def _shell(state):
    """Fallow 12 HUD shells: active (1) is the blued-steel + walnut 6-shell
    tube; empty (0) and idle (2) are the 12-round field shell box."""
    s = K.new(26, 55)
    if state == 1:
        s.fill((74, 82, 92), (10, 0, 5, 2))
        s.fill((58, 66, 76), (5, 2, 15, 4))
        s.fill((112, 124, 138), (5, 2, 14, 1))
        for kx in (7, 10, 13, 16):
            s.fill((34, 38, 44), (kx, 3, 1, 2))
        s.fill((26, 32, 38), (3, 5, 19, 39))
        s.fill((12, 14, 18), (4, 6, 17, 37))
        pygame.draw.rect(s, (120, 230, 180), (3, 5, 19, 39), 1)
        for idx in range(6):
            sy = 37 - idx * 6
            s.fill((18, 21, 26), (5, sy + 1, 15, 3))
            s.fill((38, 44, 52), (5, sy + 1, 3, 3))
            s.fill((48, 56, 66), (11, sy + 2, 3, 1))
        s.fill((118, 72, 40), (3, 44, 19, 8))
        s.fill((152, 98, 56), (3, 44, 18, 1))
        s.fill((142, 90, 50), (3, 44, 1, 7))
        for rx in (6, 10, 14, 18):
            s.fill((76, 44, 26), (rx, 45, 1, 6))
        s.fill((28, 32, 38), (4, 52, 17, 3))
        s.fill((120, 230, 180), (24, 5, 2, 46))
        return s
    has_ammo = state == 2
    if has_ammo:
        s.fill((86, 82, 64), (9, 2, 8, 3))
        s.fill((118, 112, 86), (9, 2, 7, 1))
        s.fill((44, 50, 42), (2, 5, 21, 41))
        pygame.draw.rect(s, (78, 86, 72), (2, 5, 21, 41), 1)
        s.fill((102, 112, 92), (2, 5, 20, 1))
        s.fill((92, 102, 82), (2, 5, 1, 40))
        s.fill((68, 74, 62), (3, 44, 19, 1))
    else:
        s.fill((36, 40, 48), (9, 2, 8, 3))
        s.fill((50, 56, 66), (9, 2, 7, 1))
        s.fill((20, 23, 28), (2, 5, 21, 41))
        pygame.draw.rect(s, (48, 54, 62), (2, 5, 21, 41), 1)
    for idx in range(6):
        sy = 37 - idx * 6
        s.fill((14, 16, 20), (5, sy + 1, 15, 3))
        s.fill((36, 40, 38) if has_ammo else (28, 32, 38), (12, sy, 3, 5))
    return s


def render(variant=0, scale=1):
    kind, state = divmod(int(variant) % VARIANTS, 3)
    if kind == 0:
        art = _stick(state)
    elif kind == 1:
        art = _box(state)
    else:
        art = _shell(state)
    return K.scaled(art, scale)
