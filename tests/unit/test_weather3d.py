"""Phase 11 step 6: weather is a closed-form, seeded, quality-gated
function of (prims, t) - same inputs, same sprite calls; quality 0 off."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from core.user_settings import SETTINGS  # noqa: E402
from cutscenes import weather3d  # noqa: E402


class _FakeR:
    def __init__(self):
        self.calls = []

    def add_sprite(self, pos, fn, layer=0):
        self.calls.append((tuple(round(v, 6) for v in pos), layer))


_PRIMS = [
    {"kind": "emitter", "sub": "steam", "pos": [1.0, 0.5, 2.0], "seed": 7},
    {"kind": "fog_layer", "rect": [-2, -2, 2, 2], "y": 0.4},
]


class Weather(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((64, 64))

    def setUp(self):
        self._q = SETTINGS.quality_3d

    def tearDown(self):
        SETTINGS.quality_3d = self._q

    def test_deterministic_same_t(self):
        SETTINGS.quality_3d = 2
        a, b = _FakeR(), _FakeR()
        weather3d.attach(a, _PRIMS, 1800)
        weather3d.attach(b, _PRIMS, 1800)
        self.assertEqual(a.calls, b.calls)
        self.assertTrue(len(a.calls) > 10)

    def test_moves_with_t(self):
        SETTINGS.quality_3d = 2
        a, b = _FakeR(), _FakeR()
        weather3d.attach(a, _PRIMS, 1800)
        weather3d.attach(b, _PRIMS, 2400)
        self.assertNotEqual(a.calls, b.calls)

    def test_quality_zero_is_off(self):
        SETTINGS.quality_3d = 0
        r = _FakeR()
        weather3d.attach(r, _PRIMS, 1800)
        weather3d.rain(r, 1800, seed=7)
        self.assertEqual(r.calls, [])

    def test_quality_one_halves_emitter(self):
        SETTINGS.quality_3d = 2
        hi = _FakeR()
        weather3d.attach(hi, _PRIMS, 1800)
        SETTINGS.quality_3d = 1
        lo = _FakeR()
        weather3d.attach(lo, _PRIMS, 1800)
        self.assertTrue(0 < len(lo.calls) < len(hi.calls))


if __name__ == "__main__":
    unittest.main()
