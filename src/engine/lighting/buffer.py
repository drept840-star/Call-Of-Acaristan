
"""lighting.buffer - half-res light buffer: grade, motivated pools, dust (engine side).

The house style ("dark vector compositions, motivated lighting") was faked
with alpha trapezoids: hard-edged cones and flat ellipse pools. This module
replaces that with a real two-pass composite at half resolution:

1. **Grade pass** (multiplicative, RGB-only): a per-wing near-white tint that
   unifies the palette - warm sodium in the Archives, phosphor green in
   Comms, cold fluorescent in the cell block - times a gentle radial
   falloff so screen edges sit a touch darker. Near-white multipliers grade
   without crushing the existing exposure.
2. **Light pass** (additive): lamp pools, cones, CRT/LED glow and muzzle
   flashes accumulate into a half-res *opaque, premultiplied* buffer
   (black = no light), upscaled once and blitted with BLEND_ADD. Radial
   falloff lives in the RGB channels, so no alpha semantics can poison it.
3. **Dust motes**: additive 1-2 px particles whose alpha is sampled from the
   light buffer, so they only sparkle *inside* light - the trick that makes
   a cone read as volume instead of geometry.

Degrades gracefully: ``enabled()`` is False under ACA_ART=legacy/off.
"""

import math
import os
import random
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream

import pygame

# RPE6 Phase 2 (A-006): moved verbatim from core/lighting.py except for the injection points marked RPE6.
__all__ = ["LightBuffer", "enabled", "frozen"]


# Per-wing multiplicative grade (near-white, tinted).
_GRADES = (
    ("archiv", (255, 242, 220)),   # warm sodium / paper dust
    ("comms",  (228, 255, 240)),   # phosphor green spill
    ("cell",   (236, 240, 250)),   # cold fluorescent
    ("corrid", (242, 242, 246)),
    ("laundry", (228, 246, 252)),  # cold cyan
    ("yard",   (236, 240, 236)),
    ("maint",  (252, 240, 220)),   # boiler amber
    ("interrog", (238, 236, 230)),
    # Mission 1: warehouse tungsten interior vs. cool slum night exterior.
    ("warehouse", (255, 238, 210)),
    ("slums", (230, 236, 248)),
    # Mission 2: rainy Route 12 night, blast aftermath, control interior.
    ("route12", (224, 234, 248)),
    ("blackout", (206, 198, 198)),
    ("control", (255, 240, 214)),
    # Mission 4: cold sodium-off curfew night on the street, phosphor/terminal
    # green indoors at the radio station (The Aftermath).
    ("m4street", (210, 222, 240)),
    ("m4station", (222, 240, 230)),
)
_DEFAULT_GRADE = (246, 244, 242)

_RADIAL = {}
_FALL = {}   # RPE6: keyed by half-res size (was one module-level sprite for the fixed window)
_CONE = None
_TINT_CACHE = {}


def enabled():
    return os.environ.get("ACA_ART", "") not in ("legacy", "off")


def frozen():
    """ACA_FREEZE=1 pins time-driven terms for deterministic golden renders."""
    return os.environ.get("ACA_FREEZE", "") == "1"


def _radial(size):
    """Opaque black-based radial falloff (RGB = intensity), keyed by diameter."""
    s = _RADIAL.get(size)
    if s is None:
        s = pygame.Surface((size, size))
        s.fill((0, 0, 0))
        cx = cy = size // 2
        for r in range(cx, 0, -2):
            v = int(255 * (1 - r / cx) ** 2.2)
            pygame.draw.circle(s, (v, v, v), (cx, cy), r)
        _RADIAL[size] = s
    return s


def _fall_sprite(_HW, _HH):
    """Opaque grey radial: 255 at centre -> ~228 at the corners (vignette)."""
    if (_HW, _HH) not in _FALL:
        s = pygame.Surface((_HW, _HH))
        s.fill((238, 238, 238))
        cx, cy = _HW // 2, _HH // 2
        maxr = int(math.hypot(cx, cy))
        for r in range(maxr, 0, -3):
            v = 238 + int((255 - 238) * (1 - r / maxr) ** 1.4)
            pygame.draw.circle(s, (v, v, v), (cx, cy), r)
        _FALL[(_HW, _HH)] = s
    return _FALL[(_HW, _HH)]


