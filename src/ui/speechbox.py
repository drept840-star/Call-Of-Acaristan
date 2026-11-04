"""Speech box: the one in-person dialogue box and film caption for the game.

The HUD radio (``ui.radio``) is the house look for spoken lines; this module
draws every other spoken / narrated line in the same family so a conversation
reads as the same device language as a transmission:

* ``draw_box``: in-person conversation box (cutscene dialogue box shim, walk
  sim, M5 conversations, M7 farm, mission briefings). Gunmetal case with ink
  outline and notched corners, caller-ID chip with the speaker's pixel
  portrait, recessed glass with scanlines, accent name plate, voice LED
  ladder while the VO channel is busy, typed body with block caret, beat
  pips and a blinking pixel continue arrow. Unfolds open (160 ms).
* ``draw_caption``: film subtitle for the letterbox band (no case: the band
  is already black) - accent name plate over centred typed rows.

Both lay out from the FULL text, so nothing jumps while it types. Bitmap
fonts only (``ui.pixfont``), integer pixel unit, hard edges.

Typewriter pacing (``reveal_count`` / ``Pacer``): a voiced line reveals over
90 % of its clip (radio clips skip their squelch padding), so the last
character lands just before the actor finishes; a line with no recording
types at ``FALLBACK_CPS`` scaled by the text-speed setting. Callers own the
skip input: the first confirm snaps their char index to full, the next one
advances.
"""
import math

import pygame

from core.config import WIDTH, HEIGHT, LETTER_H
from engine.core import now_ms as _now_ms
from engine.text import T as _T
from ui import pixfont
from ui import radio as _R

FINISH_AT = 0.9            # voiced reveal ends at this fraction of the speech
FALLBACK_CPS = 30.0        # chars / s for lines without a recording
FRAME_MS = 1000.0 / 60.0   # one fixed-step update
OPEN_MS = 160
REOPEN_GAP_MS = 250        # box not drawn for this long -> next draw unfolds again
MAX_ROWS = 5

TEXT_RGB = (232, 236, 226)
SYSTEM_RGB = (176, 196, 204)
HINT_RGB = (128, 138, 128)


# -- pacing ------------------------------------------------------------------
def _text_speed():
    try:
        from core.user_settings import SETTINGS
        return max(0.1, float(SETTINGS.text_speed_mul))
    except Exception:
        return 1.0


def reveal_window(text, vo_ms=0, radio=False):
    """(lead_ms, duration_ms) of the typewriter for one line.

    ``vo_ms`` is the clip length the voice module reported (``play_line`` /
    ``clip_ms``); ``radio`` marks a ``play_line(radio=True)`` length, which
    carries the squelch in/out padding around the speech."""
    n = len(text or "")
    if vo_ms and vo_ms > 0:
        lead = tail = 0.0
        if radio:
            try:
                from audio.voice import RADIO_SQUELCH_IN_S, RADIO_SQUELCH_OUT_S
                lead, tail = RADIO_SQUELCH_IN_S * 1000.0, RADIO_SQUELCH_OUT_S * 1000.0
            except Exception:
                pass
        return lead, max(150.0, (vo_ms - lead - tail) * FINISH_AT)
    return 0.0, n * 1000.0 / (FALLBACK_CPS * _text_speed())


def reveal_count(text, age_ms, vo_ms=0, radio=False):
    """Characters of ``text`` visible ``age_ms`` after the line started."""
    n = len(text or "")
    lead, dur = reveal_window(text, vo_ms, radio)
    if dur <= 0:
        return n
    k = (age_ms - lead) / dur
    return max(0, min(n, int(n * k)))


class Pacer:
    """Frame-stepped typewriter clock for one dialogue system.

    Deterministic (fixed ``FRAME_MS`` per ``step``), so replays and the smoke
    test see the same reveal on every run, and it stops with the caller's
    update (pause menus, cutscene handoffs)."""

    def __init__(self):
        self.text = None
        self.age = 0.0
        self.vo_ms = 0
        self.radio = False

    def start(self, text, vo_ms=0, radio=False):
        self.text = text
        self.age = 0.0
        self.vo_ms = int(vo_ms or 0)
        self.radio = bool(radio)

    def voice(self, vo_ms, radio=False):
        """Attach the clip length once the caller has started the VO."""
        self.vo_ms = int(vo_ms or 0)
        self.radio = bool(radio)

    @property
    def voiced(self):
        return self.vo_ms > 0

    def step(self, text, dt_ms=FRAME_MS):
        """Advance one update; returns the visible character count."""
        if text != self.text:
            self.start(text)
        self.age += dt_ms
        return reveal_count(text, self.age, self.vo_ms, self.radio)


