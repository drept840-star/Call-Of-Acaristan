"""M6 3D scene performance governor (train scene + rail-yard fight).

Both playable M6 scenes render engine3d at ``RES`` (0.64 -> 640x448, the PS2
frame) and then upscale.  Almost every cost in those two scenes scales with
the *buffer area*, not with the actor count:

    * the GPU -> CPU readback of the colour and depth targets,
    * ``GLRenderer._composite`` (the depth-masked sprite pass),
    * the grade LUT and the ``present_crisp`` upscale,
    * the sky repaint and the software backend's per-pixel polygon fill.

So when a machine cannot hold 60 fps, the one lever that buys all of them at
once is the internal resolution - and at this scale it barely shows, because
the frame is already upscaled 1.56x with a sharp-bilinear filter.

Tiers
    quality_3d = 2 -> 0.64 (the authored look, default)
    quality_3d = 1 -> 0.56
    quality_3d = 0 -> 0.48

**The scale is static by default.**  The scene simply renders at the tier the
``quality_3d`` setting asks for; there is no measurement, no watchdog and no
logging in the frame path.  That is the mode to ship a fix in: an adaptive
loop that changes a GL target size while the player is being shot at is a
*hitch generator* on real drivers, and a stutter cannot be debugged while the
thing that is meant to fix it keeps moving.

The adaptive path exists behind ``ACA_M6_AUTO=1`` (measure once in the
warm-up, then a frame-interval watchdog with a cooldown).  It is a tool, not
the default.

Determinism: everything here is inert under ``ACA_FREEZE=1`` (golden / parity
/ smoke harnesses), so a gate run always gets the setting's tier.

Overrides (environment)
    ACA_M6_RES=0.48     force a fixed scale (wins over everything)
    ACA_M6_AUTO=1       enable measure + watchdog (opt in)
    ACA_M6_DRS=0        legacy alias for "no adaptive path"
    ACA_M6_HITCHLOG=1   append spikes to build/m6_hitches.log
    ACA_M6_HUD=1        on-screen ms/fps strip
    ACA_M6_DEBUG=1      one log line per resolved scale
"""
import os

BUDGET_MS = 12.0          # draw() budget for 60 fps (update + present live outside)
MIN_SCALE = 0.34          # never go below this: HUD text read-through gets mushy
SCALES = (0.64, 0.56, 0.48, 0.40, 0.34)     # tiers, best first
_TIER_BY_QUALITY = {2: 0, 1: 1, 0: 2}

_state = {
    "scale": None,        # locked scale, None until first use
    "tier": None,
    "planned": set(),     # scene names already measured
    "base": None,
    "why": "",            # human-readable reason, for the one-off log line
}


def _env_float(name):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _frozen():
    """True when a harness pinned the frame (golden/parity/smoke runs)."""
    return os.environ.get("ACA_FREEZE", "") == "1"


def auto():
    """True only when the adaptive path (measure + watchdog) was opted into."""
    if _frozen() or _env_float("ACA_M6_RES"):
        return False
    if os.environ.get("ACA_M6_DRS", "") == "0":
        return False
    return os.environ.get("ACA_M6_AUTO", "") == "1"


def _quality():
    q = _state.get("quality")
    if q is None:
        try:
            from core.user_settings import SETTINGS      # lazy: settings owner
            q = int(getattr(SETTINGS, "quality_3d", 2))
        except Exception:
            q = 2
        _state["quality"] = q
    return q


def base_scale():
    """The scale the player's ``quality_3d`` setting asks for."""
    fixed = _env_float("ACA_M6_RES")
    if fixed:
        return min(SCALES[0], max(MIN_SCALE, fixed))
    if _state["base"] is None:
        tier = _TIER_BY_QUALITY.get(_quality(), 0)
        _state["base"] = SCALES[tier]
        _state["tier"] = tier
    return _state["base"]


def scale():
    """The internal render scale the M6 scenes should use right now."""
    if _state["scale"] is None:
        _state["scale"] = base_scale()
        _state["tier"] = SCALES.index(_state["base"]) if _state["base"] in SCALES else 0
    return _state["scale"]


def buffer_size(size, aspect_ref=None):
    """``(w, h)`` of the internal render buffer at the current scale."""
    w, h = size
    s = scale()
    return max(64, int(w * s)), max(64, int(h * s))


def detail():
    """0.45..1.0 multiplier for optional per-frame flourish (snow, motes,
    light count).  1.0 at the authored tier, so nothing changes on a machine
    that is already holding the frame."""
    base = base_scale()
    if base <= 0.0:
        return 1.0
    return max(0.45, min(1.0, 0.45 + 0.55 * (scale() / base)))


