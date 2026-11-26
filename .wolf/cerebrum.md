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

- **GPU bloom is a cascade, not independent levels.** `gl_post._run_bloom` must
  sample the PREVIOUS level's result (`src_tex`) as each level's horizontal-blur
  source. Reading that level's own `ta` (its vertical-blur write target) works for
  level 0 by coincidence (`ta == src_tex`) but levels >= 1 read an f2 texture that
  has never been written — its bytes are whatever GPU memory the driver recycled.
  Symptom: M5 Print Works went magenta/rainbow only AFTER an m5x 3D cutscene
  (whose 614x345 frames reused that memory); with cutscenes off the memory was
  zeroed and the frame looked fine. A pass that only forces `bloom=0.0` (M5
  quarter, when CPU items exist) never exposed it. When a colour bug depends on
  "some earlier scene ran", suspect uninitialised GPU/FBO memory in a pass that
  only some hosts execute, not shared shader state.

- **A PostPipeline's bound source texture must outlive the whole `render_to`.**
  `PostPipeline.bind_source` may bind `r._active_color_tex`, which is the
  per-pipeline `_atmos_tex`. Calling `_drop_atmos()` anywhere between bind and
  `_draw_final`/`_run_bloom` (e.g. accidentally placing it in `_ensure_bloom`,
  which also calls `_drop_bloom()`) releases that texture's `mglo`; the next
  `tex.use()` fails with `AttributeError: InvalidObject ... use`. Keep
  `_drop_atmos()` in `release()` and `_ensure_atmos()` only. Also: a `"""` line
  is not a unique insertion anchor in gl_post — insert shader strings BEFORE
  `_FINAL_FRAG = """#version 330`, never after its opening delimiter.
- **Applying hand-written unified diffs with wrong hunk counts:** `git apply
  --recount` still consumes the following file header when a hunk's old count is
  wrong; `git apply --ignore-space-change` does not bridge CRLF/LF. A small
  context-matching applier (strip `\r`, search the whole file, replace) is
  reliable, but empty old-sequences (`@@ -N,0`) must be avoided — they insert at
  the hint's first index, so a pure-add hunk needs a neighbouring context line.
- **`tools/sync_arch_map.py` has no `--help` flag.** Any argument (including
  `--help`) triggers a full regeneration that rewrites hand-written prose into
  a condensed style, producing a ~500-line diff. To undo, capture `git diff`
  bytes with Python (`subprocess.check_output`, write `wb`) — PowerShell `>`
  redirects decode as cp1252 (mojibake `§`) and write UTF-16 with CRLF, so
  `git apply -R` rejects them. Update the map with targeted `edit`s instead.
- **Animation endpoint tests must respect beat boundaries.** At exactly
  `hit_s`, `mansion3d._andrei_death_anim` has already left the player-shot
  backpedal branch and entered the shared pinned-rack shake, which adds ±0.025 m
  jitter; `assertAlmostEqual(off[0], ANDREI_RACK_DX, places=3)` fails although
  the travel curve is correct. Use a tolerance sized to the next beat's jitter.

- **M8 TrapScene/MansionScene BORROW RaidScene methods by assignment** (class
  attributes like `_ground_move = R.RaidScene._move`), they do not subclass it.
  Any NEW RaidScene helper called from a borrowed method must also be borrowed:
  adding `_anim_ctl`/`_debris_ctl` to RaidScene._move/_player_pose/hp without
  `_anim_ctl = R.RaidScene._anim_ctl` on TrapScene and MansionScene crashes the
  first M8 update with `AttributeError: ... object has no attribute '_anim_ctl'`.
- **Verlet ragdoll friction belongs once per step**, not inside the constraint
  iteration loop. Applying ground friction each of 5 iterations bleeds horizontal
  momentum ~5x and pins the body at a ledge instead of falling off it.
- **Never put a frozenset (or any set) as a public default argument** when an API
  snapshot tool hashes `inspect.signature`: its repr ordering depends on
  PYTHONHASHSEED, so record/check disagree between processes. Use `None` and
  resolve inside the function.

- **A humanoid rig auto-grounds every frame**: `Humanoid.build`/`pose_world`
  snap the lowest foot vertex to `pos[1]`. Any gait whose leg span shortens at
  stride split (straight knees + big hip swing) makes the body pogo vertically;
  compensate with a cosine-derived positive `lift` on sprint only, and keep walk
  lift at 0. Also: never gate an IK solve on a per-frame `abs(left.y-right.y)`
  threshold when both feet are already on flat ground.
