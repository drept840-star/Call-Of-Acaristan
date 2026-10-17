"""Mission 5 - part module. See __init__.py for the package facade.

World construction + shared position/objective helpers for Mission 5,
plus the Maru escort ally. Idioms ported from missions.m4.world (wall
parsing, guard spawns, radio/objective helpers, tile-BFS ally pathing) -
ported, NOT imported: m4 globals are mission-scoped (one-owner rule).
"""

import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
from collections import deque

import pygame

from core.config import (ENEMY_DAMAGE, TILE_SIZE)
from core.state import STATE
from core import config as _config
from entities.player import Player
from entities.enemy_ai import Enemy

audio = _config.audio

from missions.m5 import maps as _m5_maps  # owner of MISSION5_MAP/_objective/_radio_marks
from missions.m5.meta import (
    M5_SOLID_CHARS, M5_ROLE_TUNING,
    QUARTER_START_TILE, PRINTWORKS_DOOR_TILE, QUARTER_GUARDS,
    PRINT_START_TILE, MARU_TILE, BASEMENT_STAIR_TILE, RAID_INSERTION_TILES,
    TUNNEL_START_TILE, TUNNEL_MARU_START_TILE, RIVER_GATE_TILE,
    TUNNEL_PURSUIT_TILES,
    HQ_START_TILE, VASILE_TILE, VASILE_DESK_FRONT_TILE, HQ_NPCS,
    HQ_BARK_RADIUS,
    M5_RAID_MAX_CONCURRENT, M5_MARU_MAX_HP, M5_MARU_SPEED, M5_MARU_LEASH,
    STAGE_QUARTER, STAGE_PRINTWORKS, STAGE_RAID, STAGE_TUNNEL,
    C_SYSTEM, C_MARU, C_VASILE, STAGE_HQ,
)
import game.world as _gw  # RPE6 Phase 5 (D4): mission data lives in components
from missions.m5.components import M5Guard as _M5Guard


def _m5g(e):
    """Declared M5 data of an enemy (replaces the ad hoc ``e.m5_*`` attributes)."""
    return _gw.ensure(e, _M5Guard)


PLAYER_MAX_HP = 115


# ─────────────────────────────────────────────
# Position helpers
# ─────────────────────────────────────────────
def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _player_pos():
    if not STATE.player:
        return (0, 0)
    return STATE.player.rect.centerx, STATE.player.rect.centery


def _near(pos, radius=80):
    return bool(STATE.player) and _dist(_player_pos(), pos) <= radius


