"""RPE6 boundary lint (master prompt §5.3, D1).

    python tools/check_boundaries.py [--warn-only] [--json out.json]

ENFORCED (non-zero exit), since engine code is new:
  E1 engine.* imports only stdlib, pygame, numpy and engine.* (rule 1/4)
  E2 engine.core imports only stdlib, pygame, numpy and engine.core (rule 1)
  E3 only engine.render3d may import engine3d / moderngl (rule 6)
  E4 code outside engine imports engine.<pkg> public packages only, not
     engine.<pkg>.<module> or _private names (rule 5)
  E5 no import cycles inside engine.* (rule 7)
WARN (legacy baseline, tracked in STATUS.md, to reach 0 by Phase 2):
  W1 shared -> mission edges (baseline_v0: 169)
Import resolution is shared with tools/ae_audit.py. Prints
`BOUNDARIES: OK (...)` or `BOUNDARIES: FAIL (...)`.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ae_audit as A  # noqa: E402

STDLIB = set(sys.stdlib_module_names) | {"__future__"}
ENGINE_EXT_OK = {"pygame", "numpy"}
RENDER3D_EXT_OK = {"moderngl"}
# 48 through Phase 9; 49 from Phase 10: Mission 0 adds the one
# core.game_core -> missions.m0 edge every mission has (deliberate,
# recorded in ADR-021 - not an accidental regression).
BASELINE_W1 = 49


def collect():
    files = list(A.iter_py(A.SRC)) + list(A.iter_py(A.TOOLS))
    mods = {A.modname(p) for p in files}
    edges = []
    for p in files:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8-sig"), filename=str(p))
        except SyntaxError:
            continue
        mod, is_pkg = A.modname(p), p.name == "__init__.py"
        funcs = {id(s) for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 for s in ast.walk(n)}
        for n in ast.walk(tree):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in n.names]
                for tgt in A.resolve_import(mod, is_pkg, n, mods):
                    edges.append({"from": mod, "to": tgt, "lazy": id(n) in funcs, "path": A.rel(p),
                                  "line": n.lineno, "names": names,
                                  "is_from": isinstance(n, ast.ImportFrom)})
    return mods, edges


def is_engine(m: str) -> bool:
    return m == "engine" or m.startswith("engine.")


def check(mods, edges):
    errs, warns = [], []
    for e in edges:
        a, b = e["from"], e["to"]
        where = f"{e['path']}:{e['line']}"
        ext = b[4:] if b.startswith("ext:") else None
        if is_engine(a):
            core = a == "engine.core" or a.startswith("engine.core.")
            r3d = a == "engine.render3d" or a.startswith("engine.render3d.")
            if ext is not None:
                ok = ext in STDLIB or ext in ENGINE_EXT_OK or (r3d and ext in RENDER3D_EXT_OK)
                if not ok:
                    errs.append(("E3" if ext in RENDER3D_EXT_OK else "E1", f"{a} imports external {ext!r}", where))
            elif b == "engine3d" or b.startswith("engine3d."):
                if not r3d:
                    errs.append(("E3", f"{a} imports {b} (only engine.render3d may)", where))
            elif not is_engine(b):
                errs.append(("E1", f"{a} imports game/legacy module {b}", where))
            elif core and not (b == "engine.core" or b.startswith("engine.core.") or b == "engine"):
                errs.append(("E2", f"{a} (core) imports {b}", where))
        elif is_engine(b) and not a.startswith("tools"):
            parts = b.split(".")
            private = any(x.startswith("_") for x in parts) or any(n.startswith("_") for n in e["names"])
            if len(parts) > 2 or private:
                errs.append(("E4", f"{a} imports non-public {b} {e['names']}", where))
        if (not A.MISSION_RE.match(a) and A.MISSION_RE.match(b) and a != "app"
                and e["path"].startswith("src/") and not is_engine(a)):
            warns.append(("W1", f"{a} -> {b}{' (lazy)' if e['lazy'] else ''}", where))
    # E5 cycles among engine modules (top-level edges)
    g = {}
    for e in edges:
        if is_engine(e["from"]) and is_engine(e["to"]) and not e["lazy"] and e["from"] != e["to"]:
            g.setdefault(e["from"], set()).add(e["to"])
    seen, stack, onstack = set(), [], set()

    def dfs(u):
        seen.add(u)
        stack.append(u)
        onstack.add(u)
        for v in sorted(g.get(u, ())):
            # a package importing its own submodules (facade) is not a cycle
            if v.startswith(u + "."):
                continue
            if v in onstack:
                cyc = stack[stack.index(v):] + [v]
                errs.append(("E5", "cycle: " + " -> ".join(cyc), ""))
            elif v not in seen:
                dfs(v)
        stack.pop()
        onstack.discard(u)
    for u in sorted(g):
        if u not in seen:
            dfs(u)
    return errs, warns


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--warn-only", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    mods, edges = collect()
    errs, warns = check(mods, edges)
    n_engine = sum(1 for m in mods if is_engine(m))
    for code, msg, where in errs:
        print(f"{code} {msg}  {where}")
    if a.verbose:
        for code, msg, where in warns:
            print(f"{code} {msg}  {where}")
    w1 = len(warns)
    trend = "=" if w1 == BASELINE_W1 else ("down" if w1 < BASELINE_W1 else "UP")
    if a.json:
        Path(a.json).write_text(json.dumps({"errors": errs, "warnings": warns}, indent=1), encoding="utf-8")
    summary = f"{len(errs)} engine violations, {n_engine} engine modules; W1 shared->mission {w1} (baseline {BASELINE_W1}, {trend})"
    if w1 > BASELINE_W1:
        print(f"W1 regressed: {w1} > baseline {BASELINE_W1}. New shared->mission imports were added.")
    ok = not errs and w1 <= BASELINE_W1
    print(("BOUNDARIES: OK (" if ok else "BOUNDARIES: FAIL (") + summary + ")")
    return 0 if ok or a.warn_only else 1


if __name__ == "__main__":
    sys.exit(main())
