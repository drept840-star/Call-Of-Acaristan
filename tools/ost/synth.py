"""Small numpy synth for the Call of Acaristan OST.

Like the game's SFX, every sound here is code-authored: no samples. Instruments
return mono (n,) or stereo (2, n) float arrays with peak near 1.0; a Track
mixes them on a dry bus and a reverb send, then masters the result.
"""
import zlib
from functools import lru_cache

import numpy as np
from scipy import signal

SR = 44100
NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6,
        "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
QUALITY = {"": (0, 4, 7), "m": (0, 3, 7), "5": (0, 7), "sus": (0, 5, 7), "dim": (0, 3, 6),
           "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10), "maj7": (0, 4, 7, 11),
           "add9": (0, 4, 7, 14), "madd9": (0, 3, 7, 14), "m9": (0, 3, 7, 10, 14),
           "7b9": (0, 4, 7, 10, 13)}


# ---------------------------------------------------------------- pitch

def midi(n):
    if isinstance(n, (int, np.integer)):
        return int(n)
    return 12 * (int(n[-1]) + 1) + NOTE[n[:-1]]


def hz(n):
    return 440.0 * 2 ** ((midi(n) - 69) / 12)


def chord(sym, base=45):
    """'Dm' -> midi notes with the root placed in [base, base + 11]."""
    root = sym[:2] if len(sym) > 1 and sym[1] in "#b" else sym[:1]
    r = base + (NOTE[root] - base) % 12
    return [r + i for i in QUALITY[sym[len(root):]]]


def _rng(*key):
    return np.random.default_rng(zlib.crc32(repr(key).encode()))


# ---------------------------------------------------------------- filters

@lru_cache(maxsize=2048)
def _sos(kind, lo, hi=0, order=2):
    if kind == "band":
        return signal.butter(order, [lo / (SR / 2), hi / (SR / 2)], btype="band", output="sos")
    return signal.butter(order, lo / (SR / 2), btype=kind, output="sos")


def _clampf(f):
    return float(min(max(f, 20.0), SR * 0.45))


def lp(x, fc, order=2):
    return signal.sosfilt(_sos("low", _clampf(fc), 0, order), x)


def hp(x, fc, order=2):
    return signal.sosfilt(_sos("high", _clampf(fc), 0, order), x)


def bp(x, lo, hi, order=2):
    return signal.sosfilt(_sos("band", _clampf(lo), _clampf(hi), order), x)


def lp_sweep(x, fc, block=256):
    """Lowpass with a moving cutoff; coefficients step per block, state carries."""
    fc = np.broadcast_to(np.asarray(fc, float), x.shape)
    y = np.empty_like(x)
    zi = np.zeros((1, 2))
    for i in range(0, len(x), block):
        sos = _sos("low", round(_clampf(fc[i]), -1))
        y[i:i + block], zi = signal.sosfilt(sos, x[i:i + block], zi=zi)
    return y


# ---------------------------------------------------------------- oscillators

def _t(n):
    return np.arange(n) / SR


def _phase(freq, n):
    return np.cumsum(np.broadcast_to(np.asarray(freq, float), (n,))) / SR


def sine(freq, n, ph=0.0):
    return np.sin(2 * np.pi * (_phase(freq, n) + ph))


def saw(freq, n, ph=0.0):
    """PolyBLEP sawtooth."""
    p = (_phase(freq, n) + ph) % 1.0
    dt = np.broadcast_to(np.asarray(freq, float), (n,)) / SR
    y = 2 * p - 1
    m = p < dt
    x = p[m] / dt[m]
    y[m] -= x + x - x * x - 1
    m = p > 1 - dt
    x = (p[m] - 1) / dt[m]
    y[m] -= x * x + x + x + 1
    return y


def square(freq, n, ph=0.0):
    return 0.5 * (saw(freq, n, ph) - saw(freq, n, ph + 0.5))


def noise(n, rng):
    return rng.standard_normal(n)


def smooth_random(n, rate, rng):
    """Slow random control signal in [-1, 1] at about `rate` changes per second."""
    k = max(4, int(n / SR * rate) + 3)
    pts = rng.uniform(-1, 1, k)
    return np.interp(np.linspace(0, k - 3, n), np.arange(k), pts)


