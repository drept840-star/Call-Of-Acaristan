"""M8 trap scene: the plaza fight's new mechanics.

Covers the Route 12 trap set's props and beats: the fuel drums, the plaza
floodlights and their fusebox, the toll kiosk that opens the north lane, the
Guard convoy truck's hull, the Guard smoke canisters they answer a camper
with, the overwatch laser lock and the two-gun swap.

Run: python -m unittest tests.unit.test_m8_trap_mechanics -v
"""
import unittest

from tests.unit import _helpers  # noqa: F401 (src path and headless SDL)

import pygame
from core.outfits import OUTFIT_GUARD
from core.state import STATE
from cutscenes import m6world3d as _w
from missions.m7 import raid3d as R
from missions.m8.revenge import set3d as S3
from missions.m8.revenge import trap3d as TR
from missions.m8.revenge import trap_world as W


class _Keys(dict):
    def __getitem__(self, key):
        return self.get(key, False)


class TrapMechanicsTests(unittest.TestCase):
    def setUp(self):
        STATE.dt = 1.0 / 60.0
        STATE.m8_trap_cp = 0        # the scene resumes from this checkpoint
        self.sc = TR.TrapScene()
        self.sc.begin()

    def _run(self, frames, keys=None):
        for _ in range(frames):
            self.sc.update(keys or _Keys())

    def test_wave_one_turns_the_floodlights_on(self):
        self._run(260)
        self.assertEqual(self.sc.phase, "w1")
        self.assertTrue(self.sc.floods_on)
        self.assertTrue(any(self.sc.flood_poles))
        self.assertGreater(self.sc.brain.alive_count(), 0)

    def test_the_fusebox_kills_the_plaza_lights(self):
        self._run(260)
        self.sc._kill_power(None)
        self.assertFalse(self.sc.floods_on)
        self.assertFalse(any(self.sc.flood_poles))

    def test_a_fuel_drum_detonates_and_leaves_the_plaza(self):
        self._run(260)
        bar = self.sc.barrels[0]
        self.sc._detonate_barrel(bar)
        self.assertFalse(bar["alive"])
        self.assertIsNone(self.sc.world.props[bar["prop_idx"]])

    def test_the_toll_kiosk_opens_the_north_lane_and_starts_wave_two(self):
        self._run(260)
        self.sc.phase = "advance1"
        self.sc.px, self.sc.pz = W.KIOSK_AT[0], W.KIOSK_AT[1] - 2.0
        self.assertEqual(self.sc._hold_action(), "kiosk")
        self.sc._open_gate()
        self.assertTrue(self.sc.gate_open)
        self.assertEqual(self.sc.phase, "w2")
        self.assertEqual(self.sc.cp, 1)
        self.assertEqual(STATE.m8_trap_cp, 1)

    def test_the_guard_truck_crashes_when_its_hull_is_gone(self):
        self._run(260)
        self.sc.phase = "advance1"
        self.sc._open_gate()
        self._run(60 * 14)
        truck = self.sc.brain.trucks[0]
        self.assertIn(truck["state"], ("drive", "stopped"))
        self.sc.brain.damage_truck(truck, 500.0)
        self.assertTrue(truck["crashed"])

    def test_clearing_wave_one_opens_the_north_lane(self):
        self._run(260)
        self.sc._clear(1)
        self.assertEqual(self.sc.phase, "advance1")
        self.assertTrue(self.sc.gate_open)
        # the kiosk is still usable while wave 2 has not rolled in
        self.sc.px, self.sc.pz = W.KIOSK_AT[0], W.KIOSK_AT[1] - 2.0
        self.assertEqual(self.sc._hold_action(), "kiosk")

    def test_camping_brings_a_smoke_canister_and_breaks_the_lock(self):
        self._run(260)
        self.sc.brain.enemies = []
        self.sc.brain.add("rifle", self.sc.px + 12.0, self.sc.pz + 4.0, [], 0.0, 1)
        self.sc._camp_pos = (self.sc.px, self.sc.pz)
        self.sc._camp_t = 0.0
        self.sc._smoke_cd = 0.0
        self._run(60 * 7)
        self.assertTrue(self.sc.smokes)
        self.assertTrue(self.sc.in_smoke(self.sc.px, self.sc.pz))

    def test_the_overwatch_snipers_telegraph_before_they_shoot(self):
        self._run(260)
        self.sc.brain.enemies = []
        ow = self.sc.brain.add("overwatch", -0.8, 57.1, [], 0.0, 1)
        self.sc.px, self.sc.pz = -20.0, 20.0
        self._run(90)
        self.assertTrue(ow["tele"] > 0.0 or ow["left"] > 0)

    def test_the_two_guns_swap_and_keep_their_own_ammo(self):
        self.sc.weapon = "shotgun"
        self.sc._sync_weapon_attrs()
        self.sc._switch_weapon("rifle")
        self.assertEqual(self.sc.weapon, "rifle")
        self.assertEqual(self.sc.MAG, 30)
        self.assertEqual(self.sc.wpns["shotgun"][0], 6)
        self.sc._switch_weapon("shotgun")
        self.assertEqual(self.sc.weapon, "shotgun")
        self.assertEqual(self.sc.MAG, 6)
        self.assertEqual(self.sc.wpns["rifle"][0], 30)

    def test_a_body_is_looted_for_both_calibres(self):
        self._run(260)
        self.sc.brain.enemies = []
        e = self.sc.brain.add("rifle", self.sc.px + 1.0, self.sc.pz, [], 0.0, 1)
        e["alive"] = False               # a body, not a live Guard
        e["mags"] = 1
        self.sc._loot()
        self.assertEqual(e["mags"], 0)
        self.assertGreater(self.sc.wpns["shotgun"][1], 24)
        self.assertGreater(self.sc.wpns["rifle"][1], 90)

    def test_ladder_climb_contacts_actual_rungs_and_rails(self):
        hum = _w.hum(("biribel", OUTFIT_GUARD), flags=("shotgun",))
        # Mid-climb rung step boundaries (steps 1..20): planted foot & planted hand sit on exact rungs.
        for step in (2, 7, 14, 19):
            u = (step + 0.99) / 21.0 * S3.LADDER_CLIMB_UP
            pose, pos, yaw, _rung = S3.ladder_climb(hum, u)
            _pl, joints, _root = hum.pose_world(pose, pos, yaw, rifle_on=False)
            # Lower foot sole rests directly on rung (step - 1) top (+0.02 m)
            self.assertAlmostEqual(pos[1], S3.LADDER_RUNG_YS[step - 1] + 0.02, delta=0.02)
            # Supporting hand sits on rung (step + 4) (or upper rail past rung 22)
            grip_idx = step + 4
            side_key = "lhand" if step % 2 == 0 else "rhand"
            sx = -1 if step % 2 == 0 else 1
            want_hand = S3._ladder_hand_pt(grip_idx, sx)
            hand = joints[side_key]
            dist = sum((hand[i] - want_hand[i]) ** 2 for i in range(3)) ** 0.5
            self.assertLess(dist, 0.035)
        # Top of climb finishes standing cleanly on the catwalk deck
        _pose, pos_end, _yaw_end, _r = S3.ladder_climb(hum, 1.0)
        self.assertAlmostEqual(pos_end[1], S3.CATWALK_Y, places=3)
        self.assertAlmostEqual(pos_end[2], S3.CATWALK_Z - 0.15, places=3)

    def test_shotgun_reload_matches_exact_shells_loaded(self):
        self.sc.weapon = "shotgun"
        self.sc._sync_weapon_attrs()
        # Partial reload (1 shell): short duration, no dry pump, exact 1 shell taken
        self.sc.mag, self.sc.reserve = 5, 10
        self.sc._begin_reload()
        self.assertAlmostEqual(self.sc.reload_total(), R.sg_reload_dur(1, False), places=4)
        self.assertFalse(self.sc._reload_dry)
        self._run(60)
        self.assertEqual(self.sc.reloading, 0.0)
        self.assertEqual(self.sc.mag, 6)
        self.assertEqual(self.sc.reserve, 9)

        # Empty reload limited by reserve (only 2 shells left -> loads 2, pumps once)
        self.sc.mag, self.sc.reserve = 0, 2
        self.sc._begin_reload()
        self.assertAlmostEqual(self.sc.reload_total(), R.sg_reload_dur(2, True), places=4)
        self.assertTrue(self.sc._reload_dry)
        self._run(120)
        self.assertEqual(self.sc.reloading, 0.0)
        self.assertEqual(self.sc.mag, 2)
        self.assertEqual(self.sc.reserve, 0)

    def test_partial_shotgun_reload_can_be_interrupted_after_shell_seats(self):
        self.sc.weapon = "shotgun"
        self.sc._sync_weapon_attrs()
        self.sc.mag, self.sc.reserve = 2, 10
        self.sc._begin_reload()
        # Run until 1 shell has seated (~0.50 s = 30 frames)
        self._run(32)
        self.assertEqual(self.sc.mag, 3)
        self.assertGreater(self.sc.reloading, 0.0)
        ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0))
        self.sc.handle_event(ev)
        self.assertEqual(self.sc.reloading, 0.0)
        self.assertEqual(self.sc.mag, 3)
        self.assertEqual(self.sc.reserve, 9)


if __name__ == "__main__":
    unittest.main()
