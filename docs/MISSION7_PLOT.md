# Mission 7 — "Fallow Ground"

> **Status: PLANNED — not implemented.** There is no `src/missions/m7/` package
> yet; the campaign ships through M6. Everything below is design. See
> `docs/FIXES_STORIES.md` for the consistency pass applied to the plan.

> *"I grow potatoes. I don't do politics. Politics came anyway."*
> — Bodi

---

## Logline

Vasile has confessed and made his offer, and every road back to the capital
belongs to the Guard. Maru sends Biribel to ground on a farm in the hills,
with a quiet farmer called **Bodi** who doesn't ask questions. One slow
morning of chores, bad coffee and the first real silence in the whole game.
Then **Alex**, MAG's runner, comes up the track on a dirt bike with the
mansion plan, and an hour behind him comes a Guard sweep team. The farm
burns. Bodi watches it go and picks up his rifle. That night the radio offers
two channels: **Duty or Revenge.**

---

## Where We Pick Up (Recap from M6 Ending)

1. **Volkov is dead.** The leaf proves Vasile's code carried the Route 12
   convoy; the M2 auth chain proves Retardovici signed the cover.
2. **Vasile confessed** by radio and offered to get Biribel into the mansion
   in two nights.
3. **Biribel didn't answer him.** Maru: *"Not tonight. Go to ground."*

**M7 cold open: Day ~11, dawn.** Maru's helicopter can't risk the capital, so
it sets Biribel down in a field above Valea Seacă (the Dry Valley) and leaves.

---

## Characters & Arcs

### Biribel
Exhausted, carrying the notebook and Vasile's voice in his head. The farm is
the only place in the game where nobody gives him an order. He breaks that
peace just by being there.

### Bodi (new, farmer)
Late teens / early twenties, inherited the farm. Slim, dark straight hair with
a heavy fringe, a black tee with a green drip print under an open work
flannel, jeans, rubber boots. Quiet, deadpan, unimpressed by soldiers. Owns an
old bolt-action hunting rifle and knows every ditch on his land. He isn't MAG.
He owes Maru a favour, and that's all he'll say about it.
**Arc:** neutral → loses everything → chooses a side. By the end he is
Biribel's Little Jacob: the friend who drives and keeps showing up.

### Alex (new, MAG runner)
The youngest MAG face we meet. Short spiky brown hair, a bright blue sports
hoodie, ripped jeans, white trainers. Talks fast and too much, jokes when he's
scared, rides a stolen dirt bike. Brings MAG's mansion plan and Maru's message.
In the raid he's braver than he is good, and Biribel saves him once.

### Maru (MAG)
Radio only. Sends Biribel to the farm and, at the end, opens the MAG channel
for the choice.

### Commander Vasile
Radio only, at the end. Calm, patient, still on the other channel.

### The Guard sweep
Not Ucilev himself. A Presidential Guard sweep team (two trucks + a dog
unit) working the valleys for "the deserter". Did Vasile point them here? The
mission never says. That doubt is the point.

---

## Phases

| # | Phase | Objective | Beat |
|---|-------|-----------|------|
| 1 | **Drop-off** (3D cutscene) | — | Dawn mist, Maru's helicopter lifts off from a stubble field. Bodi at the fence with a bucket, not surprised. |
| 2 | **Chores** (top-down, no combat) | Feed the animals; fix the generator; bring the water in. | Walking-sim pacing (reuse `walking_sim.py`). Bodi's dry lines. Hidden in the barn: a MAG crate and a photo of Bodi with Maru. Optional: sit on the porch. |
| 3 | **The Runner** (2D cutscene) | — | Alex skids into the yard on a dirt bike. Maru's message, the mansion plan, too many jokes. |
| 4 | **Dust on the Road** (top-down) | Prepare the farm. | Two Guard trucks seen on the valley road. Choose 2 of 3 preparations: block the track with the tractor, rig the fuel shed, move Bodi to the hayloft. |
| 5 | **The Raid** (top-down, main fight) | Survive the sweep. | Waves through the orchard, the yard and the barn. **Bodi and Alex are AI allies.** Mid-fight the Guard sets the barn on fire. Save Alex when he's pinned by the well. |
| 6 | **Fallow Ground** (3D cutscene) | — | Night. The farmhouse and barn burning. Bodi sits on the tractor and watches. Then: *"I'm coming with you."* |
| 7 | **Two Channels** (radio, the choice) | — | Moved here from the end of M6. |

