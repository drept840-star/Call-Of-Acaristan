# Mission 1 "Black Notebook" - rework plan

Branch `m1/rework` (worktree `E:/Code/Call of Acaristan/m1-rework`). Point-in-time plan; the shipped game wins on disagreement.

Scope (approved 2026-10-26): street approach + bigger map, real stealth, Volkov standoff, readable leaf, dialogue files + VO rows, breach as three waves with roles, a named miniboss, exfil pressure, lighting/ambience/music, painter peel-off, escape cutscene as a timeline, B-004, dead code.

## Canon constraints (do not break)
- Day 0. Biribel is sent by Vasile to take Volkov alive; Volkov MUST escape (his dry copy of the leaf matters in M6). `VO_094` "Volkov escaped! Get that notebook and get out." stays the canonical radio beat.
- The loose leaf is water-damaged: in M1 only "ROUTE 12" and a smeared relay code are legible. Never show the full schedule or Vasile's name. Registry FT-7742..7745 and IPA #8841-8844 may be shown.
- Vasile pockets the notebook unread at the end (`VO_198`, caption-only). Keep it.
- The game already opens with `core.cutscene1` (ocean) and `core.cutscene2` (van briefing, `VO_025`..`VO_032`). The street approach is the playable arrival after the van; do not add a second briefing cutscene. A 6-8 s in-engine "drop-off" timeline (van pulls away, rain, Vasile radio check) bridges van to street.
- New spoken lines: `VO_xxx` row + `KNOWN_MISSING_AUDIO`, never in `VOICE_ORDER` (AGENTS.md:53). Keep the blocky character look; top-down art uses art-pack tiles, dark ambient, hard edges, no soft blobs or noise.

## (a) Key choices
1. Stealth model. Options: port M6 `stealth.py` beams (built for 3D lamps, exposure latch 0.4 s); extend `enemy_ai` cone test with a per-enemy suspicion meter; keep binary detection with longer timers. Pick: per-enemy suspicion meter in a new `missions/m1/stealth.py`, fed by the existing `enemy_ai` cone (+-45 deg, 350 px, LOS) and light level, with an M6-style "radio call" delay before the alarm latches. Reuses tuned AI, gives the player a window to fix a mistake.
2. Where the street goes. Options: west wing; north band; south past exfil. Pick: a 10-row north band. The player now enters the stockroom from outside, the old north spawn becomes the natural first room, and the exfil corridor stays the finale. Cost: every row index shifts +10; door rows become named constants.
3. Escape cutscene. Options: keep frame-counted state; timeline shots with M1 scene painters. Pick: `m1.escape.timeline.json` played by `CutscenePlayer`; the three painters in `m1/draw.py` (dashboard, close-up, truck) become named scenes. Audio cues move onto shots if the timeline schema supports per-shot sfx; otherwise keep a small cue table keyed by shot index, not by frame.
4. Music. `assets/music/` has no mission tracks and there are no rain recordings; ambience is synthesised in `core/ambience.py` (M1 already in `RAIN_MISSIONS`). Pick: wire M1 gameplay to the synth beds now (rain outdoors/indoors, elec hum by the gate console); add a two-layer music hook that plays `assets/music/m1_infiltrate.ogg` / `m1_combat.ogg` only if the files exist. The user supplies the tracks.

## (b) Map (28 x 33, 64 px)
Rows 0-9 are new. Rows 10-32 are the old map shifted +10 (old row r -> r+10). Coordinates are authoritative; the grid is a guide. Implementer maps the symbolic chars below onto existing tile chars or adds legend entries in `mapbuilder`/art pack consistently.

```
row  0 ############################   # outer wall (street boundary)
row  1 #P.........................#   . street (wet asphalt, art-pack tile)
row  2 #.....L........L...........#   L lamp post (decor, light source)
row  3 #.......TTT................#   T parked truck (blocks move + sight)
row  4 #.......TTT........e.......#   e street patrol
row  5 #....r.....................#   r rubble pile (bricks pickup)
row  6 #.....................TTTT.#   delivery van (cover)
row  7 #ffffff.ffffffffffffff.ffff#   f chain fence (blocks move, NOT sight)
row  8 #......................e.e.#   shutter guards (smoking)
row  9 #...........r..........F...#   F shutter floodlight
row 10 CCCdCCCCCCCCCCCCCCCCCCSSSCCC   d side door (dark), S loading shutter (3 wide)
row 11.. old rows 1..22 shifted +10
```

