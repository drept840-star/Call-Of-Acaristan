# ADR-021: Game-side dev tools, data-only editors, Mission 0, and the W1 49 baseline

Status: accepted (Phase 10) · Date: 2026-10-16

## Context
- Master Phase 10 / §6.19–6.21, §6.24: in-game debug overlay,
  console, inspector, timeline/level editors, a mission scaffolder,
  an "add a mission" tutorial, and Mission 0 (D2) built by following
  it — with zero edits under `src/engine/`. CI still carried TODO
  rows: bench budgets, engine3d parity, mission 0.
- The engine kernels are pure by design (E4); debugging and editing
  are inherently game-facing (they reach into STATE, missions, live
  entities). The W1 ratchet (shared→mission import sites, baseline
  48) exists to stop accidental coupling creep.

## Decision
1. **Dev tools are game-side.** `src/game/devtools.py` (F3 overlay:
   frame graph from `engine.core` profiling samples, RenderStats,
   entity/scene readouts; F4 collision view; click inspector with
   plain-field edit; prefab spawn) plus the `~` console
   (`src/core/console.py`, commands bound through `Console.bind`).
   Both are inert unless opened, so the oracle harnesses — which
   never open them — see zero behaviour change. The F12 level editor
   and the F5/F6 level/timeline panels ride the same overlay and
   write **data files only**, through the same canonical writers as
   the CLI tools (`game.timelines.save_timeline`, indent=1).
2. **Mission 0 is a thin host, not a clone.** `tools/ae_new_mission.py`
   scaffolds data where the loaders look
   (`content/{levels,dialogue,timelines,sets}/<id>.*`) plus a host
   package; the host composes existing pieces (`Enemy`/`Player`,
   `DialogueRunner`, registered cutscene renderers, `engine.ui`
   widgets) instead of copying a mission. Proof is automated:
   `tools/ae_mission0_check.py` pins the sha256 of the whole
   `src/engine/**.py` tree (82 files, `e26ff0bd…baf`, frozen before
   M0 existed) and plays the mission start-to-finish headlessly.
3. **W1 baseline 48 → 49, deliberately.** One new shared→mission edge
   (`core.game_core -> missions.m0`, the import every mission has) is
   the honest cost of a sixth mission. It is recorded here and in
   `tools/check_boundaries.py`, not slipped past the ratchet; the
   earlier accidental W1 edges in this phase (heat/reload/cache
   reach-throughs) were fixed properly through app bindings instead.
4. **Bench budgets are data.** `tools/bench_budgets.json` holds the
   §6.22 owner budget (10 ms) and recorded sandbox caps with ~1.5×
   headroom; `ae_bench.py --check-budget` renders the verdict. The
   sandbox caps catch regressions; only the owner machine certifies
   10 ms. The engine3d parity CI row likewise gates software-backend
   determinism everywhere (`tools/ae_engine3d_parity.py`); the GL
   diff remains an owner run of `tools/engine3d_check.py`.
5. **Packaging is a build, not a gate.** `tools/ae_package.py` zips
   the runtime tree with a hashed manifest (`ae.package/1`);
   `dist/` is produced on demand and not kept in the tree.

## Consequences
- D2/D9/D10/D11 are provable from CI rows and the gauntlet report
  (`tools/ae_gauntlet.py`, clean on first run) instead of by
  assertion. The last CI TODO rows are retired.
- If a future mission is added, W1 rises by exactly its one dispatch
  edge — amend this ADR's successor, never quietly re-pin.
- B-038 (owner golden set overwritten by a sandbox recapture at
  Phase 10 opening) stays open until the owner re-exports
  `tests/golden/baseline_v0`; sandbox gates are unaffected.
