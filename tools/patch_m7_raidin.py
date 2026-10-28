"""One-shot data patch for the M7 raid-in film caption - run from the repo root:

    python tools/patch_m7_raidin.py [--dry-run]

Why: the raid-in bridge film (top-down farm -> the 3D raid) used to show the
Guard trucks rolling up to the yard while Alex called "Trucks! Two of them -
no, three!" (VO_226) - but in the raid itself the trucks only come up the
track in wave 2, where the very same call plays again (missions/m7/raid3d.py,
_begin_wave).  The film visuals (cutscenes/m7films.py) now keep the convoy
far up the valley and show wave 1's vanguard - the dog and the riflemen -
working in from the orchard, and this patch retimes the caption to match:
Bodi gets a new line (VO_229, caption-only until recorded, already listed in
audio/voice_manifest.KNOWN_MISSING_AUDIO):

    "Eyes on the trees, not the track. First knock comes on foot."

It sets up Bodi's wave-1-clear call ("That's the first knock. They'll come
up the track next.") and leaves VO_226 for the moment the trucks arrive.

Edits src/game/content/timelines/m7.raidin.timeline.json in place, in the
canonical shape (json indent=1, LF endings, trailing newline) that
tools/ae_timeline_edit.py and game.timelines.save_timeline write, after
engine.timeline validation.  Idempotent: re-running reports "already
patched".
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

TIMELINE = ROOT / "src" / "game" / "content" / "timelines" / "m7.raidin.timeline.json"

OLD_SPEAKER = "ALEX"
OLD_TEXT = "Trucks! Two of them - no, three!"
NEW_SPEAKER = "BODI"
NEW_TEXT = "Eyes on the trees, not the track. First knock comes on foot."


def _is_old(speaker, text) -> bool:
    if not text:
        return False
    t = str(text).strip()
    return t == OLD_TEXT or (str(speaker).upper() == OLD_SPEAKER and "Trucks!" in t)


def patch(data: dict) -> int:
    """Rewrite the truck call in every shot caption / dialogue event. Count."""
    n = 0
    for shot in data.get("shots", ()):
        if _is_old(shot.get("speaker"), shot.get("text")):
            shot["speaker"], shot["text"] = NEW_SPEAKER, NEW_TEXT
            n += 1
        events = shot.get("dialogue_events")
        if isinstance(events, list):
            for ev in events:
                if isinstance(ev, list) and len(ev) >= 3 and _is_old(ev[1], ev[2]):
                    ev[1], ev[2] = NEW_SPEAKER, NEW_TEXT
                    n += 1
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="report only, do not write")
    args = ap.parse_args(argv)

    if not TIMELINE.exists():
        print(f"timeline not found: {TIMELINE}")
        return 2
    data = json.loads(TIMELINE.read_text(encoding="utf-8"))

    n = patch(data)
    if n == 0:
        blob = json.dumps(data, ensure_ascii=False)
        if NEW_TEXT in blob:
            print("already patched - nothing to do")
            return 0
        print(f"no shot caption matches {OLD_TEXT!r}; inspect {TIMELINE.name} manually")
        return 1

    from engine.timeline import from_dict
    from_dict(data, source=TIMELINE.name)          # raises TimelineError on problems

    if args.dry_run:
        print(f"would rewrite {n} caption(s): {OLD_SPEAKER} {OLD_TEXT!r}"
              f" -> {NEW_SPEAKER} {NEW_TEXT!r}")
        return 0
    with open(TIMELINE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"patched {n} caption(s) in {os.path.relpath(TIMELINE, ROOT)}")
    print("remember: golden captures of m7_raidin_* frames will drift - re-baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
