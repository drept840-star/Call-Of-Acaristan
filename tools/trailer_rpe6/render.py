"""RPE6 engine trailer for Call of Acaristan: the engine and the game, no story.

    python tools/trailer_rpe6/render.py --at 12 30 50   stills -> outputs/trailer_rpe6/stills/
    python tools/trailer_rpe6/render.py --sheet          one still per shot + _sheet.jpg
    python tools/trailer_rpe6/render.py                  full 80 s MP4 (1920x1080, 30 fps, score)
    python tools/trailer_rpe6/render.py --from 30 --to 45 --noaudio --out part.mp4

Every frame comes out of the engine: new GL set pieces (a voxel logo, a rig
built box by box, the K93D turntable), the live M6 yard and train scenes with
the HUD off and the body out of the set, and worlds from the story trailer
(tools/trailer3d) with their text left out.  No caption names a plot beat.
The cut follows "Shell Ghost" (Soundridemusic); score.py adds the sound design
from the events this renderer logs (shots, hits, boot ticks).
"""
import argparse
import json
import math
import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
os.environ.setdefault("ACARISTAN_RENDERER", "gl")
sys.path[:0] = [os.path.join(ROOT, "tools", "trailer3d"), os.path.join(ROOT, "tools"),
                os.path.join(ROOT, "src")]
import common as C  # noqa: E402  (dummy SDL drivers, fonts, easing, glow)
import numpy as np  # noqa: E402
import pygame  # noqa: E402

FPS = 30
OUT_W, OUT_H = 1920, 1080
PW, PH = 1920, 804                  # the 2.39:1 picture between the bars
BAR = (OUT_H - PH) // 2
TOTAL = 80.0
MUSIC_AT = 5.15                     # trailer clock of the music's first sample
OUT_DIR = os.path.join(ROOT, "outputs", "trailer_rpe6")
ORANGE, INK, DIM = C.ORANGE, C.INK, (168, 164, 156)
# white flash on the big music hits (trailer clock -> strength)
FLASH = {6.0: 1.0, 14.0: 0.5, 45.25: 0.4, 62.0: 0.55, 71.3: 0.85}
EVENTS = []                         # (T, kind) for score.py, logged while rendering video
clamp, smooth, seg, lerp, ease_out = C.clamp, C.smooth, C.seg, C.lerp, C.ease_out


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def spaced(txt, fnt, col, spacing):
    glyphs = [fnt.render(ch, True, col) for ch in txt]
    w = sum(g.get_width() for g in glyphs) + spacing * (len(glyphs) - 1)
    s = pygame.Surface((max(1, w), fnt.get_height()), pygame.SRCALPHA)
    x = 0
    for g in glyphs:
        s.blit(g, (x, 0))
        x += g.get_width() + spacing
    return s


def fade_in_out(lt, t_in, t_out, a=0.3, b=0.35):
    return clamp((lt - t_in) / a) * clamp((t_out - lt) / b)


# ── captions (crisp, on the 1920x1080 canvas) ───────────────────────────
def caption(cv, head, sub, t_in, t_out, lt):
    """Engine feature label, top left of the picture."""
    k = fade_in_out(lt, t_in, t_out)
    if k <= 0:
        return
    x, y = 96 - int(28 * (1 - ease_out(clamp((lt - t_in) / 0.45)))), BAR + 52
    lab = C.font("monob", 20).render("RPE6 //", True, ORANGE)
    big = spaced(head, C.font("oswald", 54), INK, 3)
    txt = C.typed(sub, lt - t_in - 0.25, 44)
    for img, pos in ((lab, (x, y)), (big, (x, y + 26))):
        img.set_alpha(int(255 * k))
        cv.blit(img, pos)
    pygame.draw.rect(cv, ORANGE, (x, y + 26 + big.get_height() + 6, int(60 * k), 3))
    if txt:
        s = C.font("mono", 24).render(txt, True, DIM)
        s.set_alpha(int(255 * k))
        cv.blit(s, (x, y + 26 + big.get_height() + 18))


def tag(cv, text, t_in, t_out, lt):
    """Typed lower-left line, the story trailer's location-tag look."""
    k = clamp((t_out - lt) / 0.4)
    s = C.typed(text, lt - t_in, 30)
    if lt < t_in or k <= 0 or not s:
        return
    cur = "_" if int(lt * 3) % 2 and len(s) < len(text) else ""
    img = C.font("mono", 26).render(s + cur, True, (214, 208, 194))
    img.set_alpha(int(255 * k))
    y = BAR + PH - 74
    cv.blit(img, (96, y))
    pygame.draw.rect(cv, ORANGE, (96, y - 12, 46, 4))


def slam(cv, text, t_in, t_out, lt, size=124):
    k = fade_in_out(lt, t_in, t_out, 0.08, 0.25)
    if k <= 0:
        return
    img = spaced(text, C.font("oswald", size), INK, 10)
    sc = 1.0 + 0.14 * (1 - ease_out(clamp((lt - t_in) / 0.22)))
    if sc != 1.0:
        img = pygame.transform.smoothscale(img, (int(img.get_width() * sc), int(img.get_height() * sc)))
    img.set_alpha(int(255 * k))
    cv.blit(img, (OUT_W // 2 - img.get_width() // 2, OUT_H // 2 - img.get_height() // 2))


# ── grade for the full-res GL picture ───────────────────────────────────
class Grain:
    """Vignette + per-pixel signed grain at 1920x804 (the post3d decision:
    grain is a wobble on every pixel, never sparse specks)."""
    def __init__(self, amp=6.0):
        rng = np.random.default_rng(11)
        self.n = [(rng.standard_normal((PW, PH)) * amp).astype(np.int16) for _ in range(4)]
        dx = (np.arange(PW) - PW / 2) / (PW / 2)
        dy = (np.arange(PH) - PH / 2) / (PH / 2)
        v = np.clip(dx[:, None] ** 2 * 0.5 + dy[None, :] ** 2 * 0.65 - 0.22, 0, 1) * 0.72
        self.vig = (256 * (1 - v)).astype(np.int32)

    def apply(self, surf, n, grain=1.0):
        a = pygame.surfarray.pixels3d(surf)
        f = (a.astype(np.int32) * self.vig[..., None]) >> 8
        if grain > 0:
            f += (self.n[n % 4] * grain).astype(np.int32)[..., None]
        np.clip(f, 0, 255, out=f)
        a[...] = f
        del a


def gl_renderer(fog, f0, f1, light):
    import engine3d
    r = engine3d.Renderer(PW, PH, fog=fog, fog_start=f0, fog_end=f1)
    r.light = light
    return r


def dyn(r, verts, faces):
    """Queue a world-space mesh (Mesh face tuples) on the dynamic pass."""
    r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in faces])


