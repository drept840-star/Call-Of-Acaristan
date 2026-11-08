"""Kill Order intro: directed 3D breach, stairs, cover and empty-dock preview.

No mission state or clocks: all action is seekable from the shot-local t.
The original illustrated takes remain in m3ko as disabled/error fallbacks.
"""
import math
import os

import pygame

from core.config import HEIGHT, SCENE_TOP, WIDTH
from cutscenes.cast3d import humanoid3d

SCENES = ("m3_ko_charge", "m3_ko_stairwell", "m3_ko_aperture", "m3_ko_van")
TOP, BOTTOM = SCENE_TOP + 6, HEIGHT - 158
SIZE = (int(WIDTH * 0.64), int((BOTTOM - TOP) * 0.64))
BOOM = 1150.0
ACQUIRE = 1950.0
TREAD, RISE, STEPS = 0.48, 0.18, 8
STAIR_END = TREAD * STEPS
PILLAR = (0.5, 1.8, 3.5)
PILLAR_HALF = (0.7, 1.8, 0.7)
# Keep the rifleman at the near edge of a clear mezzanine firing bay, to the
# right of the cover pillar in the PA lens. His silhouette identifies the threat;
# no beam or tracer is needed to point him out.
MARKSMAN = (6.8, 2.6, 8.5)
_cache = {"sets": {}, "rigs": {}, "routes": {}, "van": None,
          "failed": False, "err": None}
_PRISONER = dict(jacket=(88, 64, 46), pants=(88, 64, 46), vest=None,
                 pouches=False, accent=None, armband=(88, 64, 46), belt=None,
                 buckle=None, cuff=(56, 42, 32), lapel=None, shirt=None)


def smooth(t, start, duration):
    u = max(0.0, min(1.0, (t - start) / duration))
    return u * u * (3 - 2 * u)