def vibrato(n, rate=5.2, depth=0.004, delay=0.3, ph=0.0):
    t = _t(n)
    ramp = np.clip((t - delay) / 0.4, 0, 1)
    return 1 + depth * ramp * np.sin(2 * np.pi * rate * t + ph)


# ---------------------------------------------------------------- envelopes

def env(n, a=0.005, d=0.0, s=1.0, r=0.05):
    e = np.full(n, float(s))
    a_n = min(n, max(1, int(a * SR)))
    e[:a_n] = np.linspace(0, 1, a_n, endpoint=False) * (1 if d else s)
    d_n = min(n - a_n, int(d * SR))
    if d_n > 0:
        e[a_n:a_n + d_n] = s + (1 - s) * np.exp(-5 * np.linspace(0, 1, d_n))
    r_n = min(n, max(1, int(r * SR)))
    e[-r_n:] *= np.linspace(1, 0, r_n) ** 1.5
    return e


def decay(n, tau, a=0.002):
    t = _t(n)
    return np.exp(-t / tau) * np.clip(t / a, 0, 1)


def fade(x, fin=0.0, fout=0.0):
    x = np.array(x, float)
    n = x.shape[-1]
    if fin:
        k = min(n, int(fin * SR))
        x[..., :k] *= np.linspace(0, 1, k) ** 2
    if fout:
        k = min(n, int(fout * SR))
        x[..., n - k:] *= np.linspace(1, 0, k) ** 2
    return x


def norm(x):
    m = np.max(np.abs(x))
    return x / m if m > 0 else x


# ---------------------------------------------------------------- pitched instruments

@lru_cache(maxsize=4096)
def cimbalom(f, dur=1.0, bright=1.0):
    """Hammered dulcimer: two detuned courses, stiff-string partials, hammer thump."""
    n = int(min(dur + 0.8, 4.0) * SR)
    t = _t(n)
    y = np.zeros(n)
    for course, det in enumerate((1.0, 1.0016)):
        for k in range(1, 11):
            fk = f * det * k * np.sqrt(1 + 0.00025 * k * k)
            if fk > 15000:
                break
            amp = k ** -1.15 * (bright if k > 3 else 1.0)
            y += amp * np.exp(-t / (2.8 / (1 + 0.55 * k))) * np.sin(2 * np.pi * fk * t + course * k)
    off = int(dur * SR)
    if off < n:
        y[off:] *= np.exp(-np.arange(n - off) / (0.25 * SR))
    h = int(0.012 * SR)
    y[:h] += 0.6 * bp(noise(h, _rng("ham", f)), 1200, 5000) * np.linspace(1, 0, h)
    return norm(y * np.clip(t / 0.0015, 0, 1))


@lru_cache(maxsize=1024)
def musicbox(f, dur=1.0, wobble=0.0):
    """Comb tine. `wobble` (cents) bends it like a water-damaged mechanism."""
    n = int(min(dur + 1.5, 3.5) * SR)
    t = _t(n)
    bend = 2 ** (wobble / 1200 * np.sin(2 * np.pi * 0.7 * t) - wobble / 2400 * t)
    y = np.zeros(n)
    for ratio, amp, tau in ((1, 1, 1.6), (2.0, 0.22, 0.6), (3.0, 0.1, 0.35), (4.07, 0.14, 0.2), (6.4, 0.05, 0.1)):
        y += amp * np.exp(-t / tau) * sine(f * ratio * bend, n)
    return norm(y * np.clip(t / 0.001, 0, 1))


@lru_cache(maxsize=1024)
def epiano(f, dur=1.0):
    """FM tine piano for the noir track."""
    n = int((dur + 0.5) * SR)
    t = _t(n)
    index = 2.2 * np.exp(-t / 0.3) + 0.25
    y = np.sin(2 * np.pi * f * t + index * np.sin(2 * np.pi * f * t))
    y += 0.12 * np.exp(-t / 0.05) * np.sin(2 * np.pi * f * 14 * t)
    return norm(y * np.exp(-t / 2.0) * env(n, 0.002, 0, 1, 0.5))


