"""m7goat3d.py - 3D engine3d takes for Mission 7's goat-escape bridge.

Stages all five shots of ``m7.goat.escape`` in the real 3D Bodi farmyard
(``cutscenes.m7world3d.stage("dawn", ...)``) so the bridge matches the rest
of Mission 7 visually, with articulated 3D goats, leaning pen post & snapping
wire, feed/water buckets, and Bodi & Biribel 3D rigs:

    pen       wide yard: Bodi & Biribel finish chores; cream goat works the wire
    slip      tight on the loose post: wire snaps and the cream goat slips out
    orchard   she bolts east toward the orchard trees; Bodi sees the open gap
    potatoes  two-shot: Biribel asks if that is bad
    bodi      close on Bodi holding a coil of repair wire ("For my potatoes, yeah.")

Falls back cleanly to ``cutscenes.m7goat`` 2D takes when ACARISTAN_CUTSCENE3D=0
or on error. Pure functions of t; zero mission imports.
"""
import math
import os

from core.outfits import OUTFIT_GUARD
from engine3d.core import Mesh, box, m_mul, rot_x, rot_y, rot_z
from cutscenes import m6world3d as _w
from cutscenes import m7world3d as F

__all__ = ["SCENES", "m7goat3d_enabled", "draw_scene"]

SCENES = ("pen", "slip", "orchard", "potatoes", "bodi")
_BIRI = ("biribel", OUTFIT_GUARD)
_BODI = "bodi"

# Goat pen sits in the sunny southeast farmyard between well (1,4), barn (13,12),
# and the east orchard fence (x=20): x in [6.5, 13.5], z in [-6.0, -1.0].
_PEN_X0, _PEN_X1 = 6.5, 13.5
_PEN_Z0, _PEN_Z1 = -6.0, -1.0
_LOOSE_POST = (13.5, 0.0, -3.5)

_GOAT_CREAM = (224, 216, 200)
_GOAT_GREY = (146, 142, 136)
_GOAT_BROWN = (138, 96, 66)
_HOOF = (52, 46, 42)
_HORN = (176, 158, 122)

_S = {"failed": False, "err": None}


def m7goat3d_enabled():
    if os.environ.get("ACARISTAN_CUTSCENE3D", "1").strip() == "0":
        return False
    return not _S["failed"]


def _face(a, b):
    return _w.yaw_to(a, b)


def _goat_mesh(coat, t, phase=0.0, walk=0.0, head_down=0.0, push_head=0.0):
    """Articulated low-poly 3D goat in local +Z forward space."""
    m = Mesh()
    dark = tuple(max(0, c - 26) for c in coat)
    sec = t * 0.001
    stride = math.sin(sec * 7.2 + phase) * 26.0 * walk
    bob = abs(math.sin(sec * 7.2 + phase)) * 0.04 * walk

    # Torso & chest
    m.add(box(0.32, 0.34, 0.72, coat, center=(0.0, 0.62 + bob, 0.0)))
    m.add(box(0.28, 0.28, 0.22, dark, center=(0.0, 0.60 + bob, 0.28)))
    # Up-tilted stub tail
    m.add(box(0.08, 0.14, 0.08, dark), m=rot_x(-34.0), t=(0.0, 0.78 + bob, -0.38))

    # 4 articulated legs
    leg_specs = (
        (-0.11, 0.24, stride),
        (0.11, 0.24, -stride),
        (-0.11, -0.24, -stride),
        (0.11, -0.24, stride),
    )
    for lx, lz, ang in leg_specs:
        leg = Mesh()
        leg.add(box(0.075, 0.44, 0.075, dark, center=(0.0, -0.22, 0.0)))
        leg.add(box(0.082, 0.08, 0.09, _HOOF, center=(0.0, -0.44, 0.01)))
        m.add(leg, m=rot_x(ang), t=(lx, 0.48 + bob, lz))

    # Neck + head + snout + beard + curved horns + ears
    neck_p = 18.0 + 36.0 * head_down - 12.0 * push_head
    head_y = math.sin(sec * 2.5 + phase) * 8.0 + push_head * 10.0 * math.sin(sec * 9.0)
    head_grp = Mesh()
    head_grp.add(box(0.16, 0.30, 0.16, coat, center=(0.0, 0.14, 0.06)))
    # Skull & tapered snout
    head_grp.add(box(0.17, 0.16, 0.22, coat, center=(0.0, 0.28, 0.14)))
    head_grp.add(box(0.11, 0.10, 0.16, dark, center=(0.0, 0.24, 0.28)))
    # Chin beard
    head_grp.add(box(0.05, 0.11, 0.05, dark, center=(0.0, 0.16, 0.25)))
    # Ears
    for sx in (-1, 1):
        head_grp.add(box(0.10, 0.04, 0.06, dark, center=(sx * 0.12, 0.32, 0.10)))
        # Swept-back horns
        horn = Mesh()
        horn.add(box(0.036, 0.18, 0.036, _HORN, center=(0.0, 0.09, 0.0)))
        head_grp.add(horn, m=m_mul(rot_x(-38.0), rot_z(sx * 16.0)),
                     t=(sx * 0.055, 0.36, 0.09))
    m.add(head_grp, m=m_mul(rot_y(head_y), rot_x(neck_p)), t=(0.0, 0.72 + bob, 0.30))
    return m