**Fail state:** death or Bodi going down for 20 s reloads the latest phase
checkpoint. Alex can go down and get back up (he can't die here).

---

## Key Scene — Drop-off

```
scene: m7_dropoff        speaker: ""       (Helicopter lifts away. Mist. A boy in rubber boots at the fence with a feed bucket.)
scene: m7_dropoff        speaker: BODI     "You're the one Maru called about. Boots off in the kitchen."
```

## Key Scene — Chores (sample lines)

```
scene: m7_chores         speaker: BODI     "The generator kicks. Hit it like you mean it."
scene: m7_porch          speaker: BODI     "I grow potatoes. I don't do politics."
```

## Key Scene — The Runner

```
scene: m7_runner         speaker: ALEX     "Biribel! THE Biribel! Maru said you'd be taller."
scene: m7_runner         speaker: ALEX     "Mansion plan. Guard rotations, cameras, the lot. Don't lose it, I nearly died for it. Twice."
```

## The Raid — callouts

```
scene: m7_raid           speaker: ALEX     "Trucks! Two of them - no, three!"
scene: m7_raid           speaker: BODI     "That's my barn."
scene: m7_raid           speaker: ALEX     "I'm pinned! Biribel, I'm pinned!"
```

## Ending — Fallow Ground (3D) → Two Channels

```
scene: m7_fire           speaker: ""       (Night. The barn roof falls in. Bodi on the tractor seat, rifle across his knees.)
scene: m7_fire           speaker: BODI     "They'll come back. There's nothing left to come back to." (beat) "I'm coming with you."
scene: m7_radio          speaker: VASILE   "Biribel. The offer stands. Tomorrow night."
scene: m7_radio          speaker: MARU     "Two channels, Biribel. His, and ours. Pick one."
scene: m7_choice         speaker: ""       [ ANSWER VASILE - DUTY ]   [ MEET VASILE ALONE - REVENGE ]
```

The choice is staged like GTA IV's: two radio channels blinking, no timer, no
hint which is "right". It's saved as `STATE.m8_route = "duty" | "revenge"`.

---

## What This Resolves

- Introduces Bodi and Alex, and gives them a reason to follow Biribel.
- Gives the player one quiet breath before the finale.
- Moves the Duty/Revenge choice to the moment Biribel has the most to lose.

## What It Leaves Open (For M8)

- Duty or Revenge.
- Did Vasile send the sweep team?

---

## Voice Lines (TTS) — new characters

Kept short on purpose. Use one generation per line, in this order. Put the
files in `assets/voice/Bodi/` and `assets/voice/Alex/` (TTS names are fine;
the voice matcher takes them oldest-first, like the other folders).

| ID | Speaker | Line |
|----|---------|------|
| BODI_01 | Bodi | "You're the one Maru called about. Boots off in the kitchen." |
| BODI_02 | Bodi | "The generator kicks. Hit it like you mean it." |
| BODI_03 | Bodi | "I grow potatoes. I don't do politics." |
| BODI_04 | Bodi | "That's my barn." |
| BODI_05 | Bodi | "They'll come back. There's nothing left to come back to. I'm coming with you." |
| BODI_06 | Bodi | "Go. We've got the doors." *(M8 Duty)* |
| BODI_07 | Bodi | "I'll drive. You think." *(M8 Revenge)* |
| BODI_08 | Bodi | "This part's yours." *(M8 Revenge)* |
| BODI_09 | Bodi | "Train leaves at six. I'll wait till it does." *(M8 Revenge)* |
| ALEX_01 | Alex | "Biribel! THE Biribel! Maru said you'd be taller." |
| ALEX_02 | Alex | "Mansion plan. Guard rotations, cameras, the lot. Don't lose it, I nearly died for it. Twice." |
| ALEX_03 | Alex | "Trucks! Two of them - no, three!" |
| ALEX_04 | Alex | "I'm pinned! Biribel, I'm pinned!" |
| ALEX_05 | Alex | "Two on the fountain, one in the hedges. I'm going left!" *(M8 Duty)* |
| ALEX_06 | Alex | "Biribel - the mansion, they were waiting for us. Maru's down. I'm sorry. I'm sorry." *(M8 Revenge)* |

Plus two short lines for existing voices: **VASILE** "Biribel. The offer
stands. Tomorrow night." and **MARU** "Not tonight. Go to ground." (M6 ending).
Bodi's M8 Revenge callout "They knew we were coming. Stay low!" is optional;
skip it if you want fewer files.

**Voice direction:** Bodi = low, slow, flat, a little sleepy. Alex = fast,
bright, cracks when he's scared.

---

## Technical Notes

- **Package:** `src/missions/m7/`, same facade pattern; stage driver
  `STATE.mission7_stage`.
- **Map:** one farm map (yard, farmhouse, barn with hayloft, orchard, fuel
  shed, well, the track down to the valley road). Fire spreads by tile over
  the raid's second half (cosmetic + blocks the barn).
- **Allies:** reuse the M4 ally system (posts, cover, downed state). Bodi =
  slow, high damage, long range; Alex = fast, low damage, flanks.
- **Art:** `figure_kit` "bodi" and "alex" (2D), `cast3d.humanoid3d("bodi")`
  / `("alex")` (3D). Already in the cast sheet (`python tools/cast_sheet.py`).
- **New state:** `STATE.m7_preps` (the 2 chosen preparations),
  `STATE.m8_route` (set by the choice).

---

## Implementation Notes (2026-10-27, branch `m7/fallow-ground`)

All seven beats are playable end to end: `python acaristan.py`, or jump in with the
`m7*` dev jumps in `core/dev_jumps.py`. The stage ladder is `arrival, chores, runner,
prep, raid, finale, choice` (`missions/m7/meta.py`); M7 completion now takes over the
"FULL CAMPAIGN COMPLETE" end that used to sit on M6.

Dev jumps (run from the repo root; `python acaristan.py --list-jumps` prints them all, and
`tools/dev_panel.py` lists them under "Mission 7"): `--jump m7`, `m7-arrival`, `m7-chores`,
`m7-runner`, `m7-prep`, `m7-raid`, `m7-raid-prepped` (all three preps), `m7-raid-w2` and
`m7-raid-w3` (raid checkpoints 1 and 2), `m7-finale`, `m7-choice` and `m7-outro`. The plain
`m7-raid` jump also reads `--m7-preps=tractor,shed,loft` and `--m7-cp=1|2`.

| Beat | Stage | Built as |
|---|---|---|
| 1 Drop-off | `arrival` | 3D film `m7.arrival` (`cutscenes/m7films.py`, farm builder `cutscenes/m7world3d.py`) |
| 2 Chores | `chores` | top-down farm (`missions/m7/farmyard.py`, level `m7.farm.level.json`): generator, water, feed |
| 3 The Runner | `runner` | 2D film `m7.runner` (`cutscenes/m7runner.py`) |
| 4 Prep | `prep` | same farm, pick 2 of tractor / fuel shed / hayloft, stored in `STATE.m7_preps` |
| 5 The Raid | `raid` | playable 3D scene (`raid3d.py`, `raid_brain.py`, `raid_world.py`, `raid_hud.py`) |
| 6 Fallow Ground | `finale` | 3D film `m7.finale`, burning farm at night |
| 7 Two Channels | `choice` | radio screen (`choice.py`), writes `STATE.m8_route`, then the `m7.outro` film |

**Raid as built.** Third-person over-the-shoulder 3D scene in the shape of the M6 yard, not
the M4 ally system: Bodi and Alex are AI allies on `engine.ai`. Three waves (orchard, trucks,
north with the barn on fire and Alex pinned at the well). Checkpoints after wave 1 and 2 are
reloaded inside the scene. The player dying, or Bodi staying down 20 s, reloads the last
checkpoint. Holding E frees Alex or revives Bodi. Preps change the fight: the tractor blocks
the track mouth, the fuel shed leaves a shootable fuel tank that explodes, and
the hayloft gives Bodi a high ledge with sight over the yard.

**Doc conflicts left for the author (nothing was changed to hide them):**

- Vasile says "Tomorrow night" here. The M8 Revenge route says the meeting is "at dawn".
  M7 text is kept; fix whichever side is wrong.
- Vasile is "Captain" in `LORE.md` and "Commander" in this file. The game only shows `VASILE`.
- Alex shouts "Trucks! Two of them - no, three!" (kept verbatim; the miscount is the joke).
- The raid's time of day and start trigger are not defined in this doc. Night was chosen.
- The choice actions follow the doc: "Answer Vasile" is `duty`, "Meet Vasile alone" is
  `revenge`. The screen prints only the action and the speaker, never the route word, so
  neither channel is marked as right.

**Known gaps.** Bodi and Alex have no recorded takes yet: `VO_219` to `VO_228` are manifest
rows listed in `KNOWN_MISSING_AUDIO`, and the lines show as captions. Only `progress="m7"` and
the stage token are saved; `m7_preps` and the raid checkpoint are not, so resuming a save at
`raid` starts the fight with no preps.

## Second pass (2026-10-28): sound, farm work, the Fallow 12, the receiver

The owner's play test found the farm silent, the tractor a cutscene, the note handoff weak and
the ending a text dump. This pass fixes those, and adds the shotgun.

- **Audio.** New `src/missions/m7/m7_audio.py`: 29 synthesised sounds (day farm bed, night bed,
  choice hum, wildlife, footsteps, well/pour/grain/hay, generator pull/cough/backfire/catch/
  idle, tractor idle/move/rev/stall/off/chock, receiver tune/lock), plus the shared
  `shotgun_blast`/`shotgun_pump`/`shell_insert` in `audio/audio.py`. Farm footsteps, dialogue
  ticks, wildlife and every interaction are wired; `M7Audio` owns its loops and stops them on
  stage change, pause, mission reset and quit. `core/ambience.py` no longer plays the indoor
  `room_tone` over the open farm and now adds M7 to the gust set.
- **Generator.** Four E-taps became prime (3 taps) -> choke (timed) -> three pull strokes in a
  moving band, with coughs/backfires and a compression meter. Misses retry; the chores set and
  the objective text are unchanged.
- **Tractor.** The 1.8 s tween became a five-leg driven route (reverse, hard left, down the
  lane, swing right, set it down) with timed steering prompts, clean/sloppy input, stalls that
  replay, and a 16-frame pre-rendered rotation. Preps and the blocking collider only change
  when the tractor is actually parked.
- **Fallow 12.** Pump shotgun, given by Alex with the plan. In the raid it replaces the K-9:
  6 shells, 8 pellets (10 body / 24 head), 0.95 s pump, 2.2 s reload, shell pickups, new HUD.
  In multiplayer it is `WPN_SHOTGUN = 4`, a crate pickup on all three maps, key 4, a fourth
  loadout slot, and its own 2D rig (`RIGS["shotgun"]`, sharing the OS-12 finish so the
  32-entry cosmetic catalog is untouched). Biribel's 3D hold is solved onto grip and fore-end
  (`hold_report` support gap 0, arm depth 2.2 cm); the 2D hold passes
  `tools/shot_weapon_grid.py` at the same 4 px grip error as the other guns.
- **The runner film.** The folder is wrist-parented, tweened between the two figures, and given
  its own close-up insert (`m7_runner_plan`). A new `m7_runner_shotgun` + `m7_runner_gun` pair
  shows Alex setting the Fallow 12 into Biribel's hands (`VO_228`).
- **The ending.** `choice.py` is now a field receiver: the real `RadioTransmission` widget
  (portrait, typewriter, static) centred, with two physical channel cards, blinking standby
  LEDs, a TX lamp and no route words. It is live from frame 1 (the old six-second wait is
  gone), `1`/`2` or `A`/`D` tune, Enter transmits, and the `_S["t0"]`/`done_at` contract the
  smoke test drives is unchanged.
- **Gates.** `SMOKE TEST: OK` including eight new M7/arena checks; `compileall` OK;
  `ae_hold_check` OK; `engine3d_check` OK. The unit voice test covers `VO_228`.

**Still open.** Bodi/Alex takes (including `VO_228`); `m7_preps` and the raid checkpoint across
save/resume; the choice still has no mouse input; the farm paint is unchanged by request.
