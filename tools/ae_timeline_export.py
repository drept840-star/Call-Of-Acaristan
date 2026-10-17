#!/usr/bin/env python3
"""ae_timeline_export - write the legacy cutscene shot lists as ae.timeline/1 data.

RPE6 Phase 8 (P8-M3).  One-way export from the in-code shot tables into
``src/game/content/timelines/*.timeline.json``; each file's ``shots`` are
the legacy shot dicts verbatim (tuples become JSON arrays; the runtime
converter restores them).  Run with the legacy sources forced so a flipped
tree re-exports from the tables, never from its own output.

    python tools/ae_timeline_export.py [--dry-run]
"""
from __future__ import annotations

import importlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "src", "game", "content", "timelines")

# (timeline id, module, attribute) - every *_shots list in the tree.
SPECS = [
    ("core.cutscene1", "cutscenes.engine", "cutscene1_shots"),
    ("core.cutscene2", "cutscenes.engine", "cutscene2_shots"),
    ("m2.intro", "missions.m2.meta", "mission2_intro_shots"),
    ("m2.ending", "missions.m2.meta", "mission2_ending_shots"),
    ("m2.seby_pickup", "missions.m2.meta", "seby_pickup_shots"),
    ("m3.intro", "missions.m3.meta", "mission3_intro_shots"),
    ("m3.ending", "missions.m3.meta", "mission3_ending_shots"),
    ("m3.vent_escape", "missions.m3.meta", "vent_escape_shots"),
    ("m3.k9_pickup", "missions.m3.meta", "k9_pickup_shots"),
    ("m3.service_transition", "missions.m3.meta", "service_transition_shots"),
    ("m3.volkov_mags", "missions.m3.meta", "volkov_mags_shots"),
    ("m3.archives_transition", "missions.m3.meta", "archives_transition_shots"),
    ("m3.ko_transition", "missions.m3.meta", "ko_transition_shots"),
    ("m3.broadcast_transition", "missions.m3.meta", "broadcast_transition_shots"),
    ("m3.vostral_pickup", "missions.m3.meta", "vostral_pickup_shots"),
    ("m3.broadcast_fail", "missions.m3.meta", "broadcast_fail_shots"),
    ("m4.intro", "missions.m4.meta", "mission4_intro_shots"),
    ("m4.ending", "missions.m4.meta", "mission4_ending_shots"),
    ("m5.intro", "missions.m5.meta", "mission5_intro_shots"),
    ("m5.ending", "missions.m5.meta", "mission5_ending_shots"),
]


def _ladder_docs() -> dict:
    """The M4 frame-scheduled radio ladders (Phase 7 rescope) as event tracks."""
    from missions.m4 import flow as m4
    story = [{"t": frame, "name": mark, "text": line, "color": list(color), "duration": 440}
             for frame, mark, line, color in m4._M4_STORY_BEATS]
    arrest = [{"t": frame, "name": mark, "text": line, "color": list(color), "sfx": sfx, "duration": 470}
              for frame, mark, color, sfx, line in m4._M4_ARREST_BEATS]
    base = {"schema": "ae.timeline/1", "fps_hint": 60, "metadata": {"time_unit": "frames"}}
    return {
        "m4.story_beats": {**base, "id": "m4.story_beats", "tracks": {"event": story},
                           "metadata": {"time_unit": "frames", "kind": "radio_ladder",
                                        "source": "missions/m4/flow.py _M4_STORY_BEATS"}},
        "m4.arrest_beats": {**base, "id": "m4.arrest_beats", "tracks": {"event": arrest},
                            "metadata": {"time_unit": "frames", "kind": "radio_ladder",
                                         "source": "missions/m4/flow.py _M4_ARREST_BEATS"}},
    }


def build() -> dict:
    docs = {}
    docs.update(_ladder_docs())
    for tid, mod_name, attr in SPECS:
        mod = importlib.import_module(mod_name)
        shots = getattr(mod, attr)
        docs[tid] = {"schema": "ae.timeline/1", "id": tid,
                     "shots": [dict(s) for s in shots],
                     "metadata": {"kind": "cutscene_shots", "source": f"{mod_name}.{attr}"}}
    return docs


def main() -> int:
    dry = "--dry-run" in sys.argv
    os.environ["ACA_TL_SRC"] = "legacy"               # export from the tables, never from flipped data
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import ae_replay  # noqa: F401  (full boot, same as the other exporters)
    docs = build()
    if not dry:
        os.makedirs(OUT_DIR, exist_ok=True)
    total = 0
    for tid, doc in sorted(docs.items()):
        total += len(doc.get("shots", [])) + sum(len(t) for t in doc.get("tracks", {}).values())
        if not dry:
            path = os.path.join(OUT_DIR, tid + ".timeline.json")
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    print(f"AE TIMELINE EXPORT: {'checked' if dry else 'wrote'} {len(docs)} timelines "
          f"({total} shots) -> src/game/content/timelines/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
