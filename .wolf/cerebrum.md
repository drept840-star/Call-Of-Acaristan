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

- [2026-11-07] M3's between-stage cutscenes need proper 3D staging, not more
  effects over the old illustrated/gameplay-camera takes. User approved
  starting that pass; first implemented bridge is cell block -> Comms.

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
- **M6 rail 2.5D is pixel-bound even on GL.** With six live Guards and ten
  settled corpses, GL draws took 54–71 ms (flush ~10; art decode 12–21;
  lighting 13–18); the existing 2D painter took 9–10 ms. A 90% internal
  resolution still took 47–57 ms and visibly changes pixels. `draw._td3d_gate`
  selects the fast 2D painter *and its aim camera* for rail by default;
  `ACA_M6_RAIL_25D=1` restores 2.5D. Offscreen culling and software-only
  settled-corpse mesh caching help the opt-in/fallback but do not fix GL's
  per-pixel work. Use interleaved camera-matched probes, not separate runs.
- **M6 Guards carry a red IFF lamp** (same as the 3D train Guards): drawn after
  the light pass so a Guard in the dark stays a red pin; `decor.hides()` keeps it
  from showing through a tall prop. The wave status uses M5's `_draw_m5_plate`
  (slot x 214-554); the searchlight exposure chip sits right of it at x 562.

- **A peeled mission submits for real, never through the whole-painter host.** A
  mission's `game_draw` that calls `submit_frame` from *inside* a hosted
  `CustomDraw` flush submits after its FLOOR/DECAL layers were already drawn, so
  the world vanishes while the HUD (a later layer) still paints. `core.game_core`
  must call `_gr.frame(..., submitter=lambda q, x, y: mN.game_draw(x, y))` for
  that mission - nested submit is only a safety net for tools.
- **`engine.render2d` static layers must declare the bake's padded world.** The
  baked world PNG and `core.staticlayer` both pad the map up to whole chunks
  (`engine.assets.bake_chunk_layer`: 1792x1472 M1 map -> 2048x1536), and the
  callback paints floor past the map border. `StaticLayers.define(world_size=)`
  with the raw map size clips that edge chunk to 256 px, so the border strip
  renders as bare background (M1 golden: 7 % px, max diff 24).
- **M8 pintle LMG irons are obstructed; ADS is a gunner-eye -> front-post camera.**
  `lmg.mesh.json` carries AA ring stalks (gun-space z~0.07/0.18, y up to 0.241)
  sitting ON the rear-blade -> front-blade line, so a notch-and-post sight
  picture is blocked. `chase3d.ADS_EYE/ADS_POST` put the eye at the gunner's
  head and look at the front post top; eye and gun turn together on the pintle,
  so the post stays on the crosshair at every yaw/pitch. The sight line runs
  ~14 deg below the gun axis: do NOT "fix" that by tilting the gun (`pe` offset)
  - `_hold_at` clamps to PITCH_LIM and the pierce regressions sweep that
  envelope. Everything in the chase is ground-level behind the trailer, so the
  depressed sight line costs no usable aim envelope.
- **A probe that imports `app` must catch SystemExit.** `src/app.py` ends with
  `sys.exit()`, so module-level probe code after `import app` never runs unless
  the import is wrapped in `try/except SystemExit` (as `tools/m6_loop_probe.py`
  does). Symptom: the probe prints only the pygame banner and no results.
- **engine3d bakes the face normal into the colour, so quad winding matters.**
  `Obj.__init__` shades each face ONCE with `light.shade(col, nrm)`; a ground
  quad wound the wrong way gets a downward normal and k = ambient - sky
  (0.34 in the M8 set) instead of ambient + diffuse*0.42 + sky (0.83) - it
  renders 2.5x too dark. `quad_xz` winds up; a hand-built `m.face([...])` must
  too (order: left-south, left-north, right-north, right-south).
- **A weapon mesh and its grip set must be chosen together.**
  `m6world3d.hum(key, flags=...)` picks the mesh: "rifle" = the K-9 (grip
  "k9"), "lmg" = the LMG, "shotgun" = the Fallow 12, "os12" = the rig's own
  OS-12 (grip "os12", muzzle 0.64 m - as `ui/mp3d.py` has it), "ak74" = the
  code-authored AK-74 (grip "ak74", `cast3d.ak74_asset`). A flag with no
  branch (or no flag) leaves the rig with NO gun at all - the arms pose, the
  weapon does not exist. The guard and ally branches need the same care:
  `_guard_humanoid` builds its rifle from the spec, so the flag has to write
  `extra["rifle"] = "os12"` (the mesh AND `_weapon`/`_muzzle_z`/
  `_gl_spec_key` after it, or the GL renderer reuses the old VBO).
- **Emissive faces skip the fog in BOTH backends** (`_emit`: `if not em and
  depth > fs`; the GL shader sets the fog flag to 0 for emissive). Distant
  window/light quads therefore stay full brightness at 250-300 m, which is the
  only way to read a far-off town through the M8 set's fog (fog_end 300).
- **Everything past `fog_end` becomes exactly the fog colour**, so a "distant
  ridge" beyond 300 m is invisible (it matches the fogged ground). A backdrop
  hill only reads if its near slope is inside 300 m; keep its footprint clear
  of anything the player must see in front of it.
