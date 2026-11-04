"""Split from mission4.py - see __init__.py for the package facade.

World construction + shared position/objective helpers for Mission 4.
Wall parsing, guard spawns and the radio/objective helpers mirror the
missions.m3.world idioms (ported, not imported - m3 globals are
mission-scoped).
"""

import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import time
from collections import deque

import pygame

from core.config import (ENEMY_DAMAGE, TILE_SIZE)
from core.state import STATE
from core import config as _config
from entities.player import Player
from entities.enemy_ai import Enemy

audio = _config.audio

from missions.m4 import maps as _m4_maps  # owner of MISSION4_MAP/_objective/_radio_marks
from missions.m4.meta import (
    MAP_W, MAP_H,
    M4_SOLID_CHARS, M4_ROLE_TUNING,
    PLAYER_START_TILE, VASILE_CACHE_TILE, STATION_DOOR_TILE, VASILE_START_TILE,
    LIAISON_TILE, JAMMER_TILE, VASILE_STATION_TILE, VASILE_ARRIVE_TILE,
    C_SYSTEM, C_VASILE, C_MARU,
    M4_VASILE_HP, M4_POSTS, M4_SQUADS, M4_SQUAD_ENTRY_TILE,
    M4_SOLDIER_HP, M4_SOLDIER_DMG_TAKEN, M4_CIVILIAN_HP,
    M4_LEASH_NEAR, M4_LEASH_FAR,
)
import game.world as _gw  # RPE6 Phase 5 (D4): mission data lives in components
from engine.world import Label as _Label
from missions.m4.components import M4Guard as _M4Guard


def _m4g(e):
    """Declared M4 data of an enemy (replaces the ad hoc ``e.m4_*`` attributes)."""
    return _gw.ensure(e, _M4Guard)


def _m4l(e):
    """Shared ``Label`` component of an enemy: ``kind`` = enemy type, ``text`` = spawn label."""
    return _gw.ensure(e, _Label)



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
    return STATE.player and _dist(_player_pos(), pos) <= radius


