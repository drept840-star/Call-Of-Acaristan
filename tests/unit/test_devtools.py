"""RPE6 Phase 10 (§6.19): debug overlay / inspector data builders + console commands."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game.devtools import DevTools, FrameSamples  # noqa: E402


class _E:
    def __init__(self, x, y, hp=10):
        self.hp = hp
        self.speed = 2.0
        self.rect = pygame.Rect(x, y, 32, 32)


class DevToolsTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        from core.state import STATE
        self.STATE = STATE
        self._saved = (STATE.enemies, STATE.player)
        self.dev = DevTools()

    def tearDown(self):
        self.STATE.enemies, self.STATE.player = self._saved

    def test_frame_samples_stats(self):
        f = FrameSamples(4)
        for ms in (16, 17, 85, 16):
            f.push(ms, 5, 10)
        st = f.stats()
        self.assertEqual(st["spikes"], 1)
        self.assertEqual(st["max"], 85.0)
        self.assertEqual(st["sim_avg"], 5.0)

    def test_pick_describe_set_field(self):
        e = _E(100, 100)
        self.STATE.enemies = [e]
        self.STATE.player = None
        self.assertIs(self.dev.pick(110, 110), e)
        self.assertIsNone(self.dev.pick(900, 600))
        self.dev.selected = e
        self.assertEqual(self.dev.set_field("hp", "42"), "set hp = 42 (was 10)")
        self.assertEqual(e.hp, 42)
        self.assertIn("no field", self.dev.set_field("nope", "1"))

    def test_console_new_commands(self):
        from core.console import Console
        c = Console()
        c.bind("scene", lambda name: f"scene -> {name}")
        c.execute_command("scene GAME")
        self.assertTrue(any("scene -> GAME" in h for h in c.history))
        c.execute_command("seed 7")
        self.assertTrue(any("seed set to 7" in h for h in c.history))
        c.execute_command("events")
        self.assertTrue(any("no bus bound" in h for h in c.history))


if __name__ == "__main__":
    unittest.main()


class EditorTests(unittest.TestCase):
    def test_level_summary_lists_data_levels(self):
        dev = DevTools()
        lines = dev.level_summary()
        self.assertTrue(any("m1.warehouse" in ln for ln in lines), lines[:3])

    def test_timeline_edit_round_trip_tmp(self):
        import json
        import shutil
        import tempfile
        from game import timelines as tl

        tmp = tempfile.mkdtemp()
        src = os.path.join(tl.TIMELINES_DIR, "m4.story_beats.timeline.json")
        shutil.copy(src, os.path.join(tmp, "m4.story_beats.timeline.json"))
        old_dir, old_cache = tl.TIMELINES_DIR, dict(tl._cache)
        tl.TIMELINES_DIR = tmp
        tl._cache.clear()
        try:
            from core.console import Console
            c = Console()
            c._tl_edit("tl_mark", ["tl_mark", "m4.story_beats", "review", "1200"])
            data = json.load(open(os.path.join(tmp, "m4.story_beats.timeline.json"), encoding="utf-8"))
            self.assertEqual(data["metadata"]["markers"][-1], {"name": "review", "t": 1200})
            tl._cache.clear()
            self.assertIn("story_beats", tl.timeline("m4.story_beats").id)
        finally:
            tl.TIMELINES_DIR = old_dir
            tl._cache.clear()
            tl._cache.update(old_cache)