def _put_goat(r, coat, pos, yaw, t, phase=0.0, walk=0.0, head_down=0.0, push_head=0.0):
    gm = _goat_mesh(coat, t, phase=phase, walk=walk, head_down=head_down, push_head=push_head)
    out = Mesh()
    out.add(gm, m=rot_y(yaw), t=pos)
    _w.add(r, out)
    r.add_blob_shadow((pos[0], 0.02, pos[2]), 0.42, 0.42, 0.40)


def _draw_pen_and_wire(r, t, lean_deg=0.0, snapped=False):
    """Wooden goat pen + the loose east post whose wire snaps."""
    m = Mesh()
    wood = F.WOOD
    wood_d = F.WOOD_D
    # North, west, south solid rail runs
    posts = [
        (_PEN_X0, _PEN_Z0), (10.0, _PEN_Z0), (_PEN_X1, _PEN_Z0),
        (_PEN_X0, -3.5),
        (_PEN_X0, _PEN_Z1), (10.0, _PEN_Z1), (_PEN_X1, _PEN_Z1),
    ]
    for px, pz in posts:
        m.add(box(0.14, 1.18, 0.14, wood_d, center=(px, 0.59, pz)))
    # Horizontal timber rails on N/W/S sides
    for y in (0.42, 0.88):
        m.add(box(_PEN_X1 - _PEN_X0, 0.09, 0.07, wood, center=(10.0, y, _PEN_Z0)))
        m.add(box(_PEN_X1 - _PEN_X0, 0.09, 0.07, wood, center=(10.0, y, _PEN_Z1)))
        m.add(box(0.07, 0.09, _PEN_Z1 - _PEN_Z0, wood, center=(_PEN_X0, y, -3.5)))
    # Wooden feed trough inside the pen
    m.add(box(1.5, 0.34, 0.46, wood_d, center=(8.6, 0.17, -4.8)))
    m.add(box(1.36, 0.10, 0.34, F.HAY, center=(8.6, 0.34, -4.8)))

    # The loose east center post at (13.5, 0, -3.5) that tilts outward as the goat leans on it
    post = Mesh()
    post.add(box(0.14, 1.18, 0.14, wood_d, center=(0.0, 0.59, 0.0)))
    m.add(post, m=rot_z(-lean_deg), t=_LOOSE_POST)
    _w.add(r, m)

    # Wire strands spanning the east gap (z = -6.0 -> -3.5 -> -1.0)
    wire_col = (176, 174, 156)
    top_dx = math.sin(math.radians(lean_deg)) * 0.92
    for wy in (0.36, 0.64, 0.92):
        mid = (_LOOSE_POST[0] + top_dx * (wy / 0.92), wy, _LOOSE_POST[2])
        if not snapped:
            r.add_line3d((_PEN_X1, wy, _PEN_Z0), mid, wire_col, 2, layer=3)
            r.add_line3d(mid, (_PEN_X1, wy, _PEN_Z1), wire_col, 2, layer=3)
        else:
            # Snapped loose wire ends recoiling and drooping into the grass
            r.add_line3d((_PEN_X1, wy, _PEN_Z0), (_PEN_X1 + 0.35, wy * 0.38, _PEN_Z0 + 0.95),
                         wire_col, 2, layer=3)
            r.add_line3d((_PEN_X1, wy, _PEN_Z1), (_PEN_X1 + 0.25, wy * 0.30, _PEN_Z1 - 0.85),
                         wire_col, 2, layer=3)


def _draw_bucket(r, pos, fill_col):
    m = Mesh()
    m.add(box(0.30, 0.32, 0.30, F.METAL, center=(pos[0], pos[1] + 0.16, pos[2])))
    m.add(box(0.24, 0.03, 0.24, fill_col, center=(pos[0], pos[1] + 0.31, pos[2])))
    _w.add(r, m)


