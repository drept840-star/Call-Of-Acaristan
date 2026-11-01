"""Mission 1 stealth (rework WP5, plan section d).

Per-enemy suspicion 0..1 fed by the enemy_ai sight cone and the light the player
stands in; a 2 s radio call before the alarm latches gives the player a window to
fix a mistake. Bricks make noise, bodies get found, takedowns are silent.

States per enemy: UNAWARE (<0.35), SUSPICIOUS (0.35-<1.0), SEARCHING (1.0, local);
ALARM is the global latch (core.interactions.trigger_alarm_early).

All per-run state lives on STATE under leading-underscore names (the replay hash
skips those, so other missions' snapshots stay as they were).
"""
import math
import pygame
from core.config import ENEMY_DETECT_RANGE, TILE_SIZE, audio, get_scaled_mouse
from core.state import STATE
from core.interactions import trigger_alarm_early, trigger_radio_chatter
from entities.player import MELEE_RANGE
import game.dialogues as _dialogues  # RPE6 P7: bark text from m1.radio
from missions.m1.map import _tc

UNAWARE, SUSPICIOUS, SEARCHING = "UNAWARE", "SUSPICIOUS", "SEARCHING"

SUSPICIOUS_AT = 0.35
FILL_BASE = 1.25            # suspicion / s while seen, times the three factors
DIST_NEAR, DIST_FAR = 120.0, float(ENEMY_DETECT_RANGE)
DIST_K_NEAR, DIST_K_FAR = 1.6, 0.4
LIGHT_K_LIT, LIGHT_K_DARK = 1.5, 0.55
MOVE_K_WALK, MOVE_K_STILL = 1.0, 0.7   # (no sprint in M1 yet; the plan's 1.3 has no input)
DECAY_PER_S = 0.25
DECAY_HOLD_S = 1.5
CONE_CALM, CONE_ALERT = math.radians(45), math.radians(80)
TURN_S = 0.8                # suspicious: turn to the point, then walk there
SUSPICIOUS_SPEED = 1.2
SEARCH_S = 6.0
RADIO_CALL_S = 2.0
NOISE_RADIUS = 250.0
NOISE_S = 6.0
BODY_RADIUS = 250.0
TAKEDOWN_REAR_HALF = math.radians(60)   # rear 120 deg arc
TAKEDOWN_LOCK_FRAMES = 24               # 0.4 s
TAKEDOWN_HINT_RANGE = 2 * TILE_SIZE
LAMP_RADIUS_SCALE = 0.8                 # the drawn pool (render_util.push_lamps radius_scale)

BRICK_PILES = ((5, 5), (12, 9), (2, 12))
BRICKS_PER_PILE = 2
BRICK_CAP = 3


def reset_stealth():
    """Called from start_mission: fresh minds, piles, bricks."""
    STATE._m1_stealth = {}
    STATE._m1_found_bodies = []
    STATE._m1_brick_impacts = []
    STATE._m1_bricks = 0
    STATE._m1_brick_piles = [list(_tc(c, r)) + [BRICKS_PER_PILE] for c, r in BRICK_PILES]
    STATE._m1_player_seen = False
    STATE._m1_takedown_lock = 0
    STATE._m1_hints = set()
    STATE._m1_inside_said = False


def _mind(e):
    minds = STATE._m1_stealth
    m = minds.get(e.uid)
    if m is None:
        m = minds[e.uid] = {"s": 0.0, "state": UNAWARE, "hold": 0.0, "point": None,
                            "sus_t": 0.0, "noise_t": 0.0, "search_t": 0.0,
                            "call_t": 0.0, "call_seen": False, "barked": set(),
                            "speed": e.speed}
    return m


def mind_of(e):
    """Read-only view for the HUD / tests (None before the first stealth frame)."""
    return getattr(STATE, "_m1_stealth", {}).get(e.uid)


