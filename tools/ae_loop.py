"""RPE6 loop probe: drive the REAL app.py main loop headless and hash every frame.

Oracle for refactoring the legacy main loop (LegacyGameScene, Phase 1). Golden
and replay call into states/missions directly and never run app.py's
``while running:`` loop; this tool does.

    python tools/ae_loop.py record [--seg NAME ...] [--frames N]
    python tools/ae_loop.py check  [--seg NAME ...] [--png]
    python tools/ae_loop.py list

Each segment runs in its own subprocess (app.py runs the game on import):
  * sys.argv gets the dev jump flag (core.dev_jumps), CWD = repo root
  * SDL dummy video/audio, software 3D renderer, random/numpy seeded
  * pygame.time.Clock is replaced: tick() returns 16 ms; game time
    (get_ticks / time.time) advances 16 ms per display.flip()
  * the OS event queue is drained and replaced by a scripted stream;
    key.get_pressed / mouse are scripted; QUIT is injected after N frames
  * saves/settings/profile go to *_aeloop.json (ACA_SAVE_SUFFIX), which are
    deleted before and after, so the owner's saves are never touched
  * PYTHONHASHSEED=0 (set iteration order); perf_counter/monotonic pinned too
  * random.seed() with no argument (entropy reseed, B-008) becomes a
    deterministic reseed (SEED + n)
  * pygame.mixer replaced by a game-time fake (Channel.get_busy follows the
    sound length on the fake clock, not the SDL audio thread); silent
  * every flip: sha1 of the display surface + gsm.current_name
Baselines: tests/loop/baseline_v5/<seg>.json (the previous set is kept for diffs; older ones are
removed by tools/slim_tree.py - their reasons stay in the notes below). No game file
is modified by this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time as _time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# v0 = pre-B-008-fix (global RNG reseeded at m2.draw import; probe-neutralised).
# v1 = after the B-008 fix (src/missions/m2/draw.py private generator).
# baseline_v2 (2026-10-14): grain textures moved to the named "grain" rng stream
# (B-002), so every frame's grain pixels and the probe's seed alignment changed.
# baseline_v3 (2026-10-14, asset diet): menu background re-saved as a real
# 1000x700 JPEG (boot frames 120+) and voice lines converted to OGG Vorbis.
# Subtitle timing is unchanged (voice._clip_ms reproduces the WAV-era length
# from the file header); the only remaining trace is the radio LED ladder,
# which follows Channel.get_busy() and goes dark one frame earlier when SDL's
# decoded Vorbis clip ends 12-33 ms early (m3 frame 151). Older sets kept.
# baseline_v4 (2026-10-14, Phase 3 baked world layers): m3 + m4 re-recorded.
#   m3: the corridor cell-door LEDs and the maintenance cabinet blink were authored
#       as per-frame animations but the chunk cache froze them at bake time; they are
#       now drawn live (_draw_m3_static_live) -> first pixel diff at frame 282 (LEDs
#       scroll into view). Proof: pinning their clock at T0_MS reproduces v3 exactly.
#   m4: B-017 (hash-salted facade RNG -> _stable_seed); see docs/engine/evidence/m4_stable_seed/.
#   boot/m1/walk/m2/m5 are byte-identical to v3.
# baseline_v5 (2026-10-15, reference-machine reconciliation): v4 was recorded in the
#   Linux sandbox from the pre-merge snapshot; the merged tree carries the owner's
#   newer work, so boot/m1/m2/m3/m5 diverge (first pixel diffs at frames 120, 295, 5,
#   0, 1; scene states match throughout and the rng streams match until 588 / 356 /
#   356), while walk/m4 are byte-identical to v4. Re-recorded on the reference
#   machine; the .venv (py 3.14, pygame-ce 2.5.7, SDL 2.32.10) and the system python
#   (py 3.13, pygame-ce 2.5.5, SDL 2.32.6) produce identical hashes, i.e. content
#   drift, not machine drift. v4 kept for history.
BASE = ROOT / "tests" / "loop" / os.environ.get("ACA_LOOP_SET", "baseline_v5")  # sandbox sets via env
BUILD = ROOT / "build" / "ae_loop"
SEED = 1337
FRAME_MS = 16
T0_MS = 100_000
SUFFIX = "_aeloop"
DEFAULT_FRAMES = 600

# Scripted input as data: (start_frame, end_frame, kind, arg)
#   key   : hold pygame key constant name in [start, end) with KEYDOWN/KEYUP
#   click : left button down at start, up at end, at the mouse position
#   mouse : move mouse to (x, y) at start
_MOVE = [
    (0, 0, "mouse", (620, 330)),
    (30, 90, "key", "K_w"),
    (90, 150, "key", "K_d"),
    (150, 158, "click", None),
    (170, 230, "key", "K_a"),
    (200, 204, "click", None),
    (240, 300, "key", "K_s"),
    (300, 330, "mouse", (380, 420)),
    (310, 318, "click", None),
    (330, 420, "key", "K_w"),
    (360, 420, "key", "K_d"),
    (430, 436, "key", "K_r"),
    (450, 540, "key", "K_a"),
    (470, 478, "click", None),
    (520, 526, "key", "K_e"),
    (550, 600, "key", "K_s"),
]
SEGMENTS = {
    "boot": {"args": [], "frames": 420,
             "script": [(0, 0, "mouse", (500, 350)), (120, 124, "key", "K_RETURN"),
                        (150, 154, "key", "K_ESCAPE"), (200, 204, "key", "K_DOWN"),
                        (240, 244, "key", "K_UP"), (300, 304, "key", "K_DOWN"),
                        (330, 334, "key", "K_DOWN"), (360, 364, "key", "K_UP")]},
    "m1":   {"args": ["--dev-m1"], "script": _MOVE},
    "walk": {"args": ["--dev-walk"], "script": _MOVE},
    "m2":   {"args": ["--dev-mission2-game"], "script": _MOVE},
    "m3":   {"args": ["--dev-mission3-game"], "script": _MOVE},
    "m4":   {"args": ["--dev-mission4-game"], "script": _MOVE},
    "m5":   {"args": ["--dev-mission5-game"], "script": _MOVE},
}


def _save_files():
    return [ROOT / f"{n}{SUFFIX}.json" for n in ("save_data", "settings", "profile")]


def _clean_saves():
    for p in _save_files():
        try:
            p.unlink()
        except FileNotFoundError:
            pass


# --------------------------------------------------------------------- child
def _child(seg: str, frames: int, out: str, png_dir: str | None) -> None:
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    os.environ["ACARISTAN_RENDERER"] = "software"
    os.environ["ACA_SAVE_SUFFIX"] = SUFFIX
    os.environ.pop("ACA_FREEZE", None)
    os.environ.pop("ACA_RECORD_INPUT", None)
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / "src"))
    spec = SEGMENTS[seg]
    sys.argv = ["acaristan.py"] + list(spec["args"])

    import random
    import threading  # noqa: F401  bind real monotonic for thread timeouts first
    import queue      # noqa: F401
    import time
    import pygame
    random.seed(SEED)
    # B-008 workaround: legacy code calls the GLOBAL random.seed() with no
    # argument (m2/draw.py "unseed"), which reseeds from OS entropy. Make a
    # no-arg reseed deterministic so the probe measures code, not entropy.
    _orig_seed = random.seed
    _reseeds = [0]

    def _seed(a=None, *args, **kw):
        if a is None:
            _reseeds[0] += 1
            return _orig_seed(SEED + _reseeds[0], *args, **kw)
        return _orig_seed(a, *args, **kw)
    random.seed = _seed
    # Optional RNG call trace (determinism forensics, B-011): with
    # AE_LOOP_RNG_TRACE=<path> every call on the global Random during the
    # first AE_LOOP_RNG_TRACE_FRAMES frames (default 2) is logged as
    # "method caller args" so two runs can be diffed to the first divergence.
    _trace_path = os.environ.get("AE_LOOP_RNG_TRACE")
    _trace, _trace_frames = [], int(os.environ.get("AE_LOOP_RNG_TRACE_FRAMES", "2"))
    if _trace_path:
        import inspect as _inspect
        _inst = random._inst  # type: ignore[attr-defined]

        def _wrap(meth):
            def w(*a, **k):
                if len(_trace) < 3_000_000:
                    f = _inspect.currentframe().f_back
                    _trace.append(f"{meth.__name__} {f.f_code.co_filename.rsplit('/', 1)[-1]}:{f.f_lineno} "
                                  f"{repr(a)[:200]}")
                return meth(*a, **k)
            return w
        for _n in ("random", "randint", "randrange", "uniform", "choice", "choices", "shuffle",
                   "gauss", "triangular", "sample", "getrandbits", "expovariate", "betavariate",
                   "normalvariate", "lognormvariate", "vonmisesvariate", "paretovariate",
                   "weibullvariate", "randbytes", "binomialvariate", "setstate"):
            if hasattr(_inst, _n):
                setattr(_inst, _n, _wrap(getattr(_inst, _n)))
                setattr(random, _n, getattr(_inst, _n))
        _traced_seed = _wrap(_seed)
        random.seed = _traced_seed
        _inst.seed = _wrap(_orig_seed)
    try:
        import numpy as _np
        _np.random.seed(SEED)
    except Exception:
        pass

    st = {"t": T0_MS, "frame": 0, "delivered": -1, "mouse": (500, 350), "done": False}

    trace_path = os.environ.get("AE_LOOP_TRACE")
    if trace_path:   # diagnostic: log the call site of every global-random call
        _tf = open(trace_path, "w", encoding="utf-8")
        _tfrom = int(os.environ.get("AE_LOOP_TRACE_FROM", "0"))   # stack-trace calls >= N
        _tc = [0]

        def _site(f):
            return f"{os.path.relpath(f.f_code.co_filename, ROOT)}:{f.f_lineno}"

        def _wrap(name, fn):
            def w(*a, **k):
                f = sys._getframe(1)
                line = f"{st['frame']} {threading.current_thread().name} {_site(f)} {name}"
                if _tfrom and _tc[0] >= _tfrom:
                    chain, g = [], f.f_back
                    while g is not None and len(chain) < 7:
                        chain.append(_site(g))
                        g = g.f_back
                    line += "  <- " + " <- ".join(chain)
                _tc[0] += 1
                _tf.write(line + "\n")
                return fn(*a, **k)
            return w
        _funcs = set(filter(None, os.environ.get("AE_LOOP_TRACE_FUNCS", "").split(",")))
        if _funcs:   # log entry of named Python functions + a checksum of their args
            def _prof(frame, event, arg):
                if event == "call" and frame.f_code.co_name in _funcs:
                    loc = frame.f_locals
                    ck = hashlib.sha1(repr(sorted((k, repr(v)[:4000]) for k, v in loc.items()
                                                  if k not in ("surface", "screen"))
                                           ).encode()).hexdigest()[:10]
                    chain, g = [], frame.f_back
                    while g is not None and len(chain) < 5:
                        chain.append(_site(g))
                        g = g.f_back
                    _tf.write(f"{st['frame']} CALL {frame.f_code.co_name} args={ck}  <- "
                              + " <- ".join(chain) + "\n")
            sys.setprofile(_prof)
        for _n in ("random", "randint", "uniform", "choice", "choices", "shuffle",
                   "sample", "randrange", "gauss", "normalvariate", "triangular",
                   "getrandbits"):
            setattr(random, _n, _wrap(_n, getattr(random, _n)))
            # game code calls the same instance as engine.core.LEGACY_RNG
            setattr(random._inst, _n, getattr(random, _n))
    hashes: list[str] = []
    rngs: list[str] = []         # global random state fingerprint per frame (diagnostic)
    states: list[list] = []      # run-length [name, first_frame, count]

    # -- time ---------------------------------------------------------------
    pygame.time.get_ticks = lambda: st["t"]
    time.time = lambda: 1.7e9 + st["t"] / 1000.0
    time.perf_counter = lambda: st["t"] / 1000.0
    time.monotonic = lambda: st["t"] / 1000.0
    time.perf_counter_ns = lambda: st["t"] * 1_000_000
    time.monotonic_ns = lambda: st["t"] * 1_000_000
    time.time_ns = lambda: int((1.7e9 + st["t"] / 1000.0) * 1e9)

    class _FakeClock:
        def __init__(self, *a, **k):
            pass

        def tick(self, *a, **k):
            return FRAME_MS
        tick_busy_loop = tick

        def get_time(self):
            return FRAME_MS
        get_rawtime = get_time

        def get_fps(self):
            return 1000.0 / FRAME_MS
    pygame.time.Clock = _FakeClock

    # -- input --------------------------------------------------------------
    K = {name: getattr(pygame, name) for (_, _, kind, name) in spec["script"]
         if kind == "key"}

    def _held(frame):
        keys, btn = set(), False
        for s, e, kind, arg in spec["script"]:
            if s <= frame < e:
                if kind == "key":
                    keys.add(K[arg])
                elif kind == "click":
                    btn = True
        return keys, btn

    class _Pressed:
        def __init__(self, keys):
            self._k = keys

        def __getitem__(self, i):
            return i in self._k

        def __len__(self):
            return 512

        def __iter__(self):
            return (i in self._k for i in range(512))

    _orig_get = pygame.event.get

    def _events_for(frame):
        evs = []
        for s, e, kind, arg in spec["script"]:
            if kind == "mouse" and frame == s:
                st["mouse"] = tuple(arg)
                evs.append(pygame.event.Event(pygame.MOUSEMOTION, pos=st["mouse"],
                                              rel=(0, 0), buttons=(0, 0, 0)))
            elif kind == "key":
                if frame == s:
                    evs.append(pygame.event.Event(pygame.KEYDOWN, key=K[arg], mod=0,
                                                  unicode="", scancode=0))
                if frame == e:
                    evs.append(pygame.event.Event(pygame.KEYUP, key=K[arg], mod=0,
                                                  unicode="", scancode=0))
            elif kind == "click":
                if frame == s:
                    evs.append(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                                  pos=st["mouse"]))
                if frame == e:
                    evs.append(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1,
                                                  pos=st["mouse"]))
        return evs

    def _get(*a, **k):
        try:
            _orig_get()          # drain + discard real OS events (nondeterministic)
        except Exception:
            pass
        f = st["frame"]
        if st["done"]:
            return [pygame.event.Event(pygame.QUIT)]
        if st["delivered"] == f:
            return []
        st["delivered"] = f
        return _events_for(f)
    pygame.event.get = _get
    pygame.event.poll = lambda: pygame.event.Event(pygame.NOEVENT)
    pygame.key.get_pressed = lambda: _Pressed(_held(st["frame"])[0])
    pygame.key.get_mods = lambda: 0
    pygame.mouse.get_pos = lambda: st["mouse"]
    pygame.mouse.get_pressed = lambda *a, **k: (_held(st["frame"])[1], False, False)
    pygame.mouse.get_rel = lambda: (0, 0)
    pygame.mouse.set_pos = lambda *a, **k: None

    # -- audio: deterministic fake mixer (game-time playback) ----------------
    # Channel.get_busy() on the real mixer follows the SDL audio thread in wall
    # time, and the radio VU meter / VO sequencing read it. Here a channel is
    # busy for exactly the sound's length in *game* time. Nothing is audible.
    INF = float("inf")

    class _FakeChannel:
        _by_id: dict = {}

        def __new__(cls, idx=None):
            if idx is not None and idx in cls._by_id:
                return cls._by_id[idx]
            o = super().__new__(cls)
            o._idx, o._snd, o._end, o._vol, o._paused = idx, None, 0.0, 1.0, None
            if idx is not None:
                cls._by_id[idx] = o
            return o

        def __init__(self, idx=None):
            pass

        def play(self, sound, loops=0, maxtime=0, fade_ms=0):
            length = max(1.0, sound.get_length() * 1000.0)
            dur = INF if loops < 0 else length * (loops + 1)
            if maxtime:
                dur = min(dur, maxtime)
            self._snd, self._end, self._paused = sound, st["t"] + dur, None
            return self

        def get_busy(self):
            return self._snd is not None and (self._paused is not None or st["t"] < self._end)

        def stop(self):
            self._snd, self._end, self._paused = None, 0.0, None

        def fadeout(self, ms):
            if self.get_busy():
                self._end = min(self._end, st["t"] + ms)

        def pause(self):
            if self.get_busy() and self._paused is None:
                self._paused = self._end - st["t"]

        def unpause(self):
            if self._paused is not None:
                self._end, self._paused = st["t"] + self._paused, None

        def queue(self, sound):
            if not self.get_busy():
                self.play(sound)

        def get_sound(self):
            return self._snd if self.get_busy() else None

        def get_queue(self):
            return None

        def set_volume(self, *a):
            self._vol = a[0] if a else self._vol

        def get_volume(self):
            return self._vol

        @property
        def id(self):
            return self._idx

        def __getattr__(self, name):      # set_endevent, set_source_location, ...
            return lambda *a, **k: None

    _nch = [8]

    def _free_channel(force=False):
        for i in range(_nch[0]):
            ch = _FakeChannel(i)
            if not ch.get_busy():
                return ch
        return _FakeChannel(0) if force else None

    _RealSound = pygame.mixer.Sound

    class _Sound(_RealSound):
        def play(self, loops=0, maxtime=0, fade_ms=0):
            ch = _free_channel(force=True)
            return ch.play(self, loops, maxtime, fade_ms)

        def stop(self):
            for ch in list(_FakeChannel._by_id.values()):
                if ch._snd is self:
                    ch.stop()

        def fadeout(self, ms):
            for ch in list(_FakeChannel._by_id.values()):
                if ch._snd is self:
                    ch.fadeout(ms)

        def get_num_channels(self):
            return sum(1 for ch in _FakeChannel._by_id.values()
                       if ch._snd is self and ch.get_busy())

    def _all(fn):
        def w(*a, **k):
            for ch in list(_FakeChannel._by_id.values()):
                getattr(ch, fn)(*a, **k)
        return w

    def _set_num_channels(n):
        _nch[0] = int(n)

    mx = pygame.mixer
    mx.Sound, mx.Channel = _Sound, _FakeChannel
    mx.find_channel = _free_channel
    mx.get_busy = lambda: any(ch.get_busy() for ch in _FakeChannel._by_id.values())
    mx.set_num_channels, mx.get_num_channels = _set_num_channels, lambda: _nch[0]
    mx.set_reserved = lambda *a, **k: 0
    mx.stop, mx.pause, mx.unpause, mx.fadeout = _all("stop"), _all("pause"), _all("unpause"), _all("fadeout")
    _music = {"on": False, "t0": 0}

    def _m_play(*a, **k):
        _music.update(on=True, t0=st["t"])
    mx.music.play = _m_play
    mx.music.stop = lambda *a, **k: _music.update(on=False)
    mx.music.fadeout = lambda *a, **k: _music.update(on=False)
    mx.music.get_busy = lambda: _music["on"]
    mx.music.get_pos = lambda: (st["t"] - _music["t0"]) if _music["on"] else -1
    mx.music.pause = mx.music.unpause = mx.music.rewind = lambda *a, **k: None
    mx.music.load = mx.music.queue = lambda *a, **k: None

    # -- frame hook ---------------------------------------------------------
    _orig_flip = pygame.display.flip

    def _scene_trace():
        # RPE6 Phase 2: the engine SceneStack mirroring the FSM (app._LegacyGameScene.stack)
        try:
            cfg = sys.modules.get("core.config")
            services = cfg._engine_app.services
            if services.has("scene"):
                return list(getattr(services.get("scene"), "stack").trace)
        except Exception:
            pass
        return None

    def _dump():
        Path(out).write_text(json.dumps({
            "seg": seg, "args": spec["args"], "frames": len(hashes), "seed": SEED,
            "frame_ms": FRAME_MS, "hashes": hashes, "states": states, "rng": rngs,
            "hashseed": os.environ.get("PYTHONHASHSEED"), "hash_probe": hash("station"),
            "entropy_reseeds": _reseeds[0], "scene_trace": _scene_trace(),
        }, indent=0), encoding="utf-8")

    def _flip(*a, **k):
        r = _orig_flip(*a, **k)
        if st["done"]:
            if st["frame"] > frames + 30:
                raise SystemExit(3)   # loop ignored the injected QUIT
            st["frame"] += 1
            return r
        surf = pygame.display.get_surface()
        h = hashlib.sha1(pygame.image.tobytes(surf, "RGB")).hexdigest()[:16]
        hashes.append(h)
        rngs.append(hashlib.sha1(repr(random.getstate()).encode()).hexdigest()[:12])
        app_mod = sys.modules.get("app")
        name = getattr(getattr(app_mod, "gsm", None), "current_name", None)
        if states and states[-1][0] == name:
            states[-1][2] += 1
        else:
            states.append([name, st["frame"], 1])
        if png_dir:
            pygame.image.save(surf, os.path.join(png_dir, f"f{st['frame']:04d}.png"))
        st["frame"] += 1
        st["t"] += FRAME_MS
        if _trace_path and st["frame"] == _trace_frames:
            Path(_trace_path).write_text("\n".join(_trace) + "\n", encoding="utf-8")
        if st["frame"] >= frames:
            st["done"] = True
            _dump()
        return r
    pygame.display.flip = _flip

    try:
        import app  # noqa: F401  (runs the game loop)
    except SystemExit:
        pass
    if not st["done"]:
        _dump()
        print(f"loop ended early at frame {st['frame']}", file=sys.stderr)
        sys.exit(4)


# -------------------------------------------------------------------- parent
def _run_segments(segs, frames_override, png):
    BUILD.mkdir(parents=True, exist_ok=True)
    _clean_saves()
    procs = {}
    try:
        for seg in segs:
            frames = frames_override or SEGMENTS[seg].get("frames", DEFAULT_FRAMES)
            out = BUILD / f"{seg}.json"
            if out.exists():
                out.unlink()
            log = open(BUILD / f"{seg}.log", "w", encoding="utf-8")
            cmd = [sys.executable, str(Path(__file__).resolve()), "_child", seg,
                   str(frames), str(out)]
            if png:
                d = BUILD / f"{seg}_png"
                d.mkdir(exist_ok=True)
                cmd.append(str(d))
            env = dict(os.environ, PYTHONHASHSEED="0")
            procs[seg] = (subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                           env=env),
                          log, out)
        results = {}
        for seg, (p, log, out) in procs.items():
            rc = p.wait(timeout=900)
            log.close()
            data = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
            results[seg] = (rc, data)
        return results
    finally:
        _clean_saves()


def _states_str(states):
    return " > ".join(f"{n}@{f}" for n, f, _ in states)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "_child":
        _child(argv[1], int(argv[2]), argv[3], argv[4] if len(argv) > 4 else None)
        return 0
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["record", "check", "list"])
    ap.add_argument("--seg", nargs="*", default=None)
    ap.add_argument("--frames", type=int, default=None)
    ap.add_argument("--png", action="store_true", help="dump every frame to build/ae_loop")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        for n, s in SEGMENTS.items():
            print(f"{n:6} {' '.join(s['args']) or '(boot)':28} {s.get('frames', DEFAULT_FRAMES)} frames")
        return 0
    segs = a.seg or list(SEGMENTS)
    t0 = _time.time()
    results = _run_segments(segs, a.frames, a.png)
    bad = 0
    for seg in segs:
        rc, data = results[seg]
        if data is None or rc not in (0, None):
            print(f"  {seg:6} ERROR rc={rc} (see build/ae_loop/{seg}.log)")
            bad += 1
            continue
        if a.cmd == "record":
            BASE.mkdir(parents=True, exist_ok=True)
            (BASE / f"{seg}.json").write_text(json.dumps(data, indent=0), encoding="utf-8",
                                              newline="\n")
            uniq = len(set(data["hashes"]))
            print(f"  {seg:6} recorded {data['frames']} frames ({uniq} distinct)  "
                  f"{_states_str(data['states'])}")
        else:
            bp = BASE / f"{seg}.json"
            if not bp.exists():
                print(f"  {seg:6} NO BASELINE")
                bad += 1
                continue
            base = json.loads(bp.read_text(encoding="utf-8"))
            # scene_trace (Phase 2) is compared only once the baseline carries it
            trace_ok = base.get("scene_trace") is None or base["scene_trace"] == data.get("scene_trace")
            if base["hashes"] == data["hashes"] and base["states"] == data["states"] and trace_ok:
                print(f"  {seg:6} OK {data['frames']} frames match")
            elif base["hashes"] == data["hashes"] and base["states"] == data["states"]:
                print(f"  {seg:6} DIFF scene trace: base {base['scene_trace']} | now {data.get('scene_trace')}")
                bad += 1
            else:
                n = min(len(base["hashes"]), len(data["hashes"]))
                first = next((i for i in range(n) if base["hashes"][i] != data["hashes"][i]), n)
                br, dr = base.get("rng") or [], data.get("rng") or []
                m = min(len(br), len(dr))
                rfirst = next((i for i in range(m) if br[i] != dr[i]), None)
                print(f"         rng state first differs at frame {rfirst}")
                print(f"  {seg:6} DIFF first frame {first} of {len(base['hashes'])}; "
                      f"states base: {_states_str(base['states'])} | now: {_states_str(data['states'])}")
                bad += 1
    verdict = "OK" if not bad else "FAIL"
    print(f"AE LOOP: {verdict} ({len(segs) - bad}/{len(segs)} segments, {_time.time() - t0:.0f}s)")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
