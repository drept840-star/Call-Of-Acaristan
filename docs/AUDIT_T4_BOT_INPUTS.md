# AUDIT T4 — Bot Inputs & Autonomous Controller (READ-ONLY)

Date: 2026-09-26 · Scope: exact source code that drives the player bot during automated/headless runs · No source files edited.

## TL;DR

There is **no learning / random-exploration bot**. All headless movement comes from **hardcoded deterministic waypoint lists** injected as fake keyboard state, plus `STATE.player.angle` set directly. Same script + same spawn + same 60 Hz tick = same path every run. The only randomness is **±4 px aim jitter** (`src/tools/trailer_bot.py:146`) and footstep-timer jitter — neither affects routing.

Two independent bot families exist (different entry points, same trick):

| # | Driver | Owner file | Injection method |
|---|---|---|---|
| A | Trailer-bot (interactive capture) | `src/tools/trailer_bot.py` | `tick_bot()` returns `_FakeKeys(dx,dy)` + sets `p.angle` directly; hooked in `src/app.py` GAME.update |
| B | Headless tour Routers (offline MP4 / audits) | `tools/render_trailer.py`, `tools/render_trailer_v2.py`, `render_ko_video.py`, `src/tools/ko_playability_audit.py` | `Router.step()` sets bits on a shared `KEYS.down` set (`K_w/a/s/d`); calls `gc.game_update(KEYS)` directly |

No `simulate_tick`, `bot_target`, or `player.move` script engine exists by those names. `player.move` is only the **terminal sink** (`src/entities/player.py:100`), never the planner.

---

## 1. Family A — `src/tools/trailer_bot.py` (deterministic operator driver)

Full source: `src/tools/trailer_bot.py:1-201`. Design statement is in its own docstring (`:9-12`): *"the bot does NOT pathfind."*

- **State owner:** `_BOT_active, _BOT_act, _BOT_wp_idx, _BOT_hold, _BOT_waypoints, _BOT_fire_cd` (`:23-28`). Per AGENTS.md rule, consumers use `import tools.trailer_bot as _bot` + `_bot.NAME`.
- **Scripts (the "same path"):** `_build_script(act)` (`:57-106`) returns a fixed list of `(move_x, move_y, aim_x, aim_y, action)` tuples in 64-px tile-center coords (`_tc64`, `:53-54`). Acts: `act1` (7 waypoints), `act2_killbox` (5), `act2_evidence` (3), `act3_breakout` (3), `act3_relay` (5). Only two entries are patched at runtime (`_patch_runtime_targets`, `:109-118`: M1 notebook/exfil from `STATE.NOTEBOOK_POS` / `STATE.EXFIL_POS`); everything else is literal.
- **Per-tick logic (`tick_bot`, `:121-162`):**
  1. Aim: instant snap `p.angle = atan2(...)` with `random.uniform(-4, 4)` px jitter (`:145-148`). No lerp, no search.
  2. Movement: vector to current waypoint → if `dist < 26`, fire `_do_action` and advance `_BOT_wp_idx` (clamped, never wraps: `min(idx+1, len-1)`); else return `_FakeKeys(dx, dy)` (`:149-162`).
  3. Combat actions go through the **real pipeline** (`_do_action`, `:165-183`): `weapons.handle_shoot / handle_throw_bottle / handle_melee / start_reload / switch_weapon`, `game_core.handle_interact`. Constants: `TAP_GAP = 9`, `REACQUIRE = 18` (`:30-31`).
- **`_FakeKeys` (`:186-201`):** duck-types `pygame.key.get_pressed()`. Deadzone ±8 px: `K_w = dy < -8`, `K_s = dy > 8`, `K_a = dx < -8`, `K_d = dx > 8`; all other keys `False`. Full-speed or stopped — no analog, no strafe logic.
- **Why identical every time:** waypoint list is rebuilt identically by `reset(act)`; index advances monotonically; no RNG in routing; spawn is fixed by the `--jump` starter. Same start + same list + same tick rate = same trajectory. The ±4 px jitter only wiggles the gun angle, not the feet.

### Family A injection point — `src/app.py`

