# AUDIT T7 — Enemy Spawning & Combat Density (READ-ONLY)

Date: 2026-09-26 · Scope: how hostiles are created, alerted, and driven into active fire so any clip can open on a firefight · No source files edited.

---

## TL;DR

- There is **one** enemy class — `Enemy` in `src/entities/enemy_ai.py:117` — shared by all three missions, the level editor, the dev console, and the breach/sweep directors. It is constructed with bare `Enemy(x, y)` and then **mutated into combat by the caller**.
- The alert model is **a boolean + a state string**, not an enum. `alerted: bool` is the "am I combat-aware" flag; `state` is one of **`IDLE`, `PATROL`, `SEARCH`, `CHASE`, `ATTACK`**. (There is no `ALERT` or `COMBAT` state — those are the two things the state *does*, not names it can hold.)
- The canonical "already fighting" recipe, repeated verbatim in **6 independent places** in the codebase, is exactly 4 lines:
  ```python
  e.alerted = True
  e.state = "CHASE"
  e.last_seen_pos = (player_x, player_y)
  e.combat_alert_timer = 420
  ```
- Enemies **cannot fire without line of sight**. `Enemy._shoot` is gated on `can_see` (`enemy_ai.py:470`). Setting `state = "ATTACK"` at frame 0 gives you 45 frames (0.75 s) of ATTACK *posture* but zero muzzle flashes unless the spawn tile actually has LOS to the player. **Place the spawn on the player's sight line, not just nearby.**
- Mission 2 auto-alerts every enemy every frame (`missions/m2/update.py:648`), so M2 spawns need only 1 line. Mission 3 re-derives `state` from its own target director *after* `Enemy.update` (`missions/m3/systems.py:1765-1799`), so M3 spawns need only `alerted + last_seen_pos`. **Mission 1 is the only mission that respects the state you hand it** — and it has a landmine (see §7.1).
- Best hook point for "frame 0 of a recording" is `src/tools/trailer_bot.py` (already the capture harness) or the dev console; the live console `spawn_enemy` command (`src/core/console.py:51-62`) is a 6-line reference implementation but spawns **un-alerted, 100 px to the right, 0 flags** — useless for density on its own.

---

## 1. `Enemy` anatomy — `src/entities/enemy_ai.py`

### 1.1 Constructor (`:118-162`) — defaults that matter for spawn scripts

| Field | Default | Notes |
|---|---|---|
| `rect` | `Rect(x, y, 32, 32)` | **`x,y` is the TOP-LEFT**, not the center. This is why every caller writes `Enemy(tile_cx - 16, tile_cy - 16)` or `Enemy(col*64+16, row*64+16)`. |
| `hp` | `200` | Every mission overrides (115 / 120 / 125 / 140). |
| `speed` | `2.0` | **px per frame**, scaled by `60 * STATE.dt` at move time (`_dt_mul`, `:234-235`). |
| `state` | `"IDLE"` | See §2. |
| `alerted` | `False` | The combat-awareness flag. |
| `combat_alert_timer` | `0` | Frames of "stay combat-aware". 420 = 7 s. |
| `last_seen_pos` | `None` | The coordinate CHASE/SEARCH path toward. **Required** — CHASE with `last_seen_pos is None` immediately falls to SEARCH (`:447-451`). |
| `fire_cooldown` | `0` | Counts **down** each frame (`:237`). `0` = fires the moment it has LOS. Stagger it (60-150) so 4 hostiles don't volley in lockstep. |
| `fire_discipline` | `random.uniform(0.65, 1.15)` | Per-enemy speed/flinch variance. Free cinematic variety — don't overwrite it. |
| `entry_grace` | `0` | If `> 0`, the enemy will **not shoot** (`:470`). Set to 20-40 to let a wave cross the door before firing. |
| `path` / `path_timer` | `[]` / `1` | Force a repath with `path = []; path_timer = 0`. |
| `sweep_points` | `[]` | Search-area points. Clear it or SEARCH will wander to stale coords. |
| `uid` | auto `_next_enemy_id` | Monotonic global. Directors track bodies by uid, not by index. |
| `angle` | `0.0` | Facing, radians. **Not set by the constructor** — a raw `Enemy()` faces due east (+X) regardless of where you put it. Always set it. |

### 1.2 Optional flags read via `getattr` (safe to set on any mission)

