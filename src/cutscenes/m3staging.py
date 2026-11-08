"""M3 service-exit bridge: one 3D set, four directed camera setups.

The existing scene IDs, dialogue, timing and gameplay hand-off stay owned by
M3/CutscenePlayer. Nothing here reads or mutates mission state. Animation is
seekable: the radio has exactly one owner, and walking stops in double support.
The old m3ops takes remain the fallback when 3D is disabled or unavailable.
"""
import math
import os

import pygame

from core.config import HEIGHT, SCENE_TOP, WIDTH
from cutscenes.cast3d import humanoid3d

SCENES = ("m3_service_door_transition", "m3_volkov_radio_call",
          "m3_radio_recovered", "m3_comms_wing_reveal")
TOP, BOTTOM = SCENE_TOP + 6, HEIGHT - 158
SIZE = (int(WIDTH * 0.64), int((BOTTOM - TOP) * 0.64))
_cache = {"renderer": None, "rigs": {}, "routes": {}, "props": {},
          "failed": False, "err": None}

# Same prisoner wardrobe as missions.m3.draw3d, without importing a mission
# from its take module (meta imports m3ops while the mission is loading).
_PRISONER = dict(jacket=(88, 64, 46), pants=(88, 64, 46), vest=None,
                 pouches=False, accent=None, armband=(88, 64, 46), belt=None,
                 buckle=None, cuff=(56, 42, 32), lapel=None, shirt=None)
_VOLKOV = (-0.72, 0.0, 0.45)
_BIRIBEL = (0.72, 0.0, 0.70)
# A short underarm toss, not a slow levitating prop. The catch has a separate
# absorption beat before the radio is raised in the following insert.
_RELEASE, _CATCH = 620.0, 980.0
_THROW_READY = (-0.65, 1.05, 0.0)
_THROW_START = (-0.35, 1.25, 0.10)
_THROW_REST = (-0.65, 0.95, 0.0)
_CATCH_POINT = (0.27, 1.19, 0.70)
_CATCH_REST = (0.37, 1.10, 0.70)


def _k(t, start, duration):
    p = max(0.0, min(1.0, (t - start) / duration))
    return p * p * (3.0 - 2.0 * p)


def _mix(a, b, p):
    return tuple(x + (y - x) * p for x, y in zip(a, b))


def _rig(who):
    if who not in _cache["rigs"]:
        _cache["rigs"][who] = humanoid3d(
            who, **(_PRISONER if who == "biribel" else {}))
    return _cache["rigs"][who]


def _mesh(r, mesh):
    r.add_dynamic(mesh.verts, [(f[0], f[1], f[2], f[3], None, f[4])
                               for f in mesh.faces])


