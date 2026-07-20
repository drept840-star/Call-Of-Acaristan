# Call of Acaristan — Playtest Feedback: Bug Report & Design Improvements

**Scope:** Transforms four pieces of playtest feedback into (1) a formal bug report and (2) a prioritized list of design improvements, grounded in the real flat-layout codebase: `acaristan.py`, `config.py`, `audio.py`, `menu.py`, `enemy_ai.py`, `game_core.py`, `cutscenes.py`, `walking_sim.py`, `mission.py`, `mission2.py`, `smoke_test.py`.

**Validation gate for every change below:** `uv run python smoke_test.py` must exit with code 0.

---

## Part 1 — Bug Report

Four defects, written in a format suitable for an issue tracker.

### BUG-001 — Ally dialogue advances too quickly during inspection

| Field | Value |
|---|---|
| Severity | Medium (readability / accessibility) |
| Type | UX defect |
| Reproducibility | Always |
| State(s) affected | `WALK`, `GAME`, `NOTEBOOK_INSPECT` |
| Primary files | `mission.py`, `mission2.py`, `game_core.py` (typewriter render path) |

**Description.** When the player inspects a story prop or triggers an ally line during an inspection, dialogue lines auto-advance before the player can finish reading. Lines stored as `(text, speed)` tuples are rendered without a per-line minimum display time; the timer is driven primarily by typewriter completion plus a short tail.

**Steps to reproduce.**
1. `uv run python acaristan.py`
2. Start Mission 1 and enter the WALK phase through the slums.
3. Approach any inspectable story point (e.g., the burning car, the body, the radio).
4. Press the interact key; observe ally commentary lines advancing within ~1 second each.

**Expected.** Each line stays on screen long enough to read at normal pace; player input (Space / E) advances early.

**Actual.** Lines auto-advance before reading completes; longer lines are clipped in perceived time.

**Suspected root cause.** Dialogue lines are `(text, speed)` tuples with no `min_display_ms`; typewriter completion plus a small constant tail is the only gate. There is no global text-speed multiplier.

**Fix direction.** See DI-03.

---
### BUG-002 — Multiple inspectable objects share the same generic sprite

| Field | Value |
|---|---|
| Severity | Medium (visual clarity, immersion) |
| Type | Art / rendering defect |
| Reproducibility | Always |
| State(s) affected | `WALK`, `GAME` |
| Primary files | `walking_sim.py` (`WALK_PROPS`, prop draw routines), `game_core.py` (warehouse interactables), `config.py` (tile / draw helpers) |, `mission2.py`

**Description.** Distinct inspectable categories (notebook, papers, radio, crate, body, weapon, etc.) reuse the same procedural silhouette. Players cannot distinguish them at a glance, which weakens both navigation and the diegetic signal that each object is meaningfully different.

**Steps to reproduce.**
1. Walk through the slums in WALK and note the inspectable markers.
2. Enter the warehouse interior.
3. Compare on-screen rendering of objects of different intended types.

**Expected.** Each inspectable kind has a unique procedural appearance using the existing pygame-primitive art language.

**Actual.** Several inspectables render with the same generic shape and palette.

**Suspected root cause.** A single shared draw path is used for multiple prop kinds; type dispatch is missing or partial.

**Fix direction.** See DI-04.

---

### BUG-003 — First-person sniper cutscene fails to trigger

| Field | Value |
|---|---|
| Severity | High (blocks an intended Mission 2 narrative beat) |
| Type | Logic / state-machine defect |
| Reproducibility | Always at the relevant Mission 2 transition |
| State(s) affected | `CUTSCENE` (Mission 2, stage `STAGE_SNIPER`) |
| Primary files | `mission2.py` (`_start_sniper_sequence` L836, `_draw_sniper_overlay` L2689, `STAGE_SNIPER` L218), `acaristan.py` (state-machine dispatch), `cutscenes.py` |

**Description.** The first-person sniper POV cinematic — the optic-view sequence in `_draw_sniper_overlay` that shows the KRAP squadmates being shot down — does not play when its trigger conditions are met. The game proceeds into the sniper-pressure gameplay (`STATE.mission2_sniper_pressure`) without the preceding cinematic, breaking pacing and removing the emotional setup for the cover gameplay.

**Steps to reproduce.**
1. Start a new game and progress to Mission 2.
2. Reach the transition that should call `_start_sniper_sequence()` (see `mission2.py` L431 / L439).
3. Observe that no FP overlay plays; gameplay continues without the cinematic.

**Expected.** State transitions to `CUTSCENE`, `_draw_sniper_overlay` renders the squad-death FP sequence end-to-end, then control returns to `GAME` in `STAGE_SNIPER` with `STATE.mission_phase = "m2_sniper"`.

