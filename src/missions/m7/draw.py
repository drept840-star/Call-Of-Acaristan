"""Mission 7 - placeholder frame: title, stage label and the advance hint."""
import pygame

from core.config import HEIGHT, font_terminal, font_terminal_small
from core.state import STATE

from . import choice as _choice
from . import farmyard as _farmyard
from . import raid3d as _raid
from .meta import MISSION7_TITLE, STAGE_ARRIVAL, STAGE_CHOICE, STAGE_LABELS, STAGE_RAID


def game_draw(surface=None, cx=0, cy=0):
    target = surface or pygame.display.get_surface()
    if target is None:
        return
    target.fill((18, 20, 24))
    stage = getattr(STATE, "mission7_stage", "") or STAGE_ARRIVAL
    if stage in _farmyard.FARM_STAGES:
        _farmyard.draw(target)
        return
    if stage == STAGE_RAID and _raid.active():
        try:
            _raid.draw(target)
        except Exception:
            import traceback
            traceback.print_exc()
            _raid.force_finish("fallback")
        return
    if stage == STAGE_CHOICE:
        _choice.draw(target)
        return
    title = font_terminal.render("MISSION 7 - " + MISSION7_TITLE.upper(), True, (226, 214, 180))
    label = font_terminal.render(STAGE_LABELS.get(stage, stage.upper()), True, (150, 190, 110))
    hint = font_terminal_small.render("[ENTER] NEXT STAGE (PLACEHOLDER)", True, (180, 172, 150))
    target.blit(title, (40, 40))
    target.blit(label, (40, 80))
    target.blit(hint, (40, HEIGHT - 60))
