"""ae_global_names - unresolved global references in src (Phase 4 gate, A-001).

    python tools/ae_global_names.py [--root src]

Every global a file *reads* must be bound at that file's module scope, come in
through a star import, or be a builtin. This reports files that read a global
nobody binds - i.e. a guaranteed NameError on that path. It is the scope-correct
companion of `ae_star_imports.py` (symtable; B-019) and the regression gate for
the Phase 4 narrowing (`tools/ae_narrow_star.py`): after the `*` rewrite, every
name the file actually needs must be on an explicit import line.

Limits (honest): files with *relative* star imports (`from .map import *`, the
package facades) are skipped - their names cannot be resolved statically; names
reached through exec()/globals() are invisible to any static pass.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import symtable
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT / "tools"))
import ae_star_imports as asi  # noqa: E402

MODULE_DUNDERS = {
    "__name__", "__file__", "__doc__", "__package__", "__spec__", "__loader__",
    "__builtins__", "__path__", "__annotations__", "__all__", "__dict__",
    "__module__", "__qualname__", "__class__", "__debug__",
}

# Not modules: applied patch fragments / notes that live under src/. Each is
# reported as skipped so the "OK" stays honest.
KNOWN_NONMODULES = {
    "src/cutscenes/m3cell_balaceanu_patch.py": "applied patch fragment (content lives in m3cell.py; imported nowhere)",
}


def _star_exports(mod: str | None) -> set[str]:
    if not mod:
        return set()
    p = SRC / (mod.replace(".", "/") + ".py")
    if not p.exists():
        p = SRC / mod.replace(".", "/") / "__init__.py"
        if not p.exists():
            return set()
    try:
        return asi.exported_names(p)
    except Exception:  # noqa: BLE001 - unparsable star target: keep it conservative
        return set()


def check_file(p: Path) -> tuple[list[str], bool]:
    """(missing globals, skipped-for-relative-star)."""
    src = p.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src)
    star_names: set[str] = set()
    relative_star = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
            if node.level:
                relative_star = True
            else:
                star_names |= _star_exports(node.module)
    if relative_star:
        return [], True
    st = symtable.symtable(src, str(p), "exec")
    bound = {s.get_name() for s in st.get_symbols()
             if s.is_assigned() or s.is_imported() or s.is_namespace() or s.is_annotated()}
    refs: set[str] = set()
    injected: set[str] = set()

    def walk(t, top: bool = False):
        for s in t.get_symbols():
            name = s.get_name()
            if s.is_referenced() and s.is_global() and not s.is_local():
                refs.add(name)
            # `global X` + assignment/import inside a function: X exists at runtime
            # after that function runs (app.py's event state, walking_sim's minimap).
            if not top and s.is_global() and (s.is_assigned() or s.is_imported()):
                injected.add(name)
        for child in t.get_children():
            walk(child)

    walk(st, top=True)
    missing = [n for n in sorted(refs - bound - injected - star_names - set(dir(builtins)) - MODULE_DUNDERS)
               if not (n.startswith("__") and n.endswith("__"))]
    return missing, False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(SRC))
    a = ap.parse_args(argv)
    root = Path(a.root)
    bad = skipped = syntax = 0
    n = 0
    known: list[str] = []
    for p in sorted(root.rglob("*.py")):
        n += 1
        rel_p = p.relative_to(root.parent).as_posix()
        if rel_p in KNOWN_NONMODULES:
            known.append(rel_p)
            continue
        try:
            missing, rel = check_file(p)
        except SyntaxError:
            syntax += 1
            continue
        if rel:
            skipped += 1
            continue
        if missing:
            bad += 1
            print(f"  UNRESOLVED {rel_p}: {', '.join(missing)}")
    for name in known:
        print(f"  skipped (known non-module): {name} - {KNOWN_NONMODULES[name]}")
    print(f"AE GLOBAL NAMES: {'OK' if not bad else 'FAIL'} "
          f"({n} files, {bad} with unresolved globals, {skipped} skipped for relative stars"
          + (f", {len(known)} known non-modules" if known else "")
          + (f", {syntax} unparsable" if syntax else "") + ")")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
