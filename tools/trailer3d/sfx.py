"""Synthesised sound design for the cinematic trailer, laid onto the
music+VO mix.

    in : assets/music/trailer_mix_80s.wav   (vo_mix.py)
         tools/trailer3d/timeline.json      (VO spans -> SFX duck under voice)
    out: assets/music/trailer_final_80s.wav (render.py picks this up)

Everything is generated from noise/sines (no samples), deterministic seed.
Event times follow the shot timeline in shots.build_timeline().
"""
import json
import os
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from music_cut import SR, TOTAL  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
MIX = os.path.join(ROOT, "assets", "music", "trailer_mix_80s.wav")
OUT = os.path.join(ROOT, "assets", "music", "trailer_final_80s.wav")
TL = os.path.join(HERE, "timeline.json")
RNG = np.random.default_rng(1207)


# ── helpers ─────────────────────────────────────────────────────────────
def noise(n):
    return RNG.standard_normal(n).astype(np.float64)


def band(x, lo=None, hi=None, soft=0.15):
    """Brick-ish FFT band filter with soft edges (lo/hi in Hz)."""
    n = len(x)
    if n < 8:
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    g = np.ones_like(f)
    if lo:
        g *= 1 / (1 + (lo / np.maximum(f, 1e-3)) ** (4 / soft * 0.15))
    if hi:
        g *= 1 / (1 + (f / hi) ** (4 / soft * 0.15))
    return np.fft.irfft(X * g, n)


def env_exp(n, tau, attack=0.002):
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t / tau)


def norm(x, peak=1.0):
    m = np.max(np.abs(x)) or 1.0
    return x / m * peak


def sine(freq, n, phase=0.0):
    t = np.arange(n) / SR
    if callable(freq):
        ph = 2 * np.pi * np.cumsum(freq(t)) / SR
    else:
        ph = 2 * np.pi * freq * t
    return np.sin(ph + phase)


def fade(x, fin=0.05, fout=0.2):
    n = len(x)
    a, b = int(fin * SR), int(fout * SR)
    w = np.ones(n)
    if a:
        w[:a] = np.linspace(0, 1, a)
    if b:
        w[-b:] *= np.linspace(1, 0, b)
    return x * w


class Bus:
    def __init__(self):
        self.L = np.zeros(int(TOTAL * SR) + SR)
        self.R = np.zeros_like(self.L)

    def add(self, t, x, gain_db=0.0, pan=0.0):
        i = int(t * SR)
        if i >= len(self.L):
            return
        x = x[: len(self.L) - i] * 10 ** (gain_db / 20)
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        self.L[i:i + len(x)] += x * l * 1.414
        self.R[i:i + len(x)] += x * r * 1.414


# ── sound recipes ───────────────────────────────────────────────────────
def gunshot(big=False, tail=0.6):
    n = int((tail + 0.3) * SR)
    crack = band(noise(n), 900, 9000) * env_exp(n, 0.012)
    body = band(noise(n), 80, 1200) * env_exp(n, 0.06 if big else 0.035)
    thump = sine(lambda t: 60 + 90 * np.exp(-t * 30), n) * env_exp(n, 0.09 if big else 0.05)
    room = band(noise(n), 150, 3000) * env_exp(n, tail * 0.35, attack=0.01) * 0.25
    return norm(crack * 0.8 + body + thump * (1.2 if big else 0.7) + room)


def boom(dur=2.0, low=38):
    n = int(dur * SR)
    sub = sine(lambda t: low + 50 * np.exp(-t * 8), n) * env_exp(n, dur * 0.3, 0.004)
    rum = band(noise(n), 30, 400) * env_exp(n, dur * 0.25, 0.01)
    crack = band(noise(n), 1500, 8000) * env_exp(n, 0.02)
    return norm(sub * 1.3 + rum + crack * 0.5)


def ring(dur=2.8, f=3150):
    n = int(dur * SR)
    t = np.arange(n) / SR
    e = np.clip(t / 0.08, 0, 1) * np.exp(-t / (dur * 0.42))
    return (sine(f, n) + 0.3 * sine(f * 1.006, n)) * e


