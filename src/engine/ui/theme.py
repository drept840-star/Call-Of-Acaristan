"""Theme: the fonts, colours and viewport metrics widgets draw with (§6.12).

The engine never imports game config (R5): the game builds one ``Theme`` from
``core.config`` (see the A-009 shim in ``src/ui/hud.py``) and hands it to every
widget. The defaults mirror the game palette at Phase 4 so a widget can be drawn
in isolation (unit tests, tools); the game path always passes the live values.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pygame

__all__ = ["Theme"]

_PANELS: dict = {}


@dataclass
class Theme:
    # Viewport metrics (design space; the game always runs 1000x700).
    size: tuple[int, int] = (1000, 700)
    letter_h: int = 80          # letterbox height for top-anchored banners
    tile_size: int = 64

    # Fonts (pygame.font.Font objects, wired by the game; None in a bare theme).
    font_prompt: object | None = None
    font_terminal: object | None = None
    font_terminal_small: object | None = None
    font_dialogue: object | None = None
    font_speaker: object | None = None
    font_title: object | None = None
    font_location: object | None = None
    font_location_sub: object | None = None
    font_btn: object | None = None

    # Palette (= core.config's values at Phase 4; a bare theme still draws).
    c_white: tuple[int, int, int] = (240, 240, 240)
    c_grey: tuple[int, int, int] = (150, 150, 150)
    c_orange: tuple[int, int, int] = (255, 120, 0)
    c_terminal: tuple[int, int, int] = (50, 255, 150)
    c_krap_blue: tuple[int, int, int] = (35, 65, 110)
    c_krap_uniform: tuple[int, int, int] = (55, 65, 80)

    # Tactical HUD skin: slate panels with a 1px steel edge (the minimap frame),
    # phosphor text and amber accents.
    c_amber: tuple[int, int, int] = (230, 159, 58)
    c_panel: tuple[int, int, int] = (16, 19, 22)
    c_panel_alpha: int = 200
    c_edge: tuple[int, int, int] = (58, 68, 76)

    # Speaker name -> accent colour (game: core.config.SPEAKER_COLORS). Empty
    # in a bare theme; ``speaker_accent`` falls back to the orange accent.
    speaker_colors: dict = field(default_factory=dict)

    # A theme is extended by assignment (``theme.extra = ...``) rather than by
    # subclassing, so widgets never need to know which build they run under.
    extra: dict = field(default_factory=dict)

    @property
    def width(self) -> int:
        return self.size[0]

    @property
    def height(self) -> int:
        return self.size[1]

    def panel(self, w: int, h: int, *, fade: int = 0, stripe=None,
              alpha: int | None = None) -> pygame.Surface:
        """Cached HUD panel: slate fill, 1px edge; ``fade`` px on the right ease
        out to clear (no right edge then); ``stripe`` is a 3px left accent."""
        a = self.c_panel_alpha if alpha is None else alpha
        key = (w, h, fade, stripe and tuple(stripe), a, tuple(self.c_panel), tuple(self.c_edge))
        s = _PANELS.get(key)
        if s is None:
            if len(_PANELS) > 64:
                _PANELS.clear()
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            s.fill(self.c_panel + (a,))
            edge = self.c_edge + (255,)
            pygame.draw.line(s, edge, (0, 0), (w - 1, 0))
            pygame.draw.line(s, edge, (0, h - 1), (w - 1, h - 1))
            pygame.draw.line(s, edge, (0, 0), (0, h - 1))
            if not fade:
                pygame.draw.line(s, edge, (w - 1, 0), (w - 1, h - 1))
            if stripe is not None:
                s.fill(tuple(stripe) + (255,), (0, 0, 3, h))
            if fade:
                fade = min(fade, w)
                alpha_px = pygame.surfarray.pixels_alpha(s)
                for i in range(fade):
                    col = w - fade + i
                    k = 1.0 - (i + 1) / float(fade)
                    alpha_px[col, :] = (alpha_px[col, :] * k).astype(alpha_px.dtype)
                del alpha_px
            _PANELS[key] = s
        return s

    def speaker_accent(self, name: str) -> tuple[int, int, int]:
        """Accent colour for ``name`` (case-insensitive), orange when unknown."""
        return self.speaker_colors.get((name or "").upper(), self.c_orange)
