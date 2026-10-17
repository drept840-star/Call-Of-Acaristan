
"""Slice 5b-5d: the Kill Order sweep director, overwatch pin, Volkov
extraction window and dock holdout.

Design source: docs/MISSION3_KILL_ORDER.md §3-§5. One module owns all
Phase-5 runtime combat logic so flow.py stays a thin stage ladder:

    update_kill_order()          - call once per logic tick from
                                   flow._update_kill_order_stage()
    coord_target(enemy, px, py)  - systems._m3_choose_enemy_target hook:
                                   fireteam formation targets while the
                                   sweep hunts your last-seen position
    draw_overwatch_laser(surf, cam_x, cam_y) - marksman telegraph

Beats:
    5b  staged fireteam insertions (shield point / breacher flanks /
        tech flush), stairwell breach-charge set-piece, sweep-line
        advance, 45s anti-turtle breacher charges on the closet doors
    5c  mezzanine marksman overwatch: lane pin with 0.9s laser telegraph
        (M2 kill-box discipline ported), assaultable nest with loot;
        Volkov 5:00 extraction window with radio thresholds and the
        mechanical-light bail branch (walk-off, Maru fallback)
    5d  dock holdout: 45s garage-door cycle, T+20s side-door breach
        charge, final wave, exfil -> broadcast cutscene flag

All spawns go through world._spawn_m3_guard(enemy_type=...) so role
stats, gear overlays and gear-aware corpses apply for free. All FX go
through effects.* helpers (particle-density and reduced-motion safe).
"""
import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream

import pygame

from core.config import (
    TILE_SIZE, C_BLOOD, C_VASILE, Particle, audio,
)
from core.state import STATE
from fx import effects

from missions.m3.meta import (
    C_BALACEANU, C_MARU, C_VOLKOV, STAGE_BROADCAST,
    STAGE_BROADCAST_TRANSITION,
)
from missions.m3.world import (
    _KO_BREACH_DOORS, _KO_MEZZ_TILE, _exfil_pos, _radio, _spawn_m3_guard,
    _set_objective, _solid_walls,
)
from entities.weapons import _wall_blocks_line
import game.world as _gw  # RPE6 Phase 5 (D4): mission data lives in components
from missions.m3.components import M3Door as _M3Door, M3Guard as _M3Guard


def _m3d(door):
    """Declared M3 data of a door (replaces the ad hoc ``door.m3_*`` attributes)."""
    return _gw.ensure(door, _M3Door)



def _m3g(e):
    """Declared M3 data of an enemy (replaces the ad hoc ``e.m3_*`` attributes)."""
    return _gw.ensure(e, _M3Guard)


# ── Director constants ───────────────────────────────────────────────
MAX_CONCURRENT = 9          # hard cap on live sweep enemies

# Difficulty/pressure pass (2026-09-19): role durability + fire cadence so
# trades carry weight. Shields soak, breachers punish close range, the
# marksman hurts; cooldowns tightened vs the base type_stats table.
ROLE_TUNING = {
    "guard":      {"hp": 110, "cooldown": 55, "damage": 15},
    "breacher":   {"hp": 160, "cooldown": 40, "damage": 18},
    "shield":     {"hp": 260, "cooldown": 60, "damage": 14},
    "technician": {"hp": 100, "cooldown": 70, "damage": 12},
    "marksman":   {"hp": 120, "cooldown": 80, "damage": 34},
}
CONTACT_STALE = 360         # 6s: last-seen goes stale
SWEEP_ADVANCE = 900         # 15s without contact: sweep line advances
TURTLE_LIMIT = 2100         # 35s in one zone: breacher charge a shortcut
WINDOW_TOTAL = 5 * 60 * 60  # Volkov's patience: 5:00
HOLDOUT_DOOR_FRAMES = 2700  # 45s garage-door cycle
HOLDOUT_BREACH_AT = 1200    # T+20s: side-door breach charge
OVERWATCH_TELEGRAPH = 54    # 0.9s laser sweep before shots
NEST_TILE = _KO_MEZZ_TILE
# The marksman's firing aperture: the mezzanine doorway. Lasers, LOS
# checks and muzzles use this point, not the room center - otherwise
# every shot crosses his own ring walls (or the pin never fires).
NEST_AIM_TILE = (25, 20)   # lobby tile just outside the mezz door:
# an origin inside the closed door's collision rect self-blocks LOS

_ZONE_CENTERS = {
    "stair": (6, 4), "west": (5, 17), "lobby": (19, 17),
    "east": (32, 17), "south": (19, 30), "dock": (19, 35),
}

# Lobby pin lanes (marksman overwatch, 5c): N-S and E-W sightlines.
_LANE_V = pygame.Rect(17 * TILE_SIZE, 9 * TILE_SIZE, 6 * TILE_SIZE, 18 * TILE_SIZE)
_LANE_H = pygame.Rect(9 * TILE_SIZE, 13 * TILE_SIZE, 20 * TILE_SIZE, 7 * TILE_SIZE)

# Wave schedule: (roles+insert tiles). Fires in order; capped by
# MAX_CONCURRENT (retries every 2s while over cap).
_WAVES = [
    {   # 0 - stairwell ambush: shield point + two guards
        "when": lambda s: s["t"] >= 120,
        "spawns": [("shield", (5, 10)), ("guard", (4, 12)), ("guard", (6, 12))],
    },
    {   # 1 - lobby approach: marksman to the nest + south-2 probes
        # (STATE commit: a player who rushed straight to the dock still gets
        # the mid-game waves - wave_idx must advance for the holdout wave.
        # Reads the PLAYER arrival flag, not st["committed"]: the holdout
        # itself stays locked until these waves are cleared, so keying on
        # the internal flag would deadlock the schedule.)
        "when": lambda s: (s["lobby_seen"] or s["waves"][0]["cleared"]
                           or getattr(STATE, "m3_sweep_committed", False)),
        "spawns": [("marksman", NEST_TILE), ("guard", (18, 30)), ("guard", (21, 30))],
    },
    {   # 2 - pincer: shield element west, breacher pair east
        "when": lambda s: s["t"] > s["waves"][1]["t"] + 900,
        "spawns": [("shield", (5, 25)), ("guard", (4, 24)), ("guard", (6, 24)),
                   ("breacher", (33, 25)), ("breacher", (34, 24))],
    },
    {   # 3 - tech flush + line guards leak from all three south routes
        "when": lambda s: _zone(s) in ("south", "dock")
                          or s["t"] > s["waves"][2]["t"] + 1800,
        "spawns": [("technician", (6, 30)), ("technician", (31, 30)),
                   ("guard", (17, 30)), ("guard", (22, 30)), ("guard", (33, 30))],
    },
    {   # 4 - holdout: everything left, dock-side + a down-dock overwatch
        # angle. The nest marksman used to insert at (32,25) - 11 tiles of
        # dark corridor off the van with no sightline down the dock, so he
        # contributed nothing. (33,29) keeps his lane but cuts the dead
        # ground in half.
        "when": lambda s: s["committed"] and s["holdout_t"] >= 60,
        "spawns": [("breacher", (30, 34)), ("breacher", (34, 34)),
                   ("technician", (28, 33)), ("marksman", (33, 29))],
    },
]

