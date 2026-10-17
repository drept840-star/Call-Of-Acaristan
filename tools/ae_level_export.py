#!/usr/bin/env python3
"""ae_level_export.py - export the legacy mission grids to .level.json (RPE6 P7-M2).

Imports each mission package (the grids are produced by its generator/builder at
import time), reads the final ``list[str]`` grids, and writes
``src/game/content/levels/<id>.level.json`` with the floor layer plus marker
objects (P = player spawn, E = enemy spawn) and stage metadata. Re-running it is
the reproducibility path: ``tools/ae_level_check.py`` proves the committed data
still equals what the legacy generators produce.

Usage: python tools/ae_level_export.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "src", "game", "content", "levels")

# (level_id, module, attribute, display name)
SPECS = [
    ("m1.warehouse", "missions.m1.map", "mission1_map", "Mission 1 - Warehouse"),
    ("m2.city", "missions.m2.world", "MISSION2_MAP", "Mission 2 - City"),
    ("m3.cell", "missions.m3.maps", "MISSION3_CELL_MAP", "Mission 3 - Cell block"),
    ("m3.comms", "missions.m3.maps", "MISSION3_COMMS_MAP", "Mission 3 - Comms"),
    ("m3.archives", "missions.m3.maps", "MISSION3_ARCHIVES_MAP", "Mission 3 - Archives"),
    ("m3.kill_order", "missions.m3.maps", "MISSION3_KILL_ORDER_MAP", "Mission 3 - Kill order"),
    ("m3.broadcast", "missions.m3.maps", "MISSION3_BROADCAST_MAP", "Mission 3 - Broadcast"),
    ("m4.street", "missions.m4.maps", "MISSION4_STREET_MAP", "Mission 4 - Street"),
    ("m4.station", "missions.m4.maps", "MISSION4_STATION_MAP", "Mission 4 - Station"),
    ("m5.hq", "missions.m5.maps", "MISSION5_HQ_MAP", "Mission 5 - Guard HQ"),
    ("m5.quarter", "missions.m5.maps", "MISSION5_QUARTER_MAP", "Mission 5 - Lower Quarter"),
    ("m5.print", "missions.m5.maps", "MISSION5_PRINT_MAP", "Mission 5 - Print works"),
    ("m5.tunnel", "missions.m5.maps", "MISSION5_TUNNEL_MAP", "Mission 5 - Tunnel"),
]
_MARKERS = {"P": ("spawn", {"who": "player"}), "E": ("spawn", {"who": "enemy"})}
# 'E' is an enemy marker only in M1's grammar; in M3 grids it is a floor tile code.
_MARKERS_BY_MISSION = {"m1": _MARKERS}


def _row_str(r) -> str:
    return r if isinstance(r, str) else "".join(r)      # some generators return list-of-chars rows


def build_level(level_id: str, name: str, grid) -> dict:
    rows = [_row_str(r) for r in grid]
    markers = _MARKERS_BY_MISSION.get(level_id.split(".")[0], {"P": _MARKERS["P"]})
    objects = []
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch in markers:
                kind, props = markers[ch]
                objects.append({"id": f"{kind}-{props['who']}@{c},{r}", "kind": kind, "tile": [c, r],
                                "props": dict(props, marker=ch)})
    mission = level_id.split(".")[0]
    return {"schema": "ae.level/1", "id": level_id, "name": name, "tile_size": 64,
            "layers": {"floor": rows}, "objects": objects, "triggers": [], "paths": [], "lights": [],
            "decor": [], "procedural_decor": [], "metadata": {"mission": mission}}


def export_all(dry_run: bool = False) -> list[str]:
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "src"))
    os.environ["ACA_LEVEL_SRC"] = "legacy"           # export from the generators, never from flipped data
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import ae_replay  # noqa: F401  (boots pygame + config)
    import importlib

    written = []
    if not dry_run:
        os.makedirs(OUT_DIR, exist_ok=True)
    for level_id, mod_name, attr, name in SPECS:
        mod = importlib.import_module(mod_name)
        grid = getattr(mod, attr)
        data = build_level(level_id, name, grid)
        text = json.dumps(data, indent=1, sort_keys=False) + "\n"
        path = os.path.join(OUT_DIR, level_id + ".level.json")
        if dry_run:
            print(f"  would write {level_id}: {len(data['layers']['floor'])} rows, {len(data['objects'])} objects")
        else:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            written.append(level_id)
            print(f"  wrote {level_id}: {len(data['layers']['floor'])} rows, {len(data['objects'])} objects")
    return written


def main() -> int:
    dry = "--dry-run" in sys.argv
    written = export_all(dry)
    print(f"AE LEVEL EXPORT: {'dry-run' if dry else f'wrote {len(written)} levels'} -> src/game/content/levels/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
