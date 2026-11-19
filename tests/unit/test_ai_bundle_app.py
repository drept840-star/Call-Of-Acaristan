"""tools/ai_bundle_app.py: request parsing, file reading, slicing, settings, CLI.

Imports the module only; gui() is never called, so no window opens.
"""
import importlib.util
import time
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


A = _load("ai_bundle_app")


@pytest.fixture
def proj(tmp_path):
    (tmp_path / ".git").mkdir()
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


# ---------------------------------------------------------------- golden cases
def test_brace_expansion(proj):
    assert A.expand_braces("m{1..3}/x.py and {a,b}.py").splitlines() == [
        "m1/x.py and a.py", "m1/x.py and b.py", "m2/x.py and a.py", "m2/x.py and b.py",
        "m3/x.py and a.py", "m3/x.py and b.py"]
    got, missing = rels("src/missions/m{1..2}/draw3d.py", proj)
    assert got == ["src/missions/m1/draw3d.py", "src/missions/m2/draw3d.py"] and not missing


def test_folder_expansion(proj):
    got, missing = rels("- src/core/\n    - state.py - reset\n    - camera.py\n- src/ui/\n"
                        "    - state.py\n", proj)
    assert got == ["src/core/state.py", "src/core/camera.py", "src/ui/state.py"]
    assert not missing


def _big_file(root, n_defs=120):
    lines = ['"""doc."""', "import os", "import sys", ""]
    for i in range(n_defs):
        lines += ["def helper_%d(x):" % i] + ["    x += %d" % k for k in range(6)] + \
                 ["    return x", ""]
    lines += ["def player_pose(a):", "    return a", ""]
    p = root / "src/core/big.py"
    p.write_text("\n".join(lines) + "\n")
    return p, lines


def test_slice_keeps_labelled_line_numbers(proj):
    p, lines = _big_file(proj)
    assert len(lines) > A.SLICE_LINES
    names = ", ".join("helper_%d" % i for i in range(3, 12))      # over the 5% sliver floor
    out, rows, missing = bundle("- src/core/big.py - player_pose, " + names, proj)
    assert not missing and rows[0]["mode"] == "slice"
    blocks = out.split("--- START OF FILE ")[1:]
    assert len(blocks) == rows[0]["parts"] >= 2
    import re
    for blk in blocks:
        head, body = blk.split(" ---\n", 1)
        m = re.match(r"src/core/big\.py \(lines (\d+)-(\d+) of (\d+)", head)
        a, b, n = map(int, m.groups())
        assert n == len(lines)
        body = body.rsplit("\n--- END OF FILE src/core/big.py ---", 1)[0]
        assert body.split("\n") == lines[a - 1:b]
    assert "player_pose" in out and "helper_7" in out and "helper_50(" not in out


def test_whole_file_when_no_names_match(proj):
    p, lines = _big_file(proj)
    out, rows, missing = bundle("- src/core/big.py - qqqzzz nothing here", proj)
    assert rows[0]["mode"] == "full" and rows[0]["sent"] == len(lines)
    assert out == "--- START OF FILE src/core/big.py ---\n%s\n--- END OF FILE src/core/big.py ---\n" \
        % "\n".join(lines)


# ---------------------------------------------------------------- parser defects
def test_hidden_dir_path(proj):
    assert rels("- .wolf/STATUS.md", proj) == ([".wolf/STATUS.md"], [])


def test_absolute_and_space_split_paths(proj):
    assert rels("%s\\src\\core\\state.py" % proj, proj)[0] == ["src/core/state.py"]
    assert rels("E:\\Some Folder\\proj\\src\\core\\state.py", proj)[0] == ["src/core/state.py"]


def test_wrong_case_is_canonical_and_not_duplicated(proj):
    got, missing = rels("- SRC/Core/Camera.py\n- src/core/camera.py", proj)
    assert got == ["src/core/camera.py"] and not missing


def test_path_outside_project_is_refused(proj):
    got, missing = rels("- src/core/../../../%s_secret.txt" % proj.name, proj)
    assert got == [] and missing


def test_folder_and_file_on_one_line(proj):
    assert rels("- src/core/ camera.py", proj) == (["src/core/camera.py"], [])


def test_line_starting_with_a_folder_word_keeps_its_paths(proj):
    assert rels("  - tests for this: src/core/ten.py", proj) == (["src/core/ten.py"], [])


def test_bare_folder_is_reported(proj):
    got, missing = rels("- src/ui/", proj)
    assert got == [] and missing == ["src/ui/ (folder: name its files)"]


def test_ambiguous_name_is_explained(proj):
    got, missing = rels("- state.py", proj)
    assert got == [] and missing == ["state.py (ambiguous: src/core/state.py, src/ui/state.py)"]


def test_reserved_backslash_path_is_not_missing(proj):
    root = TOOLS.parent
    assert rels("python tools\\ai_bundle.py src/core/state.py", root) == (["src/core/state.py"], [])


def test_huge_brace_does_not_hang():
    t = time.time()
    A.expand_braces("m{1..999999999}/x.py")
    A.expand_braces("m{1..99999999999999999999}/x.py")
    assert time.time() - t < 1


def test_long_dotted_run_parses_fast(proj):
    t = time.time()
    A.parse_request("a." * 20000, proj)
    assert time.time() - t < 5          # was ~50 s: PATH_RE backtracked quadratically


