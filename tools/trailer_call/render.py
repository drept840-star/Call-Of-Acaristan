"""THE CALL — 90 s spoiler-safe 2.39:1 widescreen cinematic + gameplay trailer.

    python tools/trailer_call/render.py --sheet              # 1 still per shot + _sheet.jpg
    python tools/trailer_call/render.py --at 4 22 30 52 78   # render specific timestamps
    python tools/trailer_call/render.py --from 28 --to 60 --noaudio --out preview.mp4
    python tools/trailer_call/render.py [--music track.mp3] [--cta "OUT NOW ON ITCH.IO"]
"""
from __future__ import annotations

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
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ACARISTAN_RENDERER", "gl")

for p in (HERE, os.path.join(ROOT, "tools", "trailer3d"), os.path.join(ROOT, "tools"), os.path.join(ROOT, "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import common as C  # noqa: E402
import hud as HUD  # noqa: E402
import numpy as np  # noqa: E402
import pygame  # noqa: E402
import scenes as SC  # noqa: E402
import score as SCORE  # noqa: E402

FPS = 30
OUT_W, OUT_H = 1920, 1080
PW, PH = 1920, 804              # 2.39:1 cinema frame
BAR = (OUT_H - PH) // 2         # 138 px bars top & bottom
TOTAL = SCORE.TOTAL             # 90.0 s
OUT_DIR = SCORE.OUT_DIR
DEFAULT_CTA = "OUT NOW ON ITCH.IO"

BONE = (234, 229, 218)
ASH = (156, 152, 144)
AMBER = (242, 142, 48)
CRIMSON = (196, 40, 32)

BIG_HITS = SCORE.BIG_HITS       # (28.8, 57.6, 80.4)
# Only flash over live 3D act drops (never paint grey over TitleShot at 80.4s!)
FLASH_HITS = (28.8, 57.6)
PULSES = (
    9.6, 22.8, 28.8, 33.6, 38.4, 43.2, 45.6, 50.4, 54.0,
    57.6, 60.0, 62.4, 64.8, 66.0, 67.2, 68.4, 69.0, 69.6, 70.2, 71.1,
    72.0, 73.1, 74.1, 74.95, 75.7, 76.3,
)

COLD_LINES = (
    (0.55, "SIGNAL INTERCEPTED // 04:12", AMBER),
    (1.85, "NO ORDERS LEFT.", BONE),
)
COLD_CPS = 28.0


def clamp(v: float, a: float = 0.0, b: float = 1.0) -> float:
    return a if v < a else b if v > b else v


def smooth(u: float) -> float:
    u = clamp(u)
    return u * u * (3.0 - 2.0 * u)


def ease_out(u: float) -> float:
    u = clamp(u)
    return 1.0 - (1.0 - u) ** 3


def seg(t: float, a: float, b: float) -> float:
    return clamp((t - a) / (b - a)) if b > a else float(t >= a)


def fade_in_out(lt: float, t_in: float, t_out: float, a: float = 0.20, b: float = 0.22) -> float:
    return clamp((lt - t_in) / a) * clamp((t_out - lt) / b)


def spaced(txt: str, fnt: pygame.font.Font, col, spacing: int) -> pygame.Surface:
    glyphs = [fnt.render(ch, True, col) for ch in txt]
    w = sum(g.get_width() for g in glyphs) + spacing * max(0, len(glyphs) - 1)
    s = pygame.Surface((max(1, w), fnt.get_height()), pygame.SRCALPHA)
    x = 0
    for g in glyphs:
        s.blit(g, (x, 0))
        x += g.get_width() + spacing
    return s


def vgrad(top, bot, w: int, h: int) -> pygame.Surface:
    s = pygame.Surface((w, h))
    arr = np.zeros((w, h, 3), dtype=np.uint8)
    u = np.linspace(0.0, 1.0, h, dtype=np.float32)[None, :, None]
    t_arr = np.array(top, dtype=np.float32)[None, None, :]
    b_arr = np.array(bot, dtype=np.float32)[None, None, :]
    # Subtle TPDF dither kills any 8-bit background banding on cards/title
    rng = np.random.default_rng(77)
    dith = (rng.random((w, h, 1), dtype=np.float32) + rng.random((w, h, 1), dtype=np.float32) - 1.0) * 0.9
    arr[:] = np.clip(t_arr + (b_arr - t_arr) * u + dith, 0, 255).astype(np.uint8)
    pygame.surfarray.blit_array(s, arr)
    return s


def kick(T: float) -> tuple[float, int]:
    """(shake px, RGB split px) driven by big hits and climax pulses."""
    sh = sp = 0.0
    for h in BIG_HITS:
        d = T - h
        if 0.0 <= d < 0.85:
            e = math.exp(-d * 7.5)
            sh += 11.0 * e
            sp += 8.0 * math.exp(-d * 10.5)
    for h in PULSES:
        d = T - h
        if 0.0 <= d < 0.36:
            e = math.exp(-d * 12.0)
            sh += 3.2 * e
            sp += 2.6 * e
    return sh, int(sp)


# ---------------------------------------------------------------------------
# Filmic Grade with Anti-Banding TPDF Dither & Shadow Toe Preservation
# ---------------------------------------------------------------------------

GW, GH = SC.RENDER_SIZE


class CinemaGrade:
    """Filmic S-curve with TPDF anti-banding dither, cool shadows, warm highlights & grain."""

    def __init__(self):
        rng = np.random.default_rng(2088)
        # Triangular-PDF anti-banding dither + subtle 35mm grain (destroys sky banding!)
        self.dither = [
            ((rng.random((GW, GH), dtype=np.float32) + rng.random((GW, GH), dtype=np.float32) - 1.0) * 3.8
             + rng.standard_normal((GW, GH)).astype(np.float32) * 3.2)
            for _ in range(8)
        ]
        dx = (np.arange(GW, dtype=np.float32) - GW * 0.5) / (GW * 0.5)
        dy = (np.arange(GH, dtype=np.float32) - GH * 0.5) / (GH * 0.5)
        r2 = dx[:, None] ** 2 * 0.40 + dy[None, :] ** 2 * 0.58
        self.vig = (1.0 - np.clip(r2 - 0.20, 0.0, 1.0) * 0.46).astype(np.float32)

        # Gentle filmic curve with preserved shadow toe (never crushes tractors/silhouettes to black)
        x = np.linspace(0.0, 1.0, 256, dtype=np.float32)
        y = (0.012 + 0.988 * (x ** 1.03)) * 255.0
        lo = (1.0 - y / 255.0) ** 2.4
        hi = (y / 255.0) ** 2.1
        self.lut = [
            np.clip(y * 1.01 + 4.5 * hi, 0, 255).astype(np.uint8),
            np.clip(y * 0.99 + 1.8 * lo + 2.0 * hi, 0, 255).astype(np.uint8),
            np.clip(y * 0.97 + 7.5 * lo, 0, 255).astype(np.uint8),
        ]

    def apply(self, surf: pygame.Surface, frame_n: int, sat: float, expo: float,
              split: int, fade_k: float = 1.0) -> None:
        a = pygame.surfarray.pixels3d(surf)
        f = a.astype(np.float32)
        if abs(sat - 1.0) > 1e-3:
            lum = (f[..., 0] * 0.299 + f[..., 1] * 0.587 + f[..., 2] * 0.114)[..., None]
            f = lum + (f - lum) * sat
        scale = (self.vig * expo)[..., None]
        f = f * scale + self.dither[frame_n % 8][..., None]
        sp = split // 2
        if sp > 0:
            f[..., 0] = np.roll(f[..., 0], sp, axis=0)
            f[..., 2] = np.roll(f[..., 2], -(sp // 2), axis=0)
        idx = np.clip(f, 0.0, 255.0).astype(np.uint8)
        out = np.empty_like(idx)
        for c in range(3):
            out[..., c] = self.lut[c][idx[..., c]]
        # True multiplicative fade -> ZERO dirty bright-dot frames on black transitions!
        if fade_k < 0.999:
            out = np.clip(out.astype(np.float32) * float(fade_k), 0.0, 255.0).astype(np.uint8)
        a[:] = out
        del a


# ---------------------------------------------------------------------------
# Shot Classes
# ---------------------------------------------------------------------------

def _draw_lower_third(cv: pygame.Surface, tag_line: str, main_line: str, k: float) -> None:
    """Unified, high-legibility lower-third scrim anchored cleanly in bottom-left safe area."""
    if k <= 0.01:
        return
    f_tag = C.font("mono", 22)
    f_main = C.font("oswald", 42) if main_line else None
    t_img = f_tag.render(tag_line, True, AMBER)
    m_img = spaced(main_line, f_main, BONE, 4) if main_line else None
    bw = max(t_img.get_width(), m_img.get_width() if m_img else 0) + 46
    bh = (98 if m_img else 48)
    x0 = 64
    y0 = BAR + PH - bh - 32
    scrim = pygame.Surface((bw, bh), pygame.SRCALPHA)
    scrim.fill((8, 10, 14, int(172 * k)))
    pygame.draw.rect(scrim, (*AMBER, int(245 * k)), (0, 0, 4, bh))
    cv.blit(scrim, (x0, y0))
    t_img.set_alpha(int(255 * k))
    cv.blit(t_img, (x0 + 20, y0 + 10))
    if m_img is not None:
        m_img.set_alpha(int(255 * k))
        cv.blit(m_img, (x0 + 20, y0 + 38))


class Shot:
    letterbox = True

    def __init__(self, start: float, end: float, *, name: str = "", sat: float = 0.90,
                 expo: float = 1.02, fade=None, stamp=None, skip: float = 0.0):
        self.start = float(start)
        self.end = float(end)
        self.name = name
        self.sat = sat
        self.expo = expo
        self.fade = fade        # (fade_in_s, fade_out_s)
        self.stamp = stamp      # (tag_line, main_line, t_in, t_out)
        self.skip = skip
        self._ready = False
        self._buf = None

    def ensure(self):
        if not self._ready:
            self.setup()
            self._ready = True

    def setup(self):
        pass

    def picture(self, lt: float, T: float, n: int) -> pygame.Surface:
        if self._buf is None:
            self._buf = pygame.Surface((GW, GH))
        SC.render_scene(self.name, self._buf, int((lt + self.skip) * 1000.0))
        return self._buf

    def overlay(self, cv: pygame.Surface, lt: float, T: float) -> None:
        if self.stamp:
            tag_l, main_l, t_in, t_out = self.stamp
            k = fade_in_out(lt, t_in, t_out, 0.22, 0.28)
            if k > 0.01:
                s_tag = C.typed(tag_l, lt - t_in, 36.0)
                s_main = C.typed(main_l, lt - (t_in + 0.30), 28.0) if main_l else ""
                _draw_lower_third(cv, s_tag or " ", s_main, k)


class ColdOpenShot(Shot):
    def overlay(self, cv: pygame.Surface, lt: float, T: float) -> None:
        k = fade_in_out(lt, 0.35, 4.45, 0.28, 0.35)
        if k <= 0.01:
            return
        s0 = C.typed(COLD_LINES[0][1], lt - COLD_LINES[0][0], COLD_CPS)
        s1 = C.typed(COLD_LINES[1][1], lt - COLD_LINES[1][0], COLD_CPS)
        if s0:
            _draw_lower_third(cv, s0, s1, k)


class GameplayShot(Shot):
    """Real engine gameplay sequence with native 1920x804 minimal tactical HUD."""

    def __init__(self, start: float, end: float, *, name: str, sat: float = 0.94,
                 expo: float = 1.04, fade=None):
        super().__init__(start, end, name=name, sat=sat, expo=expo, fade=fade)

    def overlay(self, cv: pygame.Surface, lt: float, T: float) -> None:
        tm = lt * 1000.0
        if self.name == "gp_mansion_ots":
            shots = (1050, 1200, 1360, 2850, 3000, 3160)
            hits = (1120, 1280, 2920, 3080)
            fired = sum(1 for s in shots if tm >= s)
            rec = SC._recoil_env(tm, shots, 185.0)
            hit_k = SC._recoil_env(tm, hits, 240.0)
            dmg_k = SC._recoil_env(tm, (2230,), 380.0)
            hp = 92 if tm < 2230 else 78
            HUD.draw_tactical_hud(
                cv, BAR, PW, PH, weapon="OS-12", caliber="5.56X45",
                ammo=max(0, 28 - fired), mag=30, reserve=120, hp=hp,
                obj="BREACH THE GRAND HALL", recoil=rec, hit_k=hit_k, dmg_side=dmg_k,
            )
        elif self.name == "gp_chase_lmg":
            shots = (320, 440, 560, 680, 1300, 1420, 1540, 1660)
            hits = (420, 640, 1400, 1640)
            fired = sum(1 for s in shots if tm >= s)
            rec = SC._recoil_env(tm, shots, 120.0)
            hit_k = SC._recoil_env(tm, hits, 220.0)
            HUD.draw_tactical_hud(
                cv, BAR, PW, PH, weapon="RPK-M TURRET", caliber="7.62X54R",
                ammo=max(0, 92 - fired), mag=100, reserve=200, hp=88,
                obj="HOLD ROUTE 12 CONVOY", recoil=rec, hit_k=hit_k,
            )
        elif self.name == "gp_door_gunner":
            ts = lt
            burst_times = [0.75 + i * 0.11 for i in range(11)] + [3.00 + i * 0.11 for i in range(9)]
            shots_ms = [int(b * 1000) for b in burst_times]
            hits_ms = [int((b + 0.34) * 1000) for b in burst_times]
            shots_so_far = sum(1 for bt in burst_times if bt <= ts)
            heat = clamp(0.12 + shots_so_far * 0.032 - max(0.0, ts - 1.95) * (0.14 if ts < 3.0 else 0.06), 0.12, 0.78)
            ads = smooth(clamp((ts - 0.35) / 0.45)) * (1.0 - 0.55 * smooth(clamp((ts - 3.85) / 0.55)))
            flares = 5 - (1 if ts >= 3.85 else 0) - (1 if ts >= 4.10 else 0)
            hit_k = SC._recoil_env(tm, hits_ms, 200.0)
            hdg = (352.0 + ts * 6.0) % 360.0
            lock = (0.50, 0.50) if ts < 2.05 else None
            HUD.draw_flight_hud(
                cv, BAR, PW, PH, heat=heat, flares=flares, heading_deg=hdg,
                ads_k=ads, hit_k=hit_k, obj="DESTROY GUARD CONVOY", lock_norm=lock,
            )
        elif self.name == "gp_checkpoint_ots":
            shots = (380, 1650)
            hits = (430, 1700)
            fired = sum(1 for s in shots if tm >= s)
            rec = SC._recoil_env(tm, shots, 260.0)
            hit_k = SC._recoil_env(tm, hits, 260.0)
            dmg_k = SC._recoil_env(tm, (1280,), 360.0)
            HUD.draw_tactical_hud(
                cv, BAR, PW, PH, weapon="FALLOW 12", caliber="12GA BUCKSHOT",
                ammo=max(0, 6 - fired), mag=6, reserve=24, hp=84,
                obj="CLEAR ROADBLOCK", recoil=rec, hit_k=hit_k, shotgun=True, dmg_side=dmg_k,
            )


class ScopeBreathShot(Shot):
    """Native 1920x804 anti-aliased PSO-1 sniper scope with crisp trigger-pull cut."""
    letterbox = False

    def __init__(self, start: float, end: float, *, sat: float = 0.80, expo: float = 1.05):
        super().__init__(start, end, name="scope_breath", sat=sat, expo=expo)

    def render_full(self, cv: pygame.Surface, grade: CinemaGrade, lt: float, T: float, n: int) -> None:
        tm = int(lt * 1000.0)
        periph_lo, scope_lo = SC.render_scope_passes(tm, (GW, GH))
        fade_in = smooth(clamp(lt / 0.16))
        # Grade both buffers cleanly (zero banding, multiplicative fade-in)
        p_work = periph_lo.copy()
        s_work = scope_lo.copy()
        grade.apply(p_work, n, self.sat, self.expo, 0, fade_k=fade_in)
        grade.apply(s_work, n, self.sat, self.expo, 0, fade_k=fade_in)

        periph_hi = pygame.transform.smoothscale(p_work, (PW, PH))
        scope_hi = pygame.transform.scale(s_work, (PW, PH))

        # Trigger-pull snap on final 2 frames (lt >= 3.52s -> instant hot bloom + recoil before black cut)
        recoil_y = 0
        flash_k = 0.0
        if lt >= 3.52:
            u_s = clamp((lt - 3.52) / 0.08)
            recoil_y = -int(26 * math.sin(u_s * math.pi * 0.6))
            flash_k = 1.0 - 0.55 * u_s
        HUD.composite_pso1_scope(cv, periph_hi, scope_hi, BAR, PW, PH,
                                 recoil_y=recoil_y, flash_k=flash_k)
        cv.fill((0, 0, 0), (0, 0, OUT_W, BAR))
        cv.fill((0, 0, 0), (0, BAR + PH, OUT_W, OUT_H - BAR - PH))


class CardShot(Shot):
    letterbox = False

    def __init__(self, start: float, end: float, text: str, *, accent=CRIMSON, size: int = 104):
        super().__init__(start, end, name="card")
        self.text = text
        self.accent = accent
        self.size = size

    def setup(self):
        rng = random.Random(int(self.start * 100) + 7)
        self.embers = [(rng.uniform(0, OUT_W), rng.uniform(32, 96), rng.uniform(0, 6.28),
                        rng.uniform(1.2, 3.6), rng.uniform(0, OUT_H)) for _ in range(38)]
        self.bg = vgrad((4, 5, 8), (15, 9, 8), OUT_W, OUT_H)
        self.pic = pygame.Surface((PW, PH))

    def picture(self, lt: float, T: float, n: int) -> pygame.Surface:
        return self.pic

    def overlay(self, cv: pygame.Surface, lt: float, T: float) -> None:
        dur = self.end - self.start
        cv.blit(self.bg, (0, 0))
        for x0, sp, ph, sz, y0 in self.embers:
            y = OUT_H + 20 - (y0 + lt * sp) % (OUT_H + 50)
            x = x0 + 18 * math.sin(lt * 0.8 + ph)
            fl = 0.35 + 0.35 * math.sin(lt * 5.0 + ph * 2.0)
            C.glow(cv, x, y, sz * 1.9, (int(145 * fl), int(48 * fl), int(16 * fl)))
        k = fade_in_out(lt, 0.0, dur, 0.08, 0.18)
        if k <= 0.0 or not self.text:
            return
        img = spaced(self.text, C.font("oswald", self.size), BONE, 12)
        sc = 1.0 + 0.12 * (1.0 - ease_out(clamp(lt / 0.20)))
        img = pygame.transform.smoothscale(img, (int(img.get_width() * sc), int(img.get_height() * sc)))
        img.set_alpha(int(255 * k))
        sh, _ = kick(T)
        rng = random.Random(int(T * FPS) + 3)
        dx = int(rng.uniform(-sh * 0.45, sh * 0.45))
        dy = int(rng.uniform(-sh * 0.35, sh * 0.35))
        cx = OUT_W // 2 - img.get_width() // 2 + dx
        cy = OUT_H // 2 - img.get_height() // 2 + dy
        cv.blit(img, (cx, cy))
        bar_w = int(108 * ease_out(clamp(lt / 0.28)))
        if bar_w > 2:
            s_bar = pygame.Surface((bar_w, 3), pygame.SRCALPHA)
            s_bar.fill((*self.accent, int(255 * k)))
            cv.blit(s_bar, (OUT_W // 2 - bar_w // 2, cy + img.get_height() + 18))


class TitleShot(Shot):
    """Clean stark end-card: CALL OF ACARISTAN -> tagline -> prominent framed platform CTA."""
    letterbox = False

    def __init__(self, start: float, end: float, cta: str = DEFAULT_CTA):
        super().__init__(start, end, name="title_end")
        self.cta = cta

    def setup(self):
        rng = random.Random(88)
        self.embers = [(rng.uniform(0, OUT_W), rng.uniform(26, 95), rng.uniform(0, 6.28),
                        rng.uniform(1.4, 4.4), rng.uniform(0, OUT_H)) for _ in range(95)]
        self.bg = vgrad((3, 5, 9), (18, 9, 7), OUT_W, OUT_H)
        f = C.font("oswald", 168)
        t = spaced("CALL OF ACARISTAN", f, (255, 255, 255), 14)
        grad = vgrad((246, 240, 228), (138, 128, 118), *t.get_size())
        t.blit(grad, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        self.title = t
        self.pic = pygame.Surface((PW, PH))

    def picture(self, lt: float, T: float, n: int) -> pygame.Surface:
        return self.pic

    def overlay(self, cv: pygame.Surface, lt: float, T: float) -> None:
        dur = self.end - self.start
        cv.blit(self.bg, (0, 0))
        for x0, sp, ph, sz, y0 in self.embers:
            y = OUT_H + 20 - (y0 + lt * sp) % (OUT_H + 60)
            x = x0 + 24 * math.sin(lt * 0.75 + ph)
            fl = 0.40 + 0.35 * math.sin(lt * 5.5 + ph * 2.5)
            C.glow(cv, x, y, sz * 2.0, (int(165 * fl), int(62 * fl), int(18 * fl)))

        sh, _ = kick(T)
        rng = random.Random(int(T * FPS) + 19)
        dx, dy = int(rng.uniform(-sh * 0.7, sh * 0.7)), int(rng.uniform(-sh * 0.45, sh * 0.45))
        out = 1.0 - smooth(seg(lt, dur - 1.3, dur - 0.12))

        # Main title slam (clean cut from black, zero redundant "THE CALL" repetition!)
        k1 = clamp(lt / 0.06) * out
        if k1 > 0.0:
            sc = 1.0 + 0.10 * (1.0 - ease_out(clamp(lt / 0.42)))
            img = pygame.transform.smoothscale(
                self.title, (int(self.title.get_width() * sc), int(self.title.get_height() * sc))
            )
            img.set_alpha(int(255 * k1))
            ty = OUT_H // 2 - img.get_height() // 2 - 78 + dy
            cv.blit(img, (OUT_W // 2 - img.get_width() // 2 + dx, ty))

        # Crimson rule + stark tagline
        k2 = clamp((lt - 1.1) / 0.55) * out
        if k2 > 0.0:
            rw = int(180 * clamp((lt - 1.1) / 0.45))
            bar = pygame.Surface((max(1, rw), 3), pygame.SRCALPHA)
            bar.fill((*CRIMSON, int(235 * k2)))
            cv.blit(bar, (OUT_W // 2 - rw // 2, OUT_H // 2 + 28))
            tag = spaced("EVERY ROAD HAS A PRICE.", C.font("oswald", 54), BONE, 8)
            tag.set_alpha(int(255 * k2))
            cv.blit(tag, (OUT_W // 2 - tag.get_width() // 2, OUT_H // 2 + 56))

        # Prominent framed Call-to-Action appearing early (lt=2.4s -> held >5.5s!)
        if self.cta:
            k3 = clamp((lt - 2.4) / 0.55) * out
            if k3 > 0.0:
                cta_txt = spaced(self.cta.upper(), C.font("monob", 30), BONE, 8)
                pw_b = cta_txt.get_width() + 72
                ph_b = cta_txt.get_height() + 28
                bx = OUT_W // 2 - pw_b // 2
                by = OUT_H - 220
                box_s = pygame.Surface((pw_b, ph_b), pygame.SRCALPHA)
                box_s.fill((14, 14, 18, int(210 * k3)))
                pygame.draw.rect(box_s, (*AMBER, int(245 * k3)), box_s.get_rect(), 2)
                cv.blit(box_s, (bx, by))
                cta_txt.set_alpha(int(255 * k3))
                cv.blit(cta_txt, (OUT_W // 2 - cta_txt.get_width() // 2, by + 14))


# ---------------------------------------------------------------------------
# Bar-Aligned 90.0 s Timeline (100 BPM = 2.4 s / bar)
# ---------------------------------------------------------------------------

def build_timeline(cta: str = DEFAULT_CTA) -> list[Shot]:
    return [
        # Act I: Tight Hook + First Gameplay Reveal (0.0 .. 28.8s)
        ColdOpenShot(0.0, 4.8, name="cold_snow", sat=0.78, expo=1.05, fade=(1.4, 0.22)),
        Shot(4.8, 9.6, name="ember_barn", sat=0.96, expo=1.04, fade=(0.18, 0.18)),
        CardShot(9.6, 10.8, "EVERY DEBT COMES DUE.", accent=AMBER, size=100),
        Shot(10.8, 14.4, name="patrol_march", sat=0.84, expo=1.04, fade=(0.14, 0.14)),
        Shot(14.4, 19.2, name="dawn_road", sat=0.86, expo=1.05, fade=(0.16, 0.16),
             stamp=("ROUTE 12 // BEFORE DAWN", "NORTHERN APPROACH", 0.35, 4.35)),
        Shot(19.2, 22.8, name="estate_gate", sat=0.82, expo=0.80, fade=(0.16, 0.14),
             stamp=("CAPITAL OUTSKIRTS // 03:40", "PRESIDENTIAL ESTATE", 0.30, 3.25)),
        GameplayShot(22.8, 27.6, name="gp_mansion_ots", sat=0.94, expo=1.04, fade=(0.12, 0.10)),
        CardShot(27.6, 28.8, "ONE NIGHT.", accent=CRIMSON, size=112),

        # Act II: Two Roads Escalation + Gameplay Showcase (28.8 .. 57.6s)
        Shot(28.8, 33.6, name="city_hover", sat=0.94, expo=1.06),
        Shot(33.6, 38.4, name="hall_breach", sat=0.94, expo=1.04),
        CardShot(38.4, 39.6, "TWO ROADS.", accent=AMBER, size=112),
        Shot(39.6, 43.2, name="chase_dust", sat=0.90, expo=1.04),
        GameplayShot(43.2, 45.6, name="gp_chase_lmg", sat=0.92, expo=1.04),
        GameplayShot(45.6, 50.4, name="gp_door_gunner", sat=0.96, expo=1.06),
        Shot(50.4, 54.0, name="convoy_boom", sat=0.98, expo=1.04),
        GameplayShot(54.0, 56.4, name="gp_checkpoint_ots", sat=0.94, expo=1.04),
        CardShot(56.4, 57.6, "NO WAY BACK.", accent=CRIMSON, size=110),

        # Act III: Kinetic Climax — 100% Brand-New Non-Recycled Shots (57.6 .. 76.8s)
        Shot(57.6, 60.0, name="terrace_wash", sat=0.90, expo=1.00),
        Shot(60.0, 62.4, name="rocket_streak", sat=0.96, expo=1.04),
        Shot(62.4, 64.8, name="gorge_pass", sat=0.88, expo=1.06),

        # Brand-New Rapid Flash-Montage (64.8 .. 72.0s)
        Shot(64.8, 66.0, name="flash_01", sat=0.90, expo=1.04),
        Shot(66.0, 67.2, name="flash_02", sat=0.94, expo=1.05),
        Shot(67.2, 68.4, name="flash_03", sat=0.98, expo=1.06),
        Shot(68.4, 69.0, name="flash_04", sat=0.96, expo=1.06),
        Shot(69.0, 69.6, name="flash_05", sat=0.92, expo=1.08),
        Shot(69.6, 70.2, name="flash_06", sat=0.90, expo=1.04),
        Shot(70.2, 71.1, name="flash_07", sat=0.92, expo=1.06),
        Shot(71.1, 72.0, name="flash_08", sat=0.96, expo=1.06),

        # Accelerating 6-Beat Kinetic Combat Crescendo (72.0 .. 76.8s)
        Shot(72.0, 76.8, name="climax_surge", sat=0.96, expo=1.06, fade=(0.04, 0.08)),

        # The Breath — Native 1920x804 PSO-1 Sniper Scope (76.8 .. 80.4s)
        ScopeBreathShot(76.8, 80.4, sat=0.82, expo=1.04),

        # Title Slam & End Card (80.4 .. 90.0s)
        TitleShot(80.4, TOTAL, cta=cta),
    ]


def collect_events(shots: list[Shot]) -> dict:
    events = []
    cuts = []
    for s in shots:
        cuts.append(round(s.start, 3))
        for dt_s, kind in SC.SHOT_EVENTS.get(s.name, ()):
            t_ev = s.start + dt_s
            if t_ev < s.end + 0.12:
                events.append((round(t_ev, 3), kind))
    typing_ticks = []
    for t0, txt, _col in COLD_LINES:
        for i, ch in enumerate(txt):
            if ch != " ":
                typing_ticks.append(round(t0 + i / COLD_CPS, 3))
    return {"total": TOTAL, "cuts": cuts, "events": events, "typing_ticks": typing_ticks}


# ---------------------------------------------------------------------------
# Renderer Driver
# ---------------------------------------------------------------------------

class Trailer:
    def __init__(self, cta: str = DEFAULT_CTA):
        pygame.init()
        pygame.display.set_mode((64, 64))
        self.shots = build_timeline(cta=cta)
        self.grade = CinemaGrade()
        self.canvas = pygame.Surface((OUT_W, OUT_H))
        self.pic = pygame.Surface((PW, PH))
        self._work = pygame.Surface((GW, GH))

    def shot_at(self, T: float) -> Shot:
        for s in self.shots:
            if s.start <= T < s.end:
                return s
        return self.shots[-1]

    def frame(self, T: float, n: int) -> pygame.Surface:
        s = self.shot_at(T)
        s.ensure()
        lt = max(0.0, T - s.start)
        cv = self.canvas
        cv.fill((0, 0, 0))
        sh, split = kick(T)

        if isinstance(s, ScopeBreathShot):
            s.render_full(cv, self.grade, lt, T, n)
        elif s.letterbox:
            surf = s.picture(lt, T, n)
            work = self._work
            if surf.get_size() == (GW, GH):
                work.blit(surf, (0, 0))
            else:
                pygame.transform.smoothscale(surf, (GW, GH), work)
            fade_k = 1.0
            if s.fade:
                fade_k = smooth(min(clamp(lt / s.fade[0]), clamp((s.end - T) / s.fade[1])))
            self.grade.apply(work, n, s.sat, s.expo, split, fade_k=fade_k)
            pygame.transform.scale(work, (PW, PH), self.pic)
            rng = random.Random(n * 11 + 5)
            dx = int(rng.uniform(-sh, sh))
            dy = int(rng.uniform(-sh, sh) * 0.55)
            cv.blit(self.pic, (dx, BAR + dy))
            cv.fill((0, 0, 0), (0, 0, OUT_W, BAR))
            cv.fill((0, 0, 0), (0, BAR + PH, OUT_W, OUT_H - BAR - PH))
            s.overlay(cv, lt, T)
        else:
            s.overlay(cv, lt, T)

        # Clean brief warm optical impact only on live-action Act II & III drops (NOT TitleShot!)
        for t0 in FLASH_HITS:
            d = T - t0
            if 0.0 <= d < 0.16:
                v = int(96 * math.exp(-d * 18.0))
                cv.fill((v, int(v * 0.94), int(v * 0.85)), special_flags=pygame.BLEND_RGB_ADD)

        if T > TOTAL - 1.0:
            k_out = 1.0 - smooth((T - (TOTAL - 1.0)) / 1.0)
            arr = pygame.surfarray.pixels3d(cv)
            arr[:] = np.clip(arr.astype(np.float32) * k_out, 0, 255).astype(np.uint8)
            del arr
        return cv


def render_sheet(tr: Trailer, out_dir: str) -> str:
    stills_dir = os.path.join(out_dir, "stills")
    os.makedirs(stills_dir, exist_ok=True)
    thumbs = []
    for idx, s in enumerate(tr.shots):
        frac = 0.55
        if s.name == "convoy_boom":
            frac = 0.34
        elif s.name == "gp_mansion_ots":
            frac = 0.28
        elif s.name == "gp_door_gunner":
            frac = 0.48
        elif s.name == "gp_checkpoint_ots":
            frac = 0.22
        elif s.name == "scope_breath":
            frac = 0.72
        elif s.name == "title_end":
            frac = 0.45
        elif s.name == "cold_snow":
            frac = 0.62
        T = s.start + (s.end - s.start) * frac
        cv = tr.frame(T, int(T * FPS))
        fname = f"{idx:02d}_{s.name}_t{T:05.1f}.png"
        fpath = os.path.join(stills_dir, fname)
        pygame.image.save(cv, fpath)
        thumbs.append((f"{idx:02d} {s.name} ({T:.1f}s)", pygame.transform.smoothscale(cv, (480, 270))))
        print(f"still [{idx + 1:02d}/{len(tr.shots):02d}] {fname}")

    cols = 4
    rows = (len(thumbs) + cols - 1) // cols
    sheet = pygame.Surface((cols * 480, rows * 270))
    sheet.fill((12, 12, 14))
    lab_f = C.font("mono", 16)
    for i, (label, img) in enumerate(thumbs):
        r_i, c_i = divmod(i, cols)
        x, y = c_i * 480, r_i * 270
        sheet.blit(img, (x, y))
        tag = lab_f.render(label, True, (240, 236, 224))
        bg = pygame.Surface((tag.get_width() + 10, tag.get_height() + 4))
        bg.fill((10, 10, 12))
        bg.set_alpha(205)
        sheet.blit(bg, (x + 6, y + 6))
        sheet.blit(tag, (x + 11, y + 8))
    sheet_path = os.path.join(stills_dir, "_sheet.jpg")
    pygame.image.save(sheet, sheet_path)
    print("contact sheet ->", sheet_path)
    return sheet_path


def render_video(tr: Trailer, t0: float, t1: float, out_mp4: str,
                 audio_wav: str | None = None) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(out_mp4)), exist_ok=True)
    n0 = int(round(t0 * FPS))
    n1 = int(round(t1 * FPS))
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24", "-s", f"{OUT_W}x{OUT_H}", "-r", str(FPS),
        "-i", "-",
    ]
    if audio_wav and os.path.exists(audio_wav):
        if t0 > 0.0 or t1 < TOTAL:
            cmd += ["-ss", f"{t0:.3f}", "-t", f"{(t1 - t0):.3f}"]
        cmd += ["-i", audio_wav, "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "17",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        out_mp4,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t_start = time.time()
    total_f = max(1, n1 - n0)
    try:
        for i, n in enumerate(range(n0, n1)):
            T = n / float(FPS)
            cv = tr.frame(T, n)
            proc.stdin.write(pygame.image.tobytes(cv, "RGB"))
            if (i + 1) % (FPS * 5) == 0 or i + 1 == total_f:
                el = time.time() - t_start
                fps_eff = (i + 1) / max(el, 1e-3)
                print(f"  frame {i + 1:4d}/{total_f} ({T:5.1f}s)  [{fps_eff:5.1f} fps, {el:5.1f}s elapsed]", flush=True)
    finally:
        proc.stdin.close()
        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(f"ffmpeg exited with code {rc}")
    print("video ->", out_mp4)
    return out_mp4


def main():
    ap = argparse.ArgumentParser(description="Render THE CALL 90s 2.39:1 cinematic + gameplay trailer.")
    ap.add_argument("--sheet", action="store_true", help="Render 1 still per shot + _sheet.jpg")
    ap.add_argument("--at", nargs="+", type=float, default=None, help="Render specific timestamps (seconds)")
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=TOTAL)
    ap.add_argument("--noaudio", action="store_true")
    ap.add_argument("--music", default=None, help="Optional external music track path")
    ap.add_argument("--cta", default=DEFAULT_CTA, help="End-card call-to-action text")
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "the_call_trailer.mp4"))
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    tr = Trailer(cta=args.cta)

    if args.sheet:
        render_sheet(tr, OUT_DIR)
        return

    if args.at:
        stills_dir = os.path.join(OUT_DIR, "stills")
        os.makedirs(stills_dir, exist_ok=True)
        for T in args.at:
            cv = tr.frame(T, int(T * FPS))
            fp = os.path.join(stills_dir, f"at_{T:05.2f}.png")
            pygame.image.save(cv, fp)
            print("still ->", fp)
        return

    ev_path = os.path.join(OUT_DIR, "events.json")
    with open(ev_path, "w", encoding="utf-8") as fh:
        json.dump(collect_events(tr.shots), fh, indent=1)

    wav_path = None
    if not args.noaudio:
        wav_path = SCORE.build_score(ev_path, os.path.join(OUT_DIR, "score.wav"), args.music)

    render_video(tr, args.t0, args.t1, args.out, audio_wav=wav_path)


if __name__ == "__main__":
    main()
