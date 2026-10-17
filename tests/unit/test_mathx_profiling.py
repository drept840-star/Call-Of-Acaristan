"""engine.core.mathx and Profiler."""
from __future__ import annotations

import unittest

from tests.unit import _helpers  # noqa: F401

from engine.core import (Profiler, clamp, ease_in_out_cubic, ease_out_quad, inv_lerp, lerp, lerp_angle,
                         smoothstep)


class MathX(unittest.TestCase):
    def test_clamp_lerp(self):
        self.assertEqual(clamp(5, 0, 3), 3)
        self.assertEqual(clamp(-1, 0, 3), 0)
        self.assertEqual(lerp(10, 20, 0.25), 12.5)
        self.assertEqual(inv_lerp(10, 20, 15), 0.5)
        self.assertEqual(inv_lerp(3, 3, 9), 0.0)

    def test_lerp_angle_short_way(self):
        self.assertAlmostEqual(lerp_angle(350, 10, 0.5), 0.0)
        self.assertAlmostEqual(lerp_angle(10, 350, 0.5), 0.0)
        self.assertAlmostEqual(lerp_angle(0, 180, 0.5), 90.0)

    def test_eases_are_clamped_and_monotonic(self):
        for f in (smoothstep, ease_in_out_cubic, ease_out_quad):
            self.assertEqual(f(-1), 0.0)
            self.assertEqual(f(2), 1.0)
            prev = 0.0
            for i in range(1, 101):
                v = f(i / 100)
                self.assertGreaterEqual(v, prev - 1e-12, f.__name__)
                prev = v
            self.assertAlmostEqual(prev, 1.0)


class ProfilerTests(unittest.TestCase):
    def test_scope_stats(self):
        p = Profiler()
        for _ in range(3):
            with p.scope("frame"):
                pass
        st = p.stats()
        self.assertEqual(st["frame"]["n"], 3)
        self.assertGreaterEqual(st["frame"]["max_ms"], st["frame"]["avg_ms"])
        p.reset()
        self.assertEqual(p.stats(), {})


if __name__ == "__main__":
    unittest.main()
