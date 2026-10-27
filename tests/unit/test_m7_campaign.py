"""Mission 7 campaign regressions. Run: python -m unittest tests.unit.test_m7_campaign -v.

Headless checks: no app import, no window, no save writes.  Covers the stage
ladder and film hand-offs, the 3D raid (prep flags, pause, waves to the
finale, death reload, Bodi-down failure), the radio choice that writes
``STATE.m8_route``, and the voice rows for Bodi and Alex.
"""
import unittest
from unittest.mock import patch

from tests.unit import _helpers  # noqa: F401  (sys.path + headless env)

import pygame

from audio import voice_manifest as _vm
from core.cutscene_registry import scene_renderer
from core.state import STATE
from missions import m7
from missions.m7 import choice as _choice
from missions.m7 import flow as _flow
from missions.m7 import meta as _meta
from missions.m7 import raid3d as _raid


class _Keys(dict):
    def __getitem__(self, key):
        return self.get(key, 0)


NONE = _Keys()


def _start(stage, preps=()):
    STATE.m7_preps = list(preps)
    m7.start_m7(stage)
    return STATE


class M7StageTests(unittest.TestCase):
    def setUp(self):
        self._save = patch.object(_flow, "_save_progress", lambda stage: None)
        self._save.start()
        self.addCleanup(self._save.stop)
        self.addCleanup(_raid.abort)

    def test_ladder_order_matches_the_doc(self):
        self.assertEqual(_meta.STAGES, ("arrival", "chores", "runner", "prep",
                                        "raid", "finale", "choice"))
        self.assertEqual(set(_meta.FILM_TIMELINES), {"arrival", "runner", "finale"})

    def test_every_film_scene_is_registered(self):
        for scene_id in _meta.M7_SCENES:
            self.assertIsNotNone(scene_renderer(scene_id), scene_id)
        for stage in _meta.FILM_TIMELINES:
            shots = _meta.film_shots(stage)
            self.assertTrue(shots, stage)
            for shot in shots:
                self.assertTrue(shot.get("scene"), (stage, shot))
        self.assertTrue(_meta.outro_shots())

    def test_start_binds_identity(self):
        _start("chores")
        self.assertEqual(STATE.active_mission, "MISSION7")
        self.assertEqual(STATE.active_mission_id, "MISSION_7")
        self.assertEqual(STATE.mission7_stage, "chores")

    def test_film_stage_requests_its_film_once(self):
        _start("finale")
        self.assertEqual(_flow.take_cutscene_request(), "finale")
        self.assertIsNone(_flow.take_cutscene_request())
        _flow.on_cutscene_done("finale")
        self.assertEqual(STATE.mission7_stage, "choice")

    def test_a_stale_film_end_does_not_move_the_ladder(self):
        _start("prep")
        _flow.on_cutscene_done("finale")
        self.assertEqual(STATE.mission7_stage, "prep")

    def test_past_the_last_stage_the_outro_latches_once(self):
        _start("choice")
        self.assertFalse(_flow.take_outro_request())
        _flow.advance_stage()
        self.assertTrue(_flow.take_outro_request())
        self.assertFalse(_flow.take_outro_request())

    def test_preps_survive_only_a_raid_restart(self):
        _start("raid", preps=("tractor", "loft"))
        self.assertEqual(STATE.m7_preps, ["tractor", "loft"])
        STATE.m7_preps = ["tractor", "loft"]
        m7.start_m7("chores")
        self.assertEqual(STATE.m7_preps, [])