def vgrad(top, bot, w=PW, h=PH):
    s = pygame.Surface((w, h))
    for y in range(h):
        pygame.draw.line(s, C.vlerp(top, bot, y / (h - 1)), (0, y), (w, y))
    return s


class Shot:
    letterbox = True
    grain = 1.0
    cap = None          # (head, sub, t_in, t_out) on the local clock
    line = None         # (text, t_in, t_out)
    fade = None         # (in, out) seconds of dip to black at the shot's ends

    def __init__(self, a, b, **kw):
        self.start, self.end, self.ready = a, b, False
        self.__dict__.update(kw)

    def ensure(self):
        if not self.ready:
            self.setup()
            self.ready = True

    def setup(self):
        pass

    def picture(self, lt, T, n):
        raise NotImplementedError

    def overlay(self, cv, lt, T):
        if self.cap:
            caption(cv, *self.cap, lt)
        if self.line:
            tag(cv, *self.line, lt)


# ═══ 0. BOOT ═════════════════════════════════════════════════════════════
BOOT = [(0.45, "RPE6 // RETARDOVICI PULSE ENGINE 6 GOLD", ORANGE),
        (1.35, "renderer ........ OpenGL, software fallback", DIM),
        (1.95, "characters ...... box rigs, two-bone IK", DIM),
        (2.55, "atmosphere ...... weather3d, post3d", DIM),
        (3.15, "sequencing ...... timelines, dialogue graphs, levels", DIM),
        (3.85, "mounting ........ CALL OF ACARISTAN", INK)]
BOOT_CPS = 46
BOOT_OK = 4.75


def boot_ticks():
    out = []
    for t0, txt, _c in BOOT:
        out += [t0 + i / BOOT_CPS for i in range(len(txt)) if txt[i] != " "]
    return out


class Boot(Shot):
    letterbox = False
    grain = 0.0

    def setup(self):
        self.black = pygame.Surface((PW, PH))
        self.scan = pygame.Surface((OUT_W, OUT_H), pygame.SRCALPHA)
        for y in range(0, OUT_H, 3):
            pygame.draw.line(self.scan, (0, 0, 0, 70), (0, y), (OUT_W, y))

    def picture(self, lt, T, n):
        return self.black

    def overlay(self, cv, lt, T):
        f = C.font("mono", 34)
        x, y0 = 300, 300
        k = 1.0 - smooth(seg(lt, 5.5, 5.95))
        for i, (t0, txt, col) in enumerate(BOOT):
            s = C.typed(txt, lt - t0, BOOT_CPS)
            if not s:
                continue
            if len(s) < len(txt) and int(lt * 8) % 2:
                s += "_"
            img = f.render(s, True, col)
            img.set_alpha(int(255 * k))
            cv.blit(img, (x, y0 + i * 52 + (14 if i else 0)))
        if lt > BOOT_OK:
            ok = f.render("[ OK ]" + (" _" if int(lt * 4) % 2 else ""), True, ORANGE)
            ok.set_alpha(int(255 * k))
            cv.blit(ok, (x, y0 + len(BOOT) * 52 + 30))
        if 5.3 < lt < 5.95:                      # the signal tears before the hit
            rng = random.Random(int(lt * 60))
            for _ in range(7):
                y = rng.randrange(y0 - 20, y0 + 380)
                h = rng.randrange(6, 30)
                strip = cv.subsurface((0, y, OUT_W, h)).copy()
                cv.blit(strip, (rng.randrange(-60, 60), y))
        cv.blit(self.scan, (0, 0))


# ═══ 1. VOXEL LOGO ═══════════════════════════════════════════════════════
FONT5 = {
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
}
VOX = 0.22
VOX_COLS = {"front": (232, 228, 220), "top": (255, 150, 58), "bottom": (110, 44, 10),
            "left": (255, 122, 26), "right": (255, 122, 26), "back": (60, 30, 12)}


