"""Vertical 1080x1920 cuts of the RPE6 trailer for TikTok / YouTube Shorts.

    python tools/trailer_rpe6/shorts.py --list
    python tools/trailer_rpe6/shorts.py gameplay --at 1 5 12     stills -> outputs/trailer_rpe6/shorts/stills/
    python tools/trailer_rpe6/shorts.py gameplay --sheet         one still per shot + _sheet_<name>.jpg
    python tools/trailer_rpe6/shorts.py gameplay                 MP4 with its own mix
    python tools/trailer_rpe6/shorts.py all
    python tools/trailer_rpe6/shorts.py all --thumbs        1080x1920 covers -> shorts/cover_<name>.png

Not a crop of the 16:9 film: every frame is rendered again by the engine at
portrait size, with the same shot classes as render.py.  The engine's fov is
horizontal, so each landscape camera's angle is remapped for a 9:16 frame
(`pz` per shot widens it).  Text keeps to the middle of the frame, clear of
the platform UI (caption and buttons on the bottom ~22% and the right edge).
Each short cuts to a window of "Shell Ghost" so its hits land where the
trailer's did, with the trailer's sound design from score.py on top.
"""
import argparse
import math
import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render as R  # noqa: E402

W, H = 1080, 1920
R.PW, R.PH, R.OUT_W, R.OUT_H, R.BAR = W, H, W, H, 0
R.GAME_FOV = 1.0
C, pygame = R.C, R.pygame
clamp, smooth, seg, lerp, ease_out = R.clamp, R.smooth, R.seg, R.lerp, R.ease_out
ORANGE, INK, DIM = R.ORANGE, R.INK, R.DIM
OUT = os.path.join(R.OUT_DIR, "shorts")
FPS = R.FPS
# music clock of the trailer's big hits (trailer time - MUSIC_AT)
HIT = {t: round(t - R.MUSIC_AT, 3) for t in (6.0, 14.0, 45.25, 62.0, 71.3)}

# ── portrait fov ─────────────────────────────────────────────────────────
PZ = [1.25]


def _portrait_camera():
    """Every renderer's fov is horizontal.  On a portrait target, read the
    shot's landscape fov as the 2.39:1 frame it was framed for and keep its
    vertical angle (x PZ), so the subject sits at the same size across the
    narrow width and the frame gains sky and ground instead of losing him."""
    from engine3d.core import SoftwareRenderer
    if getattr(SoftwareRenderer, "_portrait", False):
        return
    base = SoftwareRenderer.set_camera

    def set_camera(self, pos, target, fov, roll=0.0):
        if self.h > self.w:
            t = math.tan(math.radians(fov) / 2) / 2.39 * PZ[0]
            fov = math.degrees(2 * math.atan(t))
        return base(self, pos, target, fov, roll)
    SoftwareRenderer.set_camera = set_camera
    SoftwareRenderer._portrait = True

    # the game's over-shoulder camera puts him at the left third of a wide
    # frame, which a 9:16 frame cuts in half: slide eye and target toward
    # his shoulder (`shift` m) so he stands in the frame with the fight beside him
    game_cam = R.YardShot.cam

    def cam(self, sc, lt):
        eye, tgt, fov, d = game_cam(self, sc, lt)
        k = getattr(self, "shift", 0.0)
        _, r = self.basis(sc)
        return ((eye[0] - r[0] * k, eye[1], eye[2] - r[2] * k),
                (tgt[0] - r[0] * k, tgt[1], tgt[2] - r[2] * k), fov, d)
    R.YardShot.cam = cam


# ── text, centred and inside the safe area ──────────────────────────────
def _fit(img, maxw):
    if img.get_width() <= maxw:
        return img
    k = maxw / img.get_width()
    return pygame.transform.smoothscale(img, (int(img.get_width() * k), int(img.get_height() * k)))


def _shadowed(img, cv, pos, alpha):
    sh = img.copy()
    sh.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MIN)
    sh.set_alpha(int(150 * alpha))
    for d in ((3, 4), (0, 5), (5, 2)):
        cv.blit(sh, (pos[0] + d[0], pos[1] + d[1]))
    img.set_alpha(int(255 * alpha))
    cv.blit(img, pos)


