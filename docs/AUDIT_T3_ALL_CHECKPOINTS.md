# AUDIT T3 — All Playable Combat Checkpoints

Scope: every bootable encounter with active shooting + enemies.
Method: read-only trace of `src/core/dev_jumps.py` (jump registry),
`src/app.py::_apply_dev_args` (CLI dispatcher), `src/core/game_core.py`
(routed wrappers), `src/missions/m1/main.py`, `src/missions/m2/starts.py`
+ `sniper.py` + `world.py`, `src/missions/m3/flow.py` + `world.py` +
`sweep.py` + `systems.py`, `src/entities/enemy_ai.py`.
No source code was edited.

## Jump registry / dispatcher (how to boot anything)

- Registry: `src/core/dev_jumps.py` → `DEV_JUMPS` dict maps short name →
  canonical CLI flag (single source of truth for `--jump NAME` and
  `tools/dev.py`).
- Dispatcher: `src/app.py::_apply_dev_args` (~line 956+) handles
  `--dev-m1`, `--dev-mission2*`, `--dev-mission3*`, `--jump NAME`.
- Routed wrappers: `src/core/game_core.py::start_mission`,
  `start_mission2`, `start_mission2_sniper`, `start_mission2_checkpoint`,
  `start_mission3`, `start_mission3_breakout_checkpoint`,
  `start_mission3_comms_checkpoint`, `start_mission3_archives_checkpoint`,
  `start_mission3_kill_order_checkpoint`, `restart_current_mission`.
- Death-respawn routing: `game_core.restart_current_mission()` —
  M2 evidence flag `STATE.mission2_checkpoint_reached` →
  `start_mission2_checkpoint`; M3 flags `mission3_archives_*` →
  archives, `mission3_comms_*` → comms, `mission3_breakout_*` →
  breakout, else full restart.

## Master table

| # | Scenario | Boot function (direct call) | CLI flag | Enemies on boot | Armed? | Player can shoot on boot? |
|---|----------|-----------------------------|----------|-----------------|--------|---------------------------|
| 1 | Act 1 warehouse shootout (M1 full) | `missions.m1.main.start_mission(preserve_timer=True)` via `core.game_core.start_mission()` | `python acaristan.py --dev-m1` / `--jump m1` | YES — map `E` tiles + `K` commander + scripted miniboss | YES — rifles via `Enemy.update` ATTACK | YES — pistol 12+spare mags, molotovs |
| 2 | Act 2 Route 12 killbox ambush (M2 combat) | `missions.m2.starts.start_mission2_after_sniper()` → `grant_seby_os12()` → `_m3_start_killbox_combat()` → `_start_sniper_aftermath()` → `_spawn_initial_ipa_team()` | `python acaristan.py --dev-mission2-after-sniper` / `--jump m2-after-sniper` (full run: `--dev-mission2-game`) | YES — 1 sniper marker + 3 IPA ground team immediately | YES — ground team live fire; sniper via pressure/laser system | YES — Seby OS-12 (25-rd mag, 2 spares) + pistol |
| 3 | Act 2 evidence holdout / control building (3-wave cleanup) | `missions.m2.starts.start_mission2_checkpoint()` (death respawn) or `start_mission2_evidence_debug()` (clean debug) | `python acaristan.py --dev-mission2-evidence` / `--jump m2-evidence` (checkpoint has no direct CLI; reached via death when `mission2_checkpoint_reached`) | YES (checkpoint) — 4-man wave 1 via `_spawn_control_cleanup()` + `_explode_tanker()` fire zones; debug variant pre-clears all 3 waves → zero | YES — `is_evidence_wave` fast cooldown (50f vs 60f) | YES — OS-12 + pistol, 80–100 HP |
| 4 | Act 3 prison cell-block breakout (M3) | `missions.m3.flow.start_mission3_breakout_checkpoint()` | `python acaristan.py --dev-mission3-game` / `--jump m3-game` | YES — 10 guards via `_spawn_m3_guards_once(force=True)` (called LAST in checkpoint) | YES — per-type guns via `_update_m3_enemies`, but start UNAWARE (IDLE/PATROL) | MELEE ONLY at first — chair leg → craft shiv; sidearm looted off first guard kill |
| 5 | Act 3 comms wing (M3 Phase 3) | `missions.m3.flow.start_mission3_comms_checkpoint()` → `_build_comms_world()` | `python acaristan.py --dev-mission3-comms` / `--jump m3-comms` | YES — 8 guards hardcoded in `_build_comms_world()` | YES — guard/breacher/shield/technician/marksman stats | YES — K-9 SMG (24-rd mag, 2 spares), Volkov ally cover fire |
| 6 | Act 3 archives wing (M3 Phase 4) | `missions.m3.flow.start_mission3_archives_checkpoint()` → `_build_archives_world()` | `python acaristan.py --dev-mission3-archives` / `--jump m3-archives` | YES — 8 guards hardcoded in `_build_archives_world()` | YES — same typed-weapon system | YES — K-9 SMG full + Volkov ally (220 HP) |
| 7 | Act 3 kill-order ground floor + lobby/dock holdout (M3 Phase 5) | `missions.m3.flow.start_mission3_kill_order_checkpoint()` → `_start_kill_order_phase(force=True)` → `_build_kill_order_world()` + `sweep.update_kill_order()` waves | `python acaristan.py --dev-mission3-kill-order` / `--jump m3-kill-order` | DELAYED ~2s — world builds empty; wave 0 (shield+2 guards) at `t>=120` via sweep director, up to 9 concurrent + holdout stream | YES — `ROLE_TUNING` overrides + mezzanine marksman overwatch (0.9s laser telegraph, 34 dmg) | YES — K-9 SMG full, Volkov ally (150 HP), mag pickups, Volkov mag-throw resupply |

