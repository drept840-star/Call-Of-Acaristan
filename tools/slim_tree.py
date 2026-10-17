#!/usr/bin/env python3
"""slim_tree.py - remove dead weight from the project root (dry run by default).

Everything this script deletes is either a duplicate, a build/scratch artefact,
or a trailer/hand-off leftover that the game never loads:

  1. voice ``.wav`` files that have an ``.ogg`` twin next to them
     (the game plays the ``.ogg``; a surviving twin doubles the take in
     ``audio.voice`` speaker-folder alignment - this is the big one, ~45 MB)
  2. golden PNGs not listed in their set's ``manifest.json`` (stale shot ids)
  3. scratch / cache output: ``build/``, ``outputs/``, ``tests/golden/_verify/``,
     ``assets/voice/_radio_cache/``, ``crash_reports/``, ``__pycache__/``, ``*.pyc``
  4. trailer-only media: ``sfx_wav/``, ``assets/voice/Trailer/``,
     ``assets/music/trailer/``, ``assets/voice/Old Fisherman/`` (duplicates of
     the numbered ``VO_`` takes)
  5. one-off hand-off material: ``handoff/``, ``SKILLS/``, the Notion skill
     export, root ``icon.png`` / ``icon_ai.png`` / ``wordmark.*`` (unreferenced),
     ``apply_k9_patch.py``, ``apply_m5_harbour.py``, ``apply_m5_reset.py``,
     ``_inspect2.py``, ``tools/_tmp_repl.json``, the superseded
     ``tools/overlay_cleanup.py``
  6. root copies of notes already archived in ``docs/history/`` (``FIXES.md``,
     ``IMPLEMENTED.md``, ``MASTER_PROMPT.md``, ``manifest.json``,
     ``MULTIPLAYER_PATCH_SHA256.json``; ``VALIDATION.md`` lives in
     ``validation/``) - removed only when the archived twin exists
  7. loop baselines older than the newest two (``tests/loop/baseline_v*``;
     only the newest set is checked, the previous one is kept for diffs)

Usage (from the project root, the folder that contains ``acaristan.py``):

    python tools/slim_tree.py            # list what would go, with sizes
    python tools/slim_tree.py --apply    # delete it

Nothing under ``src/``, ``tools/``, ``docs/``, ``assets/baked/``, ``assets/art/``,
``assets/sprites/``, ``tests/unit|api|loop|replay`` or any ``manifest.json`` is
ever touched.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCRATCH_DIRS = [
    "build",
    "outputs",
    "crash_reports",
    os.path.join("tests", "golden", "_verify"),
    os.path.join("assets", "voice", "_radio_cache"),
    # machine-local oracle sets (ACA_GOLDEN_SET / ACA_LOOP_SET overrides, Phase 5): never the owner's baselines
    os.path.join("tests", "golden", "sandbox_linux"),
    os.path.join("tests", "loop", "sandbox_linux"),
]
LEFTOVER_DIRS = [
    "sfx_wav",
    "handoff",
    "SKILLS",
    os.path.join("assets", "voice", "Trailer"),
    os.path.join("assets", "music", "trailer"),
    os.path.join("assets", "voice", "Old Fisherman"),
]
LEFTOVER_FILES = [
    "icon.png",
    "icon_ai.png",
    "wordmark.png",
    "wordmark.html",
    "apply_k9_patch.py",
    "apply_m5_harbour.py",
    "apply_m5_reset.py",
    "_inspect2.py",
    os.path.join("tools", "overlay_cleanup.py"),  # superseded by this script
    os.path.join("tools", "_tmp_repl.json"),  # editor scratch
]
LEFTOVER_GLOBS = ["create-beautiful-pygame-graphics*.md"]  # Notion skill export (its siblings lived in SKILLS/)
# Root copies of notes that were moved to docs/history/ (or validation/): removed only when the archived twin exists.
ROOT_DUPLICATES = {
    "FIXES.md": os.path.join("docs", "history", "FIXES.md"),
    "IMPLEMENTED.md": os.path.join("docs", "history", "IMPLEMENTED.md"),
    "MASTER_PROMPT.md": os.path.join("docs", "history", "MASTER_PROMPT.md"),
    "MULTIPLAYER_PATCH_SHA256.json": os.path.join("docs", "history", "MULTIPLAYER_PATCH_SHA256.json"),
    "manifest.json": os.path.join("docs", "history", "manifest.json"),
    "VALIDATION.md": os.path.join("validation", "M5_harbour_graphics.md"),
}
LOOP_BASELINES_KEPT = 2  # newest N tests/loop/baseline_v* sets stay (current + previous); older history goes
SKIP_WALK = {".git", ".venv", "venv", "node_modules", ".idea", ".vscode"}


def _size(path: str) -> int:
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for dp, _dn, fn in os.walk(path):
        for f in fn:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def _walk(top: str):
    for dp, dn, fn in os.walk(top):
        dn[:] = [d for d in dn if d not in SKIP_WALK]
        yield dp, dn, fn


def collect() -> list[tuple[str, str]]:
    """Return (reason, absolute path) pairs; directories are listed once."""
    out: list[tuple[str, str]] = []

    # 1. voice .wav twins
    vdir = os.path.join(ROOT, "assets", "voice")
    if os.path.isdir(vdir):
        for dp, dn, fn in _walk(vdir):
            dn[:] = [d for d in dn if d != "_radio_cache"]
            for f in fn:
                if f.lower().endswith(".wav") and os.path.exists(os.path.join(dp, f[:-4] + ".ogg")):
                    out.append(("wav twin", os.path.join(dp, f)))

    # 2. orphan golden PNGs
    gdir = os.path.join(ROOT, "tests", "golden")
    if os.path.isdir(gdir):
        for name in sorted(os.listdir(gdir)):
            sdir = os.path.join(gdir, name)
            man = os.path.join(sdir, "manifest.json")
            if name.startswith("_") or not os.path.isfile(man):
                continue
            try:
                with open(man, "r", encoding="utf-8") as fh:
                    ids = set(json.load(fh).get("shots", {}).keys())
            except (OSError, ValueError):
                continue
            if not ids:
                continue
            for f in sorted(os.listdir(sdir)):
                if f.lower().endswith(".png") and f[:-4] not in ids:
                    out.append(("orphan golden", os.path.join(sdir, f)))

    # 3./4./5. scratch + leftovers
    for rel in SCRATCH_DIRS:
        p = os.path.join(ROOT, rel)
        if os.path.isdir(p):
            out.append(("scratch dir", p))
    for rel in LEFTOVER_DIRS:
        p = os.path.join(ROOT, rel)
        if os.path.isdir(p):
            out.append(("leftover dir", p))
    for rel in LEFTOVER_FILES:
        p = os.path.join(ROOT, rel)
        if os.path.isfile(p):
            out.append(("leftover file", p))
    import glob as _glob
    for pat in LEFTOVER_GLOBS:
        for p in sorted(_glob.glob(os.path.join(ROOT, pat))):
            if os.path.isfile(p):
                out.append(("leftover file", p))
    for name, twin in ROOT_DUPLICATES.items():
        p = os.path.join(ROOT, name)
        if os.path.isfile(p) and os.path.isfile(os.path.join(ROOT, twin)):
            out.append(("root duplicate", p))
    ldir = os.path.join(ROOT, "tests", "loop")
    if os.path.isdir(ldir):
        sets = []
        for d in os.listdir(ldir):
            if d.startswith("baseline_v") and d[10:].isdigit() and os.path.isdir(os.path.join(ldir, d)):
                sets.append((int(d[10:]), d))
        for _v, d in sorted(sets)[:-LOOP_BASELINES_KEPT]:
            out.append(("old loop set", os.path.join(ldir, d)))
    for dp, dn, fn in _walk(ROOT):
        for d in list(dn):
            if d == "__pycache__":
                out.append(("pycache", os.path.join(dp, d)))
                dn.remove(d)
        for f in fn:
            if f.endswith(".pyc"):
                out.append(("pyc", os.path.join(dp, f)))
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="delete instead of listing")
    a = ap.parse_args(argv)

    items = collect()
    by_reason: dict[str, list[int]] = {}
    total = 0
    for reason, p in items:
        s = _size(p)
        total += s
        by_reason.setdefault(reason, [0, 0])
        by_reason[reason][0] += 1
        by_reason[reason][1] += s
        if reason not in ("wav twin", "pycache", "pyc", "orphan golden"):
            print(f"  {reason:14s} {s / 1e6:7.1f} MB  {os.path.relpath(p, ROOT)}")
    for reason in ("wav twin", "orphan golden", "pycache", "pyc"):
        if reason in by_reason:
            n, s = by_reason[reason]
            print(f"  {reason:14s} {s / 1e6:7.1f} MB  ({n} files)")
    print(f"TOTAL: {len(items)} entries, {total / 1e6:.1f} MB" + ("" if a.apply else "  (dry run; add --apply)"))

    if not a.apply:
        return 0
    removed = 0
    for _reason, p in items:
        try:
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p)
            elif os.path.lexists(p):
                os.remove(p)
            removed += 1
        except OSError as e:
            print(f"  ! could not remove {os.path.relpath(p, ROOT)}: {e}")
    print(f"removed {removed}/{len(items)} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
