"""RPE6 Phase 11 step 5: cinematic post stack (cutscenes.post3d)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


class TestPost3d(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pygame
        pygame.init()
        pygame.display.set_mode((64, 64))
        from cutscenes import post3d
        cls.p = post3d

    def _surf(self):
        import numpy as np
        import pygame
        s = pygame.Surface((120, 90))
        a = np.zeros((120, 90, 3), dtype=np.uint8)
        a[:] = (120, 130, 140)
        a[40:80, 30:60] = (250, 250, 250)  # bright block for bloom
        pygame.surfarray.blit_array(s, a)
        return s

    def _px(self, s):
        import pygame
        return pygame.surfarray.array3d(s).copy()

    def test_grade_changes_colour_predictably(self):
        import numpy as np
        s = self._surf()
        before = self._px(s).astype(int)
        self.p.apply_post(s, {"grade": "cold_blue"}, 0, "t", 1000)
        after = self._px(s).astype(int)
        mid_b, mid_a = before[10, 10], after[10, 10]
        self.assertGreater(mid_a[2], mid_b[2])   # blue lifted
        self.assertLess(mid_a[0], mid_b[0])      # red pulled down

    def test_grain_is_deterministic(self):
        s1, s2 = self._surf(), self._surf()
        self.p.apply_post(s1, {"grain": 0.5}, 400, "scene", 1000)
        self.p.apply_post(s2, {"grain": 0.5}, 400, "scene", 1000)
        self.assertTrue((self._px(s1) == self._px(s2)).all())

    def test_vignette_darkens_corners(self):
        s = self._surf()
        self.p.apply_post(s, {"vignette": 0.9}, 0, "t", 1000)
        a = self._px(s).astype(int)
        self.assertLess(a[2, 2].mean(), a[60, 45].mean())

    def test_bloom_brightens_near_highlights(self):
        s = self._surf()
        before = self._px(s).astype(int)
        self.p.apply_post(s, {"bloom": 0.9}, 0, "t", 1000)
        after = self._px(s).astype(int)
        self.assertGreater(after[35, 45].mean(), before[35, 45].mean())

    def test_quality_off_is_identity(self):
        import core.user_settings as us
        old = us.SETTINGS.quality_3d
        us.SETTINGS.quality_3d = 0
        try:
            s = self._surf()
            before = self._px(s)
            self.p.apply_post(s, {"grain": 1.0, "vignette": 1.0}, 0, "t", 1000)
            self.assertTrue((self._px(s) == before).all())
        finally:
            us.SETTINGS.quality_3d = old


if __name__ == "__main__":
    unittest.main()
