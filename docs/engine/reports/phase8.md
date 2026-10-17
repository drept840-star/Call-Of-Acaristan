# Phase 8 report — declarative 3D sets and cutscene timelines (RPE6)

Status: **DONE in the sandbox** (2026-10-15), in the master exit's second
form: sequencing and one production set are data; the remaining
imperative takes are reduced to documented custom FX hooks registered by
id (A-012). Owner reference-machine `ae_ci.py` re-run pending, as with
every phase.

## What changed
- `engine.timeline` kernel: `ae.timeline/1` model + validator, a
  whitelisted expression evaluator (no `eval`), and a deterministic
  `TimelinePlayer` (keyframe sampling at any t — expressions resolve at
  their own key's time — plus clip tracks and frame-exact
  `events_between`).
- `engine.render3d` kernel: `ae.set3d/1` model + validator + `build`
  (nodes → ordered primitives; `repeat` stencils, `prop_ref` library
  sub-sets, decals carrying geometric fallbacks). Pure data — no
  renderer imports.
- All 20 cutscene shot lists (90 shots) exported to
  `src/game/content/timelines/*.timeline.json` and read back through
  `game.timelines.shots()`; the M4 story/arrest radio ladders are
  timeline event tracks consumed by `missions/m4/flow.py`. Legacy
  tables stay under `ACA_TL_SRC=legacy`.
- Vasile's office — the static set behind four M5 takes — renders from
  `src/game/content/sets/m5.vasile_office.set3d.json` through
  `game/render3d_bridge.apply_set` (host `add`/`dec`/`spr`/`decal_add`
  helpers, so painter-sort/bias semantics are the legacy ones).
  `ACA_SET_SRC=legacy` restores the imperative builder.
- `engine.scene.CutsceneScene.from_timeline` plays a `Timeline`
  (shots + track sampling) behind the Phase 2 surface.
- Tooling: `tools/ae_timeline_export.py`, `tools/ae_timeline_check.py`,
  `tools/ae_set3d_check.py`, `tools/ae_timeline_edit.py` (camera-key
  round-trip: edit → save → reload → sample differs exactly at the key;
  unit-tested). CI gained `timeline` + `set3d` rows.

## Exit criteria (master §7) vs evidence
- *Every cutscene shot matches golden (3D tolerance)* — `AE GOLDEN: OK`
  (373/373, incl. all `cut.*` shots and the 15 vasile shots rendered
  from set data), `AE LOOP: OK (7/7)`, `AE REPLAY: OK`. Nothing
  re-baselined, nothing re-recorded.
- *Imperative take modules removed, or reduced to custom FX hooks
  registered by id (documented)* — second form: A-012 lists every
  registered take/set builder, why it stays (per-frame poses/IK/post),
  and the per-set migration recipe proven by the office pilot.
- *Camera editor round-trip works* — `ae_timeline_edit set-key` +
  `tests/unit/test_timeline_edit_scene.py` (move fov 40→30, reload,
  sample(1000)=30, sample(500)=42.5).

## Honest scope notes
- The pool/failure-latch/present plumbing already lived in
  `m5martial3d` (`_rend`, `_present`, `_cache["failed"]`); the bridge
  deliberately does not duplicate it — it only turns data into the
  host's primitive calls. The 2D fallback latch firing during
  development proved it still works.
- A recorder-based keyframe migration of all 30 M5 takes (poses baked
  to dense keys) was not attempted: the takes compute animation
  procedurally, and sampled keys would be worse data than the code.
  The timeline format carries camera/light/actor tracks for the day a
  take is authored data-first (Mission 0, Phase 10).
- §6.7's prop quality bar and `content/props3d/` library are Phase 11
  groundwork; this phase ships one production prop (`m5/flags`, inside
  the bridge library) to prove `prop_ref`, not the library.

## Numbers
- Unit tests: 260 OK (8 added this phase). One pre-existing flake
  fixed for real: B-037 (the fire-zone twin now pins the engine clock;
  the painter's flicker reads `now_ms()`).
- API snapshot re-recorded for the two kernels: 72 modules, 491 names.
  Boundaries OK (75 engine modules, W1 48).
- Evidence: `docs/engine/evidence/phase8/final_gate.txt`.