@lru_cache(maxsize=1024)
def pad(f, dur=4.0, cutoff=1400.0, a=0.8, r=1.5):
    n = int((dur + r) * SR)
    rng = _rng("pad", f, dur)
    out = np.zeros((2, n))
    for ch in range(2):
        y = sum(saw(f * (1 + d + rng.uniform(-0.001, 0.001)) * vibrato(n, 0.3, 0.0015, 0, rng.uniform(0, 6)),
                    n, rng.uniform()) for d in (-0.006, 0.0, 0.005))
        y = lp(y, cutoff) + 0.3 * sine(f / 2, n)
        out[ch] = y
    return norm(out) * env(n, a, 0, 1, r)


@lru_cache(maxsize=2048)
def strings(f, dur=2.0, a=0.3, r=0.8, cutoff=3200.0, trem=0.0):
    """Section of four detuned saws with delayed vibrato; `trem` = tremolo rate (Hz)."""
    n = int((dur + r) * SR)
    rng = _rng("str", f, dur, trem)
    out = np.zeros((2, n))
    for ch in range(2):
        y = np.zeros(n)
        for _ in range(4):
            fr = f * (1 + rng.uniform(-0.003, 0.003)) * vibrato(n, rng.uniform(4.8, 5.8), 0.003, 0.25, rng.uniform(0, 6))
            y += saw(fr, n, rng.uniform())
        out[ch] = hp(lp(y, cutoff), 160)
    if trem:
        out *= 0.65 + 0.35 * np.sin(2 * np.pi * trem * _t(n))
    return norm(out) * env(n, a, 0, 1, r)


@lru_cache(maxsize=2048)
def brass(f, dur=1.0, bright=2200.0, a=0.06, r=0.25):
    n = int((dur + r) * SR)
    t = _t(n)
    vib = vibrato(n, 5.0, 0.0025, 0.35)
    y = saw(f * vib, n) + 0.7 * saw(f * 1.003 * vib, n, 0.3) + 0.3 * saw(f / 2, n)
    fc = 250 + bright * (1 - np.exp(-t / 0.07)) * (0.65 + 0.35 * np.exp(-t / 0.4))
    y = lp_sweep(y, fc)
    y = np.tanh(1.5 * norm(y))
    return norm(y) * env(n, a, 0.2, 0.85, r)


@lru_cache(maxsize=1024)
def choir(f, dur=3.0, vowel="a", a=0.7, r=1.2):
    forms = {"a": ((800, 1.0), (1150, 0.5), (2900, 0.2)),
             "o": ((450, 1.0), (800, 0.45), (2830, 0.12)),
             "u": ((325, 1.0), (700, 0.3), (2530, 0.08))}[vowel]
    n = int((dur + r) * SR)
    rng = _rng("choir", f, dur, vowel)
    out = np.zeros((2, n))
    for ch in range(2):
        src = np.zeros(n)
        for _ in range(3):
            fr = f * (1 + rng.uniform(-0.004, 0.004)) * vibrato(n, rng.uniform(4.5, 5.5), 0.005, 0.2, rng.uniform(0, 6))
            src += saw(fr, n, rng.uniform())
        y = sum(g * bp(src, fm * 0.88, fm * 1.12) for fm, g in forms)
        out[ch] = y + 0.02 * hp(noise(n, rng), 4000)
    return norm(out) * env(n, a, 0, 1, r)


@lru_cache(maxsize=1024)
def organ(f, dur=2.0, a=0.04, r=0.4):
    n = int((dur + r) * SR)
    t = _t(n)
    y = sum(g * sine(f * k, n) for k, g in ((0.5, 0.5), (1, 1), (2, 0.6), (3, 0.35), (4, 0.3), (6, 0.12), (8, 0.1)))
    out = np.vstack([y * (0.85 + 0.15 * np.sin(2 * np.pi * 0.8 * t)),
                     y * (0.85 + 0.15 * np.cos(2 * np.pi * 0.8 * t))])
    return norm(out) * env(n, a, 0, 1, r)