class VoxelLogo(Shot):
    """RPE6 in 0.22 m boxes: they fly in from depth on the hit, a key light
    sweeps the faces, the camera drifts."""
    def setup(self):
        from engine3d import box
        self.r = gl_renderer((0, 0, 0), 9.0, 30.0, C.light((0.25, 0.45, -0.85), 0.24, 0.6, sky=0.0))
        rng = random.Random(6)
        self.vox = []
        col0 = 0
        for ch in "RPE6":
            for row, bits in enumerate(FONT5[ch]):
                for c, b in enumerate(bits):
                    if b == "1":
                        self.vox.append([(col0 + c) * VOX, (6 - row) * VOX, rng.uniform(0.0, 0.5),
                                         rng.uniform(5.0, 12.0), rng.uniform(-1.0, 1.0)])
            col0 += 6
        cx = (col0 - 2) * VOX / 2
        for v in self.vox:
            v[0] -= cx
            v[1] += 0.55
        self.cube = box(VOX * 0.94, VOX * 0.94, VOX * 0.94, (90, 90, 96), cols=VOX_COLS)
        from engine3d.core import Mesh
        from engine3d import quad_xz
        floor = Mesh()
        for i in range(-12, 13):                     # a faint emissive floor grid
            floor.add(quad_xz(i * 0.8 - 0.012, -2.0, i * 0.8 + 0.012, 30.0, 0.0, (52, 26, 10),
                              emissive=True))
        for j in range(0, 38):
            z = -2.0 + j * 0.8
            floor.add(quad_xz(-9.6, z - 0.012, 9.6, z + 0.012, 0.0, (52, 26, 10), emissive=True))
        self.r.bake(floor)
        self.sky = vgrad((0, 0, 0), (10, 6, 4))

    def picture(self, lt, T, n):
        from engine3d.core import Mesh
        from engine3d import rot_y, rot_x, m_mul
        r = self.r
        u = smooth(lt / (self.end - self.start))
        r.set_camera((lerp(-1.5, 1.1, u), lerp(1.05, 1.35, u), lerp(-6.6, -5.9, u)),
                     (0.0, 1.2, 0.0), 60)
        m = Mesh()
        for x, y, delay, dist, spin in self.vox:
            k = ease_out(clamp((lt - delay) / 0.55))
            if k <= 0:
                continue
            a = (1 - k) * 220.0 * spin
            m.add(self.cube, m=m_mul(rot_y(a), rot_x(a * 0.6)),
                  t=(x * (1 + 0.6 * (1 - k)), y + (1 - k) * spin * 1.4, (1 - k) * dist))
        r.surface.blit(self.sky, (0, 0))
        r.begin()
        r.add_static()
        dyn(r, m.verts, m.faces)
        lx = lerp(-3.4, 3.4, smooth(seg(lt, 0.5, 3.8)))
        r.set_lights([{"pos": (lx, 1.9, -1.0), "color": (255, 232, 200), "intensity": 1.7, "range": 3.6},
                      {"pos": (0.0, 0.25, -1.6), "color": (255, 122, 26), "intensity": 0.9, "range": 4.5}])
        r.flush(r.surface)
        return r.surface

    def overlay(self, cv, lt, T):
        k = fade_in_out(lt, 0.8, 4.4, 0.6, 0.4)
        if k > 0:
            s = spaced("RETARDOVICI PULSE ENGINE 6 GOLD", C.font("mono", 30), INK, 9)
            s.set_alpha(int(255 * k))
            cv.blit(s, (OUT_W // 2 - s.get_width() // 2, BAR + PH - 150))


# ═══ 2. ASSEMBLY ═════════════════════════════════════════════════════════
# rig slot -> landing time (local s); legs up, torso on the 12.55 hit, the
# head on the 14.0 hit, the rifle last
LAND = {9: 0.60, 15: 0.75, 8: 0.95, 14: 1.10, 7: 1.30, 13: 1.45, 0: 1.65,
        1: 1.90, 17: 1.90, 19: 1.90, 20: 1.90, 4: 2.30, 5: 2.30, 10: 2.45, 6: 2.65, 12: 2.80,
        2: 3.35, 3: 3.35, 18: 3.35, 16: 4.75}
DROP = 0.42


class Assembly(Shot):
    cap = ("BUILT FROM BOXES", "every character is a hand-made box rig", 0.5, 7.5)

    def setup(self):
        from cutscenes.cast3d import humanoid3d
        from engine3d import disc_xz, box, rot_y, m_mul
        from engine3d.core import Mesh
        self.lt = 0.0
        self.sparks = []
        self.h = humanoid3d("biribel")
        real = self.h.pose_world

        def pose_world(pose, pos, yaw, rifle_on=True):
            places, joints, root = real(pose, pos, yaw, rifle_on=rifle_on)
            out, self.sparks = [], []
            for slot, key, M, org, g, fb in places:
                t = LAND.get(slot, 1.9)
                u = (self.lt - (t - DROP)) / DROP
                if u <= 0:
                    continue
                dy = 0.0
                if u < 1:
                    dy = 1.8 * (1 - u * u)
                    M = m_mul(rot_y((1 - u) * 150.0 * (1 if slot % 2 else -1)), M)
                elif self.lt - t < 0.3:
                    if key in ("torso", "head", "thigh", "foot", "rifle", "farm"):
                        self.sparks.append(((root[0] + org[0], root[1] + org[1], root[2] + org[2]),
                                            self.lt - t))
                out.append((slot, key, M, (org[0], org[1] + dy, org[2]), g, fb))
            return out, joints, root
        self.h.pose_world = pose_world
        self.r = gl_renderer((3, 3, 5), 6.0, 20.0,
                             C.light((-0.4, 0.8, -0.5), 0.2, 0.5, sky=0.05, tint=(0.92, 0.96, 1.08)))
        stage = Mesh()
        stage.add(disc_xz(0, 0, 2.3, 0.0, (34, 34, 38), n=48))
        for i in range(48):                          # the turntable rim
            a = 2 * math.pi * i / 48
            stage.add(box(0.05, 0.012, 0.32, (255, 122, 26), emissive=True),
                      m=rot_y(-math.degrees(a)), t=(2.3 * math.cos(a), 0.006, 2.3 * math.sin(a)))
        self.r.bake(stage)
        self.sky = vgrad((2, 2, 3), (12, 12, 16))

    def picture(self, lt, T, n):
        from engine3d import blend
        self.lt = lt
        r = self.r
        D = self.end - self.start
        pose = blend("stand", "ready", smooth(seg(lt, 4.0, 4.6)))
        pose["spine"] = pose.get("spine", 0.0) + 1.2 * math.sin(lt * 2.1)
        pose["head_p"] = pose.get("head_p", 0.0) - 6.0 * smooth(seg(lt, 5.4, 6.4))
        a = math.radians(lerp(-40.0, 26.0, smooth(lt / D)))
        R = lerp(5.2, 3.3, smooth(seg(lt, 3.2, D)))
        tgt = (0.0, lerp(0.75, 1.2, smooth(lt / D)), 0.0)
        r.set_camera((math.sin(a) * R, lerp(0.5, 1.4, smooth(lt / D)), -math.cos(a) * R), tgt, 60)
        r.surface.blit(self.sky, (0, 0))
        r.begin()
        r.add_static()
        r.add_humanoid(self.h, pose, (0.0, 0.0, 0.0), 180.0, rifle_on=True)
        for p, age in self.sparks:
            s = 1.0 - age / 0.3
            r.add_sprite(p, C.glow_sprite(0.22 * s + 0.05, (int(255 * s), int(130 * s), int(40 * s))))
        r.set_lights([{"pos": (0.4, 3.4, -1.3), "color": (255, 222, 186), "intensity": 1.5, "range": 6.5},
                      {"pos": (-1.3, 2.0, 1.9), "color": (110, 150, 255), "intensity": 1.4, "range": 5.5}])
        r.flush(r.surface)
        return r.surface


# ═══ 3. THE LIVE GAME (M6 yard / train) ══════════════════════════════════
class Keys:
    def __init__(self, *codes):
        self.c = set(codes)

    def __getitem__(self, k):
        return k in self.c


_GAME = {"mode": None, "surf": None}


def game(mode):
    """Bring up the M6 scene a shot needs ('yard' or 'train')."""
    from core.state import STATE
    from missions import m6
    from missions.m6 import flow, train3d as T
    if _GAME["surf"] is None:
        # the GL pass renders straight at the picture size; the game's
        # 1000x700 output (and its HUD) is never used
        T.RW, T.RH = PW, PH
        T._cache["r"] = None
        _GAME["surf"] = pygame.Surface((T.WIDTH, T.HEIGHT))
    if _GAME["mode"] == mode:
        return
    T.reset()
    m6.start_mission6_train_checkpoint()
    if STATE.player is not None:
        STATE.player.max_hp = STATE.player.hp = 100000
    if mode == "yard":
        T.reset()
        STATE.m6_train_active = False
        flow._enter_yard()
    _GAME["mode"] = mode


def look(eye, tgt):
    """(yaw, pitch) in the M6 convention (T._forward) from eye to tgt."""
    d = (tgt[0] - eye[0], tgt[1] - eye[1], tgt[2] - eye[2])
    return (math.degrees(math.atan2(d[0], -d[2])),
            math.degrees(math.atan2(d[1], math.hypot(d[0], d[2]))))


GAME_FOV = 1.22


class YardShot(Shot):
    preroll = 1.2
    pos = None
    yaw = None
    wave = None
    rate = 0.18                     # auto-aim catch-up per 60 Hz step

    def setup(self):
        self.disp = None

    def speed(self, lt):
        return 1.0

    def stage(self, sc):
        pass

    def drive(self, sc, lt):
        return Keys()

    def cam(self, sc, lt):
        # the game's own camera, widened: its fov is horizontal, and at
        # 2.39:1 the stock angle would crop the frame to his shoulders
        eye, tgt, fov, d = type(sc).camera(sc)
        return eye, tgt, fov * GAME_FOV, d

    # helpers for drive()
    def basis(self, sc):
        from missions.m6 import train3d as T
        f = T._forward(sc.yaw, 0.0)
        rr = T._right(sc.yaw)
        return f, (-rr[0], -rr[1], -rr[2])     # screen right is -T._right

    def head(self, sc):
        x, y, z = sc.pos
        return (x, y + 1.6, z)

    def target(self, sc):
        best, bd = None, 1e9
        f, _ = self.basis(sc)
        for g in sc.guards:
            if not g.get("alive"):
                continue
            p = g["pos"]
            dx, dz = p[0] - sc.pos[0], p[2] - sc.pos[2]
            d = math.hypot(dx, dz)
            if d < 1.5 or d > 34:
                continue
            ang = abs(wrap(math.degrees(math.atan2(dx, -dz)) - sc.yaw))
            score = ang + d * 0.8
            if score < bd:
                best, bd = g, score
        return best

    def aim(self, sc, g, rate=None):
        if g is None:
            return
        p = g["pos"]
        low = g.get("stance") in ("crouch", "cover") or g.get("pose") in ("crouch", "cover")
        eye = type(sc).camera(sc)[0]
        yaw, pitch = look(eye, (p[0], p[1] + (0.95 if low else 1.2), p[2]))
        k = self.rate if rate is None else rate
        sc.yaw += wrap(yaw - sc.yaw) * k
        sc.pitch += (pitch - sc.pitch) * k

    # sim
    def reset(self):
        from missions.m6 import yard3d as Y
        game("yard")
        self.Y = Y
        sc = self.sc = Y.scene()
        sc.restart()
        sc._draw_hud = lambda surface: None
        sc._draw_volkov = lambda r, t: None
        sc.guards, sc.pending = [], []
        if self.wave is None:            # a quiet shot: no wave ever starts
            sc._update_waves = lambda: None
        elif "_update_waves" in sc.__dict__:
            del sc._update_waves
        if self.pos is not None:
            sc.pos = self.pos
        if self.yaw is not None:
            sc.yaw = self.yaw
        if self.wave is not None:
            sc._start_wave(self.wave)
        self.stage(sc)
        self.last_fire = sc.last_fire
        self.hp = {}
        self.disp = -self.preroll
        while self.disp < -1e-9:
            self.tick()

    def tick(self):
        from core.state import STATE
        sc, lt = self.sc, self.disp
        keys = self.drive(sc, lt)
        STATE.dt = self.speed(lt) / 60.0
        self.Y.update(keys)
        if STATE.player is not None:
            STATE.player.hp = STATE.player.max_hp
        if lt >= 0:
            if sc.last_fire != self.last_fire:
                EVENTS.append((self.start + lt, "shot" if self.speed(lt) >= 1 else "shot_slow"))
            for g in sc.guards:
                k = id(g)
                if k in self.hp and g.get("hp", 0) < self.hp[k]:
                    EVENTS.append((self.start + lt, "hit"))
        self.last_fire = sc.last_fire
        self.hp = {id(g): g.get("hp", 0) for g in sc.guards}
        self.disp += 1.0 / 60.0

    def picture(self, lt, T, n):
        from missions.m6 import train3d as TT
        if self.disp is None or lt < self.disp - 0.05:
            self.reset()
        while self.disp <= lt + 1e-9:
            self.tick()
        cam = self.cam(self.sc, lt)
        self.sc.camera = lambda c=cam: c
        try:
            self.Y.draw(_GAME["surf"])
        finally:
            del self.sc.camera
        return TT._renderer().surface


def rel(sc, shot, fwd, right, up):
    f, r = shot.basis(sc)
    x, y, z = sc.pos
    return (x + f[0] * fwd + r[0] * right, y + up, z + f[2] * fwd + r[2] * right)


class Run(YardShot):
    line = ("PROCEDURAL LOCOMOTION", 0.35, 3.2)
    pos, yaw, preroll = (19.0, 0.04, -2.6), -90.0, 0.8

    def drive(self, sc, lt):
        sc.yaw, sc.pitch = -90.0, -4.0
        return Keys(pygame.K_w, pygame.K_LSHIFT)

    def cam(self, sc, lt):
        u = lt / (self.end - self.start)
        eye = rel(sc, self, lerp(1.8, 0.2, u), 4.3, 0.85)
        return eye, rel(sc, self, 0.6, 0.0, 1.0), 62.0, 4.0


class Aim(YardShot):
    cap = ("TWO-BONE IK", "both hands stay on the gun: hip, ADS, strafe, reload", 0.3, 3.0)
    pos, yaw, preroll = (14.0, 0.04, -3.0), -60.0, 1.0

    def drive(self, sc, lt):
        sc.yaw, sc.pitch = -60.0 + 3.0 * lt, -2.0
        sc.aiming = lt >= -0.05
        sc.firing = 1.65 <= lt < 1.95
        sc.mag = 30
        return Keys()

    def cam(self, sc, lt):
        a = lerp(38.0, 62.0, smooth(lt / (self.end - self.start)))
        f, r = self.basis(sc)
        h = self.head(sc)
        R = 2.2
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        eye = (h[0] + (f[0] * ca + r[0] * sa) * R, h[1] + 0.02, h[2] + (f[2] * ca + r[2] * sa) * R)
        tgt = (h[0] + f[0] * 0.35 + r[0] * 0.05, h[1] - 0.1, h[2] + f[2] * 0.35 + r[2] * 0.05)
        return eye, tgt, 58.0, R


class YardWide(YardShot):
    cap = ("LIGHT AND WEATHER", "sodium lamps, torches, falling snow, all in real time", 0.6, 3.3)
    pos, yaw, preroll = (6.0, 0.04, -4.5), -120.0, 1.0

    def drive(self, sc, lt):
        sc.yaw, sc.pitch = -120.0, -8.0
        return Keys(pygame.K_w)

    def cam(self, sc, lt):
        u = smooth(lt / (self.end - self.start))
        x, y, z = sc.pos
        eye = (x + lerp(-9.0, -4.6, u), lerp(8.5, 2.6, u), z + lerp(-11.0, -6.2, u))
        return eye, (x, y + lerp(0.6, 1.1, u), z), 70.0, 10.0


class YardPlay(YardShot):
    line = ("GAMEPLAY // CAPTURED IN-ENGINE", 0.25, 1.85)
    wave, preroll = 0, 1.6

    def stage(self, sc):
        # a third man up the strip as the first two drop, so the shot ends
        # in a fight rather than on the bodies
        sc.pending.append(self.Y._make_guard(0, 3, (
            "rifle", (21.4, 0.04, -9.4), ((19.8, 0.04, -7.7),), "cover", True,
            self.preroll + 1.3), sc.t))

    def drive(self, sc, lt):
        # already on the gun when the shot opens: first burst in a quarter second
        g = self.target(sc)
        sc.mag = 30
        sc.aiming = lt >= -0.4
        sc.firing = g is not None and any(a <= lt < b for a, b in (
            (0.2, 0.5), (0.9, 1.2), (1.65, 1.95), (2.45, 2.75), (3.25, 3.55)))
        self.aim(sc, g, 0.12 if lt < -0.4 else 0.3)
        if lt < -0.4:
            return Keys(pygame.K_w)
        return Keys(pygame.K_a) if lt < 2.2 else Keys(pygame.K_d)


class Combat(YardShot):
    pos, wave, preroll = (16.2, 0.04, -2.8), 1, 3.0
    bursts = ((0.15, 0.55), (1.0, 1.4), (1.95, 2.35), (2.9, 3.35))
    strafe = True

    def stage(self, sc):
        sc.yaw, sc.pitch = look(self.head(sc), (21.5, 1.0, 3.5))

    def drive(self, sc, lt):
        sc.mag = 30
        sc.aiming = True
        sc.firing = any(a <= lt < b for a, b in self.bursts)
        self.aim(sc, self.target(sc))
        if not self.strafe:
            return Keys()
        return Keys(pygame.K_d) if lt < 1.8 else Keys(pygame.K_a)


class Reload(YardShot):
    pos, preroll = (16.2, 0.04, -2.8), 0.6

    def stage(self, sc):
        sc.yaw, sc.pitch = look(self.head(sc), (21.5, 1.0, 3.5))
        sc.mag = 0

    def drive(self, sc, lt):
        if -0.02 < lt <= 0.0 and not sc.reloading:
            sc.mag = 5
            sc._begin_reload()
        return Keys()

    def cam(self, sc, lt):
        u = smooth(lt / (self.end - self.start))
        eye = rel(sc, self, lerp(2.7, 2.2, u), lerp(-1.5, -0.8, u), 0.7)
        return eye, rel(sc, self, 0.3, 0.1, 1.2), 58.0, 2.5


class FireLow(Combat):
    """Low in front of the muzzle, looking back up at him through the bursts."""
    bursts = ((0.0, 0.5), (0.8, 1.3), (1.6, 2.2))
    strafe = False

    def cam(self, sc, lt):
        u = smooth(lt / (self.end - self.start))
        eye = rel(sc, self, lerp(3.4, 2.8, u), lerp(-1.6, -1.1, u), 0.45)
        return eye, rel(sc, self, 0.4, 0.0, 1.3), 62.0, 3.0


class SlowMo(Combat):
    bursts = ((0.05, 0.08), (0.95, 0.98))
    strafe = False

    def speed(self, lt):
        return 0.2 if lt >= 0 else 1.0

    def cam(self, sc, lt):
        u = smooth(lt / (self.end - self.start))
        eye = rel(sc, self, lerp(0.3, 0.7, u), 1.7, 1.45)
        return eye, rel(sc, self, 0.5, 0.0, 1.35), 54.0, 1.7


class Breath(YardShot):
    """The quiet before the title: close on his face in the snow, he looks up."""
    pos, yaw, preroll = (8.0, 0.04, -9.6), 0.0, 1.2
    fade = (0.5, 0.35)

    def drive(self, sc, lt):
        sc.yaw = 0.0
        sc.pitch = lerp(-12.0, 14.0, smooth(seg(lt, 1.1, 2.2)))
        return Keys()

    def cam(self, sc, lt):
        u = smooth(lt / (self.end - self.start))
        x, y, z = sc.pos
        h = (x, y + 1.72, z)
        f, r = self.basis(sc)
        R = lerp(1.3, 1.0, u)
        eye = (h[0] + f[0] * R + r[0] * 0.2, h[1] + 0.02, h[2] + f[2] * R + r[2] * 0.2)
        return eye, (h[0], h[1] + 0.03, h[2]), 50.0, R


class TrainFP(Shot):
    """The M6 train fight, first person, guards on the platform."""
    line = ("FIRST PERSON // THE SAME ENGINE", 0.3, 3.2)
    clock = 9.0

    def setup(self):
        self.disp = None

    def reset(self):
        from missions.m6 import train3d as T
        game("train")
        self.T = T
        self.sc = T.scene()
        self.flash = self.sc.flash_t
        STEP = 1.0 / 60.0
        from core.state import STATE
        while self.sc.t < self.clock:
            STATE.dt = STEP
            T.update(None, (T.WIDTH // 2, T.HEIGHT // 2))
        self.ay, self.ap = self.sc.yaw, self.sc.pitch
        self.disp = 0.0

    def track(self):
        """(yaw, pitch) onto the living guard nearest the sight, inside the
        train's aim arc; None if nobody is up."""
        TT, sc = self.T, self.sc
        eye = sc._eye()[0]
        best, bd = None, 1e9
        for g in sc.guards:
            if not (g.get("alive") and g.get("active", True)):
                continue
            p = g["pos"]
            yaw, pitch = look(eye, (p[0], p[1] + 1.15, p[2]))
            if abs(wrap(yaw - TT.BASE_YAW)) > TT.YAW_LIMIT * 0.92:
                continue
            if abs(pitch - TT.BASE_PITCH) > TT.PITCH_LIMIT * 0.92:
                continue
            d = abs(wrap(yaw - self.ay)) + abs(pitch - self.ap)
            if d < bd:
                best, bd = (yaw, pitch), d
        return best

    def picture(self, lt, T, n):
        from core.state import STATE
        if self.disp is None or lt < self.disp - 0.05:
            self.reset()
        sc, TT = self.sc, self.T
        while self.disp <= lt + 1e-9:
            sc.aiming = self.disp > 0.15
            want = self.track()
            sc.firing = False
            if want is not None:
                # a player's hand: ease the sight onto the man, then a burst
                self.ay += wrap(want[0] - self.ay) * 0.16
                self.ap += (want[1] - self.ap) * 0.16
                on = abs(wrap(want[0] - sc.yaw)) < 1.4 and abs(want[1] - sc.pitch) < 1.4
                sc.firing = on and self.disp > 0.35 and (self.disp % 0.62) < 0.34
            sens = 1.0 - 0.22 * sc.ads
            mx = TT.WIDTH / 2 - (self.ay - TT.BASE_YAW) / (TT.YAW_LIMIT * sens) * (TT.WIDTH * 0.5)
            my = TT.HEIGHT / 2 - (self.ap - TT.BASE_PITCH) / (TT.PITCH_LIMIT * sens) * (TT.HEIGHT * 0.5)
            STATE.dt = 1.0 / 60.0
            hp = {id(g): g.get("hp", 0) for g in sc.guards}
            TT.update(None, (mx, my))
            if STATE.player is not None:
                STATE.player.hp = STATE.player.max_hp
            if sc.flash_t != self.flash:
                self.flash = sc.flash_t
                EVENTS.append((self.start + self.disp, "shot"))
            if any(g.get("hp", 0) < hp.get(id(g), 0) for g in sc.guards):
                EVENTS.append((self.start + self.disp, "hit"))
            self.disp += 1.0 / 60.0
        self.T.draw(_GAME["surf"])
        return self.T._renderer().surface


# ═══ 4. WORLDS FROM THE STORY TRAILER ═══════════════════════════════════
_LEGACY = {}


def legacy(name):
    """The story trailer's shot instance (its own clock), built once."""
    if not _LEGACY:
        import shots
        with open(os.path.join(ROOT, "tools", "trailer3d", "timeline.json"), encoding="utf-8") as fh:
            marks = json.load(fh)["marks"]
        for s in shots.build_timeline(marks):
            _LEGACY.setdefault(type(s).__name__, s)
        _LEGACY["_grade"] = C.Grade()
    return _LEGACY[name]


class World(Shot):
    """A world rendered by tools/trailer3d at its 640x268 PS1 chunk, text off."""
    grain = 0.0
    name, skip = "Ocean", 0.0

    def picture(self, lt, T, n):
        s = legacy(self.name)
        s.ensure()
        t = lt + self.skip
        surf = s.render(t, s.start + t, n)
        legacy("_grade").apply(surf, n, grain=s.grain)
        return surf


# ═══ 5. K93D TURNTABLE ═══════════════════════════════════════════════════
class K9Turn(Shot):
    cap = ("MESH IMPORT", "authored assets and procedural sets, one renderer", 0.3, 2.4)

    def setup(self):
        from missions.m6 import yard3d as Y
        self.mesh, _muzzle = Y._k9_asset()
        self.r = gl_renderer((0, 0, 0), 3.0, 9.0, C.light((-0.3, 0.7, -0.6), 0.22, 0.65, sky=0.0))
        self.sky = vgrad((4, 4, 6), (18, 14, 12))

    def picture(self, lt, T, n):
        from engine3d import rot_y, rot_z, m_apply, m_mul
        r = self.r
        D = self.end - self.start
        M = m_mul(rot_y(lerp(-60.0, 50.0, lt / D)), rot_z(4.0))
        w = [m_apply(M, v) for v in self.mesh.verts]
        r.set_camera((0.0, 0.12, -lerp(1.45, 1.2, smooth(lt / D))), (0.0, 0.0, 0.05), 58)
        r.surface.blit(self.sky, (0, 0))
        r.begin()
        dyn(r, w, self.mesh.faces)
        lx = lerp(-1.4, 1.4, smooth(seg(lt, 0.2, D)))
        r.set_lights([{"pos": (lx, 0.5, -0.7), "color": (255, 230, 200), "intensity": 1.6, "range": 2.4},
                      {"pos": (0.0, -0.3, 0.8), "color": (255, 122, 26), "intensity": 1.0, "range": 2.0}])
        r.flush(r.surface)
        return r.surface


# ═══ 6. TITLE + POWERED BY ══════════════════════════════════════════════
class Title(Shot):
    letterbox = False
    grain = 0.0
    END_AT = 4.7                    # local: title -> "powered by" crossfade

    def setup(self):
        rng = random.Random(9)
        self.embers = [(rng.uniform(0, OUT_W), rng.uniform(40, 160), rng.uniform(0, 6.3),
                        rng.uniform(2.5, 7.0), rng.uniform(0, OUT_H)) for _ in range(150)]
        self.bg = vgrad((6, 6, 8), (22, 13, 9), OUT_W, OUT_H)
        glow = pygame.Surface((OUT_W, OUT_H))
        C.glow(glow, OUT_W // 2, OUT_H + 160, 880, (70, 30, 10))
        self.bg.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        f = C.font("oswald", 168)
        self.title = spaced("CALL OF ACARISTAN", f, (255, 255, 255), 16)
        grad = vgrad((250, 246, 238), (150, 140, 128), *self.title.get_size())
        tinted = self.title.copy()
        tinted.blit(grad, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        self.metal = tinted
        self.pic = pygame.Surface((PW, PH))

    def picture(self, lt, T, n):
        return self.pic

    def overlay(self, cv, lt, T):
        cv.blit(self.bg, (0, 0))
        for x0, sp, ph, sz, y0 in self.embers:
            y = OUT_H + 20 - (y0 + lt * sp) % (OUT_H + 60)
            x = x0 + 28 * math.sin(lt * 0.9 + ph)
            fl = 0.55 + 0.45 * math.sin(lt * 7 + ph * 3)
            C.glow(cv, x, y, sz * 2.2, (int(200 * fl), int(80 * fl), int(20 * fl)))
        k_title = clamp(lt / 0.12) * (1 - smooth(seg(lt, self.END_AT - 0.4, self.END_AT + 0.2)))
        if k_title > 0:
            sc = 1.0 + 0.05 * (1 - ease_out(clamp(lt / 1.6)))
            img = self.metal
            if sc != 1.0:
                img = pygame.transform.smoothscale(img, (int(img.get_width() * sc), int(img.get_height() * sc)))
            img = img.copy()
            u = seg(lt, 0.7, 1.9)                     # one light sweep across the letters
            if 0 < u < 1:
                band = pygame.Surface(img.get_size(), pygame.SRCALPHA)
                bx = int(lerp(-300, img.get_width() + 300, smooth(u)))
                pygame.draw.polygon(band, (255, 255, 255, 150),
                                    [(bx - 90, 0), (bx + 30, 0), (bx - 30, img.get_height()),
                                     (bx - 150, img.get_height())])
                band.blit(img, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                img.blit(band, (0, 0))
            img.set_alpha(int(255 * k_title))
            cv.blit(img, (OUT_W // 2 - img.get_width() // 2, OUT_H // 2 - img.get_height() // 2 - 40))
            k2 = fade_in_out(lt, 1.6, self.END_AT - 0.3, 0.6, 0.4)
            if k2 > 0:
                s = spaced("COMING SOON", C.font("mono", 30), ORANGE, 14)
                s.set_alpha(int(255 * k2))
                cv.blit(s, (OUT_W // 2 - s.get_width() // 2, OUT_H // 2 + 110))
        lt2 = lt - self.END_AT
        if lt2 > 0:
            k = clamp(lt2 / 0.6) * (1 - smooth(seg(lt, self.end - self.start - 0.9,
                                                   self.end - self.start - 0.1)))
            for txt, fnt, col, sp, y in (("POWERED BY", C.font("mono", 26), DIM, 12, OUT_H // 2 - 150),
                                         ("RPE6", C.font("oswald", 190), INK, 18, OUT_H // 2 - 30),
                                         ("RETARDOVICI PULSE ENGINE 6 GOLD", C.font("mono", 30), ORANGE, 9,
                                          OUT_H // 2 + 108)):
                s = spaced(txt, fnt, col, sp)
                s.set_alpha(int(255 * k))
                cv.blit(s, (OUT_W // 2 - s.get_width() // 2, y - s.get_height() // 2))
            s = C.font("mono", 20).render('Music: "Shell Ghost" by Soundridemusic', True, (128, 126, 122))
            s.set_alpha(int(255 * k))
            cv.blit(s, (OUT_W // 2 - s.get_width() // 2, OUT_H - 90))


# ═══ timeline ════════════════════════════════════════════════════════════
def build():
    W_ = World
    return [
        Boot(0.0, 6.0),
        VoxelLogo(6.0, 10.65),
        Assembly(10.65, 18.6),
        Run(18.6, 22.0),
        Aim(22.0, 25.2),
        W_(25.2, 28.45, name="Ocean", skip=5.4,
           cap=("WEATHER3D", "storms, rain and fog from data, per set", 0.3, 2.9)),
        YardWide(28.45, 32.05),
        YardPlay(32.05, 34.11),
        TrainFP(34.11, 39.25),
        Combat(39.25, 43.0),
        Reload(43.0, 45.25),
        W_(45.25, 47.6, name="Route12Aerial", skip=0.8,
           cap=("DATA-DRIVEN LEVELS", ".level.json, Tiled import, validated at build", 0.2, 2.1)),
        W_(47.6, 50.8, name="MartialLaw", skip=2.0,
           cap=("TIMELINE CUTSCENES", "keyed cameras, rigs and lights", 0.2, 2.9)),
        W_(50.8, 52.6, name="Mansion", skip=0.0,
           cap=("ONE SIM, TWO BACKENDS", "OpenGL, or software when there is no GPU", 0.2, 1.6)),
        W_(52.6, 53.95, name="Rooftops", skip=0.0),
        W_(53.95, 55.35, name="Gunship", skip=0.0,
           cap=("DETERMINISTIC", "seeded simulation, replayable runs", 0.1, 1.2)),
        W_(55.35, 57.4, name="Alley", skip=0.0,
           cap=("SAVE, LOAD, SETTINGS", "accessibility options built in", 0.2, 1.8)),
        W_(57.4, 59.3, name="Cockpit", skip=0.0,
           cap=("DIALOGUE GRAPHS", ".dlg.json, walked by the runner", 0.2, 1.7)),
        K9Turn(59.3, 62.0),
        FireLow(62.0, 64.6),
        Combat(64.6, 66.95, bursts=((0.1, 0.5), (0.9, 1.4), (1.7, 2.2)), strafe=False),
        SlowMo(66.95, 68.55),
        Breath(68.55, 71.3),
        Title(71.3, TOTAL),
    ]


class Trailer:
    def __init__(self):
        pygame.init()
        pygame.display.set_mode((64, 64))
        self.shots = build()
        self.grain = Grain()
        self.canvas = pygame.Surface((OUT_W, OUT_H))
        self.pic = pygame.Surface((PW, PH))

    def shot_at(self, T):
        for s in self.shots:
            if s.start <= T < s.end:
                return s
        return self.shots[-1]

    def frame(self, T, n):
        s = self.shot_at(T)
        s.ensure()
        lt = T - s.start
        surf = s.picture(lt, T, n)
        cv = self.canvas
        cv.fill((0, 0, 0))
        if s.letterbox:
            if surf.get_size() == (PW, PH):
                self.pic.blit(surf, (0, 0))
            else:                                   # the 640x268 chunk, x3 nearest
                pygame.transform.scale(surf, (PW, PH), self.pic)
            if s.grain > 0 or surf.get_size() == (PW, PH):
                self.grain.apply(self.pic, n, s.grain)
            if s.fade:
                k = min(clamp(lt / s.fade[0]), clamp((s.end - T) / s.fade[1]))
                if k < 1:
                    v = int(255 * (1 - smooth(k)))
                    self.pic.fill((v, v, v), special_flags=pygame.BLEND_RGB_SUB)
            cv.blit(self.pic, (0, BAR))
        s.overlay(cv, lt, T)
        for t0, amp in FLASH.items():
            d = T - t0
            if 0 <= d < 0.4:
                v = int(255 * amp * math.exp(-d * 11.0))
                cv.fill((v, v, v), special_flags=pygame.BLEND_RGB_ADD)
        if T > TOTAL - 0.8:
            v = int(255 * smooth((T - (TOTAL - 0.8)) / 0.8))
            cv.fill((v, v, v), special_flags=pygame.BLEND_RGB_SUB)
        return cv


def stills(tr, times, out=None):
    d = out or os.path.join(OUT_DIR, "stills")
    os.makedirs(d, exist_ok=True)
    paths = []
    for T in times:
        t0 = time.time()
        cv = tr.frame(T, int(T * FPS))
        p = os.path.join(d, "T%05.2f_%s.png" % (T, type(tr.shot_at(T)).__name__))
        pygame.image.save(cv, p)
        paths.append(p)
        print("%-40s %.2fs" % (os.path.basename(p), time.time() - t0), flush=True)
    return paths


def sheet(paths, out, cols=4, w=480):
    h = w * OUT_H // OUT_W
    rows = (len(paths) + cols - 1) // cols
    s = pygame.Surface((cols * w, rows * h))
    f = C.font("mono", 16)
    for i, p in enumerate(paths):
        img = pygame.transform.smoothscale(pygame.image.load(p), (w, h))
        img.blit(f.render(os.path.basename(p)[:-4], True, (255, 255, 0)), (6, 4))
        s.blit(img, ((i % cols) * w, (i // cols) * h))
    pygame.image.save(s, out)
    print("->", out)


def video(tr, t0, t1, out, audio=True):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    silent = out if not audio else out[:-4] + "_picture.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
           "%dx%d" % (OUT_W, OUT_H), "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
           "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", silent]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n0, n1 = int(round(t0 * FPS)), int(round(t1 * FPS))
    del EVENTS[:]
    st = time.time()
    for n in range(n0, n1):
        T = (n + 0.5) / FPS
        p.stdin.write(pygame.image.tobytes(tr.frame(T, n), "RGB"))
        if (n - n0) % 90 == 0:
            el = max(time.time() - st, 1e-6)
            done = n - n0 + 1
            print("frame %d/%d  T=%.1f  %.1f fps" % (done, n1 - n0, T, done / el), flush=True)
    p.stdin.close()
    p.wait()
    ev = {"events": sorted(EVENTS), "boot_ticks": boot_ticks(), "boot_ok": BOOT_OK,
          "flash": sorted(FLASH), "music_at": MUSIC_AT, "total": TOTAL,
          "cuts": [s.start for s in tr.shots],
          "lands": [10.65 + t for t in sorted(set(LAND.values()))],
          "quiet": (68.55, 71.3), "powered": 71.3 + Title.END_AT}
    with open(os.path.join(OUT_DIR, "events.json"), "w", encoding="utf-8") as fh:
        json.dump(ev, fh, indent=1)
    print("picture ->", silent, "in %.0fs" % (time.time() - st))
    if audio:
        import score
        wav = score.build(ev, os.path.join(OUT_DIR, "score.wav"))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-ss", "%.3f" % t0, "-i", wav,
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                        "-shortest", "-movflags", "+faststart", out], check=True)
        print("->", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--at", type=float, nargs="*")
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=TOTAL)
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "rpe6_engine_trailer.mp4"))
    ap.add_argument("--noaudio", action="store_true")
    a = ap.parse_args()
    tr = Trailer()
    if a.sheet:
        times = [s.start + (s.end - s.start) * 0.6 for s in tr.shots]
        sheet(stills(tr, times), os.path.join(OUT_DIR, "_sheet.jpg"))
    elif a.at:
        stills(tr, a.at)
    else:
        video(tr, a.t0, a.t1, a.out, audio=not a.noaudio)


if __name__ == "__main__":
    main()
