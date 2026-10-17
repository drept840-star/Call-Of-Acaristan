"""True 3D oil-rig strike cinematic, rendered by the game's engine3d."""
import math
import random

import pygame

from engine3d import (Mesh, Renderer, box, disc_xz, clamp, lerp, mix_col,
                      m_apply, m_mul, rot_x, rot_y, rot_z, smooth)

RIGS = ((-20.0, 52.0), (0.0, 37.0), (19.0, 46.0))  # LEFT far, CENTER near, RIGHT mid
DECK_Y = 6.4
# Height the deck/derrick hinge settles to once collapsed: topside slab floats
# at the waterline with the tower lying out across the sea.
WRECK_DECK_Y = 0.6
# Frames for the fold-down collapse once a rig is struck (~1.5s at 60fps), timed
# so the mass meets the water near the rig_water_splash cue (impact + ~68f).
COLLAPSE_FRAMES = 90
WATER_CONTACT_FRAME = 68  # existing walking_sim rig_water_splash cue
FOG_COL = (44, 56, 72)
SEA_COL = (40, 66, 90)
_SCENE = None


def _hinge_part(mesh, pivot, rz, rx, drop, sink):
    """Rotate a local rig part about its own hinge, then sink the result.

    Each part collapses on a pivot that matches its real joint (jacket foot,
    deck center, derrick base) instead of swinging about the rig base origin,
    so the rig folds down *in place* instead of flinging its topside outward.
    """
    rot = m_mul(rot_z(rz), rot_x(rx))
    out = []
    for v in mesh.verts:
        q = m_apply(rot, (v[0] - pivot[0], v[1] - pivot[1], v[2] - pivot[2]))
        out.append((q[0] + pivot[0],
                    q[1] + pivot[1] - drop - sink,
                    q[2] + pivot[2]))
    return out



def _collapse_motion(since, index, reduced=False):
    """Support gives way, mass accelerates into water, then the wreck settles."""
    age = 600.0 if reduced else max(0.0, since)
    p = clamp(age / COLLAPSE_FRAMES)
    # Brief structural resistance, accelerating descent to the splash cue.
    fall = (.72 * clamp((age - 12) / (WATER_CONTACT_FRAME - 12)) ** 2
            + .28 * smooth((age - WATER_CONTACT_FRAME)
                           / (COLLAPSE_FRAMES - WATER_CONTACT_FRAME)))
    sink = min(.9, max(0.0, age - COLLAPSE_FRAMES) * .003)
    flip = -1 if index == 2 else 1
    roll = 24 * flip * smooth(p)
    pitch = 4 * flip * smooth(p)
    drop = (DECK_Y + .5 - WRECK_DECK_Y) * fall
    return age, roll, pitch, drop, sink


def _deck_pose(vertices, since, index, reduced=False):
    _, roll, pitch, drop, sink = _collapse_motion(since, index, reduced)
    return _hinge_part(Mesh(verts=vertices), (0, DECK_Y + .5, 0),
                       roll, pitch, drop, sink)


def _collapse_parts(parts, since, index, reduced=False):
    """LOCAL geometry: pinned feet, bowed supports, attached deck and tower.

    This is an authored deterministic deformation, not a physics simulation.
    Each support's top follows the slab while its footing stays pinned; the
    middle bows outward as the upper jacket folds. The tower inherits the
    moving deck transform after folding at its own base joint.
    """
    age, roll, pitch, drop, sink = _collapse_motion(since, index, reduced)
    legs, deck, derrick = parts
    buckle = smooth((age - 8) / 60)
    leg_verts = []
    tops = _deck_pose([(vx, DECK_Y, vz) for vx, _, vz in legs.verts],
                      since, index, reduced)
    for (vx, vy, vz), top in zip(legs.verts, tops):
        f = clamp(vy / DECK_Y)
        # A nonlinear height field, with staggered side failure, preserves the
        # footing and top attachment exactly and bends the subdivided beams.
        bow = (1 - abs(2 * f - 1)) * buckle
        side = -1 if vx < 0 else 1
        stagger = .85 if side == (-1 if index == 2 else 1) else 1.0
        leg_verts.append((lerp(vx, top[0], f) + side * 1.5 * bow * stagger,
                          lerp(0.0, top[1], f),
                          lerp(vz, top[2], f) + (1 if vz >= 0 else -1) * .5 * bow))
    deck_verts = _deck_pose(deck.verts, since, index, reduced)
    flip = -1 if index == 2 else 1
    tower_roll = 88 * flip * smooth((age - 18) / 72)
    relative = _hinge_part(derrick, (0, DECK_Y + .5, .4),
                           tower_roll - roll, 0, 0, 0)
    der_verts = _deck_pose(relative, since, index, reduced)
    return (leg_verts, deck_verts, der_verts), sink


def _rig_fire_anchors(since, index, reduced=False):
    """Deck sockets transformed identically to the geometry, in WORLD space."""
    local = [(0, DECK_Y + .7, -.5), (-2.3, DECK_Y + .9, .8),
             (2.2, DECK_Y + .65, -1.5)]
    return _rig_world_vertices(_deck_pose(local, since, index, reduced), index)


def _water_contact(index):
    flip = -1 if index == 2 else 1
    edge = [(-flip * 4.2, DECK_Y, 0)]
    p = _rig_world_vertices(_deck_pose(edge, WATER_CONTACT_FRAME, index), index)[0]
    return (p[0], .28, p[2])


def _rig_world_vertices(vertices, index):
    """Use the same world origin as the baked standing rig and its effects."""
    x, z = RIGS[index]
    return [(vx + x, vy, vz + z) for vx, vy, vz in vertices]



def _visible_wreck(mesh, vertices, water_y=.12):
    """Clip submerged polygons for both backends (software layers lack depth).

    The mean waterline is deliberately stable: the sea's small baked swell
    should not cause the wreck silhouette to flicker from frame to frame.
    """
    out = Mesh()
    for indices, col, layer, double, emissive in mesh.faces:
        polygon = [vertices[j] for j in indices]
        clipped = []
        for a, b in zip(polygon, polygon[1:] + polygon[:1]):
            a_in, b_in = a[1] >= water_y, b[1] >= water_y
            if a_in:
                clipped.append(a)
            if a_in != b_in:
                k = (water_y - a[1]) / (b[1] - a[1])
                clipped.append((lerp(a[0], b[0], k), water_y,
                                lerp(a[2], b[2], k)))
        if len(clipped) >= 3:
            out.face(clipped, col, layer, double, emissive)
    return out


