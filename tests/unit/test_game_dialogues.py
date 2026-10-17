"""game.dialogues converter: node chain -> legacy beat dicts (RPE6 Phase 7)."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import game.dialogues as gd  # noqa: E402

DOC = {"schema": "ae.dialogue/1", "id": "t.conv", "start": "n1",
       "speakers": {"ADA": {}, "BOB": {}},
       "nodes": {"n1": {"speaker": "ADA", "text": "one", "next": "n2"},
                 "n2": {"speaker": "BOB", "text": "pick", "next": None,
                        "choices": [{"label": "yes", "next": "r1"},
                                    {"label": "no", "next": "r2"}]},
                 "r1": {"speaker": "BOB", "text": "said yes", "next": None},
                 "r2": {"speaker": "BOB", "text": "said no", "next": None}}}

COLORS = {"ADA": (1, 2, 3), "BOB": (4, 5, 6)}


class ConverterTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        with open(os.path.join(self._tmp.name, "t.conv.dlg.json"), "w", encoding="utf-8") as fh:
            json.dump(DOC, fh)
        self._old = (gd.DIALOGUES_DIR, dict(gd._cache))
        gd.DIALOGUES_DIR = self._tmp.name
        gd._cache.clear()
        self._old_env = os.environ.get("ACA_DLG_SRC")
        os.environ.pop("ACA_DLG_SRC", None)

    def tearDown(self):
        gd.DIALOGUES_DIR, cache = self._old
        gd._cache.clear()
        gd._cache.update(cache)
        self._tmp.cleanup()
        if self._old_env is None:
            os.environ.pop("ACA_DLG_SRC", None)
        else:
            os.environ["ACA_DLG_SRC"] = self._old_env

    def test_plain_beats(self):
        self.assertEqual(
            gd.beats("t.conv", [], COLORS),
            [{"speaker": "ADA", "color": (1, 2, 3), "text": "one"},
             {"speaker": "BOB", "color": (4, 5, 6), "prompt": "pick",
              "options": [("yes", "said yes"), ("no", "said no")]}])

    def test_typed_beats(self):
        beats = gd.beats("t.conv", [], COLORS, typed=True)
        self.assertEqual(beats[0]["type"], "line")
        self.assertEqual(beats[1]["type"], "choice")
        self.assertEqual(beats[1]["options"][1], ("no", "said no"))

    def test_fresh_list_each_call(self):
        a = gd.beats("t.conv", [], COLORS)
        a.append({"junk": True})
        self.assertEqual(len(gd.beats("t.conv", [], COLORS)), 2)

    def test_legacy_identity(self):
        legacy = [{"speaker": "X", "text": "raw"}]
        os.environ["ACA_DLG_SRC"] = "legacy"
        self.assertIs(gd.beats("t.conv", legacy, COLORS, typed=True), legacy)


if __name__ == "__main__":
    unittest.main()
