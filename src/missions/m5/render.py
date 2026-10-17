"""Mission 5 - part module. RENDER_SUBMIT systems (RPE6 §6.4 step 2 / §6.6, Phase 6).

``GuardRenderSystem`` turns the Presidential Guard troopers into queue drawables: the
shared contact shadow, the baked guard sprite rotated to the nearest of 64 headings
(engine ``RotationCache`` - same bucket formula as the old module cache), the two eye
dots, the raider's dome catchlight and the hit-flash ring. The pixels are exactly what
``draw._draw_m5_guard`` painted; the numbers are computed here, at submit time, in
screen space, so the legacy truncation order is preserved. Enemies that are not Guard
troopers keep their own painter (``Enemy.draw`` - a shared procedural painter, ticket
B-033) and the authored list order is kept through the sort key ``(3, index)``.

The system self-gates on the presence of ``M5Guard`` components and reads the legacy
enemy list through ``ctx`` (``STATE``) because the authored draw order *is* the list
order (ADR-017). The walk-cycle advance stays in the draw path (ADR-016 §5).
"""
from __future__ import annotations

import math

from core.config import HEIGHT, WIDTH
from engine.render2d import SCREEN, CircleDraw, CustomDraw, Layer, RotatedSpriteDraw, SurfaceDraw
from engine.world import RENDER_SUBMIT, System, Transform, WalkCycle
import game.render as _gr
import game.world as _gw
from missions.m5.components import M5Guard

__all__ = ["GuardRenderSystem", "ensure_installed", "ENEMY_KEY"]

ENEMY_KEY = 3          # authored slot of the enemies inside the entities layer (draw.submit_frame)
_GUARD_BUCKETS = 64
_GUARD_VARIANT = {"marksman": 1, "raider": 2}


def _m5art(name, variant=0):
    from missions.m5 import draw as _draw  # lazy: draw imports this module's facade siblings
    return _draw._m5art(name, variant)


def _enemy_shadow():
    from entities.enemy_ai import _enemy_shadow as _sh  # lazy: pygame surface built at import of enemy_ai
    return _sh


class GuardRenderSystem(System):
    name = "m5_guard_render"
    phase = RENDER_SUBMIT
    order = 0
    reads = (M5Guard, Transform, WalkCycle)

    def run(self, world, ctx, dt):
        if world.count(M5Guard) == 0 or not _gr.installed() or not _gr.in_frame():
            return
        q = _gr.queue()
        cam_x, cam_y = q.cam_x, q.cam_y
        enemies = getattr(ctx, "enemies", None) or ()
        for i, e in enumerate(enemies):
            g = _gw.get(e, M5Guard)
            key = (ENEMY_KEY, i)
            if g is None or not g.guard:
                q.submit(CustomDraw(lambda s, x, y, e=e: e.draw(s, x, y), "m5.enemy_draw"), Layer.ENTITIES, sort_key=key)
                continue
            self.submit_guard(q, e, g, cam_x, cam_y, key)

    @staticmethod
    def submit_guard(q, e, g, cam_x, cam_y, key):
        x = e.rect.centerx - cam_x
        y = e.rect.centery - cam_y
        if not (-50 < x < WIDTH + 50 and -50 < y < HEIGHT + 50):
            return
        kind = g.kind
        v = _GUARD_VARIANT.get(kind, 0)
        base = _m5art("m5_guard", v)
        if base is None:
            # No baked art: the procedural painter stays whole (fallback kept, R-rule), walk advance inside it.
            from missions.m5 import draw as _draw  # lazy
            q.submit(CustomDraw(lambda s, cx, cy, e=e: _draw._draw_m5_guard(s, e, cx, cy), "m5.guard_fallback"),
                     Layer.ENTITIES, sort_key=key)
            return
        a = e.angle
        dx, dy = math.cos(a), math.sin(a)
        px, py = math.cos(a + math.pi / 2), math.sin(a + math.pi / 2)
        # walk sway: same displacement-driven phase as Enemy.draw (render-driven, ADR-016 §5)
        moved = e.walk.advance(e.rect.centerx, e.rect.centery)
        ph = e.walk.phase
        sway = math.sin(ph) * 1.6 if moved > 0.4 else math.sin(ph * 0.25) * 0.5
        x += px * sway
        y += py * sway

        def L(f, sd):            # local (forward, side) -> screen
            return (x + f * dx + sd * px, y + f * dy + sd * py)

        sub = q.submit
        sub(SurfaceDraw(_enemy_shadow(), (int(x - 17), int(y - 5)), space=SCREEN), Layer.ENTITIES, sort_key=key)
        sub(RotatedSpriteDraw((int(x), int(y)), a, base=base, buckets=_GUARD_BUCKETS, key=("m5_guard", v),
                              space=SCREEN), Layer.ENTITIES, sort_key=key)
        head = L(2, 0)
        if kind == "raider":                  # dome catchlight stays upper-left (key light)
            sub(CircleDraw((int(head[0] - 3), int(head[1] - 3)), 2, (66, 68, 72), space=SCREEN), Layer.ENTITIES,
                sort_key=key)
        face = L(4, 0)
        for off in (-0.25, 0.25):
            sub(CircleDraw((int(face[0] + math.cos(a + off) * 3), int(face[1] + math.sin(a + off) * 3)), 1,
                           (40, 25, 15), space=SCREEN), Layer.ENTITIES, sort_key=key)
        if getattr(e, "hit_flash", 0) > 0 or getattr(e, "flash_timer", 0) > 0:
            sub(CircleDraw((int(head[0]), int(head[1])), 10, (255, 255, 255), 1, space=SCREEN), Layer.ENTITIES,
                sort_key=key)


def ensure_installed():
    """Register the system once per scheduler (idempotent; survives ``game.world.reset``)."""
    if not _gw.installed():
        return False
    sched = _gw.scheduler()
    if sched.find(GuardRenderSystem.name) is None:
        sched.add(GuardRenderSystem())
    return True
