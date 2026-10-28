"""Mission 7 farm work: the generator pull-cord and the tractor route.

The two puzzles are pure state machines driven by ``engine.core.now_ms`` and a
pressed key.  They emit sound names; farmyard drains them so this module never
touches the audio manager.  The cards are drawn here too, in the farm palette.
"""
import pygame

from core.config import WIDTH, font_prompt, font_terminal_small
from engine.core import now_ms as _now_ms

from . import maps as M

CREAM = (238, 228, 198)
DIM = (148, 140, 120)
AMBER = (232, 196, 104)
GREEN = (142, 196, 120)
RED = (206, 86, 66)
PANEL = (30, 26, 22)
TRACK = (52, 44, 36)

CARD_W, CARD_H = 430, 108


def card_rect():
    return pygame.Rect((WIDTH - CARD_W) // 2, 56, CARD_W, CARD_H)


def _text(surface, font, text, col, pos, anchor="topleft"):
    img = font.render(text, True, col)
    surface.blit(img, img.get_rect(**{anchor: pos}))


def _frame(surface, rect, title, edge):
    shade = pygame.Surface(rect.size, pygame.SRCALPHA)
    shade.fill((0, 0, 0, 90))
    surface.blit(shade, (rect.x + 4, rect.y + 4))
    pygame.draw.rect(surface, PANEL, rect)
    pygame.draw.rect(surface, edge, rect, 2)
    surface.fill(M.WOOD_D, (rect.x + 2, rect.y + 2, rect.w - 4, 20))
    _text(surface, font_terminal_small, title, CREAM, (rect.x + 8, rect.y + 4))


def _key_cap(surface, x, y, label):
    w = max(28, font_prompt.size(label)[0] + 12)
    cap = pygame.Rect(x, y, w, 24)
    pygame.draw.rect(surface, (24, 22, 20), cap)
    pygame.draw.rect(surface, (176, 168, 148), cap, 1)
    _text(surface, font_prompt, label, CREAM, cap.center, "center")
    return cap.w


def _track(surface, x, y, w, marker, band=None, col=CREAM):
    pygame.draw.rect(surface, TRACK, (x, y, w, 14))
    pygame.draw.rect(surface, (92, 84, 70), (x, y, w, 14), 1)
    if band is not None:
        lo, hi = band
        bx = x + int(lo * w)
        bw = max(2, int((hi - lo) * w))
        pygame.draw.rect(surface, GREEN, (bx, y + 1, bw, 12))
    mx = x + int(max(0.0, min(1.0, marker)) * (w - 3))
    pygame.draw.rect(surface, col, (mx, y - 2, 3, 18))


def _pips(surface, x, y, filled, total, col=AMBER):
    for i in range(total):
        r = pygame.Rect(x + i * 14, y, 10, 10)
        pygame.draw.rect(surface, (44, 38, 32), r)
        pygame.draw.rect(surface, (86, 76, 64), r, 1)
        if i < filled:
            pygame.draw.rect(surface, col, r.inflate(-4, -4))


class GenPuzzle:
    """Prime (3 taps) -> choke (one timed tap) -> 3 timed pulls -> run."""

    PRIME_TAPS = 3
    CHOKE_MS = 1400
    CHOKE_BAND = (0.42, 0.62)
    PULL_MS = 900
    PULL_BANDS = ((0.52, 0.66), (0.30, 0.44), (0.70, 0.84))
    PULLS = 3

    def __init__(self, now=None):
        self.phase = "prime"
        self.prime = 0
        self.pull = 0
        self.comp = 0.0
        self.t = _now_ms() if now is None else now
        self.tries = 0
        self.flash = 0.0
        self.events = []
        self.done = False

    def sweep(self, now):
        if self.phase == "choke":
            u = ((now - self.t) % self.CHOKE_MS) / float(self.CHOKE_MS)
        elif self.phase == "pull":
            u = ((now - self.t) % self.PULL_MS) / float(self.PULL_MS)
        else:
            return 0.0
        return 1.0 - abs(2.0 * u - 1.0)

    def band(self):
        if self.phase == "choke":
            return self.CHOKE_BAND
        if self.phase == "pull":
            return self.PULL_BANDS[min(self.pull, len(self.PULL_BANDS) - 1)]
        return None

    def press(self, now):
        if self.done:
            return self.events
        if self.phase == "prime":
            self.prime += 1
            self.events.append("prime")
            if self.prime >= self.PRIME_TAPS:
                self.phase = "choke"
                self.t = now
            return self.events
        pos = self.sweep(now)
        lo, hi = self.band()
        if self.phase == "choke":
            if lo <= pos <= hi:
                self.phase = "pull"
                self.pull = 0
                self.comp = 0.0
                self.t = now
                self.flash = 1.0
                self.events.append("choke_ok")
            else:
                self.tries += 1
                self.flash = -1.0
                self.events.append("choke_miss")
                self.t = now
            return self.events
        if self.phase == "pull":
            if lo <= pos <= hi:
                self.pull += 1
                self.comp = self.pull / float(self.PULLS)
                self.flash = 1.0
                self.events.append("pull_ok")
                if self.pull >= self.PULLS:
                    self.phase = "run"
                    self.done = True
                    self.events.append("run")
                else:
                    self.t = now
            else:
                self.tries += 1
                self.comp = max(0.0, self.comp - 1.0 / self.PULLS)
                self.flash = -1.0
                self.events.append("pull_miss")
                self.t = now
        return self.events

    def update(self, now):
        if self.flash:
            self.flash *= 0.86
            if abs(self.flash) < 0.04:
                self.flash = 0.0
        return self.events

    def take_events(self):
        out = self.events
        self.events = []
        return out


class TractorPuzzle:
    """Guided low-speed manoeuvres: hold the indicated control; no timeout."""

    PROMPT_MS = 1100
    CLEAN_MS = 380
    SEG_MS = 1150
    STALL_MS = 850

    def __init__(self, route, now=None):
        self.route = tuple(route)
        self.i = 0
        self.state = "prompt"
        self.t = _now_ms() if now is None else now
        self.tries = 0
        self.clean = False
        self.flash = 0.0
        self.events = []
        self.done = False

    @property
    def duration(self):
        x0, y0, x1, y1, a0, a1, *_ = self.step()
        distance = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        return max(650, int(distance / 100.0 * 1000), int(abs(a1 - a0) * 12))

    def step(self):
        return self.route[min(self.i, len(self.route) - 1)]

    def _ease(self, u):
        u = max(0.0, min(1.0, u))
        return u * u * (3.0 - 2.0 * u)

    def pose(self, now):
        step = self.step()
        x0, y0, x1, y1, a0, a1, _key, _label = step
        if self.state == "drive":
            u = self._ease((now - self.t) / float(self.duration))
        elif self.state == "done":
            u = 1.0
        else:
            u = 0.0
        return (x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, a0 + (a1 - a0) * u)

    def press(self, now, key):
        if self.done or self.state != "prompt":
            return self.events
        elapsed = now - self.t
        if key == self.step()[6]:
            self.state = "drive"
            self.t = now
            self.clean = elapsed <= self.CLEAN_MS
            self.flash = 1.0 if self.clean else 0.4
            self.events.append("drive")
        else:
            self._stall(now)
        return self.events

    def _stall(self, now):
        self.state = "stall"
        self.t = now
        self.tries += 1
        self.flash = -1.0
        self.events.append("stall")

    def update(self, now):
        if self.flash:
            self.flash *= 0.88
            if abs(self.flash) < 0.04:
                self.flash = 0.0
        if self.state == "stall" and now - self.t >= self.STALL_MS:
            self.state = "prompt"
            self.t = now
        elif self.state == "drive" and now - self.t >= self.duration:
            self.i += 1
            self.t = now
            self.events.append("arrive")
            if self.i >= len(self.route):
                self.i = len(self.route) - 1
                self.state = "done"
                self.done = True
                self.events.append("park")
            else:
                self.state = "prompt"
        return self.events

    def window(self, now):
        if self.state != "prompt":
            return 0.0
        return max(0.0, 1.0 - (now - self.t) / float(self.PROMPT_MS))

    def take_events(self):
        out = self.events
        self.events = []
        return out


# ── cards ───────────────────────────────────────────────────────────────────
def draw_generator(surface, pz, now):
    rect = card_rect()
    edge = M.WOOD_L
    if pz.flash > 0.2:
        edge = GREEN
    elif pz.flash < -0.2:
        edge = RED
    _frame(surface, rect, "GENERATOR", edge)
    phases = ("PRIME", "CHOKE", "PULL")
    active = phases.index({"prime": "PRIME", "choke": "CHOKE", "pull": "PULL",
                           "run": "PULL"}.get(pz.phase, "PULL"))
    x = rect.x + 10
    for i, name in enumerate(phases):
        col = AMBER if i == active else (GREEN if i < active else DIM)
        _text(surface, font_terminal_small, name, col, (x, rect.y + 26))
        x += 96
    y = rect.y + 52
    if pz.phase == "prime":
        _text(surface, font_terminal_small, "TAP", DIM, (rect.x + 10, y + 4))
        _key_cap(surface, rect.x + 44, y, "E")
        _text(surface, font_terminal_small, "TO PRIME", DIM, (rect.x + 86, y + 4))
        _pips(surface, rect.x + 200, y + 6, pz.prime, GenPuzzle.PRIME_TAPS)
        _text(surface, font_terminal_small, "COLD", DIM, (rect.right - 58, y + 4))
    else:
        pz_now = now
        band = pz.band()
        marker = pz.sweep(pz_now)
        _text(surface, font_terminal_small, "PULL", DIM, (rect.x + 10, y + 4))
        _key_cap(surface, rect.x + 48, y, "E")
        _text(surface, font_terminal_small, "IN THE GREEN", DIM, (rect.x + 90, y + 4))
        _track(surface, rect.x + 210, y + 5, 120, marker, band)
        _pips(surface, rect.right - 58, y + 6, int(round(pz.comp * GenPuzzle.PULLS)),
              GenPuzzle.PULLS)
    if pz.flash < -0.2:
        _text(surface, font_terminal_small, "COUGH - AGAIN", RED, (rect.centerx, rect.y + 86),
              "midtop")


def draw_tractor(surface, pz, now):
    rect = card_rect()
    edge = M.WOOD_L
    if pz.flash > 0.2:
        edge = GREEN
    elif pz.flash < -0.2:
        edge = RED
    _frame(surface, rect, "TRACTOR", edge)
    step = pz.step()
    total = len(pz.route)
    for i in range(total):
        cx = rect.x + 12 + i * 16
        col = AMBER if i == pz.i else (GREEN if i < pz.i else DIM)
        pygame.draw.circle(surface, col, (cx, rect.y + 32), 4 if i == pz.i else 3)
    label = step[7]
    _text(surface, font_terminal_small, label, CREAM, (rect.x + 110, rect.y + 25))
    y = rect.y + 54
    if pz.state == "prompt":
        _key_cap(surface, rect.x + 10, y, step[6].upper())
        _text(surface, font_terminal_small, "HOLD", DIM, (rect.x + 52, y + 4))
        _text(surface, font_terminal_small, "NO TIME LIMIT", DIM, (rect.x + 110, y + 4))
        _text(surface, font_terminal_small, "%d/%d" % (pz.i + 1, total), DIM,
              (rect.right - 44, y + 4))
    elif pz.state == "drive":
        frac = max(0.0, min(1.0, (now - pz.t) / float(pz.duration)))
        pygame.draw.rect(surface, TRACK, (rect.x + 10, y + 6, rect.w - 20, 12))
        pygame.draw.rect(surface, M.TRACTOR, (rect.x + 10, y + 6, int((rect.w - 20) * frac), 12))
        _text(surface, font_terminal_small, "MOVING", CREAM, (rect.centerx, y + 24), "midtop")
    elif pz.state == "stall":
        _text(surface, font_terminal_small, "STALLED - EASE IT", RED, (rect.centerx, y + 4),
              "midtop")
    else:
        _text(surface, font_terminal_small, "PARKED", GREEN, (rect.centerx, y + 4), "midtop")
