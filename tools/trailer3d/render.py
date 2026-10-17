"""Render the cinematic trailer.

    python tools/trailer3d/render.py --stills          one frame per shot -> outputs/trailer3d/stills/
    python tools/trailer3d/render.py --at 23.5         single frame at T=23.5 s
    python tools/trailer3d/render.py                   full 80 s MP4 (1920x1080, 30 fps)
    python tools/trailer3d/render.py --from 40 --to 50 --out part.mp4   a section (no audio)

Audio: assets/music/trailer_final_80s.wav (tools/trailer3d/sfx.py) if present,
else trailer_mix_80s.wav (vo_mix.py).
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

OUT_DIR = os.path.join(C.ROOT, "outputs", "trailer3d")


def load_marks():
    with open(os.path.join(HERE, "timeline.json"), encoding="utf-8") as fh:
        return json.load(fh)["marks"]


class Trailer:
    def __init__(self):
        pygame.init()
        pygame.display.set_mode((64, 64))
        import shots
        self.shots = shots.build_timeline(load_marks())
        self.grade = C.Grade()
        self.canvas = pygame.Surface((C.OUT_W, C.OUT_H))
        self.big = pygame.Surface((C.W * C.SCALE, C.H * C.SCALE))

    def shot_at(self, T):
        for s in self.shots:
            if s.start <= T < s.end:
                return s
        return self.shots[-1]

    def frame(self, T, n):
        s = self.shot_at(T)
        for o in self.shots:                       # free scenes we're done with
            if o.ready and o is not s and (o.end <= T or o.start > T + 1):
                o.release()
        s.ensure()
        lt = T - s.start
        surf = s.render(lt, T, n)
        if T < 1.6:                               # fade up from black
            k = int(255 * (1 - C.smooth(T / 1.6)))
            surf.fill((k, k, k), special_flags=pygame.BLEND_RGB_SUB)
        self.grade.apply(surf, n, grain=s.grain)
        cv = self.canvas
        cv.fill((0, 0, 0))
        pygame.transform.scale(surf, self.big.get_size(), self.big)
        if s.letterbox:
            cv.blit(self.big, (0, C.BAR))
        else:
            cv.blit(pygame.transform.scale(surf, (C.OUT_W, C.OUT_H)), (0, 0))
        s.overlay(cv, lt, T)
        return cv


def stills(tr, times=None):
    d = os.path.join(OUT_DIR, "stills")
    os.makedirs(d, exist_ok=True)
    if times is None:
        times = []
        for s in tr.shots:
            times.append(s.start + (s.end - s.start) * 0.55)
    paths = []
    for T in times:
        t0 = time.time()
        cv = tr.frame(T, int(T * C.FPS))
        p = os.path.join(d, "T%05.1f_%s.png" % (T, type(tr.shot_at(T)).__name__))
        pygame.image.save(cv, p)
        paths.append(p)
        print("%-40s %.2fs" % (os.path.basename(p), time.time() - t0), flush=True)
    return paths


def video(tr, t0, t1, out, audio=True):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
           "%dx%d" % (C.OUT_W, C.OUT_H), "-r", str(C.FPS), "-i", "-"]
    wav = None
    if audio:
        for name in ("trailer_final_80s.wav", "trailer_mix_80s.wav"):
            p = os.path.join(C.ROOT, "assets", "music", name)
            if os.path.exists(p):
                wav = p
                break
    if wav:
        cmd += ["-ss", "%.3f" % t0, "-i", wav]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart"]
    if wav:
        cmd += ["-c:a", "aac", "-b:a", "256k", "-shortest"]
    cmd += [out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n0, n1 = int(round(t0 * C.FPS)), int(round(t1 * C.FPS))
    st = time.time()
    for n in range(n0, n1):
        T = (n + 0.5) / C.FPS
        cv = tr.frame(T, n)
        p.stdin.write(pygame.image.tobytes(cv, "RGB"))
        if (n - n0) % 60 == 0:
            el = time.time() - st
            done = n - n0 + 1
            print("frame %d/%d  T=%.1f  %.1f fps  eta %.0fs" % (done, n1 - n0, T, done / max(el, 1e-6),
                                                             (n1 - n0 - done) / max(done / max(el, 1e-6), 1e-6)), flush=True)
    p.stdin.close()
    p.wait()
    print("->", out, "in %.0fs" % (time.time() - st))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", action="store_true")
    ap.add_argument("--at", type=float, nargs="*")
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=80.0)
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "call_of_acaristan_cinematic_trailer.mp4"))
    ap.add_argument("--noaudio", action="store_true")
    a = ap.parse_args()
    tr = Trailer()
    if a.stills:
        stills(tr)
    elif a.at:
        stills(tr, a.at)
    else:
        video(tr, a.t0, a.t1, a.out, audio=not a.noaudio)


if __name__ == "__main__":
    main()