Extra bootable combat-adjacent checkpoints (for completeness):
- M2 sniper setup: `missions.m2.starts.start_mission2_sniper()` (`--dev-mission2-sniper`) — clues auto-completed, sniper suppressed, NO live ground enemies yet (combat starts on move).
- M2 flank: `missions.m2.starts.start_mission2_flank()` (`--dev-mission2-flank`) — OS-12 granted, sniper ALIVE on gantry, ground team filtered to sniper-only, phase `m2_flank_sniper`.
- M2 truck: `missions.m2.starts.start_mission2_truck()` (`--dev-mission2-truck`) — zero enemies (`STATE.enemies[:] = []`), STAGE_TRUCK manifest inspection (non-combat breather).
- M3 ledger debug: `missions.m3.systems.start_black_ledger_debug()` (`--dev-mission3-ledger`) — `STATE.enemies = []`, full K-9 loadout; combat is the Black Ledger punishment spawn AFTER shooting the last detainee, not on boot.
- M1 safe: `--dev-safe` / `--jump m1-safe` — explicitly clears `STATE.enemies = []` (non-combat keypad test).
- M3 interrogation cold open: `missions.m3.flow.start_mission3()` (`--dev-mission3`) — ZERO enemies, `player_disarmed=True`, dialogue-only.

---

## 1. Act 1 warehouse shootout (M1)

- Boot: `gc.start_mission(preserve_timer=True)` → `missions/m1/main.py::start_mission` (line 44). CLI: `--dev-m1`.
- Spawn-immediate: YES. `E` tiles → `Enemy(x+16,y+16)`, `K` tile → commander (`hp=250`, `speed=2.2`, `is_commander`), plus appended miniboss (`hp=400`, `is_miniboss`, `speed=1.8`) at tile (10,17). Row-based patrol assignment follows.
- Armed: YES. All use `entities/enemy_ai.py::Enemy.update` — CHASE→ATTACK branch fires `STATE.bullets` (`owner: enemy`) with `fire_cooldown = ENEMY_FIRE_COOLDOWN` (50f for evidence-wave flag, else global). Audible escalation via `enemy_hear_shot`.
- Player fire: YES immediately — `ammo_in_mag=12`, `spare_mags=3 + warehouse_mag_bonus`, molotovs (`player_bottles=2`), melee.
- Note: `--dev-safe` is the same map with enemies stripped — NOT a combat scenario.

## 2. Act 2 Route 12 killbox ambush (M2 combat)

