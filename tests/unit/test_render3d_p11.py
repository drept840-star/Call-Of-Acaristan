"""RPE6 Phase 11: local lights, contact shadows, baked AO (data -> bridge)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


class TestP11(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pygame
        pygame.init()
        pygame.display.set_mode((64, 64))
        from game import render3d_bridge as bridge
        cls.bridge = bridge
        cls.prims = bridge.set_prims("mission0.depot")

    def test_attach_light_becomes_point_light_prim(self):
        kinds = [p["kind"] for p in self.prims]
        self.assertIn("point_light", kinds)
        self.assertIn("spot_light", kinds)
        lamp = next(p for p in self.prims if p["kind"] == "point_light")
        self.assertEqual(lamp["color"], [255, 196, 120])
        self.assertGreater(lamp["range"], 3.0)

    def test_shadow_prims_skip_walls(self):
        sh = self.bridge.shadow_prims(self.prims)
        self.assertTrue(sh)
        for s in sh:
            self.assertLess(s["rx"], 1.2)  # crates/bench only, no wall slabs

    def test_ao_darkens_low_faces(self):
        wall = next(p for p in self.prims
                    if p["kind"] == "box" and p["size"][1] >= 3.0)
        mesh = self.bridge.build_mesh(wall)
        cols = [f[1] for f in mesh.faces]
        self.assertLess(min(c[0] for c in cols), wall["color"][0])

    def test_local_light_brightens(self):
        from engine3d.core import SoftwareRenderer
        r = SoftwareRenderer(64, 64)
        r.set_lights([{"pos": (0, 1, 0), "color": (255, 200, 120),
                       "intensity": 1.0, "range": 4.0, "kind": "point"}])
        lit = r._local_light((100, 100, 100), (0, 0, 0), (0, 1, 0))
        self.assertGreater(lit[0], 150)
        r.set_lights([])
        self.assertEqual(r._local_light((100, 100, 100), (0, 0, 0), (0, 1, 0)),
                         (100, 100, 100))


if __name__ == "__main__":
    unittest.main()