| Flag | Effect | Source |
|---|---|---|
| `is_commander` | Red beret + "CMDR" label + double gold pips; drop `keycard` + 2 bandages on death | `enemy_ai.py:871`, `m1/update.py:656-677` |
| `is_ambush_enemy` | **Bullet damage 8 instead of 18** + MAG bandana + "MAG" label | `enemy_ai.py:786`, `:872` |
| `is_breach_enemy` | Re-fixes on the player every 30 frames of lost sight during `firefight`/`escape` (never peels to SEARCH) | `m1/update.py:628-637` |
| `is_evidence_wave` | Fire cooldown **50** instead of `ENEMY_FIRE_COOLDOWN` (60) | `enemy_ai.py:476` |
| `fire_weakness` | Molotov damage multiplier (`1.15` = +15 %) | `weapons.py:86` |
| `drops_mag` | Mag drop on death | `corpse.py` |

> `is_ambush_enemy` is the single biggest density lever and is **counter-intuitive**: it makes the enemy 2.25× more fragile (8 dmg vs 18). For a "player is shredding a squad" trailer look, use plain enemies; for a "shootout where the player must survive" look, use `is_ambush_enemy`.

### 1.3 TUNING constants — `src/core/config.py:74-84`

```
TILE_SIZE              = 64
ENEMY_DETECT_RANGE     = 350     # unalerted sight radius
ENEMY_ATTACK_RANGE     = 200     # CHASE -> ATTACK threshold; optimal band 100-160
ENEMY_FIRE_COOLDOWN    = 60      # frames (~1.0 s) between shots
ENEMY_DAMAGE           = 18      # per bullet
ENEMY_HEAR_RADIUS      = 300     # gunshot hearing, ignores walls
PATH_RECALC_INTERVAL   = 6
PROBE_LEN              = 128
```

`_can_see` (`:594-624`) uses 9 sample points around the player (±12 px) and a **multiplied** sight range: `×1.15` unalerted, `×3.0` if `alerted or combat_alert_timer > 0` → **1050 px once alerted**. So an alerted enemy will "see" you from across most of a map. Unalerted cone is 45° half-angle; alerted is 80° (`:261`).

---

## 2. The actual state machine

`Enemy.update()` (`:229-585`) is one big `if/elif` chain over `self.state`. There is no separate `ALERT` state.

```
                    ┌──────────────── can_see && dist<=200 ──────────────┐
                    │                                                      ▼
  IDLE ──see──▶ CHASE ────────────────────────────────▶ ATTACK ──out of range──▶ CHASE
   ▲             │  ▲                                    │      (×1.5 = 300px)
   │             │  │ reached last_seen,                │
   │             │  │ !can_see, lost_sight>45            │ can_see or lost<45
   │             ▼  │                                    │
   │           SEARCH ◀───────────────────────────────────┘
   │             │
   └─────────────┘  search_timer expires AND combat_alert_timer <= 0
```

| State | Behaviour | Line |
|---|---|---|
| `IDLE` | Stands still, drifts `idle_angle` every 60-180 frames. | `:353-358` |
| `PATROL` | Walks `patrol_points` in a loop; **auto-drops to IDLE if `patrol_points` is empty** (`:360-362`). | `:359-382` |
| `SEARCH` | Pathfinds to `distraction_target`, else sweeps `self.angle` around `last_seen_pos`. De-alerts only when `search_timer <= 0` **and** `combat_alert_timer <= 0`. | `:383-428` |
| `CHASE` | A* to `last_seen_pos`, `+ repulsion`; promotes to `ATTACK` on LOS within `ENEMY_ATTACK_RANGE`; falls to `SEARCH` on arrival with no LOS. | `:429-451` |
| `ATTACK` | Faces player (eased 0.10, with an 8-frame flinch on entry from IDLE/PATROL), strafes sideways between shots, backs off if `dist < 100`, closes if `> 160`. **Fires here.** | `:452-519` |