- Flag parse (`src/app.py:1240-1252`): standalone `if "--trailer-bot" in args` composes with any `--jump`; `--trailer-act X` / `--trailer-act=X` selects script; `_bot.set_active(True); _bot.reset(act)`. Registered jump aliases in `src/core/dev_jumps.py:51-61` (`trailer-m1`, `trailer-m2-killbox`, `trailer-m2-evidence`, `trailer-m3-breakout`, `trailer-m3-comms`) — all map to existing `--dev-*` starters, so the bot always starts from the same spawn.
- Per-frame hook (`src/app.py:2168-2179`, inside GAME update, BEFORE `gc.game_update`): `keys_eff, _ = _bot.tick_bot(keys_eff)` then `gc.game_update(keys_eff)`. Comment at `:2169-2171` explains `keys_eff` (not rebinding `keys`) avoids `UnboundLocalError` on the module-global. Wrapped in bare `try/except: pass`, off by default, never affects normal play.
- Spec source: `docs/PLAN_1_CHOREOGRAPHY.md` §§1-5 (bot-flaw masks: full-speed-or-stopped, instant snap, `tap2` only, reload/swap in cover, melee ≤52 px/±60°, molotov never across walls, never cross FireZone r48).

---

## 2. Family B — headless tour Routers (trailer renders + audits)

Same pattern in four files: fixed **goal-tile list** → A* expands it to tile-center sub-waypoints → `step()` presses WASD toward the current sub-waypoint. A* only fills in the micro-path; the **macro path is the hardcoded goal list**, so runs repeat.

### 2a. `tools/render_trailer.py:340-471` (Longcat structure owner)

- `Router` (`:340-425`): `goals` → `_route()` via `entities.enemy_ai._astar` on a char-grid (`build_grid`, `:322-324` + `overlay_rects` for live colliders, `:327-337`); straight-through `D` nodes dropped (`:366-371`); `step()` advances at `< 24 px`, stuck counter `> 40` triggers 30-frame diagonal `jit` (`:388-425`, `jit_total` logged per section). `grid_fn` refreshes every 60 ticks (`run_gameplay`, `:449-453`).
- `TOURS` (`:491-500`) — **these goal lists are the "same path" for renders:**
  - `m1: [(8,2),(8,8),(8,11),(10,14),(13,16),(15,17),(15,18),(14,20),(22,21)]`
  - `m2: [(14,72),(22,68),(30,62),(24,58)]` — sparse road/transit tiles (see §4)
  - `m2sniper: [(48,28),(52,30),(58,28),(50,26)]`
  - `m3break / m3comms / m3arch / m3ko / walk`: see `:495-499`.
- `make_router` (`:528-542`): builds grid from `tour_grid(map_key)` (`:503-516`: `missions.m1.map.mission1_map`, `missions.m2.world.MISSION2_MAP`, `missions.m3.maps.*`, `walking_sim.walk_map`), overlays locked-door collision rects (`router_colliders`, `:519-525`).
- `run_gameplay` (`:447-470`): `top_up()` god-modes HP/ammo every tick (`:238-249`), `combat_pre` strafes `A/D` on alternating 25-frame halves (`:288-296`), `combat_post` aims with velocity lead `dist/24` and fires ~60% of frames (`:299-319`), else `face_player(router.target())` (`:438-444`). 60-tick pre-roll before feeding frames (`:665-672`) so take starts mid-action.
- `main` SECTIONS (`:545-553`): 7 starters × fixed seconds; `--smoke` shortens to 1 s each.

### 2b. `tools/render_trailer_v2.py` (finish wrapper, owns pacing overrides)

- Delegates structure to `render_trailer` (`:23, 145-154, 530-539`); overrides `card / run_gameplay / run_menu / run_walk / mux` only.
- **Tour-routing fix block (`:503-528`) — read this before touching goals:** strips `"D"` from every tour's solids (unlocked auto-open doors must be A*-passable; locked doors stay sealed via `overlay_rects` collider overlay — verified M1 gate `(14,15)`, archives vault `(24-25,6)/(36,8-9)`), then replaces three goal lists:
  - `m1 → [(8,2),(8,6),(8,9),(9,12),(14,12),(18,11)]` (south-first breach into mid-room fight)
  - `m3break → [(32,10),(33,12),(35,13),(38,13),(40,14),(41,15)]`
  - `m3arch → [(24,39),(24,35),(23,30),(21,26),(17,26),(12,26),(12,22)]`
