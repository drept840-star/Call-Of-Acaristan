"""Lit red Guard notice plate over the Print Works door (36 x 20 px, 0.9 x 0.5 m)."""
from art.m5 import _kit as K

W, H = 36, 20
VARIANTS = 1


def render(variant=0, scale=1):
    s = K.new(W, H, (178, 36, 34))
    K.bevel(s, (0, 0, W, H), (226, 92, 80), (90, 16, 16))
    s.fill((150, 28, 28), (2, 2, W - 4, H - 4))
    s.fill((232, 222, 200), (3, 3, W - 6, 1))
    s.fill((232, 222, 200), (3, H - 4, W - 6, 1))
    K.text_c(s, "GUARD", W // 2, 6, (240, 232, 214))
    return K.scaled(s, scale)
