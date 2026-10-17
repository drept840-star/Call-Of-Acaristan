"""engine.core.Clock: fixed-step semantics, identity with the legacy FixedStepClock (ADR-004)."""
from __future__ import annotations

import unittest

from tests.unit import _helpers  # noqa: F401  (sys.path + headless env)

from engine.core import Clock, DEFAULT_HZ, DEFAULT_MAX_STEPS


def _simulate(step_hz: int, render_fps: float, seconds: float = 1.0):
    """Run ``seconds`` of real time at a given render rate; return (steps, sim_time, frame)."""
    clk = Clock(step_hz)
    real_dt = 1.0 / render_fps
    n_frames = int(round(seconds * render_fps))
    steps = 0
    for _ in range(n_frames):
        for _dt in clk.steps(real_dt):
            steps += 1
    # Summing 144 × (1/144) lands a few ulp under 1.0, which legitimately starves
    # the last step (same as the legacy clock; ADR-004 keeps that semantics).
    # A microsecond of slack makes the comparison about step logic, not float sums.
    for _dt in clk.steps(1e-6):
        steps += 1
    return steps, clk.sim_time, clk.frame


class ClockBasics(unittest.TestCase):
    def test_defaults(self):
        clk = Clock()
        self.assertEqual(clk.step_hz, DEFAULT_HZ)
        self.assertEqual(clk.max_steps, DEFAULT_MAX_STEPS)
        self.assertAlmostEqual(clk.dt, 1.0 / DEFAULT_HZ)
        self.assertEqual((clk.frame, clk.sim_time, clk.real_time), (0, 0.0, 0.0))

    def test_invalid_args(self):
        with self.assertRaises(ValueError):
            Clock(0)
        with self.assertRaises(ValueError):
            Clock(60, 0)

    def test_zero_or_negative_dt_does_nothing(self):
        clk = Clock(60)
        self.assertEqual(clk.advance(0.0), 0)
        self.assertEqual(clk.advance(-1.0), 0)
        self.assertEqual(clk.advance(None), 0)
        self.assertEqual(clk.frame, 0)

    def test_one_step_per_exact_frame(self):
        clk = Clock(60)
        for i in range(1, 11):
            got = list(clk.steps(1.0 / 60.0 + 1e-9))   # a hair over, so float noise can't starve a step
            self.assertEqual(len(got), 1, f"frame {i}")
        self.assertEqual(clk.frame, 10)
        self.assertEqual(clk.ticks_ms, 10 * 1000 // 60)

    def test_spiral_of_death_guard(self):
        clk = Clock(60, max_steps=5)
        n = clk.advance(1.0)             # 60 steps owed, only 5 allowed
        self.assertEqual(n, 5)
        self.assertEqual(clk.dropped_steps, 55)
        self.assertEqual(clk.alpha, 0.0)  # accumulator cleared

    def test_pause_and_time_scale(self):
        clk = Clock(60)
        clk.paused = True
        self.assertEqual(clk.advance(0.5), 0)
        self.assertAlmostEqual(clk.real_time, 0.5)   # UI clock keeps running
        clk.paused = False
        clk.time_scale = 0.5
        self.assertEqual(clk.advance(1.0 / 60.0), 0)  # half speed: one real frame is half a step
        self.assertEqual(clk.advance(1.0 / 60.0), 1)

    def test_alpha_in_unit_interval(self):
        clk = Clock(60)
        clk.advance(0.5 / 60.0)
        self.assertAlmostEqual(clk.alpha, 0.5, places=6)
        self.assertGreaterEqual(clk.alpha, 0.0)
        self.assertLessEqual(clk.alpha, 1.0)

    def test_reset(self):
        clk = Clock(60)
        list(clk.steps(0.1))
        clk.reset()
        self.assertEqual((clk.frame, clk.sim_time, clk.real_time, clk.dropped_steps), (0, 0.0, 0.0, 0))


class ClockIdentity(unittest.TestCase):
    """§6.1 acceptance: 1 s simulated at 30, 60 and 144 fps render rates gives identical sim state."""

    def test_same_sim_state_at_any_render_rate(self):
        results = {fps: _simulate(60, fps) for fps in (30, 60, 144)}
        steps = {r[0] for r in results.values()}
        self.assertEqual(len(steps), 1, results)
        self.assertEqual(steps.pop(), 60)
        for fps, (_, sim_time, frame) in results.items():
            self.assertAlmostEqual(sim_time, 1.0, places=9, msg=f"{fps} fps")
            self.assertEqual(frame, 60, f"{fps} fps")

    def test_matches_legacy_fixedstep_clock(self):
        """Step counts per frame are identical to core.fixedstep.FixedStepClock for a jittery stream."""
        from core import fixedstep
        import random
        rnd = random.Random(4242)
        dts = [rnd.uniform(0.004, 0.090) for _ in range(600)]
        for hz in (30, 60, 144):
            new, old = Clock(hz), fixedstep.FixedStepClock(hz)
            for dt in dts:
                n = new.advance(dt)
                self.assertEqual(n, old.steps(dt), f"hz={hz} dt={dt}")
                for _ in range(n):
                    new.tick()
            self.assertEqual(new.dropped_steps, old.dropped_steps)
            self.assertAlmostEqual(new.sim_time, old.sim_time, places=6)


class WallClock(unittest.TestCase):
    """Frame-coherent wall time (B-001): fed once per presented frame, read anywhere."""

    def test_origin_feed_and_scale(self):
        clk = Clock(60)
        clk.set_wall_origin(100_000, 1_700_000_000.0)
        self.assertEqual(clk.wall_ms, 100_000)
        self.assertEqual(clk.wall_s, 1_700_000_000.0)
        clk.feed_wall(16)
        clk.feed_wall(0)            # ignored
        clk.feed_wall(-5)           # ignored
        clk.feed_wall(17)
        self.assertEqual(clk.wall_ms, 100_033)
        self.assertAlmostEqual(clk.wall_s, 1_700_000_000.033)
        clk.set_wall_elapsed(1000)
        self.assertEqual(clk.wall_ms, 101_000)

    def test_wall_is_independent_of_sim_pause_and_reset(self):
        clk = Clock(60)
        clk.set_wall_origin(5, 0.0)
        clk.paused = True
        clk.feed_wall(16)
        self.assertEqual(clk.wall_ms, 21)        # pause affects the sim clock only
        clk.reset()
        self.assertEqual(clk.wall_ms, 5)         # reset clears elapsed, keeps the origin

    def test_timebase_accessors_follow_the_running_app(self):
        from engine.core import App, Settings, now_ms, now_s
        from engine.core import app as app_mod
        self.assertIsNone(app_mod._CURRENT)
        self.assertIsInstance(now_ms(), int)     # OS fallback before boot
        a = App(Settings({"video_driver": "dummy"})).boot(open_display=False)
        try:
            a.clock.set_wall_origin(1234, 10.0)
            a.clock.feed_wall(100)
            self.assertEqual(now_ms(), 1334)
            self.assertEqual(now_s(), 10.1)
        finally:
            a.shutdown()

    def test_pin_wall_overrides_everything_until_unpinned(self):
        from engine.core import now_ms, now_s, pin_wall, unpin_wall
        clock = [5]
        pin_wall(ms=lambda: clock[0], s=2.5)
        try:
            self.assertEqual(now_ms(), 5)
            clock[0] = 9
            self.assertEqual(now_ms(), 9)
            self.assertEqual(now_s(), 2.5)
        finally:
            unpin_wall()
        self.assertNotEqual(now_s(), 2.5)


if __name__ == "__main__":
    unittest.main()