@lru_cache(maxsize=2048)
def reed(f, dur=1.0, a=0.07, r=0.3):
    """Duduk-ish folk reed: pitch scoop on attack, delayed vibrato, breath."""
    n = int((dur + r) * SR)
    t = _t(n)
    scoop = 2 ** (-0.6 / 12 * np.exp(-t / 0.05))
    fr = f * scoop * vibrato(n, 5.6, 0.006, 0.28)
    y = 0.6 * saw(fr, n) + 0.4 * square(fr, n)
    y = lp(y, 2400) + 0.8 * bp(y, 900, 1400)
    y += 0.06 * bp(noise(n, _rng("breath", f)), 1200, 3500)
    return norm(y) * env(n, a, 0.15, 0.9, r)


@lru_cache(maxsize=2048)
def oud(f, dur=0.4, bright=1.0):
    """Fretless lute: plucked double course, pitch settling after the pick, body resonance."""
    n = int((dur + 0.6) * SR)
    t = _t(n)
    ph = _phase(f * (1 + 0.004 * np.exp(-t / 0.02)), n)
    y = np.zeros(n)
    for course, det in enumerate((1.0, 1.0025)):
        for k in range(1, 25):
            if f * k > 9000:
                break
            amp = abs(np.sin(np.pi * k * 0.13)) / k * (bright if k > 4 else 1.0)
            y += amp * np.exp(-t / (1.4 / (1 + 0.35 * k))) * np.sin(2 * np.pi * k * det * ph + course * k)
    y += 0.5 * bp(y, 180, 420)
    off = int(dur * SR)
    if off < n:
        y[off:] *= np.exp(-np.arange(n - off) / (0.08 * SR))
    h = int(0.006 * SR)
    y[:h] += 0.4 * bp(noise(h, _rng("pick", f)), 1500, 6000) * np.linspace(1, 0, h)
    return norm(y * np.clip(t / 0.001, 0, 1))


@lru_cache(maxsize=1024)
def ney(f, dur=1.0, a=0.12, r=0.35):
    """End-blown reed flute: soft scoop, slow vibrato, nearly as much breath as tone."""
    n = int((dur + r) * SR)
    t = _t(n)
    rng = _rng("ney", f, dur)
    scoop = 2 ** (-0.8 / 12 * np.exp(-t / 0.08))
    ph = _phase(f * scoop * vibrato(n, 4.6, 0.007, 0.35), n)
    tone = np.sin(2 * np.pi * ph) + 0.25 * np.sin(4 * np.pi * ph) + 0.12 * np.sin(6 * np.pi * ph)
    tone *= 1 + 0.15 * smooth_random(n, 6.0, rng)
    air = 4.0 * bp(noise(n, rng), f * 0.85, f * 1.2) + 0.15 * bp(noise(n, rng), 1500, 6000)
    chiff = 0.5 * bp(noise(n, rng), 2000, 5000) * np.exp(-t / 0.04)
    return norm(tone + air + chiff) * env(n, a, 0.2, 0.85, r)


@lru_cache(maxsize=1024)
def bass(f, dur=1.0):
    n = int((dur + 0.1) * SR)
    y = sine(f, n) + 0.35 * lp(saw(f, n), 450)
    return norm(y) * env(n, 0.004, 0.3, 0.7, 0.08)


@lru_cache(maxsize=1024)
def pulse(f, dur=0.2, cutoff=900.0):
    """Plucky filtered saw for 8th/16th bass ostinatos."""
    n = int((dur + 0.05) * SR)
    t = _t(n)
    s = saw(f, n) + 0.5 * saw(f * 1.005, n, 0.4)
    k = np.exp(-t / 0.06)
    y = lp(s, cutoff * 2.5) * k + lp(s, cutoff * 0.5) * (1 - k)
    return norm(y) * env(n, 0.002, 0.1, 0.6, 0.04)


