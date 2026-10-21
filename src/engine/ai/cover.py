"""engine.ai.cover - cover spots around solid boxes, and picking one.

``build_spots`` walks the faces of every box tall enough to hide behind and
drops a spot every ``spacing`` metres, ``offset`` out from the face, where the
nav grid says a body fits. A spot is

``low``   the box top is under ``low_h`` above the floor: crouch behind it
          to hide, stand up to shoot over it
``high``  taller: stand behind it to hide, step out past the nearer edge to
          shoot (only spots within ``corner`` of an edge can do that)

``pick`` scores the spots that hide from a threat: travel, distance from the
threat against an ideal range, and spread from squadmates (where they stand,
or the spots they are heading for); the best few are
then checked for a firing line and a walkable route, cheapest first.
"""
from __future__ import annotations

import math
from typing import Callable, Iterable, Sequence

from engine.collision.boxes import BoxWorld, ray_aabb

__all__ = ["Spot", "build_spots", "hides", "peek_point", "can_peek", "pick"]

Vec3 = Sequence[float]

HIDE_EYE_LOW = 0.9          # crouched head behind low cover, above the floor
HIDE_EYE_HIGH = 1.55        # standing head behind tall cover
SHOOT_EYE = 1.45            # standing, shouldered


class Spot:
    __slots__ = ("id", "x", "y", "z", "nx", "nz", "tx", "tz", "edge", "box", "low")

    def __init__(self, id, x, y, z, nx, nz, tx, tz, edge, box, low) -> None:
        self.id = id
        self.x, self.y, self.z = x, y, z
        self.nx, self.nz = nx, nz        # out of the face, toward the spot
        self.tx, self.tz = tx, tz        # along the face, toward the nearer edge
        self.edge = edge                 # metres to that edge
        self.box = box
        self.low = low

    @property
    def pos(self) -> tuple[float, float, float]:
        return self.x, self.y, self.z

    def __repr__(self) -> str:
        return f"Spot({self.id}, {self.x:.2f}, {self.z:.2f}, {'low' if self.low else 'high'})"


def build_spots(world: BoxWorld, walkable: Callable[[float, float], bool],
                floor: Callable[[float, float], float], spacing: float = 1.0,
                offset: float = 0.6, min_h: float = 0.7, low_h: float = 1.35,
                corner: float = 1.2) -> list[Spot]:
    spots: list[Spot] = []
    for bi, (x0, y0, z0, x1, y1, z1) in enumerate(world.boxes):
        # (along-axis span, fixed coordinate, normal) for the four faces
        faces = (("x", x0, x1, z0 - offset, (0.0, -1.0)), ("x", x0, x1, z1 + offset, (0.0, 1.0)),
                 ("z", z0, z1, x0 - offset, (-1.0, 0.0)), ("z", z0, z1, x1 + offset, (1.0, 0.0)))
        for axis, a0, a1, fixed, (nx, nz) in faces:
            n = max(1, int((a1 - a0) / spacing))
            for k in range(n):
                a = a0 + (k + 0.5) * (a1 - a0) / n
                x, z = (a, fixed) if axis == "x" else (fixed, a)
                if not walkable(x, z):
                    continue
                fy = floor(x, z)
                if y1 - fy < min_h or y0 > fy + 0.3:
                    continue
                lo_d, hi_d = a - a0, a1 - a
                sgn = -1.0 if lo_d < hi_d else 1.0
                tx, tz = (sgn, 0.0) if axis == "x" else (0.0, sgn)
                low = y1 - fy < low_h
                edge = min(lo_d, hi_d)   # tall mid-wall spots hide but can't peek
                spots.append(Spot(len(spots), x, fy, z, nx, nz, tx, tz, edge, bi, low))
    return spots


def hides(spot: Spot, threat: Vec3, world: BoxWorld) -> bool:
    """The spot's own box stands between the hidden head and ``threat``."""
    eye = (spot.x, spot.y + (HIDE_EYE_LOW if spot.low else HIDE_EYE_HIGH), spot.z)
    d = (threat[0] - eye[0], threat[1] - eye[1], threat[2] - eye[2])
    dist = math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2])
    if dist < 1e-6:
        return False
    # the threat must be on the box's side of the spot, not behind him
    if (d[0] * spot.nx + d[2] * spot.nz) > 0.0:
        return False
    b = world.boxes[spot.box]
    t = ray_aabb(eye, (d[0] / dist, d[1] / dist, d[2] / dist), b[:3], b[3:])
    return t is not None and t < dist


def peek_point(spot: Spot) -> tuple[float, float, float]:
    """Where he stands to shoot: the spot itself over low cover, past the
    nearer edge for tall cover."""
    if spot.low:
        return spot.pos
    out = spot.edge + 0.45
    return spot.x + spot.tx * out, spot.y, spot.z + spot.tz * out


def can_peek(spot: Spot, threat: Vec3, world: BoxWorld) -> bool:
    px, py, pz = peek_point(spot)
    return not world.segment_blocked((px, py + SHOOT_EYE, pz), threat)


def pick(spots: Iterable[Spot], me: Vec3, threat: Vec3, world: BoxWorld, *,
         band: tuple[float, float] = (4.0, 30.0), ideal: float = 14.0,
         max_travel: float = 16.0, taken: Callable[[Spot], bool] | None = None,
         mates: Sequence[Vec3] = (), spread: float = 3.5, need_peek: bool = True,
         corner: float = 1.2,
         reachable: Callable[[Spot], bool] | None = None, tries: int = 6) -> Spot | None:
    scored = []
    for s in spots:
        travel = math.hypot(s.x - me[0], s.z - me[2])
        if travel > max_travel:
            continue
        td = math.hypot(s.x - threat[0], s.z - threat[2])
        if not band[0] <= td <= band[1]:
            continue
        if need_peek and not s.low and s.edge > corner:
            continue
        if taken is not None and taken(s):
            continue
        if not hides(s, threat, world):
            continue
        cost = travel + abs(td - ideal) * 0.5
        for m in mates:
            dm = math.hypot(s.x - m[0], s.z - m[2])
            if dm < spread:
                cost += (spread - dm) * 2.0
        scored.append((cost, s.id, s))
    scored.sort()
    for _cost, _id, s in scored[:tries]:
        if need_peek and not can_peek(s, threat, world):
            continue
        if reachable is not None and not reachable(s):
            continue
        return s
    return None
