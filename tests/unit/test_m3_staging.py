"""M3's first 3D bridge: deterministic seeking, prop contact and fallback."""
import json
import math
import os
import unittest
from unittest.mock import patch
from pathlib import Path

from tests.unit import _helpers  # noqa: F401
import pygame

from cutscenes import m3ops, m3staging as film
from core.cutscene_registry import scene_renderer


class M3StagingTests(unittest.TestCase):
    def test_set_uses_shared_textured_materials_and_baked_detail(self):
        from engine3d.textures import Tex
        meshes = []
        film._set(unittest.mock.Mock(bake=meshes.append))
        self.assertGreater(len(meshes), 350, "service architecture and relay detail stay baked")
        textured = sum(isinstance(face[1], Tex) for mesh in meshes for face in mesh.faces)
        self.assertGreater(textured, 100, "large surfaces must not regress to flat grey boxes")
        self.assertTrue(any(face[4] for mesh in meshes for face in mesh.faces),
                        "practical lamps must retain emissive source geometry")

    def test_existing_dialogue_and_silent_shot_pacing(self):
        path = Path(_helpers.ROOT) / "src/game/content/timelines/m3.service_transition.timeline.json"
        shots = json.loads(path.read_text(encoding="utf-8"))["shots"]
        self.assertEqual(tuple(s["scene"] for s in shots), film.SCENES)
        self.assertEqual([s["text"] for s in shots if s.get("text")], [
            "Biribel! Take the radio. I draw them off, you get the relay alive.",
            "Biribel? If you hear me, get to the relay. I can see your signal now."])
        self.assertTrue(all(s["hard_cut"] for s in shots))
        for shot in (shots[0], shots[2]):
            self.assertTrue(shot["auto_advance"])
            self.assertTrue(shot["quiet_ui"])

    def test_radio_has_one_owner_and_continuous_catch(self):
        self.assertEqual(film._hold(0)[1], "volkov")
        self.assertEqual(film._hold((film._RELEASE + film._CATCH) / 2)[1], "flight")
        self.assertEqual(film._hold(2400)[1], "biribel")
        self.assertEqual(film._hold(2400), film._hold(0, recover=True))
        a, _ = film._hold(film._CATCH - 0.01)
        b, _ = film._hold(film._CATCH)
        self.assertLess(sum(abs(x - y) for x, y in zip(a, b)), 0.001)

    def test_toss_has_anticipation_short_flight_and_catch_absorption(self):
        self.assertLessEqual(film._CATCH - film._RELEASE, 400)
        self.assertGreater(math.dist(film._hold(0)[0], film._hold(film._RELEASE)[0]), 0.25)
        self.assertGreater(math.dist(film._hold(film._CATCH)[0], film._hold(1600)[0]), 0.10)
        for t in range(0, int(film._RELEASE), 20):
            pose, _, radio, owner = film._handoff_poses(t)
            hand = film._rig("volkov").pose_world(
                pose, film._VOLKOV, 90, rifle_on=False)[1]["rhand"]
            self.assertEqual(owner, "volkov")
            self.assertLess(math.dist(hand, radio), 0.075, t)
        ready = film._handoff_poses(0)[1]
        catch = film._handoff_poses(film._CATCH)[1]
        h = film._rig("biribel")
        ready_hand = h.pose_world(ready, film._BIRIBEL, -90, rifle_on=False)[1]["lhand"]
        catch_hand = h.pose_world(catch, film._BIRIBEL, -90, rifle_on=False)[1]["lhand"]
        self.assertGreater(math.dist(ready_hand, catch_hand), 0.25)
        for boundary in (film._RELEASE, film._CATCH, film._CATCH + 220):
            self.assertLess(math.dist(film._hold(boundary - 0.01)[0],
                                      film._hold(boundary)[0]), 0.001)

    def test_hand_contact_at_release_and_catch(self):
        for t, who, side, pos, yaw in (
                (film._RELEASE, "volkov", "rhand", film._VOLKOV, 90),
                (film._CATCH, "biribel", "lhand", film._BIRIBEL, -90)):
            vp, bp, radio, _ = film._handoff_poses(t)
            _, joints, _ = film._rig(who).pose_world(
                vp if who == "volkov" else bp, pos, yaw, rifle_on=False)
            distance = sum((x - y) ** 2 for x, y in zip(joints[side], radio)) ** 0.5
            self.assertLess(distance, 0.075, (who, distance))

    def test_stopped_walk_does_not_keep_marching(self):
        points = ((0.72, -1.6), (0.72, 0.7))
        self.assertEqual(film._walk("biribel", points, 2000, 0, 1450),
                         film._walk("biribel", points, 20000, 0, 1450))

    def test_radio_stays_in_hand_through_the_power_on_insert(self):
        for t in (0, 160, 450, 850, 1600, 12000):
            _, bp, radio, owner = film._handoff_poses(t, recover=True)
            _, joints, _ = film._rig("biribel").pose_world(
                bp, film._BIRIBEL, -90, rifle_on=False)
            self.assertEqual(owner, "biribel")
            distance = sum((a - b) ** 2 for a, b in zip(joints["lhand"], radio)) ** 0.5
            self.assertLess(distance, 0.02, (t, distance))

    def test_radio_hand_is_separate_from_the_whole_rifle(self):
        from engine3d import m_apply, m_mul, os12_mesh, rot_x, rot_y, v_add
        from engine3d.hold import arm_clash
        h = film._rig("biribel")
        gun = os12_mesh()
        for recover in (False, True):
            for t in (*range(0, 2401, 80), 12000):
                _, pose, _, _ = film._handoff_poses(t, recover)
                _, joints, _ = h.pose_world(pose, film._BIRIBEL, -90, rifle_on=False)
                rotation = m_mul(rot_y(-90 + pose.get("rifle_y", 0)), rot_x(pose["rifle_p"]))
                verts = [v_add(joints["rhand"], m_apply(rotation, v)) for v in gun.verts]
                # Nearest point on the gun's AABB: stricter than vertex-only
                # distance (which misses the middle of a long handguard face).
                lo = [min(v[i] for v in verts) for i in range(3)]
                hi = [max(v[i] for v in verts) for i in range(3)]
                hand = joints["lhand"]
                nearest = [max(lo[i], min(hi[i], hand[i])) for i in range(3)]
                self.assertGreater(math.dist(hand, nearest), 0.20, (recover, t))
                self.assertLessEqual(arm_clash(h, pose, film._BIRIBEL, -90, "r", margin=0.04),
                                     0.001, (recover, t))

    def test_volkov_throw_and_exit_stay_outside_his_torso(self):
        from engine3d.hold import arm_clash
        h = film._rig("volkov")
        for t in (*range(0, 2401, 20), 12000):
            pose = film._handoff_poses(t)[0]
            self.assertLessEqual(arm_clash(h, pose, film._VOLKOV, 90, "r", margin=0.04),
                                 0.001, ("throw", t))
            pose, pos, yaw = film._volkov_exit(t)
            self.assertLessEqual(arm_clash(h, pose, pos, yaw, "r", margin=0.04),
                                 0.001, ("exit", t))
        held = h.pose_world(film._handoff_poses(12000)[0], film._VOLKOV, 90,
                            rifle_on=False)[1]["rhand"]
        first = h.pose_world(*film._volkov_exit(0), rifle_on=False)[1]["rhand"]
        self.assertLess(math.dist(held, first), 0.04, "follow-through must survive the cut")

    def test_disabled_and_failed_3d_use_legacy_take(self):
        fallback = unittest.mock.Mock()
        draw = m3ops._staged_service_take(film.SCENES[0], fallback)
        surf = pygame.Surface((1000, 700))
        with patch.dict(os.environ, {"ACARISTAN_CUTSCENE3D": "0"}):
            draw(surf, 600)
        fallback.assert_called_once_with(surf, 600)
        with patch.dict(film._cache, failed=False, err=None), \
                patch.object(film, "_draw", side_effect=RuntimeError("backend unavailable")):
            self.assertFalse(film.draw(film.SCENES[0], surf, 0))
            self.assertTrue(film._cache["failed"])
            self.assertIsInstance(film._cache["err"], RuntimeError)

    def test_registered_software_takes_render_and_seek_identically(self):
        from engine3d import SoftwareRenderer
        surf = pygame.Surface((1000, 700))
        with patch.dict(os.environ, {"ACARISTAN_CUTSCENE3D": "1"}), \
                patch.dict(film._cache, renderer=None, failed=False, err=None), \
                patch("engine3d.Renderer", SoftwareRenderer):
            frames = []
            for scene in film.SCENES:
                draw = scene_renderer(scene)
                self.assertIsNotNone(draw)
                draw(surf, 1000)
                self.assertIsNone(film._cache["err"], film._cache["err"])
                if scene == film.SCENES[1]:
                    r = film._cache["renderer"][0]
                    self.assertGreater(r.cam[2], -1.9, "the closed service door must stay behind the lens")
                    projected = r.project(film._hold(1000)[0])
                    self.assertIsNotNone(projected)
                    self.assertTrue(0 < projected[0] < r.w and 0 < projected[1] < r.h)
                    for t in (0, film._RELEASE, 800, film._CATCH, 1600):
                        x, y, z = film._hold(t)[0]
                        low = r.project((x, y - 0.115, z))
                        high = r.project((x, y + 0.115, z))
                        self.assertIsNotNone(low)
                        self.assertIsNotNone(high)
                        for point in (low, high):
                            self.assertTrue(0 < point[0] < r.w and 0 < point[1] < r.h)
                        self.assertGreater(abs(low[1] - high[1]), 18,
                                           "radio must read as a prop, not a tiny dot")
                first = pygame.image.tobytes(surf, "RGB")
                frames.append(first)
                draw(surf, 12000)
                draw(surf, 1000)
                self.assertEqual(first, pygame.image.tobytes(surf, "RGB"), scene)
                colours = pygame.surfarray.array3d(surf)[:, film.TOP:film.BOTTOM]
                self.assertGreater(int(colours.max()), 60, scene)
            self.assertEqual(len(set(frames)), 4, "each setup must have its own composition")


if __name__ == "__main__":
    unittest.main()
