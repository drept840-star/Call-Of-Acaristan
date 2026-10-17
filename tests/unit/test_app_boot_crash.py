"""engine.core.App: headless boot, service wiring, crash report (§6.1 acceptance)."""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.unit import _helpers  # noqa: F401
from tests.unit._helpers import ROOT, SRC

from engine.core import AEError, App, AssetError, Settings, write_crash_report


class CrashReport(unittest.TestCase):
    def test_write_crash_report_contents(self):
        with tempfile.TemporaryDirectory() as d:
            try:
                raise AssetError("missing", asset="m5/poster", variant=2)
            except AssetError as e:
                path = write_crash_report(d, e, log_lines=[f"line {i}" for i in range(250)],
                                          extra={"seed": 7, "frame": 12})
            text = path.read_text(encoding="utf-8")
            self.assertTrue(path.name.endswith(".txt"))
            self.assertIn("RPE6 CRASH REPORT", text)
            self.assertIn("AssetError: missing [asset='m5/poster', variant=2]", text)
            self.assertIn("seed: 7", text)
            self.assertIn("frame: 12", text)
            self.assertIn("--- traceback ---", text)
            self.assertNotIn("line 49\n", text)      # only the last 200 log lines
            self.assertIn("line 249", text)
            self.assertNotIn("\r\n", path.read_bytes().decode("utf-8"))

    def test_error_context(self):
        e = AEError("bad", timeline="m5/end04", t=1200)
        self.assertEqual(e.context, {"timeline": "m5/end04", "t": 1200})
        self.assertIn("t=1200", str(e))


class Boot(unittest.TestCase):
    def test_boot_without_display_registers_services(self):
        app = App(Settings({"video_driver": "dummy", "crash_dir": tempfile.mkdtemp()}))
        self.assertFalse(app.booted)
        app.boot(open_display=False)
        try:
            self.assertTrue(app.booted)
            self.assertIs(App.current(), app)
            for name in ("settings", "log", "clock", "rng", "events", "profiler"):
                self.assertTrue(app.services.has(name), name)
            self.assertFalse(app.services.has("screen"))
            self.assertIs(app.rng.stream("legacy"), app.rng.stream("legacy"))
            self.assertIn("booted", app.log.tail(1)[0])
        finally:
            app.shutdown()
        self.assertIsNone(App.current())

    def test_run_frames_fixed_step_and_crash(self):
        with tempfile.TemporaryDirectory() as d:
            app = App(Settings({"video_driver": "dummy", "crash_dir": d}))
            app.boot(open_display=False)
            try:
                steps = []
                app.run_frames([1 / 60 + 1e-9] * 6, lambda a, dt: steps.append(dt))
                self.assertEqual(len(steps), 6)
                self.assertEqual(app.clock.frame, len(steps))

                def boom(a, dt):
                    raise RuntimeError("injected")

                with self.assertRaises(RuntimeError):
                    app.run_frames([1 / 30], boom)
                reports = sorted(Path(d).glob("*.txt"))
                self.assertEqual(len(reports), 1)
                text = reports[0].read_text(encoding="utf-8")
                self.assertIn("RuntimeError: injected", text)
                self.assertIn("services:", text)
            finally:
                app.shutdown()

    def test_quit_stops_run_scene(self):
        app = App(Settings({"video_driver": "dummy"}))
        app.boot(open_display=False)
        try:
            class Scene:
                done = False
                frames = 0

                def frame(self):
                    self.frames += 1
                    if self.frames == 3:
                        app.quit(4)

            s = Scene()
            self.assertEqual(app.run_scene(s), 4)
            self.assertEqual(s.frames, 3)
            self.assertIs(app.services.scene, s)
        finally:
            app.shutdown()


class ImportSideEffects(unittest.TestCase):
    """Importing engine.* in a fresh interpreter must not create a window or init pygame (R7)."""

    def test_engine_import_is_pure(self):
        code = (
            "import sys, pkgutil, importlib\n"
            "import engine, engine.core\n"
            "for m in pkgutil.walk_packages(engine.__path__, 'engine.'):\n"
            "    importlib.import_module(m.name)\n"
            "pg = sys.modules.get('pygame')\n"
            "assert pg is None or not pg.get_init(), 'pygame initialised at import'\n"
            "assert pg is None or pg.display.get_surface() is None, 'window at import'\n"
            "print('PURE', engine.__version__, engine.ENGINE_NAME)\n"
        )
        env = dict(os.environ)
        env.pop("SDL_VIDEODRIVER", None)
        env["PYTHONPATH"] = str(SRC)
        r = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PURE 0.", r.stdout)
        self.assertIn("Retardovici Pulse Engine 6 Gold", r.stdout)


if __name__ == "__main__":
    unittest.main()
