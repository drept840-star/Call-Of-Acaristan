"""core.frame_pacer: whole fixed steps per frame, rate drop on slow frames."""
import unittest

from tests.unit import _helpers  # noqa: F401  (sys.path + headless env)

from core.frame_pacer import Pacer, STEP


class _Fake(object):
    def __init__(self):
        self.t = 0.0

    def clock(self):
        return self.t

    def sleep(self, s):
        self.t += s + 0.0004          # OS sleep overshoots a little


def _run(work, frames):
    f = _Fake()
    p = Pacer(f.clock, f.sleep)
    out = []
    for i in range(frames):
        out.append(p.wait())
        f.t += work(i)
    return p, out


class PacerTest(unittest.TestCase):
    def test_light_frames_run_one_step_each(self):
        p, dts = _run(lambda i: 0.005, 200)
        self.assertEqual(p.n, 1)
        self.assertTrue(all(abs(d - STEP) < 1e-9 for d in dts[1:]))

    def test_slow_frames_settle_on_two_steps(self):
        p, dts = _run(lambda i: 0.028, 200)
        self.assertEqual(p.n, 2)
        self.assertTrue(all(abs(d - 2 * STEP) < 1e-9 for d in dts[-100:]))

    def test_never_locks_below_30fps(self):
        p, _ = _run(lambda i: 0.040, 200)
        self.assertEqual(p.n, 2)

    def test_lone_spikes_keep_the_rate(self):
        p, _ = _run(lambda i: 0.09 if i % 30 == 0 else 0.008, 300)
        self.assertEqual(p.n, 1)

    def test_climbs_back_after_load_drops(self):
        p, _ = _run(lambda i: 0.028 if i < 100 else 0.006, 400)
        self.assertEqual(p.n, 1)

    def test_climbs_back_through_occasional_overruns(self):
        # 14 ms frames with one 17 ms frame in ten: fits 60 fps, must not stay at 30
        p, _ = _run(lambda i: 0.028 if i < 100 else (0.017 if i % 10 == 0 else 0.014), 600)
        self.assertEqual(p.n, 1)

    def test_borderline_frames_stay_at_two_steps(self):
        p, _ = _run(lambda i: 0.016, 400)
        self.assertEqual(p.n, 2)

    def test_overrun_returns_real_duration(self):
        f = _Fake()
        p = Pacer(f.clock, f.sleep)
        p.wait()
        f.t += 0.2
        self.assertAlmostEqual(p.wait(), 0.2, places=3)   # + the first sleep's overshoot


if __name__ == "__main__":
    unittest.main()
