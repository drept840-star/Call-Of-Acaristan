# ADR-019: Cutscene timelines and 3D sets as data, takes as registered hooks

Status: accepted (Phase 8) · Date: 2026-10-15

## Context
- Cutscenes were sequenced by ~20 shot lists (`{scene, speaker, text,
  lighting, min_ms, ...}` dicts in mission `meta.py` modules and
  `cutscenes/engine.py`), played by `app.CutscenePlayer` through
  `draw_cutscene_scene`'s 2D elif chain plus takes registered by scene id
  (`core.cutscene_registry`). The M5 3D takes (`m5mid3d`, `m5martial3d`)
  build `engine3d` meshes imperatively per frame — poses, IK-ish reaches,
  post passes — behind a renderer pool + failure latch.
- The master's §6.7/§6.15 ask for recorder-based keyframe migration of
  every take. That is a human-scale art project per take; the same exit
  section explicitly accepts the alternative: imperative modules "reduced
  to custom FX hooks registered by id (documented)". Phase 5/6 set the
  precedent: kernels + data for what is data-shaped, hosting for the rest.
- The M4 timed radio/arrest ladders left over from Phase 7 are
  frame-scheduled event sequences — timeline data by shape.

## Decision
1. **`ae.timeline/1`** (`engine.timeline`): a timeline is an ordered
   `shots` list (each shot names a renderer *hook id* in `scene` and
   carries its legacy payload verbatim) and/or keyframed `tracks`
   (camera/light/actor/decal keys; fx/dialogue/caption/audio/event
   clips). `TimelinePlayer.sample(t)` is deterministic — key expressions
   resolve at their own key's time, then snapshots interpolate — and
   `events_between` gives frame-exact one-shot firing. Values may be
   expressions over params via the whitelisted evaluator
   (`timeline.expr`); `eval` is never used.
2. **Every shot list is data.** All 20 lists (90 shots) are exported to
   `src/game/content/timelines/*.timeline.json` and converted back to
   legacy shot dicts by `game.timelines.shots()` at definition;
   `ACA_TL_SRC=legacy` keeps the tables. `tools/ae_timeline_check.py`
   proves validator-clean + equality in CI, so `CutsceneScene` (and the
   legacy player, and the golden gauntlet) all read timelines.
3. **The M4 ladders are event tracks.** `m4.story_beats` /
   `m4.arrest_beats` carry `{t (frames), name, text, color, sfx?,
   duration}` clips; `m4/flow.py` fires `events_between(t-1, t)`.
   Frame-exactness is proven by the checker sampling every legacy beat.
4. **`ae.set3d/1`** (`engine.render3d`): sets are node lists (box,
   quad_xz, quad, disc_xz, decal+fallback, sprite3d, humanoid, light,
   repeat, prop_ref) flattened by `build` into ordered primitives with
   expressions evaluated. The kernel never imports a renderer. The
   game-side bridge (`game/render3d_bridge.apply_set`) walks primitives
   onto a live renderer through the host's own `add`/`dec`/`spr`/
   `decal_add` helpers, preserving painter-sort and bias semantics; a
   failed decal emits its fallback primitives (§6.7 semantics).
5. **Pilot set, honestly scoped.** Vasile's office (`_office_set`,
   static geometry behind four golden-covered takes) renders from
   `content/sets/m5.vasile_office.set3d.json` — 15/15 golden shots
   pixel-identical. Dynamic builders (seeded windows, per-vertex colour
   functions, time-driven doors) stay imperative; each remaining take is
   a registered FX hook (A-012) and migrates set-by-set as its static
   parts are factored out. Deleting the take modules is *not* a Phase 8
   claim.
6. **`CutsceneScene` plays timelines.** `CutsceneScene.from_timeline`
   builds the scene from a `Timeline` (shots + a `TimelinePlayer` for
   track sampling) behind the Phase 2 surface — the lift its docstring
   promised. The in-game `app.CutscenePlayer` stays as the hosted
   player (A-007 lineage) and consumes the same data.
7. **Editor round-trip exists at file level.** `tools/ae_timeline_edit.py
   set-key` edits a key and proves by reload+resample that the frame
   changed exactly there (unit-tested). The §6.20 in-window editor
   remains Phase 10 tooling.

## Consequences
- No golden was re-baselined and no loop segment re-recorded for this
  phase: timelines and the pilot set are parity-identical (373/373,
  7/7, replay OK).
- Banned-pattern check (§10 item "magic camera or set numbers in Python
  after Phase 8"): now *possible* to violate knowingly — new sets/scenes
  are expected in data; the remaining magic numbers are the documented
  A-012 hooks, removed per-set under golden gates.
- The 2D elif chain in `cutscenes/engine.py` and the `m5mid3d` 2D
  fallbacks are untouched: they are what the hooks render, and the 3D
  failure latch still falls back to them.
- API snapshot re-recorded for the two kernels (72 modules, 491 names).

## Alternatives considered
- Recorder-fitted keyframes for all 30 M5 shots now: rejected for this
  phase — the takes compute poses/IK procedurally per frame; a sampled
  recorder would bake dense keys with worse fidelity and no authoring
  win. The timeline *format* supports it when someone does that pass.
- Modelling the office sprites (`_fx.glow` etc.) as kernel concepts:
  rejected — FX constructors are game presentation; the data names them
  (`sprite3d.asset`) with a params bag, the bridge binds them.
