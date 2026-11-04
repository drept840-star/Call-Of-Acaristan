# Mission 4 — "The Aftermath"

> *"Nobody asked us to do this. First time in my life — that's how it's done right."*
> — Biribel, on the studio roof at dawn

---

## Logline

Two days after the Vostral went live, the capital is eating itself. Balaceanu's
career is public record, Retardovici's strings are cut (the read on the
night — a cape without a handler), KRAP has "kind of dissolved," and Volkov
has run for the border. Biribel and Vasile are what's
left of the thread. The one transmitter still loyal to nobody but the truth is
the state radio station — and Balaceanu's last loyalists intend to take it back.
The job is not to kill anyone. The job is to **hold the mic open long enough for
the President to arrest the Prime Minister on the Prime Minister's own airwaves.**
Biribel never sees Balaceanu. He only hears the regime collapse without him.

---

## Where We Pick Up (Recap from M3 Ending)

M3 ended on the record beating:

1. **The Vostral is on every screen** — Balaceanu's fabricated service history,
   read in his own building, live.
2. **Balaceanu's public career is over**, but he is not in custody — the arrest
   hasn't landed yet, and his loyalists still have rifles.
3. **Volkov is gone**, and **KRAP is under government review** — the organization
   neither dissolves cleanly nor survives intact.

**M4 cold open: two days later, the capital.** No handler assigning targets, no
clean chain of command. The frame is no longer "mission assigned" — it is "what
do we do now," and the answer Vasile gives is: keep one transmitter breathing
until the state arrests its own head of government on air.
> The shipped line is *"Forty-eight hours after the Vostral…"* (VO_078) — M4 is
> **Day 6** (dawn Day 7), not the same night as the M3 broadcast.

---

## Setting

**The capital, ~48 hours of curfew.** Two connected spaces, both procedurally
generated in the M3 `list[str]` tile grammar, both border-sealed:

- **The curfew street (40×40)** — a rain-slick night city between the old-town
  safehouse and the radio station cordon: a ruined boulevard, checkpoint
  barricades, three named zones (Old Town Safehouse, Curfew Boulevard, Radio
    Station Cordon) and sparse IPA loyalist patrols (guards on the checkpoints,
    marksmen on the long sightlines).
- **The state radio station (24×20 interior)** — south entry hall, north
    transmitter hall, east studio wing, joined by corridors. This is the siege
    ground; the transmitter is the objective, not a boss.

**Time:** one night into first light. The mission clock is the story.

---

## The Spine — Making the Vendetta Irrelevant

The trilogy's through-line was Balaceanu's attempt to have Biribel killed. M3
proved the Vostral. **M4 inverts the payoff: Biribel does not kill Balaceanu,
because the state does it for him, on live air, while he can only hear it.** The
vendetta ends by being made *small* — a name in an arrest order read over a PA
the hero is standing three rooms away from. The nation cheers the wrong man
(Retardovici — read tonight as the puppet who just ate his own handler; **M5
reveals he was the puppeteer and the handler was the one on the air**), and
Biribel — the one person who knows how the dominos actually fell — chooses to
stay and keep fighting rather than take the border that would finally let him
disappear.

---

## Characters & Arcs

### Biribel
From soldier-for-hire to a man picking his own last job. The liaison's tone
question ("the state, or the people inside it?") is the seed of the ending V.O.;
both answers land on the same roof at dawn — the choice is about *why he stays*,
not about which scene plays.

### Captain Vasile
No longer commanding an organization — commanding two people and a radio. He
runs the comms cache, calls the loyalist movements, and holds the aisle at the
station. His arc closes the M3 "commander to resistance leader" line: this is
all that's left of the resistance, and it's enough for one night.

### Maru (MAG)
**First physical presence.** The voice from three missions walks into the
transmitter hall in person. Maru sets the terms of the hold and asks Biribel the
tone question. KRAP "kind of dissolves"; its remnants ally with MAG — the
liaison meet *is* that alliance, sealed over a jammer and a transmitter.

