#!/usr/bin/env python3
"""ae_d6_gate.py - D6 gate: one 2D render path (RPE6 §2 D6, §6.6; Phase 6).

Two measurements, both ratcheted against ``docs/engine/evidence/phase6/d6_baseline.json``:

1. **Custom draws per mission (dynamic).** Each replay segment (m1..m5) is started at
   its checkpoint, simulated for one second with the replay input stream, then drawn
   twice through ``core.game_core.game_draw``; the render queue's stats give the number
   and names of ``CustomDraw`` items in the frame. Exit criterion: ``m5 == 0`` and the
   other missions together ``<= 5`` (each a documented ticket in BUGS.md).
2. **Direct screen draws per mission (static census).** Call sites of ``pygame.draw.*(``
   and ``.blit(`` under ``src/missions/<m>/``; declared procedural asset painters
   (``decor_paint.py``, ``tram_wreck.py``, ``inspect_art*.py``, ``water.py``) are listed
   separately and allowed (D6: "except inside declared procedural asset definitions").

Usage:  python tools/ae_d6_gate.py [-v] [--update] [--static-only]
Prints ``AE D6: OK (...)`` or ``AE D6: FAIL (...)``; exit 1 on FAIL.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "docs", "engine", "evidence", "phase6", "d6_baseline.json")
MISSIONS = ("m1", "m2", "m3", "m4", "m5")
PROCEDURAL_PAINTERS = {"decor_paint.py", "tram_wreck.py", "inspect_art.py", "inspect_art_street.py", "water.py",
                       "props_paint.py", "set_paint.py"}
_DRAW_RE = re.compile(r"pygame\.draw\.\w+\(|\.blit\(")


def static_census() -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for m in MISSIONS:
        d = os.path.join(ROOT, "src", "missions", m)
        total = painters = 0
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".py"):
                continue
            with open(os.path.join(d, fn), "r", encoding="utf-8", errors="replace") as fh:
                n = len(_DRAW_RE.findall(fh.read()))
            if fn in PROCEDURAL_PAINTERS:
                painters += n
            else:
                total += n
        out[m] = {"draw_sites": total, "painter_sites": painters}
    return out


def dynamic_custom_draws(verbose: bool = False) -> dict[str, dict]:
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "src"))
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import ae_replay as R  # noqa: E402  (boots pygame + core.config like the replay oracle)
    import game.render as _gr  # noqa: E402

    out: dict[str, dict] = {}
    for seg in MISSIONS:
        starter, _label = R.SEGMENTS[seg]
        frames = R.FPS
        R._clock["frame"] = 0
        R._engine_clock().set_wall_elapsed(R._elapsed_ms())
        R.random.seed(R.SEED)
        getattr(R.gc, starter)()
        R.random.seed(R.SEED)
        stream = R.make_stream(R.SEED + sum(map(ord, seg)), frames)
        cam = (0, 0)
        for f, (held, mpos, fire) in enumerate(R.expand(stream)):
            if f >= frames:
                break
            R._clock["frame"] = f
            R._engine_clock().set_wall_elapsed(R._elapsed_ms())
            R._mouse["pos"] = mpos
            R._mouse["buttons"] = (fire, False, False)
            R.STATE.dt = R.DT
            res = R.gc.game_update(R.Keys(held))
            if isinstance(res, (tuple, list)) and len(res) >= 2:
                cam = (res[0], res[1])
        for _ in range(2):
            R.gc.game_draw(cam[0], cam[1])
        st = _gr.last_stats()
        out[seg] = {"custom": st.custom, "names": list(st.custom_names), "draws": st.total_draws,
                    "per_layer": dict((k, v) for k, v in st.as_dict()["draws"].items() if v)}
        if verbose:
            print(f"  {seg}: custom={st.custom} {st.custom_names} draws/layer={out[seg]['per_layer']}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--update", action="store_true", help="write the current numbers as the new baseline")
    ap.add_argument("--strict", action="store_true", help="also fail when the D6 exit criterion is not met")
    ap.add_argument("--static-only", action="store_true")
    a = ap.parse_args(argv)

    census = static_census()
    dyn = {} if a.static_only else dynamic_custom_draws(a.verbose)
    current = {"schema": "ae.d6/1", "static": census,
               "custom": {m: dyn[m]["custom"] for m in dyn}, "custom_names": {m: dyn[m]["names"] for m in dyn}}

    base = None
    if os.path.exists(BASELINE):
        with open(BASELINE, "r", encoding="utf-8") as fh:
            base = json.load(fh)

    problems = []
    if base is not None:
        for m in MISSIONS:
            b = base.get("static", {}).get(m, {}).get("draw_sites")
            c = census[m]["draw_sites"]
            if b is not None and c > b:
                problems.append(f"{m} direct draw sites {c} > baseline {b}")
            if m in current["custom"]:
                bc = base.get("custom", {}).get(m)
                if bc is not None and current["custom"][m] > bc:
                    problems.append(f"{m} custom draws {current['custom'][m]} > baseline {bc}")
                # names ratchet: a custom draw that is not in the baseline is a new legacy painter
                bn = base.get("custom_names", {}).get(m)
                if bn is not None:
                    new_names = sorted(set(current["custom_names"][m]) - set(bn))
                    if new_names:
                        problems.append(f"{m} new custom draw names {new_names} (baseline {sorted(bn)})")

    if a.update or base is None:
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        with open(BASELINE, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(current, fh, indent=1, sort_keys=True)
            fh.write("\n")
        if a.verbose or base is None:
            print(f"  baseline written: {os.path.relpath(BASELINE, ROOT)}")

    m5c = current["custom"].get("m5")
    others = sum(v for m, v in current["custom"].items() if m != "m5")
    exit_met = (m5c == 0 and others <= 5) if current["custom"] else False
    static_s = " ".join(f"{m}={census[m]['draw_sites']}" for m in MISSIONS)
    custom_s = " ".join(f"{m}={current['custom'][m]}" for m in MISSIONS if m in current["custom"]) or "n/a"
    if a.strict and not exit_met:
        problems.append("D6 exit criterion not met (--strict)")
    status = "FAIL" if problems else "OK"
    tail = "exit criterion met" if exit_met else f"exit criterion not met (m5 custom={m5c}, others={others})"
    print(f"AE D6: {status} (custom draws: {custom_s}; direct draw sites: {static_s}; {tail})")
    for p in problems:
        print("  - " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
