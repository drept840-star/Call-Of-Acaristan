"""Mission 8 - per-frame update, dispatched by stage: a 3D scene, or a beat."""
from core.state import STATE

from .meta import FIGHT_STAGES, STAGE_CHASE, STAGE_FLIGHT, STAGE_KILL, STAGE_MANSION, STAGE_RIDGE
from .duty import flight3d as _flight
from .duty import mansion3d as _mansion
from .duty import ridge3d as _ridge
from .revenge import beats as _beats
from .revenge import chase3d as _chase
from .revenge import kill3d as _kill
from .revenge import trap3d as _trap


def _scene_for(stage):
    if stage in FIGHT_STAGES:
        return _trap
    if stage == STAGE_KILL:
        return _kill
    if stage == STAGE_CHASE:
        return _chase
    if stage == STAGE_MANSION:
        return _mansion
    if stage == STAGE_FLIGHT:
        return _flight
    if stage == STAGE_RIDGE:
        return _ridge
    return None


def game_update(keys=None):
    stage = getattr(STATE, "mission8_stage", "")
    sc = _scene_for(stage)
    if sc is not None:
        if sc.active():
            try:
                sc.update(keys)
            except Exception:
                import traceback
                traceback.print_exc()
                sc.force_finish("fallback")
        return (0, 0)
    if _beats.current() != stage:
        return (0, 0)                    # a film owns this stage; app.py is starting it
    dt = float(getattr(STATE, "dt", 1.0 / 60.0) or 1.0 / 60.0)
    return _beats.update(keys, min(dt, 0.05))