def _set(r):
    """Cold concrete corridor opening into a practical-lit equipment room."""
    from engine3d import box, quad_xz
    from cutscenes.ps2mat import mesh as textured  # lazy: shared film materials

    def bake(mesh):
        r.bake(textured(mesh))

    bake(quad_xz(-2.8, -4.0, 2.8, 11.0, 0, (64, 70, 69), seg=1.0))
    # Subdivided walls: no camera-straddling, room-sized faces.
    for side in (-1, 1):
        bake(box(0.22, 3.25, 15, (75, 83, 81),
                   center=(side * 2.9, 1.6, 3.5), seg=1.0))
        bake(box(0.08, 0.92, 15, (40, 58, 54),
                   center=(side * 2.77, 0.5, 3.5), seg=1.0))
        for z in (-2.0, 1.5, 5.0, 8.5):
            bake(box(0.12, 0.1, 2.0, (125, 133, 124),
                       center=(side * 2.65, 2.5, z)))
        # Cable tray under the ceiling, metal curb along the floor.
        for y, col in ((2.85, (40, 47, 46)), (0.12, (58, 64, 60))):
            bake(box(0.22, 0.12, 15, col,
                       center=(side * 2.65, y, 3.5), seg=1.0))
    bake(box(5.8, 3.2, 0.22, (56, 66, 63), center=(0, 1.6, 11), seg=1.0))
    for z in range(-3, 11):
        bake(box(5.5, 0.008, 0.016, (37, 46, 44), center=(0, 0.008, z)))
    # The cell-block door stays behind the actors on the same screen axis.
    for x in (-2.05, 2.05):
        bake(box(1.5, 3.2, 0.3, (62, 71, 68), center=(x, 1.6, -2), seg=0.8))
    for x in (-1.27, 1.27):
        bake(box(0.13, 2.65, 0.38, (118, 126, 118), center=(x, 1.32, -2)))
    bake(box(2.66, 0.34, 0.38, (88, 100, 93), center=(0, 2.8, -2)))
    # Relay bay portal: the opening, racks and console are visible in the wide.
    for x in (-2.45, 2.45):
        bake(box(0.7, 3.2, 0.32, (72, 82, 77), center=(x, 1.6, 3.6), seg=0.8))
    bake(box(5.5, 0.26, 0.38, (89, 102, 94), center=(0, 2.95, 3.6)))
    for side in (-1, 1):
        for z in (5.0, 7.0, 9.0):
            x = side * 2.1
            bake(box(0.9, 2.3, 0.9, (32, 43, 44), center=(x, 1.15, z)))
            bake(box(0.78, 2.05, 0.025, (48, 62, 60), center=(x, 1.16, z - 0.465)))
            for y in (0.4, 0.72, 1.04, 1.36, 1.68, 2.0):
                bake(box(0.65, 0.028, 0.035, (104, 119, 110),
                           center=(x, y, z - 0.49)))
                bake(box(0.036, 0.036, 0.04, (105, 184, 134),
                           center=(x + 0.27, y + 0.07, z - 0.49), emissive=True))
    bake(box(2.1, 0.85, 0.9, (47, 64, 60), center=(0, 0.43, 8.5)))
    bake(box(2.2, 0.09, 1.0, (102, 116, 104), center=(0, 0.9, 8.5)))
    bake(box(0.9, 0.7, 0.55, (30, 42, 40), center=(0, 1.3, 8.7)))
    bake(box(0.72, 0.48, 0.025, (45, 112, 86), center=(0, 1.33, 8.41), emissive=True))
    for z in (0.0, 4.0, 8.0):
        bake(box(1.3, 0.1, 0.22, (48, 59, 54), center=(0, 3.0, z)))
        bake(box(1.12, 0.035, 0.16, (192, 218, 192),
                   center=(0, 2.94, z), emissive=True))

    # Architectural scale and wear: a service tunnel, not an empty box set.
    # All detail is baked once and kept out of the actors' walk/catch envelope.
    for side in (-1, 1):
        for z in (-0.8, 2.0, 4.8, 7.6, 10.4):
            bake(box(0.16, 3.0, 0.11, (97, 105, 102),
                     center=(side * 2.72, 1.5, z)))
            bake(box(0.03, 0.3, 0.65, (54, 65, 61),
                     center=(side * 2.635, 0.26, z + 0.5)))
        for y in (2.25, 2.38):
            bake(box(0.08, 0.065, 14.5, (100, 109, 105),
                     center=(side * 2.58, y, 3.5), seg=0.8))
        # Vent grilles with an actual recessed dark cavity and slats.
        for z in (0.9, 6.3):
            bake(box(0.07, 0.65, 1.05, (24, 31, 30),
                     center=(side * 2.69, 1.75, z)))
            for j in range(7):
                bake(box(0.1, 0.035, 0.96, (99, 111, 105),
                         center=(side * 2.63, 1.49 + j * 0.08, z)))
    # Ceiling bands are subdivided like the walls (near-plane safe).
    bake(box(5.6, 0.14, 15, (44, 53, 52), center=(0, 3.24, 3.5), seg=1))
    for z in (-1, 2, 5, 8, 10):
        bake(box(5.5, 0.16, 0.16, (91, 100, 96), center=(0, 3.1, z)))
    # Floor drainage and worn threshold strips, not glowing navigation paint.
    for z in (0.8, 3.4, 6.7):
        bake(box(1.5, 0.018, 0.25, (28, 36, 34), center=(-1.5, 0.018, z)))
        for j in range(12):
            bake(box(0.055, 0.022, 0.24, (91, 100, 91),
                     center=(-2.16 + j * 0.12, 0.023, z)))
    # Rack module faces: recessed slots, handles, meter windows and wiring.
    for side in (-1, 1):
        for z in (5.0, 7.0, 9.0):
            x = side * 2.1
            for y in (0.52, 1.16, 1.8):
                bake(box(0.55, 0.19, 0.035, (19, 29, 28),
                         center=(x - 0.035, y, z - 0.49)))
                bake(box(0.15, 0.075, 0.045, (103, 132, 116),
                         center=(x - 0.15, y + 0.035, z - 0.515)))
                for dx in (-0.27, 0.27):
                    bake(box(0.035, 0.14, 0.07, (147, 155, 137),
                             center=(x + dx, y, z - 0.53)))
            for dx in (-0.18, 0, 0.18):
                bake(box(0.035, 0.035, 0.5, (104, 80, 50),
                         center=(x + dx, 2.4, z - 0.15)))
    # Relay desk: sloped control surface, keys, monitor feet and paper trays.
    for x in (-0.32, 0.32):
        bake(box(0.05, 0.12, 0.28, (108, 120, 106), center=(x, 1.0, 8.6)))
    bake(box(0.8, 0.035, 0.28, (25, 35, 31), center=(-0.32, 0.97, 8.19)))
    for row in range(3):
        for col in range(9):
            bake(box(0.055, 0.018, 0.05, (132, 141, 120),
                     center=(-0.63 + col * 0.075, 0.994, 8.1 + row * 0.075)))
    bake(box(0.32, 0.03, 0.28, (157, 148, 121), center=(0.76, 0.97, 8.26)))
    # Door's warm practical has a physical housing; it supplies the rim light.
    bake(box(0.35, 0.5, 0.18, (51, 58, 52), center=(-1.7, 2.3, -1.75)))
    bake(box(0.22, 0.33, 0.04, (236, 168, 93),
             center=(-1.7, 2.3, -1.64), emissive=True))


