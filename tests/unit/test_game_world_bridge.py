"""game.world bridge (RPE6 Phase 5, D4): ensure/get, roster reset + removed-tag policy, WalkCycle.advance."""
from __future__ import annotations

import os
import sys
import types
import unittest
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

import game.world as gw  # noqa: E402
from engine.world import POST, SIM, FunctionSystem, LegacyRef, Tags, WalkCycle, component  # noqa: E402


@component
@dataclass(slots=True)
class _TestTag:
    kind: str = ""
    counted: bool = False
    hp0: object = None


class _FakeEnemy:
    """Duck-typed like entities.enemy_ai.Enemy: rect + hp + state (+ a declared WalkCycle)."""

    _uid = 0

    def __init__(self, x=10, y=20):
        self.rect = pygame.Rect(x, y, 32, 32)
        self.hp = 95.0
        self.max_hp = 95.0
        self.angle = 0.0
        self.state = "PATROL"
        self.uid = _FakeEnemy._uid
        _FakeEnemy._uid += 1
        self.walk = WalkCycle()


class _FakeDoor:
    """Duck-typed like core.interactions.Door: rect + anim_progress (+ locked)."""

    def __init__(self, x=64, y=64):
        self.rect = pygame.Rect(x, y, 64, 64)
        self.anim_progress = 0.0
        self.locked = False
        self.collision_disabled = False


def _state():
    return types.SimpleNamespace(player=None, enemies=[], doors=[], pickups=[], corpses=[], fire_zones=[], dt=1 / 60)


class TestEnsure(unittest.TestCase):
    def setUp(self):
        self.state = _state()
        gw.install(self.state)
        gw.reset()

    def test_ensure_creates_default_component_once(self):
        e = _FakeEnemy()
        self.state.enemies.append(e)
        c = gw.ensure(e, _TestTag)
        self.assertEqual((c.kind, c.counted, c.hp0), ("", False, None))   # getattr(e, "x", default) semantics
        c.kind = "marksman"
        self.assertIs(gw.ensure(e, _TestTag), c)                           # same object on every call
        self.assertEqual(gw.get(e, _TestTag).kind, "marksman")
        self.assertIsNone(gw.get(_FakeEnemy(), _TestTag))                  # unknown object -> default, no spawn

    def test_ensure_before_first_sync_then_sync_reuses_entity(self):
        e = _FakeEnemy()
        gw.ensure(e, _TestTag).counted = True        # mission starter attaches data at spawn time
        self.state.enemies.append(e)
        gw.roster().sync(self.state)                 # the PRE roster pass must not create a second entity
        self.assertEqual(gw.world().count(LegacyRef), 1)
        self.assertTrue(gw.get(e, _TestTag).counted)
        self.assertIs(gw.world().get(gw.entity_of(e), WalkCycle), e.walk)  # declared WalkCycle is the component

    def test_removed_enemy_keeps_components_and_gets_tagged(self):
        e = _FakeEnemy()
        self.state.enemies.append(e)
        gw.ensure(e, _TestTag).kind = "guard"
        gw.roster().sync(self.state)
        self.state.enemies.remove(e)                 # killed: legacy code drops it from the list
        gw.roster().sync(self.state)
        self.assertEqual(gw.get(e, _TestTag).kind, "guard")               # kill counting still sees its data
        self.assertIn("removed", gw.world().get(gw.entity_of(e), Tags).set)
        self.assertEqual(gw.roster().removed_count(), 1)

    def test_reset_detection_on_enemies_list_rebind(self):
        e = _FakeEnemy()
        self.state.enemies.append(e)
        gw.ensure(e, _TestTag)
        gw.roster().sync(self.state)
        self.state.enemies = []                      # mission restart: STATE.reset()/_reset_world_lists rebinds
        e2 = _FakeEnemy()
        self.state.enemies.append(e2)
        gw.ensure(e2, _TestTag)
        self.assertEqual(gw.roster().resets, 1)
        self.assertIsNone(gw.get(e, _TestTag))        # old entities forgotten
        self.assertEqual(gw.world().count(LegacyRef), 1)

    def test_door_components_survive_an_enemy_list_swap(self):
        from engine.world import Label, Transform
        d = _FakeDoor()
        self.state.doors.append(d)
        gw.ensure(d, _TestTag).kind = "cell"             # mission attaches door data at build time
        e = _FakeEnemy()
        self.state.enemies.append(e)
        gw.roster().sync(self.state)
        self.assertEqual(gw.world().get(gw.entity_of(d), Label).kind, "door")
        self.assertEqual(gw.world().get(gw.entity_of(d), Transform).x, 96.0)
        self.state.enemies = []                          # m3._spawn_m3_guards_once idiom: enemies swapped, doors stay
        gw.roster().sync(self.state)
        self.assertEqual(gw.get(d, _TestTag).kind, "cell")
        self.assertIsNone(gw.get(e, _TestTag))
        self.state.doors.remove(d)                       # world rebuilt: the door leaves its list -> despawned
        gw.roster().sync(self.state)
        gw.world().flush()
        self.assertIsNone(gw.get(d, _TestTag))

    def test_enemy_list_swap_keeps_objects_still_listed(self):
        e1, e2 = _FakeEnemy(), _FakeEnemy()
        self.state.enemies.extend([e1, e2])
        gw.ensure(e1, _TestTag).kind = "a"
        gw.ensure(e2, _TestTag).kind = "b"
        gw.roster().sync(self.state)
        self.state.enemies = [e2]                        # new list, one survivor (wave code / smoke restore idiom)
        gw.roster().sync(self.state)
        self.assertIsNone(gw.get(e1, _TestTag))
        self.assertEqual(gw.get(e2, _TestTag).kind, "b")
        self.assertEqual(gw.roster().resets, 1)

    def test_first_observation_never_clears(self):
        e = _FakeEnemy()
        self.state.enemies.append(e)
        gw.ensure(e, _TestTag).kind = "x"
        self.assertEqual(gw.roster().resets, 0)
        gw.roster().sync(self.state)
        self.assertEqual(gw.get(e, _TestTag).kind, "x")


