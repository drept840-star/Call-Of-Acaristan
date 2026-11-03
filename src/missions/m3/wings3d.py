"""Mission 3 wings in 2.5D: the comms wing, the archives, the kill order
floor and the broadcast studio, for ``draw3d``.

``draw3d`` owns the frame, the walls, the doors and the cast on every M3
map; this module holds what differs per wing: floor palette, furniture on
the 2D barrier rects, tubes, the story pieces whose look follows the
objective chain (relay, breaker, Vostral case, van, station PC) and the
room plaques. Keys are ``draw._m3_map_key()``.

Props stand on the barrier rects ``world`` builds, so what Biribel bumps
into is what he sees. Pieces with no rect hug a wall and stay shallow.
"""
import math

from core.config import TILE_SIZE
from core.state import STATE
from game import topdown3d as td
from game.topdown3d import K, to3

T = TILE_SIZE
DARK = (34, 36, 38)
STEEL = (70, 74, 78)
WOOD = (92, 70, 48)


def _cr(kind, cx, cy, wpx, hpx):
    """A barrier rect given as centre (tiles) + size (px), as top-left + size in tiles."""
    return (kind, cx - wpx / 2.0 / T, cy - hpx / 2.0 / T, wpx / float(T), hpx / float(T))


# ── floors ─────────────────────────────────────────────────────────────

_GRAVEL = ("ballast", (36, 36, 37))
_HALL = ("pavement", (40, 41, 41))
FLOOR = {
    "comms": {"g": _GRAVEL, ".": _HALL, "P": _HALL, "D": _HALL,
              "O": ("concrete", (37, 43, 45)), "M": ("concrete", (41, 43, 40)),
              "S": ("metal_rib", (46, 50, 56)), "E": ("concrete", (40, 46, 42)),
              "X": ("concrete", (40, 46, 42))},
    "archives": {"g": _GRAVEL, ".": ("pavement", (44, 42, 40)), "P": ("pavement", (44, 42, 40)),
                 "D": ("pavement", (44, 42, 40)), "B": ("pavement", (44, 42, 40)),
                 "O": ("concrete", (40, 42, 46)), "L": ("m7_plank", (58, 46, 34)),
                 "S": ("metal_rib", (50, 54, 60)), "E": ("concrete", (42, 42, 40)),
                 "X": ("concrete", (42, 42, 40))},
    "killorder": {"g": _GRAVEL, ".": _HALL, "P": ("concrete", (44, 45, 44)), "D": _HALL,
                  "E": ("concrete", (44, 45, 44)), "B": ("concrete", (44, 45, 44))},
    "broadcast": {"g": _GRAVEL, ".": _HALL, "P": _HALL, "D": _HALL,
                  "E": ("concrete", (40, 39, 45)), "B": ("concrete", (40, 39, 45))},
}


# ── furniture on the barrier rects ─────────────────────────────────────

PROPS = {
    "comms": (_cr("relay_bank", 19.8, 16.4, 140, 42), _cr("relay_bank", 28.2, 16.4, 140, 42),
              _cr("tuning_desk", 24.0, 19.2, 118, 52),
              _cr("server_rack", 36.0, 18.0, 58, 230), _cr("server_rack", 42.0, 18.0, 58, 230),
              _cr("battery", 17.0, 35.0, 70, 118), _cr("battery", 27.2, 35.0, 70, 118),
              _cr("workbench", 37.5, 25.0, 128, 42),
              ("lockers", 4.1, 19.1, 0.4, 2.6), ("wall_terminal", 12.1, 18.05, 2.8, 0.4),
              ("wall_panel", 21.0, 11.02, 6.0, 0.3), ("cable_tray", 37.2, 14.2, 4.6, 0.35)),
    "archives": (_cr("reception", 24.0, 44.0, 140, 36),
                 _cr("catalog", 8.5, 22.0, 40, 90), _cr("catalog", 14.5, 22.0, 40, 90),
                 _cr("catalog", 8.5, 33.0, 40, 90), _cr("catalog", 14.5, 33.0, 40, 90),
                 _cr("maru_desk", 11.0, 12.0, 96, 48),
                 _cr("desk", 34.0, 22.0, 70, 40), _cr("desk", 38.0, 22.0, 70, 40),
                 _cr("desk", 34.0, 32.0, 70, 40), _cr("desk", 38.0, 32.0, 70, 40),
                 _cr("pedestal", 42.0, 9.0, 70, 70), _cr("card_island", 28.0, 9.0, 120, 40),
                 ("bench", 20.1, 44.55, 2.8, 0.4), ("bench", 26.1, 44.55, 2.8, 0.4),
                 ("vault_case", 37.05, 5.1, 0.45, 8.8), ("vault_case", 45.5, 5.1, 0.45, 8.8),
                 ("filing", 7.05, 9.1, 0.45, 2.4)),
    "killorder": (("stairs", 3.05, 2.05, 2.2, 1.6), ("crane", 7.5, 33.2, 4.0, 3.0),
                  ("crates", 35.1, 33.1, 1.8, 1.8), ("racks", 3.1, 29.05, 8.8, 0.45),
                  ("racks", 15.1, 29.05, 9.8, 0.45), ("racks", 28.1, 29.05, 8.8, 0.45)),
    "broadcast": (("on_air", 14.0, 17.02, 2.0, 0.2),
                  ("light_stand", 4.2, 17.2, 0.6, 0.6), ("light_stand", 27.2, 17.2, 0.6, 0.6),
                  ("pc_desk", 24.3, 26.9, 2.4, 0.9), ("rack_wall", 24.1, 21.05, 3.8, 0.4),
                  ("rack_wall", 4.1, 7.05, 6.8, 0.4), ("lockers", 4.1, 23.1, 0.4, 2.8),
                  ("uplink", 15.1, 26.1, 0.8, 0.8)),
}


def build(r, key):
    """Static wing set: furniture, B-tile pillars or road cases, floor paint."""
    from missions.m3 import draw3d as D
    for kind, x, y, w, h in PROPS.get(key, ()):
        if kind in ("workbench", "bench"):
            D._furniture(r, kind, x, y, w, h)
        else:
            _piece(r, kind, x, y, w, h)
    w, h = D._dims()
    for row in range(h):
        for col in range(w):
            g = D._glyph(col, row)
            if g == "B":
                (_road_case if key == "broadcast" else _pillar)(r, col, row)
            elif g == "S" and key == "comms":
                _floor_grille(r, col, row)
    _paint(r, key)


