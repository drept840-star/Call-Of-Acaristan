"""Mission 8 Duty Mansion: security room layout, Andrei trigger, death & cash burst."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import math
import tests.unit._helpers  # noqa: F401
from engine3d import SoftwareRenderer
from missions.m8.duty import mansion3d as M3
from missions.m8.duty import mansion_brain as B
from missions.m8.duty import mansion_set as MS
from missions.m8.duty import mansion_world as W


class _StubScene:
    def __init__(self, px, py, pz):
        self.px, self.py, self.pz = px, py, pz
        self.t = 10.0
        self.kills = 0
        self.slowmo_until = -1.0
        self.world = W.World()
        self.sparks = []
        self.flashes = []
        self.said = []

    def say(self, who, text, dur):
        self.said.append((who, text, dur))

    def tracer(self, a, b):
        pass

    def flash(self, pos):
        pass

    def _snd(self, *args):
        pass

    def _pan(self, x, z):
        return 0.0

    def on_andrei_shot(self, a):
        pass

    def on_andrei_ceiling_shot(self, a):
        pass

    def on_andrei_rack_hit(self):
        pass

    def on_andrei_breaker_pop(self):
        pass

    def on_andrei_smoke(self, a, hot=True):
        pass


class MansionSecurityRoomTests(unittest.TestCase):
    def test_workstations_flush_and_within_desks(self):
        north_desk = (-10.9, -6.1, 34.1, 35.1)
        west_desk = (-11.35, -10.45, 27.7, 30.3)
        for pos, yaw, pc, mon in MS.WORKSTATIONS:
            self.assertAlmostEqual(pos[1], MS.GF + 0.78, places=4)
            if abs(yaw - 180.0) < 1.0:
                x0, x1, z0, z1 = north_desk
            else:
                x0, x1, z0, z1 = west_desk
            self.assertGreaterEqual(pos[0] - 0.25, x0)
            self.assertLessEqual(pos[0] + 0.25, x1)
            self.assertGreaterEqual(pos[2] - 0.42, z0)
            self.assertLessEqual(pos[2] + 0.42, z1)
        # Matching desk colliders exist in mansion_world.STATIC
        self.assertIn((-10.9, 34.1, -6.1, 35.1, MS.GF, MS.GF + 0.78), W.STATIC)
        self.assertIn((-11.35, 27.7, -10.45, 30.3, MS.GF, MS.GF + 0.78), W.STATIC)

    def test_andrei_trigger_rejects_exterior_and_requires_los(self):
        for pt in ((-14.5, 0.0, 31.0), (-8.0, 0.0, 37.5), (-8.0, MS.FF, 31.0), (-6.0, MS.GF, 25.0)):
            sc = _StubScene(*pt)
            br = B.Brain(sc, cp=1)
            br._andrei_update(sc.t)
            self.assertEqual(br.andrei["state"], "idle", msg=f"Triggered unexpectedly at {pt}")

        # Inside security room doorway with LOS triggers intro
        sc = _StubScene(-6.0, MS.GF, 28.0)
        br = B.Brain(sc, cp=1)
        br._andrei_update(sc.t)
        self.assertEqual(br.andrei["state"], "intro")

    def test_cp2_starts_with_andrei_already_dead(self):
        sc = _StubScene(0.0, MS.GF, 16.2)
        br = B.Brain(sc, cp=2)
        self.assertEqual(br.andrei["state"], "done")
        self.assertLess(br.andrei["dead_t"], -10.0)
        self.assertTrue(br.andrei["rack_hit"])
        br._andrei_update(0.5)
        self.assertEqual(br.andrei["state"], "done")

    def test_andrei_cannot_be_shot_while_idle_from_outside_room(self):
        sc = M3.MansionScene()
        sc._setup(1)
        an = sc.brain.andrei
        tgt = (an["x"], an["y"] + 1.15, an["z"])

        def _aim_at_andrei():
            sc.ads = 1.0
            sc.heat = 0.0
            sc.cam_kick = 0.0
            for _ in range(3):
                o, _ = sc._aim_ray()
                dx, dy, dz = tgt[0] - o[0], tgt[1] - o[1], tgt[2] - o[2]
                sc.yaw = math.degrees(math.atan2(dx, dz))
                sc.pitch = math.degrees(math.atan2(dy, math.hypot(dx, dz)))

        # Outside the security room in the Grand Hall with direct doorway sightline
        sc.px, sc.py, sc.pz = -5.5, MS.GF, 20.0
        sc.body_yaw = 0.0
        _aim_at_andrei()
        sc._fire()
        self.assertEqual(an["state"], "idle")

        # Inside the security room: player shot triggers his death
        sc.px, sc.py, sc.pz = -6.0, MS.GF, 28.0
        sc.last_fire = -9.0
        _aim_at_andrei()
        sc._fire()
        self.assertEqual(an["state"], "dying")
        self.assertEqual(an["cause"], "player")

    def test_player_shot_vs_misfire_and_cash_burst_bounds(self):
        sc = M3.MansionScene()
        sc._setup(1)
        sc.px, sc.py, sc.pz = -6.0, MS.GF, 28.0
        self.assertTrue(sc.brain.trigger_andrei_death(cause="player", hit_zone="head"))
        self.assertEqual(sc.brain.andrei["cause"], "player")
        self.assertEqual(sc.brain.andrei["hit_zone"], "head")

        sc.on_andrei_rack_hit()
        self.assertEqual(len(sc.cash_bricks), 7)
        self.assertGreaterEqual(len(sc.cash_notes), 35)
        for _ in range(180):
            sc._step_cash(1.0 / 60.0)
        for b in sc.cash_bricks:
            self.assertGreaterEqual(b["x"], -11.41)
            self.assertLessEqual(b["x"], -3.94)
            self.assertGreaterEqual(b["y"], MS.GF)
        for n in sc.cash_notes:
            self.assertTrue(n["settled"])
            self.assertGreaterEqual(n["y"], MS.GF)

    def test_dynamic_rack_and_surge_software_render(self):
        r = SoftwareRenderer(320, 200)
        r.begin()
        MS.draw_dynamic_props(r, 1200.0, cams_alive=True, rack_state=("surge", 5.2, 1), monitor_surge=2)
        MS.draw_dynamic_props(r, 2400.0, cams_alive=False, rack_state=("ember", 5.0, 0), monitor_surge=0)
        r.flush()


if __name__ == "__main__":
    unittest.main()
