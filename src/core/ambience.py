
"""ambience.py - zone-driven world ambience layers.

Pumped once per frame from the main loop. Uses only existing AudioManager
features (looped play, stop, schedule) - no mixer changes. Every layer is a
loop or scheduled one-shot; mission changes tear all layers down so nothing
leaks across missions or respawns.
"""
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream

from core.config import audio
from core.state import STATE

TILE = 64

# World rects where hardware hum lives (relay / server / generator rooms).
ELEC_ZONES = {
    "MISSION3": [(36 * TILE, 32 * TILE, 46 * TILE, 42 * TILE)],
    "MISSION1": [(12 * TILE, 20 * TILE, 20 * TILE, 26 * TILE)],
}
# Corridors where tiled drips echo.
# Drips belong to the cell block's wet plumbing ONLY. A drip echoing in the
# comms wing or archives reads as a random unexplained noise.
DRIP_ZONES = {
    "MISSION3": [(4 * TILE, 4 * TILE, 20 * TILE, 20 * TILE)],
}
RAIN_MISSIONS = {"MISSION1", "MISSION2", "MISSION4"}
GUST_MISSIONS = {"MISSION2", "MISSION4"}   # exterior only; indoors a gust reads as static
PA_STAGES = set()              # random PA removed: the prison PA only exists
                               # where the script puts it (see systems.py)
_state = {
    "mission": None,
    "room_tone_on": False,
    "rain_inside_on": False,
    "elec_hum_on": False,
    "drip_timer": 0,
    "gust_timer": 0,
    "pa_timer": 0,
    "debris_cooldown": 0,
    "shake_seen": 0,
}


def _in_any(zones, x, y, pad=0):
    for x0, y0, x1, y1 in zones:
        if x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad:
            return True
    return False


def _teardown():
    for name in ("room_tone", "rain_inside", "elec_hum"):
        try:
            audio.stop(name)
        except Exception:
            pass
    _state["room_tone_on"] = False
    _state["rain_inside_on"] = False
    _state["elec_hum_on"] = False


def update_ambience():
    mission = getattr(STATE, "active_mission", None)
    if mission != _state["mission"]:
        _state["mission"] = mission
        _teardown()
        _state["drip_timer"] = 300
        _state["gust_timer"] = 480
        _state["pa_timer"] = 0
        _state["debris_cooldown"] = 0
        try:
            from core import settings_store
            _state["layers_on"] = bool(
                settings_store.load().get("ambience_layers", True))
        except Exception:
            _state["layers_on"] = True
    player = STATE.player
    if player is None or mission is None:
        return
    px, py = player.rect.centerx, player.rect.centery
    layers = _state.get("layers_on", True)

    # 1 ── interior bed: the room is alive
    if layers and not _state["room_tone_on"]:
        audio.play("room_tone", volume=0.35, loops=-1)
        _state["room_tone_on"] = True

    # 2 ── rain heard through the roof, layered under the exterior loop
    if layers and mission in RAIN_MISSIONS and not _state["rain_inside_on"]:
        audio.play("rain_inside", volume=0.4, loops=-1)
        _state["rain_inside_on"] = True

    # 3 ── electrical hum near relay/server hardware (hysteresis: 260 in / 340 out)
    zones = ELEC_ZONES.get(mission, ())
    if layers and not _state["elec_hum_on"] and _in_any(zones, px, py, pad=260):
        audio.play("elec_hum", volume=0.35, loops=-1)
        _state["elec_hum_on"] = True
    elif _state["elec_hum_on"] and not _in_any(zones, px, py, pad=340):
        audio.stop("elec_hum")
        _state["elec_hum_on"] = False

    # 4 ── tiled-corridor drips, only when the guns are quiet
    _state["drip_timer"] -= 1
    if _state["drip_timer"] <= 0:
        if (layers and _in_any(DRIP_ZONES.get(mission, ()), px, py)
                and _state["shake_seen"] <= 0):
            audio.play("drip_echo", volume=0.18)
            if _rng_legacy.random() < 0.20:
                audio.schedule(_rng_legacy.randint(14, 30), "drip_echo", volume=0.12)
        _state["drip_timer"] = _rng_legacy.randint(360, 720)

    # 5 ── wind gusts through broken glass
    if layers and mission in GUST_MISSIONS:
        _state["gust_timer"] -= 1
        if _state["gust_timer"] <= 0:
            audio.play("wind_gust", volume=0.10)
            _state["gust_timer"] = _rng_legacy.randint(720, 1440)

    # 7 ── the building answers explosions: debris settling afterwards
    shake = getattr(STATE, "screen_shake", 0)
    if shake >= 18:
        _state["shake_seen"] = 90
        if _state["debris_cooldown"] <= 0:
            audio.schedule(_rng_legacy.randint(60, 120), "debris_settle", volume=0.25)
            _state["debris_cooldown"] = 240
    _state["shake_seen"] = max(0, _state["shake_seen"] - 1)
    _state["debris_cooldown"] = max(0, _state["debris_cooldown"] - 1)
