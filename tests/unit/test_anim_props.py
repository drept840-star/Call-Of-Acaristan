"""Phase 11 step 10: flicker is a deterministic closed form; set fields
written as timeline expressions animate with the ``t`` param and are
static (t=0) without it."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import render3d_bridge as bridge  # noqa: E402


def _monitor_colour(prims):
    for p in prims:
        if p["kind"] == "box" and p.get("emissive") \
                and p.get("size") == [0.62, 0.4, 0.06]:
            return tuple(p["color"])
    raise AssertionError("monitor prim not found")


class AnimProps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((64, 64))

    def test_flicker_deterministic_bounded_seeded(self):
        self.assertEqual(bridge.flicker_at(5, 1234), bridge.flicker_at(5, 1234))
        vals = [bridge.flicker_at(5, t) for t in range(0, 20000, 37)]
        self.assertTrue(all(0.15 <= v <= 1.0 for v in vals))
        self.assertTrue(max(vals) - min(vals) > 0.3, "flicker must actually vary")
        other = [bridge.flicker_at(9, t) for t in range(0, 20000, 37)]
        self.assertNotEqual(vals, other)

    def test_expressions_animate_with_t(self):
        a = bridge.set_prims("mission0.depot", params={"t": 0.9})
        b = bridge.set_prims("mission0.depot", params={"t": 2.5})
        self.assertNotEqual(_monitor_colour(a), _monitor_colour(b))
        a2 = bridge.set_prims("mission0.depot", params={"t": 0.9})
        self.assertEqual(_monitor_colour(a), _monitor_colour(a2))

    def test_static_without_t(self):
        a = bridge.set_prims("mission0.depot")
        b = bridge.set_prims("mission0.depot")
        self.assertEqual(_monitor_colour(a), _monitor_colour(b))

    def test_yard_lamp_flicker_scales_light_and_bulb(self):
        prims = bridge.set_prims("mission0.yard", params={"t": 1.7})
        lights = [p for p in prims if p["kind"] == "point_light"
                  and p.get("flicker") is not None]
        bulbs = [p for p in prims if p["kind"] == "box"
                 and p.get("flicker") is not None]
        self.assertTrue(lights and bulbs)
        f = bridge.flicker_at(5, 1700)
        self.assertAlmostEqual(lights[0]["intensity"], 1.0 * f, places=6)


if __name__ == "__main__":
    unittest.main()
