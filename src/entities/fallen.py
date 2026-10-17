
"""A fallen body for a player, drawn in the same visual language as enemies.

entities/corpse.py already solves this properly for guards: the body is not a
rotated sprite but a skeleton morphing between the top-down standing silhouette
and a full-length lying pose, so it reads as a body unfolding onto the floor.
This module applies that same approach to the player character, which is what
makes death look consistent instead of like two unrelated art systems sharing a
map.

It is deliberately parameterised by a resolved appearance palette rather than
reading any globals, for two reasons. The arena draws up to eight players who
each wear a different loadout, so there is no single "the player's colour" to
look up; and core.appearance resolves a peer's claimed identifiers into RGB at
the seat, long before anything is drawn, so nothing here has to trust a number
that arrived over a socket.

Single-player death is NOT routed through this. entities/death_anim.py owns the
campaign's cinematic sequence -- slow-motion, camera tilt and collapse, tinnitus,
radio cut -- and its fallen body is one beat inside that. Replacing it would
trade a bespoke directed sequence for a generic one, for no benefit to the
player who is watching their own story beat die.
"""
import math
import random
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream

import pygame

# Joint offsets are shared with entities/corpse.py on purpose: same shoulder
# width, same limb lengths, same torso taper. A player sprawl that used
# different proportions would sit next to enemy corpses looking like a
# different species.
_STAND = {
    "head": (2, 0),
    "sh_l": (-1, 7), "sh_r": (-1, -7),
    "elbow_a": (5, 10), "hand_a": (15, -3),
    "elbow_b": (5, -10), "hand_b": (15, 3),
    "hip_l": (-7, 4), "hip_r": (-7, -4),
    "knee_l": (-10, 4), "foot_l": (-12, 4),
    "knee_r": (-10, -4), "foot_r": (-12, -4),
}
_LIE_HEAD = (-19, 0)
_LIE_HIP_L = (2, 4)
_LIE_HIP_R = (2, -4)

# Three sprawls plus jitter, so two kills in the same fight do not look stamped
# from one mold. Mirrors the enemy pose library.
_POSES = [
    {"hand_a": (-3, 18), "elbow_a": (-9, 12),
     "hand_b": (-21, -12), "elbow_b": (-15, -8),
     "knee_l": (12, 6), "foot_l": (21, 9),
     "knee_r": (12, -4), "foot_r": (22, -7)},
    {"hand_a": (0, 7), "elbow_a": (-7, 11),
     "hand_b": (-5, -5), "elbow_b": (-11, -7),
     "knee_l": (10, 8), "foot_l": (16, 13),
     "knee_r": (14, -2), "foot_r": (20, -8)},
    {"hand_a": (-22, 9), "elbow_a": (-16, 6),
     "hand_b": (2, -16), "elbow_b": (-5, -12),
     "knee_l": (13, 3), "foot_l": (23, 4),
     "knee_r": (10, -7), "foot_r": (14, -13)},
]
_JITTERED = ("elbow_a", "hand_a", "elbow_b", "hand_b",
             "knee_l", "foot_l", "knee_r", "foot_r")

_BOOT = (18, 16, 14)
_OUTLINE = (16, 18, 22)
_POOL = (96, 12, 14)
_POOL_DARK = (54, 6, 8)


def _ease_out_cubic(t):
    t = max(0.0, min(1.0, float(t)))
    return 1.0 - (1.0 - t) ** 3


def _lerp(p0, p1, t):
    return (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t)


def _rgb(value, fallback):
    """Coerce a palette entry to a drawable 3-tuple, or fall back.

    The appearance pipeline resolves identifiers through the catalog, so in
    normal play every colour here is already a valid tuple. This exists for the
    paths that hand it something else -- a caller passing a raw dict, a stub sim
    in a tool, a palette table edited by hand. A corpse is not worth taking the
    whole frame down over, and one undrawn body beats a crashed match.
    """
    try:
        r, g, b = value[0], value[1], value[2]
        return (max(0, min(255, int(r))), max(0, min(255, int(g))),
                max(0, min(255, int(b))))
    except (TypeError, ValueError, IndexError):
        return tuple(fallback)


