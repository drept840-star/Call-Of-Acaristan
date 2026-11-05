"""Mission 4 siege: five waves on the station while the arrest airs.

The clock (STATE.m4_siege_t, frames) starts at -M4_JAMMER_COUNTDOWN when the
jammer goes in and runs to M4_SIEGE_FRAMES. Waves spawn loyalists from the
ring's insertion points; every loyalist runs a local brain on a Dijkstra
flow field to the transmitter rack, where barricades are passable at a cost
(so the field bends toward the weakest site, and a unit that reaches a
standing barricade has to break it).

  rifleman  shoots any defender in sight, otherwise shoots the barricade
            in its way
  marksman  holds at range and fires the laser-telegraphed pinned shot
  breacher  bashes planks and boards, plants a charge on a steel plate, and
            turns on Biribel when shot or crowded

Losing the rack (loyalists hold it M4_RACK_HOLD_FAIL frames uncontested)
fails the wave. A snapshot is taken M4_WAVE_GRACE frames before each wave;
the tower checkpoint restores the latest one. Snapshots live here, at module
level, so they survive STATE.reset().
"""

import copy
import heapq
import math

import pygame

from core.config import TILE_SIZE
from core.state import STATE
from engine.core import LEGACY_RNG as _rng_legacy
from fx import effects
from entities.enemy_ai import Enemy
from missions.m4 import maps as _m4_maps
from missions.m4.meta import (
    TRANSMITTER_TILE, M4_SIEGE_FRAMES, M4_WAVE_GRACE, M4_RACK_RADIUS, M4_RACK_HOLD_FAIL,
    M4_BREACH_CHARGE, M4_RUNNER_SUPPLY, M4_JAMMER_COUNTDOWN, M4_ROLE_TUNING,
    C_SYSTEM, C_VASILE, C_MARU, BIRIBEL_SPEAKER,
)
from missions.m4.world import (
    _m4g, _m4l, _radio, _sfx, _tile_world, _spawn_m4_guard, _add_sniper_laser,
    _decay_lasers, _shot_walls, _solid_walls, _damage_m4_ally, _ally_at, barricade_blocks_shots,
    M4_MARKSMAN_DAMAGE, fail_mission,
)
from missions.m4 import fortify
from missions.m4.escort import add_supply

T = TILE_SIZE
C_RUNNER = (150, 200, 140)

# start/end in siege frames; units = budget by kind; doors = insertion keys.
WAVES = (
    {"n": 1, "start": 0, "end": 4800, "cap": 6, "gap": 120,
     "units": (("loyalist", 14),), "doors": ("S", "SW", "SE")},
    {"n": 2, "start": 6000, "end": 10800, "cap": 7, "gap": 110,
     "units": (("loyalist", 14), ("marksman", 3)), "doors": ("S", "W", "E", "SW")},
    {"n": 3, "start": 12000, "end": 16800, "cap": 8, "gap": 100,
     "units": (("loyalist", 14), ("marksman", 3), ("breacher", 4)), "doors": ("W", "E", "N", "NW")},
    {"n": 4, "start": 18000, "end": 22800, "cap": 9, "gap": 95,
     "units": (("loyalist", 15), ("marksman", 4), ("breacher", 4)), "doors": ("E", "NE", "SE", "N"),
     "breach": 900},
    {"n": 5, "start": 24000, "end": 28800, "cap": 10, "gap": 90,
     "units": (("loyalist", 16), ("marksman", 4), ("breacher", 6)), "doors": ("S", "SW", "SE", "W", "E"),
     "apc": 300},
)
# Once a wave's budget is spent, reinforcements keep coming in small squads
# until this many frames before the wave window closes.
REFILL_STOP = 900
REFILL_SQUAD = 4
WAVE_LINES = {
    1: ("VASILE: Here they come - south side, off the forecourt!", C_VASILE),
    2: ("MARU: Marksmen on the ring. Watch for the red line and move.", C_MARU),
    3: ("VASILE: Breachers with them. They'll go for the doors - keep them patched.", C_VASILE),
    4: ("MARU: Engineers on the east ring. That corridor wall won't hold.", C_MARU),
    5: ("VASILE: Engine noise. Armour on the forecourt - get off the main door!", C_VASILE),
}
RUNNER_AT = {2: 5400, 3: 11400, 4: 17400, 5: 23400}

