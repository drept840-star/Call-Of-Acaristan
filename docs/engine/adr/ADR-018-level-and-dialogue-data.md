# ADR-018: Levels and dialogue as validated data, generators as fallback

Status: accepted (Phase 7) · Date: 2026-10-15

Numbering note: ADR-003 fixed the data-format direction; this ADR records how the
mission grids and the conversation tables actually crossed over in Phase 7.

## Context
- Every mission grid was produced at import time by a generator or builder
  (M1 `MapBuilder`, M2 `world.py`, M3/M4/M5 `_generate_*_map()`), then consumed
  everywhere as `list[str]` — the standing runtime contract.
- Grid markers are per-mission grammar: `P` is the player spawn everywhere, but
  `E` is an enemy spawn only in M1 (in M3 grids `E` is a floor tile code).
  Marker extraction without a per-mission map produces garbage objects.
- Conversations were Python literals with game constants inlined
  (`{"speaker": "MARU", "color": C_MARU, "text": ...}`), consumed by two
  mission-local typewriter machines. Timed radio/arrest ladders
  (`_M4_STORY_BEATS`, `_M4_ARREST_BEATS`) are frame-scheduled event sequences,
  not conversations.

## Decision
1. **`ae.level/1`** (`engine.level`): JSON with tile layers as `list[str]`
   (one string per row), plus `objects`, `triggers`, `paths`, `lights`,
   `decor`, `procedural_decor`, `metadata`. `Level.grid()` returns a copy —
   callers rebind markers in their grid, the parsed level stays pristine.
   A Tiled `.tmj` importer (`engine.level.from_tiled`) maps gids to tile
   chars through a caller-supplied table.
2. **Export from the booted game, compare in CI.** `tools/ae_level_export.py`
   boots the full game (`ACA_LEVEL_SRC=legacy`), reads the final generator
   grids, and writes `src/game/content/levels/*.level.json` (13 levels).
   Object extraction uses explicit per-mission marker maps.
   `tools/ae_level_check.py` re-derives the generator grids and fails on any
   row difference; it runs in `ae_ci.py`.
3. **Runtime flip is one line per grid.** Mission modules wrap their
   generator call: `_levels.grid("m3.cell", _generate_map())`
   (`game.levels`). Data is the default; `ACA_LEVEL_SRC=legacy` returns the
   generator grid untouched (identity). Generators stay in code as the
   fallback until a later phase deletes them deliberately.
4. **`ae.dialogue/1`** (`engine.dialogue`): node graph (`speaker`, `text` /
   `text_key`, `next`, `choices`, `condition`, `effects`, `timing`) with a
   static validator (dangling targets, unreachable nodes, unknown speakers,
   missing string keys, length proxy for box fit) and a `DialogueRunner`
   whose conditions are data strings evaluated by a safe parser — never
   `eval`. New conversations run on the runner; legacy typewriters keep
   their machines this phase.
5. **Conversations cross over; timed ladders wait for timelines.** The two
   conversation tables (M5 Maru, M4 liaison incl. its tone choice) are
   exported to `src/game/content/dialogue/*.dlg.json` and converted back to
   legacy beat dicts at dialogue start by `game.dialogues.beats` (colours
   resolved game-side from the speaker name; the data names speakers only).
   `tools/ae_dialogue_check.py` proves validator-clean + beat-for-beat
   equality with the legacy tables in CI. `_M4_STORY_BEATS` /
   `_M4_ARREST_BEATS` are frame-scheduled sequences and move with the
   Phase 8 timeline work, not here.
6. **Choice follow-ups are nodes.** A choice option's spoken follow-up line
   is a target node; the converter pairs each label with its target's text,
   reproducing the legacy `options=[(label, follow)]` shape and the
   resolve-time splice exactly.

## Consequences
- Static-layer pixel parity is proven, not assumed: golden 373/373, loop
  7/7, replay OK with data as the default source.
- Data mode returns a fresh beat list per dialogue start, which also fixes
  a latent legacy quirk (M4's `_resolve_choice` splices into the shared
  module-level table under `ACA_DLG_SRC=legacy`; behaviour there is
  unchanged, one-shot per run).
- The generators and tables remain as env-selected fallbacks — deleting
  them is a later, separately gated cleanup, not a Phase 7 exit item.
- `engine.level` / `engine.dialogue` are game-agnostic kernels: the API
  snapshot was re-recorded deliberately (66 modules, 451 names).

## Alternatives considered
- Authoring levels directly in Tiled and dropping generators now: rejected —
  parity first; the importer exists so authoring can migrate incrementally.
- Storing speaker colours in the data: rejected — colours are game
  presentation constants; data stays presentation-free.
- Extracting the timed radio/arrest ladders as dialogue: rejected — they
  are schedules, and Phase 8 owns timelines.
