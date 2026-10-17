
"""Enemy death corpses - bodies that fall instead of vanishing.

Previously every mission's ``if e.hp <= 0:`` funnel did burst + decal +
``STATE.enemies.remove(e)`` - the sprite disappeared on the same frame the
enemy died, which read as anticlimactic. Now the funnels also call
``spawn_corpse(e)`` (just before removing the Enemy), which drops a Corpse
into ``STATE.corpses`` and plays a short sequence:

    1. Topple (~0.27s) - a two-pose skeleton morph: the compact top-down
       standing silhouette (head + torso + arms, legs hidden under the
       torso) unfolds into a full-length body laid on the floor - head at
       one end, legs extended, arms thrown out - rotating onto a random
       side as it goes. The rifle pops out of the hands and skids away,
       spinning.
    2. Landing       - a body-fall thud (3D positional, concrete_impact),
       a small blood puff, a subtle screen shake + hit-stop on the kill
       itself, and a blood-pool decal that is joined by a wider second
       pool ~1s later (the bleed spreads).
    3. Lie (~2.8s)   - the body lies in the growing pool in one of three
       randomized sprawl poses (face-up splayed, curled on side, face-down
       with a bent leg); occasional blood drip particles (respects
       SETTINGS.particle_density).
    4. Fade (~0.9s)  - the corpse fades out, leaving the blood decals
       behind as the permanent trace of the kill.

Integration points (mirrors the death_anim.py convention):
    spawn_corpse(enemy)              - call in the hp <= 0 funnel
    corpse.update_corpses()          - once per frame from game_update()
    corpse.draw_corpses(surf, cx, cy)- in mission draw, AFTER floor decals
                                       and BEFORE living enemies/particles

All state lives on STATE.corpses so reset() in state.py clears it cleanly.
Corpses are capped (MAX_CORPSES): spawning past the cap retires the oldest
body so heavy firefights can't accumulate hundreds of surfaces.
"""
import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream

import pygame

from core.config import (
    WIDTH, HEIGHT, C_BLOOD, C_ENEMY_SKIN,
    C_IPA_UNIFORM, C_MAG_UNIFORM, C_IPA_ARMBAND, C_MAG_BANDANA,
    Particle,
)
from core.state import STATE
from fx import effects
import game.world as _gw  # RPE6 Phase 5 (D4): entity components
from engine.world import Label as _Label


# ── Timing (frames @ 60fps) ───────────────────────────────────────────
FALL_FRAMES = 16           # topple duration
LIE_FRAMES = 170           # body on the ground, bleeding
FADE_FRAMES = 55           # sink/fade out
CORPSE_TOTAL = FALL_FRAMES + LIE_FRAMES + FADE_FRAMES   # ~4.0s

MAX_CORPSES = 10           # hard cap - oldest body is retired first

# ── Kill punch (applied in spawn_corpse, same max-clamp helpers the
#    rest of the codebase uses; M3's own shake(6) still wins there) ────
SHAKE_ON_KILL = 8
HIT_STOP_ON_KILL = 0.05    # seconds - per AEGIS "heavy strike" guidance

# ── Pool decal timing ─────────────────────────────────────────────────
SECOND_POOL_DELAY = 60     # frames after landing before the bleed spreads
DRIP_PERIOD = 14           # frames between blood-drip chances
DRIP_CHANCE = 0.55

_POOL_DARK = (90, 6, 6)    # under-torso ooze (darker than C_BLOOD)
_BOOT = (30, 26, 22)


def _ease_out_cubic(t):
    """Decelerating ease - the body hits the floor fast, then settles."""
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def _lerp(p0, p1, t):
    return (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t)


def _corpses():
    """STATE.corpses with a lazy-init guard (survives odd reset paths)."""
    lst = getattr(STATE, "corpses", None)
    if lst is None:
        lst = []
        STATE.corpses = lst
    return lst


def _particle_density():
    """Same graceful density read as fx.effects.spawn_particles()."""
    try:
        from core.user_settings import SETTINGS
        return SETTINGS.particle_density
    except Exception:
        return 1.0


