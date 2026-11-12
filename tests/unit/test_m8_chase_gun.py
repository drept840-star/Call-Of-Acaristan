"""The mounted LMG must never pass through Biribel in the tractor chase.

The owner-reported bug: the gun went through the player in the M8 chase.
Root cause: the stock of the imported light machine gun runs 24 cm behind the
grip, and the infantry ``aim`` hold anchors the butt inside the shoulder
pocket, so the stock sat inside Biribel's chest at every yaw.  The fix is a
pintle configuration: the stock is cut from the drawn parts
(``chase_set.STOCK_CUT_Z``), the receiver's own rear plate stays and closes
the gun, and ``GRIPS['lmg']`` anchors out on the shoulder crest with the
support hand on the feed tray.

Run: python -m unittest tests.unit.test_m8_chase_gun -v
"""
import math
import unittest

from tests.unit import _helpers  # noqa: F401 (src path and headless SDL)

import engine3d.hold as H
from cutscenes import m6world3d as W
from engine3d import POSES
from missions.m8.revenge import chase3d as C
from missions.m8.revenge import chase_set as S

#: a vert is only a piercing vert beyond this depth (the pocket contact by
#: design sits within ~1 cm of the vest face)
TOL = 0.02

_VOLS = ("torso", "chest", "pelvis", "head")


def _parts():
    """(name, mesh, origin) for the drawn gun parts (cut applied)."""
    split = S._lmg_split()
    for k, o in (("body", S.LMG_PIVOT), ("can", S.LMG_CAN), ("cover", S.LMG_HINGE)):
        yield k, split[k], o


class ChaseGunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pygame  # headless display for font/config side effects
        if not pygame.get_init():
            pygame.init()
        try:
            pygame.display.set_mode((64, 64))
        except pygame.error:
            pass
        cls.hum = W.hum(C.BIRIBEL, flags=(C.GUN,))
        cls.scene = C.scene()
        cls.scene.begin()
        cls.scene.t = 4.0

    def test_stock_is_cut_from_the_drawn_gun(self):
        """A pintle gun is stockless: nothing is drawn behind the cut plane.

        ``z`` grows toward the muzzle, so every drawn vert must satisfy
        z >= STOCK_CUT_Z (parts are origin-relative: raw z = vert + origin)."""
        for name, mesh, origin in _parts():
            used = {i for f in mesh.faces for i in f[0]}
            for i in used:
                z = mesh.verts[i][2] + origin[2]
                self.assertGreaterEqual(z, S.STOCK_CUT_Z - 1e-9,
                                        "%s part draws stock tail vert z=%.3f" % (name, z))

    def test_the_cut_gun_is_closed_behind_the_grip(self):
        """The receiver's rear plate survives the cut, so no hole at the seam."""
        body, origin = S._lmg_split()["body"], S.LMG_PIVOT
        used = sorted({i for f in body.faces for i in f[0]})
        zs = [body.verts[i][2] + origin[2] for i in used]
        rear = [z for z in zs if z <= S.STOCK_CUT_Z + 0.05]
        self.assertTrue(rear, "the receiver rear plate disappeared with the stock")
        # the nearest rear face sits at the cut plane: a cap, not a gap
        self.assertGreaterEqual(min(rear), S.STOCK_CUT_Z - 0.005,
                                "rear plate at %.3f leaves a gap before %.2f"
                                % (min(rear), S.STOCK_CUT_Z))

    def _rig_pen(self, sc):
        """Worst drawn-gun vertex inside the drawn body for one rig state."""
        g = sc._rig()
        split = S._lmg_split()
        vols = H.body_volumes(self.hum, g["pose"], g["feet"], sc.yaw)
        lift = C._cover_lift(g["el"])
        worst = 0.0
        for k, o in (("body", S.LMG_PIVOT), ("can", S.LMG_CAN), ("cover", S.LMG_HINGE)):
            m = split[k]
            gp = g["gpitch"] - (lift if k == "cover" else 0.0)
            used = {i for f in m.faces for i in f[0]}
            for i in used:
                v = m.verts[i]
                q = (v[0] - S.LMG_PIVOT[0] + o[0], v[1] - S.LMG_PIVOT[1] + o[1],
                     v[2] - S.LMG_PIVOT[2] + o[2])
                w = S._xf(q, g["pivot"], g["gyaw"], gp)
                worst = max(worst, *(H._depth(vols[n], w, 0.0) for n in _VOLS))
        return worst

    def test_hold_never_passes_through_the_body_across_the_aim_envelope(self):
        """Sweep aim pitch: the drawn gun stays out of the man.

        Measured the way the frame is drawn (_rig: gun at the pintle, body at
        the derived feet), so the result matches the pixels."""
        sc, worst = self.scene, 0.0
        sc.z = 380.0
        sc.lane = 0.0
        sc.speed = 0.0
        for yaw in (0.0, 90.0, 180.0, 270.0):
            sc.yaw = yaw
            for pitch in (C.PITCH_LIM[0], -14.0, -3.0, 8.0, C.PITCH_LIM[1]):
                sc.pitch = pitch
                worst = max(worst, self._rig_pen(sc))
        self.assertLess(worst, TOL, "LMG hold pierces the body by %.3f m" % worst)

    def test_reload_blend_never_passes_through_the_body(self):
        """The belt change, end to end: gun on its pintle, spine bends and all.

        The rack keys reach the tray with the arm, never a torso lean (a
        spine=24 lean walked the chest 3.9 cm into the receiver)."""
        sc, worst = self.scene, 0.0
        sc.z = 380.0
        sc.lane = 0.0
        sc.speed = 0.0
        sc.yaw = 180.0
        for i in range(int(C.RELOAD_S * 10)):
            sc.reloading = C.RELOAD_S - 0.1 * (i + 1)
            worst = max(worst, self._rig_pen(sc))
        sc.reloading = 0.0
        # the rack stances themselves stay upright (guard the tune)
        for k0, k1 in zip(C.RELOAD_TRACK, C.RELOAD_TRACK[1:]):
            if k0[1].startswith("rack") and k1[1].startswith("rack"):
                pose = C._reload_keys(self.hum)[k0[1]]
                self.assertLessEqual(abs(pose.get("spine", 0.0)), 10.0,
                                     "rack key %s leans the torso again" % k0[1])
        self.assertLess(worst, TOL, "reload blend pierces by %.3f m" % worst)

    def test_live_rig_clears_the_body_over_the_full_chase_sweep(self):
        """The scene's own rig math (used by _draw_mount) across route/yaw."""
        sc, worst = self.scene, 0.0
        for z in (60.0, 380.0, 760.0, 1300.0, 1950.0):
            sc.z = z
            sc.lane = 0.0
            sc.speed = 0.0
            for yaw in range(0, 360, 24):
                sc.yaw = float(yaw)
                for pitch in (C.PITCH_LIM[0], -4.0, C.PITCH_LIM[1]):
                    sc.pitch = pitch
                    worst = max(worst, self._rig_pen(sc))
        self.assertLess(worst, TOL, "live rig pierces by %.3f m" % worst)

    def test_hands_stay_on_the_pintle_hold(self):
        """Grip in the right hand, support hand on the feed tray point.

        Measured through the live rig: the feet follow the gun, so the hand
        coincides with the drawn grip and the support hand with its point."""
        sc = self.scene
        sc.z = 380.0
        sc.lane = 0.0
        sc.speed = 0.0
        sc.reloading = 0.0
        for yaw in (0.0, 90.0, 180.0, 270.0):
            sc.yaw = yaw
            for pitch in (C.PITCH_LIM[0], -3.0, C.PITCH_LIM[1]):
                sc.pitch = pitch
                g = sc._rig()
                joints = self.hum.pose_world(g["pose"], g["feet"], sc.yaw,
                                             rifle_on=True)[1]
                grip = sc.gun_pt((0.0, 0.0, 0.0))   # the drawn gun's grip point
                self.assertLess(math.dist(joints["rhand"], grip), 0.01,
                                "right hand off the grip at yaw %.0f" % yaw)

    def test_ready_stance_keys_survive(self):
        """The chase's ready-based stance is a superset of POSES['ready'] keys."""
        pose = C._hold(self.hum, 0.0)
        for k in POSES["ready"]:
            self.assertIn(k, pose)

    def test_a_shot_renders_instead_of_faulting_the_scene(self):
        """game_draw force-finishes the chase on any exception, so a draw-time
        FX bug reads as 'shooting skips to the end of the mission'."""
        import pygame
        from core import config
        sc = self.scene
        sc._active, sc.paused, sc.dying = True, False, False
        sc.end_t = None
        sc.reloading = 0.0
        sc.t = max(sc.t, 1.0)
        sc.last_fire = sc.t - 0.01                    # player muzzle flash
        sc.firing = True
        sc.kick = 0.45
        sc.flashes = [(sc.t - 0.01, sc.biribel_pos(), 0.0)]   # enemy muzzle flash
        try:
            sc.draw(pygame.Surface((config.WIDTH, config.HEIGHT)))
        finally:
            sc.flashes = []
            sc.firing = False