# Holdout assault stream (bug report 2026-09-19: the dock holdout had only
# wave 4's four bodies, so the 45s door cycle played out against nothing).
# Every 150 ticks a fresh pair pours in from a rotating gate until the
# door opens and you're out.
#
# Gate geometry (owner pass): the old gates sat at x=6/19/32, i.e. 14-27
# tiles from the van at (33,36), so the stream visibly crawled the length
# of the dock while the player held the door - the pressure read as
# background traffic. The exfil point is a known, idling, fixed target:
# gates now ring the van at 3-7 tiles so the ambush lands on you almost
# as soon as it inserts, from alternating sides. Tiles avoid the dock
# crate stack (35,33)/(36,33)/(36,34) and the van sprite itself.
_HOLDOUT_STREAM = [
    [("breacher", (36, 35)), ("guard", (28, 34))],
    [("guard", (35, 37)), ("technician", (27, 33))],
    [("breacher", (30, 37)), ("guard", (36, 36))],
    [("technician", (34, 33)), ("guard", (27, 36))],
]

_DOOR_TILES = {
    (13, 12): "closet_n", (13, 20): "closet_s",
    (31, 32): "dock_side", (32, 32): "dock_side",
}


# ── helpers ──────────────────────────────────────────────────────────
def _zone(s=None):
    """Player zone via flow's partition (imported lazily: flow->sweep)."""
    if STATE.player is None:
        return "stair"
    from missions.m3.flow import _ko_zone_of
    return _ko_zone_of(STATE.player.rect.centerx, STATE.player.rect.centery)