**Actual.** The cinematic is silently skipped or never invoked.

**Suspected root cause (to confirm during implementation).**
- The two `_start_sniper_sequence()` call sites (L431, L439) may be unreachable under current phase flow.
- The dispatcher in `acaristan.py` may not route to the FP overlay path when `mission_phase == "m2_sniper"` is set without an intermediate `CUTSCENE` state push.
- A guard on `STATE.mission2_sniper_*` initialization may run before the overlay frame loop, hiding the cinematic.

**Fix direction.** See DI-02.

---
### BUG-004 — "Draw Conclusions" mechanic is poorly received

| Field | Value |
|---|---|
| Severity | Medium (UX defect; not a crash, but the most-cited pain point) |
| Type | Mechanic / UX defect |
| Reproducibility | Always on encountering the deduction board |
| State(s) affected | `GAME` (Mission 2 deduction board) |
| Primary files | `mission2.py` (`MANOR_DEDUCTION_STEPS` L248, `STATE.deduction_*` L301 onward, slot/pool phase) |

**Description.** Players consistently report the "Draw Conclusions" / deduction board as confusing and unfun. Symptoms from feedback:
- Unclear which clue belongs in which slot.
- Slot/pool phase switching (`STATE.deduction_phase`) is opaque.
- Wrong placements do not give clear diegetic feedback.
- The on-screen state has accumulated many ad-hoc fields (e.g. `deduction_open_message_persistent_timer_persistent_timer_max`), suggesting the UX was patched repeatedly rather than redesigned.
- The payoff text feels anticlimactic relative to effort.

**Steps to reproduce.**
1. Progress Mission 2 to the deduction board (`STATE.deduction_active = True`).
2. Attempt to fill the slots from the clue pool.
3. Observe the friction described above.

**Expected.** A clear, learnable mini-mechanic where each placement gives immediate, legible feedback and the payoff feels earned.

**Actual.** Players bounce off the mechanic; many request to skip it.

**Fix direction.** See DI-01 (tracking design improvement for this defect).

---

## Part 2 — Prioritized Design Improvements

Priority key: **P0** = ship-blocker for player experience; **P1** = high-impact quality win; **P2** = polish; **P3** = nice-to-have. Ordering reflects player impact per engineering effort.
### P0 — DI-01: Redesign the "Draw Conclusions" mechanic

**Why first.** Highest-friction system in the game; affects Mission 2 completion rate.

**Proposal.**
- Collapse the slot/pool dual-phase into a single board: clue cards on the left, deduction slots on the right, drag-to-place (or arrow-select plus confirm).
- Per-slot **diegetic feedback**: correct placement snaps and a short ally line plays via `audio.py`; wrong placement gently rejects with a shake and an in-character hint ("That doesn''t fit the timeline").
- Cap simultaneous active clues at no more than 6; reveal additional clues as earlier slots are solved.
- Gate progression on the minimal-necessary deduction; mark remaining slots as optional with codex/dialogue rewards.
- Aggressively prune the `STATE.deduction_open_message_persistent_timer_persistent_*` field cascade in `mission2.py` and replace with a single `DeductionMessage` dict shape: `{text, color, lines, index, total, speed, priority, persistent, timer, timer_max}`.

**Acceptance.**
- New players resolve the mandatory deduction within ~60 seconds on first try in playtest.
- The `STATE.deduction_*` field count is reduced by at least 50%.
- `uv run python smoke_test.py` exits 0; opening and closing the deduction board raises no exceptions.

**Touch points.** `mission2.py` (deduction state and UI), `audio.py` (snap / reject SFX), `config.py` (any new procedural icons).

---

### P0 — DI-02: Restore the first-person sniper cutscene

**Why first.** Tiny scope, fixes a blocking narrative regression on Mission 2.

**Proposal.**
- Audit both call sites of `_start_sniper_sequence()` in `mission2.py` (L431, L439). Confirm the phase predicate that reaches them.
- Introduce a single canonical entry: when `STATE.mission_phase` transitions into `"m2_sniper"`, the main loop in `acaristan.py` must push state `CUTSCENE` and route draw to `_draw_sniper_overlay` until the cinematic clock (`t >= 645` per current overlay timing) elapses, then pop back to `GAME`.
- Add a one-line dev log (gated by a `DEBUG_CUTSCENES` flag in `config.py`) whenever the trigger is evaluated and whenever it fires.
- Add a developer keybind (e.g. F9) in `acaristan.py` that force-plays the sniper cutscene for QA.
- Wrap `_draw_sniper_overlay` in `try/except` so a render error logs and falls through to `STAGE_SNIPER` gameplay rather than freezing.