@lru_cache(maxsize=256)
def drone(f, dur=10.0):
    n = int(dur * SR)
    rng = _rng("drone", f, dur)
    out = np.zeros((2, n))
    for ch in range(2):
        y = saw(f, n, rng.uniform()) + saw(f * 1.004, n, rng.uniform()) + 0.5 * saw(f * 1.5, n, rng.uniform())
        out[ch] = lp_sweep(y, 320 + 180 * smooth_random(n, 0.2, rng), 512) + 0.6 * sine(f / 2, n)
    return norm(out) * env(n, 3.0, 0, 1, 3.0)


@lru_cache(maxsize=256)
def glass(f, dur=4.0):
    """Cold sine pad with slow beating, for Ucilev and the snow."""
    n = int((dur + 1.5) * SR)
    rng = _rng("glass", f, dur)
    out = np.zeros((2, n))
    for ch in range(2):
        out[ch] = sine(f, n, rng.uniform()) + 0.5 * sine(f * 2.003, n) + 0.2 * sine(f * 3.01, n)
    return norm(out) * env(n, 1.2, 0, 1, 1.5)


# ---------------------------------------------------------------- percussion

@lru_cache(maxsize=64)
def kick(v=0):
    n = int(0.5 * SR)
    t = _t(n)
    y = np.sin(2 * np.pi * _phase(45 + 95 * np.exp(-t / 0.035), n)) * np.exp(-t / 0.28)
    c = int(0.004 * SR)
    y[:c] += 0.4 * hp(noise(c, _rng("kick", v)), 2000)
    return norm(y)


@lru_cache(maxsize=64)
def taiko(v=0, f0=62.0):
    n = int(1.8 * SR)
    t = _t(n)
    rng = _rng("taiko", v, f0)
    f0 *= rng.uniform(0.97, 1.03)
    body = np.sin(2 * np.pi * _phase(f0 * (1 + 0.6 * np.exp(-t / 0.025)), n)) * np.exp(-t / 0.55)
    body += 0.3 * sine(f0 * 1.6, n) * np.exp(-t / 0.25)
    skin = lp(noise(n, rng), 900) * np.exp(-t / 0.1)
    return norm(body + 0.35 * norm(skin) * 2.5)


@lru_cache(maxsize=64)
def snare(v=0, snap=1.0):
    n = int(0.45 * SR)
    t = _t(n)
    rng = _rng("snare", v)
    y = snap * bp(noise(n, rng), 1300, 7500) * np.exp(-t / 0.14) * 3
    y += 0.8 * sine(185, n) * np.exp(-t / 0.05) + 0.35 * sine(330, n) * np.exp(-t / 0.03)
    return norm(y)


@lru_cache(maxsize=64)
def hat(v=0, open_=False):
    n = int((0.35 if open_ else 0.08) * SR)
    t = _t(n)
    y = hp(noise(n, _rng("hat", v)), 7000) * np.exp(-t / (0.25 if open_ else 0.022))
    return norm(y)


@lru_cache(maxsize=64)
def rim(v=0):
    n = int(0.06 * SR)
    t = _t(n)
    y = sine(1750, n) * np.exp(-t / 0.01) + 0.6 * hp(noise(n, _rng("rim", v)), 3000) * np.exp(-t / 0.006)
    return norm(y)


@lru_cache(maxsize=64)
def metal(v=0):
    """Industrial clank: inharmonic plate modes."""
    n = int(1.2 * SR)
    t = _t(n)
    rng = _rng("metal", v)
    f0 = rng.uniform(230, 520)
    y = sum(sine(f0 * m, n) * np.exp(-t / (0.5 / k)) / k for k, m in enumerate((1, 2.32, 3.86, 5.41, 7.03), 1))
    y += 1.5 * hp(noise(n, rng), 2500) * np.exp(-t / 0.015)
    return norm(y)


@lru_cache(maxsize=64)
def clack(v=0):
    """Rail joint under a boxcar wheel."""
    n = int(0.25 * SR)
    t = _t(n)
    rng = _rng("clack", v)
    y = sine(105 * rng.uniform(0.95, 1.05), n) * np.exp(-t / 0.05)
    y += 1.2 * bp(noise(n, rng), 400, 2500) * np.exp(-t / 0.02)
    return norm(y)


