"""engine.timeline + engine.render3d kernels: expressions, sampling, set building (RPE6 Phase 8)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from engine.render3d import build as build_set  # noqa: E402
from engine.render3d import from_dict as set_from  # noqa: E402
from engine.render3d import validate as set_validate  # noqa: E402
from engine.timeline import TimelinePlayer, evaluate, from_dict as tl_from  # noqa: E402
from engine.timeline import validate as tl_validate  # noqa: E402
from engine.timeline.expr import ExprError  # noqa: E402

TL = {"schema": "ae.timeline/1", "id": "t.cut", "duration_ms": 1000, "skippable": True,
      "params": {"span": 4.0},
      "shots": [{"scene": "a", "speaker": "ADA", "text": "hi", "duration_ms": 400},
                {"scene": "b", "speaker": "", "text": "", "duration_ms": 600}],
      "tracks": {"camera": [{"t": 0, "pos": [0, 1.6, 6], "fov": 55},
                            {"t": 1000, "pos": ["lerp(0, span, k)", 1.6, 2], "fov": 40, "ease": "linear"}],
                 "light": [{"t": 0, "ambient": 0.4}, {"t": 500, "ambient": 0.8}],
                 "event": [{"t": 300, "name": "bang"}, {"t": 900, "name": "end"}],
                 "audio": [{"start": 100, "end": 400, "sound": "room_tone"}]}}

SET = {"schema": "ae.set3d/1", "id": "t/room",
       "fog": {"color": [10, 10, 12], "start": 8.0, "end": 30.0},
       "light": {"direction": [-0.5, 0.7, -0.5], "ambient": 0.42, "diffuse": 0.78, "tint": [1.0, 1.0, 1.0]},
       "nodes": [{"type": "quad_xz", "rect": [-5, -5, 5, 3], "y": 0.0, "color": [40, 30, 26]},
                 {"type": "repeat", "count": 3, "as": "i",
                  "node": {"type": "box", "size": [1.6, 0.06, 0.02],
                           "center": [-1.6, "1.3 + i*0.18", 3.08], "color": [110, 96, 70], "emissive": True}},
                 {"type": "prop_ref", "ref": "lamp", "at": [2, 0, 1]},
                 {"type": "decal", "asset": "t/poster", "center": [0, 1.5, 3.0], "size": [1, 1],
                  "fallback": [{"type": "box", "size": [1, 1, 0.04], "center": [0, 1.5, 3.02], "color": [9, 9, 9]}]}]}

LIB = {"lamp": [{"type": "box", "size": [0.3, 0.05, 0.3], "center": [0, 0.02, 0], "color": [20, 20, 20]},
                {"type": "sprite3d", "pos": [0, 0.6, 0], "size": [0.5, 0.5], "color": [255, 220, 160]}]}


class ExprTests(unittest.TestCase):
    def test_arithmetic_and_funcs(self):
        self.assertAlmostEqual(evaluate("lerp(-3.2, -2.9, k)", {"k": 0.5}), -3.05)
        self.assertAlmostEqual(evaluate("1.3 + i*0.18", {"i": 2}), 1.66)
        self.assertAlmostEqual(evaluate("clamp(x, 0, 1)", {"x": 7}), 1.0)

    def test_rejects_eval_escape(self):
        for bad in ("__import__('os')", "x.real", "open('f')", "[1,2][0]", "k if k else 0"):
            with self.assertRaises(ExprError, msg=bad):
                evaluate(bad, {"k": 0.0})


class TimelineTests(unittest.TestCase):
    def test_validates_and_samples(self):
        self.assertEqual(tl_validate(TL), [])
        player = TimelinePlayer(tl_from(TL))
        s = player.sample(500)
        self.assertEqual(s.values["light"]["ambient"], 0.8)
        self.assertAlmostEqual(s.values["camera"]["pos"][0], 2.0)   # lerp(0, 4, k=.5)
        self.assertEqual(s.values["camera"]["fov"], 47.5)
        self.assertEqual(s.active["audio"], [])                     # clip ended at 400
        self.assertEqual(player.sample(200).active["audio"][0]["sound"], "room_tone")
        self.assertEqual(player.shot_at(100)[0], 0)
        self.assertEqual(player.shot_at(500)[1]["scene"], "b")
        self.assertEqual([e["name"] for e in player.events_between(0, 500)], ["bang"])

    def test_validator_catches_disorder(self):
        bad = {"schema": "ae.timeline/1", "id": "x",
               "tracks": {"camera": [{"t": 10, "pos": [0, 0, 0]}, {"t": 5, "pos": [0, 0, 0]}]}}
        self.assertTrue(any("out of order" in p for p in tl_validate(bad)))
        bad2 = {"schema": "ae.timeline/1", "id": "x", "shots": [{"speaker": "ADA"}]}
        self.assertTrue(any("scene" in p for p in tl_validate(bad2)))


class Set3DTests(unittest.TestCase):
    def test_build_expands_and_offsets(self):
        self.assertEqual(set_validate(SET), [])
        prims = build_set(set_from(SET), library=LIB)
        self.assertEqual(prims[0]["kind"], "fog")
        self.assertEqual(prims[1]["kind"], "light")
        boxes = [p for p in prims if p["kind"] == "box"]
        self.assertEqual(len(boxes), 4)                             # 3 repeat + lamp base
        self.assertAlmostEqual(boxes[1]["center"][1], 1.48)         # 1.3 + 1*0.18
        lamp_base = [p for p in boxes if p["center"][0] == 2.0][0]
        self.assertEqual(lamp_base["center"], [2.0, 0.02, 1.0])     # prop_ref `at` applied
        decal = [p for p in prims if p["kind"] == "decal"][0]
        self.assertEqual(decal["fallback"][0]["kind"], "box")

    def test_validator_catches_unknowns(self):
        bad = {"schema": "ae.set3d/1", "id": "x", "nodes": [{"type": "sphere", "r": 1}]}
        self.assertTrue(any("unknown node type" in p for p in set_validate(bad)))


if __name__ == "__main__":
    unittest.main()
