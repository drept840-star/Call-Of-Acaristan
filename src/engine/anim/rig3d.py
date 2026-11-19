"""Layered 3D pose controller, velocity-coupled gait, and stair/foot-IK solver.

Operates purely on pose dictionaries matching ``engine3d.rig.NEUTRAL`` keys so
``engine.anim`` remains independent of ``engine3d`` / ``moderngl`` (boundary E3).
Joint sign conventions follow ``ARCHITECTURE_MAP.md`` §2.1 (+X right, +Y up,
+Z forward, +deg spine forward, +deg hip/shoulder forward, +deg knee bend).
"""
from __future__ import annotations

import math
from typing import Callable, Iterable, Mapping

from .springs import Spring, Spring3, TurnLagTracker

__all__ = [
    "LOWER_BODY_KEYS",
    "TORSO_KEYS",
    "HEAD_KEYS",
    "LEFT_ARM_KEYS",
    "RIGHT_ARM_KEYS",
    "WEAPON_KEYS",
    "UPPER_BODY_KEYS",
    "FULL_BODY_KEYS",
    "NEUTRAL_POSE",
    "blend_poses",
    "add_pose",
    "mask_pose",
    "locomotion_pose",
    "gait_cycle_m",
    "FootIKSolver",
    "LayeredAnimState",
]

LOWER_BODY_KEYS: frozenset[str] = frozenset({
    "lhip_p", "lhip_r", "lkn", "lank",
    "rhip_p", "rhip_r", "rkn", "rank",
    "lift",
})
TORSO_KEYS: frozenset[str] = frozenset({"spine", "spine_r", "twist"})
HEAD_KEYS: frozenset[str] = frozenset({"head_p", "head_y", "head_x"})
LEFT_ARM_KEYS: frozenset[str] = frozenset({"lsh_p", "lsh_r", "lsh_y", "lel"})
RIGHT_ARM_KEYS: frozenset[str] = frozenset({"rsh_p", "rsh_r", "rsh_y", "rel"})
WEAPON_KEYS: frozenset[str] = frozenset({"rifle_p", "rifle_y"})
UPPER_BODY_KEYS: frozenset[str] = TORSO_KEYS | HEAD_KEYS | LEFT_ARM_KEYS | RIGHT_ARM_KEYS | WEAPON_KEYS
FULL_BODY_KEYS: frozenset[str] = LOWER_BODY_KEYS | UPPER_BODY_KEYS | frozenset({"body_p", "body_r"})

