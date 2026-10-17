"""engine.ui Phase 4: Theme + the standard widgets, drawn headless.

The widgets are covered end-to-end by the golden (373 shots) and loop (7
segments) gates; these tests prove the engine-side contract: no game imports, a
Theme carries the fonts, and every widget draws onto a plain surface.
"""
import unittest

from tests.unit import _helpers  # noqa: F401  (sys.path + headless env)

import pygame

from engine.text import load_face
from engine.ui import Theme
from engine.ui import (bottle_hud, crosshair, health_bar, hostiles, minimap,
                       objective_banner, prompt, weapon_panel)   # public surface


def _theme():
    f = load_face("plex_regular", 14)
    return Theme(size=(1000, 700), font_prompt=f, font_terminal=f, font_terminal_small=f)


def _panel_bg(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


class PromptTests(unittest.TestCase):
    """The world prompt tag draws headless and keeps M3's viewport clamp."""

    def test_draw_and_clamp(self):
        f = load_face("plex_regular", 14)
        blank = pygame.Surface((1000, 700))
        surf = pygame.Surface((1000, 700))
        prompt.draw(surf, 500, 400, "PRESS [E]", (255, 255, 255), font=f,
                    fallback_font=f)
        self.assertNotEqual(pygame.image.tobytes(surf, "RGB"),
                            pygame.image.tobytes(blank, "RGB"))
        # y_off pushes the tag off-screen; the clamp brings it back inside.
        low = pygame.Surface((1000, 700))
        prompt.draw(low, 500, 20, "PRESS [E]", (255, 255, 255), font=f, y_off=-400)
        self.assertNotEqual(pygame.image.tobytes(low, "RGB"),
                            pygame.image.tobytes(blank, "RGB"))
        # clamp=False keeps the off-screen position (M5's older behaviour).
        free = pygame.Surface((1000, 700))
        prompt.draw(free, 500, 20, "PRESS [E]", (255, 255, 255), font=f,
                    y_off=-400, clamp=False)
        self.assertEqual(pygame.image.tobytes(free, "RGB"),
                         pygame.image.tobytes(blank, "RGB"))


class ThemeTests(unittest.TestCase):
    def test_geometry_defaults(self):
        t = Theme()
        self.assertEqual((t.width, t.height), (1000, 700))
        self.assertEqual(t.letter_h, 80)


class WidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.theme = _theme()

    def setUp(self):
        self.surf = pygame.Surface((1000, 700), pygame.SRCALPHA)

    def test_objective_banner_draws_and_clamps(self):
        objective_banner.draw(self.surf, "north-east of the press hall", self.theme)
        objective_banner.draw(self.surf, "X" * 400, self.theme)          # single long token
        objective_banner.draw(self.surf, " ".join(["word"] * 200), self.theme)  # clamps to 2 lines

    def test_health_bar_ratio_and_zero_max(self):
        health_bar.draw(self.surf, self.theme, 100, 100, panel_bg=_panel_bg)
        health_bar.draw(self.surf, self.theme, 0, 0, panel_bg=_panel_bg)  # no division by zero

    def test_hostiles_box(self):
        hostiles.draw(self.surf, self.theme, 3)

    def test_weapon_info_gather_rules(self):
        class S:  # duck-typed STATE
            current_weapon = "k9_smg"
            k9_ammo_in_mag = 7
            k9_mag_size = 24
            k9_spare_mags = 2
            is_reloading = True
            reload_timer = 36

        info = weapon_panel.WeaponInfo.from_state(S())
        self.assertEqual((info.label, info.kind, info.ammo, info.mag, info.spares),
                         ("K-9 SMG", "stick", 7, 24, 2))
        self.assertTrue(info.reloading)

        class P:
            current_weapon = "pistol"
            ammo_in_mag, mag_size, spare_mags = 5, 12, 1

        p = weapon_panel.WeaponInfo.from_state(P())
        self.assertEqual((p.label, p.kind), ("SIDEARM", "box"))

    def test_weapon_panel_draws_four_mags_and_reload_bar(self):
        calls = []

        def mag_icon(surface, mx, my, kind, rounds, cap, is_active):
            calls.append((mx, my, kind, rounds, cap, is_active))

        info = weapon_panel.WeaponInfo(cw="os12", label="OS-12", caliber="12GA", kind="stick",
                                       ammo=5, mag=25, spares=1, reloading=True, reload_timer=45)
        weapon_panel.draw(self.surf, self.theme, info, panel_bg=_panel_bg, mag_icon=mag_icon)
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0][3], 5)     # active mag shows the chambered ammo
        self.assertEqual(calls[1][3], 25)    # one spare => second mag full
        self.assertEqual(calls[2][3], 0)     # no second spare
        self.assertEqual([c[5] for c in calls], [True, False, False, False])

    def test_crosshair_shapes_and_palette(self):
        crosshair.draw(self.surf, 100, 100, size=6, color=(255, 255, 255), kick=9)
        crosshair.draw_combat(self.surf, 100, 100, size=6, color=(255, 128, 0))
        crosshair.draw(self.surf, 100, 100, size=1, color=(255, 255, 255))  # clamps to 3
        self.assertEqual(crosshair.color_for("protanopia", default=(1, 2, 3)),
                         (90, 180, 255))
        self.assertEqual(crosshair.color_for("none", default=(1, 2, 3)), (1, 2, 3))

    def test_bottle_strip_draws_cap_icons_and_fills(self):
        calls = []

        def icon(surface, x, y, filled):
            calls.append((x, y, filled))

        bottle_hud.draw(self.surf, self.theme, 2, panel_bg=_panel_bg, icon=icon,
                        x=24, y=100, width=246, cap=4)
        self.assertEqual(len(calls), 4)
        self.assertEqual([c[2] for c in calls], [True, True, False, False])
        self.assertEqual(calls[0][:2], (24 + 18, 100 + 23))

    def test_minimap_constructs_and_draws_playerless(self):
        mm = minimap.MiniMap(["CCCC", "C..C", "CCCC"], palette="m1", theme=self.theme)
        mm.draw(self.surf, None, [], 0, 0)   # player-less path is guarded


if __name__ == "__main__":
    unittest.main()
