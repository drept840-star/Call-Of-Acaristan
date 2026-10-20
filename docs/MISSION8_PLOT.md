# Mission 8 — "The Call"

> **Status: PLANNED — not implemented.** There is no `src/missions/m8/` package
> yet; the campaign ships through M6. Everything below is design. See
> `docs/FIXES_STORIES.md` for the consistency pass applied to the plan.

> *"I chose the many. You chose the four."*
> — Captain Vasile

---

## Logline

The final mission splits on the choice made at the end of Mission 7 (Bodi's farm).

- **DUTY — "Head of State":** take Vasile's help, storm Retardovici's mansion
  with Bodi and Alex at your back,
  chase his helicopter across the capital with Maru at the controls, get shot
  down by Ucilev, and end it through a sniper scope on a frozen ridge. Then
  listen to what the dying President has to say about Vasile — and shoot anyway.
- **REVENGE — "Old Friends":** ignore the President. Bodi drives you out to
  meet Vasile where he chose to meet: the Route 12 ambush site where the squad died. Fight
  through his Guard and put six rounds in the man who raised you.

Both endings are bittersweet. Neither is the "good" one.

| | You win | You lose |
| --- | --- | --- |
| **Duty** | The tyrant is dead. The country is free. | The traitor takes the throne — and you put him there. |
| **Revenge** | The squad is avenged. | Maru dies, the dictatorship survives, and you leave forever. |

---

## Where We Pick Up (Recap from M6 + M7)

1. **Volkov is dead** at the Kim Kim border, one step from the train.
2. **The notebook proves it:** Retardovici ordered Route 12; Vasile's codes
   carried it out.
3. **Ucilev is Bogdan Velicu**, Biribel's own KRAP intake, officially
   dead since Y-2.
4. **Vasile confessed** — "I chose the many" — and offered to get Biribel into
   the mansion.
5. **Bodi's farm burned** (M7). The Guard raided it looking for Biribel. Bodi
   has nothing left to protect, so he's coming along. Alex brought MAG's
   mansion plan.
6. **The choice** (end of M7): `STATE.m8_route = "duty" | "revenge"`.

---

## Characters & Arcs (both routes)

### Biribel
In both routes he finally chooses his own target, and in both he pays for it.

### Captain Vasile
Never a cartoon. He did sell the squad, and he did it to keep 300 men alive —
and to keep himself in the room where power is. **Duty:** he survives and
becomes President. **Revenge:** he dies without begging.

### Bodi (farmer)
Not a soldier and doesn't pretend to be. Quiet, dry, steady with his old
hunting rifle. He lost the farm because Biribel slept in his barn and he has
decided that makes it his fight too. **Duty:** holds the ballroom doors so
Biribel can reach the study; survives, stands in the epilogue crowd.
**Revenge:** Biribel's driver and backup, Little Jacob-style. Drives him out
to Route 12 in the farm truck, fights the Guard trap beside him, stays at the
foot of the gantry ("This part's yours."), and drives him to the border
after.

### Alex (MAG runner)
Young, loud, fast, cocky in a way that's mostly nerves. Maru's courier.
**Duty:** an AI ally in the mansion fight (gardens → ballroom), flanking and
calling targets; survives. **Revenge:** rides with MAG's attack on the mansion
off-screen; gets out alive and is the voice on the radio telling Biribel it
failed.

### Maru (MAG)
**Duty:** flies the helicopter; pinned in the wreck with a broken leg; hands
Biribel the rifle; survives. **Revenge:** leads the mansion attack without
Vasile's inside access; it fails; Maru is killed.

### Ucilev Nadgob Ierdna
**Duty:** the gunship pilot who shoots Maru down — the chase's final boss —
then shields Retardovici on the evacuation pad. Biribel has to shoot him first.
He dies with dignity. **Revenge:** never fights Biribel. In the epilogue he is
named Commander of the Presidential Guard — Vasile's old job — and is last seen
at the border, looking at Biribel's photo.

### President Retardovici
**Duty:** the target. Gets the last speech. **Revenge:** survives and calls
Biribel a terrorist on national TV.

---

# ROUTE A — DUTY: "Head of State"

## Phases

| # | Phase | Objective | Beat |
|---|-------|-----------|------|
| 1 | **Approach** (3D cutscene) | — | Presents the mansion: slow aerial pass over the lit estate, guards, the helipad. Vasile on the radio walks Biribel through it. |
| 2 | **The Mansion** (top-down) | Fight to the President's study. | Big fight: gardens → ballroom → staircase → study, with **Bodi and Alex as AI allies**. Vasile kills the security systems on cue ("cameras down in three, two..."). At the ballroom doors they stay behind to hold the stairs. |
| 3 | **Liftoff** (3D cutscene) | — | The study is empty. Through the window: Retardovici's helicopter lifting off. Maru's helicopter swoops in low over the lawn — Biribel jumps for the open door. |
| 4 | **Last Flight** (3D, interactive) | Door gunner chase, ~4:30. | See below. |
| 5 | **The Crash** (3D cutscene) | — | Spin, impact, black. Forest fire light. Maru pinned. |
| 6 | **The Ridge** (3D, interactive) | Climb the ridge; snipe. | First-person scope finale. See below. |
| 7 | **Epilogue** (3D cutscene) | — | Vasile's inauguration. |

## Phase 4 — "Last Flight" (helicopter chase)

You're the door gunner. **Maru flies** — fitting, since Maru is the one who
always got Biribel in and out. The route is fixed; the gun is yours.

| Time | Section | What happens |
|------|---------|--------------|
| 0:00–0:40 | **Mansion lawn** | Liftoff under fire: lawn guards, two AA trucks. Teaches aim, overheat and flares. |
| 0:40–1:50 | **Curfew Boulevard** | Searchlights, rooftop rocket teams. Maru weaves between buildings; Retardovici's helicopter visible ahead. |
| 1:50–2:50 | **The Radio Station** | Fly past the M4 roof where Biribel and Vasile watched the dawn. Two Guard helicopters engage. |
| 2:50–3:50 | **Route 12** | Over the highway where the squad died; a convoy fires from below. Shred Retardovici's tail rotor until he's forced down beyond the ridge. Maru, quietly: *"This is where they died, isn't it?"* |
| 3:50–4:30 | **Ucilev** | His gunship comes out of the fog. A short duel — rockets, flares, his searchlight on you. He wins. Rocket hit, spin, forest. |

**Controls:** mouse aims the door gun (yaw/pitch limits of a real mount), hold
to fire, barrel overheats; one key fires flares (limited, regained per section).

**Fail conditions (restart at the last section checkpoint):**
- **Hull reaches zero.** Damage is visible: smoke trails thicken, warning tone,
  Maru's lines get tense.
- **Retardovici escapes.** A distance meter; if his helicopter leaves range
  for too long, he's gone.
- **Rockets:** the GTA way — shoot them down or pop flares. Maru calls them:
  *"Rocket, left side!"*

**The shootdown is always scripted** — the story needs it — but you only
reach it by surviving everything before it.

**Maru callout pool:** "Hold on!", "Rocket, left!", "Searchlight - kill it!",
"I'm hit, I'm fine, keep shooting!", "That's the roof. ...Keep shooting.",
"He's going down! He's going -", "UCILEV. Brace!"

## Phase 5 — The Crash

```
scene: m8d_crash_wake    speaker: ""      (Ringing. Fire light through trees. The helicopter on its side.)
scene: m8d_maru_pinned   speaker: MARU    "Leg's done. Don't. Don't you dare carry me."
scene: m8d_maru_pinned   speaker: MARU    "His bird went down past the ridge. He's waiting for a pickup."
scene: m8d_rifle         speaker: MARU    "Go. Finish what we started." (hands Biribel the sniper rifle)
```

## Phase 6 — The Ridge (sniper finale)

First-person scope over the evacuation pad below: Retardovici's damaged
helicopter, a few surviving Guards, a rescue helicopter's lights approaching.

1. **Ucilev steps in front of the President.** He knows exactly where Biribel
   is. He doesn't hide. Biribel has to take him first.
2. **Ucilev kill scene (3D, slow-motion):** one round. He drops to his knees,
   looks up at the ridge.
   *UCILEV: "Now you know what it's like to follow orders."*
3. **Retardovici** grabs a Guard radio, on Biribel's channel:
   *"You know what he did on Route 12. You don't know what he did tonight."*
   *"Who told you the mansion's weak points? Who turned off my cameras?"*
   *"Who do you think gave me to you?"*
   *"Tomorrow he sits in my chair. And you put him there."*
4. **You shoot anyway.** The player has to pull the trigger — the game waits.
   Kill scene: slow-mo, scope recoil, the radio hissing in the snow.

**Scope mechanics:** sway, breath-hold key (limited), wind indicator, simple
drop, scope zoom levels. Failing = the rescue helicopter lands and lifts off
with him → retry from the ridge.

## Phase 7 — Epilogue (Duty)

```
scene: m8d_inauguration   speaker: ANCHOR    "Interim President Vasile takes the oath this morning, on the steps of the old courthouse."
scene: m8d_vasile_speech  speaker: VASILE    "We owe this morning to soldiers whose names you will never know."
scene: m8d_crowd          speaker: ""        (Biribel in the crowd. Maru beside him on crutches. Bodi and Alex a row behind.)
scene: m8d_eyes           speaker: ""        (Vasile, on the stage, finds Biribel in the crowd. A tiny nod.)
scene: m8d_biribel_vo     speaker: BIRIBEL   "Gabi, Seby, Darius. Volkov. The country's free. I wanted to tell you that."
scene: m8d_biribel_vo     speaker: BIRIBEL   "I didn't want to tell you who's holding it."
scene: title_card         speaker: ""        "CALL OF ACARISTAN"
```

---

## Bodi & Alex — mansion lines (Duty)

```
scene: m8d_gardens        speaker: ALEX      "Two on the fountain, one in the hedges. I'm going left!"
scene: m8d_ballroom       speaker: BODI      "Go. We've got the doors."
```

---

# ROUTE B — REVENGE: "Old Friends"

## Bodi — Revenge lines

```
scene: m8r_truck          speaker: BODI      "I'll drive. You think."
scene: m8r_trap           speaker: BODI      "They knew we were coming. Stay low!"
scene: m8r_gantry         speaker: BODI      "This part's yours."
```

## Phases

| # | Phase | Objective | Beat |
|---|-------|-----------|------|
| 1 | **The Meet** (3D cutscene) | — | Bodi drives Biribel out to Route 12 at dawn in the farm truck. The toll gantry, the burned cars, the M2 set — rebuilt, quiet. |
| 2 | **The Trap** (top-down) | Survive. | Vasile brought the Guard. Old KRAP faces. The fight runs back along the M2 route in reverse. **Bodi fights beside you** (AI ally, hunting rifle) and covers from the truck. |
| 3 | **The Gantry** (top-down) | Reach Vasile. | Up onto the sign gantry where the M2 sniper sat. Bodi stays at the bottom: *"This part's yours."* |
| 4 | **Old Friends** (3D dialogue) | — | The two of them alone. |
| 5 | **The Kill** (3D, interactive) | Shoot Vasile. | GTA IV-style execution. See below. |
| 6 | **Epilogue** (3D cutscene) | — | The cost. |

## Phase 4 — Old Friends

```
VASILE   "You picked the four over the three hundred."
BIRIBEL  "You didn't pick the three hundred. You picked the desk."
VASILE   "...Maybe. Maybe both. Does it matter to them?" (nods at the road)
VASILE   "I taught you to shoot on this kind of morning. Cold barrel, steady hands."
VASILE   "I chose the many. You chose the four."
```

## Phase 5 — The Kill

The player controls every shot. The camera holds close, over Biribel's
shoulder, and each hit gets its **own** reaction — no single death animation:

1. **Shoulder** — he spins half-around, catches the railing.
2. **Gut** — he folds, knees buckle.
3. **Leg** — he drops to one knee, still looking up.
4. **Chest** — he sits back against the railing, slides down.
5. **Chest** — hand falls from the wound. Breathing.
6. **Final** — slow-motion, camera cuts to the road below, the squad's burned
   cars. Silence.

Vasile doesn't beg. Between shots he says nothing, or at most: *"...Steady
hands."* The player can stop shooting at any point after the third shot — he
dies either way, but the game lets the player decide how much they needed.

## Phase 6 — Epilogue (Revenge)

```
scene: m8r_radio          speaker: ALEX      "Biribel - the mansion, they were waiting for us. Maru's down. I'm sorry. I'm sorry-" (static)
scene: m8r_tv             speaker: PRESIDENT "The terrorist Maru is dead. The traitor Biribel will be found."
scene: m8r_ucilev         speaker: ANCHOR    "...appointed Commander of the Presidential Guard, Bogdan Velicu."
scene: m8r_bodi_truck     speaker: BODI      "Train leaves at six. I'll wait till it does."
scene: m8r_border_train   speaker: ""        (The Kim Kim border. Night. The train Volkov never caught. Biribel on it. Bodi's truck on the road outside, headlights off.)
scene: m8r_ucilev_photo   speaker: ""        (Ucilev at the border post, holding Biribel's photo. He watches the train go.)
scene: m8r_biribel_vo     speaker: BIRIBEL   "Gabi, Seby, Darius. It's done. He's gone."
scene: m8r_biribel_vo     speaker: BIRIBEL   "Volkov - I caught your train. The coffee's terrible."
scene: title_card         speaker: ""        "CALL OF ACARISTAN"
```

---

## Foreshadowing to Retrofit into M1–M4

Small additions that make the Vasile twist feel planned all along. None change
gameplay.

| Mission | Add | Pays off in | Shipped? |
|---------|-----|-------------|----------|
| **M1** | Vasile pockets the notebook without reading it in front of Biribel: *"Good. I've got it. Later. You need sleep."* | M6 — he already knew what was in it. | **Yes** — M1 escape cutscene (caption + radio VO, VO_198). |
| **M1** | Volkov, as he escapes: *"Read it before you hand it over!"* (sounds like a taunt) | M6 boxcar: "You took this from me once. Read it this time." | **Yes** — `core/interactions.py`. |
| **M2** | Half a second of radio static from Vasile's channel right before the sniper's first shot. | M6 — the convoy route went out on his channel. | **Yes** — the 3D kill-box film, dead air in the gap before the first round. |
| **M2** | Vasile's line before the kill-box: *"Route's clean. I checked it myself."* | M6 / M8. | **Yes** — the film's opening radio line (VO_199). |
| **M2** | *(new)* The upload OS auth chain carries **VASILE, C. — KRAP LIAISON** as the node that authorised Route 12 operations. | M6 — the player has seen his name on the order since M2. | **Yes** — `ui/upload_os.py`. |
| **M3** | Volkov: *"Your captain's code opened that IPA relay on the first try. Ask him where he got it."* | M6. | **Yes** — `missions/m3/meta.py`. |
| **M4** | Vasile steers Biribel away from the arrest: *"You don't need to see him. Trust me."* | Balaceanu could have exposed Vasile. | **Yes** — the arrest beat ladder (VO_200). |
| **M4** | Warm moments for Vasile in the command van and on the roof (a story about his daughter, a joke) — the player must **like** him. | Makes M8 hurt in both routes. | Partly — the M4 roof/van warmth is shipped; the "daughter" story is not. |

---

## Technical Notes

- **Package:** `src/missions/m8/` with `duty/` and `revenge/` parts behind one
  facade; `STATE.m8_route` picks the stage ladder. Save system records
  `MISSION_8` and the route.
- **Allies:** Bodi and Alex reuse the M4 ally system (`M4_ALLY_POSTS`-style
  posts: meet / cover / door, hp, damage, downed state). Downed allies get back
  up after the room is cleared, so neither can die in the mansion. In 2D they
  are `figure_kit` "bodi" / "alex"; in 3D `cast3d.humanoid3d("bodi")` etc.
- **3D stack:** every cutscene and both kill scenes run on `engine3d`
  (`GLRenderer`, auto-fallback to software). Characters via
  `r.add_humanoid(...)` (GPU-skinned — crowds and Guards are cheap).
- **Kill scenes:** per-hit reaction poses blended with `blend()` over ~0.25 s,
  layered on a slow-motion time scale; camera cuts keyed to hit events, like the
  M2 film's VO-anchored cuts. Reuse the M2 blood mist, spark and muzzle sprites.
- **Helicopter chase:** fixed spline route; city chunks (blocks of `box`
  buildings, streets, lights) streamed ahead and dropped behind
  (`r.objs` + `GLRenderer.invalidate_static()` on chunk swap, or one baked Obj per
  chunk toggled with `.visible`). Night fog hides streaming. Door gun aim as a
  yaw/pitch offset on the camera; hits by ray vs. target spheres. Rotors =
  spinning flat boxes plus a translucent disc sprite. Searchlights = emissive
  cones (double-sided, layer 1).
- **Sniper finale:** first-person scope reusing the M2 scope overlay; sway =
  low-frequency noise on aim, breath-hold damps it; drop = small y offset by
  range.
- **Verification:** smoke checks per route (stage ladder, checkpoints, chase
  fail conditions, kill-scene shot count), and every 3D shot rendered on both
  backends via `tools/engine3d_check.py`-style parity.
