"""RPE6 Phase 11 step 1: lighting preset resolution (engine.render3d)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

from engine.render3d import (PresetError, blend_lighting, load_preset_library,
                             resolve_lighting)
from engine.render3d import presets as _p


def _lib():
    return {
        "night": _p.from_dict({
            "schema": "ae.lighting3d/1", "id": "night",
            "key": {"direction": [0, 1, 0], "ambient": 0.3, "diffuse": 0.7,
                    "tint": [1.0, 0.9, 0.8]},
            "fog": {"color": [10, 12, 16], "start": 9.0, "end": 30.0},
            "sky": [[8, 10, 14], [4, 5, 8]]}),
        "day": _p.from_dict({
            "schema": "ae.lighting3d/1", "id": "day",
            "key": {"direction": [0, 1, 0], "ambient": 0.5, "diffuse": 0.9,
                    "tint": [1.0, 1.0, 1.0]},
            "fog": {"color": [90, 90, 90], "start": 18.0, "end": 90.0}}),
        "aliasday": _p.from_dict({"schema": "ae.lighting3d/1", "id": "aliasday",
                                  "alias": "day"}),
    }


class TestPresets(unittest.TestCase):
    def test_resolve_by_id_and_alias(self):
        lib = _lib()
        self.assertEqual(resolve_lighting("night", lib)["key"]["ambient"], 0.3)
        self.assertEqual(resolve_lighting("aliasday", lib)["key"]["ambient"], 0.5)

    def test_overrides_merge_single_fields(self):
        out = resolve_lighting({"preset": "night", "key": {"ambient": 0.44}}, _lib())
        self.assertEqual(out["key"]["ambient"], 0.44)
        self.assertEqual(out["key"]["diffuse"], 0.7)  # untouched field survives

    def test_blend_midpoint(self):
        out = blend_lighting("night", "day", 0.5, _lib())
        self.assertAlmostEqual(out["key"]["ambient"], 0.4)
        self.assertAlmostEqual(out["fog"]["start"], 13.5)

    def test_unknown_and_cycle_raise(self):
        with self.assertRaises(PresetError):
            resolve_lighting("nope", _lib())
        lib = _lib()
        lib["loop"] = {"id": "loop", "alias": "loop"}
        with self.assertRaises(PresetError):
            resolve_lighting("loop", lib)

    def test_real_library_loads(self):
        import os
        d = os.path.join(os.path.dirname(__file__), "..", "..",
                         "src", "game", "content", "lighting3d")
        lib = load_preset_library(os.path.normpath(d))
        for pid in ("night_interior", "office_day", "day_interior",
                    "exterior_overcast", "exterior_night_rain", "rainy_street"):
            self.assertIn(pid, lib)
        # aliases resolve to the same mood, not a copy
        self.assertEqual(resolve_lighting("rainy_street", lib),
                         resolve_lighting("exterior_night_rain", lib))


if __name__ == "__main__":
    unittest.main()