def _tile_world(col, row):
    """Center of a tile, in world px."""
    return (col * TILE_SIZE + TILE_SIZE // 2, row * TILE_SIZE + TILE_SIZE // 2)


def _street_door_pos():
    return _tile_world(*STATION_DOOR_TILE)


def _vasile_cache_pos():
    return _tile_world(*VASILE_CACHE_TILE)


def _liaison_pos():
    return _tile_world(*LIAISON_TILE)


def _jammer_pos():
    return _tile_world(*JAMMER_TILE)


# Weapon kits for the allies: damage per bullet, frames between shots,
# reach in px, pellets per shot.
ALLY_WEAPONS = {
    "rifle": (24, 36, 520, 1),
    "pistol": (16, 30, 420, 1),
    "shotgun": (11, 54, 260, 4),
}
C_SQUAD = (150, 190, 120)


def _ally_record(name, tile, color, hp, weapon, look=None, label=None, coat=None,
                 role="idle", armed=True, mortal=False, dmg_mul=1.0):
    x, y = _tile_world(*tile)
    dmg, gap, reach, pellets = ALLY_WEAPONS[weapon]
    return {
        "name": name, "label": label or name, "look": look, "coat": coat,
        "x": float(x), "y": float(y), "angle": -math.pi / 2, "color": color,
        "hp": hp, "max_hp": hp, "cooldown": 0,
        "cover": tile, "door": tile, "role": role,
        "weapon": weapon if armed else "folder", "combat": weapon,
        "damage": dmg, "fire_gap": gap, "range": reach, "pellets": pellets,
        "armed": armed, "mortal": mortal, "dmg_mul": dmg_mul,
        "hit_flash": 0, "muzzle": 0, "hurt": 0, "downed": 0, "dead": False,
        "revive": 0, "following": False, "engaged": False,
        "path": [], "path_goal": None, "stuck": 0,
    }


def _ally(name):
    for a in getattr(STATE, "m4_allies", []) or []:
        if a["name"] == name:
            return a
    return None


def friendly_npcs():
    """[(name, (x, y), color, facing_rad, weapon)] live ally view."""
    out = []
    for a in getattr(STATE, "m4_allies", []) or []:
        out.append((a["name"], (a["x"], a["y"]), a["color"], a["angle"],
                    a.get("weapon", "rifle")))
    return out


# ─────────────────────────────────────────────
# Collision
# ─────────────────────────────────────────────
def _solid_walls():
    """All solid collision rects for this frame (STATE.walls + barriers).

    Mirrors m3.world._solid_walls minus the cell-door logic - M4 has no
    shootable doors yet (Slice 2 may add the station gate).
    """
    out = list(STATE.walls)
    out.extend(getattr(STATE, "m4_barriers", []))
    for d in getattr(STATE, "doors", []):
        if getattr(d, "collision_rect", None):
            out.append(d.collision_rect)
    for bar in (getattr(STATE, "m4_barricades", None) or {}).values():
        if bar["hp"] > 0:
            out.append(bar["rect"])
    return out


def barricade_blocks_shots(bar):
    """Intact and damaged barricades stop bullets; broken ones let them through."""
    return bar["hp"] > bar["max"] / 3.0


def _shot_walls():
    """What stops a bullet or a line of sight: walls, doors, unbroken barricades."""
    out = list(STATE.walls)
    out.extend(getattr(STATE, "m4_barriers", []))
    for d in getattr(STATE, "doors", []):
        if getattr(d, "collision_rect", None):
            out.append(d.collision_rect)
    for bar in (getattr(STATE, "m4_barricades", None) or {}).values():
        if bar["hp"] > 0 and barricade_blocks_shots(bar):
            out.append(bar["rect"])
    return out


# ─────────────────────────────────────────────
# Objective / radio helpers
# ─────────────────────────────────────────────
def _set_objective(text):
    _m4_maps._objective = text


def _movement_locked():
    """Movement gates for scripted beats (m3.world._movement_locked idiom).

    W2/W3 will add: the Vasile cache conversation, the liaison dialogue
    panel, and the jammer install hold.
    """
    if getattr(STATE, "player_dead", False):
        return True
    if getattr(STATE, "m4_dialogue_active", False):
        return True
    if getattr(STATE, "m4_work_lock", False):
        return True
    return False


def _radio(text, color=C_SYSTEM, duration=320, mark=None, priority=0, valid=None):
    """Pinned-radio helper (m3.world._radio idiom, dedup via _radio_marks).
    ``valid`` is a callable; the line cuts itself off once it returns False."""
    if mark and mark in _m4_maps._radio_marks:
        return
    if mark:
        _m4_maps._radio_marks.add(mark)
    try:
        from core.interactions import trigger_radio_chatter
        trigger_radio_chatter(text, color=color, duration=duration,
                              priority=max(priority, 0.5) if mark else priority,
                              valid=valid)
    except Exception:
        # Audio/interactions are optional in headless test harnesses.
        pass


# ─────────────────────────────────────────────
# Enemy spawns
# ─────────────────────────────────────────────
def _spawn_m4_guard(x, y, etype="guard", label="", aware=False):
    """Typed Enemy spawn (m3._spawn_m3_guard idiom; hp/speed from the local
    M4_ROLE_TUNING table - values ported from m3.sweep, module NOT imported)."""
    tuning = M4_ROLE_TUNING.get(etype, M4_ROLE_TUNING["guard"])
    e = Enemy(x, y)
    e.hp = tuning["hp"]
    e.speed = tuning["speed"]
    _m4l(e).kind = etype
    _m4l(e).text = label
    e.alerted = bool(aware)
    STATE.enemies.append(e)
    return e


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
    STATE.m4_barriers = []
    STATE.m4_breach_walls = []
    STATE.m4_sites = []
    STATE.m4_spawns = []
    STATE.doors = []
    STATE.player = None
    # Siege director scratch state (W4). Single-owner reset so a fresh world
    # build never carries fireteam counters or telegraph beams across a
    # checkpoint respawn.
    STATE.m4_lasers = []
    STATE.m4_siege_wave = 0
    STATE.m4_siege_spawn_timer = 0
    STATE.m4_laser_timer = 0
    STATE.m4_allies = []
    STATE.m4_barricades = {}
    STATE.m4_breached = False


def _parse_grid(g, etype="guard"):
    """Walk MISSION4_MAP: build walls/barriers, spawn the player on "P" and
    patrols on "E". Returns the player (or None if the grid had no "P").

    "H"/"h" car hulks are solid cover (body rect inset across the short
    axis), "W" is the weak station wall (kept on STATE.m4_breach_walls so the
    wave-4 charge can lift it), "b"/"w" register barricade sites and "Z"
    loyalist insertion points; sites and markers are walkable floor."""
    for row_idx, row in enumerate(g):
        for col_idx, tile in enumerate(row):
            x, y = col_idx * TILE_SIZE, row_idx * TILE_SIZE
            if tile == "C":
                STATE.walls.append(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE))
            elif tile == "H":
                STATE.walls.append(pygame.Rect(x, y + 12, TILE_SIZE, TILE_SIZE - 24))
            elif tile == "h":
                STATE.walls.append(pygame.Rect(x + 12, y, TILE_SIZE - 24, TILE_SIZE))
            elif tile == "W":
                r = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
                STATE.walls.append(r)
                STATE.m4_breach_walls.append(r)
            elif tile in ("b", "w"):
                STATE.m4_sites.append((col_idx, row_idx, "door" if tile == "b" else "window"))
            elif tile == "Z":
                STATE.m4_spawns.append((col_idx, row_idx))
            elif tile == "B":
                r = pygame.Rect(x + 4, y + 12, TILE_SIZE - 8, TILE_SIZE - 24)
                STATE.walls.append(r)
                STATE.m4_barriers.append(r)
            elif tile == "P":
                STATE.player = Player(x + 16, y + 16, max_hp=115)
            elif tile == "E":
                _spawn_m4_guard(x + TILE_SIZE // 2, y + TILE_SIZE // 2,
                                etype="guard", label="patrol_{}_{}".format(col_idx, row_idx))
            elif tile == "M":
                _spawn_m4_guard(x + TILE_SIZE // 2, y + TILE_SIZE // 2,
                                etype="marksman", label="marksman_{}_{}".format(col_idx, row_idx))
            # All other chars are walkable floor / markers - no collision.
    return STATE.player


