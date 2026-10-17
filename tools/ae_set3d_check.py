#!/usr/bin/env python3
"""ae_set3d_check - Phase 8 set gate: validate + build every .set3d.json.

Every ``src/game/content/sets/*.set3d.json`` must pass the
``engine.render3d`` validator and flatten (via ``game.render3d_bridge``'s
prop library) into renderer primitives without error.  Pixel parity for
sets in production is proven by the golden cutscene shots; this gate is
the cheap structural tripwire.  Run by ae_ci.

    python tools/ae_set3d_check.py [-v]
"""
from __future__ import annotations

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETS_DIR = os.path.join(ROOT, "src", "game", "content", "sets")


def main() -> int:
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    sys.path.insert(0, os.path.join(ROOT, "src"))

    problems: list[str] = []
    paths = sorted(glob.glob(os.path.join(SETS_DIR, "*.set3d.json")))
    if not paths:
        print("AE SET3D: FAIL (no .set3d.json files in src/game/content/sets/)")
        return 1

    from engine.render3d import Set3DError, build, from_dict, validate
    import game.render3d_bridge as bridge

    checked = 0
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for problem in validate(data):
            problems.append(f"{os.path.basename(path)}: {problem}")
            continue
        try:
            prims = build(from_dict(data), library=bridge.PROP_LIBRARY,
                          presets=bridge.presets())
        except Set3DError as e:
            problems.append(f"{os.path.basename(path)}: build failed: {e}")
            continue
        checked += 1
        if verbose:
            print(f"  {data.get('id')}: OK ({len(prims)} primitives)")
    if problems:
        print(f"AE SET3D: FAIL ({checked}/{len(paths)} sets built)")
        for p in problems:
            print("  - " + p)
        return 1
    print(f"AE SET3D: OK ({checked} sets valid, primitives build clean)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