def _renderer():
    if _cache["renderer"] is None:
        from engine3d import Light, Renderer
        r = Renderer(*SIZE, fog=(13, 24, 23), fog_start=9, fog_end=25)
        r.light = Light(direction=(-0.4, 0.8, -0.6), ambient=0.30,
                        diffuse=0.55, sky=0.06, tint=(0.94, 0.98, 1.0))
        r.light_albedo = True
        _set(r)
        _cache["renderer"] = (r, pygame.Surface(SIZE))
    return _cache["renderer"]


def _walk(who, points, t, start, duration):
    # lazy: reuse the planted-foot motion kit without importing any mission.
    from cutscenes import m6world3d as motion
    key = tuple(points)
    if key not in _cache["routes"]:
        route = motion.path(points)
        stride = motion.walk_stride(route.length)
        _cache["routes"][key] = (route, stride, motion.walk_span(route.length, stride))
    route, stride, (g0, g1) = _cache["routes"][key]
    g = g0 + (g1 - g0) * motion.travel(t, start, duration)
    return motion.walk(_rig(who), route, g, stride)


def _hold(t, recover=False):
    """Hand targets and radio centre share the exact catch/recovery endpoint."""
    if recover:
        centre = _mix(_CATCH_REST, (0.40, 1.43, 0.74), _k(t, 160, 850))
        return centre, "biribel"
    if t < _RELEASE:
        return _mix(_THROW_READY, _THROW_START, _k(t, 280, _RELEASE - 280)), "volkov"
    if t >= _CATCH:
        return _mix(_CATCH_POINT, _CATCH_REST, _k(t, _CATCH, 220)), "biribel"
    u = (t - _RELEASE) / (_CATCH - _RELEASE)
    centre = _mix(_THROW_START, _CATCH_POINT, u)
    # Ballistic arc: constant horizontal travel and gravity-shaped height.
    centre = (centre[0], centre[1] + 0.16 * 4 * u * (1 - u), centre[2])
    return centre, "flight"


def _handoff_poses(t, recover=False):
    from cutscenes import m6world3d as motion  # lazy: motion/arm IK only
    from engine3d.hold import solve_arm_safe
    radio, owner = _hold(t, recover)
    vp = dict(head_y=-8, rsh_p=15, rel=35)
    bp = _carry(dict(head_y=8, head_p=10), _BIRIBEL, -90)
    # At the release Volkov's palm is at the radio; it retracts only after.
    # His right shoulder is on the camera side (world -z at yaw 90).
    # Keeping the whole path there avoids reaching THROUGH his chest.
    vtarget = (radio if owner == "volkov" else
               _mix(_THROW_START, _THROW_REST,
                    1.0 if recover else _k(t, _RELEASE, 380)))
    vp = solve_arm_safe(_rig("volkov"), vp, _VOLKOV, 90, "r", vtarget, margin=0.04)
    # Start with the receiving hand down; react to the throw instead of holding
    # a rigid catch pose throughout Volkov's whole line.
    btarget = radio if owner == "biribel" else _mix(
        (0.62, 0.97, 0.70), _CATCH_POINT, _k(t, 440, _CATCH - 440))
    bp = motion.reach(_rig("biribel"), bp, "l", btarget, _BIRIBEL, -90)
    return vp, bp, radio, owner