def _tile_world(col, row):
    """Center of a tile, in world px."""
    return (col * TILE_SIZE + TILE_SIZE // 2, row * TILE_SIZE + TILE_SIZE // 2)


def _vasile_desk_pos():
    """Where Biribel stands to report (in front of Vasile's desk)."""
    return _tile_world(*VASILE_DESK_FRONT_TILE)


def _vasile_pos():
    return _tile_world(*VASILE_TILE)


def _printworks_door_pos():
    return _tile_world(*PRINTWORKS_DOOR_TILE)


def _maru_office_pos():
    return _tile_world(*MARU_TILE)


def _stair_pos():
    return _tile_world(*BASEMENT_STAIR_TILE)


def _river_gate_pos():
    return _tile_world(*RIVER_GATE_TILE)


# ─────────────────────────────────────────────
# Collision
# ─────────────────────────────────────────────
def _solid_walls():
    """All solid collision rects for this frame (STATE.walls + barriers)."""
    out = list(STATE.walls)
    out.extend(getattr(STATE, "m5_barriers", []))
    for d in getattr(STATE, "doors", []):
        if getattr(d, "collision_rect", None):
            out.append(d.collision_rect)
    return out


# ─────────────────────────────────────────────
# Objective / radio helpers
# ─────────────────────────────────────────────
def _set_objective(text):
    _m5_maps._objective = text


def _movement_locked():
    if getattr(STATE, "player_dead", False):
        return True
    if getattr(STATE, "m5_dialogue_active", False):
        return True
    return False


# Authored navigation/escort information only. Descriptive street/HQ barks
# are already communicated by the scenery, objectives and cinematics.
# New urgent tactical calls can opt in explicitly with priority > 0.
M5_RADIO_ESSENTIAL_MARKS = frozenset({
    "hq_enter", "start_vasile", "pw_enter", "raid_over", "tunnel_enter",
    "maru_fail", "stair_wait", "gate_wait", "maru_leash",
})


def _radio(text, color=C_SYSTEM, duration=320, mark=None, priority=0):
    """Curated M5 radio; dedup keys do not make incidental barks critical."""
    if priority <= 0 and mark not in M5_RADIO_ESSENTIAL_MARKS:
        return
    if mark and mark in _m5_maps._radio_marks:
        return
    if mark:
        _m5_maps._radio_marks.add(mark)
    try:
        from core.interactions import trigger_radio_chatter
        trigger_radio_chatter(text, color=color, duration=duration,
                              priority=max(priority, 1) if mark in M5_RADIO_ESSENTIAL_MARKS else priority)
    except Exception:
        pass  # optional in headless harnesses


def _sfx(name, volume):
    try:
        audio.play(name, volume=volume)
    except Exception:
        pass


# ─────────────────────────────────────────────
# Enemy spawns (Presidential Guard troopers)
# ─────────────────────────────────────────────
def _spawn_m5_guard(x, y, etype="guard", label="", aware=False):
    """Typed Guard trooper. Tagged m5_guard (draw: black + red armband)."""
    tuning = M5_ROLE_TUNING.get(etype, M5_ROLE_TUNING["guard"])
    e = Enemy(x, y)
    e.hp = tuning["hp"]
    e.speed = tuning["speed"]
    g = _m5g(e)                      # declared M5 data (component), not attributes on the Enemy
    g.guard = True
    g.kind = etype
    g.label = label
    g.stage = getattr(STATE, "mission5_stage", None)
    g.counted = False
    e.alerted = bool(aware)
    STATE.enemies.append(e)
    return e


def _arm_hunt(e):
    e.alerted = True
    e.state = "CHASE"
    e.combat_alert_timer = 420
    e.path = []
    e.path_timer = 0
    if STATE.player is not None:
        e.last_seen_pos = (STATE.player.rect.centerx, STATE.player.rect.centery)


def _register_guard_kill(e):
    """Call once per dead enemy (W3 systems). Only Lower Quarter kills feed
    STATE.m5_guard_kills (the mercy tally M8 reads). Idempotent per enemy."""
    if _m5g(e).counted:
        return False
    _m5g(e).counted = True
    if _m5g(e).stage == STAGE_QUARTER:
        STATE.m5_guard_kills = getattr(STATE, "m5_guard_kills", 0) + 1
        return True
    return False


# ─────────────────────────────────────────────
# World builders
# ─────────────────────────────────────────────
def _reset_world_lists():
    STATE.walls = []
    STATE.enemies = []
    STATE.pickups = []
    STATE.blood_decals = []
    STATE.bullets = []
    STATE.casings = []
    STATE.particles = []
    STATE.floating_texts = []
    STATE.fire_zones = []
    STATE.m5_barriers = []
    STATE.doors = []
    STATE.player = None
    STATE.m5_maru = None
    STATE.m5_squad_timer = 0
    STATE.m5_squads_sent = 0
    STATE.m5_hq_npcs = []


def _parse_grid(g, spawn_guards=True):
    """Walls/barriers from the grid; player on "P"; guards on "E"/"M"."""
    for row_idx, row in enumerate(g):
        for col_idx, tile in enumerate(row):
            x, y = col_idx * TILE_SIZE, row_idx * TILE_SIZE
            if tile == "C":
                STATE.walls.append(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE))
            elif tile in ("B", "H"):
                r = pygame.Rect(x + 4, y + 8, TILE_SIZE - 8, TILE_SIZE - 16)
                STATE.walls.append(r)
                STATE.m5_barriers.append(r)
            elif tile == "P":
                STATE.player = Player(x + 16, y + 16, max_hp=PLAYER_MAX_HP)
            elif tile in ("E", "M") and spawn_guards:
                _spawn_m5_guard(x + TILE_SIZE // 2, y + TILE_SIZE // 2,
                                etype="marksman" if tile == "M" else "guard",
                                label="q_{}_{}".format(col_idx, row_idx))
    return STATE.player


def _fallback_player(tile):
    if STATE.player is None:
        sx, sy = tile
        STATE.player = Player(sx * TILE_SIZE + 16, sy * TILE_SIZE + 16,
                              max_hp=PLAYER_MAX_HP)
    return STATE.player


