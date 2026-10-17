"""ae_text_check.py - string-table validation and text fit (RPE6 Phase 4, 6.13).

    python tools/ae_text_check.py                     # check, exit 1 on failure
    python tools/ae_text_check.py --md docs/engine/audit/text_migration.md
    python tools/ae_text_check.py --strict            # unused keys also fail

What it proves, in order:

1. **Table hygiene** - ``game/content/strings/en.json`` parses, has no duplicate
   keys and every value is a string.
2. **Key coverage** - every static ``T("key")`` call in ``src/`` exists in the
   table (missing -> FAIL); table keys nobody calls are reported (warn, or
   FAIL with ``--strict``); dynamically built keys (f-strings) are reported so
   nothing is skipped silently.
3. **Placeholders** - a value with ``{placeholders}`` must be called with
   exactly those keyword arguments; a mismatch shows the engine's ``[[key]]``
   marker at runtime, so it is a FAIL here (see tests/unit/test_engine_text.py).
4. **Text fit** - every value that has a known widget slot must fit that slat's
   box at the shipped font size (``engine.text.layout.fits``), with
   placeholders filled by two digits. This is the phase-exit "text-fit
   validation passes for every string in every widget it appears in".

``--md PATH`` additionally writes the migration inventory: per module, the
number of ``T()`` calls vs. player-facing literals still rendered directly
(``font.render("...")``), so the remaining work is measured rather than guessed.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path
from string import Formatter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TABLE_PATH = SRC / "game" / "content" / "strings" / "en.json"

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, str(SRC))

T_NAMES_HINT = {"T", "_T"}


def t_bindings(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Resolve what this module bound to ``engine.text.T``.

    Returns (local names bound by ``from engine.text import T [as X]``, dotted
    module prefixes bound to ``engine.text`` such as ``text`` / ``t`` /
    ``engine.text``). Matching by name alone is wrong: ``src/tools/trailer_bot.py``
    has a local ``T = _tc64`` tile helper.
    """
    names: set[str] = set()
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
            if mod == "engine.text" or mod.startswith("engine.text."):
                for a in node.names:
                    if a.name == "T":
                        names.add(a.asname or a.name)
                    else:
                        mods.add(a.asname or a.name)      # e.g. from engine.text import strings
            elif mod == "engine":
                for a in node.names:
                    if a.name == "text":
                        mods.add(a.asname or a.name)      # from engine import text [as t]
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "engine.text" or a.name.startswith("engine.text."):
                    mods.add(a.asname or a.name)          # import engine.text [as t]
    return names, mods


def is_T_call(node: ast.Call, names: set[str], mods: set[str]) -> bool:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id in names
    if isinstance(f, ast.Attribute):
        dotted = ast.unparse(f)
        return dotted.endswith(".T") and dotted[:-2] in mods
    return False

# key -> the box the string is drawn into (font attribute in core.config)
FIT_SLOTS = (
    ("hud.hp", "font_terminal_small", 20, None,
     "health_bar: label gap before the bar (20px inset)"),
    ("hud.hostiles", "font_terminal_small", 160, None,
     "hostiles: 180x26 box, text at +10"),
    ("hud.objective", "font_prompt", 600, None,
     "objective banner: 620px panel minus 2x10 pad"),
    ("hud.reloading", "font_terminal_small", 86, None,
     "weapon panel: readout column (246 - 160)"),
    ("hud.mags", "font_terminal_small", 86, None,
     "weapon panel: readout column (246 - 160)"),
    ("hud.minimap_north", "font_terminal_small", 12, None,
     "minimap: the N compass marker"),
    ("hud.bottles", "font_terminal_small", 126, None,
     "bottle strip: right column (246 - 120)"),
    ("hud.molotovs", "font_terminal_small", 126, None,
     "bottle strip: right column (246 - 120)"),
    ("cutscene.space_to_continue", "font_terminal_small", 420, None,
     "dialogue box: right-aligned prompt (box ~880px wide)"),
    ("cutscene.analyzing_file", "font_terminal_small", 420, None,
     "dialogue box: right-aligned prompt (box ~880px wide)"),
    ("hud.hold_transmitter", "font_terminal_small", 296, None,
     "M4 hold clock: plate 320 wide, text at +12"),
    ("hud.hold_timer", "font_terminal_small", 56, None,
     "M4 hold clock: right column after the bar"),
    ("hud.convoy_inbound", "font_terminal_small", 276, None,
     "M5 plate 340 wide: title row minus the pips column"),
    ("hud.convoy_on_site", "font_terminal_small", 276, None,
     "M5 plate 340 wide: title row minus the pips column"),
    ("hud.raid_title", "font_terminal_small", 276, None,
     "M5 plate 340 wide: title row minus the pips column"),
    ("hud.clock", "font_terminal_small", 52, None,
     "M5 plate 340 wide: right column (x + w - 12, right-aligned)"),
    ("hud.now", "font_terminal_small", 52, None,
     "M5 plate 340 wide: right column (x + w - 12, right-aligned)"),
    ("hud.heat", "font_terminal_small", 40, None,
     "M5 plate: HEAT label left of the 5 pips (10px gap)"),
    ("hud.vis_spotted", "font_terminal_small", 156, None,
     "M5 visibility chip: 180 wide at x=20, text at x=44"),
    ("hud.vis_lit", "font_terminal_small", 156, None,
     "M5 visibility chip: 180 wide at x=20, text at x=44"),
    ("hud.vis_shadow", "font_terminal_small", 156, None,
     "M5 visibility chip: 180 wide at x=20, text at x=44"),
)


