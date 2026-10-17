
"""art_cache.py - Centralized procedural surface cache for Call of Acaristan.

Pre-renders procedural surfaces once and returns cached ``pygame.Surface``
objects via getter functions. This eliminates the repeated per-frame
``pygame.Surface()`` + ``pygame.draw.*`` creation found across mission.py,
mission2.py, mission3.py, ui_hud.py, weapons.py, and death_anim.py.

All cached surfaces call ``.convert_alpha()`` for fast blitting (guarded
against the case where the display isn't initialized yet). Surfaces are
built lazily on first request and stored in module-level dict caches,
matching the ``_scaled_mouse_cache`` pattern from config.py.

Usage example::

    from entities.art_cache import get_blood_decal, get_panel_bg

    # Instead of creating a new Surface every frame:
    #   d_surf = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
    #   pygame.draw.circle(d_surf, (130,10,10,255), (r, r), r)
    #   d_surf.set_alpha(int(decal_alpha))
    #   screen.blit(d_surf, ...)
    # Just do:
    decal = get_blood_decal(r)
    decal.set_alpha(int(decal_alpha))
    screen.blit(decal, ...)

After a display-mode change (e.g. toggling fullscreen), call
``rebuild_caches()`` to discard stale surfaces that were converted against
the old pixel format.
"""

import math
import random

import pygame
from core.config import (HEIGHT, WIDTH)

# ── Cache registries ──

_blood_decals = {}
_panels = {}
_plate_bgs = {}
_labels = {}
_glows = {}
_overlays = {}
_shadows = {}
_fire_scorch = {}
_fire_glow = {}
_singletons = {}
_tinnitus_bars = {}


def rebuild_caches():
    """Clear ALL surface caches.

    Call this after a display-mode change (fullscreen toggle, resolution
    change, etc.) so that surfaces are re-built and ``.convert_alpha()``
    against the new pixel format. Without this, cached surfaces created
    against the old display format can cause slow blits or visual glitches.
    """
    _blood_decals.clear()
    _panels.clear()
    _labels.clear()
    _glows.clear()
    _overlays.clear()
    _shadows.clear()
    _fire_scorch.clear()
    _fire_glow.clear()
    _singletons.clear()
    _tinnitus_bars.clear()


def _safe_convert_alpha(surf):
    """``convert_alpha()`` that gracefully handles no display yet.

    config.py builds surfaces at import time assuming the display is ready
    (it calls ``pygame.init()`` and ``set_mode()`` before any factory runs).
    This guard mirrors that assumption but provides a fallback so that
    importing art_cache before display init doesn't crash.
    """
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        return surf.convert_alpha()
    return surf


# ── Blood decals ──

def get_blood_decal(radius):
    """Return a cached blood decal surface for the given radius.

    Builds a filled dark-red circle on a transparent ``(radius*2)`` square,
    matching the blood decal style used across mission.py, mission2.py,
    and mission3.py.

    Callers apply per-frame alpha fade via ``surf.set_alpha(int(decal_alpha))``.
    The cached surface is built at full alpha (255) so ``set_alpha()`` maps
    directly to the original per-pixel alpha value.
    """
    if radius not in _blood_decals:
        surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (130, 10, 10, 255), (radius, radius), radius)
        _blood_decals[radius] = _safe_convert_alpha(surf)
    return _blood_decals[radius]


# ── HUD panel backgrounds ──

def get_panel_bg(w, h, alpha=150, border_radius=4, border_col=(40, 42, 38)):
    """Return a cached HUD panel background surface.

    Matches the panel styling used across mission2.py:10117-10120 and
    mission3.py:2220-2223: a semi-transparent black fill with a thin
    1-pixel border and rounded corners.
    """
    key = (w, h, alpha, border_radius, border_col)
    if key not in _panels:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (0, 0, 0, alpha), (0, 0, w, h),
                         border_radius=border_radius)
        pygame.draw.rect(surf, border_col, (0, 0, w, h), 1,
                         border_radius=border_radius)
        _panels[key] = _safe_convert_alpha(surf)
    return _panels[key]


