# CALL OF ACARISTAN — A DOCUMENTARY

*An unauthorized, code-deep dive into a tactical stealth-shooter built in Pygame by a single obsessive hand. This is the story of the game, told through its own source.*

> **Snapshot note (2026-10-20):** this piece describes an early build of the
> campaign (three missions, single-file mission modules). The game now ships
> six missions (`src/missions/m1`…`m6`); M7/M8 are planned. The story canon was
> re-synced with the code in `docs/FIXES_STORIES.md` — the six-year Vostral
> timeline below is the current one.

---

## ACT I — THE GAME YOU CAN'T QUITE CATEGORIZE

Open `dist/Call of Acaristan.exe` and you are dropped into a 1000×700 logical frame — a top-down, neon-and-rain tactical shooter with the soul of a spy thriller and the body of a 90s arcade gunfight. It calls itself **"Call of Acaristan"**, and it is a three-mission campaign about a framed operative, a corrupt Prime Minister, and a single buried rumor that could topple a government.

It is, by any honest accounting, *enormous* for a Pygame project:

- ~40 Python modules, several exceeding 100,000 characters (`mission2.py` is **580 KB**, `mission3.py` is **528 KB**).
- A full finite-state-machine engine, a centralized state singleton, procedural art caching, a hand-written FM-synthesized audio engine, a level editor, a settings suite, a save system, and a *multiplayer server browser that connects to no servers at all*.
- A build pipeline that compiles the whole thing into a single Windows executable via PyInstaller.

This is not a jam game. This is a *project*.

---

## ACT II — THE WORLD OF ACARISTAN

Acaristan is, in the game's own words (*cutscenes.py:5703*), *"a nation in name only. The ground beneath it is worth more than the people standing on it."* It is a fictional post-Soviet-flavored state run by leverage, contracts, and black sites.

The factions (defined by faction colors in `config.py`):

| Faction | Meaning | Role |
|---|---|---|
| **KRAP** | The protagonist's military/intelligence force | Biribel's side; "off-book" resistance |
| **IPA** | Interior Protection Agency | The regime's domestic enforcers; the visible enemy |
| **MAG** | Militia | Scapegoats; bomb IPA checkpoints out of personal grievance |
| **CIV** | Civilians | Collateral, flavor, occasional payoff |

The political engine is a decree-laced timeline: **Y-6** (Balaceanu becomes PM, and the Vostral is born in the ranks), **Y-12** (the National Stability Decree — the legal cover for domestic black sites), and **Y-1** — *The Vostral reaches the press*.

---

## ACT III — THE PROTAGONIST AND THE VILLAIN

**Biribel** (`C_BIRIBEL = (200, 200, 200)`, a grey ghost of a man) is a KRAP field operator. He is good at his job, and that is precisely the problem.

**Prime Minister Balaceanu** is the antagonist — and the genius of the writing is *why* he hates Biribel. The rumor is **six years old**: Biribel said it out loud in the ranks at **Y-6** (he was a serving soldier, years before KRAP existed), and it reached the civilian press at **Y-1**, where it became a capital charge: that Balaceanu's entire decorated military career — his medals, his war stories, his "tough man of Acaristan" brand — is **fabricated**. Balaceanu *cannot* deny it without a trial that forces him to produce his classified service record; he *cannot* court-martial Biribel without that same trial. So he does the only thing left: he engineers Biribel's death in action, one "high-risk stabilization assignment" at a time.

The Volkov handoff in Mission 1? That was the latest such assignment. The whole trilogy is Balaceanu trying to kill a man he legally cannot touch.

**Sebastian Volkov** is the wildcard — an IPA affiliate who is "tracking" Biribel, escapes every mission, throws Biribel a radio mid-breakout, and may or may not be on anyone's side. **Captain Vasile** is the KRAP handler, the voice on the radio who keeps coming back "under fire." **Maru** (revealed in M3) is a former IPA archivist who faked their own death rather than forge seizure documents — and who *actually forged Balaceanu's record*. The trilogy's buried root.

---

## ACT IV — THE THREE MISSIONS

