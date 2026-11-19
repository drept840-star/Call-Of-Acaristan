"""Analytical spring-damper primitives for 3D procedural animation & camera feel.

All integrators solve the damped harmonic oscillator analytically over ``dt``,
so stiffnesses up to 40+ Hz remain unconditionally stable across frame hitches
and variable timesteps without sub-stepping or per-frame allocations.
"""
from __future__ import annotations

import math

__all__ = ["Spring", "AngleSpring", "Spring3", "TurnLagTracker"]


def _step_osc(y: float, v: float, dt: float, omega: float, zeta: float) -> tuple[float, float]:
    """Advance displacement ``y = x - target`` and velocity ``v`` by ``dt``."""
    if dt <= 0.0:
        return y, v
    if omega <= 1e-6:
        return y + v * dt, v
    if abs(zeta - 1.0) < 1e-4:
        e = math.exp(-omega * dt)
        c1 = y
        c2 = v + omega * y
        y_new = (c1 + c2 * dt) * e
        v_new = (c2 - omega * (c1 + c2 * dt)) * e
        return y_new, v_new
    if zeta < 1.0:
        a = zeta * omega
        wd = omega * math.sqrt(max(1e-8, 1.0 - zeta * zeta))
        e = math.exp(-a * dt)
        c1 = y
        c2 = (v + a * y) / wd
        cos_t = math.cos(wd * dt)
        sin_t = math.sin(wd * dt)
        y_new = e * (c1 * cos_t + c2 * sin_t)
        v_new = e * ((c2 * wd - a * c1) * cos_t - (c1 * wd + a * c2) * sin_t)
        return y_new, v_new
    s = omega * math.sqrt(max(1e-8, zeta * zeta - 1.0))
    r1 = -omega * zeta + s
    r2 = -omega * zeta - s
    denom = r2 - r1
    c2 = (v - r1 * y) / denom if abs(denom) > 1e-9 else 0.0
    c1 = y - c2
    e1 = math.exp(r1 * dt)
    e2 = math.exp(r2 * dt)
    return c1 * e1 + c2 * e2, c1 * r1 * e1 + c2 * r2 * e2


def _wrap180(deg: float) -> float:
    return ((deg + 180.0) % 360.0) - 180.0


class Spring:
    """Scalar damped spring."""

    __slots__ = ("value", "vel", "target", "freq_hz", "zeta")

    def __init__(self, value: float = 0.0, *, freq_hz: float = 6.0, zeta: float = 0.85) -> None:
        self.value = float(value)
        self.vel = 0.0
        self.target = float(value)
        self.freq_hz = float(freq_hz)
        self.zeta = float(zeta)

    def snap(self, value: float = 0.0) -> float:
        self.value = float(value)
        self.target = float(value)
        self.vel = 0.0
        return self.value

    def impulse(self, dv: float) -> None:
        self.vel += float(dv)

    def kick(self, dx: float, dv: float = 0.0) -> None:
        self.value += float(dx)
        self.vel += float(dv)

    def step(self, dt: float, target: float | None = None) -> float:
        if target is not None:
            self.target = float(target)
        if dt <= 0.0:
            return self.value
        omega = math.tau * max(0.0, self.freq_hz)
        y, v = _step_osc(self.value - self.target, self.vel, float(dt), omega, max(0.05, self.zeta))
        self.value = self.target + y
        self.vel = v
        return self.value


class AngleSpring:
    """Shortest-arc angular spring in degrees (safe across the +-180 seam)."""

    __slots__ = ("value", "vel", "target", "freq_hz", "zeta")

    def __init__(self, value: float = 0.0, *, freq_hz: float = 7.0, zeta: float = 0.9) -> None:
        self.value = _wrap180(float(value))
        self.vel = 0.0
        self.target = self.value
        self.freq_hz = float(freq_hz)
        self.zeta = float(zeta)

    def snap(self, value: float = 0.0) -> float:
        self.value = _wrap180(float(value))
        self.target = self.value
        self.vel = 0.0
        return self.value

    def impulse(self, dv: float) -> None:
        self.vel += float(dv)

    def step(self, dt: float, target: float | None = None) -> float:
        if target is not None:
            self.target = _wrap180(float(target))
        if dt <= 0.0:
            return self.value
        err = _wrap180(self.target - self.value)
        tgt_eff = self.value + err
        omega = math.tau * max(0.0, self.freq_hz)
        y, v = _step_osc(-err, self.vel, float(dt), omega, max(0.05, self.zeta))
        self.value = _wrap180(tgt_eff + y)
        self.vel = v
        return self.value