def light_cap(default):
    """Point-light budget for the tier (the shader clamps to 8 anyway)."""
    return max(4, int(round(default * detail())))


def _log(msg):
    print("M6 3D: %s" % msg)


def set_scale(value, why=""):
    value = round(min(SCALES[0], max(MIN_SCALE, float(value))), 2)
    if value == _state["scale"]:
        return False
    _state["scale"] = value
    _state["why"] = why
    return True


def reset():
    """Forget the measurement (the setting may have changed in the options)."""
    _state["planned"].clear()
    _state["scale"] = None
    _state["base"] = None
    _state["tier"] = None


def _time_draw(draw_fn, frames=2):
    import time
    best = None
    for _ in range(frames):
        t0 = time.perf_counter()
        draw_fn()
        ms = (time.perf_counter() - t0) * 1000.0
        if best is None or ms < best:
            best = ms
    return best
def plan(name, draw_fn, frames=2):
    """Measure and lock the scale for one scene.  Idempotent per process.

    ``draw_fn`` must draw a complete frame of the scene (it may be called a
    few times; the scene's own caches make the repeat cheap).  Returns the
    locked scale.
    """
    if name in _state["planned"]:
        return scale()
    _state["planned"].add(name)
    if not auto():
        # static tier from the setting - nothing measured, nothing adaptive
        _state["scale"] = base_scale()
        if os.environ.get("ACA_M6_DEBUG", "") == "1":
            _log("render scale %.2f (static, quality_3d tier)"
                 % _state["scale"])
        return _state["scale"]

    tier = SCALES.index(base_scale())
    _state["scale"] = SCALES[tier]
    start = SCALES[tier]
    ms = _time_draw(draw_fn, frames)
    while ms > BUDGET_MS and tier + 1 < len(SCALES):
        prev_ms, prev_scale = ms, _state["scale"]
        tier += 1
        _state["scale"] = SCALES[tier]
        ms = _time_draw(draw_fn, frames)
        if ms > prev_ms * 0.92:
            # The frame is not buffer-bound (the software backend spends its
            # time emitting polygons in Python, not filling pixels), so the
            # smaller buffer buys nothing: keep the sharper picture.
            _state["scale"] = prev_scale
            ms = prev_ms
            break
    if start != _state["scale"]:
        _log("render scale %.2f -> %.2f (draw %.1f ms, budget %.1f)"
             % (start, _state["scale"], ms, BUDGET_MS))
    elif os.environ.get("ACA_M6_DEBUG", "") == "1":
        _log("render scale %.2f (draw %.1f ms, budget %.1f)"
             % (_state["scale"], ms, BUDGET_MS))
    return _state["scale"]


# ── live watchdog ────────────────────────────────────────────────────────
# The warm-up measurement times two frames of a scene nobody is playing yet,
# which is not the same thing as "this machine holds 60 fps in the fight": a
# GPU that is fine on an idle set can still fall over with eight actors, the
# viewmodel overlay and the whole yard on screen.  So while the scene runs, the
# presented frame interval is watched too, and one tier is dropped when the
# median sits above SLOW_MS for SLOW_FRAMES frames - at most MAX_STEPS times
# per scene.  Each step re-bakes the set (~100 ms hitch), so the rule is
# deliberately hard to trigger and never treads back up (no oscillation).
SLOW_MS = 22.0             # ~45 fps: below this the game cannot hold 60
SLOW_FRAMES = 90
MAX_STEPS = 2
STEP_COOLDOWN_S = 6.0      # never two tier changes close together

_watch = {
    "scene": None,
    "last": None,
    "samples": [],         # rolling window of frame intervals (ms)
    "steps": 0,
    "last_step": -1e9,
    "reports": 0,
}


