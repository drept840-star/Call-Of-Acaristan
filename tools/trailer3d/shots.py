"""The trailer's shots. Each Shot covers [start, end) on the trailer clock
(seconds, see timeline.json) and renders W x H internal frames; overlay()
draws crisp full-res text on the 1920x1080 canvas."""
import math
import random

import pygame

import common as C
from common import (H, W, Rain, beam, clamp, ease_in, ease_out, fire_sprite, glow, glow_at,
                    glow_sprite, keys, lerp, muzzle_at, muzzle_sprite, seg, shake, smoke_sprite, smooth, vlerp)
import props3d as P

from engine3d import POSES, blend, box, disc_xz, m_apply, pose_run, quad_xz, rot_x, rot_y, rot_z


def pose_walk(phase, base="ready", amp=22):
    s, c = math.sin(phase), math.cos(phase)
    p = dict(POSES[base])
    p.update(lhip_p=amp * s + 3, rhip_p=-amp * s + 3, lkn=8 + 30 * max(0.0, -c),
             rkn=8 + 30 * max(0.0, c), lift=0.0)
    return p


def pose_stroll(phase):
    p = pose_walk(phase, "stand", amp=20)
    s = math.sin(phase)
    p.update(lsh_p=-14 * s + 6, rsh_p=14 * s + 6, lel=14, rel=14)
    return p


SEATED = dict(spine=4, lhip_p=88, lkn=90, rhip_p=88, rkn=90, lsh_p=34, lsh_r=10, lel=64,
              rsh_p=34, rsh_r=10, rel=64, rifle_p=60)


def hum(who, **kw):
    from cutscenes.cast3d import humanoid3d
    return humanoid3d(who, **kw)


def guard_spec(i):
    from cutscenes.cast3d import spec3d
    skins = [(200, 160, 130), (176, 138, 110), (150, 116, 92)]
    return spec3d("ucilev", hair_style="crop", helmet=(30, 31, 35), head_w=1.0, brow_t=3,
                  skin=skins[i % 3], iris=(30, 28, 26), rifle="rifle")


def guard(i):
    from engine3d import Humanoid
    return Humanoid(guard_spec(i))


def head_point(j, yaw, off):
    """World point at an offset (x right, y up, z forward) from the head joint."""
    q = m_apply(rot_y(yaw), off)
    h = j["head"]
    return (h[0] + q[0], h[1] + q[1], h[2] + q[2])


_IK_CACHE = {}


def ik_arm(hum, pose, pos, yaw, side, target, rifle_on=False, roll=(-40, 90)):
    """Shoulder/elbow angles that put the side ('l'/'r') hand at a world
    target (coordinate descent; cached). Returns the updated pose copy."""
    key = (id(hum), side, roll, tuple(round(v, 3) for v in target), tuple(round(v, 3) for v in pos), round(yaw, 2),
           tuple(sorted((k, round(v, 1)) for k, v in pose.items() if not k.startswith(side + "s") and k != side + "el")))
    names = (side + "sh_p", side + "sh_r", side + "el")
    if key in _IK_CACHE:
        out = dict(pose)
        out.update(_IK_CACHE[key])
        return out
    cur = dict(pose)
    for n, v0 in zip(names, (40.0, 10.0, 60.0)):
        cur.setdefault(n, v0)

    def err(q):
        _, j, _ = hum.pose_world(q, pos, yaw, rifle_on=rifle_on)
        h = j[side + "hand"]
        return sum((h[i] - target[i]) ** 2 for i in range(3))
    best = err(cur)
    step = 24.0
    lim = {names[0]: (-60, 170), names[1]: roll, names[2]: (0, 150)}
    while step > 0.4:
        improved = False
        for n in names:
            for d in (step, -step):
                q = dict(cur)
                q[n] = max(lim[n][0], min(lim[n][1], q[n] + d))
                e = err(q)
                if e < best - 1e-9:
                    best, cur, improved = e, q, True
        if not improved:
            step *= 0.5
    _IK_CACHE[key] = {n: cur[n] for n in names}
    return cur


class Shot:
    start = end = 0.0
    grain = 1.0
    letterbox = True

    def __init__(self, start, end):
        self.start, self.end = start, end
        self.r = None
        self.ready = False

    def setup(self):
        pass

    def ensure(self):
        if not self.ready:
            self.setup()
            self.ready = True

    def render(self, lt, T, frame):
        raise NotImplementedError

    def overlay(self, canvas, lt, T):
        pass

    def release(self):
        if self.r is not None and hasattr(self.r, "release"):
            try:
                self.r.release()
            except Exception:
                pass
        self.r = None
        self.ready = False

    # helper: draw scene = sky + static + callback
    def frame3d(self, sky, dyn=None, flush=True):
        r = self.r
        r.surface.blit(sky, (0, 0))
        r.begin()
        r.add_static()
        if dyn:
            dyn(r)
        if flush:
            r.flush(r.surface)
        return r.surface


def location_tag(canvas, txt, lt, t_in, t_out, y=None):
    if lt < t_in or lt > t_out + 0.6:
        return
    a = int(255 * clamp((t_out + 0.6 - lt) / 0.6)) if lt > t_out else 255
    s = C.typed(txt, lt - t_in, 22)
    if not s:
        return
    f = C.font("mono", 26)
    img = f.render(s + ("_" if int(lt * 3) % 2 and len(s) < len(txt) else ""), True, (210, 205, 190))
    img.set_alpha(a)
    y = C.BAR + H * C.SCALE - 70 if y is None else y
    canvas.blit(img, (90, y))
    pygame.draw.rect(canvas, C.ORANGE, (90, y - 10, 46, 4))


# ═══ 1. OCEAN ═══════════════════════════════════════════════════════════
class Ocean(Shot):
    def setup(self):
        self.r = C.renderer((24, 32, 44), 40, 420, C.light((0.15, 0.45, 0.88), 0.30, 0.95, sky=0.04))
        self.ocean = P.Ocean()
        self.flares = []
        self.lights = []
        for pos, seed, fl in (((22, 0, 150), 1, True), ((-70, 0, 240), 2, True), ((105, 0, 300), 3, False)):
            m, tip, li = P.oil_platform(seed, fl)
            self.r.bake(m, t=pos)
            if tip:
                self.flares.append(tuple(a + b for a, b in zip(tip, pos)))
            self.lights += [tuple(a + b for a, b in zip(l_, pos)) for l_ in li]
        self.sky = C.gradient((5, 7, 12), (34, 42, 56), mid=(0.62, (14, 18, 28)))
        C.stars(self.sky, 140, 9, H * 0.55)
        glow(self.sky, 120, 40, 90, (40, 44, 56))
        pygame.draw.circle(self.sky, (196, 200, 210), (120, 40), 7)

    def render(self, lt, T, frame):
        r = self.r
        u = lt / 8.86
        pos = keys([(0, (0.0, 40.0, -40.0)), (8.86, (8.0, 3.0, 12.0))], lt, ease=lambda x: 1 - (1 - x) ** 2.2)
        tgt = keys([(0, (12.0, 4.0, 160.0)), (8.86, (20.0, 16.0, 150.0))], lt)
        r.set_camera(pos, tgt, lerp(54, 44, smooth(u)))

        def dyn(r):
            v, f = self.ocean.faces(lt)
            r.add_dynamic(v, f)
            for i, tip in enumerate(self.flares):
                fl = 0.5 + 0.5 * math.sin(lt * 17 + i * 3) * math.sin(lt * 7.3 + i)
                r.add_sprite(tip, fire_sprite(fl, size=1.6 if i == 0 else 1.2), layer=3)
        surf = self.frame3d(self.sky, dyn)
        for i, tip in enumerate(self.flares):
            fl = 0.8 + 0.2 * math.sin(lt * 11 + i)
            glow_at(r, surf, tip, 14 * fl, (120, 60, 20))
            pw = r.project((tip[0], 0.3, tip[2]))
            ph = r.project(tip)
            if pw and ph:
                x, y = pw[0], pw[1]
                for k in range(26):
                    yy = y + k * 2.2
                    wob = math.sin(lt * 4 + k * 0.9) * (1 + k * 0.15)
                    w = 1 + k * 0.18
                    c = (int(90 * (1 - k / 26)), int(40 * (1 - k / 26)), 8)
                    pygame.draw.line(surf, c, (x - w + wob, yy), (x + w + wob, yy))
        for p in self.lights:
            glow_at(r, surf, p, 2.2, (60, 50, 34))
        return surf

    def overlay(self, canvas, lt, T):
        location_tag(canvas, "KILEMENO OCEAN  //  03:12", lt, 2.2, 7.6)


