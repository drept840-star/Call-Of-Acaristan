"""engine.text Phase 4: string tables + `T()`, font registry + glyph coverage, layout
(measure/wrap/ellipsize/check_fit/draw_line). Headless: SDL dummy via _helpers, fonts from
the bundled TTFs, no display."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from tests.unit import _helpers  # noqa: F401  (sys.path + headless env)

import pygame

from core import font_coverage as fontcov
from engine.core import get_log
from engine.text import (FACES, T, check_fit, ellipsize, font_dir, load_face, load_strings, marker,
                         measure, missing_glyphs, missing_keys, reset_strings, table, wrap_lines)
from engine.text import strings as strings_mod


class StringTableTests(unittest.TestCase):
    def setUp(self):
        reset_strings()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _write(self, data):
        p = Path(self.tmp.name) / "en.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def test_load_and_lookup(self):
        self.assertEqual(load_strings(self._write({"m1.hud.objective": "OBJECTIVE", "m5.hud.heat": "HEAT {n}"})), 2)
        self.assertEqual(T("m1.hud.objective"), "OBJECTIVE")
        self.assertEqual(T("m5.hud.heat", n=3), "HEAT 3")
        self.assertEqual(missing_keys(), ())

    def test_missing_key_returns_marker_and_is_recorded(self):
        load_strings(self._write({}))
        self.assertEqual(T("m2.never.defined"), "[[m2.never.defined]]")
        self.assertEqual(T("m2.never.defined"), marker("m2.never.defined"))
        self.assertEqual(missing_keys(), ("m2.never.defined",))

    def test_default_used_when_missing(self):
        load_strings(self._write({"present": "value"}))
        self.assertEqual(T("absent", default="fallback"), "fallback")
        self.assertEqual(T("present", default="fallback"), "value")

    def test_bad_format_shows_marker_not_crash(self):
        load_strings(self._write({"k": "HEAT {n}"}))
        self.assertEqual(T("k"), "[[k]]")
        self.assertEqual(T("k", other=1), "[[k]]")

    def test_literal_braces_use_standard_escaping(self):
        load_strings(self._write({"pct": "100% {{done}}"}))
        self.assertEqual(T("pct"), "100% {done}")

    def test_reload_replaces_the_table(self):
        load_strings(self._write({"a": "1"}))
        self.assertEqual(T("a"), "1")
        load_strings(self._write({"b": "2"}))
        self.assertEqual(T("b"), "2")
        self.assertEqual(T("a"), "[[a]]")  # gone with the old table
        self.assertEqual(missing_keys(), ("a",))

    def test_shipped_table_parses_and_lives_in_the_content_tree(self):
        reset_strings()
        self.assertEqual(strings_mod.DEFAULT_TABLE.name, "en.json")
        self.assertEqual(strings_mod.DEFAULT_TABLE.parent.name, "strings")
        self.assertIsInstance(table(), dict)  # the shipped table loads (empty is valid at this phase)

    def test_missing_file_is_an_empty_table(self):
        n = load_strings(Path(self.tmp.name) / "does_not_exist.json")
        self.assertEqual(n, 0)
        self.assertEqual(T("anything"), "[[anything]]")


class FontRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_font_dir_has_the_bundled_faces(self):
        d = Path(font_dir())
        for fname in FACES.values():
            self.assertTrue((d / fname).exists(), f"missing bundled face {fname}")

    def test_load_face_returns_a_usable_font(self):
        f = load_face("plex_regular", 14)
        self.assertGreater(f.size("ABC")[0], 0)
        self.assertGreater(f.size("ABC")[1], 0)

    def test_load_face_accepts_a_raw_path_with_system_fallback(self):
        f = load_face(str(Path(font_dir()) / "IBMPlexMono-Bold.ttf"), 12, "Consolas", True)
        self.assertGreater(f.size("X")[0], 0)
        fb = load_face(str(Path(font_dir()) / "no_such_face.ttf"), 12, "Consolas")
        self.assertIsNotNone(fb)

    def test_coverage_reads_every_face(self):
        if not fontcov.coverage_supported():
            self.skipTest("fontTools not installed (dev-only dependency)")
        cov = fontcov.glyph_coverage()
        self.assertEqual(set(cov), set(FACES))
        self.assertIn(ord("A"), cov["plex_regular"])
        self.assertIn(0x2588, cov["plex_regular"])       # full block: Plex only
        self.assertNotIn(0x27E6, cov["oswald"])          # no dev-marker bracket glyph anywhere

    def test_missing_glyphs_verdicts(self):
        if not fontcov.coverage_supported():
            self.skipTest("fontTools not installed (dev-only dependency)")
        cov = fontcov.glyph_coverage()
        self.assertEqual(missing_glyphs("plain ASCII", cov), {})
        self.assertEqual(missing_glyphs("\u2588", cov), {})          # plex-only allowlist
        self.assertIn(0x27E6, missing_glyphs("\u27e6", cov))          # marker bracket would be tofu
        self.assertEqual(missing_glyphs("\u2588", cov, plex_only_ok=False), {0x2588: ["oswald"]})


class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.font = load_face("plex_regular", 14)

    def test_measure_matches_font_size(self):
        self.assertEqual(measure(self.font, "hello"), self.font.size("hello"))

    def test_wrap_lines_split_on_words_and_fit(self):
        lines = wrap_lines(self.font, "one two three four five six seven eight", 60)
        self.assertGreater(len(lines), 1)
        for ln in lines:
            self.assertLessEqual(measure(self.font, ln)[0], 60)

    def test_wrap_hard_splits_a_word_wider_than_the_box(self):
        lines = wrap_lines(self.font, "A" * 80, 50)
        self.assertGreater(len(lines), 1)
        for ln in lines:
            self.assertLessEqual(measure(self.font, ln)[0], 50)

    def test_wrap_keeps_explicit_newlines(self):
        self.assertEqual(wrap_lines(self.font, "a\nb", 200), ["a", "b"])

    def test_ellipsize_shortens_to_fit(self):
        text = "A very long caption line that will not fit in this narrow box at all"
        out = ellipsize(self.font, text, 120)
        self.assertLessEqual(measure(self.font, out)[0], 120)
        self.assertTrue(out.endswith("\u2026"))
        self.assertTrue(text.startswith(out[:-1]))
        self.assertEqual(ellipsize(self.font, "short", 200), "short")

    def test_check_fit_warns_once_per_key(self):
        log = get_log()

        def overflow_lines():
            return [ln for ln in log.tail(200) if "text overflow" in ln]

        before = len(overflow_lines())
        self.assertFalse(check_fit(self.font, "X" * 500, 20, key="unit.text.overflow"))
        self.assertFalse(check_fit(self.font, "X" * 500, 20, key="unit.text.overflow"))
        self.assertEqual(len(overflow_lines()), before + 1)

    def test_check_fit_true_for_text_that_fits(self):
        self.assertTrue(check_fit(self.font, "ok", 200))
        self.assertTrue(check_fit(self.font, "wrapped words fit", 200, height=200))
        self.assertFalse(check_fit(self.font, "wrapped words fit", 200, height=1))


class ShippedTableTests(unittest.TestCase):
    """The widget strings live in the shipped table and keep their old text.

    The expected values are the literals the widgets drew before Phase 4 moved
    them into ``game/content/strings/en.json`` - i.e. what the golden frames
    were baked against. Changing one is a deliberate UI change.
    """

    def test_widget_strings(self):
        reset_strings()
        load_strings()
        self.assertEqual(T("hud.hp"), "HP")
        self.assertEqual(T("hud.hostiles", n=3), "HOSTILES: 3")
        self.assertEqual(T("hud.mags", n=2), "MAGS: 2")
        self.assertEqual(T("hud.reloading"), "RELOADING")
        self.assertEqual(T("hud.objective"), "OBJECTIVE: ")
        self.assertEqual(T("cutscene.space_to_continue"), "SPACE TO CONTINUE")
        self.assertEqual(T("cutscene.analyzing_file"), "ANALYZING FILE...")
        self.assertEqual(T("hud.hold_transmitter"), "HOLD THE TRANSMITTER")
        self.assertEqual(T("hud.hold_timer", s=42), "42s")
        self.assertEqual(T("hud.clock", m=1, s="05"), "1:05")
        self.assertEqual(T("hud.vis_shadow"), "HIDDEN - IN SHADOW")
        self.assertEqual(T("hud.minimap_north"), "N")
        self.assertEqual(missing_keys(), ())


class FormatShorthandTests(unittest.TestCase):
    """``"{02}"`` is a positional index, not zero padding (B-026).

    The string gate validates table *entries*, so it cannot see this class of
    call-site bug; this scan is the cheap guard. The smoke test's settings draw
    was the one gate that caught the real mistake.
    """

    def test_no_leading_zero_index_shorthand(self):
        root = Path(__file__).resolve().parents[2] / "src"
        bad = []
        for path in sorted(root.rglob("*.py")):
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"\{0\d", line):
                    rel = path.relative_to(root).as_posix()
                    bad.append(f"{rel}:{i}: {line.strip()[:90]}")
        self.assertEqual(bad, [], "use a ':{spec}' format spec instead: " + "; ".join(bad))


if __name__ == "__main__":
    unittest.main()
