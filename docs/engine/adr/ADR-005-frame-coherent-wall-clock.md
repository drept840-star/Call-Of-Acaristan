# ADR-005: Frame-coherent wall clock and the `grain` rng stream

Status: accepted (Phase 1, M3) · Date: 2026-10-14

## Context
- 232 legacy sites read `pygame.time.get_ticks()` / `time.time()` directly (B-001, AUDIT §8). A single frame therefore saw many different "nows", visuals depended on wall time even under `ACA_FREEZE=1`, and every harness had to monkeypatch pygame and `time`.
- ADR-004 made `engine.core.Clock` the sim time source but left wall-clock reads for later. `Clock.ticks_ms` (sim-derived) cannot replace them yet: the legacy loop is not a pure fixed-step loop, and UI timers must keep running while the sim is paused.
- `core/config.py` built `GRAIN_VARIANTS` from the shared legacy RNG at import time (19,800 draws), so the simulation's random sequence depended on an import-order side effect (B-002, B-007).

## Decision
1. `Clock` carries a **frame-coherent wall clock**: `set_wall_origin(ms, epoch_s)` anchors it to the OS clocks at `App.boot`; the host calls `feed_wall(elapsed_ms)` once per presented frame with the raw, unclamped frame time; `wall_ms` / `wall_s` are constant within a frame. It is independent of sim pause, time scale and `reset()`.
2. `app.py` feeds it right after `pygame.display.flip()`, so reads during frame k return the time at which frame k−1 was presented. Because `pygame.time.Clock.tick()` deltas telescope, `wall_ms` advances exactly like `get_ticks()` from one frame boundary to the next in real play. The only intended difference is that intra-frame jitter is gone. (`core/config.py` creates the pygame Clock right after `App.boot`, so the first tick spans loading, and a traced import of `app` shows 0 `now_ms()` calls before the first frame: nothing stamps game time during import.)
3. `engine.core.now_ms()` / `now_s()` (adapter A-004) are the drop-in replacements for legacy reads. They fall back to the OS clocks before an App is booted. `pin_wall` / `unpin_wall` are the test hook that replaces the pygame monkeypatch in check tools. Scenes written against the engine receive `ctx.clock` and never use these accessors.
4. Reads that mean *real* time stay on the OS clock: `src/net/*`, `src/tools/*`, `core/save_system.py` timestamps, `perf_counter` profiling.
5. `GRAIN_VARIANTS` draw from the named `grain` stream (`App.rng.stream("grain")`, derived from the master seed). The six surfaces are still built at `core.config` import (B-007 scope).

## Alternatives considered
- Feed the wall clock at the top of the frame (before reads): identical in real play up to one frame, but under `ae_loop.py` it reads one frame ahead of the pinned `get_ticks()`, which would have forced a loop re-baseline for a parity-neutral change. Feeding after present keeps all three oracles bit-identical.
- Honour a monkeypatched `pygame.time.get_ticks` inside `now_ms()`: re-couples the engine to pygame internals; rejected.
- Seed `grain` so that the old textures reproduce: impossible, the old textures depended on whatever state the OS-seeded global RNG had at import.

## Consequences
- Good: 211 call sites migrated mechanically (`tools/ae_migrate_time.py`, AST-proof per file); golden 353/353, replay 5/5 and loop 7/7 bit-identical after the time migration; a whole frame now shares one "now"; harness pins become redundant for game code.
- Bad / deliberate: the grain change alters every frame that draws grain (alpha 2–10 specks) and shifts the loop probe's seed alignment, so `tests/loop/baseline_v1` → **`baseline_v2`** (state sequences identical in all 7 segments; v1 kept). Golden and replay baselines are untouched.
- Follow-ups: drop the harness `get_ticks`/`time.time` pins once `src/net` and tools no longer matter to the oracles; remove A-004 when the last legacy scene migrates (Phase 4/5).

## Verification
- `python -m unittest discover -s tests/unit -t .` (WallClock tests: origin/feed/pin, pause independence, accessor fallback and pin hook).
- `python tools/ae_golden.py verify`, `python tools/ae_replay.py check`, `python tools/ae_loop.py check` after each step (M3 log: `/tmp/m3_time_gate.txt`, `/tmp/ci_m3.txt`).
- Before/after of the grain change: `tests/loop/baseline_v1` vs `baseline_v2`: `states` identical in 7/7 segments, first differing frame = first frame that draws grain (boot 88, walk 22, missions 0).
