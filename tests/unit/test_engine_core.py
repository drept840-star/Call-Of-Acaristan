"""Unit tests for engine.core (stdlib unittest; run: python -m unittest discover -s tests/unit -t .)."""
import io
import random
import tempfile
import unittest
from dataclasses import dataclass

from tests.unit import _path  # noqa: F401

from engine.core import (AEError, App, Clock, EventBus, Log, RngStreams, ServiceMissing, Services, Settings,
                         derive_seed, lerp_angle, write_crash_report)


class ClockTests(unittest.TestCase):
    def _simulate(self, fps, seconds=1.0):
        c = Clock(60)
        rnd = random.Random(7)
        state = {"x": 0.0, "v": 1.0, "hits": 0}
        per_step = []
        for _ in range(int(round(fps * seconds))):
            for dt in c.steps(1.0 / fps):
                state["v"] += rnd.uniform(-0.1, 0.1)
                state["x"] += state["v"] * dt
                state["hits"] += rnd.random() < 0.2
                per_step.append((round(state["x"], 12), state["hits"]))
        return c, per_step

    def test_identical_sim_state_at_30_60_144_fps(self):
        runs = {fps: self._simulate(fps) for fps in (30, 60, 144)}
        n = min(len(p) for _, p in runs.values())
        self.assertGreaterEqual(n, 59)
        for fps, (c, p) in runs.items():
            self.assertLessEqual(abs(len(p) - 60), 1, fps)
            self.assertEqual(p[:n], runs[60][1][:n], f"diverged at {fps} fps")

    def test_spiral_guard_and_counters(self):
        c = Clock(60, max_steps=5)
        self.assertEqual(c.advance(1.0), 5)
        self.assertEqual(c.dropped_steps, 55)
        self.assertEqual(c.advance(0), 0)
        self.assertEqual(c.advance(-1), 0)

    def test_pause_and_time_scale(self):
        c = Clock(60)
        c.paused = True
        self.assertEqual(c.advance(0.5), 0)
        self.assertAlmostEqual(c.real_time, 0.5)
        c.paused = False
        c.time_scale = 0.5
        self.assertEqual(c.advance(2 / 60), 1)

    def test_ticks_ms_is_frame_derived(self):
        c = Clock(60)
        for _ in c.steps(0.5):
            pass
        self.assertEqual(c.frame, 5)       # max_steps=5 caps the 30-step backlog
        self.assertEqual(c.ticks_ms, 83)

    def test_matches_legacy_fixedstep(self):
        try:
            from core.fixedstep import FixedStepClock
        except Exception as e:  # noqa: BLE001
            self.skipTest(f"legacy clock unavailable: {e!r}")
        a, b = FixedStepClock(), Clock()
        rnd = random.Random(3)
        for _ in range(500):
            d = rnd.uniform(0.001, 0.1)
            self.assertEqual(a.steps(d), b.advance(d))


class RngTests(unittest.TestCase):
    def test_streams_independent_and_stable(self):
        r = RngStreams(42)
        a1 = [r.stream("ai").random() for _ in range(5)]
        r2 = RngStreams(42)
        r2.stream("fx").random()           # an extra consumer must not shift "ai"
        a2 = [r2.stream("ai").random() for _ in range(5)]
        self.assertEqual(a1, a2)
        self.assertEqual(derive_seed(42, "ai"), derive_seed(42, "ai"))
        self.assertNotEqual(derive_seed(42, "ai"), derive_seed(43, "ai"))

    def test_snapshot_restore(self):
        r = RngStreams(1)
        r.stream("a").random()
        snap = r.snapshot()
        x = [r.stream("a").random() for _ in range(3)]
        r.restore(snap)
        self.assertEqual(x, [r.stream("a").random() for _ in range(3)])


@dataclass
class Hit:
    n: int


class EventTests(unittest.TestCase):
    def test_queue_flush_scope(self):
        bus, got, scope = EventBus(), [], object()
        bus.subscribe(Hit, lambda e: got.append(e.n), scope=scope)
        bus.emit(Hit(1))
        self.assertEqual(got, [])
        self.assertEqual(bus.flush(), 1)
        self.assertEqual(got, [1])
        bus.emit_now(Hit(2))
        self.assertEqual(got, [1, 2])
        self.assertEqual(bus.unsubscribe_scope(scope), 1)
        bus.emit_now(Hit(3))
        self.assertEqual(got, [1, 2])
        self.assertEqual(len(bus.tail()), 3)


class LogServicesSettingsTests(unittest.TestCase):
    def test_log_ring_and_warn_once(self):
        out = io.StringIO()
        log = Log(capacity=3, stream=out)
        self.assertTrue(log.warn_once("assets", "k", "missing x"))
        self.assertFalse(log.warn_once("assets", "k", "missing x"))
        for i in range(5):
            log.info("core", str(i))
        self.assertEqual(len(log.tail()), 3)
        self.assertIn("[RPE6][assets] WARN: missing x", out.getvalue())
        with self.assertRaises(ValueError):
            log.info("nope", "x")

    def test_services(self):
        s = Services()
        s.register("a", 1)
        self.assertEqual(s.a, 1)
        with self.assertRaises(ServiceMissing):
            s.get("b")
        with self.assertRaises(ValueError):
            s.register("a", 2)

    def test_settings_layers(self):
        with tempfile.TemporaryDirectory() as d:
            p = f"{d}/s.json"
            open(p, "w").write('{"seed": 5, "width": 800}')
            s = Settings.load(p, env={"ACA_SEED": "9", "ACARISTAN_CUTSCENE3D": "0"}, overrides={"width": 640})
        self.assertEqual((s["seed"], s["width"], s["cutscene3d"], s["height"]), (9, 640, False, 700))
        self.assertEqual(s.source("seed"), "env:ACA_SEED")
        self.assertEqual(s.source("width"), "cli")

    def test_misc(self):
        self.assertAlmostEqual(lerp_angle(350, 10, 0.5), 0.0)
        self.assertIn("asset_id='x'", str(AEError("boom", asset_id="x")))


class AppTests(unittest.TestCase):
    def test_crash_report_on_injected_exception(self):
        with tempfile.TemporaryDirectory() as d:
            app = App(Settings({"crash_dir": d}))
            app.log.info("core", "before crash")

            def boom(a, dt):
                if a.clock.frame == 3:
                    raise RuntimeError("injected")
            with self.assertRaises(RuntimeError):
                app.run_frames([1 / 60] * 10, boom)
            import os
            files = [f for f in os.listdir(d) if f.endswith(".txt")]
            self.assertEqual(len(files), 1)
            txt = open(os.path.join(d, files[0]), encoding="utf-8").read()
            self.assertIn("RuntimeError: injected", txt)
            self.assertIn("frame: 3", txt)
            self.assertIn("before crash", txt)

    def test_write_crash_report_plain(self):
        with tempfile.TemporaryDirectory() as d:
            try:
                raise ValueError("x")
            except ValueError as e:
                p = write_crash_report(d, e, extra={"seed": 1})
            self.assertTrue(p.exists())


if __name__ == "__main__":
    unittest.main()
