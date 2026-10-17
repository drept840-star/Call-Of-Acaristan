"""Phase 8 tooling surface: ae_timeline_edit round-trip + CutsceneScene.from_timeline."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import ae_timeline_edit  # noqa: E402
from engine.scene import CutsceneScene  # noqa: E402
from engine.timeline import TimelinePlayer, from_dict  # noqa: E402

DOC = {"schema": "ae.timeline/1", "id": "t.edit", "duration_ms": 1000,
       "shots": [{"scene": "a", "text": "one", "duration_ms": 1000}],
       "tracks": {"camera": [{"t": 0, "pos": [0, 1.6, 6], "fov": 55},
                             {"t": 1000, "pos": [0, 1.6, 2], "fov": 40}]}}


class EditorRoundTripTests(unittest.TestCase):
    def test_set_key_moves_the_sampled_frame(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.timeline.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(DOC, fh)
            before = TimelinePlayer(from_dict(DOC)).sample(1000).values["camera"]["fov"]
            self.assertEqual(before, 40)
            self.assertEqual(ae_timeline_edit.main(
                ["set-key", path, "camera", "1", "fov", "30"]), 0)
            with open(path, encoding="utf-8") as fh:
                edited = json.load(fh)
            after = TimelinePlayer(from_dict(edited)).sample(1000).values["camera"]["fov"]
            self.assertEqual(after, 30)                 # reload sees exactly the moved key
            mid = TimelinePlayer(from_dict(edited)).sample(500).values["camera"]["fov"]
            self.assertEqual(mid, 42.5)                 # interpolation follows


class CutsceneSceneTimelineTests(unittest.TestCase):
    def test_from_timeline_plays_shots_and_samples(self):
        seen = []
        scene = CutsceneScene.from_timeline(
            from_dict(DOC), renderer=lambda ctx, shot, t: seen.append((shot["scene"], t)))
        self.assertFalse(scene.done)
        scene.advance(400, None)
        self.assertEqual(scene.shot["scene"], "a")
        sample = scene.player.sample(500)
        self.assertEqual(sample.values["camera"]["fov"], 47.5)
        scene.advance(700, None)
        self.assertTrue(scene.done)


if __name__ == "__main__":
    unittest.main()
