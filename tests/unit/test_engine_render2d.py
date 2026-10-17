"""engine.render2d kernel: queue order, drawables, rotation cache, camera, static chunks, post-FX parity (RPE6 Phase 6)."""
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from engine.render2d import (  # noqa: E402
    SCREEN, Camera2D, CircleDraw, CustomDraw, FillDraw, Layer, LineDraw, OverlayDraw, PostFX, RectDraw, RenderQueue,
    RotatedSpriteDraw, RotationCache, SpriteDraw, StaticLayers, SurfaceDraw, TextDraw, Y_SORTED,
)
from engine.render2d import postfx  # noqa: E402


def _surf(w=8, h=8, color=(255, 0, 0, 255)):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill(color)
    return s


def _same(a, b):
    return pygame.image.tobytes(a, "RGBA") == pygame.image.tobytes(b, "RGBA")


class QueueOrderTests(unittest.TestCase):
    def test_layers_draw_in_table_order_and_insertion_order_inside_unsorted_layers(self):
        q = RenderQueue()
        trace = []
        q.begin(0, 0)
        q.submit(CustomDraw(lambda s, x, y: trace.append("ui"), "ui"), Layer.UI)
        q.submit(CustomDraw(lambda s, x, y: trace.append("floor-a"), "fa"), Layer.FLOOR)
        q.submit(CustomDraw(lambda s, x, y: trace.append("floor-b"), "fb"), Layer.FLOOR)
        q.submit(CustomDraw(lambda s, x, y: trace.append("decal"), "d"), Layer.DECALS_DYNAMIC)
        st = q.flush(pygame.Surface((4, 4)))
        self.assertEqual(trace, ["floor-a", "floor-b", "decal", "ui"])
        self.assertEqual(st.custom, 4)
        self.assertEqual(st.custom_names, ["fa", "fb", "d", "ui"])
        self.assertEqual(q.pending(), 0)          # flushed items are gone

    def test_y_sorted_layers_default_to_world_y_and_explicit_keys_win(self):
        q = RenderQueue()
        trace = []

        def mk(name, y):
            return CustomDraw(lambda s, x, yy, n=name: trace.append(n), name, pos=(0, y))

        q.begin()
        q.submit(mk("low", 300), Layer.ENTITIES)
        q.submit(mk("high", 100), Layer.ENTITIES)
        q.submit(mk("mid", 200), Layer.ENTITIES)
        q.flush(pygame.Surface((4, 4)))
        self.assertEqual(trace, ["high", "mid", "low"])
        self.assertIn(Layer.ENTITIES, Y_SORTED)

        trace.clear()
        q.begin()
        q.submit(mk("second", 50), Layer.ENTITIES, sort_key=2)     # authored order beats world y
        q.submit(mk("first", 900), Layer.ENTITIES, sort_key=1)
        q.submit(mk("third-a", 10), Layer.ENTITIES, sort_key=3)
        q.submit(mk("third-b", 5), Layer.ENTITIES, sort_key=3)     # ties keep insertion order
        q.flush(pygame.Surface((4, 4)))
        self.assertEqual(trace, ["first", "second", "third-a", "third-b"])

    def test_begin_clears_and_optional_clear_colour_is_the_first_draw(self):
        q = RenderQueue()
        q.begin()
        q.submit(CustomDraw(lambda s, x, y: None, "stale"), Layer.UI)
        q.begin(clear=(1, 2, 3))
        self.assertEqual([d["kind"] for d in q.describe()], ["fill"])
        target = pygame.Surface((4, 4))
        q.flush(target)
        self.assertEqual(target.get_at((0, 0))[:3], (1, 2, 3))

    def test_unknown_layer_raises_and_exceptions_propagate(self):
        q = RenderQueue()
        with self.assertRaises(ValueError):
            q.submit(FillDraw((0, 0, 0)), 42)

        def boom(s, x, y):
            raise RuntimeError("painter failed")

        q.begin()
        q.submit(CustomDraw(boom, "boom"), Layer.UI)
        with self.assertRaises(RuntimeError):
            q.flush(pygame.Surface((4, 4)))

    def test_stats_count_blits_per_layer(self):
        q = RenderQueue()
        q.begin(10, 20)
        img = _surf()
        q.submit(SurfaceDraw(img, (10, 20)), Layer.ENTITIES)
        q.submit(SurfaceDraw(img, (10, 20)), Layer.ENTITIES)
        q.submit(TextDraw("x", pygame.font.Font(None, 12), (0, 0), shadow=(1, 1)), Layer.UI)
        st = q.flush(pygame.Surface((32, 32)))
        self.assertEqual(st.draws[Layer.ENTITIES], 2)
        self.assertEqual(st.blits[Layer.ENTITIES], 2)
        self.assertEqual(st.blits[Layer.UI], 2)      # shadow + text
        self.assertEqual(st.custom, 0)
        self.assertIn("entities", st.as_dict()["draws"])
        self.assertTrue(st.lines()[0].startswith("frame 0:"))


