"""art_cache.get_plate_bg: the shared M4/M5 "status plate" chrome.

The M4 hold clock and the M5 status plate each built this surface inline
(pygame.Surface + fill + rim); both now share the cached factory. This test
locks the pixels to the legacy inline construction, so the plate look cannot
drift behind a golden shot that may only cover one of the two paths.
"""
import unittest

from tests.unit import _helpers  # noqa: F401  (sys.path + headless env)

import pygame

from entities import art_cache


def _legacy_plate(w, h):
    """The exact surface both missions built before the shared factory."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(surf, (8, 10, 14, 210), surf.get_rect(), border_radius=6)
    pygame.draw.rect(surf, (150, 170, 190, 220), surf.get_rect(), 1, border_radius=6)
    return surf


class PlateBgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((320, 200))   # dummy driver: exercises convert_alpha

    def test_matches_legacy_inline_build(self):
        for w, h in ((320, 46), (340, 46), (200, 30)):
            got = art_cache.get_plate_bg(w, h)
            ref = _legacy_plate(w, h)
            self.assertEqual(pygame.image.tobytes(got, "RGBA"),
                             pygame.image.tobytes(ref, "RGBA"),
                             f"plate {w}x{h} drifted from the legacy build")

    def test_cached(self):
        self.assertIs(art_cache.get_plate_bg(320, 46), art_cache.get_plate_bg(320, 46))


if __name__ == "__main__":
    unittest.main()