def hook(cv, lines, t_in, t_out, lt, y=300, size=104):
    """The first-second line: big, slammed in, a word stack on the top third."""
    k = R.fade_in_out(lt, t_in, t_out, 0.06, 0.25)
    if k <= 0:
        return
    sc = 1.0 + 0.16 * (1 - ease_out(clamp((lt - t_in) / 0.2)))
    for i, (txt, col) in enumerate(lines):
        img = _fit(R.spaced(txt, C.font("oswald", size), col, 4), W - 140)
        if sc != 1.0:
            img = pygame.transform.smoothscale(img, (int(img.get_width() * sc), int(img.get_height() * sc)))
        _shadowed(img, cv, (W // 2 - img.get_width() // 2, y + i * int(size * 1.08)), k)
    yb = y + len(lines) * int(size * 1.08) + 14
    bw = int(120 * k)
    pygame.draw.rect(cv, ORANGE, (W // 2 - bw // 2, yb, bw, 6))


def label(cv, head, sub, t_in, t_out, lt, y=330):
    """The trailer's engine-feature caption, centred for a phone."""
    k = R.fade_in_out(lt, t_in, t_out)
    if k <= 0:
        return
    dy = int(24 * (1 - ease_out(clamp((lt - t_in) / 0.45))))
    lab = R.spaced("RPE6 //", C.font("monob", 28), ORANGE, 3)
    _shadowed(lab, cv, (W // 2 - lab.get_width() // 2, y + dy), k)
    big = _fit(R.spaced(head, C.font("oswald", 78), INK, 3), W - 120)
    _shadowed(big, cv, (W // 2 - big.get_width() // 2, y + 36 + dy), k)
    yb = y + 36 + big.get_height() + 8 + dy
    pygame.draw.rect(cv, ORANGE, (W // 2 - int(40 * k), yb, int(80 * k), 4))
    txt = C.typed(sub, lt - t_in - 0.25, 44)
    if txt:
        img = _fit(C.font("mono", 30).render(txt, True, (226, 222, 212)), W - 120)
        _shadowed(img, cv, (W // 2 - img.get_width() // 2, yb + 18), k)


# ── shots that need a portrait layout ───────────────────────────────────
class Logo(R.VoxelLogo):
    pz = 2.15

    def overlay(self, cv, lt, T):
        k = R.fade_in_out(lt, 0.8, self.end - self.start - 0.1, 0.6, 0.3)
        if k > 0:
            for i, txt in enumerate(("RETARDOVICI PULSE ENGINE", "6  GOLD")):
                s = R.spaced(txt, C.font("mono", 34), INK if i == 0 else ORANGE, 8)
                _shadowed(s, cv, (W // 2 - s.get_width() // 2, 1180 + i * 52), k)


class EndCard(R.Shot):
    """Title, then the engine, on the trailer's ember field, stacked for 9:16."""
    letterbox = False
    grain = 0.0
    swap = 2.3                      # local: title -> "powered by"

    def setup(self):
        rng = random.Random(9)
        self.embers = [(rng.uniform(0, W), rng.uniform(60, 220), rng.uniform(0, 6.3),
                        rng.uniform(3.0, 8.0), rng.uniform(0, H)) for _ in range(140)]
        self.bg = R.vgrad((6, 6, 8), (24, 14, 9), W, H)
        glow = pygame.Surface((W, H))
        C.glow(glow, W // 2, H + 200, 1000, (74, 32, 10))
        self.bg.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        self.lines = []
        for txt, size, sp in (("CALL OF", 120, 22), ("ACARISTAN", 196, 10)):
            t = _fit(R.spaced(txt, C.font("oswald", size), (255, 255, 255), sp), W - 110)
            g = R.vgrad((250, 246, 238), (150, 140, 128), *t.get_size())
            t.blit(g, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
            self.lines.append(t)
        self.pic = pygame.Surface((W, H))

    def picture(self, lt, T, n):
        return self.pic

    def overlay(self, cv, lt, T):
        D = self.end - self.start
        cv.blit(self.bg, (0, 0))
        for x0, sp, ph, sz, y0 in self.embers:
            y = H + 20 - (y0 + lt * sp) % (H + 60)
            x = x0 + 30 * math.sin(lt * 0.9 + ph)
            fl = 0.55 + 0.45 * math.sin(lt * 7 + ph * 3)
            C.glow(cv, x, y, sz * 2.2, (int(200 * fl), int(80 * fl), int(20 * fl)))
        out = 1 - smooth(seg(lt, D - 0.7, D - 0.05))
        k = clamp(lt / 0.12) * out
        sc = 1.0 + 0.05 * (1 - ease_out(clamp(lt / 1.6)))
        y = 560
        for i, img in enumerate(self.lines):
            if sc != 1.0:
                img = pygame.transform.smoothscale(img, (int(img.get_width() * sc), int(img.get_height() * sc)))
            img = img.copy()
            u = seg(lt, 0.4 + 0.15 * i, 1.5 + 0.15 * i)
            if 0 < u < 1:                            # one light sweep across the letters
                band = pygame.Surface(img.get_size(), pygame.SRCALPHA)
                bx = int(lerp(-300, img.get_width() + 300, smooth(u)))
                pygame.draw.polygon(band, (255, 255, 255, 150),
                                    [(bx - 90, 0), (bx + 30, 0), (bx - 30, img.get_height()),
                                     (bx - 150, img.get_height())])
                band.blit(img, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                img.blit(band, (0, 0))
            img.set_alpha(int(255 * k))
            cv.blit(img, (W // 2 - img.get_width() // 2, y))
            y += img.get_height() - 6
        k2 = R.fade_in_out(lt, 0.9, D, 0.5, 0.7)
        if k2 > 0:
            s = R.spaced("COMING SOON", C.font("mono", 40), ORANGE, 14)
            s.set_alpha(int(255 * k2))
            cv.blit(s, (W // 2 - s.get_width() // 2, y + 40))
        k3 = clamp((lt - self.swap) / 0.5) * out
        if k3 > 0:
            yy = y + 190
            for txt, fnt, col, spc in (("POWERED BY", C.font("mono", 28), DIM, 12),
                                       ("RPE6", C.font("oswald", 120), INK, 14),
                                       ("RETARDOVICI PULSE ENGINE 6 GOLD", C.font("mono", 28), ORANGE, 4)):
                s = _fit(R.spaced(txt, fnt, col, spc), W - 140)
                s.set_alpha(int(255 * k3))
                cv.blit(s, (W // 2 - s.get_width() // 2, yy))
                yy += s.get_height() + 6
            s = C.font("mono", 22).render('Music: "Shell Ghost" by Soundridemusic', True, (128, 126, 122))
            s.set_alpha(int(255 * k3))
            cv.blit(s, (W // 2 - s.get_width() // 2, yy + 30))


# ── the three shorts ────────────────────────────────────────────────────
NOTXT = {"cap": None, "line": None}
SAME = ((0.15, 0.55), (1.0, 1.4), (1.95, 2.35))     # one fight, played back three times


class Short:
    """shots, text cues, white flashes and the music windows for one cut.
    music: (short time, music time, length) pieces, crossfaded on the joins."""
    def __init__(self, name, title, shots, texts, flash, music, end):
        self.name, self.title, self.shots = name, title, shots
        self.texts, self.flash, self.music, self.total = texts, flash, music, end


def shorts():
    S = {}
    # 1. GAMEPLAY: the fight from the trailer's back half, the music from
    # its 45.25 hit to the title (26.05 s), the title hit on the end card
    t = HIT[71.3] - HIT[45.25]
    S["gameplay"] = Short("gameplay", "100% in-engine gameplay", [
        R.YardPlay(0.0, 2.6, pz=1.6, shift=0.24, **NOTXT),
        R.TrainFP(2.6, 7.4, pz=1.0, **NOTXT),
        R.Combat(7.4, 10.9, pz=1.6, shift=0.24),
        R.Reload(10.9, 13.3, pz=1.15),
        R.Aim(13.3, 16.75, pz=1.1, **NOTXT),
        R.FireLow(16.75, 19.35, pz=1.2),
        R.Combat(19.35, 21.7, bursts=((0.1, 0.5), (0.9, 1.4), (1.7, 2.2)), strafe=False, pz=1.6, shift=0.24),
        R.SlowMo(21.7, 23.3, pz=1.15),
        R.Breath(23.3, t, pz=1.1),
        EndCard(t, t + 5.2),
    ], [
        ("hook", [("100% IN-ENGINE", INK), ("GAMEPLAY", ORANGE)], 0.0, 2.4),
        ("label", "FIRST PERSON", "the same engine, the same sim", 2.9, 6.9),
        ("label", "TWO-BONE IK", "both hands stay on the gun", 13.6, 16.5),
        ("label", "SLOW MOTION", "the sim, stepped at 0.2x", 21.75, 23.2),
    ], {0.0: 0.6, HIT[62.0] - HIT[45.25]: 0.55, t: 0.85},
        [(0.0, HIT[45.25], t + 5.2)], t + 5.2)

    # 2. ENGINE: the voxel logo on the first hit, the rig built box by box
    # (its head lands on the 14.0 hit), the K9 mesh, light, first person,
    # then a jump cut in the music to the title hit
    a = HIT[14.0] - HIT[6.0] - 3.35            # Assembly start so the head lands on the hit
    e = 21.4
    S["engine"] = Short("engine", "I built my own game engine", [
        Logo(0.0, a),
        R.Assembly(a, a + 7.0, pz=0.95, **NOTXT),
        R.K9Turn(a + 7.0, a + 9.7, pz=1.6, **NOTXT),
        R.YardWide(a + 9.7, a + 13.0, pz=1.3, **NOTXT),
        R.Run(a + 13.0, e - 2.6, pz=1.3, **NOTXT),
        R.FireLow(e - 2.6, e, pz=1.2),
        EndCard(e, e + 5.2),
    ], [
        ("hook", [("I BUILT MY OWN", INK), ("GAME ENGINE", ORANGE)], 0.0, 2.6),
        ("label", "BUILT FROM BOXES", "every character is a hand-made box rig", a + 0.4, a + 6.8),
        ("label", "MESH IMPORT", "authored assets, one renderer", a + 7.2, a + 9.6),
        ("label", "LIGHT AND WEATHER", "sodium lamps, torches, snow, real time", a + 9.9, a + 12.9),
        ("label", "PROCEDURAL LOCOMOTION", "", a + 13.2, e - 2.7),
    ], {0.0: 1.0, HIT[14.0] - HIT[6.0]: 0.5, e - 2.6: 0.55, e: 0.85},
        [(0.0, HIT[6.0], e - 2.6), (e - 2.6, HIT[62.0], 2.6 + 5.2)], e + 5.2)

    # 3. REPLAY: one seeded fight shown from three cameras, on the music's
    # 62.0 -> 71.3 build (9.3 s) into the title; loops cleanly
    t = HIT[71.3] - HIT[62.0]
    c = t / 3

    def fight(cls, a0, a1, **kw):
        return cls(a0, a1, bursts=SAME, strafe=False, **kw)
    S["replay"] = Short("replay", "same fight, three cameras", [
        fight(R.Combat, 0.0, c, pz=1.6, shift=0.24),
        fight(R.FireLow, c, 2 * c, pz=1.2),
        fight(R.SlowMo, 2 * c, t, pz=1.15, speed=lambda lt: 1.0),
        EndCard(t, t + 4.6, swap=2.0),
    ], [
        ("hook", [("SAME FIGHT", INK), ("THREE CAMERAS", ORANGE)], 0.0, c - 0.15),
        ("tag", "CAM 2", c, 2 * c),
        ("tag", "CAM 3", 2 * c, t),
        ("label", "DETERMINISTIC", "seeded sim, replayable runs", 2 * c + 0.2, t - 0.05),
    ], {0.0: 0.55, c: 0.3, 2 * c: 0.3, t: 0.85},
        [(0.0, HIT[62.0], t + 4.6)], t + 4.6)
    return S


# ── frames ──────────────────────────────────────────────────────────────
class Cutter:
    def __init__(self, sh):
        pygame.init()
        pygame.display.set_mode((64, 64))
        _portrait_camera()
        self.sh = sh
        self.grain = R.Grain()
        self.cv = pygame.Surface((W, H))
        self.pic = pygame.Surface((W, H))

    def shot_at(self, T):
        for s in self.sh.shots:
            if s.start <= T < s.end:
                return s
        return self.sh.shots[-1]

    def frame(self, T, n):
        s = self.shot_at(T)
        PZ[0] = getattr(s, "pz", 1.25)
        s.ensure()
        lt = T - s.start
        surf = s.picture(lt, T, n)
        cv = self.cv
        cv.fill((0, 0, 0))
        if s.letterbox:
            if surf.get_size() == (W, H):
                self.pic.blit(surf, (0, 0))
            else:
                pygame.transform.smoothscale(surf, (W, H), self.pic)
            self.grain.apply(self.pic, n, s.grain)
            if s.fade:
                k = min(clamp(lt / s.fade[0]), clamp((s.end - T) / s.fade[1]))
                if k < 1:
                    v = int(255 * (1 - smooth(k)))
                    self.pic.fill((v, v, v), special_flags=pygame.BLEND_RGB_SUB)
            cv.blit(self.pic, (0, 0))
        s.overlay(cv, lt, T)
        for cue in self.sh.texts:
            kind = cue[0]
            if kind == "hook":
                hook(cv, cue[1], cue[2], cue[3], T)
            elif kind == "label":
                label(cv, cue[1], cue[2], cue[3], cue[4], T)
            elif kind == "tag" and cue[2] <= T < cue[3]:
                img = R.spaced(cue[1], C.font("monob", 34), ORANGE, 6)
                _shadowed(img, cv, (W // 2 - img.get_width() // 2, 230), 1.0)
        for t0, amp in self.sh.flash.items():
            d = T - t0
            if 0 <= d < 0.4:
                v = int(255 * amp * math.exp(-d * 11.0))
                cv.fill((v, v, v), special_flags=pygame.BLEND_RGB_ADD)
        if T > self.sh.total - 0.5:
            v = int(255 * smooth((T - (self.sh.total - 0.5)) / 0.5))
            cv.fill((v, v, v), special_flags=pygame.BLEND_RGB_SUB)
        return cv


# ── sound ───────────────────────────────────────────────────────────────
def mix(sh, events, out):
    import numpy as np
    import score
    X = score.X
    SR = X.SR
    X.TOTAL = sh.total
    bus = X.Bus()
    m = score.decode(score.SRC)
    xf = int(0.06 * SR)
    for t0, m0, dur in sh.music:
        i0, j0, k = int(t0 * SR), int(m0 * SR), int(dur * SR)
        k = min(k, len(m) - j0, len(bus.L) - i0)
        piece = m[j0:j0 + k].copy()
        ramp = np.linspace(0, 1, xf)[:, None]
        if t0 > 0:
            piece[:xf] *= ramp
        piece[-xf:] *= ramp[::-1]
        bus.L[i0:i0 + k] += piece[:, 0] * 0.9
        bus.R[i0:i0 + k] += piece[:, 1] * 0.9
    for t, amp in sh.flash.items():
        if t > 0 or amp >= 0.55:
            bus.add(t, X.boom(2.2 if amp >= 0.8 else 1.4), -6 if amp >= 0.8 else -12)
    for s in sh.shots[1:]:
        bus.add(max(0.0, s.start - 0.3), X.whoosh(0.3, up=True), -23, pan=score.RNG.uniform(-0.5, 0.5))
    shot = X.gunshot(tail=0.45)
    for t, kind in events:
        if kind == "shot":
            bus.add(t, shot, -10 + score.RNG.uniform(-1.5, 0.5), pan=score.RNG.uniform(-0.15, 0.15))
        elif kind == "shot_slow":
            bus.add(t, score.slowed(X.gunshot(big=True, tail=0.8)), -6)
            bus.add(t, X.boom(1.6), -14)
        elif kind == "hit":
            bus.add(t + 0.03, score.impact(), -18, pan=score.RNG.uniform(-0.4, 0.4))
    for s in sh.shots:
        if isinstance(s, R.Assembly):
            for lt in sorted(set(R.LAND.values())):
                if s.start + lt < s.end:
                    bus.add(s.start + lt, score.clack(), -17, pan=score.RNG.uniform(-0.4, 0.4))
        if isinstance(s, R.Breath):
            bus.add(s.start, score.wind(s.end - s.start + 0.8), -26)
            bus.add(s.start + 1.3, score.exhale(), -25)
        if isinstance(s, EndCard):
            bus.add(s.start, X.ring(3.0, 2480), -34)
            bus.add(s.start + s.swap, X.stamp(), -15)
    mixd = np.stack([bus.L, bus.R], 1)[: int(sh.total * SR)]
    tail = int(0.6 * SR)
    mixd[-tail:] *= np.linspace(1, 0, tail)[:, None] ** 1.5
    ref = np.percentile(np.abs(mixd), 99.95) or 1.0
    mixd = np.tanh(mixd / ref * 1.05) * 0.89 * 0.8      # a touch hotter than the film: phone speakers
    import wave
    pcm = (np.clip(mixd, -1, 1) * 32767).astype(np.int16)
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out


def video(sh, audio=True):
    os.makedirs(OUT, exist_ok=True)
    cut = Cutter(sh)
    out = os.path.join(OUT, "rpe6_short_%s.mp4" % sh.name)
    silent = out[:-4] + "_picture.mp4" if audio else out
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", silent]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    del R.EVENTS[:]
    st, N = time.time(), int(round(sh.total * FPS))
    for n in range(N):
        T = (n + 0.5) / FPS
        p.stdin.write(pygame.image.tobytes(cut.frame(T, n), "RGB"))
        if n % 90 == 0:
            print("%s frame %d/%d  %.1f fps" % (sh.name, n + 1, N, (n + 1) / max(time.time() - st, 1e-6)),
                  flush=True)
    p.stdin.close()
    p.wait()
    if audio:
        wav = mix(sh, sorted(R.EVENTS), out[:-4] + ".wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", wav, "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart",
                        out], check=True)
        os.remove(silent)
        os.remove(wav)
    print("->", out, "in %.0fs" % (time.time() - st), flush=True)


def stills(sh, times):
    d = os.path.join(OUT, "stills")
    os.makedirs(d, exist_ok=True)
    cut = Cutter(sh)
    paths = []
    for T in times:
        p = os.path.join(d, "%s_T%05.2f_%s.png" % (sh.name, T, type(cut.shot_at(T)).__name__))
        pygame.image.save(cut.frame(T, int(T * FPS)), p)
        paths.append(p)
        print(os.path.basename(p), flush=True)
    return paths


# ── covers: the trailer thumbnail's look (heavy type, red banner) at 9:16 ─
# TikTok's grid crops a cover to the middle 3:4 (y 240..1680), so the type
# keeps inside that band
COVERS = {
    # name: (pictures, lines, banner, sub, text top).  One picture is
    # (time, (x, y, w)): punch in on that 9:16 window.  Several are
    # (local time, strip top y) per camera, one sim instant stacked.
    "gameplay": ([(18.4, (40, 330, 820))], ["100%", "IN-ENGINE"], "GAMEPLAY", "CALL OF ACARISTAN", 1200),
    "engine": ([(8.05, (150, 260, 780))], ["I BUILT MY", "OWN GAME"], "ENGINE", "RPE6 // CALL OF ACARISTAN", 1200),
    "replay": ([(1.2, 940), (None, 700), (None, 480)], ["SAME FIGHT"], "3 CAMERAS",
               "CALL OF ACARISTAN", 1300),
}


def _heavy(txt, size, col=(255, 255, 255), stroke=7):
    f = pygame.font.SysFont("arialblack", size)
    body = f.render(txt, True, col)
    edge = f.render(txt, True, (0, 0, 0))
    out = pygame.Surface((body.get_width() + 2 * stroke + 8, body.get_height() + 2 * stroke + 8), pygame.SRCALPHA)
    for a in range(0, 360, 20):
        dx, dy = stroke * math.cos(math.radians(a)), stroke * math.sin(math.radians(a))
        out.blit(edge, (stroke + dx + 6, stroke + dy + 8))          # drop shadow
    for a in range(0, 360, 20):
        dx, dy = stroke * math.cos(math.radians(a)), stroke * math.sin(math.radians(a))
        out.blit(edge, (stroke + dx, stroke + dy))
    out.blit(body, (stroke, stroke))
    return out


def _lift(surf, gain=1.18, gamma=0.82):
    """Night frames read muddy at feed size: open the shadows a little."""
    import numpy as np
    a = pygame.surfarray.pixels3d(surf)
    f = (a.astype(np.float32) / 255.0) ** gamma * gain
    a[...] = np.clip(f * 255.0, 0, 255).astype(np.uint8)
    del a


def cover(name, sh):
    pics, lines, banner, sub, y = COVERS[name]
    quiet = Short(sh.name, sh.title, sh.shots, [], {}, sh.music, sh.total)
    cut = Cutter(quiet)
    cv = pygame.Surface((W, H))
    if len(pics) == 1:
        T, (x, y0, w) = pics[0]
        img = cut.frame(T, int(T * FPS)).subsurface((x, y0, w, w * H // W))
        pygame.transform.smoothscale(img, (W, H), cv)
    else:                                    # one sim instant from each camera, stacked
        lt = pics[0][0]
        strip = (y - 60) // len(pics)
        for i, (shot, (_t, cy)) in enumerate(zip(sh.shots, pics)):
            T = shot.start + lt
            img = cut.frame(T, int(T * FPS))
            cv.blit(img, (0, i * strip), (0, cy - strip // 2, W, strip))
            pygame.draw.rect(cv, (0, 0, 0), (0, i * strip - 4, W, 8))
            tag_ = _heavy("CAM %d" % (i + 1), 44, ORANGE, 4)
            cv.blit(tag_, (44, i * strip + 28))
    _lift(cv)
    shade = pygame.Surface((W, 760), pygame.SRCALPHA)       # a floor under the type
    for j in range(760):
        a = int(170 * max(0.0, math.sin(math.pi * j / 759)) ** 0.8)
        pygame.draw.line(shade, (0, 0, 0, a), (0, j), (W, j))
    cv.blit(shade, (0, y - 140))
    for txt in lines:
        img = _fit(_heavy(txt, 150), W - 70)
        cv.blit(img, (W // 2 - img.get_width() // 2, y))
        y += img.get_height() - 40
    b = _fit(_heavy(banner, 112, stroke=3), W - 200)
    bw, bh = b.get_width() + 60, b.get_height() - 4
    pygame.draw.rect(cv, (206, 28, 28), (W // 2 - bw // 2, y + 18, bw, bh))
    cv.blit(b, (W // 2 - b.get_width() // 2, y + 14))
    s = _fit(_heavy(sub, 50, (255, 178, 74), 4), W - 120)
    cv.blit(s, (W // 2 - s.get_width() // 2, y + bh + 44))
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "cover_%s.png" % name)
    pygame.image.save(cv, p)
    pygame.image.save(cv, p[:-4] + ".jpg")
    print("->", p, flush=True)


def sheet(paths, out, cols=5, w=270):
    h = w * H // W
    rows = (len(paths) + cols - 1) // cols
    s = pygame.Surface((cols * w, rows * h))
    for i, p in enumerate(paths):
        s.blit(pygame.transform.smoothscale(pygame.image.load(p), (w, h)), ((i % cols) * w, (i // cols) * h))
    pygame.image.save(s, out)
    print("->", out)


def main():
    S = shorts()
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?", choices=sorted(S) + ["all"])
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--at", type=float, nargs="*")
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--noaudio", action="store_true")
    ap.add_argument("--thumbs", action="store_true")
    a = ap.parse_args()
    if a.list or not a.name:
        for k, sh in S.items():
            print("%-9s %5.1fs  %s" % (k, sh.total, sh.title))
        return
    for k in (sorted(S) if a.name == "all" else [a.name]):
        sh = S[k]
        if a.thumbs:
            cover(k, sh)
        elif a.sheet:
            times = [s.start + (s.end - s.start) * 0.55 for s in sh.shots]
            sheet(stills(sh, times), os.path.join(OUT, "_sheet_%s.jpg" % k))
        elif a.at:
            stills(sh, a.at)
        else:
            video(sh, audio=not a.noaudio)


if __name__ == "__main__":
    main()
