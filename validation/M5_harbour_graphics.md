# Validation — M5 Harbour Graphics

## Verified scope

Canonical body/face mesh hashes for Biribel, Ucilev and Maru match the previous
integrated build. The state timeline, cameras, walking function and armed-pose
function have unchanged syntax-tree fingerprints. Weapon surface colours,
world art, lighting/shadows and picture sampling changed; character shapes,
grip targets and choreography did not.

## Passing checks

- Python compileall for src/ and tools/.
- Dedicated harbour-art check: cubic cast/choreography preservation, material
  and face-index validity, practical spill, water movement/reduced motion,
  supersampling and same-frame/out-of-order deterministic lighting.
- Existing focused finale check: two-hand contact, stance-foot stability,
  column clearance, head-safe framing, reveal order, player clock, timed cues,
  pause/resume, cancel/confirmed skip, automatic completion and save once.
- Empty-finale fallback and actual Maru escort gate, with temporary saves.
- Existing K9 regression check; no K9 source or assets overwritten.
- Installer tests against supplied original, M5 reset and M5 rebuild baselines:
  integrity, backup, no-op reinstallation, exact rollback, save/asset sentinels.
  Locally modified source refused before any changes.
- Full disposable installed game passes art and production-playback checks.

## Full regression suite

**131 checks OK, 1 FAIL, 1 SKIP.** The full suite therefore
still exits as failed, not an all-pass result.

- FAIL: mission5_sprites — stale baked tram_wreck v0, reproduced against the
  supplied original source before these cutscene changes. This patch does not
  replace unrelated baked gameplay sprites.
- SKIP: engine3d_gl_backend — no OpenGL 3.3/libGL context in this headless
  environment. The native software 3D fallback is exercised. GPU image quality
  and runtime performance remain checks on a GL-capable machine.

## Rendering and inspection

The review uses the actual production cutscene state, not a separately animated
mockup: 42 seconds, 1,260 frames at 30 fps, original 1000x700 screen, H.264 plus
stereo AAC native ambience/foley. The full encoded MP4 decodes successfully.
Internal film: 1200x572, filtered to 1000x476 before unchanged caption/controls.

Production frames were individually inspected for the escape, threshold,
threat/reaction, discovery, both dialogue mediums, lowering start/middle/end,
withdrawal and final radio/reaction. Pause, skip-confirmation and reduced-motion
states were inspected separately. Same-shot before/after composition was also
reviewed; its input frames were inspected individually, not just as a sheet.
Encoded opening and withdrawal-column frames were checked after compression.

Observed surface-layering faults in the reference painter renderer were fixed:
wall/floor cells replace oversized overlapping faces, share centres where
layered, and the close column uses a bevelled shell rather than floating seams.
Shared static vertices are indexed to reduce transform work. Environmental
light is restored each frame so the previous actor's light cannot tint water.

Measured headless software median in the final focused check was about 35 ms
per sampled frame. This is an environment-specific measurement, not a promise
of live 30/60 fps on all machines; the review export is offline at 30 fps.

## Important limits / next pass

- This is the graphics pass only. Awkward walking, holding poses and Maru's
  stopping/exit timing still need the planned animation/blocking overhaul.
- The passage now continues in geometry; Maru's animation has not been extended.
- Lighting is stylized: baked practical surface spill and projected posed-mesh
  ground shadows, not PBR, ray tracing or dynamic shadow-map illumination.
- The six new dialogue takes remain absent. Current playback uses subtitles,
  native ambience/foley and the existing recording-ready VO hooks.
- The exporter does not mix dialogue takes; check future recordings in-game.
- No interactive desktop playthrough on the user's hardware is claimed.
