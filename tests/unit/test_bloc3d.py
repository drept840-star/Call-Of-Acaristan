"""Phase 5: the Bloc landmarks and Cyrillic signage build sane boxes.

The font is the contract every sign depends on, so its shapes and layout are
checked first; the builders are then checked on what the set relies on: the
counts they report match the meshes they added, the facing axis is respected,
and the lamp positions they hand back are on (or above) their own geometry.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from engine3d.core import Mesh  # noqa: E402
from missions.m6 import bloc3d as B  # noqa: E402
from missions.m6.bloc3d import font, signs, stacks, tower  # noqa: E402

ALPHABET = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
FACINGS = ("+z", "-z", "+x", "-x")
AXIS = {"+z": 2, "-z": 2, "+x": 0, "-x": 0}


def _mesh():
    """A Mesh plus a counting ``add``; boxes subdivide, so count calls, not faces."""
    m = Mesh()
    calls = []

    def add(mesh):
        calls.append(mesh)
        return m.add(mesh)

    return m, add, calls


class Font(unittest.TestCase):
    def test_glyphs_are_7x5_cells(self):
        for ch, rows in B.GLYPHS.items():
            self.assertEqual(len(rows), B.GLYPH_H, ch)
            for row in rows:
                self.assertEqual(len(row), B.GLYPH_W, (ch, row))
                self.assertTrue(set(row) <= {"#", "."}, (ch, row))

    def test_alphabet_and_digits_covered(self):
        for ch in ALPHABET:
            self.assertIn(ch, B.GLYPHS)
        for d in "0123456789":
            self.assertIn(d, B.GLYPHS)

    def test_width(self):
        self.assertEqual(B.width("АБ"), 11)
        self.assertEqual(B.width(""), 0)
        self.assertEqual(B.width("А"), 5)
        self.assertEqual(B.width("АБВ"), 17)

    def test_layout_runs_stay_in_glyph_cells(self):
        runs = B.layout("АБ")
        self.assertTrue(runs)
        for i, (col, row, length) in enumerate(runs):
            self.assertTrue(0 <= row < B.GLYPH_H)
            self.assertGreaterEqual(length, 1)
            if i < len(runs) // 2 or col < 5:
                self.assertLessEqual(col + length, 5, "run crosses the А cell")
            else:
                self.assertGreaterEqual(col, 6, "run starts before the Б cell")
                self.assertLessEqual(col + length, 11, "run crosses the Б cell")


class Letters(unittest.TestCase):
    def test_returns_run_count_and_adds_meshes(self):
        n_runs = len(B.layout("АБ"))
        for facing in FACINGS:
            m, add, calls = _mesh()
            n = B.letters(add, "АБ", (10.0, 5.0, -3.0), facing)
            self.assertEqual(n, n_runs, facing)
            self.assertTrue(m.faces)
            self.assertEqual(len(calls), n, facing)

    def test_boxes_are_thin_along_the_facing_axis(self):
        axis = None
        for facing in FACINGS:
            axis = AXIS[facing]
            m, add, calls = _mesh()
            B.letters(add, "АБ", (10.0, 5.0, -3.0), facing, depth=0.04)
            whole = [v[axis] for v in m.verts]
            self.assertLessEqual(max(whole) - min(whole), 0.05, facing)
            for idx, *_ in m.faces:
                vs = [m.verts[i][axis] for i in idx]
                self.assertLessEqual(max(vs) - min(vs), 0.05, facing)


class Board(unittest.TestCase):
    def test_board_positive_sizes(self):
        for facing in FACINGS:
            m, add, calls = _mesh()
            bw, bh = B.board(add, "БЛОК", (0.0, 4.0, 0.0), facing)
            self.assertGreater(bw, 0)
            self.assertGreater(bh, 0)
            self.assertTrue(m.faces)


class Billboard(unittest.TestCase):
    def test_returns_two_lamps(self):
        m, add, calls = _mesh()
        lamps = B.billboard(add, ("СЛАВА", "ТРУДУ"), (3.0, 8.0), "-x")
        self.assertEqual(len(lamps), 2)
        for p in lamps:
            self.assertEqual(len(p), 3)
            self.assertTrue(all(isinstance(c, float) for c in p))
        self.assertTrue(m.faces)


class PanelBlock(unittest.TestCase):
    def _verts(self, **kw):
        m, add, calls = _mesh()
        n = B.panel_block(add, 2.0, 3.0, 12.0, 15.0, 9.0, "+z", seed=4, **kw)
        return n, m

    def test_returns_count_added(self):
        for facing in FACINGS:
            m, add, calls = _mesh()
            n = B.panel_block(add, 0.0, 0.0, 12.0, 15.0, 9.0, facing, seed=1)
            self.assertGreater(n, 0)
            self.assertEqual(len(calls), n, facing)

    def test_deterministic(self):
        _n1, m1 = self._verts()
        _n2, m2 = self._verts()
        self.assertEqual(m1.verts, m2.verts)
        self.assertEqual(m1.faces, m2.faces)

    def test_budget_caps_windows(self):
        n_free, m_free = self._verts(budget=None)
        n_zero, m_zero = self._verts(budget=0)
        self.assertLess(n_zero, n_free)
        self.assertLess(len(m_zero.faces), len(m_free.faces))


class Stacks(unittest.TestCase):
    def test_smokestack_lamps(self):
        m, add, calls = _mesh()
        for h in (10.0, 40.0, 120.0):
            lamps = stacks.smokestack(add, 5.0, -2.0, h)
            self.assertTrue(lamps)
            for x, y, z in lamps:
                self.assertGreater(y, 0.0)
                self.assertLessEqual(y, h + 4.0)
        self.assertTrue(m.faces)

    def test_radio_mast_lamps(self):
        m, add, calls = _mesh()
        for h in (8.0, 30.0, 90.0):
            lamps = stacks.radio_mast(add, 0.0, 0.0, h)
            self.assertTrue(lamps)
            for x, y, z in lamps:
                self.assertGreater(y, 0.0)
                self.assertLessEqual(y, h + 4.0)
        self.assertTrue(m.faces)


class Tower(unittest.TestCase):
    def test_watchtower_lens_above_cabin(self):
        m, add, calls = _mesh()
        for facing in FACINGS:
            lens, f = tower.watchtower(add, 1.0, 1.0, h=6.5, facing=facing)
            self.assertEqual(f, facing)
            self.assertGreater(lens[1], 6.5)

    def test_fence_run_returns_count(self):
        for x0, z0, x1, z1 in ((0.0, 0.0, 12.0, 0.0), (4.0, 0.0, 4.0, 9.0)):
            m, add, calls = _mesh()
            n = tower.fence_run(add, x0, z0, x1, z1)
            self.assertGreater(n, 0)
            self.assertEqual(len(calls), n)


if __name__ == "__main__":
    unittest.main()
