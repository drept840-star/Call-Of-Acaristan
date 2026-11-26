"""9:16 vertical Short/TikTok cutdown (1080x1920, 43.2 s) and thumbnails for Call of Acaristan.

    python tools/trailer_call/vertical.py                # -> outputs/trailer_call/short/the_call_short.mp4
    python tools/trailer_call/vertical.py --thumbs       # -> thumb_16x9.png (1280x720) & thumb_9x16.png
    python tools/trailer_call/vertical.py --at 2 12 30 38  # vertical stills at short-clock timestamps

Splices two bar-aligned segments of the 100 BPM trailer so the beat never slips:
  - Segment A: 45.6 .. 56.4 s (10.8 s — door gunner ADS gameplay + truck explosion + checkpoint shotgun)
  - Segment B: 57.6 .. 90.0 s (32.4 s — Act III climax, fresh montage, kinetic surge, PSO-1 scope, title)
Total: 43.2 s (18 bars at 100 BPM).
"""
from __future__ import annotations

import argparse
import math
import os
import random
import subprocess
import sys
import time
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import render as R  # noqa: E402
import score as SCORE  # noqa: E402

C = R.C
pygame = R.pygame
W, H, FPS = 1080, 1920, R.FPS
OUT_DIR = os.path.join(R.OUT_DIR, "short")

# Bar-aligned slices of the 90s widescreen master: total = 43.2s
SEGMENTS = (
    (45.6, 56.4),      # 10.8s: gp_door_gunner + convoy_boom + gp_checkpoint_ots
    (57.6, 90.0),      # 32.4s: Act III climax + The Breath + Title
)
SHORT_TOTAL = sum(b - a for a, b in SEGMENTS)

CW = 960                               # center-crop width from 1920x804 band
PIC_H = int(round(R.PH * W / CW))      # 904 px
PIC_Y = 420
SHIFT = {                              # optional horizontal crop offset (px in 1920 band)
    "gp_door_gunner": 80,
    "convoy_boom": -10,
    "gp_checkpoint_ots": 30,
    "terrace_wash": 80,
    "gorge_pass": 0,
    "scope_breath": 0,
}


def map_time(st: float) -> float:
    """Map short-clock seconds ``st`` -> widescreen master clock ``T``."""
    acc = 0.0
    for a, b in SEGMENTS:
        d = b - a
        if st < acc + d:
            return a + (st - acc)
        acc += d
    return SEGMENTS[-1][1] - 1e-4


def _fit(img: pygame.Surface, maxw: int) -> pygame.Surface:
    if img.get_width() <= maxw:
        return img
    return pygame.transform.smoothscale(img, (maxw, int(img.get_height() * maxw / img.get_width())))


def _heavy(txt: str, size: int, col=(244, 238, 226), stroke: int = 6, spacing: int = 6) -> pygame.Surface:
    f = C.font("oswald", size)
    top = R.spaced(txt, f, col, spacing)
    ink = R.spaced(txt, f, (8, 8, 10), spacing)
    out = pygame.Surface((top.get_width() + 2 * stroke, top.get_height() + 2 * stroke), pygame.SRCALPHA)
    for a in range(0, 360, 30):
        ox = stroke + int(stroke * math.cos(math.radians(a)))
        oy = stroke + int(stroke * math.sin(math.radians(a)))
        out.blit(ink, (ox, oy))
    out.blit(top, (stroke, stroke))
    return out