def _carry(pose, pos, yaw):
    """Low, right-side gun; leave the radio arm entirely caller-owned."""
    from engine3d import m_apply, rot_y, v_add
    from engine3d.hold import hold_weapon, solve_arm_safe
    h = _rig("biribel")
    pose = hold_weapon(h, pose, pos, yaw, "os12", "one_hand")
    hand = h.pose_world(pose, pos, yaw, rifle_on=False)[1]["rhand"]
    # Extra room for the radio and its antenna as it rises past the stock.
    target = v_add(hand, m_apply(rot_y(yaw), (0.10, -0.08, 0.0)))
    return solve_arm_safe(h, pose, pos, yaw, "r", target, margin=0.04)


def _volkov_exit(t):
    from engine3d import m_apply, rot_y, v_add
    from engine3d.hold import solve_arm_safe
    from cutscenes import m6world3d as motion  # lazy: walk/turn helpers
    pose, pos, yaw = _walk("volkov", ((-0.72, 0.45), (-1.65, 1.7)), t, 180, 1350)
    yaw = motion.yaw_mix(90, yaw, _k(t, 180, 450))
    # Match the previous shot's held follow-through before turning away.
    local = _mix((0.45, 0.95, 0.07), (0.34, 0.95, 0.08), _k(t, 180, 700))
    target = v_add(pos, m_apply(rot_y(yaw), local))
    pose = solve_arm_safe(_rig("volkov"), pose, pos, yaw, "r", target, margin=0.04)
    return pose, pos, yaw


def _actor(r, who, pose, pos, yaw, t, talk=False):
    from engine3d import mouth_flap, os12_mesh, m_apply, m_mul, rot_x, rot_y, v_add
    h = _rig(who)
    h.set_expression("stern" if who == "volkov" else "neutral",
                     mouth_flap(int(t), 3) if talk else 0)
    joints = r.add_humanoid(h, pose, pos, yaw, rifle_on=False)
    if who == "biribel":
        # The armory pickup precedes this bridge. Keep the K-9 in his right
        # hand at low ready while the free left hand receives the radio.
        if "k9" not in _cache["props"]:
            _cache["props"]["k9"] = os12_mesh()
        gun = _cache["props"]["k9"]
        rotation = m_mul(rot_y(yaw + pose.get("rifle_y", 0)),
                         rot_x(pose.get("rifle_p", 40)))
        verts = [v_add(m_apply(rotation, v), joints["rhand"])
                 for v in gun.verts]
        r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in gun.faces])
    return joints


def _radio(r, centre, t, boot=False):
    from engine3d import box
    x, y, z = centre
    # Broad face points south, toward all three handoff/insert lenses.
    _mesh(r, box(0.15, 0.23, 0.07, (26, 39, 35), center=centre))
    _mesh(r, box(0.10, 0.065, 0.008, (87, 178, 125) if boot else (23, 47, 38),
                 center=(x, y + 0.025, z - 0.041), emissive=boot))
    _mesh(r, box(0.015, 0.19, 0.015, (73, 85, 75),
                 center=(x - 0.052, y + 0.2, z)))
    # Rubber corner guards and controls give the insert a real manufactured
    # silhouette without enlarging the prop or breaking the hand contact.
    for dx in (-0.067, 0.067):
        for dy in (-0.098, 0.098):
            _mesh(r, box(0.022, 0.04, 0.085, (12, 20, 18),
                         center=(x + dx, y + dy, z)))
    for dx in (-0.025, 0.025):
        _mesh(r, box(0.022, 0.018, 0.012, (131, 143, 120),
                     center=(x + dx, y - 0.018, z - 0.044)))
    _mesh(r, box(0.025, 0.025, 0.025, (112, 121, 100),
                 center=(x + 0.043, y + 0.126, z)))
    for dy in (-0.05, -0.07, -0.09):
        _mesh(r, box(0.09, 0.008, 0.008, (8, 17, 14), center=(x, y + dy, z - 0.041)))