class Spring3:
    """Three-axis spring for vector recoil, flinch, and secondary motion."""

    __slots__ = ("x", "y", "z")

    def __init__(self, value: tuple[float, float, float] = (0.0, 0.0, 0.0),
                 *, freq_hz: float = 7.0, zeta: float = 0.8) -> None:
        self.x = Spring(value[0], freq_hz=freq_hz, zeta=zeta)
        self.y = Spring(value[1], freq_hz=freq_hz, zeta=zeta)
        self.z = Spring(value[2], freq_hz=freq_hz, zeta=zeta)

    @property
    def value(self) -> tuple[float, float, float]:
        return (self.x.value, self.y.value, self.z.value)

    def snap(self, value: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> tuple[float, float, float]:
        return (self.x.snap(value[0]), self.y.snap(value[1]), self.z.snap(value[2]))

    def impulse(self, dv: tuple[float, float, float]) -> None:
        self.x.impulse(dv[0])
        self.y.impulse(dv[1])
        self.z.impulse(dv[2])

    def kick(self, dx: tuple[float, float, float], dv: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> None:
        self.x.kick(dx[0], dv[0])
        self.y.kick(dx[1], dv[1])
        self.z.kick(dx[2], dv[2])

    def step(self, dt: float, target: tuple[float, float, float] | None = None) -> tuple[float, float, float]:
        if target is None:
            return (self.x.step(dt), self.y.step(dt), self.z.step(dt))
        return (self.x.step(dt, target[0]), self.y.step(dt, target[1]), self.z.step(dt, target[2]))


class TurnLagTracker:
    """Measures yaw velocity and drives damped head/shoulder lag offsets."""

    __slots__ = ("_yaw", "_primed", "head_lag", "shoulder_lag", "roll_lag", "max_rate")

    def __init__(self, yaw_deg: float = 0.0, *, max_rate: float = 420.0) -> None:
        self._yaw = _wrap180(float(yaw_deg))
        self._primed = False
        self.max_rate = float(max_rate)
        self.head_lag = Spring(0.0, freq_hz=6.5, zeta=0.78)
        self.shoulder_lag = Spring(0.0, freq_hz=8.5, zeta=0.72)
        self.roll_lag = Spring(0.0, freq_hz=7.5, zeta=0.75)

    def reset(self, yaw_deg: float = 0.0) -> None:
        self._yaw = _wrap180(float(yaw_deg))
        self._primed = False
        self.head_lag.snap(0.0)
        self.shoulder_lag.snap(0.0)
        self.roll_lag.snap(0.0)

    def step(self, dt: float, yaw_deg: float) -> tuple[float, float, float]:
        y = _wrap180(float(yaw_deg))
        if not self._primed:
            self._yaw = y
            self._primed = True
            return 0.0, 0.0, 0.0
        if dt <= 1e-5:
            return self.head_lag.value, self.shoulder_lag.value, self.roll_lag.value
        dy = _wrap180(y - self._yaw)
        self._yaw = y
        rate = max(-self.max_rate, min(self.max_rate, dy / dt))
        # Turning clockwise (+rate) leaves head/shoulders lagging briefly (-offset)
        h = self.head_lag.step(dt, max(-18.0, min(18.0, -rate * 0.042)))
        s = self.shoulder_lag.step(dt, max(-14.0, min(14.0, -rate * 0.032)))
        r = self.roll_lag.step(dt, max(-8.0, min(8.0, -rate * 0.018)))
        return h, s, r