def mix(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def rig(who):
    if who not in _cache["rigs"]:
        overrides = _PRISONER if who == "biribel" else {"rifle": "rifle"} if who == "ipa" else {}
        _cache["rigs"][who] = humanoid3d(who, **overrides)
    return _cache["rigs"][who]


def stair_height(x, z):
    """True tread support, descending along +z; bottom landing is y=0."""
    step = max(0, min(STEPS, int(math.floor((z + 1e-7) / TREAD))))
    return (STEPS - step) * RISE


def stair_actor(who, t):
    from cutscenes import m6world3d as motion  # lazy: planted feet + terrain IK
    # Each lane has its own route; Biribel follows 500 ms later and never
    # passes through Volkov even when the leader stops on the landing.
    x, start, end = (-0.48, 0, 8.1) if who == "volkov" else (0.48, 500, 7.3)
    if who not in _cache["routes"]:
        route = motion.path(((x, 0), (x, end)))
        # One tread per half-cycle keeps every planted sole on a real tread.
        _cache["routes"][who] = route
    route = _cache["routes"][who]
    stride = 2 * TREAD
    g0, g1 = motion.walk_span(route.length, stride)
    g = g0 + (g1 - g0) * motion.travel(t, start, 4800)
    h = rig(who)
    pose, pos, yaw = motion.walk(h, route, g, stride, speed=1.0, ground=stair_height)
    # Terrain IK plants ankle centres; a box-shaped toe can still intersect
    # the next riser. Lift by actual sole geometry, not a guessed ankle offset.
    from engine3d import m_apply, v_add
    places, _joints, root = h.pose_world(pose, pos, yaw, rifle_on=False)
    clearance = []
    for _slot, key, matrix, org, _ground, _bias in places:
        if key == "foot":
            for vertex in h._unique_verts()[key]:
                x, y, z = v_add(root, v_add(org, m_apply(matrix, vertex)))
                clearance.append(y - stair_height(x, z))
    pose["lift"] += -min(clearance)
    # Once through the portal they check opposite flanks of the corridor;
    # nobody stands stock-still staring back at the blown door on a hold.
    scan = smooth(t, start + 4800, 450)
    pose["head_y"] = (32 if who == "volkov" else -35) * scan
    return pose, pos, yaw + (18 if who == "volkov" else -20) * scan


def cover_actor(who, t):
    from engine3d import POSES, blend
    from cutscenes import m6world3d as motion  # lazy: approach / reaction
    # Match the preceding exit: both emerge from the visible stair door,
    # then cut LEFT around the pillar when the PA orders free fire. Volkov
    # scouts first; Biribel trails him instead of spawning beside the cover.
    if who == "volkov":
        points, start, duration = ((-0.48, -2.8), (-0.48, -1.0),
                                   (-1.65, 1.0), (-1.55, 2.15)), 0, 1550
    else:
        points, start, duration = ((0.48, -2.8), (0.48, -1.0),
                                   (-1.15, 0.25), (-1.3, 1.0)), 250, 1750
    key = ("cover", who)
    if key not in _cache["routes"]:
        route = motion.path(points)
        _cache["routes"][key] = (route, motion.walk_stride(route.length))
    route, stride = _cache["routes"][key]
    g0, g1 = motion.walk_span(route.length, stride)
    pose, pos, yaw = motion.walk(rig(who), route,
        g0 + (g1 - g0) * motion.travel(t, start, duration), stride)
    duck = smooth(t, start + duration - 200, 400)
    p = blend(pose, dict(POSES["kneel"]), duck)
    p["head_y"] = 12
    p["head_p"] = 4
    return p, pos, motion.yaw_mix(yaw, 35, duck)


def shot_age(t):
    """First shot at acquisition, then spaced shots while the dialogue holds."""
    return None if t < ACQUIRE else (t - ACQUIRE) % 1700


def cover_hit(origin):
    """First slab hit on the pillar from the actual muzzle, never past cover."""
    aim = (-0.5, 1.0, 2.1)
    direction = tuple(aim[i] - origin[i] for i in range(3))
    lo, hi = 0.0, 1.0
    for i in range(3):
        a, b = PILLAR[i] - PILLAR_HALF[i], PILLAR[i] + PILLAR_HALF[i]
        if abs(direction[i]) < 1e-9:
            if not a <= origin[i] <= b:
                raise ValueError("marksman ray misses cover")
        else:
            u, v = (a - origin[i]) / direction[i], (b - origin[i]) / direction[i]
            lo, hi = max(lo, min(u, v)), min(hi, max(u, v))
    if lo > hi:
        raise ValueError("marksman ray misses cover")
    return mix(origin, aim, lo)


def _dynamic(r, mesh):
    r.add_dynamic(mesh.verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces])


def _van_mesh():
    if _cache["van"] is None:
        from engine3d import Mesh, box
        from game.render3d_bridge import load_mesh_asset
        try:
            verts, faces = load_mesh_asset("m3_van")
            m = Mesh()
            m.verts = list(verts)
            m.faces = [(tuple(idx), tuple(col), 2, False, False) for idx, col, _grp in faces]
        except (OSError, ValueError, KeyError):
            # Explicit procedural fallback, not a missing whole cinematic.
            m = box(4.6, 2.0, 2.0, (62, 68, 76), center=(0, 1.25, 0))
            m.add(box(1.0, 1.4, 1.9, (71, 80, 87), center=(2.5, 0.95, 0)))
            for x in (-1.8, 2.0):
                for z in (-1.02, 1.02):
                    m.add(box(0.65, 0.65, 0.18, (19, 22, 25), center=(x, 0.33, z)))
        _cache["van"] = m
    return _cache["van"]