def _bg_fill(band: pygame.Surface) -> pygame.Surface:
    """Blurred darkened portrait fill derived from the 2.39:1 band."""
    small = pygame.transform.smoothscale(band, (64, 27))
    w = max(8, int(27 * W / H))
    bg = pygame.transform.smoothscale(small.subsurface(((64 - w) // 2, 0, w, 27)), (W, H))
    bg.fill((120, 124, 134), special_flags=pygame.BLEND_RGB_MULT)
    return bg


def _crop_band(band: pygame.Surface, scene: str = "") -> pygame.Surface:
    x0 = (R.PW - CW) // 2 + SHIFT.get(scene, 0)
    x0 = max(0, min(R.PW - CW, x0))
    return pygame.transform.smoothscale(band.subsurface((x0, 0, CW, R.PH)), (W, PIC_H))


def _header(cv: pygame.Surface, alpha_k: float) -> None:
    if alpha_k <= 0.0:
        return
    for txt, fnt, col, sp, y in (
        ("CALL OF ACARISTAN", C.font("oswald", 78), R.BONE, 8, 175),
        ("EVERY ROAD HAS A PRICE.", C.font("mono", 24), R.AMBER, 8, 282),
    ):
        s = _fit(R.spaced(txt, fnt, col, sp), W - 120)
        s.set_alpha(int(255 * alpha_k))
        cv.blit(s, (W // 2 - s.get_width() // 2, y))


class PortraitTitle:
    def __init__(self, cta: str = R.DEFAULT_CTA):
        self.cta = cta
        rng = random.Random(88)
        self.embers = [(rng.uniform(0, W), rng.uniform(32, 110), rng.uniform(0, 6.28),
                        rng.uniform(1.6, 4.6), rng.uniform(0, H)) for _ in range(110)]
        self.bg = R.vgrad((3, 5, 9), (18, 9, 7), W, H)
        f = C.font("oswald", 162)
        self.rows = []
        for txt in ("CALL OF", "ACARISTAN"):
            t = _fit(R.spaced(txt, f, (255, 255, 255), 12), W - 96)
            grad = R.vgrad((244, 238, 226), (132, 122, 112), *t.get_size())
            t.blit(grad, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
            self.rows.append(t)

    def draw(self, cv: pygame.Surface, lt: float, dur: float, T: float) -> None:
        cv.blit(self.bg, (0, 0))
        for x0, sp, ph, sz, y0 in self.embers:
            y = H + 20 - (y0 + lt * sp) % (H + 60)
            x = x0 + 24 * math.sin(lt * 0.75 + ph)
            fl = 0.40 + 0.35 * math.sin(lt * 5.5 + ph * 2.5)
            C.glow(cv, x, y, sz * 2.1, (int(165 * fl), int(62 * fl), int(18 * fl)))

        out = 1.0 - R.smooth(R.seg(lt, dur - 1.5, dur - 0.15))
        k1 = R.clamp(lt / 0.08) * out
        if k1 > 0.0:
            sc = 1.0 + 0.12 * (1.0 - R.ease_out(R.clamp(lt / 0.45)))
            y = H // 2 - 260
            for row in self.rows:
                img = pygame.transform.smoothscale(row, (int(row.get_width() * sc), int(row.get_height() * sc)))
                img.set_alpha(int(255 * k1))
                cv.blit(img, (W // 2 - img.get_width() // 2, y))
                y += 176

        k2 = R.clamp((lt - 1.1) / 0.55) * out
        if k2 > 0.0:
            rw = int(180 * R.clamp((lt - 1.1) / 0.45))
            bar = pygame.Surface((max(1, rw), 3), pygame.SRCALPHA)
            bar.fill((*R.CRIMSON, int(235 * k2)))
            cv.blit(bar, (W // 2 - rw // 2, H // 2 + 115))
            tag = _fit(R.spaced("EVERY ROAD HAS A PRICE.", C.font("oswald", 56), R.BONE, 8), W - 110)
            tag.set_alpha(int(255 * k2))
            cv.blit(tag, (W // 2 - tag.get_width() // 2, H // 2 + 150))

        if self.cta:
            k4 = R.clamp((lt - 2.4) / 0.55) * out
            if k4 > 0.0:
                cta = _fit(R.spaced(self.cta.upper(), C.font("monob", 32), R.BONE, 8), W - 180)
                pw_b = cta.get_width() + 64
                ph_b = cta.get_height() + 26
                bx = W // 2 - pw_b // 2
                by = H - 340
                box_s = pygame.Surface((pw_b, ph_b), pygame.SRCALPHA)
                box_s.fill((14, 14, 18, int(210 * k4)))
                pygame.draw.rect(box_s, (*R.AMBER, int(245 * k4)), box_s.get_rect(), 2)
                cv.blit(box_s, (bx, by))
                cta.set_alpha(int(255 * k4))
                cv.blit(cta, (W // 2 - cta.get_width() // 2, by + 13))


def _slice_audio(src_wav: str, out_wav: str) -> str:
    with wave.open(src_wav, "rb") as wf:
        sr, ch, sw = wf.getframerate(), wf.getnchannels(), wf.getsampwidth()
        raw = wf.readframes(wf.getnframes())
    pcm = np.frombuffer(raw, np.int16).reshape(-1, ch).astype(np.float32) / 32768.0
    parts = []
    xf = int(0.035 * sr)
    for idx, (a, b) in enumerate(SEGMENTS):
        seg_a = pcm[int(a * sr):int(b * sr)].copy()
        if idx > 0 and len(parts) > 0 and len(seg_a) > xf:
            fade = np.linspace(0.0, 1.0, xf, dtype=np.float32)[:, None]
            parts[-1][-xf:] = parts[-1][-xf:] * (1.0 - fade) + seg_a[:xf] * fade
            seg_a = seg_a[xf:]
        parts.append(seg_a)
    out = np.concatenate(parts, axis=0)
    # Soft fade-in on opening of short
    fi = min(int(0.08 * sr), len(out))
    out[:fi] *= np.linspace(0.0, 1.0, fi, dtype=np.float32)[:, None]
    out_i16 = (np.clip(out, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(ch)
        wf.setsampwidth(sw)
        wf.setframerate(sr)
        wf.writeframes(out_i16.tobytes())
    return out_wav


class _MasterReader:
    """Fast sequential frame reader over the already-rendered 16:9 master MP4."""
    def __init__(self, path: str):
        import cv2
        self._cv2 = cv2
        self.cap = cv2.VideoCapture(path)
        self.idx = -9
        self.cur = None

    def read_surface(self, frame_idx: int) -> pygame.Surface | None:
        if frame_idx != self.idx:
            if frame_idx != self.idx + 1:
                self.cap.set(self._cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, bgr = self.cap.read()
            if not ok:
                return None
            rgb = self._cv2.cvtColor(bgr, self._cv2.COLOR_BGR2RGB)
            self.cur = pygame.image.frombytes(rgb.tobytes(), (rgb.shape[1], rgb.shape[0]), "RGB")
            self.idx = frame_idx
        return self.cur


def render_portrait_frame(tr: R.Trailer, ptitle: PortraitTitle, st: float, n: int,
                          reader: _MasterReader | None = None) -> pygame.Surface:
    T = map_time(st)
    s = tr.shot_at(T)
    s.ensure()
    lt = max(0.0, T - s.start)
    cv = pygame.Surface((W, H))

    if isinstance(s, R.TitleShot):
        ptitle.draw(cv, lt, s.end - s.start, T)
    else:
        wide = reader.read_surface(int(round(T * FPS))) if reader is not None else None
        if wide is None:
            wide = tr.frame(T, n)
        band = wide.subsurface((0, R.BAR, R.PW, R.PH))
        cv.blit(_bg_fill(band), (0, 0))
        pic = _crop_band(band, s.name)
        cv.blit(pic, (0, PIC_Y))
        # Thin cinema rules above & below portrait band
        pygame.draw.line(cv, (24, 24, 28), (0, PIC_Y), (W, PIC_Y), 2)
        pygame.draw.line(cv, (24, 24, 28), (0, PIC_Y + PIC_H), (W, PIC_Y + PIC_H), 2)
        # Header fades out smoothly during The Breath (76.8..80.4s)
        hdr_k = 1.0 - R.smooth(R.seg(T, 76.4, 77.2))
        _header(cv, hdr_k)

    # Brief optical impact only on live-action drops (never grey over TitleShot!)
    for t0 in R.FLASH_HITS:
        d = T - t0
        if 0.0 <= d < 0.16:
            v = int(92 * math.exp(-d * 18.0))
            cv.fill((v, v, v), special_flags=pygame.BLEND_RGB_ADD)

    if st > SHORT_TOTAL - 0.9:
        v = int(255 * R.smooth((st - (SHORT_TOTAL - 0.9)) / 0.9))
        cv.fill((v, v, v), special_flags=pygame.BLEND_RGB_SUB)
    return cv


def render_thumbs(tr: R.Trailer) -> tuple[str, str]:
    os.makedirs(R.OUT_DIR, exist_ok=True)
    # Use the dramatic billowing convoy explosion peak (T=51.5s) as base visual
    wide = tr.frame(51.5, int(51.5 * FPS))
    band = wide.subsurface((0, R.BAR, R.PW, R.PH))

    # 16:9 YouTube thumbnail (1280x720)
    t16 = pygame.Surface((1280, 720))
    scaled = pygame.transform.smoothscale(band, (1280, int(round(1280 * R.PH / R.PW))))
    t16.blit(_bg_fill(band) if False else pygame.transform.smoothscale(band, (1280, 720)), (0, 0))
    # Darken lower half slightly for bold text legibility
    grad = pygame.Surface((1280, 320), pygame.SRCALPHA)
    for y in range(320):
        grad.fill((0, 0, 0, int(195 * (y / 319.0))), (0, y, 1280, 1))
    t16.blit(grad, (0, 400))
    h1 = _heavy("CALL OF ACARISTAN", 118, (248, 242, 230), stroke=7, spacing=8)
    h2 = _heavy("OFFICIAL GAMEPLAY & CINEMATIC TRAILER", 34, R.AMBER, stroke=4, spacing=5)
    t16.blit(h1, (64, 470))
    t16.blit(h2, (68, 622))
    p16 = os.path.join(R.OUT_DIR, "thumb_16x9.png")
    pygame.image.save(t16, p16)
    print("thumb 16:9 ->", p16)

    # 9:16 Shorts/TikTok thumbnail (1080x1920)
    t9 = pygame.Surface((W, H))
    t9.blit(_bg_fill(band), (0, 0))
    t9.blit(_crop_band(band, "convoy_boom"), (0, PIC_Y))
    th1 = _fit(_heavy("CALL OF ACARISTAN", 94, (248, 242, 230), stroke=6, spacing=6), W - 96)
    th2 = _fit(_heavy("EVERY ROAD HAS A PRICE", 76, R.AMBER, stroke=6, spacing=6), W - 96)
    t9.blit(th1, (W // 2 - th1.get_width() // 2, 200))
    t9.blit(th2, (W // 2 - th2.get_width() // 2, PIC_Y + PIC_H + 84))
    p9 = os.path.join(R.OUT_DIR, "thumb_9x16.png")
    pygame.image.save(t9, p9)
    print("thumb 9:16 ->", p9)
    return p16, p9


def main():
    ap = argparse.ArgumentParser(description="Render THE CALL 9:16 vertical Short + thumbnails.")
    ap.add_argument("--thumbs", action="store_true", help="Render 16:9 and 9:16 thumbnails only")
    ap.add_argument("--at", nargs="+", type=float, default=None, help="Render portrait stills at short-clock times")
    ap.add_argument("--cta", default=R.DEFAULT_CTA)
    ap.add_argument("--noaudio", action="store_true")
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "the_call_short.mp4"))
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    tr = R.Trailer(cta=args.cta)
    ptitle = PortraitTitle(cta=args.cta)

    if args.thumbs:
        render_thumbs(tr)
        return

    if args.at:
        stills_dir = os.path.join(OUT_DIR, "stills")
        os.makedirs(stills_dir, exist_ok=True)
        for st in args.at:
            cv = render_portrait_frame(tr, ptitle, st, int(st * FPS))
            fp = os.path.join(stills_dir, f"short_t{st:05.2f}.png")
            pygame.image.save(cv, fp)
            print("short still ->", fp)
        return

    src_wav = os.path.join(R.OUT_DIR, "score.wav")
    short_wav = None
    if not args.noaudio:
        if not os.path.exists(src_wav):
            ev_path = os.path.join(R.OUT_DIR, "events.json")
            SCORE.build_score(ev_path if os.path.exists(ev_path) else None, src_wav)
        short_wav = _slice_audio(src_wav, os.path.join(OUT_DIR, "short_score.wav"))

    n_frames = int(round(SHORT_TOTAL * FPS))
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
        "-i", "-",
    ]
    if short_wav and os.path.exists(short_wav):
        cmd += ["-i", short_wav, "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        args.out,
    ]
    master_mp4 = os.path.join(R.OUT_DIR, "the_call_trailer.mp4")
    reader = _MasterReader(master_mp4) if os.path.exists(master_mp4) else None
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t_start = time.time()
    try:
        for i in range(n_frames):
            st = i / float(FPS)
            cv = render_portrait_frame(tr, ptitle, st, i, reader=reader)
            proc.stdin.write(pygame.image.tobytes(cv, "RGB"))
            if (i + 1) % (FPS * 5) == 0 or i + 1 == n_frames:
                el = time.time() - t_start
                print(f"  short frame {i + 1:4d}/{n_frames} ({st:5.1f}s)  [{(i + 1) / max(el, 1e-3):5.1f} fps]", flush=True)
    finally:
        proc.stdin.close()
        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(f"ffmpeg exited with code {rc}")
    print("short video ->", args.out)


if __name__ == "__main__":
    main()