- `stage_breakout()` (`:157-173`): posts shiv/cell-open flags because the bot can't play the craft drag-minigame — without it the bot "shuffles inside the cell forever". `_run_melee_rush` (`:272-312`): beeline + `handle_melee` inside 60 px with LOS.
- `EDITOR_EDL` (`:48-93`, 58 s lock): game takes are 2.0-2.8 s handles; `editor_main` (`:541-604`) reuses `make_router(key)` per take.

### 2c. `render_ko_video.py:87-216` (PLAN_2 combat-only cut)

- Own `Router` (`:87-153`, same 24 px / stuck-40 / jit-30 recipe, door-map `D` filter `:107-113`), `nearest_enemy(max_d=560)` (`:155-166`), `combat()` (`:169-197`: velocity-lead aim, melee `< 52 px`, `handle_shoot()` every tick gated by real weapon cooldowns), `seek_cover()` vs pin lanes (`:200-216`), `tick()` (`:219-242`: god-mode HP/ammo, unfed `preroll_until_contact` so first fed frame is already firing).
- Scene goals printed at `:283-288` and executed at `:294-316`: A `[(6,5),(10,11),(14,12),(18,11)]`, B `[(32,10),(33,12),(35,13),(38,13),(40,14),(41,15)]` (+ `stage_breakout_flags`, `:250-262`), C `[(5,12),(5,17),(19,12),(14,16)]`.

### 2d. `src/tools/ko_playability_audit.py:54-168` (7-check headless gate)

- `Keys` (`:54-61`) + `Walker` (`:64-106`, same 24 px / 6 px / stuck-40 / jit-30 controller) + `Router(Walker)` (`:127-160`) that A*-routes between **goal tiles** with the straight-through-door smoothing (`:140-150` — comment explains a waypoint ON a door tile causes diagonal corner-jam outside the 48 px auto-open range).
- Check 3 goals (`:230`): `[(5,12),(9,13),(20,15),(20,26),(20,30),(20,35),(33,36)]` spawn→van; check 7 grand tour (`:320-323`): 20-goal loop of all zones with `jit_total <= 6` budget. `pump()` (`:163-168`) god-modes HP each tick. This file documents the `"D"`-in-solids root cause inline.

### 2e. Minor / supporting harnesses (same fake-keys idiom, not path drivers)

- `src/tools/smoke_test.py:44-50` `EmptyKeys` (all-`False`) — never moves the player; `check_game_update` / `check_mission3_kill_order_walk` only prove update+draw don't crash.
- `tools/probe_holdout.py`, `probe_holdout5.py`, `probe_ko_behavior.py`, `probe_ko_cutscene.py`, `probe_stair_gap.py`: static `Keys.down = set()` + optional teleport; they observe AI, they don't walk paths.
- `tools/audio_parade.py:40-57`: `walk_to()` / `tick()` call `Player.move(dx, dy, [])` directly (bypasses keys entirely) to sweep material zones.
- `tools/bench_frame.py`, `tools/collision_map_audit.py`, `m2_walk_shots.py`, `render_walk_rain.py`, `slot_select_shot.py`, `cursor_arrow_shots.py`: fixed teleports / stills, no waypoint loop.

---

## 3. Where movement + aiming are commanded (full chain)