def rain(dur, level=1.0):
    n = int(dur * SR)
    x = band(noise(n), 1200, 9000)
    drops = np.zeros(n)
    idx = RNG.integers(0, n, int(dur * 60))
    drops[idx] = RNG.uniform(0.5, 1.0, len(idx))
    k = env_exp(int(0.01 * SR), 0.002)
    drops = np.convolve(drops, k)[:n] * band(noise(n), 2000, 7000)
    return fade(norm(x * 0.6 + drops * 2.0) * level, 0.5, 0.5)


def rotor(dur, r0, r1, low=70, interior=False):
    """Blade 'whup' AM noise; rate ramps r0 -> r1 Hz."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    rate = r0 + (r1 - r0) * (t / dur) ** 1.4
    ph = 2 * np.pi * np.cumsum(rate) / SR
    am = (0.5 + 0.5 * np.cos(ph)) ** 6
    whup = band(noise(n), 60, 700 if interior else 1500) * (0.25 + am)
    hum = sine(lambda tt: low + 30 * (tt / dur), n) * 0.35
    turb = band(noise(n), 20, 160) * 0.6
    return norm(whup + hum + turb)


def tank(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    eng = sine(31, n) * (0.6 + 0.4 * sine(7.3, n)) + 0.5 * sine(62.3, n)
    rum = band(noise(n), 25, 220)
    clank = np.zeros(n)
    for k in np.arange(0.1, dur, 0.27):
        i = int(k * SR)
        m = min(n - i, int(0.05 * SR))
        clank[i:i + m] += band(noise(m), 1500, 5000) * env_exp(m, 0.008) * RNG.uniform(0.3, 0.8)
    return fade(norm(eng * 0.7 + rum + clank * 0.6), 0.8, 0.6)


def train(dur):
    n = int(dur * SR)
    rum = band(noise(n), 30, 300)
    clack = np.zeros(n)
    k = 0.15
    while k < dur:
        for off in (0.0, 0.11):
            i = int((k + off) * SR)
            m = min(n - i, int(0.06 * SR))
            if m > 0:
                clack[i:i + m] += band(noise(m), 300, 2500) * env_exp(m, 0.012)
        k += 0.82
    hiss = band(noise(n), 3000, 8000) * 0.08
    return fade(norm(rum * 0.7 + clack * 1.6 + hiss), 0.3, 0.4)


def lighter():
    n = int(1.4 * SR)
    out = np.zeros(n)
    m = int(0.03 * SR)
    out[:m] += band(noise(m), 2500, 9000) * env_exp(m, 0.004)          # flint click
    i = int(0.06 * SR)
    m2 = int(0.25 * SR)
    out[i:i + m2] += band(noise(m2), 400, 3000) * env_exp(m2, 0.06, 0.01) * 0.6   # catch
    i2 = int(0.12 * SR)
    m3 = n - i2
    out[i2:] += band(noise(m3), 150, 1200) * np.exp(-np.arange(m3) / SR / 0.7) * 0.15   # burn
    return norm(out)


def paper():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    e = np.sin(np.pi * np.clip(t / 0.45, 0, 1)) ** 2
    return norm(band(noise(n), 1500, 7000) * e * (0.6 + 0.4 * sine(23, n)))


def whoosh(dur=0.6, up=True):
    n = int(dur * SR)
    t = np.arange(n) / SR
    e = (t / dur) ** 2 if up else (1 - t / dur) ** 2
    return norm(band(noise(n), 300, 4000) * e)


def stamp():
    n = int(0.8 * SR)
    hit = band(noise(n), 80, 2500) * env_exp(n, 0.03)
    sub = sine(lambda t: 55 + 40 * np.exp(-t * 25), n) * env_exp(n, 0.18)
    return norm(hit + sub * 1.5)


def tracer_burst(n_shots, period, big=False):
    dur = n_shots * period + 0.8
    out = np.zeros(int(dur * SR))
    for k in range(n_shots):
        g = gunshot(big, tail=0.35) * RNG.uniform(0.6, 1.0)
        i = int((k * period + RNG.uniform(-0.01, 0.01)) * SR)
        i = max(0, i)
        m = min(len(out) - i, len(g))
        out[i:i + m] += g[:m]
    return norm(out)


# ── score ───────────────────────────────────────────────────────────────
def build():
    tl = json.load(open(TL))
    m = tl["marks"]
    b = Bus()
    hb = m["hit_biribel"]
    sil0, sil1 = m["silence"]
    bang = sil0 + 0.42

    # ACT 1
    b.add(hb - 0.3, rain(18.24 - hb + 0.6), -27)                          # Route 12 rain
    for t0, pan in ((hb + 0.5, -0.4), (hb + 3.0, 0.5)):
        n = int(5 * SR)
        b.add(t0, fade(band(noise(n), 200, 1800) * (0.6 + 0.4 * sine(1.7, n)), 1, 1.5), -36, pan)  # fire crackle bed
    b.add(18.24 + 1.6, paper(), -18, 0.2)                                 # file page flip
    b.add(22.88 + 0.48, lighter(), -14, 0.3)                              # Vasile lighter
    b.add(25.82 - 0.4, tank(3.46 + 0.9), -15)                             # tank low angle
    b.add(29.28 - 0.3, whoosh(0.5), -26)
    b.add(35.86 - 0.2, train(41.77 - 35.86 + 0.3), -20)                   # train
    b.add(35.86 + 0.9, fade(band(noise(int(2.1 * SR)), 300, 3000), 0.2, 0.3), -34, 0.2)  # notebook slide
    b.add(35.86 + 4.42 + 0.15, paper(), -16, 0.1)                         # cover flip
    b.add(41.77, rain(45.5 - 41.77 + 0.2), -26)                           # aerial rain
    b.add(m["sold_start"] + 0.25, stamp(), -3)                            # SOLD
    # ACT 2
    b.add(48.0 + 5.0, rotor(3.3, 1.5, 11.0), -16)                         # spin-up
    b.add(56.0, rain(1.4), -24)
    b.add(56.0, whoosh(0.4, False), -24, -0.3)
    b.add(57.3 + 0.35, boom(1.6, 45), -6)                                 # breach
    b.add(57.3 + 1.0 + 0.15, tracer_burst(8, 1 / 7.0), -12, -0.2)         # Biribel fires
    for k in (0.05, 0.3, 0.33, 0.6, 0.78):
        b.add(57.3 + 1.0 + k, gunshot(False, 0.3), -19, 0.5)              # guards return fire
    b.add(59.7, tracer_burst(7, 0.15), -17, 0.3)                          # rooftops
    b.add(60.8, rotor(1.43, 13, 13, low=55, interior=True), -16)          # cockpit
    b.add(m["hits_act2"][2], rotor(1.1, 14, 14, low=80), -14)             # gunship
    b.add(m["hits_act2"][2] + 0.2, whoosh(0.55), -12, -0.5)               # missile
    b.add(m["hits_act2"][2] + 0.75, boom(1.2, 40), -10)                   # white-out
    # ACT 3
    b.add(m["dip"][0], rain(sil0 - m["dip"][0] - 1.0), -22)               # breath + roof rain
    b.add(bang, gunshot(True, tail=2.6), -1)                              # THE shot
    b.add(bang, boom(2.6, 34), -6)
    b.add(bang + 0.05, ring(sil1 - bang), -36)                            # tinnitus into silence
    b.add(m["hit_logo"], boom(2.4, 36), -9)                               # logo slam
    return b, tl


def duck_curve(tl, n, depth_db=-7.0):
    g = np.ones(n)
    for v in tl["vo"]:
        a, z = int((v["start"] - 0.08) * SR), int((v["end"] + 0.15) * SR)
        g[max(a, 0):min(z, n)] = 10 ** (depth_db / 20)
    k = int(0.08 * SR)
    w = np.ones(k) / k
    return np.convolve(g, w, mode="same")


def main():
    with wave.open(MIX) as w:
        ch, sr, n = w.getnchannels(), w.getframerate(), w.getnframes()
        mix = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float64).reshape(-1, ch) / 32768
    assert sr == SR
    b, tl = build()
    g = duck_curve(tl, n)
    # the gunshot must cut through the voice-free silence; don't duck it
    L, R = b.L[:n] * g, b.R[:n] * g
    out = mix.copy()
    out[:, 0] += L
    out[:, 1 if ch > 1 else 0] += R
    out = np.tanh(out * 1.05) / np.tanh(1.05)
    pk = np.max(np.abs(out))
    if pk > 0.98:
        out *= 0.98 / pk
    pcm = (out * 32767).astype(np.int16)
    with wave.open(OUT, "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("wrote", os.path.relpath(OUT, ROOT), "%.1fs" % (n / SR))


if __name__ == "__main__":
    main()