### Mission 1 — "Black Notebook" (WAREHOUSE RAID)
Biribel infiltrates a warehouse to recover a **black notebook** from courier S. Volkov. Top-down stealth: silent movement, sight cones, a keycard gate, a safe (code **742**), truck hot-wiring minigame, and a Volkov who *escapes* rather than dies — leaving Biribel with the notebook and "questions remain." Outcome string (`mission.py:90`): *"Target escaped · Notebook recovered · Questions remain."* A clean/stealth run is tracked and rewarded (`STATE.stealth_clean`).

### Mission 2 — "Quiet on Route 12" (THE FRAME-UP)
The masterpiece of the trilogy's plotting. Biribel investigates a *staged* massacre on Route 12 — evidence markers to inspect, a fuel tanker, a control building with green evidence terminals. Then a **sniper kill-box**, a KRAP patrol to hold the road, a hidden **remote-detonated tanker blast** (Vasile loses contact in the explosion), and a solo "comms blackout." The twist: Route 12 was a **false-flag** by Balaceanu's government to pin a massacre on Biribel personally. The mission ends with IPA booting the door and **dragging Biribel away** — captured, not killed.

### Mission 3 — "The Vostral" (THE VENDETTA, FACE TO FACE)
Three days later, Biribel wakes **disarmed** in an IPA black-site cell — the Stabilization Center, a repurposed Y-12 courthouse. This is the dialogue-heavy, craft-driven finale:
- **Interrogation** under Balaceanu's monitor.
- **Breakout**: Biribel must *break a chair*, grab a **chair leg**, and **whittle it into a shiv** at a drain grate (a mandatory mouse-drag crafting minigame — 8 strokes, Volkov holding the door).
- **KRAP Re-Contact**, **The Archives** (steal the Vostral file — the mission's "notebook"), **The Kill Order** (Balaceanu's disciplined sweep), and the **Live Broadcast** climax: get the file onto the uplink before Balaceanu finishes his 22:00 address pinning Route 12 on Biribel *by name, on camera*.

The hunter becomes the exposé.

---

## ACT V — THE MACHINERY (HOW IT WORKS)

### The Engine: Strict FSM + One State to Rule Them All
`fsm.py` enforces a clean **Finite State Machine**: every screen (MENU, GAME, CUTSCENE, PAUSED, DEATH, SETTINGS…) is a `GameState` with `enter/exit/handle_event/update/render`. Transitions are either instant (`transition`) or fades (`trigger_transition` — fade-out → swap → fade-in at alpha 12/frame).

All mutable game data lives on a single singleton, `STATE` (`state.py` — ~300 lines of `reset()`). Every submodule does `from state import STATE; STATE.player.hp -= 10`. This is the project's "AEGIS standard" — a reaction to an earlier era of scattered module-level globals.

`game_core.py` is a **proxy facade**: it routes `gc.start_mission()` / `gc.game_update()` to Mission 1/2/3 based on `STATE.active_mission`, and its `_GameCoreModule` proxy intercepts attribute access so legacy code keeps working. `mission2.py` and `mission3.py` are so large they were split from a monolithic `game_source.py` (PDFs of which litter the repo).

### Combat & Player
- **Weapons** (`weapons.py`): pistol, an OS-12 assault rifle (unlocked in M2), a K-9 suppressed SMG (M3 armory reward), melee, and **molotov cocktails** with real fire-zone damage modeling (tuned so a grunt dies in ~1.8s at fire center).
- **Player** (`player.py`): movement, weapon rig, breathing/blink, recoil, and **AEGIS i-frames** — 0.75s invincibility after a hit with a 60ms sprite-blink so you *see* you were hit and *see* you're safe.
- **Enemy AI** (`enemy_ai.py`): real **A\*** pathfinding on a cached walk-grid, sight cones, hearing radius, waypoint navigation, stuck-timeout recovery. Enemies have detect/attack ranges, fire cooldowns, and alert states.

### Feel & Juice
- **Hit-stop** freeze on impact (`STATE.hit_stop_timer`), **screen shake**, **muzzle flashes**, **casings**, **blood decals**, **death animation** (`death_anim.py` — a 2s cinematic fall with camera tilt, body slide, blood pool growth, weapon eject, and a **tinnitus overlay**).
- **Post-processing**: brightness, scanlines, film grain, all toggleable.
- **Cutscenes** (`cutscenes.py`, 274 KB): fully procedural, code-drawn cinematic shots — TV studios, streets, safehouses, silhouettes booting doors, Volkov throwing a radio Biribel catches in frame.

