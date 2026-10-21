"""Sound for the RPE6 trailer: "Shell Ghost" (Soundridemusic), placed so its
first hit lands on the voxel logo, under synthesised sound design driven by
the events render.py logs (boot typing, rig parts landing, every gunshot and
hit the live game fired) and the cut list.

    python tools/trailer_rpe6/score.py      outputs/trailer_rpe6/events.json -> score.wav

Everything but the music is generated from noise and sines (seeded), with the
recipes of tools/trailer3d/sfx.py.
"""
import json
import os
import subprocess
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "trailer3d"))
import sfx as X  # noqa: E402

SR = X.SR
SRC = os.path.join(ROOT, "assets", "music", "trailer", "trailer_shell_ghost.mp3")
RNG = np.random.default_rng(606)


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)


def click():
    n = int(0.014 * SR)
    return X.norm(X.band(X.noise(n), 2200, 9000) * X.env_exp(n, 0.0022))


def beep(f, dur=0.09):
    n = int(dur * SR)
    return X.fade(X.sine(f, n), 0.004, 0.03)


def clack():
    """A rig part seating: a short metallic tick over a thud."""
    n = int(0.25 * SR)
    tick = X.band(X.noise(n), 1500, 7000) * X.env_exp(n, 0.012)
    tone = X.sine(lambda t: 700 + 300 * np.exp(-t * 40), n) * X.env_exp(n, 0.05)
    thud = X.sine(lambda t: 90 + 60 * np.exp(-t * 30), n) * X.env_exp(n, 0.06)
    return X.norm(tick * 0.7 + tone * 0.4 + thud)


def impact():
    n = int(0.3 * SR)
    return X.norm(X.band(X.noise(n), 100, 1400) * X.env_exp(n, 0.035)
                  + X.band(X.noise(n), 3000, 8000) * X.env_exp(n, 0.006) * 0.4)


def slowed(x, k=4.0):
    """Pitch-and-time stretch by k (a slow-motion report)."""
    n = int(len(x) * k)
    return np.interp(np.arange(n) / k, np.arange(len(x)), x)


def drone(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    swell = np.clip(t / dur, 0, 1) ** 1.6
    sub = (X.sine(41.0, n) + 0.5 * X.sine(61.7, n)) * (0.3 + 0.7 * swell)
    air = X.band(X.noise(n), 180, 1400) * (0.15 + 0.85 * swell)
    return X.fade(sub * 0.8 + air * 0.35, 0.8, 0.05)


def tear(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    gate = (np.sin(2 * np.pi * 38 * t) > 0.2).astype(float)
    x = X.band(X.noise(n), 500, 6000) * gate
    return X.norm(np.round(x * 6) / 6)


def wind(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    mod = 0.6 + 0.4 * np.sin(2 * np.pi * 0.35 * t) * np.sin(2 * np.pi * 0.13 * t + 1.0)
    return X.fade(X.norm(X.band(X.noise(n), 140, 900) * mod), 0.4, 0.3)


def exhale():
    n = int(1.1 * SR)
    t = np.arange(n) / SR
    e = np.clip(t / 0.18, 0, 1) * np.exp(-np.clip(t - 0.18, 0, None) / 0.35)
    return X.norm(X.band(X.noise(n), 300, 2600) * e)


def build(ev, out):
    total = ev["total"]
    bus = X.Bus()
    n = len(bus.L)
    # music
    m = decode(SRC)
    i0 = int(ev["music_at"] * SR)
    k = min(len(m), n - i0)
    bus.L[i0:i0 + k] += m[:k, 0] * 0.9
    bus.R[i0:i0 + k] += m[:k, 1] * 0.9
    # boot: drone, typing, OK, the tear, the riser into the logo hit
    bus.add(0.2, drone(5.85), -20)
    for i, t in enumerate(ev["boot_ticks"]):
        bus.add(t, click(), -27 + RNG.uniform(-3, 2), pan=RNG.uniform(-0.3, 0.3))
    bus.add(ev["boot_ok"], beep(1320), -27)
    bus.add(ev["boot_ok"] + 0.11, beep(1760), -27)
    bus.add(5.3, tear(0.62), -24)
    bus.add(4.75, X.whoosh(1.25, up=True), -15)
    big = ev["flash"]
    for t in big:
        bus.add(t, X.boom(2.4 if t in (6.0, 71.3) else 1.4), -5 if t in (6.0, 71.3) else -11)
    bus.add(6.0, X.whoosh(0.9, up=False), -16)
    # the rig, part by part
    for t in ev.get("lands", []):
        bus.add(t, clack(), -17, pan=RNG.uniform(-0.4, 0.4))
    # whooshes into the montage cuts
    for t in ev["cuts"]:
        if 45.0 < t < 62.5:
            bus.add(t - 0.32, X.whoosh(0.32, up=True), -21, pan=RNG.uniform(-0.5, 0.5))
    # the game's own fire
    shot = X.gunshot(tail=0.45)
    for t, kind in ev["events"]:
        if kind == "shot":
            bus.add(t, shot, -10 + RNG.uniform(-1.5, 0.5), pan=RNG.uniform(-0.15, 0.15))
        elif kind == "shot_slow":
            bus.add(t, slowed(X.gunshot(big=True, tail=0.8)), -6)
            bus.add(t, X.boom(1.6), -14)
        elif kind == "hit":
            bus.add(t + 0.03, impact(), -18, pan=RNG.uniform(-0.4, 0.4))
    # the quiet before the title
    q0, q1 = ev.get("quiet", (68.55, 71.3))
    bus.add(q0, wind(q1 - q0 + 0.8), -26)
    bus.add(q0 + 1.3, exhale(), -25)
    bus.add(71.3, X.ring(3.2, 2480), -34)
    bus.add(ev.get("powered", 76.0), X.stamp(), -15)
    mix = np.stack([bus.L, bus.R], 1)[: int(total * SR)]
    tail = int(1.2 * SR)                       # fade with the picture
    mix[-tail:] *= np.linspace(1, 0, tail)[:, None] ** 1.5
    ref = np.percentile(np.abs(mix), 99.95) or 1.0
    mix = np.tanh(mix / ref * 1.05) * 0.89 * 0.72     # ~-14 LUFS integrated (ebur128)
    pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("score ->", out)
    return out


if __name__ == "__main__":
    d = os.path.join(ROOT, "outputs", "trailer_rpe6")
    with open(os.path.join(d, "events.json"), encoding="utf-8") as fh:
        build(json.load(fh), os.path.join(d, "score.wav"))