def _build_hq_world():
    """Guard HQ walk (STAGE_HQ). No guards, no combat: squadmates in new
    armbands (proximity barks) and Vasile behind his new desk."""
    _reset_world_lists()
    STATE.mission5_stage = STAGE_HQ
    _parse_grid(_m5_maps.MISSION5_HQ_MAP, spawn_guards=False)
    npcs = []
    for c, r, name, armband, line in HQ_NPCS:
        x, y = _tile_world(c, r)
        npcs.append({"name": name, "x": float(x), "y": float(y),
                     "angle": math.pi / 2, "armband": bool(armband),
                     "line": line, "said": False,
                     "prop": name == "EMPTY LOCKER", "vasile": False})
    vx, vy = _vasile_pos()
    npcs.append({"name": "VASILE", "x": float(vx), "y": float(vy),
                 "angle": math.pi / 2, "armband": True, "line": "",
                 "said": True, "prop": False, "vasile": True,
                 "color": C_VASILE})
    STATE.m5_hq_npcs = npcs
    return _fallback_player(HQ_START_TILE)


def _update_hq_barks():
    """Walking-sim barks: each squadmate speaks once when Biribel passes.
    Returns the name that spoke this frame (or None)."""
    for n in getattr(STATE, "m5_hq_npcs", []) or []:
        if n["said"] or not n["line"]:
            continue
        if _near((n["x"], n["y"]), radius=HQ_BARK_RADIUS):
            n["said"] = True
            text = (n["line"] if n["prop"]
                    else "{}: {}".format(n["name"], n["line"]))
            _radio(text, color=C_SYSTEM, duration=300,
                   mark="hq_" + n["name"].lower().replace(" ", "_"))
            return n["name"]
    return None


def _build_quarter_world():
    """Lower Quarter streets (STAGE_QUARTER). Patrol flags from QUARTER_GUARDS."""
    _reset_world_lists()
    STATE.mission5_stage = STAGE_QUARTER
    _parse_grid(_m5_maps.MISSION5_QUARTER_MAP)
    patrols = {(c, r) for c, r, _k, p in QUARTER_GUARDS if p}
    for e in STATE.enemies:
        c, r = e.rect.centerx // TILE_SIZE, e.rect.centery // TILE_SIZE
        if (c, r) in patrols:
            # Short back-and-forth beat along the lane.
            a = _tile_world(c, r)
            b = _tile_world(c + (2 if c < 38 else -2), r)
            e.patrol_points = [a, b] if _tile_walkable(c + (2 if c < 38 else -2), r) else [a]
            e.state = "PATROL"
    return _fallback_player(QUARTER_START_TILE)


def _build_print_world():
    """Print works interior (STAGE_PRINTWORKS / STAGE_RAID). No guards until
    the raid; Maru waits in the back office."""
    _reset_world_lists()
    _parse_grid(_m5_maps.MISSION5_PRINT_MAP, spawn_guards=False)
    _fallback_player(PRINT_START_TILE)
    _init_maru(MARU_TILE)
    return STATE.player


def _build_tunnel_world():
    """Basement tunnel (STAGE_TUNNEL). Maru escorted from the landing."""
    _reset_world_lists()
    _parse_grid(_m5_maps.MISSION5_TUNNEL_MAP, spawn_guards=False)
    _fallback_player(TUNNEL_START_TILE)
    _init_maru(TUNNEL_MARU_START_TILE, following=True)
    return STATE.player


def _tile_walkable(c, r):
    g = _m5_maps.MISSION5_MAP
    if not (0 <= r < len(g) and 0 <= c < len(g[0])):
        return False
    return g[r][c] not in M5_SOLID_CHARS


# ─────────────────────────────────────────────
# Squad spawns (raid insertions / tunnel pursuit)
# ─────────────────────────────────────────────
def _squad_alive_count():
    return sum(1 for e in STATE.enemies
               if _m5g(e).squad and e.hp > 0)


