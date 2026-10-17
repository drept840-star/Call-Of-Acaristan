# PLAN 1 — Bot Gameplay & Tactical Choreography (AI 1, actionable)

> Scope: make the trailer bot look like a disciplined operator. No other files are edited by this plan — apply diffs in order, then verify.

## 0. Ground truth (do not retune these, drive around them)

| System | File:line | Value |
|---|---|---|
| Player speed | `src/entities/player.py:26` | `speed = 5` px/frame, diagonal `*0.707` in `src/missions/m1/update.py:453-455` |
| Enemy sense/shoot | `src/core/config.py:75-84` | `DETECT 350, ATTACK 200, FIRE_CD 60, HEAR 300` |
| Pistol / OS-12 / K-9 | `src/entities/weapons.py:332-343,412-419` | Pistol `cd12/dmg50`, OS-12 `cd8/dmg28/25rd`, K-9 `cd5/dmg18/24rd` |
| Reload | `src/entities/weapons.py:209-226` | Pistol `60f`, K-9 `72f`, OS-12 `90f` |
| Swap anim | `src/core/state.py:86-89`, `src/entities/player.py:422-433` | `weapon_swap_duration 24f`, flip at midpoint, blocks fire |
| Melee | `src/entities/player.py:842-847` | `RANGE 52, CONE ±60°, DMG 78, KILL_HIT_STOP 0.05` |
| Molotov | `src/entities/weapons.py:13-25,499-501` | `RADIUS 92, flight speed 0.035, arc 40px` |
| Camera | `src/core/camera.py:28-38,124-191` | `EASE 0.15, LOOKAHEAD 48, DEADZONE 16`; shake+kick applied direct to render, aim from `STATE.camera_x/y` |
| M1 breach wave | `src/missions/m1/update.py:196-265` | 8x bay + 6x rear, `hp115, fire_weakness 1.15, speed 2.0-2.7` |
| M2 sniper clock | `src/missions/m2/meta.py:646-687` | `regroup 100f, m1 720f, m2 600f, m3 600f`; lock `105f/decay 5/warn 35,65,90` (`meta.py:473-475`) |
| M2 anchors | `src/missions/m2/meta.py:306,431-438` | `PLAYER_START _tc(8,74)`, covers `_tc(34,40),(40,41),(30,43)`, flank `_tc(22,47),(55,45)`, `SAFE_ZONE _tc(29,47)`, `TANKER _tc(45,40)` |
| M3 Volkov ally | `src/missions/m3/systems.py:1329,1376,1464`, `src/missions/m3/flow.py:256-264` | `follow_dist 82` behind aim vector, `speed 3.05`, fire `cd32/dmg28/range620`, `hp220` |
| M3 relay tune | `src/missions/m3/draw.py:2252-2269` | `m3_relay_duration 360f` |
| Input map | `src/app.py:2106-2126` | `LMB shoot, RMB/G throw, R reload, Q swap, E interact, V melee` |
| Update route | `src/core/game_core.py:167-172` | `game_update(keys)` → m3/m2/m1 by `STATE.active_mission` |

## 1. CREATE `src/tools/trailer_bot.py` (owner of all `_BOT_*` mutable state)

New file. Nothing else owns bot state (per `AGENTS.md` shared-mutable-state rule — consumers read via `import tools.trailer_bot as _bot` + `_bot.NAME`).

