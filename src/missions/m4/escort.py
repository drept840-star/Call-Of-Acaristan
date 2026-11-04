"""Mission 4 escort: Vasile, the KRAP comms cache and the supply pool.

Vasile carries the cache across the curfew street. The cache is the supply
pool the station is fortified with (STATE.m4_supply). He follows Biribel on
a leash (world._ally_follow), shoots back, and street shooters pick him as
a target about a third of the time they can see him.

Downs: the first time he hits 0 HP he is downed, spills a quarter of the
cache and Biribel has M4_REVIVE_WINDOW frames to hold E over him. The
second down, or a window that runs out, kills him and fails the mission.
The rule holds for the whole mission, the siege included.
"""

import math

import pygame

from engine.core import LEGACY_RNG as _rng_legacy
from core.state import STATE
from missions.m4.meta import (
    C_VASILE, BIRIBEL_SPEAKER, M4_SUPPLY_DROP_FRAC, M4_REVIVE_WINDOW, M4_REVIVE_HOLD,
    M4_REVIVE_RADIUS, M4_FOCUS_VASILE, M4_DOOR_ESCORT_RADIUS,
)
from missions.m4.world import (
    _ally, _m4g, _near, _player_pos, _radio, _sfx, _street_door_pos, fail_mission,
)

C_SUPPLY = (232, 190, 96)


def held(keys, key):
    try:
        return bool(keys is not None and keys[key])
    except (IndexError, KeyError, TypeError):
        return False


def vasile():
    a = _ally("VASILE")
    if a is None or a.get("dead"):
        return None
    return a


def vasile_up():
    a = vasile()
    return a is not None and a["downed"] <= 0


def add_supply(n, x=None, y=None):
    STATE.m4_supply = max(0, getattr(STATE, "m4_supply", 0) + n)
    if x is not None and n:
        text = ("+%d SUPPLY" % n) if n > 0 else ("-%d SUPPLY" % -n)
        STATE.floating_texts.append([x, y - 30, text, C_SUPPLY, 90])


def vasile_down(a):
    """Vasile hit 0 HP (world._damage_m4_ally)."""
    if getattr(STATE, "m4_vasile_downs", 0) >= 1:
        _vasile_dies(a)
        return
    STATE.m4_vasile_downs = 1
    a["downed"] = M4_REVIVE_WINDOW
    a["revive"] = 0
    a["following"] = False
    a["path_goal"] = None
    pool = getattr(STATE, "m4_supply", 0)
    spill = max(1, int(round(pool * M4_SUPPLY_DROP_FRAC))) if pool > 0 else 0
    if spill:
        add_supply(-spill, a["x"], a["y"])
    STATE.blood_decals.append([a["x"], a["y"], 150, _rng_legacy.randint(10, 16)])
    _radio("VASILE: I'm hit - I'm down! The cache is spilling - get me up!",
           color=C_VASILE, duration=360, mark="vasile_down")
    _sfx("bullet_impact_enemy", 0.5)


def _vasile_dies(a):
    a["dead"] = True
    a["downed"] = 0
    a["hp"] = 0
    STATE.m4_cache_carried = False
    STATE.blood_decals.append([a["x"], a["y"], 180, _rng_legacy.randint(16, 24)])
    fail_mission("vasile")


def update_vasile_down(keys):
    """Per frame, any stage: tick the revive window and the E hold."""
    a = vasile()
    STATE.m4_reviving = False
    if a is None or a["downed"] <= 0:
        return
    a["downed"] -= 1
    close = (STATE.player is not None and not getattr(STATE, "player_dead", False)
             and math.hypot(a["x"] - STATE.player.rect.centerx,
                            a["y"] - STATE.player.rect.centery) <= M4_REVIVE_RADIUS)
    if close and held(keys, pygame.K_e):
        a["revive"] += 1
        STATE.m4_reviving = True
        STATE.m4_work_lock = True
        if a["revive"] % 30 == 1:
            _sfx("rifle_handle", 0.18)
    else:
        a["revive"] = max(0, a["revive"] - 2)
    if a["revive"] >= M4_REVIVE_HOLD:
        a["downed"] = 0
        a["revive"] = 0
        a["hp"] = a["max_hp"] // 2
        a["hurt"] = 0
        STATE.m4_reviving = False
        _radio("VASILE: ...Okay. I'm up. That was the one, Biribel - "
               "I don't get another.", color=C_VASILE, duration=380, mark="vasile_up")
        _sfx("pickup", 0.4)
    elif a["downed"] <= 0:
        _radio("BIRIBEL: Vasile? ...Vasile!", color=BIRIBEL_SPEAKER, duration=300,
               mark="vasile_lost")
        _vasile_dies(a)


def revive_prompt():
    """(seconds left, hold fraction) while Vasile is down, else None."""
    a = vasile()
    if a is None or a["downed"] <= 0:
        return None
    return a["downed"] / 60.0, a["revive"] / float(M4_REVIVE_HOLD)


def enemy_focus(e, px, py, walls):
    """Street shooters: who this enemy is after this frame. Returns (x, y)."""
    a = vasile()
    if a is None or a["downed"] > 0:
        return px, py
    g = _m4g(e)
    g.focus_t -= 1
    if g.focus_t <= 0:
        g.focus_t = _rng_legacy.randint(70, 130)
        sees = e._can_see(a["x"], a["y"], walls)
        g.focus = "vasile" if sees and _rng_legacy.random() < M4_FOCUS_VASILE else "player"
    if g.focus == "vasile":
        return a["x"], a["y"]
    return px, py


def vasile_at_door():
    a = vasile()
    if a is None or a["downed"] > 0:
        return False
    dx, dy = _street_door_pos()
    return math.hypot(a["x"] - dx, a["y"] - dy) <= M4_DOOR_ESCORT_RADIUS