# ═══ 2. ROUTE 12 (also the aerial in SOLD) ═══════════════════════════════
class Route12(Shot):
    aerial = False

    def setup(self):
        self.r = C.renderer((38, 32, 30), 6, 95, C.light((0.35, 0.8, -0.45), 0.36, 0.52, tint=(1.05, 0.86, 0.68)))
        r = self.r
        r.bake(P.road())
        r.bake(P.burnt_van(), m=rot_y(24), t=(1.4, 0, 26))
        r.bake(P.burnt_van(), m=rot_y(-70), t=(-2.6, 0, 33))
        self.lamps = []
        for x, z, flip in ((-5.2, 15, 1), (5.2, 36, -1), (-5.2, 58, 1)):
            m, head = P.streetlamp()
            mm = rot_y(0 if flip > 0 else 180)
            r.bake(m, m=mm, t=(x, 0, z))
            hp = m_apply(mm, head)
            self.lamps.append((x + hp[0], hp[1], z + hp[2]))
            r.bake(disc_xz(x + hp[0], z + hp[2], 4.2, 0.012, (64, 44, 26), n=12, layer=0))
        for x, z in ((-9, 50), (11, 64), (-12, 80), (9, 20)):
            r.bake(box(0.5, 3.5, 0.5, (30, 26, 22), center=(x, 1.75, z)))
            r.bake(box(2.6, 2.2, 2.6, (28, 34, 26), center=(x, 4.2, z)))
        self.fires = [(1.0, 2.3, 26.5), (-2.4, 2.1, 33.2)]
        self.sky = C.gradient((10, 10, 12), (50, 40, 34))
        self.rain = Rain(n=520, seed=11, slant=0.12, speed=820)
        self.bir = hum("biribel", rifle="rifle")
        rng = random.Random(3)
        self.smoke = [(rng.uniform(-1, 1), rng.uniform(0, 1), rng.uniform(0.8, 1.4)) for _ in range(16)]

    def _dyn_common(self, r, lt):
        for i, f in enumerate(self.fires):
            fl = 0.5 + 0.5 * math.sin(lt * 13 + i * 2) * math.sin(lt * 5.1 + i)
            r.add_sprite(f, fire_sprite(fl, 0.32, i), layer=2, bias=-1.5)
            r.add_sprite(f, glow_sprite(2.2 if not self.aerial else 4.5, (90, 40, 10)), layer=2, bias=-1.5)
        for k, (ox, ph, sp) in enumerate(self.smoke):
            f = self.fires[k % 2]
            age = (lt * 0.12 * sp + ph) % 1.0
            p = (f[0] + ox + age * 3.0, f[1] + age * 9.0, f[2] + age * 1.5)
            r.add_sprite(p, smoke_sprite(age, (30, 28, 28), 0.8, 3.2, 120), layer=2)

    def render(self, lt, T, frame):
        r = self.r
        if self.aerial:
            return self._aerial(lt, frame)
        walk_t = min(lt, 7.8)
        bz = 25.0 - walk_t * 1.45
        bx = -0.6 + 0.25 * math.sin(walk_t * 0.4)
        phase = walk_t * 1.45 / 0.72 * math.pi
        stopk = seg(lt, 7.4, 8.2)
        pose = blend(pose_walk(phase, "ready"), POSES["ready"], stopk)
        pose["head_p"] = lerp(8, -6, seg(lt, 7.8, 9.0))
        if lt < 6.02:
            k = lt / 6.02
            cpos = (lerp(-2.0, -1.6, k), lerp(0.55, 0.75, k), bz - lerp(7.5, 5.0, smooth(k)))
            ctgt = (bx * 0.7, lerp(1.6, 1.3, k), bz + 2)
            fov = lerp(30, 28, k)
        else:
            k = (lt - 6.02) / 3.36
            cpos = (bx + 0.75 - 0.2 * k, 1.66, bz - lerp(2.6, 1.9, smooth(k)))
            ctgt = (bx, 1.58, bz)
            fov = 30
        sx, sy = shake(lt, 0.012)
        r.set_camera((cpos[0] + sx, cpos[1] + sy, cpos[2]), ctgt, fov)

        def dyn(r):
            self._dyn_common(r, lt)
            r.add_humanoid(self.bir, pose, (bx, 0, bz), 180.0 + 4 * math.sin(lt * 0.5))
        surf = self.frame3d(self.sky, dyn)
        for p in self.lamps:
            glow_at(r, surf, p, 3.0, (150, 96, 40))
        self.rain.draw(surf, lt, 0.9)
        return surf

    def _aerial(self, lt, frame):
        r = self.r
        k = lt / 3.73
        a = math.radians(lerp(-30, 6, smooth(k)))
        rad = lerp(26, 20, k)
        cpos = (1.4 + math.sin(a) * rad, lerp(16, 11, smooth(k)), 26 - math.cos(a) * rad)
        r.set_camera(cpos, (0.0, 0, 30), 50)
        surf = self.frame3d(self.sky, lambda r: self._dyn_common(r, lt + 9))
        for p in self.lamps:
            glow_at(r, surf, p, 3.0, (150, 96, 40))
        self.rain.draw(surf, lt, 0.7)
        return surf


class Route12Aerial(Route12):
    aerial = True


# ═══ 3. VASILE: the file + the cigarette ═════════════════════════════════
def text_page(lines, wpx=420, hpx=560, bg=None, ink=(40, 36, 32), size=26, stamp=None, redact=(),
              stamp_size=96, top=30, gap=1.5):
    s = pygame.Surface((wpx, hpx), pygame.SRCALPHA)
    if bg:
        s.fill(bg)
    f = C.font("mono", size)
    y = top
    for i, ln in enumerate(lines):
        img = f.render(ln, True, ink)
        s.blit(img, (28, y))
        if i in redact:
            pygame.draw.rect(s, (12, 12, 14), (28 + img.get_width() * 0.42, y + 4, img.get_width() * 0.5, size))
        y += int(size * gap)
    if stamp:
        fs = C.font("oswald", stamp_size)
        st = fs.render(stamp, True, (176, 34, 30))
        box_ = pygame.Surface((st.get_width() + 30, st.get_height() + 6), pygame.SRCALPHA)
        pygame.draw.rect(box_, (176, 34, 30), box_.get_rect(), 6)
        box_.blit(st, (15, 3))
        box_ = pygame.transform.rotate(box_, 14)
        s.blit(box_, (wpx - box_.get_width() - 18, max(y + 4, hpx - box_.get_height() - 18)))
    return s


def flat_sprite(img, width_m):
    cache = {}

    def draw(surf, sx, sy, scale, z):
        wpx = int(width_m * scale)
        if wpx < 4 or wpx > 2000:
            return
        hpx = int(img.get_height() * wpx / img.get_width())
        k = (wpx, hpx)
        g = cache.get(k)
        if g is None:
            g = pygame.transform.smoothscale(img, k)
            cache.clear()
            cache[k] = g
        surf.blit(g, (int(sx - wpx / 2), int(sy - hpx / 2)))
    return draw


class VasileFile(Shot):
    def setup(self):
        self.r = C.renderer((14, 12, 10), 2, 14, C.light((-0.4, 0.85, -0.3), 0.30, 0.75, tint=(1.1, 0.95, 0.75)))
        r = self.r
        r.bake(box(1.6, 0.06, 1.0, (64, 44, 30), center=(0, 0.72, 0)))
        r.bake(box(0.25, 0.012, 0.33, (176, 150, 98), center=(0.02, 0.756, 0.0)))
        r.bake(box(0.24, 0.006, 0.32, (214, 206, 186), center=(0.025, 0.763, 0.0)))
        r.bake(box(0.1, 0.02, 0.07, (120, 116, 110), center=(-0.32, 0.76, 0.18)))   # ashtray
        r.bake(box(0.012, 0.012, 0.06, (230, 226, 214), center=(-0.32, 0.778, 0.18)))
        r.bake(box(0.06, 0.24, 0.06, (40, 40, 42), center=(0.45, 0.87, 0.3)))
        r.bake(box(0.16, 0.06, 0.16, (40, 40, 42), center=(0.42, 1.0, 0.24)))
        r.bake(box(0.12, 0.01, 0.12, (255, 226, 160), center=(0.42, 0.968, 0.24), emissive=True))
        self.sky = C.gradient((8, 7, 6), (16, 13, 10))
        page = text_page(["KRAP // OPERATIONS", "FILE 12-0412", "", "OPERATOR:  BIRIBEL", "UNIT:      KRAP-7",
                          "ASSIGNMENT: ROUTE 12", "STATUS:    ACTIVE", "", "HANDLER:   ████████",
                          "COPY 2 OF 3"], stamp="ROUTE 12", size=22, stamp_size=60, top=48, gap=1.42)
        self.page_img = page
        cover = text_page(["", "", "   CONFIDENTIAL", "", "   KRAP"], bg=(176, 150, 98), ink=(110, 70, 40), size=34)
        self.cover_img = cover

    def render(self, lt, T, frame):
        r = self.r
        k = lt / 4.64
        r.set_camera((lerp(0.16, 0.1, k), lerp(1.7, 1.58, smooth(k)), lerp(-0.34, -0.26, k)),
                     (0.03, 0.76, 0.01), 50)
        flip = seg(lt, 1.6, 2.6)
        hand_x = keys([(0, 0.5), (1.2, 0.18), (1.6, 0.12), (2.6, -0.2), (3.6, -0.5)], lt)
        hand_z = keys([(0, -0.25), (1.6, -0.08), (2.6, 0.0), (3.6, -0.2)], lt)

        def dyn(r):
            if flip < 1:
                ang = 180 * smooth(flip)
                m = rot_z(ang)
                v, f = P.dyn_faces(box(0.25, 0.008, 0.33, (176, 150, 98), center=(0.125, 0, 0)), m, (-0.105, 0.772, 0.0))
                r.add_dynamic(v, f)
                if flip < 0.35:
                    q = C.quad_on(r, (0.02, 0.777, 0.0), 0.12, 0.16)
                    if q:
                        r.add_sprite((0.02, 0.777, 0.0), C.warp_sprite(self.cover_img, q), layer=3, bias=0.05)
            else:
                q = C.quad_on(r, (0.025, 0.767, 0.0), 0.118, 0.158)
                if q:
                    r.add_sprite((0.025, 0.767, 0.0), C.warp_sprite(self.page_img, q), layer=3, bias=0.05)
            v, f = P.dyn_faces(P.merge(box(0.1, 0.05, 0.22, (18, 18, 20), center=(0, 0, -0.06)),
                                       box(0.12, 0.07, 0.2, (24, 26, 30), center=(0, 0.01, -0.26))),
                               rot_y(-20), (hand_x, 0.8, hand_z), layer=4)
            r.add_dynamic(v, f)
        surf = self.frame3d(self.sky, dyn)
        glow_at(r, surf, (0.42, 0.95, 0.24), 0.5, (110, 86, 50))
        return surf