def _wpos(tile):
    return (tile[0] * TILE_SIZE + TILE_SIZE // 2,
            tile[1] * TILE_SIZE + TILE_SIZE // 2)


def _seed():
    """Per-phase director state (idempotent)."""
    if getattr(STATE, "m3_sweep_seeded", False):
        return STATE.m3_sweep
    st = {
        "t": 0, "wave_idx": 0, "contact": 9999, "zone_t": 0, "zone": None,
        "lobby_seen": False, "committed": False, "bailed": False,
        "holdout_t": 0, "breached": set(), "stair_charge_t": -1,
        "overwatch": {"uid": None, "telegraph": 0, "cool": 0, "pending": 0},
        "waves": [{"t": -1, "cleared": False, "uids": []} for _ in _WAVES],
    }
    STATE.m3_sweep = st
    STATE.m3_sweep_seeded = True
    return st


def _mark(key):
    return key in STATE.mission3_events


def _once(key):
    if key in STATE.mission3_events:
        return False
    STATE.mission3_events.add(key)
    return True


def _team_members(team):
    return [e for e in STATE.enemies
            if _m3g(e).sweep_team == team]


# ── breach charges ───────────────────────────────────────────────────
def breach_door(door, tag="BREACH!"):
    """Blow a sealed door: rubble-open + full set-piece FX."""
    door.locked = False
    door.target_open = True
    door.manual_timer = 40
    x, y = door.rect.centerx, door.rect.centery
    effects.shake(18)
    effects.burst(x, y, (120, 110, 90), 26, speed_mul=1.5, life_min=14, life_max=40)
    effects.burst(x, y, (70, 65, 58), 14, speed_mul=0.7, life_min=20, life_max=55)
    try:
        audio.play("breach", volume=0.55)
        audio.play("door_rattle", volume=0.35)
    except Exception:
        pass
    if STATE.player is not None:
        STATE.floating_texts.append([x, y - 26, tag, (230, 120, 60), 80])


def _nearest_turtle_door(px, py):
    best, bd = None, 1e9
    for door in STATE.doors:
        if not _m3d(door).ko_breach or not door.locked:
            continue
        key = (door.rect.centerx // TILE_SIZE, door.rect.centery // TILE_SIZE)
        if _DOOR_TILES.get(key) == "dock_side":
            continue                      # holdout owns the side door
        d = math.hypot(door.rect.centerx - px, door.rect.centery - py)
        if d < bd:
            best, bd = door, d
    return best


# ── beat gates (rush fix 2026-09-27) ─────────────────────────────────
# The lobby->south row (world._KO_BEAT_GATES, wave 0 = stair ambush) and
# the south->dock row (wave 1 = lobby marksman + probes) are sealed at
# world build and blow open as their authored beat clears - a
# stairwell->van sprint must cross beats 1-2, not skip them (it used to
# hit an empty dock and park on "HOLDOUT LOCKED" while the sweep hunted
# ghosts). The door cycle stays timer-driven and the existing
# commit/boarding kill-gates stay as the backstop for waves 2-3; the
# gates only make the beats spatially unavoidable.
def _beat_gate_doors(st, wave):
    return [d for d in STATE.doors
            if _m3d(d).ko_beat_gate == wave and d.locked]


def _beat_gate_ready(st, wave):
    """Wave cleared AND none of its members still queued to spawn.

    _update_waves' cleared bookkeeping marks a wave cleared once every
    SPAWNED uid is dead, but the 24-tick trickle insert can still have
    members queued while the concurrent cap holds - the gate must not
    open while part of the wave is still on its way in.
    """
    rec = st["waves"][wave] if wave < len(st["waves"]) else None
    if rec is None or not rec.get("cleared", False):
        return False
    return not any(it[3] == wave for it in st.get("pending", []))


def _beat_gate_remaining(st, wave):
    """Live + queued bodies of one wave (for the gate prompt count)."""
    if st is None:
        return 0
    rec = st["waves"][wave] if wave < len(st["waves"]) else None
    if rec is None:
        return 0
    live = sum(1 for e in getattr(STATE, "enemies", [])
               if _m3g(e).sweep_team == wave and e.hp > 0)
    pending = sum(1 for it in st.get("pending", []) if it[3] == wave)
    if live + pending == 0 and rec.get("t", -1) < 0:
        try:
            return len(_WAVES[wave]["spawns"])
        except Exception:
            return 0
    return live + pending


def _update_beat_gates(st):
    for wave in (0, 1):
        if not _beat_gate_ready(st, wave):
            continue
        key = f"ko_beat_gate_{wave}"
        if not _once(key):
            continue
        for door in _beat_gate_doors(st, wave):
            breach_door(door, "SOUTH GATES BLOWN!" if wave == 0
                        else "DOCK GATES BLOWN!")
        if wave == 0:
            _radio("VOLKOV: Shield point is down - the south is open. "
                   "Push, friend.", color=C_VOLKOV, duration=300, mark=key)
        elif st["bailed"]:
            _radio("MARU: Dock gates open. No van waiting - move.",
                   color=C_MARU, duration=300, mark=key)
        else:
            _radio("VOLKOV: Their marksman is gone. Dock gates are open - "
                   "I'll cycle the door when you get there.",
                   color=C_VOLKOV, duration=300, mark=key)


# ── gate anti-soft-lock (2026-09-27) ─────────────────────────────────
# A beat gate may never deadlock: a member of a gated wave wedged on
# geometry (A* no-path + overlap wedge) can't be killed, so the gate
# stays sealed forever. After ~10s without real movement the member
# re-inserts on a fresh bearing 3-5 tiles from the player - same fight,
# but one the player can actually reach. The pinned nest marksman is
# excluded: his "stillness" is the overwatch beat, not a jam.
STUCK_REINSERT_FRAMES = 600


def _update_stuck(st):
    if st.get("committed") or STATE.player is None:
        return
    stuck = st.setdefault("stuck", {})
    pin_uid = st["overwatch"].get("uid")
    live_uids = {e.uid for e in STATE.enemies if e.hp > 0}
    for uid in [u for u in stuck if u not in live_uids]:
        stuck.pop(uid, None)
    for e in STATE.enemies:
        team = _m3g(e).sweep_team
        if team is None or team >= 4 or e.hp <= 0 or e.uid == pin_uid:
            continue
        x, y = e.rect.centerx, e.rect.centery
        rec = stuck.get(e.uid)
        if rec is None or math.hypot(x - rec[0], y - rec[1]) > 24:
            stuck[e.uid] = (x, y, st["t"])
            continue
        if st["t"] - rec[2] < STUCK_REINSERT_FRAMES:
            continue
        px, py = STATE.player.rect.centerx, STATE.player.rect.centery
        ang = _rng_legacy.uniform(0.0, 2.0 * math.pi)
        tile = _free_spawn_tile(
            (int((px + math.cos(ang) * TILE_SIZE * 4) // TILE_SIZE),
             int((py + math.sin(ang) * TILE_SIZE * 4) // TILE_SIZE)))
        if tile is None:
            stuck[e.uid] = (x, y, st["t"])     # neighbourhood packed: retry
            continue
        stuck.pop(e.uid, None)
        e.rect.center = _wpos(tile)
        e.path = []
        e.state = "CHASE"
        e.alerted = True
        e.last_seen_pos = (px, py)
        STATE.floating_texts.append([
            e.rect.centerx, e.rect.centery - 26, "SWEEP RE-FLANKS",
            (180, 140, 90), 60])


# ── wave spawning ────────────────────────────────────────────────────
def _spawn_sweep_member(st, role, tile, idx):
    """One insertion: tuned stats, alerted, seeded with your last pos."""
    e = _spawn_m3_guard(
        tile[0], tile[1],
        enemy_type=role,
        label=f"ko_sweep_{idx}_{role}",
        facing=None,
    )
    tun = ROLE_TUNING.get(role, {})
    e.hp = tun.get("hp", 90)
    _m3g(e).fire_cooldown = tun.get("cooldown", 38)
    _m3g(e).damage = tun.get("damage", 12)
    _m3g(e).sweep_team = idx
    _m3g(e).sweep_role = role
    e.alerted = True
    e.state = "CHASE"
    if STATE.player is not None:
        e.last_seen_pos = STATE.player.rect.center   # they hunt YOU on entry
    if idx < len(st["waves"]):
        st["waves"][idx]["uids"].append(e.uid)
    else:
        st.setdefault("extra_uids", []).append(e.uid)   # holdout stream etc.
    if role == "marksman" and idx == 1:
        st["overwatch"]["uid"] = e.uid
    return e


def _fire_wave(st, idx):
    """Queue the wave: members trickle in on a 24-tick cadence (formation
    entry, not a teleport crowd) and respect the concurrent cap."""
    wave = _WAVES[idx]
    rec = st["waves"][idx]
    for i, (role, tile) in enumerate(wave["spawns"]):
        st.setdefault("pending", []).append([role, tile, st["t"] + i * 24, idx])
    rec["t"] = st["t"]
    st["wave_idx"] = idx + 1
    if idx == 0:
        st["stair_charge_t"] = 20         # charge under the player's feet
    if idx == 3:
        # Tech flush route: blow the closet shortcuts open so their loot
        # becomes reachable even if the player never turtles (playability
        # audit finding 2026-09-19).
        for door in STATE.doors:
            key = (door.rect.centerx // TILE_SIZE,
                   door.rect.centery // TILE_SIZE)
            if _DOOR_TILES.get(key, "").startswith("closet") and door.locked:
                breach_door(door, "FLUSH BREACH!")
                st["breached"].add(_DOOR_TILES[key])


def _update_pending(st):
    for item in st.get("pending", [])[:]:
        role, tile, at, idx = item
        if st["t"] < at or len(STATE.enemies) >= MAX_CONCURRENT:
            continue
        st["pending"].remove(item)
        _spawn_sweep_member(st, role, tile, idx)


def _update_waves(st):
    if st["wave_idx"] >= len(_WAVES):
        return
    idx = st["wave_idx"]
    rec = st["waves"][idx]
    if rec["t"] < 0 and _WAVES[idx]["when"](st):
        # Withhold the whole wave if it would break the concurrent cap -
        # waves insert 3-5 bodies at once, so the check must account for
        # the incoming size, not just the current count.
        if len(STATE.enemies) + len(_WAVES[idx]["spawns"]) > MAX_CONCURRENT:
            return                        # retry on a later tick
        _fire_wave(st, idx)
    # cleared-bookkeeping (drives wave1 fallback trigger)
    for i, w in enumerate(st["waves"]):
        if w["t"] >= 0 and not w["cleared"]:
            if w["uids"] and all(
                    uid not in {e.uid for e in STATE.enemies} for uid in w["uids"]):
                w["cleared"] = True


# ── coordination hook (systems._m3_choose_enemy_target) ─────────────
def _overwatch_engaged(st, px, py):
    """Pin conditions minus LOS: used to walk the marksman to the door."""
    if _zone() != "lobby":
        return False
    if not (_LANE_V.collidepoint(px, py) or _LANE_H.collidepoint(px, py)):
        return False
    if _player_covered(px, py):
        return False
    return True


def coord_target(enemy, px, py, solid_walls):
    """Formation targets while sweeping; None = default AI owns it.

    The caller (systems._m3_choose_enemy_target) only reaches us when the
    member has NO live strict-LOS sightline on the player - so any member
    who can actually see them is left entirely to the vanilla combat AI.
    Everyone else keeps advancing as a fireteam: the leader pushes the
    last-seen position / zone center, the rest hold formation offsets off
    his shoulder (shield point leads, breachers flank, tech lag behind).
    """
    team = _m3g(enemy).sweep_team
    if team is None or getattr(STATE, "mission3_stage", None) != "kill_order":
        return None
    # The mezzanine marksman is pinned by _update_overwatch: normal sweep
    # movement would stage-whisper him out of the nest (tug-of-war with the
    # pin step) and read as the old "wandering sniper".
    st_ = getattr(STATE, "m3_sweep", None)
    pinned_uid = (st_["overwatch"].get("uid") if st_ is not None else None)
    if (pinned_uid is not None
            and pinned_uid == getattr(enemy, "uid", None)
            and not st_.get("committed")):
        return None
    st = getattr(STATE, "m3_sweep", None)
    if st is None:
        return None
    if st.get("committed") or _zone() == "dock":
        # Dock holdout (owner report: "the AI doesn't know where I am").
        # The assault knows you're holding the van: every member converges
        # on the exfil point on its OWN bearing (golden-angle ring at
        # 1.6-3.2 tiles), so a jammed leader can no longer park the whole
        # fireteam mid-dock, and the player is attacked from several sides
        # at once instead of one conga line.
        #
        # Also pre-commit: standing on the van is not "somewhere in the
        # dock" - the van is idling at a fixed, known point and the dock
        # zone center is 14 tiles west of it, so a zone-hunting squad
        # camped mid-dock and left the player untouchable. The extraction
        # point is the one place in the phase they know exactly.
        gx, gy = _exfil_pos()
        ang = (enemy.uid * 2.39996) % (2 * math.pi)
        r = TILE_SIZE * (1.6 + (enemy.uid % 3) * 0.8)
        return ("sweep", gx + math.cos(ang) * r, gy + math.sin(ang) * r, False)
    if st["contact"] <= CONTACT_STALE and STATE.m3_sweep_last_seen:
        gx, gy = STATE.m3_sweep_last_seen
    else:
        gx, gy = _wpos(_ZONE_CENTERS[_zone()])   # sweep line: hunt the zone
    # Leader election must ignore the pinned nest marksman: he holds
    # station while his team formed up on him inside the mezzanine, so
    # the whole element stood still in the nest doorway.
    members = [e for e in _team_members(team)
               if not (pinned_uid is not None
                       and not st.get("committed")
                       and e.uid == pinned_uid)]
    if not members:
        return None
    leader = min(members, key=lambda e: e.uid)
    if enemy.uid == leader.uid:
        return ("sweep", gx, gy, False)
    lx, ly = leader.rect.centerx, leader.rect.centery
    ang = math.atan2(gy - ly, gx - lx)
    d = (math.cos(ang), math.sin(ang))
    p = (-d[1], d[0])
    role = _m3g(enemy).sweep_role
    side = 1.0 if (enemy.uid % 2) else -1.0
    if role == "shield":
        ox, oy = d[0] * 26, d[1] * 26            # point element leads
    elif role == "breacher":
        ox, oy = p[0] * 34 * side - d[0] * 14, p[1] * 34 * side - d[1] * 14
    elif role == "technician":
        ox, oy = -d[0] * 18 + p[0] * 10 * side, -d[1] * 18 + p[1] * 10 * side
    else:
        ox, oy = p[0] * 20 * side - d[0] * 8, p[1] * 20 * side - d[1] * 8
    return ("sweep", lx + ox, ly + oy, False)


def _free_spawn_tile(tile):
    """De-stack: holdout stream pairs land every 2.5s on the same few
    tiles, and two bodies on one tile wedge each other in the overlap
    resolver until the jam breaker fires - or forever. Pick the first
    walkable, unoccupied tile near the requested one (self out to
    radius 2); None if the whole neighbourhood is packed."""
    from entities.enemy_ai import _build_walk_grid
    grid, cols, rows = _build_walk_grid(_solid_walls())
    cx, cy = tile
    for r in (0, 1, 2):
        for dc in range(-r, r + 1):
            for dr in range(-r, r + 1):
                if max(abs(dc), abs(dr)) != r:
                    continue
                nc, nr = cx + dc, cy + dr
                if not (0 <= nc < cols and 0 <= nr < rows) or not grid[nr][nc]:
                    continue
                wx, wy = _wpos((nc, nr))
                if any(e.hp > 0 and math.hypot(e.rect.centerx - wx,
                                               e.rect.centery - wy) < 44
                       for e in STATE.enemies):
                    continue
                return (nc, nr)
    return None


# ── overwatch pin (5c) ───────────────────────────────────────────────
def _player_covered(px, py):
    pr = pygame.Rect(int(px) - 10, int(py) - 10, 20, 20)
    for r in STATE.mission3_barriers:
        if r.inflate(10, 10).colliderect(pr):
            return True
    for r in STATE.walls:
        if r.inflate(2, 2).colliderect(pr) and not r.collidepoint(px, py):
            # adjacent wall between the nest lane and the player reads as cover
            if abs(r.centerx - px) < 46 or abs(r.centery - py) < 46:
                return True
    return False


def _update_overwatch(st):
    ow = st["overwatch"]
    uid = ow["uid"]
    marksman = next((e for e in STATE.enemies if e.uid == uid), None)
    if uid is not None and marksman is None and _once("ko_nest_down"):
        # Nest cleared: loot where he actually fell (door or room).
        lx, ly = ow.get("last", _wpos(NEST_TILE))
        STATE.pickups.append([lx - 10, ly, "mag"])
        STATE.pickups.append([lx + 10, ly, "bandage"])
        _radio("VASILE: Nest is dark. Their eyes are out - move while it lasts.",
               color=C_VASILE, duration=260, mark="ko_nest_down")
        ow["telegraph"] = 0
        return
    if marksman is None:
        return
    if st.get("committed"):
        # Holdout: the nest is done pinning - release the marksman to the
        # dock assault (he becomes a normal sweep member again).
        return
    # Full ownership: the marksman never chases. Both the sweep formation
    # AND Enemy.update are bypassed for him (systems feeds him dummy coords)
    # - otherwise his CHASE state fights _update_overwatch's pin step and he
    # shambles/walks in the nest. Force a scanning hold facing the doorway.
    marksman.state = "SEARCH"
    marksman.last_seen_pos = _wpos(NEST_AIM_TILE)
    marksman.path = []
    ow["last"] = (marksman.rect.centerx, marksman.rect.centery)
    if STATE.player is None or STATE.player_dead:
        ow["telegraph"] = 0
        return
    px, py = STATE.player.rect.centerx, STATE.player.rect.centery
    rx, ry = _wpos(NEST_TILE)
    if math.hypot(px - rx, py - ry) < TILE_SIZE * 2.5:
        ow["telegraph"] = 0               # player is assaulting the nest
        ow["cool"] = max(ow["cool"], 60)
        return
    # Honest pin, moved here because Enemy.update recomputes its own vision
    # against whatever coords it is handed: step him physically to the
    # doorway while engaged, withdraw into the room when you break it.
    engaged = _overwatch_engaged(st, px, py)
    if engaged and not st.get("sniper_warned", False):
        st["sniper_warned"] = True
        _radio("VASILE: Marksman up on that mezzanine - his red line means "
               "they have the lane zeroed. Keep your head down.",
               color=C_VASILE, duration=280, mark="ko_sniper_warn")
    pinx, piny = _wpos(NEST_AIM_TILE) if engaged else _wpos(NEST_TILE)
    mx, my = marksman.rect.center
    dd = math.hypot(pinx - mx, piny - my)
    if dd > 6:
        stepv = min(2.0, dd)
        marksman.rect.center = (mx + (pinx - mx) / dd * stepv,
                                my + (piny - my) / dd * stepv)
    nx, ny = marksman.rect.centerx, marksman.rect.centery
    if engaged:
        marksman.angle = math.atan2(py - ny, px - nx)
    if _zone() != "lobby":
        ow["telegraph"] = 0
        return
    in_lane = (_LANE_V.collidepoint(px, py) or _LANE_H.collidepoint(px, py))
    if ow["cool"] > 0:
        ow["cool"] -= 1
        ow["telegraph"] = 0
        return
    if not in_lane or _player_covered(px, py):
        ow["telegraph"] = 0
        return
    # Hard line-of-sight gate: the nest never paints or shoots through
    # walls/pillars (bug report 2026-09-19: 'sniper targets you through
    # walls'). Lasers and rounds only exist on clear sightlines.
    if _wall_blocks_line(nx, ny, px, py, _solid_walls()):
        ow["telegraph"] = 0
        return
    ow["telegraph"] += 1
    if ow["telegraph"] == 1:
        # Telegraph onset cue: audible tick + world-space warning so the
        # pin's job ("leave the lane or break LOS in 0.9s") is unmistakable.
        try:
            audio.play("rifle_handle", volume=0.45)
        except Exception:
            pass
        STATE.floating_texts.append([
            px, py - 34, "MARKSMAN LOCK - BREAK LINE!", (255, 90, 60), 70])
    if ow["telegraph"] >= OVERWATCH_TELEGRAPH:
        ow["telegraph"] = 0
        ow["cool"] = 110 + _rng_legacy.randint(0, 60)
        for i in range(2):
            a = math.atan2(py - ny, px - nx) + _rng_legacy.uniform(-0.05, 0.05)
            mx, my = nx + math.cos(a) * 20, ny + math.sin(a) * 20
            STATE.bullets.append({
                "x": mx, "y": my, "prev_x": mx, "prev_y": my,
                "dx": math.cos(a) * 22, "dy": math.sin(a) * 22,
                "life": 26, "owner": "enemy", "damage": 22,
            })
        effects.shake(5)
        effects.burst(px + _rng_legacy.randint(-14, 14), py + _rng_legacy.randint(-14, 14),
                      (150, 145, 130), 8, speed_mul=0.8, life_min=10, life_max=26)
        try:
            audio.play("sniper_crack", volume=0.35)
            effects.play_impact("concrete_impact", (px, py), base_volume=0.30)
        except Exception:
            pass


def draw_overwatch_laser(surface, cam_x, cam_y):
    """0.9s red sweep telegraph before the nest shoots (M2 discipline).

    While the player is in a lobby lane with a clean sightline the beam is
    drawn faintly even when not telegraphing, so crossing the kill box is
    legible BEFORE the first crack goes down. The nest itself carries a
    pulsing scope glint so the threat has a visible source, and the
    telegraph thickens + rings the target as the shot approaches.
    """
    import time as _time
    st = getattr(STATE, "m3_sweep", None)
    if not st or STATE.player is None:
        return
    tel = st["overwatch"]["telegraph"]
    mk = next((e for e in STATE.enemies if e.uid == st["overwatch"]["uid"]), None)
    if mk is None:
        return
    nx, ny = mk.rect.centerx, mk.rect.centery
    px, py = STATE.player.rect.centerx, STATE.player.rect.centery
    # Scope glint at the nest: always drawn while the marksman lives, so the
    # player can trace the beam back to a source and assault it.
    glint_pulse = 0.5 + 0.5 * math.sin(_time.time() * 6.0)
    glint_a = int(90 + 90 * glint_pulse)
    lay = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
    pygame.draw.circle(lay, (255, 120, 90, glint_a),
                       (int(nx - cam_x), int(ny - cam_y)), 5)
    pygame.draw.circle(lay, (255, 220, 200, glint_a),
                       (int(nx - cam_x), int(ny - cam_y)), 2)
    if tel <= 0:
        if _zone() != "lobby":
            surface.blit(lay, (0, 0))
            return
        if not (_LANE_V.collidepoint(px, py) or _LANE_H.collidepoint(px, py)):
            surface.blit(lay, (0, 0))
            return
        if _player_covered(px, py):
            surface.blit(lay, (0, 0))
            return
        if _wall_blocks_line(nx, ny, px, py, _solid_walls()):
            surface.blit(lay, (0, 0))
            return
        alpha = 78                          # idle search beam (was 22: invisible)
        width = 2
    else:
        alpha = min(235, 60 + tel * 4)
        width = 2 + int(tel / 18)           # 2px -> 4px as the shot nears
    pygame.draw.line(lay, (255, 60, 50, alpha),
                     (int(nx - cam_x), int(ny - cam_y)),
                     (int(px - cam_x), int(py - cam_y)), width)
    pygame.draw.line(lay, (255, 170, 130, min(255, alpha + 20)),
                     (int(nx - cam_x), int(ny - cam_y)),
                     (int(px - cam_x), int(py - cam_y)), 1)
    if tel > 0:
        pygame.draw.circle(lay, (255, 60, 50, alpha), (int(px - cam_x), int(py - cam_y)), 6, 2)
        # Closing ring: shrinks onto the player as telegraph fills.
        frac = tel / max(1.0, float(OVERWATCH_TELEGRAPH))
        pygame.draw.circle(lay, (255, 200, 160, alpha),
                           (int(px - cam_x), int(py - cam_y)),
                           max(4, int(22 - 16 * frac)), 1)
    surface.blit(lay, (0, 0))
    # Top-center status chip: IN LANE / IN COVER / FIRING, mirroring the M2
    # sniper HUD so the pin's rules are explicit, not inferred.
    try:
        from core.config import font_terminal as _ft, font_terminal_small as _fts
        in_lane = (_LANE_V.collidepoint(px, py) or _LANE_H.collidepoint(px, py))
        covered = _player_covered(px, py)
        if tel > 0:
            label, col = "MARKSMAN FIRING - MOVE!", (255, 70, 45)
        elif in_lane and not covered:
            label, col = "MARKSMAN PIN - USE PILLARS / ASSAULT NEST", (255, 170, 90)
        elif in_lane and covered:
            label, col = "IN COVER - HOLD / PUSH NEST", (110, 220, 150)
        else:
            label, col = None, None
        if label is not None and _zone() == "lobby":
            warn = _ft.render(label, True, col)
            panel = pygame.Surface((warn.get_width() + 24, warn.get_height() + 10),
                                   pygame.SRCALPHA)
            panel.fill((0, 0, 0, 175))
            pygame.draw.rect(panel, col, panel.get_rect(), 1)
            surface.blit(panel, (surface.get_width() // 2 - panel.get_width() // 2, 84))
            surface.blit(warn, (surface.get_width() // 2 - warn.get_width() // 2, 89))
    except Exception:
        pass


# ── Volkov window + bail (5c) ────────────────────────────────────────
def _update_window(st):
    if not st.get("window_armed"):
        st["window_armed"] = True
        STATE.m3_sweep_window_active = True      # arm once, first tick post-5a
    if st["committed"] or st["bailed"]:
        return
    left = STATE.m3_sweep_window_frames
    left -= 1
    STATE.m3_sweep_window_frames = left
    secs = left // 60
    for threshold, key, line, col in (
        (210, "ko_win_210",
         "VOLKOV: Window's closing. My engine idles for no one - not even you.",
         C_VOLKOV),
        (120, "ko_win_120",
         "VASILE: Volkov's patience is a resource. Spend it wisely.", C_VASILE),
        (45, "ko_win_45",
         "VOLKOV: Forty-five seconds. Then I'm a memory.", C_VOLKOV),
    ):
        if secs <= threshold and _once(key):
            _radio(line, color=col, duration=260, mark=key)
    if left <= 0:
        st["bailed"] = True
        STATE.m3_volkov_bailed = True
        STATE.m3_sweep_window_active = False
        STATE.m3_volkov_bail_timer = 180         # walk-off, then despawn
        _radio("VOLKOV: ...The van's gone. Dock crane, roof line - you're "
               "resourceful. Sorry, friend.",
               color=C_VOLKOV, duration=320, mark="ko_volkov_bail")


# ── holdout + exfil (5d) ─────────────────────────────────────────────
def _mid_wave_blockers(st):
    """Live pre-holdout sweep enemies + unfired/uncleared mid waves.

    Waves 0-3 are the staged stair/lobby/pincer/flush fights; wave 4 is the
    holdout itself. A sprint straight to the van must not skip them, so the
    holdout stays locked until they are actually dead (mirrors the
    comms/archives "CLEAR HOSTILES FIRST" gates). Returns (live, open):
    live mid-wave bodies (including trickle spawns still queued) and the
    number of mid waves not yet fired+cleared.
    """
    want = min(4, len(_WAVES))
    if want <= 0:
        return (0, 0)
    live = sum(1 for e in STATE.enemies
               if getattr(e, "hp", 0) > 0
               and _m3g(e).sweep_team is not None
               and 0 <= _m3g(e).sweep_team < want)
    live += sum(1 for it in st.get("pending", []) if it[3] < want)
    recs = st.get("waves", [])
    open_waves = 0
    for i in range(min(want, len(recs))):
        r = recs[i]
        if r["t"] < 0 or not r["cleared"]:
            open_waves += 1
    return (live, open_waves)


def _mid_waves_cleared(st):
    live, open_waves = _mid_wave_blockers(st)
    return live == 0 and open_waves == 0


# Exfil gating (rush fix): sprinting stairwell -> van used to skip waves
# 0-3 entirely - the door cycled on a pure timer while the sweep hunted
# an empty lobby. Boarding now requires the pre-holdout roster to be
# cleared: every required wave fired AND none of its members still
# live/pending. The door cycle itself stays timer-driven (no soft-lock);
# only the final boarding is gated, mirroring the Archives
# "CLEAR HOSTILES FIRST" idiom. The holdout stream (team 4) is excluded:
# it spawns forever until you leave, so it can never be "cleared".
_PRE_HOLDOUT_TEAMS = (0, 1, 2, 3)


def _pre_holdout_ids(st):
    waves = st.get("waves", []) if isinstance(st, dict) else []
    return [i for i in _PRE_HOLDOUT_TEAMS if i < len(waves)]


def _pre_holdout_remaining(st):
    """(uncleared_wave_ids, live, pending) for the pre-holdout roster."""
    ids = _pre_holdout_ids(st)
    if not ids:
        return [], 0, 0
    req = set(ids)
    waves = st.get("waves", [])
    uncleared = [i for i in ids if not waves[i].get("cleared", False)]
    live = sum(1 for e in getattr(STATE, "enemies", [])
               if _m3g(e).sweep_team in req)
    pending = sum(1 for item in st.get("pending", []) if item[3] in req)
    return uncleared, live, pending


def _pre_holdout_blocker_count(st):
    """Sweep hostiles the player must still kill before the van leaves."""
    uncleared, live, pending = _pre_holdout_remaining(st)
    if not uncleared:
        return 0
    total = live + pending
    for i in uncleared:
        rec = st["waves"][i]
        if rec.get("t", -1) < 0 and not rec.get("uids"):
            try:
                total += len(_WAVES[i]["spawns"])
            except Exception:
                total += 1
    return total


def _update_holdout(st):
    committed = getattr(STATE, "m3_sweep_committed", False)
    if committed and not st["committed"]:
        if not _mid_waves_cleared(st):
            live, open_waves = _mid_wave_blockers(st)
            if live > 0:
                _set_objective(f"Holdout locked - clear {live} sweep team(s) first.")
            else:
                _set_objective("Holdout locked - sweep teams inbound.")
            gate_t = st.get("holdout_gate_msg", 0) - 1
            st["holdout_gate_msg"] = 180 if gate_t <= 0 else gate_t
            if gate_t <= 0 and STATE.player is not None:
                px, py = STATE.player.rect.centerx, STATE.player.rect.centery
                STATE.floating_texts.append([
                    px, py - 40, "HOLDOUT LOCKED - CLEAR SWEEP TEAMS",
                    (220, 150, 90), 110])
            return
        st["committed"] = True
        STATE.m3_sweep_window_active = False
        st["holdout_t"] = 1
        if not st["bailed"]:
            _radio("VOLKOV: Behind me. Door cycles in forty-five. I'll keep "
                   "them off it.", color=C_VOLKOV, duration=300, mark="ko_commit")
        else:
            _radio("MARU: No van. The crane cage lifts to the roof line - "
                   "hold the dock until it clears.",
                   color=C_MARU, duration=300, mark="ko_commit")
    if not st["committed"]:
        return
    st["holdout_t"] += 1
    # Holdout cap: MAX_CONCURRENT is usually already full of wave members
    # stranded up in the stairwell/lobby - if the dock used the same cap,
    # the ambush stream could never spawn (zero-pressure holdout). Allow a
    # small overflow while committed.
    # Holdout cap: MAX_CONCURRENT is usually already full of wave members
    # stranded up in the stairwell/lobby - if the dock used the same cap,
    # the ambush stream could never spawn (zero-pressure holdout). Allow a
    # small overflow while committed. The overflow is +2, not +3: with the
    # gates now ringing the van, twelve bodies inside 3 tiles was a wall
    # rather than a fight (AFK player died in 29s). Eleven still means the
    # van is never safe.
    holdout_cap = MAX_CONCURRENT + 2
    # 200-tick cadence (was 150): same pair-every-N rhythm, but the tighter
    # gates mean each insertion actually lands on the player now.
    if st["holdout_t"] % 200 == 0 and len(STATE.enemies) < holdout_cap:
        seq = st.get("holdout_seq", 0)
        st["holdout_seq"] = seq + 1
        side_open = any(
            not d.locked for d in STATE.doors
            if (d.rect.centerx // TILE_SIZE, d.rect.centery // TILE_SIZE)
            in ((31, 32), (32, 32)))
        spawned = 0
        for role, tile in _HOLDOUT_STREAM[seq % len(_HOLDOUT_STREAM)]:
            if len(STATE.enemies) >= holdout_cap:
                break
            if tile == (32, 33) and not side_open:
                tile = (32, 30)          # side door still sealed: use south 3
            tile = _free_spawn_tile(tile)   # never drop a body on a buddy
            if tile is None:
                continue
            _spawn_sweep_member(st, role, tile, 4)
            spawned += 1
        if spawned and STATE.player is not None:
            # The ambush is on the van and knows it: hand the whole assault
            # your live position instead of letting it re-derive a stale fix
            # from a zone center 14 tiles west. Without this the stream
            # arrived one at a time and the rest of the squad kept hunting
            # the dock middle.
            STATE.m3_sweep_last_seen = STATE.player.rect.center
            st["contact"] = 0
    if st["holdout_t"] == HOLDOUT_BREACH_AT:
        for door in STATE.doors:
            key = (door.rect.centerx // TILE_SIZE,
                   door.rect.centery // TILE_SIZE)
            if _DOOR_TILES.get(key) == "dock_side" and door.locked:
                breach_door(door, "SIDE DOOR BLOWN!")
                st["breached"].add("dock_side")
    cycle = min(HOLDOUT_DOOR_FRAMES, getattr(STATE, "m3_exfil_door_cycle", 0) + 1)
    STATE.m3_exfil_door_cycle = cycle
    blockers = _pre_holdout_blocker_count(st)
    if cycle >= HOLDOUT_DOOR_FRAMES:
        if blockers > 0:
            _set_objective(
                f"DOOR OPEN - clear {blockers} sweep hostile(s), then exfil!")
        else:
            _set_objective("DOOR OPEN - EXFIL NOW!")
    else:
        secs = max(0, (HOLDOUT_DOOR_FRAMES - cycle)) // 60
        if blockers > 0:
            _set_objective(
                f"Hold the dock - door cycles in 0:{secs:02d} - "
                f"clear {blockers} sweep hostile(s).")
        elif st["bailed"]:
            _set_objective(f"Cage lifting in 0:{secs:02d} - hold the dock, alone.")
        else:
            _set_objective(f"Hold the dock - door cycles in 0:{secs:02d}.")
    if cycle >= HOLDOUT_DOOR_FRAMES and STATE.player is not None:
        ex, ey = _exfil_pos()
        px, py = STATE.player.rect.centerx, STATE.player.rect.centery
        if math.hypot(px - ex, py - ey) < TILE_SIZE * 1.5:
            if blockers > 0:
                if _once("ko_exfil_held"):
                    _radio("VOLKOV: Van's held - sweep teams still on you. "
                           "Clear them, then we roll!",
                           color=C_VOLKOV, duration=300, mark="ko_exfil_held")
                last = st.get("exfil_block_msg_t", -9999)
                if st["holdout_t"] - last > 180:
                    st["exfil_block_msg_t"] = st["holdout_t"]
                    STATE.floating_texts.append([
                        px, py - 40,
                        f"CLEAR SWEEP FIRST - {blockers} LEFT",
                        (230, 140, 80), 120])
                    _set_objective(
                        f"DOOR OPEN - clear {blockers} sweep hostile(s), "
                        "then exfil!")
                return
            _exfil(st)


def _exfil(st):
    if not _once("ko_exfil_done"):
        return
    STATE.m3_exfil_door_cycle = HOLDOUT_DOOR_FRAMES
    from missions.m3.world import _stop_m3_alarm
    _stop_m3_alarm()
    # Slice 5 -> Slice 6 handoff through the broadcast transition holding
    # stage (mirrors the Archives -> KO prebuild pattern): the world stays put
    # while the transition cutscene plays, then flow._update_stage lands the
    # real STAGE_BROADCAST via _start_broadcast_phase().
    STATE.mission3_stage = STAGE_BROADCAST_TRANSITION
    STATE.mission_phase = "m3_broadcast_transition"
    if st["bailed"]:
        _radio("MARU: Roof line confirmed. You're a ghost again, Biribel. "
               "Now - the broadcast.", color=C_MARU, duration=320, mark="ko_exfil")
    else:
        _radio("VOLKOV: File's aboard. I drive, you watch the mirrors. DRIVE!",
               color=C_VOLKOV, duration=240, mark="ko_exfil")
    STATE.request_broadcast_transition_cutscene = True
    if STATE.player is not None:
        STATE.floating_texts.append([
            STATE.player.rect.centerx, STATE.player.rect.centery - 40,
            "EXFIL SECURED", (200, 230, 160), 140])


# ── main per-tick entry ──────────────────────────────────────────────
def update_kill_order():
    """Phase 5 runtime: director + pin + window + holdout."""
    if STATE.player is None:
        return
    st = _seed()
    st["t"] += 1
    px, py = STATE.player.rect.centerx, STATE.player.rect.centery

    # Contact / last-seen bookkeeping.
    # Contact must mean "an enemy can actually SEE Biribel", not "some
    # member is in CHASE". The old test read e.last_seen_pos, which the
    # director itself writes every tick (coord_target -> formation point),
    # so the squad fed its own destination back as the fresh fix: contact
    # never went stale, the sweep line never advanced, and the fireteam
    # parked in the lobby forever while the player sat untouched on the
    # dock (ghost-town holdout: 5 live enemies, 0 damage, 0 exfil).
    # Sightline is a cheap clip check; only a real sighting refreshes.
    saw = False
    for e in STATE.enemies:
        if _m3g(e).sweep_team is None or e.hp <= 0:
            continue
        if not _wall_blocks_line(e.rect.centerx, e.rect.centery, px, py,
                                 _solid_walls()):
            saw = True
    if saw:
        STATE.m3_sweep_last_seen = (px, py)
    if getattr(STATE, "muzzle_flash_timer", 0) > 0 and not getattr(
            STATE, "m3_ko_muzzle_prev", False):
        STATE.m3_sweep_last_seen = (px, py)     # they heard your gun
        saw = True
    STATE.m3_ko_muzzle_prev = getattr(STATE, "muzzle_flash_timer", 0) > 0
    st["contact"] = 0 if saw else st["contact"] + 1
    if st.get("committed"):
        # Holdout: they hear the door cycle + van - refresh the fix on your
        # real position every ~2s so the assault never goes stale mid-dock.
        if st["t"] % 120 == 0:
            STATE.m3_sweep_last_seen = (px, py)
            st["contact"] = 0
    elif st["contact"] > SWEEP_ADVANCE:
        STATE.m3_sweep_last_seen = _wpos(_ZONE_CENTERS[_zone()])
        st["contact"] = SWEEP_ADVANCE - 600     # re-advance every 10s

    # zone dwell / anti-turtle
    z = _zone()
    if z == "lobby" and not st["lobby_seen"]:
        st["lobby_seen"] = True
        _radio("VOLKOV: Contact - shield point ahead! His sight cone is narrow: "
               "go around it, friend.", color=C_VOLKOV, duration=280,
               mark="ko_beat1")
    if st["zone"] == z:
        st["zone_t"] += 1
    else:
        st["zone"] = z
        st["zone_t"] = 0
    if (st["zone_t"] >= TURTLE_LIMIT and st["wave_idx"] >= 2
            and _once(f"ko_turtle_{z}_{st['t'] // 3000}")):
        door = _nearest_turtle_door(px, py)
        if door is not None:
            breach_door(door, "THEY'RE BREACHING!")

    # stairwell set-piece: charge under the player as wave 0 lands
    if st["stair_charge_t"] > 0:
        st["stair_charge_t"] -= 1
        if st["stair_charge_t"] == 1 and _once("ko_stair_charge"):
            dx, dy = _wpos((5, 8))
            effects.shake(18)
            effects.burst(dx + 32, dy, (120, 110, 90), 30,
                          speed_mul=1.6, life_min=14, life_max=44)
            effects.burst(dx + 32, dy, (80, 75, 68), 16,
                          speed_mul=0.6, life_min=24, life_max=60)
            try:
                audio.play("breach", volume=0.6)
                audio.play("explosion", volume=0.25)
            except Exception:
                pass
            if STATE.player is not None:
                STATE.floating_texts.append([
                    px, py - 34, "BREACH CHARGE - BELOW YOU!", (230, 120, 60), 90])

    _update_pending(st)
    _update_waves(st)
    _update_beat_gates(st)
    _update_stuck(st)
    _update_overwatch(st)
    _update_window(st)
    _update_holdout(st)
