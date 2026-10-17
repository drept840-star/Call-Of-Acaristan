"""Geometry and effect regressions for the rig collapse repair.
Run from the project root: python tools/test_oilrig_collapse.py
"""
import os
import sys
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from engine3d import Mesh
from missions.walking_attack3d import (
    RIGS, DECK_Y, _rig_local_parts, _rig_mesh,
    _collapse_parts, _rig_world_vertices, _deck_pose, _rig_fire_anchors,
    _water_entry_mesh, _water_contact, WATER_CONTACT_FRAME, _visible_wreck,
)


class CollapseTests(unittest.TestCase):
    def setUp(self):
        self.parts = _rig_local_parts()

    def assertVertexClose(self, a, b):
        for x, y in zip(a, b):
            self.assertAlmostEqual(x, y, places=8)

    def test_impact_matches_standing_mesh_for_all_rigs(self):
        for index in range(len(RIGS)):
            poses, sink = _collapse_parts(self.parts, 0, index)
            self.assertEqual(sink, 0)
            actual = [v for pose in poses for v in _rig_world_vertices(pose, index)]
            expected = _rig_mesh(index).verts
            self.assertEqual(len(actual), len(expected))
            for a, b in zip(actual, expected):
                self.assertVertexClose(a, b)

    def test_tower_base_stays_attached_to_deck(self):
        joint = (0, DECK_Y + .5, .4)
        probe = Mesh(verts=[joint])
        for index in range(3):
            for age in (0, 1, 20, 40, 65, 90, 180, 600):
                poses, _ = _collapse_parts((probe, probe, probe), age, index)
                self.assertVertexClose(poses[1][0], poses[2][0])

    def test_pose_continuous_at_phase_boundaries(self):
        for index in range(3):
            for age in (0, 8, 12, 18, 64.8, 68, 90, 390):
                before, _ = _collapse_parts(self.parts, max(0, age - .001), index)
                after, _ = _collapse_parts(self.parts, age + .001, index)
                for a_pose, b_pose in zip(before, after):
                    for a, b in zip(a_pose, b_pose):
                        self.assertLess(max(abs(x-y) for x,y in zip(a,b)), .01)

    def test_reduced_motion_is_settled_and_stationary(self):
        for index in range(3):
            start = _collapse_parts(self.parts, 0, index, reduced=True)
            end = _collapse_parts(self.parts, 600, index, reduced=True)
            settled = _collapse_parts(self.parts, 600, index)
            self.assertEqual(start, end)
            self.assertEqual(end, settled)

    def test_jacket_feet_pinned_and_tops_follow_deck(self):
        feet = [(-3.6, 0, -2.6), (3.6, 0, 2.6)]
        tops = [(-3.6, DECK_Y, -2.6), (3.6, DECK_Y, 2.6)]
        probe = Mesh(verts=feet + tops)
        for index in range(3):
            for age in (0, 18, 36, 54, 68, 90, 600):
                poses, _ = _collapse_parts((probe, Mesh(), Mesh()), age, index)
                for a, b in zip(poses[0][:2], feet):
                    self.assertVertexClose(a, b)
                for a, b in zip(poses[0][2:], _deck_pose(tops, age, index)):
                    self.assertVertexClose(a, b)

    def test_support_middle_bows_not_rigidly_translates(self):
        points = [(3.6, 0, 2.6), (3.6, DECK_Y / 2, 2.6),
                  (3.6, DECK_Y, 2.6)]
        poses, _ = _collapse_parts((Mesh(verts=points), Mesh(), Mesh()), 54, 1)
        bottom, middle, top = poses[0]
        linear_x = (bottom[0] + top[0]) / 2
        self.assertGreater(middle[0] - linear_x, .7)

    def test_fire_sockets_follow_geometry(self):
        local = [(0, DECK_Y + .7, -.5), (-2.3, DECK_Y + .9, .8),
                 (2.2, DECK_Y + .65, -1.5)]
        for index in range(3):
            for age in (0, 36, 68, 90, 600):
                expected = _rig_world_vertices(_deck_pose(local, age, index), index)
                self.assertEqual(_rig_fire_anchors(age, index), expected)
            self.assertGreater(_rig_fire_anchors(0, index)[0][1], DECK_Y)
            self.assertLess(_rig_fire_anchors(600, index)[0][1], 1)

    def test_splash_lifetime_and_contact_position(self):
        for index in range(3):
            self.assertFalse(_water_entry_mesh(index, WATER_CONTACT_FRAME - 1).verts)
            self.assertTrue(_water_entry_mesh(index, WATER_CONTACT_FRAME + 10).verts)
            self.assertFalse(_water_entry_mesh(index, WATER_CONTACT_FRAME + 128).verts)
            self.assertEqual(_water_entry_mesh(index, 80).verts,
                             _water_entry_mesh(index, 80).verts)
            flip = -1 if index == 2 else 1
            edge = _deck_pose([(-flip * 4.2, DECK_Y, 0)], WATER_CONTACT_FRAME, index)[0]
            self.assertLess(abs(edge[1]), .5)
            contact = _water_contact(index)
            self.assertAlmostEqual(contact[0], edge[0] + RIGS[index][0])
            self.assertAlmostEqual(contact[2], edge[2] + RIGS[index][1])

    def test_submerged_faces_are_clipped_without_changing_materials(self):
        mesh = Mesh()
        mesh.face([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)],
                  (100, 110, 120), 2, True)
        clipped = _visible_wreck(mesh, mesh.verts)
        self.assertEqual(len(clipped.faces), 1)
        self.assertEqual(clipped.faces[0][1:], mesh.faces[0][1:])
        self.assertTrue(all(v[1] >= .12 for v in clipped.verts))
        self.assertEqual(sum(abs(v[1] - .12) < 1e-8 for v in clipped.verts), 2)
        self.assertFalse(_visible_wreck(mesh, [(x, y-3, z) for x,y,z in mesh.verts]).faces)

    def test_settled_render_geometry_stays_at_each_rig(self):
        for index in range(3):
            poses, _ = _collapse_parts(self.parts, 600, index)
            total = []
            for mesh, pose in zip(self.parts, poses):
                clipped = _visible_wreck(mesh, _rig_world_vertices(pose, index))
                total.extend(clipped.verts)
            self.assertTrue(total)
            self.assertTrue(all(v[1] >= .12 for v in total))
            self.assertTrue(all(abs(v[0] - RIGS[index][0]) < 16 for v in total))
            self.assertTrue(all(abs(v[2] - RIGS[index][1]) < 10 for v in total))

    def test_deterministic_seek(self):
        a = _collapse_parts(self.parts, 45, 1)
        _collapse_parts(self.parts, 900, 2)
        self.assertEqual(a, _collapse_parts(self.parts, 45, 1))


if __name__ == '__main__':
    unittest.main()
