
import pygame
from core.config import (C_ENEMY_SKIN, C_IPA_ARMBAND, C_IPA_UNIFORM, C_MAG_BANDANA, C_MAG_UNIFORM, ENEMY_ATTACK_RANGE, ENEMY_DAMAGE, ENEMY_DETECT_RANGE, ENEMY_FIRE_COOLDOWN, ENEMY_HEAR_RADIUS, PATH_RECALC_INTERVAL, PATH_WAYPOINT_REACH, PROBE_LEN, Particle, TILE_SIZE, audio, font_terminal_small)
from core.state import STATE
import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import heapq
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
from engine.text import T as _T  # RPE6 Phase 4 text table
from engine.world import WalkCycle as _WalkCycle  # RPE6 Phase 5: declared walk-cycle component
_enemy_shadow = pygame.Surface((34, 16), pygame.SRCALPHA)
pygame.draw.ellipse(_enemy_shadow, (0, 0, 0, 45), (0, 0, 34, 16))
_SQRT2 = math.sqrt(2)
def _heuristic(ax, ay, bx, by):
    dx = abs(bx - ax)
    dy = abs(by - ay)
    return max(dx, dy) + (_SQRT2 - 1) * min(dx, dy)
_walk_grid_cache = {}
def _build_walk_grid(walls):
    if not walls:
        return [], 0, 0
    h = hash((len(walls), *(w.x for w in walls), *(w.y for w in walls)))
    cached = _walk_grid_cache.get(h)
    if cached:
        return cached["grid"], cached["cols"], cached["rows"]
    map_cols = max(w.right - 1 for w in walls) // TILE_SIZE + 1
    map_rows = max(w.bottom - 1 for w in walls) // TILE_SIZE + 1
    grid = [[True for _ in range(map_cols)] for _ in range(map_rows)]
    for wall in walls:
        c0 = wall.x // TILE_SIZE
        r0 = wall.y // TILE_SIZE
        c1 = (wall.right - 1) // TILE_SIZE
        r1 = (wall.bottom - 1) // TILE_SIZE
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                if 0 <= col < map_cols and 0 <= row < map_rows:
                    grid[row][col] = False
    # Multi-entry: raw and door-filtered wall lists alternate per repath;
    # a single-slot cache thrashed (full rebuild) on every call.
    if len(_walk_grid_cache) > 8:
        _walk_grid_cache.clear()
    _walk_grid_cache[h] = {"grid": grid, "cols": map_cols, "rows": map_rows}
    return grid, map_cols, map_rows


def _route_walls(walls):
    """A* obstacles: unlocked doors are PASSABLE for route planning.

    Door.update() opens unlocked doors for chasing guards on approach, but
    while a panel is still closed its collision rect sits in the walls list.
    If those panels mark the walk grid, A* concludes every doorway is a dead
    end and the whole assault stacks against the wall NEXT TO the door
    (never close enough to trigger it) - the "AI doesn't know where I am"
    freeze. Same lesson as _m3_volkov_navigation_walls in m3/systems.
    """
    passable = {
        id(d.collision_rect)
        for d in getattr(STATE, "doors", [])
        if not getattr(d, "locked", False)
        and getattr(d, "collision_rect", None) is not None
    }
    if not passable:
        return walls
    return [w for w in walls if id(w) not in passable]


def _astar(start, goal, grid):
    sx, sy = int(start[0]), int(start[1])
    gx, gy = int(goal[0]), int(goal[1])
    rows = len(grid)
    cols = len(grid[0])
    if not (0 <= sx < cols and 0 <= sy < rows and grid[sy][sx]):
        return []
    if not (0 <= gx < cols and 0 <= gy < rows and grid[gy][gx]):
        # Try to find nearest walkable goal
        best = None
        best_dist = float('inf')
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                nr, nc = gy + dr, gx + dc
                if 0 <= nc < cols and 0 <= nr < rows and grid[nr][nc]:
                    d = abs(dr) + abs(dc)
                    if d < best_dist:
                        best_dist = d
                        best = (nc, nr)
        if best is None:
            return []
        gx, gy = best
    open_set = [(0, sx, sy)]
    came_from = {}
    g_score = {(sx, sy): 0}
    # Cap search space. Must cover the whole walkable grid: long cross-map
    # routes through big open rooms (KO lobby -> dock) legitimately exhaust
    # a smaller budget and silently return "unreachable".
    max_nodes = min(cols * rows, 4000)  # Cap search space
    nodes_expanded = 0
    while open_set and nodes_expanded < max_nodes:
        _, cx, cy = heapq.heappop(open_set)
        nodes_expanded += 1
        if (cx, cy) == (gx, gy):
            path = []
            while (cx, cy) in came_from:
                path.append((cx, cy))
                cx, cy = came_from[(cx, cy)]
            path.reverse()
            return path
        for dc, dr in [
            (1, 0), (-1, 0), (0, 1), (0, -1),
            (1, 1), (-1, 1), (1, -1), (-1, -1),
        ]:
            nc, nr = cx + dc, cy + dr
            if 0 <= nc < cols and 0 <= nr < rows and grid[nr][nc]:
                if dc != 0 and dr != 0:
                    if not grid[cy][nc] or not grid[nr][cx]:
                        continue
                step_cost = _SQRT2 if (dc != 0 and dr != 0) else 1.0
                tentative = g_score[(cx, cy)] + step_cost
                key = (nc, nr)
                if tentative < g_score.get(key, float("inf")):
                    came_from[key] = (cx, cy)
                    g_score[key] = tentative
                    f = tentative + _heuristic(nc, nr, gx, gy)
                    heapq.heappush(open_set, (f, nc, nr))
    return []
