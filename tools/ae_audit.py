"""RPE6 Phase 0 audit: static census of src/ and tools/ (read-only, stdlib only).

Usage:  python tools/ae_audit.py [--out docs/engine/audit]

Writes:
  <out>/audit.json            machine-readable everything
  <out>/inventory.md          per-file lines / defs / line endings / encoding
  <out>/imports.md            package graph + shared->mission boundary edges
  <out>/state_census.md       every STATE.<field> read/write, by field and owner
  <out>/duplication.md        normalised-AST duplicate function groups
  <out>/draw_census.md        procedural draw calls per function (static count)
  <out>/cache_census.md       module-level cache dicts and their invalidation
  <out>/hazards.md            import side effects, unseeded random, direct loads,
                              wall-clock time, getattr attribute stuffing, mojibake
Never modifies source files. Deterministic output (sorted).
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
TOOLS = ROOT / "tools"
SKIP_DIRS = {"__pycache__", ".git", ".kilo", "node_modules"}

MISSION_RE = re.compile(r"^(missions(\.|$)|cutscenes\.m\d|art\.m\d|game\.art\.m\d)")
DRAW_FUNCS = {"line", "lines", "aaline", "aalines", "rect", "circle", "ellipse", "polygon",
              "arc", "pixel", "filled_circle", "filled_polygon", "aacircle", "aapolygon",
              "box", "hline", "vline", "filled_ellipse", "aaellipse", "trigon", "filled_trigon",
              "bezier", "textured_polygon", "pie"}
CACHE_NAME_RE = re.compile(r"(cache|CACHE|Cache|_static|_STATIC|SPRITES|_ROT$|_MEMO|_memo)")
RANDOM_FUNCS = {"random", "randint", "uniform", "choice", "choices", "shuffle", "sample",
                "randrange", "gauss", "seed", "triangular", "betavariate", "expovariate"}
MOJIBAKE_RE = re.compile("(\u00e2\u201d|\u00e2\u20ac|\u00c3[\u0080-\u00bf]|\ufffd)")


def iter_py(base: Path):
    for p in sorted(base.rglob("*.py")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def modname(p: Path) -> str:
    if p.is_relative_to(SRC):
        rel = p.relative_to(SRC).with_suffix("")
    else:
        rel = Path("tools") / p.relative_to(TOOLS).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) or "(root)"


def owner_of(mod: str) -> str:
    """Grouping key: mission id for mission code, else top package."""
    m = re.match(r"missions\.(m\d|arena|walking_sim|walking_attack3d)", mod)
    if m:
        return "mission:" + m.group(1)
    m = re.match(r"(cutscenes|art)\.(m\d)", mod)
    if m:
        return "mission:" + m.group(2)
    return mod.split(".")[0]


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


# ---------------------------------------------------------------- helpers
def dotted(node) -> str | None:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


class Norm(ast.NodeTransformer):
    """Anonymise identifiers (and optionally constants) for duplicate detection."""

    def __init__(self, consts: bool):
        self.consts = consts

    def visit_Name(self, n):
        return ast.copy_location(ast.Name(id="_", ctx=n.ctx), n)

    def visit_arg(self, n):
        return ast.copy_location(ast.arg(arg="_", annotation=None), n)

    def visit_FunctionDef(self, n):
        self.generic_visit(n)
        n.name = "_"
        n.decorator_list = []
        n.returns = None
        if n.body and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant) \
                and isinstance(n.body[0].value.value, str):
            n.body = n.body[1:] or [ast.Pass()]
        return n

    def visit_Constant(self, n):
        if self.consts:
            return ast.copy_location(ast.Constant(value=type(n.value).__name__), n)
        return n


def fn_hash(fn, consts: bool) -> str:
    import copy
    t = Norm(consts).visit(copy.deepcopy(fn))
    return hashlib.sha1(ast.dump(t, annotate_fields=False).encode()).hexdigest()[:16]


def stmt_count(fn) -> int:
    return sum(1 for n in ast.walk(fn) if isinstance(n, ast.stmt)) - 1


# ---------------------------------------------------------------- per-file pass
def analyse(p: Path, all_mods: set[str]):
    raw = p.read_bytes()
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    cr = raw.count(b"\r") - crlf
    info = {
        "path": rel(p), "module": modname(p), "owner": owner_of(modname(p)),
        "bytes": len(raw), "lines": raw.count(b"\n") + (0 if raw.endswith(b"\n") or not raw else 1),
        "crlf": crlf, "lf": lf, "cr": cr,
        "eol": "mixed" if (crlf and lf) or cr else ("crlf" if crlf else "lf"),
        "bom": raw.startswith(b"\xef\xbb\xbf"), "utf8": True, "mojibake_lines": [],
        "defs": 0, "classes": 0, "imports": [], "parse_error": None,
    }
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        info["utf8"] = False
        text = raw.decode("latin-1")
    for i, line in enumerate(text.splitlines(), 1):
        if MOJIBAKE_RE.search(line):
            info["mojibake_lines"].append(i)
    try:
        tree = ast.parse(text, filename=str(p))
    except SyntaxError as e:
        info["parse_error"] = str(e)
        return info, None, text
    return info, tree, text


def resolve_import(mod: str, is_pkg: bool, node, all_mods: set[str]) -> list[str]:
    out = []
    if isinstance(node, ast.Import):
        for a in node.names:
            out.append(a.name)
    else:
        base = node.module or ""
        if node.level:
            pkg = mod.split(".") if is_pkg else mod.split(".")[:-1]
            pkg = pkg[: len(pkg) - (node.level - 1)] if node.level > 1 else pkg
            base = ".".join([*pkg, base] if base else pkg)
        for a in node.names:
            cand = f"{base}.{a.name}" if base else a.name
            out.append(cand if cand in all_mods else base)
    # trim to the longest known module prefix
    res = []
    for name in out:
        parts = name.split(".")
        while parts and ".".join(parts) not in all_mods:
            parts.pop()
        res.append(".".join(parts) if parts else "ext:" + name.split(".")[0])
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/engine/audit")
    args = ap.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    files = list(iter_py(SRC)) + list(iter_py(TOOLS))
    all_mods = {modname(p) for p in files}
    inv, edges = [], []
    state = []                      # (field, rw, path, line, owner)
    fns = []                        # duplicate candidates
    draws = []                      # (count, qualname, path, line, owner, breakdown)
    caches = []
    hz = defaultdict(list)          # hazard kind -> [(path, line, detail)]

    for p in files:
        info, tree, text = analyse(p, all_mods)
        inv.append(info)
        if tree is None:
            continue
        mod, is_pkg = info["module"], p.name == "__init__.py"
        in_src = p.is_relative_to(SRC)
        top_level_nodes = set()
        for n in tree.body:
            for sub in ast.walk(n):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and sub is not n:
                    continue
                top_level_nodes.add(id(sub))
        func_nodes = set()
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for sub in ast.walk(n):
                    func_nodes.add(id(sub))
        info["defs"] = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in tree.body)
        info["classes"] = sum(isinstance(n, ast.ClassDef) for n in tree.body)

        # imports
        for n in ast.walk(tree):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                lazy = id(n) in func_nodes
                for tgt in resolve_import(mod, is_pkg, n, all_mods):
                    edges.append((mod, tgt, "lazy" if lazy else "top", rel(p), n.lineno))
                    if not lazy:
                        info["imports"].append(tgt)
        info["imports"] = sorted(set(info["imports"]))

        # STATE census (src + tools)
        for n in ast.walk(tree):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "STATE":
                rw = "write" if isinstance(n.ctx, (ast.Store, ast.Del)) else "read"
                state.append((n.attr, rw, rel(p), n.lineno, info["owner"]))
            elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Attribute) \
                    and isinstance(n.target.value, ast.Name) and n.target.value.id == "STATE":
                state.append((n.target.attr, "write", rel(p), n.lineno, info["owner"]))
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("getattr", "setattr", "hasattr") \
                    and n.args and isinstance(n.args[0], ast.Name) and n.args[0].id == "STATE" \
                    and len(n.args) > 1 and isinstance(n.args[1], ast.Constant):
                state.append((str(n.args[1].value), "write" if n.func.id == "setattr" else "read",
                              rel(p), n.lineno, info["owner"]))

        if not in_src:
            continue

        # functions: duplicates + draw census
        for n in ast.walk(tree):
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            sc = stmt_count(n)
            if sc >= 6:
                fns.append({"name": n.name, "path": rel(p), "line": n.lineno, "owner": info["owner"],
                            "stmts": sc, "h_exact": fn_hash(n, False), "h_struct": fn_hash(n, True)})
            br = Counter()
            for c in ast.walk(n):
                if isinstance(c, ast.Call):
                    d = dotted(c.func) or ""
                    last = d.rsplit(".", 1)[-1]
                    if (".draw." in "." + d + "." or ".gfxdraw." in "." + d + "." or d.startswith(("draw.", "gfxdraw."))) \
                            and last in DRAW_FUNCS:
                        br["draw." + last] += 1
                    elif last in ("blit", "blits", "fblits"):
                        br["blit"] += 1
                    elif last == "fill" and isinstance(c.func, ast.Attribute):
                        br["fill"] += 1
            if br:
                draws.append((sum(br.values()), n.name, rel(p), n.lineno, info["owner"], dict(br)))

        # module-level caches + hazards
        for n in tree.body:
            targets, value = [], None
            if isinstance(n, ast.Assign):
                targets, value = n.targets, n.value
            elif isinstance(n, ast.AnnAssign) and n.value is not None:
                targets, value = [n.target], n.value
            for t in targets:
                if isinstance(t, ast.Name) and CACHE_NAME_RE.search(t.id):
                    is_container = isinstance(value, (ast.Dict, ast.List, ast.Set)) or (
                        isinstance(value, ast.Call) and (dotted(value.func) or "").split(".")[-1]
                        in ("dict", "defaultdict", "OrderedDict", "list", "set", "WeakValueDictionary"))
                    if is_container:
                        name = t.id
                        clears = len(re.findall(rf"\b{re.escape(name)}\s*\.\s*(clear|pop|popitem)\s*\(", text)) + \
                            len(re.findall(rf"\b{re.escape(name)}\s*=\s*", text)) - 1
                        dels = len(re.findall(rf"del\s+{re.escape(name)}\s*\[", text))
                        caches.append({"name": name, "path": rel(p), "line": n.lineno, "owner": info["owner"],
                                       "kind": type(value).__name__ if not isinstance(value, ast.Call) else dotted(value.func),
                                       "invalidations": max(clears, 0) + dels})
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in n.decorator_list:
                    d = dotted(dec.func if isinstance(dec, ast.Call) else dec) or ""
                    if d.split(".")[-1] in ("lru_cache", "cache"):
                        caches.append({"name": n.name + "()", "path": rel(p), "line": n.lineno,
                                       "owner": info["owner"], "kind": d, "invalidations":
                                       len(re.findall(rf"\b{n.name}\.cache_clear\(", text))})
            if not isinstance(n, ast.Call):
                continue
            d = dotted(n.func) or ""
            top = id(n) in top_level_nodes and id(n) not in func_nodes
            line = n.lineno
            if top and d.endswith(("display.set_mode", "pygame.init", "mixer.init", "font.init",
                                   "image.load", "mixer.Sound", "font.Font", "font.SysFont", "Surface",
                                   "display.init")):
                hz["import_side_effect"].append((rel(p), line, d))
            if d.endswith("image.load") and not mod.startswith("engine.assets"):
                hz["direct_image_load"].append((rel(p), line, d))
            if d.endswith(("mixer.Sound", "mixer.music.load")):
                hz["direct_sound_load"].append((rel(p), line, d))
            if d.startswith("random.") and d.split(".")[-1] in RANDOM_FUNCS:
                hz["global_random"].append((rel(p), line, d))
            if d in ("time.time", "time.perf_counter", "time.monotonic", "pygame.time.get_ticks", "time.get_ticks"):
                hz["wall_clock"].append((rel(p), line, d))
            if d == "getattr" and len(n.args) == 3 and isinstance(n.args[1], ast.Constant) \
                    and isinstance(n.args[1].value, str) and n.args[1].value.startswith("_") \
                    and not (isinstance(n.args[0], ast.Name) and n.args[0].id in ("STATE", "sys", "os")):
                hz["getattr_private_default"].append((rel(p), line, n.args[1].value))
            if d.startswith(("pygame.draw.", "draw.")) and n.args and isinstance(n.args[0], ast.Name) \
                    and n.args[0].id in ("screen", "SCREEN") and owner_of(mod).startswith("mission:"):
                hz["mission_draws_on_screen"].append((rel(p), line, d))
        for i in info["mojibake_lines"]:
            hz["mojibake"].append((rel(p), i, "suspicious byte sequence"))

    # ------------------------------------------------------------ derived
    src_inv = [i for i in inv if i["path"].startswith("src/")]
    pkg_edges = Counter()
    boundary = []
    for a, b, kind, path, line in edges:
        if b.startswith("ext:") or not path.startswith("src/"):
            continue
        pa, pb = owner_of(a), owner_of(b)
        if pa != pb:
            pkg_edges[(pa, pb, kind)] += 1
        if not MISSION_RE.match(a) and MISSION_RE.match(b) and a != "app":
            boundary.append((a, b, kind, path, line))
    ext = Counter(b[4:] for a, b, k, path, l in edges if b.startswith("ext:") and path.startswith("src/"))

    dup_groups = []
    for key in ("h_exact", "h_struct"):
        g = defaultdict(list)
        for f in fns:
            g[f[key]].append(f)
        for h, members in g.items():
            if len(members) > 1 and len({m["path"] for m in members}) > 1:
                dup_groups.append({"kind": "exact" if key == "h_exact" else "structural", "hash": h,
                                   "stmts": members[0]["stmts"],
                                   "members": sorted(({k: m[k] for k in ("name", "path", "line", "owner")}
                                                      for m in members), key=lambda m: (m["path"], m["line"]))})
    exact_hashes = {g["hash"] for g in dup_groups if g["kind"] == "exact"}
    exact_sets = {tuple((m["path"], m["line"]) for m in g["members"]) for g in dup_groups if g["kind"] == "exact"}
    dup_groups = [g for g in dup_groups if g["kind"] == "exact"
                  or tuple((m["path"], m["line"]) for m in g["members"]) not in exact_sets]
    dup_groups.sort(key=lambda g: (g["kind"] != "exact", -g["stmts"] * len(g["members"]), g["hash"]))
    dup_stmts = sum(g["stmts"] * (len(g["members"]) - 1) for g in dup_groups if g["kind"] == "exact")

    field_rw = defaultdict(lambda: {"read": 0, "write": 0, "owners": Counter(), "writers": Counter()})
    for f, rw, path, line, owner in state:
        e = field_rw[f]
        e[rw] += 1
        e["owners"][owner] += 1
        if rw == "write":
            e["writers"][owner] += 1

    draws.sort(key=lambda d: (-d[0], d[2], d[3]))
    eol = Counter(i["eol"] for i in inv)

    summary = {
        "src_files": len(src_inv), "src_lines": sum(i["lines"] for i in src_inv),
        "tools_files": len(inv) - len(src_inv), "tools_lines": sum(i["lines"] for i in inv) - sum(i["lines"] for i in src_inv),
        "eol": dict(eol), "non_utf8": [i["path"] for i in inv if not i["utf8"]],
        "bom": [i["path"] for i in inv if i["bom"]], "parse_errors": [i["path"] for i in inv if i["parse_error"]],
        "boundary_edges": len(boundary), "boundary_edges_top": sum(1 for b in boundary if b[2] == "top"),
        "state_refs": len(state), "state_fields": len(field_rw),
        "state_writes": sum(1 for s in state if s[1] == "write"),
        "state_fields_mission_named": sorted(f for f in field_rw if re.match(r"(m\d|mission\d)", f)),
        "dup_groups_exact": sum(1 for g in dup_groups if g["kind"] == "exact"),
        "dup_groups_structural": sum(1 for g in dup_groups if g["kind"] == "structural"),
        "dup_redundant_stmts_exact": dup_stmts,
        "draw_functions": len(draws), "draw_calls_static": sum(d[0] for d in draws),
        "caches": len(caches), "caches_never_invalidated": sum(1 for c in caches if c["invalidations"] == 0),
        "hazards": {k: len(v) for k, v in sorted(hz.items())},
        "external_imports": dict(sorted(ext.items())),
    }

    data = {"summary": summary, "inventory": inv,
            "boundary_edges": [dict(zip(("from", "to", "kind", "path", "line"), b)) for b in sorted(boundary)],
            "package_edges": [{"from": a, "to": b, "kind": k, "n": n} for (a, b, k), n in sorted(pkg_edges.items())],
            "state": [dict(zip(("field", "rw", "path", "line", "owner"), s)) for s in sorted(state)],
            "duplicates": dup_groups, "draws": [dict(zip(("calls", "func", "path", "line", "owner", "by"), d)) for d in draws],
            "caches": sorted(caches, key=lambda c: (c["path"], c["line"])),
            "hazards": {k: [dict(zip(("path", "line", "detail"), x)) for x in sorted(v)] for k, v in sorted(hz.items())}}
    (out / "audit.json").write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8", newline="\n")

    # ------------------------------------------------------------ markdown
    def w(name, lines):
        (out / name).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    hdr = ["<!-- generated by tools/ae_audit.py; do not edit by hand -->", ""]
    L = hdr + ["# Inventory", "", f"src: {summary['src_files']} files / {summary['src_lines']} lines; "
               f"tools: {summary['tools_files']} files / {summary['tools_lines']} lines.", "",
               "| path | lines | top-level defs | classes | eol | utf8 | top-level imports (internal) |", "|---|---:|---:|---:|---|---|---|"]
    for i in sorted(inv, key=lambda i: i["path"]):
        imps = ", ".join(x for x in i["imports"] if not x.startswith("ext:"))
        L.append(f"| `{i['path']}` | {i['lines']} | {i['defs']} | {i['classes']} | {i['eol']} | "
                 f"{'yes' if i['utf8'] else '**no**'}{' BOM' if i['bom'] else ''} | {imps} |")
    w("inventory.md", L)

    L = hdr + ["# Import graph", "", "## Package-level edges (src only)", "", "| from | to | top | lazy |", "|---|---|---:|---:|"]
    pairs = defaultdict(lambda: [0, 0])
    for (a, b, k), n in pkg_edges.items():
        pairs[(a, b)][0 if k == "top" else 1] += n
    for (a, b), (t, lz) in sorted(pairs.items()):
        L.append(f"| {a} | {b} | {t} | {lz} |")
    L += ["", f"## Shared → mission edges (boundary violations to remove): {len(boundary)} "
          f"({summary['boundary_edges_top']} top-level)", "", "| from | to | kind | where |", "|---|---|---|---|"]
    for a, b, k, path, line in sorted(boundary):
        L.append(f"| {a} | {b} | {k} | `{path}:{line}` |")
    L += ["", "## External imports (src)", ""] + [f"- `{k}`: {v}" for k, v in sorted(ext.items())]
    w("imports.md", L)

    L = hdr + ["# Global-state census (`STATE.<field>`)", "",
               f"{summary['state_refs']} references ({summary['state_writes']} writes) to {summary['state_fields']} fields.", "",
               "## By field", "", "| field | reads | writes | owners (refs) | writers |", "|---|---:|---:|---|---|"]
    for f, e in sorted(field_rw.items(), key=lambda kv: (-(kv[1]['read'] + kv[1]['write']), kv[0])):
        L.append(f"| `{f}` | {e['read']} | {e['write']} | " + ", ".join(f"{o} {n}" for o, n in e["owners"].most_common())
                 + " | " + ", ".join(f"{o} {n}" for o, n in e["writers"].most_common()) + " |")
    L += ["", "## By owner", "", "| owner | refs | writes | distinct fields |", "|---|---:|---:|---:|"]
    by_owner = defaultdict(lambda: [0, 0, set()])
    for f, rw, path, line, owner in state:
        by_owner[owner][0] += 1
        by_owner[owner][1] += rw == "write"
        by_owner[owner][2].add(f)
    for o, (n, wr, fs) in sorted(by_owner.items(), key=lambda kv: -kv[1][0]):
        L.append(f"| {o} | {n} | {wr} | {len(fs)} |")
    L += ["", "## Every reference (field, rw, file:line)", "", "<details><summary>expand</summary>", ""]
    for f, rw, path, line, owner in sorted(state):
        L.append(f"- `{f}` {rw} `{path}:{line}`")
    L += ["", "</details>"]
    w("state_census.md", L)

    L = hdr + ["# Duplication census (normalised-AST hashing)", "",
               "exact = identical after renaming every identifier; structural = identical after also erasing constants.",
               f"Exact groups: {summary['dup_groups_exact']} (≈{dup_stmts} redundant statements). "
               f"Structural-only groups: {summary['dup_groups_structural']}.", ""]
    for g in dup_groups:
        L.append(f"### {g['kind']} · {g['stmts']} stmts · ×{len(g['members'])}")
        for m in g["members"]:
            L.append(f"- `{m['name']}` — `{m['path']}:{m['line']}` ({m['owner']})")
        L.append("")
    w("duplication.md", L)

    L = hdr + ["# Draw census (static count of draw/blit/fill call sites per function)", "",
               f"{summary['draw_functions']} functions, {summary['draw_calls_static']} call sites. "
               "Static count — loops multiply real per-frame calls; use tools/m5_draw_audit.py for runtime counts.", "",
               "| # | calls | function | where | owner | breakdown |", "|---:|---:|---|---|---|---|"]
    for i, (n, fn, path, line, owner, br) in enumerate(draws[:150], 1):
        L.append(f"| {i} | {n} | `{fn}` | `{path}:{line}` | {owner} | " + ", ".join(f"{k} {v}" for k, v in sorted(br.items())) + " |")
    L += ["", "## Totals by owner", "", "| owner | functions | call sites |", "|---|---:|---:|"]
    to = defaultdict(lambda: [0, 0])
    for n, fn, path, line, owner, br in draws:
        to[owner][0] += 1
        to[owner][1] += n
    for o, (a, b) in sorted(to.items(), key=lambda kv: -kv[1][1]):
        L.append(f"| {o} | {a} | {b} |")
    w("draw_census.md", L)

    L = hdr + ["# Cache census (module-level cache containers and memoised functions)", "",
               f"{summary['caches']} caches; {summary['caches_never_invalidated']} have no clear()/pop()/rebind/del anywhere "
               "in their module (never invalidated). Key shape must be read per site; see the AUDIT.md notes.", "",
               "| cache | where | owner | kind | invalidation sites |", "|---|---|---|---|---:|"]
    for c in sorted(caches, key=lambda c: (c["path"], c["line"])):
        L.append(f"| `{c['name']}` | `{c['path']}:{c['line']}` | {c['owner']} | {c['kind']} | {c['invalidations'] or '**0**'} |")
    w("cache_census.md", L)

    L = hdr + ["# Hazards (rule violations to retire in later phases)", ""]
    for k, v in sorted(hz.items()):
        L += [f"## {k} — {len(v)}", ""]
        for path, line, d in sorted(v)[:400]:
            L.append(f"- `{path}:{line}` {d}")
        if len(v) > 400:
            L.append(f"- … {len(v) - 400} more (see audit.json)")
        L.append("")
    w("hazards.md", L)

    print(json.dumps(summary, indent=1, sort_keys=True, ensure_ascii=False))
    print("AE AUDIT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
