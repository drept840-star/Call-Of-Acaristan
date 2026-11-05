"""Speech box: the one in-person dialogue box and film caption for the game.

* ``draw_box``: the slab. A full-width dark strip resting on the bottom
  letterbox, a hard accent rule along its top edge, the speaker's name in an
  accent tab that breaks the rule, wide typed rows with a block caret, and
  three pixel bars at the right (they bob while the line is spoken, then
  step as the continue mark). Used by the cutscene dialogue box shim, walk
  sim, M5 conversations, M7 farm and the mission briefings. Wipes up from
  the letterbox (160 ms).
* ``draw_caption``: film subtitle for the letterbox band (already black) -
  the same accent tab over centred typed rows.

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


def _mix(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def _tab(s, f_tab, name, acc, x, y, u):
    """Accent name tab with notched top corners; returns its rect."""
    h = (f_tab.cap + 3) * u
    r = pygame.Rect(x, y, f_tab.size(name)[0] + 10 * u, h)
    s.fill(acc, (r.x + u, r.y, r.w - 2 * u, u))
    s.fill(acc, (r.x, r.y + u, r.w, r.h - u))
    f_tab.draw(s, name, (r.x + 5 * u, r.y + (h - f_tab.cap * u) // 2), (12, 12, 14))
    return r


def _bars(s, x, y, u, acc, now, mode):
    """Three pixel bars, 5u tall. ``mode``: "talk" bobs, "next" steps,
    "wait" pulses the first bar."""
    dim = _mix(acc, (40, 42, 44), 0.7)
    for i in range(3):
        bx = x + i * 5 * u
        if mode == "talk":
            h = 2 + int(round(3 * abs(math.sin(now * (0.012 + 0.004 * i) + i * 1.9))))
            s.fill(acc, (bx, y + (5 - h) * u, 3 * u, h * u))
        elif mode == "next":
            lit = i < 1 + (now // 220) % 3
            s.fill(acc if lit else dim, (bx, y, 3 * u, 5 * u))
        else:
            lit = i == 0 and (now // 420) % 2 == 0
            s.fill(acc if lit else dim, (bx, y, 3 * u, 5 * u))


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


def _fonts(u):
    """(body, tab, hint) bitmap fonts for pixel unit ``u``."""
    return (pixfont.font("R7", max(1, 3 * u // 2)), pixfont.font("R7", u),
            pixfont.font("R5", u))


# -- the slab ----------------------------------------------------------------
_box_state = {"last": -10 ** 9, "open_t": 0}
STRIP_RGBA = (8, 10, 12, 228)


def draw_box(surface, speaker, text, shown, total=None, prompt=True, show_name=True,
             color=None, bottom=None, pips=None, hint=None, clock=None):
    """Draw the slab; returns its screen rect (tab included).

    ``shown`` characters of ``text`` are visible (the caller's typewriter);
    ``prompt``: True = continue bars (+ ``hint`` if given) once typed,
    False = "ANALYZING FILE...", None = no prompt (timeline-owned lines).
    ``pips`` = (index, count) beat progress. ``bottom`` defaults to the top
    of the bottom letterbox band."""
    text = text or ""
    total = len(text) if total is None else total
    now = _now_ms() if clock is None else clock
    st = _box_state
    if now - st["last"] > REOPEN_GAP_MS or now < st["last"]:
        st["open_t"] = now
    st["last"] = now

    sw, sh = surface.get_size()
    u = _unit(surface)
    f_body, f_tab, f_hint = _fonts(u)
    system = _is_system(speaker)
    acc = tuple(color or (SYSTEM_RGB if system else _R.accent_for(speaker, SYSTEM_RGB)))[:3]
    names = show_name and not system and _R.PREFS.get("radio_speaker_names", True)

    margin = 30 * u
    rows = _wrap(text, f_body, sw - 2 * margin - 24 * u)
    row_h = f_body.get_linesize() + 2 * u
    n_rows = max(2, min(MAX_ROWS, len(rows)))
    strip_h = 8 * u + n_rows * row_h + 6 * u
    tab_h = (f_tab.cap + 3) * u
    lift = (tab_h - u) if names else 0
    s = pygame.Surface((sw, lift + strip_h), pygame.SRCALPHA)
    s.fill(STRIP_RGBA, (0, lift, sw, strip_h))
    s.fill(acc, (0, lift, sw, u))
    if names:
        _tab(s, f_tab, _R._base(speaker), acc, 20 * u, 0, u)
    if pips:
        idx, cnt = pips
        cnt = max(1, min(int(cnt), 24))
        px = sw - margin - cnt * 4 * u + u
        for i in range(cnt):
            col = acc if i <= idx else _mix(acc, (40, 42, 44), 0.7)
            s.fill(col, (px + i * 4 * u, lift + 4 * u, 2 * u, 2 * u))

    # body: wrapped from the full line, typed prefix, scroll past MAX_ROWS
    n = max(0, min(len(text), int(shown)))
    vis = _typed_rows(rows, n)
    scrolled = max(0, len(vis) - MAX_ROWS)
    vis = vis[scrolled:]
    tx, by = margin, lift + 8 * u
    ink = SYSTEM_RGB if system else TEXT_RGB
    for i, r in enumerate(vis):
        if not r:
            continue
        col = _mix(ink, (8, 10, 12), 0.5) if (scrolled and i == 0) else ink
        f_body.draw(s, r, (tx + u, by + i * row_h + u), (0, 0, 0))
        f_body.draw(s, r, (tx, by + i * row_h), col)
    typing = n < len(text)
    if typing and vis and (now // 220) % 2 == 0:
        cx = tx + f_body.size(vis[-1])[0] + f_body.scale
        s.fill(acc, (cx, by + (len(vis) - 1) * row_h, f_body.scale * 3, f_body.cap * f_body.scale))

    # right edge: bars bob while spoken, then step as the continue mark
    bx, bby = sw - margin - 13 * u, lift + strip_h - 11 * u
    if typing or (_vo_busy() and not system):
        _bars(s, bx, bby, u, acc, now, "talk")
    elif n >= total and prompt is not None:
        label = (hint if prompt else _T("cutscene.analyzing_file")) or ""
        _bars(s, bx, bby, u, acc, now, "next" if prompt else "wait")
        if label:
            lw = f_hint.size(label)[0]
            f_hint.draw(s, label, (bx - 4 * u - lw, bby + (5 * u - f_hint.cap * u) // 2), HINT_RGB)

    # open: wipe up from the letterbox, hard edge
    if bottom is None:
        bottom = sh - int(LETTER_H * sh / HEIGHT)
    full_h = s.get_height()
    y0 = bottom - full_h
    k = 1.0 if OPEN_MS <= 0 else _R._ease_out((now - st["open_t"]) / OPEN_MS)
    if k < 1.0:
        h = max(u, int(full_h * k) // u * u)
        surface.blit(s.subsurface((0, full_h - h, sw, h)), (0, bottom - h))
    else:
        surface.blit(s, (0, y0))
    return pygame.Rect(0, y0, sw, full_h)


def reset_box():
    """Next ``draw_box`` wipes in again (scene entry)."""
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
    f_tab = _fonts(u)[1]
    if band is None:
        band = (sh - int(LETTER_H * sh / HEIGHT), sh)
    top, bot = band
    rows = _wrap(text, f_body, int(sw - 160 * scale)) if text else []
    row_h = f_body.get_linesize()
    names = bool(speaker) and not _is_system(speaker) and _R.PREFS.get("radio_speaker_names", True)
    tab_h = (f_tab.cap + 3) * u
    head = (tab_h + 2 * u) if names else 0
    block = head + len(rows) * row_h
    y = top + max(u, (bot - top - block) // 2)
    acc = _R.accent_for(speaker, (255, 150, 60))
    if names:
        name = _R._base(speaker)
        tw = f_tab.size(name)[0] + 10 * u
        talk = _vo_busy()
        x = (sw - tw - (16 * u if talk else 0)) // 2
        r = _tab(surface, f_tab, name, acc, x, y, u)
        if talk:
            _bars(surface, r.right + 3 * u, y + (tab_h - 5 * u) // 2, u, acc, now, "talk")
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
