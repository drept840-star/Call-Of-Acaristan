"""Phase 11 step 9: palette textures load through the bridge, UV
payloads attach at quality >= 1 only, and pass through dynamic_faces."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from core.user_settings import SETTINGS  # noqa: E402
from game import render3d_bridge as bridge  # noqa: E402


class Textures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((64, 64))

    def setUp(self):
        self._q = SETTINGS.quality_3d

    def tearDown(self):
        SETTINGS.quality_3d = self._q

    def test_load_texture_shape_and_palette(self):
        arr = bridge.load_texture("wood_crate")
        self.assertEqual(arr.shape, (16, 16, 3))
        self.assertEqual(arr.dtype.name, "uint8")
        with self.assertRaises((ValueError, FileNotFoundError)):
            bridge.load_texture("no_such_texture")

    def test_uv_payload_quality_gated(self):
        prim = {"kind": "quad_xz", "rect": [0, 0, 2, 2], "y": 0.0,
                "color": (104, 102, 98), "texture": "concrete",
                "tex_scale": 1.4}
        SETTINGS.quality_3d = 2
        mesh = bridge.build_mesh(prim)
        self.assertTrue(all(len(f) == 6 for f in mesh.faces))
        faces = bridge.dynamic_faces(mesh)
        self.assertTrue(all(len(f) == 8 and f[7][0] == "concrete"
                            for f in faces))
        SETTINGS.quality_3d = 0
        flat = bridge.build_mesh(prim)
        self.assertTrue(all(len(f) == 5 for f in flat.faces))

    def test_textured_face_renders_nearest(self):
        from engine3d import Renderer
        r = Renderer(120, 90)
        buf = pygame.Surface((120, 90))
        buf.fill((0, 0, 0))
        r.set_camera((0, 1.2, -2.2), (0, 0.4, 0), 55)
        prim = {"kind": "box", "size": [1.2, 1.2, 1.2],
                "center": [0, 0.6, 0], "color": (146, 110, 66),
                "texture": "wood_crate", "tex_scale": 0.9}
        SETTINGS.quality_3d = 2
        bridge.push_textures(r, [prim])
        mesh = bridge.build_mesh(prim)
        r.begin()
        r.add_dynamic(mesh.verts, bridge.dynamic_faces(mesh))
        r.flush(buf)
        colours = set()
        for x in range(20, 100, 7):
            for y in range(15, 75, 7):
                colours.add(buf.get_at((x, y))[:3])
        self.assertTrue(len(colours) > 4,
                        f"textured box should show palette variety, got {colours}")


if __name__ == "__main__":
    unittest.main()
