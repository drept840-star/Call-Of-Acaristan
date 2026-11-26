"""Mission 8 Duty: Ucilev 3-phase gunship boss duel, gorge landmarks, and crash continuity."""
import math
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import tests.unit._helpers  # noqa: F401
from core.config import HEIGHT, WIDTH, audio
from core.state import STATE
from cutscenes import m8dutyfilms as DF
from missions.m8 import m8_audio as M8A
from missions.m8.duty import flight3d as F
from missions.m8.duty import flight_set as FS
from missions.m8.revenge import chase_set as CS


class UcilevBossTests(unittest.TestCase):
    def setUp(self):
        self._prev_cp = getattr(STATE, "m8_flight_cp", 0)
        self._prev_ucp = getattr(STATE, "m8_ucilev_cp", None)
        self._prev_dt = getattr(STATE, "dt", 1.0 / 60.0)
        self._prev_stage = getattr(STATE, "mission8_stage", None)
        STATE.dt = 1.0 / 60.0
        STATE.m8_flight_cp = 4
        STATE.m8_ucilev_cp = None
        self.sc = F.FlightScene()
        self.sc._active = True
        self.sc._setup(4)

    def tearDown(self):
        F.abort()
        STATE.m8_flight_cp = self._prev_cp
        STATE.m8_ucilev_cp = self._prev_ucp
        STATE.dt = self._prev_dt
        STATE.mission8_stage = self._prev_stage

    def _step(self, seconds):
        n = int(round(seconds * 60.0))
        for _ in range(n):
            self.sc.hull = F.HULL
            self.sc.update()

    def test_weakpoint_crit_vs_hull_armor_and_ray_aiming(self):
        u = self.sc.ucilev
        s0 = u["subs"]["spotlight"]
        self.sc.hurt_target(u, 100.0, hit_part=None)
        self.assertAlmostEqual(s0 - u["subs"]["spotlight"], 35.0, places=3)

        s1 = u["subs"]["spotlight"]
        self.sc.hurt_target(u, 100.0, hit_part="spotlight")
        self.assertAlmostEqual(s1 - u["subs"]["spotlight"], 125.0, places=3)

        # Aim directly at spotlight world anchor and fire
        self._step(2.5)
        eye = self.sc.eye()
        sp_w = CS._xf(
            F.UCILEV_ANCHORS["spotlight"],
            (u["x"], u["y"], u["z"]),
            u["yaw"], u["pitch"], u["roll"],
        )
        dx, dy, dz = sp_w[0] - eye[0], sp_w[1] - eye[1], sp_w[2] - eye[2]
        self.sc.gy = F.R._wrap(math.degrees(math.atan2(dx, dz)) - self.sc.mount_yaw())
        self.sc.gp = math.degrees(math.atan2(dy, math.hypot(dx, dz)))
        self.sc.ads = 1.0
        self.sc.heat = 0.0
        self.sc.last_fire = -9.0
        before = u["subs"]["spotlight"]
        self.sc._fire()
        self.assertLess(u["subs"]["spotlight"], before)
        self.assertEqual(self.sc.hit_kind, "head")

    def test_three_phase_progression_stagger_and_pod_salvo_payoff(self):
        u = self.sc.ucilev
        self.assertEqual(u["phase"], 1)
        self.assertTrue(u["light_on"])

        # Massive single hit breaks only Phase 1 and activates stagger immunity
        self.sc.hurt_target(u, 9999.0, hit_part="spotlight")
        self.assertEqual(u["phase"], 2)
        self.assertFalse(u["light_on"])
        self.assertEqual(u["maneuver"], "stagger")
        pods_before = (u["subs"]["pod_l"], u["subs"]["pod_r"])
        self.sc.hurt_target(u, 9999.0, hit_part="pod_l")
        self.assertEqual((u["subs"]["pod_l"], u["subs"]["pod_r"]), pods_before)

        # Advance past 1.5 s stagger; breaking 1 pod stays in Phase 2 and disables twin salvo
        self._step(1.6)
        self.sc.hurt_target(u, 9999.0, hit_part="pod_l")
        self.assertEqual(u["phase"], 2)
        self.assertEqual(u["subs"]["pod_l"], 0.0)
        self.assertGreater(u["subs"]["pod_r"], 0.0)

        u["maneuver"] = "pod_salvo"
        u["maneuver_t"] = 0.1
        u["maneuver_id"] += 1
        u["maneuver_fired_rk"] = -1
        u["rk_tele"] = False
        self._step(1.2)
        self.assertLess(u.get("salvo_at", -9.0), 0.0)

        # Break second pod -> Phase 3 + stagger
        self.sc.hurt_target(u, 9999.0, hit_part="pod_r")
        self.assertEqual(u["phase"], 3)
        self.assertEqual(u["maneuver"], "stagger")

        # Advance past stagger -> break turbine -> climax fakeout -> kill_shot -> shootdown -> win
        self._step(1.6)
        self.sc.hurt_target(u, 9999.0, hit_part="turbine")
        self.assertGreaterEqual(u["climax_t"], 0.0)
        self.assertEqual(u["maneuver"], "climax")

        for _ in range(60 * 8):
            if self.sc.done:
                break
            self.sc.hull = F.HULL
            self.sc.update()
        self.assertTrue(self.sc.kill_shot)
        self.assertGreaterEqual(self.sc.shootdown, 0.0)
        self.assertTrue(self.sc.done)
        self.assertEqual(self.sc.result, "win")

    def test_zero_stall_gorge_and_basin_orbit_continuity(self):
        for sec in (0.0, 25.0, 50.0, 72.5, 72.85, 73.0, 90.0, 120.0):
            self.sc.sec_t = sec
            self.sc.road_t = (F.SECTIONS[4][2] - F.SECTIONS[1][2]) / F.HELI_V + sec
            p = self.sc._heli_pos()
            vx, vy, vz = self.sc._heli_vel()
            spd = math.sqrt(vx * vx + vy * vy + vz * vz)
            self.assertGreaterEqual(spd, 24.0, f"stalled at sec_t={sec}")
            self.assertGreaterEqual(p[1], FS.surface_y(p[0], p[2]) + 14.0)

        # Verify smooth C1 handoff across z=5400 orbit entry (t_orb ~ 72.857 s)
        t_cross = (F.SECTIONS[4][3] - F.SECTIONS[4][2]) / F.UCILEV_V
        self.sc.sec_t = t_cross - 0.02
        self.sc.road_t = (F.SECTIONS[4][2] - F.SECTIONS[1][2]) / F.HELI_V + self.sc.sec_t
        p_pre = self.sc._heli_pos()
        y_pre = self.sc.mount_yaw()
        self.sc.sec_t = t_cross + 0.02
        self.sc.road_t = (F.SECTIONS[4][2] - F.SECTIONS[1][2]) / F.HELI_V + self.sc.sec_t
        p_post = self.sc._heli_pos()
        y_post = self.sc.mount_yaw()
        self.assertLess(math.dist(p_pre, p_post), 2.0)
        self.assertLess(abs(F.R._wrap(y_post - y_pre)), 2.5)

        # Verify Ucilev stays inside starboard bay & above terrain across active combat
        u = self.sc.ucilev
        for i in range(60 * 18):
            self.sc.hull = F.HULL
            self.sc.update()
            if i % 30 == 0 and u["alive"]:
                hp = self.sc._heli_pos()
                rel = F.R._wrap(F.R._yaw(u["x"] - hp[0], u["z"] - hp[2]) - self.sc._heli_yaw())
                self.assertGreaterEqual(rel, F.REL_YAW_LIM[0] - 2.0)
                self.assertLessEqual(rel, F.REL_YAW_LIM[1] + 2.0)
                self.assertGreaterEqual(u["y"], FS.surface_y(u["x"], u["z"]) + 10.0)

    def test_headless_draw_all_phases_and_crash_spin(self):
        surf = pygame.Surface((WIDTH, HEIGHT))
        u = self.sc.ucilev
        self.sc.draw(surf)
        u["phase"] = 2
        u["light_on"] = False
        u["subs"]["spotlight"] = 0.0
        u["subs"]["pod_l"] = 0.0
        self.sc.draw(surf)
        u["phase"] = 3
        u["subs"]["pod_r"] = 0.0
        self.sc.draw(surf)
        for tm_ms in (400, 1500, 3200):
            DF.crash_spin(surf, tm_ms)

    def test_gorge_landmarks_and_audio_cues(self):
        FS._build_corridor()
        fires = FS._CACHE.get("fires", ())
        beacons = FS._CACHE.get("beacons", ())
        searchlights = FS._CACHE.get("searchlights", ())
        self.assertTrue(any(3440.0 <= p[2] <= 3480.0 for p in fires))
        self.assertTrue(any(3800.0 <= p[2] <= 3840.0 for p in beacons))
        self.assertTrue(any(4260.0 <= p[2] <= 4300.0 for p in searchlights))
        self.assertTrue(any(4760.0 <= p[2] <= 4800.0 for p in beacons))
        for cue in ("m8_rotor_pass", "m8_subsys_boom"):
            pcm = M8A.shot_pcm(cue)
            self.assertEqual(pcm.ndim, 2)
            self.assertGreater(len(pcm), 10000)
        m8a = M8A.instance(audio)
        m8a.rotor_pass()
        m8a.subsys_boom()

    def test_subsystem_break_checkpoints_and_respawn(self):
        u = self.sc.ucilev
        self.assertIsNone(STATE.m8_ucilev_cp)

        def die_and_respawn():
            self.sc.hurt_hull(999.0)
            self.assertTrue(self.sc.dying)
            for _ in range(int(round(2.8 * 60.0))):
                self.sc.update()
            self.assertFalse(self.sc.dying)
            self.assertEqual(self.sc.hull, F.HULL)
            self.assertEqual(self.sc.flares, F.FLARES)

        # Break 1: spotlight -> Phase 2 checkpoint saved & restores directly into Phase 2
        self.sc.hurt_target(u, 9999.0, hit_part="spotlight")
        self.assertIsInstance(STATE.m8_ucilev_cp, dict)
        self.assertEqual(STATE.m8_ucilev_cp["phase"], 2)
        self.assertEqual(self.sc._cp_toast_label, "CHECKPOINT - SPOTLIGHT DOWN")
        die_and_respawn()
        u = self.sc.ucilev
        self.assertEqual(u["phase"], 2)
        self.assertFalse(u["light_on"])
        self.assertEqual(u["subs"]["spotlight"], 0.0)
        self.assertGreater(u["subs"]["pod_l"], 0.0)
        self.assertGreater(u["subs"]["pod_r"], 0.0)
        self.assertNotEqual(u["maneuver"], "dive")

        # Break 2: port pod -> mid-Phase 2 checkpoint preserves broken port pod only
        self.sc.hurt_target(u, 9999.0, hit_part="pod_l")
        self.assertEqual(self.sc._cp_toast_label, "CHECKPOINT - PORT POD DOWN")
        die_and_respawn()
        u = self.sc.ucilev
        self.assertEqual(u["phase"], 2)
        self.assertEqual(u["subs"]["pod_l"], 0.0)
        self.assertGreater(u["subs"]["pod_r"], 0.0)

        # Break 3: starboard pod -> Phase 3 turbine checkpoint
        self.sc.hurt_target(u, 9999.0, hit_part="pod_r")
        self.assertEqual(self.sc._cp_toast_label, "CHECKPOINT - TURBINE EXPOSED")
        die_and_respawn()
        u = self.sc.ucilev
        self.assertEqual(u["phase"], 3)
        self.assertEqual(u["subs"]["pod_l"], 0.0)
        self.assertEqual(u["subs"]["pod_r"], 0.0)
        self.assertGreater(u["subs"]["turbine"], 0.0)
        self.assertLess(u["climax_t"], 0.0)

        # Break 4: turbine -> climax is protected from fatal hull hits until win clears cp
        self.sc.hurt_target(u, 9999.0, hit_part="turbine")
        self.assertGreaterEqual(u["climax_t"], 0.0)
        self.sc.hurt_hull(999.0)
        self.assertFalse(self.sc.dying)
        for _ in range(60 * 8):
            if self.sc.done:
                break
            self.sc.update()
        self.assertTrue(self.sc.done)
        self.assertEqual(self.sc.result, "win")
        self.assertIsNone(STATE.m8_ucilev_cp)


if __name__ == "__main__":
    unittest.main()
