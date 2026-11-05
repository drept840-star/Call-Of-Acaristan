"""TVA 1 broadcast: the 2.5D announcement trailer.

    python tools/trailer_25d/render.py [--from S] [--to S] [--stills S,S,...] [--no-audio]

Composes the 3D sets (sets.py), the captured gameplay clips and the 2D cards at
1920x1080/30, grades everything black-and-white with CRT grain until the lever
works (SWITCH), then mixes VO, music and SFX and muxes
trailers/announce_25d/announce_25d_trailer.mp4. ``--stills`` writes single
frames to the scratch dir given by --out-dir (review), nothing else.
"""
import json
import math
import os
import random
import subprocess
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import cv2  # noqa: E402
import sets as S  # noqa: E402  (imports trailer3d/common, src/ on sys.path)
import common as C  # noqa: E402
import pygame  # noqa: E402

OW, OH, FPS = 1920, 1080, 30
OUT = os.path.join(ROOT, "trailers", "announce_25d")
CLIPS = os.path.join(OUT, "clips")
VO_DIR = os.path.join(ROOT, "assets", "voice", "Trailer", "announce_25d")
SFX = os.path.join(ROOT, "sfx_wav")
OST = os.path.join(ROOT, "assets", "music", "ost")
M6_SRC = os.path.join(ROOT, "outputs", "trailer_rpe6_m7", "rpe6_m7_trailer.mp4")
SR = 48000
END = 171.0
SWITCH = 73.0
GOLD, RED, INK = (214, 176, 84), (176, 28, 32), (240, 236, 226)

# ── VO: id -> (start in mix, trimmed span in file, speaker, subtitle) ─────
SPAN = {"A01": (.35, 7.78), "A02": (.18, 6.73), "A03": (.14, 5.56), "A04": (.21, 6.41),
        "A05": (.32, 7.98), "A06": (.56, 9.81), "A07": (.28, 8.15), "A08": (.32, 2.12),
        "A09": (.33, 1.77), "A10": (.24, 2.89), "A11": (.28, 5.03), "A12": (.27, 3.39),
        "A13": (.21, 3.03), "A14": (.41, 4.13), "A15": (.31, 5.14), "A16": (.25, 5.56),
        "A17": (.29, 7.07), "A18": (.30, 6.29), "B01": (.26, 8.35), "B02": (.32, 4.93),
        "G01": (.32, 4.88), "G02": (.25, 2.61), "N01": (.26, 5.82), "R01": (.31, 6.74),
        "R02": (.28, .71), "R03": (.33, 1.12), "T01": (.35, 3.29), "V01": (.30, 3.56)}
VO = [
    ("A01", 4.0, "Good evening, citizens. Please remain seated. Tonight, history will be... slightly taller."),
    ("A02", 12.2, "By Decree Number Two-Point-Five, the Republic of Acaristan moves from two dimensions to two and a half."),
    ("A03", 19.2, "The remaining half was sold by the Ministry of Finance. It is under review."),
    ("A04", 25.6, "Rules for viewers. One: do not touch the screen. Depth is state property."),
    ("A05", 32.3, "Two: do not look behind the walls. Behind the walls there is nothing. There has always been nothing."),
    ("A06", 40.5, "Three: depth will arrive on the ground floor first. Tenth floor, please wait. "
                  "Depth is taking the stairs. The elevator is broken."),
    ("A07", 50.3, "Four: if your television shows depth before eight o'clock, report your neighbor."),
    ("R01", 59.0, "Citizens! With this lever, I give you... the half dimension!"),
    ("R02", 66.0, "...Is it on?"),
    ("T01", 66.9, "Mister President, it's plugged into the kettle."),
    ("R03", 70.15, None),
    ("A08", 73.4, "Citizens. It is happening."),
    ("A09", 80.6, "Walls now have a side."),
    ("A10", 84.3, "Enemies now have backs. Please use them."),
    ("A11", 88.8, "Bullets now cast shadows. Shadows are not taxed. Yet."),
    ("A12", 94.3, "Rain now falls down. Previously it fell across."),
    ("A13", 98.4, "The same beloved citizens. Now with a top of the head."),
    ("V01", 102.0, "Biribel, I can see you now. ...You need a haircut."),
    ("A14", 105.8, "Multiplayer: now you can be shot from an angle."),
    ("G01", 112.6, "In my day we had one dimension, and we were grateful."),
    ("G02", 117.7, "Turn it off. It's looking at me."),
    ("N01", 120.8, "I can see the roof of my block! ...There is a man on the roof."),
    ("B01", 127.2, "I was there when depth was invented. I fought in the first dimension. I was decorated in the second."),
    ("B02", 135.8, "The medal is real. The paperwork is... being prepared."),
    ("A15", 141.2, "Call of Acaristan. Now in two and a half D."),
    ("A16", 146.4, "Release date: soon. ...Maybe. The Ministry of Calendars will confirm."),
    ("A17", 152.2, "The Ministry is already studying the third dimension. Estimated arrival: twenty eighty-seven."),
    ("A18", 159.4, "That footage did not happen. Goodnight, citizens. Glory to the extra half."),
]
SPEAKER = {"A": "ann", "R": "pres", "T": "tech", "G": "gran", "N": "nb", "B": "bal", "V": "vas"}


def read_wav(path):
    with wave.open(path, "rb") as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        x = np.frombuffer(w.readframes(n), "<i2").astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def resample(x, sr):
    if sr == SR:
        return x
    n = int(len(x) * SR / sr)
    return np.interp(np.arange(n) * (sr / SR), np.arange(len(x)), x).astype(np.float32)


def vo_clip(vid):
    x, sr = read_wav(os.path.join(VO_DIR, vid + ".wav"))
    a, b = SPAN[vid]
    x = x[max(0, int((a - 0.06) * sr)):int((b + 0.12) * sr)]
    return resample(x, sr)


# mouth envelopes per speaker, 30 fps over the whole cut
ENV = {k: np.zeros(int(END * FPS) + 2, np.float32) for k in SPEAKER.values()}
SUBS = []
for vid, t0, text in VO:
    x = vo_clip(vid)
    hop = SR // FPS
    rms = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2) + 1e-9) for i in range(0, len(x) - hop, hop)])
    rms = np.clip(rms / (np.percentile(rms, 95) + 1e-6), 0, 1)
    i0 = int(round((t0 - 0.06) * FPS))
    e = ENV[SPEAKER[vid[0]]]
    e[i0:i0 + len(rms)] = np.maximum(e[i0:i0 + len(rms)], rms[:len(e) - i0])
    if text:
        SUBS.append((t0, t0 + len(x) / SR, text))


def env_of(who, t0):
    e = ENV[who]
    return lambda lt: float(e[min(len(e) - 1, max(0, int((t0 + lt) * FPS)))])


# ── clips ────────────────────────────────────────────────────────────────
class Clip:
    def __init__(self, path, crop=(0, 69, 1000, 562)):
        self.cap = cv2.VideoCapture(path)
        self.n = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.crop, self.idx, self.cur = crop, -9, None

    def raw(self, t):
        idx = max(0, min(self.n - 1, int(round(t * FPS))))
        if idx != self.idx:
            if idx != self.idx + 1:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, f = self.cap.read()
            if ok:
                self.cur = f
            self.idx = idx
        return self.cur

    def frame(self, t, crop=None, size=(OW, OH), zoom=1.0, pop=False):
        f = self.raw(t)
        x, y, w, h = crop or self.crop
        if zoom != 1.0:
            nw, nh = int(w / zoom), int(h / zoom)
            x, y, w, h = x + (w - nw) // 2, y + (h - nh) // 2, nw, nh
        img = cv2.resize(f[y:y + h, x:x + w], size, interpolation=cv2.INTER_LINEAR)
        if pop:
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[..., 1] = np.clip(hsv[..., 1] * 1.3, 0, 255)
            hsv[..., 2] = np.clip(255.0 * (hsv[..., 2] / 255.0) ** 0.8 * 1.06, 0, 255)
            img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return pygame.image.frombytes(img.tobytes(), size, "RGB")


