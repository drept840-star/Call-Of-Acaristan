"""engine.world kernel: registry, storage, views, queries, scheduler phases, prefabs (RPE6 Phase 5)."""
import json
import os
import sys
import tempfile
import unittest
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

from engine.core import SchemaError  # noqa: E402
from engine.world import (  # noqa: E402
    POST, PRE, RENDER_SUBMIT, SIM, FunctionSystem, Health, Label, PrefabLibrary, Scheduler, System, Tags,
    Transform, WalkCycle, World, WorldError, component, from_dict, is_component, load_prefabs, schema, to_dict,
)


@component
@dataclass
class _Probe:
    n: int = 0
    names: set = None


class _RectOwner:
    """Stand-in for a legacy object: a Transform view over its rect-like fields."""

    def __init__(self, x, y):
        self.cx, self.cy = x, y
        self.angle = 0.0
        self.prev_x = self.prev_y = 0.0

    x = property(lambda s: s.cx, lambda s, v: setattr(s, "cx", v))
    y = property(lambda s: s.cy, lambda s, v: setattr(s, "cy", v))


class TestRegistry(unittest.TestCase):
    def test_component_requires_dataclass(self):
        with self.assertRaises(SchemaError):
            component(type("NotData", (), {}))

    def test_registered_and_schema(self):
        self.assertTrue(is_component(Transform))
        self.assertFalse(is_component(Transform()))
        self.assertIn("WalkCycle", schema())
        self.assertEqual([f for f, _ in schema()["WalkCycle"]], ["phase", "moving", "last_x", "last_y", "primed"])

    def test_to_from_dict_roundtrip_sets(self):
        t = Tags({"b", "a"})
        d = to_dict(t)
        self.assertEqual(d, {"set": ["a", "b"]})
        self.assertEqual(from_dict(Tags, d).set, {"a", "b"})
        with self.assertRaises(SchemaError):
            from_dict(Health, {"hp": 1, "bogus": 2})

    def test_std_components_reject_attribute_stuffing(self):
        with self.assertRaises(AttributeError):
            Transform().extra = 1  # slots=True (D4)


class TestWorld(unittest.TestCase):
    def test_spawn_get_has_remove(self):
        w = World()
        e = w.spawn(Transform(1, 2), Health(5, 10))
        self.assertTrue(w.has(e, Transform, Health))
        self.assertEqual(w.get(e, Transform).x, 1)
        self.assertIsNone(w.get(e, Tags))
        self.assertEqual(w.get(e, Tags, "dflt"), "dflt")
        w.remove(e, Health)
        self.assertFalse(w.has(e, Health))
        with self.assertRaises(WorldError):
            w.require(e, Health)
        with self.assertRaises(WorldError):
            w.add(999, Transform())
        with self.assertRaises(WorldError):
            w.add(e, object())  # not a component

    def test_query_spawn_order_and_snapshot(self):
        w = World()
        ids = [w.spawn(Health(hp=i)) for i in range(3)]
        w.add(ids[1], Transform())
        self.assertEqual([e for e, _ in w.query(Health)], ids)
        self.assertEqual([e for e, _ in w.query(Transform, Health)], [ids[1]])
        seen = []
        for eid, (h,) in w.query(Health):
            seen.append(eid)
            w.despawn(ids[2])
            w.spawn(Health())
        self.assertEqual(seen, ids[:2])
        self.assertEqual(w.count(Health), 4)
        self.assertEqual(w.flush(), 1)
        self.assertEqual(w.count(Health), 4)
        self.assertFalse(w.alive(ids[2]))
        with self.assertRaises(WorldError):
            list(w.query())

    def test_views_read_and_write_through(self):
        w = World()
        owner = _RectOwner(10, 20)
        e = w.spawn()
        w.add(e, owner, kind=Transform)
        t = w.get(e, Transform)
        self.assertIs(t, owner)
        t.x = 11
        self.assertEqual(owner.cx, 11)
        self.assertEqual(w.dump_entity(e)["Transform"]["x"], 11)
        with self.assertRaises(WorldError):
            w.add(w.spawn(), object(), kind=Health)  # view lacks fields

    def test_dump_counts(self):
        w = World()
        w.spawn(Transform(), Health())
        w.spawn(Transform())
        d = w.dump()
        self.assertEqual(d["entities"], 2)
        self.assertEqual(d["components"]["Transform"]["count"], 2)
        self.assertEqual(d["components"]["Health"]["count"], 1)
        self.assertEqual(d["components"]["Health"]["fields"], ["hp", "max"])

    def test_readonly_guard(self):
        w = World()
        w.set_readonly(True)
        with self.assertRaises(WorldError):
            w.spawn()
        w.set_readonly(False)
        self.assertEqual(w.spawn(), 1)


