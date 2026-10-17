"""Phase 11 step 11 (ADR-024): the importer converts OBJ/glTF into
ae.mesh/1 with palette snapping + triangle budget; the bridge loads
and instantiates mesh prims."""
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import render3d_bridge as bridge  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
IMPORTER = os.path.join(ROOT, "tools", "ae_import_mesh.py")

_CUBE_OBJ = """v -0.5 0 -0.5
v 0.5 0 -0.5
v 0.5 0 0.5
v -0.5 0 0.5
v -0.5 1 -0.5
v 0.5 1 -0.5
v 0.5 1 0.5
v -0.5 1 0.5
usemtl wood
f 1 2 3 4
f 5 8 7 6
f 1 5 6 2
f 2 6 7 3
f 3 7 8 4
f 4 8 5 1
"""


def _run_import(src_text, suffix, *extra):
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in" + suffix)
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(src_text)
        out = subprocess.run(
            [sys.executable, IMPORTER, src, "test_cube",
             "--budget", "100"] + list(extra),
            capture_output=True, text=True, cwd=td,
            env={**os.environ, "PYTHONPATH": ""})
        asset = os.path.join(ROOT, "src", "game", "content", "meshes",
                             "test_cube.mesh.json")
        data = None
        if os.path.exists(asset):
            with open(asset, encoding="utf-8") as fh:
                data = json.load(fh)
            os.unlink(asset)
        return out, data


class MeshImport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((64, 64))

    def test_obj_import_snaps_and_budgets(self):
        out, data = _run_import(_CUBE_OBJ, ".obj")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(data["schema"], "ae.mesh/1")
        self.assertEqual(data["tris"], 12)
        self.assertEqual(len(data["verts"]), 8)
        # grounded: min y == 0 after import
        self.assertAlmostEqual(min(v[1] for v in data["verts"]), 0.0)

    def test_budget_enforced(self):
        out, _data = _run_import(_CUBE_OBJ, ".obj", "--budget", "4")
        self.assertEqual(out.returncode, 1)
        self.assertIn("budget", out.stdout)

    def test_bridge_instantiates_barrel(self):
        mesh = bridge.mesh_for_prim({"kind": "mesh", "ref": "barrel",
                                     "pos": [1, 0, 2], "yaw": 30,
                                     "scale": 2.0})
        self.assertEqual(len(mesh.faces), 140)
        ys = [v[1] for v in mesh.verts]
        self.assertAlmostEqual(min(ys), 0.0, places=4)
        self.assertAlmostEqual(max(ys), 1.8, places=3)

    def test_gltf_import(self):
        # minimal GLB: one triangle, no material
        pos = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        idx = [0, 1, 2]
        binbuf = struct.pack("<9f", *pos) + struct.pack("<3H", *idx)
        binbuf += b"\x00" * (len(binbuf) % 4)
        gltf = {"asset": {"version": "2.0"},
                "buffers": [{"byteLength": len(binbuf)}],
                "bufferViews": [
                    {"buffer": 0, "byteOffset": 0, "byteLength": 36},
                    {"buffer": 0, "byteOffset": 36, "byteLength": 6}],
                "accessors": [
                    {"bufferView": 0, "componentType": 5126,
                     "count": 3, "type": "VEC3"},
                    {"bufferView": 1, "componentType": 5123,
                     "count": 3, "type": "SCALAR"}],
                "meshes": [{"primitives": [
                    {"attributes": {"POSITION": 0}, "indices": 1}]}]}
        js = json.dumps(gltf).encode()
        js += b" " * (len(js) % 4)
        glb = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js)
                          + 8 + len(binbuf))
        glb += struct.pack("<II", len(js), 0x4E4F534A) + js
        glb += struct.pack("<II", len(binbuf), 0x004E4942) + binbuf
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "tri.glb")
            with open(src, "wb") as fh:
                fh.write(glb)
            out = subprocess.run(
                [sys.executable, IMPORTER, src, "test_tri"],
                capture_output=True, text=True, cwd=td)
            asset = os.path.join(ROOT, "src", "game", "content",
                                 "meshes", "test_tri.mesh.json")
            try:
                self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
                with open(asset, encoding="utf-8") as fh:
                    data = json.load(fh)
                self.assertEqual(data["tris"], 1)
            finally:
                if os.path.exists(asset):
                    os.unlink(asset)


if __name__ == "__main__":
    unittest.main()
