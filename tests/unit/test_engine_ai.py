"""engine.ai: behaviour tree preemption and memory, sight reaction and
forgetting, noise muffling, squad radio/tokens/claims, and cover picking."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from engine.ai import cover, senses  # noqa: E402
from engine.ai.bt import (FAILURE, RUNNING, SUCCESS, Action, Cooldown, If,  # noqa: E402
                          Selector, Sequence, Timeout, Tree)
from engine.ai.squad import Squad  # noqa: E402
from engine.collision import BoxWorld  # noqa: E402


class BehaviourTreeTests(unittest.TestCase):
    def setUp(self):
        self.log = []

    def _act(self, name, status):
        """An action returning ``status`` (or ``status(ctx)``) that logs its
        starts, ticks and halts."""
        def fn(ctx):
            self.log.append((name, "start" if ctx.fresh else "tick"))
            return status(ctx) if callable(status) else status
        return Action(fn, halt=lambda ctx: self.log.append((name, "halt")), name=name)

    def test_higher_branch_preempts_and_halts_the_running_one(self):
        alarm = {"on": False}
        tree = Tree(Selector(If(lambda c: alarm["on"], self._act("fight", RUNNING)),
                             self._act("patrol", RUNNING)))
        bb = {}
        tree.tick(None, bb, 0.0, 0.1)
        tree.tick(None, bb, 0.1, 0.1)
        alarm["on"] = True
        tree.tick(None, bb, 0.2, 0.1)
        self.assertEqual(self.log, [("patrol", "start"), ("patrol", "tick"),
                                    ("fight", "start"), ("patrol", "halt")])
        alarm["on"] = False
        self.log.clear()
        tree.tick(None, bb, 0.3, 0.1)
        self.assertEqual(self.log, [("fight", "halt"), ("patrol", "start")])

    def test_trace_names_the_running_branch(self):
        tree = Tree(Selector(If(lambda c: False, self._act("a", RUNNING), name="hurt"),
                             Selector(self._act("b", RUNNING), name="calm")))
        bb = {}
        tree.tick(None, bb, 0.0, 0.1)
        self.assertEqual(bb["_trace"], "calm > b")
        self.assertEqual(bb["_status"], RUNNING)

    def test_sequence_resumes_at_the_running_child(self):
        n = {"b": 0}

        def b(ctx):
            n["b"] += 1
            return SUCCESS if n["b"] >= 3 else RUNNING
        tree = Tree(Sequence(self._act("a", SUCCESS), self._act("b", b), self._act("c", SUCCESS)))
        bb = {}
        for i in range(3):
            tree.tick(None, bb, i * 0.1, 0.1)
        self.assertEqual([e[0] for e in self.log], ["a", "b", "b", "b", "c"])
        self.assertEqual(bb["_status"], SUCCESS)

    def test_sequence_failure_restarts_from_the_top(self):
        tree = Tree(Sequence(self._act("a", SUCCESS), self._act("b", FAILURE)))
        bb = {}
        tree.tick(None, bb, 0.0, 0.1)
        tree.tick(None, bb, 0.1, 0.1)
        self.assertEqual([e[0] for e in self.log], ["a", "b", "a", "b"])

    def test_cooldown_skips_the_child_until_it_expires(self):
        tree = Tree(Selector(Cooldown(self._act("shoot", SUCCESS), 1.0), self._act("wait", SUCCESS)))
        bb = {}
        for t in (0.0, 0.5, 0.99, 1.0):
            tree.tick(None, bb, t, 0.1)
        self.assertEqual([e[0] for e in self.log], ["shoot", "wait", "wait", "shoot"])

    def test_timeout_fails_and_halts_a_stuck_child(self):
        tree = Tree(Timeout(self._act("walk", RUNNING), 1.0))
        bb = {}
        self.assertEqual(tree.tick(None, bb, 0.0, 0.5).bb["_status"], RUNNING)
        self.assertEqual(tree.tick(None, bb, 0.5, 0.5).bb["_status"], RUNNING)
        self.assertEqual(tree.tick(None, bb, 1.0, 0.5).bb["_status"], FAILURE)
        self.assertIn(("walk", "halt"), self.log)
        self.log.clear()
        tree.tick(None, bb, 1.5, 0.5)                    # a fresh run after the timeout
        self.assertEqual(self.log, [("walk", "start")])

    def test_one_tree_keeps_agents_apart(self):
        tree = Tree(self._act("x", RUNNING))
        bb1, bb2 = {}, {}
        tree.tick(1, bb1, 0.0, 0.1)
        tree.tick(2, bb2, 0.0, 0.1)
        tree.tick(1, bb1, 0.1, 0.1)
        self.assertEqual(self.log, [("x", "start"), ("x", "start"), ("x", "tick")])


class SightTests(unittest.TestCase):
    def setUp(self):
        self.sight = senses.Sight(fov=120, range=40, near=3, react=(0.2, 1.0), forget=2.0)

    def test_cone_and_near_radius(self):
        eye, fwd = (0.0, 1.5, 0.0), (0.0, 1.0)
        self.assertTrue(self.sight.in_view(eye, fwd, (0.0, 1.5, 20.0)))
        self.assertFalse(self.sight.in_view(eye, fwd, (0.0, 1.5, -20.0)))
        self.assertTrue(self.sight.in_view(eye, fwd, (0.0, 1.5, -2.0)))     # heard breathing
        self.assertFalse(self.sight.in_view(eye, fwd, (0.0, 1.5, 41.0)))

    def _ticks_to_contact(self, dist):
        mem = senses.new_memory()
        for k in range(1000):
            if self.sight.update(mem, k * 0.01, 0.01, True, (0, 0, dist), dist):
                return k + 1
        return None

    def test_far_targets_take_longer_to_notice(self):
        near, far = self._ticks_to_contact(4.0), self._ticks_to_contact(36.0)
        self.assertLess(near, far)
        self.assertAlmostEqual(far * 0.01, 0.2 + 0.8 * 0.9, delta=0.02)

    def test_losing_sight_turns_into_a_lead(self):
        mem = senses.new_memory()
        senses.on_hit(mem, 0.0, (5.0, 1.4, 5.0))
        self.assertTrue(mem["contact"])
        self.sight.update(mem, 1.0, 0.1, False, (0, 0, 0), 0.0)
        self.assertTrue(mem["contact"])
        self.sight.update(mem, 2.5, 0.1, False, (0, 0, 0), 0.0)
        self.assertFalse(mem["contact"])
        self.assertEqual(mem["lead"], (5.0, 1.4, 5.0))
        self.assertEqual(mem["lead_kind"], "lost")


class NoiseTests(unittest.TestCase):
    def test_a_wall_muffles_far_sounds_but_not_near_ones(self):
        bus = senses.NoiseBus(muffle=0.5)
        wall = lambda a, b: True          # noqa: E731
        bus.emit(0.0, (0.0, 0.0, 0.0), 10.0, "shot")
        mem = senses.new_memory()
        self.assertIsNotNone(bus.listen(mem, 0.1, (7.0, 0.0, 0.0)))
        mem = senses.new_memory()
        self.assertIsNone(bus.listen(mem, 0.1, (7.0, 0.0, 0.0), blocked=wall))
        mem = senses.new_memory()
        self.assertIsNotNone(bus.listen(mem, 0.1, (4.0, 0.0, 0.0), blocked=wall))

    def test_each_sound_is_heard_once_and_the_loudest_wins(self):
        bus = senses.NoiseBus()
        bus.emit(0.0, (8.0, 0.0, 0.0), 10.0, "step")
        bus.emit(0.0, (2.0, 0.0, 0.0), 10.0, "shot")
        mem = senses.new_memory()
        self.assertEqual(bus.listen(mem, 0.1, (0.0, 0.0, 0.0))[3], "shot")
        self.assertIsNone(bus.listen(mem, 0.2, (0.0, 0.0, 0.0)))
        bus.prune(5.0)
        self.assertEqual(bus.events, [])


class SquadTests(unittest.TestCase):
    def test_reports_arrive_after_the_radio_delay_and_not_to_the_sender(self):
        sq = Squad(radio=1.0)
        sq.report(0.0, (1.0, 0.0, 2.0), by="a")
        self.assertIsNone(sq.intel(0.5, me="b"))
        self.assertEqual(sq.intel(1.0, me="b"), ((1.0, 0.0, 2.0), 1.0))
        self.assertIsNone(sq.intel(1.0, me="a"))

    def test_instant_report_skips_the_delay(self):
        sq = Squad(radio=1.0)
        sq.report(0.0, (3.0, 0.0, 0.0), by="officer", instant=True)
        self.assertEqual(sq.intel(0.0, me="b")[0], (3.0, 0.0, 0.0))

    def test_fire_tokens_cap_the_shooters(self):
        sq = Squad(shooters=2)
        self.assertTrue(sq.fire_token(0.0, "a", 1.0))
        self.assertTrue(sq.fire_token(0.0, "b", 1.0))
        self.assertFalse(sq.fire_token(0.0, "c", 1.0))
        self.assertTrue(sq.fire_token(0.5, "a", 1.0))     # keeping his own
        sq.release("b")
        self.assertTrue(sq.fire_token(0.5, "c", 1.0))
        self.assertFalse(sq.fire_token(1.2, "d", 1.0))    # a held till 1.5
        self.assertTrue(sq.fire_token(1.6, "d", 1.0))
        self.assertFalse(sq.has_token(1.6, "a"))

    def test_claims_are_exclusive_and_freed_on_forget(self):
        sq = Squad()
        self.assertTrue(sq.claim("spot1", "a"))
        self.assertFalse(sq.claim("spot1", "b"))
        self.assertTrue(sq.claimed("spot1", by_other_than="b"))
        self.assertFalse(sq.claimed("spot1", by_other_than="a"))
        self.assertTrue(sq.claim("spot2", "a"))          # moving on frees the old one
        self.assertTrue(sq.claim("spot1", "b"))
        sq.forget("a")
        self.assertEqual(sq.claims(), {"spot1": "b"})


class CoverTests(unittest.TestCase):
    """A low crate and a tall wall on open ground, the threat to the north
    (+z) of both."""

    def setUp(self):
        self.world = BoxWorld([(-1.0, 0.0, -0.5, 1.0, 1.0, 0.5),          # low crate
                               (8.0, 0.0, -0.5, 12.0, 3.0, 0.5)])         # tall wall
        self.spots = cover.build_spots(self.world, lambda x, z: True, lambda x, z: 0.0)
        self.threat = (0.0, 1.4, 15.0)

    def test_spots_ring_the_boxes_and_know_their_height(self):
        crate = [s for s in self.spots if s.box == 0]
        wall = [s for s in self.spots if s.box == 1]
        self.assertTrue(crate and wall)
        self.assertTrue(all(s.low for s in crate))
        self.assertFalse(any(s.low for s in wall))
        for s in self.spots:
            self.assertFalse(self.world.body_hits(s.x, s.z, 0.3, 0.1, 1.8), s)

    def test_only_the_far_side_hides(self):
        for s in self.spots:
            if s.box == 0 and abs(s.nx) < 0.5:
                self.assertEqual(cover.hides(s, self.threat, self.world), s.nz < 0, s)

    def test_low_cover_shoots_over_and_tall_cover_steps_out(self):
        low = next(s for s in self.spots if s.box == 0 and s.nz < -0.5)
        self.assertEqual(cover.peek_point(low), low.pos)
        self.assertTrue(cover.can_peek(low, self.threat, self.world))
        tall = min((s for s in self.spots if s.box == 1 and s.nz < -0.5), key=lambda s: s.edge)
        px, _py, pz = cover.peek_point(tall)
        self.assertTrue(px < 8.0 or px > 12.0)          # past the wall's end
        self.assertTrue(cover.can_peek(tall, (10.0, 1.4, 15.0), self.world))

    def test_pick_prefers_near_cover_that_hides_and_skips_taken_spots(self):
        me = (0.0, 0.0, -3.0)
        s = cover.pick(self.spots, me, self.threat, self.world, band=(4, 30), ideal=14)
        self.assertIsNotNone(s)
        self.assertEqual(s.box, 0)
        self.assertTrue(cover.hides(s, self.threat, self.world))
        s2 = cover.pick(self.spots, me, self.threat, self.world, taken=lambda o: o.id == s.id)
        self.assertIsNotNone(s2)
        self.assertNotEqual(s2.id, s.id)

    def test_mates_spread_the_picks(self):
        me = (0.0, 0.0, -3.0)
        alone = cover.pick(self.spots, me, self.threat, self.world)
        shared = cover.pick(self.spots, me, self.threat, self.world, mates=[alone.pos], spread=3.5)
        self.assertNotEqual(shared.id, alone.id)        # the crate's other back spot
        self.assertGreaterEqual(math.hypot(shared.x - alone.x, shared.z - alone.z), 0.99)

    def test_nothing_in_band_is_none(self):
        self.assertIsNone(cover.pick(self.spots, (0.0, 0.0, -3.0), self.threat, self.world,
                                     band=(40, 50)))
        self.assertIsNone(cover.pick(self.spots, (0.0, 0.0, -3.0), self.threat, self.world,
                                     reachable=lambda s: False))


if __name__ == "__main__":
    unittest.main()
