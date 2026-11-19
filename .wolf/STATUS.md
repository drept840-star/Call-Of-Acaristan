---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1000
---
# STATUS — first-try

> Read this FIRST when resuming. Last updated: 2026-11-19

**LATEST (2026-11-19): gameplay sweep (Alex-well class bugs)** - 6 fixes, uncommitted:
M8 trap checkpoint retry restores both guns' ammo (`_cp_snapshot`); trap/mansion `_loot` leaves
the body's ammo when both reserves are full; mansion `near_revive` same floor only; trap kiosk
gate moves Bodi to post 2 like `_clear(1)`; M1 hotwire "not yet" E no longer eats the hotwire
tutorial (own flag `hotwire_not_clear_said`); M1-M5 pickups at full stay on the ground.
Tests: `tests/unit/test_gameplay_sweep.py` (9, all fail/error on old code), smoke
`m1_hotwire_tutorial_after_early_e`. Gates: compileall, smoke `--fast` OK, sync_arch_map OK.
Pre-existing reds untouched: `test_m8_trap_mechanics` smoke-canister + guard-truck tests.
Not eyeballed in game. Map: ARCHITECTURE_MAP "Gameplay sweep (2026-11-19)"; buglog `*-20261119`.

**LATEST (2026-11-19): physical-stride walking upgrade across 3D combat, 2.5D and films** -
owner's exact 9-file patch applied verbatim (`engine/anim/rig3d.py`, `m7/raid3d.py`,
`m8/revenge/trap3d.py`, `m8/duty/mansion3d.py`, `m6/yard3d.py`, `m1/draw3d.py`,
`missions/walk3d.py`, `cutscenes/m6world3d.py`, `cutscenes/m7world3d.py`) + map +
one obsolete unit assertion. One necessary addition: `locomotion_pose` keeps
`s = math.sin(phase)` because the patch's new `spine_r` term still uses `s`.
`rig3d`: `_cycle_len` (1.16 m crouch, else 1.38..2.00 m by speed/sprint) makes
`LayeredAnimState.stride_phase` advance by ground distance (`stride_gain/2` now a
cadence factor); `_leg_cycle` replaces symmetric `sin` legs with asymmetric
heel-strike/loading-shock/midstance-vault/toe-off/swing plus pelvic `body_r`,
lumbar `spine_r` counter-tilt, athletic idle and a 0.850..0.878 m CoM target;
`compose` finally consumes `secondary` inertia and stabilises head. `_held`/
`_shotgun_hold` sync `rifle_y` to the twist delta; new `raid3d._sprint_carry_hold`/
`apply_sprint_carry` give a cached Fallow 12 / OS-12 high-port sprint carry
(prewarmed in Raid/Trap/Mansion `_warm`), with K-9 stride bounce in `yard3d._gun_frame`.
Guards/allies in all four 3D scenes phase from distance travelled (yard accumulates
`_gphase`); Trap's catwalk `_move` now runs `LayeredAnimState`. 2.5D `_motion` in
`m1/draw3d` + `walk3d` keeps a 7-slot cache with `STATE.dt`; `WALK_RAD_PER_M` retired,
`_gait`/`_person` blend into `locomotion_pose` instead of `pose_run`. Films:
`m6world3d.walk` adds ankle/head/elbow follow-through while keeping leg IK and
`body_r=0` (walk_slip < 1 mm); `m7world3d.walk_pose` delegates to `locomotion_pose`.
Gates in requested order: normalize OK, compileall OK, api snapshot OK (92/676 +0),
hold OK, unit discover 625 = 5F/6E (same pre-existing set; the only new failure was
the obsolete `test_engine_anim` idle-`lhip_p`==0 assertion, updated to compare
`locomotion_pose(0,0,0)` because the new idle stance is deliberately non-zero),
targeted smoke `--only m1,m6,m7,m8` OK. `check_boundaries` pre-existing E4 credits +
W1 89 (this patch adds no shared->mission edges). `smoke --fast` only the 3
documented pre-existing reds (`mission5_shadow_finale`, `mission4_cinematic_arrest`
fade_out_music fakes, `mission8_vertical_slice` phase "clear"). `sync_arch_map`
regenerated idempotently; ARCHITECTURE_MAP bullet added. Owner still needs the
in-game eyeball: --dev-mission7-raid / --dev-mission8-trap / --dev-mission8-mansion /
--dev-mission6-yard, --dev-walk, --dev-m1-game.

**PREVIOUS (2026-11-19): M7 raid - you can free Alex under the fallen well beam again** - root cause: the shared-revive rollout added `REV.step(self, dt, None, False, ...)` to `m7/raid3d._hold()`'s pinned-Alex branch just to decay a leftover Bodi revive animation; `revive3d.step()`'s inactive (`who is None`) path zeroes `scene.hold`, which Alex's beam-lift timer shares, so hold reset to one frame's `dt` every frame and never reached `HOLD_S["alex"] = 1.6`. Fix: save/restore `self.hold` around that `REV.step` call; `REV.step` and Bodi/M8 callers untouched. Added `M7RaidTests.test_holding_e_frees_pinned_alex` - verified it FAILS on the buggy code (hold 0.0167 after 30 frames) and passes with the fix. Gates: focused unit 30/30 OK, `smoke --only m7` OK, compileall OK, ae_normalize dry OK, `sync_arch_map --check` OK; final `smoke --fast` shows only the three documented pre-existing reds (M5 shadow finale + M4 cinematic arrest `fade_out_music` harness fakes, M8 vertical slice phase 'clear'). Map updated.

**PREVIOUS (2026-11-19): 3D frustum culling across engine3d + heavy sets** -
owner's 8-file patch applied verbatim except ONE owner-approved one-line fix
(see below). `engine3d/core`: `frustum_cull`, `visible_frustum`/`visible_ortho`,
sphere culls on shadows/sprites/lines. `engine3d/gl`: baked `Obj`s >32 m split
into 32 m XZ slices; per-pass culling (main/sun-ortho/spot) in
`_visible_static_runs`/`_pass_cull_fn`; resident chunks culled + 128-entry LRU;
rigs/dyn/sprites/lines/lights/pools culled with `culled_*` stats.
`m6world3d.pack_memo_end` splits live memo into 24 m chunks. Mansion set bakes
shell/hall/rooms/terrace/grounds/surroundings separately (Early-Z preserved);
mansion3d/raid3d/yard3d skip off-screen ragdolls, Andrei, cash, scorches,
car FX, Volkov, pig. 2D untouched; `r.frustum_cull=False` opts out.
**Owner-approved deviation:** verbatim patch hard-crashed M6 yard on frame 1
(`InvalidObject ... render`): when a frame queues >128 memo chunks (yard = 196),
the new LRU key is not yet in `live`, so the VAO just created is evicted+released
and then queued. Fix: `live = {id(e[0]) for e in self._res_draw} | {key}` in
`add_resident`. Gates: normalize/compileall OK, `engine3d_check` 5.71% parity OK,
smoke `mission6_vertical_slice,engine3d` OK, `ae_bench_scenes` all 9 scenes run,
full `--fast` (3 pre-existing reds), unit discover 624 (5F/6E unchanged),
boundaries E4/W1 89 unchanged. Map updated.