**Acceptance.**
- From a fresh save, the sniper FP cinematic plays in 5/5 runs at the intended Mission 2 beat.
- F9 force-play works from any state.
- Esc-skip (hold 0.5s) returns cleanly to `STAGE_SNIPER`.
- `uv run python smoke_test.py` exits 0.

**Touch points.** `mission2.py`, `acaristan.py`, `cutscenes.py`, `config.py` (debug flag).

---
### P1 — DI-03: Dialogue pacing overhaul plus text-speed setting

**Why.** Fixes BUG-001 and raises baseline readability across the whole game.

**Proposal.**
- Replace `(text, speed)` tuples in `walking_sim.py`, `mission.py`, `mission2.py` with a shared helper `make_line(text, voice=None)` that returns a normalized dict: `{text, min_display_ms, auto_advance_ms, voice}`.
- Default formula: `min_display_ms = max(2200, 55 * len(text))`; `auto_advance_ms = min_display_ms + 1500`.
- Player input (Space / E) advances only after `min_display_ms` has elapsed (prevents accidental skips on freshly-appeared lines).
- Add a **Text Speed** setting in `menu.py` (Slow x1.5, Normal x1.0, Fast x0.7) that scales `min_display_ms` and `auto_advance_ms`.
- Persist via whatever save path `menu.py` / `acaristan.py` already use for settings (introduce a small `settings.json` sidecar if none exists).

**Acceptance.**
- On Normal, playtesters finish reading each line before auto-advance in at least 90% of cases.
- Setting persists across runs.
- `uv run python smoke_test.py` exits 0.

**Touch points.** `walking_sim.py`, `mission.py`, `mission2.py`, `menu.py`, `config.py`, `acaristan.py`.

---

### P1 — DI-04: Unique procedural sprites for inspectable objects

**Why.** Fixes BUG-002; parallelizable with DI-03.

**Proposal.**
- Add an `INSPECTABLE_KINDS` enum-like constant set in `config.py`: `NOTEBOOK`, `PAPERS`, `RADIO`, `CRATE`, `PHOTO`, `BODY`, `WEAPON`, `BOTTLE`, `MAP`, `BURNING_CAR`.
- For each, add a small `draw_inspectable_<kind>(surf, rect, accent)` function using the existing pygame-primitive language (flat shapes, limited palette, 1-2px outline) that reads at the `TILE_SIZE` footprint defined in `config.py`.
- Add a per-kind accent glow used only when the prop is in interact range.
- Update `WALK_PROPS` in `walking_sim.py` and the warehouse interactables in `game_core.py` / `mission2.py` to carry a `kind` field, and dispatch on it in the prop draw routine.

**Acceptance.**
- Every inspectable in Mission 1 has a visually distinct silhouette in a single screenshot pass.
- `uv run python smoke_test.py` exits 0 and exercises each draw variant.

**Touch points.** `config.py`, `walking_sim.py`, `game_core.py`, `mission2.py`, `smoke_test.py`.

---
### P2 — DI-05: Inspection HUD anchor plus speaker tag

**Why.** Companion to DI-03; the pacing fix is undermined if the HUD itself is noisy.

**Proposal.**
- Anchor inspection / dialogue text to a fixed lower-third panel with consistent positioning across `WALK` and `GAME`.
- Add a small procedural speaker silhouette plus name tag on the left of the panel, driven by the new `voice` field from DI-03.
- Show a `Press [E] to continue` prompt that fades in only after `min_display_ms` elapses.

**Acceptance.**
- Inspection panel never overlaps the player sprite or critical HUD.
- Prompt indicator is unambiguous in playtest.

**Touch points.** `game_core.py`, `walking_sim.py`, `config.py`.

---

### P2 — DI-06: Cutscene robustness and uniform skip

**Why.** Generalizes the safety net from DI-02 to all cutscenes.

**Proposal.**
- Wrap every cutscene draw/update in `try/except`; on exception, log and fall through to the appropriate post-cutscene state.
- Universal hold-Esc-0.5s skip, with a small radial fill indicator so accidental taps don''t skip.
- Add a Scene Log in the pause menu listing previously seen cutscenes, replayable from the main menu after first completion.

**Acceptance.**
- No cutscene can soft-lock the game in a 30-minute playtest.
- Hold-Esc skip works in every cutscene including the FP sniper sequence.

**Touch points.** `cutscenes.py`, `mission2.py`, `walking_sim.py`, `menu.py`, `acaristan.py`.

---