class DrawableTests(unittest.TestCase):
    def setUp(self):
        pygame.font.init()

    def test_world_space_subtracts_the_camera_and_screen_space_does_not(self):
        target = pygame.Surface((32, 32))
        img = _surf(4, 4)
        q = RenderQueue()
        q.begin(100, 200)
        q.submit(SurfaceDraw(img, (104, 204)), Layer.ENTITIES)             # -> (4, 4)
        q.submit(SurfaceDraw(img, (20, 20), space=SCREEN), Layer.UI)       # -> (20, 20)
        q.flush(target)
        self.assertEqual(target.get_at((4, 4))[:3], (255, 0, 0))
        self.assertEqual(target.get_at((20, 20))[:3], (255, 0, 0))
        self.assertEqual(target.get_at((0, 0))[:3], (0, 0, 0))

    def test_anchor_and_alpha(self):
        target = pygame.Surface((32, 32))
        img = _surf(8, 8)
        SurfaceDraw(img, (16, 16), anchor="center").draw(target, 0, 0)
        self.assertEqual(target.get_at((12, 12))[:3], (255, 0, 0))
        self.assertEqual(target.get_at((11, 11))[:3], (0, 0, 0))
        target.fill((0, 0, 0))
        SurfaceDraw(img, (0, 0), alpha=128).draw(target, 0, 0)
        self.assertLess(target.get_at((1, 1))[0], 255)
        self.assertEqual(img.get_alpha(), None if img.get_alpha() is None else img.get_alpha())  # source untouched

    def test_sprite_draw_resolves_through_the_queue_resolver(self):
        calls = []
        img = _surf(4, 4, (0, 255, 0, 255))

        def resolver(asset, variant, scale):
            calls.append((asset, variant, scale))
            return img if asset == "m5/thing" else None

        q = RenderQueue(resolver=resolver)
        target = pygame.Surface((16, 16))
        q.begin()
        q.submit(SpriteDraw("m5/thing", 2, (2, 2), anchor="topleft"), Layer.ENTITIES)
        q.submit(SpriteDraw("m5/missing", 0, (8, 8)), Layer.ENTITIES)
        st = q.flush(target)
        self.assertEqual(calls, [("m5/thing", 2, 1.0), ("m5/missing", 0, 1.0)])
        self.assertEqual(target.get_at((2, 2))[:3], (0, 255, 0))
        self.assertEqual(st.blits[Layer.ENTITIES], 1)      # the missing asset drew nothing, loudly countable

    def test_rotation_cache_matches_the_legacy_guard_formula(self):
        base = pygame.Surface((10, 4), pygame.SRCALPHA)
        base.fill((255, 255, 255, 255))
        pygame.draw.rect(base, (255, 0, 0, 255), (8, 0, 2, 4))
        cache = RotationCache()
        import math
        for angle in (0.0, 0.3, math.pi / 2, 2.0, 5.9):
            b = int(round(angle / (2 * math.pi) * 64)) % 64
            legacy = pygame.transform.rotate(base, -b * 360.0 / 64)
            self.assertTrue(_same(cache.get(base, angle, 64), legacy))
        self.assertEqual(cache.misses, 5)
        cache.get(base, 0.3, 64)
        self.assertEqual(cache.hits, 1)
        self.assertEqual(RotationCache.bucket_of(2 * math.pi, 64), 0)

    def test_rotated_sprite_draw_uses_the_shared_cache_and_reports_hits(self):
        base = _surf(6, 2)
        q = RenderQueue()
        target = pygame.Surface((32, 32))
        for _ in range(2):
            q.begin()
            q.submit(RotatedSpriteDraw((16, 16), 1.0, base=base, key="g0"), Layer.ENTITIES)
            st = q.flush(target)
        self.assertEqual((st.cache_hits, st.cache_misses), (1, 0))

    def test_primitives_draw_where_pygame_would(self):
        target = pygame.Surface((32, 32))
        ref = pygame.Surface((32, 32))
        LineDraw([(2, 2), (10, 2)], (255, 255, 255), 1).draw(target, 0, 0)
        CircleDraw((20, 20), 3, (0, 255, 0)).draw(target, 0, 0)
        RectDraw((1, 20, 5, 5), (0, 0, 255), 1, border_radius=1).draw(target, 0, 0)
        pygame.draw.line(ref, (255, 255, 255), (2, 2), (10, 2), 1)
        pygame.draw.circle(ref, (0, 255, 0), (20, 20), 3, 0)
        pygame.draw.rect(ref, (0, 0, 255), (1, 20, 5, 5), 1, border_radius=1)
        self.assertTrue(_same(target, ref))

    def test_custom_draw_receives_surface_and_camera(self):
        seen = []
        CustomDraw(lambda s, x, y: seen.append((s.get_width(), x, y)), "probe").draw(pygame.Surface((7, 7)), 3, 4)
        self.assertEqual(seen, [(7, 3, 4)])


