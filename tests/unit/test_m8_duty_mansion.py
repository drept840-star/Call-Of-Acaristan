"""Mission 8 Duty Mansion: security room layout, Andrei trigger, death & cash burst."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import math
import tests.unit._helpers  # noqa: F401
from engine3d import Mesh, SoftwareRenderer
from engine3d.core import v_cross, v_sub
from missions.m8.duty import mansion3d as M3
from missions.m8.duty import mansion_brain as B
from missions.m8.duty import mansion_props as MP
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

    def test_andrei_player_shot_timing_pistol_mesh_and_anim(self):
        hit_s, zap_s, sit_s, down_s = B.andrei_timings("player")
        self.assertGreaterEqual(hit_s, 1.3)
        self.assertLess(hit_s, zap_s)
        self.assertLess(zap_s, sit_s)
        self.assertLess(sit_s, down_s)

        pm = MS.pistol_mesh()
        self.assertGreater(len(pm.faces), 20)

        # Smooth yaw turn + single-eased backpedal (no instant full-distance snap)
        _p0, off0, y0 = M3._andrei_death_anim(0.05, cause="player", shot_yaw=135.0, had_gun=True)
        _p1, off1, y1 = M3._andrei_death_anim(hit_s * 0.5, cause="player", shot_yaw=135.0, had_gun=True)
        _p2, off2, y2 = M3._andrei_death_anim(hit_s, cause="player", shot_yaw=135.0, had_gun=True)
        self.assertGreater(y0, 95.0)
        self.assertAlmostEqual(y2, 90.0, places=2)
        self.assertLess(abs(off0[0]), 0.15)
        self.assertLess(abs(off1[0]), abs(M3.ANDREI_RACK_DX) * 0.45)
        # at hit_s the pinned-rack shake takes over, adding up to 0.025 m of jitter
        self.assertLess(abs(off2[0] - M3.ANDREI_RACK_DX), 0.03)

        # Dropped pistol settles on the floor and stops moving
        p0 = (-7.35, MS.GF + 1.22, 31.35)
        pos_a, _ = M3._dropped_pistol_xform(1.2, p0, 90.0, MS.GF + 0.032)
        pos_b, _ = M3._dropped_pistol_xform(3.0, p0, 90.0, MS.GF + 0.032)
        self.assertEqual(pos_a, pos_b)
        self.assertAlmostEqual(pos_a[1], MS.GF + 0.032, places=4)

    def test_dynamic_rack_and_surge_software_render(self):
        r = SoftwareRenderer(320, 200)
        r.begin()
        MS.draw_dynamic_props(r, 1200.0, cams_alive=True, rack_state=("surge", 5.2, 1), monitor_surge=2)
        MS.draw_dynamic_props(r, 2400.0, cams_alive=False, rack_state=("ember", 5.0, 0), monitor_surge=0)
        r.flush()


    def test_study_door_kick_animation_doors_and_furniture(self):
        import pygame
        sc = M3.MansionScene()
        sc._setup(3)
        sc._active = True  # update() gates on _active; _setup alone leaves it False
        sc.px, sc.pz, sc.yaw, sc.body_yaw = 0.0, 27.6, 0.0, 0.0
        self.assertEqual(sc._hold_action(), "study_door")
        self.assertFalse(sc.world.study_open)

        # Trigger kick via [E] edge
        keys = {pygame.K_e: True}
        sc._hold(keys, 1.0 / 60.0)
        self.assertIsNotNone(sc.study_kick_t)
        self.assertFalse(sc.world.study_open)

        # Chambering right leg during wind-up, full extension at kick hit
        hum = M3._w.hum(("biribel", M3.OUTFIT_GUARD), flags=("os12", "nomag"))
        p_wind = sc._door_kick_pose(hum, M3.POSES["ready"], 0.16, False)
        p_hit = sc._door_kick_pose(hum, M3.POSES["ready"], M3.KICK_HIT_S, False)
        self.assertGreater(p_wind["rhip_p"], 70.0)
        self.assertGreater(p_wind["rkn"], 80.0)
        self.assertGreater(p_hit["rhip_p"], 70.0)
        self.assertLess(p_hit["rkn"], 20.0)

        # Step past impact: doors unlock, splinters spawn on FF, wave 5 begins
        for _ in range(30):
            sc.update({pygame.K_e: False})
        self.assertTrue(sc.world.study_open)
        self.assertEqual(sc.phase, "study")
        self.assertGreater(len(sc.debris), 5)

        # Doors & furniture build flush and detailed
        l0, r0 = MP.study_door_angles(0.0)
        l1, r1 = MP.study_door_angles(1.0)
        self.assertEqual((l0, r0), (0.0, 0.0))
        self.assertLess(l1, -80.0)
        self.assertGreater(r1, 90.0)
        for builder in (MP.dining_chair, MP.four_poster_bed, MP.study_desk, MP.executive_chair):
            mesh = builder()
            min_y = min(v[1] for v in mesh.verts)
            self.assertGreaterEqual(min_y, -0.02)

        # Retardovici's portrait renders the angled 3D model onto a flat 2D framed canvas
        wide_p = MP.president_portrait(2.2, 1.6, (46, 56, 40))
        self.assertGreater(len(wide_p.faces), 180)
        xs = [v[0] for v in wide_p.verts]
        zs = [v[2] for v in wide_p.verts]
        self.assertLessEqual(max(xs) - min(xs), 2.38)
        self.assertLessEqual(max(zs) - min(zs), 0.06)
        # Canvas quads (at z=-0.028) must face -Z so neither GL nor Software backface-culls them
        canvas_faces = [
            f for f in wide_p.faces
            if all(abs(wide_p.verts[i][2] + 0.028) < 1e-4 for i in f[0])
        ]
        self.assertGreater(len(canvas_faces), 150)
        for f in canvas_faces:
            a, b, c = (wide_p.verts[i] for i in f[0][:3])
            nrm = v_cross(v_sub(b, a), v_sub(c, a))
            self.assertLess(nrm[2], 0.0)
        # Render from -Z and verify non-frame portrait colours appear on screen
        sr = SoftwareRenderer(64, 64)
        sr.set_camera((0.0, 0.0, -2.5), (0.0, 0.0, 0.0), 45.0)
        sr.bake(wide_p)
        sr.begin()
        sr.add_static()
        sr.surface.fill((255, 0, 255))
        sr.flush()
        center_col = sr.surface.get_at((32, 32))[:3]
        self.assertNotEqual(center_col, (255, 0, 255))
        # Grand Hall back-wall portraits sit on the piers outside the staircase
        hall = Mesh()
        MS._interior_hall(hall)
        self.assertGreater(len(hall.faces), 0)


if __name__ == "__main__":
    unittest.main()