@lru_cache(maxsize=64)
def doum(v=0):
    """Darbuka bass stroke, struck in the centre of the head."""
    n = int(0.7 * SR)
    t = _t(n)
    rng = _rng("doum", v)
    f0 = 92 * rng.uniform(0.98, 1.02)
    y = np.sin(2 * np.pi * _phase(f0 * (1 + 0.35 * np.exp(-t / 0.015)), n)) * np.exp(-t / 0.32)
    y += 0.25 * sine(f0 * 2.3, n) * np.exp(-t / 0.08)
    y += 0.5 * lp(noise(n, rng), 700) * np.exp(-t / 0.02)
    return norm(y)


@lru_cache(maxsize=64)
def tek(v=0):
    """Darbuka rim stroke: dry crack over the head's high modes."""
    n = int(0.3 * SR)
    t = _t(n)
    rng = _rng("tek", v)
    y = 1.6 * bp(noise(n, rng), 1800, 9000) * np.exp(-t / 0.007)
    for m, tau in ((610, 0.05), (1180, 0.035), (1730, 0.025), (2390, 0.018)):
        y += 0.5 * sine(m * rng.uniform(0.98, 1.02), n) * np.exp(-t / tau)
    return norm(y)


@lru_cache(maxsize=64)
def riq(v=0):
    """Frame drum with zils: skin tap, then a shimmer of brass jingles."""
    n = int(0.35 * SR)
    t = _t(n)
    rng = _rng("riq", v)
    y = 0.5 * bp(noise(n, rng), 700, 2500) * np.exp(-t / 0.01)
    for _ in range(8):
        s = int(rng.uniform(0, 0.008) * SR)
        y[s:] += 0.35 * sine(rng.uniform(4200, 9500), n - s) * np.exp(-t[:n - s] / rng.uniform(0.04, 0.12))
    y += 0.6 * hp(noise(n, rng), 6000) * np.exp(-t / 0.05)
    return norm(y)


@lru_cache(maxsize=64)
def timpani(f, v=0):
    n = int(2.5 * SR)
    t = _t(n)
    y = np.sin(2 * np.pi * _phase(f * (1 + 0.03 * np.exp(-t / 0.1)), n)) * np.exp(-t / 1.1)
    y += 0.35 * sine(f * 1.5, n) * np.exp(-t / 0.6) + 0.2 * sine(f * 2, n) * np.exp(-t / 0.4)
    y += 0.5 * lp(noise(n, _rng("timp", f, v)), 700) * np.exp(-t / 0.04)
    return norm(y)


@lru_cache(maxsize=16)
def boom(v=0):
    """Cinematic low impact."""
    n = int(4.5 * SR)
    t = _t(n)
    rng = _rng("boom", v)
    y = np.sin(2 * np.pi * _phase(28 + 40 * np.exp(-t / 0.15), n)) * np.exp(-t / 1.3)
    y += 0.6 * lp(noise(n, rng), 220) * np.exp(-t / 0.5) * 4
    y += 0.4 * lp(saw(36.7, n) + saw(55.0, n), 300) * np.exp(-t / 0.9)
    return norm(y)


@lru_cache(maxsize=16)
def shot(v=0):
    """Distant rifle report: crack, body, slapback."""
    n = int(2.5 * SR)
    t = _t(n)
    rng = _rng("shot", v)
    y = 2.5 * hp(noise(n, rng), 900) * np.exp(-t / 0.012)
    y += lp(noise(n, rng), 300) * np.exp(-t / 0.25) * 3
    y += 0.7 * np.sin(2 * np.pi * _phase(40 + 60 * np.exp(-t / 0.05), n)) * np.exp(-t / 0.4)
    lag = int(0.17 * SR)
    y[lag:] += 0.25 * lp(y[:-lag], 1500)
    return norm(y)


@lru_cache(maxsize=16)
def riser(dur=4.0):
    n = int(dur * SR)
    t = _t(n) / dur
    rng = _rng("riser", dur)
    y = lp_sweep(hp(noise(n, rng), 300), 300 * 20 ** t)
    y += 0.3 * sine(100 * 8 ** t, n)
    return norm(y) * t ** 2.5