class TestScheduler(unittest.TestCase):
    def test_phase_order_and_system_order(self):
        w = World()
        log = []
        sch = Scheduler(w)
        for phase in (RENDER_SUBMIT, POST, SIM, PRE):
            sch.add(FunctionSystem(lambda wd, ctx, dt, p=phase: log.append(p), name=phase, phase=phase))
        sch.add(FunctionSystem(lambda wd, ctx, dt: log.append("SIM-early"), name="early", phase=SIM, order=-1))
        sch.step(None, 1 / 60)
        self.assertEqual(log, [PRE, "SIM-early", SIM, POST, RENDER_SUBMIT])
        self.assertEqual([s["name"] for s in sch.describe()][:3], [PRE, "early", SIM])
        self.assertEqual(sch.steps, 1)

    def test_post_flushes_deferred_despawns(self):
        w = World()
        e = w.spawn(Health())
        sch = Scheduler(w)
        sch.add(FunctionSystem(lambda wd, ctx, dt: wd.despawn(e), name="kill", phase=SIM))
        sch.run_phase(SIM)
        self.assertIn(e, w)
        sch.run_phase(POST)
        self.assertNotIn(e, w)

    def test_render_systems_cannot_mutate_in_debug(self):
        w = World()
        sch = Scheduler(w, debug=True)
        sch.add(FunctionSystem(lambda wd, ctx, dt: wd.spawn(), name="bad_render", phase=RENDER_SUBMIT))
        with self.assertRaises(WorldError):
            sch.run_phase(RENDER_SUBMIT)
        self.assertFalse(w.readonly)  # guard released even on error

    def test_render_system_declaring_writes_refused(self):
        class Bad(System):
            phase = RENDER_SUBMIT
            writes = (Transform,)

            def run(self, world, ctx, dt):
                pass

        with self.assertRaises(WorldError):
            Scheduler(World()).add(Bad())
        with self.assertRaises(WorldError):
            Scheduler(World()).add(FunctionSystem(lambda *a: None, phase="BOGUS"))

    def test_remove_and_enabled(self):
        w = World()
        sch = Scheduler(w)
        hits = []
        s = sch.add(FunctionSystem(lambda wd, ctx, dt: hits.append(1), name="s", phase=SIM))
        s.enabled = False
        sch.step()
        self.assertEqual(hits, [])
        self.assertTrue(sch.remove("s"))
        self.assertIsNone(sch.find("s"))


class TestPrefabs(unittest.TestCase):
    BASE = {"schema": "ae.prefab/1", "id": "t/base",
            "components": {"Health": {"hp": 70, "max": 70}, "Tags": {"set": ["guard"]}}}
    CHILD = {"id": "t/raider", "extends": "t/base",
             "components": {"Health": {"max": 90}, "Label": {"text": "Raider"}}}

    def test_resolve_diff_instantiate(self):
        lib = PrefabLibrary([self.BASE, self.CHILD])
        self.assertEqual(lib.chain("t/raider"), ["t/base", "t/raider"])
        self.assertEqual(lib.resolve("t/raider")["Health"], {"hp": 70, "max": 90})
        self.assertEqual(lib.diff("t/raider"), {"Health": {"max": 90}, "Label": {"text": "Raider"}})
        w = World()
        e = lib.instantiate(w, "t/raider", {"Transform": {"x": 5}})
        self.assertEqual(w.get(e, Health).max, 90)
        self.assertEqual(w.get(e, Tags).set, {"guard"})
        self.assertEqual(w.get(e, Label).text, "Raider")
        self.assertEqual(w.get(e, Transform).x, 5)

    def test_errors(self):
        lib = PrefabLibrary([self.BASE])
        with self.assertRaises(SchemaError):
            lib.resolve("t/missing")
        lib.add({"id": "a", "extends": "b", "components": {}})
        lib.add({"id": "b", "extends": "a", "components": {}})
        with self.assertRaises(SchemaError):
            lib.chain("a")
        lib.add({"id": "bad", "components": {"Health": {"nope": 1}}})
        with self.assertRaises(SchemaError):
            lib.build("bad")
        with self.assertRaises(SchemaError):
            PrefabLibrary([{"schema": "ae.prefab/9", "id": "x"}])

    def test_load_from_directory(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "base.prefab.json"), "w", encoding="utf-8") as fh:
                json.dump(self.BASE, fh)
            os.mkdir(os.path.join(d, "sub"))
            with open(os.path.join(d, "sub", "more.prefab.json"), "w", encoding="utf-8") as fh:
                json.dump({"prefabs": [self.CHILD]}, fh)
            lib = load_prefabs(d)
            self.assertEqual(lib.ids(), ["t/base", "t/raider"])
            with self.assertRaises(SchemaError):
                load_prefabs(os.path.join(d, "nope"))


if __name__ == "__main__":
    unittest.main()
