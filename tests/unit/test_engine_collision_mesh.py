"""engine.collision.mesh: hitboxes follow the mesh's triangles, not a box around it,
and a placed mesh uses the renderer's rot_y convention."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from engine.collision import MeshCollider  # noqa: E402
from engine3d.core import m_apply, rot_y  # noqa: E402

# one diagonal triangle at y = 1: its bounding box is 4 x 4, its area is half of that
VERTS = [(0.0, 1.0, 0.0), (4.0, 1.0, 0.0), (0.0, 1.0, 4.0)]
FACES = [(0, 1, 2)]


class BodyTests(unittest.TestCase):
    def setUp(self):
        self.shape = MeshCollider(VERTS, FACES)

    def test_inside_the_triangle_hits(self):
        self.assertTrue(self.shape.at(0, 0, 0).body_hits(1.0, 1.0, 0.32, 0.0, 1.9))

    def test_bounding_box_corner_is_clear(self):
        # (3, 3) sits inside the 4 x 4 bounding box but 1.41 m past the diagonal
        self.assertFalse(self.shape.at(0, 0, 0).body_hits(3.0, 3.0, 0.32, 0.0, 1.9))

    def test_height_band_is_respected(self):
        self.assertFalse(self.shape.at(0, 0, 0).body_hits(1.0, 1.0, 0.32, 2.0, 3.0))

    def test_radius_reaches_the_edge(self):
        # (2.1, 2.1) sits 0.14 m outside the diagonal
        self.assertTrue(self.shape.at(0, 0, 0).body_hits(2.1, 2.1, 0.32, 0.0, 1.9))
        self.assertFalse(self.shape.at(0, 0, 0).body_hits(2.1, 2.1, 0.05, 0.0, 1.9))


class RayTests(unittest.TestCase):
    def setUp(self):
        self.shape = MeshCollider(VERTS, FACES)

    def test_ray_hits_the_surface(self):
        self.assertAlmostEqual(self.shape.at(0, 0, 0).ray((1.0, 5.0, 1.0), (0.0, -1.0, 0.0)), 4.0)

    def test_ray_past_the_diagonal_misses(self):
        self.assertIsNone(self.shape.at(0, 0, 0).ray((3.5, 5.0, 3.5), (0.0, -1.0, 0.0)))

    def test_ray_respects_tmax(self):
        self.assertIsNone(self.shape.at(0, 0, 0).ray((1.0, 5.0, 1.0), (0.0, -1.0, 0.0), 3.0))


class PlacementTests(unittest.TestCase):
    def test_yaw_and_offset_match_renderer(self):
        shape = MeshCollider(VERTS, FACES)
        placed = shape.at(10.0, 0.5, -2.0, 90.0)
        m = rot_y(90.0)
        for v in VERTS:
            world = tuple(c + p for c, p in zip(m_apply(m, v), (10.0, 0.5, -2.0)))
            lx, ly, lz = placed._to_local(world)
            self.assertAlmostEqual(lx, v[0], places=9)
            self.assertAlmostEqual(ly, v[1], places=9)
            self.assertAlmostEqual(lz, v[2], places=9)

    def test_placed_body_follows_rotation(self):
        placed = MeshCollider(VERTS, FACES).at(10.0, 0.0, 0.0, 90.0)
        # local (1, 1) lands at world (11, -1) after a 90 degree yaw
        self.assertTrue(placed.body_hits(11.0, -1.0, 0.32, 0.0, 1.9))
        self.assertFalse(placed.body_hits(1.0, 1.0, 0.32, 0.0, 1.9))

    def test_world_box_bounds_the_placed_mesh(self):
        placed = MeshCollider(VERTS, FACES).at(10.0, 0.0, 0.0, 90.0)
        x0, y0, z0, x1, y1, z1 = placed.world_box()
        self.assertAlmostEqual(x0, 10.0)
        self.assertAlmostEqual(x1, 11.0 + 3.0)
        self.assertAlmostEqual(z0, -4.0)
        self.assertAlmostEqual(z1, 0.0)


if __name__ == "__main__":
    unittest.main()
