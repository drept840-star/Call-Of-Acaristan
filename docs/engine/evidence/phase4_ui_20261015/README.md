# Phase 4 / engine.ui + HUD dedup — evidence (2026-10-15)

Scope of this increment: the `engine.ui` kernel, five standard widgets in
`engine.ui.std`, the A-009 shim in `src/ui/hud.py` (one theme built from
`core.config`), and the **M4 + M5 HUD migration** that deletes the duplicated
panel bodies (census Jaccard 0.70 pair).

Everything landed behind the standing gates: golden (373 shots), loop (7
segments × 600 frames), unit tests, API snapshot, bake check.

## What moved (all bodies verbatim + injected names only)

| Widget (engine.ui.std) | Legacy home | Injection |
|---|---|---|
| `objective_banner` | `src/ui/hud.py: draw_objective_panel` (+`OBJECTIVE_PANEL_*` consts) | `Theme.font_prompt/c_white/c_krap_blue/width/letter_h` |
| `minimap.MiniMap` | `src/ui/hud.py: class MiniMap` (380 lines, mechanical move) | `Theme.width/height/font_terminal_small`; `__init__(..., *, theme=None)`; hud.py keeps a **subclass shim** pinning the game theme |
| `health_bar` | M4 `_draw_m4_hud` + M5 `_draw_hud` HP blocks (identical) | `panel_bg(w,h)` callable (`entities.art_cache.get_panel_bg`) |
| `weapon_panel` (MagIcons) | M4 + M5 weapon/magazine blocks (identical) | `WeaponInfo.from_state(state)`, `panel_bg`, `mag_icon(...)` callback (each mission keeps its baked sprite painter) |
| `hostiles` | M4 + M5 hostiles box (count rule stays mission-side) | — |

`src/ui/hud.py` keeps every legacy name; missions and `app.py`/`arena_view`
call sites were not touched (A-009, see `docs/engine/ADAPTERS.md`).

## Boundary lint (first full CI after the move: red → green)

The first `tools/ae_ci.py` run on this increment failed one row — `boundary lint
(enforce engine)` — with 11 violations introduced here (B-021):

* **E1**: `engine.text.fonts` read the TTFs with `fontTools`; engine code may
  import stdlib + pygame + numpy only. The reader moved to
  `src/core/font_coverage.py` (smoke check + unit tests read it there);
  `engine.text` keeps `FACES`, `PLEX_ONLY`, `font_dir`, `load_face` and the pure
  `missing_glyphs` verdict.
* **E4**: call sites imported `engine.text.fonts` / `engine.ui.std.<widget>`;
  outside the engine only the 2-level `engine.<pkg>` is public. `engine.ui` now
  re-exports the five widget modules and every caller uses
  `from engine.ui import health_bar`.

Red log kept: `build/ae_reconcile/ae_ci_ui.log` (CI-RC=1). `BOUNDARIES: OK
(0 engine violations, 46 engine modules)`; green re-run:
`build/ae_reconcile/ae_ci_ui_final.log` (12 rows: compileall, boundaries,
imports, hygiene, global names, api 44/239, units 163, bake, smoke, golden
373/373, replay 5/5, loop 7/7).

The mechanical MiniMap move rewrote exactly 4 references
(`WIDTH`×2 → `self._theme.width`, `HEIGHT` → `self._theme.height`,
`font_terminal_small` → `self._theme.font_terminal_small`) — full unified diff:
`build/ae_reconcile/minimap_move_diff.txt`; script:
`build/ae_reconcile/move_minimap.py`.

## Census before → after (`tools/ae_hud_census.py`)

| owner | before (draw/blit) | after | note |
|---|---|---|---|
| m4 | 7 / 10, 100 lines | **0 / 0** | HUD is now data + widget calls |
| m5 | 10 / 12, 114 lines | **3 / 2** | the 3/2 are M5's own status plate + raid timer |
| ui | 42 / 36 | 40 / 34 | objective panel + minimap moved out of `hud.py` into `engine.ui.std` |
| m1/m2/m3 | unchanged | unchanged | next migrations (M3 → M2 → M1) |