def _cone_sprite():
    """Soft-edged light cone, 256x512, apex top-centre, RGB = intensity."""
    global _CONE
    if _CONE is None:
        s = pygame.Surface((256, 512))
        s.fill((0, 0, 0))
        pygame.draw.polygon(s, (210, 210, 210), [(128, 0), (256, 512), (0, 512)])
        grad = pygame.Surface((256, 512))
        for y in range(512):
            v = min(255, int(255 * (1 - y / 512) ** 1.6) + 12)
            pygame.draw.line(grad, (v, v, v), (0, y), (256, y))
        s.blit(grad, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        s = pygame.transform.smoothscale(s, (64, 128))
        s = pygame.transform.smoothscale(s, (256, 512))
        _CONE = s
    return _CONE


def _tinted(sprite, color, scale):
    """Colourise an intensity sprite: rgb *= color * scale (opaque out)."""
    key = (id(sprite), color, scale)
    s = _TINT_CACHE.get(key)
    if s is None:
        s = sprite.copy()
        s.fill((color[0], color[1], color[2]), special_flags=pygame.BLEND_RGB_MULT)
        if scale != 255:
            s.fill((scale, scale, scale), special_flags=pygame.BLEND_RGB_MULT)
        if len(_TINT_CACHE) > 128:
            _TINT_CACHE.clear()
        _TINT_CACHE[key] = s
    return s


class LightBuffer:
    def __init__(self, size):
        # RPE6: the target size is injected (was core.config WIDTH/HEIGHT at import)
        WIDTH, HEIGHT = self._w, self._h = int(size[0]), int(size[1])
        self._hw, self._hh = WIDTH // 2, HEIGHT // 2
        self._grade = pygame.Surface((self._hw, self._hh))
        self._add = pygame.Surface((self._hw, self._hh))
        self._vis_cache = {}
        self._doors_sig = 0
        self._motes = [(_rng_legacy.uniform(0, WIDTH), _rng_legacy.uniform(0, HEIGHT),
                        _rng_legacy.uniform(-6, 6), _rng_legacy.uniform(4, 14),
                        _rng_legacy.uniform(0.4, 1.0))
                       for _ in range(34)]
        self.wing = "default"

    @property
    def size(self):
        """Target (full-resolution) size this buffer composites onto."""
        return (self._w, self._h)

    # ── frame lifecycle ──
    def begin_frame(self, wing, doors_sig=0):
        self.wing = wing or "default"
        if doors_sig != self._doors_sig:
            self._doors_sig = doors_sig
            self._vis_cache.clear()
        grade = _DEFAULT_GRADE
        for key, g in _GRADES:
            if key in self.wing:
                grade = g
                break
        self._grade.fill(grade)
        self._grade.blit(_fall_sprite(self._hw, self._hh), (0, 0),
                         special_flags=pygame.BLEND_RGB_MULT)
        self._add.fill((0, 0, 0))

    def flicker(self, key, t, base=1.0, depth=0.12, rate=11.0):
        """Cheap per-fixture fluorescent flicker multiplier."""
        if frozen():
            return base
        seed = int(t * rate) + hash(key) % 1000
        rnd = random.Random(seed)
        v = base
        if rnd.random() < 0.16:
            v -= depth * rnd.random()
        return v

    # ── light submission (screen space; buffer is half-res) ──
    def light(self, sx, sy, radius, color, intensity=1.0, caster=None,
              cam=None, key=None):
        if intensity <= 0:
            return
        d = max(6, int(radius) // 2)          # half-res diameter
        spr = _tinted(_radial(d * 2), color, min(255, int(255 * intensity)))
        spr = pygame.transform.smoothscale(spr, (d, d))
        self._add.blit(spr, (int(sx // 2 - d // 2), int(sy // 2 - d // 2)),
                       special_flags=pygame.BLEND_ADD)
        if caster is not None and cam is not None:
            mask = self._vis_mask(key or ("l", int(sx), int(sy)), d, caster, cam)
            self._add.blit(mask, (int(sx // 2 - d // 2), int(sy // 2 - d // 2)),
                           special_flags=pygame.BLEND_RGB_MULT)

    def cone(self, sx, sy, angle, half_spread_deg, length, color,
             intensity=1.0, caster=None, cam=None, key=None):
        if intensity <= 0:
            return
        hl = max(12, int(length) // 2)        # half-res length
        spr = _cone_sprite()
        w = int(hl * math.tan(math.radians(half_spread_deg)) * 2)
        w = max(12, w)
        spr = pygame.transform.smoothscale(spr, (w, hl))
        spr = _tinted(spr, color, min(255, int(255 * intensity)))
        spr = pygame.transform.rotate(spr, -math.degrees(angle) - 90)
        r = spr.get_rect(center=(int(sx // 2), int(sy // 2)))
        self._add.blit(spr, r, special_flags=pygame.BLEND_ADD)
        if caster is not None and cam is not None:
            d = max(w, hl)
            mask = self._vis_mask(key or ("c", int(sx), int(sy)), d, caster, cam)
            self._add.blit(mask, (r.centerx - d // 2, r.centery - d // 2),
                           special_flags=pygame.BLEND_RGB_MULT)

    def _vis_mask(self, key, d, caster, cam):
        """White visibility polygon on black, half-res, d x d.

        Ray-marches RAYS angles against ``caster(world_x, world_y)`` and
        multiplies the additive buffer by it, so light stops at walls -
        real cast shadows that agree with gameplay collision.
        """
        sig = self._doors_sig
        ck = (key, sig, d)
        m = self._vis_cache.get(ck)
        if m is not None:
            return m
        RAYS = 56
        STEP = 24.0
        reach = d * 2.0                        # world px (screen == world)
        cx = cy = d / 2.0
        pts = [(cx, cy)]
        camx, camy = cam
        lx = camx + (cx * 2)                   # world pos of light centre
        ly = camy + (cy * 2)
        for i in range(RAYS):
            a = i * (2 * math.pi / RAYS)
            ca, sa = math.cos(a), math.sin(a)
            hit = reach
            t = STEP
            while t < reach:
                if caster(lx + ca * t, ly + sa * t):
                    hit = t
                    break
                t += STEP
            pts.append((cx + ca * hit / 2.0, cy + sa * hit / 2.0))
        m = pygame.Surface((d, d))
        m.fill((0, 0, 0))
        if len(pts) > 2:
            pygame.draw.polygon(m, (255, 255, 255), pts)
        if len(self._vis_cache) > 96:
            self._vis_cache.clear()
        self._vis_cache[ck] = m
        return m

    # ── composite ──
    def composite(self, target, t, motes=True):
        grade = pygame.transform.smoothscale(self._grade, (self._w, self._h))
        target.blit(grade, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        add = pygame.transform.smoothscale(self._add, (self._w, self._h))
        target.blit(add, (0, 0), special_flags=pygame.BLEND_ADD)
        if motes:
            self._draw_motes(target, 0.0 if frozen() else t, add)

    def _draw_motes(self, target, t, add):
        for i, (x, y, vx, vy, sz) in enumerate(self._motes):
            if not frozen():
                x += vx * 0.016
                y += vy * 0.016
            if x < 0 or x >= self._w or y < 0 or y >= self._h:
                x = _rng_legacy.uniform(0, self._w)
                y = _rng_legacy.uniform(0, self._h)
            lum = max(add.get_at((int(x // 2), int(y // 2)))[:3])
            self._motes[i] = (x, y, vx, vy, sz)
            if lum < 26:
                continue
            a = min(140, int(lum * 0.55))
            tw = 1.0 if frozen() else 0.7 + 0.3 * math.sin(t * 2.1 + i)
            r = 1 if sz < 0.75 else 2
            m = pygame.Surface((r * 2 + 1, r * 2 + 1), pygame.SRCALPHA)
            pygame.draw.circle(m, (255, 244, 220, int(a * tw)), (r, r), r)
            target.blit(m, (int(x - r), int(y - r)),
                        special_flags=pygame.BLEND_ADD)