- **`pose_world` returns only 5 world joints** (pelvis/chest/head/lhand/rhand);
  the other limb nodes live in `places` (left uarm 4, thigh 7, shin 8; right
  uarm 10, thigh 13, shin 14). Build ragdolls from `places` + matrices, not from
  those 5 joints plus default standing offsets, or rest lengths break for
  crouched/aiming/scaled actors. Ragdolls also need min-distance constraints on
  shoulder/hip/knee pairs, or they invert into origami.

- **`MultiFloorNav` has three caches that must invalidate together.** Since
  2026-11-19 the string-pulled waypoints (`_pulled_cache`), static neighbour
  tuples (`_nbr_cache`) and the dynamic-obstacle `_blocked` bytearray are all
  derived state: `_sync_blocked()` rasterises `_dyn_boxes`/`_dyn_circles` once
  per `_dyn_ver`, and `_static_neighbors()` caches geometry WITHOUT the blocked
  check (it uses `_layer_step_raw`) so it survives a pure dynamic-box change.
  Invalidate `_nbr_cache` + `_pulled_cache` on `add_link` and `_pulled_cache` on
  both dynamic setters; forgetting either makes paths reuse stale geometry.

- **When an LRU evicts "entries not live this frame", the just-added entry must
  count as live.** In `engine3d.gl.GLRenderer.add_resident()` the eviction pass
  runs before the new entry is appended to `_res_draw`, so a frame that queues
  more chunks than the cap (M6 yard: 196 chunks vs cap 128) evicts and releases
  the VAO it just created, then queues the released handle -> hard crash with
  `InvalidObject ... render`. Include the new key in the live set (`| {key}`).
  Same pattern applies to any cache whose "in use" set is assembled before the
  current insertion is registered.

- **One GLB can feed several rigs via path-aware face tagging.** `chase_set._load_glb(path, return_paths=True)` prefixes each face with its node path, so `maru_gunship_parts()` splits root nodes `heli_fuselage`/`heli_tail_boom`/`main_rotor`/`tail_rotor` 1:1 in metres (no bake, procedural `flight_fx` meshes are the missing-asset fallback). **Roll polarity is opposite across the two submit paths:** `CS._xf`/`_rot_rt` apply `rot_z(+roll)` while `flight_fx.heli_matrix` applies `rot_z(-roll)`, so every shared gunship submit must pass `-hroll` or a banked airframe tilts the wrong way. `gunner_eye`/pintle/seat anchors must come from the GLB info dict (`floor_y=0.574`, `pintle_top=(0,1.26,0)`), not the old procedural offsets.

- **Cutting a GLB hull by a y-range can tear the roof.** `_vip_open_body` removed faces up to `y=2.45` (above the roof eave) with nothing behind the hole, so night sky leaked through the opposite side and the standing actor punched through the lintel. Keep the doorway recessed (`y 0.56..2.02`), SEAL a dark interior box behind the cut, and place the actor below the lintel (`POSES["crouch"]`). Also: from a third-person camera, an airframe hovering over a balustrade occupies the rail footprint - move the hover outside the rail (`x=12.4` vs `x=+9.0`) instead of trying to crop it. For a door-gunner view, the eye must sit on the doorway threshold (`lx=0.96*tanh(3.2*sin(rr))`), not the center aisle, or cockpit pillars block the target.

