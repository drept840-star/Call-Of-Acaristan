"""Fixed-step simulation clock (master prompt §6.1, ADR-004).

Semantics match the legacy ``core.fixedstep.FixedStepClock`` (same accumulator,
same spiral-of-death guard) and add: frame counter, deterministic sim ticks in
ms (the replacement for ``pygame.time.get_ticks()`` in simulation code), time
scale and pause (applied to sim time only; the UI clock is ``real_time``).
"""
from __future__ import annotations

__all__ = ["Clock", "DEFAULT_HZ", "DEFAULT_MAX_STEPS"]

DEFAULT_HZ = 60
DEFAULT_MAX_STEPS = 5


class Clock:
    def __init__(self, step_hz: int = DEFAULT_HZ, max_steps: int = DEFAULT_MAX_STEPS) -> None:
        if step_hz <= 0:
            raise ValueError(f"step_hz must be positive, got {step_hz!r}")
        if max_steps < 1:
            raise ValueError(f"max_steps must be >= 1, got {max_steps!r}")
        self.step_hz = int(step_hz)
        self.max_steps = int(max_steps)
        self.dt = 1.0 / self.step_hz
        self.time_scale = 1.0
        self.paused = False
        self.reset()

    def reset(self) -> None:
        """Back to t=0: no accumulated time, frame 0. The wall clock keeps its origin."""
        self._acc = 0.0
        self.frame = 0            # sim steps run so far
        self.sim_time = 0.0       # seconds of simulated time
        self.real_time = 0.0      # seconds of wall time fed in (UI clock)
        self.dropped_steps = 0
        self._wall_elapsed_ms = 0

    # -- frame-coherent wall clock (B-001) ---------------------------------
    # The game used to read pygame.time.get_ticks()/time.time() anywhere, so a
    # frame saw many different "nows" and tests had to monkeypatch pygame.
    # Here the host feeds the frame's elapsed milliseconds once per presented
    # frame; every read during the next frame returns the same value.
    _wall_origin_ms = 0
    _wall_origin_s = 0.0

    def set_wall_origin(self, ms: int, epoch_s: float) -> None:
        """Anchor the wall clock (normally the OS tick count and epoch at boot)."""
        self._wall_origin_ms = int(ms)
        self._wall_origin_s = float(epoch_s)
        self._wall_elapsed_ms = 0

    def feed_wall(self, elapsed_ms: int) -> None:
        """Advance the wall clock by one presented frame's raw duration (unclamped)."""
        if elapsed_ms > 0:
            self._wall_elapsed_ms += int(elapsed_ms)

    def set_wall_elapsed(self, elapsed_ms: float) -> None:
        """Pin the wall clock to an absolute elapsed value (harnesses, replays).

        Fractional milliseconds are kept so ``wall_s`` can mirror a pinned
        ``time.time()`` exactly; ``wall_ms`` floors like the OS tick count.
        """
        self._wall_elapsed_ms = max(0, elapsed_ms)

    @property
    def wall_ms(self) -> int:
        """Frame-coherent milliseconds, same scale as ``pygame.time.get_ticks()``."""
        return self._wall_origin_ms + int(self._wall_elapsed_ms)

    @property
    def wall_s(self) -> float:
        """Frame-coherent epoch seconds, same scale as ``time.time()``."""
        return self._wall_origin_s + self._wall_elapsed_ms / 1000.0

    def advance(self, real_dt: float) -> int:
        """Feed real elapsed seconds; return how many fixed steps to run now.

        The caller runs exactly that many ``fixed_update(dt)`` calls and must
        call :meth:`tick` once per step (or use :meth:`steps`).
        """
        if real_dt is None or real_dt <= 0:
            return 0
        self.real_time += float(real_dt)
        if self.paused:
            return 0
        self._acc += float(real_dt) * self.time_scale
        count = int(self._acc / self.dt)
        if count <= 0:
            return 0
        if count > self.max_steps:
            self.dropped_steps += count - self.max_steps
            count = self.max_steps
            self._acc = 0.0
        else:
            self._acc -= count * self.dt
        return count

    def tick(self) -> None:
        """Account for one completed sim step."""
        self.frame += 1
        self.sim_time = self.frame * self.dt

    def steps(self, real_dt: float):
        """Iterate the steps for this frame, ticking after each one."""
        for _ in range(self.advance(real_dt)):
            yield self.dt
            self.tick()

    @property
    def alpha(self) -> float:
        """Interpolation factor in [0, 1] between the last two sim states."""
        return min(1.0, max(0.0, self._acc / self.dt))

    @property
    def ticks_ms(self) -> int:
        """Deterministic sim time in integer ms (derived from the frame count)."""
        return self.frame * 1000 // self.step_hz
