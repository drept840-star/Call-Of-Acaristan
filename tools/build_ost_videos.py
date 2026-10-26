"""Render the OST music videos: one seamless 3D loop per album track.

    python tools/build_ost_videos.py            # all 8 -> build/ost/video/NN_slug.mp4
    python tools/build_ost_videos.py 3 4        # only tracks 3 and 4
    python tools/build_ost_videos.py --stills   # contact sheets -> shots/ost_mv/NN_slug.png
    python tools/build_ost_videos.py --thumbs   # 1280x720 thumbnails -> build/ost/video/NN_slug.png

Needs the WAV masters from tools/build_ost.py (build/ost/NN_slug.wav), ffmpeg
and the GL backend. The loop is whole bars of one section (tools/ost/mv.py
LOOPS); its audio tail is crossfaded into its head so the MP4 loops cleanly.
"""
import os
import re
import shutil
import subprocess
import sys
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from ost.album import ALBUM  # noqa: E402

WAV_DIR = os.path.join(ROOT, "build", "ost")
OUT_DIR = os.path.join(WAV_DIR, "video")
STILL_DIR = os.path.join(ROOT, "shots", "ost_mv")
FPS = 30
XFADE = 0.25


def slug(title):
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


def ffmpeg():
    exe = shutil.which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"
    if not os.path.exists(exe) and not shutil.which(exe):
        sys.exit("ffmpeg not found")
    return exe


def read_wav(path):
    with wave.open(path, "rb") as w:
        sr, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, ch)
    return x.astype(np.float32) / 32768.0, sr