class FallenBody:
    """One dead body: where it fell, how it sprawled, which gun it dropped.

    Construction takes everything needed to draw without further state, because
    the arena only keeps an entity tuple per frame -- if the pose were chosen at
    draw time the corpse would re-roll its sprawl every frame and vibrate.
    """

    def __init__(self, x, y, angle, roles, head_id="head_kevlar",
         rig_name="pistol", seed=None, fall_frames=22):
        self.x = float(x)
        self.y = float(y)
        self.angle = float(angle)
        self.roles = dict(roles or {})
        self.head_id = head_id
        self.rig_name = rig_name
        # How many frames the topple takes. 22 is ~0.37s: long enough to read as
        # a body going down rather than a sprite swap, short enough that it is
        # finished well before a 3-second respawn.
        self.fall_frames = max(1, int(fall_frames))
        self.t = 0
        rng = random.Random(seed if seed is not None else _rng_legacy.randrange(1 << 30))
        # Seeded so the same death always sprawls the same way.
        self.pose = dict(_POSES[rng.randrange(len(_POSES))])
        for key in _JITTERED:
            jx, jy = self.pose[key]
            self.pose[key] = (jx + rng.uniform(-2.0, 2.0),
                              jy + rng.uniform(-2.0, 2.0))
        # The body ends up lying roughly along the facing it died pointing,
        # nudged off-axis so a kill mid-stride does not land perfectly straight.
        self.lie_angle = angle + math.pi + rng.uniform(-0.55, 0.55)
        # Feet direction: lie_angle points head->feet, and the body slides that
        # way as it goes down.
        self.slide = (math.cos(self.lie_angle), math.sin(self.lie_angle))
        self.slide_dist = rng.uniform(5.0, 9.0)
        # Detached weapon: skids out along the firing line and spins down.
        reach = 20.0
        self.gun_start = (x + math.cos(angle) * reach,
                          y + math.sin(angle) * reach)
        skid = rng.uniform(16.0, 30.0)
        drift = rng.uniform(-0.5, 0.5)
        self.gun_end = (self.gun_start[0] + math.cos(angle + drift) * skid,
                        self.gun_start[1] + math.sin(angle + drift) * skid)
        self.gun_angle = angle + rng.uniform(-1.2, 1.2)
        self.gun_spin = rng.uniform(-140.0, 140.0)
        self.t = 0

    def advance(self, frames=1):
        """Age the body. Past the topple it just lies there."""
        self.t += max(0, int(frames))

    @property
    def progress(self):
        """0..1 topple amount, eased."""
        return _ease_out_cubic(self.t / float(self.fall_frames))

    def _skeleton(self, u):
        f = (math.cos(self.lie_angle), math.sin(self.lie_angle))
        p = (math.cos(self.lie_angle + math.pi / 2),
             math.sin(self.lie_angle + math.pi / 2))

        def pt(along, perp):
            return (f[0] * along + p[0] * perp, f[1] * along + p[1] * perp)

        stand = {k: pt(*v) for k, v in _STAND.items()}
        lying = dict(stand)
        lying["head"] = pt(*_LIE_HEAD)
        lying["sh_l"] = pt(-12, 7)
        lying["sh_r"] = pt(-12, -7)
        lying["hip_l"] = pt(*_LIE_HIP_L)
        lying["hip_r"] = pt(*_LIE_HIP_R)
        for key in _JITTERED:
            lying[key] = pt(*self.pose[key])
        return {k: _lerp(stand[k], lying[k], u) for k in stand}

    def draw(self, surface, cam_x, cam_y, alpha=255):
        """Paint the body at world position minus the camera offset.

        Everything goes onto a small offscreen layer so the whole thing can fade
        with one set_alpha; procedural draw calls have no alpha argument of
        their own.
        """
        if alpha <= 0:
            return
        u = self.progress
        sx = self.x - cam_x
        sy = self.y - cam_y
        size = 132
        c = size // 2
        layer = pygame.Surface((size, size), pygame.SRCALPHA)

        cx = c + self.slide[0] * self.slide_dist * u
        cy = c + self.slide[1] * self.slide_dist * u
        J = self._skeleton(u)

        def P(j):
            return (cx + J[j][0], cy + J[j][1])

        uniform = _rgb(self.roles.get("uniform"), (60, 70, 50))
        skin = _rgb(self.roles.get("skin"), (210, 180, 140))
        helmet = _rgb(self.roles.get("helmet"), (30, 35, 28))
        rim = _rgb(self.roles.get("helmet_rim"), helmet)
        eyes = _rgb(self.roles.get("eyes"), (30, 20, 10))

        self._draw_pool(layer, (cx, cy), u)
        self._draw_gun(layer, u, c)

        # ── Legs: tucked under while standing, unfold as it goes down ──
        if u > 0.12:
            leg_w = max(1, int(5 * u))
            dark = tuple(max(0, v - 14) for v in uniform)
            for side in ("l", "r"):
                pygame.draw.line(layer, dark, P("hip_" + side),
                                 P("knee_" + side), leg_w)
                pygame.draw.line(layer, dark, P("knee_" + side),
                                 P("foot_" + side), max(1, leg_w - 1))
                pygame.draw.circle(layer, _BOOT,
                                   (int(P("foot_" + side)[0]),
                                    int(P("foot_" + side)[1])),
                                   max(1, int(3 * u)))

        # ── Torso: shoulder-to-hip taper, plus the webbing line ──
        torso = [P("sh_l"), P("sh_r"), P("hip_r"), P("hip_l")]
        pygame.draw.polygon(layer, uniform, torso)
        sh_mid = ((P("sh_l")[0] + P("sh_r")[0]) / 2.0,
                  (P("sh_l")[1] + P("sh_r")[1]) / 2.0)
        hip_mid = ((P("hip_l")[0] + P("hip_r")[0]) / 2.0,
                   (P("hip_l")[1] + P("hip_r")[1]) / 2.0)
        pygame.draw.line(layer, (uniform[0] + 12, uniform[1] + 10,
                                 uniform[2] + 8), sh_mid, hip_mid, 2)
        pygame.draw.polygon(layer, _OUTLINE, torso, 1)

        # ── Arms: two segments each, ending in skin hands ──
        arm_w = 5 if u < 0.5 else 4
        for sh, el, ha in (("sh_l", "elbow_a", "hand_a"),
                           ("sh_r", "elbow_b", "hand_b")):
            pygame.draw.line(layer, uniform, P(sh), P(el), arm_w)
            pygame.draw.line(layer, uniform, P(el), P(ha), max(1, arm_w - 1))
            pygame.draw.circle(layer, skin, (int(P(ha)[0]), int(P(ha)[1])), 3)

        self._draw_head(layer, P("head"), u, helmet, rim, skin, eyes)

        if alpha >= 255:
            surface.blit(layer, (int(sx - c), int(sy - c)))
        else:
            layer.set_alpha(max(0, min(255, int(alpha))))
            surface.blit(layer, (int(sx - c), int(sy - c)))

    def _draw_head(self, layer, pos, u, helmet, rim, skin, eyes):
        """Head plus whatever the loadout was actually wearing.

        The gear is the point of routing colours through here: a player who
        bought goggles should die wearing goggles. Headgear is drawn as a cap
        over the skull circle, then the face is punched back in, which is how
        the enemy corpses do it and keeps the two readable at the same zoom.
        """
        hx, hy = pos
        f = (math.cos(self.lie_angle), math.sin(self.lie_angle))
        r = 8 - int(u)
        # Shell/cover pushed toward the crown as the head settles.
        gx, gy = hx - f[0] * 2 * u, hy - f[1] * 2 * u
        head_id = self.head_id
        if head_id == "head_beret":
            pygame.draw.circle(layer, rim, (int(gx), int(gy)), r + 1)
        elif head_id == "head_peaked_cap":
            pygame.draw.circle(layer, helmet, (int(gx), int(gy)), r)
            pygame.draw.line(layer, rim, (gx - 6, gy - 3), (gx + 6, gy + 3), 3)
        elif head_id == "head_balaclava":
            pygame.draw.circle(layer, helmet, (int(gx), int(gy)), r)
        elif head_id == "head_heavy_helmet":
            pygame.draw.circle(layer, helmet, (int(gx), int(gy)), r + 2)
            pygame.draw.circle(layer, rim, (int(gx), int(gy)), r + 2, 2)
        else:                                     # kevlar and unknown ids
            pygame.draw.circle(layer, helmet, (int(gx), int(gy)), r)
            pygame.draw.arc(layer, rim, (int(gx - r), int(gy - r), r * 2, r * 2),
                            self.lie_angle - 0.9, self.lie_angle + 0.9, 2)
        pygame.draw.circle(layer, skin, (int(hx), int(hy)), max(1, r - 1))
        if head_id == "head_goggles":
            p = (math.cos(self.lie_angle + math.pi / 2),
                 math.sin(self.lie_angle + math.pi / 2))
            pygame.draw.line(layer, (96, 158, 196),
                             (hx - p[0] * 5, hy - p[1] * 5),
                             (hx + p[0] * 5, hy + p[1] * 5), 3)
        elif head_id != "head_balaclava":
            # Bare eyes only when nothing is covering the face.
            pygame.draw.circle(layer, eyes, (int(hx), int(hy)), 2)

    def _draw_gun(self, layer, u, c):
        """The equipped weapon, skidding and spinning to rest.

        Uses the real rig colours from the resolved finish, so a gold K-9 drops
        a gold K-9. Geometry is a compact silhouette rather than the full
        Player.draw rig because that rig needs an arm context this scene does
        not have -- but the palette is genuinely the gun it was holding.
        """
        gun_u = _ease_out_cubic(self.t / float(self.fall_frames + 6))
        gx = (self.gun_start[0] + (self.gun_end[0] - self.gun_start[0]) * gun_u
              - self.x + c)
        gy = (self.gun_start[1] + (self.gun_end[1] - self.gun_start[1]) * gun_u
              - self.y + c)
        ang = self.gun_angle + math.radians(self.gun_spin * gun_u)
        rig = self.rig_name
        # Guarded as a lookup, not just a default: `or {}` would let a non-dict
        # "rigs" value through and blow up one line later on .get().
        roles = self.roles if isinstance(self.roles, dict) else {}
        table = roles.get("rigs")
        table = table if isinstance(table, dict) else {}
        colors = table.get({"os12": "os12", "k9_smg": "k9",
                            "pistol": "pistol"}.get(rig, "pistol")) or {}
        if not isinstance(colors, dict):
            colors = {}
        body = colors.get("receiver") or colors.get("frame") or (38, 36, 32)
        edge = colors.get("cover_edge") or colors.get("slide_edge") or (18, 18, 20)
        accent = colors.get("wood") or colors.get("can") or body
        if rig == "os12":
            length, thick = 34, 4
        elif rig == "k9_smg":
            length, thick = 22, 4
        else:
            length, thick = 14, 3
        d = (math.cos(ang), math.sin(ang))
        p = (-d[1], d[0])
        rear = -length * 0.35
        fwd = length * 0.55
        pts = [(gx + d[0] * rear + p[0] * thick, gy + d[1] * rear + p[1] * thick),
               (gx + d[0] * fwd + p[0] * (thick - 1), gy + d[1] * fwd + p[1] * (thick - 1)),
               (gx + d[0] * fwd - p[0] * (thick - 1), gy + d[1] * fwd - p[1] * (thick - 1)),
               (gx + d[0] * rear - p[0] * thick, gy + d[1] * rear - p[1] * thick)]
        pygame.draw.polygon(layer, body, pts)
        pygame.draw.polygon(layer, edge, pts, 1)
        # Furniture / muzzle device in the second colour so the drop reads as
        # the same gun and not a grey stick.
        pygame.draw.line(layer, accent,
                         (gx + d[0] * rear * 0.9, gy + d[1] * rear * 0.9),
                         (gx + d[0] * rear * 0.2, gy + d[1] * rear * 0.2),
                         max(1, thick - 1))

    def _draw_pool(self, layer, center, u):
        """Blood spreading under the body once it has landed.

        Sized to sit UNDER the body rather than around it. The first pass grew
        to a 72px blob that swallowed the whole silhouette -- a puddle with a
        person beside it. Enemy kills bleed onto mission-layer decals, so this
        only has to suggest the pool at rest scale.
        """
        grow = max(0.0, (self.t - self.fall_frames * 0.5) / float(self.fall_frames * 2))
        if grow <= 0:
            return
        grow = min(1.0, grow) ** 0.7          # spreads fast, then stops
        rx = 6 + 14 * grow
        ry = 4 + 8 * grow
        pool = pygame.Surface((int(rx * 2 + 6), int(ry * 2 + 6)), pygame.SRCALPHA)
        pygame.draw.ellipse(pool, _POOL + (115,), pool.get_rect())
        pygame.draw.ellipse(pool, _POOL_DARK + (90,),
                            pool.get_rect().inflate(-6, -5))
        px, py = center
        layer.blit(pool, (int(px - pool.get_width() / 2),
                          int(py - pool.get_height() / 2 + 3)))