### Prime Minister Balaceanu
Absent. Never drawn, never fought, never named to Biribel's face in the room. He
exists entirely as a PA caption and a color on a radio crawl — a career ending
off-screen while the protagonist holds a door for it.

### President Retardovici
The cape is gone; the man wearing it is not. His arrest order is the clock's
voice — the regime's survival mechanism, turned on itself. Foreshadows the M5+
reveal (the wrong man on the throne).

### Sebastian Volkov
Gone to **Regatul Kim Kim** (radio lore only). An intercepted border log, not a
character. His flight is the sound of every opportunist leaving the board.

---

## Mission Phases (Stage Ladder)

The runtime driver is `STATE.mission4_stage` (mirrors M3), owned by
`missions/m4/flow.py::start_m4` and advanced by `_update_stage`.

| # | Stage | Objective | Beat |
|---|-------|-----------|------|
| 1 | **STAGE_INTRO** | - | Intro cutscene, then the street. |
| 2 | **STAGE_ESCORT** | Bring Vasile and the KRAP cache to the station door. | Vasile follows Biribel down the curfew street carrying the cache (the supply pool, 24). Guard and marksman patrols; the timed radio story beats (Vasile's read on the collapse, the border intercept, the PA performing calm) still air on their clock. Vasile can be revived **once** (hold E inside 10 s); the first down spills a share of the supply, the second kills him and fails the mission. |
| 3 | **STAGE_FORTIFY** | Meet Maru, build the barricades, plant the jammer. | Door handoff swaps to the station. Biribel holds E at door sites (planks, upgrade to steel plate) and window sites (boards), paid from supply. The Maru meet runs here, word for word: Biribel admits the chain carried Vasile's name - "There's an explanation." - and Maru answers, "There always is." The tone choice (VO_076/077) now picks the squad: **the state** sends 2 armoured soldiers, **the people** 4 fragile MAG civilians. Planting the jammer on the rack starts a 10 s countdown. |
| 4 | **STAGE_SIEGE** | Hold the station for 8 minutes. Keep them off the rack. | Five waves of riflemen, marksmen (laser telegraph) and breachers (charges on plate, shotguns up close). MAG runners bring timber before waves 2-5. Wave 4 blows the weak east wall; wave 5 opens with the APC ramming the forecourt and unloading breachers. Repairs are hold E, 1 supply a step, any time. The arrest PA ladder plays out word for word over the 8 minutes, and Vasile still steers Biribel away from it - *"You don't need to see him. Trust me."* (M6 plant). The completion card quotes VO_082 and the tone echoes on the M5 card. |
| 5 | **STAGE_DONE** | - | Clock ends -> `_complete_m4()` -> `request_mission4_ending`. |

**Fail state:** combat stays lethal. Death restarts the current wave from its
snapshot (5 s before it, barricades, supply, squad and APC as they were, Biribel
back by the rack); before the siege it reloads the station or the street.
Loyalists holding the rack for 8 s fail the wave. Vasile's second down fails
the mission. All routes go through `game_core.restart_current_mission()`.

---

## Intro Cutscene Shot-List

```
scene: m3_end_nation      speaker: NARRATOR   "Forty-eight hours after the Vostral, the address is still reading on every screen in the capital."
scene: m4_city_curfew     speaker: VASILE     "And this is what it bought us. A curfew nobody can enforce and a regime that shoots its own order."
scene: title_card         speaker: ""         "MISSION 4\nTHE AFTERMATH"
```

## Ending Cutscene Shot-List

```
scene: m4_arrest_screen     speaker: VASILE   "It's done. He's in a cell by his own guard's hands."
scene: m4_maru_silhouette   speaker: MARU     "And the man on the screen smiles. The country is cheering the wrong name tonight."
scene: m4_roof_dawn         speaker: BIRIBEL  "Nobody asked us to do this. First time in my life - that's how it's done right."
scene: m4_roof_dawn         speaker: BIRIBEL  "There's a border that doesn't care about my name. I'm not taking it. Not yet."
scene: title_card           speaker: ""       "THE AFTERMATH"
```

---

## What This Resolves

- The Balaceanu vendetta — ended by irrelevance, not by a bullet (per the M3
  plot doc's stated theme).
- Maru's first physical appearance and the KRAP→MAG remnants alliance.
- Volkov's fate (fled to Regatul Kim Kim; off the board).
- Biribel's frame change from "mission assigned" to "a war of his own choosing"
  — and him choosing to stay.

## What It Leaves Open (For M5+)

- **Retardovici on the throne** — the cape who ate his handler is now the face
  of a nation that cheered him. That is the read on the night; the reveal M5
  inherits is that the cape was holding the strings.
- **What "staying and fighting" means** with no KRAP, no orders, and one
  transmitter.

---

## Technical Notes

- **Build strategy:** incremental slices W1–W6; every slice gated by
  `python tools/smoke_test.py` (`SMOKE TEST: OK`) + `python -m compileall -q src tools`.
- **Package:** `src/missions/m4/` — re-export facade (`__init__.py`, PEP 562
  `__getattr__` + `_LIVE_STATE`) over `meta → maps → world → flow → systems → draw`.
- **Maps:** procedural generators (`_generate_m4_map`, `_generate_station_map`),
  M3 tile grammar (`C/g/./D/B/O/L`), validated sealed border + spawn-on-floor in
  the boot check (MapBuilder.validate() is not used by the M2/M3 style).
- **Cross-package rule:** zero imports from `missions.m3` internals. Enemy role
  tuning (`M4_ROLE_TUNING`), typewriter cadence (`_TYPE_SPEED`), and the sniper
  laser telegraph idiom are **ported with `# ported from` comments**, mirroring
  how M3 ported M2's sniper idiom.
- **Global-state rule:** one-owner mutable globals; stage flags live on `STATE`
  (`mission4_stage`, `m4_*`); the liaison dialogue state and siege clocks are
  single-owner module globals mutated in place, read live (`_m4_flow._m4_dlg`).
- **Campaign chain:** `game_core` routes MISSION4 before MISSION3; `save_system`
  records `MISSION_4`; `app.py` wires the intro/ending cutscenes, `--dev-mission4`,
  slot-select resume (`MISSION_3 → M4`, `progress=="m4" → checkpoint`), and the
  FULL CAMPAIGN COMPLETE notice.
- **New cutscene art:** `src/cutscenes/m4aftermath.py` (`_draw_m4_city_curfew`,
  `_draw_m4_arrest_screen`, `_draw_m4_maru_silhouette`, `_draw_m4_roof_dawn`),
  dispatched from `cutscenes/engine.py::draw_cutscene_scene` and re-exported from
  `cutscenes/__init__.py` — following the `m3ending.py` per-scene `surface, t` idiom.
- **2.5D:** the street and station draw through the shared top-down host
  (`game/topdown3d.py`, `missions/m4/draw3d.py`); `ACA_TD_2D=1` or any
  renderer error falls back to the 2D view, whose static layer is baked in
  `assets/baked/m4` (rebake with `python tools/ae_bake.py --pack m4` after a
  map or static-draw change).
- **Overhaul modules:** `escort.py` (Vasile, supply, downs), `fortify.py`
  (sites, barricades, holds), `siege.py` (wave director, flow field to the
  rack, enemy brains, snapshots), `apc.py` (wave 5 ram). Design in
  `docs/M4_OVERHAUL_PLAN.md`.
- **Verification:** smoke checks `mission4_boot_and_walk`, `mission4_layout`,
  `mission4_stage_transitions`, `mission4_checkpoint_routes`,
  `mission4_escort_downs`, `mission4_barricades`, `mission4_wave_director`,
  `mission4_cinematic_arrest`, `mission4_ending_shots_render`,
  `mission4_campaign_chain`. Review shots: `python tools/m4_td3d_shots.py`.
