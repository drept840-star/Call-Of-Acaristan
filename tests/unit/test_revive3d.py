"""Unit tests for the shared 3D ally-revive animation controller (cutscenes.revive3d)."""
import math
import unittest

import tests.unit._helpers  # noqa: F401  (headless SDL + src path)

from core.outfits import OUTFIT_GUARD
from cutscenes import m6world3d as _w
from cutscenes import revive3d as REV
from engine3d import POSES


class _DummyWorld:
    def move(self, x, z, dx, dz):
        return x + dx, z + dz

    def ray_hit(self, o, d, max_d):
        return max_d


class _DummyBrain:
    def __init__(self):
        self.bodi = {
            "x": 0.0, "y": 0.0, "z": 1.4, "yaw": 180.0,
            "state": "down", "hp": 0.0,
        }


class _DummyScene:
    def __init__(self):
        self.t = 10.0
        self.px = 0.0
        self.py = 0.0
        self.pz = 0.0
        self.yaw = 0.0
        self.pitch = -4.0
        self.body_yaw = 0.0
        self.vel = (0.0, 0.0)
        self.pmoving = False
        self.sprint = False
        self.aiming = False
        self.firing = False
        self.reloading = 0.0
        self.swapping = 0.0
        self.weapon = "shotgun"
        self.hold = 0.0
        self.cam_kick = 0.0
        self.dying = False
        self.turn = None
        self.impacts = []
        self.world = _DummyWorld()
        self.brain = _DummyBrain()


class Revive3DTests(unittest.TestCase):
    def test_down_pose_proximity_and_no_inverse_bends(self):
        p_far = REV.down_pose(1.0, (0.0, 0.0, 10.0), (0.0, 0.0, 0.0), 180.0)
        p_near = REV.down_pose(1.0, (0.4, 0.0, -2.0), (0.0, 0.0, 0.0), 180.0)
        self.assertGreater(p_near["rsh_p"], p_far["rsh_p"])
        self.assertGreaterEqual(p_near["rel"], 0.0)
        self.assertGreaterEqual(p_near["lel"], 0.0)
        for v in p_near.values():
            self.assertTrue(math.isfinite(v))

    def test_full_revive_clasp_and_follow_through(self):
        sc = _DummyScene()
        REV.reset(sc)
        completed = []

        def on_done(who):
            completed.append(who)
            sc.brain.bodi["state"] = "up"

        p_hum = _w.hum(("biribel", OUTFIT_GUARD), flags=("shotgun", "nopump"))
        a_hum = _w.hum(("ally", "bodi"), flags=("os12",))
        ready = dict(POSES["ready"])

        min_hand_gap = 9e9
        for i in range(60):
            sc.t += 0.04
            REV.step(sc, 0.04, "bodi", True, 2.0, on_done)
            if completed:
                break
            a_pose, armed, _expr, hand_w = REV.ally_pose_and_hand(
                sc, "bodi", sc.brain.bodi, a_hum, ready, sc.brain.bodi["yaw"],
            )
            self.assertIsNotNone(hand_w)
            self.assertGreaterEqual(a_pose["lkn"], 0.0)
            self.assertGreaterEqual(a_pose["rkn"], 0.0)
            p_pose, draw_yaw, active = REV.apply_player_revive(
                sc, p_hum, ready, (sc.px, sc.py, sc.pz), sc.body_yaw + 35.0, True,
            )
            self.assertTrue(active)
            _pl, p_joints, _rt = p_hum.pose_world(
                p_pose, (sc.px, sc.py, sc.pz), draw_yaw, rifle_on=True,
            )
            lhand = p_joints.get("lhand")
            self.assertIsNotNone(lhand)
            if 0.28 <= sc._revive.u <= 0.78:
                gap = math.dist(lhand, hand_w)
                min_hand_gap = min(min_hand_gap, gap)

        self.assertEqual(completed, ["bodi"])
        self.assertLess(min_hand_gap, 0.14)
        self.assertFalse(REV.is_locking(sc))

        # Post-revive settle runs smoothly without snaps or NaNs
        sc.t += 0.15
        a_pose, armed, _expr, _hw = REV.ally_pose_and_hand(
            sc, "bodi", sc.brain.bodi, a_hum, ready, sc.brain.bodi["yaw"],
        )
        self.assertTrue(armed)
        p_pose, _dy, active = REV.apply_player_revive(
            sc, p_hum, ready, (sc.px, sc.py, sc.pz), sc.body_yaw + 35.0, True,
        )
        self.assertFalse(active)
        for v in list(a_pose.values()) + list(p_pose.values()):
            self.assertTrue(math.isfinite(v))

    def test_early_release_decays_cleanly(self):
        sc = _DummyScene()
        REV.reset(sc)
        for _ in range(10):
            sc.t += 0.04
            REV.step(sc, 0.04, "bodi", True, 2.0, lambda _w: None)
        self.assertTrue(REV.is_locking(sc))
        for _ in range(12):
            sc.t += 0.04
            REV.step(sc, 0.04, "bodi", False, 2.0, lambda _w: None)
        self.assertFalse(REV.is_locking(sc))
        self.assertEqual(sc._revive.vis_w, 0.0)


if __name__ == "__main__":
    unittest.main()
