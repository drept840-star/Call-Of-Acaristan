"""Mission 7 - per-frame update, dispatched by stage (placeholder stages: ENTER advances)."""
import pygame

from core.state import STATE

from . import choice as _choice
from . import farmyard as _farmyard
from . import flow as _flow
from . import raid3d as _raid
from .meta import STAGE_CHOICE, STAGE_RAID

_enter_held = False


def game_update(keys=None):
    global _enter_held
    stage = getattr(STATE, "mission7_stage", "")
    if stage in _farmyard.FARM_STAGES:
        return _farmyard.update(keys)
    if stage == STAGE_RAID and _raid.active():
        try:
            _raid.update(keys)
        except Exception:
            import traceback
            traceback.print_exc()
            _raid.force_finish("fallback")
        return (0, 0)
    if stage == STAGE_CHOICE:
        return _choice.update(keys)
    down = bool(keys is not None and keys[pygame.K_RETURN])
    if down and not _enter_held:
        _flow.advance_stage()
    _enter_held = down
    return (0, 0)