class M7RaidTests(unittest.TestCase):
    def setUp(self):
        self._save = patch.object(_flow, "_save_progress", lambda stage: None)
        self._save.start()
        self.addCleanup(self._save.stop)
        self.addCleanup(_raid.abort)

    def _scene(self, preps=()):
        _start("raid", preps)
        self.assertTrue(_raid.active())
        return _raid.scene()

    def test_begin_sets_prep_flags_and_checkpoint(self):
        s = self._scene(("tractor", "loft"))
        self.assertEqual(s.flags, {"tractor": True, "shed": False, "loft": True})
        self.assertEqual(STATE.m7_raid_cp, 0)
        self.assertTrue(STATE.m7_raid_active)
        self.assertEqual(STATE.mission7_stage, "raid")

    def test_game_update_and_draw_route_to_the_scene(self):
        s = self._scene()
        for _ in range(60):
            cam = m7.game_update(NONE)
            self.assertEqual(len(cam), 2)
        self.assertGreater(s.t, 0.9)
        surface = pygame.Surface((1000, 700))
        m7.game_draw(surface, 0, 0)

    def test_pause_freezes_the_clock(self):
        s = self._scene()
        _raid.update(NONE)
        s.set_paused(True)
        t0 = s.t
        _raid.update(NONE)
        self.assertEqual(s.t, t0)
        s.set_paused(False)
        _raid.update(NONE)
        self.assertGreater(s.t, t0)

    def test_mouse_buttons_drive_fire(self):
        s = self._scene()
        _raid.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0)))
        self.assertTrue(s.firing)
        _raid.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(0, 0)))
        self.assertFalse(s.firing)

    def test_first_wave_arrives_after_the_intro(self):
        s = self._scene()
        for _ in range(60 * 8):
            STATE.player.hp = max(STATE.player.hp, 60)
            _raid.update(NONE)
            if s.phase == "w1":
                break
        self.assertEqual(s.phase, "w1")
        self.assertTrue(s.brain.enemies)

    def test_player_death_reloads_the_phase_in_place(self):
        s = self._scene()
        for _ in range(30):
            _raid.update(NONE)
        STATE.player.hp = 5
        s.hurt_player(40, (s.px + 5, s.pz))
        self.assertTrue(s.dying)
        for _ in range(60 * 5):
            _raid.update(NONE)
        self.assertFalse(s.dying)
        self.assertGreater(s.hp(), 0)
        self.assertEqual(STATE.mission7_stage, "raid")

    def test_checkpoint_restores_position_and_ammo(self):
        s = self._scene(("shed",))
        s.cp_state = dict(px=3.0, pz=-4.0, yaw=45.0, mag=11, reserve=77)
        s._setup(1)
        self.assertAlmostEqual(s.px, 3.0)
        self.assertEqual((s.mag, s.reserve), (11, 77))
        self.assertEqual(s.phase, "gap")

    def test_bodi_down_for_twenty_seconds_fails_the_fight(self):
        s = self._scene()
        s.brain.bodi["state"] = "down"
        s.brain.bodi["down_at"] = s.t
        s.brain.bodi["hp"] = 0
        for _ in range(60 * 21):
            _raid.update(NONE)
            if s.dying:
                break
        self.assertTrue(s.dying or s.death_t > 0)

    def test_win_hands_off_to_the_finale_film_once(self):
        self._scene()
        self.assertTrue(_raid.force_finish("win"))
        self.assertEqual(STATE.mission7_stage, "finale")
        self.assertFalse(_raid.active())
        self.assertEqual(STATE.request_m7_cutscene, "finale")
        self.assertFalse(_raid.force_finish("win"), "raid hand-off double-fired")

    def test_a_broken_scene_falls_through_instead_of_stranding(self):
        self._scene()

        def boom(*_a, **_k):
            raise RuntimeError("m7 raid probe")

        with patch.object(_raid, "update", boom):
            m7.game_update(NONE)
        self.assertEqual(STATE.mission7_stage, "finale")
        self.assertFalse(_raid.active())

    def test_restart_while_active_rebuilds_the_fight(self):
        s = self._scene(("tractor",))
        for _ in range(20):
            _raid.update(NONE)
        _start("raid", ("tractor",))
        self.assertTrue(_raid.active())
        self.assertLess(_raid.scene().t, 0.1)
        self.assertTrue(_raid.scene().flags["tractor"])
        self.assertIs(_raid.scene(), s)


class M7ChoiceTests(unittest.TestCase):
    def setUp(self):
        self._save = patch.object(_flow, "_save_progress", lambda stage: None)
        self._save.start()
        self.addCleanup(self._save.stop)

    def _open(self):
        _start("choice")
        STATE.m8_route = ""
        _choice._S["t0"] -= 60000          # past the typed transmission
        m7.game_update(NONE)

    def _pick(self, key):
        m7.game_update(_Keys({key: 1}))
        m7.game_update(NONE)
        m7.game_update(_Keys({pygame.K_RETURN: 1}))
        m7.game_update(NONE)

    def test_nothing_is_selected_by_default(self):
        self._open()
        m7.game_update(_Keys({pygame.K_RETURN: 1}))
        m7.game_update(NONE)
        self.assertEqual(STATE.m8_route, "")
        self.assertFalse(_choice._S["done_at"])

    def test_each_channel_writes_its_route_and_ends_the_mission(self):
        for key, route in ((pygame.K_1, "duty"), (pygame.K_d, "revenge")):
            self._open()
            self._pick(key)
            self.assertEqual(STATE.m8_route, route)
            _choice._S["done_at"] -= 5000
            m7.game_update(NONE)
            self.assertTrue(_flow.take_outro_request(), route)


class M7VoiceTests(unittest.TestCase):
    BODI_ALEX = {
        "VO_219": ("BODI", "You're the one Maru called about. Boots off in the kitchen."),
        "VO_222": ("BODI", "That's my barn."),
        "VO_224": ("ALEX", "Biribel! THE Biribel! Maru said you'd be taller."),
        "VO_226": ("ALEX", "Trucks! Two of them - no, three!"),
        "VO_227": ("ALEX", "I'm pinned! Biribel, I'm pinned!"),
    }

    def test_rows_exist_and_are_marked_missing(self):
        rows = {row[0]: row for row in _vm.VOICE_LINES}
        for vid, (speaker, text) in self.BODI_ALEX.items():
            self.assertIn(vid, rows)
            self.assertEqual((rows[vid][1], rows[vid][2]), (speaker, text))
            self.assertIn(vid, _vm.KNOWN_MISSING_AUDIO)
        for n in range(219, 228):
            self.assertIn("VO_%d" % n, rows)
            self.assertNotIn("VO_%d" % n, _vm.VOICE_ORDER)

    def test_raid_callouts_use_manifest_text(self):
        import inspect
        src = inspect.getsource(_raid)
        for _vid, (_speaker, text) in self.BODI_ALEX.items():
            if text in ("That's my barn.", "Trucks! Two of them - no, three!",
                        "I'm pinned! Biribel, I'm pinned!"):
                self.assertIn(text, src)


if __name__ == "__main__":
    unittest.main()