```python
"""Trailer bot — deterministic operator driver for cinematic capture.

Usage (after Diff 3 hook lands):
  python acaristan.py --jump m1 --trailer-bot --trailer-act act1
  python acaristan.py --jump m2-game --trailer-bot --trailer-act act2_killbox
  python acaristan.py --jump m3-game --trailer-bot --trailer-act act3_breakout
  python acaristan.py --jump m3-comms --trailer-bot --trailer-act act3_relay

Design: the bot does NOT pathfind. Each act is a waypoint list
(tile-center coords resolved at runtime via each mission's _tc).
Every frame: sprint full-speed at current waypoint, snap angle
instantly to pre-aim, fire double-taps via the real weapons pipeline.
"""
import math
import pygame
from core.state import STATE

_BOT_active = False
_BOT_act = "act1"
_BOT_wp_idx = 0
_BOT_hold = 0
_BOT_waypoints = []  # list of (x, y, aim_x, aim_y, action)
_BOT_fire_cd = 0

TAP_GAP = 9          # frames between the 2 shots of a double-tap
REACQUIRE = 18       # frames to hold aim after a kill before moving
PREAIM_SPREAD = 0.06 # radians of humanising jitter around pre-aim

def reset(act="act1"):
    global _BOT_act, _BOT_wp_idx, _BOT_hold, _BOT_waypoints, _BOT_fire_cd
    _BOT_act = act
    _BOT_wp_idx = 0
    _BOT_hold = 0
    _BOT_fire_cd = 0
    _BOT_waypoints = _build_script(act)

def is_active():
    return _BOT_active

def set_active(v):
    global _BOT_active
    _BOT_active = bool(v)

def _tc64(col, row):
    return (col * 64 + 32, row * 64 + 32)

def _build_script(act):
    """Waypoint = (move_x, move_y, aim_x, aim_y, action).
    Actions: move | tap2 | molotov | melee | interact | reload | swap | hold<N>"""
    T = _tc64
    if act == "act1":
        # Warehouse: patrol kill -> gate console (13,15) -> notebook (runtime)
        # -> bay-mouth hold (15,18) -> exfil (runtime). Notebook/exfil patched
        # at runtime from STATE.NOTEBOOK_POS / STATE.EXFIL_POS (see tick_bot).
        return [
            (T(6, 5)[0], T(6, 5)[1], T(6, 7)[0], T(6, 7)[1], "tap2"),
            (T(10, 11)[0], T(10, 11)[1], T(12, 11)[0], T(12, 11)[1], "tap2"),
            (T(13, 15)[0], T(13, 15)[1], T(15, 15)[0], T(15, 15)[1], "interact"),
            (T(14, 17)[0], T(14, 17)[1], T(16, 18)[0], T(16, 18)[1], "molotov"),
            (T(15, 18)[0], T(15, 18)[1], T(15, 20)[0], T(15, 20)[1], "tap2"),
            (T(15, 18)[0], T(15, 18)[1], T(13, 17)[0], T(13, 17)[1], "tap2"),
            (T(15, 21)[0], T(15, 21)[1], T(15, 21)[0], T(15, 21)[1], "interact"),
        ]
    if act == "act2_killbox":
        return [
            (T(34, 40)[0], T(34, 40)[1], T(36, 34)[0], T(36, 34)[1], "tap2"),
            (T(40, 41)[0], T(40, 41)[1], T(44, 34)[0], T(44, 34)[1], "tap2"),
            (T(40, 41)[0], T(40, 41)[1], T(40, 41)[0], T(40, 41)[1], "reload"),
            (T(30, 43)[0], T(30, 43)[1], T(36, 34)[0], T(36, 34)[1], "tap2"),
            (T(22, 47)[0], T(22, 47)[1], T(30, 40)[0], T(30, 40)[1], "tap2"),  # ditch flank
        ]
    if act == "act2_evidence":
        return [
            (T(55, 23)[0], T(55, 23)[1], T(57, 23)[0], T(57, 23)[1], "interact"),
            (T(63, 19)[0], T(63, 19)[1], T(63, 17)[0], T(63, 17)[1], "tap2"),
            (T(59, 14)[0], T(59, 14)[1], T(59, 12)[0], T(59, 12)[1], "interact"),
        ]
    if act == "act3_breakout":
        return [
            (T(6, 6)[0], T(6, 6)[1], T(8, 6)[0], T(8, 6)[1], "melee"),
            (T(8, 6)[0], T(8, 6)[1], T(10, 6)[0], T(10, 6)[1], "tap2"),
            (T(10, 8)[0], T(10, 8)[1], T(12, 8)[0], T(12, 8)[1], "tap2"),
        ]
    if act == "act3_relay":
        # Comms chain: breaker -> auth booth -> relay. Exact relay pos via
        # missions.m3.draw._relay_pos() at runtime; tiles below are approach.
        return [
            (T(8, 10)[0], T(8, 10)[1], T(10, 10)[0], T(10, 10)[1], "tap2"),
            (T(12, 10)[0], T(12, 10)[1], T(14, 10)[0], T(14, 10)[1], "interact"),
            (T(14, 12)[0], T(14, 12)[1], T(16, 12)[0], T(16, 12)[1], "tap2"),
            (T(16, 12)[0], T(16, 12)[1], T(16, 12)[0], T(16, 12)[1], "reload"),
            (T(16, 12)[0], T(16, 12)[1], T(16, 12)[0], T(16, 12)[1], "swap"),
        ]
    return []

def _patch_runtime_targets():
    # Resolve M1 notebook/exfil + M3 relay from live STATE so the script
    # survives map-authoring moves. Called once per tick (cheap).
    if _BOT_act == "act1" and _BOT_waypoints:
        nb = getattr(STATE, "NOTEBOOK_POS", None)
        ex = getattr(STATE, "EXFIL_POS", None)
        if nb:
            _BOT_waypoints[3] = (nb[0], nb[1] + 54, nb[0], nb[1], "interact")
        if ex:
            _BOT_waypoints[-1] = (ex[0] - 42, ex[1], ex[0], ex[1], "interact")

def tick_bot(keys):
    """Called from app GAME.update BEFORE gc.game_update(keys).

    Returns (keys, fired_action). Sets STATE.player.angle directly
    (instant snap — never lerp). Fires through the real weapons pipeline
    so shake/kick/casings/tracers match human play. Movement is injected
    by returning a fake keys object with WASD set toward the waypoint.
    """
    # lazy: breaks tools<->app load cycle (AGENTS.md import direction)
    from entities import weapons as _w
    _patch_runtime_targets()
    p = getattr(STATE, "player", None)
    if p is None or getattr(STATE, "player_dead", False):
        return keys, None
    if not _BOT_waypoints:
        return keys, None
    global _BOT_wp_idx, _BOT_hold, _BOT_fire_cd
    if _BOT_fire_cd > 0:
        _BOT_fire_cd -= 1
    if _BOT_hold > 0:
        _BOT_hold -= 1
        return keys, "hold"
    mx, my, ax, ay, action = _BOT_waypoints[min(_BOT_wp_idx, len(_BOT_waypoints) - 1)]
    # 1. Snap aim (human flick: instant + tiny jitter, no ease).
    import random as _r
    p.angle = math.atan2(
        (ay + _r.uniform(-4, 4)) - p.rect.centery,
        (ax + _r.uniform(-4, 4)) - p.rect.centerx)
    # 2. Movement: full-speed (5px/f) toward waypoint via fake WASD.
    dx, dy = mx - p.rect.centerx, my - p.rect.centery
    dist = math.hypot(dx, dy)
    if dist < 26 and action in ("move", "tap2", "molotov", "melee", "interact"):
        _do_action(action, _w)
        if action in ("tap2", "molotov", "melee"):
            _BOT_hold = REACQUIRE
        _BOT_wp_idx = min(_BOT_wp_idx + 1, len(_BOT_waypoints) - 1)
        return keys, action
    if dist < 26:  # reload / swap / hold waypoints fire in place
        _do_action(action, _w)
        _BOT_wp_idx = min(_BOT_wp_idx + 1, len(_BOT_waypoints) - 1)
        return keys, action
    return _FakeKeys(dx, dy), None

def _do_action(action, _w):
    if action == "tap2" and _BOT_fire_cd <= 0:
        _w.handle_shoot()
        _BOT_fire_cd = TAP_GAP
        # Second tap queued next tick by hold window; weapon cd gates it
        # exactly like a human double-tap (pistol 12f / OS-12 8f / K-9 5f).
    elif action == "molotov":
        _w.handle_throw_bottle()
    elif action == "melee":
        _w.handle_melee()
    elif action == "reload":
        _w.start_reload()
    elif action == "swap":
        _w.switch_weapon()
    elif action == "interact":
        # lazy: game_core routes E per mission (M1 gate / M2 clue / M3 relay)
        from core import game_core as _gc
        _gc.handle_interact()

class _FakeKeys:
    """Duck-types pygame.key.get_pressed() for game_update(keys)."""
    def __init__(self, dx, dy):
        self._dx, self._dy = dx, dy
    def __getitem__(self, key):
        if key == pygame.K_w:
            return self._dy < -8
        if key == pygame.K_s:
            return self._dy > 8
        if key == pygame.K_a:
            return self._dx < -8
        if key == pygame.K_d:
            return self._dx > 8
        if key == pygame.K_e:
            return False
        try:
            return False
        except Exception:
            return False
```

