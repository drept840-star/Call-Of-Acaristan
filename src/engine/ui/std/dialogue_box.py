"""DialogueBox: the shared cutscene dialogue box (A6.11, Phase 4).

Extracted verbatim from ``cutscenes/engine.py``, which keeps the A-009 shims
``draw_dialogue_box`` / ``reset_dialogue_slide``. Everything the box draws with
comes from the injected ``Theme`` (fonts, palette, viewport, speaker accents -
the engine never imports game config, rule R5); the slide-up animation state
lives here as ``_dialogue_box_slide`` so the cutscenes facade's live view and
the legacy name keep reading the same value.
"""
from __future__ import annotations

import math

import pygame

from engine.core import now_ms as _now_ms
from engine.text import T

__all__ = ["draw", "reset_slide", "slide"]

# Slide-up offset in pixels (0..12): the box eases up while the typewriter
# starts (char_idx < 8) and settles back down afterwards. Legacy name kept
# because ``cutscenes._dialogue_box_slide`` is a live view of this global.
_dialogue_box_slide = 0.0


def reset_slide() -> None:
    """Snap the slide animation back to its start-of-line offset (scene entry)."""
    global _dialogue_box_slide
    _dialogue_box_slide = 0.0


def slide() -> float:
    """Current slide offset in pixels (0..12)."""
    return _dialogue_box_slide


def draw(surface, theme, speaker, text, char_idx, total_len, can_continue=True,
         show_speaker=False):
    """Cutscene dialogue box shared by every scene (incl. the M5 finale).

    ``can_continue=None`` draws the box with no prompt: timeline-owned lines
    (M5 shadow finale) auto-advance with ESC/ENTER controls, so neither
    "SPACE TO CONTINUE" nor "ANALYZING FILE..." applies.

    ``show_speaker`` is opt-in for cinematic sequences that need an explicit
    name tab (the M5 finale); the established cutscene box remains unchanged
    for all other callers.
    """
    global _dialogue_box_slide
    font_dialogue = theme.font_dialogue
    font_speaker = theme.font_speaker
    font_terminal_small = theme.font_terminal_small
    width = theme.width
    height = theme.height
    letter_h = theme.letter_h
    c_white = theme.c_white
    visible_text = text[:char_idx]
    paragraphs = visible_text.split("\n")
    box_w = width - 120
    inner_w = box_w - 52
    final_lines = []
    for para in paragraphs:
        if not para.strip():
            final_lines.append("")
            continue
        words = para.split(" ")
        line = ""
        for word in words:
            test = line + word + " "
            if font_dialogue.size(test)[0] < inner_w:
                line = test
            else:
                if line:
                    final_lines.append(line.rstrip())
                while word and font_dialogue.size(word)[0] > inner_w:
                    word = word[:-1]
                line = word + " "
        if line:
            final_lines.append(line.rstrip())
    full_paragraphs = text.split("\n")
    full_lines = []
    for para in full_paragraphs:
        if not para.strip():
            full_lines.append("")
            continue
        words = para.split(" ")
        line = ""
        for word in words:
            test = line + word + " "
            if font_dialogue.size(test)[0] < inner_w:
                line = test
            else:
                if line:
                    full_lines.append(line.rstrip())
                line = word + " "
        if line:
            full_lines.append(line.rstrip())
    num_lines = max(1, len(full_lines))
    line_h = 30
    # No speaker-name header strip (polish pass T8): the box hugs the text.
    # Who is talking still reads from the SPEAKER_COLORS accent bar. The
    # opt-in name tab hangs off the top border, so it needs the same head
    # room the M5 dialogue panel gives it - otherwise the first line prints
    # through the tab.
    show_name = bool(show_speaker and speaker.strip())
    top_pad = font_speaker.get_height() // 2 + 5 if show_name else 14
    bottom_pad = 24
    box_h = top_pad + num_lines * line_h + bottom_pad
    box_y = height - letter_h - box_h - 14
    box_x = 60
    box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
    # ── Slide up animation ──
    if char_idx < 8:
        _dialogue_box_slide = min(12.0, _dialogue_box_slide + 1.0)
    else:
        _dialogue_box_slide = max(0.0, _dialogue_box_slide - 1.0)
    slide_offset = int(_dialogue_box_slide)
    panel = pygame.Surface((box_rect.width, box_rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, (0, 0, 0, 205), panel.get_rect())
    accent = theme.speaker_accent(speaker)
    pygame.draw.rect(panel, (*accent, 255), (0, 0, 4, box_rect.height))
    surface.blit(panel, (box_rect.x, box_rect.y + slide_offset))
    if show_name:
        name = font_speaker.render(speaker, True, (14, 14, 18))
        tab = pygame.Rect(
            box_rect.x + 22,
            box_rect.y - name.get_height() // 2 - 2 + slide_offset,
            name.get_width() + 22,
            name.get_height() + 6,
        )
        pygame.draw.rect(surface, accent, tab, border_radius=4)
        surface.blit(name, (tab.x + 11, tab.y + 3))
    for i, line in enumerate(final_lines[:num_lines]):
        if line:
            line_alpha = min(255, max(0, char_idx * 8 - i * 40))
            surf = font_dialogue.render(line, True, c_white)
            surf.set_alpha(line_alpha)
            surface.blit(
                surf, (box_rect.x + 24, box_rect.y + top_pad + i * line_h + slide_offset)
            )
    if char_idx >= total_len:
        if can_continue is None:
            return
        continue_alpha = int(140 + math.sin(_now_ms() * 0.004) * 60)
        dim = (accent[0] // 2, accent[1] // 2, accent[2] // 2)
        # NOTE: the ▼/◆ icons are drawn procedurally, never rendered as text -
        # the bundled IBM Plex Mono build lacks those codepoints, so they
        # showed up as grey tofu boxes on machines without a fallback font.
        prompt_text = T("cutscene.space_to_continue") if can_continue else T("cutscene.analyzing_file")
        cont = font_terminal_small.render(
            prompt_text,
            True,
            dim,
        )
        cont.set_alpha(continue_alpha)
        cont_x = box_rect.right - cont.get_width() - 22
        cont_y = box_rect.bottom - 20 + slide_offset
        surface.blit(cont, (cont_x, cont_y))
        icon = pygame.Surface((12, 12), pygame.SRCALPHA)
        if can_continue:
            pygame.draw.polygon(icon, (*dim, 255), [(2, 3), (10, 3), (6, 9)])
        else:
            pygame.draw.polygon(icon, (*dim, 255), [(6, 1), (11, 6), (6, 11), (1, 6)])
        icon.set_alpha(continue_alpha)
        surface.blit(icon, (cont_x - 18, cont_y - 1))
