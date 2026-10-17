"""Phase 11 step 8: expressions rebuild only the face, mouth flap is a
deterministic closed form, look-at clamps, mouth follows dialogue data."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from cutscenes.cast3d import humanoid3d  # noqa: E402
from engine3d.rig import EXPRESSIONS, mouth_flap, solve_look  # noqa: E402
from game import render3d_bridge as bridge  # noqa: E402


class Faces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((64, 64))
        cls.hum = humanoid3d("vasile")

    def test_neutral_matches_fresh_build(self):
        fresh = humanoid3d("vasile")
        self.hum.set_expression("smile", 0.5)
        self.hum.set_expression("neutral", 0.0)
        self.assertEqual(self.hum._parts["face"], fresh._parts["face"])
        self.assertEqual(self.hum._parts["face2"], fresh._parts["face2"])
        self.hum.set_expression("neutral", 0.0)

    def test_expression_changes_face_not_body(self):
        torso = self.hum._parts["torso"]
        self.hum.set_expression("angry", 0.0)
        self.assertNotEqual(self.hum._parts["face"],
                            humanoid3d("vasile")._parts["face"])
        self.assertEqual(self.hum._parts["torso"], torso)
        self.assertIn("angry", EXPRESSIONS)
        self.hum.set_expression("neutral", 0.0)

    def test_mouth_flap_deterministic_bounded(self):
        self.assertEqual(mouth_flap(1000, 7), mouth_flap(1000, 7))
        for t in range(0, 5000, 137):
            self.assertTrue(0.0 <= mouth_flap(t, 3) <= 1.0)

    def test_solve_look_clamps(self):
        hy, hp = solve_look((0, 1.6, 0), (10, 1.6, 0.2), 0)
        self.assertTrue(-38.0 <= hy <= 38.0)
        hy2, hp2 = solve_look((0, 1.6, 0), (0, -5, 0.3), 0)
        self.assertTrue(hp2 <= 30.0)
        hy3, _hp3 = solve_look((0, 1.6, 0), (0, 1.6, 1), 0)
        self.assertAlmostEqual(hy3, 0.0, places=5)

    def test_speaking_follows_dialogue_data(self):
        from core.cutscene_registry import set_current_shot
        prim = {"kind": "humanoid", "cast": "vasile"}
        set_current_shot({"speaker": "VASILE", "text": "x" * 40})
        try:
            self.assertTrue(bridge._is_speaking(prim, 100))
            self.assertFalse(bridge._is_speaking(prim, 100000))
            set_current_shot({"speaker": "BIRIBEL", "text": "x" * 40})
            self.assertFalse(bridge._is_speaking(prim, 100))
            set_current_shot({"speaker": "NARRATOR", "text": "x" * 40})
            self.assertFalse(bridge._is_speaking(prim, 100))
        finally:
            set_current_shot(None)


if __name__ == "__main__":
    unittest.main()