def _build_m4_world():
    """Curfew-street world (STAGE_AFTERMATH arena)."""
    _reset_world_lists()
    player = _parse_grid(_m4_maps.MISSION4_MAP)

    if player is None:
        # Fallback spawn if the map ever loses its "P".
        sx, sy = PLAYER_START_TILE
        STATE.player = Player(sx * TILE_SIZE + 16, sy * TILE_SIZE + 16, max_hp=115)
    vasile = _ally_record("VASILE", VASILE_START_TILE, C_VASILE, M4_VASILE_HP, "rifle",
                          role="follow")
    STATE.m4_allies = [vasile]
    return STATE.player


# (col, row, tiles_w, tiles_h, inset px) - shared with missions.m4.draw3d.
STATION_PROPS = (
    (15, 5, 7, 1, 2),     # TX rack row along the hall's north wall
    (12, 7, 2, 1, 6),     # hall console, west
    (23, 7, 1, 2, 6),     # hall console, east
    (14, 19, 2, 1, 6),    # reception desk, west of the door lane
    (20, 19, 2, 1, 6),    # reception desk, east of the door lane
    (9, 5, 1, 2, 8),      # archive shelving
    (26, 6, 1, 2, 8),     # engineering bench
    (8, 18, 2, 1, 6),     # office desk
    (27, 19, 2, 1, 6),    # studio table
)


def _build_station_world():
    """Radio-station interior world (fortify and siege arena)."""
    _reset_world_lists()
    player = _parse_grid(_m4_maps.MISSION4_STATION_MAP)

    # Station furniture collision (the 3D set dresses the same rects): the
    # transmitter rack on the hall's north wall, the hall consoles, the
    # reception desks either side of the main door lane, archive shelving,
    # the engineering bench, the office desk and the studio table. Every
    # rect leaves a lane to its room's door and barricade sites.
    for c, r, tw, th, inset in STATION_PROPS:
        STATE.walls.append(pygame.Rect(
            c * TILE_SIZE + inset, r * TILE_SIZE + inset,
            tw * TILE_SIZE - 2 * inset, th * TILE_SIZE - 2 * inset))

    if player is None:
        sx, sy = STATION_DOOR_TILE
        STATE.player = Player(sx * TILE_SIZE + 16, sy * TILE_SIZE + 16, max_hp=115)
    _init_m4_allies()
    walls = _solid_walls()
    ex, ey = _tile_world(*M4_SQUAD_ENTRY_TILE)
    for post, (cover, door) in M4_POSTS.items():
        cx, cy = _tile_world(*cover)
        dx, dy = _tile_world(*door)
        if _ally_find_path(ex, ey, cover, walls) is None:
            print("M4 WARNING: post %s cover %s is unreachable" % (post, cover))
        if not _ally_los(cx, cy, dx, dy, walls):
            print("M4 WARNING: post %s cover %s has no LOS to %s" % (post, cover, door))
    return STATE.player


