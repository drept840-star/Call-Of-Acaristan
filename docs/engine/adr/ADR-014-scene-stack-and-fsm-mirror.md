# ADR-014: Scene stack semantics and the FSM mirror

Status: accepted (Phase 2) · Date: 2026-10-14

## Context
- §6.2 asks for an explicit scene stack replacing stage flags and mode switches, with overlays, pause/resume and a scene trace as the Phase 2 oracle.
- The legacy flow is a flat `GameStateManager` (15 states in `app.py`) whose `enter/exit` carry audio, save and camera side effects. Lifting those states one by one is Phase 4 work; Phase 2 needs the stack and its trace *now* without changing behaviour (R1, R2).
- Hooks that mutate the stack from inside a hook (a scene pushing its child during `update`) are the common case; mutating a list while dispatching over it is the common bug.

## Decision
1. `engine.scene.SceneStack` semantics: `push` pauses the scene below unless the new scene is an **overlay**; an overlay lets the scenes below keep *drawing*, and keep *updating* only if it sets `passthrough_update`. `pop` resumes a paused scene only when nothing above it still covers it; `replace` pauses/resumes the scene below only if its state actually changes; `clear_to` exits everything top-first. Mutations requested during a dispatch are **deferred** until that dispatch returns (`flush()`), so a frame always completes against the stack it started with.
2. Every structural change is a one-line trace entry (`push X`, `replace X -> Y [via T]`, `pop X`) appended to `stack.trace` and the `scene` log channel. `transition` objects are recorded, not rendered: pixels of a transition belong to the host until the render queue exists (Phase 6).
3. **Mirror first, lift later (A-005).** The legacy FSM gets a single observer (`GameStateManager.on_change`, None by default) and `core.scene_mirror.FsmSceneMirror` replays its transitions onto the stack: states in `overlay_states` push/pop, every other state replaces the top, re-entering a state is a replace. A `scene_factory` lets the host substitute a richer engine scene for a state - the CUTSCENE state becomes a `CutsceneScene` carrying the take that plays, `inspect_fpv` becomes an `InspectScene` overlay (A-007). The mirror never drives behaviour; the FSM remains the owner until each state is lifted.
4. `CutsceneScene` runs on **real time** (`update`), not simulation time; `InspectScene` is an overlay with `passthrough_update=False` (freezes gameplay below, as `inspect_fpv` does).

## Alternatives considered
- Converting `_CutsceneState`/`CutscenePlayer` to run on the engine scene now: the only oracle that exercises that state is the loop probe's boot segment (no cutscene inside the probe windows), so a rewrite would be unprotected; rejected for Phase 2.
- Applying stack mutations immediately: simpler, but a scene that pops itself inside `update` would corrupt the dispatch loop; rejected.
- Treating SLOT_SELECT/SETTINGS as pushes on MENU: closer to the eventual design, but the FSM does not know "back" from "forward" - the mirror would have to guess; replace keeps the mirror honest.

## Consequences
- Good: a scene trace exists for every run (loop probe records `scene_trace`; `tests/data/m5_scene_trace.txt` pins the M5 flow); golden/replay/loop stay bit-identical; 27 unit tests cover the stack, the two scene types and the mirror.
- Bad / deliberate: until Phase 4 the stack is a shadow of the FSM; the trace for a real playthrough is produced by the FSM flow, not by scenes driving the game.
- Follow-ups: Phase 4 lifts PAUSED, NOTEBOOK_INSPECT, CUTSCENE and INSPECT first (they already have scene objects), then MENU/GAME; the mirror and `on_change` are deleted with `gsm`.

## Verification
- `python -m unittest tests.unit.test_scene_stack tests.unit.test_scene_types tests.unit.test_scene_mirror`.
- `python tools/ae_loop.py check` (compares `scene_trace` once a baseline carries it); `/tmp/ci_phase2.txt`.
