"""Drawable adapters for shared legacy classes (RPE6 Phase 6, ADR-017).

Each builder returns the *same pixels* as the legacy painter it mirrors - the numbers are
computed exactly like the legacy call site, in screen space, and the engine primitives pass
them through untouched (truncation rule). Legacy painters stay in place for the missions that
still paint directly; ``tests/unit/test_render_adapters.py`` pins pixel equivalence.

Builders are generators of ``(drawable)``; the caller picks layer and sort key.
"""
from __future__ import annotations

from engine.render2d import SCREEN, CircleDraw, LineDraw, PolyDraw, RectDraw, SurfaceDraw

__all__ = ["particle_drawables", "casing_drawables", "bullet_drawables", "corpse_drawables"]

_CASING_FILL = (190, 155, 70)
_CASING_EDGE = (140, 110, 40)
_TRAIL = (255, 220, 140)


def particle_drawables(particles, cam_x, cam_y):
    """Mirror of ``core.config.Particle.draw``: one rect per live particle."""
    for p in particles:
        if p.life > 0:
            yield RectDraw((p.x - cam_x, p.y - cam_y, p.size, p.size), p.color, space=SCREEN)


def casing_drawables(casings, cam_x, cam_y):
    """Mirror of ``core.config.Casing.draw``: rotated brass quad, fill then 1px edge."""
    import math
    for c in casings:
        if c.life <= 0:
            continue
        sx, sy = c.x - cam_x, c.y - cam_y
        hw, hh = c.CASING_W / 2, c.CASING_H / 2
        ca, sa = math.cos(c.rot), math.sin(c.rot)
        corners = []
        for lx, ly in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
            corners.append((sx + lx * ca - ly * sa, sy + lx * sa + ly * ca))
        yield PolyDraw(corners, _CASING_FILL, space=SCREEN)
        yield PolyDraw(corners, _CASING_EDGE, 1, space=SCREEN)


def bullet_drawables(bullets, cam_x, cam_y, glow, core_color, with_glow=True):
    """Mirror of ``core.camera.draw_bullets``: glow halo, 2px core, trail to the previous position."""
    for b in bullets:
        bx = int(b["x"] - cam_x)
        by = int(b["y"] - cam_y)
        if with_glow:
            yield SurfaceDraw(glow, (bx - 8, by - 8), space=SCREEN)
        yield CircleDraw((bx, by), 2, core_color, space=SCREEN)
        prev_x = b.get("prev_x", b["x"] - b["dx"]) - cam_x
        prev_y = b.get("prev_y", b["y"] - b["dy"]) - cam_y
        yield LineDraw([(bx, by), (prev_x, prev_y)], _TRAIL, 2, space=SCREEN)


def corpse_drawables(corpses, cam_x, cam_y):
    """One ``SurfaceDraw`` per visible corpse (``Corpse.render`` paints the faded body layer)."""
    for c in corpses:
        r = c.render(cam_x, cam_y)
        if r is not None:
            yield SurfaceDraw(r[0], r[1], space=SCREEN)
