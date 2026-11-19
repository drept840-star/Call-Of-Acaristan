"""engine.anim 3D spring, layered pose mixing, and stair foot-IK tests."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from engine.anim import (  # noqa: E402
    LOWER_BODY_KEYS,
    UPPER_BODY_KEYS,
    AngleSpring,
    FootIKSolver,
    LayeredAnimState,
    Spring,
    TurnLagTracker,
    locomotion_pose,
)


class SpringTests(unittest.TestCase):
    def test_critically_damped_spring_settles_without_overshoot(self):
        s = Spring(0.0, freq_hz=8.0, zeta=1.0)
        vals = [s.step(1.0 / 60.0, 10.0) for _ in range(90)]
        self.assertTrue(all(0.0 <= v <= 10.001 for v in vals))
        self.assertAlmostEqual(vals[-1], 10.0, places=3)

    def test_hitch_stability_for_large_dt(self):
        s = Spring(0.0, freq_hz=30.0, zeta=0.7)
        s.impulse(200.0)
        v = s.step(0.05, 0.0)
        self.assertTrue(math.isfinite(v))
        self.assertLess(abs(v), 15.0)

    def test_angle_spring_takes_shortest_arc_across_seam(self):
        a = AngleSpring(175.0, freq_hz=8.0, zeta=1.0)
        mid = a.step(1.0 / 30.0, -175.0)
        # Should step clockwise through +-180, never backwards through 0
        self.assertGreater(abs(mid), 170.0)

    def test_turn_lag_recovers_to_zero_when_turning_stops(self):
        tl = TurnLagTracker(0.0)
        tl.step(1.0 / 60.0, 0.0)
        h1, s1, _ = tl.step(1.0 / 60.0, 12.0)
        self.assertLess(h1, 0.0)
        self.assertLess(s1, 0.0)
        for _ in range(60):
            h2, s2, _ = tl.step(1.0 / 60.0, 12.0)
        self.assertAlmostEqual(h2, 0.0, places=2)
        self.assertAlmostEqual(s2, 0.0, places=2)


class LayeredAnimTests(unittest.TestCase):
    def test_reload_and_flinch_keep_running_legs_active(self):
        ctrl = LayeredAnimState(yaw_deg=0.0)
        ctrl.start_reload(1.0)
        ctrl.trigger_flinch(0.0, 1.0, strength=1.0)
        for _ in range(15):
            ctrl.update(1.0 / 60.0, vel_xz=(0.0, 4.5), yaw_deg=0.0, aiming=False)
        ready = {"lsh_p": 20.0, "rsh_p": 22.0, "lel": 40.0, "rel": 42.0, "spine": 2.0}
        pose_run = ctrl.compose(ready, time_s=0.25)

        ctrl_idle = LayeredAnimState(yaw_deg=0.0)
        ctrl_idle.start_reload(1.0)
        for _ in range(15):
            ctrl_idle.update(1.0 / 60.0, vel_xz=(0.0, 0.0), yaw_deg=0.0, aiming=False)
        pose_idle = ctrl_idle.compose(ready, time_s=0.25)

        # Legs move dynamically while upper body reloads; the idle gait keeps
        # only its static athletic stance (no stride cycle), not zeroed legs.
        # Sample the whole cycle: a single frame can sit at a leg crossing,
        # where both thighs are legitimately level.
        poses = [pose_run]
        for _ in range(20):
            ctrl.update(1.0 / 60.0, vel_xz=(0.0, 4.5), yaw_deg=0.0, aiming=False)
            poses.append(ctrl.compose(ready, time_s=0.25))
        hips = [p["lhip_p"] for p in poses]
        self.assertGreater(max(hips) - min(hips), 25.0)
        self.assertGreater(max(abs(p["lhip_p"] - p["rhip_p"]) for p in poses), 20.0)
        self.assertAlmostEqual(pose_idle["lhip_p"], locomotion_pose(0.0, 0.0, 0.0)["lhip_p"], places=3)
        # Reload cancel restores arms smoothly
        ctrl.cancel_reload()
        for _ in range(30):
            ctrl.update(1.0 / 60.0, vel_xz=(0.0, 4.5), yaw_deg=0.0)
        self.assertLess(ctrl.reload_w.value, 0.05)

    def test_strafe_produces_lateral_hip_and_lean(self):
        p = locomotion_pose(0.0, 4.0, phase=math.pi * 0.5)
        self.assertNotEqual(p["spine_r"], 0.0)
        self.assertGreater(max(p["lhip_r"], p["rhip_r"]), 4.0)
        self.assertTrue(LOWER_BODY_KEYS.isdisjoint(UPPER_BODY_KEYS))

    def test_knee_folds_on_forward_swing_not_planted_stroke(self):
        # Folding the knee while the thigh sweeps back drags the planted foot
        # forward (moonwalk); the fold belongs to the forward swing.
        n = 72
        poses = [locomotion_pose(3.3, 0.0, phase=i * math.tau / n) for i in range(n)]
        swing, stance = [], []
        for i in range(n):
            dhip = poses[(i + 1) % n]["lhip_p"] - poses[i - 1]["lhip_p"]
            (swing if dhip > 0.0 else stance).append(poses[i]["lkn"])
        self.assertGreater(max(swing), 50.0)
        self.assertGreater(sum(swing) / len(swing), 3.0 * sum(stance) / len(stance))

    def test_foot_ik_bends_uphill_leg_on_stairs(self):
        ik = FootIKSolver(y0=0.0)
        # Steps rising smoothly along +z: front foot at z > 0 is higher than back foot
        def stairs(x, z):
            return max(0.0, z * 0.8)

        for _ in range(30):
            adj = ik.update(1.0 / 60.0, (0.0, 0.0, 0.0), 0.0, math.pi * 0.5, 1.0, stairs)
        self.assertGreater(adj["lkn"], adj["rkn"])
        self.assertGreater(ik.foot_targets["l"][1], ik.foot_targets["r"][1])


if __name__ == "__main__":
    unittest.main()
