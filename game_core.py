# ------------------------------------------------------------
# game_core.py
# ------------------------------------------------------------

# ------------------------------------------------------------
# game_core.py
# ------------------------------------------------------------

# ------------------------------------------------------------
# game_core.py
# ------------------------------------------------------------

# ------------------------------------------------------------

"""game_core.py — Proxy facade that delegates to split modules.

This keeps old code like:
    import game_core as gc
    gc.start_mission()
    gc.player
    gc.show_minimap = False
working while the real implementation lives in split files.

Mission 2 integration note:
    The original game used gc.game_update()/gc.game_draw() for Mission 1.
    Those calls now route to Mission 2 when STATE.active_mission == "MISSION2".
"""
import sys
import types

from state import STATE
import cutscenes
import walking_sim
import mission
import mission2
import mission3
import ui_hud
import weapons
import interactions
import effects

_MODULES = [
    cutscenes,
    walking_sim,
    mission,
    mission2,
    mission3,
    ui_hud,
    weapons,
    interactions,
    effects,
]

# These are still owned by walking_sim module-level globals.
# Everything else should prefer STATE first.
_MODULE_FIRST_NAMES = {
    "walk_dialogue_active",
    "walk_dialogue_speaker",
    "walk_dialogue_text",
    "walk_dialogue_char_idx",
    "walk_dialogue_timer",
    "rain_drops",
    "warehouse_hp_bonus",
    "warehouse_mag_bonus",
    "warehouse_intel_given",
    "player_rations",
}


def _is_mission2_active():
    return getattr(STATE, "active_mission", "MISSION1") == "MISSION2"


def _is_mission3_active():
    return getattr(STATE, "active_mission", "MISSION1") == "MISSION3"


# ─────────────────────────────────────────────
# Routed mission entry/update/draw helpers
# ─────────────────────────────────────────────
def start_mission(preserve_timer=False):
    """Start Mission 1."""
    return mission.start_mission(preserve_timer=preserve_timer)


def start_mission2(preserve_timer=False):
    """Start Mission 2: Quiet on Route 12."""
    return mission2.start_mission2(preserve_timer=preserve_timer)


def start_mission2_sniper(preserve_timer=False):
    """Start Mission 2 at the sniper cutscene."""
    return mission2.start_mission2_sniper(preserve_timer=preserve_timer)


def start_mission2_checkpoint(preserve_timer=False):
    """Start Mission 2 at the evidence-phase checkpoint (post-tanker blast).

    Used by restart_current_mission() when the player has reached the
    evidence phase and dies — respawns at the shelter instead of restarting
    the entire mission.
    """
    return mission2.start_mission2_checkpoint(preserve_timer=preserve_timer)


def start_mission3(preserve_timer=False):
    """Start Mission 3: The Interrogation."""
    return mission3.start_mission3(preserve_timer=preserve_timer)


def start_mission3_breakout_checkpoint(preserve_timer=False):
    """Restart Mission 3 at post-Volkov-breach gameplay."""
    return mission3.start_mission3_breakout_checkpoint(preserve_timer=preserve_timer)


def start_mission3_comms_checkpoint(preserve_timer=False):
    """Restart Mission 3 at the Comms Wing."""
    return mission3.start_mission3_comms_checkpoint(preserve_timer=preserve_timer)


def start_mission3_archives_checkpoint(preserve_timer=False):
    """Restart Mission 3 at the Archives Wing (Phase 4)."""
    return mission3.start_mission3_archives_checkpoint(preserve_timer=preserve_timer)


def restart_current_mission():
    """Restart whichever playable mission is currently active.

    Uses STATE.active_mission to decide — EXCEPT when:
    1. The player is in the walking sim (acaristan.game_state == "WALK"),
       which is a transition scene between M1 and M2 and doesn't reset
       active_mission. A restart from WALK always goes to Mission 1.
    2. The player has reached the Mission 2 evidence-phase checkpoint
       (STATE.mission2_checkpoint_reached == True). In this case we respawn
       at the shelter with the evidence phase active, instead of restarting
       the entire mission from the intro cutscene. This makes the difficult
       3-wave cleanup team fight feel fair — dying doesn't lose 20+ minutes
       of progress.
    """
    if _is_mission2_active() and not _in_walking_sim():
        if getattr(STATE, "mission2_checkpoint_reached", False):
            return start_mission2_checkpoint(preserve_timer=False)
        return mission2.start_mission2(preserve_timer=False)
    if _is_mission3_active() and not _in_walking_sim():
        if getattr(STATE, "mission3_archives_checkpoint_reached", False):
            return mission3.start_mission3_archives_checkpoint(preserve_timer=False)
        if getattr(STATE, "mission3_comms_checkpoint_reached", False):
            return mission3.start_mission3_comms_checkpoint(preserve_timer=False)
        if getattr(STATE, "mission3_breakout_checkpoint_reached", False):
            return mission3.start_mission3_breakout_checkpoint(preserve_timer=False)
        return mission3.start_mission3(preserve_timer=False)
    return mission.start_mission(preserve_timer=False)


