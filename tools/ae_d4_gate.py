#!/usr/bin/env python3
"""ae_d4_gate.py - D4 grep gate: no attribute stuffing on entity objects (RPE6 §2 D4, §6.4 acceptance).

    python tools/ae_d4_gate.py            # check (exit 1 on a violation or a ratchet regression)
    python tools/ae_d4_gate.py --update   # re-record the ratchet baseline after a migration step
    python tools/ae_d4_gate.py -v         # list every site

Two rules over src/ (engine/ and net/ excluded):

  HARD  ``getattr(x, "_name", ...)`` / ``setattr(x, "_name", ...)`` / ``hasattr(x, "_name")`` with an
        underscore-prefixed attribute on an entity-like receiver (``e``, ``en``, ``enemy``, ``new_e``,
        ``g``, ``guard``, ``npc``, ``p``, ``player``, ``corpse``, ``v`` (posed sprites), ``self`` inside src/entities/).
        Always a failure.
  RATCHET  mission-prefixed data on any object that is not the game state - ``x.m3_foo = ...``,
        ``getattr(x, "m5_bar", d)``, ``x.is_missionN_...`` (enemies, doors, props) - counted per family; the count may never grow (baseline in
        docs/engine/evidence/phase5/d4_baseline.json) and must reach 0 for Phase 5 to exit.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
BASELINE = os.path.join(ROOT, "docs", "engine", "evidence", "phase5", "d4_baseline.json")
EXCLUDE_DIRS = {os.path.join("src", "engine"), os.path.join("src", "net")}
EXCLUDE_FILES: set = set()
ENTITY_VARS = {"e", "en", "enemy", "new_e", "g", "guard", "npc", "p", "player", "corpse", "commander",
               "commander_enemy", "miniboss", "target", "victim", "v"}

_STATE_LIKE = {"STATE", "state", "self", "st", "s", "gc", "cfg", "config", "_S", "_state", "game_state"}
_HARD = re.compile(r'\b(getattr|setattr|hasattr)\(\s*(\w+)\s*,\s*"(_[A-Za-z0-9_]*)"')
_RATCHET_GET = re.compile(r'\b(getattr|setattr|hasattr)\(\s*(\w+)\s*,\s*"((?:m[1-5]_|is_mission[1-5]_)[A-Za-z0-9_]*)"')
_RATCHET_DOT = re.compile(r'\b(\w+)\.((?:m[1-5]_|is_mission[1-5]_)[A-Za-z0-9_]*)\b(?!\s*\()')   # calls = module functions, not data


def _files():
    for dp, dn, fn in os.walk(SRC):
        rel = os.path.relpath(dp, ROOT)
        if any(rel == ex or rel.startswith(ex + os.sep) for ex in EXCLUDE_DIRS):
            dn[:] = []
            continue
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            if f.endswith(".py"):
                p = os.path.join(dp, f)
                if os.path.relpath(p, ROOT) in EXCLUDE_FILES:
                    continue
                yield p


def _entity_receiver(var: str, path: str) -> bool:
    if var in ENTITY_VARS:
        return True
    return var == "self" and os.sep + "entities" + os.sep in path


def scan():
    hard, ratchet = [], {}
    for p in _files():
        rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
        in_doc = None  # inside a triple-quoted string (docstrings describe the old names; not code)
        with open(p, encoding="utf-8", errors="replace") as fh:
            for ln, line in enumerate(fh, 1):
                code = re.sub(r'"""[^"]*"""', '""', line.split("#", 1)[0])   # one-line docstrings
                if in_doc:
                    if in_doc in code:
                        code = code.split(in_doc, 1)[1]
                        in_doc = None
                    else:
                        continue
                for q in ('"""', "\'\'\'"):
                    if code.count(q) % 2 == 1:
                        code = code.split(q, 1)[0]
                        in_doc = q
                        break
                for m in _HARD.finditer(code):
                    fn, var, attr = m.groups()
                    if _entity_receiver(var, p):
                        hard.append((rel, ln, f"{fn}({var}, \"{attr}\")"))
                for m in _RATCHET_GET.finditer(code):
                    fn, var, attr = m.groups()
                    if var not in _STATE_LIKE:
                        fam = attr.split("_", 1)[0] + "_" if attr.startswith("m") else "is_missionN_"
                        ratchet.setdefault(fam, []).append((rel, ln, f"{fn}({var}, \"{attr}\")"))
                for m in _RATCHET_DOT.finditer(code):
                    var, attr = m.groups()
                    if var in _STATE_LIKE:
                        continue
                    fam = attr.split("_", 1)[0] + "_" if attr.startswith("m") else "is_missionN_"
                    ratchet.setdefault(fam, []).append((rel, ln, f"{var}.{attr}"))
    return hard, ratchet


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--update", action="store_true", help="re-record the ratchet baseline")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    hard, ratchet = scan()
    counts = {k: len(v) for k, v in sorted(ratchet.items())}
    base = {}
    if os.path.isfile(BASELINE):
        with open(BASELINE, encoding="utf-8") as fh:
            base = json.load(fh).get("families", {})
    ok = True
    if hard:
        ok = False
        print(f"HARD violations ({len(hard)}): underscore attributes on entity objects")
        for rel, ln, what in hard:
            print(f"  {rel}:{ln}: {what}")
    print("mission-prefixed attribute sites on entities (ratchet, must reach 0):")
    for fam, n in counts.items():
        b = base.get(fam)
        flag = "" if b is None or n <= b else "  <-- REGRESSION"
        if b is not None and n > b:
            ok = False
        print(f"  {fam:14s} {n:4d}  (baseline {b if b is not None else '-'}){flag}")
        if a.verbose:
            for rel, ln, what in ratchet[fam]:
                print(f"      {rel}:{ln}: {what}")
    for fam, b in base.items():
        if fam not in counts:
            print(f"  {fam:14s}    0  (baseline {b})  cleared")
    total = sum(counts.values())
    if a.update:
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        with open(BASELINE, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"schema": "ae.d4_baseline/1", "families": counts}, fh, indent=1)
            fh.write("\n")
        print("baseline updated:", os.path.relpath(BASELINE, ROOT))
    print(f"AE D4: {'OK' if ok else 'FAIL'} (hard={len(hard)}, remaining mission-prefixed sites={total}"
          f"{', exit criterion met' if total == 0 and not hard else ''})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
