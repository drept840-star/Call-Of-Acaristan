"""render2d.camera - Camera2D: follow, dead-zone, look-ahead, bounds, trauma shake, zoom (RPE6 §6.6).

The camera owns a *world-space top-left* (``x``, ``y``) for a viewport of
``width × height``. ``follow(...)`` moves it toward a target with an ease factor,
dead-zone and optional look-ahead; ``bounds`` clamps it to the level; ``shake`` is
a trauma model (``trauma²`` × amplitude, decaying per step) fed from a named rng
stream passed in by the caller - the engine never touches the global ``random``.

``offset(alpha)`` is what a renderer uses: the integer camera for this frame,
interpolated between the previous and current step by ``alpha`` and including the
shake kick. ``world_to_screen`` / ``screen_to_world`` use the same offset so
picking and drawing agree.
"""
from __future__ import annotations

import math
from typing import Any

__all__ = ["Camera2D", "clamp_top_left", "deadzone_hold", "ease_toward", "legacy_shake"]


# ── follow math (Phase 6, P6-M4): one implementation shared by Camera2D and the legacy
#    camera module, which still owns the game's camera state until the Phase 7 flip ───────
def clamp_top_left(x, y, world_w, world_h, view_w, view_h):
    """Clamp a camera top-left into ``[0, world - view]`` (never negative bounds)."""
    max_x = max(0, world_w - view_w)
    max_y = max(0, world_h - view_h)
    return max(0, min(max_x, x)), max(0, min(max_y, y))


def deadzone_hold(cur_x, cur_y, desired_x, desired_y, deadzone_px):
    """Per-axis hold: while the desired position stays within ``deadzone_px`` the axis keeps its value."""
    if deadzone_px > 0:
        if abs(desired_x - cur_x) < deadzone_px:
            desired_x = cur_x
        if abs(desired_y - cur_y) < deadzone_px:
            desired_y = cur_y
    return desired_x, desired_y


def ease_toward(cur_x, cur_y, desired_x, desired_y, ease):
    """One frame of linear ease toward the desired position."""
    return cur_x + (desired_x - cur_x) * ease, cur_y + (desired_y - cur_y) * ease


def legacy_shake(shake, rng):
    """Max-clamp shake: two ``randint(-shake, shake)`` draws (x then y) from the given rng stream."""
    return rng.randint(-shake, shake), rng.randint(-shake, shake)


