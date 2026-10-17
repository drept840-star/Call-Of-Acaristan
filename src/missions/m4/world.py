
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
    PLAYER_START_TILE, VASILE_CACHE_TILE, STATION_DOOR_TILE,
    LIAISON_TILE, JAMMER_TILE, VASILE_STATION_TILE,
    C_SYSTEM, C_VASILE, C_MARU,
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


# Door split during the hold: Vasile covers the north TX assault door,
# Maru the studio mouth. Biribel keeps the south entry. Cover tiles sit
# inside the transmitter hall, never on a spawn cell. Vasile holds (13, 7):
# south of the console desk on open hall floor, with a clear line to the
# north-door overwatch without sitting inside solid geometry.
M4_ALLY_POSTS = {
    "VASILE": {
        "meet": VASILE_STATION_TILE, "cover": (13, 7), "door": (15, 8),
        "color": C_VASILE, "hp": 180, "damage": 24, "cooldown": 36,
        "range": 520, "weapon": "rifle",
    },
    "MARU": {
        "meet": LIAISON_TILE, "cover": (19, 5), "door": (18, 9),
        "color": C_MARU, "hp": 140, "damage": 16, "cooldown": 28,
        "range": 420, "weapon": "pistol",
    },
}


def friendly_npcs():
    """[(name, (x, y), color, facing_rad, weapon)] live ally view.
    Empty outside the station stages so the street world never draws them."""
    stage = getattr(STATE, "mission4_stage", "")
    if stage not in ("krap_status", "maru", "commit", "done"):
        return []
    out = []
    for a in getattr(STATE, "m4_allies", []) or []:
        out.append((a["name"], (a["x"], a["y"]), a["color"], a["angle"],
                    a.get("weapon", "rifle")))
    if out:
        return out
    mx, my = _liaison_pos()
    vx, vy = _tile_world(*VASILE_STATION_TILE)
    return [
        ("MARU", (mx, my), C_MARU, math.pi / 2, "folder"),
        ("VASILE", (vx, vy), C_VASILE, math.pi / 2, "rifle"),
    ]


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
    return False


def _radio(text, color=C_SYSTEM, duration=320, mark=None, priority=0):
    """Pinned-radio helper (m3.world._radio idiom, dedup via _radio_marks)."""
    if mark and mark in _m4_maps._radio_marks:
        return
    if mark:
        _m4_maps._radio_marks.add(mark)
    try:
        from core.interactions import trigger_radio_chatter
        trigger_radio_chatter(text, color=color, duration=duration,
                              priority=max(priority, 0.5) if mark else priority)
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


def _parse_grid(g, etype="guard"):
    """Walk MISSION4_MAP: build walls/barriers, spawn the player on "P" and
    patrols on "E". Returns the player (or None if the grid had no "P")."""
    for row_idx, row in enumerate(g):
        for col_idx, tile in enumerate(row):
            x, y = col_idx * TILE_SIZE, row_idx * TILE_SIZE
            if tile == "C":
                STATE.walls.append(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE))
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
    return STATE.player


def _build_station_world():
    """Radio-station interior world (STAGE_KRAP_STATUS..STAGE_COMMIT arena)."""
    _reset_world_lists()
    player = _parse_grid(_m4_maps.MISSION4_STATION_MAP)

    # Station furniture collision (mirrors the dressing pass in draw.py): the
    # rack row, console desk, entry bench, studio table and utility shelves
    # are solid so rooms read as furnished spaces, not walk-over decals.
    # Every rect keeps a walkable lane around it (hall rows 3-8, entry cols
    # 6-13, studio sides, utility centre col 11).
    def _prop(c, r, tw=1, th=1, inset=6):
        STATE.walls.append(pygame.Rect(
            c * TILE_SIZE + inset, r * TILE_SIZE + inset,
            tw * TILE_SIZE - 2 * inset, th * TILE_SIZE - 2 * inset))

    _prop(5, 2, 9, 1, 2)     # TX rack row along the hall's north wall
    _prop(12, 6, 2, 1)       # console desk (hall middle)
    _prop(5, 15, 1, 2, 8)    # entry-hall bench (west wall)
    _prop(18, 13, 2, 1)      # studio broadcast table
    _prop(10, 10)            # utility shelf, west bay
    _prop(12, 10)            # utility shelf, east bay

    if player is None:
        sx, sy = STATION_DOOR_TILE
        STATE.player = Player(sx * TILE_SIZE + 16, sy * TILE_SIZE + 16, max_hp=115)
    _init_m4_allies()
    walls = _solid_walls()
    for name, spec in M4_ALLY_POSTS.items():
        cx, cy = _tile_world(*spec["cover"])
        dx, dy = _tile_world(*spec["door"])
        mx, my = _tile_world(*spec["meet"])
        if _ally_find_path(mx, my, spec["cover"], walls) is None:
            print("M4 WARNING: %s cannot reach cover %s" % (name, spec["cover"]))
        if not _ally_los(cx, cy, dx, dy, walls):
            print("M4 WARNING: %s cover %s has no LOS to door %s"
                  % (name, spec["cover"], spec["door"]))
    return STATE.player


