"""RPE6 replay baseline + determinism check (master prompt §6.17, Phase 0 item 9, D8).

    python tools/ae_replay.py record [--set baseline_v1] [--only m3]   # write baselines
    python tools/ae_replay.py check  [--set baseline_v1] [--only m3]   # replay + compare

Snapshot version 2 (Phase 5): the hash also covers the declared components of every
enemy's entity in game.world ("~world" field), so data migrated off the legacy objects
stays under the oracle. baseline_v0 (version 1) is superseded: it hashed the ad hoc
``e.m5_*`` attributes that are now M5Guard components (proof of equivalence:
tools/ae_d4_replay_compat.py, docs/engine/evidence/phase5/m4_replay_compat.txt).

One segment per mission: load a checkpoint, then drive the *legacy* sim
(core.game_core.game_update) for SECONDS at a fixed 1/60 s dt with a scripted
input stream (WASD holds, aim, fire), snapshotting a state hash every second.
The input stream is generated once from a seed and stored *as data* in the
baseline file, so `check` replays the recorded stream, not the generator.
Human-played streams can be dropped in the same format (see
src/tools/input_recorder.py, dev flag ACA_RECORD_INPUT).

Determinism scaffolding (legacy code is not yet deterministic on its own -
BUGS.md B-001/B-002): random.seed(SEED) at segment start, pinned
pygame.time.get_ticks()/time.time() advancing with the fixed step, pinned
mouse. Output: tests/replay/<set>/<segment>.json. Prints AE REPLAY: OK/FAIL.

Caveat (harness, not sim): segments run sequentially in one process and the
snapshot hashes the whole STATE, including fields an earlier mission left
behind (e.g. m3_* while m4 runs). So `check --only m4` against a baseline that
was recorded in full order can never match; record and check with the same
segment list (B-011 note in BUGS.md).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ["ACA_FREEZE"] = "1"
# Sandbox saves/settings/profile (*_aetools.json); see B-010.
os.environ.setdefault("ACA_SAVE_SUFFIX", "_aetools")
ROOT = Path(__file__).resolve().parent.parent

# Hash-seed pin (BUGS B-011, withdrawn): the oracle re-executes itself with
# PYTHONHASHSEED=0 so record and check always share one str-hash order. This is
# belt and braces, not a known dependence: the full replay matches baseline_v0
# under seeds 0, 1, 7 and random (2026-10-14). The divergence first blamed on
# hashing was B-012 (cold vs warm radio cache). AE_NO_HASHSEED_PIN=1 runs unpinned.
if os.environ.get("PYTHONHASHSEED") != "0" and not os.environ.get("AE_NO_HASHSEED_PIN"):
    import subprocess as _sp
    sys.exit(_sp.call([sys.executable, *sys.argv], env=dict(os.environ, PYTHONHASHSEED="0")))
sys.path.insert(0, str(ROOT / "src"))

import pygame  # noqa: E402

FPS = 60
DT = 1.0 / FPS
SECONDS = 30
SEED = 4242
_clock = {"frame": 0}
_mouse = {"pos": (500, 350), "buttons": (False, False, False)}
# Both OS pins and the engine wall clock (engine.core.now_ms/now_s, B-001)
# derive from one elapsed-ms value per frame so migrated and legacy reads agree.
def _elapsed_ms():
    return _clock["frame"] * 1000 / FPS


pygame.time.get_ticks = lambda: 100_000 + int(_elapsed_ms())
time.time = lambda: 1_700_000_000.0 + _elapsed_ms() / 1000.0
pygame.mouse.get_pos = lambda: _mouse["pos"]
pygame.mouse.get_pressed = lambda num_buttons=3: _mouse["buttons"][:num_buttons] + (False,) * max(0, num_buttons - 3)

pygame.init()
from core import config as cfg  # noqa: E402,F401
from core import game_core as gc  # noqa: E402
from core.state import STATE  # noqa: E402

SEGMENTS = {
    "m1": ("start_mission", "M1 warehouse start"),
    "m2": ("start_mission2_checkpoint", "M2 checkpoint"),
    "m3": ("start_mission3_comms_checkpoint", "M3 comms checkpoint"),
    "m4": ("start_mission4_station_checkpoint", "M4 station checkpoint"),
    "m5": ("start_mission5_quarter_checkpoint", "M5 quarter checkpoint"),
}
KEYMAP = {"w": pygame.K_w, "a": pygame.K_a, "s": pygame.K_s, "d": pygame.K_d,
          "shift": pygame.K_LSHIFT, "r": pygame.K_r}


class Keys:
    """Stands in for pygame.key.get_pressed(): indexable by key code."""

    def __init__(self, held):
        self.held = {KEYMAP[k] for k in held}

    def __getitem__(self, code):
        return code in self.held

    def __len__(self):
        return 512


def make_stream(seed: int, frames: int) -> list:
    """Run-length input stream: [[n_frames, "wd", mx, my, fire], ...]."""
    rng = random.Random(seed)
    out, f = [], 0
    dirs = ["", "w", "a", "s", "d", "wa", "wd", "sa", "sd", "w", "d"]
    while f < frames:
        n = rng.randint(20, 90)
        out.append([n, rng.choice(dirs) + ("shift" if rng.random() < 0.1 else ""),
                    rng.randint(100, 900), rng.randint(80, 620), int(rng.random() < 0.25)])
        f += n
    return out


def expand(stream):
    for n, keys, mx, my, fire in stream:
        held = []
        k = keys.replace("shift", "")
        held += list(k)
        if "shift" in keys:
            held.append("shift")
        for _ in range(n):
            yield held, (mx, my), bool(fire)


# --------------------------------------------------------------- state hash
PRIMS = (int, float, str, bool, type(None))


def _canon(v, depth=0):
    if isinstance(v, float):
        return repr(round(v, 6))
    if isinstance(v, PRIMS):
        return repr(v)
    if isinstance(v, pygame.Rect):
        return "R%r" % (tuple(v),)
    if isinstance(v, (tuple, list)) and depth < 2:
        return "[" + ",".join(_canon(x, depth + 1) for x in v) + "]"
    if isinstance(v, dict) and depth < 2:
        return "{" + ",".join(f"{k!r}:{_canon(x, depth + 1)}" for k, x in sorted(v.items(), key=lambda kv: repr(kv[0]))) + "}"
    if hasattr(v, "__dict__") and depth < 2:
        return "<" + type(v).__name__ + ":" + ",".join(
            f"{k}={_canon(x, depth + 1)}" for k, x in sorted(vars(v).items())
            if not k.startswith("__") and isinstance(x, PRIMS + (pygame.Rect, tuple, list))) + ">"
    return type(v).__name__


def _world_canon() -> str:
    """Declared components of every live enemy's and door's entity (RPE6 Phase 5, snapshot version 2).

    Data that moves off the legacy objects into ``game.world`` components would otherwise
    silently leave the oracle. Enemies are walked in ``STATE.enemies`` order; components in
    type-name order; dataclass fields through ``_canon``. Read-only: entities not registered
    yet (spawned this frame, before the next PRE sync) contribute nothing.
    """
    import game.world as _gw  # lazy: booted by game_core at the first game_update
    if not _gw.installed():
        return ""
    w, roster = _gw.world(), _gw.roster()
    out = []
    objs = list(getattr(STATE, "enemies", []) or []) + list(getattr(STATE, "doors", []) or [])
    for e in objs:
        eid = roster.eid_for(e)
        if eid is None:
            continue
        dump = w.dump_entity(eid)   # {TypeName: {field: value}} - views and dataclasses alike
        parts = [f"{name}{{{','.join(f'{f}={_canon(v)}' for f, v in dump[name].items())}}}"
                 for name in sorted(dump)]
        out.append("<" + ",".join(parts) + ">")
    return "[" + ",".join(out) + "]"


def snapshot() -> dict:
    fields = {}
    for k, v in sorted(vars(STATE).items()):
        if k.startswith("_") or callable(v) or isinstance(v, pygame.Surface):
            continue
        fields[k] = _canon(v)
    fields["~world"] = _world_canon()   # sorts after every STATE field; "" before Phase 5
    pl = getattr(STATE, "player", None)
    core = {
        "player_rect": list(pl.rect) if pl is not None and hasattr(pl, "rect") else None,
        "player_hp": next((getattr(pl, a) for a in ("health", "hp") if hasattr(pl, a)), None) if pl else None,
        "enemies": len(getattr(STATE, "enemies", []) or []),
    }
    h = hashlib.sha256("\n".join(f"{k}={v}" for k, v in fields.items()).encode()).hexdigest()[:16]
    return {"hash": h, **core, "_fields": fields}


def _engine_clock():
    from core import config as _cfg  # booted App (adapter A-001)
    return _cfg._engine_app.clock


def run_segment(seg: str, stream=None):
    starter, label = SEGMENTS[seg]
    frames = SECONDS * FPS
    _clock["frame"] = 0
    _engine_clock().set_wall_elapsed(_elapsed_ms())   # starters stamp "now" too
    random.seed(SEED)
    getattr(gc, starter)()
    random.seed(SEED)
    stream = stream or make_stream(SEED + sum(map(ord, seg)), frames)
    snaps = []
    for f, (held, mpos, fire) in enumerate(expand(stream)):
        if f >= frames:
            break
        _clock["frame"] = f
        _engine_clock().set_wall_elapsed(_elapsed_ms())
        _mouse["pos"] = mpos
        _mouse["buttons"] = (fire, False, False)
        STATE.dt = DT
        gc.game_update(Keys(held))
        if (f + 1) % FPS == 0:
            s = snapshot()
            s["t_s"] = (f + 1) // FPS
            snaps.append(s)
    return {"schema": "ae.replay.segment", "version": 2, "segment": seg, "label": label,
            "checkpoint": f"core.game_core.{starter}", "seed": SEED, "fps": FPS, "seconds": SECONDS,
            "input_stream": stream, "snapshots": snaps}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("record", "check"))
    ap.add_argument("--set", default="baseline_v1")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    d = ROOT / "tests" / "replay" / a.set
    d.mkdir(parents=True, exist_ok=True)
    segs = [s for s in SEGMENTS if not a.only or s in a.only.split(",")]
    ok, rows = True, []
    for seg in segs:
        path = d / f"{seg}.json"
        t0 = time.perf_counter()
        try:
            if a.mode == "record":
                res = run_segment(seg)
                slim = {**res, "snapshots": [{k: v for k, v in s.items() if k != "_fields"} for s in res["snapshots"]]}
                path.write_text(json.dumps(slim, indent=1) + "\n", encoding="utf-8", newline="\n")
                (d / f"{seg}.fields.json").write_text(json.dumps(res["snapshots"][-1]["_fields"], indent=1, sort_keys=True)
                                                      + "\n", encoding="utf-8", newline="\n")
                last = res["snapshots"][-1]
                rows.append(f"{seg}: recorded {len(res['snapshots'])} snapshots, final hash {last['hash']} "
                            f"player {last['player_rect']} hp {last['player_hp']} enemies {last['enemies']}")
            else:
                base = json.loads(path.read_text(encoding="utf-8"))
                res = run_segment(seg, base["input_stream"])
                bad = [(b["t_s"], b["hash"], r["hash"]) for b, r in zip(base["snapshots"], res["snapshots"])
                       if b["hash"] != r["hash"]]
                if len(base["snapshots"]) != len(res["snapshots"]):
                    bad.append(("count", len(base["snapshots"]), len(res["snapshots"])))
                if bad:
                    ok = False
                    first = bad[0]
                    rows.append(f"{seg}: FAIL first divergence at t={first[0]}s ({first[1]} != {first[2]}); "
                                f"{len(bad)} of {len(base['snapshots'])} snapshots differ")
                    diverged = res["snapshots"][[s["t_s"] for s in res["snapshots"]].index(first[0])] \
                        if isinstance(first[0], int) else None
                    fp = d / f"{seg}.fields.json"
                    if diverged and fp.exists() and first[0] == base["snapshots"][-1]["t_s"]:
                        bf = json.loads(fp.read_text(encoding="utf-8"))
                        diff = [k for k in sorted(set(bf) | set(diverged["_fields"]))
                                if bf.get(k) != diverged["_fields"].get(k)]
                        rows.append(f"    differing STATE fields at final snapshot: {diff[:20]}")
                else:
                    rows.append(f"{seg}: OK {len(base['snapshots'])} snapshots match (final {base['snapshots'][-1]['hash']})")
        except Exception as e:  # noqa: BLE001
            ok = False
            rows.append(f"{seg}: ERROR {e!r}\n{traceback.format_exc(limit=5)}")
        rows[-1] += f"  [{time.perf_counter() - t0:.1f}s]"
    print("\n".join(rows))
    print("AE REPLAY: OK" if ok else "AE REPLAY: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
