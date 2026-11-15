---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1000
---
# STATUS — first-try

> Read this FIRST when resuming. Last updated: 2026-11-15

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