SNAPS = {}                  # wave n (or "station") -> snapshot dict
_RT = {"flow": None, "flow_key": None, "pool": [], "spawn_t": 0, "wave": 0}


def wave_of(t):
    for w in WAVES:
        if t < w["end"]:
            return w
    return WAVES[-1]


def current_wave():
    return getattr(STATE, "m4_wave", 0)


def reset_runtime():
    _RT.update(flow=None, flow_key=None, pool=[], spawn_t=0, wave=0)
    STATE.m4_rack_hold = 0
    STATE.m4_wave = 0


def clear_snapshots():
    SNAPS.clear()


# ─────────────────────────────────────────────
# Flow field to the rack
# ─────────────────────────────────────────────
def _rack_goal():
    c, r = TRANSMITTER_TILE
    return c, r + 1


def rack_pos():
    return _tile_world(*_rack_goal())


def _static_free(walls, w, h):
    free = [[True] * w for _ in range(h)]
    probe = pygame.Rect(0, 0, 30, 30)
    for r in range(h):
        for c in range(w):
            probe.center = (c * T + T // 2, r * T + T // 2)
            if probe.collidelist(walls) != -1:
                free[r][c] = False
    return free


def _flow_key():
    bars = tuple(sorted((k, b["kind"]) for k, b in STATE.m4_barricades.items()
                        if fortify.standing(b)))
    return bars, len(STATE.walls), bool(getattr(STATE, "m4_breached", False))


def flow():
    key = _flow_key()
    if _RT["flow_key"] == key and _RT["flow"] is not None:
        return _RT["flow"]
    w, h = _m4_maps._live_map_dims()
    free = _static_free(STATE.walls, w, h)
    cost = {}
    for (c, r), b in STATE.m4_barricades.items():
        if fortify.standing(b):
            cost[(c, r)] = 4 + b["max"] / 40.0
    INF = float("inf")
    dist = [[INF] * w for _ in range(h)]
    gc, gr = _rack_goal()
    dist[gr][gc] = 0.0
    heap = [(0.0, gc, gr)]
    while heap:
        d, c, r = heapq.heappop(heap)
        if d > dist[r][c]:
            continue
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nc, nr = c + dc, r + dr
            if not (0 <= nc < w and 0 <= nr < h) or not free[nr][nc]:
                continue
            nd = d + cost.get((nc, nr), 1.0)
            if nd < dist[nr][nc]:
                dist[nr][nc] = nd
                heapq.heappush(heap, (nd, nc, nr))
    _RT["flow"] = dist
    _RT["flow_key"] = key
    return dist


def _next_tile(dist, c, r):
    h, w = len(dist), len(dist[0])
    best, best_d = None, dist[r][c] if (0 <= r < h and 0 <= c < w) else float("inf")
    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nc, nr = c + dc, r + dr
        if 0 <= nc < w and 0 <= nr < h and dist[nr][nc] < best_d:
            best, best_d = (nc, nr), dist[nr][nc]
    return best


# ─────────────────────────────────────────────
# Spawning
# ─────────────────────────────────────────────
def _pool_for(w):
    pool = [k for k, n in w["units"] for _ in range(n)]
    _rng_legacy.shuffle(pool)
    # Breachers never lead a wave: the first bodies through are rifles.
    for i in range(min(2, len(pool))):
        if pool[i] == "breacher":
            j = next((j for j in range(2, len(pool)) if pool[j] != "breacher"), None)
            if j is not None:
                pool[i], pool[j] = pool[j], pool[i]
    return pool


def _spawn(kind, door):
    col, row = _m4_maps.STATION_SPAWNS[door]
    x, y = _tile_world(col, row)
    x += _rng_legacy.randint(-12, 12)
    y += _rng_legacy.randint(-12, 12)
    e = _spawn_m4_guard(x - 16, y - 16, etype=kind, label="wave%d_%s" % (current_wave(), kind),
                        aware=True)
    g = _m4g(e)
    g.loyalist = True
    g.focus_t = _rng_legacy.randint(0, 11)
    e.state = "CHASE"
    e.combat_alert_timer = 0
    e.fire_cooldown = _rng_legacy.randint(30, 80)
    return e


def alive():
    return [e for e in STATE.enemies if e.hp > 0 and _m4g(e).loyalist]


def _run_spawns(t):
    w = wave_of(t)
    if not (w["start"] <= t < w["end"]):
        return
    if _RT["wave"] != w["n"]:
        _RT["wave"] = w["n"]
        _RT["pool"] = _pool_for(w)
        _RT["spawn_t"] = 0
        STATE.m4_wave = w["n"]
        line, color = WAVE_LINES[w["n"]]
        _radio(line, color=color, duration=380, mark="wave_%d" % w["n"])
        _sfx("alarm", 0.25)
    if not _RT["pool"]:
        # Budget spent and the floor clear: the next squad is already inbound.
        if t < w["end"] - REFILL_STOP and len(alive()) <= w["cap"] // 3:
            kinds = [k for k, _ in w["units"] if k != "breacher"] or ["loyalist"]
            _RT["pool"] = ["loyalist"] * (REFILL_SQUAD - 1) + [_rng_legacy.choice(kinds)]
            _RT["spawn_t"] = min(_RT["spawn_t"], 90)
        else:
            return
    _RT["spawn_t"] -= 1
    if _RT["spawn_t"] > 0 or len(alive()) >= w["cap"]:
        return
    _RT["spawn_t"] = w["gap"] + _rng_legacy.randint(-20, 20)
    _spawn(_RT["pool"].pop(0), _rng_legacy.choice(w["doors"]))


# ─────────────────────────────────────────────
# Loyalist brain
# ─────────────────────────────────────────────
def _defenders():
    out = []
    p = STATE.player
    if p is not None and not getattr(STATE, "player_dead", False):
        out.append(("player", p.rect.centerx, p.rect.centery))
    for a in getattr(STATE, "m4_allies", []):
        if not a.get("dead") and a.get("downed", 0) <= 0:
            out.append((a["name"], a["x"], a["y"]))
    return out


def _target_pos(name):
    if name == "player":
        p = STATE.player
        if p is None or getattr(STATE, "player_dead", False):
            return None
        return p.rect.centerx, p.rect.centery
    for a in getattr(STATE, "m4_allies", []):
        if a["name"] == name and not a.get("dead") and a.get("downed", 0) <= 0:
            return a["x"], a["y"]
    return None


def _pick_target(e, sight, reach):
    """Nearest defender in sight and reach (re-rolled every 12 frames)."""
    g = _m4g(e)
    g.focus_t -= 1
    if g.focus_t > 0 and g.focus:
        pos = _target_pos(g.focus)
        if pos is not None:
            return pos
    g.focus_t = 12
    ex, ey = e.rect.centerx, e.rect.centery
    best, best_d = None, reach
    for name, x, y in _defenders():
        d = math.hypot(x - ex, y - ey)
        # Biribel draws the fire: an ally has to be clearly closer to be picked.
        score = d if name == "player" else d * 1.35
        if d < reach and score < best_d and e._can_see(x, y, sight):
            best, best_d = name, score
    g.focus = best or ""
    return _target_pos(best) if best else None


def _face(e, x, y, rate=0.25):
    e._ease_toward_angle(math.atan2(y - e.rect.centery, x - e.rect.centerx), rate)


def _aimed(e, x, y, tol=0.18):
    want = math.atan2(y - e.rect.centery, x - e.rect.centerx)
    return abs((want - e.angle + math.pi) % (2 * math.pi) - math.pi) < tol


def _separate(e):
    px = py = 0.0
    for o in STATE.enemies:
        if o is e or o.hp <= 0:
            continue
        dx, dy = e.rect.centerx - o.rect.centerx, e.rect.centery - o.rect.centery
        d = math.hypot(dx, dy)
        if 0 < d < 30:
            px += dx / d * (30 - d) * 0.08
            py += dy / d * (30 - d) * 0.08
    return px, py


def _move(e, mx, my, walls):
    """_apply_move with the sub-pixel remainder kept: pygame rects drop the
    fraction, so a slow sidestep along a wall edge would never happen."""
    m = e._dt_mul
    fx = getattr(e, "_m4_fx", 0.0) + mx * m
    fy = getattr(e, "_m4_fy", 0.0) + my * m
    ix, iy = int(fx), int(fy)
    e._m4_fx, e._m4_fy = fx - ix, fy - iy
    e._dt_mul = 1.0
    e._apply_move(ix, iy, walls)
    e._dt_mul = m


def _advance(e, walls, speed):
    """Step along the flow field. Returns the standing barricade site in the
    way (the next tile), or None."""
    dist = flow()
    c, r = e.rect.centerx // T, e.rect.centery // T
    nxt = _next_tile(dist, c, r)
    if nxt is None:
        return None
    bar = STATE.m4_barricades.get(nxt)
    if fortify.standing(bar):
        tx, ty = _tile_world(*nxt)
        if math.hypot(tx - e.rect.centerx, ty - e.rect.centery) < T * 1.05:
            return nxt
    tx, ty = _tile_world(*nxt)
    dx, dy = tx - e.rect.centerx, ty - e.rect.centery
    d = math.hypot(dx, dy) or 1.0
    sx, sy = _separate(e)
    _move(e, dx / d * speed + sx, dy / d * speed + sy, walls)
    _face(e, tx, ty, 0.12)
    return None


def _fire(e, x, y, walls):
    e.angle = math.atan2(y - e.rect.centery, x - e.rect.centerx)
    e._shoot(x, y, STATE.bullets, STATE.particles, walls)


def _blast(x, y, radius, damage):
    effects.burst(x, y, (255, 170, 70), 40)
    effects.burst(x, y, (90, 84, 78), 30)
    effects.shake(14)
    _sfx("explosion", 0.7)
    p = STATE.player
    if p is not None and not getattr(STATE, "player_dead", False):
        if math.hypot(p.rect.centerx - x, p.rect.centery - y) < radius:
            p.take_damage(damage)
    for a in getattr(STATE, "m4_allies", []):
        if not a.get("dead") and a.get("downed", 0) <= 0 and math.hypot(a["x"] - x, a["y"] - y) < radius:
            _damage_m4_ally(a, damage)
    for o in STATE.enemies:
        if o.hp > 0 and math.hypot(o.rect.centerx - x, o.rect.centery - y) < radius:
            o.hp -= damage


def _work_on(e, site, walls, kind):
    """A unit stopped at a standing barricade."""
    g = _m4g(e)
    bar = STATE.m4_barricades[site]
    sx, sy = fortify.site_center(*site)
    _face(e, sx, sy, 0.2)
    e.state = "ATTACK"
    if kind == "breacher":
        if bar["kind"] == "plate":
            g.charge += 1
            if g.charge == 1:
                STATE.floating_texts.append([sx, sy - 34, "CHARGE SET", (255, 140, 80), 90])
                _sfx("rifle_handle", 0.5)
            if g.charge >= M4_BREACH_CHARGE:
                g.charge = 0
                fortify.damage(site, bar["hp"])
                _blast(sx, sy, 96, 55)
            return
        g.work += 1
        if g.work % 36 == 0:
            fortify.damage(site, 40, sx, sy)
            effects.burst(sx, sy, (140, 110, 70), 10)
            _sfx("door_rattle", 0.4)
        return
    if kind == "marksman":
        return
    if not barricade_blocks_shots(bar):
        # Shot through: rounds pass the gaps now, so they rip the rest out by hand.
        g.work += 1
        if g.work % 45 == 0:
            fortify.damage(site, 12, sx, sy)
            effects.burst(sx, sy, (140, 110, 70), 8)
            _sfx("door_rattle", 0.35)
        return
    if e.fire_cooldown <= 0 and _aimed(e, sx, sy, 0.3):
        _fire(e, sx, sy, walls)
        e.fire_cooldown = _rng_legacy.randint(48, 72)   # working a barricade, not a firefight


def _retreat(e, walls, speed):
    """Stand-down: walk back out to the nearest insertion point and vanish."""
    best = min(_m4_maps.STATION_SPAWNS.values(),
               key=lambda t: math.hypot(t[0] * T - e.rect.centerx, t[1] * T - e.rect.centery))
    tx, ty = _tile_world(*best)
    dx, dy = tx - e.rect.centerx, ty - e.rect.centery
    d = math.hypot(dx, dy)
    if d < 40:
        e.hp = 0
        return
    _move(e, dx / d * speed, dy / d * speed, walls)
    _face(e, tx, ty, 0.15)
    e.state = "SEARCH"


def _brain(e, walls, sight):
    e._dt_mul = 60.0 * STATE.dt
    e.fire_cooldown -= 1
    if e.combat_alert_timer > 0:
        e.combat_alert_timer -= 1
    g = _m4g(e)
    kind = _m4l(e).kind or "loyalist"
    speed = M4_ROLE_TUNING.get(kind, M4_ROLE_TUNING["guard"])["speed"]
    if g.retreat:
        _retreat(e, walls, speed * 1.2)
        return
    ex, ey = e.rect.centerx, e.rect.centery
    p = STATE.player

    if kind == "breacher":
        near = (p is not None and not getattr(STATE, "player_dead", False)
                and math.hypot(p.rect.centerx - ex, p.rect.centery - ey) < 128)
        if e.combat_alert_timer > 0 or near:
            g.aggro = 240
        if g.aggro > 0 and p is not None and not getattr(STATE, "player_dead", False):
            g.aggro -= 1
            g.charge = 0
            px, py = p.rect.centerx, p.rect.centery
            d = math.hypot(px - ex, py - ey)
            _face(e, px, py, 0.3)
            e.state = "ATTACK"
            if d > 90:
                sx, sy = _separate(e)
                _move(e, (px - ex) / d * speed * 1.1 + sx, (py - ey) / d * speed * 1.1 + sy, walls)
            if d < 170 and e.fire_cooldown <= 0 and _aimed(e, px, py, 0.35) and e._can_see(px, py, sight):
                base = math.atan2(py - ey, px - ex)
                for i in range(4):
                    e.angle = base + (i - 1.5) * 0.09
                    e._shoot(px, py, STATE.bullets, STATE.particles, walls)
                e.angle = base
                _sfx("shotgun_blast", 0.35)
                e.fire_cooldown = 70
            return
        site = _advance(e, walls, speed)
        if site is not None:
            _work_on(e, site, walls, kind)
        else:
            e.state = "CHASE"
        return

    if kind == "marksman":
        tgt = _pick_target(e, sight, 620)
        if tgt is not None:
            _face(e, *tgt, rate=0.2)
            e.state = "ATTACK"
            busy = any(l.get("shooter") is e for l in getattr(STATE, "m4_lasers", []))
            if not busy and e.fire_cooldown <= 0:
                _add_sniper_laser(tgt, e._gun_pos(), life=54, shooter=e, damage=M4_MARKSMAN_DAMAGE)
                _sfx("rifle_handle", 0.3)
                e.fire_cooldown = _rng_legacy.randint(150, 200)
            return
        if math.hypot(rack_pos()[0] - ex, rack_pos()[1] - ey) > 6 * T:
            _advance(e, walls, speed)
        e.state = "CHASE"
        return

    # rifleman
    tgt = _pick_target(e, sight, 460)
    if tgt is not None:
        _face(e, *tgt, rate=0.25)
        e.state = "ATTACK"
        d = math.hypot(tgt[0] - ex, tgt[1] - ey)
        if d > 300:
            _advance(e, walls, speed * 0.6)
        if e.fire_cooldown <= 0 and _aimed(e, *tgt):
            _fire(e, tgt[0], tgt[1], walls)
            e.fire_cooldown = int(_rng_legacy.randint(34, 58) * e.fire_discipline)
        return
    if math.hypot(rack_pos()[0] - ex, rack_pos()[1] - ey) < 1.5 * T:
        e.state = "CHASE"
        return
    site = _advance(e, walls, speed)
    if site is not None:
        _work_on(e, site, walls, kind)
    else:
        e.state = "CHASE"


def update_enemies(walls):
    sight = _shot_walls()
    for e in STATE.enemies:
        if e.hp > 0 and _m4g(e).loyalist:
            _brain(e, walls, sight)


# ─────────────────────────────────────────────
# Rack, runners, the wave 4 wall
# ─────────────────────────────────────────────
def _update_rack():
    rx, ry = rack_pos()
    near = [e for e in alive() if not _m4g(e).retreat
            and math.hypot(e.rect.centerx - rx, e.rect.centery - ry) < M4_RACK_RADIUS]
    p = STATE.player
    contested = (p is not None and not getattr(STATE, "player_dead", False)
                 and math.hypot(p.rect.centerx - rx, p.rect.centery - ry) < M4_RACK_RADIUS)
    hold = getattr(STATE, "m4_rack_hold", 0)
    if near and not contested:
        hold += 1
        if hold == 1:
            _radio("VASILE: They're on the rack! Get back to the hall!", color=C_VASILE,
                   duration=260)
        if hold >= M4_RACK_HOLD_FAIL:
            fail_mission("rack")
    else:
        hold = max(0, hold - 2)
    STATE.m4_rack_hold = hold


def _runner(n):
    rx, ry = rack_pos()
    add_supply(M4_RUNNER_SUPPLY, rx, ry)
    _radio("MAG RUNNER: Timber through the back - %d loads. Patch what they broke." % M4_RUNNER_SUPPLY,
           color=C_RUNNER, duration=320, mark="runner_%d" % n)
    _sfx("pickup", 0.4)


def blow_wall():
    if getattr(STATE, "m4_breached", False):
        return
    STATE.m4_breached = True
    xs = [r.centerx for r in STATE.m4_breach_walls] or [0]
    ys = [r.centery for r in STATE.m4_breach_walls] or [0]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    for r in STATE.m4_breach_walls:
        if r in STATE.walls:
            STATE.walls.remove(r)
    _blast(cx, cy, 130, 45)
    for _ in range(3):
        effects.burst(cx + _rng_legacy.randint(-40, 40), cy + _rng_legacy.randint(-50, 50),
                      (120, 112, 100), 24)
    _radio("VASILE: East corridor - they blew the wall! Cover the gap!", color=C_VASILE,
           duration=380, mark="wall_blown")


# ─────────────────────────────────────────────
# Snapshots (wave restarts)
# ─────────────────────────────────────────────
_PLAYER_AMMO = ("ammo_in_mag", "spare_mags", "k9_ammo_in_mag", "k9_spare_mags",
                "os12_ammo_in_mag", "os12_spare_mags", "current_weapon")


def snapshot(n, t):
    allies = []
    for a in STATE.m4_allies:
        b = {k: v for k, v in a.items() if k != "path"}
        b["path"] = []
        b["path_goal"] = None
        allies.append(copy.deepcopy(b))
    bars = {k: {"kind": v["kind"], "hp": v["hp"], "max": v["max"], "rect": pygame.Rect(v["rect"])}
            for k, v in STATE.m4_barricades.items()}
    SNAPS[n] = {
        "wave": n, "t": t, "supply": STATE.m4_supply, "bars": bars,
        "breached": bool(getattr(STATE, "m4_breached", False)),
        "apc": copy.deepcopy(getattr(STATE, "m4_apc", None)),
        "allies": allies, "downs": STATE.m4_vasile_downs,
        "tone": list(getattr(STATE, "m4_tone", []) or []),
        "hp": STATE.player.hp if STATE.player else None,
        "ammo": {k: getattr(STATE, k, None) for k in _PLAYER_AMMO},
        "pickups": [list(p) for p in STATE.pickups],
    }


def latest():
    waves = [k for k in SNAPS if isinstance(k, int)]
    return SNAPS[max(waves)] if waves else None


def restore(s):
    STATE.m4_siege_t = s["t"]
    STATE.m4_supply = s["supply"]
    STATE.m4_barricades = {k: {"kind": v["kind"], "hp": v["hp"], "max": v["max"],
                               "rect": pygame.Rect(v["rect"])} for k, v in s["bars"].items()}
    if s["breached"]:
        STATE.m4_breached = False
        blow_quiet()
    STATE.m4_apc = copy.deepcopy(s.get("apc"))
    from missions.m4 import apc
    apc.restore_parked()
    STATE.m4_allies = copy.deepcopy(s["allies"])
    STATE.m4_vasile_downs = s["downs"]
    STATE.m4_tone = list(s["tone"])
    if STATE.player is not None and s["hp"]:
        STATE.player.hp = max(s["hp"], STATE.player.max_hp // 2)
    for k, v in s["ammo"].items():
        if v is not None:
            setattr(STATE, k, v)
    STATE.pickups = [list(p) for p in s["pickups"]]
    _RT.update(flow=None, flow_key=None, pool=[], spawn_t=0, wave=0)
    STATE.m4_wave = s["wave"]
    STATE.m4_rack_hold = 0
    # Lines and beats already aired before the snapshot stay aired.
    for w in WAVES:
        if w["n"] < s["wave"]:
            _m4_maps._radio_marks.add("wave_%d" % w["n"])
    for n, at in RUNNER_AT.items():
        if at < s["t"]:
            _m4_maps._radio_marks.add("runner_%d" % n)


def blow_quiet():
    STATE.m4_breached = True
    for r in STATE.m4_breach_walls:
        if r in STATE.walls:
            STATE.walls.remove(r)


# ─────────────────────────────────────────────
# Frame driver (called from flow._update_stage in STAGE_SIEGE)
# ─────────────────────────────────────────────
def update():
    t = getattr(STATE, "m4_siege_t", -M4_JAMMER_COUNTDOWN)
    if getattr(STATE, "m4_fail_reason", None):
        return t
    t += 1
    STATE.m4_siege_t = t
    for w in WAVES:
        if t == w["start"] - M4_WAVE_GRACE and w["n"] not in SNAPS:
            snapshot(w["n"], t)
    for n, at in RUNNER_AT.items():
        if t == at:
            _runner(n)
    if t == -M4_JAMMER_COUNTDOWN + 1:
        _radio("SYSTEM: Jammer live. First contact in ten seconds.", color=C_SYSTEM,
               duration=300, mark="countdown")
    if t >= 0:
        _run_spawns(t)
    w = wave_of(t)
    if w.get("breach") and t == w["start"] + w["breach"]:
        blow_wall()
    from missions.m4 import apc
    if w.get("apc") and t == w["start"] + w["apc"]:
        apc.start()
    apc.update()
    _decay_lasers()
    if t >= 0:
        _update_rack()
    return t


def stand_down():
    """Arrest beat: every loyalist breaks off and walks out."""
    for e in alive():
        _m4g(e).retreat = True
    _RT["pool"] = []


def hud_state():
    """(wave n, seconds to next wave or None, units left in the wave)."""
    t = getattr(STATE, "m4_siege_t", 0)
    w = wave_of(max(0, t))
    left = len(_RT["pool"]) + len(alive())
    if t < w["start"]:
        return w["n"], (w["start"] - t) / 60.0, left
    return w["n"], None, left


def clock_left():
    return max(0, M4_SIEGE_FRAMES - getattr(STATE, "m4_siege_t", 0)) / 60.0


def player_line_done():
    _radio("BIRIBEL: That's the last of them. ...It's on every set in the country.",
           color=BIRIBEL_SPEAKER, duration=380, mark="siege_done")