# ─────────────────────────────────────────────
# Station allies (Vasile / Maru)
# ─────────────────────────────────────────────
def _init_m4_allies():
    allies = []
    for name, spec in M4_ALLY_POSTS.items():
        mx, my = _tile_world(*spec["meet"])
        allies.append({
            "name": name,
            "x": float(mx),
            "y": float(my),
            "angle": math.pi / 2,
            "color": spec["color"],
            "hp": spec["hp"],
            "max_hp": spec["hp"],
            "cooldown": 0,
            "cover": spec["cover"],
            "door": spec["door"],
            "weapon": "folder" if name == "MARU" else spec["weapon"],
            "combat": spec["weapon"],
            "damage": spec["damage"],
            "fire_gap": spec["cooldown"],
            "range": spec["range"],
            "armed": False,
            "hit_flash": 0,
            "downed": 0,
            "path": [],
            "path_goal": None,
            "stuck": 0,
        })
    STATE.m4_allies = allies
    return allies


def _arm_m4_allies():
    allies = getattr(STATE, "m4_allies", None)
    if not allies:
        allies = _init_m4_allies()
    for a in allies:
        spec = M4_ALLY_POSTS[a["name"]]
        a["path"] = []
        a["path_goal"] = None
        a["stuck"] = 0
        a["armed"] = True
        a["weapon"] = spec["weapon"]
        a["hp"] = spec["hp"]
        a["max_hp"] = spec["hp"]
        a["downed"] = 0
        a["cooldown"] = 18
        dx, dy = _tile_world(*spec["door"])
        a["angle"] = math.atan2(dy - a["y"], dx - a["x"])
    STATE.m4_maru_joined = True
    return allies


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