- **[2026-11-21] Both FPV and film gunship paths now read the GLB anchors (supersedes the earlier "FPV no longer reads GLB" note).** `chase_set.maru_gunship_fpv_parts()` clips the same `maru_gunship.glb` faces for first person (drops `cabin_b_pillar_*`/`quarter_mullion_*`/`a_pillar_*`/`windshield_center_mullion` and eye-level rocket pods/tubes/pylons, clips rear walls/doors to `y<=1.04`, lights `avionics_*`), and `put_maru_gunship(..., fpv=True)` submits it under a separate `maru_fuse_fpv[_burnt]` cache key. `flight_fx.draw_cabin_and_gun` and `m8dutyfilms._gunship(..., fpv=True)` both use `info` anchors (`floor_y=0.574`, eye `floor_y+1.06`, `pintle_top`, `pilot_seat`, `roof_beacon`); the old `FPV_*` local constants are now fallback-only. Shared submits must pass `-hroll` (CS `_xf` uses `rot_z(+roll)`, FX `heli_matrix` `rot_z(-roll)`). For sightline work edit the clip sets/eye formula, not the old procedural offsets. Also: rockets now fly in pure world space (`dir=normalize(vel)`, no `hvel` addition/loft), so smoke trails behind the nose; lead-intercept guidance at launch and every tick via `_heli_vel()` + `_rocket_intercept()` (solves `|(tgt-p)+vh*t| = s*t`), current speeds `ROCKET_V=22`/`ROAD=28`/`AIR=26`, `ROCKET_DMG=18`; hit sphere only 0.90 m (no free heat cooling on a rocket kill), road gate `dz>90/58`, relaxed to `60/36` mid-`rk_tele` windup, `<=180 m` ground / `220 m` air (rpg/aa active 185 m), `+-72 deg`, and the HUD lock diamond only inside 105 m. Flight altitude for the road canyon is 21.0 m cp1-2 / `ALT=19.5` cp3-4 with fog `(0.0028, 0.0, 2.2, FS.FOG)`; `flight_set` lightens night albedos, uses FOG (12,17,30) 130..560, and focuses lamps 55 m ahead along the aim direction. `e["rk_tele"]` is separate from bullet `tele`, so rocket windups do not re-roll the RNG or re-check range.
- **[2026-11-23] GL `light` sprites get a hard horizontal ground cut when their anchor is above ground.** Use `phys_occ=True` with an `occ_bias` around the sprite radius (`rad_m * 0.8..0.9`, or `max(0.8, rad_m * 0.9)` for ground spills) for blast flashes and fireballs so nearby foreground ground does not clip the bottom half along a depth scanline.

- **[2026-11-23] Owner-supplied ridge patch had two import/draw-time traps.** A parenthesised generator cannot be concatenated to a tuple (`(x for ...) + (y,)` raises `TypeError` at import) - wrap it in `tuple(...)` when extending an existing generator-built constant such as `ridge3d._PAD_LIGHTS`. Also `ridge3d._off(dx, dz)` returns a 3-tuple `(x, 0.0, z)`, so `for (mx, mz) in (_off(...), ...)` fails at draw time; unpack `(mx, _my, mz)`. Render the owner's contact-sheet probe before declaring a visual patch done - neither error is caught by `compileall` or `smoke --only m8`.

- **[2026-11-24] A missing render pass can be a truncated file, not a logic bug.** If a function ends mid-expression and a queued-delta probe reports 0 (e.g. `m8duty_crowd.draw_maru_with_crutches` stopped at `cuff_m = _basis_from_xy(...)`), check the file tail before debugging conditions/caches. Probe shape: compare `len(getattr(r, "_dyn", getattr(r, "_tris", [])))` before/after calling the draw helper - `delta=1` confirms the final `r.add_dynamic(...)` now runs. `compileall` and `smoke --only m8` both pass on a truncated tail, so only the delta probe catches it.

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

- [2026-11-15] Weapon-swap animation is split by pipeline: 2.5D shares
  `game.topdown3d.apply_swap_pose(pose, k)` (campaign `m1.draw3d._body` for
  every player draw + `ui.arena_view3d`); 3D owns its own `_swap_pose` in
  `m8/revenge/trap3d.py`. The weapon mesh must flip at the midpoint, so
  `_switch_weapon` updates `self.weapon` immediately (tests/HUD/toast) while
  `_draw_player` keeps drawing `_swap_from` until `swap_u >= 0.5`; `_fire`,
  `_begin_reload` and ADS are gated on `swapping > 0`. Keep the `instant=True`
  path for the climb (snapping mid-swap would strand the old mesh).

- [2026-11-19] `cutscenes/revive3d.step()` owns `scene.hold` and zeroes it on
  its inactive (`who is None`) path. A caller that only wants its animation
  decay (e.g. M7 `raid3d._hold()`'s pinned-Alex beam-lift) must save/restore
  `scene.hold` around the call, or its own hold accumulator resets every frame
  and its completion timer is unreachable. Before "re-enabling" a mechanic,
  check whether a shared helper silently writes the same mutable field.

- [2026-11-20] `tools/sync_arch_map.py` regenerates the ENTIRE `<!-- AUTO:sigs --> ... <!-- /AUTO:sigs -->` block, so a hand-written note placed inside it is silently dropped (the old `_CONTRAST`/stucco textures note vanished). Keep prose OUTSIDE those markers; when regenerating a stale map, diff against a backup and restore any dropped prose BEFORE re-running `--check`. §8.1 rows belong to `map_assets3d.py` but that tool PRESERVES existing row text, so hand-edits there are safe.

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
