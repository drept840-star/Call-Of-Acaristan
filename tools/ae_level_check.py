#!/usr/bin/env python3
"""ae_level_check.py - validator: level JSON == legacy generator output (RPE6 P7).

For every exported level: (1) the file parses and validates against the
``ae.level/1`` schema (engine.level), and (2) its floor grid equals, row for row,
the grid the legacy generator/builder produces when the mission is imported
under ``ACA_LEVEL_SRC=legacy``. This is what lets the data be the default while
the generators stay as a fallback that can never silently diverge.

Usage: python tools/ae_level_check.py [-v]
Prints ``AE LEVEL: OK (N levels)`` or ``AE LEVEL: FAIL``; exit 1 on FAIL.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    os.environ["ACA_LEVEL_SRC"] = "legacy"          # read the generators, not the data
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import ae_replay  # noqa: F401
    import importlib
    from engine.level import load_level
    from ae_level_export import OUT_DIR, SPECS

    problems: list[str] = []
    checked = 0
    for level_id, mod_name, attr, _name in SPECS:
        path = os.path.join(OUT_DIR, level_id + ".level.json")
        if not os.path.exists(path):
            problems.append(f"{level_id}: missing {os.path.relpath(path, ROOT)} (run ae_level_export.py)")
            continue
        try:
            lvl = load_level(path)
        except Exception as e:                        # noqa: BLE001 - report, don't crash
            problems.append(f"{level_id}: {e}")
            continue
        mod = importlib.import_module(mod_name)
        legacy = [(r if isinstance(r, str) else "".join(r)) for r in getattr(mod, attr)]
        data = lvl.grid("floor")
        checked += 1
        if data != legacy:
            diff = next((i for i, (a, b) in enumerate(zip(data, legacy)) if a != b), min(len(data), len(legacy)))
            problems.append(f"{level_id}: grid differs from the legacy generator at row {diff} "
                            f"({len(data)} vs {len(legacy)} rows)")
        elif verbose:
            print(f"  {level_id}: OK ({len(data)} rows, {len(lvl.objects)} objects)")
    if problems:
        print(f"AE LEVEL: FAIL ({checked} checked)")
        for p in problems:
            print("  - " + p)
        return 1
    print(f"AE LEVEL: OK ({checked} levels, data == legacy generators)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
