"""ae_narrow_star - rewrite ``from core.config import *`` into explicit imports (A-001, Phase 4).

    python tools/ae_narrow_star.py              # dry run: show the planned edit per file
    python tools/ae_narrow_star.py --apply      # rewrite every star site
    python tools/ae_narrow_star.py --apply --only m1/draw
    python tools/ae_narrow_star.py --verify     # 0 star sites expected after --apply

The name list per file comes from ``tools/ae_star_imports.py`` (pure AST: names
reachable through the star, not bound locally). Modules that ``core.config``
re-exports (``math``, ``pygame``, ``random``, ``os``, ``time`` ...) become direct
imports. Files that use **no** name still import ``core.config`` for its boot
side effect (B-007) until Phase 4 P4-1 moves the boot into ``App.boot``.

Files are backed up to ``build/ae_narrow_star/backup/`` before the first write,
so a revert is ``copy`` back - one edit per file, parity-neutral by construction.
"""
from __future__ import annotations

import argparse
import ast
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
BACKUP = ROOT / "build" / "ae_narrow_star" / "backup"
sys.path.insert(0, str(ROOT / "tools"))
import ae_star_imports as asi  # noqa: E402


def module_reexports(module_path: Path) -> set[str]:
    """Names core.config binds via plain imports (math, pygame, ... re-exported by the star)."""
    tree = ast.parse(module_path.read_text(encoding="utf-8", errors="replace"))
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname is None and type(node) is ast.Import:
                    out.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name != "*":
                    out.add(a.asname or a.name)
    return out


def build_lines(used: list[str], mod_names: set[str]) -> list[str]:
    direct = sorted(n for n in used if n in mod_names)
    from_cfg = [n for n in used if n not in mod_names]
    lines = [f"import {n}" for n in direct]
    if from_cfg:
        lines.append(f"from core.config import ({', '.join(from_cfg)})")
    elif not direct:
        lines = ["import core.config  # noqa: F401  boot side effect (A-001/B-007); removed in P4-1"]
    return lines


def edit_file(path: Path, lineno: int, new_lines: list[str], apply: bool) -> str:
    rel = path.relative_to(ROOT).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")
    old = lines[lineno - 1].strip()
    report = f"{rel}:{lineno}\n  - {old}\n  + " + "\n  + ".join(new_lines)
    if not apply:
        return report
    BACKUP.mkdir(parents=True, exist_ok=True)
    bpath = BACKUP / rel
    if not bpath.exists():
        bpath.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, bpath)
    lines[lineno - 1 : lineno] = new_lines
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return report


def stars_left(module: str) -> list[str]:
    return [p.relative_to(ROOT).as_posix() for p, _ in asi.star_users(module)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--module", default="core.config")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args(argv)

    mod_path = SRC / (a.module.replace(".", "/") + ".py")
    _exported, rows = asi.analyse(a.module)
    mod_names = module_reexports(mod_path)

    if a.verify:
        left = stars_left(a.module)
        for f in left:
            print(f"  star site left: {f}")
        print(f"AE NARROW: {'OK' if not left else 'FAIL'} ({len(left)} star sites left)")
        return 0 if not left else 1

    edited = 0
    for r in rows:
        if a.only and a.only not in r["file"]:
            continue
        new_lines = build_lines(r["used"], mod_names)
        print(edit_file(ROOT / r["file"], r["line"], new_lines, a.apply))
        if a.apply:
            edited += 1
    mode = "rewrote" if a.apply else "planned"
    print(f"AE NARROW: {mode} {edited} file(s)" if a.apply else "AE NARROW: dry run (pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