Global transitions applied every frame *before* the chain:
- `can_see` → `last_seen_pos = (px,py)`, `lost_sight_timer = 0`, `combat_alert_timer = 420`; if `alerted` and not CHASE/ATTACK → force `CHASE` (`:251-258`).
- Unalerted + in cone (or `dist < 115` regardless of cone) → `alerted = True; state = "CHASE"; combat_alert_timer = 420` (`:260-283`).
- Standing in a `FireZone` core → `alerted = True`, **flee** the fire, `return` (skips the state chain entirely) (`:303-345`).
- `_prev_state` IDLE/PATROL → CHASE/ATTACK sets `flinch_timer = 8`, adding ±0.15 rad aim jitter for 8 frames (`:244-247`). This is the "human reaction delay" and it is the visual tell that contact just happened.

---

## 3. The seven ways the game puts an enemy into combat

Ranked by how directly they answer "spawn them already fighting".

### 3.1 Spawn-time mutation (the one you want)
The 4-line recipe. Occurrences:

| Location | Context | Extra flags |
|---|---|---|
| `missions/m2/world.py:446-449` | `_spawn_enemy()` — M2's universal factory | `is_mission2_ipa`, `is_mission2_sniper` |
| `missions/m1/update.py:204-226` | Breach wave A, 8 bodies from bay doors (rows 20-21) | `is_ambush_enemy`, `is_breach_enemy`, `hp=115`, `fire_weakness=1.15`, staggered `fire_cooldown = 40 + i*15 + rand(0,30)` |
| `missions/m1/update.py:244-265` | Breach wave B, 6 bodies from the commander room | same, `fire_cooldown = 60 + i*18 + rand(0,25)` |
| `missions/m3/sweep.py:214-238` | `_spawn_sweep_member()` — KO wave insertion | `m3_sweep_team/role`, `ROLE_TUNING` hp/dmg/cd |
| `core/interactions.py:320-328` | `trigger_mag_ambush()` — stair block | `is_ambush_enemy`, `hp=80`, `fire_cooldown=90` |
| `core/interactions.py:172-174` and `:280-282` | Alarm broadcast: `for e in STATE.enemies: e.alerted=True; e.state="CHASE"` (no `last_seen_pos` — they fall through to the sight cone on the next frame) | — |
| `missions/m3/interrog.py:352-361` | M3 cell-block alarm, same broadcast + fixed `last_seen_pos` at the door tile | — |
| `missions/m3/systems.py:1789-1791` | `technician` type "CALLING IT IN": loops **all** enemies, `alerted = True`, `combat_alert_timer >= 300` | — |
| `missions/m2/update.py:648-658` | Per-frame: **every** M2 enemy is force-alerted and re-pointed at the player every single frame. M2 has no stealth. | — |

### 3.2 Sight cone (passive)
`enemy_ai.py:260-283`. Unalerted: 45° half-cone, 350 px, or **any** direction within 115 px. Immediately sets the full 4-line recipe.

### 3.3 Hearing gunfire
`Enemy.hear_shot()` (`:803-836`), dispatched by `enemy_hear_shot(sx, sy, enemies, walls)` (`:987-989`), called from `weapons.py:363` on every player shot. **Ignores walls** — LOS only reduces positional error (`TILE_SIZE//3` with LOS, `TILE_SIZE` without). Radius `ENEMY_HEAR_RADIUS = 300`. Branching by current state:
- CHASE/ATTACK + `dist < 384`: re-fix noisy position, `combat_alert_timer >= 360`.
- SEARCH: `combat_alert_timer >= 360`, `sweep_points = [noisy_pos]`.
- otherwise: `alerted = True`, `state = "SEARCH"` (not CHASE), `search_timer = 210`, `combat_alert_timer = 300`.

> **Cheapest possible density trigger:** fire one shot anywhere within 300 px of an idle guard and it goes SEARCH with a fix on the noise. It will then walk toward the player. For frame-0 firefights, mutate the flag directly instead — SEARCH costs 3.5 s of approach.

### 3.4 Taking a hit
`Enemy.on_hit(shooter_x, shooter_y)` (`:837-848`), called from `player.py:907` on melee and from the bullet loops (`m1/update.py:575`, `m2/update.py:603`). Sets `alerted = True`, `combat_alert_timer = 480` (longest in the codebase), `last_seen_pos` = shooter ± 16 px noise, forces CHASE, clears `sweep_points`/`path`, and seeds `fire_cooldown = randint(8, 40)`.

