# ADR-004: Fixed timestep and the engine clock

Status: accepted (Phase 1) · Date: 2026-10-11

## Context
- The legacy single-player loop runs on a variable dt (`clock.tick(FPS)`). Only multiplayer uses `core/fixedstep.FixedStepClock` (60 Hz, max 5 steps).
- 232 wall-clock reads (`pygame.time.get_ticks`, `time.time`) make visuals and some logic depend on wall time (B-001). Golden and replay harnesses currently pin both clocks to stay deterministic.

## Decision
1. `engine.core.clock.Clock` is the single time source for engine code: fixed `dt = 1/hz` (default 60), accumulator with `max_steps` spiral guard, `alpha` for interpolation, `time_scale`, `pause`, and a simulated `ticks_ms` that replaces `get_ticks()` for game time.
2. Its step accounting matches `FixedStepClock` exactly. A unit test checks identical step counts at 30/60/144 fps.
3. Legacy code keeps its variable dt until its scene migrates (strangler, R3). Migrated systems read time only from the clock service. Wall-clock reads stay legal only for profiling and UI blink effects marked `# rpe6: wall-clock ok`.
4. Replay/golden: the harness drives `Clock.advance(1/60)` and pins wall clocks until each legacy wall-clock site has been routed through the clock.

## Consequences
- Frame-rate independence for migrated systems; replays become exact without monkeypatching once B-001 sites are routed.
- Two clocks coexist during migration; `ADAPTERS.md` tracks the bridge.
- `core/fixedstep.py` has a duplicated `DEFAULT_MAX_STEPS = 5` (lines 52 and 154, B-006). It's harmless and left alone until the multiplayer loop adopts the engine clock.