def _beam(mesh, a, b, width, depth, color, layer=2):
    dx, dy, dz = (b[i] - a[i] for i in range(3))
    length = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
    axis = (dx / length, dy / length, dz / length)
    ref = (0.0, 0.0, 1.0) if abs(axis[1]) > 0.92 else (0.0, 1.0, 0.0)
    side = (axis[1] * ref[2] - axis[2] * ref[1],
            axis[2] * ref[0] - axis[0] * ref[2],
            axis[0] * ref[1] - axis[1] * ref[0])
    sl = math.sqrt(sum(v * v for v in side)) or 1.0
    side = tuple(v / sl for v in side)
    normal = (axis[1] * side[2] - axis[2] * side[1],
              axis[2] * side[0] - axis[0] * side[2],
              axis[0] * side[1] - axis[1] * side[0])
    verts = []
    for p in (a, b):
        for s, n in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
            verts.append(tuple(p[i] + s * side[i] * width / 2
                               + n * normal[i] * depth / 2 for i in range(3)))
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
              (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        mesh.face([verts[i] for i in f], color, layer, True)


# ── static world ────────────────────────────────────────────────────────
def _rig_local_parts():
    """Rig split into three hierarchically-collapsible parts, in LOCAL coords
    (origin = rig base at the waterline). ``_rig_mesh`` composes them at world
    position for the standing rig; the draw loop topples each part on its own
    pivot when the rig is destroyed (see OilRigAttack3D.draw)."""
    legs, deck, derrick = Mesh(), Mesh(), Mesh()
    steel, brace = (86, 96, 104), (56, 66, 76)
    hull, rust = (112, 118, 116), (98, 76, 58)
    # ── legs: the jacket (four legs, footings, two levels of horizontal + X bracing)
    for sx in (-1, 1):
        for sz in (-1, 1):
            px, pz = sx * 3.6, sz * 2.6
            legs.add(box(.52, DECK_Y, .52, steel, center=(px, DECK_Y / 2, pz), skip=("bottom",), seg=1.1))
            legs.add(box(.9, .3, .9, brace, center=(px, .18, pz), skip=("bottom",)))
    def jacket_beam(a, b, width, depth, color):
        for j in range(3):
            aa = tuple(lerp(a[k], b[k], j / 3) for k in range(3))
            bb = tuple(lerp(a[k], b[k], (j + 1) / 3) for k in range(3))
            _beam(legs, aa, bb, width, depth, color)

    for sz in (-1, 1):
        for y in (2.1, 4.3):
            jacket_beam((-3.6, y, sz * 2.6), (3.6, y, sz * 2.6), .16, .16, brace)
        jacket_beam((-3.6, .5, sz * 2.6), (3.6, DECK_Y - .4, sz * 2.6), .17, .15, steel)
        jacket_beam((3.6, .5, sz * 2.6), (-3.6, DECK_Y - .4, sz * 2.6), .17, .15, steel)
    for sx in (-1, 1):
        for y in (2.1, 4.3):
            jacket_beam((sx * 3.6, y, -2.6), (sx * 3.6, y, 2.6), .16, .16, brace)
        jacket_beam((sx * 3.6, .5, -2.6), (sx * 3.6, DECK_Y - .4, 2.6), .17, .15, steel)
        jacket_beam((sx * 3.6, .5, 2.6), (sx * 3.6, DECK_Y - .4, -2.6), .17, .15, steel)
    # ── deck: shadow girder + topside slab, railings, module/deckhouse, helipad,
    #    pipe rack, flare-stack boom and deck crane (deck equipment folds with it).
    deck.add(box(9.2, .34, 7.0, (66, 74, 78), center=(0, DECK_Y - .17, 0), skip=("bottom",)))
    deck.add(box(8.8, .5, 6.6, hull, center=(0, DECK_Y + .25, 0), skip=("bottom",),
                 cols={"top": (134, 138, 130), "front": (88, 98, 102), "back": (78, 88, 94)}))
    rail = (118, 126, 126)
    for i in (-4, -2, 0, 2, 4):
        for sz in (-1, 1):
            deck.add(box(.09, .55, .09, rail, center=(i * 1.05, DECK_Y + .78, sz * 3.25)))
    for sz in (-1, 1):
        _beam(deck, (-4.2, DECK_Y + 1.04, sz * 3.25), (4.2, DECK_Y + 1.04, sz * 3.25), .06, .06, rail)
    for sx in (-1, 1):
        _beam(deck, (sx * 4.2, DECK_Y + 1.04, -3.25), (sx * 4.2, DECK_Y + 1.04, 3.25), .06, .06, rail)
    deck.add(box(4.6, .4, 3.6, (102, 108, 106), center=(-1.6, DECK_Y + .7, -.8), skip=("bottom",)))
    deck.add(box(2.6, 1.5, 2.2, (94, 102, 106), center=(-1.9, DECK_Y + 1.65, -1.1),
                 cols={"front": (110, 120, 124), "top": (120, 126, 122)}))
    for i in range(3):
        deck.add(box(.34, .26, .04, (224, 238, 216), emissive=True,
                     center=(-2.6 + i * .7, DECK_Y + 1.8, -2.21)))
    deck.add(box(1.6, 1.1, 1.8, (88, 96, 100), center=(2.5, DECK_Y + 1.05, -2.0),
                 cols={"front": (104, 114, 118)}))
    deck.add(box(.3, .22, .04, (255, 196, 120), emissive=True,
                 center=(2.5, DECK_Y + 1.2, -1.08)))
    deck.add(disc_xz(2.6, 1.7, 1.55, DECK_Y + .51, (56, 72, 68), n=10))
    deck.add(disc_xz(2.6, 1.7, 1.1, DECK_Y + .53, (66, 86, 78), n=10))
    _beam(deck, (-4.2, DECK_Y + .62, -3.0), (4.2, DECK_Y + .62, -3.0), .12, .12, (118, 114, 98))
    _beam(deck, (-4.2, DECK_Y + .84, -3.0), (4.2, DECK_Y + .84, -3.0), .1, .1, rust)
    # Flare stack boom; its flame sprite is added per-frame while ONLINE.
    _beam(deck, (3.4, DECK_Y + .4, -2.2), (6.2, DECK_Y + 4.6, -3.6), .22, .22, rust)
    deck.add(box(.34, .5, .34, (70, 60, 52), center=(6.2, DECK_Y + 4.7, -3.6)))
    # Deck crane reaching out over the water.
    deck.add(box(.8, .9, .8, rust, center=(-3.6, DECK_Y + .95, 2.2)))
    _beam(deck, (-3.6, DECK_Y + 1.3, 2.2), (-8.2, DECK_Y + 4.4, 4.6), .18, .14, (150, 88, 62))
    _beam(deck, (-8.2, DECK_Y + 4.4, 4.6), (-8.2, DECK_Y + 1.2, 4.6), .07, .07, brace)
    # ── derrick: a real square lattice tower, not a flat ladder.
    base_y, top_y, hb, ht, dz = DECK_Y + .5, DECK_Y + 8.4, 1.7, .42, .4
    for sx in (-1, 1):
        for sz in (-1, 1):
            _beam(derrick, (sx * hb, base_y, dz + sz * hb),
                  (sx * ht, top_y, dz + sz * ht), .2, .2, steel)
    for lvl in range(1, 5):
        y = base_y + (top_y - base_y) * lvl / 5
        h = hb + (ht - hb) * lvl / 5
        derrick.add(box(2 * h + .12, .12, .12, brace, center=(0, y, dz - h)))
        derrick.add(box(2 * h + .12, .12, .12, brace, center=(0, y, dz + h)))
        derrick.add(box(.12, .12, 2 * h + .12, brace, center=(-h, y, dz)))
        derrick.add(box(.12, .12, 2 * h + .12, brace, center=(h, y, dz)))
    derrick.add(box(1.1, .5, 1.1, steel, center=(0, top_y + .25, dz)))
    derrick.add(box(.1, 1.2, .1, brace, center=(0, top_y + 1.1, dz)))
    return legs, deck, derrick


def _rig_mesh(index):
    """Standing rig at world position. Composed from the local parts so the
    collapse animation and the baked rig share one geometry source."""
    x, z = RIGS[index]
    m = Mesh()
    for part in _rig_local_parts():
        m.add(part, t=(x, 0, z))
    return m


def _water_mesh():
    m = Mesh()
    nx, nz = 40, 30
    x0, x1, z0, z1 = -110.0, 110.0, -24.0, 150.0
    cw, cd = (x1 - x0) / nx, (z1 - z0) / nz

    def swell(x, z):
        return (.30 * math.sin(x * .16 + z * .21)
                + .18 * math.sin(x * .34 - z * .13)
                + .06 * math.sin(x * .9 + z * 1.3))

    grid = [[(x0 + cw * i, swell(x0 + cw * i, z0 + cd * j), z0 + cd * j)
             for j in range(nz + 1)] for i in range(nx + 1)]
    for i in range(nx):
        for j in range(nz):
            p = (grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1])
            dy_dx = (grid[i + 1][j][1] - grid[i][j][1]) / cw
            dy_dz = (grid[i][j + 1][1] - grid[i][j][1]) / cd
            # Moon is screen-left behind the camera: west/front wave faces glint.
            glint = max(0.0, -dy_dx) * 1.5 + max(0.0, dy_dz) * .35
            v = ((i * 7 + j * 13) % 5) * .016
            k = clamp(.82 + glint + v, .5, 1.65)
            m.face(p, tuple(int(c * k) for c in SEA_COL), 0, True)
    return m