New / shifted positions:
- Player spawn P (1,1). Old P(3,2) removed.
- Street enemies: patrol e (19,4) route (19,4)->(10,5)->(4,8)->(19,8) via fence gaps; shutter guards (22,8), (24,8) stationary, facing each other (side-on to the apron) until disturbed.
- Fence gaps: (7,7) west, (22,7) east.
- Entries: side door (3,10) unlit, quiet route; shutter (22..24,10) lit by F (23,9).
- Rubble/bricks: (5,5), (12,9), inside (2,12). Each pile gives 2 bricks, cap 3.
- Lamps: L (6,2), (15,2) warm sodium; F (23,9) cone pointing north over the apron. Interior `_M1_LAMPS` shift +10 rows; `wh_e` and `dk_a` flicker.
- Old spawns shifted: E (22,15),(7,17),(16,17),(11,21),(19,22),(5,23),(15,23); K (10,24); V (15,27); N (15,28); X (22,31); miniboss (10,27).
- Door rows: `M1_STOCK_DOOR_ROW=20` (col 8), `M1_GATE_ROW=25` (col 14), `M1_BAY_ROW=29` (cols 14-16), `M1_STREET_ROW=10`. `m1/main.py` `is_bay`/`is_gate` read these constants; nothing else hardcodes rows.
- Level JSON `m1.warehouse.level.json`: regenerate floor rows + spawn objects from the builder; add `lights[]` for the new lamps and `triggers[]` for: `street_exit` (rows 10-11), `volkov_standoff` (rect cols 11-19, rows 26-28), `exfil_van` (rect cols 18-26, rows 30-31).

## (c) Beat sheet and lines
IDs: next free after the current max VO row. Placeholder ids below are `VO_M1_nn`; assign real numbers in order. All new rows go to `KNOWN_MISSING_AUDIO`. Inline lines that move unchanged keep their text exactly.

0. Drop-off timeline `m1.dropoff` (in-engine, ~7 s): van tail-lights leave east, rain.
   - VASILE (radio): "Channel 4. You're on the street. / Two at the shutter, one walking the fence." (VO_M1_01)
   - BIRIBEL: "Side door's dark." (VO_M1_02)
   - VASILE: "Then use it. Volkov's inside with the book." (VO_M1_03)
1. First fence gap reached, unseen: no line (silence is the reward).
2. Brick tutorial (first pickup): hint text only, "Q - throw brick (noise)".
3. Takedown tutorial (first enemy within 2 tiles, from behind, unaware): hint text "E - takedown".
4. Enemy suspicious (first time): ENEMY "Hm? Who's there?" (VO_M1_04, bark); searching: ENEMY "Check the corner." (VO_M1_05, bark).
5. Alarm latched: existing pair stays (`VOLKOV` "Read it before you hand it over!" moves to beat 7 on the quiet route; on the loud route it stays here), `VASILE` "Biribel, they spotted you! Alarm is active!".
6. Inside, quiet: VASILE "Clean so far. Keep it that way." (VO_M1_06), on entering row 11.
7. Volkov standoff (quiet route only; trigger `volkov_standoff`, alarm not raised). Gameplay freezes, camera eases to frame both, letterbox 24 px, ~9 s:
   - VOLKOV: "Easy. I'm a clerk. I count crates." (VO_M1_07)
   - BIRIBEL: "Then count to three and walk with me." (VO_M1_08)
   - VOLKOV: "Read it before you hand it over! / The loose page. Read it." (existing inline line + new second beat VO_M1_09)
   - commander K spots them (scripted) -> alarm; Volkov runs out the bay door (existing 90-frame run), VASILE `VO_094`.
   Loud route: no freeze; when the alarm fires Volkov shouts the existing line and runs; `VO_094` plays when he exits.