def _angle_diff(a, b):
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def sees(e, px, py, sight_walls):
    """Plan sight test: cone +-45 calm / +-80 alerted, 350 px, LOS through sight walls
    (chain-link fences are not in them)."""
    dx, dy = px - e.rect.centerx, py - e.rect.centery
    if math.hypot(dx, dy) > ENEMY_DETECT_RANGE * e.sight_mul:
        return False
    half = CONE_ALERT if e.alerted else CONE_CALM
    if _angle_diff(math.atan2(dy, dx), e.angle) > half:
        return False
    return e._can_see(px, py, sight_walls)


def dist_k(d):
    if d <= DIST_NEAR:
        return DIST_K_NEAR
    if d >= DIST_FAR:
        return DIST_K_FAR
    u = (d - DIST_NEAR) / (DIST_FAR - DIST_NEAR)
    return DIST_K_NEAR + (DIST_K_FAR - DIST_K_NEAR) * u


def in_light(px, py):
    from missions.m1.draw import _M1_LAMPS  # lazy: draw loads after this part
    for tx, ty, r, _col, _key in _M1_LAMPS:
        if math.hypot(px - tx * TILE_SIZE, py - ty * TILE_SIZE) < r * LAMP_RADIUS_SCALE:
            return True
    return False


def fill_rate(d, lit, moving):
    return (FILL_BASE * dist_k(d) * (LIGHT_K_LIT if lit else LIGHT_K_DARK)
            * (MOVE_K_WALK if moving else MOVE_K_STILL))


def _bark(e, m, node, legacy):
    if node in m["barked"]:
        return
    m["barked"].add(node)
    STATE.floating_texts.append([e.rect.centerx, e.rect.centery - 44,
                                 _dialogues.line("m1.radio", node, legacy), (225, 215, 190), 110])


def _calm(e, m, s):
    e.alerted = False
    e.combat_alert_timer = 0
    e.state = "PATROL" if e.patrol_points else "IDLE"
    e.distraction_target = None
    e.sweep_points = []
    e.path = []
    e.speed = m["speed"]
    m.update(state=UNAWARE, s=s, hold=0.0, noise_t=0.0, call_t=0.0, call_seen=False)


def _start_call(m):
    m["call_t"] = RADIO_CALL_S
    m["call_seen"] = False


def _enter_search(e, m, point, walls, drive=True):
    """SEARCHING: local alert + the radio call. ``drive`` False keeps whatever the
    enemy_ai already chose (a heard shot / a hit set its own SEARCH or CHASE)."""
    m.update(state=SEARCHING, s=1.0, point=point, search_t=SEARCH_S, hold=0.0, noise_t=0.0)
    _start_call(m)
    e.speed = m["speed"]
    e.alerted = True
    if drive and e.state not in ("CHASE", "ATTACK"):
        e.state = "SEARCH"
        e.search_timer = int(SEARCH_S * 60)
        e.last_seen_pos = point
        e.sweep_points = e._build_sweep_points(point[0], point[1], walls)
        e.distraction_target = point
        e.path = []
        e.path_timer = 0
    _bark(e, m, "bark_search", "Check the corner.")


def _enter_suspicious(e, m):
    m["state"] = SUSPICIOUS
    m["sus_t"] = 0.0
    e.path = []
    _bark(e, m, "bark_suspicious", "Hm? Who's there?")


def _tick_suspicious(e, m, dt):
    m["sus_t"] += dt
    pt = m["point"]
    if pt is None:
        return
    e.last_seen_pos = pt
    if m["sus_t"] < TURN_S:
        e.state = "HOLD"                 # no enemy_ai branch: it stands while turning
        e._ease_toward_angle(math.atan2(pt[1] - e.rect.centery, pt[0] - e.rect.centerx), 0.12)
        return
    if e.state != "SEARCH" or e.distraction_target is not None:
        e.state = "SEARCH"
        e.search_timer = 9999            # stealth ends it, not the enemy_ai timer
        e.sweep_points = []
        e.speed = SUSPICIOUS_SPEED
        if e.distraction_target != pt:
            e.distraction_target = pt
            e.path_timer = 0


