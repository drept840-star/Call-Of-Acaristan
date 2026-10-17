"""RPE6 Phase 0 item 7: line-ending / encoding normalisation with proofs (R14, B-003).

    python tools/ae_normalize.py [--apply] [--mojibake] [--report PATH]

Dry run by default. With --apply it rewrites, in place:
  * every text file (no NUL in the first 8 KB, valid UTF-8) under the repo:
    CRLF -> LF, UTF-8 BOM removed. ``*.bat``, ``*.cmd``, ``*.ps1`` keep CRLF
    (Windows shells); ``build/``, ``__pycache__``, ``.git``, ``node_modules``
    and ``.venv`` are skipped. ``tests/`` baselines are already LF (verified).
  * with --mojibake, Python files additionally get double-encoded UTF-8
    (``â”€`` for ``─``, ``Â°`` for ``°`` ...) repaired, but ONLY inside COMMENT
    tokens and docstrings; string literals that execute are never touched.
Proof, per Python file: ``ast.dump`` before == after (comments are not in
the AST; for docstrings the "before" dump is compared after applying the
same repair to its docstring constants, so any other difference fails).
Non-Python files must equal ``before.replace(CRLF, LF)`` minus the BOM.
Nothing is written if any proof fails. Prints ``AE NORMALIZE: OK`` / ``FAIL``.
"""
from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__", "build", "node_modules", ".venv", ".arena"}
KEEP_CRLF = {".bat", ".cmd", ".ps1"}
BOM = b"\xef\xbb\xbf"
# A UTF-8 multibyte lead byte read as cp1252/latin-1: Â/Ã/â followed by a
# continuation byte shown as a cp1252 symbol or a C1 control char.
MOJI = re.compile(r"[\u00c2\u00c3\u00e2][\u0080-\u00bf\u2013\u2014\u2018\u2019\u201a\u201c\u201d\u201e\u2020"
                  r"\u2021\u2022\u20ac\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192\u02c6\u02dc\u2026"
                  r"\u2030\u2039\u203a\u2122]")


def is_text(data: bytes) -> bool:
    if b"\0" in data[:8192]:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def demojibake(s: str) -> str:
    """Undo UTF-8 bytes that were decoded as cp1252 (with latin-1 for the C1 gaps)."""
    if not MOJI.search(s):
        return s
    out = bytearray()
    try:
        for ch in s:
            try:
                out += ch.encode("cp1252")
            except UnicodeEncodeError:
                if "\u0080" <= ch <= "\u009f":
                    out += ch.encode("latin-1")
                else:
                    out += ch.encode("utf-8")      # genuine non-cp1252 text, keep
        fixed = out.decode("utf-8")
    except UnicodeDecodeError:
        return s
    return fixed if not MOJI.search(fixed) or fixed != s else s


def repair_python(text: str) -> tuple[str, int, int]:
    """Repair mojibake in comments and docstrings. Returns (new_text, n_comments, n_docstrings)."""
    toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    tree = ast.parse(text)
    doc_spans = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                c = body[0].value
                doc_spans.add((c.lineno, c.col_offset))
    lines = text.split("\n")
    # Work on absolute offsets so multi-line tokens are replaced exactly.
    starts = [0]
    for ln in lines[:-1]:
        starts.append(starts[-1] + len(ln) + 1)
    edits = []
    nc = nd = 0
    for t in toks:
        if t.type == tokenize.COMMENT and MOJI.search(t.string):
            fixed = demojibake(t.string)
            if fixed != t.string:
                edits.append((t.start, t.end, fixed))
                nc += 1
        elif t.type == tokenize.STRING and MOJI.search(t.string) and t.start in doc_spans:
            fixed = demojibake(t.string)
            if fixed != t.string:
                edits.append((t.start, t.end, fixed))
                nd += 1
    for (sl, sc), (el, ec), fixed in sorted(edits, reverse=True):
        a = starts[sl - 1] + sc
        b = starts[el - 1] + ec
        text = text[:a] + fixed + text[b:]
    return text, nc, nd


def dump_with_repaired_docstrings(tree: ast.AST) -> str:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                body[0].value.value = demojibake(body[0].value.value)
    return ast.dump(tree)


def iter_files():
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        yield p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--mojibake", action="store_true", help="also repair double-encoded comments/docstrings in .py")
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    rows, failures, plan = [], [], []
    stats = {"scanned": 0, "text": 0, "crlf": 0, "mixed": 0, "bom": 0, "keep_crlf": 0,
             "py_changed": 0, "moji_comments": 0, "moji_docstrings": 0, "changed": 0}
    for p in iter_files():
        stats["scanned"] += 1
        raw = p.read_bytes()
        if not is_text(raw):
            continue
        stats["text"] += 1
        rel = p.relative_to(ROOT).as_posix()
        if p.suffix.lower() in KEEP_CRLF:
            stats["keep_crlf"] += 1
            continue
        had_bom = raw.startswith(BOM)
        n_crlf = raw.count(b"\r\n")
        n_lf = raw.count(b"\n") - n_crlf
        if had_bom:
            stats["bom"] += 1
        if n_crlf and n_lf:
            stats["mixed"] += 1
        elif n_crlf:
            stats["crlf"] += 1
        body = raw[len(BOM):] if had_bom else raw
        new = body.replace(b"\r\n", b"\n")
        expected = new
        nc = nd = 0
        if p.suffix == ".py":
            text = new.decode("utf-8")
            before_tree = ast.parse(text)
            if a.mojibake:
                text, nc, nd = repair_python(text)
            new = text.encode("utf-8")
            try:
                after_dump = ast.dump(ast.parse(text))
            except SyntaxError as e:
                failures.append((rel, f"repaired source does not parse: {e}"))
                continue
            before_dump = dump_with_repaired_docstrings(before_tree) if nd else ast.dump(before_tree)
            if before_dump != after_dump:
                failures.append((rel, "AST changed"))
                continue
            if nc or nd:
                stats["moji_comments"] += nc
                stats["moji_docstrings"] += nd
        elif new != expected:
            failures.append((rel, "non-python content changed beyond CRLF/BOM"))
            continue
        if new != raw:
            stats["changed"] += 1
            if p.suffix == ".py":
                stats["py_changed"] += 1
            kind = []
            if had_bom:
                kind.append("bom")
            if n_crlf:
                kind.append("mixed" if n_lf else "crlf")
            if nc or nd:
                kind.append(f"mojibake c{nc}/d{nd}")
            rows.append((rel, "+".join(kind)))
            plan.append((p, new))
    for rel, why in failures:
        print(f"FAIL {rel}: {why}")
    if not failures and a.apply:
        for p, new in plan:
            p.write_bytes(new)
    summary = (f"scanned {stats['scanned']} files, {stats['text']} text; crlf {stats['crlf']}, mixed {stats['mixed']}, "
               f"bom {stats['bom']}, kept-crlf {stats['keep_crlf']}; changed {stats['changed']} "
               f"({stats['py_changed']} .py); mojibake repaired: {stats['moji_comments']} comments, "
               f"{stats['moji_docstrings']} docstrings")
    report = [f"# ae_normalize {'APPLY' if a.apply else 'DRY RUN'}", summary, ""]
    report += [f"{kind:28s} {rel}" for rel, kind in rows]
    if a.report:
        Path(a.report).parent.mkdir(parents=True, exist_ok=True)
        Path(a.report).write_text("\n".join(report) + "\n", encoding="utf-8", newline="\n")
    print(summary)
    ok = not failures
    print(f"AE NORMALIZE: {'OK' if ok else 'FAIL'} ({'applied' if a.apply and ok else 'dry run'})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