def _in_walking_sim():
    """Returns True if the player is currently in the walking sim transition.

    The walking sim (acaristan.game_state == "WALK") sits between Mission 1
    and Mission 2. It doesn't reset STATE.active_mission, so we can't use
    active_mission alone to decide what to restart — we have to check the
    top-level game state too.

    Late-imports acaristan to avoid a circular dependency (acaristan imports
    game_core at module load time). In the running game acaristan is already
    in sys.modules, so this is a dict lookup, not a re-execution.
    """
    try:
        acaristan_mod = sys.modules.get("acaristan") or sys.modules.get("__main__")
        return getattr(acaristan_mod, "game_state", "") == "WALK"
    except Exception:
        return False


def game_update(keys):
    if _is_mission3_active():
        return mission3.game_update(keys)
    if _is_mission2_active():
        return mission2.game_update(keys)
    return mission.game_update(keys)


def game_draw(fcx, fcy):
    if _is_mission3_active():
        return mission3.game_draw(fcx, fcy)
    if _is_mission2_active():
        return mission2.game_draw(fcx, fcy)
    return mission.game_draw(fcx, fcy)


def handle_interact():
    if _is_mission3_active():
        # M3: E key at the drain triggers the crafting minigame (if the player
        # has a chair_leg and hasn't sharpened it yet).
        import mission3
        return mission3.handle_interact()
    if _is_mission2_active():
        return mission2.handle_interact()
    return interactions.handle_interact()


def debug_jump_to_exfil():
    if _is_mission3_active():
        # No debug jump for M3 — it's a linear dialogue mission.
        return
    if _is_mission2_active():
        return mission2.debug_jump_to_evidence()
    return mission.debug_jump_to_exfil()


class _GameCoreModule(types.ModuleType):
    """Proxy module — routes old game_core globals to new modules/STATE."""

    def __getattr__(self, name):
        if name in _MODULE_FIRST_NAMES:
            for mod in _MODULES:
                if hasattr(mod, name):
                    return getattr(mod, name)
        if hasattr(STATE, name):
            return getattr(STATE, name)
        for mod in _MODULES:
            if hasattr(mod, name):
                return getattr(mod, name)
        raise AttributeError(f"module 'game_core' has no attribute {name!r}")

    def __setattr__(self, name, value):
        wrote = False
        if hasattr(STATE, name):
            setattr(STATE, name, value)
            wrote = True
        # Important: propagate to ALL modules that imported screen/config globals.
        for mod in _MODULES:
            if hasattr(mod, name):
                setattr(mod, name, value)
                wrote = True
        if not wrote:
            super().__setattr__(name, value)


_proxy = _GameCoreModule(__name__)
_proxy.__dict__.update({
    "__doc__": __doc__,
    "__file__": __file__,
    "__package__": __package__,
    "__loader__": __loader__,
    "__spec__": __spec__,
    # Explicit routed functions override same-named functions in split modules.
    "start_mission": start_mission,
    "start_mission2": start_mission2,
    "start_mission2_sniper": start_mission2_sniper,
    "start_mission2_checkpoint": start_mission2_checkpoint,
    "start_mission3": start_mission3,
    "start_mission3_breakout_checkpoint": start_mission3_breakout_checkpoint,
    "start_mission3_comms_checkpoint": start_mission3_comms_checkpoint,
    "start_mission3_archives_checkpoint": start_mission3_archives_checkpoint,
    "restart_current_mission": restart_current_mission,
    "game_update": game_update,
    "game_draw": game_draw,
    "handle_interact": handle_interact,
    "debug_jump_to_exfil": debug_jump_to_exfil,
})
sys.modules[__name__] = _proxy