NEUTRAL_POSE: dict[str, float] = {k: 0.0 for k in FULL_BODY_KEYS}


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _smooth(t: float) -> float:
    u = _clamp(t, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def blend_poses(a: Mapping[str, float], b: Mapping[str, float], t: float,
                keys: Iterable[str] | None = None) -> dict[str, float]:
    """Lerp pose ``a`` toward ``b`` by ``t`` (restricted to ``keys`` if given)."""
    u = _clamp(t, 0.0, 1.0)
    target_keys = FULL_BODY_KEYS if keys is None else keys
    out = dict(NEUTRAL_POSE)
    for k in FULL_BODY_KEYS:
        va = float(a.get(k, 0.0))
        if k in target_keys:
            out[k] = va + (float(b.get(k, 0.0)) - va) * u
        else:
            out[k] = va
    return out


def add_pose(base: Mapping[str, float], delta: Mapping[str, float], weight: float = 1.0,
             keys: Iterable[str] | None = None) -> dict[str, float]:
    """Add ``delta * weight`` onto ``base`` across ``keys``."""
    w = float(weight)
    target_keys = FULL_BODY_KEYS if keys is None else keys
    out = {k: float(base.get(k, 0.0)) for k in FULL_BODY_KEYS}
    if abs(w) <= 1e-6:
        return out
    for k in target_keys:
        if k in delta:
            out[k] += float(delta[k]) * w
    return out


def mask_pose(lower: Mapping[str, float], upper: Mapping[str, float],
              *, upper_keys: Iterable[str] | None = None) -> dict[str, float]:
    """Combine ``lower`` body angles with ``upper`` body angles cleanly."""
    # A frozenset default would put its hash-seed-dependent repr in the public
    # signature and break the API snapshot between processes; use None instead.
    uk = UPPER_BODY_KEYS if upper_keys is None else frozenset(upper_keys)
    out = {k: float(lower.get(k, 0.0)) for k in FULL_BODY_KEYS}
    for k in uk:
        if k in upper:
            out[k] = float(upper[k])
    return out


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * _clamp(t, 0.0, 1.0)


def _cycle_len(speed: float, sprint: float, crouch: float) -> float:
    """Ground metres covered by one full two-step gait cycle.

    Stride grows with speed like a person's: ~1.7 m at an aimed 1.9 m/s walk
    (1.1 cycles/s), ~2.1 m at the 3.3 m/s patrol jog (1.55/s), ~2.7 m at a
    5.3 m/s sprint (2.0/s). A fixed 2.15 m made slow walks plod and fast ones
    need lunging strides to keep the planted foot still. ``sprint`` is kept
    for callers; speed already carries it.
    """
    c = _clamp(1.20 + 0.276 * speed, 1.33, 2.71)
    return c * 0.78 if crouch > 0.5 else c


def gait_cycle_m(speed: float, sprint: float = 0.0, crouch: float = 0.0) -> float:
    """Public cycle length (m) so scenes can advance a phase from ground metres."""
    return _cycle_len(speed, sprint, crouch)


def _leg_swing(ph: float, fold: float, soft: float) -> tuple[float, float, float, float]:
    """One leg of the harmonic gait: ``(hip_norm, knee_deg, swing_w, stance_w)``.

    ``sin(ph) + 0.14 * sin(2*ph)`` passes through swing faster than it sweeps
    the planted stance, which reads as a deliberate step instead of a shuffle.

    The knee folds in proportion to how fast the thigh swings FORWARD
    (``dwave``): zero at both hip extremes, so the leg is straight at
    heel-strike and toe-off, deepest as it passes the planted leg. It used to
    fold on the backward stroke, which dragged the planted foot forward
    (moonwalk). A small ``soft`` give loads the front leg in early stance and
    is gone again by the time it trails. Powers above 1 keep the curve C1
    across the swing/stance switch, so the knee never snaps.
    """
    wave = (math.sin(ph) + 0.14 * math.sin(2.0 * ph)) / 1.08
    dwave = (math.cos(ph) + 0.28 * math.cos(2.0 * ph)) / 1.28
    swing_w = max(0.0, dwave) ** 1.3
    stance_w = max(0.0, -dwave) ** 1.3
    knee = 3.0 + fold * swing_w + soft * max(0.0, wave) * stance_w
    return wave, knee, swing_w, stance_w


def locomotion_pose(fwd_speed: float, side_speed: float, phase: float,
                    *, sprint: float = 0.0, crouch: float = 0.0,
                    max_walk: float = 4.8, max_sprint: float = 7.4) -> dict[str, float]:
    """Velocity-coupled lower-body & torso-counter-twist pose.

    ``fwd_speed`` / ``side_speed`` are m/s in character local space (+fwd, +right).
    ``phase`` advances monotonically in radians per gait cycle.
    """
    speed = math.hypot(fwd_speed, side_speed)
    move_k = _smooth(speed / 0.9)
    sp_k = _clamp(sprint, 0.0, 1.0) * move_k
    cr_k = _clamp(crouch, 0.0, 1.0)

    denom = max_walk + (max_sprint - max_walk) * sp_k
    norm_spd = _clamp(speed / max(0.5, denom), 0.0, 1.25)
    fwd_ratio = (fwd_speed / speed) if speed > 1e-4 else 1.0
    side_ratio = (side_speed / speed) if speed > 1e-4 else 0.0

    amp = move_k * (0.50 + 0.50 * min(1.0, norm_spd)) * (1.0 - 0.42 * cr_k)
    fwd_mag = abs(fwd_ratio)
    fwd_sign = 1.0 if fwd_ratio >= -0.25 else -1.0
    # Thigh swing sized to the speed-scaled stride (``_cycle_len``) so the
    # planted foot sweeps back about as far as the body travels over it.
    hip_amp = move_k * _clamp(12.0 + 7.0 * speed, 16.0, 44.0) * (1.0 - 0.42 * cr_k)
    fold = _clamp(36.0 + 10.0 * speed, 44.0, 96.0) * (1.0 - 0.30 * cr_k)
    soft = 14.0 + 4.0 * sp_k
    # Planted ankle stays inside the auto-grounder's band; the toe-point is
    # only ever added to a foot that is actually airborne.
    base_ank = max(-8.0, min(10.0, -8.0 * cr_k + 4.0 * (1.0 - cr_k)))
    toe_off = (18.0 + 6.0 * sp_k) * (1.0 - cr_k)

    l_out = {}
    for side, off, lat in (("l", 0.0, -1.0), ("r", math.pi, 1.0)):
        ph = phase + off
        wave, knee_deg, swing_w, _stance_w = _leg_swing(ph, fold, soft)

        # Lateral strafe step: leading leg abducts and lifts, trailing follows.
        ph_lat = ph + (0.0 if off == 0.0 else math.pi)
        s_lat = math.sin(ph_lat)
        lat_swing = max(0.0, math.cos(ph_lat)) ** 1.15
        step_out = (-lat * side_ratio) * s_lat
        strafe_hip_r = amp * abs(side_ratio) * (18.0 * max(0.0, step_out) - 4.0 * max(0.0, -step_out))
        strafe_kn = amp * abs(side_ratio) * (34.0 * lat_swing + 6.0)
        strafe_ank = amp * abs(side_ratio) * (-8.0 * lat_swing + 6.0 * (1.0 - lat_swing))

        # The staggered idle stance fades out while walking, or one leg would
        # reach further forward than the other.
        idle_hip_p = 68.0 * cr_k + (1.0 - cr_k) * (1.0 - move_k) * (-5.5 * lat)
        idle_kn = 92.0 * cr_k + (1.0 - cr_k) * (11.0 + 2.0 * (1.0 + lat))
        idle_hip_r = 3.5 + 3.5 * cr_k

        hip_p = idle_hip_p + fwd_mag * hip_amp * wave * fwd_sign
        kn = _lerp(idle_kn, 90.0 * cr_k + knee_deg * fwd_mag + strafe_kn, move_k)
        stance_ank = max(-8.0, min(10.0, base_ank + strafe_ank * (1.0 - swing_w)))
        # Toe points as the foot leaves behind, lifts as it reaches forward.
        behind = 0.5 - 0.5 * math.sin(ph)
        swing_ank = swing_w * (toe_off * behind - 10.0 * (1.0 - behind))
        ank = _lerp(base_ank, stance_ank + swing_ank, move_k)
        hip_r = idle_hip_r + strafe_hip_r + amp * 1.4 * swing_w
        l_out[side] = (hip_p, kn, ank, hip_r, swing_w)

    lhip_p, lkn, lank, lhip_r, lst = l_out["l"]
    rhip_p, rkn, rank, rhip_r, rst = l_out["r"]

    # Bridge the geometric leg-span shortening with one smooth target instead
    # of letting the grounder chase a per-leg stance weight (that oscillated).
    drop_l = 0.45 * (math.cos(math.radians(lhip_p)) + math.cos(math.radians(lhip_p - lkn)))
    drop_r = 0.45 * (math.cos(math.radians(rhip_p)) + math.cos(math.radians(rhip_p - rkn)))
    # A walk keeps a foot down (the pelvis dips as the legs split); a jog or
    # sprint floats briefly at full split, like a real flight phase.
    target_h = 0.80 + 0.058 * _smooth((speed - 1.5) / 2.0) + 0.010 * sp_k
    lift = move_k * (1.0 - cr_k) * max(0.0, target_h - max(drop_l, drop_r))

    s = math.sin(phase)
    c2 = math.cos(2.0 * phase)
    spine = (14.0 * cr_k
             + move_k * ((3.5 + 7.0 * sp_k) * fwd_ratio + 4.0 * abs(side_ratio))
             + amp * (1.6 + 1.2 * sp_k) * (-c2))
    spine_r = -move_k * 5.0 * side_ratio + amp * 1.8 * s * (1.0 - abs(side_ratio))
    twist = -amp * (3.8 + 2.8 * sp_k) * s * fwd_ratio

    out = dict(NEUTRAL_POSE)
    out.update(
        lhip_p=lhip_p, rhip_p=rhip_p,
        lhip_r=lhip_r, rhip_r=rhip_r,
        lkn=lkn, rkn=rkn,
        lank=lank, rank=rank,
        lift=lift,
        body_r=0.0,                      # no pelvic roll: it doubled the grounder bounce
        spine=spine, spine_r=spine_r, twist=twist,
    )
    return out


class FootIKSolver:
    """Samples terrain/stairs under each foot and smooths step heights.

    Outputs both world-space foot targets ``{"l": (x,y,z), "r": (x,y,z)}``
    (ready for ``engine3d.ik.solve_leg``) and direct joint-angle deltas for
    lightweight LOD rigs.
    """

    __slots__ = ("hip_half", "stride_reach", "max_step", "ly", "ry", "pelvis_y",
                 "foot_targets", "pelvis_drop")

    def __init__(self, *, hip_half: float = 0.11, stride_reach: float = 0.26,
                 max_step: float = 0.65, y0: float = 0.0) -> None:
        self.hip_half = float(hip_half)
        self.stride_reach = float(stride_reach)
        self.max_step = float(max_step)
        self.ly = Spring(y0, freq_hz=12.0, zeta=0.92)
        self.ry = Spring(y0, freq_hz=12.0, zeta=0.92)
        self.pelvis_y = Spring(y0, freq_hz=10.0, zeta=0.92)
        self.foot_targets: dict[str, tuple[float, float, float]] = {
            "l": (-hip_half, y0, 0.0),
            "r": (hip_half, y0, 0.0),
        }
        self.pelvis_drop = 0.0

    def reset(self, y0: float = 0.0) -> None:
        self.ly.snap(y0)
        self.ry.snap(y0)
        self.pelvis_y.snap(y0)
        self.pelvis_drop = 0.0

    def update(self, dt: float, pos: tuple[float, float, float], yaw_deg: float,
               phase: float, move_k: float,
               floor_fn: Callable[[float, float], float] | None) -> dict[str, float]:
        px, py, pz = float(pos[0]), float(pos[1]), float(pos[2])
        rad = math.radians(yaw_deg)
        fx, fz = math.sin(rad), math.cos(rad)
        rx, rz = math.cos(rad), -math.sin(rad)

        reach = self.stride_reach * _clamp(move_k, 0.0, 1.0)
        s = math.sin(phase)
        lx = px - rx * self.hip_half + fx * (reach * s)
        lz = pz - rz * self.hip_half + fz * (reach * s)
        rx_w = px + rx * self.hip_half - fx * (reach * s)
        rz_w = pz + rz * self.hip_half - fz * (reach * s)

        if floor_fn is not None:
            raw_l = _clamp(float(floor_fn(lx, lz)), py - self.max_step, py + self.max_step)
            raw_r = _clamp(float(floor_fn(rx_w, rz_w)), py - self.max_step, py + self.max_step)
        else:
            raw_l = raw_r = py

        sy_l = self.ly.step(dt, raw_l)
        sy_r = self.ry.step(dt, raw_r)
        low = min(sy_l, sy_r)
        sp_y = self.pelvis_y.step(dt, low)
        self.pelvis_drop = _clamp(sp_y - py, -0.35, 0.25)

        # Clearance lift during swing phase
        c = math.cos(phase)
        swing_l = max(0.0, c) * 0.10 * _clamp(move_k, 0.0, 1.0)
        swing_r = max(0.0, -c) * 0.10 * _clamp(move_k, 0.0, 1.0)
        self.foot_targets["l"] = (lx, sy_l + swing_l, lz)
        self.foot_targets["r"] = (rx_w, sy_r + swing_r, rz_w)

        # Direct angle compensation for the uphill foot relative to the downhill foot
        up_l = max(0.0, sy_l - sp_y)
        up_r = max(0.0, sy_r - sp_y)
        return {
            "lift": self.pelvis_drop,
            "lhip_p": up_l * 78.0,
            "lkn": up_l * 112.0,
            "lank": -up_l * 34.0,
            "rhip_p": up_r * 78.0,
            "rkn": up_r * 112.0,
            "rank": -up_r * 34.0,
        }


class LayeredAnimState:
    """Shared per-character 3D layered animation + spring-damper controller."""

    def __init__(self, *, yaw_deg: float = 0.0, y0: float = 0.0,
                 stride_gain: float = 2.0) -> None:
        self.stride_phase = 0.0
        self.stride_gain = float(stride_gain)
        self.aim = Spring(0.0, freq_hz=4.5, zeta=0.95)
        self.sprint_w = Spring(0.0, freq_hz=4.0, zeta=0.95)
        self.crouch_w = Spring(0.0, freq_hz=5.0, zeta=0.92)
        self.radio_w = Spring(0.0, freq_hz=4.5, zeta=0.90)
        self.reload_w = Spring(0.0, freq_hz=6.0, zeta=0.92)
        self.swap_w = Spring(0.0, freq_hz=7.0, zeta=0.92)

        self.reloading = False
        self.reload_phase = 0.0
        self.reload_dur = 1.0
        self.swapping = False
        self.swap_phase = 0.0
        self.swap_dur = 0.35
        self.melee_t = -1.0
        self.melee_dur = 0.38

        # (pitch_kick, yaw_kick, rifle_kick)
        self.recoil = Spring3((0.0, 0.0, 0.0), freq_hz=11.0, zeta=0.65)
        self.cam_punch = Spring3((0.0, 0.0, 0.0), freq_hz=9.5, zeta=0.72)
        self.flinch = Spring3((0.0, 0.0, 0.0), freq_hz=8.5, zeta=0.60)
        self.secondary = Spring3((0.0, 0.0, 0.0), freq_hz=3.0, zeta=0.92)
        self.turn_lag = TurnLagTracker(yaw_deg)
        self.foot_ik = FootIKSolver(y0=y0)

        self._local_fwd = 0.0
        self._local_side = 0.0
        self._prev_vel = (0.0, 0.0)
        self._ik_delta: dict[str, float] = {}

    def trigger_recoil(self, pitch_deg: float = 5.5, yaw_deg: float = 0.0,
                       rifle_deg: float = 10.0, *, cam_pitch: float = 1.4,
                       cam_yaw: float = 0.0, cam_roll: float = 0.0) -> None:
        self.recoil.kick((pitch_deg * 0.45, yaw_deg * 0.45, rifle_deg * 0.45),
                         (pitch_deg * 18.0, yaw_deg * 18.0, rifle_deg * 26.0))
        self.cam_punch.kick((cam_pitch * 0.35, cam_yaw * 0.35, cam_roll * 0.35),
                            (cam_pitch * 16.0, cam_yaw * 16.0, cam_roll * 14.0))

    def trigger_flinch(self, local_dir_x: float, local_dir_z: float,
                       strength: float = 1.0) -> None:
        # Hit from front (+z) pushes torso backward (-spine); from right (+x) rolls left
        s = _clamp(strength, 0.1, 2.5)
        self.flinch.impulse((-local_dir_z * 95.0 * s,
                             -local_dir_x * 75.0 * s,
                             local_dir_x * 110.0 * s))

    def trigger_melee(self, duration: float = 0.38) -> None:
        self.melee_dur = max(0.12, float(duration))
        self.melee_t = 0.0

    def start_reload(self, duration: float = 1.5) -> None:
        self.reloading = True
        self.reload_dur = max(0.15, float(duration))
        self.reload_phase = 0.0

    def cancel_reload(self) -> None:
        self.reloading = False
        self.reload_phase = 0.0

    def start_swap(self, duration: float = 0.35) -> None:
        self.swapping = True
        self.swap_dur = max(0.10, float(duration))
        self.swap_phase = 0.0

    def update(self, dt: float, *, vel_xz: tuple[float, float] = (0.0, 0.0),
               yaw_deg: float = 0.0, aiming: bool = False, sprint: bool = False,
               crouch: bool = False, radio: bool = False,
               floor_fn: Callable[[float, float], float] | None = None,
               pos: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> None:
        dt = max(0.0, min(0.05, float(dt)))
        vx, vz = float(vel_xz[0]), float(vel_xz[1])
        rad = math.radians(yaw_deg)
        fx, fz = math.sin(rad), math.cos(rad)
        rx, rz = math.cos(rad), -math.sin(rad)
        self._local_fwd = vx * fx + vz * fz
        self._local_side = vx * rx + vz * rz
        speed = math.hypot(vx, vz)
        cycle_m = _cycle_len(speed, self.sprint_w.value, self.crouch_w.value)
        # Keep stride_gain ~2.0 as a 1.0x cadence factor so feet track ground distance.
        self.stride_phase += (speed * dt / max(0.6, cycle_m)) * math.tau * (self.stride_gain / 2.0)

        if dt > 1e-5:
            ax = _clamp((vx - self._prev_vel[0]) / dt, -30.0, 30.0)
            az = _clamp((vz - self._prev_vel[1]) / dt, -30.0, 30.0)
            local_af = ax * fx + az * fz
            local_as = ax * rx + az * rz
            # Start/stop inertia, deliberately gentle: the velocity derivative
            # is noisy on wall slides and the old 0.35 gain + zeta=0.52 rang.
            self.secondary.step(dt, (-local_as * 0.16, -local_af * 0.13, -speed * 0.12))
        self._prev_vel = (vx, vz)

        self.aim.step(dt, 1.0 if (aiming and not sprint and not self.reloading) else 0.0)
        self.sprint_w.step(dt, 1.0 if sprint else 0.0)
        self.crouch_w.step(dt, 1.0 if crouch else 0.0)
        self.radio_w.step(dt, 1.0 if radio else 0.0)
        self.reload_w.step(dt, 1.0 if self.reloading else 0.0)
        self.swap_w.step(dt, 1.0 if self.swapping else 0.0)

        if self.reloading:
            self.reload_phase += dt / self.reload_dur
            if self.reload_phase >= 1.0:
                self.reloading = False
                self.reload_phase = 1.0
        if self.swapping:
            self.swap_phase += dt / self.swap_dur
            if self.swap_phase >= 1.0:
                self.swapping = False
                self.swap_phase = 1.0
        if self.melee_t >= 0.0:
            self.melee_t += dt
            if self.melee_t >= self.melee_dur:
                self.melee_t = -1.0

        self.recoil.step(dt, (0.0, 0.0, 0.0))
        self.cam_punch.step(dt, (0.0, 0.0, 0.0))
        self.flinch.step(dt, (0.0, 0.0, 0.0))
        self.turn_lag.step(dt, yaw_deg)
        self._ik_delta = self.foot_ik.update(
            dt, pos, yaw_deg, self.stride_phase, _clamp(speed / 0.9, 0.0, 1.0), floor_fn,
        )

    def compose(self, ready_pose: Mapping[str, float], aim_pose: Mapping[str, float] | None = None,
                *, pitch_deg: float = 0.0, time_s: float = 0.0,
                breath_amp: float = 0.25,
                reload_pose: Mapping[str, float] | None = None) -> dict[str, float]:
        """Compose lower-body locomotion + upper-body actions + spring overlays."""
        lower = locomotion_pose(
            self._local_fwd, self._local_side, self.stride_phase,
            sprint=self.sprint_w.value, crouch=self.crouch_w.value,
        )
        if self._ik_delta:
            lower = add_pose(lower, self._ik_delta, 1.0, LOWER_BODY_KEYS)

        upper_base = ready_pose if aim_pose is None else blend_poses(
            ready_pose, aim_pose, self.aim.value, UPPER_BODY_KEYS,
        )
        pose = mask_pose(lower, upper_base)
        # Keep locomotion torso lean/twist alive under the upper-body stance
        pose["body_r"] = lower.get("body_r", 0.0) * (1.0 - 0.55 * self.aim.value)
        # Keep locomotion torso lean/twist/tilt alive under the upper-body stance
        aim_damp = 1.0 - 0.45 * self.aim.value
        for tk in TORSO_KEYS:
            pose[tk] = upper_base.get(tk, 0.0) + lower.get(tk, 0.0) * aim_damp
        # Eyes stay stabilized downrange as the shoulders counter-rotate beneath them.
        pose["head_y"] -= lower.get("twist", 0.0) * aim_damp * 0.75
        pose["head_p"] -= (lower.get("spine", 0.0) - 15.0 * self.crouch_w.value) * 0.28 * aim_damp

        if self.reload_w.value > 0.01:
            rp = reload_pose if reload_pose is not None else {
                "spine": 8.0, "head_p": 14.0, "lsh_p": 46.0, "lsh_r": -8.0, "lel": 84.0,
                "rsh_p": 36.0, "rsh_r": 6.0, "rel": 72.0, "rifle_p": 18.0, "rifle_y": -16.0,
            }
            pose = blend_poses(pose, rp, self.reload_w.value, LEFT_ARM_KEYS | RIGHT_ARM_KEYS | WEAPON_KEYS | {"head_p"})

        if self.swap_w.value > 0.01:
            dip = math.sin(self.swap_phase * math.pi)
            pose = add_pose(pose, {
                "rsh_p": -28.0 * dip, "rel": 24.0 * dip, "rifle_p": 38.0 * dip, "twist": 10.0 * dip,
            }, self.swap_w.value, TORSO_KEYS | RIGHT_ARM_KEYS | WEAPON_KEYS)

        if self.radio_w.value > 0.01:
            pose = blend_poses(pose, {
                "lsh_p": 76.0, "lsh_r": -14.0, "lel": 112.0, "head_p": 8.0, "head_y": -10.0,
            }, self.radio_w.value, LEFT_ARM_KEYS | {"head_p", "head_y"})

        if self.melee_t >= 0.0:
            u = _clamp(self.melee_t / self.melee_dur, 0.0, 1.0)
            if u < 0.25:
                k = -_smooth(u / 0.25) * 0.45
            elif u < 0.55:
                k = -0.45 + 1.45 * _smooth((u - 0.25) / 0.30)
            else:
                k = 1.0 - _smooth((u - 0.55) / 0.45)
            pose = add_pose(pose, {
                "twist": 28.0 * k, "spine": 10.0 * abs(k),
                "rsh_p": 46.0 * k, "rsh_r": -18.0 * k, "rel": -22.0 * k,
                "lsh_p": 24.0 * k, "rifle_y": 26.0 * k, "rifle_p": -14.0 * k,
            }, 1.0, UPPER_BODY_KEYS)

        # Springs: recoil + flinch + turn lag + start/stop inertia + breathing + pitch
        rx, ry, r_gun = self.recoil.value
        fx, fy, fz = self.flinch.value
        sec_side, sec_fwd, _ = self.secondary.value
        sec_fwd = _clamp(sec_fwd, -5.0, 6.5) * (1.0 - 0.55 * self.aim.value)
        sec_side = _clamp(sec_side, -5.0, 5.0) * (1.0 - 0.50 * self.aim.value)
        h_lag, s_lag, r_lag = self.turn_lag.head_lag.value, self.turn_lag.shoulder_lag.value, self.turn_lag.roll_lag.value
        breath = (math.sin(time_s * 1.95) + 0.42 * math.sin(time_s * 0.85)) * breath_amp * (1.0 - 0.65 * self.aim.value)

        pose["spine"] += -0.35 * pitch_deg - rx * 0.45 + fx + sec_fwd * 0.65 + breath
        pose["head_p"] += -0.55 * pitch_deg - rx * 0.25 + fx * 0.8 + sec_fwd * 0.28 + breath * 0.6
        pose["head_y"] += h_lag + ry * 0.25
        pose["spine_r"] += fy + r_lag + sec_side * 0.75
        pose["body_r"] += sec_side * 0.25
        pose["twist"] += fz + s_lag * 0.45
        pose["rsh_p"] += rx * 0.85
        pose["lsh_p"] += rx * 0.65
        pose["rsh_r"] += s_lag * 0.25
        pose["rifle_p"] += -r_gun - 0.20 * pitch_deg
        pose["rifle_y"] += ry + s_lag * 0.65
        return pose