class CameraTests(unittest.TestCase):
    def test_snap_follow_deadzone_and_bounds(self):
        cam = Camera2D(100, 50, bounds=(1000, 500), deadzone=(10, 5), ease=1.0)
        cam.snap(50, 25)
        self.assertEqual(cam.offset(), (0, 0))               # clamped to the top-left corner
        cam.follow(50, 25)
        self.assertEqual(cam.offset(), (0, 0))               # inside the dead-zone: no move
        cam.follow(500, 250)
        self.assertEqual(cam.offset(), (440, 220))           # moved by (target - deadzone edge)
        cam.follow(5000, 5000)
        self.assertEqual(cam.offset(), (900, 450))           # clamped to the far corner
        self.assertEqual(cam.world_to_screen(950, 475), (50, 25))
        self.assertEqual(cam.screen_to_world(50, 25), (950.0, 475.0))

    def test_interpolation_and_lookahead(self):
        cam = Camera2D(100, 50, ease=1.0, lookahead=20)
        cam.snap(100, 100)
        cam.follow(100, 100, aim_angle=0.0)                  # look-ahead pulls 20 px along +x
        self.assertEqual(cam.offset(1.0), (70, 75))
        self.assertEqual(cam.offset(0.0), (50, 75))
        self.assertEqual(cam.offset(0.5), (60, 75))

    def test_trauma_shake_is_deterministic_from_the_given_stream(self):
        a = Camera2D(100, 50, rng=random.Random(7), shake_amp=10, trauma_decay=0.5)
        b = Camera2D(100, 50, rng=random.Random(7), shake_amp=10, trauma_decay=0.5)
        for cam in (a, b):
            cam.add_trauma(1.0)
            cam.tick_shake()
        self.assertEqual((a.kick_x, a.kick_y), (b.kick_x, b.kick_y))
        self.assertNotEqual(a.offset(), (0, 0))
        a.tick_shake()
        a.tick_shake()
        self.assertEqual(a.trauma, 0.0)
        self.assertEqual(a.offset(), (0, 0))
        a.set_kick(3, -2)
        self.assertEqual(a.offset(), (3, -2))