def _stage_yard(t, eye, tgt, fov, seed):
    r, buf = F.stage("dawn", t, eye, tgt, fov, hh=0.007, seed=seed)
    F.mist(r, t, seed=seed, n=7, intensity=0.07)
    F.sun(r, t, (96.0, 14.0, 34.0))
    return r, buf


# ── Shot 1: pen ───────────────────────────────────────────────────────────

def pen(surface, t):
    """Last chore lands; the cream goat works the loose east fence wire."""
    u = F.k(t, 0, 3600)
    eye = F.mix((1.8, 2.25, -13.0), (3.4, 2.05, -11.4), u)
    tgt = F.mix((7.6, 1.15, -3.5), (10.4, 1.00, -3.5), u)
    r, buf = _stage_yard(t, eye, tgt, 50, seed=71)

    lean = 6.0 + 10.0 * math.sin(F.k(t, 400, 2600) * math.pi * 0.5)
    _draw_pen_and_wire(r, t, lean_deg=lean, snapped=False)
    _draw_bucket(r, (4.3, 0.0, -3.8), F.HAY)
    _draw_bucket(r, (5.7, 0.0, -4.3), (112, 134, 136))

    bodi_pos = (4.0, 0.0, -3.4)
    biri_pos = (5.4, 0.0, -4.1)
    _w.actor(r, _BODI, F.stand_pose(spine=4, rsh_p=16, head_y=-14), bodi_pos,
             _face(bodi_pos, biri_pos), t, seed=61, amp=0.30, expression="neutral")
    _w.actor(r, _BIRI, F.stand_pose(spine=5, rsh_p=14, head_y=12), biri_pos,
             _face(biri_pos, bodi_pos), t, seed=52, amp=0.25, expression="neutral")

    # Cream goat working the loose wire; grey & brown goats grazing inside pen
    _put_goat(r, _GOAT_CREAM, (12.85 + 0.25 * u, 0.0, -3.45), 88.0, t, phase=0.4,
              walk=0.2, push_head=1.0)
    _put_goat(r, _GOAT_GREY, (9.4, 0.0, -4.4), -38.0, t, phase=1.8, head_down=0.85)
    _put_goat(r, _GOAT_BROWN, (8.2, 0.0, -2.5), 42.0, t, phase=3.1, head_down=0.65)
    F.finish(surface, r, buf, 71, "M7", t)


# ── Shot 2: slip ──────────────────────────────────────────────────────────

def slip(surface, t):
    """Close on the loose post: the wire snaps and the cream goat slips free."""
    snap = t >= 1200.0
    u_push = F.k(t, 0, 1200)
    u_bolt = F.k(t, 1200, 1800)
    eye = F.mix((11.6, 1.15, -6.6), (12.4, 1.10, -6.1), F.k(t, 0, 2800))
    tgt = F.mix((13.4, 0.72, -3.5), (15.6, 0.72, -3.3), u_bolt)
    r, buf = _stage_yard(t, eye, tgt, 40, seed=72)

    lean = 12.0 + 18.0 * u_push + (22.0 * F.k(t, 1200, 500) if snap else 0.0)
    _draw_pen_and_wire(r, t, lean_deg=lean, snapped=snap)

    gx = 12.95 + 0.35 * u_push + 3.4 * u_bolt
    _put_goat(r, _GOAT_CREAM, (gx, 0.0, -3.5 + 0.25 * u_bolt), 86.0, t, phase=0.2,
              walk=0.35 + 0.95 * u_bolt, push_head=1.0 - u_bolt)
    _put_goat(r, _GOAT_GREY, (10.2, 0.0, -4.2), 75.0, t, phase=1.8, head_down=0.2)
    F.finish(surface, r, buf, 72, "M7", t)


# ── Shot 3: orchard ───────────────────────────────────────────────────────

