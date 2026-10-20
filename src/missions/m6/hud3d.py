"""Mission 6 3D HUD: minimal tactical, shared by the train shootout and the
yard fight.

Thin lines and small mono text, nothing boxed: the 3D scene carries the
frame.  Every element draws its own 1 px drop shadow so it reads over the
lit platform and the dark yard alike.  Shapes are drawn, never glyphs: the
terminal font has no arrows or diamonds.
"""
import math

import pygame

from core.config import HEIGHT, WIDTH, font_terminal, font_terminal_small

TEXT = (228, 230, 222)
DIM = (142, 150, 162)
ACCENT = (214, 176, 96)
DANGER = (220, 76, 62)
GOOD = (118, 184, 128)
SHADOW = (0, 0, 0)
MARGIN = 28


_GLYPHS = {}     # (font, text, colour) -> rendered text; the HUD redraws
_PANES = {}      # the same handful of strings every frame


def _render(font, s, col):
    key = (id(font), s, col)
    img = _GLYPHS.get(key)
    if img is None:
        if len(_GLYPHS) > 400:
            _GLYPHS.clear()
        img = _GLYPHS[key] = font.render(s, True, col)
    return img


def _text(surface, font, s, col, pos, anchor="topleft", alpha=255):
    img = _render(font, s, col)
    sh = _render(font, s, SHADOW)
    rect = img.get_rect(**{anchor: pos})
    if alpha < 255:
        img, sh = img.copy(), sh.copy()
        img.set_alpha(alpha)
        sh.set_alpha(alpha)
    surface.blit(sh, rect.move(1, 1))
    surface.blit(img, rect)
    return rect


def _line(surface, col, a, b, w=1):
    pygame.draw.line(surface, SHADOW, (a[0] + 1, a[1] + 1), (b[0] + 1, b[1] + 1), w)
    pygame.draw.line(surface, col, a, b, w)


def _bar(surface, x, y, w, frac, col, h=3, back=(52, 56, 64)):
    pygame.draw.rect(surface, SHADOW, (x + 1, y + 1, w, h))
    pygame.draw.rect(surface, back, (x, y, w, h))
    if frac > 0.0:
        pygame.draw.rect(surface, col, (x, y, max(1, int(w * frac)), h))


def _chevron(surface, x, y, col, size=5):
    pts = [(x, y - size), (x + size, y), (x, y + size)]
    pygame.draw.polygon(surface, SHADOW, [(px + 1, py + 1) for px, py in pts])
    pygame.draw.polygon(surface, col, pts)


def diamond(surface, x, y, col, size=6, width=0):
    pts = [(x, y - size), (x + size, y), (x, y + size), (x - size, y)]
    pygame.draw.polygon(surface, SHADOW, [(px + 1, py + 1) for px, py in pts], width)
    pygame.draw.polygon(surface, col, pts, width)


# ── top left: the objective ───────────────────────────────────────────────
def objective(surface, head, sub=None, dist=None, accent=ACCENT):
    x, y = MARGIN, MARGIN
    _chevron(surface, x + 2, y + 9, accent)
    r = _text(surface, font_terminal_small, head.upper(), TEXT, (x + 14, y))
    if dist is not None:
        diamond(surface, r.right + 18, y + 8, accent, 5)
        _text(surface, font_terminal_small, "%d M" % int(round(dist)), accent,
              (r.right + 28, y))
    if sub:
        _text(surface, font_terminal_small, sub, DIM, (x + 14, y + 20))
    return y + (40 if sub else 22)


def status_line(surface, y, label, frac, state, col):
    """One-line status under the objective (the train's Volkov run)."""
    x = MARGIN + 14
    r = _text(surface, font_terminal_small, label, DIM, (x, y))
    _bar(surface, r.right + 10, y + 7, 120, frac, col)
    _text(surface, font_terminal_small, state, col, (r.right + 140, y))