def _set(r, key):
    from engine3d import box, quad_xz
    from cutscenes.ps2mat import mesh as textured

    def bake(m):
        r.bake(textured(m))

    if key == "charge":
        for x in (-2.0, 2.0):
            bake(box(2.1, 4, 0.25, (66, 69, 68), center=(x, 1.8, 0.3), seg=0.6))
        bake(box(2.0, 0.8, 0.25, (66, 69, 68), center=(0, 3.5, 0.3), seg=0.5))
        for x in (-0.95, 0.95):
            bake(box(0.14, 3, 0.4, (115, 120, 109), center=(x, 1.5, 0)))
        bake(box(2.05, 0.16, 0.4, (115, 120, 109), center=(0, 3, 0)))
        return
    if key == "stairs":
        bake(quad_xz(-2.4, -2, 2.4, 10, 0, (58, 60, 59), seg=0.8))
        for i in range(STEPS):
            z, h = (i + 0.5) * TREAD, (STEPS - i) * RISE
            bake(box(2.7, h, TREAD, (92, 92, 83), center=(0, h / 2, z)))
            bake(box(2.7, 0.025, 0.045, (148, 140, 108), center=(0, h + 0.014, z - TREAD / 2 + 0.04)))
        bake(box(2.7, 0.18, 1.6, (87, 89, 82), center=(0, STEPS * RISE - 0.09, -0.8)))
        for x in (-2.1, 2.1):
            bake(box(0.2, 5.4, 9, (72, 77, 74), center=(x, 2.7, 2.3), seg=0.8))
            for z in (0, 1, 2, 3, 4, 5.5):
                y = stair_height(x, z)
                bake(box(0.055, 1.0, 0.055, (129, 133, 115), center=(x * 0.69, y + 0.5, z)))
            for i in range(STEPS):
                bake(box(0.07, 0.08, TREAD + 0.08, (121, 128, 113),
                         center=(x * 0.69, (STEPS - i) * RISE + 1, (i + 0.5) * TREAD)))
        # Actual open aperture, not jambs placed in front of a solid back wall.
        for x in (-1.8, 1.8):
            bake(box(0.6, 4.8, 0.25, (66, 72, 71), center=(x, 2.4, 5.9), seg=0.6))
            bake(box(0.13, 2.8, 0.4, (112, 116, 104), center=(x * 0.78, 1.4, 5.9)))
        bake(box(3.0, 0.25, 0.4, (112, 116, 104), center=(0, 2.92, 5.9)))
        bake(box(4.2, 1.6, 0.25, (66, 72, 71), center=(0, 4.0, 5.9), seg=0.6))
        # Door is visibly blown against the wall, leaving the centre clear.
        bake(box(0.12, 2.65, 1.55, (55, 66, 62), center=(-1.65, 1.33, 6.65)))
        bake(box(4.2, 4.8, 0.2, (49, 63, 66), center=(0, 2.4, 10), seg=0.8))
        return
    bake(quad_xz(-8, -4, 8, 15, 0, (61, 64, 63), seg=1))
    for x in (-8, 8):
        bake(box(0.25, 6, 19, (80, 85, 83), center=(x, 3, 5.5), seg=1))
    bake(box(16, 6, 0.25, (61, 70, 72), center=(0, 3, 15), seg=1))
    for z in (-1, 4, 9, 14):
        bake(box(16, 0.24, 0.25, (70, 79, 76), center=(0, 5.6, z), seg=1))
    if key == "lobby":
        # Same painter layer as actors: this pillar must physically occlude.
        bake(box(*(2 * a for a in PILLAR_HALF), (109, 111, 103), center=PILLAR, layer=2, seg=0.6))
        bake(box(6.2, 0.3, 3.0, (78, 85, 83), center=(4.4, 2.45, 9.5), layer=2, seg=0.7))
        # Leave a genuine shooting bay at x=5.4..7.4. The old continuous
        # railing/post cut across the rifleman and hid his weapon.
        for x in (1.4, 2.4, 3.4, 4.4, 5.4, 7.4):
            bake(box(0.06, 0.95, 0.06, (130, 137, 123), center=(x, 3.08, 8.1)))
        bake(box(4.0, 0.07, 0.08, (143, 147, 132), center=(3.4, 3.56, 8.1)))
        # A practical over the firing bay lifts his silhouette off the dark
        # wall; its light is real geometry, not a laser over foreground cover.
        bake(box(1.0, 0.1, 0.16, (203, 211, 184), center=(6.8, 5.0, 8.8), emissive=True))
        bake(box(1.4, 2.6, 0.08, (153, 116, 73), center=(4, 3.9, 14.8), emissive=True))
        # The stair exit is IN this room: a threshold and open portal behind
        # the pair, not an unexplained jump to an unrelated blank lobby.
        # A short, cutaway stair throat joins the threshold to the lobby.
        # The camera-side parapet stays low so the entering cast is legible.
        bake(box(0.22, 3.1, 2.8, (69, 78, 76), center=(1.53, 1.55, -2.75), seg=0.7))
        bake(box(0.22, 0.95, 2.8, (69, 78, 76), center=(-1.53, 0.475, -2.75), seg=0.7))
        bake(box(0.09, 0.1, 2.8, (138, 144, 125), center=(-1.53, 0.99, -2.75)))
        for x in (-1.4, 1.4):
            bake(box(0.22, 3.15, 0.32, (130, 139, 125), center=(x, 1.575, -1.35)))
        bake(box(3.04, 0.26, 0.34, (130, 139, 125), center=(0, 3.06, -1.35)))
        bake(box(2.95, 0.08, 0.48, (156, 140, 92), center=(0, 0.04, -1.35)))
        # Heavy, side-lit security bay with actual depth; a red alarm strip
        # and PA grille tell the story of Balaceanu's voice over this space.
        for z in (1.1, 4.6, 8.1, 11.6):
            bake(box(0.09, 4.8, 0.12, (121, 129, 115), center=(7.78, 2.4, z)))
        for y in (0.55, 1.75, 3.1):
            bake(box(0.13, 0.12, 13.5, (96, 105, 98), center=(7.76, y, 5.2), seg=0.85))
        bake(box(0.12, 1.7, 3.1, (38, 57, 59), center=(7.58, 2.1, 5.8)))
        for z in (4.7, 5.45, 6.2, 6.95):
            bake(box(0.15, 0.07, 0.54, (146, 158, 146), center=(7.47, 2.1, z)))
        bake(box(0.15, 0.12, 3.2, (178, 53, 36), center=(7.45, 3.15, 5.8), emissive=True))
        # PA source and institutional scale: visible speaker on the pillar,
        # clerk counters and wall bays, not two kneeling figures in a void.
        bake(box(0.52, 0.68, 0.16, (29, 39, 39), center=(0.5, 3.15, 2.72)))
        bake(box(0.62, 0.12, 0.2, (178, 53, 36), center=(0.5, 3.57, 2.70), emissive=True))
        for y in (2.94, 3.03, 3.12, 3.21, 3.30, 3.39):
            bake(box(0.43, 0.025, 0.04, (133, 141, 123), center=(0.5, y, 2.62)))
        for x in (-5.5, -2.8):
            bake(box(1.9, 1.0, 1.1, (77, 82, 73), center=(x, 0.5, 7.2)))
            bake(box(2.0, 0.09, 1.2, (142, 132, 106), center=(x, 1.04, 7.2)))
        for z in (3.5, 8.5, 13.5):
            for x in (-7.7, 7.7):
                bake(box(0.3, 5.3, 0.35, (105, 112, 102), center=(x, 2.65, z)))
        # Rear escape corridor is lit differently from the sniper doorway.
        bake(box(1.4, 2.6, 0.1, (54, 95, 102), center=(-3.7, 1.3, 14.8), emissive=True))
    else:
        # Staged asset at its authored metre scale, nose +x. No cast at dock.
        from engine3d import Mesh
        van = Mesh()
        van.add(_van_mesh(), t=(0.7, 0, 6.5))
        r.bake(van)
        for x, z, h in ((-4.5, 7, 1), (-4.5, 8.2, 2), (4.8, 10, 1), (5.9, 10, 1)):
            bake(box(1.0, h, 1, (113, 96, 66), center=(x, h / 2, z)))
        bake(box(6.5, 1.6, 0.15, (99, 113, 119), center=(0, 5.1, 14.6)))
        for y in (4.5, 4.8, 5.1, 5.4, 5.7):
            bake(box(6.5, 0.035, 0.19, (142, 150, 143), center=(0, y, 14.5)))
        for z in (3.5, 11.5):
            for x in (-3.6, 3.6):
                bake(box(0.15, 0.75, 0.15, (176, 143, 64), center=(x, 0.375, z)))
    for z in (1, 7, 12):
        bake(box(1.6, 0.12, 0.3, (34, 44, 43), center=(0, 5.35, z)))
        bake(box(1.4, 0.04, 0.2, (198, 217, 201), center=(0, 5.27, z), emissive=True))