class StaticLayerTests(unittest.TestCase):
    def test_chunks_paint_lazily_and_compose_like_a_cleared_screen(self):
        painted = []

        def painter(target, ox, oy, w, h):
            painted.append((ox, oy, w, h))
            # a 16-px grid of red squares in world space, exactly like per-tile blits would do
            for wy in range(oy - oy % 16, oy + h, 16):
                for wx in range(ox - ox % 16, ox + w, 16):
                    pygame.draw.rect(target, (255, 0, 0), (wx - ox, wy - oy, 8, 8))

        layers = StaticLayers(chunk=32)
        layers.define("floor", painter=painter, world_size=(80, 48), signature=("map-a",), fill=(9, 9, 9))
        screen = pygame.Surface((40, 40))
        n = layers.blit(screen, "floor", 20, 10, (40, 40))
        self.assertEqual(n, 4)                                   # chunks (0,0) (1,0) (0,1) (1,1)
        self.assertEqual(sorted(painted), [(0, 0, 32, 32), (0, 32, 32, 16), (32, 0, 32, 32), (32, 32, 32, 16)])
        ref = pygame.Surface((40, 40))
        ref.fill((9, 9, 9))
        for wy in range(0, 48, 16):
            for wx in range(0, 80, 16):
                pygame.draw.rect(ref, (255, 0, 0), (wx - 20, wy - 10, 8, 8))
        # outside the world the static layer paints nothing (the caller clears the screen)
        ref_vis = ref.subsurface((0, 0, 40, 38)).copy()
        self.assertTrue(_same(screen.subsurface((0, 0, 40, 38)).copy(), ref_vis))
        layers.blit(screen, "floor", 20, 10, (40, 40))
        self.assertEqual(len(painted), 4)                        # cached: no repaint
        self.assertEqual(layers.stats()["floor"]["chunks"], 4)

    def test_signature_change_drops_chunks_and_same_signature_keeps_them(self):
        calls = []
        painter = lambda t, ox, oy, w, h: calls.append((ox, oy))  # noqa: E731
        layers = StaticLayers(chunk=64)
        layers.define("floor", painter=painter, world_size=(64, 64), signature=1)
        layers.blit(pygame.Surface((64, 64)), "floor", 0, 0, (64, 64))
        layers.define("floor", painter=painter, world_size=(64, 64), signature=1)
        layers.blit(pygame.Surface((64, 64)), "floor", 0, 0, (64, 64))
        self.assertEqual(len(calls), 1)
        layers.define("floor", painter=painter, world_size=(64, 64), signature=2)
        layers.blit(pygame.Surface((64, 64)), "floor", 0, 0, (64, 64))
        self.assertEqual(len(calls), 2)
        self.assertEqual(layers.visible_chunks("floor", 500, 500, (64, 64)), [])
        self.assertEqual(layers.visible_chunks("floor", -100, -100, (64, 64)), [])


class PostFXParityTests(unittest.TestCase):
    """The engine builders must reproduce the legacy overlays pixel for pixel (core.config)."""

    def test_vignette_and_scanlines_match_core_config(self):
        from core import config
        size = (config.WIDTH, config.HEIGHT)
        band = (config.SCENE_TOP, config.SCENE_BOT)
        self.assertTrue(_same(postfx.vignette(size, 130, band), config.VIGNETTE))
        self.assertTrue(_same(postfx.scanlines(size, band), config.SCANLINES))

    def test_cache_and_overlay_draw(self):
        fx = PostFX()
        a = fx.vignette((40, 30), 100, (5, 25))
        b = fx.vignette((40, 30), 100, (5, 25))
        self.assertIs(a, b)
        self.assertEqual(len(fx), 1)
        plate = fx.flash((8, 8), (255, 255, 255))
        target = pygame.Surface((8, 8))
        OverlayDraw(plate, alpha=0).draw(target, 0, 0)
        self.assertEqual(target.get_at((1, 1))[:3], (0, 0, 0))
        OverlayDraw(plate, alpha=255).draw(target, 0, 0)
        self.assertEqual(target.get_at((1, 1))[:3], (255, 255, 255))
        g = postfx.grain((16, 16), seed=3)
        self.assertTrue(_same(g, postfx.grain((16, 16), seed=3)))
        lb = postfx.letterbox((20, 20), 4)
        self.assertEqual(lb.get_at((1, 1)), (0, 0, 0, 255))
        self.assertEqual(lb.get_at((1, 10))[3], 0)


if __name__ == "__main__":
    unittest.main()