def py_files() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def load_table(path: Path):
    """(table, duplicate_keys, non_string_keys)."""
    pairs: list[tuple[str, str]] = []

    def hook(items):
        pairs.extend(items)
        return dict(items)

    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=hook)
    seen: dict[str, int] = {}
    for k, _ in pairs:
        seen[k] = seen.get(k, 0) + 1
    dupes = sorted(k for k, n in seen.items() if n > 1)
    bad = sorted(k for k, v in data.items() if not isinstance(v, str))
    return data, dupes, bad


def scan_calls():
    """[(key, relpath, line, kwargs)] for static T() calls; plus dynamic keys.

    Only calls this module resolved to ``engine.text.T`` count; a same-named
    local function is ignored (and reported separately as a hint if it takes a
    string literal).
    """
    static, dynamic, t_like = [], [], []
    for p in py_files():
        rel = p.relative_to(ROOT).as_posix()
        tree = ast.parse(p.read_text(encoding="utf-8"))
        names, mods = t_bindings(tree)
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            if not is_T_call(n, names, mods):
                f = n.func
                if (isinstance(f, ast.Name) and f.id in T_NAMES_HINT and n.args
                        and isinstance(n.args[0], ast.Constant)
                        and isinstance(n.args[0].value, str)):
                    t_like.append((rel, n.lineno, f.id))
                continue
            if not n.args:
                continue
            first = n.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                kwargs = {kw.arg for kw in n.keywords if kw.arg}
                static.append((first.value, rel, n.lineno, kwargs))
            else:
                dynamic.append((rel, n.lineno))
    return static, dynamic, t_like


def placeholders(entry: str) -> set[str]:
    """Names of ``{placeholders}``; raises ValueError on a malformed template."""
    return {name for _, name, _, _ in Formatter().parse(entry) if name is not None}


def scan_render_literals():
    """Per module: (T calls, directly rendered string literals)."""
    counts: dict[str, list[int]] = {}
    for p in py_files():
        rel = p.relative_to(ROOT).as_posix()
        tree = ast.parse(p.read_text(encoding="utf-8"))
        names, mods = t_bindings(tree)
        t_calls = renders = 0
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            if is_T_call(n, names, mods):
                t_calls += 1
                continue
            if (isinstance(n.func, ast.Attribute) and n.func.attr == "render"
                    and n.args and isinstance(n.args[0], (ast.Constant, ast.JoinedStr))):
                first = n.args[0]
                if isinstance(first, ast.Constant) and not isinstance(first.value, str):
                    continue          # render(3, ...) is not text
                renders += 1
        if t_calls or renders:
            counts[rel] = [t_calls, renders]
    return counts


def check_fit(table, failures) -> tuple[int, list[str]]:
    import core.config as config          # pylint: disable=import-error,import-outside-toplevel
    from engine.text.layout import fits   # pylint: disable=import-outside-toplevel
    lines = []
    checked = 0
    for key, font_attr, width, height, note in FIT_SLOTS:
        entry = table.get(key)
        if entry is None:
            continue
        try:
            filled = entry.format(**{name: "99" for name in placeholders(entry)})
        except (KeyError, IndexError, ValueError):
            try:
                # Numeric format specs (``{s:02d}``) reject a str sample.
                filled = entry.format(**{name: 99 for name in placeholders(entry)})
            except (KeyError, IndexError, ValueError):
                continue                   # placeholder problems are reported separately
        font = getattr(config, font_attr)
        checked += 1
        if not fits(font, filled, width, height):
            failures.append(f"FIT {key!r} does not fit {width}x{height} in {note}")
            lines.append(f"- FAIL `{key}` {filled!r} in {width}x{height}px ({note})")
        else:
            lines.append(f"- ok `{key}` {filled!r} in {width}x{height}px ({note})")
    return checked, lines