def _add(r, mesh):
    from cutscenes import m6world3d as _w
    _w.add(r, mesh)


def _pillar(r, col, row):
    from engine3d import box, tex
    x, _, z = to3((col + 0.5) * T, (row + 0.5) * T)
    s = (T - 20) * K
    _add(r, box(s, 2.4, s, tex("concrete", like=(70, 70, 66), tint=True), center=(x, 1.2, z),
                cols={"top": (30, 31, 32)}))
    _add(r, box(s + 0.06, 0.24, s + 0.06, (40, 46, 44), center=(x, 0.12, z), skip=("bottom",)))
    _add(r, box(s + 0.05, 0.12, s + 0.05, (150, 130, 50), center=(x, 1.05, z), skip=("top", "bottom")))


def _road_case(r, col, row):
    from engine3d import box, tex
    x, _, z = to3((col + 0.5) * T, (row + 0.5) * T)
    s = (T - 20) * K
    _add(r, box(s, 0.9, s, tex("crate", like=(64, 60, 52)), center=(x, 0.45, z), cols={"top": (54, 52, 48)}))
    for y in (0.08, 0.82):
        _add(r, box(s + 0.03, 0.06, s + 0.03, (170, 150, 60), center=(x, y, z), skip=("top", "bottom")))
    _add(r, box(s * 0.7, 0.01, 0.1, (26, 26, 26), center=(x, 0.905, z)))


def _floor_grille(r, col, row):
    """Raised-floor tile seams in the server cage."""
    from engine3d import quad_xz
    x0, z0 = col * T * K, -(row + 1) * T * K
    seam = (26, 28, 32)
    _add(r, quad_xz(x0, z0, x0 + T * K, z0 + 0.03, 0.004, seam, layer=1))
    _add(r, quad_xz(x0, z0, x0 + 0.03, z0 + T * K, 0.004, seam, layer=1))


def _stripes(r, x0, z0, x1, z1, n, along_x=True):
    from engine3d import quad_xz
    for i in range(n):
        col = (178, 148, 40) if i % 2 else (30, 30, 28)
        if along_x:
            a = x0 + i * (x1 - x0) / n
            _add(r, quad_xz(a, z0, a + (x1 - x0) / n, z1, 0.006, col, layer=1))
        else:
            a = z0 + i * (z1 - z0) / n
            _add(r, quad_xz(x0, a, x1, a + (z1 - z0) / n, 0.006, col, layer=1))


def _band(r, c0, r0, c1, r1):
    """Hazard band over tiles c0..c1 x r0..r1 (tile edges)."""
    x0, x1 = c0 * T * K, c1 * T * K
    z0, z1 = -r1 * T * K, -r0 * T * K
    along_x = (x1 - x0) >= (z1 - z0)
    n = max(4, int(round(max(x1 - x0, z1 - z0) / 0.4)))
    _stripes(r, x0, z0, x1, z1, n, along_x)


def _paint(r, key):
    from missions.m3 import draw3d as D
    from engine3d import quad_xz, tex
    seam = (28, 31, 33)                          # slab seams every two tiles, as in the cell block
    w, h = D._dims()
    for row in range(0, h, 2):
        for col in range(0, w, 2):
            if D._glyph(col, row) in ("g", "C", "", "S", "L"):
                continue
            sx, sz = col * T * K, -row * T * K
            _add(r, quad_xz(sx - 0.01, sz - 2 * T * K, sx + 0.01, sz, 0.004, seam, layer=1))
            _add(r, quad_xz(sx, sz - 0.01, sx + 2 * T * K, sz + 0.01, 0.004, seam, layer=1))
    if key == "comms":
        _band(r, 33.0, 23.0, 33.25, 27.0)            # server cage threshold
        _band(r, 44.75, 23.0, 45.0, 26.0)            # archive portal
        _band(r, 20.0, 28.9, 23.0, 29.0)
        line = (60, 96, 80)                          # walk line to the relay
        _add(r, quad_xz(23.9 * T * K, -22.0 * T * K, 24.1 * T * K, -20.4 * T * K, 0.005, line, layer=1))
    elif key == "archives":
        _band(r, 21.0, 37.75, 28.0, 38.0)
        _band(r, 21.0, 12.75, 28.0, 13.0)
        _add(r, quad_xz(23.2 * T * K, -37.6 * T * K, 25.8 * T * K, -13.2 * T * K, 0.004, (88, 70, 40), layer=1))
        _add(r, quad_xz(23.32 * T * K, -37.48 * T * K, 25.68 * T * K, -13.32 * T * K, 0.0045,
                        tex("m7_plaster", like=(50, 24, 24), tint=True), layer=1))   # oxblood runner, brass edge
    elif key == "killorder":
        for c0 in (3.0, 15.0, 28.0):
            _band(r, c0, 32.95, c0 + 9.0, 33.2)
        _band(r, 29.0, 37.7, 37.0, 38.0)             # garage shutter line
        bay = (150, 140, 110)
        for i in range(5):                           # dock bay lines
            x = (13.0 + i * 4.0) * T * K
            _add(r, quad_xz(x - 0.03, -37.9 * T * K, x + 0.03, -35.2 * T * K, 0.005, bay, layer=1))
    elif key == "broadcast":
        _band(r, 14.0, 15.75, 18.0, 16.0)
        tape = (150, 140, 60)                        # the set's taped floor and camera marks
        x0, x1, z0, z1 = 9.0 * T * K, 23.0 * T * K, -23.0 * T * K, -18.4 * T * K
        for a, b, c, d in ((x0, z0, x1, z0 + 0.05), (x0, z1 - 0.05, x1, z1),
                           (x0, z0, x0 + 0.05, z1), (x1 - 0.05, z0, x1, z1)):
            _add(r, quad_xz(a, b, c, d, 0.005, tape, layer=1))
        _add(r, quad_xz(x0 + 0.05, z0 + 0.05, x1 - 0.05, z1 - 0.05, 0.004, (46, 40, 58), layer=1))
        for cx, cy in ((12.9, 26.2), (16.9, 26.2), (9.4, 23.6)):
            x, _, z = to3(cx * T, cy * T)
            _add(r, quad_xz(x - 0.3, z - 0.02, x + 0.3, z + 0.02, 0.005, tape, layer=1))
            _add(r, quad_xz(x - 0.02, z - 0.3, x + 0.02, z + 0.3, 0.005, tape, layer=1))
        cable = (22, 22, 24)                         # cable runs from the uplink to the set
        for x, z0, z1 in ((15.0, 23.0, 26.0), (15.3, 23.0, 26.0)):
            _add(r, quad_xz(x * T * K, -z1 * T * K, x * T * K + 0.05, -z0 * T * K, 0.006, cable, layer=1))