def get_plate_bg(w, h):
    """Return a cached "status plate" backdrop (dark glass + steel rim).

    The chrome of the M4 hold clock and the M5 status plate - and of the baked
    frame in ``src/art/m5/plate.py``, which both must keep matching: fill
    (8, 10, 14, 210), 1px rim (150, 170, 190, 220), 6px radius.
    """
    key = (w, h)
    if key not in _plate_bgs:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (8, 10, 14, 210), (0, 0, w, h), border_radius=6)
        pygame.draw.rect(surf, (150, 170, 190, 220), (0, 0, w, h), 1,
                         border_radius=6)
        _plate_bgs[key] = _safe_convert_alpha(surf)
    return _plate_bgs[key]


# ── Text labels ──

def get_label(text, font, color):
    """Return a cached rendered text label.

    Calls ``font.render(text, True, color)`` once and caches the result.
    Avoids per-frame ``font.render`` for common strings like "CMDR", "MAG",
    "HP", "HOSTILES:", "DESK", "BAY DOOR", "[E]".

    The cache key uses ``id(font)`` because Font objects are not hashable.
    """
    key = (text, id(font), color)
    if key not in _labels:
        surf = font.render(text, True, color)
        _labels[key] = _safe_convert_alpha(surf)
    return _labels[key]


# ── Radial glow ──

def get_glow(radius, color, alpha=255):
    """Return a cached radial glow surface.

    Builds a soft radial gradient by drawing concentric circles with
    increasing alpha toward the center, matching the glow style used for
    breach markers (mission.py:1768-1775) and pickup glows
    (mission.py:2010-2017).

    Callers can apply ``set_alpha()`` for per-frame pulsing.
    """
    key = (radius, color, alpha)
    if key not in _glows:
        size = radius * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx = cy = radius
        # Draw concentric circles from the outside in, increasing alpha
        # toward the center (quadratic falloff - matches muzzle flash style
        # from config.py:425-437).
        for r in range(radius, 0, -1):
            t = 1.0 - (r / max(radius, 1))
            a = int(alpha * t * t)
            if a > 0:
                pygame.draw.circle(surf, (*color[:3], min(255, a)),
                                   (cx, cy), r)
        _glows[key] = _safe_convert_alpha(surf)
    return _glows[key]


# ── Full-screen overlays ──

def get_fullscreen_overlay(color):
    """Return a cached full-screen overlay surface of the given color.

    Builds a ``(WIDTH, HEIGHT)`` SRCALPHA surface filled with ``color``.
    Callers apply fade via ``set_alpha()``. Replaces per-frame
    ``pygame.Surface((WIDTH, HEIGHT), SRCALPHA)`` creation for GC flash
    (mission3.py:2722-2724), tinnitus gray/red
    (mission2.py:7208-7213), and breach flicker overlays.
    """
    if color not in _overlays:
        surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        surf.fill(color)
        _overlays[color] = _safe_convert_alpha(surf)
    return _overlays[color]


# ── Fire zone surfaces ──

def get_firezone_glow(radius):
    """Return a cached fire-zone glow surface.

    Replicates the low orange glow from ``FireZone.draw()`` in weapons.py
    (lines 119-136): three concentric ellipses with increasing alpha toward
    the center, drawn on a ``(radius*3, radius*2)`` surface.

    Built at full life_ratio (1.0) and flicker (1.0). Callers can apply
    ``set_alpha(int(255 * life_ratio * flicker))`` to scale the glow.
    """
    if radius not in _fire_glow:
        surf = pygame.Surface((radius * 3, radius * 2), pygame.SRCALPHA)
        for r, a in [
            (radius + 25, 24),
            (radius, 40),
            (radius - 20, 65),
        ]:
            if r > 0:
                pygame.draw.ellipse(
                    surf,
                    (255, 95, 20, a),
                    (
                        radius * 3 // 2 - r,
                        radius - int(r * 0.45),
                        r * 2,
                        int(r * 0.9),
                    ),
                )
        _fire_glow[radius] = _safe_convert_alpha(surf)
    return _fire_glow[radius]