@lru_cache(maxsize=32)
def braam(f, dur=2.5):
    n = int((dur + 0.6) * SR)
    t = _t(n)
    y = saw(f, n) + saw(f * 1.006, n, 0.3) + 0.7 * saw(f * 1.5, n, 0.6) + 0.5 * saw(f * 2, n)
    fc = 150 + 1300 * np.exp(-((t - 0.25) / 0.35) ** 2) + 250 * np.exp(-t / 2)
    y = np.tanh(2.0 * norm(lp_sweep(y, fc)))
    return norm(y) * env(n, 0.05, 0, 1, 0.6)


# ---------------------------------------------------------------- textures (full-length beds)

def rain(n, rng):
    out = np.zeros((2, n))
    k = int(0.006 * SR)
    for ch in range(2):
        hiss = hp(lp(noise(n, rng), 5000), 350) * 0.25
        imp = np.zeros(n)
        idx = rng.integers(0, n, int(n / SR * 60))
        imp[idx] = rng.uniform(0.2, 1.0, len(idx))
        drop = bp(noise(k, rng), 2000, 7000) * np.linspace(1, 0, k)
        out[ch] = hiss + signal.fftconvolve(imp, drop)[:n] + 0.4 * lp(noise(n, rng), 180)
    return norm(out)


def wind(n, rng, lo=250.0, hi=900.0):
    out = np.zeros((2, n))
    for ch in range(2):
        g = np.exp(1.2 * smooth_random(n, 0.4, rng))
        whistle = lp_sweep(hp(noise(n, rng), lo * 1.5), hi * 1.6 + hi * smooth_random(n, 0.25, rng), 1024)
        out[ch] = (bp(noise(n, rng), lo, hi) + 0.3 * whistle) * g
    return norm(out)


def static(n, rng):
    y = hp(noise(n, rng), 1500) * 0.3
    imp = np.zeros(n)
    idx = rng.integers(0, n, int(n / SR * 25))
    imp[idx] = rng.uniform(-1, 1, len(idx))
    return norm(y + hp(imp, 800) * 3)


def hum(n, rng):
    """50 Hz mains, the sound of an Acaristan back room."""
    y = sine(50, n) + 0.5 * sine(100, n) + 0.3 * sine(150, n) + 0.15 * sine(250, n)
    return norm(y * (1 + 0.1 * smooth_random(n, 0.5, rng)))


def rotor(n, rng, rate=5.3):
    """Gunship rotor: blade thumps over turbine whine."""
    imp = np.zeros(n)
    step = SR / rate
    pos = (np.arange(int(n / step)) * step + rng.uniform(-80, 80, int(n / step))).astype(int)
    imp[pos[(pos >= 0) & (pos < n)]] = 1.0
    k = int(0.09 * SR)
    kt = _t(k)
    thump = lp(noise(k, rng), 260) * np.exp(-kt / 0.03) * 3 + sine(68, k) * np.exp(-kt / 0.04)
    y = signal.fftconvolve(imp, thump)[:n]
    y += 0.15 * lp(noise(n, rng), 400) + 0.03 * sine(1840 * (1 + 0.002 * smooth_random(n, 0.3, rng)), n)
    return norm(y)


def crowd(n, rng):
    out = np.zeros((2, n))
    for ch in range(2):
        y = np.zeros(n)
        for lo, hi in ((300, 700), (700, 1400), (1400, 2600)):
            y += bp(noise(n, rng), lo, hi) * (1 + smooth_random(n, 5.0, rng))
        out[ch] = lp(y, 2200)
    return norm(out)


@lru_cache(maxsize=16)
def chirp(v=0):
    rng = _rng("chirp", v)
    n = int(0.4 * SR)
    y = np.zeros(n)
    f0 = rng.uniform(2800, 4200)
    for i in range(rng.integers(2, 4)):
        k = int(0.06 * SR)
        s = int(i * 0.1 * SR)
        y[s:s + k] += sine(f0 * np.linspace(1, 1.4, k), k) * np.sin(np.linspace(0, np.pi, k))
    return norm(y)


