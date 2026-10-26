import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from engine3d import hold, ik  # noqa: E402
from engine3d.rig import Humanoid  # noqa: E402

SPEC = dict(skin=(200, 160, 130), hair=(40, 30, 20), jacket=(60, 70, 60),
            vest=(50, 60, 50), pants=(40, 40, 50), boots=(20, 20, 20), rifle="rifle")
POS, YAW = (0.0, 0.0, 0.0), 0.0


def _hum():
    return Humanoid(dict(SPEC))


def _local(vols, p, name="torso"):
    b = vols[name]
    q = ik.m_apply(ik._t(b.M), ik._sub(p, b.org))
    return [q[i] / b.sc2 - b.c[i] for i in range(3)]


class HoldTests(unittest.TestCase):
    def test_push_out_clears_torso(self):
        h = _hum()
        vols = hold.body_volumes(h, {}, POS, YAW)
        inside = vols["torso"].org
        inside = ik._add(inside, ik.m_apply(vols["torso"].M, (0.0, 0.30, 0.0)))
        self.assertGreater(hold._depth(vols["torso"], inside), 0.05)
        out = hold.push_out(vols, inside)
        for n in ("torso", "chest"):
            self.assertLess(hold._depth(vols[n], out), 0.03)

    def test_pole_choice_for_target_in_front_of_chest(self):
        h = _hum()
        sh = ik.shoulder_world(h, {}, POS, YAW, "r")
        # across the chest, low and a hand's width in front of the vest
        target = (sh[0] - 0.22, sh[1] - 0.25, sh[2] + 0.22)
        pose = hold.solve_arm_safe(h, {}, POS, YAW, "r", target)
        self.assertLess(hold.arm_clash(h, pose, POS, YAW, "r"), 0.03)
        j = h.pose_world(pose, POS, YAW, rifle_on=False)[1]
        self.assertLess(ik._len(ik._sub(j["rhand"], target)), 0.02)

    def test_modes_reach_both_grips(self):
        h = _hum()
        for mode in ("aim", "ready", "port", "carry"):
            pose = hold.hold_weapon(h, dict(spine=10, twist=12), POS, YAW, "rifle", mode,
                                    aim=(0.0, 1.4, 20.0) if mode == "aim" else None)
            rep = hold.hold_report(h, pose, POS, YAW, "rifle")
            self.assertLess(rep["support"], 0.015, mode)
            self.assertLess(rep["arm"], 0.03, mode)
            self.assertLess(rep["rifle"], 0.03, mode)

    def test_spine_lean_keeps_contact(self):
        h = _hum()
        for spine, twist in ((3, 0), (20, 0), (8, 25), (-6, -20)):
            pose = hold.hold_weapon(h, dict(spine=spine, twist=twist), POS, YAW,
                                    "rifle", "aim", aim=(2.0, 1.5, 15.0))
            rep = hold.hold_report(h, pose, POS, YAW, "rifle")
            self.assertLess(rep["support"], 0.015, (spine, twist))

    def test_one_hand_leaves_left_arm(self):
        h = _hum()
        pose = hold.hold_weapon(h, dict(lsh_p=30, lel=40), POS, YAW, "pistol", "one_hand")
        self.assertEqual(pose["lsh_p"], 30)


if __name__ == "__main__":
    unittest.main()
