"""inspect_fpv.py - Mission 5 "[E] look": a short first-person look at the
thing instead of a radio line.

    can_play(key)      shot exists and a real display is up (headless -> text)
    start(key)         begin; M5 game_update freezes while active()
    update(dt_ms)      advance (called from systems.game_update) -> active
    draw(surface)      full-screen, over HUD (called from draw.game_draw)
    skip()             any key / click / ESC (app.py via m5.handle_inspect_event)
    render_frame(key, t) -> Surface   (also used by tools/_inspect_shots.py)

Camera: the shot is painted on a 1.3x canvas; the view rises from below
(the player lifting his eyes), then eases a push/pan between two keys with a
small hand-held sway. Vignette + grain on top, one caption line.
"""
import math
import os
import random

import pygame

from core.config import WIDTH, HEIGHT
from missions.m5 import inspect_art as _art
from missions.m5 import inspect_art_street as _street
from engine.text import T as _T  # RPE6 Phase 4 text table

FRAME_MS = 1000.0 / 60.0
RISE_MS = 520
HOLD_MS = 1500          # rest on the last frame, then close by itself
FADE_IN_MS = 300
FADE_OUT_MS = 220
FORCE_HEADLESS = False  # tools flip this to exercise the shots under the dummy driver

# key -> static painter, dynamic painter, camera ((fx, fy, zoom) start, end), ms, caption
SHOTS = {
    "notice": dict(static=_art.notice_static, dyn=None,
                   cam=((0.50, 0.29, 1.22), (0.45, 0.70, 1.55)), dur=4000,
                   caption="Every name crossed out. Mine's still there. For now."),
    "hq_tv": dict(static=_art.tv_static, dyn=_art.tv_dyn,
                  cam=((0.47, 0.62, 1.08), (0.48, 0.46, 1.58)), dur=3800,
                  caption="Somebody turned the volume down."),
    "portrait": dict(static=_art.portrait_static, dyn=None,
                     cam=((0.50, 0.33, 1.75), (0.50, 0.46, 1.0)), dur=3800,
                     caption="New frame, old smile."),
    "paint": dict(static=_street.paint_static, dyn=None,
                  cam=((0.36, 0.52, 1.35), (0.72, 0.78, 1.4)), dur=3800,
                  caption="Enough for the whole building."),
    "shop_tv": dict(static=_street.shop_static, dyn=_street.shop_dyn,
                    cam=((0.50, 0.42, 1.15), (0.48, 0.56, 1.6)), dur=3600,
                    caption="The shopkeeper pulled the shutter halfway."),
    "tram": dict(static=_street.tram_static, dyn=_street.tram_dyn,
                 cam=((0.33, 0.42, 1.45), (0.52, 0.64, 1.25)), dur=4000,
                 caption="Nobody was on it when it burned. Probably."),
}

_st = {"key": None, "t": 0.0, "close": None, "caption": ""}
_static = {}
_fx = {}


def can_play(key):
    if key not in SHOTS:
        return False
    if FORCE_HEADLESS:
        return True
    # Ask SDL which driver is really running. The env var is unreliable: other
    # modules (e.g. missions.m3) setdefault SDL_VIDEODRIVER=dummy at import
    # time, after the real window already exists.
    try:
        if pygame.display.get_init():
            return pygame.display.get_driver() != "dummy"
    except pygame.error:
        pass
    return os.environ.get("SDL_VIDEODRIVER", "") != "dummy"


def active():
    return _st["key"] is not None


# RPE6 A-007: optional observer on_change(active: bool, key) - the engine scene stack
# mirrors the inspect as an InspectScene overlay. None keeps the module as before.
on_change = None


def _notify(key):
    cb = on_change
    if cb is not None:
        cb(_st["key"] is not None, key)


def start(key, caption=None):
    _static_for(key)
    _st.update(key=key, t=0.0, close=None,
               caption=SHOTS[key]["caption"] if caption is None else caption)
    _notify(key)


def skip():
    if _st["key"] is not None and _st["close"] is None:
        _st["close"] = _st["t"]


def reset():
    key = _st["key"]
    _st.update(key=None, t=0.0, close=None, caption="")
    if key is not None:
        _notify(key)


def update(dt_ms=FRAME_MS):
    key = _st["key"]
    if key is None:
        return False
    _st["t"] += dt_ms
    t = _st["t"]
    if _st["close"] is None and t >= SHOTS[key]["dur"] + HOLD_MS:
        _st["close"] = t
    if _st["close"] is not None and t - _st["close"] >= FADE_OUT_MS:
        reset()
    return active()