def _draw(scene, surface, t):
    from engine3d import box
    from cutscenes import m6fx3d as fx  # lazy: presentation/camera kit

    r, buf = _renderer()
    r.set_lights([
        {"pos": (0, 2.75, 0), "color": (192, 217, 207), "intensity": 1.15, "range": 4.5},
        {"pos": (0, 2.75, 5), "color": (139, 189, 185), "intensity": 0.85, "range": 5},
        {"pos": (-1.7, 2.3, -1.5), "color": (236, 168, 93), "intensity": 1.0, "range": 4},
        {"pos": (0.7, 1.7, -0.7), "color": (155, 187, 205), "intensity": 0.45, "range": 2.8},
    ])
    if scene == SCENES[0]:
        p = _k(t, 0, 1500)
        eye, target, fov = _mix((2.3, 1.8, 2.9), (2.1, 1.7, 2.6), p), (0, 1.2, -0.4), 57
    elif scene == SCENES[1]:
        # A locked waist-up two-shot keeps both hands readable. Do not dolly
        # during the toss: the prop's motion should come from the throw alone.
        # Stay INSIDE the sealed door at z=-2, not behind its steel leaves.
        eye, target, fov = (0.02, 1.52, -1.80), (0, 1.20, 0.45), 62
    elif scene == SCENES[2]:
        eye, target, fov = (0.02, 1.65, -0.22), (0.40, 1.39, 0.72), 43
    else:
        p = _k(t, 0, 2200)
        eye, target, fov = _mix((0.8, 1.8, -0.8), (1.2, 2.05, 2.3), p), (0, 1.3, 7.7), 63
    fx.set_cam(r, t, eye, target, fov, hh=0.0)
    buf.fill((13, 24, 23))
    r.begin()
    r.add_static()
    # Sliding steel leaves close AFTER the prisoner has cleared the threshold.
    shut = _k(t, 820, 600) if scene == SCENES[0] else 1.0
    for side in (-1, 1):
        _mesh(r, box(1.18, 2.6, 0.12, (57, 72, 65),
                     center=(side * (1.8 - 1.2 * shut), 1.3, -2), seg=0.6))
    if scene == SCENES[0]:
        pose, pos, yaw = _walk("biribel", ((0.72, -1.6), (0.72, 0.70)), t, 0, 1450)
        yaw -= 90 * _k(t, 1100, 350)
        pose = _carry(pose, pos, yaw)
        _actor(r, "biribel", pose, pos, yaw, t)
        vp, _, radio, _ = _handoff_poses(0)
        _actor(r, "volkov", vp, _VOLKOV, 90, t)
        _radio(r, radio, t)
    elif scene in SCENES[1:3]:
        recover = scene == SCENES[2]
        vp, bp, radio, owner = _handoff_poses(t, recover)
        if recover:
            vp, vpos, vyaw = _volkov_exit(t)
        else:
            vpos, vyaw = _VOLKOV, 90
        _actor(r, "volkov", vp, vpos, vyaw, t, talk=not recover)
        _actor(r, "biribel", bp, _BIRIBEL, -90, t)
        _radio(r, radio, t, boot=recover and t >= 450)
    else:
        pose, pos, yaw = _walk("biribel", ((0.72, 0.70), (0.72, 4.9)), t, 0, 3000)
        yaw -= 90 * (1.0 - _k(t, 0, 450))
        pose = _carry(pose, pos, yaw)
        pose.update(lsh_p=40, lsh_r=60, lel=150)
        joints = _actor(r, "biribel", pose, pos, yaw, t)
        _radio(r, joints["lhand"], t, boot=True)
    # Small source-anchored practical halos, depth masked by the shared film
    # compositor. No frame-wide haze to wash the character silhouettes out.
    for z in (0, 4, 8):
        r.add_sprite((0, 2.91, z), fx.glow(
            (174, 208, 190), 0.28, t=t, intensity=0.35, max_px=12), layer=6)
    r.add_sprite((-1.7, 2.3, -1.61), fx.glow(
        (236, 168, 93), 0.22, t=t, intensity=0.45, max_px=14), layer=6)
    r.flush(buf)
    surface.fill((5, 9, 9))
    fx.grade_cine(buf)
    fx.present_crisp(buf, surface.subsurface((0, TOP, WIDTH, BOTTOM - TOP)))


def draw(scene, surface, t):
    """Return False to let the existing take paint its complete 2D fallback."""
    if scene not in SCENES or os.environ.get("ACARISTAN_CUTSCENE3D", "1").strip() == "0":
        return False
    if _cache["failed"]:
        return False
    try:
        _draw(scene, surface, max(0.0, float(t)))
        return True
    except Exception as exc:
        _cache["failed"], _cache["err"] = True, exc
        return False