def _piece(r, kind, tx, ty, tw, th):
    """One wing piece on its rect (tile units, top-left + size)."""
    from engine3d import Mesh, box, tex
    x, _, z = to3((tx + tw / 2.0) * T, (ty + th / 2.0) * T)
    w, d = tw * T * K, th * T * K
    if kind == "relay_bank":
        _add(r, box(w, 1.0, d, tex("steel", like=(36, 46, 48), tint=True), center=(x, 0.5, z),
                    cols={"top": (44, 56, 58)}))
        _add(r, box(w, 0.5, d * 0.4, (30, 38, 40), center=(x, 1.25, z + d * 0.3)))
        n = max(2, int(w / 0.7))
        for i in range(n):
            sx = x - w / 2.0 + (i + 0.5) * w / n
            _add(r, box(w / n - 0.12, 0.34, 0.02, (36, 92, 78), center=(sx, 1.27, z + d * 0.1 - 0.01),
                        emissive=True))
            for j in range(3):
                col = ((220, 170, 60), (80, 230, 140), (90, 160, 230))[(i + j) % 3]
                _add(r, box(0.05, 0.02, 0.05, col, center=(sx - 0.2 + j * 0.2, 1.01, z - d * 0.2), emissive=True))
    elif kind == "tuning_desk":
        _add(r, box(w, 0.06, d, tex("steel", like=(62, 66, 66)), center=(x, 0.78, z)))
        _add(r, box(w - 0.1, 0.72, d * 0.5, (32, 36, 38), center=(x, 0.38, z + d * 0.2)))
        _add(r, box(0.7, 0.32, 0.42, (40, 44, 42), center=(x - w * 0.25, 0.97, z + 0.1),
                    cols={"top": (54, 58, 54)}))
        for i in range(4):
            _add(r, box(0.06, 0.02, 0.06, (200, 190, 150), center=(x - w * 0.25 - 0.24 + i * 0.16, 1.14, z)))
        _add(r, box(0.05, 1.3, 0.05, DARK, center=(x + w * 0.42, 1.45, z + d * 0.35)))   # antenna whip
    elif kind == "server_rack":
        n = max(1, int(round(d / 0.92)))
        for i in range(n):
            cz = z + d / 2.0 - (i + 0.5) * d / n
            _add(r, box(w, 2.1, d / n - 0.06, tex("steel", like=(30, 32, 36), tint=True), center=(x, 1.05, cz),
                        cols={"top": (40, 42, 46)}))
            for side in (-1.0, 1.0):
                fx = x + side * (w / 2.0 + 0.006)
                for k in range(6):
                    col = (70, 220, 120) if (i + k) % 3 else (90, 150, 240)
                    _add(r, box(0.01, 0.025, 0.05, col, center=(fx, 0.5 + k * 0.24, cz - 0.15 + (k % 2) * 0.22),
                                emissive=True))
                _add(r, box(0.012, 1.7, d / n - 0.2, (22, 24, 26), center=(fx, 1.05, cz)))
    elif kind == "battery":
        _add(r, box(w, 1.5, d, tex("steel", like=(58, 66, 58), tint=True), center=(x, 0.75, z),
                    cols={"top": (64, 72, 62)}))
        _add(r, box(w + 0.02, 0.12, d + 0.02, (170, 140, 40), center=(x, 1.2, z), skip=("top", "bottom")))
        for i in range(3):
            for j in range(2):
                _add(r, box(w * 0.36, 0.14, d * 0.26, (40, 44, 40),
                            center=(x - w * 0.22 + j * w * 0.44, 1.57, z - d * 0.32 + i * d * 0.32)))
        _add(r, box(0.06, 0.06, 0.06, (230, 70, 40), center=(x, 1.3, z - d / 2.0 - 0.02), emissive=True))
    elif kind == "wall_terminal":
        _add(r, box(w, 0.06, d, (56, 58, 58), center=(x, 0.9, z)))
        _add(r, box(w, 0.86, 0.05, (34, 36, 38), center=(x, 0.45, z + d / 2.0 - 0.03)))
        _add(r, box(0.6, 0.42, 0.08, (24, 26, 28), center=(x + 0.4, 1.4, z + d / 2.0 - 0.05)))
        _add(r, box(0.5, 0.32, 0.02, (60, 120, 150), center=(x + 0.4, 1.4, z + d / 2.0 - 0.1), emissive=True))
        _add(r, box(0.3, 0.02, 0.22, (190, 186, 170), center=(x - 0.6, 0.94, z)))
    elif kind == "wall_panel":
        _add(r, box(w, 1.6, d, (34, 40, 42), center=(x, 1.3, z)))
        for i in range(int(w / 0.5)):
            col = (80, 230, 140) if i % 3 else (230, 180, 60)
            _add(r, box(0.06, 0.04, 0.02, col, center=(x - w / 2.0 + 0.25 + i * 0.5, 1.8, z - d / 2.0 - 0.01),
                        emissive=True))
        _add(r, box(w - 0.3, 0.5, 0.02, (30, 64, 58), center=(x, 1.2, z - d / 2.0 - 0.01), emissive=True))
    elif kind == "lockers":                              # a run against the west wall, doors face east
        n = max(1, int(round(d / 0.5)))
        for i in range(n):
            cz = z + d / 2.0 - (i + 0.5) * d / n
            _add(r, box(w, 1.9, d / n - 0.04, tex("steel", like=(52, 64, 60), tint=True), center=(x, 0.95, cz),
                        cols={"top": (66, 78, 72)}))
            for vy in (1.6, 1.68, 1.76):
                _add(r, box(0.02, 0.02, d / n - 0.2, (24, 30, 30), center=(x + w / 2.0 + 0.01, vy, cz)))
    elif kind == "cable_tray":
        _add(r, box(w, 0.06, d, (60, 62, 64), center=(x, 2.4, z)))
        for i in range(3):
            _add(r, box(w, 0.04, 0.04, ((40, 40, 120), (150, 40, 34), (30, 30, 30))[i],
                        center=(x, 2.45, z - 0.1 + i * 0.1)))
    elif kind == "reception":
        wood = tex("crate", like=(86, 64, 44))
        _add(r, box(w, 1.0, d, wood, center=(x, 0.5, z), cols={"top": (96, 74, 52)}))
        _add(r, box(w + 0.08, 0.05, d + 0.08, (120, 96, 64), center=(x, 1.02, z)))
        _add(r, box(0.42, 0.3, 0.05, (30, 32, 34), center=(x - w * 0.25, 1.2, z + 0.1)))
        _add(r, box(0.36, 0.24, 0.01, (120, 170, 190), center=(x - w * 0.25, 1.2, z + 0.07), emissive=True))
        _add(r, box(0.12, 0.3, 0.12, (150, 130, 60), center=(x + w * 0.3, 1.19, z)))
    elif kind == "catalog":
        _add(r, box(w, 1.2, d, tex("crate", like=(88, 64, 42)), center=(x, 0.6, z), cols={"top": (100, 76, 52)}))
        for side in (-1.0, 1.0):
            fx = x + side * (w / 2.0 + 0.005)
            for i in range(4):
                for j in range(3):
                    _add(r, box(0.01, 0.04, 0.12, (170, 150, 90),
                                center=(fx, 0.25 + i * 0.27, z - d / 3.0 + j * d / 3.0)))
    elif kind == "maru_desk":
        _add(r, box(w, 0.06, d, tex("crate", like=(80, 60, 42)), center=(x, 0.76, z)))
        for sx in (-w / 2.0 + 0.06, w / 2.0 - 0.06):
            _add(r, box(0.06, 0.73, d - 0.1, (54, 40, 28), center=(x + sx, 0.365, z)))
        _add(r, box(0.5, 0.36, 0.4, (44, 44, 38), center=(x - w * 0.18, 0.97, z + 0.1), cols={"top": (56, 54, 46)}))
        for i in range(3):
            _add(r, box(0.26, 0.01, 0.2, (190, 180, 150), center=(x + w * 0.2 + i * 0.05, 0.795 + i * 0.002,
                                                                  z - 0.08 + i * 0.04)))
        _add(r, box(0.42, 0.06, 0.42, (34, 38, 38), center=(x, 0.46, z - d / 2.0 - 0.38)))
    elif kind == "desk":
        _add(r, box(w, 0.05, d, (96, 98, 96), center=(x, 0.74, z)))
        _add(r, box(w - 0.08, 0.7, 0.04, (60, 62, 64), center=(x, 0.37, z + d / 2.0 - 0.04)))
        _add(r, box(0.4, 0.28, 0.05, (30, 32, 34), center=(x, 0.93, z + 0.12)))
        _add(r, box(0.34, 0.22, 0.01, (110, 160, 180), center=(x, 0.93, z + 0.09), emissive=True))
        _add(r, box(0.42, 0.06, 0.42, (40, 44, 52), center=(x, 0.46, z - d / 2.0 - 0.35)))
    elif kind == "pedestal":
        _add(r, box(w, 0.9, d, tex("vault", like=(76, 78, 82)), center=(x, 0.45, z), cols={"top": (90, 92, 96)}))
        _add(r, box(w + 0.1, 0.08, d + 0.1, (40, 42, 46), center=(x, 0.04, z)))
        for sx in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                _add(r, box(0.04, 0.5, 0.04, (150, 156, 160), center=(x + sx * (w / 2.0 - 0.06), 1.15,
                                                                      z + sz * (d / 2.0 - 0.06))))
        _add(r, box(w - 0.08, 0.04, d - 0.08, (110, 130, 140), center=(x, 1.42, z)))
    elif kind == "card_island":
        _add(r, box(w, 1.05, d, tex("crate", like=(84, 62, 42)), center=(x, 0.525, z), cols={"top": (98, 74, 50)}))
        for side in (-1.0, 1.0):
            fz = z + side * (d / 2.0 + 0.005)
            for i in range(6):
                for j in range(3):
                    _add(r, box(0.12, 0.04, 0.01, (176, 156, 96), center=(x - w / 2.0 + 0.2 + i * (w - 0.4) / 5.0,
                                                                          0.25 + j * 0.3, fz)))
    elif kind == "vault_case":
        _add(r, box(w, 2.0, d, tex("vault", like=(60, 62, 66)), center=(x, 1.0, z), cols={"top": (40, 42, 46)}))
        n = max(1, int(d / 1.2))
        for i in range(n):
            cz = z + d / 2.0 - (i + 0.5) * d / n
            side = 1.0 if x < 40 * T * K else -1.0
            _add(r, box(0.012, 1.6, d / n - 0.2, (34, 46, 56), center=(x + side * (w / 2.0 + 0.006), 1.0, cz)))
    elif kind == "filing":
        n = max(1, int(round(d / 0.6)))
        for i in range(n):
            cz = z + d / 2.0 - (i + 0.5) * d / n
            _add(r, box(w, 1.3, d / n - 0.04, tex("steel", like=(76, 80, 78)), center=(x, 0.65, cz)))
            for k in range(4):
                _add(r, box(0.01, 0.03, 0.16, (40, 42, 42), center=(x + w / 2.0 + 0.006, 0.2 + k * 0.3, cz)))
    elif kind == "stairs":
        for i in range(5):                               # flight down to the west hall
            _add(r, box(w, 0.06, d / 5.0, (70 - i * 6, 66 - i * 6, 58 - i * 6),
                        center=(x, 0.36 - i * 0.07, z + d / 2.0 - (i + 0.5) * d / 5.0)))
        _add(r, box(0.05, 0.9, d, (90, 92, 90), center=(x + w / 2.0 - 0.03, 0.45, z)))
    elif kind == "crane":
        metal = (96, 88, 56)
        mx, mz = x - w / 2.0 + 0.3, z - d / 2.0 + 0.3
        _add(r, box(0.22, 4.2, 0.22, metal, center=(mx, 2.1, mz)))
        _add(r, box(w, 0.18, 0.18, metal, center=(x, 4.1, mz)))
        hx = mx + w * 0.75
        _add(r, box(0.03, 2.4, 0.03, (40, 40, 36), center=(hx, 2.9, mz)))
        _add(r, box(0.3, 0.22, 0.3, (70, 66, 52), center=(hx, 1.6, mz)))
        _add(r, box(0.5, 0.2, 0.5, (30, 28, 22), center=(mx, 0.1, mz)))
    elif kind == "crates":
        crate = tex("crate", like=(118, 92, 60))
        for i, (ox, oz, s) in enumerate(((0.0, 0.0, 0.9), (0.95, 0.0, 0.85), (0.95, -0.95, 0.9))):
            _add(r, box(s, s, s, crate, center=(x - w / 2.0 + 0.45 + ox, s / 2.0, z + d / 2.0 - 0.45 + oz)))
        _add(r, box(0.8, 0.8, 0.8, crate, center=(x - w / 2.0 + 1.4, 1.3, z + d / 2.0 - 0.45)))
    elif kind == "racks":
        n = max(1, int(w / 1.6))
        for i in range(n):
            cx = x - w / 2.0 + (i + 0.5) * w / n
            for y in (0.4, 1.0, 1.6):
                _add(r, box(w / n - 0.2, 0.05, d, (70, 72, 74), center=(cx, y, z)))
            for sx in (-1.0, 1.0):
                _add(r, box(0.05, 1.7, d, DARK, center=(cx + sx * (w / n / 2.0 - 0.12), 0.85, z)))
            if i % 2 == 0:
                _add(r, box(0.5, 0.36, d - 0.06, tex("crate", like=(110, 88, 56)), center=(cx - 0.2, 0.62, z)))
            else:
                _add(r, box(0.36, 0.4, d - 0.08, (60, 72, 60), center=(cx + 0.2, 1.24, z)))
    elif kind == "on_air":                               # lit sign on the studio's north wall
        _add(r, box(w, 0.4, d, (30, 20, 22), center=(x, 2.3, z)))
        _add(r, box(w - 0.16, 0.26, 0.02, (255, 70, 56), center=(x, 2.3, z - d / 2.0 - 0.01), emissive=True))
    elif kind == "light_stand":
        _add(r, box(0.04, 2.0, 0.04, (40, 42, 44), center=(x, 1.0, z)))
        _add(r, box(0.5, 0.5, 0.2, (24, 24, 26), center=(x, 2.05, z - 0.1)))
        _add(r, box(0.42, 0.42, 0.02, (255, 236, 200), center=(x, 2.05, z - 0.21), emissive=True))
    elif kind == "pc_desk":
        _add(r, box(w, 0.06, d, tex("steel", like=(70, 70, 74)), center=(x, 0.76, z)))
        for sx in (-w / 2.0 + 0.06, w / 2.0 - 0.06):
            _add(r, box(0.06, 0.73, d - 0.1, DARK, center=(x + sx, 0.365, z)))
        _add(r, box(0.56, 0.48, 0.5, (150, 142, 120), center=(x, 1.03, z + 0.1), cols={"top": (166, 158, 136)}))
        _add(r, box(0.7, 0.04, 0.24, (140, 132, 112), center=(x, 0.81, z - 0.26)))
        _add(r, box(0.36, 0.2, 0.3, (140, 132, 112), center=(x + 0.7, 0.89, z)))
    elif kind == "rack_wall":
        n = max(1, int(w / 0.7))
        for i in range(n):
            cx = x - w / 2.0 + (i + 0.5) * w / n
            _add(r, box(w / n - 0.05, 2.0, d, (30, 32, 36), center=(cx, 1.0, z), cols={"top": (40, 42, 46)}))
            for k in range(5):
                col = (70, 220, 120) if (i + k) % 3 else (230, 180, 60)
                _add(r, box(0.05, 0.025, 0.01, col, center=(cx - 0.1 + (k % 2) * 0.2, 0.5 + k * 0.28,
                                                            z - d / 2.0 - 0.006), emissive=True))
    elif kind == "uplink":
        _add(r, box(w, 0.5, d, (40, 44, 48), center=(x, 0.25, z), cols={"top": (54, 58, 62)}))
        _add(r, box(0.08, 0.06, 0.08, (80, 230, 140), center=(x + 0.2, 0.53, z), emissive=True))
        for i in range(3):
            _add(r, box(0.05, 0.03, 1.4, (24, 24, 26), center=(x - 0.2 + i * 0.12, 0.015, z - 0.9)))


