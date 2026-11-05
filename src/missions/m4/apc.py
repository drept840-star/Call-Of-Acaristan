"""Mission 4 wave 5: the APC ram.

The APC comes in along the forecourt lane from the east, turns north at the
main door, rams it (both door barricades go, a blast at the door), backs off
half a tile and parks. Parked, its hull is solid cover on the forecourt and
breachers pile out of the back.

STATE.m4_apc = {"x", "y", "yaw", "phase", "t", "shake"} in world pixels;
phases: "lane" (driving west), "turn", "ram" (north to the door), "back",
"parked". None until wave 5 calls start().
"""

import math

import pygame

from core.config import TILE_SIZE
from core.state import STATE
from fx import effects
from missions.m4.meta import C_VASILE
from missions.m4.world import _radio, _sfx

T = TILE_SIZE
HULL_W, HULL_L = 2.0 * T, 3.0 * T     # hull footprint (across, along)
LANE_Y = 26 * T              # rows 25-26: clear of the jersey barriers on row 24
TURN_X = 18 * T              # main door centre (cols 17-18)
TURN_RATE = 0.05             # rad per frame through the arc
TURN_SPEED = 2.4             # px per frame through the arc (radius = speed / rate)
TURN_R = TURN_SPEED / TURN_RATE
RAM_Y = 22 * T + HULL_L / 2 + 4   # hull centre when the nose meets the door row
PARK_Y = RAM_Y + T           # backs off a tile: row 22 stays a lane to the door
START_X = 36 * T + 2 * T
LANE_SPEED = 3.2
RAM_SPEED = 4.4
MAIN_DOOR = ((17, 21), (18, 21))


def start():
    if getattr(STATE, "m4_apc", None):
        return
    STATE.m4_apc = {"x": START_X, "y": LANE_Y, "yaw": math.pi, "phase": "lane", "t": 0,
                    "rect": None}
    _radio("MARU: APC on the forecourt lane! It's going for the main door!", color=C_VASILE,
           duration=360, mark="apc_in")
    _sfx("rig_low_boom", 0.35)


def hull_rect(apc):
    """Axis-aligned hull rect for the current yaw (lane: long across x)."""
    along_x = abs(math.cos(apc["yaw"])) > 0.7
    w, h = (HULL_L, HULL_W) if along_x else (HULL_W, HULL_L)
    r = pygame.Rect(0, 0, int(w), int(h))
    r.center = (int(apc["x"]), int(apc["y"]))
    return r


def _crush(r):
    """Anything standing in the hull's way gets shoved (and hurt)."""
    p = STATE.player
    if p is not None and not getattr(STATE, "player_dead", False) and r.colliderect(p.rect):
        p.take_damage(35)
        effects.shake(10)
        dx = p.rect.centerx - r.centerx
        dy = p.rect.centery - r.centery
        d = math.hypot(dx, dy) or 1.0
        p.rect.x += int(dx / d * 40)
        p.rect.y += int(dy / d * 40)
    for e in STATE.enemies:
        if e.hp > 0 and r.colliderect(e.rect):
            e.hp -= 60


def _ram():
    from missions.m4 import fortify, siege
    for site in MAIN_DOOR:
        bar = STATE.m4_barricades.get(site)
        if fortify.standing(bar):
            fortify.damage(site, bar["hp"])
    x, y = 17.5 * T + T // 2, 21 * T + T // 2
    siege._blast(x, y, 110, 40)
    effects.shake(22)
    _sfx("rig_metal_collapse", 0.6)
    _radio("VASILE: Main door's gone! Breachers behind it!", color=C_VASILE,
           duration=320, mark="apc_ram", interrupt=True)


def _park():
    apc = STATE.m4_apc
    r = hull_rect(apc)
    apc["rect"] = (r.x, r.y, r.w, r.h)
    STATE.walls.append(r)
    from missions.m4 import siege
    for i, kind in enumerate(("breacher", "breacher", "loyalist", "breacher", "loyalist")):
        e = siege._spawn(kind, "S")
        e.rect.center = (int(apc["x"]) - 60 + 30 * i, r.bottom + 40)


def restore_parked():
    """Snapshot restore: a parked APC is back as solid cover."""
    apc = getattr(STATE, "m4_apc", None)
    if apc and apc.get("phase") == "parked" and apc.get("rect"):
        STATE.walls.append(pygame.Rect(apc["rect"]))


def update():
    apc = getattr(STATE, "m4_apc", None)
    if not apc or apc["phase"] == "parked":
        return
    apc["t"] += 1
    if apc["t"] % 40 == 1:
        _sfx("ambient_drone", 0.12)
    if apc["phase"] == "lane":
        apc["x"] -= LANE_SPEED
        if apc["x"] <= TURN_X + TURN_R:
            apc["x"] = TURN_X + TURN_R
            apc["phase"] = "turn"
    elif apc["phase"] == "turn":
        # Arc right (west -> north) about a fixed centre so the hull never
        # swings through the barriers or the south wall.
        want = -math.pi / 2
        diff = (want - apc["yaw"] + math.pi) % (2 * math.pi) - math.pi
        apc["yaw"] += max(-TURN_RATE, min(TURN_RATE, diff))
        if abs(diff) < TURN_RATE + 0.01:
            apc["yaw"] = want
            apc["phase"] = "ram"
        # pivot (TURN_X + R, LANE_Y - R); yaw runs pi -> 3pi/2 through the arc
        yaw = apc["yaw"] if apc["phase"] == "turn" else 1.5 * math.pi
        apc["x"] = TURN_X + TURN_R + TURN_R * math.sin(yaw)
        apc["y"] = LANE_Y - TURN_R - TURN_R * math.cos(yaw)
    elif apc["phase"] == "ram":
        apc["y"] -= RAM_SPEED
        if apc["y"] <= RAM_Y:
            apc["y"] = RAM_Y
            _ram()
            apc["phase"] = "back"
    elif apc["phase"] == "back":
        apc["y"] += 1.2
        if apc["y"] >= PARK_Y:
            apc["y"] = PARK_Y
            apc["phase"] = "parked"
            _park()
            return
    _crush(hull_rect(apc))