# -- shared bits -------------------------------------------------------------
def _unit(surface):
    return _R.unit_for(surface)


def _scale(surface):
    sw, sh = surface.get_size()
    return max(0.75, min(sw / WIDTH, sh / HEIGHT))


def _vo_busy():
    try:
        from audio import voice
        return voice.busy()
    except Exception:
        return False


def _plate(s, f_lab, name, acc, x, y, u):
    """Accent callsign plate (the radio's), returns its rect."""
    nw = f_lab.size(name)[0]
    plate = pygame.Rect(x, y, nw + 4 * u, (f_lab.cap + 2) * u)
    s.fill(acc, plate)
    s.fill(_R._mix(acc, (255, 255, 255), 0.35), (plate.x, plate.y, plate.w, u))
    s.fill(_R._mix(acc, (0, 0, 0), 0.35), (plate.x, plate.bottom - u, plate.w, u))
    f_lab.draw(s, name, (plate.x + 2 * u, plate.y + u), (14, 14, 16))
    return plate


def _ladder(s, x, y, h, u, acc, clock, busy):
    """Six-bar voice meter; bars only move while the VO channel speaks."""
    seg_rows = max(3, (h // u - 1) // 2)
    for i in range(6):
        lv = 0.0
        if busy:
            lv = 0.25 + 0.75 * abs(math.sin(clock * (0.011 + i * 0.0037) + i * 1.7)
                                   * math.sin(clock * 0.0047 + i))
        lit = int(round(lv * seg_rows))
        for j in range(seg_rows):
            col = ((_R.LED_RED if j == seg_rows - 1 else acc) if j < lit else _R.LED_OFF)
            s.fill(col, (x + i * 2 * u, y + h - (j + 1) * 2 * u + u, u, u))
    return 12 * u


def _arrow(s, x, y, u, col):
    """Pixel down-arrow, 5 units wide (no glyph: fonts lack the codepoint)."""
    for r, w in enumerate((5, 3, 1)):
        s.fill(col, (x + (5 - w) // 2 * u, y + r * u, w * u, u))


def _diamond(s, x, y, u, col):
    for r, w in enumerate((1, 3, 5, 3, 1)):
        s.fill(col, (x + (5 - w) // 2 * u, y + r * u, w * u, u))


def _typed_rows(rows, n):
    """Slice wrapped ``rows`` to the first ``n`` characters of the text."""
    out, left = [], n
    for r in rows:
        if left <= 0:
            break
        out.append(r[:left])
        left -= len(r) + 1
    return out


def _wrap(text, font, width):
    rows = []
    for para in (text or "").split("\n"):
        cur = ""
        for w in para.split(" "):
            t = (cur + " " + w) if cur else w
            if font.size(t)[0] > width and cur:
                rows.append(cur)
                cur = w
            else:
                cur = t
        rows.append(cur)
    while len(rows) > 1 and not rows[-1]:
        rows.pop()
    return rows or [""]


def _is_system(speaker):
    return _R._base(speaker) in ("", "SYSTEM")


# -- conversation box --------------------------------------------------------
_box_state = {"last": -10 ** 9, "open_t": 0}
_case_cache = {}


def _case(w, h, u, chip_rect, win):
    key = (w, h, u, chip_rect and tuple(chip_rect), tuple(win))
    hit = _case_cache.get(key)
    if hit is not None:
        return hit
    if len(_case_cache) > 24:
        _case_cache.clear()
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((*_R.CASE_INK, 255), (u, 0, w - 2 * u, h))
    s.fill((*_R.CASE_INK, 255), (0, u, w, h - 2 * u))
    body = pygame.Rect(u, u, w - 2 * u, h - 2 * u)
    _R._bevel_box(s, body, _R.CASE, _R.CASE_HI, _R.CASE_LO, u)
    for y in range(body.y + 3 * u, body.bottom - 2 * u, 3 * u):
        s.fill(_R._mix(_R.CASE, _R.CASE_LO, 0.25), (body.x + u, y, body.w - 2 * u, max(1, u // 2)))
    for x, y in ((2 * u, 2 * u), (w - 4 * u, 2 * u), (2 * u, h - 4 * u), (w - 4 * u, h - 4 * u)):
        _R._screw(s, x, y, u)
    if chip_rect is not None:
        _R._bevel_box(s, chip_rect.inflate(2 * u, 2 * u), (8, 10, 9), _R.CASE_LO, _R.CASE_HI, u)
    _R._bevel_box(s, win.inflate(2 * u, 2 * u), _R.GLASS, _R.CASE_LO, _R.CASE_HI, u)
    s.fill(_R.GLASS, win)
    s.fill(_R.GLASS_HI, (win.x, win.y, win.w, u))
    for y in range(win.y + u, win.bottom, 2 * u):
        s.fill((14, 20, 16), (win.x, y, win.w, max(1, u // 2)))
    _case_cache[key] = s
    return s


def box_metrics(surface):
    sw, sh = surface.get_size()
    scale = _scale(surface)
    u = _unit(surface)
    f_body = _R.body_font(None, u)
    f_lab = pixfont.font("R5", u)
    return {"scale": scale, "u": u, "f_body": f_body, "f_lab": f_lab,
            "panel_w": int(min(sw - 60 * scale, 760 * scale)),
            "chip": _R.PORTRAIT_PX * 2 * u, "pad": 4 * u,
            "plate_h": (f_lab.cap + 2) * u, "row_h": f_body.get_linesize()}


def draw_box(surface, speaker, text, shown, total=None, prompt=True, show_name=True,
             color=None, bottom=None, pips=None, hint=None, clock=None):
    """Draw the conversation box; returns its screen rect.

    ``shown`` characters of ``text`` are visible (the caller's typewriter);
    ``prompt``: True = continue arrow + ``hint`` once typed, False =
    "ANALYZING FILE...", None = no prompt (timeline-owned lines). ``pips`` =
    (index, count) beat progress. ``bottom`` defaults to just above the
    bottom letterbox band."""
    text = text or ""
    total = len(text) if total is None else total
    now = _now_ms() if clock is None else clock
    st = _box_state
    if now - st["last"] > REOPEN_GAP_MS or now < st["last"]:
        st["open_t"] = now
    st["last"] = now

    sw, sh = surface.get_size()
    m = box_metrics(surface)
    u, pad, f_body, f_lab = m["u"], m["pad"], m["f_body"], m["f_lab"]
    panel_w, row_h, plate_h = m["panel_w"], m["row_h"], m["plate_h"]
    system = _is_system(speaker)
    acc = tuple((color or _R.accent_for(speaker, SYSTEM_RGB)))[:3]
    chip = 0 if system else m["chip"]
    names = show_name and not system and _R.PREFS.get("radio_speaker_names", True)

    win_x = pad + u + ((chip + 2 * u + 3 * u) if chip else 0)
    win_w = panel_w - win_x - pad - u
    text_w = win_w - 8 * u
    rows = _wrap(text, f_body, text_w)
    n_rows = max(2, min(MAX_ROWS, len(rows)))
    head_h = (plate_h + 3 * u) if (names or pips) else 2 * u
    foot_h = plate_h + u
    win_h = 2 * u + head_h + n_rows * row_h + foot_h
    panel_h = max(chip + 2 * u + 2 * pad, win_h + 2 * u + 2 * pad)
    win = pygame.Rect(win_x, pad + u, win_w, panel_h - 2 * pad - 2 * u)
    chip_rect = pygame.Rect(pad + u, (panel_h - chip) // 2, chip, chip) if chip else None

    s = _case(panel_w, panel_h, u, chip_rect, win).copy()
    if chip_rect is not None:
        s.fill(_R._mix(acc, (6, 8, 8), 0.82), chip_rect)
        s.blit(_R._portrait(speaker, chip, acc), chip_rect.topleft)
        s.blit(_R._screen_overlay(chip, u), chip_rect.topleft)

    hx, hy = win.x + 4 * u, win.y + 2 * u
    busy = _vo_busy() and not system
    if names:
        plate = _plate(s, f_lab, _R._base(speaker), acc, hx, hy, u)
        _ladder(s, plate.right + 3 * u, hy, plate_h, u, acc, now, busy)
    if pips:
        idx, cnt = pips
        cnt = max(1, min(int(cnt), 24))
        px = win.right - 4 * u - cnt * 3 * u + u
        for i in range(cnt):
            col = acc if i <= idx else _R.LED_OFF
            s.fill(col, (px + i * 3 * u, hy + plate_h // 2 - u, 2 * u, 2 * u))

    # body: wrapped from the full line, typed prefix, scroll past MAX_ROWS
    n = max(0, min(len(text), int(shown)))
    vis = _typed_rows(rows, n)
    scrolled = max(0, len(vis) - MAX_ROWS)
    vis = vis[scrolled:]
    tx, by = win.x + 4 * u, win.y + 2 * u + head_h
    ink = SYSTEM_RGB if system else TEXT_RGB
    sh_off = max(1, u // 2)
    for i, r in enumerate(vis):
        if not r:
            continue
        t = f_body.render(r, False, ink)
        shd = f_body.render(r, False, (0, 0, 0))
        if scrolled and i == 0:
            t, shd = t.copy(), shd.copy()
            t.set_alpha(120)
            shd.set_alpha(120)
        s.blit(shd, (tx + sh_off, by + i * row_h + sh_off))
        s.blit(t, (tx, by + i * row_h))
    typing = n < len(text)
    if typing and vis and (now // 220) % 2 == 0:
        cx = tx + f_body.size(vis[-1])[0] + f_body.scale
        s.fill(acc, (cx, by + (len(vis) - 1) * row_h, f_body.scale * 3, f_body.get_ascent()))

    # footer prompt, bottom-right of the glass
    fy = win.bottom - plate_h
    if not typing and n >= total and prompt is not None:
        blink = (now // 420) % 2 == 0
        dim = _R._mix(acc, (40, 44, 40), 0.45)
        if prompt:
            label = hint if hint is not None else _T("cutscene.space_to_continue")
            ax = win.right - 9 * u
            if blink:
                _arrow(s, ax, fy + u, u, acc)
        else:
            label = _T("cutscene.analyzing_file")
            ax = win.right - 9 * u
            _diamond(s, ax, fy, u, acc if blink else dim)
        if label:
            lw = f_lab.size(label)[0]
            f_lab.draw(s, label, (ax - 3 * u - lw, fy + u), HINT_RGB)

    # open: unfold from a centre line, hard edges
    k = 1.0 if OPEN_MS <= 0 else _R._ease_out((now - st["open_t"]) / OPEN_MS)
    x0 = (sw - panel_w) // 2
    if bottom is None:
        bottom = sh - int(LETTER_H * sh / HEIGHT) - int(14 * m["scale"])
    y0 = bottom - panel_h
    if k < 1.0:
        h = max(2 * u, int(panel_h * k) // u * u)
        top = (panel_h - h) // 2
        part = s.subsurface((0, top, panel_w, h)).copy()
        part.set_alpha(int(255 * (0.35 + 0.65 * k)))
        surface.blit(part, (x0, y0 + top))
    else:
        surface.blit(s, (x0, y0))
    return pygame.Rect(x0, y0, panel_w, panel_h)


def reset_box():
    """Next ``draw_box`` unfolds again (scene entry)."""
    _box_state["last"] = -10 ** 9


# -- film caption (letterbox band) -------------------------------------------
def draw_caption(surface, speaker, text, shown=None, band=None, clock=None):
    """Film subtitle centred in the bottom letterbox band (draw AFTER the
    letterbox). ``shown=None`` shows the whole line."""
    text = text or ""
    if not text and not speaker:
        return None
    now = _now_ms() if clock is None else clock
    sw, sh = surface.get_size()
    scale = _scale(surface)
    u = _unit(surface)
    f_body = _R.body_font(None, u)
    f_lab = pixfont.font("R5", u)
    if band is None:
        band = (sh - int(LETTER_H * sh / HEIGHT), sh)
    top, bot = band
    rows = _wrap(text, f_body, int(sw - 160 * scale)) if text else []
    row_h = f_body.get_linesize()
    names = bool(speaker) and not _is_system(speaker) and _R.PREFS.get("radio_speaker_names", True)
    plate_h = (f_lab.cap + 2) * u
    head = (plate_h + 2 * u) if names else 0
    block = head + len(rows) * row_h
    y = top + max(u, (bot - top - block) // 2)
    acc = _R.accent_for(speaker, (255, 150, 60))
    if names:
        name = _R._base(speaker)
        pw = f_lab.size(name)[0] + 4 * u
        meter = 13 * u if _vo_busy() else 0
        px = (sw - pw - meter) // 2
        plate = _plate(surface, f_lab, name, acc, px, y, u)
        if meter:
            _ladder(surface, plate.right + u, y, plate_h, u, acc, now, True)
        y += head
    n = len(text) if shown is None else max(0, min(len(text), int(shown)))
    vis = _typed_rows(rows, n)
    sh_off = max(1, u // 2)
    ink = SYSTEM_RGB if _is_system(speaker) and speaker else TEXT_RGB
    for i, part in enumerate(vis):
        x = (sw - f_body.size(rows[i])[0]) // 2   # full-row x: no drift while typing
        if part:
            f_body.draw(surface, part, (x + sh_off, y + sh_off), (0, 0, 0))
            f_body.draw(surface, part, (x, y), ink)
        y += row_h
    return pygame.Rect(0, top, sw, bot - top)
