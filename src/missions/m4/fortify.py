"""Mission 4 fortify: barricade sites, the build / upgrade / repair holds.

Sites come from the station map ("b" doors, "w" windows; STATE.m4_sites).
A barricade lives in STATE.m4_barricades[(col, row)] as
{"kind", "hp", "max", "rect"}. Doors take planks (upgrade to a steel plate),
windows take boards. Damage states by hp fraction: intact, damaged, broken
(under a third: bullets pass, bodies still don't) and gone (hp 0: the site is
open again and only a wreck is left).

Every hold is E held at the site: movement is locked while it runs and a hit
on Biribel cancels it. Building and upgrading happen in the fortify stage
only; repairs cost one supply a step and work in the siege as well.
"""

import math

import pygame

from core.config import TILE_SIZE
from core.state import STATE
from missions.m4.meta import (
    M4_BARRICADE_KINDS, M4_BUILD_HOLD, M4_REPAIR_STEP, M4_REPAIR_FRAC, M4_REPAIR_COST,
    M4_SITE_RADIUS, STAGE_FORTIFY, STAGE_SIEGE,
)
from missions.m4.world import _sfx
from missions.m4.escort import add_supply, held, C_SUPPLY

_HOLD = {"site": None, "t": 0, "mode": None, "release": False, "hp": None, "need": 0}


def reset():
    _HOLD.update(site=None, t=0, mode=None, release=False, hp=None, need=0)
    STATE.m4_hold_ui = None


def site_kind(col, row):
    for c, r, kind in getattr(STATE, "m4_sites", []):
        if (c, r) == (col, row):
            return kind
    return None


def site_center(col, row):
    return col * TILE_SIZE + TILE_SIZE // 2, row * TILE_SIZE + TILE_SIZE // 2


def nearest_site(x, y, radius=M4_SITE_RADIUS):
    best, best_d = None, radius
    for c, r, _kind in getattr(STATE, "m4_sites", []):
        sx, sy = site_center(c, r)
        d = math.hypot(sx - x, sy - y)
        if d <= best_d:
            best, best_d = (c, r), d
    return best


def standing(bar):
    return bar is not None and bar.get("hp", 0) > 0


def built_count():
    return sum(1 for b in getattr(STATE, "m4_barricades", {}).values() if standing(b))


def state_of(bar):
    if not standing(bar):
        return "gone"
    f = bar["hp"] / float(bar["max"])
    if f >= 0.67:
        return "intact"
    if f >= 1 / 3.0:
        return "damaged"
    return "broken"


def _place(site, kind):
    label, _cost, hp = M4_BARRICADE_KINDS[kind]
    c, r = site
    STATE.m4_barricades[site] = {
        "kind": kind, "hp": hp, "max": hp,
        "rect": pygame.Rect(c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE),
    }


def action_at(site):
    """(mode, kind, cost, frames, label) of what E would do at a site, or None."""
    if site is None:
        return None
    stage = getattr(STATE, "mission4_stage", None)
    bar = STATE.m4_barricades.get(site)
    if not standing(bar):
        if stage != STAGE_FORTIFY:
            return None
        kind = "planks" if site_kind(*site) == "door" else "boards"
        label, cost, _hp = M4_BARRICADE_KINDS[kind]
        return ("build", kind, cost, M4_BUILD_HOLD, "BUILD " + label)
    if bar["hp"] < bar["max"]:
        return ("repair", bar["kind"], M4_REPAIR_COST, M4_REPAIR_STEP, "REPAIR")
    if stage == STAGE_FORTIFY and bar["kind"] == "planks":
        label, cost, _hp = M4_BARRICADE_KINDS["plate"]
        return ("upgrade", "plate", cost - M4_BARRICADE_KINDS["planks"][1], M4_BUILD_HOLD,
                "UPGRADE TO " + label)
    return None


def prompt():
    """(label, cost, affordable) for the site Biribel stands at, else None."""
    p = STATE.player
    if p is None or getattr(STATE, "mission4_stage", None) not in (STAGE_FORTIFY, STAGE_SIEGE):
        return None
    act = action_at(nearest_site(p.rect.centerx, p.rect.centery))
    if act is None:
        return None
    return act[4], act[2], getattr(STATE, "m4_supply", 0) >= act[2]