def _walls_between(x0, y0, x1, y1, walls):
    return sum(1 for w in walls if w.clipline((x0, y0), (x1, y1)))


def _hear_brick(e, m, ix, iy, sight_walls):
    if math.hypot(e.rect.centerx - ix, e.rect.centery - iy) > NOISE_RADIUS:
        return
    if _walls_between(ix, iy, e.rect.centerx, e.rect.centery, sight_walls) > 1:
        return                           # LOS or one wall's thickness only
    m["point"] = (ix, iy)
    m["noise_t"] = NOISE_S
    m["s"] = max(m["s"], SUSPICIOUS_AT)
    _enter_suspicious(e, m)


def _find_body(e, sight_walls):
    for c in getattr(STATE, "corpses", ()) or ():
        if c in STATE._m1_found_bodies:
            continue
        if math.hypot(c.x - e.rect.centerx, c.y - e.rect.centery) > BODY_RADIUS:
            continue
        if sees(e, c.x, c.y, sight_walls):
            STATE._m1_found_bodies.append(c)
            return (c.x, c.y)
    return None


def stealth_update(dt, moving, sight_walls, walls):
    """One stealth frame, before the enemies update. Latches the alarm through
    trigger_alarm_early() when a radio call completes."""
    if not hasattr(STATE, "_m1_stealth"):
        reset_stealth()
    p = STATE.player
    if p is None or STATE.player_dead:
        STATE._m1_player_seen = False
        return
    px, py = p.rect.centerx, p.rect.centery
    enemies = STATE.enemies
    STATE._m1_player_seen = any(sees(e, px, py, sight_walls) for e in enemies)
    impacts, STATE._m1_brick_impacts = STATE._m1_brick_impacts, []
    for ix, iy in impacts:
        audio.play_3d("debris_settle", (ix, iy), (px, py), base_volume=0.7)
    if STATE.firefight_triggered:
        STATE._m1_stealth = {}
        return
    if not STATE._m1_inside_said and py >= (11 * TILE_SIZE):
        STATE._m1_inside_said = True
        trigger_radio_chatter('VASILE: "{}"'.format(
            _dialogues.line("m1.radio", "inside_quiet", "Clean so far. Keep it that way.")))
    live = {e.uid for e in enemies}
    for uid in [u for u in STATE._m1_stealth if u not in live]:
        del STATE._m1_stealth[uid]       # a dead caller cancels its radio call
    corpses = getattr(STATE, "corpses", ()) or ()
    STATE._m1_found_bodies = [c for c in STATE._m1_found_bodies if c in corpses]
    lit = in_light(px, py)
    for e in enemies:
        m = _mind(e)
        if (e.alerted or e.combat_alert_timer > 0) and m["state"] != SEARCHING:
            # Alerted by an existing path (heard shot, hit, fire): straight to SEARCHING.
            # (A guard already walking to a suspicious point only gets its combat timer
            # raised by enemy_ai.hear_shot, hence the second test.)
            pt = e.distraction_target or e.last_seen_pos or (e.rect.centerx, e.rect.centery)
            _enter_search(e, m, pt, walls, drive=False)
        if m["state"] != SEARCHING:
            for ix, iy in impacts:
                _hear_brick(e, m, ix, iy, sight_walls)
            body = _find_body(e, sight_walls)
            if body is not None:
                _enter_search(e, m, body, walls)
        seen = sees(e, px, py, sight_walls)
        if seen:
            m["point"] = (px, py)
            m["hold"] = 0.0
            if m["state"] != SEARCHING:
                d = math.hypot(px - e.rect.centerx, py - e.rect.centery)
                m["s"] = min(1.0, m["s"] + fill_rate(d, lit, moving) * dt)
        else:
            m["hold"] += dt
            if m["hold"] >= DECAY_HOLD_S and m["state"] != SEARCHING:
                floor = SUSPICIOUS_AT if m["noise_t"] > 0 else 0.0
                m["s"] = max(floor, m["s"] - DECAY_PER_S * dt)
        m["noise_t"] = max(0.0, m["noise_t"] - dt)

        if m["state"] == SEARCHING:
            if m["call_t"] > 0:
                m["call_seen"] = m["call_seen"] or seen
                m["call_t"] -= dt
                if m["call_t"] <= 0:
                    m["call_t"] = 0.0
                    if m["call_seen"]:
                        trigger_alarm_early()
                        STATE._m1_stealth = {}
                        return
            elif seen:
                _start_call(m)
            if seen:
                m["search_t"] = SEARCH_S
            else:
                m["search_t"] -= dt
                if m["search_t"] <= 0 and m["call_t"] <= 0:
                    _calm(e, m, SUSPICIOUS_AT - 0.01)
        elif m["s"] >= 1.0:
            _enter_search(e, m, m["point"] or (px, py), walls)
        elif m["s"] >= SUSPICIOUS_AT:
            if m["state"] != SUSPICIOUS:
                _enter_suspicious(e, m)
            _tick_suspicious(e, m, dt)
        elif m["state"] == SUSPICIOUS:
            _calm(e, m, m["s"])
        elif (("takedown" not in STATE._m1_hints)
              and math.hypot(px - e.rect.centerx, py - e.rect.centery) < TAKEDOWN_HINT_RANGE
              and _in_rear_arc(e, px, py)):
            STATE._m1_hints.add("takedown")
            STATE.floating_texts.append([px, py - 50, "V - takedown", (200, 210, 190), 150])