def orchard(surface, t):
    """She bolts east toward the orchard trees; Bodi sees the broken pen."""
    u = F.k(t, 0, 3200)
    eye = F.mix((2.4, 2.0, -9.8), (3.8, 1.9, -9.2), u)
    tgt = F.mix((11.8, 1.05, -3.2), (17.5, 1.05, -2.2), u)
    r, buf = _stage_yard(t, eye, tgt, 46, seed=73)

    _draw_pen_and_wire(r, t, lean_deg=44.0, snapped=True)
    _draw_bucket(r, (4.3, 0.0, -3.8), F.HAY)
    _draw_bucket(r, (5.7, 0.0, -4.3), (112, 134, 136))

    # Bodi & Biribel turn sharply east toward the escaping goat
    bodi_pos = (4.2, 0.0, -3.5)
    biri_pos = (5.6, 0.0, -4.2)
    gx = 16.5 + 6.5 * u
    goat_pos = (gx, 0.0, -2.6 + 1.2 * u)
    _w.actor(r, _BODI, F.stand_pose(spine=6, head_y=8, rsh_p=18), bodi_pos,
             _face(bodi_pos, goat_pos), t, seed=61, amp=0.30, expression="worried")
    _w.actor(r, _BIRI, F.stand_pose(spine=4, head_y=-4), biri_pos,
             _face(biri_pos, goat_pos), t, seed=52, amp=0.25, expression="neutral")

    _put_goat(r, _GOAT_CREAM, goat_pos, 78.0, t, phase=2.0, walk=1.35)
    _put_goat(r, _GOAT_GREY, (9.8, 0.0, -4.4), 82.0, t, phase=1.4, head_down=0.0)
    _put_goat(r, _GOAT_BROWN, (8.4, 0.0, -2.4), 88.0, t, phase=3.0, head_down=0.0)
    F.finish(surface, r, buf, 73, "M7", t)


# ── Shot 4: potatoes ──────────────────────────────────────────────────────

def potatoes(surface, t):
    """Two-shot: Biribel asks the obvious question."""
    u = F.k(t, 0, 2800)
    eye = F.mix((4.7, 1.55, -7.2), (4.8, 1.54, -6.8), u)
    tgt = (4.85, 1.48, -3.8)
    r, buf = _stage_yard(t, eye, tgt, 38, seed=74)

    _draw_pen_and_wire(r, t, lean_deg=44.0, snapped=True)
    bodi_pos = (4.1, 0.0, -3.6)
    biri_pos = (5.6, 0.0, -4.0)
    _w.actor(r, _BODI, F.stand_pose(spine=4, head_y=-8), bodi_pos,
             _face(bodi_pos, biri_pos), t, seed=61, amp=0.25, expression="neutral")
    _w.actor(r, _BIRI, F.stand_pose(spine=5, rsh_p=18, rel=38, head_y=6), biri_pos,
             _face(biri_pos, bodi_pos), t, seed=52, amp=0.30, expression="neutral")
    F.finish(surface, r, buf, 74, "M7", t)


# ── Shot 5: bodi ──────────────────────────────────────────────────────────

def bodi(surface, t):
    """Dirty single on Bodi raising a coil of fence wire."""
    u = F.k(t, 0, 2800)
    lift = F.k(t, 500, 900)
    eye = F.mix((6.1, 1.62, -6.4), (5.8, 1.60, -5.9), u)
    tgt = (4.15, 1.48, -3.6)
    r, buf = _stage_yard(t, eye, tgt, 42, seed=75)

    _draw_pen_and_wire(r, t, lean_deg=44.0, snapped=True)
    bodi_pos = (4.1, 0.0, -3.6)
    biri_pos = (5.9, 0.0, -4.4)
    b_pose = F.stand_pose(spine=4, rsh_p=36 + 22 * lift, rel=62, head_y=-4)
    joints = _w.actor(r, _BODI, b_pose, bodi_pos, _face(bodi_pos, biri_pos),
                      t, seed=61, amp=0.30, expression="smile")
    _w.actor(r, _BIRI, F.stand_pose(spine=4), biri_pos, _face(biri_pos, bodi_pos),
             t, seed=52, amp=0.20, expression="neutral")

    # Coiled steel repair wire held in Bodi's right hand
    if joints and "rhand" in joints:
        hx, hy, hz = joints["rhand"]
        coil = Mesh()
        for k in range(6):
            ang = k * 60.0
            rad = 0.11
            ox = math.cos(math.radians(ang)) * rad
            oy = math.sin(math.radians(ang)) * rad
            coil.add(box(0.05, 0.03, 0.04, (162, 158, 142),
                         center=(hx + ox * 0.4, hy - 0.08 + oy, hz + ox * 0.8)))
        _w.add(r, coil)

    F.finish(surface, r, buf, 75, "M7", t)


_DISPATCH = {
    "pen": pen,
    "slip": slip,
    "orchard": orchard,
    "potatoes": potatoes,
    "bodi": bodi,
}


def draw_scene(name, surface, t):
    if not m7goat3d_enabled():
        return False
    fn = _DISPATCH.get(name)
    if fn is None:
        return False
    try:
        fn(surface, t)
        return True
    except Exception as e:
        _S["failed"], _S["err"] = True, e
        print(f"m7goat3d: disabled ({name}: {e!r}), using 2D")
        return False