def _finish(site, mode, kind, cost):
    sx, sy = site_center(*site)
    add_supply(-cost, sx, sy)
    if mode == "build":
        _place(site, kind)
        _sfx("door_rattle", 0.4)
    elif mode == "upgrade":
        _place(site, "plate")
        _sfx("rifle_handle", 0.5)
    else:
        bar = STATE.m4_barricades[site]
        bar["hp"] = min(bar["max"], bar["hp"] + int(bar["max"] * M4_REPAIR_FRAC))
        _sfx("rifle_handle", 0.3)


def update_holds(keys):
    """Per frame in fortify/siege: run the E hold at the nearest site."""
    STATE.m4_hold_ui = None
    p = STATE.player
    stage = getattr(STATE, "mission4_stage", None)
    if (p is None or getattr(STATE, "player_dead", False)
            or stage not in (STAGE_FORTIFY, STAGE_SIEGE)
            or getattr(STATE, "m4_dialogue_active", False)):
        reset()
        return
    hp = p.hp
    hurt = _HOLD["hp"] is not None and hp < _HOLD["hp"]
    _HOLD["hp"] = hp
    if not held(keys, pygame.K_e):
        _HOLD.update(site=None, t=0, mode=None, release=False)
        return
    if _HOLD["release"]:
        return
    site = nearest_site(p.rect.centerx, p.rect.centery)
    act = action_at(site)
    if act is None:
        _HOLD.update(site=None, t=0, mode=None)
        return
    mode, kind, cost, frames, label = act
    if getattr(STATE, "m4_supply", 0) < cost:
        STATE.floating_texts.append([p.rect.centerx, p.rect.centery - 44,
                                     "NEED %d SUPPLY" % cost, C_SUPPLY, 70])
        _sfx("menu_click", 0.3)
        _HOLD["release"] = True
        return
    if hurt and _HOLD["t"] > 0:
        STATE.floating_texts.append([p.rect.centerx, p.rect.centery - 44,
                                     "INTERRUPTED", (230, 110, 90), 60])
        _HOLD.update(site=None, t=0, mode=None, release=True)
        return
    if site != _HOLD["site"] or mode != _HOLD["mode"]:
        _HOLD.update(site=site, t=0, mode=mode)
    _HOLD["t"] += 1
    STATE.m4_work_lock = True
    STATE.m4_hold_ui = (label, _HOLD["t"] / float(frames), site)
    if _HOLD["t"] % 15 == 1:
        _sfx("footstep", 0.25)
    if _HOLD["t"] >= frames:
        _finish(site, mode, kind, cost)
        _HOLD["t"] = 0
        # Repairs chain while E stays down; a build or upgrade wants a fresh press.
        if mode != "repair":
            _HOLD["release"] = True


def damage(site, amount, x=None, y=None):
    """Hurt a barricade. Returns True when this hit brought it down."""
    bar = STATE.m4_barricades.get(site)
    if not standing(bar):
        return False
    before = state_of(bar)
    bar["hp"] = max(0, bar["hp"] - amount)
    after = state_of(bar)
    if after == before:
        return False
    sx, sy = site_center(*site)
    if after == "gone":
        STATE.floating_texts.append([sx, sy - 30, M4_BARRICADE_KINDS[bar["kind"]][0] + " DOWN",
                                     (230, 110, 90), 100])
        _sfx("concrete_impact", 0.5)
        return True
    if after == "broken":
        STATE.floating_texts.append([sx, sy - 30, "BREAKING", (230, 160, 90), 70])
    return False


def site_of_rect(rect):
    for site, bar in getattr(STATE, "m4_barricades", {}).items():
        if bar.get("rect") is rect:
            return site
    return None


def bullet_hit(b, shot_only=True):
    """Barricade the bullet segment crossed this frame (or None)."""
    seg = ((b["prev_x"], b["prev_y"]), (b["x"], b["y"]))
    from missions.m4.world import barricade_blocks_shots
    for site, bar in getattr(STATE, "m4_barricades", {}).items():
        if not standing(bar) or (shot_only and not barricade_blocks_shots(bar)):
            continue
        if bar["rect"].clipline(*seg):
            return site
    return None
