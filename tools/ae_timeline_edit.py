#!/usr/bin/env python3
"""ae_timeline_edit - the Phase 8 camera/track key editor (CLI form).

The in-window editor (§6.20) is future work; this is its file-level core:
read a ``.timeline.json``, move one key's field, write it back with the
same formatting (indent 1, key order preserved), and verify by re-loading
through ``engine.timeline`` and sampling both versions - the frame must
change exactly at the edited key.

    python tools/ae_timeline_edit.py set-key <file> <track> <key-index> <field> <json-value> [--check-only]
    python tools/ae_timeline_edit.py sample <file> <t> [track]

Exit 0 on success; the before/after sample lines are the round-trip proof.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _sample(data, track, t):
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from engine.timeline import TimelinePlayer, from_dict
    return TimelinePlayer(from_dict(data)).sample(t).values.get(track, {})


def set_key(path: str, track: str, index: int, field: str, raw_value: str,
            check_only: bool = False) -> int:
    data = _load(path)
    tracks = data.get("tracks", {})
    if track not in tracks:
        print(f"AE TIMELINE EDIT: FAIL (no track {track!r} in {path})")
        return 1
    keys = tracks[track]
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        value = raw_value
    key = keys[index]
    t = key.get("t", 0)
    before = _sample(data, track, t)
    old = key.get(field)
    key[field] = value
    after = _sample(data, track, t)
    if not check_only:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
        reloaded = _sample(_load(path), track, t)
        if reloaded != after:
            print("AE TIMELINE EDIT: FAIL (reloaded sample differs from in-memory sample)")
            return 1
    changed = before.get(field) != after.get(field)
    print(f"AE TIMELINE EDIT: {'OK' if changed else 'FAIL'} "
          f"({track}[{index}].{field}: {old!r} -> {value!r} at t={t}; "
          f"sample {before.get(field)!r} -> {after.get(field)!r}{' (not written)' if check_only else ''})")
    return 0 if changed else 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd == "set-key":
        check_only = "--check-only" in argv
        args = [a for a in argv[1:] if a != "--check-only"]
        path, track, index, field, raw = args[0], args[1], int(args[2]), args[3], args[4]
        return set_key(path, track, index, field, raw, check_only)
    if cmd == "sample":
        data = _load(argv[1])
        t = float(argv[2])
        track = argv[3] if len(argv) > 3 else None
        sys.path.insert(0, os.path.join(ROOT, "src"))
        from engine.timeline import TimelinePlayer, from_dict
        sample = TimelinePlayer(from_dict(data)).sample(t)
        print(json.dumps(sample.values.get(track) if track else sample.values,
                         indent=1, ensure_ascii=False, default=str))
        return 0
    print(f"AE TIMELINE EDIT: FAIL (unknown command {cmd!r})")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