# ── bottom left: health and the Guard count ───────────────────────────────
def vitals(surface, hp, hp_max, wounded=False, alive=None, slots=None):
    """``slots``: per-Guard states for the pips - 'alive' | 'down' | 'due'."""
    x, y = MARGIN, HEIGHT - MARGIN - 34
    frac = max(0.0, min(1.0, hp / float(max(1, hp_max))))
    col = DANGER if frac < 0.35 else TEXT
    _bar(surface, x, y + 8, 200, frac, col, h=3)
    _text(surface, font_terminal_small, "%d" % int(hp), col, (x + 210, y))
    if wounded:
        _text(surface, font_terminal_small, "WOUNDED", DANGER, (x + 250, y))
    if alive is not None:
        r = _text(surface, font_terminal_small, "GUARD", DIM, (x, y + 18))
        px = r.right + 10
        for i, st in enumerate(slots or ["alive"] * alive):
            c = {"alive": DANGER, "down": (70, 74, 82)}.get(st, (40, 44, 50))
            pygame.draw.rect(surface, SHADOW, (px + i * 10 + 1, y + 25, 6, 6))
            pygame.draw.rect(surface, c, (px + i * 10, y + 24, 6, 6))


# ── bottom right: the weapon ──────────────────────────────────────────────
def ammo(surface, name, mag, mag_size, reserve_text, reloading=0.0):
    right, y = WIDTH - MARGIN, HEIGHT - MARGIN - 40
    low = mag <= mag_size // 4
    col = DANGER if low else TEXT
    r = _text(surface, font_terminal_small, reserve_text, DIM, (right, y + 12),
              anchor="topright")
    _line(surface, DIM, (r.left - 9, y + 10), (r.left - 9, y + 26))
    big = _text(surface, font_terminal, "%02d" % mag, col, (r.left - 18, y + 4),
                anchor="topright")
    _text(surface, font_terminal_small, name, DIM, (big.left - 10, y + 12),
          anchor="topright")
    # magazine pips: one hairline per round
    w = 150
    step = w / float(max(1, mag_size))
    for i in range(mag_size):
        px = right - w + int(i * step)
        c = ACCENT if i < mag else (52, 56, 64)
        pygame.draw.line(surface, c, (px, y + 34), (px, y + 39), 1)
    if reloading > 0.0:
        _text(surface, font_terminal_small, "RELOADING", ACCENT,
              (right, y - 14), anchor="topright")
        _bar(surface, right - 150, y - 18, 150, reloading, ACCENT, h=2)
    elif low:
        _text(surface, font_terminal_small, "R  RELOAD", ACCENT,
              (right, y - 14), anchor="topright")


# ── centre: crosshair, hit marker, damage arcs ───────────────────────────
def crosshair(surface, gap, reload_frac=0.0, hit_age=None, hit_kind=None,
              tight=False, lines=True):
    cx, cy = WIDTH // 2, HEIGHT // 2
    ln = 6 if tight else 9
    if lines:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            _line(surface, TEXT, (cx + dx * gap, cy + dy * gap),
                  (cx + dx * (gap + ln), cy + dy * (gap + ln)), 1)
        pygame.draw.rect(surface, TEXT, (cx, cy, 1, 1))
    if reload_frac > 0.0:
        rect = pygame.Rect(cx - 20, cy - 20, 40, 40)
        pygame.draw.arc(surface, ACCENT, rect, math.pi / 2,
                        math.pi / 2 + reload_frac * 2 * math.pi, 2)
    if hit_age is not None and hit_age < 0.2:
        k = 1.0 - hit_age / 0.2
        rr = int(9 + 4 * (1 - k))
        col = {"head": (246, 196, 84), "kill": DANGER}.get(hit_kind, TEXT)
        if hit_kind in ("kill", "head"):
            rr = int(rr * (1.0 + 0.5 * k))
        for sx in (-1, 1):
            for sy in (-1, 1):
                _line(surface, col, (cx + sx * rr, cy + sy * rr),
                      (cx + sx * (rr + 6), cy + sy * (rr + 6)), 2)


def damage_arcs(surface, marks, now, life=0.85):
    """``marks``: (time, bearing deg) of hits; arcs point at the shooter."""
    cx, cy = WIDTH // 2, HEIGHT // 2
    rad = 110
    rect = pygame.Rect(cx - rad, cy - rad, rad * 2, rad * 2)
    for t0, bearing in marks:
        k = 1.0 - (now - t0) / life
        if k <= 0.0:
            continue
        a = math.radians(90.0 + bearing)
        col = (int(200 * k + 40), int(40 * k), int(34 * k))
        pygame.draw.arc(surface, col, rect, a - 0.3, a + 0.3, 3)


