# Rig collapse repair — first-pass handoff

## Apply
This is a SMALL OVERLAY, not the full game. Extract the original `First try.zip`
into a project folder, then extract this ZIP into that same folder, allowing
`src/missions/walking_attack3d.py` to be replaced. Keep the original assets.
A unified diff is included in `handoff/collapse_first_pass.patch` for review.
No voice lines, impact times, camera cuts, or unrelated gameplay were changed.

## Completed scope
- Traced the live path: walking_sim.py -> missions.walking_attack3d.py.
  src/cutscenes/oil_rig_3d.py is a separate implementation, NOT the live path.
- Fixed missing world translation for destroyed-rig geometry. Before the fix,
  all three rigs collapsed at world origin rather than their RIGS coordinates;
  the center rig even threw giant close-up beams across the camera.
- Added _collapse_parts and _rig_world_vertices. The derrick now folds in deck
  space and inherits its deck's pitch/drop, preserving the base joint.
- Reduced motion immediately uses the settled geometry rather than leaving a
  DESTROYED rig upright. This is not a full reduced-motion effects audit.
- Added tools/test_oilrig_collapse.py: five regression tests for standing/impact
  identity on all rigs, joint attachment, continuity, deterministic seeking,
  and stationary reduced-motion geometry.

## Validation
- python tools/test_oilrig_collapse.py: 5 tests PASS.
- python -m compileall -q src: PASS.
- Software preview rendered frames 990, 1020, 1058, 1080, 1430, 1498, 1890,
  1938, 2400. Before/after montage reviewed: world-placement bug is resolved.
- Full smoke suite FAILS join_loopback_fallback and mission4_cinematic_arrest.
  BOTH fail on unmodified original code too (baseline log included).
- GL backend SKIPPED: libGL/OpenGL 3.3 unavailable in this environment.
  Hardware GL parity and a normal in-game playback are NOT verified.
- Dependencies installed for testing: pygame-ce 2.5.8 and moderngl.

## Remaining scope — deliberately left for session two
1. Improve collapse choreography: current jacket is a rigid translated/rotated
   piece, not independently buckling legs. Deck/legs can intersect or visually
   separate. Create staged support failure, heavier deck descent and controlled
   tower folding with a clear final wreck silhouette.
2. Attach early flame origins to moving wreck geometry. Existing persistent
   fire sprites sit at the waterline immediately after impact, while the deck
   is still elevated. Keep heat/fire/steam/reflection spatially coherent.
3. Better water entry: splash/foam/waves and steam near actual contact locations,
   synced to existing rig_water_splash cue (~impact+68f). Avoid obscuring the
   collapse with big fire sprites or dense smoke. No new assets required.
4. Review ALL three strike shots and aftermath, at several intermediate ages;
   current first pass visually reviewed mainly the center sequence. Existing
   preview script mirrors the timeline rather than running actual gameplay.
5. Audit reduced-motion effects separately if changing flashes/shake/debris.
6. Preserve voice sequencing, impact_frames order (left, center, right),
   shot timing, existing renderer API, and deterministic frame-based poses.
7. Run tests/compile/smoke again; do not claim SMOKE TEST: OK unless it passes.
   Verify GL on a suitable machine if available; otherwise mark it unverified.

## Resume prompt
I attached my original First try.zip and the Rig collapse - first pass.zip
small overlay. Apply the overlay to the original, then read
handoff/README_FIRST_PASS.md and AGENTS.md. Continue only the SECOND HALF of the
rig-collapse repair. The live owner is src/missions/walking_attack3d.py, not
src/cutscenes/oil_rig_3d.py. First pass fixed missing world translation for all
three collapsing rigs, kept the derrick joint attached to the deck, and added
five passing geometry tests. Now improve support buckling and collapse weight,
track fire with moving geometry, and polish water contact/splash/steam while
preserving impact times, VO and cameras. Review left/center/right and aftermath,
run regression/compile/smoke checks, and return a small overlay ZIP plus results.
Two full-suite smoke failures reproduce on the original: join_loopback_fallback
and mission4_cinematic_arrest. GL could not be tested here. Work in bounded
steps; if you must stop, return the current files and another continuation
prompt. Do not claim the cinematic is finished without visual verification.
