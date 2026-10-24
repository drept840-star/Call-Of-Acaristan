---
description: learned preferences, project conventions, and Do-Not-Repeat rules
budget_tokens: 2000
---
# Cerebrum

> OpenWolf's learning memory. Updated automatically as the AI learns from interactions.
> Do not edit manually unless correcting an error.
> Last updated: 2026-10-20

## User Preferences

<!-- How the user likes things done. Code style, tools, patterns, communication. -->

## Key Learnings

- **Project:** first-try
- **Description:** Top-down action game by **Retardovici Inc.**, running on the in-house
- **GL depth is painter-layer encoded** (`gl_FragDepth = ((7-layer)+lin)/8`).
  Raising a mesh to layer 7 makes it win every depth comparison. Never merge
  the held viewmodel into the world pass this way: `_composite` then treats
  every lower-layer sprite box overlapping the gun as occluded and takes the
  subsurface copy/restore path (snow: ~16 ms/frame). Keep the separate
  overlay pass.
- **Sprite callbacks can declare their true extent.** `fn.bounds` (exact pixel
  box, blob shadows) or `fn.bounds_m` + `fn.bounds_cap_px` (metres at the
  sprite's scale, lamps/haze/glow) shrink `_composite`'s depth box 4-20x.
  The generic `SPRITE_REACH_M = 3.5` box is far too big for small glows.
- **pygame.image.frombuffer is ~free but cannot flip.** FBO readback is
  bottom-up, so `frombytes(..., "RGBX", True)` stays; `frombuffer` only pays
  off for already top-down data.
- **M6 live set replay:** `m6world3d.pack_memo/ready/replay`; the train body
  is excluded (moving part) and the animated sprites are replayed by
  `TrainScene._draw_static_lights(train_offset=, snow_n=, beacon=True)`.
  `prepare()` builds the memo during stage load so the cut does not stall.
- **GL depth is painter-layer encoded, so layer-6 sprites need a physical
  depth test.** `gl_FragDepth` mixes the painter slot with linear z; world
  geometry can never be nearer than a layer-6 light. `gl._render` now packs
  physical depth (0..64 m) into the colour target's unused alpha
  (`u_depth_alpha`, opaque targets only) and `_composite` tests tagged
  `fn.light` sprites against it. The 3×3 anchor gate is enough; the 5×5
  version doubled the combat composite cost. Window glows/haze are
  anchor-gated but `light_soft` (no per-pixel background copy).
- **engine3d poses are dicts, so a hold can be composed from two of them.**
  `POSES["kneel"]` has no weapon hold (arms down, `rifle_p=40`), so a kneeling
  sniper looks unarmed. To shoulder a rifle on a kneel: start from
  `POSES["kneel"]` and copy only the spine/head/shoulder/elbow/rifle keys from
  `POSES["aim"]`, leaving the hip/knee keys from the kneel. `m6world3d.actor`
  then applies `life_pose` idle motion on top, so pass `amp=0.0` when the
  shoulder/optic contact must stay exact.

- **M6 top-down dressing is baked, flat and gated by the grid.** Floor variety,
  litter, steel plates and the exit thresholds live in `decor._floor_variety /
  _litter / _flat_detail` and are painted into the cached ground surface (zero
  per-frame cost). Litter only lands where `_open_spot` finds open floor, so a
  flat item never reads as cover or collides. Per-frame additions (lamp
  housings, IFF lamps, pickup ticks, exit lamps) draw after the light pass and
  measured +1.1-1.4% frame time in an interleaved A/B (raw run-to-run noise on
  this machine is +-30%, so never compare two separate bench runs).
- **M6 Guards carry a red IFF lamp** (same as the 3D train Guards): drawn after
  the light pass so a Guard in the dark stays a red pin; `decor.hides()` keeps it
  from showing through a tall prop. The wave status uses M5's `_draw_m5_plate`
  (slot x 214-554); the searchlight exposure chip sits right of it at x 562.

## Do-Not-Repeat

<!-- Mistakes made and corrected. Each entry prevents the same mistake recurring. -->
<!-- Format: [YYYY-MM-DD] Description of what went wrong and what to do instead. -->

- [2026-10-24] A "PS2 revert" request can already be undone: check
  `git diff <pre-revert> HEAD` before restoring anything. 3260f70 dropped the 3D
  PS2 path and 75294cd restored it; HEAD was byte-identical to 57acb6c.

## Decision Log

<!-- Significant technical decisions with rationale. Why X was chosen over Y. -->

- [2026-10-24] **3D PS2 kept, 2D PS2 dropped.** The 3D pipeline (engine3d, M5 3D
  cutscenes + `cutscenes/ps2mat.py`, M6 yard3d/train3d/bloc3d, `m6films`,
  `m6fx3d`, `m6world3d`) keeps the PS2 look. The top-down game never had a PS2
  pipeline in history and must not get one: M6 top-down matches the house art
  (art-pack tiles, hard edges, dark ambient), no pixel-art/affine/dither filter.
