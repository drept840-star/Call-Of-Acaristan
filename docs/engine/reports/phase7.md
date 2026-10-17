# Phase 7 report — data-driven levels and dialogue (RPE6)

Status: **DONE in the sandbox** (2026-10-15). Owner reference-machine
`ae_ci.py` re-run pending, as with every phase.

## What changed
- `engine.level` kernel: `ae.level/1` load/validate (tile layers as
  `list[str]`, objects/triggers/paths/lights/decor/procedural_decor/
  metadata) + Tiled `.tmj` importer. `engine.dialogue` kernel:
  `ae.dialogue/1` node model, static validator (dangling targets,
  unreachable nodes, unknown speakers, missing string keys, length box-fit
  proxy), and a `DialogueRunner` with a safe non-`eval` condition parser.
- 13 level files exported from the booted generators to
  `src/game/content/levels/*.level.json`; every mission grid now loads
  from data at import via `game.levels.grid(...)` (one-line wrap per
  grid), with `ACA_LEVEL_SRC=legacy` returning the generator grid
  untouched. Runtime contract unchanged: grids stay `list[str]`.
- The two conversation tables (M5 Maru, M4 liaison incl. the tone choice)
  exported to `src/game/content/dialogue/*.dlg.json` and converted back
  to legacy beat dicts at dialogue start by `game.dialogues.beats`
  (colours resolved game-side by speaker name).
  `ACA_DLG_SRC=legacy` returns the legacy tables untouched.
- CI: new `level` and `dialogue` rows in `tools/ae_ci.py` prove
  data == generators / data == legacy tables on every run.

## Exit criteria (master §7) vs evidence
- *Every mission loads levels from data* — 13/13 grids wrapped
  (M1, M2, M3 ×5, M4 ×2, M5 ×4); `tools/ae_level_check.py`:
  `AE LEVEL: OK (13 levels, data == legacy generators)`.
- *Static-layer pixel parity* — `AE GOLDEN: OK` (373/373),
  `AE LOOP: OK (7/7)`, `AE REPLAY: OK`, `SMOKE TEST: OK` with data as
  the default source (sandbox oracle sets, recaptured pre-phase).
- *Dialogue validator clean in CI* — `AE DIALOGUE: OK (2 dialogues
  valid, data == legacy tables)`; both new rows run inside `ae_ci.py`.
- *Replay parity* — above; no baseline re-recorded, no golden
  re-baselined.

## Scope notes / leftovers
- Timed ladders `_M4_STORY_BEATS` / `_M4_ARREST_BEATS` are frame-scheduled
  sequences, not conversations: they move with Phase 8 timelines
  (STATUS rescope note). Cutscene dialogue likewise stays Phase 8.
- Generators and legacy tables remain as env-selected fallbacks;
  deleting them is a later gated cleanup (ADR-018).
- B-034 (peel M1–M4 custom draws), B-035, B-036 remain open Phase 8+
  candidates; the camera-state flip (B-036) is untouched here.
- M4's generator returns rows as `list[str]` chars in some maps and
  `list[list[str]]` in others; exporter/checker/loader normalise — the
  data itself is always `list[str]`.

## Numbers
- Unit tests: 252 OK (6 kernel + 4 converter added this phase).
- API snapshot re-recorded deliberately for the two new kernels:
  66 modules, 451 public names, check OK. Boundaries OK (W1 48).
- Evidence: `docs/engine/evidence/phase7/final_gate.txt`.
