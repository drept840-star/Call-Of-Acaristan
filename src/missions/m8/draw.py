"""Mission 8 - frame: a 3D scene, or the stage's 3D beat."""
import pygame

from core.state import STATE

from .systems import _scene_for
from .revenge import beats as _beats


def game_draw(surface=None, cx=0, cy=0):
    target = surface or pygame.display.get_surface()
    if target is None:
        return
    target.fill((18, 20, 24))
    stage = getattr(STATE, "mission8_stage", "")
    sc = _scene_for(stage)
    try:
        if sc is not None:
            if sc.active():
                sc.draw(target)
            return
        if _beats.current() == stage:
            _beats.draw(target)
    except Exception:
        import traceback
        traceback.print_exc()
        if sc is not None:
            sc.force_finish("fallback")
