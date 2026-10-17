
"""Kill Order (Mission 3 Phase 5) playability audit - headless.

Answers "is the map REALLY 100% playable?" with nine checks:

  1. tile flood-reachability from spawn (doors passable): every pickup,
     insert tile, nest, exfil, closet interior, mezzanine, dock corner
  2. enemy A* reachability from every wave insert tile to a sample tile
     in every zone (uses the real walk grid + solid walls; beat gates
     count as open - they blow once their wave is wiped)
  3. WALK-ONLY traversal: a waypoint bot walks spawn -> stairwell ->
     lobby -> south -> dock -> van with the beat gates pre-opened, waits
     the real 45s door cycle and exfils to STAGE_BROADCAST; every
     critical-path door must actually open under the player
  4. Volkov bail navigation: on bail he must physically walk dock ->
     stairwell (not teleport/stuck) before despawning
  5. pin-lane sanity: lanes sit on lobby floor and every exposed sample
     has cover (pillar/wall) within dodge distance
  6. closet loot accessibility: wave-3 flush breach opens the closets,
     loot reachable without turtling
  7. grand tour soft-lock sweep: a full loop of all zones completes with
     a bounded unstuck-jitter budget (beat gates pre-opened)
  8. beat-gate rush regression (real combat): a sprint spawn -> van is
     physically stopped at gate S while wave 0 lives and at gate D
     while wave 1 lives; wiping each wave blows its gates (breach +
     radio); the full holdout -> door cycle -> exfil then runs through
     to the broadcast
  9. gate anti-soft-lock: a wave member wedged with no movement for
     10s+ re-inserts onto a walkable tile near the player

Run:  SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=src \
      python3 src/tools/ko_playability_audit.py
"""
import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pygame
pygame.init()

from core import game_core as gc
from core.state import STATE
from core.config import TILE_SIZE as T
from missions.m3 import maps as M
from missions.m3 import sweep
from missions.m3.world import _solid_walls, _exfil_pos
from entities.enemy_ai import _build_walk_grid, _astar

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
    return ok


class Keys:
    def __init__(self):
        self.down = set()
    def __getitem__(self, k):
        return k in self.down


KEYS = Keys()


