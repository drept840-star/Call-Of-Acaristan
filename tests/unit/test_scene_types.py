"""engine.scene.CutsceneScene / InspectScene (§6.2) and the mirror's scene factory (A-007)."""
from __future__ import annotations

import unittest

from tests.unit import _helpers  # noqa: F401  (sys.path + headless env)

from core.fsm import GameState, GameStateManager
from core.scene_mirror import FsmSceneMirror
from engine.scene import CutsceneScene, InspectScene, Scene, SceneStack


class Cutscene(unittest.TestCase):
    def shots(self):
        return [{"scene": "a", "duration": 1000}, {"scene": "b", "duration": 500}, {"scene": "c", "duration": 250}]

    def test_cursor_carries_overshoot_and_ends_once(self):
        ends = []
        cs = CutsceneScene("intro", self.shots(), on_end=lambda ctx: ends.append(ctx))
        self.assertEqual(cs.name, "CUTSCENE[intro]")
        cs.advance(999)
        self.assertEqual((cs.index, cs.elapsed_ms), (0, 999.0))
        cs.advance(2)                      # 1001 -> shot b at 1 ms
        self.assertEqual((cs.index, cs.elapsed_ms), (1, 1.0))
        cs.advance(5000)                   # runs off the end
        self.assertTrue(cs.done)
        self.assertIsNone(cs.shot)
        self.assertEqual(ends, [None])
        cs.advance(10)
        cs.skip()
        self.assertEqual(ends, [None])     # finished exactly once

    def test_skip_and_handle(self):
        cs = CutsceneScene("x", self.shots())
        cs.advance(300)
        self.assertTrue(cs.handle(None, ["skip"]))
        self.assertEqual((cs.index, cs.elapsed_ms), (1, 0.0))
        self.assertFalse(cs.handle(None, ["jump"]))

        class Ev:
            action = "confirm"
        cs.handle(None, [Ev()])
        self.assertEqual(cs.index, 2)

    def test_draws_current_shot_and_pops_itself_from_the_stack(self):
        drawn = []
        stack = SceneStack(ctx="CTX")
        base = Scene("GAME")
        stack.push(base)
        cs = CutsceneScene("t", self.shots(), renderer=lambda ctx, shot, t: drawn.append((ctx, shot["scene"], t)))
        stack.push(cs)
        self.assertTrue(stack.is_paused(base))
        stack.update(0.25)                 # real-time seconds
        stack.draw(1.0)
        self.assertEqual(drawn, [("CTX", "a", 250.0)])
        stack.update(5.0)                  # ends -> deferred pop after the dispatch
        self.assertEqual(stack.names(), ["GAME"])
        self.assertFalse(stack.is_paused(base))
        self.assertEqual(stack.trace, ["push GAME", "push CUTSCENE[t]", "pop CUTSCENE[t]"])

    def test_empty_shots_is_done_immediately(self):
        self.assertTrue(CutsceneScene("e", []).done)


class FakeInspect:
    """Shape of missions.m5.inspect_fpv: start/update/draw/skip/active."""
    def __init__(self):
        self.key, self.t, self.drawn, self.skipped = None, 0.0, 0, 0

    def active(self):
        return self.key is not None

    def start(self, key, caption=None):
        self.key, self.t = key, 0.0

    def update(self, dt_ms):
        self.t += dt_ms
        if self.t >= 1000:
            self.key = None
        return self.active()

    def draw(self, surface):
        self.drawn += 1

    def skip(self):
        self.skipped += 1
        self.key = None


class Inspect(unittest.TestCase):
    def test_overlay_freezes_below_and_pops_when_inactive(self):
        ctrl = FakeInspect()
        updates = []

        class Game(Scene):
            def update(self, ctx, dt):
                updates.append(dt)

        class Ctx:
            screen = object()
        stack = SceneStack(ctx=Ctx())
        game = Game("GAME")
        stack.push(game)
        ins = InspectScene(ctrl, "ledger")
        stack.push(ins)
        self.assertEqual(ctrl.key, "ledger")              # started on enter
        self.assertFalse(stack.is_paused(game))           # overlay: not paused ...
        stack.update(0.5)
        self.assertEqual(updates, [])                     # ... but frozen (no passthrough)
        stack.draw(1.0)
        self.assertEqual(ctrl.drawn, 1)
        stack.update(0.6)                                 # controller finishes -> pop
        self.assertEqual(stack.names(), ["GAME"])
        self.assertEqual(stack.trace, ["push GAME", "push INSPECT[ledger]", "pop INSPECT[ledger]"])

    def test_skip_action_forwards_and_everything_else_is_swallowed(self):
        ctrl = FakeInspect()
        ins = InspectScene(ctrl, "k")
        ins.on_enter(None)
        self.assertTrue(ins.handle(None, ["move_left"]))
        self.assertEqual(ctrl.skipped, 0)
        self.assertTrue(ins.handle(None, ["cancel"]))
        self.assertEqual(ctrl.skipped, 1)


class MirrorFactory(unittest.TestCase):
    def test_cutscene_state_becomes_a_cutscene_scene(self):
        gsm = GameStateManager()
        for n in ("MENU", "CUTSCENE", "GAME", "PAUSED"):
            st = GameState()
            st.name = n
            gsm.add(st)
        stack = SceneStack()
        shots = [{"scene": "m5_tv_bulletin", "duration": 10}] * 3

        def factory(name, overlay):
            if name == "CUTSCENE":
                return CutsceneScene("m5_tv_bulletin+3", shots)
            return None
        FsmSceneMirror(gsm, stack, {"PAUSED"}, scene_factory=factory)
        for n in ("MENU", "CUTSCENE", "GAME", "PAUSED", "GAME", "CUTSCENE", "CUTSCENE", "GAME"):
            gsm.transition(n)
        self.assertEqual(stack.trace, [
            "push MENU", "replace MENU -> CUTSCENE[m5_tv_bulletin+3]", "replace CUTSCENE[m5_tv_bulletin+3] -> GAME",
            "push PAUSED", "pop PAUSED", "replace GAME -> CUTSCENE[m5_tv_bulletin+3]",
            "replace CUTSCENE[m5_tv_bulletin+3] -> CUTSCENE[m5_tv_bulletin+3]",
            "replace CUTSCENE[m5_tv_bulletin+3] -> GAME"])
        self.assertIsInstance(stack.scenes[0], Scene)


if __name__ == "__main__":
    unittest.main()