class VasileSmoke(Shot):
    def setup(self):
        self.lt_ = C.light((0.85, 0.35, -0.35), 0.16, 0.95, sky=0.02, tint=(0.8, 0.9, 1.1))
        self.r = C.renderer((10, 12, 16), 3, 18, self.lt_)
        r = self.r
        r.bake(box(8, 4, 0.2, (30, 32, 38), center=(0, 2, 2.5)))
        for i in range(9):
            r.bake(box(1.6, 0.06, 0.02, (60, 80, 110), center=(1.6, 1.0 + i * 0.16, 2.38), emissive=True))
        r.bake(box(1.8, 0.08, 0.9, (50, 36, 26), center=(0, 0.74, -0.6)))
        self.sky = C.gradient((8, 9, 12), (14, 15, 20))
        self.vas = hum("vasile")

    def render(self, lt, T, frame):
        r = self.r
        yaw = 196.0
        flame = seg(lt, 0.5, 0.58) * (1 - seg(lt, 1.75, 1.85))
        pose = dict(POSES["stand"])
        pose.update(head_p=lerp(6, 12, seg(lt, 0.3, 0.6)) - 8 * seg(lt, 2.0, 2.8), head_y=-6)
        _, j0, _ = self.vas.pose_world(pose, (0, 0, 0), yaw, rifle_on=False)
        tip = head_point(j0, yaw, (0.105, -0.09, 0.11))         # cigarette tip (rig: cig box)
        r_rest, l_rest = j0["rhand"], j0["lhand"]
        r_lit = head_point(j0, yaw, (0.125, -0.17, 0.11))
        l_cup = head_point(j0, yaw, (0.0, -0.13, 0.2))
        r_low = head_point(j0, yaw, (0.12, -0.42, 0.22))
        up = smooth(seg(lt, 0.0, 0.5))
        r_t = vlerp(r_rest, r_lit, up)
        r_t = vlerp(r_t, r_low, smooth(seg(lt, 2.0, 2.7)))
        pose = ik_arm(self.vas, pose, (0, 0, 0), yaw, "r", r_t, roll=(-30, 70))
        self.lt_.ambient = 0.16 + 0.22 * flame * (0.85 + 0.15 * math.sin(lt * 40))
        self.lt_.tint = vlerp((0.8, 0.9, 1.1), (1.25, 0.95, 0.65), flame)
        k = lt / 2.94
        hx, hy, hz = j0["head"]
        r.set_camera((hx - 0.75 + 0.1 * k, hy - 0.02, hz - lerp(2.9, 2.5, smooth(k))), (hx + 0.02, hy - 0.2, hz), 28)
        lighter_on = lt < 2.75

        def dyn(r):
            j = r.add_humanoid(self.vas, pose, (0, 0, 0), yaw, rifle_on=False)
            if lighter_on:
                h = j["rhand"]
                v, f = P.dyn_faces(P.merge(box(0.03, 0.05, 0.016, (150, 150, 156), center=(0, 0.035, 0)),
                                           box(0.022, 0.012, 0.014, (90, 90, 96), center=(0, 0.066, 0))),
                                   rot_y(yaw), h)
                r.add_dynamic(v, f)
                if flame > 0:
                    fp = (h[0], h[1] + 0.074, h[2])
                    fl = 0.8 + 0.2 * math.sin(lt * 37)
                    r.add_sprite(fp, fire_sprite(fl, 0.012 * flame, 3), layer=2, bias=-0.04)
                    r.add_sprite(fp, glow_sprite(0.35 * flame, (255, 150, 60)), layer=2, bias=-0.04)
            if lt > 0.9:
                ember = 0.6 + 0.4 * math.sin(lt * 3.1)
                r.add_sprite(tip, glow_sprite(0.06 + 0.04 * ember, (255, 90, 30)), layer=2, bias=-0.02)
            for i in range(5):                                  # exhale
                age = (lt - 2.2 - i * 0.08) / 1.2
                if 0 < age < 1:
                    mp = head_point(j0, yaw, (0.02 + age * 0.1, -0.08 + age * 0.15, 0.14 + age * 0.35))
                    r.add_sprite(mp, smoke_sprite(age, (120, 124, 132), 0.02, 0.12, 40), layer=2, bias=-0.02)
        return self.frame3d(self.sky, dyn)


# ═══ 4. MARTIAL LAW ═══════════════════════════════════════════════════════
class MartialLaw(Shot):
    def setup(self):
        self.r = C.renderer((22, 26, 36), 12, 160, C.light((-0.3, 0.75, -0.55), 0.34, 0.5, tint=(0.8, 0.88, 1.08)))
        r = self.r
        r.bake(quad_xz(-9, -60, 9, 200, 0.0, (30, 31, 34), seg=6,
                       colfn=lambda i, j: (30, 31, 34) if (i + j) % 3 else (36, 37, 40)))
        r.bake(quad_xz(-14, -60, -9, 200, 0.12, (52, 52, 54), seg=8))
        r.bake(quad_xz(9, -60, 14, 200, 0.12, (52, 52, 54), seg=8))
        rng = random.Random(8)
        z = -50
        while z < 190:
            d = rng.uniform(14, 22)
            for side in (-1, 1):
                w, h = rng.uniform(12, 16), rng.uniform(22, 42)
                blk = P.apartment_block(w, h, d, rng.randrange(999), facing=-side, lit=0.3)
                r.bake(blk, t=(side * (14 + w / 2), 0, z + d / 2))
            z += d + rng.uniform(4, 9)
        self.tank_m, self.tank_lights = P.tank()
        r.bake(P.barrier(6), t=(-3, 0, -6))
        r.bake(P.sandbags(5), t=(-8.5, 0, -7))
        r.bake(P.sandbags(4), t=(5.5, 0, -7))
        r.bake(box(1.8, 2.4, 1.8, (60, 62, 58), center=(7.5, 1.2, -3)))
        r.bake(box(0.16, 5, 0.16, (60, 60, 60), center=(-7, 2.5, -9)))
        self.flood = (-7, 5.0, -9)
        self.guards = [guard(i) for i in range(3)]
        self.sky = C.gradient((6, 8, 14), (30, 36, 50))
        C.stars(self.sky, 40, 4, H * 0.3)
        self.searchers = [(-20, 44, 60), (22, 40, 110)]

    def _tank_at(self, r, z, x=0.0):
        v, f = P.dyn_faces(self.tank_m, rot_y(180), (x, 0, z))
        r.add_dynamic(v, f)
        return [(x - lx, ly, z - lz) for lx, ly, lz in self.tank_lights]

    def render(self, lt, T, frame):
        r = self.r
        # column rolls in and halts well short of the camera / checkpoint
        lead = 24.0 - 12.0 * ease_out(clamp(lt / 3.6))
        tanks = [(0.0, lead), (-0.5, lead + 13.0), (0.5, lead + 26.0)]
        if lt < 3.46:
            sx, sy = shake(lt, 0.03 + 0.05 * seg(lt, 1.0, 3.4), 31)
            r.set_camera((1.4 + sx, 0.35 + sy, -4.0 + lt * 0.2), (0.0, 2.2 + lt * 0.3, 14), 52)
        elif lt < 6.78:
            k = (lt - 3.46) / 3.32
            r.set_camera((lerp(13, 9, k), lerp(30, 27, k), lerp(-40, -36, k)), (0, 8, 40), 50)
        else:
            k = (lt - 6.78) / 3.26
            r.set_camera((lerp(-1.0, 2.6, smooth(k)), 1.65, -12.5), (lerp(-2.5, 0.5, smooth(k)), 1.5, -4), 40)
        heads = []

        def dyn(r):
            for x, z in tanks:
                for hp in self._tank_at(r, z, x):
                    r.add_sprite(hp, glow_sprite(1.2, (120, 116, 96)), layer=2, bias=-0.1)
            for i, gd in enumerate(self.guards):
                look = -55 * smooth(seg(lt, 8.28, 8.9)) if i == 1 else 0
                pose = dict(POSES["ready"])
                pose["head_y"] = look
                pose["twist"] = look * 0.3
                r.add_humanoid(gd, pose, ((-4.2, -1.2, 2.6)[i], 0, (-4.5, -4.0, -4.8)[i]), (190, 160, 205)[i])
        surf = self.frame3d(self.sky, dyn)
        for i, s in enumerate(self.searchers):
            a = lt * 0.5 + i * 2.2
            tgt = (s[0] * -0.6 + math.sin(a) * 14, 18 + 8 * math.sin(a * 1.3), s[2] + 30 + math.cos(a) * 20)
            beam(r, surf, s, tgt, 0.4, 3.2, (26, 28, 26))
            glow_at(r, surf, tgt, 4, (60, 60, 52))
            glow_at(r, surf, s, 2, (140, 140, 120))
        glow_at(r, surf, self.flood, 2.4, (160, 150, 120))
        return surf

    def overlay(self, canvas, lt, T):
        location_tag(canvas, "ACARISTAN CAPITAL  //  CURFEW 21:00", lt, 3.7, 6.4)