# ── sprite painters (must stay within ~3.4m of their anchor for the GL depth mask) ──
def _flame_fn(seed, t, size_m, heat=1.0, smoke_mix=0.0, drift=0.0):
    def draw(s, sx, sy, scale, z):
        r = max(5, int(size_m * scale))
        w_, h_ = r * 2 + 8, int(r * 2.6) + 8
        img = pygame.Surface((w_, h_), pygame.SRCALPHA)
        cx, cy = w_ // 2, h_ - 6
        n = 15
        for i in range(n):
            speed = .06 + (i % 3) * .02
            f = (i / n + t * speed + seed * .13) % 1.0
            ph = seed * 1.93 + i * 2.41
            spread = .3 + .32 * math.sin(f * math.pi)
            ox = (math.sin(ph + t * .14) * spread + drift * f * .7) * r
            oy = -f * r * 1.55
            rw = max(1.5, r * (.42 - f * .24) * (1 + .15 * math.sin(t * .3 + ph)))
            rh = rw * 1.7
            hc = (1 - f) * heat
            col = (int(110 + 145 * hc), int(28 + 150 * hc * hc), int(6 + 40 * hc ** 3))
            a = int((38 + 90 * hc) * heat)
            rect = pygame.Rect(0, 0, rw * 2, rh * 2)
            rect.center = (cx + int(ox), cy + int(oy))
            pygame.draw.ellipse(img, (*col, min(160, a)), rect)
        s.blit(img, (int(sx) - cx, int(sy) - cy), special_flags=pygame.BLEND_RGBA_ADD)
    return draw


def _smoke_fn(seed, t, size_m, drift=1.0, density=1.0):
    def draw(s, sx, sy, scale, z):
        r = max(6, int(size_m * scale))
        d = r * 2 + 8
        img = pygame.Surface((d, d), pygame.SRCALPHA)
        cx, cy = d // 2, d // 2 + int(r * .4)
        n = 12
        for i in range(n):
            f = (i / n + t * .035 + seed * .31) % 1.0
            ph = seed * 2.17 + i * 1.83
            ox = int((math.sin(ph + t * .05) * .35 + drift * f * .9) * r)
            oy = -int(f * r * .82)
            rr = max(2, int(r * (.34 + f * .55)))
            sh = int(46 + f * 24 + 6 * math.sin(ph + t * .1))
            env = math.sin(f * math.pi) ** .8
            a = int(92 * density * env)
            if a <= 3:
                continue
            pygame.draw.circle(img, (sh, sh - 2, sh + 2, min(120, a)), (cx + ox, cy + oy), rr)
        s.blit(img, (int(sx) - cx, int(sy) - cy))
    return draw


