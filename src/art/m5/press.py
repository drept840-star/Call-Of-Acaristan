"""Print Works offset press, top-down (154 x 64). The press bed is the
116 x 52 two-tile footprint at (18, 6); paper feed hangs off the left,
delivery pile off the right, yellow floor safety line around the plinth.
Key light upper-left: lit top edge on each steel box, shaded bottom.
Variant 0: running (green lamp), 1: raid alarm (red lamp).
Replaces decor_interior._press (shadow stays live, it is alpha-blended)."""
import pygame

from art.m5 import _kit as K

VARIANTS = 2
W, H = 154, 64
BED = pygame.Rect(18, 6, 116, 52)
PAPER = (214, 208, 190)
PAPER_D = (176, 170, 152)
INK = (24, 26, 34)
STEEL = (70, 76, 84)
STEEL_D = (40, 44, 50)
HAZ = (196, 160, 40)


def _box(s, r, col):
    pygame.draw.rect(s, col, r)
    pygame.draw.line(s, tuple(min(255, c + 26) for c in col), r.topleft, (r.right - 1, r.y))
    pygame.draw.line(s, tuple(max(0, c - 22) for c in col), (r.x, r.bottom - 1), (r.right - 1, r.bottom - 1))
    pygame.draw.rect(s, tuple(max(0, c - 34) for c in col), r, 1)


def render(variant=0, scale=1):
    alarm = int(variant) % VARIANTS == 1
    s = K.new(W, H)
    r = BED
    pygame.draw.rect(s, (20, 22, 26), r.inflate(10, 6))                  # base plinth
    pygame.draw.rect(s, HAZ, r.inflate(16, 12), 2)                       # floor safety line
    _box(s, r, STEEL_D)
    body = r.inflate(-10, -14)
    _box(s, body, STEEL)
    for i in range(5):                                                   # roller train
        x = body.x + 10 + i * (body.w - 20) // 4
        pygame.draw.rect(s, (30, 32, 36), (x - 4, body.y + 2, 8, body.h - 4))
        pygame.draw.rect(s, (130, 134, 140), (x - 2, body.y + 3, 3, body.h - 6))
    pygame.draw.rect(s, INK, (body.x + 6, body.y + body.h // 2 - 3, body.w - 12, 6))
    feed = pygame.Rect(r.x - 18, r.y + 10, 16, r.h - 20)                 # paper feed
    pygame.draw.rect(s, PAPER, feed)
    pygame.draw.rect(s, PAPER_D, feed, 1)
    out = pygame.Rect(r.right + 2, r.y + 12, 18, r.h - 24)               # delivery pile
    pygame.draw.rect(s, (236, 232, 218), out)
    for k in range(2, out.h, 3):
        pygame.draw.line(s, PAPER_D, (out.x + 1, out.y + k), (out.right - 2, out.y + k))
    pygame.draw.rect(s, (200, 40, 34) if alarm else (60, 200, 90), (r.right - 12, r.y + 4, 6, 6))
    return K.scaled(s, scale)
