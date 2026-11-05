"""3D sets for the TVA 1 broadcast: studio desk, palace podium with the
depth lever, the block flat, the neighbour's window, the press room.

Every set renders an internal W x H (16:9) frame; the trailer upscales it
nearest-neighbour x3 into 1920x1080. Characters are the game's box rigs
(figure_kit / cast3d); talking mouths follow the real VO envelope.
"""
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "trailer3d"))
import common as C  # noqa: E402  (sets SDL dummy drivers, src/ on sys.path)
import pygame  # noqa: E402
import props3d as P  # noqa: E402
from common import clamp, glow_sprite, keys, lerp, seg, smooth, vlerp  # noqa: E402
from engine3d import POSES, box, quad_xz, rot_x, rot_y, rot_z  # noqa: E402
from engine3d.core import m_apply  # noqa: E402
from engine3d.ik import shoulder_world, solve_arm  # noqa: E402

W, H = 640, 360


def renderer(fog, f0, f1, light):
    import engine3d
    r = engine3d.Renderer(W, H, fog=fog, fog_start=f0, fog_end=f1)
    r.light = light
    return r


def hum(who, **kw):
    from cutscenes.cast3d import humanoid3d
    return humanoid3d(who, **kw)


def spec(who, **kw):
    from cutscenes.cast3d import spec3d
    return spec3d(who, **kw)


def person(sp):
    from engine3d import Humanoid
    return Humanoid(sp)


def gradient(top, bottom):
    return C.gradient(top, bottom, h=H, w=W)


def _talk_faces():
    """Talking variants of each face: corners near flat and no resting gap,
    so the animated jaw reads as one mouth instead of a bracket."""
    from engine3d.rig import EXPRESSIONS
    for name in list(EXPRESSIONS):
        if name.startswith("tk_"):
            continue
        d = dict(EXPRESSIONS[name])
        d["mouth_curve"] *= 0.35
        d["mouth_open"] = 0.0
        EXPRESSIONS["tk_" + name] = d


_talk_faces()


def talk(hm, env, t, expr=None):
    """Mouth follows the VO envelope, held at 15 Hz on three shapes
    (closed, half, open) like hand-keyed lip flap."""
    m = 0.0
    if env:
        tq = math.floor(t * 15) / 15.0
        m = clamp(0.65 * (env(tq) + env(tq - 1 / 15.0)))
    level = 0.0 if m < 0.2 else (0.4 if m < 0.62 else 0.75)
    hm.set_expression("tk_" + (expr or "neutral"), mouth_open=level)


def pose(base="stand", **kw):
    p = dict(POSES[base])
    p.update(kw)
    return p


def wob(t, ph):
    """Smooth wander in [-1, 1]: two detuned sines, never a loop you can spot."""
    return (math.sin(t * 0.7 + ph) + 0.6 * math.sin(t * 1.13 + ph * 1.7)) / 1.6


def slow(env, t):
    """Phrase energy: speech averaged over the last second, so hands rise on a
    phrase and settle between phrases instead of twitching on syllables."""
    if not env:
        return 0.0
    w = [1.0 - k / 12.0 for k in range(12)]
    return clamp(sum(env(t - k * 0.085) * w[k] for k in range(12)) / sum(w) * 1.8)


def alive(p, t, env=None, seed=0.0, amt=1.0):
    """Breath, weight shift, idle head and nods on the phrase."""
    p = dict(p)
    e = slow(env, t)
    p["spine"] = p.get("spine", 3) + amt * 1.4 * math.sin(t * 1.6 + seed) + 2.0 * e
    p["spine_r"] = p.get("spine_r", 0) + amt * 1.5 * wob(t * 0.6, seed + 1)
    p["twist"] = p.get("twist", 0) + amt * 4.0 * wob(t * 0.5, seed + 2)
    p["head_y"] = p.get("head_y", 0) + amt * 6.0 * wob(t * 0.45, seed + 3)
    p["head_p"] = p.get("head_p", 0) + 1.2 * math.sin(t * 0.9 + seed) + 4.0 * e * math.sin(t * 3.1 + seed)
    return p


def hands(hm, p, pos, yaw, t, env=None, rest=None, world=None, seed=0.0, amp=1.0,
          lift=(0.12, 0.06, 0.05), pole=(0.45, -0.85, -0.5)):
    """Both hands placed by IK. ``rest`` = per-side offset from that shoulder in
    body space (x = outward, y = up, z = forward); speech lifts one hand at a
    time off its rest into a small open gesture. ``world`` = side ->
    (point, weight) pins a hand to a world point (lever, chest, sill)."""
    rest, world = rest or {}, world or {}
    e = amp * slow(env, t)
    lead = smooth(0.5 + 0.5 * math.sin(t * 0.55 + seed))
    R = rot_y(yaw)
    for side in "rl":
        sx = 1 if side == "r" else -1
        k = e * (0.25 + 0.75 * (lead if side == "r" else 1.0 - lead))
        ph = seed + (0.0 if side == "r" else 2.1)
        beat = 0.5 + 0.5 * math.sin(t * 2.4 + ph)
        ox, oy, oz = rest.get(side, (0.03, -0.9 * 0.61 * hm._scale, 0.08))   # default: hanging
        loc = (sx * (ox + lift[2] * k + 0.012 * wob(t, ph)),
               oy + lift[0] * k * (0.55 + 0.45 * beat) + 0.01 * wob(t * 1.3, ph + 4),
               oz + lift[1] * k + 0.01 * wob(t * 0.9, ph + 7))
        sh = shoulder_world(hm, p, pos, yaw, side)
        d = m_apply(R, loc)
        tg = (sh[0] + d[0], sh[1] + d[1], sh[2] + d[2])
        if side in world:
            wt, wk = world[side]
            tg = vlerp(tg, wt, clamp(wk))
        p = solve_arm(hm, p, pos, yaw, side, tg, pole=(pole[0] * sx, pole[1], pole[2]))
    return p


