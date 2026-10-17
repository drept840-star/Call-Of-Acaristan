# Phase 1 report — Kernel: App, Clock, Services, no import side effects
Date: 2026-10-14 (closeout; kernel written 2026-10-11)   Commits: none (owner tracks changes as files; see CHANGELOG.md M1–M3 and docs/worklog.md)

## Outcome (first line = honest status)
DONE in the Arena sandbox, with two carried caveats: (1) `App.boot` still runs at `core.config` import time because 51 modules star-import `screen` (B-007, Phase 4 scope); (2) all baselines backing this report are sandbox baselines (Linux, pygame-ce 2.5.8, software 3D, sandbox fonts); the owner re-captures on the reference machine before trusting `tests/` there.

## Exit criteria (master prompt §7 Phase 1)
- [x] `engine.core` (app, clock, events, rng, log, config/settings, services, profiling, errors, mathx, timebase) — evidence: `src/engine/core/*.py`, 13 modules, each with `__all__`; `tools/check_boundaries.py` → `0 engine violations`.
- [x] Import-side-effect test passes — evidence: `python tools/ae_import_check.py` → `IMPORT CHECK: OK (engine 13 modules clean)`; row 3 of `/tmp/ci_m3.txt`.
- [x] Display creation in `App.boot`; no import-time `SDL_VIDEODRIVER` setdefaults in `src/` — evidence: `grep -rn SDL_VIDEODRIVER src` → only `engine/core/app.py:57` (chosen once at boot). Adapter A-001 documents the import-time boot caveat.
- [x] Legacy game runs inside `_LegacyGameScene` on the fixed-step loop — evidence: `app.py:_legacy_frame` + `App.run_scene` (A-002); single-player sim steps through `App.clock.advance(dt)` (ADR-004); `ae_loop.py` 7/7 segments.
- [x] All `random` use in simulation through named streams, legacy seeding kept — evidence: 0 direct `random.X(` calls in `src/` (519 uses via `_rng_legacy` = adopted `legacy` stream; 191 private `random.Random` instances for art); grain on the `grain` stream; replay `baseline_v0` 5/5 identical.
- [x] Golden and replay baselines identical — evidence: `/tmp/ci_m3.txt`: `golden images OK 353 shots: 0 failures, 0 errors`; `replay determinism OK 5 segments match` (final hashes m1 2bbec2400def5ebf, m2 f80109f8b020d6ef, m3 edd429e9fc6818aa, m4 72737dd7449275b2, m5 b05d9ee03d6e99a1, unchanged since M1).
- [x] Crash report works — evidence: `tests/unit/test_errors.py`; `App.run_scene` writes it on uncaught errors (A-002).
- [x] `ae_ci.py` exists and is green — evidence: `/tmp/ci_m3.txt` → `AE CI: OK (implemented gates)`: compileall, boundary lint, import side effects, unit tests (43), smoke (`SMOKE TEST: OK`), golden, replay, loop.
- [x] Wall-clock reads through the engine clock (B-001, STATUS criterion) — evidence: `tools/ae_migrate_time.py` → `files=33 get_ticks=163 time.time=48`, AST proof per file; golden/replay/loop bit-identical after the migration (`/tmp/m3_time_gate.txt`, after the harness-order fix).

## Metrics
- Boundary violations: engine 0 → 0; W1 shared → mission 169 → 169 (held; ratchet starts in Phase 2).
- STATE fields: 478 → 478 (no new fields; §10).
- Procedural draw calls (census): 1,113 mission `pygame.draw(screen, …)` calls, unchanged.
- Duplicated UI functions: unchanged (`audit/duplication.md`).
- Adapters: added A-004 (timebase accessors); removed none; open A-001, A-002, A-003, A-004.
- Wall-clock reads in game code (`src/` minus `engine`, `net`, `tools`, `save_system`): 211 → 0 (`get_ticks` 163 → 0, `time.time` 48 → 0).
- Direct global `random.X(` calls in `src/`: 0 (B-002 direct part was done in P1 earlier); import-time RNG consumption by `GRAIN_VARIANTS`: 19,800 draws → 0 on the sim stream.
- Unused `import random`: 34 → 0.
- Unit tests: 39 → 43.
- Bench: not measured (Phase 10).

## Visual evidence
- Golden comparisons: 353, failures 0, worst: none (byte-identical).
- Loop probe: time migration 4,020/4,020 frames identical; grain stream: `baseline_v1` → `baseline_v2`, state sequences identical in 7/7 segments, first differing frame = first grain frame (boot 88, walk 22, missions 0). Images reviewed: none needed; the change is 1,100 alpha-2..10 specks per variant.

## Risks & caveats
- Frozen game clock in harnesses: tools that render without running the frame loop see a constant `now_ms()`; six check tools were updated to `pin_wall`. Any future tool mixing `pygame.time.get_ticks()` arithmetic with game-time fields will mis-compute (the death-screen capture did, fixed).
- The sim still uses one shared `legacy` stream for all missions; per-system streams come with the ECS migration (Phase 5). Harness `get_ticks`/`time.time`/hash-seed pins are kept as belt and braces.
- `ae_replay.py --only mX` cannot match a sequential baseline (STATE leakage in the hash; B-011 note). Fix with the Phase 2 replay-format revisit.
- Sandbox baselines ≠ owner baselines.

## Decisions (ADRs)
- ADR-004 fixed timestep (earlier); ADR-005 frame-coherent wall clock + `grain` stream re-baseline (new).

## Next phase entry check
- Phase 2 entry = Phase 1 exit criteria hold (above) and `ae_ci.py` green: yes (`/tmp/ci_m3.txt`). First Phase 2 tasks: `tools/ae_api_snapshot.py`; generalise `core.cutscene_registry` into the take registry; start ratcheting `BASELINE_W1`.