def _spawn_squad(tiles, label, size=2, cap=M5_RAID_MAX_CONCURRENT):
    """Commit a small aware squad on a random walkable tile from `tiles`.
    Never exceeds `cap` alive squad members. Returns spawned enemies."""
    out = []
    tiles = list(tiles)
    _rng_legacy.shuffle(tiles)
    for c, r in tiles:
        if not _tile_walkable(c, r):
            continue
        x, y = _tile_world(c, r)
        for i in range(size):
            if _squad_alive_count() >= cap:
                break
            etype = "raider" if i == 0 else "guard"
            e = _spawn_m5_guard(x + i * 6, y + i * 4, etype=etype,
                                label="{}_{}".format(label, STATE.m5_squads_sent),
                                aware=True)
            _m5g(e).squad = True
            _arm_hunt(e)
            out.append(e)
        break
    if out:
        STATE.m5_squads_sent = getattr(STATE, "m5_squads_sent", 0) + 1
        _sfx("footstep", 0.35)
    return out


def _spawn_raid_squad():
    return _spawn_squad(RAID_INSERTION_TILES, "raid")


def _spawn_pursuit_squad():
    return _spawn_squad(TUNNEL_PURSUIT_TILES, "pursuit", size=2, cap=4)


# ─────────────────────────────────────────────
# Maru (escort ally)
# ─────────────────────────────────────────────
def _init_maru(tile, following=False):
    x, y = _tile_world(*tile)
    STATE.m5_maru = {
        "name": "MARU", "x": float(x), "y": float(y),
        "angle": math.pi / 2, "color": C_MARU,
        "hp": getattr(STATE, "m5_maru_hp", 0) or M5_MARU_MAX_HP,
        "max_hp": M5_MARU_MAX_HP,
        "following": bool(following), "waiting": False,
        "hit_flash": 0, "path": [], "path_goal": None, "stuck": 0,
        "weapon": "pistol",
    }
    STATE.m5_maru_hp = STATE.m5_maru["hp"]
    return STATE.m5_maru


def friendly_npcs():
    """[(name, (x, y), color, facing_rad, weapon)] live ally view (draw)."""
    m = getattr(STATE, "m5_maru", None)
    if not m or getattr(STATE, "m5_maru_dead", False):
        return []
    return [(m["name"], (m["x"], m["y"]), m["color"], m["angle"], m["weapon"])]


_ALLY_SIZE = 24
_ALLY_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1),
                    (1, 1), (1, -1), (-1, 1), (-1, -1))


def _ally_slide(ax, ay, mx, my, walls):
    actor = pygame.Rect(0, 0, _ALLY_SIZE, _ALLY_SIZE)
    actor.center = (round(ax), round(ay))
    actor.x += round(mx)
    for wall in walls:
        if actor.colliderect(wall):
            if mx > 0:
                actor.right = wall.left
            elif mx < 0:
                actor.left = wall.right
    actor.y += round(my)
    for wall in walls:
        if actor.colliderect(wall):
            if my > 0:
                actor.bottom = wall.top
            elif my < 0:
                actor.top = wall.bottom
    return float(actor.centerx), float(actor.centery)