class ChaseAdsTests(unittest.TestCase):
    """ADS (RMB) on the pintle LMG: the camera sits at the gunner's eye and
    looks down the gun at its front post, so the post is the reticle."""

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
        from core.state import STATE
        STATE.dt = 1.0 / 60.0
        sc = self.scene
        sc._active, sc.paused, sc.dying = True, False, False
        sc.end_t = None
        sc.wreck_t = None
        sc.reloading = 0.0
        sc.aiming = False
        sc.ads = 0.0
        sc.firing = False
        sc.t = 4.0
        sc.z = 380.0
        sc.lane = 0.0
        sc.speed = 0.0
        sc.yaw = 180.0
        sc.pitch = -3.0

    def _run(self, n):
        for _ in range(n):
            self.scene.update()

    def test_rmb_raises_and_lowers_the_sight(self):
        import pygame
        sc = self.scene
        sc.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3))
        self._run(40)
        self.assertGreater(sc.ads, 0.95)
        self.assertAlmostEqual(sc.camera()[2], C.ADS_FOV, places=1)
        sc.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=3))
        self._run(60)
        self.assertLess(sc.ads, 0.05)
        self.assertAlmostEqual(sc.camera()[2], 60.0, places=1)

    def test_reload_drops_the_sight_and_it_returns_after(self):
        sc = self.scene
        sc.aiming = True
        self._run(40)
        self.assertGreater(sc.ads, 0.95)
        sc.mag = 0
        sc._reload()
        self._run(30)
        self.assertLess(sc.ads, 0.1, "the sight stays up while he works the feed")
        self._run(int(C.RELOAD_S * 60) + 40)
        self.assertGreater(sc.ads, 0.95, "RMB held: the sight must come back up")

    def test_the_front_post_stays_on_the_aim_ray(self):
        """The sight picture is rigid: eye and gun turn together on the pintle,
        so the post sits on the crosshair at every yaw/pitch."""
        sc = self.scene
        sc.aiming = True
        self._run(40)
        for yaw in (0.0, 90.0, 180.0, 270.0):
            sc.yaw = yaw
            for pitch in (C.PITCH_LIM[0], -3.0, 8.0, C.PITCH_LIM[1]):
                sc.pitch = pitch
                eye, d = sc.aim_ray()
                p = sc.gun_pt(C.ADS_POST)
                v = tuple(p[i] - eye[i] for i in range(3))
                n = math.sqrt(sum(c * c for c in v))
                v = tuple(c / n for c in v)
                dot = sum(d[i] * v[i] for i in range(3))
                self.assertGreater(dot, math.cos(math.radians(0.5)),
                                   "post off the aim ray at yaw %.0f pitch %.0f"
                                   % (yaw, pitch))

    def test_ads_tightens_the_bloom_cone(self):
        from unittest.mock import patch
        sc = self.scene
        eye, d = sc.aim_ray()

        def dev(ads):
            sc.ads = ads
            with patch.object(C.random, "uniform", return_value=0.0), \
                    patch.object(C.random, "random", return_value=0.5):
                _o, dd = sc._spread(eye, d)
            return math.degrees(math.acos(max(-1.0, min(1.0, sum(d[i] * dd[i] for i in range(3))))))

        hip, aimed = dev(0.0), dev(1.0)
        self.assertGreater(hip, 0.0)
        self.assertAlmostEqual(aimed / hip, 1.0 - C.ADS_SPREAD, places=3)

    def test_ads_tightens_the_mouse_gain(self):
        import pygame
        sc = self.scene
        ev = pygame.event.Event(pygame.MOUSEMOTION, rel=(100, 0))
        sc.ads = 0.0
        y0 = sc.yaw
        sc.handle_event(ev)
        hip = sc.yaw - y0
        sc.ads = 1.0
        y0 = sc.yaw
        sc.handle_event(ev)
        aimed = sc.yaw - y0
        self.assertAlmostEqual(aimed / hip, 1.0 - C.ADS_SENS, places=3)

    def test_an_aimed_shot_renders_instead_of_faulting_the_scene(self):
        import pygame
        from core import config
        sc = self.scene
        sc.aiming = True
        self._run(40)
        sc.last_fire = sc.t - 0.01
        sc.firing = True
        sc.kick = 0.45
        sc.flashes = [(sc.t - 0.01, sc.biribel_pos(), 0.0)]
        try:
            sc.draw(pygame.Surface((config.WIDTH, config.HEIGHT)))
        finally:
            sc.flashes = []
            sc.firing = False


if __name__ == "__main__":
    unittest.main()
