"""Cut 'Shell Ghost' (Soundridemusic) to the 80 s trailer timeline.

    python tools/trailer3d/music_cut.py
      in : assets/music/trailer_shell_ghost.mp3   (81.7 s, music ends ~72.5 s)
      out: assets/music/trailer_music_80s.wav     (48 kHz stereo, exactly 80.0 s)

Edit (source seconds -> trailer seconds), fitted to the recorded narration:
  T 0.0-8.0        prelude: synthesized ocean wash + low drone (TR_01 sits here)
  src 0.0-3.4      -> T 8.0-11.4      (hit src 0.86 -> T 8.86 = Biribel reveal)
  src 5.4-39.5     -> T 11.4-45.5     (2 s of decay removed, crossfaded)
  2.5 s silence    -> T 45.5-48.0     ("It was a sale." lands in silence)
  src 39.95-end    -> T 48.0-80.0     (hit src 40.10 -> T 48.15 = Ucilev reveal)
Key points on the trailer clock are exported as MARKS for the shot timeline.
"""
import os
import subprocess

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "assets", "music", "trailer_shell_ghost.mp3")
OUT = os.path.join(ROOT, "assets", "music", "trailer_music_80s.wav")
SR = 48000
TOTAL = 80.0
PRE = 8.0
TRIM_A, TRIM_B = 3.4, 5.4                     # quiet decay removed before the 2nd hit
CUT_OUT, CUT_IN, GAP = 39.5, 39.95, 2.5
SHIFT_A = PRE - (TRIM_B - TRIM_A)
SHIFT_B = SHIFT_A + CUT_OUT + GAP - CUT_IN    # trailer = src + SHIFT_B after the gap


def src_to_t(s):
    if s < TRIM_A:
        return s + PRE
    return s + SHIFT_A if s < CUT_OUT else s + SHIFT_B


# trailer-clock markers (seconds) used by the shot list
MARKS = {
    "music_in": PRE,
    "hit_biribel": src_to_t(0.86),
    "hits_act1": [round(src_to_t(s), 2) for s in (5.58, 8.88, 13.52, 16.88, 20.06, 23.28, 28.10, 34.28)],
    "sold_start": SHIFT_A + CUT_OUT,
    "sold_end": SHIFT_A + CUT_OUT + GAP,
    "hit_ucilev": src_to_t(40.10),
    "hits_act2": [round(src_to_t(s), 2) for s in (44.12, 45.68, 54.18)],
    "dip": (src_to_t(55.2), src_to_t(56.8)),
    "hit_scopes": src_to_t(56.86),
    "silence": (src_to_t(63.0), src_to_t(66.2)),
    "hit_logo": src_to_t(66.24),
    "end": TOTAL,
}


def _load():
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-ac", "2", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def _fade(a, n_in=0, n_out=0):
    a = a.copy()
    if n_in:
        a[:n_in] *= np.linspace(0, 1, n_in)[:, None]
    if n_out:
        a[-n_out:] *= np.linspace(1, 0, n_out)[:, None]
    return a


def _prelude(n):
    """Ocean wash (slow-swelling low-passed noise) + 55 Hz drone, rising into the first hit."""
    rng = np.random.default_rng(12)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for ch in range(2):
        w = rng.standard_normal(n)
        # one-pole low-pass ~ 500 Hz
        k = np.exp(-2 * np.pi * 500 / SR)
        y = np.empty(n); acc = 0.0
        for i in range(n):
            acc = acc * k + w[i] * (1 - k)
            y[i] = acc
        swell = 0.55 + 0.45 * np.sin(2 * np.pi * t / 5.5 + ch * 0.7) ** 2
        out[:, ch] = y * swell * 0.9
    drone = (np.sin(2 * np.pi * 55 * t) * 0.5 + np.sin(2 * np.pi * 82.4 * t) * 0.18
             + np.sin(2 * np.pi * 110 * t + 0.3) * 0.08)
    out += drone[:, None] * 0.09 * np.clip(t / 3.0, 0, 1)[:, None]
    env = np.clip(t / 1.5, 0, 1)                       # fade in from black
    out *= env[:, None]
    return out


def build():
    src = _load()
    s = lambda sec: int(round(sec * SR))
    x = s(0.08)                                   # crossfade over the removed decay
    a1 = src[:s(TRIM_A)].copy()
    a2 = src[s(TRIM_B) - x:s(CUT_OUT)].copy()
    a1[-x:] *= np.linspace(1, 0, x)[:, None]
    a2[:x] *= np.linspace(0, 1, x)[:, None]
    a = np.concatenate([a1[:-x], a1[-x:] + a2[:x], a2[x:]])
    a = _fade(a, n_out=s(0.35))
    b = _fade(src[s(CUT_IN):], n_in=s(0.04))
    pre = _prelude(s(PRE))
    peak = np.abs(src).max()
    pre *= (peak * 0.22) / (np.abs(pre).max() + 1e-9)
    # let the ocean bleed 2 s under the music start
    tail = _fade(_prelude(s(2.0)) * (peak * 0.22) / (np.abs(pre).max() + 1e-9), n_out=s(2.0))
    out = np.concatenate([pre, a, np.zeros((s(GAP), 2)), b])
    out[s(PRE):s(PRE) + len(tail)] += tail
    n = s(TOTAL)
    out = out[:n] if len(out) >= n else np.concatenate([out, np.zeros((n - len(out), 2))])
    out = _fade(out, n_out=s(1.0))
    out = np.clip(out, -1, 1)
    import wave
    with wave.open(OUT, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((out * 32767).astype("<i2").tobytes())
    return OUT


if __name__ == "__main__":
    print(build())
    for k, v in MARKS.items():
        print("%-12s %s" % (k, v))
