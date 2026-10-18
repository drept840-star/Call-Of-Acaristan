# ------------------------------------------------------------

"""game_core.py - Proxy facade that delegates to split modules.

This keeps old code like:
    from core import game_core as gc
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

from core.state import STATE
import cutscenes
from missions import walking_sim
from missions import m1
from missions import m2
from missions import m3
from missions import m4
from missions import m5
from missions import m6
from missions import m0
from ui import hud
from entities import weapons
from core import interactions
from fx import effects
import game.world as _gw  # RPE6 Phase 5: engine.world host (PRE / SIM+POST / RENDER_SUBMIT around the legacy loop)
import game.render as _gr  # RPE6 Phase 6: engine.render2d host (the gameplay frame goes through the render queue)
from core import config as _cfg

_MODULES = [
    cutscenes,
    walking_sim,
    m1,
    m2,
    m3,
    m4,
    m5,
    m6,
    hud,
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


def _is_mission4_active():
    return getattr(STATE, "active_mission", "MISSION1") == "MISSION4"


def _is_mission5_active():
    return getattr(STATE, "active_mission", "MISSION1") == "MISSION5"

def _is_mission6_active():
    return getattr(STATE, "active_mission", "MISSION1") == "MISSION6"


def _is_mission0_active():
    # RPE6 Phase 10: Mission 0 (tutorial mission, D2 proof) - game-side host.
    return getattr(STATE, "active_mission", "MISSION1") == "MISSION0"


# ─────────────────────────────────────────────
# Routed mission entry/update/draw helpers
# ─────────────────────────────────────────────
def start_mission0(preserve_timer=False):
    """Start Mission 0: Depot (RPE6 Phase 10 tutorial mission)."""
    return m0.start_mission0(preserve_timer=preserve_timer)


def start_mission(preserve_timer=False):
    """Start Mission 1."""
    return m1.start_mission(preserve_timer=preserve_timer)


def start_mission2(preserve_timer=False):
    """Start Mission 2: Quiet on Route 12."""
    return m2.start_mission2(preserve_timer=preserve_timer)


def start_mission2_sniper(preserve_timer=False):
    """Start Mission 2 at the sniper cutscene."""
    return m2.start_mission2_sniper(preserve_timer=preserve_timer)


def start_mission2_checkpoint(preserve_timer=False):
    """Start Mission 2 at the evidence-phase checkpoint (post-tanker blast).

    Used by restart_current_mission() when the player has reached the
    evidence phase and dies - respawns at the shelter instead of restarting
    the entire m1.
    """
    return m2.start_mission2_checkpoint(preserve_timer=preserve_timer)


def start_mission3(preserve_timer=False):
    """Start Mission 3: The Interrogation."""
    return m3.start_mission3(preserve_timer=preserve_timer)


def start_mission3_breakout_checkpoint(preserve_timer=False):
    """Restart Mission 3 at post-Volkov-breach gameplay."""
    return m3.start_mission3_breakout_checkpoint(preserve_timer=preserve_timer)


def start_mission3_comms_checkpoint(preserve_timer=False):
    """Restart Mission 3 at the Comms Wing."""
    return m3.start_mission3_comms_checkpoint(preserve_timer=preserve_timer)


def start_mission3_archives_checkpoint(preserve_timer=False):
    """Restart Mission 3 at the Archives Wing (Phase 4)."""
    return m3.start_mission3_archives_checkpoint(preserve_timer=preserve_timer)


def start_mission3_kill_order_checkpoint(preserve_timer=False):
    """Restart Mission 3 at the Kill Order ground floor (Phase 5)."""
    return m3.start_mission3_kill_order_checkpoint(preserve_timer=preserve_timer)


def start_mission3_broadcast_checkpoint(preserve_timer=False):
    """Restart Mission 3 at the Broadcast Wing (Phase 6)."""
    return m3.start_mission3_broadcast_checkpoint(preserve_timer=preserve_timer)


def start_mission4(preserve_timer=False):
    """Start Mission 4: The Aftermath."""
    return m4.start_m4(preserve_timer=preserve_timer)


def start_mission4_station_checkpoint(preserve_timer=False):
    """Restart Mission 4 at the radio-station interior checkpoint."""
    return m4.start_mission4_station_checkpoint(preserve_timer=preserve_timer)


def start_mission4_tower_checkpoint(preserve_timer=False):
    """Restart Mission 4 at the transmitter hold (siege checkpoint)."""
    return m4.start_mission4_tower_checkpoint(preserve_timer=preserve_timer)


def start_mission5(preserve_timer=False):
    """Start Mission 5: Martial Law (Guard HQ walk -> Vasile's office)."""
    return m5.start_m5(preserve_timer=preserve_timer)


def start_mission5_hq_checkpoint(preserve_timer=False):
    """Mission 5 Guard HQ walking sim (the opening; same as a fresh start)."""
    return m5.start_mission5_hq_checkpoint(preserve_timer=preserve_timer)


def start_mission5_quarter_checkpoint(preserve_timer=False):
    """Restart Mission 5 in the Lower Quarter (HQ + office already played)."""
    return m5.start_mission5_quarter_checkpoint(preserve_timer=preserve_timer)


def start_mission5_printworks_checkpoint(preserve_timer=False):
    """Restart Mission 5 inside the MAG print works (find Maru)."""
    return m5.start_mission5_printworks_checkpoint(preserve_timer=preserve_timer)


def start_mission5_tunnel_checkpoint(preserve_timer=False):
    """Restart Mission 5 at the basement tunnel (escort Maru)."""
    return m5.start_mission5_tunnel_checkpoint(preserve_timer=preserve_timer)

def start_mission6(preserve_timer=False):
    return _call_m6(m6.start_m6, preserve_timer)

def _call_m6(fn, preserve_timer=False):
    """Call M6 entry points across old/new facade signatures safely."""
    try:
        return fn(preserve_timer=preserve_timer)
    except TypeError as exc:
        if "preserve_timer" not in str(exc):
            raise
        return fn()

def _m6_checkpoint(name, preserve_timer=False):
    fn = getattr(m6, name, None)
    result = _call_m6(fn, preserve_timer) if fn else _call_m6(m6.start_m6, preserve_timer)
    if name.endswith("train_checkpoint"):
        STATE.m6_train_checkpoint_reached = True
    return result

def start_mission6_train_checkpoint(preserve_timer=False):
    return _m6_checkpoint("start_mission6_train_checkpoint", preserve_timer)

def start_mission6_customs_checkpoint(preserve_timer=False):
    return _m6_checkpoint("start_mission6_customs_checkpoint", preserve_timer)

def start_mission6_noman_checkpoint(preserve_timer=False):
    return _m6_checkpoint("start_mission6_noman_checkpoint", preserve_timer)

def start_mission6_rail_checkpoint(preserve_timer=False):
    return _m6_checkpoint("start_mission6_rail_checkpoint", preserve_timer)


def start_mission6_train_checkpoint(preserve_timer=False):
    return _m6_checkpoint("start_mission6_train_checkpoint", preserve_timer)


def restart_current_mission():
    """Restart whichever playable mission is currently active.

    Uses STATE.active_mission to decide - EXCEPT when:
    1. The player is in the walking sim (acaristan.game_state == "WALK"),
       which is a transition scene between M1 and M2 and doesn't reset
       active_mission. A restart from WALK always goes to Mission 1.
    2. The player has reached the Mission 2 evidence-phase checkpoint
       (STATE.mission2_checkpoint_reached == True). In this case we respawn
       at the shelter with the evidence phase active, instead of restarting
       the entire mission from the intro cutscene. This makes the difficult
       3-wave cleanup team fight feel fair - dying doesn't lose 20+ minutes
       of progress.
    3. The player has reached a Mission 3 phase checkpoint. M3 is the
       longest chain in the campaign (six phases), so the respawn is the
       DEEPEST phase reached, not the archives: the Kill Order and the
       Broadcast Wing are combat gauntlets, and dropping a player who died
       in the dock holdout back into the atrium costs them the whole run.
    4. The player has reached a Mission 5 checkpoint. The print works and the
       tunnel escort are both gated by checkpoints; the deepest one reached
       wins so a Maru death in the tunnel doesn't replay the raid.
    """
    if _is_mission2_active() and not _in_walking_sim():
        if getattr(STATE, "mission2_checkpoint_reached", False):
            return start_mission2_checkpoint(preserve_timer=False)
        return m2.start_mission2(preserve_timer=False)
    if _is_mission3_active() and not _in_walking_sim():
        if getattr(STATE, "mission3_broadcast_checkpoint_reached", False):
            return start_mission3_broadcast_checkpoint(preserve_timer=False)
        if getattr(STATE, "mission3_kill_order_checkpoint_reached", False):
            return start_mission3_kill_order_checkpoint(preserve_timer=False)
        if getattr(STATE, "mission3_archives_checkpoint_reached", False):
            return m3.start_mission3_archives_checkpoint(preserve_timer=False)
        if getattr(STATE, "mission3_comms_checkpoint_reached", False):
            return m3.start_mission3_comms_checkpoint(preserve_timer=False)
        if getattr(STATE, "mission3_breakout_checkpoint_reached", False):
            return m3.start_mission3_breakout_checkpoint(preserve_timer=False)
        return m3.start_mission3(preserve_timer=False)
    if _is_mission6_active() and not _in_walking_sim():
        # Deepest reached checkpoint wins (same rule as M5).  The train is a
        # scene, not a top-down stage, but its checkpoint resumes the scene.
        if getattr(STATE, "m6_train_checkpoint_reached", False):
            return start_mission6_train_checkpoint(preserve_timer=False)
        if getattr(STATE, "m6_rail_checkpoint", False):
            return start_mission6_rail_checkpoint(preserve_timer=False)
        if getattr(STATE, "m6_noman_checkpoint", False):
            return start_mission6_noman_checkpoint(preserve_timer=False)
        return start_mission6(preserve_timer=False)
    if _is_mission5_active() and not _in_walking_sim():
        # Deepest checkpoint wins: the tunnel escort is the hardest stretch
        # and Maru dying there must not cost the print-works raid as well.
        if getattr(STATE, "mission5_tunnel_checkpoint_reached", False):
            return start_mission5_tunnel_checkpoint(preserve_timer=False)
        if getattr(STATE, "mission5_printworks_checkpoint_reached", False):
            return start_mission5_printworks_checkpoint(preserve_timer=False)
        # W6: a death in the Lower Quarter must not replay the HQ walk.
        if getattr(STATE, "mission5_quarter_checkpoint_reached", False):
            return start_mission5_quarter_checkpoint(preserve_timer=False)
        return start_mission5_hq_checkpoint(preserve_timer=False)
    if _is_mission4_active() and not _in_walking_sim():
        if getattr(STATE, "mission4_tower_checkpoint_reached", False):
            return start_mission4_tower_checkpoint(preserve_timer=False)
        if getattr(STATE, "mission4_station_checkpoint_reached", False):
            return start_mission4_station_checkpoint(preserve_timer=False)
        return m4.start_m4(preserve_timer=False)
    return m1.start_mission(preserve_timer=False)


def _in_walking_sim():
    """Returns True if the player is currently in the walking sim transition.

    The walking sim (acaristan.game_state == "WALK") sits between Mission 1
    and Mission 2. It doesn't reset STATE.active_mission, so we can't use
    active_mission alone to decide what to restart - we have to check the
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
    # RPE6 Phase 5: the per-mission legacy update is the SIM authority. It runs as the
    # scheduler's ``legacy_mission_update`` system (order 0): roster sync in PRE before it,
    # other SIM systems around it by order, despawn flush in POST after it.
    if not _gw.installed():
        _gw.install(STATE)

    def _mission_update():
        if _is_mission0_active():
            return m0.game_update(keys)
        if _is_mission5_active():
            return m5.game_update(keys)
        if _is_mission6_active():
            return m6.game_update(keys)
        if _is_mission4_active():
            return m4.game_update(keys)
        if _is_mission3_active():
            return m3.game_update(keys)
        if _is_mission2_active():
            return m2.game_update(keys)
        return m1.game_update(keys)

    return _gw.step(_mission_update)


def _active_mission_tag():
    if _is_mission0_active():
        return "m0"
    if _is_mission5_active():
        return "m5"
    if _is_mission6_active():
        return "m6"
    if _is_mission4_active():
        return "m4"
    if _is_mission3_active():
        return "m3"
    if _is_mission2_active():
        return "m2"
    return "m1"


def game_draw(fcx, fcy):
    # RPE6 Phase 6: the gameplay frame goes through the render queue. The legacy mission
    # painter is ONE CustomDraw on the entities layer (§6.6 migration step 1); RENDER_SUBMIT
    # systems add drawables around it; the queue flushes to the screen in layer order and
    # records the custom-draw count the D6 gate ratchets down.
    if not _gr.installed():
        _gr.install(_cfg.WIDTH, _cfg.HEIGHT)
    if not _gw.installed():
        _gw.install(STATE)
    hook = _gw.render_submit
    if _is_mission6_active():
        _gr.frame(_cfg.screen, fcx, fcy, submitter=lambda q, x, y: m6.game_draw(x, y), name="m6.game_draw", submit_hook=hook)
        return None
    if _is_mission5_active():
        # M5 submits its own drawables (Phase 6 peel-off); the facade attribute is looked up at call time.
        _gr.frame(_cfg.screen, fcx, fcy, submitter=lambda q, x, y: m5.game_draw(x, y), name="m5.game_draw",
                  submit_hook=hook)
        return None
    result = []

    def _mission_draw(surface, cam_x, cam_y):
        if _is_mission0_active():
            result.append(m0.game_draw(fcx, fcy))
        elif _is_mission4_active():
            result.append(m4.game_draw(fcx, fcy))
        elif _is_mission3_active():
            result.append(m3.game_draw(fcx, fcy))
        elif _is_mission2_active():
            result.append(m2.game_draw(fcx, fcy))
        else:
            result.append(m1.game_draw(fcx, fcy))

    _gr.frame(_cfg.screen, fcx, fcy, _mission_draw, name=_active_mission_tag() + ".game_draw", submit_hook=hook)
    return result[0] if result else None


def handle_interact():
    if _is_mission5_active():
        return m5.handle_interact()
    if _is_mission6_active():
        return m6.handle_interact()
    if _is_mission4_active():
        return m4.handle_interact()
    if _is_mission3_active():
        # M3: E key at the drain triggers the crafting minigame (if the player
        # has a chair_leg and hasn't sharpened it yet).
        from missions import m3
        return m3.handle_interact()
    if _is_mission2_active():
        return m2.handle_interact()
    return interactions.handle_interact()

def debug_jump_to_exfil():
    if _is_mission5_active():
        # No debug jump for M5 - linear stage ladder, use the
        # --dev-mission5-* flags or `set_stage` instead.
        return
    if _is_mission4_active():
        # No debug jump for M4 - linear stage chain, use the console
        # `set_stage` dev path or the --dev-mission4-* flags instead.
        return
    if _is_mission3_active():
        # No debug jump for M3 - it's a linear dialogue m1.
        return
    if _is_mission2_active():
        return m2.debug_jump_to_evidence()
    return m1.debug_jump_to_exfil()


class _GameCoreModule(types.ModuleType):
    """Proxy module - routes old game_core globals to new modules/STATE."""

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
    "start_mission0": start_mission0,
    "start_mission": start_mission,
    "start_mission2": start_mission2,
    "start_mission2_sniper": start_mission2_sniper,
    "start_mission2_checkpoint": start_mission2_checkpoint,
    "start_mission3": start_mission3,
    "start_mission3_breakout_checkpoint": start_mission3_breakout_checkpoint,
    "start_mission3_comms_checkpoint": start_mission3_comms_checkpoint,
    "start_mission3_archives_checkpoint": start_mission3_archives_checkpoint,
    "start_mission3_kill_order_checkpoint": start_mission3_kill_order_checkpoint,
    "start_mission3_broadcast_checkpoint": start_mission3_broadcast_checkpoint,
    "start_mission4": start_mission4,
    "start_mission4_station_checkpoint": start_mission4_station_checkpoint,
    "start_mission4_tower_checkpoint": start_mission4_tower_checkpoint,
    "start_mission5": start_mission5,
    "start_mission5_hq_checkpoint": start_mission5_hq_checkpoint,
    "start_mission5_quarter_checkpoint": start_mission5_quarter_checkpoint,
    "start_mission5_printworks_checkpoint": start_mission5_printworks_checkpoint,
    "start_mission5_tunnel_checkpoint": start_mission5_tunnel_checkpoint,
    "start_mission6": start_mission6,
    "start_mission6_customs_checkpoint": start_mission6_customs_checkpoint,
    "start_mission6_noman_checkpoint": start_mission6_noman_checkpoint,
    "start_mission6_rail_checkpoint": start_mission6_rail_checkpoint,
    "start_mission6_train_checkpoint": start_mission6_train_checkpoint,
    "restart_current_mission": restart_current_mission,
    "game_update": game_update,
    "game_draw": game_draw,
    "handle_interact": handle_interact,
    "debug_jump_to_exfil": debug_jump_to_exfil,
})


def _fresh_audio(fn):
    """Every mission (re)start / checkpoint / dev jump begins in silence:
    stop the previous scene's VO, screams, loops and scheduled cues."""
    def wrapped(*a, **kw):
        try:
            from core.config import audio as _audio
            _audio.hard_stop()
        except Exception:
            pass
        return fn(*a, **kw)
    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = fn.__doc__
    return wrapped


for _n in list(_proxy.__dict__):
    if _n.startswith("start_mission") or _n == "restart_current_mission":
        _proxy.__dict__[_n] = _fresh_audio(_proxy.__dict__[_n])

sys.modules[__name__] = _proxy