- **A muzzle flash is culled if the muzzle is off-frame.** The M8 over-the-
  shoulder camera collapses its boom in tight spots, and the rig's muzzle can
  then sit 40 degrees off the view axis - the flash mesh is correctly queued
  (the renderer counts it) but projects off-screen and draws nothing. Check
  the flash from an open stance before blaming the helper.
- **The rig's gun follows the BODY, and `body_yaw` eases toward `yaw`.**
  `raid3d._move` mixes `body_yaw` into `yaw` at 10/s, so a probe (or a
  teleport) that sets `sc.yaw` must run ~40 frames before the gun - and any
  bore-aligned flash - points where you expect. `joints["rifle_m"]` is the
  gun's rotation matrix and `joints["rhand"]` the trigger hand: the bore is
  `hand + m_apply(rifle_m, BORE)` and the bore axis is
  `m_apply(rifle_m, (0,0,1))`.

## Do-Not-Repeat

<!-- Mistakes made and corrected. Each entry prevents the same mistake recurring. -->
<!-- Format: [YYYY-MM-DD] Description of what went wrong and what to do instead. -->

- [2026-11-11] M8 chase: spawning chasers far back (past the draw cull) is only
  half the job — `_enemy_update` also CULLS enemies behind `tz - DESPAWN_BACK`.
  The old `tz-160` filter deleted a 350 m spawn the same frame, so smoke failed
  "chasers must spawn on the farm track". Spawn distance and despawn distance
  must be reconciled (`DESPAWN_BACK = SPAWN_BACK + 60`). Also: a proportional
  lateral steer (`step=(want-x)*dt*rate`) lags a curving `road_x`, so the actual
  lane offset overshoots the clamped avoidance target by ~speed*curve/rate on
  bends — clamp the TARGET, but expect the body to swing wider mid-swerve.
- [2026-10-24] A "PS2 revert" request can already be undone: check
  `git diff <pre-revert> HEAD` before restoring anything. 3260f70 dropped the 3D
  PS2 path and 75294cd restored it; HEAD was byte-identical to 57acb6c.
- [2026-10-26] Do not judge a mission peel by "the frame draws": if the world
  disappears but the HUD stays, the mission is still hosted as a whole painter
  (nested submit after its layer's flush). Check `_gr.queue().pending()` after a
  frame and `_gr.static_layers().stats()` for `built: 0`. Also diff only the
  golden tail - `ae_golden --only m1` renders 54 shots, so read the reported
  failure ids, not the count.

- [2026-10-28] M7 raid shots: take the aim ray before recoil and camera kick, or the shot lands above the crosshair. The over-the-shoulder camera sits ~0.85 m right of the body centreline, so test targets must sit on `_aim_ray()`, not on the player's centre.
- [2026-11-13] `m7world3d._fence` is axis-aligned only: it lays each rail as
  an axis-aligned box sized to the segment's BOUNDING BOX, so feeding it a
  diagonal segment turns the rail into a 16 m x 3 m slab. A fence that follows
  a curve needs its own polyline builder with yaw-aligned rails (see
  `set3d._rail_fence`). Same trap for a "sagging" wire built from `box()`: a
  yaw-rotated box stays horizontal, so the sag reads as a step - build a thin
  tube along the segment instead (`set3d._wire`).
- [2026-11-13] `STATE.m8_trap_cp` is the trap scene's resume point and it
  LEAKS between scenes and unit tests: `trap3d.begin()` reads it, so a test
  that sets it (or a previous run that died mid-fight) starts the next scene
  at checkpoint 1/2 instead of 0. Reset it in test setUp and after a
  checkpoint change.
- [2026-11-13] The M8 trap scene's borrowed `R.RaidScene` methods read
  `self.turn` (the raid's betrayal beat) - keep `self.turn = None` in
  `_setup` even though the M8 scene never uses it, or the borrowed
  `handle_event`/`_move` raise AttributeError.

## Decision Log

<!-- Significant technical decisions with rationale. Why X was chosen over Y. -->

- [2026-10-24] **3D PS2 kept, 2D PS2 dropped.** The 3D pipeline (engine3d, M5 3D
  cutscenes + `cutscenes/ps2mat.py`, M6 yard3d/train3d/bloc3d, `m6films`,
  `m6fx3d`, `m6world3d`) keeps the PS2 look. The top-down game never had a PS2
  pipeline in history and must not get one: M6 top-down matches the house art
  (art-pack tiles, hard edges, dark ambient), no pixel-art/affine/dither filter.
- [2026-10-25] **One art source for the top-down game.** M6 floors and walls come
  only from the art pack (`artpack.tile` / `artpack.wall`, `tools/make_art_pack.py`),
  never from `assets/tex3d` (that set is for the 3D side). New looks are added as
  new tile codes (`sn`/`st`); existing tile bytes stay fixed because M3-M5 goldens
  depend on them. Light follows M5: falloff pools, a white-balanced torch, hard
  bloom discs. A lamp on pale snow must stay under ~1.4x (`_COLD`), or it clips
  to a white blob. Signed off by the user.
- engine3d painter layers: a higher layer ALWAYS paints over a lower one (both
  backends; GL gives each layer its own depth slice). Terrain on layer 0 cannot
  hide layer-2 props: anything buried in it or behind a crest shows through and
  slides with parallax. Terrain that props stand on or behind (M7 hill rings)
  must be layer 2 and closed (back slope). Flat ground can stay layer 0 if no
  prop goes below y=0.
