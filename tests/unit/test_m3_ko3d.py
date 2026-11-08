"""Kill Order 3D routing, seekable action, stair support and cover geometry."""
import json
import math
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from tests.unit import _helpers
import pygame
from cutscenes import m3ko, m3ko3d as film
import missions.m3.meta as meta
from core.cutscene_registry import scene_renderer


class KillOrder3DTests(unittest.TestCase):
    def test_dialogue_pacing_and_scene_ids(self):
        shots = json.loads((Path(_helpers.SRC) / "game/content/timelines/m3.ko_transition.timeline.json").read_text(encoding="utf-8"))["shots"]
        self.assertEqual(tuple(s["scene"] for s in shots), film.SCENES)
        self.assertEqual([s["min_ms"] for s in shots], [1300, 5400, 2400, 2600])
        self.assertGreaterEqual(shots[1]["min_ms"], 500 + 4800,
                                "the door must be crossed before the player can cut")
        self.assertTrue(all(s["hard_cut"] for s in shots))
        self.assertTrue(shots[0]["auto_advance"] and shots[0]["quiet_ui"])
        self.assertEqual([s["text"] for s in shots[1:]], [
            "My van's still staged at the dock, I haven't bailed on you yet. Through that smoke, friend, and don't make me regret it.",
            "Sweep teams: the prisoner is in the lobby levels. Free fire, my address begins at 22:00, and I will not be interrupted.",
            "The loading dock is your only way out, Volkov's van is staged there. Hold it, and the Vostral goes live tonight."])
        self.assertEqual([s["scene"] for s in meta.ko_transition_shots], list(film.SCENES))

    def test_stair_ground_and_actor_separation(self):
        for i in range(film.STEPS):
            z = (i + 0.5) * film.TREAD
            self.assertAlmostEqual(film.stair_height(0, z), (film.STEPS - i) * film.RISE)
        for t in range(0, 6001, 40):
            a = film.stair_actor("volkov", t)
            b = film.stair_actor("biribel", t)
            self.assertGreater(math.dist(a[1], b[1]), 0.8)
            for pose, pos, yaw in (a, b):
                self.assertEqual(pos[1], film.stair_height(pos[0], pos[2]))
                self.assertTrue(all(math.isfinite(v) for v in pose.values()))
        from engine3d import m_apply, v_add
        for who in ("biribel", "volkov"):
            self.assertEqual(film.stair_actor(who, 8000), film.stair_actor(who, 20000))
            h = film.rig(who)
            for t in range(0, 4600, 80):
                places, _j, root = h.pose_world(*film.stair_actor(who, t), rifle_on=False)
                gaps = []
                for _slot, key, matrix, org, _ground, _bias in places:
                    if key == "foot":
                        for vertex in h._unique_verts()[key]:
                            x, y, z = v_add(root, v_add(org, m_apply(matrix, vertex)))
                            gaps.append(y - film.stair_height(x, z))
                self.assertAlmostEqual(min(gaps), 0, places=5, msg=(who, t))

    def test_stairs_clear_exit_and_pa_shot_has_an_approach(self):
        for who in ("volkov", "biribel"):
            self.assertGreater(film.stair_actor(who, 8000)[1][2], 7,
                               "actors must pass through z=5.9 exit, not stare at it")
            self.assertGreater(math.dist(film.cover_actor(who, 0)[1],
                                         film.cover_actor(who, 1600)[1]), 1.0)
            self.assertEqual(film.cover_actor(who, 8000), film.cover_actor(who, 20000))
        for t in range(0, 2000, 40):
            self.assertGreater(math.dist(film.cover_actor("volkov", t)[1],
                                         film.cover_actor("biribel", t)[1]), 0.8)
        meshes = []
        film._set(unittest.mock.Mock(bake=meshes.append), "stairs")
        # No baked face may seal the actual doorway across the route centre.
        for mesh in meshes:
            for idx, *_rest in mesh.faces:
                verts = [mesh.verts[i] for i in idx]
                if min(v[0] for v in verts) <= 0 <= max(v[0] for v in verts):
                    if all(5.7 <= v[2] <= 6.1 for v in verts):
                        self.assertFalse(min(v[1] for v in verts) < 2.7 and
                                         max(v[1] for v in verts) > 0.1,
                                         "exit aperture is sealed by wall geometry")

    def test_exit_to_pa_staging_and_framing(self):
        from engine3d import SoftwareRenderer
        surf = pygame.Surface((1000, 700))
        with patch.dict(film._cache, sets={}, failed=False, err=None), \
                patch("engine3d.Renderer", SoftwareRenderer):
            stairs = film.SCENES[1]
            for t in (0, 2600, 4300, 5400):
                film._draw(stairs, surf, t)
                r = film._cache["sets"]["stairs"][0]
                for who in ("volkov", "biribel"):
                    pos = film.stair_actor(who, t)[1]
                    q = r.project((pos[0], pos[1] + 1.4, pos[2]))
                    self.assertIsNotNone(q)
                    self.assertTrue(0 < q[0] < r.w and 0 < q[1] < r.h,
                                    (stairs, t, who, q))
            self.assertGreater(film.stair_actor("biribel", 5400)[1][2], 5.9)
            lobby = film.SCENES[2]
            for t in (0, 450, 900, 1300, 1600, 2400):
                film._draw(lobby, surf, t)
                r = film._cache["sets"]["lobby"][0]
                for who in ("volkov", "biribel"):
                    pos = film.cover_actor(who, t)[1]
                    q = r.project((pos[0], pos[1] + 1.4, pos[2]))
                    self.assertIsNotNone(q)
                    self.assertTrue(0 < q[0] < r.w and 0 < q[1] < r.h,
                                    (lobby, t, who, q))
                speaker = r.project((0.5, 3.15, 2.6))
                self.assertTrue(0 < speaker[0] < r.w and 0 < speaker[1] < r.h,
                                (lobby, t, speaker))
            self.assertLess(film.cover_actor("volkov", 0)[1][2], -1.35)
            self.assertGreater(film.cover_actor("volkov", 1600)[1][2], -1.35)
            self.assertLess(film.cover_actor("biribel", 0)[1][2], -1.35)
            self.assertGreater(film.cover_actor("biribel", 2400)[1][2], -1.35)
            # The new portal is open in the hero lanes, not a painted doorway.
            meshes = []
            film._set(unittest.mock.Mock(bake=meshes.append), "lobby")
            for mesh in meshes:
                for idx, *_rest in mesh.faces:
                    verts = [mesh.verts[i] for i in idx]
                    if (all(-1.6 <= v[2] <= -1.1 for v in verts) and
                            min(v[0] for v in verts) <= 0 <= max(v[0] for v in verts)):
                        self.assertFalse(min(v[1] for v in verts) < 2.7 and
                                         max(v[1] for v in verts) > 0.15,
                                         "the PA entrance is sealed")

    def test_sniper_has_no_targeting_line_and_hits_cover(self):
        from engine3d import POSES
        h = film.rig("ipa")
        origin = h.pose_world(POSES["aim"], film.MARKSMAN, 210, rifle_on=True)[1]["muzzle"]
        hit = film.cover_hit(origin)
        inside = [abs(hit[i] - film.PILLAR[i]) <= film.PILLAR_HALF[i] + 1e-6 for i in range(3)]
        self.assertTrue(all(inside))
        self.assertTrue(any(abs(abs(hit[i] - film.PILLAR[i]) - film.PILLAR_HALF[i]) < 1e-6 for i in range(3)))
        self.assertIsNone(film.shot_age(film.ACQUIRE - 1))
        self.assertEqual(film.shot_age(film.ACQUIRE), 0)
        for t in (0, 1150, film.ACQUIRE - 1, film.ACQUIRE, film.ACQUIRE + 50, 12000):
            r = unittest.mock.Mock()
            r.add_humanoid.return_value = {"muzzle": origin}
            film._marksman(r, t)
            r.add_line3d.assert_not_called()
            if t == film.ACQUIRE:
                self.assertEqual(r.add_sprite.call_count, 2,
                                 "muzzle and pillar impact, not a drawn ray")
        for who in ("biribel", "volkov"):
            pos = film.cover_actor(who, 1600)[1]
            self.assertLess(pos[0], film.PILLAR[0] - film.PILLAR_HALF[0])
            self.assertLess(pos[2], film.PILLAR[2] - film.PILLAR_HALF[2])

    def test_sniper_is_visible_without_flashes_or_beam(self):
        from engine3d import SoftwareRenderer
        surf = pygame.Surface((1000, 700))
        with patch.dict(film._cache, sets={}, failed=False, err=None), \
                patch("engine3d.Renderer", SoftwareRenderer):
            t = 2800  # between shots: only the actual rifleman should read
            film._draw(film.SCENES[2], surf, t)
            r = film._cache["sets"]["lobby"][0]
            q = r.project((film.MARKSMAN[0], film.MARKSMAN[1] + 1.7, film.MARKSMAN[2]))
            self.assertIsNotNone(q)
            x = int(q[0] * surf.get_width() / r.w)
            y = int(film.TOP + q[1] * (film.BOTTOM - film.TOP) / r.h)
            self.assertTrue(30 < x < 970 and 30 < y < 620)
            with_guard = pygame.surfarray.array3d(surf).copy()
            with patch.object(film, "_marksman"):
                film._draw(film.SCENES[2], surf, t)
            empty_bay = pygame.surfarray.array3d(surf).copy()
            delta = np.abs(with_guard.astype(np.int16) - empty_bay.astype(np.int16)).max(axis=2)
            self.assertGreater(int((delta[x-30:x+30, y-15:y+55] > 18).sum()), 500,
                               "sniper must be visible above the mezzanine, not hidden by the pillar")

    def test_breach_pack_never_rearms_and_dock_has_no_cast(self):
        r = unittest.mock.Mock()
        with patch.object(film, "_dynamic") as add:
            film._charge(r, 0)
            armed = add.call_count
            add.reset_mock()
            film._charge(r, 12000)
            self.assertEqual(add.call_count, 1, "only displaced door remains")
            self.assertGreater(armed, 1)
        surf = pygame.Surface((1000, 700))
        with patch.object(film, "_actor") as actor:
            film._draw(film.SCENES[3], surf, 12000)
            actor.assert_not_called()

    def test_disabled_and_failed_take_fallback(self):
        surf = pygame.Surface((1000, 700))
        fallback = unittest.mock.Mock()
        draw = m3ko._staged_take(film.SCENES[0], fallback)
        with patch.dict(os.environ, {"ACARISTAN_CUTSCENE3D": "0"}):
            draw(surf, 100)
        fallback.assert_called_once_with(surf, 100)
        with patch.dict(film._cache, failed=False, err=None), \
                patch.object(film, "_draw", side_effect=RuntimeError("probe")):
            self.assertFalse(film.draw(film.SCENES[0], surf, 0))
            self.assertIsInstance(film._cache["err"], RuntimeError)

    def test_registry_software_render_and_seek(self):
        from engine3d import SoftwareRenderer
        surf = pygame.Surface((1000, 700))
        with patch.dict(film._cache, sets={}, failed=False, err=None), \
                patch.dict(os.environ, {"ACARISTAN_CUTSCENE3D": "1"}), \
                patch("engine3d.Renderer", SoftwareRenderer):
            frames = []
            for scene in film.SCENES:
                draw = scene_renderer(scene)
                self.assertIsNotNone(draw)
                draw(surf, 2000)
                self.assertIsNone(film._cache["err"], film._cache["err"])
                first = pygame.image.tobytes(surf, "RGB")
                draw(surf, 12000)
                draw(surf, 2000)
                self.assertEqual(first, pygame.image.tobytes(surf, "RGB"), scene)
                frames.append(first)
                pixels = pygame.surfarray.array3d(surf)[:, film.TOP:film.BOTTOM]
                self.assertGreater(int(pixels.max()), 60)
                key = ("charge", "stairs", "lobby", "dock")[film.SCENES.index(scene)]
                r = film._cache["sets"][key][0]
                points = ((0, 1.5, 0),) if key == "charge" else (
                    ((0.7, 1.2, 6.5),) if key == "dock" else (
                        tuple((s[1][0], s[1][1] + 1.4, s[1][2])
                              for s in (film.stair_actor("volkov", 2000), film.stair_actor("biribel", 2000)))
                        if key == "stairs" else ((-0.65, 1.1, 2.35), film.MARKSMAN)))
                for point in points:
                    q = r.project(point)
                    self.assertIsNotNone(q)
                    self.assertTrue(0 < q[0] < r.w and 0 < q[1] < r.h, (key, q))
            self.assertEqual(len(set(frames)), 4)


if __name__ == "__main__":
    unittest.main()