# ─────────────────────────────────────────────
# Station allies (Vasile, Maru, the tone squad)
# ─────────────────────────────────────────────
def _init_m4_allies(vasile_hp=None):
    """Vasile walks in beside Biribel and heads for the rack post; Maru waits
    unarmed at the meet anchor in the entry hall."""
    vasile = _ally_record("VASILE", VASILE_ARRIVE_TILE, C_VASILE, M4_VASILE_HP, "rifle",
                          role="post")
    if vasile_hp is not None:
        vasile["hp"] = max(1, min(M4_VASILE_HP, int(vasile_hp)))
    vasile["cover"], vasile["door"] = M4_POSTS["rack"]
    maru = _ally_record("MARU", LIAISON_TILE, C_MARU, 140, "pistol", role="idle", armed=False)
    maru["angle"] = math.pi / 2
    STATE.m4_allies = [vasile, maru]
    return STATE.m4_allies


def _tone_choice():
    tone = getattr(STATE, "m4_tone", None)
    return tone[0] if isinstance(tone, list) and tone else 0


def _arm_m4_allies():
    """After the meet: Maru arms and takes the main door, and the squad the
    tone picked walks in to its posts."""
    if not getattr(STATE, "m4_allies", None):
        _init_m4_allies()
    maru = _ally("MARU")
    if maru is not None and not maru["armed"]:
        maru["armed"] = True
        maru["weapon"] = "pistol"
        maru["role"] = "post"
        maru["cover"], maru["door"] = M4_POSTS["main_e"]
        maru["path_goal"] = None
    if not any(a.get("squad") for a in STATE.m4_allies):
        for i, (name, look, weapon, post, coat) in enumerate(M4_SQUADS[_tone_choice()]):
            soldier = look == "soldier"
            ex, ey = M4_SQUAD_ENTRY_TILE
            a = _ally_record(name, (ex + (i % 2), ey), C_SQUAD,
                             M4_SOLDIER_HP if soldier else M4_CIVILIAN_HP, weapon,
                             look=look, coat=coat, role="post", mortal=True,
                             dmg_mul=M4_SOLDIER_DMG_TAKEN if soldier else 1.0)
            a["squad"] = True
            a["cover"], a["door"] = M4_POSTS[post]
            if soldier:
                a["damage"] = 22
            STATE.m4_allies.append(a)
    STATE.m4_maru_joined = True
    return STATE.m4_allies


def _ally_los(ax, ay, tx, ty, walls):
    for wall in walls:
        if wall.clipline((ax, ay), (tx, ty)):
            return False
    return True


def _ally_slide(ax, ay, mx, my, walls):
    actor = pygame.Rect(0, 0, 24, 24)
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


# ─────────────────────────────────────────────
# Ally pathing (BFS over tiles, probed against the real wall rects)
# ─────────────────────────────────────────────
_ALLY_SIZE = 24   # must match the 24x24 actor used by _ally_slide
_ALLY_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1),
                    (1, 1), (1, -1), (-1, 1), (-1, -1))


_FREE = {"key": None, "cache": {}}