def get_firezone_scorch(x, y, radius):
    """Return a cached fire-zone scorch surface.

    Replicates the scorched ground patch from ``FireZone.draw()`` in
    weapons.py (lines 107-117): a seeded irregular polygon using
    ``random.Random(int(x * 13 + y * 7))`` to produce 18 points around a
    circle, drawn on a ``(radius*3, radius*3)`` surface.

    The cache key is ``(x, y, radius)`` so each fire zone gets a unique
    but deterministic shape. Built at full life_ratio (1.0); callers can
    apply ``set_alpha(int(255 * life_ratio))`` to fade the scorch.
    """
    key = (x, y, radius)
    if key not in _fire_scorch:
        surf = pygame.Surface((radius * 3, radius * 3), pygame.SRCALPHA)
        cx = cy = radius * 3 // 2
        rng = random.Random(int(x * 13 + y * 7))
        points = []
        for i in range(18):
            ang = i / 18.0 * math.pi * 2
            rr = radius * rng.uniform(0.75, 1.25)
            points.append((cx + math.cos(ang) * rr,
                           cy + math.sin(ang) * rr * 0.72))
        pygame.draw.polygon(surf, (10, 7, 5, 115), points)
        pygame.draw.polygon(surf, (45, 22, 8, 80), points, 2)
        _fire_scorch[key] = _safe_convert_alpha(surf)
    return _fire_scorch[key]


# ── Death animation ──

def get_fallen_body_surface():
    """Return a cached fallen-body silhouette surface.

    Replicates the body drawing from ``_draw_fallen_body()`` in
    death_anim.py (lines 403-456): a 40x56 surface with splayed arms,
    torso, vest detail, legs, and head. Colors match the player's in-game
    appearance (C_PLAYER_UNIFORM / C_PLAYER_SKIN).

    Callers apply ``pygame.transform.rotate`` per frame for the death
    rotation, and blit a shadow underneath (use ``get_shadow()``).
    """
    if 'fallen_body' not in _singletons:
        # Late import - colors may not exist at module load (matches
        # death_anim.py:385 pattern).
        from core.config import C_PLAYER_UNIFORM, C_PLAYER_SKIN

        BODY_W, BODY_H = 28, 44
        pad = 6
        surf = pygame.Surface((BODY_W + pad * 2, BODY_H + pad * 2),
                              pygame.SRCALPHA)
        cx_local = (BODY_W + pad * 2) // 2
        cy_local = (BODY_H + pad * 2) // 2

        body_col = C_PLAYER_UNIFORM
        skin_col = C_PLAYER_SKIN
        outline_col = (20, 22, 28)

        # Splayed arms (both arms out at ~45 deg from the torso).
        arm_col = body_col
        # Left arm
        pygame.draw.line(surf, arm_col,
                         (cx_local - 4, cy_local - 8),
                         (cx_local - 14, cy_local + 4), 5)
        # Right arm
        pygame.draw.line(surf, arm_col,
                         (cx_local + 4, cy_local - 8),
                         (cx_local + 14, cy_local + 4), 5)
        # Hands (small skin-colored circles at the ends)
        pygame.draw.circle(surf, skin_col, (cx_local - 14, cy_local + 4), 3)
        pygame.draw.circle(surf, skin_col, (cx_local + 14, cy_local + 4), 3)

        # Torso - rounded rectangle, slightly tapered toward the waist.
        pygame.draw.rect(surf, body_col,
                         (cx_local - 7, cy_local - 10, 14, 22),
                         border_radius=4)
        # Vest detail (slightly darker strip down the center).
        vest_col = tuple(max(0, c - 25) for c in body_col)
        pygame.draw.rect(surf, vest_col,
                         (cx_local - 3, cy_local - 8, 6, 18),
                         border_radius=2)

        # Legs - splayed slightly, feet apart.
        leg_col = tuple(max(0, c - 15) for c in body_col)
        # Left leg
        pygame.draw.rect(surf, leg_col,
                         (cx_local - 6, cy_local + 10, 4, 14),
                         border_radius=1)
        # Right leg
        pygame.draw.rect(surf, leg_col,
                         (cx_local + 2, cy_local + 10, 4, 14),
                         border_radius=1)

        # Head - skin-colored circle on top.
        pygame.draw.circle(surf, skin_col, (cx_local, cy_local - 14), 6)
        # Head shadow / outline
        pygame.draw.circle(surf, outline_col, (cx_local, cy_local - 14), 6, 1)

        # Outline the whole silhouette.
        pygame.draw.rect(surf, outline_col,
                         (cx_local - 7, cy_local - 10, 14, 22),
                         1, border_radius=4)

        _singletons['fallen_body'] = _safe_convert_alpha(surf)
    return _singletons['fallen_body']