# ── Sprawled-pose library ─────────────────────────────────────────────
# Local lying-space offsets in (along, perp) coords: +along = toward the
# FEET, -along = toward the HEAD. Each pose is a dict of joints; three
# presets plus per-corpse jitter so no two kills look identical.
_POSES = [
    {   # face-up sprawl - arms thrown wide, legs slightly open
        "hand_a": (-3, 18), "elbow_a": (-9, 12),
        "hand_b": (-21, -12), "elbow_b": (-15, -8),
        "knee_l": (12, 6), "foot_l": (21, 9),
        "knee_r": (12, -4), "foot_r": (22, -7),
    },
    {   # curled on side - one arm tucked to the chest, legs drawn up
        "hand_a": (0, 7), "elbow_a": (-7, 11),
        "hand_b": (-5, -5), "elbow_b": (-11, -7),
        "knee_l": (10, 8), "foot_l": (16, 13),
        "knee_r": (14, -2), "foot_r": (20, -8),
    },
    {   # face-down - one arm flung overhead, one leg bent hard at knee
        "hand_a": (-22, 9), "elbow_a": (-16, 6),
        "hand_b": (2, -16), "elbow_b": (-5, -12),
        "knee_l": (13, 3), "foot_l": (23, 4),
        "knee_r": (10, -7), "foot_r": (14, -13),
    },
]
_JOINTS = ("hand_a", "elbow_a", "hand_b", "elbow_b",
           "knee_l", "foot_l", "knee_r", "foot_r")


