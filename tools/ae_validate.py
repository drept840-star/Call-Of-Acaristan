#!/usr/bin/env python3
"""AE VALIDATE - load every game data file through its public loader.

RPE6 Phase 10 (M4). Data families that went data-driven in Phases
7-8 (levels, dialogue, timelines, 3D sets) are enumerated from
src/game/content/ and loaded via the same facade functions the game
uses, so a malformed file fails here instead of at runtime. Every
content JSON is also parse-checked.

Prints "AE VALIDATE: OK (N files: L levels, D dialogues, T
timelines, S sets)" and exits 0; any failure exits 1.
"""
import json
import os
import sys


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(root, "src"))
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((64, 64))

    from game import dialogues, levels, render3d_bridge, timelines

    content = os.path.join(root, "src", "game", "content")
    counts = {"levels": 0, "dialogue": 0, "timelines": 0, "sets": 0}
    total = 0

    def ids(subdir, suffix):
        d = os.path.join(content, subdir)
        return sorted(f[: -len(suffix)] for f in os.listdir(d)
                      if f.endswith(suffix))

    for lid in ids("levels", ".level.json"):
        lv = levels.level(lid)
        assert lv.grid(), lid
        counts["levels"] += 1
    for did in ids("dialogue", ".dlg.json"):
        dlg = dialogues.dialogue(did)
        assert dlg.nodes, did
        counts["dialogue"] += 1
    for tid in ids("timelines", ".timeline.json"):
        timelines.timeline(tid)  # from_dict validation lives in the load
        with open(os.path.join(timelines.TIMELINES_DIR,
                               f"{tid}.timeline.json"),
                  encoding="utf-8") as fh:
            raw = json.load(fh)
        if raw.get("shots"):  # beat-only event tracks carry no shots
            assert timelines.shots(tid, None), tid
        counts["timelines"] += 1
    for sid in ids("sets", ".set3d.json"):
        assert render3d_bridge.set_prims(sid), sid
        counts["sets"] += 1

    for dirpath, _dirs, files in os.walk(content):
        for f in files:
            if f.endswith(".json"):
                with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                    json.load(fh)
                total += 1

    print(f"AE VALIDATE: OK ({total} files: {counts['levels']} levels, "
          f"{counts['dialogue']} dialogues, {counts['timelines']} timelines, "
          f"{counts['sets']} sets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