8. Notebook keypad (code 742, hints unchanged), then NOTEBOOK_INSPECT shows: registry page (FT-7742..7745, IPA #8841-8844) and the loose leaf rendered water-damaged: "ROUTE 12" legible, a smeared relay code "V-?7", the rest bled ink. BIRIBEL: "Half of it's gone. Route twelve." (VO_M1_10)
9. Breach (existing 6 s staged breach), then waves (section e). CIOCAN entrance: "The clerk's new friend? Let's see." (VO_M1_11). Charge windup bark: "Hah!" (caption only, no row).
10. Exfil van arrives (trigger `exfil_van`, first time): VASILE "Company on the east road. Move." (VO_M1_12).
11. Hotwire: existing tutorial lines. Smoke reaches the truck at 25 s: BIRIBEL "Come on... break." reuse `VO_045` if it fits the take, else new row "Come on. Come on." (VO_M1_13).
12. Escape timeline `m1.escape` (port of the current 1080-frame cut, same shots and subtitles, `VO_198` at the end).

All M1 gameplay lines live in `src/game/content/dialogue/m1.radio.dlg.json` (radio/barks keyed by beat id) and `m1.standoff.dlg.json`; loaded via `game/dialogues.py` with the inline strings as `legacy` fallback.

## (d) Stealth state machine (`missions/m1/stealth.py`)
Per enemy `suspicion` 0..1, states: UNAWARE (<0.35), SUSPICIOUS (0.35-<1.0), SEARCHING (1.0, local), ALARM (global latch).
- Sight test: existing `enemy_ai` cone (+-45 deg calm / +-80 alerted, `ENEMY_DETECT_RANGE` 350 px, LOS through `T`/walls blocked, fences `f` not blocking).
- Fill per second while seen: `base 1.25 * dist_k * light_k * move_k`. `dist_k` = 1.6 at <=120 px falling linearly to 0.4 at 350 px. `light_k` = 1.5 if the player stands in a lamp radius, 0.55 in dark. `move_k` = 1.3 sprinting, 1.0 walking, 0.7 still. Close + lit + walking fills in ~0.35 s; far + dark + still ~3.6 s.
- Decay 0.25/s when not seen, after a 1.5 s hold.
- SUSPICIOUS: stop patrol, turn to the last seen point, walk there at speed 1.2 after 0.8 s. Bark VO_M1_04 once per enemy.
- SEARCHING (1.0): existing `SEARCH` state for 6 s around the last seen point, `alerted=True` for that enemy only. Starts a 2.0 s radio call (small red "!" over the head). If the enemy dies or loses all sight for the whole 2.0 s, no alarm. Else `trigger_alarm_early()` (existing).
- Noise: unsuppressed pistol shot -> existing `enemy_hear_shot` (300 px) -> those enemies go straight to SEARCHING (radio call still applies). Brick impact -> enemies within 250 px with LOS-or-wall-thin path go SUSPICIOUS and walk to the impact (6 s), no radio call.
- Bodies: an enemy that sees a corpse within 250 px -> SEARCHING.
- Takedown: melee input on an enemy in UNAWARE/SUSPICIOUS state, within `MELEE_RANGE` 52 px, with the player inside the enemy's rear 120 deg arc -> instant silent kill (no hear event, 0.4 s lock, corpse). Otherwise normal `resolve_melee`.
- HUD: per-enemy arc meter over the head (hard-edged 2 px pixel arc, white -> amber -> red), no screen-wide overlay.
- Notebook: drop the "no enemy within 300 px" rule; keypad entry is allowed whenever the player is not in an enemy's sight.
- `quiet_entry`: true while no alarm has latched. Pays out: wave 3 skipped, wave sizes in section e, VASILE VO_M1_06 inside, standoff beat.

## (e) Breach and exfil
`missions/m1/roles.py`: `@component M1Role(kind: str)` with kinds `rusher` (speed 2.6, no cover, closes to 120 px), `cover` (existing cover sweeps, holds 200-280 px), `flanker` (paths to a point 90 deg around the player at 260 px, then CHASE). Waves spawn with hp 115 (unchanged).

| wave | trigger | spawn | count loud / quiet | roles |
|---|---|---|---|---|
| 1 | breach flash | bay row 30-31 | 6 / 5 | 2 rusher, 3 cover, 1 flanker |
| 2 | W1 <= 2 alive or +14 s | gate row 25 (+ CIOCAN) | 4 / 4 | 1 rusher, 2 cover, 1 flanker |
| 3 | W2 <= 1 alive or +14 s | commander rows 21-23 | 4 / 0 | 2 cover, 2 flanker |

CIOCAN (old hardcoded miniboss, hp 400, moves from (10,27) to arrive with wave 2): shoulder charge every 7-9 s when the player is 160-420 px in LOS. Windup 0.8 s (stops, body flashes red on alternate 4-frame blinks, bark), then a straight dash 6 tiles at speed 9; hit player = 30 damage + knockback; hits a wall = stunned 1.5 s taking 2x damage. Drops a bandage and 2 mags.

Exfil: when the player first enters `exfil_van`, a van stops at the corridor east end (27,31) and drops 3 enemies (1 rusher, 2 cover) using `escape_reinforcement_timer/count` (spawn one every 40 frames). Hotwire stays modal but the world keeps updating while the panel is open; taking damage closes the panel. Smoke: fire zones grow from the bay door row 29 west/east one tile per 3 s once wave 1 spawns; at 25 s after hotwire first opens the truck tile area deals 4 hp/s smoke damage.

## (f) Work packages (land in this order, one writer at a time)
Every WP ends with: `python -m compileall -q src` clean and `python tools/smoke_test.py` -> `SMOKE TEST: OK`, then a commit on `m1/rework`. LF line endings (`git ls-files --eol` on touched files).

WP0 - dead code + B-004
- Delete `core/interactions.py` `trigger_mag_ambush()` (no callers). Keep `escape_reinforcement_timer/count` (used in WP7).
- `m1/update.py game_update`: return right after the death transition when the player is dead, so the headless sim stops mutating.
- Re-record the replay with a gentler stream: `python tools/ae_replay.py record --set baseline_v2 --only m1`, then `check`. Note in `docs/engine/BUGS.md` B-004.

WP1 - painter peel-off (B-034, P6-M7), M5 recipe
- `m1/draw.py`: split `_game_draw_inner` into submits: static bake `layers.define("m1.tiles", ...)` -> `StaticLayerDraw` on `FLOOR`; decor on `DECOR_STATIC`; actors stay a `CustomDraw` on `ENTITIES` for now (allowed); bullets/particles/casings/fire via `game/render/adapters.py` on `FX_WORLD`; lighting composite on `LIGHTING`; HUD, objective panel, dialogue, hotwire panel, notebook inspect as `UiPassDraw` on `UI` (names `m1.hud`, `m1.dialogue`, `m1.hotwire`, `m1.inspect`).
- `core/game_core.py:376-391`: M1 uses a submit path like M5 instead of the whole-painter `_mission_draw`.
- Checks: `python tools/ae_golden.py verify --set baseline_v0 --only m1` must stay pixel-equal (this WP changes structure, not look). Update B-034 in BUGS.md (M1 done).

WP2 - escape cutscene as timeline
- New `src/game/content/timelines/m1.escape.timeline.json` with shots for dashboard (<135), close-up (<300), truck (<500), and the rest of the current cut, same subtitles and `VO_198`.
- Scene painters registered from `m1/draw.py`; `app.py` `_EscapeCutsceneState` replaced by `start_cutscene(m1 escape shots, after_state="MISSION_COMPLETE")`; remove `escape_cutscene_timer` / `ESCAPE_CUTSCENE_DURATION` if nothing else reads them (smoke `volkov_foreshadowing` reads escape timers: update the check).
- Checks: smoke; render the cut at t25/50/75 against the old frames (side by side, eyeball by main model).

WP3 - dialogue files + VO rows
- Move every inline M1 line (inventory in `docs/MISSION1_REWORK_PLAN.md` beat sheet + current inline list in `core/interactions.py`, `m1/update.py`, `m1/main.py`) into `m1.radio.dlg.json`, with inline as fallback. Add the new rows from section c. Smoke `voice_manifest_resolves`, `cutscene_no_speaker_headers`, `radio_gated_by_cutscenes`.

WP4 - map growth + street
- `m1/map.py`: new band rows 0-9, shift spawns, door-row constants, `validate()` returns `[]`. Regenerate `m1.warehouse.level.json`. Update every row consumer (`m1/main.py` door detection, patrol routes, `_M1_LAMPS`, desk clues, console (13,25), molotov tutorial text positions, `update.py` breach spawn rows, `EXFIL_POS`, smoke checks with hardcoded tiles, `tools/ae_golden.py` m1 `_cam_at` positions).
- Street art: art-pack floor tile for wet asphalt, fence, truck/van blocks in the house style (check `assets/art` and `tools/sprites/` for existing street/vehicle tiles; M5 quarter uses street tiles - reuse first). Static bake covers the street.
- Rain over the street band (existing rain art `rain_0..5`), interior keeps `rain_inside`.
- Checks: smoke; `gameplay_camera_unified`; walk check via `--dev-m1` loop record.

WP5 - stealth
- `missions/m1/stealth.py` per section d; hook into `m1/update.py` before `trigger_alarm_early`; takedown in the melee path; bricks (pickup piles, `Q` throw reusing the bottle arc in `entities/weapons.py` with no fire, impact noise). HUD meters in `m1.hud`. Remove the 300 px notebook rule. Smoke: add `m1_stealth_suspicion` (fill/decay numbers), `m1_takedown_silent`, `m1_brick_noise`.

WP6 - Volkov standoff + leaf
- Standoff beat from section c as a short in-engine sequence (freeze update, camera ease, letterbox, dialogue file `m1.standoff`), then scripted K alarm and Volkov's existing run. Leaf rendering in NOTEBOOK_INSPECT (pixel font, ink-bleed done with hard 2-tone pixel blots, not blur). Smoke: `volkov_foreshadowing` still green; add `m1_volkov_escapes_both_routes`.

WP7 - waves, roles, CIOCAN, exfil
- `missions/m1/roles.py`, wave director in `m1/update.py`, CIOCAN charge, exfil van + smoke, hotwire non-pausing world. Smoke: `m1_waves_quiet_vs_loud`, `m1_ciocan_charge_stun`, `m1_hotwire_damage_closes`.

WP8 - lighting, ambience, music hooks
- Street lamps, shutter flood cone, two flickering interior lamps via `LightBuffer.flicker`, bay-door rain cone; `_set_ambience` beds per band (street: rain + wind_gust; interior: rain_inside + elec_hum near console + drip_echo); music hook (files optional) with alarm crossfade over 1.5 s.
- Checks: smoke; golden stills reviewed by the main model.

WP9 - re-bake and docs
- `python tools/ae_golden.py capture --set baseline_v0 --only m1`, `python tools/ae_replay.py record --set baseline_v2 --only m1`, `python tools/ae_loop.py record --seg m1`; then `python tools/ae_ci.py` (known unrelated reds: mission4_stage_transitions, mission4_cinematic_arrest, mission5_shadow_finale, mission5_harbour_art).
- `docs/LORE.md` M1 section (street, standoff, CIOCAN, leaf legibility), `docs/engine/BUGS.md` (B-004, B-034 M1), `.wolf/STATUS.md`.

## (g) Risks
- Row shift is the widest change (WP4): any missed hardcoded row breaks doors, the breach or the exfil. Grep for every numeric row/col in m1 and `core/interactions.py` before editing; smoke covers only some.
- Peel-off (WP1) must stay pixel-equal; if not, stop and fix before moving on, or every later golden diff is ambiguous.
- `core/interactions.py` is shared with other missions; M1-only changes stay behind the M1 mission check.
- The smoke `_GameState_` AST extraction in `app.py`: keep helpers on the class, not module level.
- Music depends on files the user must supply; the hook is silent without them.