class Corpse:
    """A fallen enemy body: topple → bleed → fade.

    Drawn as a skeleton morph between the standing top-down silhouette
    (what Enemy.draw shows) and a full-length lying pose, so the fall
    reads as a body unfolding onto the floor instead of a sprite spin.
    """

    def __init__(self, enemy):
        self.x = float(enemy.rect.centerx)
        self.y = float(enemy.rect.centery)
        self.angle = enemy.angle
        self.t = 0
        self.done = False

        # ── Identity (mirrors Enemy.draw's uniform selection) ──
        self.is_commander = enemy.is_commander
        self.is_mag = enemy.is_ambush_enemy
        if self.is_commander:
            self.uniform_col = (35, 32, 45)
            self.skin_col = (175, 145, 120)
        elif self.is_mag:
            self.uniform_col = C_MAG_UNIFORM
            self.skin_col = C_ENEMY_SKIN
        else:
            self.uniform_col = C_IPA_UNIFORM
            self.skin_col = C_ENEMY_SKIN

        # ── Topple choreography ──
        # Falls onto its side: perpendicular to facing, random direction,
        # with a little jitter so two enemies killed together don't mirror.
        self.fall_dir = _rng_legacy.choice((-1.0, 1.0))
        self.fall_jitter = _rng_legacy.uniform(-0.35, 0.35)
        self.slide_dist = _rng_legacy.uniform(3.0, 6.0)
        perp = self.angle + self.fall_dir * math.pi / 2
        self._slide_dx = math.cos(perp)
        self._slide_dy = math.sin(perp)
        # Lying axis: head points back along the fall side.
        self.lie_angle = self.angle + self.fall_dir * math.pi / 2 + self.fall_jitter

        # ── Sprawled pose: preset + per-joint jitter ──
        pose = dict(_rng_legacy.choice(_POSES))
        for j in _JOINTS:
            ax, pp = pose[j]
            pose[j] = (ax + _rng_legacy.uniform(-1.5, 1.5),
                       pp + _rng_legacy.uniform(-1.5, 1.5))
        self.pose = pose

        # ── Weapon eject ──
        d_x, d_y = math.cos(self.angle), math.sin(self.angle)
        grip_x = self.x + d_x * 19
        grip_y = self.y + d_y * 19
        eject_ang = perp + _rng_legacy.uniform(-0.9, 0.9)
        eject_dist = _rng_legacy.uniform(14.0, 24.0)
        self.gun_start = (grip_x, grip_y)
        self.gun_end = (
            grip_x + math.cos(eject_ang) * eject_dist,
            grip_y + math.sin(eject_ang) * eject_dist,
        )
        self.gun_angle = self.angle
        self.gun_spin = _rng_legacy.uniform(1.5, 3.0) * _rng_legacy.choice((-1.0, 1.0))

        # ── Mission-3 role gear: identity survives the fall ──
        # Breacher keeps vest+visor on the body, marksman's ejected rifle
        # is the long scoped one, technician keeps the headset (the radio
        # pack strap snaps - it clatters away), and the riot shield is a
        # physical object: it clatters to the floor beside the body.
        # RPE6 Phase 5 (D4): the enemy type is the shared Label component's ``kind``
        # (set by the mission spawn helpers); "" when the enemy carries no label.
        label = _gw.get(enemy, _Label)
        self.m3_type = label.kind if label is not None else ""
        self.gun_len = 34 if self.m3_type == "marksman" else 18
        self.shield_rel = None
        self.pack_rel = None
        if self.m3_type == "shield":
            s0 = (d_x * 20, d_y * 20)
            side = _rng_legacy.choice((-1.0, 1.0))
            dist = _rng_legacy.uniform(22, 30)
            s1 = (math.cos(perp) * dist * side + d_x * _rng_legacy.uniform(-4, 8),
                  math.sin(perp) * dist * side + d_y * _rng_legacy.uniform(-4, 8))
            self.shield_rel = (s0, s1, _rng_legacy.uniform(2.0, 3.6) * side)
        if self.m3_type == "technician":
            s0 = (-d_x * 10, -d_y * 10)
            side = _rng_legacy.choice((-1.0, 1.0))
            dist = _rng_legacy.uniform(16, 22)
            s1 = (math.cos(perp) * dist * side - d_x * _rng_legacy.uniform(2, 8),
                  math.sin(perp) * dist * side - d_y * _rng_legacy.uniform(2, 8))
            self.pack_rel = (s0, s1, _rng_legacy.uniform(1.5, 3.0) * side)

        self._landed = False
        self._pool2 = False

    # ── Lifecycle ──────────────────────────────────────────────────────
    def update(self):
        self.t += 1

        if self.t == FALL_FRAMES and not self._landed:
            self._landed = True
            self._on_land()

        if self.t == FALL_FRAMES + SECOND_POOL_DELAY and not self._pool2:
            self._pool2 = True
            # The bleed widens: second, larger decal slightly offset.
            STATE.blood_decals.append([
                self.x + _rng_legacy.randint(-5, 5),
                self.y + _rng_legacy.randint(-4, 6),
                150, _rng_legacy.randint(18, 26),
            ])

        # Occasional drip while the body lies there (density-aware).
        if FALL_FRAMES < self.t < FALL_FRAMES + LIE_FRAMES:
            if self.t % DRIP_PERIOD == 0 and _rng_legacy.random() < DRIP_CHANCE * _particle_density():
                p = Particle(
                    self.x + _rng_legacy.randint(-9, 9),
                    self.y + _rng_legacy.randint(-7, 9),
                    C_BLOOD,
                )
                p.dx *= 0.08
                p.dy *= 0.08
                p.life = _rng_legacy.randint(25, 45)
                STATE.particles.append(p)

        if self.t >= CORPSE_TOTAL:
            self.done = True

    def _on_land(self):
        """Body hits the floor: thud, small blood puff, first pool decal."""
        STATE.blood_decals.append([
            int(self.x), int(self.y + 1), 155, _rng_legacy.randint(13, 19),
        ])
        effects.burst(
            self.x, self.y, C_BLOOD, 5,
            speed_mul=0.45, life_min=12, life_max=28, jitter=6,
        )
        # Positional body-fall thud; falls back to flat audio if the
        # player is dead/unavailable (same helper the missions use).
        effects.play_impact("concrete_impact", (self.x, self.y), base_volume=0.30)

    # ── Skeleton ───────────────────────────────────────────────────────
    def _standing_skeleton(self):
        """Top-down standing joints (matches Enemy.draw proportions)."""
        a = self.angle
        d = (math.cos(a), math.sin(a))
        p = (math.cos(a + math.pi / 2), math.sin(a + math.pi / 2))
        C = (0.0, 0.0)  # local; caller offsets

        def pt(along, perp):
            return (C[0] + d[0] * along + p[0] * perp,
                    C[1] + d[1] * along + p[1] * perp)

        return {
            "head": pt(2, 0),
            "sh_l": pt(-1, 7), "sh_r": pt(-1, -7),
            "elbow_a": pt(5, 10), "hand_a": pt(15, -3),
            "elbow_b": pt(5, -10), "hand_b": pt(15, 3),
            "hip_l": pt(-7, 4), "hip_r": pt(-7, -4),
            # legs tucked under the torso (invisible while standing)
            "knee_l": pt(-10, 4), "foot_l": pt(-12, 4),
            "knee_r": pt(-10, -4), "foot_r": pt(-12, -4),
        }

    def _lying_skeleton(self):
        """Full-length body laid on the floor along lie_angle."""
        L = self.lie_angle
        # f = toward feet, h = toward head, p = perpendicular
        f = (math.cos(L), math.sin(L))
        p = (math.cos(L + math.pi / 2), math.sin(L + math.pi / 2))

        def pt(along, perp):
            return (f[0] * along + p[0] * perp,
                    f[1] * along + p[1] * perp)

        pose = self.pose
        return {
            "head": pt(-19, 0),
            "sh_l": pt(-12, 7), "sh_r": pt(-12, -7),
            "elbow_a": pt(*pose["elbow_a"]), "hand_a": pt(*pose["hand_a"]),
            "elbow_b": pt(*pose["elbow_b"]), "hand_b": pt(*pose["hand_b"]),
            "hip_l": pt(2, 4), "hip_r": pt(2, -4),
            "knee_l": pt(*pose["knee_l"]), "foot_l": pt(*pose["foot_l"]),
            "knee_r": pt(*pose["knee_r"]), "foot_r": pt(*pose["foot_r"]),
        }

    # ── Rendering ──────────────────────────────────────────────────────
    def draw(self, surface, cam_x, cam_y):
        r = self.render(cam_x, cam_y)
        if r is not None:
            surface.blit(r[0], r[1])

    def render(self, cam_x, cam_y):
        """Paint the body on its faded 128x128 layer; returns ``(layer, screen_pos)`` or
        ``None`` when culled/invisible. ``draw`` blits it; the RPE6 render queue wraps it
        in a ``SurfaceDraw`` (game.render.adapters.corpse_drawables)."""
        sx = self.x - cam_x
        sy = self.y - cam_y
        if sx < -110 or sx > WIDTH + 110 or sy < -110 or sy > HEIGHT + 110:
            return None

        u = _ease_out_cubic(self.t / float(FALL_FRAMES))          # topple 0→1
        fade_t = max(0.0, (self.t - FALL_FRAMES - LIE_FRAMES) / float(FADE_FRAMES))
        alpha = int(255 * (1.0 - fade_t))
        if alpha <= 0:
            return None
        sink = fade_t * 2.0                                        # settles into the floor

        cx = sx + self._slide_dx * self.slide_dist * u
        cy = sy + self._slide_dy * self.slide_dist * u + sink

        stand = self._standing_skeleton()
        lying = self._lying_skeleton()
        J = {k: _lerp(stand[k], lying[k], u) for k in stand}

        # Everything is painted on a small offscreen layer so the whole
        # body can fade with one set_alpha (procedural draws can't).
        layer = pygame.Surface((128, 128), pygame.SRCALPHA)
        c = 64  # layer center

        def P(j):
            return (c + J[j][0], c + J[j][1])

        L = self.lie_angle
        f = (math.cos(L), math.sin(L))
        p = (math.cos(L + math.pi / 2), math.sin(L + math.pi / 2))

        # ── Detached gear clattering to the floor: riot shield / radio pack ──
        gear_u = _ease_out_cubic(self.t / float(FALL_FRAMES + 6))
        for rel, is_shield in ((self.shield_rel, True), (self.pack_rel, False)):
            if rel is None:
                continue
            s0, s1, spin = rel
            ox = c + s0[0] + (s1[0] - s0[0]) * gear_u
            oy = c + s0[1] + (s1[1] - s0[1]) * gear_u
            ang = self.angle + spin * gear_u
            gdx, gdy = math.cos(ang), math.sin(ang)
            gpx, gpy = -gdy, gdx
            if is_shield:
                hw, hh = 10, 18
                pygame.draw.polygon(layer, (8, 12, 14), [
                    (ox + gpx * hw - gdx * hh, oy + gpy * hw - gdy * hh),
                    (ox - gpx * hw - gdx * hh, oy - gpy * hw - gdy * hh),
                    (ox - gpx * hw + gdx * hh, oy - gpy * hw + gdy * hh),
                    (ox + gpx * hw + gdx * hh, oy + gpy * hw + gdy * hh)])
                pygame.draw.polygon(layer, (34, 44, 46), [
                    (ox + gpx * (hw - 2) - gdx * (hh - 2), oy + gpy * (hw - 2) - gdy * (hh - 2)),
                    (ox - gpx * (hw - 2) - gdx * (hh - 2), oy - gpy * (hw - 2) - gdy * (hh - 2)),
                    (ox - gpx * (hw - 2) + gdx * (hh - 2), oy - gpy * (hw - 2) + gdy * (hh - 2)),
                    (ox + gpx * (hw - 2) + gdx * (hh - 2), oy + gpy * (hw - 2) + gdy * (hh - 2))])
                pygame.draw.line(layer, (132, 164, 154),
                                 (ox - gpx * 6 - gdx * 6, oy - gpy * 6 - gdy * 6),
                                 (ox + gpx * 6 - gdx * 6, oy + gpy * 6 - gdy * 6), 2)
            else:
                hl, hw2 = 8, 6
                pygame.draw.polygon(layer, (10, 12, 12), [
                    (ox + gpx * hw2 - gdx * hl, oy + gpy * hw2 - gdy * hl),
                    (ox - gpx * hw2 - gdx * hl, oy - gpy * hw2 - gdy * hl),
                    (ox - gpx * hw2 + gdx * hl, oy - gpy * hw2 + gdy * hl),
                    (ox + gpx * hw2 + gdx * hl, oy + gpy * hw2 + gdy * hl)])
                pygame.draw.polygon(layer, (20, 40, 38), [
                    (ox + gpx * (hw2 - 1) - gdx * (hl - 1), oy + gpy * (hw2 - 1) - gdy * (hl - 1)),
                    (ox - gpx * (hw2 - 1) - gdx * (hl - 1), oy - gpy * (hw2 - 1) - gdy * (hl - 1)),
                    (ox - gpx * (hw2 - 1) + gdx * (hl - 1), oy - gpy * (hw2 - 1) + gdy * (hl - 1)),
                    (ox + gpx * (hw2 - 1) + gdx * (hl - 1), oy + gpy * (hw2 - 1) + gdy * (hl - 1))])
                pygame.draw.circle(layer, (70, 145, 120), (int(ox), int(oy)), 2)

        # ── Contact shadow: grows from standing disc to body-length ──
        sh_len = int(34 + 22 * u)
        sh = pygame.Surface((sh_len + 8, 26), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 32), (0, 0, sh_len + 8, 26))
        sh_ang = self.angle + (L - self.angle) * u
        sh = pygame.transform.rotate(sh, -math.degrees(sh_ang))
        sh_off = 6 * u  # shadow slides toward the feet as the body lays out
        layer.blit(sh, (int(c - sh.get_width() / 2 + f[0] * sh_off),
                        int(c - sh.get_height() / 2 + f[1] * sh_off + 3)))

        # ── Blood ooze: pools under head/torso once the body is down ──
        lie_t = max(0.0, min(1.0, (self.t - FALL_FRAMES) / 90.0))
        ooze_c = (c - f[0] * (6 * u) , c - f[1] * (6 * u))
        ooze_rx = (4.0 + 5.0 * u) + 7.0 * lie_t
        ooze = pygame.Surface((int(ooze_rx * 2) + 4, int(ooze_rx * 1.4) + 4), pygame.SRCALPHA)
        pygame.draw.ellipse(ooze, _POOL_DARK + (170,), ooze.get_rect())
        ooze = pygame.transform.rotate(ooze, -math.degrees(L))
        layer.blit(ooze, (int(ooze_c[0] - ooze.get_width() / 2),
                          int(ooze_c[1] - ooze.get_height() / 2)))

        uniform = self.uniform_col

        # ── Legs: hidden while standing, unfold as the body goes down ──
        if u > 0.12:
            leg_w = max(1, int(5 * u))
            for side in ("l", "r"):
                pygame.draw.line(layer, uniform, P("hip_" + side), P("knee_" + side), leg_w)
                pygame.draw.line(layer, uniform, P("knee_" + side), P("foot_" + side), leg_w - 1)
                pygame.draw.circle(layer, _BOOT,
                                   (int(P("foot_" + side)[0]), int(P("foot_" + side)[1])),
                                   max(1, int(3 * u)))

        # ── Torso: shoulder→hip taper (widens slightly as it sprawls) ──
        torso_pts = [P("sh_l"), P("sh_r"), P("hip_r"), P("hip_l")]
        pygame.draw.polygon(layer, uniform, torso_pts)
        sh_mid = ((P("sh_l")[0] + P("sh_r")[0]) / 2, (P("sh_l")[1] + P("sh_r")[1]) / 2)
        hip_mid = ((P("hip_l")[0] + P("hip_r")[0]) / 2, (P("hip_l")[1] + P("hip_r")[1]) / 2)
        pygame.draw.line(layer, (uniform[0] + 12, uniform[1] + 10, uniform[2] + 8),
                         sh_mid, hip_mid, 2)  # strap/webbing line
        if self.m3_type == "breacher":
            # Armored vest stays on the body: dark plate over the torso.
            sh_l, sh_r = P("sh_l"), P("sh_r")
            hip_l, hip_r = P("hip_l"), P("hip_r")
            vo = [_lerp(sh_l, sh_r, 0.08), _lerp(sh_r, sh_l, 0.08),
                  _lerp(hip_r, sh_r, 0.20), _lerp(hip_l, sh_l, 0.20)]
            pygame.draw.polygon(layer, (12, 14, 14), vo)
            vcx = sum(q[0] for q in vo) / 4.0
            vcy = sum(q[1] for q in vo) / 4.0
            vi = [(q[0] * 0.72 + vcx * 0.28, q[1] * 0.72 + vcy * 0.28) for q in vo]
            pygame.draw.polygon(layer, (40, 45, 40), vi)
            # Red shoulder tabs.
            pygame.draw.line(layer, (150, 55, 42), sh_l,
                             _lerp(sh_l, P("elbow_a"), 0.30), 3)
            pygame.draw.line(layer, (150, 55, 42), sh_r,
                             _lerp(sh_r, P("elbow_b"), 0.30), 3)

        # ── Arms: two segments each, from gun-grip to thrown sprawl ──
        arm_w = 5 if u < 0.5 else 4
        pygame.draw.line(layer, uniform, P("sh_l"), P("elbow_a"), arm_w)
        pygame.draw.line(layer, uniform, P("elbow_a"), P("hand_a"), arm_w - 1)
        pygame.draw.line(layer, uniform, P("sh_r"), P("elbow_b"), arm_w)
        pygame.draw.line(layer, uniform, P("elbow_b"), P("hand_b"), arm_w - 1)
        pygame.draw.circle(layer, self.skin_col,
                           (int(P("hand_a")[0]), int(P("hand_a")[1])), 3)
        pygame.draw.circle(layer, self.skin_col,
                           (int(P("hand_b")[0]), int(P("hand_b")[1])), 3)
        # IPA armband on the upper arm of standard guards.
        if not self.is_commander and not self.is_mag:
            band = _lerp(P("sh_l"), P("elbow_a"), 0.45)
            pygame.draw.line(layer, C_IPA_ARMBAND,
                             (band[0] - p[0] * 3, band[1] - p[1] * 3),
                             (band[0] + p[0] * 3, band[1] + p[1] * 3), 3)

        # ── Head + headgear ──
        hx, hy = P("head")
        head_r = 8 - int(u)  # 8 standing → 7 laid out
        if self.is_commander:
            pygame.draw.circle(layer, (160, 30, 30),
                               (int(hx - f[0] * 2 * u), int(hy - f[1] * 2 * u)), head_r + 1)
        else:
            cap_col = C_MAG_BANDANA if self.is_mag else (25, 18, 14)
            pygame.draw.circle(layer, cap_col,
                               (int(hx - f[0] * 2 * u), int(hy - f[1] * 2 * u)), head_r)
        pygame.draw.circle(layer, self.skin_col, (int(hx), int(hy)), head_r - 1)
        if self.m3_type == "breacher":
            pygame.draw.line(layer, (20, 18, 16),
                             (hx - p[0] * 5, hy - p[1] * 5),
                             (hx + p[0] * 5, hy + p[1] * 5), 3)
        elif self.m3_type == "technician":
            pygame.draw.arc(layer, (80, 190, 140),
                            (int(hx - 9), int(hy - 9), 18, 18), L - 1.9, L + 1.9, 2)
            pygame.draw.circle(layer, (80, 220, 140),
                               (int(hx + p[0] * 8), int(hy + p[1] * 8)), 2)
        elif self.m3_type == "marksman":
            pygame.draw.line(layer, (120, 95, 60),
                             (hx - p[0] * 6, hy - p[1] * 6),
                             (hx + p[0] * 6, hy + p[1] * 6), 2)
        if self.is_mag:
            pygame.draw.line(layer, C_MAG_BANDANA,
                             (int(hx - f[0] * 6), int(hy - f[1] * 6)),
                             (int(hx - f[0] * 11 + p[0] * 3), int(hy - f[1] * 11 + p[1] * 3)), 2)

        # ── Ejected rifle: skids from the grip to its resting spot ──
        gun_u = _ease_out_cubic(self.t / float(FALL_FRAMES + 6))
        gx = self.gun_start[0] + (self.gun_end[0] - self.gun_start[0]) * gun_u - self.x + c
        gy = self.gun_start[1] + (self.gun_end[1] - self.gun_start[1]) * gun_u - self.y + c
        gun_ang = self.gun_angle + self.gun_spin * gun_u
        gd_x, gd_y = math.cos(gun_ang), math.sin(gun_ang)
        back = self.gun_len * 0.35
        fwd = self.gun_len * 0.55
        if self.m3_type == "marksman":
            pygame.draw.line(layer, (8, 8, 8),
                             (gx - gd_x * back, gy - gd_y * back),
                             (gx + gd_x * fwd, gy + gd_y * fwd), 5)
            pygame.draw.line(layer, (42, 40, 34),
                             (gx - gd_x * back, gy - gd_y * back),
                             (gx + gd_x * fwd, gy + gd_y * fwd), 3)
            scx = gx + gd_x * (fwd * 0.45) - gd_y * 3
            scy = gy + gd_y * (fwd * 0.45) + gd_x * 3
            pygame.draw.circle(layer, (12, 16, 16), (int(scx), int(scy)), 4)
            pygame.draw.circle(layer, (92, 150, 128), (int(scx), int(scy)), 2)
        else:
            pygame.draw.line(layer, (35, 30, 25),
                             (gx - gd_x * back, gy - gd_y * back),
                             (gx + gd_x * fwd, gy + gd_y * fwd), 3)
        pygame.draw.circle(layer, (55, 48, 40),
                           (int(gx + gd_x * fwd), int(gy + gd_y * fwd)), 2)

        layer.set_alpha(alpha)
        return layer, (int(cx - c), int(cy - c))


def spawn_corpse(enemy):
    """Create a Corpse for a just-killed Enemy and punch the kill.

    Call from the mission death funnels right before
    ``STATE.enemies.remove(e)``. The kill shake/hit-stop use the same
    max-clamp helpers as everywhere else, so a bigger in-flight effect
    (e.g. M3's shake(6), an explosion) is never truncated.
    """
    c = Corpse(enemy)
    lst = _corpses()
    lst.append(c)
    while len(lst) > MAX_CORPSES:
        lst.pop(0)
    effects.shake(SHAKE_ON_KILL)
    effects.hit_stop(HIT_STOP_ON_KILL)
    return c


def update_corpses():
    """Advance every corpse one logic tick; retire finished ones."""
    lst = _corpses()
    for c in lst[:]:
        c.update()
        if c.done:
            try:
                lst.remove(c)
            except ValueError:
                pass


def draw_corpses(surface, cam_x, cam_y):
    """Draw all corpses. Z-order: after floor decals, before living
    enemies and particles (bodies lie ON the floor, under the action)."""
    for c in _corpses():
        c.draw(surface, cam_x, cam_y)