# ═══ 5. TRAIN + NOTEBOOK ══════════════════════════════════════════════════
class Train(Shot):
    """Night train booth: Volkov (window seat, facing camera) slides the
    notebook across the table; insert of the open ledger."""
    VZ = 0.78          # Volkov pelvis z (faces -z)

    def setup(self):
        self.lt_ = C.light((0.15, 0.95, -0.35), 0.5, 0.62, tint=(1.0, 1.0, 0.94))
        self.r = C.renderer((12, 15, 17), 4, 22, self.lt_)
        r = self.r
        r.bake(P.train_car(seats=False))
        seat, tab = (64, 86, 74), (78, 66, 54)
        # booth: table against the right window, benches either side
        r.bake(box(0.75, 0.05, 0.62, tab, center=(1.05, 0.72, 0.0)))
        r.bake(box(0.08, 0.7, 0.08, (48, 48, 50), center=(0.9, 0.36, 0.0)))
        for zc, back in ((self.VZ + 0.08, self.VZ + 0.38),):
            r.bake(box(1.0, 0.5, 0.5, seat, center=(0.95, 0.25, zc)))
            r.bake(box(1.0, 0.9, 0.12, seat, center=(0.95, 0.88, back)))
            r.bake(box(1.0, 0.1, 0.16, (80, 104, 90), center=(0.95, 1.36, back)))
        # opposite side booths (background)
        for zc in (-3.0, 3.0, 5.0):
            r.bake(box(1.0, 0.42, 0.5, seat, center=(-0.95, 0.21, zc)))
            r.bake(box(1.0, 0.9, 0.12, seat, center=(-0.95, 0.88, zc + 0.3)))
        r.bake(box(0.12, 0.05, 0.12, (255, 236, 190), center=(1.38, 1.95, 0.0), emissive=True))
        self.sky = C.gradient((4, 6, 8), (10, 12, 16))
        self.vol = hum("volkov")
        rng = random.Random(9)
        self.outside = [(rng.uniform(-60, 60), rng.uniform(0.4, 3.0), rng.choice((7.0, 12.0, 20.0)))
                        for _ in range(18)]
        L = ["14.III  R-12", "  ████  4.000.000", "02.IV   R-12", "  ████  1.200.000",
             "09.IV   KK-B", "  ████     80.000"]
        R = ["ROUTE 12", "  = SOLD ?", "", "21.IV   R-12", "  V. ████   ?", "27.IV   PG", "  ██████   ???"]
        self.pageL = text_page(L, wpx=400, hpx=560, size=30, top=50, gap=1.55, bg=(218, 210, 188))
        self.pageR = text_page(R, wpx=400, hpx=560, size=30, top=50, gap=1.55, ink=(110, 24, 20))
        self.half = P.merge(box(0.21, 0.012, 0.29, (20, 20, 22), center=(0.105, 0.006, 0)),
                            box(0.2, 0.01, 0.28, (218, 210, 188), center=(0.105, 0.016, 0)))
        self.leaf = box(0.205, 0.006, 0.285, (20, 20, 22), center=(0.1025, 0, 0))
        self.bhand = P.merge(box(0.09, 0.05, 0.11, (176, 136, 108), center=(0, 0, 0.0)),
                             box(0.1, 0.09, 0.22, (52, 64, 46), center=(0, 0.01, -0.16)))

    def render(self, lt, T, frame):
        r = self.r
        flick = 1.0 if (frame * 7919) % 23 else 0.55
        self.lt_.ambient = 0.5 * flick
        insert = lt >= 4.42
        slide = smooth(seg(lt, 0.9, 3.0))
        nb = (lerp(0.84, 0.98, slide), 0.745, lerp(0.26, -0.16, slide))
        pose = dict(SEATED)
        pose.update(lsh_p=40, lel=80, head_p=lerp(4, 14, slide), head_y=-6)
        vpos = (0.98, 0, self.VZ)
        _, j0, _ = self.vol.pose_world(pose, vpos, 180.0, rifle_on=False)
        on_book = (nb[0] - 0.02, nb[1] + 0.06, nb[2] + 0.06)          # palm on the cover
        reach = smooth(seg(lt, 0.3, 0.9)) * (1 - smooth(seg(lt, 3.1, 3.8)))
        pose = ik_arm(self.vol, pose, vpos, 180.0, "r", vlerp(j0["rhand"], on_book, reach))
        sx, sy = shake(lt, 0.004, 5)
        if not insert:
            k = lt / 4.42
            r.set_camera((lerp(0.42, 0.52, k) + sx, 1.62 + sy, lerp(-1.95, -1.7, smooth(k))),
                         (0.95, lerp(1.04, 0.98, k), 0.4), 54)
        else:
            k = (lt - 4.42) / 1.5
            r.set_camera((0.97 + sx, lerp(1.85, 1.7, smooth(k)), -0.62), (0.97, 0.74, -0.1), 40)
        ins = lt - 4.42
        flip = smooth(seg(ins, 0.15, 0.6))
        hinge = (0.99, 0.768, -0.15)

        def dyn(r):
            r.add_humanoid(self.vol, pose, vpos, 180.0, rifle_on=False)
            if not insert:
                v, f = P.dyn_faces(P.notebook(), rot_y(6 - 6 * slide), nb)
                r.add_dynamic(v, f)
            else:
                v, f = P.dyn_faces(self.half, None, (0.99, 0.745, -0.15))
                r.add_dynamic(v, f)
                ang = 180.0 * flip
                v, f = P.dyn_faces(self.leaf, rot_z(ang), hinge)
                r.add_dynamic(v, f)
                if flip > 0.5:
                    q = C.quad_on(r, (1.095, 0.763, -0.15), 0.1, 0.14)
                    if q:
                        r.add_sprite((1.095, 0.763, -0.15), C.warp_sprite(self.pageR, q), layer=3, bias=0.03)
                if flip >= 1.0:
                    q = C.quad_on(r, (0.885, 0.773, -0.15), 0.1, 0.14)
                    if q:
                        r.add_sprite((0.885, 0.773, -0.15), C.warp_sprite(self.pageL, q), layer=3, bias=0.03)
                # Biribel's hand (camera side) lifts the cover's edge over
                inn = smooth(seg(ins, 0.0, 0.15)) * (1 - smooth(seg(ins, 0.7, 1.0)))
                ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
                edge = (hinge[0] + 0.2 * ca, hinge[1] + 0.2 * sa + 0.03, hinge[2] - 0.1)
                hp = vlerp((1.22, 0.78, -0.32), edge, inn)
                v, f = P.dyn_faces(self.bhand, rot_y(-15), hp, layer=4)
                r.add_dynamic(v, f)
            for z0, yy, xx in self.outside:
                z = (z0 - lt * 42) % 120 - 60
                v, f = P.dyn_faces(box(0.3, 0.25, 0.9, (240, 200, 120), emissive=True), None, (xx, yy, z))
                r.add_dynamic(v, f)
        surf = self.frame3d(self.sky, dyn)
        if flick < 1:
            surf.fill((150, 150, 150), special_flags=pygame.BLEND_RGB_MULT)
        return surf