**PREVIOUS (2026-11-19): M8 Mansion 3D nav/fragment perf pass** - owner's exact
6-file patch applied verbatim. (1) `engine/collision/nav.py`: `MultiFloorNav` gains
`_pulled_cache` (string-pulled waypoints), `_nbr_cache`/`_static_neighbors`
(static neighbor geometry) and a `_blocked` bytearray synced once per `_dyn_ver`
by `_sync_blocked()`; `_layer_step_raw` split out; all caches invalidated in
`set_dynamic_boxes`/`set_dynamic_circles`/`add_link`. (2) `gl_post._ATMOS_FRAG`
gates SSR on `refl_w > 0.08`. (3) `mansion3d`: `_warm()` now prewarms guard holds,
car/chandelier meshes and the ~12k-cell `world.nav()`; warm errors print a
traceback; `marble_refl` only inside on the ground floor; `_draw_enemies` reuses
one `_OneEnemy` stand-in. (4) `mansion_brain`: `nav_at` throttles + `door_locked`
skip in `_steer`/`_walk_ally`, cp-0 ally follow point clamped to `GATE_Z+1.2`.
(5) `mansion_set`: `money_bundle(..., detail=False)` for baked pallets, grass
seg 10->40, `_grounds` baked last for Early-Z, `house_lights`/`pools` `near=`
cull to 6/10 fed from `frame()`'s `tgt`. (6) `mansion_world`: `_dyn_box_aabbs`
cached and reused by `ragdoll_boxes`/`nav`/`move`, plus `_LOS_STATIC_BW` for
`los3d` static rejection and `_STATIC_BW.ray()` for short `ray_hit` probes
(owner's follow-up hunks, applied verbatim). Gates: normalize OK,
compileall OK, nav + m8_duty unit tests OK (`test_gl_composite` 6/6),
`engine3d_check` 4.14% OK, smoke `mission8_duty,engine3d` OK. Map updated.
`ae_bench_scenes` mansion 14.45 avg / 9.93 p50 ms (GL, 90f). Final gates show
ONLY pre-existing reds: `smoke --fast` = `mission8_vertical_slice` + the two
`fade_out_music` harness fakes; unit discover 624 = 5F/6E (ragdoll jitter
3.89>0.05 in CapsulePhysicsTests - untouched by this patch, all nav tests pass;
m5 Channel.id x2, m8 chase font-quit x2, m8 trap smokes/truck, raw-loads,
m6 exposure 173>170, m8 chase silhouettes 8!=10, pytest missing), boundaries
E4 ui.credits + W1 89 (the only W1 edge in a touched file is the pre-existing
`engine3d.gl_post -> missions.m1.grade3d` lazy import). No new reds.
**Known edge case, owner chose to KEEP VERBATIM:** the new short-`ray_hit`
fast path uses `BoxWorld.ray()` which returns the FIRST hit (t=0 when the origin
starts inside a box); the `1e-4 <` guard drops it without checking the next
box, so 44/1323 realistic downward probes returned a farther hit than the
legacy scan (e.g. (-12, 2.25, 26) fast 4.27 / legacy 1.80). `los3d()` is fully
equivalent (0/2000 random probes). Documented in ARCHITECTURE_MAP.md; no code
change.

**PREVIOUS (2026-11-19): M8 Andrei hitscan room-entry guard** - owner supplied exact
patch applied verbatim across 4 files + map + buglog. Root cause: `mansion3d._fire`
tested Andrei's spheres whenever state was `idle`/`intro` with no room-entry guard,
so stray Grand Hall / front-door rounds through the open 2 m `BACK_Z` doorway
(x -7..-5) could trigger `trigger_andrei_death(cause="player")` before the player
entered the security room; `mansion_world._static` also lacked colliders for the
rendered doorway lintels. Fix: `mansion_brain.in_security_room(x,y,z)` is the single
interior-bounds test, reused by `_andrei_update` and by `_fire`'s `can_hit_andrei`
(intro always hittable, idle only from inside the room); `_fire` seeds
`andrei_zone/end/dd` up front instead of `locals().get()`; added the two BACK_Z
lintel colliders. New regression test
`test_andrei_cannot_be_shot_while_idle_from_outside_room`. Gates: normalize OK,
compileall OK, unit 6/6 OK, smoke --only m8 OK. Map + buglog updated. Note:
`--only m8` matches ZERO checks (names contain "mission8", not "m8"); the real
`--fast` gate shows three PRE-EXISTING reds unrelated to this patch -
`mission8_vertical_slice` (`assert sc.phase == "climb"` yields "clear"; confirmed
by reverting all four edits and re-running the isolated check - still fails),
plus the known `mission5_shadow_finale` / `mission4_cinematic_arrest`
`fade_out_music` harness fakes. Duty itself (`mission8_duty`) is green.

**PREVIOUS (2026-11-18): hit-context death upgrade (14 files)** - owner's exact
patch applied verbatim across physics.py, rig.py, m6world3d.py, death3d.py and
all four 3D combat scenes/worlds/brains. Soft spine/neck range links, ribcage /
shoulder / hip / neck constraints + wall-slump friction, hit-aware active poses
(head whip, shotgun/overkill punch, gut/leg/melee, catch-step, bracing, head
settle), dropped-rifle rigid body via `fall.draw_gun(r)`, `Fall` hit-context
kwargs and `ragdoll_boxes()` on all worlds; no caller contract broken.
Gates: normalize/compileall/API snapshot OK, boundaries pre-existing E4/W1,
smoke --only m6,m7,m8,engine3d,collision OK, ae_ci --quick pre-existing reds.
**TWO NEW REDS FOUND - owner decision needed:** (1) headless probe: the new
single-node constraint pushes in `_apply_anatomical_limits()` are not
`prev`-compensated and inject momentum - settled root drifts 2.5 m at realistic
push 0.3 (5.8 m at push 1.0, 0.67 m at zero push); runtime monkeypatch disabling
the method drops drift to 0.003-0.25 m. (2) unit discover now 5F/6E (was 4F/6E):
`test_debris_and_ragdoll_collide_with_walls_and_drop_off_ledge` fails, chest
y=1.43 (expected <0.45) - the ledge-drop/ragdoll constraint interaction.
Map updated with both anomalies; no fix applied (verbatim patch preserved).

**PREVIOUS (2026-11-18): active-ragdoll muscle tone** - owner's exact patch to
`engine/collision/physics.py` + `cutscenes/death3d.py`. Pure Verlet lost all
tone on frame 1 (instant limp sacks); `Fall` now drives `RagdollBody` with
damped PD springs toward authored reactions before collapsing: `_active_pose`
returns stagger/clutch/kneel/buckle pose + yaw and separate upper/lower tone
envelopes (0.28 s, knee-drop 0.54 s), `_apply_muscle_tone` pushes nodes via
`prev -= dv*h` (260/240 stiff, 28 damping) and gives pelvis support only when
a foot/knee is within 0.18 m of the floor (so truck-bed/catwalk pushes lose
footing immediately). Track 3 fires a one-shot topple at a>=0.38 s; blast
kills skip tone. `RagdollBody` drag 0.962 and ground rebound 0.04 make limbs
thud/drape. Impulses softened (push 1.1-2.8, less launch). Headless 40-fall /
6 s probe: root y 0.00, max drift 0.138 m, 0 nonfinite (rest forced at 4 s).
Gates: normalize/compileall OK, boundaries pre-existing E4/W1, API snapshot
OK (92/676), unit 614 same 10 pre-existing reds, smoke --only m6,m7,m8 OK.
Map updated; no caller/engine3d changes.

**PREVIOUS (2026-11-18): ragdoll-bone bridge** - owner's exact three-file patch;
no mission caller touched. `physics.py`: `RagdollBody._apply_anatomical_limits()`
knocks knees onto a backward 1-DOF hinge plane and stops backward elbow snap,
called per constraint iteration. `engine3d/rig.py`: new `_basis_xy`/`_col_x`
helpers, `Humanoid.ragdoll_nodes()` (15 world nodes, no chest-Z bias) and
`Humanoid.places_from_nodes()` (orthonormal slot matrices with socket
continuity, scale/PART_FB preserved, boot-floor pitch clamp); `pose_world`/
`build` accept `{"_places":...,"_joints":...}` and skip `_placements` and the
`-miny` auto-grounding shift (GL root `(0,0,0)`). `death3d.py`: `Fall` seeds
the ragdoll from `ragdoll_nodes`, zero-velocity depenetrates against boxes,
applies track/blast impulses, sub-steps `rag.step(h<=1/60, iters=6)`, tracks
`fall.chest`, caches `rest` as a `_places` pose, and re-floors the cached root.
Headless 40-fall / 6 s probe: root y 0.00, max drift 0.116 m, 0 nonfinite.
Gates in requested order: normalize OK, compileall OK, boundaries pre-existing
E4/W1 88, api snapshot OK (92/676 +0), unit 614 same 10 pre-existing reds,
engine3d parity OK, smoke --only m6,m7,m8 OK. Map updated (new authoritative
ragdoll-bone bridge bullet; prior death3d bullets marked superseded).

**PREVIOUS (2026-11-18): authored death-fall rewrite** - owner's exact patch to
`cutscenes/death3d.py` only (physics.py RagdollBody fixes stay, untouched).
The 15-node ragdoll inversion through Humanoid's Euler hierarchy kept
propping corpses up (body_p -30..-52 deg, lhip_p 0 / lkn 6, pw_y 0.32-0.42 m,
upright sitting), so `RagdollBody`/`_world_joints`/`_pose_from_ragdoll` and the
vector helpers are removed. `Fall` now returns to authored `death_pose` +
`_flop` with per-slot variation (yaw jitter, head/shoulder/elbow, track-1
hip/knee), advances the root by ankle change + clamped push + blast velocity
through `slide_capsule` (plus a second chest-vs-wall pass), applies radial
blast throw and ledge gravity with 0.16 restitution, and latches `rest` only
when grounded with both velocities near zero. Headless 40-fall / 4 s / flat
probe: root y 0.00, drift 0.00, yaw jump 0.00, 0 nonfinite, 40/40 rested.
Gates: compileall, normalize, sync map, smoke --only m6,m7,m8 OK; unit
discover 614 with the same 10 pre-existing reds; boundaries unchanged
pre-existing E4/W1 88. Map rewritten (prior death3d ragdoll bullets marked
superseded); no physics.py or data changes.

**PREVIOUS (2026-11-18): death-fall geometry pass applied** - owner's exact patch
to `engine/collision/physics.py` + `cutscenes/death3d.py` on top of the
slide/roll fix. Four causes: (1) `pose_world` auto-grounding lifted corpses
0.5-0.75 m because clamped/relaxed limbs poked -0.50..-0.89 m below the pelvis
and `max(min_node_y - 0.04, pel[1] - root_0[1])` launched the root; `Fall.at`
now sets `clear = pel[1] - min_node_y + 0.04` and binary-searches 7 steps over
body_p-plane-safe knees/hips/shoulders. (2) `rx_anim/rz_anim` added `push*k`
then snapped back to the ragdoll pelvis (lunge + rubber-band); push term removed,
blend_rag now 0.06..0.30 s. (3) rig.py's chest Z +0.08 biased `up` 12.5 deg and
`asin/atan2` flipped yaw/body_r 180 deg when `up[1] < 0`; `up` now comes from
pelvis->mid-shoulder, gimbal solved from `(uh, up[1], right[1])` with new blend
`_s(0.80, 0.94, |fwd[1]|) * (1 - _s(0.55, 0.85, |right[1]|))`, pitch re-solved
in the clamped roll plane. (4) forward falls pinned feet (all-fours tenting,
legs crossing); added cross-hip min distances (0.40 m) and chest+head impulses
with upward knee/foot counters. Headless 40-fall / 3 s / 180-frame probe:
max settled height offset 0.04 m, drift 0.027 m, yaw/roll step 3.4/4.2 deg,
0 nonfinite. Gates: compileall, normalize, sync map, smoke --only m6,m7,m8 OK;
unit discover 614 with the same 10 pre-existing reds; boundaries unchanged
pre-existing E4/W1 88. Map updated; no new asset/baseline changes.

**PREVIOUS (2026-11-18): ragdoll slide/roll regression fixed** - owner's exact
patch to `engine/collision/physics.py` + `cutscenes/death3d.py`. Cause 1: ground
friction was latched only from `on_surf` on the last constraint iteration (the
links leave `p[1] >= fl`), so landed nodes got no friction and never slept.
Now a per-step `surf_hit` set (floor/box tops + `p[1] <= surf_y + 0.005`) gets
`k_f = 0.58**(h*60)` friction ONCE after the loop and feeds `grounded`. Cause 2:
`_limit_joints()` (5x/step below 7 landed nodes) shifted single child joints with
no parent reaction or `prev` compensation - a reactionless motor catapulting
grounded legs; removed it with `_shift`/`_RAGDOLL_LEGS`/`_LIMIT_STEP`/
`_LANDED_NODES` (rig limits stay in `_pose_from_ragdoll` and `_RAGDOLL_MIN/MAX_DISTS`).
Cause 3: death3d's 4.0-4.5 m/s single-shoulder impulses and early gimbal blend
zeroed `body_r` at 71.8 deg pitch; gimbal is now `_s(0.985, 0.998, ...)`, the
impulses are rebalanced (chest/lat/knee, 1.5 m/s side), and rest also needs
`a >= land + 0.5` so a corpse cannot latch mid-air.
Gates: compileall, normalize, sync map, focused collision 17/17, smoke --only
m6,m7,m8 OK; unit discover 614 with the same 10 pre-existing reds; boundaries
still the pre-existing E4/W1 88. Map + buglog updated.

**PREVIOUS (2026-11-18): M4 station foyer sealed** - one-line fix in
`m4/maps.py`: `FOYER` (35,18,3,2) instead of (35,18,3,3). It is carved by
`_carve_station_interior` inside `_street_grid`, so the old 3 rows overwrote the
station block's south wall on street row 20 at cols 35-37; now row 20 stays
solid "C" with colonnade windows and the gold door (34,19) is the only way in.
Regenerated `levels/m4.street.level.json` + `assets/baked/m4/` (commit with
diff). Gates: level_export OK, bake OK, normalize OK, compileall OK, level_check
OK, bake --check OK, smoke --only mission4 all OK except the known pre-existing
`mission4_cinematic_arrest` harness fake. Headless tile probe confirms row 20
cols 35-37 = C, rows 18-19 cols 35-37 = F, door (34,19) = D. Map updated.

**PREVIOUS (2026-11-18): M4 shop oscillating wall fan** - small follow-up to
`m4/draw3d.py` only: the mid-room 3-blade ceiling fan is replaced by a
wall-mounted fan at (36.92*S, 2.10, -35.18*S) on the north interior wall above
the counter. Static mount bracket boxes in `_corner_shop`; `_fan_mesh` split into
`_fan_cage_mesh` (guard cage) and `_fan_blades_mesh` (radial 4 blades via
`rot_z`), both placed at the same pos with `yaw=32*sin(t*1.3)` oscillation and
blade `roll=t*480` spin, `static=False`. Gates: normalize OK, compileall OK,
smoke --only mission4 all M4 checks OK except the known pre-existing
`mission4_cinematic_arrest` harness fake; both new mesh builders produce valid
meshes (cage 42 faces, blades 30). No level/bake data changed. Map updated.
Owner to eyeball --dev-mission4-game.

**PREVIOUS (2026-11-18): M4 shop pass 2 - roomy 3x4 room + live animations** -
owner's follow-up on the same five `m4` modules, applied after pass 1. Bug 1:
distance-only prompt/loot let you search the counter through the north wall;
both `flow.handle_interact` and the HUD tag now require `_in_corner_shop()`.
Bug 2: the 2x2 kiosk was cramped behind a 7.1 m lintel; `deep_g` is now
(35,34,4,5) with `blk_s7` shrunk to one row, a double-wide (35,36)/(35,37)
shutter entrance, 3x4 `F` interior (36,35,3,4), "d" apron on row 33 / col 34,
`CORNER_SHOP_COUNTER_TILE=(37,35)` and an east-crate collider. `draw3d` splits
static `_corner_shop` from per-frame `_draw_corner_shop_anim` (rolling shutter,
stutter-neon NON-STOP, spinning fan, swaying pendant, glowing cooler, flickering
CRT, kettle steam, wagging/blinking cat, mag pickup); `_shop_cut_active` opens
the front walls from the sidewalk; `_put(..., static=False)` for animated bits.
`draw._draw_m4_corner_shop_2d` paints the 3x4 cutaway. Re-exported and rebaked:
`levels/m4.street.level.json` + `assets/baked/m4/` (commit with diff).
Gates in order: level_export OK, bake OK, normalize OK, compileall OK,
level_check OK, bake --check OK, smoke --only mission4: all M4 checks OK except
the known pre-existing `mission4_cinematic_arrest` harness fake. Headless probe
confirms D/D doors, 3x4 F floor, apron, colliders, and that looting is blocked
outside but works inside (same 58 px/70 px distances). Map updated. Owner to
eyeball --dev-mission4-game (shutter/fan/cat/CRT animations, sidewalk cutaway).

**PREVIOUS (2026-11-18): M4 human-scale blocks + enterable corner shop** - owner's
exact patch across `m4/{maps,world,flow,draw3d,draw}.py`. `_height` gives blocks
2.7+2.2*(storeys-1) m (station 8.2), `_windows` 2.2 m floor spacing + 1.70 m
shutters, `_cut_zone_for` scales the cutaway with wall height. `deep_g` -> (35,36,4,3)
with a "d" apron, west door D at (35,37) and a 2x2 "F" shop interior; counter
collider + `_shop_counter_pos`, `_in_corner_shop`, `m4_shop_visited/looted`,
Vasile's line, `_loot_corner_shop` (+1 K-9 mag, +3 supply, +40 HP or bandage),
`_corner_shop` 3D props/lights and `_draw_m4_corner_shop_2d` + "E - SEARCH
COUNTER" tag; rain treats "F" as dry. Regenerated `levels/m4.street.level.json`
and `assets/baked/m4/` (world_static_0 + bakeinfo) - commit with the diff.
Gates in order: level_export OK, bake --pack m4 OK, normalize OK, compileall OK,
level_check OK (data == legacy), bake --check OK, smoke --only mission4: all M4
checks OK except the known pre-existing `mission4_cinematic_arrest` harness fake
(`SimpleNamespace.fade_out_music`). Headless shop probe OK (door D, 2x2 F, apron,
collider, loot rewards). Map updated. Owner to eyeball --dev-mission4-game.

**PREVIOUS (2026-11-18): M6 sealed border doors** - owner's exact patch to
`m6/world.py` + `tests/unit/test_m6_campaign.py`. Perimeter `"D"` gates
(customs (15,0), noman (20,0)/(20,17)) were not in `M6_SOLID_CHARS` and
`Player.move` has no map clamp, so the player could walk out of the map.
`world._is_border_door(grid,col,row)` flags a `"D"` on row 0 / h-1 / col 0 / w-1;
`_floor_at` rejects it and `_parse_grid` adds a wall Rect, while interior doors
stay walkable. New `test_border_doors_block_leaving_the_map` passes (all three
gates + an interior customs floor tile).
Gates: compileall OK, normalize OK, m6_campaign -v 59 tests (new test OK; only
the known pre-existing face-exposure 173>170 red), smoke --only m6 OK. Map
updated. No in-game check requested for this one.

**PREVIOUS (2026-11-18): M6 2.5D textures + all-stage gate** - owner's exact patch
across `engine3d/{core,gl}.py`, `game/topdown3d.py`, `m6/{draw,draw3d}.py` and
`tests/unit/test_m6_campaign.py`. Root cause: `topdown3d.put` rebuilt every face
`(f[0..4], None, f[4])`, dropping M6's `("uv", slot, uvs)` tail, so GL packed
`f_tex=-1` (flat white). `put` now forwards `*f[5:]`, `Mesh.add` preserves face
tails, `gl._pack_faces` finds the UV tag at element 6 or 7 and keeps `fb` separate,
FRAG `eslot` -1.5 -> -1.25; `_gl_atlas` gets a 4-byte-aligned shelf, 1 px gutter
and a 0.01 UV inset. `_td3d_gate` now enables 2.5D for customs/noman/rail/boxcar
(`ACA_M6_RAIL_25D=0` opts rail out), and `draw3d._stage()` folds boxcar into rail.
Gates in order: compileall OK, normalize OK, m6_campaign -v (both new/updated
tests pass; only the known pre-existing face-exposure 173>170 red), m6_td3d_shots
wrote 9 frames incl. rail (visually textured), smoke --only m6 OK; extra
engine3d_check parity 4.14% OK. Map updated. Owner to eyeball
`--dev-mission6-game` / `--dev-mission6-rail` live.

**PREVIOUS (2026-11-18): corpses lie flat** - owner's exact patch applied to
`cutscenes/death3d.py`: `_pose_from_ragdoll` now derives the knee bend as a SIGNED
angle in the thigh's bend plane (project shin with `Tt`, then `atan2(-f_t[2],
-f_t[1])`, clamped 4..120) instead of unsigned `acos(dot(u,f))` - the rig has no
hip_y, so sideways legs on the floor read as +90 deg downward knees and tent-poled
the torso up on its toes. Gimbal blend `g` -> `_s(0.95, 0.995, ...)`, track-1 knee
impulse -> `(px*0.9, -0.25, pz*0.9)`, and `Fall.at` relaxes knees/hips/shoulders/
ankles toward rest when a flat torso would root > 0.20 m; `pel_y` bias -> -0.04.
Gates: normalize/compileall/smoke --only m6,m7,m8 OK, headless 20-fall settle
probe OK (worst pelvis 0.182 m, 0 nonfinite), unit discover 612 tests with the
same 10 pre-existing reds. Map updated. Owner to spot-check kills near vehicles
and ledges in-game (--dev-mission8-trap, --dev-mission7-raid).

**PREVIOUS (2026-11-18): leg hit spheres** - owner's exact patch applied to
`m6/yard_brain`, `m7/raid_brain`, `m8/revenge/trap_brain`, `m8/duty/mansion_brain`:
standing Guards gain pelvis (~0.72 m) + shin/ankle (~0.30 m) spheres beside
chest (index 0) and head (index 1), which keep their order for `yard3d`'s
`zi == 1` headshot test and `suppress()`; M7/M8 scenes use the `is_head` flag.
Truck gunners keep chest+head only (`e.get("truck") is not None`) so rounds
cannot pierce the truck bed. M6 downed/hide_low sets stay reduced; dogs unchanged.
Gates: normalize/compileall/smoke --only m6,m7,m8 all OK, headless four-scene
sphere probe OK, unit discover 612 tests with the same 10 pre-existing reds.
Map updated. Owner still needs the in-game dev-jump eyeball (yard/raid/trap/mansion).

---

## GAIT STRENGTH, RIFLES-UP, RAGDOLL LEDGES (2026-11-18)

Owner verified all four scenes and supplied exact fixes; applied verbatim.
Gait: locomotion_pose restores 26-34 deg thigh / 52-80 deg knee drive, powers
l_lift^1.15, broadens the lift bridge to walks (target_h 0.858+...), adds
stride-coupled spine_r. YardScene now runs LayeredAnimState. Rifles-up:
RaidScene._guard_pose (borrowed by M8 Trap/Mansion) and YardScene._guard_pose
use mask_pose(lower, aim/ready upper); _hold_cached and the rifle_p flinch run
for moving guards as well (probe: walking guard has rsh_p 22, rifle_p 28).
Ragdolls: max knee/foot spread constraints + rest ON TOP of box surfaces
(p[1] >= box_top - 0.05) stop splits and sideways launches off pillars;
trap_world.ragdoll_boxes() gives the sniper deck + 3 guardrails; Fall anchors
root to the ragdoll pelvis, relaxes ankles by face-up/face-down, caps hip spread
and varies impulses per slot.

Gates: compileall, normalize, api snapshot (92/676), sync map OK; 612 unit
tests with only the same 10 pre-existing reds; smoke --only m6,m7,m8 OK;
ae_bench_scenes all 90f OK (yard 16.1/trap 5.0/mansion 9.9/raid 5.8 ms);
walk span variation 3.8 cm, sprint 1.5 cm; ragdoll probe 0 nonfinite.
Boundary/ae_ci reds unchanged. Map updated.

---

## GAIT BOUNCE + RAGDOLL OVERHAUL (2026-11-18)

Owner traced both bugs and supplied exact fixes; applied verbatim (with the
permitted simplification of the identity-matrix multiply in `_pose_from_ragdoll`).
Gait: `locomotion_pose` now adds sprint-only positive `lift` compensating the
cosine leg-span shortening at stride splits (measured span+lift variation 0.025 m
walk / 0.016 m sprint, was ~0.20 m); hip swing/twist reduced; `pelvis_drop`
clamped; the discontinuous `_solve_leg` snap gated on `abs(foot L.y - R.y) > 0.03`
removed from RaidScene/TrapScene `_draw_player`. Ragdolls: `death3d._world_joints`
extracts all 15 nodes from `pose_world`'s `places` (slots 4/7/8/10/13/14) rather
than its 5-joint `joints` dict, so rest lengths match crouched/aiming/scaled
guards; `RagdollBody` gains shoulder/hip/knee separation + `_RAGDOLL_MIN_DISTS`
anti-origami constraints, smaller node radii, and capped impulses (push <=1.2,
track impulses <=3.8 m/s, no +2.2 upward launch); `_pose_from_ragdoll` rebuilds
`(pose, yaw)` from the full rig basis (no canned-pose pitch blending or pre-leg
`solve_arm`), blend starts at 0.04s and rest waits `land + 2.5s`; trap3d passes
`box_world` to its deaths.

Verification: 24 anim/collision tests OK, smoke --only m6,m7,m8 OK,
ae_bench_scenes all 90f OK, engine3d_check 4.14%, API snapshot stable,
sync/normalize OK, ragdoll probe 15 nodes / 0 nonfinite frames / smooth pitch
0->83 deg, pink probe still 0% magenta. Map updated.

---

## ANIMATION + COLLISION KERNELS AND GAMEPLAY WIRING (2026-11-18, Phases 1-2)

Both supplied phases applied. Phase 1 (pure engine): new engine/anim/springs.py
and rig3d.py (analytical springs, bone-masked pose mixer, velocity-coupled gait,
LayeredAnimState, FootIKSolver); new engine/collision/physics.py (slide_capsule,
DebrisPool, 15-node Verlet RagdollBody); MultiFloorNav/NavLink in nav.py;
capsule_contacts in boxes.py/mesh.py; re-exports; new test_engine_anim.py and
expanded test_engine_collision.py (24 tests OK). Phase 2 (gameplay): death3d.Fall
ragdoll seeded from live pose_world joints with IK limb draping; slide_capsule in
M7 raid_world / M8 trap_world / M8 mansion_world (Mansion keeps its 1 m ledge
guard and 0.6 m stair step_h); mansion_world.nav() shared MultiFloorNav over
FLOORS synced to dynamic doors/cars/helicopter, used by mansion_brain routing;
RaidScene runs LayeredAnimState/TurnLagTracker/FootIKSolver+solve_leg/DebrisPool.

Three corrections during application: (a) the supplied ragdoll applied ground
friction inside every constraint iteration (5x per frame), pinning bodies at
ledge edges -> friction now once per step (test_debris_and_ragdoll passes);
(b) mask_pose's frozenset default put a hash-seed-dependent repr in the public
signature, breaking ae_api_snapshot between processes -> default is now None;
(c) raid3d's two omitted imports (m_mul, solve_leg as _solve_leg) added, and
TrapScene/MansionScene (which BORROW RaidScene methods by assignment rather than
subclassing) now also borrow _anim_ctl, otherwise borrowed _move/_player_pose/hp
raise AttributeError in M8.

Gates: compileall, ae_normalize --changed --apply, ae_api_snapshot record+check
(92 modules, 676 names, stable across processes), sync_arch_map --check,
engine3d_check (4.14%), 24 new engine tests OK, smoke --only m6,m7,m8 OK,
ae_bench_scenes all 90f OK (raid 4.95 ms, trap 4.22, mansion 6.69, yard 12.1).
Full unit discover 612 tests: same 10 pre-existing reds as before (no new ones).
Boundary/ae_ci reds unchanged (E4/W1 pre-existing). Map updated.

---

## FIVE GPU VISUAL UPGRADES APPLIED (2026-11-18)

Owner supplied a complete unified implementation; applied verbatim (plus two
patch-application corrections, see below). New `src/engine3d/particles.py`
(vectorized `ParticlePool`/`DecalPool`, `pack_dots`, `pack_blood_decals`).

1. SSAO: `gl_post.PostPipeline.apply_atmos` half-res hemisphere from `f_pdepth`+
   `f_aux`, bilateral blur; emissives (`a>0.9`) exempt, rigs (`mat_id 0.75`) softened.
2. 64 tiled lights + 2 spot-shadow maps: `GLRenderer._upload_lights` packs a
   `(64,4)` RGBA32F data texture + 12x8 CPU tile bitmask; `_spot_pass` renders up
   to two 512x512 PCF perspective maps. `light_cap` default 64, software cap 64.
3. HDR GPU unification: M2/M3/M4/Walk3D -> `hdr=True`+`flush_to`; M6 2.5D ported
   to GPU extra textures (`u_extra0..2`), GPU `grade3d`+`char_lift`, no CPU
   `_decode`/`_light` on GL; software paths intact everywhere.
4. Wet reflections + exponential height fog: `textures.reflectivity()` -> `f_aux.a`
   material tag; `_ATMOS_FRAG` does SSR raymarch, 64-light specular, puddles, fog.
   M8 Mansion sets `marble_refl`.
5. Instanced particles/decals: `gl_sprites.ParticlePass`/`DecalPass` with hardware
   instancing + `u_pdepth` fade; software fallback via `_emit_fallback_fx`. Adopters:
   `topdown3d.dots`, M1-M5 blood, M6 yard, M7 raid, M8 trap/mansion.

Two corrections during application: (a) the `_SSAO_FRAG` block had to be inserted
BEFORE `_FINAL_FRAG` (inserting after its opening `"""` corrupted the shader);
(b) `release()`'s `self._drop_atmos()` initially landed in `_ensure_bloom` because
`self._drop_bloom()` is not a unique anchor — that released the bound HDR atlas
texture mid-`_run_bloom` and crashed M8 (`InvalidObject.use`); moved to `release()`.

Gates: `compileall`, `ae_normalize --changed --apply`, `ae_api_snapshot check`
(89/622 +0), `sync_arch_map --check`, `engine3d_check` (worst 4.14%, GL 17.4 ms),
`unittest` 3 shader/texture/render3d modules 13/13, `smoke_test --only m1..m8`
**SMOKE TEST: OK**, all six `m{1..6}_td3d_shots.py` wrote frames, `ae_bench_scenes all`
90f OK (trap 5.2/chase 10.5/raid 5.7/yard 13.9/train 11.3 ms). The earlier pink
Print Works fix still holds (probe 0% magenta). `ae_ci --quick` still FAIL on the
same pre-existing reds (E4/W1 boundaries, D4/D6, stale bake, 10 unit reds: m5
Channel.id, m8 font/chase/trap, raw-loads, face-exposure 173, ai_bundle pytest)
and `smoke --fast` only the two `fade_out_music` harness fakes. Map updated.

---

## PINK PRINT WORKS FIXED (2026-11-17) — GL bloom chain read uninitialised texture

The bug isolated below is fixed in `src/engine3d/gl_post.py::_run_bloom`. Root cause:
the multi-level blur loop sampled the current level's `ta` (the vertical-blur WRITE
target, unwritten on the first frame) as the horizontal-blur source instead of the
previous level's result (`src_tex`, assigned but never used). Level 0 was fine only
because `ta == src_tex` there; level 1+ read garbage f2 texture memory. With
cutscenes off that memory is zeroed (frame clean); after a 614x345 m5x cutscene it
holds magenta frame data, so the `bloom`/`grade3d` final pass floods Print Works
pink. Quarter never showed it because `flush_to` forces `bloom=0.0` when CPU items
exist, so `_run_bloom` never ran there. Fix: `src_tex.use(location=0)` in the
horizontal blur, so all bloom textures are written before being read.
- Repro probe (`Temp/opencode/pink_leak_probe2.py`) for BOTH triggering cutscenes
  (`m5x_faces_wide`, `m5x_pw_arrival_wide`): print magenta 62.83% -> 0.00%, mean RGB
  (108.7, 35.5, 94.8) -> (33.9, 30.0, 26.1), matching the cutscene-off baseline
  (34.9, 30.9, 26.7). Visual check of the fixed frame: normal warm-lit print works.
- Gates: `compileall -q src` OK, `ae_normalize --changed` OK, `engine3d_check.py`
  worst diff 4.14% OK, `sync_arch_map.py --check` OK. `smoke_test.py --fast` still
  RED only on the two known pre-existing harness fakes (`mission5_shadow_finale`,
  `mission4_cinematic_arrest`: `SimpleNamespace` has no `fade_out_music`); all other
  M5/mission checks green. `docs/ARCHITECTURE_MAP.md` updated (GPU bloom-chain
  bullet + regenerated inventory) and buglog gained `bug-gl-bloom-uninitialized-level-20261117`.

---

## PINK PRINT WORKS REPRODUCED HEADLESS (2026-11-17) — root cause isolated

Built `C:/Users/BIRIBEL/AppData/Local/Temp/opencode/pink_leak_probe2.py`:
in ONE process, render M5 Lower Quarter (quarter checkpoint, (6,6)), then
`m5mid3d.draw_m5x(scene, surf, 1500)`, then render quarter again and Print Works
(checkpoint, (5,15)); captures each frame to PNG. `ACARISTAN_CUTSCENE3D` is set
from argv. `pink_check.py` measures channel means + magenta-pixel %.
- cut3d=1 (`m5x_faces_wide` OR `m5x_pw_arrival_wide`): quarter before AND after
  cutscene normal (mean 10.6/17.1/32.5, 0% magenta); Print Works AFTER is PINK
  (mean ~107/35/94, **62.8% magenta**) — deterministic, repeated twice.
  Visual matches the owner's input_file_12.png exactly (HUD normal, world
  flooded magenta/orange/blue).
- cut3d=0, identical sequence: quarter normal, Print Works NORMAL
  (mean 34.9/30.9/26.7, 0% magenta).
- A shorter print->cutscene->print probe (no quarter render) stayed clean in
  BOTH modes, so the trigger needs the quarter render BEFORE the cutscene.
=> Answers the owner's two questions: with 3D cutscenes off Print Works is
normal; with them on the quarter stays normal after Kovac & Sandu and pink only
appears inside Print Works. Confirms hypothesis (1): a 3D m5x cutscene
(614x345 renderer on shared `engine3d.gl._CTX`) leaves GL state that corrupts
the later 1000x700 Print Works `flush_to`/post pipeline. Owner will write the
exact fix. The probe scripts are in Temp/opencode, not the repo.

---

## Print Works wide-angle left background closed (2026-11-17, uncommitted)

Applied the clean diff to `_street_set` in `src/cutscenes/m5mid3d.py`:
avenue asphalt -64..32 (z -18..8), lane dashes/tram rails to x=-58, sidewalks
-64..32, opposite sidewalk widened and centred at -16, three streetlamps down
the left avenue (-13.2/-26.5/-40), Quarter blocks out to -58 plus a far-left
skyline block, an extra opposite-side block at -24, and three emissive
lettering bars on the red blade sign; `_faces_set` cross-street end-caps at x=±22 (608/609). Verified: `ae_normalize --changed` OK,
`compileall` OK, `smoke_test.py --only m5` OK but matches ZERO checks (use
`--only mission5`: all M5 checks green except the known pre-existing
`mission5_shadow_finale` `fade_out_music` red). Re-rendered `_arrival_wide`
Angle 1 at t=200/1500/2900 (`tools/shot_m5x.py`) — left edge filled with
buildings/ground, no void. `docs/ARCHITECTURE_MAP.md` §4.3 updated + regenerated.
Pink: `--dev-m5-printworks` is a typo (`--dev-mission5-printworks`) and both dev
flags are interactive, so isolated GL/software frames were used and stayed clean.
The full quarter -> cutscene -> printworks sequence DOES reproduce (see section
above); code inspection shows glow -> `gl_post._gb_fbo` (RGBA16F `dtype="f2"`,
additive blend, sampled as `u_gbloom` and added to `col`), cone -> `_lm_tex`
(RGBA8).
`python tools/ai_bundle.py src/cutscenes/m6fx3d.py` ran: 625 lines, 1 file,
copied to clipboard.

---

## M5 mid-cutscene texture / empty-void fix + pink diagnostic (2026-11-17, uncommitted)

Owner's patch applied to `cutscenes/ps2mat.py` and `cutscenes/m5mid3d.py`.
`_class` now classifies dark, low-saturation cool colours as `"asphalt"` ->
`pavement`/`concrete`, so cool-dark asphalt and dark steel stop rendering flat.
`m5mid3d` gains cached tinted `_qt` + `_pave_tex`/`_conc_tex`, `_framed_window`,
`_quarter_block`, `_mag_van_3d`, `_paper_bales_3d`; `_street_set`, `_pw_interior`
and the rebuilt `_faces_set(r, t)` enclose the East Checkpoint / Print Works
avenue with textured pavement, kerbs, tram rails, barriers, flanking Quarter
blocks and Print Works down the cross-street. `docs/ARCHITECTURE_MAP.md` updated
(§4.3 bullet + generated rows) and `sync_arch_map --check` OK.
- The two touched files were CRLF in the repo; `ae_normalize --changed --apply`
  normalised them (now dry-run clean). Other gates: `compileall` OK,
  `smoke_test.py --only m5` OK (note: `--only m5` matches ZERO checks — use
  `--only mission5`); `--only mission5` green except the known pre-existing
  `mission5_shadow_finale` `fade_out_music` harness failure. `shot_m5x.py`
  rendered `m5x_faces_wide`, `m5x_pw_arrival_wide`, `m5x_pw_arrival_door` —
  all three visually textured with no empty void.
- **Pink Print Works diagnostic:** the supplied `--dev-m5-printworks` is a typo
  (real flag `--dev-mission5-printworks`), and both dev flags are interactive
  with no auto-exit, so I used the headless shot tools that jump to the same
  checkpoints instead. `tools/m1_td3d_shots.py` (GL) and `tools/m5_td3d_shots.py
  print` with `ACARISTAN_RENDERER=gl` AND `=software` (GL available: RX 7800
  XT): all frames normal, mean R>G>B in Print Works and cool B>G>R in M1/quarter,
  0% magenta pixels. Pink does NOT reproduce in isolated headless frames on
  either backend -> likely interactive/cached-renderer state; owner's in-game
  reproduction still needed. No baselines re-recorded.

---

## Unified world-space 2.5D rain rollout (2026-11-17, uncommitted)

Owner's spec applied: new `src/game/rain3d.py` (387 lines) plus wiring in
`walk3d`, `walking_sim`, `m1/{draw3d,draw}`, `m4/{draw3d,draw}`, `m5/draw3d`.
Three hashed world-cell depth bands (`emit`), light-reactive streaks from
`_pack_lights`/`_lit_at` (lamps, fires, headlights, torch, M5 searchlight),
ground ripples/splash crowns/puddle double-rings, sightline/roof/ground
occlusion callbacks, GL batching via `add_lines3d` and software `add_line3d`
fallback. `step_rain_drops` keeps 2D replay RNG parity; M1 drop-off films skip
their 2D rain when a 3D take drew. `docs/ARCHITECTURE_MAP.md` updated by hand
(§538/§1243) + `sync_arch_map.py` (inventory row §1549).
- **Deviation from the supplied patch (required):** the spec queued pre-projected
  2D screen tuples into `GLRenderer.add_lines3d`, which takes WORLD-space
  endpoints. That raised `IndexError: tuple index out of range` in
  `core.to_cam`, was swallowed by `walk3d.draw`'s handler, and silently
  disabled 2.5D. `rain3d.py` now keeps `proj()` only for near/off-screen
  culling and queues world endpoints (taper split interpolated in world space).
  Spotted via the caught traceback in `--only m1,m4,m5,walk`, not the exit code.
- Gates: `compileall`, `ae_api_snapshot check` (89/622 +0), `ae_import_check`,
  `ae_normalize --changed`, `sync_arch_map --check` equivalent, targeted smoke
  (`--only m1,m4,m5,walk`, no traceback) and all four td3d shot tools clean;
  eyeballed `shots/m1_td3d/m1_street_3d.png` + `shots/m5_td3d/m5_q_a_3d.png`
  (streaks visible). Pre-existing reds unchanged: `check_boundaries` E4/W1 88,
  `ae_global_names` `oil_rig_3d.py: i`. No baselines re-recorded.

---

## Verification re-run: tactical HUD / night-grade rollout (2026-11-17)

Re-checked the ALREADY-APPLIED "Shared 2.5D tactical HUD + night-grade pass"
against the owner's full spec: all 13 file changes are present. The two apparent
`grade3d.py` mismatches are later drift, not gaps — `_cones = OrderedDict()`
(LRU) and `kind="pool"` in the glow branch came from the fire/perf passes, which
also added the `"fire"` light kind. `docs/ARCHITECTURE_MAP.md` already documents
it (§531/§544/§1869); no map edit was needed.
Green: `compileall`, `ae_api_snapshot check` (89 mod/622 names), `ae_text_check`,
`ae_bench --check-budget`, `ae_normalize --changed`, all seven
`m{1..6}/walk_td3d_shots` tools wrote their stills, and every smoke check but two.
Four reds, all pre-existing / from later passes, NOT this rollout:
`check_boundaries` E4 `ui.credits` + W1 88>51; `test_m6_campaign` face exposure
173>170; `smoke_test.py --fast` `mission5_shadow_finale` and
`mission4_cinematic_arrest` — both `AttributeError: 'types.SimpleNamespace' has
no attribute 'fade_out_music'` at `app.py:2892`, introduced when the OST pass
added "fade on exit" but left the fake `audio` namespace in `smoke_test.py:9664`
(and `m5_shadow_check.py`) unpatched. Owner decision pending: fix those harness
fakes or leave them. No baselines re-recorded.

---

## HDR scoping + GPU sky fixes (2026-11-16, uncommitted)

Owner's probe pinned two root causes; both fixed:
1. HDR leaked from cached `m6world3d.rend()` renderers into M2/M3/M4/M6/walk3d/
   arena 2.5D hosts, corrupting `K_TOP..K_PTOP` key colours so M6 `_decode()`
   never swapped in wall/roof/container textures. `rend(w,h,hdr=True)` now
   scopes HDR per call; M1/M5 request True, others False, all save/restore.
   M6 also forces `dither=False`/`ps1_snap=False` and restores them.
2. GPU skies need `buf is r.surface`: M7 stage passes `r.surface`, M8 chase
   dawn uses `night_sky(gpu=False)` + `stratus`, `night_sky` clears stale sky
   with `set_sky(None)`. Added GPU `_gl_spec` to blob shadows (avoids double
   readback) and fixed M6 reticle alpha via RGBA_MULT.
- Gates: `compileall` OK, `ae_normalize` OK, `test_gl_composite` 6/6 OK,
  `engine3d_check` parity 4.14% OK (software 15.4 / GL 9.2 ms), GL smoke
  `m1..m8` **SMOKE TEST: OK**. In-game visual checks of M6 2.5D textures and
  M7 raid/film skies are the owner's.
- `docs/ARCHITECTURE_MAP.md` updated.

---

## GPU Phase 1: HDR/MRT + GPU sky/sprites/post (2026-11-16, in progress)

Applied verbatim: new `engine3d/gl_sprites.py` + `gl_post.py`; GLRenderer gets
RGBA16F colour + `f_aux` + `f_pdepth` MRT FBO, `flush_to`/`present_to`,
`_render_into_fbo` and single-readback post; `core.py` set_sky stub; `_gl_spec`/
`_gl_surf`/`_gl_lines` on m5fx3d/m6fx3d/fire3d/topdown3d; GPU sky hooks in
m6world3d/m7world3d; `post3d.gpu_spec`; GL wiring in M1/M5 2.5D, M6 train/yard,
M7 raid, M8 set/chase/mansion.
- Fixed two regressions from this pass: `ctx.depth_func="always"` raised
  SystemError in this moderngl build, which tripped `td.disable()` 5x and left
  dev-skips stuck in 2D for the session — depth clear now uses `"<="`. Also
  `m6world3d.night()` needed `gpu=` passthrough, and gl_sprites halo path had
  to tolerate specs without `radius_m` (rx_m-only). Fresh game launch restores
  2.5D.
- Gates: `ae_normalize` OK, `compileall` OK, unit discover 601 tests (4F/6E —
  all pre-existing), `ae_engine3d_parity` OK, `ae_bench3d --check-budget` OK.
- **Resolved:** owner found the real root cause — `clear_depth()` used
  `depth_func="<="` with a quad at 1.0, so against a fresh depth texture of
  0.0 nothing passed and 100% of geometry was culled (only sky survived).
  Now probes `depth_func="1"` at init with `">="` fallback, and every MRT
  sky/bg/post pass explicitly resets color/depth masks. Also fixed
  `ctx.NEAREST` -> `self.ctx.NEAREST` in resize and `_split_items` handling of
  `lines` items. `engine3d_check.py` parity back to 4.14% OK (software 12.6 /
  GL 7.8 ms); GL smoke `m1,m6,m7,m8` all OK including train viewmodel/scope.
  `check_boundaries` W1 now 88 (pre-existing gate; new engine3d -> missions.m1
  grade3d import in `gl_post._render_grade3d`).
- `docs/ARCHITECTURE_MAP.md` updated.

---

## More benchmarks (2026-11-17)

Added `tools/ae_bench_scenes.py` (diagnostic, not a CI gate): times
update+draw on nine more 3D scenes — M8 trap/chase/kill/mansion/flight/ridge,
M7 raid, M6 yard/train — with `--frames`, `--runs`, `--backend`, reporting
avg/p50/p99/max ms and fps. `docs/ARCHITECTURE_MAP.md` §21/§18 updated.
Sample (GL, 40 frames): trap 163 fps, chase 77.5, kill 191, mansion 144,
flight 126, ridge 185, raid 132, yard 69, train 73 — yard/train/chase are the
slowest of this set. `compileall`/`ae_normalize` clean.

---

## FPS baseline for the pending big performance upgrade (2026-11-16)

Owner is planning a large perf upgrade; these are the reference numbers to
compare against. Clean serial runs (FPS = 1000/frame-ms). "Before" = pass-1
serial runs under residual parallel-load contention, so ratios are inflated —
trust the absolute "after" numbers. NOTE: measured after Pass 2, **before** the
fire3d overhaul (only `engine3d_check` re-ran after that: software 40.3 ms /
GL 13.9 ms; no FPS probes re-run).

| Probe | Before | After (pass 2) |
|---|---|---|
| `m7_prof w2` mean | 182.70 ms / 5.5 fps | 46.92 ms / 21.3 fps |
| `m2_fire_probe --live` 3D median | 54.07 ms / 18.5 fps | 25.27 ms / 39.6 fps |
| `m2_fire_probe --2d` median | 70.15 ms / 14.3 fps | 10.31 ms / 97 fps |
| `ae_bench` m5-quarter avg | 41.77 ms / 23.9 fps | 15.13 ms / 66.1 fps |
| `ae_bench3d` office3d q2 | 87.00 ms / 11.5 fps | 16.32 ms / 61.3 fps |
| `ae_bench3d` depot3d q2 | 101.28 ms / 9.9 fps | 14.98 ms / 66.8 fps |

M6 (measured only after pass 2): train 12.62 ms / 79.2 fps, yard 10.15 ms /
98.5 fps. `ae_bench3d` q1 office/depot 16.40/6.78 ms, q0 15.08/4.26 ms.
Still under 60 fps after pass 2: M7 w2 (~21 fps) and M2 3D fireball (~40 fps) —
likely targets for the upgrade.

---

## Fire overhaul: volumetric fire3d + un-crushed lightmap (2026-11-16, uncommitted)

Owner's visual pass, applied across 14 files + new `src/cutscenes/fire3d.py`
(886 lines). Replaces stacked cardboard flame cutouts / hexagon smoke / oil-rig
emissive cubes with one deterministic turbulent system: 24-frame seamless
advected-turbulence flame atlas (feathered SRCALPHA body + additive core),
warm-underlit soft smoke, feathered ember beds and rising embers. `GLRenderer`
now honours `phys_occ` for per-pixel physical-depth occlusion of fire/smoke
(no light-anchor single-point kill). `grade3d.apply` handles a new `"fire"`
light kind (amber spill + cream core + bloom) so the night multiply no longer
crushes fire; M6 bakes warm fire spill into `_light` directly; M4/M5 car/tram
flashes emit `fire` lights. M7/M8 tank fires use `layer=2` so actors sort in
front on software. No gameplay rules changed.
- Gates: `ae_normalize --changed --apply` OK, `compileall -q src` OK,
  `test_gl_composite`/`test_weather3d` 10/10 OK, `test_oilrig_collapse` 11/11
  OK, `ae_engine3d_parity` OK, `smoke_test.py --only m1..m8` **SMOKE TEST: OK**.
- Visual captures all wrote frames: `m1_td3d_shots`, `m2_td3d_shots`,
  `m5_td3d_shots`, `render_m7_feedback` (9 previews + 2 sheets),
  `oilrig_preview` (13 frames in `tools/out/oilrig/`). In-game eyeballing of
  barn/tank, truck/blast, molotovs/burning tram is the owner's:
  `--dev-mission7-raid`, `--dev-mission7-finale`, `--dev-mission8-trap`,
  `--dev-m1-game`, `--dev-mission2-truck`, `--dev-mission5-game`.
  `docs/ARCHITECTURE_MAP.md` updated.

---

## Pass 2 perf: mesh collider + remaining draw3d/train (2026-11-16, uncommitted)

Owner's final perf pass applied verbatim to 4 files. `engine/collision/mesh.py`
gains precomputed triangle edges/Y bounds, a local 3D AABB ray clip, Y-band
triangle culling and a no-`set()` single-cell path; `m1/draw3d` evicts the
oldest 128 entries of its three fire/pool caches instead of wiping them;
`m3/draw3d._draw_fx` culls off-screen fire zones; `m6/train3d` caches the fade
veil and reuses `add_humanoid` joints for dead guards (one `pose_world()`
instead of two). No gameplay rules changed.
- Gates: `compileall -q src tools` OK, `ae_normalize --changed` OK,
  `ae_api_snapshot check` OK (622 names), targeted units incl.
  `test_engine_collision_mesh` **68/68 OK**,
  `smoke_test.py --only m6,m7,m8,m2,m5,engine3d` **SMOKE TEST: OK**.
  `check_boundaries.py` / `ae_ci.py --quick` unchanged pre-existing reds.
- Serial probes (clean, no parallel contention):
  `m7_prof w2` mean 46.92 ms p99 91.46 (was 182.70 in the pass-1 serial run),
  `m2_fire_probe --live` median 25.27 ms p95 30.82 (was 54.07),
  `--2d --live` median 10.31 ms p95 13.86 (was 70.15),
  `m6_phases train` 12.62 ms/frame (79.2 fps; `_draw_guards` 0.01 ms),
  `yard` 10.15 ms/frame (98.5 fps),
  `ae_bench` 15.13 ms p99 27.51 (was 41.77),
  `ae_bench3d` office3d 16.32 / depot3d 14.98 ms q2 (was 87.00/101.28).
  Caveat: earlier runs were under parallel-load contention, so the deltas
  overstate the pure pass-2 gain; absolute numbers are the trusted ones.
  `docs/ARCHITECTURE_MAP.md` updated.

---

## Pass 1 perf: gas drums / fire / shared hot paths (2026-11-16, uncommitted)

Owner's perf rollout applied verbatim across 13 files (GL composite scratch
buffers + `draw_depth` per-point spark occlusion + conditional depth readback +
bone buffer reuse; software blob LRU + inlined normals; `pose_world` radius
pruning; m7world3d cached/packed flame templates + smoke-base separation;
m6fx3d/m5fx3d bounded LRU + pre-sliced Bayer + cached stars; m7 gas-drum
smoke/glow reductions; FireZone surface caches; LightBuffer LRU + reused
upscale buffers; topdown3d/grade3d LRU; m6world3d flake bounds; m2 blast halo
clamp). No gameplay rules changed. Two CRLF files normalised via
`ae_normalize --changed --apply`.
- Gates: `compileall -q src tools` OK, `ae_normalize --changed` OK,
  targeted units `test_gl_composite/test_m7_campaign/test_engine_render2d/
  test_weather3d` **58/58 OK**, `smoke_test.py --only m7,m2,m5,m6`
  **SMOKE TEST: OK**. `check_boundaries.py` and `ae_ci.py --quick` still show
  the same pre-existing reds (E4 credits, W1 87>51, D4/D6, stale bake, 10
  unit reds).
- Serial probes (parallel runs inflate timings; these are standalone):
  `m7_prof.py w2 --time` mean 182.70 ms p50 217.11 p99 564.53 (600f);
  `m2_fire_probe.py --live` 3D median 54.07 ms p95 160.55 (120f, 23 zones);
  `m2_fire_probe.py --2d --live` median 70.15 ms p95 152.03;
  `ae_bench.py` m5-quarter avg 41.77 ms p99 137.10;
  `ae_bench3d.py` office3d 87.00 / depot3d 101.28 ms (software q2).
  Owner to judge whether these scenes still feel heavy; Pass 2 targets
  m1/draw3d `_fire`/`_draw_walls`, m3–m6/draw3d, m6/train3d, m8 3D scenes.
  `docs/ARCHITECTURE_MAP.md` updated.

---

## Track 20 + M7 shift-at-the-shotgun (2026-11-16, uncommitted)

New `20_dust_on_the_road.mp3` (Track 20, 7/4 G minor, 92.4s / -1.2 dBFS,
rendered by `python tools/build_ost.py 20`). `tools/ost/album.py` is now a
20-track album. M7 wiring: `m7_audio.MUSIC["prep"]` = 20; `m7/flow.STAGE_MUSIC`
`STAGE_PREP` "farm" -> "prep"; `m7/flow.film_music` switches to "prep" the
moment `current_shot()["scene"]` is `m7_runner_shotgun` or `m7_runner_gun`,
so the uneasy ticking starts as Alex hands over the shotgun and carries into
prep; chores stay on 16, raid-in/raid stay on 09. No other mission/state files
touched.
- Gates: `compileall -q src tools` OK, `ae_normalize --changed` OK,
  `python -m unittest tests/unit/test_m7_campaign.py` 29/29 OK,
  `smoke_test.py --only m7` **SMOKE TEST: OK**. `docs/ARCHITECTURE_MAP.md`
  updated; no baselines re-recorded.

---

## 19-track OST rollout (2026-11-16, uncommitted)

Seven new tracks in `tools/ost/album.py` (13 Wet Concrete, 14 After Hours,
15 Cold Iron, 16 Mending Wire, 17 Cold Marble, 18 To the Crossing,
19 Paper Trail), rendered by `python tools/build_ost.py 13 14 15 16 17 18 19`
into `assets/music/ost/` + `build/ost/` (all peaks -0.9..-2.6 dBFS). Wired
through `core/score.py` (mission-keyed `CALM`/`TENSE` dicts + `TENSE_DEFAULT`,
`is_tense` fade flag), `m7_audio`/`m7.flow` (farm=16, finale=19),
`m8_audio`/`m8.flow` (approach/mansion=17, trap=13, chase=18, flight=10), and
`app.py` (M6 film cues 15/07/19, BRIEFING + MISSION_COMPLETE play 19 and fade
on exit, `_keep_music_for_credits` preserves M8's title theme into CREDITS).
No gameplay rules, maps or dialogue touched.
- Gates: `compileall -q src tools` OK, `ae_normalize --changed` OK,
  `m5_finale_cut_check.py` OK, `smoke_test.py --only m6,m7,m8` **SMOKE TEST: OK**.
- `ae_ci.py --quick` still **FAIL** with the same pre-existing reds documented
  below (boundary E4/W1 87>51, D4/D6 greps, stale asset bake, 10 unit reds:
  m5 finale audio, m6 exposure 173>170, raw-loads, m8 chase/trap,
  ai_bundle_app) — none OST-related. `docs/ARCHITECTURE_MAP.md` updated.
- Rebuilt 13-19 from scratch (same session): nine new voices in `tools/ost/synth.py` (`cello`, `vibra`, `analog_lead`, `upright_bass`, `sub_kick`, `ind_snare`, `brush`, `shaker`, `clave`) and a clean replacement of the t13-t19 block in `album.py` — new meters (5/4, slow 4/4 noir, 6/8, 3/4, 4/4 march, 4/4 motorik, 4/4 chamber), no reused grooves/bass/progressions/motifs from 01-12. Filenames unchanged, so score/app/m7/m8 wiring stayed as-is. Re-rendered peaks/durations match the owner's verified values exactly (106.7s/-1.2, 118.9s/-1.9, 107.9s/-1.2, 89.7s/-2.3, 104.0s/-1.6, 86.1s/-0.8, 102.0s/-2.6). All gates re-run green where they were green before; `ae_ci.py --quick` reds unchanged (pre-existing).
- Owner still needs to listen to the cues in-game; no audio baselines exist.

---

## Shared 2.5D tactical HUD + night-grade pass (2026-11-16, uncommitted)

Owner's rollout across the shared grading/rim kit, shared HUD, walk3d, M1-M6
and MP Arena, applied verbatim. No gameplay rules, maps, dialogue or saves touched.
- **New `src/ui/tactical_hud.py`**: single source of truth for M1-M6
  `HUD_MARGIN=18`, `PANEL_GAP=6`, `TACTICAL_THEME`, `draw_tactical_corners`,
  `tactical_panel_bg`, `place_minimap`. `engine/ui/theme.py::Theme.panel()` now
  draws 2px brackets + top catchlight only when `extra["tactical_hud"]` (cache
  key includes the flag; default themes unchanged). `m6/hud_ui.py` re-exports
  the shared theme/panel helpers instead of owning copies.
- **Shared grade/rim** (`missions/m1/grade3d.py`, `game/topdown3d.py`): the
  grade now has native `.convert()` gradients, a bloomed "glow" radial, a
  rippled "reflect" streak and a 64-angle cached directional "cone" flashlight
  (6-tuple light). `td.add_player_rim` is the shared cool-rim + optional GL
  spot helper; M1-M5, walk3d and arena now route the player fill through it.
- **Night contrast/refs**: deeper blue-slate AMBIENT + darker wall caps, wet
  reflections, 2-layer grounded contact shadows, warmer sodium lamps in
  walk3d; M1/M2/M4 flashlight cones; M3 slate-teal (no prisoner torch); M5
  per-stage contrast + torch only in quarter/print/tunnel; arena ambient tone
  down so sconce pools pop. M6 puddle sheen extended to noman/rail aprons.
- **Layout**: all M1-M5 gameplay HUDs now pass `TACTICAL_THEME` to the shared
  `engine.ui.std` widgets, use `tactical_panel_bg` and 18px/6px margins, and
  call `place_minimap`. M4 siege/supply plates and M3 checklist use the same kit.
- Gates: `compileall -q src` OK, `ae_api_snapshot check` OK (89 modules/622
  names), `ae_text_check` OK, `ae_normalize --changed` OK, `ae_bench --check-budget`
  OK, full `smoke_test.py` **SMOKE TEST: OK**, all seven `m{1..6}/walk_td3d_shots.py`
  tools wrote their stills, `docs/ARCHITECTURE_MAP.md` updated.
- Pre-existing reds (not from this pass, in this dirty tree):
  `check_boundaries.py` E4 `ui.credits` + W1 87>51 (untouched files), and
  `test_m6_campaign` face-exposure 173>170 (cutscene-only; this pass touched
  gameplay `draw3d`, which `m6films` does not import). No baselines re-recorded.
- Owner still needs to eyeball the new grading/HUD in-game and decide whether
  to refresh `tests/golden/baseline_v0` (expected HUD/lighting diffs).

---

## M8 Duty route playable end to end (2026-11-15, uncommitted)

Mansion rebuilt (second pass): `duty/mansion3d.py` + `mansion_set.py` follow
the Revenge funeral estate. Five areas (gates, grand hall, gallery, study,
helipad terrace), checkpoints 0-4 (`--m8-cp=`), rifle + shotgun (suppressed
pistol removed), car explosions, falling chandeliers, heli liftoff under fire.
Interior uses flat colours; floors that sit on box tops must be layer 2 or the
box needs `skip=("top",)` (GL layers paint by slice, not depth). Liftoff films
reframed (camera stays on the terrace). Flight lawn moved to z 12, r 48.

Duty ladder approach -> mansion -> liftoff -> flight -> crash -> ridge ->
d_epilogue now runs to the outro. New: `missions/m8/duty/flight3d.py`
(door-gunner chase, 5 sections, `STATE.m8_flight_cp`), `duty/ridge3d.py`
(scope finale: zoom, sway, SHIFT breath, wind+drop, rescue timer retry),
crash + inauguration films in `cutscenes/m8dutyfilms.py`, timelines
`m8.d_crash` / `m8.d_epilogue`, VO_430-455 caption rows, beds `flight`/`ridge`.
Fixed mansion first-draw `KeyError: 'truck'` (draw fallback skipped the stage).
Gate `mission8_duty` OK; full smoke OK. Not played by hand yet: flight
difficulty/timing and ridge feel are untuned.

## Mission-complete case dossier (2026-11-15, uncommitted)

Replaced the legacy floating MISSION_COMPLETE card (and the interim CRT build)
with a physical KRAP Intelligence case file on a tungsten-lit desk. Owner's
patch applied verbatim; two owner-approved polish fixes:
- **`src/ui/mission_complete.py`** (605 lines, deliberately unlike
  `ui/mission_failed`): open manila folder with index tab + spine fasteners,
  taped 160x95 pixel-art field photograph (upscaled 2x nearest, one painter per
  mission), paperclipped audio transcript slip, cream FORM KR-47 sheet with
  bulleted outcome, dotted-leader ledger rows (`ELAPSED TIME .... 04:18`) and a
  tilted rubber stamp, plus a steel command rail (`y=624..700`).
  `PROFILES[key] -> (location, exhibit_caption, photo_kind, stamp_colour)`,
  `_DEBRIEF`, `ledger_rows` (no score/rank), `debrief_copy` (M8 splits on
  `m8_route`, stamp becomes CASE CLOSED), `button_specs` -> `[menu, continue]`.
  The whole sheet is cached on a signature and re-blitted: **one blit/frame**.
- **`src/app.py::_MissionCompleteState`**: `_has_next_mission()` +
  `_advance_campaign()` (the old chain, moved out verbatim) and thin
  `handle_event`/`render` delegating to the module; `enter()` latches
  `STATE.mission_end_time` when a mission ended without setting it, so the
  ELAPSED clock freezes instead of ticking on the debrief.
- **`src/game/content/strings/en.json`**: 17 `mc.*` keys (0 missing, 0 unused).
- **`src/ui/mission_complete_3d.py`** (663 lines): live engine3d diorama viewport
  embedded in the dossier exhibit Polaroid frame; one scene per mission using
  real meshes/textures/Humanoid rigs (krap_van, car_m2, barrel, molotov,
  pc_zarya, monitor_crt/lcd, medkit, pill_bottle, m7world3d farm, chase_set
  train/tractor, m6world3d snow/night/FX); slow camera drift, reduced_motion
  freezes, GL/software auto-select, ACA_MC_2D=1 opt-out, traceback-logged
  fallback, epoch-bumped static bake for M7. Per-cut PNGs in
  `shots/mission_complete_3d/`.
- **`tests/unit/test_mission_complete_ui.py`** (13 tests) + **`tools/preview_mission_complete.py`**
  (`MISSION COMPLETE CHECK: OK`, 9 dossier PNGs + 10 exhibit cuts, asserts the
  sheet cache is not rebuilt between frames).
- Gates: `compileall` OK, `ae_text_check.py` OK, `smoke_test.py --only
  radio,mission4,mission6,mission7,mission8` **SMOKE TEST: OK**,
  `m5_finale_cut_check.py` (MENU path) OK, `m5_shadow_check.py` OK.
- Polish fixes on top of the patch: the two footer lines are shortened by
  splitting the existing strings on ` - ` (they were ellipsized mid-word), and
  a short transcript gets ruled continuation lines instead of a blank slip.

---

## Shadow visibility pass: 2.5D + 3D (2026-11-15, uncommitted)

Owner's 4-group shadow patch, applied verbatim; nothing else touched.
- **Side-view blob collapse** (`engine3d/core.py:_blob_item`): screen
  width/height was measured by projecting world +X and +Z, so an east/west
  camera (`kill3d` 270, `raid3d` 90, yard/trap/chase scenes) collapsed every
  blob to a 4x3 px dot (or `None` near NEAR). Now the radius is projected
  along the camera's horizontal `fwd`/`right` basis (`r_side`/`r_fwd`, with
  `self.right` as the degenerate fallback) and the width uses the full 2D
  distance `hypot(ex[0]-c[0], ex[1]-c[1])`. Identical at yaw 0; measured
  51x27 px at N/E/W/S/NE on the same blob.
- **Bias sign** (`core.py:add_blob_shadow`): key is now `lay*1e6-c[2]+0.5-bias`,
  matching `add_sprite` and `GLRenderer.add_blob_shadow`; the old `+bias`
  pushed negative-bias shadows behind the floor.
- **2.5D layering** (`game/topdown3d.py`, `missions/walk3d.py`, `m1..m6/draw3d.py`,
  `ui/arena_view3d.py`): `td.cast_shadows` queued `layer=1, bias=-200.0`
  (alpha walk3d/arena 150, m1-m5 155; M6 stays 100 so `m6/draw3d._decode`
  is unchanged). Every `td.shadow`/`td.tac_ring` moved `layer=0 -> layer=1`
  with a negative bias, and `add_humanoid` now passes `shadow=(1, -0.5)`
  (M2 sniper deck `(2, -0.30)`). Dead-player shadows added in walk3d, arena,
  m1-m4 and M6.
- **3D ground layers**: `m6/train3d._shadow_for` always returns `_PLAT_SHADOW`
  (+3 actor calls); `m7/raid3d._GROUND_SHADOW = (1, -4.0)` for 6 actor calls
  + pig/dog blobs; `m8/chase3d` decks `(2, -0.30)` vs ground `(1, -4.0)` (+3
  vehicle blobs); `kill3d` catwalk `(2, -0.30)`; `trap3d._shadow_at(y)` picks
  catwalk vs ground per actor height.
- Gates: `compileall -q src` OK; `smoke_test.py --only
  m1,m2,m3,m5,m6,m7,m8,arena` **SMOKE TEST: OK**; `smoke_test.py --fast`
  **SMOKE TEST: OK**; `engine3d_check.py` worst diff 4.31% -> OK
  (software 14.3 ms / gl 6.7 ms); `tests.unit.test_cast_shadows`,
  `test_engine_core`, `test_gl_composite`, `test_m8_chase_gun` 36/36 OK;
  `ae_normalize --changed` OK.

---

## M3 Kill Order rebalance: de-meatgrinder pass (2026-11-15, uncommitted)

Owner's third patch batch, applied verbatim; all `ko_playability_audit.py`
invariants kept (`HOLDOUT_DOOR_FRAMES = 2700`, beat-gate wave IDs 0/1,
wave-3 closet flush).
- **`m3/sweep.py`**: `MAX_CONCURRENT` 9 -> 6; `ROLE_TUNING` softened
  (guard 80hp/68cd/11, breacher 100/56/13, shield 165/74/10,
  technician 75/82/9, marksman 90/100/22); `OVERWATCH_TELEGRAPH` 54 -> 78
  (1.3 s) and the marksman now fires ONE 22-dmg shot per cycle (was a 2x22
  burst) with a longer cool (`135+rnd(0,60)`); Wave 2 fires on
  "wave 1 cleared" or +1500 ticks (was a flat +900) with 4 spawns (5 before),
  Wave 3 drops one of its three line guards; holdout ring 1.6-3.2 -> 2.6-4.4
  tiles off the van, `holdout_cap = MAX_CONCURRENT` (was +2) and the pair
  cadence 200 -> 300 ticks.
- **`m3/world.py`**: 4 new `_KO_PICKUPS` on the fight route - bandages at
  (5,16), (19,25), (32,33) and a spare mag at (29,35); all on walkable floor,
  off `_KO_VAN_RECT`, all flood-reachable from the (6,3) spawn.
- **`m3/flow.py`**: KO checkpoint starts with 3 spare K-9 mags (was 2).
- Fixed a latent `NameError` in `src/tools/ko_playability_audit.py` (line 223
  used `_sweep_mod` before its import; now `sweep`), so the audit runs again.
- Gates: `compileall -q src` OK, `smoke_test.py` m3 pass **SMOKE TEST: OK**,
  m3 unit modules 22/22 OK, `ae_normalize --changed` OK, headless real-loop
  KO jump 301 frames clean. End-to-end headless KO probe: holdout commits at
  tick 197 with waves 0-3 wiped, exfil door cycle hits exactly 2700,
  stage -> `broadcast_transition` -> `broadcast`.
- Audit result: 10/14 PASS, the 4 reds are checks 3 (walk-only Router never
  reaches the van), 4 (Volkov bail starts 152 px from the stair, needs
  >=450), 7 (grand-tour jitter) and 8f (same walk failure). Proven NOT caused
  by the rebalance: re-running the audit with `MAX_CONCURRENT`/`ROLE_TUNING`/
  `OVERWATCH_TELEGRAPH`/wave rosters restored to the old values reproduces
  the identical 4 failures, and check 9 flips pass/fail between runs
  (bot/RNG flakiness). The invariants the brief names pass: 8a-8e (beat
  gates), 6 (closet flush), plus 1, 2, 5.

---

## M3 Kill Order perf pass: AI thrash + KO renderer churn (2026-11-15, uncommitted)

Owner's second patch batch, applied verbatim; no gameplay rules touched.
- **`entities/enemy_ai.py`**: `_can_see` clips against an AABB prefiltered
  subset (`collidelistall`, only when `len(walls) > 32`); `_update_pathfinding`
  returns early and bumps `path_timer` when A* yields nothing; `_move_toward`
  probes/collides against `near_walls`/`c_walls` (probe box, movement box) and
  only forces a repath on "both axes blocked" when it had a path (`had_path`),
  so a CHASE enemy parked behind a locked KO door stops re-running the full
  grid every frame. `_apply_move` uses the same movement-box prefilter.
- **`game/topdown3d.py`**: `put(..., static=True)`; dynamic props skip the
  `_cache["packed"]["placed"]` lookup/insert so spinning pickups stop wiping
  the 2048-entry static transform cache. `m3/draw3d._put` forwards `static`,
  and the spinning pickup gun / pickup mesh / Volkov mag / molotov pass
  `static=False`.
- **`m3/sweep.py`**: `draw_overwatch_laser` reuses one module-level
  `_LASER_LAY` SRCALPHA surface (cleared only inside the dirty rect, blitted
  dirty-only; beam-less frames dirty just the glint). `update_kill_order`
  hoists `_solid_walls()` out of the enemy loop, prefilters by the
  enemy->player segment bbox and breaks on the first sighting.
- **`m3/systems.py`**: `_m3_volkov_segment_clear` and
  `_m3_enemy_has_los_to_point` bbox-prefilter their wall lists;
  `_m3_volkov_build_grid` memoises on a `(len, x*, y*)` wall hash
  (`_VOLKOV_GRID_CACHE`, cleared past 8 entries) and hands out row copies;
  `_update_volkov_ally` drops `or not path` from the replan condition (no more
  full-grid rebuild every frame when the repath returns `[]`), clears
  `m3_volkov_path_goal` on `direct_clear`, and zeroes the timer when the path
  is consumed.
- **`m3/wings3d.py`** KO van: GL keeps the packed path; software bakes a
  world-space mesh once (`("van_world", vx, vz)`) and `add_dynamic`s it.
  Beacon pulse/colour quantised to eighths (`bq`) so `D._glow` stops
  rebuilding a surface every frame.
- Gates: `compileall -q src` OK, `smoke_test.py` (m3 run) **SMOKE TEST: OK**,
  `tests/unit` m3 modules 31/31 OK, `ae_normalize --changed` OK, and a
  headless `--jump m3-kill-order` loop (301 real frames, software renderer)
  exits clean. `tests/unit` full discover: 9 reds, all pre-existing/unrelated
  (m5 `Channel.id` pygame-ce mismatch, m6 exposure 173>170, assets raw-load
  scan, m8 chase/trap).

---


## AI Bundle app: paste a file request -> clipboard (2026-11-15, uncommitted)

`tools/ai_bundle_app.py` (gui) turns an AI's "share these files" message into one
paste-ready bundle: folder bullets scope bare names, `mN/`, `ui/`, `core/`
shorthands and `{1..6}` braces resolve, and >800-line files are sliced by the
names the message asks for (AST defs/classes/module constants + the enclosing
class header + the import prologue; whole file when nothing resolves, or when a
slice would cover most of it). Header format = `ai_bundle.py`'s, so they are
interchangeable. `--selftest` pins the 15-file example, `--check FILE` prints the
manifest. Built to `apps/AIBundle.exe` by the new `tools/build_apps.py ai_bundle`
(onefile/windowed, `tools/ai_bundle.ico`). Gates: selftest OK,
`compileall -q src`, `AE NORMALIZE --changed`, `smoke_test.py --fast` all OK;
`sync_arch_map.py` run (line counts of the in-flight edits above).

Bug sweep after the first build (all fixed, exe rebuilt): `./src/x.py` (and
`src\\x.py`) were dropped by the path regex lookbehind; markdown
backticks/asterisks leaked into descriptions and repeated paths appended the
description twice; a URL tail (`https://x/docs/state.py`) resolved to a project
file; "full file" in the description now disables slicing; the theme switch ran
a second Tk mainloop in the dead window (now the same restart-after-mainloop
pattern as `paste_apply.py`, with pending `after()` jobs cancelled); the
`time.time()` paste window became a `state["built_text"]` comparison, so typing
right after a paste refreshes instead of being skipped.
Known edges, accepted: a bare ambiguous name (`draw3d.py`) is reported "not
found" rather than expanded to every mission; the body-text relevance pass can
pull a few extra helpers into a slice.

---

## Weapon-swap animations: 2.5D campaign/MP + 3D trap (2026-11-15, uncommitted)

Owner's focused diff applied verbatim across four files; no gameplay rules,
maps, dialogue or saves touched.
- **2.5D shared** (`src/game/topdown3d.py`): `_SWAP_TUCK` +
  `apply_swap_pose(pose, k)` ease the arms/gun down to a hip/sling tuck
  (wrap-safe, spine/head follow). Campaign draws route through
  `m1.draw3d._body`, which now derives the swap from `STATE.weapon_swap_timer`
  for the `"player"` key only (melee wins), forces `ready` and applies the
  tuck; flash kick is suppressed during the swap. `_Meta3D` in
  `ui/arena_view3d.py` tracks `rig`/`from_rig` and decrements the networked
  `v.swap_timer`, drawing the old rig until the midpoint.
- **3D trap** (`src/missions/m8/revenge/trap3d.py`): `SWAP_S = 0.44`,
  `_swap_pose()` (bladed Fallow/OS-12 ready hold -> tuck), `_switch_weapon`
  keeps `self.weapon`/`MAG`/`mag` immediate but renders `_swap_from` for the
  first half, flips the mesh at `swap_u >= 0.5` with a `rifle_handle` cue,
  eases `SG_BLADE_YAW` so the hips never snap, and gates `_fire`,
  `_begin_reload` and ADS. Climb uses `instant=True`.
- Gates: `compileall -q src` OK, `AE NORMALIZE --changed` OK,
  `smoke_test.py --only m2,m3,m5,m8,arena` and full `--fast` both
  **SMOKE TEST: OK**; `test_m8_trap_mechanics` swap test passes (the other
  2 reds - missing `smokes` attribute, truck crash - reproduce at HEAD,
  proven by reverting `trap3d.py`). Headless probes drove both trap swap
  directions (40 draw frames each) and the 2.5D `_body` swap with no faults.
  Owner playtest still wanted: `--dev-mission2-game` (Q), arena, and
  `--dev-mission8-trap` (Q/1/2/wheel).

---

## M1 Volkov standoff: pacing, framing, the run, the captions (2026-11-15, uncommitted)

Owner's four complaints (frozen pacing/spotter, flat camera with a snap on escape,
half-speed run that popped out of a closed shutter, 24 px legacy subtitle bar) are
fixed in `m1/update.py`, `m1/draw.py`, `m1/draw3d.py`, `core/interactions.py`
(+ `tools/smoke_test.py` expectations).
- **Root cause of the freeze**: `_standoff_update()` returns True (frame frozen), and
  the whole escape block lived below that early return in `game_update`, so the run
  never advanced during the standoff. It is now `_update_volkov_escape()`, driven from
  the standoff's own `escape` phase AND from `game_update` (after `Door.update`) for
  the loud route. Do not put per-frame world work below that early return (buglog
  bug-332).
- **Phases**: `talk` (speechbox `Pacer` + `reveal_window` timing, Volkov backpedals
  toward the bay on beat 3+) -> `spot` (28 frames, K nudged into the row-25 gate
  doorway so the red '!' lands on a visible body; camera frames all three) ->
  `escape` (latch the alarm, hold `_STANDOFF_ESCAPE_FRAMES = 56` on the sprint,
  `bar_k` fades the letterbox).
- **The run**: `volkov_escape_timer` 90 -> 210; shutter lifts to 0.58, he ducks under
  it (2D body squashed + `pose_run` blended 42% into `POSES["crouch"]` in 2.5D), it
  slams behind him, then he runs east along row 30 to `(26*64+48, 30*64+36)`. Draw
  uses `_m1_volkov_angle` (no per-frame re-aim at the old tile centre).
- **Captions**: `LETTER_H` bars via `bar_k` and `ui.speechbox.draw_caption` (bitmap
  font), replacing the hand-rolled 24 px strip; `STANDOFF_BAR_H` deleted.
- **2.5D camera**: `_standoff_cam()` eases `cam_blend` (pitch -13, dist -7.5, fov -4,
  look_h +0.45; 0.55x in the escape) with a snap guard for teleports; the bay shutter
  cutaway is suppressed while the standoff/escape runs so the door reads.
- Gates: compileall, `ae_dialogue_check`, `ae_text_check`, `smoke_test.py --only m1`,
  full `--fast` smoke (OK), `ae_normalize --changed`, `m1_td3d_shots.py` all pass;
  2D + 2.5D probe frames looked at (talk/spot/escape, doors end at 0.0, final pos
  ~(1704, 1956)). **Not** hand-playtested: `python acaristan.py --dev-m1-game` and
  `set ACA_TD_2D=1` are the owner's.
- Pre-existing reds (proved by stashing this work, NOT caused by it):
  `tools/check_boundaries.py` (E4 `ui.credits` + W1 76 > 51 from untracked files) and
  `tools/ae_replay.py check --only m1` (dirty-tree content drift). No baselines were
  re-recorded.

---

## M6 rail lag and K-9 supply (2026-11-15, uncommitted follow-up)

The three top-down stages and train share the K-9 supply; the authored maps had
no ammo pickups. The committed supply ladder (`9d03fae`) now starts with four
spares, drops a mag every second Guard kill (six-spare cap), floors spares at
no-man's-land/rail/train entry, and gives the separate yard 150 reserve and a
2.4 m body-loot radius. `tools/m6_ammo_check.py` passes.

The rail 2.5D GL path still cost 54–71 ms **draw-only** (six Guards, ten corpses)
despite culling/decode work (`17618b1`). `m6/draw.py` now gates rail to its
existing 2D painter by default (9–10 ms in the same probe), including the 2D
aim ray; `ACA_M6_RAIL_25D=1` opts back into 2.5D. Customs/no-man's-land and
the dedicated train/yard scenes are unchanged. `m6/draw3d.py` also caches
settled corpse geometry on software only for the opt-in path (pixel parity in
two views). Gates: ammo check, targeted M6 smoke, full `--fast` smoke,
compileall and AE NORMALIZE --changed OK. M6 unit suite passed 57 earlier,
but the current shared-film worktree now fails an unrelated
`test_face_exposure_is_readable_on_software_frames` (insert-ground mean 173 >
170; deterministic rerun). The rail gate regression itself passed. No
hand-playtest yet.

---

## M8 trap perf + tex3d path fixes (2026-11-14)

Owner's second audit (trap lag + textures never loading) applied; `textures.py`
and `trap3d.py` only.
- **Per-frame repack gone**: `_truck_crashed` mesh is built once and reused
  (the old code wrapped ~15k faces in a new `Mesh()` every frame, repacking the
  CPU vertices and leaking `RW._ROWS`); the truck's crash fire is a
  `F.flame_mesh` for 28 s, the wreck TTL 28 s.
- **Blasts made cheap**: no more full-frame `F.sparks` on layer 2 (moved to
  `_fx.FX_LAYER`), smoke/dust ring replaced by `self.smoke_puffs` +
  `_blast_puff_fn` (cached 32x32 puff images, quantised radius, 60 px bounds),
  debris packed into ONE `Mesh` per frame, scorch discs cached in one mesh.
  Fireball shortened (5/4 lobes), streak count/shortened, barrel puddle uses
  `F.flame_mesh`. Truck smoke is emitted from `update` (0.24 s cadence, 56-puff
  cap) instead of draw.
- **Deviation (named)**: the scorch cache keys on `tuple(self.scorches)` rather
  than only its length, so decals keep updating after the 16-slot cap (a
  count-only key freezes once the ring buffer is full).
- **Textures**: `textures._root()` now falls back to the repo-root `assets/tex3d`
  when cwd isn't the repo (verified from `C:/Users/BIRIBEL`: root resolves,
  `concrete`/`snow` load); paletted PNGs are converted with `.convert(24)`
  before `array3d`.
- **GL is live here** (`gl_info().available True`, Radeon RX 7800 XT). Software
  mode still rasterizes the ground on CPU (~418 ms/frame probe) — do not judge
  perf there; GL probe with burning wreck + 3 blasts + debris: **15.9 ms/frame**.
- Gates: compileall, AE NORMALIZE, engine3d parity (worst 3.26%),
  `mission8_vertical_slice` 7.3 s (was 42.5 s), m7 + `--fast` smoke OK.
  Probe frames in `.qoder/tmp/trap_*.png` (scratch). Owner playtest:
  `python acaristan.py --dev-mission8-trap`.

---

## M8 trap: sniper beam, truck HP, real explosions, reloads, frag grenades (2026-11-14)

Owner's six-issue audit + drop-in patches applied (half of them had landed in a
prior session; this pass completed the render/update wiring and the HUD).
Files: `src/engine3d/rig.py`, `src/cutscenes/m6world3d.py`,
`src/missions/m8/m8_audio.py`, `src/missions/m7/raid3d.py`,
`src/missions/m8/revenge/{trap_brain,trap3d,trap_hud}.py`, `tools/smoke_test.py`.
- **Sniper line**: overwatch laser is now a depth-tested, segmented, camera-facing
  layer-2 ribbon out to 105 m vs Biribel's chest (+ optic glint + surface dot),
  so cover and the player occlude it. `_finished` wobble no longer terminates
  mid-air beside him.
- **Truck boss**: `TRUCK_HP 150 -> 580`, gunner 74 -> 110; engine/cab weakspot
  (9/15) vs rear armour (5/9.5); `pending(2)` keeps the wave open until the truck
  is actually crashed; smooth crash skid/nose dip, secondary cook-off, persistent
  burning wreck and a 35 s light.
- **Explosions**: barrel/truck/grenade blasts are now dicts driven by one
  `_draw_blasts` (multi-lobe `F.flame_mesh` fireball, `_fx.flash`, pool, dust
  ring, 3D shrapnel debris with bounce, cooling streak lines, dark alpha smoke,
  scorches). Barrels also damage the truck (`BARREL_TRUCK_DMG 260`).
- **Reloads**: `rig.os12_mag_mesh()` + `os12_mesh(with_mag=...)`, `nomag` flag in
  `m6world3d.hum`; OS-12 drops its mag (physics + ground pickup), swaps from the
  belt and racks under the receiver; Fallow 12 gets the shared shell-by-shell +
  pump-rack reload (`raid3d.sg_reload_pose` / `draw_sg_shell`).
- **Grenades**: soldiers wind up (`throw_t/throw_at/throw_dst`, arm pose, grenade
  in hand), lob a bouncing/rolling frag (`_grenade_mesh`, wall ray, fuze sparks,
  HUD diamond warning with edge clamping, cover-mitigated blast).
- **Deviations (named, minimal)**: `_fx.scope_glint` does not exist in
  `m6fx3d`, so the optic glint uses `_fx.glow(..., strict_occ=True)`; the smoke
  M8 wave loop now also calls `damage_truck(tr, 999)` — required by the new
  `pending(2)` rule, otherwise the gate sits in `w2` forever.
- Gates: compileall OK, AE NORMALIZE OK, **AE HOLD: OK**, engine3d parity OK
  (worst 3.26%), `test_faces3d` 6 OK, **SMOKE TEST: OK** (m7 + `mission8_vertical_slice`
  + `--fast`). Software probe drove the trap: grenade detonated, truck crashed +
  cook-off, barrel chain, OS-12 mag drop, both reload animations, laser lock, all
  while drawing; frames in `.qoder/tmp/trap_{grenade,truck_boom}.png` (scratch).
- Not yet: owner playtest in `--dev-mission8-trap` (feel of 580 HP, grenade
  cadence, reload choreography).

### Re-measured 2026-11-15 (same tree, headless probes)

- Fallow 12 full dry reload: **3.26 s**, shells seat at 0.47/0.91/1.35/1.79/
  2.23/2.67 s (0.44 apart), dry pump-rack at 2.95 s, mag 6 / reserve 18.
  Partial (2 shells into a mag of 4): 1.22 s, no pump. Same numbers in M7's
  `raid3d` scene.
- OS-12: 1.45 s, mag drop -> belt grab -> seat -> under-receiver charge all
  fire, 1 mag physically dropped, mag 30 / reserve 60.
- Truck: 580 HP; one shotgun blast into the **front engine** reads **72**
  (8 x 9), into the **rear bed** **40** (8 x 5); 2 wreck blasts on crash +
  cook-off 0.58 s later; persistent fire/smoke puffs.
- Grenade flush: soldier wind-up, 1-2 airframes, blast, cover-mitigated damage
  (player 100 -> 57 through open ground), 14 debris, scorch, HUD diamond.
- Frame cost of the burning wreck close-up with 6 live enemies: **18.4 ms GL**
  (software 398 ms). Removing puffs/blasts/debris moves it to 17.2-17.6 ms, so
  the new FX are ~1 ms and the software number is scene/camera, not FX.

---

## M7/M8 shotgun: bladed hold + a pump that actually slides (2026-11-13)

Owner's patches applied (his diagnosis was right on both counts) and verified;
the look itself still needs his eyes.
- **Where the hand was**: Biribel stood square, so `hold_frame`'s
  `ARM_REACH = 0.58` clamp lerped the left target fore->guard and parked his
  fist on the receiver (z ~0.20). **Where the wood was**: `shotgun_mesh()` baked
  the wooden fore-end in, so nothing could slide.
- `src/engine3d/rig.py`: `shotgun_pump_mesh()` (wood + 7 grain bands, centred on
  z=0) extracted; `shotgun_mesh(with_pump=True)` keeps the old look for films /
  MP / kill3d, `False` leaves the wood out for M7/M8.
  `src/cutscenes/m6world3d.py`: `hum(flags=("shotgun","nopump"))` -> pump-free
  rig with its own `|shotgun_nopump` GL spec key.
- `src/missions/m7/raid3d.py` owns the new shared kit: `SG_BLADE_YAW = 25`,
  `_sg_holds` (cached bladed solve -> rest pose / racked left arm),
  `_shotgun_hold` (+25 twist, head_y -22, spine-following rifle_p),
  `draw_shotgun_pump` (wood at `PUMP_REST_Z 0.350` -> `PUMP_BACK_Z 0.275`),
  `_pump_k` (`PUMP_DELAY 0.12`, `PUMP_DUR 0.32`). M8's trap scene just calls
  `R._sg_holds` / `R._shotgun_hold` / `R.draw_shotgun_pump` with the same
  `("m7player_sg", mode)` key (one cache, one solve).
- The gun is solved -25 deg in body space and the root is drawn +25, so the
  barrel still lands on the crosshair: **one extra cached re-aim pass** was
  needed, because the hold aims from the shoulder pocket (0.15 m off the grip)
  and one solve left the bore 1.1 deg off (measured). Re-aiming about the gun
  origin drops it to 0.0.
- **Measured** (real joints, full stroke, aim mode): left hand in gun space
  `(0, 0.025, 0.350)` -> `(0, 0.025, 0.275)`, i.e. 7.5 cm dead straight back
  along the bore with zero climb; `hold_report` support 2.0 cm at rest (hand on
  the front of the wood, 2 cm past the `fore` grip point) / 0.0 racked, arm
  clash 1.6 cm (< 3 cm). Ready mode reaches 0.330 -> 0.275 (5.7 cm: the lowered
  stance can't quite reach 0.350) and still slides on the wood.
- Gates: `python tools/ae_hold_check.py` -> AE HOLD: OK.
  `python tools/smoke_test.py --only m7,m8` -> SMOKE TEST: OK (m8 has no
  registered smoke checks, so also drew 6 frames of each scene headless:
  hip/ADS/pump, `_draw_player` hit 12x/6x, no exception).
  `compileall` clean; `ae_normalize --changed` lists none of the touched files.
  `check_boundaries` still reports W1 70 > 51, but from `core.console`'s lazy
  `missions.m2/m3` imports (pre-existing dirty tree); this pass adds no
  shared->mission edge.
- Not played: sign-off for hip + RMB aim in `--dev-mission7-raid` /
  `--dev-mission8-trap` is the owner's.

---

## M8 trap/kill: the flash no longer draws through Biribel (2026-11-13, unverified)

Owner's diagnosis + patches applied verbatim; NO gates run (owner's instruction).
`src/engine3d/gl.py` + `src/missions/m8/revenge/trap3d.py`.
- **Why it showed through the body**: `_fx.glow()` tags `draw.light = True`, so
  GL treated the muzzle halo as a streetlamp: `zeff - 0.45` depth cheat plus
  "anchor probe >= 0.75 -> vis = 1.0" (no per-pixel mask). At 0.15-0.45 m from
  the head/shoulder the whole bloom drew over him. The halo also sat on
  `_fx.FX_LAYER` (6), which outranks layer-2 actors on BOTH backends, and the
  3D mesh was submitted with `bias=-0.04`.
- **gl.py**: new opt-in `strict_occ` sprite flag in `_composite` - skips the
  <= 196 px centre probe and the `frac <= 0.12` fast path, culls at
  `frac >= 0.999` (fully behind geometry), otherwise masks per pixel. `light`
  stays untouched, so lamps keep the 0.45 m bias and the anchor gate.
- **trap3d**: `FLASH_S = 0.044` + new `FLASH_S_SUPP = 0.028`; `handheld_flash`
  rewritten - root vertices 0.004 m ahead of the tip, `bias=0.0`, halo on
  `layer=2` with `light = False` / `strict_occ = True`. The OS-12 (suppressed)
  branch is now a 6-sided axial bore dart (core_r 10 mm, throat 13 mm, wisps
  <= 16.5 mm) that stays inside the rig's 25-27 mm suppressor can, pale
  cream -> amber -> sooty rust, 12 px halo; the Fallow 12 keeps a 5-fin crown.
- Also: `_switch_weapon` clears `last_flash` (no flash on the other gun), the
  `_lights()` muzzle light is per-weapon (0.55 / 3.2 m suppressed vs 1.45 /
  5.5 m), `draw()` gates on `FLASH_S`/`FLASH_S_SUPP`, and `TrapScene._draw_fx`
  replaces the borrowed `RaidScene._draw_fx`: tracers are layer-2 3D
  cross-quad ribbons and flecks/flash arms use `layer=2` instead of layer-3
  unoccluded lines. `kill3d` inherits the fix through `T3.handheld_flash`.
- Not yet: smoke/compileall/unit/ae_ci, and the visual check in
  `--dev-mission8-trap` / `--dev-mission8-kill`.

---

## M8 Part 2 re-audit + the three gaps it left (2026-11-13, uncommitted)

The owner re-sent the Part 2 spec (twilight lighting, sandbags, kiosk, smoke,
dual guns, HUD, kill pacing). It was already applied in the "plaza fight
rebuilt" pass; this pass audited it line by line and closed the three things
it had actually left undone.
- **Already in the tree** (verified item by item): `set3d` FOG/LIGHT/SKY_TOP/
  SODIUM + `SANDBAGS` + `_fortifications()` (called in `renderer()`, with
  `CS.tractor()` still at `TRUCK_AT`); `trap_world` sandbag colliders,
  `KIOSK_AT`, `ray_hit_static()`; `m8_audio` `m8_smoke`/`_smoke_hiss`/
  `rifle_shot`/`smoke_hiss`; `trap_brain` the truck-gunner `los3d` fix, the
  smoke flush, `alive_in_wave()`; `trap3d` the Q/1/2/wheel swap, kiosk +
  barrier meshes, smoke rendering, 2.3 s climb, per-weapon FOV_ADS, the
  dual-weapon `_fire()` with `ray_hit_static` + the truck-gunner hit priority,
  the corpse-carry fix, the auto-shotgun on climb; `trap_hud` the kiosk blip,
  the weapon readout, the peripheral hit flash; `kill3d` 1.1 s / 15.5 CPS.
- **Gap 1 - `_smoke_can_mesh()`** was in the prose but in neither the code
  block nor the draw path: the canister was only a glow sprite. Added the
  mesh (a stubby cylinder) and it now flies on the arc and lies where it
  landed.
- **Gap 2 - the barrier arm never lifted.** The spec computes `arm_pitch`
  but `RW.put()` takes a yaw only, so the arm always rendered flat. There are
  now two meshes (`barrier_arm` / `barrier_arm_open`, the arm rotated 72 deg
  about its hinge with `rot_z`) and the open one is used when the lane is
  open. Frames `shots/m8_trap/gate_closed.png` / `gate_open.png` show it.
- **Gap 3 - `self.gate_open = True` in `_clear(1)`** (the plaza is clear, so
  the north lane opens). Note this makes the kiosk's "advance1" branch
  unreachable if the prompt keeps gating on `not self.gate_open`, so the
  prompt now gates on "wave 2 has not rolled in" (the phase) instead, and
  `_open_gate()` tolerates an already-open gate (it still starts wave 2 and
  takes the checkpoint). The kiosk is therefore usable during wave 1 (the
  rolling breach, <=2 stragglers left) AND in advance1 (skip the wait).
- The AK-74 stays out: the "rifle" slot is the OS-12 (5.56X45) and the flash
  is the bore-locked `handheld_flash`, not `flash_star` - both were the
  owner's own later instructions.
- Gates: `smoke_test.py` -> **SMOKE TEST: OK**, `test_m8_trap_mechanics` 10/10,
  `test_hold` OK, compileall OK. New regression:
  `test_clearing_wave_one_opens_the_north_lane`.

---

## M8: the muzzle flashes rebuilt (2026-11-13, uncommitted)

Owner listed five real bugs in the M8 flash code; all five are fixed.
`src/missions/m8/revenge/{trap3d,kill3d,chase3d}.py` (+ `m8_audio.py`,
`trap_hud.py` for the caliber).
- **1. The stick-figure arms are gone.** `_fire()` no longer appends to
  `self.flashes`, so the inherited `raid3d._draw_fx()` stops drawing the
  rigid 22 cm FLASH_ARMS sticks through the 3D flame on every player shot
  (the Guard shots still use that language - they are the raid's own look).
- **2. The flash is no longer stale.** `_draw_player()` now computes
  `_flash_basis = (tip, fvec, rx, ry)` from THIS frame's `joints["rhand"]`
  and `joints["rifle_m"]`, so the flame leaves the bore of the gun as it is
  held - not the previous frame's hip-height muzzle.
- **3. The bore is the gun's own.** `trap3d.BORE_LOCAL` holds the bore in the
  gun's frame: the Fallow 12's top barrel `(0, 0.090, 0.702)` (rig.shotgun_mesh
  `tube(0.017, 0.18, 0.70, 0.090)`) and the OS-12's suppressor can
  `(0, 0.005, 0.640)`. The direction is the bore axis
  `m_apply(rifle_m, (0,0,1))`, NOT the camera ray.
- **4. The flame is emissive.** `chase3d.flash_star()`'s 13 faces now pass
  `emissive=True` (they were being shaded by the dawn directional light into
  muddy dark red-brown), and the new `trap3d.handheld_flash()` builds every
  face emissive too.
- **5. The flash is handheld-sized.** `handheld_flash()` is a compact
  4-blade crown + axial jet fins + a soft bloom sprite: 24 cm for the
  Fallow 12, 14 cm for the suppressed OS-12, 42 ms, with a muzzle light in
  `_lights()`. (The old `flash_star` cone was 42 cm.)
- OS-12 caliber is now **5.56X45** (HUD panel + the loot toast "+N SH / +N 5.56").
- Gates: `ae_hold_check` -> **AE HOLD: OK**, `test_hold` +
  `test_m8_trap_mechanics` OK, compileall OK, `smoke_test.py` ->
  **SMOKE TEST: OK**. Frames in `shots/m8_trap/kill_flash.png` (gitignored):
  the kill scene's flash is a compact warm crown at the bore; the trap's is a
  small warm point at the muzzle (the third-person camera looks down the
  gun, so the flame is seen end-on).
- **Gotcha for the next session:** the rig's gun follows the BODY, and
  `body_yaw` eases toward `yaw` at 10/s - teleport the player and the gun
  keeps pointing where the body was for a second. A probe that sets `sc.yaw`
  must run ~40 frames before the flash will point where you expect.

---

## M8: the AK-74 is out, the OS-12 is everywhere (2026-11-13, uncommitted)

Owner: "remove the AK-74 / Guard akrifle in M8 and use OS-12 for Biribel and
all Guard NPCs" (plus the optional Bodi swap). Applied across
`src/cutscenes/m6world3d.py`, `src/missions/m8/m8_audio.py`,
`src/missions/m8/revenge/{trap3d,trap_hud,chase3d}.py`,
`src/cutscenes/m8films.py`.
- **`m6world3d.hum` learned `flags=("os12",)`** for biribel, `("guard", kind)`,
  `("ally", name)` and the plain `"guard"` key: the rig's own
  `engine3d.rig.os12_mesh()`, grip set `os12`, muzzle 0.64 m (as `ui/mp3d.py`
  has it). The guard branch writes `extra["rifle"] = "os12"` BEFORE
  `_guard_humanoid` (the spec builds the mesh) and then overrides
  `_weapon`/`_muzzle_z`/`_gl_spec_key` after it - without the `_gl_spec_key`
  the GL renderer reuses the old VBO. The `ak74` flag stays in the engine
  (it is a real asset; M8 simply no longer uses it).
- **Trap**: the "rifle" slot is the OS-12 (OS-12 / 9X39MM / 30 rounds, still
  the plaza combat tuning); Q/1/2/wheel swaps Fallow 12 <-> OS-12; every
  Guard carries the OS-12 (hold key `("m8_guard", kind)`); bodies give both
  calibres; the HUD panel is `cw="os12"`, `kind="stick"`, `reload_ms=90`
  (matching `weapon_panel.RELOAD_MS["os12"]`).
- **Chase + films**: the heli crew, the gun-truck/jeep crews, the foot
  soldiers, the captors, the funeral honour guard and the heli door gunner
  all take `flags=("os12",)`; `("guard","heavy")` is warmed in the chase's
  `begin()`.
- **Bodi (the optional block) IS applied**: in M8 he carries the OS-12
  (`m8films._bodi_gun`/`_bodi`, and the trap's own `_bodi_pose` - the raid's
  ally pose re-posed for the os12 hold keys, since `R._ally_pose` hard-codes
  the no-flags ally hum and would pose him for the m7rifle).
- Gates: `python tools/ae_hold_check.py` -> **AE HOLD: OK**, `test_hold` +
  `test_m8_trap_mechanics` OK, compileall OK, `tools/smoke_test.py` ->
  **SMOKE TEST: OK**, `ae_ci` -> **AE CI: FAIL** with the SAME reds as before
  this change (boundary W1 ratchet, D4/D6 greps, the pre-existing unit reds,
  the stale asset bake, the 346 goldens - identical count, so the OS-12 swap
  moved no golden - replay, loop parity, mission0); smoke, compileall, api
  snapshot, data validation, engine3d parity and **3D cutscene weapon holds**
  all OK.
  Frames in `shots/m8_trap/os12_*.png` (gitignored): the HUD reads OS-12 30/30
  and the Guard's OS-12 sits in both hands.
  `docs/ARCHITECTURE_MAP.md` updated (the flags, the M8 stage row, the
  controls).
- Still yours to eyeball in-game: `--dev-mission8-trap`, `--dev-mission8-chase`,
  `--dev-mission8-heli`.

---

## M8 Route 12 trap: the plaza fight rebuilt (2026-11-13, uncommitted)

Owner supplied the full drop-in replacement for the M8 trap set (audit + five
files) and a second pass on top of it (twilight lighting, sandbags, the toll
kiosk, the AK-74, smoke, the bore-aligned flash). All of it is applied.
Files: `src/missions/m8/m8_audio.py`, `src/missions/m8/revenge/{trap_world,
trap_brain,trap3d,trap_hud,set3d,kill3d}.py`, `src/cutscenes/m6world3d.py`
(one additive branch), plus a NEW `tests/unit/test_m8_trap_mechanics.py`.
No map, dialogue, timeline, save or mission-state changes.
- **The fight is now beat-based, not timer-based.** approach -> w1 (wrecks,
  floods on, gantry laser) -> advance1 (supply crate) -> w2 (the Guard convoy
  truck with hull HP: shoot the engine or blow the lane drum to crash it)
  -> advance2 -> w3 (the gantry-foot holdout) -> clear -> the ladder.
  Vasile comes over the PA per beat and appears on the catwalk at wave 3.
- **New Guard roles** (`trap_brain`): rifle, breacher (pushes inside 14 m),
  overwatch (gantry/watchtower sniper, laser lock, faster in the floodlights),
  officer (squad lead), gunner (rides the truck bed). The truck's gunner is
  hit through its own hull now (`ray_hit_static`).
- **Two guns** (`trap3d`): Fallow 12 (6) and AK-74 (30), Q / 1 / 2 / wheel;
  the AK needs a new `m6world3d.hum` "ak74" flag so the mesh and the
  `ak74` grip set match. Ammo pools per gun; corpses give both calibres.
- **Props**: fuel drums (chain detonation), the floodlight fusebox, the
  supply crate, the toll kiosk (E opens the north lane = the wave-1 ->
  wave-2 gate), a steel watchtower, Guard sandbag bunkers
  (`set3d.SANDBAGS`, read by `trap_world` too).
- **Guard smoke canisters** answer a camper: they break the overwatch lock
  and force a move.
- **Lighting** is now pre-dawn twilight (fog 22-210 m, ambient 0.28) so the
  floodlights, lasers, blasts and embers pop; `kill3d`'s intro/typing lock
  was tightened (1.1 s push-in, 15.5 CPS) and both scenes use
  `chase3d.flash_star` for the bore-aligned muzzle flash.
- Gates: `python tools/smoke_test.py` -> **SMOKE TEST: OK** (the M8 vertical
  slice plays meet -> trap -> gantry -> friends -> kill -> descent -> chase
  -> epilogue), compileall OK, new `test_m8_trap_mechanics` 9/9 OK, full
  unit suite 565 tests with the SAME 2 failures + 4 errors as before this
  change (proved by stashing: `test_m8_chase_scenery` 8 != 10 is the prior
  session's `chase_set.ROADSIDE_SITES`, plus m5 finale audio and m8 chase
  gun errors and the raw-loads check - all pre-existing).
  `python tools/ae_ci.py` -> **AE CI: FAIL**, all reds pre-existing and
  provably not ours: smoke/compileall/api-snapshot/data-validation/
  engine3d-parity/**3D cutscene weapon holds** all OK; the reds are the
  boundary W1 ratchet (70 > 51, every source is core/ui/cutscenes - none of
  them touched here), the D4/D6 greps, the unit reds above, the stale asset
  bake, the goldens (346; the golden set has NO m8 shots - it covers m1-m7,
  which the prior sessions' uncommitted work already moved), replay, loop
  parity and mission0 diff.
- Owner playtest still wanted: `python acaristan.py --dev-mission8-trap`
  (the waves, the kiosk, the AK, the smoke) and `--dev-mission8-kill`.

---

## M8 Route 12: the south road now leads out of the valley (2026-11-13, uncommitted)

Owner: the approach road "came out of nowhere" - a giant black hill sat on it
and the road died against it 55 m behind the player. Only
`src/missions/m8/revenge/set3d.py` changed (the set bake); no gameplay, map,
dialogue or timeline edits.
- **Root cause**: `hills.add(W7._bipyr(-40.0, 0.0, -240.0, 160.0, ...))` - a
  160 m-radius peak centred 240 m south, whose front wall reached z=-80, right
  where the straight road ran. Removed (verified gone in `git diff`).
- **Now**: `south_road_x(z)` is a valley S-curve (straight at the gate, then
  -76 + 18*sin, bulging east to x=-58 at z=-180 and back to -74 at z=-300);
  the road runs z=-310 -> the map edge (row 79), so it fades into the mist
  instead of hitting a wall. Two flanking ridges (x=-195 and x=+45, z=-255)
  frame an open pass (x in [-115,-30]); a far hazy ridge at z=-400 keeps its
  nose clear of the road end (r=95 at z=-370 would have swallowed it AND the
  valley lights - fog kills anything past 300 m, so the backdrop must sit
  inside that).
- **Dressing**: telegraph poles + sagging wires on the east shoulder
  (z=-36..-244), Route 12 sign at z=-44, dirt farm track branching west at
  z=-72 to a burned farmstead/silo at (-118,-108) (Bodi's Valea Seaca echo),
  distant valley town/highway lights (emissive, so they cut through the fog)
  at z=-265..-300, post-and-rail fences following the curve with a gap at the
  turnoff, and the perimeter hedgerow pushed 16 m off the road (the spiky
  diamond bush in the foreground is gone).
- **Two engine traps found** (see cerebrum): `Mesh.face` winding decides the
  baked normal (a wrong-way ground quad renders 2.5x too dark - all new ground
  quads go through `set3d._flat`), and `m7world3d._fence` is axis-aligned only
  (it would lay a diagonal rail as a 16 m x 3 m slab - the curve fence uses
  the new `set3d._rail_fence`, and the wires are thin tubes, `set3d._wire`).
- Gates: `python tools/smoke_test.py` -> **SMOKE TEST: OK**, compileall OK,
  AE NORMALIZE OK, `tests/unit/test_m8_chase_*` 30/31 - the one failure
  (`test_two_distinct_roadside_silhouettes_per_section`, 8 != 10) is
  PRE-EXISTING in `chase_set.ROADSIDE_SITES`, proven by stashing this change.
  Looked at the frames in `shots/m8_valley/` (gitignored).
- Owner playtest still wanted: `python acaristan.py --dev-mission8-trap`
  (and `--dev-mission8`) with the eyes on the road's south run.

---

## Cast: Andrei M. (2026-11-13, uncommitted)

`figure_kit.SPECS["andrei_m"]` (glasses, moustache, crew neck, short
sleeves, satchel, stacked bracelets, sole) flowing through `cast3d.spec3d`
into the engine3d rig; no mission/save/sprite changes.
- figure_kit: moustache polygon, rectangular glasses branch, 2D left-wrist
  bracelets (two black bands + three silver studs). Moustache darkened to
  (26,20,18) and thickened to `moustache_h=0.022` so it survives the zoomed
  out line-up; bracelet band/stud to (20,20,24)/(210,214,222).
- cast3d: forwards `moustache`/`moustache_h` **and `bracelets`**, maps
  `neck="crew"` → `crew`.
- rig: glasses frames 0.011 m with a 0.044 bridge and raised brows when
  glasses are on, `moustache_h` support, crew collar + satchel shoulder bridge,
  matching back strap + buckle, thin temple arms, slim bare arms/forearms/hands
  for short sleeves. Moustache box widened to 0.090 and pushed to z=0.1245
  (below the nose, clear of the glasses frames at z=0.1248). The stacked
  bracelets are built in `P["farm"]` (two bands at y -0.205/-0.242 + studs).
  **KNOWN**: `P["farm"]` is shared by both forearms (SLOTS 6 and 12), so the
  3D stack shows on BOTH wrists while the 2D sheet draws it on the left only
  - visible in `cast_compare.png`. Left-wrist-only in 3D needs a new
  left-only slot (slot 11 is the free right `uarm_acc` slot).
- `tools/cast_sheet.py` adds him; lineup centred (step 0.96, cam -11.4/fov 48),
  label fonts 22/9 so nine names/roles don't collide, portrait slug sanitised;
  new `tools/view_cast3d.py` turntable viewer.
- Generated `outputs/cast/{andrei_m,cast_lineup,cast_compare}.png` inspected:
  moustache and both wrist stacks read on the 3D model.
  Gates: unittest `test_faces3d` 6 OK, compileall OK, AE NORMALIZE OK,
  **SMOKE TEST: OK**.

---

## M8 chase: gunship arrival runs through CutscenePlayer (2026-11-13, uncommitted)

Owner's plan: kill the inline cutscene inside `chase3d.py` and run the gunship
arrival as a real M8 film on the house player (film key `"heli"`).
- New set `epilogue3d.command_room()`/`CMD_ROOM`/`command_lights()` (Guard
  situation room, Route 12 map, radio rack, field radio + desk mic).
- Four shots in `cutscenes/m8films.py`: `heli_road`, `heli_retardovici`,
  `heli_flyby`, `heli_lockon` (spline-derivative flyby, full-frame cut_to_play
  into the live camera). Registered in `meta.M8_SCENES`, `FILM_TIMELINES["heli"]`,
  `m8_audio.FILM` (+ `f_heli` bed), timeline `src/game/content/timelines/m8.heli.timeline.json`,
  fallback `meta.HELI_SHOTS`.
- `chase3d`: `_start_heli_cutscene()` now pauses and sets
  `STATE.request_m8_cutscene="heli"`; `on_heli_cutscene_done()` advances 55 m,
  spawns the orbit gunship. `flow.on_cutscene_done("heli")` hands back to it.
  Deleted `_cutscene_update`/`_draw_cutscene`/`_handset`/old finish.
- Fixed two real defects found on the path: (1) a stale duplicate
  `_heli_shoot` (spawn-dict copy) + old `_heli_update` shadowed the salvo-QTE /
  `_heli_crash_update` implementation and KeyError'd on `rocket_fired`; removed
  the 4.5 KB dead block. (2) `solve_arm_safe` cannot reach desk height
  (~0.25 m short), so Retardovici is seated (`_w.sit_pose`, seat 0.46) with
  authored upper-body keys.
- Owner revision applied: dark slate war room (plank floor, plain-color walls),
  cool steel-blue rim light instead of the red flood; shot 2 back to
  `epi_president` framing (~5.4 m, fov 38) for head+desk+map+rack; shot 3
  rear-quarter rig camera aimed forward; shot 4 adds `draw_vignette` so it
  matches the play frame it cuts into. `f_tv` bed kept for the room tone.
- Difficulty rebalanced: `HELI_HP=280`, `HELI_GUNNER_HP=18`, heli bursts
  7/8 rounds at 30% hit / 1.6 dmg with 2.3 s (1.95 s phase-2) gaps, 2 escorts
  in `SPAWNS[3]`, `ROCKET_DMG=40`, two locks (72% / 32%, 10 s apart).
- Interactive toolbox repair: `S.toolbox()`/`TOOLBOX_AT` on the trailer bed;
  look at it (ray vs 0.58 m sphere) + `E` → 2.4 s repair, side camera, Biribel
  on the right footboard with a wrench, spark ticks, +45 hull, 35% incoming
  damage; 2 charges per run, topped up at every checkpoint; Bodi barks when
  hull < 45 and turns to watch. Staging was moved off the original
  `(0.72,0.58,-0.15)` position because the rear wheel filled the frame.
- QTE retuned for fairness: `HELI_LOCK_S=1.5`, `ROCKET_HP=2`, `ROCKET_HIT_R=0.65`,
  `ROCKET_DMG=40`, `DODGE_S=1.7`; one missile per lock; closing speed 16 m/s;
  `rk["dodged"]` latches before impact and a dodged missile only detonates
  behind the rig; SPACE steers away from the missile's `target_lane`; HUD shows
  DODGED! / `SHOOT MISSILE (2/2)`. Map lowered 0.22 m so the red rail line
  clears the top letterbox bar.
- Verified: compileall OK, **SMOKE TEST: OK** (one transient network-soak socket
  failure on the first run, green on re-run; slice plays all 4 heli shots and
  asserts orbit resume). Software probe: rocket dodged at the earliest legal
  moment survives to its +24 m detonation with no hull loss from it; 2 LMG hits
  shoot it down; HUD prompt frames inspected. Flyby keeps tractor+Biribel framed
  but the chopper exits the top of frame at the 2850 ms flyover (design call —
  sound+shake carry it; playtest). Not played in the live app.

## M8 tractor chase: solid traffic, off-camera spawns, wreck avoidance (2026-11-11, uncommitted)

Owner: "the cars just go through the ones that are destroyed", plus no pop-in and
swerve around wrecks. All in `chase3d.py` (+ footprint constants in `chase_set.py`);
no engine/renderer/model/other-mission edits. Hit spheres, HP, fail rules, `SPAWNS`
timing, Bodi barks and the crossing blocker are untouched.
- Collision: `_resolve_contacts` = circle push-out in x/z (car/car, car/tractor+trailer,
  car/static-wreck, blocker as static), partial speed exchange (`CRASH_TRANSFER=0.6`),
  wrecks a live car on closing > `CRASH_SPEED=7` m/s (`_crash_hit` -> pile-ups), hull
  nick `TRACTOR_HIT=4` once per contact (rising-edge `_trac`). Radii `CAR_R=1.35`,
  `TRUCK_R=1.70`, `TRACTOR_R=TRAILER_R=1.60`, `WRECK_R=1.50` (from body/tyre spans).
- No pop-in: jeep/gun_truck spawn at `eye[2]-SPAWN_BACK` (350 m, past the 330 m draw
  cull) via `camera()` and drive in; gun_truck enters from +34 m side. Despawn widened
  to `DESPAWN_BACK=410` so an entering car isn't culled the frame it spawns (the old
  tz-160 filter deleted far spawns immediately -> smoke "chasers must spawn" failed).
- Avoidance: `_avoid_lat` looks 80 m ahead in-lane; swerves only if
  `gap >= speed*REACT_S + speed*(2r/LAT_MAX) + r` (reaction + one-car-width shift),
  else keeps the lane and takes the hit. Deterministic, no RNG. `CLOSE_MAX=16`,
  `LAT_MAX=5` keep entering cars on the road through curves (drifted +5 m at 30/4).
- Gates: 11 new `test_m8_chase_traffic` + 8 gun + 9 scenery = 28 OK; compileall OK;
  **SMOKE TEST: OK**. Live probe `tools/_m8_traffic_loop.py --software` (reel + per-car
  log in `outputs/m8_traffic/`): cars hold the lane (off <=2.1 m farm track), swerve
  around Route 12 wrecks, one pile-up wreck where spacing < reaction distance.
- Tradeoff for owner: a far spawn means ~19 s lead-in from spawn trigger to firing
  range (closure 16 m/s from 350 m). Tune `SPAWN_BACK`/`CLOSE_MAX` if the first wave
  feels slow. Owner playtest needed: `python acaristan.py --dev-mission8-chase`.

## M8 tractor chase: ADS added (2026-11-11, uncommitted)

Owner: "add ADS in the tractor chase in M8". RMB now holds aim on the pintle
LMG (`chase3d`): `aiming`/`ads` blend (11 up / 7 down), camera leaves the
over-shoulder hip view for a gunner's-eye view down the gun at its front post
(`ADS_EYE`/`ADS_POST`, gun-space), FOV 60->45, mouse gain -30%, bloom cone -55%,
muzzle climb -45%, shake damped. The hip orange reticle yields to the real
front post above ads 0.55; reload/dying/capture/ending force the sight down and
it returns if RMB is still held. HUD hint "LMB FIRE RMB AIM R BELT".
- The mesh's AA ring stalks block a blade-to-blade sight line, so ADS aims
  eye->front-post (see cerebrum). Sight line ~14 deg below gun axis is intentional.
- Gates: 6 new `ChaseAdsTests` + 8 chase-gun + 3 scenery = 17 OK; compileall OK;
  **SMOKE TEST: OK**. Live app loop (`tools/_m8_ads_loop.py`, scripted RMB/LMB)
  raises/lowers the sight on BOTH backends without skipping the chase; frames in
  `outputs/m8_ads_loop/`, sweep/hit-rate in `outputs/m8_ads_verify/`
  (24-round bursts: hip 0/6 trials hit, aimed 6/6).
- Fixed a pre-existing stale mock in `test_m8_chase_scenery` (`lambda *args` vs
  the `burn=` kwarg the scenery pass added); unrelated to ADS but blocked the gate.
- Owner playtest still needed: `python acaristan.py --dev-mission8-chase`, hold RMB.

## M8 chase: first shot skipped the mission — FIXED (2026-11-10, uncommitted)

Owner: "when i shoot on M8 tractor chase it just boots me STRAIGHT to the end of the mission".
Root cause: both muzzle-flash draw sites in `chase3d` called `cutscenes.m6fx3d.muzzle_flash`,
a helper that exists in neither m6fx3d nor its m5fx3d fallback; the first trigger pull raised
AttributeError inside `ChaseScene.draw`, and `missions/m8/draw.py` force-finishes the scene on
any draw fault -> `on_chase_done` -> epilogue film -> mission complete. Fix: both sites use the
proven `_fx.glow` muzzle idiom (as m1/draw3d). Regression
`test_m8_chase_gun.py::test_a_shot_renders_instead_of_faulting_the_scene` renders one frame with
a fresh shot + enemy flash. Gates: 8 chase-gun tests OK, compileall OK, **SMOKE TEST: OK**;
software probes drew first shot / enemy flash / reload / wreck / crossing / ending cleanly, and
the real app loop (`--dev-mission8-chase`, scripted 180-frame burst) stayed in `chase` with
`outro=False`. Owner playtest of a burst in the chase still needed.

## M8 tractor chase: the LMG went through Biribel — FIXED (2026-11-10, uncommitted)

Owner: "the gun goes through you in the Tractor chase scene". Root cause was geometric and
complete: the imported LMG's shoulder stock runs 24 cm behind the grip, mode `aim` anchors the
butt INSIDE the shoulder pocket, so ~24 stock verts sat in Biribel's chest at every yaw/pitch
(probe: 6.3-7.6 cm deep, 131k piercing vert-states over the route sweep). No stance can clear it
(sweeps over twist/spine/blade/pocket all failed: the grip must stay in reach of both hands).
- Fix = a pintle configuration, like a real mounted gun (M240D-style):
  `chase_set.STOCK_CUT_Z = -0.10` cuts the stock faces from the drawn split parts
  (`_lmg_split`); the receiver's own rear plate (raw z -0.094) survives and closes the gun, so no
  cap mesh was added; `GRIPS["lmg"]` now carries `pocket=(0.08,0,0)` (butt anchor out on the
  shoulder crest) and `fore/guard` moved to the feed tray left of the receiver.
  Both backends draw Biribel `rifle_on=False`, so the rig's uncut rifle copy is never visible.
- Second pierce found during verification: the reload `rack`/`rack_up` keys (spine 24/18,
  twist -14/-10) leaned the chest 3.9 cm into the FIXED pintle gun in the el 1.7-2.4 s band.
  Re-tuned to spine 6/4, twist -6/-4 (arm reaches the tray; the read is unchanged).
- `hold.py`: `hold_cached` now keys on `_grip_sig(weapon)` too, so tuning GRIPS in-process can't
  serve poses solved against the old grip points.
- Gates: `tests/unit/test_m8_chase_gun.py` (7 tests: stock cut, closed cap, aim envelope,
  reload blend, route/yaw sweep, hand-on-grip, stance keys) + chase_scenery + test_hold pass;
  compileall OK; **SMOKE TEST: OK** after reconciling the STALE M8 oracle (below).
- Owner playtest: `python acaristan.py` -> dev jump `m8*` chase (or play to it). Visual sign-off
  still needed: this agent could not view images this session (same as 2026-11-09).

## M8 smoke oracle reconciled to shipped gameplay (2026-11-10, uncommitted)

The smoke M8 vertical slice predated TWO shipped changes and died inside the kill beat, never
reaching the chase assertions (matches the 2026-11-09 note "do not change the kill choreography
just to satisfy this stale test; reconcile its expectations separately" - done):
- kill beat: rewritten to the shipped kill3d (one wounding hit; `DECISION_AT` window; second hit
  = "shot" or ENTER = "lowered"; `HANDS_AT` caption; witness `cine()` road/still close-out).
  Old `REACT_S`/`SLOWMO_S`/`PROFILE_S`/`ROAD_S`/`LOWERED_DIE_S`/`said_hands` no longer exist.
- chase beat: the 2026-11-09 armour pass made tyres take `TYRE_HP` hits and the blocker driver
  `DRIVER_HP`, so the one-hit "clear"-loop oracle no longer wrecked anything. Now bursts a tyre
  to zero via `TYRE_HP` and kills the blocker with `DRIVER_HP` hits.
- `M6 train draw failed (RuntimeError: probe draw failure)` printed mid-run is EXPECTED: the
  redeploy test deliberately raises inside a draw ("failing the run, not the mission"), and the
  check still passes. The printed pwsh exit code 1 on SMOKE TEST: OK is harness stderr noise.

## M8 tractor chase: LMG, wheels, armoured cars, set pieces (2026-11-09, uncommitted)

Owner still saw a repeating background, static wheels, and wanted an LMG instead of the shotgun.
- LMG: `assets/3D/light_machine_gun.glb` -> `tools/ae_import_lmg.py` -> `src/game/content/meshes/lmg.mesh.json`
  (bipod dropped), grips `engine3d.hold` GRIPS["lmg"], `m6world3d.hum(flags=("lmg",))`
  (falls back to the shotgun if the mesh is missing). `chase3d`: 100-round belt, 4.2 s reload,
  ~700 rpm, bloom cone + muzzle climb, `m8_audio.lmg_shot` (pool `m8_lmg`).
- Cars buffed: hp per part (`HP`, `TYRE_HP`, `DRIVER_HP`, `GUNNER_HP`); the driver sits behind a
  windscreen plate (`chase_set._armour`), the gun truck has steel bed walls; denser `SPAWNS`.
- Wheels: `chase_set.put_wheeled` splits wheel components off the vehicle meshes and spins them
  by an odometer (tractor, trailer with new round tyres, jeep, gun truck; wrecks lock).
- Background: `chase_set.ZONES` near-road set pieces (hamlet, woods, pond, kolkhoz, petrol station,
  cutting + overpass, bus stop + panel blocks, rail siding, border fence); power line skips the
  woods/cutting and changes sides at the ditch. Own RNG stream, wreck layout unchanged.
  The 2026-11-10 stock cut above alters only the drawn gun parts; the ZONES/wrecks are untouched.

## M8 tractor chase scenery variety (2026-11-09, uncommitted, superseded above)

Owner reports the tractor chase background repeats. `src/missions/m8/revenge/chase_set.py`
reused five field patterns across the whole route, farmsteads at every stop and
identical church villages five times; most landmarks were distant from the
rearward-facing trailer view. Now the four sections have two distinct nearby
landmarks each (farm gate/orchard, hay yard/pump house, Guard post/memorial,
freight depot/watchtower), different field palettes and a darker ditch track.
Farms end before Route 12; villages appear only twice. Eight final software
section captures in `outputs/m8_chase_unique/` rendered; changed scene pixels
range 6.6-25.8% versus the prior captures, but image viewing is unavailable to
this agent, so owner visual sign-off is still needed. Three focused unit tests
pass, compileall OK, changed Python LF/UTF-8. **Full smoke fails at a pre-existing
M8 kill-scene test drift** (`tools/smoke_test.py` expects `kill3d.REACT_S`, but
current kill3d removed it); it never reaches the tractor assertions. All earlier
smoke checks pass. Do not change the kill choreography just to satisfy this stale
test; reconcile its expectations separately. No unrelated edits rolled back.

## Balaceanu VO caption mismatch fix (2026-11-08, uncommitted)

Owner: "the TTS doesn't match what Balaceanu is saying in the narration box".
Root cause: the 13 TTS takes in `assets/voice/Balaceanu/` were recorded OUT of
spreadsheet order, so `voice.py`'s length-based `_align()` heuristic shifted most
lines. The broadcast mast beat (VO_009 "The prisoner is contained...") was playing
the take that actually says VO_011 "They'll see your face, Biribel...". Verified by
transcribing every take (faster-whisper base.en, scratch since removed; transcripts
kept at `assets/voice/Balaceanu/_transcripts.json`). Fix = the system's intended
mechanism: renamed each take's .ogg+.wav to its canonical `VO_xxx` (explicit names
always win, bypassing the heuristic). 12 unique lines named; VO_014 shares VO_006's
text/take; the duplicate VO_002 retake (old `7_04PM`) moved to `_retakes/`. VO_007
"Cut the feed!" gained audio it never had. `balaceanu_matches.txt` rewritten with
the verified mapping (LF/UTF-8). No dialogue/manifest text edited (canon: never edit
a recorded line). All 13 captions resolve to the correct file at runtime; VO_009
decodes 12.19s. compileall OK, **SMOKE TEST: OK**. Pre-existing unrelated reds:
`ae_normalize` crashes on root `_tmp_assets.py` (syntax error, not ours); ae_ci reds.
Owner playtest: `python acaristan.py --dev-mission3-broadcast-transition`.

## M3 Broadcast bridge dead-space pass (2026-11-08, uncommitted)

Owner: "a lot of dead space in the background and missing floors". All fixes in
`src/cutscenes/m3broadcast3d.py` baked sets (+ road/exterior camera tilt, outdoor
fog matched to sky); no timeline, dialogue, blocking or map changes. Dock: full
side returns + ceiling + wall ribs/practicals, widened and dressed back wall
(bulkhead lamp + conduit + pipes) so the open shutter frames a lit surface, not
void. Road: wet verge ground plane beyond the barriers, scrolling side blocks at
the lamps' 16 m/s, a second fogged skyline row, brighter dash; camera tilts down.
Exterior: lit entrance apron + bollard walkway, perimeter wall with gate gap,
stepped left/right wings, distant skyline, roof antenna; camera target lowered so
the facade base meets visible ground. Corridor: ceiling slab on the beam tops.
A back-wall glow sprite bled through the closed shutter (slat gaps) and was
removed — the emissive lamp box is geometry-occluded and clean. 5 broadcast unit
tests pass (seek determinism + corridor framing intact), compileall OK, standalone
**SMOKE TEST: OK**, 40 frames/backend in `shots/m3_broadcast3d/{gl,software}/`.
This session CAN view images: contact sheets + key frames reviewed on both
backends, no voids/floats/bleed. Changed file LF/UTF-8/no-BOM. Owner playtest:
`python acaristan.py --dev-mission3-broadcast-transition` jumps straight to the
five-shot bridge. Full ae_ci not run (known pre-existing reds).

## Office and medical GLB scenery (2026-11-08, uncommitted)

User requested six unused assets integrated: Zarya/tall Soviet PCs, CRT/LCD,
medkit and pill bottle. New `tools/ae_import_workstation_props.py` bakes all
six into `src/game/content/meshes/`; node transforms, embedded texture colours,
metre scale, deterministic face budgets, transparent glare removal and tagged
screen faces. `game/scenery3d.py` caches shared props/workstations and live
screen-only meshes, with procedural fallbacks at scene owners.
M2 upload/evidence PCs; M3 Comms/Archives/Broadcast desks, guard consoles and
cell monitor; M5 HQ signup/armory monitors + medical bench; M7 shared farmhouse
porch chest; shared M1 pickup helper upgrades existing bandage pickups across
missions. No maps, collision, interaction state, dialogue or health rules changed.
21 targeted tests pass (six new scenery tests), compileall/diff check and scoped
UTF-8/LF pass. GL/software M3 and GL M5 captures plus M2 upload/M7 porch captures
in `shots/scenery_props/`. Image input is unavailable to this model: appearance
needs owner review. Full normalizer still stops at existing scratch syntax line
13. Standalone **SMOKE TEST: OK**. Full engine gate: compileall, API, import,
text/data/timeline, frame budgets, replay-check, flash, software determinism
and holds pass; known baseline failures include M4 entity attributes, W1/D6
ratchets, M5 audio channel mocks and existing M7 motorcycle raw image load,
stale bake/replay/loop/mission0 drift. **AE CI: FAIL** (343/393 golden
mismatches in the dirty tree; scenery changes also intentionally change images,
no golden baselines regenerated). Both standalone and CI smoke pass.

## M3 Kill Order sniper sightline (2026-11-07, uncommitted)

Owner reports a targeting line through the cover block and an invisible
sniper. `m3ko3d._marksman` drew both a persistent beam and firing tracer
with a painter-layered 3D line, which can overpaint the slab. The guard's
projection was entirely behind the foreground pillar (render-difference
probe: zero pixels). Removed BOTH lines, kept the brief muzzle + stone hits,
shifted guard right onto a clear mezzanine firing bay, opened its rail and
added a local practical. Guard now contributes ~2,000 software / 1,724 GL
contrast pixels around the upper body between flashes. New regression asserts
no targeting line at any beat and visible silhouette with the guard removed
from a comparison frame. 14 KO/hold unit tests, compileall and both backend
40-frame captures pass. Final standalone **SMOKE TEST: OK** after the
light was scoped to the PA shot; owner visual sign-off pending.

## M3 Kill Order staging follow-up (2026-11-07, uncommitted)

Owner still saw actors stare at the door and Balaceanu's PA shot read badly.
Root cause: the stair shot allowed advance at 2200 ms but Biribel crossed
at 5300 ms; the PA lens initially missed the entrance and the lobby shot
had no connected threshold. Now stair minimum is 5400 ms in the timeline
and fallback meta; the lens follows both through the open portal and they
scan separate flanks on hold. PA shot has a cutaway stair throat, open portal,
separate timed entrance-to-cover routes, a pan from entry to speaker/overwatch,
and security-bay alarm dressing. Recorded lines unchanged. Eight KO tests +
five hold tests pass, timeline round-trip and compileall pass; 40 final GL
captures and 40 earlier software captures generated. Final standalone
**SMOKE TEST: OK**. Visual sign-off still needs owner; this model cannot
inspect the image captures.

## M3 door orientation (2026-11-07, uncommitted)

Fixed `src/missions/m3/draw3d.py`: north-only axis inference rotated lower
leaves of vertical double doors by 90 degrees (Comms, Archives, Kill Order).
Now follows contiguous D runs to concrete jambs on both axes, preserving the
cell armory's two-column wall. No map, collision or gameplay changes.
Four regressions in `tests/unit/test_m3_door_orientation.py` pass, covering
all five maps, both sliding axes and cache rebinding; compileall and scoped
LF/UTF-8/diff checks pass. **SMOKE TEST: OK**. Whole normalizer still crashes on
an existing line-13 scratch syntax error; ae_ci refuses another live lock
(pid 39632); did not steal it. Other working-tree changes left untouched.

## M3 Kill Order 3D bridge (2026-11-07, uncommitted)

Approved plan implemented in `src/cutscenes/m3ko3d.py`, routed by m3ko registry
wrappers with illustrated disabled/error fallback. Four shots: one-way breach
at 1150 ms, tread-supported descent (Volkov leads, separate lanes), pillar
cover/mezzanine marksman (actual muzzle ray terminates on pillar), empty dock
preview with existing m3_van asset. Shared textured materials, PS2 grade and
practical lighting. No mission state mutation, new dialogue or map changes.
Silent charge auto-advances; all lenses hard-cut. Meta/timeline agree.
24 KO/M3/hold regressions pass; compileall OK; 36 GL/software captures in
`shots/m3_ko3d/`. Stair regression checks actual sole geometry against steps,
not just root height; renderer tests check deterministic seeking and framing.
Standalone **SMOKE TEST: OK**. Full CI ran: FAIL (M5 audio unit errors,
M7 raw asset load, boundary/component/render-queue ratchets, stale bake,
golden/replay/loop/mission0 drift); no KO unit failures. Timeline round-trip,
API, holds and software determinism pass. No unrelated rebaselines made.
Repo normalizer still fails on existing scratch syntax; KO files LF/UTF-8.
Visual sign-off pending (model cannot view captures). Playtest:
`python acaristan.py --dev-mission3-kill-order`.
Archives stays reverted; earlier Comms and Molotov changes preserved.

Owner playtest follow-up: stair portal had a solid rear wall and routes ended
short. Replaced with genuine open aperture, displaced door leaf, extended
landing/corridor and both walks through z=5.9 to z>7. PA shot now has approach
then kneel, separated cover positions, side-biased camera, visible loudspeaker,
clerk counters/wall bays and distinct exit light. Removed searching beam that
could pass through cover. 25 targeted regressions pass; compileall and 36
captures/backend OK. New tests forbid wall sealing the exit and assert actual
passage/approach. Follow-up **SMOKE TEST: OK**; visual sign-off remains pending.

## M3 Comms visual upgrade (2026-11-07, uncommitted)

User says m3-comms graphics fall short of other 3D films. Service set now
uses shared ps2mat textured concrete/steel instead of plain large faces.
Added baked wall ribs, piping, recessed vents, ceiling structure, drainage,
rack modules/meters/handles/wiring, relay keys/paper and a physical warm lamp.
Lower ambient, stronger source-based warm/cool lights, small depth-masked
practical halos; radio insert has corner guards, buttons and a top control.
Animation, cast wardrobe, timelines and reverted Archives remain unchanged.
18 staging/hold/Molotov tests pass; compileall OK; 44 captures/backend succeed.
New regression asserts baked detail, textured surfaces and emissive sources.
Changed files LF/UTF-8 clean. **SMOKE TEST: OK**. Full CI still locked by another
run; repo normalization still crashes on existing scratch syntax error.
Visual sign-off still needs owner: this model cannot inspect image inputs.

## M3 Archives conversion reverted (2026-11-07)

User requested revert of the latest Comms -> Archives 3D conversion. Restored
original live-map cinematic and pacing; removed new film/test and Archives
preview option. Earlier service/radio staging and ghost Molotov fix preserved.
Old preview captures are historical only. Kill Order/Broadcast not converted.

## M3 ghost Molotov fix (2026-11-07, uncommitted)

Shared `entities.weapons.handle_throw_bottle` now rejects MISSION3 before
inventory, aim, audio or projectile side effects. M3 has no flight update but
its 3D FX renders the shared projectile list; firearm-equipped players with
nonzero bottle inventory could create a stuck ghost. Both RMB and G use this
handler. Two regressions cover all M3 weapons and preserve M1/M2/M6 throws;
unit tests + compileall pass; standalone **SMOKE TEST: OK**.

## M3 in-mission 3D staging, first bridge (2026-11-07, uncommitted)

User requested a proper 3D staging pass on the between-stage films, not the
intro/outro. First slice is **cell block -> Comms only**. New
`src/cutscenes/m3staging.py` draws a shared concrete service/relay set with
four lenses: exit wide, radio-handoff two-shot, power-on insert, Comms dolly.
Prisoner wardrobe, K-9 right-hand carry, left-hand radio IK, planted-foot
walks, deterministic seek/holds. `m3ops.py` wraps the four existing registry
IDs; original 2D takes survive under `ACARISTAN_CUTSCENE3D=0` / render failure.
Dialogue/takes and mission hand-off unchanged. Timeline + meta fallback have
hard cuts and auto-advance/quiet UI on the two silent action shots.

Follow-up playtest fix: one-handed rifle is now lowered/outboard with a
20 cm minimum radio-hand/gun-AABB gap in tests. Volkov's toss/retract stays
on his right side; recovery keeps the held arm and blends his turn away.
The old target path could penetrate the chest even with safe IK (solver
returns least-bad pose for impossible targets). This M3 prop is a radio;
user also called it a Molotov, so a separate Molotov scene remains unconfirmed.

9 staging + 5 hold regressions pass (`python -m unittest
tests.unit.test_m3_staging tests.unit.test_hold -v`), compileall OK;
24 fresh frames/backend captured by
`python tools/m3_staging_preview.py --backend gl|software` into
`shots/m3_staging/{gl,software}/`. Fresh engine3d parity OK (worst 3.26%). Changed
files normalize cleanly; whole-repo normalizer crashes on the pre-existing
untracked `_tmp_assets.py:13`. Follow-up standalone smoke: **SMOKE TEST: OK**.
Follow-up ae_ci refused: another run holds its lock; not stolen.
Prior full ae_ci: **FAIL**, broad failures (M4 entity attributes,
shared->mission ratchet, M5 audio mock/channel IDs, M7 raw asset load,
golden/replay/bake/mission0 drift); do not rebaseline those in this task.

Radio-handoff follow-up (user disliked the take): replaced the 840 ms float
with a 360 ms ballistic toss, visible wind-up, delayed receiving reach and
220 ms catch absorption. Locked two-shot (no competing dolly), with projection
regressions keeping the radio body inside frame and >18 internal pixels tall.
15 staging/hold tests pass; compileall OK; standalone **SMOKE TEST: OK**;
44 fresh frames per backend captured.
Recorded dialogue, timeline and unrelated M6 edits unchanged. Full ae_ci still
refused its live lock; repository normalizer still hits the existing scratch
syntax error. Changed Python files verified LF/UTF-8 without BOM.

**Needs visual playtest:** this agent cannot view image inputs. Jump directly
with `python acaristan.py --dev-mission3-comms`. Archives, Kill Order and
Broadcast bridges have NOT been converted. Pre-existing M6 working-tree
edits were left alone.

---

## M7 goat-escape bridge (2026-10-31, branch `walk/look-pass`, uncommitted)

Chores-complete film, so Bodi's "one of them got out" is watched, not told:
`src/cutscenes/m7goat.py` (5 shots: pen / slip / orchard / two-shot / Bodi) +
`src/game/content/timelines/m7.goat.escape.timeline.json`. `farmyard._chores_complete()`
requests it once from the trough and generator handlers; `meta.MID_TIMELINES`
(`MID_GOAT_ESCAPE`) registers it, `flow.on_cutscene_done` resumes chores without
moving the ladder, and `flow.film_music` keeps the farm cue. VO_345-347 moved
from `GoatRescue.__init__` into the film; the cream goat is hidden from the pen
after it. Gates: compileall OK, smoke OK (new `m7_goat_escape`), M7 unit 29 OK,
AE TIMELINE/VALIDATE OK. Not hand-played yet.

---

## M7 playtest fixes (2026-10-28, branch `m7/fallow-ground`, uncommitted)

Owner playtest list fixed in place (details: Obsidian `Sessions/2026-10-28 Call of Acaristan - M7 playtest fixes.md`):
- Shots aim along the crosshair before the kick; 8 lanes incl. centre; hard FX (`raid3d.py`).
- Allies carry a rifle (`m6world3d.hum` "ally" branch); Alex picks firing spots, 13 m leash (`raid_brain.py`).
- Guards fall, dogs roll and stay (`raid_world.dog_fall`).
- Raid ground, sky and hills cleaned (`m7world3d.py`).
- Bridge: stage `raidin` and film `m7.raidin` between prep and raid.

Gates: smoke OK, compileall OK, unit 485 OK (full suite before the copy, M7 28 after), boundary OK. `ae_ci` was 20/26 before the copy; not re-run. Still red: API snapshot, asset bake, replay, loop parity, mission0 diff (uncommitted engine/asset/baseline edits). `m7runner.py` now copies the shotgun helpers in instead of importing `engine.anim.figure_kit`.
Open: hand playtest; truck gunner hidden by his own truck box.

## Mission 7 "Fallow Ground" (2026-10-28, branch `m7/fallow-ground`, uncommitted)

All seven beats are implemented and headless-tested: 3D drop-off film, top-down chores and
prep, 2D runner film, playable 3D raid (`src/missions/m7/raid3d.py` + `raid_*`), 3D burning-farm
finale, radio choice writing `STATE.m8_route`, outro. Details: `docs/worklog.md` (2026-10-28) and
the implementation notes at the end of `docs/MISSION7_PLOT.md`.

Gates green: compileall, smoke (`mission7_vertical_slice`), unit 479, ae_validate/text/hold/
mission0, boundaries (W1 baseline now 51). `ae_ci` red only on bake/replay/loop: replay hashes
all of `STATE`, so the new M7 fields shift every segment, and m1/m2 also differ in camera/player
from the uncommitted M1 work, so baselines were NOT re-recorded.

Next: playtest the raid by hand (dev jumps `m7*`); record Bodi/Alex takes (`VO_219`-`VO_227`);
persist `m7_preps`/raid checkpoint; settle the doc conflicts ("Tomorrow night" vs M8 "at dawn").

---

## Investigating (2026-10-27 M1 dropoff cutscene "replays" report)

User reports the m1.dropoff cut (street drop-off after the briefing) replays
("same 2-3 shots repeating"; user says the van truly re-pulls-out). Could NOT
reproduce in any deterministic config: real `_legacy_frame` loop headless with
scripted SPACE input (idle / spaced / 30 Hz mash) plays the cut exactly once;
shot clocks continuous (offsets 0/+4300/+6600 applied in engine.py line 23);
goldens `gp.m1.dropoff.*` match. `finish_briefing` is the only `start_cutscene`
caller; update+handle_event are gated by `not gsm.transitioning` (app.py
~4164/~4203) so it cannot double-fire. Diagnostics shipped: `ACA_CUTSCENE_TRACE=1`
appends `start_cutscene`/`player_state` (player replacement = restart, shot idx,
start_time) lines to `build/cutscene_trace.log` (app.py `_cut_trace`/`_cut_watch`;
NOT inside CutscenePlayer/_CutsceneState/finish_briefing — the smoke test execs
those in bare namespaces). Also real, non-replay issues in the take itself:
shots 2-3 share one static hold cam (goldens 01/02 near-identical stills),
SPACE blocked by min_ms holds (4300/2300/2500), painter clamps at 9100 ms.
Cause confirmed by frames (not a double start): shots 2 and 3 painted the same
static wide street frame (golden `gp.m1.dropoff.01.t50` vs `02.t50`), so the cut
read as one shot repeating. Working-tree fix (uncommitted): three scales, beat 1
wide pan, beat 2 `m1_dropoff_follow` 1.6x on Biribel, beat 3 `m1_dropoff_entry`
2.4x at the side door (draw.py `_draw_dropoff_zoom`). Smoke OK; dropoff goldens
recaptured. Open: user confirms the cut reads right in play.

## Done (2026-10-27 M1 Volkov art, uncommitted)

User: "in M1, Volkov is drawn uglily". `_draw_volkov_topdown` (missions/m1/draw.py)
hand-rolled him like Enemy.draw (rotated coat polygon + hair circle + cig splinter).
Now it blits the cached figure_kit cast body — `_volkov_body`, the M4/M5/M6 recipe
(3x supersample, smoothscale 84x84, artpack.pose per facing, scale 0.232 on 64 px
tiles), feet on his post/run line over the guard shadow, walk bob on the body only.
`_volkov_turn` + `STATE.volkov_draw_angle` deleted, plus the stale smoke reset line.
Frames: shots/m1_volkov/. Gates: compileall OK, smoke OK; no golden covers tile 15,27.

## Done (2026-10-27 respawn fix, uncommitted)

M1 "invisible player after respawn" fixed: die -> Retry left `death_anim_phase=2`
+ stale tilt armed because `m1.start_mission()` hand-rolls its reset (no
`STATE.reset()`). `death_anim.reset_stale_visuals()` added and called from
`m1.start_mission()` (`entities/death_anim.py`, `missions/m1/main.py`).
Gates: compileall OK, smoke OK, headless die->retry->move probe OK (probe
script deleted after use). Bug logged as bug-106 in `.wolf/buglog.json`.

## Done (2026-10-27 M1 rework complete on this branch)

Branch `cutscene-holds`, merge `ef9302b`: WP8+WP9a+WP9b merged in from `m1/rework`
(its tip `1c9e8ac` is now fully contained here; that worktree has no further M1 work).
The M1 rework plan (`docs/MISSION1_REWORK_PLAN.md`) is executed WP0-WP9.

- What landed here with this merge: WP8 hard lights (`m1.hard_lights` LIGHTING pass,
  halos, flood/bay cones; soft lamp pushes removed from `LightBuffer`, grade kept),
  ambience bands (street rain+wind vs inside rain_inside/console hum/stockroom drips),
  `m1_audio` music hook (silent without `assets/music/m1_{infiltrate,combat}.ogg`);
  WP9a seeded rain + 13 m1 goldens; WP9b replay/loop/bake/D6 baselines + docs.
- Gates on the merge: compileall OK, smoke OK (3 new WP8 checks green),
  ae_level_check OK, golden 390/390, replay m1 OK, loop m1 OK, bake m1 OK.
- ae_ci reds are ALL pre-existing — proven by rerunning them at pre-merge `63839e2`
  (detached temp worktree) and at `m1/rework` tip: unit `test_gl_composite` 3x
  `GLRenderer.stats`, api snapshot +210, boundary lint 18, bake m2/m3 stale,
  replay m2-m5 divergence at t=1s, loop parity 1/7 (m1 is the 1), mission0
  engine-tree hash (91 files, fails on the branch too).
- Earlier on this branch: letterboxed presentation (`63839e2`, 1000x700 canvas +
  `present()`), MP version-skew refusal (`a5e5c98`), launcher/updater (`d1a833e`),
  M6 train viewmodel tint (`39b168d`), M6 top-down art pass (uncommitted work
  committed before the WP0-WP7 merge).

## Next

1. User plays the M1 flow once here (`python acaristan.py` or `--jump m1`; F9 exfil)
   and decides the merge to main. Nothing is pushed anywhere.
2. Optional M1 polish (user calls, all listed in `docs/M1_REWORK_HANDOFF.md`):
   street patrol + shutter guards facing each other; suspicion meter visibility;
   Volkov escape figure; CIOCAN speaker color; Q-brick binding; `files_already`
   timing; stockroom outer walls; supply the two music files.
3. M6 leftovers (see 2026-10-25 worklog): noman identity pass; `_mat_fill` tex3d;
   user review of the M6 intro shots.

## Done (2026-10-27 overnight CI sweep, uncommitted)

All seven pre-existing ae_ci reds from the list below are green on this
branch, verified with a full `python tools/ae_ci.py` (26 gates) + smoke.

- **B-041** (real defect, `docs/engine/BUGS.md`): context-free `GLRenderer`
  test construction had no `stats` dict once `_composite` wrote light stats;
  `SoftwareRenderer.__init__` now owns the shared `stats` dict. 6/6 tests.
- **E4 boundary lint 0**: `engine.ai.__init__` re-exports the
  bt/cover/senses/squad public names (B-021 pattern); call sites re-pointed
  in `m6/yard_brain.py`, `m6/yard_hud.py`, `ui/arena_view.py`,
  `engine3d/gl.py` to 2-level facades.
- **Stale oracles re-baselined** (content drift, proven by scratch-set
  self-reproduction first): api snapshot 616 names; `baseline_v2` replay
  m2–m5 (5/5); `baseline_v6` loop (7/7); bake m2/m3 rebaked (only
  `.bakeinfo.json` moved, art byte-identical).
- **mission0 pin re-frozen** `356f0326…` (91 files) for the Oct 21
  ai/collision subsystems, the Oct 26 MP/HUD sweep and today's facade —
  justified in `docs/engine/reports/phase10.md` ("2026-10-27 addendum").
- Smoke MP flakes: one extra standalone run — `SMOKE TEST: OK` (twice total:
  inside the CI run and standalone; the MP flakes did not reproduce today).
- Rule recorded in BUGS.md: re-run the oracle gates in the same session as
  any engine/public-surface change; stale oracles read as pre-existing reds.

Old list (fixed 2026-10-27): unit `test_gl_composite` 3x `GLRenderer.stats`,
api snapshot +210, boundary lint 18, bake m2/m3 stale, replay m2-m5 divergence,
loop parity 1/7, mission0 engine-tree hash.

## Context

- Main checkout `E:/Code/Call of Acaristan/First try` = `cutscene-holds` (this file).
  `E:/Code/Call of Acaristan/m1-rework` = `m1/rework`, tip fully merged; its
  untracked shots/saves/handoff noise stays untracked.
- Files carry CRLF at HEAD (core.autocrlf); pre-existing.
- Gates: `python tools/smoke_test.py` -> `SMOKE TEST: OK`; `python -m compileall -q src`;
  `python tools/ae_golden.py verify`; `python tools/ae_replay.py check --only m1`.

References: `.wolf/cerebrum.md`, `.wolf/anatomy.md`, `.wolf/buglog.json`.
