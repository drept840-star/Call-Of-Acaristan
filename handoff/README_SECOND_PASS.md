# Oil-rig collapse repair — cumulative second pass

## Installation
This ZIP is a small, CUMULATIVE OVERLAY, not a full game archive.
Extract the original First try.zip into a project folder. Extract this ZIP into
that same folder and allow replacement. It also applies over the first-pass
repair; the first-pass ZIP is not required. Preserve all original assets.
Back up src/missions/walking_attack3d.py if you have made your own edits.
Only two executable files are supplied:
- src/missions/walking_attack3d.py (updated live renderer)
- tools/test_oilrig_collapse.py (new regression tests)
Review the full original-to-final diff in handoff/collapse_cumulative.patch.

## Repairs included
First pass: corrected missing world translation for all destroyed-rig parts,
kept the derrick base attached to its deck, and made reduced-motion geometry
settle immediately instead of leaving destroyed rigs upright.

Second pass:
- Authored staged collapse: short resistance, accelerated descent into water
  around the existing +68-frame splash cue, then settlement by +90 frames.
- Subdivided jacket columns/bracing to allow angular bowing. Footings stay
  pinned; support tops follow the moving slab. This is deterministic authored
  geometry deformation, NOT a rigid-body structural physics simulation.
- Derrick folding is delayed and composed with its parent deck transform;
  right-hand rig falls in the opposite direction.
- Fire sockets follow the deck; submerged sockets quench toward a smaller
  surface oil fire. Smaller flames/smoke preserve the readable falling steel.
- Added depth-correct broken foam rings and ballistic spray around the moving
  deck's low edge at water contact, plus a short steam plume.
- Clipped underwater wreck polygons at a stable mean waterline to stop the
  software painter drawing submerged steel over the sea. Wave-surface precise
  intersections are not simulated.
- Reduced motion suppresses new spray/steam, sparks, impact flash and roll;
  settled geometry and its fire/smoke animation phase remain stationary.
  Ambient rain/sea/camera drift are retained; this is not a full accessibility
  audit of all game effects.

## Unchanged
Impact frames (left 1410, center 990, right 1850), voice sequencing, dialogue,
existing sound cues, and shot cuts are unchanged. All existing src/*.py files
except missions/walking_attack3d.py are byte-identical to the original ZIP.
OilRigAttack3D._camera is AST-identical to the original. Normal-mode cameras
are unchanged; reduced-motion mode no longer applies impact roll.
The separate src/cutscenes/oil_rig_3d.py implementation is not the live path
and was intentionally not changed.

## Validation performed
- 11 geometry/effect regressions: PASS (log included).
- python -m compileall -q src: PASS.
- Final full smoke suite: FAILED, with exactly the same two checks observed
  on the original project: join_loopback_fallback and mission4_cinematic_arrest.
  Original baseline and final logs are included; this is NOT a full-suite pass.
- python tools/engine3d_check.py: GPU unavailable (libGL.so not loaded), so GL
  parity/performance is NOT verified.
- Software previews captured and visually reviewed for ALL THREE strikes at
  +0, +18, +36, +54, +68, +76, +90, +120 frames and aftermath 2400/3000.
  Contact sheets are included. Verification was offscreen still-frame review,
  not normal interactive gameplay or an audio-synced playback review.

## Local checks
From the project root with dependencies installed:
python tools/test_oilrig_collapse.py
python -m compileall -q src
python tools/smoke_test.py
python tools/engine3d_check.py
python tools/oilrig_preview.py tools/out/oilrig 1026 1058 1066 1110 1446 1478 1486 1530 1886 1918 1926 1970 2400 3000

## Remaining target-machine verification
Run the actual walking mission with its audio and UI. Review the collapse
animation at playback speed and verify the existing +68f sound sync. Verify GL
on a machine with an OpenGL 3.3 context. The main unresolved risk is hardware
renderer appearance/performance, not a known remaining coordinate bug.
The existing full-suite smoke failures also remain outside this repair scope.

## Optional continuation prompt
I attached First try.zip and Rig collapse - second pass.zip. Apply the cumulative
overlay, then read handoff/README_SECOND_PASS.md and AGENTS.md. The authored
collapse, attached fire, splash/steam and underwater clipping are implemented,
and 11 regression tests pass. Do not redo the repair from scratch. Focus on
final validation: actual walking-mission playback with audio/UI and hardware
GL appearance/performance, preserving timeline and camera cuts. Software still
frames of all three rigs and aftermath were reviewed, but interactive playback
and GL were not verified. Two smoke failures also occur on the original:
join_loopback_fallback and mission4_cinematic_arrest. Work in bounded steps;
return any small corrective overlay and truthful verification results. If the
environment cannot run GL/game playback, state the limitation rather than
claiming those checks passed.