# ═══ 6. SOLD card ═════════════════════════════════════════════════════════
class Sold(Shot):
    grain = 0.6

    def setup(self):
        self.black = pygame.Surface((W, H))

    def render(self, lt, T, frame):
        self.black.fill((0, 0, 0))
        return self.black

    def overlay(self, canvas, lt, T):
        t = lt - 0.25
        if t < 0:
            return
        k = ease_out(t / 0.18)
        sc = lerp(1.9, 1.0, k)
        f = C.font("oswald", 230)
        img = f.render("SOLD", True, (196, 32, 28))
        bx = pygame.Surface((img.get_width() + 70, img.get_height() + 10), pygame.SRCALPHA)
        pygame.draw.rect(bx, (196, 32, 28), bx.get_rect(), 12)
        bx.blit(img, (35, 5))
        bx = pygame.transform.rotozoom(bx, -6, sc)
        if t > 0.18:
            bx.set_alpha(int(255 * (1 - 0.15 * seg(t, 0.2, 2.2))))
        jx, jy = shake(t, 10 * (1 - seg(t, 0.18, 0.5)) if t > 0.18 else 0, 50)
        canvas.blit(bx, (C.OUT_W // 2 - bx.get_width() // 2 + jx, C.OUT_H // 2 - bx.get_height() // 2 + jy))


# ═══ 7. HANGAR / UCILEV ═══════════════════════════════════════════════════
class Hangar(Shot):
    def setup(self):
        self.r = C.renderer((18, 20, 24), 10, 70, C.light((0.2, 0.9, -0.3), 0.34, 0.62, tint=(0.92, 0.98, 1.06)))
        r = self.r
        r.bake(P.hangar())
        r.bake(P.gunship_body(), m=rot_y(180), t=(0, 0, 8))
        self.ship = (0, 0, 8)
        r.bake(box(1.2, 1.0, 0.8, (40, 44, 40), center=(-5, 0.5, 4)))
        r.bake(box(1.2, 1.0, 0.8, (40, 44, 40), center=(-5, 1.5, 4.2)))
        self.sky = C.gradient((10, 11, 14), (22, 24, 28))
        self.uci = hum("ucilev")
        self.beacons = [(0, 3.15, 8.2), (0, 2.2, 13.0), (-21.5, 8, 0), (21.5, 8, 0)]

    def render(self, lt, T, frame):
        r = self.r
        if lt < 4.17:
            wx = lerp(-5.5, 1.4, lt / 4.17)
            pose = pose_stroll(lt * 1.65 / 0.7 * math.pi)
            yaw, hy = 90.0, 0.0
        else:
            wx = 1.4
            stop = smooth(seg(lt, 4.17, 4.5))
            pose = blend(pose_stroll(4.17 * 1.65 / 0.7 * math.pi), POSES["stand"], stop)
            yaw = 90.0
            hy = lerp(0, 52, smooth(seg(lt, 4.45, 5.3)))
            pose["head_y"] = hy
            pose["twist"] = hy * 0.15
        pos = (wx, 0, -3.2)
        if lt < 4.17:
            r.set_camera((lerp(-3.4, -1.2, lt / 4.17), 1.45, -9.5), (wx * 0.8, 1.6, -2.0), 46)
        elif lt < 5.73:
            _, j, _ = self.uci.pose_world(pose, pos, yaw)
            hx, hy_, hz = j["head"]
            k = (lt - 4.17) / 1.56
            r.set_camera((hx + 0.8, hy_ + 0.12, hz - lerp(2.7, 2.4, k)), (hx + 0.1, hy_ + 0.06, hz), 30)
        else:
            k = (lt - 5.73) / 2.27
            r.set_camera((lerp(7.5, 6.5, k), lerp(1.4, 1.8, k), lerp(-5.5, -4.5, k)), (0.5, 2.0, 8.5), 50)
        spin = 0.0
        if lt > 5.0:
            u = lt - 5.0
            spin = 40 * u + 260 * u * u
        blink = int(lt * 2.4) % 2 == 0

        def dyn(r):
            r.add_humanoid(self.uci, pose, pos, yaw, rifle_on=False)
            v, f = P.rotor_faces((0, 3.05, 8.2), spin, radius=6.2)
            r.add_dynamic(v, f)
            v, f = P.rotor_faces((0.32, 2.9, 15.3), spin * 2.4, radius=0.9, n=2)
            r.add_dynamic(v, [(i, c, l, d, n, e) for i, c, l, d, n, e in f])
        surf = self.frame3d(self.sky, dyn)
        if blink:
            for b in self.beacons:
                glow_at(r, surf, b, 1.4, (180, 30, 24))
        for x in range(-16, 18, 8):
            glow_at(r, surf, (x, 12.9, 4), 3.0, (60, 60, 56))
        return surf


# ═══ 8. MONTAGE ═══════════════════════════════════════════════════════════
class Alley(Shot):
    def setup(self):
        self.r = C.renderer((20, 22, 28), 6, 60, C.light((0.4, 0.8, 0.3), 0.32, 0.55, tint=(0.85, 0.95, 1.1)))
        r = self.r
        r.bake(quad_xz(-3, -20, 3, 80, 0.0, (30, 32, 36), seg=3,
                       colfn=lambda i, j: (30, 32, 36) if (i + j) % 2 else (40, 42, 48)))
        for side in (-1, 1):
            r.bake(P.apartment_block(4, 18, 100, 3 + side, facing=-side, lit=0.25), t=(side * 5, 0, 30))
        m, head = P.streetlamp(5)
        r.bake(m, t=(-2.6, 0, 12))
        self.lamp = (-1.1, 4.7, 12)
        self.sky = C.gradient((8, 9, 14), (24, 28, 36))
        self.maru = hum("maru")
        self.rain = Rain(n=420, seed=21, slant=0.25, speed=900)

    def render(self, lt, T, frame):
        r = self.r
        z = 4 + lt * 5.2
        pose = pose_run(lt * 11.0)
        pose.update(lsh_p=60, lel=90)
        r.set_camera((2.2, 1.1, z - 1.6), (0, 1.1, z + 1.5), 52)

        def dyn(r):
            j = r.add_humanoid(self.maru, pose, (-0.4, 0, z), 0.0, rifle_on=False)
            h = j["lhand"]
            v, f = P.dyn_faces(box(0.24, 0.32, 0.02, (196, 168, 110)), rot_y(-10), (h[0] + 0.05, h[1] + 0.05, h[2] + 0.04))
            r.add_dynamic(v, f)
        surf = self.frame3d(self.sky, dyn)
        glow_at(r, surf, self.lamp, 3.0, (120, 110, 90))
        self.rain.draw(surf, lt, 1.0)
        return surf


class Mansion(Shot):
    """A (0..1.0): Biribel stacked beside the mansion's side door, charge
    blinking -> breach at 0.35 (flash, doors gone, debris + smoke, glowing
    doorway). B (1.0..2.4): inside the foyer over his shoulder - he fires,
    two guards return fire and drop."""
    IX = 200.0          # interior set lives at x+200

    def setup(self):
        self.lt_out = C.light((-0.3, 0.7, -0.6), 0.30, 0.6, tint=(0.9, 0.92, 1.05))
        self.lt_in = C.light((0.2, 0.9, -0.3), 0.34, 0.55, tint=(1.12, 0.96, 0.78))
        self.r = C.renderer((16, 16, 22), 8, 80, self.lt_out)
        r = self.r
        r.bake(P.mansion_facade(), t=(0, 0, 14))
        r.bake(quad_xz(-30, -20, 30, 14, 0.0, (52, 50, 46), seg=4,
                       colfn=lambda i, j: (52, 50, 46) if (i + j) % 2 else (46, 44, 42)))
        r.bake(box(1.5, 1.0, 1.5, (60, 70, 50), center=(-6, 0.5, 5)))
        r.bake(box(1.5, 1.0, 1.5, (60, 70, 50), center=(6, 0.5, 5)))
        r.bake(box(2.8, 3.5, 0.12, (110, 100, 86), center=(0, 2.25, 12.9)))   # door frame
        # interior foyer
        X = self.IX
        r.bake(quad_xz(X - 7, -3, X + 7, 14, 0.0, (150, 140, 120), seg=8,
                       colfn=lambda i, j: (150, 140, 120) if (i + j) % 2 else (60, 52, 46)))
        r.bake(box(14, 6, 0.4, (96, 60, 46), center=(X, 3, 14)))
        for sx in (-1, 1):
            r.bake(box(0.4, 6, 17, (90, 56, 44), center=(X + sx * 7, 3, 5.5)))
            r.bake(box(0.6, 6, 0.6, (170, 160, 140), center=(X + sx * 3.2, 3, 6.5)))
            for z in (3.0, 9.0):
                r.bake(box(0.2, 0.3, 0.2, (255, 220, 150), center=(X + sx * 6.8, 2.6, z), emissive=True))
        for k in range(8):   # staircase
            r.bake(box(4, 0.25 * (k + 1), 0.45, (120, 70, 56), center=(X + 0.5, 0.125 * (k + 1), 11 + k * 0.42)))
        r.bake(box(14, 0.3, 17, (60, 40, 32), center=(X, 6.1, 5.5)))
        r.bake(box(1.2, 0.5, 1.2, (255, 226, 160), center=(X, 5.2, 6.0), emissive=True))   # chandelier
        self.sconces = [(X + sx * 6.7, 2.6, z) for sx in (-1, 1) for z in (3.0, 9.0)]
        self.sky = C.gradient((6, 6, 10), (20, 20, 30))
        self.sky_in = C.gradient((40, 28, 20), (60, 44, 32))
        self.door = P.door_leaf()
        self.bir = hum("biribel", rifle="rifle")
        self.g = [guard(0), guard(1)]
        rng = random.Random(77)
        self.debris = [(rng.uniform(-1.2, 1.2), rng.uniform(0.3, 2.8), rng.uniform(-1, 1), rng.uniform(2, 7),
                        rng.uniform(1, 4), rng.uniform(0.06, 0.2), rng.uniform(0, 360)) for _ in range(16)]

    def _exterior(self, lt, frame):
        r = self.r
        r.light = self.lt_out
        boom = lt - 0.35
        sx, sy = shake(lt, 0.0 if boom < 0 else 0.08 * max(0.0, 1 - boom * 1.8), 41)
        r.set_camera((-5.2 + lt * 0.3 + sx, 1.5 + sy, 5.0), (-0.2, 1.7, 12.8), 44)
        pose = dict(POSES["ready"])
        pose.update(spine=10, head_y=-35 if boom < 0 else -60)

        def dyn(r):
            r.add_humanoid(self.bir, pose, (-1.9, 0.5, 12.3), 90.0)
            if boom < 0:
                for sxd in (-0.6, 0.6):
                    v, f = P.dyn_faces(self.door, None, (sxd, 0.5, 12.85))
                    r.add_dynamic(v, f)
                v, f = P.dyn_faces(box(0.18, 0.12, 0.06, (40, 44, 36)), None, (0.0, 1.7, 12.74))
                r.add_dynamic(v, f)
                if int(lt * 8) % 2 == 0:
                    r.add_sprite((0.0, 1.72, 12.7), glow_sprite(0.12, (255, 40, 30)), layer=2, bias=-0.05)
            else:
                v, f = P.dyn_faces(box(2.4, 3.0, 0.05, (90, 60, 34), emissive=True), None, (0, 2.0, 12.93))
                r.add_dynamic(v, f)
                for (ox, oy, oz, sp, up, sz, ang) in self.debris:
                    t = boom
                    p = (ox + ox * sp * t * 0.6, oy + up * t - 4.9 * t * t, 12.8 - sp * t)
                    if p[1] > 0.5:
                        v, f = P.dyn_faces(box(sz, sz * 0.5, sz * 0.3, (60, 36, 24)), rot_y(ang + t * 400), p)
                        r.add_dynamic(v, f)
                for i in range(8):
                    age = clamp(boom * 0.9 + i * 0.04)
                    r.add_sprite((math.sin(i * 2.3) * 1.2, 1.2 + i * 0.25 + age * 1.5, 12.4 - age * 3),
                                 smoke_sprite(age, (90, 86, 80), 0.7, 2.6, 170), layer=2, bias=-0.1)
                fl = max(0.0, 1 - boom / 0.25)
                if fl > 0:
                    r.add_sprite((0, 1.8, 12.6), glow_sprite(6 * fl, (255, 220, 160)), layer=2, bias=-0.2)
                    r.add_sprite((0, 1.6, 12.6), fire_sprite(fl, 0.9 * fl, 5), layer=2, bias=-0.2)
        surf = self.frame3d(self.sky, dyn)
        if 0 <= boom < 0.08:
            surf.fill((180, 160, 130), special_flags=pygame.BLEND_RGB_ADD)
        return surf

    def _interior(self, lt, frame):
        r = self.r
        r.light = self.lt_in
        X = self.IX
        k = lt - 1.0
        sx, sy = shake(lt, 0.012, 43)
        bp = (X - 0.6, 0, lerp(-0.6, 0.2, smooth(k / 1.4)))
        r.set_camera((bp[0] + 0.95 + sx, 1.62 + sy, bp[2] - 1.6), (X + 0.1, 1.3, 9.0), 50)
        firing = 0.15 < k < 1.2
        shot = firing and int(k * 14) % 2 == 0
        pose = dict(POSES["aim"])
        if shot:
            pose.update(rifle_p=-4, spine=6)
        gpos = [(X - 1.4, 0, 8.2), (X + 2.0, 0, 9.4)]
        hits = [0.45, 0.85]
        flashes = []

        def dyn(r):
            j = r.add_humanoid(self.bir, pose, bp, 8.0)
            if shot:
                fn = muzzle_at(r, j["muzzle"], j["rhand"], 0.08, frame)
                if fn:
                    r.add_sprite(j["muzzle"], fn, layer=2, bias=-0.05)
                flashes.append(j["muzzle"])
            for gi, (gd, gp) in enumerate(zip(self.g, gpos)):
                hk = smooth(seg(k, hits[gi], hits[gi] + 0.35))
                dead = POSES["dead_back"] if gi == 0 else POSES["dead_side"]
                pz = blend(POSES["aim"], dead, hk)
                pos = (gp[0], gp[1], gp[2] + 0.6 * hk)
                jj = r.add_humanoid(gd, pz, pos, 188 + gi * 8)
                if k < hits[gi] and int(k * 11 + gi * 3) % 3 == 0:
                    fn = muzzle_at(r, jj["muzzle"], jj["rhand"], 0.09, frame + gi)
                    if fn:
                        r.add_sprite(jj["muzzle"], fn, layer=2, bias=-0.05)
                if hits[gi] - 0.03 < k < hits[gi] + 0.06:       # hit puff
                    r.add_sprite((gp[0], 1.4, gp[2] + 0.1), smoke_sprite(0.2, (150, 130, 120), 0.15, 0.6, 140), layer=2)
            for i in range(3):          # sparks on the pillar/wall near the camera
                if int(k * 9 + i) % 5 == 0 and k < 0.9:
                    r.add_sprite((X - 3.0 + i * 0.3, 1.6 + i * 0.3, 6.2), glow_sprite(0.15, (255, 200, 120)), layer=2)
            for p in self.sconces:
                r.add_sprite(p, glow_sprite(1.2, (90, 60, 30)), layer=2)
            r.add_sprite((X, 5.0, 6.0), glow_sprite(4.0, (70, 54, 30)), layer=2)
            for i in range(5):
                age = clamp(k * 0.6 + i * 0.12)
                r.add_sprite((X - 0.4 + i * 0.4, 2.2 + age, 1.5 + i), smoke_sprite(age, (110, 100, 90), 0.8, 2.0, 70), layer=2)
        surf = self.frame3d(self.sky_in, dyn)
        if shot:
            surf.fill((24, 16, 8), special_flags=pygame.BLEND_RGB_ADD)
        return surf

    def render(self, lt, T, frame):
        return self._exterior(lt, frame) if lt < 1.0 else self._interior(lt, frame)


class Rooftops(Shot):
    def setup(self):
        self.r = C.renderer((20, 22, 30), 20, 260, C.light((0.3, 0.6, -0.7), 0.3, 0.5, tint=(0.85, 0.9, 1.1)))
        r = self.r
        r.bake(P.skyline(5, z=60, lit=0.3, hmin=10, hmax=30))
        r.bake(P.skyline(6, z=140, lit=0.25))
        r.bake(box(30, 20, 20, (44, 44, 48), center=(0, 10, 0)))
        r.bake(box(2, 1.2, 1.2, (60, 60, 64), center=(-6, 20.6, 4)))
        self.sky = C.gradient((8, 9, 16), (34, 34, 46))
        rng = random.Random(9)
        self.tr = [(rng.uniform(-30, 30), rng.uniform(10, 34), rng.uniform(40, 90), rng.uniform(0, 1)) for _ in range(9)]

    def render(self, lt, T, frame):
        r = self.r
        r.set_camera((lerp(-8, -4, lt), 21.6, -6), (10, 22, 60), 52)
        surf = self.frame3d(self.sky)
        for i, (x, y, z, ph) in enumerate(self.tr):
            u = (lt * 1.6 + ph) % 1.0
            a = (x, y, z)
            b = (x * -0.3 + 6, 21, 6)
            p = vlerp(a, b, u)
            q = vlerp(a, b, max(0, u - 0.08))
            pa, pb = r.project(p), r.project(q)
            if pa and pb:
                pygame.draw.line(surf, (255, 190, 90), pa[:2], pb[:2], 2)
                glow(surf, pa[0], pa[1], 6, (120, 60, 20))
            if int(lt * 12 + i) % 4 == 0:
                glow_at(r, surf, a, 2.0, (200, 120, 50))
        return surf


class Cockpit(Shot):
    """Over Maru's shoulder: the city slides by far below the windscreen."""
    def setup(self):
        self.r = C.renderer((10, 12, 18), 40, 360, C.light((0.2, 0.9, 0.3), 0.36, 0.5, tint=(0.85, 0.95, 1.1)))
        r = self.r
        rng = random.Random(4)
        for _ in range(900):
            x, z = rng.uniform(-220, 220), rng.uniform(-50, 700)
            c = rng.choice([(255, 200, 110), (240, 220, 170), (170, 200, 230), (255, 170, 80)])
            sz = rng.choice((0.8, 1.2, 1.8))
            r.bake(box(sz, 0.2, sz, c, center=(x, -70, z), emissive=True))
        for k in range(-6, 7):        # avenues: lines of lamps
            for z in range(-50, 700, 6):
                r.bake(box(0.7, 0.2, 0.7, (255, 180, 90), center=(k * 32.0, -70, z), emissive=True))
        self.sky = C.gradient((6, 8, 14), (26, 30, 42))
        self.maru = hum("maru")
        self.cab = P.merge(box(1.9, 0.45, 0.6, (26, 28, 30), center=(0, 0.9, 1.05)),
                           *[box(0.2, 0.12, 0.02, c, center=(x, 1.02, 0.74), emissive=True)
                             for x, c in ((-0.55, (60, 200, 110)), (-0.25, (220, 150, 50)), (0.15, (60, 200, 110)), (0.5, (60, 150, 220)))],
                           box(0.08, 1.3, 0.08, (20, 20, 22), center=(-0.9, 1.75, 1.3)),
                           box(0.08, 1.3, 0.08, (20, 20, 22), center=(0.9, 1.75, 1.3)),
                           box(0.06, 1.0, 0.06, (20, 20, 22), center=(0.0, 1.65, 1.3)),
                           box(1.9, 0.1, 0.5, (20, 20, 22), center=(0, 2.4, 1.1)),
                           box(0.5, 0.06, 0.5, (30, 32, 34), center=(0.45, 0.35, 0.2)))

    def render(self, lt, T, frame):
        r = self.r
        off = lt * 26.0
        bank = 6 * math.sin(lt * 1.3)
        sx, sy = shake(lt, 0.01, 27)
        r.set_camera((-0.3 + sx, 1.85 + sy, -0.75 + off), (0.55, 0.2, 5.0 + off), 62, roll=bank)

        def dyn(r):
            pose = dict(SEATED)
            pose.update(lsh_p=58, lel=40, rsh_p=52, rel=50, head_y=-10 + 8 * math.sin(lt * 2), head_p=6)
            r.add_humanoid(self.maru, pose, (0.45, 0.38, 0.2 + off), 0.0, rifle_on=False)
            v, f = P.dyn_faces(self.cab, None, (0, 0, off))
            r.add_dynamic(v, f)
        surf = self.frame3d(self.sky, dyn)
        if int(lt * 9) % 2 == 0:
            p = r.project((-0.6, 1.02, 0.74 + off))
            if p:
                glow(surf, p[0], p[1], 14, (160, 100, 40))
        return surf


class Gunship(Shot):
    def setup(self):
        self.r = C.renderer((12, 14, 20), 20, 200, C.light((0.2, 0.6, -0.8), 0.3, 0.6, tint=(0.85, 0.9, 1.1)))
        r = self.r
        r.bake(P.skyline(11, z=90, lit=0.25))
        self.body = P.gunship_body()
        self.sky = C.gradient((6, 7, 12), (26, 28, 40))

    def render(self, lt, T, frame):
        r = self.r
        z = lerp(30, 13, ease_out(lt / 1.02))
        r.set_camera((0, 30, 0), (0, 31, 30), 50)
        nose = (0, 30.2, z - 3.5)

        def dyn(r):
            v, f = P.dyn_faces(self.body, rot_y(180), (0, 28.5, z))
            r.add_dynamic(v, f)
            v, f = P.rotor_faces((0, 31.55, z), lt * 1400, radius=6.2)
            r.add_dynamic(v, f)
        surf = self.frame3d(self.sky, dyn)
        mk = 0.5 + seg(lt, 0.0, 0.9)
        beam(r, surf, (0, 29.3, z - 3.2), (3.5, 24, 1.0), 0.2, 3.4, tuple(int(60 * mk) for _ in range(3)))
        glow_at(r, surf, (0, 29.3, z - 3.2), 2.5 * mk, (255, 255, 230))
        # missile streak
        u = seg(lt, 0.25, 0.75)
        if 0 < u < 1:
            a = (-1.6, 28.6, z)
            b = (-4, 29, -6)
            p, q = vlerp(a, b, u), vlerp(a, b, max(0, u - 0.25))
            pa, pb = r.project(p), r.project(q)
            if pa and pb:
                pygame.draw.line(surf, (255, 220, 160), pa[:2], pb[:2], 3)
                glow(surf, pa[0], pa[1], 18, (255, 140, 60))
        if lt > 0.85:
            surf.fill((int(255 * seg(lt, 0.85, 1.02)),) * 3, special_flags=pygame.BLEND_RGB_ADD)
        return surf


class Breath(Shot):
    """dip before the scopes: Biribel close, rain, he looks up."""
    def setup(self):
        self.r = C.renderer((14, 14, 18), 4, 40, C.light((-0.7, 0.4, -0.5), 0.18, 0.8, tint=(0.8, 0.88, 1.08)))
        self.sky = C.gradient((6, 6, 9), (16, 16, 22))
        self.bir = hum("biribel")
        self.rain = Rain(n=300, seed=31, slant=0.05, speed=500, col=(90, 96, 110))

    def render(self, lt, T, frame):
        r = self.r
        pose = dict(POSES["stand"])
        pose["head_p"] = lerp(22, 0, smooth(seg(lt, 0.4, 1.5)))
        _, j, _ = self.bir.pose_world(pose, (0, 0, 0), 180)
        hx, hy, hz = j["head"]
        r.set_camera((hx + 0.22, hy - 0.06, hz - lerp(1.45, 1.25, lt / 1.66)), (hx, hy - 0.1, hz), 30)
        surf = self.frame3d(self.sky, lambda r: r.add_humanoid(self.bir, pose, (0, 0, 0), 180, rifle_on=False))
        self.rain.draw(surf, lt, 0.8)
        return surf


# ═══ 9. SCOPES + SHOT ═════════════════════════════════════════════════════
class SniperRoof(Shot):
    @staticmethod
    def _pose():
        pose = dict(POSES["kneel"])
        pose.update({k: v for k, v in POSES["aim"].items() if k[0] in "lr" and k[1] in "se" or k in ("rifle_p", "head_p")})
        pose.update(spine=10, head_p=10, lkn=92, rkn=104, lhip_p=88, rhip_p=-8)
        return pose

    """Side profile: Biribel kneels at the parapet, sniper up, silhouetted
    against the city glow."""
    def setup(self):
        self.r = C.renderer((22, 22, 30), 8, 200, C.light((-0.5, 0.45, 0.75), 0.2, 0.9, tint=(0.95, 0.85, 0.9)))
        r = self.r
        r.bake(box(14, 1, 10, (44, 44, 48), center=(0, -0.5, 0)))
        r.bake(box(14, 0.85, 0.3, (58, 58, 62), center=(0, 0.425, 4.4)))
        r.bake(box(14, 0.08, 0.4, (70, 70, 74), center=(0, 0.89, 4.4)))
        r.bake(box(0.6, 1.2, 0.6, (50, 50, 54), center=(1.8, 0.6, 1.4)))     # vent block
        r.bake(box(0.1, 3.2, 0.1, (40, 40, 44), center=(1.6, 1.6, 1.4)))     # antenna
        r.bake(P.skyline(13, z=120, lit=0.4, hmin=10, hmax=40), t=(0, -26, 0))
        r.bake(P.skyline(17, z=0, lit=0.35, hmin=6, hmax=30), m=rot_y(90), t=(170, -24, 0))
        self.sky = C.gradient((5, 6, 10), (70, 56, 60), mid=(0.55, (18, 20, 30)))
        self.bir = hum("biribel", rifle="sniper")
        self.rain = Rain(n=380, seed=41, slant=0.08, speed=760, col=(100, 108, 124))

    def render(self, lt, T, frame):
        r = self.r
        pose = self._pose()
        pos = (0, 0, 3.55)
        k = smooth(lt / 2.69)
        r.set_camera((lerp(-5.2, -4.4, k), 1.05, lerp(3.2, 3.5, k)), (0.0, 1.05, 3.85), 32)
        surf = self.frame3d(self.sky, lambda r: r.add_humanoid(self.bir, pose, pos, 0))
        self.rain.draw(surf, lt, 0.9)
        return surf


class Scopes(Shot):
    """Two scope circles side by side: mansion window | Route 12 site."""
    grain = 0.8

    def setup(self):
        import engine3d
        S = 240
        self.S = S
        self.rL = engine3d.Renderer(S, S, fog=(18, 16, 20), fog_start=30, fog_end=200)
        self.rL.light = C.light((-0.3, 0.7, -0.6), 0.3, 0.6, tint=(0.9, 0.92, 1.05))
        self.rL.bake(P.mansion_facade(), t=(0, 0, 60))
        self.rL.bake(box(1.6, 2.6, 0.1, (236, 196, 128), center=(0, 9.5, 58.95), emissive=True))
        self.rL.bake(box(0.12, 2.6, 0.12, (60, 44, 30), center=(0, 9.5, 58.9)))
        self.rL.bake(box(1.6, 0.1, 0.12, (60, 44, 30), center=(0, 9.9, 58.9)))
        self.rR = engine3d.Renderer(S, S, fog=(40, 34, 30), fog_start=30, fog_end=220)
        self.rR.light = C.light((0.3, 0.7, -0.6), 0.36, 0.55, tint=(1.05, 0.88, 0.72))
        self.rR.bake(P.construction_site(), t=(0, 0, 80))
        self.rR.bake(quad_xz(-60, 40, 60, 140, 0.0, (40, 36, 32), seg=12))
        self.rR.bake(P.road(40, 140), m=rot_y(90), t=(0, 0, 70))
        self.skyL = C.gradient((6, 6, 10), (18, 18, 26), h=S, w=S)
        self.skyR = C.gradient((18, 14, 16), (60, 46, 36), h=S, w=S)
        self.fig = hum("president")
        self.fig2 = hum("vasile")
        self.out = pygame.Surface((W, H))
        self.mask = pygame.Surface((S, S), pygame.SRCALPHA)
        self.mask.fill((0, 0, 0, 255))
        pygame.draw.circle(self.mask, (0, 0, 0, 0), (S // 2, S // 2), S // 2 - 6)
        self.r = self.rL

    def _scope(self, r, sky, cam, tgt, fov, dyn):
        r.set_camera(cam, tgt, fov)
        r.surface.blit(sky, (0, 0))
        r.begin(); r.add_static(); dyn(r)
        r.flush(r.surface)
        s = r.surface.copy()
        S = self.S
        c = S // 2
        pygame.draw.line(s, (8, 8, 8), (0, c), (S, c), 1)
        pygame.draw.line(s, (8, 8, 8), (c, 0), (c, S), 1)
        for k in range(-4, 5):
            pygame.draw.line(s, (8, 8, 8), (c + k * 14, c - 3), (c + k * 14, c + 3))
            pygame.draw.line(s, (8, 8, 8), (c - 3, c + k * 14), (c + 3, c + k * 14))
        pygame.draw.circle(s, (180, 30, 26), (c, c), 2)
        s.blit(self.mask, (0, 0))
        pygame.draw.circle(s, (30, 30, 30), (c, c), c - 6, 3)
        return s

    def render(self, lt, T, frame):
        out = self.out
        out.fill((0, 0, 0))
        swL = (0.15 * math.sin(lt * 1.3), 0.1 * math.sin(lt * 1.7))
        swR = (0.15 * math.sin(lt * 1.1 + 1), 0.1 * math.sin(lt * 1.9 + 2))
        zoom = lerp(7.0, 5.2, smooth(lt / 3.4))

        def dl(r):
            r.add_humanoid(self.fig, POSES["stand"], (0.25, 8.8, 58.4), 180, rifle_on=False,
                           tint=((6, 5, 6), 1.0))
        sL = self._scope(self.rL, self.skyL, (0, 9.8, 0), (0.25 + swL[0], 10.0 + swL[1], 58.4), zoom, dl)

        def dr(r):
            r.add_humanoid(self.fig2, POSES["stand"], (-1.0, 0.4, 76), 200, rifle_on=False, tint=((8, 6, 6), 1.0))
        sR = self._scope(self.rR, self.skyR, (0, 2.0, 0), (-1.0 + swR[0], 1.4 + swR[1], 76), zoom, dr)
        a = int(255 * clamp(lt / 0.3))
        sL.set_alpha(a); sR.set_alpha(a)
        y = (H - self.S) // 2
        out.blit(sL, (W // 2 - self.S - 14, y))
        out.blit(sR, (W // 2 + 14, y))
        return out

    def release(self):
        for r in (getattr(self, "rL", None), getattr(self, "rR", None)):
            if r is not None and hasattr(r, "release"):
                r.release()
        self.r = None
        self.ready = False


class Trigger(SniperRoof):
    """71.05..74.29: tight on Biribel's eye at the scope, BANG at 0.42 s
    (white flash), then black silence until the logo."""
    BANG = 0.42

    def setup(self):
        super().setup()
        self.black = pygame.Surface((W, H))

    def render(self, lt, T, frame):
        if lt >= self.BANG:
            self.black.fill((0, 0, 0))
            if lt < self.BANG + 0.07:
                self.black.fill((255, 250, 236))
            return self.black
        r = self.r
        pose = self._pose()
        pos = (0, 0, 3.55)
        _, j, _ = self.bir.pose_world(pose, pos, 0)
        hx, hy, hz = j["head"]
        d = lerp(1.0, 0.85, lt / self.BANG)
        r.set_camera((-4.6 * d, 1.25, 3.6), (0.0, 1.15, 3.95), 16)
        surf = self.frame3d(self.sky, lambda r: r.add_humanoid(self.bir, pose, pos, 0))
        self.rain.draw(surf, lt + 70, 0.8)
        return surf


# ═══ 10. LOGO ═════════════════════════════════════════════════════════════
def spaced(fnt, txt, col, spacing):
    glyphs = [fnt.render(ch, True, col) for ch in txt]
    w = sum(g.get_width() for g in glyphs) + spacing * (len(glyphs) - 1)
    out = pygame.Surface((max(1, w), fnt.get_height()), pygame.SRCALPHA)
    x = 0
    for g in glyphs:
        out.blit(g, (x, 0))
        x += g.get_width() + spacing
    return out


class Logo(Shot):
    """End card: dark smoke + rising embers + low fire glow; the scope icon
    slams in on the music hit, the title resolves under it (metal gradient,
    one light sweep), tagline, COMING SOON, credit, fade."""
    letterbox = False
    grain = 0.5

    def setup(self):
        self.black = pygame.Surface((W, H))
        self.icon = pygame.image.load(C.os.path.join(C.ART, "trailer_icon.png")).convert_alpha()
        OW, OH = C.OUT_W, C.OUT_H
        # background plate
        bg = pygame.Surface((OW, OH))
        for y in range(OH):
            u = y / OH
            c = vlerp((8, 9, 12), (20, 14, 12), u ** 1.6)
            pygame.draw.line(bg, c, (0, y), (OW, y))
        g = pygame.Surface((OW, OH))
        g.fill((0, 0, 0))
        glow(g, OW // 2, OH + 120, 900, (70, 30, 10))
        glow(g, OW // 2, OH // 2 - 60, 700, (22, 18, 16))
        bg.blit(g, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        self.bg = bg
        # vignette
        sm = pygame.Surface((96, 54), pygame.SRCALPHA)
        for yy in range(54):
            for xx in range(96):
                dx, dy = (xx - 47.5) / 48, (yy - 26.5) / 27
                d = min(1.0, math.hypot(dx, dy))
                sm.set_at((xx, yy), (0, 0, 0, int(215 * clamp((d - 0.45) / 0.55) ** 1.8)))
        self.vig = pygame.transform.smoothscale(sm, (OW, OH))
        rng = random.Random(74)
        self.embers = [(rng.uniform(0, OW), rng.uniform(40, 160), rng.uniform(0, 1), rng.uniform(1.5, 4.0),
                        rng.uniform(0, 6.28)) for _ in range(90)]
        self.smoke = [(rng.uniform(-200, OW + 200), rng.uniform(OH * 0.35, OH), rng.uniform(260, 520),
                       rng.uniform(8, 22), rng.uniform(0, 6.28)) for _ in range(14)]
        # title art
        title = C.font("oswald", 230).render("ACARISTAN", True, (255, 255, 255))
        grad = pygame.Surface(title.get_size(), pygame.SRCALPHA)
        th = title.get_height()
        for y in range(th):
            u = y / th
            c = vlerp((250, 247, 240), (150, 144, 136), clamp((u - 0.25) / 0.6))
            pygame.draw.line(grad, (*c, 255), (0, y), (title.get_width(), y))
        self.title = title.copy()
        self.title.blit(grad, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        sh = title.copy()
        sh.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
        sh.set_alpha(150)
        self.title_sh = sh
        self.title_white = title
        self.callof = spaced(C.font("oswald", 64), "CALL OF", INK, 26)
        self.tag = spaced(C.font("mono", 30), "SOME ORDERS YOU FINISH.", (176, 170, 160), 8)
        self.soon = spaced(C.font("monob", 40), "COMING SOON", C.ORANGE, 16)

    def render(self, lt, T, frame):
        self.black.fill((0, 0, 0))
        return self.black

    def _sweep(self, u):
        """Title copy lit by a diagonal band at position u (0..1)."""
        t = self.title_white
        w, h = t.get_size()
        band = pygame.Surface((w, h), pygame.SRCALPHA)
        band.fill((0, 0, 0, 0))
        x = int(lerp(-0.3, 1.3, u) * w)
        for k in range(-60, 61, 4):
            a = int(200 * (1 - abs(k) / 60.0))
            pygame.draw.line(band, (255, 236, 200, a), (x + k, 0), (x + k - h * 0.4, h), 5)
        out = t.copy()
        out.blit(band, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        flat = pygame.Surface((w, h))
        flat.fill((0, 0, 0))
        flat.blit(out, (0, 0))
        return flat

    def overlay(self, canvas, lt, T):
        OW, OH = C.OUT_W, C.OUT_H
        canvas.blit(self.bg, (0, 0))
        # smoke drift
        hz = pygame.Surface((OW, OH))
        hz.fill((0, 0, 0))
        for x0, y0, rad, sp, ph in self.smoke:
            x = x0 + lt * sp
            y = y0 - lt * sp * 0.4 + 20 * math.sin(lt * 0.5 + ph)
            glow(hz, x, y, rad, (16, 14, 14))
        canvas.blit(hz, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        # embers
        for x0, sp, ph, sz, wob in self.embers:
            y = OH + 40 - ((lt * sp + ph * (OH + 80)) % (OH + 80))
            x = x0 + 26 * math.sin(lt * 1.3 + wob) + lt * 12
            fl = 0.55 + 0.45 * math.sin(lt * 9 + wob * 3)
            life = clamp(y / OH)
            c = (int(255 * fl * life), int(120 * fl * life), int(30 * fl * life))
            glow(canvas, x, y, sz * 5, (c[0] // 3, c[1] // 3, c[2] // 3))
            pygame.draw.circle(canvas, c, (int(x), int(y)), max(1, int(sz * 0.6)))
        cx, cy = OW // 2, OH // 2
        # 1) icon slam (0..0.25), settles above the title
        k = ease_out(clamp(lt / 0.25))
        size = int(lerp(520, 170, k))
        ic = pygame.transform.smoothscale(self.icon, (size, size))
        if lt < 0.1:
            ic.set_alpha(int(255 * lt / 0.1))
        jx, jy = shake(lt, 16 * (1 - seg(lt, 0.15, 0.6)), 60)
        iy = cy - 285
        canvas.blit(ic, (cx - size // 2 + jx, iy - size // 2 + jy))
        if lt < 0.18:      # hit flash
            canvas.fill((int(90 * (1 - lt / 0.18)),) * 3, special_flags=pygame.BLEND_RGB_ADD)
        # 2) CALL OF with rules
        a1 = clamp((lt - 0.35) / 0.4)
        ty = cy - 90
        if a1 > 0:
            c = self.callof.copy()
            c.set_alpha(int(255 * a1))
            canvas.blit(c, (cx - c.get_width() // 2, ty - 50 - c.get_height() // 2 + int(14 * (1 - a1))))
            rl = int(150 * ease_out(seg(lt, 0.45, 1.0)))
            for sgn in (-1, 1):
                x_in = cx + sgn * (c.get_width() // 2 + 30)
                x_out = x_in + sgn * rl
                pygame.draw.line(canvas, C.ORANGE, (x_in, ty - 50), (x_out, ty - 50), 3)
        # 3) ACARISTAN
        a2 = clamp((lt - 0.55) / 0.5)
        if a2 > 0:
            tw, th = self.title.get_size()
            x = cx - tw // 2
            y = ty + 10
            sc = lerp(1.06, 1.0, ease_out(a2))
            t = self.title if sc == 1.0 else pygame.transform.smoothscale(self.title, (int(tw * sc), int(th * sc)))
            sh = self.title_sh if sc == 1.0 else pygame.transform.smoothscale(self.title_sh, (int(tw * sc), int(th * sc)))
            x = cx - t.get_width() // 2
            t = t.copy(); t.set_alpha(int(255 * a2))
            sh.set_alpha(int(150 * a2))
            canvas.blit(sh, (x + 6, y + 8))
            canvas.blit(t, (x, y))
            u = seg(lt, 1.2, 2.2)
            if 0 < u < 1:
                canvas.blit(self._sweep(u), (cx - tw // 2, y), special_flags=pygame.BLEND_RGB_ADD)
            ul = int(tw * 0.62 * ease_out(seg(lt, 0.8, 1.4)))
            pygame.draw.rect(canvas, C.ORANGE, (cx - ul // 2, y + int(th * 0.86), ul, 7))
        base = ty + 10 + int(self.title.get_height() * 0.86)
        # 4) tagline + coming soon + credit
        if lt > 2.1:
            t = self.tag.copy(); t.set_alpha(int(255 * clamp((lt - 2.1) / 0.6)))
            canvas.blit(t, (cx - t.get_width() // 2, base + 46))
        if lt > 2.9:
            a = clamp((lt - 2.9) / 0.5)
            t = self.soon.copy(); t.set_alpha(int(255 * a))
            canvas.blit(t, (cx - t.get_width() // 2, base + 120))
        if lt > 3.3:
            a = int(150 * clamp((lt - 3.3) / 0.6))
            C.text_center(canvas, "Music: \"Shell Ghost\" by Soundridemusic", C.font("mono", 20), (130, 128, 124),
                          OH - 48, a)
        canvas.blit(self.vig, (0, 0))
        if lt > 5.0:
            canvas.fill((int(255 * seg(lt, 5.0, 5.71)),) * 3, special_flags=pygame.BLEND_RGB_SUB)


INK = C.INK


# ═══ timeline ═════════════════════════════════════════════════════════════
def build_timeline(marks):
    m = marks
    hb, hu, hs = m["hit_biribel"], m["hit_ucilev"], m["hit_scopes"]
    sil0 = m["silence"][0]
    S = [
        (0.0, hb, Ocean),
        (hb, 18.24, Route12),
        (18.24, 22.88, VasileFile),
        (22.88, 25.82, VasileSmoke),
        (25.82, 35.86, MartialLaw),
        (35.86, 41.77, Train),
        (41.77, m["sold_start"], Route12Aerial),
        (m["sold_start"], hu - 0.15, Sold),
        (hu - 0.15, 56.0, Hangar),
        (56.0, 57.3, Alley),
        (57.3, 59.7, Mansion),
        (59.7, 60.8, Rooftops),
        (60.8, m["hits_act2"][2], Cockpit),
        (m["hits_act2"][2], m["dip"][0], Gunship),
        (m["dip"][0], hs, Breath),
        (hs, hs + 2.69, SniperRoof),
        (hs + 2.69, sil0, Scopes),
        (sil0, m["hit_logo"], Trigger),
        (m["hit_logo"], 80.0, Logo),
    ]
    return [cls(a, b) for a, b, cls in S]
