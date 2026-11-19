"""MISSION_COMPLETE physical case-dossier screen (ui/mission_complete.py).

No arcade score/rank, one profile + debrief + ledger shape per mission, buttons
only offer CONTINUE when the campaign has a next mission, and no missing
translation key behind the labels.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from core import mission_meta  # noqa: E402
from ui import mission_complete as mc  # noqa: E402

_MISSIONS = ("MISSION1", "MISSION2", "MISSION3", "MISSION4", "MISSION5",
             "MISSION6", "MISSION7", "MISSION8")


class _State:
    def __init__(self, key, **kw):
        self.active_mission = key
        for name, value in kw.items():
            setattr(self, name, value)


_REPORT = {"kills": 6, "shots_fired": 30, "shots_hit": 12, "accuracy": 40,
           "time_str": "03:45", "civilians_helped": 0, "rations_used": 1,
           "intel_found": False, "stealth_clean": False, "score": 61, "rank": "C"}


class DossierProfiles(unittest.TestCase):
    def test_every_mission_has_a_case_file_profile(self):
        for key in _MISSIONS:
            self.assertIn(key, mc.PROFILES, key)
            location, caption, photo_kind, stamp = mc.PROFILES[key]
            self.assertTrue(location and caption and photo_kind, key)
            self.assertEqual(len(stamp), 3, key)

    def test_every_profile_mission_is_in_the_meta_table(self):
        for key in mc.PROFILES:
            if key == "MISSION0":
                continue
            self.assertIn(key, mission_meta.MISSION_META, key)

    def test_no_score_or_rank_is_presented(self):
        for key in _MISSIONS:
            labels = [label for label, _v in mc.ledger_rows(_State(key), _REPORT, key)]
            self.assertNotIn("RANK", labels, key)
            self.assertNotIn("SCORE", labels, key)
            self.assertEqual(len(labels), 4, key)


class Ledger(unittest.TestCase):
    def test_rows_use_the_run_report(self):
        rows = dict(mc.ledger_rows(_State("MISSION3"), _REPORT, "MISSION3"))
        self.assertEqual(rows["ELAPSED TIME"], "03:45")
        self.assertEqual(rows["HOSTILES DOWN"], "6")
        self.assertEqual(rows["SHOT ACCURACY"], "40%")

    def test_per_mission_fourth_column(self):
        self.assertEqual(dict(mc.ledger_rows(_State("MISSION1", notebook_collected=True),
                                             _REPORT, "MISSION1"))["LOGBOOK"], "RECOVERED")
        ev = [{"done": True}, {"done": False}, {"done": True}]
        self.assertEqual(dict(mc.ledger_rows(_State("MISSION2", mission2_evidence=ev),
                                             _REPORT, "MISSION2"))["EVIDENCE"], "2/3 SENT")
        self.assertEqual(dict(mc.ledger_rows(_State("MISSION6"), _REPORT, "MISSION6"))["GUARD FILE"],
                         "VELICU, B.")
        self.assertEqual(dict(mc.ledger_rows(_State("MISSION7", m7_preps=("a", "b")),
                                             _REPORT, "MISSION7"))["FARM PREPS"], "2/3 SET")

    def test_m8_route_wording(self):
        duty = dict(mc.ledger_rows(_State("MISSION8", m8_route="duty"), _REPORT, "MISSION8"))
        rev = dict(mc.ledger_rows(_State("MISSION8", m8_route="revenge"), _REPORT, "MISSION8"))
        self.assertEqual(duty["ROUTE"], "HEAD OF STATE")
        self.assertEqual(rev["ROUTE"], "OLD FRIENDS")
        outcome, _attr, _quote, stamp = mc.debrief_copy(_State("MISSION8", m8_route="duty"), "MISSION8")
        self.assertIn("Interim President Vasile", outcome)
        self.assertEqual(stamp, "CASE CLOSED")


class Buttons(unittest.TestCase):
    def test_continue_only_when_a_next_mission_exists(self):
        self.assertEqual([a for a, _l in mc.button_specs(_State("MISSION3"), True)],
                         ["menu", "continue"])
        self.assertEqual([a for a, _l in mc.button_specs(_State("MISSION3"), False)], ["menu"])
        self.assertEqual([a for a, _l in mc.button_specs(_State("MISSION8"), False)], ["menu"])

    def test_continue_label_names_the_next_mission(self):
        labels = dict((a, l) for a, l in mc.button_specs(_State("MISSION4"), True))
        self.assertEqual(labels["continue"], "NEXT: MISSION 05")
        only = mc.button_specs(_State("MISSION8"), False)[0][1]
        self.assertEqual(only, "RETURN TO MENU")

    def test_keyboard_paths(self):
        pygame.init()
        state = _State("MISSION3")
        mc.enter()
        esc = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        self.assertEqual(mc.handle_event(esc, 0, 0, state, 100, True), "menu")
        enter = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        # focus defaults to the rightmost (primary) action: NEXT
        self.assertEqual(mc.handle_event(enter, 0, 0, state, 100, True), "continue")
        right = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)
        mc.handle_event(right, 0, 0, state, 100, True)
        self.assertEqual(mc.handle_event(enter, 0, 0, state, 100, True), "menu")
        # Mouse is ignored during the entrance fade.
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1)
        self.assertIsNone(mc.handle_event(click, 760, 660, state, 3, True))

    def test_single_action_ignores_arrows(self):
        pygame.init()
        state = _State("MISSION8")
        mc.enter()
        right = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)
        self.assertIsNone(mc.handle_event(right, 0, 0, state, 100, False))
        enter = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        self.assertEqual(mc.handle_event(enter, 0, 0, state, 100, False), "menu")


class Strings(unittest.TestCase):
    def test_labels_resolve(self):
        from engine.text import T, missing_keys

        for key in ("mc.archive_desk", "mc.audio_transcript", "mc.campaign_concluded",
                    "mc.case_closed", "mc.case_file_tag", "mc.exhibit_loc",
                    "mc.filed_stamp", "mc.form_code", "mc.hint_bar",
                    "mc.krap_intel_division", "mc.main_menu", "mc.next_deployment",
                    "mc.operative_id", "mc.return_menu", "mc.sec_outcome",
                    "mc.sec_record"):
            self.assertNotEqual(T(key), "", key)
        self.assertEqual(T("mc.next_mission", num="04"), "NEXT: MISSION 04")
        self.assertEqual(T("mc.case_file_tag", tag="M-03"), "CASE FILE // M-03")
        self.assertEqual(missing_keys(), ())


class Diorama(unittest.TestCase):
    """The live exhibit viewport (ui/mission_complete_3d.py).

    The full 9-cut sweep lives in tools/preview_mission_complete.py; here we
    only pin the contract the dossier relies on: the opt-out kills it, a cut
    comes back at exhibit size, and a repeat inside the reuse window does no
    work.
    """

    def setUp(self):
        pygame.init()

    def test_opt_out_returns_none(self):
        from ui import mission_complete_3d as mc3d

        old = os.environ.get("ACA_MC_2D")
        os.environ["ACA_MC_2D"] = "1"
        try:
            self.assertFalse(mc3d.enabled())
            self.assertIsNone(mc3d.render("MISSION4", None, 4000))
        finally:
            if old is None:
                os.environ.pop("ACA_MC_2D", None)
            else:
                os.environ["ACA_MC_2D"] = old

    def test_cheap_cut_renders_at_exhibit_size_and_is_reused(self):
        from ui import mission_complete_3d as mc3d

        if not mc3d.enabled():
            self.skipTest("3D path disabled (ACA_MC_2D=1)")
        mc3d.enter()
        surf = mc3d.render("MISSION4", None, 4000)
        if surf is None:
            self.skipTest("no 3D back end on this machine")
        self.assertEqual(surf.get_size(), (mc3d.OUT_W, mc3d.OUT_H))
        r = mc3d._S["r"]
        is_gl = "gl" in str(getattr(r, "backend", "")).lower()
        second = mc3d.render("MISSION4", None, 4100)
        self.assertIsNotNone(second)
        if is_gl:
            # GL re-renders every frame so the drift animates; the cached
            # bytes may still match, but the object is fresh.
            self.assertEqual(second.get_size(), (mc3d.OUT_W, mc3d.OUT_H))
        else:
            # Software reuses the frame inside the throttle window.
            self.assertIs(second, surf)


if __name__ == "__main__":
    unittest.main()
