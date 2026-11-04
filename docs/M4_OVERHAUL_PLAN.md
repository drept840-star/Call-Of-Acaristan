# Mission 4 overhaul plan - "The Aftermath" in 2.5D

Status: design agreed 2026-11-04, nothing built yet. Branch `td3d/m4-overhaul`
(cut from `td3d/m2-m3` after the WIP snapshot commit 693424f).

The lore stays: everything in `docs/MISSION4_PLOT.md` from Logline to
"What It Leaves Open" is canon, plus the intro and ending cutscenes, the Maru
meet text, the tone choice (VO_076/077), the arrest PA ladder and Vasile's
"You don't need to see him" plant. The gameplay is replaced: the street walk
and the 60 s mic hold go.

---

## 1. The new mission at a glance

| # | Stage | Space | What the player does |
|---|-------|-------|----------------------|
| 0 | `STAGE_INTRO` | - | Intro cutscene, unchanged. |
| 1 | `STAGE_ESCORT` | Curfew street | Escort Vasile, who carries the KRAP comms cache, from the old-town safehouse to the station door. Patrols, the radio story beats. |
| 2 | `STAGE_FORTIFY` | Station | Walk the station and spend supply points on barricades. Hold the Maru meet (tone choice decides the allies). Install the jammer: this starts the siege. |
| 3 | `STAGE_SIEGE` | Station | About 8 minutes, 5 waves, arrest beats on the PA. Repair barricades with hold-E. |
| 4 | `STAGE_DONE` | - | `_complete_m4()` -> ending cutscene, unchanged. |

Combat is lethal, the same as M1-M3.

---

## 2. Mechanics

### 2.1 Escort (street)
- Vasile follows Biribel (leash about 2-4 tiles). He stops behind cover when
  shot at and moves on when the player moves on or the lane is clear.
- He carries the supply pool (see 2.2). The HUD shows his HP and the pool.
- **Downs:** the first time he hits 0 HP he is downed. Biribel has a revive
  window (proposed 10 s, hold E 2 s) to get him up. His second down kills him,
  and the mission fails back to the street checkpoint.
- Assumption to confirm: the first down also drops part of the supplies
  (proposed 25 % of the pool).
- Enemies: the existing IPA riflemen and marksmen (`M4_ROLE_TUNING`). They
  target Vasile as well as the player (proposed 35 % of shots when he is in
  line of sight).
- The radio story beats (Vasile's read on the collapse, the Volkov border
  intercept, the PA performing calm) play on the walk, as today.

### 2.2 Supply points
- One pool, `STATE.m4_supply`, filled by the KRAP comms cache Vasile carries.
- Proposed numbers: the cache starts at 24 points. Vasile taking damage does
  not drain it; only a down does (2.1).
- Spent in the fortify phase and on repairs during the siege. Leftover points
  carry through the siege; there is no refund.

### 2.3 Barricades (fortify phase)
- Fixed build sites on the station map: every door into the station halls and
  every street-facing window. Each site shows a ghost marker and its cost.
- Two tiers per site (proposed):

  | Kind | Cost | HP | Notes |
  |------|------|----|-------|
  | Door: planks | 3 | 300 | |
  | Door: welded plate | 6 | 700 | Costs more, holds breachers longer. |
  | Window: boards | 2 | 200 | Stops marksmen line of sight while it stands. |

- A barricade is a solid rect in `_solid_walls()` and blocks bullets. It has
  4 visual states (intact, damaged, broken, gone).
- Enemies path to the nearest open or weakest door. Riflemen shoot through
  broken barricades; breachers attack them directly (2.5).
- Build with E at a site. No build menu is needed: one press builds the cheap
  tier, a second press upgrades a door to plate.

### 2.4 Maru meet and allies
- The meet moves into the fortify phase: after the player has placed their
  first barricade (or walked into the transmitter hall), Maru is there.
- Same typewriter dialogue, same choice, same VO, `STATE.m4_tone` as today.
- **The tone choice decides who joins:**
  - "The state" -> **2 defecting soldiers**: armoured (proposed 160 HP,
    damage x0.6), rifles. Few, tough, hold one post well.
  - "The people" -> **4 MAG civilians**: fragile (proposed 60 HP), pistols and
    a shotgun. They cover more doors.
- Vasile and Maru stay as allies in both cases. Today's ally code
  (`_init_m4_allies`, `_ally_posts_for_tone`, `_arm_m4_allies`,
  `M4_ALLY_POSTS`) is the base. The new squads are extra entries per tone.
- The player assigns nobody; allies take fixed posts per tone (proposed:
  soldiers at the main hall and the studio mouth; civilians spread across
  four doors).
- Installing the jammer (E at the rack, `rifle_handle` + `terminal_glitch`)
  ends fortify and starts wave 1 after a short countdown (proposed 10 s).

### 2.5 Siege: 5 waves, about 8 minutes
Waves are data (`src/game/content/m4/waves.json`), run by one wave director.
Each wave has a duration, spawn doors, a unit mix, a max concurrent count and
the arrest beats that fire inside it. There is a lull of about 20 s between
waves; the PA and the radio talk over it.