Regenerated audit: `docs/engine/audit/hud_duplication.md`.

## Gates (logs in `build/ae_reconcile/`)

| Gate | Result |
|---|---|
| golden (after each move) | `ui1_golden.log`, `ui2_golden.log`, `ui3_golden.log` — **373/373, 0 failures** |
| loop (m1–m5 + boot + walk, 600 frames each) | `ui3_loop.log` — **7/7** (M4 and M5 HUD frames included) |
| unit tests | `unit_ui.log` — **163 tests OK** (`tests/unit/test_engine_ui.py` +11) |
| API snapshot | re-recorded **44 modules / 239 public names** (was 36/221); B-020 fixed the comparator |
| bake check | `AE BAKE: OK` — m4 pack re-baked twice (once after the HUD migration, once after the E4 import re-pointing, which also touches a declared dep): **58/58 rendered files byte-identical** both times, only `.bakeinfo.json` source hashes updated |
| compileall | clean |

## How to reproduce

```
.venv\Scripts\python.exe tools\ae_hud_census.py --md docs\engine\audit\hud_duplication.md
.venv\Scripts\python.exe tools\ae_golden.py verify      # 373/373
.venv\Scripts\python.exe tools\ae_loop.py check         # 7/7
.venv\Scripts\python.exe -m unittest discover -s tests/unit -t .
.venv\Scripts\python.exe tools\ae_api_snapshot.py check
.venv\Scripts\python.exe tools\ae_bake.py --check --lint
```

## Increments 2-4 (2026-10-15) — DialogueBox, HUD strips, string tables, crosshair, plate chrome

Landed after the increment above, same gates:

* **`engine.ui.std.dialogue_box`** — the cutscene dialogue box (131 lines)
  moved verbatim out of `src/cutscenes/engine.py`; `draw_dialogue_box` /
  `reset_dialogue_slide` stay as A-009 shims and the slide state moved into the
  widget (the `cutscenes` facade live view `_dialogue_box_slide` is repointed at
  `engine.ui.std.dialogue_box`, locked by `tests/unit/test_engine_shims.py`).
  `Theme` gained `speaker_colors` + `speaker_accent()` (game values:
  `core.config.SPEAKER_COLORS`). Splice script + diff:
  `build/ae_reconcile/migrate_dialogue_box.py`, `dialogue_box_diff.txt`.
* **M1 + M2 HP strips and hostiles boxes on the shared widgets.**
  `health_bar.draw` gained geometry arguments (`bb`, `inset`, `panel`,
  `panel_off`, `label_dy`; defaults are the M2–M5 look) so M1's compact strip
  (160×14 bar at `HEIGHT-50`, label above, plain `_m1_hp_panel` backdrop) and
  M2's `unified_w` panel (296 with the OS-12) are the same widget; both
  hostiles boxes were already byte-identical to `hostiles.draw`. Script + diff:
  `build/ae_reconcile/migrate_m1m2_hud.py`, `m1m2_hud_diff.txt`.
* **String tables started.** `game/content/strings/en.json` (7 keys) is the
  single source for the widget strings (`hud.hp`, `hud.hostiles`,
  `hud.objective`, `hud.reloading`, `hud.mags`, `cutscene.space_to_continue`,
  `cutscene.analyzing_file`). New gate **`tools/ae_text_check.py`** (CI row 6)
  validates table hygiene, key coverage, placeholder/`str.format` match, and the
  fit of every table string in its widget box (7 fit slots, shipped fonts);
  `docs/engine/audit/text_migration.md` is the migration inventory
  (501 player-facing literals still rendered directly — the measured remainder).
