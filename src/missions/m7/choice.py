"""Mission 7 beat 7 - Two Channels: Vasile's offer, Maru's reply, then the choice.

A field receiver: the real radio widget shows the incoming line, two physical
channel cards blink, and nothing marks one as right.  The pick is written to
``STATE.m8_route`` ("duty" or "revenge") and the mission ends through the
callback given to ``begin``.
"""
import pygame

from core.config import HEIGHT, WIDTH, audio as _manager
from core.state import STATE
from engine.core import now_ms as _now_ms
from ui import pixfont
from ui import radio as _radio

from . import m7_audio as _m7_audio

LINES = (
    ("VASILE", (100, 160, 220), "Biribel. The offer stands. Tomorrow night."),
    ("MARU", (110, 200, 140), "Two channels, Biribel. His, and ours. Pick one."),
)
OPTIONS = (
    ("ANSWER VASILE", "duty"),
    ("MEET VASILE ALONE", "revenge"),
)
CHANNELS = (("141.20", "1"), ("141.80", "2"))
BROADCAST_MS = 3400
FADE_MS = 900

_S = {"t0": 0, "sel": -1, "done_at": 0, "cb": None, "prev": set(),
      "line_i": 0, "line_start": 0}
_WIDGET = _radio.RadioTransmission()


def _snd():
    return _m7_audio.instance(_manager)


def begin(on_done):
    now = _now_ms()
    _S.update(t0=now, sel=-1, done_at=0, cb=on_done, prev=set(),
              line_i=0, line_start=now)
    _WIDGET.reset()
    snd = _snd()
    snd.stop_loops()
    snd.start_loop("m7_choice_hum", 0.22)
    snd.power_on()


def _pressed(keys, *codes):
    try:
        return any(keys[c] for c in codes)
    except Exception:
        return False


def _select(i):
    if i == _S["sel"]:
        return
    _S["sel"] = i
    _S["line_i"] = i
    _S["line_start"] = _now_ms()
    _snd().radio_tune()
    _snd().click()


def update(keys=None):
    now = _now_ms()
    if _S["done_at"]:
        if now - _S["done_at"] >= FADE_MS and _S["cb"]:
            cb, _S["cb"] = _S["cb"], None
            _snd().stop_loops()
            cb()
        return (0, 0)
    held = set()
    if keys is not None:
        for name, codes in (("l", (pygame.K_LEFT, pygame.K_a)),
                            ("r", (pygame.K_RIGHT, pygame.K_d)),
                            ("1", (pygame.K_1, pygame.K_KP1)),
                            ("2", (pygame.K_2, pygame.K_KP2)),
                            ("ok", (pygame.K_RETURN, pygame.K_e, pygame.K_SPACE))):
            if _pressed(keys, *codes):
                held.add(name)
    fresh = held - _S["prev"]
    _S["prev"] = held
    if _S["sel"] < 0 and _S["line_i"] == 0 and now - _S["t0"] >= BROADCAST_MS:
        _S["line_i"] = 1
        _S["line_start"] = now
    if "l" in fresh or "1" in fresh:
        _select(0)
    elif "r" in fresh or "2" in fresh:
        _select(1)
    elif "ok" in fresh and _S["sel"] >= 0:
        STATE.m8_route = OPTIONS[_S["sel"]][1]
        _S["done_at"] = now
        _snd().tx_lock()
        _snd().stop_loop("m7_choice_hum")
    return (0, 0)


def _text(surface, font, text, col, pos, anchor="topleft"):
    img = font.render(text, False, col)
    surface.blit(img, img.get_rect(**{anchor: pos}))


def draw(surface):
    now = _now_ms()
    u = _radio.RadioTransmission.metrics(surface)["u"]
    surface.fill((12, 14, 12))
    surface.fill((16, 20, 16), (0, 150, WIDTH, 214))
    surface.fill((22, 26, 20), (0, 364, WIDTH, HEIGHT - 364))
    for y in range(0, HEIGHT, 4):
        pygame.draw.line(surface, (10, 12, 10), (0, y), (WIDTH, y))
    plate = pygame.Rect(140, 110, 720, 52)
    pygame.draw.rect(surface, (34, 38, 32), plate)
    pygame.draw.rect(surface, (150, 158, 132), plate, 1)
    _text(surface, pixfont.font("R7", u), "KR-7 FIELD RECEIVER", (226, 216, 180),
          (plate.x + 10 * u, plate.y + 4 * u))
    _text(surface, pixfont.font("R5", u), "FALLOW GROUND  -  TWO CHANNELS",
          (140, 152, 138), (plate.x + 10 * u, plate.y + 4 * u + 8 * u))
    _text(surface, pixfont.font("R5", u), "INCOMING TRANSMISSION  -  NIGHT",
          (110, 122, 110), (WIDTH // 2, 204), "midtop")

    who, col, text = LINES[_S["line_i"]]
    live = {"text": text, "speaker": who, "body": text, "color": col,
            "start": _S["line_start"], "end": _S["line_start"] + 90000,
            "vo_ms": 0, "priority": 0}
    _WIDGET.draw(surface, live=live, allowed=True, clock=now, anchor="center")

    for i, rect in enumerate((pygame.Rect(170, 430, 300, 140),
                              pygame.Rect(530, 430, 300, 140))):
        _radio.draw_channel_card(surface, rect, LINES[i][0], CHANNELS[i][0],
                                 _S["sel"] == i, now, key=CHANNELS[i][1])
    if _S["sel"] >= 0:
        _text(surface, pixfont.font("R5", u), OPTIONS[_S["sel"]][0],
              (232, 216, 168), (WIDTH // 2, 592), "midtop")
    tx_col = (170, 220, 160) if _S["sel"] >= 0 else (70, 78, 70)
    pygame.draw.rect(surface, tx_col, (WIDTH // 2 - 46, 622, 8, 8))
    _text(surface, pixfont.font("R5", u), "TX", (150, 160, 148), (WIDTH // 2 - 30, 622))
    _text(surface, pixfont.font("R5", u),
          "A / D  TUNE     1 / 2  CHANNEL     ENTER  TRANSMIT",
          (120, 130, 118), (WIDTH // 2, 654), "midtop")
    if _S["done_at"]:
        k = min(1.0, (now - _S["done_at"]) / float(FADE_MS))
        veil = pygame.Surface((WIDTH, HEIGHT))
        veil.set_alpha(int(255 * k))
        surface.blit(veil, (0, 0))
