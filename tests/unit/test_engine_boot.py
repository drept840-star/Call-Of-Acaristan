"""App.boot display ownership (ADAPTER A-001)."""
import os
import unittest

from tests.unit import _path  # noqa: F401  (puts src/ on sys.path)


class BootTest(unittest.TestCase):
    def test_force_mode_and_set_screen(self):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import pygame
        from engine.core.app import App
        from engine.core.config import Settings
        app = App(Settings.load(env={"SDL_VIDEODRIVER": "dummy"}))
        try:
            app.boot(display_size=(320, 200), force_mode=True)
            self.assertEqual(app.screen.get_size(), (320, 200))
            self.assertIs(app.services.get("screen"), app.screen)
            self.assertIs(App.current(), app)
            other = pygame.Surface((10, 10))
            app.set_screen(other)
            self.assertIs(app.services.get("screen"), other)
        finally:
            app.shutdown()
        self.assertIsNone(App.current())


class RunSceneTest(unittest.TestCase):
    def _app(self):
        from engine.core.app import App
        from engine.core.config import Settings
        return App(Settings.load(env={}, overrides={"crash_dir": self._tmp}))

    def setUp(self):
        import tempfile
        self._tmp = tempfile.mkdtemp()

    def test_runs_until_done(self):
        class S:
            n = 0
            done = False

            def frame(self):
                self.n += 1
                self.done = self.n >= 5
        s = S()
        self.assertEqual(self._app().run_scene(s), 0)
        self.assertEqual(s.n, 5)

    def test_crash_report_then_reraise(self):
        class Boom:
            done = False

            def frame(self):
                raise ValueError("boom")
        with self.assertRaises(ValueError):
            self._app().run_scene(Boom())
        self.assertTrue(os.listdir(self._tmp))

    def test_system_exit_passes_through(self):
        class Exit:
            done = False

            def frame(self):
                raise SystemExit(0)
        with self.assertRaises(SystemExit):
            self._app().run_scene(Exit())
        self.assertFalse(os.listdir(self._tmp))


if __name__ == "__main__":
    unittest.main()