class Camera2D:
    def __init__(self, width: int, height: int, *, x: float = 0.0, y: float = 0.0, bounds: Any = None,
                 deadzone: tuple[float, float] = (0.0, 0.0), ease: float = 1.0, lookahead: float = 0.0,
                 zoom: float = 1.0, shake_amp: float = 8.0, trauma_decay: float = 0.04,
                 rng: Any = None) -> None:
        self.width, self.height = int(width), int(height)
        self.x, self.y = float(x), float(y)
        self.prev_x, self.prev_y = float(x), float(y)
        self.bounds = bounds            # (w, h) world size or (x, y, w, h); None = unbounded
        self.deadzone = (float(deadzone[0]), float(deadzone[1]))
        self.ease = float(ease)
        self.lookahead = float(lookahead)
        self.zoom = float(zoom)
        self.shake_amp = float(shake_amp)
        self.trauma = 0.0
        self.trauma_decay = float(trauma_decay)
        self.rng = rng
        self.kick_x = 0.0
        self.kick_y = 0.0

    # ── placement ──────────────────────────────────────────────────────────
    def center(self) -> tuple[float, float]:
        return self.x + self.width / (2 * self.zoom), self.y + self.height / (2 * self.zoom)

    def snap(self, cx: float, cy: float) -> None:
        """Centre on (cx, cy) immediately (level start, checkpoint)."""
        self.x = cx - self.width / (2 * self.zoom)
        self.y = cy - self.height / (2 * self.zoom)
        self._clamp()
        self.prev_x, self.prev_y = self.x, self.y

    def follow(self, tx: float, ty: float, *, aim_angle: float | None = None, ease: float | None = None) -> None:
        """One step toward the target: dead-zone, look-ahead along ``aim_angle``, ease, bounds."""
        self.prev_x, self.prev_y = self.x, self.y
        if aim_angle is not None and self.lookahead:
            tx += math.cos(aim_angle) * self.lookahead
            ty += math.sin(aim_angle) * self.lookahead
        cx, cy = self.center()
        dzx, dzy = self.deadzone
        dx = dy = 0.0
        if tx > cx + dzx:
            dx = tx - (cx + dzx)
        elif tx < cx - dzx:
            dx = tx - (cx - dzx)
        if ty > cy + dzy:
            dy = ty - (cy + dzy)
        elif ty < cy - dzy:
            dy = ty - (cy - dzy)
        e = self.ease if ease is None else float(ease)
        self.x, self.y = ease_toward(self.x, self.y, self.x + dx, self.y + dy, e)
        self._clamp()

    def _clamp(self) -> None:
        if self.bounds is None:
            return
        b = self.bounds
        if len(b) == 2:
            bx, by, bw, bh = 0.0, 0.0, float(b[0]), float(b[1])
        else:
            bx, by, bw, bh = (float(v) for v in b)
        vw, vh = self.width / self.zoom, self.height / self.zoom
        cx, cy = clamp_top_left(self.x - bx, self.y - by, bw, bh, vw, vh)
        self.x, self.y = cx + bx, cy + by

    # ── shake ──────────────────────────────────────────────────────────────
    def add_trauma(self, amount: float) -> None:
        self.trauma = min(1.0, self.trauma + float(amount))

    def tick_shake(self) -> None:
        """Advance the trauma model one step; the kick is re-drawn from ``rng`` while trauma > 0."""
        if self.trauma <= 0.0:
            self.kick_x = self.kick_y = 0.0
            return
        amp = self.shake_amp * self.trauma * self.trauma
        if self.rng is not None:
            self.kick_x = self.rng.uniform(-amp, amp)
            self.kick_y = self.rng.uniform(-amp, amp)
        else:
            self.kick_x = self.kick_y = amp
        self.trauma = max(0.0, self.trauma - self.trauma_decay)

    def set_kick(self, kx: float, ky: float) -> None:
        """Adopt an externally computed kick (legacy shake mirror, Phase 6 host)."""
        self.kick_x, self.kick_y = float(kx), float(ky)

    # ── mapping ────────────────────────────────────────────────────────────
    def offset(self, alpha: float = 1.0) -> tuple[int, int]:
        """Integer camera (top-left world px) for this frame, interpolated by ``alpha`` plus the kick."""
        a = min(1.0, max(0.0, float(alpha)))
        x = self.prev_x + (self.x - self.prev_x) * a + self.kick_x
        y = self.prev_y + (self.y - self.prev_y) * a + self.kick_y
        return int(round(x)), int(round(y))

    def world_to_screen(self, wx: float, wy: float, alpha: float = 1.0) -> tuple[int, int]:
        ox, oy = self.offset(alpha)
        return int(round((wx - ox) * self.zoom)), int(round((wy - oy) * self.zoom))

    def screen_to_world(self, sx: float, sy: float, alpha: float = 1.0) -> tuple[float, float]:
        ox, oy = self.offset(alpha)
        return sx / self.zoom + ox, sy / self.zoom + oy

    def visible_rect(self, alpha: float = 1.0, margin: int = 0) -> tuple[int, int, int, int]:
        ox, oy = self.offset(alpha)
        return (ox - margin, oy - margin, int(self.width / self.zoom) + 2 * margin,
                int(self.height / self.zoom) + 2 * margin)

    def describe(self) -> dict[str, Any]:
        return {"x": self.x, "y": self.y, "zoom": self.zoom, "trauma": self.trauma, "kick": (self.kick_x, self.kick_y),
                "bounds": self.bounds, "deadzone": self.deadzone, "ease": self.ease, "lookahead": self.lookahead}
