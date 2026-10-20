"""Mission 6 campaign regressions. Run: python -m unittest tests.unit.test_m6_campaign -v.

Pure/local checks: no app import, no window, no save writes.  Covers the four
authored maps, floodlight geometry/exposure/alarm, the shot contract, a few
representative engine3d film frames under the software backend, the train
timeline/hitscan/ammo/reload/handoff, checkpoint bindings and Guard-outfit
continuity.
"""
import math
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.unit import _helpers  # noqa: F401  (sys.path + headless env)

import pygame

from core.config import HEIGHT, WIDTH
from core.outfits import OUTFIT_GUARD, OUTFIT_KRAP, gameplay_outfit
from core.state import STATE
from core.cutscene_registry import scene_renderer, set_current_shot
from cutscenes import m6films
from cutscenes import m6world3d as _w3
from missions.m6 import flow as _flow
from missions.m6 import maps as _maps
from missions.m6 import meta as _meta
from missions.m6 import stealth as _stealth
from missions.m6 import train3d as _train
from missions.m6 import world as _world

ROOT = Path(__file__).resolve().parents[2]


# ───────────────────────────────────────────────────────────────────────────
# maps
# ───────────────────────────────────────────────────────────────────────────
class M6MapTests(unittest.TestCase):
    def test_three_maps_validate_and_are_distinct(self):
        grids = (_maps.M6_CUSTOMS_MAP, _maps.M6_NOMAN_MAP,
                 _maps.M6_RAIL_MAP)
        for grid in grids:
            self.assertIsInstance(grid, list)
            self.assertTrue(all(isinstance(row, str) for row in grid))
            self.assertEqual(len({len(row) for row in grid}), 1,
                             "map rows must be rectangular")
        self.assertEqual(len({(len(g[0]), len(g)) for g in grids}), 3,
                         "stages must not reuse one baked map")
        self.assertEqual(_maps._validate(), [])

    def test_anchors_spawns_and_markers_are_consistent(self):
        for stage in _meta.STAGES:
            structure = _maps.structure_for(stage)
            grid = _maps.grid_for(stage)
            ax, ay = _meta.STAGE_ANCHORS[stage]
            sx, sy = _meta.STAGE_SPAWNS[stage]
            self.assertNotIn(structure[ay][ax], _meta.M6_SOLID_CHARS, stage)
            self.assertNotIn(structure[sy][sx], _meta.M6_SOLID_CHARS, stage)
            self.assertEqual(grid[sy][sx], "P", stage)
            self.assertLess(ax, len(structure[0]))
            self.assertLess(ay, len(structure))

    def test_bind_stage_rebinds_the_live_grid(self):
        expected = {
            _meta.STAGE_CUSTOMS: (30, 20),
            _meta.STAGE_NOMAN: (40, 18),
            _meta.STAGE_RAIL: (46, 26),
        }
        try:
            for stage, dims in expected.items():
                _maps.bind_stage(stage)
                self.assertEqual(_maps._live_map_dims(), dims)
        finally:
            _maps.bind_stage(_meta.STAGE_CUSTOMS)


# ───────────────────────────────────────────────────────────────────────────
# floodlights
# ───────────────────────────────────────────────────────────────────────────
class FloodlightGeometryTests(unittest.TestCase):
    def test_sweep_is_a_deterministic_sine(self):
        light = _stealth.Floodlight((0, 0), 0.25, 0.4, 8.0, phase=1.1)
        for t in (0.0, 1.0, 3.7, 8.0, 17.25):
            want = 0.25 + 0.4 * math.sin(2 * math.pi * t / 8.0 + 1.1)
            self.assertAlmostEqual(light.angle_at(t), want, places=9)
        twin = _stealth.Floodlight((0, 0), 0.25, 0.4, 8.0, phase=1.1)
        self.assertEqual([light.angle_at(t) for t in range(20)],
                         [twin.angle_at(t) for t in range(20)])

    def test_cone_respects_angle_range_and_walls(self):
        grid = [
            "CCCCCCCC",
            "C..C...C",
            "C..C...C",
            "CCCCCCCC",
        ]
        light = _stealth.Floodlight((96, 96), 0.0, 0.0, 10.0,
                                    half_angle=0.5, range_px=500)
        self.assertTrue(_stealth.point_in_cone(light, 160, 96, 0.0, grid))
        # Same row, but the wall at column 3 blocks the ray.
        self.assertFalse(_stealth.point_in_cone(light, 352, 96, 0.0, grid))
        # In the grid, in range, but far outside the cone angle.
        self.assertFalse(_stealth.point_in_cone(light, 96, 260, 0.0, grid))
        # Out of range in open space.
        near = _stealth.Floodlight((96, 96), 0.0, 0.0, 10.0,
                                   half_angle=0.5, range_px=100)
        grid_open = ["CCCCCCCC", "C......C", "C......C", "CCCCCCCC"]
        self.assertFalse(_stealth.point_in_cone(near, 300, 96, 0.0, grid_open))


