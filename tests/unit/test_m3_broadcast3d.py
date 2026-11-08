"""Broadcast bridge framing, settled blocking, registry routing and seeking."""
import os
import unittest
from unittest.mock import Mock, patch

import numpy as np

from tests.unit import _helpers
import pygame
from cutscenes import m3broadcast, m3broadcast3d as film
from core.cutscene_registry import scene_renderer
from engine3d import SoftwareRenderer
import missions.m3.meta as meta


class Broadcast3DTests(unittest.TestCase):
    def test_pacing_finishes_actions_and_final_line_changes_lens(self):
        shots = meta.broadcast_transition_shots
        self.assertEqual(tuple(s["scene"] for s in shots), film.SCENES)
        self.assertTrue(all(s["hard_cut"] for s in shots))
        self.assertTrue(shots[0]["auto_advance"] and shots[0]["quiet_ui"])
        self.assertGreaterEqual(shots[0]["min_ms"], film.SLAM_MS)
        self.assertGreaterEqual(shots[3]["min_ms"], film.WALK_MS)
        self.assertNotEqual(film.camera(film.SCENES[3], film.WALK_MS),
                            film.camera(film.SCENES[4], 0))

    def test_shutter_stays_closed_and_walker_stops_short_of_door(self):
        heights = [film.shutter_bottom(t) for t in range(0, 1500, 20)]
        self.assertTrue(all(a >= b for a, b in zip(heights, heights[1:])))
        self.assertEqual(film.shutter_bottom(16000), film.shutter_bottom(900))
        for t in range(0, 4000, 40):
            pose, pos, yaw = film.corridor_actor(t)
            self.assertTrue(all(np.isfinite(v) for v in pose.values()))
            self.assertLess(pos[2] + 0.9, film.DOOR_Z)
            self.assertEqual(pos[1], 0)
        start = film.corridor_actor(0)[1]
        end = film.corridor_actor(film.WALK_MS)[1]
        self.assertGreater(end[2] - start[2], 5)
        self.assertEqual(end, film.corridor_actor(16000)[1])
        self.assertEqual(end, film.corridor_actor(3800)[1])

    def test_full_body_and_sign_stay_in_corridor_frame(self):
        r = SoftwareRenderer(*film.SIZE)
        for t in (0, 450, 900, 1600, 2400, 3400, 16000):
            eye, target, fov = film.camera(film.SCENES[3], t)
            r.set_camera(eye, target, fov)
            pos = film.corridor_actor(t)[1]
            for point in ((pos[0], 0.04, pos[2]), (pos[0], 1.95, pos[2]), (0, 3.48, 7.665)):
                q = r.project(point)
                self.assertIsNotNone(q)
                self.assertTrue(8 < q[0] < r.w - 8 and 5 < q[1] < r.h - 5, (t, point, q))
        for t in (0, 2200, 16000):
            r.set_camera(*film.camera(film.SCENES[4], t))
            q = r.project((-0.85, 1.7, 6.25))
            self.assertTrue(0.2 * r.w < q[0] < 0.8 * r.w and 10 < q[1] < r.h * 0.6)

    def test_software_registry_renders_seekable_frames_and_visible_actor(self):
        surf = pygame.Surface((1000, 700))
        with patch.dict(film._cache, sets={}, failed=False, err=None), \
                patch.dict(os.environ, ACARISTAN_CUTSCENE3D="1"), \
                patch("engine3d.Renderer", SoftwareRenderer):
            for scene in film.SCENES:
                scene_renderer(scene)(surf, 3400)
                self.assertFalse(film._cache["failed"], film._cache["err"])
                before = pygame.image.tobytes(surf, "RGB")
                film._draw(scene, surf, 16000)
                film._draw(scene, surf, 3400)
                self.assertEqual(before, pygame.image.tobytes(surf, "RGB"), scene)
                band = pygame.surfarray.array3d(surf)[:, film.TOP:film.BOTTOM]
                self.assertGreater(float(band.std()), 8, scene)
            for scene in film.SCENES[3:]:
                film._draw(scene, surf, 3400)
                before = pygame.surfarray.array3d(surf).astype(np.int16)
                r = film.renderer("corridor")[0]
                with patch.object(r, "add_humanoid"):
                    film._draw(scene, surf, 3400)
                delta = np.abs(before - pygame.surfarray.array3d(surf)).max(axis=2)
                self.assertGreater(int((delta > 15).sum()), 1500, scene)

    def test_disabled_or_failed_3d_uses_illustrated_fallback(self):
        surf = pygame.Surface((1000, 700))
        fallback = Mock()
        take = m3broadcast._staged_take(film.SCENES[0], fallback)
        with patch.dict(os.environ, ACARISTAN_CUTSCENE3D="0"):
            take(surf, 50)
        fallback.assert_called_once_with(surf, 50)
        with patch.dict(film._cache, failed=False, err=None), \
                patch.dict(os.environ, ACARISTAN_CUTSCENE3D="1"), \
                patch.object(film, "_draw", side_effect=RuntimeError("probe")):
            self.assertFalse(film.draw(film.SCENES[0], surf, 0))
            self.assertIsInstance(film._cache["err"], RuntimeError)


if __name__ == "__main__":
    unittest.main()