_next_enemy_id = 0
class Enemy:
    # RPE6 Phase 5 (D4): role / tuning flags the missions used to stuff on at spawn time
    # are declared here with the defaults the shared code assumed. Class-level on purpose:
    # an instance only carries the attribute once a mission sets it, exactly as before, so
    # the replay state hash (which walks instance __dict__) is unchanged (R5).
    is_commander = False      # M1 warehouse commander (keycard carrier)
    is_ambush_enemy = False   # M1 ambush wave: 8 dmg shots, mag-carrier look
    is_evidence_wave = False  # M2 evidence wave: 50-frame fire cooldown
    is_breach_enemy = False   # breach wave: extra fire sparks / ignition chance
    fire_weakness = 1.0       # molotov damage multiplier
    sight_mul = 1.0           # per-guard sight scale (M5 night quarter)
    _dt_mul = 1.0             # per-frame dt multiplier cached by update() for _apply_move

    def __init__(self, x, y):
        global _next_enemy_id
        self.uid = _next_enemy_id
        _next_enemy_id += 1
        self.rect = pygame.Rect(x, y, 32, 32)
        self.speed = 2
        self.angle = 0
        self.hp = 200
        self.state = "IDLE"
        self._step_timer = 0.0
        self.state_timer = 0
        self.fire_cooldown = 0
        self.lost_sight_timer = 0
        self.idle_angle = _rng_legacy.uniform(0, math.pi * 2)
        self.idle_switch_timer = _rng_legacy.randint(60, 180)
        self.search_timer = 0
        self.alerted = False
        self.drops_mag = False
        self.path = []
        self.path_timer = 1
        self.path_waypoint_timer = 0
        self.patrol_points = []
        self.patrol_idx = 0
        self.distraction_target = None
        self.last_seen_pos = None
        self.combat_alert_timer = 0
        self.sweep_points = []
        # Stuck detection
        self._last_pos = (x, y)
        self._stuck_timer = 0
        # Deadlock breaker state (see update()): overlap forces can cancel
        # chase movement exactly, leaving two enemies wedged forever.
        self._jam_prev = (x, y)
        self._jam_t = 0
        # Combat strafe state (ATTACK sidestep between shots).
        self._strafe_dir = 0
        self._strafe_t = 0
        self.fire_react_cooldown = 0
        self.fire_discipline = _rng_legacy.uniform(0.65, 1.15)
        self.flinch_timer = 0
        self.entry_grace = 0
        self.breach_entry_target = None
        self.breach_entrying = False
        self.breach_entry_source = ""
        self._prev_state = "IDLE"
        self.walk = _WalkCycle()  # RPE6 Phase 5: engine.world WalkCycle (the entity's component, one object)
    def _can_pass(self, target_x, target_y, walls):
        sx, sy = self.rect.centerx, self.rect.centery
        dx = target_x - sx
        dy = target_y - sy
        dist = math.hypot(dx, dy)
        if dist == 0:
            return True
        radius = 13
        nx = -dy / dist * radius
        ny = dx / dist * radius
        for wall in walls:
            if wall.clipline((sx, sy), (target_x, target_y)):
                return False
            if wall.clipline((sx + nx, sy + ny), (target_x + nx, target_y + ny)):
                return False
            if wall.clipline((sx - nx, sy - ny), (target_x - nx, target_y - ny)):
                return False
        return True
    def _smooth_path(self, walls):
        if not self.path:
            return
        for i in range(min(len(self.path) - 1, 5), 0, -1):
            col, row = self.path[i]
            wx = col * TILE_SIZE + TILE_SIZE // 2
            wy = row * TILE_SIZE + TILE_SIZE // 2
            if self._can_pass(wx, wy, walls):
                self.path = self.path[i:]
                break
    def _build_sweep_points(self, cx, cy, walls):
        grid, map_cols, map_rows = _build_walk_grid(walls)
        if not grid:
            return []
        offsets = [
            (TILE_SIZE * 2, 0), (-TILE_SIZE * 2, 0),
            (0, TILE_SIZE * 2), (0, -TILE_SIZE * 2),
            (TILE_SIZE, TILE_SIZE), (-TILE_SIZE, TILE_SIZE),
            (TILE_SIZE, -TILE_SIZE), (-TILE_SIZE, -TILE_SIZE),
            (TILE_SIZE * 3, 0), (-TILE_SIZE * 3, 0),
            (0, TILE_SIZE * 3), (0, -TILE_SIZE * 3),
        ]
        _rng_legacy.shuffle(offsets)
        search_offsets = []
        for dc in range(-3, 4):
            for dr in range(-3, 4):
                search_offsets.append((dc, dr))
        search_offsets.sort(key=lambda p: abs(p[0]) + abs(p[1]))
        points = []
        for dx, dy in offsets:
            wx, wy = cx + dx, cy + dy
            col = max(0, min(int(wx // TILE_SIZE), map_cols - 1))
            row = max(0, min(int(wy // TILE_SIZE), map_rows - 1))
            found = False
            for dc, dr in search_offsets:
                nc, nr = col + dc, row + dr
                if 0 <= nc < map_cols and 0 <= nr < map_rows and grid[nr][nc]:
                    col, row = nc, nr
                    found = True
                    break
            if not found:
                continue
            tx = col * TILE_SIZE + TILE_SIZE // 2
            ty = row * TILE_SIZE + TILE_SIZE // 2
            points.append((tx, ty))
            if len(points) == 4:
                break
        return points
    def update(self, px, py, walls, bullets, particles, enemies=None, fire_zones=None):
        ox, oy = self.rect.centerx, self.rect.centery
        # Delta-time multiplier: speed values in this module are in px/frame,
        # so multiply by (60 * dt) to get px this frame at any FPS.
        # At 60 FPS dt=1/60, so 60*dt = 1 → identical to old behavior.
        _dt_mul = 60.0 * STATE.dt
        self._dt_mul = _dt_mul  # cached for _apply_move
        self.state_timer -= 1
        self.fire_cooldown -= 1
        if self.entry_grace > 0:
            self.entry_grace -= 1
        if self.fire_react_cooldown > 0:
            self.fire_react_cooldown -= 1
        if self.combat_alert_timer > 0:
            self.combat_alert_timer -= 1
        # ── Flinch on state change to chase/attack ──
        if self.state != self._prev_state:
            if self.state in ("CHASE", "ATTACK") and self._prev_state in ("IDLE", "PATROL"):
                self.flinch_timer = 8
        self._prev_state = self.state
        if self.flinch_timer > 0:
            self.flinch_timer -= 1
        can_see = self._can_see(px, py, walls)
        if can_see:
            self.last_seen_pos = (px, py)
            self.lost_sight_timer = 0
            self.combat_alert_timer = 420
            if self.alerted and self.state not in ("CHASE", "ATTACK"):
                self.state = "CHASE"
        else:
            self.lost_sight_timer += 1
        # Sight cone detection
        cone_half = math.radians(80) if self.alerted else math.radians(45)
        dist_to_player = math.hypot(px - self.rect.centerx, py - self.rect.centery)
        detect_range = ENEMY_DETECT_RANGE * (2 if self.alerted else 1)
        if not self.alerted and dist_to_player < detect_range:
            in_sight_cone = False
            if dist_to_player < 115 and can_see:
                # Close-range peripheral awareness. Stops enemies being blind when
                # the player walks almost beside them.
                in_sight_cone = True
            else:
                angle_to_player = math.atan2(
                    py - self.rect.centery, px - self.rect.centerx
                )
                diff = abs(angle_to_player - self.angle)
                if diff > math.pi:
                    diff = 2 * math.pi - diff
                if diff < cone_half and can_see:
                    in_sight_cone = True
            if in_sight_cone:
                self.alerted = True
                self.state = "CHASE"
                self.last_seen_pos = (px, py)
                self.combat_alert_timer = 420
        # Soft Repulsion - capped to prevent wall-pushing
        repulse_x, repulse_y = 0.0, 0.0
        personal_space = 44.0
        if enemies:
            for other in enemies:
                if other is not self and other.state in ("CHASE", "ATTACK"):
                    dx = self.rect.centerx - other.rect.centerx
                    dy = self.rect.centery - other.rect.centery
                    dist = math.hypot(dx, dy)
                    if 0 < dist < personal_space:
                        force = (personal_space - dist) / personal_space
                        repulse_x += (dx / dist) * force * 1.0
                        repulse_y += (dy / dist) * force * 1.0
            # Cap repulsion magnitude
            rep_mag = math.hypot(repulse_x, repulse_y)
            if rep_mag > self.speed * 0.5:
                scale = (self.speed * 0.5) / rep_mag
                repulse_x *= scale
                repulse_y *= scale
        # ── FIRE ZONE AWARENESS ──
        # Only care about fire that's actually close.
        nearest_fire = None
        nearest_fire_dist = float("inf")
        if fire_zones:
            for fz in fire_zones:
                fd = math.hypot(self.rect.centerx - fz.x, self.rect.centery - fz.y)
                if fd < fz.radius + 20 and fd < nearest_fire_dist:
                    nearest_fire = fz
                    nearest_fire_dist = fd
        if nearest_fire:
            in_core = nearest_fire_dist < nearest_fire.radius * 0.45
            near_edge = nearest_fire_dist < nearest_fire.radius * 0.75
            player_visible_and_shootable = (
                can_see and dist_to_player <= ENEMY_ATTACK_RANGE * 1.1
            )
            if in_core:
                if self.fire_react_cooldown <= 0:
                    self.fire_react_cooldown = _rng_legacy.randint(18, 36)
                else:
                    if _rng_legacy.random() < 0.55:
                        move_x = repulse_x * 0.25
                        move_y = repulse_y * 0.25
                        self._apply_move(move_x, move_y, walls)
                        return
                self.alerted = True
                self.combat_alert_timer = max(self.combat_alert_timer, 240)
                self.path = []
                self.distraction_target = None
                flee_angle = math.atan2(
                    self.rect.centery - nearest_fire.y,
                    self.rect.centerx - nearest_fire.x,
                )
                flee_angle += _rng_legacy.uniform(-0.85, 0.85)
                flee_speed = self.speed * _rng_legacy.uniform(1.15, 1.55) * self.fire_discipline
                move_x = math.cos(flee_angle) * flee_speed + repulse_x * 0.5
                move_y = math.sin(flee_angle) * flee_speed + repulse_y * 0.5
                self.angle = flee_angle
                self._apply_move(move_x, move_y, walls)
                if can_see:
                    self.last_seen_pos = (px, py)
                    self.state = "CHASE"
                return
            elif near_edge and not player_visible_and_shootable:
                avoid_angle = math.atan2(
                    self.rect.centery - nearest_fire.y,
                    self.rect.centerx - nearest_fire.x,
                )
                repulse_x += math.cos(avoid_angle) * 0.7 * self.fire_discipline
                repulse_y += math.sin(avoid_angle) * 0.7 * self.fire_discipline
        if self.state == "IDLE":
            self.idle_switch_timer -= 1
            if self.idle_switch_timer <= 0:
                self.idle_angle = _rng_legacy.uniform(0, math.pi * 2)
                self.idle_switch_timer = _rng_legacy.randint(60, 180)
            self._ease_toward_angle(self.idle_angle, 0.04)
        elif self.state == "PATROL":
            if not self.patrol_points:
                self.state = "IDLE"
            else:
                target_x, target_y = self.patrol_points[self.patrol_idx]
                dx = target_x - self.rect.centerx
                dy = target_y - self.rect.centery
                dist = math.hypot(dx, dy)
                if dist < 16:
                    self.patrol_idx = (self.patrol_idx + 1) % len(self.patrol_points)
                else:
                    self._ease_toward_angle(math.atan2(dy, dx), 0.06)
                    move_x = math.cos(self.angle) * self.speed
                    move_y = math.sin(self.angle) * self.speed
                    self.rect.x += move_x * _dt_mul
                    for wall in walls:
                        if self.rect.colliderect(wall):
                            if move_x > 0: self.rect.right = wall.left
                            elif move_x < 0: self.rect.left = wall.right
                    self.rect.y += move_y * _dt_mul
                    for wall in walls:
                        if self.rect.colliderect(wall):
                            if move_y > 0: self.rect.bottom = wall.top
                            elif move_y < 0: self.rect.top = wall.bottom
        elif self.state == "SEARCH":
            if self.distraction_target:
                tx, ty = self.distraction_target
                self.angle = math.atan2(ty - self.rect.centery, tx - self.rect.centerx)
                dist_to_distraction = math.hypot(tx - self.rect.centerx, ty - self.rect.centery)
                if dist_to_distraction > 24:
                    self._update_pathfinding(tx, ty, walls)
                    self._move_toward(tx, ty, walls, repulse_x, repulse_y)
                else:
                    self.distraction_target = None
                    self.path = []
                    if self.sweep_points:
                        self.distraction_target = self.sweep_points.pop(0)
            else:
                # Scan - face toward last seen position
                if self.last_seen_pos:
                    target_a = math.atan2(
                        self.last_seen_pos[1] - self.rect.centery,
                        self.last_seen_pos[0] - self.rect.centerx,
                    )
                    sweep_offset = math.sin(_now_ms() * 0.002) * math.radians(60)
                    target_a += sweep_offset
                    diff = (target_a - self.angle + math.pi) % (math.pi * 2) - math.pi
                    self.angle += diff * 0.05
                else:
                    self.idle_switch_timer -= 1
                    if self.idle_switch_timer <= 0:
                        self.idle_angle = _rng_legacy.uniform(0, math.pi * 2)
                        self.idle_switch_timer = _rng_legacy.randint(30, 80)
                    self.angle += (self.idle_angle - self.angle) * 0.05
            self.search_timer -= 1
            if self.search_timer <= 0:
                # FIX: Only de-alert if combat_alert_timer is truly expired
                if self.combat_alert_timer <= 0:
                    self.alerted = False
                    self.state = "PATROL" if self.patrol_points else "IDLE"
                    self.patrol_idx = 0
                    self.distraction_target = None
                    self.sweep_points = []
                    self.path = []
                else:
                    # Still combat-aware - do one more search sweep
                    self.search_timer = 120
                    self.distraction_target = None
                    self.sweep_points = []
                    self.path = []
        elif self.state == "CHASE":
            if self.last_seen_pos:
                tx, ty = self.last_seen_pos
                self._update_pathfinding(tx, ty, walls)
                dist_to_last = math.hypot(tx - self.rect.centerx, ty - self.rect.centery)
                if can_see and dist_to_player <= ENEMY_ATTACK_RANGE:
                    self.state = "ATTACK"
                    self.path = []
                elif dist_to_last < 32 and not can_see and self.lost_sight_timer > 45:
                    # Reached last known position, can't see - search
                    self.state = "SEARCH"
                    self.search_timer = 200 if self.combat_alert_timer > 0 else 120
                    self.sweep_points = self._build_sweep_points(tx, ty, walls)
                    if self.sweep_points:
                        self.distraction_target = self.sweep_points.pop(0)
                    self.path = []
                else:
                    self._move_toward(tx, ty, walls, repulse_x, repulse_y)
            else:
                self.state = "SEARCH"
                self.search_timer = 120
                self.distraction_target = None
                self.path = []
        elif self.state == "ATTACK":
            if can_see or self.lost_sight_timer < 45:
                self.alerted = True
                self.combat_alert_timer = 420
                # Always face player - with easing for human delay
                target_a = math.atan2(py - self.rect.centery, px - self.rect.centerx)
                if self.flinch_timer > 0:
                    flinch_jitter = math.sin(_now_ms() * 0.2) * 0.15
                    target_a += flinch_jitter
                self._ease_toward_angle(target_a, 0.10)
                optimal_min = ENEMY_ATTACK_RANGE * 0.50
                optimal_max = ENEMY_ATTACK_RANGE * 0.80
                # Use a larger threshold before going back to CHASE
                out_of_range = dist_to_player > ENEMY_ATTACK_RANGE * 1.5
                if out_of_range:
                    self.state = "CHASE"
                else:
                    # Shoot when ready
                    if can_see and self.fire_cooldown <= 0 and self.entry_grace <= 0:
                        self._shoot(px, py, bullets, particles, walls)
                        # Evidence-wave enemies (post-tanker cleanup team) fire
                        # faster than the global default - 50 frames vs 60.
                        # This is a per-enemy override so it doesn't affect
                        # Mission 1 or the sniper phase.
                        self.fire_cooldown = 50 if self.is_evidence_wave else ENEMY_FIRE_COOLDOWN
                    too_close = dist_to_player < optimal_min
                    too_far = dist_to_player > optimal_max
                    if too_close:
                        away_angle = math.atan2(
                            self.rect.centery - py, self.rect.centerx - px
                        )
                        move_x = math.cos(away_angle) * self.speed * 0.6 + repulse_x
                        move_y = math.sin(away_angle) * self.speed * 0.6 + repulse_y
                        self._apply_move(move_x, move_y, walls)
                    elif too_far:
                        self._update_pathfinding(px, py, walls)
                        self._move_toward(px, py, walls, repulse_x, repulse_y)
                    elif not can_see:
                        # Strafe to regain LOS
                        strafe_angle = self.angle + math.pi / 2
                        if (_now_ms() // 400) % 2 == 0:
                            strafe_angle = self.angle - math.pi / 2
                        move_x = math.cos(strafe_angle) * self.speed * 0.6 + repulse_x
                        move_y = math.sin(strafe_angle) * self.speed * 0.6 + repulse_y
                        self._apply_move(move_x, move_y, walls)
                    else:
                        # In optimal range with LOS - combat strafe: sidestep
                        # between shots instead of statue-standing in the
                        # open ("the AI is extremely stupid" - a guard that
                        # holds still while trading fire is a free kill).
                        if self._strafe_dir == 0:
                            self._strafe_dir = _rng_legacy.choice((-1, 1))
                            self._strafe_t = _rng_legacy.randint(30, 70)
                        self._strafe_t -= 1
                        if self._strafe_t <= 0:
                            self._strafe_dir = -self._strafe_dir
                            self._strafe_t = _rng_legacy.randint(30, 70)
                        sa = self.angle + math.pi / 2 * self._strafe_dir
                        move_x = math.cos(sa) * self.speed * 0.5 + repulse_x
                        move_y = math.sin(sa) * self.speed * 0.5 + repulse_y
                        self._apply_move(move_x, move_y, walls)
            else:
                # Lost sight for too long
                if self.last_seen_pos:
                    self.state = "CHASE"
                else:
                    self.state = "SEARCH"
                    self.search_timer = 120
        # Hard overlap resolution
        if enemies:
            for other in enemies:
                if other is not self:
                    if self.rect.colliderect(other.rect):
                        dx = self.rect.centerx - other.rect.centerx
                        dy = self.rect.centery - other.rect.centery
                        dist = math.hypot(dx, dy)
                        if dist == 0:
                            dx = _rng_legacy.choice([-1, 1])
                            dy = _rng_legacy.choice([-1, 1])
                            dist = math.hypot(dx, dy)
                        overlap = (self.rect.width / 2 + other.rect.width / 2) - dist
                        if overlap > 0:
                            push_force = min(overlap / 2, 3.0)
                            push_x = (dx / dist) * push_force
                            push_y = (dy / dist) * push_force
                            self.rect.x += push_x * _dt_mul
                            for wall in walls:
                                if self.rect.colliderect(wall):
                                    if push_x > 0: self.rect.right = wall.left
                                    elif push_x < 0: self.rect.left = wall.right
                            self.rect.y += push_y * _dt_mul
                            for wall in walls:
                                if self.rect.colliderect(wall):
                                    if push_y > 0: self.rect.bottom = wall.top
                                    elif push_y < 0: self.rect.top = wall.bottom
        # ── Deadlock breaker ──
        # Overlap resolution runs AFTER movement and can cancel it exactly:
        # two chasing enemies wedged together sit at 0 px/frame forever
        # (dock holdout: the whole assault stream froze around its spawn
        # tiles). If a chasing enemy hasn't actually moved for ~1s, shove
        # it out of the equilibrium with a random impulse and force a
        # repath from its real tile.
        if self.state == "CHASE":
            moved_now = math.hypot(self.rect.centerx - self._jam_prev[0],
                                   self.rect.centery - self._jam_prev[1])
            self._jam_prev = (self.rect.centerx, self.rect.centery)
            if moved_now < 0.75:
                self._jam_t += 1
            else:
                self._jam_t = 0
            if self._jam_t > 60:
                self._jam_t = 0
                self.path = []
                self.path_timer = 0
                ja = _rng_legacy.uniform(0, 2 * math.pi)
                self._apply_move(math.cos(ja) * 8.0, math.sin(ja) * 8.0, walls)

        # ── Positional footsteps: hear a patrol before you see it ──
        moved = math.hypot(self.rect.centerx - ox, self.rect.centery - oy)
        if moved > 0.5 and self.state in ("PATROL", "SEARCH", "CHASE"):
            self._step_timer -= moved
            if self._step_timer <= 0:
                chasing = self.state == "CHASE"
                audio.play_3d(
                    f"enemy_footstep_{_rng_legacy.randint(1, 3)}",
                    (self.rect.centerx, self.rect.centery),
                    (px, py),
                    max_dist=560,
                    base_volume=0.80 if chasing else 0.55,
                )
                self._step_timer = ((26.0 + _rng_legacy.randint(0, 5)) if chasing
                                    else (40.0 + _rng_legacy.randint(0, 8)))
        elif moved <= 0.5:
            self._step_timer = min(self._step_timer, 8.0)

    def _ease_toward_angle(self, target_angle, speed=0.08):
        diff = (target_angle - self.angle + math.pi) % (math.pi * 2) - math.pi
        if abs(diff) < 0.01:
            self.angle = target_angle
        else:
            self.angle += diff * speed
            self.angle = (self.angle + math.pi) % (math.pi * 2) - math.pi
    def _can_see(self, px, py, walls, from_pos=None):
        if from_pos is None:
            from_pos = (self.rect.centerx, self.rect.centery)
        dist = math.hypot(px - from_pos[0], py - from_pos[1])
        # Alerted enemies should not suddenly become blind at medium range.
        aware = self.alerted or self.combat_alert_timer > 0
        sight_range = ENEMY_DETECT_RANGE * (3.0 if aware else 1.15)
        # Per-guard visibility scale (default 1.0 = unchanged). M5's night
        # quarter lowers it when the player is in the dark.
        sight_range *= self.sight_mul
        if dist > sight_range:
            return False
        # Check several points around the player instead of only the exact center.
        # This prevents tiny wall/corner clips from making AI randomly "forget" you.
        target_points = [
            (px, py),
            (px - 12, py),
            (px + 12, py),
            (px, py - 12),
            (px, py + 12),
            (px - 8, py - 8),
            (px + 8, py - 8),
            (px - 8, py + 8),
            (px + 8, py + 8),
        ]
        for tx, ty in target_points:
            blocked = False
            for wall in walls:
                if wall.clipline(from_pos, (tx, ty)):
                    blocked = True
                    break
            if not blocked:
                return True
        return False
    def _update_pathfinding(self, px, py, walls):
        self.path_timer -= 1
        if self.path_timer > 0:
            return
        dist = math.hypot(px - self.rect.centerx, py - self.rect.centery)
        if dist < ENEMY_ATTACK_RANGE * 1.5:
            self.path_timer = max(3, PATH_RECALC_INTERVAL // 3)
        else:
            self.path_timer = PATH_RECALC_INTERVAL
        grid, map_cols, map_rows = _build_walk_grid(_route_walls(walls))
        if map_cols == 0 or map_rows == 0:
            self.path = []
            return
        start_col = int(self.rect.centerx // TILE_SIZE)
        start_row = int(self.rect.centery // TILE_SIZE)
        goal_col = int(px // TILE_SIZE)
        goal_row = int(py // TILE_SIZE)
        if start_col == goal_col and start_row == goal_row:
            self.path = []
            return
        self.path = _astar((start_col, start_row), (goal_col, goal_row), grid)
        self._smooth_path(walls)
    def _move_toward(self, px, py, walls, repulse_x=0.0, repulse_y=0.0):
        if self.path:
            col, row = self.path[0]
            target_x = col * TILE_SIZE + TILE_SIZE // 2
            target_y = row * TILE_SIZE + TILE_SIZE // 2
            dx = target_x - self.rect.centerx
            dy = target_y - self.rect.centery
            dist_sq = dx * dx + dy * dy
            reach = PATH_WAYPOINT_REACH * 1.25
            if dist_sq < reach * reach:
                self.path.pop(0)
                self._smooth_path(walls)
                self.path_waypoint_timer = 0
                if self.path:
                    col, row = self.path[0]
                    target_x = col * TILE_SIZE + TILE_SIZE // 2
                    target_y = row * TILE_SIZE + TILE_SIZE // 2
                else:
                    target_x, target_y = px, py
            else:
                # FIX: Stuck detection based on actual position change
                cx, cy = self.rect.centerx, self.rect.centery
                moved = math.hypot(cx - self._last_pos[0], cy - self._last_pos[1])
                if moved < 0.5:
                    self._stuck_timer += 1
                else:
                    self._stuck_timer = 0
                self._last_pos = (cx, cy)
                if self._stuck_timer > 30:
                    self._stuck_timer = 0
                    if self.path:
                        self.path.pop(0)
                    self._smooth_path(walls)
                    self.path_timer = 0  # Force repath next frame
            self._ease_toward_angle(
                math.atan2(target_y - self.rect.centery, target_x - self.rect.centerx), 0.07
            )
            move_x = math.cos(self.angle) * self.speed + repulse_x
            move_y = math.sin(self.angle) * self.speed + repulse_y
            slide_tx, slide_ty = target_x, target_y
        else:
            # No path - use direct steering
            desired_angle = math.atan2(py - self.rect.centery, px - self.rect.centerx)
            num_dirs = 16
            probe_len = PROBE_LEN
            best_angle = desired_angle
            best_score = -999.0
            for i in range(num_dirs):
                angle_offset = -math.pi / 2 + (i / (num_dirs - 1)) * math.pi
                candidate = desired_angle + angle_offset
                alignment = math.cos(candidate - desired_angle)
                probe_x = self.rect.centerx + math.cos(candidate) * probe_len
                probe_y = self.rect.centery + math.sin(candidate) * probe_len
                probe_rect = pygame.Rect(probe_x - 10, probe_y - 10, 20, 20)
                blocked = any(w.colliderect(probe_rect) for w in walls)
                short_probe_x = self.rect.centerx + math.cos(candidate) * (probe_len * 0.4)
                short_probe_y = self.rect.centery + math.sin(candidate) * (probe_len * 0.4)
                short_probe_rect = pygame.Rect(short_probe_x - 8, short_probe_y - 8, 16, 16)
                short_blocked = any(w.colliderect(short_probe_rect) for w in walls)
                score = alignment - (5.0 if blocked else 0.0) - (3.0 if short_blocked else 0.0)
                if score > best_score:
                    best_score = score
                    best_angle = candidate
            diff = (best_angle - self.angle + math.pi) % (math.pi * 2) - math.pi
            self.angle += diff * 0.45
            move_x = math.cos(self.angle) * self.speed + repulse_x
            move_y = math.sin(self.angle) * self.speed + repulse_y
            slide_tx, slide_ty = px, py
        self.rect.x += move_x * self._dt_mul
        blocked_x = False
        for wall in walls:
            if self.rect.colliderect(wall):
                if move_x > 0:
                    self.rect.right = wall.left
                elif move_x < 0:
                    self.rect.left = wall.right
                blocked_x = True
        self.rect.y += move_y * self._dt_mul
        blocked_y = False
        for wall in walls:
            if self.rect.colliderect(wall):
                if move_y > 0:
                    self.rect.bottom = wall.top
                elif move_y < 0:
                    self.rect.top = wall.bottom
                blocked_y = True
        if blocked_x and not blocked_y:
            if abs(slide_ty - self.rect.centery) > 2:
                slide_dy = self.speed if slide_ty > self.rect.centery else -self.speed
                self.rect.y += slide_dy * self._dt_mul
                for wall in walls:
                    if self.rect.colliderect(wall):
                        if slide_dy > 0: self.rect.bottom = wall.top
                        elif slide_dy < 0: self.rect.top = wall.bottom
        elif blocked_y and not blocked_x:
            if abs(slide_tx - self.rect.centerx) > 2:
                slide_dx = self.speed if slide_tx > self.rect.centerx else -self.speed
                self.rect.x += slide_dx * self._dt_mul
                for wall in walls:
                    if self.rect.colliderect(wall):
                        if slide_dx > 0: self.rect.right = wall.left
                        elif slide_dx < 0: self.rect.left = wall.right
        elif blocked_x and blocked_y:
            # Both axes blocked - force repath
            self.path = []
            self.path_timer = 0
    def _apply_move(self, move_x, move_y, walls):
        # Delta-time aware: callers pass per-frame movement; multiply by _dt_mul.
        _dt_mul = self._dt_mul
        move_x *= _dt_mul
        move_y *= _dt_mul
        self.rect.x += move_x
        for wall in walls:
            if self.rect.colliderect(wall):
                if move_x > 0: self.rect.right = wall.left
                elif move_x < 0: self.rect.left = wall.right
        self.rect.y += move_y
        for wall in walls:
            if self.rect.colliderect(wall):
                if move_y > 0: self.rect.bottom = wall.top
                elif move_y < 0: self.rect.top = wall.bottom
    def _gun_pos(self):
        """World-space enemy muzzle position.
        Matches Enemy.draw():
        arm_len = 15
        grip offset = 4
        gun length = 20
        """
        reach = 15 + 4 + 20
        return (
            self.rect.centerx + math.cos(self.angle) * reach,
            self.rect.centery + math.sin(self.angle) * reach,
        )
    def _shoot(self, px, py, bullets, particles, walls):
        gx, gy = self._gun_pos()
        spread = _rng_legacy.uniform(-0.06, 0.06)
        # Spawn exactly at the muzzle, not 5 pixels ahead of it.
        bx = gx
        by = gy
        damage = 8 if self.is_ambush_enemy else ENEMY_DAMAGE
        bullets.append({
            "x": bx, "y": by,
            "dx": math.cos(self.angle + spread) * 18,
            "dy": math.sin(self.angle + spread) * 18,
            "life": 60,
            "owner": "enemy",
            "damage": damage,
        })
        for _ in range(4):
            particles.append(Particle(bx, by, (255, 200, 100)))
        audio.play_3d(
            "gunshot_distant",
            (self.rect.centerx, self.rect.centery),
            (px, py),
            base_volume=0.4,
        )
    def hear_shot(self, sx: float, sy: float, walls: list) -> None:
        # Hearing works through walls: gunfire alerts within radius even
        # without a sightline. LOS only controls how precise the fix is -
        # a heard shot through a wall is noisier than a seen one.
        dist = math.hypot(sx - self.rect.centerx, sy - self.rect.centery)
        if dist >= ENEMY_HEAR_RADIUS:
            return
        has_los = self._can_see(sx, sy, walls)
        spread = TILE_SIZE // 3 if has_los else TILE_SIZE
        noise = _rng_legacy.randint(-spread, spread)
        noisy_pos = (sx + noise, sy + noise)
        if self.state in ("CHASE", "ATTACK"):
            if dist < TILE_SIZE * 6:
                self.last_seen_pos = noisy_pos
                self.combat_alert_timer = max(self.combat_alert_timer, 360)
            elif not has_los:
                # Distant muffled shot while already fighting: stay in the
                # fight but stay combat-aware instead of ignoring it.
                self.combat_alert_timer = max(self.combat_alert_timer, 240)
            return
        if self.state == "SEARCH":
            self.combat_alert_timer = max(self.combat_alert_timer, 360)
            self.sweep_points = [noisy_pos]
            self.distraction_target = self.sweep_points.pop(0)
            self.search_timer = max(self.search_timer, 180)
            return
        self.alerted = True
        self.state = "SEARCH"
        self.search_timer = 210
        self.combat_alert_timer = 300
        self.distraction_target = noisy_pos
        self.sweep_points = []
        self.path = []
        self.path_timer = 0
    def on_hit(self, shooter_x: float, shooter_y: float) -> None:
        self.alerted = True
        self.combat_alert_timer = 480
        noise = _rng_legacy.randint(-TILE_SIZE // 4, TILE_SIZE // 4)
        self.last_seen_pos = (shooter_x + noise, shooter_y + noise)
        if self.state not in ("ATTACK",):
            self.state = "CHASE"
        self.sweep_points = []
        self.path = []
        self.path_timer = 0
        if self.fire_cooldown <= 0:
            self.fire_cooldown = _rng_legacy.randint(8, 40)
    def draw(self, surface, offset_x, offset_y):
        draw_x = self.rect.centerx - offset_x
        draw_y = self.rect.centery - offset_y
        a = self.angle
        d_x = math.cos(a)
        d_y = math.sin(a)
        perp_x = math.cos(a + math.pi / 2)
        perp_y = math.sin(a + math.pi / 2)
        # Continuous walk sway: phase advances with actual displacement, so
        # motion never quantises (same lesson as the player aim-snap revert).
        _moved = self.walk.advance(self.rect.centerx, self.rect.centery)
        _ph = self.walk.phase
        _sway = math.sin(_ph) * 1.6 if _moved > 0.4 else math.sin(_ph * 0.25) * 0.5
        draw_x += perp_x * _sway
        draw_y += perp_y * _sway
        surface.blit(_enemy_shadow, (int(draw_x - 17), int(draw_y - 5)))
        is_cmdr = self.is_commander
        is_mag = self.is_ambush_enemy
        if is_cmdr:
            uniform_col = (35, 32, 45)
            skin_col = (175, 145, 120)
        elif is_mag:
            uniform_col = C_MAG_UNIFORM
            skin_col = C_ENEMY_SKIN
        else:
            uniform_col = C_IPA_UNIFORM
            skin_col = C_ENEMY_SKIN
        body_w, body_h = 20, 13
        cos_b, sin_b = math.cos(a), math.sin(a)
        torso_pts = []
        for bx, by in [
            (-body_w // 2, -body_h // 2),
            (body_w // 2, -body_h // 2),
            (body_w // 2, body_h // 2),
            (-body_w // 2, body_h // 2),
        ]:
            rx = bx * cos_b - by * sin_b
            ry = bx * sin_b + by * cos_b
            torso_pts.append((draw_x + rx, draw_y + ry))
        pygame.draw.polygon(surface, uniform_col, torso_pts)
        pygame.draw.line(
            surface,
            (uniform_col[0] + 10, uniform_col[1] + 8, uniform_col[2] + 6),
            (draw_x - d_x * 4, draw_y - d_y * 4),
            (draw_x + d_x * 4, draw_y + d_y * 4),
            2,
        )
        ls_x = draw_x + perp_x * 11
        ls_y = draw_y + perp_y * 11
        rs_x = draw_x - perp_x * 11
        rs_y = draw_y - perp_y * 11
        arm_len = 15
        hand_x = draw_x + d_x * arm_len
        hand_y = draw_y + d_y * arm_len
        pygame.draw.line(
            surface, uniform_col, (ls_x, ls_y),
            (hand_x - perp_x * 3, hand_y - perp_y * 3), 5
        )
        pygame.draw.line(
            surface, uniform_col, (rs_x, rs_y),
            (hand_x + perp_x * 3, hand_y + perp_y * 3), 5
        )
        grip_x = draw_x + d_x * (arm_len + 4)
        grip_y = draw_y + d_y * (arm_len + 4)
        pygame.draw.circle(surface, skin_col, (int(grip_x), int(grip_y)), 4)
        gun_start_x = grip_x + d_x * 2
        gun_start_y = grip_y + d_y * 2
        gun_end_x = grip_x + d_x * 20
        gun_end_y = grip_y + d_y * 20
        pygame.draw.line(
            surface, (35, 30, 25), (gun_start_x, gun_start_y), (gun_end_x, gun_end_y), 3
        )
        pygame.draw.circle(surface, (55, 48, 40), (int(gun_end_x), int(gun_end_y)), 2)
        head_x = draw_x + d_x * 2
        head_y = draw_y + d_y * 2
        head_r = 8
        pygame.draw.circle(surface, skin_col, (int(head_x), int(head_y)), head_r)
        
        # Draw armbands on standard IPA guards
        if not is_cmdr and not is_mag:
            band_x1 = draw_x + perp_x * 9
            band_y1 = draw_y + perp_y * 9
            band_x2 = band_x1 + d_x * 4
            band_y2 = band_y1 + d_y * 4
            pygame.draw.line(surface, C_IPA_ARMBAND,
                             (int(band_x1), int(band_y1)),
                             (int(band_x2), int(band_y2)), 3)

        if is_cmdr:
            beret_x = int(head_x - d_x * 2)
            beret_y = int(head_y - d_y * 2)
            pygame.draw.circle(surface, (160, 30, 30), (beret_x, beret_y), head_r + 1)
            pygame.draw.circle(surface, skin_col, (int(head_x), int(head_y)), head_r)
            pip1_x = draw_x + perp_x * 8 - d_x * 3
            pip1_y = draw_y + perp_y * 8 - d_y * 3
            pip2_x = pip1_x - d_x * 4
            pip2_y = pip1_y - d_y * 4
            pygame.draw.circle(surface, (220, 190, 60), (int(pip1_x), int(pip1_y)), 2)
            pygame.draw.circle(surface, (220, 190, 60), (int(pip2_x), int(pip2_y)), 2)
            band_x1 = draw_x + perp_x * 10
            band_y1 = draw_y + perp_y * 10
            band_x2 = band_x1 + d_x * 6
            band_y2 = band_y1 + d_y * 6
            pygame.draw.line(surface, (180, 30, 30),
                             (int(band_x1), int(band_y1)),
                             (int(band_x2), int(band_y2)), 4)
            label = font_terminal_small.render(_T("enemy_ai.cmdr"), True, (220, 80, 60))
            surface.blit(label, (int(draw_x - label.get_width() // 2), int(draw_y - 28)))
        elif is_mag:
            # Draw MAG bandana on the head
            pygame.draw.circle(surface, C_MAG_BANDANA, (int(head_x - d_x * 2), int(head_y - d_y * 2)), head_r - 1)
            tail1_x = int(head_x - d_x * 8 + perp_x * 3)
            tail1_y = int(head_y - d_y * 8 + perp_y * 3)
            tail2_x = int(head_x - d_x * 8 - perp_x * 3)
            tail2_y = int(head_y - d_y * 8 - perp_y * 3)
            pygame.draw.line(surface, C_MAG_BANDANA, (int(head_x - d_x * 6), int(head_y - d_y * 6)), (tail1_x, tail1_y), 2)
            pygame.draw.line(surface, C_MAG_BANDANA, (int(head_x - d_x * 6), int(head_y - d_y * 6)), (tail2_x, tail2_y), 2)
            
            label = font_terminal_small.render(_T("enemy_ai.mag"), True, (80, 180, 100))
            surface.blit(label, (int(draw_x - label.get_width() // 2), int(draw_y - 28)))
        else:
            pygame.draw.arc(
                surface, (25, 18, 14),
                (int(head_x - head_r), int(head_y - head_r), head_r * 2, head_r * 2),
                a + 1.2, a + math.pi * 2 - 1.2, 3
            )
        face_x = head_x + d_x * 2
        face_y = head_y + d_y * 2
        for ang_off in (-0.25, 0.25):
            ex = face_x + math.cos(a + ang_off) * 3
            ey = face_y + math.sin(a + ang_off) * 3
            pygame.draw.circle(surface, (40, 25, 15), (int(ex), int(ey)), 1)
def enemy_hear_shot(sx, sy, enemies, walls):
    for e in enemies:
        e.hear_shot(sx, sy, walls)