def renderer(key):
    if key not in _cache["sets"]:
        from engine3d import Light, Renderer
        r = Renderer(*SIZE, fog=(14, 21, 26), fog_start=13, fog_end=34)
        r.light = Light(direction=(-0.5, 0.8, -0.5), ambient=0.32, diffuse=0.55,
                        sky=0.06, tint=(0.94, 0.98, 1.0))
        r.light_albedo = True
        _set(r, key)
        _cache["sets"][key] = (r, pygame.Surface(SIZE))
    return _cache["sets"][key]


def _actor(r, who, state, t, talk=False):
    from engine3d import mouth_flap, os12_mesh, m_apply, m_mul, rot_x, rot_y, v_add
    from engine3d.hold import hold_weapon
    p, pos, yaw = state
    h = rig(who)
    if who == "biribel":
        p = hold_weapon(h, p, pos, yaw, "os12", "carry")
    h.set_expression("stern", mouth_flap(int(t), 3) if talk else 0)
    j = r.add_humanoid(h, p, pos, yaw, rifle_on=False)
    if who == "biribel":
        if "gun" not in _cache:
            _cache["gun"] = os12_mesh()
        gun = _cache["gun"]
        rotation = m_mul(rot_y(yaw + p.get("rifle_y", 0)), rot_x(p.get("rifle_p", 40)))
        verts = [v_add(j["rhand"], m_apply(rotation, v)) for v in gun.verts]
        r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in gun.faces])
    return j


