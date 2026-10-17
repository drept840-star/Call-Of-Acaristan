"""engine.scene: lifecycle, overlay/passthrough dispatch, deferred mutations, trace (§6.2)."""
from __future__ import annotations

import unittest

from tests.unit import _helpers  # noqa: F401  (sys.path + headless env)

from engine.core import Log
from engine.scene import Scene, SceneStack


class Rec(Scene):
    """Records every hook call into a shared journal."""
    def __init__(self, name, journal, overlay=False, passthrough=False):
        super().__init__(name)
        self.journal = journal
        if overlay:
            self.overlay = True
        if passthrough:
            self.passthrough_update = True

    def _j(self, what, *extra):
        self.journal.append((self.name, what) + extra)

    def on_enter(self, ctx): self._j("enter")
    def on_exit(self, ctx): self._j("exit")
    def on_pause(self, ctx): self._j("pause")
    def on_resume(self, ctx): self._j("resume")
    def fixed_update(self, ctx, dt): self._j("fixed", dt)
    def update(self, ctx, dt): self._j("update")
    def draw(self, ctx, alpha): self._j("draw")
    def handle(self, ctx, events): self._j("handle"); return True


class StackSemantics(unittest.TestCase):
    def setUp(self):
        self.j = []
        self.stack = SceneStack(ctx="CTX")

    def test_push_pauses_below_and_pop_resumes(self):
        a, b = Rec("A", self.j), Rec("B", self.j)
        self.stack.push(a)
        self.stack.push(b)
        self.assertEqual(self.j, [("A", "enter"), ("A", "pause"), ("B", "enter")])
        self.assertTrue(self.stack.is_paused(a))
        self.stack.pop()
        self.assertEqual(self.j[3:], [("B", "exit"), ("A", "resume")])
        self.assertIs(self.stack.top, a)
        self.assertIsNone(b.stack)

    def test_overlay_does_not_pause_but_blocks_update(self):
        a = Rec("A", self.j)
        ov = Rec("OV", self.j, overlay=True)
        self.stack.push(a)
        self.stack.push(ov)
        self.assertNotIn(("A", "pause"), self.j)
        self.j.clear()
        self.stack.fixed_update(0.5)
        self.stack.draw(1.0)
        self.stack.handle([])
        self.assertEqual(self.j, [("OV", "fixed", 0.5), ("A", "draw"), ("OV", "draw"), ("OV", "handle")])

    def test_passthrough_overlay_updates_scenes_below(self):
        a = Rec("A", self.j)
        hud = Rec("HUD", self.j, overlay=True, passthrough=True)
        self.stack.push(a)
        self.stack.push(hud)
        self.j.clear()
        self.stack.fixed_update(1.0)
        self.stack.update(0.016)
        self.assertEqual(self.j, [("A", "fixed", 1.0), ("HUD", "fixed", 1.0), ("A", "update"), ("HUD", "update")])

    def test_draw_walks_down_through_overlays_only(self):
        a, b = Rec("A", self.j), Rec("B", self.j)
        o1 = Rec("O1", self.j, overlay=True)
        o2 = Rec("O2", self.j, overlay=True)
        for s in (a, b, o1, o2):
            self.stack.push(s)
        self.j.clear()
        self.stack.draw(0.0)
        self.assertEqual([n for n, *_ in self.j], ["B", "O1", "O2"])

    def test_replace_keeps_below_paused_without_resume(self):
        menu, game, death = Rec("MENU", self.j), Rec("GAME", self.j), Rec("DEATH", self.j)
        self.stack.push(menu)
        self.stack.push(game)
        self.j.clear()
        self.stack.replace(death)
        self.assertEqual(self.j, [("GAME", "exit"), ("DEATH", "enter")])
        self.assertEqual(self.stack.names(), ["MENU", "DEATH"])
        self.assertTrue(self.stack.is_paused(menu))

    def test_replace_overlay_with_full_scene_pauses_below(self):
        game, pause, menu = Rec("GAME", self.j), Rec("PAUSED", self.j, overlay=True), Rec("MENU", self.j)
        self.stack.push(game)
        self.stack.push(pause)
        self.j.clear()
        self.stack.replace(menu)
        self.assertEqual(self.j, [("PAUSED", "exit"), ("GAME", "pause"), ("MENU", "enter")])

    def test_clear_to_exits_everything_top_first(self):
        a, b, c = Rec("A", self.j), Rec("B", self.j), Rec("C", self.j)
        self.stack.push(a)
        self.stack.push(b)
        self.j.clear()
        self.stack.clear_to(c)
        self.assertEqual(self.j, [("B", "exit"), ("A", "exit"), ("C", "enter")])
        self.assertEqual(self.stack.names(), ["C"])

    def test_mutations_during_dispatch_are_deferred(self):
        stack, j = self.stack, self.j

        class Pusher(Rec):
            def update(self, ctx, dt):
                super().update(ctx, dt)
                stack.push(Rec("CHILD", j))
        p = Pusher("P", j)
        stack.push(p)
        j.clear()
        stack.update(0.0)
        # the push happened after the dispatch, never inside it
        self.assertEqual(j, [("P", "update"), ("P", "pause"), ("CHILD", "enter")])
        self.assertEqual(stack.names(), ["P", "CHILD"])
        self.assertEqual(stack.pending, 0)

    def test_scene_cannot_be_on_two_stacks_or_twice(self):
        a = Rec("A", self.j)
        self.stack.push(a)
        with self.assertRaises(ValueError):
            self.stack.push(a)
        other = SceneStack()
        with self.assertRaises(ValueError):
            other.push(a)

    def test_trace_and_log_channel(self):
        log = Log(echo_level="error")
        stack = SceneStack(log=log)

        class Fade:
            name = "fade"
        stack.push(Rec("BOOT", self.j))
        stack.replace(Rec("MENU", self.j), transition=Fade())
        stack.push(Rec("PAUSED", self.j, overlay=True))
        stack.pop()
        stack.clear_to(Rec("GAME", self.j))
        self.assertEqual(stack.trace, ["push BOOT", "replace BOOT -> MENU via fade", "push PAUSED",
                                       "pop PAUSED", "pop MENU", "push GAME"])
        self.assertEqual(stack.trace_text().splitlines()[1], "replace BOOT -> MENU via fade")
        self.assertTrue(all("[RPE6][scene] INFO: " in ln for ln in log.tail(6)))
        self.assertEqual(stack.transition, None)

    def test_empty_stack_is_safe(self):
        self.stack.pop()
        self.stack.fixed_update(1.0)
        self.stack.draw()
        self.assertFalse(self.stack.handle([]))
        self.assertEqual(len(self.stack), 0)


if __name__ == "__main__":
    unittest.main()
