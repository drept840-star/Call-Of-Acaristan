"""engine.ui.std.dialogue_box (Phase 4): theme injection, slide ownership.

The pixels are covered by the golden gate (cutscene dialogue shots); these
tests pin the engine-side contract: the box draws from a bare ``Theme``, the
slide animation state belongs to the widget, and the speaker accent comes from
the theme (the engine never imports ``core.config``).
"""
from __future__ import annotations

import unittest

from tests.unit import _helpers  # noqa: F401  (sys.path + headless env)

import pygame

from engine.text import load_face
from engine.ui import Theme
from engine.ui import dialogue_box   # public surface


def _theme():
    f = load_face("plex_regular", 14)
    return Theme(size=(1000, 700), font_prompt=f, font_terminal=f,
                 font_terminal_small=f, font_dialogue=f, font_speaker=f,
                 speaker_colors={"VOLKOV": (120, 200, 255)})


class DialogueBoxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.theme = _theme()

    def setUp(self):
        self.surf = pygame.Surface((1000, 700), pygame.SRCALPHA)
        dialogue_box.reset_slide()

    def test_typing_full_and_prompt(self):
        text = "The Krap line holds the harbour.\nMove out before dawn."
        dialogue_box.draw(self.surf, self.theme, "VOLKOV", text, 0, len(text))
        dialogue_box.draw(self.surf, self.theme, "VOLKOV", text, 10, len(text))
        dialogue_box.draw(self.surf, self.theme, "VOLKOV", text, len(text), len(text))

    def test_no_prompt_variants(self):
        text = "Timeline line."
        dialogue_box.draw(self.surf, self.theme, "VOLKOV", text, len(text), len(text),
                          can_continue=None)          # no prompt at all
        dialogue_box.draw(self.surf, self.theme, "VOLKOV", text, len(text), len(text),
                          can_continue=False)         # "ANALYZING FILE..." + diamond

    def test_speaker_tab_and_unknown_speaker(self):
        text = "Name tab."
        dialogue_box.draw(self.surf, self.theme, "VOLKOV", text, len(text), len(text),
                          show_speaker=True)
        dialogue_box.draw(self.surf, self.theme, "ANONYMOUS", text, len(text), len(text),
                          show_speaker=True)          # accent falls back to c_orange
        dialogue_box.draw(self.surf, self.theme, "   ", text, len(text), len(text),
                          show_speaker=True)          # blank speaker draws no tab

    def test_long_token_and_paragraphs(self):
        text = "X" * 900 + "\n\nshort"
        dialogue_box.draw(self.surf, self.theme, "VOLKOV", text, len(text), len(text))

    def test_slide_state_owned_by_the_widget(self):
        self.assertEqual(dialogue_box.slide(), 0.0)
        dialogue_box.draw(self.surf, self.theme, "V", "hi", 0, 2)     # typing: +1
        self.assertEqual(dialogue_box.slide(), 1.0)
        self.assertEqual(dialogue_box.slide(), dialogue_box._dialogue_box_slide)
        dialogue_box.draw(self.surf, self.theme, "V", "hi", 8, 2)     # settled: -1
        self.assertEqual(dialogue_box.slide(), 0.0)
        dialogue_box._dialogue_box_slide = 12.0
        dialogue_box.draw(self.surf, self.theme, "V", "hi", 0, 2)
        self.assertEqual(dialogue_box.slide(), 12.0)                  # clamps at 12
        dialogue_box.reset_slide()
        self.assertEqual(dialogue_box.slide(), 0.0)


class ThemeAccentTests(unittest.TestCase):
    def test_speaker_accent_is_case_insensitive_with_orange_fallback(self):
        t = _theme()
        self.assertEqual(t.speaker_accent("volkov"), (120, 200, 255))
        self.assertEqual(t.speaker_accent("Volkov"), (120, 200, 255))
        self.assertEqual(t.speaker_accent("nobody"), t.c_orange)
        self.assertEqual(t.speaker_accent(""), t.c_orange)
        self.assertEqual(Theme().speaker_accent(None), Theme().c_orange)


if __name__ == "__main__":
    unittest.main()