def draw(surface):
    key = _st["key"]
    if key is None:
        return
    t = _st["t"]
    a = _art.ease(t / FADE_IN_MS)
    if _st["close"] is not None:
        a *= 1.0 - _art.ease((t - _st["close"]) / FADE_OUT_MS)
    frame = render_frame(key, t, _st["caption"])
    frame.set_alpha(int(255 * a))
    surface.blit(frame, (0, 0))


# -- rendering --
def _static_for(key):
    s = _static.get(key)
    if s is None:
        s = pygame.Surface((_art.CW, _art.CH))
        spr = None
        try:                                  # baked layer (src/game/art/m5/inspect_art.py)
            from art import m5 as _m5art
            from art.m5.inspect_art import KEYS
            if key in KEYS:
                spr = _m5art.get("inspect_art", KEYS.index(key))
        except Exception:
            spr = None
        if spr is not None and spr.get_size() == s.get_size():
            s.blit(spr, (0, 0))
        else:
            SHOTS[key]["static"](s)
        _static[key] = s
    return s


def canvas(key, t):
    """The whole painted set at time t (static layer + per-frame motion)."""
    shot = SHOTS[key]
    s = _static_for(key)
    if shot["dyn"] is None:
        return s
    s = s.copy()
    shot["dyn"](s, t)
    return s


def _vignette():
    v = _fx.get("vig")
    if v is None:
        sw, sh = 100, 70
        small = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for y in range(sh):
            for x in range(sw):
                d = math.hypot((x - sw / 2) / (sw / 2), (y - sh / 2) / (sh / 2))
                small.set_at((x, y), (0, 0, 0, int(215 * max(0.0, min(1.0, (d - 0.5) / 0.75)) ** 1.4)))
        v = _fx["vig"] = pygame.transform.smoothscale(small, (WIDTH, HEIGHT))
    return v


def _grain(t):
    g = _fx.get("grain")
    if g is None:
        g = []
        for i in range(4):
            rnd = random.Random(900 + i)
            s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            for _ in range(2600):
                c = rnd.choice((0, 255))
                pygame.draw.rect(s, (c, c, c, rnd.randint(10, 26)),
                                 (rnd.randrange(WIDTH), rnd.randrange(HEIGHT), 2, 2))
            g.append(s)
        _fx["grain"] = g
    return g[int(t / 60) % len(g)]


def render_frame(key, t, caption=None):
    shot = SHOTS[key]
    cv = canvas(key, t)
    (fx0, fy0, z0), (fx1, fy1, z1) = shot["cam"]
    u = _art.ease(t / shot["dur"])
    rise = 1.0 - _art.ease(t / RISE_MS)
    z = max(WIDTH / _art.CW + 0.01, (z0 + (z1 - z0) * u) * (1.0 - 0.05 * rise))
    sx = 7 * math.sin(t * 0.0011) + 3 * math.sin(t * 0.0029 + 0.7)
    sy = 5 * math.sin(t * 0.0014 + 1.3) + 2 * math.sin(t * 0.0037)
    vw, vh = WIDTH / z, HEIGHT / z
    cx = (fx0 + (fx1 - fx0) * u) * _art.CW + sx
    cy = (fy0 + (fy1 - fy0) * u) * _art.CH + sy + rise * HEIGHT * 0.22
    x0 = max(0.0, min(_art.CW - vw, cx - vw / 2))
    y0 = max(0.0, min(_art.CH - vh, cy - vh / 2))
    view = cv.subsurface((int(x0), int(y0), int(vw), int(vh)))
    out = pygame.transform.smoothscale(view, (WIDTH, HEIGHT))
    out.blit(_vignette(), (0, 0))
    out.blit(_grain(t), (0, 0))
    if caption is None:
        caption = shot["caption"]
    ca = _art.ease((t - 900) / 500)
    if caption and ca > 0:
        img = _art.font(21).render(caption, True, (232, 228, 214))
        bar = pygame.Surface((img.get_width() + 44, img.get_height() + 16), pygame.SRCALPHA)
        bar.fill((6, 8, 12, int(175 * ca)))
        bx = WIDTH // 2 - bar.get_width() // 2
        by = HEIGHT - 84
        out.blit(bar, (bx, by))
        img.set_alpha(int(255 * ca))
        out.blit(img, (bx + 22, by + 8))
    ha = _art.ease((t - 700) / 400)
    if ha > 0:
        hint = _art.font(13).render(_T("inspect_fpv.e_any_key_back"), True, (200, 196, 184))
        hint.set_alpha(int(150 * ha))
        out.blit(hint, (WIDTH - hint.get_width() - 22, HEIGHT - 30))
    return out
