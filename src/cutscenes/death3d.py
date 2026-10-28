"""Gameplay death falls for 3D guards (Mission 7 raid, Mission 6 yard).

Four keyed tracks out of the guard's last live pose: 0 buckle onto the face,
1 thrown onto the back, 2 spin onto the side, 3 drop to the knees and topple.
The rig pitches about the pelvis, so the root moves to keep the feet planted
while the body tips.  The body rests on ``floor(x, z)`` under the chest, read
every frame: a guard killed on a truck bed or a platform lip falls with
gravity once he tips past the edge, instead of lying on air.
"""

import math

from engine3d import POSES, blend, clamp, m_apply, rot_y

GRAVITY = 9.8
TIP_AT = (0.30, 0.22, 0.30, 0.60)   # s: body past its feet, free to drop
LAND_AT = (0.90, 0.75, 0.90, 1.10)  # s: body meets the floor on level ground
SPIN = 75.0                         # deg: side-fall twist

_STAGGER = dict(POSES["aim"], spine=-14, head_p=-12, lsh_p=96, lsh_r=26, lel=18,
                rsh_p=90, rsh_r=40, rel=24, lhip_p=-4, lkn=14, rhip_p=6, rkn=22)
_BUCKLE = dict(POSES["slump"], spine=44, head_p=26, lsh_p=40, lsh_r=18, rsh_p=34,
               rsh_r=16)
_KNEEL = dict(POSES["kneel"], spine=34, head_p=30, lsh_p=14, lsh_r=10, lel=20,
              rsh_p=10, rsh_r=12, rel=24)


def _s(a, b, x):
    x = clamp((x - a) / (b - a), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def track_for(front, slot):
    """Death track from where the shot came: thrown back or spun from the
    front, buckled or dropped to the knees from behind."""
    if front:
        return 2 if slot % 3 == 0 else 1
    return 3 if slot % 2 else 0


def death_pose(track, a, was):
    """Pose ``a`` seconds after the kill, out of the last live pose ``was``."""
    if track == 1:
        if a < 0.18:
            return blend(was, _STAGGER, _s(0.0, 0.18, a))
        return blend(_STAGGER, POSES["dead_back"], _s(0.18, 0.75, a))
    if track == 2:
        half = blend(was, POSES["slump"], 0.5)
        if a < 0.30:
            return blend(was, half, _s(0.0, 0.30, a))
        return blend(half, POSES["dead_side"], _s(0.30, 0.90, a))
    if track == 3:
        if a < 0.55:
            p = blend(was, _KNEEL, _s(0.0, 0.40, a))
            return dict(p, spine=p["spine"] + 8.0 * math.sin(a * 9.0) * _s(0.3, 0.55, a))
        return blend(_KNEEL, POSES["dead_front"], _s(0.55, 1.10, a))
    if a < 0.35:
        return blend(was, _BUCKLE, _s(0.0, 0.35, a))
    return blend(_BUCKLE, POSES["dead_front"], _s(0.35, 0.90, a))


def _flop(p, u):
    """Limp rebound for half a second after the body hits the floor."""
    if not 0.0 <= u < 0.5:
        return p
    b = math.sin(u * 20.0) * math.exp(-u * 8.0)
    return dict(p, head_p=p["head_p"] + 16.0 * b, spine=p["spine"] + 5.0 * b,
                lsh_p=p["lsh_p"] + 12.0 * b, rsh_p=p["rsh_p"] - 10.0 * b,
                lkn=p["lkn"] + 8.0 * b)


def _ankles(hum, pose, yaw):
    """Mid-ankle (x, z) relative to the root; skeleton only."""
    feet = [org for _s, k, _M, org, _g, _fb in hum.placements(pose, rifle_on=False)[0]
            if k == "foot"]
    w = m_apply(rot_y(yaw), (sum(f[0] for f in feet) / len(feet), 0.0,
                             sum(f[2] for f in feet) / len(feet)))
    return w[0], w[2]


class Fall:
    """One body: keyed pose, planted feet, a shove, and a drop to the floor."""

    def __init__(self, hum, was, track, pos, yaw, push=(0.0, 0.0), slot=0):
        self.hum, self.was, self.track = hum, dict(was), track
        self.x, self.y, self.z = pos
        self.yaw0 = yaw
        self.spin = (SPIN if slot % 2 else -SPIN) if track == 2 else 0.0
        self.push = push
        self.ax0, self.az0 = _ankles(hum, self.was, yaw)
        self.vy = 0.0
        self.last = 0.0
        self.land = LAND_AT[track]
        self.rest = None            # (pose, (x, z), yaw) once settled
        self.chest = (self.x, self.z)

    def at(self, a, floor):
        """(pose, root, yaw) ``a`` seconds after the kill."""
        if self.rest is not None:
            p, (rx, rz), yaw = self.rest
        else:
            yaw = self.yaw0 + self.spin * _s(0.30, 0.90, a)
            p = death_pose(self.track, a, self.was)
            ax, az = _ankles(self.hum, p, yaw)
            k = 1.0 - (1.0 - min(1.0, a / 0.45)) ** 2
            rx = self.x + self.ax0 - ax + self.push[0] * k
            rz = self.z + self.az0 - az + self.push[1] * k
            ch = self.hum.pose_world(p, (rx, 0.0, rz), yaw, rifle_on=False)[1]["chest"]
            self.chest = (ch[0], ch[2])
        dt = max(0.0, a - self.last)
        self.last = a
        fl = floor(*self.chest)
        if self.y > fl + 1e-3 and a >= TIP_AT[self.track]:
            self.vy += GRAVITY * dt
            self.y = max(fl, self.y - self.vy * dt)
            if self.y <= fl:
                if self.vy > 2.0:
                    self.land = max(self.land, a)
                self.vy = 0.0
        if self.rest is None:
            p = _flop(p, a - self.land)
            if a > self.land + 0.5 and self.vy == 0.0:
                self.rest = (p, (rx, rz), yaw)
        return p, (rx, self.y, rz), yaw
