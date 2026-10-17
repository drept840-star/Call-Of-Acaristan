"""RPE6 B-001: move legacy wall-clock reads onto the engine timebase.

Rewrites, in code tokens only (never comments or strings):
    pygame.time.get_ticks()  ->  _now_ms()
    time.time()              ->  _now_s()
and inserts ``from engine.core import now_ms as _now_ms, now_s as _now_s``
(only the names used) after the module's first top-level import block.

Proof per file: the rewritten module's AST, with the new calls mapped back and
the inserted import removed, must equal the original AST. Dry run by default;
``--apply`` writes. Excluded on purpose: src/engine, src/net, src/tools and
src/core/save_system.py (real timestamps / network / profiling keep the OS clock).
"""
from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
EXCLUDE_DIRS = ("engine", "net", "tools")
EXCLUDE_FILES = {SRC / "core" / "save_system.py"}
RE_TICKS = re.compile(r"pygame\s*\.\s*time\s*\.\s*get_ticks\s*\(\s*\)")
RE_TIME = re.compile(r"(?<![\w.])time\s*\.\s*time\s*\(\s*\)")


def _code_mask(src: str) -> list[list[bool]]:
    """Per line, per column: True where the character belongs to a comment/string."""
    lines = src.splitlines(keepends=True)
    mask = [[False] * (len(l) + 1) for l in lines]
    toks = tokenize.generate_tokens(io.StringIO(src).readline)
    for tok in toks:
        if tok.type not in (tokenize.COMMENT, tokenize.STRING):
            continue
        (sr, sc), (er, ec) = tok.start, tok.end
        for r in range(sr, er + 1):
            row = mask[r - 1]
            c0 = sc if r == sr else 0
            c1 = ec if r == er else len(row)
            for c in range(c0, min(c1, len(row))):
                row[c] = True
    return mask


def rewrite(src: str) -> tuple[str, int, int]:
    mask = _code_mask(src)
    out, n_ms, n_s = [], 0, 0
    for i, line in enumerate(src.splitlines(keepends=True)):
        def sub(rx, repl, text):
            res, pos, cnt = [], 0, 0
            for m in rx.finditer(text):
                if any(mask[i][c] for c in range(m.start(), m.end())):
                    continue
                res.append(text[pos:m.start()]); res.append(repl); pos = m.end(); cnt += 1
            res.append(text[pos:])
            return "".join(res), cnt
        line, a = sub(RE_TICKS, "_now_ms()", line)
        n_ms += a
        if a:  # columns shifted; refresh mask for this line conservatively
            mask[i] = [False] * (len(line) + 1)
            mask[i] = _code_mask("".join(out) + line)[i] if False else mask[i]
        line, b = sub(RE_TIME, "_now_s()", line)
        n_s += b
        out.append(line)
    return "".join(out), n_ms, n_s


def insert_import(src: str, names: list[str]) -> str:
    tree = ast.parse(src)
    last_end = None
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last_end = node.end_lineno
            # stop at the first import block (contiguous imports from the first one)
            nxt = tree.body[tree.body.index(node) + 1] if tree.body.index(node) + 1 < len(tree.body) else None
            if nxt is None or not isinstance(nxt, (ast.Import, ast.ImportFrom)):
                break
        elif last_end is not None:
            break
    if last_end is None:
        raise RuntimeError("no top-level import block")
    lines = src.splitlines(keepends=True)
    stmt = "from engine.core import " + ", ".join(f"{n} as _{n}" for n in names) + "  # RPE6 B-001 timebase\n"
    lines.insert(last_end, stmt)
    return "".join(lines)


class _Back(ast.NodeTransformer):
    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == "_now_ms" and not node.args:
            return ast.copy_location(ast.Call(
                func=ast.Attribute(value=ast.Attribute(value=ast.Name(id="pygame", ctx=ast.Load()),
                                                       attr="time", ctx=ast.Load()),
                                   attr="get_ticks", ctx=ast.Load()), args=[], keywords=[]), node)
        if isinstance(node.func, ast.Name) and node.func.id == "_now_s" and not node.args:
            return ast.copy_location(ast.Call(
                func=ast.Attribute(value=ast.Name(id="time", ctx=ast.Load()), attr="time", ctx=ast.Load()),
                args=[], keywords=[]), node)
        return node


def prove(original: str, rewritten: str) -> bool:
    new = ast.parse(rewritten)
    new.body = [n for n in new.body
                if not (isinstance(n, ast.ImportFrom) and n.module == "engine.core"
                        and all(a.name in ("now_ms", "now_s") for a in n.names))]
    new = _Back().visit(new)
    return ast.dump(ast.parse(original)) == ast.dump(new)


def targets():
    for p in sorted(SRC.rglob("*.py")):
        rel = p.relative_to(SRC).parts
        if rel[0] in EXCLUDE_DIRS or p in EXCLUDE_FILES:
            continue
        yield p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", nargs="*", help="restrict to these paths (relative to repo root)")
    a = ap.parse_args(argv)
    only = {ROOT / o for o in (a.only or [])}
    total_ms = total_s = files = 0
    bad = 0
    for p in targets():
        if only and p not in only:
            continue
        src = p.read_text(encoding="utf-8")
        new, n_ms, n_s = rewrite(src)
        if not (n_ms or n_s):
            continue
        names = [n for n, c in (("now_ms", n_ms), ("now_s", n_s)) if c]
        new = insert_import(new, names)
        ok = prove(src, new)
        files += 1; total_ms += n_ms; total_s += n_s
        print(f"{'OK ' if ok else 'BAD'} {p.relative_to(ROOT)}: get_ticks {n_ms}, time.time {n_s}")
        if not ok:
            bad += 1
            continue
        if a.apply:
            p.write_text(new, encoding="utf-8", newline="\n")
    print(f"AE MIGRATE TIME: {'FAIL' if bad else 'OK'} files={files} get_ticks={total_ms} time.time={total_s}"
          f"{' (applied)' if a.apply else ' (dry run)'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