class TestWalkCycleAdvance(unittest.TestCase):
    def _legacy(self, steps):
        """The sway code enemy_ai.draw used to inline: prime, then +0.22 per frame moved > 0.4."""
        prev, phase, moving = None, 0.0, False
        out = []
        for x, y in steps:
            if prev is None:
                moved = 0.0
            else:
                moved = ((x - prev[0]) ** 2 + (y - prev[1]) ** 2) ** 0.5
            prev = (x, y)
            moving = moved > 0.4
            if moving:
                phase += 0.22
            out.append((round(phase, 6), moving))
        return out

    def test_matches_legacy_sway(self):
        steps = [(0, 0), (0, 0), (1, 0), (1.3, 0), (3, 2), (3, 2), (3.5, 2.1), (10, 10)]
        w = WalkCycle()
        got = []
        for x, y in steps:
            w.advance(x, y)
            got.append((round(w.phase, 6), w.moving))
        self.assertEqual(got, self._legacy(steps))
        self.assertTrue(w.primed)

    def test_first_call_primes_without_moving(self):
        w = WalkCycle()
        self.assertFalse(w.primed)
        w.advance(500, 300)
        self.assertEqual((w.phase, w.moving, w.primed, w.last_x, w.last_y), (0.0, False, True, 500.0, 300.0))


if __name__ == "__main__":
    unittest.main()


class HostedStepTests(unittest.TestCase):
    """P5-M6: the legacy mission update runs as the ``legacy_mission_update`` SIM system."""

    def setUp(self):
        self.state = _state()
        gw.install(self.state)
        gw.reset()

    def test_step_runs_pre_sim_post_in_order_and_returns_the_result(self):
        trace = []
        sched = gw.scheduler()
        sched.add(FunctionSystem(lambda w, c, d: trace.append("sim-before"), name="t_before", phase=SIM, order=-1))
        sched.add(FunctionSystem(lambda w, c, d: trace.append("sim-after"), name="t_after", phase=SIM, order=1))
        sched.add(FunctionSystem(lambda w, c, d: trace.append("post"), name="t_post", phase=POST))
        e = _FakeEnemy()
        self.state.enemies.append(e)

        def legacy_update():
            trace.append("legacy")
            # the PRE roster pass already registered the enemy that appeared before this frame
            self.assertEqual(gw.world().count(LegacyRef), 1)
            return "mission-result"

        steps0 = sched.steps
        self.assertEqual(gw.step(legacy_update), "mission-result")
        self.assertEqual(trace, ["sim-before", "legacy", "sim-after", "post"])
        self.assertEqual(sched.steps, steps0 + 1)
        listed = [(d["phase"], d["name"]) for d in sched.describe()]
        self.assertIn((SIM, "legacy_mission_update"), listed)
        self.assertLess(listed.index(("PRE", "legacy_roster")), listed.index((SIM, "legacy_mission_update")))

    def test_step_runs_post_and_propagates_when_the_legacy_update_raises(self):
        trace = []
        gw.scheduler().add(FunctionSystem(lambda w, c, d: trace.append("post"), name="t_post", phase=POST))

        def boom():
            raise RuntimeError("legacy failure")

        with self.assertRaises(RuntimeError):
            gw.step(boom)
        self.assertEqual(trace, ["post"])
        # the host is disarmed again: a plain SIM pass must not re-run the failed callable
        gw.post_update()
        self.assertEqual(trace, ["post", "post"])
