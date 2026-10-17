# ADR-022: 3D visual upgrade track, steps 1–4 (Phase 11)

Status: accepted (Phase 11) · Date: 2026-10-16

## Context
Master §6.7 orders the 3D visual upgrades; Phase 11's minimum exit is
steps 1–4 shipped to the track's acceptance bar (data-reachable,
proof sheet, review entry, setting, bench number, deliberate golden
re-baseline, gauntlet clean). The software renderer is the CI oracle;
GL-only divergence needs an ADR (this is it, for the points below).

## Decision
1. **Lighting presets are kernel data.** `ae.lighting3d/1` files in
   `src/game/content/lighting3d/` (night_interior, office_day +
   day_interior alias, exterior_overcast, exterior_night_rain +
   rainy_street alias; duplicates rejected, aliases resolve, no
   copies). `engine.render3d` gains `presets.py` (resolve/blend —
   the engine-tree hash in `ae_mission0_check.py` was re-frozen with
   justification in the Phase 11 report; Mission 0's own zero-diff
   proof stands on the Phase 10 hash). A set says `"lighting":
   "office_day"` or `{"preset": ..., "key"/"fog" overrides}`; the
   set's legacy `light`/`fog` blocks still override single fields.
   `render3d_bridge.set_lighting(set_id, blend=(a, b, k))` serves
   timeline-style cross-fades (M0 outro warms 25% toward office_day).
2. **Local lights, per-face in software, per-pixel-model in GL.**
   `{"type": "light", "kind": "point|spot", ...}` nodes and
   `attach_light` on emissive boxes (a lamp lights its desk wherever
   placed). `SoftwareRenderer.set_lights` caps at the 8 strongest;
   contribution is evaluated per face centre (the software backend's
   accepted approximation of per-vertex). The GL fragment shader
   implements the same falloff/cone model for up to 4 lights on
   dynamic geometry. Declared divergence: GL *baked-static* geometry
   does not receive local lights (its colours are pre-lit); software
   does. Owner verifies GL via `tools/engine3d_check.py`.
3. **Contact shadows are sprite-path blobs.** A cached radial disc,
   projected from the prop's declared footprint (`bridge.shadow_prims`
   auto-derives them from floor-resting boxes; humanoids get one in
   `add_humanoid` on both backends). Disc sizes are clamped to the
   viewport and the cache is bounded (an unclamped near-camera disc
   OOM-killed a parity run during development — fixed, see report).
4. **AO is baked into face colours.** `_annotate_ao` tags prims with
   floor height + wall footprints at `set_prims` time; `_mesh`
   darkens box faces within 0.7 m of their base and floor faces
   within 0.55 m of a wall. Sets opt into finer tessellation with
   `seg` (metres per face) so the gradient has faces to live on.
   Side benefit, recorded: finer wall tessellation fixed a painter
   occlusion artifact — the office GUARD banner decal now resolves
   in front of the back wall in every shot.
5. **One quality setting.** `quality_3d` (0 off / 1 low / 2 high,
   default high) in the Phase 9 settings kernel path
   (`settings_store` → `user_settings.SETTINGS`): off disables local
   lights, blobs and AO; low caps lights at 4. Bench:
   `tools/ae_bench3d.py` + caps in `tools/bench_budgets.json`
   (owner budgets office3d 20 ms / depot3d 12 ms at 480×270 internal;
   sandbox-recorded caps beside them).

## Consequences
- Every 3D golden was deliberately re-captured in the sandbox for
  the upgraded look (proof sheets `previews/upgrades3d/step1..4/` +
  `final_sheet.png` are the review); the owner re-baselines on the
  reference machine together with the B-038 restore.
- Steps 5–11 (post-FX, weather, cast shadows, character polish,
  textures, animated props, Blender import) remain ordered future
  work; each starts only when it can finish to the same bar.
