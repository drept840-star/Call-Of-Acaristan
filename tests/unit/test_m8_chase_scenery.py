"""The trailer's rearward view must change as the tractor crosses four regions.

Run: python -m unittest tests.unit.test_m8_chase_scenery -v
"""
import random
import unittest
from unittest.mock import patch

from tests.unit import _helpers  # noqa: F401 (src path and headless SDL)

from engine3d import Mesh
from missions.m8.revenge import chase_set as S


class ChaseSceneryTests(unittest.TestCase):
    def test_two_distinct_roadside_silhouettes_per_section(self):
        sites = S.ROADSIDE_SITES
        self.assertEqual(len(sites), 2 * len(S.SECTIONS))
        self.assertEqual(len({name for name, *_ in sites}), len(sites))
        for section in range(len(S.SECTIONS)):
            start = S.SECTIONS[section]
            end = S.SECTIONS[section + 1] if section + 1 < len(S.SECTIONS) else S.CROSSING_Z
            for name, z, side, distance in sites[2 * section:2 * section + 2]:
                self.assertLess(start + 30, z, name)
                self.assertLess(z, end - 30, name)
                self.assertIn(side, (-1, 1))
                self.assertGreater(distance, S.ROAD_W / 2 + 8, name)

    def test_each_landmark_is_built_into_a_different_mesh(self):
        silhouettes = []
        for name, *_ in S.ROADSIDE_SITES:
            mesh = S._roadside_site(name)
            self.assertGreater(len(mesh.faces), 25, name)
            self.assertTrue(mesh.verts, name)
            silhouettes.append((len(mesh.faces), round(max(v[1] for v in mesh.verts), 1),
                                round(max(v[0] for v in mesh.verts) - min(v[0] for v in mesh.verts), 1)))
        self.assertEqual(len(set(silhouettes)), len(silhouettes))
        class Recorder:
            def __init__(self):
                self.placements = []
            def add(self, mesh, rotation=None, position=None, **kwargs):
                self.placements.append(position)
        record = Recorder()
        S._roadside_landmarks(record)
        self.assertEqual([p[2] for p in record.placements], [z for _, z, _, _ in S.ROADSIDE_SITES])

    def test_farmsteads_and_churches_do_not_repeat_to_the_border(self):
        farms = []
        churches = []
        class Recorder:
            def add(self, mesh, rotation=None, position=None, **kwargs):
                pass
        with patch.object(S, "_farm", side_effect=lambda *a, **k: farms.append(a) or Mesh()):
            S._farmsteads(Recorder(), random.Random(812))
        self.assertLessEqual(len(farms), 4)
        with patch.object(S, "_church", side_effect=lambda: churches.append(True) or Mesh()):
            S._villages(Recorder(), random.Random(812))
        self.assertEqual(len(churches), 2)


if __name__ == "__main__":
    unittest.main()