def test_folder_probe_is_cached(proj, monkeypatch):
    calls = []
    real = A._is_dir
    monkeypatch.setattr(A, "_is_dir", lambda r, p: calls.append(p) or real(r, p))
    A.parse_request("plain words here\n" * 1000, proj)
    assert len(calls) == 1


def test_empty_and_pathless_pastes(proj):
    assert rels("", proj) == ([], [])
    assert rels("hello\nno files here\n```\ncode\n```", proj) == ([], [])


# ---------------------------------------------------------------- reading and bundling
def test_line_count_and_bytes_match_ai_bundle(proj):
    out, rows, _ = bundle("- src/core/ten.py:8-", proj)
    assert out.startswith("--- START OF FILE src/core/ten.py (lines 8-10 of 10) ---\nl7 = 7\n")
    out, rows, _ = bundle("- src/core/ten.py", proj)
    assert rows[0]["lines"] == 10 and out.endswith("l9 = 9\n--- END OF FILE src/core/ten.py ---\n")
    sib = _load("ai_bundle")
    reqs = [{"rel": "tools/build_apps.py", "desc": "", "ranges": []}]
    assert A.build_bundle(reqs, TOOLS.parent)[0] == sib.bundle(["tools/build_apps.py"])[0]
    reqs[0]["ranges"] = [(5, 20)]
    assert A.build_bundle(reqs, TOOLS.parent)[0] == sib.bundle(["tools/build_apps.py:5-20"])[0]


def test_exactly_800_lines_is_not_sliced(proj):
    body = "".join("def f%d():\n    return 1\n" % i for i in range(400))
    (proj / "src/core/edge.py").write_text(body)
    out, rows, _ = bundle("- src/core/edge.py - f3", proj)
    assert rows[0]["lines"] == 800 and rows[0]["mode"] == "full"


def test_range_past_end_is_reported(proj):
    out, rows, missing = bundle("- src/core/ten.py:50-60", proj)
    assert out == "" and rows == [] and missing == ["src/core/ten.py:50-60 (file has 10 lines)"]


def test_repeated_ranges_are_merged(proj):
    out, rows, _ = bundle("- src/core/ten.py:2-3\n- src/core/ten.py:2-3\n- src/core/ten.py:3-5", proj)
    assert out.count("START OF FILE") == 1 and "(lines 2-5 of 10)" in out


def test_listed_whole_file_beats_a_range(proj):
    out, rows, _ = bundle("- src/core/ten.py:1-5\n- src/core/ten.py", proj)
    assert rows[0]["mode"] == "full" and rows[0]["sent"] == 10 and "(lines" not in out
    out, rows, _ = bundle("- src/core/ten.py:1-5\nsee also src/core/ten.py", proj)   # prose: range kept
    assert rows[0]["mode"] == "lines" and rows[0]["sent"] == 5


@pytest.mark.parametrize("raw, want", [
    (b"\xef\xbb\xbfa = 1\n", "a = 1"),                         # UTF-8 BOM
    ("a = 1\n".encode("utf-16"), "a = 1"),                     # UTF-16 with BOM
    (b"a\x00b\n", "a\ufffdb"),                                 # NUL ends Windows clipboard text
    (b"x = 1\ry = 2\r", "x = 1\ny = 2"),                       # old Mac line ends
    (b"\xff\xfe\xfdz", None),                                  # not text: no crash
])
def test_file_text_encodings(tmp_path, raw, want):
    p = tmp_path / "f.txt"
    p.write_bytes(raw)
    got = A.file_text(p)
    if want is not None:
        assert got.rstrip("\n") == want
    assert "\x00" not in got


def test_empty_file_and_missing_file(proj):
    (proj / "src/core/empty.py").write_bytes(b"")
    out, rows, missing = bundle("- src/core/empty.py", proj)
    assert rows[0]["lines"] == 0 and not missing
    assert A.file_text(proj / "nope.py") is None


def test_unparseable_python_goes_whole():
    deep = "x = " + "+".join(["1"] * 200000) + "\n" + "def f():\n    pass\n" * 500
    assert A.pick_symbols(deep, "f") == (None, "not parseable")
    assert A.pick_symbols("def (:\n", "f") == (None, "not parseable")


# ---------------------------------------------------------------- settings and CLI
@pytest.mark.parametrize("body", [b"[]", b"null", b"3", b"{bad", b"\xff\xfe"])
def test_corrupt_settings(tmp_path, monkeypatch, body):
    monkeypatch.setattr(A, "DATA", tmp_path)
    monkeypatch.setattr(A, "SETTINGS", tmp_path / "settings.json")
    (tmp_path / "settings.json").write_bytes(body)
    assert A.load_settings() == {}
    A.save_settings(theme="dark")
    assert A.load_settings() == {"theme": "dark"}


def test_unwritable_settings(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setattr(A, "DATA", blocker / "sub")
    monkeypatch.setattr(A, "SETTINGS", blocker / "sub" / "settings.json")
    A.save_settings(theme="dark")              # must not raise
    assert A.load_settings() == {}


def test_cli_bad_arguments(tmp_path, capsys):
    assert A.main(["--check"]) == 2
    assert A.main(["--check", str(tmp_path / "nope.txt")]) == 2
    msg = tmp_path / "m.txt"
    msg.write_text("- tools/build_apps.py\n- no/such/file.py\n")
    assert A.main(["--check", str(msg)]) == 1
    assert "MISSING  no/such/file.py" in capsys.readouterr().out