def _charge(r, t):
    from engine3d import box
    from cutscenes import m6fx3d as fx
    # One-way door displacement: holding or seeking never re-arms the pack.
    gone = smooth(t, BOOM, 300)
    _dynamic(r, box(1.75, 2.85, 0.12, (65, 73, 68),
                    center=(gone * 2.8, 1.43 - gone * 0.6, 0.06 + gone * 1.3), seg=0.4))
    if t < BOOM:
        _dynamic(r, box(0.38, 0.46, 0.12, (35, 42, 35), center=(0, 1.5, -0.08)))
        for y in (1.36, 1.65):
            _dynamic(r, box(0.43, 0.04, 0.14, (123, 117, 91), center=(0, y, -0.10)))
        r.add_line3d((0.05, 1.75, -0.15), (0.12, 2.7, -0.13), (23, 29, 24), 2, layer=3)
        period = 620 - 480 * min(1, t / BOOM)
        on = t % period < period * 0.4
        _dynamic(r, box(0.04, 0.04, 0.025, (235, 65, 36) if on else (57, 28, 21),
                        center=(0.08, 1.62, -0.158), emissive=on))
    elif t < BOOM + 420:
        r.add_sprite((0, 1.5, -0.2), fx.flash(t - BOOM, radius_m=1.4, dur_ms=420), layer=6)
    if BOOM <= t < BOOM + 350:
        age = (t - BOOM) / 350
        for i in range(10):
            a = i * math.tau / 10
            start = (math.cos(a) * age * 0.65, 1.5 + math.sin(a) * age * 0.65, -0.18)
            end = (start[0] + math.cos(a) * 0.10, start[1] + math.sin(a) * 0.10, -0.18)
            r.add_line3d(start, end, (237, 191, 102), 1, layer=3)
    if t >= BOOM:
        for i in range(4):
            r.add_sprite((math.sin(i * 2) * 0.35, 1.3 + i * 0.28, -0.15),
                         fx.haze((105, 107, 100), 0.55, t=t - BOOM, seed=i, intensity=0.12), layer=2)