### 3.5 Environmental damage (molotov / fire zones)
`weapons.py:532-537` (ignition, sets `last_seen_pos` + CHASE/SEARCH) and `weapons.py:605-614` (burning, `alerted=True`, `combat_alert_timer >= 300`). **Counter-effect:** the `FireZone` branch in `Enemy.update` (`:313-345`) makes anyone inside the inner 45 % of a fire **flee outward at 1.15-1.55× speed and `return` before the state chain runs** — they will not shoot and will not obey CHASE. Do not spawn hostiles inside a fire zone.

### 3.6 Mission 3 target director (overrides your state)
`missions/m3/systems.py:1724-1799`. `_m3_choose_enemy_target` (`:1635-`) may hand `Enemy.update()` a target that is **not the player** (Volkov ally, or a formation sweep point during `STAGE_KILL_ORDER`), then the post-update block **reassigns `e.state` from scratch** every frame:
```python
if can_see:  e.alerted = True; e.combat_alert_timer = 420
   breacher   & dist > range  -> CHASE (+ speed floor 1.85)
   marksman   & dist < 150    -> backpedal + ATTACK
   technician (once)          -> alert ALL enemies on the map
   dist <  m3_attack_range    -> ATTACK
   else                       -> CHASE
```
So in M3 your `state` write is advisory. `alerted = True` + `last_seen_pos` is enough, and the director promotes to ATTACK the frame LOS exists.

### 3.7 M2's per-frame override
`missions/m2/update.py:646-658` unconditionally sets `e.alerted = True`, promotes IDLE/PATROL/SEARCH → CHASE, and re-points `last_seen_pos` at the player **every frame**. In M2, `STATE.enemies.append(Enemy(x, y))` alone is sufficient to produce a hostile that chases and shoots.

---

## 4. Spawn inventory — every call site

| File:line | Count | Constructor | Pre-combat mutations | Mission |
|---|---|---|---|---|
| `missions/m1/main.py:216` | 7 (`E` tiles) | `Enemy(x+16, y+16)` | none here; `state="PATROL"`, `speed=1.5`, per-region `patrol_points` at `:226-272` | M1 map bake |
| `missions/m1/main.py:220-224` | 1 (`K` tile) | `Enemy(...)` | `hp=250`, `is_commander=True`, `speed=2.2` | M1 commander |
| `missions/m1/main.py:273-277` | 1 | `Enemy(10*64+16, 17*64+16)` | `hp=400`, `is_miniboss=True`, `speed=1.8` | M1 miniboss |
| `missions/m1/update.py:205` | 8 | `Enemy(mx,my)` | full 4-line + ambush flags | M1 breach A |
| `missions/m1/update.py:245` | 6 | `Enemy(mx,my)` | full 4-line + ambush flags | M1 breach B |
| `missions/m2/world.py:440` | all | `_spawn_enemy()` | `alerted/state/last_seen_pos/fire_cooldown=rand(18,75)` | M2 factory |
| `missions/m2/sniper.py:1193-1196` | 4 | `_spawn_enemy` | sniper hp 90 speed 0; then `fire_cooldown = 150 + rand(0,80)` on all four | M2 initial IPA team |
| `missions/m2/sniper.py:1203-1252` | 3/wave | `_spawn_enemy` | far-anchor sort, ±1 tile jitter, wall-overlap retry, `hp=100 speed=2.05`, dust burst | M2 killbox reinforcements |
| `missions/m2/sniper.py:1278-1280` | 4 | `_spawn_enemy` | `is_evidence_wave=True` | M2 cleanup wave 1 |
| `missions/m2/sniper.py:1290-1359` | 5 (w2) / 7 (w3) | `_spawn_enemy` | **nearest-anchor** sort, `is_evidence_wave=True` | M2 evidence waves |
| `missions/m3/world.py:647` | all | `_spawn_m3_guard()` | **un-alerted** (`alerted=False`), `state = PATROL if patrol else IDLE`, `facing`, `type_stats` table (`:660-666`) | M3 factory |
| `missions/m3/world.py:1327-1366+` | 8 | `_spawn_m3_guard` | hp 130-150, speed 1.2-1.4, guard/marksman/breacher types | M3 cell block |
| `missions/m3/sweep.py:216-238` | 3-5/wave | `_spawn_m3_guard` | `alerted=True`, `state="CHASE"`, `last_seen_pos = player center` | M3 KO sweep |
| `core/interactions.py:321` | 2-3 | `Enemy(mx,my)` | `alerted/state/last_seen_pos`(fixed)/`is_ambush_enemy`/`hp=80`/`fire_cooldown=90` | M1 MAG ambush |
| `core/level_editor.py:147,149` | — | `Enemy(x+16,y+16)` | editor: adds `is_commander` variant | level editor |
| `core/console.py:56` | 1 | `Enemy(px+100, py)` | **NOTHING** — un-alerted, IDLE, faces +X | dev console |