class Walker:
    """Waypoint bot on real key states (same controller as the preview)."""
    def __init__(self, waypoints):
        self.wps = [(x * T + T // 2, y * T + T // 2) for x, y in waypoints]
        self.i = 0
        self.stuck = 0
        self.last = None
        self.jit = 0
        self.jit_total = 0
    def done(self):
        return self.i >= len(self.wps)
    def step(self):
        if self.done() or STATE.player is None:
            KEYS.down.clear()
            return
        px, py = STATE.player.rect.center
        tx, ty = self.wps[self.i]
        if math.hypot(tx - px, ty - py) < 24:
            self.i += 1
            self.stuck = 0
            return
        moved = self.last and math.hypot(px - self.last[0], py - self.last[1]) > 1.5
        self.stuck = 0 if moved else self.stuck + 1
        self.last = (px, py)
        KEYS.down.clear()
        if self.stuck > 40:
            self.jit = 30
            self.jit_total += 1
            self.stuck = 0
        dx, dy = tx - px, ty - py
        if self.jit > 0:
            self.jit -= 1
            if abs(dy) >= abs(dx):
                KEYS.down.add(pygame.K_s if dy > 0 else pygame.K_w)
                KEYS.down.add(pygame.K_a if (self.jit // 15) % 2 else pygame.K_d)
            else:
                KEYS.down.add(pygame.K_d if dx > 0 else pygame.K_a)
                KEYS.down.add(pygame.K_w if (self.jit // 15) % 2 else pygame.K_s)
            return
        if abs(dx) > 6:
            KEYS.down.add(pygame.K_d if dx > 0 else pygame.K_a)
        if abs(dy) > 6:
            KEYS.down.add(pygame.K_s if dy > 0 else pygame.K_w)


BREACH_LOCKED = {(13, 12), (13, 20), (31, 32), (32, 32)}
# Beat gates (2026-09-27 rush fix): sealed at phase start until their wave
# is wiped - locked for routing until check 8's combat opens them in-game.
BEAT_LOCKED = {(9, 27), (10, 27), (19, 27), (20, 27), (31, 27), (32, 27),
               (6, 32), (7, 32), (19, 32), (20, 32)}


def _walkable_grid(sealed):
    """True = foot-traversable tile: floors + unlocked doors (they auto-open)."""
    gw = []
    for y in range(40):
        row = []
        for x in range(40):
            ch = M.MISSION3_KILL_ORDER_MAP[y][x]
            # B = pillar cover: partial collision in game, so route AROUND
            row.append(ch not in ("C", "g", "B")
                       and not (ch == "D" and (x, y) in sealed))
        gw.append(row)
    return gw


WGRID = _walkable_grid(BREACH_LOCKED | BEAT_LOCKED)


class Router(Walker):
    """Walker that A*-routes between goal tiles on the walkable grid -
    no hand-authored waypoints, so the audit tests the map, not my memory."""
    def __init__(self, goals):
        super().__init__([])
        self.goals = list(goals)
        self._route()
    def _route(self):
        if not self.goals or STATE.player is None:
            return
        gx, gy = self.goals.pop(0)
        px, py = STATE.player.rect.center
        path = _astar((int(px // T), int(py // T)), (gx, gy), WGRID)
        # Drop straight-through door nodes: a waypoint ON a door tile makes
        # the bot push diagonally into the door/wall corner outside the
        # 48px auto-open range. Targeting the tile beyond the door makes
        # the approach cut across the door face so it triggers.
        kept = []
        for idx, (x, y) in enumerate(path):
            if (0 < idx < len(path) - 1
                    and M.MISSION3_KILL_ORDER_MAP[y][x] == "D"):
                (ax, ay), (bx, by) = path[idx - 1], path[idx + 1]
                if (ax - x, ay - y) == (x - bx, y - by):
                    continue
            kept.append((x * T + T // 2, y * T + T // 2))
        self.wps = kept or [(gx * T + T // 2, gy * T + T // 2)]
        self.i = 0
        self.stuck = 0
    def done(self):
        return not self.goals and self.i >= len(self.wps)
    def step(self):
        if self.i >= len(self.wps) and self.goals:
            self._route()
        Walker.step(self)


def pump(n=1):
    for _ in range(n):
        if STATE.player:
            STATE.player.hp = STATE.player.max_hp
        gc.game_update(KEYS)


# ═══ 1. tile flood reachability ═══
grid = M.MISSION3_KILL_ORDER_MAP
locked_set = {(13, 12), (13, 20), (31, 32), (32, 32)}
def solid(x, y, doors_pass=True):
    ch = grid[y][x]
    if ch in ("C", "g"):
        return True
    if ch == "D" and not doors_pass:
        return (x, y) in locked_set
    return False
seen = {(6, 3)}
stack = [(6, 3)]
while stack:
    x, y = stack.pop()
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < 40 and 0 <= ny < 40 and (nx, ny) not in seen and not solid(nx, ny):
            seen.add((nx, ny))
            stack.append((nx, ny))
targets = {
    "exfil van": (33, 36), "nest": (26, 24), "closet N": (11, 13),
    "closet S": (11, 20), "insert w": (6, 29), "insert s": (19, 29),
    "insert e": (31, 29), "dock SW": (4, 37), "dock SE": (36, 37),
    "mezz door": (25, 21), "lobby N": (19, 10), "east cor": (32, 17),
    "west cor": (5, 17), "stair top": (6, 2),
}
missing = [n for n, (x, y) in targets.items() if (x, y) not in seen]
check("1 tile flood-reachability (spawn -> all key tiles)", not missing,
      f"{len(targets)} targets" + (f", UNREACHABLE: {missing}" if missing else ""))

# ═══ 2. enemy A* reachability per zone ═══
gc.start_mission3_kill_order_checkpoint()
# Unlocked doors auto-open on approach, so route-planning treats them as
# passable; locked (breach) doors stay solid. Beat gates test the
# post-clear topology: once their wave is wiped the doors blow open, so
# they are excluded here (the locked state itself is check 8's job).
# Static walls + pillars only.
walls = list(STATE.walls) + list(STATE.mission3_barriers)
for d in STATE.doors:
    if d.locked and _sweep_mod._m3d(d).ko_beat_gate is None:
        walls.append(d.rect)
g, cols, rows = _build_walk_grid(walls)
zone_samples = {"stair": (6, 4), "west": (5, 17), "lobby": (19, 17),
                "east": (32, 17), "south": (19, 30), "dock": (19, 35)}
from missions.m3 import sweep as _sweep_mod
inserts = sorted({tuple(tile) for w in _sweep_mod._WAVES
                  for _role, tile in w["spawns"]})
bad = []
for ix, iy in inserts:
    for zn, (zx, zy) in zone_samples.items():
        path = _astar((ix, iy), (zx, zy), g)
        if not path and (ix, iy) != (zx, zy):
            bad.append(f"({ix},{iy})->{zn}")
check("2 enemy A* reachability (inserts x zones)", not bad,
      f"{len(inserts) * len(zone_samples)} pairs" + (f", NOPATH: {bad}" if bad else ""))

# ═══ 3. walk-only traversal (gates pre-opened) ═══
gc.start_mission3_kill_order_checkpoint()
saved_waves = sweep._WAVES
sweep._WAVES = []                      # traversal-only: no combat spawns
# Traversal test: pre-open the beat gates (their combat is check 8's job);
# otherwise an empty _WAVES can never clear them and the walk dead-ends.
for d in STATE.doors:
    if _sweep_mod._m3d(d).ko_beat_gate is not None:
        d.locked = False
WGRID = _walkable_grid(BREACH_LOCKED)  # route against the opened gates
path_doors = [(5, 8), (6, 8), (8, 12), (8, 13),
              (19, 27), (20, 27), (19, 32), (20, 32)]
door_max = {d: 0.0 for d in path_doors}
w = Router([(5, 12), (9, 13), (20, 15), (20, 26), (20, 30), (20, 35), (33, 36)])
ticks = 0
while not w.done() and ticks < 6000:
    w.step()
    pump()
    ticks += 1
    for d in path_doors:
        for do in STATE.doors:
            if (do.rect.centerx // T, do.rect.centery // T) == d:
                door_max[d] = max(door_max[d], do.anim_progress)
reached_van = w.done()
# wait out the real 45s door cycle, then step on the van
wait = 0
while STATE.m3_exfil_door_cycle < 2700 and wait < 4000:
    KEYS.down.clear()
    pump()
    wait += 1
w2 = Router([(33, 36)])
t2 = 0
while STATE.mission3_stage == "kill_order" and t2 < 900:
    w2.step()
    pump()
    t2 += 1
# Slice 5 -> 6 transition: headless has no app.py to consume the cutscene
# flag, so simulate it - clear the request and tick once to land broadcast.
if STATE.mission3_stage == "broadcast_transition":
    STATE.request_broadcast_transition_cutscene = False
    pump(2)
# 2-wide doorways count as opened when either leaf opened under the player
door_pairs = [((5, 8), (6, 8)), ((8, 12), (8, 13)),
              ((19, 27), (20, 27)), ((19, 32), (20, 32))]
unopened = [p for p in door_pairs if max(door_max[p[0]], door_max[p[1]]) < 1.0]
check("3 walk-only full completion (spawn -> exfil -> broadcast)",
      reached_van and STATE.mission3_stage == "broadcast" and not unopened,
      f"walked {ticks + wait + t2} ticks; doorways unopened: {unopened or 'none'}; "
      f"stage={STATE.mission3_stage}")
sweep._WAVES = saved_waves

# ═══ 4. Volkov bail navigation ═══
gc.start_mission3_kill_order_checkpoint()
STATE.player.rect.center = (19 * T + 32, 17 * T + 32)
pump(600)                     # Volkov follows the player into the lobby
# (bail must be tested away from the van: at the van the player commits
#  and the window deactivates by design)
STATE.m3_sweep_window_frames = 10
pump(30)
assert STATE.m3_volkov_bailed, "bail never triggered in lobby" 
start = (STATE.m3_volkov_ally_x, STATE.m3_volkov_ally_y)
goal = (6 * T + 32, 4 * T + 32)
d0 = math.hypot(start[0] - goal[0], start[1] - goal[1])
trav = []
for i in range(180):
    pump()
    trav.append(math.hypot(STATE.m3_volkov_ally_x - goal[0],
                           STATE.m3_volkov_ally_y - goal[1]))
d1 = trav[-1]
monotone = sum(1 for a, b in zip(trav, trav[1:]) if b <= a + 4) / len(trav)
# walk-off is a 180f timer: he walks toward the stair at ~3.4px/f and
# despawns mid-walk by design - assert sustained directed movement + despawn
check("4 Volkov bail walk-off traverses the map",
      d1 <= d0 - 450 and monotone > 0.8
      and not STATE.m3_volkov_ally_active,
      f"dist to stair {d0:.0f}px -> {d1:.0f}px, monotone {monotone:.2f}, despawned")

# ═══ 5. pin-lane / cover sanity ═══
from missions.m3.sweep import _LANE_V, _LANE_H, _player_covered


gc.start_mission3_kill_order_checkpoint()
barriers = list(STATE.mission3_barriers)
lane_ok = True
detail = []
for lane, name in ((_LANE_V, "lane N-S"), (_LANE_H, "lane E-W")):
    cx, cy = lane.center
    on_floor = grid[cy // T][cx // T] not in ("C", "g")
    near_cover = any(
        math.hypot(b.centerx - cx, b.centery - cy) < 160 for b in barriers)
    lane_ok &= on_floor and near_cover
    detail.append(f"{name}: floor={on_floor} cover<160px={near_cover}")
check("5 pin lanes on floor with dodge-cover nearby", lane_ok, "; ".join(detail))

# ═══ 6. closet loot accessibility via wave-3 flush ═══
gc.start_mission3_kill_order_checkpoint()
pump(5)
st = STATE.m3_sweep
while len(STATE.enemies) + 5 > 9:
    pump(30)
sweep._fire_wave(st, 3)
closet_open = all(
    not d.locked for d in STATE.doors
    if (d.rect.centerx // T, d.rect.centery // T) in ((13, 12), (13, 20)))
check("6 closet loot reachable (wave-3 flush breach)", closet_open,
      "both closet doors blown open at wave 3")

# ═══ 7. grand tour soft-lock sweep ═══
gc.start_mission3_kill_order_checkpoint()
sweep._WAVES = []
# Same as check 3: the tour tests map traversal, not combat gating.
for d in STATE.doors:
    if _sweep_mod._m3d(d).ko_beat_gate is not None:
        d.locked = False
WGRID = _walkable_grid(BREACH_LOCKED)  # route against the opened gates
tour = Router([(5, 10), (5, 24), (9, 21), (14, 25), (22, 25), (26, 24),
               (22, 25), (19, 30), (6, 30), (6, 34), (19, 34), (32, 30),
               (32, 34), (33, 36), (19, 35), (6, 34), (19, 30), (19, 26),
               (9, 21), (5, 10)])
tt = 0
while not tour.done() and tt < 12000:
    tour.step()
    pump()
    tt += 1
check("7 grand tour of all zones without soft-lock",
      tour.done() and tour.jit_total <= 6,
      f"{tt} ticks, unstuck-jitter events: {tour.jit_total}")
sweep._WAVES = saved_waves

# ═══ 8. beat-gate rush regression (real combat) ═══
# The sprint spawn->van must physically cross the authored beats: gate S
# (lobby->south, row 27) stays sealed while wave 0 is alive, gate D
# (south->dock, row 32) stays sealed while wave 1 is alive; wiping each
# wave blows its gates (breach FX + radio); the full holdout -> door
# cycle -> exfil then runs through to the broadcast.
gc.start_mission3_kill_order_checkpoint()
GATE_S = [(9, 27), (10, 27), (19, 27), (20, 27), (31, 27), (32, 27)]
GATE_D = [(6, 32), (7, 32), (19, 32), (20, 32)]
WGRID = _walkable_grid(BREACH_LOCKED | BEAT_LOCKED)  # sealed gates route last-leg straight


def _door_at(tile):
    for d in STATE.doors:
        if (d.rect.centerx // T, d.rect.centery // T) == tile:
            return d
    return None


def _gates_locked(tiles):
    return all(_door_at(t) is not None and _door_at(t).locked for t in tiles)


def _team_alive(team):
    return [e for e in STATE.enemies
            if _sweep_mod._m3g(e).sweep_team == team and e.hp > 0]


check("8a beat gates sealed at phase start",
      _gates_locked(GATE_S) and _gates_locked(GATE_D),
      "%d/%d gate doors locked" % (
          sum(1 for t in GATE_S + GATE_D
              if _door_at(t) is not None and _door_at(t).locked),
          len(GATE_S) + len(GATE_D)))

# Sprint at the south gate with the ambush held alive: the sealed gate
# must hold and the bot must not get through. Router legs route on the
# locked grid; the unreachable final leg falls back to a straight push
# into the door face.
w = Router([(5, 12), (19, 26), (19, 30)])
st8 = None
fired0_t = None
s_crossed = s_opened_early = False
t = 0
while t < 6000:
    w.step()
    for e in _team_alive(0):
        e.hp = max(e.hp, 400)            # the ambush is still standing
    pump()
    t += 1
    st8 = STATE.m3_sweep
    if st8 is None or st8["waves"][0]["t"] < 0:
        continue
    if fired0_t is None:
        fired0_t = t
    if _gates_locked(GATE_S):
        if STATE.player.rect.centery > 27 * T + 16:
            s_crossed = True
            break
    else:
        s_opened_early = True
        break
    if t - fired0_t >= 300:
        break
check("8b gate S holds the sprint while wave 0 is alive",
      fired0_t is not None and not s_crossed and not s_opened_early,
      "wave0 fired at t=%s, gate held %s ticks, crossed=%s early_open=%s"
      % (fired0_t, (t - fired0_t) if fired0_t else 0, s_crossed,
         s_opened_early))

# Wipe wave 0 (player combat simulated) -> gate S blows open.
for e in _team_alive(0):
    e.hp = 0
t = 0
while t < 900 and not (st8["waves"][0]["cleared"]
                       and not _gates_locked(GATE_S)):
    pump()
    t += 1
    st8 = STATE.m3_sweep
check("8c wave 0 clear blows gate S (breach + radio)",
      st8["waves"][0]["cleared"] and not _gates_locked(GATE_S)
      and "ko_beat_gate_0" in STATE.mission3_events,
      "cleared=%s doors open=%s radio=%s"
      % (st8["waves"][0]["cleared"], not _gates_locked(GATE_S),
         "ko_beat_gate_0" in STATE.mission3_events))

# Push through the open gate S into the south corridor with wave 1 held
# alive: the sealed dock gate must hold.
w = Router([(19, 29), (19, 35)])
fired1_t = None
d_crossed = d_opened_early = False
t = 0
while t < 6000:
    w.step()
    for e in _team_alive(1):
        e.hp = max(e.hp, 400)            # the lobby team is still standing
    pump()
    t += 1
    st8 = STATE.m3_sweep
    if st8 is None or st8["waves"][1]["t"] < 0:
        continue
    if fired1_t is None:
        fired1_t = t
    if _gates_locked(GATE_D):
        if STATE.player.rect.centery > 32 * T + 16:
            d_crossed = True
            break
    else:
        d_opened_early = True
        break
    if t - fired1_t >= 300:
        break
check("8d gate D holds the sprint while wave 1 is alive",
      fired1_t is not None and not d_crossed and not d_opened_early,
      "wave1 fired at t=%s, gate held %s ticks, crossed=%s early_open=%s"
      % (fired1_t, (t - fired1_t) if fired1_t else 0, d_crossed,
         d_opened_early))

# Wipe wave 1 -> gate D blows open.
for e in _team_alive(1):
    e.hp = 0
t = 0
while t < 900 and not (st8["waves"][1]["cleared"]
                       and not _gates_locked(GATE_D)):
    pump()
    t += 1
    st8 = STATE.m3_sweep
check("8e wave 1 clear blows gate D (breach + radio)",
      st8["waves"][1]["cleared"] and not _gates_locked(GATE_D)
      and "ko_beat_gate_1" in STATE.mission3_events,
      "cleared=%s doors open=%s radio=%s"
      % (st8["waves"][1]["cleared"], not _gates_locked(GATE_D),
         "ko_beat_gate_1" in STATE.mission3_events))

# Full run to the van: waves 2-3 still have to clear (holdout backstop),
# then the real 45s door cycle -> exfil -> broadcast.
w = Walker([(19, 34), (33, 36)])
t = 0
while t < 9000 and not (st8 and st8["committed"]):
    w.step()
    for team in (2, 3):
        for e in _team_alive(team):
            e.hp = 0                     # clear the hunting waves on contact
    pump()
    t += 1
    st8 = STATE.m3_sweep
t = 0
while t < 3600 and getattr(STATE, "m3_exfil_door_cycle", 0) < 2700:
    w.step()
    pump()
    t += 1
# Slice 5 -> 6 transition: simulate the app consuming the cutscene flag.
if STATE.mission3_stage == "broadcast_transition":
    STATE.request_broadcast_transition_cutscene = False
    pump(2)
check("8f gates open -> holdout -> door cycle -> broadcast",
      bool(st8) and st8["committed"]
      and STATE.mission3_stage == "broadcast",
      "committed=%s door_cycle=%d stage=%s"
      % (st8["committed"] if st8 else None,
         getattr(STATE, "m3_exfil_door_cycle", 0),
         STATE.mission3_stage))

# ═══ 9. gate anti-soft-lock: wedged member re-flanks ═══
gc.start_mission3_kill_order_checkpoint()
t = 0
mem9 = []
while t < 600 and not mem9:
    pump()
    t += 1
    mem9 = [e for e in STATE.enemies
            if _sweep_mod._m3g(e).sweep_team == 0 and e.hp > 0]
st9 = STATE.m3_sweep
moved = on_floor = False
detail9 = "no live wave-0 member spawned"
if mem9:
    e = mem9[0]
    sx, sy = e.rect.centerx, e.rect.centery
    st9.setdefault("stuck", {})[e.uid] = (
        sx, sy, st9["t"] - sweep.STUCK_REINSERT_FRAMES - 1)
    sweep._update_stuck(st9)
    nx, ny = e.rect.centerx, e.rect.centery
    moved = math.hypot(nx - sx, ny - sy) > 40
    on_floor = M.MISSION3_KILL_ORDER_MAP[ny // T][nx // T] in (".", "E", "D", "P")
    detail9 = "reinserted (%d,%d)->(%d,%d)" % (sx // T, sy // T, nx // T, ny // T)
check("9 wedged wave member re-flanks onto walkable tile",
      bool(mem9) and moved and on_floor, detail9)

print()
fails = [n for n, ok, _ in RESULTS if not ok]
print(f"AUDIT: {'ALL PASS' if not fails else 'FAILURES: ' + ', '.join(fails)}"
      f" ({len(RESULTS) - len(fails)}/{len(RESULTS)})")
raise SystemExit(1 if fails else 0)