def write_inventory(path: Path, table, static, dynamic, missing, unused, t_like) -> None:
    counts = scan_render_literals()
    rows = sorted(counts.items(), key=lambda kv: (-kv[1][1], kv[0]))
    total_t = sum(v[0] for v in counts.values())
    total_r = sum(v[1] for v in counts.values())
    out = [
        "# Text migration inventory (Phase 4)",
        "",
        "Generated by `python tools/ae_text_check.py --md docs/engine/audit/text_migration.md` (pure AST).",
        "`T()` calls = strings already going through the table; `render literals` = player-facing strings",
        "still rendered directly by `font.render(\"...\")` / f-strings. The table holds "
        f"{len(table)} key(s); {total_t} call(s) and {total_r} direct literal(s) are left in `src/`.",
        "",
        "## Per module",
        "",
        "| module | T() calls | render literals |",
        "|---|---:|---:|",
    ]
    out += [f"| `{rel}` | {t} | {r} |" for rel, (t, r) in rows]
    out += ["", "## Table state", ""]
    out += [f"- keys in `src/game/content/strings/en.json`: {len(table)}",
            f"- missing keys (called, not in the table): {len(missing)}",
            f"- unused keys (in the table, never called): {len(unused)}",
            f"- dynamic keys (f-string, not statically checkable): {len(dynamic)}",
            f"- T-like calls that are not `engine.text.T` (local helpers): {len(t_like)}", ""]
    if missing:
        out += ["### Missing", ""] + [f"- `{k}` ({rel}:{line})" for k, rel, line, _ in missing] + [""]
    if unused:
        out += ["### Unused", ""] + [f"- `{k}`" for k in unused] + [""]
    if dynamic:
        out += ["### Dynamic", ""] + [f"- `{rel}:{line}`" for rel, line in dynamic] + [""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", metavar="PATH", help="also write the migration inventory")
    ap.add_argument("--strict", action="store_true", help="unused keys fail the check")
    args = ap.parse_args(argv)

    failures: list[str] = []
    warnings: list[str] = []

    if not TABLE_PATH.exists():
        print(f"AE TEXT: FAIL (string table missing: {TABLE_PATH.relative_to(ROOT)})")
        return 1
    table, dupes, bad = load_table(TABLE_PATH)
    if dupes:
        failures.append(f"duplicate table keys: {', '.join(dupes)}")
    if bad:
        failures.append(f"non-string table values: {', '.join(bad)}")

    static, dynamic, t_like = scan_calls()
    used: dict[str, list[tuple[str, int, set[str]]]] = {}
    for key, rel, line, kwargs in static:
        used.setdefault(key, []).append((rel, line, kwargs))
    missing = [(k, r, l, kw) for k, r, l, kw in static if k not in table]

    for key, rel, line, kwargs in missing:
        failures.append(f"missing key {key!r} at {rel}:{line}")
    for key in sorted(used):
        entry = table.get(key)
        if entry is None:
            continue
        try:
            need = placeholders(entry)
        except ValueError as exc:
            failures.append(f"bad template for {key!r}: {exc}")
            continue
        for rel, line, kwargs in used[key]:
            short = need - kwargs
            if short:
                failures.append(
                    f"{key!r} needs {sorted(short)} at {rel}:{line} (engine shows the marker)")
    unused = sorted(set(table) - set(used))
    if args.strict and unused:
        failures.append(f"unused keys: {', '.join(unused)}")
    elif unused:
        warnings.append(f"unused keys: {', '.join(unused)}")
    if dynamic:
        warnings.append(f"no static key: {len(dynamic)} dynamic T() key(s) "
                        f"(first: {dynamic[0][0]}:{dynamic[0][1]})")
    if t_like:
        warnings.append(f"{len(t_like)} T-like call(s) are not engine.text.T "
                        f"(first: {t_like[0][0]}:{t_like[0][1]})")

    fit_checked, _fit_lines = check_fit(table, failures)
    if args.md:
        write_inventory(ROOT / args.md, table, static, dynamic, missing, unused, t_like)

    for w in warnings:
        print(f"  warn: {w}")
    for f in failures:
        print(f"  FAIL: {f}")
    detail = (f"table {len(table)} keys, {len(missing)} missing, {len(unused)} unused, "
              f"{fit_checked} fit slots")
    if failures:
        print(f"AE TEXT: FAIL ({len(failures)} problem(s); {detail})")
        return 1
    print(f"AE TEXT: OK ({detail})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