def _ally_tile_free(c, r, w, h, walls, cache):
    """True when an ally-sized box centred on tile (c, r) touches no wall."""
    key = (c, r)
    free = cache.get(key)
    if free is None:
        if 0 <= c < w and 0 <= r < h:
            probe = pygame.Rect(0, 0, _ALLY_SIZE, _ALLY_SIZE)
            probe.center = (c * TILE_SIZE + TILE_SIZE // 2,
                            r * TILE_SIZE + TILE_SIZE // 2)
            free = probe.collidelist(walls) == -1
        else:
            free = False
        cache[key] = free
    return free


def _free_cache(walls):
    """Tile-free probes, reused while the wall set is unchanged (a follower
    re-plans every time Biribel crosses a tile)."""
    key = (id(_m4_maps.MISSION4_MAP), len(walls),
           tuple(sorted((r.x, r.y) for r in walls[len(STATE.walls):])))
    if _FREE["key"] != key:
        _FREE["key"] = key
        _FREE["cache"] = {}
    return _FREE["cache"]


def _ally_find_path(ax, ay, goal, walls):
    """Tile BFS (8-way, no corner cutting). Returns a list of world-px
    waypoints ending on the goal tile centre, or None if unreachable."""
    w, h = _m4_maps._live_map_dims()
    start = (int(ax) // TILE_SIZE, int(ay) // TILE_SIZE)
    goal = (int(goal[0]), int(goal[1]))
    if start == goal:
        return [_tile_world(*goal)]
    cache = _free_cache(walls)

    def free(c, r):
        return (c, r) == goal or _ally_tile_free(c, r, w, h, walls, cache)

    prev = {start: None}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        if cur == goal:
            break
        c, r = cur
        for dc, dr in _ALLY_NEIGHBOURS:
            nxt = (c + dc, r + dr)
            if nxt in prev or not free(*nxt):
                continue
            if dc and dr and not (free(c + dc, r) and free(c, r + dr)):
                continue  # diagonal would clip a wall corner
            prev[nxt] = cur
            queue.append(nxt)
    if goal not in prev:
        return None
    nodes, node = [], goal
    while node is not None:
        nodes.append(node)
        node = prev[node]
    nodes.reverse()
    return [_tile_world(c, r) for c, r in nodes[1:]]  # skip the tile we stand in


def _ally_walk_to(a, goal, step, walls):
    """Advance one frame along the BFS route to `goal` (a tile).
    Returns True once the ally has arrived."""
    if a.get("path_goal") != goal:
        route = _ally_find_path(a["x"], a["y"], goal, walls)
        a["path_goal"] = goal
        a["stuck"] = 0
        if route is None:
            print("M4: no route for %s to tile %s" % (a["name"], goal))
            a["path"] = []
            return False
        a["path"] = route
    path = a["path"]
    while path and math.hypot(path[0][0] - a["x"], path[0][1] - a["y"]) <= 3:
        path.pop(0)
    if not path:
        return True
    tx, ty = path[0]
    dx, dy = tx - a["x"], ty - a["y"]
    dist = math.hypot(dx, dy)
    mv = min(step, dist)
    nx, ny = _ally_slide(a["x"], a["y"], dx / dist * mv, dy / dist * mv, walls)
    moved = math.hypot(nx - a["x"], ny - a["y"])
    a["x"], a["y"] = nx, ny
    if moved < mv * 0.25:
        a["stuck"] = a.get("stuck", 0) + 1
        if a["stuck"] > 45:
            a["path_goal"] = None  # force a re-plan from where we really are
    else:
        a["stuck"] = 0
    return False


def _ally_targets(a, walls, anchor):
    """Nearest living enemy in reach and in sight, weighted toward `anchor`."""
    best, target = 1e9, None
    for e in getattr(STATE, "enemies", []):
        if e.hp <= 0:
            continue
        ex, ey = e.rect.centerx, e.rect.centery
        d_ally = math.hypot(ex - a["x"], ey - a["y"])
        if d_ally > a["range"]:
            continue
        if not _ally_los(a["x"], a["y"], ex, ey, walls):
            continue
        score = d_ally if anchor is None else (
            math.hypot(ex - anchor[0], ey - anchor[1]) * 0.55 + d_ally * 0.45)
        if score < best:
            best, target = score, e
    return target


def _ally_fire(a, target):
    a["angle"] = math.atan2(target.rect.centery - a["y"], target.rect.centerx - a["x"])
    a["cooldown"] = max(0, a["cooldown"] - 1)
    if a["cooldown"] > 0:
        return
    reach = 34 if a["combat"] == "rifle" else 26
    mx = a["x"] + math.cos(a["angle"]) * reach
    my = a["y"] + math.sin(a["angle"]) * reach
    pellets = a.get("pellets", 1)
    for i in range(pellets):
        if pellets == 1:
            spread = _rng_legacy.uniform(-0.04, 0.04)
        else:
            spread = (i - (pellets - 1) / 2.0) * 0.07
        shot_a = a["angle"] + spread
        STATE.bullets.append({
            "x": mx, "y": my, "prev_x": mx, "prev_y": my,
            "dx": math.cos(shot_a) * 22, "dy": math.sin(shot_a) * 22,
            "life": 22 if pellets == 1 else 12, "owner": "player",
            "damage": a["damage"], "ally": a["name"],
        })
    target.alerted = True
    a["muzzle"] = 4
    a["cooldown"] = a["fire_gap"] + _rng_legacy.randint(0, 6)
    _sfx("gunshot_distant", 0.28)


def _ally_follow(a, walls, dt_mul):
    """Leash on Biribel: walk while he is past M4_LEASH_FAR, stop inside
    M4_LEASH_NEAR. Shot at with a target in sight, Vasile holds and returns
    fire unless Biribel is leaving him behind."""
    if STATE.player is None:
        return
    px, py = STATE.player.rect.center
    d = math.hypot(px - a["x"], py - a["y"])
    if a["hurt"] > 0 and a.get("engaged") and d < 320:
        return
    if d > M4_LEASH_FAR or (a["following"] and d > M4_LEASH_NEAR):
        a["following"] = True
        goal = (int(px) // TILE_SIZE, int(py) // TILE_SIZE)
        speed = 3.5 if d < 420 else 4.3
        _ally_walk_to(a, goal, speed * dt_mul, walls)
        if not a.get("engaged") and a["path"]:
            tx, ty = a["path"][0]
            a["angle"] = math.atan2(ty - a["y"], tx - a["x"])
    else:
        a["following"] = False
        a["path_goal"] = None


def _update_m4_allies(solid_walls):
    allies = getattr(STATE, "m4_allies", None)
    if not allies or getattr(STATE, "m4_dialogue_active", False):
        return
    dt_mul = 60.0 * STATE.dt
    shot_walls = _shot_walls()
    for a in allies:
        if a.get("dead"):
            continue
        for k in ("hit_flash", "muzzle", "hurt"):
            if a[k] > 0:
                a[k] -= 1
        if a["downed"] > 0:
            if a["name"] == "VASILE":
                continue          # escort.update_vasile_down owns the revive
            a["downed"] -= 1
            if a["downed"] <= 0:
                # Maru stays down while a loyalist stands over her.
                if _enemy_within(a["x"], a["y"], 140):
                    a["downed"] = 60
                else:
                    a["hp"] = max(40, a["max_hp"] // 2)
            continue
        role = a.get("role")
        was_engaged = a.get("engaged")
        if role == "follow":
            _ally_follow(a, solid_walls, dt_mul)
        elif role == "post":
            _ally_walk_to(a, a["cover"], 2.6 * dt_mul, solid_walls)
            if a["path"] and not was_engaged:
                tx, ty = a["path"][0]
                a["angle"] = math.atan2(ty - a["y"], tx - a["x"])
        a["engaged"] = False
        if not a["armed"]:
            continue
        anchor = _tile_world(*a["door"]) if role == "post" else None
        target = _ally_targets(a, shot_walls, anchor)
        if target is not None:
            a["engaged"] = True
            _ally_fire(a, target)
        else:
            a["cooldown"] = max(0, a["cooldown"] - 1)
            if role == "post" and not a["path"]:
                door = _tile_world(*a["door"])
                a["angle"] = math.atan2(door[1] - a["y"], door[0] - a["x"])


def _enemy_within(x, y, radius):
    """True when a living enemy is inside `radius` of a world point."""
    r2 = radius * radius
    for e in getattr(STATE, "enemies", []):
        if e.hp <= 0:
            continue
        dx = e.rect.centerx - x
        dy = e.rect.centery - y
        if dx * dx + dy * dy <= r2:
            return True
    return False


def _ally_at(x, y, radius=22):
    for a in getattr(STATE, "m4_allies", None) or []:
        if a.get("dead") or a["downed"] > 0:
            continue
        if math.hypot(x - a["x"], y - a["y"]) < radius:
            return a
    return None


def _damage_m4_ally(a, amount):
    """Apply damage to one ally. Squad members die; Maru kneels and gets up;
    Vasile goes to the escort down/revive rule."""
    a["hp"] -= amount * a.get("dmg_mul", 1.0)
    a["hit_flash"] = 10
    a["hurt"] = 120
    if a["hp"] > 0:
        return
    a["hp"] = 0
    if a["name"] == "VASILE":
        from missions.m4 import escort as _escort
        _escort.vasile_down(a)
    elif a.get("mortal"):
        a["dead"] = True
        a["downed"] = 0
        STATE.blood_decals.append([a["x"], a["y"], 170, _rng_legacy.randint(14, 22)])
        _radio("%s is down." % a["label"], color=C_SYSTEM, duration=240)
    else:
        a["downed"] = 600


def _hit_m4_ally(b):
    """Apply an enemy bullet to the first living ally under it. Returns True
    on a hit so the bullet is consumed."""
    a = _ally_at(b["x"], b["y"])
    if a is None:
        return False
    _damage_m4_ally(a, b.get("damage", ENEMY_DAMAGE))
    return True


# ─────────────────────────────────────────────
# Marksman telegraph (shared by the street and the siege)
# ─────────────────────────────────────────────
M4_MARKSMAN_DAMAGE = 28        # the pinned shot a laser windup delivers


def _siege_reset():
    """Explicit re-init for the flow.start_m4 double-reset idiom."""
    STATE.m4_lasers = []
    STATE.m4_siege_wave = 0
    STATE.m4_siege_spawn_timer = 0
    STATE.m4_laser_timer = 0


def _siege_alive_count():
    return sum(1 for e in STATE.enemies
               if _m4g(e).loyalist and e.hp > 0)


def _add_sniper_laser(target_pos, from_pos, life=48, shooter=None, damage=0):
    """Queue a marksman windup.

    The beam is a real telegraph now: while it is up the shooter's own fire is
    suppressed, and when it expires the shot lands on the pinned point - not
    on wherever the player has walked to - so strafing out of the beam dodges
    it. A beam queued with no shooter stays visual-only (smoke proof).
    """
    STATE.m4_lasers.append({"from": from_pos, "to": target_pos, "life": life,
                            "shooter": shooter, "damage": damage})


def _sfx(name, volume):
    try:
        audio.play(name, volume=volume)
    except Exception:
        pass  # audio is optional in headless harnesses


def _decay_lasers():
    for laser in getattr(STATE, "m4_lasers", [])[:]:
        laser["life"] -= 1
        shooter = laser.get("shooter")
        if shooter is not None:
            if getattr(shooter, "hp", 0) > 0:
                # Hold the marksman's own trigger while the beam is up: the
                # telegraph must be the only shot coming, or it teaches the
                # player nothing (the old "visual only" beam was a lie).
                shooter.fire_cooldown = max(getattr(shooter, "fire_cooldown", 0),
                                            max(1, laser["life"]))
            else:
                laser["life"] = 0      # shooter died mid-windup: no shot
        if laser["life"] <= 0:
            _resolve_laser_shot(laser)
            STATE.m4_lasers.remove(laser)


def _resolve_laser_shot(laser):
    """Fire the pinned marksman shot at the point the beam pinned."""
    shooter = laser.get("shooter")
    if shooter is None or getattr(shooter, "hp", 0) <= 0:
        return
    tx, ty = laser["to"]
    sx, sy = shooter.rect.centerx, shooter.rect.centery
    dx, dy = tx - sx, ty - sy
    dist = math.hypot(dx, dy)
    if dist < 1:
        return
    speed = 26
    STATE.bullets.append({
        "x": sx, "y": sy, "prev_x": sx, "prev_y": sy,
        "dx": dx / dist * speed, "dy": dy / dist * speed,
        "life": 90, "owner": "enemy",
        "damage": laser.get("damage") or M4_MARKSMAN_DAMAGE,
        "marksman": True,
    })
    _sfx("gunshot_distant", 0.4)


# ─────────────────────────────────────────────
# Mission fail (M5 pattern: flag -> timer -> death screen)
# ─────────────────────────────────────────────
M4_FAIL_DELAY = 150


def fail_mission(reason):
    """Start the fail countdown once; flow._update_fail raises the screen."""
    if getattr(STATE, "m4_fail_reason", None):
        return
    STATE.m4_fail_reason = reason
    STATE.m4_fail_timer = M4_FAIL_DELAY
