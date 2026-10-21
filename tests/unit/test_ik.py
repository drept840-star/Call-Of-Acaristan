"""engine3d.ik: analytic arm/leg IK and the shouldered rifle hold land on
their targets as measured by the rig's own forward kinematics."""
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from cutscenes.cast3d import humanoid3d  # noqa: E402
from engine3d import ik  # noqa: E402
from engine3d.rig import NEUTRAL, POSES, blend  # noqa: E402


def _ankle(hum, pose, pos, yaw, side):
    places, _j, root = hum.pose_world(pose, pos, yaw, rifle_on=False)
    slot = 9 if side == "l" else 15
    for s, _k, _m, org, _g, _fb in places:
        if s == slot:
            return tuple(org[i] + root[i] for i in range(3))
    raise AssertionError("no foot slot")


class IK(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((64, 64))
        cls.hum = humanoid3d("vasile")

    def test_arm_reaches_random_targets(self):
        rng = random.Random(7)
        for _ in range(120):
            base = dict(POSES[rng.choice(["stand", "ready", "aim", "kneel", "crouch"])])
            pos = (rng.uniform(-3, 3), 0.0, rng.uniform(-3, 3))
            yaw = rng.uniform(-180, 180)
            side = rng.choice("lr")
            sh = ik.shoulder_world(self.hum, base, pos, yaw, side)
            d = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
            n = math.sqrt(sum(c * c for c in d)) or 1.0
            r = rng.uniform(0.08, 0.58) * self.hum._scale
            tgt = tuple(sh[i] + d[i] / n * r for i in range(3))
            pose = ik.solve_arm(self.hum, base, pos, yaw, side, tgt)
            hand = self.hum.pose_world(pose, pos, yaw, rifle_on=False)[1][side + "hand"]
            self.assertLess(math.dist(hand, tgt), 1e-6)

    def test_arm_out_of_reach_points_at_target(self):
        pos, yaw = (0.0, 0.0, 0.0), 30.0
        sh = ik.shoulder_world(self.hum, {}, pos, yaw, "r")
        tgt = (sh[0] + 2.0, sh[1] + 0.5, sh[2] + 1.0)
        pose = ik.solve_arm(self.hum, {}, pos, yaw, "r", tgt)
        self.assertLess(pose["rel"], 3.0)                 # straight arm
        hand = self.hum.pose_world(pose, pos, yaw, rifle_on=False)[1]["rhand"]
        a = [hand[i] - sh[i] for i in range(3)]
        b = [tgt[i] - sh[i] for i in range(3)]
        cos = sum(x * y for x, y in zip(a, b)) / (math.hypot(*a) * math.hypot(*b))
        self.assertGreater(cos, 0.999)

    def test_pole_picks_the_elbow_side(self):
        pos, yaw = (0.0, 0.0, 0.0), 0.0
        sh = ik.shoulder_world(self.hum, {}, pos, yaw, "r")
        tgt = (sh[0], sh[1] - 0.1, sh[2] + 0.4)
        for px in (1.0, -1.0):
            pose = ik.solve_arm(self.hum, {}, pos, yaw, "r", tgt, pole=(px, 0.0, 0.0))
            places = self.hum.pose_world(pose, pos, yaw, rifle_on=False)[0]
            elbow = [o for s, _k, _m, o, _g, _f in places if s == 12][0]
            self.assertGreater((elbow[0] - (sh[0] - pos[0])) * px, 0.0)

    def test_leg_plants_the_ankle(self):
        rng = random.Random(11)
        errs = []
        for _ in range(80):
            base = dict(POSES[rng.choice(["stand", "ready", "kneel", "crouch"])])
            yaw = rng.uniform(-180, 180)
            side = rng.choice("lr")
            an = _ankle(self.hum, base, (0.0, 0.0, 0.0), yaw, side)
            tgt = (an[0] + rng.uniform(-0.15, 0.15), an[1] + rng.uniform(0.0, 0.2),
                   an[2] + rng.uniform(-0.2, 0.2))
            pose = ik.solve_leg(self.hum, base, (0.0, 0.0, 0.0), yaw, side, tgt)
            errs.append(math.dist(_ankle(self.hum, pose, (0.0, 0.0, 0.0), yaw, side), tgt))
        errs.sort()
        # auto ground contact can lift the body when a sole edge would dip
        # under the floor; everything else is exact
        self.assertLess(errs[len(errs) // 2], 1e-6)
        self.assertLess(errs[-1], 0.03)

    def test_rifle_hold_contacts(self):
        from cutscenes import m6world3d
        hum = m6world3d.hum("ucilev", True)     # the M6 sniper rig carries a rifle
        self.assertIsNotNone(hum._rifle)
        pos = (0.0, 0.0, 0.0)
        target = (4.0, 1.2, 9.0)
        # bladed stance: body turned off the target line so the support hand
        # can reach the fore-end (square to the target it falls short)
        yaw = m6world3d.yaw_to(pos, target) + 35.0
        pose = ik.solve_rifle_hold(hum, dict(POSES["aim"], twist=15), pos, yaw, target)
        gaps = ik.rifle_hold_gaps(hum, pose, pos, yaw)
        self.assertLess(gaps["butt"], 1e-3)
        self.assertLess(gaps["support"], 1e-3)
        j = hum.pose_world(pose, pos, yaw)[1]
        fwd = ik.m_apply(j["rifle_m"], (0.0, 0.0, 1.0))
        aim = ik._norm(ik._sub(target, j["muzzle"]))
        self.assertGreater(ik._dot(fwd, aim), math.cos(math.radians(0.5)))

    def test_solvers_do_not_mutate_input(self):
        base = dict(POSES["aim"])
        snap = dict(base)
        ik.solve_arm(self.hum, base, (0, 0, 0), 0.0, "l", (0.3, 1.2, 0.5))
        ik.solve_leg(self.hum, base, (0, 0, 0), 0.0, "r", (0.1, 0.1, 0.2))
        self.assertEqual(base, snap)

    def test_arm_roll_is_a_neutral_key(self):
        self.assertEqual(NEUTRAL["lsh_y"], 0)
        self.assertEqual(NEUTRAL["rsh_y"], 0)
        self.assertAlmostEqual(blend({"rsh_y": 40.0}, {}, 0.5)["rsh_y"], 20.0)


if __name__ == "__main__":
    unittest.main()