def _in_rear_arc(e, px, py):
    to_player = math.atan2(py - e.rect.centery, px - e.rect.centerx)
    return _angle_diff(to_player, e.angle + math.pi) <= TAKEDOWN_REAR_HALF


def takedown_target(player, enemies, walls):
    """Nearest UNAWARE/SUSPICIOUS enemy within MELEE_RANGE with the player in its rear
    120 deg arc and no wall between, or None (then the normal melee runs)."""
    if STATE.firefight_triggered:
        return None
    px, py = player.rect.centerx, player.rect.centery
    best, best_d = None, float("inf")
    for e in enemies:
        if e.alerted or e.hp <= 0:
            continue
        m = mind_of(e)
        if m is not None and m["state"] == SEARCHING:
            continue
        d = math.hypot(e.rect.centerx - px, e.rect.centery - py)
        if d >= MELEE_RANGE or d >= best_d or not _in_rear_arc(e, px, py):
            continue
        if any(w.clipline((px, py), e.rect.center) for w in walls):
            continue
        best, best_d = e, d
    return best


def do_takedown(e):
    """Instant silent kill: no hear event; the death funnel lays the corpse."""
    e.hp = 0
    STATE._m1_takedown_lock = TAKEDOWN_LOCK_FRAMES


def update_bricks():
    """Pick up from rubble piles (2 per pile, carry cap 3)."""
    p = STATE.player
    if p is None or STATE.player_dead:
        return
    for pile in STATE._m1_brick_piles:
        if pile[2] <= 0 or STATE._m1_bricks >= BRICK_CAP:
            continue
        if math.hypot(pile[0] - p.rect.centerx, pile[1] - p.rect.centery) < 30:
            take = min(pile[2], BRICK_CAP - STATE._m1_bricks)
            pile[2] -= take
            STATE._m1_bricks += take
            STATE.floating_texts.append([pile[0], pile[1] - 16, "+%d BRICK%s" % (take, "S" if take > 1 else ""),
                                         (200, 150, 120), 70])
            audio.play("pickup", volume=0.4)
            if "brick" not in STATE._m1_hints:
                STATE._m1_hints.add("brick")
                STATE.floating_texts.append([p.rect.centerx, p.rect.centery - 50,
                                             "Q - throw brick (noise)", (200, 210, 190), 180])