### Audio
`audio.py` is a self-contained **FM-synthesized** sound engine (no sample assets for most effects) — shell casings, gunshots, alarms, radio static — with master/music/SFX volume buses and focus-loss muting.

### The "Multiplayer" Easter Egg
The menu has a **server browser** (`update_server_browser_animation`) with live-fluctuating pings and player counts, a chat feed full of in-character banter ("RushB_Acaristan: RUSH B CYKA", "Volkov_Real: i am literally him", an admin muting "BiribelMain (toxicity)"), and a "connecting…" state that *always* resolves to **"kicked."** There is no netcode. It is a perfect, melancholic joke: the lone operative, barred even from the fantasy of company.

---

## ACT VI — THE SECRETS

### The 666 Safe (a small horror show)
In Mission 1, the safe keypad accepts **742** to open. But type **666** and `_trigger_safe_666_easter_egg()` ignites one of the most unhinged things in the codebase (`ui_hud.py`):
- A demonic face drawn from randomized "crack" and "teeth" RNG seeded on 666.
- A demon **noise** played from bundled audio.
- **OS-window tampering**: the real window caption mutates to `"Call of Acaristan - 666"` then `"FATAL ERROR 0x00000666"`, and the window *jitters its position and opacity*.
- A fake crash screen, then `raise SystemExit("FATAL ERROR 0x00000666")`.

It doesn't just break the fourth wall. It *kicks it out the window and follows.*

### The Black Ledger
Mission 3 hides a **Black Ledger** easter egg — a supernatural punishment entity that, when triggered, replaces the death screen with a custom **"BLACK LEDGER"** composition and its own reveal/control flow. The objective literally becomes *"SURVIVE THE BLACK LEDGER"* / *"THE LEDGER COLLECTS."*

### Dev Backdoors
`acaristan.py` parses `--dev-mission1/2/3`, `--dev-safe`, `--dev-mission2-sniper`, etc., jumping straight into missions, cutscenes, or the safe keypad for testing. Debug jumps to exfil exist per mission.

---

## ACT VII — THE ARCHITECTURE AS CHARACTER

You can read the *personality* of the developer in the code:

- **Relentless self-documentation.** Nearly every file opens with `---` banners and long docstrings explaining not just *what* but *why* — including confessions of past bugs: the missing `from state import STATE` that caused a `NameError` on first melee (`player.py:18`), the obsolete FSM monkey-patch that would `AttributeError` on first transition (`acaristan.py:34-44`), the molotov double-damage math that "would add up to an instant kill."
- **Naming discipline as doctrine.** "AEGIS standards" recur: delta-time everywhere, `STATE` over globals, i-frames, max-clamp helpers for `screen_shake`. This is someone who got burned by their own magic numbers and built guardrails.
- **Procedural everything.** Art is drawn in code (`art_cache.py`), sound is synthesized, cutscenes are composed frame-by-frame. Almost no external assets — a defiant, old-school craft ethos.
- **The split-module saga.** `game_source.py` was too big; it was carved into `mission.py` / `mission2.py` / `mission3.py`, with `game_core.py` as the glue. Whole PDFs of the old monolith sit in `PDFs/` and `TXTs/` like archaeological layers.

---

## ACT VIII — WHAT IT ALL MEANS

*Call of Acaristan* is, at its core, a story about **a man the state cannot legally kill, so it tries to kill illegally — and the one rumor that survives every attempt.** Biribel is never the strongest gun in the room; he wins by being the one piece Balaceanu can't put on trial. The Vostral (the fabricated-hero rumor) is the only weapon that actually hurts the villain, and the entire third mission is built to let the player *use* it.

And underneath the tactical shooting and the rain and the radio static, there's the developer's own signature: a lone builder, routing everything through one `STATE`, drawing every pixel by hand, synthesizing every sound, and hiding a demon in the safe that will crash your window if you type the wrong number. The multiplayer screen that always kicks you? That's the thesis. **In Acaristan, you are always alone — and the lobby was never going to let you in.**

---

*End of documentary. Built from the source of `E:\Code\Call of Acaristan\First try`.*
