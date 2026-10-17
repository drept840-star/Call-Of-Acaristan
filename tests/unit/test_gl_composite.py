"""GL renderer item-queue regression (owner-hardware crash, M5 finale).

``SoftwareRenderer.add_blob_shadow`` queues a ``(key, callable, args)``
item; the GL backend's ``_composite`` reads ``(key, kind, data)`` items
and treated the callable as a line, unpacking a float as screen points
(``TypeError: 'float' object is not subscriptable``) on the first
humanoid rendered with a GPU. Sandbox has no GL context, so these tests
drive the queue/composite layer of a context-free ``GLRenderer``
(``SoftwareRenderer.__init__`` supplies camera/cache state; moderngl is
only touched by ``_render``, never here).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np  # noqa: E402
import pygame  # noqa: E402

from engine3d.core import SoftwareRenderer  # noqa: E402
from engine3d.gl import GLRenderer  # noqa: E402


def _gl_renderer():
    r = object.__new__(GLRenderer)
    SoftwareRenderer.__init__(r, 120, 90, fog=(26, 38, 44),
                              fog_start=32.0, fog_end=100.0)
    r.set_camera((0.0, 1.6, 0.0), (0.0, 1.2, 8.0), 55)
    r.begin()
    return r


class GLBlobShadowItem(unittest.TestCase):
    def test_blob_shadow_queues_a_sprite_item(self):
        r = _gl_renderer()
        r.add_blob_shadow((0.0, 0.0, 6.0), 0.34, 0.30, 0.40)
        self.assertEqual(len(r._items), 1)
        _key, kind, data = r._items[0]
        self.assertEqual(kind, "sprite")
        self.assertEqual(len(data), 7)          # fn, sx, sy, scale, z, layer, zeff
        self.assertTrue(callable(data[0]))

    def test_blob_shadow_behind_camera_queues_nothing(self):
        r = _gl_renderer()
        r.add_blob_shadow((0.0, 0.0, -6.0), 0.34, 0.30, 0.40)
        self.assertEqual(r._items, [])

    def test_software_blob_item_format_unchanged(self):
        # Parity: the software backend keeps its callable item format.
        r = SoftwareRenderer(120, 90)
        r.set_camera((0.0, 1.6, 0.0), (0.0, 1.2, 8.0), 55)
        r.add_blob_shadow((0.0, 0.0, 6.0), 0.34, 0.30, 0.40)
        self.assertEqual(len(r._items), 1)
        _key, fn, data = r._items[0]
        self.assertTrue(callable(fn))
        self.assertEqual(len(data), 4)          # sx, sy, scale, z


class GLComposite(unittest.TestCase):
    def _depth(self, r, value=1.0):
        return np.full((r.h, r.w), value, dtype=np.float32)

    def test_composite_blob_line_and_sprite_items(self):
        pygame.init()
        r = _gl_renderer()
        r.add_blob_shadow((0.0, 0.0, 6.0), 0.34, 0.30, 0.40)
        r.add_line3d((0.0, 0.2, 6.0), (0.5, 1.4, 6.0), (255, 0, 0), 1)
        r.add_sprite((0.0, 1.0, 6.0),
                     lambda s, sx, sy, sc, z: pygame.draw.circle(
                         s, (0, 255, 0), (int(sx), int(sy)), 3))
        surf = pygame.Surface((r.w, r.h))
        surf.fill((200, 200, 200))
        blob = next(d for _k, kind, d in r._items if kind == "sprite"
                    and len(d) == 7)
        cx, cy = int(blob[1]), int(blob[2])
        centre_before = surf.get_at((cx, cy))[:3]
        r._composite(surf, list(r._items), self._depth(r), False)
        centre_after = surf.get_at((cx, cy))[:3]
        # The blob darkened the floor at its projected centre; the line drew red.
        self.assertLess(sum(centre_after), sum(centre_before))
        px = pygame.surfarray.array3d(surf)
        self.assertTrue((px[:, :, 0] > 200).any() and (px[:, :, 1] < 80).any())

    def test_composite_survives_a_legacy_callable_item(self):
        # The exact item shape that crashed the owner's build: it must
        # draw (software semantics), never raise.
        pygame.init()
        r = _gl_renderer()
        hit = []

        def draw_fn(s, sx, sy, scale, z):
            hit.append((sx, sy))
            pygame.draw.circle(s, (255, 0, 0), (int(sx), int(sy)), 3)

        r._items.append((0.5, draw_fn, (60.0, 45.0, 10.0, 5.0)))
        surf = pygame.Surface((r.w, r.h))
        r._composite(surf, list(r._items), self._depth(r), False)
        self.assertEqual(hit, [(60.0, 45.0)])
        self.assertEqual(surf.get_at((60, 45))[:3], (255, 0, 0))

    def test_composite_skips_a_degenerate_line(self):
        pygame.init()
        r = _gl_renderer()
        r._items.append((1.0, "line", ((255, 255, 255), 1, [(10, 10)], 3)))
        surf = pygame.Surface((r.w, r.h))
        r._composite(surf, list(r._items), self._depth(r), False)  # no raise


if __name__ == "__main__":
    unittest.main()
