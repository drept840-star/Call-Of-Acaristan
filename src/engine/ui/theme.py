"""Theme: the fonts, colours and viewport metrics widgets draw with (§6.12).

The engine never imports game config (R5): the game builds one ``Theme`` from
``core.config`` (see the A-009 shim in ``src/ui/hud.py``) and hands it to every
widget. The defaults mirror the game palette at Phase 4 so a widget can be drawn
in isolation (unit tests, tools); the game path always passes the live values.
"""
from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["Theme"]


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

    def speaker_accent(self, name: str) -> tuple[int, int, int]:
        """Accent colour for ``name`` (case-insensitive), orange when unknown."""
        return self.speaker_colors.get((name or "").upper(), self.c_orange)