- Boot: `missions/m2/starts.py::start_mission2_after_sniper` (line 265). CLI: `--dev-mission2-after-sniper`. Full-run entry: `start_mission2()` (`--dev-mission2-game`) → investigate → sniper sequence → `grant_seby_os12()` → `_m3_start_killbox_combat()` → `_start_sniper_aftermath()` (sniper.py:412).
- Spawn-immediate: YES. `_spawn_initial_ipa_team()` (sniper.py:1183): sniper marker at (58,26, `hp=90,speed=0,sniper=True`) + 3 ground grunts (47,35 / 52,41 / 42,31, hp 105–115). Placed at `KILLBOX_COVER_POSITIONS[0]`, OS-12 granted first. Reinforcements via `_spawn_reinforcement_wave(count=3)` from `KILLBOX_REINFORCEMENT_SPAWNS` once player commits to cover.
- Armed: YES. Ground team: `_spawn_enemy` (world.py:431) sets `alerted=True, state=CHASE, is_mission2_ipa=True`, `fire_cooldown 18–75` → live `Enemy.update` fire. Sniper marker does NOT shoot via `Enemy`; `_update_sniper_pressure` drives gantry fire from `SNIPER_NEST_POS` with laser telegraph + cover/lock logic (`_player_exposed_to_sniper`, `_player_in_meaningful_cover`).
- Player fire: YES — `grant_seby_os12()`: `os12_unlocked=True, current_weapon=os12, 25-rd mag + 2 spares`, plus pistol fallback.

## 3. Act 2 evidence holdout / control building (M2 STAGE_EVIDENCE)

- Boot (real): `missions/m2/starts.py::start_mission2_checkpoint` (line 368) — auto-used by `restart_current_mission()` when `mission2_checkpoint_reached`. Boot (debug): `start_mission2_evidence_debug` (line 493). CLI: `--dev-mission2-evidence`.
- Spawn-immediate: CHECKPOINT YES / DEBUG NO. Checkpoint: `_spawn_control_cleanup()` wave 1 = 4 enemies at (54,20),(64,22),(58,18),(61,24) `hp=115`, `is_evidence_wave=True`, plus `_explode_tanker()` persistent fire zones; schedule arms wave 2 (5 enemies, hp 120) and wave 3 (7 enemies, hp 125) via `_spawn_evidence_reinforcement_wave`. Debug: same setup then `STATE.enemies[:] = []`, `evidence_wave=3, cleared=True`, event `control_cleanup` pre-added so nothing spawns.
- Armed: YES. Evidence-wave flag → 50-frame fire cooldown (vs 60 global), perimeter+flanker composition, nearest-to-player anchors for instant pressure.
- Player fire: YES — OS-12 + pistol, HP 80 (checkpoint, post-blast scrape) or 100 (debug), placed at `SAFE_ZONE` / first evidence terminal.

## 4. Act 3 prison cell-block breakout (M3 STAGE_BREAKOUT)

- Boot: `missions/m3/flow.py::start_mission3_breakout_checkpoint` (line 330). CLI: `--dev-mission3-game`.
- Spawn-immediate: YES (with gate). `_spawn_m3_guards_once(force=True)` runs LAST: 10 guards — corridor patrols (posts 1/5), stationary marksman (post 2, facing north), guard-room guard+technician (posts 3/8), kitchen breacher (post 4), armory shield (post 6, hp 165), exit marksman (post 7, hp 160), service breacher (post 9), maintenance shield (post 10, hp 230). Live path spawns under same gate once doorway unblocks + weapon in (shiv/sidearm/k9).
- Armed: YES, but start UNAWARE. `_spawn_m3_guard` (world.py:630): `alerted=False`, `IDLE`/`PATROL`, `fire_cooldown 30–90`, per-type table (guard/breacher 15dmg-38f/shield 12dmg-68f+78° plate/technician 10dmg-76f/marksman 30dmg-92f-430range). Fire via `systems.py::_update_m3_enemies` (line 1724) custom LOS path (`_m3_choose_enemy_target`, can also target Volkov), NOT base `Enemy.update` fire.
- Player fire: MELEE ONLY on boot — `mission3_weapon=chair_leg`, `player_disarmed=False`, `sidearm_acquired=False` (explicitly reset so first guard drops pistol). Must sharpen shiv at drain → silent takedowns → loot sidearm → armory K-9 (`k9_unlocked` gates exit via `_m3_exit_requirements`).

## 5. Act 3 comms wing (M3 STAGE_COMMS)

