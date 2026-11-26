"""tools/ai_bundle_app.py: request parsing, file reading, slicing, settings, CLI.

Imports the module only; gui() is never called, so no window opens.
"""
import contextlib
import importlib.util
import io
from pathlib import Path
import re
import tempfile
import time
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[2] / "tools"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


A = _load("ai_bundle_app")


def _make_proj(tmp_path):
    (tmp_path / ".git").mkdir(parents=True)
    for d in ("src/core", "src/ui", "src/missions/m1", "src/missions/m2", "tests", ".wolf"):
        (tmp_path / d).mkdir(parents=True)
    (tmp_path / ".wolf/STATUS.md").write_text("status\n")
    (tmp_path / "src/core/state.py").write_text("a = 1\nb = 2\n")
    (tmp_path / "src/ui/state.py").write_text("x = 1\n")
    (tmp_path / "src/core/camera.py").write_text("cam = 1\n")
    (tmp_path / "src/core/ten.py").write_text("".join("l%d = %d\n" % (i, i) for i in range(10)))
    for m in ("m1", "m2"):
        (tmp_path / "src/missions" / m / "draw3d.py").write_text("d = 1\n")
    (tmp_path.parent / (tmp_path.name + "_secret.txt")).write_text("SECRET\n")
    return tmp_path


def rels(text, root):
    reqs, missing = A.parse_request(text, root)
    return [r["rel"] for r in reqs], missing


def bundle(text, root, **kw):
    reqs, missing = A.parse_request(text, root)
    out, rows, gone = A.build_bundle(reqs, root, **kw)
    return out, rows, missing + gone


def _big_file(root, n_defs=120):
    lines = ['"""doc."""', "import os", "import sys", ""]
    for i in range(n_defs):
        lines += ["def helper_%d(x):" % i] + ["    x += %d" % k for k in range(6)] + \
                 ["    return x", ""]
    lines += ["def player_pose(a):", "    return a", ""]
    p = root / "src/core/big.py"
    p.write_text("\n".join(lines) + "\n")
    return p, lines


class AiBundleAppTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.proj = _make_proj(self.tmp_path / "proj")

    def tearDown(self):
        self._tmp.cleanup()

    # ---------------------------------------------------------------- golden cases
    def test_brace_expansion(self):
        proj = self.proj
        self.assertEqual(
            A.expand_braces("m{1..3}/x.py and {a,b}.py").splitlines(),
            ["m1/x.py and a.py", "m1/x.py and b.py", "m2/x.py and a.py", "m2/x.py and b.py",
             "m3/x.py and a.py", "m3/x.py and b.py"],
        )
        got, missing = rels("src/missions/m{1..2}/draw3d.py", proj)
        self.assertEqual(got, ["src/missions/m1/draw3d.py", "src/missions/m2/draw3d.py"])
        self.assertFalse(missing)

    def test_folder_expansion(self):
        got, missing = rels("- src/core/\n    - state.py - reset\n    - camera.py\n- src/ui/\n"
                            "    - state.py\n", self.proj)
        self.assertEqual(got, ["src/core/state.py", "src/core/camera.py", "src/ui/state.py"])
        self.assertFalse(missing)

    def test_slice_keeps_labelled_line_numbers(self):
        proj = self.proj
        _p, lines = _big_file(proj)
        self.assertGreater(len(lines), A.SLICE_LINES)
        names = ", ".join("helper_%d" % i for i in range(3, 12))      # over the 5% sliver floor
        out, rows, missing = bundle("- src/core/big.py - player_pose, " + names, proj)
        self.assertFalse(missing)
        self.assertEqual(rows[0]["mode"], "slice")
        blocks = out.split("--- START OF FILE ")[1:]
        self.assertEqual(len(blocks), rows[0]["parts"])
        self.assertGreaterEqual(len(blocks), 2)
        for blk in blocks:
            head, body = blk.split(" ---\n", 1)
            m = re.match(r"src/core/big\.py \(lines (\d+)-(\d+) of (\d+)", head)
            a, b, n = map(int, m.groups())
            self.assertEqual(n, len(lines))
            body = body.rsplit("\n--- END OF FILE src/core/big.py ---", 1)[0]
            self.assertEqual(body.split("\n"), lines[a - 1:b])
        self.assertIn("player_pose", out)
        self.assertIn("helper_7", out)
        self.assertNotIn("helper_50(", out)

    def test_whole_file_when_no_names_match(self):
        _p, lines = _big_file(self.proj)
        out, rows, _missing = bundle("- src/core/big.py - qqqzzz nothing here", self.proj)
        self.assertEqual(rows[0]["mode"], "full")
        self.assertEqual(rows[0]["sent"], len(lines))

    # ---------------------------------------------------------------- parser defects
    def test_hidden_dir_path(self):
        self.assertEqual(rels("- .wolf/STATUS.md", self.proj), ([".wolf/STATUS.md"], []))

    def test_absolute_and_space_split_paths(self):
        self.assertEqual(rels("%s\\src\\core\\state.py" % self.proj, self.proj)[0], ["src/core/state.py"])
        self.assertEqual(rels("E:\\Some Folder\\proj\\src\\core\\state.py", self.proj)[0], ["src/core/state.py"])

    def test_wrong_case_is_canonical_and_not_duplicated(self):
        got, missing = rels("- SRC/Core/Camera.py\n- src/core/camera.py", self.proj)
        self.assertEqual(got, ["src/core/camera.py"])
        self.assertFalse(missing)

    def test_path_outside_project_is_refused(self):
        got, missing = rels("- src/core/../../../%s_secret.txt" % self.proj.name, self.proj)
        self.assertEqual(got, [])
        self.assertTrue(missing)

    def test_folder_and_file_on_one_line(self):
        self.assertEqual(rels("- src/core/ camera.py", self.proj), (["src/core/camera.py"], []))

    def test_line_starting_with_a_folder_word_keeps_its_paths(self):
        self.assertEqual(rels("  - tests for this: src/core/ten.py", self.proj), (["src/core/ten.py"], []))

    def test_bare_folder_is_reported(self):
        got, missing = rels("- src/ui/", self.proj)
        self.assertEqual(got, [])
        self.assertEqual(missing, ["src/ui/ (folder: name its files)"])

    def test_ambiguous_name_is_explained(self):
        got, missing = rels("- state.py", self.proj)
        self.assertEqual(got, [])
        self.assertEqual(missing, ["state.py (ambiguous: src/core/state.py, src/ui/state.py)"])

    def test_reserved_backslash_path_is_not_missing(self):
        root = TOOLS.parent
        self.assertEqual(rels("python tools\\ai_bundle.py src/core/state.py", root), (["src/core/state.py"], []))

    def test_huge_brace_does_not_hang(self):
        t = time.time()
        A.expand_braces("m{1..999999999}/x.py")
        A.expand_braces("m{1..99999999999999999999}/x.py")
        self.assertLess(time.time() - t, 1)

    def test_long_dotted_run_parses_fast(self):
        t = time.time()
        A.parse_request("a." * 20000, self.proj)
        self.assertLess(time.time() - t, 5)          # was ~50 s: PATH_RE backtracked quadratically

    def test_folder_probe_is_cached(self):
        calls = []
        real = A._is_dir
        with patch.object(A, "_is_dir", side_effect=lambda r, p: calls.append(p) or real(r, p)):
            A.parse_request("plain words here\n" * 1000, self.proj)
        self.assertEqual(len(calls), 1)

    def test_empty_and_pathless_pastes(self):
        self.assertEqual(rels("", self.proj), ([], []))
        self.assertEqual(rels("hello\nno files here\n```\ncode\n```", self.proj), ([], []))

    # ---------------------------------------------------------------- reading and bundling
    def test_line_count_and_bytes_match_ai_bundle(self):
        proj = self.proj
        out, rows, _ = bundle("- src/core/ten.py:8-", proj)
        self.assertTrue(out.startswith("--- START OF FILE src/core/ten.py (lines 8-10 of 10) ---\nl7 = 7\n"))
        out, rows, _ = bundle("- src/core/ten.py", proj)
        self.assertEqual(rows[0]["lines"], 10)
        self.assertTrue(out.endswith("l9 = 9\n--- END OF FILE src/core/ten.py ---\n"))
        sib = _load("ai_bundle")
        reqs = [{"rel": "tools/build_apps.py", "desc": "", "ranges": []}]
        self.assertEqual(A.build_bundle(reqs, TOOLS.parent)[0], sib.bundle(["tools/build_apps.py"])[0])
        reqs[0]["ranges"] = [(5, 20)]
        self.assertEqual(A.build_bundle(reqs, TOOLS.parent)[0], sib.bundle(["tools/build_apps.py:5-20"])[0])

    def test_exactly_800_lines_is_not_sliced(self):
        body = "".join("def f%d():\n    return 1\n" % i for i in range(400))
        (self.proj / "src/core/edge.py").write_text(body)
        out, rows, _ = bundle("- src/core/edge.py - f3", self.proj)
        self.assertEqual(rows[0]["lines"], 800)
        self.assertEqual(rows[0]["mode"], "full")

    def test_range_past_end_is_reported(self):
        out, rows, missing = bundle("- src/core/ten.py:50-60", self.proj)
        self.assertEqual(out, "")
        self.assertEqual(rows, [])
        self.assertEqual(missing, ["src/core/ten.py:50-60 (file has 10 lines)"])

    def test_repeated_ranges_are_merged(self):
        out, _rows, _ = bundle("- src/core/ten.py:2-3\n- src/core/ten.py:2-3\n- src/core/ten.py:3-5", self.proj)
        self.assertEqual(out.count("START OF FILE"), 1)
        self.assertIn("(lines 2-5 of 10)", out)

    def test_listed_whole_file_beats_a_range(self):
        out, rows, _ = bundle("- src/core/ten.py:1-5\n- src/core/ten.py", self.proj)
        self.assertEqual(rows[0]["mode"], "full")
        self.assertEqual(rows[0]["sent"], 10)
        self.assertNotIn("(lines", out)
        out, rows, _ = bundle("- src/core/ten.py:1-5\nsee also src/core/ten.py", self.proj)   # prose: range kept
        self.assertEqual(rows[0]["mode"], "lines")
        self.assertEqual(rows[0]["sent"], 5)

    def test_file_text_encodings(self):
        cases = [
            (b"\xef\xbb\xbfa = 1\n", "a = 1"),                         # UTF-8 BOM
            ("a = 1\n".encode("utf-16"), "a = 1"),                     # UTF-16 with BOM
            (b"a\x00b\n", "a\ufffdb"),                                 # NUL ends Windows clipboard text
            (b"x = 1\ry = 2\r", "x = 1\ny = 2"),                       # old Mac line ends
            (b"\xff\xfe\xfdz", None),                                  # not text: no crash
        ]
        for idx, (raw, want) in enumerate(cases):
            with self.subTest(case=idx):
                p = self.tmp_path / ("f_%d.txt" % idx)
                p.write_bytes(raw)
                got = A.file_text(p)
                if want is not None:
                    self.assertEqual(got.rstrip("\n"), want)
                self.assertNotIn("\x00", got)

    def test_empty_file_and_missing_file(self):
        (self.proj / "src/core/empty.py").write_bytes(b"")
        _out, rows, missing = bundle("- src/core/empty.py", self.proj)
        self.assertEqual(rows[0]["lines"], 0)
        self.assertFalse(missing)
        self.assertIsNone(A.file_text(self.proj / "nope.py"))

    def test_unparseable_python_goes_whole(self):
        deep = "x = " + "+".join(["1"] * 200000) + "\n" + "def f():\n    pass\n" * 500
        self.assertEqual(A.pick_symbols(deep, "f"), (None, "not parseable"))
        self.assertEqual(A.pick_symbols("def (:\n", "f"), (None, "not parseable"))

    # ---------------------------------------------------------------- settings and CLI
    def test_corrupt_settings(self):
        for body in (b"[]", b"null", b"3", b"{bad", b"\xff\xfe"):
            with self.subTest(body=body):
                with tempfile.TemporaryDirectory() as td:
                    tdir = Path(td)
                    with patch.object(A, "DATA", tdir), patch.object(A, "SETTINGS", tdir / "settings.json"):
                        (tdir / "settings.json").write_bytes(body)
                        self.assertEqual(A.load_settings(), {})
                        A.save_settings(theme="dark")
                        self.assertEqual(A.load_settings(), {"theme": "dark"})

    def test_unwritable_settings(self):
        blocker = self.tmp_path / "file"
        blocker.write_text("x")
        with patch.object(A, "DATA", blocker / "sub"), patch.object(A, "SETTINGS", blocker / "sub" / "settings.json"):
            A.save_settings(theme="dark")              # must not raise
            self.assertEqual(A.load_settings(), {})

    def test_cli_bad_arguments(self):
        self.assertEqual(A.main(["--check"]), 2)
        self.assertEqual(A.main(["--check", str(self.tmp_path / "nope.txt")]), 2)
        msg = self.tmp_path / "m.txt"
        msg.write_text("- tools/build_apps.py\n- no/such/file.py\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = A.main(["--check", str(msg)])
        self.assertEqual(rc, 1)
        self.assertIn("MISSING  no/such/file.py", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
