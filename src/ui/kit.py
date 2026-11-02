"""KRAPNET terminal style kit shared by the main menu and its sub-screens.

One palette, one pair of bundled faces (Oswald for titles, IBM Plex Mono for
everything else) and the few chrome pieces every menu screen repeats: the art
backdrop, framed panels, headers, key hints and toasts. Drawing only - no
state, no input.
"""
import os
import pygame
from core.config import HEIGHT, WIDTH, bg_image, resource_path

# Palette. Amber on near-black ink; steel blue for file/system data, green and
# red only for state.
INK = (6, 7, 9)
PLATE = (11, 12, 14)
PLATE_HI = (20, 18, 15)
EDGE = (54, 44, 32)
EDGE_HI = (120, 82, 38)
ORANGE = (255, 120, 0)
AMBER = (255, 176, 64)
AMBER_DIM = (156, 104, 48)
TEXT = (232, 228, 216)
DIM = (152, 148, 136)
MUTED = (96, 93, 86)
STEEL = (110, 168, 204)
GOOD = (112, 214, 140)
BAD = (236, 104, 78)

_FONT_DIR = os.path.join(resource_path("assets"), "fonts")
_FACES = {
    "display": "Oswald.ttf",
    "regular": "IBMPlexMono-Regular.ttf",
    "semibold": "IBMPlexMono-SemiBold.ttf",
    "bold": "IBMPlexMono-Bold.ttf",
}
_fonts = {}


def font(size, weight="regular"):
    """Cached bundled face; SysFont Consolas only if the file is missing."""
    key = (size, weight)
    f = _fonts.get(key)
    if f is None:
        path = os.path.join(_FONT_DIR, _FACES[weight])
        try:
            f = pygame.font.Font(path, size)
        except (OSError, FileNotFoundError):
            f = pygame.font.SysFont("Consolas", size, bold=weight != "regular")
        _fonts[key] = f
    return f


def text(surface, label, x, y, size=13, color=DIM, weight="regular", align="left"):
    """Blit *label*; returns its rect. align: left, right (x is the right edge), center."""
    s = font(size, weight).render(label, True, color)
    if align == "right":
        x -= s.get_width()
    elif align == "center":
        x -= s.get_width() // 2
    return surface.blit(s, (x, y))


def fit(label, size, width, weight="regular"):
    """Trim *label* with '...' so it renders no wider than *width*."""
    f = font(size, weight)
    if f.size(label)[0] <= width:
        return label
    while label and f.size(label + "...")[0] > width:
        label = label[:-1]
    return label.rstrip() + "..."


_cache = {}


def _scanlines():
    s = _cache.get("scan")
    if s is None:
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for y in range(0, HEIGHT, 3):
            pygame.draw.line(s, (0, 0, 0, 34), (0, y), (WIDTH, y))
        _cache["scan"] = s
    return s


def _vignette():
    s = _cache.get("vig")
    if s is None:
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        # Hard-stepped bands, no soft blobs: darker toward every edge.
        for i, a in enumerate((70, 44, 26, 12)):
            pad = i * 18
            pygame.draw.rect(s, (0, 0, 0, a), (pad, pad, WIDTH - 2 * pad, HEIGHT - 2 * pad), 18)
        _cache["vig"] = s
    return s


def backdrop(surface, dim=214):
    """Menu art under a dark ink wash; the art stays a faint presence."""
    if bg_image:
        surface.blit(bg_image, (0, 0))
    else:
        surface.fill(INK)
    key = ("dim", dim)
    wash = _cache.get(key)
    if wash is None:
        wash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        wash.fill((*INK, dim))
        _cache[key] = wash
    surface.blit(wash, (0, 0))


def finish(surface):
    """Scanlines + edge vignette, drawn last."""
    surface.blit(_scanlines(), (0, 0))
    surface.blit(_vignette(), (0, 0))


def ticks(surface, rect, color=AMBER, size=12, width=2):
    """Corner registration marks."""
    for cx, cy, dx, dy in ((rect.x, rect.y, 1, 1), (rect.right - 1, rect.y, -1, 1),
                           (rect.x, rect.bottom - 1, 1, -1), (rect.right - 1, rect.bottom - 1, -1, -1)):
        pygame.draw.line(surface, color, (cx, cy), (cx + dx * size, cy), width)
        pygame.draw.line(surface, color, (cx, cy), (cx, cy + dy * size), width)