@lru_cache(maxsize=8)
def horn(dur=3.0):
    """Distant locomotive horn, minor third."""
    n = int((dur + 0.5) * SR)
    y = saw(220, n) + saw(261.6, n, 0.4) + 0.5 * saw(329.6, n, 0.7)
    y = lp(lp(y, 1100), 900)
    return norm(y) * env(n, 0.15, 0, 1, 0.5)


@lru_cache(maxsize=8)
def squelch(v=0):
    n = int(0.14 * SR)
    y = hp(noise(n, _rng("sq", v)), 1000) * env(n, 0.002, 0, 1, 0.02)
    return norm(y)


def radio(x, rng, drive=3.0, hiss=0.04):
    """AM / field-radio band: bandpass, saturation, hiss."""
    mono = x.mean(axis=0) if x.ndim == 2 else x
    y = np.tanh(drive * norm(bp(mono, 380, 3100))) / np.tanh(drive)
    return y + hiss * static(len(y), rng)


# ---------------------------------------------------------------- track bus

class Track:
    def __init__(self, bars, bpm, beats=4, seed=0, verb_s=2.8, damp=5000.0, tail=4.0, target_db=-14.0):
        self.spb = 60.0 / bpm
        self.beats = beats
        self.bars = bars
        self.n = int((bars * beats * self.spb + tail) * SR)
        self.dry = np.zeros((2, self.n))
        self.send = np.zeros((2, self.n))
        self.rng = np.random.default_rng(seed)
        self.verb = (verb_s, damp, seed)
        self.target_db = target_db

    def t(self, bar, beat=0.0):
        return (bar * self.beats + beat) * self.spb

    def dur(self, beats):
        return beats * self.spb

    def add(self, sig, t, gain=1.0, pan=0.0, verb=0.25, human=0.0):
        if human:
            t += self.rng.normal(0, human)
            gain *= 1 + self.rng.normal(0, 0.06)
        sig = np.asarray(sig, float)
        if sig.ndim == 1:
            th = (np.clip(pan, -1, 1) + 1) * np.pi / 4
            sig = np.vstack([sig * np.cos(th), sig * np.sin(th)]) * np.sqrt(2)
        elif pan:
            sig = sig * np.array([[min(1, 1 - pan)], [min(1, 1 + pan)]])
        i = int(round(t * SR))
        if i < 0:
            sig, i = sig[:, -i:], 0
        j = min(self.n, i + sig.shape[1])
        if j <= i:
            return
        seg = sig[:, :j - i] * gain
        self.dry[:, i:j] += seg
        if verb:
            self.send[:, i:j] += seg * verb

    def render(self):
        secs, damp, seed = self.verb
        wet = np.vstack([signal.fftconvolve(self.send[c], ir)[:self.n] for c, ir in enumerate(_ir(secs, damp, seed))])
        mix = hp(self.dry + wet, 35)
        return master(mix + 0.5 * hp(mix, 4500), self.target_db)


def _ir(seconds, damp, seed, predelay=0.018):
    rng = np.random.default_rng(seed + 77)
    n = int(seconds * SR)
    t = _t(n)
    ir = rng.standard_normal((2, n)) * np.exp(-6.9 * t / seconds)
    w = np.clip(t / (seconds * 0.4), 0, 1)
    ir = lp(ir * (1 - w) + lp(ir, damp * 0.35) * w, damp)
    ir = np.pad(ir, ((0, 0), (int(predelay * SR), 0)))
    return ir / np.sqrt(np.sum(ir ** 2, axis=1, keepdims=True))


def master(x, target_db=-14.0, th=0.6, ceil=0.95):
    """Level the loud passages (90th percentile of 400 ms RMS) to target, then soft-knee limit."""
    w = int(0.4 * SR)
    m = (x ** 2).mean(axis=0)
    k = len(m) // w
    rms = np.sqrt(m[:k * w].reshape(k, w).mean(axis=1))
    loud = np.percentile(rms[rms > 1e-5], 90)
    x = x * (10 ** (target_db / 20) / loud)
    a = np.abs(x)
    over = a > th
    x[over] = np.sign(x[over]) * (th + (ceil - th) * np.tanh((a[over] - th) / (ceil - th)))
    return fade(x, 0.02, 0.5)
