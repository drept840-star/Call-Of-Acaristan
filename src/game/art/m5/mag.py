"""Maru's thrown magazines (gameplay). Variant 0: K-9 stick mag (12 x 29 px),
variant 1: short 9mm pistol mag (10 x 19 px). Replaces draw._mag_sprite."""
import pygame

from game.art.m5 import _kit as K

VARIANTS = 2


def render(variant=0, scale=1):
    if variant == 0:
        s = K.new(12, 29)
        body = [(2, 4), (10, 4), (9, 25), (3, 25)]
        pygame.draw.polygon(s, (25, 32, 30), body)
        pygame.draw.polygon(s, (82, 98, 90), body, 1)
        pygame.draw.line(s, (48, 60, 56), (4, 6), (4, 23), 1)     # lit left flank
        for ry in (10, 15, 20):
            pygame.draw.line(s, (56, 68, 63), (4, ry), (8, ry), 1)
        for wy in (8, 14, 20):                                   # witness holes
            pygame.draw.circle(s, (166, 137, 55), (7, wy), 1)
        pygame.draw.line(s, (132, 145, 138), (3, 3), (5, 1), 1)  # feed lips
        pygame.draw.line(s, (132, 145, 138), (9, 3), (7, 1), 1)
        pygame.draw.rect(s, (12, 16, 15), (2, 24, 8, 4), border_radius=1)
    else:
        s = K.new(10, 19)
        pygame.draw.rect(s, (30, 32, 34), (2, 3, 6, 13), border_radius=1)
        pygame.draw.rect(s, (92, 96, 100), (2, 3, 6, 13), 1, border_radius=1)
        pygame.draw.circle(s, (176, 142, 60), (5, 3), 2)         # top round
        pygame.draw.rect(s, (14, 15, 16), (1, 15, 8, 3), border_radius=1)
    return K.scaled(s, scale)
