# Subsystem: `engine.text` (Phase 4)

Shipped: 2026-10-15 · Report: `docs/engine/reports/phase4.md` · Inventory: `docs/engine/audit/text_migration.md`

## Contract

```python
from engine.text import T          # game code; widgets use the same import
T("hud.hp")                        # "HP"
T("hud.hostiles", n=3)             # "HOSTILES: 3"
```

- **`T(key, **kwargs)`** looks the key up in the shipped table, runs `str.format(**kwargs)` and returns the
  string. Braces in table text must be escaped (`{{`/`}}`); placeholders are `{name}`.
- **Missing key** → returns a visible marker `[[key]]` and warns once per key (a missing string must be
  loud but must never crash a frame).
- **Unfilled placeholder** → same policy: marker + warn-once, never raises.
- The table is loaded lazily on first use (`load_strings()`); `reset_strings()` exists for tests.
- Faces and measurement live beside it: `load_face(name, px)`, `measure`, `fits`, wrapping
  (`engine.text.layout`); `src/core/font_coverage.py` reports glyph coverage per face.
- Engine purity: `engine.text` imports pygame + stdlib only; the *table file* is game content.

## The table

- Location: `src/game/content/strings/en.json` (sorted keys, 2-space indent, UTF-8, LF, `ensure_ascii=False`).
- **488 keys** as of Phase 4 exit; key shape = `<surface>.<slug>`, surface from the file
  (`os`, `mp`, `sys`, `hud`, `app`, `menu`, `arena`, `ws`, `m1`…`m5`, `cs` for cutscenes).
- Duplicate texts across surfaces get separate keys on purpose; a codemod collision gets `_2`, `_3`
  suffixes rather than a silent overwrite.

## The `_T` alias rule (important)

Mission modules already use `T` for the tile size — `tram_wreck.py:22` does
`from core.config import TILE_SIZE as T`, and `m3/m4/m5` draw/quarter modules do `T = TILE_SIZE`. A plain
`from engine.text import T` at the top of such a file is silently *shadowed* later in the module (the first
golden run after the string migration died exactly there: `TypeError: 'int' object is not callable`).

Rule: **any binding of the name `T` in a module forces the alias `_T`** (`from engine.text import T as _T`,
with a comment). The codemod detects assignments, import aliases, `for`/`with`/walrus targets, `global T`
and `def T`/`class T`; new imports are *always* inserted as `_T` to keep the trap closed.

## Fit validation

- `tools/ae_text_check.py` (CI row "string tables + text fit") owns `FIT_SLOTS`: `(key, font_attr, width,
  height, note)` for every string that lands in a fixed column (widget readouts, plate titles, chip text,
  the minimap `N`, the dialogue prompt).
- Placeholder sampling: `"99"` for each placeholder; if the format spec rejects a str (`{s:02d}`), the tool
  retries with the int `99`, so numeric entries are checked rather than skipped.
- Self-fitting widgets (prompt, objective banner, dialogue box) do not need slots — they wrap/shrink
  themselves; see `subsystems/ui.md`.
- `--md docs/engine/audit/text_migration.md` regenerates the inventory (per-module `T()` calls vs direct
  render literals). At exit: 518 calls, 3 direct literals — the developer console input echo plus the 2
  `PROVOCATEURS` sites inside the frozen m5 inspect-art closure (they move with the B-024 decision).

## Tooling

- `build/ae_reconcile/migrate_strings.py` — the one-shot codemod that moved 480 `X.render(<literal>)` sites
  into the table (plain literals + f-strings with simple `{Name}` fields; anything else was skipped and
  hand-migrated). Two traps it documents in code: **AST column offsets are UTF-8 byte offsets** (slicing a
  `str` by them eats a comma per non-ASCII char earlier in the line) and the `T`-binding rule above.
  Backups of every rewritten file: `build/ae_reconcile/strbak/`.
- The codemod is *build* tooling, not a CI tool: it runs once per migration batch, never in a gate.

## How to add a string

1. Use `_T("surface.slug")` (or `_T("surface.slug", n=value)`) at the call site — never a raw literal.
2. Add the entry to `src/game/content/strings/en.json` (sorted, braces escaped).
3. If the string renders into a fixed column, add a `FIT_SLOTS` row in `tools/ae_text_check.py`.
4. `python tools/ae_text_check.py` (must print `AE TEXT: OK`) and one golden run.

## What Phase 7 owns

The dialogue half: curated key names + speaker attribution for the `cutscene.*` and mission line strings
(the text is already table-backed; only the naming/attribution layer is Phase 7's), and any locale
negotiation beyond the single shipped table.