## 2. Diff `src/core/dev_jumps.py` — register trailer takes

```diff
--- a/src/core/dev_jumps.py
+++ b/src/core/dev_jumps.py
@@
     "m3-archives-cutscene": ("--dev-mission3-archives-cutscene",
                              "Mission 3 comms-to-archives transition cutscene"),
+    # ── Trailer bot takes (AI 1 choreography) ──
+    "trailer-m1": ("--dev-m1",
+            "Trailer Act I warehouse take (bot: breach/molotov)"),
+    "trailer-m2-killbox": ("--dev-mission2-game",
+            "Trailer Act II killbox take (bot: OS-12 hold + flank)"),
+    "trailer-m2-evidence": ("--dev-mission2-evidence",
+            "Trailer Act II evidence take (bot: control building)"),
+    "trailer-m3-breakout": ("--dev-mission3-game",
+            "Trailer Act III breakout take (bot: shiv/sidearm)"),
+    "trailer-m3-comms": ("--dev-mission3-comms",
+            "Trailer Act III relay take (bot: power->auth->tune, Volkov cover)"),
     # ── Misc ──
```

## 3. Diff `src/app.py` — `--trailer-bot` / `--trailer-act` flags + GAME.update hook

Keep the hook lazy (function-level import) so load order stays acyclic.

