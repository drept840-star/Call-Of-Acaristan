"""Dark story trailer for Call of Acaristan, cut to "Dark Cello Horror Trailer Music".

    python tools/trailer_rpe6/dark.py --at 12 40 76    stills -> outputs/trailer_dark/stills/
    python tools/trailer_rpe6/dark.py --sheet          one still per shot + _sheet.jpg
    python tools/trailer_rpe6/dark.py                  full MP4 (1920x1080, 30 fps, score)
    python tools/trailer_rpe6/dark.py --from 39 --to 60 --noaudio --out part.mp4

A story cut, no engine captions: the drop-off at Valea Seaca, the Guard
coming up the valley, the raid, the farm burning.  Every picture is a new
scene staged on the Mission 7 farm set (dark_films.py) under a gritty grade: bled colour, crushed blacks, heavy grain, shake and a colour
split on the music's hits.  The music starts at T=0; its bar is 3.0 s with
downbeats at 3k+0.04, a drop to silence at 36-39 and the last hit at 93.02.
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
sys.path.insert(0, HERE)
import render as R  # noqa: E402  (paths, SDL, the M6 shots)
import render_m7 as M  # noqa: E402  (the M7 raid shots and films)
import numpy as np  # noqa: E402
import pygame  # noqa: E402

C = R.C
PW, PH, OUT_W, OUT_H, BAR, FPS = R.PW, R.PH, R.OUT_W, R.OUT_H, R.BAR, R.FPS
clamp, smooth, seg, lerp, ease_out = R.clamp, R.smooth, R.seg, R.lerp, R.ease_out
OUT_DIR = os.path.join(R.ROOT, "outputs", "trailer_dark")
MUSIC = os.path.join(R.ROOT, "assets", "music", "newtrailer",
                     "Dark Cello Horror Trailer Music Free Music For Video Creators.mp3")
TOTAL = 104.6
BLOOD = (168, 28, 22)
BONE = (214, 208, 196)
ASH = (128, 124, 118)

STRONG = (6.02, 39.04, 93.02)           # the three big hits: flash, shake, colour split
PULSE = [12.08, 15.1, 18.1, 21.08] + [3 * k + 0.04 for k in range(14, 30)]


def B(k):
    """Downbeat k of the 3.0 s bar."""
    return 3 * k + 0.04


def kick(T):
    """(shake px, colour split px) from the hits just before T."""
    s = c = 0.0
    for h in STRONG:
        d = T - h
        if 0 <= d < 1.2:
            e = math.exp(-d * 6.0)
            s += 16 * e
            c += 12 * math.exp(-d * 9.0)
    for h in PULSE:
        d = T - h
        if 0 <= d < 0.5:
            e = math.exp(-d * 10.0)
            s += 4 * e
            c += 4 * e
    return s, int(c)


# --- the grade ----------------------------------------------------------------------
class Grit:
    """Bled colour, crushed blacks, cold shadows, chunky grain, a hard vignette."""
    def __init__(self):
        rng = np.random.default_rng(23)
        self.n = [(rng.standard_normal((PW // 2, PH // 2)) * 10).astype(np.int32)
                  .repeat(2, 0).repeat(2, 1) for _ in range(6)]
        dx = (np.arange(PW) - PW / 2) / (PW / 2)
        dy = (np.arange(PH) - PH / 2) / (PH / 2)
        self.vig = 1 - np.clip(dx[:, None] ** 2 * 0.55 + dy[None, :] ** 2 * 0.8 - 0.12, 0, 1) * 0.85
        x = np.arange(256)
        y = np.clip((x - 14) / 241.0, 0, 1) ** 1.22 * 255
        lo = (1 - y / 255) ** 3
        self.lut = [np.clip(v, 0, 255).astype(np.uint8)
                    for v in (y * 1.0, y * 0.95 + 3 * lo, y * 0.9 + 11 * lo)]

    def apply(self, surf, n, sat, expo, split):
        a = pygame.surfarray.pixels3d(surf)
        f = a.astype(np.int32)
        L = ((f[..., 0] * 77 + f[..., 1] * 150 + f[..., 2] * 29) >> 8)[..., None]
        f = L + (((f - L) * int(sat * 256)) >> 8)
        f = (f * (self.vig * (256 * expo)).astype(np.int32)[..., None]) >> 8
        f += self.n[n % 6][..., None]
        if split:
            f[..., 0] = np.roll(f[..., 0], split, 0)
            f[..., 2] = np.roll(f[..., 2], -(split // 2), 0)
        np.clip(f, 0, 255, out=f)
        for c in range(3):
            a[..., c] = self.lut[c][f[..., c]]
        del a


# --- text ---------------------------------------------------------------------------
def stamp(cv, text, t_in, t_out, lt):
    """Typed location line, lower left, a blood-red bar over it."""
    k = clamp((t_out - lt) / 0.4)
    s = C.typed(text, lt - t_in, 26)
    if lt < t_in or k <= 0 or not s:
        return
    cur = "_" if int(lt * 3) % 2 and len(s) < len(text) else ""
    img = C.font("mono", 24).render(s + cur, True, BONE)
    img.set_alpha(int(255 * k))
    y = BAR + PH - 70
    cv.blit(img, (96, y))
    pygame.draw.rect(cv, BLOOD, (96, y - 12, 40, 3))


def subtitle(cv, who, text, t_in, t_out, lt):
    k = R.fade_in_out(lt, t_in, t_out, 0.25, 0.3)
    if k <= 0:
        return
    img = C.font("mono", 30).render(text, True, (236, 232, 222))
    lab = C.font("monob", 20).render(who, True, BLOOD)
    for s in (img, lab):
        s.set_alpha(int(255 * k))
    y = BAR + PH - 92
    cv.blit(lab, (OUT_W // 2 - lab.get_width() // 2, y - 30))
    cv.blit(img, (OUT_W // 2 - img.get_width() // 2, y))


class Shot(R.Shot):
    sat, expo = 0.42, 1.0
    stamp = None                    # (text, t_in, t_out)
    sub = None                      # (who, text, t_in, t_out)

    def overlay(self, cv, lt, T):
        if self.stamp:
            stamp(cv, *self.stamp, lt)
        if self.sub:
            subtitle(cv, *self.sub, lt)


def live(cls):
    """A render.py / render_m7.py live shot class with the dark overlay and grade knobs."""
    return type("Dark" + cls.__name__, (cls,), {"overlay": Shot.overlay, "sat": Shot.sat,
                                                 "expo": Shot.expo, "stamp": None, "sub": None,
                                                 "cap": None, "line": None})


class Film(live(M.Film)):
    """Any (surface, t_ms) film: M7 via render_m7, the M6 and M5 hosts with their tags off."""
    def setup(self):
        from cutscenes import m6world3d as W6
        if not getattr(W6.finish, "_untagged", False):
            orig = W6.finish

            def finish(surface, seed, tag="", col=(120, 190, 220), t=0, ps2=False):
                orig(surface, seed, "", col, t, ps2)
            finish._untagged = True
            W6.finish = finish
        super().setup()


class Scene(Film):
    """One of the new staged scenes in dark_films.py."""
    scene = "cold_farm"

    def setup(self):
        super().setup()
        import dark_films
        self.fn = getattr(dark_films, self.scene)


class Card(Shot):
    """Words on black.  kind 'card': slow fade; 'slam': hard on the beat; 'quote': typed."""
    kind = "card"
    text = ""
    sat = 0.0

    def setup(self):
        self.pic = pygame.Surface((PW, PH))

    def picture(self, lt, T, n):
        self.pic.fill((0, 0, 0))
        return self.pic

    def overlay(self, cv, lt, T):
        D = self.end - self.start
        fl = 0.9 + 0.1 * random.Random(int(T * FPS)).random()
        if self.kind == "slam":
            k = R.fade_in_out(lt, 0.0, D - 0.05, 0.04, 0.2) * fl
            img = R.spaced(self.text, C.font("oswald", 112), BONE, 12)
            sc = 1.0 + 0.18 * (1 - ease_out(clamp(lt / 0.18)))
        elif self.kind == "quote":
            k = R.fade_in_out(lt, 0.2, D - 0.15, 0.3, 0.5) * fl
            img = C.font("mono", 40).render(C.typed(self.text, lt - 0.3, 30), True, BONE)
            sc = 1.0
            full = C.font("mono", 40).size(self.text)[0]      # typed left to right, not from the middle
        else:
            k = R.fade_in_out(lt, 0.15, D - 0.1, 0.8, 0.45) * fl
            img = R.spaced(self.text, C.font("oswald", 74), BONE, 14)
            sc = 1.0 + 0.04 * (1 - smooth(clamp(lt / D)))
        if k <= 0 or img.get_width() < 2:
            return
        if sc != 1.0:
            img = pygame.transform.smoothscale(img, (int(img.get_width() * sc), int(img.get_height() * sc)))
        img.set_alpha(int(255 * clamp(k)))
        x, y = OUT_W // 2 - img.get_width() // 2, OUT_H // 2 - img.get_height() // 2
        if self.kind == "quote":
            x = OUT_W // 2 - full // 2
        cv.blit(img, (x, y))
        if self.kind == "card":
            w = int(90 * clamp(k))
            pygame.draw.rect(cv, BLOOD, (OUT_W // 2 - w // 2, y + img.get_height() + 14, w, 3))


COLD = [(0.7, "KRAP FIELD CHANNEL // DAY 11", ASH),
        (1.9, "The package is down at Valea Seaca.", BONE),
        (3.6, "Keep him off the roads. Nobody looks up there.", BONE)]
COLD_CPS = 30


def cold_ticks():
    out = []
    for t0, txt, _c in COLD:
        out += [t0 + i / COLD_CPS for i in range(len(txt)) if txt[i] != " "]
    return out


class ColdOpen(Scene):
    """The radio log typed over the farm before dawn, fading up out of black."""
    scene, skip = "cold_farm", 0.0
    expo = 1.4

    def overlay(self, cv, lt, T):
        k = clamp((5.75 - lt) / 0.35)
        for i, (t0, txt, col) in enumerate(COLD):
            s = C.typed(txt, lt - t0, COLD_CPS)
            if not s:
                continue
            img = C.font("mono", 26 if i == 0 else 34).render(s, True, col)
            img.set_alpha(int(255 * k))
            cv.blit(img, (180, OUT_H // 2 - 70 + i * 58 + (0 if i == 0 else 10)))
        if lt > 0.5:
            pygame.draw.rect(cv, BLOOD, (180, OUT_H // 2 - 92, int(40 * k), 3))


class Title(Shot):
    letterbox = False

    def setup(self):
        rng = random.Random(4)
        self.embers = [(rng.uniform(0, OUT_W), rng.uniform(30, 110), rng.uniform(0, 6.3),
                        rng.uniform(1.5, 5.0), rng.uniform(0, OUT_H)) for _ in range(90)]
        self.bg = R.vgrad((2, 2, 3), (16, 6, 4), OUT_W, OUT_H)
        f = C.font("oswald", 168)
        t = R.spaced("CALL OF ACARISTAN", f, (255, 255, 255), 16)
        grad = R.vgrad((236, 230, 220), (110, 100, 92), *t.get_size())
        t.blit(grad, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        self.title = t
        self.pic = pygame.Surface((PW, PH))

    def picture(self, lt, T, n):
        return self.pic

    def overlay(self, cv, lt, T):
        D = self.end - self.start
        cv.blit(self.bg, (0, 0))
        for x0, sp, ph, sz, y0 in self.embers:
            y = OUT_H + 20 - (y0 + lt * sp) % (OUT_H + 60)
            x = x0 + 22 * math.sin(lt * 0.7 + ph)
            fl = 0.4 + 0.35 * math.sin(lt * 6 + ph * 3)
            C.glow(cv, x, y, sz * 2.0, (int(150 * fl), int(40 * fl), int(12 * fl)))
        sh, _ = kick(T)
        rng = random.Random(int(T * FPS))
        dx, dy = int(rng.uniform(-sh, sh)), int(rng.uniform(-sh, sh))
        out = 1 - smooth(seg(lt, D - 1.6, D - 0.2))
        k1 = clamp(lt / 0.06) * (1 - smooth(seg(lt, 5.2, 5.9)))
        if k1 > 0:
            sc = 1.0 + 0.1 * (1 - ease_out(clamp(lt / 0.5)))
            img = pygame.transform.smoothscale(self.title, (int(self.title.get_width() * sc),
                                                            int(self.title.get_height() * sc)))
            img.set_alpha(int(255 * k1))
            cv.blit(img, (OUT_W // 2 - img.get_width() // 2 + dx, OUT_H // 2 - img.get_height() // 2 - 40 + dy))
            k = R.fade_in_out(lt, 1.6, 5.6, 0.8, 0.4)
            if k > 0:
                s = R.spaced("MISSION 7 // FALLOW GROUND", C.font("mono", 34), BLOOD, 14)
                s.set_alpha(int(255 * k))
                cv.blit(s, (OUT_W // 2 - s.get_width() // 2, OUT_H // 2 + 112))
        for txt, t0, y in (("DUTY.", 6.0, -50), ("OR REVENGE.", 7.0, 50)):
            k = clamp((lt - t0) / 0.5) * out
            if k > 0:
                s = R.spaced(txt, C.font("oswald", 96), BONE if t0 < 7 else BLOOD, 12)
                s.set_alpha(int(255 * k))
                cv.blit(s, (OUT_W // 2 - s.get_width() // 2, OUT_H // 2 + y - s.get_height() // 2 - 40))
        k = clamp((lt - 8.6) / 0.6) * out
        if k > 0:
            for txt, fnt, col, y in (("COMING SOON", C.font("mono", 28), ASH, OUT_H // 2 + 130),
                                     ('Music: "Dark Cello Horror Trailer Music"', C.font("mono", 18),
                                      (96, 92, 88), OUT_H - 80)):
                s = R.spaced(txt, fnt, col, 10 if txt == "COMING SOON" else 1)
                s.set_alpha(int(255 * k))
                cv.blit(s, (OUT_W // 2 - s.get_width() // 2, y))


# --- timeline -----------------------------------------------------------------------
def build():
    S = Scene
    q = 0.75                            # a quarter bar in the climax
    return [
        ColdOpen(0.0, 6.02, fade=(3.2, 0.25)),
        # the pulses: one picture or one card per hit
        S(6.02, B(3), scene="heli_leave", skip=0.2, expo=0.85),
        Card(B(3), 12.08, text="NO ROAD HOME."),
        S(12.08, 15.1, scene="field_wide", skip=0.0, expo=0.85, sat=0.32,
          stamp=("VALEA SEACA // DAWN", 0.4, 2.7)),
        Card(15.1, 18.1, text="SO HE WENT TO GROUND."),
        S(18.1, 21.08, scene="bodi_look", skip=0.0, expo=0.85, sat=0.32),
        # the build: the Guard comes up the valley
        S(21.08, 22.58, scene="well", skip=0.3, expo=1.15, sat=0.36),
        S(22.58, B(8), scene="valley", skip=0.6, expo=0.85, sat=0.3),
        S(B(8), B(9), scene="dusk_road", skip=0.0, expo=1.4,
          stamp=("THE VALLEY ROAD // NIGHT", 0.3, 2.6)),
        S(B(9), B(9) + 1.5, scene="torchline", skip=0.6, expo=1.3),
        S(B(9) + 1.5, B(10), scene="dog_run", skip=0.4, expo=1.3),
        S(B(10), B(11), scene="three_gate", skip=0.0, expo=1.3),
        # the drop to silence
        S(B(11), 34.9, scene="porch", skip=0.0, expo=0.9, fade=(0.3, 0.9)),
        Card(34.9, B(13), kind="quote", text="\"There's nothing left to come back to.\""),
        # the raid: every slot a different shot
        S(B(13), B(14), scene="cover_fire", skip=0.0, expo=1.3),
        S(B(14), B(14) + 1.5, scene="guard_aim", skip=0.3, expo=1.3),
        S(B(14) + 1.5, B(15), scene="guard_down", skip=0.0, expo=1.3),
        S(B(15), B(16), scene="alex_pinned", skip=0.0, expo=1.3),
        Card(B(16), B(16) + 1.5, kind="slam", text="THEY CAME AT NIGHT."),
        S(B(16) + 1.5, B(17), scene="headlights", skip=1.8, expo=1.3),
        S(B(17), B(18), scene="bodi_aim", skip=0.0, expo=1.3),
        S(B(18), B(18) + 1.5, scene="gate_entry", skip=0.5, expo=1.3),
        S(B(18) + 1.5, B(19), scene="biribel_run", skip=0.2, expo=1.3),
        S(B(19), B(19) + 1.5, scene="officer_lamp", skip=0.4, expo=1.3),
        S(B(19) + 1.5, B(20), scene="alex_fire", skip=0.5, expo=1.3),
        S(B(20), B(21), scene="torch_house", skip=0.3, expo=1.0, sat=0.6),
        Card(B(21), B(21) + 1.5, kind="slam", text="THEY BURNED IT ALL."),
        S(B(21) + 1.5, B(22), scene="fire_window", skip=0.4, sat=0.7),
        S(B(22), B(23), scene="house_wide_burn", skip=0.0, sat=0.75),
        S(B(23), B(24), scene="ember_sky", skip=0.0, sat=0.75),
        S(B(24), B(25), scene="bodi_grief", skip=0.0, sat=0.7, expo=1.2),
        S(B(25), B(26), scene="fire_walk", skip=0.0, sat=0.75),      # the roof falls on the half bar
        # the climax: quarter bars, half bars, quarter bars, mostly fresh moments
        S(B(26), B(26) + q, scene="cover_fire", skip=1.75, expo=1.3),
        S(B(26) + q, B(26) + 2 * q, scene="guard_down", skip=0.2, expo=1.3),
        S(B(26) + 2 * q, B(26) + 3 * q, scene="alex_fire", skip=1.0, expo=1.3),
        S(B(26) + 3 * q, B(27), scene="dog_run", skip=1.3, expo=1.3),
        S(B(27), B(27) + 1.5, scene="three_gate", skip=1.5, expo=1.3),
        S(B(27) + 1.5, B(28), scene="headlights", skip=0.4, expo=1.3),
        S(B(28), B(28) + q, scene="bodi_aim", skip=1.6, expo=1.3),
        S(B(28) + q, B(28) + 2 * q, scene="guard_aim", skip=1.2, expo=1.3),
        S(B(28) + 2 * q, B(28) + 3 * q, scene="biribel_run", skip=1.6, expo=1.3),
        S(B(28) + 3 * q, B(29), scene="officer_lamp", skip=1.0, expo=1.3),
        # the fall
        S(B(29), 89.9, scene="biribel_fire", skip=0.6, sat=0.7, expo=1.3),
        S(89.9, 92.9, scene="bodi_rifle", skip=0.0, sat=0.7, fade=(0.2, 0.8),
          sub=("BODI", "\"I'm coming with you.\"", 1.1, 2.6)),
        Card(92.9, 93.02, text=""),
        Title(93.02, TOTAL),
    ]


# --- render -------------------------------------------------------------------------
class Trailer:
    def __init__(self):
        pygame.init()
        pygame.display.set_mode((64, 64))
        self.shots = build()
        self.grit = Grit()
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
        sh, split = kick(T)
        if s.letterbox:
            if surf.get_size() == (PW, PH):
                self.pic.blit(surf, (0, 0))
            else:
                pygame.transform.scale(surf, (PW, PH), self.pic)
            self.grit.apply(self.pic, n, getattr(s, "sat", 0.42), getattr(s, "expo", 1.0), split)
            if s.fade:
                k = min(clamp(lt / s.fade[0]), clamp((s.end - T) / s.fade[1]))
                if k < 1:
                    v = int(255 * (1 - smooth(k)))
                    self.pic.fill((v, v, v), special_flags=pygame.BLEND_RGB_SUB)
            rng = random.Random(n * 7 + 1)
            dx, dy = int(rng.uniform(-sh, sh)), int(rng.uniform(-sh, sh) * 0.6)
            cv.blit(self.pic, (dx, BAR + dy))
            cv.fill((0, 0, 0), (0, 0, OUT_W, BAR))
            cv.fill((0, 0, 0), (0, BAR + PH, OUT_W, OUT_H - BAR - PH))
        s.overlay(cv, lt, T)
        for t0 in STRONG:
            d = T - t0
            if 0 <= d < 0.35:
                v = int(200 * math.exp(-d * 12.0))
                cv.fill((v, v, v), special_flags=pygame.BLEND_RGB_ADD)
        if T > TOTAL - 1.0:
            v = int(255 * smooth((T - (TOTAL - 1.0)) / 1.0))
            cv.fill((v, v, v), special_flags=pygame.BLEND_RGB_SUB)
        return cv


# --- sound --------------------------------------------------------------------------
def crackle(dur, seed):
    X = _sfx()
    rng = np.random.default_rng(seed)
    n = int(dur * X.SR)
    x = np.zeros(n)
    for i in rng.integers(0, n - 400, int(dur * 26)):
        x[i:i + 400] += rng.uniform(0.2, 1.0) * X.env_exp(400, 0.002) * rng.standard_normal(400)
    bed = X.band(X.noise(n), 200, 1800) * 0.25
    return X.fade(X.norm(X.band(x, 800, 7000) + bed), 0.2, 0.3)


def static(dur):
    X = _sfx()
    n = int(dur * X.SR)
    t = np.arange(n) / X.SR
    gate = 0.55 + 0.45 * (np.sin(2 * np.pi * 3.1 * t) * np.sin(2 * np.pi * 0.7 * t + 1) > -0.2)
    return X.fade(X.norm(X.band(X.noise(n), 900, 5200) * gate), 0.6, 0.4)


_SFX = {}


def _sfx():
    if not _SFX:
        sys.path.insert(0, os.path.join(R.ROOT, "tools", "trailer3d"))
        import sfx
        _SFX["X"] = sfx
    return _SFX["X"]


def score(ev, out):
    import score as S                   # decode(), click(), impact(), slowed(), wind()
    X = _sfx()
    bus = X.Bus()
    bus.L = np.zeros(int(TOTAL * X.SR) + X.SR)
    bus.R = np.zeros_like(bus.L)
    m = S.decode(MUSIC)
    k = min(len(m), len(bus.L))
    bus.L[:k] += m[:k, 0] * 0.95
    bus.R[:k] += m[:k, 1] * 0.95
    # cold open: the radio log
    bus.add(0.3, static(5.6), -33)
    for t in ev["ticks"]:
        bus.add(t, S.click(), -31 + S.RNG.uniform(-3, 2), pan=S.RNG.uniform(-0.2, 0.2))
    for t in STRONG:
        bus.add(t - 1.1, X.whoosh(1.1, up=True), -22)
        bus.add(t, X.boom(2.6), -9)
    for t in ev["slams"]:
        bus.add(t, X.stamp(), -14)
        bus.add(t, X.boom(1.4), -16)
    for a, b in ev["fire"]:
        bus.add(a, crackle(b - a, int(a * 10)), -24)
    bus.add(ev["collapse"], X.boom(2.0, low=30), -12)
    q0, q1 = ev["quiet"]
    bus.add(q0, S.wind(q1 - q0 + 0.6), -28)
    shot = X.gunshot(tail=0.4)
    for t, kind in ev["events"]:
        if kind == "shot":
            bus.add(t, shot, -13 + S.RNG.uniform(-1.5, 0.5), pan=S.RNG.uniform(-0.15, 0.15))
        elif kind == "shot_slow":
            bus.add(t, S.slowed(X.gunshot(big=True, tail=0.8)), -8)
        elif kind == "hit":
            bus.add(t + 0.03, S.impact(), -21, pan=S.RNG.uniform(-0.4, 0.4))
    mix = np.stack([bus.L, bus.R], 1)[: int(TOTAL * X.SR)]
    tail = int(1.0 * X.SR)
    mix[-tail:] *= np.linspace(1, 0, tail)[:, None] ** 1.5
    ref = np.percentile(np.abs(mix), 99.95) or 1.0
    mix = np.tanh(mix / ref * 1.05) * 0.89 * 0.74
    pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    import wave
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(X.SR)
        w.writeframes(pcm.tobytes())
    print("score ->", out)
    return out


FIRE_SCENES = {"torch_house", "fire_window", "house_wide_burn", "ember_sky", "bodi_grief",
               "fire_walk", "biribel_fire", "bodi_rifle"}


def staged_events(tr, t0, t1):
    """Gunshots and hits of the staged scenes, from dark_films.SHOTS / HITS."""
    import dark_films as D
    out = []
    for s in tr.shots:
        if not isinstance(s, Scene):
            continue
        for table, kind in ((D.SHOTS, "shot"), (D.HITS, "hit")):
            for ms in table.get(s.scene, ()):
                T = s.start + ms / 1000.0 - s.skip
                if s.start <= T < s.end and t0 <= T < t1:
                    out.append((T, kind))
    return out


def video(tr, t0, t1, out, audio=True):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    silent = out if not audio else out[:-4] + "_picture.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
           "%dx%d" % (OUT_W, OUT_H), "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
           "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", silent]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n0, n1 = int(round(t0 * FPS)), int(round(t1 * FPS))
    del R.EVENTS[:]
    st = time.time()
    for n in range(n0, n1):
        T = (n + 0.5) / FPS
        p.stdin.write(pygame.image.tobytes(tr.frame(T, n), "RGB"))
        if (n - n0) % 90 == 0:
            done = n - n0 + 1
            print("frame %d/%d  T=%.1f  %.1f fps" % (done, n1 - n0, T, done / max(time.time() - st, 1e-6)),
                  flush=True)
    p.stdin.close()
    p.wait()
    burn = [s for s in tr.shots if getattr(s, "scene", "") in FIRE_SCENES]
    ev = {"events": sorted(R.EVENTS + staged_events(tr, t0, t1)), "ticks": cold_ticks(),
          "slams": [s.start for s in tr.shots if isinstance(s, Card) and s.kind == "slam"],
          "fire": [(s.start, s.end) for s in burn],
          "collapse": B(25) + 1.5, "quiet": (B(11), B(13))}
    with open(os.path.join(OUT_DIR, "events.json"), "w", encoding="utf-8") as fh:
        json.dump(ev, fh, indent=1)
    print("picture ->", silent, "in %.0fs" % (time.time() - st))
    if audio:
        wav = score(ev, os.path.join(OUT_DIR, "score.wav"))
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
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "acaristan_dark_trailer.mp4"))
    ap.add_argument("--noaudio", action="store_true")
    a = ap.parse_args()
    R.OUT_DIR = OUT_DIR
    tr = Trailer()
    if a.sheet:
        times = [s.start + (s.end - s.start) * 0.6 for s in tr.shots]
        R.sheet(R.stills(tr, times), os.path.join(OUT_DIR, "_sheet.jpg"), cols=6, w=400)
    elif a.at:
        R.stills(tr, a.at)
    else:
        video(tr, a.t0, a.t1, a.out, audio=not a.noaudio)


if __name__ == "__main__":
    main()