def _flash_fn(seed, age):
    def draw(s, sx, sy, scale, z):
        early = max(0.0, 1.0 - age / 14.0)
        if early <= 0:
            return
        r = min(int(3.3 * scale), int((1.1 + age * .22) * scale))
        if r < 4:
            return
        d = r * 2 + 4
        img = pygame.Surface((d, d), pygame.SRCALPHA)
        c = d // 2
        for rf, col, ka in ((1.0, (255, 96, 32), .45), (.8, (255, 140, 50), .55),
                            (.6, (255, 180, 80), .65), (.42, (255, 214, 130), .8),
                            (.26, (255, 236, 190), .9), (.13, (255, 250, 224), 1.0)):
            rr = int(r * rf)
            if rr > 1:
                pygame.draw.circle(img, (*col, int(235 * early * ka)), (c, c), rr)
        s.blit(img, (int(sx) - c, int(sy) - c))
    return draw


def _sparks_fn(seed, age):
    def draw(s, sx, sy, scale, z):
        if age > 55:
            return
        rng = random.Random(seed)
        hot = max(0.0, 1.0 - age / 55.0)
        for i in range(14):
            ang = -math.pi * .9 + 1.8 * math.pi * (i / 13.0) + rng.uniform(-.12, .12)
            spd = (1.2 + rng.random() * 2.2) * scale * .09
            age_i = age - rng.randint(0, 8)
            if age_i <= 0:
                continue
            dx = math.cos(ang) * spd * age_i
            dy = math.sin(ang) * spd * age_i + .004 * age_i * age_i
            px, py = sx + dx, sy - min(dy, 3.0 * scale)
            tail = 4 + 6 * hot
            col = (255, int(120 + 90 * hot), 50) if i % 3 else (120, 110, 105)
            pygame.draw.line(s, col, (px, py),
                             (px - math.cos(ang) * tail, py + math.sin(ang) * tail), 1)
    return draw


