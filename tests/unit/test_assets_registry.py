"""engine.assets Phase 3: manifest schema, registry chain + cache + ref-counts, bake/check
hashing, lint, hot reload (watcher + AssetReloaded), loaders, pose cache, D5 guard and the
art.m5 -> game.art.m5 shim (A-008). Headless: plain Surfaces, no display."""
import io
import json
import os
import re
import shutil
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pygame  # noqa: E402

from engine.assets import (AssetRegistry, AssetReloaded, AssetWatcher, PLACEHOLDER, bake_pack,  # noqa: E402
                           check_pack, contact_sheet, lint_pack, load_image, load_manifest, load_sound,
                           source_hash)
from engine.assets.manifest import parse_manifest  # noqa: E402
from engine.core import AssetError, EventBus, SchemaError  # noqa: E402

ART_SRC = '''
import pygame
VARIANTS = 2
VARIANT_NAMES = ("plain", "lit")
COLOR = (%d, 40, 200, 255)
def render(variant=0, scale=1):
    s = pygame.Surface((8 * scale, 6 * scale), pygame.SRCALPHA)
    s.fill(COLOR if variant == 0 else (255, 255, 0, 255))
    return s
'''

BROKEN_SRC = '''
VARIANTS = 1
def render(variant=0, scale=1):
    raise RuntimeError("no art today")
'''


