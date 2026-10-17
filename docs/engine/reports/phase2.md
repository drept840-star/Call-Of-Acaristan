# Phase 2 report — Boundary and scene stack
Date: 2026-10-14 (Arena sandbox)   Commits: none (owner tracks changes as files; see CHANGELOG.md "Phase 2 start" + "Phase 2 close" and docs/worklog.md)

## Outcome (first line = honest status)
DONE with one carried caveat: the scene stack exists, is enforced by lint, traced in every run and populated with the §6.2 scene types — but until Phase 4 it is a **mirror** of the legacy `GameStateManager` (A-005/A-007): the FSM still owns behaviour, and the M5 scene trace is produced by driving the real FSM through the M5 flow (`tests/unit/test_scene_mirror.py`), not by a scripted end-to-end playthrough (no such driver exists yet; Phase 10 tooling).

## Exit criteria (master prompt §7 Phase 2)
- [x] `engine.scene` — `src/engine/scene/` (`Scene`, `SceneStack`, `CutsceneScene`, `InspectScene`), ADR-014; 22 unit tests (`test_scene_stack.py`, `test_scene_types.py`, `test_scene_mirror.py`).
- [x] boot/menu/mission/pause as scenes — mirrored (A-005): BOOT_INTRO/MENU/GAME/... replace, PAUSED and NOTEBOOK_INSPECT push/pop as overlays; `_LegacyGameScene.stack` owns them; lifting the states' behaviour into the scenes is Phase 4 (ADAPTERS A-002/A-005 removal plan).
- [x] Cutscene dispatcher wrapped in `CutsceneScene`, `inspect_fpv` in `InspectScene` — A-007: CUTSCENE state → `CUTSCENE[<first scene>+<shots>]` on the stack; `inspect_fpv.on_change` → `INSPECT[<key>]` overlay. The take registry (A-003) now holds every mission-owned scene id (59), the dispatcher imports no mission take module.
- [x] `check_boundaries.py` in enforce mode for `engine/*` — `BOUNDARIES: OK (0 engine violations, 27 engine modules)`; E1–E5 enforced since M1, now over 27 modules; W1 ratchet 169 → 48 (`BASELINE_W1`).
- [x] Shared engine code moved under `engine/` with re-export shims and deprecation warnings — A-006: `render_util` → `engine.render2d`, `lighting` → `engine.lighting`, `artpack` + `sprite_lib` → `engine.assets`, `figure_kit` → `engine.anim` (generic kit; the KRAP palette is the only game coupling, pinned to config by a test).
- [x] Scene trace for an M5 playthrough matches the expected trace — `tests/data/m5_scene_trace.txt` == `SceneStack.trace` after the M5 FSM flow (23 lines) through the real `GameStateManager`; loop probe `scene_trace` compared per segment (`tests/loop/baseline_v3`, additive key). Caveat above.
- [x] Boundary lint enforced and passing — row 2 of `/tmp/ci_phase2.txt`.
- [x] Golden and replay parity — `/tmp/ci_phase2.txt`: golden 353/353 (0 failures, 0 errors), replay 5/5, loop 7/7 bit-identical through every Phase 2 step (`/tmp/ci_p2m1.txt`, `/tmp/ci_p2m4.txt`, `/tmp/ci_phase2.txt`).

## Metrics
- Boundary violations: engine 0 → 0 (13 → 27 engine modules); W1 shared → mission **169 → 48** (dispatcher −57, facade −66, +2 for the explicit mission imports).
- Engine public surface (`tests/api/engine_api.json`): 16 modules / 79 names → 25 / 121; `ae_api_snapshot.py check` is a CI row.
- STATE fields: 478 → 478 (no new fields; §10). No new globals in shared code except the registry tables at the take modules' bottoms.
- Adapters: added A-005 (FSM mirror), A-006 (module shims), A-007 (cutscene/inspect mirrors); A-003 generalised (1 → 59 registered scene ids); removed none; open A-001..A-007.
- Unit tests: 43 → 72. Smoke checks: +1 (`cutscene_scene_ids_resolve`: 72 shot-list ids → 59 takes + 27 built-ins + 1 prefix handler).
- Cutscene dispatcher: 82 → 24 `elif` branches (+1 `in` branch, +1 prefix); 53 import names dropped.
- Repo size unchanged (29 MB). Bench: not measured (Phase 10).

## Visual evidence
- Golden set verified bit-identical after each step (no new goldens needed: the moves and mirrors are parity-neutral by construction). Loop probe frame hashes identical in 7/7 segments (`build/ae_loop/*.json` vs `tests/loop/baseline_v3`).

## Risks / debt carried
- The stack is a shadow of the FSM until Phase 4 (ADR-014 consequences).
- `tools/sprites/t7_probe.py` monkeypatches `artpack.frame` on the shim (dev tool; engine-internal calls do not see it).
- B-013: `ae_replay.py --only` deferred to Phase 9 (format revisit).
- Remaining W1 48: `core.console → missions` 18 (dev console command table), `core.game_core → missions` 7 (mission start table; Phase 7 level registry), `cutscenes.chair → cutscenes.m3cell` 8 (shared helpers `_m3_clamp01/_m3_noise/...` want a neutral home), tools 8, dispatcher 2, ui/entities 5.

## Next three steps
1. Phase 3 entry: asset registry + bake check (`engine.assets` already hosts artpack/sprites; the CI row "asset bake check + lint" is the gate).
2. Phase 4 prep (can start in parallel): lift PAUSED/NOTEBOOK_INSPECT/CUTSCENE/INSPECT to stack-driven scenes (they already have scene objects), then narrow the `from core.config import *` star imports (A-001).
3. Ratchet the remaining W1 edges as registries appear (console commands, mission start table).