def _reflection_fn(seed, t, heat):
    def draw(s, sx, sy, scale, z):
        w = max(8, int(2.6 * scale))
        h = max(6, int(3.1 * scale))
        img = pygame.Surface((w, h), pygame.SRCALPHA)
        for j in range(9):
            yy = int(2 + j * h / 10)
            wob = math.sin(t * .13 + j * 1.7 + seed) * w * .16
            seg = w * (.62 - j * .05) * (.65 + .35 * math.sin(t * .21 + j * 2.3))
            a = int(130 * heat * (1 - j / 10.0))
            if a <= 3 or seg <= 1:
                continue
            pygame.draw.line(img, (255, int(110 + 50 * heat), 38, a),
                             (w // 2 + int(wob - seg / 2), yy),
                             (w // 2 + int(wob + seg / 2), yy), 1)
        s.blit(img, (int(sx) - w // 2, int(sy)))
    return draw


def _glow_fn(color, radius_m, pulse=0.0, t=0):
    def draw(s, sx, sy, scale, z):
        k = 1.0 + pulse * math.sin(t * .25)
        r = max(2, int(radius_m * scale * k))
        d = r * 4 + 4
        img = pygame.Surface((d, d), pygame.SRCALPHA)
        c = d // 2
        for rr, a in ((r * 2, 60), (int(r * 1.3), 120), (r, 235)):
            if rr >= 1:
                pygame.draw.circle(img, (*color, a), (c, c), rr)
        s.blit(img, (int(sx) - c, int(sy) - c))
    return draw


def _beacon_fn(seed, t, targeted):
    def draw(s, sx, sy, scale, z):
        if targeted:
            k = .6 + .4 * math.sin(t * .3)
            col, r_m = (255, 190, 70), .42 * k
        else:
            if (t + seed * 40) % 70 > 6:
                return
            col, r_m = (255, 70, 55), .3
        r = max(2, int(r_m * scale))
        pygame.draw.circle(s, col, (int(sx), int(sy)), r)
        pygame.draw.circle(s, (255, 240, 210), (int(sx), int(sy)), max(1, r // 2))
    return draw


def _boat_light_fn(t):
    def draw(s, sx, sy, scale, z):
        phase = t % 80
        on = phase < 5 or 12 < phase < 17
        col = (255, 84, 62) if on else (118, 42, 36)
        pygame.draw.circle(s, col, (int(sx), int(sy)), max(1, int(.22 * scale)))
    return draw


# ── dynamic world ───────────────────────────────────────────────────────
def _glitter_mesh(t):
    m = Mesh()
    rng = random.Random(7)
    for i in range(120):
        gx = -32 + rng.random() * 36
        gz = 6 + rng.random() * 112
        tw = .5 + .5 * math.sin(t * .11 + i * 2.17)
        if tw < .3:
            continue
        b = 80 + int(120 * tw)
        w = .3 + .35 * rng.random()
        m.face([(gx - w, .22, gz), (gx + w, .22, gz),
                (gx + w, .22, gz + .16), (gx - w, .22, gz + .16)],
               (int(b * .72), int(b * .88), b), 1, True)
    return m


def _foam_mesh(t):
    m = Mesh()
    for x, z in RIGS:
        for j in range(4):
            a = t * .025 + j * 1.57 + x
            rr = 3.9 + .4 * math.sin(t * .06 + j * 2.1)
            fx, fz = x + math.cos(a) * rr, z + math.sin(a) * rr * .72
            b = 52 + int(38 * (.5 + .5 * math.sin(t * .09 + j * 1.3)))
            m.face([(fx - .55, .16, fz), (fx + .55, .16, fz),
                    (fx + .45, .16, fz + .3), (fx - .45, .16, fz + .3)],
                   (b, int(b * 1.18), int(b * 1.3)), 1, True)
    return m



def _water_entry_mesh(index, since):
    """Expanding broken foam ring and ballistic spray at the actual low edge."""
    m = Mesh()
    age = since - WATER_CONTACT_FRAME
    if age < 0 or age >= 128:
        return m
    x, _, z = _water_contact(index)
    env = math.sin(math.pi * clamp(age / 128)) ** .6
    radius = 2.1 + age * .065
    width = .16 + .3 * env
    for j in range(24):
        if j % 5 == 0:
            continue
        a, b = j * math.tau / 24, (j + .72) * math.tau / 24
        pts = [(x + math.cos(ang) * rr, .28, z + math.sin(ang) * rr * .72)
               for ang, rr in ((a, radius), (b, radius),
                               (b, radius + width), (a, radius + width))]
        bright = int(45 + 115 * env)
        m.face(pts, (bright, min(230, bright + 20), min(245, bright + 32)), 1, True)
    # Small separate shards of spray stay near the contact edge, never a wall.
    if age < 44:
        for j in range(14):
            flight = age - (j % 4) * 2
            if flight <= 0:
                continue
            a = j * 2.399 + index
            y = .28 + (.12 + .015 * (j % 3)) * flight - .004 * flight * flight
            if y <= .28:
                continue
            rr = 1.3 + .055 * flight
            sx, sz = x + math.cos(a) * rr, z + math.sin(a) * rr * .7
            m.add(box(.08, .18, .08, (155, 186, 202), center=(sx, y, sz), layer=2))
    return m


def _boat_mesh():
    """Lofted patrol-boat hull (bow +z) with bridge, rails, gun and radar."""
    m = Mesh()
    # station z, half-width at deck, deck height, keel half-width, keel height
    st = ((-2.9, .86, .86, .62, .3), (-1.6, .94, .86, .5, .16), (0.0, .96, .9, .42, .12),
          (1.5, .82, .96, .26, .14), (2.9, .5, 1.06, .1, .3), (3.95, .0, 1.18, .0, .66))
    top, side_l, side_r = (96, 104, 104), (46, 56, 64), (70, 80, 86)
    for (z0, w0, d0, kw0, k0), (z1, w1, d1, kw1, k1) in zip(st, st[1:]):
        # deck
        m.face([(-w0, d0, z0), (w0, d0, z0), (w1, d1, z1), (-w1, d1, z1)], top, 3, True)
        # hull sides (upper plate + red boot-stripe below)
        for sg, col in ((-1, side_l), (1, side_r)):
            mid0, mid1 = d0 - .28, d1 - .28
            m.face([(sg * w0, d0, z0), (sg * w1, d1, z1), (sg * w1, mid1, z1), (sg * w0, mid0, z0)], col, 3, True)
            m.face([(sg * w0, mid0, z0), (sg * w1, mid1, z1), (sg * kw1, k1, z1), (sg * kw0, k0, z0)],
                   (128, 46, 40) if sg > 0 else (104, 38, 34), 3, True)
        # bottom
        m.face([(-kw0, k0, z0), (kw0, k0, z0), (kw1, k1, z1), (-kw1, k1, z1)], (30, 34, 38), 3, True)
    # transom
    m.face([(-.86, .86, -2.9), (.86, .86, -2.9), (.62, .3, -2.9), (-.62, .3, -2.9)], (40, 46, 52), 3, True)
    # gunwale rails (thin raised strips along both sides)
    for sg in (-1, 1):
        m.add(box(.07, .1, 4.6, (150, 156, 154), center=(sg * .82, 1.0, -.5), layer=3))
    # white-ish accent line on the deck edge near the bow
    m.add(box(.5, .02, .9, (210, 214, 210), center=(0, 1.15, 2.55), layer=3))
    # superstructure: lower house + bridge + roof
    m.add(box(1.35, .62, 1.9, (150, 156, 158), center=(0, 1.3, -.7), layer=3,
              cols={"top": (176, 182, 184), "left": (118, 126, 130), "right": (136, 144, 148),
                    "front": (160, 168, 170)}))
    m.add(box(1.1, .5, 1.05, (126, 134, 138), center=(0, 1.86, -.35), layer=3,
              cols={"top": (166, 172, 174), "left": (104, 112, 116), "right": (120, 128, 132)}))
    # bridge windows (forward + sides), emissive
    m.add(box(1.0, .22, .04, (196, 226, 232), emissive=True, center=(0, 1.9, .2), layer=4))
    for sg in (-1, 1):
        m.add(box(.04, .2, .7, (196, 226, 232), emissive=True, center=(sg * .56, 1.9, -.35), layer=4))
    # roof: radar mast with rotating-looking bar, antenna whip
    m.add(box(.1, .8, .1, (60, 66, 70), center=(0, 2.6, -.5), layer=3))
    m.add(box(.9, .07, .12, (190, 196, 196), center=(0, 3.02, -.5), layer=3))
    m.add(box(.04, 1.2, .04, (40, 44, 46), center=(.4, 2.75, -.9), layer=3))
    # funnel at the stern of the house
    m.add(box(.4, .5, .4, (70, 74, 78), center=(0, 2.15, -1.35), layer=3))
    # foredeck gun: pedestal + barrel
    m.add(box(.34, .22, .34, (72, 78, 80), center=(0, 1.26, 1.9), layer=3))
    m.add(box(.2, .16, .2, (88, 94, 96), center=(0, 1.45, 1.9), layer=3))
    m.add(box(.07, .07, .85, (46, 50, 52), center=(0, 1.47, 2.4), layer=3))
    # stern: twin outboard engines + cleats
    for sg in (-1, 1):
        m.add(box(.26, .55, .3, (36, 40, 44), center=(sg * .38, .7, -3.05), layer=3))
    # deck cargo / life raft
    m.add(box(.5, .22, .6, (214, 120, 52), center=(.4, 1.1, -2.2), layer=3))
    return m


def _wake_mesh(bx, t):
    m = Mesh()
    for j in range(1, 9):
        spread = .4 + j * .34
        fade = 1 - j / 9.0
        b = 44 + int(66 * fade * (.6 + .4 * math.sin(t * .1 + j * 1.9)))
        col = (b, int(b * 1.15), int(b * 1.28))
        wx = bx - j * .9
        for sgn in (-1, 1):
            wz = 22 + sgn * spread
            m.face([(wx - .5, .14, wz), (wx + .5, .14, wz),
                    (wx + .45, .14, wz + .3 * sgn), (wx - .45, .14, wz + .3 * sgn)],
                   col, 1, True)
    b = 110 + int(45 * math.sin(t * .4))
    m.face([(bx + 2.6, .15, 21.4), (bx + 3.4, .15, 21.9), (bx + 3.4, .15, 22.1), (bx + 2.6, .15, 22.6)],
           (b, int(b * 1.1), int(b * 1.2)), 1, True)
    return m


def _missile_mesh(length=5.2, radius=.3):
    """Missile along +z: ogive nose, banded body, 4 swept fins, nozzle."""
    m = Mesh()
    n = 8
    def ring(z, r, rot=0.0):
        return [(math.cos(rot + k * math.tau / n) * r, math.sin(rot + k * math.tau / n) * r, z)
                for k in range(n)]
    rings = [  # z fraction, radius fraction, colour
        (-.50, .78, (60, 62, 66)), (-.46, 1.0, (60, 62, 66)),
        (-.46, 1.0, (200, 204, 200)), (.05, 1.0, (200, 204, 200)),
        (.05, 1.0, (190, 56, 44)), (.10, 1.0, (190, 56, 44)),
        (.10, 1.0, (214, 218, 212)), (.22, 1.0, (214, 218, 212)),
        (.22, .98, (86, 92, 70)), (.30, .9, (86, 92, 70)),
        (.40, .62, (74, 80, 62)), (.46, .3, (60, 64, 54)), (.5, 0.0, (50, 52, 48)),
    ]
    prev = None
    for fz, fr, col in rings:
        cur = ring(fz * length, fr * radius)
        if prev is not None and prev[1] is not None:
            (pp, pc), cc = prev, cur
            for k in range(n):
                k2 = (k + 1) % n
                shade = .72 + .28 * math.cos((k + .5) * math.tau / n - .8)
                c = tuple(min(255, int(v * shade)) for v in col)
                m.face([pp[k], pp[k2], cc[k2], cc[k]], c, 3, True)
        prev = (cur, col)
    # fins
    fin = (70, 74, 78)
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        ca, sa = math.cos(a), math.sin(a)
        def P(rr, z):
            return (ca * rr, sa * rr, z)
        m.face([P(radius * .9, -.5 * length), P(radius * 2.5, -.58 * length),
                P(radius * 2.5, -.46 * length), P(radius * .9, -.2 * length)], fin, 3, True)
    # canards near the nose
    for k in range(2):
        a = k * math.pi
        ca, sa = math.cos(a), math.sin(a)
        m.face([(ca * radius * .8, sa * radius * .8, .26 * length),
                (ca * radius * 1.6, sa * radius * 1.6, .22 * length),
                (ca * radius * .8, sa * radius * .8, .18 * length)], fin, 3, True)
    # nozzle glow disc
    m.face(ring(-.505 * length, radius * .62), (255, 190, 90), 4, True, True)
    return m


def _orient_missile(mesh, pos, direction):
    """Rotate a +z-pointing mesh so +z follows ``direction``; translate to pos."""
    dx, dy, dz = direction
    ln = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
    f = (dx / ln, dy / ln, dz / ln)
    up = (0.0, 1.0, 0.0) if abs(f[1]) < .98 else (1.0, 0.0, 0.0)
    rx = (up[1] * f[2] - up[2] * f[1], up[2] * f[0] - up[0] * f[2], up[0] * f[1] - up[1] * f[0])
    rl = math.sqrt(sum(c * c for c in rx)) or 1.0
    rx = tuple(c / rl for c in rx)
    uy = (f[1] * rx[2] - f[2] * rx[1], f[2] * rx[0] - f[0] * rx[2], f[0] * rx[1] - f[1] * rx[0])
    out = []
    for x, y, z in mesh.verts:
        out.append((pos[0] + rx[0] * x + uy[0] * y + f[0] * z,
                    pos[1] + rx[1] * x + uy[1] * y + f[1] * z,
                    pos[2] + rx[2] * x + uy[2] * y + f[2] * z))
    return out


def _missile_pos(m, u=None):
    tx, tz = RIGS[m["rig_index"]]
    if u is None:
        u = m["t"]
    sx = -29 + min(1.0, max(0.0, m["start_x"] / 920.0)) * 57 + 1
    return (sx + (tx - sx) * u,
            1.6 + math.sin(u * math.pi) * 12.5,
            22 + (tz - 22) * u)


class OilRigAttack3D:
    def __init__(self, width, height):
        self.w, self.h = max(1, width // 2), max(1, height // 2)
        self.r = Renderer(self.w, self.h, fog=FOG_COL, fog_start=40, fog_end=135)
        self.r.light.ambient, self.r.light.diffuse, self.r.light.sky = .5, .62, .1
        self.r.light.dir = (-0.45, 0.75, -0.5)
        self.r.light.tint = (0.86, 0.92, 1.06)
        self.r.bake(_water_mesh(), tag="storm-sea")
        self.rigs = [self.r.bake(_rig_mesh(i), tag="oil-rig-%d" % i) for i in range(3)]
        self.rig_parts = _rig_local_parts()  # (legs, deck, derrick), local coords
        self.boat = _boat_mesh()
        self.missile = _missile_mesh()
        self._bg = pygame.Surface((self.w, self.h))
        srng = random.Random(11)
        self._stars = [(srng.uniform(0, 1), srng.uniform(0, .42), srng.random())
                       for _ in range(70)]

    # ── screen-space sky (drawn into _bg under the 3D scene) ──
    def _paint_sky(self, t, cam):
        bg = self._bg
        w, h = self.w, self.h
        horizon = int(h * .52)
        for y in range(h):
            if y < horizon:
                f = y / max(1, horizon)
                c = (int(10 + 30 * f), int(17 + 35 * f), int(34 + 34 * f))
            else:
                c = (36, 46, 60)
            pygame.draw.line(bg, c, (0, y), (w, y))
        # stars
        for fx, fy, tw in self._stars:
            a = .35 + .65 * abs(math.sin(t * .05 + tw * 9))
            b = int(120 * a * (1 - fy * 1.8))
            if b > 12:
                bg.set_at((int(fx * w), int(fy * horizon)), (b, b, int(b * 1.1)))
        # moon + halo, slight parallax against the camera
        mx = int(w * .21 - cam[0] * .45)
        my = int(h * .16 - (cam[1] - 8) * .8)
        for rr, a in ((34, 6), (26, 10), (19, 14), (14, 20), (11, 26)):
            glow = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (190, 205, 225, a), (rr, rr), rr)
            bg.blit(glow, (mx - rr, my - rr))
        pygame.draw.circle(bg, (224, 230, 234), (mx, my), 9)
        pygame.draw.circle(bg, (200, 208, 214), (mx - 3, my + 2), 3)
        pygame.draw.circle(bg, (210, 217, 222), (mx + 3, my - 3), 2)
        # slow cloud bands, soft and thin
        for i in range(4):
            cw = int(w * (.3 + .09 * i))
            ch = 8 + i * 3
            cx = int((i * 260 + t * .05 * (1 + i * .3) - cam[0] * (.5 + i * .18)) % (w + cw) - cw // 2)
            cy = int(h * (.06 + .06 * i))
            cloud = pygame.Surface((cw, ch * 4), pygame.SRCALPHA)
            for inset, a in ((0, 26), (1, 20), (2, 14)):
                pygame.draw.ellipse(cloud, (16, 22, 36, a),
                                    (inset * 6, inset * 3, cw - inset * 12, ch * 4 - inset * 6))
            bg.blit(cloud, (cx, cy))
        # horizon mist band
        mist = pygame.Surface((w, 14), pygame.SRCALPHA)
        for yy in range(14):
            a = int(26 * (1 - abs(yy - 7) / 7))
            pygame.draw.line(mist, (*FOG_COL, a), (0, yy), (w, yy))
        bg.blit(mist, (0, horizon - 7))

    def _camera(self, t, shake, cuts):
        center, left, right, aftermath = cuts

        def drift(a, b, t0, t1):
            k = clamp((t - t0) / max(1.0, t1 - t0))
            k = k * k * (3 - 2 * k)
            return (lerp(a[0], b[0], k), lerp(a[1], b[1], k), lerp(a[2], b[2], k))

        if t < center:
            p = drift((-10.5, 8.4, -15), (-8, 7.8, -12.5), -90, center)
            q, fov = (1.2, 6.8, 42), 52
        elif t < left:
            p = drift((-3.2, 8.8, -2), (-2.2, 8.4, -3.6), center, left)
            q, fov = (0, 7.6, 37), 45
        elif t < right:
            p = drift((-26, 8.2, 14), (-27.5, 7.8, 15.8), left, right)
            q, fov = (-20, 7.2, 52), 44
        elif t < aftermath:
            p = drift((10.5, 9.6, 4), (12, 9, 2.2), right, aftermath)
            q, fov = (19, 7.2, 46), 45
        else:
            a = (t - aftermath) / 600.0
            p = (math.sin(a * .5) * 4.5, 10.8 + math.sin(t * .008) * .25, -18)
            q, fov = (0, 6.5, 44), 50
        self.r.set_camera((p[0], p[1], p[2]), (q[0], q[1], q[2]), fov,
                          roll=min(1.4, shake * .018))
        return p

    def draw(self, surface, state, impact_frames, force=False, shot_frames=(850, 1270, 1710, 2320)):
        t = state.walk_attack_timer
        w, h = surface.get_size()
        shake = 0 if getattr(state, "reduced_motion", False) else max(0, int(state.screen_shake))
        if state.screen_shake:
            state.screen_shake = max(0, state.screen_shake - 1)
        cam = self._camera(t, shake, shot_frames)
        self._paint_sky(t, cam)
        r = self.r
        r.begin()
        for i, obj in enumerate(self.rigs):
            obj.visible = state.rig_status[i] != "DESTROYED"
        r.add_static()

        def add(mesh, bias=0.0):
            r.add_dynamic(mesh.verts,
                          [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces],
                          bias=bias)

        add(_glitter_mesh(t))
        add(_foam_mesh(t))

        # attack boat: travels +x, bow first, with a trailing wake.
        boat_x = -29 + min(1.0, max(0.0, state.walk_boat_x / 920.0)) * 57
        if state.walk_boat_active:
            yaw = 90 + math.degrees(.09 * math.sin(t * .03))
            roll = math.degrees(.05 * math.sin(t * .11))
            tf = m_mul(rot_y(yaw), rot_z(roll))
            bob = .06 * math.sin(t * .09)
            verts = [tuple(m_apply(tf, v)[i] + (boat_x, .12 + bob, 22)[i]
                           for i in range(3)) for v in self.boat.verts]
            r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in self.boat.faces])
            add(_wake_mesh(boat_x, t))
            r.add_sprite((boat_x - .5, 3.2, 22), _boat_light_fn(t), layer=6)

        # rigs: flare flame + nav beacon while alive, fire + smoke once burning.
        for i, status in enumerate(state.rig_status):
            x, z = RIGS[i]
            if status == "DESTROYED":
                since = max(0, t - impact_frames[i])
                heat = max(.55, 1.0 - since / 1400.0)
                reduced = getattr(state, "reduced_motion", False)
                # Shared local collapse pose; translate EVERY part to this rig.
                # Keep geometry/materials continuous with the baked standing rig.
                poses, sink = _collapse_parts(self.rig_parts, since, i, reduced)
                flip = -1 if i == 2 else 1
                char_t = smooth(clamp((since - COLLAPSE_FRAMES) / 500.0))
                char_amt = 0.62 * char_t
                tint = ((40, 38, 36), char_amt) if char_amt > 0.02 else None
                for mesh, verts in zip(self.rig_parts, poses):
                    wreck = _visible_wreck(mesh, _rig_world_vertices(verts, i))
                    r.add_dynamic(wreck.verts,
                                  [(f[0], f[1], f[2], f[3], None, f[4])
                                   for f in wreck.faces], tint=tint)
                anchors = _rig_fire_anchors(since, i, reduced)
                # Smaller flames reveal the collapse silhouette. Submerged
                # sockets quench; the remaining oil fire sits on the water.
                fx_t = impact_frames[i] + 600 if reduced else t
                for j, anchor in enumerate(anchors):
                    wet = smooth(clamp((.4 - anchor[1]) / 1.0))
                    fire_pos = (anchor[0], max(.28, anchor[1]), anchor[2])
                    r.add_sprite(fire_pos,
                                 _flame_fn(i * 17 + j, fx_t, 1.05 - j * .15,
                                           heat * (1 - wet * .55)), layer=5)
                source = anchors[0]
                smoke_age = 600 if reduced else since
                smoke_build = .25 + .75 * smooth(smoke_age / 180)
                for j in range(2):
                    r.add_sprite((source[0] + .8 + j, max(.8, source[1]) + 2.4 + j * 2.7,
                                  source[2] + .3),
                                 _smoke_fn(i * 11 + j, fx_t, 1.05 + j * .25,
                                           drift=1.0 + .3 * j,
                                           density=heat * smoke_build * .65), layer=5)
                # Splash starts on the existing +68f audio cue, steam follows.
                if not reduced:
                    add(_water_entry_mesh(i, since))
                    water_age = since - WATER_CONTACT_FRAME
                    if 0 <= water_age < 100:
                        contact = _water_contact(i)
                        density = math.sin(math.pi * water_age / 100) * .65
                        r.add_sprite((contact[0], .6, contact[2]),
                                     _smoke_fn(i * 41 + 3, t, 1.1, drift=.7,
                                               density=density), layer=4)
                r.add_sprite((source[0], .5, source[2]),
                             _reflection_fn(i * 13 + 5, fx_t, heat * .75), layer=1)
            else:
                r.add_sprite((x + 6.2, DECK_Y + 5.05, z - 3.6),
                             _flame_fn(i * 17 + 7, t, .45, heat=.8), layer=5)
                r.add_sprite((x, DECK_Y + 9.5, z + .4), _beacon_fn(i, t, status == "TARGETED"), layer=6)

        # missiles: segmented smoke trail + hot warhead, not one solid laser line.
        for m in state.walk_missiles:
            head = _missile_pos(m)
            prev = None
            for j in range(13, -1, -1):
                uj = m["t"] - j * .022
                if uj < 0:
                    continue
                pj = _missile_pos(m, uj)
                if prev is not None:
                    age = j / 13.0
                    col = mix_col((255, 178, 80), (78, 84, 96), age)
                    r.add_line3d(prev, pj, col, 2 if j < 5 else 1, layer=5)
                prev = pj
            ahead = _missile_pos(m, min(1.0, m["t"] + .01))
            behind = _missile_pos(m, max(0.0, m["t"] - .01))
            dirv = (ahead[0] - behind[0], ahead[1] - behind[1], ahead[2] - behind[2])
            mv = _orient_missile(self.missile, head, dirv)
            r.add_dynamic(mv, [(f[0], f[1], f[2], f[3], None, f[4]) for f in self.missile.faces])
            tail = _missile_pos(m, max(0.0, m["t"] - .004))
            r.add_sprite(tail, _glow_fn((255, 170, 70), .22, pulse=.1, t=t), layer=6)

        # impact bursts layered on top of the persistent fires.
        for i, impact in enumerate(impact_frames):
            dt = t - impact
            if 0 <= dt < 145:
                x, z = RIGS[i]
                reduced = getattr(state, "reduced_motion", False)
                origin = _rig_fire_anchors(dt, i, reduced)[0]
                if dt < 14 and not reduced:
                    r.add_sprite((x, DECK_Y + 1, z), _flash_fn(i, dt), layer=6)
                if dt < 60 and not reduced:
                    grow = min(1.0, dt / 26.0)
                    r.add_sprite(origin,
                                 _flame_fn(i * 23 + 9, t, .6 + .5 * grow, heat=.9), layer=6)
                    r.add_sprite((x, DECK_Y + 1.5, z), _sparks_fn(i * 31 + 4, dt), layer=6)
                elif dt < 145 and not reduced:
                    r.add_sprite((origin[0], max(.8, origin[1]) + 1.6, origin[2]),
                                 _smoke_fn(i * 37 + 2, t, 1.0, drift=.9, density=.5), layer=5)

        # rain falls straight down past the camera; two depths for parallax.
        for i in range(64):
            near = i < 40
            fall = (t * (.55 if near else .34) + i * 3.71) % 15
            ry = 15.5 - fall
            rx = cam[0] + math.sin(i * 12.9898) * (24 if near else 55)
            rz = cam[2] + 7 + (i * 7.13) % (30 if near else 90)
            ln = 1.6 if near else 2.4
            col = (86, 104, 124) if near else (66, 80, 100)
            r.add_line3d((rx, ry, rz), (rx - .45, ry - ln, rz + .12), col, 1, layer=6)

        rendered = self._bg.copy()
        r.flush(rendered)
        if (self.w, self.h) != (w, h):
            rendered = pygame.transform.scale(rendered, (w, h))
        ox = 0 if getattr(state, "reduced_motion", False) else int(math.sin(t * .9) * min(2, shake / 7))
        oy = 0 if getattr(state, "reduced_motion", False) else int(math.cos(t * .7) * min(2, shake / 9))
        surface.fill((0, 0, 0))
        surface.blit(rendered, (ox, oy))
        if not getattr(state, "reduced_motion", False) and any(0 <= t - f < 12 for f in impact_frames):
            flash = pygame.Surface((w, h), pygame.SRCALPHA)
            flash.fill((255, 165, 78, max(0, 75 - min(t - f for f in impact_frames if 0 <= t - f < 12) * 6)))
            surface.blit(flash, (0, 0))
        if t < 60:
            veil = pygame.Surface((w, h), pygame.SRCALPHA)
            veil.fill((0, 0, 0, max(0, min(255, int(255 * (1 - max(0, t) / 60))))))
            surface.blit(veil, (0, 0))


def draw_oilrig_attack_3d(surface, state, impact_frames, force=False, shot_frames=(850, 1270, 1710, 2320)):
    global _SCENE
    size = surface.get_size()
    if _SCENE is None or (_SCENE.w * 2, _SCENE.h * 2) != size:
        _SCENE = OilRigAttack3D(*size)
    _SCENE.draw(surface, state, impact_frames, force, shot_frames)
