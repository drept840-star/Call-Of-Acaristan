"""Phase 11 step 7 (ADR-023): baked cast shadows - occluded faces darken,
open faces do not, quality 0 disables the bake."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from game import render3d_bridge as bridge  # noqa: E402


def _scene():
    floor = {"kind": "quad_xz", "rect": [-4, -4, 4, 4], "y": 0.0,
             "color": (200, 200, 200), "seg": 0.8}
    crate = {"kind": "box", "size": [1, 1, 1], "center": [0, 0.5, 0],
             "color": (180, 180, 180)}
    lamp = {"kind": "point_light", "pos": [0, 3, 0],
            "color": (255, 255, 255), "intensity": 1.0, "range": 6.0,
            "cast_shadows": True}
    return [floor, crate, lamp]


class CastShadows(unittest.TestCase):
    def _bake(self, prims):
        pairs = [(p, bridge.build_mesh(p)) for p in prims
                 if p["kind"] in ("box", "quad_xz")]
        bridge.bake_cast_shadows(pairs, prims)
        return dict((id(p), m) for p, m in pairs)

    def test_floor_under_crate_darkened_open_floor_not(self):
        prims = _scene()
        meshes = self._bake(prims)
        floor = meshes[id(prims[0])]
        dark = bright = 0
        for idx, col in [(f[0], f[1]) for f in floor.faces]:
            cx = sum(floor.verts[i][0] for i in idx) / len(idx)
            cz = sum(floor.verts[i][2] for i in idx) / len(idx)
            if abs(cx) < 0.6 and abs(cz) < 0.6:
                if col[0] < 120:
                    dark += 1
            if cx > 2.5 and cz > 2.5 and col[0] > 150:
                bright += 1
        self.assertTrue(dark > 0, "floor faces under the crate must darken")
        self.assertTrue(bright > 0, "open floor faces must stay bright")

    def test_no_cast_flag_no_bake(self):
        prims = _scene()
        prims[2] = dict(prims[2])
        del prims[2]["cast_shadows"]
        before = [f[1] for f in bridge.build_mesh(prims[0]).faces]
        meshes = self._bake(prims)
        after = [f[1] for f in meshes[id(prims[0])].faces]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