class _Pack(unittest.TestCase):
    """A throwaway pack 'tp' in a temp dir: art module tp_art.spr + a manifest."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ae_assets_"))
        self.pkg = self.tmp / "tp_art"
        self.pkg.mkdir()
        (self.pkg / "__init__.py").write_text("", encoding="utf-8")
        self.mod_path = self.pkg / "spr.py"
        self.mod_path.write_text(ART_SRC % 10, encoding="utf-8")
        (self.pkg / "broken.py").write_text(BROKEN_SRC, encoding="utf-8")
        sys.path.insert(0, str(self.tmp))
        self.manifest = self.tmp / "manifest.json"
        self.manifest.write_text(json.dumps({
            "schema": "ae.manifest/1", "pack": "tp", "baked_dir": "assets/baked/tp",
            "assets": [
                {"id": "tp/spr", "kind": "sprite_def", "module": "tp_art.spr", "variants": 2, "size": [8, 6]},
                {"id": "tp/broken", "kind": "sprite_def", "module": "tp_art.broken", "fallback": "tp/spr", "size": [4, 4]},
                {"id": "tp/orphan", "kind": "sprite_def", "module": "tp_art.broken", "size": [16, 8]},
                {"id": "tp/photo", "kind": "image", "path": "assets/photo.png"},
            ]}), encoding="utf-8")
        self.reg = AssetRegistry(str(self.tmp), dev=True)
        self.reg.load_pack(str(self.manifest))

    def tearDown(self):
        sys.path.remove(str(self.tmp))
        for k in [k for k in sys.modules if k == "tp_art" or k.startswith("tp_art.")]:
            del sys.modules[k]
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestManifest(unittest.TestCase):
    def test_schema_errors(self):
        bad = [
            ({"schema": "nope", "pack": "p", "assets": []}, "schema"),
            ({"schema": "ae.manifest/1", "pack": "", "assets": []}, "pack"),
            ({"schema": "ae.manifest/1", "pack": "p", "assets": [{"id": "q/x", "kind": "image", "path": "a"}]}, "id"),
            ({"schema": "ae.manifest/1", "pack": "p", "assets": [{"id": "p/x", "kind": "blob", "path": "a"}]}, "kind"),
            ({"schema": "ae.manifest/1", "pack": "p", "assets": [{"id": "p/x", "kind": "sprite_def"}]}, "module"),
            ({"schema": "ae.manifest/1", "pack": "p", "assets": [{"id": "p/x", "kind": "sound"}]}, "path"),
            ({"schema": "ae.manifest/1", "pack": "p", "assets": [{"id": "p/x", "kind": "image", "path": "a"},
                                                                  {"id": "p/x", "kind": "image", "path": "b"}]}, "duplicate"),
            ({"schema": "ae.manifest/1", "pack": "p", "assets": [{"id": "p/x", "kind": "image", "path": "a",
                                                                   "fallback": "p/none"}]}, "fallback"),
        ]
        for doc, word in bad:
            with self.assertRaises(SchemaError, msg=word) as cm:
                parse_manifest(doc)
            self.assertIn(word, str(cm.exception).lower())

    def test_defaults_and_baked_pattern(self):
        m = parse_manifest({"schema": "ae.manifest/1", "pack": "p", "baked_dir": "b/p",
                            "assets": [{"id": "p/x", "kind": "sprite_def", "module": "m", "tags": ["lit"]}]})
        a = m.assets["p/x"]
        self.assertEqual((a.name, a.variants, a.tags, a.rendered), ("x", 1, ("lit",), True))
        self.assertEqual(a.baked_file(3), "b/p/x_3.png")
        self.assertEqual(len(m), 1)

    def test_m5_manifest_loads_and_matches_pack(self):
        m = load_manifest(ROOT / "src" / "game" / "content" / "m5" / "manifest.json")
        from game.art import m5 as owner
        self.assertEqual(sorted(a.name for a in m), sorted(owner.ASSETS))
        self.assertEqual(sum(a.variants for a in m), 125)
        self.assertEqual(m.assets["m5/inspect_art"].kind, "layer")
        self.assertEqual(sorted(a.name for a in m if "decal" in a.tags), sorted(owner.DECALS))


class TestRegistry(_Pack):
    def test_render_chain_cache_and_invalidate(self):
        s = self.reg.get("tp/spr", 0)
        self.assertEqual((s.get_size(), s.get_at((0, 0))), ((8, 6), (10, 40, 200, 255)))
        self.assertIs(self.reg.get("tp/spr", 0), s)
        self.assertEqual((self.reg.stats["rendered"], self.reg.stats["hits"], self.reg.stats["baked"]), (1, 1, 0))
        self.assertEqual(self.reg.get("tp/spr", 1, 2).get_size(), (16, 12))
        self.assertEqual(self.reg.invalidate("tp/spr"), 2)
        self.assertIsNot(self.reg.get("tp/spr", 0), s)

    def test_variant_names(self):
        self.assertIs(self.reg.get("tp/spr", "lit"), self.reg.get("tp/spr", 1))
        self.assertIs(self.reg.get("tp/spr:lit"), self.reg.get("tp/spr", 1))
        with self.assertRaises(AssetError):
            self.reg.get("tp/spr", "nope")

    def test_fallback_placeholder_default_none(self):
        fb = self.reg.get("tp/broken")
        self.assertIs(fb, self.reg.get("tp/spr", 0))
        self.assertEqual(self.reg.stats["fallback"], 1)
        ph = self.reg.get("tp/orphan")
        self.assertEqual(ph.get_size(), (16, 8))
        self.assertEqual(ph.get_at((0, 0)), (255, 0, 255, 255))      # dev: magenta checker
        self.assertEqual(ph.get_at((8, 0)), (20, 20, 20, 255))
        self.assertEqual(self.reg.stats["placeholder"], 1)
        self.assertIsNone(self.reg.get("tp/orphan", 0, 2, default=None))
        rel = AssetRegistry(str(self.tmp), dev=False)
        rel.load_pack(str(self.manifest))
        t = rel.get("tp/orphan")
        self.assertEqual((t.get_size(), t.get_at((0, 0))[3]), ((16, 8), 0))  # release: transparent
        with self.assertRaises(AssetError):
            self.reg.get("tp/missing")
        self.assertIsNone(self.reg.get("tp/photo", default=None))        # image file absent -> None

    def test_image_kind_loads_file(self):
        p = self.tmp / "assets" / "photo.png"
        p.parent.mkdir(parents=True)
        s = pygame.Surface((3, 2), pygame.SRCALPHA)
        s.fill((1, 2, 3, 255))
        pygame.image.save(s, str(p))
        got = self.reg.get("tp/photo")
        self.assertEqual((got.get_size(), got.get_at((0, 0))), ((3, 2), (1, 2, 3, 255)))
        self.assertEqual(self.reg.get("tp/photo", 0, 2).get_size(), (6, 4))

    def test_refcounts_and_unload(self):
        a, b = object(), object()
        self.reg.acquire("tp", a)
        self.reg.acquire("tp", b)
        self.assertEqual(self.reg.holders("tp"), 2)
        self.assertFalse(self.reg.unload_pack("tp"))
        self.assertEqual(self.reg.release(a), [])
        self.assertEqual(self.reg.release(b), ["tp"])
        self.reg.get("tp/spr")
        self.assertTrue(self.reg.unload_pack("tp"))
        self.assertEqual((self.reg.cache_size(), self.reg.ids()), (0, []))
        with self.assertRaises(AssetError):
            self.reg.acquire("tp", a)

    def test_ids_and_watched_files(self):
        self.assertEqual(self.reg.ids("tp", "sprite_def"), ["tp/broken", "tp/orphan", "tp/spr"])
        files = self.reg.watched_files()
        self.assertTrue(any(f.endswith("spr.py") for f in files["tp/spr"]))
        self.assertTrue(any(f.endswith("spr_1.png") for f in files["tp/spr"]))


class TestBake(_Pack):
    def test_bake_check_stale_and_rebake(self):
        rep = bake_pack(self.reg.packs["tp"], str(self.tmp), verbose=None)
        self.assertEqual(rep.baked, 2)                      # tp/spr x2; broken/orphan raise -> errors
        self.assertEqual(len(rep.errors), 2)
        self.assertTrue((self.tmp / "assets/baked/tp/spr_1.png").exists())
        info = json.loads((self.tmp / "assets/baked/tp/.bakeinfo.json").read_text())
        self.assertEqual((info["schema"], info["pack"], sorted(info["entries"])), ("ae.bakeinfo/1", "tp", ["tp/spr"]))
        h1, deps = source_hash(self.reg.define("tp/spr"), str(self.tmp))
        self.assertEqual((info["entries"]["tp/spr"]["source"], deps), (h1, ["tp_art.spr"]))
        # a second bake is byte-identical (determinism)
        png1 = (self.tmp / "assets/baked/tp/spr_0.png").read_bytes()
        bake_pack(self.reg.packs["tp"], str(self.tmp), only={"tp/spr"}, verbose=None)
        self.assertEqual(png1, (self.tmp / "assets/baked/tp/spr_0.png").read_bytes())
        # fresh registry prefers the baked file and matches the live render pixel for pixel
        reg2 = AssetRegistry(str(self.tmp))
        reg2.load_pack(str(self.manifest))
        got = reg2.get("tp/spr", 1)
        self.assertEqual(reg2.stats["baked"], 1)
        self.assertEqual(pygame.image.tobytes(got, "RGBA"), pygame.image.tobytes(reg2.module("tp/spr").render(1, 1), "RGBA"))
        self.assertEqual(reg2.get("tp/spr", 1, 3).get_size(), (24, 18))
        self.assertEqual(reg2.get("tp/spr", 0, baked=False).get_at((0, 0)), (10, 40, 200, 255))  # live path
        # check: unbakeable assets count as missing; on the bakeable subset it is clean now,
        # stale after the source changes, mismatched once the new source is live, clean after a rebake
        full = check_pack(self.reg.packs["tp"], str(self.tmp), sample_every=1)
        self.assertEqual((full.ok, full.checked, len(full.missing)), (False, 3, 2))
        m = self.reg.packs["tp"]
        m.assets = {k: v for k, v in m.assets.items() if k == "tp/spr"}
        chk = check_pack(m, str(self.tmp), sample_every=1)
        self.assertTrue(chk.ok, chk.summary())
        self.assertEqual((chk.checked, chk.sampled), (1, 2))
        self.mod_path.write_text(ART_SRC % 99, encoding="utf-8")
        chk2 = check_pack(m, str(self.tmp), sample_every=1)
        self.assertFalse(chk2.ok)
        self.assertTrue(any("source hash changed" in s for s in chk2.stale), chk2.stale)
        self.reg.reload("tp/spr")                                  # source re-exec (pyc stamp-proof)
        chk3 = check_pack(m, str(self.tmp), sample_every=1)
        self.assertTrue(any("baked pixels != live render" in s for s in chk3.mismatched), chk3.mismatched)
        bake_pack(m, str(self.tmp), only={"tp/spr"}, verbose=None)
        self.assertTrue(check_pack(m, str(self.tmp), sample_every=1).ok)

    def test_check_reports_missing_bakeinfo_and_files(self):
        chk = check_pack(self.reg.packs["tp"], str(self.tmp))
        self.assertFalse(chk.ok)
        self.assertEqual(len(chk.missing), 3)

    def test_lint_and_sheet(self):
        bake_pack(self.reg.packs["tp"], str(self.tmp), verbose=None)
        m = self.reg.packs["tp"]
        m.assets = {k: v for k, v in m.assets.items() if k == "tp/spr"}
        rep = lint_pack(m, str(self.tmp))
        self.assertEqual((rep.assets, rep.checks["fringe"], rep.warnings), (1, 2, []))
        out = self.tmp / "sheet.png"
        self.assertEqual(contact_sheet(m, str(self.tmp), str(out)), 2)
        self.assertTrue(out.exists())

    def test_source_hash_tracks_in_package_imports_and_bake_deps(self):
        (self.pkg / "kit.py").write_text("PAL = 1\n", encoding="utf-8")
        (self.pkg / "far.py").write_text("X = 1\n", encoding="utf-8")
        self.mod_path.write_text("from tp_art import kit\nBAKE_DEPS = ('tp_art.far',)\n" + ART_SRC % 10, encoding="utf-8")
        a = self.reg.define("tp/spr")
        h1, deps = source_hash(a, str(self.tmp))
        self.assertEqual(deps, ["tp_art.spr", "tp_art.kit", "tp_art.far"])   # package __init__ not hashed
        (self.pkg / "__init__.py").write_text("ZZ = 1\n", encoding="utf-8")
        self.assertEqual(source_hash(a, str(self.tmp))[0], h1)
        (self.pkg / "kit.py").write_text("PAL = 2\n", encoding="utf-8")
        h2, _ = source_hash(a, str(self.tmp))
        (self.pkg / "far.py").write_text("X = 2\n", encoding="utf-8")
        h3, _ = source_hash(a, str(self.tmp))
        self.assertEqual(len({h1, h2, h3}), 3)


class TestHotReload(_Pack):
    def test_watcher_reloads_module_and_emits_event(self):
        bus = EventBus()
        seen = []
        bus.subscribe(AssetReloaded, seen.append)
        self.reg.bus = bus
        before = self.reg.get("tp/spr", 0)
        self.assertEqual(before.get_at((0, 0)), (10, 40, 200, 255))
        w = AssetWatcher(self.reg, interval_ms=500)
        self.assertEqual(w.run_once(), [])
        self.mod_path.write_text(ART_SRC % 77, encoding="utf-8")
        os.utime(self.mod_path, (time.time() + 5, time.time() + 5))     # mtime surely differs
        self.assertEqual(w.poll(0), ["tp/spr"])
        self.assertEqual(w.poll(100), [])                               # throttled
        bus.flush()
        self.assertEqual([(e.id, "spr.py" in e.reason) for e in seen], [("tp/spr", True)])
        after = self.reg.get("tp/spr", 0)
        self.assertIsNot(after, before)
        self.assertEqual(after.get_at((0, 0)), (77, 40, 200, 255))       # new source is live
        self.assertEqual(w.reloads, 1)

    def test_manual_reload_without_bus(self):
        self.reg.get("tp/spr", 0)
        self.reg.get("tp/spr", 1)
        self.assertEqual(self.reg.reload("tp/spr"), 2)
        self.assertEqual(self.reg.cache_size(), 0)


class TestLoadersAndPoseCache(unittest.TestCase):
    def test_load_image_modes(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            p = tmp / "i.png"
            s = pygame.Surface((2, 2), pygame.SRCALPHA)
            s.fill((9, 8, 7, 128))
            pygame.image.save(s, str(p))
            got = load_image(str(p))
            self.assertEqual(got.get_at((0, 0)), (9, 8, 7, 128))
            self.assertEqual(load_image(io.BytesIO(p.read_bytes())).get_size(), (2, 2))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_load_sound_bytesio(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except pygame.error as e:
            self.skipTest(f"no mixer: {e}")
        import struct
        import wave
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(22050)
            w.writeframes(struct.pack("<2205h", *([0] * 2205)))
        snd = load_sound(io.BytesIO(buf.getvalue()))
        self.assertAlmostEqual(snd.get_length(), 0.1, delta=0.02)

    def test_pose_cache_fifo_and_artpack_delegation(self):
        from engine.anim import POSES, PoseCache
        from engine.assets import artpack
        pc = PoseCache(cap=2)
        calls = []
        mk = lambda k: pc.get(k, (2, 2), lambda s: calls.append(k))  # noqa: E731
        a = mk("a")
        self.assertIs(mk("a"), a)
        mk("b")
        mk("c")                                   # evicts "a" (FIFO)
        self.assertEqual((len(pc), "a" in pc, pc.hits, pc.misses), (2, False, 1, 3))
        self.assertIsNot(mk("a"), a)
        POSES.clear()
        s = artpack.pose(("unit", 1), (3, 3), lambda surf: surf.fill((1, 1, 1, 255)))
        self.assertIs(artpack.pose(("unit", 1), (3, 3), lambda surf: None), s)
        self.assertIn(("unit", 1), POSES)
        artpack.rebuild()
        self.assertEqual(len(POSES), 0)


class TestD5AndShim(unittest.TestCase):
    RAW = re.compile(r"pygame\.image\.load\(|pygame\.mixer\.Sound\(|pygame\.mixer\.music\.load\(")

    def test_no_raw_loads_outside_engine_assets(self):
        hits = []
        for p in (ROOT / "src").rglob("*.py"):
            rel = p.relative_to(ROOT).as_posix()
            if rel.startswith("src/engine/assets/"):
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if self.RAW.search(line) and not line.lstrip().startswith("#"):
                    hits.append(f"{rel}:{i}")
        self.assertEqual(hits, [], "raw loads must go through engine.assets.load_image/load_sound")

    def test_art_m5_shim_is_the_owner(self):
        import art.m5 as shim
        import game.art.m5 as owner
        from art.m5 import _kit as K
        from art.m5.bale import variant_for
        self.assertIs(shim.get, owner.get)
        self.assertIs(K, sys.modules["game.art.m5._kit"])
        self.assertIs(sys.modules["art.m5.bale"], sys.modules["game.art.m5.bale"])
        self.assertIs(variant_for, sys.modules["game.art.m5.bale"].variant_for)
        self.assertIs(shim.maru, owner.module("maru"))
        self.assertEqual(shim.module("plate").__name__, "game.art.m5.plate")
        reg = owner.registry()
        self.assertIn("m5/armband", reg.assets)
        s = owner.get("armband")
        self.assertEqual(s.get_size(), tuple(reg.define("m5/armband").size))
        self.assertIs(s, shim.get("armband"))
        # out-of-range variant: no baked file -> live render path, exactly like the legacy loader
        self.assertEqual(reg.get("m5/armband", 7, default=None).get_size(), s.get_size())
        self.assertGreaterEqual(reg.stats["rendered"], 1)
        self.assertEqual(reg.variant_index("m5/inspect_art", "tram"), 5)
        self.assertTrue(owner.baked_path("armband").endswith(os.path.join("assets", "baked", "m5", "armband_0.png")))


if __name__ == "__main__":
    unittest.main()