- Boot: `missions/m3/flow.py::start_mission3_comms_checkpoint` (line 441) → `_build_comms_world()` (world.py:876). CLI: `--dev-mission3-comms`.
- Spawn-immediate: YES — 8 guards on build: corridor guard (12,24,hp145,patrol), relay technician (24,18,hp135), server marksman (39,23,hp145,patrol), utility breacher (22,35,hp135,patrol), security technician (13,19,hp130), server shield (36,21,hp230), archive marksman (43,24,hp155), relay breacher (28,18,hp130,patrol).
- Armed: YES — same typed-weapon system as §4 + security camera hazard; objective ladder (clear → restore power → copy auth → tune relay) while `len(STATE.enemies)>0` blocks progress.
- Player fire: YES — `mission3_weapon=k9_smg, current_weapon=k9_smg, k9_unlocked=True, 24+2 mags, sidearm_acquired=True`, full HP, Volkov ally active (220 HP, follow-A*, controlled shots, mag-throw resupply when dry).

## 6. Act 3 archives wing (M3 STAGE_ARCHIVES)

- Boot: `missions/m3/flow.py::start_mission3_archives_checkpoint` (line 531) → `_build_archives_world()` (world.py:1112). CLI: `--dev-mission3-archives`.
- Spawn-immediate: YES — 8 guards on build: atrium patrol (24,34,hp150), stacks technician (12,26,hp140,patrol), stacks marksman (8,32,hp155,patrol), Maru office guard (11,14,hp145), research breacher (34,26,hp150,patrol), cubicle marksman (38,21,hp160), vestibule shield (33,9,hp240,patrol — deliberately NOT inside locked vault to avoid soft-lock), vestibule guard (24,10,hp155,patrol).
- Armed: YES — typed weapons; atrium/pillar cover matters vs marksmen; vault + kill-order exit doors locked until `m3_archives_cleared`/Vostral acquired.
- Player fire: YES — K-9 full loadout (same as comms), Volkov ally re-anchored beside player (220 HP), facing north into atrium; Maru dead-drop → Vostral file → KO handoff.

## 7. Act 3 kill-order ground floor + lobby/dock holdout (M3 STAGE_KILL_ORDER)

- Boot: `missions/m3/flow.py::start_mission3_kill_order_checkpoint` (line 943) → `interrog.py::_start_kill_order_phase(force=True)` (line 78) → `_build_kill_order_world()` (world.py:1027). CLI: `--dev-mission3-kill-order`.
- Spawn-immediate: DELAYED. World builds EMPTY (only `_KO_PICKUPS`: mags/bandage/sidearm); sweep director (`sweep.py`, `MAX_CONCURRENT=9`) fires wave 0 (shield 5,10 + guards 4,12/6,12) at `t>=120`, wave 1 (nest marksman + south probes) on lobby-seen/wave0-cleared/committed, wave 2 pincer (shields west + breachers east) +900f, wave 3 tech flush on south/dock, wave 4 holdout (breachers+tech+marksman) on dock-commit +60f, plus rotating `_HOLDOUT_STREAM` pair every 150 ticks during the 45s garage-door cycle (side-door breach charge at T+20s).
- Armed: YES, heaviest. `ROLE_TUNING` overrides base stats (guard 110hp/55f/15dmg, breacher 160/40/18, shield 260/60/14, tech 100/70/12, marksman 120/80/34); mezzanine marksman overwatch pins `_LANE_V/_LANE_H` with 54-frame (0.9s) laser telegraph; breacher charges punish turtling (`TURTLE_LIMIT` 35s same zone); Volkov 5:00 extraction window with bail branch.
- Player fire: YES — K-9 full, `m3_vostral_acquired=True`, Volkov ally (150 HP), alarm + Balaceanu PA at 90f, exfil at van tile (33,36) → broadcast flag.

## Non-combat exclusions (verified, no live enemies on boot)

- Walking sim harbor (`start_walking_sim`, `--dev-walk`) — exploration/NPC only.
- M3 interrogation (`start_mission3`, `--dev-mission3`) — `enemies=[]`, `player_disarmed=True`.
- M1 safe (`--dev-safe`), M2 truck (`start_mission2_truck`), M2 evidence-debug, M3 ledger-debug — all explicitly clear `STATE.enemies`.
