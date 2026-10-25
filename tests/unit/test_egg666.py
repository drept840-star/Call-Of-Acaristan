"""Tests for the 3D "666" safe-keypad scare (ui/egg666_*.py).

The director, the sound synthesis and the kill switch need no GPU; the render
tests are skipped where there is no GL 3.3 context.  Run from the repo root:
    python -m unittest tests.unit.test_egg666 -q
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from ui import egg666_3d as egg  # noqa: E402
from ui import egg666_audio as snd  # noqa: E402
from ui import egg666_dir as D  # noqa: E402
from ui import egg666_fx as FX  # noqa: E402

try:
    from engine3d.gl import gl_available
    HAVE_GL = bool(gl_available())
except Exception:
    HAVE_GL = False


class TestDirector(unittest.TestCase):
    def test_same_seed_same_frames(self):
        a, b = D.make_plan(4242), D.make_plan(4242)
        self.assertEqual(a.wins, b.wins)
        self.assertEqual(a.stations, b.stations)
        for f in (0, 50, 120, 200, 262, 330, 395, 441, 520):
            self.assertEqual(D.lamp(f, a), D.lamp(f, b))
            self.assertEqual(D.pose(f, a), D.pose(f, b))
            self.assertEqual(D.eyes(f, a, D.lamp(f, a)), D.eyes(f, b, D.lamp(f, b)))

    def test_other_seed_other_scare(self):
        a, b = D.make_plan(1), D.make_plan(2)
        self.assertNotEqual(a.stations, b.stations)

    def test_opens_black_and_silent_then_one_flicker_without_the_demon(self):
        p = D.make_plan(7)
        self.assertTrue(all(D.lamp(f, p) == 0.0 and D.marks(f, 0.0) == 0.0 for f in range(0, 40)))
        lit = [f for f in range(0, 90) if D.lamp(f, p) > 0.0]
        self.assertTrue(lit and lit[0] >= 38)
        self.assertTrue(all(D.station(f, p) == 0 for f in range(0, 90)))
        self.assertTrue(all(max(D.eyes(f, p, D.lamp(f, p))) == 0.0 for f in range(0, 90)))

    def test_it_comes_nearer_at_every_flicker(self):
        p = D.make_plan(7)
        zs = [p.stations[i]["z"] for i in range(1, 6)]
        self.assertEqual(zs, sorted(zs, reverse=True))
        self.assertEqual([D.station(w[0], p) for w in p.wins], [0, 1, 2, 3, 4, 5])

    def test_eyes_gain_pairs(self):
        p = D.make_plan(7)
        e = [D.eyes(f, p, 1.0) for f in (100, 170, 220, 300, 360)]
        self.assertEqual(e[0][1], 0.0)                 # one pair at the start
        self.assertGreater(e[2][1], 0.0)               # a second pair nearer
        self.assertEqual(e[2][2], 0.0)
        self.assertGreater(e[4][2], 0.0)               # a third at the end
        self.assertGreater(e[4][0], e[0][0])           # and brighter

    def test_lamp_dies_in_beat_three(self):
        p = D.make_plan(7)
        self.assertTrue(all(D.lamp(f, p) == 0.0 for f in range(306, D.TOTAL)))

    def test_the_beat_boundaries_show_something(self):
        for seed in range(1, 40):
            p = D.make_plan(seed)
            self.assertGreater(D.lamp(90, p), 0.0, seed)             # 1.5 s: the first flicker, demon far
            self.assertEqual(D.station(90, p), 1)
            self.assertGreater(D.lamp(180, p), 0.0, seed)            # 3.0 s: nearer
            self.assertEqual(D.station(180, p), 3)
            self.assertGreater(max(D.eyes(300, p, D.lamp(300, p))), 0.0, seed)   # 5.0 s: the eyes in the dark

    def test_silence_before_the_lunge(self):
        self.assertEqual(D.demon_bed_level(D.QUIET_F + 3), 0.0)
        self.assertGreater(D.demon_bed_level(D.LUNGE_F + 1), 0.0)
        self.assertTrue(all(b < D.QUIET_F for b in D.BEATS))
        self.assertEqual(D.flash_rgb(D.LUNGE_F - 1), (0, 0, 0))
        self.assertGreater(D.flash_rgb(D.LUNGE_F)[0], 200)
        self.assertEqual(D.flash_rgb(D.LUNGE_F + 70), (0, 0, 0))
        self.assertLess(D.flash_rgb(D.LUNGE_F, 0.35)[0], 100)    # flash reduction

    def test_picture_dies_at_the_cut(self):
        p = D.make_plan(7)
        self.assertIsNone(D.post(499, p)["squeeze"])
        self.assertLess(D.post(505, p)["squeeze"], 0.5)

    def test_head_keeps_its_face_on_the_lens(self):
        p = D.make_plan(7)
        for f in (225, 300, 380, 395):
            P = D.pose(f, p)
            chain = P["lean_lo"] + P["lean_hi"] + P["n1"] + P["n2"] + P["n3"]
            self.assertLess(abs(chain + P["h_rx"]), 20.0, f)


class TestSound(unittest.TestCase):
    def test_every_sound_is_a_wav(self):
        import io
        import wave
        for name in snd.NAMES:
            data = snd._GEN[name]()
            with wave.open(io.BytesIO(data)) as w:
                self.assertEqual(w.getnchannels(), 2, name)
                self.assertGreater(w.getnframes(), snd.RATE // 4, name)
                self.assertTrue(any(w.readframes(w.getnframes())), name)


class TestFx(unittest.TestCase):
    def test_glow_is_a_light_sprite_that_adds(self):
        g = FX.glow((255, 36, 20), 0.1, 0.0, intensity=1.0, max_px=24)
        self.assertTrue(g.light and g.bounds_m == (0.1, 0.1) and g.bounds_cap_px == (24, 24))
        s = pygame.Surface((64, 64))
        g(s, 32, 32, 200.0, 3.0)
        self.assertGreater(s.get_at((32, 32))[0], 100)
        self.assertEqual(tuple(s.get_at((1, 1)))[:3], (0, 0, 0))
        dark = pygame.Surface((64, 64))
        FX.glow((255, 36, 20), 0.1, 0.0, intensity=0.0)(dark, 32, 32, 200.0, 3.0)
        self.assertEqual(tuple(dark.get_at((32, 32)))[:3], (0, 0, 0))

    def test_grade_lifts_black_to_the_ink_floor_and_present_fills_the_screen(self):
        s = pygame.Surface((32, 24))
        FX.grade(s)
        avg = pygame.transform.average_color(s)[:3]          # the dither averages out to the ink
        self.assertTrue(all(2 <= c <= 20 for c in avg), avg)
        dst = pygame.Surface((100, 70))
        s.fill((200, 100, 50))
        FX.present(s, dst)
        self.assertEqual(dst.get_size(), (100, 70))
        self.assertGreater(dst.get_at((50, 35))[0], 150)


class TestSwitch(unittest.TestCase):
    def test_kill_switch_means_2d(self):
        old = os.environ.get("ACA_EGG666_3D")
        os.environ["ACA_EGG666_3D"] = "0"
        try:
            self.assertFalse(egg.available())
            self.assertFalse(egg.begin(1, (320, 224), sound=False))
            self.assertFalse(egg.active())
            self.assertFalse(egg.frame(pygame.Surface((320, 224)), 50))
        finally:
            if old is None:
                os.environ.pop("ACA_EGG666_3D", None)
            else:
                os.environ["ACA_EGG666_3D"] = old


@unittest.skipUnless(HAVE_GL, "no GL 3.3 context")
class TestRender(unittest.TestCase):
    SIZE = (320, 224)

    def setUp(self):
        self.assertTrue(egg.begin(4242, self.SIZE, sound=False))
        self.screen = pygame.Surface(self.SIZE)

    def tearDown(self):
        egg.stop()

    def shot(self, f):
        self.assertTrue(egg.frame(self.screen, f))
        return pygame.image.tobytes(self.screen, "RGB")

    def test_black_where_it_should_be(self):
        black = bytes(self.SIZE[0] * self.SIZE[1] * 3)
        for f in (0, 20, 39, 508, 520, 539):
            self.assertEqual(self.shot(f), black, f)

    def test_lit_frames_have_a_picture(self):
        for f in (50, 150, 396, 450):
            self.assertTrue(any(self.shot(f)), f)

    def test_frames_are_reproducible(self):
        a = self.shot(396)
        self.shot(150)
        self.assertEqual(self.shot(396), a)
        egg.stop()
        self.assertTrue(egg.begin(4242, self.SIZE, sound=False))
        self.assertEqual(self.shot(396), a)

    def test_stop_is_idempotent_and_frame_fails_closed(self):
        egg.stop()
        egg.stop()
        self.assertFalse(egg.active())
        self.assertFalse(egg.frame(self.screen, 50))


@unittest.skipUnless(HAVE_GL, "no GL 3.3 context")
class TestHudCaller(unittest.TestCase):
    """hud.py stays a thin caller: the 3D scare, the kill switch and the mid-run fallback."""

    class _Stop(Exception):
        pass

    def setUp(self):
        from core.state import STATE
        from ui import hud
        pygame.init()                                  # other tests may have quit pygame
        pygame.display.set_mode((64, 64))
        self.STATE, self.hud = STATE, hud
        self.crashes = []
        self._saved = (hud._safe_666_fake_crash, hud.screen)
        hud._safe_666_fake_crash = lambda: self.crashes.append(1) or True
        hud.screen = pygame.Surface((hud.WIDTH, hud.HEIGHT))
        STATE.safe_keypad_code = "666"
        STATE.safe_666_active = False

    def tearDown(self):
        self.hud._egg3d_stop()
        self.hud._safe_666_fake_crash, self.hud.screen = self._saved
        self.STATE.safe_666_active = False
        egg.stop()

    def test_runs_in_3d_and_ends_in_the_crash(self):
        self.hud._submit_safe_keypad_code()
        self.assertTrue(self.hud.safe_666_3d_live())
        self.assertEqual(self.STATE.safe_666_timer, egg.TOTAL)
        for _ in range(egg.TOTAL):
            self.hud.draw_safe_keypad()
        self.assertEqual(self.crashes, [])
        self.assertEqual(self.STATE.safe_666_timer, 0)
        self.assertEqual(pygame.display.get_caption()[0], "DON'T LOOK BEHIND YOU")
        self.hud.draw_safe_keypad()
        self.assertEqual(self.crashes, [1])

    def test_kill_switch_runs_the_2d_scare(self):
        os.environ["ACA_EGG666_3D"] = "0"
        try:
            self.hud._submit_safe_keypad_code()
        finally:
            os.environ.pop("ACA_EGG666_3D", None)
        self.assertFalse(self.hud.safe_666_3d_live())
        self.assertEqual(self.STATE.safe_666_timer, 390)

    def test_a_failure_mid_run_falls_back_to_2d(self):
        hud = self.hud
        hud._submit_safe_keypad_code()
        for _ in range(60):
            hud.draw_safe_keypad()

        class Halt(Exception):
            pass

        def halt(*args, **kw):
            raise Halt()

        saved = hud._safe_666_loud_open
        hud._safe_666_loud_open = lambda: None
        hud.screen = type("LostScreen", (), {"fill": staticmethod(halt)})()   # presenting into it fails
        try:
            with self.assertRaises(Halt):                  # it fell through to the 2D frame
                hud.draw_safe_keypad()
        finally:
            hud._safe_666_loud_open = saved
        self.assertFalse(hud.safe_666_3d_live())
        self.assertFalse(egg.active())
        self.assertTrue(self.STATE.safe_666_active)
        self.assertEqual((self.STATE.safe_666_timer, self.STATE.safe_666_total_timer), (389, 390))


if __name__ == "__main__":
    unittest.main()
