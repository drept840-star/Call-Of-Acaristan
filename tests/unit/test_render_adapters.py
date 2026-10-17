"""Phase 6 peel-off twins are pixel-identical to the legacy painters they replace (RPE6, ADR-017).

Each test paints the same inputs twice - once through the legacy painter, once through the
drawable twin flushed onto a second surface - and compares the raw pixels. Inputs use
fractional/negative positions on purpose: that is where truncation order differs.
"""
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

from engine.render2d import EllipseDraw, PolyDraw, RectDraw, RenderQueue, Layer  # noqa: E402
import engine.lighting as lighting  # noqa: E402
from engine.ui import prompt as ui_prompt  # noqa: E402


def _same(a, b):
    return pygame.image.tobytes(a, "RGBA") == pygame.image.tobytes(b, "RGBA")


def _pair(size=(200, 160), color=(30, 40, 50)):
    a = pygame.Surface(size)
    a.fill(color)
    b = a.copy()
    return a, b


def _flush(surface, drawables):
    for d in drawables:
        d.draw(surface, 0, 0)


class PrimitivePassThroughTests(unittest.TestCase):
    def test_rect_and_ellipse_forward_floats_like_the_legacy_call(self):
        a, b = _pair()
        pygame.draw.rect(a, (200, 10, 10), (-0.6, 3.4, 7, 5))
        pygame.draw.ellipse(a, (10, 200, 10), (20.7, -0.2, 30, 11))
        _flush(b, [RectDraw((-0.6, 3.4, 7, 5), (200, 10, 10), space="screen"),
                   EllipseDraw((20.7, -0.2, 30, 11), (10, 200, 10), space="screen")])
        self.assertTrue(_same(a, b))

    def test_polygon_points_pass_through(self):
        a, b = _pair()
        pts = [(3.2, 4.9), (40.5, -1.5), (22.1, 33.3)]
        pygame.draw.polygon(a, (1, 2, 3), pts)
        pygame.draw.polygon(a, (9, 9, 9), pts, 1)
        _flush(b, [PolyDraw(pts, (1, 2, 3), space="screen"), PolyDraw(pts, (9, 9, 9), 1, space="screen")])
        self.assertTrue(_same(a, b))


class LegacyClassTwinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core import config  # noqa: F401  (pygame fonts etc. come up once)
        from game.render import adapters
        cls.config, cls.adapters = config, adapters

    def test_particles_match(self):
        cfg, ad = self.config, self.adapters
        rng = random.Random(7)
        parts = []
        for _ in range(40):
            p = cfg.Particle(rng.uniform(-5, 190), rng.uniform(-5, 150), (rng.randrange(256), 90, 40))
            p.size = rng.randint(1, 4)
            p.life = rng.randint(0, 3)
            parts.append(p)
        a, b = _pair()
        for p in parts:
            p.draw(a, 2.5, -1.25)
        _flush(b, ad.particle_drawables(parts, 2.5, -1.25))
        self.assertTrue(_same(a, b))

    def test_casings_match(self):
        cfg, ad = self.config, self.adapters
        rng = random.Random(3)
        cas = []
        for _ in range(25):
            c = cfg.Casing(rng.uniform(0, 190), rng.uniform(0, 150), rng.uniform(0, 6.3))
            c.rot = rng.uniform(0, 6.3)
            c.life = rng.randint(0, 2)
            cas.append(c)
        a, b = _pair()
        for c in cas:
            c.draw(a, 0.4, 0.6)
        _flush(b, ad.casing_drawables(cas, 0.4, 0.6))
        self.assertTrue(_same(a, b))

    def test_bullets_match(self):
        from core.camera import draw_bullets
        cfg, ad = self.config, self.adapters
        rng = random.Random(11)
        bullets = []
        for i in range(20):
            b_ = {"x": rng.uniform(-10, 200), "y": rng.uniform(-10, 160), "dx": rng.uniform(-9, 9),
                  "dy": rng.uniform(-9, 9)}
            if i % 2:
                b_["prev_x"], b_["prev_y"] = b_["x"] - 3.3, b_["y"] + 2.2
            bullets.append(b_)
        a, b = _pair()
        draw_bullets(a, bullets, 1.7, 2.9, with_glow=True)
        _flush(b, ad.bullet_drawables(bullets, 1.7, 2.9, cfg.bullet_glow, cfg.C_BULLET))
        self.assertTrue(_same(a, b))

    def test_rain_twin_steps_drops_and_rng_identically(self):
        cfg = self.config
        from engine.core import LEGACY_RNG
        drops_a = [(x * 37 % cfg.WIDTH, cfg.SCENE_BOT - 3 + (x % 5), 10 + x % 9) for x in range(60)]
        drops_b = list(drops_a)
        a, b = _pair((cfg.WIDTH, cfg.HEIGHT))
        st = LEGACY_RNG.getstate()
        cfg.draw_rain(a, drops_a)
        after_legacy = LEGACY_RNG.getstate()
        LEGACY_RNG.setstate(st)
        _flush(b, cfg.rain_drawables(drops_b))
        self.assertEqual(LEGACY_RNG.getstate(), after_legacy)
        self.assertEqual(drops_a, drops_b)
        self.assertTrue(_same(a, b))

    def test_fire_zone_draw_equals_drawables(self):
        from entities.weapons import FireZone
        from engine.core import LEGACY_RNG, pin_wall, unpin_wall
        fz = FireZone(90.4, 70.2)
        fz.life = 300
        a, b = _pair()
        pin_wall(lambda: 123456)      # B-037: the painter's flicker reads now_ms();
        try:                          # an unpinned pair can straddle a tick and differ
            st = LEGACY_RNG.getstate()
            fz.draw(a, 3.1, -2.2)
            LEGACY_RNG.setstate(st)
            _flush(b, fz.drawables(3.1, -2.2))
        finally:
            unpin_wall()
        self.assertTrue(_same(a, b))

    def test_corpse_render_is_what_draw_blits(self):
        from entities import corpse as corpse_mod
        c = corpse_mod.Corpse.__new__(corpse_mod.Corpse)
        # a minimal corpse: use the public spawn path if available, else skip
        try:
            from core.state import STATE
            from entities.enemy_ai import Enemy
            e = Enemy(100, 80)
            e.angle = 0.7
            corpse_mod.spawn_corpse(e)
            c = corpse_mod._corpses()[-1]
        except Exception as exc:  # pragma: no cover - environment without a spawnable enemy
            self.skipTest("no spawnable enemy: %r" % (exc,))
        a, b = _pair()
        c.draw(a, 4, 6)
        r = c.render(4, 6)
        if r is not None:
            b.blit(r[0], r[1])
        self.assertTrue(_same(a, b))