def _ally_find_path(ax, ay, goal, walls):
    """Tile BFS (8-way, no corner cutting). Returns a list of world-px
    waypoints ending on the goal tile centre, or None if unreachable."""
    w, h = _m4_maps._live_map_dims()
    start = (int(ax) // TILE_SIZE, int(ay) // TILE_SIZE)
    goal = (int(goal[0]), int(goal[1]))
    if start == goal:
        return [_tile_world(*goal)]
    cache = {}

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


def _update_m4_allies(solid_walls):
    allies = getattr(STATE, "m4_allies", None)
    if not allies:
        return
    if getattr(STATE, "m4_dialogue_active", False):
        return
    stage = getattr(STATE, "mission4_stage", "")
    if stage not in ("krap_status", "maru", "commit", "done"):
        return
    dt_mul = 60.0 * STATE.dt
    for a in allies:
        if a["hit_flash"] > 0:
            a["hit_flash"] -= 1
        if a["downed"] > 0:
            a["downed"] -= 1
            if a["downed"] <= 0:
                a["hp"] = max(40, a["max_hp"] // 2)
            continue
        door = _tile_world(*a["door"])
        if a["armed"]:
            _ally_walk_to(a, a["cover"], 2.4 * dt_mul, solid_walls)
            target = None
            best = 999999.0
            for e in getattr(STATE, "enemies", []):
                if e.hp <= 0:
                    continue
                ex, ey = e.rect.centerx, e.rect.centery
                d_ally = math.hypot(ex - a["x"], ey - a["y"])
                if d_ally > a["range"]:
                    continue
                if not _ally_los(a["x"], a["y"], ex, ey, solid_walls):
                    continue
                d_door = math.hypot(ex - door[0], ey - door[1])
                score = d_door * 0.55 + d_ally * 0.45
                if score < best:
                    best = score
                    target = e
            if target is not None:
                a["angle"] = math.atan2(
                    target.rect.centery - a["y"], target.rect.centerx - a["x"])
                a["cooldown"] = max(0, a["cooldown"] - 1)
                if a["cooldown"] <= 0:
                    spread = _rng_legacy.uniform(-0.04, 0.04)
                    shot_a = a["angle"] + spread
                    reach = 34 if a["weapon"] == "rifle" else 26
                    mx = a["x"] + math.cos(a["angle"]) * reach
                    my = a["y"] + math.sin(a["angle"]) * reach
                    STATE.bullets.append({
                        "x": mx, "y": my, "prev_x": mx, "prev_y": my,
                        "dx": math.cos(shot_a) * 22,
                        "dy": math.sin(shot_a) * 22,
                        "life": 22, "owner": "player",
                        "damage": a["damage"], "ally": a["name"],
                    })
                    target.alerted = True
                    if STATE.player is not None:
                        target.last_seen_pos = (
                            STATE.player.rect.centerx,
                            STATE.player.rect.centery)
                    try:
                        audio.play("gunshot_distant", volume=0.28)
                    except Exception:
                        pass
                    a["cooldown"] = a["fire_gap"]
            else:
                a["angle"] = math.atan2(door[1] - a["y"], door[0] - a["x"])
                a["cooldown"] = max(0, a["cooldown"] - 1)
        else:
            a["angle"] = math.pi / 2
            a["cooldown"] = max(0, a["cooldown"] - 1)


def _hit_m4_ally(b):
    """Apply an enemy bullet to the first living ally under it. Returns True
    on a hit so the bullet is consumed. Downed allies kneel, then stand."""
    allies = getattr(STATE, "m4_allies", None)
    if not allies:
        return False
    for a in allies:
        if a["downed"] > 0:
            continue
        if math.hypot(b["x"] - a["x"], b["y"] - a["y"]) >= 22:
            continue
        a["hp"] -= b.get("damage", ENEMY_DAMAGE)
        a["hit_flash"] = 10
        if a["hp"] <= 0:
            a["hp"] = 0
            a["downed"] = 180
        return True
    return False


# ─────────────────────────────────────────────
# Siege director (W4 STAGE_COMMIT)
# ─────────────────────────────────────────────
# Ported in SPIRIT from m2.sniper's kill-box pressure and m3.sweep's wave
# cadence; neither module is imported (both are mission-scoped, one-owner
# rule). The loyalist assault is the clock's texture, never its lock: up to
# M4_MAX_CONCURRENT fireteams stream from the station's carved assault doors,
# pursuit runs on the shared Enemy target coords, and a marksman press paints
# a laser telegraph (m2._add_sniper_laser visual idiom). The hold ends on the
# timer, not on kills (m3 exfil-door lesson), and once the arrest order lands
# on air (M4_SIEGE_RELIEF_FRAMES) no fresh teams commit - the siege breaks off.
#
# INSERTION DOORS: every tile here MUST be a walkable floor char ("D"/"O"/
# "L") on MISSION4_STATION_MAP so a fireteam commits THROUGH a doorway onto
# open floor, never inside a wall cell. The smoke check asserts this.
#   (15, 8)  north-wall door of the transmitter hall
#   (18, 9)  studio corridor mouth (studio <-> TX hall)
#   (11, 13) east-wall door of the entry hall
M4_INSERTION_TILES = [(15, 8), (18, 9), (11, 13)]
M4_MAX_CONCURRENT = 6
M4_FIRETEAM_GAP = (150, 260)   # frames between committed fireteams
M4_LASER_GAP = (150, 320)      # frames between marksman telegraph pins
M4_SIEGE_RELIEF_FRAMES = 4080  # ~68s: after the standdown beat, spawns cease


def _siege_reset():
    """Explicit re-init for the flow.start_m4 double-reset idiom."""
    STATE.m4_lasers = []
    STATE.m4_siege_wave = 0
    STATE.m4_siege_spawn_timer = 0
    STATE.m4_laser_timer = 0


def _siege_alive_count():
    return sum(1 for e in STATE.enemies
               if _m4g(e).loyalist and e.hp > 0)


def _add_sniper_laser(target_pos, from_pos, life=48):
    """Queue a telegraph beam (m2 idiom: purely visual; the Enemy AI owns fire)."""
    STATE.m4_lasers.append({"from": from_pos, "to": target_pos, "life": life})


def _arm_loyalist_hunt(e):
    e.alerted = True
    e.state = "CHASE"
    e.combat_alert_timer = 420
    e.path = []
    e.path_timer = 0
    if STATE.player is not None:
        e.last_seen_pos = (STATE.player.rect.centerx, STATE.player.rect.centery)


def _spawn_loyalist_fireteam():
    """Commit one fireteam through a random assault door. Every insertion tile
    is a carved doorway on walkable floor, so the team appears IN the door -
    never inside a wall cell. aware=True: they came to take the transmitter
    back, not to patrol; the loyalist channel also pins their target to the
    player every frame (see systems._update_m4_enemies)."""
    g = _m4_maps.MISSION4_STATION_MAP
    h = len(g)
    w = len(g[0]) if h else 0
    solid = set(M4_SOLID_CHARS)
    # Deterministic walkable floor tile inside each door (the hall side the
    # team commits from). Keeps every spawn rect fully on open floor.
    DOOR_IN = {(15, 8): (15, 7), (18, 9): (18, 10), (11, 13): (12, 13)}
    doors = list(M4_INSERTION_TILES)
    _rng_legacy.shuffle(doors)
    for door in doors:
        dc, dr = DOOR_IN.get(door, door)
        if not (0 <= dc < w and 0 <= dr < h) or g[dr][dc] in solid:
            continue
        x, y = _tile_world(dc, dr)
        leader = _spawn_m4_guard(x, y, etype="guard",
                                 label="loyalist_{}".format(STATE.m4_siege_wave),
                                 aware=True)
        _m4g(leader).loyalist = True
        _arm_loyalist_hunt(leader)
        STATE.m4_siege_wave += 1
        # Later teams pair the point-man with a marksman on the long
        # sightlines. The marksman rides the same floor tile (a few px
        # sprite-centre offset only) so it can never land inside a wall.
        # Gate on the concurrency cap too: a two-man team committed at
        # cap-1 alive would overshoot M4_MAX_CONCURRENT (the hold check
        # asserts the cap every frame).
        if (STATE.m4_siege_wave >= 3 and _rng_legacy.random() < 0.6
                and _siege_alive_count() + 1 <= M4_MAX_CONCURRENT):
            m = _spawn_m4_guard(x + 6, y + 4, etype="marksman",
                                label="loyalist_marksman", aware=True)
            _m4g(m).loyalist = True
            _arm_loyalist_hunt(m)
        _sfx("footstep", 0.35)
        return


def _sfx(name, volume):
    try:
        audio.play(name, volume=volume)
    except Exception:
        pass  # audio is optional in headless harnesses


def _decay_lasers():
    for laser in getattr(STATE, "m4_lasers", [])[:]:
        laser["life"] -= 1
        if laser["life"] <= 0:
            STATE.m4_lasers.remove(laser)


def _marksman_press():
    """Telegraph a marksman pin on the player. Visual only - the shared Enemy
    AI owns the actual shot, same as m2's sniper pressure reads."""
    STATE.m4_laser_timer -= 1
    if STATE.m4_laser_timer > 0:
        return
    STATE.m4_laser_timer = _rng_legacy.randint(*M4_LASER_GAP)
    marksmen = [e for e in STATE.enemies
                if _m4g(e).loyalist
                and _m4l(e).kind == "marksman" and e.hp > 0]
    if not marksmen or STATE.player is None:
        return
    m = _rng_legacy.choice(marksmen)
    px, py = STATE.player.rect.center
    _add_sniper_laser((px, py), from_pos=(m.rect.centerx, m.rect.centery), life=46)
    _sfx("rifle_handle", 0.3)


def _run_siege_director():
    """Per-frame siege driver, called from flow._update_stage (STAGE_COMMIT)."""
    if STATE.player is None:
        return
    _decay_lasers()
    STATE.m4_siege_spawn_timer -= 1
    if STATE.m4_hold_timer >= M4_SIEGE_RELIEF_FRAMES:
        return  # the order aired - the siege breaks off, the clock runs out
    if (STATE.m4_siege_spawn_timer <= 0
            and _siege_alive_count() < M4_MAX_CONCURRENT):
        _spawn_loyalist_fireteam()
        STATE.m4_siege_spawn_timer = _rng_legacy.randint(*M4_FIRETEAM_GAP)
    _marksman_press()
