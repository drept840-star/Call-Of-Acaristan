"""The tractor chase traffic must be solid, enter from off-camera, and swerve
around wrecks only when the steering limit leaves room.

Owner-reported: the enemy cars drove straight through the destroyed ones.  The
fix adds circle push-out contacts (car/car, car/tractor+trailer, car/wreck),
spawns chasers past the renderer's draw cull so they drive in instead of popping
in, and a deterministic look-ahead swerve decided by reaction time plus the time
to shift one car width at the lateral steering cap.

Run: python -m unittest tests.unit.test_m8_chase_traffic -v
"""
import math
import unittest
from unittest.mock import patch

from tests.unit import _helpers  # noqa: F401 (src path and headless SDL)

from missions.m8.revenge import chase3d as C
from missions.m8.revenge import chase_set as S

DT = 1.0 / 60.0
EPS = 1e-6


def _car(sc, z, lat=0.0, gap=11.0, v=0.0, wrecked=False, kind="jeep"):
    e = sc._spawn(kind, lat, z=z, x=S.road_x(z) + lat)
    e["gap"], e["v"] = gap, v
    if wrecked:
        e["wrecked"], e["alive"] = True, False
    return e


def _dist(a, b):
    return math.hypot(a["x"] - b["x"], a["z"] - b["z"])


class ChaseTrafficTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pygame
        if not pygame.get_init():
            pygame.init()
        try:
            pygame.display.set_mode((64, 64))
        except pygame.error:
            pass
        cls.scene = C.scene()
        cls.scene.begin()

    def setUp(self):
        sc = self.scene
        sc.enemies = []
        sc.cp = 0
        sc.speed = C.SPEED
        sc.lane = 0.0
        sc.slew = 0.0
        sc.z = 200.0
        sc.hull = C.HULL
        sc.dying = False
        sc.end_t = None
        sc.wreck_t = None
        sc.t = 10.0

    def _cruise(self, sc, car, steps, break_z=None):
        """Step the traffic while the tractor pulls ahead at chase speed, so a
        car holding its gap cruises at SPEED (the real chase condition)."""
        for _ in range(steps):
            sc.z += C.SPEED * DT
            sc._enemy_move(DT)
            if break_z is not None and car["z"] > break_z:
                break

    # --- 1. solid bodies -------------------------------------------------------

    def test_two_cars_on_one_lane_never_overlap(self):
        sc = self.scene
        sc.speed = 0.0
        a = _car(sc, 100.5, gap=11.0)
        b = _car(sc, 99.5, gap=11.0)        # same lane, same gap: they stack
        sc.z = 100.0 + C.HITCH + 11.0       # target sits on the pair
        rr = S.CAR_R * 2.0
        for _ in range(240):
            sc._enemy_move(DT)
            self.assertGreaterEqual(_dist(a, b), rr - EPS,
                                    "two cars on one lane overlapped")

    def test_a_car_does_not_drive_through_the_trailer(self):
        sc = self.scene
        sc.z = 200.0
        (_lx, _ly, lz), _ = sc.trailer_pos()
        e = _car(sc, lz - 6.0, gap=0.0, v=C.SPEED)   # aimed straight at the trailer
        rr = S.CAR_R + S.TRAILER_R
        for _ in range(120):
            sc._enemy_move(DT)
            (cx, _cy, cz), _ = sc.trailer_pos()
            self.assertGreaterEqual(math.hypot(e["x"] - cx, e["z"] - cz), rr - EPS,
                                    "a car passed through the trailer")

    def test_a_hard_rear_end_wrecks_the_striking_car(self):
        sc = self.scene
        sc.z = 120.0                                        # inside CRASH_RANGE
        front = _car(sc, 100.0, v=1.0)
        back = _car(sc, 98.0, v=1.0 + C.CRASH_SPEED + 3.0)   # closing > CRASH_SPEED
        sc._resolve_contacts(DT)                            # impulse, no gap law
        self.assertTrue(back["wrecked"], "a hard rear-end must wreck the car")
        self.assertGreaterEqual(_dist(front, back), S.CAR_R * 2.0 - EPS)

    def test_a_hard_rear_end_far_back_is_only_a_bump(self):
        sc = self.scene
        sc.z = 100.0 + C.CRASH_RANGE + 50.0       # out of the fight: cars must arrive
        front = _car(sc, 100.0, v=1.0)
        back = _car(sc, 98.0, v=1.0 + C.CRASH_SPEED + 3.0)
        sc._resolve_contacts(DT)
        self.assertFalse(back["wrecked"] or front["wrecked"])
        self.assertGreaterEqual(_dist(front, back), S.CAR_R * 2.0 - EPS)

    def test_a_car_alongside_does_not_stop_its_neighbour(self):
        sc = self.scene
        _car(sc, 100.2, lat=-1.4, v=0.0)          # stopped beside, a hair ahead
        e = _car(sc, 100.0, lat=1.3, v=C.SPEED)
        self.assertGreater(sc._follow_cap(e), C.SPEED, "side-by-side cars deadlocked")

    def test_wrecks_despawn_once_lost_in_the_fog(self):
        sc = self.scene
        old = _car(sc, sc.z - S.FOG_END - 30.0, wrecked=True)
        live = _car(sc, sc.z - S.FOG_END - 30.0, v=C.SPEED)
        sc._enemy_update(DT)
        self.assertNotIn(old, sc.enemies)
        self.assertIn(live, sc.enemies)

    def test_a_soft_contact_shoves_but_does_not_wreck(self):
        sc = self.scene
        front = _car(sc, 100.0, v=2.0)
        back = _car(sc, 98.0, v=2.0 + C.CRASH_SPEED - 2.0)   # closing < CRASH_SPEED
        sc._resolve_contacts(DT)
        self.assertFalse(back["wrecked"], "a gentle contact must not wreck")
        self.assertFalse(front["wrecked"])
        self.assertGreater(front["v"], 2.0, "speed must transfer to the car ahead")
        self.assertLess(back["v"], 2.0 + C.CRASH_SPEED - 2.0, "the striker sheds speed")

    # --- 2. no pop-in ----------------------------------------------------------

    def test_chasers_spawn_past_the_draw_cull(self):
        sc = self.scene
        sc.yaw, sc.pitch, sc.ads = 180.0, -3.0, 0.0
        eye, _tgt, _fov = sc.camera()
        jeep = sc._spawn("jeep", 0.0)
        self.assertGreater(eye[2] - jeep["z"], S.FOG_END,
                           "a jeep spawned inside the fog: it would pop in")
        self.assertGreater(eye[2] - jeep["z"], S.FOG_END + 60.0,
                           "a jeep spawned inside the renderer's draw cull")

    def test_the_gun_truck_enters_from_its_side(self):
        sc = self.scene
        sc.yaw, sc.pitch, sc.ads = 180.0, -3.0, 0.0
        eye, _tgt, _fov = sc.camera()
        truck = sc._spawn("gun_truck", 2.0)
        self.assertGreater(eye[2] - truck["z"], S.FOG_END + 60.0)
        self.assertAlmostEqual(truck["x"] - S.road_x(truck["z"]), 34.0, places=3)
        self.assertEqual(truck["lat"], 2.0)        # merges to its lane as it drives in

    # --- 3. deterministic avoidance -------------------------------------------

    def test_the_swerve_decision_uses_the_steering_limit(self):
        sc = self.scene
        _car(sc, 40.0, lat=2.0, wrecked=True)      # a wrecked car in the right of the lane
        e = _car(sc, 0.0, lat=0.0, v=C.SPEED)
        self.assertLess(sc._avoid_lat(e), -0.5, "40 m of room at chase speed must swerve")
        sc.enemies = []
        _car(sc, 3.0, lat=2.0, wrecked=True)
        e = _car(sc, 0.0, lat=0.0, v=C.SPEED)
        self.assertEqual(sc._avoid_lat(e), e["lat"], "3 m is too close to react")

    def test_a_wreck_40m_ahead_is_steered_around(self):
        sc = self.scene
        sc.cp = 2
        wz = 1000.0
        wx = S.road_x(wz) + 2.0
        with patch.object(S, "wrecks", return_value=[(wx, wz)]):
            e = _car(sc, wz - 40.0, lat=0.0, gap=11.0)
            sc.z = e["z"] + C.HITCH + 11.0
            min_off = 0.0
            for _ in range(420):
                sc.z += C.SPEED * DT
                sc._enemy_move(DT)
                if wz - 10.0 < e["z"] < wz + 10.0:
                    min_off = min(min_off, e["x"] - S.road_x(e["z"]))
                if e["z"] > wz + 12.0:
                    break
            self.assertFalse(e["wrecked"], "the car had room to react but still crashed")
            self.assertLess(min_off, -0.8, "the car did not shift left to pass the wreck")

    def test_a_wreck_3m_ahead_at_chase_speed_is_hit(self):
        sc = self.scene
        sc.cp = 2
        wz = 1000.0
        with patch.object(S, "wrecks", return_value=[(S.road_x(wz), wz)]):
            e = _car(sc, wz - 3.0, lat=0.0, gap=11.0, v=C.SPEED)
            sc.z = e["z"] + C.HITCH + 11.0
            self._cruise(sc, e, 90)
            self.assertTrue(e["wrecked"], "too close to react: the car must take the hit")

    def test_a_wrecked_car_3m_ahead_is_hit(self):
        sc = self.scene
        sc.z = 135.0                               # clear of the trailer, inside CRASH_RANGE
        _car(sc, 100.0, lat=0.0, wrecked=True)
        e = _car(sc, 97.0, lat=0.0, gap=11.0, v=C.SPEED)
        for _ in range(90):
            sc._enemy_move(DT)
            if e["wrecked"]:
                break
        self.assertTrue(e["wrecked"], "a car must crash into a wreck it cannot react to")

    def test_traffic_is_deterministic(self):
        def run():
            sc = self.scene
            sc.enemies = []
            sc.cp = 2
            wz = 1000.0
            with patch.object(S, "wrecks", return_value=[(S.road_x(wz) + 2.0, wz)]):
                e = _car(sc, wz - 40.0, lat=0.0, gap=11.0)
                sc.z = e["z"] + C.HITCH + 11.0
                for _ in range(200):
                    sc.z += C.SPEED * DT
                    sc._enemy_move(DT)
            return (round(e["x"], 6), round(e["z"], 6), e["wrecked"])
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()