def panel(surface, rect, alpha=236, spine=True):
    """Framed plate: hard drop shadow, 1px edge, amber spine and corner ticks."""
    shadow = pygame.Surface(rect.size, pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 150))
    surface.blit(shadow, (rect.x + 6, rect.y + 6))
    plate = pygame.Surface(rect.size, pygame.SRCALPHA)
    plate.fill((*PLATE, alpha))
    surface.blit(plate, rect.topleft)
    pygame.draw.rect(surface, EDGE, rect, 1)
    if spine:
        pygame.draw.rect(surface, ORANGE, (rect.x, rect.y, 4, 64))
    ticks(surface, rect)


def header(surface, rect, eyebrow, title, tag=None, sub=None):
    """Eyebrow / Oswald title / rule at the top of *rect*. Returns the y below the rule."""
    x = rect.x + 28
    text(surface, eyebrow, x, rect.y + 16, 11, AMBER, "bold")
    t = font(34, "display")
    surface.blit(t.render(title, True, (0, 0, 0)), (x + 2, rect.y + 32))
    surface.blit(t.render(title, True, TEXT), (x, rect.y + 30))
    if tag:
        tw = font(11, "bold").size(tag)[0] + 22
        chip = pygame.Rect(rect.right - 28 - tw, rect.y + 16, tw, 22)
        pygame.draw.rect(surface, PLATE_HI, chip)
        pygame.draw.rect(surface, EDGE_HI, chip, 1)
        text(surface, tag, chip.centerx, chip.y + 4, 11, AMBER, "bold", "center")
    y = rect.y + 80
    if sub:
        text(surface, fit(sub, 12, rect.w - 56), x, y - 4, 12, DIM)
        y += 18
    pygame.draw.line(surface, EDGE, (x, y), (rect.right - 28, y))
    pygame.draw.rect(surface, ORANGE, (x, y - 1, 64, 3))
    return y + 1


def section(surface, label, x, y, width):
    """Small amber label with a rule running to x + width."""
    r = text(surface, label, x, y, 11, AMBER_DIM, "bold")
    pygame.draw.line(surface, EDGE, (r.right + 10, y + 7), (x + width, y + 7))


def key_hints(surface, items, right, y, color=MUTED):
    """Right-aligned row of [KEY] label pairs ending at *right*."""
    x = right
    for key, label in reversed(items):
        lab = font(11).render(label, True, color)
        x -= lab.get_width()
        surface.blit(lab, (x, y + 3))
        k = font(10, "bold").render(key, True, DIM)
        box = pygame.Rect(0, y, k.get_width() + 12, 19)
        box.right = x - 6
        pygame.draw.rect(surface, PLATE_HI, box)
        pygame.draw.rect(surface, EDGE_HI, box, 1)
        surface.blit(k, (box.x + 6, y + 3))
        x = box.x - 18


def button(surface, rect, label, hot=False, primary=False):
    """Flat command button: amber edge when primary or hot."""
    pygame.draw.rect(surface, (34, 26, 16) if hot else PLATE_HI, rect)
    edge = ORANGE if hot else (EDGE_HI if primary else EDGE)
    pygame.draw.rect(surface, edge, rect, 1)
    if hot or primary:
        pygame.draw.rect(surface, ORANGE if hot else AMBER_DIM, (rect.x, rect.y, 3, rect.h))
    col = AMBER if (hot or primary) else TEXT
    f = font(14, "bold")
    s = f.render(label, True, col)
    surface.blit(s, (rect.centerx - s.get_width() // 2, rect.centery - s.get_height() // 2))


def toast(surface, label, y, color=AMBER):
    """Centered notice pill."""
    s = font(14, "bold").render(label, True, color)
    box = pygame.Rect(0, y, s.get_width() + 36, s.get_height() + 14)
    box.centerx = WIDTH // 2
    pygame.draw.rect(surface, PLATE, box)
    pygame.draw.rect(surface, EDGE_HI, box, 1)
    pygame.draw.rect(surface, ORANGE, (box.x, box.y, 3, box.h))
    surface.blit(s, (box.x + 18, box.y + 7))
