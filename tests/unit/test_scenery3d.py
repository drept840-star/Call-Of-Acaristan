"""Imported scenery budgets, grounded placement, live displays and fallbacks."""
import json
import math
import sys
import unittest
from unittest.mock import patch

from tests.unit import _helpers
from game import scenery3d as S


class SceneryTests(unittest.TestCase):
    def tearDown(self):
        S.prop.cache_clear()
        S.display.cache_clear()
        S.workstation.cache_clear()
        S.workstation_display.cache_clear()

    def test_baked_assets_are_deterministic_grounded_and_budgeted(self):
        sys.path.insert(0, str(_helpers.ROOT / "tools"))
        import ae_import_workstation_props as importer
        for asset in importer.ASSETS:
            ref, _, height, _, budget = asset
            path = _helpers.SRC / "game/content/meshes" / (ref + ".mesh.json")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data, importer.build(asset), ref)
            self.assertLessEqual(data["tris"], budget)
            self.assertEqual(min(v[1] for v in data["verts"]), 0)
            self.assertAlmostEqual(max(v[1] for v in data["verts"]), height, delta=0.015)
            self.assertTrue(all(math.isfinite(c) for v in data["verts"] for c in v))
            self.assertTrue(all(0 <= i < len(data["verts"]) for f in data["faces"] for i in f[0]))

    def test_live_screen_matches_shell_and_does_not_mutate_it(self):
        for pc, monitor in (("pc_zarya", "monitor_crt"), ("pc_tall", "monitor_crt"), ("pc_tall", "monitor_lcd")):
            shell = S.workstation(pc, monitor, True)
            before = list(shell.faces)
            live = S.workstation_display(pc, monitor, (90, 230, 150))
            self.assertTrue(live.faces)
            self.assertTrue(all(f[4] for f in live.faces))
            self.assertFalse(any(f[4] for f in shell.faces))
            self.assertEqual(before, shell.faces)
            # Live pixels are just outside the same screen, not a detached card.
            for f in live.faces:
                for i in f[0]:
                    x, y, z = live.verts[i]
                    self.assertTrue(any(abs(x-a) < 1e-6 and abs(y-b) < 1e-6 and abs(z-c-0.001) < 1e-6
                                        for a, b, c in shell.verts))

    def test_missing_assets_retain_fallbacks(self):
        from missions.m1 import draw3d as m1
        from missions.m2 import draw3d as m2
        with patch("game.render3d_bridge.load_mesh_asset", side_effect=OSError("missing")):
            self.assertIsNone(S.workstation())
            self.assertGreater(len(S.medical_supplies().faces), 10)
            self.assertGreater(len(m1._pickup_mesh("bandage").faces), 0)
            self.assertGreater(len(m2._upload_pc_mesh().faces), 0)
        S.prop.cache_clear()
        S.workstation.cache_clear()
        from game.render3d_bridge import load_mesh_asset
        def missing_cpu(ref):
            if ref == "pc_tall":
                raise OSError("missing tower")
            return load_mesh_asset(ref)
        with patch("game.render3d_bridge.load_mesh_asset", side_effect=missing_cpu):
            self.assertIsNone(S.workstation_display("pc_tall", "monitor_lcd", (80, 160, 120)))

    def test_m2_and_shared_health_pickups_use_imports(self):
        from missions.m1 import draw3d as m1
        from missions.m2 import draw3d as m2
        self.assertIs(m1._pickup_mesh("bandage"), S.prop("medkit"))
        self.assertGreater(len(m2._upload_pc_mesh().faces), 1700)
        self.assertGreater(len(m2._ev_mesh("terminal").faces), 1600)

    def test_m3_static_and_live_desk_paths(self):
        from missions.m3 import wings3d as W
        from missions.m3 import draw3d as D
        for key, kind, pc, monitor in (("comms", "tuning_desk", "pc_tall", "monitor_crt"),
                                       ("archives", "maru_desk", "pc_zarya", "monitor_crt"),
                                       ("broadcast", "pc_desk", "pc_tall", "monitor_lcd")):
            meshes, live = [], []
            p = next(p for p in W.PROPS[key] if p[0] == kind)
            with patch.object(W, "_add", side_effect=lambda r, m: meshes.append(m)):
                W._piece(None, *p)
            self.assertGreater(sum(len(m.faces) for m in meshes), 1600)
            with patch.object(D, "_put", side_effect=lambda r, mesh, pos, **kw: live.append((mesh, pos, kw))):
                self.assertTrue(W._live_screen(None, kind, pc, monitor, (90, 230, 150)))
            self.assertEqual(live[0][2]["yaw"], 180)

    def test_m5_hq_and_m7_house_build_with_assets(self):
        from missions.m5 import draw3d as m5
        from cutscenes import m7world3d as m7
        with patch.object(m5, "_put") as put, patch.object(m5, "_box_at"), patch.object(m5, "_decal"), \
                patch.object(m5, "_on_wall"), patch.object(m5, "_portrait3d"), patch.object(m5, "_flag3d"), \
                patch.object(m5, "_banner3d"):
            m5._hq_dress(None)
            self.assertGreaterEqual(put.call_count, 3)
        self.assertGreater(len(m7.house().faces), len(m7.house(burn=True).faces) + 800)


if __name__ == "__main__":
    unittest.main()