# ── lamps ──────────────────────────────────────────────────────────────

_WHITE = (232, 238, 244)
_COOL = (176, 204, 255)
_WARM = (255, 222, 176)
_SODIUM = (255, 196, 128)
_FLOODS = tuple((c, r_, 340, (255, 230, 180), "fl") for c, r_ in ((2.5, 2.5), (45.5, 2.5), (2.5, 45.5), (45.5, 45.5)))
_EMERGENCY = (255, 92, 66)

LAMPS = {
    "comms": ((6.5, 21.5, 190, (214, 230, 240), "room"), (6.5, 26.0, 190, (214, 230, 240), "room"),
              (13.5, 19.6, 150, _WHITE, "room"),
              *((c, 24.5, 170, _WHITE, "cor") for c in (13.5, 19.5, 25.5, 31.0)),
              (19.5, 13.2, 240, (214, 236, 236), "relay"), (28.5, 13.2, 240, (214, 236, 236), "relay"),
              (24.0, 18.0, 200, (170, 246, 210), "relay"),
              (39.0, 16.0, 200, _COOL, "srv"), (39.0, 21.5, 200, _COOL, "srv"), (39.0, 26.5, 200, _COOL, "srv"),
              (45.5, 24.0, 140, (140, 255, 190), "exit"),
              (17.5, 32.0, 220, (250, 226, 186), "bat"), (26.0, 32.0, 220, (250, 226, 186), "bat"),
              (21.5, 37.0, 220, (250, 226, 186), "bat"),
              *_FLOODS),
    "archives": ((21.8, 41.5, 210, _WARM, "room"), (26.2, 41.5, 210, _WARM, "room"),
                 *((24.0, r_, 210, (246, 230, 200), "atr") for r_ in (15.5, 21.0, 26.5, 32.0, 36.0)),
                 *((c, r_, 170, _WARM, "stk") for c in (8.5, 14.5) for r_ in (20.5, 25.0, 30.5, 34.5)),
                 (18.5, 24.5, 160, _WARM, "stk"),
                 (9.5, 11.0, 180, (255, 206, 140), "room"), (13.5, 15.5, 180, (255, 206, 140), "room"),
                 (23.5, 9.0, 200, _WHITE, "room"), (32.0, 9.0, 200, _WHITE, "room"),
                 (25.0, 4.2, 150, (140, 255, 190), "exit"),
                 (41.0, 7.0, 200, _COOL, "vault"), (41.0, 11.5, 200, _COOL, "vault"),
                 *((c, r_, 180, _WHITE, "room") for c in (30.5, 34.5, 38.5, 41.5) for r_ in (21.5, 29.0, 33.5)),
                 *_FLOODS),
    "killorder": ((6.0, 4.5, 170, _WHITE, "room"),
                  *((5.0, r_, 170, _WHITE, "cor") for r_ in (11.0, 17.5, 24.0)),
                  *((32.0, r_, 170, _WHITE, "cor") for r_ in (11.0, 17.5, 24.0)),
                  *((c, r_, 230, (236, 240, 246), "lobby") for c in (12.0, 19.0, 26.0) for r_ in (10.5, 17.5)),
                  (12.0, 24.0, 230, (236, 240, 246), "lobby"), (19.0, 24.0, 230, (236, 240, 246), "lobby"),
                  (25.5, 23.5, 150, (255, 150, 120), "room"),
                  (11.8, 12.5, 120, _WHITE, "room"), (11.8, 20.5, 120, _WHITE, "room"),
                  (7.0, 30.0, 190, _WARM, "room"), (19.5, 30.0, 190, _WARM, "room"), (32.0, 30.0, 190, _WARM, "room"),
                  *((c, 35.0, 260, _SODIUM, "dock") for c in (7.0, 15.0, 23.0)),
                  (33.0, 34.2, 240, _SODIUM, "dock"),
                  *_FLOODS),
    "broadcast": ((15.5, 3.0, 160, _WHITE, "room"), (15.5, 8.0, 170, _WHITE, "cor"), (15.5, 12.5, 170, _WHITE, "cor"),
                  (7.0, 8.0, 160, _WARM, "room"), (24.0, 8.0, 160, _COOL, "room"),
                  (8.0, 19.5, 230, (255, 214, 176), "studio"), (16.0, 19.5, 230, (246, 240, 236), "studio"),
                  (23.0, 19.5, 230, (180, 206, 255), "studio"), (12.0, 25.5, 230, (246, 240, 236), "studio"),
                  (19.0, 25.5, 230, (246, 240, 236), "studio"),
                  (5.8, 25.5, 150, _WARM, "room"), (25.5, 22.5, 150, _COOL, "room"),
                  (25.5, 27.2, 150, (140, 255, 180), "room"),
                  (2.0, 2.0, 300, (255, 230, 180), "fl"), (29.5, 2.0, 300, (255, 230, 180), "fl"),
                  (2.0, 29.5, 300, (255, 230, 180), "fl"), (29.5, 29.5, 300, (255, 230, 180), "fl")),
}
# The grade's multiply floor per wing: lower than the cell block's but the
# wings are wider rooms, so the dark between lamps must still read.
AMBIENT = {"comms": (176, 170, 172), "archives": (184, 180, 174), "killorder": (186, 188, 190),
           "broadcast": (184, 182, 190)}
