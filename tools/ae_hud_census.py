"""ae_hud_census - HUD duplication census across missions (Phase 4 prep).

    python tools/ae_hud_census.py [--md docs/engine/audit/hud_duplication.md]

Finds HUD-drawing functions (name contains ``hud`` or draws the classic HUD
vocabulary: AMMO/HP/HEALTH/OBJECTIVE/STAMINA ...) in ``src/missions/*/``,
``src/ui/hud.py`` and ``src/missions/walking_sim.py``; for each one records
size, draw/blit counts, the UI string literals it paints, the helpers it calls
(``ui.hud``/``hud.*``, fonts, ``draw_vignette`` ...) and then scores pairwise
similarity (Jaccard over helper calls + literals) between missions. Pure AST.
The output tells Phase 4 which widgets are already shared through ui.hud,
which are re-implemented per mission, and the order to lift them.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
HUD_WORDS = {"AMMO", "HP", "HEALTH", "OBJECTIVE", "OBJECTIVES", "STAMINA", "WEAPON", "RELOAD", "MAG", "KILLS",
             "TIME", "ARMOR", "MINIMAP", "WANTED", "ALERT", "HEAT", "NOISE", "OBJ", "SCORE", "GRENADE", "MOLOTOV"}
LITERAL_RE = re.compile(r"^[A-Z0-9 :/%.\-\[\]]{2,24}$")


def _calls(fn) -> set[str]:
    out = set()
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Attribute):
                base = f.value
                if isinstance(base, ast.Name):
                    out.add(f"{base.id}.{f.attr}")
                elif isinstance(base, ast.Attribute):
                    out.add(f"{base.attr}.{f.attr}")
                else:
                    out.add(f".{f.attr}")
            elif isinstance(f, ast.Name):
                out.add(f.id)
    return out


def _literals(fn) -> set[str]:
    out = set()
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and LITERAL_RE.match(sub.value.strip()):
            out.add(sub.value.strip())
    return out


def _counts(fn) -> tuple[int, int]:
    d = b = 0
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            v = sub.func.value
            if (isinstance(v, ast.Attribute) and v.attr in ("draw", "gfxdraw")) or \
                    (isinstance(v, ast.Name) and v.id in ("draw", "gfxdraw", "pd")):
                d += 1
            elif sub.func.attr in ("blit", "blits"):
                b += 1
    return d, b


def owner_of(rel: str) -> str:
    m = re.match(r"src/missions/(m\d)/", rel)
    if m:
        return m.group(1)
    if rel.startswith("src/ui/"):
        return "ui"
    if "walking_sim" in rel:
        return "walking_sim"
    return rel.split("/")[1]


def shared_names() -> set[str]:
    """Top-level defs/classes of ui/hud.py - the widgets that already exist once."""
    tree = ast.parse((SRC / "ui" / "hud.py").read_text(encoding="utf-8", errors="replace"))
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith("_")}


def scan() -> list[dict]:
    files = sorted(SRC.glob("missions/m*/*.py")) + [SRC / "ui" / "hud.py", SRC / "missions" / "walking_sim.py"]
    shared = shared_names()
    rows = []
    for p in files:
        if not p.exists():
            continue
        rel = p.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            lits = _literals(node)
            words = {w for lit in lits for w in re.split(r"[^A-Z]+", lit) if w}
            is_ui = rel == "src/ui/hud.py"
            calls = _calls(node)
            used_shared = sorted({c.split(".")[-1] for c in calls if c.split(".")[-1] in shared
                                  and (c in shared or c.startswith(("hud.", "_hud.", "ui_hud.")))})
            if (is_ui and node.name in shared and node.name.startswith("draw")) or (not is_ui and (
                    "hud" in node.name.lower() or len(words & HUD_WORDS) >= 2 or len(used_shared) >= 2)):
                d, b = _counts(node)
                rows.append({"file": rel, "owner": owner_of(rel), "func": node.name, "line": node.lineno,
                             "len": (node.end_lineno or node.lineno) - node.lineno + 1, "draw": d, "blit": b,
                             "literals": sorted(lits), "words": sorted(words & HUD_WORDS),
                             "shared": used_shared, "sig": calls | {"lit:" + x for x in lits}})
    rows.sort(key=lambda r: (r["owner"], r["file"], r["line"]))
    return rows


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a | b) else 0.0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--md")
    args = ap.parse_args(argv)
    rows = scan()
    by_owner: dict[str, list[dict]] = {}
    for r in rows:
        by_owner.setdefault(r["owner"], []).append(r)
    print(f"{len(rows)} HUD-ish functions in {len(by_owner)} owners")
    for o, rs in by_owner.items():
        print(f"  {o:12s} funcs={len(rs):3d} draw={sum(r['draw'] for r in rs):4d} blit={sum(r['blit'] for r in rs):4d} "
              f"shared ui.hud calls={sum(len(r['shared']) for r in rs)}")
    # pairwise: best match per mission HUD function against other owners
    pairs = []
    for a, b in combinations(rows, 2):
        if a["owner"] == b["owner"]:
            continue
        j = jaccard(a["sig"], b["sig"])
        if j >= 0.35:
            pairs.append((j, a, b))
    pairs.sort(key=lambda t: -t[0])
    word_owner: dict[str, set] = {}
    for r in rows:
        for w in r["words"]:
            word_owner.setdefault(w, set()).add(r["owner"])
    if args.md:
        L = ["# HUD duplication census (Phase 4 prep)", "",
             "Generated by `python tools/ae_hud_census.py --md docs/engine/audit/hud_duplication.md` (pure AST). "
             "A function counts as HUD if its name contains `hud`, it paints >= 2 words of the HUD vocabulary, or it hosts >= 2 shared widgets (M1 draws its HUD inline in `_game_draw_inner`) "
             "(AMMO, HP, OBJECTIVE, STAMINA, WEAPON, RELOAD, MINIMAP, ...). `ui.hud calls` = calls into the widgets that already exist "
             "once in `src/ui/hud.py` (`MiniMap`, `draw_objective_panel`, `draw_pinned_radio`, `draw_combat_reticle`, ...); the `ui` "
             "rows are that shared baseline. Phase 4 lifts the per-mission `_draw_*hud` bodies onto those widgets (data-driven slots), "
             "mission by mission, behind the golden gate.", "",
             "## Per owner", "", "| owner | HUD functions | draw calls | blits | lines | calls into ui.hud |", "|---|---:|---:|---:|---:|---:|"]
        for o, rs in by_owner.items():
            L.append(f"| {o} | {len(rs)} | {sum(r['draw'] for r in rs)} | {sum(r['blit'] for r in rs)} | "
                     f"{sum(r['len'] for r in rs)} | {sum(len(r['shared']) for r in rs)} |")
        L += ["", "## Widget vocabulary by owner (which missions paint which HUD words themselves)", "",
              "| word | owners |", "|---|---|"]
        for w, os_ in sorted(word_owner.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            L.append(f"| {w} | {', '.join(sorted(os_))} |")
        L += ["", "## Cross-owner look-alikes (Jaccard over helper calls + UI literals, >= 0.35)", "",
              "| similarity | A | B |", "|---:|---|---|"]
        for j, a, b in pairs[:40]:
            L.append(f"| {j:.2f} | `{a['file']}:{a['line']}` `{a['func']}` | `{b['file']}:{b['line']}` `{b['func']}` |")
        L += ["", "## Functions", "", "| owner | function | lines | draw | blit | HUD words | ui.hud calls |", "|---|---|---:|---:|---:|---|---|"]
        for r in rows:
            L.append(f"| {r['owner']} | `{r['file']}:{r['line']}` `{r['func']}` | {r['len']} | {r['draw']} | {r['blit']} | "
                     f"{', '.join(r['words'])} | {', '.join(r['shared'])} |")
        Path(args.md).write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
        print("wrote", args.md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