def _ally_find_path(ax, ay, goal, walls):
    """Tile BFS (8-way, no corner cutting) -> world-px waypoints or None."""
    w, h = _m5_maps._live_map_dims()
    start = (int(ax) // TILE_SIZE, int(ay) // TILE_SIZE)
    goal = (int(goal[0]), int(goal[1]))
    if start == goal:
        return [_tile_world(*goal)]
    cache = {}

    def free(c, r):
        if (c, r) == goal:
            return True
        k = (c, r)
        v = cache.get(k)
        if v is None:
            if 0 <= c < w and 0 <= r < h:
                probe = pygame.Rect(0, 0, _ALLY_SIZE, _ALLY_SIZE)
                probe.center = _tile_world(c, r)
                v = probe.collidelist(walls) == -1
            else:
                v = False
            cache[k] = v
        return v

    prev = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur == goal:
            break
        c, r = cur
        for dc, dr in _ALLY_NEIGHBOURS:
            nxt = (c + dc, r + dr)
            if nxt in prev or not free(*nxt):
                continue
            if dc and dr and not (free(c + dc, r) and free(c, r + dr)):
                continue
            prev[nxt] = cur
            q.append(nxt)
    if goal not in prev:
        return None
    nodes, node = [], goal
    while node is not None:
        nodes.append(node)
        node = prev[node]
    nodes.reverse()
    return [_tile_world(c, r) for c, r in nodes[1:]]


def _maru_step(m, goal_tile, step, walls):
    """One frame along the BFS route to goal_tile. Re-plans when the goal
    tile changes or Maru gets stuck. Returns True when arrived."""
    if m.get("path_goal") != goal_tile:
        m["path"] = _ally_find_path(m["x"], m["y"], goal_tile, walls) or []
        m["path_goal"] = goal_tile
        m["stuck"] = 0
    path = m["path"]
    while path and math.hypot(path[0][0] - m["x"], path[0][1] - m["y"]) <= 3:
        path.pop(0)
    if not path:
        return True
    tx, ty = path[0]
    dx, dy = tx - m["x"], ty - m["y"]
    d = math.hypot(dx, dy) or 1.0
    mv = min(step, d)
    nx, ny = _ally_slide(m["x"], m["y"], dx / d * mv, dy / d * mv, walls)
    moved = math.hypot(nx - m["x"], ny - m["y"])
    m["angle"] = math.atan2(dy, dx)
    m["x"], m["y"] = nx, ny
    if moved < mv * 0.25:
        m["stuck"] += 1
        if m["stuck"] > 45:
            m["path_goal"] = None
    else:
        m["stuck"] = 0
    return False


M5_MARU_FIRE_RANGE = 380     # px
M5_MARU_FIRE_CD = (26, 40)    # frames between shots (random in range)
M5_MARU_DAMAGE = 34
M5_MARU_SPREAD = 0.06         # rad


def _maru_los(ax, ay, bx, by, walls):
    for w in walls:
        if w.clipline((ax, ay), (bx, by)):
            return False
    return True


def _update_maru_combat(m, walls):
    """Maru returns fire in the raid + tunnel with the pistol: nearest guard
    in range with a clear line. Returns the aim angle when engaged, else
    None. Bullets are player-side (`ally` = not counted in accuracy)."""
    if m.get("fire_cd", 0) > 0:
        m["fire_cd"] -= 1
    if m.get("muzzle", 0) > 0:
        m["muzzle"] -= 1
    if getattr(STATE, "mission5_stage", None) not in (STAGE_RAID, STAGE_TUNNEL):
        return None
    if getattr(STATE, "m5_dialogue_active", False) or STATE.player_dead:
        return None
    cands = []
    for e in STATE.enemies:
        if getattr(e, "hp", 1) <= 0:
            continue
        d = math.hypot(e.rect.centerx - m["x"], e.rect.centery - m["y"])
        if d <= M5_MARU_FIRE_RANGE:
            cands.append((d, e))
    cands.sort(key=lambda c: c[0])
    for _d, e in cands[:4]:
        ex, ey = e.rect.centerx, e.rect.centery
        if not _maru_los(m["x"], m["y"], ex, ey, walls):
            continue
        aim = math.atan2(ey - m["y"], ex - m["x"])
        if m.get("fire_cd", 0) <= 0:
            a = aim + _rng_legacy.uniform(-M5_MARU_SPREAD, M5_MARU_SPREAD)
            bx, by = m["x"] + math.cos(a) * 20, m["y"] + math.sin(a) * 20
            STATE.bullets.append({
                "x": bx, "y": by, "prev_x": bx, "prev_y": by,
                "dx": math.cos(a) * 22, "dy": math.sin(a) * 22,
                "life": 22, "owner": "player", "ally": True,
                "damage": M5_MARU_DAMAGE,
            })
            m["fire_cd"] = _rng_legacy.randint(*M5_MARU_FIRE_CD)
            m["muzzle"] = 4
            _sfx("gunshot", 0.4)
            try:
                e.hear_shot(bx, by, walls)
            except Exception:
                pass
        return aim
    return None


def _update_maru(solid_walls=None):
    """Follow Biribel when `following`. Maru keeps ~1.5 tiles back, and
    WAITS (holds position) when Biribel runs further ahead than
    M5_MARU_LEASH beyond that - the escort is paced by Maru, not the player."""
    m = getattr(STATE, "m5_maru", None)
    if not m or STATE.player is None or getattr(STATE, "m5_maru_dead", False):
        return
    if m["hit_flash"] > 0:
        m["hit_flash"] -= 1
    _update_maru_mags()
    _check_maru_ammo_resupply()
    walls = solid_walls if solid_walls is not None else _solid_walls()
    aim = _update_maru_combat(m, walls)
    if aim is not None:
        m["angle"] = aim
    if not m["following"] or getattr(STATE, "m5_dialogue_active", False):
        return
    px, py = _player_pos()
    d = math.hypot(px - m["x"], py - m["y"])
    follow_gap = TILE_SIZE * 1.5
    if d > follow_gap + M5_MARU_LEASH:
        if not m["waiting"]:
            m["waiting"] = True
            _radio("MARU: Biribel - slow down. I can't keep that pace.",
                   color=C_MARU, duration=260, mark="maru_leash")
        if aim is None:
            m["angle"] = math.atan2(py - m["y"], px - m["x"])
        return
    m["waiting"] = False
    if d <= follow_gap:
        if aim is None:
            m["angle"] = math.atan2(py - m["y"], px - m["x"])
        return
    goal = (int(px) // TILE_SIZE, int(py) // TILE_SIZE)
    dt_mul = 60.0 * (getattr(STATE, "dt", 1.0 / 60.0) or (1.0 / 60.0))
    speed = M5_MARU_SPEED
    g = _m5_maps.MISSION5_MAP
    mc, mr = int(m["x"]) // TILE_SIZE, int(m["y"]) // TILE_SIZE
    if 0 <= mr < len(g) and 0 <= mc < len(g[0]) and g[mr][mc] == "W":
        speed *= 0.7  # flooded section
    _maru_step(m, goal, speed * dt_mul, walls)
    if aim is not None:      # shoot while moving: keep the gun on target
        m["angle"] = aim


def _hit_maru(b):
    """Apply an enemy bullet to Maru. True = bullet consumed. HP mirrors to
    STATE.m5_maru_hp; at 0 Maru is dead and the flow fails the mission."""
    m = getattr(STATE, "m5_maru", None)
    if not m or getattr(STATE, "m5_maru_dead", False):
        return False
    if b.get("owner") == "player":
        return False
    if math.hypot(b["x"] - m["x"], b["y"] - m["y"]) >= 22:
        return False
    m["hp"] = max(0, m["hp"] - b.get("damage", ENEMY_DAMAGE))
    m["hit_flash"] = 10
    STATE.m5_maru_hp = m["hp"]
    if m["hp"] <= 0:
        STATE.m5_maru_dead = True
    return True


# ─────────────────────────────────────────────
# Maru ammo resupply (ported from M3 Volkov - mission-scoped, not imported)
# ─────────────────────────────────────────────
# When Biribel runs completely dry in the raid or the tunnel, Maru throws two
# magazines across. They fly on an authored arc, gently track the player and
# grant +1 spare mag each on the catch. No cutscene, no pause.
M5_MARU_THROW_RANGE = 640      # px - further than this and Maru can't reach

_MARU_MAG_LINES = {
    STAGE_RAID: (
        "MARU: You're empty - catch!",
        "MARU: Mag! Keep them off the stair!",
        "MARU: Again?! Count your shots, Biribel!",
    ),
    STAGE_TUNNEL: (
        "MARU: Catch - left hand, don't laugh.",
        "MARU: Mag! Keep moving!",
        "MARU: I'm running low too - make them count!",
    ),
}


def _player_dry():
    """True when the gun in hand has nothing in the mag and no spares."""
    cw = getattr(STATE, "current_weapon", "pistol")
    if cw == "k9_smg":
        return (getattr(STATE, "k9_ammo_in_mag", 0) <= 0
                and getattr(STATE, "k9_spare_mags", 0) <= 0)
    if cw == "os12":
        return (getattr(STATE, "os12_ammo_in_mag", 0) <= 0
                and getattr(STATE, "os12_spare_mags", 0) <= 0)
    if cw == "pistol":
        return STATE.ammo_in_mag <= 0 and STATE.spare_mags <= 0
    return False


def _check_maru_ammo_resupply():
    m = getattr(STATE, "m5_maru", None)
    if not m or getattr(STATE, "m5_maru_dead", False) or STATE.player is None:
        return False
    if STATE.player_dead or getattr(STATE, "m5_dialogue_active", False):
        return False
    if getattr(STATE, "mission5_stage", None) not in (STAGE_RAID, STAGE_TUNNEL):
        return False
    if getattr(STATE, "m5_maru_mags", None):
        return False  # already throwing
    if not _player_dry():
        return False
    if _dist((m["x"], m["y"]), _player_pos()) > M5_MARU_THROW_RANGE:
        return False
    _trigger_maru_mags_throw()
    return True


def _trigger_maru_mags_throw():
    m = getattr(STATE, "m5_maru", None)
    if not m or STATE.player is None:
        return
    px, py = _player_pos()
    mx, my = m["x"], m["y"]
    dist = math.hypot(px - mx, py - my)
    kind = "k9" if getattr(STATE, "current_weapon", "") == "k9_smg" else "pistol"
    # Longer throws take a little longer and loft higher, so a cross-room
    # toss still reads as a throw and not a teleport.
    base_dur = 38 + int(min(dist, M5_MARU_THROW_RANGE) / 26)
    mags = []
    for i, (ox, oy) in enumerate([(-14, -10), (16, -8)]):
        tx = px + _rng_legacy.randint(-20, 20)
        ty = py + _rng_legacy.randint(-14, 14)
        sx, sy = mx + ox, my + oy
        dur = base_dur + i * 5
        mags.append({
            "x": sx, "y": sy, "start_x": sx, "start_y": sy,
            "target_x": tx, "target_y": ty,
            "life": dur + i * 6 + 60, "duration": dur, "delay": i * 6,
            "arc_height": 70.0 + min(dist, 400) * 0.06 - i * 12.0,
            "vx": 0.0, "vy": 0.0, "rot": _rng_legacy.uniform(-1.1, 1.1),
            "age": 0, "kind": kind,
        })
    STATE.m5_maru_mags = mags
    m["angle"] = math.atan2(py - my, px - mx)   # face the throw
    m["throw_anim"] = 14

    STATE.m5_maru_mags_thrown_count = getattr(STATE, "m5_maru_mags_thrown_count", 0) + 1
    lines = _MARU_MAG_LINES.get(getattr(STATE, "mission5_stage", None),
                                _MARU_MAG_LINES[STAGE_RAID])
    n = STATE.m5_maru_mags_thrown_count
    _radio(lines[min(n - 1, len(lines) - 1)], color=C_MARU, duration=200,
           mark=None, priority=1)
    _sfx("rifle_handle", 0.5)


def _update_maru_mags():
    """Step the magazines in flight; resolve each at its catch point."""
    mags = getattr(STATE, "m5_maru_mags", None)
    if not mags:
        return
    if STATE.player is None:
        STATE.m5_maru_mags = []
        return
    m = getattr(STATE, "m5_maru", None)
    if m and m.get("throw_anim", 0) > 0:
        m["throw_anim"] -= 1
    px, py = _player_pos()
    remaining = []
    for mag in mags:
        mag["age"] += 1
        mag["life"] -= 1
        flight = max(0, mag["age"] - mag.get("delay", 0))
        dur = max(1, mag.get("duration", 42))
        if flight > 0:          # catch point eases after a moving player
            mag["target_x"] += (px - mag["target_x"]) * 0.075
            mag["target_y"] += (py - mag["target_y"]) * 0.075
        t = max(0.0, min(1.0, flight / dur))
        e = t * t * (3.0 - 2.0 * t)
        ox, oy = mag["x"], mag["y"]
        mag["x"] = mag["start_x"] + (mag["target_x"] - mag["start_x"]) * e
        mag["y"] = (mag["start_y"] + (mag["target_y"] - mag["start_y"]) * e
                    - math.sin(math.pi * t) * mag.get("arc_height", 76.0))
        mag["vx"], mag["vy"] = mag["x"] - ox, mag["y"] - oy
        if flight > 0:
            mag["rot"] += 0.24
        if flight >= dur or mag["life"] <= 0:
            cw = getattr(STATE, "current_weapon", "pistol")
            if cw == "k9_smg":
                STATE.k9_spare_mags = getattr(STATE, "k9_spare_mags", 0) + 1
                label = "+1 K-9 MAG"
            elif cw == "os12":
                STATE.os12_spare_mags = getattr(STATE, "os12_spare_mags", 0) + 1
                label = "+1 OS-12 MAG"
            else:
                STATE.spare_mags += 1
                label = "+1 9MM MAG"
            STATE.floating_texts.append([mag["x"], mag["y"] - 18, label,
                                         (140, 220, 160), 55])
            _sfx("pickup", 0.65)
            continue
        remaining.append(mag)
    STATE.m5_maru_mags = remaining