### 4.1 M3 per-type stat table (`missions/m3/world.py:660-666`)

| `enemy_type` | damage | cooldown | spread | bullet speed | attack range |
|---|---|---|---|---|---|
| `guard` | 18 (`ENEMY_DAMAGE`) | 60 | 0.06 | 18 | 200 |
| `breacher` | 15 | 38 | 0.12 | 17 | 145 |
| `shield` | 12 | 68 | 0.08 | 16 | 175 (+ `shield_angle_width` 78°) |
| `technician` | 10 | 76 | 0.10 | 16 | 215 (alerts whole map on first sighting) |
| `marksman` | 30 | 92 | 0.025 | 22 | 430 |

**For maximum visual density at frame 0, `breacher` is the pick**: 145 px range means it closes and fires almost immediately, at 1.9 shots/s, with a 0.12 rad spread that looks like a real firefight. `marksman` is the opposite — 92-frame cooldown, 430 px range, will hold the line.

### 4.2 Sweep caps
`missions/m3/sweep.py:50` — `MAX_CONCURRENT = 9`, holdout cap `+3`. Waves are **withheld entirely** if the incoming size would exceed the cap (`:282-284`), so a hand-spawned body in the KO stage can stall the director. Budget for it.

---

## 5. Dead-walking-time budget per mission (measured from source tiles)

Player speed = **5 px/frame** (`entities/player.py:26`) → 300 px/s at 60 Hz. `ENEMY_DETECT_RANGE` = 350.

| Mission | Player spawn | Nearest pre-authored enemy | Gap | First contact | Objective distance |
|---|---|---|---|---|---|
| **M1** | `P` = tile (3,2) → px (208,144) | `E` = tile (7,7) → (480,480) | **432 px** (beyond the 350 detect radius) | ~1.4 s of walking + 45° cone alignment | notebook `N` = (15,18) → (992,1184) = **1298 px ≈ 4.3 s** of empty corridor |
| **M2** | `PLAYER_START` = tile (8,74) → (544,4768) | **none** — `_build_world` (`m2/world.py:459-`) spawns zero enemies; the first team arrives via `_spawn_initial_ipa_team` at tiles (58,26),(47,35),(52,41),(42,31) | **~3510 px** | ~12 s+ | investigation clues are scattered across a 70×80 map |
| **M3** | `P` / `PLAYER_START_TILE` = (32,9) → (2080,608) | guard post 1 = (34,15) → (2208,992) — **and** not spawned until `m3_volkov_run_done` (`world.py:1321`) | **384 px** + cutscene gate | ~1.3 s after the breach | corridor is 6 tiles of walk before contact |

**Conclusion: M2 is the worst offender by an order of magnitude** — the entire investigate phase is authored as zero-density. M1 has a 4.3 s walk. M3 is fine but gated behind a scripted Volkov beat.

---

## 6. How to spawn 2-4 armed hostiles in front of the player at frame 0

### 6.0 The shared primitive

There is no cross-mission spawn helper — M1, M2 and M3 each have their own factory. The generic one for a capture harness:

```python
# src/tools/trailer_bot.py (or any capture-side module)
import math, random
from core.config import TILE_SIZE
from core.state import STATE
from entities.enemy_ai import Enemy

def force_fight(x, y, hp=115, speed=2.0, *, cooldown=90, ambush=False,
                breach=False, angle=None):
    """Create an Enemy already in active combat with the player."""
    e = Enemy(x, y)                       # NOTE: x,y is TOP-LEFT of a 32x32 rect
    e.hp = hp
    e.speed = speed
    e.alerted = True                      # 1. combat-aware: 3x sight, 80 deg cone
    e.state = "CHASE"                     # 2. skip IDLE/PATROL
    px, py = STATE.player.rect.center      # 3. mandatory chase target
    e.last_seen_pos = (px + random.randint(-24, 24), py + random.randint(-24, 24))
    e.combat_alert_timer = 420            # 4. hold awareness 7 s minimum
    e.fire_cooldown = cooldown            # stagger so they don't volley in unison
    if angle is not None:
        e.angle = e.idle_angle = angle    # else they face due +X until frame 1
    if ambush:
        e.is_ambush_enemy = True          # damage 8, MAG bandana
    if breach:
        e.is_breach_enemy = True          # never peels to SEARCH during firefight
    STATE.enemies.append(e)
    return e
```