_clips = {}


def clip(name):
    if name not in _clips:
        if name == "m6":
            _clips[name] = Clip(M6_SRC, crop=(285, 138, 1350, 760))
        elif name == "mp":
            _clips[name] = Clip(os.path.join(OUT, "mp", "host_flow.mp4"))
        else:
            _clips[name] = Clip(os.path.join(CLIPS, name + ".mp4"))
    return _clips[name]


# ── 2D pieces ────────────────────────────────────────────────────────────
_txt = {}


def text(s, name, size, col, outline=0):
    k = (s, name, size, col, outline)
    if k not in _txt:
        f = C.font(name, size)
        img = f.render(s, True, col)
        if outline:
            o = f.render(s, True, (0, 0, 0))
            out = pygame.Surface((img.get_width() + outline * 2, img.get_height() + outline * 2), pygame.SRCALPHA)
            for dx in range(-outline, outline + 1, max(1, outline // 2)):
                for dy in range(-outline, outline + 1, max(1, outline // 2)):
                    out.blit(o, (outline + dx, outline + dy))
            out.blit(img, (outline, outline))
            img = out
        _txt[k] = img
    return _txt[k]


def wrap(s, name, size, maxw):
    f = C.font(name, size)
    lines, cur = [], ""
    for w in s.split():
        nxt = (cur + " " + w).strip()
        if f.size(nxt)[0] > maxw and cur:
            lines.append(cur)
            cur = w
        else:
            cur = nxt
    return lines + ([cur] if cur else [])


def test_card(w=OW, h=OH):
    s = pygame.Surface((w, h))
    s.fill((26, 26, 28))
    k = h / 1080.0
    bars = [(192, 192, 192), (192, 192, 0), (0, 192, 192), (0, 192, 0), (192, 0, 192), (192, 0, 0), (0, 0, 192)]
    bw = w // 7
    for i, c in enumerate(bars):
        pygame.draw.rect(s, c, (i * bw, 0, bw + 1, int(h * 0.62)))
    for i in range(7):
        pygame.draw.rect(s, (20 + i * 36,) * 3, (i * bw, int(h * 0.62), bw + 1, int(h * 0.12)))
    cx, cy, r = w // 2, int(h * 0.45), int(h * 0.36)
    pygame.draw.circle(s, (240, 240, 240), (cx, cy), r, max(2, int(6 * k)))
    pygame.draw.circle(s, (30, 30, 34), (cx, cy), int(r * 0.55))
    pygame.draw.line(s, (240, 240, 240), (cx - r, cy), (cx + r, cy), max(1, int(3 * k)))
    pygame.draw.line(s, (240, 240, 240), (cx, cy - r), (cx, cy + r), max(1, int(3 * k)))
    crest = pygame.transform.smoothscale(S._crest(100), (int(h * 0.3),) * 2)
    s.blit(crest, crest.get_rect(center=(cx, cy)))
    t = text("TVA 1", "oswald", max(12, int(110 * k)), INK)
    pygame.draw.rect(s, (12, 12, 14), t.get_rect(center=(cx, int(h * 0.86))).inflate(60 * k, 10 * k))
    s.blit(t, t.get_rect(center=(cx, int(h * 0.86))))
    t2 = text("PROGRAMUL NATIONAL", "mono", max(10, int(34 * k)), (200, 200, 200))
    s.blit(t2, t2.get_rect(center=(cx, int(h * 0.95))))
    return s


TEST = None
CARD43 = None


def bug(surf, t):
    """Channel bug, clock, and the 2.5D badge once depth arrives."""
    b = text("TVA 1", "oswald", 54, GOLD, outline=3)
    surf.blit(b, (OW - b.get_width() - 60, 40))
    if (t * 1.2) % 2 < 1.4:
        pygame.draw.circle(surf, (220, 30, 30), (OW - b.get_width() - 84, 78), 10)
    clock = "20:00" if t >= SWITCH else "19:5%d" % min(9, 7 + int(t / 30))
    c = text(clock, "mono", 30, INK, outline=2)
    surf.blit(c, (OW - c.get_width() - 62, 108))
    if t >= SWITCH + 1.0:
        d = text("+0.5D", "oswald", 34, (255, 255, 255), outline=0)
        r = d.get_rect(topright=(OW - b.get_width() - 130, 50)).inflate(18, 4)
        pygame.draw.rect(surf, RED, r)
        surf.blit(d, d.get_rect(center=r.center))


CHYRONS = [(5.0, 11.5, "DECREE No. 2.5", "MINISTRY OF DIMENSIONS"),
           (19.6, 24.6, "BREAKING", "REMAINING 0.5D SOLD - UNDER REVIEW"),
           (59.6, 63.4, "LIVE", "PRESIDENT RETARDOVICI THROWS THE LEVER"),
           (67.4, 69.8, "TECHNICIAN", "NOT TO BLAME"),
           (113.0, 117.3, "CITIZEN REACTION", "BLOCK 4, 10TH FLOOR - STILL WAITING FOR DEPTH"),
           (121.0, 123.1, "CITIZEN REACTION", "BLOCK 4, 3RD FLOOR"),
           (127.6, 134.6, "GEN. BALACEANU", "INVENTOR OF DEPTH"),
           (159.6, 165.0, "CORRECTION", "THE PREVIOUS FOOTAGE DID NOT HAPPEN")]


def chyron(surf, t):
    for a, b, tag, msg in CHYRONS:
        if a <= t < b:
            u = C.smooth(C.clamp((t - a) / 0.35)) * C.smooth(C.clamp((b - t) / 0.3))
            tg = text(tag, "oswald", 40, (255, 255, 255))
            ms = text(msg, "oswald", 40, (20, 20, 24))
            x = int(-900 * (1 - u)) + 90
            y = 780
            pygame.draw.rect(surf, RED, (x, y, tg.get_width() + 40, 62))
            pygame.draw.rect(surf, (236, 232, 220), (x + tg.get_width() + 40, y, ms.get_width() + 44, 62))
            pygame.draw.rect(surf, GOLD, (x, y + 62, tg.get_width() + ms.get_width() + 84, 6))
            surf.blit(tg, (x + 20, y + 4))
            surf.blit(ms, (x + tg.get_width() + 62, y + 4))


def subtitles(surf, t):
    for a, b, s in SUBS:
        if a - 0.05 <= t < b + 0.25:
            lines = wrap(s, "oswald", 46, 1500)
            y = OH - 70 - len(lines) * 58
            for ln in lines:
                img = text(ln, "oswald", 46, (255, 255, 255), outline=3)
                surf.blit(img, img.get_rect(midtop=(OW // 2, y)))
                y += 58


RULES = {1: ("DO NOT TOUCH THE SCREEN", "Depth is state property."),
         2: ("DO NOT LOOK BEHIND THE WALLS", "There is nothing there."),
         3: ("GROUND FLOOR FIRST", "Depth is taking the stairs."),
         4: ("REPORT YOUR NEIGHBOR", "If depth arrives before 20:00.")}


def rule_panel(surf, n, lt):
    u = C.smooth(C.clamp(lt / 0.4))
    pw = 700
    x = int(-pw * (1 - u))
    p = pygame.Surface((pw, OH), pygame.SRCALPHA)
    p.fill((10, 10, 12, 225))
    pygame.draw.rect(p, GOLD, (0, 0, 10, OH))
    p.blit(text("VIEWER INSTRUCTIONS", "mono", 34, GOLD), (60, 150))
    p.blit(text("RULE", "oswald", 60, INK), (60, 230))
    p.blit(text(str(n), "oswald", 300, INK), (60, 270))
    y = 650
    for ln in wrap(RULES[n][0], "oswald", 62, 590):
        p.blit(text(ln, "oswald", 62, (255, 255, 255)), (60, y))
        y += 74
    p.blit(text(RULES[n][1], "mono", 30, (190, 190, 190)), (60, y + 16))
    surf.blit(p, (x, 0))


def stamp(surf, lt, lines, center, angle=-12, scale=1.0, paper=False):
    if lt < 0:
        return
    k = 1.0 + 1.6 * (1 - C.clamp(lt / 0.12))
    w = max(text(l, "oswald", int(90 * scale), RED).get_width() for l in lines) + 60
    h = len(lines) * int(100 * scale) + 40
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    if paper:                                  # slapped-on notice: still legible in black and white
        s.fill((236, 230, 214, 235))
    pygame.draw.rect(s, RED, (0, 0, w, h), 10)
    y = 20
    for l in lines:
        img = text(l, "oswald", int(90 * scale), RED)
        s.blit(img, img.get_rect(midtop=(w // 2, y)))
        y += int(100 * scale)
    rng = random.Random(len(lines[0]))
    for _ in range(140):                       # ink wear
        pygame.draw.circle(s, (236, 230, 214, 235) if paper else (0, 0, 0, 0), (rng.randrange(w), rng.randrange(h)),
                           rng.randint(2, 6))
    s = pygame.transform.rotozoom(s, angle, k)
    s.set_alpha(int(255 * min(1.0, lt / 0.06 + 0.3)))
    surf.blit(s, s.get_rect(center=center))


def extruded(surf, label, size, center, depth, front, side):
    for i in range(depth, 0, -1):
        k = i / max(1, depth)
        sh = text(label, "oswald", size, tuple(int(c * (0.35 + 0.4 * (1 - k))) for c in side))
        surf.blit(sh, sh.get_rect(center=(center[0] + i, center[1] + i)))
    fr = text(label, "oswald", size, front)
    surf.blit(fr, fr.get_rect(center=center))
    return fr.get_rect(center=center)


def logo_card(t, lt):
    bgc = clip("m1_3d").frame(4.0 + lt * 0.5, size=(OW // 8, OH // 8))
    s = pygame.transform.smoothscale(pygame.transform.smoothscale(bgc, (OW // 16, OH // 16)), (OW, OH))
    dark = pygame.Surface((OW, OH), pygame.SRCALPHA)
    dark.fill((34, 6, 8, 215))
    s.blit(dark, (0, 0))
    # slow state-broadcast sun rays behind the crest
    rays = pygame.Surface((OW, OH), pygame.SRCALPHA)
    cx, cy = OW // 2, 250
    for i in range(18):
        a0 = lt * 0.12 + i * math.tau / 18
        pts = [(cx, cy), (cx + 2400 * math.cos(a0), cy + 2400 * math.sin(a0)),
               (cx + 2400 * math.cos(a0 + 0.12), cy + 2400 * math.sin(a0 + 0.12))]
        pygame.draw.polygon(rays, (214, 176, 84, 22), pts)
    s.blit(rays, (0, 0))
    u = C.smooth(C.clamp(lt / 0.6))
    cs = int(220 * (0.85 + 0.15 * u))
    cr = pygame.transform.smoothscale(S._crest(100), (cs, cs))
    s.blit(cr, cr.get_rect(center=(cx, cy)))
    extruded(s, "CALL OF ACARISTAN", 150, (OW // 2, 500 + int(40 * (1 - u))), 10, INK, (200, 60, 60))
    # "NOW IN 2.5D": the extrusion grows as the half dimension is delivered
    depth = int(22 * C.ease_out(C.clamp((lt - 0.8) / 0.9)))
    r = extruded(s, "NOW IN 2.5D", 120, (OW // 2, 700), depth, GOLD, (180, 40, 40))
    k = C.clamp((lt - 1.9) / 0.7)
    if 0 < k < 1:                              # gold sweep across the words
        x = int(r.left - 120 + (r.width + 240) * k)
        sw = pygame.Surface((90, r.height), pygame.SRCALPHA)
        for xx in range(90):
            pygame.draw.line(sw, (255, 250, 220, int(110 * math.sin(math.pi * xx / 90))), (xx, 0), (xx, r.height))
        s.blit(sw, (x, r.top))
    if lt > 2.4:
        f = text("A TVA 1 STATE BROADCAST", "mono", 32, (220, 200, 160))
        f.set_alpha(int(255 * C.clamp((lt - 2.4) / 0.5)))
        s.blit(f, f.get_rect(center=(OW // 2, 840)))
    return s


def soon_card(t, lt):
    s = pygame.Surface((OW, OH))
    s.fill((16, 18, 26))
    for y in range(0, OH, 4):
        pygame.draw.line(s, (20, 22, 32), (0, y), (OW, y))
    a = text("RELEASE DATE", "mono", 54, GOLD)
    s.blit(a, a.get_rect(center=(OW // 2, 300)))
    b = text("SOON", "oswald", 300, INK)
    s.blit(b, b.get_rect(center=(OW // 2, 530)))
    stamp(s, lt - 2.0, ["(MAYBE)"], (OW // 2 + 480, 740), angle=10, scale=1.1)
    if lt > 3.0:
        c = text("Pending confirmation by the Ministry of Calendars", "mono", 36, (170, 170, 180))
        c.set_alpha(int(255 * C.clamp((lt - 3.0) / 0.4)))
        s.blit(c, c.get_rect(center=(OW // 2, 860)))
    return s


# ── shots: (t0, t1, fn(lt, t) -> Surface) ────────────────────────────────
studio, palace, flat, window, press, cardstand = S.Studio(), S.Palace(), S.Flat(), S.Window(), S.Press(), S.CardStand()


def up3(s):
    return pygame.transform.scale(s, (OW, OH))


def sh_test(lt, t):
    return TEST


def sh_studio(cam, expr=None, t0=0.0):
    return lambda lt, t: up3(studio.render(lt, env=env_of("ann", t0), cam=cam, expr=expr, deep=t >= SWITCH))


TAGS = {"m1": "MISSION 1 - BLACK NOTEBOOK", "m2": "MISSION 2 - QUIET ON ROUTE 12",
        "m3": "MISSION 3 - THE VOSTRAL", "m4": "MISSION 4 - THE AFTERMATH", "mp": "MULTIPLAYER"}


def tag(surf, label, lt):
    a = C.clamp(lt / 0.25)
    img = text(label, "mono", 30, (255, 255, 255))
    r = img.get_rect(topright=(OW - 62, 160)).inflate(36, 12)
    box = pygame.Surface(r.size, pygame.SRCALPHA)
    box.fill((12, 12, 16, int(200 * a)))
    pygame.draw.rect(box, RED, (0, 0, 8, r.h))
    surf.blit(box, r)
    img.set_alpha(int(255 * a))
    surf.blit(img, img.get_rect(center=r.center).move(4, 0))


def sh_clip(name, off, rate=1.0, dur=4.0, z=(1.0, 1.08)):
    pop = name.endswith("3d") or name == "mp"
    def f(lt, t):
        zoom = C.lerp(z[0], z[1], C.clamp(lt / dur)) if pop else 1.0
        s = clip(name).frame(off + lt * rate, zoom=zoom, pop=pop)
        if pop and OVERLAYS["on"]:
            tag(s, TAGS[name[:2]], lt)
        return s
    return f


def sh_palace(shot, **kw):
    def f(lt, t):
        a = {k: (v(t) if callable(v) else v) for k, v in kw.items()}
        return up3(palace.render(lt, env=env_of("pres", t - lt), shot=shot, tech_env=env_of("tech", t - lt), **a))
    return f


def sh_static(lt, t):
    rng = np.random.default_rng(int(t * 30))
    n = rng.integers(0, 255, (OH // 4, OW // 4), dtype=np.uint8)
    img = np.repeat(np.repeat(n, 4, 0), 4, 1)
    img = np.stack([img] * 3, -1)
    return pygame.image.frombytes(np.ascontiguousarray(img).tobytes(), (OW, OH), "RGB")


def sh_flat(shot, expr=None):
    def f(lt, t):
        scr = clip("m1_3d").frame(6.0 + lt, crop=(120, 40, 760, 570), size=(320, 240)) if shot == "tv" else None
        return up3(flat.render(lt, env=env_of("gran", t - lt), shot=shot, screen=scr, expr=expr,
                               lean=0.5 if shot == "tv" else 0.0))
    return f


def sh_window(lt, t):
    up = C.smooth(C.clamp((t - 123.2) / 1.3))
    wave = C.smooth(C.clamp((t - 124.6) / 0.4))
    return up3(window.render(lt, env=env_of("nb", t - lt), up=up, wave=wave))


def sh_press(shot, chest=0.0, expr="grin"):
    def f(lt, t):
        s = up3(press.render(lt, env=env_of("bal", t - lt), shot=shot, expr=expr, chest=chest))
        if press.flash:
            fl = pygame.Surface((OW, OH))
            fl.fill((255, 255, 255))
            fl.set_alpha(70)
            s.blit(fl, (0, 0))
        if shot == "close":
            stamp(s, t - 139.7, ["KRAP", "FACT-CHECK:", "UNVERIFIED"], (OW // 2 + 540, 430), angle=-12, scale=0.9)
        return s
    return f


def sh_leak(lt, t):
    s = clip("m6").frame(20.0 + lt, zoom=1.06 + 0.05 * lt, pop=True)
    lab = text("LEAKED FOOTAGE - DO NOT WATCH", "oswald", 56, (255, 60, 60), outline=3)
    s.blit(lab, (80, 70))
    yr = text("EST. 2087", "oswald", 120, (255, 255, 255), outline=4)
    s.blit(yr, yr.get_rect(bottomright=(OW - 80, OH - 200)))
    return s


def sh_card(lt, t):
    fall = 0.0
    if 0.8 <= lt < 1.4:
        fall = 0.10 * abs(math.sin((lt - 0.8) * 10))
    elif lt >= 1.4:
        fall = 0.10 + 0.9 * C.clamp((lt - 1.4) / 0.6)
    s = up3(cardstand.render(lt, CARD43, fall=fall))
    if lt > 2.6:
        a = C.clamp((lt - 2.6) / 0.6)
        m = text("PROGRAMUL S-A INCHEIAT", "oswald", 96, INK)
        m.set_alpha(int(255 * a))
        s.blit(m, m.get_rect(center=(OW // 2, 820)))
        n = text("(the broadcast has ended)", "mono", 34, (170, 170, 170))
        n.set_alpha(int(255 * a))
        s.blit(n, n.get_rect(center=(OW // 2, 900)))
    return s


# ── rule shots: each picture acts out its rule ───────────────────────────
TOUCH = (1420, 800)          # where the announcer's fist meets the glass (close cam)


def _crack_lines():
    rg = np.random.default_rng(11)
    out = []
    for i in range(10):
        a = i / 10 * math.tau + rg.uniform(-0.25, 0.25)
        n, length = int(rg.integers(4, 8)), rg.uniform(140, 460)
        x = y = 0.0
        pts = [(0.0, 0.0)]
        for _ in range(n):
            a += rg.uniform(-0.35, 0.35)
            x, y = x + math.cos(a) * length / n, y + math.sin(a) * length / n
            pts.append((x, y))
        out.append(pts)
    for rad in (46, 104):
        a0 = rg.uniform(0, math.tau)
        out.append([(math.cos(a0 + k * 0.42) * rad * rg.uniform(0.85, 1.15),
                     math.sin(a0 + k * 0.42) * rad * rg.uniform(0.85, 1.15)) for k in range(16)])
    return out


CRACKS = _crack_lines()


def cracks(surf, k, at=TOUCH):
    for pts in CRACKS:
        q = [(at[0] + x * k, at[1] + y * k) for x, y in pts]
        pygame.draw.lines(surf, (20, 20, 24), False, q, 6)
        pygame.draw.lines(surf, (236, 240, 248), False, q, 2)


def zap(surf, lt, at=TOUCH):
    rng = np.random.default_rng(int(lt * 60))
    for _ in range(6):
        a = rng.uniform(0, math.tau)
        x, y = at
        pts = [at]
        for _ in range(7):
            a += rng.uniform(-0.7, 0.7)
            x, y = x + math.cos(a) * rng.uniform(30, 70), y + math.sin(a) * rng.uniform(30, 70)
            pts.append((x, y))
        pygame.draw.lines(surf, (150, 190, 255), False, pts, 7)
        pygame.draw.lines(surf, (250, 252, 255), False, pts, 3)


def sh_rule1(lt, t):
    T = 3.0                                    # "...do not touch the screen" - he touches it
    if lt < T:
        reach = C.smooth(C.clamp((lt - 1.8) / 1.1))
    else:
        reach = 1.0 - C.smooth(C.clamp((lt - T - 0.05) / 0.35))
    s = up3(studio.render(lt, env=env_of("ann", t - lt), cam="close",
                          expr="worried" if lt >= T else None, reach=reach))
    if lt >= T:
        sh = max(0.0, 1 - (lt - T) / 0.5)
        if sh > 0:
            rng = np.random.default_rng(int(lt * 60))
            s.scroll(int(rng.uniform(-16, 16) * sh), int(rng.uniform(-10, 10) * sh))
        cracks(s, C.smooth(C.clamp((lt - T) / 0.12)))
        if lt < T + 0.35:
            zap(s, lt)
            fl = pygame.Surface((OW, OH))
            fl.fill((235, 242, 255))
            fl.set_alpha(int(170 * (1 - (lt - T) / 0.35)))
            s.blit(fl, (0, 0))
    stamp(s, lt - 4.5, ["STATE", "PROPERTY"], (1580, 470), angle=-10, paper=True)
    if OVERLAYS["on"]:
        rule_panel(s, 1, lt)
    return s


_PG = {}


def peel(img, a):
    """Fold the bottom-right of the map back like a page; behind it is nothing."""
    H, W = img.shape[:2]
    if "g" not in _PG:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        n = np.array([1.0, 0.72], np.float32)
        n /= np.linalg.norm(n)
        _PG.update(g=(xx, yy), n=n, p=xx * n[0] + yy * n[1], dmax=W * n[0] + H * n[1])
    xx, yy = _PG["g"]
    n, p, dmax = _PG["n"], _PG["p"], _PG["dmax"]
    d = dmax * (1 - 0.6 * a)
    void = p > d
    rx = xx + 2 * (d - p) * n[0]
    ry = yy + 2 * (d - p) * n[1]
    flap = ~void & (rx < W - 1) & (ry < H - 1)
    out = img.astype(np.float32)
    sh = cv2.GaussianBlur(flap.astype(np.float32), (0, 0), 14)
    out *= (1 - 0.6 * np.clip(sh * ~flap, 0, 1))[..., None]
    ghost = cv2.remap(img, rx, ry, cv2.INTER_LINEAR).astype(np.float32)
    dist = d - p
    paper = np.array([212, 208, 198], np.float32) * (0.62 + 0.38 * np.clip(dist / 140, 0, 1))[..., None]
    paper = paper * 0.88 + ghost * 0.12
    paper[dist < 2.5] = 252
    out = np.where(flap[..., None], paper, out)
    out[void] = (6, 6, 8)
    pos = (W - n[0] * (dmax - d) * 0.42, H - n[1] * (dmax - d) * 0.42)
    return np.clip(out, 0, 255).astype(np.uint8), pos


def sh_rule2(lt, t):
    W, H = OW // 2, OH // 2
    base = clip("m3_2d").frame(lt, size=(W, H))
    if lt < 7.3:
        a = C.smooth(C.clamp((lt - 2.9) / 2.1))
    else:
        a = 1.0 - C.clamp((lt - 7.3) / 0.22) ** 2          # snapped back shut
    pos = None
    if a > 0.001:
        arr = np.frombuffer(pygame.image.tobytes(base, "RGB"), np.uint8).reshape(H, W, 3)
        arr, pos = peel(arr, a)
        base = pygame.image.frombytes(arr.tobytes(), (W, H), "RGB")
    s = up3(base)
    if pos and a > 0.75:
        k = C.clamp((a - 0.75) / 0.25)
        cx, cy = int(pos[0] * 2), int(pos[1] * 2)
        m = text("NOTHING", "oswald", 96, (200, 200, 200))
        m.set_alpha(int(255 * k))
        s.blit(m, m.get_rect(center=(cx, cy)))
        if lt >= 5.7:
            n = text("(there has always been nothing)", "mono", 26, (150, 150, 150))
            n.set_alpha(int(255 * k * C.clamp((lt - 5.7) / 0.3)))
            s.blit(n, n.get_rect(center=(cx, cy + 74)))
    stamp(s, lt - 7.45, ["CLASSIFIED"], (1300, 520), angle=8, paper=True)
    if OVERLAYS["on"]:
        rule_panel(s, 2, lt)
    return s


BX, FH, GY, NF = 900, 62, 830, 11       # block of flats: left x, floor height, ground y, GF + 10
STAIR = (912, 1048)
LIFT = (1490, 1590)


def depth_man(s, x, y, t):
    glow = pygame.Surface((200, 200), pygame.SRCALPHA)
    for i, rad in enumerate((80, 58, 40)):
        pygame.draw.circle(glow, (255, 255, 255, 30 + 30 * i), (100, 100), rad)
    s.blit(glow, (x - 100, y - 140))
    step = int(t * 6) % 2
    pygame.draw.rect(s, (250, 250, 250), (x - 10, y - 20, 8, 20 if step else 16))
    pygame.draw.rect(s, (250, 250, 250), (x + 2, y - 20, 8, 16 if step else 20))
    pygame.draw.rect(s, (250, 250, 250), (x - 12, y - 52, 24, 34))
    pygame.draw.rect(s, (250, 250, 250), (x - 9, y - 74, 18, 18))
    lab = text("2.5D", "oswald", 30, (255, 255, 255), outline=2)
    s.blit(lab, lab.get_rect(midbottom=(x, y - 80)))


def flats(lt, t):
    s = pygame.Surface((OW, OH))
    s.fill((30, 34, 40))
    for x in range(0, OW, 48):
        pygame.draw.line(s, (38, 43, 50), (x, 0), (x, OH))
    for y in range(0, OH, 48):
        pygame.draw.line(s, (38, 43, 50), (0, y), (OW, y))
    s.blit(text("FIG. 3 - DISTRIBUTION OF DEPTH, BLOCK C4", "mono", 30, INK), (BX - 40, 84))
    top = GY - NF * FH
    pygame.draw.rect(s, (54, 58, 66), (BX, top, LIFT[1] - BX, NF * FH))
    pygame.draw.rect(s, INK, (BX, top, LIFT[1] - BX, NF * FH), 4)
    pygame.draw.line(s, INK, (760, GY), (1880, GY), 5)
    k0 = C.smooth(C.clamp((lt - 1.8) / 0.4))
    for f in range(NF):
        y1 = GY - f * FH
        y0 = y1 - FH
        pygame.draw.line(s, (120, 124, 130), (BX, y0), (LIFT[1], y0), 2)
        lab = text("GF" if f == 0 else str(f), "mono", 26, INK)
        s.blit(lab, lab.get_rect(midright=(BX - 16, y0 + FH // 2)))
        k = k0 if f == 0 else 0.0
        dx, dy = int(30 * k), int(-20 * k)
        for i in range(3):
            wx, wy = 1086 + i * 128, y0 + 14
            if k > 0:
                pygame.draw.polygon(s, (150, 150, 150), [(wx + 90, wy), (wx + 90 + dx, wy + dy),
                                                         (wx + 90 + dx, wy + 32 + dy), (wx + 90, wy + 32)])
                pygame.draw.polygon(s, (190, 190, 190), [(wx, wy), (wx + dx, wy + dy),
                                                         (wx + 90 + dx, wy + dy), (wx + 90, wy)])
            pygame.draw.rect(s, (250, 246, 226) if k > 0 else (84, 90, 98), (wx, wy, 90, 32))
            pygame.draw.rect(s, (20, 20, 24), (wx, wy, 90, 32), 2)
        sx0, sx1 = STAIR if f % 2 == 0 else STAIR[::-1]
        for j in range(8):                     # the stairs, one flight per floor
            xa = sx0 + (sx1 - sx0) * j / 8
            xb = sx0 + (sx1 - sx0) * (j + 1) / 8
            ya = y1 - FH * j / 8
            pygame.draw.line(s, INK, (xa, ya), (xb, ya), 3)
            pygame.draw.line(s, INK, (xb, ya), (xb, ya - FH / 8), 3)
    if k0 > 0:
        pygame.draw.rect(s, (255, 255, 255), (BX - 4, GY - FH - 4, LIFT[1] - BX + 8, FH + 8), 5)
        if lt < 2.6:                           # arrival burst
            b = C.clamp((lt - 1.8) / 0.8)
            pygame.draw.circle(s, (255, 255, 255), (990, GY - 30), int(40 + 420 * b), max(1, int(10 * (1 - b))))
        lab = text("NOW DEEP", "oswald", 40, (20, 20, 24))
        r = lab.get_rect(midleft=(LIFT[1] + 30, GY - FH // 2)).inflate(24, 8)
        pygame.draw.rect(s, (255, 255, 255), r)
        lab.set_alpha(int(255 * k0))
        s.blit(lab, lab.get_rect(center=r.center))
    # the lift: stuck at 4, then it gives up
    pygame.draw.rect(s, (24, 26, 30), (LIFT[0], top, LIFT[1] - LIFT[0], NF * FH))
    pygame.draw.rect(s, INK, (LIFT[0], top, LIFT[1] - LIFT[0], NF * FH), 3)
    drop = C.clamp((lt - 7.7) / 0.3) ** 2
    bounce = 10 * math.sin(C.clamp((lt - 8.0) / 0.3) * math.pi) * (lt > 8.0)
    cy = C.lerp(GY - 4 * FH, GY, drop) - bounce
    if drop < 1:
        pygame.draw.line(s, INK, ((LIFT[0] + LIFT[1]) // 2, top), ((LIFT[0] + LIFT[1]) // 2, cy - FH + 6), 2)
    pygame.draw.rect(s, (110, 114, 120), (LIFT[0] + 8, cy - FH + 6, LIFT[1] - LIFT[0] - 16, FH - 8))
    if lt >= 7.7:
        on = int(lt * 4) % 2 == 0 or lt < 8.4
        sign = text("OUT OF ORDER", "oswald", 34, (255, 255, 255) if on else (140, 140, 140))
        r = sign.get_rect(center=((LIFT[0] + LIFT[1]) // 2, GY + 44)).inflate(24, 10)
        pygame.draw.rect(s, (20, 20, 24), r)
        pygame.draw.rect(s, (255, 255, 255), r, 3)
        s.blit(sign, sign.get_rect(center=r.center))
    # tenth floor, waiting
    if lt >= 3.7:
        a = C.clamp((lt - 3.7) / 0.3)
        wx, wy = 1086 + 2 * 128, top + 18
        pygame.draw.rect(s, (230, 230, 230), (wx + 36, wy + 4, 18, 16))
        pygame.draw.rect(s, (230, 230, 230), (wx + 26, wy + 20, 38, 12))
        pulse = int(3 + 2 * math.sin(lt * 6))
        pygame.draw.rect(s, (255, 255, 255), (BX - 6, top - 6, LIFT[1] - BX + 12, FH + 10), pulse)
        b = text("STILL WAITING", "oswald", 34, (20, 20, 24))
        r = b.get_rect(midleft=(LIFT[1] + 30, top + FH // 2)).inflate(26, 12)
        bub = pygame.Surface(r.size, pygame.SRCALPHA)
        bub.fill((240, 236, 226, int(255 * a)))
        s.blit(bub, r)
        b.set_alpha(int(255 * a))
        s.blit(b, b.get_rect(center=r.center))
    # depth arrives at the door, then takes the stairs (slowly)
    if lt >= 1.8:
        if lt < 5.7:
            x, y = 990, GY
        else:
            p = 0.11 * (lt - 5.7)
            x, y = STAIR[0] + (STAIR[1] - STAIR[0]) * p, GY - FH * p
        depth_man(s, int(x), int(y), lt)
    if lt >= 6.6:
        a = C.clamp((lt - 6.6) / 0.3)
        for i, (ln, sz) in enumerate((("ETA 10TH FLOOR:", 30), ("2031", 64))):
            e = text(ln, "mono" if i == 0 else "oswald", sz, INK)
            e.set_alpha(int(255 * a))
            s.blit(e, (LIFT[1] + 30, GY - 6 * FH + i * 40))
    return s


def sh_rule3(lt, t):
    s = flats(lt, t)
    if OVERLAYS["on"]:
        rule_panel(s, 3, lt)
    return s


def dashed_rect(s, rect, col, w=4, dash=22):
    x, y, rw, rh = rect
    for a, b in (((x, y), (x + rw, y)), ((x + rw, y), (x + rw, y + rh)),
                 ((x + rw, y + rh), (x, y + rh)), ((x, y + rh), (x, y))):
        n = int(math.hypot(b[0] - a[0], b[1] - a[1]) // dash)
        for i in range(0, n, 2):
            p0 = (a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
            p1 = (a[0] + (b[0] - a[0]) * (i + 1) / n, a[1] + (b[1] - a[1]) * (i + 1) / n)
            pygame.draw.line(s, col, p0, p1, w)


def sh_rule4(lt, t):
    sx = 300 if OVERLAYS["on"] else 0
    s = pygame.Surface((OW, OH))
    s.fill((40, 42, 46))
    s.blit(up3(window.render(lt)), (sx, 0))
    if lt >= 2.4:                                # his TV is showing depth
        fl = pygame.Surface((560, 640), pygame.SRCALPHA)
        fl.fill((210, 225, 255, int(16 + 16 * abs(math.sin(lt * 13)) + 8 * math.sin(lt * 31))))
        s.blit(fl, (sx + 620, 120))
        dashed_rect(s, (sx + 580, 90, 640, 700), (255, 255, 255))
        lab = text("DEPTH DETECTED", "mono", 30, (255, 255, 255), outline=2)
        s.blit(lab, (sx + 590, 50))
    if lt >= 1.0:
        a = C.clamp((lt - 1.0) / 0.25)
        box = pygame.Surface((300, 150), pygame.SRCALPHA)
        box.fill((12, 12, 16, int(220 * a)))
        pygame.draw.rect(box, RED, (0, 0, 300, 150), 4)
        clock = text("19:58" if int(lt * 2) % 2 == 0 else "19 58", "oswald", 96, (255, 255, 255))
        box.blit(clock, clock.get_rect(center=(150, 66)))
        box.blit(text("BEFORE 20:00", "mono", 22, (200, 200, 200)), (78, 116))
        s.blit(box, (OW - 360, 150))
    if lt >= 4.4:
        k = C.smooth(C.clamp((lt - 4.4) / 0.25))
        tip = (sx + 1010, 280)
        tail = (int(tip[0] + 300 * k), int(tip[1] + 160 * k))
        pygame.draw.line(s, RED, tail, tip, 14)
        pygame.draw.polygon(s, RED, [tip, (tip[0] + 54, tip[1] - 2), (tip[0] + 28, tip[1] + 46)])
        lab = text("SUSPECT", "oswald", 64, RED, outline=3)
        s.blit(lab, lab.get_rect(midleft=(tail[0] - 40, tail[1] + 50)))
    stamp(s, lt - 5.6, ["REPORT", "TEL 25-25-25"], (sx + 1080, 600), angle=-8, scale=0.9, paper=True)
    if OVERLAYS["on"]:
        rule_panel(s, 4, lt)
    return s


# ── the switch: a depth wave sweeps the flat map into 2.5D ───────────────
WAVE = 1.6


def wave_r(t):
    return C.smooth(C.clamp((t - SWITCH) / WAVE)) * 1.05


_WG = {}


def sh_wave(lt, t):
    ct = 2.0 + lt                              # clip 4.0 = SWITCH; the 2.5D camera tilts from clip 5.6
    if t < SWITCH:
        return clip("wave_2d").frame(ct)
    if t >= SWITCH + WAVE:
        return clip("wave_3d").frame(ct, zoom=C.lerp(1.0, 1.07, C.smooth(C.clamp((t - 77.6) / 2.4))), pop=True)
    if not _WG:
        yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32)
        dx, dy = xx - OW / 2, yy - OH / 2
        nr = np.sqrt(dx * dx + dy * dy) + 1e-3
        rg = np.random.default_rng(5)
        _WG.update(x=xx, y=yy, ux=dx / nr, uy=dy / nr, ang=rg.uniform(0, math.tau, 110),
                   off=rg.uniform(0, 1, 110), ln=rg.uniform(10, 46, 110), dm=float(_d.max()))
    r = wave_r(t)

    def arr(s):
        return np.frombuffer(pygame.image.tobytes(s, "RGB"), np.uint8).reshape(OH, OW, 3)
    a2, a3 = arr(clip("wave_2d").frame(ct)), arr(clip("wave_3d").frame(ct, pop=True))
    comp = np.where((WIPE < r)[..., None], a3, a2)
    disp = 34.0 * np.exp(-((WIPE - r) / 0.035) ** 2)
    comp = cv2.remap(comp, _WG["x"] - _WG["ux"] * disp, _WG["y"] - _WG["uy"] * disp, cv2.INTER_LINEAR)
    s = pygame.image.frombytes(np.ascontiguousarray(comp).tobytes(), (OW, OH), "RGB")
    dm = _WG["dm"]
    for i in range(110):                       # sparks riding just inside the wave front
        rho = r - 0.008 - _WG["off"][i] * 0.05
        if rho <= 0.01:
            continue
        a = _WG["ang"][i] + 0.02 * math.sin(t * 20 + i)
        x, y = OW / 2 + math.cos(a) * rho * dm * OW / 2, OH / 2 + math.sin(a) * rho * dm * OH / 2
        ln = _WG["ln"][i] * (1.2 - 0.6 * _WG["off"][i])
        pygame.draw.line(s, (255, 214, 120), (x, y), (x - math.cos(a) * ln, y - math.sin(a) * ln), 3)
        pygame.draw.circle(s, (255, 250, 230), (int(x), int(y)), 3)
    return s


def lever_t(t):
    return C.smooth(C.clamp((t - 64.15) / 0.3))


SHOTS = [
    (0.0, 3.7, sh_test),
    (3.7, 12.0, sh_studio("mid", t0=3.7)),
    (12.0, 19.0, sh_studio("close", t0=12.0)),
    (19.0, 25.0, sh_studio("wide", "worried", t0=19.0)),
    (25.0, 31.9, sh_rule1),
    (31.9, 40.1, sh_rule2),
    (40.1, 50.0, sh_rule3),
    (50.0, 58.6, sh_rule4),
    (58.6, 63.4, sh_palace("front", flourish=lambda t: C.clamp((t - 59.1) / 0.5) - C.clamp((t - 60.9) / 0.6))),
    (63.4, 65.0, sh_palace("lever", lever=lever_t)),
    (65.0, 65.7, sh_palace("wide", lever=1.0)),
    (65.7, 66.7, sh_palace("side", lever=1.0, whisper=True, turn=1.0)),
    (66.7, 69.9, sh_palace("tech", lever=1.0, tech_in=lambda t: C.clamp((t - 66.7) / 0.8))),
    (69.9, 70.6, sh_palace("kick", lever=1.0, turn=1.0, tech_in=1.0,
                           kick=lambda t: C.clamp((t - 70.05) / 0.5))),
    (70.6, 71.0, sh_static),
    (71.0, 80.0, sh_wave),
    (80.0, 84.0, sh_clip("m4_3d", 22.0)),
    (84.0, 88.5, sh_clip("m2_3d", 3.0)),
    (88.5, 94.0, sh_clip("m3_3d", 2.0)),
    (94.0, 95.9, sh_clip("m4_3d", 0.5)),
    (95.9, 97.8, sh_clip("m1_2d", 2.0)),
    (97.8, 101.8, sh_clip("m4_3d", 100.0)),
    (101.8, 105.4, sh_clip("m4_3d", 6.5)),
    (105.4, 110.0, sh_clip("mp", 15.0)),
    (110.0, 112.2, sh_clip("m4_3d", 131.0)),
    (112.2, 117.4, sh_flat("gran", "angry")),
    (117.4, 120.4, sh_flat("tv", "worried")),
    (120.4, 127.0, sh_window),
    (127.0, 135.6, sh_press("mid", chest=0.0)),
    (135.6, 141.0, sh_press("close", chest=0.2)),
    (141.0, 146.1, logo_card),
    (146.1, 151.9, soon_card),
    (151.9, 156.0, sh_studio("close", t0=151.9)),
    (156.0, 157.1, sh_leak),
    (157.1, 159.4, sh_studio("close", "worried", t0=157.1)),
    (159.4, 165.4, sh_studio("mid", "grin", t0=159.4)),
    (165.4, END, sh_card),
]


OVERLAYS = {"on": True}   # shorts.py turns the 16:9 overlays off and lays out its own
FLASH_CUTS = [80.0, 84.0, 88.5, 94.0, 97.8, 101.8, 105.4, 110.0, 141.0, 156.0]


def is_bw(t):
    return t < SWITCH or 95.9 <= t < 97.8


# ── grade ────────────────────────────────────────────────────────────────
yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32)
_d = np.sqrt(((xx - OW / 2) / (OW / 2)) ** 2 + ((yy - OH / 2) / (OH / 2)) ** 2)
VIG = (1.0 - 0.28 * np.clip(_d - 0.45, 0, 1) ** 1.5)[..., None]
SCAN_BW = (1.0 - 0.16 * ((yy.astype(int) % 3) == 0))[..., None] * VIG
SCAN_C = (1.0 - 0.06 * ((yy.astype(int) % 3) == 0))[..., None] * VIG
WIPE = (_d / _d.max())
del yy, xx
_rg = np.random.default_rng(7)
GRAIN = [_rg.normal(0, 9, (OH // 2, OW // 2)).astype(np.float32) for _ in range(6)]
LUMA = np.array([0.299, 0.587, 0.114], np.float32)


def grade(surf, t):
    a = np.frombuffer(pygame.image.tobytes(surf, "RGB"), np.uint8).reshape(OH, OW, 3).astype(np.float32)
    col = a * SCAN_C
    if not is_bw(t):
        col += cv2.resize(GRAIN[int(t * FPS) % 6], (OW, OH), interpolation=cv2.INTER_NEAREST)[..., None] * 0.35
    need_bw = is_bw(t) or (SWITCH <= t < SWITCH + WAVE)
    if need_bw:
        g = cv2.resize(GRAIN[int(t * FPS) % 6], (OW, OH), interpolation=cv2.INTER_NEAREST)
        y = 255.0 * (np.maximum(a @ LUMA, 0) / 255.0) ** 0.72
        y = (y - 128.0) * 1.1 + 128.0 + g
        bw = y[..., None] * np.array([0.97, 1.0, 1.04], np.float32) * SCAN_BW
        if SWITCH <= t < SWITCH + WAVE:
            r = wave_r(t)
            out = np.where((WIPE < r)[..., None], col, bw)
            out += np.exp(-((WIPE - r) / 0.012) ** 2)[..., None] * np.array([255, 235, 170], np.float32)
            out += np.exp(-((WIPE - r) / 0.05) ** 2)[..., None] * np.array([120, 80, 20], np.float32)
        else:
            out = bw
    else:
        out = col
    out = np.clip(out, 0, 255).astype(np.uint8)
    # vertical roll on the cold-open cut and coming out of the static
    for a0, a1, amt in ((3.55, 3.95, 340), (70.95, 71.3, 500)):
        if a0 <= t < a1:
            k = (t - a0) / (a1 - a0)
            sft = int(amt * (1 - k) ** 2)
            out = np.roll(out, sft, axis=0)
            out[max(0, sft - 18):sft] = 0
    return out


def compose(t):
    for a, b, fn in SHOTS:
        if a <= t < b:
            s = fn(t - a, t)
            break
    else:
        s = pygame.Surface((OW, OH))
    if s.get_size() != (OW, OH):
        s = pygame.transform.scale(s, (OW, OH))
    else:
        s = s.copy()
    for c in FLASH_CUTS:
        if 0 <= t - c < 0.14:
            fl = pygame.Surface((OW, OH))
            fl.fill((255, 255, 255))
            fl.set_alpha(int((230 if c == SWITCH else 120) * (1 - (t - c) / 0.14)))
            s.blit(fl, (0, 0))
    if SWITCH <= t < SWITCH + 0.45:
        fl = pygame.Surface((OW, OH))
        fl.fill((255, 250, 235))
        fl.set_alpha(int(90 * (1 - (t - SWITCH) / 0.45) ** 2))
        s.blit(fl, (0, 0))
    if not OVERLAYS["on"]:
        return s
    if 3.7 <= t < 165.4 and not (70.6 <= t < 71.0) and not (141.0 <= t < 152.0):
        bug(s, t)
    chyron(s, t)
    if not (141.0 <= t < 152.0):
        subtitles(s, t)
    if 95.9 <= t < 97.8:
        lab = text("ARCHIVE FOOTAGE", "mono", 40, INK, outline=2)
        s.blit(lab, (80, 70))
    if t >= END - 1.0:
        k = C.clamp((t - (END - 1.0)) / 1.0)
        f = pygame.Surface((OW, OH))
        f.set_alpha(int(255 * k))
        s.blit(f, (0, 0))
    return s


# ── audio ────────────────────────────────────────────────────────────────
def mp3(path, start=0.0, dur=None):
    cmd = ["ffmpeg", "-v", "error", "-ss", str(start), "-i", path]
    if dur:
        cmd += ["-t", str(dur)]
    cmd += ["-f", "f32le", "-ac", "2", "-ar", str(SR), "-"]
    x = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32)
    return x.reshape(-1, 2).copy()


def bandpass(x, lo, hi):
    X = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(x.shape[0], 1.0 / SR)
    g = np.clip(np.minimum((f - lo * 0.7) / (lo * 0.3), (hi * 1.3 - f) / (hi * 0.3)), 0, 1)
    return np.fft.irfft(X * g[:, None], n=x.shape[0], axis=0).astype(np.float32)


def db(v):
    return 10 ** (v / 20.0)


def put(buf, x, t, gain_db=0.0, pan=0.0):
    if x.ndim == 1:
        a = (pan + 1) * math.pi / 4
        x = np.stack([x * math.cos(a) * 1.41, x * math.sin(a) * 1.41], -1)
    i = int(t * SR)
    if i >= len(buf):
        return
    x = x[:len(buf) - i] * db(gain_db)
    buf[i:i + len(x)] += x


_sfx = {}


def sfx(name):
    if name not in _sfx:
        x, sr = read_wav(os.path.join(SFX, name + ".wav"))
        _sfx[name] = resample(x, sr)
    return _sfx[name]


def gain_curve(points, n):
    """Piecewise-linear dB curve [(t, db), ...] -> per-sample gain."""
    ts = np.array([p[0] for p in points]) * SR
    ds = np.array([p[1] for p in points])
    return db(np.interp(np.arange(n), ts, ds)).astype(np.float32)[:, None]


def foley(buf, name, off, t0, t1, path=None, go=0.0):
    p = path or os.path.join(CLIPS, name + ".foley.json")
    if not os.path.exists(p):
        return
    d = json.load(open(p))
    hz = d.get("hz", 60)
    m = {"player_shot": ("gunshot", -13), "enemy_shot": ("gunshot_distant", -15),
         "enemy_hit": ("bullet_impact_enemy", -17), "hit": ("bullet_impact_enemy", -17)}
    for i, e in enumerate(d["events"]):
        if e["kind"] not in m:
            continue
        ct = go + e["t"] / hz
        gt = t0 + (ct - off)
        if t0 <= gt < t1:
            nm, g = m[e["kind"]]
            put(buf, sfx(nm), gt, g, pan=random.Random(i).uniform(-0.4, 0.4))


def mix(path):
    n = int(END * SR)
    vo = np.zeros((n, 2), np.float32)
    for vid, t0, _ in VO:
        put(vo, vo_clip(vid), t0 - 0.06, 3.0 if vid == "R02" else 0.0)
    # TV-speaker colour on everything said before the switch
    pre = int(SWITCH * SR)
    vo[:pre] = 0.75 * vo[:pre] + 0.25 * bandpass(vo[:pre], 250, 5000)
    voice_env = np.abs(vo).max(axis=1)
    k = int(0.25 * SR)
    voice_env = np.convolve(voice_env, np.ones(k, np.float32) / k, mode="same")
    duck = db(-10 * np.clip(voice_env / 0.04, 0, 1))[:, None].astype(np.float32)

    mus = np.zeros((n, 2), np.float32)
    muz = mp3(os.path.join(OST, "11_old_friends.mp3"), 8.0, 62.0)
    muz = bandpass(muz, 400, 3200)
    muz *= gain_curve([(0, -60), (0.6, -21), (60.0, -21), (60.6, -40)], len(muz))
    put(mus, muz, 3.7)
    # the lever does nothing: the muzak drops out under it
    mus[int(64.35 * SR):int(71.0 * SR)] *= 0.0
    main = mp3(os.path.join(OST, "01_call_of_acaristan.mp3"), 0.0, 156.0 - SWITCH)
    tv = bandpass(main, 350, 3500)
    L = len(main)
    rel = lambda a: a - SWITCH  # noqa: E731
    g_full = gain_curve([(0, -40), (rel(73.5), -5), (rel(112.0), -6), (rel(112.4), -60), (rel(120.2), -60),
                         (rel(120.6), -9), (rel(127.0), -12), (rel(140.8), -12), (rel(141.0), -3),
                         (rel(155.8), -4), (rel(156.0), -60)], L)
    g_tv = gain_curve([(0, -60), (rel(112.0), -60), (rel(112.4), -16), (rel(120.2), -16), (rel(120.6), -60)], L)
    put(mus, main * g_full + tv * g_tv, SWITCH)
    leak = mp3(M6_SRC, 20.0, 1.1)
    put(mus, leak, 156.0, -4)
    mus *= duck

    fx = np.zeros((n, 2), np.float32)
    tone = 0.25 * np.sin(2 * np.pi * 1000 * np.arange(int(3.65 * SR)) / SR).astype(np.float32)
    put(fx, tone, 0.05, -10)
    t_end = np.arange(int(2.4 * SR)) / SR
    put(fx, (0.25 * np.sin(2 * np.pi * 1000 * t_end) * np.clip((2.4 - t_end) / 0.6, 0, 1)).astype(np.float32),
        168.2, -14)
    put(fx, sfx("crt_thunk"), 3.65, -6)
    put(fx, sfx("crt_thunk"), 64.4, -3, pan=0.3)
    put(fx, sfx("melee_hit"), 70.4, -2, pan=0.2)
    put(fx, sfx("crt_thunk"), 70.45, -2)
    put(fx, sfx("radio_static")[:int(0.4 * SR)], 70.6, -6)
    w = sfx("crt_whine")[:int(2.0 * SR)]
    put(fx, w * np.linspace(0.2, 1.0, len(w), dtype=np.float32), 71.0, -16)
    put(fx, sfx("rig_low_boom"), SWITCH, -6)
    for name, a, b, off in (("m2_3d", 84.0, 88.5, 3.0), ("m3_3d", 88.5, 94.0, 2.0)):
        foley(fx, name, off, a, b)
    foley(fx, "mp", 15.0, 105.4, 110.0, path=os.path.join(OUT, "mp", "host_flow.foley.json"), go=13.067)
    rng = random.Random(5)
    for a, b in ((80.0, 84.0), (97.8, 101.8), (110.0, 112.2)):   # M4 has no foley log
        t = a + 0.3
        while t < b:
            put(fx, sfx(rng.choice(["gunshot", "gunshot_distant"])), t, -16, pan=rng.uniform(-0.5, 0.5))
            t += rng.uniform(0.12, 0.45)
    put(fx, sfx("rain"), 94.0, -18)
    for a, b in ((127.0, 135.6), (135.6, 141.0)):           # press camera shutters (same RNG as the set)
        for kk in range(int((b - a) * 7)):
            if random.Random(kk).random() < 0.45:
                put(fx, sfx("type_tick"), a + kk / 7.0, -12, pan=random.Random(kk + 99).uniform(-0.6, 0.6))
    put(fx, sfx("melee_hit"), 139.7, 0)
    put(fx, sfx("concrete_impact"), 139.72, -6)
    put(fx, sfx("rig_low_boom"), 141.0, -5)
    put(fx, sfx("melee_hit"), 148.1, -2)
    put(fx, sfx("radio_static")[:int(0.25 * SR)], 155.9, -8)
    put(fx, sfx("radio_static")[:int(0.25 * SR)], 157.0, -8)
    put(fx, sfx("concrete_impact"), 165.4 + 2.0, -3)
    out = vo * db(1.0) + mus + fx
    fade = np.clip((END - np.arange(n) / SR) / 1.0, 0, 1)[:, None]
    out *= fade
    pk = np.abs(out).max()
    out = np.tanh(out / max(pk, 1e-6) * 1.4) / math.tanh(1.4) * db(-1.0)
    with wave.open(path, "wb") as wv:
        wv.setnchannels(2)
        wv.setsampwidth(2)
        wv.setframerate(SR)
        wv.writeframes((out * 32767).astype("<i2").tobytes())


# ── main ─────────────────────────────────────────────────────────────────
def main():
    global TEST, CARD43
    args = sys.argv[1:]

    def opt(k, d=None):
        return args[args.index(k) + 1] if k in args else d
    pygame.init()
    pygame.display.set_mode((64, 64))
    TEST = test_card()
    CARD43 = test_card(480, 360)
    if "--stills" in args:
        d = opt("--out-dir", OUT)
        for s in opt("--stills").split(","):
            t = float(s)
            img = grade(compose(t), t)
            cv2.imwrite(os.path.join(d, "f_%06.2f.jpg" % t), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            print("still", t, flush=True)
        return
    t0, t1 = float(opt("--from", 0.0)), float(opt("--to", END))
    os.makedirs(OUT, exist_ok=True)
    vid = os.path.join(OUT, "_video.mp4")
    aud = os.path.join(OUT, "_mix.wav")
    if "--no-audio" not in args:
        mix(aud)
        print("audio mixed", flush=True)
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", "%dx%d" % (OW, OH), "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                           "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", vid], stdin=subprocess.PIPE)
    f0, f1 = int(t0 * FPS), int(t1 * FPS)
    for fi in range(f0, f1):
        t = fi / FPS
        ff.stdin.write(grade(compose(t), t).tobytes())
        if fi % 150 == 0:
            print("frame %d / %d" % (fi, f1), flush=True)
    ff.stdin.close()
    ff.wait()
    final = os.path.join(OUT, "announce_25d_trailer.mp4")
    if os.path.exists(aud) and t0 == 0.0 and t1 == END:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-i", aud, "-c:v", "copy", "-c:a", "aac",
                        "-b:a", "192k", "-shortest", final], check=True)
        print("wrote", final)
    else:
        print("wrote", vid)


if __name__ == "__main__":
    main()
