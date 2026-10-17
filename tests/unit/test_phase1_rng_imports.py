"""Phase 1 checks: legacy rng stream (R6) and m3 import side effects (B-010)."""
import os
import random
import subprocess
import sys
import unittest
from pathlib import Path

from tests.unit import _path  # noqa: F401

from engine.core import LEGACY, LEGACY_RNG, App, RngStreams

ROOT = Path(__file__).resolve().parents[2]


class LegacyStreamTests(unittest.TestCase):
    def test_legacy_is_the_global_random_instance(self):
        # Same object -> game code routed through it keeps legacy seeding/sequence.
        self.assertIs(LEGACY_RNG, random.random.__self__)
        random.seed(1234)
        a = [random.random() for _ in range(3)]
        random.seed(1234)
        b = [LEGACY_RNG.random() for _ in range(3)]
        self.assertEqual(a, b)

    def test_app_adopts_legacy_and_reseed_leaves_it_alone(self):
        app = App()
        self.assertIs(app.rng.stream(LEGACY), LEGACY_RNG)
        random.seed(99)
        before = LEGACY_RNG.getstate()
        app.rng.reseed(5)
        self.assertEqual(LEGACY_RNG.getstate(), before)

    def test_named_streams_still_independent(self):
        r = RngStreams(3)
        self.assertIsNot(r.stream("ai"), LEGACY_RNG)


class M3ImportSideEffectTests(unittest.TestCase):
    def test_importing_m3_does_not_redirect_saves_or_env(self):
        code = (
            "import os, sys; sys.path.insert(0, 'src');"
            "from core import save_system as s, settings_store as t, profile_store as p;"
            "before = (s.SAVE_FILE, t.SAVE_FILE, p.PROFILE_FILE, os.environ.get('SDL_VIDEODRIVER'));"
            "import missions.m3;"
            "after = (s.SAVE_FILE, t.SAVE_FILE, p.PROFILE_FILE, os.environ.get('SDL_VIDEODRIVER'));"
            "print('SAME' if before == after else 'CHANGED %r -> %r' % (before, after))"
        )
        env = dict(os.environ, SDL_AUDIODRIVER="dummy", PYGAME_HIDE_SUPPORT_PROMPT="1",
                   ACA_SAVE_SUFFIX="_aetest")
        env["SDL_VIDEODRIVER"] = "dummy"
        r = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), env=env,
                           capture_output=True, text=True, timeout=120)
        self.assertIn("SAME", r.stdout, r.stdout[-800:] + r.stderr[-800:])


if __name__ == "__main__":
    unittest.main()
