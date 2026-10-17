
"""render2d.util - shared gameplay-render helpers (engine side).

Promoted from missions/m3/draw.py during the Mission 1/2 graphics upgrade.
Mission 3 wired the static-bake + half-res lighting pipeline with a handful
of small mission-agnostic helpers (screen culling, lamp-table submission,
bake screen-swap, door-animation signature); Missions 1 and 2 use the same
pipeline now, so the helpers live here and all three missions call them.
"""

# RPE6 Phase 2 (A-006): moved verbatim from core/render_util.py except for the injection points marked RPE6.

__all__ = ["screen_visible", "swap_screen", "doors_anim_sig", "push_lamps", "soft_shadow", "soft_shadow_surface", "add_radial"]


def screen_visible(sx, sy, w, h, margin=80, viewport=None):
    """True when the rect (sx, sy, w, h) can intersect the screen.

    ``viewport`` = (width, height) of the target (RPE6: injected, was core.config).
    """
    vw, vh = viewport
    return not (sx > vw + margin or sx + w < -margin
                or sy > vh + margin or sy + h < -margin)


def swap_screen(module_namespace, surf, fn):
    """Run ``fn()`` with ``module_namespace["screen"]`` set to ``surf``.

    Bake callbacks for :mod:`core.staticlayer` need the mission's existing
    screen-space draw code (which blits to the module-global ``screen``)
    to land on the chunk surface instead. The swap is exception-safe and
    restores the previous surface afterwards.
    """
    old = module_namespace.get("screen")
    module_namespace["screen"] = surf
    try:
        fn()
    finally:
        module_namespace["screen"] = old


def doors_anim_sig(doors):
    """Cheap light-cache signature over a mission's animating doors.

    Matches the Mission 3 formula: the summed open-progress is quantised so
    the lighting visibility cache only invalidates while a door is actually
    moving, not every frame.
    """
    try:
        return int(sum(getattr(d, "anim_progress", 0.0) for d in doors) * 4)
    except TypeError:
        return 0


def push_lamps(lb, lamps, cam_x, cam_y, t, caster, key_filter=None,
               base=0.30, radius_scale=0.8, key_fn=None):
    """Submit a lamp table to a :class:`core.lighting.LightBuffer`.

    ``lamps`` yields ``(world_x, world_y, radius, color, key)`` tuples.
    Each lamp is culled against the screen, then submitted with per-fixture
    fluorescent flicker and an optional shadow-casting ``caster`` predicate
    plus ``(cam_x, cam_y)`` camera (both forwarded to ``lb.light``).

    ``key_filter(key)`` drops lamps that do not belong to the active map
    (Mission 3 routes lamp families per stage; Missions 1/2 gate event
    lamps such as the tanker worklight the same way). ``key_fn(wx, wy)``
    overrides the visibility-cache key, defaulting to the world position.
    """
    cam = (cam_x, cam_y)
    for wx, wy, r, col, key in lamps:
        if key_filter is not None and not key_filter(key):
            continue
        sx = wx - cam_x
        sy = wy - cam_y
        if not screen_visible(sx, sy, 1, 1, viewport=lb.size):   # RPE6: the buffer knows its target size
            continue
        lb.light(sx, sy, int(r * radius_scale), col,
                 base * lb.flicker(key, t),
                 caster=caster, cam=cam,
                 key=key_fn(wx, wy) if key_fn is not None else ("lamp", wx, wy))


def soft_shadow(surf, rect, alpha=70):
    """Contact shadow that stays soft on opaque surfaces.

    Per-pixel alpha drawn directly onto an opaque surface is discarded, so
    ``draw.ellipse(surf, (0, 0, 0, a), rect)`` bakes as a SOLID black blob.
    Draw into a small SRCALPHA temp and blit instead.
    """
    made = soft_shadow_surface(rect, alpha)
    if made is not None:
        surf.blit(made[0], made[1])


def soft_shadow_surface(rect, alpha=70):
    """The ``soft_shadow`` ellipse as ``(surface, topleft)`` for queue submission; ``None`` if empty."""
    import pygame
    r = pygame.Rect(rect)
    if r.w <= 0 or r.h <= 0:
        return None
    a = max(0, min(255, int(alpha)))
    t = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
    pygame.draw.ellipse(t, (0, 0, 0, a), (0, 0, r.w, r.h))
    return t, r.topleft


_RADIAL_ADD_CACHE = {}


def add_radial(surf, cx, cy, radius, color, intensity=255):
    """Additive soft light pool (premultiplied, so BLEND_ADD stays soft).

    ``get_glow`` sprites carry their falloff in the ALPHA channel, which
    BLEND_ADD/BLEND_RGBA_ADD ignore - blitting them additively produces a
    hard bright disc.  This builds an opaque radial whose RGB *is* the
    falloff (same trick as core.lighting) and adds it.
    """
    import pygame
    key = (radius, color)
    spr = _RADIAL_ADD_CACHE.get(key)
    if spr is None:
        d = radius * 2
        spr = pygame.Surface((d, d))
        spr.fill((0, 0, 0))
        for r in range(radius, 0, -1):
            v = (1 - r / radius) ** 2.0
            pygame.draw.circle(
                spr, (int(color[0] * v), int(color[1] * v), int(color[2] * v)),
                (radius, radius), r)
        _RADIAL_ADD_CACHE[key] = spr
    if intensity != 255:
        spr = spr.copy()
        spr.fill((intensity, intensity, intensity),
                 special_flags=pygame.BLEND_RGB_MULT)
    surf.blit(spr, (int(cx - radius), int(cy - radius)),
              special_flags=pygame.BLEND_ADD)