**Non-negotiable rules**

1. **`last_seen_pos` is mandatory.** `CHASE` with `last_seen_pos is None` immediately drops to `SEARCH` with `search_timer = 120` (`:447-451`). You get SEARCH, not combat.
2. **Set `angle`.** A fresh `Enemy` faces +X. The facing only eases toward the player at `_ease_toward_angle(..., 0.10)` — i.e. ~10 %/frame. If you spawn *behind* the player, frame 0 shows four guards facing a wall. For a "spotted you" opening, set `angle = math.atan2(py - y, px - x)` directly.
3. **Spawn on the LOS line.** Firing requires `can_see` (`:470`). Best practice: compute the tile directly in front of the player along `STATE.player.angle` (the player's facing), 3-5 tiles out, and verify with a wall clipline before appending. Fall back to a 180° arc of candidates.
4. **Stagger `fire_cooldown` to `40 + i*25 + random.randint(0, 30)`.** This is verbatim the M1 breach-wave pattern (`m1/update.py:224`) and it is the difference between a firefight and a synchronised volley.
5. **Do not spawn inside a `FireZone`.** `enemy_ai.py:313-345` short-circuits `update()` with a flee.
6. **Do not spawn overlapping walls or each other.** Every director in the codebase does a `pygame.Rect(wx-16, wy-16, 32, 32).colliderect(w)` check with offset retries — copy `m2/sniper.py:1336-1358` (`_try_spawn`).

### 6.1 Placement: "in front of the player"

```python
def spawn_wedge(count=3, tiles_out=4, spread=0.55, cooldown0=40):
    """Fan `count` hostiles across an arc in front of the player."""
    p = STATE.player
    if p is None:
        return []
    base = getattr(p, "angle", 0.0)            # player's own aim = where they look
    out = []
    for i in range(count):
        t = 0.0 if count == 1 else (i / (count - 1) - 0.5) * 2   # -1 .. +1
        a = base + t * spread
        d = tiles_out * TILE_SIZE + (i % 2) * 40   # alternate near/far row
        x = int(p.rect.centerx + math.cos(a) * d)
        y = int(p.rect.centery + math.sin(a) * d)
        e = force_fight(x - 16, y - 16,           # top-left, not center
                        hp=115, speed=2.1,
                        cooldown=cooldown0 + i * 25 + random.randint(0, 30),
                        angle=a)
        out.append(e)
    return out
```

A **wedge** (2-4 bodies at 3-5 tiles, ±0.55 rad) reads as "ambushed / contact" on frame 0. If you want "they walked up on me", invert: spawn behind (`base + math.pi`) so they close into frame.

### 6.2 Per-mission concrete recipes

**Mission 1** — the only mission that respects your state write, and the only one with a landmine (§7.1). Player spawns at tile (3,2) px (208,144) in a 30×22 map. Enemy `E` tiles: (25,5), (7,7), (16,7), (12,11), (21,12), (5,13), (15,13); commander `K` (10,14); miniboss (10,17). Open floor is rows 1-3, cols 1-28.

```python
# M1: 3 hostiles in the open bay the player is already standing in
spawn_wedge(count=3, tiles_out=4, spread=0.5, cooldown0=40)
# then, to match M1's house style:
for e in STATE.enemies[-3:]:
    e.hp = 115
    e.is_ambush_enemy = True
    e.is_breach_enemy = True
    e.fire_weakness = 1.15
    e.speed = random.uniform(2.0, 2.7)
```
Add 2-second stagger: `STATE.mission_phase = "firefight"; STATE.firefight_triggered = True` (skips the auto-alarm path, §7.1) and `STATE.radio_chatter_stage = 1`.

**Mission 2** — the highest-value fix. M2's update loop force-alerts every enemy every frame (`m2/update.py:648`), so you only need the constructor:
```python
from missions.m2.world import _spawn_enemy
from missions.m2.sniper import grant_seby_os12
grant_seby_os12()                    # player needs the OS-12 for the trailer weapon
_spawn_enemy(10, 71, hp=115, speed=2.05)   # player start is (8,74)
_spawn_enemy(12, 70, hp=115, speed=2.05)
_spawn_enemy( 9, 68, hp=120, speed=2.1)
```
`MAP_W, MAP_H = 70, 80` (`m2/meta.py:220`). Prefer `is_evidence_wave = True` for the 50-frame cooldown. Or reuse the real director: `from missions.m2.sniper import _spawn_reinforcement_wave; _spawn_reinforcement_wave(count=3, prefer_far=False)` — it sorts anchors **nearest-first** when `prefer_far=False` and does the wall-overlap retry for you. Anchors: `(58,32) (54,41) (46,28) (20,41) (26,44) (50,34) ...` (`m2/meta.py:481-`).

**Mission 3** — spawn *un-alerted-friendly*: `_spawn_m3_guard` already sets `alerted=False`, so flip it after. But remember §3.6: the director overwrites `state` every frame, so only `alerted` + `last_seen_pos` matter.
```python
from missions.m3.world import _spawn_m3_guard
px, py = STATE.player.rect.center
escorts = [
    _spawn_m3_guard(34, 12, hp=130, speed=1.8, facing=math.pi,      label="hot_1", enemy_type="breacher"),
    _spawn_m3_guard(35, 13, hp=130, speed=1.8, facing=math.pi,      label="hot_2", enemy_type="guard"),
    _spawn_m3_guard(33, 13, hp=130, speed=1.9, facing=math.pi * 0.5, label="hot_3", enemy_type="technician"),
]
for e in escorts:                       # technician auto-alerts the whole block on sighting
    e.alerted = True
    e.last_seen_pos = (px, py)
    e.combat_alert_timer = 420
    e.fire_cooldown = random.randint(20, 90)
```
Player start tile is (32,9) (px 2080,608); the main corridor is row 15, so tiles (33-35, 12-14) are open and in LOS. Existing guard posts (for reference / to avoid stacking): (34,15) (22,15) (22,21) (4,22) (15,15) (40,22) (41,15) (30,21) — `missions/m3/world.py:557-564`.

### 6.3 Wiring it to frame 0 of a recording

The capture harness already exists and already has a per-frame, pre-simulation hook.

- **Flag parse:** `src/app.py:1240-1252` — standalone `if "--trailer-bot" in args`, composes with any `--jump`, reads `--trailer-act X` / `--trailer-act=X`, calls `_bot.set_active(True); _bot.reset(act)`.
- **Per-frame hook:** `src/app.py:2168-2179`, inside `GAME.update`, **before** `gc.game_update(keys_eff)`. The comment at `:2169-2171` warns you to assign to `keys_eff` and never rebind `keys` (module-global read → `UnboundLocalError`).
- **Best insertion point:** the first `tick_bot` invocation, or better a one-shot guard in `trailer_bot.reset()` — but `reset()` runs at flag-parse time, *before* the mission has been started, so `STATE.player` is still `None` and `STATE.enemies` is not yet built. The correct frame-0 location is therefore a **one-shot latch inside `tick_bot`**: first call after `STATE.player` is non-`None` and `STATE.mission_phase` is a gameplay phase. Track it with a module global in `trailer_bot` (per AGENTS.md: the `_BOT_*` owner module, consumed as `import tools.trailer_bot as _bot; _bot.NAME`).
- **Alternative, zero-code:** drive it live from the dev console (backtick, `src/core/console.py:36`). `spawn_enemy` exists but is un-alerted; `teleport X Y` + one player shot (`enemy_hear_shot` radius 300) will pull nearby guards into SEARCH. Reliable enough for a hand-framed take, not for a deterministic 60 Hz render.

For **headless** renders (`tools/render_trailer.py`, `tools/render_trailer_v2.py`, `render_ko_video.py`) there is no `--trailer-bot` flag — those call `gc.game_update(KEYS)` directly. The same latch belongs in `run_gameplay()`'s pre-roll (`:665-672` already burns 60 ticks before feeding frames; a spawn placed at the top of that pre-roll is genuinely frame 0 of the captured section).

### 6.4 Verify

```
python tools/smoke_test.py          # must print SMOKE TEST: OK
python -m compileall -q src
```
Then run a take and assert, in the first 30 frames: at least one `audio.play_3d("gunshot_distant")`, at least one bullet in `STATE.bullets` with `"owner": "enemy"`, and `any(e.state == "ATTACK" for e in STATE.enemies)`.

---

## 7. Pitfalls (read before shipping a spawn hook)

### 7.1 M1 pre-alerting detonates the alarm — and the whole map
`missions/m1/update.py:100-105`:
```python
if STATE.player and not STATE.firefight_triggered:
    for e in STATE.enemies:
        if e.alerted:
            trigger_alarm_early()
            break
```
`trigger_alarm_early()` (`core/interactions.py:262-291`) sets `mission_phase = "firefight"`, `quiet_entry = False`, starts Volkov's escape animation, plays the alarm, force-alerts **every** enemy to CHASE, floats "ALARM TRIGGERED!", and queues the Vasile line. Any pre-alerted spawn at frame 0 therefore fires the entire alarm beat on frame 1 and converts the stealth phase into a firefight. That is usually what you want for a trailer — but it is *not* just "add enemies", and it also means the M1 radio-chatter ladder (`:112-128`) jumps to stage 1.

### 7.2 M1 hostile-gate on the notebook
`core/interactions.py:126-145` — the safe keypad only opens if **no enemy is within 300 px of `STATE.NOTEBOOK_POS`**. Hostiles parked at frame 0 near tile (15,18) will lock the objective with a "CLEAR HOSTILES FIRST" float. Spawn away from the notebook tile or shoot them off before the interact.

### 7.3 M2 spawns are auto-alerted, so `alerted=False` is a no-op there
Already covered (§3.7) — but it means you cannot author a stealth M2 clip by omission. `STATE.enemies[:] = []` is the only way to get an empty M2 frame (used by `starts.py:349`, `:411`, `:526`).

### 7.4 M3 director overwrites your state — and can stall
§3.6 plus `MAX_CONCURRENT = 9` (`sweep.py:50`). A hand-spawned body in `STAGE_KILL_ORDER` counts against the cap and the whole next wave is withheld (`:282-284`).

### 7.5 Kills and drops are observable
`STATE.hostiles_killed` increments in the per-mission death handler (`m1/update.py:693`, `m2/update.py:661`, `m3/systems.py:1828`) and feeds the end-of-mission score (`app.py:562`: `min(25, hostiles_killed * 3)`) and the stats screen (`ui/system.py:1172`). Extra bodies inflate the KILLS line in any clip that shows the results card. M2 also rolls a 28 % bandage / 28 % mag drop per kill (`m2/update.py:667-671`), so 4 extra bodies means up to 2 extra pickups on the floor.

### 7.6 Corpses persist
`corpse.spawn_corpse(e)` runs on death in all three missions; dead enemies leave a body for the rest of the clip. Budget for corpses in the frame if you're spawning 4 bodies.

### 7.7 `is_ambush_enemy` cuts damage by more than half
`8` instead of `ENEMY_DAMAGE = 18` (`enemy_ai.py:786`). If your trailer's *point* is the player shredding hostiles, do **not** use it.

### 7.8 M1 breach flags only matter in `firefight`/`escape`
`m1/update.py:628-637` — `is_breach_enemy` re-fixing is gated on `STATE.mission_phase in ("firefight", "escape")`. Outside those phases the flag is inert.

---

## 8. One-page summary of the incantation

```python
e = Enemy(top_left_x, top_left_y)   # top-left, not center; 32x32
e.hp, e.speed = 115, 2.1
e.alerted = True
e.state = "CHASE"
e.last_seen_pos = (STATE.player.rect.centerx, STATE.player.rect.centery)
e.combat_alert_timer = 420
e.fire_cooldown = 40 + i * 25 + random.randint(0, 30)
e.angle = math.atan2(py - e.rect.centery, px - e.rect.centerx)
STATE.enemies.append(e)
```
Plus: verify LOS from the spawn tile to the player, keep the 32×32 footprint clear of `STATE.walls`, keep out of `STATE.fire_zones`, and in M1 set `STATE.firefight_triggered = True` on the same frame to own the alarm beat deliberately.
