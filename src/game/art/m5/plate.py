"""HUD status plate (convoy / raid clock), 340 x 46: dark glass, steel rim
with a lit top edge (upper-left key light), empty progress-bar well at
(12, 28, 264, 10). Title, bar fill, readout and heat pips are live data and
are drawn on top by draw._draw_m5_plate."""
import pygame

from game.art.m5 import _kit as K

W, H = 340, 46
VARIANTS = 1
BAR = (12, 28, W - 76, 10)


def render(variant=0, scale=1):
    s = K.new(W, H)
    r = s.get_rect()
    pygame.draw.rect(s, (8, 10, 14, 210), r, border_radius=6)
    pygame.draw.rect(s, (150, 170, 190, 220), r, 1, border_radius=6)
    pygame.draw.line(s, (196, 210, 224, 230), (6, 1), (W - 7, 1), 1)   # lit top lip
    pygame.draw.line(s, (90, 104, 118, 220), (6, H - 2), (W - 7, H - 2), 1)
    pygame.draw.rect(s, (30, 30, 30, 255), BAR)
    pygame.draw.rect(s, (150, 170, 190, 255), BAR, 1)
    return K.scaled(s, scale)