class ExposureAlarmTests(unittest.TestCase):
    def setUp(self):
        STATE.reset()
        STATE.mission6_stage = _meta.STAGE_NOMAN
        STATE.player = SimpleNamespace(rect=pygame.Rect(0, 0, 32, 32))
        STATE.player.rect.center = (200, 100)
        STATE.dt = 1.0 / 60.0
        _stealth.init_stage(_meta.STAGE_NOMAN)
        self.probe = _stealth.Floodlight((100, 100), 0.0, 0.0, 10.0,
                                         half_angle=0.8, range_px=2000)
        _stealth._lights = (self.probe,)
        self.alarms = []
        self._patches = [
            patch.object(_world, "on_alarm",
                         lambda stage: self.alarms.append(stage)),
            patch.object(_world, "radio", lambda *a, **kw: True),
            patch.object(_world, "sfx", lambda *a, **kw: None),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        _stealth._lights = ()
        _stealth._stage = None
        STATE.reset()

    def test_exposure_accumulates_and_latches_exactly_once(self):
        seen = _stealth.update(0.2)
        self.assertTrue(seen)
        self.assertAlmostEqual(STATE.m6_exposure, 0.2, places=6)
        self.assertFalse(STATE.m6_alarm)
        _stealth.update(0.1)
        _stealth.update(0.1)
        self.assertTrue(STATE.m6_alarm)
        self.assertTrue(STATE.m6_alarm_triggered)
        self.assertEqual(self.alarms, [_meta.STAGE_NOMAN])
        self.assertFalse(_stealth.trigger_alarm())
        self.assertEqual(self.alarms, [_meta.STAGE_NOMAN])

    def test_hidden_player_decays_and_never_latches(self):
        _stealth.update(0.3)
        STATE.player.rect.center = (100, 1100)      # far outside the cone angle
        self.assertFalse(_stealth.update(0.2))
        self.assertLess(STATE.m6_exposure, 0.3)
        for _ in range(10):
            _stealth.update(0.1)
        self.assertEqual(STATE.m6_exposure, 0.0)
        self.assertFalse(STATE.m6_alarm)

    def test_stage_entry_clears_exposure_and_alarm(self):
        _stealth.update(0.4)
        self.assertTrue(STATE.m6_alarm)
        _stealth.init_stage(_meta.STAGE_RAIL)
        self.assertEqual(STATE.m6_exposure, 0.0)
        self.assertFalse(STATE.m6_alarm)
        self.assertFalse(STATE.m6_alarm_triggered)
        self.assertEqual(len(_stealth.lights()), 2)

    def test_alarm_waves_stay_under_the_cap(self):
        STATE.enemies = []
        STATE.player.rect.center = (640, 640)
        STATE.m6_wave_count = 0
        _world._wave_cursor = 0
        for _ in range(8):
            _world.spawn_alarm_wave(4)
        living = sum(1 for e in STATE.enemies if getattr(e, "hp", 0) > 0)
        self.assertEqual(living, _meta.MAX_ALARM_ENEMIES)
        self.assertEqual(STATE.m6_wave_count, _meta.MAX_ALARM_ENEMIES)
        self.assertEqual(_world.spawn_alarm_wave(4), 0)


# ───────────────────────────────────────────────────────────────────────────
# films
# ───────────────────────────────────────────────────────────────────────────
class ShotContractTests(unittest.TestCase):
    def test_every_authored_scene_is_registered(self):
        self.assertEqual(set(_meta.M6_FILM_SCENES),
                         set(m6films.M6_3D_SCENES))
        for scene in _meta.M6_FILM_SCENES:
            self.assertIsNotNone(scene_renderer(scene), scene)
        self.assertNotIn("title_card", _meta.M6_FILM_SCENES)

    def test_ending_chain_matches_the_doc(self):
        shots = _meta.mission6_ending_shots
        self.assertEqual([s["scene"] for s in shots], [
            "m6_customs_terminal",
            "m6_radio_vasile", "m6_radio_vasile", "m6_radio_vasile",
            "m6_radio_vasile",
            "m6_radio_maru", "m6_helicopter", "title_card"])
        text = "\n".join(s.get("text", "") for s in shots)
        for line in ("Route 12 went out on your code.",
                     "...Three hundred men, Biribel. They'd have purged every one. I chose the many.",
                     "You'd have done the same.",
                     "Retardovici is at the mansion in two nights.",
                     "Not tonight. Go to ground."):
            self.assertIn(line, text)
        for shot in shots[1:6]:
            self.assertTrue(shot["radio"])

    def test_boxcar_dialogue_is_verbatim(self):
        text = "\n".join(s.get("text", "")
                         for s in _meta.M6_MID_CUTSCENES["boxcar"])
        for line in ("You took this from me once. Read it this time.",
                     "...Route 12. Movement order. Authorization - That's Vasile's code.",
                     "I tried to sell it to anyone who'd stop it. You were the one who showed up.",
                     "You knew. In the warehouse. You knew where it would go.",
                     "I knew who you'd give it to. I didn't know how to tell you without you shooting me.",
                     "I just wanted to get out. Funny. You did too."):
            self.assertIn(line, text)

    def test_3d_can_be_disabled_by_environment(self):
        with patch.dict(os.environ, {"ACARISTAN_CUTSCENE3D": "0"}):
            self.assertFalse(m6films.m6_3d_enabled())
        self.assertFalse(m6films._cache["failed"])

    def test_terminal_record_drops_the_first_name(self):
        record = (" ".join(" ".join(pair) for pair in m6films.CRT_LINES)
                  + " " + m6films.CRT_FOOT).upper()
        self.assertNotIn("ANDREI", record)
        self.assertIn("VELICU", record)
        self.assertIn("UCILEV", record)
        self.assertIn("KIA", record)

    def test_fall_deploys_a_canopy(self):
        self.assertEqual(m6films.chute_open(100), 0.0)
        self.assertGreater(m6films.chute_open(1800), 0.95)
        mesh, rim = m6films._chute_mesh((0.0, 10.0, 0.0), 1.6, 1.0)
        self.assertTrue(mesh.verts)
        self.assertEqual(len(rim), 12)
        self.assertGreater(max(p[1] for p in rim), 10.0)
        self.assertGreater(max(p[0] for p in rim) - min(p[0] for p in rim), 1.0)

    def test_representative_frames_render_on_the_software_backend(self):
        import core.config as cfg
        import cutscenes.m6world3d as world3d
        # Engine boot tests pygame.quit() mid-suite, which invalidates the
        # Font objects cached at import time.  Rebuild the ones the film
        # renderers hold by value before warming the set.
        if not pygame.font.get_init():
            pygame.font.init()
        try:
            cfg.font_terminal_small.size("m6")
        except Exception:
            cfg.font_terminal_small = cfg._load_font(
                cfg._MONO_R, 14, "Consolas")
        m6films.font_terminal_small = cfg.font_terminal_small
        world3d.font_terminal_small = cfg.font_terminal_small
        m6films._cache["failed"], m6films._cache["err"] = False, None
        world3d._cache["r"].clear()
        surface = pygame.Surface((WIDTH, HEIGHT))
        with patch.dict(os.environ, {"ACARISTAN_RENDERER": "software",
                                     "ACARISTAN_CUTSCENE3D": "1"}):
            self.assertTrue(
                m6films.draw_m6_scene_3d("m6_insert_heli", surface, 1200))
            self.assertTrue(
                m6films.draw_m6_scene_3d("m6_boxcar_wide", surface, 1500))
            self.assertTrue(
                m6films.draw_m6_scene_3d("m6_radio_vasile", surface, 2200))
        self.assertFalse(m6films._cache["failed"], m6films._cache["err"])


# ───────────────────────────────────────────────────────────────────────────
# interactive train
# ───────────────────────────────────────────────────────────────────────────
class TrainSceneTests(unittest.TestCase):
    def setUp(self):
        STATE.reset()
        STATE.player = SimpleNamespace(hp=115)
        STATE.dt = 1.0 / 60.0
        self.scene = _train.TrainScene()
        self.scene.started = True
        self.scene.done = False
        self.scene.guards = [
            {"slot": i, "pos": slot["pos"], "spawn": slot["spawn"],
             "hp": _train.GUARD_HP, "alive": False, "active": False,
             "dead_t": -9.0, "flinch": 0.0, "yaw": 0.0}
            for i, slot in enumerate(_train._GUARD_SLOTS)]
        self.mouse = (WIDTH // 2, HEIGHT // 2)

    def tearDown(self):
        STATE.reset()

    def _run_until(self, t):
        guard = 0
        while self.scene.t < t and guard < 3000:
            self.scene.update(mouse=self.mouse)
            guard += 1
        self.assertLess(self.scene.t, t + 0.1, "train clock stalled")

    def test_scripted_shot_timing(self):
        scene = self._fresh_scene(hp=100000)
        while scene.t < _train.SHOT_AT - 0.2:
            scene.update(mouse=self.mouse)
        self.assertFalse(STATE.m6_volkov_dead)
        guard = 0
        while not STATE.m6_volkov_dead and guard < 120:
            scene.update(mouse=self.mouse)
            guard += 1
        self.assertTrue(STATE.m6_volkov_dead)
        self.assertIn("shot", scene._ev)
        self.assertTrue(scene.volkov_failed,
                        "a squad-left shot must be the failed-cover branch")

    def test_guard_fire_can_kill_biribel(self):
        STATE.mission6_stage = _meta.STAGE_TRAIN
        STATE.m6_train_active = True
        scene = self._fresh_scene(hp=1)
        guard = scene.guards[0]
        guard["active"] = True
        guard["alive"] = True
        with patch.object(scene, "_cover_blocks", return_value=False):
            scene._guard_shot(guard, _train._guard_profile("rifle"))
        self.assertTrue(STATE.player_dead, "Biribel survived a lethal burst")
        self.assertTrue(scene.dying)
        self.assertTrue(scene.active(), "the 3D death beat must keep rendering")
        self.assertTrue(STATE.m6_train_active)
        self.assertEqual(STATE.m6_train_result, "dead")
        for _ in range(140):                    # > 2.2 s death beat
            scene.update(mouse=self.mouse)
        self.assertTrue(STATE.request_death_screen)
        self.assertTrue(STATE.m6_train_death)
        self.assertFalse(STATE.m6_train_active)
        self.assertFalse(STATE.request_mission6_ending)
        self.assertFalse(_flow.on_train_done("fallback"),
                         "a failed train run handed off to the ending")

    def test_fire_and_reload_use_the_shared_k9(self):
        STATE.k9_ammo_in_mag = STATE.k9_mag_size
        STATE.k9_spare_mags = 2
        STATE.shots_fired = 0
        self.scene.t = _train.CONTROL_AT
        self.assertTrue(self.scene.fire_once())
        self.assertEqual(STATE.k9_ammo_in_mag, STATE.k9_mag_size - 1)
        self.assertEqual(STATE.shots_fired, 1)
        self.scene._begin_reload()
        self.assertTrue(self.scene.reloading)
        self.scene._update_reload(_train.RELOAD_TIME + 0.01)
        self.assertEqual(STATE.k9_ammo_in_mag, STATE.k9_mag_size)
        self.assertEqual(STATE.k9_spare_mags, 1)

    def test_hitscan_selects_the_guards_chest(self):
        guard = self.scene.guards[0]
        guard["active"] = True
        guard["alive"] = True
        eye = (_train.PLAYER_POS[0],
               _train.PLAYER_POS[1] + _train.PLAYER_EYE,
               _train.PLAYER_POS[2])
        target = (guard["pos"][0], guard["pos"][1] + 1.32, guard["pos"][2])
        d = tuple(target[i] - eye[i] for i in range(3))
        n = math.sqrt(sum(c * c for c in d))
        fwd = tuple(c / n for c in d)
        hit = self.scene._hitscan(eye, fwd)
        self.assertIsNotNone(hit)
        self.assertIs(hit[0], guard)
        self.assertIsNone(self.scene._hitscan(
            eye, (-fwd[0], -fwd[1], -fwd[2])))

    def test_hitscan_flags_headshots_and_world_impacts(self):
        guard = self.scene.guards[0]
        guard["active"] = True
        guard["alive"] = True
        eye = (_train.PLAYER_POS[0],
               _train.PLAYER_POS[1] + _train.PLAYER_EYE,
               _train.PLAYER_POS[2])

        def aim(dy):
            tgt = (guard["pos"][0], guard["pos"][1] + dy, guard["pos"][2])
            d = tuple(tgt[i] - eye[i] for i in range(3))
            n = math.sqrt(sum(c * c for c in d))
            return tuple(c / n for c in d)

        self.assertIsNotNone(self.scene._hitscan(eye, aim(1.60)))
        self.assertTrue(self.scene.last_hit_head)
        self.assertIsNotNone(self.scene._hitscan(eye, aim(1.20)))
        self.assertFalse(self.scene.last_hit_head)
        # misses land on a surface now, not 40 m out in mid-air
        down = _train._world_hit(eye, (0.0, -0.6, -0.8))
        self.assertIsNotNone(down)
        self.assertEqual(down[1], "snow")
        side = _train._world_hit(eye, (0.0, 0.0, -1.0))
        self.assertIsNotNone(side)
        self.assertEqual(side[1], "metal")

    def test_skip_and_handoff_are_idempotent(self):
        STATE.mission6_stage = _meta.STAGE_TRAIN
        STATE.m6_train_active = True
        self.scene.t = 1.0
        self.assertFalse(self.scene.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e)))
        self.scene.t = 2.1
        with patch.object(_world, "volkov", lambda: None):
            self.assertTrue(self.scene.handle_event(
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e)))
            self.assertFalse(self.scene.force_finish("win"))
        self.assertEqual(STATE.mission6_stage, _meta.STAGE_TRAIN)
        self.assertEqual(STATE.m6_train_result, "skip")
        self.assertTrue(STATE.m6_volkov_dead)
        self.assertFalse(STATE.m6_train_active)
        self.assertTrue(STATE.request_mission6_ending)

    def test_train_handoff_requests_the_ending_film(self):
        STATE.mission6_stage = _meta.STAGE_TRAIN
        STATE.m6_train_active = True
        with patch.object(_world, "volkov", lambda: None):
            self.assertTrue(_flow.on_train_done("win"))
            self.assertFalse(_flow.on_train_done("win"))
        self.assertEqual(STATE.mission6_stage, _meta.STAGE_TRAIN)
        self.assertTrue(STATE.request_mission6_ending)

    def test_mouse_look_is_not_inverted(self):
        self.scene.t = _train.CONTROL_AT
        self.scene.update(mouse=(WIDTH // 2, HEIGHT // 2))
        self.assertAlmostEqual(self.scene.yaw, _train.BASE_YAW)
        # Mouse right must look right: engine3d's screen-right is -x, so yaw
        # decreases when the camera turns toward the screen's right edge.
        self.scene.update(mouse=(WIDTH * 3 // 4, HEIGHT // 2))
        self.assertAlmostEqual(self.scene.yaw,
                               _train.BASE_YAW - _train.YAW_LIMIT * 0.5)
        # Mouse up must look up (positive pitch).
        self.scene.update(mouse=(WIDTH // 2, HEIGHT // 4))
        self.assertAlmostEqual(self.scene.pitch,
                               _train.BASE_PITCH + _train.PITCH_LIMIT * 0.5)

    # ── platform pressure / roster ─────────────────────────────────────
    def _fresh_scene(self, hp=100000):
        STATE.player = SimpleNamespace(hp=hp, max_hp=max(115, hp),
                                       rect=pygame.Rect(0, 0, 32, 32),
                                       angle=0.0)
        scene = _train.TrainScene()
        scene.started = True
        scene.done = False
        scene.t = 0.0
        scene.guards = [_train._make_guard(i, s)
                        for i, s in enumerate(_train._GUARD_SLOTS)]
        return scene

    def test_roster_has_distinct_models_and_jobs(self):
        kinds = {s.get("kind") for s in _train._GUARD_SLOTS}
        self.assertGreaterEqual(len(kinds), 4)
        shapes = set()
        for kind in kinds:
            prof = _train._GUARD_KINDS[kind]
            self.assertTrue(prof.get("lamp"))
            hum = _w3.hum(("guard", kind))
            shapes.add((hum.spec.get("beret"), hum.spec.get("beanie"),
                        hum.spec.get("helmet"), hum.spec.get("cap"),
                        hum.spec.get("long_coat"), hum.spec.get("bulk")))
        self.assertGreaterEqual(len(shapes), 4,
                                "Guard variants collapsed to one silhouette")

    def test_guards_advance_and_pin_volkov(self):
        scene = self._fresh_scene()
        while scene.t < 9.0:
            scene.update(mouse=self.mouse)
        moved = [g for g in scene.guards
                 if g.get("active") and tuple(g["pos"]) != tuple(g["home"])]
        self.assertTrue(moved, "no Guard ever left his spawn point")
        self.assertTrue(scene.volkov_pinned)
        self.assertGreater(scene.volkov_delay, 0.0)

    def test_ignoring_the_guard_fails_the_escort(self):
        STATE.mission6_stage = _meta.STAGE_TRAIN
        scene = self._fresh_scene()
        guard = 0
        # The overrun is decided at SHOT_AT - budget from the timeline, not a
        # hardcoded frame count (a longer cinematic must not fail this test).
        budget = int((_train.SHOT_AT + 3.0) * 60)
        while not scene.volkov_failed and guard < budget:
            scene.update(mouse=self.mouse)
            guard += 1
        self.assertTrue(scene.volkov_failed)
        self.assertTrue(scene.overrun)
        self.assertTrue(STATE.m6_train_overrun)
        self.assertGreaterEqual(STATE.m6_train_guards_left, 2)
        self.assertTrue(STATE.m6_volkov_dead)
        self.assertTrue(scene.volkov_failed)
        while scene.fail_t < 1.9:
            scene.update(mouse=self.mouse)
        self.assertEqual(STATE.m6_train_result, "failed")
        self.assertTrue(STATE.m6_train_death)
        self.assertTrue(STATE.request_death_screen)
        self.assertFalse(STATE.request_mission6_ending)
        self.assertFalse(scene.force_finish("win"),
                         "a failed escort handed off to the ending")
        self.assertFalse(_flow.on_train_done("win"),
                         "a failed escort handed off to the ending")

    def test_clearing_the_platform_reaches_ucilevs_shot(self):
        STATE.mission6_stage = _meta.STAGE_TRAIN
        scene = self._fresh_scene()
        # Clear the lane just before the scripted shot, then run past Ucilev's
        # round.  Both beats come from the timeline constants, and the reserves
        # are disarmed too (a guard whose spawn is still ahead would re-arm and
        # turn a cleared platform into the overrun branch).
        while scene.t < _train.SHOT_AT - 0.6:
            scene.update(mouse=self.mouse)
        for guard in scene.guards:
            guard["alive"] = False
            guard["spawn"] = 999.0
        while scene.t < _train.HIT_AT + 0.1:
            scene.update(mouse=self.mouse)
        self.assertFalse(scene.overrun)
        self.assertFalse(STATE.m6_train_overrun)
        self.assertFalse(scene.volkov_failed)
        self.assertTrue(STATE.m6_volkov_dead)
        self.assertTrue(scene.ucilev_fired, "the signal-tower shot never fired")
        scene.force_finish("win")
        self.assertIn("reached the step", STATE.active_mission_outcome)


# ───────────────────────────────────────────────────────────────────────────
# checkpoints / outfit / app save-resume contract
# ───────────────────────────────────────────────────────────────────────────
class CheckpointAndOutfitTests(unittest.TestCase):
    def tearDown(self):
        STATE.reset()

    def test_checkpoint_wrappers_bind_stage_maps_and_flags(self):
        cases = (
            (_flow.start_mission6_noman_checkpoint, _meta.STAGE_NOMAN,
             _maps.M6_NOMAN_MAP, "m6_noman_checkpoint"),
            (_flow.start_mission6_rail_checkpoint, _meta.STAGE_RAIL,
             _maps.M6_RAIL_MAP, "m6_rail_checkpoint"),
        )
        with patch.object(_flow, "_save_progress", lambda stage: None), \
                patch.object(_world, "radio", lambda *a, **kw: True):
            for fn, stage, grid, flag in cases:
                fn()
                self.assertEqual(STATE.mission6_stage, stage)
                self.assertIs(_maps.MISSION6_MAP, grid)
                self.assertTrue(getattr(STATE, flag), flag)

    def test_m6_guard_black_and_m5_unchanged(self):
        self.assertEqual(gameplay_outfit(SimpleNamespace(active_mission="MISSION6")),
                         OUTFIT_GUARD)
        self.assertEqual(gameplay_outfit(SimpleNamespace(
            active_mission="MISSION5", m5_outfit=OUTFIT_GUARD)), OUTFIT_GUARD)
        # Pre-change KRAP hands back the saved look, exactly as before.
        self.assertIsNone(gameplay_outfit(SimpleNamespace(
            active_mission="MISSION5", m5_outfit=OUTFIT_KRAP)))
        self.assertIsNone(gameplay_outfit(SimpleNamespace(active_mission="MISSION1")))

    def test_app_resume_map_covers_every_m6_save_stage(self):
        src = (ROOT / "src" / "app.py").read_text(encoding="utf-8-sig")
        start = src.index("resume_names = {")
        block = src[start:src.index("}", start)]
        for stage in ("customs", "noman", "rail", "train"):
            self.assertIn('"%s"' % stage, block)
        self.assertIn('"train": "start_mission6_train_checkpoint"', block)
        # Removed file/call stages resume at the train, the last playable stage.
        self.assertIn('"file": "start_mission6_train_checkpoint"', block)
        self.assertIn('"call": "start_mission6_train_checkpoint"', block)
        self.assertNotIn("start_mission6_file_checkpoint", src)
        self.assertNotIn("start_mission6_radio_checkpoint", src)


# ───────────────────────────────────────────────────────────────────────────
# staging, planted gaits and face exposure
# ───────────────────────────────────────────────────────────────────────────
def _lowest_vertex(hum, pose, pos, yaw, key):
    places, _j, root = hum.pose_world(pose, pos, yaw)
    uniq = hum._unique_verts()
    low = 1e9
    for _slot, k, M, org, _g, _fb in places:
        if k != key:
            continue
        for x, y, z in uniq[key]:
            low = min(low, M[3] * x + M[4] * y + M[5] * z + org[1])
    return low + root[1]


class StagingAndExposureTests(unittest.TestCase):
    """The reviewed MP4 regressions: actors inside props, sliding feet and
    blown or crushed faces."""

    PARTS = ("pelvis", "thigh", "shin", "foot")

    def tearDown(self):
        _w3._cache["r"].clear()
        set_current_shot(None)
        m6films._cache["failed"] = False

    def _assert_clear(self, cast, boxes, label):
        for a in cast:
            d, part, box = _w3.penetration(_w3.hum(a["key"]), a["pose"],
                                           a["pos"], a["yaw"], boxes,
                                           parts=self.PARTS)
            name = a["key"] if isinstance(a["key"], str) else a["key"][0]
            self.assertLessEqual(d, 0.02, "%s: %s %s in %s by %.3f m"
                                 % (label, name, part, box, d))

    def test_boxcar_staging_clears_the_set(self):
        boxes = _w3.solids("boxcar")
        for scene, dur in (("m6_boxcar_wide", 6200),
                           ("m6_boxcar_notebook", 6600),
                           ("m6_boxcar_volkov", 6600),
                           ("m6_boxcar_biribel", 6100)):
            for t in range(0, dur, 100):
                cast, _nb = m6films.boxcar_stage(scene, t)
                self._assert_clear(cast, boxes, "%s@%d" % (scene, t))

    def test_both_boxcar_exit_shots_clear_the_set(self):
        boxes = _w3.solids("boxcar")
        for second, dur in ((False, 6900), (True, 5400)):
            for t in range(0, dur, 100):
                cast, _nb = m6films.boxcar_stage("m6_boxcar_exit", t, second)
                self._assert_clear(cast, boxes,
                                   "m6_boxcar_exit#%d@%d" % (second, t))

    def test_radio_staging_clears_the_desk(self):
        boxes = _w3.solids("terminal")
        for variant, dur in ((0, 4400), (1, 6600), ("maru", 4200)):
            for t in range(0, dur, 100):
                cast, _hs = m6films.radio_stage(variant, t)
                self._assert_clear(cast, boxes,
                                   "m6_radio_vasile[%s]@%d" % (variant, t))

    def test_door_seat_clears_the_airframe(self):
        hum = _w3.hum(m6films._BIRI)
        for t in range(0, 3200, 100):
            pose, pos, yaw = m6films.seated_door(t)
            boxes = _w3.heli_solids(*m6films.heli_at("m6_insert_heli", t))
            d, part, box = _w3.penetration(hum, pose, pos, yaw, boxes,
                                           parts=self.PARTS)
            self.assertLessEqual(d, 0.02, "door seat@%d: %s in %s by %.3f m"
                                 % (t, part, box, d))

    def test_seated_pelvis_and_feet_meet_the_seat_and_skid(self):
        volkov = _w3.hum("volkov")
        cast, _nb = m6films.boxcar_stage("m6_boxcar_wide", 0)
        v = cast[0]
        self.assertAlmostEqual(_w3._seat_contact(volkov, v["pose"]),
                               m6films._SEAT_Y, delta=0.03)
        self.assertAlmostEqual(_lowest_vertex(volkov, v["pose"], v["pos"],
                                              v["yaw"], "foot"), 0.0, delta=0.03)
        biri = _w3.hum(m6films._BIRI)
        pose, _root = m6films.heli_seat()
        self.assertAlmostEqual(_w3._seat_contact(biri, pose),
                               _w3.HELI_SILL_Y - _w3.HELI_SKID_Y, delta=0.03)
        pos, hyaw, hbank, hpitch = m6films.heli_at("m6_insert_heli", 0)
        seat = m6films.seated_door(0)
        skid_top = _w3.heli_xform(pos, hyaw, hbank, hpitch)(
            _w3.HELI_SKID_X, _w3.HELI_SKID_Y, _w3.HELI_DOOR_Z)[1]
        self.assertAlmostEqual(_lowest_vertex(biri, seat[0], seat[1], seat[2],
                                              "foot"), skid_top, delta=0.03)

    def test_walks_plant_their_stance_feet(self):
        for scene, second in (("m6_boxcar_exit", False),
                              ("m6_boxcar_exit", True),
                              ("m6_insert_ground", None)):
            slip = _w3.walk_slip(*m6films.walk_metrics(scene, second))
            self.assertLess(max(slip.values()), 0.02,
                            "%s(%s): slip %r" % (scene, second, slip))

    def test_rotor_blur_reaches_the_blade_radius(self):
        with patch.dict(os.environ, {"ACARISTAN_RENDERER": "software",
                                     "ACARISTAN_CUTSCENE3D": "1"}):
            _w3._cache["r"].clear()
            r, buf = _w3.rend()
            _w3.cam(r, 0, (12.8, 26.0, -62.5), (-0.6, 22.8, -45.5), 44)
            r.begin()
            pos, yaw, bank, pitch = m6films.heli_at("m6_insert_heli", 0)
            anchors = _w3.helicopter(r, 0, pos, yaw=yaw, bank=bank,
                                     pitch=pitch)
            r.flush(buf)
        self.assertGreater(anchors["blur_radius"], 0.0)
        self.assertAlmostEqual(anchors["blur_radius"],
                               anchors["rotor_radius"], places=5)

    def test_insertion_skids_stay_above_the_terrain(self):
        for scene, dur in (("m6_insert_heli", 3200),
                           ("m6_insert_jump", 2900),
                           ("m6_insert_fall", 2900),
                           ("m6_insert_ground", 3100)):
            for t in range(0, dur, 100):
                boxes = _w3.heli_solids(*m6films.heli_at(scene, t))
                for skid in ("skid_l", "skid_r"):
                    lo, hi = boxes[skid]
                    ground = _w3.height_at((lo[0] + hi[0]) / 2,
                                           (lo[2] + hi[2]) / 2)
                    self.assertGreater(lo[1], ground + 0.02,
                                       "%s@%d %s: %.3f vs ground %.3f"
                                       % (scene, t, skid, lo[1], ground))

    def test_face_exposure_is_readable_on_software_frames(self):
        import core.config as cfg
        if not pygame.font.get_init():
            pygame.font.init()
        try:
            cfg.font_terminal_small.size("m6")
        except Exception:
            cfg.font_terminal_small = cfg._load_font(
                cfg._MONO_R, 14, "Consolas")
        m6films.font_terminal_small = cfg.font_terminal_small
        _w3.font_terminal_small = cfg.font_terminal_small
        m6films._cache["failed"], m6films._cache["err"] = False, None
        surface = pygame.Surface((WIDTH, HEIGHT))
        radio_v1 = next(s for s in _meta.mission6_ending_shots
                        if s.get("scene") == "m6_radio_vasile"
                        and "Three hundred" in s.get("text", ""))
        cases = (("m6_boxcar_volkov", 2772, None),
                 ("m6_boxcar_biribel", 2562, None),
                 ("m6_radio_vasile", 2772, radio_v1))
        seen = 0
        with patch.dict(os.environ, {"ACARISTAN_RENDERER": "software",
                                     "ACARISTAN_CUTSCENE3D": "1"}):
            _w3._cache["r"].clear()
            for scene, t, shot in cases:
                set_current_shot(shot)
                m6films.M6_3D_SCENES[scene](surface, t)
                for h in _w3.head_stats(surface):
                    seen += 1
                    self.assertGreaterEqual(h["mean"], 55.0,
                                            "%s@%d mean %.0f" % (scene, t,
                                                                 h["mean"]))
                    self.assertLessEqual(h["mean"], 170.0,
                                         "%s@%d mean %.0f" % (scene, t,
                                                              h["mean"]))
                    self.assertLess(h["p95"], 235.0,
                                    "%s@%d p95 %.0f" % (scene, t, h["p95"]))
        self.assertTrue(seen, "no faces were measured")


if __name__ == "__main__":
    unittest.main()
