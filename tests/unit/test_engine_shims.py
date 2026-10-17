"""A-006 shims: the legacy paths re-export the engine implementations unchanged."""
from __future__ import annotations

import os
import unittest
import warnings

from tests.unit import _helpers  # noqa: F401  (sys.path + headless env)


class Shims(unittest.TestCase):
    def test_palette_constants_match_config(self):
        from core import config
        from engine import anim
        self.assertEqual(tuple(config.C_KRAP_UNIFORM), anim.KRAP_UNIFORM)
        self.assertEqual(tuple(config.C_KRAP_BLUE), anim.KRAP_BLUE)

    def test_shims_alias_the_engine_objects(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from core import artpack, lighting, render_util
            from cutscenes import figure_kit
            from entities import sprite_lib
        from engine import anim, assets, lighting as elighting, render2d
        self.assertIs(artpack.tile, assets.artpack.tile)
        self.assertIs(artpack.pose, assets.artpack.pose)
        self.assertIs(sprite_lib.get_sprite, assets.sprites.get_sprite)
        self.assertIs(figure_kit.draw_character, anim.draw_character)
        self.assertIs(figure_kit.SPECS, anim.SPECS)
        self.assertIs(figure_kit._REF_H, anim.REF_H)
        self.assertIs(lighting.LightBuffer, elighting.LightBuffer)
        self.assertIs(render_util.push_lamps, render2d.push_lamps)

    def test_legacy_signatures_bind_the_window(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from core import lighting, render_util
        from core import config
        from engine import render2d
        lb = lighting.buffer()
        self.assertIs(lb, lighting.buffer())
        self.assertEqual(lb.size, (config.WIDTH, config.HEIGHT))
        for args in ((-500, 10, 50, 50), (10, 10, 50, 50), (config.WIDTH + 100, 10, 5, 5), (10, config.HEIGHT + 90, 5, 5)):
            self.assertEqual(render_util.screen_visible(*args),
                             render2d.screen_visible(*args, viewport=(config.WIDTH, config.HEIGHT)))

    def test_resolver_is_bound_to_the_game_root(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from core import artpack
        from core import config
        self.assertEqual(os.path.normpath(artpack.path("x")),
                         os.path.normpath(config.resource_path("assets/art") + "/x.png"))
        self.assertTrue(artpack.path("x").endswith("x.png"))

    def test_dialogue_box_shim_follows_the_widget_state(self):
        """A-009: cutscenes keeps the names; engine.ui.std owns the slide state."""
        import cutscenes
        from engine.ui import dialogue_box
        self.assertTrue(callable(cutscenes.draw_dialogue_box))
        self.assertTrue(callable(cutscenes.reset_dialogue_slide))
        cutscenes.reset_dialogue_slide()
        try:
            dialogue_box._dialogue_box_slide = 5.0
            self.assertEqual(cutscenes._dialogue_box_slide, 5.0)
        finally:
            dialogue_box.reset_slide()
        self.assertEqual(cutscenes._dialogue_box_slide, 0.0)


if __name__ == "__main__":
    unittest.main()
