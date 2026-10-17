"""9:16 TikTok / YouTube Shorts / Reels cut of the cinematic trailer.

Same 80 s timeline and audio as render.py; every frame is rendered by the
16:9 pipeline, then re-laid out for a phone screen:

    blurred, darkened fill of the same shot (full 1080x1920)
    header      CALL OF ACARISTAN / OFFICIAL CINEMATIC TRAILER
    picture     the shot, zoomed per-shot (FRAMING) and centre-cropped
    subtitles   burned-in VO lines from timeline.json (most phones are muted)
    end card    centre square of the logo card, full screen

    python tools/trailer3d/vertical.py                 -> outputs/trailer3d/call_of_acaristan_vertical.mp4
    python tools/trailer3d/vertical.py --at 14 47 77   -> stills in outputs/trailer3d/vertical_stills/
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import pygame  # noqa: E402
import render  # noqa: E402

VW, VH = 1080, 1920
BAND_CY = 860                 # centre of the picture band
OUT = os.path.join(render.OUT_DIR, "call_of_acaristan_vertical.mp4")

# shot class -> (zoom of the 1920-wide picture, horizontal focus -1..1)
DEFAULT = (0.8, 0.0)
FRAMING = {
    "Scopes": (0.5625, 0.0),       # keep both scope circles
    "Rooftops": (0.7, 0.0),
    "MartialLaw": (0.75, 0.0),
    "Route12Aerial": (0.75, 0.0),
    "Train": (0.85, 0.15),
    "VasileSmoke": (0.85, -0.1),
    "Hangar": (0.8, 0.0),
    "Breath": (0.9, 0.0),
    "Ocean": (0.75, 0.0),
}


def subtitle_cues():
    with open(os.path.join(HERE, "timeline.json"), encoding="utf-8") as fh:
        tl = json.load(fh)
    cues = []
    for v in tl["vo"]:
        if v["id"] == "TR_10":            # the title card says it
            continue
        parts = [p.strip() for p in v["text"].split("/") if p.strip()]
        total = sum(len(p) for p in parts)
        t = v["start"]
        span = v["end"] - v["start"]
        for p in parts:
            d = span * len(p) / total
            cues.append((t, t + d, p))
            t += d
    return cues


def wrap(fnt, text, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if fnt.size(t)[0] > maxw and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def outlined(fnt, text, col, outline=(0, 0, 0), px=4):
    base = fnt.render(text, True, col)
    o = fnt.render(text, True, outline)
    w, h = base.get_width() + px * 2, base.get_height() + px * 2
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for dx in range(-px, px + 1, 2):
        for dy in range(-px, px + 1, 2):
            if dx * dx + dy * dy <= px * px + 1:
                s.blit(o, (px + dx, px + dy))
    s.blit(base, (px, px))
    return s


class Vertical:
    def __init__(self):
        self.tr = render.Trailer()
        import shots
        self.tags = []
        orig = shots.location_tag

        def rec(canvas, txt, lt, t_in, t_out, y=None):
            self.tags.append((txt, lt, t_in, t_out))
        shots.location_tag = rec
        self._tag = orig
        self.cues = subtitle_cues()
        self.cv = pygame.Surface((VW, VH))
        self.f_sub = C.font("oswald", 58)
        self.f_h1 = C.font("oswald", 64)
        self.f_h2 = C.font("mono", 26)
        self.head1 = render_spaced(self.f_h1, "CALL OF ACARISTAN", C.INK, 10)
        self.head2 = render_spaced(self.f_h2, "OFFICIAL CINEMATIC TRAILER", (190, 184, 172), 6)
        self._sub_cache = {}

    def subtitle(self, T):
        for a, b, txt in self.cues:
            if a <= T < b + 0.25:
                return txt
        return None

    def frame(self, T, n):
        self.tags.clear()
        full = self.tr.frame(T, n)
        s = self.tr.shot_at(T)
        name = type(s).__name__
        cv = self.cv
        if name == "Logo":
            cv.fill((10, 10, 13))
            sq = full.subsurface(((C.OUT_W - VW) // 2, 0, VW, C.OUT_H))
            cv.blit(sq, (0, (VH - C.OUT_H) // 2))
            # extend the card's dark gradient into the top/bottom
            top = (VH - C.OUT_H) // 2
            pygame.draw.rect(cv, full.get_at((C.OUT_W // 2, 2))[:3], (0, 0, VW, top))
            pygame.draw.rect(cv, full.get_at((C.OUT_W // 2, C.OUT_H - 3))[:3], (0, top + C.OUT_H, VW, top + 2))
            return cv
        pic = full.subsurface((0, C.BAR, C.OUT_W, C.OUT_H - 2 * C.BAR))
        pw, ph = pic.get_size()
        # blurred backdrop
        small = pygame.transform.smoothscale(pic, (48, 20))
        small = pygame.transform.smoothscale(small, (24, 10))
        bg = pygame.transform.smoothscale(small, (int(VH * pw / ph), VH))
        cv.blit(bg, (-(bg.get_width() - VW) // 2, 0))
        cv.fill((120, 120, 120), special_flags=pygame.BLEND_RGB_MULT)
        # picture band
        z, fx = FRAMING.get(name, DEFAULT)
        sw, sh = int(pw * z), int(ph * z)
        scaled = pygame.transform.smoothscale(pic, (sw, sh)) if z != 1 else pic
        slack = max(0, sw - VW)
        x0 = int(slack / 2 * (1 + fx))
        y0 = BAND_CY - sh // 2
        cv.blit(scaled, (0, y0), (x0, 0, VW, sh))
        pygame.draw.rect(cv, (0, 0, 0), (0, y0 - 4, VW, 4))
        pygame.draw.rect(cv, (0, 0, 0), (0, y0 + sh, VW, 4))
        # header
        a = int(255 * C.clamp((T - 1.0) / 1.0))
        if a > 0:
            h1, h2 = self.head1.copy(), self.head2.copy()
            h1.set_alpha(a); h2.set_alpha(a)
            cv.blit(h1, (VW // 2 - h1.get_width() // 2, 250))
            bar_y = 250 + h1.get_height() + 10
            pygame.draw.rect(cv, C.ORANGE, (VW // 2 - 60, bar_y, 120, 5))
            cv.blit(h2, (VW // 2 - h2.get_width() // 2, bar_y + 18))
        # location tags (recorded from the shot overlay) sit just under the picture
        for txt, lt, t_in, t_out in self.tags:
            self._tag(cv, txt, lt, t_in, t_out, y=y0 + sh + 34)
        # subtitles
        sub = self.subtitle(T)
        if sub:
            img = self._sub_cache.get(sub)
            if img is None:
                lines = wrap(self.f_sub, sub, 940)
                imgs = [outlined(self.f_sub, ln, (250, 248, 240)) for ln in lines]
                h = sum(i.get_height() for i in imgs)
                img = pygame.Surface((VW, h), pygame.SRCALPHA)
                y = 0
                for i in imgs:
                    img.blit(i, (VW // 2 - i.get_width() // 2, y))
                    y += i.get_height()
                self._sub_cache[sub] = img
            cv.blit(img, (0, y0 + sh + 120))
        return cv


def render_spaced(fnt, txt, col, spacing):
    glyphs = [fnt.render(ch, True, col) for ch in txt]
    w = sum(g.get_width() for g in glyphs) + spacing * (len(glyphs) - 1)
    s = pygame.Surface((w, fnt.get_height()), pygame.SRCALPHA)
    x = 0
    for g in glyphs:
        s.blit(g, (x, 0))
        x += g.get_width() + spacing
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--at", type=float, nargs="*")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    v = Vertical()
    if a.at:
        d = os.path.join(render.OUT_DIR, "vertical_stills")
        os.makedirs(d, exist_ok=True)
        for T in a.at:
            cv = v.frame(T, int(T * C.FPS))
            pygame.image.save(cv, os.path.join(d, "V%05.1f.png" % T))
        print("stills ->", d)
        return
    wav = None
    for nm in ("trailer_final_80s.wav", "trailer_mix_80s.wav"):
        p = os.path.join(C.ROOT, "assets", "music", nm)
        if os.path.exists(p):
            wav = p
            break
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (VW, VH),
           "-r", str(C.FPS), "-i", "-"]
    if wav:
        cmd += ["-i", wav]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-tune", "grain", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart"]
    if wav:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += [a.out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    N = int(80.0 * C.FPS)
    st = time.time()
    for n in range(N):
        T = (n + 0.5) / C.FPS
        p.stdin.write(pygame.image.tobytes(v.frame(T, n), "RGB"))
        if n % 120 == 0:
            print("frame %d/%d  %.1f fps" % (n, N, (n + 1) / max(time.time() - st, 1e-6)), flush=True)
    p.stdin.close()
    p.wait()
    print("->", a.out, "in %.0fs" % (time.time() - st))


if __name__ == "__main__":
    main()
