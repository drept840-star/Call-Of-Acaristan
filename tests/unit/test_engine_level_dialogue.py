"""engine.level + engine.dialogue kernels: load/validate, Tiled import, runner conditions/effects (RPE6 Phase 7)."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from engine.dialogue import DialogueHost, DialogueRunner, from_dict as dlg_from  # noqa: E402
from engine.dialogue.model import validate as dlg_validate  # noqa: E402
from engine.level import LevelError, from_dict, from_tiled, loads_level, validate  # noqa: E402

LEVEL = {"schema": "ae.level/1", "id": "m1.warehouse", "name": "Warehouse", "tile_size": 64,
         "layers": {"floor": ["CCC", "C.C", "CCC"]},
         "objects": [{"id": "p", "kind": "spawn", "tile": [1, 1], "props": {"who": "player"}}],
         "paths": [{"id": "patrol", "points": [[0, 0], [2, 0], [2, 2]]}],
         "metadata": {"objective_key": "m1.obj", "weather": {"rain": False}}}

DLG = {"schema": "ae.dialogue/1", "id": "t", "start": "a",
       "speakers": {"ADA": {"color": [1, 2, 3]}, "BOB": {}},
       "nodes": {"a": {"speaker": "ADA", "text": "hi", "next": "b", "effects": [{"set": "met", "value": True}]},
                 "b": {"speaker": "BOB", "text_key": "t.b", "condition": 'flag("met")',
                       "choices": [{"label": "go", "next": "c"}, {"label": "stay", "next": "d"}]},
                 "c": {"speaker": "ADA", "text": "went", "next": None},
                 "d": {"speaker": "ADA", "text": "stayed", "next": None}}}


class Host:
    def __init__(self):
        self.flags, self.vars, self.events = {}, {}, []

    def flag(self, n):
        return bool(self.flags.get(n) or self.vars.get(n))

    def var(self, n):
        return self.vars.get(n)

    def set_var(self, n, v):
        self.vars[n] = v

    def emit(self, n, payload=None):
        self.events.append((n, payload))

    def resolve(self, node):
        return node.get("text") or {"t.b": "key text"}.get(node.get("text_key"), "?")

    def speaker_meta(self, sp):
        return {"color": (1, 2, 3)} if sp == "ADA" else {}


class LevelTests(unittest.TestCase):
    def test_load_grid_objects_paths_and_copy_semantics(self):
        lvl = from_dict(LEVEL, "t")
        self.assertEqual(lvl.grid(), ["CCC", "C.C", "CCC"])
        g = lvl.grid()
        g[0] = "XXX"
        self.assertEqual(lvl.grid()[0], "CCC")          # copy, not a view
        self.assertEqual(lvl.size(), (3, 3))
        self.assertEqual(lvl.objects_of("spawn")[0]["tile"], [1, 1])
        self.assertEqual(lvl.path("patrol"), [(0, 0), (2, 0), (2, 2)])

    def test_validate_catches_ragged_unknown_and_bad_targets(self):
        bad = dict(LEVEL, layers={"floor": ["CC", "C"]}, bogus=1, paths=[{"id": "p", "points": [[0, 0]]}])
        probs = validate(bad)
        self.assertTrue(any("ragged" in p for p in probs))
        self.assertTrue(any("unknown top-level" in p for p in probs))
        self.assertTrue(any(">= 2 points" in p for p in probs))
        with self.assertRaises(LevelError):
            from_dict(bad)
        with self.assertRaises(LevelError):
            loads_level("{not json")

    def test_tiled_importer_maps_gids_objects_and_paths(self):
        tmj = {"type": "map", "name": "tiled.level", "tilewidth": 32,
               "layers": [{"type": "tilelayer", "name": "floor", "width": 3, "height": 2,
                           "data": [1, 1, 1, 1, 0, 1]},
                          {"type": "objectgroup", "objects": [
                              {"name": "p", "type": "spawn", "x": 32, "y": 32, "width": 0, "height": 0},
                              {"name": "door", "type": "transition", "x": 0, "y": 0, "width": 32, "height": 32},
                              {"name": "patrol", "type": "path", "x": 0, "y": 0,
                               "polyline": [{"x": 0, "y": 0}, {"x": 64, "y": 0}]}]}]}
        lvl = from_tiled(tmj, {0: ".", 1: "C"}, tile_size=32)
        self.assertEqual(lvl.grid(), ["CCC", "C.C"])
        self.assertEqual(lvl.objects_of("spawn")[0]["tile"], [1, 1])
        self.assertEqual(lvl.triggers[0]["kind"], "transition")
        self.assertEqual(lvl.path("patrol"), [(0, 0), (2, 0)])
        with self.assertRaises(LevelError):
            from_tiled(tmj, {1: "C"})                    # gid 0 unmapped -> loud


class DialogueTests(unittest.TestCase):
    def test_runner_walks_effects_conditions_choices(self):
        dlg = dlg_from(DLG)
        host = Host()
        r = DialogueRunner(dlg, host)
        line = r.begin()
        self.assertEqual((line.node_id, line.text, line.speaker), ("a", "hi", "ADA"))
        self.assertTrue(host.vars["met"])                        # effect applied on entry
        line = r.advance()                                       # b passes flag("met"), offers choices
        self.assertEqual(line.text, "key text")
        self.assertEqual([c[0] for c in line.choices], ["go", "stay"])
        with self.assertRaises(ValueError):
            r.advance()                                          # must choose
        line = r.choose(1)
        self.assertEqual(line.text, "stayed")
        end = r.advance()
        self.assertEqual(end.visited, ("a", "b", "d"))
        self.assertFalse(end.skipped)

    def test_condition_false_nodes_are_passed_through_and_skip_works(self):
        data = json.loads(json.dumps(DLG))
        data["nodes"]["b"]["condition"] = 'var("heat") > 2'
        host = Host()
        r = DialogueRunner(dlg_from(data), host)
        r.begin()
        line = r.advance()                                       # b fails condition -> follows next (None)
        self.assertEqual(line.__class__.__name__, "DialogueEnded")
        r2 = DialogueRunner(dlg_from(DLG), Host())
        r2.begin()
        end = r2.skip()
        self.assertTrue(end.skipped)
        self.assertEqual(end.visited, ("a",))

    def test_validate_catches_dangling_unreachable_speaker_and_keys(self):
        data = json.loads(json.dumps(DLG))
        data["nodes"]["a"]["next"] = "nope"
        data["nodes"]["x"] = {"speaker": "GHOST", "text": "boo", "next": None}
        probs = dlg_validate(data, {"t.b": "ok"})
        self.assertTrue(any("nope" in p for p in probs))
        self.assertTrue(any("unreachable" in p for p in probs))
        self.assertTrue(any("GHOST" in p for p in probs))
        probs = dlg_validate(DLG, {})
        self.assertTrue(any("missing from the string table" in p for p in probs))
        long_data = json.loads(json.dumps(DLG))
        long_data["nodes"]["a"]["text"] = "x" * 500
        self.assertTrue(any("box fit" in p for p in dlg_validate(long_data)))


if __name__ == "__main__":
    unittest.main()
