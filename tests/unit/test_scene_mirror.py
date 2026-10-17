"""core.scene_mirror (A-005): the legacy FSM replayed onto an engine SceneStack.

Drives the real ``core.fsm.GameStateManager`` with inert states through the
Mission 5 flow and compares the stack trace with ``tests/data/m5_scene_trace.txt``
(§6.2 acceptance trace; the states' own enter/exit are untouched).
"""
from __future__ import annotations

import unittest
from pathlib import Path

from tests.unit import _helpers  # noqa: F401  (sys.path + headless env)

from core.fsm import GameState, GameStateManager
from core.scene_mirror import FsmSceneMirror, LegacyStateScene
from engine.scene import SceneStack

ROOT = Path(__file__).resolve().parents[2]
OVERLAYS = frozenset({"PAUSED", "NOTEBOOK_INSPECT"})
NAMES = ("BOOT_INTRO", "MENU", "SLOT_SELECT", "MULTIPLAYER", "SETTINGS", "SHOP", "CUTSCENE",
         "BRIEFING", "WALK", "GAME", "ESCAPE_CUTSCENE", "NOTEBOOK_INSPECT", "PAUSED", "DEATH",
         "MISSION_COMPLETE")

# The FSM path of a complete M5 run (see the data file for the narrative).
M5_FLOW = ["MENU", "SLOT_SELECT", "BRIEFING", "CUTSCENE", "GAME", "PAUSED", "GAME",
           "NOTEBOOK_INSPECT", "GAME", "CUTSCENE", "GAME", "DEATH", "GAME",
           "GAME",                      # restart from the pause menu: same state re-entered
           "PAUSED", "MENU",            # quit to menu from the pause overlay
           "SLOT_SELECT", "GAME", "CUTSCENE", "MISSION_COMPLETE", "MENU"]


def _gsm(journal):
    gsm = GameStateManager()
    for n in NAMES:
        st = GameState()
        st.name = n
        st.enter = (lambda n=n: journal.append(("enter", n)))
        st.exit = (lambda n=n: journal.append(("exit", n)))
        gsm.add(st)
    return gsm


def expected_lines():
    txt = (ROOT / "tests" / "data" / "m5_scene_trace.txt").read_text(encoding="utf-8")
    return [ln.strip() for ln in txt.splitlines() if ln.strip() and not ln.startswith("#")]


class Mirror(unittest.TestCase):
    def test_m5_flow_matches_expected_trace(self):
        journal = []
        gsm = _gsm(journal)
        gsm.transition("BOOT_INTRO")              # before the mirror attaches: seeds the stack
        stack = SceneStack()
        FsmSceneMirror(gsm, stack, OVERLAYS)
        self.assertEqual(stack.names(), ["BOOT_INTRO"])
        for name in M5_FLOW:
            gsm.transition(name)
        self.assertEqual(stack.trace, expected_lines())
        self.assertEqual(stack.names(), ["MENU"])
        # the FSM itself was not altered by the observer: every transition still enters/exits
        self.assertEqual(journal.count(("enter", "GAME")), M5_FLOW.count("GAME"))

    def test_overlay_states_push_and_pop(self):
        gsm = _gsm([])
        stack = SceneStack()
        FsmSceneMirror(gsm, stack, OVERLAYS)
        gsm.transition("GAME")
        gsm.transition("PAUSED")
        self.assertEqual(stack.names(), ["GAME", "PAUSED"])
        self.assertTrue(stack.top.overlay)
        self.assertFalse(stack.is_paused(stack.scenes[0]))
        gsm.transition("GAME")
        self.assertEqual(stack.names(), ["GAME"])
        self.assertEqual(stack.trace, ["push GAME", "push PAUSED", "pop PAUSED"])

    def test_faded_transition_is_mirrored_at_the_swap(self):
        gsm = _gsm([])
        stack = SceneStack()
        FsmSceneMirror(gsm, stack, OVERLAYS)
        gsm.transition("MENU")
        gsm.trigger_transition("GAME")
        swaps = 0
        while gsm.transitioning:
            gsm.update_transition()
            if stack.top.name == "GAME":
                swaps += 1
        self.assertEqual(stack.names(), ["GAME"])
        self.assertGreater(swaps, 0)
        self.assertEqual(stack.trace, ["push MENU", "replace MENU -> GAME"])

    def test_detach_restores_plain_fsm(self):
        gsm = _gsm([])
        stack = SceneStack()
        m = FsmSceneMirror(gsm, stack, OVERLAYS)
        gsm.transition("MENU")
        m.detach()
        gsm.transition("GAME")
        self.assertIsNone(gsm.on_change)
        self.assertEqual(stack.names(), ["MENU"])
        self.assertIsInstance(stack.top, LegacyStateScene)


if __name__ == "__main__":
    unittest.main()