def _marksman(r, t):
    from engine3d import POSES
    from engine3d.hold import hold_weapon
    h = rig("ipa")
    aim = tuple((-0.5, 1.0, 2.1)[i] - (MARKSMAN[i] + (1.4 if i == 1 else 0)) for i in range(3))
    pose = hold_weapon(h, POSES["aim"], MARKSMAN, 210, "akrifle", "aim", aim=aim)
    joints = r.add_humanoid(h, pose, MARKSMAN, 210, rifle_on=True)
    origin = joints["muzzle"]
    hit = cover_hit(origin)
    # A 3D line is not depth-masked reliably against the pillar in both
    # renderers: it appears THROUGH the cover even if the ray ends on it.
    # Let the visible guard and a brief muzzle/stone hit sell each shot.
    age = shot_age(t)
    if age is not None and age < 120:
        from cutscenes import m6fx3d as fx
        r.add_sprite(origin, fx.flash(age, radius_m=0.3, dur_ms=120), layer=2)
        r.add_sprite(hit, fx.flash(age, radius_m=0.17, dur_ms=120), layer=2)
    return origin, hit


def _draw(scene, surface, t):
    from cutscenes import m6fx3d as fx
    key = ("charge", "stairs", "lobby", "dock")[SCENES.index(scene)]
    r, buf = renderer(key)
    if key == "charge":
        eye, target, fov = (0.95, 1.8, -1.65), (0, 1.55, 0), 43
    elif key == "stairs":
        # Travel WITH them: the open exit passes through frame, rather than
        # freezing on the door while the line continues over an empty tableau.
        follow = smooth(t, 400, 4400)
        eye = mix((1.0, 3.4, -1.6), (0.8, 2.0, 4.55), follow)
        target = mix((-0.1, 1.4, 2.4), (-0.1, 1.3, 8.0), follow)
        fov = 66
    elif key == "lobby":
        # Enter from the stair portal with the actors, then reveal the PA
        # speaker and armed mezzanine in the SAME connected space.
        follow = smooth(t, 0, 1450)
        eye = mix((-2.8, 2.0, -4.4), (-3.2, 1.95, -2.6), follow)
        target = mix((1.1, 2.1, -0.5), (0.9, 2.2, 4.0), follow)
        fov = 60
    else:
        eye = mix((-5.6, 2.4, -1.3), (-4.3, 2.15, 0.5), smooth(t, 0, 2600))
        target, fov = (0.6, 1.2, 6.5), 56
    fx.set_cam(r, t, eye, target, fov, hh=0)
    lights = [
        {"pos": (-1.4, 3.2, 0), "color": (219, 153, 90), "intensity": 1.2, "range": 6},
        {"pos": (1.4, 3.5, 4.5), "color": (147, 190, 210), "intensity": 1.0, "range": 7},
        {"pos": (0, 4.4, 9), "color": (211, 174, 109), "intensity": 1.0, "range": 8},
    ]
    if key == "lobby":
        lights.append({"pos": (6.8, 4.7, 7.9), "color": (194, 212, 212),
                       "intensity": 1.6, "range": 5})
    r.set_lights(lights)
    buf.fill((14, 21, 26))
    r.begin()
    r.add_static()
    if key == "charge":
        _charge(r, t)
    elif key == "stairs":
        for who in ("volkov", "biribel"):
            _actor(r, who, stair_actor(who, t), t, talk=who == "volkov")
        r.add_sprite((0, 2, 5.7), fx.haze((115, 110, 99), 0.8, t=t, seed=2, intensity=0.12), layer=2)
    elif key == "lobby":
        for who in ("volkov", "biribel"):
            _actor(r, who, cover_actor(who, t), t)
        _marksman(r, t)
        # The voice is ON THE PA, not a phantom third person in the lobby.
        r.add_sprite((0.5, 3.57, 2.58),
                     fx.glow((219, 57, 38), 0.28, t=t, pulse=0.22, intensity=0.5), layer=2)
    else:
        r.add_sprite((-1.8, 1.7, 6.5), fx.glow((238, 177, 95), 0.32, t=t, intensity=0.6), layer=2)
    r.flush(buf)
    surface.fill((5, 8, 11))
    fx.grade_cine(buf)
    fx.present_crisp(buf, surface.subsurface((0, TOP, WIDTH, BOTTOM - TOP)))


def draw(scene, surface, t):
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