# ── the objective marker in the world ────────────────────────────────────
def marker(surface, screen, dist, label=None, col=ACCENT):
    """``screen``: (x, y, in_front) of the target, already in screen pixels.
    Off screen (or behind) the diamond rides the edge, pointing at it."""
    x, y, front = screen
    pad = 36
    inside = front and pad <= x <= WIDTH - pad and pad <= y <= HEIGHT - pad
    if not inside:
        cx, cy = WIDTH / 2.0, HEIGHT / 2.0
        dx, dy = x - cx, y - cy
        if not front:
            dx, dy = -dx, -dy
        if abs(dx) < 1e-3 and abs(dy) < 1e-3:
            dy = 1.0
        s = min((WIDTH / 2.0 - pad) / max(1e-3, abs(dx)),
                (HEIGHT / 2.0 - pad) / max(1e-3, abs(dy)))
        x, y = cx + dx * s, cy + dy * s
    x, y = int(x), int(y)
    diamond(surface, x, y, col, 7, 2)
    diamond(surface, x, y, col, 3)
    _text(surface, font_terminal_small, "%d M" % int(round(dist)), col,
          (x, y + 12), anchor="midtop")
    if label and inside:
        _text(surface, font_terminal_small, label, TEXT, (x, y - 12),
              anchor="midbottom")


# ── top right: the square north-up minimap ───────────────────────────────
def minimap(surface, bounds, rects, lines, player, yaw_vec, objective=None,
            enemies=(), size=176):
    """North-up map of the play area.

    ``bounds`` (x0, x1, z0, z1) world metres; ``rects`` [(x0, z0, x1, z1,
    col)]; ``lines`` [((x, z), (x, z), col)]; ``player`` (x, z) with
    ``yaw_vec`` its facing (dx, dz); ``objective`` (x, z) or None;
    ``enemies`` [(x, z)].  North is -z (the yard is at the top), and x is
    mirrored because engine3d is: looking north, +x is on screen-left."""
    x0b, x1b, z0b, z1b = bounds
    span = max(x1b - x0b, z1b - z0b)
    sc = (size - 12) / span
    left, top = WIDTH - MARGIN - size, MARGIN
    ox = left + 6 + ((size - 12) - (x1b - x0b) * sc) / 2.0
    oz = top + 6 + ((size - 12) - (z1b - z0b) * sc) / 2.0

    def m(x, z):
        return (ox + (x1b - x) * sc, oz + (z - z0b) * sc)

    pane = _PANES.get(size)
    if pane is None:
        pane = _PANES[size] = pygame.Surface((size, size), pygame.SRCALPHA)
        pane.fill((6, 9, 14, 150))
    surface.blit(pane, (left, top))
    pygame.draw.rect(surface, (96, 106, 122), (left, top, size, size), 1)
    clip = surface.get_clip()
    surface.set_clip(pygame.Rect(left + 1, top + 1, size - 2, size - 2))
    for a, b, col in lines:
        pygame.draw.line(surface, col, m(*a), m(*b), 1)
    for rx0, rz0, rx1, rz1, col in rects:
        (ax, az), (bx, bz) = m(rx1, rz0), m(rx0, rz1)
        pygame.draw.rect(surface, col, (ax, az, max(1, bx - ax), max(1, bz - az)))
    for ex, ez in enemies:
        px, pz = m(ex, ez)
        pygame.draw.circle(surface, DANGER, (int(px), int(pz)), 3)
    if objective is not None:
        px, pz = m(*objective)
        px = min(max(px, left + 8), left + size - 8)
        pz = min(max(pz, top + 8), top + size - 8)
        diamond(surface, int(px), int(pz), ACCENT, 5)
    px, pz = m(*player)
    fx, fz = -yaw_vec[0], yaw_vec[1]
    n = math.hypot(fx, fz) or 1.0
    fx, fz = fx / n, fz / n
    tip = (px + fx * 8, pz + fz * 8)
    l = (px - fx * 4 - fz * 5, pz - fz * 4 + fx * 5)
    r = (px - fx * 4 + fz * 5, pz - fz * 4 - fx * 5)
    pygame.draw.polygon(surface, TEXT, [tip, l, r])
    surface.set_clip(clip)
    _text(surface, font_terminal_small, "N", DIM, (left + size // 2, top + 2),
          anchor="midtop")
