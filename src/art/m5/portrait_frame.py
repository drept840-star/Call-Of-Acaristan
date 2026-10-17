"""Official portrait of President Retardovici in a gilt frame (30 x 30 px, 1.0 x 1.0 m).
Frame bevel and the sitter's key light both come from the upper-left."""
import pygame

from art.m5 import _kit as K

W, H = 30, 30
VARIANTS = 1


def render(variant=0, scale=1):
    s = K.new(W, H, K.BRASS)
    K.bevel(s, (0, 0, W, H), K.GOLD_HI, K.GOLD_LO, 2)
    s.fill(K.GOLD_LO, (3, 3, W - 6, 1)); s.fill(K.GOLD_LO, (3, 3, 1, H - 6))   # inner lip (shaded)
    s.fill(K.GOLD_HI, (3, H - 4, W - 6, 1)); s.fill(K.GOLD_HI, (W - 4, 3, 1, H - 6))
    s.fill((54, 64, 58), (4, 4, W - 8, H - 8))                 # studio backdrop
    s.fill((70, 80, 72), (4, 4, 10, H - 8))                    # lit side
    pygame.draw.polygon(s, (30, 30, 36), [(5, 26), (8, 20), (15, 18), (22, 20), (25, 26)])  # suit
    pygame.draw.polygon(s, (226, 222, 210), [(13, 18), (15, 23), (17, 18)])   # shirt
    s.fill((150, 30, 32), (14, 19, 2, 5))                     # tie
    s.fill((150, 30, 32), (8, 21, 2, 1)); s.fill((150, 30, 32), (9, 22, 3, 1))   # sash
    s.fill(K.BRASS, (20, 21, 2, 2))                            # medal
    s.fill((196, 150, 120), (11, 9, 8, 9))                     # face
    s.fill((150, 108, 86), (17, 10, 2, 8))                     # face shade, right
    s.fill((214, 172, 142), (11, 10, 2, 3))                    # lit cheek, left
    s.fill((150, 150, 150), (10, 6, 10, 3))                    # grey hair
    s.fill((150, 150, 150), (10, 9, 1, 3)); s.fill((120, 120, 122), (19, 9, 1, 3))
    s.fill((40, 30, 28), (12, 12, 2, 1)); s.fill((40, 30, 28), (16, 12, 2, 1))  # eyes
    s.fill((60, 50, 46), (12, 15, 6, 1))                       # moustache
    s.fill((236, 230, 210), (11, 6, 3, 1))                     # hair highlight
    return K.scaled(s, scale)