```diff
--- a/src/app.py
+++ b/src/app.py
@@ _apply_dev_args, after --jump handling
+    # Trailer bot flags (AI 1). Gated, off by default, never affects play.
+    if "--trailer-bot" in args:
+        # lazy: tools.trailer_bot owns _BOT_* state
+        from tools import trailer_bot as _bot
+        _bot.set_active(True)
+        _act = "act1"
+        for _i, _a in enumerate(raw):
+            if _a == "--trailer-act" and _i + 1 < len(raw):
+                _act = raw[_i + 1]
+            if _a.startswith("--trailer-act="):
+                _act = _a.split("=", 1)[1]
+        _bot.reset(_act)
@@ GAME.update, replace `cx, cy = gc.game_update(keys)`
-        cx, cy = gc.game_update(keys)
+        # Trailer bot injects aim + WASD before the sim steps (AI 1).
+        try:
+            from tools import trailer_bot as _bot
+            if _bot.is_active():
+                keys, _ = _bot.tick_bot(keys)
+        except Exception:
+            pass
+        cx, cy = gc.game_update(keys)
```

Why this injection point: `STATE.player.angle` is read by `handle_shoot/barrel_tip` and camera lookahead in the same frame; setting it before `game_update` gives exact-frame snap. Movement flows through the existing `keys[WASD] → player.move(dx,dy,solid_walls)` path so collision/footsteps stay canonical.

## 4. Per-act recording scripts (exact commands + bot expectations)

All captures 60fps, crosshair on, `auto_reload` OFF (bot calls `start_reload` on `reload` waypoints only).

### Act I — Warehouse breach/molotov

```powershell
python acaristan.py --jump m1 --trailer-bot --trailer-act act1
```

1. Bot sprint-taps patrol at `(6,5)→(6,7)`, commander lane `(10,11)`, hacks gate `(13,15)` via `E`.
2. Notebook waypoint auto-patched from `STATE.NOTEBOOK_POS`; bot `interact`s, breach `stage 1-5` runs (~390f).
3. Bot throws molotov at `(16,18)` mouth, holds `(15,18)` and double-taps bay rushers then rear flankers. Fire `weakness 1.15` guarantees visible panic-flee.
4. Bot exfils to `STATE.EXFIL_POS - 42px`, `interact` hotwire.
5. Re-take until: molotov bloom ring fully in frame + ≥2 kills inside fire.