def get_dropped_weapon_surface(weapon_type):
    """Return a cached dropped-weapon sprite surface.

    Replicates the weapon silhouette from ``_draw_dropped_weapon()`` in
    death_anim.py (lines 356-372). Each weapon type (e.g. "os12", "pistol")
    gets its own cached surface with receiver body, top cover highlight,
    dark outline, and magazine nub.

    Callers apply ``pygame.transform.rotate`` per frame and blit a shadow
    underneath (use ``get_shadow()``).
    """
    key = ('dropped_weapon', weapon_type)
    if key not in _singletons:
        if weapon_type == "os12":
            w, h = 36, 10
            col = (38, 36, 32)
            detail = (58, 56, 52)
        else:
            w, h = 22, 8
            col = (45, 42, 38)
            detail = (70, 65, 58)

        surf = pygame.Surface((w + 4, h + 4), pygame.SRCALPHA)
        # Receiver body.
        pygame.draw.rect(surf, col, (2, 2, w, h), border_radius=2)
        # Top cover / slide highlight.
        pygame.draw.rect(surf, detail, (3, 3, w - 2, h - 3), border_radius=1)
        # Dark outline.
        pygame.draw.rect(surf, (20, 18, 16), (2, 2, w, h), 1, border_radius=2)
        # Magazine (small nub on the underside).
        pygame.draw.rect(surf, (28, 26, 24), (w // 2 - 1, h, 3, 4))

        _singletons[key] = _safe_convert_alpha(surf)
    return _singletons[key]


# ── Generic shadows ──

def get_shadow(w, h, shape='ellipse', alpha=80):
    """Return a cached generic shadow surface.

    Builds a simple shadow on a ``(w, h)`` transparent surface.
    For ``shape='ellipse'`` draws a filled ellipse (matching player_shadow
    and bottle shadows in config.py:678-679 / mission.py:1908-1910).
    For ``shape='rect'`` draws a filled rectangle (matching wall_shadow and
    bay_door_shadow in config.py:671-677 / effects.py:17-29).
    """
    key = (w, h, shape, alpha)
    if key not in _shadows:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        if shape == 'ellipse':
            pygame.draw.ellipse(surf, (0, 0, 0, alpha), (0, 0, w, h))
        elif shape == 'rect':
            pygame.draw.rect(surf, (0, 0, 0, alpha), (0, 0, w, h))
        _shadows[key] = _safe_convert_alpha(surf)
    return _shadows[key]


# ── Tinnitus bars ──

def get_tinnitus_bar(width):
    """Return a cached tinnitus jitter bar surface.

    Replicates the scanline jitter bar from ``_draw_tinnitus_overlay()``
    in mission2.py (line 7217): a ``(width, 3)`` surface filled with a
    warm white at low alpha.

    Callers apply per-frame strength via ``set_alpha(int(255 * strength))``
    to scale the bar's visibility.
    """
    if width not in _tinnitus_bars:
        surf = pygame.Surface((width, 3), pygame.SRCALPHA)
        surf.fill((255, 245, 220, 22))
        _tinnitus_bars[width] = _safe_convert_alpha(surf)
    return _tinnitus_bars[width]
