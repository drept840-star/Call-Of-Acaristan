"""Mission 7 beat 7 - Two Channels: Vasile's offer, Maru's reply, then the choice.

Staged like a radio dial: two channels blink, there is no timer and nothing
marks one as right.  The pick is written to ``STATE.m8_route`` ("duty" or
"revenge") and the mission ends through the callback given to ``begin``.
"""
import math

import pygame

from core.config import HEIGHT, WIDTH, font_terminal, font_terminal_small
from core.state import STATE
from engine.core import now_ms as _now_ms

LINES = (
    ("VASILE", (214, 122, 104), "Biribel. The offer stands. Tomorrow night."),
    ("MARU", (146, 208, 150), "Two channels, Biribel. His, and ours. Pick one."),
)
OPTIONS = (
    ("ANSWER VASILE", "DUTY", "duty"),
    ("MEET VASILE ALONE", "REVENGE", "revenge"),
)
CPS = 34.0                 # typed characters per second
HOLD_MS = 1500             # a finished line stays this long before the next
FADE_MS = 900              # black-out after the pick
BG = (10, 12, 14)
DIM = (96, 104, 108)
TEXT = (226, 228, 220)
LIT = (232, 196, 104)

_S = {"t0": 0, "sel": -1, "done_at": 0, "cb": None, "prev": set()}


def begin(on_done):
    _S.update(t0=_now_ms(), sel=-1, done_at=0, cb=on_done, prev=set())


def _line_times():
    """Start time of each line and of the options, in ms from the first frame."""
    starts, t = [], 400
    for _who, _col, text in LINES:
        starts.append(t)
        t += int(len(text) / CPS * 1000) + HOLD_MS
    return starts, t


def _pressed(keys, *codes):
    try:
        return any(keys[c] for c in codes)
    except Exception:
        return False


def update(keys=None):
    now = _now_ms()
    if _S["done_at"]:
        if now - _S["done_at"] >= FADE_MS and _S["cb"]:
            cb, _S["cb"] = _S["cb"], None
            cb()
        return (0, 0)
    held = set()
    if keys is not None:
        for name, codes in (("l", (pygame.K_LEFT, pygame.K_a)), ("r", (pygame.K_RIGHT, pygame.K_d)),
                            ("1", (pygame.K_1, pygame.K_KP1)), ("2", (pygame.K_2, pygame.K_KP2)),
                            ("ok", (pygame.K_RETURN, pygame.K_e, pygame.K_SPACE))):
            if _pressed(keys, *codes):
                held.add(name)
    fresh = held - _S["prev"]
    _S["prev"] = held
    _starts, opt_t = _line_times()
    elapsed = now - _S["t0"]
    if elapsed < opt_t:
        if "ok" in fresh:
            _S["t0"] -= opt_t - elapsed       # skip the transmission
        return (0, 0)
    if "l" in fresh or "1" in fresh:
        _S["sel"] = 0
    elif "r" in fresh or "2" in fresh:
        _S["sel"] = 1
    elif "ok" in fresh and _S["sel"] >= 0:
        STATE.m8_route = OPTIONS[_S["sel"]][2]
        _S["done_at"] = now
    return (0, 0)


def _text(surface, font, text, col, pos, anchor="topleft"):
    img = font.render(text, True, col)
    surface.blit(img, img.get_rect(**{anchor: pos}))


def _channel(surface, i, rect, tuned, blink_on):
    label, tag, _route = OPTIONS[i]
    pygame.draw.rect(surface, (18, 22, 24), rect)
    pygame.draw.rect(surface, LIT if tuned else DIM, rect, 2 if tuned else 1)
    led = LIT if (tuned or blink_on) else (46, 50, 52)
    pygame.draw.circle(surface, led, (rect.x + 24, rect.y + 26), 6)
    _text(surface, font_terminal_small, "CHANNEL %d" % (i + 1), DIM, (rect.x + 44, rect.y + 17))
    _text(surface, font_terminal, "[ %s - %s ]" % (label, tag), TEXT if tuned else DIM,
          (rect.centerx, rect.y + 70), "midtop")


def draw(surface):
    now = _now_ms()
    elapsed = now - _S["t0"]
    surface.fill(BG)
    for y in range(0, HEIGHT, 4):
        pygame.draw.line(surface, (14, 17, 19), (0, y), (WIDTH, y))
    _text(surface, font_terminal_small, "RADIO  -  NIGHT  -  FALLOW GROUND", DIM, (40, 34))
    starts, opt_t = _line_times()
    y = 170
    for (who, col, text), t0 in zip(LINES, starts):
        if elapsed < t0:
            break
        shown = min(len(text), int((elapsed - t0) / 1000.0 * CPS))
        _text(surface, font_terminal_small, who, col, (WIDTH // 2 - 340, y))
        _text(surface, font_terminal, text[:shown], TEXT, (WIDTH // 2 - 340, y + 26))
        y += 110
    if elapsed >= opt_t:
        blink_on = int(elapsed / 520) % 2 == 0
        for i in range(2):
            rect = pygame.Rect(40 + i * 480, 430, 440, 120)
            _channel(surface, i, rect, _S["sel"] == i, blink_on == (i == 0))
        hint = "A / D  TUNE      ENTER  TRANSMIT" if _S["sel"] >= 0 else "A / D  TUNE"
        _text(surface, font_terminal_small, hint, DIM, (WIDTH // 2, HEIGHT - 70), "midtop")
    if _S["done_at"]:
        k = min(1.0, (now - _S["done_at"]) / float(FADE_MS))
        veil = pygame.Surface((WIDTH, HEIGHT))
        veil.set_alpha(int(255 * k))
        surface.blit(veil, (0, 0))