| Wave | Time (approx.) | Units | Event | Beats on the PA / radio |
|------|----------------|-------|-------|--------------------------|
| 1 | 0:00-1:20 | Riflemen, 2 doors | - | "garrison command is... recalibrated" |
| 2 | 1:40-3:00 | Riflemen + marksmen on street roofs, first breachers | - | - |
| 3 | 3:20-4:40 | Breacher-heavy, 3 doors | - | "Balaceanu is relieved of command and arrested"; Vasile: "You don't need to see him. Trust me." |
| 4 | 5:00-6:20 | Mixed | **Wall breach:** a charge blows a hole in the studio-wing wall, a new lane no barricade covers | Jammed loyalist comms |
| 5 | 6:40-8:00 | All breachers | **APC breach:** a loyalist APC rams the main entrance and the front barricade is gone at once | "They're taking the General"; "Fall back! ... Break off!" ends it |

- The siege ends when the last beat airs and wave 5 breaks off. Remaining
  enemies retreat, then `STAGE_DONE`.
- Arrest-beat text stays word for word. Only its timing is re-laid across the
  8 minutes (`m4.arrest_beats.timeline.json`). The order of beats stays, so
  the radio never reports the cuffs before the ending cutscene shows them.
- The broadcast clock runs on the wave script. The old mic toggle
  (`_mic_state`, `_toggle_mic`, `M4_MIC_RADIUS`, off-air decay) goes.
- Assumption to confirm: losing the transmitter hall (enemies hold the rack
  area for 8 s) fails the mission, restarting the wave.

**Enemy roles**
- Riflemen and marksmen: existing roles, marksmen keep the laser telegraph.
- **Breachers (new):** path straight to the nearest barricade, ignore the
  player unless shot or within 2 tiles. They bash planks (ram) or plant a
  charge on plate (proposed 4 s fuse, audible beep, big damage). Lower HP
  than riflemen. The counter to fortifying.

**APC (wave 5 set piece):** set dressing, not a unit. A scripted drive down
the boulevard lane, a ram into the main door (camera shake, the barricade
goes to "gone"), then it sits in the doorway as cover. Breachers pour out of
it.

### 2.6 Repairs
- Hold E at a damaged barricade during the siege (proposed 1.5 s per step).
- Each step restores 25 % HP and costs 1 supply point. It cannot rebuild a
  "gone" barricade.
- The player is exposed while repairing: movement and aim are locked for the
  hold, and taking a hit cancels it.