### Act II — Killbox + evidence (sniper cinematic is NOT bot-played)

```powershell
python acaristan.py --jump m2-game --trailer-bot --trailer-act act2_killbox
python acaristan.py --jump m2-evidence --trailer-bot --trailer-act act2_evidence
```

1. Let the sniper cutscene (`regroup/movement_one/two/three`) play untouched — record clean for AI 2.
2. Post-cutscene bot takes OS-12 (`grant_seby_os12`), hops `covers (34,40)→(40,41)→(30,43)`, never exposed >90f (lock kills at 105f).
3. `reload` waypoint timed to Volkov-equivalent lull; then ditch-flank `(22,47)` push.
4. Evidence take: `E` at decree `(55,23)`, fight through `(63,19)`, `E` at packet `(59,14)`.

### Act III — Breakout + relay (Volkov staged as cover, never lead)

```powershell
python acaristan.py --jump m3-game --trailer-bot --trailer-act act3_breakout
python acaristan.py --jump m3-comms --trailer-bot --trailer-act act3_relay
```

1. Breakout: `melee` (shiv thrust peak `e≈0.5` + glint), loot sidearm on first kill, `tap2` next two guards. Shows `chair_leg 24f → shiv 14f → sidearm` arc.
2. Relay: bot leads every room entry; Volkov (`follow_dist 82`, auto-A* repath `15f`) trails and posts doorways with `cd32` cover fire. Bot `reload`/`swap` (24f anim) only under Volkov fire.
3. Tune hold: bot stands relay `360f` while Volkov holds — this is the trailer two-shot.

## 5. Bot-flaw masks (enforced in `tick_bot`, not optional)

- Full-speed or stopped — no analog drift (kills wander read).
- Instant aim snap + `±4px` jitter — never lerp (kills hesitate read).
- `tap2` only (`TAP_GAP 9f`); mag dumps forbidden except OS-12 holdout B-roll.
- `reload`/`swap` waypoints only in cover / under Volkov fire.
- Melee only inside `52px + ±60°` (resolver rejects the rest — a whiff on camera is a failed take).
- Molotov never across `solid_walls` line (bottle stops at wall clip — check frame before throw).
- Never cross `FireZone radius 48`; use it as a wall to funnel rushers.

## 6. Handoff to AI 2 (Editor) / AI 3 (Audio)

| TC | Cut on (AI 2) | Sound cue (AI 3) |
|---|---|---|
| 0:06 | First snap-kill casing eject | `gunshot` + `hit_stop` gap |
| 0:11→0:13 | Molotov apex → bloom ring | `molotov_throw` → `molotov_explode` + `explosion` 3D |
| 0:18 | `BAY DOOR BREACH!` text + 14-man rush | `door_rattle` → `breach`, `VASILE both sides` |
| 0:26 | Gabi crack (`m1 gabi_crack 300f`), no telegraph | `sniper_crack` + `dead_air 110f` + `tinnitus` |
| 0:31 | `MISSED—YOU'RE NEXT` callout | `bullet_snap` + `concrete_impact` + heartbeat |
| 0:34 | OS-12 pickup → `GET TO COVER` | `rifle_handle` + `combat_sting` |
| 0:38 | Tanker valve → shelter sprint | `terminal_glitch` → rising tone → blast |
| 0:43 | Shiv thrust-peak glint `e 0.44-0.60` | `melee_hit` + spark |
| 0:47 | Relay tune complete (green glow) | `elec_hum` resolve + `SYSTEM relay restored` |
| 0:52 | K-9 `swap 24f` midpoint + double kill | `gunshot` + `gunshot_distant` (Volkov) |
| 0:57 | Vostral take | `radio_static` + title hit |

Cut on `shake` peaks (`OS-12 28 / pistol 18 / sniper 52`), never on lerp tails. Keep letterbox only on authored M2 sniper + M3 breach cinematics.

## 7. Verify (gate)

```powershell
python tools/smoke_test.py
python -m compileall -q src
```

Must print `SMOKE TEST: OK` with zero new failures. Bot module is import-only in smoke (no gameplay branch taken without `--trailer-bot`), so golden signatures are unaffected.
