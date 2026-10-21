"""engine.collision: box rays and segments agree with brute force, and grid
nav routes round walls, through gaps and never up a ledge."""
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from engine.collision import BoxWorld, GridNav, ray_aabb  # noqa: E402


def _unit(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


class RayAabbTests(unittest.TestCase):
    LO, HI = (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)

    def test_hit_from_outside_is_the_near_face(self):
        self.assertAlmostEqual(ray_aabb((-2.0, 0.5, 0.5), (1.0, 0.0, 0.0), self.LO, self.HI), 2.0)

    def test_start_inside_is_zero(self):
        self.assertEqual(ray_aabb((0.5, 0.5, 0.5), (0.0, 1.0, 0.0), self.LO, self.HI), 0.0)

    def test_miss_and_behind(self):
        self.assertIsNone(ray_aabb((-2.0, 3.0, 0.5), (1.0, 0.0, 0.0), self.LO, self.HI))
        self.assertIsNone(ray_aabb((3.0, 0.5, 0.5), (1.0, 0.0, 0.0), self.LO, self.HI))

    def test_parallel_ray_outside_the_slab_misses(self):
        self.assertIsNone(ray_aabb((-1.0, 0.5, 2.0), (1.0, 0.0, 0.0), self.LO, self.HI))


class BoxWorldTests(unittest.TestCase):
    def setUp(self):
        rnd = random.Random(7)
        boxes = []
        for _ in range(60):
            x, z = rnd.uniform(-30, 30), rnd.uniform(-30, 30)
            w, d, h = rnd.uniform(0.3, 6), rnd.uniform(0.3, 6), rnd.uniform(0.5, 4)
            boxes.append((x, 0.0, z, x + w, h, z + d))
        self.world = BoxWorld(boxes, cell=4.0)
        self.rnd = rnd

    def _brute_ray(self, o, d, tmax):
        best = None
        for i, b in enumerate(self.world.boxes):
            t = ray_aabb(o, d, b[:3], b[3:])
            if t is not None and t <= tmax and (best is None or t < best[0]):
                best = (t, i)
        return best

    def test_ray_matches_brute_force(self):
        for _ in range(400):
            o = (self.rnd.uniform(-35, 35), self.rnd.uniform(0.1, 3), self.rnd.uniform(-35, 35))
            d = _unit((self.rnd.uniform(-1, 1), self.rnd.uniform(-0.2, 0.2), self.rnd.uniform(-1, 1)))
            tmax = self.rnd.uniform(1, 50)
            got, want = self.world.ray(o, d, tmax), self._brute_ray(o, d, tmax)
            self.assertEqual(got is None, want is None)
            if got is not None:
                self.assertAlmostEqual(got[0], want[0])

    def test_segment_blocked_matches_brute_force(self):
        for _ in range(400):
            a = (self.rnd.uniform(-35, 35), self.rnd.uniform(0.1, 3), self.rnd.uniform(-35, 35))
            b = (self.rnd.uniform(-35, 35), self.rnd.uniform(0.1, 3), self.rnd.uniform(-35, 35))
            dist = math.dist(a, b)
            want = self._brute_ray(a, _unit([b[i] - a[i] for i in range(3)]), dist - 0.2) is not None
            self.assertEqual(self.world.segment_blocked(a, b), want)

    def test_slack_ignores_a_box_the_target_leans_on(self):
        w = BoxWorld([(0.0, 0.0, -1.0, 1.0, 2.0, 1.0)])
        self.assertTrue(w.segment_blocked((-5.0, 1.0, 0.0), (5.0, 1.0, 0.0)))
        self.assertFalse(w.segment_blocked((-5.0, 1.0, 0.0), (0.1, 1.0, 0.0)))
        self.assertFalse(w.segment_blocked((-5.0, 3.0, 0.0), (5.0, 3.0, 0.0)))   # over it

    def test_body_hits_respects_radius_and_height(self):
        w = BoxWorld([(0.0, 0.0, 0.0, 1.0, 1.0, 1.0)])
        self.assertTrue(w.body_hits(1.2, 0.5, 0.3, 0.0, 1.8))
        self.assertFalse(w.body_hits(1.4, 0.5, 0.3, 0.0, 1.8))
        self.assertFalse(w.body_hits(0.5, 0.5, 0.3, 1.0, 2.8))           # standing on top


class GridNavTests(unittest.TestCase):
    BOUNDS = (0.0, 20.0, 0.0, 20.0)

    @staticmethod
    def _wall(gap):
        # a wall along x = 10, open for z in gap (or sealed when gap is None)
        def walkable(x, z):
            if 9.0 <= x <= 11.0:
                return gap is not None and gap[0] <= z <= gap[1]
            return True
        return walkable

    def _assert_walkable_route(self, nav, a, pts):
        here = a
        for p in pts:
            self.assertTrue(nav.walk_clear(here, p), (here, p))
            here = p

    def test_open_ground_is_one_straight_leg(self):
        nav = GridNav(self.BOUNDS, 0.5, lambda x, z: True)
        self.assertEqual(nav.path((1.0, 0.0, 1.0), (18.0, 0.0, 17.0)), [(18.0, 0.0, 17.0)])

    def test_routes_through_the_gap(self):
        nav = GridNav(self.BOUNDS, 0.5, self._wall((15.0, 18.0)))
        a, b = (2.0, 0.0, 2.0), (18.0, 0.0, 2.0)
        pts = nav.path(a, b)
        self.assertTrue(pts)
        self.assertEqual(pts[-1], b)
        self.assertTrue(any(p[2] > 14.0 for p in pts))  # went up to the gap
        self._assert_walkable_route(nav, a, pts)
        self.assertLessEqual(len(pts), 4)               # string-pulled, not a staircase

    def test_sealed_wall_has_no_route(self):
        nav = GridNav(self.BOUNDS, 0.5, self._wall(None))
        self.assertEqual(nav.path((2.0, 0.0, 2.0), (18.0, 0.0, 2.0)), [])

    def test_blocked_goal_snaps_to_the_nearest_walkable_cell(self):
        nav = GridNav(self.BOUNDS, 0.5, self._wall((15.0, 18.0)))
        pts = nav.path((2.0, 0.0, 2.0), (10.0, 0.0, 2.0))
        self.assertTrue(pts)
        self.assertTrue(nav.is_walkable(pts[-1][0], pts[-1][2]))
        self.assertLess(abs(pts[-1][0] - 10.0), 1.5)

    def test_ledges_taller_than_step_are_not_climbed(self):
        # a 1 m shelf for x > 10, reachable only by a ramp at z > 16
        def height(x, z):
            if x <= 10.0:
                return 0.0
            if z > 16.0:
                return min(1.0, (x - 10.0) * 0.25)
            return 1.0
        nav = GridNav(self.BOUNDS, 0.5, lambda x, z: True, height=height, step=0.3)
        a, b = (2.0, 0.0, 2.0), (16.0, 1.0, 2.0)
        pts = nav.path(a, b)
        self.assertTrue(pts)
        self.assertTrue(any(p[2] > 15.0 for p in pts))
        self._assert_walkable_route(nav, a, pts)
        self.assertAlmostEqual(pts[-1][1], 1.0)
        flat = GridNav(self.BOUNDS, 0.5, lambda x, z: True,
                       height=lambda x, z: 0.0 if x <= 10.0 else 1.0, step=0.3)
        self.assertEqual(flat.path(a, b), [])


if __name__ == "__main__":
    unittest.main()
