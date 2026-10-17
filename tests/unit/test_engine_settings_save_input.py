"""engine.settings / engine.save / engine.input kernels (RPE6 Phase 9)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from engine.input import ActionMap  # noqa: E402
from engine.save import canonical, dumps, loads, statehash  # noqa: E402
from engine.settings import BOOL, ENUM, FLOAT, INT, STR, Field, Settings, env_layer, resolve  # noqa: E402

SCHEMA = [Field("master_volume", INT, 80, "audio", 0, 100),
          Field("subtitles", BOOL, True, "gameplay"),
          Field("shake_scale", INT, 100, "accessibility", 0, 100),
          Field("text_speed", ENUM, 1, "accessibility", values=(0, 1, 2)),
          Field("brightness", FLOAT, 1.0, "video", 0.5, 1.5),
          Field("player_name", STR, "", "multiplayer")]


class SettingsTests(unittest.TestCase):
    def test_layering_and_coercion(self):
        values, problems = resolve(SCHEMA, {"master_volume": 30, "mystery": 1},
                                   {"master_volume": "loud", "shake_scale": 250})
        self.assertEqual(values["master_volume"], 80)      # invalid in top layer -> default (legacy rule)
        self.assertEqual(values["shake_scale"], 100)       # clamped to range
        self.assertEqual(values["mystery"], 1)             # unknown keys preserved
        self.assertTrue(problems)

    def test_env_layer(self):
        env = env_layer(SCHEMA, {"ACARISTAN_SHAKE_SCALE": "25", "ACARISTAN_SUBTITLES": "off",
                                 "ACARISTAN_BRIGHTNESS": "1.2", "OTHER": "x"})
        self.assertEqual(env, {"shake_scale": 25, "subtitles": False, "brightness": 1.2})

    def test_live_change_notification(self):
        s = Settings(SCHEMA, {"shake_scale": 100})
        seen = []
        s.subscribe(lambda n, o, v: seen.append((n, o, v)))
        self.assertTrue(s.set("shake_scale", 40))
        self.assertFalse(s.set("shake_scale", "banana"))
        s.set("shake_scale", 40)                            # no effective change
        self.assertEqual(seen, [("shake_scale", 100, 40)])


class SaveTests(unittest.TestCase):
    def test_statehash_quantises_and_sorts(self):
        a = {"enemies": [{"x": 10.00001, "hp": 3}], "frame": 7}
        b = {"frame": 7, "enemies": [{"hp": 3, "x": 10.00002}]}
        self.assertEqual(statehash(a), statehash(b))
        self.assertNotEqual(statehash(a), statehash({"frame": 8, "enemies": [{"hp": 3, "x": 10.0}]}))
        self.assertEqual(canonical({"b": (1, 2)}), {"b": [1, 2]})   # tuples hash like lists
        self.assertEqual(canonical({"z": {2, 1}}), {"z": [1, 2]})   # sets sort canonically

    def test_snapshot_round_trip(self):
        snap = {"schema": "ae.save/1", "id": "m5.checkpoint.print", "frame": 42,
                "mission": "m5", "vars": {"m5_stage": "print"}, "world": {},
                "rng": {"legacy": [3, [1, 2], None]}, "clock": {"frame": 42}}
        self.assertEqual(loads(dumps(snap)), snap)
        self.assertEqual(dumps(snap), dumps(dict(reversed(list(snap.items())))))


class InputTests(unittest.TestCase):
    def test_identity_by_default(self):
        m = ActionMap()
        self.assertEqual(m.remap({"w", "x"}), {"w", "x"})
        self.assertEqual(m.to_bindings(), {})

    def test_rebinding_and_gamepad(self):
        m = ActionMap({"move_up": {"key": "up"}})
        self.assertEqual(m.remap({"up"}), {"up", "w"})
        self.assertTrue(m.down("move_up", {"up", "w"}))
        self.assertEqual(m.to_bindings(), {"move_up": {"key": "up"}})
        pad = m.pad_down([0.0, -0.9], [1])
        self.assertIn("w", pad)                             # axis up
        self.assertIn("e", pad)                             # button 0 = interact


if __name__ == "__main__":
    unittest.main()


class SaveAdapterTests(unittest.TestCase):
    def test_clean_unclean_round_trip(self):
        from game.save_adapter import _clean, _unclean
        v = {"pos": (3, 4), "tags": {"a", "b"}, "items": [(1, 2), {"x": (5,)}], "n": None}
        back = _unclean(_clean(v))
        self.assertEqual(back, v)
        self.assertIsInstance(back["pos"], tuple)
        self.assertIsInstance(back["tags"], set)

    def test_set_attr_does_not_materialise_class_default(self):
        from game.save_adapter import _set_attr

        class Thing:
            speed = 2.0

        t = Thing()
        _set_attr(t, "speed", 2.0)
        self.assertNotIn("speed", vars(t))      # class default: left alone
        _set_attr(t, "speed", 3.0)
        self.assertEqual(t.speed, 3.0)          # real change: written
        _set_attr(t, "speed", 2.0)
        self.assertEqual(t.speed, 2.0)          # instance carries it: reset


class InputAdapterTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        from game import input_adapter
        self.ia = input_adapter
        self.ia.load_bindings(None)

    def tearDown(self):
        self.ia.load_bindings(None)

    class _Fake:
        def __init__(self, down):
            self.down = set(down)

        def __getitem__(self, code):
            return code in self.down

        def __len__(self):
            return 512

    def test_identity_at_defaults(self):
        fake = self._Fake({pygame.K_w})
        self.assertIs(self.ia.apply(fake), fake)   # untouched snapshot object

    def test_remap_forces_canonical(self):
        self.ia.set_binding("move_up", "t")
        wrapped = self.ia.apply(self._Fake({pygame.K_t}))
        self.assertTrue(wrapped[pygame.K_w])       # canonical reads down
        self.assertTrue(wrapped[pygame.K_t])       # physical still reads down
        self.assertEqual(self.ia.bindings_dict(), {"move_up": {"key": "t"}})
        self.ia.load_bindings({"move_up": {"key": "t"}})   # persistence round-trip
        self.assertEqual(self.ia.display_bindings()["move_up"], "t")