POOL_K = {"room": 0.45, "cor": 0.5, "relay": 0.5, "srv": 0.45, "bat": 0.48, "atr": 0.5, "stk": 0.45,
          "vault": 0.5, "lobby": 0.5, "dock": 0.55, "studio": 0.5}


def lamps(key):
    """This wing's lamps as (col, row, reach, colour, key); the comms tubes
    over the relay and the servers go to emergency red until the power is
    back."""
    base = _LIT.get(key)
    if base is None:                            # wing rooms are bigger than the cells: longer throws
        base = _LIT[key] = tuple((c, r_, rad if k == "fl" else int(rad * 1.35), col, k)
                                 for c, r_, rad, col, k in LAMPS.get(key, ()))
    if key != "comms" or getattr(STATE, "m3_comms_power_restored", False):
        return base
    dark = _LIT.get("comms_dark")
    if dark is None:
        dark = _LIT["comms_dark"] = tuple((c, r_, int(rad * 0.9), _EMERGENCY, k) if k in ("relay", "srv")
                                          else (c, r_, rad, col, k) for c, r_, rad, col, k in base)
    return dark


_LIT = {}


def dyn_lights(key, tm):
    """Per-frame grade lights: the relay's state glow, the kill order alarm."""
    out = []
    t = tm / 1000.0
    if key == "comms":
        x, _, z = to3(24.5 * T, 19.5 * T)
        if getattr(STATE, "m3_comms_power_restored", False):
            col = (90, 255, 150) if getattr(STATE, "m3_relay_tuned", False) else (220, 190, 90)
            out.append(("pool", (x, 0.0, z), col, 3.2, 0.35))
        else:
            out.append(("pool", (x, 0.0, z), _EMERGENCY, 6.0, 0.12 + 0.12 * (0.5 + 0.5 * math.sin(t * 3.0))))
    elif key == "killorder" and getattr(STATE, "m3_alarm_active", False):
        p = STATE.player
        if p is not None:
            x, _, z = to3(p.rect.centerx, p.rect.centery)
            k = 0.5 + 0.5 * math.sin(t * 4.0)
            out.append(("pool", (x, 0.0, z), (255, 50, 36), 9.0, 0.1 + 0.16 * k))
    for col, row in _x_tiles(key):
        x, _, z = to3((col + 0.5) * T, (row + 0.5) * T)
        out.append(("pool", (x, 0.0, z), (90, 255, 150), 1.6, 0.25 + 0.15 * math.sin(t * 3.0)))
    return out