def _median(xs):
    s = sorted(xs)
    return s[len(s) // 2]


surface_ref = [None]     # the frame surface, for the optional stats overlay


def govern(scene, now=None, surface=None):
    """Feed one presented frame of ``scene`` (call at the end of its draw).

    Returns True when the scale was just lowered (the caller's renderer is
    stale and the next frame must rebuild).  Uses the OS clock on purpose:
    this is profiling, not game time (AGENTS.md keeps real timestamps on the
    OS clocks).  Does nothing under a pinned harness clock.
    """
    if not auto():
        # default path: no clock read, no samples, no allocation, no I/O
        return False
    if os.environ.get("ACA_M6_HUD", "") == "1" and surface_ref[0] is not None:
        _overlay(surface_ref[0])
    if surface is not None:
        surface_ref[0] = surface
    if _watch["scene"] != scene:
        _watch["scene"] = scene
        _watch["last"] = None
        _watch["samples"] = []
    if now is None:
        import time
        now = time.perf_counter()
    last = _watch["last"]
    _watch["last"] = now
    if last is None:
        return False
    ms = (now - last) * 1000.0
    if ms > 400.0:
        return False              # a load/pause hitch, not a frame: discard
    samples = _watch["samples"]
    samples.append(ms)
    _HITCH["median"] = _median(samples[-30:])
    # a hitch is a frame far over this machine's own median: log it with the
    # phases that were live in it (see note_phase), then carry on
    if (os.environ.get("ACA_M6_HITCHLOG", "") == "1"
            and ms > 3.0 * (_HITCH["median"] or 16.0) and ms > 40.0):
        _write_hitch(ms, now)          # opt-in: disk I/O must never ride the frame
    _HITCH["window"].clear()
    if len(samples) < SLOW_FRAMES:
        return False
    med = _median(samples)
    samples.clear()
    if _watch["reports"] < 4 and os.environ.get("ACA_M6_DEBUG", "") == "1":
        _watch["reports"] += 1
        _log("%s: %.1f ms/frame median at scale %.2f"
             % (scene, med, scale()))
    now_s = now
    if _watch["steps"] and now_s - _watch["last_step"] < STEP_COOLDOWN_S:
        return False
    _watch["last_step"] = now_s
    if med <= SLOW_MS or _watch["steps"] >= MAX_STEPS:
        return False
    if scale() <= MIN_SCALE:
        return False
    _watch["steps"] += 1
    _state["planned"].clear()      # the scene may re-measure at the new size
    set_scale(scale() - 0.08, "watchdog")
    _log("%s: %.1f ms/frame median -> render scale %.2f"
         % (scene, med, scale()))
    return True


def watchdog_reset():
    _watch["steps"] = 0
    _watch["samples"].clear()
    _watch["last"] = None
    _watch["scene"] = None


# ── diagnostics: hitch log + on-screen stats ─────────────────────────────
# A player cannot report "it stutters at the truck" usefully, and the frame
# time on their machine is the only place the remaining hitches exist.  Both
# scenes already time every presented frame (``govern``); this records the
# spikes to a file (always) and can draw a one-line stats strip (opt in).
_HITCH = {
    "log": None,          # path once opened
    "last": 0.0,
    "median": None,
    "window": [],
    "scale": None,
}


def _log_path():
    if _HITCH["log"]:
        return _HITCH["log"]
    try:
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))
        d = os.path.join(root, "build")
        os.makedirs(d, exist_ok=True)
        _HITCH["log"] = os.path.join(d, "m6_hitches.log")
    except Exception:
        _HITCH["log"] = os.path.join(os.getcwd(), "m6_hitches.log")
    return _HITCH["log"]


def note_phase(name, ms):
    """Optional: scenes report their phases so a logged hitch names one."""
    if ms >= 1.5:
        _HITCH["window"].append((name, ms))


def _write_hitch(ms, now):
    try:
        import time as _t
        stamp = _t.strftime("%Y-%m-%d %H:%M:%S", _t.localtime())
        phases = sorted(_HITCH["window"], key=lambda kv: -kv[1])[:6]
        line = "%s frame=%.1fms scale=%.2f scale_changes=%d phases=%s\n" % (
            stamp, ms, scale(), _watch["steps"],
            " ".join("%s:%.1f" % (n, v) for n, v in phases) or "-")
        with open(_log_path(), "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        pass


def stats_line():
    """One-line status for an on-screen overlay (ACA_M6_HUD=1)."""
    med = _HITCH["median"]
    if med is None:
        return ""
    try:
        from engine3d import gl_available
        backend = "GL" if gl_available() else "SOFTWARE"
    except Exception:
        backend = "?"
    return "M6 %s  scale %.2f  %4.1f ms  (%.0f fps)" % (
        backend, scale(), med, 1000.0 / med if med > 0 else 0.0)


def _overlay(surface):
    text = stats_line()
    if not text:
        return
    try:
        import pygame
        font = _HITCH.get("font")
        if font is None:
            font = _HITCH["font"] = pygame.font.Font(None, 20)
        img = font.render(text, True, (210, 220, 235))
        surface.blit(img, (8, surface.get_height() - 22))
    except Exception:
        pass