class Set:
    def __init__(self):
        self.r = None

    def ensure(self):
        if self.r is None:
            self.setup()

    def release(self):
        if self.r is not None and hasattr(self.r, "release"):
            try:
                self.r.release()
            except Exception:
                pass
        self.r = None

    def frame(self, bg, dyn):
        r = self.r
        r.surface.blit(bg, (0, 0))
        r.begin()
        r.add_static()
        dyn(r)
        r.flush(r.surface)
        return r.surface


def _crest(size, col=(196, 160, 70)):
    """Acaristan crest: a shield with a star and two wheat strokes."""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    k = size / 100.0
    pts = [(50, 6), (88, 20), (82, 64), (50, 94), (18, 64), (12, 20)]
    pygame.draw.polygon(s, col, [(x * k, y * k) for x, y in pts])
    pygame.draw.polygon(s, (120, 24, 28), [(x * k, y * k) for x, y in
                                           [(50, 14), (80, 25), (75, 61), (50, 85), (25, 61), (20, 25)]])
    star = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = 18 if i % 2 == 0 else 7
        star.append(((50 + rr * math.cos(a)) * k, (46 + rr * math.sin(a)) * k))
    pygame.draw.polygon(s, col, star)
    return s


# ═══ STUDIO: the announcer's desk ═══════════════════════════════════════
class Studio(Set):
    def setup(self):
        self.lt = C.light((0.3, 0.8, -0.6), 0.44, 0.85, sky=0.05, tint=(1.0, 0.97, 0.92))
        self.r = renderer((14, 14, 16), 6, 30, self.lt)
        r = self.r
        # desk: wide anchor desk with a front panel and the TVA stripe
        r.bake(box(2.8, 0.06, 0.9, (70, 52, 38), center=(0, 1.02, -0.35)))
        r.bake(box(2.7, 0.98, 0.06, (54, 40, 30), center=(0, 0.5, -0.78)))
        r.bake(box(2.7, 0.08, 0.02, (196, 160, 70), center=(0, 0.78, -0.82), emissive=True))
        r.bake(box(0.36, 0.14, 0.02, (120, 24, 28), center=(0, 0.5, -0.82), emissive=True))
        # papers + microphone
        r.bake(box(0.34, 0.01, 0.24, (225, 222, 210), center=(-0.28, 1.06, -0.5)))
        r.bake(box(0.04, 0.22, 0.04, (30, 30, 32), center=(0.36, 1.16, -0.52)))
        r.bake(box(0.07, 0.08, 0.07, (40, 40, 44), center=(0.36, 1.3, -0.52)))
        self.bg = self._backdrop()
        self.bg_deep = self._backdrop(deep=True)
        sp = spec("civilian", long_coat=None, jacket=(58, 60, 66), pants=(40, 40, 44),
                  hair_style="slick", hair=(28, 24, 22), glasses=(20, 20, 22),
                  tie=(120, 24, 28), lapel=(46, 48, 54), cuff=(210, 205, 195), stubble_t=0.0,
                  armband=None)
        sp.pop("stubble", None)
        self.ann = person(sp)

    def _backdrop(self, deep=False):
        bg = gradient((26, 28, 36), (10, 10, 14)) if not deep else gradient((34, 22, 30), (12, 10, 16))
        glow = (60, 64, 76) if not deep else (214, 170, 90)
        for x in (40, W - 140):
            pygame.draw.rect(bg, (34, 36, 44), (x, 30, 100, 240))
            for j in range(10):
                pygame.draw.rect(bg, glow if (j + x // 40) % 3 else (90, 94, 110), (x + 8, 42 + j * 22, 84, 11))
        for x in range(0, W, 64):                       # back-wall seams
            pygame.draw.line(bg, (18, 18, 24), (x, 0), (x, H))
        pygame.draw.rect(bg, (196, 160, 70), (0, 286, W, 3))
        bg.blit(_crest(110), (170, 46))
        f = C.font("oswald", 54)
        img = f.render("TVA 1", True, (196, 160, 70))
        x0 = W - 170 - img.get_width()
        if deep:                                        # the logo now has depth too
            for i in range(9, 0, -1):
                bg.blit(f.render("TVA 1", True, (110 - i * 6, 30, 30)), (x0 + i, 70 + i))
        bg.blit(img, (x0, 70))
        pygame.draw.rect(bg, (120, 24, 28), (x0, 140, img.get_width(), 6))
        return bg

    def render(self, t, env=None, cam="mid", expr=None, look=0.0, deep=False, reach=0.0):
        self.ensure()
        r = self.r
        talk(self.ann, env, t, expr)
        k = smooth(clamp(reach))                      # fist to the lens: "do not touch the screen"
        pos = (0, 0, 0.05)
        p = alive(pose("stand", head_y=look, spine=4 + 10 * k, head_p=-6 * k), t, env, seed=0.3)
        sh = shoulder_world(self.ann, p, pos, 180.0, "l")
        lens = (sh[0] + 0.05, sh[1] + 0.02, sh[2] - 0.6)
        p = hands(self.ann, p, pos, 180.0, t, env, rest={"r": (-0.07, -0.36, 0.33), "l": (-0.07, -0.36, 0.33)},
                  world={"l": (lens, k)}, seed=0.3, lift=(0.14, 0.07, 0.05))
        if cam == "close":
            eye, tgt, fov = (0.05, 1.5, -2.3 + 0.03 * t), (0, 1.45, 0), 30
        elif cam == "wide":
            eye, tgt, fov = (-0.5, 1.6, -6.0 + 0.06 * t), (0, 1.15, 0), 40
        else:
            eye, tgt, fov = (0.15, 1.78, -4.0 + 0.04 * t), (0, 1.3, 0), 34
        sway = 0.05 * math.sin(t * 0.35)
        r.set_camera((eye[0] + sway, eye[1], eye[2]), tgt, fov)
        return self.frame(self.bg_deep if deep else self.bg,
                          lambda r: r.add_humanoid(self.ann, p, pos, 180.0, rifle_on=False))




def proj_quad(r, pts):
    out = []
    for p in pts:
        q = r.project(p)
        if q is None:
            return None
        out.append((q[0], q[1]))
    return out


def screen_on(r, img, center, half_w, half_h):
    """Map img onto a vertical rectangle facing -z."""
    cx, cy, cz = center
    pts = [(cx - half_w, cy + half_h, cz), (cx + half_w, cy + half_h, cz),
           (cx + half_w, cy - half_h, cz), (cx - half_w, cy - half_h, cz)]
    q = proj_quad(r, pts)
    if q is not None:
        r.add_sprite((cx, cy, cz), C.warp_sprite(img, q), layer=2, bias=-0.05)


def lever_mesh(angle):
    """The DEPTH lever: a pedestal + a knife-switch handle pivoting about x
    (0 = up, 1 = thrown)."""
    m = rot_x(lerp(-30, 58, angle))
    parts = [box(0.42, 0.95, 0.36, (70, 72, 78), center=(0, 0.475, 0)),
             box(0.46, 0.07, 0.4, (196, 160, 70), center=(0, 0.96, 0)),
             box(0.3, 0.14, 0.02, (160, 30, 30), center=(0, 0.66, -0.19), emissive=True)]
    handle = [box(0.05, 0.55, 0.05, (40, 40, 44), center=(0, 0.275, 0)),
              box(0.2, 0.09, 0.09, (170, 30, 30), center=(0, 0.56, 0))]
    return P.merge(*(parts + [P.transformed(h, m, (0, 1.0, 0)) for h in handle]))


def kettle_mesh():
    return P.merge(box(0.22, 0.24, 0.18, (190, 190, 196), center=(0, 0.12, 0)),
                   box(0.1, 0.03, 0.03, (40, 40, 44), center=(0, 0.28, 0)),
                   box(0.03, 0.12, 0.03, (40, 40, 44), center=(0.05, 0.22, 0)),
                   box(0.06, 0.05, 0.05, (190, 190, 196), center=(-0.14, 0.17, 0)))


def dial_img(v, label):
    """Gauge face: 2D on the left, 2.5D in the red zone on the right."""
    n = 120
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    c = n // 2
    pygame.draw.circle(s, (30, 28, 26), (c, c), c)
    pygame.draw.circle(s, (228, 220, 196), (c, c), c - 6)
    for i in range(11):
        a = math.radians(-150 + i * 12)
        r0 = c - 14 if i % 5 else c - 22
        pygame.draw.line(s, (30, 30, 30), (c + r0 * math.cos(a), c + r0 * math.sin(a)),
                         (c + (c - 8) * math.cos(a), c + (c - 8) * math.sin(a)), 3)
    pygame.draw.arc(s, (170, 30, 30), (10, 10, n - 20, n - 20), math.radians(10), math.radians(50), 8)
    f = C.font("oswald", 18)
    for txt, x in (("2D", 26), ("2.5D", n - 30)):
        img = f.render(txt, True, (30, 30, 30))
        s.blit(img, img.get_rect(center=(x, c + 22)))
    lab = C.font("mono", 11).render(label, True, (60, 56, 50))
    s.blit(lab, lab.get_rect(center=(c, c + 40)))
    a = math.radians(lerp(-150, -30, v))
    pygame.draw.line(s, (20, 20, 20), (c, c), (c + (c - 18) * math.cos(a), c + (c - 18) * math.sin(a)), 4)
    pygame.draw.circle(s, (20, 20, 20), (c, c), 7)
    return s


def plate_img(lines, w=260, h=60, bg=(196, 160, 70), fg=(30, 24, 16)):
    s = pygame.Surface((w, h))
    s.fill(bg)
    pygame.draw.rect(s, fg, s.get_rect(), 3)
    f = C.font("oswald", int(h / (len(lines) + 0.6)))
    y = h / (len(lines) + 1)
    for i, ln in enumerate(lines):
        img = f.render(ln, True, fg)
        s.blit(img, img.get_rect(center=(w // 2, int(y * (i + 1)))))
    return s


def chair_mesh():
    legs = [box(0.05, 0.45, 0.05, (150, 120, 60), center=(x, 0.225, z)) for x in (-0.2, 0.2) for z in (-0.2, 0.2)]
    return P.merge(box(0.46, 0.06, 0.46, (92, 30, 30), center=(0, 0.46, 0)),
                   box(0.46, 0.6, 0.06, (92, 30, 30), center=(0, 0.78, -0.22)), *legs)


SEATED = dict(spine=4, lhip_p=88, lkn=90, rhip_p=88, rkn=90, lsh_p=34, lsh_r=-8, lel=64,
              rsh_p=34, rsh_r=-8, rel=64)


# ═══ PALACE: the hall of state, the President, the Dimension Switch ═════
class Palace(Set):
    LEVER = (1.3, 0.0, -0.15)
    CAB = (1.3, 0.0, 0.55)           # switch cabinet behind the lever
    KETTLE = (2.35, 0.0, 0.35)

    def setup(self):
        self.lt = C.light((-0.35, 0.8, -0.55), 0.46, 0.78, sky=0.06, tint=(1.06, 0.97, 0.86))
        self.r = renderer((14, 10, 10), 14, 34, self.lt)
        r = self.r
        for i in range(-7, 7):                                   # marble checker floor
            for j in range(-10, 6):
                col = (176, 170, 160) if (i + j) % 2 else (70, 66, 64)
                r.bake(quad_xz(i, j, i + 1, j + 1, 0.0, col))
        r.bake(quad_xz(-0.8, -10, 0.8, 4, 0.004, (110, 26, 28)))   # carpet runner
        r.bake(box(16, 8, 0.3, (138, 126, 108), center=(0, 4, 4.2)))           # back wall
        for x in (-5.2, -2.1, 2.1, 5.2):                                         # columns
            r.bake(box(0.7, 6.4, 0.7, (196, 188, 168), center=(x, 3.2, 3.6)))
            r.bake(box(0.95, 0.3, 0.95, (196, 160, 70), center=(x, 6.5, 3.6)))
            r.bake(box(0.95, 0.25, 0.95, (150, 140, 120), center=(x, 0.125, 3.6)))
        r.bake(box(3.0, 5.0, 0.06, (120, 22, 26), center=(0, 3.6, 4.0)))      # crest banner
        r.bake(box(3.0, 0.16, 0.08, (196, 160, 70), center=(0, 6.1, 3.98)))
        for x in (-3.65, 3.65):                                                  # side windows + drapes
            r.bake(box(1.6, 3.6, 0.05, (40, 52, 80), center=(x, 3.4, 4.02), emissive=True))
            for dx in (-0.95, 0.95):
                r.bake(box(0.42, 4.6, 0.12, (100, 20, 24), center=(x + dx, 3.5, 3.9)))
        for x in (-2.9, 2.9):                                                    # flags
            r.bake(box(0.06, 3.2, 0.06, (196, 160, 70), center=(x, 1.6, 2.7)))
            for k, c in enumerate(((150, 24, 28), (196, 160, 70), (40, 60, 110))):
                r.bake(box(0.9, 0.34, 0.03, c, center=(x + 0.48, 2.95 - k * 0.34, 2.7)))
        r.bake(box(0.8, 1.15, 0.5, (60, 40, 30), center=(0, 0.575, -0.55)))     # podium
        r.bake(box(0.86, 0.06, 0.56, (90, 64, 44), center=(0, 1.17, -0.55)))
        r.bake(box(0.5, 0.06, 0.02, (196, 160, 70), center=(0, 0.95, -0.81), emissive=True))
        for dx in (-0.12, 0.12):                                                 # microphones
            r.bake(box(0.02, 0.32, 0.02, (30, 30, 32), center=(dx, 1.36, -0.68)))
            r.bake(box(0.05, 0.07, 0.05, (20, 20, 22), center=(dx, 1.54, -0.7)))
        cx, _, cz = self.CAB                                                     # switch cabinet
        r.bake(box(1.5, 1.9, 0.55, (64, 70, 66), center=(cx, 0.95, cz)))
        r.bake(box(1.56, 0.08, 0.6, (196, 160, 70), center=(cx, 1.92, cz)))
        for i, x in enumerate((-0.55, -0.35, 0.35, 0.55)):
            r.bake(box(0.08, 0.08, 0.02, ((200, 40, 40), (220, 180, 60))[i % 2],
                       center=(cx + x, 0.55, cz - 0.285), emissive=True))
        for k in range(12):                                                      # cable to the kettle
            u = k / 11.0
            r.bake(box(0.1, 0.02, 0.06, (16, 16, 16),
                       center=(lerp(self.LEVER[0] + 0.2, self.KETTLE[0], u), 0.012,
                               lerp(self.LEVER[2], self.KETTLE[2], u) - 0.25 * math.sin(u * math.pi))))
        kx, _, kz = self.KETTLE
        r.bake(box(0.5, 0.62, 0.5, (88, 60, 40), center=(kx, 0.31, kz)))            # side table
        r.bake(box(0.4, 0.01, 0.4, (230, 226, 214), center=(kx, 0.625, kz)))        # doily
        r.bake(kettle_mesh(), t=(kx, 0.63, kz))
        self.seats = []
        for z in (-3.4, -4.6):                                                    # audience chairs
            for x in (-2.6, -1.7, 1.7, 2.6):
                r.bake(chair_mesh(), t=(x, 0, z))
                self.seats.append((x, z))
        self.bg = gradient((26, 18, 16), (12, 8, 8))
        self.crest = _crest(160)
        self.plate = plate_img(["DIMENSION SWITCH", "MODEL 2.5"])
        self.pres = hum("president")
        sp = spec("civilian", long_coat=None, jacket=(70, 84, 96), pants=(60, 72, 84),
                  hair_style="mop", armband=None)
        self.tech = person(sp)
        self.guards = [hum("krap"), hum("krap")]
        self.crowd = [hum("commander"), person(spec("civilian", jacket=(60, 60, 64), armband=None)),
                      person(spec("civilian", jacket=(90, 80, 70), hair_style="messy", armband=None)),
                      person(spec("civilian", jacket=(40, 44, 54), armband=None))]

    def render(self, t, env=None, shot="front", lever=0.0, kick=0.0, turn=0.0, whisper=False,
               tech_env=None, tech_in=0.0, px=0.0, flourish=0.0):
        self.ensure()
        r = self.r
        talk(self.pres, env, t, "worried" if whisper else "smile")
        pres = self.pres
        if shot == "front":
            ppos, yaw = (0.0, 0.0, 0.0), 180.0
            p = alive(pose("stand", spine=7), t, env, seed=1.1, amt=1.3)
            f = smooth(clamp(flourish))                 # "...the half dimension!" - the big arm
            sh = shoulder_world(pres, p, ppos, yaw, "r")
            up = (sh[0] - 0.3, sh[1] - 0.02, sh[2] - 0.42)
            p = hands(pres, p, ppos, yaw, t, env, rest={"r": (-0.04, -0.52, 0.36), "l": (-0.04, -0.52, 0.36)},
                      world={"r": (up, f)}, seed=1.1, amp=1.4, lift=(0.24, 0.12, 0.1))
        else:
            ppos = (0.78, 0.0, -0.1)
            yaw = 180.0 - 70.0 * smooth(turn)
            if kick > 0:
                k = math.sin(clamp(kick) * math.pi)
                p = pose("stand", rhip_p=-70 * k, rkn=30 * (1 - k), spine=-8 * k, head_p=12 * k)
                p = hands(pres, p, ppos, yaw, t, rest={"r": (0.2, -0.5, 0.05), "l": (0.2, -0.5, 0.05)})
            elif whisper:
                p = alive(pose("stand", head_p=10, head_y=42, spine=6), t, seed=1.1, amt=0.6)
                p = hands(pres, p, ppos, yaw, t, rest={"l": (-0.12, 0.3, 0.2)})
            else:
                p = alive(pose("stand", head_y=-18 if shot == "lever" else 0), t, env, seed=1.1, amt=0.7)
                pin = {}
                if shot == "lever":                     # hand on the red grip all the way through
                    lx, _, lz = self.LEVER
                    g = m_apply(rot_x(lerp(-30, 58, lever)), (0.0, 0.56, 0.0))
                    pin = {"l": ((lx + g[0], 1.0 + g[1], lz + g[2]), 1.0)}
                p = hands(pres, p, ppos, yaw, t, env, world=pin, seed=1.1, amp=0.6)
        tp = alive(pose("stand", head_p=8, head_y=-20, spine=6), t, tech_env, seed=2.7)
        tpos, tyaw = (lerp(3.5, 2.75, smooth(tech_in)), 0, 0.6), 205.0
        tp = hands(self.tech, tp, tpos, tyaw, t, tech_env, rest={"r": (-0.1, -0.4, 0.2), "l": (-0.1, -0.4, 0.2)},
                   seed=2.7, lift=(0.16, 0.08, 0.06))
        talk(self.tech, tech_env, t, "worried")
        if shot == "front":
            eye, tgt, fov = (0.05, 1.68, -3.9 + 0.08 * t), (0.15, 1.52, 1.0), 36
        elif shot == "wide":
            eye, tgt, fov = (-0.4, 2.7, -8.6 + 0.1 * t), (0.5, 1.7, 1.5), 48
        elif shot == "lever":
            eye, tgt, fov = (2.6, 1.6, -2.5), (1.15, 1.15, 0.1), 42
        elif shot == "tech":
            eye, tgt, fov = (1.7, 1.5, -1.9), (2.55, 1.15, 0.4), 44
        elif shot == "kick":
            eye, tgt, fov = (-0.9, 1.45, -3.2), (1.1, 0.95, 0.2), 44
        else:                                                   # side: the whisper two-shot
            eye, tgt, fov = (-1.4, 1.7, -2.3), (1.4, 1.42, 0.3), 46
        if kick > 0:
            sx, sy = C.shake(t, 0.05 * math.sin(clamp(kick) * math.pi))
            eye = (eye[0] + sx, eye[1] + sy, eye[2])
        r.set_camera(eye, tgt, fov)
        needle = 0.04 + 0.02 * math.sin(t * 7) if kick < 0.5 else clamp((kick - 0.5) * 3) * 0.96
        lamp = kick > 0.55 and int(t * 12) % 2 == 0

        def dyn(r):
            screen_on(r, self.crest, (0, 4.1, 3.95), 1.0, 1.0)
            cx, _, cz = self.CAB
            fz = cz - 0.29
            screen_on(r, dial_img(needle, "DEPTH"), (cx - 0.36, 1.35, fz), 0.24, 0.24)
            screen_on(r, dial_img(needle * 0.9, "VOLTAGE"), (cx + 0.36, 1.35, fz), 0.24, 0.24)
            screen_on(r, self.plate, (cx, 0.85, fz), 0.42, 0.1)
            if lamp:
                r.add_sprite((cx, 1.7, fz - 0.05), glow_sprite(0.5, (255, 230, 150)), layer=2)
            r.add_humanoid(self.pres, p, ppos, yaw, rifle_on=False)
            r.add_humanoid(self.tech, tp, tpos, tyaw, rifle_on=False)
            for g, x in zip(self.guards, (-3.6, 3.6)):
                gp = alive(pose("stand"), t, seed=x, amt=0.35)
                r.add_humanoid(g, hands(g, gp, (x, 0, 2.4), 180.0, t, seed=x), (x, 0, 2.4), 180.0, rifle_on=False)
            for h, (x, z) in zip(self.crowd, self.seats):
                q = dict(SEATED)
                q["head_y"] = 6 * math.sin(t * 0.4 + x)
                r.add_humanoid(h, q, (x, 0.02, z - 0.02), 0.0, rifle_on=False)
            v, f = P.dyn_faces(lever_mesh(lever), None, self.LEVER)
            r.add_dynamic(v, f)
            if kick > 0.4:
                rng = random.Random(int(t * 30))
                for i in range(12):
                    a = rng.uniform(0, math.tau)
                    d = rng.uniform(0.1, 0.7) * kick
                    q = (self.LEVER[0] + math.cos(a) * d, 1.0 + abs(math.sin(a)) * d, self.LEVER[2] - 0.2)
                    r.add_sprite(q, glow_sprite(0.06, (255, 220, 120)), layer=2)
        return self.frame(self.bg, dyn)


# ═══ FLAT: Grandma on the sofa, the TV ═══════════════════════════════════
class Flat(Set):
    TV = (0.0, 0.0, -2.2)

    def setup(self):
        self.lt = C.light((0.2, 0.6, -0.8), 0.3, 0.7, sky=0.04, tint=(0.8, 0.9, 1.15))
        self.r = renderer((16, 14, 12), 6, 25, self.lt)
        r = self.r
        r.bake(quad_xz(-5, -5, 5, 5, 0.0, (80, 50, 40), seg=4))
        r.bake(box(2.4, 0.45, 0.9, (90, 70, 50), center=(0, 0.22, 0.3)))             # sofa
        r.bake(box(2.4, 0.8, 0.25, (100, 78, 56), center=(0, 0.6, 0.75)))
        for x in (-1.25, 1.25):
            r.bake(box(0.2, 0.65, 0.9, (100, 78, 56), center=(x, 0.33, 0.3)))
        r.bake(box(0.7, 0.04, 0.3, (230, 230, 225), center=(0, 1.02, 0.8)))           # lace doily
        tx, _, tz = self.TV                                                           # TV on a cabinet
        r.bake(box(1.1, 0.55, 0.5, (70, 48, 32), center=(tx, 0.27, tz)))
        r.bake(box(0.9, 0.7, 0.6, (58, 44, 30), center=(tx, 0.9, tz)))
        r.bake(box(0.25, 0.04, 0.2, (230, 230, 225), center=(tx, 1.27, tz)))
        r.bake(box(0.02, 0.3, 0.02, (160, 160, 166), center=(tx - 0.1, 1.42, tz)))
        r.bake(box(0.02, 0.3, 0.02, (160, 160, 166), center=(tx + 0.1, 1.42, tz)))
        self.bg = self._backdrop()
        sp = spec("fisherman", hat=None, beard=None, hair=(200, 200, 196), hair_style="bald",
                  bandana=(150, 40, 50), jacket=(70, 60, 90), long_coat=(70, 60, 90))
        self.gran = person(sp)

    def _backdrop(self):
        bg = gradient((90, 76, 56), (60, 50, 38))
        for y in range(0, H, 18):
            for x in range((y // 18) % 2 * 16, W, 32):
                pygame.draw.circle(bg, (104, 88, 64), (x, y), 3)
        pygame.draw.rect(bg, (40, 52, 84), (16, 50, 120, 170))           # night window
        for k in range(6):
            pygame.draw.rect(bg, (220, 190, 110), (28 + (k * 37) % 96, 70 + (k * 53) % 130, 8, 10))
        pygame.draw.rect(bg, (210, 200, 180), (16, 50, 120, 170), 6)
        pygame.draw.line(bg, (210, 200, 180), (76, 50), (76, 220), 4)
        pygame.draw.rect(bg, (150, 40, 50), (4, 40, 30, 200))             # curtains
        pygame.draw.rect(bg, (150, 40, 50), (118, 40, 30, 200))
        px = W - 120                                                       # portrait of the President
        pygame.draw.rect(bg, (150, 120, 50), (px, 60, 80, 100))
        pygame.draw.rect(bg, (40, 36, 34), (px + 8, 68, 64, 84))
        pygame.draw.rect(bg, (190, 150, 120), (px + 26, 84, 28, 30))
        pygame.draw.rect(bg, (24, 26, 40), (px + 16, 114, 48, 38))
        pygame.draw.rect(bg, (150, 24, 28), (px + 38, 118, 4, 26))
        rx, ry, rw, rh = W // 2 - 170, 40, 340, 150   # the wall carpet
        pygame.draw.rect(bg, (120, 30, 32), (rx, ry, rw, rh))
        pygame.draw.rect(bg, (180, 140, 70), (rx + 8, ry + 8, rw - 16, rh - 16), 4)
        for i in range(5):
            cx = rx + 40 + i * 65
            pygame.draw.polygon(bg, (40, 50, 90), [(cx, ry + 30), (cx + 22, ry + 75), (cx, ry + 120), (cx - 22, ry + 75)])
            pygame.draw.polygon(bg, (200, 160, 80), [(cx, ry + 55), (cx + 9, ry + 75), (cx, ry + 95), (cx - 9, ry + 75)])
        return bg

    def render(self, t, env=None, shot="gran", screen=None, expr=None, lean=0.0):
        self.ensure()
        r = self.r
        flick = 0.85 + 0.15 * math.sin(t * 13) * math.sin(t * 5.1)
        self.lt.ambient = 0.3 * flick
        talk(self.gran, env, t, expr)
        p = dict(SEATED)
        p.update(spine=6 - 14 * lean, head_p=4 + 6 * lean)
        p = alive(p, t, env, seed=2.0, amt=0.8)
        p = hands(self.gran, p, (0, -0.18, 0.5), 180.0, t, env,
                  rest={"r": (-0.07, -0.36, 0.3), "l": (-0.07, -0.36, 0.3)}, seed=2.0, amp=0.9, lift=(0.14, 0.1, 0.05))
        if shot == "gran":
            eye, tgt, fov = (0.0, 1.2, -1.95 + 0.02 * t), (0.0, 0.88, 0.3), 48
        else:
            eye, tgt, fov = (-0.55, 1.35, 0.6), (0.0, 0.95, -2.2), 42
        r.set_camera(eye, tgt, fov)

        def dyn(r):
            r.add_humanoid(self.gran, p, (0, -0.18, 0.5), 180.0, rifle_on=False)
            if screen is not None:
                tx, _, tz = self.TV
                screen_on(r, screen, (tx, 0.92, tz + 0.31), 0.36, 0.27)
            if shot == "gran":
                r.add_sprite((0.0, 1.0, -1.6), glow_sprite(1.2 * flick, (40, 70, 120)), layer=2)
        return self.frame(self.bg, dyn)


# ═══ WINDOW: the neighbour, the man on the roof ══════════════════════════
class Window(Set):
    def setup(self):
        self.lt = C.light((0.5, 0.7, -0.5), 0.36, 0.7, sky=0.1, tint=(0.95, 0.95, 1.05))
        self.r = renderer((70, 80, 96), 20, 120, self.lt)
        r = self.r
        r.bake(P.apartment_block(18, 30, 10, 3, facing=-1, lit=0.3, col=(110, 108, 102), axis="z"),
               t=(0, 0, 5.0))
        r.bake(box(1.6, 0.12, 0.35, (150, 148, 140), center=(0, 8.3, -0.1)))     # sill
        r.bake(box(1.6, 1.5, 0.06, (16, 18, 22), center=(0, 9.1, -0.01)))       # window hole
        r.bake(box(1.2, 0.3, 0.02, (220, 220, 216), center=(-2.5, 7.6, -0.04)))  # laundry
        self.bg = gradient((120, 140, 170), (190, 196, 204))
        sp = spec("civilian", long_coat=None, jacket=(200, 196, 186), pants=(40, 50, 90),
                  hair_style="messy", armband=None)
        sp["cuff"] = None
        self.nb = person(sp)
        self.bir = hum("biribel", rifle="sniper")

    def render(self, t, env=None, up=0.0, wave=0.0):
        self.ensure()
        r = self.r
        talk(self.nb, env, t, "surprised" if up > 0.3 else "grin")
        npos = (0, 7.45, -0.15)
        p = alive(pose("stand", spine=20, head_p=-25 * up - 6), t, env, seed=3.3)
        hold = 1.0 - 0.8 * slow(env, t)              # leaning on the sill, lets go to talk
        p = hands(self.nb, p, npos, 180.0, t, env, rest={"r": (-0.05, -0.3, 0.32), "l": (-0.05, -0.3, 0.32)},
                  world={"r": ((-0.26, 8.4, -0.22), hold), "l": ((0.26, 8.4, -0.22), hold)}, seed=3.3,
                  lift=(0.16, 0.08, 0.06))
        u = smooth(up)
        r.set_camera((lerp(0.6, 1.2, u), lerp(7.6, 27.8, u), lerp(-3.6, -4.2, u)),
                     (lerp(0.0, 1.4, u), lerp(8.9, 30.6, u), lerp(0.0, 0.6, u)), lerp(38, 40, u))
        bp = pose("kneel", rsh_p=lerp(30, 160, wave), rel=lerp(60, 20, wave) + 20 * math.sin(t * 9) * wave)

        def dyn(r):
            r.add_humanoid(self.nb, p, npos, 180.0, rifle_on=False)
            r.add_humanoid(self.bir, bp, (1.5, 30.0, 0.6), 180.0, rifle_on=wave < 0.5)
        return self.frame(self.bg, dyn)


# ═══ PRESS: Balaceanu's press podium ═════════════════════════════════════
class Press(Set):
    def setup(self):
        self.lt = C.light((0.2, 0.7, -0.7), 0.4, 0.85, sky=0.05, tint=(1.0, 0.98, 0.95))
        self.r = renderer((16, 18, 26), 8, 30, self.lt)
        r = self.r
        r.bake(box(0.9, 1.15, 0.5, (40, 50, 80), center=(0, 0.575, -0.55)))
        r.bake(box(0.6, 0.12, 0.02, (196, 160, 70), center=(0, 0.9, -0.81), emissive=True))
        rng = random.Random(4)
        for i in range(7):                        # mic cluster
            x = -0.3 + i * 0.1
            h = rng.uniform(0.2, 0.35)
            r.bake(box(0.025, h, 0.025, (24, 24, 26), center=(x, 1.15 + h / 2, -0.72)))
            r.bake(box(0.06, 0.07, 0.06, rng.choice([(150, 30, 30), (30, 60, 140), (30, 30, 32), (220, 220, 220)]),
                       center=(x, 1.15 + h, -0.74)))
        self.bg = self._backdrop()
        self.bal = hum("balaceanu")
        self.flash = False

    def _backdrop(self):
        bg = gradient((30, 44, 80), (16, 22, 44))
        f = C.font("oswald", 20)
        img = f.render("GUVERNUL ACARISTAN", True, (44, 60, 104))
        for y in range(16, H, 72):
            for x in range(-((y // 72) % 2) * 130, W, 260):
                bg.blit(img, (x, y))
        for x in (0, W - 70):                            # flags at the wall ends
            for i, c in enumerate(((150, 24, 28), (196, 160, 70), (40, 60, 110))):
                pygame.draw.rect(bg, c, (x + 10, 60 + i * 40, 50, 40))
        bg.blit(_crest(70), (W // 2 - 35, 40))
        return bg

    def render(self, t, env=None, shot="mid", expr="grin", flashes=True, chest=0.0):
        self.ensure()
        r = self.r
        talk(self.bal, env, t, expr)
        c = smooth(clamp(chest * 3.0))                 # right hand to the medal
        p = alive(pose("stand", spine=5 - 6 * chest), t, env, seed=4.0, amt=1.1)
        sh = shoulder_world(self.bal, p, (0, 0, 0), 180.0, "r")
        medal = (sh[0] + 0.16, sh[1] - 0.18, sh[2] - 0.17)
        p = hands(self.bal, p, (0, 0, 0), 180.0, t, env, rest={"r": (-0.04, -0.45, 0.36), "l": (-0.04, -0.45, 0.36)},
                  world={"r": (medal, c)}, seed=4.0, amp=1.2, lift=(0.2, 0.1, 0.08))
        if shot == "close":
            eye, tgt, fov = (0.1, 1.85, -2.2 + 0.03 * t), (0, 1.75, 0), 28
        else:
            eye, tgt, fov = (0.25, 1.75, -4.0 + 0.05 * t), (0, 1.5, 0), 34
        r.set_camera(eye, tgt, fov)
        fl = []
        if flashes:
            rng = random.Random(int(t * 7))
            if rng.random() < 0.45:
                fl.append((rng.uniform(-2.5, 2.5), rng.uniform(0.8, 1.6), -3.2))

        def dyn(r):
            r.add_humanoid(self.bal, p, (0, 0, 0), 180.0, rifle_on=False)
            for q in fl:
                r.add_sprite(q, glow_sprite(0.5, (255, 255, 240)), layer=2)
        self.flash = bool(fl)
        return self.frame(self.bg, dyn)


# ═══ TEST CARD on the floor (the ending: it tilts back, then falls over) ═
class CardStand(Set):
    def setup(self):
        self.lt = C.light((0.2, 0.8, -0.5), 0.5, 0.6)
        self.r = renderer((10, 10, 12), 6, 30, self.lt)
        self.r.bake(quad_xz(-6, -6, 6, 6, 0.0, (40, 40, 44), seg=4))
        self.bg = gradient((14, 14, 18), (26, 26, 30))

    def render(self, t, card, fall=0.0):
        self.ensure()
        r = self.r
        r.set_camera((0.0, 1.0 + 1.4 * fall, -4.0), (0.0, 0.9 - 0.5 * fall, 0.0), 44)
        f = clamp(fall)
        ang = 90.0 * f * f
        if f >= 1.0:
            ang = 90.0
        a = math.radians(ang)
        hw, hh = 1.2, 0.9

        def pt(x, y):        # pivots on its bottom edge, falling backward (+z)
            return (x, 0.02 + y * math.cos(a), y * math.sin(a))
        quad = [pt(-hw, 2 * hh), pt(hw, 2 * hh), pt(hw, 0.0), pt(-hw, 0.0)]

        def dyn(r):
            q = proj_quad(r, quad)
            if q is not None:
                r.add_sprite(pt(0, hh), C.warp_sprite(card, q), layer=3)
        return self.frame(self.bg, dyn)


def _still(set_, t, out, **kw):
    pygame.init()
    pygame.display.set_mode((64, 64))
    s = set_.render(t, **kw)
    pygame.image.save(pygame.transform.scale(s, (W * 2, H * 2)), out)


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else "."
    e = lambda t: 0.6  # noqa: E731
    pal = Palace()
    shots = [("studio", Studio(), dict(env=e)), ("palace_front", pal, dict(env=e)),
             ("palace_wide", pal, dict(shot="wide")),
             ("palace_lever", pal, dict(shot="lever", lever=0.0)),
             ("palace_whisper", pal, dict(shot="side", whisper=True, env=e, turn=1.0, tech_in=1.0)),
             ("palace_tech", pal, dict(shot="tech", tech_env=e, tech_in=1.0)),
             ("palace_kick", pal, dict(shot="kick", kick=0.5, turn=1.0, lever=0.6, tech_in=1.0)),
             ("flat_gran", Flat(), dict(env=e)), ("window", Window(), dict(env=e)),
             ("press", Press(), dict(env=e, chest=1.0))]
    for name, st, kw in shots:
        _still(st, 1.0, os.path.join(d, name + ".png"), **kw)
        print("wrote", name)
