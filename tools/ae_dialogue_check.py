#!/usr/bin/env python3
"""ae_dialogue_check - Phase 7 dialogue gate: validate + data == legacy tables.

Every ``src/game/content/dialogue/*.dlg.json`` must (a) pass the
``engine.dialogue`` validator and (b) convert, via ``game.dialogues.beats``,
into exactly the legacy in-code beat tables (colours resolved game-side).
Run by ae_ci.  Exit 0 only when the whole set checks out.

    python tools/ae_dialogue_check.py [-v]
"""
from __future__ import annotations

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DLG_DIR = os.path.join(ROOT, "src", "game", "content", "dialogue")


def main() -> int:
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.pop("ACA_DLG_SRC", None)               # force data mode for the round-trip
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "src"))

    problems: list[str] = []
    paths = sorted(glob.glob(os.path.join(DLG_DIR, "*.dlg.json")))
    if not paths:
        print("AE DIALOGUE: FAIL (no .dlg.json files; run ae_dialogue_export.py)")
        return 1

    from engine.dialogue import validate
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for problem in validate(data):
            problems.append(f"{os.path.basename(path)}: {problem}")
        if verbose:
            print(f"  {data.get('id')}: valid ({len(data.get('nodes', {}))} nodes)")

    import ae_replay  # noqa: F401  (full boot, like the level checker)
    import game.dialogues as dlg
    from missions.m4 import flow as m4_flow
    from missions.m5 import flow as m5_flow

    cases = [
        ("m5.maru", m5_flow._M5_MARU_BEATS,
         {"MARU": m5_flow.C_MARU, "BIRIBEL": m5_flow.BIRIBEL_SPEAKER, "SYSTEM": m5_flow.C_GUARD}, False),
        ("m4.liaison", m4_flow._M4_LIAISON_BEATS,
         {"MARU": m4_flow.C_MARU, "BIRIBEL": m4_flow.BIRIBEL_SPEAKER}, True),
    ]
    checked = 0
    for dlg_id, legacy, colors, typed in cases:
        got = dlg.beats(dlg_id, legacy, colors, typed=typed)
        want = [{k: v for k, v in beat.items()} for beat in legacy]
        # legacy choice options are tuples; the converter yields tuples too,
        # so a straight comparison is meaningful once colours are resolved.
        checked += 1
        if got != want:
            problems.append(f"{dlg_id}: converted beats differ from the legacy table")
            if verbose:
                for i, (g, w) in enumerate(zip(got, want)):
                    if g != w:
                        print(f"    beat {i}: data={g!r} legacy={w!r}")
                        break
                print(f"    ({len(got)} vs {len(want)} beats)")
        elif verbose:
            print(f"  {dlg_id}: OK ({len(got)} beats == legacy table)")

    if problems:
        print(f"AE DIALOGUE: FAIL ({checked} round-trips, {len(paths)} files)")
        for p in problems:
            print("  - " + p)
        return 1
    print(f"AE DIALOGUE: OK ({len(paths)} dialogues valid, data == legacy tables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
