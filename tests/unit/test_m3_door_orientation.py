"""M3's visual door panels follow the wall, including every double leaf."""
import unittest
from unittest.mock import patch

from tests.unit import _helpers  # noqa: F401
from missions.m3 import draw3d, maps


class M3DoorOrientationTests(unittest.TestCase):
    def door_tiles(self, grid):
        with patch.object(maps, "MISSION3_MAP", grid), \
                patch.dict(draw3d._cache, {"doors": None}):
            return draw3d._door_tiles()

    def test_all_five_maps_match_authored_wall_axes(self):
        # All other doors span east-west. The armory's two adjacent D tiles
        # cross two wall columns: they must both stay north-south panels.
        vertical = {
            "CELL": {(35, 21), (36, 21), (6, 22)},
            "COMMS": {(34, 23), (34, 24), (10, 24), (10, 25), (44, 24)},
            "ARCHIVES": {(36, 8), (36, 9), (20, 24), (20, 25), (28, 24), (28, 25)},
            "KILL_ORDER": {(8, 12), (8, 13), (13, 12), (29, 16), (29, 17),
                           (8, 20), (8, 21), (13, 20)},
            "BROADCAST": {(11, 8), (20, 8), (23, 23), (8, 26)},
        }
        for wing, expected in vertical.items():
            with self.subTest(wing=wing):
                tiles = self.door_tiles(getattr(maps, "MISSION3_" + wing + "_MAP"))
                self.assertEqual({(c, r) for c, r, along_x, _ in tiles if not along_x}, expected)

    def test_vertical_leaves_share_axis_and_slide_toward_opposite_jambs(self):
        grid = ["CCCCC", "..C..", "..D..", "..D..", "..C..", "CCCCC"]
        self.assertEqual(self.door_tiles(grid), [(2, 2, False, -1), (2, 3, False, 1)])

    def test_horizontal_leaves_share_axis_and_slide_toward_opposite_jambs(self):
        grid = ["CCCCCC", "......", ".CDDC.", "......", "CCCCCC"]
        self.assertEqual(self.door_tiles(grid), [(2, 2, True, -1), (3, 2, True, 1)])

    def test_cached_tiles_follow_map_rebinding(self):
        with patch.dict(draw3d._cache, {"doors": None}):
            with patch.object(maps, "MISSION3_MAP", maps.MISSION3_COMMS_MAP):
                comms = draw3d._door_tiles()
                self.assertIs(draw3d._door_tiles(), comms)
            with patch.object(maps, "MISSION3_MAP", maps.MISSION3_ARCHIVES_MAP):
                self.assertIsNot(draw3d._door_tiles(), comms)


if __name__ == "__main__":
    unittest.main()
