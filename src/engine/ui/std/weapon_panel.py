"""WeaponPanel (MagIcons) - the 84px magazine-icon weapon panel.

Body moved verbatim from the M4 ``_draw_m4_hud`` / M5 ``_draw_hud`` weapon
blocks, which were identical. The mission supplies the data (``WeaponInfo``)
and the magazine painter (each mission bakes its own ``mag_icon`` sprite set and
keeps its procedural painter as the fallback), the engine supplies the layout.

The reload-bar duration per weapon is part of the panel's drawing, not of the
mission: it moved with the body (``RELOAD_MS``; anything unknown = pistol).
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

from engine.text import T

from ..theme import Theme

__all__ = ["RELOAD_MS", "WeaponInfo", "draw"]

PANEL_W = 246
PANEL_H = 84
RELOAD_MS = {"k9_smg": 72, "os12": 90}      # anything else (sidearm) = 60


@dataclass
class WeaponInfo:
    """The panel's data: what the HUD needs to know about the held weapon."""
    cw: str = "pistol"
    label: str = "SIDEARM"
    caliber: str = "9MM"
    kind: str = "box"
    ammo: int = 0
    mag: int = 1
    spares: int = 0
    reloading: bool = False
    reload_timer: int = 0

    @classmethod
    def from_state(cls, state) -> "WeaponInfo":
        """Read the classic ``STATE`` weapon attributes (same rules as both missions)."""
        cw = getattr(state, "current_weapon", "pistol")
        if cw == "k9_smg":
            ammo, mag, spares = (getattr(state, "k9_ammo_in_mag", 0),
                                 getattr(state, "k9_mag_size", 24),
                                 getattr(state, "k9_spare_mags", 0))
            label, caliber, kind = "K-9 SMG", "9MM-S", "stick"
        elif cw == "os12":
            ammo, mag, spares = (getattr(state, "os12_ammo_in_mag", 0),
                                 getattr(state, "os12_mag_size", 25),
                                 getattr(state, "os12_spare_mags", 0))
            label, caliber, kind = "OS-12", "12GA", "stick"
        else:
            ammo, mag, spares = state.ammo_in_mag, state.mag_size, state.spare_mags
            label, caliber, kind = "SIDEARM", "9MM", "box"
        return cls(cw=cw, label=label, caliber=caliber, kind=kind, ammo=ammo, mag=mag,
                   spares=spares, reloading=bool(getattr(state, "is_reloading", False)),
                   reload_timer=getattr(state, "reload_timer", 0))


def draw(surface: pygame.Surface, theme: Theme, info: WeaponInfo, *, panel_bg, mag_icon,
         x: int = 24, y: int | None = None, panel_h: int = PANEL_H,
         reload_label_dx: int = 0) -> None:
    """Draw the weapon panel; ``mag_icon(surface, mx, my, kind, rounds, cap, active)`` paints one mag.

    ``panel_h`` and ``reload_label_dx`` exist for the M3 variant (92px firearm
    panel, "RELOADING" 2px right of M4/M5's); the defaults are the M4/M5 look.
    """
    panel_y = (y if y is not None else theme.height - 40) - panel_h - 2
    surface.blit(panel_bg(PANEL_W, panel_h), (x, panel_y))
    pygame.draw.line(surface, theme.c_krap_blue, (x, panel_y), (x, panel_y + panel_h), 3)
    ammo_x, ammo_y = x + 6, panel_y + 6
    for i in range(4):
        is_active = i == 0
        rounds = info.ammo if is_active else (info.mag if info.spares >= i else 0)
        mag_icon(surface, ammo_x + 8 + i * 34, ammo_y + 8, info.kind, rounds, info.mag, is_active)
    tc = theme.c_terminal if info.ammo > 0 else (220, 60, 60)
    tx = ammo_x + 154
    surface.blit(theme.font_terminal_small.render(info.label, True, (150, 210, 190)),
                 (tx, ammo_y - 6))
    surface.blit(theme.font_terminal_small.render("{}/{}".format(int(info.ammo), int(info.mag)),
                                                  True, tc), (tx, ammo_y + 10))
    surface.blit(theme.font_terminal_small.render(info.caliber, True, (100, 130, 120)),
                 (tx, ammo_y + 28))
    surface.blit(theme.font_terminal_small.render(T("hud.mags", n=int(info.spares)), True,
                                                  (140, 150, 130)), (tx, ammo_y + 46))
    if info.reloading:
        bar_x, bar_y = ammo_x + 148, ammo_y + 64
        dur = RELOAD_MS.get(info.cw, 60)
        prog = 1.0 - info.reload_timer / dur if info.reload_timer > 0 else 0.0
        prog = max(0.0, min(1.0, prog))
        pygame.draw.rect(surface, (50, 50, 50), (bar_x, bar_y, 80, 8), border_radius=2)
        pygame.draw.rect(surface, (220, 160, 40), (bar_x, bar_y, int(80 * prog), 8),
                         border_radius=2)
        surface.blit(theme.font_terminal_small.render(T("hud.reloading"), True, (220, 160, 40)),
                     (bar_x + reload_label_dx, bar_y + 12))