```
Family A:  --jump STARTER --trailer-bot --trailer-act ACT
             → app._apply_dev_args  (src/app.py:1242-1252)
             → GAME.update: tick_bot (src/app.py:2172-2179)
               → src/tools/trailer_bot.py:121-162
                   aim:   STATE.player.angle = atan2(...)   (instant snap)
                   move:  return _FakeKeys(dx,dy)           (:186-201)
             → gc.game_update(keys_eff)
Family B:  python tools/render_trailer[v2].py | render_ko_video.py | ko_playability_audit.py
             → starter() e.g. gc.start_mission / start_mission2* / start_mission3_*_checkpoint
             → Router.step() sets KEYS.down ⊆ {K_w,K_s,K_a,K_d}
             → gc.game_update(KEYS)  (+ combat_pre/post aim via STATE.player.angle)
Sink:      src/core/game_core.py:167-172  game_update(keys) → m3/m2/m1 by STATE.active_mission
             → keys cached per mission:
                 m1: missions/m1/update.py:71    _last_keys = keys
                 m2: missions/m2/update.py:1043  _m2_world._last_keys = keys
                 m3: missions/m3/systems.py:1506 _m3_maps._last_keys = keys
             → per-mission move intake reads keys[WASD] × speed × dt-mul (×0.707 diagonal):
                 m1: missions/m1/update.py:440-457  (STATE.player.speed = 5, entities/player.py:26)
                 m2: missions/m2/update.py:340-359
                 m3: missions/m3/flow.py:640-665   (speed 3.6; angle from mouse EXCEPT under Family A snap)
                 walk sim: missions/walking_sim.py:314-332 (spd 3, walk_player.move)
             → entities/player.py:100-127  Player.move(dx, dy, walls): axis-separated
                 rect slide + material footstep cadence. Only collisions can perturb the path.
Aiming:    Family A sets STATE.player.angle pre-update (read same-frame by
           weapons.handle_shoot/barrel_tip + camera lookahead — PLAN_1 §3 comment).
           Family B: combat_post / combat() set STATE.player.angle with lead dist/24;
           else face_player(router.target()). M2/M3 live updates otherwise overwrite
           angle from the mouse (m2/update.py:335-338, m3/flow.py:642-648).
Interact:  Family A calls game_core.handle_interact() (→ m3/m2/m1 per mission,
           core/game_core.py:183-191). Family B never presses E — it walks through
           auto-open doors and relies on staged flags (v2 stage_breakout).
```

Grep anchors for re-verification: `tick_bot|_BOT_|trailer-act` → `src/app.py:1243-1244,1250,2174-2176` + `src/tools/trailer_bot.py`; `TOURS|make_router|run_gameplay|class Router` → `tools/render_trailer.py`, `tools/render_trailer_v2.py:503-528`, `render_ko_video.py:87-216`; `class Walker|class Router|_astar` → `src/tools/ko_playability_audit.py`.

---

## 4. Why it walks the same path / lingers on empty roads

1. **Fixed scripts, zero perception.** Family A has no enemy/door/cover queries — it marches `_BOT_waypoints` in order. Family B's A* interpolates between fixed tour goals; with no randomization in `goals`, `_route()`, or `step()` thresholds (`<24 px` advance, `>6 px` press, `stuck>40` → `jit 30`), the expanded polyline is bit-identical given the same spawn and collider set.
2. **Sparse transit goals.** The lingering-on-roads feel is literal: e.g. `m2: [(14,72),(22,68),(30,62),(24,58)]` are checkpoint-road tiles, `walk: [(10,2),(16,2),(22,2)]` is a straight hallway, KO check-3 walks the stairwell→lobby→south→dock corridor. Between goals the bot beelines at full speed and, finding no LOS enemy, just `face_player(next_target)` — a long hold on empty asphalt.
3. **Combat layer is reactive, not seeking.** `combat_pre` strafes A/D in place; `combat_post/combat()` only engage when an enemy is already within 560-620 px **with LOS** (`has_los` / `_wall_blocks_line`). No contact → no deviation, no room entry, no corner slicing. `top_up()` god-mode removes any damage pressure that would otherwise break the line.
4. **Door history.** The v2 comment block (`tools/render_trailer_v2.py:503-511`) records the previous "never leaves start" mode: `"D"` listed in tour solids made A* unroutable through unlocked auto-open doors, degrading every cross-door goal to a beeline shuffle. Currently patched by stripping `"D"` + `overlay_rects` locked-collider overlay — but any new goal list that re-adds `"D"` to solids regresses to the same symptom.
5. **M3 angle overwrite caveat:** outside Family A/B aim writes, M2/M3 recompute `STATE.player.angle` from the OS mouse each tick — in dummy-video runs the mouse never moves, so aim freezes unless the bot writes it every tick (both families do, but only toward current foe/waypoint).

---

## 5. How to feed aggressive, room-clearing coordinates (no edits made)

Pick **one** driver per use case; coordinate frames are 64-px tiles (`tile*T+32`), except Family A act-lists which store pre-multiplied pixels via `_tc64`.

