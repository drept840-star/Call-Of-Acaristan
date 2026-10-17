#!/usr/bin/env python3
"""ae_timeline_check - Phase 8 timeline gate: validate + data == legacy tables.

Every ``src/game/content/timelines/*.timeline.json`` must (a) pass the
``engine.timeline`` validator and (b) convert, via ``game.timelines.shots``,
into exactly the legacy in-code shot lists.  The M4 timed ladders
(``m4.story_beats`` / ``m4.arrest_beats`` event tracks) are validated here
too - their consumers compare against the same checker's sampling proof in
the unit tests.  Run by ae_ci.  Exit 0 only when the whole set checks out.

    python tools/ae_timeline_check.py [-v]
"""
from __future__ import annotations

import glob
import importlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TL_DIR = os.path.join(ROOT, "src", "game", "content", "timelines")


def _norm(v):
    if isinstance(v, tuple):
        return [_norm(x) for x in v]
    if isinstance(v, list):
        return [_norm(x) for x in v]
    if isinstance(v, dict):
        return {k: _norm(x) for k, x in v.items()}
    return v


def main() -> int:
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.pop("ACA_TL_SRC", None)                 # force data mode for the round-trip
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "src"))

    problems: list[str] = []
    paths = sorted(glob.glob(os.path.join(TL_DIR, "*.timeline.json")))
    if not paths:
        print("AE TIMELINE: FAIL (no .timeline.json files; run ae_timeline_export.py)")
        return 1

    from engine.timeline import validate
    seen_ids = set()
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        seen_ids.add(data.get("id"))
        for problem in validate(data):
            problems.append(f"{os.path.basename(path)}: {problem}")
        if verbose:
            print(f"  {data.get('id')}: valid ({len(data.get('shots', []))} shots, "
                  f"{len(data.get('tracks', {}))} tracks)")

    import ae_replay  # noqa: F401  (full boot, like the other checkers)
    import game.timelines as tl
    from ae_timeline_export import SPECS

    checked = 0
    for tid, mod_name, attr in SPECS:
        if tid not in seen_ids:
            problems.append(f"{tid}: no timeline file (run ae_timeline_export.py)")
            continue
        legacy = getattr(importlib.import_module(mod_name), attr)
        got = tl.shots(tid, legacy)
        checked += 1
        if _norm(got) != _norm([dict(s) for s in legacy]):
            problems.append(f"{tid}: converted shots differ from the legacy table")
        elif verbose:
            print(f"  {tid}: OK ({len(got)} shots == legacy table)")

    # The M4 ladders: every legacy beat must fire exactly once, at its frame.
    from engine.timeline import TimelinePlayer
    from missions.m4 import flow as m4_flow
    ladders = [
        ("m4.story_beats", [(f, m, ln, c, None, 440) for f, m, ln, c in m4_flow._M4_STORY_BEATS]),
        ("m4.arrest_beats", [(f, m, ln, c, sfx, 470) for f, m, c, sfx, ln in m4_flow._M4_ARREST_BEATS]),
    ]
    for tid, legacy in ladders:
        if tid not in seen_ids:
            problems.append(f"{tid}: no timeline file (run ae_timeline_export.py)")
            continue
        player = TimelinePlayer(tl.timeline(tid))
        for frame, mark, line, color, sfx, duration in legacy:
            fired = player.events_between(frame - 1, frame)
            if len(fired) != 1:
                problems.append(f"{tid}: {len(fired)} events at frame {frame}, expected 1 ({mark})")
                continue
            clip = fired[0]
            if (clip.get("name"), clip.get("text"), tuple(clip.get("color", ())),
                    clip.get("sfx"), clip.get("duration")) != (mark, line, tuple(color), sfx, duration):
                problems.append(f"{tid}: clip at frame {frame} differs from the legacy beat ({mark})")
        checked += 1
        if verbose:
            print(f"  {tid}: OK ({len(legacy)} event clips == legacy ladder)")

    if problems:
        print(f"AE TIMELINE: FAIL ({checked} round-trips, {len(paths)} files)")
        for p in problems:
            print("  - " + p)
        return 1
    print(f"AE TIMELINE: OK ({len(paths)} timelines valid, data == legacy tables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