class LightMapTests(unittest.TestCase):
    def test_lightmap_draw_equals_inline_multiply_double_formula(self):
        a, b = _pair((120, 90), (90, 120, 150))
        pygame.draw.circle(a, (200, 180, 40), (40, 40), 20)
        pygame.draw.circle(b, (200, 180, 40), (40, 40), 20)
        lamp = lighting.falloff_sprite(30, (255, 200, 120))
        bloom = lighting.bloom_sprite(24, (255, 200, 120))
        # inline legacy formula
        lm = pygame.Surface((120, 90))
        lm.fill(tuple(c // 2 for c in (50, 58, 94)))
        lm.blit(lamp, (10, 5), special_flags=pygame.BLEND_RGB_ADD)
        a.blit(lm, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        a.blit(a.copy(), (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        a.blit(bloom, (16, 11), special_flags=pygame.BLEND_RGB_ADD)
        d = lighting.LightMapDraw((50, 58, 94), [(lamp, (10, 5))], [(bloom, (16, 11))])
        d.draw(b, 0, 0)
        self.assertTrue(_same(a, b))
        self.assertEqual(d.kind, "lighting")

    def test_sprites_are_cached_per_key(self):
        self.assertIs(lighting.falloff_sprite(40, (1, 2, 3)), lighting.falloff_sprite(40, (1, 2, 3)))
        self.assertIsNot(lighting.falloff_sprite(40, (1, 2, 3)), lighting.falloff_sprite(41, (1, 2, 3)))


class PromptBuildTests(unittest.TestCase):
    def test_build_parts_blit_to_the_same_pixels_as_draw(self):
        pygame.font.init()
        font = pygame.font.Font(None, 18)
        a, b = _pair((300, 200))
        ui_prompt.draw(a, 150.4, 120.2, "look", (240, 230, 200), font=font, fill=(10, 12, 18, 200),
                       rim=(200, 170, 90, 220), radius=5, pad=(6, 3), clamp=False)
        for img, pos in ui_prompt.build((300, 200), 150.4, 120.2, "look", (240, 230, 200), font=font,
                                        fill=(10, 12, 18, 200), rim=(200, 170, 90, 220), radius=5, pad=(6, 3),
                                        clamp=False):
            b.blit(img, pos)
        self.assertTrue(_same(a, b))


class QueueViewportTests(unittest.TestCase):
    def test_begin_records_viewport(self):
        q = RenderQueue()
        q.begin(3, 4, viewport=(640, 360))
        self.assertEqual(q.viewport, (640, 360))
        self.assertEqual((q.cam_x, q.cam_y), (3, 4))

    def test_tuple_sort_keys_interleave_with_authored_slots(self):
        q = RenderQueue()
        trace = []
        q.begin(0, 0)
        from engine.render2d import CustomDraw
        for key, name in [((5, 0), "maru"), ((3, 2), "guard2"), ((0, 0), "corpse"), ((3, 0), "guard0"), ((4, 0), "npc")]:
            q.submit(CustomDraw(lambda s, x, y, n=name: trace.append(n), name), Layer.ENTITIES, sort_key=key)
        q.flush(pygame.Surface((4, 4)))
        self.assertEqual(trace, ["corpse", "guard0", "guard2", "npc", "maru"])


class PenTests(unittest.TestCase):
    def test_player_draw_recording_pen_equals_immediate(self):
        from entities.player import Player
        from engine.render2d import RecordingPen
        from core.state import STATE
        saved_weapon = getattr(STATE, "current_weapon", "pistol")
        try:
            for weapon in ("pistol", "k9_smg", "os12"):
                STATE.current_weapon = weapon
                a, b = _pair((240, 200), (24, 28, 34))
                p = Player(120, 100)
                p.angle = 0.7
                p.draw(a, 20, 30, is_moving=True)
                pen = RecordingPen()
                p.draw(None, 20, 30, is_moving=True, pen=pen)
                self.assertGreater(len(pen.items), 20)
                _flush(b, pen.items)
                self.assertTrue(_same(a, b), f"weapon {weapon} diverged")
        finally:
            STATE.current_weapon = saved_weapon

    def test_rig_draw_accepts_a_pen_and_records(self):
        from entities import weapon_rig
        from core import appearance
        from engine.render2d import RecordingPen
        resolved = appearance.resolve(appearance.default_appearance())
        ctx = {"grip_x": 60.4, "grip_y": 50.6, "arm_dx": 0.8, "arm_dy": 0.6, "raise_factor": 0.3,
               "reload_active": True, "reload_progress": 0.4}
        for gun in ("os12", "k9_smg", "pistol"):
            a, b = _pair()
            weapon_rig.draw(a, gun, ctx, resolved["rigs"])
            pen = RecordingPen()
            weapon_rig.draw(None, gun, ctx, resolved["rigs"], pen=pen)
            self.assertTrue(pen.items)
            _flush(b, pen.items)
            self.assertTrue(_same(a, b), f"rig {gun} diverged")


if __name__ == "__main__":
    unittest.main()