### 2.7 Checkpoints
- Street: the start of the escort (same as today's street checkpoint).
- Fortify: the station door, with the supply pool as Vasile delivered it.
- **Siege: the start of the current wave.** A snapshot is taken at each wave
  start: barricade HP, supply pool, ally HP and posts, player HP and ammo,
  tone. Death reloads that snapshot. Checkpoint ids `m4_wave_1`..`m4_wave_5`.
- Old saves: any pre-overhaul M4 checkpoint id maps to the street start.

---

## 3. 2.5D presentation

Same approach as M2/M3: the 2D sim, collision and rules stay in sim pixels;
only the frame changes.

- `game/topdown3d.py`: add `"MISSION4": Cam(64.0, 25.0, 50.0)` to `CAMS`. No
  gate is needed: both spaces are 3D.
- New `missions/m4/draw3d.py`: hand-off from `draw.game_draw`, the M1 wall
  cutaway, 2D screen passes on top (HUD, prompts, radio crawl, build ghosts,
  repair ring) projected through `td.View`. Any renderer error ->
  `td.disable()` and the 2D painter.
- New `missions/m4/sets3d.py` (the M3 `wings3d` pattern): floors, props and
  lamps per space. Static batch per map; barricades, the breach hole and the
  APC drawn per frame.
  - **Curfew street:** rain-slick asphalt under sodium lamps, checkpoint
    barricades, burnt car hulks, curfew posters, a light rain layer
    (`cutscenes/weather3d.py` idiom). Light on wet ground, hard edges, dark
    ambient (house art rules).
  - **Radio station:** entry hall, transmitter hall with the rack and its
    status lights, studio wing with ON AIR lamps, corridors. Window boards,
    door planks, welded plate, each with 4 damage states.
- Cast: the blocky figures stay as they are (`figure_kit.SPECS`). Vasile
  carries the cache as a backpack prop. Breachers get a ram or charge-bag prop
  and a darker loadout. The defecting soldiers wear army colours with an MAG
  armband; the civilians wear plain coats with armbands.
- APC: a low-poly mesh in `game/content/meshes/` (the M3 van import path,
  `tools/ae_import_m3_van.py`, is the model), with a scripted drive and ram.
- Shots: `tools/m4_shots.py` for every stage and every wave, for review.

---

## 4. Code plan

Package stays `src/missions/m4/` with its facade and load order
(`meta -> maps -> world -> flow -> systems -> draw`). New parts slot in:

| File | Change |
|------|--------|
| `meta.py` | New stage constants, supply and barricade tuning, breacher role, ally squads per tone, wave checkpoint ids. Remove mic and hold constants. |
| `maps.py` | Authored grids instead of procedural ones (street route with cover for the escort, station with barricade sites, the breach wall and the APC lane). Glyphs for build sites (`b` door site, `w` window site), breach wall (`X`), APC lane (`A`). Keep `_validate`. |
| `world.py` | Vasile follower, downs and revive; barricade entities in `_solid_walls()`; ally squads per tone. |
| `escort.py` (new) | Vasile leash, cover-stop, revive logic. |
| `fortify.py` (new) | Build sites, supply spend, repair hold. |
| `siege.py` (new) | Wave director reading `waves.json`, breacher AI, wall breach and APC events, wave snapshots. |
| `flow.py` | New stage ladder; the Maru meet moves to fortify; arrest beats run off the director; checkpoint load per wave. |
| `systems.py` | Calls into escort, fortify and siege; drop the mic code. |
| `draw.py` / `draw3d.py` / `sets3d.py` | 2D fallback for the new entities, plus the 3D frame. |
| `game/content/m4/waves.json` | Wave data. |
| `game/content/timelines/m4.arrest_beats.timeline.json` | Re-timed over 8 minutes. |
| `core/save_system.py`, `core/game_core.py`, `app.py` | Wave checkpoint ids and the old-save mapping. |
| `tools/smoke_test.py` | Replace the M4 checks (section 6). |

Rules: no imports from `missions.m3` internals (port with `# ported from`
comments); stage flags on `STATE` (`m4_*`); one-owner module globals.

---

## 5. Build slices

Each slice ends green on `python tools/smoke_test.py` and
`python -m compileall -q src tools`, and is one commit.

1. **2.5D shell** - `CAMS` entry, `draw3d.py` and `sets3d.py` over today's
   maps, 2D fallback. The mission still plays the old way.
2. **Maps v2** - the authored street and station grids with build sites, the
   breach wall and the APC lane.
3. **Escort** - Vasile follower, supply pool, downs and revive, street fail.
4. **Fortify** - build sites, barricade entities, the Maru meet moved, tone
   allies, jammer starts the siege.
5. **Siege core** - wave director and `waves.json`, breachers, repairs,
   re-timed arrest beats, wave checkpoints. Remove the mic hold.
6. **Set pieces** - wave 4 wall breach, wave 5 APC.
7. **Art pass** - barricade states, APC mesh, breacher and ally looks, rain,
   grade, `tools/m4_shots.py`.
8. **Docs and polish** - rewrite the Mission Phases and Technical Notes in
   `MISSION4_PLOT.md`, tuning pass, golden frames if any cover M4.

---

## 6. Verification

Replace or rewrite these smoke checks:
- `mission4_boot_and_walk` - boots in 2.5D and in 2D (`ACA_TD_2D=1`).
- `mission4_layout` - new grids validate: sealed border, every build site on a
  door or window, escort route connected.
- `mission4_stage_transitions` (already failing before the overhaul) ->
  rewritten for intro -> escort -> fortify -> siege -> done.
- `mission4_hold_clock` -> `mission4_wave_director`: 5 waves in order, beats in
  order, siege ends on the last beat.
- `mission4_checkpoint_routes` - street, fortify and each wave snapshot reload;
  old checkpoint ids map to the street.
- New: `mission4_escort_downs` (one revive, second down fails),
  `mission4_barricades` (build cost, solid, damage states, repair cost),
  `mission4_tone_allies` (2 soldiers vs 4 civilians).
- Kept: `mission4_ending_shots_render`, `mission4_cinematic_arrest`,
  `mission4_campaign_chain`.

---

## 7. Open points to confirm

- Does Vasile's first down cost supplies (proposed 25 %)?
- Does losing the transmitter hall fail the wave (proposed 8 s hold by
  enemies)?
- Tuning numbers above (supply 24, barricade costs and HP, ally HP, wave
  timing) are first guesses for the tuning pass.

---

## 8. Build notes (2026-11-04)

All eight slices are in. Answers to section 7 and what changed in tuning:
- Vasile's first down spills a share of the supply (`M4_SUPPLY_DROP_FRAC`).
- Loyalists holding the rack for 8 s (`M4_RACK_HOLD_FAIL`) fail the wave.
- Biribel and the squad pass through their own barricades; only loyalists
  are held at them. This stops a softlock where a barricaded main door left
  Biribel or Vasile outside.
- A wave restart puts Biribel at `RESPAWN_TILE` (18, 9) by the rack.
- Rifle fire chips barricades at half damage (`M4_BAR_FIRE_MUL`). Riflemen
  working a barricade fire every 48-72 frames. Once boards drop under a third
  (they stop blocking shots), riflemen tear the rest out by hand. Boards
  have 260 hp.
- Civilians have 100 hp, up from 60. In playtest probes, three of the four
  died in wave 1 at 60 hp.
- Siege movement keeps the sub-pixel remainder (`siege._move`). Before this,
  units pinned at a window edge never slid into the gap.

In a static probe (player parked at the rack, auto-fire, periodic repairs),
both tones take no damage in wave 1. The pressure then climbs each wave, and
wave 5 peaks at 13 loyalists (cap 8 plus the APC load).