def write_wav(path, x, sr):
    with wave.open(path, "wb") as w:
        w.setnchannels(x.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def loop_audio(x, sr, start_s, loop_s):
    """The loop slice with what follows it crossfaded over its head."""
    a, n, xf = int(round(start_s * sr)), int(round(loop_s * sr)), int(XFADE * sr)
    seg = x[a:a + n].copy()
    tail = x[a + n:a + n + xf]
    if len(tail) == xf:
        ramp = np.linspace(0, 1, xf, dtype=np.float32)[:, None]
        seg[:xf] = seg[:xf] * ramp + tail * (1 - ramp)
    return seg


def _envelope(sig, sr, attack, release):
    k_a, k_r = np.exp(-1 / (attack * sr)), np.exp(-1 / (release * sr))
    out = np.empty_like(sig)
    e = 0.0
    for i, v in enumerate(sig):
        k = k_a if v > e else k_r
        e = k * e + (1 - k) * v
        out[i] = e
    return out


def features(seg, sr, n_frames):
    """Per-frame low/mid/high envelopes and a kick onset, 0..1, circular over the loop."""
    from scipy.signal import butter, sosfilt
    mono = seg.mean(axis=1)
    hop = 64
    two = np.concatenate([mono, mono])
    bands = {"low": butter(4, [30, 150], "bandpass", fs=sr, output="sos"),
             "mid": butter(4, [300, 2500], "bandpass", fs=sr, output="sos"),
             "high": butter(4, 5000, "highpass", fs=sr, output="sos")}
    out = {}
    n = len(mono)
    for name, sos in bands.items():
        y = np.abs(sosfilt(sos, two))
        y = y[: len(y) // hop * hop].reshape(-1, hop).max(axis=1)
        env = _envelope(y, sr / hop, 0.005, 0.18 if name == "low" else 0.12)
        env = env[n // hop: 2 * (n // hop)]
        out[name] = env / (np.percentile(env, 95) + 1e-6)
    low = out["low"]
    kick = np.maximum(0, np.diff(low, prepend=low[-1]))
    kick = _envelope(kick, sr / hop, 0.002, 0.12)
    out["kick"] = kick / (np.percentile(kick, 98) + 1e-6)
    idx = (np.arange(n_frames) / n_frames * len(low)).astype(int)
    return [{k: float(min(1.0, v[i])) for k, v in out.items()} for i in idx]


def track_info(num):
    from ost import mv
    title, _sub, build = ALBUM[num - 1]
    T = build()
    bar0, bars = mv.LOOPS[num]
    start = T.t(bar0, 0)
    loop_s = T.t(bar0 + bars, 0) - start
    return title, start, loop_s, T.spb


# track no -> loop bar of the thumbnail frame
THUMB_BAR = {1: 1.0, 2: 6.5, 3: 2.5, 4: 8.02, 5: 6.0, 6: 2.5, 7: 2.5, 8: 2.5}


def thumbnail(num):
    """One hero frame, upscaled to 1280x720, with the track title over a dark band."""
    from ost import mv
    from ui.pixfont import font
    title, sub, _build = ALBUM[num - 1]
    _t, _start, loop_s, spb = track_info(num)
    scene = mv.SCENES[num](title)
    scene.caption = lambda surf: None
    surf = pygame.Surface((mv.W, mv.H))
    scene.draw(surf, mv.Frame(THUMB_BAR[num] * 4 * spb, loop_s, spb, dict(low=0.5, mid=0.4, high=0.3, kick=0.0)))
    scene.release()
    img = pygame.transform.scale(surf, (1280, 720))
    band = pygame.Surface((1280, 220), pygame.SRCALPHA)
    for y in range(220):
        pygame.draw.line(band, (0, 0, 0, int(200 * (y / 220) ** 1.4)), (0, y), (1279, y))
    img.blit(band, (0, 500))
    rows = ((font("R7", 2), f"CALL OF ACARISTAN OST  -  TRACK {num:02d}", 590, (200, 190, 170)),
            (font("R7", 6), title.upper(), 620, (240, 232, 214)))
    for f, text, y, col in rows:
        for dx, dy, c in ((3, 3, (0, 0, 0)), (0, 0, col)):
            f.draw(img, text, (48 + dx, y + dy), c)
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"{num:02d}_{slug(title)}.png")
    pygame.image.save(img, out)
    print(f"thumbnail -> {out}")


def render(num, stills=False):
    from ost import mv
    title, start, loop_s, spb = track_info(num)
    name = f"{num:02d}_{slug(title)}"
    x, sr = read_wav(os.path.join(WAV_DIR, name + ".wav"))
    seg = loop_audio(x, sr, start, loop_s)
    n = int(round(loop_s * FPS))
    feats = features(seg, sr, n)
    scene = mv.SCENES[num](f"{num:02d}  {title}")
    surf = pygame.Surface((mv.W, mv.H))
    if stills:
        picks = [int(n * (k + 0.5) / 12) for k in range(12)]
        sheet = pygame.Surface((mv.W // 2 * 4, mv.H // 2 * 3))
        for c, i in enumerate(picks):
            scene.draw(surf, mv.Frame(i * loop_s / n, loop_s, spb, feats[i]))
            sheet.blit(pygame.transform.smoothscale(surf, (mv.W // 2, mv.H // 2)),
                       ((c % 4) * mv.W // 2, (c // 4) * mv.H // 2))
        os.makedirs(STILL_DIR, exist_ok=True)
        out = os.path.join(STILL_DIR, name + ".png")
        pygame.image.save(sheet, out)
        scene.release()
        print(f"{name}: {loop_s:.2f}s, {n} frames, sheet {out}")
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    wav = os.path.join(OUT_DIR, name + "_loop.wav")
    write_wav(wav, seg, sr)
    out = os.path.join(OUT_DIR, name + ".mp4")
    rate = f"{n * 1000}/{int(round(loop_s * 1000))}"
    cmd = [ffmpeg(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{mv.W}x{mv.H}", "-framerate", rate, "-i", "-",
           "-i", wav, "-vf", "scale=1280:720:flags=neighbor", "-c:v", "libx264", "-crf", "18",
           "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        scene.draw(surf, mv.Frame(i * loop_s / n, loop_s, spb, feats[i]))
        p.stdin.write(pygame.image.tobytes(surf, "RGB"))
    p.stdin.close()
    if p.wait():
        sys.exit(f"ffmpeg failed on {name}")
    scene.release()
    os.remove(wav)
    print(f"{name}: {loop_s:.2f}s, {n} frames -> {out}")


def main(argv):
    stills = "--stills" in argv
    nums = [int(a) for a in argv if a.isdigit()] or list(range(1, len(ALBUM) + 1))
    pygame.init()
    for num in nums:
        if "--thumbs" in argv:
            thumbnail(num)
        else:
            render(num, stills)


if __name__ == "__main__":
    main(sys.argv[1:])
