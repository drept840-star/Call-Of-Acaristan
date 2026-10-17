"""RPE6 import side-effect check (R7, §6.1 acceptance).

    python tools/ae_import_check.py [--legacy]

Imports modules one by one in a fresh interpreter (SDL dummy drivers, so no
real window pops up on a dev machine) and records the first module after which
a display surface exists, pygame is initialised, or the mixer is running.
  engine  : every module under src/engine/  -> ENFORCED (must be clean)
  legacy  : every other src module except the app entry point and src/tools
            (--legacy; WARN, baseline tracked in STATUS.md)
Prints `IMPORT CHECK: OK (...)` / `IMPORT CHECK: FAIL (...)`.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

PROBE = r"""
import importlib, json, os, sys
sys.path.insert(0, %(src)r)
mods = json.loads(%(mods)r)
import pygame
def state():
    return {"surface": pygame.display.get_surface() is not None,
            "init": bool(pygame.get_init()),
            "mixer": bool(pygame.mixer.get_init())}
base = state()
out = {"base": base, "offenders": [], "errors": []}
seen = set()
for m in mods:
    try:
        importlib.import_module(m)
    except BaseException as e:
        out["errors"].append([m, repr(e)[:200]])
        continue
    s = state()
    for k, v in s.items():
        if v and not base[k] and k not in seen:
            seen.add(k)
            out["offenders"].append([m, k])
print("@@" + json.dumps(out))
"""


def modules(prefix_filter):
    out = []
    for p in sorted(SRC.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(SRC).with_suffix("")
        parts = list(rel.parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts:
            continue
        m = ".".join(parts)
        if prefix_filter(m):
            out.append(m)
    return out


def probe(mods):
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", PYGAME_HIDE_SUPPORT_PROMPT="1")
    code = PROBE % {"src": str(SRC), "mods": json.dumps(mods)}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env,
                       cwd=str(ROOT), timeout=600)
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("@@")), None)
    if line is None:
        return {"offenders": [], "errors": [["<probe>", (r.stderr or r.stdout)[-400:]]]}
    return json.loads(line[2:])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy", action="store_true")
    a = ap.parse_args()
    eng = modules(lambda m: m == "engine" or m.startswith("engine."))
    res = probe(eng)
    ok = not res["offenders"] and not res["errors"]
    for m, k in res["offenders"]:
        print(f"ENGINE SIDE EFFECT: importing {m} -> {k}")
    for m, e in res["errors"]:
        print(f"ENGINE IMPORT ERROR: {m}: {e}")
    msg = f"engine {len(eng)} modules clean" if ok else f"engine {len(res['offenders'])} side effects, {len(res['errors'])} errors"
    if a.legacy:
        leg = modules(lambda m: not (m == "engine" or m.startswith("engine.") or m == "app" or m.startswith("tools")))
        lr = probe(leg)
        for m, k in lr["offenders"]:
            print(f"legacy (warn): first {k} after importing {m}")
        msg += f"; legacy {len(leg)} modules, first-offenders {len(lr['offenders'])} (warn), import errors {len(lr['errors'])}"
        for m, e in lr["errors"][:10]:
            print(f"legacy import error (warn): {m}: {e}")
    print(("IMPORT CHECK: OK (" if ok else "IMPORT CHECK: FAIL (") + msg + ")")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