def throw_brick():
    """Q in M1: the bottle arc from entities.weapons, flagged as a brick (no fire)."""
    p = STATE.player
    if p is None or STATE.player_dead or STATE.truck_hotwiring:
        return
    if getattr(STATE, "_m1_bricks", 0) <= 0:
        STATE.floating_texts.append([p.rect.centerx, p.rect.centery - 40, "NO BRICKS", (220, 60, 60), 60])
        return
    from game import topdown3d as td
    tx, ty = td.mouse_world()
    dx, dy = tx - p.rect.centerx, ty - p.rect.centery
    dist = math.hypot(dx, dy)
    if dist > 400:
        tx, ty = p.rect.centerx + dx / dist * 400, p.rect.centery + dy / dist * 400
    STATE._m1_bricks -= 1
    STATE.thrown_bottles.append({
        "x": p.rect.centerx, "y": p.rect.centery,
        "start_x": p.rect.centerx, "start_y": p.rect.centery,
        "tx": tx, "ty": ty, "t": 0.0, "speed": 0.035, "spin": 0.0, "brick": True,
    })
    audio.play("molotov_throw", volume=0.4)


# -- HUD: per-enemy arc meter over the head, hard 2 px pixels, white -> amber -> red --
_METER_WHITE = (235, 235, 225)
_METER_AMBER = (235, 165, 40)
_METER_RED = (220, 50, 40)
_METER_BACK = (30, 30, 28)
_METER_R = 11
_METER_STEPS = 18


_BRICK_FACE = (120, 62, 44)
_BRICK_EDGE = (60, 32, 24)
_BRICK_TOP = (160, 92, 66)


def draw_brick_piles(surface, cam_x, cam_y):
    """Rubble piles: one hard 12x6 brick per brick left, stacked; no glow."""
    for x, y, n in getattr(STATE, "_m1_brick_piles", ()):
        if n <= 0:
            continue
        bx, by = int(x - cam_x), int(y - cam_y)
        for i, (ox, oy) in enumerate(((-9, 2), (1, 3), (-4, -3))[:n + 1]):
            r = pygame.Rect(bx + ox, by + oy, 12, 6)
            surface.fill(_BRICK_EDGE, r)
            surface.fill(_BRICK_FACE, r.inflate(-2, -2))
            surface.fill(_BRICK_TOP, (r.x + 1, r.y + 1, 10, 1))


def meter_color(m):
    if m["state"] == SEARCHING:
        return _METER_RED
    return _METER_AMBER if m["s"] >= SUSPICIOUS_AT else _METER_WHITE


def draw_meters(surface, cam_x, cam_y):
    if STATE.firefight_triggered:
        return
    minds = getattr(STATE, "_m1_stealth", {})
    for e in STATE.enemies:
        m = minds.get(e.uid)
        if m is None or m["s"] <= 0.0:
            continue
        cx = int(e.rect.centerx - cam_x)
        cy = int(e.rect.centery - cam_y) - 30
        lit = int(round(m["s"] * _METER_STEPS))
        col = meter_color(m)
        for i in range(_METER_STEPS + 1):
            a = math.pi + math.pi * i / _METER_STEPS     # left -> over the top -> right
            x = cx + int(round(math.cos(a) * _METER_R)) - 1
            y = cy + int(round(math.sin(a) * _METER_R)) - 1
            surface.fill(col if i <= lit and lit > 0 else _METER_BACK, (x, y, 2, 2))
        if m["call_t"] > 0:                              # radio call: small red "!"
            surface.fill(_METER_RED, (cx - 1, cy - 9, 2, 6))
            surface.fill(_METER_RED, (cx - 1, cy - 1, 2, 2))
