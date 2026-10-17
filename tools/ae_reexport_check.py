"""ae_reexport_check - who pulls star-imported names THROUGH another module? (Phase 4, A-001)

    python tools/ae_reexport_check.py [--module core.config]

`tools/ae_narrow_star.py` replaces each `from core.config import *` with the explicit
names *that file* uses. Every other core.config export disappears from that module's
namespace - which is fine unless another file imports or attribute-accesses such a
name *through* it (a re-export chain). This pass finds those dependencies first, so
the narrowing is not blind outside the audit's own file-by-file view. Pure AST:
nothing is imported or executed.

Known limits (state them honestly): import-from chains and direct `module.attr`
accesses are covered for the star-using modules themselves; imports-of-imports
(G gets the name from H which got it from F) and `getattr(mod, name)` are not.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT / "tools"))
import ae_star_imports as asi  # noqa: E402


def module_name(p: Path) -> str:
    rel = p.relative_to(SRC).with_suffix("")
    parts = [q for q in rel.parts if q != "__init__"]
    return ".".join(parts)


def attr_path(node: ast.AST) -> list[str] | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return list(reversed(parts))
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--module", default="core.config")
    a = ap.parse_args(argv)
    mod_file = SRC / (a.module.replace(".", "/") + ".py")
    exported = asi.exported_names(mod_file)
    sites = asi.star_users(a.module)

    site_mods: dict[str, dict] = {}
    for p, _ in sites:
        used, bound = asi.global_names(p)
        used = set((used - bound - set(dir(builtins))) & exported)
        site_mods[module_name(p)] = {"path": p, "used": used, "bound": bound}

    dangers: set[tuple[str, int, str]] = set()
    scan_roots = (SRC, ROOT / "tools", ROOT / "tests")
    for root in scan_roots:
        for p in sorted(root.rglob("*.py")):
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            rel = p.relative_to(ROOT).as_posix()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module in site_mods:
                    info = site_mods[node.module]
                    if p == info["path"]:
                        continue
                    for al in node.names:
                        if al.name == "*":
                            continue
                        nm = al.asname or al.name
                        if nm in exported and nm not in info["used"] and nm not in info["bound"]:
                            dangers.add((rel, node.lineno, f"from {node.module} import {nm}"))
                elif isinstance(node, ast.Import):
                    for al in node.names:
                        m = al.name
                        if m not in site_mods:
                            continue
                        info = site_mods[m]
                        bound = al.asname or m.split(".")[0]
                        prefix = [bound] + m.split(".")[1:]
                        for sub in ast.walk(tree):
                            if not isinstance(sub, ast.Attribute):
                                continue
                            path = attr_path(sub)
                            if path and path[:-1] == prefix:
                                nm = path[-1]
                                if nm in exported and nm not in info["used"] and nm not in info["bound"]:
                                    dangers.add((rel, sub.lineno, f"{'.'.join(path)} ({m} re-exports it via the star)"))

    for rel, line, what in sorted(dangers):
        print(f"  RE-EXPORT RISK {rel}:{line}  {what}")
    n = len(dangers)
    print(f"AE REEXPORT: {'OK' if not n else 'FAIL'} ({n} risk(s) through {len(site_mods)} star-using module(s))")
    return 0 if not n else 1


if __name__ == "__main__":
    sys.exit(main())
