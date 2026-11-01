"""Mission 7 beat 7 - Two Channels: Vasile's offer, Maru's reply, then the choice.

The whole screen is one field receiver faceplate:

* a tuning dial across the top: a live spectrum band (141.0 - 142.0) holding
  the two carriers, and an amber needle that glides to the tuned channel;
* two mirror-identical channel bays split by a seam.  Each bay owns its own
  transmission (Vasile types into the left one, Maru into the right one), a
  6x caller portrait, the callsign, an amber frequency readout, an RX lamp, a
  signal ladder on its outer edge and the key plate with the action;
* a TRANSMIT key straddling the seam.

Both bays are drawn by the same code with the same values; nothing marks one
as right (plot rule, ``docs/MISSION7_PLOT.md``).  Keyboard: A/D or 1/2 tune,
Enter/E/Space transmits.  Mouse: moving over a bay tunes it, a click on a bay
or on TRANSMIT sends.  The pick is written to ``STATE.m8_route`` and the
mission ends through the callback given to ``begin``.
"""
import random

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
NEEDLE_MS = 320          # needle glide between channels
LOCK_MS = 420            # signal ladder climb to the lock plateau
PING_MS = 1300           # standby lamps / ladder ping alternate at this period

# ── layout (1000x700 logical canvas, pixel unit u = 2) ─────────────────────
CASE_RECT = pygame.Rect(12, 12, WIDTH - 24, HEIGHT - 24)
NAMEPLATE = pygame.Rect(36, 28, 300, 40)
DIAL = pygame.Rect(36, 82, WIDTH - 72, 94)
WATERFALL = pygame.Rect(DIAL.x + 8, DIAL.y + 8, DIAL.w - 16, 50)
BAYS = (pygame.Rect(36, 192, 452, 404), pygame.Rect(512, 192, 452, 404))
TX_KEY = pygame.Rect(WIDTH // 2 - 90, 612, 180, 52)
F_LO, F_HI = 141.0, 142.0
SCALE_X0, SCALE_X1 = DIAL.x + 24, DIAL.right - 24
PORTRAIT = 144           # 24 px sheet frame at 6x, nearest only

# ── palette (ui.radio owns the receiver colours) ───────────────────────────
GROUND = (6, 7, 6)
POCKET = _radio._mix(_radio.CASE, _radio.CASE_LO, 0.55)
LABEL = (120, 130, 118)
DIM = (96, 106, 100)
NOISE = (38, 56, 44)
ENGRAVE_PLATE = (118, 122, 108)
ENGRAVE_INK = (30, 32, 28)
ENGRAVE_LIT = (154, 158, 144)
BAYER4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
POINTER = ("#.......", "##......", "#*#.....", "#**#....", "#***#...",
           "#****#..", "#*****#.", "#**####.", "#*#.....", "##......")

_S = {"t0": 0, "sel": -1, "done_at": 0, "cb": None, "prev": set(),
      "line_i": 0, "line_start": 0, "maru_at": 0, "sel_at": 0,
      "needle_from": 141.5, "mpos": None, "mdown": False, "mouse_seen": False}
_CACHE = {}


def _snd():
    return _m7_audio.instance(_manager)


def _mouse():
    """(canvas pos, left button down), or (None, False) without a pointer."""
    try:
        from core.config import get_scaled_mouse
        return get_scaled_mouse(), bool(pygame.mouse.get_pressed()[0])
    except Exception:
        return None, False


def begin(on_done):
    now = _now_ms()
    pos, down = _mouse()
    _S.update(t0=now, sel=-1, done_at=0, cb=on_done, prev=set(),
              line_i=0, line_start=now, maru_at=0, sel_at=now,
              needle_from=(F_LO + F_HI) / 2, mpos=pos, mdown=down, mouse_seen=False)
    snd = _snd()
    snd.stop_loops()
    snd.start_loop("m7_choice_hum", 0.22)
    snd.power_on()
    _radio._sfx("squelch_head", 0.22)


def _pressed(keys, *codes):
    try:
        return any(keys[c] for c in codes)
    except Exception:
        return False


def _freq(i):
    return float(CHANNELS[i][0])


def _line_start(i):
    """Radio-clock ms when line ``i`` went on air, 0 if it has not yet."""
    return _S["t0"] if i == 0 else _S["maru_at"]


def _start_maru(now):
    if not _S["maru_at"]:
        _S["maru_at"] = now
        _radio._sfx("squelch_head", 0.22)


def _needle(now):
    """Needle frequency: eased glide from the last position to the target."""
    target = _freq(_S["sel"]) if _S["sel"] >= 0 else (F_LO + F_HI) / 2
    k = _radio._ease_out((now - _S["sel_at"]) / float(NEEDLE_MS))
    return _S["needle_from"] + (target - _S["needle_from"]) * k


def _select(i):
    if i == _S["sel"]:
        return
    now = _now_ms()
    _S["needle_from"] = _needle(now)
    _S["sel"] = i
    _S["sel_at"] = now
    _S["line_i"] = i
    if i == 1:
        _start_maru(now)
    _S["line_start"] = _line_start(i)
    _snd().radio_tune()
    _snd().click()


def _transmit(now):
    if _S["sel"] < 0 or _S["done_at"]:
        return
    STATE.m8_route = OPTIONS[_S["sel"]][1]
    _S["done_at"] = now
    _snd().tx_lock()
    _snd().stop_loop("m7_choice_hum")


def _hit(pos):
    """What the pointer is over: a bay index, "tx", or None."""
    if pos is None:
        return None
    for i, bay in enumerate(BAYS):
        if bay.collidepoint(pos):
            return i
    return "tx" if TX_KEY.collidepoint(pos) else None


def _update_mouse(now):
    pos, down = _mouse()
    moved = pos is not None and _S["mpos"] is not None and pos != _S["mpos"]
    click = down and not _S["mdown"]
    _S["mpos"], _S["mdown"] = pos, down
    if not (moved or click):
        return
    _S["mouse_seen"] = True
    hit = _hit(pos)
    if isinstance(hit, int):
        _select(hit)
        if click:
            _transmit(now)
    elif hit == "tx" and click:
        _transmit(now)


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
    if not _S["maru_at"] and now - _S["t0"] >= BROADCAST_MS:
        _start_maru(now)
        if _S["sel"] < 0:
            _S["line_i"] = 1
            _S["line_start"] = now
    if "l" in fresh or "1" in fresh:
        _select(0)
    elif "r" in fresh or "2" in fresh:
        _select(1)
    elif "ok" in fresh:
        _transmit(now)
    if not _S["done_at"]:
        _update_mouse(now)
    return (0, 0)


# ── drawing helpers ────────────────────────────────────────────────────────
def _fx(f):
    return int(SCALE_X0 + (f - F_LO) / (F_HI - F_LO) * (SCALE_X1 - SCALE_X0))


def _chamfer(s, rect, bg, u):
    """Cut a one-unit corner off each corner of ``rect`` (bg shows through)."""
    r = pygame.Rect(rect)
    for x, y in ((r.x, r.y), (r.right - u, r.y), (r.x, r.bottom - u), (r.right - u, r.bottom - u)):
        s.fill(bg, (x, y, u, u))


def _glass(s, rect, u):
    """Recessed display glass with the radio's faint scanlines."""
    _radio._bevel_box(s, rect.inflate(2 * u, 2 * u), _radio.GLASS, _radio.CASE_LO,
                      _radio.CASE_HI, u)
    s.fill(_radio.GLASS, rect)
    s.fill(_radio.GLASS_HI, (rect.x, rect.y, rect.w, u))
    for y in range(rect.y + u, rect.bottom, 2 * u):
        s.fill((14, 20, 16), (rect.x, y, rect.w, max(1, u // 2)))


def _keycap(s, text, x, cy, u):
    """Small key legend cap; returns its right edge."""
    f = pixfont.font("R5", u)
    w = f.size(text)[0] + 6 * u
    cap = pygame.Rect(x, cy - 5 * u, w, 10 * u)
    _radio._bevel_box(s, cap, _radio.CASE_LO, _radio.CASE_HI, _radio.CASE_INK, u)
    _chamfer(s, cap, _radio.CASE, u)
    f.draw(s, text, (cap.x + 3 * u, cap.y + 2 * u + u // 2), _radio.BODY_RGB)
    return cap.right


def _bay_parts(i):
    """Geometry of bay ``i``: content x, post rect, portrait, text well, key plate."""
    bay = BAYS[i]
    cx = bay.x + 44 if i == 0 else bay.x + 20
    cw = bay.w - 64
    post = pygame.Rect(bay.x + 18 if i == 0 else bay.right - 30, bay.y + 20, 12, bay.h - 40)
    return {
        "cx": cx, "cw": cw, "post": post,
        "screen": pygame.Rect(cx, bay.y + 20, PORTRAIT, PORTRAIT),
        "text": pygame.Rect(cx, bay.y + 184, cw, 108),
        "plate": pygame.Rect(cx, bay.y + 312, cw, 64),
        "info_x": cx + PORTRAIT + 20,
    }


def _build_chassis(u):
    s = pygame.Surface((WIDTH, HEIGHT))
    s.fill(GROUND)
    case = CASE_RECT
    s.fill(_radio.CASE_INK, case.inflate(2 * u, 2 * u))
    _radio._bevel_box(s, case, _radio.CASE, _radio.CASE_HI, _radio.CASE_LO, u)
    brush = _radio._mix(_radio.CASE, _radio.CASE_LO, 0.25)
    for y in range(case.y + 3 * u, case.bottom - 2 * u, 3 * u):
        s.fill(brush, (case.x + u, y, case.w - 2 * u, max(1, u // 2)))
    for x, y in ((case.x + 2 * u, case.y + 2 * u), (case.right - 4 * u, case.y + 2 * u),
                 (case.x + 2 * u, case.bottom - 4 * u), (case.right - 4 * u, case.bottom - 4 * u)):
        _radio._screw(s, x, y, u)

    # engraved nameplate
    plate = NAMEPLATE
    s.fill(_radio.CASE_INK, plate.inflate(2 * u, 2 * u))
    _radio._bevel_box(s, plate, ENGRAVE_PLATE, ENGRAVE_LIT, _radio._mix(ENGRAVE_PLATE, (0, 0, 0), 0.35), u)
    _chamfer(s, plate.inflate(2 * u, 2 * u), _radio.CASE, u)
    head = pixfont.font("R7", u)
    ty = plate.y + (plate.h - head.cap * u) // 2
    head.draw(s, "KR-7 FIELD RECEIVER", (plate.x + 7 * u, ty + u // 2 or 1), ENGRAVE_LIT)
    head.draw(s, "KR-7 FIELD RECEIVER", (plate.x + 7 * u, ty), ENGRAVE_INK)
    _radio._screw(s, plate.right - 5 * u, plate.centery - u, u)
    _radio._screw(s, plate.x + 2 * u, plate.centery - u, u)

    # dial: glass, band scale ticks and labels
    _glass(s, DIAL, u)
    lab = pixfont.font("R5", u)
    tick_y = WATERFALL.bottom + 4
    for k in range(0, 21):
        x = _fx(F_LO + k * 0.05)
        major = k % 2 == 0
        s.fill((96, 108, 98) if major else (58, 68, 60), (x - u // 2, tick_y, u, 4 * u if major else 2 * u))
        if major:
            text = "%.1f" % (F_LO + k * 0.05)
            w = lab.size(text)[0]
            lab.draw(s, text, (x - w // 2, tick_y + 6 * u), LABEL)

    # bays: recessed pockets, seam, portrait bezels, text wells, ladder wells
    for i, bay in enumerate(BAYS):
        s.fill(_radio.CASE_INK, bay.inflate(2 * u, 2 * u))
        _radio._bevel_box(s, bay, POCKET, _radio.CASE_LO, _radio.CASE_HI, u, inset=True)
        p = _bay_parts(i)
        _radio._bevel_box(s, p["screen"].inflate(4 * u, 4 * u), (8, 10, 9),
                          _radio.CASE_LO, _radio.CASE_HI, u)
        _glass(s, p["text"], u)
        _radio._bevel_box(s, p["post"].inflate(2 * u, 2 * u), _radio.CASE_INK,
                          _radio.CASE_LO, _radio.CASE_HI, u)
    seam_x = WIDTH // 2
    s.fill(_radio.CASE_LO, (seam_x - u, BAYS[0].y, u, BAYS[0].h))
    s.fill(_radio.CASE_HI, (seam_x, BAYS[0].y, u, BAYS[0].h))

    # key legends either side of TRANSMIT
    cy = TX_KEY.centery
    keys = ("A", "D", None, "1", "2")
    total = sum(_keycap_w(lab, k, u) + 2 * u if k else 4 * u for k in keys)
    x = TX_KEY.x - 20 - total - 2 * u - lab.size("TUNE")[0]
    for key in keys:
        x = _keycap(s, key, x, cy, u) + 2 * u if key else x + 4 * u
    lab.draw(s, "TUNE", (x + 2 * u, cy - 2 * u - u // 2), LABEL)
    x = _keycap(s, "ENTER", TX_KEY.right + 20, cy, u)
    lab.draw(s, "TRANSMIT", (x + 4 * u, cy - 2 * u - u // 2), LABEL)
    return s


def _keycap_w(font, text, u):
    return font.size(text)[0] + 6 * u


def _chassis(u):
    key = ("chassis", u)
    hit = _CACHE.get(key)
    if hit is None:
        hit = _CACHE[key] = _build_chassis(u)
    return hit


def _scanlines(w, h, u, alpha=60):
    key = ("scan", w, h, u, alpha)
    hit = _CACHE.get(key)
    if hit is None:
        hit = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(u, h, 2 * u):
            hit.fill((0, 0, 0, alpha), (0, y, w, max(1, u // 2)))
        _CACHE[key] = hit
    return hit


# ── dynamic parts ──────────────────────────────────────────────────────────
def _draw_dial(surface, now, u):
    wf = WATERFALL
    col_w = 2 * u
    n = (SCALE_X1 - SCALE_X0) // col_w
    rng = random.Random(now // 80)
    carriers = [(_fx(_freq(i)), _radio.accent_for(LINES[i][0], LINES[i][1])) for i in range(2)]
    sel, done = _S["sel"], bool(_S["done_at"])
    for j in range(n):
        x = SCALE_X0 + j * col_w
        mid = x + col_w // 2
        h = rng.randint(1, 6) * u
        col = NOISE
        for i, (cx, acc) in enumerate(carriers):
            d = abs(mid - cx)
            if d <= col_w:
                tuned = sel == i
                full = wf.h if (tuned and done) else int(wf.h * (0.86 if tuned else 0.74))
                h = full - rng.randint(0, 2) * u
                col = _radio._mix(acc, (255, 255, 255), 0.3) if tuned else acc
            elif d <= 4 * col_w:
                h = max(h, int(wf.h * 0.3) - rng.randint(0, 3) * u)
                col = _radio._mix(acc, NOISE, 0.55)
        surface.fill(col, (x, wf.bottom - h, col_w - u // 2, h))
    surface.blit(_scanlines(wf.w, wf.h, u), wf.topleft)
    x = _fx(_needle(now))
    surface.fill(_radio.AMBER, (x - u // 2, DIAL.y + 2 * u, u, DIAL.h - 4 * u))
    surface.fill(_radio.AMBER, (x - 2 * u, DIAL.y + 2 * u, 4 * u, 2 * u))
    surface.fill(_radio.AMBER_BG, (x - 2 * u, DIAL.bottom - 4 * u, 4 * u, 2 * u))


def _ladder(surface, i, post, acc, now, u):
    seg_h, step = 2 * u, 3 * u
    n = post.h // step
    tuned = _S["sel"] == i
    if tuned:
        k = _radio._ease_out((now - _S["sel_at"]) / float(LOCK_MS))
        lit = int(n * 0.86 * k) - (1 if (now // 140 + i) % 3 == 0 else 0)
        if _S["done_at"]:
            lit = n
    else:
        lit = random.Random(now // 90 * 7 + i).randint(2, 6)
    ping = -1
    if _S["sel"] < 0 and (now // PING_MS) % 2 == i:
        ping = int(n * ((now % PING_MS) / float(PING_MS)))
    for j in range(n):
        y = post.bottom - (j + 1) * step + u
        if j < lit:
            col = _radio.LED_RED if j >= n - 2 else acc
        elif j == ping:
            col = _radio._mix(acc, (255, 255, 255), 0.4)
        else:
            col = _radio.LED_OFF
        surface.fill(col, (post.x + u, y, post.w - 2 * u, seg_h))


def _static(surface, rect, now, seed, density, u):
    rng = random.Random(now // 40 * 131 + seed)
    cells = (rect.w // u) * (rect.h // u)
    for _ in range(int(cells * density)):
        x = rect.x + rng.randrange(rect.w // u) * u
        y = rect.y + rng.randrange(rect.h // u) * u
        v = rng.randrange(50, 200)
        surface.fill((v, v, v), (x, y, u, u))


def _draw_bay(surface, i, now, u):
    who, col, text = LINES[i]
    acc = _radio.accent_for(who, col)
    bay = BAYS[i]
    p = _bay_parts(i)
    tuned = _S["sel"] == i
    start = _line_start(i)
    age = now - start if start else -1
    type_ms = max(1, len(text)) * _radio.TYPE_MS_PER_CHAR

    _ladder(surface, i, p["post"], acc, now, u)

    # caller-ID screen: dark until the line comes on air, static while it tunes
    scr = p["screen"]
    surface.fill(_radio._mix(acc, (6, 8, 8), 0.82 if age >= 0 else 0.94), scr)
    if age < 0:
        _static(surface, scr, now, i, 0.05, u)
    else:
        if age > _radio.STATIC_MS * 0.55:
            surface.blit(_radio._portrait(who, PORTRAIT, acc), scr.topleft)
        if age < _radio.STATIC_MS:
            _static(surface, scr, now, i, 0.4 * (1.0 - age / float(_radio.STATIC_MS)), u)
    surface.blit(_scanlines(PORTRAIT, PORTRAIT, u, 46), scr.topleft)
    surface.fill((255, 255, 255), (scr.x + u, scr.y + u, u, 3 * u))

    # callsign, channel, frequency tray, RX lamp
    x = p["info_x"]
    big = pixfont.font("R7", 2 * u)
    big.draw(surface, who, (x, bay.y + 24), acc if tuned else _radio.BODY_RGB)
    lab = pixfont.font("R5", u)
    lab.draw(surface, "CHANNEL " + CHANNELS[i][1], (x, bay.y + 62), LABEL)
    fr = pixfont.font("R7", 3 * u // 2)
    tray = pygame.Rect(x, bay.y + 84, fr.size(CHANNELS[i][0])[0] + 8 * u, fr.cap * fr.scale + 6 * u)
    surface.fill(_radio.AMBER_BG if tuned else _radio.CASE_INK, tray)
    surface.fill(_radio._mix(_radio.AMBER_BG, (0, 0, 0), 0.5) if tuned else _radio.CASE_LO,
                 (tray.x, tray.y, tray.w, u))
    fr.draw(surface, CHANNELS[i][0], (tray.x + 4 * u, tray.y + 3 * u),
            _radio.AMBER if tuned else (150, 160, 148))
    on_air = 0 <= age < type_ms + 900
    ry = bay.y + 140
    lab.draw(surface, "RX", (x, ry), LABEL)
    lamp = _radio.LED_GREEN if on_air else _radio.LED_OFF
    lx = x + lab.size("RX")[0] + 2 * u
    surface.fill(lamp, (lx, ry + u // 2, 2 * u, 2 * u))
    if on_air:
        surface.fill(_radio._mix(lamp, (255, 255, 255), 0.5), (lx, ry + u // 2, u, u))

    # the transmission, typed into this bay's glass
    well = p["text"]
    body = pixfont.font("R7", u)
    tx, ty = well.x + 4 * u, well.y + 4 * u
    if age < 0:
        lab.draw(surface, "NO CARRIER", (tx, ty + u), DIM)
    else:
        rows = _radio._wrap(text, body, well.w - 8 * u)
        left = int(len(text) * min(1.0, age / float(type_ms)))
        row_h = body.get_linesize()
        last_w, last_row = 0, 0
        for r_i, row in enumerate(rows):
            if left <= 0:
                break
            part = row[:left]
            left -= len(row) + 1
            body.draw(surface, part, (tx + u // 2 or 1, ty + r_i * row_h + (u // 2 or 1)), (0, 0, 0))
            last_w = body.draw(surface, part, (tx, ty + r_i * row_h), _radio.BODY_RGB)
            last_row = r_i
        if age < type_ms and (now // 220) % 2 == 0:
            surface.fill(acc, (tx + last_w + body.scale, ty + last_row * row_h,
                               body.scale * 3, body.get_ascent()))

    _draw_plate(surface, i, p["plate"], tuned, now, u)
    if tuned:
        pygame.draw.rect(surface, _radio.AMBER, bay, u)


def _draw_plate(surface, i, plate, tuned, now, u):
    sunk = tuned and bool(_S["done_at"])
    r = plate.move(0, u) if sunk else plate
    if tuned:
        fill, hi, lo, ink = (_radio.AMBER, (255, 214, 140), (170, 110, 30), _radio.CASE_INK)
    else:
        fill, hi, lo, ink = (_radio.CASE_LO, _radio.CASE_HI, _radio.CASE_INK, _radio.BODY_RGB)
    if sunk:
        hi, lo = lo, hi
    surface.fill(_radio.CASE_INK, plate.inflate(2 * u, 2 * u))
    _radio._bevel_box(surface, r, fill, hi, lo, u)
    _chamfer(surface, plate.inflate(2 * u, 2 * u), POCKET, u)
    cap = pygame.Rect(r.x + 4 * u, r.y + 4 * u, r.h - 8 * u, r.h - 8 * u)
    surface.fill(_radio.CASE_INK if tuned else _radio.GLASS, cap)
    _chamfer(surface, cap, fill, u)
    digit = pixfont.font("R7", 3 * u // 2)
    dw = digit.size(CHANNELS[i][1])[0]
    digit.draw(surface, CHANNELS[i][1], (cap.centerx - dw // 2, cap.centery - digit.cap * digit.scale // 2),
               _radio.AMBER if tuned else _radio.BODY_RGB)
    act = pixfont.font("R7", u)
    act.draw(surface, OPTIONS[i][0], (cap.right + 6 * u, r.centery - act.cap * u // 2), ink)
    if tuned:
        led = _radio.LED_GREEN
    else:
        blink = _S["sel"] >= 0 or (now // PING_MS) % 2 == i
        led = _radio.AMBER if (blink and (now // 325) % 2 == 0) else _radio.LED_OFF
    lx, ly = r.right - 8 * u, r.centery - u
    surface.fill(_radio.CASE_INK, (lx - u, ly - u, 4 * u, 4 * u))
    surface.fill(led, (lx, ly, 2 * u, 2 * u))


def _draw_tx(surface, now, u):
    armed = _S["sel"] >= 0
    sent = bool(_S["done_at"])
    hover = _S["mouse_seen"] and _hit(_S["mpos"]) == "tx" and armed and not sent
    r = TX_KEY.move(0, u) if sent else TX_KEY
    hi = _radio.CASE_HI if not hover else _radio._mix(_radio.CASE_HI, (255, 255, 255), 0.25)
    lo = _radio.CASE_INK
    if sent:
        hi, lo = lo, _radio.CASE_HI
    surface.fill(_radio.CASE_INK, TX_KEY.inflate(2 * u, 2 * u))
    _radio._bevel_box(surface, r, _radio.CASE if armed else _radio.CASE_LO, hi, lo, u)
    _chamfer(surface, TX_KEY.inflate(2 * u, 2 * u), _radio.CASE, u)
    if sent:
        lamp = _radio._mix(_radio.LED_RED, (255, 255, 255), 0.35)
    elif armed:
        lamp = _radio.LED_RED
    else:
        lamp = (60, 30, 28)
    lr = pygame.Rect(r.x + 8 * u, r.centery - 3 * u, 6 * u, 6 * u)
    surface.fill(_radio.CASE_INK, lr.inflate(2 * u, 2 * u))
    surface.fill(lamp, lr)
    if armed:
        surface.fill(_radio._mix(lamp, (255, 255, 255), 0.5), (lr.x, lr.y, 2 * u, 2 * u))
    f = pixfont.font("R7", u)
    f.draw(surface, "TRANSMIT", (lr.right + 6 * u, r.centery - f.cap * u // 2),
           _radio.BODY_RGB if armed else DIM)


def _draw_header(surface, now, u):
    lab = pixfont.font("R5", u)
    x = DIAL.right - lab.size("PWR")[0] - 6 * u
    y = NAMEPLATE.centery - 2 * u
    lab.draw(surface, "PWR", (x, y), LABEL)
    surface.fill(_radio.LED_GREEN, (x + lab.size("PWR")[0] + 2 * u, y + u // 2, 2 * u, 2 * u))


def _draw_pointer(surface, u):
    if not _S["mouse_seen"] or _S["mpos"] is None or _S["done_at"]:
        return
    mx, my = _S["mpos"]
    fill = _radio.AMBER if _hit(_S["mpos"]) is not None else _radio.BODY_RGB
    for y, row in enumerate(POINTER):
        for x, ch in enumerate(row):
            if ch != ".":
                surface.fill(_radio.CASE_INK if ch == "#" else fill, (mx + x * u, my + y * u, u, u))


def _dissolve(surface, k, u):
    """Bayer ordered-dither fade: 4x4 cells of 2u px drop to black in order."""
    n = min(16, int(k * 17))
    if n <= 0:
        return
    if n >= 16:
        surface.fill((0, 0, 0))
        return
    key = ("dissolve", n, u, surface.get_size())
    hit = _CACHE.get("dissolve")
    if hit is None or hit[0] != key:
        c = 2 * u
        tile = pygame.Surface((4 * c, 4 * c))
        tile.fill((255, 0, 255))
        for y in range(4):
            for x in range(4):
                if BAYER4[y][x] < n:
                    tile.fill((0, 0, 0), (x * c, y * c, c, c))
        w, h = surface.get_size()
        veil = pygame.Surface((w, h))
        for y in range(0, h, 4 * c):
            for x in range(0, w, 4 * c):
                veil.blit(tile, (x, y))
        veil.set_colorkey((255, 0, 255))
        hit = _CACHE["dissolve"] = (key, veil)
    surface.blit(hit[1], (0, 0))


def draw(surface):
    now = _now_ms()
    u = _radio.unit_for(surface)
    surface.blit(_chassis(u), (0, 0))
    _draw_header(surface, now, u)
    _draw_dial(surface, now, u)
    for i in range(2):
        _draw_bay(surface, i, now, u)
    _draw_tx(surface, now, u)
    _draw_pointer(surface, u)
    if _S["done_at"]:
        _dissolve(surface, (now - _S["done_at"]) / float(FADE_MS), u)
