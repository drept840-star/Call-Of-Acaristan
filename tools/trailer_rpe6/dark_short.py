"""Vertical 1080x1920 Short of the dark trailer, and thumbnails for both.

    python tools/trailer_rpe6/dark_short.py                 short MP4 -> outputs/trailer_dark/short/
    python tools/trailer_rpe6/dark_short.py --at 40 63      vertical stills
    python tools/trailer_rpe6/dark_short.py --thumbs        thumb_trailer.png (1280x720), thumb_short.png

The dark films render at a fixed size, so the Short re-frames the trailer's own
frames: the scope band cropped to the middle and scaled up, over a blurred copy of
itself.  Slam cards and the title are redrawn for the narrow frame.  The sound is
the trailer's score.wav, so render the trailer (dark.py) first.
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
import dark as D  # noqa: E402

R, C, pygame = D.R, D.C, D.pygame
clamp, smooth, seg, ease_out = D.clamp, D.smooth, D.seg, D.ease_out
W, H, FPS = 1080, 1920, D.FPS
T0, T1 = D.B(13), D.TOTAL                 # from the big hit into the raid, to the end
OUT = os.path.join(D.OUT_DIR, "short")
CW = 960                                  # band crop width (of PW), scaled up to W
PIC_H = int(D.PH * W / CW)
PIC_Y = 380
SHIFT = {}                                # scene -> crop offset from centre, band px


def _fit(img, maxw):
    if img.get_width() <= maxw:
        return img
    return pygame.transform.smoothscale(img, (maxw, int(img.get_height() * maxw / img.get_width())))


def heavy(txt, size, col=(255, 255, 255), stroke=6, spacing=6):
    """Bold caps with a dark outline, for thumbnails."""
    f = C.font("oswald", size)
    top = R.spaced(txt, f, col, spacing)
    ink = R.spaced(txt, f, (8, 6, 6), spacing)
    out = pygame.Surface((top.get_width() + 2 * stroke, top.get_height() + 2 * stroke), pygame.SRCALPHA)
    for a in range(0, 360, 30):
        out.blit(ink, (stroke + int(stroke * math.cos(math.radians(a))),
                       stroke + int(stroke * math.sin(math.radians(a)))))
    out.blit(top, (stroke, stroke))
    return out


def lines_to_fit(text, fnt, spacing, maxw):
    words, out = text.split(), []
    for w in words:
        trial = (out[-1] + " " + w) if out else w
        if out and R.spaced(trial, fnt, (0, 0, 0), spacing).get_width() <= maxw:
            out[-1] = trial
        else:
            out.append(w)
    if len(out) == 2:                               # balance two rows: "THEY CAME / AT NIGHT."
        width = lambda s: R.spaced(s, fnt, (0, 0, 0), spacing).get_width()
        out = min(([" ".join(words[:i]), " ".join(words[i:])] for i in range(1, len(words))),
                  key=lambda rows: max(width(r) for r in rows))
    return out


def fill(band):
    """A blurred, darkened copy of ``band`` that covers the whole portrait frame."""
    small = pygame.transform.smoothscale(band, (64, 27))
    w = int(27 * W / H)
    bg = pygame.transform.smoothscale(small.subsurface(((64 - w) // 2, 0, w, 27)), (W, H))
    bg.fill((150, 150, 150), special_flags=pygame.BLEND_RGB_MULT)
    return bg


def picture(band, scene=""):
    x0 = (D.PW - CW) // 2 + SHIFT.get(scene, 0)
    return pygame.transform.smoothscale(band.subsurface((x0, 0, CW, D.PH)), (W, PIC_H))


def header(cv, k):
    if k <= 0:
        return
    for txt, fnt, col, sp, y in (("CALL OF ACARISTAN", C.font("oswald", 84), (236, 230, 220), 10, 170),
                                 ("MISSION 7 // FALLOW GROUND", C.font("mono", 28), D.BLOOD, 8, 290)):
        s = _fit(R.spaced(txt, fnt, col, sp), W - 120)
        s.set_alpha(int(255 * k))
        cv.blit(s, (W // 2 - s.get_width() // 2, y))


def slam(cv, card, lt, T):
    dur = card.end - card.start
    fl = 0.9 + 0.1 * random.Random(int(T * FPS)).random()
    k = R.fade_in_out(lt, 0.0, dur - 0.05, 0.04, 0.2) * fl
    if k <= 0 or not card.text:
        return
    fnt = C.font("oswald", 112)
    rows = lines_to_fit(card.text, fnt, 12, W - 120)
    sc = 1.0 + 0.18 * (1 - ease_out(clamp(lt / 0.18)))
    y = PIC_Y + PIC_H // 2 - len(rows) * 70
    for row in rows:
        img = R.spaced(row, fnt, D.BONE, 12)
        img = pygame.transform.smoothscale(img, (int(img.get_width() * sc), int(img.get_height() * sc)))
        img.set_alpha(int(255 * clamp(k)))
        cv.blit(img, (W // 2 - img.get_width() // 2, y))
        y += 140


class Title:
    """The trailer's end card, stacked for portrait."""
    def __init__(self):
        rng = random.Random(4)
        self.embers = [(rng.uniform(0, W), rng.uniform(30, 110), rng.uniform(0, 6.3),
                        rng.uniform(1.5, 5.0), rng.uniform(0, H)) for _ in range(120)]
        self.bg = R.vgrad((2, 2, 3), (16, 6, 4), W, H)
        f = C.font("oswald", 168)
        self.rows = []
        for txt in ("CALL OF", "ACARISTAN"):
            t = _fit(R.spaced(txt, f, (255, 255, 255), 16), W - 100)
            grad = R.vgrad((236, 230, 220), (110, 100, 92), *t.get_size())
            t.blit(grad, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
            self.rows.append(t)

    def draw(self, cv, lt, T, dur):
        cv.blit(self.bg, (0, 0))
        for x0, sp, ph, sz, y0 in self.embers:
            y = H + 20 - (y0 + lt * sp) % (H + 60)
            x = x0 + 22 * math.sin(lt * 0.7 + ph)
            fl = 0.4 + 0.35 * math.sin(lt * 6 + ph * 3)
            C.glow(cv, x, y, sz * 2.0, (int(150 * fl), int(40 * fl), int(12 * fl)))
        sh, _ = D.kick(T)
        rng = random.Random(int(T * FPS))
        dx, dy = int(rng.uniform(-sh, sh)), int(rng.uniform(-sh, sh))
        out = 1 - smooth(seg(lt, dur - 1.6, dur - 0.2))
        k1 = clamp(lt / 0.06) * (1 - smooth(seg(lt, 5.2, 5.9)))
        if k1 > 0:
            sc = 1.0 + 0.1 * (1 - ease_out(clamp(lt / 0.5)))
            y = 640
            for t in self.rows:
                img = pygame.transform.smoothscale(t, (int(t.get_width() * sc), int(t.get_height() * sc)))
                img.set_alpha(int(255 * k1))
                cv.blit(img, (W // 2 - img.get_width() // 2 + dx, y + dy))
                y += 200
            k = R.fade_in_out(lt, 1.6, 5.6, 0.8, 0.4)
            if k > 0:
                s = _fit(R.spaced("MISSION 7 // FALLOW GROUND", C.font("mono", 34), D.BLOOD, 10), W - 120)
                s.set_alpha(int(255 * k))
                cv.blit(s, (W // 2 - s.get_width() // 2, 1080))
        for txt, t0, y in (("DUTY.", 6.0, 700), ("OR REVENGE.", 7.0, 840)):
            k = clamp((lt - t0) / 0.5) * out
            if k > 0:
                s = R.spaced(txt, C.font("oswald", 120), D.BONE if t0 < 7 else D.BLOOD, 12)
                s.set_alpha(int(255 * k))
                cv.blit(s, (W // 2 - s.get_width() // 2, y))
        k = clamp((lt - 8.6) / 0.6) * out
        if k > 0:
            for txt, fnt, col, sp, y in (("COMING SOON", C.font("mono", 34), D.ASH, 10, 1040),
                                         ('Music: "Dark Cello Horror Trailer Music"', C.font("mono", 20),
                                          (96, 92, 88), 1, 1420)):
                s = R.spaced(txt, fnt, col, sp)
                s.set_alpha(int(255 * k))
                cv.blit(s, (W // 2 - s.get_width() // 2, y))


class Short:
    def __init__(self):
        self.tr = D.Trailer()
        self.cv = pygame.Surface((W, H))
        self.title = Title()

    def frame(self, T, n):
        tr, cv = self.tr, self.cv
        s = tr.shot_at(T)
        lt = T - s.start
        full = tr.frame(T, n)                       # graded, shaken, flashed: the trailer's frame
        cv.fill((0, 0, 0))
        if isinstance(s, D.Title):
            self.title.draw(cv, lt, T, s.end - s.start)
        elif isinstance(s, D.Card):
            s.ensure()
            slam(cv, s, lt, T)
        else:
            band = full.subsurface((0, D.BAR, D.PW, D.PH))
            cv.blit(fill(band), (0, 0))
            cv.blit(picture(band, getattr(s, "scene", "")), (0, PIC_Y))
            header(cv, clamp((T - T0 - 0.6) / 0.6))
        for t0 in D.STRONG:
            d = T - t0
            if 0 <= d < 0.35:
                v = int(200 * math.exp(-d * 12.0))
                cv.fill((v, v, v), special_flags=pygame.BLEND_RGB_ADD)
        if T > D.TOTAL - 1.0:
            v = int(255 * smooth((T - (D.TOTAL - 1.0)) / 1.0))
            cv.fill((v, v, v), special_flags=pygame.BLEND_RGB_SUB)
        return cv


def video(sh, out):
    os.makedirs(OUT, exist_ok=True)
    silent = out[:-4] + "_picture.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", silent]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n0, n1 = int(round(T0 * FPS)), int(round(T1 * FPS))
    st = time.time()
    for n in range(n0, n1):
        T = (n + 0.5) / FPS
        p.stdin.write(pygame.image.tobytes(sh.frame(T, n), "RGB"))
        if (n - n0) % 90 == 0:
            done = n - n0 + 1
            print("frame %d/%d  T=%.1f  %.1f fps" % (done, n1 - n0, T, done / max(time.time() - st, 1e-6)),
                  flush=True)
    p.stdin.close()
    p.wait()
    wav = os.path.join(D.OUT_DIR, "score.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-ss", "%.3f" % T0, "-t", "%.3f" % (T1 - T0),
                    "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                    "-shortest", "-movflags", "+faststart", out], check=True)
    os.remove(silent)
    print("->", out)


def stills(sh, times):
    os.makedirs(os.path.join(OUT, "stills"), exist_ok=True)
    for T in times:
        path = os.path.join(OUT, "stills", "V%06.2f.png" % T)
        pygame.image.save(sh.frame(T, int(T * FPS)), path)
        print(path)


def hero(t_ms=1200.0, expo=1.55, sat=0.75):
    """The thumbnail scene, graded like the trailer, as a PW x PH band."""
    s = D.Scene(0.0, 4.0, scene="thumb_hero", expo=expo, sat=sat)
    s.ensure()
    pic = s.picture(t_ms / 1000.0, 0.0, 0).copy()
    D.Grit().apply(pic, 0, sat, expo, 0)
    return pic


def thumbs():
    os.makedirs(OUT, exist_ok=True)
    band = hero()
    # trailer: 1280x720, the scope band cut to 16:9
    cw = int(D.PH * 16 / 9)
    x0 = D.PW - cw                         # Biribel on the right, words on the left
    th = pygame.transform.smoothscale(band.subsurface((x0, 0, cw, D.PH)), (1280, 720))
    shade = pygame.Surface((1280, 720), pygame.SRCALPHA)
    for x in range(640):
        a = int(170 * (1 - x / 640.0) ** 1.6)
        pygame.draw.line(shade, (0, 0, 0, a), (x, 0), (x, 720))
    th.blit(shade, (0, 0))
    y = 70
    for row, col in (("THEY BURNED", (240, 236, 228)), ("IT ALL.", D.BLOOD)):
        img = heavy(row, 132, col, stroke=6, spacing=4)
        th.blit(img, (54, y))
        y += 150
    t = heavy("CALL OF ACARISTAN", 54, (236, 230, 220), stroke=4, spacing=8)
    th.blit(t, (58, 720 - 150))
    s = R.spaced("MISSION 7 // FALLOW GROUND", C.font("monob", 26), D.BLOOD, 6)
    th.blit(s, (64, 720 - 78))
    pygame.image.save(th, os.path.join(OUT, "thumb_trailer.png"))
    # short: 1080x1920, the Short's own layout with the hook on top
    cv = pygame.Surface((W, H))
    cv.blit(fill(band), (0, 0))
    x0 = D.PW - CW
    cv.blit(pygame.transform.smoothscale(band.subsurface((x0, 0, CW, D.PH)), (W, PIC_H)), (0, 560))
    y = 150
    for row, col in (("THEY BURNED", (240, 236, 228)), ("IT ALL.", D.BLOOD)):
        img = _fit(heavy(row, 170, col, stroke=8, spacing=4), W - 60)
        cv.blit(img, (W // 2 - img.get_width() // 2, y))
        y += 200
    t = _fit(heavy("CALL OF ACARISTAN", 88, (236, 230, 220), stroke=5, spacing=8), W - 80)
    cv.blit(t, (W // 2 - t.get_width() // 2, 560 + PIC_H + 50))
    s = R.spaced("MISSION 7 // FALLOW GROUND", C.font("monob", 34), D.BLOOD, 8)
    cv.blit(s, (W // 2 - s.get_width() // 2, 560 + PIC_H + 180))
    pygame.image.save(cv, os.path.join(OUT, "thumb_short.png"))
    print(os.path.join(OUT, "thumb_trailer.png"))
    print(os.path.join(OUT, "thumb_short.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--at", type=float, nargs="*")
    ap.add_argument("--thumbs", action="store_true")
    ap.add_argument("--out", default=os.path.join(OUT, "acaristan_dark_short.mp4"))
    a = ap.parse_args()
    R.OUT_DIR = D.OUT_DIR
    if a.thumbs:
        pygame.init()
        pygame.display.set_mode((64, 64))
        thumbs()
        return
    sh = Short()
    if a.at:
        stills(sh, a.at)
    else:
        video(sh, a.out)


if __name__ == "__main__":
    main()
