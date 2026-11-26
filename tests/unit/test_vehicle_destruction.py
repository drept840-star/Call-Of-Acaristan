"""Unit tests for the shared engine.render3d vehicle destruction system."""
from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import pygame
from cutscenes import m6fx3d as _fx  # noqa: E402
from engine.render3d import (  # noqa: E402
    VEHICLE_PROFILES,
    VehicleDestructionManager,
    get_vehicle_profile,
)
from engine3d import SoftwareRenderer  # noqa: E402
from game.vehicle_fx import default_vehicle_fx  # noqa: E402


class VehicleDestructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((320, 200))

    def test_all_profiles_and_aliases(self):
        expected = {
            "car", "jeep", "truck", "gun_truck", "aa_truck",
            "tanker", "gunship", "gunship_air", "tractor",
        }
        self.assertEqual(set(VEHICLE_PROFILES.keys()), expected)
        self.assertEqual(get_vehicle_profile("aa").kind, "aa_truck")
        self.assertEqual(get_vehicle_profile("blocker").kind, "jeep")
        self.assertEqual(get_vehicle_profile("heli").kind, "gunship")
        self.assertEqual(get_vehicle_profile("vip_heli").kind, "gunship_air")
        self.assertEqual(get_vehicle_profile("unknown_vehicle").kind, "car")

    def test_signature_parts_per_vehicle_kind(self):
        mgr = VehicleDestructionManager(seed=42)
        mgr.trigger("aa_truck", (0.0, 0.0, 0.0), tag="aa")
        self.assertIn("aa_turret", {p.shape for p in mgr.parts})

        mgr.clear()
        mgr.trigger("gunship", (0.0, 0.0, 0.0), tag="heli")
        shapes = {p.shape for p in mgr.parts}
        self.assertIn("rotor_blade", shapes)
        self.assertIn("tail_boom", shapes)

        mgr.clear()
        mgr.trigger("tanker", (0.0, 0.0, 0.0), tag="tank")
        shapes = {p.shape for p in mgr.parts}
        self.assertIn("tanker_cap", shapes)
        self.assertIn("tanker_rib", shapes)

        mgr.clear()
        mgr.trigger("car", (0.0, 0.0, 0.0), paint=(40, 80, 120), tag="car")
        shapes = {p.shape for p in mgr.parts}
        self.assertIn("hood", shapes)
        self.assertIn("door", shapes)
        self.assertIn("wheel", shapes)
        self.assertTrue(any(p.paint == (40, 80, 120) for p in mgr.parts))

    def test_momentum_inheritance_and_floor_settle(self):
        mgr = VehicleDestructionManager(seed=7)
        mgr.trigger("jeep", (0.0, 0.0, 0.0), vel=(0.0, 0.0, 24.0))
        self.assertGreater(len(mgr.parts), 0)
        mean_vz = sum(p.vel[2] for p in mgr.parts) / len(mgr.parts)
        self.assertGreater(mean_vz, 15.0)

        floor_fn = lambda x, z: 1.5
        for _ in range(180):
            mgr.update(1.0 / 60.0, floor_fn=floor_fn)
        self.assertTrue(all(p.pos[1] >= 1.5 for p in mgr.parts))
        self.assertTrue(any(p.settled for p in mgr.parts))

    def test_hull_hop_and_sag_for_stationary_car(self):
        mgr = VehicleDestructionManager(seed=9)
        mgr.trigger("car", (2.0, 0.0, 4.0), tag="c1")
        mgr.update(0.12)
        dy_hop, dp_hop, _ = mgr.hull_transform("c1")
        self.assertGreater(dy_hop, 0.0)
        self.assertLess(dp_hop, 0.0)

        for _ in range(40):
            mgr.update(0.02)
        dy_rest, _, _ = mgr.hull_transform("c1")
        self.assertLess(dy_rest, -0.10)

    def test_cookoff_triggers_once_and_sync_pose(self):
        fired = []
        mgr = VehicleDestructionManager(seed=11)
        mgr.trigger(
            "aa_truck", (0.0, 0.0, 0.0), tag="aa1", follow=True,
            on_cookoff=lambda vd, ck: fired.append((vd.kind, ck.delay_s)),
        )
        self.assertEqual(fired, [])
        mgr.sync_pose("aa1", (5.0, 1.0, 12.0), yaw=45.0, pitch=2.0, roll=-5.0)
        for _ in range(120):
            mgr.update(0.02)
        self.assertEqual(len(fired), 2)
        lights = mgr.active_lights()
        self.assertGreater(len(lights), 0)
        self.assertAlmostEqual(lights[0]["pos"][0], 5.0, places=2)

    def test_software_render_standalone_and_with_game_fx(self):
        for fx in (None, default_vehicle_fx(), default_vehicle_fx(_fx)):
            mgr = VehicleDestructionManager(seed=21, fx=fx)
            for idx, kind in enumerate(("car", "aa_truck", "tanker", "gunship")):
                mgr.trigger(kind, (-6.0 + idx * 4.0, 0.0, 14.0), paint=(70, 90, 110), tag=(kind, idx))
            mgr.update(0.08)
            r = SoftwareRenderer(320, 200)
            r.set_camera((0.0, 4.0, -4.0), (0.0, 1.2, 14.0), 60.0)
            r.begin()
            mgr.draw(r, 80.0)
            surf = pygame.Surface((320, 200))
            surf.fill((10, 12, 18))
            r.flush(surf)
            # Confirm explosion/parts painted visible pixels
            non_bg = any(surf.get_at((x, y))[:3] != (10, 12, 18)
                         for x in range(40, 280, 16) for y in range(40, 180, 16))
            self.assertTrue(non_bg)


if __name__ == "__main__":
    unittest.main()