**A. Trailer-bot takes (interactive `--trailer-bot` captures):** extend `_build_script(act)` in `src/tools/trailer_bot.py:57-106` (add acts or waypoints; keep the `(move_x, move_y, aim_x, aim_y, action)` 5-tuple and the `dist < 26` / `REACQUIRE` rhythm). Room-clear recipe per room:
  - approach tile **beyond** the door face (never ON the `D` tile — audit note `ko_playability_audit.py:140-143`), action `tap2` aimed at the room's far corners / known guard posts;
  - one `tap2` per threat pocket (aim coords ≠ move coords — pre-aim while moving);
  - `reload`/`swap` waypoints only on cover tiles or under Volkov fire (PLAN_1 §5);
  - `interact` waypoints exactly on console/notebook/relay/exfil tiles (runtime-patch pattern at `:109-118` shows how to resolve `STATE.NOTEBOOK_POS / STATE.EXFIL_POS / missions.m3.draw._relay_pos()` live).
  - Source coordinates from live maps: `missions.m1.map.mission1_map`, `missions.m2.world.MISSION2_MAP`, `missions.m3.maps.MISSION3_*_MAP`, enemy inserts (`missions.m3.sweep._WAVES`), covers (`missions.m2.meta` anchors `(34,40),(40,41),(30,43)`, flank `(22,47)`, `SAFE_ZONE (29,47)`, `TANKER (45,40)`).

**B. Offline trailer takes (MP4 renders):** replace the goal list in `TOURS` (`tools/render_trailer.py:491-500`, overridden at `tools/render_trailer_v2.py:517-528`) or the scene lists in `render_ko_video.py:294-314`. Keep `"D"` **out** of the solids tuple; locked doors are enforced by `router_colliders()` / `overlay_rects`. Chain door-beyond tiles + one goal per room pocket (e.g. M1 south-first breach `[(8,2),(8,6),(8,9),(9,12),(14,12),(18,11)]` is the worked example); keep legs ≤ ~6 tiles so `preroll_until_contact` finds contact fast and `jit_total` stays 0. Validate with `--smoke` (prints `jit_events=` per section).

**C. Playability/completion audits:** use `Router(goals)` in `src/tools/ko_playability_audit.py:127-160` (A* + door-smoothing included) rather than hand улицы waypoints; assert `jit_total <= 6` (check 7 pattern, `:329-332`).

**D. Don'ts (from file comments):** no waypoint centered on a `D` tile (corner jam); no `D` in tour solids (beeline shuffle); no `reload` in the open (105 f sniper lock in M2, pin lanes in KO — use `seek_cover` / pillar list `render_ko_video.py:53`); Family A `melee` only `< 52 px` (resolver rejects the rest); molotov never across a wall line; never stage the bot at the KO van when testing Volkov bail (window deactivates by design, audit `:267-268`).

---

## Appendix — exact file:line index

- `src/tools/trailer_bot.py:1-201` — bot owner; `:57-106` scripts; `:121-162` tick; `:186-201` fake keys
- `src/app.py:1240-1252` flags · `src/app.py:2168-2179` hook · `src/core/dev_jumps.py:51-61` jump aliases
- `docs/PLAN_1_CHOREOGRAPHY.md` — choreography spec + verify gate (`smoke_test`, `compileall`)
- `tools/render_trailer.py:82-90` Keys · `:238-249` top_up · `:288-319` combat_pre/post · `:340-425` Router · `:447-470` run_gameplay · `:491-500` TOURS · `:503-542` grid/router factory · `:545-553` SECTIONS
- `tools/render_trailer_v2.py:152-173` stage_breakout · `:272-312` melee rush · `:315-360` run_gameplay · `:503-528` tour fixes · `:541-604` editor EDL main
- `render_ko_video.py:87-216` Router/combat/cover · `:250-316` staged scenes + goals
- `src/tools/ko_playability_audit.py:64-160` Walker/Router · `:230` + `:320-323` goal lists
- Sink chain: `src/core/game_core.py:167-191` · `src/entities/player.py:26,100-127` · `missions/m1/update.py:71,440-457` · `missions/m2/update.py:335-359,1043` · `missions/m3/flow.py:640-665` + `missions/m3/systems.py:1506` · `missions/walking_sim.py:314-332`