* **`engine.ui.std.bottle_hud`** — M1 + M2 drew the same 246×36 molotov strip
  (M2 even imported M1's `_draw_molotov_icon`); the strip is one widget now
  (each mission passes its own `panel_bg` — M1 alpha 140 via
  `_m1_panel_140`/`get_panel_bg`, M2 the cached default 150 — and the icon
  painter; strings `hud.molotovs`, `hud.bottles`). Script + diff:
  `build/ae_reconcile/migrate_bottle_hud.py`, `bottle_hud_diff.txt`.
* **`engine.ui.std.crosshair`** — the combat reticle shape was inlined
  byte-identically in M1, M2 and walking_sim and lived a fourth time in
  `ui.hud.draw_combat_reticle`; the colour-blind palette chain had five copies
  (`_crosshair_color`, the combat reticle, M1, M2, walking_sim). Shape +
  palette moved to the widget (`color_for(mode, default=...)`); the missions
  keep their own gating (settings, scene/stage checks) and call it with the
  same numbers. Script + diff: `build/ae_reconcile/migrate_crosshair.py`,
  `crosshair_diff.txt`.
* **Plate chrome + the first mission-side strings (increment 4).** The M4 hold
  clock and the M5 status plate built the same dark-glass + steel-rim surface
  inline; `art_cache.get_plate_bg(w, h)` is the shared cached factory now
  (`tests/unit/test_art_cache.py` locks it to the legacy pixels) and M5's
  baked-frame fallback stopped duplicating `_plate_text`. Eleven HUD labels
  moved into the table (hold clock, convoy/raid plate, clock + HEAT, visibility
  chip) — the first *mission* callers of `T()`, imported as `_T` because all
  three modules rebind `T = TILE_SIZE` (m4/draw.py:1087, m5/draw.py:100,
  quarter.py:42; the alias is commented at each import). The windows question
  was closed honestly: `ui/system.py:809` and `arena_view.py:1504` share only
  the fill colour, not the chrome. Table is now 20 keys / 20 fit slots (the
  chip strings measure 145/144 px in a 156 px column).

### Red first, green after (B-022)

The M1 splice removed `hb_y`, which the ammo panel 11 lines below still read
(`ammo_x, ammo_y = 30, hb_y - 96` — a hidden coupling between two HUD blocks).
Golden caught it on the first verify (`ERROR gp.m1_seq.ERROR: NameError(...)`,
1 error / 370 shots; loop m1 rc=1). Fixed in the same pass
(`(HEIGHT - 50) - 96` + comment), then golden **373/373** and loop **7/7**.
Red/green logs: `build/ae_reconcile/m1m2_golden.log` / `m1m2_golden2.log`,
`m1m2_loop.log` / `m1m2_loop2.log`.

Two more reds, both caught by the gates of the increment that introduced them:

* **Fit slots that were narrower than the real column.** The first chip slot
  said 136 px (`180 - 44`), forgetting the chip sits at x=20 while the text is
  at x=44 → the real column is 156 px (`EXPOSED - IN LIGHT` is 145 px). The
  gate refused to pass on a wrong number, which is the point of the gate.
* **`T` is `TILE_SIZE` in three mission modules.** `from engine.text import T`
  in `m4/draw.py`, `m5/draw.py` and `quarter.py` is rebound later in each file
  (`T = TILE_SIZE`), so the first golden run died with
  `TypeError: 'int' object is not callable` at `quarter.py:489`. Fixed by
  importing `T as _T` with a comment; the text tool resolves the alias
  (`0 missing, 0 unused`).

### Findings (B-023, B-024)

* **B-023 (fixed).** `_safe_convert_alpha` checked `display.get_init()` but not
  whether a mode was set, so the headless `test_art_cache` run hit exactly the
  crash the guard exists to prevent. Guard fixed; production path unchanged.
* **B-024 (open, owner decision).** A fresh `ae_bake --pack m5` is
  deterministic but differs from the committed art in `inspect_art_0/5` and
  `tram_wreck_0`; `ae_bake --check` cannot see it because the m5 pack deps do
  not cover `missions.m5.inspect_art` / `inspect_art_street` / `tram_wreck`.
  Regenerating moves the golden `gp.m5.quarter_mid` (309 px), so it is a
  visual + re-baseline decision: the committed files were restored and the
  fresh copies kept under `build/ae_reconcile/baked_m5_fresh{,_2}/`.

### Gates (increments 2 + 3)

| Gate | Result |
|---|---|
| golden | `db_golden.log`, `m1m2_golden2.log`, `bottle_golden.log`, `ch_golden.log` — **373/373, 0 failures, 0 errors** |
| loop | `db_loop.log`, `m1m2_loop2.log`, `bottle_loop.log`, `ch_loop.log` — **7/7 segments × 600 frames** |
| units | **175 tests** (dialogue box, shim live view, shipped strings, bottle strip, crosshair, plate chrome) |
| API snapshot | re-recorded **47 modules / 255 public names** (each widget addition was an explicit `record`) |
| bake check | m1 + m2 + m4 packs re-baked after every HUD edit: byte-identical (only `.bakeinfo.json`); m5 drift is **B-024** (owner decision) |
| string gate | `AE TEXT: OK (table 20 keys, 0 missing, 0 unused, 20 fit slots)`; inventory: 21 `T()` calls, 498 direct literals left |
| census | m1 47 draw/47 blit → **37/40**, m2 38/28 → **32/21**, m3 1/4, m4 0/0, m5 3/2, ui 40/34 → **32/34** |
| full CI | `build/ae_reconcile/ae_ci_plate.log` — **13 rows OK** |

## Increment 5 (2026-10-15) — Prompt widget + the complete string migration

* **`engine.ui.std.prompt`** — the world-anchored interaction tag. Body moved
  verbatim from `missions.m3.draw._draw_prompt_tag` (its look is the widget
  default: fallback font, shrink guard, viewport clamp, icon slot) and
  `missions.m5.decor.draw_prompt` migrated onto it (chrome knobs
  `fill=(10,12,18,200)`, `rim=(200,170,90,220)`, `radius=5`, `pad=(6,3)`,
  `clamp=False`; `[E] look` / `[E] look again` moved into the table as
  `m5.look` / `m5.look_again`). Font-only widget (the two callers resolve faces
  from different modules) — same documented exception as `crosshair`'s colour
  policy. Unit proof: `tests/unit/test_engine_ui.py::PromptTests` (draws,
  clamps, and verifies `clamp=False` really leaves the old position). Named
  widgets closed without extraction, documented in `subsystems/ui.md`: NameTag
  (arena `_draw_name_tag`, single copy) and StealthIndicator (M5 visibility
  chip, single copy, strings already migrated); Menu/Toast are not on the
  master Work list.
* **String migration, all 480 convertible `X.render(<literal>)` sites.** One-shot
  codemod `build/ae_reconcile/migrate_strings.py` (reuses the
  `tools/ae_text_check.py` detection rule: attribute call named `render`, first
  arg a str constant or f-string) — plain literals get braces escaped, simple
  `{Name}` f-strings become `{name}` entries with the names passed as kwargs.
  Keys are `<surface>.<slug>` (`os`, `mp`, `sys`, `hud`, `app`, `menu`,
  `arena`, `ws`, `m1`…`m4`, cutscenes by file stem); collisions suffix
  `_2`, `_3`. Every rewritten file backed up in `build/ae_reconcile/strbak/`.
  The 16 remaining f-strings (calls/subscripts/nested specs) were hand-migrated
  the same shape — e.g. `f"[E] Search {stash['label']}"` →
  `_T("ws.search_label", label=stash["label"])`, progress readouts pass a
  pre-formatted `pct` (`"{03d}".format(int(upload_t * 100))`). The dev-console
  input echo (`src/core/console.py:196`) stays a literal on purpose.
* **Result**: table **488 keys**, **518** `T()` calls, **21** fit slots,
  inventory **3 direct render literals left** in all of `src/` — the dev console
  echo plus the 2 `PROVOCATEURS` sites inside the frozen m5 inspect-art
  closure, reverted because migrating them changes a source hash the m5 bake
  manifest tracks (the string half of the **B-024** decision;
  `docs/engine/audit/text_migration.md` regenerated by `--md`).
* **Red first, green after (B-025).** Two codemod traps each cost a red cycle
  before landing: AST column offsets are UTF-8 **byte** offsets (a `·` earlier
  in `app.py:972`'s line ate a comma in 9 modules → `compileall` red), and
  `tram_wreck.py` binds `T` via `from core.config import TILE_SIZE as T` (not
  an assignment) so the inserted `from engine.text import T` shadowed the tile
  size (`TypeError` in the m5 finale-audio loader + the m3 import test).
  Fixed in the same pass (byte slicing + every-binding detection + `_T` always
  for new imports), then: compileall green, `AE TEXT: OK`, units 176, golden
  373/373, loop 7/7.
* **Red first, green after (B-026).** Six hand-migrated format strings used the
  zero-padding shorthand without the colon (`"{02d}".format(x)`), which Python
  reads as a positional index — the smoke test's settings draw raised
  `IndexError: Replacement index 2 out of range` at `src/ui/system.py:534`
  (golden/loop/units do not cover those draw paths). All 7 sites now use
  explicit specs (`"{:02d}"`, `"{:03d}"`, `"{:02}"`) and a src scan
  (`FormatShorthandTests` in `tests/unit/test_engine_text.py`) guards the
  class; smoke is green.

### Gates (increment 5)

| Gate | Result |
|---|---|
| golden | `str_golden.log` — **373/373, 0 failures, 0 errors** (never re-baselined in Phase 4) |
| loop | `str_loop.log` — **7/7 segments × 600 frames** |
| units | **176 tests** (`OK`; `units_str2.log` / `units_str3.log`) |
| API snapshot | re-recorded **48 modules / 258 public names** (`engine.ui.std.prompt` added) |
| bake check | m1/m2/m3/m4 packs re-baked after the HUD/string edits: **byte-identical** (only `.bakeinfo.json`); m5 not re-baked (B-024) |
| string gate | `AE TEXT: OK (table 488 keys, 0 missing, 0 unused, 21 fit slots)`; inventory 518 calls / **3** direct literals |
| census | unchanged at exit: m1 37/40, m2 32/21, m3 1/4, m4 0/0, m5 3/2, ui 32/34 |
| full CI | `build/ae_reconcile/ae_ci_phase4d.log` — **13 rows OK** (compileall → loop); an earlier run of the same tree, `ae_ci_phase4c.log`, had 2 false-red rows while another gate run + a game process shared the machine (B-027) |

### CI run history (B-027)

The full gate was run four times while Phase 4 landed: `ae_ci_phase4.log` (run a — bake
stale m5 + the smoke format bug: both real, both fixed), `ae_ci_phase4b.log` (run b —
smoke still red from the same format bug), `ae_ci_phase4c.log` (run c — **2 false-red
rows** on an unchanged tree: golden `cut.m3.archives_transition_shots.01_m3_archives_ingame_join.t25/t50/t75`
and loop `boot`/`m1` "rng state first differs at frame 290", while a game process wrote the real
`save_data.json` at 20:59:54 inside the run's window and another gate run's fast rows were
written at 21:05-21:06; the same commands were green standalone and in a
smoke→golden→replay→loop subset re-run), and **`ae_ci_phase4d.log` (run d — 13/13 rows OK)**.
B-027 keeps the row timings, log mtimes and process evidence; treat a red row from a loaded
machine as suspect rather than a tree change.

## Remaining after Phase 4 (tracked in `docs/engine/STATUS.md`)

1. **B-024 (owner decision)**: regenerate the 3 stale m5 artifacts + re-baseline
   `gp.m5.quarter_mid` + add `missions.m5.inspect_art`, `inspect_art_street`,
   `tram_wreck` to the m5 pack deps — or confirm the committed art and add only
   the deps.
2. The remaining `src/ui/hud.py` widgets (desk note, notebook inspection, safe
   keypad) — they need the `STATE`/`SETTINGS`/audio context injected, and the
   PAUSED / NOTEBOOK_INSPECT scene lift (ADR-014) precedes them; the boot
   refactor (B-007 / A-001 removal) is the tail.
3. Phase 7 dialogue naming: the `cutscene.*` / mission-line keys are mechanical
   slugs; the dialogue half may want curated names + speaker attribution (the
   text is already table-backed).