def _x_tiles(key):
    from missions.m3 import draw3d as D
    hit = _X.get(key)
    if hit is None:
        w, h = D._dims()
        hit = _X[key] = tuple((c, r_) for r_ in range(h) for c in range(w) if D._glyph(c, r_) == "X")
    return hit


_X = {}


# ── live pieces ────────────────────────────────────────────────────────

def draw_live(r, key, tm, flashes):
    """The pieces whose look follows the objective chain, per frame."""
    from missions.m3 import draw3d as D
    from engine3d import box
    from cutscenes import m6fx3d as _fx
    t = tm / 1000.0
    pulse = 0.5 + 0.5 * math.sin(t * 3.0)
    for col, row in _x_tiles(key):                 # the 2D objective beacon, as a floor ring
        x, _, z = to3((col + 0.5) * T, (row + 0.5) * T)
        g = int(150 + 90 * pulse)
        D._put(r, D._mesh(("xring", g // 16), lambda g=g: _ring(0.62, (60, g, 120))), (x, 0.0, z))
    if key == "comms":
        powered = getattr(STATE, "m3_comms_power_restored", False)
        tuned = getattr(STATE, "m3_relay_tuned", False)
        auth = getattr(STATE, "m3_comms_auth_acquired", False)
        x, _, z = to3(24.0 * T, 19.2 * T)
        col = ((80, 240, 150) if tuned else (230, 190, 80) if powered and auth else
               (200, 120, 60) if powered else (150, 30, 24))
        D._put(r, D._mesh(("relay_scr", col), lambda c=col: box(0.6, 0.02, 0.3, c, center=(0.0, 1.14, 0.0),
                                                                emissive=True)), (x - 0.47, 0.0, z + 0.1))
        bx, _, bz = to3(29.75 * T, 36.5 * T)
        D._put(r, D._mesh(("breaker", powered), lambda: _breaker(powered)), (bx, 0.0, bz))
        ax, _, az = to3(13.5 * T, 18.25 * T)
        led = (80, 230, 140) if auth else (230, 60, 40)
        D._put(r, D._mesh(("auth_led", led), lambda c=led: box(0.06, 0.06, 0.02, c, center=(0.0, 1.62, 0.0),
                                                               emissive=True)), (ax, 0.0, az))
    elif key == "archives":
        x, _, z = to3(11.0 * T, 12.0 * T)
        on = getattr(STATE, "m3_maru_contacted", False)
        col = (90, 230, 150) if on else (int(200 + 50 * pulse), 150, 60)
        D._put(r, D._mesh(("maru_scr", col), lambda c=col: box(0.36, 0.02, 0.26, c, center=(0.0, 1.16, 0.0),
                                                               emissive=True)), (x - 0.27, 0.0, z + 0.1))
        if not getattr(STATE, "m3_vostral_acquired", False):
            vx, _, vz = to3(42.5 * T, 9.5 * T)
            D._put(r, D._mesh(("vostral",), _vostral), (vx, 0.0, vz))
            r.add_sprite((vx, 1.1, vz), D._glow((255, 120, 90), 0.4, tm, 0.35 + 0.2 * pulse, 14), layer=_fx.FX_LAYER)
    elif key == "killorder":
        bailed = getattr(STATE, "m3_volkov_bailed", False)
        if not bailed:
            vx, _, vz = to3((31.0 + 0.125 + 1.875) * T, (35.0 + 0.03 + 0.64) * T)
            D._put(r, D._mesh(("van",), _van), (vx, 0.0, vz))
            b = 0.55 + 0.45 * math.sin(t * 5.0)
            head = (vx + 0.55, 2.05, vz + 0.2)
            r.add_sprite(head, D._glow((255, int(130 + 70 * b), 60), 0.3, tm, 0.5 + 0.4 * b, 14), layer=_fx.FX_LAYER)
            flashes.append({"pos": head, "color": (255, 170, 70), "intensity": 0.4 + 0.3 * b, "range": 3.5})
        else:
            ex, _, ez = to3(33.5 * T, 36.5 * T)
            D._put(r, D._mesh(("cage",), _cage), (ex, 0.0, ez))
        cyc = getattr(STATE, "m3_exfil_door_cycle", 0)
        shut = 1.0 - min(1.0, cyc / 2700.0) if cyc > 0 else 1.0
        sx, _, sz = to3(33.0 * T, 38.5 * T)
        D._put(r, D._mesh(("shutter", round(shut, 1)), lambda s=round(shut, 1): _shutter(s)), (sx, 0.0, sz))
    elif key == "broadcast":
        x, _, z = to3(25.5 * T, 27.35 * T)
        ready = getattr(STATE, "m3_bcast_pc_ready", False)
        g = int(150 + 80 * pulse) if ready else 90
        col = (60, g, 120) if ready else (40, 70, 60)
        D._put(r, D._mesh(("pc_scr", col), lambda c=col: box(0.42, 0.32, 0.02, c, center=(0.0, 1.05, 0.0),
                                                             emissive=True)), (x, 0.0, z - 0.17))
        if ready:
            r.add_sprite((x, 1.05, z - 0.2), D._glow((120, 255, 170), 0.35, tm, 0.3 + 0.2 * pulse, 12),
                         layer=_fx.FX_LAYER)


def _ring(rad, col):
    from engine3d import Mesh, box
    m = Mesh()
    n = 12
    for i in range(n):
        a = 2 * math.pi * i / n
        m.add(box(rad * 0.52, 0.01, 0.06, col, center=(math.cos(a) * rad, 0.008, math.sin(a) * rad), emissive=True),
              m=_rot(-math.degrees(a) + 90.0))
    return m


def _rot(deg):
    from engine3d import rot_y
    return rot_y(deg)


def _breaker(on):
    from engine3d import Mesh, box
    m = Mesh()
    m.add(box(0.3, 1.1, 0.9, (58, 62, 60), center=(0.0, 1.25, 0.0), cols={"top": (70, 74, 70)}))
    m.add(box(0.02, 0.9, 0.7, (40, 44, 42), center=(-0.16, 1.25, 0.0)))
    m.add(box(0.14, 0.06, 0.06, (200, 170, 50), center=(-0.22, 1.5 if on else 1.0, 0.0)))
    m.add(box(0.03, 0.06, 0.06, (80, 230, 140) if on else (230, 60, 40), center=(-0.17, 1.72, 0.25), emissive=True))
    return m


def _vostral():
    from engine3d import Mesh, box
    m = Mesh()
    m.add(box(0.36, 0.04, 0.26, (150, 120, 70), center=(0.0, 0.93, 0.0)))
    m.add(box(0.3, 0.01, 0.2, (200, 60, 50), center=(0.0, 0.955, 0.0)))
    return m


def _van():
    from engine3d import Mesh, box, tex
    m = Mesh()
    L, W = 3.75 * T * K, 1.28 * T * K
    body = tex("steel", like=(62, 68, 76), tint=True)
    m.add(box(L - 0.9, 1.9, W, body, center=(0.45, 1.15, 0.0), cols={"top": (70, 76, 84)}))
    m.add(box(0.9, 1.3, W - 0.06, body, center=(-L / 2.0 + 0.45, 0.85, 0.0), cols={"top": (40, 44, 51)}))
    m.add(box(0.05, 0.5, W - 0.2, (104, 138, 158), center=(-L / 2.0 + 0.92, 1.6, 0.0)))   # windshield
    m.add(box(0.3, 0.04, W - 0.3, (104, 138, 158), center=(-L / 2.0 + 0.75, 1.5, 0.0)))
    for sx in (-1.0, 1.0):
        m.add(box(0.06, 0.14, 0.2, (235, 220, 160), center=(-L / 2.0 + 0.02, 0.7, sx * (W / 2.0 - 0.25)),
                  emissive=True))
        m.add(box(0.04, 0.16, 0.2, (190, 44, 40), center=(L / 2.0 - 0.02, 0.9, sx * (W / 2.0 - 0.25)),
                  emissive=True))
        for wx in (-L / 2.0 + 0.7, L / 2.0 - 0.8):
            m.add(box(0.62, 0.62, 0.2, (14, 15, 17), center=(wx, 0.31, sx * (W / 2.0 - 0.06))))
    m.add(box(1.4, 1.5, 0.02, (255, 214, 150), center=(0.6, 1.0, -W / 2.0 - 0.01), emissive=True))   # open door
    m.add(box(0.5, 0.36, 0.5, (96, 74, 46), center=(0.6, 0.4, -W / 2.0 + 0.4)))
    m.add(box(0.4, 0.16, 0.5, (54, 58, 66), center=(0.0, 2.18, 0.2)))
    m.add(box(0.16, 0.12, 0.16, (230, 160, 60), center=(0.55, 2.16, 0.2), emissive=True))
    return m


def _cage():
    from engine3d import Mesh, box
    m = Mesh()
    m.add(box(0.06, 2.6, 0.06, (90, 84, 60), center=(0.0, 1.3, 0.0)))
    for i in range(5):
        m.add(box(0.5, 0.04, 0.04, (70, 66, 50), center=(0.0, 0.4 + i * 0.45, 0.0)))
    m.add(box(0.8, 0.3, 0.6, (60, 56, 44), center=(0.0, 0.15, -0.3)))
    return m


def _shutter(closed):
    from engine3d import Mesh, box
    m = Mesh()
    w = 6 * T * K
    h = 2.6 * closed
    if h > 0.05:
        m.add(box(w, h, 0.12, (52, 56, 60), center=(0.0, 2.6 - h / 2.0, 0.0)))
        for i in range(int(h / 0.2)):
            m.add(box(w, 0.02, 0.13, (34, 36, 40), center=(0.0, 2.6 - 0.1 - i * 0.2, 0.0)))
    m.add(box(w + 0.2, 0.3, 0.3, (40, 42, 44), center=(0.0, 2.75, 0.0)))
    return m


# ── room plaques ───────────────────────────────────────────────────────

# (col, row of the room's inside top-left corner, text): drawn on the
# north wall's inside face, like the cell plaques.
PLAQUES = {
    "comms": ((4.2, 19.0, "AIRLOCK"), (12.1, 18.0, "SECURITY"), (16.2, 11.0, "RELAY ROOM"),
              (35.2, 14.0, "SERVER CAGE"), (14.2, 30.0, "BATTERY BACKUP"), (11.2, 23.0, "SERVICE CORRIDOR")),
    "archives": ((19.2, 39.0, "ELEVATOR LOBBY"), (21.2, 13.0, "ATRIUM"), (5.2, 19.0, "CATALOG STACKS"),
                 (7.2, 9.0, "CLERK OFFICE"), (29.2, 19.0, "RESEARCH"), (21.2, 7.0, "SECURITY VESTIBULE"),
                 (37.2, 5.0, "VAULT"), (23.2, 3.0, "STAIRWELL")),
    "killorder": ((3.2, 2.0, "STAIRWELL"), (3.1, 9.0, "WEST HALL"), (9.2, 9.0, "MAIN LOBBY"),
                  (30.1, 9.0, "EAST HALL"), (24.2, 22.0, "MEZZANINE"), (3.2, 29.0, "STORAGE A"),
                  (15.2, 29.0, "STORAGE B"), (28.2, 29.0, "STORAGE C"), (3.2, 33.0, "LOADING DOCK")),
    "broadcast": ((13.2, 2.0, "LIFT"), (4.2, 7.0, "EDIT BAY"), (21.2, 7.0, "EQUIPMENT"),
                  (4.2, 17.0, "STUDIO A"), (24.2, 21.0, "SUITE"), (24.2, 26.0, "UPLINK"),
                  (4.2, 23.0, "GREEN ROOM")),
}
ACCENT = {"comms": (110, 210, 160), "archives": (230, 190, 110), "killorder": (220, 120, 90),
          "broadcast": (190, 160, 240)}
